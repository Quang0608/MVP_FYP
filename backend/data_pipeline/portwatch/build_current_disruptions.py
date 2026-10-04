"""Derive currently active PortWatch disruptions from source dates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _as_of(value: str | None) -> pd.Timestamp:
    if value:
        timestamp = pd.to_datetime(value, utc=True, errors="raise")
    else:
        timestamp = pd.Timestamp.now(tz="UTC")
    return timestamp


def build_current_disruptions(
    input_path: Path = Path("data/processed/portwatch/disruptions.parquet"),
    output_path: Path = Path("data/processed/portwatch/current_disruptions.parquet"),
    *,
    current_time: str | datetime | pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Write active records using only PortWatch start/end timestamps."""

    if not input_path.exists():
        raise FileNotFoundError(f"Canonical disruption file not found: {input_path}")
    frame = pd.read_parquet(input_path)
    if current_time is None:
        as_of = pd.Timestamp.now(tz="UTC")
    else:
        as_of = pd.to_datetime(current_time, utc=True, errors="raise")
    if frame.empty:
        current = frame.copy()
    else:
        starts = pd.to_datetime(frame["start_time"], utc=True, errors="coerce")
        ends = pd.to_datetime(frame["end_time"], utc=True, errors="coerce")
        active_mask = starts.notna() & starts.le(as_of) & (ends.isna() | ends.ge(as_of))
        current = frame.loc[active_mask].copy()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    current.to_parquet(output_path, index=False, engine="pyarrow")
    report = {
        "source": "IMF_PORTWATCH",
        "dataset_type": "current_disruptions",
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
        "historical_records": len(frame),
        "active_disruptions": len(current),
        "validation_warnings": [],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    report_path = output_path.with_name("current_disruptions_report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return current, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/portwatch/disruptions.parquet"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/portwatch/current_disruptions.parquet"))
    parser.add_argument("--as-of", type=str)
    args = parser.parse_args()
    result, report = build_current_disruptions(args.input, args.output, current_time=args.as_of)
    print(json.dumps({"active_disruptions": len(result), "report": report}, indent=2))


if __name__ == "__main__":
    main()
