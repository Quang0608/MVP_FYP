"""Run the sanitized Phase 1 Neo4j connectivity health check."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import settings
from backend.app.persistence.neo4j.driver import Neo4jConnectionManager


def main() -> int:
    manager = Neo4jConnectionManager(settings)
    try:
        health = manager.health_check()
        print(json.dumps(health.as_dict(), sort_keys=True))
        return 0 if health.status == "ok" else 1
    finally:
        manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
