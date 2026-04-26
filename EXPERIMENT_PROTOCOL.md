# Experiment Protocol

## Purpose

This document defines the **canonical measurement protocol** for the project.  
Any implementation detail that changes the meaning of these measurements requires explicit human approval.

## Canonical metrics

### 1) Time-to-First-Token (TTFT)

**Definition**: elapsed time between:
- the laptop client sending the request, and
- the laptop client receiving the first generated token.

TTFT intentionally includes:
- client-side request overhead,
- ADB/USB transport,
- server parsing and tokenization,
- prefill,
- and the computation needed to emit the first token.

This is the metric for **user-perceived prompt responsiveness**.

### 2) Decode throughput (Decode TPS)

**Definition**: generated token rate over the decode window only.

Operationally:
- record first token arrival time,
- record final token arrival time,
- count generated output tokens,
- compute decode TPS using the interval after streaming has started.

This is the metric for **sustained generation speed**, not prompt responsiveness.

## Canonical experimental conditions

### Required core comparison
1. **Laptop local baseline**: laptop CPU-only inference.
2. **Reverse-tethered phone baseline**: phone CPU-only inference over ADB.

### Required controlled extension
3. **Reverse-tethered phone GPU/OpenCL**, if stable enough for repeated runs.

### Exploratory only
4. **NPU-oriented path**, only if implementation is feasible without derailing the core benchmark.

## Fixed settings for a comparable run

Fill these before benchmarking and keep them fixed across like-for-like comparisons.

- **Model:** `Llama-3.2-1B-Instruct` (Baseline test model; up to `Meta-Llama-3.1-8B-Instruct` pending empirical RAM limit validation).
- **Quantization:** `Q4_0` (Strict requirement to ensure maximum compatibility and optimal kernel performance with the Adreno OpenCL backend).
- **Context length:** `2048` tokens (Enforced via `-c 2048` on the server launch).
- **Seed:** `42` (Fixed integer enforced in the API payload to guarantee identical token generation paths).
- **Temperature / sampling configuration:** `0.0` (Greedy decoding to enforce strictly deterministic output and eliminate TPS variance caused by different token choices).
- **Max new tokens:** `512` (Enforced via `"n_predict": 512` in the API payload to provide a long enough generation window for sustained TPS measurement).
- **Stop criteria:** Standard model EOS (End of Sequence) token, or hitting the 512 `n_predict` limit.
- **Server-side settings that affect throughput:**
  - GPU Offload: `-ngl 99` (OpenCL) or `-ngl 0` (CPU baseline).
  - Binding: `--host 127.0.0.1 --port 8080` (Required for the ADB bridge).
  - Threads: Default to physical cores (handled natively by `llama.cpp` unless explicit throttling is required for thermal control).

If GPU/OpenCL or NPU requires a different quantization or runtime format, treat that as a **separate condition**, not a hidden speedup.

## Prompt suite

Use the same prompt suite across all comparable conditions.

### Suite types

The project uses two prompt-suite roles:

- **Smoke / development suite**: short engineering prompts used for CLI smoke checks, parser validation, and local harness development. These prompts are not final dissertation evidence.
- **Synthetic final suite**: synthetic offline fixture prompts used for final evidence collection and dissertation claims.

The smoke suite may be referred to as `smoke_suite_v1` and is currently materialized as `configs/prompts/smoke_suite.json`. The synthetic final suite may be referred to as `dataset_suite_v1` and is currently materialized as `configs/prompts/dataset_suite_v1.json`.

Final claims must use records whose prompt metadata identifies the suite as `synthetic`. Historical `short_v1` records and `_smoke_v1` records are excluded from final evidence unless a later decision log entry explicitly changes that rule.

### Minimum prompt categories
- **Short prompt**: representative of light interactive use.
- **Medium prompt**: representative of normal use.
- **Long prompt**: representative of a prefill-heavy workload.
- **Soak prompt**: fixed prompt used repeatedly during sustained-load testing.

### Prompt suite rules
- Prompt text must be versioned in the repo.
- Prompt token counts must be recorded from the runtime/tooling, not guessed manually.
- Synthetic final fixtures must also record a fixed `fixture_prompt_token_count` for auditing the selected prompt text.
- Do not change prompt wording mid-series without versioning the suite.
- Keep the soak workload fixed.

### Prompt token count fields

Final records must distinguish static fixture metadata from runtime measurement:

- `fixture_prompt_token_count`: the precomputed token count stored with the fixture. This identifies the intended full prompt size and helps detect prompt drift.
- `runtime_prompt_eval_token_count`: the count reported by the runtime for the actual request, equivalent to the server-side prompt evaluation count.

`fixture_prompt_token_count` must never replace the runtime count in metric computation. Decode TPS continues to use generated output tokens over the decode window only.

If the runtime prompt evaluation count is unexpectedly lower than the fixture count for the same prompt, treat the run as a cache/state mismatch until proven otherwise.

## Operating regimes

### Cold start
Captures the first measured request after a fresh server process launch. Each cold repetition requires a server restart before the measured prompt. Any server startup or model-load duration must be recorded separately from TTFT unless a new metric is approved in `DECISION_LOG.md`.

### Warm start
Captures normal interactive use with the model already resident.

### Steady-state / soak
Captures thermally constrained sustained behavior after repeated requests.

## Repetitions

Each measured configuration should be repeated at least **five times**.  
Do not report a single “best run” as the result.

Minimum summary outputs:
- p50 TTFT,
- p95 TTFT,
- average decode TPS,
- spread / variance commentary,
- raw logs preserved for audit.

## Logging schema

Each run record **must** contain the following fields. Records missing mandatory fields are invalid and must be rejected by the benchmark harness.

**Critical reproducibility fields** (see DECISION_LOG.md DL-20260322-03):
- `model_sha256`: SHA-256 hash of the exact model file used.
- `llama_cpp_commit`: Full 40-character git commit hash of the llama.cpp build.
- `seed`: Fixed RNG seed (must be `42` for comparable runs).
- `quantization`: Must be `Q4_0` for core benchmark comparisons.

### Mandatory fields at minimum:

### Run identity
- timestamp,
- run id,
- benchmark condition id,
- regime (`cold`, `warm`, `soak`),
- repetition index.

### Device/runtime metadata
- laptop identifier,
- phone identifier,
- OS/build metadata,
- llama.cpp commit hash (**mandatory**, full 40-character git hash),
- llama.cpp build flags,
- server launch arguments,
- server mode (`local` / `phone`),
- accelerator mode (`cpu`, `gpu_opencl`, `npu_experimental`).

### Model/settings metadata
- model name (full HuggingFace-style identifier),
- model filename (exact GGUF filename),
- parameter count,
- quantization (must be `Q4_0`),
- model file SHA-256 hash (**mandatory**, 64 hex characters),
- context length,
- seed (**mandatory**, must be `42`),
- sampling config (temperature `0.0`),
- max new tokens (`n_predict`),
- stopping config.

### Prompt/output metadata
- prompt id,
- prompt token count,
- generated token count,
- stop reason.

### Timing metadata
- request sent timestamp,
- first token timestamp,
- final token timestamp,
- computed TTFT,
- computed decode TPS.

### Optional thermal / environment metadata
- device temperature if readable,
- battery / charging state if relevant,
- whether background apps were minimized,
- known anomalies.

## Fairness constraints

- Same prompt suite across comparable runs.
- Same generation settings across comparable runs.
- Same model and quantization across comparable runs unless explicitly documented otherwise.
- No hidden warm caches or preparation steps that exist in only one condition.
- Manual intervention must be recorded.

## Cache policy and acceptance gate

Final evidence must use a controlled cache policy. The benchmark must either disable prompt/KV cache reuse for measured requests or clear cache state by a documented server restart where that is compatible with the regime.

Final records must include:

- `cache_policy`
- `cache_expected`
- `cache_observed`
- `cache_mismatch`

For accepted final records, `cache_expected` must be `false`, `cache_observed` must be `"full_eval"`, and `cache_mismatch` must be `false`.

Cache mismatch detection is an acceptance gate. If cache reuse is observed, suspected from runtime prompt evaluation counts, or cannot be verified, the affected record is development-only and excluded from final dissertation claims.

## Success interpretation

### Strong success
Phone wins on TTFT and decode TPS, including after soak.

### Partial success
Phone wins on TTFT but not decode TPS.

### Neutral / negative but valid
Phone fails to outperform, but the explanation is backed by logs and careful interpretation.

## Threats to validity to track during implementation

- broken or unstable ADB forwarding,
- hidden retries,
- inconsistent model files or hashes,
- prompt drift,
- thermal throttling,
- background phone activity,
- quantization differences hidden inside “accelerator” claims,
- client overhead differences across conditions,
- network/server parser retries that inflate TTFT.

## Change-control rule

Any proposed change to:
- metric definitions,
- run regimes,
- prompt suite,
- fixed settings,
- or comparison conditions

must be recorded in `DECISION_LOG.md` before benchmarking continues.
