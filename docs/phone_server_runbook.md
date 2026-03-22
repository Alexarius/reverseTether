# Phone Server Runbook

This runbook documents the procedures for launching and validating the llama.cpp server on the Samsung Galaxy S25 Ultra for the reverse-tethered benchmark.

## Device Specification

- **Device**: Samsung Galaxy S25 Ultra (SM-S938N)
- **SoC**: Snapdragon 8 Elite + Adreno 830
- **RAM**: 12 GB
- **OS**: Android 15
- **Runtime Environment**: Termux 0.118.3

## Prerequisites

### Termux Environment Setup

Install required packages in Termux:
```bash
pkg update && pkg upgrade
pkg install -y git cmake make ninja clang clinfo ocl-icd opencl-headers
```

### llama.cpp Build

Build llama.cpp with the appropriate flags. The `LD_LIBRARY_PATH` must be unset during compilation.

```bash
cd ~/llama.cpp
unset LD_LIBRARY_PATH

cmake -B build \
  -DGGML_OPENCL=ON \
  -DGGML_OPENCL_EMBED_KERNELS=ON \
  -DGGML_OPENCL_USE_ADRENO_KERNELS=ON \
  -DCMAKE_BUILD_TYPE=Release

cmake --build build --config Release -j$(nproc)
```

### Model Download

Download the primary model to the device:
```bash
mkdir -p ~/llama.cpp/models
cd ~/llama.cpp/models
# Download the model using your preferred method (wget, curl, or manual transfer)
```

**Required Model for Benchmark**:
- File: `Llama-3.2-1B-Instruct-Q4_0-GGUF` (or variant per PROJECT_BRIEF.md)
- Quantization: Q4_0 (mandatory for Adreno OpenCL compatibility)

## Server Launch Commands

### CPU Baseline Launch

Use this command for the mandatory CPU-only baseline:

```bash
LD_LIBRARY_PATH=/vendor/lib64 ./build/bin/llama-server \
  -m models/Llama-3.2-1B-Instruct-Q4_0-GGUF \
  -c 2048 \
  --port 8080 \
  --host 127.0.0.1 \
  -ngl 0
```

**Parameter explanation**:
| Flag | Value | Purpose |
|------|-------|---------|
| `LD_LIBRARY_PATH` | `/vendor/lib64` | Links Android vendor libraries at runtime |
| `-m` | model path | Specifies the GGUF model file |
| `-c` | `2048` | Context length (fixed per EXPERIMENT_PROTOCOL.md) |
| `--port` | `8080` | Server port for ADB forwarding |
| `--host` | `127.0.0.1` | Bind to localhost only |
| `-ngl` | `0` | CPU-only mode (no GPU offload) |

### GPU/OpenCL Launch (Controlled Extension)

```bash
LD_LIBRARY_PATH=/vendor/lib64 ./build/bin/llama-server \
  -m models/Llama-3.2-1B-Instruct-Q4_0-GGUF \
  -c 2048 \
  --port 8080 \
  --host 127.0.0.1 \
  -ngl 99
```

- `-ngl 99`: Offload all layers to GPU

## Health Check Procedures

After launching the server, validate it is running correctly.

### Health Endpoint Check

```bash
curl http://127.0.0.1:8080/health
```

**Expected response**:
```json
{"status":"ok"}
```

### Model List Check

```bash
curl http://127.0.0.1:8080/v1/models
```

**Expected response** (example):
```json
{
  "object": "list",
  "data": [
    {
      "id": "Llama-3.2-1B-Instruct-Q4_0-GGUF",
      "object": "model",
      ...
    }
  ]
}
```

### Simple Completion Test

```bash
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Say hello"}],
    "temperature": 0,
    "max_tokens": 10
  }'
```

## Metadata Capture

Before each benchmark session, capture device and runtime metadata using:

```bash
./scripts/capture_phone_metadata.sh > metadata.json
```

This script captures:
- llama.cpp commit hash and build info
- Device identifiers and OS version
- Battery state and charging status
- Thermal zone readings (if available)
- Server launch configuration

## Pre-Benchmark Checklist

Run this checklist before starting benchmark runs:

- [ ] **Background Apps**: Close all non-essential apps and disable sync
- [ ] **Battery State**: Record charging status; prefer benchmarking while plugged in OR unplugged, consistently
- [ ] **Thermal State**: Allow device to cool to ambient temperature before cold-start tests
- [ ] **Model File**: Verify model file integrity (checksum if available)
- [ ] **Server Arguments**: Confirm launch flags match the intended condition (CPU vs GPU)
- [ ] **Metadata Capture**: Run `capture_phone_metadata.sh` and verify output

## Troubleshooting

### Server Fails to Start

**Symptom**: Immediate exit with OpenCL errors

**Resolution**:
1. Verify `LD_LIBRARY_PATH=/vendor/lib64` is set
2. Check model file exists and is readable
3. For CPU baseline, ensure `-ngl 0` is set
4. Check available RAM: `free -h`

### Out of Memory (OOM)

**Symptom**: Server process killed by Android

**Resolution**:
1. Close background applications
2. Reduce context length if testing larger models
3. Consider smaller model variant
4. Monitor memory: `cat /proc/meminfo | grep -E "MemFree|MemAvailable"`

### Port Already in Use

**Symptom**: `Address already in use` error

**Resolution**:
1. Kill existing server: `pkill llama-server`
2. Verify port is free: `netstat -tlnp | grep 8080`

### Thermal Throttling

**Symptom**: Sudden performance degradation during soak tests

**Observation**:
1. Check thermal zones: `cat /sys/class/thermal/thermal_zone*/temp`
2. Allow cooldown period between intensive runs
3. Document thermal state in metadata

## Risks to Measurement Integrity

These factors can silently affect benchmark results:

| Risk | Impact | Mitigation |
|------|--------|------------|
| Thermal Throttling | Skewed soak/warm metrics | Monitor temp; allow cooldown |
| Background Processes | CPU/RAM contention | Minimize apps; record state |
| Inconsistent Launch Flags | Non-comparable runs | Use wrapper script |
| Environment Drift | Unreproducible results | Capture metadata every session |
| Battery/Charging State | Power management variance | Document and keep consistent |

## Version Control

When reporting results, always include:
- llama.cpp commit hash
- Build timestamp
- Model file name and checksum (if available)
- Server launch command exactly as executed

## Related Documents

- `PROJECT_BRIEF.md`: Hardware specs and project goals
- `EXPERIMENT_PROTOCOL.md`: Fixed generation settings and metric definitions
- `configs/server_metadata_schema.json`: JSON schema for metadata capture
- `scripts/launch_phone_server.sh`: Wrapper script for reproducible launch
- `scripts/capture_phone_metadata.sh`: Metadata capture script
