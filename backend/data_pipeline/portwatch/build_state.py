"""Build latest PortWatch operational state using configurable proxy scores."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .build_features import build_port_features


def _score(value: object, reference: float) -> float | None:
    if value is None or pd.isna(value):
        return None
    if reference <= 0:
        raise ValueError("score references must be greater than zero")
    return round(min(1.0, float(value) / reference), 6)


def _status(scores: list[float | None], busy_threshold: float, high_threshold: float) -> str:
    available = [score for score in scores if score is not None]
    if not available:
        return "UNKNOWN"
    highest = max(available)
    if highest >= high_threshold:
        return "HIGH_ACTIVITY"
    if highest >= busy_threshold:
        return "BUSY"
    return "NORMAL"


def _operational_status(
    activity_score: float | None,
    anomaly_score: float | None,
    high_threshold: float,
    high_anomaly_threshold: float,
    low_anomaly_threshold: float,
) -> str:
    if activity_score is None and anomaly_score is None:
        return "UNKNOWN"
    if (
        activity_score is not None
        and activity_score >= high_threshold
    ) or (
        anomaly_score is not None
        and anomaly_score >= high_anomaly_threshold
    ):
        return "HIGH_ACTIVITY"
    if anomaly_score is not None and anomaly_score <= low_anomaly_threshold:
        return "LOW_ACTIVITY"
    return "NORMAL"


def _latest_rows(frame: pd.DataFrame, identifier: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    frame = frame.copy()
    frame["observation_date"] = pd.to_datetime(frame["observation_date"]).dt.date
    indexes = frame.groupby(identifier)["observation_date"].idxmax()
    return frame.loc[indexes].sort_values(identifier).reset_index(drop=True)


def build_port_state(
    input_path: Path = Path("data/processed/portwatch/port_monitoring.parquet"),
    output_path: Path = Path("data/processed/portwatch/current_port_state.parquet"),
    *,
    activity_reference: float = 100,
    pressure_reference: float = 1_000_000,
    busy_threshold: float = 0.5,
    high_threshold: float = 0.8,
    high_anomaly_threshold: float = 0.5,
    low_anomaly_threshold: float = -0.5,
    features_output_path: Path | None = None,
    baseline_output_path: Path | None = None,
) -> pd.DataFrame:
    """Write current port activity state; values are local proxies."""

    features_output_path = features_output_path or output_path.with_name("port_features.parquet")
    baseline_output_path = baseline_output_path or output_path.with_name("port_baselines.parquet")
    frame, _ = build_port_features(
        input_path,
        features_output_path,
        baseline_output_path,
        activity_reference=activity_reference,
    )
    latest = _latest_rows(frame, "location_id")
    rows = []
    for row in latest.to_dict(orient="records"):
        trade_volume = pd.Series(
            [row.get("import_total"), row.get("export_total")], dtype="float64"
        ).sum(min_count=1)
        activity_score = _score(row.get("port_calls_total"), activity_reference)
        pressure_score = _score(trade_volume, pressure_reference)
        operational_status = _operational_status(
            activity_score,
            row.get("activity_anomaly_score"),
            high_threshold,
            high_anomaly_threshold,
            low_anomaly_threshold,
        )
        rows.append(
            {
                "location_id": row["location_id"],
                "source_port_id": row["source_port_id"],
                "port_calls_total": row.get("port_calls_total"),
                "average_port_calls": row.get("average_port_calls"),
                "recent_change_percent": row.get("port_calls_change_pct"),
                "activity_score": activity_score,
                "activity_anomaly_score": row.get("activity_anomaly_score"),
                "capacity_pressure_score": pressure_score,
                "operational_status": operational_status,
                "status": operational_status,
                "latest_observation_date": row["observation_date"],
                "source": "PORTWATCH",
                "ingested_at": row["ingested_at"],
            }
        )
    result = pd.DataFrame(
        rows,
        columns=[
            "location_id",
            "source_port_id",
            "port_calls_total",
            "average_port_calls",
            "recent_change_percent",
            "activity_score",
            "activity_anomaly_score",
            "capacity_pressure_score",
            "operational_status",
            "status",
            "latest_observation_date",
            "source",
            "ingested_at",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_path, index=False, engine="pyarrow")
    return result


def build_checkpoint_state(
    input_path: Path = Path("data/processed/portwatch/checkpoint_monitoring.parquet"),
    output_path: Path = Path(
        "data/processed/portwatch/current_checkpoint_state.parquet"
    ),
    *,
    activity_reference: float = 100,
    pressure_reference: float = 10_000_000,
    busy_threshold: float = 0.5,
    high_threshold: float = 0.8,
) -> pd.DataFrame:
    """Write current checkpoint state using vessel and capacity proxy scores."""

    frame = pd.read_parquet(input_path)
    latest = _latest_rows(frame, "checkpoint_id")
    rows = []
    for row in latest.to_dict(orient="records"):
        activity_score = _score(row.get("vessel_count_total"), activity_reference)
        pressure_score = _score(row.get("capacity_total"), pressure_reference)
        rows.append(
            {
                "checkpoint_id": row["checkpoint_id"],
                "source_checkpoint_id": row["source_checkpoint_id"],
                "activity_score": activity_score,
                "capacity_pressure_score": pressure_score,
                "status": _status(
                    [activity_score, pressure_score], busy_threshold, high_threshold
                ),
                "latest_observation_date": row["observation_date"],
                "source": "PORTWATCH",
                "ingested_at": row["ingested_at"],
            }
        )
    result = pd.DataFrame(
        rows,
        columns=[
            "checkpoint_id",
            "source_checkpoint_id",
            "activity_score",
            "capacity_pressure_score",
            "status",
            "latest_observation_date",
            "source",
            "ingested_at",
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output_path, index=False, engine="pyarrow")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ports-input", type=Path)
    parser.add_argument("--checkpoints-input", type=Path)
    parser.add_argument("--ports-output", type=Path)
    parser.add_argument("--checkpoints-output", type=Path)
    parser.add_argument("--activity-reference", type=float, default=100)
    parser.add_argument("--port-pressure-reference", type=float, default=1_000_000)
    parser.add_argument("--checkpoint-pressure-reference", type=float, default=10_000_000)
    parser.add_argument("--busy-threshold", type=float, default=0.5)
    parser.add_argument("--high-threshold", type=float, default=0.8)
    parser.add_argument("--high-anomaly-threshold", type=float, default=0.5)
    parser.add_argument("--low-anomaly-threshold", type=float, default=-0.5)
    parser.add_argument("--ports-features-output", type=Path)
    parser.add_argument("--ports-baseline-output", type=Path)
    args = parser.parse_args()
    output = {}
    if args.ports_input or args.ports_output:
        result = build_port_state(
            args.ports_input or Path("data/processed/portwatch/port_monitoring.parquet"),
            args.ports_output or Path("data/processed/portwatch/current_port_state.parquet"),
            activity_reference=args.activity_reference,
            pressure_reference=args.port_pressure_reference,
            busy_threshold=args.busy_threshold,
            high_threshold=args.high_threshold,
            high_anomaly_threshold=args.high_anomaly_threshold,
            low_anomaly_threshold=args.low_anomaly_threshold,
            features_output_path=(
                args.ports_features_output
                or Path("data/processed/portwatch/port_features.parquet")
            ),
            baseline_output_path=(
                args.ports_baseline_output
                or Path("data/processed/portwatch/port_baselines.parquet")
            ),
        )
        output["ports"] = len(result)
    if args.checkpoints_input or args.checkpoints_output:
        result = build_checkpoint_state(
            args.checkpoints_input
            or Path("data/processed/portwatch/checkpoint_monitoring.parquet"),
            args.checkpoints_output
            or Path("data/processed/portwatch/current_checkpoint_state.parquet"),
            activity_reference=args.activity_reference,
            pressure_reference=args.checkpoint_pressure_reference,
            busy_threshold=args.busy_threshold,
            high_threshold=args.high_threshold,
        )
        output["checkpoints"] = len(result)
    if not output:
        raise SystemExit("Specify --ports-input/--ports-output or checkpoint equivalents")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
