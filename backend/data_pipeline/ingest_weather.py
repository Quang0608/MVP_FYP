"""Weather and marine-weather ingestion interface."""

from pathlib import Path
from typing import Any


def ingest_weather(raw_path: Path) -> list[dict[str, Any]]:
    """Parse a weather API response saved as JSON into source rows."""

    raise NotImplementedError(
        f"Weather ingestion is not implemented for {raw_path}; confirm the provider response contract first."
    )
