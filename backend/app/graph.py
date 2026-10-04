"""Transient NetworkX graph construction and scenario-state operations."""

from __future__ import annotations

from collections.abc import Mapping

import networkx as nx

from .domain import Location, Route, Status
from .schemas import DisruptionRequest
from .network_state import (
    NetworkState,
    NetworkStateEngine,
    apply_network_state_to_graph,
)


def build_supply_chain_graph(
    locations: list[Location],
    routes: list[Route],
    portwatch_state: Mapping[str, Mapping[str, object]] | None = None,
    network_state: NetworkState | None = None,
) -> nx.DiGraph:
    """Build an isolated transient graph scenario.

    NetworkX stores edge and node attributes by reference. The routing layer
    changes route status, duration, and load while evaluating a disruption, so
    the graph owns deep copies of the mutable domain models it contains. The
    caller's master data and every graph built from it remain unchanged.
    """

    graph = nx.DiGraph()
    for location in locations:
        state = dict((portwatch_state or {}).get(location.id, {}))
        graph.add_node(
            location.id,
            location=location.model_copy(deep=True),
            status=location.status,
            available=location.status == Status.ACTIVE,
            disruption_ids=[],
            portwatch_state=state or None,
            canonical_location_id=state.get("canonical_location_id")
            or location.canonical_location_id,
            portwatch_source=state.get("source") or location.source
            if location.source == "PORTWATCH"
            else state.get("source"),
            portwatch_source_port_id=state.get("source_port_id")
            or location.portwatch_source_port_id,
            latest_activity_score=state.get("activity_score")
            or location.activity_score,
            activity_anomaly_score=state.get("activity_anomaly_score")
            if state.get("activity_anomaly_score") is not None
            else location.activity_anomaly_score,
            operational_status=state.get("operational_status")
            or location.operational_status,
            latest_portwatch_update=state.get("latest_observation_date")
            or location.latest_observation_date,
        )
    for route in routes:
        isolated_route = route.model_copy(deep=True)
        graph.add_edge(
            route.source_location_id,
            route.destination_location_id,
            route=isolated_route,
            route_id=isolated_route.route_id,
            corridor_ids=list(isolated_route.corridor_ids),
            weather_sample_points=[
                point.model_copy(deep=True)
                for point in isolated_route.weather_sample_points
            ],
            duration=isolated_route.base_duration_hours,
            cost=isolated_route.base_cost,
            risk=isolated_route.risk_score,
            capacity=isolated_route.max_capacity,
            current_load=isolated_route.current_load,
            base_duration=isolated_route.base_duration_hours,
            base_cost=isolated_route.base_cost,
            base_risk=isolated_route.risk_score,
            base_capacity=isolated_route.max_capacity,
            base_current_load=isolated_route.current_load,
            effective_duration=isolated_route.base_duration_hours,
            effective_cost=isolated_route.base_cost,
            effective_risk=isolated_route.risk_score,
            effective_capacity=isolated_route.max_capacity,
            available=isolated_route.status == Status.ACTIVE,
            disruption_ids=[],
            status=isolated_route.status,
            weight=isolated_route.base_duration_hours,
        )
    state = network_state or NetworkStateEngine().build(locations, routes)
    apply_network_state_to_graph(graph, state)
    return graph


def apply_disruption(graph: nx.DiGraph, disruption: DisruptionRequest) -> None:
    """Compatibility facade for the canonical network-state engine."""

    locations = [data["location"] for _, data in graph.nodes(data=True)]
    routes = [data["route"] for _, _, data in graph.edges(data=True)]
    state = NetworkStateEngine().build(locations, routes, [disruption])
    apply_network_state_to_graph(graph, state)
