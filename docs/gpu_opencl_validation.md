# GPU/OpenCL Validation Track

## Purpose

This note defines the controlled GPU/OpenCL validation path for the reverse-tethered phone condition. It is an operational validation track, not a replacement for the Phase 1 CPU baseline.

The CPU baseline logic, metric definitions, and aggregation math remain unchanged. GPU/OpenCL results must be logged and interpreted as a separate benchmark condition.

## Runtime And Quantization

The GPU/OpenCL validation path uses the same laptop-side measurement boundary as the CPU baseline:

- TTFT is measured from laptop request send to first generated token received by the laptop client.
- Decode TPS is measured only over the decode window after first-token arrival.
- Raw structured logs must be preserved.

The runtime difference is isolated to the phone-side llama.cpp server launch:

- CPU phone baseline: `-ngl 0`
- GPU/OpenCL validation: `-ngl 99`

The existing `scripts/launch_phone_server.sh --gpu` path sets `-ngl 99` for the GPU/OpenCL validation run. The Android vendor OpenCL libraries are exposed through `LD_LIBRARY_PATH=/vendor/lib64`, matching the documented phone server launch procedure.

Quantization remains `Q4_0` for this validation condition. If a future GPU/OpenCL run requires a different model format, quantization, context length, seed, sampling setting, or stopping rule, that run must receive a new benchmark condition id and must not be presented as a like-for-like CPU baseline comparison.

## Stability Note

Soak instability is possible and acceptable for this validation track. Instability must be recorded plainly in the raw logs and final interpretation rather than hidden or filtered away.

An unstable soak result may still be useful evidence that the GPU/OpenCL path was evaluated and rejected or limited for clear operational reasons. It must not be reported as a stable accelerator speedup unless repeated runs support that claim.

## Scope Boundary

This track must not modify the core benchmark client or aggregation code. In particular, the following files remain outside the scope of this validation documentation task:

- `client/matrix.py`
- `client/metrics.py`
- `analysis/aggregate.py`

Any later behavior change to the benchmark harness, metric computation, run regimes, or aggregation rules requires separate review under the project experiment protocol.
