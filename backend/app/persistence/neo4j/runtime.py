"""Explicit Neo4j runtime adapter used only after a successful preflight."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from ...config import Settings, settings
from ...domain import RuntimeDataset
from ...schemas import Disruption, DisruptionRequest
from .driver import Neo4jConnectionManager, managed_neo4j_connection
from .importer import EXPECTED_COUNTS, EXPECTED_RELATIONSHIP_COUNTS
from .repository import Neo4jReadRepository
from .schema import CONSTRAINT_STATEMENTS, INDEX_STATEMENTS
from .write_repository import (
    Neo4jWriteNotFoundError,
    Neo4jWriteRepository,
    WriteReceipt,
)


class Neo4jRuntimePreflightError(RuntimeError):
    """Raised when Neo4j cannot safely become the explicitly selected backend."""


def _datetime(value: Any) -> datetime:
    if hasattr(value, "to_native"):
        value = value.to_native()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        return _datetime(parsed)
    raise Neo4jRuntimePreflightError(
        f"Unsupported Neo4j runtime timestamp: {type(value).__name__}"
    )


def _json_or_empty(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise Neo4jRuntimePreflightError("Invalid persisted Neo4j JSON state") from exc
    if not isinstance(decoded, dict):
        raise Neo4jRuntimePreflightError("Persisted Neo4j result must be an object")
    return decoded


class Neo4jRuntimeRepository:
    """Repository facade for the supported runtime operations only."""

    def __init__(self, configuration: Settings = settings) -> None:
        self.configuration = configuration
        self.read_snapshot_id = configuration.neo4j_snapshot_id
        self.read_import_scope = configuration.neo4j_import_scope
        self.write_snapshot_id = configuration.neo4j_write_snapshot_id
        self.write_import_scope = configuration.neo4j_write_import_scope

    @contextmanager
    def _connection(self) -> Iterator[Neo4jConnectionManager]:
        with managed_neo4j_connection(self.configuration) as manager:
            yield manager

    def _read_repository(self, manager: Neo4jConnectionManager) -> Neo4jReadRepository:
        return Neo4jReadRepository(
            manager,
            snapshot_id=self.read_snapshot_id,
            import_scope=self.read_import_scope,
        )

    def _write_repository(self, manager: Neo4jConnectionManager) -> Neo4jWriteRepository:
        return Neo4jWriteRepository(
            manager,
            snapshot_id=self.write_snapshot_id,
            import_scope=self.write_import_scope,
            reference_snapshot_id=self.read_snapshot_id,
            reference_import_scope=self.read_import_scope,
        )

    def preflight(self) -> dict[str, Any]:
        """Verify connectivity, schema, canonical data, and graph integrity."""

        try:
            with self._connection() as manager:
                constraint_rows = manager.execute_read(
                    "SHOW CONSTRAINTS YIELD name RETURN collect(name) AS names"
                )
                index_rows = manager.execute_read(
                    "SHOW INDEXES YIELD name, state RETURN collect({name: name, state: state}) AS indexes"
                )
                constraint_names = set(constraint_rows[0].get("names", [])) if constraint_rows else set()
                index_values = index_rows[0].get("indexes", []) if index_rows else []
                index_names = {item.get("name") for item in index_values}
                expected_constraints = {name for name, _ in CONSTRAINT_STATEMENTS}
                expected_indexes = {name for name, _ in INDEX_STATEMENTS}
                offline_indexes = sorted(
                    item.get("name")
                    for item in index_values
                    if item.get("state") not in {None, "ONLINE"}
                )
                if not expected_constraints <= constraint_names:
                    missing = sorted(expected_constraints - constraint_names)
                    raise Neo4jRuntimePreflightError(
                        f"Neo4j schema constraints are incomplete: {missing}"
                    )
                if not expected_indexes <= index_names or offline_indexes:
                    raise Neo4jRuntimePreflightError(
                        "Neo4j schema indexes are incomplete or not ONLINE"
                    )

                repository = self._read_repository(manager)
                dataset = repository.load_runtime_dataset()
                counts = {
                    "locations": len(dataset.locations),
                    "routes": len(dataset.routes),
                    "shipments": len(dataset.shipments),
                    "route_plans": len(repository.get_route_plans()),
                    "ordered_legs": len(repository.get_shipment_leg_records()),
                }
                if counts != EXPECTED_COUNTS:
                    raise Neo4jRuntimePreflightError(
                        f"Neo4j canonical counts do not match the approved snapshot: {counts}"
                    )
                relationships = repository.get_relationship_counts()
                if relationships != EXPECTED_RELATIONSHIP_COUNTS:
                    raise Neo4jRuntimePreflightError(
                        "Neo4j relationship counts do not match the approved snapshot"
                    )
        except Neo4jRuntimePreflightError:
            raise
        except Exception as exc:
            raise Neo4jRuntimePreflightError(
                "Neo4j runtime preflight failed; SQLite fallback is disabled"
            ) from exc
        return {
            "backend": "neo4j",
            "connectivity": "pass",
            "schema": "pass",
            "snapshot": {
                "snapshot_id": self.read_snapshot_id,
                "import_scope": self.read_import_scope,
                "counts": counts,
                "relationship_counts": relationships,
            },
            "write_scope": {
                "snapshot_id": self.write_snapshot_id,
                "import_scope": self.write_import_scope,
            },
        }

    def load_runtime_dataset(self) -> RuntimeDataset:
        with self._connection() as manager:
            return self._read_repository(manager).load_runtime_dataset()

    def save_disruption(
        self,
        disruption: Disruption,
        simulation_result: dict[str, Any],
    ) -> WriteReceipt:
        with self._connection() as manager:
            return self._write_repository(manager).create_disruption(
                disruption,
                simulation_result,
            )

    def save_agent_decisions(
        self,
        disruption_id: str,
        reroute_result: dict[str, Any],
    ) -> WriteReceipt:
        with self._connection() as manager:
            repository = self._write_repository(manager)
            state = repository.get_write_state(disruption_id)
            run = state.get("run") or {}
            expected_version = int(run.get("write_version", 0))
            return repository.save_reroute_decisions(
                disruption_id,
                reroute_result,
                expected_write_version=expected_version,
            )

    def save_decision_explanation(
        self,
        disruption_id: str,
        shipment_id: str,
        explanation: dict[str, Any],
    ) -> WriteReceipt:
        with self._connection() as manager:
            repository = self._write_repository(manager)
            state = repository.get_write_state(disruption_id)
            decision_id = f"{disruption_id}:{shipment_id}"
            decision = next(
                (
                    item
                    for item in state.get("decisions", [])
                    if item.get("decision_id") == decision_id
                ),
                None,
            )
            if decision is None:
                raise Neo4jWriteNotFoundError(
                    f"Agent decision {decision_id} does not exist"
                )
            return repository.save_decision_explanation(
                disruption_id,
                shipment_id,
                explanation,
                expected_write_version=int(decision.get("write_version", 0)),
            )

    def _stored_record(self, manager: Neo4jConnectionManager, run_id: str) -> dict[str, Any] | None:
        rows = manager.execute_read(
            """
            MATCH (disruption:Disruption {disruption_id: $run_id})
            WHERE disruption.snapshot_id = $write_snapshot_id
              AND disruption.import_scope = $write_import_scope
            OPTIONAL MATCH (disruption)-[:TARGETS_LOCATION]->(location:Location)
            WITH disruption, collect(DISTINCT location.location_id) AS location_ids
            OPTIONAL MATCH (disruption)-[:TARGETS_ROUTE]->(route:Route)
            WITH disruption, location_ids, collect(DISTINCT route.route_id) AS route_ids
            OPTIONAL MATCH (disruption)-[:HAS_SIMULATION]->(run:SimulationRun)
            OPTIONAL MATCH (run)-[:HAS_DECISION]->(decision:AgentDecision)
            RETURN disruption{.*} AS disruption,
                   location_ids,
                   route_ids,
                   run{.*} AS run,
                   collect(DISTINCT decision{.*}) AS decisions
            """,
            {
                "run_id": run_id,
                "write_snapshot_id": self.write_snapshot_id,
                "write_import_scope": self.write_import_scope,
            },
        )
        if not rows:
            return None
        row = rows[0]
        disruption_properties = row["disruption"]
        run_properties = row.get("run") or {}
        request = DisruptionRequest(
            disruption_type=disruption_properties["event_type"],
            affected_location_ids=sorted(row.get("location_ids") or []),
            affected_route_ids=sorted(row.get("route_ids") or []),
            duration_hours=int(disruption_properties["duration_hours"]),
            severity=disruption_properties["severity"],
            description=disruption_properties.get("description"),
        )
        stored_result = run_properties.get("reroute_result_json") or run_properties.get(
            "simulation_result_json"
        )
        return {
            "disruption": {
                "id": disruption_properties["disruption_id"],
                "request": request.model_dump(mode="json"),
                "created_at": _datetime(disruption_properties["created_at"]).isoformat(),
            },
            "results": _json_or_empty(stored_result),
            "_run": run_properties,
            "_decisions": row.get("decisions") or [],
        }

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connection() as manager:
            record = self._stored_record(manager, run_id)
        if record is None:
            return None
        record.pop("_run", None)
        record.pop("_decisions", None)
        return record

    def all_runs(self) -> list[dict[str, Any]]:
        with self._connection() as manager:
            rows = manager.execute_read(
                """
                MATCH (disruption:Disruption)
                WHERE disruption.snapshot_id = $write_snapshot_id
                  AND disruption.import_scope = $write_import_scope
                RETURN disruption.disruption_id AS disruption_id
                ORDER BY disruption.created_at, disruption.disruption_id
                """,
                {
                    "write_snapshot_id": self.write_snapshot_id,
                    "write_import_scope": self.write_import_scope,
                },
            )
            records = [
                self._stored_record(manager, row["disruption_id"])
                for row in rows
            ]
        output = []
        for record in records:
            if record is None:
                continue
            run = record.pop("_run", {})
            record.pop("_decisions", None)
            record["id"] = record["disruption"]["id"]
            record["created_at"] = _datetime(
                record["disruption"]["created_at"]
            )
            output.append(record)
        return output

    def get_decision_state(self, disruption_id: str, shipment_id: str) -> dict[str, Any] | None:
        with self._connection() as manager:
            repository = self._write_repository(manager)
            try:
                state = repository.get_write_state(disruption_id)
            except Neo4jWriteNotFoundError:
                return None
        decision_id = f"{disruption_id}:{shipment_id}"
        return next(
            (
                item
                for item in state.get("decisions", [])
                if item.get("decision_id") == decision_id
            ),
            None,
        )

    def cleanup_owned_scope(self) -> int:
        with self._connection() as manager:
            return self._write_repository(manager).cleanup_owned_scope()


def preflight_neo4j_runtime(configuration: Settings = settings) -> dict[str, Any]:
    return Neo4jRuntimeRepository(configuration).preflight()
