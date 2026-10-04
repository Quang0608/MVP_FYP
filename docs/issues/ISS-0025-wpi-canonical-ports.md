# ISS-0025: Normalize WPI Canonical Ports

## Status

`DONE`

## Source

Direct request: normalize the uploaded World Port Index table into a canonical
port table.

## Goal

Create `data/processed/wpi/ports.parquet` containing the requested canonical port
fields without modifying the raw WPI file.

## Scope

- Read `data/raw/wpi/UpdatedPub150.csv`.
- Normalize WPI number, name, country, UN/LOCODE, coordinates, and fixed source
  metadata.
- Validate required columns, identifiers, names, coordinates, and unique IDs.
- Write a Parquet output under `data/processed/wpi/`.
- Add a repeatable CLI normalizer and focused tests/documentation.

## Out of Scope

- Route generation from ports.
- OpenStreetMap connectivity.
- Entity resolution against other providers.
- Loading PostgreSQL, Neo4j, or the current SQLite MVP database.
- Editing or downloading raw WPI data.

## Data Decisions

- `wpi_number` remains a string so values such as `49454.5` are not changed.
- Blank WPI UN/LOCODE values become null; nonblank values are uppercased with
  internal whitespace removed, so `US FSP` becomes `USFSP`.
- `location_id` uses `LOC_WPI_<wpi_number>`. When a WPI number is duplicated in
  the source, `_OID_<OID_>` is appended to both duplicate records.
- `location_type` and `source` are fixed to `PORT` and `WPI`.

## Acceptance Criteria

- [x] Normalizer reads the uploaded WPI CSV without changing it.
- [x] Output exists at `data/processed/wpi/ports.parquet`.
- [x] Output contains exactly the requested canonical fields.
- [x] Output has valid coordinates and unique nonempty `location_id` values.
- [x] WPI identifiers, names, countries, and available UN/LOCODE values are
  preserved in normalized form.
- [x] Focused tests and existing backend tests pass.
- [x] Data documentation and continuity records are updated.

## Local Verification

Passed:

- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_normalize_wpi.py -q` (1 passed)
- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests -q` (21 passed)
- `.\\.venv\\Scripts\\python.exe -m compileall -q backend dashboard`
- Generated and inspected `data/processed/wpi/ports.parquet` (3,802 rows, 9
  requested columns, unique IDs, valid coordinate ranges).
- `git diff --check` passed; Git only reported existing line-ending warnings.

## Completion Notes

Verified on 2026-08-23. The uploaded WPI CSV was normalized into the requested
canonical Parquet port table. The raw file was not modified.
