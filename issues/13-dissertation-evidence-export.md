# Issue 13 — Dissertation evidence export

## Summary
Produce a clean export path for tables, plots, and method notes so dissertation writing does not depend on reconstructing results manually.

## Why this task exists
Writing will go faster and be safer if benchmark outputs are already organized for citation and discussion.

## Current milestone
Milestone 7 — Dissertation evidence pack

## Scope
- export summary tables,
- export plot assets,
- link derived outputs to raw runs,
- include short method notes and caveat notes.

## Out of scope
- no rewriting of the dissertation itself,
- no new benchmark semantics,
- no additional conditions.

## Allowed files
- `analysis/**`
- `results/**`
- `docs/**`

## Acceptance criteria
- [ ] A human can find raw logs behind each exported summary.
- [ ] The export set supports later report writing.
- [ ] Caveats and limitations are preserved.

## Validation
Human review with spot-check against raw runs.

## Recommended tool
Copilot or Codex for automation, ChatGPT/Gemini for wording critique.

## Reviewer focus
Evidence hygiene and writing-readiness.
