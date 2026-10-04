# ISS-0039: Asia network and synthetic shipment population expansion

## Status

`DONE`

## Source

Direct user request: expand the runtime into a reproducible Asia-focused
semi-synthetic logistics network without changing routing, disruption policy, or
assistant architecture.

## Scope

- Select 40–70 existing geometry-bearing canonical WPI ports across ten Asian
  logistics regions without duplicating canonical port entities.
- Generate deterministic synthetic factories, warehouses/distribution centres,
  and customers near those ports.
- Generate a sparse directed route network and 150–300 valid synthetic
  shipments with ordered route legs and consistent progress.
- Load the generated dataset through the existing SQLite repository and
  canonical runtime models.
- Add topology, reproducibility, data-quality, and scenario regression tests.
- Keep frontend changes limited to rendering the active operational subset.

## Out of scope

Vessel/AIS tracking, news, RAG, new LLM behavior, new external APIs, Neo4j,
Kafka, PostgreSQL migration, and major dashboard redesign.

## Acceptance Criteria

- [x] Runtime SQLite seed uses canonical Asia ports plus synthetic enterprise
  entities through `RuntimeDataset`.
- [x] Fixed seed reproduces locations, routes, shipments, and ordered legs.
- [x] All generated routes and active shipment paths validate against the graph.
- [x] Singapore, Port Klang, congestion, and capacity scenarios remain valid.
- [x] Existing graph isolation and impact/rerouting semantics remain unchanged.
- [x] Required tests, compile checks, frontend build, and demo evidence are
  recorded.

## Verification Plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
cd frontend; npm run build
```

## Local Verification

- `backend/app/asia_dataset.py` generated 51 canonical real ports, 12
  factories, 14 warehouses/DCs, 14 customers, 150 directed routes, 220
  shipments, and 1,000 ordered legs with seed `20260913`.
- The generated topology has one connected component and 215 shipments with
  at least two feasible baseline paths. Countries represented are China, Hong
  Kong, India, Indonesia, Japan, Malaysia, Philippines, Singapore, South Korea,
  Sri Lanka, Thailand, and Vietnam.
- `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed: 71 tests.
- `.\.venv\Scripts\python.exe -m compileall -q backend dashboard` passed.
- `npm run build` passed with Vite after the sandbox-restricted attempt was
  retried using the environment's approved process-spawn permission.
- Default SQLite runtime counts are 91 active locations, 150 routes, and 220
  shipments; old compatibility master rows remain outside the active query.
- Scenario checks against the active database:
  - Singapore closure: 29 `REROUTE_REQUIRED`, 29 recommendations.
  - Port Klang closure: 8 `REROUTE_REQUIRED`, 8 recommendations.
  - Port Klang congestion: 8 `SHIPMENT_AT_RISK`, 0 recommendations.
  - Critical capacity reduction on `ASIA_R_0001`: 1 `REROUTE_REQUIRED`, 1
    recommendation.
- `git diff --check` passed. Docker was not rerun; prior local evidence records
  the Docker Desktop Linux engine as unavailable.

## Remaining Follow-up

Legacy SQLite master rows and the small fixture remain for compatibility and
history. A later migration issue should back up and compare those rows, migrate
history/foreign keys, and remove the compatibility aliases only after parity
evidence is recorded. No prohibited infrastructure or product feature was
introduced in this issue.
