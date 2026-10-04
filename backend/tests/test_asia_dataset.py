from copy import deepcopy

import networkx as nx
import pandas as pd
import pytest

from backend.app.asia_dataset import (
    ASIA_PORT_IDS,
    AsiaGenerationConfig,
    generate_asia_runtime_dataset,
    report_asia_dataset,
    validate_asia_dataset,
)
from backend.app.disruption_policy import canonical_disruptions_from_request
from backend.app.domain import ShipmentRouteLeg
from backend.app.graph import build_supply_chain_graph
from backend.app.impact import classify_shipment_impacts, reroute_required_shipments
from backend.app.network_state import NetworkStateEngine
from backend.app.schemas import DisruptionRequest, DisruptionType, ImpactClassification
from backend.app.services import reroute


@pytest.fixture(scope="module")
def asia_dataset():
    return generate_asia_runtime_dataset(AsiaGenerationConfig(seed=20260913, shipment_count=220))


def test_selected_ports_are_existing_unique_canonical_port_master_entities():
    frame = pd.read_parquet("data/processed/ports/port_master.parquet")
    port_ids = set(frame.loc[frame["location_type"] == "PORT", "location_id"])

    assert len(ASIA_PORT_IDS) == len(set(ASIA_PORT_IDS))
    assert set(ASIA_PORT_IDS).issubset(port_ids)


def test_asia_dataset_has_expected_population_and_topology(asia_dataset):
    report = validate_asia_dataset(asia_dataset)
    graph = nx.DiGraph()
    graph.add_edges_from(
        (route.source_location_id, route.destination_location_id)
        for route in asia_dataset.routes
    )

    assert report.real_ports == 51
    assert report.synthetic_factories == 12
    assert report.synthetic_warehouses == 14
    assert report.synthetic_customers == 14
    assert 80 <= report.routes <= 150
    assert 150 <= report.shipments <= 300
    assert report.connected_components == 1
    assert report.shipments_with_alternatives >= 200
    assert not nx.is_empty(graph)
    assert all(location.source == "WPI" for location in asia_dataset.locations if location.location_id in ASIA_PORT_IDS)
    assert all(location.source == "SYNTHETIC" for location in asia_dataset.locations if location.location_id.startswith("ASIA_"))
    assert all(location.latitude is not None and location.longitude is not None for location in asia_dataset.locations)


def test_fixed_seed_reproduces_network_and_shipments():
    config = AsiaGenerationConfig(seed=77, shipment_count=180)
    first = generate_asia_runtime_dataset(config)
    second = generate_asia_runtime_dataset(config)

    assert first == second
    assert report_asia_dataset(config) == validate_asia_dataset(first)


def test_every_active_shipment_has_ordered_progress_and_feasible_route(asia_dataset):
    routes = {route.route_id: route for route in asia_dataset.routes}
    for shipment in asia_dataset.shipments:
        legs = shipment.ordered_route_legs
        assert all(isinstance(leg, ShipmentRouteLeg) for leg in legs)
        assert [leg.sequence_no for leg in legs] == list(range(1, len(legs) + 1))
        assert legs[0].source_location_id == shipment.origin_location_id
        assert legs[-1].destination_location_id == shipment.destination_location_id
        assert all(leg.route_id in routes for leg in legs)
        if shipment.status == "COMPLETED":
            assert shipment.current_location_id == shipment.destination_location_id
            assert all(leg.status == "COMPLETED" for leg in legs)
        else:
            assert shipment.current_location_id in {
                shipment.origin_location_id,
                *(leg.source_location_id for leg in legs),
            }


def _request(disruption_type, *, locations=None, routes=None, severity="HIGH"):
    return DisruptionRequest(
        disruption_type=disruption_type,
        affected_location_ids=locations or [],
        affected_route_ids=routes or [],
        duration_hours=72,
        severity=severity,
    )


def _scenario(asia_dataset, request):
    events = canonical_disruptions_from_request(request, disruption_id="TEST-D")
    state = NetworkStateEngine().build(asia_dataset.locations, asia_dataset.routes, events)
    graph = build_supply_chain_graph(
        asia_dataset.locations,
        asia_dataset.routes,
        network_state=state,
    )
    return state, graph


def test_singapore_closure_detects_remaining_shipments_and_preserves_baseline(asia_dataset):
    baseline = build_supply_chain_graph(asia_dataset.locations, asia_dataset.routes)
    state, scenario = _scenario(
        asia_dataset,
        _request(DisruptionType.PORT_CLOSURE, locations=["LOC_WPI_50000"]),
    )
    impacts = classify_shipment_impacts(asia_dataset.shipments, state)
    required = [item for item in impacts if item.classification == ImpactClassification.REROUTE_REQUIRED]

    assert required
    assert state.nodes["LOC_WPI_50000"].available is False
    assert scenario.nodes["LOC_WPI_50000"]["available"] is False
    assert baseline.nodes["LOC_WPI_50000"]["available"] is True
    assert all(
        data["available"] is True
        for _, _, data in baseline.edges(data=True)
    )


def test_passed_singapore_port_is_not_marked_affected(asia_dataset):
    shipment = next(
        shipment
        for shipment in asia_dataset.shipments
        if "LOC_WPI_50000" in shipment.planned_route_location_ids[1:-1]
        and shipment.status != "COMPLETED"
    )
    target_index = next(
        index
        for index, leg in enumerate(shipment.ordered_route_legs)
        if leg.destination_location_id == "LOC_WPI_50000"
    )
    if target_index + 1 >= len(shipment.route_legs):
        pytest.skip("Selected fixture shipment ends at Singapore")
    progressed = shipment.model_copy(deep=True)
    progressed.current_location_id = "LOC_WPI_50000"
    progressed.route_legs = [
        leg.model_copy(
            update={
                "status": "COMPLETED" if index <= target_index else "CURRENT" if index == target_index + 1 else "PLANNED"
            }
        )
        for index, leg in enumerate(progressed.ordered_route_legs)
    ]
    state, _ = _scenario(
        asia_dataset,
        _request(DisruptionType.PORT_CLOSURE, locations=["LOC_WPI_50000"]),
    )
    impact = classify_shipment_impacts([progressed], state)[0]

    assert impact.classification == ImpactClassification.UNAFFECTED


def test_port_klang_congestion_and_capacity_reduction_are_classified(asia_dataset):
    congestion_state, congestion_graph = _scenario(
        asia_dataset,
        _request(DisruptionType.CONGESTION, locations=["LOC_WPI_49930"], severity="MEDIUM"),
    )
    congestion_impacts = classify_shipment_impacts(asia_dataset.shipments, congestion_state)
    assert any(item.classification == ImpactClassification.SHIPMENT_AT_RISK for item in congestion_impacts)
    assert congestion_state.nodes["LOC_WPI_49930"].available is True
    assert any(
        data["available"] and data["effective_duration"] > data["base_duration"]
        for source, destination, data in congestion_graph.edges(data=True)
        if source == "LOC_WPI_49930" or destination == "LOC_WPI_49930"
    )

    route_id = next(
        leg.route_id
        for shipment in asia_dataset.shipments
        for leg in shipment.ordered_route_legs
        if leg.status != "COMPLETED"
    )
    capacity_state, _ = _scenario(
        asia_dataset,
        _request(DisruptionType.CAPACITY_REDUCTION, routes=[route_id], severity="CRITICAL"),
    )
    capacity_impacts = classify_shipment_impacts(asia_dataset.shipments, capacity_state)
    assert any(item.classification == ImpactClassification.REROUTE_REQUIRED for item in capacity_impacts)


def test_reroute_only_receives_required_shipments_and_can_find_alternatives(asia_dataset):
    request = _request(DisruptionType.PORT_CLOSURE, locations=["LOC_WPI_50000"])
    state, scenario = _scenario(asia_dataset, request)
    required, impacts = reroute_required_shipments(asia_dataset.shipments, state)
    baseline = build_supply_chain_graph(asia_dataset.locations, asia_dataset.routes)
    recommendations = reroute(scenario, required, baseline)
    required_ids = {item.shipment_id for item in impacts if item.classification == ImpactClassification.REROUTE_REQUIRED}

    assert required
    assert {shipment.shipment_id for shipment in required} == required_ids
    assert recommendations
    assert any(item.status == "REROUTED" for item in recommendations)
    baseline_loads = {
        data["route_id"]: data["current_load"]
        for _, _, data in baseline.edges(data=True)
    }
    assert all(baseline_loads[route.route_id] == route.current_load for route in asia_dataset.routes)
