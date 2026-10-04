"""Normalize immutable PortWatch disruption snapshots to canonical Parquet."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .client import load_raw_disruption_records
from .validate import (
    DISRUPTION_REQUIRED_COLUMNS,
    DISRUPTION_SOURCE_COLUMNS,
    CanonicalDisruption,
    validate_source_records,
    write_report,
)


OUTPUT_COLUMNS = [
    "event_id",
    "event_type",
    "event_name",
    "description",
    "alert_level",
    "severity_text",
    "country",
    "start_time",
    "end_time",
    "last_updated",
    "latitude",
    "longitude",
    "affected_ports_raw",
    "affected_port_count",
    "affected_population",
    "source_page_id",
    "source",
    "ingested_at",
]
COMPARE_COLUMNS = [
    "alert_level",
    "severity_text",
    "start_time",
    "end_time",
    "affected_ports_raw",
    "last_updated",
]


def _snapshot_dirs(root: Path, input_dir: Path | None) -> list[Path]:
    if input_dir is not None:
        return [input_dir]
    disruptions_root = root / "disruptions"
    if not disruptions_root.exists():
        return []
    return sorted(
        path
        for path in disruptions_root.iterdir()
        if path.is_dir() and (path / "response.json").exists()
    )


def _text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any) -> float | None:
    if value is None or value == "" or pd.isna(value):
        return None
    return float(value)


def _integer(value: Any) -> int | None:
    number = _number(value)
    if number is None:
        return None
    if number != int(number):
        raise ValueError(f"Expected an integer value, received {value!r}")
    return int(number)


def _timestamp(value: Any) -> datetime | None:
    if value is None or value == "" or pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed = pd.to_datetime(value, unit="ms", errors="coerce", utc=True)
    else:
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        raise ValueError(f"Invalid PortWatch timestamp: {value!r}")
    return parsed.to_pydatetime()


def _affected_ports_text(value: Any) -> str | None:
    if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _normalize_record(record: dict[str, Any], ingested_at: str) -> dict[str, Any]:
    event_id = _text(record.get("eventid"))
    if not event_id:
        raise ValueError("PortWatch disruption record is missing eventid")
    normalized = {
        "event_id": event_id,
        "event_type": _text(record.get("eventtype")),
        "event_name": _text(record.get("eventname")),
        "description": _text(record.get("htmldescription")),
        "alert_level": _text(record.get("alertlevel")),
        "severity_text": _text(record.get("severitytext")),
        "country": _text(record.get("country")),
        "start_time": _timestamp(record.get("fromdate")),
        "end_time": _timestamp(record.get("todate")),
        "last_updated": _timestamp(record.get("editdate")),
        "latitude": _number(record.get("lat")),
        "longitude": _number(record.get("long")),
        "affected_ports_raw": _affected_ports_text(record.get("affectedports")),
        "affected_port_count": _integer(record.get("n_affectedports")),
        "affected_population": _text(record.get("affectedpopulation")),
        "source_page_id": _text(record.get("pageid")),
        "source": "PORTWATCH",
        "ingested_at": _timestamp(ingested_at),
    }
    return CanonicalDisruption.model_validate(normalized).model_dump()


def _value_equal(left: Any, right: Any) -> bool:
    if left is None or pd.isna(left):
        return right is None or pd.isna(right)
    if right is None or pd.isna(right):
        return False
    if isinstance(left, pd.Timestamp):
        left = left.to_pydatetime()
    if isinstance(right, pd.Timestamp):
        right = right.to_pydatetime()
    return left == right


def _is_same(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(_value_equal(left.get(column), right.get(column)) for column in COMPARE_COLUMNS)


def _recency(row: dict[str, Any]) -> datetime:
    return row.get("last_updated") or row.get("ingested_at") or datetime.min.replace(
        tzinfo=timezone.utc
    )


def _deduplicate_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        previous = latest.get(row["event_id"])
        if previous is None or _recency(row) >= _recency(previous):
            latest[row["event_id"]] = row
    return list(latest.values())


def _load_existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    frame = pd.read_parquet(path)
    return {
        str(row["event_id"]): row
        for row in frame.to_dict(orient="records")
        if _text(row.get("event_id"))
    }


def normalize_disruptions(
    input_dir: Path | None = None,
    *,
    raw_root: Path = Path("data/raw/portwatch"),
    output_path: Path = Path("data/processed/portwatch/disruptions.parquet"),
    report_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normalize all snapshots and merge events by stable ``event_id``."""

    directories = _snapshot_dirs(raw_root, input_dir)
    records: list[dict[str, Any]] = []
    record_ingested_at: list[str] = []
    metadata: list[dict[str, Any]] = []
    for directory in directories:
        extraction_records, extraction_metadata = load_raw_disruption_records(directory)
        records.extend(extraction_records)
        record_ingested_at.extend(
            [str(extraction_metadata["retrieved_at"])] * len(extraction_records)
        )
        metadata.append(extraction_metadata)

    warnings: list[str] = []
    if records:
        warnings.extend(
            validate_source_records(
                records,
                expected_columns=DISRUPTION_REQUIRED_COLUMNS,
                numeric_columns={"n_affectedports"},
                allowed_columns=DISRUPTION_SOURCE_COLUMNS,
            )
        )
        observed = set().union(*(record.keys() for record in records))
        unexpected = observed - DISRUPTION_SOURCE_COLUMNS
        if unexpected:
            warnings.append("Unexpected source columns: " + ", ".join(sorted(unexpected)))
    else:
        warnings.append("No PortWatch disruption records were found in the selected snapshots.")

    candidate_rows = []
    for record, ingested_at in zip(records, record_ingested_at, strict=True):
        candidate_rows.append(_normalize_record(record, ingested_at))
    candidate_rows = _deduplicate_candidates(candidate_rows)

    existing = _load_existing(output_path)
    new_count = 0
    updated_count = 0
    unchanged_count = 0
    stale_count = 0
    for candidate in candidate_rows:
        previous = existing.get(candidate["event_id"])
        if previous is None:
            existing[candidate["event_id"]] = candidate
            new_count += 1
            continue
        if _recency(candidate) < _recency(previous):
            stale_count += 1
            continue
        if _is_same(candidate, previous):
            unchanged_count += 1
            continue
        existing[candidate["event_id"]] = candidate
        updated_count += 1

    rows = list(existing.values())
    normalized = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if not normalized.empty:
        validated_rows = [
            CanonicalDisruption.model_validate(
                {key: (None if pd.isna(value) else value) for key, value in row.items()}
            ).model_dump()
            for row in normalized.to_dict(orient="records")
        ]
        normalized = pd.DataFrame(validated_rows, columns=OUTPUT_COLUMNS)
        normalized = normalized.sort_values("event_id").reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_parquet(output_path, index=False, engine="pyarrow")

    report = {
        "source": "IMF_PORTWATCH",
        "dataset_type": "disruptions",
        "raw_records": len(records),
        "normalized_records": len(normalized),
        "new_events": new_count,
        "updated_events": updated_count,
        "unchanged_events": unchanged_count,
        "ignored_stale_events": stale_count,
        "validation_warnings": warnings,
        "raw_snapshots": [item.get("retrieved_at") for item in metadata],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    report_path = report_path or output_path.with_name("disruptions_report.json")
    write_report(report_path, report)
    return normalized, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/portwatch"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/portwatch/disruptions.parquet"),
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result, report = normalize_disruptions(
        args.input_dir,
        raw_root=args.raw_root,
        output_path=args.output,
        report_path=args.report,
    )
    print(json.dumps({"normalized_records": len(result), "report": report}, indent=2))


if __name__ == "__main__":
    main()
