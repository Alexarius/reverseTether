# Issue 09 — Prompt suite, token counting, and fixture versioning

## Summary
Version the prompt fixtures and ensure prompt token counts are captured consistently for each run.

## Why this task exists
Prompt drift and guessed token counts can break comparability.

## Current milestone
Milestone 4 — Repeated measurement and soak automation

## Scope
- prompt fixture storage,
- prompt ids/versioning,
- token-count recording,
- soak prompt fixation,
- docs for how prompt changes are handled.

## Out of scope
- no GPU/NPU,
- no broad UI work,
- no major architecture changes.

## Allowed files
- `configs/**`
- `docs/**`
- `client/**`
- `tests/**`

## Acceptance criteria
- [ ] Prompt fixtures are versioned in the repo.
- [ ] Every run records a prompt id.
- [ ] Prompt token counts are recorded consistently.
- [ ] Soak prompt is fixed and documented.

## Validation
- inspect raw records and confirm prompt ids and token counts exist.

## Recommended tool
Copilot or manual with AI review.

## Reviewer focus
Comparability and version discipline.
