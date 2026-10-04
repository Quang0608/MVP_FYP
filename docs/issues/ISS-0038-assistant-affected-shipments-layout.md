# ISS-0038: Consolidate assistant insights in dashboard summaries

## Status

`DONE`

## Source

Direct user request: move the AI Supply Chain Assistant beside the affected
shipments table, remove redundant route/context prompt text, and move the
existing insight content into the Rerouting Summary.

## Scope

- Move the existing `AssistantPanel` into the affected-shipments dashboard row.
- Remove the introductory “Ask me…” display and redundant unaffected-route
  explanatory sentence.
- Preserve assistant interaction, backend calls, shipment table behavior, and
  route comparison behavior.
- Move the existing operational insight list into Rerouting Summary and remove
  the separate Recent AI Insights panel.
- Do not redesign the dashboard or add product features.

## Acceptance Criteria

- [x] Assistant panel renders beside the affected shipments table on desktop.
- [x] The requested “Ask me about the data currently on this dashboard.” text
  is no longer rendered.
- [x] The redundant unchanged-route explanatory display is no longer rendered.
- [x] Existing assistant input/chat and shipment interactions remain available.
- [x] Existing insight content renders within Rerouting Summary.
- [x] The separate `Recent AI Insights` title/panel is no longer rendered.
- [x] Frontend production build passes.

## Verification

- `cd frontend; npm run build`: passed with Vite 5.4.21.
- `git diff --check`: passed.
