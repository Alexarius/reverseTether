# Issue 07 — Structured logging and run-record schema

## Summary
Define and implement the canonical raw run-record schema so benchmark results are machine-readable, auditable, and easy to aggregate later.

## Why this task exists
Without a stable schema, repeated measurements and later analysis become fragile and error-prone.

## Current milestone
Milestone 4 — Repeated measurement and soak automation

## Scope
- raw run-record schema,
- result directory convention,
- append-friendly logging behavior,
- required metadata fields,
- schema documentation.

## Out of scope
- no big plotting layer,
- no prompt-suite redesign,
- no GPU/NPU features.

## Allowed files
- logging / config files
- `client/**`
- `analysis/**`
- `docs/**`

## Acceptance criteria
- [ ] Every run produces a raw structured record.
- [ ] Required metadata fields are present.
- [ ] The schema is documented in repo docs.
- [ ] Derived outputs remain separate from raw logs.

## Validation
- inspect raw records from at least two runs,
- confirm schema consistency.

## Recommended tool
Copilot Agent Mode.

## Reviewer focus
Will this schema still make sense during dissertation writing months later?
