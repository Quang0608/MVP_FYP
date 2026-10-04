# ISS-0037: Dynamic network state and disruption policy

## Status

`DONE`

## Source

Direct user request: Phase 3 - Dynamic Network State and Disruption Policy

## Context

Phase 2 provides canonical runtime locations, routes, shipments, ordered route
legs, and isolated NetworkX graphs. Disruption behavior is still split between
the graph module, API request DTOs, and PortWatch impact helpers. Congestion is
hard-coded, simulated and PortWatch events do not share one canonical policy
path, and impact results do not classify whether rerouting is required.

## Goal

Create one deterministic network-state engine and disruption-policy layer that
projects canonical base data plus active canonical disruptions into an isolated
scenario state, classifies active shipment impacts from remaining route legs,
and passes only reroute-required shipments to deterministic rerouting.

## Scope

- Add configurable deterministic policies for closure, shutdown, congestion,
  and capacity reduction effects.
- Keep canonical locations/routes and persistent records unchanged.
- Normalize simulated and PortWatch disruption facts into the same policy input.
- Add `UNAFFECTED`, `NETWORK_WARNING`, `SHIPMENT_AT_RISK`, and
  `REROUTE_REQUIRED` impact classifications.
- Preserve existing API response shapes unless an additive impact field is
  required for explainable scenario results.
- Add exact tests for disruption types, progress, isolation, policy reuse, and
  rerouting selection.
- Update architecture, API, deployment/demo, concerns, issue, and continuity
  documentation.

## Out of Scope

- RAG, LLM agent features, news, weather, vessel tracking, Neo4j, Kafka,
  PostgreSQL migration, new external APIs, or major frontend changes.
- Automatic rerouting of PortWatch events without deterministic policy and
  impact criteria.
- Persisting temporary scenario values into canonical master data.

## Approval

- Approved by: User
- Approved at: 2026-09-13

## Acceptance Criteria

- [x] Network state is built from canonical locations/routes, current loads, and
  active disruptions through one service.
- [x] Scenario state contains effective availability, duration, cost, risk,
  capacity, load, and disruption IDs while preserving base values.
- [x] Port closure, route closure, factory shutdown, warehouse shutdown,
  congestion, and capacity reduction have deterministic configurable policies.
- [x] Simulated and PortWatch-derived disruptions use the same policy path.
- [x] Impact detection uses current and remaining shipment legs and returns the
  four required classifications.
- [x] Rerouting is invoked only for `REROUTE_REQUIRED` shipments.
- [x] Base domain objects and independent scenario graphs remain unchanged and
  isolated.
- [x] Existing Singapore closure API workflow remains compatible.
- [x] Congestion and capacity scenarios demonstrate non-blocking and infeasible
  outcomes respectively.
- [x] Required tests, compile checks, frontend build, and local demos are
  attempted and recorded.

## Verification Plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
cd frontend; npm run build
```

Manual gates:

1. Singapore closure: affected remaining-route shipments become
   `REROUTE_REQUIRED`, alternatives avoid Singapore, and base routes remain
   unchanged.
2. Klang congestion: the route remains available, effective duration/risk
   increase, and a dependent shipment becomes `SHIPMENT_AT_RISK` without a
   reroute requirement while capacity remains feasible.
3. Capacity reduction: a dependent shipment becomes `REROUTE_REQUIRED` when
   effective capacity cannot carry its load.

## Local Verification

Passed on 2026-09-13:

- `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 63 passed,
  with 3 expected deprecation warnings.
- `.\.venv\Scripts\python.exe -m compileall -q backend dashboard`: passed.
- `git diff --check`: passed.
- `cd frontend; npm run build`: passed with Vite 5.4.21 after retrying outside
  the sandbox because the sandbox blocked the esbuild child process.
- Docker CLI is installed, but `docker info` cannot connect to the Docker
  Desktop Linux engine pipe; Compose was not run.

## Demo Evidence

Passed using an in-memory SQLite runtime and FastAPI `TestClient`:

- Singapore `PORT_CLOSURE` at `P_SG`: 15 `REROUTE_REQUIRED`, 15 unaffected,
  15 recommendations; base records remain unchanged.
- Klang `CONGESTION` at `P_KL`: 10 `SHIPMENT_AT_RISK`, 20 unaffected, route
  remains available, and 0 reroute recommendations.
- Critical `CAPACITY_REDUCTION` on `R3`: 3 `REROUTE_REQUIRED`, 2 at risk,
  25 unaffected, and 3 recommendations.
- Regression coverage includes an in-progress shipment at Singapore after its
  Singapore leg completed; the closure is `UNAFFECTED`.

## Completion Notes

The canonical disruption/policy/network-state/impact path is now shared by
simulation and PortWatch-derived events. Temporary scenario values remain in
the state overlay and isolated graph only. Policy multipliers are documented
research assumptions and tracked as `CON-023`; they are not PortWatch facts.
