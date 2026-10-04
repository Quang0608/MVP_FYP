"""Source-neutral canonical models used by runtime services and repositories."""

from __future__ import annotations

from datetime import date, datetime
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class LocationType(str, Enum):
    PORT = "PORT"
    CHECKPOINT = "CHECKPOINT"
    FACTORY = "FACTORY"
    WAREHOUSE = "WAREHOUSE"
    CUSTOMER = "CUSTOMER"


class Status(str, Enum):
    ACTIVE = "ACTIVE"
    DISRUPTED = "DISRUPTED"
    BLOCKED = "BLOCKED"
    INACTIVE = "INACTIVE"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ShipmentStatus(str, Enum):
    PLANNED = "PLANNED"
    ON_TIME = "ON_TIME"
    IN_TRANSIT = "IN_TRANSIT"
    AT_RISK = "AT_RISK"
    DELAYED = "DELAYED"
    DELIVERED = "DELIVERED"
    REROUTED = "REROUTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class ShipmentLegStatus(str, Enum):
    COMPLETED = "COMPLETED"
    CURRENT = "CURRENT"
    PLANNED = "PLANNED"


class DisruptionLifecycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"


class DisruptionTargetType(str, Enum):
    LOCATION = "LOCATION"
    ROUTE = "ROUTE"


class Location(BaseModel):
    """Canonical operational location, independent of source provenance."""

    model_config = ConfigDict(extra="forbid")

    location_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location_type: LocationType
    country: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    unlocode: str | None = None
    status: Status = Status.ACTIVE
    source: str = "SYNTHETIC"
    capacity: float = Field(default=0, ge=0)
    city: str | None = None
    canonical_location_id: str | None = None
    source_entity_id: str | None = None
    portwatch_source_port_id: str | None = None
    latest_observation_date: date | None = None
    activity_score: float | None = Field(default=None, ge=0, le=1)
    activity_anomaly_score: float | None = Field(default=None, ge=-1, le=1)
    operational_status: str | None = None

    @property
    def id(self) -> str:
        """Compatibility alias for the legacy HTTP model."""

        return self.location_id

    @property
    def type(self) -> LocationType:
        return self.location_type


class WeatherSamplePoint(BaseModel):
    """Representative point used for future route-exposure matching.

    These points are not vessel-navigation tracks. They are deterministic
    exposure samples attached to maritime route metadata.
    """

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    sequence: int = Field(ge=1)


class Route(BaseModel):
    """Canonical route master record; scenario state is held by NetworkX."""

    model_config = ConfigDict(extra="forbid")

    route_id: str = Field(min_length=1)
    source_location_id: str = Field(min_length=1)
    destination_location_id: str = Field(min_length=1)
    transport_mode: str = Field(min_length=1)
    distance_km: float = Field(default=0, ge=0)
    base_duration_hours: float = Field(gt=0)
    base_cost: float = Field(ge=0)
    max_capacity: float = Field(ge=0)
    risk_score: float = Field(ge=0, le=1)
    status: Status = Status.ACTIVE
    current_load: float = Field(default=0, ge=0)
    source: str = "DERIVED_SYNTHETIC"
    source_entity_id: str | None = None
    corridor_ids: list[str] = Field(default_factory=list)
    weather_sample_points: list[WeatherSamplePoint] = Field(default_factory=list)
    scenario_duration_hours: float | None = Field(default=None, exclude=True)

    @property
    def id(self) -> str:
        return self.route_id

    @property
    def mode(self) -> str:
        return self.transport_mode

    @property
    def normal_duration_hours(self) -> float:
        return self.base_duration_hours

    @property
    def current_duration_hours(self) -> float:
        return self.scenario_duration_hours or self.base_duration_hours

    @current_duration_hours.setter
    def current_duration_hours(self, value: float) -> None:
        self.scenario_duration_hours = value

    @property
    def cost(self) -> float:
        return self.base_cost

    @property
    def capacity(self) -> float:
        return self.max_capacity


class ShipmentRouteLeg(BaseModel):
    """Ordered shipment leg with explicit progress state."""

    model_config = ConfigDict(extra="forbid")

    shipment_id: str = Field(min_length=1)
    sequence_no: int = Field(ge=1)
    route_id: str = Field(min_length=1)
    source_location_id: str = Field(min_length=1)
    destination_location_id: str = Field(min_length=1)
    status: str = ShipmentLegStatus.PLANNED.value
    planned_departure: datetime | None = None
    planned_arrival: datetime | None = None
    transport_mode: str | None = None


class Shipment(BaseModel):
    """Primary operational entity with structured ordered route legs."""

    model_config = ConfigDict(extra="forbid")

    shipment_id: str = Field(min_length=1)
    origin_location_id: str = Field(min_length=1)
    destination_location_id: str = Field(min_length=1)
    current_location_id: str = Field(min_length=1)
    priority: Priority
    required_delivery_time: datetime
    current_eta: datetime
    load_units: float = Field(gt=0)
    cargo_type: str = "GENERAL"
    status: str = ShipmentStatus.ON_TIME.value
    route_legs: list[ShipmentRouteLeg] = Field(default_factory=list)
    order_id: str | None = None
    customer_id: str | None = None
    cargo_value: float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, gt=0)
    source: str = "SYNTHETIC"

    @property
    def id(self) -> str:
        return self.shipment_id

    @property
    def origin_id(self) -> str:
        return self.origin_location_id

    @property
    def destination_id(self) -> str:
        return self.destination_location_id

    @property
    def deadline(self) -> datetime:
        return self.required_delivery_time

    @property
    def planned_route_location_ids(self) -> list[str]:
        locations = [self.origin_location_id]
        locations.extend(leg.destination_location_id for leg in self.ordered_route_legs)
        return locations

    @property
    def planned_route_ids(self) -> list[str]:
        return [leg.route_id for leg in self.ordered_route_legs]

    @property
    def ordered_route_legs(self) -> list[ShipmentRouteLeg]:
        return sorted(self.route_legs, key=lambda leg: leg.sequence_no)

    def remaining_route_legs(self) -> list[ShipmentRouteLeg]:
        """Return only the current and future legs from current location onward."""

        legs = self.ordered_route_legs
        for index, leg in enumerate(legs):
            if leg.source_location_id == self.current_location_id:
                return legs[index:]
            if leg.destination_location_id == self.current_location_id:
                return legs[index + 1 :]
        for index, leg in enumerate(legs):
            if leg.status.upper() == "CURRENT":
                return legs[index:]
        return [leg for leg in legs if leg.status.upper() == "PLANNED"]

    def remaining_route_location_ids(self) -> list[str]:
        locations = [self.current_location_id]
        locations.extend(
            leg.destination_location_id for leg in self.remaining_route_legs()
        )
        return locations

    def remaining_route_ids(self) -> list[str]:
        return [leg.route_id for leg in self.remaining_route_legs()]


class Disruption(BaseModel):
    """Canonical disruption event for simulated and external sources."""

    model_config = ConfigDict(extra="forbid")

    disruption_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    target_type: DisruptionTargetType
    target_id: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    status: DisruptionLifecycleStatus = DisruptionLifecycleStatus.ACTIVE
    start_time: datetime
    end_time: datetime
    source: str = Field(min_length=1)
    description: str | None = None
    is_simulated: bool = False


@dataclass(frozen=True)
class RuntimeDataset:
    """Repository-facing canonical snapshot consumed by application services."""

    locations: list[Location]
    routes: list[Route]
    shipments: list[Shipment]
