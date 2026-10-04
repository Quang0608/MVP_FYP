"""Normalize raw PortWatch daily chokepoint pages to canonical checkpoints."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .client import load_raw_records
from .mapping import resolve_checkpoints
from .validate import (
    CHECKPOINT_NUMERIC_COLUMNS,
    CHECKPOINT_REQUIRED_COLUMNS,
    CHECKPOINT_SOURCE_COLUMNS,
    CanonicalCheckpointMonitoring,
    missing_dates,
    parse_observation_dates,
    validate_source_records,
    write_report,
)


OUTPUT_COLUMNS = [
    "checkpoint_id",
    "observation_date",
    "vessel_count_total",
    "vessel_count_container",
    "vessel_count_dry_bulk",
    "vessel_count_general_cargo",
    "vessel_count_roro",
    "vessel_count_tanker",
    "capacity_total",
    "capacity_container",
    "capacity_dry_bulk",
    "capacity_general_cargo",
    "capacity_roro",
    "capacity_tanker",
    "source_checkpoint_id",
    "source",
    "ingested_at",
]
CHECKPOINT_FIELD_MAP = {
    "vessel_count_total": "n_total",
    "vessel_count_container": "n_container",
    "vessel_count_dry_bulk": "n_dry_bulk",
    "vessel_count_general_cargo": "n_general_cargo",
    "vessel_count_roro": "n_roro",
    "vessel_count_tanker": "n_tanker",
    "capacity_total": "capacity",
    "capacity_container": "capacity_container",
    "capacity_dry_bulk": "capacity_dry_bulk",
    "capacity_general_cargo": "capacity_general_cargo",
    "capacity_roro": "capacity_roro",
    "capacity_tanker": "capacity_tanker",
}


def _extraction_dirs(root: Path, input_dir: Path | None) -> list[Path]:
    if input_dir is not None:
        return [input_dir]
    return sorted(
        path
        for path in (root / "checkpoints").glob("*_*" )
        if path.is_dir() and (path / "response.json").exists()
    )


def _number(value: Any) -> float | None:
    if value is None or value == "" or pd.isna(value):
        return None
    return float(value)


def _metadata_range(metadata: list[dict[str, Any]]) -> tuple[date, date]:
    starts = [date.fromisoformat(item["start_date"]) for item in metadata]
    ends = [date.fromisoformat(item["end_date"]) for item in metadata]
    return min(starts), max(ends)


def normalize_checkpoints(
    input_dir: Path | None = None,
    *,
    raw_root: Path = Path("data/raw/portwatch"),
    mapping_path: Path = Path("data/mappings/portwatch_checkpoint_mapping.csv"),
    output_path: Path = Path("data/processed/portwatch/checkpoint_monitoring.parquet"),
    report_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normalize one extraction or all saved checkpoint extractions."""

    directories = _extraction_dirs(raw_root, input_dir)
    if not directories:
        raise FileNotFoundError("No saved PortWatch checkpoint extraction was found")
    records: list[dict[str, Any]] = []
    record_ingested_at: list[str] = []
    metadata: list[dict[str, Any]] = []
    for directory in directories:
        extraction_records, extraction_metadata = load_raw_records(directory)
        records.extend(extraction_records)
        record_ingested_at.extend(
            [extraction_metadata["retrieved_at"]] * len(extraction_records)
        )
        metadata.append(extraction_metadata)

    warnings = validate_source_records(
        records,
        expected_columns=CHECKPOINT_REQUIRED_COLUMNS,
        numeric_columns=CHECKPOINT_NUMERIC_COLUMNS,
        allowed_columns=CHECKPOINT_SOURCE_COLUMNS,
    )
    unexpected_columns = set().union(*(record.keys() for record in records)) - CHECKPOINT_SOURCE_COLUMNS
    if unexpected_columns:
        warnings.append(
            "Unexpected source columns: " + ", ".join(sorted(unexpected_columns))
        )
    observation_dates = parse_observation_dates(records)
    if observation_dates.isna().any():
        raise ValueError("PortWatch records contain invalid or missing observation dates")

    resolved, _, unresolved = resolve_checkpoints(
        records,
        mapping_path=mapping_path,
    )
    rows: list[dict[str, Any]] = []
    for record, observation_date, ingested_at in zip(
        records, observation_dates, record_ingested_at, strict=True
    ):
        source_checkpoint_id = str(record.get("portid", "")).strip()
        checkpoint_id = resolved.get(source_checkpoint_id)
        if not checkpoint_id:
            continue
        row: dict[str, Any] = {
            "checkpoint_id": checkpoint_id,
            "observation_date": observation_date,
            "source_checkpoint_id": source_checkpoint_id,
            "source": "PORTWATCH",
            "ingested_at": ingested_at,
        }
        row.update(
            {
                output_column: _number(record.get(source_column))
                for output_column, source_column in CHECKPOINT_FIELD_MAP.items()
            }
        )
        rows.append(row)

    normalized = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    duplicate_mask = normalized.duplicated(
        subset=["source_checkpoint_id", "observation_date"], keep="first"
    )
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count:
        warnings.append(
            f"Dropped {duplicate_count} duplicate source checkpoint/date records after retaining the first."
        )
        normalized = normalized.loc[~duplicate_mask].copy()

    validated_rows = [
        CanonicalCheckpointMonitoring.model_validate(
            {key: (None if pd.isna(value) else value) for key, value in row.items()}
        ).model_dump()
        for row in normalized.to_dict(orient="records")
    ]
    normalized = pd.DataFrame(validated_rows, columns=OUTPUT_COLUMNS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_parquet(output_path, index=False, engine="pyarrow")

    start_date, end_date = _metadata_range(metadata)
    report = {
        "source": "IMF_PORTWATCH",
        "dataset_type": "checkpoints",
        "requested_dates": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "raw_record_count": len(records),
        "processed_record_count": len(normalized),
        "matched_ports": 0,
        "unresolved_ports": 0,
        "matched_checkpoints": len(resolved),
        "unresolved_checkpoints": len(unresolved),
        "unresolved_checkpoint_records": unresolved,
        "missing_dates": missing_dates(observation_dates, start_date, end_date),
        "validation_warnings": warnings,
        "raw_extractions": [item.get("request", {}) for item in metadata],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    report_path = report_path or output_path.with_name("checkpoint_monitoring_report.json")
    write_report(report_path, report)
    return normalized, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/portwatch"))
    parser.add_argument("--mapping-path", type=Path, default=Path("data/mappings/portwatch_checkpoint_mapping.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/portwatch/checkpoint_monitoring.parquet"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result, report = normalize_checkpoints(
        args.input_dir,
        raw_root=args.raw_root,
        mapping_path=args.mapping_path,
        output_path=args.output,
        report_path=args.report,
    )
    print(json.dumps({"processed_record_count": len(result), "report": report}, indent=2))


if __name__ == "__main__":
    main()
