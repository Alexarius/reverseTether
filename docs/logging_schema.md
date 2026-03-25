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

These fields are required for valid benchmark comparisons per DECISION_LOG.md DL-20260322-03:

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
| `prompt_id` | string | Identifier for the prompt |
| `prompt_tier` | string | `short`, `medium`, `long`, or `soak` |
| `prompt_token_count` | integer \| null | Prompt tokens (from server) |
| `generated_token_count` | integer | Number of tokens generated |
| `stop_reason` | string | Why generation stopped |

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

| Field | Type | Description |
|-------|------|-------------|
| `device_temperature_c` | float \| null | Device temperature in Celsius |
| `battery_level_percent` | integer \| null | Battery percentage |
| `battery_status` | string | `Charging`, `Discharging`, `Full` |
| `background_apps_minimized` | boolean \| null | Whether apps were minimized |
| `known_anomalies` | string | Any known issues during run |
| `notes` | string | General notes |

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
  "laptop_identifier": "yoga_slim7_14are05",
  "phone_identifier": "",
  "os_build_metadata": "Windows 11 Education 10.0.26200",
  "llama_cpp_commit": "abc123def456789012345678901234567890abcd",
  "llama_cpp_build_flags": "-DGGML_OPENCL=OFF",
  "server_launch_args": "-m model.gguf -c 2048 -ngl 0",
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
  "prompt_id": "short_chat_v1",
  "prompt_tier": "short",
  "prompt_token_count": 45,
  "generated_token_count": 87,
  "stop_reason": "eos",
  "request_sent_timestamp": "2026-03-25T14:30:52.123456",
  "first_token_timestamp": "2026-03-25T14:30:52.456789",
  "final_token_timestamp": "2026-03-25T14:30:55.789012",
  "ttft_ms": 333.3,
  "decode_tps": 25.8,
  "client_overhead_ms": 2.5,
  "device_temperature_c": null,
  "battery_level_percent": null,
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

## Schema Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-25 | Initial schema with mandatory reproducibility fields |
