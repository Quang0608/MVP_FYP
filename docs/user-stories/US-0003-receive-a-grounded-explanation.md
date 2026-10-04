# US-0003: Receive a Grounded Explanation

## User Story

As a supply-chain operator, I want a clear explanation of a deterministic route
decision, so that I can understand its trade-offs without the AI inventing facts.

## Context

The backend supplies a structured decision record. OpenAI structured output
constrains response shape, while backend validation currently checks two numerical
fields.

## Acceptance Criteria

- [ ] The deterministic backend remains the sole route-selection authority.
- [ ] Explanation inputs contain only the minimum structured decision record.
- [ ] Operational identifiers and numbers are validated against that record.
- [ ] Unsupported claims are rejected or replaced by deterministic output.
- [x] Offline mode is clearly identified and remains demonstrable.
- [ ] Provider failures are safe, understandable, and do not expose secrets.
- [ ] Security and API guarantees are documented.

## Out of Scope

- Allowing an LLM to create or select routes.
- General-purpose supply-chain question answering.
- Retrieval-augmented generation over external policy documents.

## Risks

- Free-form prose cannot be perfectly fact-checked without stronger structural
  constraints.
- A fallback that looks like provider output may mislead users.

## Follow-up Issues

- `ISS-0002`: offline explanation fallback
- `ISS-0003`: strengthen LLM grounding
- `ISS-0004`: record explanation state in metrics

## Implementation Order

1. Add a transparent deterministic fallback.
2. Strengthen structured grounding and adversarial tests.
3. Add explanation-state metrics.
4. Run provider-mocked and offline local demos.
