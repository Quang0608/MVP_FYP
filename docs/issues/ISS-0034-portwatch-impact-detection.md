# ISS-0034 Detect shipment impacts from PortWatch disruptions

Status: DONE

## Proposal

Use active normalized PortWatch disruptions as an input to a deterministic
impact detector. Resolve their canonical affected locations against the
runtime graph, inspect each active shipment's remaining planned route, and
return evidence when a disrupted port is still ahead of the shipment.

Detection is not rerouting. The output is a candidate set for a later
rerouting-evaluation step.

## Acceptance criteria

- [x] A shipment using an affected port on its remaining route is returned.
- [x] A shipment whose route does not use the affected port is not returned.
- [x] A shipment that has already passed the affected port is not returned.
- [x] A disruption with no dependent shipments produces no impact action.
- [x] Evidence includes event ID, runtime/canonical affected location,
  shipment IDs, and a deterministic reason.
- [x] Active PortWatch impacts are exposed without automatic rerouting.
- [x] Existing manual disruption and routing behavior remains unchanged.
- [x] Tests, compilation, and the local API check pass.

## Scope and assumptions

- PortWatch disruption relations provide canonical location IDs; the graph node
  overlay provides the canonical-to-runtime identity bridge.
- `current_location_id` is included in the remaining route. A port before that
  position is considered passed and is not an impact.
- Shipments with status `DELIVERED`, `CANCELLED`, or `COMPLETED` are treated as
  inactive. The current synthetic seed shipments are active.
- The detector does not block routes, mutate shipments, persist a reroute, or
  call an LLM.

## Verification plan

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
git diff --check
```

Manual API check: `/portwatch/impacts` returns only active shipment impacts
whose remaining route intersects a canonical active PortWatch disruption.

## Local verification

- Four critical detector cases passed: remaining-route intersection, no route
  intersection, already-passed port, and no dependent shipments.
- Fixture API check returned a structured impact for `S001` with runtime port
  `P_SG`, canonical port `PW_PORT_port1201`, and reason
  `remaining route contains disrupted port`.
- The live current snapshot returned HTTP 200 with zero impacts because its one
  active event affects unresolved `chokepoint6`, not a canonical runtime port.
- Full verification passed: 38 backend tests, backend/dashboard compilation,
  and `git diff --check`.
