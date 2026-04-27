# analysis/

Aggregation, comparison, plots, and sanity checks.

## Purpose

This directory contains scripts for:

- aggregating raw JSONL logs,
- computing medians, percentiles, and spread,
- comparing laptop baseline vs reverse-tethered phone conditions,
- exporting charts and tables for the dissertation.

## Scripts

### `aggregate.py`

**Purpose**: Parse all valid run directories under `results/`, compute aggregated metrics (p50/p95 TTFT, mean Decode TPS) grouped by benchmark condition, and output summary tables and plots.

**Usage**:

```bash
python analysis/aggregate.py --input results/ --output results/summaries/
```

**Outputs** (written to `--output/aggregation_{timestamp}/`):

| File                        | Description                                       |
|-----------------------------|---------------------------------------------------|
| `summary.csv`               | Aggregated metrics in CSV format                  |
| `summary.md`                | Markdown table with cross-check instructions      |
| `ttft_comparison.png`       | Bar chart of TTFT p50 by condition                |
| `decode_tps_comparison.png` | Bar chart of Decode TPS mean by condition         |
| `raw_export.csv`            | All raw records with source directory annotations |

**Grouping dimensions**:

- `benchmark_condition_id` (e.g., `yoga_cpu_local_Q4_0`)
- `regime` (cold, warm)
- `prompt_tier` (short, medium, long)

**Failure handling**: Runs with `stop_reason == "error"` or `ttft_ms == 0.0` are counted in `sample_count`, `failure_count`, and `error_rate`, but excluded from TTFT and Decode TPS performance math.

**Traceability**: Every aggregated row includes a `source_dirs` column listing the original run directories that contributed to the performance aggregate.

**Exclusion logging**: Directories that are skipped (malformed names, missing files, empty data) are logged explicitly.

## Manual Cross-Check

After generating summaries, verify the derived metrics:

1. Pick a condition from the summary table.
2. Note the `source_dirs` for that condition.
3. Extract raw JSONL lines for that prompt tier:
   ```powershell
   Select-String -Path "results\<source_dir>\raw_metrics.jsonl" -Pattern '"prompt_tier": "short"'
   ```
4. Manually compute:
   - **p50 TTFT**: Median of `ttft_ms` values
   - **p95 TTFT**: 95th percentile of `ttft_ms` values
   - **Mean Decode TPS**: Average of `decode_tps` values
   - **Failure count / error rate**: Count of rows where `stop_reason == "error"` or `ttft_ms == 0.0`
5. Compare against the summary table values.