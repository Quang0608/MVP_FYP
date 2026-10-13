"""Bootstrap the Phase 1 Neo4j schema without importing application data."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import settings
from backend.app.persistence.neo4j.driver import Neo4jConnectionManager
from backend.app.persistence.neo4j.schema import bootstrap_schema


def main() -> int:
    manager = Neo4jConnectionManager(settings)
    try:
        health = manager.health_check()
        if health.status != "ok":
            print(json.dumps(health.as_dict(), sort_keys=True))
            return 1
        schema = bootstrap_schema(manager)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "database": settings.neo4j_database,
                    "schema": schema,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
