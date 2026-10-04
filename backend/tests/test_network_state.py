from copy import deepcopy

from backend.app.data import seed_data
from backend.app.disruption_policy import (
    canonical_disruptions_from_external,
    canonical_disruptions_from_request,
)
from backend.app.domain import Disruption, DisruptionLifecycleStatus, DisruptionTargetType
from backend.app.impact import classify_shipment_impacts, reroute_required_shipments
from backend.app.network_state import NetworkStateEngine
from backend.app.schemas import DisruptionRequest, DisruptionType, ImpactClassification


def _request(disruption_type, *, locations=None, routes=None, severity="HIGH"):
    return DisruptionRequest(
        disruption_type=disruption_type,
        affected_location_ids=locations or [],
        affected_route_ids=routes or [],
        duration_hours=48,
        severity=severity,
    )


def _dataset():
    return seed_data()


def _impacts(shipments, locations, routes, request):
    events = canonical_disruptions_from_request(request, disruption_id="D-1")
    state = NetworkStateEngine().build(locations, routes, events)
    return state, {impact.shipment_id: impact for impact in classify_shipment_impacts(shipments, state)}


def test_port_closure_isolated_from_canonical_records_and_baseline_state():
    locations, routes, shipments = _dataset()
    baseline = NetworkStateEngine().build(locations, routes)
    scenario, impacts = _impacts(
        shipments,
        locations,
        routes,
        _request(DisruptionType.PORT_CLOSURE, locations=["P_SG"]),
    )

    assert baseline.nodes["P_SG"].available is True
    assert baseline.edges["R1"].available is True
    assert scenario.nodes["P_SG"].available is False
    assert scenario.edges["R1"].available is False
    assert routes[0].status.value == "ACTIVE"
    assert routes[0].base_duration_hours == 48
    assert routes[0].current_load == 20
    assert impacts["S001"].classification == ImpactClassification.REROUTE_REQUIRED


def test_route_closure_only_changes_target_edge():
    locations, routes, _ = _dataset()
    baseline = NetworkStateEngine().build(locations, routes)
    scenario = NetworkStateEngine().build(
        locations,
        routes,
        canonical_disruptions_from_request(
            _request(DisruptionType.ROUTE_CLOSURE, routes=["R10"]), disruption_id="D-2"
        ),
    )

    assert scenario.edges["R10"].available is False
    assert scenario.edges["R2"].available is True
    assert baseline.edges["R10"].available is True


def test_congestion_keeps_route_available_but_marks_matching_shipment_at_risk():
    locations, routes, shipments = _dataset()
    state, impacts = _impacts(
        shipments,
        locations,
        routes,
        _request(DisruptionType.CONGESTION, locations=["P_KL"], severity="MEDIUM"),
    )

    assert state.edges["R2"].available is True
    assert state.edges["R2"].effective_duration == 81
    assert state.edges["R2"].effective_risk == 0.4
    assert impacts["S002"].classification == ImpactClassification.SHIPMENT_AT_RISK


def test_capacity_reduction_requires_reroute_when_remaining_capacity_is_insufficient():
    locations, routes, shipments = _dataset()
    state, impacts = _impacts(
        shipments,
        locations,
        routes,
        _request(DisruptionType.CAPACITY_REDUCTION, routes=["R3"], severity="CRITICAL"),
    )

    assert state.edges["R3"].effective_capacity == 25
    assert impacts["S003"].classification == ImpactClassification.REROUTE_REQUIRED
    assert impacts["S003"].reason == "remaining route lacks effective capacity"


def test_factory_shutdown_uses_current_location_and_remaining_legs():
    locations, routes, shipments = _dataset()
    progressed = deepcopy(shipments[0])
    progressed.shipment_id = "S001-PROGRESSED"
    for leg in progressed.route_legs:
        leg.shipment_id = progressed.shipment_id
    progressed.current_location_id = "P_SG"
    progressed.route_legs[0].status = "COMPLETED"
    progressed.route_legs[1].status = "CURRENT"
    state, impacts = _impacts(
        [shipments[0], progressed],
        locations,
        routes,
        _request(DisruptionType.FACTORY_SHUTDOWN, locations=["F_SZ"]),
    )

    assert state.nodes["F_SZ"].available is False
    assert impacts["S001"].classification == ImpactClassification.REROUTE_REQUIRED
    assert impacts[progressed.shipment_id].classification == ImpactClassification.UNAFFECTED


def test_passed_location_is_not_an_active_route_intersection():
    locations, routes, shipments = _dataset()
    progressed = deepcopy(shipments[0])
    progressed.current_location_id = "W_SG"
    progressed.route_legs[0].status = "COMPLETED"
    progressed.route_legs[1].status = "COMPLETED"
    progressed.route_legs[2].status = "CURRENT"
    _, impacts = _impacts(
        [progressed],
        locations,
        routes,
        _request(DisruptionType.PORT_CLOSURE, locations=["P_SG"]),
    )

    assert impacts[progressed.shipment_id].classification == ImpactClassification.UNAFFECTED


def test_current_port_is_not_retroactively_affected_after_departure():
    locations, routes, shipments = _dataset()
    progressed = deepcopy(shipments[0])
    progressed.shipment_id = "S001-DEPARTED"
    for leg in progressed.route_legs:
        leg.shipment_id = progressed.shipment_id
    progressed.current_location_id = "P_SG"
    progressed.route_legs[0].status = "COMPLETED"
    progressed.route_legs[1].status = "CURRENT"
    _, impacts = _impacts(
        [progressed],
        locations,
        routes,
        _request(DisruptionType.PORT_CLOSURE, locations=["P_SG"]),
    )

    assert impacts[progressed.shipment_id].classification == ImpactClassification.UNAFFECTED


def test_warehouse_shutdown_affects_remaining_warehouse_dependency():
    locations, routes, shipments = _dataset()
    _, impacts = _impacts(
        [shipments[0]],
        locations,
        routes,
        _request(DisruptionType.WAREHOUSE_SHUTDOWN, locations=["W_SG"]),
    )

    assert impacts["S001"].classification == ImpactClassification.REROUTE_REQUIRED


def test_unrelated_shipment_is_unaffected_and_relevant_unknown_event_is_warning():
    locations, routes, shipments = _dataset()
    _, unrelated = _impacts(
        [shipments[1]],
        locations,
        routes,
        _request(DisruptionType.PORT_CLOSURE, locations=["P_SG"]),
    )
    warning_event = Disruption(
        disruption_id="D-WARN",
        event_type="STRIKE",
        target_type=DisruptionTargetType.LOCATION,
        target_id="P_SG",
        severity="HIGH",
        status=DisruptionLifecycleStatus.ACTIVE,
        start_time=shipments[0].current_eta,
        end_time=shipments[0].required_delivery_time,
        source="SIMULATED",
        is_simulated=True,
    )
    state = NetworkStateEngine().build(locations, routes, [warning_event])
    warning = {item.shipment_id: item for item in classify_shipment_impacts([shipments[0]], state)}

    assert unrelated["S002"].classification == ImpactClassification.UNAFFECTED
    assert warning["S001"].classification == ImpactClassification.NETWORK_WARNING


def test_multiple_disruptions_are_combined_deterministically():
    locations, routes, shipments = _dataset()
    requests = [
        _request(DisruptionType.PORT_CLOSURE, locations=["P_SG"]),
        _request(DisruptionType.CAPACITY_REDUCTION, routes=["R2"], severity="HIGH"),
    ]
    events = [event for request in requests for event in canonical_disruptions_from_request(request, disruption_id="D-1")]
    state = NetworkStateEngine().build(locations, routes, events)
    impacts = {item.shipment_id: item for item in classify_shipment_impacts(shipments, state)}

    assert state.edges["R1"].available is False
    assert state.edges["R2"].effective_capacity == 50
    assert impacts["S001"].classification == ImpactClassification.REROUTE_REQUIRED
    assert impacts["S002"].classification == ImpactClassification.SHIPMENT_AT_RISK


def test_portwatch_and_simulated_events_use_the_same_policy_path():
    locations, routes, _ = _dataset()
    locations[3].canonical_location_id = "PW_PORT_port1201"
    simulated = canonical_disruptions_from_request(
        _request(DisruptionType.CONGESTION, locations=["P_SG"]), disruption_id="SIM"
    )
    external = canonical_disruptions_from_external(
        {
            "event_id": "PW-1",
            "event_type": "PORT_CONGESTION",
            "affected_location_ids": ["PW_PORT_port1201"],
            "severity": "HIGH",
            "source": "PORTWATCH",
        }
    )
    simulated_state = NetworkStateEngine().build(locations, routes, simulated)
    external_state = NetworkStateEngine().build(locations, routes, external)

    assert simulated_state.edges["R1"].effective_duration == external_state.edges["R1"].effective_duration
    assert simulated_state.edges["R1"].effective_risk == external_state.edges["R1"].effective_risk
    assert simulated_state.edges["R1"].available is True


def test_only_reroute_required_shipments_are_selected():
    locations, routes, shipments = _dataset()
    request = _request(DisruptionType.PORT_CLOSURE, locations=["P_SG"])
    events = canonical_disruptions_from_request(request, disruption_id="D-1")
    state = NetworkStateEngine().build(locations, routes, events)
    required, impacts = reroute_required_shipments(shipments, state)
    by_id = {item.shipment_id: item for item in impacts}

    assert required
    assert all(by_id[item.shipment_id].classification == ImpactClassification.REROUTE_REQUIRED for item in required)
    assert all(item.classification != ImpactClassification.SHIPMENT_AT_RISK for item in impacts if item.shipment_id in {"S002", "S004"})
