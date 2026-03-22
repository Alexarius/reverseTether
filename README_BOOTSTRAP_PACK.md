# Reverse-Tethered LLM Benchmark Bootstrap Pack

This pack is a first-pass control plane for the reverse-tethered benchmark project. It is meant to be committed **before** serious implementation work starts.

## What this pack is for

The project is a **measurement-driven feasibility study**, not a polished product. The point of these documents is to:

- keep the benchmark honest,
- keep AI agents inside scope,
- make each task small and reviewable,
- preserve TTFT/TPS semantics across the whole repo,
- and stop the project from drifting into unrelated optimization or UI work.

## Recommended default tool split

- **ChatGPT Deep Research / Gemini Deep Research / NotebookLM**: literature review, uncertainty tracking, issue decomposition, architecture critique.
- **Copilot Agent Mode in the IDE**: primary local implementation on the machine that actually has the laptop, phone, ADB, and logs.
- **Codex CLI / Codex app**: plan difficult tasks, review diffs, tighten tests, critique measurement integrity, and refactor after implementation.
- **Gemini CLI `/plan`**: safe, read-only repo analysis before large edits.
- **Jules / GitHub cloud coding agent**: only after the repo has clear instructions, tests, and hardware-independent tasks.

## Suggested repository layout

This is a recommendation, not a law:

```text
/
├─ PROJECT_BRIEF.md
├─ ARCHITECTURE.md
├─ EXPERIMENT_PROTOCOL.md
├─ AGENTS.md
├─ CODE_REVIEW.md
├─ DECISION_LOG.md
├─ MILESTONE_PLAN.md
├─ PROMPT_LIBRARY.md
├─ DAY0_RUNBOOK.md
├─ PLANS_TEMPLATE.md
├─ .github/
│  ├─ copilot-instructions.md
│  ├─ PULL_REQUEST_TEMPLATE.md
│  ├─ ISSUE_TEMPLATE/
│  │  └─ agent-task.md
│  └─ instructions/
│     └─ benchmark.instructions.md
├─ docs/
├─ client/
├─ scripts/
├─ analysis/
├─ configs/
├─ results/
└─ tests/
```

## Day-0 usage sequence

1. Create the repo and drop these files in at the root.
2. Read `PROJECT_BRIEF.md`, `ARCHITECTURE.md`, and `EXPERIMENT_PROTOCOL.md`.
3. Fill in the obvious TODOs:
   - primary model,
   - quantization,
   - llama.cpp commit/build details,
   - chosen laptop harness language/tooling,
   - prompt suite,
   - result directories.
4. Commit the docs as **initial control docs**.
5. Run **Gemini CLI `/plan`** or **Codex `/plan`** over the repo and ask for missing assumptions.
6. Turn the issue drafts in `/issues` into actual GitHub issues.
7. Use **Copilot Agent Mode** for the first local implementation issue.
8. Use **Codex** to review the resulting diff against `CODE_REVIEW.md`.
9. Keep one human-owned decision log entry for every change that affects methodology.

## Non-negotiable project guardrails

- Do **not** redefine TTFT or decode TPS without explicit human approval.
- Do **not** add GUI/product polish before the CLI benchmark harness is stable.
- Do **not** jump to NPU work before the CPU baseline and ADB path are working.
- Do **not** silently swap models, quantization, seeds, context length, or stopping rules mid-comparison.
- Do **not** let multiple agents modify the same files in parallel.

## Most important starting point

The first valuable result is **not** “the whole system exists.”  
It is:

1. a local laptop-only baseline,
2. a phone-side server that can be launched repeatably,
3. an ADB tunnel health check,
4. end-to-end TTFT/TPS logging at the laptop boundary,
5. repeated cold/warm/soak runs with structured output.

Once those exist, the optional GPU/OpenCL and exploratory NPU work become much safer.
