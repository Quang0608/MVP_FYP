"""OpenStreetMap PBF ingestion interface."""

from pathlib import Path
from typing import Any


def ingest_osm(raw_path: Path) -> list[dict[str, Any]]:
    """Parse an OSM PBF extract into source geometry rows."""

    raise NotImplementedError(
        f"OSM ingestion is not implemented for {raw_path}; choose and review a PBF parser first."
    )
