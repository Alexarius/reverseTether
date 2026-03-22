# Milestone Plan

## Overall rule

Only move to the next milestone when the current one has a clear exit condition.  
Do not use later milestones as a reason to skip disciplined work in earlier ones.

## Milestone 0 — Control docs and repo scaffold

### Goal
Create the repo control plane before implementation.

### Deliverables
- core docs committed,
- issue template committed,
- PR template committed,
- agent instructions committed,
- initial decision log created.

### Exit condition
The repo is ready for a planning pass by Gemini CLI or Codex.

### Best tool
- ChatGPT / Gemini for drafting and critique
- Gemini CLI `/plan` or Codex `/plan` for missing assumptions

---

## Milestone 1 — Laptop-only baseline

### Goal
Prove the measurement harness locally before ADB and phone complexity are introduced.

### Deliverables
- local baseline client path,
- TTFT and decode TPS computed correctly,
- structured logging,
- prompt suite wired in,
- at least one smoke benchmark run recorded.

### Exit condition
A human can run the local baseline twice and obtain two valid structured records.

### Best tool
- Copilot Agent Mode for implementation
- Codex for review and parser/test tightening

---

## Milestone 2 — Phone server bring-up

### Goal
Make the phone-side server launch path reproducible and auditable.

### Deliverables
- server launch procedure,
- server metadata capture,
- health-check behavior,
- manual troubleshooting notes.

### Exit condition
The phone endpoint can be launched repeatably and verified before a full benchmark run.

### Best tool
- Copilot for wrappers/docs
- Codex for review
- Gemini `/plan` if build/runtime assumptions are unclear

---

## Milestone 3 — Reverse-tethered path

### Goal
Make the laptop client talk to the phone server over ADB with the same metric semantics as the local baseline.

### Deliverables
- ADB forward bootstrap,
- endpoint health check,
- reverse-tethered request path,
- first end-to-end TTFT/TPS record.

### Exit condition
A single prompt can be run from the laptop through ADB to the phone and logged successfully.

### Best tool
- Copilot Agent Mode locally
- Codex review after each task slice

---

## Milestone 4 — Repeated measurement and soak automation

### Goal
Turn the system into a benchmark harness rather than a demo.

### Deliverables
- repeated run matrix,
- cold/warm/soak orchestration,
- run summaries,
- result aggregation,
- basic sanity checks.

### Exit condition
At least five repeated runs per condition can be executed and summarized.

### Best tool
- Copilot for scripts and runners
- Codex for review and testability improvements

---

## Milestone 5 — GPU/OpenCL validation

### Goal
Determine whether the GPU/OpenCL path is stable and worth reporting.

### Deliverables
- controlled GPU/OpenCL condition,
- explicit documentation of any quantization/runtime differences,
- comparison against CPU baseline,
- clear note if the path is unstable or not worthwhile.

### Exit condition
The report can honestly say either:
- GPU/OpenCL works and its benefit is measured, or
- GPU/OpenCL was evaluated and rejected for clear reasons.

### Best tool
- Gemini `/plan` first
- Copilot for implementation
- Codex for review and claim discipline

---

## Milestone 6 — Exploratory NPU track

### Goal
Investigate NPU only if the core benchmark is complete.

### Deliverables
- feasibility notes,
- tooling gap notes,
- implementation attempt only if low enough risk,
- explicit separation from the main benchmark claim.

### Exit condition
Either:
- the NPU path is clearly out of scope and documented as such, or
- a small exploratory condition exists without compromising the core study.

### Best tool
- ChatGPT/Gemini research first
- Gemini `/plan`
- extremely small implementation slices only

---

## Milestone 7 — Dissertation evidence pack

### Goal
Export results and traces in a form that supports writing.

### Deliverables
- clean summary tables,
- raw log references,
- method notes,
- threat-to-validity notes,
- figures with consistent labels.

### Exit condition
A later report chapter can be written without re-deriving metrics from memory.

### Best tool
- Copilot or Codex for export automation
- ChatGPT / Gemini for writing support and interpretation critique
