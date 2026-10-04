# ISS-0002: Offline Explanation Fallback

## Status

`COMPLETE`

## Source

User stories:

- `docs/user-stories/US-0002-plan-an-interactive-route.md`
- `docs/user-stories/US-0003-receive-a-grounded-explanation.md`

## Context

Interactive route planning requests explanations by default. Without
`OPENAI_API_KEY`, the backend returns `502`, although the project brief requires a
mock or local fallback so the MVP remains demonstrable offline.

## Goal

Return a clearly labelled, deterministic explanation when no provider key exists,
without hiding genuine provider failures when a key is configured.

## Scope

- Add a deterministic explanation built only from the decision record.
- Use it when the provider key is missing.
- Identify the explanation source in the response or documented contract.
- Cover route planning and shipment analytics consistently.
- Correct README and API documentation.

## Out of Scope

- Building a second model provider integration.
- Silently converting configured-provider outages into success unless approved.

## Concerns

- The fallback must not imply that AI generated the content.
- Changing response shapes requires dashboard and test updates.

## Proposal

Define a typed explanation structure with a source indicator. Construct fallback
fields from exact decision-record values. Keep configured-provider errors explicit,
then update both API consumers and tests.

## Approval

- Approved by: `PENDING`
- Approved at: `PENDING`

## Acceptance Criteria

- [x] `/plan-route` succeeds without `OPENAI_API_KEY`.
- [x] `/shipment-analytics` succeeds without `OPENAI_API_KEY`.
- [x] The response clearly distinguishes deterministic fallback from provider output.
- [x] Fallback content contains only decision-record facts.
- [x] Provider behavior with a configured key remains covered by mocked tests.
- [x] README, API, security, and continuity docs are updated.
- [x] Local no-key demo passes.

## Local Verification

`\.venv\Scripts\python.exe -m pytest backend/tests -q` — 15 passed.
`\.venv\Scripts\python.exe -m compileall -q backend dashboard` — passed.
The isolated Singapore closure workflow succeeded with no provider key; route
planning returned `ROUTE_FOUND`, the explanation source was
`offline_deterministic`, and shipment analytics remains on demand.

## Demo Evidence

Verified locally on 2026-08-15. Configured-provider calls remain explicit and
still surface provider failures rather than silently using the fallback.

## Completion Notes

The fallback is generated from the deterministic decision record in
`backend/app/llm.py` and is labeled in the API response with `source`.
