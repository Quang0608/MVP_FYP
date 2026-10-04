# ISS-0011: Add Geographic Basemap

## Status

`DONE`

## Source

Direct user request: show a global geographic map with supply-chain points and
routes instead of the abstract SVG network view.

## Goal

Render the synthetic supply-chain network on an interactive geographic basemap
with real latitude/longitude positioning and route overlays.

## Scope

- Add Leaflet and React Leaflet dependencies.
- Replace the abstract SVG map with OpenStreetMap tiles.
- Render locations as geographic markers with labels/tooltips.
- Render base, selected, original, and disrupted route overlays.
- Preserve zoom, pan, reset/fit behavior supplied by Leaflet.

## Out of Scope

- Google Maps API keys or proprietary map services.
- Changing backend coordinates or route-selection logic.
- Editing or persisting geographic data.

## Concerns

- Basemap tiles require browser network access and must retain OpenStreetMap
  attribution.
- Production deployments should review tile-provider usage limits and policy.

## Acceptance Criteria

- [x] Frontend displays a geographic basemap behind the network.
- [x] Synthetic locations appear at their persisted coordinates.
- [x] Route overlays and disruption highlighting remain visible.
- [x] Map supports normal Leaflet zoom and pan controls.
- [x] Frontend production build passes.

## Local Verification

`npm install leaflet@^1.9.4 react-leaflet@^4.2.1` completed and `npm run build`
passed with the geographic map bundle.

## Demo Evidence

The map now fits all persisted locations on an OpenStreetMap basemap, shows
location tooltips, and overlays base/original/selected/disrupted route legs.

## Completion Notes

Replaced the abstract SVG network view with Leaflet in `frontend/src/App.jsx` and
added Leaflet assets/dependencies. OpenStreetMap attribution is rendered by the
map tile layer.
