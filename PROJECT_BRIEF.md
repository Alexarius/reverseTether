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

## Human approval required before any change to:

- metric definitions,
- prompt suite,
- fixed generation settings,
- primary model or quantization,
- repo scope,
- device topology,
- or claims in the dissertation.

## Open TODOs to fill before coding

## Completed Pre-Coding Decisions

- [x] **Choose the exact primary model:** - **Candidates for empirical memory-limit testing:**
    1. `ggml-org/DeepSeek-R1-Distill-Qwen-1.5B-Q4_0-GGUF`
    2. `unnicknameable/Llama-3.2-1B-Instruct-Q4_0-GGUF`
    3. `lahirum/Llama-3.2-3B-Instruct-Q4_0-GGUF`
    4. `ggml-org/Meta-Llama-3.1-8B-Instruct-Q4_0-GGUF`
  - **Final selection constraint:** The primary model will be the largest from this list that reliably fits within the S25 Ultra's available RAM while leaving sufficient headroom for Android 15 background processes and the 2048-token context window without triggering Out-Of-Memory (OOM) kills.

- [x] **Choose the exact 4-bit quantization:** - **Format:** `Q4_0`
  - **Rationale:** `Q4_0` is the most mature and universally supported quantization format in the `llama.cpp` ecosystem, ensuring maximum kernel compatibility and optimization with the Qualcomm Adreno OpenCL backend.

- [x] **Choose the laptop harness package manager / environment workflow:** - **Environment:** Native Python 3.11+ `venv` to guarantee zero-overhead reproducibility on Windows 11.
  - **Dependencies (`requirements.txt`):** `requests` (for REST API communication), `pandas` (for CSV summaries), `matplotlib` (for plotting TTFT/TPS metrics), and `tqdm` (for CLI progress indication).

- [x] **Decide the result directory naming convention:** - **Structure:** `results/{YYYYMMDD_HHMMSS}_{node}_{backend}_{run_type}/`
  - **Variables:**
    - `{node}`: `s25ultra` or `yoga`
    - `{backend}`: `opencl` or `cpu`
    - `{run_type}`: `cold`, `warm`, or `soak`
  - **Directory Contents:** Every run folder must contain `raw_metrics.jsonl`, `metadata.json`, and `server_log.txt`.

- [x] **Decide the exact prompt suite:** - **Methodology:** Fixed, explicit hardcoded prompts sent over the Python API. `llama-bench` will *not* be used for final metric gathering, as it relies on synthetic text generation rather than deterministic, real-world instruction parsing.
  - **Suite Tiers (Context Load Tests):**
    - **Short (~50 tokens):** Chat-style query to measure baseline TTFT.
    - **Medium (~500 tokens):** RAG-style summarization task.
    - **Long (~1500 tokens):** Code or dense text analysis to measure sustained decode TPS under high KV-cache pressure.
  - **Settings:** `temperature = 0.0` to enforce deterministic generation across all nodes.

- [x] **Record llama.cpp build and server launch details:**
  - **S25 Ultra Build Environment:** Termux 0.118.3.
  - **Package Dependencies:** `pkg install -y git cmake make ninja clang clinfo ocl-icd opencl-headers`
  - **Build Workaround:** Must ensure `LD_LIBRARY_PATH` is unset during compilation to avoid conflicting with Android NDK headers (`unset LD_LIBRARY_PATH`).
  - **CMake Configuration Flags:**
    ```bash
    cmake -B build \
      -DGGML_OPENCL=ON \
      -DGGML_OPENCL_EMBED_KERNELS=ON \
      -DGGML_OPENCL_USE_ADRENO_KERNELS=ON \
      -DCMAKE_BUILD_TYPE=Release
    ```
  - **Build Command:** `cmake --build build --config Release -j$(nproc)`
  - **Server Launch Command (Phone OpenCL):** Requires explicitly linking the Android vendor partition at runtime.
    ```bash
    LD_LIBRARY_PATH=/vendor/lib64 ./build/bin/llama-server -m models/<model_name>.gguf -c 2048 --port 8080 --host 127.0.0.1 -ngl 99
    ```
  - **Server Launch Command (Phone CPU Baseline):** Identical to above, but with `-ngl 0`.
  - **Laptop Link Command:** Executed on the Yoga Windows client to establish the reverse-tethered bridge:
    ```powershell
    adb forward tcp:8080 tcp:8080
    ```
  - *(Sources: `llama.cpp` official build documentation; Qualcomm Developer Blog for Adreno OpenCL flags; localized compilation tests on S25 Ultra).*