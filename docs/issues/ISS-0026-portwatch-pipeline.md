# ISS-0026: PortWatch Port and Checkpoint Pipeline

## Status

`DONE`

## Source

Direct request: implement IMF PortWatch daily ports and checkpoint monitoring.

## Goal

Ingest official PortWatch ArcGIS daily observations into immutable dated raw
extracts, map ports to the WPI canonical master, normalize historical monitoring
to Parquet, and derive a documented latest operational state.

## Scope

- ArcGIS REST client for the official `Daily_Ports_Data` and
  `Daily_Chokepoints_Data` layers.
- Date-configurable ports and checkpoints ingestion CLIs with pagination,
  metadata, and raw response preservation.
- WPI port mapping and generated checkpoint mapping with unresolved reports.
- Canonical monitoring Parquet outputs and validation reports.
- Configurable, explicitly non-official current-state scores.
- Focused offline tests; no automatic live download during verification.

## Out of Scope

- Rerouting, disruption API ingestion, Kafka, PostgreSQL, or Neo4j loading.
- Treating PortWatch data as shipment-level data.
- Weather or congestion claims beyond the derived state fields documented here.

## Decisions

- The actual PortWatch “checkpoint” source is the official
  `Daily_Chokepoints_Data` layer; internal output names remain checkpoint-oriented.
- The actual daily API has a nullable date-only `date` field and system
  `ObjectId`; `date` is canonicalized to `observation_date` and `ObjectId` is not
  copied to canonical output.
- PortWatch daily rows do not contain UN/LOCODE. The initial implementation used
  manual mappings first, then normalized country/name matching. `ISS-0027`
  supersedes that automatic rule with country-independent exact and
  conservative fuzzy name matching; unresolved rows remain reported and are
  excluded from canonical port records.
- `response.json` stores an ordered bundle of unchanged ArcGIS page payloads so
  pagination does not require transforming or discarding raw responses.

## Acceptance Criteria

- [x] Official ports/checkpoints endpoints and fields are implemented.
- [x] Date-configurable ingestion writes immutable dated raw folders and metadata.
- [x] WPI and checkpoint mappings are created and unresolved entities reported.
- [x] Canonical port/checkpoint Parquet outputs preserve nulls and required fields.
- [x] Current-state Parquet outputs use configurable, documented non-official scores.
- [x] Ingestion reports include counts, matches, missing dates, and warnings.
- [x] Offline tests, existing tests, compilation, and diff checks pass.
- [x] Data documentation and continuity records are updated.

## Local Verification

Passed:

- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_portwatch_pipeline.py -q` (3 passed)
- `.\\.venv\\Scripts\\python.exe -m pytest backend/tests -q` (24 passed)
- `.\\.venv\\Scripts\\python.exe -m compileall -q backend dashboard`
- 12 JSON schemas parsed successfully.
- All four PortWatch CLI help commands completed successfully.
- `git diff --check` passed; Git only reported existing line-ending warnings.

## Completion Notes

Verified on 2026-08-23 with offline ArcGIS-shaped fixtures. No live PortWatch
download was performed automatically. The date-configurable CLIs are ready for
an explicit extraction.

Live extraction evidence, 2026-08-23:

- Ports request for 2026-08-10 through 2026-08-16 succeeded.
- Raw response saved under `data/raw/portwatch/ports/2026-08-10_2026-08-16/`.
- 10,325 records arrived across 11 pages.
- Normalization wrote 5,300 matched canonical rows to
  `data/processed/portwatch/port_monitoring.parquet`.
- 1,060 PortWatch ports matched WPI; 1,005 remained unresolved and are listed in
  the mapping/report.
- The source returned no observations for 2026-08-15 and 2026-08-16.
- Current state wrote 1,059 canonical WPI locations to
  `data/processed/portwatch/current_port_state.parquet`.
