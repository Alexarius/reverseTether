# GitHub Copilot Repository Instructions

This repository is a **measurement-driven benchmark** for reverse-tethered LLM inference.

## Always read first
- `PROJECT_BRIEF.md`
- `ARCHITECTURE.md`
- `EXPERIMENT_PROTOCOL.md`
- `AGENTS.md`
- `CODE_REVIEW.md`

## High-priority instructions
- Treat benchmark correctness and reproducibility as more important than cleverness.
- Prefer small diffs and simple logic.
- Keep metric semantics stable.
- Keep the CLI benchmark harness ahead of GUI or product work.
- Do not widen scope beyond the current issue.

## Metric rules
- TTFT is measured at the laptop client boundary.
- Decode TPS is measured separately from TTFT.
- Do not collapse or rename these metrics in ways that obscure their meaning.

## Scope rules
Do not introduce:
- model partitioning,
- cloud dependencies,
- NPU-first engineering,
- unnecessary frameworks,
- or unrelated UI work.

## Task handling
- Use the issue description as the contract.
- Stay inside the allowed files listed by the issue.
- If the task is underspecified, ask a short clarifying question.
- If you cannot fully validate due to missing hardware, complete the code path and clearly list the manual validation steps still required.

## Validation
When you finish a task, state:
1. what changed,
2. what you validated,
3. what remains manual,
4. and any risk to measurement integrity.

## Documentation
If behavior or methodology changes, update the relevant docs in the same task unless explicitly told not to.
