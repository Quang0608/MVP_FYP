# US-0004: Verify Locally Before Publication

## User Story

As the project owner, I want every issue processed and demonstrated locally before
it is pushed to GitHub, so that remote history contains reviewed, working changes.

## Context

Local issue files are the active source of truth. GitHub actions are publication
steps that require explicit user approval.

## Acceptance Criteria

- [ ] Every implementation change is linked to a focused local issue.
- [ ] Scope and material decisions are approved locally before implementation.
- [ ] Acceptance criteria, automated checks, and demo evidence are recorded.
- [ ] Concerns and continuity are updated before an issue is closed.
- [ ] The intended release scope passes the full local demo gate.
- [ ] No GitHub issue, push, or pull request occurs without explicit approval.
- [ ] Deferred issues are clearly identified before publication.

## Out of Scope

- Defining organization-wide GitHub governance.
- Automated production deployment.
- Requiring GitHub connectivity for local development.

## Risks

- Local issue records may drift unless code and docs are reviewed together.
- Manual demo evidence may be inconsistent without a stable checklist.

## Follow-up Issues

- `ISS-0001`: make the container demo functional
- Future: automate a repeatable local smoke/demo script

## Implementation Order

1. Maintain local issues, stories, concerns, and continuity.
2. Complete issues in dependency order.
3. Run tests, checks, and the documented local demo.
4. Review the local release scope with the user.
5. Publish to GitHub only after explicit approval.
