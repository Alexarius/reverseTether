# Issue 02 — Select the primary model and record reproducibility metadata

## Summary
Finalize the first model/quantization choice and document the reproducibility metadata that must be captured for all runs.

## Why this task exists
The benchmark cannot be meaningfully compared if the model choice and metadata requirements remain vague.

## Current milestone
Milestone 0 -> Milestone 1 transition

## Scope
- choose the primary model,
- choose the primary quantization,
- document required metadata fields,
- document any known constraints for laptop vs phone comparability.

## Out of scope
- no code generation,
- no benchmark runner,
- no ADB work,
- no GPU/NPU implementation.

## Allowed files
- `PROJECT_BRIEF.md`
- `EXPERIMENT_PROTOCOL.md`
- `DECISION_LOG.md`
- optional supporting docs

## Acceptance criteria
- [ ] Primary model is named explicitly.
- [ ] Quantization is named explicitly.
- [ ] Required run metadata is recorded.
- [ ] Any uncertainty is listed, not hidden.
- [ ] A decision-log entry is added.

## Validation
Human review only.

## Recommended tool
ChatGPT Deep Research or Gemini research/planning pass.

## Reviewer focus
Is the choice documented clearly enough that implementation agents will not guess?
