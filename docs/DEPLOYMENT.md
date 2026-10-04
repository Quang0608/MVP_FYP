# Deployment and Local Demo

The project must be installed, verified, and demonstrated locally before any
GitHub push or deployment.

## Environment

Create `.env` from `.env.example`. Never commit `.env`.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection URL |
| `OPENAI_API_KEY` | Optional provider credential; no-key deterministic fallback is available |
| `OPENAI_MODEL` | OpenAI model identifier |
| `OPENAI_TIMEOUT_SECONDS` | Provider timeout |
| `APP_ENV` | Runtime environment label |
| `VITE_API_URL` | React frontend API base URL; defaults to `http://localhost:8000` locally |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call FastAPI |
| `PORTWATCH_ENABLED` | Enable the optional normalized PortWatch runtime adapter |
| `PORTWATCH_STATE_PATH` | Current normalized PortWatch state Parquet path |
| `PORTWATCH_DISRUPTIONS_PATH` | Current normalized PortWatch disruptions Parquet path |
| `PORTWATCH_AFFECTED_PORTS_PATH` | Canonical PortWatch disruption relation Parquet path |
| `RUNTIME_LOCATION_MAPPING_PATH` | Runtime-to-canonical location mapping CSV path |
| `OPEN_METEO_ENABLED` | Opt-in switch for the Phase 4.2A raw provider integration; defaults to false |
| `OPEN_METEO_FORECAST_BASE_URL` | Open-Meteo regular forecast endpoint |
| `OPEN_METEO_MARINE_BASE_URL` | Open-Meteo marine forecast endpoint |
| `OPEN_METEO_REQUEST_TIMEOUT_SECONDS` | Per-request provider timeout |
| `OPEN_METEO_RETRY_COUNT` | Bounded retries for timeout and temporary 5xx failures |
| `OPEN_METEO_CACHE_TTL_MINUTES` | Freshness window for the local file cache |
| `OPEN_METEO_RAW_SNAPSHOT_DIRECTORY` | Immutable raw weather snapshot root |
| `OPEN_METEO_CACHE_DIRECTORY` | Local weather cache root; ignored by git |
| `OPEN_METEO_MAX_COORDINATES_PER_REQUEST` | Maximum coordinates in one provider batch |
| `NEO4J_*` | Reserved placeholders; currently unused |

## Local Startup

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload
```

In a second terminal, start the React frontend:

```powershell
cd frontend
npm install
npm run dev
```

Backend: `http://localhost:8000`
React frontend: `http://localhost:5173`

When enabled, the backend reads the normalized PortWatch outputs under
`data/processed/portwatch/` through its application adapter. Missing outputs are
treated as an unavailable optional overlay, so the synthetic runtime remains
usable. The active runtime loads the reproducible Asia population: selected
canonical WPI ports plus synthetic factories, warehouses, customers, routes,
shipments, and ordered legs. Legacy IDs such as `P_SG` are accepted temporarily
at the API boundary and mapped to canonical runtime IDs; they are not a second
active network.

The frontend uses OpenStreetMap tiles for the geographic basemap. Browser
network access is required to load tiles, and the map retains the required
OpenStreetMap attribution.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend
cd frontend
npm run build
```

## Required Local Demo Gate

For every release candidate:

1. Confirm `/health` returns `{"status":"ok"}`.
2. Open the React frontend locally. Confirm the active map shows the Asia
   operational subset rather than the global port master.
3. Select or activate the Singapore closure scenario and verify that its
   scenario state marks Singapore unavailable while the base route data remains
   unchanged.
4. Use a 72-hour duration and click **Run selected disruption**.
5. Confirm the disruption row is selected/green and affected shipments render.
6. Plan a route from Shenzhen Factory to Customer A.
7. Confirm the interactive route identifies any disrupted original legs, compares
   alternatives, or reports that no other route is feasible.
8. Confirm the focused map shows only the planned route and the assistant can
   answer a question about its cost/time or the affected shipments.
9. Exercise an explanation through the configured provider or the labeled
   `offline_deterministic` fallback when no provider key is configured.
10. Record date, result, commands, and any failure in the active local issue.

Phase 3 scenario checks:

- A Singapore closure marks shipments whose current/remaining route still uses
  Singapore as `REROUTE_REQUIRED`; shipments that already passed it remain
  `UNAFFECTED`.
- Klang congestion keeps the route available, increases effective duration and
  risk, and marks feasible dependent shipments `SHIPMENT_AT_RISK` without
  generating reroute recommendations.
- A critical capacity reduction makes a dependent route infeasible and produces
  reroute recommendations only for the affected `REROUTE_REQUIRED` shipments.

Phase 4 dataset checks:

- The default generated population is 51 canonical real ports, 12 factories,
  14 warehouses/DCs, 14 customers, 150 directed routes, and 220 shipments.
- Singapore and Port Klang closure, congestion, and capacity scenarios are
  exercised against the generated population; baseline graph/domain state must
  remain unchanged.

Phase 3.5 agent checks:

- Dashboard simulation remains a direct `POST /simulate-disruption` call and
  does not require the LLM.
- The natural-language `POST /supervisor` path resolves locations and calls
  the shared deterministic simulation service through trusted tools.
- Compare the direct and Supervisor Singapore closure results; affected
  shipment classifications and base route values should match.

Do not mark a release scope ready to push until this gate passes or the user
explicitly accepts a documented exception.

Phase 4.1 exposure checks:

- GET /network/corridors returns the curated chokepoint/zone catalog and
  GET /routes exposes corridor IDs plus five representative points on each
  SEA route.
- POST /external-signals/exposure with a Singapore location signal returns
  only shipments whose current/remaining route still depends on Singapore.
- A synthetic CHK_SUEZ corridor signal returns only routes tagged with that
  corridor and excludes shipments whose tagged leg is completed.
- A synthetic marine-weather coordinate signal matches near route sample
  points but not unrelated routes; validity dates filter shipment exposure.
- These checks leave base route metadata, NetworkX route weights, and shipment
  impact classifications unchanged. No external provider is called.

Phase 4.2A optional raw-provider smoke check:

```powershell
$env:OPEN_METEO_ENABLED="true"
.\.venv\Scripts\python.exe -m backend.app.integrations.weather.smoke `
  --route-id ASIA_R_0056
```

The smoke script loads the route's five representative points, performs one
batched Forecast request and one batched Marine request, writes immutable raw
snapshots, and prints only a concise summary. It is not part of offline pytest
and is intentionally disabled by default. Phase 4.2A retrieves evidence only;
it does not score weather, create signals, change graph state, or reroute.

## Containers

The repository includes the backend `Dockerfile`, a React frontend Dockerfile,
and `docker-compose.yml`. The frontend container serves the built React assets
and proxies `/api/*` to the Compose backend service.

The intended container workflow is:

```powershell
docker compose up --build
```

Container frontend: `http://localhost:8501`

The React command center includes the geographic map, route planner, disruption
simulator, shipment filters and detail view, capacity bottlenecks, rerouting
summary, stored scenario comparison, and JSON/CSV report export. All route and
capacity values are read from the backend response; browser-side panels do not
choose or override routes.

Container tooling is preferred over installing new system packages on the host.
