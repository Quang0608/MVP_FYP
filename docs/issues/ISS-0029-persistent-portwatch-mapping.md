# ISS-0029: Persistent WPI-PortWatch Mapping Table

## Status

`DONE`

## Source

Direct request: create a separate persistent mapping between WPI and PortWatch,
use it for future normalization, and list hard cases for confirmation.

## Goal

Prevent future PortWatch normalization runs from silently changing canonical WPI
assignments.

## Scope

- Add a persistent WPI-to-PortWatch port mapping table.
- Build automatic suggestions using exact, country-alias, and conservative fuzzy
  logic only during explicit mapping-table creation.
- Add a numbered review queue for hard and unresolved cases.
- Make normalization consume the mapping table by PortWatch source ID only.
- Reprocess the existing 2026-08-10 through 2026-08-16 extract.

## Out of Scope

- Automatically resolving review-required cases.
- Editing immutable raw PortWatch responses.
- Rerouting or dashboard integration.

## Acceptance Criteria

- [x] Separate persistent mapping and review queue are created.
- [x] Normalization does not rerun name/country matching.
- [x] Hard cases have stable review sequence numbers.
- [x] Existing extraction is reprocessed using the persistent table.
- [x] Relevant tests, compilation, and diff checks pass.
- [x] Documentation and continuity files are updated.

## Local Verification

Passed:

- `.\\.venv\\Scripts\\python.exe -m backend.data_pipeline.portwatch.build_port_mapping --input-dir data/raw/portwatch/ports/2026-08-10_2026-08-16`
- `.\\.venv\\Scripts\\python.exe -m backend.data_pipeline.portwatch.normalize_ports --mapping-path data/mappings/wpi_portwatch_port_mapping.csv`
- `.\\.venv\\Scripts\\python.exe -m backend.data_pipeline.portwatch.build_state --ports-input data/processed/portwatch/port_monitoring.parquet --ports-output data/processed/portwatch/current_port_state.parquet`
- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests -q` (25 passed, 3 existing deprecation warnings)
- `.\\.venv\\Scripts\\python.exe -m compileall -q backend dashboard` (passed)
- `git diff --check` (passed; Git reported existing line-ending warnings)

## Completion Notes

The persistent table contains 2,065 source-port mappings: 1,158 automatic
matches and 907 review/unmapped rows after adding observed, unambiguous country
aliases. Normalization produced 5,790 canonical monitoring rows and current
state for 1,157 WPI locations. The review queue is numbered 1-907.
Rows with `REVIEW_REQUIRED` include a proposed candidate, while `UNMAPPED`
rows need a manual WPI assignment or explicit exclusion.
