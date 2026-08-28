# Code2Paper Repository Guidelines

## Authority Map

Read `docs/README.md` first; it is the documentation entry point. For the current Research Agent
development, preserve this precedence:

1. `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md` constrains overall
   architecture and trust direction. It is a specification, not a progress checklist.
2. `docs/publication_ready_method_writer_design_2026-07-31.md` constrains Method Writer subsystem
   quality and authority separation. It is a target design, not a completion ledger.
3. `docs/post_r8_research_agent_execution_plan_2026-07-31.md` is the current execution authority.
4. `docs/project_status_and_gap_report_2026-07-31.md` records current status when supported by its
   cited artifacts. Dated reports and `/tmp` outputs prove only their bound code/input/protocol.

Method Authoring quality (Candidate/Verified product path) currently executes
`docs/method_intent_first_authoring_redesign_2026-08-22.md`. That document implements
Writer-design §§1.3 and 1.6 and revises the 2026-08-21 “license is purely deterministic”
rule for the Candidate wording lane only. It does not replace items 1–4.

`.agent/task.md`, `.agent/plan.md`, `.agent/implementation.md`, and `.agent/review.md` coordinate one
task. They supplement but never replace the authorities above. If they conflict, stop and return to
Codex instead of silently choosing a new architecture or weakening a gate.

The ignored `.agent-team/` directory is a legacy coordination record from an earlier workflow. Do
not read or update it for the current task; the active handoff protocol is `.agent/`.

## Codex and OpenCode Workflow

- Codex owns architecture judgment, root-cause diagnosis, task and plan documents, final read-only
  acceptance, and integration decisions.
- OpenCode default `build` owns implementation, tests, authorized real API execution, monitoring,
  artifact analysis, in-direction repair, and `.agent/implementation.md`.
- Work serially in the same worktree. The current uncommitted Post-R8 changes are part of the
  baseline. Do not run `git reset`, `git clean`, checkout another branch, discard files, commit, or
  merge.
- OpenCode must not edit `AGENTS.md`, `.agent/task.md`, `.agent/plan.md`, `.agent/review.md`, or the
  architecture, design, status, execution, and ADR documents cited by the plan.
- After a Codex `REPAIR`, invoke `/implement` again in the same worktree. Do not create a new task
  or plan for an in-direction correction.
- Codex acceptance is read-only. It reviews OpenCode's diff, `.agent/implementation.md`, and frozen
  artifacts without rerunning tests, benchmarks, model calls, or real APIs.

## Project Structure

- Production package: `src/code2paper/`
- Agentic research and publication pipeline: `src/code2paper/agentic/`
- LLM clients, response recovery, role configuration, and section Writer: `src/code2paper/llm/`
- Tests: `tests/`; live profiles: `tests/live/profiles/`
- Operational and evaluation entry points: `scripts/`
- Durable design, status, execution, and evidence indexes: `docs/`
- Long-running output and live artifacts: fresh task-specific directories under `/tmp`

Preserve unrelated user changes in the dirty tree. Keep edits within the responsible subsystem and
explain every necessary deviation in `.agent/implementation.md`.

## Verification Commands

- Focused tests: `python -m pytest -q <test paths>`
- Full static suite, only when the active plan names a milestone: `python -m pytest -q`
- Syntax/import check when relevant: `python -m compileall -q src tests`
- Patch hygiene: `git diff --check`

Do not report progress by test count alone. Record the exact command, exit status, summary, and code
state in `.agent/implementation.md`. OpenCode runs required verification; Codex does not rerun it
during acceptance.

## Authorized Local LLM Runtime

The current designated local OpenAI-compatible runtime is:

- Base URL: `http://127.0.0.1:8003/v1`
- Model: `qwen36-27b-nvfp4`
- Context: `131072`
- Profile: `tests/live/profiles/qwen36_vllm_budgeted.example.env`

Before a planned live run, record `/health`, `/v1/models`, model identity, queue/KV-cache state when
available, and the fresh output directory. Never print or persist secrets. Monitor long requests.
Controlled concurrency on one local model is allowed for independent project runs when the engine
advertises sufficient sequence capacity: use distinct fresh output directories, cap Code2Paper at
four concurrent runs, and monitor running/waiting requests, KV-cache pressure, OOMs, and aborts.
Reduce concurrency when waiting persists or cache/resource pressure becomes unsafe. Do not repeat
an unchanged failed run merely to wait for a lucky sample.

## Non-Negotiable Boundaries

- Final positive Method claims require frozen repository evidence and reverse validation.
- Author intent may guide scope and organization but cannot authorize implementation facts.
- Keep evidence, qualifier, numeric/formula, authorship, callback, checkpoint, and final-integrity
  gates fail-closed. Never pass by filtering claims, weakening matching, reducing obligations, or
  treating missing output as success.
- Harness recovery may repair representation-only damage. Content, binding, evidence, and wording
  failures return to the owning Agent through a bounded, traced repair path.
- Final prose lexical tokens may originate only from Writer, Formalizer, Editor, or Rewrite as
  authorized by the current design.
- Historical project profiles may support diagnostics but cannot supply production fact authority.
- Project-specific source paths, symbols, claim text, or known answers must not enter generic
  production logic.
- A successful static suite or one live sample does not authorize D5 completion, rollout, default
  cutover, or release freeze.
