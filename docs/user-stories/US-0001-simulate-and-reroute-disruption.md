# US-0001: Simulate and Reroute a Disruption

## User Story

As a supply-chain operator, I want to simulate a disruption and reroute affected
shipments, so that I can understand operational impact and choose feasible routes.

## Context

The core MVP flow uses synthetic locations, routes, and shipments seeded into a
structured relational database. Disruptions may block nodes or routes or increase
congestion. Deterministic backend logic identifies affected shipments, reserves
route capacity in priority order, and persists one agent decision per shipment.
Active normalized PortWatch disruptions can also be evaluated against the
remaining planned route of active shipments to produce impact evidence before a
separate rerouting decision is made.

## Acceptance Criteria

- [ ] The operator can select a built-in disruption and duration.
- [ ] The system identifies affected shipments and downstream locations.
- [ ] Candidate routes avoid blocked legs and reject unavailable capacity.
- [ ] Routes are scored by time, cost, risk, capacity, and shipment priority.
- [ ] Selected routes reserve capacity before later shipments are evaluated.
- [ ] Explicit no-feasible-route results are displayed.
- [ ] Aggregate metrics are accurate and documented.
- [ ] Master data, disruptions, and agent decisions retain relational integrity.
- [ ] The workflow passes the required local demo.

## Out of Scope

- Real carrier feeds, live shipment tracking, and production optimization.
- Globally optimal multi-commodity flow.
- Automatic operational execution of recommendations.

## Risks

- Greedy priority ordering may not produce a globally optimal allocation.
- Delay saved currently assumes the full disruption duration applies to the original
  route.
- Synthetic capacity and costs are illustrative rather than calibrated.

## Follow-up Issues

- `ISS-0004`: complete evaluation metrics
- `ISS-0006`: strengthen deterministic tests
- `ISS-0007`: structured persistence schema
- `ISS-0034`: detect shipment impacts from PortWatch disruptions

## Implementation Order

1. Preserve deterministic disruption and candidate routing behavior.
2. Define and complete metric contracts.
3. Strengthen controlled scoring and capacity tests.
4. Run the Singapore closure demo locally.
