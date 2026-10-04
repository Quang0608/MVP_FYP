# ISS-0043: External signal foundation and network exposure

## Status

`DONE`

## Source

Direct user request: implement Phase 4.1 as a provider-independent external
signal, corridor metadata, temporal matching, and shipment exposure foundation.

## Scope

- Add validated provider-independent `ExternalSignal` and `OperationalEffect`
  contracts.
- Add curated corridor/chokepoint metadata and route corridor memberships.
- Add representative maritime weather sample points to SEA routes.
- Match signals deterministically to locations, routes, corridors, and route
  sample points.
- Estimate remaining shipment-leg traversal windows and return structured
  exposure evidence with temporal overlap.
- Keep exposure separate from disruption impact, operational effects, and
  rerouting; do not modify NetworkX state or route weights.
- Add minimal read/debug APIs and synthetic fixtures without live ingestion.

## Explicitly out of scope

- Open-Meteo, GDELT, OpenWeather, NewsAPI, scraping, or any live provider call.
- Weather or security risk scoring, graph penalties, capacity changes, route
  blocking, automatic rerouting, frontend signal layers, PostGIS, Neo4j, Kafka,
  AIS, or LLM matching.

## Acceptance criteria

- [x] `ExternalSignal`, `OperationalEffect`, corridor, match, traversal-window,
  and exposure models validate structured inputs.
- [x] Existing SEA routes have deterministic representative sample points and
  meaningful corridor/chokepoint memberships after SQLite reload.
- [x] Direct location and route matching work without inferring extra impact.
- [x] Corridor matching returns every route with the requested membership.
- [x] Coordinate/radius matching uses deterministic haversine distance with
  near/far coverage.
- [x] Temporal overlap handles closed and open-ended validity windows with
  documented boundary semantics.
- [x] Shipment exposure uses only current/remaining route legs, excludes
  completed legs, and returns evidence without producing `AT_RISK` or
  `REROUTE_REQUIRED` classifications.
- [x] Minimal API/debug exposure and three synthetic scenarios are verified.
- [x] Existing backend tests, compilation, frontend build, and local demo gate
  are attempted; no external API is called.
- [x] Architecture, API, database, security, concerns, and continuity docs are
  synchronized.

## Local verification plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
Set-Location frontend; npm run build
```

Focused verification will also exercise synthetic Singapore location,
CHK_SUEZ corridor, South China Sea coordinate, and temporal-overlap scenarios,
plus confirm that the base route/network state is unchanged.

## Implementation notes

- SQLite metadata additions must be additive and compatible with existing local
  databases; route metadata will be stored as structured JSON text rather than
  introducing a parallel route master.
- Representative maritime sample points are exposure points, not navigation
  tracks. Corridor memberships are curated supply-chain metadata.
- Phase 4.1 stops at `signal -> network match -> temporal match -> exposed
  shipment`; policy application remains deferred to Phase 4.3.

## Local verification evidence

- Backend suite: 93 passed, with the existing 3 FastAPI/Starlette deprecation
  warnings.
- Python compilation: passed for `backend` and `dashboard`.
- Frontend production build: passed on the approved retry after the local
  sandboxed Vite/esbuild process hit `spawn EPERM`.
- Diff check: passed.
- Runtime metadata: 150 routes loaded from SQLite; 70 SEA routes have five
  representative weather sample points and corridor memberships; CHK_SUEZ is
  present on two routes.
- Singapore synthetic signal: matched `LOC_WPI_50000`, 18 directly connected
  routes, and 76 exposed remaining-leg records.
- CHK_SUEZ synthetic signal: matched two tagged routes and three exposed
  shipments; completed Suez legs were excluded.
- Coordinate synthetic marine signal: matched one route sample point and three
  exposed shipments within a 1 km radius; unrelated routes did not match.
- No external API or LLM call was used. Exposure evaluation did not alter route
  metadata or operational routing state.

## Remaining limitations

- Signals are evaluated in memory and are not persisted in Phase 4.1.
- Maritime sample points are representative linear exposure points, not
  navigation tracks.
- Traversal windows use planned timestamps or deterministic ETA/duration
  fallbacks and are not live tracking.
- Existing file-backed SQLite databases receive the new route columns during
  normal application startup; standalone repository reads should call the
  existing `initialise_database()` boundary first.
