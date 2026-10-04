"""Adapters from processed canonical artifacts to runtime domain models."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from ..domain import Location, LocationType, Status


def locations_from_port_master(
    records: Iterable[Mapping[str, Any]],
    *,
    skip_missing_geometry: bool = True,
) -> list[Location]:
    """Convert validated port-master rows into runtime ``Location`` models.

    WPI-backed rows retain their WPI identity. Accepted PortWatch mappings also
    use the WPI location ID from the port master; source-native PortWatch rows
    remain valid processed artifacts but are excluded by default when geometry
    is unavailable because the runtime Location contract requires coordinates.
    """

    locations: list[Location] = []
    for record in records:
        latitude = record.get("latitude")
        longitude = record.get("longitude")
        if _missing(latitude) or _missing(longitude):
            if not skip_missing_geometry:
                raise ValueError(
                    "A runtime Location requires latitude and longitude: "
                    f"{record.get('location_id')}"
                )
            continue
        source = _optional_text(record.get("canonical_source")) or "UNKNOWN"
        locations.append(
            Location(
                location_id=str(record["location_id"]),
                name=str(record["name"]),
                location_type=LocationType(str(record.get("location_type", "PORT"))),
                country=str(record["country"]),
                latitude=float(latitude),
                longitude=float(longitude),
                unlocode=_optional_text(record.get("unlocode")),
                status=Status.ACTIVE,
                source=source,
                capacity=float(record.get("capacity") or 0),
                source_entity_id=_optional_text(record.get("source_entity_id"))
                or str(record["location_id"]),
                portwatch_source_port_id=_optional_text(record.get("source_port_id")),
            )
        )
    return locations


def _missing(value: Any) -> bool:
    return value is None or bool(pd.isna(value))


def _optional_text(value: Any) -> str | None:
    return None if _missing(value) else str(value)


def load_port_master_locations(
    path: Path = Path("data/processed/ports/port_master.parquet"),
) -> list[Location]:
    """Load usable port-master rows without making files runtime state."""

    if not path.exists():
        return []
    frame = pd.read_parquet(path)
    return locations_from_port_master(frame.to_dict(orient="records"))
