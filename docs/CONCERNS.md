# Concerns

Unresolved risks, assumptions, and deferred work belong here and in a focused local
issue where implementation is required.

| ID | Status | Concern | Tracking issue |
|---|---|---|---|
| CON-001 | Closed | React frontend proxies `/api` requests to the Compose backend service. | `ISS-0001`, `ISS-0008` |
| CON-002 | Closed | Interactive planning and shipment analytics use a labeled deterministic explanation fallback when no OpenAI key is configured or the provider is unreachable. | `ISS-0002`, `ISS-0016`, `ISS-0019` |
| CON-003 | Open | LLM grounding validation checks only two numeric fields. | `ISS-0003` |
| CON-004 | Open | Metrics omit algorithm response time and explanation success/failure. | `ISS-0004` |
| CON-005 | Open | Dashboard and log strings contain corrupted Unicode characters. | `ISS-0005` |
| CON-006 | Open | Some tests assert sorting or accept either outcome without verifying intended behavior. | `ISS-0006` |
| CON-007 | Closed | Disruption location and route IDs are validated against persisted master data before simulation or planning. | `ISS-0007` |
| CON-008 | Open | Dependencies use lower bounds only, reducing build reproducibility. | Not yet scheduled |
| CON-009 | Open | FastAPI startup uses the deprecated `on_event` API. | Not yet scheduled |
| CON-010 | Open | No authentication, authorization, or production hardening exists. | Out of MVP scope |
| CON-011 | Open | Structured tables are created additively, but legacy `runs` conversion and rollback are not automated with a migration framework. | `ISS-0007` |
| CON-012 | Open | The React geographic basemap depends on browser access to OpenStreetMap tile services and their usage policy. | `ISS-0011` |
| CON-013 | Open | Provider-backed assistant prose is schema-constrained but not fully fact-checked beyond its supplied dashboard context; the deterministic fallback is the reliable local path. | `ISS-0021`, `ISS-0003` |
| CON-014 | Open | Canonical sample contracts and pipeline interfaces exist, but processed files are not yet loaded into the current SQLite repository or future PostgreSQL/Neo4j adapters. | `ISS-0024` |
| CON-015 | Open | The runtime now consumes normalized PortWatch activity through a read-only adapter and graph overlay, but activity does not yet modify route weights or select reroutes; calibrated operational penalties remain future work. | `ISS-0033` |
| CON-016 | Open | PortWatch activity baselines currently cover only 2026-08-10 through 2026-08-14, so all current baselines are marked `LIMITED_HISTORY`; activity indicators must not be treated as congestion, delay, or risk. | `ISS-0030` |
| CON-017 | Open | PortWatch disruption outputs are exposed through the runtime adapter and API, but they do not automatically trigger impact detection or rerouting; that decision boundary remains deliberately separate. | `ISS-0031`, `ISS-0033` |
| CON-018 | Open | 907 valid PortWatch source-native ports currently have null coordinates because the daily monitoring schema has no port geometry. They should not enter geospatial or operational graph workflows until geometry or manual validation is supplied. | `ISS-0032` |
| CON-019 | Open | Synthetic SQLite runtime master data and canonical WPI/PortWatch processed artifacts currently coexist; migration to one canonical operational runtime store is deferred. | `ISS-0035`, `ISS-0024` |
| CON-020 | Open | `/assistant` still accepts browser context for unsaved interactive plans; persisted-run requests now prefer server-reconstructed context, but the compatibility field should be retired after frontend/API migration. | `ISS-0035`, `ISS-0003` |
| CON-021 | Open | SQLite legacy columns do not yet persist canonical provenance or explicit shipment-leg progress/times; the repository derives runtime progress and keeps processed WPI/PortWatch artifacts separate until a parity-checked migration. | `ISS-0036` |
| CON-022 | Open | Port-master source-native PortWatch rows without coordinates remain valid processed entities but cannot enter the coordinate-bearing runtime graph until geometry or manual validation is supplied. | `ISS-0036`, `ISS-0032` |
| CON-023 | Open | Phase 3 congestion penalties and severity-based capacity reductions are controlled research assumptions, not calibrated operational forecasts. | `ISS-0037`; calibration deferred to P3 |

| CON-024 | Open | Phase 4.1 maritime weather sample points are deterministic representative exposure points, not vessel-navigation tracks or calibrated geospatial coverage. | ISS-0043; provider/geospatial calibration deferred to Phase 4.2+ |
| CON-025 | Open | Shipment exposure windows fall back to planned leg times, current ETA, and baseline route duration when exact schedules are missing; they are deterministic approximations, not live tracking. | ISS-0043; AIS/live schedule integration deferred |
| CON-026 | Open | Phase 4.2A Open-Meteo retrieval preserves provider payloads and validates structure, but does not yet normalize observations, score weather, or align forecasts to shipment traversal windows. | ISS-0044; Phase 4.2B |
| CON-027 | Open | Open-Meteo requests are opt-in and use a local file cache/snapshot store; provider availability, forecast model changes, and retention policy require later operational review. | ISS-0044; deployment/data-retention review deferred |

## Maintenance Rule

Add a concern when a requirement is ambiguous, a workaround is temporary, a
security or data risk exists, verification cannot run, or a design choice needs
human review. Close or supersede entries explicitly; do not silently delete history.
