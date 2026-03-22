# Issue 08 — Benchmark matrix runner for cold, warm, and soak

## Summary
Create the smallest runner/orchestration layer that can execute repeated benchmark runs under cold, warm, and soak regimes without manual timing.

## Why this task exists
The project becomes a real benchmark only when repeated measurement is automated.

## Current milestone
Milestone 4 — Repeated measurement and soak automation

## Scope
- repeated execution,
- regime selection (`cold`, `warm`, `soak`),
- repetition count,
- raw logging integration,
- failure handling for incomplete runs.

## Out of scope
- no GPU/NPU yet,
- no dissertation export,
- no unrelated refactors.

## Allowed files
- `scripts/**`
- `client/**`
- `configs/**`
- `docs/**`
- `tests/**`

## Acceptance criteria
- [ ] A repeated-run matrix can be executed.
- [ ] Cold, warm, and soak regimes are represented explicitly.
- [ ] Repetition count is configurable.
- [ ] Raw logs are written per run.
- [ ] Failures are visible rather than silently skipped.

## Validation
- execute a small dry run,
- inspect produced run ids and regime labels,
- confirm repeated runs do not overwrite each other.

## Recommended tool
Copilot for implementation, Codex for review.

## Reviewer focus
Is the runner trustworthy enough to support the later comparison chapter?
