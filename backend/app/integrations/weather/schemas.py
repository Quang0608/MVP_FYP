"""Provider-neutral contracts for raw Open-Meteo retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WeatherCoordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ForecastWindow(BaseModel):
    """Optional UTC request bounds; omitted bounds use provider defaults."""

    model_config = ConfigDict(extra="forbid")

    start_time: datetime | None = None
    end_time: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_datetimes(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for field_name in ("start_time", "end_time"):
            item = normalized.get(field_name)
            if isinstance(item, datetime):
                normalized[field_name] = cls._as_utc(item)
        return normalized

    @model_validator(mode="after")
    def validate_window(self) -> "ForecastWindow":
        if self.start_time is not None:
            self.start_time = self._as_utc(self.start_time)
        if self.end_time is not None:
            self.end_time = self._as_utc(self.end_time)
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError("end_time must not be before start_time")
        return self

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def as_request_dates(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.start_time is not None:
            params["start_date"] = self.start_time.date().isoformat()
        if self.end_time is not None:
            params["end_date"] = self.end_time.date().isoformat()
        return params


class WeatherCacheStatus(str, Enum):
    MISS = "MISS"
    HIT = "HIT"
    REFRESHED = "REFRESHED"
    STALE = "STALE"


class OpenMeteoBatchResponse:
    """Validated envelope retaining the provider payload byte-for-byte in JSON form.

    The raw payload is intentionally not normalized into operational concepts.
    It is provider data and is only exposed to internal integration callers.
    """

    def __init__(
        self,
        *,
        api_type: str,
        coordinates: list[WeatherCoordinate],
        requested_variables: tuple[str, ...],
        raw_payload: dict[str, Any] | list[Any],
        missing_variables: dict[int, list[str]] | None = None,
    ) -> None:
        self.api_type = api_type
        self.coordinates = coordinates
        self.requested_variables = requested_variables
        self.raw_payload = raw_payload
        self.missing_variables = missing_variables or {}

    def model_dump(self) -> dict[str, Any]:
        return {
            "api_type": self.api_type,
            "coordinates": [item.model_dump(mode="json") for item in self.coordinates],
            "requested_variables": list(self.requested_variables),
            "raw_payload": self.raw_payload,
            "missing_variables": self.missing_variables,
        }


class RouteWeatherRawResult:
    """Internal result for one route operation; no risk or effect is inferred."""

    def __init__(
        self,
        *,
        route_id: str,
        requested_at: datetime,
        forecast_window: ForecastWindow,
        points: list[dict[str, Any]],
        weather_response: OpenMeteoBatchResponse,
        marine_response: OpenMeteoBatchResponse,
        cache_status: dict[str, WeatherCacheStatus],
        snapshot_path: str | None,
    ) -> None:
        self.route_id = route_id
        self.provider = "OPEN_METEO"
        self.requested_at = requested_at
        self.forecast_window = forecast_window
        self.points = points
        self.weather_response = weather_response
        self.marine_response = marine_response
        self.cache_status = cache_status
        self.snapshot_path = snapshot_path

    def summary(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "provider": self.provider,
            "requested_at": self.requested_at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "points": self.points,
            "cache_status": {key: value.value for key, value in self.cache_status.items()},
            "snapshot_path": self.snapshot_path,
            "forecast_window": self.forecast_window.model_dump(mode="json"),
        }
