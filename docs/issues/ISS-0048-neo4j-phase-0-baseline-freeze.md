# ISS-0048 Neo4j Phase 0 baseline freeze

## Status

`DONE`

## Source

Direct request: execute only Phase 0 of the Neo4j migration plan.

## Context

The migration plan requires a verified SQLite baseline before any Neo4j
infrastructure, importer, repository adapter, routing change, agent change, or
frontend change. The current runtime uses the active Asia snapshot selected by
`load_runtime_dataset()` and deterministic NetworkX services.

## Goal

Create a reproducible, read-only Phase 0 baseline manifest, deterministic
scenario evidence, and progress report for the current SQLite runtime.

## Scope

- Inspect and document the current active SQLite/domain/NetworkX boundary.
- Export sorted active IDs and canonical attributes through the existing loader.
- Classify compatibility/history rows separately from the active Asia snapshot.
- Verify active counts, references, connectivity, route-pair uniqueness, and
  stable content hashes.
- Capture deterministic scenario outputs without changing application behavior.
- Add automated validation for the generated baseline artifacts.

## Out of Scope

- Neo4j dependencies, configuration, Compose services, or Cypher.
- OR-Tools, routing-policy, LLM/tool, API, database-schema, or frontend changes.
- Mutating or deleting the existing SQLite database, provider artifacts, or
  legacy/history records.
- Phase 1 or any import/cutover work.

## Concerns

- The local SQLite database is a generated artifact and remains ignored; the
  manifest must not embed the database or secrets.
- Scenario timestamps are normalized to a fixed UTC instant for reproducible
  evidence, while the existing application can use wall-clock timestamps.
- NetworkX uses `DiGraph`; a duplicate source/destination pair would require an
  approved structural change and blocks migration work.

## Proposal

Add a read-only `scripts/migration/export_sqlite_baseline.py` command that uses
the existing runtime loader and direct read-only SQLite inspection for separate
row classification. Store sanitized JSON baseline artifacts under
`docs/migration/baseline/`, with `MANIFEST.md`, `BASELINE.md`, and a progress
report documenting commands and results. Add focused tests for manifest
validation and deterministic export behavior.

## Approval

- Approved by: `USER`
- Approved at: `2026-10-13T00:00:00+08:00`

## Acceptance Criteria

- [x] Active 91/150/220/1,000 counts are verified rather than assumed.
- [x] Sorted IDs, canonical attributes, route endpoints, ordered leg data,
  source mappings, and stable hashes are captured without secrets or DB files.
- [x] Compatibility/history/excluded row classes are counted separately.
- [x] Parallel-route, orphan-reference, and connectivity checks are explicit.
- [x] Required deterministic scenarios and repeated-request evidence are saved.
- [x] Automated baseline validation, full tests, compile checks, and the local
  Singapore demo are attempted and recorded.
- [x] Phase 1 has not started and no application behavior has changed.

## Local Verification

- `\.venv\Scripts\python.exe -m pytest backend/tests -q`: 107 passed, 3
  existing deprecation warnings.
- `\.venv\Scripts\python.exe -m pytest backend/tests/test_migration_baseline.py -q`:
  2 passed.
- `\.venv\Scripts\python.exe -m compileall -q backend dashboard scripts`: passed.
- `\.venv\Scripts\python.exe scripts/migration/export_sqlite_baseline.py
  --output-dir docs/migration/baseline`: passed with artifact validation true.
- The same exporter with `--validate`: passed; counts, hashes, structural
  checks, and repeated-request equality all matched.
- `git diff --check`: passed.

## Demo Evidence

The fixed-clock in-memory Singapore closure produced 29 affected shipments, 10
reroutes, and 19 no-feasible recommendations. The isolated FastAPI smoke used
`DATABASE_URL=sqlite://` and verified `/health`, `/simulate-disruption`, and
`/reroute` returned HTTP 200; base routes were unchanged. The local SQLite file
was not modified.

## Completion Notes

Phase 0 artifacts and documentation are complete. Phase 1 is intentionally not
started. No commit was created automatically.
