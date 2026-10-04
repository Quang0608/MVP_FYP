from __future__ import annotations
import json
import networkx as nx
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Mapping

from .schemas import *
from .domain import Location, Route, Shipment
from .graph import apply_disruption, build_supply_chain_graph
from .impact import classify_shipment_impacts
from .network_state import NetworkState


def find_portwatch_affected_shipments(
    shipments: list[Shipment],
    portwatch_state: Mapping[str, Mapping[str, object]],
) -> list[Shipment]:
    """Return shipments whose planned routes contain an activity-flagged port.

    PortWatch activity flags are candidates for later impact analysis. They do
    not block routes, change weights, or prove congestion by themselves.
    """

    flagged_ports = {
        location_id
        for location_id, state in portwatch_state.items()
        if state.get("operational_status") in {"HIGH_ACTIVITY", "LOW_ACTIVITY"}
    }
    return [
        shipment
        for shipment in shipments
        if flagged_ports.intersection(shipment.remaining_route_location_ids())
    ]


def _remaining_route_locations(shipment: Shipment) -> list[str]:
    """Return the shipment route from its current location onward."""

    return shipment.remaining_route_location_ids()


class ImpactDetectionService:
    """Detect deterministic shipment impacts from canonical external events."""

    INACTIVE_STATUSES = {"DELIVERED", "CANCELLED", "COMPLETED"}

    @classmethod
    def detect_external_impacts(
        cls,
        disruption: Mapping[str, object],
        shipments: list[Shipment],
        graph: nx.DiGraph,
    ) -> list[dict[str, object]]:
        event_id = str(disruption.get("event_id", ""))
        affected_ids = disruption.get("affected_location_ids", []) or []
        canonical_to_runtime: dict[str, list[str]] = {}
        for runtime_id, data in graph.nodes(data=True):
            canonical_id = data.get("canonical_location_id") or runtime_id
            canonical_to_runtime.setdefault(str(canonical_id), []).append(str(runtime_id))

        evidence: list[dict[str, object]] = []
        for affected_id in affected_ids:
            canonical_id = str(affected_id)
            runtime_ids = canonical_to_runtime.get(canonical_id, [])
            if not runtime_ids and canonical_id in graph:
                runtime_ids = [canonical_id]
            if not runtime_ids:
                continue
            runtime_id_set = set(runtime_ids)
            affected_shipments = [
                shipment.id
                for shipment in shipments
                if shipment.status.upper() not in cls.INACTIVE_STATUSES
                and runtime_id_set.intersection(_remaining_route_locations(shipment))
            ]
            if not affected_shipments:
                continue
            evidence.append(
                {
                    "event_id": event_id,
                    "affected_location": runtime_ids[0],
                    "canonical_location_id": canonical_id,
                    "affected_shipments": affected_shipments,
                    "reason": "remaining route contains disrupted port",
                    "source": str(disruption.get("source") or "PORTWATCH"),
                }
            )
        return evidence


def detect_external_impacts(
    disruption: Mapping[str, object],
    shipments: list[Shipment],
    graph: nx.DiGraph,
    network_state: NetworkState | None = None,
) -> list[dict[str, object]]:
    """Functional wrapper for external impact evidence and classification."""

    if network_state is None:
        return ImpactDetectionService.detect_external_impacts(
            disruption, shipments, graph
        )

    classifications = {
        impact.shipment_id: impact
        for impact in classify_shipment_impacts(shipments, network_state)
    }
    event_id = str(disruption.get("event_id", ""))
    affected_ids = disruption.get("affected_location_ids", []) or []
    canonical_to_runtime: dict[str, list[str]] = {}
    for runtime_id, data in graph.nodes(data=True):
        canonical_id = data.get("canonical_location_id") or runtime_id
        canonical_to_runtime.setdefault(str(canonical_id), []).append(str(runtime_id))

    evidence: list[dict[str, object]] = []
    for affected_id in affected_ids:
        runtime_ids = canonical_to_runtime.get(str(affected_id), [])
        if not runtime_ids and str(affected_id) in graph:
            runtime_ids = [str(affected_id)]
        runtime_id_set = set(runtime_ids)
        matching = []
        matching_classifications = []
        for shipment in shipments:
            if not runtime_id_set.intersection(
                shipment.remaining_route_location_ids()
            ):
                continue
            impact = classifications[shipment.shipment_id]
            if impact.classification == ImpactClassification.UNAFFECTED:
                continue
            matching.append(shipment.shipment_id)
            matching_classifications.append(impact.classification)
        if not matching:
            continue
        classification = _highest_impact_classification(matching_classifications)
        evidence.append(
            {
                "event_id": event_id,
                "affected_location": runtime_ids[0] if runtime_ids else str(affected_id),
                "canonical_location_id": str(affected_id),
                "affected_shipments": matching,
                "reason": "remaining route contains disrupted port",
                "source": str(disruption.get("source") or "PORTWATCH"),
                "classification": classification,
            }
        )
    return evidence


def _highest_impact_classification(
    classifications: list[ImpactClassification],
) -> ImpactClassification:
    priority = {
        ImpactClassification.REROUTE_REQUIRED: 3,
        ImpactClassification.SHIPMENT_AT_RISK: 2,
        ImpactClassification.NETWORK_WARNING: 1,
        ImpactClassification.UNAFFECTED: 0,
    }
    return max(classifications, key=lambda item: priority[item])


def find_affected_shipments(shipments: list[Shipment], disruption: DisruptionRequest) -> list[Shipment]:
    nodes = set(disruption.affected_location_ids)
    routes = set(disruption.affected_route_ids)
    return [
        shipment
        for shipment in shipments
        if nodes.intersection(shipment.remaining_route_location_ids())
        or routes.intersection(shipment.remaining_route_ids())
    ]


def find_downstream_impacts(graph: nx.DiGraph, disrupted_location_ids: list[str]) -> list[Location]:
    output={}
    for source in disrupted_location_ids:
        if source not in graph: continue
        for node in nx.descendants(graph,source):
            loc=graph.nodes[node]["location"]
            if loc.type in {LocationType.WAREHOUSE,LocationType.CUSTOMER}: output[node]=loc
    return list(output.values())


def path_result(graph: nx.DiGraph, nodes: list[str], load: float) -> PathResult | None:
    edges = []
    for source, destination in zip(nodes, nodes[1:]):
        if not graph.has_edge(source, destination):
            return None
        edge = graph[source][destination]
        if not edge.get("available", edge["status"] != Status.BLOCKED):
            return None
        edges.append(edge)
    feasible = all(
        edge["current_load"] + load <= edge["capacity"] for edge in edges
    )
    penalty = sum(
        (edge["current_load"] + load) / max(1, edge["capacity"])
        for edge in edges
    ) / max(1, len(edges))
    return PathResult(
        location_ids=nodes,
        route_ids=[edge["route_id"] for edge in edges],
        duration_hours=sum(edge["duration"] for edge in edges),
        cost=sum(edge["cost"] for edge in edges),
        risk_score=sum(edge["risk"] for edge in edges) / max(1, len(edges)),
        capacity_feasible=feasible,
        capacity_penalty=penalty,
    )


def find_candidate_routes(graph: nx.DiGraph, shipment: Shipment, k: int=3) -> list[PathResult]:
    active = graph.copy()
    active.remove_edges_from(
        [
            (source, destination)
            for source, destination, data in active.edges(data=True)
            if not data.get("available", data["status"] != Status.BLOCKED)
        ]
    )
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
    query = Shipment(
        shipment_id="INTERACTIVE",
        origin_location_id=request.origin_id,
        destination_location_id=request.destination_id,
        current_location_id=request.origin_id,
        priority=request.priority,
        required_delivery_time=datetime.now(timezone.utc),
        current_eta=datetime.now(timezone.utc),
        load_units=request.load_units,
    )
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


def original_result(graph: nx.DiGraph, shipment: Shipment) -> PathResult | None:
    return path_result(
        graph, shipment.remaining_route_location_ids(), shipment.load_units
    )
def reserve(graph: nx.DiGraph, route: PathResult) -> None:
    for source, destination in zip(route.location_ids, route.location_ids[1:]):
        graph[source][destination]["current_load"] += 0


def reroute(graph: nx.DiGraph, shipments: list[Shipment], baseline: nx.DiGraph | None = None, disruption_hours: float = 0) -> list[Recommendation]:
    results=[]
    for shipment in sorted(shipments,key=lambda s:{Priority.HIGH:0,Priority.MEDIUM:1,Priority.LOW:2}[s.priority]):
        original=original_result(baseline or graph,shipment); candidates=score_routes(find_candidate_routes(graph,shipment),shipment.priority)
        if not candidates: results.append(Recommendation(shipment_id=shipment.id,status="NO_FEASIBLE_ROUTE",original_route=original)); continue
        best=candidates[0]
        for source, destination in zip(best.location_ids, best.location_ids[1:]):
            edge = graph[source][destination]
            edge["current_load"] += shipment.load_units
            edge["route"].current_load = edge["current_load"]
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
