"""Import and verify the frozen active SQLite snapshot in Neo4j."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import settings
from backend.app.persistence.neo4j.driver import Neo4jConnectionManager
from backend.app.persistence.neo4j.importer import (
    ImportValidationError,
    run_import,
)


DEFAULT_MANIFEST = Path("docs/migration/phase2/IMPORT_MANIFEST.json")


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--snapshot-id",
        required=True,
        help="Frozen active dataset snapshot identifier.",
    )
    parser.add_argument(
        "--source-sqlite",
        type=Path,
        required=True,
        help="SQLite database file to load through the canonical repository mapper.",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Machine-readable report path (default: {DEFAULT_MANIFEST}).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser(
        "import",
        help="Validate and optionally import the active snapshot.",
    )
    _common_arguments(import_parser)
    mode_group = import_parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report the source without connecting to or writing Neo4j.",
    )
    mode_group.add_argument(
        "--execute",
        action="store_true",
        help="Import the validated source and verify the resulting graph.",
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify the active snapshot already present in Neo4j.",
    )
    _common_arguments(verify_parser)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    mode = "verify" if args.command == "verify" else "dry-run" if args.dry_run else "execute"
    manager = None
    try:
        if mode in {"execute", "verify"}:
            manager = Neo4jConnectionManager(settings)
        report = run_import(
            snapshot_id=args.snapshot_id,
            source_sqlite=args.source_sqlite,
            mode=mode,
            manifest_out=args.manifest_out,
            manager=manager,
        )
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0 if report.get("verification", {}).get("pass", True) else 1
    except ImportValidationError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "detail": str(exc),
                    "manifest_out": str(args.manifest_out),
                },
                sort_keys=True,
            )
        )
        return 1
    finally:
        if manager is not None:
            manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
