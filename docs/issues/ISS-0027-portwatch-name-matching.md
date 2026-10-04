# ISS-0027: PortWatch Name-Only Port Matching

## Status

`DONE`

## Source

Direct request: accept similar PortWatch port names without requiring country
matches and reprocess the 2026-08-10 through 2026-08-16 extraction.

## Goal

Increase PortWatch-to-WPI matching while preserving deterministic, reviewable
unresolved reporting.

## Scope

- Keep manual mappings as the highest-priority override.
- Match exact normalized names across all WPI countries.
- Add conservative fuzzy name matching with recorded scores.
- Reprocess the existing immutable raw extraction and rebuild current state.

## Out of Scope

- Editing or replacing raw PortWatch responses.
- Country-based alias tables or external geocoding.
- Rerouting or dashboard integration.

## Acceptance Criteria

- [x] Country is not required for exact or fuzzy name matching.
- [x] Similar-name matches use a deterministic threshold and ambiguity margin.
- [x] Mapping and normalization reports retain unresolved cases.
- [x] The 2026-08-10 through 2026-08-16 extraction is reprocessed.
- [x] Relevant tests, compilation, and diff checks pass.
- [x] Documentation and continuity files are updated.

## Local Verification

Passed:

- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_portwatch_pipeline.py -q` (4 passed)
- `.\\.venv\\Scripts\\python.exe -m backend.data_pipeline.portwatch.normalize_ports`
- `.\\.venv\\Scripts\\python.exe -m backend.data_pipeline.portwatch.build_state --ports-input data/processed/portwatch/port_monitoring.parquet --ports-output data/processed/portwatch/current_port_state.parquet`
- Output inspection confirmed 5,625 processed rows, 1,125 matched source
  ports, 940 unresolved source ports, and missing source dates on August 15
  and 16.

## Completion Notes

The immutable raw extraction was reused; no second raw download was created.
The mapping now records `similarity_score` for fuzzy matches.

This rule was later superseded by `ISS-0028`, which requires the WPI primary
name and WPI `Country Code` to match the PortWatch name and country exactly.

Full verification:

- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests -q` (25 passed, 3 existing deprecation warnings)
- `.\\.venv\\Scripts\\python.exe -m compileall -q backend dashboard` (passed)
- `git diff --check` (passed; Git reported existing line-ending warnings)
