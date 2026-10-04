import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .data import SCENARIOS
from .config import settings
from .schemas import *
from .domain import Location as CanonicalLocation, Route as CanonicalRoute
from .integrations.portwatch import PortWatchAdapter
from .external_state import (
    ExternalExposureResult,
    ExternalSignal,
    SignalNetworkMatch,
    find_shipments_exposed,
    get_network_zones,
)
from .external_state.matcher import match_signal_to_network
from .disruption_policy import (
    canonical_disruptions_from_external,
    canonical_disruptions_from_request,
)
from .impact import reroute_required_shipments
from .network_state import NetworkStateEngine
from .runtime_identity import (
    canonical_location_id,
    canonicalize_disruption_request,
    canonicalize_route_plan_request,
)
from .agent.assistant import build_assistant_context
from .agent.schemas import SupervisorRequest, SupervisorResponse
from .agent.supervisor import run_supervisor
from .api.serializers import location_response, route_response, shipment_response
from .services import (
    build_supply_chain_graph,
    decision_record,
    detect_external_impacts,
    metrics,
    plan_route,
    reroute,
    route_plan_decision_record,
)
from .repository import (
    all_runs,
    get_run,
    initialise_database,
    load_runtime_dataset,
    save_agent_decisions,
    save_decision_explanation,
)
from .llm import answer_question, explain
from .simulation_service import load_runtime_snapshot, run_simulation
from .integrations.weather import (
    ForecastWindow,
    InvalidWeatherRequest,
    InvalidWeatherResponse,
    SnapshotPersistenceError,
    UnsupportedWeatherRoute,
    WeatherCacheError,
    WeatherProviderError,
    WeatherProviderTimeout,
    WeatherProviderUnavailable,
    WeatherRateLimited,
)
from .integrations.weather.runtime import build_weather_service

allowed_cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]
app=FastAPI(title="Autonomous Supply Chain Reroute Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger=logging.getLogger(__name__)
@app.on_event("startup")
def startup(): initialise_database()
def portwatch_adapter() -> PortWatchAdapter:
    return PortWatchAdapter.from_settings(settings)


def runtime_data():
    dataset = load_runtime_dataset()
    adapter = portwatch_adapter()
    portwatch_state = adapter.runtime_port_state()
    return (
        adapter.enrich_locations(dataset.locations),
        dataset.routes,
        dataset.shipments,
        portwatch_state,
    )


def base():
    locations, routes, shipments, _ = runtime_data()
    return locations, routes, shipments


def scenario_graph(
    locations,
    routes,
    disruptions=(),
    portwatch_state=None,
):
    state = NetworkStateEngine().build(locations, routes, disruptions)
    graph = build_supply_chain_graph(
        locations,
        routes,
        portwatch_state,
        network_state=state,
    )
    return state, graph
def validate_disruption_references(
    request: DisruptionRequest,
    locations: list[CanonicalLocation],
    routes: list[CanonicalRoute],
) -> None:
    known_location_ids = {location.location_id for location in locations}
    known_route_ids = {route.route_id for route in routes}
    unknown_location_ids = sorted(
        set(request.affected_location_ids) - known_location_ids
    )
    unknown_route_ids = sorted(set(request.affected_route_ids) - known_route_ids)
    if unknown_location_ids or unknown_route_ids:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Disruption references unknown network identifiers.",
                "unknown_location_ids": unknown_location_ids,
                "unknown_route_ids": unknown_route_ids,
            },
        )
@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/assistant",response_model=AssistantResponse)
def assistant(request: AssistantRequest):
    """Answer from a server-reconstructed run or transitional client context."""
    try:
        context = build_assistant_context(request)
        return answer_question(request.question, context)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Dashboard assistant failed")
        raise HTTPException(status_code=502, detail="Dashboard assistant unavailable") from exc


@app.post("/supervisor", response_model=SupervisorResponse)
def supervisor(request: SupervisorRequest):
    """Run the bounded tool-using Supervisor over trusted backend services."""

    try:
        return run_supervisor(request)
    except Exception as exc:
        logger.exception("Supervisor request failed")
        raise HTTPException(status_code=502, detail="Supervisor unavailable") from exc
@app.get("/locations",response_model=list[Location])
def locations(): return [location_response(location) for location in base()[0]]
@app.get("/locations/{location_id}",response_model=Location)
def location_detail(location_id: str):
    location_id = canonical_location_id(location_id)
    location = next(
        (item for item in base()[0] if item.location_id == location_id), None
    )
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return location_response(location)
@app.get("/routes",response_model=list[Route])
def routes(): return [route_response(route) for route in base()[1]]


@app.get("/weather/routes/{route_id}/raw")
def weather_route_raw(
    route_id: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
):
    """Fetch raw weather internally and return only a debug retrieval summary."""

    if not settings.open_meteo_enabled:
        raise HTTPException(status_code=503, detail="Open-Meteo integration is disabled")
    snapshot = load_runtime_snapshot()
    service = build_weather_service(snapshot.routes, settings)
    try:
        try:
            window = ForecastWindow(start_time=start_time, end_time=end_time)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        result = service.get_route_weather_raw(route_id, window)
        return result.summary()
    except UnsupportedWeatherRoute as exc:
        status_code = 404 if route_id not in {route.route_id for route in snapshot.routes} else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except InvalidWeatherRequest as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WeatherProviderTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except WeatherRateLimited as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except (WeatherProviderUnavailable, InvalidWeatherResponse) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (WeatherCacheError, SnapshotPersistenceError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except WeatherProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        service.close()


@app.get("/shipments",response_model=list[Shipment])
def shipments(): return [shipment_response(shipment) for shipment in base()[2]]
@app.get("/network/corridors")
def network_corridors():
    """Return curated corridor/chokepoint metadata for matching clients."""

    return get_network_zones()
@app.post("/external-signals/network-match", response_model=SignalNetworkMatch)
def external_signal_network_match(signal: ExternalSignal):
    """Match synthetic/provider-shaped evidence without persisting or applying it."""

    snapshot = load_runtime_snapshot()
    return match_signal_to_network(signal, snapshot.locations, snapshot.routes)
@app.post("/external-signals/exposure", response_model=ExternalExposureResult)
def external_signal_exposure(signal: ExternalSignal):
    """Return deterministic remaining-leg exposure evidence only."""

    snapshot = load_runtime_snapshot()
    return find_shipments_exposed(
        signal,
        snapshot.shipments,
        snapshot.routes,
        snapshot.locations,
    )
@app.get("/disruptions")
def disruptions(): return SCENARIOS
@app.get("/portwatch/disruptions")
def portwatch_disruptions():
    return portwatch_adapter().get_active_disruptions()
@app.get("/portwatch/impacts", response_model=list[ExternalImpactEvidence])
def portwatch_impacts():
    locations, routes, shipments, portwatch_state = runtime_data()
    impacts = []
    for disruption in portwatch_adapter().get_active_disruptions():
        events = canonical_disruptions_from_external(disruption)
        state, graph = scenario_graph(
            locations,
            routes,
            events,
            portwatch_state,
        )
        impacts.extend(
            detect_external_impacts(disruption, shipments, graph, state)
        )
    return impacts
@app.get("/portwatch/state")
def portwatch_state():
    return portwatch_adapter().runtime_port_state()
@app.post("/plan-route",response_model=RoutePlanResult)
def plan_route_endpoint(request: RoutePlanRequest):
    request = canonicalize_route_plan_request(request)
    locations, routes, _, portwatch_state = runtime_data()
    if request.disruption:
        validate_disruption_references(request.disruption, locations, routes)
    events = (
        canonical_disruptions_from_request(request.disruption)
        if request.disruption
        else []
    )
    _, baseline = scenario_graph(locations, routes, (), portwatch_state)
    _, graph = scenario_graph(locations, routes, events, portwatch_state)
    result = plan_route(graph, request, baseline)
    if result.status=="ROUTE_FOUND" and request.generate_explanation:
        logger.info("Generating OpenAI analysis for interactive route %s → %s",request.origin_id,request.destination_id)
        try: result.explanation=explain(route_plan_decision_record(result))
        except Exception as exc:
            logger.exception("Interactive route explanation failed")
            raise HTTPException(status_code=502,detail=f"OpenAI explanation failed: {exc}") from exc
    return result
@app.post("/simulate-disruption",response_model=SimulationResult)
def simulate(request: DisruptionRequest):
    request = canonicalize_disruption_request(request)
    snapshot = load_runtime_snapshot()
    validate_disruption_references(request, snapshot.locations, snapshot.routes)
    execution = run_simulation(
        request,
        snapshot=snapshot,
    )
    return execution.result
@app.post("/reroute")
def reroute_endpoint(disruption_id: str):
    stored = get_run(disruption_id)
    if not stored:
        raise HTTPException(404, "Disruption not found")
    disruption = Disruption.model_validate(stored["disruption"])
    locations, routes, shipments, portwatch_state = runtime_data()
    events = canonical_disruptions_from_request(
        disruption.request,
        disruption_id=disruption.id,
        start_time=disruption.created_at,
    )
    baseline = build_supply_chain_graph(locations, routes, portwatch_state)
    state, graph = scenario_graph(
        locations,
        routes,
        events,
        portwatch_state,
    )
    affected, shipment_impacts = reroute_required_shipments(shipments, state)
    recommendations = reroute(
        graph,
        affected,
        baseline,
        disruption.request.duration_hours,
    )
    result = {
        "disruption_id": disruption_id,
        "recommendations": [
            recommendation.model_dump(mode="json")
            for recommendation in recommendations
        ],
        "metrics": metrics(recommendations),
        "shipment_impacts": [
            impact.model_dump(mode="json") for impact in shipment_impacts
        ],
    }
    save_agent_decisions(disruption_id, result)
    return result
@app.post("/shipment-analytics",response_model=ShipmentAnalyticsResult)
def shipment_analytics(request: ShipmentAnalyticsRequest):
    """Generate LLM analytics for exactly one user-selected affected shipment."""
    stored=get_run(request.disruption_id)
    if not stored: raise HTTPException(404,"Disruption not found")
    disruption=Disruption.model_validate(stored["disruption"])
    locations, routes, shipments, portwatch_state = runtime_data()
    events = canonical_disruptions_from_request(
        disruption.request,
        disruption_id=disruption.id,
        start_time=disruption.created_at,
    )
    _, baseline = scenario_graph(locations, routes, (), portwatch_state)
    state, graph = scenario_graph(
        locations,
        routes,
        events,
        portwatch_state,
    )
    affected, _ = reroute_required_shipments(shipments, state)
    rec=next((item for item in reroute(graph,affected,baseline,disruption.request.duration_hours) if item.shipment_id==request.shipment_id),None)
    shipment=next((item for item in shipments if item.id==request.shipment_id),None)
    if rec is None or shipment is None: raise HTTPException(404,"Affected shipment not found")
    logger.info("Generating OpenAI impact analytics for shipment %s",request.shipment_id)
    try: analytics=explain(decision_record(disruption,shipment,rec))
    except Exception as exc:
        logger.exception("Shipment analytics failed for %s",request.shipment_id)
        raise HTTPException(status_code=502,detail=f"OpenAI analytics failed: {exc}") from exc
    save_decision_explanation(request.disruption_id,request.shipment_id,analytics)
    return ShipmentAnalyticsResult(disruption_id=request.disruption_id,shipment_id=request.shipment_id,status=rec.status,analytics=analytics)
@app.get("/recommendations")
def recommendations(): return all_runs()
@app.get("/metrics")
def metric_history(): return [{"id":r["id"],"metrics":r["results"].get("metrics")} for r in all_runs()]
