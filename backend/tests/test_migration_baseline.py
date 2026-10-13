from backend.app.migration_baseline import (
    BASELINE_SCHEMA_VERSION,
    EXPECTED_COUNTS,
    _dataset_records,
    _validate_dataset,
)
from backend.app.repository import load_runtime_dataset


def test_active_runtime_matches_phase_zero_counts_and_integrity():
    dataset = load_runtime_dataset()
    records = _dataset_records(dataset)

    assert {key: len(value) for key, value in records.items()} == EXPECTED_COUNTS
    checks = _validate_dataset(dataset)

    assert checks["pass"] is True
    assert checks["orphan_references"] == []
    assert checks["ordered_leg_sequence_errors"] == []
    assert checks["parallel_route_pairs"] == []
    assert checks["weakly_connected_components"] == 1


def test_phase_zero_schema_version_is_explicit():
    assert BASELINE_SCHEMA_VERSION == "neo4j-phase-0/v1"
