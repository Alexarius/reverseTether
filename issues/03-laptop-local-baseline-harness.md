# Issue 03 — Laptop local baseline harness

## Summary
Implement the smallest local-only baseline path so the laptop benchmark client can send a request to a local endpoint, record TTFT and decode TPS, and write a valid structured run record.

## Why this task exists
The project should prove the metric semantics locally before adding ADB and phone complexity.

## Current milestone
Milestone 1 — Laptop-only baseline

## Scope
- laptop-only request path,
- TTFT timing at the client boundary,
- decode TPS calculation,
- one valid structured raw run record,
- minimal CLI-first behavior.

## Out of scope
- no ADB,
- no phone runtime,
- no GPU/NPU,
- no soak automation yet,
- no elaborate UI.

## Allowed files
- `client/**`
- `configs/**`
- `tests/**`
- `docs/**`
- logging-related files if needed

## Acceptance criteria
- [ ] A local baseline request can be executed from the laptop harness.
- [ ] TTFT is measured from request send to first token receive.
- [ ] Decode TPS is computed over the decode window only.
- [ ] A raw structured run record is written.
- [ ] The implementation is simple enough to audit.

## Validation
- run one smoke local benchmark twice,
- confirm both raw run records are valid,
- inspect the timestamps and computed metrics manually.

## Recommended tool
Copilot Agent Mode first, then Codex review.

## Reviewer focus
Metric integrity first; overengineering second.
