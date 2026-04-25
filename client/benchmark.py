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
import re
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional

import requests

from .metrics import TimingData, ComputedMetrics, RunRecord, compute_metrics


# Fixed generation settings from EXPERIMENT_PROTOCOL.md
DEFAULT_TEMPERATURE = 0.0
DEFAULT_SEED = 42
DEFAULT_MAX_TOKENS = 512
DEFAULT_CONTEXT_LENGTH = 2048
MODEL_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
LLAMA_CPP_COMMIT_PATTERN = re.compile(r"^[a-f0-9]{40}$")
WARM_CACHE_POLICIES = {
    "warm_cache",
    "cache_reuse_expected",
    "prompt_cache_reuse_expected",
    "kv_cache_reuse_expected",
}


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    node: str  # yoga, s25ultra
    backend: str  # cpu, opencl, npu_experimental
    run_type: str  # cold, warm, soak
    prompt_tier: str  # short, medium, long, soak

    # Prompt suite and cache metadata
    suite_type: str = "unknown"
    cache_policy: str = "unknown"
    fixture_prompt_token_count: Optional[int] = None

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
    model_filename: str = ""
    model_sha256: str = ""  # MANDATORY: 64 hex characters
    parameter_count: str = ""  # e.g., "1B", "3B", "8B"
    quantization: str = "Q4_0"

    # Device/runtime metadata
    laptop_identifier: str = ""
    phone_identifier: str = ""
    os_build_metadata: str = ""
    llama_cpp_commit: str = ""  # MANDATORY: Full 40-character git hash
    llama_cpp_build_flags: str = ""
    server_launch_args: str = ""

    # Optional thermal / environment metadata captured outside inference window
    start_temperature_c: Optional[float] = None
    end_temperature_c: Optional[float] = None
    temperature_source: str = ""
    start_battery_level_percent: Optional[int] = None
    end_battery_level_percent: Optional[int] = None
    battery_status: str = ""
    background_apps_minimized: Optional[bool] = None
    known_anomalies: str = ""

    # Mock mode for testing
    mock: bool = False


def validate_reproducibility_fields(config: BenchmarkConfig) -> None:
    """Validate mandatory reproducibility fields for real benchmark runs."""
    if config.mock:
        return

    if not MODEL_SHA256_PATTERN.fullmatch(config.model_sha256):
        raise ValueError(
            "model_sha256 must be exactly 64 lowercase hex characters for non-mock runs."
        )

    if not LLAMA_CPP_COMMIT_PATTERN.fullmatch(config.llama_cpp_commit):
        raise ValueError(
            "llama_cpp_commit must be exactly 40 lowercase hex characters for non-mock runs."
        )


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


def generate_mock_timing() -> tuple[TimingData, list[dict], str]:
    """Generate mock timing data for dry-run testing.

    Returns:
        Tuple of (timing_data, raw_events, stop_reason) with realistic mock values
    """
    import random

    # Simulate realistic timing values
    request_sent_ts = time.perf_counter()
    request_sent_wallclock = datetime.now()

    # Simulate TTFT between 100-500ms
    mock_ttft_seconds = random.uniform(0.1, 0.5)
    first_token_ts = request_sent_ts + mock_ttft_seconds
    first_token_wallclock = datetime.now()

    # Simulate generating 50-100 tokens at 10-30 TPS
    mock_token_count = random.randint(50, 100)
    mock_tps = random.uniform(10.0, 30.0)
    decode_duration = (mock_token_count - 1) / mock_tps
    final_token_ts = first_token_ts + decode_duration
    final_token_wallclock = datetime.now()

    timing = TimingData(
        request_sent_ts=request_sent_ts,
        first_token_ts=first_token_ts,
        final_token_ts=final_token_ts,
        generated_token_count=mock_token_count,
        client_overhead_ms=random.uniform(1.0, 5.0),
        request_sent_wallclock=request_sent_wallclock,
        first_token_wallclock=first_token_wallclock,
        final_token_wallclock=final_token_wallclock,
    )

    # Generate mock events
    events = [
        {"content": f"mock_token_{i}", "stop": False}
        for i in range(mock_token_count - 1)
    ]
    events.append({
        "content": "",
        "stop": True,
        "stop_type": "eos",
        "tokens_predicted": mock_token_count,
        "tokens_evaluated": random.randint(20, 100),  # Mock prompt tokens
    })

    return timing, events, "eos"


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


def _coerce_token_count(value: object) -> Optional[int]:
    """Normalize token-count values from llama.cpp metadata chunks."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def extract_prompt_token_count(events: list[dict]) -> Optional[int]:
    """Extract prompt token count from recent llama.cpp SSE metadata events.

    The final prompt token count may appear in slightly different metadata shapes
    depending on the llama.cpp server build. We inspect the most recent events so
    the benchmark is resilient to trailing stop markers or nearby metadata chunks.
    """
    recent_events = events[-3:]
    for event in reversed(recent_events):
        timings = event.get("timings")
        if isinstance(timings, dict):
            prompt_n = _coerce_token_count(timings.get("prompt_n"))
            if prompt_n is not None:
                return prompt_n

        for field_name in ("prompt_tokens", "tokens_evaluated"):
            token_count = _coerce_token_count(event.get(field_name))
            if token_count is not None:
                return token_count

    return None


def evaluate_cache_policy(
    cache_policy: str,
    fixture_prompt_token_count: Optional[int],
    runtime_prompt_eval_token_count: Optional[int],
) -> tuple[bool, str, bool]:
    """Evaluate cache expectations and observed prompt evaluation evidence."""
    normalized_policy = cache_policy.strip().lower()
    cache_expected = normalized_policy in WARM_CACHE_POLICIES
    cache_observed = "unknown"

    if runtime_prompt_eval_token_count is not None:
        collapsed_eval = runtime_prompt_eval_token_count == 1
        if (
            fixture_prompt_token_count is not None
            and fixture_prompt_token_count > 0
        ):
            collapsed_eval = (
                collapsed_eval
                or runtime_prompt_eval_token_count < fixture_prompt_token_count * 0.10
            )
        cache_observed = "collapsed_eval" if collapsed_eval else "full_eval"

    cache_mismatch = (
        not cache_expected and cache_observed == "collapsed_eval"
    )
    return cache_expected, cache_observed, cache_mismatch


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
    setup_start = time.perf_counter()
    url = f"http://{config.host}:{config.port}/completion"
    payload = build_completion_payload(prompt, config)

    timing = TimingData(request_sent_ts=0)
    events = []
    stop_reason = ""
    token_count = 0
    client_overhead_seconds = time.perf_counter() - setup_start

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
    status_check_start = time.perf_counter()
    response.raise_for_status()
    client_overhead_seconds += time.perf_counter() - status_check_start

    # Process SSE stream line by line
    line_iterator = response.iter_lines(decode_unicode=True)
    for line in line_iterator:
        process_start = time.perf_counter()

        if not line:
            client_overhead_seconds += time.perf_counter() - process_start
            continue

        data = parse_sse_line(line)
        if data is None:
            client_overhead_seconds += time.perf_counter() - process_start
            continue

        events.append(data)

        # TTFT starts only on a real generated token, not on empty or non-string chunks.
        content = data.get("content")
        if isinstance(content, str) and len(content) > 0:
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
            client_overhead_seconds += time.perf_counter() - process_start
            break

        client_overhead_seconds += time.perf_counter() - process_start

    finalize_start = time.perf_counter()
    timing.generated_token_count = token_count
    client_overhead_seconds += time.perf_counter() - finalize_start
    timing.client_overhead_ms = client_overhead_seconds * 1000.0
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
        # Model metadata
        "model_name": config.model_name,
        "model_filename": config.model_filename,
        "model_sha256": config.model_sha256,
        "parameter_count": config.parameter_count,
        "quantization": config.quantization,
        # Generation settings
        "context_length": DEFAULT_CONTEXT_LENGTH,
        "seed": config.seed,
        "temperature": config.temperature,
        "max_new_tokens": config.max_tokens,
        # Device/runtime metadata
        "laptop_identifier": config.laptop_identifier,
        "phone_identifier": config.phone_identifier,
        "os_build_metadata": config.os_build_metadata,
        "llama_cpp_commit": config.llama_cpp_commit,
        "llama_cpp_build_flags": config.llama_cpp_build_flags,
        "server_launch_args": config.server_launch_args,
        # Optional thermal / environment metadata
        "start_temperature_c": config.start_temperature_c,
        "end_temperature_c": config.end_temperature_c,
        "temperature_source": config.temperature_source,
        "start_battery_level_percent": config.start_battery_level_percent,
        "end_battery_level_percent": config.end_battery_level_percent,
        "battery_status": config.battery_status,
        "background_apps_minimized": config.background_apps_minimized,
        "known_anomalies": config.known_anomalies,
        # Mock mode indicator
        "mock_mode": config.mock,
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


def create_failed_run_record(
    prompt_id: str,
    config: BenchmarkConfig,
    repetition_index: int,
    error_message: str,
) -> RunRecord:
    """Create a durable error record for a failed matrix repetition."""
    timestamp = datetime.now().isoformat()
    benchmark_condition_id = f"{config.node}_{config.backend}_{config.server_mode}_{config.quantization}"
    cache_expected, cache_observed, cache_mismatch = evaluate_cache_policy(
        cache_policy=config.cache_policy,
        fixture_prompt_token_count=config.fixture_prompt_token_count,
        runtime_prompt_eval_token_count=None,
    )

    return RunRecord(
        timestamp=timestamp,
        run_id=str(uuid.uuid4()),
        regime=config.run_type,
        suite_type=config.suite_type,
        cache_policy=config.cache_policy,
        fixture_prompt_token_count=config.fixture_prompt_token_count,
        runtime_prompt_eval_token_count=None,
        cache_expected=cache_expected,
        cache_observed=cache_observed,
        cache_mismatch=cache_mismatch,
        repetition_index=repetition_index,
        benchmark_condition_id=benchmark_condition_id,
        node=config.node,
        backend=config.backend,
        server_mode=config.server_mode,
        laptop_identifier=config.laptop_identifier,
        phone_identifier=config.phone_identifier,
        os_build_metadata=config.os_build_metadata,
        llama_cpp_commit=config.llama_cpp_commit,
        llama_cpp_build_flags=config.llama_cpp_build_flags,
        server_launch_args=config.server_launch_args,
        model_name=config.model_name,
        model_filename=config.model_filename,
        model_sha256=config.model_sha256,
        parameter_count=config.parameter_count,
        quantization=config.quantization,
        context_length=DEFAULT_CONTEXT_LENGTH,
        seed=config.seed,
        temperature=config.temperature,
        max_new_tokens=config.max_tokens,
        stop_config="eos_or_max_tokens",
        prompt_id=prompt_id,
        prompt_tier=config.prompt_tier,
        prompt_token_count=None,
        generated_token_count=0,
        stop_reason="error",
        request_sent_timestamp=timestamp,
        first_token_timestamp="",
        final_token_timestamp="",
        ttft_ms=0.0,
        decode_tps=0.0,
        client_overhead_ms=0.0,
        start_temperature_c=config.start_temperature_c,
        end_temperature_c=config.end_temperature_c,
        temperature_source=config.temperature_source,
        start_battery_level_percent=config.start_battery_level_percent,
        end_battery_level_percent=config.end_battery_level_percent,
        battery_status=config.battery_status,
        background_apps_minimized=config.background_apps_minimized,
        known_anomalies=config.known_anomalies,
        notes=error_message,
    )


def run_benchmark(
    prompt: str,
    prompt_id: str,
    config: BenchmarkConfig,
    output_dir: Optional[Path] = None,
    repetition_index: int = 0,
    skip_metadata: bool = False,
) -> RunRecord:
    """Execute a single benchmark run.

    Args:
        prompt: The prompt text to send
        prompt_id: Identifier for the prompt
        config: Benchmark configuration
        output_dir: Output directory (created if None)
        repetition_index: Index of this repetition
        skip_metadata: If True, skip writing metadata.json (used by matrix runner)

    Returns:
        Completed RunRecord with all metrics
    """
    validate_reproducibility_fields(config)

    if output_dir is None:
        output_dir = create_result_directory(config)

    # Execute the benchmark (real or mock)
    if config.mock:
        timing, events, stop_reason = generate_mock_timing()
    else:
        timing, events, stop_reason = stream_completion(prompt, config)

    # Compute metrics (post-processing, after all tokens received)
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

    # Generate benchmark condition ID for grouping comparable runs
    benchmark_condition_id = f"{config.node}_{config.backend}_{config.server_mode}_{config.quantization}"
    runtime_prompt_eval_token_count = extract_prompt_token_count(events)
    cache_expected, cache_observed, cache_mismatch = evaluate_cache_policy(
        cache_policy=config.cache_policy,
        fixture_prompt_token_count=config.fixture_prompt_token_count,
        runtime_prompt_eval_token_count=runtime_prompt_eval_token_count,
    )

    # Build the run record with all mandatory fields
    record = RunRecord(
        # Run identity
        timestamp=request_sent_wallclock.isoformat(),
        run_id=str(uuid.uuid4()),
        regime=config.run_type,
        suite_type=config.suite_type,
        cache_policy=config.cache_policy,
        fixture_prompt_token_count=config.fixture_prompt_token_count,
        runtime_prompt_eval_token_count=runtime_prompt_eval_token_count,
        cache_expected=cache_expected,
        cache_observed=cache_observed,
        cache_mismatch=cache_mismatch,
        repetition_index=repetition_index,
        benchmark_condition_id=benchmark_condition_id,
        node=config.node,
        backend=config.backend,
        server_mode=config.server_mode,
        # Device/runtime metadata
        laptop_identifier=config.laptop_identifier,
        phone_identifier=config.phone_identifier,
        os_build_metadata=config.os_build_metadata,
        llama_cpp_commit=config.llama_cpp_commit,
        llama_cpp_build_flags=config.llama_cpp_build_flags,
        server_launch_args=config.server_launch_args,
        # Model/settings metadata
        model_name=config.model_name,
        model_filename=config.model_filename,
        model_sha256=config.model_sha256,
        parameter_count=config.parameter_count,
        quantization=config.quantization,
        context_length=DEFAULT_CONTEXT_LENGTH,
        seed=config.seed,
        temperature=config.temperature,
        max_new_tokens=config.max_tokens,
        stop_config="eos_or_max_tokens",
        # Prompt/output metadata
        prompt_id=prompt_id,
        prompt_tier=config.prompt_tier,
        prompt_token_count=runtime_prompt_eval_token_count,
        generated_token_count=timing.generated_token_count,
        stop_reason=stop_reason,
        # Timing metadata
        request_sent_timestamp=request_sent_wallclock.isoformat(),
        first_token_timestamp=first_token_wallclock,
        final_token_timestamp=final_token_wallclock,
        # Computed metrics
        ttft_ms=metrics.ttft_ms,
        decode_tps=metrics.decode_tps,
        client_overhead_ms=timing.client_overhead_ms,
        # Optional thermal / environment metadata
        start_temperature_c=config.start_temperature_c,
        end_temperature_c=config.end_temperature_c,
        temperature_source=config.temperature_source,
        start_battery_level_percent=config.start_battery_level_percent,
        end_battery_level_percent=config.end_battery_level_percent,
        battery_status=config.battery_status,
        background_apps_minimized=config.background_apps_minimized,
        known_anomalies=config.known_anomalies,
    )

    if not skip_metadata:
        write_metadata_file(config, output_dir)

    # Write the record (post-processing, after metric computation)
    write_run_record(record, output_dir)

    return record


@dataclass
class MatrixConfig:
    """Configuration for a benchmark matrix run.

    The matrix runner executes benchmarks across multiple regimes (cold, warm, soak)
    with multiple repetitions per regime.
    """

    regimes: List[str]  # e.g., ["cold", "warm", "soak"]
    repetitions: int  # Number of repetitions per regime
    prompt_tier: Optional[str] = None  # short, medium, long, soak
    prompt_id: Optional[str] = None
    all_final_prompts: bool = False
    prompt_selection_mode: str = "prompt_tier"
    prompt_tiers_by_id: Optional[Dict[str, str]] = None
    soak_prompt: Optional[dict] = None
    dry_run: bool = False  # If True, log actions but don't execute


@dataclass
class MatrixRunResult:
    """Result from a single run within the matrix."""

    regime: str
    repetition_index: int
    success: bool
    prompt_id: str = ""
    record: Optional[RunRecord] = None
    error_message: str = ""


def create_matrix_output_directory(
    base_config: BenchmarkConfig,
    output_dir: Optional[Path] = None,
) -> Path:
    """Create the output directory for a matrix run.

    Directory naming: results/{YYYYMMDD_HHMMSS}_{node}_{backend}_matrix/

    Args:
        base_config: Base benchmark configuration
        output_dir: Override output directory if specified

    Returns:
        Path to the created directory
    """
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{timestamp}_{base_config.node}_{base_config.backend}_matrix"
    result_dir = Path("results") / dir_name
    result_dir.mkdir(parents=True, exist_ok=True)
    return result_dir


def write_matrix_metadata(
    base_config: BenchmarkConfig,
    matrix_config: MatrixConfig,
    prompts: List[dict],
    output_dir: Path,
) -> Path:
    """Write metadata.json for the matrix run directory.

    Args:
        base_config: Base benchmark configuration
        matrix_config: Matrix configuration
        prompts: Prompt fixture objects
        output_dir: Output directory

    Returns:
        Path to the metadata file
    """
    metadata_file = output_dir / "metadata.json"
    metadata = {
        "run_type": "matrix",
        "regimes": matrix_config.regimes,
        "repetitions": matrix_config.repetitions,
        "prompt_selection_mode": matrix_config.prompt_selection_mode,
        "prompt_tier": matrix_config.prompt_tier,
        "prompt_id": matrix_config.prompt_id,
        "all_final_prompts": matrix_config.all_final_prompts,
        "selected_prompt_ids": _matrix_selected_prompt_ids(matrix_config, prompts),
        "dry_run": matrix_config.dry_run,
        "node": base_config.node,
        "backend": base_config.backend,
        "server_mode": base_config.server_mode,
        "host": base_config.host,
        "port": base_config.port,
        # Model metadata
        "model_name": base_config.model_name,
        "model_filename": base_config.model_filename,
        "model_sha256": base_config.model_sha256,
        "parameter_count": base_config.parameter_count,
        "quantization": base_config.quantization,
        # Generation settings
        "context_length": DEFAULT_CONTEXT_LENGTH,
        "seed": base_config.seed,
        "temperature": base_config.temperature,
        "max_new_tokens": base_config.max_tokens,
        # Device/runtime metadata
        "laptop_identifier": base_config.laptop_identifier,
        "phone_identifier": base_config.phone_identifier,
        "os_build_metadata": base_config.os_build_metadata,
        "llama_cpp_commit": base_config.llama_cpp_commit,
        "llama_cpp_build_flags": base_config.llama_cpp_build_flags,
        "server_launch_args": base_config.server_launch_args,
        # Optional thermal / environment metadata
        "start_temperature_c": base_config.start_temperature_c,
        "end_temperature_c": base_config.end_temperature_c,
        "temperature_source": base_config.temperature_source,
        "start_battery_level_percent": base_config.start_battery_level_percent,
        "end_battery_level_percent": base_config.end_battery_level_percent,
        "battery_status": base_config.battery_status,
        "background_apps_minimized": base_config.background_apps_minimized,
        "known_anomalies": base_config.known_anomalies,
        # Mock mode indicator
        "mock_mode": base_config.mock,
    }

    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    return metadata_file


def _matrix_selected_prompt_ids(
    matrix_config: MatrixConfig,
    prompts: List[dict],
) -> List[str]:
    """Return matrix prompt IDs, including the fixed soak prompt when present."""
    prompt_ids = [prompt_obj["id"] for prompt_obj in prompts]
    if matrix_config.soak_prompt is not None:
        soak_prompt_id = matrix_config.soak_prompt["id"]
        if soak_prompt_id not in prompt_ids:
            prompt_ids.append(soak_prompt_id)
    return prompt_ids


def _prompts_for_regime(
    regime: str,
    prompts: List[dict],
    matrix_config: MatrixConfig,
) -> List[dict]:
    """Resolve the prompt workload for a specific matrix regime."""
    prompt_tiers_by_id = matrix_config.prompt_tiers_by_id or {}

    if regime == "soak":
        soak_prompts = []
        if matrix_config.soak_prompt is not None:
            soak_prompts.append(matrix_config.soak_prompt)
        soak_prompts.extend(
            prompt_obj
            for prompt_obj in prompts
            if prompt_tiers_by_id.get(prompt_obj["id"]) == "soak"
        )
        unique_soak_prompts = []
        seen_prompt_ids = set()
        for prompt_obj in soak_prompts:
            prompt_id = prompt_obj["id"]
            if prompt_id in seen_prompt_ids:
                continue
            unique_soak_prompts.append(prompt_obj)
            seen_prompt_ids.add(prompt_id)
        if len(unique_soak_prompts) != 1:
            raise ValueError("Soak regime requires exactly one fixed soak prompt")
        return unique_soak_prompts

    normal_prompts = [
        prompt_obj
        for prompt_obj in prompts
        if prompt_tiers_by_id.get(
            prompt_obj["id"],
            matrix_config.prompt_tier or "",
        ) != "soak"
    ]
    if not normal_prompts:
        raise ValueError("Cold and warm regimes require non-soak prompts")
    return normal_prompts


def run_matrix(
    prompts: List[dict],
    base_config: BenchmarkConfig,
    matrix_config: MatrixConfig,
    output_dir: Optional[Path] = None,
    on_regime_start: Optional[Callable[[str], None]] = None,
    on_run_complete: Optional[Callable[[MatrixRunResult], None]] = None,
) -> List[MatrixRunResult]:
    """Execute a benchmark matrix across regimes and repetitions.

    The matrix runner executes benchmarks in this order:
    1. For each regime in matrix_config.regimes:
       a. Call on_regime_start callback (for cold starts, user must restart server)
       b. Resolve the prompts for that regime:
          - cold/warm use non-soak prompts
          - soak uses exactly one fixed soak prompt
       c. For each resolved prompt:
          - For each repetition in range(matrix_config.repetitions):
            - Execute benchmark run
            - Record result
            - Call on_run_complete callback

    CRITICAL MEASUREMENT INTEGRITY NOTES:
    - Cold regime: The caller is responsible for ensuring the server is restarted
      before cold runs. The on_regime_start callback should be used to prompt
      the user or trigger a server restart.
    - Warm regime: Assumes server is already warm from prior requests.
    - Soak regime: Captures thermally-constrained behavior after repeated requests.
      Falling Decode TPS is expected due to thermal throttling.

    Args:
        prompts: Prompt fixture objects
        base_config: Base benchmark configuration (run_type will be overridden per regime)
        matrix_config: Matrix configuration specifying regimes and repetitions
        output_dir: Override output directory (auto-generated if None)
        on_regime_start: Callback invoked at the start of each regime.
            IMPORTANT: For cold regime, this callback should ensure server restart.
        on_run_complete: Callback invoked after each run completes.

    Returns:
        List of MatrixRunResult for each run in the matrix.

    Raises:
        ValueError: If reproducibility fields are invalid for non-mock runs.
    """
    # Validate reproducibility fields upfront
    validate_reproducibility_fields(base_config)

    # Create output directory
    actual_output_dir = create_matrix_output_directory(base_config, output_dir)

    # Write matrix metadata
    write_matrix_metadata(base_config, matrix_config, prompts, actual_output_dir)

    results: List[MatrixRunResult] = []
    prompt_tiers_by_id = matrix_config.prompt_tiers_by_id or {}

    for regime in matrix_config.regimes:
        # Signal regime start (caller should handle cold restart if needed)
        if on_regime_start is not None:
            on_regime_start(regime)

        for prompt_obj in _prompts_for_regime(regime, prompts, matrix_config):
            prompt = prompt_obj["text"]
            prompt_id = prompt_obj["id"]
            fixture_prompt_token_count = prompt_obj.get("fixture_prompt_token_count")
            if regime == "soak":
                prompt_tier = "soak"
            else:
                prompt_tier = prompt_tiers_by_id.get(
                    prompt_id,
                    matrix_config.prompt_tier or "",
                )

            for rep_idx in range(matrix_config.repetitions):
                # Create config for this specific run
                run_config = BenchmarkConfig(
                    node=base_config.node,
                    backend=base_config.backend,
                    run_type=regime,  # Override with current regime
                    prompt_tier=prompt_tier,
                    suite_type=base_config.suite_type,
                    cache_policy=base_config.cache_policy,
                    fixture_prompt_token_count=fixture_prompt_token_count,
                    host=base_config.host,
                    port=base_config.port,
                    server_mode=base_config.server_mode,
                    temperature=base_config.temperature,
                    seed=base_config.seed,
                    max_tokens=base_config.max_tokens,
                    model_name=base_config.model_name,
                    model_filename=base_config.model_filename,
                    model_sha256=base_config.model_sha256,
                    parameter_count=base_config.parameter_count,
                    quantization=base_config.quantization,
                    laptop_identifier=base_config.laptop_identifier,
                    phone_identifier=base_config.phone_identifier,
                    os_build_metadata=base_config.os_build_metadata,
                    llama_cpp_commit=base_config.llama_cpp_commit,
                    llama_cpp_build_flags=base_config.llama_cpp_build_flags,
                    server_launch_args=base_config.server_launch_args,
                    start_temperature_c=base_config.start_temperature_c,
                    end_temperature_c=base_config.end_temperature_c,
                    temperature_source=base_config.temperature_source,
                    start_battery_level_percent=base_config.start_battery_level_percent,
                    end_battery_level_percent=base_config.end_battery_level_percent,
                    battery_status=base_config.battery_status,
                    background_apps_minimized=base_config.background_apps_minimized,
                    known_anomalies=base_config.known_anomalies,
                    mock=base_config.mock,
                )

                result = MatrixRunResult(
                    regime=regime,
                    prompt_id=prompt_id,
                    repetition_index=rep_idx,
                    success=False,
                )

                if matrix_config.dry_run:
                    # Dry run: log intent but don't execute
                    result.success = True
                    result.error_message = "dry_run"
                else:
                    try:
                        record = run_benchmark(
                            prompt=prompt,
                            prompt_id=prompt_id,
                            config=run_config,
                            output_dir=actual_output_dir,
                            repetition_index=rep_idx,
                            skip_metadata=True,  # Matrix metadata already written
                        )
                        result.success = True
                        result.record = record
                    except Exception as e:
                        # Log failure but continue with matrix
                        # CRITICAL: Do not silently skip - capture the error for audit
                        result.success = False
                        result.error_message = str(e)
                        result.record = create_failed_run_record(
                            prompt_id=prompt_id,
                            config=run_config,
                            repetition_index=rep_idx,
                            error_message=result.error_message,
                        )
                        write_run_record(result.record, actual_output_dir)

                results.append(result)

                if on_run_complete is not None:
                    on_run_complete(result)

    return results
