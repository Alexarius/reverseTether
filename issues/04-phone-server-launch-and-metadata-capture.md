# Issue 04 — Phone server launch and metadata capture

## Summary
Create a repeatable way to document and/or wrap phone-side server bring-up so the llama.cpp server launch path is reproducible and benchmark metadata is captured.

## Why this task exists
The benchmark is not credible if the phone-side runtime is launched ad hoc with poorly tracked settings.

## Current milestone
Milestone 2 — Phone server bring-up

## Scope
- server launch procedure,
- reproducibility notes,
- metadata capture for build/runtime details,
- health check expectations.

## Out of scope
- no ADB forwarding yet,
- no benchmark matrix runner,
- no GPU/NPU implementation.

## Allowed files
- `docs/**`
- `scripts/**`
- `configs/**`

## Acceptance criteria
- [ ] The phone server launch path is documented or wrapped repeatably.
- [ ] Required runtime/build metadata is captured.
- [ ] A basic health-check procedure exists.
- [ ] Manual troubleshooting notes exist.

## Validation
- manual local verification on the actual device,
- record what was verified vs what remains manual.

## Recommended tool
Copilot for doc/wrapper work, Codex for review.

## Reviewer focus
Reproducibility and auditability.
