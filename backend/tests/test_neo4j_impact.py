from __future__ import annotations

import pytest

from backend.app.persistence.neo4j.impact import (
    DOWNSTREAM_LEG_QUERY,
    LOCATION_DEPENDENCY_QUERY,
    ROUTE_DEPENDENCY_QUERY,
    Neo4jImpactQueryError,
    Neo4jImpactQueryService,
)


class FakeImpactManager:
    def __init__(self):
        self.calls = []

    def execute_read(self, query, parameters, *, timeout_seconds):
        self.calls.append((query, parameters, timeout_seconds))
        if query == LOCATION_DEPENDENCY_QUERY:
            return [{
                "shipment_id": "S1",
                "shipment_status": "IN_TRANSIT",
                "current_location_id": "A",
                "plan_id": "S1:v1",
                "plan_version": 1,
                "leg_id": "S1:v1:2",
                "sequence_no": 2,
                "leg_status": "PLANNED",
                "route_id": "R2",
                "source_location_id": "A",
                "destination_location_id": "B",
                "dependency_kind": "REMAINING_DESTINATION",
                "graph_path": [
                    {"entity_type": "Shipment", "entity_id": "S1", "relationship_from_previous": None},
                    {"entity_type": "RoutePlan", "entity_id": "S1:v1", "relationship_from_previous": "HAS_PLAN"},
                    {"entity_type": "ShipmentLeg", "entity_id": "S1:v1:2", "relationship_from_previous": "HAS_LEG"},
                    {"entity_type": "Route", "entity_id": "R2", "relationship_from_previous": "USES_ROUTE"},
                    {"entity_type": "Location", "entity_id": "B", "relationship_from_previous": "TO"},
                ],
            }]
        if query == ROUTE_DEPENDENCY_QUERY:
            return []
        return [{
            "shipment_id": "S1",
            "plan_id": "S1:v1",
            "plan_version": 1,
            "start_leg_id": "S1:v1:1",
            "downstream_leg_id": "S1:v1:2",
            "sequence_no": 2,
            "leg_status": "PLANNED",
            "depth": 1,
            "graph_path": [
                {"entity_type": "ShipmentLeg", "entity_id": "S1:v1:1", "relationship_from_previous": None},
                {"entity_type": "ShipmentLeg", "entity_id": "S1:v1:2", "relationship_from_previous": "NEXT_LEG"},
            ],
        }]


def test_location_impact_returns_typed_evidence_and_parameterized_scope():
    manager = FakeImpactManager()
    service = Neo4jImpactQueryService(
        manager,
        snapshot_id="snap",
        import_scope="scope",
    )

    result = service.analyze_location("B", "PORT_CLOSURE")

    assert result.impacted_shipment_ids == ["S1"]
    assert result.evidence[0].plan_version == 1
    assert result.evidence[0].leg_status == "PLANNED"
    assert result.evidence[0].graph_path[-1].entity_id == "B"
    _, parameters, timeout = manager.calls[0]
    assert parameters["snapshot_id"] == "snap"
    assert parameters["import_scope"] == "scope"
    assert parameters["target_id"] == "B"
    assert timeout == 5.0
    assert all("$target_id" in query for query, _, _ in manager.calls[:1])


def test_route_and_bounded_next_leg_queries_are_read_only_and_bounded():
    manager = FakeImpactManager()
    service = Neo4jImpactQueryService(manager)

    route_result = service.analyze_route("R2", "ROUTE_CLOSURE")
    downstream, _ = service.find_downstream_leg_dependencies("S1:v1:1", max_depth=2)

    assert route_result.impacted_shipment_ids == []
    assert downstream[0].depth == 1
    assert downstream[0].classification == "DOWNSTREAM"
    assert "LIMIT $result_limit" in DOWNSTREAM_LEG_QUERY
    assert "*1..5" in DOWNSTREAM_LEG_QUERY
    assert all("execute_write" not in query for query, _, _ in manager.calls)


def test_impact_query_limits_and_timeout_fail_clearly():
    manager = FakeImpactManager()
    with pytest.raises(ValueError):
        Neo4jImpactQueryService(manager, result_limit=5001)
    with pytest.raises(ValueError):
        Neo4jImpactQueryService(manager).find_downstream_leg_dependencies(
            "S1:v1:1", max_depth=6
        )


class NoTimeoutManager:
    def execute_read(self, query, parameters):
        return []


def test_manager_without_timeout_support_is_rejected():
    service = Neo4jImpactQueryService(NoTimeoutManager())
    with pytest.raises(Neo4jImpactQueryError, match="timeouts"):
        service.analyze_route("R1", "ROUTE_CLOSURE")
