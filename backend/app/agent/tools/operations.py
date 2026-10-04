"""Thin, structured wrappers around trusted deterministic application services."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ...config import settings
from ...domain import Location, LocationType, Priority, Shipment
from ...impact import classify_shipment_impacts
from ...integrations.portwatch import PortWatchAdapter
from ...runtime_identity import canonical_location_id
from ...schemas import DisruptionRequest, DisruptionType, ImpactClassification
from ...services import find_candidate_routes, original_result, path_result, score_routes
from ...simulation_service import (
    SimulationContext,
    load_runtime_snapshot,
    load_simulation_context,
    run_simulation,
)
from ...repository import all_runs
from ..schemas import (
    ActiveDisruptionSummary,
    AffectedShipmentsInput,
    AffectedShipmentsOutput,
    CandidateRoutesInput,
    LocationMatch,
    LocationResolution,
    RouteComparisonOutput,
    RouteConstraints,
    RouteOption,
    ShipmentFilterInput,
    ShipmentImpactOutput,
    ShipmentLegSummary,
    ShipmentRouteOutput,
    ShipmentSimulationInput,
    ShipmentSummary,
    SimulateDisruptionInput,
    SimulateDisruptionOutput,
    SimulationInput,
    SimulationSummary,
    ValidationOutput,
    ValidateRouteCandidateInput,
)


MAX_TOOL_RECORDS = 50


class AgentToolError(ValueError):
    """Safe, user-facing failure from a trusted tool."""

    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _location_map(context: SimulationContext | None = None) -> dict[str, Location]:
    locations = context.snapshot.locations if context else load_runtime_snapshot().locations
    return {location.location_id: location for location in locations}


def _location_name(location_id: str, locations: dict[str, Location]) -> str:
    location = locations.get(location_id)
    return location.name if location else location_id


def _shipment_or_error(shipment_id: str, context: SimulationContext | None = None) -> Shipment:
    shipments = context.snapshot.shipments if context else load_runtime_snapshot().shipments
    shipment = next((item for item in shipments if item.shipment_id == shipment_id), None)
    if shipment is None:
        raise AgentToolError("UNKNOWN_SHIPMENT", f"Shipment {shipment_id} was not found.")
    return shipment


def _shipment_summary(shipment: Shipment, locations: dict[str, Location]) -> ShipmentSummary:
    return ShipmentSummary(
        shipment_id=shipment.shipment_id,
        priority=shipment.priority,
        status=shipment.status,
        origin_location_id=shipment.origin_location_id,
        origin_name=_location_name(shipment.origin_location_id, locations),
        destination_location_id=shipment.destination_location_id,
        destination_name=_location_name(shipment.destination_location_id, locations),
        current_location_id=shipment.current_location_id,
        current_location_name=_location_name(shipment.current_location_id, locations),
        cargo_type=shipment.cargo_type,
        load_units=shipment.load_units,
        required_delivery_time=shipment.required_delivery_time,
        current_eta=shipment.current_eta,
    )


def get_shipment(shipment_id: str) -> ShipmentSummary:
    snapshot = load_runtime_snapshot()
    shipment = _shipment_or_error(shipment_id)
    return _shipment_summary(shipment, {item.location_id: item for item in snapshot.locations})


def get_shipments(filters: ShipmentFilterInput) -> list[ShipmentSummary]:
    context = (
        load_simulation_context(filters.simulation_run_id)
        if filters.simulation_run_id
        else None
    )
    snapshot = context.snapshot if context else load_runtime_snapshot()
    locations = {item.location_id: item for item in snapshot.locations}
    impacts = {}
    if filters.affected is not None:
        if context is None:
            raise AgentToolError(
                "SIMULATION_REQUIRED",
                "affected filtering requires simulation_run_id.",
            )
        impacts = {
            impact.shipment_id: impact
            for impact in classify_shipment_impacts(snapshot.shipments, context.state)
        }
    selected = []
    for shipment in snapshot.shipments:
        if filters.shipment_id and shipment.shipment_id != filters.shipment_id:
            continue
        if filters.priority and shipment.priority != filters.priority:
            continue
        if filters.status and shipment.status.upper() != filters.status.upper():
            continue
        if filters.origin_location_id and shipment.origin_location_id != filters.origin_location_id:
            continue
        if filters.destination_location_id and shipment.destination_location_id != filters.destination_location_id:
            continue
        if filters.affected is not None:
            is_affected = impacts[shipment.shipment_id].classification != ImpactClassification.UNAFFECTED
            if is_affected != filters.affected:
                continue
        selected.append(_shipment_summary(shipment, locations))
        if len(selected) >= filters.limit:
            break
    return selected


def get_shipment_route(request: ShipmentSimulationInput | str) -> ShipmentRouteOutput:
    shipment_id = request if isinstance(request, str) else request.shipment_id
    snapshot = load_runtime_snapshot()
    shipment = _shipment_or_error(shipment_id)
    locations = {item.location_id: item for item in snapshot.locations}
    legs = [
        ShipmentLegSummary(
            sequence_no=leg.sequence_no,
            route_id=leg.route_id,
            source_location_id=leg.source_location_id,
            source_name=_location_name(leg.source_location_id, locations),
            destination_location_id=leg.destination_location_id,
            destination_name=_location_name(leg.destination_location_id, locations),
            status=leg.status,
            transport_mode=leg.transport_mode,
            planned_departure=leg.planned_departure,
            planned_arrival=leg.planned_arrival,
        )
        for leg in shipment.ordered_route_legs
    ]
    return ShipmentRouteOutput(
        shipment_id=shipment.shipment_id,
        current_location_id=shipment.current_location_id,
        current_location_name=_location_name(shipment.current_location_id, locations),
        remaining_leg_count=len(shipment.remaining_route_legs()),
        legs=legs,
    )


def _normalise_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def resolve_location(name_or_id: str) -> LocationResolution:
    query = name_or_id.strip()
    if not query:
        raise AgentToolError("INVALID_LOCATION_QUERY", "A location name or ID is required.")
    locations = load_runtime_snapshot().locations
    canonical_id = canonical_location_id(query)
    direct = [
        location
        for location in locations
        if location.location_id == query
        or location.location_id == canonical_id
        or location.canonical_location_id == query
    ]
    if len(direct) == 1:
        location = direct[0]
        return LocationResolution(
            query=query,
            resolved=_location_match(location, 100),
            matches=[_location_match(location, 100)],
        )

    query_tokens = set(_normalise_text(query).split())
    scored: list[tuple[int, Location]] = []
    for location in locations:
        name_tokens = set(_normalise_text(location.name).split())
        country_tokens = set(_normalise_text(location.country).split())
        if not query_tokens.intersection(name_tokens | country_tokens):
            continue
        score = 0
        if query_tokens.issubset(name_tokens):
            score += 80
        elif query_tokens.intersection(name_tokens):
            score += 50
        if query_tokens.intersection(country_tokens):
            score += 20
        if "port" in query_tokens and location.location_type == LocationType.PORT:
            score += 20
        scored.append((score, location))
    scored.sort(key=lambda item: (-item[0], item[1].location_id))
    matches = [_location_match(location, score) for score, location in scored[:MAX_TOOL_RECORDS]]
    if not matches:
        return LocationResolution(query=query)
    top_score = matches[0].score
    top_matches = [match for match in matches if match.score == top_score]
    if len(top_matches) == 1:
        return LocationResolution(query=query, resolved=top_matches[0], matches=matches)
    return LocationResolution(query=query, matches=matches, ambiguous=True)


def _location_match(location: Location, score: int) -> LocationMatch:
    return LocationMatch(
        location_id=location.location_id,
        name=location.name,
        location_type=location.location_type.value,
        country=location.country,
        source=location.source,
        score=score,
    )


def get_active_disruptions() -> list[ActiveDisruptionSummary]:
    now = datetime.now(timezone.utc)
    output: list[ActiveDisruptionSummary] = []
    for run in all_runs():
        request = run.get("disruption") or {}
        created = run.get("created_at")
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        duration = int(request.get("duration_hours", 0))
        if created and created + timedelta(hours=duration) < now:
            continue
        location_ids = request.get("affected_location_ids") or []
        route_ids = request.get("affected_route_ids") or []
        if location_ids:
            for location_id in location_ids:
                output.append(
                    ActiveDisruptionSummary(
                        disruption_id=run["id"],
                        disruption_type=str(request.get("disruption_type", "UNKNOWN")),
                        target_type="LOCATION",
                        target_id=location_id,
                        severity=str(request.get("severity", "HIGH")),
                        duration_hours=duration,
                        source="SIMULATED",
                        status="ACTIVE",
                        created_at=created,
                    )
                )
        for route_id in route_ids:
            output.append(
                ActiveDisruptionSummary(
                    disruption_id=run["id"],
                    disruption_type=str(request.get("disruption_type", "UNKNOWN")),
                    target_type="ROUTE",
                    target_id=route_id,
                    severity=str(request.get("severity", "HIGH")),
                    duration_hours=duration,
                    source="SIMULATED",
                    status="ACTIVE",
                    created_at=created,
                )
            )
    for record in PortWatchAdapter.from_settings(settings).get_active_disruptions():
        start_time = record.get("start_time")
        created_at = None
        if start_time:
            if isinstance(start_time, str):
                created_at = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            elif isinstance(start_time, datetime):
                created_at = start_time
            if created_at is not None and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        affected_location_ids = record.get("affected_location_ids") or []
        for location_id in affected_location_ids:
            output.append(
                ActiveDisruptionSummary(
                    disruption_id=str(record.get("event_id", "PORTWATCH")),
                    disruption_type=str(record.get("event_type") or "NETWORK_WARNING"),
                    target_type="LOCATION",
                    target_id=str(location_id),
                    severity=str(
                        record.get("severity_text")
                        or record.get("alert_level")
                        or "MEDIUM"
                    ),
                    duration_hours=0,
                    source="PORTWATCH",
                    status="ACTIVE",
                    created_at=created_at,
                )
            )
    return output[:MAX_TOOL_RECORDS]


def get_disruption(request: SimulationInput) -> SimulationSummary:
    return get_simulation(request)


def get_simulation(request: SimulationInput) -> SimulationSummary:
    context = load_simulation_context(request.simulation_run_id)
    impacts = classify_shipment_impacts(context.snapshot.shipments, context.state)
    counts: dict[str, int] = {}
    for impact in impacts:
        counts[impact.classification.value] = counts.get(impact.classification.value, 0) + 1
    available = sum(1 for edge in context.state.edges.values() if edge.available)
    return SimulationSummary(
        simulation_run_id=request.simulation_run_id,
        disruption_type=context.request.disruption_type.value,
        affected_location_ids=context.request.affected_location_ids,
        affected_route_ids=context.request.affected_route_ids,
        severity=context.request.severity,
        duration_hours=context.request.duration_hours,
        affected_shipment_count=sum(
            count for key, count in counts.items() if key != ImpactClassification.UNAFFECTED.value
        ),
        impact_counts=counts,
        available_route_count=available,
        unavailable_route_count=len(context.state.edges) - available,
        created_at=context.disruption.created_at,
    )


def get_scenario_network_summary(request: SimulationInput) -> SimulationSummary:
    return get_simulation(request)


def _impact_output(context: SimulationContext, shipment: Shipment, impact) -> ShipmentImpactOutput:
    locations = {item.location_id: item for item in context.snapshot.locations}
    return ShipmentImpactOutput(
        simulation_run_id=context.disruption.id,
        shipment=_shipment_summary(shipment, locations),
        classification=impact.classification,
        reason=impact.reason,
        affected_location_ids=impact.affected_location_ids,
        affected_route_ids=impact.affected_route_ids,
        route_feasible=impact.route_feasible,
        baseline_duration_hours=impact.baseline_duration_hours,
        effective_duration_hours=impact.effective_duration_hours,
        baseline_risk_score=impact.baseline_risk_score,
        effective_risk_score=impact.effective_risk_score,
    )


def get_affected_shipments(request: AffectedShipmentsInput) -> AffectedShipmentsOutput:
    context = load_simulation_context(request.simulation_run_id)
    shipments = {shipment.shipment_id: shipment for shipment in context.snapshot.shipments}
    priority = getattr(request, "priority", None)
    limit = getattr(request, "limit", MAX_TOOL_RECORDS)
    outputs = [
        _impact_output(context, shipments[impact.shipment_id], impact)
        for impact in classify_shipment_impacts(context.snapshot.shipments, context.state)
        if impact.classification != ImpactClassification.UNAFFECTED
        and (
            priority is None
            or shipments[impact.shipment_id].priority == priority
        )
    ]
    return AffectedShipmentsOutput(
        simulation_run_id=request.simulation_run_id,
        total=len(outputs),
        shipments=outputs[:limit],
    )


def get_shipment_impact(request: ShipmentSimulationInput) -> ShipmentImpactOutput:
    context = load_simulation_context(request.simulation_run_id)
    shipment = _shipment_or_error(request.shipment_id, context)
    impact = next(
        item
        for item in classify_shipment_impacts(context.snapshot.shipments, context.state)
        if item.shipment_id == request.shipment_id
    )
    return _impact_output(context, shipment, impact)


def _normalise_datetime(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _route_option(
    path,
    shipment: Shipment,
    locations: dict[str, Location],
    original=None,
) -> RouteOption:
    eta = _normalise_datetime(shipment.current_eta) + timedelta(hours=path.duration_hours)
    deadline = _normalise_datetime(shipment.required_delivery_time)
    return RouteOption(
        route_ids=path.route_ids,
        location_ids=path.location_ids,
        location_names=[_location_name(identifier, locations) for identifier in path.location_ids],
        duration_hours=path.duration_hours,
        duration_delta_hours=(
            path.duration_hours - original.duration_hours if original else None
        ),
        cost=path.cost,
        cost_delta=path.cost - original.cost if original else None,
        risk_score=path.risk_score,
        capacity_feasible=path.capacity_feasible,
        capacity_penalty=path.capacity_penalty,
        sla_met=eta <= deadline,
        route_score=path.route_score,
        validation_status="VALID" if path.capacity_feasible else "INFEASIBLE_CAPACITY",
    )


def _candidate_paths(context: SimulationContext, shipment: Shipment, limit: int):
    return score_routes(
        find_candidate_routes(context.graph, shipment, k=limit),
        shipment.priority,
    )


def _filter_constraints(paths, constraints: RouteConstraints | None):
    if constraints is None:
        return paths
    return [
        path
        for path in paths
        if (
            constraints.max_duration_hours is None
            or path.duration_hours <= constraints.max_duration_hours
        )
        and (constraints.max_cost is None or path.cost <= constraints.max_cost)
        and (
            constraints.max_risk_score is None
            or path.risk_score <= constraints.max_risk_score
        )
    ]


def get_route_comparison(request: ShipmentSimulationInput) -> RouteComparisonOutput:
    context = load_simulation_context(request.simulation_run_id)
    shipment = _shipment_or_error(request.shipment_id, context)
    locations = {item.location_id: item for item in context.snapshot.locations}
    original = original_result(context.baseline_graph, shipment)
    candidates = _candidate_paths(context, shipment, 3)
    original_output = _route_option(original, shipment, locations) if original else None
    candidate_outputs = [
        _route_option(path, shipment, locations, original)
        for path in candidates
    ]
    selected = candidate_outputs[0] if candidate_outputs else None
    return RouteComparisonOutput(
        simulation_run_id=request.simulation_run_id,
        shipment_id=shipment.shipment_id,
        original_route=original_output,
        candidate_routes=candidate_outputs,
        selected_route=selected,
        no_feasible_route=not bool(candidate_outputs),
    )


def generate_candidate_routes(request: CandidateRoutesInput) -> RouteComparisonOutput:
    context = load_simulation_context(request.simulation_run_id)
    shipment = _shipment_or_error(request.shipment_id, context)
    locations = {item.location_id: item for item in context.snapshot.locations}
    original = original_result(context.baseline_graph, shipment)
    candidates = _filter_constraints(
        _candidate_paths(context, shipment, request.limit),
        request.constraints,
    )[: request.limit]
    outputs = [_route_option(path, shipment, locations, original) for path in candidates]
    return RouteComparisonOutput(
        simulation_run_id=request.simulation_run_id,
        shipment_id=shipment.shipment_id,
        original_route=_route_option(original, shipment, locations) if original else None,
        candidate_routes=outputs,
        selected_route=outputs[0] if outputs else None,
        no_feasible_route=not bool(outputs),
    )


def _candidate_location_ids(context: SimulationContext, shipment: Shipment, route_ids: list[str]) -> list[str]:
    routes = {route.route_id: route for route in context.snapshot.routes}
    current = shipment.current_location_id
    locations = [current]
    for route_id in route_ids:
        route = routes.get(route_id)
        if route is None or route.source_location_id != current:
            raise AgentToolError(
                "INVALID_ROUTE_SEQUENCE",
                "The supplied route legs do not form an ordered path from the shipment's current location.",
            )
        locations.append(route.destination_location_id)
        current = route.destination_location_id
    if current != shipment.destination_location_id:
        raise AgentToolError(
            "INCOMPLETE_ROUTE",
            "The supplied route legs do not reach the shipment destination.",
        )
    return locations


def validate_route_candidate(request: ValidateRouteCandidateInput) -> ValidationOutput:
    context = load_simulation_context(request.simulation_run_id)
    shipment = _shipment_or_error(request.shipment_id, context)
    locations = {item.location_id: item for item in context.snapshot.locations}
    try:
        location_ids = _candidate_location_ids(context, shipment, request.route_ids)
    except AgentToolError as exc:
        return ValidationOutput(valid=False, status=exc.code, reason=exc.message)
    path = path_result(context.graph, location_ids, shipment.load_units)
    if path is None:
        return ValidationOutput(
            valid=False,
            status="INFEASIBLE",
            reason="The route is unavailable or does not have enough effective capacity.",
        )
    original = original_result(context.baseline_graph, shipment)
    return ValidationOutput(
        valid=True,
        status="VALID",
        reason="The route is an ordered, available, capacity-feasible path to the shipment destination.",
        route=_route_option(path, shipment, locations, original),
    )


def simulate_disruption(request: SimulateDisruptionInput) -> SimulateDisruptionOutput:
    snapshot = load_runtime_snapshot()
    location_target = request.disruption_type not in {
        DisruptionType.ROUTE_CLOSURE,
        DisruptionType.ROUTE_BLOCKED,
    }
    location_id = None
    if location_target:
        resolution = resolve_location(request.target_id)
        if resolution.ambiguous:
            raise AgentToolError(
                "AMBIGUOUS_LOCATION",
                f"{request.target_id} matches multiple runtime locations.",
                {"matches": [match.model_dump() for match in resolution.matches]},
            )
        if resolution.resolved is None:
            raise AgentToolError(
                "UNKNOWN_LOCATION",
                f"No runtime location matched {request.target_id}.",
            )
        location_id = resolution.resolved.location_id
        if request.disruption_type == DisruptionType.PORT_CLOSURE:
            location = next(item for item in snapshot.locations if item.location_id == location_id)
            if location.location_type != LocationType.PORT:
                raise AgentToolError(
                    "INVALID_TARGET_TYPE",
                    "PORT_CLOSURE requires a runtime port target.",
                )
    else:
        route_ids = {route.route_id for route in snapshot.routes}
        if request.target_id not in route_ids:
            raise AgentToolError(
                "UNKNOWN_ROUTE",
                f"No runtime route matched {request.target_id}.",
            )
    disruption_request = DisruptionRequest(
        disruption_type=request.disruption_type,
        affected_location_ids=[location_id] if location_id else [],
        affected_route_ids=[] if location_id else [request.target_id],
        duration_hours=request.duration_hours,
        severity=request.severity,
    )
    execution = run_simulation(disruption_request, snapshot=snapshot)
    counts: dict[str, int] = {}
    affected_ids: list[str] = []
    for impact in execution.result.shipment_impacts:
        counts[impact.classification.value] = counts.get(impact.classification.value, 0) + 1
        if impact.classification != ImpactClassification.UNAFFECTED:
            affected_ids.append(impact.shipment_id)
    return SimulateDisruptionOutput(
        simulation_run_id=execution.disruption.id,
        disruption_type=request.disruption_type.value,
        target_id=location_id or request.target_id,
        affected_shipment_count=len(affected_ids),
        impact_counts=counts,
        affected_shipment_ids=affected_ids[:MAX_TOOL_RECORDS],
    )
