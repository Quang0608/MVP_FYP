# ISS-0053 Neo4j Phase 5 write repository

Status: COMPLETE

## Goal

Implement the approved Phase 5 Neo4j write boundary for the SQLite-backed
simulation state that already has application write paths, with explicit
transactions, stable idempotency, rollback, and optimistic version checks.

## Scope

- audit the actual SQLite writes for disruptions, targets, simulation runs,
  reroute decisions, and decision explanations;
- add an explicitly invoked Neo4j write repository for those supported records;
- keep JSON snapshots bounded and serialized as Neo4j-compatible properties;
- validate canonical Location, Route, and Shipment references against the
  imported Phase 2 snapshot;
- verify successful writes, rollback, retries, invalid references/statuses,
  stale versions, and isolated cleanup against a unique live test scope;
- document that canonical shipment progress, route-plan versions, and legs have
  no operational SQLite mutation path in this MVP and remain unsupported here.

## Out of scope

Runtime database cutover, dual writes, canonical shipment/route-plan/leg
mutation, NetworkX/routing changes, API/frontend contracts, Supervisor/LLM
behavior, data import, and Phase 6 work.

## Acceptance criteria

- supported writes are atomic, parameterized, snapshot-scoped, and auditable;
- repeat operations are idempotent and conflicting/stale writes are rejected;
- invalid references and invalid decision states fail without partial records;
- isolated live verification proves rollback, read-back, historical snapshot
  preservation, and stale-version/concurrency protection;
- SQLite remains the default runtime source of truth and existing backend
  behavior remains unchanged.

## Verification plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_neo4j_write.py -q
.\.venv\Scripts\python.exe scripts/migration/verify_neo4j_writes.py --source-sqlite reroute_agent.db --report-out docs/migration/phase5/WRITE_REPORT.json
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard scripts
git diff --check
```

User approval: 2026-10-13T19:17:07+08:00.

## Completion evidence

- Audited SQLite writes are `save_disruption`, `save_agent_decisions`, and
  `save_decision_explanation`; legacy `runs` migration is retained as an
  explicit SQLite-only compatibility path and is not imported.
- Added `backend/app/persistence/neo4j/write_repository.py` and exported its
  typed errors/receipt through the Neo4j package. Canonical shipment progress,
  route-plan version, and leg mutations are explicitly unsupported because
  the current SQLite MVP has no such operational write methods.
- Live command passed all 18 checks in
  `docs/migration/phase5/WRITE_REPORT.json`: supported writes/read-back,
  idempotent retries, stale-version conflicts, invalid statuses/references,
  missing simulation, intentional rollback, isolated SQLite-vs-Neo4j
  normalized write parity, historical snapshot preservation, and exact-scope
  cleanup.
- Live reference snapshot remained 91 locations, 150 routes, 220 shipments,
  220 version-1 plans, 1,000 legs, and 3,960 typed relationships. The test
  scope created one Disruption, one SimulationRun, one AgentDecision, and four
  typed relationships, then left zero owned nodes after cleanup.
- Focused Neo4j tests passed (`25`), full backend regression passed (`132` with
  3 existing deprecation warnings), compilation passed, and `git diff --check`
  passed with existing line-ending warnings only.
- SQLite remains the runtime writer; no API, routing, NetworkX, frontend,
  Supervisor/LLM, or Phase 6 changes were made. No commit or push was made.
