# AGENTS.md

## Read this first

Before changing anything, read these files in order:

1. `PROJECT_BRIEF.md`
2. `ARCHITECTURE.md`
3. `EXPERIMENT_PROTOCOL.md`
4. `CODE_REVIEW.md`
5. `MILESTONE_PLAN.md`

If a task conflicts with any of those files, stop and ask for clarification.

## Project identity

This repository is for a **measurement-driven reverse-tethered LLM benchmark**.

The project is not trying to be:
- a product,
- a web app,
- a GUI-first experience,
- a cloud offload system,
- a multi-device split-inference system,
- or an NPU showcase at the expense of the core benchmark.

## Prime directive

Protect the integrity of the measurement boundary.

That means:
- TTFT is measured at the laptop boundary.
- Decode TPS is measured separately from TTFT.
- Cold, warm, and soak regimes are preserved.
- Model/settings comparability is preserved.
- Optional accelerator paths stay clearly separated from the mandatory baseline.

## Required working style

- Prefer **small, reviewable diffs**.
- For complex or ambiguous tasks, use **plan mode first**.
- If assumptions are missing, ask concise clarification questions before editing.
- Do not widen scope to “while I’m here” refactors unless explicitly asked.
- Do not silently rename or move core benchmark files without good reason.
- Keep documentation aligned with any behavior change.

## Hard do-not rules

Do not, without explicit approval:

- redefine TTFT or decode TPS,
- add GUI/product features ahead of the CLI benchmark harness,
- introduce model partitioning between laptop and phone,
- start NPU work before the core CPU benchmark path is stable,
- silently change the model, quantization, seed, context length, or stopping rules,
- claim that an accelerator is faster without controlled comparison support,
- remove raw logging,
- or hide validation failures.

## What “done” means

A task is only done when all of the following are true:

- the requested scope is complete,
- the task does not violate `EXPERIMENT_PROTOCOL.md`,
- relevant checks or smoke validations have been run,
- any TODOs or manual follow-ups are clearly called out,
- and the result is easy for a human reviewer to verify.

## Repository conventions

### General
- Prefer explicit, boring names over clever abstractions.
- Keep benchmark logic simple and auditable.
- Prefer flat data flows over frameworks.
- Prefer composition over large inheritance trees or agentic meta-systems.

### Logging
- Structured logs are mandatory.
- Fields affecting comparison must be explicit.
- Logs should be append-friendly and easy to aggregate.

### Benchmarking
- Keep a clear separation between:
  - transport setup,
  - request execution,
  - metric computation,
  - result storage,
  - and result aggregation.

### Analysis
- Derived summaries must never replace raw logs.
- Any filtering or exclusion rule must be documented.

## Human approval checkpoints

Stop and ask for approval before:

- adding new runtime dependencies that materially change the stack,
- changing benchmark semantics,
- changing run regime definitions,
- changing result directory layout if scripts depend on it,
- changing prompt suite contents,
- or collapsing optional accelerator paths into the core baseline.

## PR / task summary format

When you finish a task, summarize with:

1. **What changed**
2. **Why it changed**
3. **How it was validated**
4. **Any remaining manual steps**
5. **Any risk to measurement integrity**

## Agent-specific hints

### Copilot
Best used for local implementation in small slices.

### Codex
Best used to plan, critique, review, tighten tests, and refactor after the initial implementation pass.

### Gemini CLI
Best used in `/plan` mode first, especially when the repo is incomplete or the task is architectural.

### Cloud coding agents
Avoid for hardware-dependent bring-up unless the task is explicitly limited to docs, tests, parsers, or analysis code.

## If the repo is still young

When the codebase is mostly scaffolding, your job is not to invent more architecture.  
Your job is to build the minimum benchmark path that can produce trustworthy logs.
