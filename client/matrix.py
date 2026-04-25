"""CLI entry point for benchmark matrix runs.

Usage:
    python -m client.matrix --node yoga --backend cpu --regimes cold,warm,soak --repetitions 5 --prompt-tier short
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .benchmark import (
    BenchmarkConfig,
    MatrixConfig,
    MatrixRunResult,
    create_matrix_output_directory,
    run_matrix,
    validate_reproducibility_fields,
)
from .cli import get_prompt_for_tier, load_prompt_suite


def build_config_from_args(args: argparse.Namespace) -> BenchmarkConfig:
    """Build the base benchmark configuration for a matrix run."""
    return BenchmarkConfig(
        node=args.node,
        backend=args.backend,
        run_type="warm",
        prompt_tier=args.prompt_tier,
        host=args.host,
        port=args.port,
        server_mode=args.server_mode,
        model_name=args.model_name,
        model_filename=args.model_filename,
        model_sha256=args.model_sha256,
        parameter_count=args.parameter_count,
        llama_cpp_commit=args.llama_cpp_commit,
        llama_cpp_build_flags=args.llama_cpp_build_flags,
        server_launch_args=args.server_launch_args,
        laptop_identifier=args.laptop_identifier,
        phone_identifier=args.phone_identifier,
        os_build_metadata=args.os_build_metadata,
        start_temperature_c=args.start_temperature_c,
        end_temperature_c=args.end_temperature_c,
        temperature_source=args.temperature_source,
        start_battery_level_percent=args.start_battery_level_percent,
        end_battery_level_percent=args.end_battery_level_percent,
        battery_status=args.battery_status,
        background_apps_minimized=(
            None if args.background_apps_minimized is None
            else args.background_apps_minimized == "true"
        ),
        known_anomalies=args.known_anomalies,
        mock=args.mock,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark matrix runner for llama.cpp server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full matrix with all regimes (dry run)
  python -m client.matrix --node yoga --backend cpu --regimes cold,warm,soak \
      --repetitions 2 --prompt-tier short --dry-run

  # Matrix run with custom output directory
  python -m client.matrix --node yoga --backend cpu --regimes cold,warm,soak \
      --repetitions 5 --prompt-tier soak --output-dir results/test_matrix_run

  # Mock mode matrix (for testing without server)
  python -m client.matrix --node yoga --backend cpu --regimes warm,soak \
      --repetitions 3 --prompt-tier short --mock
"""
    )

    parser.add_argument(
        "--node",
        required=True,
        choices=["yoga", "s25ultra"],
        help="Node identifier (yoga for laptop, s25ultra for phone)"
    )
    parser.add_argument(
        "--backend",
        required=True,
        choices=["cpu", "opencl", "npu_experimental"],
        help="Backend mode for inference"
    )
    parser.add_argument(
        "--regimes",
        required=True,
        help="Comma-separated list of regimes to run (cold,warm,soak)"
    )
    parser.add_argument(
        "--prompt-tier",
        required=True,
        choices=["short", "medium", "long", "soak"],
        help="Prompt tier from suite"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Server port (default: 8080)"
    )
    parser.add_argument(
        "--server-mode",
        default="local",
        choices=["local", "phone"],
        help="Server mode: local or phone (reverse-tethered) (default: local)"
    )
    parser.add_argument(
        "--model-name",
        default="",
        help="Model name for metadata (optional)"
    )
    parser.add_argument(
        "--suite-path",
        "--prompt-suite",
        dest="suite_path",
        type=Path,
        default=Path("configs/prompts/smoke_suite.json"),
        help="Path to prompt suite JSON"
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=5,
        help="Number of repetitions per regime (default: 5, per EXPERIMENT_PROTOCOL.md)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode (no server required, generates synthetic timing data)"
    )
    parser.add_argument(
        "--model-filename",
        default="",
        help="Exact GGUF model filename"
    )
    parser.add_argument(
        "--model-sha256",
        default="",
        help="SHA-256 hash of model file (64 hex chars, mandatory for real runs)"
    )
    parser.add_argument(
        "--parameter-count",
        default="",
        help="Model parameter count (e.g., '1B', '3B', '8B')"
    )
    parser.add_argument(
        "--llama-cpp-commit",
        default="",
        help="Full 40-character git commit hash of llama.cpp build (mandatory for real runs)"
    )
    parser.add_argument(
        "--llama-cpp-build-flags",
        default="",
        help="CMake build flags used for llama.cpp"
    )
    parser.add_argument(
        "--server-launch-args",
        default="",
        help="Server launch command arguments"
    )
    parser.add_argument(
        "--laptop-identifier",
        default="",
        help="Laptop identifier (e.g., 'yoga_slim7_14are05')"
    )
    parser.add_argument(
        "--phone-identifier",
        default="",
        help="Phone identifier (e.g., 's25ultra_sm_s938n')"
    )
    parser.add_argument(
        "--os-build-metadata",
        default="",
        help="OS version and build information"
    )
    parser.add_argument(
        "--start-temperature-c",
        type=float,
        default=None,
        help="Pre-run device temperature snapshot in Celsius"
    )
    parser.add_argument(
        "--end-temperature-c",
        type=float,
        default=None,
        help="Post-run device temperature snapshot in Celsius"
    )
    parser.add_argument(
        "--temperature-source",
        default="",
        help="Source for temperature fields"
    )
    parser.add_argument(
        "--start-battery-level-percent",
        type=int,
        default=None,
        help="Pre-run battery percentage snapshot"
    )
    parser.add_argument(
        "--end-battery-level-percent",
        type=int,
        default=None,
        help="Post-run battery percentage snapshot"
    )
    parser.add_argument(
        "--battery-status",
        default="",
        help="Battery charging status, if captured"
    )
    parser.add_argument(
        "--background-apps-minimized",
        choices=["true", "false"],
        default=None,
        help="Whether background apps were minimized before capture"
    )
    parser.add_argument(
        "--known-anomalies",
        default="",
        help="Known anomalies affecting this matrix run"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for results (auto-generated if not specified)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions but don't execute benchmarks (for validation)"
    )

    args = parser.parse_args()

    try:
        suite = load_prompt_suite(args.suite_path)
    except FileNotFoundError:
        print(f"Error: Prompt suite not found at {args.suite_path}", file=sys.stderr)
        print("Ensure configs/prompts/smoke_suite.json exists.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in prompt suite: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        prompt_text, prompt_id = get_prompt_for_tier(suite, args.prompt_tier)
    except KeyError:
        print(f"Error: Prompt tier '{args.prompt_tier}' not found in suite", file=sys.stderr)
        sys.exit(1)

    regimes = [regime.strip() for regime in args.regimes.split(",")]
    valid_regimes = {"cold", "warm", "soak"}
    for regime in regimes:
        if regime not in valid_regimes:
            print(f"Error: Invalid regime '{regime}'. Valid options: cold, warm, soak", file=sys.stderr)
            sys.exit(1)

    base_config = build_config_from_args(args)

    try:
        validate_reproducibility_fields(base_config)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    matrix_config = MatrixConfig(
        regimes=regimes,
        repetitions=args.repetitions,
        prompt_tier=args.prompt_tier,
        dry_run=args.dry_run,
    )

    if args.output_dir is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        requested_output_dir = Path(f"results/{ts}_{args.node}_{args.backend}_matrix")
    else:
        requested_output_dir = Path(args.output_dir)
    output_dir = create_matrix_output_directory(base_config, requested_output_dir)

    total_runs = len(regimes) * args.repetitions
    print("Matrix Benchmark Run")
    print("=" * 40)
    print(f"  Node: {base_config.node}")
    print(f"  Backend: {base_config.backend}")
    print(f"  Prompt tier: {args.prompt_tier}")
    print(f"  Server mode: {base_config.server_mode}")
    print(f"  Regimes: {', '.join(regimes)}")
    print(f"  Repetitions per regime: {args.repetitions}")
    print(f"  Total runs: {total_runs}")
    if args.dry_run:
        print("  Mode: DRY RUN (no actual requests)")
    elif base_config.mock:
        print("  Mode: MOCK (no server connection)")
    else:
        print(f"  Server: {base_config.host}:{base_config.port}")
    print("=" * 40)
    print()

    success_count = 0
    failure_count = 0

    def on_regime_start(regime: str) -> None:
        print(f"\n--- Regime: {regime.upper()} ---")
        if regime == "cold":
            print("WARNING: Cold regime requires server restart for accurate measurement.")
            if not args.dry_run and not base_config.mock:
                print("         Ensure server was restarted before continuing.")

    def on_run_complete(result: MatrixRunResult) -> None:
        nonlocal success_count, failure_count

        rep_display = result.repetition_index + 1
        if result.success:
            success_count += 1
            if result.record:
                ttft_str = f"{result.record.ttft_ms:.1f}ms" if result.record.ttft_ms else "N/A"
                tps_str = f"{result.record.decode_tps:.2f}" if result.record.decode_tps else "N/A"
                print(
                    f"  [{result.regime}] Rep {rep_display}/{args.repetitions}: "
                    f"TTFT: {ttft_str}, Decode TPS: {tps_str}, "
                    f"Tokens: {result.record.generated_token_count}"
                )
            elif args.dry_run:
                print(f"  [{result.regime}] Rep {rep_display}/{args.repetitions}: DRY RUN")
        else:
            failure_count += 1
            print(
                f"  [{result.regime}] Rep {rep_display}/{args.repetitions}: "
                f"FAILED - {result.error_message}",
                file=sys.stderr,
            )

    run_matrix(
        prompt=prompt_text,
        prompt_id=prompt_id,
        base_config=base_config,
        matrix_config=matrix_config,
        output_dir=output_dir,
        on_regime_start=on_regime_start,
        on_run_complete=on_run_complete,
    )

    print()
    print("=" * 40)
    print("Matrix Run Complete")
    print(f"  Successful runs: {success_count}/{total_runs}")
    print(f"  Failed runs: {failure_count}/{total_runs}")
    print(f"  Output directory: {output_dir}")
    if not args.dry_run:
        print("  Results file: raw_metrics.jsonl")
    print("=" * 40)

    if failure_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
