# configs/

Run configs, model metadata, and prompt suite definitions.

## Directory Structure

```
configs/
  prompts/
    smoke_suite.json     # SMOKE/DEVELOPMENT ONLY prompt suite
    final_suite.json     # Reserved placeholder for final dissertation prompts
  conditions/
    matrix.json          # Matrix run condition definitions
  server_metadata_schema.json  # Schema for server metadata validation
```

## Prompt Suites

Prompt suites are versioned JSON files containing prompts used by the benchmark harness. This ensures reproducibility and prevents prompt drift.

- `prompts/smoke_suite.json`: development/smoke prompts used by CLI defaults.
- `prompts/final_suite.json`: reserved placeholder for the final dissertation benchmark prompts.

**Warning:** `short_v1` and any `_smoke_v1` prompt variants are not valid for final dissertation evidence.

### Schema

```json
{
  "version": "1.0.0",
  "description": "Prompt suite description",
  "prompts": {
    "<tier>": {
      "id": "<tier>_smoke_v<version>",
      "tier": "<tier>",
      "estimated_tokens": <number>,
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

### Versioning Rules

Per EXPERIMENT_PROTOCOL.md, prompt text must be versioned:

1. **Smoke prompt IDs** use the format `<tier>_smoke_v<version>` (e.g., `short_smoke_v1`, `soak_smoke_v1`)
2. **Never modify** prompt text without incrementing the version number
3. **Log the prompt_id** in every benchmark record for reproducibility
4. **Token counts** are recorded from the runtime, not guessed

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

- `prompt_token_count`: Retrieved from the server's `tokens_evaluated` response field
- `generated_token_count`: Retrieved from the server's `tokens_predicted` response field

This ensures decode TPS comparability across different models and tokenizers.

## Related Documentation

- `EXPERIMENT_PROTOCOL.md` - Prompt suite rules and token count requirements
- `docs/logging_schema.md` - How prompt_id and prompt_token_count are logged
- `PROJECT_BRIEF.md` - Reproducibility requirements
