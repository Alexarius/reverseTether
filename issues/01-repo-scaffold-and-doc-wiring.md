# Issue 01 — Repo scaffold and doc wiring

## Summary
Create the initial repository structure and wire in the control documents so all agents have a stable context before implementation starts.

## Why this task exists
The project needs a control plane before code generation, otherwise agent behavior will drift and tasks will become too broad.

## Current milestone
Milestone 0 — Control docs and repo scaffold

## Scope
- create the agreed top-level directories,
- place the control docs in the right locations,
- ensure the repository can support issue-driven agent work,
- add placeholders where future benchmark code will live.

## Out of scope
- no benchmark logic,
- no device code,
- no ADB automation,
- no results analysis,
- no GUI.

## Allowed files
- root docs
- `.github/**`
- empty directory placeholders / placeholder README files

## Acceptance criteria
- [ ] Root control docs are present.
- [ ] `.github/copilot-instructions.md` is present.
- [ ] issue and PR templates are present.
- [ ] suggested directories exist or are clearly documented.
- [ ] no benchmark semantics are invented or changed.

## Validation
- inspect the repo tree manually,
- confirm the docs are readable from the repo root,
- confirm the issue template is visible on GitHub once pushed.

## Recommended tool
Copilot Agent Mode or a normal manual commit.

## Reviewer focus
Did the task remain documentation/scaffolding only?
