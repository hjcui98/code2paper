---
name: scoped-implementation
description: "Let the OpenCode default build agent execute a Codex-approved project plan end to end, including code changes, regression tests, authorized real API runs, monitoring, artifact analysis, in-direction repair, and evidence reporting. Use when the user invokes /implement."
---

# Scoped Implementation

Use this skill for `/implement`. Run the normal OpenCode `build` agent; this command is an entry
point, not a separate orchestration platform.

## Read the Authorities

1. Read the nearest `AGENTS.md` and follow its project-specific authority map and boundaries.
2. Read the architecture, design, current status, and active execution sections cited by
   `.agent/plan.md`.
3. Read `.agent/task.md`, `.agent/plan.md`, and the latest `.agent/review.md` when it contains a
   `REPAIR` direction.
4. Treat `.agent` files as task-local supplements. If they conflict with an upper-level authority
   in a way that changes architecture, safety, scope, or acceptance, report `BLOCKED` to Codex.

## Execute End to End

Within Codex's approved direction:

- inspect and modify the responsible production code, tests, scripts, configuration, and fixtures;
- add regressions for each real failure and run the focused and milestone checks named in the plan;
- use and monitor only the real API/runtime authorized by `AGENTS.md` and `.agent/plan.md`;
- preserve exact commands, outputs, artifact paths, model/runtime identity, and earliest-loss
  diagnosis;
- repair defects that remain inside the approved design and rerun affected checks without asking
  for a new micro-plan;
- never repeat an unchanged failed real run: change code, test, runtime condition, or diagnosis
  first;
- keep safety and evidence gates fail-closed; never pass by filtering claims, reducing obligations,
  weakening validation, or adding project-specific answers.

Continue until the plan's mechanism is demonstrated, evidence disproves the direction, a new
architecture decision is necessary, or an external dependency is genuinely unavailable.

## Report Without Redesigning

Keep `.agent/implementation.md` current with:

- state (`WORKING`, `COMPLETE`, or `BLOCKED`);
- files and behavior changed;
- exact focused/full test results;
- real API health, calls, monitoring, run identities, and artifact paths;
- each evidence-driven repair and the result after repair;
- remaining risks and a stable handoff statement.

Do not edit `AGENTS.md`, `.agent/task.md`, `.agent/plan.md`, `.agent/review.md`, architecture,
design, status, execution, or ADR documents. Do not create a duplicate report system. Do not reset,
clean, checkout, commit, merge, or discard the shared worktree.
