from __future__ import annotations
import json
import networkx as nx
from dataclasses import dataclass
from datetime import datetime, timezone
from .schemas import *


def build_supply_chain_graph(locations: list[Location], routes: list[Route]) -> nx.DiGraph:
    graph=nx.DiGraph()
    for location in locations: graph.add_node(location.id, location=location)
    for route in routes: graph.add_edge(route.source_location_id,route.destination_location_id,route=route,weight=route.current_duration_hours)
    return graph


def apply_disruption(graph: nx.DiGraph, disruption: DisruptionRequest) -> None:
    blocked_nodes=set(disruption.affected_location_ids); blocked_routes=set(disruption.affected_route_ids)
    for node in blocked_nodes:
        if node in graph: graph.nodes[node]["location"].status=Status.DISRUPTED
    for u,v,data in graph.edges(data=True):
        route=data["route"]
        if disruption.disruption_type==DisruptionType.CONGESTION and (u in blocked_nodes or v in blocked_nodes):
            route.current_duration_hours*=1.5; route.current_load=min(route.capacity,route.current_load*1.5); data["weight"]=route.current_duration_hours
        elif route.id in blocked_routes or u in blocked_nodes or v in blocked_nodes:
            route.status=Status.BLOCKED


def find_affected_shipments(shipments: list[Shipment], disruption: DisruptionRequest) -> list[Shipment]:
    nodes=set(disruption.affected_location_ids); routes=set(disruption.affected_route_ids)
    return [s for s in shipments if nodes.intersection(s.planned_route_location_ids) or routes.intersection(s.planned_route_ids)]


def find_downstream_impacts(graph: nx.DiGraph, disrupted_location_ids: list[str]) -> list[Location]:
    output={}
    for source in disrupted_location_ids:
        if source not in graph: continue
        for node in nx.descendants(graph,source):
            loc=graph.nodes[node]["location"]
            if loc.type in {LocationType.WAREHOUSE,LocationType.CUSTOMER}: output[node]=loc
    return list(output.values())


def path_result(graph: nx.DiGraph, nodes: list[str], load: float) -> PathResult | None:
    legs=[]
    for a,b in zip(nodes,nodes[1:]):
        if not graph.has_edge(a,b): return None
        route=graph[a][b]["route"]
        if route.status==Status.BLOCKED: return None
        legs.append(route)
    feasible=all(r.current_load+load<=r.capacity for r in legs)
    penalty=sum((r.current_load+load)/r.capacity for r in legs)/max(1,len(legs))
    return PathResult(location_ids=nodes,route_ids=[r.id for r in legs],duration_hours=sum(r.current_duration_hours for r in legs),cost=sum(r.cost for r in legs),risk_score=sum(r.risk_score for r in legs)/max(1,len(legs)),capacity_feasible=feasible,capacity_penalty=penalty)


def find_candidate_routes(graph: nx.DiGraph, shipment: Shipment, k: int=3) -> list[PathResult]:
    active=graph.copy()
    active.remove_edges_from([(u,v) for u,v,d in active.edges(data=True) if d["route"].status==Status.BLOCKED])
    candidates=[]
    try:
        paths=nx.shortest_simple_paths(active,shipment.current_location_id,shipment.destination_id,weight="weight")
        for path in paths:
            result=path_result(graph,path,shipment.load_units)
            if result and result.capacity_feasible: candidates.append(result)
            if len(candidates)>=k: break
    except (nx.NetworkXNoPath,nx.NodeNotFound):
        return []
    return candidates


def plan_route(graph: nx.DiGraph, request: RoutePlanRequest, baseline: nx.DiGraph | None = None) -> RoutePlanResult:
    """Plan one user-selected journey; no shipment database record is required."""
    query=Shipment(id="INTERACTIVE",origin_id=request.origin_id,destination_id=request.destination_id,
                   current_location_id=request.origin_id,planned_route_location_ids=[],planned_route_ids=[],
                   deadline=datetime.now(timezone.utc),priority=request.priority,load_units=request.load_units)
    original=None
    if baseline:
        try: original=path_result(baseline,nx.shortest_path(baseline,request.origin_id,request.destination_id,weight="weight"),request.load_units)
        except (nx.NetworkXNoPath,nx.NodeNotFound):
            return RoutePlanResult(status="NO_BASE_ROUTE",reason="The selected origin and destination are not connected by a directed route in the current network.",origin_id=request.origin_id,destination_id=request.destination_id,disruption=request.disruption)
    disrupted=set(request.disruption.affected_location_ids) if request.disruption else set()
    if request.origin_id in disrupted or request.destination_id in disrupted:
        endpoint="origin" if request.origin_id in disrupted else "destination"
        return RoutePlanResult(status="DISRUPTED_ENDPOINT",reason=f"The selected {endpoint} is directly affected by the active disruption. Choose another endpoint or disable the disruption.",origin_id=request.origin_id,destination_id=request.destination_id,original_route=original,disruption=request.disruption)
    candidates=score_routes(find_candidate_routes(graph,query),request.priority)
    reason=None if candidates else "Every remaining path is blocked by the disruption or exceeds available route capacity."
    return RoutePlanResult(status="ROUTE_FOUND" if candidates else "NO_FEASIBLE_ROUTE",reason=reason,origin_id=request.origin_id,destination_id=request.destination_id,original_route=original,candidate_routes=candidates,selected_route=candidates[0] if candidates else None,disruption=request.disruption)


def route_plan_decision_record(plan: RoutePlanResult) -> dict:
    return {"route_request":{"origin_id":plan.origin_id,"destination_id":plan.destination_id},
            "disruption":plan.disruption.model_dump(mode="json") if plan.disruption else None,
            "original_route":plan.original_route.model_dump() if plan.original_route else None,
            "candidate_routes":[route.model_dump() for route in plan.candidate_routes],
            "selected_route":plan.selected_route.model_dump() if plan.selected_route else None,
            "delay_saved_hours":0,"additional_cost":round((plan.selected_route.cost-plan.original_route.cost),2) if plan.selected_route and plan.original_route else 0}


WEIGHTS={Priority.HIGH:(.60,.20,.15,.05),Priority.MEDIUM:(.45,.30,.15,.10),Priority.LOW:(.30,.45,.15,.10)}
def score_routes(routes: list[PathResult], priority: Priority) -> list[PathResult]:
    if not routes: return []
    maxima=[max(getattr(r,f) for r in routes) or 1 for f in ("duration_hours","cost","risk_score","capacity_penalty")]; w=WEIGHTS[priority]
    for route in routes: route.route_score=round(sum(a*b/c for a,b,c in zip(w,[route.duration_hours,route.cost,route.risk_score,route.capacity_penalty],maxima)),4)
    return sorted(routes,key=lambda r:r.route_score or 999)


def original_result(graph: nx.DiGraph, shipment: Shipment) -> PathResult | None: return path_result(graph,shipment.planned_route_location_ids,shipment.load_units)
def reserve(graph: nx.DiGraph, route: PathResult) -> None:
    for a,b in zip(route.location_ids,route.location_ids[1:]): graph[a][b]["route"].current_load+=0 # reserved externally by caller quantity is intentionally not inferred


def reroute(graph: nx.DiGraph, shipments: list[Shipment], baseline: nx.DiGraph | None = None, disruption_hours: float = 0) -> list[Recommendation]:
    results=[]
    for shipment in sorted(shipments,key=lambda s:{Priority.HIGH:0,Priority.MEDIUM:1,Priority.LOW:2}[s.priority]):
        original=original_result(baseline or graph,shipment); candidates=score_routes(find_candidate_routes(graph,shipment),shipment.priority)
        if not candidates: results.append(Recommendation(shipment_id=shipment.id,status="NO_FEASIBLE_ROUTE",original_route=original)); continue
        best=candidates[0]
        for a,b in zip(best.location_ids,best.location_ids[1:]): graph[a][b]["route"].current_load+=shipment.load_units
        disrupted_eta=(original.duration_hours + disruption_hours) if original else best.duration_hours
        results.append(Recommendation(shipment_id=shipment.id,status="REROUTED",original_route=original,candidate_routes=candidates,selected_route=best,delay_saved_hours=round(max(0,disrupted_eta-best.duration_hours),2),additional_cost=round(best.cost-(original.cost if original else best.cost),2)))
    return results


def metrics(recommendations: list[Recommendation]) -> dict:
    affected=len(recommendations); rerouted=[r for r in recommendations if r.status=="REROUTED"]
    return {"affected_shipments":affected,"successfully_rerouted":len(rerouted),"reroute_success_rate":round(len(rerouted)/affected,2) if affected else 0,"average_delay_saved_hours":round(sum(r.delay_saved_hours for r in rerouted)/len(rerouted),2) if rerouted else 0,"total_additional_cost":round(sum(r.additional_cost for r in rerouted),2),"average_route_risk":round(sum(r.selected_route.risk_score for r in rerouted)/len(rerouted),2) if rerouted else 0}


def decision_record(disruption: Disruption, shipment: Shipment, rec: Recommendation) -> dict:
    return {"disruption_id":disruption.id,"shipment_id":shipment.id,"status":rec.status,"original_route":rec.original_route.model_dump() if rec.original_route else None,"selected_route":rec.selected_route.model_dump() if rec.selected_route else None,"delay_saved_hours":rec.delay_saved_hours,"additional_cost":rec.additional_cost}


def validate_explanation(payload: dict, record: dict) -> dict:
    for key in ("delay_saved_hours","additional_cost"):
        if payload.get(key)!=record[key]: raise ValueError(f"LLM returned unsupported {key}")
    return payload
