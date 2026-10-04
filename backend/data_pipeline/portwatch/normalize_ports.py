"""Normalize raw PortWatch daily port pages to canonical Parquet."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .client import load_raw_records
from .build_port_master import resolve_port_master
from .mapping import resolve_ports
from .validate import (
    PORT_NUMERIC_COLUMNS,
    PORT_REQUIRED_COLUMNS,
    PORT_SOURCE_COLUMNS,
    CanonicalPortMonitoring,
    missing_dates,
    parse_observation_dates,
    validate_source_records,
    write_report,
)


OUTPUT_COLUMNS = [
    "location_id",
    "observation_date",
    "port_calls_total",
    "port_calls_container",
    "port_calls_dry_bulk",
    "port_calls_general_cargo",
    "port_calls_roro",
    "port_calls_tanker",
    "import_total",
    "import_container",
    "import_dry_bulk",
    "import_general_cargo",
    "import_roro",
    "import_tanker",
    "export_total",
    "export_container",
    "export_dry_bulk",
    "export_general_cargo",
    "export_roro",
    "export_tanker",
    "source_port_id",
    "source",
    "ingested_at",
]
SOURCE_LINK_COLUMNS = ["location_id", "observation_date", "source_port_id"]
PORT_FIELD_MAP = {
    "port_calls_total": "portcalls",
    "port_calls_container": "portcalls_container",
    "port_calls_dry_bulk": "portcalls_dry_bulk",
    "port_calls_general_cargo": "portcalls_general_cargo",
    "port_calls_roro": "portcalls_roro",
    "port_calls_tanker": "portcalls_tanker",
    "import_total": "import",
    "import_container": "import_container",
    "import_dry_bulk": "import_dry_bulk",
    "import_general_cargo": "import_general_cargo",
    "import_roro": "import_roro",
    "import_tanker": "import_tanker",
    "export_total": "export",
    "export_container": "export_container",
    "export_dry_bulk": "export_dry_bulk",
    "export_general_cargo": "export_general_cargo",
    "export_roro": "export_roro",
    "export_tanker": "export_tanker",
}


def _extraction_dirs(root: Path, input_dir: Path | None) -> list[Path]:
    if input_dir is not None:
        return [input_dir]
    return sorted(
        path
        for path in (root / "ports").glob("*_*" )
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


def _collapse_canonical_duplicates(
    normalized: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Aggregate multiple provider IDs that resolve to one port/date."""

    if normalized.empty:
        return normalized, pd.DataFrame(columns=SOURCE_LINK_COLUMNS), 0
    links = normalized[SOURCE_LINK_COLUMNS].drop_duplicates().copy()
    duplicate_mask = normalized.duplicated(
        subset=["location_id", "observation_date"], keep=False
    )
    duplicate_count = int(duplicate_mask.sum())
    if not duplicate_count:
        return normalized, links, 0

    numeric_columns = [
        column
        for column in OUTPUT_COLUMNS
        if column not in {"location_id", "observation_date", "source_port_id", "source", "ingested_at"}
    ]
    rows: list[dict[str, Any]] = []
    for (location_id, observation_date), group in normalized.groupby(
        ["location_id", "observation_date"], sort=False
    ):
        row: dict[str, Any] = {
            "location_id": location_id,
            "observation_date": observation_date,
            "source_port_id": (
                group["source_port_id"].iloc[0]
                if group["source_port_id"].nunique() == 1
                else None
            ),
            "source": "PORTWATCH",
            "ingested_at": group["ingested_at"].max(),
        }
        for column in numeric_columns:
            row[column] = group[column].sum(min_count=1)
        rows.append(row)
    collapsed = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    return collapsed, links, duplicate_count


def normalize_ports(
    input_dir: Path | None = None,
    *,
    raw_root: Path = Path("data/raw/portwatch"),
    wpi_path: Path = Path("data/processed/wpi/ports.parquet"),
    mapping_path: Path | None = None,
    port_master_mapping_path: Path = Path("data/mappings/port_master_mapping.csv"),
    output_path: Path = Path("data/processed/portwatch/port_monitoring.parquet"),
    report_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normalize one extraction or all saved port extractions."""

    directories = _extraction_dirs(raw_root, input_dir)
    if not directories:
        raise FileNotFoundError("No saved PortWatch port extraction was found")
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
        expected_columns=PORT_REQUIRED_COLUMNS,
        numeric_columns=PORT_NUMERIC_COLUMNS,
        allowed_columns=PORT_SOURCE_COLUMNS,
    )
    unexpected_columns = set().union(*(record.keys() for record in records)) - PORT_SOURCE_COLUMNS
    if unexpected_columns:
        warnings.append(
            "Unexpected source columns: " + ", ".join(sorted(unexpected_columns))
        )
    observation_dates = parse_observation_dates(records)
    if observation_dates.isna().any():
        raise ValueError("PortWatch records contain invalid or missing observation dates")

    if mapping_path is None:
        if not port_master_mapping_path.exists():
            raise FileNotFoundError(
                "Unified port master mapping not found. Run "
                "backend.data_pipeline.portwatch.build_port_master first."
            )
        resolved, unresolved = resolve_port_master(
            records,
            mapping_path=port_master_mapping_path,
        )
        mapping_table = pd.read_csv(
            port_master_mapping_path, dtype=str, keep_default_na=False
        )
        effective_mapping_path = port_master_mapping_path
    else:
        resolved, mapping_table, unresolved = resolve_ports(
            records,
            mapping_path=mapping_path,
        )
        effective_mapping_path = mapping_path
    rows: list[dict[str, Any]] = []
    for record, observation_date, ingested_at in zip(
        records, observation_dates, record_ingested_at, strict=True
    ):
        source_port_id = str(record.get("portid", "")).strip()
        location_id = resolved.get(source_port_id)
        if not location_id:
            continue
        row: dict[str, Any] = {
            "location_id": location_id,
            "observation_date": observation_date,
            "source_port_id": source_port_id,
            "source": "PORTWATCH",
            "ingested_at": ingested_at,
        }
        row.update(
            {
                output_column: _number(record.get(source_column))
                for output_column, source_column in PORT_FIELD_MAP.items()
            }
        )
        rows.append(row)

    normalized = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    duplicate_mask = normalized.duplicated(
        subset=["source_port_id", "observation_date"], keep="first"
    )
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count:
        warnings.append(
            f"Dropped {duplicate_count} duplicate source port/date records after retaining the first."
        )
        normalized = normalized.loc[~duplicate_mask].copy()

    normalized, source_links, canonical_duplicate_count = _collapse_canonical_duplicates(
        normalized
    )
    if canonical_duplicate_count:
        warnings.append(
            "Aggregated "
            f"{canonical_duplicate_count} source rows sharing one canonical location/date."
        )

    validated_rows = [
        CanonicalPortMonitoring.model_validate(
            {key: (None if pd.isna(value) else value) for key, value in row.items()}
        ).model_dump()
        for row in normalized.to_dict(orient="records")
    ]
    normalized = pd.DataFrame(validated_rows, columns=OUTPUT_COLUMNS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_parquet(output_path, index=False, engine="pyarrow")
    source_links.to_parquet(
        output_path.with_name("port_monitoring_source_links.parquet"),
        index=False,
        engine="pyarrow",
    )

    start_date, end_date = _metadata_range(metadata)
    report = {
        "source": "IMF_PORTWATCH",
        "dataset_type": "ports",
        "requested_dates": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "raw_record_count": len(records),
        "processed_record_count": len(normalized),
        "matched_ports": len(resolved),
        "matched_wpi_ports": int(
            (mapping_table["status"] == "MATCHED_WPI").sum()
        )
        if "status" in mapping_table.columns
        else len(resolved),
        "source_native_ports": int(
            (mapping_table["status"] == "SOURCE_NATIVE").sum()
        )
        if "status" in mapping_table.columns
        else 0,
        "canonical_duplicate_rows_aggregated": canonical_duplicate_count,
        "source_link_records": len(source_links),
        "unresolved_ports": len(unresolved),
        "unresolved_port_records": unresolved,
        "mapping_path": str(effective_mapping_path),
        "mapping_status_counts": (
            mapping_table["status"].value_counts().to_dict()
            if "status" in mapping_table.columns
            else mapping_table["mapping_status"].value_counts().to_dict()
        ),
        "matched_checkpoints": 0,
        "missing_dates": missing_dates(observation_dates, start_date, end_date),
        "validation_warnings": warnings,
        "raw_extractions": [item.get("request", {}) for item in metadata],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    report_path = report_path or output_path.with_name("port_monitoring_report.json")
    write_report(report_path, report)
    return normalized, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/portwatch"))
    parser.add_argument("--wpi-path", type=Path, default=Path("data/processed/wpi/ports.parquet"))
    parser.add_argument("--mapping-path", type=Path)
    parser.add_argument(
        "--port-master-mapping",
        type=Path,
        default=Path("data/mappings/port_master_mapping.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("data/processed/portwatch/port_monitoring.parquet"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result, report = normalize_ports(
        args.input_dir,
        raw_root=args.raw_root,
        wpi_path=args.wpi_path,
        mapping_path=args.mapping_path,
        port_master_mapping_path=args.port_master_mapping,
        output_path=args.output,
        report_path=args.report,
    )
    print(json.dumps({"processed_record_count": len(result), "report": report}, indent=2))


if __name__ == "__main__":
    main()
