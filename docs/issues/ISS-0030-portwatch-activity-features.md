# ISS-0030 PortWatch activity baselines and current state

Status: DONE

## Proposal

Add a project-derived historical baseline and daily activity-feature layer for
the normalized PortWatch port observations. Build the latest port state for
future graph and shipment-route impact analysis without treating PortWatch
activity as proof of congestion or changing deterministic route selection.

## Acceptance criteria

- [x] Write per-port baselines to `port_baselines.parquet`.
- [x] Write daily features to `port_features.parquet`.
- [x] Mark the current five-day extract as `LIMITED_HISTORY`.
- [x] Write latest `current_port_state.parquet` with activity anomaly and
      operational status fields.
- [x] Attach supplied current state to matching NetworkX nodes through an
      explicit integration hook.
- [x] Identify candidate shipments whose planned route contains a flagged port.
- [x] Keep route weights and route selection unchanged.
- [x] Record the need to rebuild the baseline after several weeks or months of
      observations as a documented follow-up concern.

## Verification plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_portwatch_pipeline.py backend/tests/test_services.py -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
git diff --check
```

## Notes

The current extract covers 2026-08-10 through 2026-08-14 only. The derived
scores are local indicators and must not be labeled official IMF congestion,
risk, or delay metrics.
