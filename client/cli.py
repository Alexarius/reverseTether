"""CLI entry point for laptop benchmark harness.

Usage:
    python -m client.cli --node yoga --backend cpu --run-type cold --prompt-tier short

This is a minimal CLI-first benchmark harness per Issue 03 requirements.
No elaborate UI - just command-line interface for measurement.
"""

import argparse
import json
import sys
from pathlib import Path

from .benchmark import BenchmarkConfig, run_benchmark, create_result_directory


def load_prompt_suite(suite_path: Path) -> dict:
    """Load the prompt suite configuration.

    Args:
        suite_path: Path to the prompt suite JSON file

    Returns:
        Dictionary mapping prompt tier to prompt data
    """
    with open(suite_path, "r", encoding="utf-8") as f:
        return json.load(f)


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
    prompt_data = suite["prompts"][tier]
    return prompt_data["text"], prompt_data["id"]


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

Prerequisites:
  1. Start llama.cpp server locally:
     llama-server -m models/<model>.gguf -c 2048 --port 8080 --host 127.0.0.1 -ngl 0

  2. Run this benchmark harness to measure TTFT and decode TPS.
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
        type=Path,
        default=Path("configs/prompts/suite.json"),
        help="Path to prompt suite JSON"
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Number of repetitions (default: 1)"
    )

    args = parser.parse_args()

    # Load prompt suite
    try:
        suite = load_prompt_suite(args.suite_path)
    except FileNotFoundError:
        print(f"Error: Prompt suite not found at {args.suite_path}", file=sys.stderr)
        print("Ensure configs/prompts/suite.json exists.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in prompt suite: {e}", file=sys.stderr)
        sys.exit(1)

    # Get prompt for the specified tier
    try:
        prompt_text, prompt_id = get_prompt_for_tier(suite, args.prompt_tier)
    except KeyError:
        print(f"Error: Prompt tier '{args.prompt_tier}' not found in suite", file=sys.stderr)
        sys.exit(1)

    # Build configuration
    config = BenchmarkConfig(
        node=args.node,
        backend=args.backend,
        run_type=args.run_type,
        prompt_tier=args.prompt_tier,
        host=args.host,
        port=args.port,
        server_mode=args.server_mode,
        model_name=args.model_name,
    )

    # Create output directory
    output_dir = create_result_directory(config)
    print(f"Results directory: {output_dir}")

    # Run benchmark
    print(f"Running {args.repetitions} repetition(s)...")
    print(f"  Node: {config.node}")
    print(f"  Backend: {config.backend}")
    print(f"  Run type: {config.run_type}")
    print(f"  Prompt tier: {config.prompt_tier}")
    print(f"  Server mode: {config.server_mode}")
    print(f"  Server: {config.host}:{config.port}")
    print()

    for i in range(args.repetitions):
        print(f"Repetition {i + 1}/{args.repetitions}...", end=" ", flush=True)

        try:
            record = run_benchmark(
                prompt=prompt_text,
                prompt_id=prompt_id,
                config=config,
                output_dir=output_dir,
                repetition_index=i
            )

            # Report results
            ttft_str = f"{record.ttft_ms:.1f}ms" if record.ttft_ms else "N/A"
            tps_str = f"{record.decode_tps:.2f}" if record.decode_tps else "N/A"
            print(f"TTFT: {ttft_str}, Decode TPS: {tps_str}, Tokens: {record.generated_token_count}")

        except Exception as e:
            print(f"FAILED: {e}", file=sys.stderr)
            sys.exit(1)

    print()
    print(f"Results written to: {output_dir / 'raw_metrics.jsonl'}")


if __name__ == "__main__":
    main()
