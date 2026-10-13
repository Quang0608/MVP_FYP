"""Idempotent initial Neo4j KG schema for Phase 1."""

from __future__ import annotations

from typing import Any


CONSTRAINT_STATEMENTS: tuple[tuple[str, str], ...] = (
    (
        "location_id_unique",
        "CREATE CONSTRAINT location_id_unique IF NOT EXISTS "
        "FOR (n:Location) REQUIRE n.location_id IS UNIQUE",
    ),
    (
        "route_id_unique",
        "CREATE CONSTRAINT route_id_unique IF NOT EXISTS "
        "FOR (n:Route) REQUIRE n.route_id IS UNIQUE",
    ),
    (
        "shipment_id_unique",
        "CREATE CONSTRAINT shipment_id_unique IF NOT EXISTS "
        "FOR (n:Shipment) REQUIRE n.shipment_id IS UNIQUE",
    ),
    (
        "route_plan_id_unique",
        "CREATE CONSTRAINT route_plan_id_unique IF NOT EXISTS "
        "FOR (n:RoutePlan) REQUIRE n.plan_id IS UNIQUE",
    ),
    (
        "shipment_leg_id_unique",
        "CREATE CONSTRAINT shipment_leg_id_unique IF NOT EXISTS "
        "FOR (n:ShipmentLeg) REQUIRE n.leg_id IS UNIQUE",
    ),
    (
        "disruption_id_unique",
        "CREATE CONSTRAINT disruption_id_unique IF NOT EXISTS "
        "FOR (n:Disruption) REQUIRE n.disruption_id IS UNIQUE",
    ),
    (
        "simulation_run_id_unique",
        "CREATE CONSTRAINT simulation_run_id_unique IF NOT EXISTS "
        "FOR (n:SimulationRun) REQUIRE n.simulation_run_id IS UNIQUE",
    ),
    (
        "agent_decision_id_unique",
        "CREATE CONSTRAINT agent_decision_id_unique IF NOT EXISTS "
        "FOR (n:AgentDecision) REQUIRE n.decision_id IS UNIQUE",
    ),
)

INDEX_STATEMENTS: tuple[tuple[str, str], ...] = (
    (
        "location_canonical_id_lookup",
        "CREATE INDEX location_canonical_id_lookup IF NOT EXISTS "
        "FOR (n:Location) ON (n.canonical_location_id)",
    ),
    (
        "route_source_location_lookup",
        "CREATE INDEX route_source_location_lookup IF NOT EXISTS "
        "FOR (n:Route) ON (n.source_location_id)",
    ),
    (
        "route_destination_location_lookup",
        "CREATE INDEX route_destination_location_lookup IF NOT EXISTS "
        "FOR (n:Route) ON (n.destination_location_id)",
    ),
    (
        "shipment_current_location_lookup",
        "CREATE INDEX shipment_current_location_lookup IF NOT EXISTS "
        "FOR (n:Shipment) ON (n.current_location_id)",
    ),
    (
        "shipment_active_plan_lookup",
        "CREATE INDEX shipment_active_plan_lookup IF NOT EXISTS "
        "FOR (n:Shipment) ON (n.active_plan_id)",
    ),
)


def bootstrap_schema(manager: Any) -> dict[str, list[str]]:
    """Apply all Phase 1 constraints and indexes through the manager."""

    applied_constraints: list[str] = []
    applied_indexes: list[str] = []
    for name, statement in CONSTRAINT_STATEMENTS:
        manager.execute_write(statement)
        applied_constraints.append(name)
    for name, statement in INDEX_STATEMENTS:
        manager.execute_write(statement)
        applied_indexes.append(name)
    return {
        "constraints": applied_constraints,
        "indexes": applied_indexes,
    }
