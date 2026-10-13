"""Bounded, read-only Neo4j dependency and impact evidence queries."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .importer import IMPORT_SCOPE, SOURCE_SNAPSHOT_ID
from .repository import Neo4jReadError


MAX_TRAVERSAL_DEPTH = 5
DEFAULT_RESULT_LIMIT = 500
MAX_RESULT_LIMIT = 5_000
DEFAULT_QUERY_TIMEOUT_SECONDS = 5.0


class Neo4jImpactQueryError(RuntimeError):
    """Raised when a bounded impact query cannot be completed safely."""


class GraphPathStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: str
    relationship_from_previous: str | None = None


class KGImpactEvidence(BaseModel):
    """One canonical graph trace supporting a direct shipment dependency."""

    model_config = ConfigDict(extra="forbid")

    disruption_type: str
    target_type: Literal["LOCATION", "ROUTE"]
    target_id: str
    shipment_id: str
    shipment_status: str
    current_location_id: str
    plan_id: str
    plan_version: int
    leg_id: str
    sequence_no: int
    leg_status: str
    route_id: str
    source_location_id: str
    destination_location_id: str
    dependency_kind: str
    classification: Literal["DIRECT", "DOWNSTREAM"] = "DIRECT"
    graph_path: list[GraphPathStep]


class DownstreamLegEvidence(BaseModel):
    """A bounded continuation through the schema's same-shipment NEXT_LEG edges."""

    model_config = ConfigDict(extra="forbid")

    shipment_id: str
    plan_id: str
    plan_version: int
    start_leg_id: str
    downstream_leg_id: str
    sequence_no: int
    leg_status: str
    depth: int = Field(ge=1, le=MAX_TRAVERSAL_DEPTH)
    classification: Literal["DOWNSTREAM"] = "DOWNSTREAM"
    graph_path: list[GraphPathStep]


class KGImpactResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disruption_type: str
    target_type: Literal["LOCATION", "ROUTE"]
    target_id: str
    impacted_shipment_ids: list[str]
    evidence: list[KGImpactEvidence]
    downstream: list[DownstreamLegEvidence] = Field(default_factory=list)
    query_name: str
    query_duration_ms: float
    result_limit: int


@dataclass(frozen=True)
class _QueryOutput:
    rows: list[dict[str, Any]]
    duration_ms: float


LOCATION_DEPENDENCY_QUERY = """
MATCH (s:Shipment)-[has_plan:HAS_PLAN]->(plan:RoutePlan)
WHERE s.snapshot_id = $snapshot_id
  AND s.import_scope = $import_scope
  AND plan.snapshot_id = $snapshot_id
  AND plan.import_scope = $import_scope
  AND has_plan.snapshot_id = $snapshot_id
  AND has_plan.import_scope = $import_scope
WITH s, plan
OPTIONAL MATCH (plan)-[:HAS_LEG]->(candidate:ShipmentLeg)
WHERE candidate.snapshot_id = $snapshot_id
  AND candidate.import_scope = $import_scope
  AND (
    candidate.source_location_id = s.current_location_id
    OR candidate.status = 'CURRENT'
  )
WITH s, plan, coalesce(
  min(CASE WHEN candidate.source_location_id = s.current_location_id THEN candidate.sequence_no END),
  min(CASE WHEN candidate.status = 'CURRENT' THEN candidate.sequence_no END),
  1
) AS start_sequence
MATCH (plan)-[has_leg:HAS_LEG]->(leg:ShipmentLeg)
MATCH (leg)-[uses_route:USES_ROUTE]->(route:Route)
MATCH (route)-[from_rel:FROM]->(from_location:Location)
MATCH (route)-[to_rel:TO]->(to_location:Location)
MATCH (target:Location {location_id: $target_id})
WHERE
  s.snapshot_id = $snapshot_id
  AND s.import_scope = $import_scope
  AND plan.snapshot_id = $snapshot_id
  AND plan.import_scope = $import_scope
  AND leg.snapshot_id = $snapshot_id
  AND leg.import_scope = $import_scope
  AND route.snapshot_id = $snapshot_id
  AND route.import_scope = $import_scope
  AND from_location.snapshot_id = $snapshot_id
  AND from_location.import_scope = $import_scope
  AND to_location.snapshot_id = $snapshot_id
  AND to_location.import_scope = $import_scope
  AND target.snapshot_id = $snapshot_id
  AND target.import_scope = $import_scope
  AND has_leg.snapshot_id = $snapshot_id
  AND has_leg.import_scope = $import_scope
  AND uses_route.snapshot_id = $snapshot_id
  AND uses_route.import_scope = $import_scope
  AND from_rel.snapshot_id = $snapshot_id
  AND from_rel.import_scope = $import_scope
  AND to_rel.snapshot_id = $snapshot_id
  AND to_rel.import_scope = $import_scope
  AND NOT s.status IN $inactive_statuses
  AND plan.active = true
  AND plan.plan_version = $active_plan_version
  AND leg.status IN $remaining_statuses
  AND leg.sequence_no >= start_sequence
  AND (
    target.location_id = leg.destination_location_id
    OR (
      leg.source_location_id = s.current_location_id
      AND target.location_id = leg.source_location_id
    )
  )
  AND target.location_id IN [from_location.location_id, to_location.location_id]
RETURN s.shipment_id AS shipment_id,
       s.status AS shipment_status,
       s.current_location_id AS current_location_id,
       plan.plan_id AS plan_id,
       plan.plan_version AS plan_version,
       leg.leg_id AS leg_id,
       leg.sequence_no AS sequence_no,
       leg.status AS leg_status,
       route.route_id AS route_id,
       route.source_location_id AS source_location_id,
       route.destination_location_id AS destination_location_id,
       CASE
         WHEN target.location_id = leg.destination_location_id
         THEN 'REMAINING_DESTINATION'
         ELSE 'CURRENT_LOCATION'
       END AS dependency_kind,
       [
         {entity_type: 'Shipment', entity_id: s.shipment_id, relationship_from_previous: null},
         {entity_type: 'RoutePlan', entity_id: plan.plan_id, relationship_from_previous: 'HAS_PLAN'},
         {entity_type: 'ShipmentLeg', entity_id: leg.leg_id, relationship_from_previous: 'HAS_LEG'},
         {entity_type: 'Route', entity_id: route.route_id, relationship_from_previous: 'USES_ROUTE'},
         {entity_type: 'Location', entity_id: target.location_id,
          relationship_from_previous: CASE WHEN target.location_id = from_location.location_id THEN 'FROM' ELSE 'TO' END}
       ] AS graph_path
ORDER BY s.shipment_id, leg.sequence_no, leg.leg_id
LIMIT $result_limit
"""


ROUTE_DEPENDENCY_QUERY = """
MATCH (s:Shipment)-[has_plan:HAS_PLAN]->(plan:RoutePlan)
WHERE s.snapshot_id = $snapshot_id
  AND s.import_scope = $import_scope
  AND plan.snapshot_id = $snapshot_id
  AND plan.import_scope = $import_scope
  AND has_plan.snapshot_id = $snapshot_id
  AND has_plan.import_scope = $import_scope
WITH s, plan
OPTIONAL MATCH (plan)-[:HAS_LEG]->(candidate:ShipmentLeg)
WHERE candidate.snapshot_id = $snapshot_id
  AND candidate.import_scope = $import_scope
  AND (
    candidate.source_location_id = s.current_location_id
    OR candidate.status = 'CURRENT'
  )
WITH s, plan, coalesce(
  min(CASE WHEN candidate.source_location_id = s.current_location_id THEN candidate.sequence_no END),
  min(CASE WHEN candidate.status = 'CURRENT' THEN candidate.sequence_no END),
  1
) AS start_sequence
MATCH (plan)-[has_leg:HAS_LEG]->(leg:ShipmentLeg)
MATCH (leg)-[uses_route:USES_ROUTE]->(route:Route {route_id: $target_id})
MATCH (route)-[from_rel:FROM]->(from_location:Location)
MATCH (route)-[to_rel:TO]->(to_location:Location)
WHERE
  s.snapshot_id = $snapshot_id
  AND s.import_scope = $import_scope
  AND plan.snapshot_id = $snapshot_id
  AND plan.import_scope = $import_scope
  AND leg.snapshot_id = $snapshot_id
  AND leg.import_scope = $import_scope
  AND route.snapshot_id = $snapshot_id
  AND route.import_scope = $import_scope
  AND from_location.snapshot_id = $snapshot_id
  AND from_location.import_scope = $import_scope
  AND to_location.snapshot_id = $snapshot_id
  AND to_location.import_scope = $import_scope
  AND has_leg.snapshot_id = $snapshot_id
  AND has_leg.import_scope = $import_scope
  AND uses_route.snapshot_id = $snapshot_id
  AND uses_route.import_scope = $import_scope
  AND from_rel.snapshot_id = $snapshot_id
  AND from_rel.import_scope = $import_scope
  AND to_rel.snapshot_id = $snapshot_id
  AND to_rel.import_scope = $import_scope
  AND NOT s.status IN $inactive_statuses
  AND plan.active = true
  AND plan.plan_version = $active_plan_version
  AND leg.status IN $remaining_statuses
  AND leg.sequence_no >= start_sequence
RETURN s.shipment_id AS shipment_id,
       s.status AS shipment_status,
       s.current_location_id AS current_location_id,
       plan.plan_id AS plan_id,
       plan.plan_version AS plan_version,
       leg.leg_id AS leg_id,
       leg.sequence_no AS sequence_no,
       leg.status AS leg_status,
       route.route_id AS route_id,
       route.source_location_id AS source_location_id,
       route.destination_location_id AS destination_location_id,
       'DIRECTED_ROUTE_LEG' AS dependency_kind,
       [
         {entity_type: 'Shipment', entity_id: s.shipment_id, relationship_from_previous: null},
         {entity_type: 'RoutePlan', entity_id: plan.plan_id, relationship_from_previous: 'HAS_PLAN'},
         {entity_type: 'ShipmentLeg', entity_id: leg.leg_id, relationship_from_previous: 'HAS_LEG'},
         {entity_type: 'Route', entity_id: route.route_id, relationship_from_previous: 'USES_ROUTE'},
         {entity_type: 'Location', entity_id: from_location.location_id, relationship_from_previous: 'FROM'},
         {entity_type: 'Location', entity_id: to_location.location_id, relationship_from_previous: 'TO'}
       ] AS graph_path
ORDER BY s.shipment_id, leg.sequence_no, leg.leg_id
LIMIT $result_limit
"""


DOWNSTREAM_LEG_QUERY = """
MATCH path=(start:ShipmentLeg)-[:NEXT_LEG*1..5]->(downstream:ShipmentLeg)
MATCH (plan:RoutePlan)-[has_leg:HAS_LEG]->(start)
WHERE start.leg_id = $start_leg_id
  AND start.snapshot_id = $snapshot_id
  AND start.import_scope = $import_scope
  AND downstream.snapshot_id = $snapshot_id
  AND downstream.import_scope = $import_scope
  AND plan.snapshot_id = $snapshot_id
  AND plan.import_scope = $import_scope
  AND has_leg.snapshot_id = $snapshot_id
  AND has_leg.import_scope = $import_scope
  AND plan.active = true
  AND plan.plan_version = $active_plan_version
  AND ALL(node IN nodes(path)
          WHERE node.snapshot_id = $snapshot_id
            AND node.import_scope = $import_scope
            AND node.status IN $remaining_statuses)
  AND ALL(rel IN relationships(path)
          WHERE rel.snapshot_id = $snapshot_id
            AND rel.import_scope = $import_scope)
  AND length(path) <= $max_depth
RETURN start.shipment_id AS shipment_id,
       plan.plan_id AS plan_id,
       plan.plan_version AS plan_version,
       start.leg_id AS start_leg_id,
       downstream.leg_id AS downstream_leg_id,
       downstream.sequence_no AS sequence_no,
       downstream.status AS leg_status,
       length(path) AS depth,
       [
         {entity_type: 'ShipmentLeg', entity_id: start.leg_id, relationship_from_previous: null}
       ] + [
         node IN nodes(path)[1..]
         | {entity_type: 'ShipmentLeg', entity_id: node.leg_id, relationship_from_previous: 'NEXT_LEG'}
       ] AS graph_path
ORDER BY depth, downstream.sequence_no, downstream.leg_id
LIMIT $result_limit
"""


class Neo4jImpactQueryService:
    """Named, bounded KG analysis; never writes or chooses an alternate route."""

    def __init__(
        self,
        manager: Any,
        *,
        snapshot_id: str = SOURCE_SNAPSHOT_ID,
        import_scope: str = IMPORT_SCOPE,
        query_timeout_seconds: float = DEFAULT_QUERY_TIMEOUT_SECONDS,
        result_limit: int = DEFAULT_RESULT_LIMIT,
    ) -> None:
        if not snapshot_id or not import_scope:
            raise ValueError("snapshot_id and import_scope are required")
        if query_timeout_seconds <= 0:
            raise ValueError("query_timeout_seconds must be greater than zero")
        if result_limit < 1 or result_limit > MAX_RESULT_LIMIT:
            raise ValueError(f"result_limit must be between 1 and {MAX_RESULT_LIMIT}")
        self.manager = manager
        self.snapshot_id = snapshot_id
        self.import_scope = import_scope
        self.query_timeout_seconds = query_timeout_seconds
        self.result_limit = result_limit

    def _execute(self, query_name: str, query: str, parameters: dict[str, Any]) -> _QueryOutput:
        values = {
            "snapshot_id": self.snapshot_id,
            "import_scope": self.import_scope,
            "inactive_statuses": ["DELIVERED", "CANCELLED", "COMPLETED"],
            "remaining_statuses": ["CURRENT", "PLANNED"],
            "active_plan_version": 1,
            "result_limit": self.result_limit,
            **parameters,
        }
        started = perf_counter()
        try:
            rows = self.manager.execute_read(
                query,
                values,
                timeout_seconds=self.query_timeout_seconds,
            )
        except TypeError as exc:
            raise Neo4jImpactQueryError(
                "Neo4j read manager does not support bounded query timeouts"
            ) from exc
        except Exception as exc:
            raise Neo4jImpactQueryError(f"Neo4j impact query failed: {query_name}") from exc
        duration_ms = (perf_counter() - started) * 1000
        if duration_ms > self.query_timeout_seconds * 1000:
            raise Neo4jImpactQueryError(
                f"Neo4j impact query exceeded {self.query_timeout_seconds:.3f}s: {query_name}"
            )
        return _QueryOutput(rows=rows, duration_ms=duration_ms)

    @staticmethod
    def _path(value: Any) -> list[GraphPathStep]:
        try:
            return [GraphPathStep.model_validate(item) for item in value or []]
        except Exception as exc:
            raise Neo4jImpactQueryError("Neo4j returned malformed dependency path") from exc

    def _evidence(
        self,
        rows: list[dict[str, Any]],
        *,
        target_type: Literal["LOCATION", "ROUTE"],
        target_id: str,
        disruption_type: str,
    ) -> list[KGImpactEvidence]:
        evidence = []
        for row in rows:
            try:
                evidence.append(
                    KGImpactEvidence(
                        disruption_type=disruption_type,
                        target_type=target_type,
                        target_id=target_id,
                        shipment_id=str(row["shipment_id"]),
                        shipment_status=str(row["shipment_status"]),
                        current_location_id=str(row["current_location_id"]),
                        plan_id=str(row["plan_id"]),
                        plan_version=int(row["plan_version"]),
                        leg_id=str(row["leg_id"]),
                        sequence_no=int(row["sequence_no"]),
                        leg_status=str(row["leg_status"]),
                        route_id=str(row["route_id"]),
                        source_location_id=str(row["source_location_id"]),
                        destination_location_id=str(row["destination_location_id"]),
                        dependency_kind=str(row["dependency_kind"]),
                        graph_path=self._path(row["graph_path"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise Neo4jImpactQueryError("Neo4j returned malformed impact evidence") from exc
        return evidence

    def _analyze(
        self,
        *,
        query_name: str,
        query: str,
        target_type: Literal["LOCATION", "ROUTE"],
        target_id: str,
        disruption_type: str,
    ) -> KGImpactResult:
        if not target_id:
            raise ValueError("target_id is required")
        output = self._execute(query_name, query, {"target_id": target_id})
        evidence = self._evidence(
            output.rows,
            target_type=target_type,
            target_id=target_id,
            disruption_type=disruption_type,
        )
        return KGImpactResult(
            disruption_type=disruption_type,
            target_type=target_type,
            target_id=target_id,
            impacted_shipment_ids=sorted({item.shipment_id for item in evidence}),
            evidence=evidence,
            query_name=query_name,
            query_duration_ms=round(output.duration_ms, 3),
            result_limit=self.result_limit,
        )

    def analyze_location(self, target_id: str, disruption_type: str) -> KGImpactResult:
        return self._analyze(
            query_name="remaining_location_dependencies",
            query=LOCATION_DEPENDENCY_QUERY,
            target_type="LOCATION",
            target_id=target_id,
            disruption_type=disruption_type,
        )

    def analyze_route(self, target_id: str, disruption_type: str) -> KGImpactResult:
        return self._analyze(
            query_name="remaining_directed_route_dependencies",
            query=ROUTE_DEPENDENCY_QUERY,
            target_type="ROUTE",
            target_id=target_id,
            disruption_type=disruption_type,
        )

    def find_downstream_leg_dependencies(
        self,
        start_leg_id: str,
        *,
        max_depth: int = MAX_TRAVERSAL_DEPTH,
    ) -> tuple[list[DownstreamLegEvidence], float]:
        if not start_leg_id:
            raise ValueError("start_leg_id is required")
        if max_depth < 1 or max_depth > MAX_TRAVERSAL_DEPTH:
            raise ValueError(f"max_depth must be between 1 and {MAX_TRAVERSAL_DEPTH}")
        output = self._execute(
            "bounded_next_leg_dependencies",
            DOWNSTREAM_LEG_QUERY,
            {"start_leg_id": start_leg_id, "max_depth": max_depth},
        )
        records = []
        for row in output.rows:
            try:
                records.append(
                    DownstreamLegEvidence(
                        shipment_id=str(row["shipment_id"]),
                        plan_id=str(row["plan_id"]),
                        plan_version=int(row["plan_version"]),
                        start_leg_id=str(row["start_leg_id"]),
                        downstream_leg_id=str(row["downstream_leg_id"]),
                        sequence_no=int(row["sequence_no"]),
                        leg_status=str(row["leg_status"]),
                        depth=int(row["depth"]),
                        graph_path=self._path(row["graph_path"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise Neo4jImpactQueryError("Neo4j returned malformed downstream evidence") from exc
        return records, output.duration_ms
