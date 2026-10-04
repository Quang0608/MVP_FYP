"""World Port Index ingestion interface."""

from pathlib import Path
from typing import Any


def ingest_wpi(raw_path: Path) -> list[dict[str, Any]]:
    """Parse a WPI extract into source rows.

    Parsing is intentionally deferred until the source file and licensing
    requirements are confirmed. The parser must not be replaced by application
    code that reads WPI columns directly.
    """

    raise NotImplementedError(
        f"WPI ingestion is not implemented for {raw_path}; provide a reviewed parser first."
    )
