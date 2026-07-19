from backend.app.data import seed_data
from backend.app.schemas import DisruptionRequest, DisruptionType, Priority
from backend.app.services import build_supply_chain_graph, apply_disruption, find_affected_shipments, find_candidate_routes, score_routes, reroute


def setup():
    locations,routes,shipments=seed_data(); return build_supply_chain_graph(locations,routes), shipments


def test_graph_has_seed_network():
    graph,_=setup(); assert graph.number_of_nodes() >= 13 and graph.number_of_edges() >= 17


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
