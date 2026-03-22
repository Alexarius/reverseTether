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

Placeholder only. No results yet.

## Important

- Raw logs must be preserved for audit.
- Derived summaries must never replace raw logs.

## Related docs

- `PROJECT_BRIEF.md` for result directory naming convention
- `EXPERIMENT_PROTOCOL.md` for logging schema
