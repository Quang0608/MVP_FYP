"""AIS historical-file ingestion interface."""

from pathlib import Path
from typing import Any


def ingest_ais(raw_path: Path) -> list[dict[str, Any]]:
    """Parse CSV or Parquet AIS records into source vessel-position rows."""

    raise NotImplementedError(
        f"AIS ingestion is not implemented for {raw_path}; provide a reviewed file adapter first."
    )
