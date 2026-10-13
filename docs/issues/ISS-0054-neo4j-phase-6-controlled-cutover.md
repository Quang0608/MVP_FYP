# ISS-0054 Neo4j Phase 6 controlled runtime cutover

Status: COMPLETE

## Goal

Add an explicit, preflight-gated persistence selector that can run the existing
runtime against SQLite or the verified Neo4j snapshot and supported write
repository, while preserving SQLite as the default and keeping API,
NetworkX/routing, frontend, and Supervisor/LLM contracts unchanged.

## Scope

- audit runtime reads/writes and document SQLite-only, Neo4j-backed, and
  transient/external operations;
- add Neo4j runtime settings for the imported snapshot and namespaced write
  scope;
- add startup preflight for connectivity, schema, exact canonical counts, and
  relationship integrity;
- route canonical dataset reads, simulation/history/decision persistence, and
  explanation persistence through the selected backend with no fallback;
- run isolated fixed-scenario SQLite/Neo4j end-to-end comparisons, API-shaped
  result comparisons, replay/error checks, and a rollback drill;
- publish a machine-readable cutover report and runbook.

## Out of scope

Canonical shipment progress or route-plan/leg mutations without an existing
SQLite write path, NetworkX algorithm changes, API contract changes, frontend
changes, Supervisor/LLM authority changes, dual writes, automatic failover,
and Phase 7 work.

## Acceptance criteria

- SQLite remains the default and Neo4j selection is explicit and preflight-gated;
- Neo4j selection fails clearly when unavailable or incomplete and never falls
  back to SQLite;
- supported runtime reads/writes use one selected backend and preserve existing
  deterministic output/API shapes;
- fixed scenarios and isolated persistence states match after documented
  volatile/transient normalization;
- cutover, rollback, outage, cleanup, and archive limitations are documented.

## Verification plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_neo4j_runtime.py -q
.\.venv\Scripts\python.exe scripts/migration/verify_neo4j_cutover.py --source-sqlite reroute_agent.db --report-out docs/migration/phase6/CUTOVER_REPORT.json
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard scripts
git diff --check
```

User approval: 2026-10-13T19:26:21+08:00.

## Completion evidence

- Runtime audit covered canonical reads, simulation, impact/reroute execution,
  history, decisions, explanations, assistant reconstruction, and dashboard
  endpoints. NetworkX, PortWatch, weather, and LLM operations remain
  transient/external; canonical progress/plan/leg mutations remain unsupported.
- Added explicit `PERSISTENCE_BACKEND` dispatch with SQLite default, Neo4j
  snapshot/write-scope settings, startup preflight, and no-fallback behavior.
- Live command passed the fixed `singapore_closure` scenario against an
  isolated SQLite copy and unique Neo4j scope. All 7 parity checks passed for
  impacts, classifications, candidate routes/scores/rankings, persisted
  history/replay, explanations, baseline IDs, and API-shaped response keys.
- Neo4j preflight passed connectivity, schema state, 91/150/220/220/1,000
  counts, and 3,960 relationships. The unavailable-endpoint test failed closed
  without SQLite fallback. Cleanup removed 31 test nodes.
- Focused migration tests passed (`31`), full backend tests passed (`138` with
  3 existing deprecation warnings), compilation passed, and `git diff --check`
  passed with line-ending normalization warnings only.
- Rollback is documented as an explicit operator process requiring quiescence,
  Neo4j write export/backup, SQLite selection, and reconciliation/replay after
  any accepted Neo4j writes. No automatic failover, commit, or push occurred.
