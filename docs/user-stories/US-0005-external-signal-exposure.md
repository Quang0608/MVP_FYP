# US-0005 Identify shipment exposure to external signals

## User Story

As an operations user, I want external evidence matched to network entities
and remaining shipment legs so that I can see exposure before any operational
policy or rerouting is applied.

## Context

Phase 4.1 established provider-independent `ExternalSignal` matching for
locations, routes, corridors, and representative maritime sample points. The
matching layer is deterministic and separate from NetworkX state, disruption
policy, and routing.

## Acceptance Criteria

- A signal identifies affected network locations, routes, or corridors using
  explicit entity or coordinate matching.
- A signal's validity window is compared with estimated remaining shipment-leg
  traversal windows.
- Completed shipment legs are excluded.
- Exposure evidence identifies the shipment, route, match type, and temporal
  window.
- Exposure does not itself mean `AT_RISK`, `REROUTE_REQUIRED`, a route penalty,
  or a graph mutation.

## Out of Scope

Live provider ingestion, weather/news interpretation, operational effects,
automatic rerouting, and frontend weather presentation.

## Risks

Representative route points and deterministic traversal windows are modeled
exposure approximations, not navigation tracks or live vessel telemetry.

## Follow-up Issues

- Phase 4.2A: preserve raw Open-Meteo provider evidence.
- Phase 4.2B: normalize weather observations and create weather signals.
- Phase 4.3: apply reviewed operational policies to external evidence.

## Implementation Order

1. Build the provider-independent signal and exposure contracts.
2. Add deterministic network and temporal matching.
3. Add provider ingestion below the signal boundary.
4. Add normalization and policy only in later phases.
