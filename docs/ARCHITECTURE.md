# Architecture

## Purpose and current boundary

This repository is a local research MVP. It is shipment-centric: a disruption
is evaluated against a shipment's current and remaining planned route, feasible
alternatives are calculated deterministically, and the resulting recommendation
may be explained by an optional provider or a deterministic offline fallback.

The implemented flow is:

```text
WPI / PortWatch raw data
        -> data_pipeline normalization and validation
        -> data/processed CSV and Parquet artifacts

SQLite runtime records
        -> Pydantic domain objects
        -> canonical disruption facts
        -> deterministic disruption policy
        -> transient network-state overlay
        -> isolated transient NetworkX scenario graph
        -> remaining-leg impact classification
        -> deterministic routing, capacity reservation, and scoring
        -> persisted simulation/recommendation records
        -> optional grounded explanation / assistant response
        -> React dashboard
```

Natural-language assistant requests take an additional path:

```text
Natural-language request
        -> bounded Supervisor Agent
        -> validated trusted tool
        -> same deterministic repository/service boundary
        -> structured result
        -> grounded explanation
```

Dashboard buttons do not pass through the Supervisor. They call the deterministic
API endpoints directly. The Supervisor is an orchestration interface, not a
second operational engine.

PortWatch and WPI supply facts and state. They do not select routes. NetworkX
exists only for request-scoped graph processing. The LLM receives a backend
decision record or trusted assistant context and cannot select, alter, or
persist a route.

## Current modules

| Responsibility | Current implementation | Boundary status |
|---|---|---|
| API and endpoint orchestration | `backend/app/main.py` | Works, but endpoint composition is too broad |
| Canonical runtime domain models | `backend/app/domain/models.py` | Source-neutral `Location`, `Route`, `Shipment`, `ShipmentRouteLeg`, and `Disruption` records |
| API request/response models | `backend/app/schemas.py`, `backend/app/api/serializers.py` | Legacy HTTP shape is intentionally kept at the boundary |
| Synthetic fixture source | `backend/app/data.py`, `backend/app/asia_dataset.py` | The small fixture remains compatibility data; the active default runtime is the reproducible Asia semi-synthetic population |
| Persistence and queries | `backend/app/repository.py` | `load_runtime_dataset()` is the canonical repository boundary; active `LOC_WPI_*` and `ASIA_*` rows are loaded; legacy `runs` read compatibility remains |
| Disruption normalization and policy | `backend/app/disruption_policy.py` | Converts simulated/external facts to canonical disruptions; owns project-defined numerical assumptions |
| Network-state overlay | `backend/app/network_state.py` | Builds isolated node/edge state without mutating persistent domain records |
| Graph construction and scenario projection | `backend/app/graph.py` | Projects canonical records plus `NetworkState` into an isolated transient graph |
| Impact detection | `backend/app/impact.py`, `backend/app/services.py` | Intersects disruption state with current/remaining shipment legs and classifies actionability |
| Routing, scoring, rerouting | `backend/app/services.py` | Consumes scenario graph and selects alternatives deterministically |
| External PortWatch adapter | `backend/app/integrations/portwatch.py` | Read-only normalized-file boundary |
| Processed port-master adapter | `backend/app/integrations/canonical.py` | Converts usable WPI-preferred/source-native port-master rows to runtime `Location`; rows without geometry remain ingestion artifacts |
| External ingestion/normalization | `backend/data_pipeline/` | Produces artifacts; does not own runtime decisions |
| Asia runtime dataset generation | `backend/app/asia_dataset.py` | Deterministically selects existing canonical ports and derives synthetic enterprise entities, routes, shipments, and ordered legs; it is loaded through SQLite rather than queried by routing |
| Explanation provider and offline fallback | `backend/app/llm.py` | Explanation only; grounding remains incomplete |
| Assistant context boundary | `backend/app/agent/assistant.py` | ID-based server reconstruction available; client context retained only for unsaved plans |
| Trusted agent tools | `backend/app/agent/tools/operations.py`, `backend/app/agent/schemas.py` | Structured read/action wrappers over repository, simulation, impact, routing, and validation services |
| Minimal Supervisor | `backend/app/agent/supervisor.py`, `POST /supervisor` | Bounded tool selection with deterministic offline path; no route or impact calculation in the LLM |
| Shared simulation application service | `backend/app/simulation_service.py` | Dashboard and agent simulation calls share one deterministic implementation |
| Web API client and presentation | `frontend/src/App.jsx` | Single large component module; no routing/business authority |

## Responsibility rules

1. External adapters expose normalized facts and state, with source provenance.
2. Repositories own persistence and queries. `load_runtime_dataset()` returns one
   source-neutral snapshot; API handlers should not construct
   database records directly as the long-term design.
3. `backend/app/domain/models.py` is the runtime domain model. API request/response
   DTOs remain separate compatibility types and are serialized at the HTTP edge.
4. NetworkX graphs are transient scenario projections. `build_supply_chain_graph`
   deep-copies every `Location` and `Route` placed into a graph. A disruption or
   reroute reservation therefore changes only that graph instance.
5. External adapters provide facts and event identity only. `disruption_policy.py`
   maps those canonical events to project-defined network effects; an external
   severity or activity value is not itself a duration or risk penalty.
6. `NetworkStateEngine` owns temporary availability, effective duration, cost,
   risk, capacity, load, and disruption IDs. It does not write those values to
   canonical `Location` or `Route` records.
7. Impact detection inspects current/remaining shipment legs and returns one of
   `UNAFFECTED`, `NETWORK_WARNING`, `SHIPMENT_AT_RISK`, or `REROUTE_REQUIRED`.
   It does not reroute or mutate shipment records.
8. Routing, capacity checks, route reservation order, and scoring are
   deterministic and testable without a network.
9. Recommendations are backend results. The assistant can explain trusted
   results, but never chooses or changes them.
10. React renders API results and gathers user inputs. It must not duplicate
   graph traversal, capacity allocation, route scoring, or disruption decisions.
11. Agents orchestrate trusted tools. Tools validate inputs and call existing
   deterministic services; they do not calculate operational truth themselves.
12. The current Supervisor has a bounded tool-call limit and structured
   `IncidentState`. Future specialist agents must extend this boundary rather
   than create parallel routing or disruption implementations.

## Data ownership and source of truth

| Entity / artifact | Current owner | Current duplication or conflict | Target owner |
|---|---|---|---|
| Locations | SQLite `locations`, loaded as canonical `domain.Location`; Asia ports come from the selected WPI master and enterprise rows are generated | The full WPI/PortWatch master remains in processed Parquet; old synthetic fixture rows remain in existing DBs outside the active query | Canonical operational location table in runtime storage, with WPI/PortWatch provenance |
| Routes | SQLite `routes`, loaded as canonical `domain.Route`; Asia connections are geography-grounded derived estimates | NetworkX holds per-scenario copies of routing state; no separate route file model is used by routing | Canonical operational route table |
| Shipments | SQLite `shipments`, loaded as canonical `domain.Shipment`; enterprise attributes remain controlled synthetic data | No external canonical shipment feed is integrated; the old small fixture remains compatibility-only | Canonical shipment table |
| Shipment route legs | SQLite `shipment_route_legs`, loaded as canonical `domain.ShipmentRouteLeg` with generated explicit progress state | Older rows may lack progress/times and use compatibility derivation | Canonical ordered shipment-leg table with explicit progress fields |
| Manual disruptions | SQLite `disruptions` plus affected-location/route tables, normalized from API request | Built-in definitions in `backend/app/data.py` are request templates, not persisted events | Runtime disruption/event tables with source, target, and lifecycle metadata |
| PortWatch disruptions | Normalized `data/processed/portwatch/*.parquet` through `PortWatchAdapter` | Not yet copied into SQLite runtime disruption tables; unresolved checkpoint tokens remain external evidence only | Ingested canonical disruption tables, retaining immutable source snapshots |
| Simulation history | SQLite `simulation_runs` | Legacy `runs` JSON rows remain readable for compatibility | SQLite/canonical operational simulation history, then an approved migrated store |
| Recommendations / decisions | SQLite `agent_decisions` | Nested route snapshots are duplicated JSON for API compatibility | Relational recommendation records plus immutable route snapshots |
| WPI / PortWatch port master | `data/processed/` Parquet/CSV | Processed artifacts are ingestion inputs; selected WPI-preferred records are copied into the canonical SQLite runtime snapshot | Canonical location ingestion input with explicit provenance and review status |
| NetworkX graph | Per-request memory built from `RuntimeDataset` | Edge scenario state duplicates canonical route facts by design for calculation; it must not be persisted as master data | Remains transient projection |
| LLM output | Optional `agent_decisions.llm_explanation` or response payload | Provider prose is not fully fact-checked | Derived explanation only; deterministic decision record remains authoritative |

The active runtime snapshot is now the generated Asia population: selected
canonical WPI ports plus synthetic enterprise locations, derived routes, and
synthetic shipments. SQLite owns the records consumed by routing. The old small
fixture rows may remain in an existing database for compatibility and history,
but `load_runtime_dataset()` excludes them from the active snapshot. Parquet/CSV
remains an ingestion/processed artifact boundary, not a second routing model.

## Dynamic network state and disruption policy

The Phase 3 boundary is deliberately split into facts, policy, state, impact, and
routing:

| Layer | Responsibility | Must not do |
|---|---|---|
| External facts | PortWatch or simulation input supplies event identity, target, severity, dates, and source | Supply project-specific penalties or select a route |
| Canonical disruption | Normalize both sources to `domain.Disruption` target records | Mutate locations, routes, or shipments |
| Disruption policy | Apply configured closure, shutdown, congestion, and capacity effects | Pretend assumptions are external observations |
| Network state | Hold scenario-only availability and effective edge/node values | Persist temporary values to base tables |
| Impact detection | Intersect state changes with current and remaining shipment legs | Mark all graph descendants as affected |
| Routing | Calculate and rank feasible alternatives on the scenario graph | Reinterpret external facts or ask the LLM to choose |

The current policy assumptions are in `DisruptionPolicyConfig`: congestion uses a
1.5 duration multiplier, adds 0.15 risk, and applies a 1.5 current-load
multiplier; severity-based capacity reductions are 10%, 25%, 50%, and 75% for
LOW, MEDIUM, HIGH, and CRITICAL. These are controlled research assumptions and
must be calibrated or reviewed before being treated as operational forecasts.

| Event type | Target type | Network effect | Impact criteria | Rerouting criteria |
|---|---|---|---|---|
| `PORT_CLOSURE` | Location | Target node and incident edges unavailable | Remaining route contains the node or incident leg | Required when the remaining node/edge is unavailable |
| `ROUTE_CLOSURE` | Route | Target edge unavailable | Remaining legs contain the route | Required when that edge is still remaining |
| `FACTORY_SHUTDOWN` | Location | Factory node and incident edges unavailable | Shipment has not passed the factory | Required when the factory is current/remaining |
| `WAREHOUSE_SHUTDOWN` | Location | Warehouse node and incident edges unavailable | Remaining route requires the warehouse | Required when the warehouse is current/remaining |
| `CONGESTION` | Location or route | Duration/risk/load assumptions increase; edge remains available | Remaining route intersects the target | `SHIPMENT_AT_RISK` while feasible; reroute only if infeasible |
| `CAPACITY_REDUCTION` | Location or route | Effective capacity falls; canonical max capacity is unchanged | Remaining route intersects the target | Required when shipment load no longer fits |

Simulated requests and PortWatch events both enter this pipeline. PortWatch is
not automatically rerouted merely because it reports an event; the same policy
and remaining-leg feasibility criteria must produce `REROUTE_REQUIRED` first.

### Remaining duplicate and legacy paths

| Path | Current purpose | Recommendation | Migration action / reason |
|---|---|---|---|
| `backend/app/schemas.py` `Location`, `Route`, `Shipment` | Legacy HTTP DTO names and response shape | Keep at API edge | Retire only after a versioned API contract or serializers cover all clients |
| `backend/app/schemas.py` `DisruptionRequest` / `Disruption` wrapper plus SQLite association tables | Current multi-target simulation request and persistence compatibility shape | Keep/refactor later | Normalize each target into canonical `domain.Disruption` records during the reviewed disruption-table migration |
| `backend/app/repository.py` `LocationRecord`, `RouteRecord`, `ShipmentRecord` | SQLite compatibility column mappings | Refactor later | Rename columns/add explicit provenance in a reviewed additive migration |
| `backend/app/repository.py` `load_supply_chain_data()` | Tuple compatibility facade used by assistant code | Keep temporarily | Move assistant to `RuntimeDataset` and remove after import-compatibility tests |
| `backend/app/data.py` `planned_route_*` compatibility properties | Synthetic fixture construction and old service callers | Keep/refactor | Generate only `ShipmentRouteLeg` records, then remove list properties after API migration |
| `backend/data_pipeline/validate_data.py` canonical file contracts | Validation of Parquet/CSV ingestion artifacts | Keep as ingestion boundary | Add/maintain explicit adapters into `backend/app/domain`; do not use file models in routing |
| `backend/data_pipeline/normalize_locations.py` | Unimplemented historical normalization placeholder | Refactor or remove in a later ingestion issue | Replace with the tested port-master adapter or remove after dependency search |
| `data/processed/ports/*.parquet` and `data/processed/portwatch/*.parquet` | Reproducible ingestion and processed external facts | Keep read-only | Load reviewed records into SQLite canonical tables in a later migration; do not query them from routing |
| `backend/app/repository.py` `LegacyRunRecord` / `runs` | Read compatibility for pre-ISS-0007 JSON snapshots | Keep and isolate | Validate and migrate old rows transactionally before removal |
| `PROJECT_BRIEF_FOR_CODEX.md` | Historical project brief | Archive/label historical | It documents superseded Streamlit and future infrastructure choices |

## Assistant boundary

`POST /assistant` accepts optional `simulation_run_id`, `disruption_id`, and
`shipment_id`. If a persisted ID is present, `backend/app/agent/assistant.py`
loads the record and reconstructs the assistant context server-side; arbitrary
browser context is ignored. The legacy `context` field remains for an unsaved
interactive plan, where there is no persisted plan identifier yet. This is a
compatibility bridge, not a trusted long-term operational data source.

## Frontend decomposition plan

`frontend/src/App.jsx` currently contains state orchestration, API calls, helper
logic, and all major panels. The UI is intentionally unchanged in this pass.
The later extraction should preserve prop contracts and keep server-owned
decisions visible:

| Planned component area | Current App.jsx responsibilities | Extraction rule |
|---|---|---|
| Dashboard shell | top bar, sidebar, global loading/error state, navigation | Own layout and shared dashboard state only |
| Supply-chain map | `NetworkMap`, map fitting, route overlays, layer toggles | Presentation of locations/routes/plans; no route selection |
| Shipment monitoring | KPI strip, `ShipmentWorkspace`, affected shipment rows | Consume affected shipments and recommendations |
| Disruptions/scenario simulation | `DisruptionPanel`, scenario selection, custom form, run action | Submit backend disruption requests; no local impact calculation |
| Impact analysis | affected shipment detail and route snapshots | Render backend evidence and deltas |
| Route comparison/rerouting | `RoutePlanner`, `RouteComparison`, `ReroutingSummary` | Render candidates/selected route returned by API |
| Analytics | `CapacityPanel`, `RiskCustomers`, `InsightsPanel`, history metrics | Format backend metrics only |
| AI assistant | `AssistantPanel`, chat state, identifier-based request | Send IDs where available; retain context only for unsaved plans |

The first safe frontend follow-up is extracting presentational components without
moving data decisions. Hook/API state should move only after endpoint contracts
are represented by typed client modules and component tests.

## Obsolete and superseded inventory

| Path | Current purpose | Recommendation | Reason |
|---|---|---|---|
| `dashboard/streamlit_app.py` | Former Streamlit dashboard | Remove after current dirty deletion is reviewed | React is the active frontend; the file is already deleted in the pre-existing worktree and is not imported by the API |
| `dashboard/` | Former dashboard directory | Keep empty temporarily; remove directory in a cleanup-only change if tooling permits | Compile command still names it and historical issue evidence references it |
| `PROJECT_BRIEF_FOR_CODEX.md` | Original project brief | Archive/label as historical; do not use as active architecture | It presents Streamlit, Neo4j, and PostgreSQL as active/final choices that contradict the current MVP |
| `docs/DATABASE.md` PostgreSQL/Neo4j planning language | Earlier future-storage description | Refactor/document as deferred | No PostgreSQL/Neo4j adapter is active; the current source of truth is SQLite |
| `NEO4J_*` in `.env.example` | Reserved unused settings | Remove in a later configuration cleanup | Current settings ignore them and no integration consumes them; removal is safe only with an explicit compatibility decision |
| `backend/app/repository.py` legacy `runs` support | Reads/migrates old JSON snapshots | Keep and isolate until migration issue | Existing local databases may depend on it; deleting it would be destructive |
| `docs/issues/ISS-0001`, `ISS-0008` status | Historical implementation issue records | Correct status in a documentation-maintenance issue | Their evidence describes completed local work but statuses remain `IN_PROGRESS`; history should be corrected explicitly |
| `.agent/CONTINUITY.md` and `docs/CONTINUITY.md` | Agent briefing and human handoff | Keep both | They are intentionally separate documents required by project guidance, not accidental duplicates |

No additional obsolete file was removed in this pass. The only code removal
visible in the worktree, `dashboard/streamlit_app.py`, predates this task and is
preserved as a user change.

## External signal exposure boundary

Phase 4.1 adds a provider-independent evidence path:

    ExternalSignal
        -> deterministic network match
        -> temporal match against remaining shipment-leg windows
        -> exposed shipment-leg evidence

The path is implemented in backend/app/external_state/. It supports explicit
location, route, and corridor matches plus coordinate/radius matching against
representative maritime route sample points. It uses current and remaining
shipment legs, so completed legs are excluded.

EXPOSED is intentionally distinct from AT_RISK and REROUTE_REQUIRED. Phase 4.1
does not create NetworkState overlays, apply OperationalEffect, change route
duration/risk/capacity/availability, classify disruption impact, or reroute.
OperationalEffect is a future policy contract for Phase 4.3. No live provider
ingestion or LLM matching exists in this phase.

Corridor memberships are curated supply-chain metadata. Maritime weather sample
points are deterministic exposure samples, not vessel-navigation tracks. When
exact shipment schedules are absent, traversal windows use documented
deterministic fallbacks based on planned times, current ETA, and baseline route
duration.

## Phase 4.2A raw weather provider boundary

Open-Meteo is isolated below the provider-independent signal layer:

```text
SEA Route weather_sample_points
        -> OpenMeteoClient (Forecast + Marine)
        -> validated raw provider response
        -> file cache
        -> immutable raw snapshot
```

`WeatherService` performs one route-level operation. It batches the route's
representative coordinates into provider requests and caches by provider, API,
normalized coordinates, requested variables, and forecast window. It is not
called once per shipment. The five points are geographic exposure samples, not
vessel-navigation tracks.

Fresh cache entries are used without HTTP. Expired entries trigger a provider
request; a typed provider failure may use an explicitly marked stale entry when
one exists. A missing response is never converted into a safe-weather value.
Successful live retrievals are written below
`data/raw/weather/open_meteo/<retrieval>/<route-request>/` as `forecast.json`,
`marine.json`, and `metadata.json`; an existing snapshot is never overwritten.
The optional debug endpoint returns a retrieval summary and snapshot location,
not raw provider payloads to the dashboard or assistant.

Phase 4.2A stops at raw evidence. It does not normalize weather observations,
create weather `ExternalSignal` records, calculate severity or risk, generate
`OperationalEffect`, modify NetworkX or shipment state, or reroute anything.
Those boundaries remain reserved for later phases.
