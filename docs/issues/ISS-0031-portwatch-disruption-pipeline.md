# ISS-0031 PortWatch disruption pipeline

Status: DONE

## Proposal

Add immutable PortWatch disruption snapshots, canonical historical disruption
records, normalized affected-port relations, and a current active-disruption
view. The pipeline will expose only canonical fields and WPI `location_id`
references to later impact detection. It will not trigger rerouting or change
the dashboard.

## Source verification

The official source is the IMF PortWatch ArcGIS layer:

`https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/portwatch_disruptions_database/FeatureServer/0/query`

The layer metadata publishes the requested `eventid`, event, date, severity,
location, affected-port, and page fields. `Shape__Area` and `Shape__Length` are
source geometry properties and are excluded from the canonical schema.

## Implementation plan

1. Extend the existing PortWatch client with the official disruptions query
   and immutable retrieval-timestamp snapshots.
2. Add source validation and canonical Pydantic disruption models.
3. Normalize saved records into `disruptions.parquet`, preserving nulls and
   source values without adding closure semantics.
4. Parse `affectedports` into `disruption_affected_ports.parquet` and resolve
   names through the persistent WPI-PortWatch mapping, then conservative
   canonical-name/country matching where no source-ID mapping exists.
5. Derive `current_disruptions.parquet` from UTC current time and source
   start/end dates.
6. Add ingestion reports, deduplication/update handling, tests, and docs.

## Assumptions and mismatch

- The API uses an integer `eventid`; it will be stored as a string canonical
  `event_id` so the stable external key is type-independent in Parquet.
- ArcGIS date values may be epoch milliseconds or ISO strings; both are parsed
  to UTC timestamps.
- `affectedports` is nullable and its delimiter/format is source data, not a
  documented relational API field. The parser will support observed JSON/list,
  comma/semicolon/newline, and pipe-delimited forms while reporting values it
  cannot resolve.
- No source schema mismatch was found in the official layer metadata.

## Acceptance criteria

- [x] Immutable raw disruption snapshots and metadata are written.
- [x] Historical canonical disruptions and affected-port relation files are
      written.
- [x] Current active disruptions are derived using source dates only.
- [x] Existing/changed/unchanged event IDs are handled deterministically.
- [x] Unresolved ports and validation warnings are reported.
- [x] No rerouting, Kafka, OpenAI, or dashboard behavior is changed.
- [x] Tests, compilation, and local data-pipeline verification pass.

## Live verification: 2026-08-24

- Retrieved one immutable snapshot for `fromdate >= 2026-01-01` and
  `fromdate < 2027-01-01`.
- Raw records: 7; canonical events: 7; active at
  `2026-08-24T00:00:00Z`: 1.
- Resolved affected-port relations: 16, all through the persistent source-ID
  mapping. Unresolved tokens: 27, consisting of 26 source IDs from event
  `1001279` and the non-port checkpoint token `chokepoint6` from event
  `10000004`.
- Validation warnings: none. The raw response remains immutable.
