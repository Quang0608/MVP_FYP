"""GDELT and external-event ingestion interface."""

from pathlib import Path
from typing import Any


def ingest_gdelt(raw_path: Path) -> list[dict[str, Any]]:
    """Parse a reviewed event extract into source disruption candidates."""

    raise NotImplementedError(
        f"GDELT ingestion is not implemented for {raw_path}; event classification needs review first."
    )
