"""Run isolated SQLite/Neo4j runtime parity and controlled cutover checks."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app import repository as sqlite_repository
from backend.app.config import Settings, settings
from backend.app.main import reroute_endpoint
from backend.app.persistence.neo4j.runtime import (
    Neo4jRuntimePreflightError,
    Neo4jRuntimeRepository,
)
from backend.app.repository import AgentDecisionRecord
from backend.app.schemas import DisruptionRequest, DisruptionType
from backend.app.simulation_service import run_simulation


BASELINE_PATH = PROJECT_ROOT / "docs/migration/baseline/SCENARIOS.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sqlite", type=Path, required=True)
    parser.add_argument(
        "--report-out",
        type=Path,
        default=Path("docs/migration/phase6/CUTOVER_REPORT.json"),
    )
    return parser.parse_args()


def _normalize(value, replacement_id: str):
    if isinstance(value, dict):
        return {
            key: _normalize(item, replacement_id)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_normalize(item, replacement_id) for item in value]
    if isinstance(value, str):
        if value == replacement_id:
            return "<DISRUPTION_ID>"
        if replacement_id in value:
            return value.replace(replacement_id, "<DISRUPTION_ID>")
        if "T" in value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
            else:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc).isoformat()
    return value


def _impact_summary(result: dict) -> list[dict]:
    impacts = result.get("shipment_impacts") or []
    return sorted(
        [
            {
                "shipment_id": item["shipment_id"],
                "classification": item["classification"],
                "route_feasible": item["route_feasible"],
                "reason": item["reason"],
                "affected_location_ids": sorted(item["affected_location_ids"]),
                "affected_route_ids": sorted(item["affected_route_ids"]),
            }
            for item in impacts
        ],
        key=lambda item: item["shipment_id"],
    )


def _recommendation_summary(result: dict, disruption_id: str) -> list[dict]:
    recommendations = result.get("recommendations") or []
    return sorted(
        [_normalize(item, disruption_id) for item in recommendations],
        key=lambda item: item["shipment_id"],
    )


@contextmanager
def _isolated_sqlite(source_sqlite: Path):
    original_engine = sqlite_repository.engine
    original_session = sqlite_repository.Session
    original_backend = settings.persistence_backend
    with tempfile.TemporaryDirectory(prefix="phase6-sqlite-") as directory:
        database_path = Path(directory) / "runtime.db"
        shutil.copy2(source_sqlite, database_path)
        isolated_engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
        sqlite_repository.engine = isolated_engine
        sqlite_repository.Session = sessionmaker(
            bind=isolated_engine,
            expire_on_commit=False,
        )
        settings.persistence_backend = "sqlite"
        try:
            with sqlite_repository.Session() as session:
                for model in (
                    sqlite_repository.AgentDecisionRecord,
                    sqlite_repository.SimulationRunRecord,
                    sqlite_repository.DisruptionLocationRecord,
                    sqlite_repository.DisruptionRouteRecord,
                    sqlite_repository.DisruptionRecord,
                ):
                    session.query(model).delete()
                if inspect(isolated_engine).has_table("runs"):
                    session.query(sqlite_repository.LegacyRunRecord).delete()
                session.commit()
            yield
        finally:
            settings.persistence_backend = original_backend
            sqlite_repository.Session = original_session
            sqlite_repository.engine = original_engine
            isolated_engine.dispose()


def _sqlite_decision_summary(disruption_id: str, shipment_id: str) -> dict | None:
    with sqlite_repository.Session() as session:
        decision = session.scalar(
            select(AgentDecisionRecord).where(
                AgentDecisionRecord.disruption_id == disruption_id,
                AgentDecisionRecord.shipment_id == shipment_id,
            )
        )
        if decision is None:
            return None
        return {
            "decision_id": f"{decision.disruption_id}:{decision.shipment_id}",
            "status": decision.status,
            "explanation": json.loads(decision.llm_explanation)
            if decision.llm_explanation
            else None,
        }


def _run_selected_backend(
    backend: str,
    request: DisruptionRequest,
    disruption_id: str,
    created_at: datetime,
    runtime_repository: Neo4jRuntimeRepository | None = None,
) -> dict:
    settings.persistence_backend = backend
    execution = run_simulation(
        request,
        disruption_id=disruption_id,
        created_at=created_at,
    )
    reroute_result = reroute_endpoint(disruption_id)
    first_recommendation = (reroute_result.get("recommendations") or [None])[0]
    explanation = {
        "source": "phase6-deterministic-verification",
        "summary": "Backend parity explanation",
    }
    if first_recommendation is not None:
        sqlite_repository.save_decision_explanation(
            disruption_id,
            first_recommendation["shipment_id"],
            explanation,
        )
    stored = sqlite_repository.get_run(disruption_id)
    replay = reroute_endpoint(disruption_id)
    all_runs = sqlite_repository.all_runs()
    decision_summary = None
    if first_recommendation is not None and backend == "sqlite":
        decision_summary = _sqlite_decision_summary(
            disruption_id,
            first_recommendation["shipment_id"],
        )
    if first_recommendation is not None and backend == "neo4j":
        decision = runtime_repository.get_decision_state(
            disruption_id,
            first_recommendation["shipment_id"],
        )
        decision_summary = {
            "decision_id": decision.get("decision_id"),
            "status": decision.get("status"),
            "explanation": json.loads(decision["llm_explanation_json"]),
        }
    return {
        "simulation_result": execution.result.model_dump(mode="json"),
        "reroute_result": reroute_result,
        "replay_result": replay,
        "stored_run": stored,
        "decision": decision_summary,
        "history_count": len(all_runs),
        "response_contracts": {
            "simulation_keys": sorted(execution.result.model_dump(mode="json")),
            "reroute_keys": sorted(reroute_result),
        },
    }


def main() -> int:
    args = parse_args()
    frozen = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    frozen_scenario = frozen["singapore_closure"]
    request = DisruptionRequest(
        disruption_type=DisruptionType.PORT_CLOSURE,
        affected_location_ids=["LOC_WPI_50000"],
        duration_hours=72,
        severity="HIGH",
        description="Phase 6 fixed Singapore closure",
    )
    created_at = datetime.fromisoformat(frozen_scenario["fixed_clock"])
    token = uuid4().hex[:12]
    sqlite_id = f"PHASE6-SQLITE-{token}"
    neo4j_id = f"PHASE6-NEO4J-{token}"
    report = {
        "schema_version": "neo4j-phase-6/v1",
        "source_sqlite": str(args.source_sqlite),
        "fixed_scenario": "singapore_closure",
        "fixed_clock": created_at.isoformat(),
        "runtime_defaults": {
            "before": "sqlite",
            "sqlite_default_preserved": Settings(_env_file=None).persistence_backend == "sqlite",
        },
        "operation_coverage": {
            "canonical_reads": "selected backend",
            "disruption_simulation": "selected backend persistence + transient NetworkX analysis",
            "impact_detection": "transient NetworkX analysis over selected backend snapshot",
            "reroute_decisions": "selected backend persistence + transient NetworkX routing",
            "simulation_history": "selected backend for supported records; legacy SQLite archive excluded in Neo4j mode",
            "explanation_updates": "selected backend persistence; LLM remains explanation-only",
            "dashboard_api_contracts": "unchanged endpoint models and response keys",
            "canonical_progress_and_plan_mutations": "unsupported in both backends",
            "portwatch_weather": "external/transient adapters, not Neo4j canonical writes",
        },
        "results": {},
        "limitations": [
            "Neo4j mode exposes only records written after cutover in its configured write scope; legacy SQLite runs are not automatic failover data.",
            "Canonical shipment progress, route-plan version creation, and leg mutation remain unsupported because no existing SQLite operational write path exists.",
            "Scenario overlays and NetworkX working state are transient and are not persisted as canonical Neo4j route properties.",
            "LLM explanation generation is not called by this offline parity harness; a deterministic structured explanation is used to verify persistence and retrieval.",
        ],
    }
    original_backend = settings.persistence_backend
    original_write_snapshot = settings.neo4j_write_snapshot_id
    original_write_scope = settings.neo4j_write_import_scope
    neo4j_runtime = None
    try:
        with _isolated_sqlite(args.source_sqlite):
            sqlite_result = _run_selected_backend(
                "sqlite",
                request,
                sqlite_id,
                created_at,
            )

        settings.neo4j_write_snapshot_id = f"phase6-write-{token}"
        settings.neo4j_write_import_scope = f"phase6-write-{token}"
        settings.persistence_backend = "neo4j"
        neo4j_runtime = Neo4jRuntimeRepository(settings)
        report["neo4j_preflight"] = neo4j_runtime.preflight()
        neo4j_result = _run_selected_backend(
            "neo4j",
            request,
            neo4j_id,
            created_at,
            runtime_repository=neo4j_runtime,
        )
        report["results"]["sqlite"] = sqlite_result
        report["results"]["neo4j"] = neo4j_result

        sqlite_simulation = _normalize(sqlite_result["simulation_result"], sqlite_id)
        neo4j_simulation = _normalize(neo4j_result["simulation_result"], neo4j_id)
        sqlite_impacts = _impact_summary(sqlite_result["simulation_result"])
        neo4j_impacts = _impact_summary(neo4j_result["simulation_result"])
        sqlite_recommendations = _recommendation_summary(
            sqlite_result["reroute_result"], sqlite_id
        )
        neo4j_recommendations = _recommendation_summary(
            neo4j_result["reroute_result"], neo4j_id
        )
        sqlite_stored = _normalize(sqlite_result["stored_run"], sqlite_id)
        neo4j_stored = _normalize(neo4j_result["stored_run"], neo4j_id)
        sqlite_replay = _normalize(sqlite_result["replay_result"], sqlite_id)
        neo4j_replay = _normalize(neo4j_result["replay_result"], neo4j_id)
        scenario_expected = set(frozen_scenario["affected_shipment_ids"])
        scenario_actual = {
            item["shipment_id"]
            for item in sqlite_impacts
            if item["classification"] != "UNAFFECTED"
        }
        report["parity"] = {
            "simulation_results": {
                "match": sqlite_simulation == neo4j_simulation,
                "sqlite": sqlite_simulation,
                "neo4j": neo4j_simulation,
            },
            "impact_classifications": {
                "match": sqlite_impacts == neo4j_impacts,
                "sqlite": sqlite_impacts,
                "neo4j": neo4j_impacts,
            },
            "fixed_scenario_baseline": {
                "match": scenario_actual == scenario_expected,
                "expected_affected_ids": sorted(scenario_expected),
                "actual_affected_ids": sorted(scenario_actual),
            },
            "reroute_candidates_scores_rankings": {
                "match": sqlite_recommendations == neo4j_recommendations,
                "sqlite": sqlite_recommendations,
                "neo4j": neo4j_recommendations,
            },
            "persisted_runs_and_replay": {
                "match": sqlite_stored == neo4j_stored
                and sqlite_replay == neo4j_replay,
                "sqlite_history_count": sqlite_result["history_count"],
                "neo4j_history_count": neo4j_result["history_count"],
            },
            "explanation_update_and_retrieval": {
                "match": _normalize(sqlite_result["decision"], sqlite_id)
                == _normalize(neo4j_result["decision"], neo4j_id),
                "sqlite": _normalize(sqlite_result["decision"], sqlite_id),
                "neo4j": _normalize(neo4j_result["decision"], neo4j_id),
            },
            "api_response_contracts": {
                "match": sqlite_result["response_contracts"]
                == neo4j_result["response_contracts"],
                "sqlite": sqlite_result["response_contracts"],
                "neo4j": neo4j_result["response_contracts"],
            },
        }
        try:
            unavailable = Settings(
                _env_file=None,
                persistence_backend="neo4j",
                neo4j_uri="bolt://127.0.0.1:9",
                neo4j_password="test-password",
                neo4j_connection_timeout_seconds=0.2,
                neo4j_connection_acquisition_timeout_seconds=0.2,
                neo4j_max_transaction_retry_time_seconds=0.2,
            )
            Neo4jRuntimeRepository(unavailable).preflight()
            outage_pass = False
        except Neo4jRuntimePreflightError:
            outage_pass = True
        report["cutover_safety"] = {
            "explicit_neo4j_selection": True,
            "no_silent_sqlite_fallback": outage_pass,
            "rollback_to_sqlite_before_new_writes": True,
            "rollback_procedure": [
                "quiesce request writers",
                "export/backup Neo4j write-scope records and manifest",
                "switch PERSISTENCE_BACKEND back to sqlite",
                "resume only from a reconciled/replayed SQLite state",
            ],
            "reconciliation_required_after_neo4j_writes": True,
            "legacy_sqlite_history_automatic_failover": False,
        }
    except Exception as exc:  # pragma: no cover - live verification detail
        report["fatal_error"] = {"type": type(exc).__name__, "detail": str(exc)}
    finally:
        if neo4j_runtime is not None:
            try:
                report["cleanup"] = {
                    "deleted_owned_nodes": neo4j_runtime.cleanup_owned_scope()
                }
            except Exception as exc:  # pragma: no cover - cleanup detail
                report["cleanup"] = {
                    "error_type": type(exc).__name__,
                    "detail": str(exc),
                }
        settings.persistence_backend = original_backend
        settings.neo4j_write_snapshot_id = original_write_snapshot
        settings.neo4j_write_import_scope = original_write_scope

    parity = report.get("parity", {})
    report["pass"] = (
        "fatal_error" not in report
        and report.get("neo4j_preflight", {}).get("connectivity") == "pass"
        and report.get("neo4j_preflight", {}).get("schema") == "pass"
        and all(item.get("match", False) for item in parity.values())
        and report.get("cutover_safety", {}).get("no_silent_sqlite_fallback") is True
        and report.get("cleanup", {}).get("deleted_owned_nodes", 0) >= 3
    )
    report["environment"] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "neo4j_database": settings.neo4j_database,
        "runtime_backend_after_verification": settings.persistence_backend,
        "canonical_source": "isolated SQLite copy and Phase 2 Neo4j snapshot",
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
                "parity_checks": len(parity),
                "parity_passes": sum(item.get("match", False) for item in parity.values()),
                "cleanup": report.get("cleanup"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
