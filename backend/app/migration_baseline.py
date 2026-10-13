"""Read-only SQLite baseline export for the Neo4j migration Phase 0 gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import networkx as nx
from sqlalchemy import func, inspect, select, text

from .config import settings
from .disruption_policy import canonical_disruptions_from_request
from .domain import RuntimeDataset, Shipment, ShipmentRouteLeg
from .impact import classify_shipment_impacts, reroute_required_shipments
from .repository import (
    AgentDecisionRecord,
    DisruptionRecord,
    LegacyRunRecord,
    LocationRecord,
    RouteRecord,
    Session,
    ShipmentRecord,
    ShipmentRouteLegRecord,
    SimulationRunRecord,
    engine,
    load_runtime_dataset,
)
from .schemas import DisruptionRequest, DisruptionType
from .services import metrics, reroute
from .simulation_service import (
    RuntimeSnapshot,
    build_scenario_graphs,
    load_runtime_snapshot,
)


BASELINE_SCHEMA_VERSION = "neo4j-phase-0/v1"
BASELINE_SNAPSHOT_ID = "asia-runtime-seed-20260913"
BASELINE_CLOCK = datetime(2026, 1, 1, tzinfo=timezone.utc)
EXPECTED_COUNTS = {
    "locations": 91,
    "routes": 150,
    "shipments": 220,
    "ordered_legs": 1000,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _record_hashes(records: list[dict[str, Any]], key: str) -> dict[str, str]:
    return {
        str(record[key]): _sha256(record)
        for record in records
    }


def _location_record(location: Any) -> dict[str, Any]:
    return location.model_dump(mode="json")


def _route_record(route: Any) -> dict[str, Any]:
    record = route.model_dump(mode="json")
    record["weather_sample_points"] = sorted(
        record.get("weather_sample_points", []),
        key=lambda point: point["sequence"],
    )
    return record


def _leg_record(leg: ShipmentRouteLeg) -> dict[str, Any]:
    return leg.model_dump(mode="json")


def _shipment_record(shipment: Shipment) -> dict[str, Any]:
    record = shipment.model_dump(mode="json", exclude={"route_legs"})
    record["route_legs"] = [
        _leg_record(leg)
        for leg in shipment.ordered_route_legs
    ]
    return record


def _dataset_records(dataset: RuntimeDataset) -> dict[str, list[dict[str, Any]]]:
    locations = sorted(
        (_location_record(location) for location in dataset.locations),
        key=lambda record: record["location_id"],
    )
    routes = sorted(
        (_route_record(route) for route in dataset.routes),
        key=lambda record: record["route_id"],
    )
    shipments = sorted(
        (_shipment_record(shipment) for shipment in dataset.shipments),
        key=lambda record: record["shipment_id"],
    )
    legs = sorted(
        (
            _leg_record(leg)
            for shipment in dataset.shipments
            for leg in shipment.ordered_route_legs
        ),
        key=lambda record: (record["shipment_id"], record["sequence_no"]),
    )
    return {
        "locations": locations,
        "routes": routes,
        "shipments": shipments,
        "ordered_legs": legs,
    }


def _table_count(model: Any) -> int:
    with Session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _database_classification(dataset: RuntimeDataset) -> dict[str, Any]:
    table_models = {
        "locations": LocationRecord,
        "routes": RouteRecord,
        "shipments": ShipmentRecord,
        "shipment_route_legs": ShipmentRouteLegRecord,
        "disruptions": DisruptionRecord,
        "simulation_runs": SimulationRunRecord,
        "agent_decisions": AgentDecisionRecord,
    }
    table_counts = {
        name: _table_count(model)
        for name, model in table_models.items()
    }
    active_location_ids = {location.location_id for location in dataset.locations}
    active_route_ids = {route.route_id for route in dataset.routes}
    active_shipment_ids = {shipment.shipment_id for shipment in dataset.shipments}

    with Session() as session:
        location_ids = list(session.scalars(select(LocationRecord.id)))
        route_ids = list(session.scalars(select(RouteRecord.id)))
        shipment_ids = list(session.scalars(select(ShipmentRecord.id)))
        leg_rows = list(session.scalars(select(ShipmentRouteLegRecord)))

    active_leg_count = sum(
        1 for row in leg_rows if row.shipment_id in active_shipment_ids
    )
    compatibility = {
        "locations": {
            "active": len(active_location_ids),
            "compatibility_or_excluded": len(
                [item for item in location_ids if item not in active_location_ids]
            ),
        },
        "routes": {
            "active": len(active_route_ids),
            "compatibility_or_excluded": len(
                [item for item in route_ids if item not in active_route_ids]
            ),
        },
        "shipments": {
            "active": len(active_shipment_ids),
            "compatibility_or_excluded": len(
                [item for item in shipment_ids if item not in active_shipment_ids]
            ),
        },
        "shipment_route_legs": {
            "active": active_leg_count,
            "compatibility_or_excluded": len(leg_rows) - active_leg_count,
        },
    }

    inspector = inspect(engine)
    history_tables = {
        "disruptions": table_counts["disruptions"],
        "simulation_runs": table_counts["simulation_runs"],
        "agent_decisions": table_counts["agent_decisions"],
    }
    if inspector.has_table("runs"):
        history_tables["runs_legacy"] = _table_count(LegacyRunRecord)

    return {
        "table_counts": table_counts,
        "compatibility_or_excluded_master_rows": compatibility,
        "historical_audit_rows": history_tables,
        "legacy_runs_table_present": inspector.has_table("runs"),
    }


def _database_metadata() -> dict[str, Any]:
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())
    table_columns = {
        table: [column["name"] for column in inspector.get_columns(table)]
        for table in table_names
    }
    metadata: dict[str, Any] = {
        "backend": engine.url.drivername,
        "database_filename": Path(engine.url.database or "").name,
        "tables": table_names,
        "table_columns": table_columns,
    }
    if engine.url.drivername.startswith("sqlite"):
        with engine.connect() as connection:
            metadata["sqlite_user_version"] = connection.execute(
                text("PRAGMA user_version")
            ).scalar()
            metadata["sqlite_journal_mode"] = connection.execute(
                text("PRAGMA journal_mode")
            ).scalar()
    return metadata


def _validate_dataset(dataset: RuntimeDataset) -> dict[str, Any]:
    records = _dataset_records(dataset)
    location_ids = {record["location_id"] for record in records["locations"]}
    route_ids = {record["route_id"] for record in records["routes"]}
    shipment_ids = {record["shipment_id"] for record in records["shipments"]}
    route_by_id = {record["route_id"]: record for record in records["routes"]}
    location_by_id = {record["location_id"]: record for record in records["locations"]}

    route_pair_counts = Counter(
        (record["source_location_id"], record["destination_location_id"])
        for record in records["routes"]
    )
    parallel_route_pairs = [
        {
            "source_location_id": source,
            "destination_location_id": destination,
            "route_ids": sorted(
                record["route_id"]
                for record in records["routes"]
                if (
                    record["source_location_id"],
                    record["destination_location_id"],
                )
                == (source, destination)
            ),
        }
        for (source, destination), count in sorted(route_pair_counts.items())
        if count > 1
    ]

    reference_errors: list[dict[str, Any]] = []
    for route in records["routes"]:
        for field in ("source_location_id", "destination_location_id"):
            if route[field] not in location_ids:
                reference_errors.append(
                    {"entity": route["route_id"], "field": field, "value": route[field]}
                )
    for shipment in records["shipments"]:
        for field in ("origin_location_id", "destination_location_id", "current_location_id"):
            if shipment[field] not in location_ids:
                reference_errors.append(
                    {"entity": shipment["shipment_id"], "field": field, "value": shipment[field]}
                )
    sequence_errors: list[dict[str, Any]] = []
    leg_reference_errors: list[dict[str, Any]] = []
    for shipment in records["shipments"]:
        legs = shipment["route_legs"]
        expected_sequences = list(range(1, len(legs) + 1))
        actual_sequences = [leg["sequence_no"] for leg in legs]
        if actual_sequences != expected_sequences:
            sequence_errors.append(
                {
                    "shipment_id": shipment["shipment_id"],
                    "expected": expected_sequences,
                    "actual": actual_sequences,
                }
            )
        for leg in legs:
            route = route_by_id.get(leg["route_id"])
            if route is None:
                leg_reference_errors.append(
                    {"shipment_id": shipment["shipment_id"], "route_id": leg["route_id"]}
                )
                continue
            expected = {
                "source_location_id": route["source_location_id"],
                "destination_location_id": route["destination_location_id"],
            }
            actual = {
                "source_location_id": leg["source_location_id"],
                "destination_location_id": leg["destination_location_id"],
            }
            if expected != actual:
                leg_reference_errors.append(
                    {
                        "shipment_id": shipment["shipment_id"],
                        "sequence_no": leg["sequence_no"],
                        "expected": expected,
                        "actual": actual,
                    }
                )
            if leg["source_location_id"] not in location_by_id:
                leg_reference_errors.append(
                    {
                        "shipment_id": shipment["shipment_id"],
                        "sequence_no": leg["sequence_no"],
                        "field": "source_location_id",
                    }
                )
            if leg["destination_location_id"] not in location_by_id:
                leg_reference_errors.append(
                    {
                        "shipment_id": shipment["shipment_id"],
                        "sequence_no": leg["sequence_no"],
                        "field": "destination_location_id",
                    }
                )

    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(location_ids))
    graph.add_edges_from(
        (
            route["source_location_id"],
            route["destination_location_id"],
        )
        for route in records["routes"]
    )
    checks = {
        "expected_counts_match": {
            key: len(records[key]) == value
            for key, value in EXPECTED_COUNTS.items()
        },
        "orphan_references": reference_errors + leg_reference_errors,
        "ordered_leg_sequence_errors": sequence_errors,
        "parallel_route_pairs": parallel_route_pairs,
        "weakly_connected_components": nx.number_weakly_connected_components(graph),
        "all_shipments_have_route_legs": all(
            shipment["route_legs"] for shipment in records["shipments"]
        ),
        "all_active_ids_are_sorted": (
            [record["location_id"] for record in records["locations"]]
            == sorted(record["location_id"] for record in records["locations"])
        ),
    }
    checks["pass"] = (
        all(checks["expected_counts_match"].values())
        and not checks["orphan_references"]
        and not checks["ordered_leg_sequence_errors"]
        and not checks["parallel_route_pairs"]
        and checks["weakly_connected_components"] == 1
        and checks["all_shipments_have_route_legs"]
        and checks["all_active_ids_are_sorted"]
    )
    return checks


def _request(
    disruption_type: DisruptionType,
    *,
    locations: list[str] | None = None,
    routes: list[str] | None = None,
    severity: str = "HIGH",
    duration_hours: int = 72,
) -> DisruptionRequest:
    return DisruptionRequest(
        disruption_type=disruption_type,
        affected_location_ids=locations or [],
        affected_route_ids=routes or [],
        duration_hours=duration_hours,
        severity=severity,
    )


def _path_result_record(path: Any) -> dict[str, Any] | None:
    return path.model_dump(mode="json") if path is not None else None


def _run_scenario(
    name: str,
    request: DisruptionRequest,
    snapshot: RuntimeSnapshot,
    *,
    shipments: list[Shipment] | None = None,
    selection_note: str | None = None,
) -> dict[str, Any]:
    events = canonical_disruptions_from_request(
        request,
        disruption_id=f"BASELINE_{name.upper()}",
        start_time=BASELINE_CLOCK,
    )
    state, graph, baseline_graph = build_scenario_graphs(snapshot, events)
    scenario_shipments = shipments or snapshot.shipments
    impacts = classify_shipment_impacts(scenario_shipments, state)
    required, _ = reroute_required_shipments(scenario_shipments, state)
    recommendations = reroute(
        graph,
        required,
        baseline_graph,
        request.duration_hours,
    )
    impact_counts = Counter(item.classification.value for item in impacts)
    impact_records = [
        item.model_dump(mode="json")
        for item in impacts
        if item.classification.value != "UNAFFECTED"
    ]
    recommendation_records = []
    for recommendation in recommendations:
        recommendation_records.append(
            {
                "shipment_id": recommendation.shipment_id,
                "status": recommendation.status,
                "original_route": _path_result_record(recommendation.original_route),
                "candidate_routes": [
                    _path_result_record(candidate)
                    for candidate in recommendation.candidate_routes
                ],
                "selected_route": _path_result_record(
                    recommendation.selected_route
                ),
                "delay_saved_hours": recommendation.delay_saved_hours,
                "additional_cost": recommendation.additional_cost,
            }
        )
    return {
        "name": name,
        "request": request.model_dump(mode="json"),
        "fixed_clock": BASELINE_CLOCK.isoformat(),
        "selection_note": selection_note,
        "impact_counts": dict(sorted(impact_counts.items())),
        "affected_shipment_ids": sorted(
            item["shipment_id"] for item in impact_records
        ),
        "impact_records": sorted(impact_records, key=lambda item: item["shipment_id"]),
        "reroute_required_ids": [shipment.shipment_id for shipment in required],
        "recommendation_order": [
            recommendation.shipment_id for recommendation in recommendations
        ],
        "recommendations": recommendation_records,
        "metrics": metrics(recommendations),
        "state": {
            "unavailable_location_ids": sorted(
                location_id
                for location_id, node in state.nodes.items()
                if not node.available
            ),
            "unavailable_route_ids": sorted(
                edge.route_id for edge in state.edges.values() if not edge.available
            ),
            "effective_capacity_overrides": {
                edge.route_id: edge.effective_capacity
                for edge in state.edges.values()
                if edge.effective_capacity != edge.base_capacity
            },
        },
    }


def _capacity_target(dataset: RuntimeDataset) -> tuple[str, str]:
    routes = {route.route_id: route for route in dataset.routes}
    for shipment in sorted(dataset.shipments, key=lambda item: item.shipment_id):
        for leg in shipment.remaining_route_legs():
            route = routes[leg.route_id]
            if route.current_load + shipment.load_units > route.max_capacity * 0.25:
                return route.route_id, shipment.shipment_id
    first_shipment = sorted(dataset.shipments, key=lambda item: item.shipment_id)[0]
    return first_shipment.ordered_route_legs[0].route_id, first_shipment.shipment_id


def _completed_leg_probe(
    snapshot: RuntimeSnapshot,
) -> tuple[RuntimeSnapshot, DisruptionRequest, str]:
    for shipment in sorted(snapshot.shipments, key=lambda item: item.shipment_id):
        legs = shipment.ordered_route_legs
        if len(legs) < 2:
            continue
        completed = legs[0]
        if completed.destination_location_id == shipment.origin_location_id:
            continue
        updated_legs = [
            completed.model_copy(update={"status": "COMPLETED"}),
            *[
                leg.model_copy(
                    update={"status": "CURRENT" if index == 1 else leg.status}
                )
                for index, leg in enumerate(legs[1:], start=1)
            ],
        ]
        progressed = shipment.model_copy(
            update={
                "current_location_id": completed.destination_location_id,
                "route_legs": updated_legs,
            }
        )
        probe_snapshot = RuntimeSnapshot(
            locations=snapshot.locations,
            routes=snapshot.routes,
            shipments=[
                progressed if item.shipment_id == shipment.shipment_id else item
                for item in snapshot.shipments
            ],
            portwatch_state=snapshot.portwatch_state,
        )
        request = _request(
            DisruptionType.PORT_CLOSURE,
            locations=[completed.destination_location_id],
        )
        return (
            probe_snapshot,
            request,
            f"Shipment {shipment.shipment_id} was advanced to {completed.destination_location_id}; "
            f"its first leg {completed.route_id} was marked COMPLETED before applying a closure.",
        )
    raise RuntimeError("No multi-leg shipment was available for the completed-leg probe")


def capture_scenarios(dataset: RuntimeDataset) -> dict[str, Any]:
    snapshot = load_runtime_snapshot()
    scenarios: dict[str, Any] = {}
    scenarios["singapore_closure"] = _run_scenario(
        "singapore_closure",
        _request(DisruptionType.PORT_CLOSURE, locations=["LOC_WPI_50000"]),
        snapshot,
    )
    scenarios["port_klang_closure"] = _run_scenario(
        "port_klang_closure",
        _request(DisruptionType.PORT_CLOSURE, locations=["LOC_WPI_49930"]),
        snapshot,
    )
    scenarios["port_klang_congestion"] = _run_scenario(
        "port_klang_congestion",
        _request(
            DisruptionType.CONGESTION,
            locations=["LOC_WPI_49930"],
            severity="MEDIUM",
        ),
        snapshot,
    )

    capacity_route_id, capacity_shipment_id = _capacity_target(dataset)
    scenarios["reduced_capacity"] = _run_scenario(
        "reduced_capacity",
        _request(
            DisruptionType.CAPACITY_REDUCTION,
            routes=[capacity_route_id],
            severity="CRITICAL",
        ),
        snapshot,
        selection_note=(
            f"Selected the first sorted remaining route where the critical 75% "
            f"capacity reduction challenges a shipment: {capacity_route_id} "
            f"for {capacity_shipment_id}."
        ),
    )

    no_route_shipment = sorted(dataset.shipments, key=lambda item: item.shipment_id)[0]
    no_route_request = _request(
        DisruptionType.PORT_CLOSURE,
        locations=[no_route_shipment.destination_location_id],
    )
    scenarios["no_feasible_route"] = _run_scenario(
        "no_feasible_route",
        no_route_request,
        snapshot,
        selection_note=(
            f"Closed the destination {no_route_shipment.destination_location_id} "
            f"of the first sorted shipment {no_route_shipment.shipment_id}; all "
            "incident paths are unavailable."
        ),
    )

    completed_snapshot, completed_request, completed_note = _completed_leg_probe(snapshot)
    scenarios["completed_leg_exclusion"] = _run_scenario(
        "completed_leg_exclusion",
        completed_request,
        completed_snapshot,
        shipments=completed_snapshot.shipments,
        selection_note=completed_note,
    )

    contention = scenarios["singapore_closure"]
    scenarios["multi_shipment_contention"] = {
        **contention,
        "name": "multi_shipment_contention",
        "selection_note": (
            "Reused the Singapore closure batch to capture deterministic priority "
            "ordering, candidate selection, and transient capacity reservations "
            "across all reroute-required shipments."
        ),
        "batch_size": len(contention["reroute_required_ids"]),
    }

    repeated_first = _run_scenario(
        "repeated_request",
        _request(DisruptionType.PORT_CLOSURE, locations=["LOC_WPI_50000"]),
        snapshot,
    )
    repeated_second = _run_scenario(
        "repeated_request",
        _request(DisruptionType.PORT_CLOSURE, locations=["LOC_WPI_50000"]),
        snapshot,
    )
    comparable_keys = (
        "request",
        "impact_counts",
        "affected_shipment_ids",
        "impact_records",
        "reroute_required_ids",
        "recommendation_order",
        "recommendations",
        "metrics",
        "state",
    )
    repeated_equal = all(
        repeated_first[key] == repeated_second[key]
        for key in comparable_keys
    )
    scenarios["identical_repeated_requests"] = {
        "name": "identical_repeated_requests",
        "fixed_clock": BASELINE_CLOCK.isoformat(),
        "request": repeated_first["request"],
        "equal_after_normalization": repeated_equal,
        "compared_keys": list(comparable_keys),
        "first": repeated_first,
        "second": repeated_second,
    }
    return scenarios


def build_manifest() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    dataset = load_runtime_dataset()
    records = _dataset_records(dataset)
    id_values = {
        "locations": [record["location_id"] for record in records["locations"]],
        "routes": [record["route_id"] for record in records["routes"]],
        "shipments": [record["shipment_id"] for record in records["shipments"]],
        "ordered_legs": [
            f"{record['shipment_id']}:{record['sequence_no']}"
            for record in records["ordered_legs"]
        ],
    }
    hashes = {
        entity: {
            "id_hash": _sha256(id_values[entity]),
            "content_hash": _sha256(records[entity]),
            "record_hashes": _record_hashes(records[entity], key),
        }
        for entity, key in (
            ("locations", "location_id"),
            ("routes", "route_id"),
            ("shipments", "shipment_id"),
            ("ordered_legs", "shipment_id"),
        )
    }
    # Leg record hashes need a composite key because each shipment has multiple legs.
    hashes["ordered_legs"]["record_hashes"] = {
        f"{record['shipment_id']}:{record['sequence_no']}": _sha256(record)
        for record in records["ordered_legs"]
    }
    checks = _validate_dataset(dataset)
    manifest = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "snapshot_id": BASELINE_SNAPSHOT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_clock": BASELINE_CLOCK.isoformat(),
        "generator_seed": 20260913,
        "database": _database_metadata(),
        "counts": {key: len(value) for key, value in records.items()},
        "expected_counts": EXPECTED_COUNTS,
        "hashes": hashes,
        "database_classification": _database_classification(dataset),
        "validation": checks,
        "runtime_contract": {
            "active_loader": "backend.app.repository.load_runtime_dataset",
            "active_location_filter": "LOC_WPI_* or ASIA_*",
            "active_route_filter": "ASIA_R_*",
            "active_shipment_filter": "ASIA_S_*",
            "graph_type": "networkx.DiGraph",
            "scenario_state": "transient NetworkState and copied NetworkX graph",
            "llm_used": False,
        },
        "environment": {
            "python": platform.python_version(),
            "packages": {
                package: _installed_version(package)
                for package in ("networkx", "pydantic", "sqlalchemy", "pytest")
            },
        },
    }
    snapshot = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "snapshot_id": BASELINE_SNAPSHOT_ID,
        "records": records,
    }
    scenarios = capture_scenarios(dataset)
    return manifest, snapshot, scenarios


def _installed_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "UNAVAILABLE"


def validate_artifacts(output_dir: Path) -> dict[str, Any]:
    manifest = json.loads((output_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    snapshot = json.loads((output_dir / "ACTIVE_SNAPSHOT.json").read_text(encoding="utf-8"))
    scenarios = json.loads((output_dir / "SCENARIOS.json").read_text(encoding="utf-8"))
    records = snapshot["records"]
    checks = {
        "snapshot_schema_matches": snapshot["schema_version"] == BASELINE_SCHEMA_VERSION,
        "manifest_schema_matches": manifest["schema_version"] == BASELINE_SCHEMA_VERSION,
        "counts_match": manifest["counts"] == {
            key: len(value) for key, value in records.items()
        },
        "manifest_validation_passed": manifest["validation"]["pass"],
        "scenario_count": len(scenarios),
        "repeated_requests_equal": scenarios[
            "identical_repeated_requests"
        ]["equal_after_normalization"],
    }
    for entity, key in (
        ("locations", "location_id"),
        ("routes", "route_id"),
        ("shipments", "shipment_id"),
        ("ordered_legs", "shipment_id"),
    ):
        records_for_entity = records[entity]
        expected_hash = _sha256(records_for_entity)
        checks[f"{entity}_content_hash_matches"] = (
            manifest["hashes"][entity]["content_hash"] == expected_hash
        )
        checks[f"{entity}_ids_sorted"] = [
            record[key] for record in records_for_entity
        ] == sorted(record[key] for record in records_for_entity)
    checks["pass"] = all(
        value is True
        for key, value in checks.items()
        if key != "scenario_count"
    ) and checks["scenario_count"] == 8
    return checks


def write_artifacts(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest, snapshot, scenarios = build_manifest()
    for name, payload in (
        ("MANIFEST.json", manifest),
        ("ACTIVE_SNAPSHOT.json", snapshot),
        ("SCENARIOS.json", scenarios),
    ):
        (output_dir / name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return validate_artifacts(output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/migration/baseline"),
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate existing Phase 0 artifacts without reading SQLite.",
    )
    args = parser.parse_args()
    if args.validate:
        result = validate_artifacts(args.output_dir)
    else:
        result = write_artifacts(args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
