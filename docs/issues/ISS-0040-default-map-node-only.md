# ISS-0040: Show route edges only for active map tasks

## Status

`DONE`

## Source

Direct user request: keep the default network map focused on locations and show
route edges only when a planned route or an applied disruption/rerouting task
provides relevant route context.

## Scope

- Hide route polylines in the idle/default map state.
- Preserve route polylines for route planning and applied disruption/rerouting
  context.
- Keep location markers, disruption styling, controls, and backend behavior
  unchanged.
- Do not redesign the dashboard or change routing semantics.

## Acceptance Criteria

- [x] Default map renders locations without route edges.
- [x] Planning a route still renders the relevant route edges.
- [x] Applied disruption/rerouting context still renders route edges.
- [x] Existing location and map-layer behavior remains available.
- [x] Frontend production build passes.

## Verification

```powershell
cd frontend
npm run build
```

## Local Verification

- Updated `frontend/src/App.jsx` so route edges and line legend entries render
  only when a planned route or applied disruption/rerouting context exists.
- Idle/default map still renders all operational location markers and keeps the
  route-layer control available.
- `npm run build` passed with Vite 5.4.21 after retrying with the required
  process-spawn permission because the sandboxed attempt returned `spawn EPERM`.
- `git diff --check` passed.
