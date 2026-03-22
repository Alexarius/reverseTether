# Code Review and Measurement Integrity Checklist

Use this checklist for human review and for AI-assisted review passes.

## 1) Metric integrity

Ask:

- Is TTFT still measured from laptop request send to laptop first-token receive?
- Is decode TPS still computed only over the decode window?
- Has any code accidentally mixed prompt processing time into decode TPS?
- Has any retry, buffering, or parsing change altered the effective timing boundary?
- Are metric names in logs and docs still unambiguous?

## 2) Fairness and comparability

Ask:

- Are model, quantization, seed, context length, and generation settings held constant across comparable conditions?
- If not, is the condition explicitly marked as different rather than presented as a fair speedup?
- Is the same prompt suite used across like-for-like runs?
- Are cold, warm, and soak regimes preserved?

## 3) Reproducibility

Ask:

- Are raw logs still written?
- Does each run record enough metadata to reproduce or audit the condition?
- Are commit/build details recorded where they matter?
- Is manual setup documented if it affects the result?

## 4) Scope control

Ask:

- Did this task stay inside its allowed files?
- Did it widen scope beyond the issue description?
- Did it introduce unnecessary abstractions or frameworks?
- Did it add UI/product features before the benchmark harness was stable?

## 5) Platform realism

Ask:

- Does the code clearly separate local-only behavior from hardware-dependent behavior?
- If hardware is unavailable, does the change fail safely and document the manual validation step?
- Are Windows + ADB realities handled explicitly rather than assumed away?

## 6) Logging and evidence quality

Ask:

- Are prompt token count, output token count, stop reason, and timing fields logged explicitly?
- Are outlier-handling or filtering rules documented?
- Are derived results traceable back to raw run ids?

## 7) Optional accelerator caution

Ask:

- Is GPU/OpenCL treated as a separate, controlled condition?
- Is NPU still clearly exploratory?
- Has any code or comment overstated accelerator support or benefits?

## PR review comment skeleton

Use this exact structure if helpful:

### Review summary
- Scope fit:
- Metric integrity:
- Reproducibility:
- Risks:
- Required changes before merge:
- Nice-to-have follow-ups:

## Merge bar

Do not approve changes that:

- break metric semantics,
- weaken reproducibility,
- hide failed validations,
- or overstate claims relative to the measurements.
