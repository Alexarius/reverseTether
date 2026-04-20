# Steady-State And Thermal Notes

This project treats thermal and environment data as optional context for
interpreting benchmark results. It does not treat a temperature snapshot as a
standalone explanation for a TTFT or Decode TPS change.

## Measurement Boundary

Thermal metadata must be captured outside the active inference window:

1. Capture a pre-run snapshot before the laptop client sends the prompt.
2. Run the benchmark without thermal polling during token generation.
3. Capture a post-run snapshot after the final token has been received.

Do not run `adb`, `dumpsys`, WMI, or thermal-zone polling during the active
request. Polling during inference can consume host CPU, phone CPU, USB/ADB
bandwidth, or scheduler attention, which can distort TTFT and Decode TPS.

## Available Metadata

Use whatever the platform exposes without changing the benchmark workload:

- Battery level and charging state from Android power-supply metadata.
- Battery temperature from Android battery metadata when readable.
- Thermal-zone snapshots from `/sys/class/thermal` when readable.
- Whether background apps were minimized before the run.
- Known anomalies, including notifications, screen wakeups, USB reconnects,
  server restarts, failed health checks, or manual intervention.

These fields are optional because Android builds differ in what they expose to a
shell process. Missing temperature data is acceptable if the absence is visible
in the metadata rather than guessed.

## Soak Interpretation

Soak runs are intended to show sustained behavior after repeated requests. The
primary evidence remains the benchmark log: TTFT, Decode TPS, generated token
count, prompt id, run regime, repetition index, and condition metadata.

When interpreting soak results:

- Compare like-for-like conditions only: same model, quantization, seed, context
  length, prompt suite, stopping rules, server mode, and backend.
- Report the trend across repetitions rather than a single best run.
- Treat falling Decode TPS during soak as a measured performance trend, not
  automatically as proof of thermal throttling.
- Use pre/post thermal snapshots and anomalies as supporting context only.
- Keep raw logs available even when summaries or plots are produced.

Acceptable wording:

- "Decode TPS declined during the soak window while the post-run battery
  temperature snapshot was higher than the pre-run snapshot."
- "Thermal metadata was unavailable for this run, so the soak trend is reported
  without attributing cause."

Avoid wording:

- "The phone throttled because temperature increased."
- "The accelerator is faster under soak" unless the comparison is controlled and
  uses the same benchmark settings.

## Suggested Manual Procedure

For phone runs, capture snapshots around the benchmark rather than during it:

```bash
./scripts/capture_phone_metadata.sh --phase pre_run > metadata_pre_run.json
python -m client.cli \
  --node s25ultra \
  --backend cpu \
  --run-type soak \
  --prompt-tier soak \
  --server-mode phone \
  --model-sha256 <64-hex-model-sha256> \
  --llama-cpp-commit <40-hex-llama-cpp-commit>
./scripts/capture_phone_metadata.sh --phase post_run > metadata_post_run.json
```

If something unusual happens, record it in the run notes or metadata:

```bash
./scripts/capture_phone_metadata.sh \
  --phase post_run \
  --known-anomalies "USB reconnect observed after repetition 3" \
  > metadata_post_run.json
```

The exact filenames may vary by run directory, but pre-run and post-run
snapshots should remain distinct so they cannot be mistaken for continuous
telemetry.
