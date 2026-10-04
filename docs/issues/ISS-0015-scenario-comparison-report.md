# ISS-0015: Scenario Comparison and Exportable Decision Report

## Status

`BACKLOG`

## Source

Project review on 2026-08-14.

## Context

The API persists recommendation and metric snapshots, but the React frontend
shows only the current run. Operators cannot compare Singapore closure,
congestion, or custom scenarios or export an auditable decision summary.

## Goal

Provide a deterministic what-if comparison view and a portable report for local
review and release demonstrations.

## Scope

- Select two or more stored runs from `/recommendations` and `/metrics`.
- Compare affected count, reroute success, delay saved, cost, and risk.
- Show scenario inputs beside each metric set.
- Export the selected comparison as JSON and CSV from frontend-generated data.
- Label missing or not-yet-rerouted metrics explicitly.

## Out of Scope

- Sending reports externally.
- Adding new scoring dimensions.
- Treating exported data as a replacement for persisted records.

## Acceptance Criteria

- [ ] Comparison uses backend-provided values without recomputing route choices.
- [ ] Partial and empty histories render without fabricated metrics.
- [ ] Exports contain scenario identifiers, timestamps, and displayed metrics.
- [ ] Exported values match the visible comparison table.
- [ ] A documented local demo compares two built-in scenarios.

## Local Verification

Pending.

## Demo Evidence

Pending.

## Completion Notes

Pending.
