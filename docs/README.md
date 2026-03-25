# docs/

Setup notes, troubleshooting, and dissertation evidence notes.

## Purpose

This directory contains:

- environment setup guides,
- troubleshooting notes,
- dissertation evidence documentation,
- metric timing boundary definitions.

## Metric Timing Boundaries

This section defines the exact measurement boundaries for TTFT and Decode TPS, which are critical for benchmark reproducibility.

### Time To First Token (TTFT)

**Definition**: Elapsed time from when the laptop client sends the HTTP request to when the first generated content token is received.

**Boundaries**:
- **Start**: `request_sent_ts` is recorded immediately BEFORE `requests.post()` is invoked
- **Stop**: `first_token_ts` is recorded when the first SSE data line containing a non-empty `content` field is parsed

**What TTFT includes**:
- Client-side HTTP request overhead
- Network transport latency (including reverse-tether USB bridge when applicable)
- Server-side request parsing
- Prompt tokenization and prefill (KV cache population)
- First token generation

**What TTFT excludes**:
- Decode time after the first token
- Any subsequent token generation

**Formula**: `ttft_ms = (first_token_ts - request_sent_ts) * 1000.0`

### Decode Tokens Per Second (Decode TPS)

**Definition**: Token generation rate during the decode phase only, measured from first token to final token arrival.

**Boundaries**:
- **Start**: `first_token_ts` (same timestamp used for TTFT stop)
- **Stop**: `final_token_ts` is recorded when the last content token is received (updated with each token, finalized at stream end)
- **Count**: `generated_token_count - 1` (tokens generated AFTER the first token)

**What Decode TPS includes**:
- Only the sustained token generation phase
- Token-by-token autoregressive decoding

**What Decode TPS excludes**:
- Prefill time (already captured in TTFT)
- First token generation time

**Formula**: `decode_tps = (generated_token_count - 1) / (final_token_ts - first_token_ts)`

**Edge cases**:
- Returns `None` if only 1 token generated (no decode window)
- Returns `None` if decode window duration is zero or negative

### Timer Resolution

All timing uses `time.perf_counter()` for microsecond-level precision, as `time.time()` may lack sufficient resolution on Windows platforms.

### Client Overhead Tracking

Raw run records include `client_overhead_ms` as an auxiliary measurement. This captures client-side processing time outside blocking HTTP and streaming waits, such as request preparation plus SSE parsing and token bookkeeping.

### Risks to Measurement Integrity

1. **Network/Library Buffering**: If the OS network stack or the requests library buffers incoming chunks, `first_token_ts` may be artificially late. This inflates TTFT and compresses the decode window, inflating Decode TPS.

2. **Zero-Token or Single-Token Generation**: If generation stops at or before the first token, the decode window may be zero, resulting in `decode_tps = None` (not a division error).

3. **Clock Drift**: Using `time.perf_counter()` provides monotonic timing that is not affected by system clock adjustments.

## Related docs

- `PROJECT_BRIEF.md` for project scope
- `EXPERIMENT_PROTOCOL.md` for benchmark methodology
- `DAY0_RUNBOOK.md` for initial setup checklist
