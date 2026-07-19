from backend.app.data import seed_data
from backend.app.schemas import RoutePlanRequest, DisruptionRequest, DisruptionType
from backend.app.services import build_supply_chain_graph, apply_disruption, plan_route


def test_interactive_route_avoids_closed_singapore():
    locations,routes,_=seed_data(); baseline=build_supply_chain_graph(locations,routes)
    locations,routes,_=seed_data(); active=build_supply_chain_graph(locations,routes)
    disruption=DisruptionRequest(disruption_type=DisruptionType.PORT_CLOSURE,affected_location_ids=["P_SG"],duration_hours=72)
    apply_disruption(active,disruption)
    result=plan_route(active,RoutePlanRequest(origin_id="F_SZ",destination_id="C_A",disruption=disruption,generate_explanation=False),baseline)
    assert result.status=="ROUTE_FOUND"
    assert all("P_SG" not in route.location_ids for route in result.candidate_routes)


def test_interactive_plan_explains_disrupted_destination():
    locations,routes,_=seed_data(); graph=build_supply_chain_graph(locations,routes)
    disruption=DisruptionRequest(disruption_type=DisruptionType.PORT_CLOSURE,affected_location_ids=["P_SG"],duration_hours=72)
    apply_disruption(graph,disruption)
    result=plan_route(graph,RoutePlanRequest(origin_id="F_SZ",destination_id="P_SG",disruption=disruption,generate_explanation=False),build_supply_chain_graph(*seed_data()[:2]))
    assert result.status=="DISRUPTED_ENDPOINT"
