# ISS-0021: Grounded Assistant and Staged Disruption Workflow

## Status

`IN_PROGRESS`

## Goal

Make disruption activation explicit and reversible, keep interactive route
planning separate from batch impact analysis, and provide a conversational
assistant grounded in the dashboard data currently displayed.

## Scope

- Stage one or more preset/custom disruptions without changing the map or
  metrics until **Run selected disruption** is clicked.
- Show selected disruption rows in a clear active/selected state and combine
  selected locations/routes into one deterministic simulation request.
- Explain when the original interactive route is disrupted, compare available
  alternatives, and clearly report no feasible alternative routes.
- Replace assistant action buttons with a question-and-answer chat workflow.
- Send structured current dashboard context with each question and keep the
  assistant from selecting routes or mutating dashboard state.

## Acceptance Criteria

- [x] Preset/custom disruptions can be selected, deselected, and combined.
- [x] Selection changes do not update map, metrics, or affected shipments until
      the run action is clicked.
- [x] A route plan explains disruption reason, alternatives, and no-route cases.
- [x] Chat questions return grounded answers using current plan/disruption/
      shipment data, including route comparisons and affected-customer queries.
- [x] Backend and React verification pass.

## Local Verification

`\.venv\Scripts\python.exe -m pytest backend/tests -q` — 17 passed.
`\.venv\Scripts\python.exe -m compileall -q backend dashboard` — passed.
`npm run build` in `frontend/` — passed.
The combined `P_SG` + `P_KL` simulation returned 25 affected shipments, and the
assistant route-comparison request returned HTTP 200 from the deterministic
fallback.

## Demo Evidence

Verified locally on 2026-08-15.

## Completion Notes

The dashboard now separates staged disruption selection from applied disruption
state. The assistant uses `POST /assistant` with current structured dashboard
context and cannot change deterministic routing decisions.
