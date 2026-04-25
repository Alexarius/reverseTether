# Decision Log

Use one entry per decision that changes scope, methodology, tooling, model choice, or reproducibility.

---

## Entry Template

### Decision ID
`DL-YYYYMMDD-XX`

### Date
`TODO`

### Decision
State the decision in one sentence.

### Context
What problem or ambiguity triggered the decision?

### Options considered
- Option A:
- Option B:
- Option C:

### Chosen option
`TODO`

### Why this option was chosen
`TODO`

### Impact on methodology
Does this change:
- TTFT semantics?
- decode TPS semantics?
- prompt comparability?
- model/quantization comparability?
- run regimes?
- raw logging?
- dissertation claims?

### Implementation impact
Which files, scripts, or issues are affected?

### Risks introduced
`TODO`

### Follow-up actions
`TODO`

### Approved by
`TODO`

---

## First expected entries

- primary model selection,
- primary quantization selection,
- laptop harness language/environment choice,
- result directory convention,
- GPU/OpenCL inclusion or exclusion decision,
- NPU defer / proceed decision.

---

## DL-20260322-01: Primary Model Selection

### Decision ID
`DL-20260322-01`

### Date
2026-03-22

### Decision
The primary model is **Llama-3.2-1B-Instruct-Q4_0-GGUF** with a tiered fallback strategy allowing escalation up to 8B parameters based on empirical RAM validation.

### Context
The S25 Ultra has 12GB RAM, but Android 15 background processes and the 2048-token KV cache reduce available memory. A systematic approach is needed to select the largest feasible model without causing OOM kills.

### Options considered
- Option A: Start with 8B model and fall back if OOM occurs (risky, may corrupt benchmark state).
- Option B: Start with 1B model as the baseline, empirically test 3B and 8B in sequence (conservative, controlled).
- Option C: Use only 1B model regardless of available headroom (safe but leaves performance on the table).

### Chosen option
Option B: Tiered escalation starting from 1B.

### Why this option was chosen
- Prioritizes measurement integrity over maximum performance.
- The 1B model guarantees a stable baseline that will always complete.
- Larger models (3B, 8B) are tested only after confirming the smaller model runs without memory pressure.
- Aligns with PROJECT_BRIEF.md constraint: "largest from this list that reliably fits."

### Model candidate priority order
1. `unnicknameable/Llama-3.2-1B-Instruct-Q4_0-GGUF` (baseline, mandatory)
2. `lahirum/Llama-3.2-3B-Instruct-Q4_0-GGUF` (upgrade candidate)
3. `ggml-org/Meta-Llama-3.1-8B-Instruct-Q4_0-GGUF` (stretch goal)
4. `ggml-org/DeepSeek-R1-Distill-Qwen-1.5B-Q4_0-GGUF` (alternative 1.5B if Llama-3.2-1B has issues)

### Impact on methodology
- TTFT semantics? No change.
- Decode TPS semantics? No change.
- Prompt comparability? Preserved (same model across all conditions in a comparison set).
- Model/quantization comparability? Enforced (Q4_0 is mandatory for all candidates).
- Run regimes? No change.
- Raw logging? No change.
- Dissertation claims? Claims are limited to the model tier actually validated.

### Implementation impact
- `EXPERIMENT_PROTOCOL.md`: Model field already references this tiered approach.
- `PROJECT_BRIEF.md`: Candidate list is already documented.
- Benchmark harness (future): Must record which model tier was used.

### Risks introduced
- If 1B model is too slow for meaningful comparison, the benchmark may not demonstrate the phone's advantage.
- If 8B model cannot be validated empirically, claims about larger models are deferred.

### Follow-up actions
- Empirical RAM testing on S25 Ultra (Issue deferred per implementation plan).
- Update this entry once final model tier is validated via hardware testing.

### Approved by
Human reviewer (pending)

---

## DL-20260425-01: Separate Smoke and Final Prompt Suites

### Decision ID
`DL-20260425-01`

### Date
2026-04-25

### Decision
The existing development prompt suite is renamed and marked as `smoke_suite.json`, while `final_suite.json` is reserved for final dissertation benchmark prompts.

### Context
The initial prompt fixture was useful for smoke testing, but its IDs and filename did not clearly distinguish development prompts from final dissertation evidence.

### Options considered
- Option A: Keep a single `suite.json` for all prompt usage.
- Option B: Rename the current fixture to `smoke_suite.json` and reserve a separate final suite.
- Option C: Replace the current prompts with final prompts immediately.

### Chosen option
Option B: Separate smoke/development prompts from final benchmark prompts.

### Why this option was chosen
This preserves existing CLI smoke behavior while preventing development prompts from being mistaken for final dissertation evidence.

### Impact on methodology
- TTFT semantics? No change.
- Decode TPS semantics? No change.
- Prompt comparability? Preserved for smoke runs by keeping tiers and prompt text unchanged; final evidence requires the future final suite.
- Model/quantization comparability? No change.
- Run regimes? No change.
- Raw logging? Preserved; only prompt ID strings change to include `_smoke_v1`.
- Dissertation claims? Strengthened by explicitly excluding smoke prompts from final evidence.

### Implementation impact
- `configs/prompts/smoke_suite.json`: renamed current prompt fixture and updated IDs.
- `configs/prompts/final_suite.json`: added reserved placeholder.
- CLI defaults now point to the smoke suite.
- Documentation and tests now reflect smoke prompt IDs.

### Risks introduced
Historical raw logs using `short_v1`, `medium_v1`, `long_v1`, or `soak_v1` must not be mixed with new `_smoke_v1` logs without explicit mapping.

### Follow-up actions
Define, approve, and record the final dissertation prompt suite before collecting final evidence.

### Approved by
Human reviewer via approved plan slice

---

## DL-20260425-02: Exclude Historical Short-Prompt Results from Final Claims

### Decision ID
`DL-20260425-02`

### Date
2026-04-25

### Decision
Historical short-prompt results are excluded from final dissertation claims and retained only as development validation evidence.

### Context
Existing result folders contain early records using prompt IDs such as `short_v1`. Some repeated records show runtime prompt evaluation counts that are much smaller than the full prompt count, which indicates prompt-cache or server-state contamination risk. These runs were useful for proving the harness and hardware path, but they do not satisfy the final dataset or cache-control methodology.

### Options considered
- Option A: Include historical short-prompt results in final claims with caveats.
- Option B: Keep the historical results for audit but exclude them from final claims and default final aggregation.
- Option C: Delete the historical result folders.

### Chosen option
Option B: Preserve the historical data but exclude it from final claims.

### Why this option was chosen
It protects measurement integrity without hiding development evidence. The raw logs remain auditable, while final claims are based only on dataset-backed fixtures with explicit cache policy metadata.

### Impact on methodology
- TTFT semantics? No change.
- Decode TPS semantics? No change.
- Prompt comparability? Strengthened by separating short development prompts from final dataset prompts.
- Model/quantization comparability? No change.
- Run regimes? No change.
- Raw logging? Preserved; no raw logs are removed.
- Dissertation claims? Restricted to final dataset records that pass acceptance gates.

### Implementation impact
- `FINAL_RUN_MANIFEST.md`: Lists excluded historical result folders.
- `results/README.md`: Marks historical short-prompt folders as development-only.
- Final aggregation: Must filter historical short-prompt and smoke-suite records by default.

### Risks introduced
The final evidence set may be smaller until new final dataset runs are collected.

### Follow-up actions
Run the final dataset suite under the approved cache policy before making performance claims.

### Approved by
Human reviewer via PR 7 plan

---

## DL-20260425-03: Adopt Dataset-Backed Final Fixtures and Cache Gates

### Decision ID
`DL-20260425-03`

### Date
2026-04-25

### Decision
Final evidence uses dataset-backed prompt fixtures with explicit fixture token counts, runtime prompt evaluation counts, dataset metadata, and cache mismatch acceptance gates.

### Context
The project needs final prompts that are reproducible, supervisor-readable, and more representative than short smoke prompts. It also needs a way to detect prompt-cache reuse so TTFT and prompt evaluation comparisons are not contaminated by hidden server state.

### Options considered
- Option A: Continue using smoke prompts and rely on runtime prompt token counts only.
- Option B: Adopt dataset-backed final fixtures and add explicit cache/token-count acceptance metadata.
- Option C: Use external dataset records dynamically during each benchmark run.

### Chosen option
Option B: Dataset-backed fixtures with explicit cache and token-count gates.

### Why this option was chosen
Fixed dataset-backed fixtures preserve reproducibility while providing realistic prompt lengths. Separating `fixture_prompt_token_count` from `runtime_prompt_eval_token_count` allows final analysis to detect cache reuse without changing TTFT or decode TPS definitions.

### Impact on methodology
- TTFT semantics? No change.
- Decode TPS semantics? No change.
- Prompt comparability? Strengthened through stable final prompt IDs and suite metadata.
- Model/quantization comparability? No change.
- Run regimes? Preserved, with true cold runs requiring server restarts.
- Raw logging? Expanded with prompt suite, dataset, runtime token count, and cache fields.
- Dissertation claims? Must be based only on final dataset records where `cache_mismatch=false`.

### Implementation impact
- `EXPERIMENT_PROTOCOL.md`: Documents smoke vs final dataset suites and cache acceptance gates.
- `configs/README.md`: Documents dataset-backed fixture requirements.
- `docs/logging_schema.md`: Documents new prompt suite, dataset, runtime token count, and cache fields.
- `FINAL_RUN_MANIFEST.md`: Defines final run procedure and acceptance gates.

### Risks introduced
If the runtime cannot disable or verify prompt-cache behavior for warm and soak regimes, those records cannot be accepted as final evidence until cache handling is fixed or independently verified.

### Follow-up actions
Collect final dataset runs after confirming cache policy behavior and preserving raw logs.

### Approved by
Human reviewer via PR 7 plan

---

## DL-20260322-02: Mandatory Q4_0 Quantization

### Decision ID
`DL-20260322-02`

### Date
2026-03-22

### Decision
**Q4_0 is the mandatory quantization format** for all benchmark runs. No other quantization format is permitted for core comparisons.

### Context
Different quantization formats (Q4_K_M, Q5_K_S, Q8_0, etc.) produce different inference behavior and may have varying kernel support on the Adreno OpenCL backend. Allowing multiple formats would break comparability.

### Options considered
- Option A: Allow any 4-bit quantization (Q4_0, Q4_K_M, Q4_K_S) and document which was used.
- Option B: Mandate Q4_0 exclusively for all core benchmark conditions.
- Option C: Mandate Q4_K_M for quality, accept potential kernel incompatibility.

### Chosen option
Option B: Q4_0 mandatory.

### Why this option was chosen
- Q4_0 is the most mature format in llama.cpp with the broadest kernel coverage.
- Qualcomm Adreno OpenCL kernels in llama.cpp have explicit optimization for Q4_0.
- Using a single quantization eliminates hidden variables that could invalidate TTFT/TPS comparisons.
- Aligns with PROJECT_BRIEF.md rationale: "maximum kernel compatibility and optimization."

### Quantization rules
1. All model files must be Q4_0-quantized GGUF format.
2. If a candidate model is not available in Q4_0, it is excluded from the benchmark.
3. If an accelerator path (GPU/NPU) requires a different format, that path is treated as a **separate experimental condition**, not the primary benchmark.

### Impact on methodology
- TTFT semantics? No change.
- Decode TPS semantics? No change.
- Prompt comparability? Preserved.
- Model/quantization comparability? **Enforced** (this decision is the enforcement mechanism).
- Run regimes? No change.
- Raw logging? Must explicitly record quantization field.
- Dissertation claims? All TTFT/TPS claims are scoped to Q4_0 quantization.

### Implementation impact
- `EXPERIMENT_PROTOCOL.md`: Already specifies Q4_0 as a fixed setting.
- `PROJECT_BRIEF.md`: Already documents Q4_0 rationale.
- Model download scripts (future): Must verify GGUF filename includes Q4_0.
- Metadata logging: Must include quantization field in every run record.

### Risks introduced
- Comparability Breakdown: If Q4_0 is later found incompatible with a specific accelerator (e.g., future NPU backend), that accelerator cannot participate in core comparisons without a separate decision log entry.

### Follow-up actions
- Verify Q4_0 availability for all candidate models before first benchmark run.

### Approved by
Human reviewer (pending)

---

## DL-20260322-03: Reproducibility Metadata Requirements

### Decision ID
`DL-20260322-03`

### Date
2026-03-22

### Decision
The following reproducibility metadata fields are **mandatory** for every benchmark run and must be explicitly recorded in the run's `metadata.json` file.

### Context
Silent variations in model files, llama.cpp versions, or generation settings can cause irreproducible results. The benchmark's scientific validity depends on being able to recreate exact conditions.

### Options considered
- Option A: Record only model name and quantization (minimal).
- Option B: Record a comprehensive metadata set including checksums, commit hashes, and all generation parameters (thorough).
- Option C: Record metadata in free-form notes (flexible but inconsistent).

### Chosen option
Option B: Comprehensive mandatory metadata.

### Why this option was chosen
- Reproducibility Failure Risk: Without explicit metadata, two runs with the same "model name" could use different file versions, producing different token sequences.
- Audit Trail: Dissertation reviewers and future researchers must be able to verify exact conditions.
- Debugging: When results diverge unexpectedly, metadata enables root cause analysis.

### Mandatory metadata fields

#### Model identity
| Field | Description | Example |
|-------|-------------|---------|
| `model_name` | Full HuggingFace-style identifier | `unnicknameable/Llama-3.2-1B-Instruct-Q4_0-GGUF` |
| `model_filename` | Exact GGUF filename | `llama-3.2-1b-instruct-q4_0.gguf` |
| `model_sha256` | SHA-256 hash of the model file | `a1b2c3d4...` (64 hex chars) |
| `parameter_count` | Declared parameter count | `1000000000` |
| `quantization` | Quantization format | `Q4_0` |

#### Runtime environment
| Field | Description | Example |
|-------|-------------|---------|
| `llama_cpp_commit` | Full git commit hash of llama.cpp build | `abc123def456...` (40 hex chars) |
| `llama_cpp_build_flags` | CMake flags used in build | `GGML_OPENCL=ON GGML_OPENCL_USE_ADRENO_KERNELS=ON` |
| `server_launch_args` | Exact CLI arguments | `-m model.gguf -c 2048 --port 8080 -ngl 99` |

#### Generation settings
| Field | Description | Example |
|-------|-------------|---------|
| `context_length` | Maximum context window | `2048` |
| `seed` | Fixed RNG seed | `42` |
| `temperature` | Sampling temperature | `0.0` |
| `n_predict` | Max new tokens | `512` |

#### Device identity
| Field | Description | Example |
|-------|-------------|---------|
| `node_id` | Device identifier | `s25ultra` or `yoga` |
| `os_version` | OS build string | `Android 15 (UP1A.231005.007)` |
| `accelerator_mode` | Compute backend | `cpu`, `gpu_opencl`, or `npu_experimental` |

### Impact on methodology
- TTFT semantics? No change.
- Decode TPS semantics? No change.
- Prompt comparability? Preserved (metadata enables verification).
- Model/quantization comparability? **Strengthened** (checksums prevent silent model drift).
- Run regimes? No change.
- Raw logging? **Enhanced** (mandatory fields added).
- Dissertation claims? All claims can be traced to exact reproducible conditions.

### Implementation impact
- `EXPERIMENT_PROTOCOL.md`: Logging schema section reinforced.
- `PROJECT_BRIEF.md`: Required reproducibility metadata section already lists these fields.
- Benchmark harness (future): Must populate all mandatory fields in `metadata.json`.
- CI validation (future): Should reject runs with missing mandatory fields.

### Risks introduced
- Overhead: Collecting SHA-256 of large model files adds startup time (acceptable tradeoff).
- If llama.cpp commit hash is not recorded at build time, it may be difficult to retrieve later.

### Follow-up actions
- Document exact procedure for obtaining model SHA-256 in the benchmark harness implementation (future issue).
- Document procedure for retrieving llama.cpp commit hash at build time.

### Approved by
Human reviewer (pending)
