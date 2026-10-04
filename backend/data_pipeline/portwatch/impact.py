"""Helpers for joining current PortWatch state to the deterministic runtime."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_current_port_state(
    path: Path = Path("data/processed/portwatch/current_port_state.parquet"),
) -> dict[str, dict[str, object]]:
    """Load current state keyed by canonical WPI ``location_id``.

    The state file is a read-only input to graph annotation. Duplicate current
    rows are rejected so a shipment cannot receive an ambiguous port status.
    """

    frame = pd.read_parquet(path)
    if frame["location_id"].duplicated().any():
        raise ValueError("current port state contains duplicate location_id values")
    return {
        str(row["location_id"]): row
        for row in frame.to_dict(orient="records")
    }


def load_current_disruption_state(
    disruptions_path: Path = Path(
        "data/processed/portwatch/current_disruptions.parquet"
    ),
    affected_ports_path: Path = Path(
        "data/processed/portwatch/disruption_affected_ports.parquet"
    ),
) -> list[dict[str, object]]:
    """Expose current disruptions with canonical affected location IDs only."""

    disruptions = pd.read_parquet(disruptions_path)
    relations = pd.read_parquet(affected_ports_path)
    if relations.duplicated(subset=["event_id", "location_id"]).any():
        raise ValueError("affected-port relations contain duplicate event/location rows")
    locations_by_event = (
        relations.groupby("event_id")["location_id"].apply(list).to_dict()
        if not relations.empty
        else {}
    )
    state = []
    for row in disruptions.to_dict(orient="records"):
        event_id = str(row["event_id"])
        state.append(
            {
                "event_id": event_id,
                "event_type": row.get("event_type"),
                "event_name": row.get("event_name"),
                "description": row.get("description"),
                "alert_level": row.get("alert_level"),
                "severity_text": row.get("severity_text"),
                "start_time": row.get("start_time"),
                "end_time": row.get("end_time"),
                "affected_location_ids": locations_by_event.get(event_id, []),
                "source": "PORTWATCH",
                "is_active": True,
            }
        )
    return state
