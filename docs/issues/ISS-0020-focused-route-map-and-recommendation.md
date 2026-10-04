# ISS-0020: Focused Route Map and Recommendation Placement

## Status

`COMPLETE`

## Goal

Make interactive route planning easier to follow by focusing the map on the
planned origin-to-destination route and placing the current recommendation
directly below the planning controls.

## Acceptance Criteria

- [x] Before planning, the map continues to show the seeded network.
- [x] After planning, the map shows only the planned route's locations and legs.
- [x] The map includes the origin, destination, and intermediate locations on
      the selected route.
- [x] The AI Assistant/current recommendation appears directly below the origin,
      destination, priority, load, and plan controls.
- [x] The assistant is not duplicated in the lower dashboard row.
- [x] Existing route planning, disruption, and batch workflows remain intact.
- [x] React production build passes.

## Local Verification

`npm run build` in `frontend/` — passed.
`\.venv\Scripts\python.exe -m pytest backend/tests -q` — 16 passed.
`\.venv\Scripts\python.exe -m compileall -q backend dashboard` — passed.
`git diff --check` — passed.

## Demo Evidence

Verified locally on 2026-08-15.

## Completion Notes

The map uses the selected route path when a plan exists and falls back to the
full seeded network before planning. The planner and assistant are now adjacent
near the top of the dashboard.
