"""IMF PortWatch ingestion interface."""

from pathlib import Path
from typing import Any


def ingest_portwatch(raw_path: Path) -> list[dict[str, Any]]:
    """Parse a PortWatch extract into source port-activity rows."""

    raise NotImplementedError(
        f"PortWatch ingestion is not implemented for {raw_path}; confirm the extract contract first."
    )
