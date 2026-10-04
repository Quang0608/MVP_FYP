# ISS-0008: Migrate Dashboard to React

## Status

`IN_PROGRESS`

## Source

Direct user request: replace the Streamlit frontend with React.

## Context

The MVP previously used `dashboard/streamlit_app.py`. The backend API and
deterministic routing layer are already the project source of truth, so the
frontend can be migrated without changing route selection or persistence.

## Goal

Provide a React frontend that supports the existing local Singapore-closure
workflow and runs locally and through Docker Compose.

## Scope

- Add a Vite React frontend under `frontend/`.
- Recreate route planning, disruption simulation, batch rerouting, metrics, and
  on-demand shipment analytics using the existing FastAPI endpoints.
- Add loading, empty, and error states, including configured API URL handling.
- Replace the Streamlit Compose service with the React frontend container.
- Update README, API/deployment documentation, and continuity records.

## Out of Scope

- Changing backend routing, persistence, or response contracts.
- Implementing the pending offline explanation fallback (`ISS-0002`).
- Authentication, production ingress, or remote publication.

## Concerns

- The current backend still returns `502` for explanations without a provider
  key; the React UI must present that failure clearly.
- Docker builds require access to the Node package registry when dependencies
  are not cached locally.

## Proposal

Use React 18 with Vite and plain JavaScript to keep the client small. The app
will load locations, routes, and scenarios from the API, render a route map with
the existing Plotly dependency replaced by a lightweight SVG network view, and
call the same plan, simulation, reroute, and analytics endpoints. The frontend
container will build static assets and serve them with Nginx; Compose will pass
`VITE_API_URL` at build time or use a same-origin `/api` proxy configuration.

## Approval

- Approved by: `USER REQUEST`
- Approved at: `2026-08-14`

## Acceptance Criteria

- [x] React frontend starts locally with documented commands.
- [x] Singapore closure planning from Shenzhen Factory to Customer A works.
- [x] Candidate routes, selected route, affected shipments, and metrics render.
- [x] Shipment analytics action calls the existing endpoint and displays errors
      without crashing the app.
- [ ] Docker Compose starts backend and React frontend with service connectivity.
- [x] Existing backend tests and compilation checks still pass.
- [x] Frontend documentation and continuity records are updated.

## Local Verification

- `npm install` completed successfully in `frontend/` on 2026-08-14.
- `npm run build` completed successfully with the Vite production bundle.
- Vite served `http://127.0.0.1:5173` with HTTP 200 and the expected page title.
- `docker compose config` resolved the backend/frontend services successfully.
- `\.venv\Scripts\python.exe -m pytest backend/tests -q`: 12 passed.
- `\.venv\Scripts\python.exe -m compileall -q backend dashboard`: passed.
- Isolated API workflow with a local explanation stub returned `ROUTE_FOUND`,
  avoided `P_SG`, and produced 15 affected shipments with 13 reroutes.
- `docker compose build frontend` was blocked because the Docker Desktop Linux
  engine was unavailable (`dockerDesktopLinuxEngine` pipe not found).

## Demo Evidence

Local React and backend workflow passed on 2026-08-14. The container workflow is
unverified until a Docker daemon is available. Explanation output used a local
test stub because `ISS-0002` remains open.

## Completion Notes

The Streamlit client was removed and replaced with `frontend/`, a Vite React
application and Nginx production image. Docker Compose configuration resolves,
but the container demo remains pending until a Docker daemon is available.
