#!/usr/bin/env python3
"""Verify final-suite fixture token counts against llama.cpp /tokenize output."""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


DEFAULT_SUITE_PATH = (
    Path(__file__).resolve().parents[1]
    / "configs"
    / "prompts"
    / "dataset_suite_v1.json"
)
TOKENIZE_URL = "http://localhost:8080/tokenize"


@dataclass
class TokenCountResult:
    prompt_id: str
    tier: str
    fixture_count: int | None
    actual_count: int | None
    status: str
    detail: str = ""


def load_prompt_suite(path: Path) -> list[dict[str, Any]]:
    """Load prompt dictionaries from the fixed final dataset suite."""
    with path.open("r", encoding="utf-8") as f:
        suite = json.load(f)

    prompts = suite.get("prompts")
    if isinstance(prompts, dict):
        return list(prompts.values())
    if isinstance(prompts, list):
        return prompts
    raise ValueError(f"Prompt suite at {path} does not contain a prompts object")


def fetch_token_count(prompt_text: str, timeout_seconds: float) -> int:
    """Call llama.cpp /tokenize and return the token array length."""
    response = requests.post(
        TOKENIZE_URL,
        json={"content": prompt_text},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    tokens = payload.get("tokens")
    if not isinstance(tokens, list):
        raise ValueError("/tokenize response did not contain a tokens array")
    return len(tokens)


def verify_prompts(
    prompts: list[dict[str, Any]],
    verify_server: bool,
    timeout_seconds: float,
) -> list[TokenCountResult]:
    """Compare fixture counts with server token counts when requested."""
    results: list[TokenCountResult] = []

    for prompt in prompts:
        prompt_id = str(prompt.get("id", ""))
        tier = str(prompt.get("tier", ""))
        fixture_count = prompt.get("fixture_prompt_token_count")
        prompt_text = prompt.get("text")

        if not isinstance(fixture_count, int):
            results.append(
                TokenCountResult(
                    prompt_id=prompt_id,
                    tier=tier,
                    fixture_count=None,
                    actual_count=None,
                    status="Error",
                    detail="missing integer fixture_prompt_token_count",
                )
            )
            continue

        if not isinstance(prompt_text, str):
            results.append(
                TokenCountResult(
                    prompt_id=prompt_id,
                    tier=tier,
                    fixture_count=fixture_count,
                    actual_count=None,
                    status="Error",
                    detail="missing prompt text",
                )
            )
            continue

        if not verify_server:
            results.append(
                TokenCountResult(
                    prompt_id=prompt_id,
                    tier=tier,
                    fixture_count=fixture_count,
                    actual_count=None,
                    status="Skipped",
                    detail="run with --verify-server to call /tokenize",
                )
            )
            continue

        try:
            actual_count = fetch_token_count(prompt_text, timeout_seconds)
        except (requests.RequestException, ValueError) as exc:
            results.append(
                TokenCountResult(
                    prompt_id=prompt_id,
                    tier=tier,
                    fixture_count=fixture_count,
                    actual_count=None,
                    status="Error",
                    detail=str(exc),
                )
            )
            continue

        status = "Match" if actual_count == fixture_count else "Mismatch"
        results.append(
            TokenCountResult(
                prompt_id=prompt_id,
                tier=tier,
                fixture_count=fixture_count,
                actual_count=actual_count,
                status=status,
            )
        )

    return results


def print_results(results: list[TokenCountResult]) -> None:
    """Print a compact summary table to stdout."""
    rows = [
        [
            result.prompt_id,
            result.tier,
            str(result.fixture_count) if result.fixture_count is not None else "-",
            str(result.actual_count) if result.actual_count is not None else "-",
            result.status,
            result.detail,
        ]
        for result in results
    ]
    headers = ["prompt_id", "tier", "fixture", "actual", "status", "detail"]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        if rows
        else len(headers[index])
        for index in range(len(headers))
    ]

    header_line = "  ".join(
        header.ljust(widths[index]) for index, header in enumerate(headers)
    )
    separator = "  ".join("-" * width for width in widths)
    print(header_line)
    print(separator)
    for row in rows:
        print(
            "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        )

    counts = {
        "Match": sum(result.status == "Match" for result in results),
        "Mismatch": sum(result.status == "Mismatch" for result in results),
        "Skipped": sum(result.status == "Skipped" for result in results),
        "Error": sum(result.status == "Error" for result in results),
    }
    print()
    print(
        "Summary: "
        f"{len(results)} prompts, "
        f"{counts['Match']} match, "
        f"{counts['Mismatch']} mismatch, "
        f"{counts['Skipped']} skipped, "
        f"{counts['Error']} error."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify configs/prompts/dataset_suite_v1.json fixture token counts "
            "against llama.cpp /tokenize output."
        )
    )
    parser.add_argument(
        "--verify-server",
        action="store_true",
        help="POST each prompt to http://localhost:8080/tokenize and compare counts.",
    )
    parser.add_argument(
        "--suite-path",
        type=Path,
        default=DEFAULT_SUITE_PATH,
        help="Prompt suite JSON path (default: configs/prompts/dataset_suite_v1.json).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout for each /tokenize request when --verify-server is set.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        prompts = load_prompt_suite(args.suite_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error loading prompt suite: {exc}", file=sys.stderr)
        return 1

    results = verify_prompts(
        prompts=prompts,
        verify_server=args.verify_server,
        timeout_seconds=args.timeout_seconds,
    )
    print_results(results)

    if any(result.status in {"Mismatch", "Error", "Skipped"} for result in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
