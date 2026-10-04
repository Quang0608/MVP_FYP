"""Validation models and data-quality checks for PortWatch processing."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


PORT_SOURCE_COLUMNS = {
    "date",
    "year",
    "month",
    "day",
    "portid",
    "portname",
    "country",
    "ISO3",
    "portcalls_container",
    "portcalls_dry_bulk",
    "portcalls_general_cargo",
    "portcalls_roro",
    "portcalls_tanker",
    "portcalls_cargo",
    "portcalls",
    "import_container",
    "import_dry_bulk",
    "import_general_cargo",
    "import_roro",
    "import_tanker",
    "import_cargo",
    "import",
    "export_container",
    "export_dry_bulk",
    "export_general_cargo",
    "export_roro",
    "export_tanker",
    "export_cargo",
    "export",
    "ObjectId",
}
PORT_REQUIRED_COLUMNS = PORT_SOURCE_COLUMNS - {"ObjectId"}
CHECKPOINT_SOURCE_COLUMNS = {
    "date",
    "year",
    "month",
    "day",
    "portid",
    "portname",
    "n_container",
    "n_dry_bulk",
    "n_general_cargo",
    "n_roro",
    "n_tanker",
    "n_cargo",
    "n_total",
    "capacity_container",
    "capacity_dry_bulk",
    "capacity_general_cargo",
    "capacity_roro",
    "capacity_tanker",
    "capacity_cargo",
    "capacity",
    "ObjectId",
}
CHECKPOINT_REQUIRED_COLUMNS = CHECKPOINT_SOURCE_COLUMNS - {"ObjectId"}
DISRUPTION_SOURCE_COLUMNS = {
    "eventid",
    "eventtype",
    "eventname",
    "htmlname",
    "htmldescription",
    "alertlevel",
    "country",
    "fromdate",
    "year",
    "todate",
    "severitytext",
    "lat",
    "long",
    "editdate",
    "affectedports",
    "n_affectedports",
    "affectedpopulation",
    "pageid",
}
DISRUPTION_REQUIRED_COLUMNS = DISRUPTION_SOURCE_COLUMNS

PORT_NUMERIC_COLUMNS = {
    "portcalls_container",
    "portcalls_dry_bulk",
    "portcalls_general_cargo",
    "portcalls_roro",
    "portcalls_tanker",
    "portcalls_cargo",
    "portcalls",
    "import_container",
    "import_dry_bulk",
    "import_general_cargo",
    "import_roro",
    "import_tanker",
    "import_cargo",
    "import",
    "export_container",
    "export_dry_bulk",
    "export_general_cargo",
    "export_roro",
    "export_tanker",
    "export_cargo",
    "export",
}
CHECKPOINT_NUMERIC_COLUMNS = {
    "n_container",
    "n_dry_bulk",
    "n_general_cargo",
    "n_roro",
    "n_tanker",
    "n_cargo",
    "n_total",
    "capacity_container",
    "capacity_dry_bulk",
    "capacity_general_cargo",
    "capacity_roro",
    "capacity_tanker",
    "capacity_cargo",
    "capacity",
}


class CanonicalPortMonitoring(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str = Field(min_length=1)
    observation_date: date
    port_calls_total: float | None = Field(default=None, ge=0)
    port_calls_container: float | None = Field(default=None, ge=0)
    port_calls_dry_bulk: float | None = Field(default=None, ge=0)
    port_calls_general_cargo: float | None = Field(default=None, ge=0)
    port_calls_roro: float | None = Field(default=None, ge=0)
    port_calls_tanker: float | None = Field(default=None, ge=0)
    import_total: float | None = Field(default=None, ge=0)
    import_container: float | None = Field(default=None, ge=0)
    import_dry_bulk: float | None = Field(default=None, ge=0)
    import_general_cargo: float | None = Field(default=None, ge=0)
    import_roro: float | None = Field(default=None, ge=0)
    import_tanker: float | None = Field(default=None, ge=0)
    export_total: float | None = Field(default=None, ge=0)
    export_container: float | None = Field(default=None, ge=0)
    export_dry_bulk: float | None = Field(default=None, ge=0)
    export_general_cargo: float | None = Field(default=None, ge=0)
    export_roro: float | None = Field(default=None, ge=0)
    export_tanker: float | None = Field(default=None, ge=0)
    source_port_id: str | None = Field(default=None)
    source: Literal["PORTWATCH"]
    ingested_at: datetime


class CanonicalCheckpointMonitoring(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint_id: str = Field(min_length=1)
    observation_date: date
    vessel_count_total: float | None = Field(default=None, ge=0)
    vessel_count_container: float | None = Field(default=None, ge=0)
    vessel_count_dry_bulk: float | None = Field(default=None, ge=0)
    vessel_count_general_cargo: float | None = Field(default=None, ge=0)
    vessel_count_roro: float | None = Field(default=None, ge=0)
    vessel_count_tanker: float | None = Field(default=None, ge=0)
    capacity_total: float | None = Field(default=None, ge=0)
    capacity_container: float | None = Field(default=None, ge=0)
    capacity_dry_bulk: float | None = Field(default=None, ge=0)
    capacity_general_cargo: float | None = Field(default=None, ge=0)
    capacity_roro: float | None = Field(default=None, ge=0)
    capacity_tanker: float | None = Field(default=None, ge=0)
    source_checkpoint_id: str = Field(min_length=1)
    source: Literal["PORTWATCH"]
    ingested_at: datetime


class CanonicalDisruption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    event_type: str | None = None
    event_name: str | None = None
    description: str | None = None
    alert_level: str | None = None
    severity_text: str | None = None
    country: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    last_updated: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    affected_ports_raw: str | None = None
    affected_port_count: int | None = Field(default=None, ge=0)
    affected_population: str | None = None
    source_page_id: str | None = None
    source: Literal["PORTWATCH"]
    ingested_at: datetime


class CanonicalDisruptionAffectedPort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    source_port_id: str | None = None
    source_port_name: str = Field(min_length=1)
    match_method: str = Field(min_length=1)
    match_confidence: float = Field(ge=0, le=1)


def validate_source_records(
    records: list[dict[str, Any]],
    *,
    expected_columns: set[str],
    numeric_columns: set[str],
    allowed_columns: set[str] | None = None,
) -> list[str]:
    """Return warnings and raise for missing columns or negative metrics."""

    if not records:
        raise ValueError("PortWatch response contains no records")
    observed_columns = set().union(*(record.keys() for record in records))
    missing = expected_columns - observed_columns
    if missing:
        raise ValueError(
            "PortWatch response is missing columns: " + ", ".join(sorted(missing))
        )
    allowed_columns = allowed_columns or expected_columns
    unexpected_columns = observed_columns - allowed_columns
    warnings = [
        "Unexpected source columns: " + ", ".join(sorted(unexpected_columns))
    ] if unexpected_columns else []
    for record_number, record in enumerate(records, start=1):
        for column in numeric_columns:
            value = record.get(column)
            if value is not None and value != "" and float(value) < 0:
                raise ValueError(f"Negative {column} at source record {record_number}")
    return warnings


def parse_observation_dates(records: list[dict[str, Any]]) -> pd.Series:
    """Use PortWatch's date field, falling back to its Y/M/D fields."""

    direct = pd.to_datetime(
        pd.Series([record.get("date") for record in records]),
        errors="coerce",
        utc=True,
    )
    fallback = pd.to_datetime(
        {
            "year": pd.to_numeric([record.get("year") for record in records], errors="coerce"),
            "month": pd.to_numeric([record.get("month") for record in records], errors="coerce"),
            "day": pd.to_numeric([record.get("day") for record in records], errors="coerce"),
        },
        errors="coerce",
        utc=True,
    )
    return direct.fillna(fallback).dt.date


def missing_dates(observation_dates: pd.Series, start_date: date, end_date: date) -> list[str]:
    expected = {
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    }
    observed = {value for value in observation_dates.dropna()}
    return sorted(value.isoformat() for value in expected - observed)


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
