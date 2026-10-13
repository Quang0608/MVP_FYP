from pathlib import Path

from backend.app.asia_dataset import generate_asia_runtime_dataset
from backend.app.persistence.neo4j import importer


def test_active_source_validation_matches_phase_zero_counts():
    dataset = generate_asia_runtime_dataset()

    validation = importer.validate_active_dataset(dataset)

    assert validation["pass"] is True
    assert validation["counts"] == importer.EXPECTED_COUNTS
    assert validation["reference_errors"] == []
    assert validation["leg_reference_errors"] == []
    assert validation["sequence_errors"] == []
    assert validation["chronology_errors"] == []
    assert validation["progress_errors"] == []


def test_node_mapping_preserves_stable_ids_and_one_based_leg_ids():
    dataset = generate_asia_runtime_dataset()

    rows = importer._node_rows(dataset, importer.SOURCE_SNAPSHOT_ID)

    assert len(rows["locations"]) == 91
    assert len(rows["routes"]) == 150
    assert len(rows["shipments"]) == 220
    assert len(rows["route_plans"]) == 220
    assert len(rows["ordered_legs"]) == 1000
    assert rows["route_plans"][0]["id"] == "ASIA_S_0001:v1"
    assert rows["ordered_legs"][0]["id"].endswith(":1")
    assert rows["ordered_legs"][0]["properties"]["sequence_no"] == 1
    assert "scenario_duration_hours" not in rows["routes"][0]["properties"]


def test_relationship_mapping_preserves_direction_and_order():
    dataset = generate_asia_runtime_dataset()

    rows = importer._relationship_rows(dataset, importer.SOURCE_SNAPSHOT_ID)

    assert {
        relationship_type: len(values)
        for relationship_type, values in rows.items()
        if relationship_type != "NEXT_LEG"
    } == {
        "FROM": 150,
        "TO": 150,
        "ORIGINATES_AT": 220,
        "DESTINED_FOR": 220,
        "CURRENTLY_AT": 220,
        "HAS_PLAN": 220,
        "HAS_LEG": 1000,
        "USES_ROUTE": 1000,
    }
    assert len([row for row in rows["NEXT_LEG"] if row["to_id"] is not None]) == 780
    first_route = rows["FROM"][0]
    assert first_route["from_id"] == "ASIA_R_0001"
    assert first_route["to_id"] == "ASIA_F_001"
    first_leg = rows["HAS_LEG"][0]
    assert first_leg["from_id"] == "ASIA_S_0001:v1"
    assert first_leg["to_id"] == "ASIA_S_0001:v1:1"
    assert first_leg["properties"]["sequence_no"] == 1


def test_dry_run_writes_report_without_a_neo4j_manager(tmp_path, monkeypatch):
    dataset = generate_asia_runtime_dataset()
    monkeypatch.setattr(importer, "load_source_dataset", lambda _path: dataset)
    report_path = tmp_path / "dry-run.json"

    report = importer.run_import(
        snapshot_id=importer.SOURCE_SNAPSHOT_ID,
        source_sqlite=Path("reroute_agent.db"),
        mode="dry-run",
        manifest_out=report_path,
    )

    assert report_path.exists()
    assert report["mode"] == "dry-run"
    assert report["verification"] == {}
    assert report["validation"]["pass"] is True


def test_import_queries_use_stable_merge_keys_and_parameterized_rows():
    assert all("MERGE" in query for query in importer.NODE_IMPORT_QUERIES.values())
    assert all("$rows" in query for query in importer.NODE_IMPORT_QUERIES.values())
    assert all("MERGE" in query for query in importer.RELATIONSHIP_IMPORT_QUERIES.values())
    assert all("$rows" in query for query in importer.RELATIONSHIP_IMPORT_QUERIES.values())
