# ISS-0018: Shipment Before-and-After Analysis

## Status

`COMPLETE`

## Goal

Give operators a readable analysis for one affected shipment, including the
baseline route, selected reroute, and the backend-generated impact summary.

## Acceptance Criteria

- [x] Selecting a shipment and requesting impact analysis renders the result in
      the affected-shipment workspace.
- [x] The result shows before and after route legs with duration, cost, risk,
      and capacity feasibility values from the backend.
- [x] The result shows delay saved, additional cost, status, and grounded
      summary/reasoning.
- [x] No-feasible-route recommendations render a clear absence of an after route.
- [x] React production build passes without backend contract changes.

## Local Verification

`npm run build` in `frontend/` — passed.
The no-key Singapore workflow returned shipment analytics with source
`offline_deterministic` and a non-empty summary for shipment `S001`.

## Demo Evidence

Verified locally on 2026-08-15.

## Completion Notes

The affected-shipment detail now renders baseline and rerouted route snapshots,
metric deltas, grounded reasoning, recommended action, risk warning, and next
steps after the operator requests analysis.
