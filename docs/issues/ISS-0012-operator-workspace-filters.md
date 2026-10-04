# ISS-0012: Operator Workspace Filters and Shipment Drill-Down

## Status

`BACKLOG`

## Source

Project review on 2026-08-14.

## Context

The React frontend renders all affected shipments in one long list. Operators
cannot search by shipment, filter by priority or reroute status, or open a
focused detail view before requesting analytics.

## Goal

Make the affected-shipment workspace usable for real operational triage while
preserving the deterministic recommendation record.

## Scope

- Add shipment search by ID and destination.
- Add filters for priority and recommendation status.
- Add sortable columns for delay saved, additional cost, risk, and route score.
- Add a selected-shipment detail panel with original and selected route legs.
- Keep analytics on-demand for the selected shipment.

## Out of Scope

- Changing route selection or scoring.
- Bulk editing or dispatching shipments.
- Authentication and multi-user saved views.

## Acceptance Criteria

- [ ] Search and filters update results without a new backend request.
- [ ] Empty filtered results have a clear message and reset action.
- [ ] Sorting is deterministic and indicates the active direction.
- [ ] Selected shipment details show route, status, delay, cost, risk, and
      capacity fields from the backend response.
- [ ] Existing Singapore closure workflow remains usable on desktop and mobile.

## Local Verification

Pending.

## Demo Evidence

Pending.

## Completion Notes

Pending.
