# Issue 11 — Thermal metadata and steady-state interpretation notes

## Summary
Capture whatever thermal/environment metadata is realistically available and document how steady-state performance should be interpreted.

## Why this task exists
A reverse-tethered win that disappears under soak is still an important result.

## Current milestone
Milestone 4 / Milestone 7 support

## Scope
- practical thermal metadata capture where available,
- soak-run notes,
- steady-state interpretation guidance,
- anomaly recording.

## Out of scope
- no speculative thermal model,
- no claim inflation,
- no major benchmark redesign.

## Allowed files
- `docs/**`
- `configs/**`
- optional logging-related files

## Acceptance criteria
- [ ] The repo documents what thermal metadata is available and what is not.
- [ ] Soak interpretation notes are explicit.
- [ ] Background anomalies can be recorded in run logs or notes.

## Validation
Human review.

## Recommended tool
ChatGPT/Gemini for critique, Copilot for any small logging-doc updates.

## Reviewer focus
Interpretation quality and honesty about missing telemetry.
