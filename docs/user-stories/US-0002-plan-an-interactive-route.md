# US-0002: Plan an Interactive Route

## User Story

As a supply-chain planner, I want to select an origin, destination, load, priority,
and disruption, so that I can compare feasible route alternatives immediately.

## Context

The dashboard calls `/plan-route` and overlays the baseline and candidate paths on a
map. Interactive planning does not require a stored shipment.

## Acceptance Criteria

- [ ] Only reachable origin/destination combinations can be submitted.
- [ ] Invalid identifiers return a clear client error.
- [ ] Closed nodes and routes are excluded from candidates.
- [ ] Capacity-infeasible routes are rejected.
- [ ] Candidate scores and the selected route are displayed.
- [x] The workflow remains usable without an external provider key.
- [ ] Loading, empty, success, and failure states are understandable.

## Out of Scope

- Saving arbitrary interactive plans as persistent shipments.
- Editing the network from the dashboard.
- Real-time traffic or carrier pricing.

## Risks

- The current dashboard allows origins with no reachable destination.
- Endpoint behavior for congestion at an origin or destination needs clarification.

## Follow-up Issues

- `ISS-0002`: offline explanation fallback
- Unscheduled: validate network identifiers and endpoint semantics

## Implementation Order

1. Make route planning reliable offline.
2. Validate identifiers and reachable selections.
3. Clarify congestion endpoint behavior.
4. Run local API and dashboard demos.
