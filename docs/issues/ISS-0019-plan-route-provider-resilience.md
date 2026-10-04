# ISS-0019: Keep Route Planning Available When Explanation Provider Is Unreachable

## Status

`COMPLETE`

## Goal

Ensure deterministic route planning still succeeds when the configured
explanation provider cannot be reached.

## Acceptance Criteria

- [x] `/plan-route` returns the deterministic route result when the provider
      connection or request times out.
- [x] The response labels the explanation as `offline_deterministic` and makes
      the provider-unavailable fallback visible to the dashboard.
- [x] Authentication/configuration errors remain explicit provider failures.
- [x] The Singapore route workflow and React build pass.

## Local Verification

`\.venv\Scripts\python.exe -m pytest backend/tests -q` — 16 passed.
`\.venv\Scripts\python.exe -m compileall -q backend dashboard` — passed.
The exact current-config Singapore `/plan-route` request returned HTTP 200 with
`ROUTE_FOUND`, `explanation.source=offline_deterministic`, and
`fallback_reason=provider_unavailable`.

## Demo Evidence

Verified locally on 2026-08-15. `npm run build` remains green from the latest
frontend verification.

## Completion Notes

Provider connection and timeout failures are now safe local fallbacks. Invalid
credentials and other provider errors still surface as explicit API failures.
