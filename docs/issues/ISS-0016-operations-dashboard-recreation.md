# ISS-0016: Operations Dashboard Recreation and End-to-End Integration

## Status

`IN_PROGRESS`

## Source

User request on 2026-08-15, based on `dashboard_design/first_dashboard_reroute.png`.

## Goal

Recreate the supplied operations command-center dashboard in the React frontend
and make every visible workflow use the existing deterministic FastAPI contracts.

## Scope

- Rebuild the dark operations layout with navigation, KPI cards, network map,
  assistant/recommendation panel, disruption and shipment workspaces, route
  comparison, capacity visibility, performance, risk, insights, and history.
- Preserve backend-owned route selection, scoring, disruption impact, and metrics.
- Add usable filtering, detail views, custom disruption submission, scenario
  comparison, and local JSON/CSV export where the existing API supports them.
- Make the core workflow demonstrable without an OpenAI credential through a
  clearly labeled deterministic explanation fallback.
- Keep the dashboard responsive and functional with the seeded synthetic data.

## Out of Scope

- Real carrier feeds, production authentication, dispatch execution, or remote
  publication.
- Changing the deterministic routing algorithm or inventing operational data.

## Acceptance Criteria

- [x] The React dashboard visually follows the supplied reference hierarchy and
      dark navy visual language while using the repository's actual network data.
- [x] Navigation sections expose the dashboard's operational views without
      breaking the existing plan, simulate, reroute, and analytics actions.
- [x] Map overlays, route comparison, capacity utilization, shipment filters,
      disruption history, and scenario comparison use backend response values.
- [x] Backend route planning and rerouting work without an OpenAI key, and any
      fallback is labeled as deterministic/offline.
- [x] Backend tests, Python compilation, React production build, and the local
      Singapore closure workflow pass.

## Local Verification

`\.venv\Scripts\python.exe -m pytest backend/tests -q` — 15 passed.
`\.venv\Scripts\python.exe -m compileall -q backend dashboard` — passed.
`npm run build` in `frontend/` — passed; Vite preview returned HTTP 200.
The isolated Singapore workflow returned `ROUTE_FOUND`, avoided Singapore Port,
identified 15 affected shipments, and rerouted 13. The dashboard history,
custom disruption form, filters, capacity panel, comparison, and exports use the
existing API records.

## Demo Evidence

Verified locally on 2026-08-15. Docker image/demo remains unverified because the
local Docker Desktop Linux engine is unavailable.

## Completion Notes

The supplied command-center visual hierarchy was recreated in `frontend/src`.
The backend remains the sole source of truth for route selection, feasibility,
capacity, and persisted metrics.
