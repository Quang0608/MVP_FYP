from datetime import datetime, timezone
from uuid import uuid4
import logging
from fastapi import FastAPI, HTTPException
from .data import seed_data, SCENARIOS
from .schemas import *
from .services import *
from .repository import initialise_database, save_run, get_run, all_runs
from .llm import explain

app=FastAPI(title="Autonomous Supply Chain Reroute Agent")
logger=logging.getLogger(__name__)
@app.on_event("startup")
def startup(): initialise_database()
def base():
    locations,routes,shipments=seed_data(); return locations,routes,shipments
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/locations",response_model=list[Location])
def locations(): return base()[0]
@app.get("/routes",response_model=list[Route])
def routes(): return base()[1]
@app.get("/shipments",response_model=list[Shipment])
def shipments(): return base()[2]
@app.get("/disruptions")
def disruptions(): return SCENARIOS
@app.post("/plan-route",response_model=RoutePlanResult)
def plan_route_endpoint(request: RoutePlanRequest):
    locations,routes,_=base()
    baseline=build_supply_chain_graph(locations,routes)
    active_locations,active_routes,_=base()
    graph=build_supply_chain_graph(active_locations,active_routes)
    if request.disruption: apply_disruption(graph,request.disruption)
    result=plan_route(graph,request,baseline)
    if result.status=="ROUTE_FOUND" and request.generate_explanation:
        logger.info("Generating OpenAI analysis for interactive route %s → %s",request.origin_id,request.destination_id)
        try: result.explanation=explain(route_plan_decision_record(result))
        except Exception as exc:
            logger.exception("Interactive route explanation failed")
            raise HTTPException(status_code=502,detail=f"OpenAI explanation failed: {exc}") from exc
    return result
@app.post("/simulate-disruption",response_model=SimulationResult)
def simulate(request: DisruptionRequest):
    locations,routes,shipments=base(); graph=build_supply_chain_graph(locations,routes); apply_disruption(graph,request); affected=find_affected_shipments(shipments,request); disruption=Disruption(id=str(uuid4()),request=request,created_at=datetime.now(timezone.utc)); result=SimulationResult(disruption_id=disruption.id,affected_shipments=affected,downstream_impacts=find_downstream_impacts(graph,request.affected_location_ids)); save_run(disruption.id,disruption.model_dump(mode="json"),result.model_dump(mode="json")); return result
@app.post("/reroute")
def reroute_endpoint(disruption_id: str):
    stored=get_run(disruption_id)
    if not stored: raise HTTPException(404,"Disruption not found")
    disruption=Disruption.model_validate(stored["disruption"]); locations,routes,shipments=base(); baseline=build_supply_chain_graph(locations,routes); active_locations,active_routes,_=base(); graph=build_supply_chain_graph(active_locations,active_routes); apply_disruption(graph,disruption.request); affected=find_affected_shipments(shipments,disruption.request); recs=reroute(graph,affected,baseline,disruption.request.duration_hours)
    result={"disruption_id":disruption_id,"recommendations":[r.model_dump(mode="json") for r in recs],"metrics":metrics(recs)}; save_run(disruption_id,disruption.model_dump(mode="json"),result); return result
@app.post("/shipment-analytics",response_model=ShipmentAnalyticsResult)
def shipment_analytics(request: ShipmentAnalyticsRequest):
    """Generate LLM analytics for exactly one user-selected affected shipment."""
    stored=get_run(request.disruption_id)
    if not stored: raise HTTPException(404,"Disruption not found")
    disruption=Disruption.model_validate(stored["disruption"])
    locations,routes,shipments=base(); baseline=build_supply_chain_graph(locations,routes)
    active_locations,active_routes,_=base(); graph=build_supply_chain_graph(active_locations,active_routes)
    apply_disruption(graph,disruption.request)
    affected=find_affected_shipments(shipments,disruption.request)
    rec=next((item for item in reroute(graph,affected,baseline,disruption.request.duration_hours) if item.shipment_id==request.shipment_id),None)
    shipment=next((item for item in shipments if item.id==request.shipment_id),None)
    if rec is None or shipment is None: raise HTTPException(404,"Affected shipment not found")
    logger.info("Generating OpenAI impact analytics for shipment %s",request.shipment_id)
    try: analytics=explain(decision_record(disruption,shipment,rec))
    except Exception as exc:
        logger.exception("Shipment analytics failed for %s",request.shipment_id)
        raise HTTPException(status_code=502,detail=f"OpenAI analytics failed: {exc}") from exc
    return ShipmentAnalyticsResult(disruption_id=request.disruption_id,shipment_id=request.shipment_id,status=rec.status,analytics=analytics)
@app.get("/recommendations")
def recommendations(): return all_runs()
@app.get("/metrics")
def metric_history(): return [{"id":r["id"],"metrics":r["results"].get("metrics")} for r in all_runs()]
