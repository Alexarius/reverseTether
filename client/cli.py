"""CLI entry point for laptop benchmark harness.

Usage:
    python -m client.cli --node yoga --backend cpu --run-type cold --prompt-tier short

This is a minimal CLI-first benchmark harness per Issue 03 requirements.
No elaborate UI - just command-line interface for measurement.
"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import List, Tuple

from .benchmark import (
    BenchmarkConfig,
    create_result_directory,
    run_benchmark,
    validate_reproducibility_fields,
)


FINAL_DATASET_BUCKET_COUNTS = {"short": 5, "medium": 5, "long": 5, "soak": 1}
FINAL_PROMPT_TIERS = {"short", "medium", "long"}
VALID_SUITE_TYPES = {"smoke", "final_dataset"}


def validate_prompt_suite(suite: dict) -> None:
    """Validate prompt suite structure before any benchmark timing begins."""
    suite_type = suite.get("suite_type")
    if suite_type not in VALID_SUITE_TYPES:
        raise ValueError("Prompt suite must define suite_type as 'smoke' or 'final_dataset'")

    prompts = suite.get("prompts")
    if not isinstance(prompts, dict):
        raise ValueError("Prompt suite must define prompts as a dictionary")

    prompt_ids = set()
    for prompt_key, prompt_data in prompts.items():
        if not isinstance(prompt_data, dict):
            raise ValueError(f"Prompt '{prompt_key}' must be an object")

        if "id" not in prompt_data:
            raise ValueError(f"Prompt '{prompt_key}' is missing required field 'id'")
        if "text" not in prompt_data:
            raise ValueError(f"Prompt '{prompt_key}' is missing required field 'text'")

        prompt_id = prompt_data["id"]
        if prompt_id in prompt_ids:
            raise ValueError(f"Duplicate prompt id '{prompt_id}' in prompt suite")
        prompt_ids.add(prompt_id)

    if suite_type != "final_dataset":
        return

    dataset_metadata = suite.get("dataset_metadata")
    if not isinstance(dataset_metadata, dict):
        raise ValueError("Final dataset suite must define dataset_metadata as an object")

    bucket_counts = {tier: 0 for tier in FINAL_DATASET_BUCKET_COUNTS}
    for prompt_key, prompt_data in prompts.items():
        fixture_count = prompt_data.get("fixture_prompt_token_count")
        if not isinstance(fixture_count, int) or isinstance(fixture_count, bool):
            raise ValueError(
                f"Final dataset prompt '{prompt_key}' must define integer "
                "fixture_prompt_token_count"
            )

        tier = prompt_data.get("tier")
        if tier not in FINAL_DATASET_BUCKET_COUNTS:
            raise ValueError(
                f"Final dataset prompt '{prompt_key}' must use tier "
                "'short', 'medium', 'long', or 'soak'"
            )
        bucket_counts[tier] += 1

    if bucket_counts != FINAL_DATASET_BUCKET_COUNTS:
        raise ValueError(
            "Final dataset prompt bucket counts must be "
            f"{FINAL_DATASET_BUCKET_COUNTS}; got {bucket_counts}"
        )


def load_prompt_suite(suite_path: Path) -> dict:
    """Load the prompt suite configuration.

    Args:
        suite_path: Path to the prompt suite JSON file

    Returns:
        Validated prompt suite dictionary
    """
    with open(suite_path, "r", encoding="utf-8") as f:
        suite = json.load(f)

    validate_prompt_suite(suite)
    return suite


def validate_prompt_selection(
    prompt_tier: str | None = None,
    prompt_id: str | None = None,
    all_final_prompts: bool = False,
) -> None:
    """Require exactly one prompt selection mode."""
    selected_modes = [
        prompt_tier is not None,
        prompt_id is not None,
        all_final_prompts,
    ]
    if sum(selected_modes) != 1:
        raise ValueError(
            "Exactly one of --prompt-tier, --prompt-id, or --all-final-prompts "
            "must be provided"
        )


def get_prompts(
    suite: dict,
    prompt_tier: str | None = None,
    prompt_id: str | None = None,
    all_final_prompts: bool = False,
) -> List[Tuple[str, str]]:
    """Return selected prompts as (prompt_text, prompt_id), sorted where applicable."""
    validate_prompt_selection(prompt_tier, prompt_id, all_final_prompts)

    prompt_items = suite["prompts"].items()

    if prompt_id is not None:
        for _, prompt_data in prompt_items:
            if prompt_data["id"] == prompt_id:
                return [(prompt_data["text"], prompt_data["id"])]
        raise KeyError(prompt_id)

    if prompt_tier is not None:
        selected = [
            prompt_data
            for prompt_key, prompt_data in prompt_items
            if prompt_data.get("tier", prompt_key) == prompt_tier
        ]
        if not selected:
            raise KeyError(prompt_tier)
        return [
            (prompt_data["text"], prompt_data["id"])
            for prompt_data in sorted(selected, key=lambda item: item["id"])
        ]

    selected = [
        prompt_data
        for prompt_key, prompt_data in prompt_items
        if prompt_data.get("tier", prompt_key) in FINAL_PROMPT_TIERS
    ]
    if not selected:
        raise KeyError("all_final_prompts")
    return [
        (prompt_data["text"], prompt_data["id"])
        for prompt_data in sorted(selected, key=lambda item: item["id"])
    ]


def get_prompt_tier_by_id(suite: dict) -> dict[str, str]:
    """Map prompt IDs to tiers for per-run log metadata."""
    return {
        prompt_data["id"]: prompt_data.get("tier", prompt_key)
        for prompt_key, prompt_data in suite["prompts"].items()
    }


def get_prompt_for_tier(suite: dict, tier: str) -> tuple[str, str]:
    """Get the prompt text and ID for a given tier.

    Args:
        suite: Loaded prompt suite dictionary
        tier: Prompt tier (short, medium, long, soak)

    Returns:
        Tuple of (prompt_text, prompt_id)

    Raises:
        KeyError: If tier not found in suite
    """
    return get_prompts(suite, prompt_tier=tier)[0]


def main():
    parser = argparse.ArgumentParser(
        description="Laptop benchmark harness for llama.cpp server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Cold start run with short prompt
  python -m client.cli --node yoga --backend cpu --run-type cold --prompt-tier short

  # Warm start run with medium prompt
  python -m client.cli --node yoga --backend cpu --run-type warm --prompt-tier medium

  # Mock mode for testing (no server required)
  python -m client.cli --node yoga --backend cpu --run-type cold --prompt-tier short --mock

Prerequisites:
  1. Start llama.cpp server locally:
     llama-server -m models/<model>.gguf -c 2048 --port 8080 --host 127.0.0.1 -ngl 0

  2. Run this benchmark harness to measure TTFT and decode TPS.

Mock mode:
  Use --mock for dry-run testing without a server. Generates synthetic timing
  data to validate directory creation and JSONL schema.
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
        "--run-type",
        required=True,
        choices=["cold", "warm", "soak"],
        help="Run regime type"
    )
    parser.add_argument(
        "--prompt-tier",
        default=None,
        choices=["short", "medium", "long", "soak"],
        help="Prompt tier from suite"
    )
    parser.add_argument(
        "--prompt-id",
        default=None,
        help="Exact prompt ID from suite"
    )
    parser.add_argument(
        "--all-final-prompts",
        action="store_true",
        help="Run all final prompts from short, medium, and long tiers"
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
        default=1,
        help="Number of repetitions (default: 1)"
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
        help="Known anomalies affecting this run"
    )

    args = parser.parse_args()

    # Load prompt suite
    try:
        suite = load_prompt_suite(args.suite_path)
    except FileNotFoundError:
        print(f"Error: Prompt suite not found at {args.suite_path}", file=sys.stderr)
        print("Ensure configs/prompts/smoke_suite.json exists.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in prompt suite: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Invalid prompt suite: {e}", file=sys.stderr)
        sys.exit(1)

    # Get prompt selection.
    try:
        prompts = get_prompts(
            suite,
            prompt_tier=args.prompt_tier,
            prompt_id=args.prompt_id,
            all_final_prompts=args.all_final_prompts,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyError as e:
        print(f"Error: Prompt selection '{e.args[0]}' not found in suite", file=sys.stderr)
        sys.exit(1)
    prompt_tiers_by_id = get_prompt_tier_by_id(suite)

    # Build configuration
    config = BenchmarkConfig(
        node=args.node,
        backend=args.backend,
        run_type=args.run_type,
        prompt_tier=args.prompt_tier or "",
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

    try:
        validate_reproducibility_fields(config)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    output_dir = create_result_directory(config)
    print(f"Results directory: {output_dir}")

    # Run benchmark
    print(f"Running {args.repetitions} repetition(s)...")
    print(f"  Node: {config.node}")
    print(f"  Backend: {config.backend}")
    print(f"  Run type: {config.run_type}")
    if args.prompt_tier is not None:
        print(f"  Prompt tier: {args.prompt_tier}")
    elif args.prompt_id is not None:
        print(f"  Prompt ID: {args.prompt_id}")
    else:
        print("  Prompt selection: all final non-soak prompts")
    print(f"  Selected prompts: {len(prompts)}")
    print(f"  Server mode: {config.server_mode}")
    if config.mock:
        print("  Mode: MOCK (no server connection)")
    else:
        print(f"  Server: {config.host}:{config.port}")
    print()

    for prompt_text, prompt_id in prompts:
        prompt_config = replace(config, prompt_tier=prompt_tiers_by_id[prompt_id])
        if len(prompts) > 1:
            print(f"Prompt {prompt_id}...")

        for i in range(args.repetitions):
            print(f"Repetition {i + 1}/{args.repetitions}...", end=" ", flush=True)

            try:
                record = run_benchmark(
                    prompt=prompt_text,
                    prompt_id=prompt_id,
                    config=prompt_config,
                    output_dir=output_dir,
                    repetition_index=i
                )

                # Report results
                ttft_str = f"{record.ttft_ms:.1f}ms" if record.ttft_ms else "N/A"
                tps_str = f"{record.decode_tps:.2f}" if record.decode_tps else "N/A"
                print(
                    f"TTFT: {ttft_str}, Decode TPS: {tps_str}, "
                    f"Tokens: {record.generated_token_count}"
                )

            except Exception as e:
                print(f"FAILED: {e}", file=sys.stderr)
                sys.exit(1)

    print()
    print(f"Results written to: {output_dir / 'raw_metrics.jsonl'}")


if __name__ == "__main__":
    main()
