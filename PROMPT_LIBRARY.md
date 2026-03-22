# Prompt Library

These prompts are intentionally scoped for the current project.

---

## 1) ChatGPT Deep Research — repo audit before coding

Use this before implementation if the documents have changed.

> I am building a reverse-tethered LLM inference benchmark, not a polished app.  
> Read the repository control docs first: PROJECT_BRIEF.md, ARCHITECTURE.md, EXPERIMENT_PROTOCOL.md, AGENTS.md, CODE_REVIEW.md, and MILESTONE_PLAN.md.  
> Do not generate code.  
> Produce:
> 1. missing assumptions,
> 2. hidden methodology risks,
> 3. the smallest viable first three tasks,
> 4. any unclear terminology that should be fixed before coding,
> 5. a short critique of whether the current milestone plan is too ambitious.

---

## 2) Gemini CLI — safe planning pass

Use in `/plan` mode.

> Inspect this repository in read-only mode.  
> Treat it as a measurement-driven systems benchmark, not a product.  
> Read PROJECT_BRIEF.md, ARCHITECTURE.md, EXPERIMENT_PROTOCOL.md, AGENTS.md, and MILESTONE_PLAN.md first.  
> Then:
> - identify missing assumptions,
> - map the most likely repo layout,
> - propose the smallest viable first implementation PR,
> - identify any measurement contamination risks,
> - and ask targeted clarification questions before recommending edits.

---

## 3) Copilot Agent Mode — implementation prompt

Use this after creating a specific issue.

> Implement only the task described in this issue.  
> Read PROJECT_BRIEF.md, ARCHITECTURE.md, EXPERIMENT_PROTOCOL.md, AGENTS.md, CODE_REVIEW.md, and .github/copilot-instructions.md first.  
> Stay inside the allowed files listed in the issue.  
> Keep the diff minimal.  
> Do not widen scope.  
> If the issue is underspecified, ask one short clarification question before editing.  
> After changes, run the requested validation steps.  
> Summarize:
> 1. files changed,
> 2. validations run,
> 3. manual follow-ups,
> 4. any risk to measurement integrity.

---

## 4) Codex — review prompt

Use after an implementation slice.

> Review the current diff against AGENTS.md, CODE_REVIEW.md, PROJECT_BRIEF.md, and EXPERIMENT_PROTOCOL.md.  
> Focus on:
> - TTFT boundary drift,
> - decode TPS boundary drift,
> - logging ambiguity,
> - hidden comparability problems,
> - overengineering,
> - hardware assumptions that may fail on the actual laptop/phone setup.  
> Suggest minimal changes only.  
> If the diff is acceptable, say so explicitly and list the highest-risk area to watch next.

---

## 5) Codex — plan prompt for a hard issue

> Start in plan mode.  
> Read the repo control docs first.  
> Do not edit yet.  
> Turn this issue into:
> - assumptions,
> - risks,
> - smallest sub-steps,
> - expected files changed,
> - validation plan,
> - and one question for the human if needed.  
> Keep the plan compatible with the current milestone only.

---

## 6) Jules or GitHub cloud coding agent — safe use prompt

Only use this for hardware-independent tasks.

> Work only on this isolated task.  
> Do not attempt hardware-dependent validation.  
> Do not modify experiment semantics.  
> Limit changes to docs/tests/parsers/analysis unless the issue explicitly says otherwise.  
> Open a reviewable PR with a concise summary and list any manual local validation that still must be done on the laptop + phone setup.

---

## 7) NotebookLM — literature-to-task synthesis prompt

> Using the project sources in this notebook, produce a build-oriented decision brief with sections for:
> - architecture constraints,
> - metric definitions,
> - thermal risks,
> - GPU/OpenCL feasibility,
> - NPU feasibility,
> - and unresolved uncertainties.  
> For each section, provide:
> - what is well-supported,
> - what is uncertain,
> - what experiment resolves the uncertainty,
> - and whether it belongs in the mandatory scope or optional scope.

---

## 8) Human self-check prompt before merging

Ask an agent this before you accept a larger change.

> Give me a merge-risk review of this branch.  
> Ignore style nits.  
> Focus only on:
> - whether the branch still answers the dissertation question,
> - whether measurement semantics changed,
> - whether the benchmark is still reproducible,
> - and whether the scope has drifted beyond the current milestone.
