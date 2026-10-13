# ISS-0049 Neo4j Phase 1 foundation setup

## Status

`COMPLETE`

## Source

Direct request: execute only Phase 1 of the Neo4j migration execution plan.

## Context

Phase 0 froze the SQLite active snapshot and deterministic scenario outputs.
The repository has no Neo4j driver, Compose service, connection lifecycle, or
schema bootstrap. SQLite must remain the default operational backend while the
Neo4j foundation is introduced as an opt-in local capability.

## Goal

Add a pinned, health-checkable Neo4j Community foundation with idempotent initial
KG constraints/indexes, without migrating data or changing application behavior.

## Scope

- Add a pinned Neo4j Community Compose service with named persistent volumes and
  a health check.
- Add validated Neo4j settings while preserving `PERSISTENCE_BACKEND=sqlite` as
  the default and retaining `DATABASE_URL`.
- Add the official Python driver, one connection manager, lifecycle context,
  read/write transaction helpers, and a sanitized health result.
- Add idempotent schema bootstrap statements for the initial KG node identities
  and query-backed indexes.
- Add offline tests using a fake driver/session and Compose/config validation.
- Update migration, database, deployment, and security documentation.

## Out of Scope

- Data import, repository adapters, read shadowing, graph projection, or cutover.
- NetworkX routing, disruption policy, simulation behavior, API response
  contracts, LLM behavior, Supervisor tools, and frontend functionality.
- Generated Neo4j data, credentials, or committed local database files.

## Concerns

- Docker image startup and live schema bootstrap depend on the local Docker
  engine and a user-provided `NEO4J_PASSWORD`; no credential is stored here.
- The current API startup remains SQLite-only. Neo4j lifecycle is an explicit
  foundation service/CLI until a later approved runtime-boundary phase.
- Neo4j schema syntax and image/driver compatibility are pinned and recorded
  from official documentation; future upgrades require a separate review.

## Proposal

Use `neo4j==6.3.0` with the official `neo4j:2026.09.0` Community image. Add
`backend/app/persistence/neo4j/driver.py` and `schema.py`, CLI commands for
health and bootstrap, and a `PERSISTENCE_BACKEND` setting defaulting to
`sqlite`. Add only stable identity constraints and indexes for location/route/
shipment lookup predicates; do not import or query operational data.

## Approval

- Approved by: `USER`
- Approved at: `2026-10-13T00:00:00+08:00`

## Acceptance Criteria

- [x] Compose defines the pinned Community service, named persistence, and health check.
- [x] Official driver and validated environment settings are present; SQLite remains default.
- [x] Connection manager verifies connectivity, scopes sessions, and closes cleanly.
- [x] Initial constraints/indexes bootstrap idempotently through explicit database sessions.
- [x] Automated connection/config/schema tests pass without a live Neo4j dependency.
- [x] Relevant docs and `MIGRATION_PROGRESS.md` are updated.
- [x] No data migration or application behavior change occurs.
- [x] Live Neo4j startup and schema bootstrap gate passes; health, two bootstrap
  runs, and read-only constraint/index inspection completed.

## Local Verification

- `\.venv\Scripts\python.exe -m pytest backend/tests/test_neo4j_foundation.py -q`: 6 passed.
- `\.venv\Scripts\python.exe -m pytest backend/tests -q`: 113 passed;
  3 existing deprecation warnings.
- `\.venv\Scripts\python.exe -m compileall -q backend dashboard scripts`: passed.
- `docker compose --env-file .env.example config --quiet`: passed.
- `docker compose up -d neo4j`: passed; container reported healthy.
- `\.venv\Scripts\python.exe scripts/migration/check_neo4j.py`: passed.
- `\.venv\Scripts\python.exe scripts/migration/bootstrap_neo4j.py`: passed twice;
  the second run returned the same schema names.
- Read-only `SHOW CONSTRAINTS`/`SHOW INDEXES`: 8 uniqueness constraints and 5
  explicit indexes confirmed; all explicit indexes were `ONLINE`.

## Demo Evidence

Offline fake-driver tests and live verification cover health, lifecycle, managed
sessions, sanitized errors, idempotent schema bootstrap, and all 8 constraints/
5 explicit indexes. No application data was imported.

## Completion Notes

Foundation implementation and live acceptance verification are complete. Phase
2 is not started. No commit was created automatically.
