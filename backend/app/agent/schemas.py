"""Structured contracts used by the bounded Supervisor and trusted tools."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..schemas import DisruptionType, ImpactClassification, Priority


class ToolError(BaseModel):
    code: str
    message: str
    details: dict[str, object] = Field(default_factory=dict)


class ToolInvocation(BaseModel):
    tool_name: str
    input: dict[str, object] = Field(default_factory=dict)
    success: bool
    error: ToolError | None = None


class LocationMatch(BaseModel):
    location_id: str
    name: str
    location_type: str
    country: str
    source: str
    score: int


class LocationResolution(BaseModel):
    query: str
    resolved: LocationMatch | None = None
    matches: list[LocationMatch] = Field(default_factory=list)
    ambiguous: bool = False


class ShipmentSummary(BaseModel):
    shipment_id: str
    priority: Priority
    status: str
    origin_location_id: str
    origin_name: str
    destination_location_id: str
    destination_name: str
    current_location_id: str
    current_location_name: str
    cargo_type: str
    load_units: float
    required_delivery_time: datetime
    current_eta: datetime


class ShipmentFilterInput(BaseModel):
    shipment_id: str | None = None
    priority: Priority | None = None
    status: str | None = None
    affected: bool | None = None
    simulation_run_id: str | None = None
    origin_location_id: str | None = None
    destination_location_id: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class ShipmentInput(BaseModel):
    shipment_id: str = Field(min_length=1)


class LocationQueryInput(BaseModel):
    name_or_id: str = Field(min_length=1, max_length=200)


class EmptyInput(BaseModel):
    pass


class ShipmentLegSummary(BaseModel):
    sequence_no: int
    route_id: str
    source_location_id: str
    source_name: str
    destination_location_id: str
    destination_name: str
    status: str
    transport_mode: str | None = None
    planned_departure: datetime | None = None
    planned_arrival: datetime | None = None


class ShipmentRouteOutput(BaseModel):
    shipment_id: str
    current_location_id: str
    current_location_name: str
    remaining_leg_count: int
    legs: list[ShipmentLegSummary]


class ActiveDisruptionSummary(BaseModel):
    disruption_id: str
    disruption_type: str
    target_type: str
    target_id: str
    severity: str
    duration_hours: int
    source: str
    status: str
    created_at: datetime | None = None


class SimulationInput(BaseModel):
    simulation_run_id: str


class AffectedShipmentsInput(SimulationInput):
    priority: Priority | None = None
    limit: int = Field(default=50, ge=1, le=100)


class SimulationSummary(BaseModel):
    simulation_run_id: str
    disruption_type: str
    affected_location_ids: list[str] = Field(default_factory=list)
    affected_route_ids: list[str] = Field(default_factory=list)
    severity: str
    duration_hours: int
    affected_shipment_count: int
    impact_counts: dict[str, int] = Field(default_factory=dict)
    available_route_count: int
    unavailable_route_count: int
    created_at: datetime | None = None


class ShipmentImpactOutput(BaseModel):
    simulation_run_id: str
    shipment: ShipmentSummary
    classification: ImpactClassification
    reason: str
    affected_location_ids: list[str] = Field(default_factory=list)
    affected_route_ids: list[str] = Field(default_factory=list)
    route_feasible: bool
    baseline_duration_hours: float | None = None
    effective_duration_hours: float | None = None
    baseline_risk_score: float | None = None
    effective_risk_score: float | None = None


class AffectedShipmentsOutput(BaseModel):
    simulation_run_id: str
    total: int
    shipments: list[ShipmentImpactOutput]


class RouteConstraints(BaseModel):
    max_duration_hours: float | None = Field(default=None, gt=0)
    max_cost: float | None = Field(default=None, ge=0)
    max_risk_score: float | None = Field(default=None, ge=0, le=1)


class RouteOption(BaseModel):
    route_ids: list[str]
    location_ids: list[str]
    location_names: list[str]
    duration_hours: float
    duration_delta_hours: float | None = None
    cost: float
    cost_delta: float | None = None
    risk_score: float
    capacity_feasible: bool
    capacity_penalty: float
    sla_met: bool
    route_score: float | None = None
    validation_status: str


class RouteComparisonOutput(BaseModel):
    simulation_run_id: str
    shipment_id: str
    original_route: RouteOption | None = None
    candidate_routes: list[RouteOption] = Field(default_factory=list)
    selected_route: RouteOption | None = None
    no_feasible_route: bool = False


class CandidateRoutesInput(BaseModel):
    shipment_id: str
    simulation_run_id: str
    constraints: RouteConstraints | None = None
    limit: int = Field(default=3, ge=1, le=10)


class ShipmentSimulationInput(BaseModel):
    shipment_id: str
    simulation_run_id: str


class ValidateRouteCandidateInput(BaseModel):
    shipment_id: str
    simulation_run_id: str
    route_ids: list[str] = Field(min_length=1, max_length=50)


class ValidationOutput(BaseModel):
    valid: bool
    status: str
    reason: str
    route: RouteOption | None = None


class SimulateDisruptionInput(BaseModel):
    disruption_type: DisruptionType
    target_id: str = Field(min_length=1)
    duration_hours: int = Field(gt=0, le=720)
    severity: str = Field(default="HIGH", min_length=1, max_length=20)


class SimulateDisruptionOutput(BaseModel):
    simulation_run_id: str
    disruption_type: str
    target_id: str
    affected_shipment_count: int
    impact_counts: dict[str, int] = Field(default_factory=dict)
    affected_shipment_ids: list[str] = Field(default_factory=list)


class IncidentState(BaseModel):
    """Small structured workflow state for later specialist-agent expansion."""

    incident_id: str | None = None
    user_request: str
    resolved_entities: list[LocationMatch] = Field(default_factory=list)
    canonical_disruption: SimulateDisruptionInput | None = None
    simulation_run_id: str | None = None
    affected_shipments: list[ShipmentImpactOutput] = Field(default_factory=list)
    prioritized_shipments: list[str] = Field(default_factory=list)
    candidate_routes: list[RouteOption] = Field(default_factory=list)
    route_evaluations: list[ValidationOutput] = Field(default_factory=list)
    critic_feedback: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class SupervisorRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    shipment_id: str | None = None
    disruption_id: str | None = None
    simulation_run_id: str | None = None


class SupervisorResponse(BaseModel):
    answer: str
    evidence: list[str] = Field(default_factory=list)
    source: str
    tool_calls: list[ToolInvocation] = Field(default_factory=list)
    state: IncidentState
    fallback_reason: str | None = None
