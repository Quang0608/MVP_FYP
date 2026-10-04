# ISS-0036: Canonical runtime data integration

## Status

`DONE`

## Source

Direct user request: Phase 2 Canonical Runtime Data Integration

## Context

The ingestion pipeline already produces canonical WPI/PortWatch artifacts, but
the runtime still exposes legacy-shaped Pydantic records and reconstructs
shipment routes from parallel ID lists. This makes source ownership unclear and
prevents impact detection from distinguishing completed and remaining legs.

## Goal

Make SQLite repository output source-neutral canonical runtime entities for
locations, routes, shipments, ordered shipment route legs, and the planned
disruption contract while preserving existing HTTP response shapes.

## Scope

- Add canonical runtime domain models with location, route, shipment, leg, and
  disruption semantics.
- Convert synthetic seed and SQLite loading to those models.
- Make ordered shipment legs with `COMPLETED`, `CURRENT`, and `PLANNED` state the
  primary impact-intersection input.
- Keep NetworkX transient and scenario-local with explicit edge state.
- Keep PortWatch/WPI normalized artifacts and mappings read-only through the
  integration adapter.
- Preserve existing API serialization and Singapore closure behavior.
- Update architecture, data ownership, migration, issue, and continuity docs.

## Out of Scope

- PostgreSQL, Neo4j, Kafka, weather, news, RAG, vessel tracking, or new APIs.
- Deleting synthetic shipments or replacing the semi-synthetic digital twin.
- Large SQLite migrations; legacy columns and `runs` compatibility remain.
- Automatic PortWatch routing penalties or automatic rerouting.
- New dashboard features or UI redesign.

## Approval

- Approved by: User
- Approved at: 2026-09-06

## Acceptance Criteria

- [x] Repository-facing runtime records use canonical source-neutral models.
- [x] Synthetic records load through the canonical model boundary.
- [x] Ordered route legs expose current/completed/planned state.
- [x] Impact detection uses current and remaining legs for location and route
  intersections.
- [x] Graph construction consumes canonical locations/routes and keeps state
  transient and isolated.
- [x] WPI/PortWatch mappings enrich the same runtime `Location` model without
  forcing unresolved entities into WPI IDs.
- [x] Existing Singapore closure and API response contracts remain valid.
- [x] Architecture and continuity documentation identify all remaining legacy
  paths and their migration actions.
- [x] Required verification commands and demo are attempted.

## Verification Plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
cd frontend; npm run build
```

Manual gate: verify baseline route state, remaining-leg affected shipments,
unaffected shipments, deterministic alternatives, comparisons, and metrics in
the Singapore closure workflow.

## Local Verification

2026-09-07:

The required Windows commands were executed as:
`.\.venv\Scripts\python.exe -m pytest backend/tests -q` and
`.\.venv\Scripts\python.exe -m compileall -q backend dashboard`.

- `\.\.venv\Scripts\python.exe -m pytest backend/tests -q` — 51 passed;
  FastAPI/httpx and startup lifecycle deprecation warnings remain.
- `\.\.venv\Scripts\python.exe -m compileall -q backend dashboard` — passed.
- `cd frontend; npm run build` — passed with elevated local execution because
  sandboxed Vite/esbuild spawning returned `EPERM`.
- `git diff --check` — passed; Git reported only existing line-ending warnings.
- Docker availability check — Docker client is installed, but the Docker
  Desktop Linux engine pipe is unavailable, so `docker compose up --build` was
  not run.

Focused canonical tests passed: 23.

## Demo Evidence

2026-09-07 isolated Singapore closure workflow:

- Repository loader returned 13 canonical locations, 17 canonical routes, and
  30 canonical shipments with structured route legs.
- Baseline route `F_SZ -> P_SG` remained `ACTIVE` and retained duration 48 hours
  while the scenario graph changed it to `BLOCKED`.
- `POST /simulate-disruption` for `P_SG` closure returned 15 affected
  shipments; a shipment moved to `W_SG` in tests did not remain affected by the
  passed Singapore port or completed road leg.
- `POST /reroute` returned 15 recommendations, 13 successful reroutes, and
  deterministic comparison/metric values.
- No PortWatch activity or disruption automatically changed routing state.

## Completion Notes

The runtime now uses `backend/app/domain/models.py` as the source-neutral
repository/service model. SQLite remains the runtime source of truth for this
phase; WPI/PortWatch Parquet and CSV outputs remain read-only ingestion
artifacts. The port-master adapter preserves WPI identity for accepted mappings
and skips source-native rows lacking required geometry rather than inventing a
mapping. Legacy SQLite column names, `load_supply_chain_data()`, API DTOs, and
`runs` compatibility remain intentionally deferred to the migration plan in
`docs/REFACTOR_PLAN.md`.
