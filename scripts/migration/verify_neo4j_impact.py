"""Verify bounded Neo4j dependency evidence against the SQLite snapshot."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from statistics import mean

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings
from backend.app.persistence.neo4j.driver import managed_neo4j_connection
from backend.app.persistence.neo4j.impact import Neo4jImpactQueryService
from backend.app.persistence.neo4j.importer import load_source_dataset
from backend.app.persistence.neo4j.repository import Neo4jReadRepository
from backend.app.migration_baseline import _capacity_target


BASELINE_PATH = PROJECT_ROOT / "docs/migration/baseline/SCENARIOS.json"
INACTIVE_STATUSES = {"DELIVERED", "CANCELLED", "COMPLETED"}
REMAINING_STATUSES = {"CURRENT", "PLANNED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sqlite", type=Path, required=True)
    parser.add_argument(
        "--report-out",
        type=Path,
        default=Path("docs/migration/phase4/IMPACT_REPORT.json"),
    )
    parser.add_argument("--snapshot-id", default=None)
    parser.add_argument("--import-scope", default=None)
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--result-limit", type=int, default=500)
    return parser.parse_args()


def _source_dependency_ids(dataset, target_type: str, target_id: str) -> set[str]:
    matches = set()
    for shipment in dataset.shipments:
        if shipment.status.upper() in INACTIVE_STATUSES:
            continue
        for leg in shipment.remaining_route_legs():
            if leg.status.upper() not in REMAINING_STATUSES:
                continue
            if target_type == "ROUTE" and leg.route_id == target_id:
                matches.add(shipment.shipment_id)
            if target_type == "LOCATION":
                current_location_match = (
                    leg.source_location_id == shipment.current_location_id
                    and leg.source_location_id == target_id
                )
                destination_match = leg.destination_location_id == target_id
                if current_location_match or destination_match:
                    matches.add(shipment.shipment_id)
    return matches


def _validate_evidence(result, dataset, route_by_id, location_ids) -> list[str]:
    shipment_by_id = {item.shipment_id: item for item in dataset.shipments}
    errors = []
    for evidence in result.evidence:
        shipment = shipment_by_id.get(evidence.shipment_id)
        route = route_by_id.get(evidence.route_id)
        if shipment is None:
            errors.append(f"missing shipment {evidence.shipment_id}")
            continue
        if route is None:
            errors.append(f"missing route {evidence.route_id}")
        if evidence.plan_id != f"{evidence.shipment_id}:v1":
            errors.append(f"wrong plan {evidence.plan_id} for {evidence.shipment_id}")
        if evidence.plan_version != 1:
            errors.append(f"wrong plan version for {evidence.plan_id}")
        if evidence.leg_id != f"{evidence.plan_id}:{evidence.sequence_no}":
            errors.append(f"wrong leg identity {evidence.leg_id}")
        if evidence.leg_status.upper() == "COMPLETED":
            errors.append(f"completed leg returned {evidence.leg_id}")
        if route is not None and (
            evidence.source_location_id != route.source_location_id
            or evidence.destination_location_id != route.destination_location_id
        ):
            errors.append(f"route endpoint mismatch {evidence.route_id}")
        if evidence.target_type == "LOCATION" and evidence.target_id not in location_ids:
            errors.append(f"unknown location target {evidence.target_id}")
        if evidence.target_type == "ROUTE" and evidence.target_id != evidence.route_id:
            errors.append(f"route target mismatch {evidence.route_id}")
        if not evidence.graph_path:
            errors.append(f"empty graph path {evidence.leg_id}")
    return errors


def _baseline_ids(frozen: dict, scenario_name: str) -> set[str] | None:
    scenario = frozen.get("scenarios", frozen).get(scenario_name, {})
    if "affected_shipment_ids" in scenario:
        return set(scenario["affected_shipment_ids"])
    if scenario_name == "identical_repeated_requests":
        return set(scenario.get("first", {}).get("affected_shipment_ids", []))
    return None


def main() -> int:
    args = parse_args()
    if args.max_depth < 1 or args.max_depth > 5:
        raise SystemExit("--max-depth must be between 1 and 5")
    frozen = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    dataset = load_source_dataset(args.source_sqlite)
    capacity_route_id, _ = _capacity_target(dataset)
    first_shipment = sorted(dataset.shipments, key=lambda item: item.shipment_id)[0]
    cases = [
        ("singapore_closure", "LOCATION", "LOC_WPI_50000", "PORT_CLOSURE"),
        ("port_klang_closure", "LOCATION", "LOC_WPI_49930", "PORT_CLOSURE"),
        ("port_klang_congestion", "LOCATION", "LOC_WPI_49930", "CONGESTION"),
        ("reduced_capacity", "ROUTE", capacity_route_id, "CAPACITY_REDUCTION"),
        ("no_feasible_route", "LOCATION", first_shipment.destination_location_id, "PORT_CLOSURE"),
        ("multi_shipment_contention", "LOCATION", "LOC_WPI_50000", "PORT_CLOSURE"),
        ("identical_repeated_requests", "LOCATION", "LOC_WPI_50000", "PORT_CLOSURE"),
    ]
    route_by_id = {route.route_id: route for route in dataset.routes}
    location_ids = {location.location_id for location in dataset.locations}
    report_cases = []
    query_times = []

    with managed_neo4j_connection(settings) as manager:
        repository_kwargs = {}
        if args.snapshot_id is not None:
            repository_kwargs["snapshot_id"] = args.snapshot_id
        if args.import_scope is not None:
            repository_kwargs["import_scope"] = args.import_scope
        repository = Neo4jReadRepository(manager, **repository_kwargs)
        service = Neo4jImpactQueryService(
            manager,
            snapshot_id=repository.snapshot_id,
            import_scope=repository.import_scope,
            result_limit=args.result_limit,
        )
        for scenario_name, target_type, target_id, disruption_type in cases:
            if target_type == "LOCATION":
                result = service.analyze_location(target_id, disruption_type)
            else:
                result = service.analyze_route(target_id, disruption_type)
            query_times.append(result.query_duration_ms)
            expected = _source_dependency_ids(dataset, target_type, target_id)
            actual = set(result.impacted_shipment_ids)
            frozen_ids = _baseline_ids(frozen, scenario_name)
            evidence_errors = _validate_evidence(
                result, dataset, route_by_id, location_ids
            )
            frozen_coverage = frozen_ids is None or frozen_ids <= actual
            report_cases.append({
                "scenario": scenario_name,
                "target_type": target_type,
                "target_id": target_id,
                "disruption_type": disruption_type,
                "query_name": result.query_name,
                "query_duration_ms": result.query_duration_ms,
                "source_dependency_ids": sorted(expected),
                "neo4j_dependency_ids": sorted(actual),
                "false_positives": sorted(actual - expected),
                "false_negatives": sorted(expected - actual),
                "source_dependency_match": actual == expected,
                "frozen_analysis_ids": sorted(frozen_ids) if frozen_ids is not None else None,
                "frozen_impact_coverage": frozen_coverage,
                "frozen_only_ids": sorted(frozen_ids - actual) if frozen_ids is not None else [],
                "dependency_only_ids": sorted(actual - frozen_ids) if frozen_ids is not None else [],
                "evidence_count": len(result.evidence),
                "evidence_errors": evidence_errors,
                "evidence_examples": [
                    item.model_dump(mode="json") for item in result.evidence[:2]
                ],
            })

        downstream_start = None
        for case in report_cases:
            if case["evidence_examples"]:
                downstream_start = case["evidence_examples"][0]["leg_id"]
                break
        downstream_records = []
        downstream_duration_ms = None
        if downstream_start is not None:
            downstream, downstream_duration_ms = service.find_downstream_leg_dependencies(
                downstream_start,
                max_depth=args.max_depth,
            )
            downstream_records = [item.model_dump(mode="json") for item in downstream]

    report = {
        "schema_version": "neo4j-phase-4/v1",
        "snapshot_id": repository.snapshot_id,
        "import_scope": repository.import_scope,
        "source_sqlite": str(args.source_sqlite),
        "dataset_counts": {
            "locations": len(dataset.locations),
            "routes": len(dataset.routes),
            "shipments": len(dataset.shipments),
            "ordered_legs": sum(len(item.route_legs) for item in dataset.shipments),
        },
        "query_limits": {
            "max_traversal_depth": args.max_depth,
            "result_limit": args.result_limit,
            "timeout_seconds": service.query_timeout_seconds,
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "neo4j_database": settings.neo4j_database,
        },
        "cases": report_cases,
        "downstream_next_leg": {
            "schema_supported": downstream_start is not None,
            "start_leg_id": downstream_start,
            "query_duration_ms": downstream_duration_ms,
            "records": downstream_records,
            "cross_shipment_dependencies_supported": False,
            "limitation": "The imported schema has NEXT_LEG within a shipment plan but no cross-shipment dependency relationship.",
        },
        "timing": {
            "query_count": len(query_times) + (1 if downstream_duration_ms is not None else 0),
            "min_ms": round(min(query_times), 3) if query_times else None,
            "max_ms": round(max(query_times), 3) if query_times else None,
            "average_ms": round(mean(query_times), 3) if query_times else None,
            "method": "Python wall-clock around managed Neo4j read transaction; includes local Bolt round trip and result materialization.",
        },
        "unsupported_comparisons": [
            "Scenario overlays and transient disruption state are not written to Neo4j; KG results are dependency evidence, not route-feasibility or classification replacements.",
            "Cross-shipment supplier, inventory, ownership, and business dependencies are absent from the approved schema and were not inferred.",
            "completed_leg_exclusion is not executed as a Neo4j scenario mutation because the canonical graph is immutable; completed-leg filtering is verified against imported statuses and a bounded NEXT_LEG query.",
        ],
    }
    report["pass"] = (
        all(case["source_dependency_match"] for case in report_cases)
        and all(case["evidence_errors"] == [] for case in report_cases)
        and all(case["frozen_impact_coverage"] for case in report_cases)
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "pass": report["pass"],
        "report": str(args.report_out),
        "cases": len(report_cases),
        "case_passes": sum(case["source_dependency_match"] and not case["evidence_errors"] for case in report_cases),
        "frozen_coverage": sum(case["frozen_impact_coverage"] for case in report_cases),
        "downstream_records": len(downstream_records),
        "average_ms": report["timing"]["average_ms"],
        "max_ms": report["timing"]["max_ms"],
    }, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
