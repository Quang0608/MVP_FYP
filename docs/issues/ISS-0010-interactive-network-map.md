# ISS-0010: Interactive Network Map Controls

## Status

`DONE`

## Source

Direct user request: make the React network map zoomable and pannable.

## Goal

Allow operators to inspect dense network routes by zooming and dragging the map.

## Scope

- Add wheel zoom, zoom in/out buttons, reset, and pointer drag-to-pan behavior.
- Preserve route, disruption, and legend rendering.
- Keep the map usable on desktop and touch-capable browsers.

## Acceptance Criteria

- [x] Users can zoom in and out with controls and the mouse wheel.
- [x] Users can drag the map to pan after zooming.
- [x] Reset returns the full network to its default view.
- [x] Production frontend build passes.

## Local Verification

`npm run build` completed successfully after adding the interactive map controls.

## Demo Evidence

The SVG map now supports wheel zoom, `+`/`-`/Reset controls, pointer drag-to-pan,
and a visible interaction hint.

## Completion Notes

Updated `NetworkMap` state and pointer handlers in `frontend/src/App.jsx`, with
map control styling in `frontend/src/styles.css`.
