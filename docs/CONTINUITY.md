# Continuity

## Current Project State

The repository contains a functional local FastAPI and React MVP backed by
structured SQLite persistence for synthetic master and simulation data, NetworkX
routing, and an optional OpenAI explanation layer.

As of 2026-09-07, the automated suite has 51 passing tests and the backend plus
React production bundle compile. The dashboard recreation and no-key local
workflow pass; Docker remains unverified because the local Docker Desktop Linux
engine is unavailable.

## Latest Completed Work

- Date: 2026-07-26T17:55:09+08:00
- Local issue: `ISS-0007`
- Summary: introduced structured relational storage for locations, routes,
  shipments, ordered planned legs, disruptions, simulation snapshots, and agent
  decisions while preserving current API response contracts and legacy reads.
- Files changed: repository/API integration, persistence tests, database/API/
  security/story documentation, issue evidence, and continuity.
- Verification: 12 tests passed, compilation succeeded, the isolated Singapore
  backend workflow passed, the frontend returned HTTP 200, and `git diff --check`
  reported no content errors.

## React Migration

- Date: 2026-08-14
- Local issue: `ISS-0008`
- Summary: replaced the Streamlit client with a Vite React frontend. The new app
  keeps the existing API contracts, renders the network as SVG, and supports
  planning, batch rerouting, metrics, and shipment analytics.
- Verification: frontend production build and HTTP smoke check passed; backend
  tests (12) and compilation passed; isolated Singapore closure workflow passed.
  Docker image and container demo remain unverified because Docker Desktop's
  Linux engine was unavailable.

## CORS Fix

- Date: 2026-08-14
- Local issue: `ISS-0009`
- Summary: added configurable FastAPI CORS middleware for the local React
  development and Compose origins after browser preflight requests returned 405.
- Verification: 13 backend tests and compilation passed, including an allowed
  preflight/GET check and rejection of an unlisted origin.

## Interactive Map

- Date: 2026-08-14
- Local issue: `ISS-0010`
- Summary: added wheel zoom, zoom controls, reset, and pointer drag-to-pan to
  the React SVG network map without changing route or disruption data.
- Verification: `npm run build` passed.

## Geographic Basemap

- Date: 2026-08-14
- Local issue: `ISS-0011`
- Summary: replaced the abstract SVG map with a Leaflet/OpenStreetMap geographic
  basemap using persisted coordinates, markers, tooltips, and route overlays.
- Verification: Leaflet dependencies installed and `npm run build` passed.

## Feature Review

- Date: 2026-08-14
- Summary: reviewed the React/API workflow and added four implementation-ready
  feature issues: operator filters and shipment drill-down (`ISS-0012`), custom
  disruption builder and history (`ISS-0013`), capacity utilization view
  (`ISS-0014`), and scenario comparison/export (`ISS-0015`).
- Scope: backlog proposals only; no application code changed in this review.

## Operations Dashboard Recreation

- Date: 2026-08-15
- Local issue: `ISS-0016`
- Summary: recreated the supplied dark command-center design in React with a
  geographic network map, KPI strip, assistant/recommendation rail, disruption
  simulator, shipment filters and detail view, capacity bottlenecks, rerouting
  summary, route comparison, performance/risk/insight panels, history, and JSON/
  CSV export. Added a labeled deterministic explanation fallback and structured
  disruption inputs to history.
- Verification: 15 backend tests, compilation, React build, HTTP preview 200,
  and Singapore closure workflow passed. Docker image/demo remains unverified.

## Panel Order Adjustment

- Date: 2026-08-15
- Local issue: `ISS-0017`
- Summary: moved Rerouting Summary beside the network map and moved the AI
  Assistant into the first lower content-row position, preserving all behavior.
- Verification: `npm run build` passed; backend contracts were unchanged.

## Shipment Analysis Detail

- Date: 2026-08-15
- Local issue: `ISS-0018`
- Summary: affected-shipment analysis now renders the original route, selected
  reroute, duration/cost/risk/capacity values, delay and cost deltas, and the
  grounded backend summary with recommended action, warning, and next steps.
- Verification: React build passed and the no-key shipment analytics workflow
  returned a labeled deterministic summary.

## Plan Route Provider Resilience

- Date: 2026-08-15
- Local issue: `ISS-0019`
- Summary: route planning no longer fails when a configured explanation provider
  is unreachable or times out; the deterministic route result returns with a
  labeled offline explanation. Authentication and other provider failures remain
  explicit.
- Verification: 16 backend tests, compilation, and the exact current-config
  Singapore plan request passed with HTTP 200 and `ROUTE_FOUND`.

## Focused Route Map and Recommendation Placement

- Date: 2026-08-15
- Local issue: `ISS-0020`
- Summary: before planning the map shows the seeded network; after planning it
  filters to the selected route's origin, destination, and intermediate legs.
  The planner and current AI recommendation now appear adjacent near the top.
- Verification: React build, 16 backend tests, compilation, and diff check passed.

## Grounded Assistant and Staged Disruptions

- Date: 2026-08-15
- Local issue: `ISS-0021`
- Summary: disruption selection is now staged and can combine multiple scenarios;
  dashboard state changes only after **Run selected disruption**. Interactive
  planning explains disrupted originals, compares alternatives, and reports no
  feasible routes. The assistant is now a chat UI backed by `POST /assistant`
  with current plan, disruption, shipment, recommendation, and location context.
- Verification: 17 backend tests, React build, compilation, combined-disruption
  simulation, and assistant route-comparison smoke checks passed.

## Readable Assistant and Interactive Route Analysis

- Date: 2026-08-15
- Local issue: `ISS-0022`
- Summary: increased dashboard text sizes, moved assistant chat above Current
  Recommendation, and added a shipment-style interactive route analysis showing
  original/selected snapshots plus every backend-returned alternative.
- Verification: 17 backend tests, React build, compilation, and diff check passed.

## Consolidated Route Recommendation

- Date: 2026-08-15
- Local issue: `ISS-0023`
- Summary: consolidated the interactive route answer so Current Recommendation
  contains the single before/after comparison, while Route Comparison retains
  alternative-route details directly below the recommendation. Removed the
  Performance Overview panel from beneath the affected-shipment workflow. An
  unaffected original route now shows only its original-route result, and a
  single alternative is kept only in the before/after comparison.
- Verification: 17 backend tests, React build, compilation, and diff check passed.

## Active Work

- Current local issue: `ISS-0024` complete locally; no active implementation issue
- Current goal: finish the local React integration and container verification
- Current blockers: Docker Desktop Linux engine unavailable locally; stronger LLM
  grounding, richer evaluation metrics, encoding cleanup, and test-strength work
  remain open.

## Canonical Data Layer Preparation

- Date: 2026-08-23
- Local issue: `ISS-0024`
- Summary: added the source-neutral `data/` directory, raw-source READMEs,
  processed/mapping documentation, JSON schemas, synthetic sample datasets, and
  placeholder source ingestion/normalization/loading modules.
- Validation: added Pydantic canonical models and cross-entity checks for
  locations, routes, shipments, route steps, vessels, AIS positions, port
  metrics, and disruption events.
- Boundary: current SQLite persistence and `backend/app/data.py` remain unchanged;
  processed-file loading into PostgreSQL/Neo4j is deferred.
- Verification: 20 backend tests, 3 focused pipeline tests, compilation, 8 JSON
  schema parse checks, isolated health/route API smoke, and `git diff --check`
  passed on 2026-08-23.

## WPI Canonical Port Table

- Date: 2026-08-23
- Local issue: `ISS-0025`
- Summary: normalized the uploaded `data/raw/wpi/UpdatedPub150.csv` into
  `data/processed/wpi/ports.parquet` with the requested nine canonical fields.
- Result: 3,802 rows; unique `location_id` values; valid coordinates; blank
  UN/LOCODE values represented as null; raw input unchanged.
- Verification: 21 backend tests, compilation, Parquet inspection, and
  `git diff --check` passed.

## PortWatch Monitoring Pipeline

- Date: 2026-08-23
- Local issue: `ISS-0026`
- Summary: added official ArcGIS REST ingestion for PortWatch daily ports and
  chokepoints, immutable dated raw bundles, WPI/checkpoint mappings, canonical
  monitoring Parquet, validation reports, and current-state outputs.
- Boundary: PortWatch provides network operational monitoring only. The current
  SQLite/routing/dashboard runtime is not yet wired to these outputs; rerouting,
  disruption ingestion, Kafka, and Neo4j remain out of scope.
- Verification: 24 backend tests, compilation, 12 JSON schema checks, CLI help
  checks, and `git diff --check` passed with offline fixtures.

### Live PortWatch Extraction

- Date: 2026-08-23
- Request: ports from 2026-08-10 through 2026-08-16.
- Result: 10,325 raw records across 11 pages; 5,300 WPI-matched canonical rows;
  1,005 unresolved source ports; missing observations on 2026-08-15 and
  2026-08-16.
- Outputs: `data/processed/portwatch/port_monitoring.parquet` and
  `data/processed/portwatch/current_port_state.parquet` with 1,059 latest WPI
  locations.

### PortWatch Name-Only Remapping

- Date: 2026-08-23
- Local issue: `ISS-0027`
- Summary: changed PortWatch-to-WPI resolution to use manual overrides, exact
  normalized names across all countries, and conservative fuzzy name matching.
  Country remains audit metadata and is no longer a matching requirement.
- Result: the same 10,325 immutable raw records now produce 5,625 canonical
  rows; 1,125 source ports matched, 940 remain unresolved, and 17 matches use
  the recorded fuzzy score. Source dates 2026-08-15 and 2026-08-16 remain
  missing.
- Outputs: updated `data/mappings/portwatch_port_mapping.csv`,
  `data/processed/portwatch/port_monitoring.parquet`,
  `data/processed/portwatch/port_monitoring_report.json`, and
  `data/processed/portwatch/current_port_state.parquet` with 1,121 latest WPI
  locations.
- Verification: 25 backend tests, compilation, and `git diff --check` passed.

### Persistent WPI-PortWatch Mapping

- Date: 2026-08-23
- Local issue: `ISS-0029`
- Summary: added `wpi_portwatch_port_mapping.csv` as the persistent source-ID
  mapping and `wpi_portwatch_review_queue.csv` as the numbered confirmation
  queue. The builder proposes exact, approved country-alias, and conservative
  country-compatible fuzzy matches. Normalization now reads the saved table only
  and never rematches names.
- Result: 2,065 source-port rows; 1,158 automatic mappings and 907 review or
  unmapped rows after adding observed, unambiguous country aliases.
  Normalization produced 5,790 canonical rows and current state for 1,157 WPI
  locations.
- Verification: 25 backend tests, compilation, and `git diff --check` passed.

### PortWatch Activity Baselines and Current State

- Date: 2026-08-23
- Local issue: `ISS-0030`
- Summary: added `port_baselines.parquet` and `port_features.parquet` with
  configurable observed-window averages, day-over-day changes, activity
  scores, and bounded activity anomalies. The latest state now exposes
  `operational_status` as an activity indicator only.
- Result: 5,790 feature rows, 1,157 baselines, and 1,157 current port states.
  Observations cover 2026-08-10 through 2026-08-14; all baselines are marked
  `LIMITED_HISTORY`. Current statuses are 823 NORMAL, 168 HIGH_ACTIVITY, and
  166 LOW_ACTIVITY.
- Integration: the NetworkX graph can attach supplied current state to matching
  nodes and identify shipments whose planned routes include flagged ports. It
  does not alter route weights or select reroutes. Neo4j/PostgreSQL loading and
  routing penalties remain future work.
- Verification: 27 backend tests, compilation, and `git diff --check` passed.

### PortWatch Disruption Pipeline

- Date: 2026-08-23
- Local issue: `ISS-0031`
- Summary: added the official PortWatch disruption layer client and immutable
  retrieval snapshots, canonical `disruptions.parquet`, relational WPI
  `disruption_affected_ports.parquet`, and date-filtered
  `current_disruptions.parquet`. Event IDs are stable merge keys; changed events
  update and unchanged/stale events are ignored.
- Integration boundary: `load_current_disruption_state` exposes canonical event
  attributes and WPI `affected_location_ids` for future impact detection. It
  does not trigger rerouting or alter dashboard behavior.
- Verification: 30 backend tests, compilation, and `git diff --check` passed.
  No live disruption snapshot was downloaded automatically.

### PortWatch WPI Name-Country Remapping

- Date: 2026-08-23
- Local issue: `ISS-0028`
- Summary: superseded the name-only fuzzy rule with exact normalized matching
  of WPI `Main Port Name`/canonical `name` plus WPI `Country Code`/canonical
  `country` against PortWatch `portname` and `country`. PortWatch `ISO3` is
  retained for audit only because the uploaded WPI Country Code values are
  country names.
- Result: reused the immutable 10,325-record raw extraction and produced 5,300
  canonical rows, 1,060 matched ports, 1,005 unresolved ports, and 1,059
  current-state locations. Source dates 2026-08-15 and 2026-08-16 remain
  missing.
- Verification: 25 backend tests, compilation, and `git diff --check` passed.

## Important User Stories

- `US-0001`: simulate a disruption and reroute affected shipments
- `US-0002`: plan an interactive capacity-aware route
- `US-0003`: receive a grounded operational explanation
- `US-0004`: verify a release candidate locally before publication

## Known Concerns

See [CONCERNS.md](CONCERNS.md).

## Live PortWatch Disruption Run

- Date: 2026-08-24
- Scope: events with `fromdate` in calendar year 2026
- Result: one immutable raw snapshot with 7 records; 7 canonical historical
  events; 1 active event as of `2026-08-24T00:00:00Z`; 16 resolved WPI
  affected-port relations; 27 unresolved affected-port tokens.
- Unresolved detail: 26 source IDs belong to event `1001279`; `chokepoint6`
  belongs to event `10000004` and is a checkpoint token rather than a WPI port.
- Validation: no warnings; 30 backend tests, compilation, and diff check passed.

## Unified WPI-PortWatch Port Master

- Date: 2026-08-30
- Local issue: `ISS-0032`
- Summary: rebuilt the PortWatch/WPI boundary as a multi-source port master.
  WPI remains preferred for accepted mappings; every valid unmatched PortWatch
  source port is retained as `PW_PORT_<portid>` with `SOURCE_NATIVE` provenance.
  Separate canonical, network, and active-route port sets are generated.
- Result: 4,709 canonical ports (3,802 WPI and 907 PortWatch source-native),
  10,320 normalized monitoring rows plus 10,325 source links, and 42 resolved
  disruption relations. `PW_PORT_port2177` represents Nakagusukuwan. One
  `chokepoint6` token remains unresolved because it is a checkpoint token, not
  a port.
- Boundary: network and active-route sets are empty until canonical route and
  shipment Parquet inputs exist; the current MVP's synthetic graph IDs are not
  guessed into those sets. Source-native coordinates remain null because the
  daily PortWatch schema has no geometry.
- Verification: full backend tests, compilation, and `git diff --check` are
  recorded in `ISS-0032` after execution.

## PortWatch Runtime Integration

- Date: 2026-08-30
- Local issue: `ISS-0033`
- Summary: connected normalized PortWatch/WPI state to the live application via
  `backend/app/integrations/portwatch.py`. Runtime IDs are translated through
  `data/mappings/runtime_location_mapping.csv`; `P_SG` maps to the PortWatch
  source-native Singapore record while `P_KL`, `P_TP`, and `P_LC` map to WPI.
- Runtime behavior: `/locations` and `/locations/{id}` expose source,
  canonical identity, latest observation, activity, anomaly, and operational
  status. NetworkX receives the same state on nodes without changing route
  weights. `/portwatch/state` and `/portwatch/disruptions` expose clean adapter
  data without triggering rerouting.
- Verification: 34 backend tests, backend/dashboard compilation, frontend
  production build, and the Singapore API check passed. Existing FastAPI and
  Starlette deprecation warnings remain unrelated.

## PortWatch Disruption Impact Detection

- Date: 2026-08-30
- Local issue: `ISS-0034`
- Summary: active normalized PortWatch disruptions now pass through the
  deterministic `ImpactDetectionService`. Canonical affected locations are
  resolved to runtime graph IDs, then compared with each active shipment's
  remaining planned route from `current_location_id` onward.
- Output: `GET /portwatch/impacts` returns event ID, runtime and canonical
  affected location IDs, affected shipment IDs, source, and the reason
  `remaining route contains disrupted port`. It returns no action for ports
  already passed, unrelated shipments, inactive shipments, or unreferenced
  ports.
- Boundary: detection does not mutate shipments, block routes, change weights,
  invoke the LLM, or trigger rerouting. The current live snapshot returns zero
  impacts because its active event affects unresolved checkpoint `chokepoint6`.
- Verification: 38 backend tests, compilation, `git diff --check`, and fixture
  plus live API checks passed.

## Next Recommended Steps

1. Verify the React Compose image/demo when Docker is available.
2. Prioritize `ISS-0012` for day-to-day triage, then `ISS-0013` and `ISS-0014`.
3. Complete grounding, metrics, encoding, and remaining test-strength issues.
3. Decide whether to introduce Alembic and migrate legacy `runs` rows.
4. Run and record the full local demo gate.
5. Ask the user for explicit approval before any GitHub push or issue migration.

## Architecture Stabilization and Scenario Isolation

- Date: 2026-09-06
- Local issue: `ISS-0035`
- Summary: isolated every NetworkX scenario from shared Pydantic `Location` and
  `Route` instances by moving graph construction/scenario mutation to
  `backend/app/graph.py` and deep-copying graph-owned state. Existing imports
  from `backend.app.services` remain compatible.
- Regression coverage: closure, congestion, capacity reservation, source-model
  immutability, and repeatable before/after route calculations.
- Assistant boundary: added optional `simulation_run_id`, `disruption_id`, and
  `shipment_id` request identifiers. Persisted-run requests reconstruct trusted
  context on the server; the old context field remains only for unsaved plans.
- Documentation: added `docs/ARCHITECTURE.md` and `docs/REFACTOR_PLAN.md`,
  updated API/database/security/deployment indexes, and labeled the original
  Streamlit/Neo4j brief as historical context. No obsolete file was deleted by
  this pass; the pre-existing Streamlit deletion remains untouched.
- Verification: 43 backend tests passed, backend/dashboard compilation passed,
  React production build passed, `git diff --check` passed, and an isolated
  Singapore closure workflow returned 15 affected shipments, 15 recommendations,
  `ROUTE_FOUND`, and `offline_deterministic` explanation output. Docker was not
  run because the local Docker Desktop Linux engine was unavailable.

## Current Handoff

- Current local issue: `ISS-0036` is complete locally.
- Current priority: use `docs/REFACTOR_PLAN.md` for the deferred canonical SQLite
  migration and P0/P1 boundary work; no new product features were added in this
  phase.
- Current blockers: Docker engine availability, canonical SQLite migration,
  stronger LLM grounding, reproducibility pinning, encoding cleanup, and
  remaining deterministic test-strength work.

## Canonical Runtime Data Integration

- Date: 2026-09-07
- Local issue: `ISS-0036`
- Summary: introduced source-neutral runtime `Location`, `Route`, `Shipment`,
  `ShipmentRouteLeg`, `Disruption`, and `RuntimeDataset` models. Synthetic seed
  and SQLite repository loading now cross that boundary; API DTOs remain a
  compatibility edge.
- Runtime boundary: SQLite is the single runtime source of truth for this phase.
  WPI/PortWatch CSV/Parquet files remain processed ingestion artifacts. The
  canonical port-master adapter maps usable WPI-preferred/source-native rows to
  runtime `Location` without coercing unresolved rows into WPI IDs.
- Routing boundary: NetworkX consumes canonical locations/routes and stores
  scenario duration, status, load, capacity, cost, and risk on isolated graph
  edges. Impact detection uses current and remaining ordered shipment legs.
- Remaining legacy paths: SQLite compatibility column names, derived leg
  progress/times, API list-shaped route fields, `load_supply_chain_data()`, the
  pipeline validation model family, and legacy `runs` reads. Their removal is
  deferred to the migration sequence in `docs/REFACTOR_PLAN.md`.
- Verification: 51 backend tests, backend/dashboard compilation, React
  production build, `git diff --check`, and the Singapore closure workflow
  passed. Docker is UNCONFIRMED because the Docker Desktop Linux engine pipe is
  unavailable.

## Dynamic Network State and Disruption Policy

- Date: 2026-09-13
- Local issue: `ISS-0037`
- [CODE] Added canonical disruption normalization, configurable deterministic
  policy effects, transient `NetworkStateEngine` overlays, and progress-aware
  impact classifications. Persistent locations/routes and independent graphs
  remain isolated from scenario changes.
- [CODE] Simulated and PortWatch-derived events now enter the same canonical
  policy path; rerouting receives only `REROUTE_REQUIRED` shipments. Congestion
  remains available and produces at-risk classifications when feasible.
- [TOOL] Full backend suite passed with 63 tests. Singapore closure produced 15
  reroute-required shipments and 15 recommendations; Klang congestion produced
  10 at-risk shipments and no recommendations; critical R3 capacity reduction
  produced 3 reroute-required shipments and 3 recommendations.
- [ASSUMPTION] Policy multipliers and severity capacity reductions are
  controlled research assumptions documented in `docs/ARCHITECTURE.md` and
  tracked by `CON-023`; they are not external PortWatch facts.

## Assistant Dashboard Placement

- Date: 2026-09-13
- Local issue: `ISS-0038`
- [CODE] Moved the existing AI Supply Chain Assistant beside the affected
  shipments table and removed the redundant introductory/dashboard route text.
  Assistant interaction and backend ownership remain unchanged.
- [TOOL] Frontend Vite production build and `git diff --check` passed.
- [CODE] Consolidated the existing AI insight list into the Rerouting Summary
  and removed the separate Recent AI Insights panel/title; lower analytics now
  uses the remaining capacity and risk panels.
- [TOOL] Frontend Vite production build passed again after the consolidation.

## Asia Network and Shipment Population Expansion

- Date: 2026-09-13T00:00:00+08:00
- Local issue: `ISS-0039`
- [USER] Requested a reproducible Asia-focused operational network and larger
  synthetic shipment population without changing policy, routing, or assistant
  architecture.
- [CODE] Added `backend/app/asia_dataset.py`, selecting 51 existing canonical
  WPI ports and generating 12 factories, 14 warehouses/DCs, 14 customers, 150
  sparse directed routes, 220 shipments, and 1,000 ordered route legs from
  seed `20260913`. Real ports are not duplicated; synthetic enterprise records
  use explicit `SYNTHETIC` provenance and routes use derived provenance.
- [CODE] Integrated the generated population through the existing SQLite
  repository and `RuntimeDataset`. The active runtime filters to canonical Asia
  rows while retaining old local master rows outside the active query for
  compatibility/history.
- [TOOL] Dataset validation reports one connected component and 215 shipments
  with alternative feasible baseline paths. Backend tests passed: 71; compile
  checks and `git diff --check` passed; frontend production build passed.
- [TOOL] Scenario evidence: Singapore closure 29 reroute-required/29
  recommendations; Port Klang closure 8/8; Port Klang congestion 8 at-risk/0
  recommendations; critical capacity reduction 1/1. Docker remains UNCONFIRMED
  because the local Docker Desktop Linux engine was unavailable.

## Default Network Map Edge Visibility

- Date: 2026-09-19T00:00:00+08:00
- Local issue: `ISS-0040`
- [USER] Requested that the default network map show nodes without route edges,
  while retaining edges for planned routes and related disruption/rerouting
  tasks.
- [CODE] Updated `frontend/src/App.jsx` to render route polylines and their
  legend only when a route plan or applied disruption context is active.
  Location markers and the route layer control remain unchanged.
- [TOOL] Vite production build and `git diff --check` passed.

## Agent-Ready Backend Foundation and Minimal Supervisor

- Date: 2026-09-20T00:00:00+08:00
- Local issue: `ISS-0041`
- [USER] Requested a trusted-tool boundary and one minimal Supervisor Agent
  without moving disruption policy, network state, impact detection, routing,
  scoring, or hard validation into an LLM.
- [CODE] Added structured Pydantic agent contracts, trusted operational tools,
  bounded Supervisor orchestration, and `IncidentState`. Added `POST /supervisor`
  as an ID-oriented natural-language path; dashboard APIs remain direct.
- [CODE] Extracted `backend/app/simulation_service.py`; dashboard simulation and
  Supervisor simulation now share `run_simulation()` and persist scenario state
  without mutating canonical network records.
- [TOOL] Full backend suite passed with 81 tests, backend/dashboard compilation,
  frontend production build, and `git diff --check`. Direct and Supervisor
  Singapore closure simulations both identified 29 affected shipments and left
  the base route API unchanged.
- [ASSUMPTION] `/assistant` keeps its transitional browser-context behavior for
  unsaved dashboard plans; `/supervisor` is the new server-grounded agent path.

## Active Shipment Status and Reroute Options

- Date: 2026-09-20T00:00:00+08:00
- Local issue: `ISS-0042`
- [USER] Reported inconsistent affected-shipment statuses and requested current
  active shipments only plus all reroute options.
- [CODE] Updated the dashboard to use server-produced shipment impact results,
  exclude `COMPLETED`, `DELIVERED`, and `CANCELLED` shipments, filter by the
  operational shipment status, and display reroute outcomes separately.
- [CODE] Shipment impact analysis now renders every candidate route returned by
  the deterministic rerouting service and marks the selected candidate.
- [CODE] The affected-shipment panel is now explicitly a reroute queue: it
  includes only `REROUTED` and `NO_FEASIBLE_ROUTE` recommendations, and its
  disrupted-shipment KPI uses the same set so the count matches the table.
- [CODE] Restricted that panel's status filter to `REROUTED` and
  `NO_FEASIBLE_ROUTE`; lifecycle statuses remain display-only details.
- [CODE] Removed the `Recommended action`, `Risk warning`, and `Next steps`
  blocks from shipment impact analysis; route evidence and metrics remain.
- [TOOL] 81 backend tests, Python compilation, and the frontend production build
  passed. The first frontend build hit the local sandbox `spawn EPERM` process
  restriction and passed on the approved retry.

## External Signal Foundation and Network Exposure

- Date: 2026-09-26
- Local issue: `ISS-0043`
- [USER] Requested Phase 4.1 as a provider-independent evidence-to-exposure
  foundation, explicitly stopping before policy effects, graph changes, or
  rerouting. Open-Meteo, GDELT, and other live providers remain deferred.
- [CODE] Added structured `ExternalSignal`, future-only `OperationalEffect`,
  curated `NetworkZone` corridor/chokepoint metadata, route corridor IDs, and
  representative five-point maritime samples. Route metadata is retained by
  the canonical `Route` model and additive SQLite JSON columns.
- [CODE] Added deterministic direct location/route/corridor matching, haversine
  sample-point matching, inclusive temporal overlap with open-ended signal
  support, remaining-leg traversal estimates, and structured shipment exposure.
  Exposure is separate from operational impact classifications and does not
  mutate NetworkX or canonical shipment/route state.
- [CODE] Added `GET /network/corridors`, `POST /external-signals/network-match`,
  and `POST /external-signals/exposure`; signals are evaluated in memory and
  are not persisted in this phase. Added US-0005 and Phase 4.1 documentation.
- [TOOL] 93 backend tests, Python compilation, `git diff --check`, and the
  frontend production build passed. The first frontend build required the
  approved retry because sandboxed Vite/esbuild spawning returned `spawn EPERM`.
  Runtime demos matched Singapore, two CHK_SUEZ routes, and one near marine
  sample route; completed Suez legs were excluded.
- [ASSUMPTION] Corridor membership is curated supply-chain metadata; maritime
  samples are representative exposure points rather than navigation tracks;
  traversal windows fall back to deterministic planned/ETA/route-duration
  approximations until reviewed provider or tracking data is integrated.

## Open-Meteo Raw Weather Provider Foundation

- Date: 2026-09-26
- Local issue: `ISS-0044`
- [USER] Requested Phase 4.2A to retrieve and preserve raw Open-Meteo Forecast
  and Marine data for existing SEA route sample points, explicitly stopping
  before weather scoring, ExternalSignal conversion, NetworkState changes, or
  rerouting.
- [CODE] Added the isolated `backend/app/integrations/weather/` provider layer:
  typed request/response contracts and provider errors, bounded `httpx` retry
  behavior, UTC request metadata, five-point batching, local file cache with
  fresh/stale/miss semantics, immutable `forecast.json`, `marine.json`, and
  `metadata.json` snapshots, and the optional summary-only debug endpoint.
- [CODE] Added opt-in Open-Meteo settings and raw-data/deployment/security/
  architecture documentation. No weather data is converted into an
  `ExternalSignal`, operational effect, risk score, route penalty, graph state,
  shipment state, or reroute.
- [TOOL] 105 backend tests, Python compilation, `git diff --check`, and the
  frontend production build passed. The optional live smoke succeeded for
  `ASIA_R_0056` with five requested points and both provider APIs; snapshot
  written under `data/raw/weather/open_meteo/20260926T102521544271Z/`. A repeat
  smoke returned Forecast/Marine cache `HIT` and wrote no second snapshot.
- [ASSUMPTION] The provider is disabled by default; local cache and snapshot
  retention are MVP defaults. Phase 4.2B should normalize raw hourly values and
  align them with existing deterministic traversal windows before creating
  weather signals.
