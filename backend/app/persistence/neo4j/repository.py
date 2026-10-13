"""Read-only, snapshot-scoped Neo4j repository for migration parity."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from ...domain import (
    Location,
    Priority,
    Route,
    RuntimeDataset,
    Shipment,
    ShipmentRouteLeg,
    WeatherSamplePoint,
)
from .driver import Neo4jConnectionManager
from .importer import IMPORT_SCOPE, SOURCE_SNAPSHOT_ID


RELATIONSHIP_TYPES = (
    "FROM",
    "TO",
    "ORIGINATES_AT",
    "DESTINED_FOR",
    "CURRENTLY_AT",
    "HAS_PLAN",
    "HAS_LEG",
    "USES_ROUTE",
    "NEXT_LEG",
)


class Neo4jReadError(RuntimeError):
    """Raised when a scoped Neo4j read cannot be completed safely."""


class Neo4jRecordNotFound(LookupError):
    """Raised when a requested scoped record does not exist."""


class RoutePlanRecord(BaseModel):
    """Typed plan identity; the runtime domain has no separate plan model."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1)
    shipment_id: str = Field(min_length=1)
    plan_version: int
    active: bool


class ShipmentLegRecord(BaseModel):
    """Stable Neo4j leg identity plus the canonical leg value object."""

    model_config = ConfigDict(extra="forbid")

    leg_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    canonical: ShipmentRouteLeg


def _native(value: Any) -> Any:
    return value.to_native() if hasattr(value, "to_native") else value


def _datetime(value: Any) -> datetime | None:
    value = _native(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        text = value
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if "." in text:
            prefix, suffix = text.split(".", 1)
            timezone_part = ""
            for marker in ("+", "-"):
                if marker in suffix:
                    fraction, timezone_part = suffix.split(marker, 1)
                    timezone_part = marker + timezone_part
                    break
            else:
                fraction = suffix
            text = f"{prefix}.{fraction[:6]}{timezone_part}"
        parsed = datetime.fromisoformat(text)
        return _datetime(parsed)
    raise Neo4jReadError(f"Unsupported Neo4j datetime value: {type(value).__name__}")


def _date(value: Any) -> date | None:
    value = _native(value)
    if value is None or isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise Neo4jReadError(f"Unsupported Neo4j date value: {type(value).__name__}")


def _json_points(value: Any) -> list[WeatherSamplePoint]:
    if value in (None, ""):
        return []
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
        return [WeatherSamplePoint.model_validate(item) for item in decoded]
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise Neo4jReadError("Invalid weather sample point JSON in Neo4j") from exc


class Neo4jReadRepository:
    """Read the imported graph without changing runtime database behavior."""

    def __init__(
        self,
        manager: Neo4jConnectionManager,
        *,
        snapshot_id: str = SOURCE_SNAPSHOT_ID,
        import_scope: str = IMPORT_SCOPE,
    ) -> None:
        if not snapshot_id or not import_scope:
            raise ValueError("snapshot_id and import_scope are required")
        self.manager = manager
        self.snapshot_id = snapshot_id
        self.import_scope = import_scope

    @property
    def scope_parameters(self) -> dict[str, str]:
        return {
            "snapshot_id": self.snapshot_id,
            "import_scope": self.import_scope,
        }

    def _read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        values = {**self.scope_parameters, **(parameters or {})}
        try:
            return self.manager.execute_read(query, values)
        except Exception as exc:
            raise Neo4jReadError("Neo4j scoped read failed") from exc

    def _node_rows(self, label: str, key: str) -> list[dict[str, Any]]:
        query = f"""
            MATCH (n:{label})
            WHERE n.snapshot_id = $snapshot_id
              AND n.import_scope = $import_scope
            RETURN n{{.*}} AS properties
            ORDER BY n.{key}
        """
        return [row["properties"] for row in self._read(query)]

    def get_locations(self) -> list[Location]:
        locations: list[Location] = []
        for properties in self._node_rows("Location", "location_id"):
            values = dict(properties)
            for key in ("snapshot_id", "data_version", "source_system", "import_scope"):
                values.pop(key, None)
            values["latest_observation_date"] = _date(values.get("latest_observation_date"))
            try:
                locations.append(Location.model_validate(values))
            except Exception as exc:
                raise Neo4jReadError("Invalid Location record in Neo4j") from exc
        return locations

    def get_routes(self) -> list[Route]:
        query = """
            MATCH (r:Route)-[from_rel:FROM]->(source:Location),
                  (r)-[to_rel:TO]->(destination:Location)
            WHERE r.snapshot_id = $snapshot_id
              AND r.import_scope = $import_scope
              AND source.snapshot_id = $snapshot_id
              AND source.import_scope = $import_scope
              AND destination.snapshot_id = $snapshot_id
              AND destination.import_scope = $import_scope
              AND from_rel.snapshot_id = $snapshot_id
              AND from_rel.import_scope = $import_scope
              AND to_rel.snapshot_id = $snapshot_id
              AND to_rel.import_scope = $import_scope
            RETURN r{.*} AS properties,
                   source.location_id AS source_location_id,
                   destination.location_id AS destination_location_id
            ORDER BY r.route_id
        """
        routes: list[Route] = []
        for row in self._read(query):
            values = dict(row["properties"])
            for key in ("snapshot_id", "data_version", "source_system", "import_scope"):
                values.pop(key, None)
            values["source_location_id"] = row["source_location_id"]
            values["destination_location_id"] = row["destination_location_id"]
            values["weather_sample_points"] = _json_points(
                values.pop("weather_sample_points_json", None)
            )
            try:
                routes.append(Route.model_validate(values))
            except Exception as exc:
                raise Neo4jReadError("Invalid Route record in Neo4j") from exc
        return routes

    def get_route_plans(self) -> list[RoutePlanRecord]:
        query = """
            MATCH (plan:RoutePlan)
            WHERE plan.snapshot_id = $snapshot_id
              AND plan.import_scope = $import_scope
            RETURN plan{.*} AS properties
            ORDER BY plan.plan_id
        """
        plans: list[RoutePlanRecord] = []
        for row in self._read(query):
            properties = dict(row["properties"])
            for key in ("snapshot_id", "data_version", "source_system", "import_scope"):
                properties.pop(key, None)
            try:
                plans.append(RoutePlanRecord.model_validate(properties))
            except Exception as exc:
                raise Neo4jReadError("Invalid RoutePlan record in Neo4j") from exc
        return plans

    def get_shipment_leg_records(self) -> list[ShipmentLegRecord]:
        query = """
            MATCH (leg:ShipmentLeg)
            WHERE leg.snapshot_id = $snapshot_id
              AND leg.import_scope = $import_scope
            RETURN leg{.*} AS properties
            ORDER BY leg.shipment_id, leg.sequence_no
        """
        records: list[ShipmentLegRecord] = []
        for row in self._read(query):
            values = dict(row["properties"])
            for key in ("snapshot_id", "data_version", "source_system", "import_scope"):
                values.pop(key, None)
            canonical_values = {
                "shipment_id": values["shipment_id"],
                "sequence_no": values["sequence_no"],
                "route_id": values["route_id"],
                "source_location_id": values["source_location_id"],
                "destination_location_id": values["destination_location_id"],
                "status": values.get("status", "PLANNED"),
                "planned_departure": _datetime(values.get("planned_departure")),
                "planned_arrival": _datetime(values.get("planned_arrival")),
                "transport_mode": values.get("transport_mode"),
            }
            try:
                records.append(
                    ShipmentLegRecord(
                        leg_id=values["leg_id"],
                        plan_id=values["plan_id"],
                        canonical=ShipmentRouteLeg.model_validate(canonical_values),
                    )
                )
            except Exception as exc:
                raise Neo4jReadError("Invalid ShipmentLeg record in Neo4j") from exc
        return records

    def get_shipment_legs(self) -> list[ShipmentRouteLeg]:
        return [record.canonical for record in self.get_shipment_leg_records()]

    def get_relationship_counts(self) -> dict[str, int]:
        """Return only owned relationship counts for the configured snapshot."""

        counts: dict[str, int] = {}
        for relationship_type in RELATIONSHIP_TYPES:
            query = f"""
                MATCH ()-[rel:{relationship_type}]->()
                WHERE rel.snapshot_id = $snapshot_id
                  AND rel.import_scope = $import_scope
                RETURN count(rel) AS count
            """
            rows = self._read(query)
            counts[relationship_type] = int(rows[0]["count"]) if rows else 0
        return counts

    def get_shipments(self) -> list[Shipment]:
        leg_records = self.get_shipment_leg_records()
        legs_by_shipment: dict[str, list[ShipmentRouteLeg]] = {}
        for record in leg_records:
            legs_by_shipment.setdefault(record.canonical.shipment_id, []).append(
                record.canonical
            )
        query = """
            MATCH (s:Shipment)
            WHERE s.snapshot_id = $snapshot_id
              AND s.import_scope = $import_scope
            RETURN s{.*} AS properties
            ORDER BY s.shipment_id
        """
        shipments: list[Shipment] = []
        for row in self._read(query):
            values = dict(row["properties"])
            for key in ("snapshot_id", "data_version", "source_system", "import_scope"):
                values.pop(key, None)
            values["required_delivery_time"] = _datetime(values.get("required_delivery_time"))
            values["current_eta"] = _datetime(values.get("current_eta"))
            values["route_legs"] = sorted(
                legs_by_shipment.get(values["shipment_id"], []),
                key=lambda leg: leg.sequence_no,
            )
            values.pop("active_plan_id", None)
            try:
                shipments.append(Shipment.model_validate(values))
            except Exception as exc:
                raise Neo4jReadError("Invalid Shipment record in Neo4j") from exc
        return shipments

    def get_location(self, location_id: str) -> Location:
        record = next(
            (item for item in self.get_locations() if item.location_id == location_id),
            None,
        )
        if record is None:
            raise Neo4jRecordNotFound(f"Location {location_id!r} is not in the scoped snapshot")
        return record

    def load_runtime_dataset(self) -> RuntimeDataset:
        return RuntimeDataset(
            locations=self.get_locations(),
            routes=self.get_routes(),
            shipments=self.get_shipments(),
        )
