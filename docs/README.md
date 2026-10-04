# Project Documentation

This directory is the maintained reference for the Supply Chain Reroute Agent.

## Technical Documents

- [API](API.md): current HTTP contracts and error behavior
- [Architecture](ARCHITECTURE.md): implemented boundaries, data ownership, and cleanup inventory
- [Database](DATABASE.md): persistence model and data ownership
- [Deployment](DEPLOYMENT.md): local startup, containers, and demo gates
- [Refactor plan](REFACTOR_PLAN.md): prioritized remaining stabilization work
- [Security](SECURITY.md): secrets, validation, LLM grounding, and known controls
- [Concerns](CONCERNS.md): unresolved risks and assumptions
- [Continuity](CONTINUITY.md): current state and handoff information

## Delivery Documents

- [Local issues](issues/README.md): implementation backlog and workflow
- [User stories](user-stories/README.md): product behavior and implementation order

Code and documentation must remain synchronized. Start with the relevant local issue,
make the smallest correct change, verify it locally, run the demo, and only then
prepare the work for an explicitly approved GitHub push.
