# Trusted agent tools

Phase 3.5 adds one bounded Supervisor over deterministic backend services. The
Supervisor can interpret a natural-language request and select a tool, but the
tool and the underlying service remain authoritative for operational facts.

Dashboard buttons continue to call the existing deterministic APIs directly.
The agent path is an additional interface, not a replacement for those APIs.

## Tool catalog

| Tool | Input | Output | Underlying service | State effect |
|---|---|---|---|---|
| `get_shipment` | `shipment_id` | `ShipmentSummary` | `load_runtime_snapshot()` / repository | Read-only |
| `get_shipments` | bounded priority/status/origin/destination filters; optional simulation | `ShipmentSummary[]` | repository snapshot and deterministic impact service for affected filtering | Read-only |
| `get_shipment_route` | `shipment_id` | ordered `ShipmentRouteOutput` | canonical shipment route legs | Read-only |
| `get_active_disruptions` | none | `ActiveDisruptionSummary[]` | persisted simulation history and PortWatch adapter | Read-only |
| `get_disruption` | `simulation_run_id` | `SimulationSummary` | `load_simulation_context()` | Read-only |
| `resolve_location` | name or runtime/canonical ID | `LocationResolution` | canonical runtime location snapshot | Read-only |
| `get_simulation` | `simulation_run_id` | `SimulationSummary` | `NetworkStateEngine` and impact service | Read-only |
| `get_scenario_network_summary` | `simulation_run_id` | `SimulationSummary` | scenario network overlay | Read-only |
| `get_affected_shipments` | simulation ID, optional priority/limit | `AffectedShipmentsOutput` | `classify_shipment_impacts()` | Read-only |
| `get_shipment_impact` | shipment ID and simulation ID | `ShipmentImpactOutput` | `classify_shipment_impacts()` | Read-only |
| `get_route_comparison` | shipment ID and simulation ID | baseline/candidate route metrics | `find_candidate_routes()` and `score_routes()` | Read-only |
| `generate_candidate_routes` | shipment ID, simulation ID, bounded constraints | route comparison output | deterministic routing/scoring | Read-only |
| `validate_route_candidate` | shipment ID, simulation ID, ordered route IDs | `ValidationOutput` | `path_result()` and graph state | Read-only |
| `simulate_disruption` | type, target ID, duration, severity | simulation ID and impact counts | `run_simulation()` / `NetworkStateEngine` | Writes simulation history only |

Tool outputs use Pydantic contracts. Raw SQLAlchemy records, NetworkX graphs,
browser context, and unvalidated arbitrary operational values are never exposed
to the Supervisor.

## Supervisor boundary

`POST /supervisor` accepts a natural-language `question` and optional trusted
identifiers. It does not accept arbitrary dashboard context. With no provider
key it uses a bounded deterministic intent path for the supported use cases.
With a configured provider it exposes the same tool registry as function tools,
with a maximum of four tool-call iterations.

The current implementation contains only one Supervisor. Future Coordinator,
Impact Prioritization, Route Planning, Critic, and Recommendation agents are
deferred. They must use this tool boundary and must not move routing, scoring,
impact detection, policy, or hard validation into an LLM.

## Simulation equivalence

The dashboard `POST /simulate-disruption` endpoint and the Supervisor's
`simulate_disruption` tool both call `backend/app/simulation_service.py`. The
service creates a scenario-only `NetworkState` and persists simulation history;
it does not mutate canonical locations, routes, shipments, or the baseline
NetworkX graph.
