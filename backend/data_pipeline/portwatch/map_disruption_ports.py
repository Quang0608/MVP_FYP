"""Resolve PortWatch affected-port values to canonical WPI locations."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .mapping import (
    AUTO_MAPPING_STATUSES,
    _country_group_key,
    normalize_name,
)
from .validate import CanonicalDisruptionAffectedPort, write_report


OUTPUT_COLUMNS = [
    "event_id",
    "location_id",
    "source_port_id",
    "source_port_name",
    "match_method",
    "match_confidence",
]
MANUAL_COLUMNS = [
    "event_id",
    "source_port_name",
    "canonical_location_id",
    "match_method",
    "match_confidence",
]


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def parse_affected_ports(value: Any) -> list[str]:
    """Parse observed list-like and delimiter-separated source values."""

    text = _text(value)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    if isinstance(parsed, dict):
        values = parsed.get("ports") or parsed.get("affectedports")
        if isinstance(values, list):
            return [str(item).strip() for item in values if str(item).strip()]
    tokens = re.split(r"[;|\n]+", text)
    if len(tokens) == 1 and "," in text:
        tokens = text.split(",")
    return [token.strip(" \t\"'[]()") for token in tokens if token.strip(" \t\"'[]()")]


def _load_manual(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype=str).fillna("")
    missing = set(MANUAL_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Manual disruption mapping is missing columns: {sorted(missing)}")
    return {
        (str(row["event_id"]).strip(), normalize_name(row["source_port_name"])): row.to_dict()
        for _, row in frame.iterrows()
        if str(row["event_id"]).strip() and normalize_name(row["source_port_name"])
    }


def _load_mapping(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype=str).fillna("")
    required = {"source_port_id", "canonical_location_id"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"PortWatch mapping is missing columns: {sorted(missing)}")
    status_column = "status" if "status" in frame.columns else "mapping_status"
    if status_column not in frame.columns:
        raise ValueError("PortWatch mapping is missing status/mapping_status")
    return {
        str(row["source_port_id"]).strip(): {
            **row.to_dict(),
            "_status": str(row[status_column]).strip(),
        }
        for _, row in frame.iterrows()
        if str(row["source_port_id"]).strip()
    }


def _wpi_indexes(wpi_path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    frame = pd.read_parquet(wpi_path).fillna("")
    required = {"location_id", "name", "country", "unlocode"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"WPI canonical ports are missing columns: {sorted(missing)}")
    by_name: dict[str, list[dict[str, Any]]] = {}
    by_unlocode: dict[str, list[dict[str, Any]]] = {}
    for row in frame.to_dict(orient="records"):
        name_key = normalize_name(row.get("name"))
        code_key = re.sub(r"[^A-Z0-9]", "", _text(row.get("unlocode")).upper())
        if name_key:
            by_name.setdefault(name_key, []).append(row)
        if code_key:
            by_unlocode.setdefault(code_key, []).append(row)
    return by_name, by_unlocode


def _country_matches(source: str, candidate: str) -> bool:
    if not source or not candidate:
        return False
    source_countries = {
        _country_group_key(part)
        for part in re.split(r"[,;|]", source)
        if part.strip()
    }
    return _country_group_key(candidate) in source_countries


def _code_from_token(token: str) -> str:
    matches = re.findall(r"\b[A-Za-z]{2}[A-Za-z0-9]{3}\b", token)
    return re.sub(r"[^A-Z0-9]", "", matches[0].upper()) if matches else ""


def _resolve_one(
    event_id: str,
    token: str,
    country: str,
    source_mapping: dict[str, dict[str, Any]],
    by_name: dict[str, list[dict[str, Any]]],
    by_unlocode: dict[str, list[dict[str, Any]]],
    manual: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    source_row = source_mapping.get(token)
    accepted_statuses = AUTO_MAPPING_STATUSES | {
        "MATCHED_WPI",
        "SOURCE_NATIVE",
        "MANUAL_MATCH",
    }
    if source_row and source_row.get("_status") in accepted_statuses:
        return {
            "location_id": source_row["canonical_location_id"],
            "source_port_id": token,
            "source_port_name": source_row.get("source_name") or token,
            "match_method": "PERSISTENT_SOURCE_ID",
            "match_confidence": 1.0,
        }

    code = _code_from_token(token)
    code_candidates = by_unlocode.get(code, [])
    if len(code_candidates) == 1:
        return {
            "location_id": code_candidates[0]["location_id"],
            "source_port_id": None,
            "source_port_name": token,
            "match_method": "UNLOCODE",
            "match_confidence": 1.0,
        }

    name_candidates = by_name.get(normalize_name(token), [])
    country_candidates = [
        candidate
        for candidate in name_candidates
        if _country_matches(country, _text(candidate.get("country")))
    ]
    if len(country_candidates) == 1:
        return {
            "location_id": country_candidates[0]["location_id"],
            "source_port_id": None,
            "source_port_name": token,
            "match_method": "NAME_COUNTRY",
            "match_confidence": 0.98,
        }

    manual_row = manual.get((event_id, normalize_name(token)))
    if manual_row:
        return {
            "location_id": manual_row["canonical_location_id"],
            "source_port_id": None,
            "source_port_name": token,
            "match_method": manual_row.get("match_method") or "MANUAL",
            "match_confidence": float(manual_row.get("match_confidence") or 1),
        }
    return None


def map_disruption_ports(
    input_path: Path = Path("data/processed/portwatch/disruptions.parquet"),
    output_path: Path = Path("data/processed/portwatch/disruption_affected_ports.parquet"),
    *,
    wpi_path: Path = Path("data/processed/wpi/ports.parquet"),
    source_mapping_path: Path = Path("data/mappings/port_master_mapping.csv"),
    manual_mapping_path: Path = Path("data/mappings/portwatch_disruption_port_mapping.csv"),
    report_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_parquet(input_path) if input_path.exists() else pd.DataFrame()
    source_mapping = _load_mapping(source_mapping_path)
    by_name, by_unlocode = _wpi_indexes(wpi_path)
    manual = _load_manual(manual_mapping_path)
    rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, str]] = []
    for record in frame.to_dict(orient="records"):
        event_id = _text(record.get("event_id"))
        tokens = parse_affected_ports(record.get("affected_ports_raw"))
        for token in tokens:
            match = _resolve_one(
                event_id,
                token,
                _text(record.get("country")),
                source_mapping,
                by_name,
                by_unlocode,
                manual,
            )
            if match is None:
                unresolved.append(
                    {
                        "event_id": event_id,
                        "source_port_name": token,
                        "country": _text(record.get("country")),
                        "reason": "No unique canonical WPI match was found.",
                    }
                )
                continue
            rows.append(
                CanonicalDisruptionAffectedPort(
                    event_id=event_id,
                    location_id=match["location_id"],
                    source_port_id=match.get("source_port_id"),
                    source_port_name=match.get("source_port_name") or token,
                    match_method=match["match_method"],
                    match_confidence=match["match_confidence"],
                ).model_dump()
            )

    relation = pd.DataFrame(rows, columns=OUTPUT_COLUMNS).drop_duplicates(
        subset=["event_id", "location_id"]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    relation.to_parquet(output_path, index=False, engine="pyarrow")
    report = {
        "source": "IMF_PORTWATCH",
        "dataset_type": "disruption_affected_ports",
        "normalized_records": len(frame),
        "resolved_affected_ports": len(relation),
        "unresolved_affected_ports": len(unresolved),
        "unresolved_records": unresolved,
        "validation_warnings": [],
    }
    report_path = report_path or output_path.with_name("disruption_mapping_report.json")
    write_report(report_path, report)
    return relation, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/portwatch/disruptions.parquet"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/portwatch/disruption_affected_ports.parquet"))
    parser.add_argument("--wpi-path", type=Path, default=Path("data/processed/wpi/ports.parquet"))
    parser.add_argument("--source-mapping", type=Path, default=Path("data/mappings/port_master_mapping.csv"))
    parser.add_argument("--manual-mapping", type=Path, default=Path("data/mappings/portwatch_disruption_port_mapping.csv"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result, report = map_disruption_ports(
        args.input,
        args.output,
        wpi_path=args.wpi_path,
        source_mapping_path=args.source_mapping,
        manual_mapping_path=args.manual_mapping,
        report_path=args.report,
    )
    print(json.dumps({"resolved_affected_ports": len(result), "report": report}, indent=2))


if __name__ == "__main__":
    main()
