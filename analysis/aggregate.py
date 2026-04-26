#!/usr/bin/env python3
"""
Aggregate benchmark results from raw JSONL logs into summary tables and plots.

This script reads raw_metrics.jsonl files from results directories, computes
p50/p95 TTFT and average Decode TPS grouped by condition, and outputs derived
tables (.csv, .md) and plots (.png) to a summaries directory.

Traceability: All derived outputs reference source run directories.
Failed runs are counted but excluded from performance math.
No silent filtering: Any excluded data is logged explicitly.
No metric redefinition: TTFT and Decode TPS semantics are unchanged.
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Expected folder naming pattern: YYYYMMDD_HHMMSS_node_backend_runtype
RUN_DIR_PATTERN = re.compile(
    r"^(\d{8}_\d{6})_([a-zA-Z0-9]+)_([a-zA-Z0-9]+)_([a-zA-Z]+)$"
)
FINAL_EVIDENCE_CACHE_POLICIES = {"disabled", "cleared_by_restart"}


def parse_run_directory_name(dirname: str) -> dict[str, str] | None:
    """Parse the run directory name to extract metadata."""
    match = RUN_DIR_PATTERN.match(dirname)
    if not match:
        return None
    ts_str, node, backend, run_type = match.groups()
    return {
        "dir_timestamp": ts_str,
        "dir_node": node,
        "dir_backend": backend,
        "dir_run_type": run_type,
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load all JSON lines from a file."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning(
                    "Skipping malformed JSON at %s:%d: %s", path, lineno, e
                )
    return records


def load_metadata(path: Path) -> dict[str, Any]:
    """Load metadata.json from a run directory."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_runs(input_dir: Path) -> pd.DataFrame:
    """
    Collect all valid benchmark runs from the input directory.

    Returns a DataFrame with one row per benchmark record, annotated with
    the source directory for traceability.
    """
    all_records = []
    excluded_dirs = []

    is_single_run_dir = (
        (input_dir / "raw_metrics.jsonl").exists()
        and (input_dir / "metadata.json").exists()
    )
    if is_single_run_dir:
        candidate_run_dirs = [input_dir]
    else:
        candidate_run_dirs = [
            subdir
            for subdir in sorted(input_dir.iterdir())
            if subdir.is_dir() and not subdir.name.startswith(".")
        ]

    for subdir in candidate_run_dirs:

        # Parse directory name
        dir_meta = parse_run_directory_name(subdir.name)
        if dir_meta is None:
            logger.info(
                "Skipping directory with non-standard name: %s", subdir.name
            )
            excluded_dirs.append((subdir.name, "non-standard naming"))
            continue

        # Check for required files
        raw_metrics_path = subdir / "raw_metrics.jsonl"
        metadata_path = subdir / "metadata.json"

        if not raw_metrics_path.exists():
            logger.info(
                "Skipping directory without raw_metrics.jsonl: %s", subdir.name
            )
            excluded_dirs.append((subdir.name, "missing raw_metrics.jsonl"))
            continue

        if not metadata_path.exists():
            logger.info(
                "Skipping directory without metadata.json: %s", subdir.name
            )
            excluded_dirs.append((subdir.name, "missing metadata.json"))
            continue

        # Load records
        records = load_jsonl(raw_metrics_path)
        if not records:
            logger.info(
                "Skipping directory with empty raw_metrics.jsonl: %s",
                subdir.name,
            )
            excluded_dirs.append((subdir.name, "empty raw_metrics.jsonl"))
            continue

        # Annotate records with source directory for traceability
        for rec in records:
            rec["source_dir"] = subdir.name
            rec.update(dir_meta)

        all_records.extend(records)
        logger.info(
            "Loaded %d records from %s", len(records), subdir.name
        )

    # Log all exclusions for auditability
    if excluded_dirs:
        logger.info("Excluded directories summary:")
        for dirname, reason in excluded_dirs:
            logger.info("  - %s: %s", dirname, reason)

    if not all_records:
        logger.warning("No valid benchmark records found in %s", input_dir)
        return pd.DataFrame()

    return pd.DataFrame(all_records)


def validate_required_columns(
    df: pd.DataFrame, group_by_prompt_id: bool = False
) -> bool:
    """Check that required columns exist for aggregation."""
    required = [
        "run_id",
        "benchmark_condition_id",
        "regime",
        "prompt_tier",
        "stop_reason",
        "ttft_ms",
        "decode_tps",
    ]
    if group_by_prompt_id:
        required.append("prompt_id")
    missing = [col for col in required if col not in df.columns]
    if missing:
        logger.error("Missing required columns: %s", missing)
        return False
    return True


def apply_final_evidence_filter(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only records eligible for final evidence aggregation.

    This is the default aggregation behavior. Missing suite/cache metadata is
    excluded so development and legacy records cannot enter final summaries by
    accident.
    """
    if df.empty:
        logger.info("Final evidence strict filter dropped 0 records.")
        return df

    suite_type = (
        df["prompt_suite_type"]
        if "prompt_suite_type" in df.columns
        else pd.Series(pd.NA, index=df.index)
    ).combine_first(
        df["suite_type"]
        if "suite_type" in df.columns
        else pd.Series(pd.NA, index=df.index)
    )
    cache_policy = (
        df["cache_policy"]
        if "cache_policy" in df.columns
        else pd.Series(pd.NA, index=df.index)
    )
    cache_observed = (
        df["cache_observed"]
        if "cache_observed" in df.columns
        else pd.Series(pd.NA, index=df.index)
    )
    source_article_id = (
        df["source_article_id"]
        if "source_article_id" in df.columns
        else pd.Series(pd.NA, index=df.index)
    )
    stop_reason = (
        df["stop_reason"]
        if "stop_reason" in df.columns
        else pd.Series(pd.NA, index=df.index)
    )
    ttft_ms = (
        pd.to_numeric(df["ttft_ms"], errors="coerce")
        if "ttft_ms" in df.columns
        else pd.Series(pd.NA, index=df.index)
    )

    suite_text = suite_type.astype("string").str.strip()
    cache_text = cache_policy.astype("string").str.strip()
    observed_text = cache_observed.astype("string").str.strip()
    source_article_text = source_article_id.astype("string").str.strip()
    stop_text = stop_reason.astype("string").str.strip()
    suite_present = suite_text.notna() & suite_text.ne("").fillna(False)
    cache_present = cache_text.notna() & cache_text.ne("").fillna(False)
    source_article_present = (
        source_article_text.notna() & source_article_text.ne("").fillna(False)
    )
    cache_expected = _field_true_mask(df, "cache_expected")
    cache_mismatch = _field_true_mask(df, "cache_mismatch")
    is_failure = stop_text.eq("error").fillna(False) | ttft_ms.eq(0.0).fillna(False)
    cache_verified = observed_text.eq("full_eval").fillna(False) | is_failure
    keep_mask = (
        suite_present
        & cache_present
        & suite_text.eq("synthetic").fillna(False)
        & cache_text.isin(FINAL_EVIDENCE_CACHE_POLICIES)
        & ~cache_expected
        & ~cache_mismatch
        & cache_verified
        & source_article_present
    )

    filtered = df.loc[keep_mask].copy()
    logger.info(
        "Final evidence strict filter dropped %d records.",
        len(df) - len(filtered),
    )
    return filtered


def _field_true_mask(df: pd.DataFrame, field_name: str) -> pd.Series:
    """Return True for records whose boolean-like field explicitly flags true."""
    if field_name not in df.columns:
        return pd.Series(False, index=df.index)

    value = df[field_name]
    if pd.api.types.is_bool_dtype(value):
        return value.fillna(False)

    value_text = value.astype("string").str.strip().str.lower()
    return value_text.isin({"true", "1", "yes"})


def exclude_invalid_records(
    df: pd.DataFrame, required_value_cols: list[str]
) -> pd.DataFrame:
    """
    Exclude records missing required values and log each exclusion explicitly.

    This prevents pandas groupby from silently dropping rows with null group keys.
    """
    missing_required_mask = df[required_value_cols].isna().any(axis=1)
    if not missing_required_mask.any():
        return df

    excluded = df.loc[missing_required_mask, ["run_id", "source_dir"] + required_value_cols]
    logger.warning(
        "Excluding %d records missing required values for aggregation.",
        len(excluded),
    )
    for _, row in excluded.iterrows():
        missing_cols = [
            col for col in required_value_cols if pd.isna(row[col])
        ]
        logger.warning(
            "Excluded run_id=%s from %s due to missing values in: %s",
            row.get("run_id", "<missing>"),
            row.get("source_dir", "<unknown>"),
            ", ".join(missing_cols),
        )

    return df.loc[~missing_required_mask].copy()


def compute_aggregates(
    df: pd.DataFrame, group_by_prompt_id: bool = False
) -> pd.DataFrame:
    """
    Compute aggregated metrics grouped by condition.

    Groups by: benchmark_condition_id, regime, prompt_tier
    Optionally includes prompt_id when requested.
    Computes for each group:
      - Sample count
      - Failure count
      - Error rate
      - TTFT p50 (median)
      - TTFT p95
      - Decode TPS mean
      - Source directories (for traceability)

    Failed runs are retained in counts but excluded from performance math.
    """
    if df.empty:
        return pd.DataFrame()

    group_keys = ["benchmark_condition_id", "regime", "prompt_tier"]
    if group_by_prompt_id:
        group_keys.append("prompt_id")

    df = exclude_invalid_records(
        df,
        required_value_cols=group_keys + ["stop_reason", "ttft_ms"],
    )
    if df.empty:
        logger.warning("No valid records remain after excluding invalid rows.")
        return pd.DataFrame()

    df = df.copy()
    df["is_failure"] = (df["stop_reason"] == "error") | (df["ttft_ms"] == 0.0)

    failure_count = int(df["is_failure"].sum())
    if failure_count:
        logger.info(
            "Flagged %d failed runs; excluded them from TTFT/TPS math while retaining them in failure counts.",
            failure_count,
        )

    counts = df.groupby(group_keys, as_index=False).agg(
        sample_count=("run_id", "size"),
        failure_count=("is_failure", "sum"),
    )
    counts["error_rate"] = counts["failure_count"] / counts["sample_count"]

    perf_df = df.loc[~df["is_failure"]]
    if perf_df.empty:
        metrics = pd.DataFrame(
            columns=group_keys
            + ["ttft_p50_ms", "ttft_p95_ms", "decode_tps_mean", "source_dirs"]
        )
    else:
        metrics = perf_df.groupby(group_keys, as_index=False).agg(
            ttft_p50_ms=("ttft_ms", lambda s: s.quantile(0.50)),
            ttft_p95_ms=("ttft_ms", lambda s: s.quantile(0.95)),
            decode_tps_mean=("decode_tps", "mean"),
            source_dirs=("source_dir", lambda s: ", ".join(sorted(set(s)))),
        )

    return counts.merge(metrics, on=group_keys, how="left")


def generate_markdown_table(df: pd.DataFrame) -> str:
    """Generate a Markdown-formatted table from a DataFrame."""
    if df.empty:
        return "*No data available.*\n"

    # Format numeric columns
    df_display = df.copy()
    for col in ["ttft_p50_ms", "ttft_p95_ms"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: "" if pd.isna(x) else f"{x:.2f}"
            )
    for col in ["decode_tps_mean", "error_rate"]:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: "" if pd.isna(x) else f"{x:.2f}"
            )

    # Build markdown table manually (avoiding tabulate dependency)
    cols = df_display.columns.tolist()
    lines = []

    # Header row
    lines.append("| " + " | ".join(cols) + " |")

    # Separator row
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")

    # Data rows
    for _, row in df_display.iterrows():
        row_values = [str(row[col]) for col in cols]
        lines.append("| " + " | ".join(row_values) + " |")

    return "\n".join(lines)


def plot_ttft_comparison(df: pd.DataFrame, output_path: Path) -> None:
    """
    Create a bar chart comparing TTFT p50 across conditions.
    """
    if df.empty:
        logger.warning("No data to plot for TTFT comparison.")
        return

    # Create condition labels
    df = df.loc[df["ttft_p50_ms"].notna()].copy()
    if df.empty:
        logger.warning("No successful TTFT data to plot.")
        return
    df["condition"] = (
        df["benchmark_condition_id"] + "_" + df["regime"] + "_" + df["prompt_tier"]
    )
    if "prompt_id" in df.columns:
        df["condition"] = df["condition"] + "_" + df["prompt_id"].astype(str)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(df["condition"], df["ttft_p50_ms"], color="steelblue", edgecolor="black")

    ax.set_xlabel("Condition (benchmark_condition_id_regime_prompt_tier)")
    ax.set_ylabel("TTFT p50 (ms)")
    ax.set_title("Time to First Token (p50) by Condition")
    ax.tick_params(axis="x", rotation=45)

    # Add value labels on bars
    for bar, val in zip(bars, df["ttft_p50_ms"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 5,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    logger.info("Saved TTFT comparison plot to %s", output_path)


def plot_decode_tps_comparison(df: pd.DataFrame, output_path: Path) -> None:
    """
    Create a bar chart comparing Decode TPS (mean) across conditions.
    """
    if df.empty:
        logger.warning("No data to plot for Decode TPS comparison.")
        return

    df = df.loc[df["decode_tps_mean"].notna()].copy()
    if df.empty:
        logger.warning("No successful Decode TPS data to plot.")
        return
    df["condition"] = (
        df["benchmark_condition_id"] + "_" + df["regime"] + "_" + df["prompt_tier"]
    )
    if "prompt_id" in df.columns:
        df["condition"] = df["condition"] + "_" + df["prompt_id"].astype(str)

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(df["condition"], df["decode_tps_mean"], color="darkorange", edgecolor="black")

    ax.set_xlabel("Condition (benchmark_condition_id_regime_prompt_tier)")
    ax.set_ylabel("Decode TPS (mean)")
    ax.set_title("Decode Throughput (mean) by Condition")
    ax.tick_params(axis="x", rotation=45)

    for bar, val in zip(bars, df["decode_tps_mean"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    logger.info("Saved Decode TPS comparison plot to %s", output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate benchmark results into summary tables and plots.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python analysis/aggregate.py --input results/ --output results/summaries/
  python analysis/aggregate.py results/20260425_120000_yoga_cpu_matrix

Manual Cross-Check:
  After running, verify derived metrics by manually inspecting a subset of
  raw_metrics.jsonl entries and computing p50/p95 TTFT and mean Decode TPS.
""",
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        help="Optional shorthand input path containing run folders or one run folder.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input directory containing run folders (e.g., results/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output directory for summaries (e.g., results/summaries/). "
            "Defaults to <input>/summaries."
        ),
    )
    parser.add_argument(
        "--group-by-prompt-id",
        action="store_true",
        help="Include prompt_id in aggregation groups and output labels.",
    )
    parser.add_argument(
        "--include-smoke",
        action="store_true",
        help="Include smoke, development, and legacy records in aggregation.",
    )
    args = parser.parse_args()

    input_arg = args.input or args.input_path
    if input_arg is None:
        parser.error(
            "an input directory is required via --input or positional input_path"
        )

    input_dir = input_arg.resolve()
    output_dir = (
        args.output.resolve()
        if args.output is not None
        else (input_dir / "summaries").resolve()
    )

    if not input_dir.exists():
        logger.error("Input directory does not exist: %s", input_dir)
        return 1

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory: %s", output_dir)

    # Collect all runs
    logger.info("Collecting benchmark runs from %s", input_dir)
    df = collect_runs(input_dir)

    if df.empty:
        logger.error("No valid records found. Exiting.")
        return 1

    logger.info("Collected %d total records", len(df))

    if not args.include_smoke:
        df = apply_final_evidence_filter(df)
        if df.empty:
            logger.error("No records remain after final evidence strict filter. Exiting.")
            return 1

    # Validate required columns
    if not validate_required_columns(df, group_by_prompt_id=args.group_by_prompt_id):
        return 1

    # Compute aggregates
    logger.info("Computing aggregated metrics...")
    agg_df = compute_aggregates(df, group_by_prompt_id=args.group_by_prompt_id)

    if agg_df.empty:
        logger.error("Aggregation produced no results. Exiting.")
        return 1

    logger.info("Computed aggregates for %d conditions", len(agg_df))

    # Generate timestamp for output files
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = output_dir / f"aggregation_{ts}"
    run_output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Aggregation run output directory: %s", run_output_dir)

    # Save CSV
    csv_path = run_output_dir / "summary.csv"
    agg_df.to_csv(csv_path, index=False)
    logger.info("Saved summary CSV to %s", csv_path)

    # Save Markdown table
    md_path = run_output_dir / "summary.md"
    md_content = f"""# Benchmark Summary

Generated: {datetime.now().isoformat()}

## Aggregated Metrics

{generate_markdown_table(agg_df)}

## Notes

- **TTFT p50/p95**: Time to first token in milliseconds (measured at laptop boundary).
- **Decode TPS mean**: Average tokens per second during decode phase.
- **failure_count / error_rate**: Failed runs retained for auditability and excluded from performance math.
- **source_dirs**: Original run directories for traceability.

## Cross-Check Instructions

To verify these derived metrics:

1. Select a specific condition from the table above.
2. Identify the source_dirs for that condition.
3. Extract raw records from those directories:
   ```powershell
   Select-String -Path "results\\<source_dir>\\raw_metrics.jsonl" -Pattern '"prompt_tier": "<tier>"'
   ```
4. Manually compute p50/p95 TTFT and mean Decode TPS.
5. Compare against the values in this table.
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info("Saved summary Markdown to %s", md_path)

    # Generate plots
    plot_ttft_comparison(agg_df, run_output_dir / "ttft_comparison.png")
    plot_decode_tps_comparison(agg_df, run_output_dir / "decode_tps_comparison.png")

    # Also save raw data export for detailed analysis
    raw_export_path = run_output_dir / "raw_export.csv"
    df.to_csv(raw_export_path, index=False)
    logger.info("Saved raw data export to %s", raw_export_path)

    logger.info("Aggregation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
