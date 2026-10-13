from datetime import datetime, timezone

import pytest

from backend.app import repository as sqlite_repository
from backend.app.config import Settings, settings
from backend.app.persistence.neo4j.runtime import (
    Neo4jRuntimePreflightError,
    Neo4jRuntimeRepository,
)


class FakeSelectedBackend:
    def __init__(self):
        self.dataset = object()
        self.calls = []

    def load_runtime_dataset(self):
        self.calls.append("load_runtime_dataset")
        return self.dataset

    def get_run(self, run_id):
        self.calls.append(("get_run", run_id))
        return {"id": run_id}

    def all_runs(self):
        self.calls.append("all_runs")
        return [{"id": "D1"}]


class FakeManager:
    def __init__(self, rows):
        self.rows = rows

    def execute_read(self, query, parameters=None):
        return self.rows


def _configured_settings(**overrides):
    values = {
        "_env_file": None,
        "neo4j_password": "test-password",
    }
    values.update(overrides)
    return Settings(**values)


def test_repository_dispatches_all_runtime_reads_to_selected_neo4j_backend(monkeypatch):
    backend = FakeSelectedBackend()
    monkeypatch.setattr(settings, "persistence_backend", "neo4j")
    monkeypatch.setattr(
        sqlite_repository,
        "_neo4j_runtime_repository",
        lambda: backend,
    )

    assert sqlite_repository.load_runtime_dataset() is backend.dataset
    assert sqlite_repository.get_run("D1") == {"id": "D1"}
    assert sqlite_repository.all_runs() == [{"id": "D1"}]
    assert backend.calls == ["load_runtime_dataset", ("get_run", "D1"), "all_runs"]


def test_selected_neo4j_backend_does_not_fall_back_when_unavailable(monkeypatch):
    class FailingBackend:
        def load_runtime_dataset(self):
            raise Neo4jRuntimePreflightError("Neo4j unavailable")

    monkeypatch.setattr(settings, "persistence_backend", "neo4j")
    monkeypatch.setattr(
        sqlite_repository,
        "_neo4j_runtime_repository",
        lambda: FailingBackend(),
    )

    with pytest.raises(Neo4jRuntimePreflightError, match="unavailable"):
        sqlite_repository.load_runtime_dataset()


def test_database_initialisation_preflights_selected_neo4j(monkeypatch):
    calls = []

    def fake_preflight(configuration):
        calls.append(configuration.persistence_backend)
        return {"connectivity": "pass", "schema": "pass"}

    monkeypatch.setattr(settings, "persistence_backend", "neo4j")
    monkeypatch.setattr(
        "backend.app.persistence.neo4j.runtime.preflight_neo4j_runtime",
        fake_preflight,
    )

    sqlite_repository.initialise_database()

    assert calls == ["neo4j"]


def test_sqlite_remains_the_default_backend():
    assert Settings(_env_file=None).persistence_backend == "sqlite"


def test_runtime_scopes_are_explicit_and_namespaced():
    configuration = _configured_settings(
        neo4j_snapshot_id="snapshot-test",
        neo4j_import_scope="import-test",
        neo4j_write_snapshot_id="write-snapshot-test",
        neo4j_write_import_scope="write-scope-test",
    )
    repository = Neo4jRuntimeRepository(configuration)

    assert repository.read_snapshot_id == "snapshot-test"
    assert repository.read_import_scope == "import-test"
    assert repository.write_snapshot_id == "write-snapshot-test"
    assert repository.write_import_scope == "write-scope-test"


def test_stored_neo4j_record_hydrates_existing_runtime_shape():
    manager = FakeManager(
        [
            {
                "disruption": {
                    "disruption_id": "D1",
                    "event_type": "PORT_CLOSURE",
                    "severity": "HIGH",
                    "duration_hours": 72,
                    "description": "test",
                    "created_at": datetime(2026, 10, 13, tzinfo=timezone.utc),
                },
                "location_ids": ["LOC_WPI_50000"],
                "route_ids": ["ASIA_R_0002"],
                "run": {
                    "simulation_result_json": '{"affected_shipments": []}',
                    "reroute_result_json": None,
                },
                "decisions": [],
            }
        ]
    )
    repository = Neo4jRuntimeRepository(_configured_settings())

    stored = repository._stored_record(manager, "D1")

    assert stored["disruption"] == {
        "id": "D1",
        "request": {
            "disruption_type": "PORT_CLOSURE",
            "affected_location_ids": ["LOC_WPI_50000"],
            "affected_route_ids": ["ASIA_R_0002"],
            "duration_hours": 72,
            "severity": "HIGH",
            "description": "test",
        },
        "created_at": "2026-10-13T00:00:00+00:00",
    }
    assert stored["results"] == {"affected_shipments": []}
