"""Metric computation for laptop benchmark harness.

This module computes TTFT and decode TPS according to EXPERIMENT_PROTOCOL.md:
- TTFT: elapsed time from laptop client sending request to receiving first generated token
- Decode TPS: token generation rate over the decode window only (after first token)

These boundaries are intentional and must not be collapsed or redefined.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TimingData:
    """Raw timing data collected during a benchmark run."""

    request_sent_ts: float  # time.perf_counter() when request was sent
    first_token_ts: Optional[float] = None  # time.perf_counter() when first token received
    final_token_ts: Optional[float] = None  # time.perf_counter() when final token received
    generated_token_count: int = 0
    request_sent_wallclock: Optional[datetime] = None  # datetime when request was sent
    first_token_wallclock: Optional[datetime] = None  # datetime when first token received
    final_token_wallclock: Optional[datetime] = None  # datetime when final token received


@dataclass
class ComputedMetrics:
    """Metrics computed from timing data."""

    ttft_ms: Optional[float] = None  # Time to first token in milliseconds
    decode_tps: Optional[float] = None  # Tokens per second during decode window


def compute_ttft_ms(request_sent_ts: float, first_token_ts: float) -> float:
    """Compute Time To First Token in milliseconds.

    TTFT Definition (from EXPERIMENT_PROTOCOL.md):
    - Start: request leaves the laptop client
    - Stop: first token is received by the laptop client

    This includes: client-side request overhead, transport, server parsing,
    prefill, and computation needed to emit the first token.

    Args:
        request_sent_ts: perf_counter timestamp when request was sent
        first_token_ts: perf_counter timestamp when first token was received

    Returns:
        TTFT in milliseconds
    """
    elapsed_seconds = first_token_ts - request_sent_ts
    return elapsed_seconds * 1000.0


def compute_decode_tps(
    first_token_ts: float,
    final_token_ts: float,
    generated_token_count: int
) -> Optional[float]:
    """Compute decode throughput (tokens per second) over the decode window.

    Decode TPS Definition (from EXPERIMENT_PROTOCOL.md):
    - Start: first token arrival
    - Stop: final token arrival
    - Count: generated output tokens in the decode window

    This is the metric for sustained generation speed, not prompt responsiveness.

    Args:
        first_token_ts: perf_counter timestamp when first token was received
        final_token_ts: perf_counter timestamp when final token was received
        generated_token_count: total number of tokens generated (including first token)

    Returns:
        Decode TPS, or None if the decode window is too short or only one token was generated
    """
    # Decode window: from first token to final token
    decode_window_seconds = final_token_ts - first_token_ts

    # We measure tokens generated AFTER the first token
    # So if we have N total tokens, the decode window produces N-1 tokens
    tokens_in_decode_window = generated_token_count - 1

    if decode_window_seconds <= 0 or tokens_in_decode_window <= 0:
        return None

    return tokens_in_decode_window / decode_window_seconds


def compute_metrics(timing: TimingData) -> ComputedMetrics:
    """Compute all metrics from timing data.

    Args:
        timing: Raw timing data from a benchmark run

    Returns:
        ComputedMetrics with TTFT and decode TPS
    """
    metrics = ComputedMetrics()

    if timing.first_token_ts is not None:
        metrics.ttft_ms = compute_ttft_ms(timing.request_sent_ts, timing.first_token_ts)

    if timing.first_token_ts is not None and timing.final_token_ts is not None:
        metrics.decode_tps = compute_decode_tps(
            timing.first_token_ts,
            timing.final_token_ts,
            timing.generated_token_count
        )

    return metrics


@dataclass
class RunRecord:
    """Complete structured run record for a single benchmark execution.

    Fields follow the logging schema in EXPERIMENT_PROTOCOL.md.
    Required fields (no defaults) must come first.
    """

    # Run identity (required)
    timestamp: str  # ISO format
    run_id: str
    regime: str  # cold, warm, soak
    node: str  # yoga, s25ultra
    backend: str  # cpu, opencl, npu_experimental

    # Fields with defaults below
    repetition_index: int = 0
    server_mode: str = "local"  # local, phone

    # Model/settings metadata
    model_name: str = ""
    quantization: str = "Q4_0"
    context_length: int = 2048
    seed: int = 42
    temperature: float = 0.0
    max_new_tokens: int = 512

    # Prompt/output metadata
    prompt_id: str = ""
    prompt_tier: str = ""  # short, medium, long, soak
    prompt_token_count: Optional[int] = None
    generated_token_count: int = 0
    stop_reason: str = ""

    # Timing metadata (raw timestamps as ISO strings for logging)
    request_sent_timestamp: str = ""
    first_token_timestamp: str = ""
    final_token_timestamp: str = ""

    # Computed metrics
    ttft_ms: Optional[float] = None
    decode_tps: Optional[float] = None

    # Optional metadata
    notes: str = ""
