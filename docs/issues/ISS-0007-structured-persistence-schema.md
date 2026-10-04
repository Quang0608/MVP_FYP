# ISS-0007: Structured Persistence Schema

## Status

`COMPLETE`

## Source

Direct request

## Context

The current SQLite database stores each disruption and its result in one `runs`
row containing JSON text. Locations, routes, and shipments are regenerated in
memory for every request. This does not represent the structured domain model
required for locations, routes, shipments, disruptions, and agent decisions.

## Goal

Persist the synthetic supply-chain master data and simulation decisions in a
structured relational schema without changing the public API or deterministic
routing behavior.

## Scope

- Add relational tables for locations, routes, shipments, shipment route legs,
  disruptions, affected disruption locations/routes, and agent decisions.
- Seed master data idempotently at database initialization.
- Load API graph inputs from the database.
- Store reroute recommendations as one agent decision per affected shipment.
- Preserve ordered route data in decision payloads where the existing API requires
  nested route comparisons.
- Keep the legacy `runs` table readable long enough to avoid deleting an existing
  local database.
- Update database, API, security, user-story, and continuity documentation.
- Add persistence-focused automated tests.

## Out of Scope

- Neo4j integration.
- Alembic or production migration automation.
- Editing master data through the dashboard.
- Authentication, authorization, or production data retention.

## Concerns

- Existing untracked local databases can contain legacy `runs` rows.
- SQLite cannot add this redesign to an existing table, so new tables are created
  alongside the legacy table and new writes use the structured schema.
- Candidate and selected route comparison objects remain JSON payloads on agent
  decisions to preserve the current API; identifiers and decision metrics are
  separately queryable relational columns.

## Proposal

- Define explicit SQLAlchemy ORM records in `backend/app/repository.py`.
- Use foreign keys and ordered association rows for shipment paths and affected
  disruption identifiers.
- Keep `seed_data()` as the canonical deterministic fixture, but copy it into empty
  master tables during startup and read runtime graph data through the repository.
- Replace `save_run` calls with `save_disruption` and `save_agent_decisions`.
- Reconstruct existing `/recommendations` and `/metrics` response shapes from the
  normalized rows.
- Treat the user's direct request as approval for this schema direction.

## Approval

- Approved by: User
- Approved at: 2026-07-26T17:55:09+08:00

## Acceptance Criteria

- [x] Locations, routes, and shipments are stored in relational tables.
- [x] Shipment planned paths retain deterministic leg order.
- [x] Disruptions retain all affected location and route identifiers.
- [x] Rerouting writes one structured agent-decision row per recommendation.
- [x] Existing API response contracts remain compatible.
- [x] Database and related documentation describe the implemented schema.
- [x] Relevant automated checks pass.
- [x] The Singapore closure local demo is attempted and recorded.

## Local Verification

2026-07-26:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
git diff --check
```

Results:

- 12 tests passed.
- Backend and dashboard compilation succeeded.
- `git diff --check` reported no content errors; Git emitted only existing
  line-ending conversion warnings.
- Persistence assertions verified 13 locations, 17 routes, 30 shipments, 95
  ordered shipment legs, disruption associations, and one agent-decision row per
  reroute recommendation.

## Demo Evidence

Date: 2026-07-26

- Used an isolated temporary SQLite database and removed it after the run.
- Backend `/health`: `ok`.
- Singapore closure, 72 hours, Shenzhen Factory to Customer A:
  `ROUTE_FOUND`.
- Candidate count: 1; all candidates avoided `P_SG`.
- Affected shipments: 15.
- Successfully rerouted: 13.
- Recommendation history rows: 1.
- Metric history rows: 1.
- Dashboard HTTP response: 200.
- Provider explanation was not attempted because the required offline fallback is
  still tracked by `ISS-0002`; this remains a release-demo concern outside this
  schema issue.

## Completion Notes

Implemented structured relational persistence in `backend/app/repository.py`,
connected the API to persisted master data, added foreign-key reference validation,
stored deterministic agent decisions and optional explanations, and updated
database/API/security/story documentation.

Existing `runs` tables remain readable but are not created or written by fresh
databases. A legacy record is copied into the structured schema when it is rerouted;
bulk conversion and rollback remain deferred as `CON-011`.
