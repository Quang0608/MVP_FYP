# ISS-0044 Open-Meteo weather provider foundation

- Status: DONE
- Related story: [US-0005 Identify shipment exposure to external signals](../user-stories/US-0005-external-signal-exposure.md)
- Phase: 4.2A

## Goal

Add an isolated, provider-specific Open-Meteo integration that retrieves and
preserves validated regular and marine forecast payloads for the existing five
representative sample points on SEA routes.

## Scope

- Add explicit Open-Meteo settings with the provider disabled by default.
- Batch route sample-point coordinates into provider requests.
- Validate response structure without calculating weather risk or creating
  `ExternalSignal` records.
- Add typed provider errors, bounded transient retries, file-backed cache with
  explicit stale fallback, and immutable raw snapshots.
- Add a small debug summary endpoint and an optional live smoke script.
- Add offline mocked tests and update architecture, deployment, raw-data, and
  continuity documentation.

## Out of scope

Weather risk scoring, weather `ExternalSignal` creation, temporal shipment
weather evaluation, `OperationalEffect` generation/application, NetworkX or
shipment mutation, rerouting, GDELT/news, LLM interpretation, frontend work,
Redis, GIS infrastructure, and mandatory live-network tests.

## Acceptance criteria

- A SEA route's five representative points are sent as one high-level batched
  forecast request and one high-level batched marine request.
- Forecast and marine variables are explicit and provider responses retain raw
  values, timestamps, and provider metadata.
- Invalid requests, timeout, transient provider failure, rejection, malformed
  response, cache failure, unsupported routes, and snapshot failure have typed
  integration-layer errors.
- Fresh cache hits avoid HTTP; expired cache attempts the provider; stale cache
  fallback is explicit; missing data is never treated as safe weather.
- Each successful live route retrieval writes a new immutable forecast, marine,
  and metadata snapshot without overwriting prior snapshots.
- Unit tests remain offline and cover requests, validation, retry behavior,
  cache semantics, snapshots, batching, and SEA/non-SEA route handling.
- Existing routing, disruption, scenario, PortWatch, agent, API, and frontend
  behavior remains unchanged.

## Local verification plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
cd frontend
npm run build
cd ..
git diff --check
```

Optional live verification, only when explicitly enabled and network access is
available:

```powershell
$env:OPEN_METEO_ENABLED="true"
.\.venv\Scripts\python.exe -m backend.app.integrations.weather.smoke --route-id ASIA_R_0056
```

## Local verification

- `backend/tests/test_weather_provider.py` covers request construction,
  multi-coordinate batching, requested variables, response validation, timeout
  and 5xx retry, non-retry 4xx rejection, cache hit/expiry/stale fallback,
  immutable snapshots, route reuse, and unsupported routes.
- `backend/tests/test_api.py` verifies the weather debug endpoint is opt-in.
- `.\.venv\Scripts\python.exe -m pytest backend/tests -q -s`: **105 passed**, 3 existing deprecation warnings.
- `.\.venv\Scripts\python.exe -m compileall -q backend dashboard`: passed.
- `npm run build` from `frontend`: passed after the approved local process-spawn
  retry; no frontend source changes were made.
- `git diff --check`: passed; only existing line-ending warnings were reported.
- Optional live smoke with `OPEN_METEO_ENABLED=true` and route `ASIA_R_0056`:
  five points requested, Forecast OK, Marine OK, cache MISS/MISS, and a new
  snapshot written under
  `data/raw/weather/open_meteo/20260926T102521544271Z/`.
- Repeating the same smoke operation returned Forecast `HIT` and Marine `HIT`
  with no second snapshot, confirming cache reuse for the route coordinate and
  variable set.

## Evidence and limitations

The live smoke test was initially blocked by the sandbox's outbound-network
restriction and passed after the approved network retry. The provider is still
disabled by default. The implementation preserves raw provider values only;
weather normalization, severity/risk scoring, signal creation, operational
effects, shipment weather-time evaluation, and rerouting remain deferred to
Phase 4.2B and later work.
