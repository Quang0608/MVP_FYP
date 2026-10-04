# Refactor plan

This plan is intentionally ordered by risk and correctness. It describes work
after the architecture stabilization pass; it does not introduce PostgreSQL,
Neo4j, Kafka, or new product behavior.

## P0 — correctness

1. Keep graph scenarios isolated. `backend/app/graph.py` now deep-copies node
   and edge domain models; retain regression tests for closure, congestion,
   route status, duration, load, capacity reservation, and repeatability.
2. Strengthen deterministic tests from `ISS-0006`: replace permissive assertions
   with controlled priority, no-route, and sequential capacity cases.
3. Separate baseline and active scenario construction behind a small service
   factory so endpoint code cannot accidentally reuse or mutate a graph. Phase
   3 now provides this through `NetworkStateEngine` plus the graph projection;
   the remaining work is to remove compatibility facades after callers migrate.
4. Define disruption semantics for endpoint congestion, route status, and
   remaining-route intersection; completed for the Phase 3 policy table, with
   calibration still deferred.
5. Add invariant checks that a routing calculation does not mutate repository
   domain objects or persisted master rows; retain these checks as new
   repository-backed scenario paths are introduced.

## P1 — architecture and data boundaries

1. Split `backend/app/schemas.py` into domain models and API DTOs only after
   import compatibility tests exist.
2. Extract `services.py` in this order: graph/scenario projection (started in
   this pass), impact detection (Phase 3 service extracted), candidate routing, scoring/capacity, and
   recommendation orchestration. Preserve facade imports until all consumers
   migrate.
3. Split `main.py` into API routers for shipments, locations, disruptions,
   routing, and assistant. Keep handlers thin and move orchestration into
   application services.
4. Split `repository.py` into repositories for master network data, shipments,
   disruptions/simulations, and decisions. Keep the legacy reader isolated until
   a migration is approved.
5. Keep the canonical operational import boundary explicit. `backend/app/domain/`
   is the runtime model, `backend/app/integrations/canonical.py` adapts usable
   WPI-preferred port-master rows, and `backend/app/asia_dataset.py` produces the
   reproducible derived/semi-synthetic Asia population. Future reviewed adapters
   may replace generated entities, but must preserve source IDs, provenance, and
   the repository boundary without guessing mappings.
6. Migrate legacy SQLite master rows and compatibility fixture ownership in a
   separate issue: back up, validate counts/references, compare routing outputs,
   run the Singapore/Port Klang demos, migrate history and foreign keys, then
   retire the old rows and aliases. The active Asia rows are already canonical
   runtime records; this remaining work is cleanup, not a second runtime model.
7. Keep PortWatch/WPI processed files read-only ingestion artifacts and add
   explicit freshness/quality metadata when they become runtime inputs.

8. Route all API disruption orchestration through the canonical disruption,
   policy, and network-state services; keep `apply_disruption()` only as a
   tested compatibility facade until legacy callers are removed.

9. Add a reviewed runtime import/migration command for replacing generated
   synthetic enterprise rows with future approved datasets while retaining the
   same `Location`, `Route`, `Shipment`, and `ShipmentRouteLeg` contracts.

## P2 — assistant grounding and reproducibility

1. Move persisted dashboard assistant requests to the ID-only `/supervisor`
   path after the current compatibility `/assistant` client flow is migrated.
2. Expand Supervisor grounding validation beyond tool input schemas to provider
   response claims about route IDs, location IDs, shipment IDs, risk, duration,
   cost, and supported structured claims.
3. Render key operational prose deterministically from validated structured
   fields where possible; use provider prose only for explanation and framing.
4. Pin dependencies and record Python/Node build versions for reproducibility.
5. Add explicit explanation-state and deterministic algorithm-duration metrics,
   keeping provider latency separate from routing performance.
6. Repair known text encoding corruption and add a source-file regression check.

## P3 — new features

Only after P0–P2 are stable:

1. Operator filters and shipment drill-down (`ISS-0012`).
2. Custom disruption builder/history improvements (`ISS-0013`).
3. Capacity utilization view (`ISS-0014`).
4. Scenario comparison/export enhancements (`ISS-0015`).
5. Calibrated PortWatch activity penalties and canonical route/shipment loading.

## Later legacy-row cleanup and future source migration sequence

1. Freeze the current SQLite database and export counts, IDs, references, route
   metrics, and Singapore closure outputs.
2. Validate WPI-preferred and accepted PortWatch source-native location rows,
   including geometry and unresolved mapping review; do not coerce unresolved
   entities into WPI identities.
3. Compare the active Asia canonical rows with any legacy fixture rows and
   preserve simulation/recommendation history and foreign-key references.
4. Run record-level and route-level parity checks, including remaining-leg impact
   detection and deterministic rerouting, before removing compatibility rows.
5. Keep future approved source adapters behind the same repository interfaces;
   do not make Parquet/CSV a second runtime model.
6. Remove fixture seeding, compatibility list properties, aliases, and legacy
   table reads only in a separately approved cleanup issue after rollback
   evidence exists.

## Safe cleanup policy

- Do not delete legacy persistence or historical briefs until dependency and
  migration checks are recorded.
- Do not present deferred PostgreSQL, Neo4j, or Kafka plans as active runtime
  architecture.
- Do not move routing or scoring into React or an LLM.
- Every extraction must preserve an import facade or update all callers in one
  verified change.
