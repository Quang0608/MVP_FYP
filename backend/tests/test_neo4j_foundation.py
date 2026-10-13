from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from backend.app.config import Settings
from backend.app.persistence.neo4j import driver as driver_module
from backend.app.persistence.neo4j.driver import (
    Neo4jConfigurationError,
    Neo4jConnectionError,
    Neo4jConnectionManager,
)
from backend.app.persistence.neo4j.schema import (
    CONSTRAINT_STATEMENTS,
    INDEX_STATEMENTS,
    bootstrap_schema,
)


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "neo4j_password": SecretStr("test-password"),
    }
    values.update(overrides)
    return Settings(**values)


class FakeResult:
    def __init__(self, rows=None):
        self.rows = rows or []

    def data(self):
        return self.rows


class FakeTransaction:
    def __init__(self, calls):
        self.calls = calls

    def run(self, query, parameters):
        self.calls.append((query, parameters))
        return FakeResult([{"ok": 1}])


class FakeSession:
    def __init__(self, calls):
        self.calls = calls
        self.closed = False

    def execute_read(self, work):
        return work(FakeTransaction(self.calls))

    def execute_write(self, work):
        return work(FakeTransaction(self.calls))

    def close(self):
        self.closed = True


class FakeDriver:
    def __init__(self):
        self.calls = []
        self.verify_count = 0
        self.closed = False
        self.sessions = []

    def verify_connectivity(self):
        self.verify_count += 1

    def session(self, *, database):
        self.calls.append(("session", database))
        session = FakeSession(self.calls)
        self.sessions.append(session)
        return session

    def close(self):
        self.closed = True


def test_settings_keep_sqlite_default_and_validate_neo4j_fields():
    configuration = Settings(_env_file=None)

    assert configuration.persistence_backend == "sqlite"
    assert configuration.neo4j_database == "neo4j"
    assert configuration.neo4j_password.get_secret_value() == ""
    assert repr(configuration.neo4j_password) == "SecretStr('')"

    configured = _settings(
        persistence_backend="neo4j",
        neo4j_uri="neo4j+s://example.test",
    )
    assert configured.persistence_backend == "neo4j"
    assert configured.neo4j_uri == "neo4j+s://example.test"
    assert "test-password" not in repr(configured)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, persistence_backend="postgres")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, neo4j_uri="http://localhost:7687")


def test_connection_manager_owns_one_driver_and_scoped_sessions(monkeypatch):
    fake_driver = FakeDriver()
    created = []

    def fake_factory(uri, *, auth, **kwargs):
        created.append((uri, auth, kwargs))
        return fake_driver

    monkeypatch.setattr(driver_module.GraphDatabase, "driver", fake_factory)
    manager = Neo4jConnectionManager(_settings())

    manager.start()
    manager.start()
    assert len(created) == 1
    assert created[0][0] == "bolt://localhost:7687"
    assert created[0][1] == ("neo4j", "test-password")
    assert fake_driver.verify_count == 1

    assert manager.execute_read("RETURN 1 AS ok") == [{"ok": 1}]
    assert manager.execute_write("RETURN 2 AS ok") == [{"ok": 1}]
    assert all(session.closed for session in fake_driver.sessions)
    assert all(call[1] == "neo4j" for call in fake_driver.calls if call[0] == "session")

    health = manager.health_check()
    assert health.as_dict() == {"status": "ok", "database": "neo4j", "detail": None}
    assert fake_driver.verify_count == 2
    manager.close()
    manager.close()
    assert fake_driver.closed is True


def test_connection_manager_reports_missing_password_without_creating_driver(monkeypatch):
    def fail_factory(*args, **kwargs):
        raise AssertionError("driver must not be created without a password")

    monkeypatch.setattr(driver_module.GraphDatabase, "driver", fail_factory)
    manager = Neo4jConnectionManager(Settings(_env_file=None))

    with pytest.raises(Neo4jConfigurationError):
        manager.start()
    assert manager.health_check().status == "unconfigured"


def test_connection_manager_closes_driver_when_connectivity_fails(monkeypatch):
    fake_driver = FakeDriver()

    def fail_connectivity():
        raise RuntimeError("simulated connection failure")

    fake_driver.verify_connectivity = fail_connectivity
    monkeypatch.setattr(driver_module.GraphDatabase, "driver", lambda *args, **kwargs: fake_driver)
    manager = Neo4jConnectionManager(_settings())

    with pytest.raises(Neo4jConnectionError):
        manager.start()
    assert fake_driver.closed is True
    assert manager.is_started is False


def test_schema_bootstrap_contains_idempotent_constraints_and_indexes():
    class FakeSchemaManager:
        def __init__(self):
            self.statements = []

        def execute_write(self, statement):
            self.statements.append(statement)

    manager = FakeSchemaManager()
    result = bootstrap_schema(manager)
    expected = [statement for _, statement in CONSTRAINT_STATEMENTS]
    expected.extend(statement for _, statement in INDEX_STATEMENTS)

    assert manager.statements == expected
    assert len(result["constraints"]) == 8
    assert len(result["indexes"]) == 5
    assert all("IF NOT EXISTS" in statement for statement in manager.statements)
    assert all("REQUIRE n." in statement for _, statement in CONSTRAINT_STATEMENTS)


def test_compose_has_pinned_neo4j_service_and_named_persistence():
    compose = Path(__file__).parents[2] / "docker-compose.yml"
    content = compose.read_text(encoding="utf-8")

    assert "neo4j:" in content
    assert "image: neo4j:2026.09.0" in content
    assert "neo4j_data:/data" in content
    assert "neo4j_logs:/logs" in content
    assert "healthcheck:" in content
    assert "NEO4J_AUTH:" in content
