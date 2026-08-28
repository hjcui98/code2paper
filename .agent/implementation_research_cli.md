# Agent 3 — Research Product Runner / CLI Surface: implementation record

- Date: 2026-08-11
- Assignment: `.agent/merged_agent_assignments_20260811.md` Agent 3 (merged
  packages B — Research 主流程 + H — 产品 CLI)
- Execution owner: OpenCode default build
- Delivery record: this file (per merged-assignment §3.8, `.agent/implementation.md` is not used)

## 1. Scope executed

Merged packages B + H:

1. B — a clear product runner that starts the research loop directly from
   repo + author intent + claims and produces evidence packets / code facts /
   atomic claims / completeness / research trace / typed gaps, then hands the
   frozen artifacts to the shared Architect/Writer surfaces.
2. H — the product CLI `code2paper method-agent run` with a reader-facing
   summary (candidate/verified/review/callback/gap) and the fixed artifact
   set, without the D5 matrix or legacy bridge.

The product path deliberately does NOT use: `V3GraphWrapper` /
`build_code2paper_v3_graph` (R8 legacy bridge), synthetic terminal gaps,
the D5 matrix runner, or execution-profile routing.

## 2. Changed files

Production (new):

- `src/code2paper/agentic/autonomous_method_agent.py` (NEW) — product runner.

Production (modified):

- `src/code2paper/cli/agentic_run.py` — `method_agent_main` CLI
  (`method-agent run` subcommand), `_apply_llm_profile` / `_restore_env`
  (bash-style profile loader with env restore), summary printer.
- `src/code2paper/cli/main.py` — thin `method-agent` subcommand dispatch
  (43 added lines only; pre-existing CRLF line endings preserved).

Tests (new):

- `tests/test_agentic_autonomous_method_agent.py` — runner unit tests.
- `tests/test_agentic_method_agent_cli.py` — CLI arg validation + product
  run tests via `method_agent_main`.
- `tests/test_agentic_autonomous_method_agent_cli.py` — unified-CLI e2e.

Note: the pre-existing `tests/test_agentic_run_cli.py` (legacy `agentic-run`
CLI tests) was left untouched — the new method-agent CLI tests live in new
files.

Not touched (per assignment): `publication_method_writer.py`,
`method_architect.py`, `llm/section_writer.py`, `llm/response_schemas.py`,
`runner.py` (the legacy agentic runner stays untouched; the product runner
lives in the new module), `.agent-team/`.

## 3. Product runner (`autonomous_method_agent.py`)

Entry point:

```python
def run_autonomous_method_agent(
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    out_root: str | Path,
    llm_config: LLMConfig | None = None,
    max_research_turns: int = 30,
    method_name: str = "",
    run_id: str = "",
    write_method_text: bool | None = None,
) -> MethodAgentRunResultV1
```

Flow:

1. `load_user_claims` — parses the `--claims` JSON file
   (`{claims: [{claim_id, text, priority, role, lane, notes}]}`). Missing
   file / invalid JSON / duplicate ids / empty text fail typed.
2. `build_product_research_runtime` — builds `RepoSnapshot`, compiles the
   `IntentObligationGraphV2` from the author intent summary, appends
   claim obligations through the deterministic intent-compiler concept
   matching (`append_claims_to_intent_graph`), builds the `ResearchAgendaV1`
   via `build_research_agenda_from_intent_graph`, and returns a
   `ResearchGraphRuntime` with `GemmaSupervisorBackend` (deterministic
   fallback when the LLM is unavailable) and an explicit `artifact_root`.
   No execution profile / D6 routing is applied on the product path.
3. `run_product_research_phase` — runs the research subgraph
   (`build_research_subgraph` from `research_graph.py`) to termination.
   This is the direct product path: repo + intent + claims start the
   research loop with no legacy bridge.
4. `merge_product_evidence` — aggregates the loop's per-obligation compiled
   evidence via `merge_compiled_evidence` (a pure aggregation adapter) and
   binds claims to typed obligations (`bind_claims_to_obligations`). No
   synthetic gaps are added anywhere.
5. `build_typed_gaps` — real typed gaps from the loop's terminal state:
   `explicit_gap` items carry the gap finalizer's accepted
   `GapRequirementV1` provenance (attempted tools, frozen search scope,
   rationale); items still open when the loop stopped are typed
   `unresolved` with the stopping reason. Nothing is fabricated.
6. `build_product_planning` — `build_obligation_coverage_v2` fed with the
   REAL terminal-gap artifacts loaded from the research data plane
   (`_load_terminal_gap_artifacts`, exact `{gap_id: [obligation_id]}`
   bindings), then `build_completeness_matrix`, equations, configurations,
   author story spine, and `build_method_section_plan_with_product_readiness`
   (Agent 1's P0/D contract). Review candidates come from
   `build_review_candidates_from_completeness`.
7. Writer surface — `_run_writer_surface` calls
   `run_publication_method_writer` with the frozen artifact paths when a
   live LLM is available (`has_provider_api_key`) and `write_method_text`
   is not False; otherwise the run stays fully deterministic with a typed
   `skipped_no_live_llm` / `no_live_llm` writer status. The Writer surface
   owns the candidate/verified/review output semantics (Agent 2's package);
   this runner only feeds it and reports its status. Writer faults are
   recorded typed, never crash the run.
8. `persist_product_artifacts` — writes the fixed artifact set.

Artifacts under `out_root/artifacts/research_product/`:
`evidence_packets.json`, `code_facts.json`, `atomic_claims.json`,
`completeness_matrix.json`, `research_trace.json`, `typed_gaps.json`,
`agent_trace.json`, `run_summary.json`, `review_candidates.json`,
`story_spine.json`.

Writer-facing keys under `out_root/artifacts/`: `evidence_packets_v3.json`,
`code_facts_v1.json`, `atomic_claims_v3.json`, `equation_claims_v1.json`,
`configuration_claims_v1.json`, `method_completeness_matrix_v1.json`,
`method_section_plan_v2.json`, `reference_method_agenda_v1.json`,
`obligation_coverage_v2.json`, `intent_obligation_graph_v2.json`,
`research_agenda_v1.json`, `user_claims_input_v1.json`.

`run_summary.json` carries the product counts: research status/reason/turns,
evidence (packets/facts/verified facts/claims/supported claims/typed gaps/
explicit gaps/unresolved obligations, `synthetic_support_used: false`),
plan readiness + blocked-for-safety reasons + review-candidate count,
writer status, callback counts (fulfilled / external queues / pending,
read from the Writer's callback bundle when present), review items,
`verified_validation` (from the Writer quality report when the Writer ran).

## 4. CLI

```text
code2paper method-agent run \
  --repo <repo> \
  --author-intent <file> \
  --claims <file> \
  --out <dir> \
  [--max-research-turns N] \
  [--llm-profile <file>] \
  [--no-live-llm] \
  [--llm-provider P] [--llm-model M] \
  [--method-name NAME] [--run-id ID]
```

- Implemented in `src/code2paper/cli/agentic_run.py:method_agent_main`
  (subcommand parser `run`), dispatched from the unified
  `src/code2paper/cli/main.py` as `code2paper method-agent run`.
- `--llm-profile` applies a bash-style `KEY=VALUE` profile; lines with `$`
  (shell expansion) are skipped; the environment is restored after the run
  (`_restore_env`), so a profile never leaks into later processes.
- `--no-live-llm` forces `LLMProvider.NONE` (deterministic supervisor, no
  Writer call).
- Exit codes: 0 = product run completed (research + planning artifacts
  persisted; writer may be `skipped_no_live_llm` or blocked — that is the
  product state, review/callback items are outputs, not failures); 2 =
  input/usage errors.
- Summary prints: run_id, candidate written, verified written, verified
  facts, supported claims, review items, callbacks fulfilled, external
  queues, gaps (explicit/unresolved), unsafe blocked claims, plan
  readiness, research status/reason/turns, writer blocked reason,
  summary path. Also writes `method_agent_result.json` next to `--out`.

## 5. Shared contract consumption (Agent 1's P0)

No parallel lane/readiness/review schema was invented. The runner imports
from `method_product_models`: `MethodEvidenceLane`, `MethodPlanReadiness`,
`MethodReviewCandidateV1`, `AuthorStoryNodeV1`, `StoryNodeRoleV1`,
`build_review_candidates_from_completeness`,
`build_default_method_output_policy`, and consumes
`MethodPlanProductReadinessV1` from `build_method_section_plan_with_product_readiness`.
The user-claims input model (`UserClaimInputV1`) uses the shared
`MethodEvidenceLane` / `StoryNodeRoleV1` types for its `lane` / `role`
fields.

## 6. Verification

Focused (new + touched subsystems):

```text
python -m pytest -q tests/test_agentic_autonomous_method_agent.py \
  tests/test_agentic_method_agent_cli.py \
  tests/test_agentic_autonomous_method_agent_cli.py
# 32 passed, exit 0
```

Consumers / adjacent subsystems:

```text
python -m pytest -q tests/test_agentic_runner.py tests/test_agentic_v3_e2e.py \
  tests/test_agentic_benchmark_cli.py tests/test_agentic_compile_candidate_node.py \
  tests/test_agentic_research_checkpoint_resume.py tests/test_agentic_v3_evidence_chain.py \
  tests/test_agentic_method_architect_product_readiness.py tests/test_agentic_method_product_models.py \
  tests/test_agentic_authoring_projection.py
# all pass
```

Full static suite (broad regression):

```text
python -m pytest -q --ignore=tests/live
# 2389 passed, 3 skipped, 2 warnings, 12 subtests passed, exit 0
```

Syntax/import and patch hygiene:

```text
python -m compileall -q src tests      # exit 0
git diff --check                        # exit 0
```

Note on suite hygiene: the first full-suite run surfaced a test-pollution
defect in this package's own CLI (`_apply_llm_profile` leaked
`CODE2PAPER_LLM_PROVIDER`/`CODE2PAPER_LLM_MODEL` into the process env,
breaking later tests such as `test_run_cli`). Fixed by restoring the
changed env keys after the run; the full suite is green with the fix.

## 7. Product behavior summary

- One command (`code2paper method-agent run --repo ... --author-intent ...
  --claims ... --out ...`) runs the full local product path on a small
  fixture: autonomous research (search/read/trace/config tools via the
  research loop), evidence/facts/claims compilation, completeness matrix,
  typed gaps with stopping reasons, author-intent-first plan with product
  readiness, and (with a live LLM) the Writer surface outputs.
- No synthetic support: `synthetic_support_used=false` is recorded in the
  run summary, and typed gaps come only from the loop's real terminal state
  (gap finalizer's `GapRequirementV1` records + the persisted terminal-gap
  artifacts), never from `_synthesize_terminal_gaps`.
- An unverifiable user claim produces a real `explicit_gap`, an
  `explicit_code_gap` completeness row, and review candidates with non-empty
  `proposed_body` + `confirmation_question` (`blocks_verified=True`,
  `blocks_candidate=False`).
- The no-live-LLM path stays deterministic and still produces the full
  research/planning artifact set with a typed `writer_blocked_reason`.

## 8. Known limitations (in-direction, owned by later packages)

- The Writer surface still writes identical candidate/verified text today
  and review `proposed_body` is still empty there — that is Agent 2's
  package (A), unchanged by design. This runner reports the Writer's status
  and persists the product artifacts; the three-way output split must come
  from Agent 2's `publication_method_writer` rework.
- `plan readiness` is unit-granular (Agent 1's documented contract): an
  unverified obligation that binds no plan unit does not change the plan's
  readiness state; the run summary still surfaces it via review items and
  gaps.
- `run_autonomous_method_agent` does not yet re-run research for a
  Writer-issued repository/config/formalization callback (full
  callback/resume loop is Agent 2's F package); the Writer's callback
  bundle is preserved and counted, and the research loop can already be
  re-invoked on the same runtime for future resume wiring.

## 9. Interfaces left for integration

- Agent 2: consume `MethodAgentRunResultV1.artifact_paths` / the
  `research_product` JSONs when wiring the candidate/verified/review split
  and callback artifacts; the writer-facing artifact keys under
  `out_root/artifacts/` are the frozen input keys.
- Codex acceptance: the diff is limited to the new runner module, the CLI
  additions in `cli/agentic_run.py`, the 43-line `cli/main.py` dispatch, and
  three new test files; no governing doc, shared contract, Writer/
  Architect/schema file, or pre-existing test file was modified.
