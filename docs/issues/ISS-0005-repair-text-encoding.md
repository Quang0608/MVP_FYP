# ISS-0005: Repair Text Encoding

## Status

`BACKLOG`

## Source

Direct review finding.

## Context

User-facing separators, arrows, and dashes are stored as mojibake such as `â†’`,
`â€”`, and `Â·` in dashboard and logger strings.

## Goal

Render readable text consistently in source, logs, and the frontend.

## Scope

- Replace corrupted characters with correct UTF-8 or stable ASCII equivalents.
- Verify repository text files are UTF-8.
- Add a lightweight regression check if practical.

## Out of Scope

- Full visual redesign or localization.

## Concerns

- PowerShell and terminal code pages may display correct file bytes incorrectly, so
  validation must inspect actual UTF-8 content and the rendered dashboard.

## Proposal

Use plain ASCII arrows/separators where typography is not important and correct
UTF-8 punctuation elsewhere. Verify with source inspection, compilation, and the
local dashboard.

## Approval

- Approved by: `PENDING`
- Approved at: `PENDING`

## Acceptance Criteria

- [ ] No known mojibake remains in tracked source or documentation.
- [ ] Route labels and metrics render correctly in the dashboard.
- [ ] Backend logger strings are readable.
- [ ] Relevant tests/checks and local visual demo pass.
- [ ] Continuity is updated.

## Local Verification

Pending.

## Demo Evidence

Pending.

## Completion Notes

Pending.
