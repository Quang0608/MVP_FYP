"""Pydantic contracts and cross-reference validation for canonical data."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CanonicalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CanonicalLocation(CanonicalModel):
    location_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location_type: Literal[
        "PORT",
        "CHECKPOINT",
        "FACTORY",
        "WAREHOUSE",
        "DISTRIBUTION_CENTER",
        "CUSTOMER",
    ]
    country: str = Field(min_length=1)
    city: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    unlocode: str | None = None
    capacity: float = Field(ge=0)
    status: Literal["ACTIVE", "DISRUPTED", "INACTIVE"]
    source: str = Field(min_length=1)


class CanonicalPort(CanonicalModel):
    location_id: str = Field(min_length=1)
    wpi_number: str = Field(min_length=1)
    name: str = Field(min_length=1)
    country: str = Field(min_length=1)
    unlocode: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_type: Literal["PORT"]
    source: Literal["WPI"]


class CanonicalPortMaster(CanonicalModel):
    location_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    location_type: Literal["PORT"]
    country: str = Field(min_length=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    unlocode: str | None = None
    wpi_number: str | None = None
    canonical_source: Literal["WPI", "PORTWATCH", "MANUAL_VALIDATED"]
    source_entity_id: str = Field(min_length=1)
    mapping_status: Literal["MATCHED_WPI", "SOURCE_NATIVE", "MANUAL_MATCH", "UNRESOLVED"]
    source_port_id: str | None = None


class CanonicalRoute(CanonicalModel):
    route_id: str = Field(min_length=1)
    source_location_id: str = Field(min_length=1)
    destination_location_id: str = Field(min_length=1)
    transport_mode: Literal["SEA", "ROAD", "RAIL", "AIR"]
    distance_km: float = Field(ge=0)
    base_duration_hours: float = Field(gt=0)
    base_cost: float = Field(ge=0)
    max_capacity: float = Field(ge=0)
    risk_score: float = Field(ge=0, le=1)
    status: Literal["ACTIVE", "DISRUPTED", "BLOCKED", "INACTIVE"]


class CanonicalShipment(CanonicalModel):
    shipment_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    origin_location_id: str = Field(min_length=1)
    destination_location_id: str = Field(min_length=1)
    current_location_id: str = Field(min_length=1)
    vessel_id: str | None = None
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    planned_departure: datetime
    required_delivery_time: datetime
    current_eta: datetime
    status: Literal[
        "PLANNED",
        "IN_TRANSIT",
        "AT_RISK",
        "DELAYED",
        "DELIVERED",
        "REROUTED",
        "CANCELLED",
    ]
    cargo_value: float = Field(ge=0)
    weight_kg: float = Field(gt=0)


class CanonicalShipmentRouteStep(CanonicalModel):
    shipment_id: str = Field(min_length=1)
    route_version: str = Field(min_length=1)
    sequence_no: int = Field(ge=1)
    route_id: str | None = None
    source_location_id: str | None = None
    destination_location_id: str | None = None
    location_id: str = Field(min_length=1)
    status: Literal["COMPLETED", "CURRENT", "PLANNED"] = "PLANNED"
    planned_arrival: datetime
    planned_departure: datetime


class CanonicalVessel(CanonicalModel):
    vessel_id: str = Field(min_length=1)
    mmsi: str = Field(pattern=r"^[0-9]{9}$")
    vessel_name: str = Field(min_length=1)
    vessel_type: str = Field(min_length=1)
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    draft: float = Field(ge=0)


class CanonicalVesselPosition(CanonicalModel):
    vessel_id: str = Field(min_length=1)
    mmsi: str = Field(pattern=r"^[0-9]{9}$")
    event_time: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_knots: float = Field(ge=0)
    course: float = Field(ge=0, lt=360)
    heading: float = Field(ge=0, lt=360)
    source: str = Field(min_length=1)


class CanonicalPortMetrics(CanonicalModel):
    location_id: str = Field(min_length=1)
    event_time: datetime
    port_calls: float = Field(ge=0)
    estimated_import_volume: float = Field(ge=0)
    estimated_export_volume: float = Field(ge=0)
    activity_score: float = Field(ge=0, le=1)
    congestion_score: float = Field(ge=0, le=1)
    source: str = Field(min_length=1)


class CanonicalDisruptionEvent(CanonicalModel):
    event_id: str = Field(min_length=1)
    event_type: Literal[
        "PORT_CLOSURE",
        "PORT_CONGESTION",
        "FACTORY_SHUTDOWN",
        "WEATHER",
        "TYPHOON",
        "STRIKE",
        "ROUTE_BLOCKAGE",
        "GEOPOLITICAL_EVENT",
        "CAPACITY_REDUCTION",
    ]
    target_type: Literal["LOCATION", "ROUTE"] = "LOCATION"
    target_id: str | None = None
    location_id: str | None = None
    route_id: str | None = None
    start_time: datetime
    end_time: datetime
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    capacity_reduction: float = Field(ge=0, le=1)
    delay_penalty_hours: float = Field(ge=0)
    risk_penalty: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    source: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: Literal["ACTIVE", "RESOLVED", "EXPIRED"] = "ACTIVE"
    is_simulated: bool = False

    @model_validator(mode="after")
    def require_target(self) -> "CanonicalDisruptionEvent":
        if self.location_id is None and self.route_id is None:
            raise ValueError("a disruption event must target a location or route")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.target_id is None:
            if self.route_id is not None:
                self.target_type = "ROUTE"
                self.target_id = self.route_id
            else:
                self.target_type = "LOCATION"
                self.target_id = self.location_id
        elif self.target_type == "ROUTE" and self.route_id is None:
            self.route_id = self.target_id
        elif self.target_type == "LOCATION" and self.location_id is None:
            self.location_id = self.target_id
        return self


class CanonicalDataset(CanonicalModel):
    locations: list[CanonicalLocation] = Field(default_factory=list)
    routes: list[CanonicalRoute] = Field(default_factory=list)
    shipments: list[CanonicalShipment] = Field(default_factory=list)
    shipment_route_steps: list[CanonicalShipmentRouteStep] = Field(default_factory=list)
    vessels: list[CanonicalVessel] = Field(default_factory=list)
    vessel_positions: list[CanonicalVesselPosition] = Field(default_factory=list)
    port_metrics: list[CanonicalPortMetrics] = Field(default_factory=list)
    disruption_events: list[CanonicalDisruptionEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "CanonicalDataset":
        location_ids = {item.location_id for item in self.locations}
        route_ids = {item.route_id for item in self.routes}
        shipment_ids = {item.shipment_id for item in self.shipments}
        vessel_ids = {item.vessel_id for item in self.vessels}
        vessel_mmsi = {item.vessel_id: item.mmsi for item in self.vessels}
        errors: list[str] = []

        if len(location_ids) != len(self.locations):
            errors.append("locations contain duplicate location_id values")
        if len(route_ids) != len(self.routes):
            errors.append("routes contain duplicate route_id values")
        if len(shipment_ids) != len(self.shipments):
            errors.append("shipments contain duplicate shipment_id values")
        if len(vessel_ids) != len(self.vessels):
            errors.append("vessels contain duplicate vessel_id values")

        for route in self.routes:
            if route.source_location_id not in location_ids:
                errors.append(f"route {route.route_id} has an unknown source location")
            if route.destination_location_id not in location_ids:
                errors.append(f"route {route.route_id} has an unknown destination location")

        for shipment in self.shipments:
            references = {
                "customer_id": shipment.customer_id,
                "origin_location_id": shipment.origin_location_id,
                "destination_location_id": shipment.destination_location_id,
                "current_location_id": shipment.current_location_id,
            }
            for field_name, location_id in references.items():
                if location_id not in location_ids:
                    errors.append(f"shipment {shipment.shipment_id} has an unknown {field_name}")
            if shipment.vessel_id is not None and shipment.vessel_id not in vessel_ids:
                errors.append(f"shipment {shipment.shipment_id} has an unknown vessel_id")

        for step in self.shipment_route_steps:
            if step.shipment_id not in shipment_ids:
                errors.append(f"route step has an unknown shipment_id {step.shipment_id}")
            if step.location_id not in location_ids:
                errors.append(f"route step has an unknown location_id {step.location_id}")
            if step.route_id is not None and step.route_id not in route_ids:
                errors.append(f"route step has an unknown route_id {step.route_id}")

        for position in self.vessel_positions:
            if position.vessel_id not in vessel_ids:
                errors.append(f"vessel position has an unknown vessel_id {position.vessel_id}")
            elif vessel_mmsi[position.vessel_id] != position.mmsi:
                errors.append(f"vessel position MMSI does not match {position.vessel_id}")

        for metric in self.port_metrics:
            if metric.location_id not in location_ids:
                errors.append(f"port metric has an unknown location_id {metric.location_id}")

        for event in self.disruption_events:
            if event.location_id is not None and event.location_id not in location_ids:
                errors.append(f"disruption {event.event_id} has an unknown location_id")
            if event.route_id is not None and event.route_id not in route_ids:
                errors.append(f"disruption {event.event_id} has an unknown route_id")

        if errors:
            raise ValueError("Canonical data validation failed: " + "; ".join(errors))
        return self


def validate_dataset(
    *,
    locations: list[CanonicalLocation],
    routes: list[CanonicalRoute],
    shipments: list[CanonicalShipment],
    shipment_route_steps: list[CanonicalShipmentRouteStep] | None = None,
    vessels: list[CanonicalVessel] | None = None,
    vessel_positions: list[CanonicalVesselPosition] | None = None,
    port_metrics: list[CanonicalPortMetrics] | None = None,
    disruption_events: list[CanonicalDisruptionEvent] | None = None,
) -> CanonicalDataset:
    """Validate canonical records and their cross-entity references."""

    return CanonicalDataset(
        locations=locations,
        routes=routes,
        shipments=shipments,
        shipment_route_steps=shipment_route_steps or [],
        vessels=vessels or [],
        vessel_positions=vessel_positions or [],
        port_metrics=port_metrics or [],
        disruption_events=disruption_events or [],
    )
