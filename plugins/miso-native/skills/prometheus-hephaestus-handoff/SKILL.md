---
name: prometheus-hephaestus-handoff
description: Plan with Prometheus, execute with Hephaestus using a strict handoff workflow
---

# Prometheus -> Hephaestus Handoff

Use this skill when you want higher-quality outcomes by separating planning and implementation.

## When To Use

- Multi-file feature work, refactors, or risky changes
- Tasks with unclear scope that benefit from interview-driven planning
- Work where you want a reusable plan artifact before coding

## Workflow

1. Enter planning mode with `/plan` or `/prometheus`.
2. Let Prometheus run interview + exploration until scope is decision-complete.
3. Save plan in `.sisyphus/plans/<plan-name>.md`.
4. Start implementation with Hephaestus using the plan as the single source of truth.
5. Verify with diagnostics, tests, and build before reporting done.

## Handoff Prompt Template

Use this exact prompt when switching to Hephaestus:

```text
Execute this plan end-to-end: .sisyphus/plans/<plan-name>.md

Rules:
1) Follow the plan order and acceptance criteria exactly.
2) If plan ambiguity appears, resolve it by reading codebase patterns first, then proceed.
3) Keep scope locked to the plan (no opportunistic expansion).
4) After edits, run diagnostics/tests/build relevant to changed files.
5) Report: what changed, verification results, and any residual risks.
```

## Guardrails

- Do not skip planning for non-trivial work.
- Do not let implementer reinterpret business scope.
- Do not mark complete without verification evidence.

## Recommended Defaults

- Planning quality: run Prometheus high-accuracy review when task has architecture impact.
- Execution mode: keep Hephaestus focused on implementation and verification only.
