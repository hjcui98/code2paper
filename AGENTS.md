# Code2Paper Repository Guidelines

## Authority Map

Read `docs/README.md` first; it is the documentation entry point. For the current Research Agent
development, preserve this precedence:

1. `docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md` constrains overall
   architecture and trust direction. It is a specification, not a progress checklist.
2. `docs/publication_ready_method_writer_design_2026-07-31.md` constrains Method Writer subsystem
   quality and authority separation. It is a target design, not a completion ledger.
3. `docs/post_r8_research_agent_execution_plan_2026-07-31.md` is the Post-R8 execution baseline;
   use the applicable subsystem revisions indexed by `docs/README.md` for subsequent work.
4. `docs/project_status_and_gap_report_2026-07-31.md` records current status when supported by its
   cited artifacts. Dated reports and `/tmp` outputs prove only their bound code/input/protocol.

Method Authoring quality (Candidate/Verified product path) currently executes
`docs/method_intent_first_authoring_redesign_2026-08-22.md`. That document implements
Writer-design §§1.3 and 1.6 and revises the 2026-08-21 “license is purely deterministic”
rule for the Candidate wording lane only. It does not replace items 1–4.

For Method Agent mainline work, also follow
`docs/method_agent_master_agent_mainline_execution_repair_plan_2026-08-17.md`. Unified Context work
follows the 2026-09-06 and 2026-09-08 execution revisions indexed by `docs/README.md`. These are
scoped revisions, not permission to replace the overall architecture or weaken quality gates.

The current user request defines the task. `.agent/README.md` describes optional local records;
they supplement the design documents and do not independently authorize work. Resolve stale task
instructions against the current request and applicable design; ask only if a substantive conflict
remains unresolved. Do not silently choose a new architecture or weaken a gate.

`.agent/archive/` and the ignored `.agent-team/` are historical records, not active instructions.
Do not load them by default; consult `.agent/archive/` only when historical evidence is needed.
Do not read or update `.agent-team/`.

## Codex Workflow

- Codex owns diagnosis, planning, implementation, tests, authorized live execution, monitoring,
  artifact analysis, review, and in-direction repair. Complete the requested work directly.
- OpenCode is no longer part of this repository's development workflow. Older documents requiring
  OpenCode/build handoff, `/implement`, role-specific file prohibitions, or Codex-only read-only
  acceptance are superseded by this section. Their product contracts, evidence requirements,
  live admission conditions, and quality gates remain applicable.
- Work in the current worktree and preserve existing uncommitted changes as the baseline. Do not
  reset, clean, discard unrelated files, switch branches, commit, or merge without user authorization.
- Keep planning proportional to the task. Small changes do not require separate task, plan,
  implementation, and review documents. For substantial work, record the scope, decisions,
  verification, and remaining gaps in `.agent/implementation.md` or the relevant durable document.
- Codex may update code, tests, and relevant documentation within the authorized scope. Fix review
  findings and run appropriate verification directly; no external-agent handoff is required.
- If the user explicitly requests read-only review, honor that scope. Otherwise review may include
  verification and repair. Do not launch tests, benchmarks, or live runs unrelated to the task.

## Project Structure

- Production package: `src/code2paper/`
- Agentic research and publication pipeline: `src/code2paper/agentic/`
- LLM clients, response recovery, role configuration, and section Writer: `src/code2paper/llm/`
- Tests: `tests/`; live profiles: `tests/live/profiles/`
- Operational and evaluation entry points: `scripts/`
- Durable design, status, execution, and evidence indexes: `docs/`
- Long-running output and live artifacts: fresh task-specific directories under `/tmp`

Preserve unrelated user changes in the dirty tree. Keep edits within the responsible subsystem and
explain necessary scope deviations in the task record or final response.

## Verification Commands

- Focused tests: `python -m pytest -q <test paths>`
- Full static suite for broad changes or an applicable milestone: `python -m pytest -q`
- Syntax/import check when relevant: `python -m compileall -q src tests`
- Patch hygiene: `git diff --check`

Codex runs verification appropriate to the change. Documentation-only edits normally need link and
patch-hygiene checks, not pytest or live APIs. Do not report progress by test count alone. For
substantial work, record exact commands, exit statuses, behavior summaries, and code state in
`.agent/implementation.md` or the relevant evidence report. Distinguish newly observed results from
historical results and unverified claims; repeat checks only when changes or unresolved concerns
justify it.

## Authorized Local LLM Runtime

The current designated local OpenAI-compatible runtime is:

- Base URL: `http://127.0.0.1:8006/v1`
- Model: `qwen38-27b-nvfp4`
- Context: `131072`
- Profile: `tests/live/profiles/qwen38_vllm_budgeted.example.env`
  (capability profile: `tests/live/profiles/qwen38_vllm_budgeted_capabilities.json`)

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
