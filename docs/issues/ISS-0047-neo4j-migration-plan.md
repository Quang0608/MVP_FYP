# ISS-0047 Neo4j migration and target-stack planning brief

## Status

`DONE`

## Source

Direct user request: document the plan, current status, and difficulties for
migrating the runtime from SQLite toward Neo4j with Cypher, NetworkX, OR-Tools
CP-SAT, FastAPI, a validated tool-calling agent, and React.

## Context

The current MVP uses SQLite as its runtime source of truth and NetworkX as a
transient deterministic scenario graph. Neo4j variables exist only as unused
placeholders. The requested target stack changes persistence and assignment
boundaries, so a parity-first migration brief is required before code changes.

## Goal

Create a portable Markdown brief that describes the current implementation,
target architecture, migration sequence, likely difficulties, acceptance gates,
and a prompt for producing an exact implementation plan.

## Scope

- Current runtime, graph, solver, agent, API, and frontend status.
- Neo4j graph model and SQLite-to-Neo4j migration phases.
- Cypher, NetworkX, CP-SAT, trusted-agent, and React responsibilities.
- Data parity, rollback, testing, deployment, and security risks.

## Out of Scope

- Installing Neo4j or OR-Tools.
- Adding a Neo4j adapter, changing the database, or changing routing behavior.
- Running a live migration or changing Docker/Compose configuration.

## Concerns

- A direct storage swap could change route selection, shipment impact behavior,
  or historical semantics without an observable parity failure.
- Neo4j should not become a place for transient scenario state or LLM-selected
  operations.
- CP-SAT may change deterministic ranking unless integer scaling, tie-breaking,
  candidate ordering, and objective weights are explicitly defined.

## Proposal

Add the root-level file `meo4j_migration.md`, preserving the user-provided
filename spelling, while using the correct Neo4j terminology inside the
document. The document is a planning artifact only.

## Approval

- Approved by: `USER`
- Approved at: `2026-10-13T00:00:00+08:00`

## Acceptance Criteria

- [x] Current project status is accurate and distinguishes implemented from
  planned components.
- [x] The target stack and data ownership boundaries are explicit.
- [x] Migration phases include parity, rollback, validation, and cutover.
- [x] Likely technical and operational difficulties are recorded.
- [x] A ready-to-paste planning prompt is included.
- [x] Continuity files and documentation validation are updated.

## Local Verification

- `git diff --check`: passed after documentation changes.
- Runtime tests and the local demo were not rerun because this is a
  documentation-only change.

## Demo Evidence

Not applicable: no runtime behavior or data was changed.

## Completion Notes

Added the migration brief and continuity entries. No application code,
database records, or deployment files were changed.
