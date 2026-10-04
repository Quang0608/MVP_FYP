# ISS-0042: Active shipment status filtering and reroute options

## Status

`DONE`

## Source

Direct user request: make the affected-shipment view use current active shipment
impact results, expose supported shipment statuses in the filter, and show all
deterministic reroute candidates for a shipment.

## Scope

- Use server-produced shipment impact classifications for the dashboard's
  affected-shipment list.
- Treat the dashboard affected-shipment list as the reroute queue: include only
  recommendations with `REROUTED` or `NO_FEASIBLE_ROUTE` outcomes.
- Limit the affected-shipment status filter to those two reroute outcomes; the
  shipment lifecycle status remains informational in each row.
- Keep shipment impact analysis focused on route evidence and metrics by
  removing the recommendation-action, risk-warning, and next-steps blocks.
- Exclude inactive shipments (`COMPLETED`, `DELIVERED`, and `CANCELLED`) from
  current affected views.
- Filter by the operational shipment status while keeping reroute outcomes
  separate from shipment lifecycle status.
- Render every candidate route returned by the deterministic rerouting service
  in shipment impact analysis.

## Acceptance criteria

- [x] The affected-shipment view is the reroute queue and includes only
  `REROUTED` or `NO_FEASIBLE_ROUTE` outcomes.
- [x] The affected-shipment view does not include completed shipments.
- [x] The status filter covers all supported shipment lifecycle statuses and
  reroute result statuses where applicable.
- [x] Status filtering uses the shipment's operational status consistently.
- [x] Shipment impact analysis displays all returned candidate routes, with the
  backend-selected route clearly identified.
- [x] Existing backend tests, compilation, and frontend build pass.

## Local verification

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
cd frontend; npm run build
```

- Backend suite: 81 passed, with 3 existing deprecation warnings.
- Python compilation: passed.
- Frontend production build: passed after retrying outside the sandbox because
  Vite/esbuild initially hit the local `spawn EPERM` restriction.
