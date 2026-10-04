"""Fetch and save an immutable PortWatch disruption snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .client import PortWatchClient, save_raw_disruption_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--where",
        default="1=1",
        help="ArcGIS where filter applied to the disruption layer",
    )
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/portwatch"))
    parser.add_argument("--retrieved-at", type=str)
    args = parser.parse_args()
    retrieved_at = None
    if args.retrieved_at:
        retrieved_at = datetime.fromisoformat(args.retrieved_at.replace("Z", "+00:00"))
    with PortWatchClient() as client:
        result = client.fetch_disruptions(args.where)
        snapshot = save_raw_disruption_snapshot(
            result=result,
            raw_root=args.raw_root,
            retrieved_at=retrieved_at,
        )
    print(
        json.dumps(
            {
                "dataset_type": "disruptions",
                "record_count": len(result.records),
                "page_count": len(result.pages),
                "snapshot_dir": str(snapshot),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
