"""Deterministic SQLite versus Neo4j parity evidence for Phase 3."""

from __future__ import annotations

import json
import hashlib
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from ...domain import RuntimeDataset
from ...migration_baseline import (
    BASELINE_CLOCK,
    _capacity_target,
    _completed_leg_probe,
    _request,
    _run_scenario,
)
from ...schemas import DisruptionType
from ...repository import load_runtime_dataset
from ...simulation_service import RuntimeSnapshot
from .importer import (
    EXPECTED_RELATIONSHIP_COUNTS,
    IMPORT_SCOPE,
    SOURCE_SNAPSHOT_ID,
    load_source_dataset,
)
from .projection import project_dataset, runtime_snapshot_from_dataset
from .repository import Neo4jReadRepository


PARITY_SCHEMA_VERSION = "neo4j-phase-3/v1"
BASELINE_REPORT = Path("docs/migration/baseline/SCENARIOS.json")


def _json(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, datetime):
        current = value
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_json(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _model_records(dataset: RuntimeDataset) -> dict[str, list[dict[str, Any]]]:
    locations = sorted(
        (location.model_dump(mode="python") for location in dataset.locations),
        key=lambda item: item["location_id"],
    )
    routes = sorted(
        (route.model_dump(mode="python") for route in dataset.routes),
        key=lambda item: item["route_id"],
    )
    shipments = sorted(
        (
            shipment.model_dump(mode="python")
            for shipment in dataset.shipments
        ),
        key=lambda item: item["shipment_id"],
    )
    legs = sorted(
        (
            {
                "leg_id": f"{shipment.shipment_id}:v1:{leg.sequence_no}",
                "plan_id": f"{shipment.shipment_id}:v1",
                **leg.model_dump(mode="python"),
            }
            for shipment in dataset.shipments
            for leg in shipment.ordered_route_legs
        ),
        key=lambda item: (item["shipment_id"], item["sequence_no"]),
    )
    return {
        "locations": locations,
        "routes": routes,
        "shipments": shipments,
        "ordered_legs": legs,
    }


def _plan_records(dataset: RuntimeDataset) -> list[dict[str, Any]]:
    return [
        {
            "plan_id": f"{shipment.shipment_id}:v1",
            "shipment_id": shipment.shipment_id,
            "plan_version": 1,
            "active": True,
        }
        for shipment in sorted(dataset.shipments, key=lambda item: item.shipment_id)
    ]


def _compare_records(
    source: list[dict[str, Any]],
    target: list[dict[str, Any]],
    key: str,
) -> dict[str, Any]:
    source_by_id = {str(item[key]): item for item in source}
    target_by_id = {str(item[key]): item for item in target}
    mismatches = []
    for item_id in sorted(set(source_by_id) | set(target_by_id)):
        if item_id not in source_by_id:
            mismatches.append({"id": item_id, "kind": "unexpected_target"})
        elif item_id not in target_by_id:
            mismatches.append({"id": item_id, "kind": "missing_target"})
        elif _canonical(source_by_id[item_id]) != _canonical(target_by_id[item_id]):
            mismatches.append(
                {
                    "id": item_id,
                    "kind": "attribute_mismatch",
                    "source": _json(source_by_id[item_id]),
                    "target": _json(target_by_id[item_id]),
                }
            )
    return {
        "source_count": len(source),
        "target_count": len(target),
        "source_ids": sorted(source_by_id),
        "target_ids": sorted(target_by_id),
        "id_sets_match": set(source_by_id) == set(target_by_id),
        "mismatches": mismatches,
        "pass": not mismatches and len(source) == len(target),
    }


def _graph_records(graph: nx.DiGraph) -> dict[str, Any]:
    node_records = {
        node_id: {
            "status": _json(data.get("status")),
            "available": data.get("available"),
        }
        for node_id, data in sorted(graph.nodes(data=True), key=lambda item: item[0])
    }
    edge_records = {}
    for source, destination, data in sorted(graph.edges(data=True)):
        edge_records[f"{source}->{destination}"] = {
            key: _json(data.get(key))
            for key in (
                "route_id",
                "duration",
                "cost",
                "risk",
                "capacity",
                "current_load",
                "base_duration",
                "base_cost",
                "base_risk",
                "base_capacity",
                "base_current_load",
                "effective_duration",
                "effective_cost",
                "effective_risk",
                "effective_capacity",
                "weight",
                "available",
                "status",
            )
        }
    return {"nodes": node_records, "edges": edge_records}


def _scenario_set(dataset: RuntimeDataset) -> dict[str, Any]:
    snapshot = runtime_snapshot_from_dataset(dataset)
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
        _request(DisruptionType.CONGESTION, locations=["LOC_WPI_49930"], severity="MEDIUM"),
        snapshot,
    )
    capacity_route_id, capacity_shipment_id = _capacity_target(dataset)
    scenarios["reduced_capacity"] = _run_scenario(
        "reduced_capacity",
        _request(DisruptionType.CAPACITY_REDUCTION, routes=[capacity_route_id], severity="CRITICAL"),
        snapshot,
        selection_note=(
            "Selected the first sorted remaining route where the critical 75% "
            f"capacity reduction challenges a shipment: {capacity_route_id} for {capacity_shipment_id}."
        ),
    )
    no_route_shipment = sorted(dataset.shipments, key=lambda item: item.shipment_id)[0]
    scenarios["no_feasible_route"] = _run_scenario(
        "no_feasible_route",
        _request(DisruptionType.PORT_CLOSURE, locations=[no_route_shipment.destination_location_id]),
        snapshot,
        selection_note=(
            f"Closed the destination {no_route_shipment.destination_location_id} of the first sorted "
            f"shipment {no_route_shipment.shipment_id}; all incident paths are unavailable."
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
            "Reused the Singapore closure batch to capture deterministic priority ordering, "
            "candidate selection, and transient capacity reservations across all reroute-required shipments."
        ),
        "batch_size": len(contention["reroute_required_ids"]),
    }
    first = _run_scenario(
        "repeated_request",
        _request(DisruptionType.PORT_CLOSURE, locations=["LOC_WPI_50000"]),
        snapshot,
    )
    second = _run_scenario(
        "repeated_request",
        _request(DisruptionType.PORT_CLOSURE, locations=["LOC_WPI_50000"]),
        snapshot,
    )
    comparable_keys = (
        "request", "impact_counts", "affected_shipment_ids", "impact_records",
        "reroute_required_ids", "recommendation_order", "recommendations", "metrics", "state",
    )
    scenarios["identical_repeated_requests"] = {
        "name": "identical_repeated_requests",
        "fixed_clock": BASELINE_CLOCK.isoformat(),
        "request": first["request"],
        "equal_after_normalization": all(first[key] == second[key] for key in comparable_keys),
        "compared_keys": list(comparable_keys),
        "first": first,
        "second": second,
    }
    return scenarios


def _compare_scenarios(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    results = {}
    for name in sorted(source):
        results[name] = {
            "source_vs_neo4j": _canonical(source[name]) == _canonical(target[name]),
            "source_hash": _digest(source[name]),
            "neo4j_hash": _digest(target[name]),
        }
        results[name]["pass"] = results[name]["source_vs_neo4j"]
    return results


def build_parity_report(
    source: RuntimeDataset,
    target: RuntimeDataset,
    repository: Neo4jReadRepository,
    *,
    baseline_path: Path = BASELINE_REPORT,
) -> dict[str, Any]:
    source_records = _model_records(source)
    target_records = _model_records(target)
    entities = {
        entity: _compare_records(
            source_records[entity], target_records[entity],
            {"locations": "location_id", "routes": "route_id", "shipments": "shipment_id", "ordered_legs": "leg_id"}[entity],
        )
        for entity in source_records
    }
    plans = _compare_records(_plan_records(source), _plan_records(target), "plan_id")
    source_graph = project_dataset(source)
    target_graph = project_dataset(target)
    source_graph_records = _graph_records(source_graph)
    target_graph_records = _graph_records(target_graph)
    graph_pass = _canonical(source_graph_records) == _canonical(target_graph_records)
    source_scenarios = _scenario_set(source)
    target_scenarios = _scenario_set(target)
    scenario_parity = _compare_scenarios(source_scenarios, target_scenarios)
    baseline_comparison: dict[str, Any] = {"available": baseline_path.exists(), "mismatches": []}
    if baseline_path.exists():
        frozen = json.loads(baseline_path.read_text(encoding="utf-8"))
        frozen_scenarios = frozen.get("scenarios", frozen)
        for name, result in source_scenarios.items():
            if name not in frozen_scenarios:
                baseline_comparison["mismatches"].append({"scenario": name, "kind": "missing_baseline"})
            elif _canonical(result) != _canonical(frozen_scenarios[name]):
                baseline_comparison["mismatches"].append({"scenario": name, "kind": "baseline_output_mismatch"})
    baseline_comparison["pass"] = not baseline_comparison["mismatches"]
    target_relationship_counts = repository.get_relationship_counts()
    relationships_match = target_relationship_counts == EXPECTED_RELATIONSHIP_COUNTS
    report = {
        "schema_version": PARITY_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": repository.snapshot_id,
        "import_scope": repository.import_scope,
        "source_of_truth": "sqlite",
        "source_snapshot": SOURCE_SNAPSHOT_ID,
        "entities": entities,
        "route_plans": plans,
        "relationships": {
            "target_counts": target_relationship_counts,
            "expected_counts": EXPECTED_RELATIONSHIP_COUNTS,
            "pass": relationships_match,
        },
        "graph": {
            "source_nodes": source_graph.number_of_nodes(),
            "source_edges": source_graph.number_of_edges(),
            "target_nodes": target_graph.number_of_nodes(),
            "target_edges": target_graph.number_of_edges(),
            "topology_and_routing_attributes_match": graph_pass,
            "source": source_graph_records,
            "target": target_graph_records,
        },
        "scenarios": scenario_parity,
        "baseline_comparison": baseline_comparison,
        "excluded_fields": {
            "scenario_duration_hours": "Transient NetworkX disruption state; never imported as canonical Route data.",
            "neo4j_element_ids": "Storage-generated identifiers are not logical identity.",
            "generated_at": "Report metadata only; excluded from parity comparisons.",
        },
        "unsupported_comparisons": [
            "External PortWatch enrichment and transient provider state are excluded; both parity snapshots use empty portwatch_state.",
            "Neo4j write behavior and runtime backend cutover are intentionally not tested in Phase 3.",
        ],
    }
    report["pass"] = (
        all(item["pass"] for item in entities.values())
        and plans["pass"]
        and relationships_match
        and graph_pass
        and all(item["pass"] for item in scenario_parity.values())
        and baseline_comparison["pass"]
    )
    return report


def run_parity(
    repository: Neo4jReadRepository,
    source_sqlite: Path,
    report_path: Path,
) -> dict[str, Any]:
    source = load_source_dataset(source_sqlite)
    target = repository.load_runtime_dataset()
    report = build_parity_report(source, target, repository)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
