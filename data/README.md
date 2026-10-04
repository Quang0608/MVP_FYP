# Canonical Supply-Chain Data Layer

This directory separates source-specific files from the normalized data consumed
by the routing and analytics layers.

```text
external source -> data/raw/ -> parser/cleaning -> entity resolution
                 -> data/processed/ -> PostgreSQL / Neo4j / routing engine
```

## Directories

- `raw/`: original provider files. Keep them immutable and source-specific.
- `processed/`: normalized canonical files produced by pipeline code. This is
  the future application-consumption boundary.
- `mappings/`: source identifiers and names mapped to canonical IDs.
- `schemas/`: JSON Schema contracts for canonical entities.
- `samples/`: small, synthetic CSV examples for local validation and demos.

The current MVP still seeds its SQLite database from
`backend/app/data.py`. The new directory is an architecture boundary and sample
contract; wiring processed files into PostgreSQL or Neo4j is deferred to a later
migration issue.

## Raw source placement

| Source | Directory | Expected format | Limitation |
|---|---|---|---|
| World Port Index | `raw/wpi/` | CSV | Slowly changing port master data |
| OpenStreetMap | `raw/osm/` | `.osm.pbf` | Geographic network, not business shipments |
| IMF PortWatch | `raw/portwatch/` | CSV or JSON | Port-level activity only; no shipment records |
| AIS | `raw/ais/` | CSV or Parquet | Vessel movement, not ownership or orders |
| Weather/marine weather | `raw/weather/` | JSON | External conditions require normalization |
| GDELT/events | `raw/gdelt/` | JSON or CSV | News-derived signals require confidence review |
| Synthetic enterprise data | `raw/synthetic/` | CSV or JSON | Illustrative private-data substitute |

Each source folder contains a README describing the planned extraction contract.

## Naming and raw-data rules

Use `source_subject_YYYY-MM-DD.ext` where an extraction date is meaningful, for
example `port_calls_2026-08-23.csv` or
`malaysia-singapore-latest.osm.pbf`. Never manually edit files in `raw/`; retain
the provider's original columns and encoding. Raw files must not be read directly
by the routing engine, dashboard, assistant, or graph loader.

## Canonical model

Canonical records include locations, routes, shipments, shipment route steps,
vessels, vessel positions, port metrics, and disruption events. Their contracts
are in `schemas/`. All timestamps are UTC ISO-8601 values. Source-specific IDs
must be resolved through `mappings/` before becoming canonical references.

Large time-series outputs such as AIS positions should normally be written as
Parquet; small master data may use CSV. The pipeline modules live under
`backend/data_pipeline/`. The first implemented source transform is the WPI port
normalizer, which writes `data/processed/wpi/ports.parquet`.

The unified PortWatch/WPI port master is written to
`data/processed/ports/port_master.parquet` and mirrored as
`canonical_ports.parquet`. It retains all valid PortWatch source ports: WPI
matches use their WPI `location_id`; unmatched source ports use
`PW_PORT_<portid>` with `canonical_source=PORTWATCH` and
`mapping_status=SOURCE_NATIVE`. `network_ports.parquet` and
`active_route_ports.parquet` are narrower membership sets and are populated
only from canonical route/shipment inputs.

## Processing flow

1. Place an untouched source extract in the matching `raw/` folder.
2. Run the source-specific parser.
3. Clean and resolve source entities using `mappings/`.
4. Normalize into the canonical schemas.
5. Run Pydantic and cross-reference validation.
6. Write validated files to `processed/`.
7. Load canonical data into the future PostgreSQL/Neo4j adapters.

No external downloads or provider credentials are required for the current
scaffolding.
