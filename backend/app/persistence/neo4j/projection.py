"""NetworkX projection of the scoped Neo4j canonical snapshot."""

from __future__ import annotations

from collections import defaultdict

import networkx as nx

from ...graph import build_supply_chain_graph
from ...simulation_service import RuntimeSnapshot
from .repository import Neo4jReadRepository


class Neo4jProjectionError(ValueError):
    """Raised when the current DiGraph representation cannot be lossless."""


def _assert_di_graph_precondition(routes: list) -> None:
    pairs: dict[tuple[str, str], list[str]] = defaultdict(list)
    for route in routes:
        pairs[(route.source_location_id, route.destination_location_id)].append(
            route.route_id
        )
    parallel = {
        pair: sorted(route_ids)
        for pair, route_ids in pairs.items()
        if len(route_ids) > 1
    }
    if parallel:
        raise Neo4jProjectionError(
            "Active snapshot contains parallel routes that cannot be represented "
            f"losslessly by the existing DiGraph: {parallel}"
        )


def project_dataset(dataset) -> nx.DiGraph:
    """Use the canonical graph builder with canonical, non-scenario data."""

    ordered_locations = sorted(dataset.locations, key=lambda item: item.location_id)
    ordered_routes = sorted(dataset.routes, key=lambda item: item.route_id)
    _assert_di_graph_precondition(ordered_routes)
    return build_supply_chain_graph(
        ordered_locations,
        ordered_routes,
        portwatch_state={},
    )


def project_neo4j(repository: Neo4jReadRepository) -> nx.DiGraph:
    """Read once and project a fresh isolated graph for parity or a scenario."""

    return project_dataset(repository.load_runtime_dataset())


def runtime_snapshot_from_dataset(dataset) -> RuntimeSnapshot:
    """Build a scenario-compatible snapshot without external/transient state."""

    return RuntimeSnapshot(
        locations=sorted(dataset.locations, key=lambda item: item.location_id),
        routes=sorted(dataset.routes, key=lambda item: item.route_id),
        shipments=sorted(dataset.shipments, key=lambda item: item.shipment_id),
        portwatch_state={},
    )
