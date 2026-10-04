# ISS-0033 Connect PortWatch state to the live runtime

Status: DONE

## Proposal

Connect the rebuilt WPI/PortWatch canonical outputs to the FastAPI and
NetworkX runtime through an application adapter. Runtime synthetic IDs remain
backward compatible, while a persistent mapping identifies their canonical
port records. The integration annotates locations and graph nodes with the
latest PortWatch state without changing deterministic route weights.

## Acceptance criteria

- [x] Runtime port IDs map to canonical WPI or PortWatch source-native IDs.
- [x] Application code loads PortWatch Parquet only through an adapter boundary.
- [x] `/locations` exposes PortWatch source and latest activity metadata when
  available.
- [x] The graph overlay contains PortWatch state for mapped runtime ports.
- [x] Current disruptions are available through a clean application adapter/API
  boundary without triggering rerouting.
- [x] Existing synthetic routing behavior remains unchanged.
- [x] Tests, compilation, and the Singapore integration check pass.

## Scope and assumptions

- The current runtime uses `P_SG`, `P_KL`, `P_TP`, and `P_LC`; these are mapped
  explicitly. `P_SG` maps to the PortWatch source-native Singapore record
  because the uploaded WPI master has no general Singapore port row.
- PortWatch state is optional at startup. If processed files are absent, the
  application continues using synthetic data with no external overlay.
- PortWatch activity is informational only. It does not block routes, alter
  edge weights, or select reroutes.
- The current application has no canonical route/shipment Parquet inputs, so
  source-native ports outside the runtime graph remain available in the data
  layer but do not become runtime nodes automatically.

## Verification plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
git diff --check
```

Manual API check: `/locations` contains `P_SG` with `source=PORTWATCH`, a
latest observation date, activity score, and operational status; the graph
node has the same state; `/portwatch/disruptions` returns canonical active
PortWatch disruptions.

Observed verification result: 34 backend tests passed, backend/dashboard
compilation passed, the frontend production build passed, and the manual
Singapore API check returned HTTP 200 with PortWatch metadata.
