---
name: acceptance-review
description: "Let Codex perform a read-only architectural review of a stable OpenCode handoff against the current project's AGENTS.md authority map, code diff, submitted tests, real-run artifacts, and invariants, then return PASS, REPAIR, or BLOCKED without rerunning tests, benchmarks, or APIs."
---

# Acceptance Review

Use this skill after OpenCode marks `.agent/implementation.md` `COMPLETE` or `BLOCKED` and all code,
tests, real API calls, monitoring, and artifact writes have stopped.

## Require a Stable Handoff

If OpenCode is still editing, testing, calling an API, monitoring, or describing the task as
continuing, stop and report that no stable handoff exists. Do not wait for or take over execution.

## Review Read Only

1. Read the nearest `AGENTS.md` and the project authorities it identifies.
2. Read `.agent/task.md`, `.agent/plan.md`, any prior `.agent/review.md`, and the completed
   `.agent/implementation.md`.
3. Inspect the actual diff and exact submitted test, runtime, and artifact evidence.
4. Decide whether the root cause was fixed at the correct layer and whether all relevant evidence,
   provenance, scope, budget, quality, and safety invariants still hold.
5. Treat test counts, metric movement, and one lucky model run as evidence only; they are not a
   substitute for the planned mechanism and acceptance surface.

Keep review read-only. Do not run tests, linters, quality suites, model calls, real APIs,
benchmarks, replays, or monitors. If evidence is missing, stale, inconsistent, or belongs to a
different code state, return `REPAIR` and require OpenCode to produce it.

## Record One Decision

Write `.agent/review.md` with exactly one outcome:

- `PASS`: the approved mechanism and evidence satisfy the task.
- `REPAIR`: identify the failed mechanism or unsupported claim, give the next in-direction repair,
  and state the required evidence. OpenCode continues with `/implement` in the same worktree.
- `BLOCKED`: a genuine user/architecture decision or unavailable external dependency prevents a
  valid implementation or judgment.

On `REPAIR`, keep the same task unless its architecture materially changes. On `PASS`, update the
existing project status or active execution document only when the accepted evidence changes
repository status. Do not create a parallel documentation hierarchy or declare a larger milestone
that the task did not prove.
