"""Verify the Phase 5 Neo4j write boundary in an isolated disposable scope."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import settings
from backend.app.persistence.neo4j.driver import managed_neo4j_connection
from backend.app.persistence.neo4j.importer import (
    IMPORT_SCOPE,
    SOURCE_SNAPSHOT_ID,
    load_source_dataset,
    validate_active_dataset,
)
from backend.app.persistence.neo4j.repository import Neo4jReadRepository
from backend.app.persistence.neo4j.write_repository import (
    Neo4jUnsupportedWriteError,
    Neo4jWriteConflictError,
    Neo4jWriteNotFoundError,
    Neo4jWriteRepository,
    Neo4jWriteValidationError,
)
from backend.app.schemas import Disruption, DisruptionRequest, DisruptionType


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sqlite", type=Path, required=True)
    parser.add_argument(
        "--report-out",
        type=Path,
        default=Path("docs/migration/phase5/WRITE_REPORT.json"),
    )
    return parser.parse_args()


def _counts(repository: Neo4jReadRepository) -> dict[str, int]:
    return {
        "locations": len(repository.get_locations()),
        "routes": len(repository.get_routes()),
        "shipments": len(repository.get_shipments()),
        "route_plans": len(repository.get_route_plans()),
        "ordered_legs": len(repository.get_shipment_leg_records()),
    }


def _state_summary(state: dict) -> dict:
    run = state.get("run") or {}
    decisions = state.get("decisions") or []
    return {
        "run_id": run.get("simulation_run_id"),
        "run_snapshot_id": run.get("snapshot_id"),
        "run_import_scope": run.get("import_scope"),
        "run_write_version": run.get("write_version"),
        "decision_ids": sorted(
            item.get("decision_id") for item in decisions if item.get("decision_id")
        ),
        "decision_count": len(decisions),
    }


def _owned_graph_counts(manager, metadata: dict[str, str]) -> dict[str, dict[str, int]]:
    node_rows = manager.execute_read(
        """
        MATCH (node)
        WHERE node.snapshot_id = $snapshot_id
          AND node.import_scope = $import_scope
        RETURN labels(node)[0] AS label, count(node) AS count
        ORDER BY label
        """,
        metadata,
    )
    relationship_rows = manager.execute_read(
        """
        MATCH ()-[relationship]->()
        WHERE relationship.snapshot_id = $snapshot_id
          AND relationship.import_scope = $import_scope
        RETURN type(relationship) AS type, count(relationship) AS count
        ORDER BY type
        """,
        metadata,
    )
    return {
        "nodes": {row["label"]: int(row["count"]) for row in node_rows},
        "relationships": {
            row["type"]: int(row["count"]) for row in relationship_rows
        },
    }


def _isolated_sqlite_write_summary(
    disruption: Disruption,
    reroute_result: dict,
    explanation: dict,
) -> dict:
    """Run the existing SQLite writes against a disposable in-memory database."""

    from backend.app import repository as sqlite_repository

    isolated_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sqlite_repository.Base.metadata.create_all(isolated_engine)
    isolated_session = sessionmaker(bind=isolated_engine, expire_on_commit=False)
    original_session = sqlite_repository.Session
    original_engine = sqlite_repository.engine
    sqlite_repository.Session = isolated_session
    sqlite_repository.engine = isolated_engine
    try:
        sqlite_repository.save_disruption(disruption, {"affected": [disruption.id]})
        sqlite_repository.save_agent_decisions(disruption.id, reroute_result)
        sqlite_repository.save_decision_explanation(
            disruption.id,
            reroute_result["recommendations"][0]["shipment_id"],
            explanation,
        )
        with isolated_session() as session:
            target_locations = session.scalars(
                select(sqlite_repository.DisruptionLocationRecord.location_id).where(
                    sqlite_repository.DisruptionLocationRecord.disruption_id == disruption.id
                )
            ).all()
            target_routes = session.scalars(
                select(sqlite_repository.DisruptionRouteRecord.route_id).where(
                    sqlite_repository.DisruptionRouteRecord.disruption_id == disruption.id
                )
            ).all()
            decisions = session.scalars(
                select(sqlite_repository.AgentDecisionRecord).where(
                    sqlite_repository.AgentDecisionRecord.disruption_id == disruption.id
                )
            ).all()
            run = session.get(sqlite_repository.SimulationRunRecord, disruption.id)
            return {
                "disruption_id": disruption.id,
                "target_location_ids": sorted(target_locations),
                "target_route_ids": sorted(target_routes),
                "simulation_run_id": run.disruption_id if run else None,
                "decision_ids": sorted(
                    f"{item.disruption_id}:{item.shipment_id}" for item in decisions
                ),
                "decision_statuses": sorted(item.status for item in decisions),
                "explanation": explanation,
            }
    finally:
        sqlite_repository.Session = original_session
        sqlite_repository.engine = original_engine
        isolated_engine.dispose()


def _neo4j_write_summary(manager, repository, disruption_id: str, metadata: dict) -> dict:
    target_rows = manager.execute_read(
        """
        MATCH (disruption:Disruption {disruption_id: $disruption_id})
        WHERE disruption.snapshot_id = $snapshot_id
          AND disruption.import_scope = $import_scope
        OPTIONAL MATCH (disruption)-[:TARGETS_LOCATION]->(location:Location)
        OPTIONAL MATCH (disruption)-[:TARGETS_ROUTE]->(route:Route)
        RETURN collect(DISTINCT location.location_id) AS location_ids,
               collect(DISTINCT route.route_id) AS route_ids
        """,
        {"disruption_id": disruption_id, **metadata},
    )
    state = repository.get_write_state(disruption_id)
    decisions = state.get("decisions") or []
    return {
        "disruption_id": disruption_id,
        "target_location_ids": sorted(target_rows[0]["location_ids"] if target_rows else []),
        "target_route_ids": sorted(target_rows[0]["route_ids"] if target_rows else []),
        "simulation_run_id": (state.get("run") or {}).get("simulation_run_id"),
        "decision_ids": sorted(item.get("decision_id") for item in decisions),
        "decision_statuses": sorted(item.get("status") for item in decisions),
        "explanation": json.loads(decisions[0]["llm_explanation_json"])
        if decisions and decisions[0].get("llm_explanation_json")
        else None,
    }


def _timed(operation: str, function, timings: list[dict]) -> object:
    started = time.perf_counter()
    result = function()
    timings.append(
        {
            "operation": operation,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    )
    return result


def _record_expected_error(
    results: dict,
    name: str,
    function,
    expected_type: type[Exception],
    timings: list[dict],
) -> None:
    try:
        _timed(name, function, timings)
    except expected_type as exc:
        results[name] = {"pass": True, "error_type": type(exc).__name__, "detail": str(exc)}
    except Exception as exc:  # pragma: no cover - live verification failure detail
        results[name] = {
            "pass": False,
            "error_type": type(exc).__name__,
            "detail": str(exc),
        }
    else:
        results[name] = {"pass": False, "detail": "Expected failure did not occur"}


def _rollback_probe(manager, metadata: dict[str, str], probe_id: str) -> bool:
    query = """
        CREATE (probe:Phase5RollbackProbe)
        SET probe = $properties
        RETURN probe.probe_id AS probe_id
    """

    def work(transaction):
        transaction.run(
            query,
            {
                "properties": {
                    **metadata,
                    "probe_id": probe_id,
                }
            },
        ).consume()
        raise RuntimeError("intentional Phase 5 rollback probe")

    try:
        manager.execute_write_transaction(work)
    except RuntimeError as exc:
        if str(exc) != "intentional Phase 5 rollback probe":
            raise
    rows = manager.execute_read(
        """
        MATCH (probe:Phase5RollbackProbe {probe_id: $probe_id})
        WHERE probe.snapshot_id = $snapshot_id
          AND probe.import_scope = $import_scope
        RETURN count(probe) AS count
        """,
        {"probe_id": probe_id, **metadata},
    )
    return int(rows[0]["count"]) == 0 if rows else True


def main() -> int:
    args = parse_args()
    dataset = load_source_dataset(args.source_sqlite)
    source_validation = validate_active_dataset(dataset)
    if not source_validation["pass"]:
        raise SystemExit("Source active dataset validation failed")

    sorted_shipments = sorted(dataset.shipments, key=lambda item: item.shipment_id)
    reference_shipment = sorted_shipments[0]
    test_token = uuid4().hex[:12]
    test_snapshot_id = f"phase5-write-test-{test_token}"
    test_scope = f"phase5-write-test-{test_token}"
    disruption_id = f"PHASE5-{test_token}"
    metadata = {
        "snapshot_id": test_snapshot_id,
        "import_scope": test_scope,
    }
    disruption = Disruption(
        id=disruption_id,
        request=DisruptionRequest(
            disruption_type=DisruptionType.PORT_CLOSURE,
            affected_location_ids=["LOC_WPI_50000"],
            affected_route_ids=["ASIA_R_0002"],
            duration_hours=72,
            severity="HIGH",
            description="Phase 5 isolated write verification",
        ),
        created_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
    )
    selected_route_id = reference_shipment.planned_route_ids[0]
    reroute_result = {
        "recommendations": [
            {
                "shipment_id": reference_shipment.shipment_id,
                "status": "REROUTED",
                "original_route": {"route_ids": reference_shipment.planned_route_ids[:2]},
                "selected_route": {
                    "route_ids": [selected_route_id],
                    "risk_score": 0.2,
                    "route_score": 1.0,
                },
                "delay_saved_hours": 1.5,
                "additional_cost": 3.0,
            }
        ],
        "metrics": {"phase5_verification": True},
    }
    changed_result = {
        **reroute_result,
        "recommendations": [
            {**reroute_result["recommendations"][0], "additional_cost": 4.0}
        ],
    }
    timings: list[dict] = []
    results: dict = {}
    report: dict = {
        "schema_version": "neo4j-phase-5/v1",
        "test_snapshot_id": test_snapshot_id,
        "test_import_scope": test_scope,
        "source_snapshot_id": SOURCE_SNAPSHOT_ID,
        "source_import_scope": IMPORT_SCOPE,
        "source_sqlite": str(args.source_sqlite),
        "source_counts": {
            "locations": len(dataset.locations),
            "routes": len(dataset.routes),
            "shipments": len(dataset.shipments),
            "ordered_legs": sum(len(item.route_legs) for item in dataset.shipments),
        },
        "audited_sqlite_writes": [
            "save_disruption: disruption, target associations, and simulation run",
            "save_agent_decisions: decision replacement and simulation run update",
            "save_decision_explanation: one decision explanation update",
        ],
        "unsupported_canonical_writes": [
            "shipment progress mutation",
            "route-plan version creation/update",
            "shipment-leg mutation",
        ],
        "results": results,
        "timings": timings,
    }

    manager = None
    repository = None
    connection_context = None
    try:
        connection_context = managed_neo4j_connection(settings)
        manager = connection_context.__enter__()
        if manager is not None:
            read_repository = Neo4jReadRepository(
                manager,
                snapshot_id=SOURCE_SNAPSHOT_ID,
                import_scope=IMPORT_SCOPE,
            )
            before_counts = _counts(read_repository)
            before_relationships = read_repository.get_relationship_counts()
            report["before_imported_snapshot"] = {
                "counts": before_counts,
                "relationship_counts": before_relationships,
            }

            repository = Neo4jWriteRepository(
                manager,
                snapshot_id=test_snapshot_id,
                import_scope=test_scope,
                reference_snapshot_id=SOURCE_SNAPSHOT_ID,
                reference_import_scope=IMPORT_SCOPE,
            )
            created = _timed(
                "create_disruption",
                lambda: repository.create_disruption(disruption, {"affected": [reference_shipment.shipment_id]}),
                timings,
            )
            results["create_disruption"] = {
                "pass": created.action == "CREATED",
                "action": created.action,
                "write_version": created.write_version,
            }
            repeated = _timed(
                "repeat_create_disruption",
                lambda: repository.create_disruption(disruption, {"affected": [reference_shipment.shipment_id]}),
                timings,
            )
            results["repeat_create_disruption"] = {
                "pass": repeated.action == "IDEMPOTENT",
                "action": repeated.action,
                "write_version": repeated.write_version,
            }

            updated = _timed(
                "save_reroute_decisions",
                lambda: repository.save_reroute_decisions(
                    disruption_id, reroute_result, expected_write_version=0
                ),
                timings,
            )
            results["save_reroute_decisions"] = {
                "pass": updated.action == "UPDATED" and updated.write_version == 1,
                "action": updated.action,
                "write_version": updated.write_version,
            }
            repeated_update = _timed(
                "repeat_save_reroute_decisions",
                lambda: repository.save_reroute_decisions(
                    disruption_id, reroute_result, expected_write_version=0
                ),
                timings,
            )
            results["repeat_save_reroute_decisions"] = {
                "pass": repeated_update.action == "IDEMPOTENT",
                "action": repeated_update.action,
                "write_version": repeated_update.write_version,
            }
            _record_expected_error(
                results,
                "stale_reroute_write",
                lambda: repository.save_reroute_decisions(
                    disruption_id, changed_result, expected_write_version=0
                ),
                Neo4jWriteConflictError,
                timings,
            )
            _record_expected_error(
                results,
                "invalid_decision_status",
                lambda: repository.save_reroute_decisions(
                    disruption_id,
                    {"recommendations": [{**reroute_result["recommendations"][0], "status": "INVALID"}]},
                ),
                Neo4jWriteValidationError,
                timings,
            )
            _record_expected_error(
                results,
                "missing_shipment_reference",
                lambda: repository.save_reroute_decisions(
                    disruption_id,
                    {"recommendations": [{**reroute_result["recommendations"][0], "shipment_id": "MISSING-SHIPMENT"}]},
                    expected_write_version=1,
                ),
                Neo4jWriteValidationError,
                timings,
            )
            missing_route_result = {
                **reroute_result,
                "recommendations": [
                    {
                        **reroute_result["recommendations"][0],
                        "selected_route": {"route_ids": ["MISSING-ROUTE"]},
                    }
                ],
            }
            _record_expected_error(
                results,
                "missing_route_reference",
                lambda: repository.save_reroute_decisions(
                    disruption_id,
                    missing_route_result,
                    expected_write_version=1,
                ),
                Neo4jWriteValidationError,
                timings,
            )

            explanation = {"summary": "Phase 5 explanation", "evidence": [disruption_id]}
            explanation_receipt = _timed(
                "save_decision_explanation",
                lambda: repository.save_decision_explanation(
                    disruption_id,
                    reference_shipment.shipment_id,
                    explanation,
                    expected_write_version=0,
                ),
                timings,
            )
            results["save_decision_explanation"] = {
                "pass": explanation_receipt.action == "UPDATED"
                and explanation_receipt.write_version == 1,
                "action": explanation_receipt.action,
                "write_version": explanation_receipt.write_version,
            }
            explanation_repeat = _timed(
                "repeat_save_decision_explanation",
                lambda: repository.save_decision_explanation(
                    disruption_id,
                    reference_shipment.shipment_id,
                    explanation,
                    expected_write_version=0,
                ),
                timings,
            )
            results["repeat_save_decision_explanation"] = {
                "pass": explanation_repeat.action == "IDEMPOTENT",
                "action": explanation_repeat.action,
                "write_version": explanation_repeat.write_version,
            }
            _record_expected_error(
                results,
                "stale_explanation_write",
                lambda: repository.save_decision_explanation(
                    disruption_id,
                    reference_shipment.shipment_id,
                    {"summary": "changed"},
                    expected_write_version=0,
                ),
                Neo4jWriteConflictError,
                timings,
            )
            _record_expected_error(
                results,
                "missing_simulation_reference",
                lambda: repository.save_reroute_decisions(
                    f"MISSING-{test_token}", reroute_result
                ),
                Neo4jWriteNotFoundError,
                timings,
            )
            _record_expected_error(
                results,
                "unsupported_canonical_progress_write",
                lambda: repository.reject_canonical_progress_write("update_progress"),
                Neo4jUnsupportedWriteError,
                timings,
            )

            rollback_probe_id = f"rollback-{test_token}"
            rollback_passed = _timed(
                "failed_transaction_rollback",
                lambda: _rollback_probe(manager, metadata, rollback_probe_id),
                timings,
            )
            results["failed_transaction_rollback"] = {"pass": rollback_passed}

            state = repository.get_write_state(disruption_id)
            report["write_state_after_operations"] = _state_summary(state)
            report["write_graph_counts"] = _owned_graph_counts(manager, metadata)
            sqlite_summary = _isolated_sqlite_write_summary(
                disruption,
                reroute_result,
                explanation,
            )
            neo4j_summary = _neo4j_write_summary(
                manager,
                repository,
                disruption_id,
                metadata,
            )
            report["isolated_sqlite_write_parity"] = {
                "sqlite": sqlite_summary,
                "neo4j": neo4j_summary,
                "matched": sqlite_summary == neo4j_summary,
                "normalization": "Stable IDs/statuses are sorted; explanation is compared as parsed JSON. Volatile timestamps, SQLite row identity, Neo4j internal IDs, and write-version metadata are excluded.",
            }
            results["isolated_sqlite_write_parity"] = {
                "pass": sqlite_summary == neo4j_summary,
            }
            results["read_back_and_progress_consistency"] = {
                "pass": (
                    state["run"].get("write_version") == 1
                    and len(state["decisions"]) == 1
                    and state["decisions"][0].get("write_version") == 1
                )
            }
            results["write_graph_shape"] = {
                "pass": report["write_graph_counts"]
                == {
                    "nodes": {"AgentDecision": 1, "Disruption": 1, "SimulationRun": 1},
                    "relationships": {
                        "HAS_DECISION": 1,
                        "HAS_SIMULATION": 1,
                        "TARGETS_LOCATION": 1,
                        "TARGETS_ROUTE": 1,
                    },
                }
            }

            after_write_counts = _counts(read_repository)
            after_write_relationships = read_repository.get_relationship_counts()
            report["after_write_imported_snapshot"] = {
                "counts": after_write_counts,
                "relationship_counts": after_write_relationships,
            }
            results["historical_plan_and_leg_preservation"] = {
                "pass": before_counts == after_write_counts
                and before_relationships == after_write_relationships,
                "route_plan_versions": sorted(
                    {plan.plan_version for plan in read_repository.get_route_plans()}
                ),
            }
    except Exception as exc:  # pragma: no cover - live environment failure detail
        report["fatal_error"] = {"type": type(exc).__name__, "detail": str(exc)}
    finally:
        if repository is not None and manager is not None:
            try:
                deleted = repository.cleanup_owned_scope()
                report["cleanup"] = {"deleted_owned_nodes": deleted}
                remaining = manager.execute_read(
                    """
                    MATCH (node)
                    WHERE node.snapshot_id = $snapshot_id
                      AND node.import_scope = $import_scope
                    RETURN count(node) AS count
                    """,
                    metadata,
                )
                report["cleanup"]["remaining_owned_nodes"] = (
                    int(remaining[0]["count"]) if remaining else 0
                )
            except Exception as exc:  # pragma: no cover - cleanup failure detail
                report["cleanup"] = {
                    "pass": False,
                    "error_type": type(exc).__name__,
                    "detail": str(exc),
                }
        if connection_context is not None:
            connection_context.__exit__(None, None, None)

    report["verification_summary"] = {
        "operation_count": len(results),
        "passed_operations": sum(item.get("pass", False) for item in results.values()),
    }
    report["pass"] = (
        "fatal_error" not in report
        and all(item.get("pass", False) for item in results.values())
        and report.get("cleanup", {}).get("remaining_owned_nodes") == 0
        and report.get("before_imported_snapshot") == report.get("after_write_imported_snapshot")
    )
    report["environment"] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "neo4j_database": settings.neo4j_database,
        "sqlite_runtime_backend": settings.persistence_backend,
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "report": str(args.report_out),
                "operations": len(results),
                "passed_operations": sum(item.get("pass", False) for item in results.values()),
                "cleanup_remaining_owned_nodes": report.get("cleanup", {}).get("remaining_owned_nodes"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
