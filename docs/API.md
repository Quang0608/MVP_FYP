# API

Base URL for local development: `http://localhost:8000`.

The API is implemented by FastAPI in `backend/app/main.py`. Request and response
models are defined in `backend/app/schemas.py`.

## Endpoints

### `GET /health`

Returns:

```json
{"status": "ok"}
```

### `POST /assistant`

Answers one operator question about trusted backend state. The assistant may
explain routes, disruption reasons, costs, times, risks, affected shipments,
priorities, and customers; it does not select or mutate routes.

Request:

```json
{
  "question": "Which customers are affected most?",
  "simulation_run_id": "optional-persisted-disruption-id",
  "shipment_id": null,
  "context": {
    "plan": null,
    "disruption": null,
    "affected_shipments": [],
    "recommendations": [],
    "locations": {}
  }
}
```

When `simulation_run_id` or `disruption_id` is supplied, the server loads the
persisted disruption/simulation result and reconstructs locations, affected
shipments, and recommendations. Any browser-provided `context` is ignored for
that request. `shipment_id` optionally narrows the reconstructed context.
Unknown identifiers return `404`. The transitional `context` field remains
supported for an unsaved interactive plan and should not be treated as the
long-term source of operational truth.

The response contains `answer`, `evidence`, and `source`. With no provider key,
or when the provider cannot be reached, `source` is
`offline_deterministic`; provider authentication and other failures remain
explicit errors.

### `POST /supervisor`

Runs the minimal bounded Supervisor over trusted backend tools. This is the
natural-language orchestration path; dashboard buttons continue to use the
direct deterministic endpoints.

Request:

```json
{
  "question": "Simulate Singapore Port closing for 72 hours.",
  "simulation_run_id": null,
  "shipment_id": null
}
```

The Supervisor may resolve a location, read a simulation, classify impacts,
compare deterministic routes, or call the controlled simulation tool. It returns
`answer`, structured `evidence`, `tool_calls`, and an `IncidentState`. It accepts
identifiers rather than arbitrary browser operational context. Provider failure
falls back to the bounded offline Supervisor path where supported.

### `GET /locations`

Returns the active persisted Asia operational subset of factories, ports,
warehouses, and customers. It does not expose the entire global port master.
Runtime ports include optional PortWatch fields when the normalized
current-state file and runtime mapping are available: `source`,
`canonical_location_id`, `portwatch_source_port_id`, `latest_observation_date`,
`activity_score`, `activity_anomaly_score`, and `operational_status`.

PortWatch activity is informational. It does not block routes, change route
weights, or select reroutes.

### `GET /locations/{location_id}`

Returns one runtime location with the same fields as `/locations`. A missing
runtime identifier returns `404`. The active runtime uses canonical WPI IDs such
as `LOC_WPI_50000`; temporary legacy aliases such as `P_SG` remain accepted at
the HTTP boundary for compatibility.

### `GET /routes`

Returns persisted directed transport legs with duration, cost, risk, capacity,
load, and status fields. SEA routes also expose curated corridor IDs and
representative weather sample points for Phase 4.1 exposure matching.

### `GET /shipments`

Returns persisted synthetic/semi-synthetic shipments. Ordered planned route
identifiers are reconstructed from relational shipment-route legs.

### GET /network/corridors

Returns the small curated catalog of provider-independent network zones and
chokepoints used for deterministic matching. Current examples include
CHK_SUEZ, CHK_MALACCA, CHK_HORMUZ, ZONE_SOUTH_CHINA_SEA, ZONE_RED_SEA,
ZONE_INDIAN_OCEAN, and ZONE_CAPE_GOOD_HOPE.

### POST /external-signals/network-match

Matches one structured external signal against the active runtime network. This
is a non-persisting debug contract for Phase 4.1. It returns direct location or
route matches, corridor memberships, and representative weather sample-point
evidence. It does not modify NetworkX state, route weights, capacity, or
shipment records.

### POST /external-signals/exposure

Matches one structured external signal and returns exposed shipment legs. A leg
is exposed only when its current/remaining route intersects a deterministic
location, route, corridor, or coordinate match and its estimated traversal
window overlaps the signal validity window. Completed legs are excluded.

The response reports spatial_match and temporal_match evidence. EXPOSED is not
an operational impact classification: this endpoint does not produce AT_RISK or
REROUTE_REQUIRED, apply operational effects, or trigger rerouting. Signals are
evaluated in memory and are not persisted in Phase 4.1.

Example request:

    {
      "id": "SIG-001",
      "source": "MANUAL",
      "source_record_id": "fixture-001",
      "signal_type": "MARINE_WEATHER",
      "target_type": "GEO_REGION",
      "latitude": 14.0,
      "longitude": 114.0,
      "radius_km": 100,
      "valid_from": "2026-09-28T00:00:00Z",
      "valid_to": "2026-09-30T00:00:00Z",
      "status": "ACTIVE"
    }

### `GET /disruptions`

Returns the built-in disruption scenario definitions.

### `GET /portwatch/state`

Returns current PortWatch state keyed by runtime location ID. Each state record
contains the canonical PortWatch/WPI identity and latest activity metadata. If
the normalized PortWatch files are absent or disabled, the response is empty.

### `GET /portwatch/disruptions`

Returns active normalized PortWatch disruptions with canonical
`affected_location_ids`. This endpoint exposes source state only; it does not
trigger impact detection or rerouting.

### `GET /portwatch/impacts`

Runs deterministic impact detection for each active PortWatch disruption. It
returns evidence only when an active shipment's remaining planned route
contains an affected runtime port. Each record includes the event ID, runtime
and canonical location IDs, shipment IDs, and the reason
`remaining route contains disrupted port`. Records also include an impact
classification. This endpoint does not automatically reroute, mutate shipments,
or change graph weights; PortWatch facts enter the same policy path as simulated
events only when scenario state is evaluated.

### `POST /simulate-disruption`

Creates and persists a structured disruption, its affected location/route
relationships, and its simulation response snapshot.

Request:

```json
{
  "disruption_type": "PORT_CLOSURE",
  "affected_location_ids": ["P_SG"],
  "affected_route_ids": [],
  "duration_hours": 72,
  "severity": "HIGH",
  "description": null
}
```

Response:

```json
{
  "disruption_id": "generated-uuid",
  "affected_shipments": [],
  "downstream_impacts": [],
  "shipment_impacts": []
}
```

`shipment_impacts` is additive and classifies every runtime shipment as
`UNAFFECTED`, `NETWORK_WARNING`, `SHIPMENT_AT_RISK`, or `REROUTE_REQUIRED`.
Classification is based on the shipment's current and remaining ordered route
legs, not on graph reachability alone. `affected_shipments` remains the
compatibility list of non-`UNAFFECTED` shipments.

Errors:

- `422`: affected location or route identifier does not exist

The `422` detail includes separate `unknown_location_ids` and
`unknown_route_ids` lists.

### `POST /reroute?disruption_id={id}`

Loads a stored disruption, deterministically reroutes affected shipments, persists
one agent-decision record per shipment plus the response snapshot, and returns
recommendations and aggregate metrics.

Only shipments classified as `REROUTE_REQUIRED` are passed to the rerouting
service. Warnings and feasible at-risk shipments remain visible in
`shipment_impacts` but do not generate recommendations.

The current contract accepts `disruption_id` as a query parameter, not a JSON body.
This endpoint does not currently generate LLM explanations.

Errors:

- `404`: disruption record not found

### `POST /plan-route`

Plans one interactive route without requiring a stored shipment.

Request:

```json
{
  "origin_id": "F_SZ",
  "destination_id": "C_A",
  "priority": "MEDIUM",
  "load_units": 10,
  "disruption": null,
  "generate_explanation": false
}
```

Possible statuses include `ROUTE_FOUND`, `NO_BASE_ROUTE`, `DISRUPTED_ENDPOINT`, and
`NO_FEASIBLE_ROUTE`.

An optional disruption containing an unknown location or route identifier returns
`422` with the same identifier detail as `/simulate-disruption`.

When `generate_explanation` is true, the current implementation requires
`OPENAI_API_KEY` when provider-backed wording is desired. Without a key, the API
returns a clearly labeled `explanation.source` of `offline_deterministic`; the
fallback summarizes only the backend decision record and does not select a route.
Provider connection and timeout failures use the same labeled fallback with
`explanation.fallback_reason` set to `provider_unavailable`. Authentication and
other provider failures still return `502`.

### `POST /shipment-analytics`

Generates an on-demand LLM explanation for one affected shipment in a stored
simulation and attaches it to the corresponding agent-decision record. It does not
change the selected route. The response contains the structured analytics payload;
the React dashboard presents its summary alongside the original and selected route
records from the reroute response, including duration, cost, risk, capacity
feasibility, delay saved, and additional cost.

Errors:

- `404`: disruption or affected shipment not found
- `502`: explanation generation failed

### `GET /recommendations`

Returns all persisted simulation/reroute snapshots, including readable legacy
`runs` records from databases created before the structured schema. Structured
records include the persisted `disruption` request so the frontend can reopen and
compare scenarios. A simulation-only record has no reroute metrics.

### `GET /metrics`

Returns persisted run identifiers and their metrics. A simulation that has not yet
been rerouted may have `null` metrics.

Phase 4.1 external signal matching is provider-independent and deterministic.
It exposes evidence only; it does not apply weather/news penalties or invoke
external providers.

### `GET /weather/routes/{route_id}/raw`

Optional Phase 4.2A integration/debug endpoint. When `OPEN_METEO_ENABLED=true`,
it retrieves the existing SEA route's representative weather sample points and
returns a summary containing the five requested points, cache statuses, request
window, and immutable snapshot path. `start_time` and `end_time` query values
are optional ISO timestamps and are interpreted in UTC by the provider layer.

The endpoint does not expose raw forecast payloads to the frontend or assistant.
It returns `503` when the provider is disabled, `404` for an unknown route,
`422` for a non-SEA route or invalid request, `504` for timeout, `429` for rate
limiting, `502` for provider/response failures, and `500` for cache or snapshot
persistence failures. It never changes route state, shipment state, NetworkX,
or rerouting decisions.

## Contract Rules

- Pydantic models validate request shapes and basic numeric bounds.
- Local browser clients may use CORS origins configured by `CORS_ORIGINS`; the
  default allowlist includes the Vite dev server (`localhost` and `127.0.0.1` on
  port 5173) and the container frontend port 8501.
- Disruption location and route identifiers are validated against persisted master
  data before the disruption is applied or stored.
- PortWatch state is loaded through `backend.app.integrations.portwatch`; API
  routes and graph construction do not depend on source-specific PortWatch
  fields.
- Interactive origin and destination identifiers are not yet validated as a
  separate client-error contract.
- API response changes require synchronized frontend and test updates.
- Scenario availability, effective duration/cost/risk/capacity/load, and
  disruption IDs are transient network-state values; canonical route and
  location records remain unchanged.
- Error details must not expose secrets or raw provider responses.
