# ISS-0041: Agent-ready backend foundation and minimal Supervisor

## Status

`DONE`

## Source

Direct user request: expose deterministic backend services through trusted tools
and add one bounded Supervisor Agent without moving operational decisions into an
LLM.

## Scope

- Extract the shared deterministic simulation service used by dashboard and
  agent paths.
- Add structured trusted read tools for shipments, disruptions, simulations,
  impacts, routes, location resolution, and validation.
- Add one controlled `simulate_disruption` action tool.
- Add an ID-grounded `/supervisor` endpoint with offline behavior and bounded
  provider tool calls.
- Add structured `IncidentState` for future specialist-agent work.
- Preserve direct dashboard APIs and current `/assistant` compatibility.

## Out of Scope

Full multi-agent orchestration, specialist agents, RAG, vector databases, news,
weather, AIS, new infrastructure, major frontend work, and LLM-based routing,
scoring, impact detection, or validation.

## Acceptance Criteria

- [x] Dashboard simulation and Supervisor simulation use the same service.
- [x] Trusted tools return structured server-owned data and bounded records.
- [x] Location resolution reports ambiguity rather than guessing.
- [x] Supervisor supports analytical queries and controlled simulation.
- [x] Canonical/base network remains unchanged by tool simulations.
- [x] Provider and offline Supervisor tests pass without live API access.
- [x] Existing backend behavior, compilation, frontend build, and Singapore
  workflow remain valid.
- [x] Architecture, API, security, tool catalog, continuity, and issue docs are
  updated.

## Verification Plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
cd frontend; npm run build
```

## Local Verification

- Added structured trusted tool contracts and wrappers under
  `backend/app/agent/`, covering shipment, disruption, location, simulation,
  impact, routing, and route-validation operations.
- Added `POST /supervisor` with a bounded four-iteration tool loop, deterministic
  offline intent path, provider function-tool path, structured `IncidentState`,
  and tool-error handling.
- Extracted `backend/app/simulation_service.py`; both dashboard simulation and
  Supervisor `simulate_disruption` call `run_simulation()`.
- Full backend suite passed: 81 tests, with 3 existing deprecation warnings.
- Backend/dashboard compile checks and `git diff --check` passed.
- Frontend Vite production build passed after the sandboxed `spawn EPERM`
  attempt was retried with the approved process-spawn permission.
- Direct/API versus Supervisor Singapore closure comparison matched: 29
  affected shipments in each path. The Supervisor called
  `resolve_location`, `simulate_disruption`, and `get_affected_shipments`.
- The base `/routes` response was identical before and after both simulations.
- Provider tool-loop tests use a mocked provider; no live OpenAI call is needed.

## Remaining Limitations

- `/assistant` retains its compatibility browser-context path for unsaved
  dashboard plans. `/supervisor` is the ID-oriented agent endpoint and does not
  accept arbitrary context.
- The Supervisor has deterministic intent support for the required use cases;
  full specialist-agent orchestration is deferred.
- Provider-generated final prose is not yet claim-validated field by field;
  deterministic tool outputs remain authoritative.
