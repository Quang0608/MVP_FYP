# ISS-0024: Canonical Data Layer Preparation

## Status

`DONE`

## Source

Direct request: prepare an extensible data directory and canonical data pipeline
for the autonomous supply-chain rerouting project.

## Context

The current MVP uses synthetic seed data from `backend/app/data.py` and persists
it in SQLite. Future public datasets and synthetic enterprise datasets need a
stable raw-to-canonical boundary before PostgreSQL, Neo4j, or source-specific
ingestion is introduced.

## Goal

Create documented canonical data contracts, representative samples, and
source-ingestion interfaces without changing the current runtime data source or
downloading external data.

## Scope

- Add the requested `data/` directory structure and documentation.
- Define JSON schemas and sample files for canonical supply-chain entities.
- Add Pydantic validation models and cross-entity reference validation.
- Add placeholder ingestion, normalization, synthetic-generation, and loading
  modules under `backend/data_pipeline/`.
- Document the SQLite-to-future-PostgreSQL/Neo4j boundary and deferred integration.

## Out of Scope

- Downloading or parsing external datasets.
- Migrating SQLite persistence to PostgreSQL.
- Creating or populating Neo4j.
- Kafka, streaming, or rerouting-algorithm changes.
- Changing existing API field names or dashboard behavior.

## Concerns

- The current API and database use a compatible but different legacy naming shape;
  the new canonical contracts must not silently replace those API contracts.
- Sample data is synthetic and illustrative, not evidence of external source
  quality or coverage.

## Proposal

Keep raw source folders immutable and make `data/processed/` the future ingestion
output boundary. Use JSON Schema for portable contracts and Pydantic models for
runtime validation, including foreign-key-like checks across the dataset. Keep
the existing deterministic fixture and SQLite repository unchanged until a
separate migration issue is approved.

## Approval

- Approved by: `USER REQUEST`
- Approved at: `2026-08-23`

## Acceptance Criteria

- [x] Required `data/` directories and placeholder files exist.
- [x] Root and source README files document ownership, formats, naming, and flow.
- [x] Canonical JSON schemas cover the requested entities and route/AIS support
  entities.
- [x] Small samples demonstrate every canonical dataset and use consistent IDs.
- [x] Pipeline modules expose clear placeholders without fake APIs or credentials.
- [x] Pydantic validation rejects invalid values and broken references.
- [x] Existing backend tests and compilation remain green.
- [x] Continuity and database documentation record the new boundary and deferred
  PostgreSQL/Neo4j integration.

## Local Verification

Passed:

- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests -q` (20 passed)
- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_data_pipeline.py -q` (3 passed)
- `.\\.venv\\Scripts\\python.exe -m compileall -q backend dashboard`
- JSON parse check for all 8 schemas passed.
- Isolated FastAPI smoke check passed: `/health` 200 and `/plan-route` 200 with
  `ROUTE_FOUND` using the existing synthetic SQLite-in-memory workflow.
- `git diff --check` passed; Git only reported existing line-ending warnings.

## Demo Evidence

Verified on 2026-08-23. No external data download was performed. The canonical
sample datasets validated together, and the existing route-planning API remained
functional.

## Completion Notes

Added the data directory, documentation, JSON contracts, samples, pipeline
interfaces, and Pydantic validation. Existing SQLite persistence, API contracts,
and routing remain unchanged. PostgreSQL/Neo4j loading and external extraction
remain intentionally deferred.
