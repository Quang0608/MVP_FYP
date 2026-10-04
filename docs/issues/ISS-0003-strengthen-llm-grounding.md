# ISS-0003: Strengthen LLM Grounding

## Status

`BACKLOG`

## Source

User story: `docs/user-stories/US-0003-receive-a-grounded-explanation.md`

## Context

The current validator checks only `delay_saved_hours` and `additional_cost`.
Free-form fields can still introduce unsupported routes, locations, identifiers,
risk scores, or numbers.

## Goal

Make unsupported operational claims detectable and reject or constrain them before
they reach API consumers.

## Scope

- Define which explanation fields may contain structured operational facts.
- Validate all machine-verifiable claims against the decision record.
- Add adversarial mocked-response tests.
- Document guarantees and residual limitations.

## Out of Scope

- Proving arbitrary natural-language text is universally hallucination-free.
- Allowing the LLM to alter route selection.

## Concerns

- Free-form natural language cannot be fully verified without constraining output.
- Overly strict matching may reject harmless prose or formatting differences.

## Proposal

Prefer structured identifiers and numeric facts over facts embedded only in prose.
Render user-facing prose from validated structured fields where practical. Reject
responses that cite values outside the supplied record and retain deterministic
fallback behavior.

## Approval

- Approved by: `PENDING`
- Approved at: `PENDING`

## Acceptance Criteria

- [ ] Every operational identifier and numeric claim is validated or generated
  deterministically.
- [ ] Unsupported route, location, ID, risk, delay, and cost examples are rejected.
- [ ] Valid grounded responses continue to pass.
- [ ] `docs/API.md`, `docs/SECURITY.md`, and continuity are updated.
- [ ] Grounded-explanation local demo passes.

## Local Verification

Pending.

## Demo Evidence

Pending.

## Completion Notes

Pending.
