# ISS-0050 Neo4j Phase 2 active SQLite import

## Status

`COMPLETE`

## Source

Direct user request: execute only Phase 2 — idempotent SQLite-to-Neo4j import.

## Goal

Import only the frozen active Asia operational snapshot through the existing
canonical SQLite loader and Pydantic domain models, preserving stable IDs,
canonical attributes, ordered shipment legs, provenance, and the approved
Neo4j graph relationships. SQLite remains the runtime source of truth.

## Scope

- Add a standalone dry-run/execute/verify importer CLI.
- Validate the canonical active snapshot before any Neo4j write.
- Import 91 locations, 150 directed routes, 220 shipments, 1,000 ordered legs,
  one version-1 plan per shipment, and their approved graph relationships.
- Use stable-key `MERGE`, deterministic ordering, parameterized batches, and no
  database wipe or unrelated-node deletion.
- Emit a machine-readable import manifest with counts, imported IDs, hashes,
  provenance, rejected records, unresolved references, and parity results.
- Add automated source validation, Neo4j verification, dry-run, and repeat-run
  tests without changing application runtime behavior.

## Out of scope

- Historical disruptions, simulation runs, agent decisions, legacy rows,
  PortWatch observations, transient scenario state, or data outside the active
  Asia snapshot.
- Neo4j runtime cutover, repository adapters, NetworkX/routing changes, API or
  frontend changes, LLM changes, and Phase 3 work.

## Acceptance criteria

- [x] Active source counts and integrity checks pass: 91/150/220/1,000, valid
  endpoints/references, one-based ordered legs, and timestamp/progress checks.
- [x] Dry-run validates source data and performs no Neo4j writes.
- [x] Execute imports all approved nodes and relationships idempotently.
- [x] A second execute produces no duplicate nodes/relationships and no stale
  active-membership edges.
- [x] Neo4j verification confirms source attribute parity and stable ID sets.
- [x] Existing SQLite-backed tests pass and SQLite remains the default backend.
- [x] Phase 2 documentation and continuity records are updated.

## Local verification plan

- `\.venv\Scripts\python.exe -m pytest backend/tests/test_neo4j_import.py -q`
- `\.venv\Scripts\python.exe -m pytest backend/tests -q`
- `\.venv\Scripts\python.exe -m compileall -q backend dashboard scripts`
- `\.venv\Scripts\python.exe scripts/migration/import_sqlite_to_neo4j.py --snapshot-id asia-runtime-seed-20260913 --source-sqlite reroute_agent.db --dry-run --manifest-out <path>`
- Execute and verify the importer twice against the live Phase 1 Neo4j service.

## Approval

- Approved by: `USER`
- Approved at: `2026-10-13T18:16:54+08:00`

## Completion notes

Phase 2 passed locally: dry-run, two live execute runs, and final read-only
verification all passed. Source/imported counts were 91 locations, 150 routes,
220 shipments, 220 plans, and 1,000 legs with 3,960 typed relationships. No
attribute mismatches or unresolved references were found. Phase 3 was not
started. Foundation/import tests passed (`5` focused import tests and `118`
backend tests, with 3 existing deprecation warnings); compilation and diff
checks passed. No commit was created automatically.
