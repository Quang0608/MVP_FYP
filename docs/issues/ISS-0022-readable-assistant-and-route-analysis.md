# ISS-0022: Readable Assistant and Interactive Route Analysis

## Status

`COMPLETE`

## Goal

Improve dashboard readability and make interactive route analysis consistent
with affected-shipment analysis.

## Scope

- Increase dashboard text sizing for operator readability.
- Keep the assistant chat transcript and input in the assistant section above
  Current Recommendation.
- Add a before/after interactive route analysis with the same route metrics and
  explanation structure used for affected shipments.
- Show every backend-returned alternative route with basic duration, cost, risk,
  capacity, and baseline delta information.

## Acceptance Criteria

- [x] Primary dashboard text is visibly larger without breaking responsive layout.
- [x] Assistant chat is visually separate from Current Recommendation.
- [x] Planned route analysis shows baseline and selected route snapshots.
- [x] Planned route analysis lists all available alternatives and their metrics.
- [x] No-feasible-route analysis remains clear.
- [x] React production build passes.

## Local Verification

`npm run build` in `frontend/` — passed.
`\.venv\Scripts\python.exe -m pytest backend/tests -q` — 17 passed.
`\.venv\Scripts\python.exe -m compileall -q backend dashboard` — passed.
`git diff --check` — passed.

## Demo Evidence

Verified locally on 2026-08-15.

## Completion Notes

Added readable typography overrides, separated assistant chat from the
recommendation card, and added `InteractiveRouteAnalysis` with original,
selected, and all candidate route metrics.
