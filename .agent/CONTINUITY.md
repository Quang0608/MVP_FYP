# Agent Continuity

Canonical compact briefing for AI agents. Read this file together with
`docs/CONTINUITY.md` before acting.

## [PLANS]

- 2026-07-26T17:18:58+08:00 [USER] Use local issue files, local verification, and
  a local demo as mandatory gates before any GitHub push.
- 2026-07-26T17:18:58+08:00 [USER] Maintain project guidance, technical docs,
  continuity, and structured user stories in the repository.

## [DECISIONS]

- 2026-07-26T17:18:58+08:00 [USER] GitHub is a publication destination, not the
  active issue tracker for current development.
- 2026-07-26T17:18:58+08:00 [CODE] Canonical documentation filenames use uppercase
  topic names under `docs/`.
- 2026-07-26T17:18:58+08:00 [CODE] Local issues live under `docs/issues/` and user
  stories under `docs/user-stories/`.

## [PROGRESS]

- 2026-07-26T17:18:58+08:00 [TOOL] Initial review completed: 11 tests passed and
  Python compilation succeeded before the documentation workflow was introduced.
- 2026-07-26T17:55:09+08:00 [CODE] ISS-0007 replaced new writes to the single
  JSON `runs` table with structured location, route, shipment, disruption,
  simulation-run, and agent-decision persistence.
- 2026-07-26T17:55:09+08:00 [TOOL] Structured persistence verification passed:
  12 tests, compilation, an isolated Singapore backend workflow, and dashboard
  HTTP 200.
- 2026-08-14T00:00:00+08:00 [USER] Replace the Streamlit frontend with React
  while preserving the FastAPI deterministic routing contracts.
- 2026-08-14T00:00:00+08:00 [USER] Reported React development-server `OPTIONS`
  requests receiving FastAPI `405 Method Not Allowed` responses.

## [DISCOVERIES]

- 2026-07-26T17:18:58+08:00 [CODE] Known gaps include container dashboard
  connectivity, missing no-key LLM fallback, incomplete grounding validation,
  incomplete evaluation metrics, text encoding corruption, and weak assertions.
- 2026-07-26T17:55:09+08:00 [CODE] Legacy `runs` rows remain readable and are
  copied on reroute; bulk conversion and rollback require a future migration
  framework.
- 2026-08-14T00:00:00+08:00 [CODE] Added a Vite React frontend under `frontend/`
  with an SVG network view, route planning, batch rerouting, metrics, and
  shipment analytics actions. Compose serves the static app with Nginx and
  proxies `/api` to the backend service.
- 2026-08-14T00:00:00+08:00 [CODE] Added explicit non-credentialed FastAPI CORS
  middleware configured by `CORS_ORIGINS` for local React and Compose origins.
- 2026-08-14T00:00:00+08:00 [CODE] Added React map wheel zoom, zoom controls,
  reset, and pointer drag-to-pan behavior in `NetworkMap`.
- 2026-08-14T00:00:00+08:00 [CODE] Replaced the abstract map with a Leaflet
  OpenStreetMap basemap, coordinate-based markers, tooltips, and route overlays.
- 2026-08-14T00:00:00+08:00 [CODE] Added reviewed feature backlog issues
  `ISS-0012` through `ISS-0015` for operator filtering, custom disruptions,
  capacity visualization, and scenario comparison/export.
- 2026-08-15T00:00:00+08:00 [USER] Recreate the supplied dashboard design and ensure
  the React frontend and FastAPI backend work together across all local features.
- 2026-08-15T00:00:00+08:00 [CODE] Added `ISS-0016` and rebuilt the React client as
  a dark operations command center with map, assistant, disruption, shipment,
  capacity, comparison, history, and export workspaces.
- 2026-08-15T00:00:00+08:00 [CODE] Added a labeled `offline_deterministic`
  explanation fallback for no-key local operation and exposed structured
  disruption inputs in recommendation history.
- 2026-08-15T00:00:00+08:00 [USER] Requested the AI Assistant and Rerouting Summary
  dashboard panels swap positions.
- 2026-08-15T00:00:00+08:00 [CODE] Completed `ISS-0017`: Rerouting Summary now sits
  beside the map and AI Assistant occupies the first lower content-row slot.
- 2026-08-15T00:00:00+08:00 [USER] Requested before/after route analysis and a
  readable summary for one selected affected shipment.
- 2026-08-15T00:00:00+08:00 [CODE] Completed `ISS-0018`: affected-shipment detail
  now renders original and selected route snapshots, metric deltas, grounded
  summary/reasoning, action, warning, and next steps.
- 2026-08-15T00:00:00+08:00 [USER] Reported that interactive planning stopped working.
- 2026-08-15T00:00:00+08:00 [CODE] Completed `ISS-0019`: provider connection and
  timeout failures now preserve deterministic route results with a labeled
  `offline_deterministic` explanation; auth/configuration failures remain explicit.
- 2026-08-15T00:00:00+08:00 [USER] Requested a focused origin-to-destination map after
  planning and the current AI recommendation directly below the route search bar.
- 2026-08-15T00:00:00+08:00 [CODE] Completed `ISS-0020`: the planned map now shows
  only the selected route path, and the planner plus assistant are adjacent near
  the top of the dashboard.
- 2026-08-15T00:00:00+08:00 [USER] Requested route disruption explanations and
  alternatives, staged multi-disruption activation, and an interactive assistant
  grounded in current dashboard context.
- 2026-08-15T00:00:00+08:00 [CODE] Completed `ISS-0021`: added `POST /assistant`,
  deterministic chat fallback, multi-disruption selection/combination, explicit
  Run selected disruption behavior, and route/no-route recommendation messaging.
- 2026-08-15T00:00:00+08:00 [USER] Requested larger dashboard text, assistant chat
  above Current Recommendation, and shipment-style interactive route analysis
  with all available route alternatives.
- 2026-08-15T00:00:00+08:00 [CODE] Completed `ISS-0022`: added readability
  overrides, separated assistant chat from recommendation content, and added
  before/after plus all-candidate interactive route analysis.

## [OUTCOMES]

- 2026-07-26T17:18:58+08:00 [CODE] Project-local workflow and documentation
  structure created. Implementation issues remain in the local backlog.
- 2026-07-26T17:18:58+08:00 [TOOL] All project-local Markdown links resolved and
  `git diff --check` reported no content errors.
- 2026-07-26T17:55:09+08:00 [CODE] ISS-0007 completed locally. Runtime graph
  calculations remain deterministic and in-memory; the LLM does not select routes.
- 2026-08-14T00:00:00+08:00 [TOOL] React production build, frontend HTTP smoke
  check, backend tests, compilation, Compose config resolution, and an isolated
  Singapore closure workflow passed. Docker image build is UNCONFIRMED because
  the local Docker Desktop Linux engine was unavailable.
- 2026-08-14T00:00:00+08:00 [TOOL] CORS regression coverage passed with 13 backend
  tests and backend compilation; allowed and unlisted origins were verified.
- 2026-08-14T00:00:00+08:00 [TOOL] React production build passed after the
  interactive map update.
- 2026-08-14T00:00:00+08:00 [TOOL] Geographic basemap dependencies installed and
  the React production build passed; browser tile loading depends on network access.
- 2026-08-14T00:00:00+08:00 [TOOL] Project review completed without application
  code changes; four focused local feature proposals were added to `docs/issues/`.
- 2026-08-15T00:00:00+08:00 [TOOL] Dashboard integration verification passed: 15 backend
  tests, backend/dashboard compilation, React production build, frontend HTTP
  preview 200, and an isolated Singapore closure workflow with 15 affected and
  13 rerouted shipments.
- 2026-08-15T00:00:00+08:00 [TOOL] `npm run build` passed after the panel-order change;
  backend contracts and routing behavior were unchanged.
- 2026-08-15T00:00:00+08:00 [TOOL] `npm run build` and a no-key shipment analytics
  workflow passed after adding the before/after analysis view.
- 2026-08-15T00:00:00+08:00 [TOOL] 16 backend tests passed and the exact current-config
  Singapore plan request returned HTTP 200 with `ROUTE_FOUND` after provider
  resilience was added.
- 2026-08-15T00:00:00+08:00 [TOOL] React build, 16 backend tests, compilation, and
  diff check passed after the focused route-map change.
- 2026-08-15T00:00:00+08:00 [TOOL] 17 backend tests, React build, compilation, and
  combined-disruption plus assistant endpoint smoke checks passed.
- 2026-08-15T00:00:00+08:00 [TOOL] 17 backend tests, React build, compilation, and
  diff check passed after the readable assistant and route-analysis update.
- 2026-08-15T00:00:00+08:00 [USER] Requested consolidation of duplicate interactive
  route answers, with the before/after comparison in Current Recommendation.
- 2026-08-15T00:00:00+08:00 [CODE] Completed ISS-0023: Current Recommendation
  now owns the single before/after comparison; standalone InteractiveRouteAnalysis
  is no longer rendered while Route Comparison retains alternatives directly
  below the recommendation.
- 2026-08-15T00:00:00+08:00 [TOOL] 17 backend tests, React build, compilation, and
  diff check passed after recommendation consolidation.
- 2026-08-15T00:00:00+08:00 [USER] Requested removal of the Performance Overview
  panel below the affected-shipments workflow.
- 2026-08-15T00:00:00+08:00 [CODE] Removed the rendered Performance Overview panel
  and its sidebar navigation entry.
- 2026-08-15T00:00:00+08:00 [USER] Requested unaffected interactive routes to show
  only the original route and single-alternative plans to avoid a duplicate
  alternative section.
- 2026-08-15T00:00:00+08:00 [CODE] Interactive route results now hide redundant
  after/alternative output for unaffected original routes and hide Route Comparison
  when exactly one feasible candidate is returned.
- 2026-08-15T00:00:00+08:00 [TOOL] 17 backend tests, backend/dashboard compilation,
  React production build, and diff check passed after the interactive result update.
- 2026-08-23T00:00:00+08:00 [USER] Requested an extensible raw-to-canonical data
  directory, sample contracts, validation models, and placeholder source pipeline
  modules without external downloads or full external-data integration.
- 2026-08-23T00:00:00+08:00 [CODE] Added `data/` raw-source folders, processed and
  mapping documentation, canonical JSON schemas, internally consistent synthetic
  samples, and `backend/data_pipeline/` ingestion/normalization interfaces.
- 2026-08-23T00:00:00+08:00 [CODE] Added Pydantic canonical models with coordinate,
  numeric, timestamp, and cross-entity reference validation in `ISS-0024`.
- 2026-08-23T00:00:00+08:00 [TOOL] `ISS-0024` passed 20 backend tests, 3 focused
  pipeline tests, backend/dashboard compilation, 8 JSON schema parse checks,
  isolated health/route API smoke, and `git diff --check`.
- 2026-08-23T00:00:00+08:00 [USER] Uploaded a WPI raw CSV and requested a canonical
  port table with WPI identifiers, names, country, UN/LOCODE, coordinates, and
  fixed PORT/WPI metadata.
- 2026-08-23T00:00:00+08:00 [CODE] Added `normalize_wpi.py`, a canonical ports
  schema, WPI processed-data documentation, and generated
  `data/processed/wpi/ports.parquet` from 3,802 raw records.
- 2026-08-23T00:00:00+08:00 [TOOL] `ISS-0025` passed 21 backend tests, compilation,
  Parquet output inspection, and `git diff --check`.
- 2026-08-23T00:00:00+08:00 [USER] Requested the official IMF PortWatch daily port and
  checkpoint ingestion, WPI mapping, canonical Parquet outputs, and current-state
  derivation without rerouting or Kafka integration.
- 2026-08-23T00:00:00+08:00 [CODE] Added the `backend/data_pipeline/portwatch/`
  client, dated raw ingestion CLIs, WPI/checkpoint mapping, normalizers, quality
  reports, validation models, and configurable state builders.
- 2026-08-23T00:00:00+08:00 [TOOL] `ISS-0026` passed 24 backend tests, compilation,
  12 JSON schema checks, CLI help checks, and `git diff --check` using offline
  ArcGIS-shaped fixtures; no live download was run automatically.
- 2026-08-23T17:00:56+08:00 [USER] Requested live PortWatch port ingestion for
  2026-08-10 through 2026-08-16 followed by normalization.
- 2026-08-23T17:00:56+08:00 [TOOL] Live PortWatch ingestion saved 10,325 records
  across 11 pages. Normalization produced 5,300 matched rows, reported 1,005
  unresolved source ports and two missing dates, and current-state processing
  wrote 1,059 canonical location rows.
- 2026-08-23T17:15:00+08:00 [USER] Requested country-independent similar-name
  PortWatch matching and reprocessing of the existing August 10-16 extraction.
- 2026-08-23T17:15:00+08:00 [CODE] ISS-0027 changed mapping to manual override,
  exact normalized name, and conservative fuzzy name matching with a recorded
  similarity score; country is audit-only.
- 2026-08-23T17:15:00+08:00 [TOOL] Reprocessing produced 5,625 canonical rows,
  1,125 matched source ports, 940 unresolved source ports, and 1,121 current
  state locations. August 15-16 remain absent in the raw response. Full tests
  (25), compilation, and diff check passed.
- 2026-08-23T22:26:00+08:00 [USER] Requested WPI primary port name plus WPI Country
  Code matching against PortWatch portname and country.
- 2026-08-23T22:26:00+08:00 [CODE] ISS-0028 superseded the name-only fuzzy
  resolver with exact normalized name-plus-country matching. WPI Country Code
  values are country names in the uploaded source; PortWatch ISO3 remains audit
  metadata only.
- 2026-08-23T22:26:00+08:00 [TOOL] Reprocessing produced 5,300 canonical rows,
  1,060 matched source ports, 1,005 unresolved source ports, and 1,059 current
  state locations. August 15-16 remain absent in the raw response. Full tests
  (25), compilation, and diff check passed.
- 2026-08-23T22:45:00+08:00 [USER] Requested a separate persistent WPI-PortWatch
  mapping table, mapping logic at build time only, and a numbered hard-case
  confirmation list.
- 2026-08-23T22:45:00+08:00 [CODE] ISS-0029 added the persistent mapping builder,
  review queue, source-ID-only normalization, and mapping status handling.
- 2026-08-23T22:45:00+08:00 [TOOL] Built 2,065 mapping rows: 1,136 automatic and
  929 review/unmapped. Reprocessing produced 5,680 canonical rows and 1,135
  current-state locations. Full tests (25), compilation, and diff check passed.
- 2026-08-23T22:50:00+08:00 [CODE] Added observed safe aliases for Netherlands,
  Saint/St country labels, Virgin Islands, Hong Kong/Macao, Taiwan, and Congo
  variants; conflicting same-name ports remain in review.
- 2026-08-23T22:50:00+08:00 [TOOL] Final persistent mapping has 1,158 automatic
  rows and 907 review/unmapped rows. Normalization produced 5,790 rows and
  current state for 1,157 locations.
- 2026-08-23T23:10:00+08:00 [USER] Requested historical PortWatch baselines,
  daily activity features, current activity state, and route-impact hooks.
- 2026-08-23T23:10:00+08:00 [CODE] ISS-0030 added configurable baseline,
  day-over-day feature, anomaly, and activity-status processing plus a
  NetworkX state-annotation and flagged-shipment helper. Route weights remain
  unchanged.
- 2026-08-23T23:10:00+08:00 [TOOL] Generated 5,790 feature rows, 1,157
  baselines, and 1,157 current port states for 2026-08-10 through 2026-08-14;
  all baselines are LIMITED_HISTORY. Full tests (27), compilation, and diff
  check passed.
- 2026-08-23T23:45:00+08:00 [USER] Requested the PortWatch disruption ingestion,
  canonical normalization, affected-WPI-port relations, and current active
  disruption state pipeline without rerouting integration.
- 2026-08-23T23:45:00+08:00 [CODE] ISS-0031 added the official PortWatch
  disruption ArcGIS client, immutable retrieval snapshots, event-ID merge/update
  normalization, WPI affected-port mapping, current-state derivation, canonical
  validation, and ImpactDetectionService-facing state loading.
- 2026-08-23T23:45:00+08:00 [TOOL] Disruption fixtures passed source snapshot,
  normalization, mapping, active-date, update, and impact-state checks. Full
  suite passed with 30 tests; compilation and diff check passed. No live
  disruption download was run automatically.
- 2026-08-24T00:06:00+08:00 [USER] Requested live ingestion and processing of
  PortWatch disruptions beginning in 2026.
- 2026-08-24T00:06:00+08:00 [TOOL] Official API ingestion saved one immutable
  snapshot with 7 records. Normalization produced 7 events; mapping resolved
  16 WPI relations and reported 27 unresolved tokens. One event is active as
  of 2026-08-24T00:00:00Z. Full tests (30), compilation, and diff check passed.

- 2026-08-30T00:00:00+08:00 [USER] Requested a multi-source port master so WPI
  remains preferred without discarding valid PortWatch-only ports, including
  source-native ports such as Nakagusukuwan.
- 2026-08-30T00:00:00+08:00 [CODE] Completed `ISS-0032`: added unified
  `port_master`, `canonical_ports`, `network_ports`, and `active_route_ports`
  outputs; source-native records use `PW_PORT_<portid>` and
  `mapping_status=SOURCE_NATIVE`.
- 2026-08-30T00:00:00+08:00 [CODE] PortWatch monitoring now resolves only from
  the persistent master mapping, retains source-native observations, and keeps
  source provenance in `port_monitoring_source_links.parquet` when canonical
  daily rows are aggregated.
- 2026-08-30T00:00:00+08:00 [CODE] Disruption relations now retain canonical
  source-native affected ports and readable source names; checkpoint token
  `chokepoint6` remains reported as unresolved rather than being forced into a
  port ID.
- 2026-08-30T00:00:00+08:00 [TOOL] Live rebuild produced 4,709 canonical ports,
  10,320 monitoring rows, 42 resolved disruption relations, one unresolved
  checkpoint token, and one active disruption as of 2026-08-30.
- 2026-08-30T00:00:00+08:00 [USER] Requested Phase 1 integration of PortWatch and
  WPI into the live SQLite/NetworkX application.
- 2026-08-30T00:00:00+08:00 [CODE] Completed `ISS-0033`: added the read-only
  `PortWatchAdapter`, runtime-to-canonical mapping for the synthetic ports,
  PortWatch state graph overlay, location metadata, and clean state/disruption
  endpoints.
- 2026-08-30T00:00:00+08:00 [TOOL] `P_SG` now returns canonical ID
  `PW_PORT_port1201`, PortWatch source, latest observation `2026-08-14`,
  activity `1.0`, and `HIGH_ACTIVITY`; 34 tests and the frontend build passed.
- 2026-08-30T00:00:00+08:00 [USER] Requested Phase 2 PortWatch disruption
  impact detection against active shipment remaining routes without automatic
  rerouting.
- 2026-08-30T00:00:00+08:00 [CODE] Completed `ISS-0034`: added
  `ImpactDetectionService`, canonical-to-runtime disruption resolution,
  remaining-route intersection evidence, and `GET /portwatch/impacts`.
- 2026-08-30T00:00:00+08:00 [TOOL] Four critical impact cases and the full
  verification suite passed with 38 backend tests. The live current snapshot
  returned no impacts because its active event affects unresolved checkpoint
  `chokepoint6`, not a runtime port.
- 2026-09-06T00:00:00+08:00 [USER] Requested an architecture stabilization pass
  centered on shipment ownership, deterministic boundaries, graph isolation,
  source-of-truth documentation, and a prioritized refactor plan.
- 2026-09-06T00:00:00+08:00 [CODE] Completed `ISS-0035`: graph construction now
  deep-copies domain state per NetworkX scenario; added `backend/app/graph.py`,
  an identifier-aware assistant context boundary, architecture/refactor docs,
  and frontend decomposition/obsolete inventory documentation.
- 2026-09-06T00:00:00+08:00 [TOOL] 43 backend tests, backend/dashboard
  compilation, `git diff --check`, React production build, and the isolated
  Singapore closure workflow passed. Docker remains UNCONFIRMED because the
  Docker Desktop Linux engine pipe is unavailable.
- 2026-09-07T00:00:00+08:00 [USER] Requested Phase 2 canonical runtime data
  integration with SQLite retained, shipment route-leg progress, WPI-preferred
  identity, and no new infrastructure or dashboard features.
- 2026-09-07T00:00:00+08:00 [CODE] Completed `ISS-0036`: added source-neutral
  runtime domain models and `RuntimeDataset`; converted synthetic seed and
  SQLite loading; added canonical port-master adaptation; kept API DTOs and
  legacy persistence compatibility at explicit boundaries.
- 2026-09-07T00:00:00+08:00 [CODE] Corrected repository leg-progress derivation
  so every leg before the current leg is `COMPLETED`, the active leg is
  `CURRENT`, and future legs are `PLANNED`.
- 2026-09-07T00:00:00+08:00 [TOOL] 51 backend tests, backend/dashboard
  compilation, React production build, `git diff --check`, and isolated
  Singapore closure verification passed. Docker remains UNCONFIRMED because
  the Docker Desktop Linux engine pipe is unavailable.
- 2026-09-13T00:00:00+08:00 [USER] Requested Phase 3 dynamic network state and
  deterministic disruption policy, with no new infrastructure or product area.
- 2026-09-13T00:00:00+08:00 [CODE] Added `disruption_policy.py`,
  `network_state.py`, and `impact.py`; canonical simulated and PortWatch events
  now project into scenario-only network state and classify shipments from
  current/remaining route legs.
- 2026-09-13T00:00:00+08:00 [TOOL] Full backend suite passed with 63 tests,
  backend/dashboard compilation and `git diff --check` passed, and the frontend
  production build passed. Closure, congestion, and capacity endpoint demos
  passed with deterministic classifications and reroute counts. Docker remains
  UNCONFIRMED because the Docker Desktop Linux engine pipe is unavailable.
- 2026-09-13T00:00:00+08:00 [USER] Requested a focused dashboard layout/text
  adjustment: place the AI assistant beside affected shipments and remove
  redundant route/context display text.
- 2026-09-13T00:00:00+08:00 [CODE] Completed `ISS-0038`; the existing assistant
  panel now occupies the third column beside the affected shipments table, with
  chat behavior unchanged and the requested text removed.
- 2026-09-13T00:00:00+08:00 [TOOL] Frontend Vite production build and
  `git diff --check` passed.
- 2026-09-13T00:00:00+08:00 [USER] Requested the existing AI insight content be
  moved into Rerouting Summary and the Recent AI Insights title be removed.
- 2026-09-13T00:00:00+08:00 [CODE] Consolidated the insight list into
  `ReroutingSummary`; removed the separate `InsightsPanel` and title without
  changing insight data generation.
- 2026-09-13T00:00:00+08:00 [TOOL] Frontend Vite production build passed after
  the consolidation.
- 2026-09-13T00:00:00+08:00 [USER] Requested Phase 4 Asia network and synthetic
  shipment population expansion without changing disruption policy, routing,
  assistant architecture, or adding external infrastructure.
- 2026-09-13T00:00:00+08:00 [CODE] Added the reproducible Asia generator and
  repository integration: 51 canonical WPI ports, 12 factories, 14 warehouses,
  14 customers, 150 routes, 220 shipments, and 1,000 ordered legs using seed
  `20260913`. The active runtime uses SQLite canonical records; old compatibility
  rows remain outside the active Asia query.
- 2026-09-13T00:00:00+08:00 [TOOL] 71 backend tests, backend/dashboard compile,
  frontend production build, and diff checks passed. Scenario checks passed for
  Singapore closure, Port Klang closure, congestion, and capacity reduction.
- 2026-09-19T00:00:00+08:00 [USER] Requested default network map node-only
  rendering, with route edges retained for route planning and related tasks.
- 2026-09-19T00:00:00+08:00 [CODE] Updated `NetworkMap` so idle mode hides route
  polylines and line legend entries; route plans and applied disruptions retain
  route visibility.
- 2026-09-19T00:00:00+08:00 [TOOL] Frontend production build and diff checks
  passed.
- 2026-09-20T00:00:00+08:00 [USER] Requested Phase 3.5: trusted tools, server-grounded
  agent context, one bounded Supervisor, and no LLM operational authority.
- 2026-09-20T00:00:00+08:00 [CODE] Added `agent/schemas.py`, trusted tool
  operations, `agent/supervisor.py`, `POST /supervisor`, structured
  `IncidentState`, and shared `simulation_service.py` used by dashboard and
  agent simulation paths.
- 2026-09-20T00:00:00+08:00 [TOOL] 81 backend tests, compile checks, frontend
  production build, and diff checks passed. Direct and Supervisor Singapore
  closure paths each identified 29 affected shipments; base routes stayed
  unchanged.
- 2026-09-20T00:00:00+08:00 [USER] Reported inconsistent affected-shipment
  statuses and requested current active shipments only plus all reroute options.
- 2026-09-20T00:00:00+08:00 [CODE] Completed `ISS-0042`: the dashboard now
  derives affected rows from persisted impact classifications, excludes inactive
  shipments, exposes all supported status filters, keeps lifecycle status
  separate from reroute result, and renders every deterministic candidate route.
- 2026-09-20T00:00:00+08:00 [CODE] Refined the affected-shipment panel into a
  reroute queue containing only `REROUTED` and `NO_FEASIBLE_ROUTE` results; the
  disrupted KPI now uses the same queue count.
- 2026-09-20T00:00:00+08:00 [CODE] Restricted the affected-shipment filter
  itself to `REROUTED` and `NO_FEASIBLE_ROUTE`; lifecycle status is display-only.
- 2026-09-20T00:00:00+08:00 [CODE] Removed recommendation action, risk warning,
  and next-steps content from shipment impact analysis per user request.
- 2026-09-20T00:00:00+08:00 [TOOL] 81 backend tests, Python compilation, and
  frontend production build passed; the first build required an approved retry
  because sandboxed Vite/esbuild process spawning returned `spawn EPERM`.

- 2026-09-26T00:00:00+08:00 [USER] Requested Phase 4.1 external signal
  foundation and provider-independent network/shipment exposure without live
  provider ingestion, operational effects, or rerouting.
- 2026-09-26T00:00:00+08:00 [CODE] Added `backend/app/external_state/` with
  `ExternalSignal`, `OperationalEffect`, curated corridors, deterministic
  route sample-point matching, temporal windows, and exposed shipment-leg
  evidence. Added additive SQLite route metadata for corridor IDs and maritime
  sample points plus `GET /network/corridors` and debug exposure endpoints.
- 2026-09-26T00:00:00+08:00 [TOOL] `ISS-0043` passed 93 backend tests,
  compilation, diff check, frontend production build after the approved
  sandbox retry, and Singapore/CHK_SUEZ/coordinate synthetic exposure demos.
- 2026-09-26T00:00:00+08:00 [ASSUMPTION] Corridor memberships are curated
  supply-chain metadata; maritime sample points are representative exposure
  points, and traversal windows are deterministic approximations rather than
  live navigation or AIS data.
- 2026-09-26T00:00:00+08:00 [USER] Requested Phase 4.2A as an isolated
  Open-Meteo Forecast/Marine raw-provider foundation below the ExternalSignal
  boundary, with no weather scoring, graph effects, signal conversion, or
  rerouting.
- 2026-09-26T00:00:00+08:00 [CODE] Completed ISS-0044 with explicit opt-in
  settings, `OpenMeteoClient`, typed errors, UTC request windows, five-point
  route batching, validated raw responses, file cache with explicit stale
  status, immutable raw snapshots, a summary-only debug endpoint, and an
  optional live smoke command. No routing, NetworkState, shipment, or LLM
  behavior was changed.
- 2026-09-26T00:00:00+08:00 [TOOL] 105 backend tests, Python compileall,
  `git diff --check`, and frontend production build passed. The optional live
  smoke succeeded for `ASIA_R_0056`: five points, Forecast OK, Marine OK, and
  snapshot `data/raw/weather/open_meteo/20260926T102521544271Z/`.
- 2026-09-26T00:00:00+08:00 [ASSUMPTION] Open-Meteo raw retrieval is disabled
  by default and cache/snapshot retention is local MVP behavior. Normalization,
  weather ExternalSignal creation, time-aligned observation logic, and policy
  effects remain deferred to Phase 4.2B/4.3.
