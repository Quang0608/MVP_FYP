"""Application adapter for normalized PortWatch state.

This module is the boundary between Parquet outputs and the live application.
API routes may ask this adapter for state, but services and routing code do not
read provider files directly.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ..domain import Location


DEFAULT_STATE_PATH = Path("data/processed/portwatch/current_port_state.parquet")
DEFAULT_DISRUPTIONS_PATH = Path(
    "data/processed/portwatch/current_disruptions.parquet"
)
DEFAULT_AFFECTED_PORTS_PATH = Path(
    "data/processed/portwatch/disruption_affected_ports.parquet"
)
DEFAULT_RUNTIME_MAPPING_PATH = Path("data/mappings/runtime_location_mapping.csv")

LEGACY_RUNTIME_PORT_ALIASES = {
    "LOC_WPI_50000": "P_SG",
    "LOC_WPI_49930": "P_KL",
    "LOC_WPI_51587": "P_TP",
    "LOC_WPI_57462": "P_LC",
}


def _optional_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


class PortWatchAdapter:
    """Read normalized PortWatch files and translate canonical IDs to runtime IDs."""

    def __init__(
        self,
        *,
        state_path: Path = DEFAULT_STATE_PATH,
        disruptions_path: Path = DEFAULT_DISRUPTIONS_PATH,
        affected_ports_path: Path = DEFAULT_AFFECTED_PORTS_PATH,
        runtime_mapping_path: Path = DEFAULT_RUNTIME_MAPPING_PATH,
    ) -> None:
        self.state_path = state_path
        self.disruptions_path = disruptions_path
        self.affected_ports_path = affected_ports_path
        self.runtime_mapping_path = runtime_mapping_path

    @classmethod
    def from_settings(cls, settings: Any) -> "PortWatchAdapter":
        """Build an adapter from application settings without requiring files."""

        if not settings.portwatch_enabled:
            missing_path = Path("__portwatch_disabled__")
            return cls(
                state_path=missing_path,
                disruptions_path=missing_path,
                affected_ports_path=missing_path,
                runtime_mapping_path=missing_path,
            )
        return cls(
            state_path=Path(settings.portwatch_state_path),
            disruptions_path=Path(settings.portwatch_disruptions_path),
            affected_ports_path=Path(settings.portwatch_affected_ports_path),
            runtime_mapping_path=Path(settings.runtime_location_mapping_path),
        )

    def _runtime_mapping(self) -> dict[str, str]:
        if not self.runtime_mapping_path.exists():
            return {}
        frame = pd.read_csv(self.runtime_mapping_path, dtype=str)
        required = {"runtime_location_id", "canonical_location_id"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(
                "Runtime location mapping is missing columns: "
                + ", ".join(sorted(missing))
            )
        if frame["runtime_location_id"].duplicated().any():
            raise ValueError("Runtime location mapping contains duplicate runtime IDs")
        return {
            str(row.runtime_location_id).strip(): str(row.canonical_location_id).strip()
            for row in frame.itertuples(index=False)
            if str(row.runtime_location_id).strip()
            and str(row.canonical_location_id).strip()
        }

    def load_current_port_state(self) -> dict[str, dict[str, object]]:
        """Return PortWatch state keyed by canonical location ID."""

        if not self.state_path.exists():
            return {}
        frame = pd.read_parquet(self.state_path)
        required = {"location_id", "source", "latest_observation_date"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(
                "Current PortWatch state is missing columns: "
                + ", ".join(sorted(missing))
            )
        if frame["location_id"].duplicated().any():
            raise ValueError("Current PortWatch state contains duplicate location IDs")
        return {
            str(row["location_id"]): {
                key: _optional_value(value) for key, value in row.items()
            }
            for row in frame.to_dict(orient="records")
        }

    def runtime_port_state(self) -> dict[str, dict[str, object]]:
        """Return current state keyed by runtime location ID for graph overlay."""

        canonical_state = self.load_current_port_state()
        mapping = self._runtime_mapping()
        runtime_state: dict[str, dict[str, object]] = {}
        for runtime_id, canonical_id in mapping.items():
            state = canonical_state.get(canonical_id)
            if state is None:
                continue
            runtime_state[runtime_id] = {
                **state,
                "canonical_location_id": canonical_id,
                "runtime_location_id": runtime_id,
            }
        return runtime_state

    def enrich_locations(self, locations: list[Location]) -> list[Location]:
        """Attach mapped PortWatch state to canonical runtime locations."""

        state_by_runtime_id = self.runtime_port_state()
        enriched = []
        for location in locations:
            state = state_by_runtime_id.get(location.location_id)
            if state is None:
                state = state_by_runtime_id.get(
                    LEGACY_RUNTIME_PORT_ALIASES.get(location.location_id, "")
                )
            if state is None:
                enriched.append(location)
                continue
            latest_observation = state.get("latest_observation_date")
            if isinstance(latest_observation, str):
                latest_observation = date.fromisoformat(latest_observation[:10])
            enriched.append(
                location.model_copy(
                    update={
                        "source": state.get("source", location.source),
                        "canonical_location_id": state.get(
                            "canonical_location_id", location.canonical_location_id
                        ),
                        "portwatch_source_port_id": state.get(
                            "source_port_id", location.portwatch_source_port_id
                        ),
                        "latest_observation_date": latest_observation,
                        "activity_score": state.get(
                            "activity_score", location.activity_score
                        ),
                        "activity_anomaly_score": state.get(
                            "activity_anomaly_score", location.activity_anomaly_score
                        ),
                        "operational_status": state.get(
                            "operational_status", location.operational_status
                        ),
                    }
                )
            )
        return enriched

    def get_port_state(self, location_id: str) -> dict[str, object] | None:
        """Return one port state using either a runtime or canonical ID."""

        runtime_state = self.runtime_port_state()
        if location_id in runtime_state:
            return runtime_state[location_id]
        return self.load_current_port_state().get(location_id)

    def get_active_disruptions(self) -> list[dict[str, object]]:
        """Return current canonical disruptions with canonical affected ports."""

        if not self.disruptions_path.exists():
            return []
        disruptions = pd.read_parquet(self.disruptions_path)
        relations = (
            pd.read_parquet(self.affected_ports_path)
            if self.affected_ports_path.exists()
            else pd.DataFrame(columns=["event_id", "location_id"])
        )
        if not relations.empty and relations.duplicated(
            subset=["event_id", "location_id"]
        ).any():
            raise ValueError("PortWatch disruption relations contain duplicates")
        affected_by_event = (
            relations.groupby("event_id")["location_id"].apply(list).to_dict()
            if not relations.empty
            else {}
        )
        output = []
        for row in disruptions.to_dict(orient="records"):
            event_id = str(row["event_id"])
            output.append(
                {
                    "event_id": event_id,
                    "event_type": _optional_value(row.get("event_type")),
                    "event_name": _optional_value(row.get("event_name")),
                    "description": _optional_value(row.get("description")),
                    "alert_level": _optional_value(row.get("alert_level")),
                    "severity_text": _optional_value(row.get("severity_text")),
                    "start_time": _optional_value(row.get("start_time")),
                    "end_time": _optional_value(row.get("end_time")),
                    "affected_location_ids": affected_by_event.get(event_id, []),
                    "source": "PORTWATCH",
                    "is_active": True,
                }
            )
        return output


def load_current_port_state(
    *,
    state_path: Path = DEFAULT_STATE_PATH,
    runtime_mapping_path: Path = DEFAULT_RUNTIME_MAPPING_PATH,
) -> dict[str, dict[str, object]]:
    """Convenience function for canonical-keyed state loading."""

    return PortWatchAdapter(
        state_path=state_path,
        runtime_mapping_path=runtime_mapping_path,
    ).load_current_port_state()


def load_runtime_port_state(
    *,
    state_path: Path = DEFAULT_STATE_PATH,
    runtime_mapping_path: Path = DEFAULT_RUNTIME_MAPPING_PATH,
) -> dict[str, dict[str, object]]:
    """Convenience function for graph-ready runtime-keyed state loading."""

    return PortWatchAdapter(
        state_path=state_path,
        runtime_mapping_path=runtime_mapping_path,
    ).runtime_port_state()


def load_current_disruptions(
    *,
    disruptions_path: Path = DEFAULT_DISRUPTIONS_PATH,
    affected_ports_path: Path = DEFAULT_AFFECTED_PORTS_PATH,
) -> list[dict[str, object]]:
    """Convenience function for loading clean active disruption state."""

    return PortWatchAdapter(
        disruptions_path=disruptions_path,
        affected_ports_path=affected_ports_path,
    ).get_active_disruptions()
