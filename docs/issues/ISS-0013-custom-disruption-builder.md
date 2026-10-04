# ISS-0013: Custom Disruption Builder and Simulation History

## Status

`BACKLOG`

## Source

Project review on 2026-08-14.

## Context

The frontend only exposes the five static scenarios returned by `/disruptions`.
The backend already accepts arbitrary validated location and route IDs, but an
operator cannot create a custom disruption from the UI or reopen a prior run.

## Goal

Let operators model a realistic disruption from the visible network and review
prior simulations without changing deterministic backend behavior.

## Scope

- Add a custom disruption form for one or more locations/routes, type, duration,
  severity, and description.
- Validate selections against loaded locations/routes before submission.
- Add a recent simulation history panel backed by `/recommendations` and
  `/metrics`.
- Allow reopening a prior simulation summary and reroute result.

## Out of Scope

- Automatically importing real-world incidents.
- Editing persisted master network data.
- Scheduling or recurring disruptions.

## Acceptance Criteria

- [ ] A custom disruption can be submitted using only IDs loaded from the API.
- [ ] Invalid or empty selections are rejected before a request is sent.
- [ ] Custom simulations use the same plan/simulate/reroute contracts as presets.
- [ ] History distinguishes simulation-only runs from rerouted runs.
- [ ] History loading and API errors have explicit UI states.

## Local Verification

Pending.

## Demo Evidence

Pending.

## Completion Notes

Pending.
