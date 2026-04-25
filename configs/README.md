# configs/

Run configs, model metadata, and prompt suite definitions.

## Directory Structure

```
configs/
  prompts/
    smoke_suite.json     # Current materialized smoke/development prompt suite
    final_suite.json     # Current materialized dataset-backed final prompt suite
    smoke_suite_v1.json  # Canonical methodology name for smoke suite v1, if materialized
    dataset_suite_v1.json # Canonical methodology name for final dataset suite v1, if materialized
  conditions/
    matrix.json          # Matrix run condition definitions
  server_metadata_schema.json  # Schema for server metadata validation
```

## Prompt Suites

Prompt suites are versioned JSON files containing prompts used by the benchmark harness. This ensures reproducibility and prevents prompt drift.

- `prompts/smoke_suite.json`: development/smoke prompts used by CLI defaults. Methodology name: `smoke_suite_v1`.
- `prompts/final_suite.json`: dataset-backed final dissertation benchmark prompts. Methodology name: `dataset_suite_v1`.

**Warning:** `short_v1` and any `_smoke_v1` prompt variants are not valid for final dissertation evidence.

### Suite Roles

| Suite role | Suite type | Canonical methodology name | Current file | Use |
|------------|------------|-----------------------------|--------------|-----|
| Smoke / development | `smoke` | `smoke_suite_v1` | `prompts/smoke_suite.json` | CLI smoke checks and implementation validation |
| Final dataset | `final_dataset` | `dataset_suite_v1` | `prompts/final_suite.json` | Final dissertation evidence |

Final aggregation must include only records from the final dataset suite. Smoke-suite records are development validation only.

### Schema

```json
{
  "version": "1.0.0",
  "suite_type": "final_dataset",
  "description": "Prompt suite description",
  "dataset_metadata": {
    "dataset_name": "cnn_dailymail",
    "dataset_split": "validation",
    "truncation_rule": "fixed_offline_to_target_prompt_tiers"
  },
  "prompts": {
    "<stable_prompt_key>": {
      "id": "final_<tier>_<index>",
      "tier": "<tier>",
      "fixture_prompt_token_count": <number>,
      "dataset_name": "cnn_dailymail",
      "dataset_split": "validation",
      "dataset_source_id": "<stable_source_record_id>",
      "truncation_rule": "<documented_rule>",
      "description": "<purpose>",
      "text": "<prompt text>"
    }
  }
}
```

### Prompt Tiers

| Tier | Purpose | Usage |
|------|---------|-------|
| `short` | Light interactive use | Baseline TTFT measurement |
| `medium` | Normal use workload | RAG-style summarization |
| `long` | Prefill-heavy workload | High KV-cache pressure testing |
| `soak` | Sustained-load testing | Thermal throttling detection |

### Dataset-Backed Fixture Requirements

Final dataset prompts must include:

- A stable prompt `id` that does not change without a suite version update.
- `tier` with one of `short`, `medium`, `long`, or `soak`.
- `fixture_prompt_token_count` for the full prompt text.
- `dataset_name`, such as `cnn_dailymail`.
- `dataset_split`, such as `train`, `validation`, or `test`.
- `dataset_source_id` that traces the fixture to the source dataset record or fixed offline source.
- `truncation_rule` describing how the source text was shortened or shaped.
- Full prompt `text` as sent to the benchmark client.

The fixture token count is metadata for reproducibility and cache detection. Runtime prompt evaluation must still be recorded separately from the server response.

### Versioning Rules

Per EXPERIMENT_PROTOCOL.md, prompt text must be versioned:

1. **Smoke prompt IDs** use the format `<tier>_smoke_v<version>` (e.g., `short_smoke_v1`, `soak_smoke_v1`)
2. **Final dataset prompt IDs** use stable final IDs such as `final_short_01`, tied to `dataset_suite_v1`
3. **Never modify** prompt text without incrementing the suite version number
4. **Log the prompt_id and prompt suite metadata** in every benchmark record for reproducibility
5. **Runtime token counts** are recorded from the runtime, not guessed

### Prompt Change Protocol

To change a prompt:

1. Increment the version in the `id` field (e.g., `short_smoke_v1` to `short_smoke_v2`)
2. Update the `text` field with the new content
3. Record the change in `DECISION_LOG.md`
4. All subsequent runs will use the new prompt and log the new ID

### Example

```json
{
  "prompts": {
    "short": {
      "id": "short_smoke_v1",
      "tier": "short",
      "estimated_tokens": 50,
      "description": "Chat-style query for baseline TTFT measurement",
      "text": "You are a helpful assistant. Explain..."
    }
  }
}
```

## Loading Prompts in Code

```python
from client.cli import load_prompt_suite, get_prompt_for_tier

# Load the suite
suite = load_prompt_suite(Path("configs/prompts/smoke_suite.json"))

# Get prompt text and ID for a tier
prompt_text, prompt_id = get_prompt_for_tier(suite, "short")
# prompt_id will be "short_smoke_v1" - logged in raw_metrics.jsonl
```

## Token Count Handling

**Critical**: Token counts must come from the llama.cpp runtime, not be guessed.

- `fixture_prompt_token_count`: Stored in the prompt fixture for the full prompt text
- `runtime_prompt_eval_token_count`: Retrieved from the server's `tokens_evaluated` response field
- `prompt_token_count`: Legacy alias for runtime prompt evaluation count in older records
- `generated_token_count`: Retrieved from the server's `tokens_predicted` response field

This ensures decode TPS comparability across different models and tokenizers.

If `runtime_prompt_eval_token_count` is much lower than `fixture_prompt_token_count` for a final dataset prompt, treat the record as cache-contaminated until reviewed.

## Related Documentation

- `EXPERIMENT_PROTOCOL.md` - Prompt suite rules and token count requirements
- `docs/logging_schema.md` - How prompt_id and prompt_token_count are logged
- `PROJECT_BRIEF.md` - Reproducibility requirements
