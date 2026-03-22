# Day 0 Runbook

This is the recommended first working session.

## 1) Create the repo

Create a clean repository for the benchmark.  
Do not start by asking an agent to “build the whole project.”

## 2) Drop in the control docs

Add:
- `PROJECT_BRIEF.md`
- `ARCHITECTURE.md`
- `EXPERIMENT_PROTOCOL.md`
- `AGENTS.md`
- `CODE_REVIEW.md`
- `MILESTONE_PLAN.md`
- `.github/copilot-instructions.md`

Commit them immediately.

Suggested commit message:
`docs: add benchmark control plane and agent instructions`

## 3) Fill the minimum TODOs

Before any coding session, fill:
- primary model,
- quantization,
- harness language choice,
- result/log directory convention,
- preferred package/environment tool,
- initial prompt suite outline.

You do not need every detail yet, but remove obvious ambiguity.

## 4) Run one planning pass

Pick one:
- **Gemini CLI `/plan`**
- **Codex `/plan`**

Ask it to:
- inspect the repo,
- identify missing assumptions,
- propose the smallest viable first implementation PR,
- and point out any measurement risks.

Do not allow edits yet.

## 5) Create the first 3 issues only

Create only these at first:
1. repo scaffold / directories / placeholders,
2. laptop-only baseline harness,
3. ADB forward health check.

Do not dump the full backlog into an agent on day 0.

## 6) Start with local baseline, not ADB

The benchmark should prove metric semantics locally before it adds transport complexity.

Best first implementation order:
1. local baseline endpoint path,
2. timing capture,
3. structured logging,
4. then ADB tunnel.

## 7) Use one primary builder

Use **Copilot Agent Mode** in your IDE as the main builder.

Prompt style:
- reference the issue,
- reference the docs,
- restrict allowed files,
- require validation,
- require a concise summary.

## 8) Use Codex as the reviewer

After Copilot finishes a meaningful slice:
- ask Codex to review the diff against `CODE_REVIEW.md`,
- look specifically for metric drift, logging ambiguity, and overengineering.

## 9) Only then expand the backlog

Once the first benchmark path exists, create the remaining issues and continue.

## 10) End every session with evidence hygiene

Before stopping:
- commit working state,
- note unresolved assumptions,
- add one `DECISION_LOG.md` entry if methodology changed,
- record what is manually verified vs only code-complete.
