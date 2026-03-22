# Issue 06 — Streaming measurement boundaries and client timing

## Summary
Implement or harden the client-side timing path for streamed responses so TTFT and decode TPS are computed at the correct boundaries for both local and reverse-tethered conditions.

## Why this task exists
This is the highest-risk area for silent metric drift.

## Current milestone
Milestone 3 — Reverse-tethered path

## Scope
- timing capture for request sent / first token / final token,
- decode window computation,
- identical timing semantics across local and forwarded endpoints,
- clear field naming.

## Out of scope
- no prompt suite redesign,
- no aggregation/plotting,
- no GPU/NPU.

## Allowed files
- `client/**`
- `tests/**`
- `docs/**`

## Acceptance criteria
- [ ] Timing boundaries are explicit in code and docs.
- [ ] TTFT matches the project definition.
- [ ] Decode TPS matches the project definition.
- [ ] Raw run records contain the required timestamps and counts.
- [ ] The same logic works across both comparison conditions.

## Validation
- manual inspection of at least one raw record from each endpoint type,
- test or smoke-check decode TPS math if possible.

## Recommended tool
Copilot for implementation, Codex for adversarial review.

## Reviewer focus
Read this change as if it could ruin the dissertation if wrong.
