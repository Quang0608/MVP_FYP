"""Idempotent import and verification for the active SQLite Asia snapshot."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from ...domain import RuntimeDataset
from ...repository import load_runtime_dataset
from .driver import Neo4jConnectionManager


IMPORTER_VERSION = "neo4j-phase-2/v1"
SOURCE_SCHEMA_VERSION = "neo4j-phase-0/v1"
SOURCE_SNAPSHOT_ID = "asia-runtime-seed-20260913"
IMPORT_SCOPE = "phase2-active-asia-snapshot"
EXPECTED_COUNTS = {
    "locations": 91,
    "routes": 150,
    "shipments": 220,
    "route_plans": 220,
    "ordered_legs": 1000,
}
EXPECTED_RELATIONSHIP_COUNTS = {
    "FROM": 150,
    "TO": 150,
    "ORIGINATES_AT": 220,
    "DESTINED_FOR": 220,
    "CURRENTLY_AT": 220,
    "HAS_PLAN": 220,
    "HAS_LEG": 1000,
    "USES_ROUTE": 1000,
    "NEXT_LEG": 780,
}
NODE_LABELS = {
    "locations": "Location",
    "routes": "Route",
    "shipments": "Shipment",
    "route_plans": "RoutePlan",
    "ordered_legs": "ShipmentLeg",
}
METADATA_KEYS = {
    "snapshot_id",
    "data_version",
    "source_system",
    "import_scope",
}


class ImportValidationError(ValueError):
    """Raised when the active source snapshot cannot be imported safely."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso_value(value: Any) -> Any:
    """Make source and Neo4j values comparable without losing null semantics."""

    if hasattr(value, "to_native"):
        value = value.to_native()
    if isinstance(value, datetime):
        return _utc_datetime(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _iso_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_iso_value(item) for item in value]
    return value


def _non_null(properties: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in properties.items() if value is not None}


def _metadata(snapshot_id: str) -> dict[str, str]:
    return {
        "snapshot_id": snapshot_id,
        "data_version": SOURCE_SCHEMA_VERSION,
        "source_system": "sqlite",
        "import_scope": IMPORT_SCOPE,
    }


def _record_lists(dataset: RuntimeDataset) -> dict[str, list[dict[str, Any]]]:
    locations = [
        location.model_dump(mode="json")
        for location in sorted(dataset.locations, key=lambda item: item.location_id)
    ]
    routes = []
    for route in sorted(dataset.routes, key=lambda item: item.route_id):
        record = route.model_dump(mode="json")
        record["weather_sample_points"] = sorted(
            record.get("weather_sample_points", []),
            key=lambda item: item["sequence"],
        )
        routes.append(record)
    shipments = []
    legs = []
    for shipment in sorted(dataset.shipments, key=lambda item: item.shipment_id):
        shipment_record = shipment.model_dump(mode="json", exclude={"route_legs"})
        shipment_record["route_legs"] = [
            leg.model_dump(mode="json") for leg in shipment.ordered_route_legs
        ]
        shipments.append(shipment_record)
        legs.extend(shipment_record["route_legs"])
    legs.sort(key=lambda item: (item["shipment_id"], item["sequence_no"]))
    return {
        "locations": locations,
        "routes": routes,
        "shipments": shipments,
        "ordered_legs": legs,
    }


def _duplicate_values(values: Iterable[str]) -> list[str]:
    duplicates = [
        value for value, count in Counter(values).items() if count > 1
    ]
    return sorted(duplicates)


def validate_active_dataset(dataset: RuntimeDataset) -> dict[str, Any]:
    """Validate counts, references, ordering, chronology, and progress state."""

    records = _record_lists(dataset)
    locations = {record["location_id"] for record in records["locations"]}
    routes = {record["route_id"]: record for record in records["routes"]}
    shipments = {record["shipment_id"]: record for record in records["shipments"]}
    duplicate_ids = {
        "locations": _duplicate_values(
            record["location_id"] for record in records["locations"]
        ),
        "routes": _duplicate_values(record["route_id"] for record in records["routes"]),
        "shipments": _duplicate_values(
            record["shipment_id"] for record in records["shipments"]
        ),
        "ordered_legs": _duplicate_values(
            f"{record['shipment_id']}:{record['sequence_no']}"
            for record in records["ordered_legs"]
        ),
    }
    reference_errors: list[dict[str, Any]] = []
    for route in records["routes"]:
        for field in ("source_location_id", "destination_location_id"):
            if route[field] not in locations:
                reference_errors.append(
                    {"entity": route["route_id"], "field": field, "value": route[field]}
                )
    for shipment in records["shipments"]:
        for field in (
            "origin_location_id",
            "destination_location_id",
            "current_location_id",
        ):
            if shipment[field] not in locations:
                reference_errors.append(
                    {
                        "entity": shipment["shipment_id"],
                        "field": field,
                        "value": shipment[field],
                    }
                )

    leg_reference_errors: list[dict[str, Any]] = []
    sequence_errors: list[dict[str, Any]] = []
    chronology_errors: list[dict[str, Any]] = []
    progress_errors: list[dict[str, Any]] = []
    for shipment in records["shipments"]:
        shipment_legs = shipment["route_legs"]
        expected_sequences = list(range(1, len(shipment_legs) + 1))
        actual_sequences = [leg["sequence_no"] for leg in shipment_legs]
        if actual_sequences != expected_sequences:
            sequence_errors.append(
                {
                    "shipment_id": shipment["shipment_id"],
                    "expected": expected_sequences,
                    "actual": actual_sequences,
                }
            )
        statuses = [str(leg["status"]).upper() for leg in shipment_legs]
        if any(status not in {"COMPLETED", "CURRENT", "PLANNED"} for status in statuses):
            progress_errors.append(
                {"shipment_id": shipment["shipment_id"], "statuses": statuses}
            )
        if statuses.count("CURRENT") > 1:
            progress_errors.append(
                {"shipment_id": shipment["shipment_id"], "statuses": statuses}
            )
        route_locations = [shipment["origin_location_id"]]
        for leg in shipment_legs:
            route = routes.get(leg["route_id"])
            if route is None:
                leg_reference_errors.append(
                    {
                        "shipment_id": shipment["shipment_id"],
                        "sequence_no": leg["sequence_no"],
                        "route_id": leg["route_id"],
                    }
                )
            else:
                expected_endpoints = {
                    "source_location_id": route["source_location_id"],
                    "destination_location_id": route["destination_location_id"],
                }
                actual_endpoints = {
                    "source_location_id": leg["source_location_id"],
                    "destination_location_id": leg["destination_location_id"],
                }
                if actual_endpoints != expected_endpoints:
                    leg_reference_errors.append(
                        {
                            "shipment_id": shipment["shipment_id"],
                            "sequence_no": leg["sequence_no"],
                            "expected": expected_endpoints,
                            "actual": actual_endpoints,
                        }
                    )
            for field in ("source_location_id", "destination_location_id"):
                if leg[field] not in locations:
                    leg_reference_errors.append(
                        {
                            "shipment_id": shipment["shipment_id"],
                            "sequence_no": leg["sequence_no"],
                            "field": field,
                            "value": leg[field],
                        }
                    )
            if not route_locations or leg["source_location_id"] != route_locations[-1]:
                progress_errors.append(
                    {
                        "shipment_id": shipment["shipment_id"],
                        "sequence_no": leg["sequence_no"],
                        "reason": "leg chain is not contiguous",
                    }
                )
            route_locations.append(leg["destination_location_id"])
            departure = leg.get("planned_departure")
            arrival = leg.get("planned_arrival")
            if departure and arrival and departure > arrival:
                chronology_errors.append(
                    {
                        "shipment_id": shipment["shipment_id"],
                        "sequence_no": leg["sequence_no"],
                        "reason": "departure after arrival",
                    }
                )
        for previous, current in zip(shipment_legs, shipment_legs[1:]):
            if previous.get("planned_arrival") and current.get("planned_departure"):
                if previous["planned_arrival"] > current["planned_departure"]:
                    chronology_errors.append(
                        {
                            "shipment_id": shipment["shipment_id"],
                            "sequence_no": current["sequence_no"],
                            "reason": "legs overlap out of order",
                        }
                    )
        if shipment["current_location_id"] not in route_locations:
            progress_errors.append(
                {
                    "shipment_id": shipment["shipment_id"],
                    "reason": "current location is not on the ordered route",
                    "current_location_id": shipment["current_location_id"],
                }
            )

    counts = {
        "locations": len(records["locations"]),
        "routes": len(records["routes"]),
        "shipments": len(records["shipments"]),
        "route_plans": len(records["shipments"]),
        "ordered_legs": len(records["ordered_legs"]),
    }
    checks = {
        "counts": counts,
        "counts_match": counts == EXPECTED_COUNTS,
        "duplicate_ids": duplicate_ids,
        "reference_errors": reference_errors,
        "leg_reference_errors": leg_reference_errors,
        "sequence_errors": sequence_errors,
        "chronology_errors": chronology_errors,
        "progress_errors": progress_errors,
        "all_shipments_have_legs": all(
            shipment["route_legs"] for shipment in records["shipments"]
        ),
    }
    checks["pass"] = (
        checks["counts_match"]
        and not any(duplicate_ids.values())
        and not reference_errors
        and not leg_reference_errors
        and not sequence_errors
        and not chronology_errors
        and not progress_errors
        and checks["all_shipments_have_legs"]
    )
    return checks


def load_source_dataset(source_sqlite: Path) -> RuntimeDataset:
    """Load one SQLite file through the repository's canonical mapper."""

    if not source_sqlite.exists():
        raise ImportValidationError(f"SQLite source does not exist: {source_sqlite}")
    if source_sqlite.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        raise ImportValidationError(
            "--source-sqlite must point to a SQLite database file"
        )
    source_engine = create_engine(
        URL.create("sqlite", database=str(source_sqlite.resolve())),
        connect_args={"check_same_thread": False},
    )
    source_session = sessionmaker(bind=source_engine, expire_on_commit=False)
    try:
        return load_runtime_dataset(source_session)
    except Exception as exc:
        raise ImportValidationError(
            f"Could not load canonical active dataset from {source_sqlite}"
        ) from exc
    finally:
        source_engine.dispose()


def _location_properties(location: Any, snapshot_id: str) -> dict[str, Any]:
    properties = {
        "location_id": location.location_id,
        "name": location.name,
        "location_type": location.location_type.value,
        "country": location.country,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "unlocode": location.unlocode,
        "status": location.status.value,
        "source": location.source,
        "capacity": location.capacity,
        "city": location.city,
        "canonical_location_id": location.canonical_location_id,
        "source_entity_id": location.source_entity_id,
        "portwatch_source_port_id": location.portwatch_source_port_id,
        "latest_observation_date": location.latest_observation_date,
        "activity_score": location.activity_score,
        "activity_anomaly_score": location.activity_anomaly_score,
        "operational_status": location.operational_status,
    }
    return _non_null({**properties, **_metadata(snapshot_id)})


def _route_properties(route: Any, snapshot_id: str) -> dict[str, Any]:
    weather_points = [
        point.model_dump(mode="json")
        for point in sorted(route.weather_sample_points, key=lambda item: item.sequence)
    ]
    properties = {
        "route_id": route.route_id,
        "source_location_id": route.source_location_id,
        "destination_location_id": route.destination_location_id,
        "transport_mode": route.transport_mode,
        "distance_km": route.distance_km,
        "base_duration_hours": route.base_duration_hours,
        "base_cost": route.base_cost,
        "max_capacity": route.max_capacity,
        "risk_score": route.risk_score,
        "status": route.status.value,
        "current_load": route.current_load,
        "source": route.source,
        "source_entity_id": route.source_entity_id,
        "corridor_ids": list(route.corridor_ids),
        "weather_sample_points_json": _canonical_json(weather_points),
    }
    return _non_null({**properties, **_metadata(snapshot_id)})


def _shipment_properties(shipment: Any, plan_id: str, snapshot_id: str) -> dict[str, Any]:
    properties = {
        "shipment_id": shipment.shipment_id,
        "origin_location_id": shipment.origin_location_id,
        "destination_location_id": shipment.destination_location_id,
        "current_location_id": shipment.current_location_id,
        "priority": shipment.priority.value,
        "required_delivery_time": _utc_datetime(shipment.required_delivery_time),
        "current_eta": _utc_datetime(shipment.current_eta),
        "load_units": shipment.load_units,
        "cargo_type": shipment.cargo_type,
        "status": shipment.status,
        "order_id": shipment.order_id,
        "customer_id": shipment.customer_id,
        "cargo_value": shipment.cargo_value,
        "weight_kg": shipment.weight_kg,
        "source": shipment.source,
        "active_plan_id": plan_id,
    }
    return _non_null({**properties, **_metadata(snapshot_id)})


def _plan_properties(shipment: Any, plan_id: str, snapshot_id: str) -> dict[str, Any]:
    return {
        **_metadata(snapshot_id),
        "plan_id": plan_id,
        "shipment_id": shipment.shipment_id,
        "plan_version": 1,
        "active": True,
    }


def _leg_properties(
    shipment: Any,
    leg: Any,
    plan_id: str,
    snapshot_id: str,
) -> dict[str, Any]:
    leg_id = f"{plan_id}:{leg.sequence_no}"
    properties = {
        "leg_id": leg_id,
        "shipment_id": shipment.shipment_id,
        "plan_id": plan_id,
        "sequence_no": leg.sequence_no,
        "route_id": leg.route_id,
        "source_location_id": leg.source_location_id,
        "destination_location_id": leg.destination_location_id,
        "status": leg.status,
        "planned_departure": _utc_datetime(leg.planned_departure),
        "planned_arrival": _utc_datetime(leg.planned_arrival),
        "transport_mode": leg.transport_mode,
    }
    return _non_null({**properties, **_metadata(snapshot_id)})


def _node_rows(dataset: RuntimeDataset, snapshot_id: str) -> dict[str, list[dict[str, Any]]]:
    locations = [
        {"id": location.location_id, "properties": _location_properties(location, snapshot_id)}
        for location in sorted(dataset.locations, key=lambda item: item.location_id)
    ]
    routes = [
        {"id": route.route_id, "properties": _route_properties(route, snapshot_id)}
        for route in sorted(dataset.routes, key=lambda item: item.route_id)
    ]
    shipments = []
    plans = []
    legs = []
    for shipment in sorted(dataset.shipments, key=lambda item: item.shipment_id):
        plan_id = f"{shipment.shipment_id}:v1"
        shipments.append(
            {
                "id": shipment.shipment_id,
                "properties": _shipment_properties(shipment, plan_id, snapshot_id),
            }
        )
        plans.append(
            {
                "id": plan_id,
                "properties": _plan_properties(shipment, plan_id, snapshot_id),
            }
        )
        for leg in shipment.ordered_route_legs:
            leg_id = f"{plan_id}:{leg.sequence_no}"
            legs.append(
                {
                    "id": leg_id,
                    "properties": _leg_properties(
                        shipment, leg, plan_id, snapshot_id
                    ),
                }
            )
    return {
        "locations": locations,
        "routes": routes,
        "shipments": shipments,
        "route_plans": plans,
        "ordered_legs": legs,
    }


NODE_IMPORT_QUERIES = {
    "locations": """
        UNWIND $rows AS row
        MERGE (n:Location {location_id: row.id})
        SET n += row.properties
    """,
    "routes": """
        UNWIND $rows AS row
        MERGE (n:Route {route_id: row.id})
        SET n += row.properties
    """,
    "shipments": """
        UNWIND $rows AS row
        MERGE (n:Shipment {shipment_id: row.id})
        SET n += row.properties
    """,
    "route_plans": """
        UNWIND $rows AS row
        MERGE (n:RoutePlan {plan_id: row.id})
        SET n += row.properties
    """,
    "ordered_legs": """
        UNWIND $rows AS row
        MERGE (n:ShipmentLeg {leg_id: row.id})
        SET n += row.properties
    """,
}


def _relationship_properties(snapshot_id: str) -> dict[str, str]:
    return {
        "snapshot_id": snapshot_id,
        "data_version": SOURCE_SCHEMA_VERSION,
        "import_scope": IMPORT_SCOPE,
    }


def _relationship_rows(dataset: RuntimeDataset, snapshot_id: str) -> dict[str, list[dict[str, Any]]]:
    properties = _relationship_properties(snapshot_id)
    rows: dict[str, list[dict[str, Any]]] = {
        "FROM": [],
        "TO": [],
        "ORIGINATES_AT": [],
        "DESTINED_FOR": [],
        "CURRENTLY_AT": [],
        "HAS_PLAN": [],
        "HAS_LEG": [],
        "USES_ROUTE": [],
        "NEXT_LEG": [],
    }
    for route in sorted(dataset.routes, key=lambda item: item.route_id):
        rows["FROM"].append(
            {
                "from_id": route.route_id,
                "to_id": route.source_location_id,
                "properties": properties,
            }
        )
        rows["TO"].append(
            {
                "from_id": route.route_id,
                "to_id": route.destination_location_id,
                "properties": properties,
            }
        )
    for shipment in sorted(dataset.shipments, key=lambda item: item.shipment_id):
        plan_id = f"{shipment.shipment_id}:v1"
        rows["ORIGINATES_AT"].append(
            {
                "from_id": shipment.shipment_id,
                "to_id": shipment.origin_location_id,
                "properties": properties,
            }
        )
        rows["DESTINED_FOR"].append(
            {
                "from_id": shipment.shipment_id,
                "to_id": shipment.destination_location_id,
                "properties": properties,
            }
        )
        rows["CURRENTLY_AT"].append(
            {
                "from_id": shipment.shipment_id,
                "to_id": shipment.current_location_id,
                "properties": properties,
            }
        )
        rows["HAS_PLAN"].append(
            {
                "from_id": shipment.shipment_id,
                "to_id": plan_id,
                "properties": properties,
            }
        )
        ordered_legs = shipment.ordered_route_legs
        for index, leg in enumerate(ordered_legs):
            leg_id = f"{plan_id}:{leg.sequence_no}"
            rows["HAS_LEG"].append(
                {
                    "from_id": plan_id,
                    "to_id": leg_id,
                    "properties": {**properties, "sequence_no": leg.sequence_no},
                }
            )
            rows["USES_ROUTE"].append(
                {
                    "from_id": leg_id,
                    "to_id": leg.route_id,
                    "properties": {**properties, "sequence_no": leg.sequence_no},
                }
            )
            next_leg_id = None
            if index + 1 < len(ordered_legs):
                next_leg_id = f"{plan_id}:{ordered_legs[index + 1].sequence_no}"
            rows["NEXT_LEG"].append(
                {
                    "from_id": leg_id,
                    "to_id": next_leg_id,
                    "properties": properties,
                }
            )
    return rows


RELATIONSHIP_IMPORT_QUERIES = {
    "FROM": """
        UNWIND $rows AS row
        MATCH (a:Route {route_id: row.from_id})
        MATCH (b:Location {location_id: row.to_id})
        MERGE (a)-[rel:FROM]->(b)
        SET rel += row.properties
    """,
    "TO": """
        UNWIND $rows AS row
        MATCH (a:Route {route_id: row.from_id})
        MATCH (b:Location {location_id: row.to_id})
        MERGE (a)-[rel:TO]->(b)
        SET rel += row.properties
    """,
    "ORIGINATES_AT": """
        UNWIND $rows AS row
        MATCH (a:Shipment {shipment_id: row.from_id})
        MATCH (b:Location {location_id: row.to_id})
        MERGE (a)-[rel:ORIGINATES_AT]->(b)
        SET rel += row.properties
    """,
    "DESTINED_FOR": """
        UNWIND $rows AS row
        MATCH (a:Shipment {shipment_id: row.from_id})
        MATCH (b:Location {location_id: row.to_id})
        MERGE (a)-[rel:DESTINED_FOR]->(b)
        SET rel += row.properties
    """,
    "CURRENTLY_AT": """
        UNWIND $rows AS row
        MATCH (a:Shipment {shipment_id: row.from_id})
        MATCH (b:Location {location_id: row.to_id})
        MERGE (a)-[rel:CURRENTLY_AT]->(b)
        SET rel += row.properties
    """,
    "HAS_PLAN": """
        UNWIND $rows AS row
        MATCH (a:Shipment {shipment_id: row.from_id})
        MATCH (b:RoutePlan {plan_id: row.to_id})
        MERGE (a)-[rel:HAS_PLAN]->(b)
        SET rel += row.properties
    """,
    "HAS_LEG": """
        UNWIND $rows AS row
        MATCH (a:RoutePlan {plan_id: row.from_id})
        MATCH (b:ShipmentLeg {leg_id: row.to_id})
        MERGE (a)-[rel:HAS_LEG]->(b)
        SET rel += row.properties
    """,
    "USES_ROUTE": """
        UNWIND $rows AS row
        MATCH (a:ShipmentLeg {leg_id: row.from_id})
        MATCH (b:Route {route_id: row.to_id})
        MERGE (a)-[rel:USES_ROUTE]->(b)
        SET rel += row.properties
    """,
    "NEXT_LEG": """
        UNWIND $rows AS row
        MATCH (a:ShipmentLeg {leg_id: row.from_id})
        MATCH (b:ShipmentLeg {leg_id: row.to_id})
        MERGE (a)-[rel:NEXT_LEG]->(b)
        SET rel += row.properties
    """,
}


def _write_batches(
    manager: Neo4jConnectionManager,
    query: str,
    rows: list[dict[str, Any]],
    batch_size: int = 100,
) -> int:
    batches = 0
    for start in range(0, len(rows), batch_size):
        manager.execute_write(query, {"rows": rows[start : start + batch_size]})
        batches += 1
    return batches


def _assert_schema_ready(manager: Neo4jConnectionManager) -> None:
    expected_constraints = {
        "location_id_unique",
        "route_id_unique",
        "shipment_id_unique",
        "route_plan_id_unique",
        "shipment_leg_id_unique",
        "disruption_id_unique",
        "simulation_run_id_unique",
        "agent_decision_id_unique",
    }
    expected_indexes = {
        "location_canonical_id_lookup",
        "route_source_location_lookup",
        "route_destination_location_lookup",
        "shipment_current_location_lookup",
        "shipment_active_plan_lookup",
    }
    constraints = {
        row["name"]
        for row in manager.execute_read("SHOW CONSTRAINTS YIELD name RETURN name")
    }
    indexes = {
        row["name"]
        for row in manager.execute_read("SHOW INDEXES YIELD name RETURN name")
    }
    missing_constraints = sorted(expected_constraints - constraints)
    missing_indexes = sorted(expected_indexes - indexes)
    if missing_constraints or missing_indexes:
        raise ImportValidationError(
            "Neo4j Phase 1 schema is incomplete: "
            f"missing constraints={missing_constraints}, indexes={missing_indexes}"
        )


def _cleanup_owned_relationships(
    manager: Neo4jConnectionManager,
    relationship_rows: dict[str, list[dict[str, Any]]],
    snapshot_id: str,
) -> None:
    """Remove only stale relationships previously owned by this import scope."""

    route_endpoint_rows = relationship_rows["FROM"]
    manager.execute_write(
        """
        UNWIND $rows AS row
        MATCH (a:Route {route_id: row.from_id})-[rel:FROM]->(b:Location)
        WHERE rel.snapshot_id = $snapshot_id
          AND rel.import_scope = $scope
          AND b.location_id <> row.to_id
        DELETE rel
        """,
        {"rows": route_endpoint_rows, "snapshot_id": snapshot_id, "scope": IMPORT_SCOPE},
    )
    manager.execute_write(
        """
        UNWIND $rows AS row
        MATCH (a:Route {route_id: row.from_id})-[rel:TO]->(b:Location)
        WHERE rel.snapshot_id = $snapshot_id
          AND rel.import_scope = $scope
          AND b.location_id <> row.to_id
        DELETE rel
        """,
        {"rows": relationship_rows["TO"], "snapshot_id": snapshot_id, "scope": IMPORT_SCOPE},
    )
    for relationship_type in ("ORIGINATES_AT", "DESTINED_FOR", "CURRENTLY_AT"):
        manager.execute_write(
            f"""
            UNWIND $rows AS row
            MATCH (a:Shipment {{shipment_id: row.from_id}})-[rel:{relationship_type}]->(b:Location)
            WHERE rel.snapshot_id = $snapshot_id
              AND rel.import_scope = $scope
              AND b.location_id <> row.to_id
            DELETE rel
            """,
            {
                "rows": relationship_rows[relationship_type],
                "snapshot_id": snapshot_id,
                "scope": IMPORT_SCOPE,
            },
        )
    manager.execute_write(
        """
        UNWIND $rows AS row
        MATCH (a:Shipment {shipment_id: row.from_id})-[rel:HAS_PLAN]->(b:RoutePlan)
        WHERE rel.snapshot_id = $snapshot_id
          AND rel.import_scope = $scope
          AND b.plan_id <> row.to_id
        DELETE rel
        """,
        {"rows": relationship_rows["HAS_PLAN"], "snapshot_id": snapshot_id, "scope": IMPORT_SCOPE},
    )
    for relationship_type in ("HAS_LEG", "USES_ROUTE"):
        start_label = "RoutePlan" if relationship_type == "HAS_LEG" else "ShipmentLeg"
        end_label = "ShipmentLeg" if relationship_type == "HAS_LEG" else "Route"
        start_key = "plan_id" if relationship_type == "HAS_LEG" else "leg_id"
        end_key = "leg_id" if relationship_type == "HAS_LEG" else "route_id"
        manager.execute_write(
            f"""
            UNWIND $rows AS row
            MATCH (a:{start_label} {{{start_key}: row.from_id}})-[rel:{relationship_type}]->(b:{end_label})
            WHERE rel.snapshot_id = $snapshot_id
              AND rel.import_scope = $scope
              AND b.{end_key} <> row.to_id
            DELETE rel
            """,
            {
                "rows": relationship_rows[relationship_type],
                "snapshot_id": snapshot_id,
                "scope": IMPORT_SCOPE,
            },
        )
    manager.execute_write(
        """
        UNWIND $rows AS row
        MATCH (a:ShipmentLeg {leg_id: row.from_id})-[rel:NEXT_LEG]->(b:ShipmentLeg)
        WHERE rel.snapshot_id = $snapshot_id
          AND rel.import_scope = $scope
          AND (row.to_id IS NULL OR b.leg_id <> row.to_id)
        DELETE rel
        """,
        {"rows": relationship_rows["NEXT_LEG"], "snapshot_id": snapshot_id, "scope": IMPORT_SCOPE},
    )


def import_dataset(
    manager: Neo4jConnectionManager,
    dataset: RuntimeDataset,
    snapshot_id: str,
) -> dict[str, Any]:
    """Import validated nodes and typed relationships without deleting nodes."""

    _assert_schema_ready(manager)
    rows = _node_rows(dataset, snapshot_id)
    relationship_rows = _relationship_rows(dataset, snapshot_id)
    batch_counts: dict[str, int] = {}
    for entity in ("locations", "routes", "shipments", "route_plans", "ordered_legs"):
        batch_counts[entity] = _write_batches(
            manager,
            NODE_IMPORT_QUERIES[entity],
            rows[entity],
        )
    _cleanup_owned_relationships(manager, relationship_rows, snapshot_id)
    for relationship_type, relation_rows in relationship_rows.items():
        filtered_rows = [row for row in relation_rows if row["to_id"] is not None]
        batch_counts[relationship_type] = _write_batches(
            manager,
            RELATIONSHIP_IMPORT_QUERIES[relationship_type],
            filtered_rows,
        )
    return {
        "node_rows": {entity: len(entity_rows) for entity, entity_rows in rows.items()},
        "relationship_rows": {
            relationship_type: sum(
                row["to_id"] is not None for row in relation_rows
            )
            for relationship_type, relation_rows in relationship_rows.items()
        },
        "batch_counts": batch_counts,
    }


def _source_properties(dataset: RuntimeDataset, snapshot_id: str) -> dict[str, dict[str, dict[str, Any]]]:
    rows = _node_rows(dataset, snapshot_id)
    return {
        entity: {row["id"]: row["properties"] for row in entity_rows}
        for entity, entity_rows in rows.items()
    }


def _read_nodes(
    manager: Neo4jConnectionManager,
    label: str,
    key: str,
    snapshot_id: str,
) -> list[dict[str, Any]]:
    query = f"""
        MATCH (n:{label})
        WHERE n.snapshot_id = $snapshot_id
        RETURN n{{.*}} AS properties
        ORDER BY n.{key}
    """
    return [row["properties"] for row in manager.execute_read(query, {"snapshot_id": snapshot_id})]


def _compare_node_properties(
    actual_rows: list[dict[str, Any]],
    expected_by_id: dict[str, dict[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    actual_by_id = {str(row[key]): row for row in actual_rows if key in row}
    mismatches: list[dict[str, Any]] = []
    if set(actual_by_id) != set(expected_by_id):
        mismatches.append(
            {
                "field": key,
                "expected_ids_missing": sorted(set(expected_by_id) - set(actual_by_id)),
                "unexpected_ids": sorted(set(actual_by_id) - set(expected_by_id)),
            }
        )
    for entity_id in sorted(set(expected_by_id) & set(actual_by_id)):
        expected = {
            name: _iso_value(value)
            for name, value in expected_by_id[entity_id].items()
            if name not in METADATA_KEYS
        }
        actual = {
            name: _iso_value(value)
            for name, value in actual_by_id[entity_id].items()
            if name not in METADATA_KEYS
        }
        if expected != actual:
            mismatches.append(
                {
                    "id": entity_id,
                    "expected": expected,
                    "actual": actual,
                }
            )
    return mismatches


def verify_import(
    manager: Neo4jConnectionManager,
    dataset: RuntimeDataset,
    snapshot_id: str,
) -> dict[str, Any]:
    """Verify scoped graph counts, IDs, relationships, and canonical attributes."""

    expected_properties = _source_properties(dataset, snapshot_id)
    node_keys = {
        "locations": ("Location", "location_id"),
        "routes": ("Route", "route_id"),
        "shipments": ("Shipment", "shipment_id"),
        "route_plans": ("RoutePlan", "plan_id"),
        "ordered_legs": ("ShipmentLeg", "leg_id"),
    }
    counts: dict[str, int] = {}
    id_sets: dict[str, list[str]] = {}
    attribute_mismatches: list[dict[str, Any]] = []
    duplicate_nodes: dict[str, list[str]] = {}
    for entity, (label, key) in node_keys.items():
        actual_rows = _read_nodes(manager, label, key, snapshot_id)
        counts[entity] = len(actual_rows)
        id_sets[entity] = sorted(str(row[key]) for row in actual_rows if key in row)
        duplicate_rows = manager.execute_read(
            f"""
            MATCH (n:{label})
            WHERE n.snapshot_id = $snapshot_id
            RETURN n.{key} AS id, count(n) AS count
            ORDER BY id
            """,
            {"snapshot_id": snapshot_id},
        )
        duplicate_nodes[entity] = sorted(
            str(row["id"]) for row in duplicate_rows if int(row["count"]) > 1
        )
        attribute_mismatches.extend(
            {
                "entity": entity,
                **mismatch,
            }
            for mismatch in _compare_node_properties(
                actual_rows,
                expected_properties[entity],
                key,
            )
        )

    relationship_counts: dict[str, int] = {}
    for relationship_type in EXPECTED_RELATIONSHIP_COUNTS:
        rows = manager.execute_read(
            f"""
            MATCH ()-[rel:{relationship_type}]->()
            WHERE rel.snapshot_id = $snapshot_id
              AND rel.import_scope = $scope
            RETURN count(rel) AS count
            """,
            {"snapshot_id": snapshot_id, "scope": IMPORT_SCOPE},
        )
        relationship_counts[relationship_type] = int(rows[0]["count"]) if rows else 0

    reference_queries = {
        "route_endpoint_mismatches": """
            MATCH (r:Route)-[rel:FROM|TO]->(l:Location)
            WHERE r.snapshot_id = $snapshot_id
              AND rel.snapshot_id = $snapshot_id
              AND rel.import_scope = $scope
              AND ((type(rel) = 'FROM' AND l.location_id <> r.source_location_id)
                OR (type(rel) = 'TO' AND l.location_id <> r.destination_location_id))
            RETURN count(rel) AS count
        """,
        "shipment_location_mismatches": """
            MATCH (s:Shipment)-[rel:ORIGINATES_AT|DESTINED_FOR|CURRENTLY_AT]->(l:Location)
            WHERE s.snapshot_id = $snapshot_id
              AND rel.snapshot_id = $snapshot_id
              AND rel.import_scope = $scope
              AND ((type(rel) = 'ORIGINATES_AT' AND l.location_id <> s.origin_location_id)
                OR (type(rel) = 'DESTINED_FOR' AND l.location_id <> s.destination_location_id)
                OR (type(rel) = 'CURRENTLY_AT' AND l.location_id <> s.current_location_id))
            RETURN count(rel) AS count
        """,
        "leg_route_mismatches": """
            MATCH (leg:ShipmentLeg)-[rel:USES_ROUTE]->(r:Route)
            WHERE leg.snapshot_id = $snapshot_id
              AND rel.snapshot_id = $snapshot_id
              AND rel.import_scope = $scope
              AND leg.route_id <> r.route_id
            RETURN count(rel) AS count
        """,
        "leg_plan_mismatches": """
            MATCH (plan:RoutePlan)-[rel:HAS_LEG]->(leg:ShipmentLeg)
            WHERE plan.snapshot_id = $snapshot_id
              AND rel.snapshot_id = $snapshot_id
              AND rel.import_scope = $scope
              AND (leg.plan_id <> plan.plan_id OR leg.sequence_no <> rel.sequence_no)
            RETURN count(rel) AS count
        """,
        "next_leg_mismatches": """
            MATCH (a:ShipmentLeg)-[rel:NEXT_LEG]->(b:ShipmentLeg)
            WHERE a.snapshot_id = $snapshot_id
              AND rel.snapshot_id = $snapshot_id
              AND rel.import_scope = $scope
              AND (b.plan_id <> a.plan_id OR b.sequence_no <> a.sequence_no + 1)
            RETURN count(rel) AS count
        """,
    }
    reference_mismatches = {}
    for name, query in reference_queries.items():
        rows = manager.execute_read(
            query,
            {"snapshot_id": snapshot_id, "scope": IMPORT_SCOPE},
        )
        reference_mismatches[name] = int(rows[0]["count"]) if rows else 0

    expected_counts = {**EXPECTED_COUNTS}
    ids_match = all(
        id_sets[entity] == sorted(expected_properties[entity])
        for entity in expected_properties
    )
    counts_match = counts == expected_counts
    relationship_counts_match = relationship_counts == EXPECTED_RELATIONSHIP_COUNTS
    pass_result = (
        counts_match
        and ids_match
        and not any(duplicate_nodes.values())
        and not attribute_mismatches
        and relationship_counts_match
        and not any(reference_mismatches.values())
    )
    return {
        "pass": pass_result,
        "counts": counts,
        "expected_counts": expected_counts,
        "id_sets_match": ids_match,
        "duplicate_nodes": duplicate_nodes,
        "relationship_counts": relationship_counts,
        "expected_relationship_counts": EXPECTED_RELATIONSHIP_COUNTS,
        "attribute_mismatches": attribute_mismatches,
        "reference_mismatches": reference_mismatches,
    }


def build_manifest(
    dataset: RuntimeDataset,
    snapshot_id: str,
    source_sqlite: Path,
    mode: str,
    import_run_id: str,
    validation: dict[str, Any],
    import_result: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    records = _record_lists(dataset)
    imported_ids = {
        "locations": sorted(record["location_id"] for record in records["locations"]),
        "routes": sorted(record["route_id"] for record in records["routes"]),
        "shipments": sorted(record["shipment_id"] for record in records["shipments"]),
        "route_plans": sorted(
            f"{record['shipment_id']}:v1" for record in records["shipments"]
        ),
        "ordered_legs": sorted(
            f"{record['shipment_id']}:v1:{record['sequence_no']}"
            for record in records["ordered_legs"]
        ),
    }
    hashes = {
        entity: {
            "id_hash": _sha256(imported_ids[entity]),
            "content_hash": _sha256(records["ordered_legs" if entity == "ordered_legs" else entity]),
        }
        for entity in ("locations", "routes", "shipments", "ordered_legs")
    }
    return {
        "importer_version": IMPORTER_VERSION,
        "import_run_id": import_run_id,
        "mode": mode,
        "snapshot_id": snapshot_id,
        "dataset_version": SOURCE_SCHEMA_VERSION,
        "source": {
            "backend": "sqlite",
            "database_filename": source_sqlite.name,
            "active_loader": "backend.app.repository.load_runtime_dataset",
            "source_snapshot": snapshot_id,
        },
        "counts": {
            **validation.get("counts", {}),
        },
        "expected_counts": EXPECTED_COUNTS,
        "imported_ids": imported_ids,
        "hashes": hashes,
        "relationship_counts_expected": EXPECTED_RELATIONSHIP_COUNTS,
        "validation": validation,
        "import_result": import_result or {},
        "verification": verification or {},
        "rejected_records": [],
        "unresolved_references": (
            validation.get("reference_errors", [])
            + validation.get("leg_reference_errors", [])
        ),
    }


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_import(
    *,
    snapshot_id: str,
    source_sqlite: Path,
    mode: str,
    manifest_out: Path,
    manager: Neo4jConnectionManager | None = None,
) -> dict[str, Any]:
    if snapshot_id != SOURCE_SNAPSHOT_ID:
        raise ImportValidationError(
            f"Unsupported snapshot_id {snapshot_id!r}; expected {SOURCE_SNAPSHOT_ID!r}"
        )
    dataset = load_source_dataset(source_sqlite)
    validation = validate_active_dataset(dataset)
    if not validation["pass"]:
        report = build_manifest(
            dataset,
            snapshot_id,
            source_sqlite,
            mode,
            "not-created",
            validation,
        )
        write_manifest(report, manifest_out)
        raise ImportValidationError(
            f"Active SQLite validation failed; report written to {manifest_out}"
        )
    import_run_id = datetime.now(timezone.utc).strftime("phase2-%Y%m%dT%H%M%SZ")
    import_result: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    if mode == "execute":
        if manager is None:
            raise ImportValidationError("Neo4j manager is required for execute mode")
        health = manager.health_check()
        if health.status != "ok":
            raise ImportValidationError(
                f"Neo4j is not ready for import: {health.status}"
            )
        import_result = import_dataset(manager, dataset, snapshot_id)
        verification = verify_import(manager, dataset, snapshot_id)
        if not verification["pass"]:
            report = build_manifest(
                dataset,
                snapshot_id,
                source_sqlite,
                mode,
                import_run_id,
                validation,
                import_result,
                verification,
            )
            write_manifest(report, manifest_out)
            raise ImportValidationError(
                f"Neo4j import verification failed; report written to {manifest_out}"
            )
    elif mode == "verify":
        if manager is None:
            raise ImportValidationError("Neo4j manager is required for verify mode")
        health = manager.health_check()
        if health.status != "ok":
            raise ImportValidationError(
                f"Neo4j is not ready for verification: {health.status}"
            )
        verification = verify_import(manager, dataset, snapshot_id)
    report = build_manifest(
        dataset,
        snapshot_id,
        source_sqlite,
        mode,
        import_run_id,
        validation,
        import_result,
        verification,
    )
    write_manifest(report, manifest_out)
    return report
