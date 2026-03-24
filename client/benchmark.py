"""Benchmark execution for laptop harness.

This module handles:
- Sending requests to the llama.cpp server
- Processing streamed responses
- Recording timestamps for TTFT and decode TPS computation

Critical timing notes (from implementation plan):
- Timer starts immediately BEFORE the HTTP request is invoked
- stream=True must be used to detect first token arrival accurately
- No hidden retries that inflate TTFT
- Token counting uses server-reported values when available
"""

import json
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import requests

from .metrics import TimingData, ComputedMetrics, RunRecord, compute_metrics


# Fixed generation settings from EXPERIMENT_PROTOCOL.md
DEFAULT_TEMPERATURE = 0.0
DEFAULT_SEED = 42
DEFAULT_MAX_TOKENS = 512
DEFAULT_CONTEXT_LENGTH = 2048


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    node: str  # yoga, s25ultra
    backend: str  # cpu, opencl, npu_experimental
    run_type: str  # cold, warm, soak
    prompt_tier: str  # short, medium, long, soak

    # Server endpoint
    host: str = "127.0.0.1"
    port: int = 8080

    # Server mode: "local" or "phone" (reverse-tethered)
    server_mode: str = "local"

    # Generation settings (fixed per EXPERIMENT_PROTOCOL.md)
    temperature: float = DEFAULT_TEMPERATURE
    seed: int = DEFAULT_SEED
    max_tokens: int = DEFAULT_MAX_TOKENS

    # Model metadata (filled by caller)
    model_name: str = ""
    quantization: str = "Q4_0"


def build_completion_payload(prompt: str, config: BenchmarkConfig) -> dict:
    """Build the request payload for llama.cpp /completion endpoint.

    Args:
        prompt: The prompt text to send
        config: Benchmark configuration

    Returns:
        Dictionary payload for the API request
    """
    return {
        "prompt": prompt,
        "n_predict": config.max_tokens,
        "temperature": config.temperature,
        "seed": config.seed,
        "stream": True,
    }


def parse_sse_line(line: str) -> Optional[dict]:
    """Parse a Server-Sent Events line from llama.cpp.

    llama.cpp streams responses as SSE with format:
    data: {"content": "token", ...}

    Args:
        line: A single line from the SSE stream

    Returns:
        Parsed JSON data, or None if not a data line
    """
    line = line.strip()
    if not line.startswith("data: "):
        return None

    json_str = line[6:]  # Remove "data: " prefix
    if json_str == "[DONE]":
        return None

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def stream_completion(
    prompt: str,
    config: BenchmarkConfig,
    timeout: float = 300.0
) -> tuple[TimingData, list[dict], str]:
    """Stream a completion request and collect timing data.

    This function implements the critical timing boundaries:
    - request_sent_ts: recorded immediately BEFORE requests.post()
    - first_token_ts: recorded when first content token arrives
    - final_token_ts: recorded when last token arrives or stream ends

    Args:
        prompt: The prompt text to send
        config: Benchmark configuration
        timeout: Request timeout in seconds

    Returns:
        Tuple of (timing_data, raw_events, stop_reason)

    Raises:
        requests.RequestException: If the request fails
    """
    url = f"http://{config.host}:{config.port}/completion"
    payload = build_completion_payload(prompt, config)

    timing = TimingData(request_sent_ts=0)
    events = []
    stop_reason = ""
    token_count = 0

    # Start timer immediately before request
    timing.request_sent_wallclock = datetime.now()
    timing.request_sent_ts = time.perf_counter()

    # Use stream=True with small chunk iteration to detect first token accurately
    # No retry logic - fail loudly if connection fails
    response = requests.post(
        url,
        json=payload,
        stream=True,
        timeout=timeout,
        headers={"Accept": "text/event-stream"}
    )
    response.raise_for_status()

    # Process SSE stream line by line
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue

        data = parse_sse_line(line)
        if data is None:
            continue

        events.append(data)

        # Check for content token
        content = data.get("content", "")
        if content:
            token_count += 1
            now = time.perf_counter()
            now_wallclock = datetime.now()

            # Record first token timestamp
            if timing.first_token_ts is None:
                timing.first_token_ts = now
                timing.first_token_wallclock = now_wallclock

            # Always update final token timestamp
            timing.final_token_ts = now
            timing.final_token_wallclock = now_wallclock

        # Check for stop condition
        if data.get("stop", False):
            stop_reason = data.get("stop_type", "eos")
            # Use server-reported token count if available
            if "tokens_predicted" in data:
                token_count = data["tokens_predicted"]
            break

    timing.generated_token_count = token_count
    return timing, events, stop_reason


def create_result_directory(config: BenchmarkConfig) -> Path:
    """Create the result directory for this benchmark run.

    Directory naming: results/{YYYYMMDD_HHMMSS}_{node}_{backend}_{run_type}/

    Args:
        config: Benchmark configuration

    Returns:
        Path to the created directory
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{timestamp}_{config.node}_{config.backend}_{config.run_type}"
    result_dir = Path("results") / dir_name
    result_dir.mkdir(parents=True, exist_ok=True)
    return result_dir


def write_metadata_file(config: BenchmarkConfig, output_dir: Path) -> Path:
    """Write metadata.json for the benchmark run directory."""
    metadata_file = output_dir / "metadata.json"
    metadata = {
        "node": config.node,
        "backend": config.backend,
        "run_type": config.run_type,
        "prompt_tier": config.prompt_tier,
        "server_mode": config.server_mode,
        "host": config.host,
        "port": config.port,
        "model_name": config.model_name,
        "quantization": config.quantization,
        "context_length": DEFAULT_CONTEXT_LENGTH,
        "seed": config.seed,
        "temperature": config.temperature,
        "max_new_tokens": config.max_tokens,
    }

    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    return metadata_file


def write_run_record(record: RunRecord, output_dir: Path) -> Path:
    """Append a run record to raw_metrics.jsonl.

    Args:
        record: The run record to write
        output_dir: Directory to write to

    Returns:
        Path to the metrics file
    """
    metrics_file = output_dir / "raw_metrics.jsonl"
    record_dict = asdict(record)

    with open(metrics_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record_dict) + "\n")

    return metrics_file


def run_benchmark(
    prompt: str,
    prompt_id: str,
    config: BenchmarkConfig,
    output_dir: Optional[Path] = None,
    repetition_index: int = 0
) -> RunRecord:
    """Execute a single benchmark run.

    Args:
        prompt: The prompt text to send
        prompt_id: Identifier for the prompt
        config: Benchmark configuration
        output_dir: Output directory (created if None)
        repetition_index: Index of this repetition

    Returns:
        Completed RunRecord with all metrics
    """
    if output_dir is None:
        output_dir = create_result_directory(config)

    # Execute the benchmark
    timing, events, stop_reason = stream_completion(prompt, config)

    # Compute metrics
    metrics = compute_metrics(timing)
    request_sent_wallclock = timing.request_sent_wallclock or datetime.now()
    first_token_wallclock = (
        timing.first_token_wallclock.isoformat()
        if timing.first_token_wallclock is not None
        else ""
    )
    final_token_wallclock = (
        timing.final_token_wallclock.isoformat()
        if timing.final_token_wallclock is not None
        else ""
    )

    # Build the run record
    record = RunRecord(
        timestamp=request_sent_wallclock.isoformat(),
        run_id=str(uuid.uuid4()),
        regime=config.run_type,
        repetition_index=repetition_index,
        node=config.node,
        backend=config.backend,
        server_mode=config.server_mode,
        model_name=config.model_name,
        quantization=config.quantization,
        context_length=DEFAULT_CONTEXT_LENGTH,
        seed=config.seed,
        temperature=config.temperature,
        max_new_tokens=config.max_tokens,
        prompt_id=prompt_id,
        prompt_tier=config.prompt_tier,
        prompt_token_count=None,  # Filled from server response if available
        generated_token_count=timing.generated_token_count,
        stop_reason=stop_reason,
        request_sent_timestamp=request_sent_wallclock.isoformat(),
        first_token_timestamp=first_token_wallclock,
        final_token_timestamp=final_token_wallclock,
        ttft_ms=metrics.ttft_ms,
        decode_tps=metrics.decode_tps,
    )

    # Try to get prompt token count from first event
    if events and "tokens_evaluated" in events[-1]:
        record.prompt_token_count = events[-1]["tokens_evaluated"]

    write_metadata_file(config, output_dir)

    # Write the record
    write_run_record(record, output_dir)

    return record
