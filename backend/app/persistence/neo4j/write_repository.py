"""Explicit Neo4j write repository for the supported Phase 5 state records."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...schemas import Disruption
from .driver import Neo4jConnectionManager
from .importer import IMPORT_SCOPE, SOURCE_SNAPSHOT_ID


WRITE_DATA_VERSION = "neo4j-phase-5/v1"
DEFAULT_WRITE_SCOPE = "phase5-operational-write"
MAX_JSON_BYTES = 1_000_000
ALLOWED_DECISION_STATUSES = {"REROUTED", "NO_FEASIBLE_ROUTE"}


class Neo4jWriteError(RuntimeError):
    """Base error for a failed atomic Neo4j write."""


class Neo4jWriteValidationError(Neo4jWriteError, ValueError):
    """Raised when a write violates domain or reference invariants."""


class Neo4jWriteConflictError(Neo4jWriteError):
    """Raised for an idempotency conflict or stale optimistic version."""


class Neo4jWriteNotFoundError(Neo4jWriteError, LookupError):
    """Raised when a required graph record does not exist."""


class Neo4jUnsupportedWriteError(Neo4jWriteError, NotImplementedError):
    """Raised for a canonical write path not present in the SQLite application."""


class WriteReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    action: Literal["CREATED", "UPDATED", "IDEMPOTENT"]
    write_version: int = Field(ge=0)
    idempotency_key: str


def _canonical_json(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise Neo4jWriteValidationError("Write payload is not JSON serializable") from exc
    if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
        raise Neo4jWriteValidationError(
            f"Write payload exceeds the {MAX_JSON_BYTES}-byte limit"
        )
    return encoded


def _key(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _rows(transaction: Any, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    return transaction.run(query, parameters).data()


class Neo4jWriteRepository:
    """Atomic write boundary, never selected by normal SQLite application startup."""

    def __init__(
        self,
        manager: Neo4jConnectionManager,
        *,
        snapshot_id: str,
        import_scope: str = DEFAULT_WRITE_SCOPE,
        reference_snapshot_id: str = SOURCE_SNAPSHOT_ID,
        reference_import_scope: str = IMPORT_SCOPE,
    ) -> None:
        if not snapshot_id or not import_scope:
            raise ValueError("snapshot_id and import_scope are required")
        if not reference_snapshot_id or not reference_import_scope:
            raise ValueError("reference snapshot and scope are required")
        self.manager = manager
        self.snapshot_id = snapshot_id
        self.import_scope = import_scope
        self.reference_snapshot_id = reference_snapshot_id
        self.reference_import_scope = reference_import_scope

    @property
    def _write_metadata(self) -> dict[str, str]:
        return {
            "snapshot_id": self.snapshot_id,
            "import_scope": self.import_scope,
            "data_version": WRITE_DATA_VERSION,
            "source_system": "neo4j-write-repository",
        }

    @property
    def _reference_metadata(self) -> dict[str, str]:
        return {
            "reference_snapshot_id": self.reference_snapshot_id,
            "reference_import_scope": self.reference_import_scope,
        }

    def _transaction(self, work):
        try:
            return self.manager.execute_write_transaction(work)
        except Neo4jWriteError:
            raise
        except Exception as exc:
            raise Neo4jWriteError("Neo4j write transaction rolled back") from exc

    @staticmethod
    def _require_references(
        transaction: Any,
        *,
        label: str,
        key: str,
        values: list[str],
        reference_snapshot_id: str,
        reference_import_scope: str,
    ) -> None:
        if not values:
            return
        if label not in {"Location", "Route", "Shipment"}:
            raise Neo4jWriteValidationError("Unsupported reference label")
        query = f"""
            MATCH (n:{label})
            WHERE n.{key} IN $values
              AND n.snapshot_id = $reference_snapshot_id
              AND n.import_scope = $reference_import_scope
            RETURN collect(n.{key}) AS ids
        """
        rows = _rows(
            transaction,
            query,
            {
                "values": sorted(set(values)),
                "reference_snapshot_id": reference_snapshot_id,
                "reference_import_scope": reference_import_scope,
            },
        )
        found = set(rows[0].get("ids", [])) if rows else set()
        missing = sorted(set(values) - found)
        if missing:
            raise Neo4jWriteValidationError(
                f"Missing {label} references: {', '.join(missing)}"
            )

    def create_disruption(
        self,
        disruption: Disruption,
        simulation_result: dict[str, Any],
    ) -> WriteReceipt:
        """Atomically create one disruption, targets, and its simulation run."""

        request = disruption.request
        result_json = _canonical_json(simulation_result)
        location_ids = sorted(set(request.affected_location_ids))
        route_ids = sorted(set(request.affected_route_ids))
        created_at = _utc(disruption.created_at)
        end_time = created_at + timedelta(hours=request.duration_hours)
        idempotency_key = _key({
            "disruption_id": disruption.id,
            "request": request.model_dump(mode="json"),
            "simulation_result": json.loads(result_json),
        })
        properties = {
            **self._write_metadata,
            "disruption_id": disruption.id,
            "event_type": request.disruption_type.value,
            "severity": request.severity,
            "start_time": created_at,
            "end_time": end_time,
            "duration_hours": request.duration_hours,
            "description": request.description,
            "created_at": created_at,
            "is_simulated": True,
            "create_idempotency_key": idempotency_key,
        }
        run_properties = {
            **self._write_metadata,
            "simulation_run_id": disruption.id,
            "disruption_id": disruption.id,
            "simulation_result_json": result_json,
            "reroute_result_json": None,
            "metrics_json": None,
            "updated_at": created_at,
            "write_version": 0,
            "last_reroute_idempotency_key": None,
        }

        def work(transaction: Any) -> WriteReceipt:
            self._require_references(
                transaction,
                label="Location",
                key="location_id",
                values=location_ids,
                **self._reference_metadata,
            )
            self._require_references(
                transaction,
                label="Route",
                key="route_id",
                values=route_ids,
                **self._reference_metadata,
            )
            existing = _rows(
                transaction,
                """
                MATCH (d:Disruption {disruption_id: $disruption_id})
                RETURN d{.*} AS properties
                """,
                {"disruption_id": disruption.id},
            )
            if existing:
                current = existing[0]["properties"]
                if (
                    current.get("snapshot_id") == self.snapshot_id
                    and current.get("import_scope") == self.import_scope
                    and current.get("create_idempotency_key") == idempotency_key
                ):
                    return WriteReceipt(
                        entity_id=disruption.id,
                        action="IDEMPOTENT",
                        write_version=0,
                        idempotency_key=idempotency_key,
                    )
                raise Neo4jWriteConflictError(
                    f"Disruption {disruption.id} already exists with different state"
                )

            _rows(
                transaction,
                "CREATE (d:Disruption) SET d = $properties RETURN d.disruption_id AS id",
                {"properties": properties},
            )
            if location_ids:
                _rows(
                    transaction,
                    """
                    MATCH (d:Disruption {disruption_id: $disruption_id})
                    UNWIND $target_ids AS target_id
                    MATCH (location:Location {location_id: target_id})
                    WHERE location.snapshot_id = $reference_snapshot_id
                      AND location.import_scope = $reference_import_scope
                    MERGE (d)-[:TARGETS_LOCATION {
                        target_id: target_id,
                        snapshot_id: $snapshot_id,
                        import_scope: $import_scope,
                        data_version: $data_version
                    }]->(location)
                    """,
                    {
                        "disruption_id": disruption.id,
                        "target_ids": location_ids,
                        **self._write_metadata,
                        **self._reference_metadata,
                    },
                )
            if route_ids:
                _rows(
                    transaction,
                    """
                    MATCH (d:Disruption {disruption_id: $disruption_id})
                    UNWIND $target_ids AS target_id
                    MATCH (route:Route {route_id: target_id})
                    WHERE route.snapshot_id = $reference_snapshot_id
                      AND route.import_scope = $reference_import_scope
                    MERGE (d)-[:TARGETS_ROUTE {
                        target_id: target_id,
                        snapshot_id: $snapshot_id,
                        import_scope: $import_scope,
                        data_version: $data_version
                    }]->(route)
                    """,
                    {
                        "disruption_id": disruption.id,
                        "target_ids": route_ids,
                        **self._write_metadata,
                        **self._reference_metadata,
                    },
                )
            _rows(
                transaction,
                """
                CREATE (run:SimulationRun)
                SET run = $properties
                WITH run
                MATCH (d:Disruption {disruption_id: $disruption_id})
                MERGE (d)-[:HAS_SIMULATION {
                    snapshot_id: $snapshot_id,
                    import_scope: $import_scope,
                    data_version: $data_version
                }]->(run)
                RETURN run.simulation_run_id AS id
                """,
                {"properties": run_properties, "disruption_id": disruption.id, **self._write_metadata},
            )
            return WriteReceipt(
                entity_id=disruption.id,
                action="CREATED",
                write_version=0,
                idempotency_key=idempotency_key,
            )

        return self._transaction(work)

    @staticmethod
    def _validate_recommendations(reroute_result: dict[str, Any]) -> list[dict[str, Any]]:
        encoded = _canonical_json(reroute_result)
        recommendations = reroute_result.get("recommendations")
        if not isinstance(recommendations, list):
            raise Neo4jWriteValidationError("reroute_result.recommendations must be a list")
        normalized = []
        shipment_ids = set()
        for recommendation in recommendations:
            if not isinstance(recommendation, dict):
                raise Neo4jWriteValidationError("Each recommendation must be an object")
            shipment_id = recommendation.get("shipment_id")
            status = str(recommendation.get("status", ""))
            if not isinstance(shipment_id, str) or not shipment_id:
                raise Neo4jWriteValidationError("Recommendation shipment_id is required")
            if shipment_id in shipment_ids:
                raise Neo4jWriteValidationError(f"Duplicate recommendation for {shipment_id}")
            if status not in ALLOWED_DECISION_STATUSES:
                raise Neo4jWriteValidationError(f"Unsupported decision status {status!r}")
            shipment_ids.add(shipment_id)
            normalized.append(recommendation)
        if len(encoded.encode("utf-8")) > MAX_JSON_BYTES:
            raise Neo4jWriteValidationError("reroute_result exceeds the JSON size limit")
        return normalized

    @staticmethod
    def _recommendation_route_ids(
        recommendations: list[dict[str, Any]],
    ) -> list[str]:
        route_ids: list[str] = []
        for recommendation in recommendations:
            route_values = [
                recommendation.get("original_route"),
                recommendation.get("selected_route"),
            ]
            candidates = recommendation.get("candidate_routes") or []
            if not isinstance(candidates, list):
                raise Neo4jWriteValidationError(
                    "Recommendation candidate_routes must be a list"
                )
            route_values.extend(candidates)
            for route_value in route_values:
                if route_value is None:
                    continue
                if not isinstance(route_value, dict):
                    raise Neo4jWriteValidationError(
                        "Route payloads must be objects or null"
                    )
                values = route_value.get("route_ids", [])
                if not isinstance(values, list) or not all(
                    isinstance(route_id, str) and route_id for route_id in values
                ):
                    raise Neo4jWriteValidationError(
                        "Route payload route_ids must be a list of non-empty strings"
                    )
                route_ids.extend(values)
        return sorted(set(route_ids))

    def save_reroute_decisions(
        self,
        disruption_id: str,
        reroute_result: dict[str, Any],
        *,
        expected_write_version: int = 0,
    ) -> WriteReceipt:
        """Atomically reconcile decisions and update one simulation run."""

        recommendations = self._validate_recommendations(reroute_result)
        result_json = _canonical_json(reroute_result)
        idempotency_key = _key(reroute_result)
        shipment_ids = sorted({item["shipment_id"] for item in recommendations})
        route_ids = self._recommendation_route_ids(recommendations)
        now = datetime.now(timezone.utc)

        def work(transaction: Any) -> WriteReceipt:
            run_rows = _rows(
                transaction,
                """
                MATCH (run:SimulationRun {simulation_run_id: $disruption_id})
                WHERE run.snapshot_id = $snapshot_id
                  AND run.import_scope = $import_scope
                RETURN run{.*} AS properties
                """,
                {"disruption_id": disruption_id, **self._write_metadata},
            )
            if not run_rows:
                raise Neo4jWriteNotFoundError(
                    f"Simulation run {disruption_id} does not exist in the write scope"
                )
            run = run_rows[0]["properties"]
            current_version = int(run.get("write_version", 0))
            if run.get("last_reroute_idempotency_key") == idempotency_key:
                return WriteReceipt(
                    entity_id=disruption_id,
                    action="IDEMPOTENT",
                    write_version=current_version,
                    idempotency_key=idempotency_key,
                )
            if current_version != expected_write_version:
                raise Neo4jWriteConflictError(
                    f"Stale simulation write version {expected_write_version}; current is {current_version}"
                )
            self._require_references(
                transaction,
                label="Shipment",
                key="shipment_id",
                values=shipment_ids,
                **self._reference_metadata,
            )
            self._require_references(
                transaction,
                label="Route",
                key="route_id",
                values=route_ids,
                **self._reference_metadata,
            )
            decision_ids = [f"{disruption_id}:{shipment_id}" for shipment_id in shipment_ids]
            existing_decisions = _rows(
                transaction,
                """
                MATCH (decision:AgentDecision)
                WHERE decision.decision_id IN $decision_ids
                RETURN decision{.*} AS properties
                """,
                {"decision_ids": decision_ids},
            ) if decision_ids else []
            for row in existing_decisions:
                properties = row["properties"]
                if (
                    properties.get("snapshot_id") != self.snapshot_id
                    or properties.get("import_scope") != self.import_scope
                ):
                    raise Neo4jWriteConflictError(
                        "A decision ID exists outside this explicit write scope"
                    )
            _rows(
                transaction,
                """
                MATCH (decision:AgentDecision)
                WHERE decision.disruption_id = $disruption_id
                  AND decision.snapshot_id = $snapshot_id
                  AND decision.import_scope = $import_scope
                  AND NOT decision.decision_id IN $decision_ids
                DETACH DELETE decision
                """,
                {
                    "disruption_id": disruption_id,
                    "decision_ids": decision_ids,
                    **self._write_metadata,
                },
            )
            for recommendation in recommendations:
                shipment_id = recommendation["shipment_id"]
                selected = recommendation.get("selected_route")
                decision_id = f"{disruption_id}:{shipment_id}"
                decision_properties = {
                    **self._write_metadata,
                    "decision_id": decision_id,
                    "disruption_id": disruption_id,
                    "shipment_id": shipment_id,
                    "status": recommendation["status"],
                    "original_route_json": _canonical_json(recommendation.get("original_route")),
                    "alternative_route_json": _canonical_json(selected),
                    "estimated_delay_saved": recommendation.get("delay_saved_hours", 0),
                    "additional_cost": recommendation.get("additional_cost", 0),
                    "risk_score": selected.get("risk_score") if isinstance(selected, dict) else None,
                    "route_score": selected.get("route_score") if isinstance(selected, dict) else None,
                    "reason": (
                        "Selected the highest-ranked capacity-feasible route."
                        if selected
                        else "No capacity-feasible alternative route was available."
                    ),
                    "confidence_score": None,
                    "llm_explanation_json": None,
                    "decision_payload_json": _canonical_json(recommendation),
                    "created_at": now,
                    "write_version": 0,
                    "explanation_idempotency_key": None,
                }
                _rows(
                    transaction,
                    """
                    MERGE (decision:AgentDecision {decision_id: $decision_id})
                    ON CREATE SET decision = $properties
                    ON MATCH SET decision = $properties
                    WITH decision
                    MATCH (run:SimulationRun {simulation_run_id: $disruption_id})
                    MERGE (run)-[:HAS_DECISION {
                        snapshot_id: $snapshot_id,
                        import_scope: $import_scope,
                        data_version: $data_version
                    }]->(decision)
                    RETURN decision.decision_id AS id
                    """,
                    {
                        "decision_id": decision_id,
                        "disruption_id": disruption_id,
                        "properties": decision_properties,
                        **self._write_metadata,
                    },
                )
            new_version = current_version + 1
            update_rows = _rows(
                transaction,
                """
                MATCH (run:SimulationRun {simulation_run_id: $disruption_id})
                WHERE run.snapshot_id = $snapshot_id
                  AND run.import_scope = $import_scope
                  AND run.write_version = $expected_write_version
                SET run.reroute_result_json = $result_json,
                    run.metrics_json = $metrics_json,
                    run.updated_at = $updated_at,
                    run.write_version = $new_version,
                    run.last_reroute_idempotency_key = $idempotency_key
                RETURN run.write_version AS write_version
                """,
                {
                    "disruption_id": disruption_id,
                    "expected_write_version": expected_write_version,
                    "new_version": new_version,
                    "result_json": result_json,
                    "metrics_json": _canonical_json(reroute_result.get("metrics")),
                    "updated_at": now,
                    "idempotency_key": idempotency_key,
                    **self._write_metadata,
                },
            )
            if not update_rows:
                raise Neo4jWriteConflictError(
                    "Simulation write version changed before commit"
                )
            return WriteReceipt(
                entity_id=disruption_id,
                action="UPDATED",
                write_version=new_version,
                idempotency_key=idempotency_key,
            )

        return self._transaction(work)

    def save_decision_explanation(
        self,
        disruption_id: str,
        shipment_id: str,
        explanation: dict[str, Any],
        *,
        expected_write_version: int = 0,
    ) -> WriteReceipt:
        """Atomically update one decision explanation with optimistic locking."""

        explanation_json = _canonical_json(explanation)
        idempotency_key = _key(explanation)

        def work(transaction: Any) -> WriteReceipt:
            rows = _rows(
                transaction,
                """
                MATCH (decision:AgentDecision {
                    decision_id: $decision_id
                })
                WHERE decision.snapshot_id = $snapshot_id
                  AND decision.import_scope = $import_scope
                RETURN decision{.*} AS properties
                """,
                {
                    "decision_id": f"{disruption_id}:{shipment_id}",
                    **self._write_metadata,
                },
            )
            if not rows:
                raise Neo4jWriteNotFoundError(
                    f"Agent decision {disruption_id}:{shipment_id} does not exist"
                )
            decision = rows[0]["properties"]
            current_version = int(decision.get("write_version", 0))
            if decision.get("explanation_idempotency_key") == idempotency_key:
                return WriteReceipt(
                    entity_id=f"{disruption_id}:{shipment_id}",
                    action="IDEMPOTENT",
                    write_version=current_version,
                    idempotency_key=idempotency_key,
                )
            if current_version != expected_write_version:
                raise Neo4jWriteConflictError(
                    f"Stale decision write version {expected_write_version}; current is {current_version}"
                )
            new_version = current_version + 1
            update_rows = _rows(
                transaction,
                """
                MATCH (decision:AgentDecision {decision_id: $decision_id})
                WHERE decision.snapshot_id = $snapshot_id
                  AND decision.import_scope = $import_scope
                  AND decision.write_version = $expected_write_version
                SET decision.llm_explanation_json = $explanation_json,
                    decision.explanation_idempotency_key = $idempotency_key,
                    decision.write_version = $new_version
                RETURN decision.decision_id AS id
                """,
                {
                    "decision_id": f"{disruption_id}:{shipment_id}",
                    "expected_write_version": expected_write_version,
                    "new_version": new_version,
                    "explanation_json": explanation_json,
                    "idempotency_key": idempotency_key,
                    **self._write_metadata,
                },
            )
            if not update_rows:
                raise Neo4jWriteConflictError(
                    "Decision write version changed before commit"
                )
            return WriteReceipt(
                entity_id=f"{disruption_id}:{shipment_id}",
                action="UPDATED",
                write_version=new_version,
                idempotency_key=idempotency_key,
            )

        return self._transaction(work)

    def reject_canonical_progress_write(self, operation: str) -> None:
        """Make the unsupported Phase 5 canonical-state boundary explicit."""

        raise Neo4jUnsupportedWriteError(
            f"{operation} is unsupported: SQLite has no operational write path "
            "for canonical shipment progress or route-plan version mutation in Phase 5"
        )

    def get_write_state(self, disruption_id: str) -> dict[str, Any]:
        """Read back only the owned test/write scope for verification."""

        rows = self.manager.execute_read(
            """
            MATCH (run:SimulationRun {simulation_run_id: $disruption_id})
            WHERE run.snapshot_id = $snapshot_id
              AND run.import_scope = $import_scope
            OPTIONAL MATCH (run)-[:HAS_DECISION]->(decision:AgentDecision)
            WHERE decision.snapshot_id = $snapshot_id
              AND decision.import_scope = $import_scope
            RETURN run{.*} AS run,
                   collect(decision{.*}) AS decisions
            """,
            {"disruption_id": disruption_id, **self._write_metadata},
        )
        if not rows:
            raise Neo4jWriteNotFoundError(f"Simulation run {disruption_id} was not found")
        return rows[0]

    def cleanup_owned_scope(self) -> int:
        """Delete only records created in this repository's explicit write scope."""

        rows = self.manager.execute_write(
            """
            MATCH (node)
            WHERE node.snapshot_id = $snapshot_id
              AND node.import_scope = $import_scope
            WITH collect(node) AS owned, count(node) AS count
            FOREACH (item IN owned | DETACH DELETE item)
            RETURN count
            """,
            self._write_metadata,
        )
        return int(rows[0]["count"]) if rows else 0
