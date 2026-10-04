"""Build PortWatch historical baselines and derived activity features."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


BASELINE_COLUMNS = [
    "location_id",
    "average_port_calls",
    "average_import_volume",
    "average_export_volume",
    "observation_count",
    "baseline_start_date",
    "baseline_end_date",
    "recent_change_percent",
    "baseline_quality",
    "source",
]
FEATURE_COLUMNS = [
    "location_id",
    "observation_date",
    "port_calls_total",
    "port_calls_change_pct",
    "import_total",
    "import_change_pct",
    "export_total",
    "export_change_pct",
    "average_port_calls",
    "average_import_volume",
    "average_export_volume",
    "activity_score",
    "activity_anomaly_score",
    "baseline_observation_count",
    "baseline_quality",
    "source_port_id",
    "source",
    "ingested_at",
]


def _percent_change(current: pd.Series, previous: pd.Series) -> pd.Series:
    result = pd.Series(float("nan"), index=current.index, dtype="float64")
    valid = current.notna() & previous.notna() & previous.ne(0)
    result.loc[valid] = ((current.loc[valid] - previous.loc[valid]) / previous.loc[valid].abs()) * 100
    return result.round(6)


def _activity_score(values: pd.Series, reference: float) -> pd.Series:
    if reference <= 0:
        raise ValueError("activity_reference must be greater than zero")
    return (values / reference).clip(lower=0, upper=1).round(6)


def _anomaly_score(values: pd.Series, baseline: pd.Series) -> pd.Series:
    denominator = baseline.abs().clip(lower=1)
    result = ((values - baseline) / denominator).clip(lower=-1, upper=1)
    result.loc[values.isna() | baseline.isna()] = float("nan")
    return result.round(6)


def build_port_features(
    input_path: Path = Path("data/processed/portwatch/port_monitoring.parquet"),
    features_output_path: Path = Path("data/processed/portwatch/port_features.parquet"),
    baseline_output_path: Path = Path("data/processed/portwatch/port_baselines.parquet"),
    *,
    activity_reference: float = 100,
    minimum_history_days: int = 28,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write daily activity features and per-port historical baselines.

    Baselines use all observations currently available for each port. This is
    intentionally a simple local indicator, not an official IMF metric. With
    fewer than ``minimum_history_days`` observations, the quality is marked
    ``LIMITED_HISTORY``.
    """

    frame = pd.read_parquet(input_path).copy()
    if frame.empty:
        empty_features = pd.DataFrame(columns=FEATURE_COLUMNS)
        empty_baselines = pd.DataFrame(columns=BASELINE_COLUMNS)
        features_output_path.parent.mkdir(parents=True, exist_ok=True)
        empty_features.to_parquet(features_output_path, index=False, engine="pyarrow")
        empty_baselines.to_parquet(baseline_output_path, index=False, engine="pyarrow")
        return empty_features, empty_baselines

    required = {"location_id", "observation_date", "port_calls_total", "import_total", "export_total"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Port monitoring data is missing columns: {', '.join(sorted(missing))}")

    frame["observation_date"] = pd.to_datetime(frame["observation_date"]).dt.date
    frame = frame.sort_values(["location_id", "observation_date"]).reset_index(drop=True)
    grouped = frame.groupby("location_id", sort=False)

    frame["average_port_calls"] = grouped["port_calls_total"].transform("mean").round(6)
    frame["average_import_volume"] = grouped["import_total"].transform("mean").round(6)
    frame["average_export_volume"] = grouped["export_total"].transform("mean").round(6)
    frame["baseline_observation_count"] = grouped["port_calls_total"].transform("count").astype("Int64")
    frame["baseline_quality"] = frame["baseline_observation_count"].map(
        lambda value: "LIMITED_HISTORY" if value < minimum_history_days else "HISTORICAL"
    )

    previous_calls = grouped["port_calls_total"].shift(1)
    previous_imports = grouped["import_total"].shift(1)
    previous_exports = grouped["export_total"].shift(1)
    frame["port_calls_change_pct"] = _percent_change(frame["port_calls_total"], previous_calls)
    frame["import_change_pct"] = _percent_change(frame["import_total"], previous_imports)
    frame["export_change_pct"] = _percent_change(frame["export_total"], previous_exports)
    frame["activity_score"] = _activity_score(frame["port_calls_total"], activity_reference)
    frame["activity_anomaly_score"] = _anomaly_score(
        frame["port_calls_total"], frame["average_port_calls"]
    )

    features = frame[FEATURE_COLUMNS].copy()
    features_output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(features_output_path, index=False, engine="pyarrow")

    baseline_groups = frame.groupby("location_id", sort=True)
    baselines = baseline_groups.agg(
        average_port_calls=("port_calls_total", "mean"),
        average_import_volume=("import_total", "mean"),
        average_export_volume=("export_total", "mean"),
        observation_count=("port_calls_total", "count"),
        baseline_start_date=("observation_date", "min"),
        baseline_end_date=("observation_date", "max"),
    ).reset_index()
    latest_changes = (
        features.sort_values(["location_id", "observation_date"])
        .groupby("location_id", sort=True)
        .tail(1)[["location_id", "port_calls_change_pct"]]
        .rename(columns={"port_calls_change_pct": "recent_change_percent"})
    )
    baselines = baselines.merge(latest_changes, on="location_id", how="left")
    baselines["baseline_quality"] = baselines["observation_count"].map(
        lambda value: "LIMITED_HISTORY" if value < minimum_history_days else "HISTORICAL"
    )
    baselines["source"] = "PORTWATCH"
    baselines = baselines[BASELINE_COLUMNS]
    baselines.to_parquet(baseline_output_path, index=False, engine="pyarrow")
    return features, baselines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/portwatch/port_monitoring.parquet"))
    parser.add_argument("--features-output", type=Path, default=Path("data/processed/portwatch/port_features.parquet"))
    parser.add_argument("--baseline-output", type=Path, default=Path("data/processed/portwatch/port_baselines.parquet"))
    parser.add_argument("--activity-reference", type=float, default=100)
    parser.add_argument("--minimum-history-days", type=int, default=28)
    args = parser.parse_args()
    features, baselines = build_port_features(
        args.input,
        args.features_output,
        args.baseline_output,
        activity_reference=args.activity_reference,
        minimum_history_days=args.minimum_history_days,
    )
    print(json.dumps({"feature_rows": len(features), "baseline_rows": len(baselines)}, indent=2))


if __name__ == "__main__":
    main()
