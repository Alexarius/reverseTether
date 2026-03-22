# Issue 12 — GPU/OpenCL validation track

## Summary
Add a controlled GPU/OpenCL validation path only after the CPU baseline is stable, and document any runtime or quantization differences as a separate condition.

## Why this task exists
GPU/OpenCL is mandatory to validate, but it must not contaminate the core baseline.

## Current milestone
Milestone 5 — GPU/OpenCL validation

## Scope
- controlled GPU/OpenCL condition,
- explicit runtime/quantization documentation,
- comparison against CPU phone baseline,
- stability notes.

## Out of scope
- no NPU work in the same issue,
- no hidden changes to the core CPU baseline,
- no claim inflation.

## Allowed files
- relevant runtime/config docs
- accelerator-specific config paths
- analysis docs/scripts if needed for separate reporting

## Acceptance criteria
- [ ] GPU/OpenCL is reported as a distinct condition.
- [ ] Any quantization/runtime change is explicit.
- [ ] Stability or instability is documented.
- [ ] The core CPU comparison remains intact.

## Validation
- repeated runs only if the path is stable enough,
- otherwise document rejection clearly.

## Recommended tool
Gemini `/plan` first, then Copilot, then Codex review.

## Reviewer focus
Separation of conditions and honesty of claims.
