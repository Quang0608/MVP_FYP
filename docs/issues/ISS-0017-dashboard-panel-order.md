# ISS-0017: Dashboard Panel Order

## Status

`COMPLETE`

## Goal

Match the requested command-center panel order by placing the AI assistant in
the rerouting-summary slot and moving the rerouting summary beside the network
map.

## Acceptance Criteria

- [x] The map's right-hand panel renders the rerouting summary.
- [x] The first lower content row renders the AI assistant in the former summary
      position without changing data or actions.
- [x] The responsive layout remains valid and the React production build passes.

## Local Verification

`npm run build` in `frontend/` passed.

## Demo Evidence

Verified locally on 2026-08-15 after the React production build passed.

## Completion Notes

This is a presentation-only change; backend contracts and deterministic routing
behavior are unchanged.
