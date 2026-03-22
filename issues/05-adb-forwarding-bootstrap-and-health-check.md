# Issue 05 — ADB forwarding bootstrap and health check

## Summary
Implement the smallest repeatable ADB-forwarding lifecycle and endpoint health check so a benchmark run can fail early if the reverse-tethered path is broken.

## Why this task exists
ADB instability can contaminate measurements or waste benchmarking time if not checked explicitly.

## Current milestone
Milestone 3 — Reverse-tethered path

## Scope
- start or verify port forwarding,
- detect broken or missing forwarding,
- perform a small endpoint health check,
- surface actionable errors.

## Out of scope
- no benchmark matrix runner,
- no GPU/NPU,
- no plots,
- no dissertation export.

## Allowed files
- `scripts/**`
- `client/**`
- `docs/**`
- `tests/**`

## Acceptance criteria
- [ ] A benchmark preflight can verify forwarding status.
- [ ] Broken forwarding produces an actionable failure.
- [ ] Health check behavior is documented.
- [ ] The task does not alter metric semantics.

## Validation
- fresh reconnect test,
- successful health check,
- failed health check case recorded and explained.

## Recommended tool
Copilot Agent Mode locally.

## Reviewer focus
Does the health check improve reliability without distorting the benchmark?
