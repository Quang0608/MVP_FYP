"""Small deterministic file cache for provider response payloads."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .errors import WeatherCacheError
from .schemas import ForecastWindow, WeatherCacheStatus, WeatherCoordinate


@dataclass(frozen=True)
class WeatherCacheEntry:
    payload: dict[str, Any] | list[Any]
    created_at: datetime
    status: WeatherCacheStatus


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def make_weather_cache_key(
    *,
    api_type: str,
    coordinates: list[WeatherCoordinate],
    variables: tuple[str, ...],
    forecast_window: ForecastWindow,
) -> str:
    request_identity = {
        "provider": "OPEN_METEO",
        "api_type": api_type,
        "coordinates": [
            {"latitude": round(point.latitude, 6), "longitude": round(point.longitude, 6)}
            for point in coordinates
        ],
        "variables": list(variables),
        "forecast_window": forecast_window.model_dump(mode="json"),
        "timezone": "UTC",
    }
    encoded = json.dumps(request_identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class WeatherCache:
    def __init__(self, directory: Path, ttl_minutes: int) -> None:
        if ttl_minutes < 0:
            raise ValueError("Weather cache TTL must not be negative")
        self.directory = directory
        self.ttl = timedelta(minutes=ttl_minutes)

    def get(self, key: str, *, now: datetime | None = None) -> WeatherCacheEntry | None:
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            payload = record["payload"]
            created_at = datetime.fromisoformat(
                str(record["created_at"]).replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            if not isinstance(payload, (dict, list)):
                raise ValueError("cached payload must be an object or list")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise WeatherCacheError(f"Unable to read weather cache entry {key}") from exc
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        status = (
            WeatherCacheStatus.HIT
            if current.astimezone(timezone.utc) <= created_at + self.ttl
            else WeatherCacheStatus.STALE
        )
        return WeatherCacheEntry(payload, created_at, status)

    def set(
        self,
        key: str,
        payload: dict[str, Any] | list[Any],
        *,
        created_at: datetime | None = None,
    ) -> None:
        created = created_at or datetime.now(timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        record = {"created_at": _timestamp(created), "payload": payload}
        path = self.directory / f"{key}.json"
        temporary = self.directory / f".{key}.tmp"
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary.replace(path)
        except (OSError, TypeError, ValueError) as exc:
            raise WeatherCacheError(f"Unable to write weather cache entry {key}") from exc
