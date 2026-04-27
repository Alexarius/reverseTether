# Logging Schema Documentation

This document describes the structured logging schema for the reverse-tethered LLM benchmark.

## Result Directory Structure

Results are organized per the PROJECT_BRIEF.md convention:

```
results/
  {YYYYMMDD_HHMMSS}_{node}_{backend}_{run_type}/
    metadata.json       # Run configuration and environment
    raw_metrics.jsonl   # Append-only benchmark records (one JSON object per line)
```

### Directory Naming Variables

- `{YYYYMMDD_HHMMSS}`: Timestamp when the run started
- `{node}`: `yoga` (laptop) or `s25ultra` (phone)
- `{backend}`: `cpu`, `opencl`, or `npu_experimental`
- `{run_type}`: `cold`, `warm`, or `soak`

### Example

```
results/20260325_143052_yoga_cpu_cold/
  metadata.json
  raw_metrics.jsonl
```

## JSONL Run Record Schema

Each line in `raw_metrics.jsonl` is a complete JSON object representing one benchmark execution. The schema follows EXPERIMENT_PROTOCOL.md requirements.

### Critical Reproducibility Fields (MANDATORY)

These fields are required for valid benchmark comparisons:

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `model_sha256` | string | SHA-256 hash of model file | 64 hex characters |
| `llama_cpp_commit` | string | Git commit hash of llama.cpp | 40 hex characters |
| `seed` | integer | RNG seed | Must be `42` for comparable runs |
| `quantization` | string | Model quantization | Must be `Q4_0` for core benchmarks |

### Run Identity Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO 8601 timestamp when request was sent |
| `run_id` | string | UUID identifying this specific run |
| `regime` | string | Run regime: `cold`, `warm`, or `soak` |
| `repetition_index` | integer | Index of this repetition (0-based) |
| `benchmark_condition_id` | string | Grouping ID for comparable runs |
| `node` | string | Node identifier: `yoga` or `s25ultra` |
| `backend` | string | Backend: `cpu`, `opencl`, `npu_experimental` |
| `server_mode` | string | Server location: `local` or `phone` |
| `prompt_suite_id` | string | Stable suite identifier, e.g., `smoke_suite_v1` or `dataset_suite_v1` |
| `prompt_suite_version` | string | Version of the prompt suite, e.g., `1.0.0` |
| `prompt_suite_type` | string | Prompt suite category: `smoke` or `synthetic` |
| `suite_type` | string | Legacy alias for `prompt_suite_type`; may appear in older records |
| `cache_policy` | string | Cache handling policy, e.g., `disabled`, `cleared_by_restart`, `unknown`, or `unsupported_unverified` |
| `cache_expected` | boolean | Whether prompt/KV cache reuse was expected for this measured request; must be `false` for final evidence |
| `cache_observed` | string | Runtime prompt evaluation evidence: `full_eval`, `collapsed_eval`, or `unknown` |
| `cache_mismatch` | boolean | Whether expected and observed cache behavior disagree; must be `false` for final evidence |
| `mock_mode` | boolean | `true` for mock/development timing generated without a real llama.cpp server. Strict final aggregation excludes `mock_mode=true` records by default. |

### Device/Runtime Metadata

| Field | Type | Description |
|-------|------|-------------|
| `laptop_identifier` | string | Laptop ID (e.g., `yoga_slim7_14are05`) |
| `phone_identifier` | string | Phone ID (e.g., `s25ultra_sm_s938n`) |
| `os_build_metadata` | string | OS version and build info |
| `llama_cpp_commit` | string | Full 40-char git hash (MANDATORY) |
| `llama_cpp_build_flags` | string | CMake build flags |
| `server_launch_args` | string | Server launch command args |

### Model/Settings Metadata

| Field | Type | Description |
|-------|------|-------------|
| `model_name` | string | Full HuggingFace-style identifier |
| `model_filename` | string | Exact GGUF filename |
| `model_sha256` | string | SHA-256 hash (MANDATORY, 64 hex chars) |
| `parameter_count` | string | e.g., `1B`, `3B`, `8B` |
| `quantization` | string | Must be `Q4_0` for core benchmarks |
| `context_length` | integer | Context window size (2048) |
| `seed` | integer | RNG seed (MANDATORY, must be 42) |
| `temperature` | float | Sampling temperature (0.0) |
| `max_new_tokens` | integer | Max tokens to generate (512) |
| `stop_config` | string | Stopping condition description |

### Prompt/Output Metadata

| Field | Type | Description |
|-------|------|-------------|
| `prompt_id` | string | Versioned identifier for the prompt (e.g., `short_smoke_v1`) |
| `prompt_tier` | string | `short`, `medium`, `long`, or `soak` |
| `fixture_prompt_token_count` | integer \| null | Static prompt-suite metadata for the fixture prompt token count. This is separate from dynamic `prompt_token_count` and must not replace the runtime-reported count. |
| `runtime_prompt_eval_token_count` | integer \| null | Prompt tokens evaluated by the runtime for this request, from server `tokens_evaluated` |
| `prompt_token_count` | integer \| null | Legacy alias for runtime prompt evaluation count in older records |
| `prompt_token_count_source` | string | Source of runtime prompt count, e.g., `llama_cpp_tokens_evaluated` |
| `generated_token_count` | integer | Number of tokens generated |
| `stop_reason` | string | Why generation stopped |

### Dataset Metadata Fields

These fields are mandatory for final dataset records and optional for smoke/development records.

| Field | Type | Description |
|-------|------|-------------|
| `dataset_name` | string | Dataset family used for the fixture, e.g., `synthetic_offline_fixture` |
| `dataset_split` | string | Dataset split or fixed offline partition, e.g., `validation` |
| `source_article_id` | string | Stable source record ID or offline fixture source ID |
| `truncation_rule` | string | Rule used to shape the source text into the fixture prompt |
| `prompt_fixture_sha256` | string | SHA-256 hash of the final prompt fixture text |
| `tokenizer_runtime_used` | string | Tokenizer/runtime used to produce `fixture_prompt_token_count` |

#### Prompt ID Versioning

The smoke prompt suite uses a versioned ID format: `<tier>_smoke_v<N>` (e.g., `short_smoke_v1`, `medium_smoke_v1`).

**Why this matters:**
- Prevents **prompt drift** — changing prompt wording without tracking invalidates historical comparisons
- Enables **reproducibility auditing** — every benchmark run can be traced to the exact prompt used
- Supports **prompt evolution** — new versions can be introduced while maintaining comparison validity

**Rules:**
1. Never modify prompt text without incrementing the version number
2. Smoke prompt IDs must match the prompt tier prefix (e.g., `short_smoke_v1` for tier `short`)
3. Smoke prompt definitions live in `configs/prompts/smoke_suite.json`; synthetic final dissertation prompt definitions live in `configs/prompts/dataset_suite_v1.json`.

#### Token Count Integrity

**Critical**: runtime prompt token counts must be recorded from the llama.cpp server response, never guessed.
`fixture_prompt_token_count` is static suite metadata only; it can help audit the selected fixture, but it is not a measurement and must not be used for dynamic runtime token accounting.

For synthetic final records:

- `fixture_prompt_token_count` records the full fixture token count.
- `runtime_prompt_eval_token_count` records the runtime-evaluated prompt tokens.
- `prompt_token_count_source` should be `llama_cpp_tokens_evaluated`.
- `prompt_token_count` may be retained as a compatibility alias, but final analysis should prefer `runtime_prompt_eval_token_count`.

The client captures this from the `tokens_evaluated` field in the server's final SSE event:

```json
{"stop": true, "tokens_evaluated": 142, "tokens_predicted": 87}
```

**Why not guess?**
- Different tokenizers produce different counts for identical text
- Guessed counts (e.g., word splitting) break decode TPS comparability across models
- The server knows the exact prompt tokens after parsing the full context

If `runtime_prompt_eval_token_count` is unexpectedly lower than `fixture_prompt_token_count`, the record may have reused prompt/KV cache state and must set `cache_mismatch=true` or be excluded from final evidence.

#### Cache Policy Integrity

Final evidence records must explicitly describe cache behavior:

| Field | Accepted final value | Reason |
|-------|----------------------|--------|
| `cache_policy` | `disabled` or regime-compatible `cleared_by_restart` | Documents how cache reuse was prevented |
| `cache_expected` | `false` | Final evidence expects full prompt evaluation |
| `cache_observed` | `full_eval` | Runtime counts must not indicate cache reuse |
| `cache_mismatch` | `false` | Mismatched cache state is an acceptance failure |

Records with `cache_mismatch=true`, missing cache fields, or unverifiable cache behavior are development-only.

### Timing Metadata

| Field | Type | Description |
|-------|------|-------------|
| `request_sent_timestamp` | string | ISO 8601 when request was sent |
| `first_token_timestamp` | string | ISO 8601 when first token arrived |
| `final_token_timestamp` | string | ISO 8601 when last token arrived |

### Computed Metrics

| Field | Type | Description |
|-------|------|-------------|
| `ttft_ms` | float \| null | Time to first token in milliseconds |
| `decode_tps` | float \| null | Tokens per second during decode window |
| `client_overhead_ms` | float | Client processing time (non-blocking) |

### Optional Thermal/Environment Metadata

Thermal and environment fields are context fields only. They must be captured
strictly before the prompt is sent or after the final token is received; do not
poll thermal sensors during the active inference window.

| Field | Type | Description |
|-------|------|-------------|
| `start_temperature_c` | float \| null | Pre-run device temperature snapshot in Celsius |
| `end_temperature_c` | float \| null | Post-run device temperature snapshot in Celsius |
| `temperature_source` | string | Source for temperature fields, e.g., `sysfs_power_supply_battery_temp`, `dumpsys_battery_temperature`, or `unavailable` |
| `start_battery_level_percent` | integer \| null | Pre-run battery percentage snapshot |
| `end_battery_level_percent` | integer \| null | Post-run battery percentage snapshot |
| `battery_status` | string | `Charging`, `Discharging`, `Full`, or platform-specific status |
| `background_apps_minimized` | boolean \| null | Whether apps were minimized |
| `known_anomalies` | string | Any known issues during run |
| `notes` | string | General notes |

If pre/post snapshots are unavailable, leave the corresponding optional fields
absent or `null`. Missing thermal data must not be replaced with guessed values.

## Example Run Record

```json
{
  "timestamp": "2026-03-25T14:30:52.123456",
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "regime": "cold",
  "repetition_index": 0,
  "benchmark_condition_id": "yoga_cpu_local_Q4_0",
  "node": "yoga",
  "backend": "cpu",
  "server_mode": "local",
  "prompt_suite_id": "dataset_suite_v1",
  "prompt_suite_version": "1.0.0",
  "prompt_suite_type": "synthetic",
  "suite_type": "synthetic",
  "cache_policy": "disabled",
  "cache_expected": false,
  "cache_observed": "full_eval",
  "cache_mismatch": false,
  "laptop_identifier": "yoga_slim7_14are05",
  "phone_identifier": "",
  "os_build_metadata": "Windows 11 Education 10.0.26200",
  "llama_cpp_commit": "abc123def456789012345678901234567890abcd",
  "llama_cpp_build_flags": "-DGGML_OPENCL=OFF",
  "server_launch_args": "-m model.gguf -c 2048 -ngl 0 --cache-ram 0 -sps 0.0 -np 1",
  "model_name": "Meta-Llama-3.2-1B-Instruct",
  "model_filename": "llama-3.2-1b-instruct-q4_0.gguf",
  "model_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
  "parameter_count": "1B",
  "quantization": "Q4_0",
  "context_length": 2048,
  "seed": 42,
  "temperature": 0.0,
  "max_new_tokens": 512,
  "stop_config": "eos_or_max_tokens",
  "prompt_id": "final_short_01",
  "prompt_tier": "short",
  "fixture_prompt_token_count": 128,
  "runtime_prompt_eval_token_count": 128,
  "prompt_token_count": 128,
  "prompt_token_count_source": "llama_cpp_tokens_evaluated",
  "dataset_name": "synthetic_offline_fixture",
  "dataset_split": "final",
  "source_article_id": "fixed_offline_baseline_short_01",
  "truncation_rule": "fixed_offline_bucket_v1",
  "prompt_fixture_sha256": "cc80a3402ea0583a27478d48a7c4dddff85073ec33c3cd964d9d58ce9558d61e",
  "tokenizer_runtime_used": "llama_3_2_1b_instruct_tokenizer",
  "generated_token_count": 87,
  "stop_reason": "eos",
  "request_sent_timestamp": "2026-03-25T14:30:52.123456",
  "first_token_timestamp": "2026-03-25T14:30:52.456789",
  "final_token_timestamp": "2026-03-25T14:30:55.789012",
  "ttft_ms": 333.3,
  "decode_tps": 25.8,
  "client_overhead_ms": 2.5,
  "start_temperature_c": null,
  "end_temperature_c": null,
  "temperature_source": "unavailable",
  "start_battery_level_percent": null,
  "end_battery_level_percent": null,
  "battery_status": "",
  "background_apps_minimized": null,
  "known_anomalies": "",
  "notes": ""
}
```

## Timing Precision

Per the implementation plan:

- **Interval measurements** (TTFT, decode TPS): Use `time.perf_counter()` for high-resolution monotonic timing
- **Timestamp metadata**: Use `datetime.now().isoformat()` for human-readable wall-clock times
- **I/O isolation**: All JSON serialization and disk writes occur AFTER the final token is received to avoid inflating measured metrics

## Metric Definitions

### TTFT (Time to First Token)

```
TTFT = first_token_timestamp - request_sent_timestamp
```

Measured at the laptop client boundary. Includes:
- Client-side request overhead
- ADB/USB transport (if phone)
- Server parsing and tokenization
- Prefill computation
- First token generation

### Decode TPS (Tokens Per Second)

```
Decode TPS = (generated_token_count - 1) / (final_token_timestamp - first_token_timestamp)
```

Measured over the decode window only (after first token). This is sustained generation speed, not prompt responsiveness.

## Validation Commands

To validate schema and logging without a server:

```bash
# Run mock benchmark
python -m client.cli --node yoga --backend cpu --run-type cold --prompt-tier short --mock

# Verify directory creation
ls -la results/

# Inspect raw logs
cat results/*_yoga_cpu_cold/raw_metrics.jsonl

# Validate JSON format
python -c "import json; [json.loads(line) for line in open('results/YYYYMMDD_HHMMSS_yoga_cpu_cold/raw_metrics.jsonl')]"
```

### Prompt Metadata Verification

To verify prompt suite metadata and runtime prompt token counts are properly logged:

```bash
# Check that prompt and cache metadata exist in JSONL records
grep -E '"prompt_id"|"prompt_suite_type"|"runtime_prompt_eval_token_count"|"cache_mismatch"' results/<latest_run_dir>/raw_metrics.jsonl

# Verify prompt_id matches expected format
python -c "
import json
with open('results/<run_dir>/raw_metrics.jsonl') as f:
    for line in f:
        record = json.loads(line)
        assert 'prompt_id' in record, 'Missing prompt_id'
        assert 'prompt_suite_type' in record, 'Missing prompt_suite_type'
        assert 'runtime_prompt_eval_token_count' in record, 'Missing runtime prompt count'
        assert record.get('cache_mismatch') is False, 'Cache mismatch excludes final evidence'
        print(f'OK: prompt_id={record[\"prompt_id\"]}, runtime_prompt_eval_token_count={record[\"runtime_prompt_eval_token_count\"]}')
"
```

### Unit Test Validation

```bash
# Run all tests including prompt fixture tests
pytest tests/

# Run only prompt-related tests
pytest tests/test_cli.py -k "prompt" -v
```

## Schema Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-25 | Initial schema with mandatory reproducibility fields |
| 1.1.0 | 2026-04-20 | Documented optional pre/post thermal, battery, and anomaly |
| 1.2.0 | 2026-04-25 | Added prompt suite type, cache policy, and static fixture prompt token count metadata |
| 1.3.0 | 2026-04-25 | Added synthetic final metadata, runtime prompt count, and cache mismatch acceptance fields |
