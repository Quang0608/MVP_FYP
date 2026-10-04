"""Structured provider-neutral external signal and exposure contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SignalSource(str, Enum):
    MANUAL = "MANUAL"
    PORTWATCH = "PORTWATCH"
    OPEN_METEO = "OPEN_METEO"
    GDELT = "GDELT"
    OTHER = "OTHER"


class SignalTargetType(str, Enum):
    LOCATION = "LOCATION"
    ROUTE = "ROUTE"
    CORRIDOR = "CORRIDOR"
    GEO_REGION = "GEO_REGION"


class SignalType(str, Enum):
    PORT_DISRUPTION = "PORT_DISRUPTION"
    PORT_CLOSURE = "PORT_CLOSURE"
    CORRIDOR_CLOSURE = "CORRIDOR_CLOSURE"
    CONGESTION = "CONGESTION"
    MARINE_WEATHER = "MARINE_WEATHER"
    LAND_WEATHER = "LAND_WEATHER"
    CAPACITY_REDUCTION = "CAPACITY_REDUCTION"
    SECURITY_RISK = "SECURITY_RISK"
    OTHER = "OTHER"


class SignalStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"


class NetworkMatchType(str, Enum):
    LOCATION = "LOCATION"
    ROUTE = "ROUTE"
    CORRIDOR = "CORRIDOR"
    GEO = "GEO"


class SignalProvenance(BaseModel):
    """Small audit envelope without storing provider payloads."""

    model_config = ConfigDict(extra="forbid")

    provider: str | None = None
    source_uri: str | None = None
    source_version: str | None = None
    notes: str | None = None


class ExternalSignal(BaseModel):
    """External evidence before any operational policy is applied."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source: SignalSource
    source_record_id: str = Field(min_length=1)
    signal_type: SignalType
    target_type: SignalTargetType
    target_id: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_km: float | None = Field(default=None, gt=0)
    valid_from: datetime
    valid_to: datetime | None = None
    severity: str = Field(default="UNKNOWN", min_length=1)
    confidence: float = Field(default=1.0, ge=0, le=1)
    measurements: dict[str, float] = Field(default_factory=dict)
    status: SignalStatus = SignalStatus.DISCOVERED
    observed_at: datetime | None = None
    retrieved_at: datetime | None = None
    provenance: SignalProvenance = Field(default_factory=SignalProvenance)

    @model_validator(mode="after")
    def validate_target_and_window(self) -> "ExternalSignal":
        if self.target_type != SignalTargetType.GEO_REGION and not self.target_id:
            raise ValueError("target_id is required for a non-geographic target")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be earlier than valid_from")
        return self

    @staticmethod
    def _utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="before")
    @classmethod
    def normalize_datetimes(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        normalized = dict(values)
        for field_name in ("valid_from", "valid_to", "observed_at", "retrieved_at"):
            value = normalized.get(field_name)
            if isinstance(value, datetime):
                normalized[field_name] = cls._utc(value)
        return normalized


class OperationalEffect(BaseModel):
    """Future policy output; Phase 4.1 never applies this contract."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(min_length=1)
    target_type: SignalTargetType
    target_id: str = Field(min_length=1)
    available: bool | None = None
    duration_multiplier: float | None = Field(default=None, gt=0)
    fixed_delay_hours: float | None = Field(default=None, ge=0)
    capacity_multiplier: float | None = Field(default=None, ge=0)
    risk_delta: float | None = None
    valid_from: datetime
    valid_to: datetime | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_window(self) -> "OperationalEffect":
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be earlier than valid_from")
        return self


class RouteMatchEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str
    match_type: NetworkMatchType
    matched_corridor_id: str | None = None
    sample_point_sequences: list[int] = Field(default_factory=list)
    distances_km: list[float] = Field(default_factory=list)


class SignalNetworkMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str
    affected_locations: list[str] = Field(default_factory=list)
    affected_routes: list[str] = Field(default_factory=list)
    matched_corridors: list[str] = Field(default_factory=list)
    route_evidence: list[RouteMatchEvidence] = Field(default_factory=list)


class ShipmentTraversalWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    route_id: str
    sequence: int = Field(ge=1)
    estimated_entry_time: datetime
    estimated_exit_time: datetime


class ShipmentExposure(BaseModel):
    """Evidence that a shipment leg intersects an external signal."""

    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    route_id: str
    sequence: int = Field(ge=1)
    match_type: NetworkMatchType
    spatial_match: bool
    temporal_match: bool
    estimated_entry_time: datetime
    estimated_exit_time: datetime
    matched_location_id: str | None = None
    matched_corridor_id: str | None = None
    matched_sample_point_sequences: list[int] = Field(default_factory=list)
    distances_km: list[float] = Field(default_factory=list)


class ExternalExposureResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: ExternalSignal
    network_match: SignalNetworkMatch
    exposed_shipments: list[ShipmentExposure] = Field(default_factory=list)
