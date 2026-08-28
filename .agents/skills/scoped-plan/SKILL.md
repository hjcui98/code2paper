---
name: scoped-plan
description: "Let Codex turn the current project's AGENTS.md authority map, existing design, status, and execution documents into one substantial OpenCode assignment without creating a duplicate documentation system. Use for planning or handing implementation to OpenCode."
---

# Scoped Plan

Use this skill to prepare an OpenCode implementation handoff. Codex owns architecture, task
direction, and acceptance; do not implement product code while planning.

## Resolve Project Authority

1. Read the repository's nearest `AGENTS.md` first.
2. Follow its authority map to the existing documentation entry point, normative design, current
   status, active execution document, tests, runtime commands, and project boundaries.
3. Preserve the precedence declared by `AGENTS.md`. Treat `.agent/plan.md` only as a task-local
   supplement; never turn it into a competing architecture, status, or execution authority.
4. Reuse existing documents by exact path and section. Do not create a parallel design,
   remediation, progress, or task-management system.
5. If `AGENTS.md` does not identify enough authority to make a material decision, return to the
   user or update the appropriate existing project document before handing off implementation.

## Make One Substantial Assignment

Inspect enough code and evidence to identify the root cause, responsible layer, accepted mechanism,
invariants, and observable completion signals. Reject shortcuts that only improve a report, weaken
a gate, or hide an incomplete result.

Write or refresh:

- `.agent/task.md` for the stable user objective and role split;
- `.agent/plan.md` for authorities, starting evidence, architectural direction, implementation
  scope, tests, real execution, artifacts, acceptance signals, and return conditions;
- `.agent/review.md` only when recording a prior `REPAIR`, `PASS`, or `BLOCKED` decision.

Give OpenCode one coherent unit of work. Implementation, regression tests, authorized real API
execution, monitoring, artifact diagnosis, and repairs inside the approved direction should remain
in the same assignment. Do not split work by file or tiny iteration.

## Preserve Ownership

Codex alone edits architecture, design, status, active execution, planning, ADR, `.agent/task.md`,
`.agent/plan.md`, and `.agent/review.md`. OpenCode reads those as authority and writes implementation
evidence only to `.agent/implementation.md`, unless the plan explicitly authorizes another artifact.

Use the same worktree for serial Codex/OpenCode work. Preserve existing user changes. Do not ask
OpenCode to reset, clean, discard, commit, merge, or change branches unless `AGENTS.md` and the user
explicitly authorize it.
