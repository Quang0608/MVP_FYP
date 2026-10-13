"""Run read-only SQLite/Neo4j Phase 3 parity verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings
from backend.app.persistence.neo4j.parity import run_parity
from backend.app.persistence.neo4j.repository import Neo4jReadRepository
from backend.app.persistence.neo4j.driver import managed_neo4j_connection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sqlite", type=Path, required=True)
    parser.add_argument(
        "--report-out",
        type=Path,
        default=Path("docs/migration/phase3/PARITY_REPORT.json"),
    )
    parser.add_argument("--snapshot-id", default=None)
    parser.add_argument("--import-scope", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with managed_neo4j_connection(settings) as manager:
        repository_kwargs = {}
        if args.snapshot_id is not None:
            repository_kwargs["snapshot_id"] = args.snapshot_id
        if args.import_scope is not None:
            repository_kwargs["import_scope"] = args.import_scope
        repository = Neo4jReadRepository(manager, **repository_kwargs)
        report = run_parity(repository, args.source_sqlite, args.report_out)
    print(json.dumps({
        "pass": report["pass"],
        "report": str(args.report_out),
        "snapshot_id": report["snapshot_id"],
        "import_scope": report["import_scope"],
        "entities": {
            name: {
                "source_count": value["source_count"],
                "target_count": value["target_count"],
                "pass": value["pass"],
            }
            for name, value in report["entities"].items()
        },
        "route_plans": report["route_plans"]["pass"],
        "relationships": report["relationships"]["pass"],
        "graph": report["graph"]["topology_and_routing_attributes_match"],
        "scenarios": all(value["pass"] for value in report["scenarios"].values()),
        "baseline": report["baseline_comparison"]["pass"],
    }, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
