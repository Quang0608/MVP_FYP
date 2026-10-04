from backend.app.data import seed_data
from backend.app.schemas import (
    DisruptionRequest,
    DisruptionType,
    Priority,
    RoutePlanRequest,
    Status,
)
from backend.app.services import (
    ImpactDetectionService,
    apply_disruption,
    build_supply_chain_graph,
    detect_external_impacts,
    find_affected_shipments,
    find_candidate_routes,
    find_portwatch_affected_shipments,
    plan_route,
    reroute,
    score_routes,
)


def setup():
    locations,routes,shipments=seed_data(); return build_supply_chain_graph(locations,routes), shipments


def test_graph_has_seed_network():
    graph,_=setup(); assert graph.number_of_nodes() >= 13 and graph.number_of_edges() >= 17


def test_portwatch_state_is_attached_without_changing_route_weights():
    locations, routes, shipments = seed_data()
    state = {
        "P_SG": {
            "activity_score": 0.72,
            "activity_anomaly_score": 0.61,
            "operational_status": "HIGH_ACTIVITY",
            "latest_observation_date": "2026-08-14",
        }
    }
    graph = build_supply_chain_graph(locations, routes, state)

    assert graph.nodes["P_SG"]["operational_status"] == "HIGH_ACTIVITY"
    assert graph.nodes["P_SG"]["latest_activity_score"] == 0.72
    assert graph["F_SZ"]["P_SG"]["weight"] == 48
    assert len(find_portwatch_affected_shipments(shipments, state)) > 0


def test_graph_overlay_keeps_canonical_portwatch_provenance():
    locations, routes, _ = seed_data()
    state = {
        "P_SG": {
            "canonical_location_id": "PW_PORT_port1201",
            "source": "PORTWATCH",
            "source_port_id": "port1201",
            "activity_score": 1.0,
            "activity_anomaly_score": -0.07,
            "operational_status": "HIGH_ACTIVITY",
            "latest_observation_date": "2026-08-14",
        }
    }
    graph = build_supply_chain_graph(locations, routes, state)

    assert graph.nodes["P_SG"]["canonical_location_id"] == "PW_PORT_port1201"
    assert graph.nodes["P_SG"]["portwatch_source"] == "PORTWATCH"
    assert graph.nodes["P_SG"]["activity_anomaly_score"] == -0.07
    assert graph["F_SZ"]["P_SG"]["weight"] == 48


def external_singapore_disruption():
    return {
        "event_id": "PW-SG-1",
        "source": "PORTWATCH",
        "affected_location_ids": ["PW_PORT_port1201"],
    }


def singapore_graph():
    locations, routes, shipments = seed_data()
    state = {
        "P_SG": {
            "canonical_location_id": "PW_PORT_port1201",
            "source": "PORTWATCH",
            "operational_status": "HIGH_ACTIVITY",
        }
    }
    return build_supply_chain_graph(locations, routes, state), shipments


def test_external_disruption_affects_shipment_using_remaining_port():
    graph, shipments = singapore_graph()

    impacts = detect_external_impacts(
        external_singapore_disruption(), [shipments[0]], graph
    )

    assert len(impacts) == 1
    assert impacts[0]["event_id"] == "PW-SG-1"
    assert impacts[0]["affected_location"] == "P_SG"
    assert impacts[0]["canonical_location_id"] == "PW_PORT_port1201"
    assert impacts[0]["affected_shipments"] == [shipments[0].id]
    assert impacts[0]["reason"] == "remaining route contains disrupted port"


def test_external_disruption_does_not_affect_shipment_without_port():
    graph, shipments = singapore_graph()

    impacts = ImpactDetectionService.detect_external_impacts(
        external_singapore_disruption(), [shipments[1]], graph
    )

    assert impacts == []


def test_external_disruption_does_not_affect_shipment_after_port_is_passed():
    graph, shipments = singapore_graph()
    passed_shipment = shipments[0].model_copy(update={"current_location_id": "W_SG"})

    impacts = detect_external_impacts(
        external_singapore_disruption(), [passed_shipment], graph
    )

    assert impacts == []


def test_external_disruption_with_no_dependent_shipments_has_no_action():
    graph, shipments = singapore_graph()

    impacts = detect_external_impacts(
        external_singapore_disruption(), shipments[1:2], graph
    )

    assert impacts == []


def test_singapore_closure_affects_expected_shipments_and_blocks_port():
    graph,shipments=setup(); request=DisruptionRequest(disruption_type=DisruptionType.PORT_CLOSURE,affected_location_ids=["P_SG"],duration_hours=72)
    assert any(s.id=="S001" for s in find_affected_shipments(shipments,request)); apply_disruption(graph,request)
    assert graph["F_SZ"]["P_SG"]["route"].status.value=="BLOCKED"


def test_candidate_routes_avoid_closed_port():
    graph,shipments=setup(); request=DisruptionRequest(disruption_type=DisruptionType.PORT_CLOSURE,affected_location_ids=["P_SG"],duration_hours=72); apply_disruption(graph,request)
    candidates=find_candidate_routes(graph,shipments[0]); assert candidates and all("P_SG" not in r.location_ids for r in candidates)


def test_high_priority_favors_shorter_path():
    graph,shipments=setup(); candidates=find_candidate_routes(graph,shipments[0]); scored=score_routes(candidates,Priority.HIGH)
    assert scored[0].route_score <= scored[-1].route_score


def test_no_route_is_explicit_result():
    graph,shipments=setup(); request=DisruptionRequest(disruption_type=DisruptionType.MULTIPLE_PORT,affected_location_ids=["P_SG","P_KL"],duration_hours=72); apply_disruption(graph,request)
    results=reroute(graph,[shipments[0]]); assert results[0].status in {"REROUTED","NO_FEASIBLE_ROUTE"}


def test_disrupted_graph_does_not_mutate_baseline_or_source_models():
    locations, routes, _ = seed_data()
    baseline = build_supply_chain_graph(locations, routes)
    disrupted = build_supply_chain_graph(locations, routes)
    request = DisruptionRequest(
        disruption_type=DisruptionType.PORT_CLOSURE,
        affected_location_ids=["P_SG"],
        duration_hours=72,
    )

    apply_disruption(disrupted, request)

    assert baseline.nodes["P_SG"]["location"].status == Status.ACTIVE
    assert baseline["F_SZ"]["P_SG"]["route"].status == Status.ACTIVE
    assert baseline["F_SZ"]["P_SG"]["route"].current_duration_hours == 48
    assert baseline["F_SZ"]["P_SG"]["route"].current_load == 20
    assert next(location for location in locations if location.id == "P_SG").status == Status.ACTIVE
    assert next(route for route in routes if route.id == "R1").status == Status.ACTIVE


def test_congestion_changes_are_isolated_to_one_graph():
    locations, routes, _ = seed_data()
    baseline = build_supply_chain_graph(locations, routes)
    congested = build_supply_chain_graph(locations, routes)
    request = DisruptionRequest(
        disruption_type=DisruptionType.CONGESTION,
        affected_location_ids=["P_KL"],
        duration_hours=48,
    )

    apply_disruption(congested, request)

    assert congested["F_SZ"]["P_KL"]["route"].current_duration_hours == 81
    assert congested["F_SZ"]["P_KL"]["route"].current_load == 30
    assert baseline["F_SZ"]["P_KL"]["route"].current_duration_hours == 54
    assert baseline["F_SZ"]["P_KL"]["route"].current_load == 20


def test_capacity_reservations_are_isolated_from_baseline_graph():
    locations, routes, shipments = seed_data()
    baseline = build_supply_chain_graph(locations, routes)
    active = build_supply_chain_graph(locations, routes)
    baseline_loads = {
        data["route"].id: data["route"].current_load
        for _, _, data in active.edges(data=True)
    }

    results = reroute(active, [shipments[0]], baseline)

    assert results[0].status == "REROUTED"
    assert any(
        data["route"].current_load > baseline_loads[data["route"].id]
        for _, _, data in active.edges(data=True)
    )
    assert all(
        data["route"].current_load == baseline_loads[data["route"].id]
        for _, _, data in baseline.edges(data=True)
    )


def test_before_after_route_calculation_is_repeatable():
    locations, routes, shipments = seed_data()
    request = DisruptionRequest(
        disruption_type=DisruptionType.PORT_CLOSURE,
        affected_location_ids=["P_SG"],
        duration_hours=72,
    )

    def calculate():
        baseline = build_supply_chain_graph(locations, routes)
        active = build_supply_chain_graph(locations, routes)
        apply_disruption(active, request)
        return plan_route(
            active,
            RoutePlanRequest(
                origin_id="F_SZ",
                destination_id="C_A",
                disruption=request,
                generate_explanation=False,
            ),
            baseline,
        ).model_dump()

    assert calculate() == calculate()
