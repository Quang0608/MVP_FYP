# ISS-0035: Architecture stabilization and scenario isolation

## Status

`DONE`

## Source

Direct user request

## Context

The local MVP has accumulated several iterations in a small set of backend
modules and a single large React entry point. More importantly,
`build_supply_chain_graph()` currently places shared Pydantic `Location` and
`Route` instances into multiple NetworkX graphs. `apply_disruption()` mutates
those instances, so a disrupted scenario can contaminate a baseline graph and
change before/after calculations.

## Goal

Make scenario graph state isolated and leave a documented, evidence-backed
architecture and refactor plan for the remaining boundary work.

## Scope

- Isolate per-graph location and route state without changing API response
  contracts.
- Add regression coverage for closure, congestion, capacity reservation, and
  deterministic before/after calculations.
- Make a small, safe backend responsibility extraction where a clear boundary
  exists.
- Define the current and target source-of-truth model, including synthetic
  SQLite, canonical Parquet/CSV artifacts, PortWatch/WPI integrations, and
  transient NetworkX state.
- Document the `/assistant` identifier-based direction while preserving the
  current dashboard contract unless a compatibility-safe boundary can be added.
- Inventory obsolete, duplicate, and superseded architecture references.
- Document a frontend decomposition plan without changing the UI design.
- Update continuity and record verification evidence.

## Out of Scope

- PostgreSQL, Neo4j, Kafka, or new external APIs.
- A large migration from synthetic SQLite to canonical operational storage.
- React redesign or broad component extraction with behavior risk.
- Autonomous route selection, route mutation, or operational execution by an LLM.
- GitHub issues, pushes, or pull requests.

## Concerns

- Existing uncommitted changes belong to the user and must be preserved.
- Legacy `runs` compatibility remains readable until a separately approved
  migration; this pass must not delete it.
- The frontend currently sends a full dashboard context to `/assistant`; the
  long-term boundary should reconstruct trusted context server-side from IDs.

## Proposal

Use deep-copied domain state at graph construction so each graph owns its node
and edge model instances. Keep the existing edge `route` attribute and public
service imports for compatibility. Extract only stable, low-risk boundaries;
document larger module moves as follow-up work.

## Approval

- Approved by: User
- Approved at: 2026-09-06

## Acceptance Criteria

- [x] Baseline and disrupted graphs cannot contaminate one another.
- [x] Baseline route status, duration, and load remain unchanged after a
  disruption or reroute calculation.
- [x] Closure, congestion, and capacity changes are scenario-local.
- [x] Repeated before/after calculations remain deterministic.
- [x] Existing API behavior remains compatible.
- [x] `docs/ARCHITECTURE.md` and `docs/REFACTOR_PLAN.md` are complete.
- [x] Obsolete component inventory and frontend decomposition plan are recorded.
- [x] Required tests, compilation, frontend build, and Singapore workflow are
  attempted and recorded.

## Verification Plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
cd frontend; npm run build
docker compose up --build  # when Docker is available
```

Manual gate: run the documented Singapore closure workflow and confirm
`ROUTE_FOUND`, alternatives that avoid `P_SG`, affected shipments, reroute
recommendations, and unchanged baseline graph state.

## Local Verification

2026-09-06:

- `\.venv\Scripts\python.exe -m pytest backend/tests -q`: 43 passed.
- `\.venv\Scripts\python.exe -m compileall -q backend dashboard`: passed.
- `git diff --check`: passed; only existing line-ending conversion warnings were
  emitted.
- `cd frontend; npm run build`: passed with Vite after a sandbox `spawn EPERM`
  retry using the approved local build escalation.
- `docker version`: unavailable because the Docker Desktop Linux engine pipe was
  not present; `docker compose up --build` was not run.

## Demo Evidence

2026-09-06 isolated Singapore closure workflow:

- Used `DATABASE_URL=sqlite://` and no provider key so the repository database
  was not used.
- `POST /simulate-disruption` with `P_SG` and 72 hours returned HTTP 200 and
  15 affected shipments.
- `POST /reroute` returned HTTP 200 and 15 recommendations.
- `POST /plan-route` from `F_SZ` to `C_A` returned `ROUTE_FOUND`; all candidate
  routes avoided `P_SG` and the explanation source was
  `offline_deterministic`.
- Assistant identifier regression verified that a persisted simulation ID
  reconstructs server context and ignores an invented browser location.

## Completion Notes

Added isolated graph construction in `backend/app/graph.py`, retained service
facade imports, and added scenario-state regression tests. Added the
identifier-aware assistant context boundary under `backend/app/agent/` without
removing the transitional unsaved-plan context. Added architecture, data
ownership, obsolete inventory, frontend decomposition, and prioritized refactor
documentation. Docker remains deferred to the existing unavailable-engine
environment concern.
