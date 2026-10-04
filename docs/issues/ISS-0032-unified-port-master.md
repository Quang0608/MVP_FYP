# ISS-0032 Unified WPI-PortWatch port master

Status: DONE

## Proposal

Keep WPI as the preferred canonical port master while retaining valid
PortWatch-only ports as source-native canonical records. Remove the current
inner-join loss from daily PortWatch monitoring and disruption affected-port
relations. Keep canonical recognition separate from membership in the current
logistics graph and from use by active shipment routes.

## Implementation plan

1. Add a unified `port_master.parquet` with WPI and PortWatch provenance,
   stable IDs, and explicit mapping status.
2. Promote every PortWatch source port with a valid source ID/name into the
   master: WPI matches retain their WPI ID; unmatched ports receive
   `PW_PORT_<source_port_id>` and `SOURCE_NATIVE` status.
3. Add separate `canonical_ports`, `network_ports`, and
   `active_route_ports` set outputs. Do not infer synthetic runtime graph
   membership from WPI/PortWatch records.
4. Rebuild daily PortWatch monitoring using the unified ID mapping so matched
   and source-native ports are retained.
5. Rebuild disruption affected-port relations so unresolved WPI matches become
   valid source-native relations; preserve checkpoint tokens as unresolved.
6. Add validation, reports, tests, documentation, and live output summaries.

## Data contract

Port master fields:

`location_id,name,location_type,country,latitude,longitude,unlocode,wpi_number,canonical_source,source_entity_id,mapping_status,source_port_id`

Statuses are `MATCHED_WPI`, `SOURCE_NATIVE`, `MANUAL_MATCH`, and
`UNRESOLVED`. A source-native record is recognized by PortWatch provenance; it
is not automatically part of the operational graph.

## Assumptions and risks

- WPI-matched records retain WPI coordinates and identity.
- The current daily PortWatch port schema has no coordinates, so source-native
  latitude/longitude remain null until a source port geometry/master extract or
  manual validation supplies them.
- The current MVP graph uses synthetic IDs (`P_SG`, `P_KL`, etc.), so network
  and active-route sets are empty unless canonical route/shipment files are
  supplied. No graph membership is guessed.
- Existing PortWatch mapping rows marked review/unmapped are still valid
  source-native candidates; they are not forced into a WPI match.

## Acceptance criteria

- [x] WPI remains the preferred identity when a persistent mapping is valid.
- [x] Unmatched PortWatch ports are retained with `PW_PORT_<portid>` IDs.
- [x] Daily monitoring retains source-native PortWatch observations.
- [x] Disruption affected-port relations retain valid source-native ports.
- [x] Unresolved non-port/checkpoint tokens remain reported.
- [x] Canonical, network, and active-route sets are separate outputs.
- [x] No rerouting or dashboard behavior changes.
- [x] Tests, compilation, and output validation pass.

## Local verification

The live August 10-16 PortWatch extract was rebuilt with the unified mapping:

- `port_master.parquet`: 4,709 canonical ports - 3,802 WPI and 907
  PortWatch source-native records.
- `port_monitoring.parquet`: 10,320 normalized daily rows from 10,325 raw
  rows; 10 duplicate canonical location/date rows were aggregated while
  `port_monitoring_source_links.parquet` preserves all 10,325 source links.
- `port_features.parquet`: 10,320 rows; `current_port_state.parquet`: 2,064
  latest port states.
- `disruption_affected_ports.parquet`: 42 resolved canonical relations,
  including `PW_PORT_port2177` / Nakagusukuwan; one `chokepoint6` token remains
  unresolved because it is a checkpoint token, not a WPI or PortWatch port.
- `current_disruptions.parquet`: one active event as of
  `2026-08-30T00:00:00Z`.
- `network_ports.parquet` and `active_route_ports.parquet` are empty because
  the current MVP runtime has synthetic NetworkX IDs and no canonical route
  or shipment Parquet inputs; no graph membership was guessed.

Verification commands:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m compileall -q backend dashboard
git diff --check
```

Observed verification result: `32 passed`; compilation completed successfully;
`git diff --check` reported no content errors.
