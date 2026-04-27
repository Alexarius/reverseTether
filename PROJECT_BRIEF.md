# Project Brief

## Title

Reverse-Tethered LLM Inference Benchmark: Laptop Client to Android Phone over ADB

## Core research question

Can a modern Android flagship used as a **reverse-tethered compute node** deliver better user-perceived inference performance than a legacy CPU-only laptop when TTFT is measured at the laptop boundary and decode TPS is measured separately?

## Project type

This is a **measurement-driven feasibility study**.

It is **not**:
- a production system,
- a polished consumer app,
- a distributed multi-phone inference platform,
- a model-partitioning project,
- or an NPU-first engineering effort.

## System under test

- **Laptop**: user-facing client and measurement harness.
- **Link**: USB with ADB port forwarding.
- **Phone**: headless llama.cpp server node.
- **Path**: laptop request -> ADB localhost forwarding -> phone llama.cpp server -> streamed tokens back to laptop.

## Primary metrics

- **TTFT**: elapsed time from laptop request send to first generated token received on the laptop.
- **Decode TPS**: token generation rate over the decode window only, after the first token has already arrived.

## Scope priorities

### Mandatory
1. Stable end-to-end reverse-tethered pipeline.
2. Laptop CPU-only baseline that is directly comparable.
3. Structured logging and repeatable automation.
4. Cold, warm, and steady-state / soak testing.
5. Clear comparison tables and plots.
6. Thermal-awareness and interpretation.
7. Controlled validation of the GPU/OpenCL path.

### Optional / later
1. NPU-oriented path if feasible.
2. Adaptive routing or dynamic placement.
3. More devices or extra baselines.
4. Partitioned or multi-device inference.

## Success definitions

### Strong success
Reverse-tethered phone shows lower TTFT and higher decode TPS than the laptop CPU-only baseline under the same settings, including after soak.

### Partial success
Reverse-tethered phone lowers TTFT but decode TPS is similar or worse. This still supports the idea that the phone can improve responsiveness through faster prefill.

### Negative / neutral but still valuable
Reverse-tethered phone does not outperform the laptop, but the result is clearly explained by transport overhead, decode bottlenecks, thermal throttling, or accelerator limitations.

## Recommended implementation defaults

- **Laptop harness language**: Python 3.11+ CLI.
- **Logging**: JSONL for raw runs, CSV/Markdown for summaries.
- **Analysis**: Python notebooks or scripts.
- **UI**: CLI first.
- **Phone runtime**: llama.cpp server build with reproducibility metadata recorded.
- **Primary model category**: open-weights, llama.cpp-compatible, decoder-only, 4-bit quantized.

## Hardware currently documented

### Laptop
- Yoga Slim 7-14ARE05 (Type 82A2)
- AMD Ryzen 7 4700U
- 16 GB RAM
- Windows 11 Education

### Phone
- Samsung Galaxy S25 Ultra (SM-S938N)
- Snapdragon 8 Elite + Adreno 830
- 12 GB RAM
- Android 15

## Required reproducibility metadata

For each evaluated condition, record:

- model name,
- parameter count,
- quantization,
- file checksum/hash,
- context length,
- generation settings,
- laptop OS + client version,
- phone build details,
- llama.cpp commit hash,
- server build flags,
- whether CPU, GPU/OpenCL, or experimental NPU path was used.