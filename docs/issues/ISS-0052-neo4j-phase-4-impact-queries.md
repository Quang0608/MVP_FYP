# ISS-0052 Neo4j Phase 4 dependency and impact queries

Status: COMPLETE

## Goal

Add an explicitly invoked, read-only Neo4j knowledge-graph query service that
explains shipment dependencies on disrupted locations and directed routes using
the imported active snapshot.

## Scope

- named, parameterized Cypher for remaining route/location and directed-route
  dependencies;
- typed impact evidence containing plan, leg, progress, target, and graph-path
  details;
- bounded `NEXT_LEG` continuation within a shipment where the schema supports
  it;
- live verification against the Phase 0 frozen scenarios and the existing
  deterministic SQLite analysis;
- query timing evidence, focused tests, regression tests, compilation, and
  documentation.

## Out of scope

Cross-shipment supplier/inventory/business dependencies absent from the schema,
Neo4j writes, runtime cutover, NetworkX/routing changes, FastAPI/frontend
contracts, Supervisor/LLM behavior, and Phase 5 work.

## Acceptance criteria

- completed legs, inactive shipments, and non-active plan versions are excluded;
- location and directed-route dependencies return stable, referentially valid
  structured evidence with deterministic ordering;
- bounded same-shipment downstream leg traversal is safe and explicit;
- selected frozen scenarios have zero unexpected false positives/negatives
  against SQLite dependency results;
- Neo4j remains inactive as the application runtime database and all queries are
  read-only, parameterized, bounded, and timed.

## Verification plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_neo4j_impact.py -q
.\.venv\Scripts\python.exe scripts/migration/verify_neo4j_impact.py --source-sqlite reroute_agent.db --report-out docs/migration/phase4/IMPACT_REPORT.json
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard scripts
git diff --check
```

User approval: 2026-10-13T18:54:26+08:00.

## Completion evidence

- Live verification passed for seven supported frozen references with exact
  SQLite dependency-set parity, complete frozen-impact coverage, zero evidence
  integrity errors, and two bounded same-shipment downstream records.
- Query timings were 33.675–1,180.118 ms, averaging 369.004 ms on the local
  Windows 11/Python 3.12.1 environment. Queries used a five-second Neo4j
  transaction timeout, result limit 500, and traversal depth 5.
- Focused Phase 4 and Phase 3 tests passed (`8`); full backend tests passed
  (`126`) with 3 existing deprecation warnings. Compilation and diff checks
  passed.
- Report: `docs/migration/phase4/IMPACT_REPORT.json`.
- SQLite remains the runtime source of truth. No Phase 5 work or commit was
  performed.
