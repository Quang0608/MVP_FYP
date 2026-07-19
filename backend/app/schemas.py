from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class LocationType(str, Enum): FACTORY="FACTORY"; PORT="PORT"; WAREHOUSE="WAREHOUSE"; CUSTOMER="CUSTOMER"
class Status(str, Enum): ACTIVE="ACTIVE"; DISRUPTED="DISRUPTED"; BLOCKED="BLOCKED"
class Priority(str, Enum): LOW="LOW"; MEDIUM="MEDIUM"; HIGH="HIGH"
class DisruptionType(str, Enum): PORT_CLOSURE="PORT_CLOSURE"; FACTORY_SHUTDOWN="FACTORY_SHUTDOWN"; ROUTE_BLOCKED="ROUTE_BLOCKED"; CONGESTION="CONGESTION"; MULTIPLE_PORT="MULTIPLE_PORT"


class Location(BaseModel):
    id: str; name: str; type: LocationType; country: str; latitude: float; longitude: float; capacity: float; status: Status = Status.ACTIVE


class Route(BaseModel):
    id: str; source_location_id: str; destination_location_id: str; mode: str
    normal_duration_hours: float; current_duration_hours: float; cost: float; risk_score: float = Field(ge=0, le=1)
    capacity: float; current_load: float = 0; status: Status = Status.ACTIVE


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
    disruption_id: str; affected_shipments: list[Shipment]; downstream_impacts: list[Location]


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
