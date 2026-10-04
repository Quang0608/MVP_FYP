"""Application services shared by dashboard and agent simulation paths."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

import networkx as nx

from .api.serializers import location_response, shipment_response
from .config import settings
from .disruption_policy import canonical_disruptions_from_request
from .domain import Disruption as CanonicalDisruption
from .graph import build_supply_chain_graph
from .impact import classify_shipment_impacts
from .network_state import NetworkState, NetworkStateEngine
from .repository import get_run, load_runtime_dataset, save_disruption
from .schemas import Disruption, DisruptionRequest, SimulationResult
from .integrations.portwatch import PortWatchAdapter
from .services import find_downstream_impacts


class UnknownNetworkReferenceError(ValueError):
    """Raised when a simulation refers to a non-existent runtime entity."""

    def __init__(self, unknown_location_ids: list[str], unknown_route_ids: list[str]) -> None:
        self.unknown_location_ids = unknown_location_ids
        self.unknown_route_ids = unknown_route_ids
        super().__init__("Disruption references unknown network identifiers.")


@dataclass(frozen=True)
class RuntimeSnapshot:
    locations: list
    routes: list
    shipments: list
    portwatch_state: dict


@dataclass(frozen=True)
class SimulationExecution:
    disruption: Disruption
    request: DisruptionRequest
    result: SimulationResult
    state: NetworkState
    graph: nx.DiGraph


@dataclass(frozen=True)
class SimulationContext:
    disruption: Disruption
    request: DisruptionRequest
    snapshot: RuntimeSnapshot
    state: NetworkState
    graph: nx.DiGraph
    baseline_graph: nx.DiGraph
    stored: dict


def load_runtime_snapshot() -> RuntimeSnapshot:
    dataset = load_runtime_dataset()
    adapter = PortWatchAdapter.from_settings(settings)
    return RuntimeSnapshot(
        locations=adapter.enrich_locations(dataset.locations),
        routes=dataset.routes,
        shipments=dataset.shipments,
        portwatch_state=adapter.runtime_port_state(),
    )


def validate_simulation_references(
    request: DisruptionRequest,
    snapshot: RuntimeSnapshot,
) -> None:
    known_location_ids = {location.location_id for location in snapshot.locations}
    known_route_ids = {route.route_id for route in snapshot.routes}
    unknown_location_ids = sorted(
        set(request.affected_location_ids) - known_location_ids
    )
    unknown_route_ids = sorted(
        set(request.affected_route_ids) - known_route_ids
    )
    if unknown_location_ids or unknown_route_ids:
        raise UnknownNetworkReferenceError(
            unknown_location_ids,
            unknown_route_ids,
        )


def build_scenario_graphs(
    snapshot: RuntimeSnapshot,
    events: Iterable[CanonicalDisruption],
) -> tuple[NetworkState, nx.DiGraph, nx.DiGraph]:
    baseline_state = NetworkStateEngine().build(
        snapshot.locations,
        snapshot.routes,
    )
    baseline_graph = build_supply_chain_graph(
        snapshot.locations,
        snapshot.routes,
        snapshot.portwatch_state,
        network_state=baseline_state,
    )
    state = NetworkStateEngine().build(
        snapshot.locations,
        snapshot.routes,
        events,
    )
    graph = build_supply_chain_graph(
        snapshot.locations,
        snapshot.routes,
        snapshot.portwatch_state,
        network_state=state,
    )
    return state, graph, baseline_graph


def run_simulation(
    request: DisruptionRequest,
    *,
    snapshot: RuntimeSnapshot | None = None,
    disruption_id: str | None = None,
    created_at: datetime | None = None,
) -> SimulationExecution:
    """Run and persist one canonical deterministic simulation.

    Dashboard endpoints and agent tools call this function. It creates only
    disruption/simulation records; canonical locations, routes, and shipments
    are never mutated.
    """

    snapshot = snapshot or load_runtime_snapshot()
    validate_simulation_references(request, snapshot)
    created_at = created_at or datetime.now(timezone.utc)
    disruption = Disruption(
        id=disruption_id or str(uuid4()),
        request=request,
        created_at=created_at,
    )
    events = canonical_disruptions_from_request(
        request,
        disruption_id=disruption.id,
        start_time=created_at,
    )
    state, graph, _ = build_scenario_graphs(snapshot, events)
    shipment_impacts = classify_shipment_impacts(snapshot.shipments, state)
    affected_ids = {
        impact.shipment_id
        for impact in shipment_impacts
        if impact.classification.value != "UNAFFECTED"
    }
    affected = [
        shipment
        for shipment in snapshot.shipments
        if shipment.shipment_id in affected_ids
    ]
    result = SimulationResult(
        disruption_id=disruption.id,
        affected_shipments=[shipment_response(shipment) for shipment in affected],
        downstream_impacts=[
            location_response(location)
            for location in find_downstream_impacts(
                graph,
                request.affected_location_ids,
            )
        ],
        shipment_impacts=shipment_impacts,
    )
    save_disruption(disruption, result.model_dump(mode="json"))
    return SimulationExecution(
        disruption=disruption,
        request=request,
        result=result,
        state=state,
        graph=graph,
    )


def load_simulation_context(simulation_run_id: str) -> SimulationContext:
    stored = get_run(simulation_run_id)
    if stored is None:
        raise LookupError(f"Simulation {simulation_run_id} was not found")
    disruption = Disruption.model_validate(stored["disruption"])
    snapshot = load_runtime_snapshot()
    validate_simulation_references(disruption.request, snapshot)
    events = canonical_disruptions_from_request(
        disruption.request,
        disruption_id=disruption.id,
        start_time=disruption.created_at,
    )
    state, graph, baseline_graph = build_scenario_graphs(snapshot, events)
    return SimulationContext(
        disruption=disruption,
        request=disruption.request,
        snapshot=snapshot,
        state=state,
        graph=graph,
        baseline_graph=baseline_graph,
        stored=stored,
    )
