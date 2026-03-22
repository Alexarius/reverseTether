# Architecture

## Design intent

The laptop remains the user-facing device.  
The phone is repurposed as a **headless inference node** over a short, controlled USB link.

The architecture deliberately favors:
- clear measurement boundaries,
- simple transport,
- simple serving,
- and clean interpretation of system overhead.

## Key design rules

1. **Short controlled link**: use USB + ADB instead of Wi-Fi.
2. **Simple serving**: use llama.cpp server mode.
3. **Laptop boundary metrics**: measure user-perceived latency from the client.
4. **No model partitioning**: the full model runs on one device per condition.
5. **CLI before GUI**: the benchmark harness comes before interface polish.

## Components

### 1) Laptop client / measurement harness
Responsibilities:
- prepare prompts and generation settings,
- target either a local baseline endpoint or the forwarded phone endpoint,
- record timestamps,
- compute TTFT and decode TPS,
- count prompt/output tokens,
- write structured logs,
- orchestrate repeated runs.

### 2) ADB tunnel
Responsibilities:
- expose the phone server as a localhost endpoint on the laptop,
- provide a stable, repeatable transport path,
- fail loudly when forwarding is broken or the phone is unavailable.

### 3) Phone inference server
Responsibilities:
- launch a known llama.cpp server build,
- host the selected model,
- stream output tokens,
- expose enough metadata for reproducibility.

### 4) Analysis layer
Responsibilities:
- aggregate raw logs,
- compute medians, percentiles, and spread,
- compare laptop baseline vs reverse-tethered phone conditions,
- export charts/tables suitable for the dissertation.

## End-to-end request flow

1. Laptop client loads a prompt fixture and fixed generation parameters.
2. Laptop sends an HTTP request to a localhost endpoint.
3. For phone runs, ADB forwards that localhost endpoint to the phone server port.
4. Phone server performs tokenization, prefill, and decode.
5. First streamed token arrives back at the laptop.
6. Laptop records TTFT at that instant.
7. Laptop continues receiving tokens until termination.
8. Laptop computes decode TPS from the decode window only.
9. Laptop writes a structured run record.
10. Analysis scripts aggregate runs into comparable summaries.

## Measurement boundaries

### TTFT boundary
Start: request leaves the laptop client.  
Stop: first token is received by the laptop client.

Included:
- client request overhead,
- ADB/USB transport,
- server parse/tokenization,
- prefill,
- computation needed to emit the first token.

Excluded:
- any later manual analysis or plotting work.

### Decode TPS boundary
Start: first token arrival.  
Stop: final token arrival.  
Count: generated tokens in the decode window.

The project must not silently merge TTFT and decode TPS into a single latency number.

## Architecture non-goals

- no layer partitioning between laptop and phone,
- no multi-phone scheduling,
- no cloud dependency,
- no production authentication stack,
- no web UI,
- no elaborate orchestration framework unless clearly justified.

## Suggested repository ownership boundaries

### `client/`
Laptop benchmark client and adapters.

### `scripts/`
ADB lifecycle helpers, benchmark orchestration, setup helpers.

### `analysis/`
Aggregation, comparison, plots, sanity checks.

### `configs/`
Run configs, model metadata, prompt suite definitions.

### `results/`
Raw JSONL logs and derived outputs.

### `docs/`
Setup notes, troubleshooting, dissertation evidence notes.

## What the first implementation should prove

The very first meaningful architecture proof is:

- the same client can target both a local laptop baseline and a reverse-tethered phone endpoint,
- metric semantics stay identical across both conditions,
- the ADB tunnel can be verified before a benchmark starts,
- and raw results are reproducibly logged without hand timing.
