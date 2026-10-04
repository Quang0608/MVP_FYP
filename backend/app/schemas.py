from datetime import date, datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from .domain.models import LocationType, Priority, Status, WeatherSamplePoint


class DisruptionType(str, Enum):
    PORT_CLOSURE = "PORT_CLOSURE"
    FACTORY_SHUTDOWN = "FACTORY_SHUTDOWN"
    WAREHOUSE_SHUTDOWN = "WAREHOUSE_SHUTDOWN"
    ROUTE_BLOCKED = "ROUTE_BLOCKED"
    ROUTE_CLOSURE = "ROUTE_CLOSURE"
    CONGESTION = "CONGESTION"
    CAPACITY_REDUCTION = "CAPACITY_REDUCTION"
    MULTIPLE_PORT = "MULTIPLE_PORT"


class Location(BaseModel):
    id: str; name: str; type: LocationType; country: str; latitude: float; longitude: float; capacity: float; status: Status = Status.ACTIVE
    source: str | None = None
    canonical_location_id: str | None = None
    portwatch_source_port_id: str | None = None
    latest_observation_date: date | None = None
    activity_score: float | None = Field(default=None, ge=0, le=1)
    activity_anomaly_score: float | None = Field(default=None, ge=-1, le=1)
    operational_status: str | None = None


class Route(BaseModel):
    id: str; source_location_id: str; destination_location_id: str; mode: str
    normal_duration_hours: float; current_duration_hours: float; cost: float; risk_score: float = Field(ge=0, le=1)
    capacity: float; current_load: float = 0; status: Status = Status.ACTIVE
    corridor_ids: list[str] = Field(default_factory=list)
    weather_sample_points: list[WeatherSamplePoint] = Field(default_factory=list)


class Shipment(BaseModel):
    id: str; origin_id: str; destination_id: str; current_location_id: str
    planned_route_location_ids: list[str]; planned_route_ids: list[str]; deadline: datetime
    priority: Priority; load_units: float = Field(gt=0); status: str = "ON_TIME"


class DisruptionRequest(BaseModel):
    disruption_type: DisruptionType
    affected_location_ids: list[str] = []
    affected_route_ids: list[str] = []
    duration_hours: int = Field(gt=0, le=720)
    severity: str = "HIGH"
    description: str | None = None


class ImpactClassification(str, Enum):
    UNAFFECTED = "UNAFFECTED"
    NETWORK_WARNING = "NETWORK_WARNING"
    SHIPMENT_AT_RISK = "SHIPMENT_AT_RISK"
    REROUTE_REQUIRED = "REROUTE_REQUIRED"


class ShipmentImpact(BaseModel):
    shipment_id: str
    classification: ImpactClassification
    reason: str
    disruption_ids: list[str] = Field(default_factory=list)
    affected_location_ids: list[str] = Field(default_factory=list)
    affected_route_ids: list[str] = Field(default_factory=list)
    route_feasible: bool = True
    baseline_duration_hours: float | None = None
    effective_duration_hours: float | None = None
    baseline_risk_score: float | None = None
    effective_risk_score: float | None = None


class Disruption(BaseModel):
    id: str; request: DisruptionRequest; created_at: datetime


class PathResult(BaseModel):
    location_ids: list[str]; route_ids: list[str]; duration_hours: float; cost: float; risk_score: float
    capacity_feasible: bool; capacity_penalty: float; route_score: float | None = None


class Recommendation(BaseModel):
    shipment_id: str; status: str; original_route: PathResult | None = None
    candidate_routes: list[PathResult] = []; selected_route: PathResult | None = None
    delay_saved_hours: float = 0; additional_cost: float = 0; explanation: dict | None = None


class SimulationResult(BaseModel):
    disruption_id: str
    affected_shipments: list[Shipment]
    downstream_impacts: list[Location]
    shipment_impacts: list[ShipmentImpact] = Field(default_factory=list)


class RoutePlanRequest(BaseModel):
    origin_id: str
    destination_id: str
    priority: Priority = Priority.MEDIUM
    load_units: float = Field(default=10, gt=0)
    disruption: DisruptionRequest | None = None
    generate_explanation: bool = True


class RoutePlanResult(BaseModel):
    status: str
    reason: str | None = None
    origin_id: str
    destination_id: str
    original_route: PathResult | None = None
    candidate_routes: list[PathResult] = []
    selected_route: PathResult | None = None
    disruption: DisruptionRequest | None = None
    explanation: dict | None = None


class ShipmentAnalyticsRequest(BaseModel):
    disruption_id: str
    shipment_id: str


class ShipmentAnalyticsResult(BaseModel):
    disruption_id: str
    shipment_id: str
    status: str
    analytics: dict


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    shipment_id: str | None = None
    disruption_id: str | None = None
    simulation_run_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    answer: str
    evidence: list[str] = []
    source: str
    fallback_reason: str | None = None


class ExternalImpactEvidence(BaseModel):
    event_id: str
    affected_location: str
    canonical_location_id: str
    affected_shipments: list[str] = []
    reason: str
    source: str = "PORTWATCH"
    classification: ImpactClassification = ImpactClassification.NETWORK_WARNING
