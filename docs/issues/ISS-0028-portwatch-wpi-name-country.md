# ISS-0028: PortWatch WPI Name-Country Matching

## Status

`DONE`

## Source

Direct request: redo PortWatch normalization using the WPI primary port name
and WPI `Country Code` matched to PortWatch `portname` and `country`.

## Goal

Produce PortWatch canonical monitoring rows only when both the normalized port
name and normalized country match the WPI master.

## Scope

- Keep manual mappings as the highest-priority override.
- Require exact normalized WPI name plus country matching.
- Reprocess the existing immutable August 10–16 raw extraction.
- Rebuild the current port state and reports.

## Out of Scope

- Fuzzy or country-independent matching.
- Editing raw PortWatch responses.
- Rerouting or dashboard integration.

## Acceptance Criteria

- [x] Resolver matches WPI name and country together.
- [x] Unmatched and ambiguous records remain reported.
- [x] Existing raw extraction is reprocessed without replacement.
- [x] Outputs and documentation are updated.
- [x] Tests, compilation, and diff checks pass.

## Local Verification

Passed:

- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests -q` (25 passed, 3 existing deprecation warnings)
- `.\\.venv\\Scripts\\python.exe -m compileall -q backend dashboard` (passed)
- `git diff --check` (passed; Git reported existing line-ending warnings)
- Normalization and state rebuild completed from the existing immutable raw
  extraction.

## Completion Notes

The strict WPI name-plus-country rule produced 5,300 canonical rows from
10,325 raw records, matched 1,060 source ports, left 1,005 unresolved, and
wrote current state for 1,059 WPI locations. The source has no observations for
2026-08-15 or 2026-08-16.
