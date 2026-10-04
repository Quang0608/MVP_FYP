"""Build the unified WPI-preferred, multi-source canonical port master."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from ..validate_data import CanonicalPortMaster
from .mapping import AUTO_MAPPING_STATUSES


MASTER_COLUMNS = [
    "location_id",
    "name",
    "location_type",
    "country",
    "latitude",
    "longitude",
    "unlocode",
    "wpi_number",
    "canonical_source",
    "source_entity_id",
    "mapping_status",
    "source_port_id",
]
MAPPING_COLUMNS = [
    "source",
    "source_port_id",
    "source_name",
    "source_country",
    "canonical_location_id",
    "wpi_number",
    "match_method",
    "status",
]


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _source_native_id(source_port_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", source_port_id).strip("_")
    if not safe:
        raise ValueError(f"Cannot create source-native ID from {source_port_id!r}")
    return f"PW_PORT_{safe}"


def _load_source_mapping(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {
        "source_port_id",
        "source_port_name",
        "source_country",
        "wpi_number",
        "wpi_name",
        "wpi_country",
        "canonical_location_id",
        "match_method",
        "mapping_status",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Persistent PortWatch mapping is missing columns: {sorted(missing)}")
    return frame


def _validate_master(frame: pd.DataFrame) -> pd.DataFrame:
    records = []
    for row in frame.to_dict(orient="records"):
        values = {key: (None if pd.isna(value) else value) for key, value in row.items()}
        records.append(CanonicalPortMaster.model_validate(values).model_dump())
    validated = pd.DataFrame(records, columns=MASTER_COLUMNS)
    if validated["location_id"].duplicated().any():
        raise ValueError("Unified port master contains duplicate location_id values")
    return validated


def _build_sets(
    master: pd.DataFrame,
    routes_path: Path | None,
    shipments_path: Path | None,
    route_steps_path: Path | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    network_ids: set[str] = set()
    if routes_path and routes_path.exists():
        routes = pd.read_parquet(routes_path)
        for column in ("source_location_id", "destination_location_id"):
            if column in routes:
                network_ids.update(routes[column].dropna().astype(str))

    active_ids: set[str] = set()
    if shipments_path and shipments_path.exists():
        shipments = pd.read_parquet(shipments_path)
        for column in (
            "origin_location_id",
            "destination_location_id",
            "current_location_id",
        ):
            if column in shipments:
                active_ids.update(shipments[column].dropna().astype(str))
    if route_steps_path and route_steps_path.exists():
        steps = pd.read_parquet(route_steps_path)
        if "location_id" in steps:
            active_ids.update(steps["location_id"].dropna().astype(str))

    network = master[master["location_id"].isin(network_ids)].copy()
    active = master[master["location_id"].isin(active_ids)].copy()
    return network, active


def build_port_master(
    wpi_path: Path = Path("data/processed/wpi/ports.parquet"),
    source_mapping_path: Path = Path("data/mappings/wpi_portwatch_port_mapping.csv"),
    output_dir: Path = Path("data/processed/ports"),
    *,
    master_mapping_path: Path = Path("data/mappings/port_master_mapping.csv"),
    routes_path: Path | None = None,
    shipments_path: Path | None = None,
    route_steps_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    wpi = pd.read_parquet(wpi_path).copy()
    source_mapping = _load_source_mapping(source_mapping_path)
    wpi_required = {
        "location_id",
        "name",
        "country",
        "latitude",
        "longitude",
        "unlocode",
        "wpi_number",
    }
    missing = wpi_required - set(wpi.columns)
    if missing:
        raise ValueError(f"WPI port master is missing columns: {sorted(missing)}")

    rows: list[dict[str, Any]] = []
    wpi_by_id = {
        str(row["location_id"]): row for row in wpi.to_dict(orient="records")
    }
    for row in wpi.to_dict(orient="records"):
        rows.append(
            {
                "location_id": row["location_id"],
                "name": row["name"],
                "location_type": "PORT",
                "country": row["country"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "unlocode": row.get("unlocode"),
                "wpi_number": row["wpi_number"],
                "canonical_source": "WPI",
                "source_entity_id": row["wpi_number"],
                "mapping_status": "MATCHED_WPI",
                "source_port_id": None,
            }
        )

    mapping_rows: list[dict[str, Any]] = []
    source_native_count = 0
    skipped_count = 0
    matched_portwatch_ids: set[str] = set()
    for row in source_mapping.to_dict(orient="records"):
        source_id = _text(row.get("source_port_id"))
        source_name = _text(row.get("source_port_name"))
        source_country = _text(row.get("source_country"))
        if not source_id or not source_name or not source_country:
            skipped_count += 1
            continue
        mapped_location_id = _text(row.get("canonical_location_id"))
        source_status = _text(row.get("mapping_status"))
        accepted_wpi = (
            source_status in AUTO_MAPPING_STATUSES
            and mapped_location_id in wpi_by_id
        )
        if accepted_wpi:
            matched_portwatch_ids.add(source_id)
            mapping_status = (
                "MANUAL_MATCH"
                if source_status in {"CONFIRMED", "MANUAL_CONFIRMED"}
                else "MATCHED_WPI"
            )
            canonical_source = (
                "MANUAL_VALIDATED" if mapping_status == "MANUAL_MATCH" else "WPI"
            )
            canonical_location_id = mapped_location_id
            wpi_number = _text(row.get("wpi_number"))
        else:
            source_native_count += 1
            mapping_status = "SOURCE_NATIVE"
            canonical_source = "PORTWATCH"
            canonical_location_id = _source_native_id(source_id)
            wpi_number = ""
            rows.append(
                {
                    "location_id": canonical_location_id,
                    "name": source_name,
                    "location_type": "PORT",
                    "country": source_country,
                    "latitude": None,
                    "longitude": None,
                    "unlocode": None,
                    "wpi_number": None,
                    "canonical_source": canonical_source,
                    "source_entity_id": source_id,
                    "mapping_status": mapping_status,
                    "source_port_id": source_id,
                }
            )
        mapping_rows.append(
            {
                "source": "PORTWATCH",
                "source_port_id": source_id,
                "source_name": source_name,
                "source_country": source_country,
                "canonical_location_id": canonical_location_id,
                "wpi_number": wpi_number or None,
                "match_method": (
                    _text(row.get("match_method"))
                    if accepted_wpi
                    else "SOURCE_NATIVE"
                ),
                "status": mapping_status,
            }
        )

    master = _validate_master(pd.DataFrame(rows, columns=MASTER_COLUMNS))
    network, active = _build_sets(master, routes_path, shipments_path, route_steps_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    master.to_parquet(output_dir / "port_master.parquet", index=False, engine="pyarrow")
    master.to_parquet(output_dir / "canonical_ports.parquet", index=False, engine="pyarrow")
    network.to_parquet(output_dir / "network_ports.parquet", index=False, engine="pyarrow")
    active.to_parquet(output_dir / "active_route_ports.parquet", index=False, engine="pyarrow")
    master_mapping_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(mapping_rows, columns=MAPPING_COLUMNS).to_csv(
        master_mapping_path, index=False
    )
    report = {
        "wpi_ports": len(wpi),
        "portwatch_source_ids": len(source_mapping),
        "matched_wpi_source_ids": len(matched_portwatch_ids),
        "source_native_ports": source_native_count,
        "skipped_invalid_source_rows": skipped_count,
        "canonical_ports": len(master),
        "network_ports": len(network),
        "active_route_ports": len(active),
        "output_dir": str(output_dir),
        "master_mapping_path": str(master_mapping_path),
    }
    (output_dir / "port_master_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return master, report


def resolve_port_master(
    source_records: list[dict[str, Any]],
    mapping_path: Path = Path("data/mappings/port_master_mapping.csv"),
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Resolve every valid PortWatch source ID to a unified canonical ID."""

    mapping = pd.read_csv(mapping_path, dtype=str, keep_default_na=False)
    by_id = {
        _text(row["source_port_id"]): row for row in mapping.to_dict(orient="records")
    }
    resolved: dict[str, str] = {}
    unresolved: list[dict[str, str]] = []
    for record in source_records:
        source_id = _text(record.get("portid"))
        row = by_id.get(source_id)
        if row and _text(row.get("canonical_location_id")):
            resolved[source_id] = row["canonical_location_id"]
        else:
            unresolved.append(
                {
                    "source_port_id": source_id,
                    "source_port_name": _text(record.get("portname")),
                    "source_country": _text(record.get("country")),
                    "mapping_status": "UNRESOLVED",
                }
            )
    return resolved, unresolved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wpi-path", type=Path, default=Path("data/processed/wpi/ports.parquet"))
    parser.add_argument("--source-mapping", type=Path, default=Path("data/mappings/wpi_portwatch_port_mapping.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/ports"))
    parser.add_argument("--master-mapping", type=Path, default=Path("data/mappings/port_master_mapping.csv"))
    parser.add_argument("--routes-path", type=Path)
    parser.add_argument("--shipments-path", type=Path)
    parser.add_argument("--route-steps-path", type=Path)
    args = parser.parse_args()
    _, report = build_port_master(
        args.wpi_path,
        args.source_mapping,
        args.output_dir,
        master_mapping_path=args.master_mapping,
        routes_path=args.routes_path,
        shipments_path=args.shipments_path,
        route_steps_path=args.route_steps_path,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
