"""Validate canonical PortWatch disruption and affected-port outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .validate import CanonicalDisruption, CanonicalDisruptionAffectedPort, write_report


def validate_disruptions(
    disruptions_path: Path = Path("data/processed/portwatch/disruptions.parquet"),
    affected_ports_path: Path = Path(
        "data/processed/portwatch/disruption_affected_ports.parquet"
    ),
    *,
    wpi_path: Path = Path("data/processed/ports/port_master.parquet"),
    current_path: Path = Path("data/processed/portwatch/current_disruptions.parquet"),
    report_path: Path | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    disruptions = pd.read_parquet(disruptions_path)
    affected = pd.read_parquet(affected_ports_path)
    wpi = pd.read_parquet(wpi_path)

    if disruptions["event_id"].duplicated().any():
        warnings.append("Duplicate event_id values detected in disruptions.parquet")
    for row_number, row in enumerate(disruptions.to_dict(orient="records"), start=1):
        values = {key: (None if pd.isna(value) else value) for key, value in row.items()}
        try:
            CanonicalDisruption.model_validate(values)
        except Exception as exc:
            warnings.append(f"Invalid disruption row {row_number}: {exc}")

    if affected.duplicated(subset=["event_id", "location_id"]).any():
        warnings.append("Duplicate event_id/location_id relations detected")
    valid_locations = set(wpi["location_id"].astype(str))
    for row_number, row in enumerate(affected.to_dict(orient="records"), start=1):
        values = {key: (None if pd.isna(value) else value) for key, value in row.items()}
        try:
            CanonicalDisruptionAffectedPort.model_validate(values)
        except Exception as exc:
            warnings.append(f"Invalid affected-port row {row_number}: {exc}")
        if str(row.get("location_id")) not in valid_locations:
            warnings.append(
                f"Affected-port row {row_number} references unknown location_id "
                f"{row.get('location_id')}"
            )

    active_count = 0
    if current_path.exists():
        active_count = len(pd.read_parquet(current_path))
    normalize_report_path = disruptions_path.with_name("disruptions_report.json")
    mapping_report_path = affected_ports_path.with_name("disruption_mapping_report.json")
    normalize_report = (
        json.loads(normalize_report_path.read_text(encoding="utf-8"))
        if normalize_report_path.exists()
        else {}
    )
    mapping_report = (
        json.loads(mapping_report_path.read_text(encoding="utf-8"))
        if mapping_report_path.exists()
        else {}
    )
    report = {
        "raw_records": normalize_report.get("raw_records"),
        "normalized_records": len(disruptions),
        "active_disruptions": active_count,
        "resolved_affected_ports": len(affected),
        "unresolved_affected_ports": mapping_report.get("unresolved_affected_ports"),
        "validation_warnings": warnings,
        "valid": not warnings,
    }
    report_path = report_path or disruptions_path.with_name("disruptions_ingestion_report.json")
    write_report(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disruptions", type=Path, default=Path("data/processed/portwatch/disruptions.parquet"))
    parser.add_argument("--affected-ports", type=Path, default=Path("data/processed/portwatch/disruption_affected_ports.parquet"))
    parser.add_argument("--wpi-path", type=Path, default=Path("data/processed/ports/port_master.parquet"))
    parser.add_argument("--current", type=Path, default=Path("data/processed/portwatch/current_disruptions.parquet"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_disruptions(
        args.disruptions,
        args.affected_ports,
        wpi_path=args.wpi_path,
        current_path=args.current,
        report_path=args.report,
    )
    print(json.dumps(report, indent=2))
    if not report["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
