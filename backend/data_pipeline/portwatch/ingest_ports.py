"""Fetch and save PortWatch daily port monitoring data."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .client import PortWatchClient, save_raw_extraction


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--iso3", nargs="*", help="Optional ISO3 country filters")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/portwatch"))
    args = parser.parse_args()
    with PortWatchClient() as client:
        result = client.fetch("ports", args.start_date, args.end_date, args.iso3)
        extraction_dir = save_raw_extraction(
            dataset_type="ports",
            start_date=args.start_date,
            end_date=args.end_date,
            result=result,
            raw_root=args.raw_root,
        )
    print(
        json.dumps(
            {
                "dataset_type": "ports",
                "record_count": len(result.records),
                "page_count": len(result.pages),
                "extraction_dir": str(extraction_dir),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
