# Security

## Security Boundary

This is a local synthetic-data MVP. It currently has no authentication,
authorization, tenant isolation, or production data controls and must not be
presented as production-ready.

## Secrets

- `.env` and generated databases are ignored by Git.
- Secrets must never appear in source code, documentation, logs, issue evidence, or
  terminal output.
- `.env.example` contains names and safe placeholders only.
- Provider errors returned to clients should be sanitized.

## Input Validation

Pydantic validates enum values, duration bounds, risk bounds, and positive shipment
loads. The API verifies disruption location and route IDs against persisted master
data before writing rows. Validation that an identifier is semantically compatible
with a selected disruption type, and a dedicated interactive-origin/destination
error contract, remain pending.

## Browser Access

- FastAPI uses an explicit, non-credentialed CORS allowlist from `CORS_ORIGINS`.
- The default list contains only local React development and Compose frontend
  origins.
- Production-like deployments must replace the local defaults with a reviewed
  allowlist; wildcard origins and credentialed cross-origin access are not used.

## LLM Grounding

The deterministic graph service selects routes. The LLM receives a structured
decision record and may only explain it.

Current controls:

- strict JSON-schema response shape;
- backend-generated decision record;
- exact validation of delay saved and additional cost.

When `OPENAI_API_KEY` is absent, the API uses a transparent
`offline_deterministic` explanation generated from the same decision record. It
is not presented as a provider response and cannot change route selection. The
same fallback is used for provider connection or timeout failures; authentication
and other provider errors remain explicit failures.

Current limitation:

- free-form explanation text is not validated for invented identifiers, locations,
  routes, risk values, or other numerical claims.

`docs/issues/ISS-0003-strengthen-llm-grounding.md` tracks stronger grounding.

## Data and Logging

- Seed data is synthetic.
- Locations, routes, shipments, disruptions, and agent decisions are persisted in
  relational tables with foreign-key enforcement.
- Simulation snapshots, route comparisons, and optional LLM explanations contain
  JSON and may include operational route and shipment details.
- `confidence_score` remains null until a factual, testable definition is approved;
  the application must not invent confidence values.
- Logs must not include API keys or raw environment dumps.
- LLM prompts and responses should not be logged verbatim by default.
- Normalized PortWatch files are read through a read-only application adapter;
  raw provider responses are not exposed by the runtime endpoints.
- The assistant accepts a transitional browser context for unsaved interactive
  plans, but requests with `simulation_run_id` or `disruption_id` reconstruct
  context from server-owned persistence and ignore that browser context. The
  frontend must not use the assistant endpoint to submit secrets or production
  data.

Phase 4.1 external-signal endpoints accept validated structured evidence for
local matching only. They do not call providers, persist raw payloads, expose
provider responses, or grant signals authority to change network state. Route
sample points are representative metadata rather than navigation or tracking
data. Provider integration and payload retention require a separate reviewed
security and data-classification decision.

Phase 4.2A stores Open-Meteo raw Forecast and Marine responses only in the local
immutable snapshot directory configured by `OPEN_METEO_RAW_SNAPSHOT_DIRECTORY`.
The debug endpoint returns retrieval metadata rather than provider payloads.
Snapshot metadata contains request coordinates, variables, time bounds,
endpoints, cache status, and request identity, but no credentials. Cache files
are local runtime artifacts and are ignored by git. Provider failures remain
typed failures or explicit stale-cache results; they are never represented as
zero risk or safe weather.

## Assistant Authority Boundary

The assistant receives a decision-support context, never authority to choose or
modify a route. NetworkX and deterministic routing/scoring remain the source of
route decisions. Persisted identifiers are the preferred future request shape;
the current free-form context field exists only for compatibility with the
unsaved interactive planner and is not a trusted source once a record ID is
present.

## Supervisor and Trusted Tools

`POST /supervisor` accepts a natural-language request plus optional trusted
identifiers. It does not accept arbitrary browser context. The Supervisor can
select a tool, but every tool validates its Pydantic input and calls a repository
or deterministic service. Raw SQLAlchemy objects and NetworkX graphs never cross
the tool boundary.

The only write-capable Phase 3.5 tool is `simulate_disruption`. It accepts a
validated runtime/canonical target, disruption type, severity, and bounded
duration, then calls the same `run_simulation()` service as the dashboard. It
creates simulation history and scenario state only; it cannot modify canonical
locations, routes, shipments, recommendations, or the baseline graph.

Provider tool loops are bounded to four iterations. Unknown IDs, ambiguous
locations, invalid targets, unavailable routes, and tool errors are surfaced as
structured failures rather than filled with generated facts. The offline
Supervisor path is deterministic and does not require network access.

## Dependency and Deployment Review

Before a production-like deployment, add:

- authentication and authorization;
- request rate limits and payload limits;
- restricted CORS and trusted-host configuration;
- dependency pinning and vulnerability scanning;
- database backup, retention, and access controls;
- provider retry, timeout, and error-sanitization policies; and
- an explicit data classification and privacy review.
