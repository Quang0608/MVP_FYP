from datetime import datetime, timezone

import pytest

from backend.app.persistence.neo4j.write_repository import (
    Neo4jUnsupportedWriteError,
    Neo4jWriteConflictError,
    Neo4jWriteNotFoundError,
    Neo4jWriteRepository,
    Neo4jWriteValidationError,
)
from backend.app.schemas import (
    Disruption,
    DisruptionRequest,
    DisruptionType,
)


class FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def data(self):
        return self._rows


class FakeTransaction:
    def __init__(self, handler):
        self.handler = handler
        self.queries = []

    def run(self, query, parameters):
        self.queries.append((query, parameters))
        return FakeResult(self.handler(query, parameters))


class FakeManager:
    def __init__(self, handler):
        self.handler = handler
        self.transactions = []
        self.reads = []

    def execute_write_transaction(self, work):
        transaction = FakeTransaction(self.handler)
        self.transactions.append(transaction)
        return work(transaction)

    def execute_read(self, query, parameters=None):
        self.reads.append((query, parameters))
        return []

    def execute_write(self, query, parameters=None):
        return self.handler(query, parameters or {})


def _disruption(disruption_id="D1"):
    return Disruption(
        id=disruption_id,
        request=DisruptionRequest(
            disruption_type=DisruptionType.PORT_CLOSURE,
            affected_location_ids=["LOC_WPI_50000"],
            affected_route_ids=["ASIA_R_0002"],
            duration_hours=72,
            severity="HIGH",
        ),
        created_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
    )


def _recommendation(shipment_id="ASIA_S_0001", status="REROUTED"):
    return {
        "shipment_id": shipment_id,
        "status": status,
        "original_route": {"route_ids": ["ASIA_R_0002"]},
        "selected_route": {"route_ids": ["ASIA_R_0003"], "risk_score": 0.2},
        "delay_saved_hours": 1.5,
        "additional_cost": 3.0,
    }


def _create_handler(query, parameters):
    if "MATCH (n:Location)" in query:
        return [{"ids": parameters["values"]}]
    if "MATCH (n:Route)" in query:
        if "MISSING-ROUTE" in parameters["values"]:
            return [{"ids": []}]
        return [{"ids": parameters["values"]}]
    if "MATCH (n:Shipment)" in query:
        return [{"ids": parameters["values"]}]
    if "MATCH (d:Disruption" in query:
        return []
    return [{"id": parameters.get("disruption_id", "D1")}]


def test_create_disruption_uses_one_parameterized_transaction_and_scope():
    manager = FakeManager(_create_handler)
    repository = Neo4jWriteRepository(
        manager,
        snapshot_id="test-snapshot",
        import_scope="test-scope",
    )

    receipt = repository.create_disruption(_disruption(), {"affected": []})

    assert receipt.action == "CREATED"
    assert len(manager.transactions) == 1
    assert manager.transactions[0].queries
    assert all("$" in query for query, _ in manager.transactions[0].queries)
    assert all(
        params.get("snapshot_id") in {None, "test-snapshot"}
        for _, params in manager.transactions[0].queries
    )


def test_create_recommendation_validation_rejects_duplicate_and_invalid_status():
    manager = FakeManager(_create_handler)
    repository = Neo4jWriteRepository(
        manager,
        snapshot_id="test-snapshot",
        import_scope="test-scope",
    )

    with pytest.raises(Neo4jWriteValidationError, match="Duplicate"):
        repository.save_reroute_decisions(
            "D1",
            {"recommendations": [_recommendation(), _recommendation()]},
        )
    with pytest.raises(Neo4jWriteValidationError, match="Unsupported decision status"):
        repository.save_reroute_decisions(
            "D1",
            {"recommendations": [_recommendation(status="INVALID")]},
        )
    assert manager.transactions == []


def test_stale_simulation_version_is_rejected_before_mutation():
    def handler(query, parameters):
        if "MATCH (run:SimulationRun" in query:
            return [{"properties": {"write_version": 2}}]
        raise AssertionError(f"unexpected query after stale check: {query}")

    manager = FakeManager(handler)
    repository = Neo4jWriteRepository(
        manager,
        snapshot_id="test-snapshot",
        import_scope="test-scope",
    )

    with pytest.raises(Neo4jWriteConflictError, match="Stale simulation"):
        repository.save_reroute_decisions(
            "D1",
            {"recommendations": [_recommendation()]},
            expected_write_version=0,
        )
    assert len(manager.transactions) == 1
    assert len(manager.transactions[0].queries) == 1


def test_route_references_in_decisions_are_validated():
    def handler(query, parameters):
        if "MATCH (run:SimulationRun" in query:
            return [{"properties": {"write_version": 0}}]
        return _create_handler(query, parameters)

    manager = FakeManager(handler)
    repository = Neo4jWriteRepository(
        manager,
        snapshot_id="test-snapshot",
        import_scope="test-scope",
    )
    recommendation = _recommendation()
    recommendation["selected_route"] = {"route_ids": ["MISSING-ROUTE"]}

    with pytest.raises(Neo4jWriteValidationError, match="Missing Route"):
        repository.save_reroute_decisions(
            "D1",
            {"recommendations": [recommendation]},
        )


def test_missing_simulation_is_explicit_and_explanation_is_not_silently_created():
    manager = FakeManager(lambda query, parameters: [])
    repository = Neo4jWriteRepository(
        manager,
        snapshot_id="test-snapshot",
        import_scope="test-scope",
    )

    with pytest.raises(Neo4jWriteNotFoundError):
        repository.save_reroute_decisions(
            "missing",
            {"recommendations": []},
        )
    with pytest.raises(Neo4jWriteNotFoundError):
        repository.save_decision_explanation("missing", "S1", {"text": "x"})


def test_unsupported_canonical_progress_write_is_explicit():
    repository = Neo4jWriteRepository(
        FakeManager(_create_handler),
        snapshot_id="test-snapshot",
        import_scope="test-scope",
    )

    with pytest.raises(Neo4jUnsupportedWriteError, match="canonical shipment progress"):
        repository.reject_canonical_progress_write("update_shipment_progress")
