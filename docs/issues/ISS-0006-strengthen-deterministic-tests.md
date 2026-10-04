# ISS-0006: Strengthen Deterministic Tests

## Status

`BACKLOG`

## Source

User stories:

- `docs/user-stories/US-0001-simulate-and-reroute-disruption.md`
- `docs/user-stories/US-0002-plan-an-interactive-route.md`

## Context

Several tests pass without proving their named behavior. The priority test only
checks sorted order, and the no-route test accepts either possible status.

## Goal

Make deterministic routing, capacity, disruption, scoring, and persistence
regressions fail clearly.

## Scope

- Assert priority-specific route selection with controlled route fixtures.
- Assert explicit no-feasible-route behavior.
- Cover sequential capacity reservations across shipments.
- Cover invalid identifiers and metrics where contracts are defined.
- Preserve provider independence through mocks or fallback behavior.

## Out of Scope

- Browser end-to-end automation.
- Live OpenAI calls in tests.
- Performance load testing.

## Concerns

- Tests tied too closely to seed ordering may become brittle.

## Proposal

Use small purpose-built graphs for scoring and capacity tests, retaining only a few
seed-data integration tests. Assert exact outcomes and invariants, never multiple
opposing outcomes.

## Approval

- Approved by: `PENDING`
- Approved at: `PENDING`

## Acceptance Criteria

- [ ] High-, medium-, and low-priority scoring behavior is tested explicitly.
- [ ] No-route behavior has one expected result.
- [ ] Sequential capacity allocation is covered.
- [ ] Tests remain deterministic and require no network.
- [ ] Relevant docs and continuity are updated.
- [ ] Full local test suite passes.

## Local Verification

Pending.

## Demo Evidence

Pending.

## Completion Notes

Pending.
