# Final Run Manifest

## Purpose

This manifest defines the final evidence collection procedure for the reverse-tethered LLM benchmark. It is an acceptance runbook for the supervisor-readable final run.

This document does not redefine TTFT or decode TPS. TTFT remains measured at the laptop request boundary, and decode TPS remains measured only over the post-first-token decode window as defined in `EXPERIMENT_PROTOCOL.md`.

## Final Evidence Scope

Final dissertation evidence includes only records that satisfy all of the following:

- `prompt_suite_type` is `final_dataset`.
- `prompt_suite_version` is the approved version for the run, initially `1.0.0`.
- The prompt fixture comes from the dataset-backed final suite.
- `cache_mismatch` is `false`.
- `fixture_prompt_token_count` and `runtime_prompt_eval_token_count` are both present.
- Raw records are stored in append-only `raw_metrics.jsonl` files.

Development, smoke, historical, and cache-contaminated runs remain useful for engineering validation, but they are excluded from final claims.

## Prompt Fixture Sources

The final methodology distinguishes two prompt suite roles:

| Role | Canonical suite name | Current materialized file | Purpose | Final evidence? |
|------|----------------------|---------------------------|---------|-----------------|
| Development smoke suite | `smoke_suite_v1.json` | `configs/prompts/smoke_suite.json` | CLI smoke checks and implementation validation | No |
| Dataset-backed final suite | `dataset_suite_v1.json` | `configs/prompts/dataset_suite_v1.json` | Final dissertation evidence runs | Yes |

The final dataset suite is derived from CNN/DailyMail-style summarization fixtures and records stable prompt IDs, dataset metadata, truncation rules, and fixture token counts. The materialized file name is `configs/prompts/dataset_suite_v1.json`.

## Result Sources

Final raw run source:

```text
results/{YYYYMMDD_HHMMSS}_{node}_{backend}_{run_type}/raw_metrics.jsonl
```

where records inside the directory identify:

- `prompt_suite_id`: `dataset_suite_v1`
- `prompt_suite_type`: `final_dataset`
- `prompt_suite_version`: `1.0.0`
- `cache_policy`: approved final policy
- `cache_mismatch`: `false`

Derived summaries may be written under:

```text
results/summaries/{aggregation_id}/
```

Derived summaries are never evidence by themselves. They must remain traceable to included raw run IDs and source result directories.

## Excluded Historical and Smoke Result Folders

The following existing folders are excluded from final dissertation claims because they use historical short prompts such as `short_v1`, do not contain final dataset prompt metadata, and include evidence of prompt-cache or server-state contamination:

```text
results/20260424_223730_s25ultra_cpu_matrix/
results/20260424_224011_s25ultra_cpu_matrix/
results/20260424_224025_s25ultra_cpu_matrix/
results/20260424_224037_s25ultra_cpu_matrix/
results/20260424_224051_s25ultra_cpu_matrix/
results/20260424_224105_s25ultra_cpu_matrix/
results/20260424_224217_s25ultra_opencl_matrix/
results/20260424_224952_s25ultra_opencl_matrix/
results/20260424_225007_s25ultra_opencl_matrix/
results/20260424_225022_s25ultra_opencl_matrix/
results/20260424_225040_s25ultra_opencl_matrix/
results/20260424_225100_s25ultra_opencl_matrix/
results/20260424_231042_yoga_cpu_matrix/
results/20260424_231628_yoga_cpu_matrix/
results/20260424_231648_yoga_cpu_matrix/
results/20260424_231712_yoga_cpu_matrix/
results/20260424_231730_yoga_cpu_matrix/
results/20260424_231749_yoga_cpu_matrix/
results/summaries/aggregation_20260424_232417/
```

The exclusion also applies to any future record with:

- `prompt_suite_type` missing, `smoke`, or `development`.
- `prompt_id` equal to `short_v1`, `medium_v1`, `long_v1`, or `soak_v1`.
- `prompt_id` ending in `_smoke_v1` or another smoke-suite version.
- `cache_mismatch` equal to `true`.
- Missing cache policy fields required by the final schema.

## Cache Policy

The final benchmark must not reuse prompt/KV cache state across measured requests unless a run is explicitly marked as non-final development data.

Approved final cache policies are:

| `cache_policy` | Meaning | Valid for final evidence? |
|----------------|---------|---------------------------|
| `disabled` | Server/runtime cache reuse is disabled for measured prompt evaluation. | Yes |
| `cleared_by_restart` | Cache state is cleared by a full server process restart before the measured request. | Yes for cold runs |
| `unsupported_unverified` | Cache behavior could not be controlled or verified. | No |

Final records must set:

- `cache_expected`: `false`
- `cache_observed`: `false`
- `cache_mismatch`: `false`

For final dataset prompts, `runtime_prompt_eval_token_count` must match the full fixture prompt evaluation. If the runtime reports a much smaller value, such as `1` after a repeated prompt, treat that as observed cache reuse and reject the record from final evidence.

If the runtime cannot disable cache reuse for warm or soak regimes, those regimes must not be accepted as final evidence until cache control is implemented or independently verified. Restarting between every soak request is not an acceptable substitute for soak evidence because it destroys the sustained-load condition.

## True Cold-Run Procedure

Each cold-run repetition must use a fresh server process.

1. Stop any existing llama.cpp server for the target condition.
2. Verify the endpoint is unavailable before relaunch.
3. Start the server with the approved model, quantization, context length, seed, and backend settings.
4. Capture server launch arguments and server log path.
5. Perform only non-generating readiness checks before the measured request.
6. Send exactly one measured final dataset prompt for that cold repetition.
7. Record TTFT from laptop request send to laptop first-token receipt.
8. Record decode TPS only over the decode window after first token arrival.
9. Stop the server after the repetition and archive `server_log.txt`.

Server startup or model-load duration may be recorded as setup metadata, but it must not be folded into TTFT unless a separate, explicitly named metric is added through the decision log.

## Warm-Run Procedure

Warm runs measure repeated requests with the model already resident while preserving prompt evaluation comparability.

1. Start the server once for the target condition.
2. Verify the approved cache policy is active.
3. Run the approved final dataset prompt sequence.
4. Reject any record where `runtime_prompt_eval_token_count` indicates prompt-cache reuse.
5. Preserve raw records and server logs.

## Soak Procedure

Soak runs measure sustained behavior after repeated requests and must use the same cache policy fields as cold and warm runs.

The soak prompt may be repeated only when cache reuse is disabled or independently verified as absent. If repeated soak prompts produce reduced runtime prompt evaluation counts, the soak run is development-only and excluded from final claims.

## Acceptance Gates

A final aggregation is acceptable only if all gates pass:

- Raw logs are present and append-only.
- Every included record uses `prompt_suite_type=final_dataset`.
- Every included record has dataset metadata fields populated.
- Every included record has `cache_mismatch=false`.
- Historical `short_v1` and smoke-suite records are filtered out by default.
- TTFT and decode TPS definitions match `EXPERIMENT_PROTOCOL.md`.
- Model, quantization, seed, context length, stopping rules, and generation settings remain fixed across comparable conditions.
- Cold runs show evidence of server restart per repetition.
- At least five repetitions exist for each reported comparable condition.
- Any filtering or exclusion is documented in the final summary.

If any gate fails, the affected records remain available for audit but must not support final dissertation performance claims.
