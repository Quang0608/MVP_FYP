"""Immutable raw Open-Meteo snapshot persistence."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .errors import SnapshotPersistenceError


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _directory_timestamp(value: datetime) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "", _utc_timestamp(value))


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:80] or "weather-request"


class RawWeatherSnapshotStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(
        self,
        *,
        route_id: str,
        retrieved_at: datetime,
        forecast_payload: dict[str, Any] | list[Any],
        marine_payload: dict[str, Any] | list[Any],
        metadata: dict[str, Any],
        request_id: str | None = None,
    ) -> Path:
        request_id = request_id or uuid4().hex
        directory = (
            self.root
            / _directory_timestamp(retrieved_at)
            / f"{_safe_key(route_id)}-{request_id}"
        )
        try:
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "marine.json").write_text(
                json.dumps(marine_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (directory / "forecast.json").write_text(
                json.dumps(forecast_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            snapshot_metadata = dict(metadata)
            snapshot_metadata.update(
                {
                    "provider": "OPEN_METEO",
                    "route_id": route_id,
                    "retrieved_at": _utc_timestamp(retrieved_at),
                    "request_id": request_id,
                    "raw_snapshot_format": "open_meteo_forecast_and_marine_json",
                }
            )
            (directory / "metadata.json").write_text(
                json.dumps(snapshot_metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as exc:
            raise SnapshotPersistenceError(
                f"Unable to persist immutable weather snapshot for {route_id}"
            ) from exc
        return directory
