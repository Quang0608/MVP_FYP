# Local Issues

This folder is the authoritative issue tracker during local development.

## Statuses

- `BACKLOG`: captured but not approved for implementation
- `READY`: proposal and acceptance criteria are approved
- `IN_PROGRESS`: implementation is active
- `BLOCKED`: progress requires a decision or external change
- `VERIFY`: implementation is complete and local checks are pending
- `DONE`: acceptance criteria and local demo requirements passed
- `DEFERRED`: intentionally postponed with a recorded reason

## Workflow

1. Copy `TEMPLATE.md` to `ISS-NNNN-short-title.md`.
2. Link the source user story when applicable.
3. Write a narrow proposal and verification plan.
4. Obtain local approval for material product, contract, or design choices.
5. Implement and update related documentation.
6. Record commands and factual results under Local Verification.
7. Run the relevant local demo.
8. Mark the issue `DONE` only after every accepted criterion passes.

No local issue is automatically mirrored to GitHub. Migration, pushing, and remote
issue creation require explicit user approval after the local release scope passes.

## Local Backlog

| Order | Issue | Status |
|---:|---|---|
| 1 | [ISS-0001 Container frontend connectivity](ISS-0001-container-dashboard-connectivity.md) | IN_PROGRESS |
| 2 | [ISS-0002 Offline explanation fallback](ISS-0002-offline-explanation-fallback.md) | BACKLOG |
| 3 | [ISS-0003 Strengthen LLM grounding](ISS-0003-strengthen-llm-grounding.md) | BACKLOG |
| 4 | [ISS-0004 Complete evaluation metrics](ISS-0004-complete-evaluation-metrics.md) | BACKLOG |
| 5 | [ISS-0005 Repair text encoding](ISS-0005-repair-text-encoding.md) | BACKLOG |
| 6 | [ISS-0006 Strengthen deterministic tests](ISS-0006-strengthen-deterministic-tests.md) | BACKLOG |
| 7 | [ISS-0007 Structured persistence schema](ISS-0007-structured-persistence-schema.md) | DONE |
| 8 | [ISS-0008 React frontend migration](ISS-0008-react-frontend-migration.md) | IN_PROGRESS |
| 9 | [ISS-0009 Local React API CORS](ISS-0009-local-react-cors.md) | DONE |
| 10 | [ISS-0010 Interactive network map](ISS-0010-interactive-network-map.md) | DONE |
| 11 | [ISS-0011 Geographic basemap](ISS-0011-geographic-basemap.md) | DONE |
| 12 | [ISS-0012 Operator workspace filters](ISS-0012-operator-workspace-filters.md) | BACKLOG |
| 13 | [ISS-0013 Custom disruption builder](ISS-0013-custom-disruption-builder.md) | BACKLOG |
| 14 | [ISS-0014 Capacity utilization view](ISS-0014-capacity-utilization-view.md) | BACKLOG |
| 15 | [ISS-0015 Scenario comparison report](ISS-0015-scenario-comparison-report.md) | BACKLOG |
| 16 | [ISS-0024 Canonical data layer preparation](ISS-0024-canonical-data-layer.md) | DONE |
| 17 | [ISS-0025 Normalize WPI canonical ports](ISS-0025-wpi-canonical-ports.md) | IN_PROGRESS |
| 18 | [ISS-0026 PortWatch port and checkpoint pipeline](ISS-0026-portwatch-pipeline.md) | DONE |
| 19 | [ISS-0027 PortWatch name-only port matching](ISS-0027-portwatch-name-matching.md) | DONE |
| 20 | [ISS-0028 PortWatch WPI name-country matching](ISS-0028-portwatch-wpi-name-country.md) | DONE |
| 21 | [ISS-0029 Persistent WPI-PortWatch mapping table](ISS-0029-persistent-portwatch-mapping.md) | DONE |
| 22 | [ISS-0030 PortWatch activity baselines and current state](ISS-0030-portwatch-activity-features.md) | DONE |
| 23 | [ISS-0031 PortWatch disruption pipeline](ISS-0031-portwatch-disruption-pipeline.md) | DONE |
| 24 | [ISS-0032 Unified WPI-PortWatch port master](ISS-0032-unified-port-master.md) | DONE |
| 25 | [ISS-0033 Connect PortWatch state to the live runtime](ISS-0033-portwatch-runtime-integration.md) | DONE |
| 26 | [ISS-0034 Detect shipment impacts from PortWatch disruptions](ISS-0034-portwatch-impact-detection.md) | DONE |
| 27 | [ISS-0035 Architecture stabilization and scenario isolation](ISS-0035-architecture-stabilization.md) | DONE |
| 28 | [ISS-0036 Canonical runtime data integration](ISS-0036-canonical-runtime-data-integration.md) | DONE |
| 29 | [ISS-0037 Dynamic network state and disruption policy](ISS-0037-dynamic-network-state-and-disruption-policy.md) | DONE |
| 30 | [ISS-0038 Place assistant beside affected shipments](ISS-0038-assistant-affected-shipments-layout.md) | DONE |
| 31 | [ISS-0039 Asia network and shipment population expansion](ISS-0039-asia-network-shipment-expansion.md) | DONE |
| 32 | [ISS-0040 Default map node-only view](ISS-0040-default-map-node-only.md) | DONE |
| 33 | [ISS-0041 Agent-ready backend foundation and Supervisor](ISS-0041-agent-ready-backend-supervisor.md) | DONE |
| 34 | [ISS-0043 External signal foundation and network exposure](ISS-0043-external-signal-network-exposure.md) | IN_PROGRESS |
| 35 | [ISS-0044 Open-Meteo weather provider foundation](ISS-0044-open-meteo-weather-provider-foundation.md) | IN_PROGRESS |
