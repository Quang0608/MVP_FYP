# ISS-0001: Container Dashboard Connectivity

## Status

`IN_PROGRESS`

## Source

User story: `docs/user-stories/US-0004-verify-locally-before-publication.md`

## Context

The React frontend defaults to `http://localhost:8000` during local development.
Inside a container, browser requests need a same-origin proxy to reach the Compose
backend service.

## Goal

Make the frontend connect to the backend when started with Docker Compose while
preserving the current host-local default.

## Scope

- Proxy frontend `/api` requests to `http://backend:8000`.
- Document and verify the Compose startup path.
- Add a health-aware startup check if required by observed behavior.

## Out of Scope

- Production orchestration, TLS, ingress, or cloud deployment.
- Authentication and authorization.

## Concerns

- `depends_on` controls start order but does not guarantee backend readiness.

## Proposal

Update only `docker-compose.yml` initially. Validate the resolved Compose
configuration, start both services locally, and run the documented demo gate.
Add a health check only if startup timing proves unreliable.

## Approval

- Approved by: `PENDING`
- Approved at: `PENDING`

## Acceptance Criteria

- [x] React frontend container proxies API calls to the backend service.
- [x] Host-local frontend defaults to `http://localhost:8000`.
- [ ] Compose frontend loads locations, routes, and disruptions.
- [ ] Container-based Singapore closure demo passes.
- [x] `docs/DEPLOYMENT.md` and continuity are updated.

## Local Verification

The Compose service was replaced by the React frontend as part of `ISS-0008`.
Container runtime verification remains pending.

## Demo Evidence

Pending.

## Completion Notes

Pending.
