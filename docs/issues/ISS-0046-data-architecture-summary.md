# ISS-0046 Data architecture and schema summary

## Status

`DONE`

## Source

Direct user request: create a detailed Markdown summary of the current dataset
and data architecture.

## Context

The repository contains an active SQLite runtime dataset, normalized WPI and
PortWatch Parquet artifacts, raw provider snapshots, mapping tables, and JSON
schema contracts. Their roles are different and need to be documented clearly.

## Goal

Create a portable root-level Markdown summary that explains which datasets are
currently used by routing and represents the active runtime and ingestion
schemas in detail.

## Scope

- Document the active Asia runtime population and its record counts.
- Document SQLite runtime tables, relationships, compatibility rows, and
  persisted simulation outputs.
- Document raw, mapping, processed, and schema-contract layers.
- Record current Parquet artifact counts, fields, provenance, and limitations.
- Preserve the requested filename `summarization_of_data_architecutre.md`.

## Out of Scope

- Database migrations or data cleanup.
- Changes to routing, API behavior, or ingestion logic.
- Live provider downloads or database regeneration.

## Concerns

- Counts describe the local worktree and `reroute_agent.db` inspected on
  2026-10-13; they may change after future local runs.
- The SQLite file contains compatibility rows and historical simulation output
  in addition to the active Asia snapshot.
- PortWatch activity features are project-derived indicators, not official
  congestion or routing decisions.

## Proposal

Add the requested summary at the repository root. State the SQLite runtime
boundary first, distinguish it from processed ingestion artifacts, and include
schema tables for canonical domain records, storage tables, and provider data.

## Approval

- Approved by: `USER`
- Approved at: `2026-10-13T00:00:00+08:00`

## Acceptance Criteria

- [x] The requested Markdown file exists at the repository root.
- [x] The active dataset population and source boundaries are stated.
- [x] Runtime and processed schemas are represented with field-level detail.
- [x] Compatibility data, provenance, and known limitations are distinguished.
- [x] Continuity files and this issue are synchronized.
- [x] Documentation diff validation passes.

## Local Verification

- `git diff --check`: passed after documentation changes.
- Runtime tests and the local demo were not rerun because this is a
  documentation-only change.

## Demo Evidence

Not applicable: no runtime behavior or data was changed.

## Completion Notes

Added `summarization_of_data_architecutre.md`, this issue record, and factual
continuity entries. No application code, database records, raw extracts, or
processed data artifacts were changed.
