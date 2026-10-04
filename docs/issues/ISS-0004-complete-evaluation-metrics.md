# ISS-0004: Complete Evaluation Metrics

## Status

`BACKLOG`

## Source

User story: `docs/user-stories/US-0001-simulate-and-reroute-disruption.md`

## Context

The project brief requires algorithm response time and LLM explanation
success/failure in addition to the currently returned reroute metrics.

## Goal

Expose complete, well-defined evaluation metrics without mixing routing time with
external provider latency.

## Scope

- Measure deterministic reroute duration.
- Record explanation state using an explicit enum or documented values.
- Define units and aggregation behavior.
- Display relevant metrics in the dashboard.

## Out of Scope

- Distributed tracing or production observability infrastructure.
- Provider billing analytics.

## Concerns

- Timing assertions can be flaky and should test shape/range rather than speed.
- Batch reroute and on-demand explanations currently occur in separate calls.

## Proposal

Record routing duration in milliseconds at the endpoint/service boundary. Track
explanation state separately (`not_requested`, `fallback`, `generated`, `failed`)
so metrics remain meaningful across the split API flow.

## Approval

- Approved by: `PENDING`
- Approved at: `PENDING`

## Acceptance Criteria

- [ ] Metrics include deterministic algorithm duration with documented units.
- [ ] Explanation state has documented, exhaustive values.
- [ ] `/metrics` and dashboard consumers display the new contract correctly.
- [ ] Tests cover metrics for empty, partial, and successful reroute sets.
- [ ] API, deployment, and continuity docs are updated.
- [ ] Local metrics demo passes.

## Local Verification

Pending.

## Demo Evidence

Pending.

## Completion Notes

Pending.
