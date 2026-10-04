# ISS-0014: Capacity Utilization and Bottleneck View

## Status

`BACKLOG`

## Source

Project review on 2026-08-14.

## Context

Capacity is enforced by the deterministic planner, but the current map and
route table do not show route capacity, current load, or utilization. Operators
cannot see why a route became infeasible or which legs are near saturation.

## Goal

Expose capacity pressure as an operational visualization without allowing the
frontend to calculate or override route feasibility.

## Scope

- Show `current_load / capacity` and utilization percentage for route legs.
- Color map legs by utilization bands and distinguish blocked legs.
- Add a bottleneck list sorted by utilization with source/destination and mode.
- Include capacity fields in route comparison and selected-shipment detail.
- Keep backend values as the only source of truth.

## Out of Scope

- Automatic capacity increases or carrier bookings.
- Replacing backend capacity checks with browser calculations.
- Predictive demand forecasting.

## Acceptance Criteria

- [ ] Every visible route leg has an understandable utilization state.
- [ ] Utilization bands and thresholds are documented and deterministic.
- [ ] Blocked legs cannot be mistaken for available high-utilization legs.
- [ ] Route recommendation capacity values match the API response exactly.
- [ ] Singapore closure and congestion scenarios show meaningful differences.

## Local Verification

Pending.

## Demo Evidence

Pending.

## Completion Notes

Pending.
