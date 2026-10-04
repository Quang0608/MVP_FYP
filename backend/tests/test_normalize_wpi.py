from pathlib import Path

import pandas as pd

from backend.data_pipeline.normalize_wpi import OUTPUT_COLUMNS, normalize_wpi


ROOT = Path(__file__).resolve().parents[2]
RAW_WPI = ROOT / "data" / "raw" / "wpi" / "UpdatedPub150.csv"


def test_wpi_normalizer_writes_requested_canonical_ports(tmp_path):
    output_path = tmp_path / "wpi" / "ports.parquet"

    result = normalize_wpi(RAW_WPI, output_path)
    stored = pd.read_parquet(output_path)

    assert len(result) == 3802
    assert list(result.columns) == OUTPUT_COLUMNS
    assert list(stored.columns) == OUTPUT_COLUMNS
    assert len(stored) == 3802
    assert stored["location_id"].notna().all()
    assert stored["location_id"].is_unique
    assert (stored["location_type"] == "PORT").all()
    assert (stored["source"] == "WPI").all()
    assert stored["latitude"].between(-90, 90).all()
    assert stored["longitude"].between(-180, 180).all()
    assert "LOC_WPI_49454.5" in set(stored["location_id"])
    assert "LOC_WPI_49460_OID_31" in set(stored["location_id"])
    assert "LOC_WPI_49460_OID_1307" in set(stored["location_id"])
    assert "USFSP" in set(stored["unlocode"].dropna())
