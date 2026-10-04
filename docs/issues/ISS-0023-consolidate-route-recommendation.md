# ISS-0023: Consolidate Interactive Route Recommendation

## Status

`COMPLETE`

## Goal

Remove duplicated interactive-route answers by making Current Recommendation the
single before/after explanation while retaining the separate alternatives table.

## Acceptance Criteria

- [x] Current Recommendation shows the original and selected route comparison.
- [x] The duplicate standalone interactive-route analysis is not rendered.
- [x] Route Comparison still lists all backend-returned alternatives.
- [x] Route Comparison appears directly below Current Recommendation.
- [x] Performance Overview is removed from beneath the affected-shipments workflow.
- [x] Unaffected original routes show only the original-route result.
- [x] A single feasible alternative is shown only in the before/after comparison.
- [x] Disruption and no-feasible-route messages remain visible.
- [x] React production build passes.

## Local Verification

Passed:

- `npm run build`
- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests -q` (17 passed)
- `.\\.venv\\Scripts\\python.exe -m compileall -q backend dashboard`
- `git diff --check`

## Demo Evidence

Verified locally on 2026-08-15. The Current Recommendation presents the single
before/after route comparison; the Route Comparison section retains the
alternative-route details.

## Completion Notes

The standalone interactive-route analysis was removed from the rendered
dashboard flow to avoid repeating the same before/after answer. Chat remains
above Current Recommendation, the Performance Overview panel is no longer
rendered beneath affected shipments, and unaffected or single-alternative
interactive plans avoid redundant alternative-route output.
