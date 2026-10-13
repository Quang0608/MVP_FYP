"""CLI wrapper for the read-only Phase 0 SQLite baseline exporter."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.migration_baseline import main


if __name__ == "__main__":
    raise SystemExit(main())
