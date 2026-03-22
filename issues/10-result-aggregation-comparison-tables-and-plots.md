# Issue 10 — Result aggregation, comparison tables, and plots

## Summary
Implement the first analysis layer that turns raw logs into comparison-ready tables and plots for laptop vs reverse-tethered conditions.

## Why this task exists
The dissertation needs derived evidence, not just raw JSONL files.

## Current milestone
Milestone 4 -> Milestone 7 bridge

## Scope
- aggregate raw logs,
- compute p50/p95 TTFT,
- compute average decode TPS,
- produce comparison tables,
- produce simple plots,
- preserve traceability back to raw run ids.

## Out of scope
- no rewriting of metric definitions,
- no hidden filtering,
- no GPU/NPU claims beyond what the data supports.

## Allowed files
- `analysis/**`
- `results/**` derived outputs only
- `docs/**`

## Acceptance criteria
- [ ] Tables compare the required core conditions.
- [ ] Derived metrics match the protocol.
- [ ] Raw-to-derived traceability exists.
- [ ] Output is suitable for later dissertation use.

## Validation
- manually cross-check one aggregated figure against raw logs.

## Recommended tool
Copilot for implementation, Codex for cross-check review.

## Reviewer focus
Accuracy and traceability over plot aesthetics.
