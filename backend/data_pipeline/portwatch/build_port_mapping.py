"""Build the persistent WPI-to-PortWatch mapping and review queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import load_raw_records
from .mapping import build_port_mapping


def _extraction_dirs(raw_root: Path, input_dir: Path | None) -> list[Path]:
    if input_dir is not None:
        return [input_dir]
    return sorted(
        path
        for path in (raw_root / "ports").glob("*_*")
        if path.is_dir() and (path / "response.json").exists()
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the persistent WPI-to-PortWatch port mapping."
    )
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/portwatch"))
    parser.add_argument("--wpi-path", type=Path, default=Path("data/processed/wpi/ports.parquet"))
    parser.add_argument(
        "--mapping-path",
        type=Path,
        default=Path("data/mappings/wpi_portwatch_port_mapping.csv"),
    )
    parser.add_argument(
        "--review-path",
        type=Path,
        default=Path("data/mappings/wpi_portwatch_review_queue.csv"),
    )
    args = parser.parse_args()

    directories = _extraction_dirs(args.raw_root, args.input_dir)
    if not directories:
        raise FileNotFoundError("No saved PortWatch port extraction was found")
    records = []
    for directory in directories:
        extraction_records, _ = load_raw_records(directory)
        records.extend(extraction_records)

    mapping, review = build_port_mapping(
        records,
        wpi_path=args.wpi_path,
        mapping_path=args.mapping_path,
        review_path=args.review_path,
    )
    print(
        json.dumps(
            {
                "source_records": len(records),
                "mapping_rows": len(mapping),
                "auto_or_confirmed": int(
                    mapping.mapping_status.isin(
                        {"AUTO_MATCHED", "CONFIRMED", "MANUAL_CONFIRMED"}
                    ).sum()
                ),
                "review_rows": len(review),
                "mapping_path": str(args.mapping_path),
                "review_path": str(args.review_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
