# ISS-0009: Allow Local React API Requests

## Status

`DONE`

## Source

User report: React development server receives `OPTIONS ... 405 Method Not
Allowed` from FastAPI.

## Context

The Vite development server runs on port 5173 while FastAPI runs on port 8000.
Browser requests are cross-origin, and the API currently has no CORS middleware,
so preflight requests are rejected before the frontend can load network data.

## Goal

Allow the documented local React origins to call the FastAPI API while keeping
the allowed-origin list explicit and configurable.

## Scope

- Add configurable CORS origins to backend settings.
- Register FastAPI CORS middleware with non-credentialed local access.
- Add a preflight regression test.
- Document the setting and local behavior.

## Out of Scope

- Wildcard production CORS.
- Authentication, cookies, or credentialed cross-origin requests.

## Acceptance Criteria

- [x] `OPTIONS /locations` from `http://localhost:5173` returns `200` with the
      expected CORS headers.
- [x] `GET /locations` from the same origin includes an allow-origin header.
- [x] Unlisted origins are not granted CORS access.
- [x] Existing backend tests and compilation pass.
- [x] API, security, deployment, and continuity docs are updated.

## Local Verification

`.\.venv\Scripts\python.exe -m pytest backend/tests -q`: 13 passed.
`.\.venv\Scripts\python.exe -m compileall -q backend`: passed.
The CORS regression test confirms the local React origin is allowed and an
unlisted origin receives no allow-origin header.

## Demo Evidence

The reported browser preflight failure is addressed by the configurable CORS
middleware. A live `OPTIONS /locations` request returned `200` with
`Access-Control-Allow-Origin: http://localhost:5173` after the reload.

## Completion Notes

Added `CORS_ORIGINS` settings, FastAPI middleware, regression coverage, and
security/deployment documentation. Existing deprecation warnings remain outside
this issue.
