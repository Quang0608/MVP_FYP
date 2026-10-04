"""Transient operational network state and disruption policy application."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from .disruption_policy import (
    DisruptionPolicyConfig,
    canonical_disruptions_from_external,
    canonical_disruptions_from_request,
)
from .domain import Disruption as CanonicalDisruption
from .domain import Location, Route, Status
from .schemas import DisruptionRequest, DisruptionType


@dataclass
class NetworkNodeState:
    location_id: str
    base_status: Status
    available: bool = True
    disruption_ids: list[str] = field(default_factory=list)

    @property
    def effective_status(self) -> Status:
        if not self.available:
            return Status.DISRUPTED
        return self.base_status


@dataclass
class NetworkEdgeState:
    route_id: str
    source_location_id: str
    destination_location_id: str
    base_duration: float
    base_cost: float
    base_risk: float
    base_capacity: float
    base_current_load: float
    available: bool = True
    effective_duration: float = 0
    effective_cost: float = 0
    effective_risk: float = 0
    effective_capacity: float = 0
    current_load: float = 0
    disruption_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_route(cls, route: Route) -> "NetworkEdgeState":
        return cls(
            route_id=route.route_id,
            source_location_id=route.source_location_id,
            destination_location_id=route.destination_location_id,
            base_duration=route.base_duration_hours,
            base_cost=route.base_cost,
            base_risk=route.risk_score,
            base_capacity=route.max_capacity,
            base_current_load=route.current_load,
            available=route.status == Status.ACTIVE,
            effective_duration=route.base_duration_hours,
            effective_cost=route.base_cost,
            effective_risk=route.risk_score,
            effective_capacity=route.max_capacity,
            current_load=route.current_load,
        )


@dataclass
class NetworkState:
    """Scenario-only state overlay; it owns no canonical domain objects."""

    nodes: dict[str, NetworkNodeState]
    edges: dict[str, NetworkEdgeState]
    disruptions: tuple[CanonicalDisruption, ...] = ()

    def resolve_location_ids(self, target_id: str, locations: list[Location]) -> list[str]:
        return [
            location.location_id
            for location in locations
            if location.location_id == target_id
            or location.canonical_location_id == target_id
        ]


def normalize_disruptions(
    disruptions: Iterable[
        CanonicalDisruption | DisruptionRequest | Mapping[str, object]
    ],
) -> list[CanonicalDisruption]:
    """Normalize request and external shapes before policy evaluation."""

    normalized: list[CanonicalDisruption] = []
    for disruption in disruptions:
        if isinstance(disruption, CanonicalDisruption):
            normalized.append(disruption)
        elif isinstance(disruption, DisruptionRequest):
            normalized.extend(canonical_disruptions_from_request(disruption))
        else:
            normalized.extend(canonical_disruptions_from_external(dict(disruption)))
    return normalized


class NetworkStateEngine:
    """Build a deterministic operational overlay from canonical base records."""

    CLOSURE_TYPES = {
        DisruptionType.PORT_CLOSURE.value,
        DisruptionType.ROUTE_CLOSURE.value,
        DisruptionType.FACTORY_SHUTDOWN.value,
        DisruptionType.WAREHOUSE_SHUTDOWN.value,
    }

    def __init__(self, policy: DisruptionPolicyConfig | None = None) -> None:
        self.policy = policy or DisruptionPolicyConfig()

    def build(
        self,
        locations: list[Location],
        routes: list[Route],
        disruptions: Iterable[
            CanonicalDisruption | DisruptionRequest | Mapping[str, object]
        ] = (),
    ) -> NetworkState:
        nodes = {
            location.location_id: NetworkNodeState(
                location_id=location.location_id,
                base_status=location.status,
                available=location.status == Status.ACTIVE,
            )
            for location in locations
        }
        edges = {
            route.route_id: NetworkEdgeState.from_route(route)
            for route in routes
        }
        events = tuple(
            sorted(
                normalize_disruptions(disruptions),
                key=lambda event: (
                    event.disruption_id,
                    event.target_type.value,
                    event.target_id,
                    event.event_type,
                ),
            )
        )
        state = NetworkState(nodes=nodes, edges=edges, disruptions=events)
        for event in events:
            self._apply_event(state, locations, event)
        return state

    def _apply_event(
        self,
        state: NetworkState,
        locations: list[Location],
        event: CanonicalDisruption,
    ) -> None:
        event_type = event.event_type.upper()
        if event.target_type.value == "LOCATION":
            target_locations = state.resolve_location_ids(event.target_id, locations)
            for location_id in target_locations:
                node = state.nodes[location_id]
                self._add_disruption(node.disruption_ids, event.disruption_id)
                incident_edges = [
                    edge
                    for edge in state.edges.values()
                    if edge.source_location_id == location_id
                    or edge.destination_location_id == location_id
                ]
                if event_type in self.CLOSURE_TYPES:
                    node.available = False
                    for edge in incident_edges:
                        self._apply_closure(edge, event.disruption_id)
                elif event_type == DisruptionType.CONGESTION.value:
                    for edge in incident_edges:
                        self._apply_congestion(edge, event)
                elif event_type == DisruptionType.CAPACITY_REDUCTION.value:
                    for edge in incident_edges:
                        self._apply_capacity_reduction(edge, event)
                else:
                    for edge in incident_edges:
                        self._add_disruption(edge.disruption_ids, event.disruption_id)
            return

        edge = state.edges.get(event.target_id)
        if edge is None:
            return
        if event_type in self.CLOSURE_TYPES or event_type == DisruptionType.ROUTE_CLOSURE.value:
            self._apply_closure(edge, event.disruption_id)
        elif event_type == DisruptionType.CONGESTION.value:
            self._apply_congestion(edge, event)
        elif event_type == DisruptionType.CAPACITY_REDUCTION.value:
            self._apply_capacity_reduction(edge, event)
        else:
            self._add_disruption(edge.disruption_ids, event.disruption_id)

    @staticmethod
    def _add_disruption(disruption_ids: list[str], disruption_id: str) -> None:
        if disruption_id not in disruption_ids:
            disruption_ids.append(disruption_id)

    def _apply_closure(self, edge: NetworkEdgeState, disruption_id: str) -> None:
        edge.available = False
        self._add_disruption(edge.disruption_ids, disruption_id)

    def _apply_congestion(
        self,
        edge: NetworkEdgeState,
        event: CanonicalDisruption,
    ) -> None:
        edge.effective_duration *= self.policy.congestion_duration_multiplier
        edge.effective_risk = min(
            1.0,
            edge.effective_risk + self.policy.congestion_risk_penalty,
        )
        edge.current_load = min(
            edge.effective_capacity,
            edge.current_load * self.policy.congestion_current_load_multiplier,
        )
        edge.effective_capacity *= self.policy.congestion_capacity_multiplier
        self._add_disruption(edge.disruption_ids, event.disruption_id)

    def _apply_capacity_reduction(
        self,
        edge: NetworkEdgeState,
        event: CanonicalDisruption,
    ) -> None:
        reduction = self.policy.capacity_reduction_fraction(event.severity)
        edge.effective_capacity *= max(0.0, 1.0 - reduction)
        self._add_disruption(edge.disruption_ids, event.disruption_id)


def apply_network_state_to_graph(graph: object, state: NetworkState) -> None:
    """Project an overlay onto an already isolated NetworkX graph."""

    for location_id, node_state in state.nodes.items():
        if location_id not in graph:
            continue
        data = graph.nodes[location_id]
        location = data["location"].model_copy(
            update={"status": node_state.effective_status}
        )
        data["location"] = location
        data["status"] = node_state.effective_status
        data["available"] = node_state.available
        data["disruption_ids"] = list(node_state.disruption_ids)

    for source, destination, data in graph.edges(data=True):
        route_id = data["route_id"]
        edge_state = state.edges.get(route_id)
        if edge_state is None:
            continue
        data.update(
            {
                "available": edge_state.available,
                "effective_duration": edge_state.effective_duration,
                "effective_cost": edge_state.effective_cost,
                "effective_risk": edge_state.effective_risk,
                "effective_capacity": edge_state.effective_capacity,
                "current_load": edge_state.current_load,
                "disruption_ids": list(edge_state.disruption_ids),
                "duration": edge_state.effective_duration,
                "cost": edge_state.effective_cost,
                "risk": edge_state.effective_risk,
                "capacity": edge_state.effective_capacity,
                "status": Status.ACTIVE if edge_state.available else Status.BLOCKED,
                "weight": edge_state.effective_duration,
            }
        )
        route = data["route"].model_copy(
            update={
                "status": data["status"],
                "current_load": edge_state.current_load,
            }
        )
        route.current_duration_hours = edge_state.effective_duration
        data["route"] = route
