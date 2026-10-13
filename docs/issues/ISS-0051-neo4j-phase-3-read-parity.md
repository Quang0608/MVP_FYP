# ISS-0051 Neo4j Phase 3 read parity

Status: COMPLETE

## Goal

Add a read-only Neo4j repository and NetworkX projection for the exact Phase 2
active Asia snapshot, then compare it with the canonical SQLite snapshot and
the frozen deterministic Phase 0 scenarios.

## Scope

- parameterized, snapshot-scoped Neo4j reads for locations, routes, shipments,
  versioned route plans, and ordered shipment legs;
- projection through the existing `build_supply_chain_graph` implementation;
- stable SQLite/Neo4j canonical comparison and machine-readable evidence;
- fixed-clock deterministic scenario comparisons;
- focused tests, live Neo4j verification, regression tests, compilation, and
  diff validation.

## Out of scope

Runtime database selection or cutover, Neo4j writes, data changes, NetworkX or
routing algorithm changes, API/frontend contracts, Supervisor/LLM behavior,
historical/transient imports, and Phase 4 query capabilities.

## Acceptance criteria

- all active entities and typed relationships read from the exact imported
  snapshot with stable IDs and canonical attributes;
- the Neo4j projection matches SQLite node/edge topology and routing attrs;
- frozen scenarios produce identical deterministic outputs or document an
  explicit unsupported comparison;
- SQLite-backed tests and the application default remain unchanged;
- a machine-readable parity report records counts, mismatches, limitations,
  scenario evidence, and snapshot identity.

## Verification plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_neo4j_read_parity.py -q
.\.venv\Scripts\python.exe scripts/migration/compare_sqlite_neo4j.py --source-sqlite reroute_agent.db --report-out docs/migration/phase3/PARITY_REPORT.json
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
git diff --check
```

User approval: 2026-10-13 (Phase 3 request).

## Completion evidence

- Live parity command passed for the Phase 2 snapshot: 91 locations, 150
  routes, 220 shipments, 220 plans, 1,000 legs, 3,960 typed relationships,
  91 projected nodes, and 150 projected directed edges.
- Eight fixed-clock scenarios matched both SQLite and the frozen Phase 0
  scenario artifact; no mismatches or unresolved references were reported.
- Focused tests passed (`4`), full backend tests passed (`122`, with 3
  existing deprecation warnings), compilation passed, and `git diff --check`
  passed.
- Report: `docs/migration/phase3/PARITY_REPORT.json`.
- SQLite remains the default runtime source of truth. No Phase 4 work or commit
  was performed.
