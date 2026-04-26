# results/

Raw JSONL logs and derived outputs.

## Purpose

This directory will store benchmark run outputs following the naming convention:

```
results/{YYYYMMDD_HHMMSS}_{node}_{backend}_{run_type}/
```

Each run folder will contain:

- `raw_metrics.jsonl` - raw run records
- `metadata.json` - run metadata
- `server_log.txt` - server-side logs

## Status

This directory now contains development and historical benchmark outputs. They are preserved for audit and implementation validation, but they are not automatically final dissertation evidence.

## Important

- Raw logs must be preserved for audit.
- Derived summaries must never replace raw logs.
- Historical short-prompt records, including `short_v1`, are development validation only.
- Smoke-suite records, including `_smoke_v1` prompt IDs, are development validation only.
- Final aggregation filters development results out by default.
- Final claims must use records marked with `prompt_suite_type=synthetic` and `cache_mismatch=false`.
- Mock outputs are development validation only. Store them under `scratch_mock/` or delete them after validation. They must not remain under top-level `results/` or `final_input/` for final submission.

## Development-Only Historical Results

The current historical folders were useful for validating the harness, phone path, OpenCL path, and aggregation workflow. They must not be used as final evidence because they use short development prompts and do not satisfy the final cache and dataset metadata gates.

Excluded from final claims:

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

The default final aggregation rule is:

```text
include only records where prompt_suite_type == "synthetic"
and cache_mismatch == false
and prompt_id is not short_v1/medium_v1/long_v1/soak_v1
and prompt_id does not contain "_smoke_"
```

Any summary that intentionally includes development results must label them as development/smoke evidence and keep them separate from final claims.

## Related docs

- `PROJECT_BRIEF.md` for result directory naming convention
- `EXPERIMENT_PROTOCOL.md` for logging schema
- `FINAL_RUN_MANIFEST.md` for final evidence inclusion and exclusion gates
