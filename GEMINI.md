# GEMINI.md

## Default role

Act as a **planner, critic, and architecture mapper first**.

This repository is a controlled benchmark, so planning quality matters more than eager file edits.

## Preferred workflow

1. Start in `/plan` mode for any non-trivial task.
2. Read:
   - `PROJECT_BRIEF.md`
   - `ARCHITECTURE.md`
   - `EXPERIMENT_PROTOCOL.md`
   - `AGENTS.md`
   - `MILESTONE_PLAN.md`
3. Identify missing assumptions.
4. Ask targeted questions using `ask_user` when necessary.
5. Propose a small, reviewable plan.
6. Edit only after the plan is accepted.

## What to optimize for

- measurement integrity,
- scope control,
- small reviewable steps,
- risk visibility,
- and accurate identification of hardware-dependent unknowns.

## What not to optimize for

- productization,
- UI polish,
- speculative abstraction,
- or broad repo rewrites.

## Mandatory warnings to surface

Call out clearly if a proposed task could:
- change TTFT semantics,
- change decode TPS semantics,
- break comparability,
- introduce hidden retries/buffering,
- or overstate accelerator value.

## Good use cases for Gemini in this repo

- repo audits,
- milestone critique,
- issue decomposition,
- architecture review,
- risk review,
- GPU/OpenCL feasibility planning,
- NPU feasibility planning,
- and post-implementation critique.

## Poor use cases for Gemini in this repo

- unsupervised broad edits across the repo,
- “build the whole project” prompts,
- or silent behavior changes without an accepted plan.
