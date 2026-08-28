---
description: Execute the Codex-designed task end to end and write evidence
agent: build
subtask: false
---

The user approves the current `.agent/plan.md` by invoking this command.

Read `AGENTS.md`, `.agents/skills/scoped-implementation/SKILL.md`, `.agent/task.md`,
`.agent/plan.md`, and the latest `.agent/review.md` if it contains a Codex `REPAIR` decision.
Use the default `build` agent to implement, test, call and monitor authorized real APIs, diagnose
artifacts, repair within the approved direction, and keep `.agent/implementation.md` current.

Treat all cited architecture, design, status, execution, task, plan, and review documents as
read-only. Preserve the current dirty worktree; do not reset, clean, checkout, commit, merge, or
discard unrelated changes. Return only after the planned mechanism is demonstrated or a genuine
architecture/external blocker is evidenced.

Additional user arguments: $ARGUMENTS
