# Agent 1 — Foundation / Planning Surface: implementation record

- Date: 2026-08-11
- Assignment: `.agent/merged_agent_assignments_20260811.md` Agent 1 (P0 shared product contracts + C
  author intent projection + D Method Architect graded gate)
- Execution owner: OpenCode default build
- Delivery record: this file (per merged-assignment §3.8, `.agent/implementation.md` is not used)

## 1. Scope executed

Merged packages P0 + C + D:

1. P0 — shared product contract layer (lanes / review items / output policy / draft bundle / plan
   readiness / story spine node).
2. C — author-intent-first projection: story spine, lane-aware writer payload, replaced hardcoded
   code-order goal, projection trace, review-question generation.
3. D — Method Architect as argument organizer: story-spine-driven section order, graded
   candidate/verified readiness, exact placement / move proof / semantic frame demoted to audit
   metadata.

## 2. Changed files

Production:

- `src/code2paper/agentic/method_product_models.py` (NEW) — P0 contract module.
- `src/code2paper/agentic/trust_contracts.py` — `AuthoringInputProjection` extended with lane-aware
  fields (backward compatible, all new fields default to empty).
- `src/code2paper/agentic/intent_compiler_v2.py` — `build_story_spine_from_intent_graph` +
  `_story_role_for_kind`.
- `src/code2paper/agentic/authoring_projection.py` — author-intent-first projection (story spine,
  lane-partitioned facts, unverified/external/formalization points, review questions, writing
  policy, projection trace, `_author_goal` with recorded repository-order fallback).
- `src/code2paper/agentic/intent_obligations.py` — `build_review_candidates_from_coverage`.
- `src/code2paper/agentic/method_architect.py` — `story_spine` parameter on
  `MethodArchitect.build` / `build_method_section_plan` / `build_method_section_plan_with_trace`,
  `_story_spine_obligation_order` / `_group_organization_key` / `_story_spine_usage_trace`, new
  entry `build_method_section_plan_with_product_readiness`.

Tests:

- `tests/test_agentic_method_product_models.py` (NEW).
- `tests/test_agentic_method_architect_product_readiness.py` (NEW).
- `tests/test_agentic_authoring_projection.py` (extended, 5 new tests).
- `tests/test_agentic_intent_compiler_v2.py` (extended, 3 new tests).

Not touched (per assignment): `publication_method_writer.py`, `llm/section_writer.py`,
`llm/response_schemas.py`, `research_graph.py`, `cli/agentic_run.py`, `method_argument_models.py`
(no changes needed — new contracts live in the sidecar module), `.agent-team/`.

## 3. What the shared contracts now define (P0)

`method_product_models.py`:

- `MethodEvidenceLane` (9 lanes): `repository_verified`, `repository_partial`, `repository_mismatch`,
  `author_intent_unverified`, `author_confirmed`, `literature_pending`, `empirical_pending`,
  `formalization_pending`, `out_of_scope`.
- `MethodPlanReadiness` (4 states): `verified_ready`, `candidate_ready`,
  `candidate_ready_with_review`, `blocked_for_safety`.
- `MethodReviewCandidateV1` — non-empty `proposed_body` enforced by validation;
  `blocks_verified` and `blocks_candidate` are independent booleans
  (default `blocks_verified=True`, `blocks_candidate=False`).
- `MethodOutputPolicyV1` + `build_default_method_output_policy()` — `verified_positive_lanes`,
  `candidate_allowed_lanes`, `review_required_lanes`,
  `unsupported_positive_blocks_verified=True`, `unresolved_blocks_candidate=False`.
- `MethodDraftBundleV1` — candidate/verified markdown + review items + plan readiness + blocked
  reasons; `blocked_for_safety` bundles require blocked reasons; `verified_ready` bundles require
  non-empty verified markdown.
- `AuthorStoryNodeV1` — story spine node (role, statement, source refs, linked obligations/claims,
  evidence lane, default `author_intent_unverified`).
- `MethodSectionReadinessV1`, `MethodUnitProductStatusV1`, `MethodPlanProductReadinessV1` — the
  per-plan readiness sidecar with `review_candidates` and `audit_warnings`.
- Functions: `method_lane_from_reference_status`, `method_lane_from_authority_lane`,
  `assess_plan_product_readiness`, `build_review_candidates_from_completeness`.

Lane authority defaults implemented: repository_verified is the only verified-positive lane by
default (partial only with a qualifying row), author_intent_unverified / external / formalization /
mismatch are review-required but candidate-permitted; only an unsupported positive without a caveat
route raises `blocked_for_safety`.

## 4. What changed in the projection (C)

- Hardcoded V3 `author_goal` ("Explain the compiled inference mainline in code order ...") replaced
  by `_author_goal()`: author goal from intent graph / method evidence first; repository-behavior
  order is now only a *recorded* fallback when no author intent exists (trace row
  `fallback_repository_behavior_order`).
- `AuthoringInputProjection` now carries: `author_story_spine`, `repository_verified_facts`,
  `repository_partial_facts`, `repository_mismatches`, `author_intent_unverified_points`,
  `external_pending_points`, `formalization_needed_points`, `review_questions`, `writing_policy`,
  `projection_trace`. All default to empty, so persisted legacy projections still load.
- Story spine built from the typed intent graph (`build_story_spine_from_intent_graph`), refined by
  exact completeness rows and projected claims (`_refined_story_spine`): supported + projected
  claims -> `repository_verified`, partial -> `repository_partial`, mismatch / external /
  formalization rows -> their own lanes; author-only nodes stay `author_intent_unverified`.
- Unverified author points (rationale/innovation/mismatch/organization obligations, unverified or
  author-confirmation-required matrix rows) survive into `author_intent_unverified_points` plus one
  `review_questions` entry each — they never disappear and never become repository facts.
- `projection_writer_payload` / `projection_writer_brief` expose the lane-aware surface; both stay
  `json.dumps`-safe (spine nodes serialized to dicts).
- `restrict_projection_for_authoring_revision` keeps lane lists and spine consistent when claims are
  excluded.

`intent_obligations.py` additionally exposes `build_review_candidates_from_coverage` so the
obligation-coverage report can be converted into actionable author review items (editable proposed
body + exact question), verified-blocking only.

## 5. What changed in the Architect (D)

- Section organization is now story-spine-first: when a spine is supplied, stage groups whose
  obligations appear in the spine are ordered by spine position (`_group_organization_key`);
  unbound groups follow in compiler priority order. Trace records `story_spine.used`, per-node
  `realized_sections` (unrealized nodes are reported, never dropped), and per-section story
  linkage. Same evidence + different author intent => different section order (tested).
- New entry `build_method_section_plan_with_product_readiness` returns
  `(plan, MethodPlanProductReadinessV1, trace)`.
- `assess_plan_product_readiness` implements the four-state gate:
  - ordinary unresolved/external/mismatch rows -> `candidate_ready_with_review` (review items,
    verified excluded);
  - supported rows fully bound -> `verified_ready`;
  - no review items but no verified basis -> `candidate_ready`;
  - positive wording with no supporting row and no `limitations_or_mismatch` caveat route ->
    `blocked_for_safety` (the only candidate blocker).
- Exact placement / move authority / semantic-frame closure are now audit-only:
  `_plan_audit_warnings` records open move-authority proofs, unresolved semantic relations, and
  unplaced assignments as `audit_warnings` that never change the candidate/verified state (tested
  by attaching an `open` proof and an unplaced assignment to an otherwise clean plan: still
  `verified_ready`, warnings present).

## 6. Verification

Focused (new + touched subsystems):

```text
python -m pytest -q tests/test_agentic_method_product_models.py \
  tests/test_agentic_method_architect_product_readiness.py \
  tests/test_agentic_authoring_projection.py tests/test_agentic_intent_compiler_v2.py \
  tests/test_agentic_intent_obligations.py tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_final_text_trust.py tests/test_agentic_writing_route_execution.py \
  tests/test_llm_publication_schema_closed_sets.py tests/test_agentic_v3_runtime.py
# 252 passed, 6 subtests passed, exit 0
```

Consumers of the projection / architect / trust contracts:

```text
python -m pytest -q tests/test_agentic_text_trust_graph.py tests/test_agentic_v3_e2e.py \
  tests/test_agentic_runner.py tests/test_agentic_v3_evidence_chain.py \
  tests/test_agentic_final_text_trust_v3.py tests/test_agentic_author_intent_summary.py \
  tests/test_agentic_r8_acceptance.py tests/test_agentic_research_checkpoint_resume.py
# 305 passed, 6 subtests passed, exit 0
```

Full static suite (broad regression):

```text
python -m pytest -q -x --ignore=tests/live
# 2359 passed, 3 skipped, 12 subtests passed, exit 0
```

Syntax/import and patch hygiene:

```text
python -m compileall -q src tests          # exit 0
git diff --check                            # exit 0
```

## 7. Product behavior summary

- Candidate/verified/review semantics now have a single shared contract (lanes, readiness,
  review items) that Agents 2/3 must consume instead of inventing their own.
- Author intent now drives section organization (story spine), and the projection no longer
  reduces the writer's view to code-supported claims: unverified author points, mismatches,
  external-pending and formalization points survive into the candidate/review surface.
- Exact placement / move proof / semantic-frame closure no longer block candidates: they are
  audit warnings on the readiness report.
- Unsupported positives still fail closed: a positive claim with no supporting completeness row
  and no caveat route produces `blocked_for_safety` (verified AND candidate blocked). Ordinary
  missing evidence produces review items (verified blocked, candidate written).

## 8. Interfaces left for Agents 2 / 3

- Agent 2 (Writer/Output/Validation): consume `MethodPlanProductReadinessV1` + `MethodDraftBundleV1`
  + `build_review_candidates_from_completeness` when splitting candidate/verified/review outputs and
  filling `author_review_candidates.json`; consume the lane-aware `projection_writer_payload`
  fields. `MethodSectionPlanV2` is unchanged (readiness is a sidecar), so the existing writer
  wiring keeps working.
- Agent 3 (Research/CLI): the product runner should pass `intent_obligation_graph_v2` and
  `completeness` into `build_authoring_projection` and `story_spine` into
  `build_method_section_plan_with_product_readiness` to enable the author-intent-first path.

## 9. Known limitations (in-direction, owned by later packages)

- `build_review_candidates_from_completeness` proposed body is a careful rephrase of the obligation
  statement or a truthful template; Writer-generated unresolved-span text as a better `proposed_body`
  source belongs to Agent 2's output splitter (A3 priority order).
- Sentence-level lane splitting (which sentences of a unit enter verified) is the validator's job
  (G); the readiness report is unit-granular and intentionally conservative.
- `assess_plan_product_readiness` treats a missing completeness matrix as "no verified basis"
  (audit warning, candidate still usable), matching "missing evidence is not failure by itself".
- `replan_moves_with_trace` (Writer-side architect upgrade) does not yet emit
  `MethodPlanProductReadinessV1`; Agent 2 can call `assess_plan_product_readiness` on the replanned
  plan directly.

## 10. Real API live runs (2026-08-11, serial, qwen36-27b-nvfp4 @ 127.0.0.1:8003/v1)

Runtime pre/post health: `/health` 200, `/v1/models` 200 (model `qwen36-27b-nvfp4`, root
`/data1/users/cuihengjia/qwen3.6/models/Qwen3.6-27B-NVFP4`).  Queue empty at start and end; no
competing runs submitted.  All four runs used
`tests/live/profiles/qwen36_vllm_budgeted.example.env`, `--max-research-turns 30`.

| Project | run dir | candidate (B) | verified (B) | verified facts | supported claims | review items | gaps | readiness |
|---|---|---|---|---|---|---|---|---|
| RAP | `/tmp/code2paper-method-agent-live-rap-20260811` | 2100 | **0** | 45 | 7 | 12 | 22 (2 explicit) | candidate_ready_with_review |
| EBCAR | `/tmp/code2paper-method-agent-live-ebcar-20260811` | 808 | **0** | 30 | 5 | 15 | 29 (4 explicit) | candidate_ready_with_review |
| LinearRAG | `/tmp/code2paper-method-agent-live-linearrag-20260811` | 1928 | **0** | 91 | 11 | 12 | 20 (2 explicit) | candidate_ready_with_review |
| DyG-Mamba | `/tmp/code2paper-method-agent-live-dygmamba-20260811` | 4863 | **0** | 69 | 18 | 5 | 19 (2 explicit) | candidate_ready_with_review |

Command per project (order: RAP -> EBCAR -> LinearRAG -> DyG-Mamba), e.g. RAP:

```bash
python -m code2paper.cli.main method-agent run \
  --repo "<repo>" --author-intent "<yaml>" \
  --out /tmp/code2paper-method-agent-live-rap-20260811 \
  --llm-profile tests/live/profiles/qwen36_vllm_budgeted.example.env \
  --max-research-turns 30 --run-id rap-live-20260811
```

### 10.1 What worked (product loop restored)

- Autonomous research loop: 30 turns each, real tool calls (search_symbols / read_symbol /
  find_references / build_behavior_subgraph), typed gaps with stopping reasons
  (`Accepted after 3 consecutive no-gain turns`), 153-entry node traces, 30-entry decision traces
  with per-turn goals (research_trace.json), 0 synthetic support.
- Candidate written in all 4 runs, covering the supported stage content.
- `author_review_candidates.json`: 12/15/12/5 items, all with non-empty `proposed_body` +
  `confirmation_question` + `needed_evidence` + `suggested_action`, `blocks_candidate=False`
  everywhere; gap/author-confirmation lanes mapped correctly (`explicit_code_gap`,
  `author_confirmation_required` -> `author_intent_unverified`); mainline-gap items section-bound
  to the unit.
- Plan readiness `candidate_ready_with_review` everywhere; `unsafe blocked claims: 0`;
  `callbacks fulfilled: 0` (no writer callback was generated, see 10.3).
- Writer prose config observed live: `temperature=0.7, top_p=0.95, seed=42` (Agent 2 role
  config live).

### 10.2 Systemic finding: repository_verified_method.md is empty in all 4 runs

Despite 30-91 verified facts and 5-18 supported claims per run, the verified document is 0 bytes.
Root-cause chain (evidence verified on the RAP and EBCAR artifacts):

1. The product runner never writes a frozen `MethodEvidence` artifact (`method_evidence` /
   `evidence` key), so `publication_method_writer._maybe_validate_final_text` returns
   `pending` and the sentence-level reverse validation
   (`build_repository_verified_text`, G-package) never runs in the product path.
2. The fallback splits at unit granularity from `plan_product_readiness_v1` (this package's
   contract).  In every run the single (or each) unit binds its `O-METHOD-MAINLINE-*` row, which
   the research loop marked `explicit_code_gap` while the claim compiler attached the same
   supported claims to it (`covers_obligation_ids` includes the mainline).  Worst-lane wins ->
   unit lane `author_intent_unverified`, `can_enter_verified=False` -> no verified section.
3. The writer also reports `incomplete` (`missing_writing_research_callback:limitations_or_mismatch`
   and `invalid_writing_research_callback`), so the final-integrity gate stays closed even though
   the section text is accepted.

This is fail-closed (no unsupported positive entered verified; 0 unsafe claims) but under-covers:
the supported stage facts never reach the verified document.

### 10.3 Repair paths (cross-agent; outside this Agent's file ownership)

- Agent 3 (`autonomous_method_agent.py`): write the `method_evidence` artifact from the
  projection via `authoring_projection.projected_writer_inputs(projection, template=...)` (helper
  already exists).  `_maybe_validate_final_text` then runs and the sentence-level verified split
  fills `repository_verified_method.md` with supported sentences only.
- Agent 2 (`publication_method_writer.py`): generate the `limitations_or_mismatch` callback
  request (or accept the already-generated review items as the caveat evidence) so
  gap-bound sections can complete; keep reverse validation available for
  incomplete-but-candidate runs.
- Agent 1 (this package, optional): the unit-granular fallback stays conservative by design
  (mixed supported+gap units are excluded); it is the last-resort path once the sentence-level
  validator runs.
- Integration note: `research_product/story_spine.json` is the unrefined spine
  (all `author_intent_unverified`); the evidence-refined spine lives in
  `build_authoring_projection(...).author_story_spine` — Agent 3 should persist that one.

### 10.4 Run monitoring

- RAP: 28 min, 202 research artifacts, 12 review items.
- EBCAR: 34 min, 186 artifacts, 15 review items.
- LinearRAG: 30 min, 204 artifacts, 12 review items.
- DyG-Mamba: 36 min, 213 artifacts, 5 review items.
- No competing requests submitted; vLLM queue stayed at 0 waiting; runtime healthy after all runs.

## 11. Codex direct repair for 0-byte verified outputs

Date: 2026-08-11.  Scope: direct fix after the four real project runs showed
non-empty candidates but empty `repository_verified_method.md`.

Implemented:

- `autonomous_method_agent.py` now builds the V3 authoring projection in the
  product planning path, converts it to writer-compatible `MethodEvidence` and
  `ClaimEvidenceMap` via `projected_writer_inputs`, persists
  `artifacts/method_evidence.json`, `artifacts/claim_evidence_map.json`, and
  `artifacts/authoring_projection_v1.json`, and passes those paths into the
  publication Writer.  This connects the existing sentence-level reverse
  validation path instead of falling back to unit-granular readiness.
- The persisted `research_product/story_spine.json` now uses the
  evidence-refined projection spine when available, so the runner-side story
  record matches the projection seen by downstream writing/validation.
- `authoring_projection.projected_writer_inputs` now converts V3 equation
  claim payloads into legacy writer-compatible `EquationCandidate` objects
  (`EQ-V3-*`, `name`, `latex`, compatible evidence ids) instead of passing the
  V3 schema through directly.
- `publication_method_writer.py` now gives the Writer complete callback
  request prototypes, including `candidate_symbols_or_terms`, for unanchored
  required moves.  A bounded Writer-owner retry is triggered when a section
  omits a required callback; retry success replaces that section output, while
  retry failure preserves the first candidate prose and leaves the section
  incomplete.  The harness still does not synthesize callback requests.

Verification:

- `python -m pytest -q tests/test_agentic_autonomous_method_agent.py tests/test_agentic_publication_method_writer.py`
  -> exit 0, `88 passed, 2 warnings`.
- `python -m pytest -q tests/test_agentic_candidate_verified_split.py tests/test_agentic_callback_resume_product.py tests/test_agentic_method_product_models.py tests/test_llm_section_writer.py`
  -> exit 0, `84 passed`.
- `python -m compileall -q src tests` -> exit 0.
- `git diff --check` -> exit 0.
- `python -m pytest -q` -> exit 0, `2408 passed, 3 skipped, 2 warnings, 12 subtests passed`.
- Small live smoke attempted on
  `/tmp/code2paper-codex-repair-smoke-20260811-live` with the qwen36 profile.
  The sandboxed attempt was network-blocked (`Operation not permitted`); the
  escalated attempt was manually interrupted after the run remained in
  `research_supervisor_node -> LLMClient._post_openai_stream_until_complete_json`
  waiting for streamed model output and had not reached product artifact
  writing.  This is not counted as acceptance evidence for the Writer split.

Next recommended real check:

- Re-run one project first (RAP is sufficient as smoke) into a fresh `/tmp`
  directory.  Expected product delta: `repository_verified_method.md` should no
  longer be blocked by `final_text_validation_status=pending`; if the Writer's
  wording fails reverse validation, the quality report should now contain
  sentence-level validation failures instead of an empty verified file caused
  by missing `MethodEvidence`.

## 11. RAP re-run after method_evidence integration fix (2026-08-11)

### 11.1 Fix applied (in-direction repair, this Agent)

The runner (updated after the first four runs) now writes `artifacts/method_evidence.json`, but the
persisted dump carried `paper_module_aliases` while the Writer's reverse gate loads the legacy
compatibility model `code2paper.schemas.MethodEvidence` (a stale copy of
`core.schemas.MethodEvidence` lacking that field).  `_maybe_validate_final_text` swallowed the
ValidationError as `failed` -> the silent 0B fallback would have persisted.

Repair (verified by round-trip before the live run): aligned the legacy class in
`src/code2paper/schemas.py` — added `PaperModuleAlias` and `paper_module_aliases` to its
`MethodEvidence`, matching `core.schemas`.  No other file changed for this fix; the Writer and the
product runner were not modified.

Verification before the run:
- `python -m pytest -q` on writer/projection/product-model/phase4 suites: 142 passed, exit 0.
- `python -m compileall -q src tests`, `git diff --check`: exit 0.
- Offline round-trip: runner-equivalent `projected_writer_inputs` dump -> legacy
  `MethodEvidence.model_validate_json` -> OK; writer-side `build_authoring_projection` rebuilds
  7 claims.

### 11.2 Re-run result (fresh `/tmp/code2paper-method-agent-live-rap-rerun-20260811`)

| Item | First run | Re-run |
|---|---|---|
| `final_text_validation_status` | `pending` | **`passed`** |
| sentence-level validation artifacts | absent | `agentic_final_text_claims.json` + `agentic_text_evidence_validation.json` written |
| hard gate | `false` | `true` (support_precision 1.0, unsupported=0) |
| `repository_verified_method.md` | 0 B | 636 B (sentence-filtered) |
| candidate | 2100 B | 636 B |
| verdicts | n/a | 4 factual claims, 4 supported / 0 caveated / 0 unsupported / 0 unverified |
| verified == candidate | - | identical — **correct**: every extracted sentence was supported |

The user-expected change is confirmed: `final_text_validation_status` is no longer `pending` due to a
missing `MethodEvidence`; the sentence-level reverse validation now runs in the product path, and a
sentence failure would surface as per-sentence verdicts in `agentic_text_evidence_validation.json`
(and empty/filtered verified content) instead of the silent 0B fallback.

### 11.3 Remaining notes for integration

- The runner summary's `verified_validation.status` reads
  `artifacts/06_authoring/publication_quality_report_v1.json` while the Writer writes it under
  `artifacts/07_validation/` -> summary shows `not_run` although validation ran (`passed`).  Path
  alignment belongs to Agent 3 (`_verified_validation_state`).
- Writer status stays `incomplete` (`missing_writing_research_callback:limitations_or_mismatch`,
  E4/F package) and plan readiness `candidate_ready_with_review`; candidate + review items remain
  the full product surface, and the verified document now carries the supported sentences.
- vLLM runtime healthy before/after the run (qwen36-27b-nvfp4); no competing requests.

## 12. Codex follow-up: summary/projection wiring and RAP quality read (2026-08-11)

Small fixes:

- `_verified_validation_state` in `autonomous_method_agent.py` now reads the real final validation
  artifact, `artifacts/07_validation/agentic_text_evidence_validation.json`, before falling back to
  the quality report.  The next run should report `verified_validation.status=passed` for the RAP
  re-run case instead of `not_run`.
- `_maybe_validate_final_text` in `publication_method_writer.py` now preserves an existing
  product `authoring_projection_v1` when supplied; if it must rebuild the projection, it also passes
  `intent_obligation_graph_v2` and `method_completeness_matrix_v1`.  This prevents the Writer's
  validation-side projection from dropping the author story spine.

Verification:

- `python -m pytest -q tests/test_agentic_autonomous_method_agent.py tests/test_agentic_publication_method_writer.py`
  -> exit 0, `89 passed, 2 warnings`.
- `python -m pytest -q tests/test_agentic_candidate_verified_split.py tests/test_agentic_callback_resume_product.py tests/test_agentic_method_product_models.py tests/test_llm_section_writer.py`
  -> exit 0, `84 passed`.
- `python -m compileall -q src tests` -> exit 0.
- `git diff --check` -> exit 0.
- `python -m pytest -q` -> exit 0, `2409 passed, 3 skipped, 2 warnings, 12 subtests passed`.

RAP artifact read:

- Candidate and verified are both 636 B and identical because all four extracted final-text factual
  units were repository-supported; sentence-level filtering is functioning.
- Current generated content covers only Feature Extraction and Normalization.  It aligns with the
  paper draft's Feature Extraction section but omits the paper's Overview, Score Prediction MLP,
  Training losses, and Feedforward Inference sections.
- The Writer did emit one open `limitations_or_mismatch` callback request routed to
  `repository_tools`; the incomplete state is due to the missing fulfillment/resume loop, not a
  missing request object.
- The plan contains one placed section/unit; the completeness matrix has one fully supported row,
  two explicit code gaps, two author-confirmation rows, and many partial rows that are not yet
  placed as writeable sections.  Product core is running; method-quality growth now depends on
  placing partial/supportable story nodes and executing callback fulfillment/resume.

## 12. F+P+W repair round (2026-08-11, per `.agent/next_repair_strategy_callback_plan_writer_20260811.md`)

Implemented the three repair packages from the strategy document.  All changes verified by the full
static suite (2425 passed, 3 skipped, exit 0) and by two RAP live canaries.

### 12.1 Package P — partial/supportable candidate planning

- `method_argument_models.py`: `MethodCompletenessItemV1` gains backward-compatible
  `matched_fact_ids` / `matched_relation_ids` / `matched_span_ids`; `build_completeness_matrix`
  populates them from the V2 coverage report (`_coverage_matched_evidence`).
- `method_architect.py`: `_candidate_buckets_from_story_and_completeness` materializes unrealized
  completeness rows (partial / author-confirmation / explicit-gap / external / formalization /
  mismatch; never out_of_scope) as candidate argument units; `_merge_plan_buckets` orders claim and
  candidate buckets by story-spine position; `_candidate_argument_unit` builds lane-typed,
  caveat-carrying units with exact `source_obligation_ids` and preserved matched-evidence handles.

RAP effect: plan went from 1 section to 22 sections aligned with the author story spine; review
candidates now bind to section/unit ids (4/4 in the rerun artifacts); partial rows produce
candidate sections instead of disappearing into the review sidecar only.

### 12.2 Package F — callback fulfillment/resume loop

New `src/code2paper/agentic/writing_callback_fulfillment.py`:

- `WritingCallbackFulfillmentBudgetV1` (rounds/tool-turns/requests-per-round/artifacts-per-request)
  and `WritingCallbackFulfillmentResultV1` (rounds, seen/fulfilled counts, resumed ids, stopped
  reason, trace path).
- `fulfill_and_resume_writing_callbacks(...)`: reads the persisted bundle, executes open local-owned
  routes (repository/config/formalization) via `execute_open_requests_for_routes`, fulfills with
  `fulfill_writing_research_callbacks`, re-invokes `run_publication_method_writer` with
  `resume_section_ids` + `research_callback_artifacts`, and loops under budget with progress-driven
  stops (`no_open_requests`, `no_progress`, `writer_success`, `budget_exhausted`).
- `_BudgetedRepositoryCallbackProvider`: deterministic budgeted tool loop (search -> file read ->
  ref-driven `read_code_span`/`read_symbol`/`find_references`), dedup by
  `(tool, args, path_scope)`, no-new-observation stop, and span **range-overlap** matching against
  the frozen fact set; writes digest-pinned file-backed artifacts under
  `artifacts/research_tool_data/writing_callbacks/<request_id>/` with `summary_for_writer`.
- `autonomous_method_agent.run_autonomous_method_agent`: new `max_callback_rounds` /
  `max_callback_tool_turns_per_request` args; runs the fulfillment loop after the first Writer
  (only for `incomplete`/`success`); records phase `writer_callback_fulfillment` and callback
  summary fields (`local_requests_seen`, `callbacks_fulfilled`, `callbacks_pending`,
  `external_queue_items`, `rounds_attempted`, `resumed_section_ids`, `stopped_reason`).
- Honest reporting: summary now distinguishes `unsupported_positive_claims_in_candidate` (the
  reverse-validator count over the candidate) from `unsupported_positive_claims_in_verified`
  (0 after the fail-closed sentence split by construction); CLI prints both.

### 12.3 Package W — reader-facing Writer surface + paper-language quality

- `method_product_models.py`: `ReaderFacingClaimV1` + `extract_code_binding_terms`.
- `publication_method_writer._writer_section_inputs`: per-section `reader_facing_claims`,
  `section_candidate_points`, and `paper_term_hints` in the Writer payload; `content_first_instruction`
  rewritten to the hierarchy (reader-facing claims = sentence plan; code identifiers = bindings,
  not prose subjects; validation constraints check meaning, not wording).
- `writer_skill.py`: version 1.6 -> 1.7, hierarchy rules, generic good/bad style example.
- `publication_quality.py`: `code_trace_prose_not_method_language` style issue (code-identifier
  density / `self.` sentence subjects) emitted without weakening evidence gates.  Rewrite
  triggering on style issues remains a documented follow-up (current rewrite path keys off
  validation failure only).

### 12.4 Live canary evidence (RAP, `/tmp/code2paper-method-agent-live-rap-fpw2-20260811`)

| acceptance item | result |
|---|---|
| first Writer emits real local-owned callback request | yes (`request:MA-S1:limitations_or_mismatch`, executable_hard) |
| bounded repository callback research executed | yes (`rounds_attempted: 2`, tool turns, span-overlap match) |
| callback artifact file-backed + digest-pinned | yes (`writing-callback:request:MA-S1:...json`, digest verified, 3 matched facts) |
| only affected section resumes | yes (`resumed_section_ids: ["MA-S1"]`) |
| candidate has multiple author-aligned sections | yes (22 sections, 34 KB, story-spine order) |
| partial obligations appear as candidate content | yes (score prediction / training / inference / losses...) |
| verified unsupported positives | 0 (`unsupported positives: candidate=267 verified=0`) |
| run_summary reports validation/callbacks/resume | yes (`verified_validation`, `callbacks.*`, `resumed_section_ids`) |

First canary (`rap-fpw`) found two defects fixed before the second: (1) provider budget was starved
by question-derived search seeds so read phases never ran (fixed: capped search seeds, ref-driven
`read_code_span` phase, span range-overlap matching); (2) the runner mislabeled candidate
unsupported sentences as `unsupported_positive_claims_in_verified` (fixed: split candidate/verified
reporting).

### 12.5 Known follow-ups (out of this round's scope)

- Writer emits only one `##` heading for the last section; candidate sections are currently
  paragraph-separated (heading emission per section is a Writer formatting follow-up).
- Style-issue -> Rewrite routing (currently the style guard publishes the issue; the rewrite path
  keys off validation failure).
- The sentence-level validator still classifies candidate-section prose as `unsupported` rather
  than `author_intent_caveated`; verified is unaffected (fail-closed splitter), but the quality
  report status says `failed` while the candidate is the intended full product surface.
- Four-project follow-up (EBCAR / LinearRAG / DyG-Mamba) per strategy document §7.

## 13. Codex integration follow-up (2026-08-12)

Read-only inspection of the FPW2 handoff confirmed the main P/F/W claims:

- RAP FPW2 artifact root: `/tmp/code2paper-method-agent-live-rap-fpw2-20260811`.
- Plan materialization: 22 sections / 22 units; review candidates are section-bound.
- Callback fulfillment: one local executable request fulfilled, file-backed artifact digest verified,
  and `resumed_section_ids=["MA-S1"]`.
- Verified split: `unsupported_positive_claims_in_verified=0`.

Codex found and patched two deterministic integration issues:

1. `writing_callback_fulfillment._load_formalization` loaded `formalization_result_v1` as a raw
   dict, but the router checks `getattr(formalization, "content_digest")`; formalization-lane
   callbacks therefore could not fulfill.  The loader now returns typed `FormalizationResultV1`.
   Added `test_formalization_request_loads_typed_result_and_resumes`.
2. The Writer prompt still instructed `section_markdown` to start with an anchored sentence, which
   directly conflicted with the desired per-section Markdown headings.  The repo-local skill and
   dynamic `content_first_instruction` now require exactly one Writer-authored H2 heading copied
   from the supplied `heading` field before the first anchored Method sentence.

Verification:

- `python -m pytest -q tests/test_agentic_autonomous_callback_fulfillment.py` -> 8 passed.
- `python -m pytest -q tests/test_agentic_publication_method_writer.py tests/test_llm_section_writer.py tests/test_agentic_autonomous_callback_fulfillment.py` -> 134 passed, 2 pydantic serialization warnings.
- `python -m compileall -q src tests` -> exit 0.
- `git diff --check -- src/code2paper/agentic/writing_callback_fulfillment.py tests/test_agentic_autonomous_callback_fulfillment.py src/code2paper/authoring/writer_skill.py src/code2paper/agentic/publication_method_writer.py` -> exit 0.

Codex assessment after the integration patch:

- Package P is implemented to first-canary acceptance.
- Package F is implemented to first-canary acceptance, with the formalization lane loader repaired.
- Package W has the data/prompt/style-guard surface implemented, but prose quality is not yet at
  publication target.  FPW2 candidate is much broader than the prior 636-byte draft, yet its opening
  still centers raw implementation identifiers (`GaussianModel.capture`, `self._features_dc`,
  `range`).  Heading emission should improve after the prompt fix, but needs a fresh live run.
- Remaining high-priority follow-ups: style-issue -> Rewrite routing; candidate validation lane
  semantics (`author_intent_caveated` instead of generic unsupported); four-project rerun.

## 14. Codex-owned implementation and RAP product regression (2026-08-12)

Codex took over implementation and testing in the same dirty worktree. This round repaired the
remaining Writer post-processing connections and ran one fresh, serial RAP product regression.

### 14.1 Implemented repairs

1. **Style issue -> owning Rewrite route.** `publication_quality` now exposes one shared
   `find_code_trace_prose_sections` detector. `publication_method_writer` converts its section
   results into typed `method_language_style / wording_only` issues and sends them to
   `LocalRewriteAgent`. Rewrite candidates are kept only when reverse-validation counts do not
   regress and a validation or Method-language issue improves. Unmatched candidate/review claims
   are not sent to lexical Rewrite for mass deletion.
2. **Representation-only Rewrite coordinate recovery.** A live Rewrite returned an exact
   full-section `original_text` with an incorrect numeric `end`. Coordinates are now recomputed
   only when that exact source text occurs exactly once in the frozen incumbent. No lexical text is
   changed; recovery is traced as `repair_unique_exact_span_coordinates`; ambiguous spans still
   fail closed.
3. **Candidate/verified validation semantics.** `run_summary` now reports separate
   `candidate_validation` and `verified_validation`. `MethodDraftBundleV1` persists the validation
   split report, and sentence splitting records `split_mode=sentence_reverse_validation`.
   Verified status is read from that fail-closed split instead of relabeling candidate validation.
4. **Product-quality semantics.** Exact assignment/semantic-frame closure remains audit metadata
   and no longer participates in the reader-facing candidate plan gate. Ordinary words such as
   `facts` and `spans` are not mistaken for internal IDs. Parenthetical code identifiers are allowed
   evidence bindings; raw code symbols as sentence subjects or execution inventories remain style
   failures.
5. **Prompt/loader integration.** The Rewrite prompt requires mechanism/data-transformation
   subjects and minimal parenthetical code bindings. Formalization callback results load as typed
   `FormalizationResultV1`. Every Writer section is instructed to begin with one supplied H2 title.

### 14.2 Static verification

```text
python -m pytest -q tests/test_agentic_writer_paper_language_quality.py \
  tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_d4_owner_fault_injection.py \
  tests/test_agentic_autonomous_method_agent.py
# exit 0: 107 passed, 2 pre-existing Pydantic serialization warnings

python -m pytest -q
# exit 0: 2431 passed, 3 skipped, 2 warnings, 12 subtests passed

python -m compileall -q src tests
# exit 0

git diff --check -- <touched production and test files>
# exit 0
```

### 14.3 Fresh RAP live regression

Runtime before submission: `/health` and `/v1/models` 200; model
`qwen36-27b-nvfp4`, frozen root `/data1/users/cuihengjia/qwen3.6/models/Qwen3.6-27B-NVFP4`,
context 131072; PID 1492408; TP=1; fp8 KV; flashinfer; MTP=2; queue running=0/waiting=0/KV=0.
Only RAP was submitted.

```text
python -m code2paper.cli.main method-agent run \
  --repo <frozen RAP repository> --author-intent <frozen RAP author YAML> \
  --out /tmp/code2paper-method-agent-live-rap-codex-20260812 \
  --llm-profile tests/live/profiles/qwen36_vllm_budgeted.example.env \
  --max-research-turns 30 --run-id rap-codex-20260812
# exit 0
```

Result:

- research trusted, 30 turns, 178 research-tool artifacts, no synthetic support;
- 22 planned sections and 22 H2 headings (FPW2 had one heading);
- one repository callback fulfilled; only `MA-S1` resumed; no pending/external queue;
- candidate 26,354 bytes; 193 checked factual claims; 187 candidate unsupported/review-linked;
- verified 3,234 bytes; 6 positive units; zero unsupported positives;
- 171 editable review items;
- candidate unsupported count improved from FPW2 267 to 187;
- summary reports candidate validation `failed` and verified validation `passed` with the sentence
  split mode;
- runtime after completion: health 200, running=0, waiting=0, KV=0.

The run exposed the coordinate-only Rewrite defect fixed above. A subsequent single-call live replay
against the frozen `MA-S1` incumbent returned `status=applied`, no patch failures, and the disclosed
coordinate recovery operation. The response used mechanisms as sentence subjects and code symbols
as parenthetical bindings. A second full RAP run was intentionally not submitted.

### 14.4 Current product judgment

The autonomous product loop is now real: author intent -> autonomous research -> evidence ->
author-aligned plan -> multi-section candidate -> callback/resume -> sentence split -> verified +
review outputs. It is not yet publication-ready. The candidate is structurally and semantically
better than FPW2, but multiple sections remain generic/repetitive; 187 candidate factual units need
better lane-aware caveat classification; seven declared supported claims were not rendered closely
enough for the validator; and only one local callback was naturally fulfilled. Next work should
improve candidate lane extraction and supported-claim rendering before the four-project regression.
This single RAP run does not authorize release or cutover.

## 15. Editor/Rewrite academic revision and authority-lane repair (2026-08-12)

Codex implemented the post-run repair directly in the same dirty worktree.  The objective was not
to add another gate or another autonomous stage.  The existing cross-section Editor now performs a
document-level academic audit, while the existing local Rewrite agent repairs only the affected
section with the same authority-bearing semantic inputs that were available to Writer.

### 15.1 Root cause confirmed from the frozen RAP artifact

1. Editor previously received section prose and shallow repetition hints, but not the per-section
   repository-supported claims, candidate author-intent points, formalization results, terminology,
   or the reader question.  It could improve wording but could not make a trustworthy authority
   decision.
2. Rewrite previously received the issue span and canonical claim text but not the complete Writer
   input.  It therefore had no reliable way to choose among three different repairs: state a
   repository-supported claim positively, preserve an author-intended point with an explicit
   caveat, or remove an unsupported detail.
3. Candidate validation conflated an editable, explicitly caveated author narrative with a positive
   implementation assertion.  Conversely, review-question token matching was broad enough to
   mislabel some positive prose as review material.
4. Supported-claim rendering used symmetric token overlap, which penalized normal explanatory
   Method prose, while the Writer supplied some candidate fact fragments through an accidental
   character-list conversion.  The frozen RAP candidate genuinely omitted several claim subjects,
   but the old metric also overstated the omission count.
5. Rewrite was effectively a one-shot lexical patch.  It did not use the model's typed
   `incomplete` signal to request another bounded attempt, and unmatched positive prose could be
   excluded from the repair route.

The 187 unsupported units in the old frozen candidate remain unsupported under the repaired code;
they are not reclassified merely to make a metric green.  A unit becomes candidate narrative only
when it matches a typed candidate point and contains a visible author/partial/mismatch/pending
marker.  It never becomes repository-verified evidence through that route.

### 15.2 Implemented behavior

1. **Typed candidate narrative.** Final atomic claims carry `candidate_narrative_ids`.  Extraction
   matches each sentence against the section's typed partial, mismatch, author-unverified,
   literature-pending, or formalization-pending points and also requires visible epistemic framing.
   The validator returns `caveated`, never `supported`, for this lane.  Bare positive statements and
   points absent from the typed projection still fail.
2. **Document-level Editor.** Editor receives a section context for every section: reader-facing
   repository claims and whether each is already rendered; typed candidate points; formalization;
   paper terminology; required moves; and the section's reader question.  It also receives document
   order and global revision priorities.  The prompt requires mechanism/data-transformation
   subjects, parenthetical-only code bindings, removal of stock scaffolding, consolidation of
   duplicate pipeline summaries, and explicit epistemic framing for candidate points.  Patch
   acceptance is Pareto-checked for authority, unsupported claims, and academic style.
3. **Evidence-aware local Rewrite.** Every issue carries the full frozen Writer authority context.
   Rewrite must choose exactly one authority-preserving action: render a supported claim in academic
   prose with its qualifiers; retain a typed candidate point with a visible caveat; or remove a
   detail authorized by neither.  It cannot invent a formula, result, novelty claim, configuration,
   or implementation fact.  Code names may appear only as short evidence bindings rather than as
   the grammatical subject of an execution trace.
4. **Adaptive but bounded revision.** The local Rewrite loop defaults to two attempts and is
   configurable through `CODE2PAPER_LOCAL_REWRITE_MAX_ATTEMPTS`, clamped to 1--4.  A typed
   `incomplete=true` requests another attempt.  The loop stops on completion, no semantic gain,
   repeated output, budget exhaustion, or validation regression.  Each attempt receives the latest
   accepted incumbent and has its own authorship ledger.
5. **Coverage and style issues.** Rewrite issues now include generic Method templates,
   cross-section semantic repetition, code-trace prose, and supported reader-facing claims not yet
   rendered.  Reverse-validation fragments are consolidated before routing.  Acceptance rewards a
   reduction in unsupported/unverified units and an increase in supported renderings, without
   trading one for a regression in another.
6. **Preventive Writer input repair.** The Writer prompt now reserves positive declarative language
   for repository-supported claims, requires visible caveats for candidate points, forbids unbound
   neighboring detail, and limits claim-free transitions.  Candidate fact fragments are typed
   fact objects rather than characters accidentally sliced from a stringified tuple.
7. **Rendering measurement.** Supported-claim rendering now uses directional semantic-anchor
   recall with a precision floor and avoids splitting dotted identifiers as sentence boundaries.
   On the frozen RAP section this reduces metric false negatives while leaving four genuinely
   under-rendered claims for Rewrite to integrate.

### 15.3 Verification

```text
python -m pytest -q tests/test_agentic_candidate_verified_split.py \
  tests/test_agentic_writer_paper_language_quality.py \
  tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_d4_owner_fault_injection.py
# exit 0: 96 passed, 2 pre-existing warnings

python -m pytest -q
# exit 0: 2433 passed, 3 skipped, 2 warnings, 12 subtests passed

python -m compileall -q src tests
# exit 0

git diff --check
# exit 0
```

## 17. Organization-first Method repair and live validation (2026-08-12)

### 17.1 Root cause and implementation

The rich RAP candidate was organized incorrectly: 23 story-spine nodes were flattened into 22 peer
sections, so stages, components, rationale checks, and four author-authored organization nodes all
became headings and repeatedly reintroduced the same pipeline.  The Architect now uses 2--8
explicit `ORGANIZATION` story nodes as top-level anchors, assigns every other bucket by semantic
overlap with a positional fallback, and preserves every argument unit and obligation.  Frozen RAP
therefore has four sections but still contains all 22 argument units and has zero unrealized story
nodes.

Editor changes are accepted per section transaction.  A regressing section retains its incumbent
without rolling back safe edits elsewhere.  Editor may not delete or rename a section heading.
Rewrite returns at most one complete paragraph/section patch per call; it may not collapse the body
or delete/change an existing heading, and a heading-less incumbent must gain the exact planned H2.

Writer skill 1.8 fixes three prompt/protocol defects: the exact heading is now present in the
request payload; typed candidate points form an explicit caveated paragraph plan instead of being
suppressed by `anchored_required_moves`; and one factual operation is written once even if it
completes mechanism, data-flow, and implementation moves.  Multiple argument units are grouped into
conceptual paragraphs.  The harness never manufactures prose or headings.

### 17.2 RAP replay and complete autonomous run

Frozen input and final replay:

```text
/tmp/code2paper-rap-consolidated-frozen-input-20260812-c
/tmp/code2paper-rap-consolidated-publication-replay-20260812-e
```

The replay candidate has exactly four author-organization H2 headings, five body paragraphs, 3,959
bytes, and a 1,000-byte verified product.  This replaces the previous 21-heading/13,687-byte flat
document with overview -> feature extraction -> learning framework -> deployment.  It remains
`incomplete`: feature/deployment prose is still identifier-heavy and supported rendering is not
complete; zero unsupported positives enter verified.

Fresh complete RAP run:

```text
/tmp/code2paper-method-agent-live-rap-organization-v18-20260812
```

Exit 0 after 30 turns: 11 evidence packets, 50/50 verified facts, seven supported claims, 22 typed
gaps (two explicit), four H2 sections, four body paragraphs, 3,256 candidate bytes, 1,083 verified
bytes, one callback fulfilled in two rounds, and only MA-S2 resumed.  Candidate validation reports
16 unsupported and five supported factual units.  Verified validation passed with four positive
units and zero unsupported positives.  Writer remains `incomplete` with 21 review items, which is
truthful for unresolved author/evidence content.

### 17.3 Verification and remaining matrix blocker

```text
python -m pytest -q --disable-warnings --junitxml=/tmp/code2paper-r17-full-static.xml
# exit 0: 2436 passed, 3 skipped, 12 subtests passed, 2 warnings

python -m pytest -q tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_d4_owner_fault_injection.py tests/test_llm_section_writer.py \
  tests/test_agentic_method_architect_product_readiness.py \
  tests/test_agentic_writer_paper_language_quality.py
# exit 0: 159 passed, 2 warnings

python -m compileall -q src tests
# exit 0

git diff --check
# exit 0
```

The single authorized runtime was repeatedly occupied by an unrelated 95-chapter workload (v3
through v7), sometimes starting after an idle check.  No second Code2Paper project was submitted
concurrently.  RAP records periods of contention but completed.  After RAP, v7 continued holding
the only model for more than ten minutes, so EBCAR, LinearRAG, and DyG-Mamba were not started under
contention.  Their live matrix rows remain externally blocked until a stable serial runtime window
exists.

## 17. Organization-first Method repair and RAP live diagnosis (2026-08-12)

### 17.1 Root cause from the publication candidate

The rich RAP candidate was not primarily missing content.  Its plan flattened 23 story-spine
nodes into 22 peer sections: stages, components, rationale checks, and the four author-authored
organization nodes all became headings.  The same method pipeline was consequently reintroduced
under many headings.  Editor and Rewrite could polish sentences but could not repair the wrong
document hierarchy safely.

The Architect now uses explicit `ORGANIZATION` story nodes as top-level section anchors (only when
there are 2--8 such nodes), assigns every remaining story/completeness bucket by semantic overlap
with a positional fallback, and preserves every argument unit and obligation.  On the frozen RAP
inputs this changes 22 peer sections into four author-intent sections while retaining all 22 units:

1. overview;
2. importance-aware feature extraction;
3. learning framework;
4. deployment.

The story-spine usage trace also recognizes an exact linked claim as realization, not only an
exact linked obligation.  The frozen projection reports zero unrealized story nodes and
`candidate_ready_with_review`.

Editor repair is now accepted per section transaction.  A regressing section stays on its
incumbent while safe sections from the same Editor batch can be retained.  Rewrite output is now
one complete paragraph/section patch per call; readability and severe-collapse guards remain
fail-closed.

### 17.2 First consolidated RAP replay and the prompt/contract defect

Frozen input:

```text
/tmp/code2paper-rap-consolidated-frozen-input-20260812-c
```

First replay:

```text
/tmp/code2paper-rap-consolidated-publication-replay-20260812-c
```

All four planned sections generated, but the visible Markdown had only two H2 headings, three body
paragraphs, 2,897 bytes, and 2.7% duplicate rate.  The feature-extraction paragraph repeated the
same repository operation three times under mechanism overview, algorithm/data flow, and
implementation realization.  The verified product remained safe (zero unsupported inclusion),
but the candidate was too compressed and still code-trace-like.

This exposed a real prompt protocol defect rather than only weak local-model prose:

- the Writer was told to copy the supplied `heading`, but the publication request did not expose
  `heading` as an independent input field;
- candidate points were present, but the instruction said to write only anchored required moves,
  suppressing author-intent/partial/mismatch narrative into generic summaries;
- rhetorical moves were interpreted as separate prose quotas, even when one operation naturally
  satisfies several moves.

The corrected Writer protocol now exposes the exact heading, treats typed candidate points as an
explicit caveated paragraph plan, groups multiple argument units into conceptual paragraphs, and
states that one operation is written once even when it completes several rhetorical moves.  The
move names remain response metadata, not extra prose.  Writer skill version is 1.8.

An attempted hard heading binding gate was deliberately rejected after focused tests showed that
it converted a style defect into whole-section absence and hid unrelated callback diagnostics.
Heading is now a Writer/Editor quality responsibility; evidence and callback binding semantics are
unchanged.

### 17.3 Verification and live-run constraint

```text
python -m pytest -q --disable-warnings --junitxml=/tmp/code2paper-r17-full-static.xml
# exit 0: 2436 passed, 3 skipped, 12 subtests passed, 2 warnings

python -m pytest -q tests/test_llm_section_writer.py \
  tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_method_architect_product_readiness.py \
  tests/test_agentic_writer_paper_language_quality.py
# exit 0 before the final heading-payload regression test: 148 passed, 2 warnings

python -m compileall -q src tests
# exit 0

git diff --check
# exit 0
```

The authorized runtime remained healthy and served `qwen36-27b-nvfp4`.  A separate 95-chapter
generation process repeatedly occupied port 8003 and resumed while the first RAP replay was in
flight.  No competing Code2Paper project was launched.  The corrected RAP replay and the four
fresh full projects must run only after the shared runtime returns to running=0/waiting=0; all runs
remain serial and use fresh output roots.

The tests cover typed candidate/caveat matching, rejection of a bare positive version of the same
point, Editor context propagation, Writer-equivalent Rewrite context, academic explanatory claim
rendering, and the bounded second Rewrite attempt requested by `incomplete=true`.

### 15.4 Live status and next acceptance run

At final verification, `http://127.0.0.1:8003/health`, `/v1/models`, and `/metrics` all refused the
connection (HTTP 000).  No model request was submitted and no process was relaunched implicitly.
Therefore this round proves the static contracts and routing but does not claim a new live quality
result.

When the authorized runtime is restored, run one fresh RAP output root first.  Accept the behavior
only if: verified output still contains zero unsupported positives; old bare implementation claims
are either removed or visibly converted to a matching typed candidate lane; supported-claim
rendering increases; generic/repeated section openings decrease; Editor and each adaptive Rewrite
attempt have traceable authorship and validation ledgers; and callback/resume behavior does not
regress.  Only then proceed to the remaining three-project serial regression.

## 16. Real RAP Editor/Rewrite validation and in-direction repair (2026-08-12)

The authorized runtime was reachable from the host environment and idle before submission:
`/health` and `/v1/models` returned HTTP 200; the served model was `qwen36-27b-nvfp4` from the
designated Qwen3.6-27B-NVFP4 root with context 131072; MTP=2, fp8 KV, FlashInfer, running=0,
waiting=0, and KV usage 0.  The sandbox-local first probe returned HTTP 000 because the sandbox
cannot see the host loopback; the approved host probe and all model calls succeeded.

### 16.1 Full fresh RAP run

Frozen inputs were the same RAP `code_final` repository and author-intent YAML recorded by the prior
run.  The fresh output root was:

```text
/tmp/code2paper-method-agent-live-rap-editor-rewrite-20260812-a
```

The complete autonomous run reached 30 research turns, compiled 11 evidence packets, 50 verified
facts, seven supported claims, a 22-section plan, and then exercised Writer, Editor, Rewrite, and
final validation.  It terminated blocked with
`publication_final_reverse_validation_failed`: candidate validation contained 25 unsupported, three
supported, and two caveated units.  The old comparable candidate had 187 unsupported units, so the
new authority context materially changed generation, but the result was not publishable.

Frozen-artifact analysis exposed three product defects:

1. The single whole-document Editor request reached the output length limit and representation
   recovery could not find valid JSON.  The Editor returned zero patches.
2. Rewrite ran on 19 sections and applied 16 responses, but many responses lowered the unsupported
   count by erasing paragraphs.  Several sections became blank or contained only connective debris
   such as `and`.  The aggregate safety metric improved while candidate utility collapsed.
3. Three responses mixed a full-section patch with nested sentence patches, so exact patch
   application correctly rejected them for overlap.  The retry loop did not retry a rejected patch;
   it retried only when the model itself returned `incomplete=true`.

### 16.2 In-direction implementation repair

1. Cross-section editing is now performed in story-order groups of four sections by default
   (`CODE2PAPER_PUBLICATION_EDITOR_BATCH_SIZE`, clamped to 1--6).  Every group retains the global
   outline, its neighboring section IDs, and its own authority context.  Each lexical patch keeps
   the exact response reference of the batch that generated it.  A malformed batch does not erase
   valid results from unrelated batches.
2. Rewrite's prompt forbids overlapping full-section plus sentence patches and forbids solving a
   candidate-authority problem by deleting the entire section.  It must preserve supported claims
   and convert typed candidate points into concise prose with a visible epistemic marker.
3. The harness rejects a rewritten Method section that becomes empty, connective debris, or a
   severe long-section collapse.  This protects candidate utility without weakening evidence
   validation and without inventing deterministic prose.
4. Rejected overlap/readability responses receive one bounded second attempt with the exact prior
   `blocked_reason` and `patch_failures`.  The model is told to return one non-overlapping paragraph
   or section patch and to preserve candidate narrative rather than erase it.

### 16.3 Frozen-evidence publication replay

Research and evidence were not rerun after the repair.  The first full run's digest-pinned
claims/facts/plan/evidence were linked into a frozen input directory, and the publication path was
replayed with live Writer, grouped Editor, Rewrite, and final validation into:

```text
/tmp/code2paper-rap-editor-rewrite-publication-replay-20260812-b
```

The replay completed without a final-validation block and wrote both products.  The resulting
candidate is 13,687 bytes across 21 headings, contains no blank/connective-debris sections, and the
verified product is 2,275 bytes with four supported units and zero unsupported positives.  The run
remains `incomplete`, not successful: candidate validation has 83 unsupported, four supported, and
one caveated unit; 81 review items remain; one Writer section was missing; and supported-claim
rendering remains incomplete.

Grouped Editor behavior was proven live: six response references and 21 proposed patches were
produced with no new output-length event.  However, the product path still evaluates the union of
all Editor patches as one global candidate.  Claim/configuration/move/style regression in a subset
caused all 21 patches to be rolled back.  Rewrite made 40 calls (20 first attempts plus 20 bounded
second attempts); seven transitions were applied and 33 rejected.  Thirteen sections exhausted the
two-attempt budget.  The readability guard prevented the former empty/`and` failure mode.

Runtime after the replay was idle: running=0, waiting=0, KV=0, with zero model error, abort, or
repetition finishes.  One length finish occurred in the pre-repair whole-document Editor request;
the grouped replay added none.

### 16.4 Current product judgment and next code target

The new prompts and authority context are directionally effective, and the candidate/verified
boundary remains safe.  The product is still not publication-ready.  The next bottleneck is no
longer missing Editor/Rewrite context; it is repair transaction granularity:

- validate and commit Editor patches per batch or per section, preserving safe improvements while
  rejecting only the regressing group instead of rolling back the full 21-patch union;
- replace offset-heavy multi-patch Rewrite output with one typed paragraph/section replacement per
  call, then re-extract issues from that accepted incumbent before another attempt;
- include positive utility requirements in each local transaction: preserve/render the assigned
  supported claims, keep a readable typed candidate point when present, and reduce the assigned
  unsupported unit rather than merely shortening text;
- after those changes, replay the same frozen publication inputs before another full research run.

### 16.5 Verification

```text
python -m pytest -q tests/test_agentic_d4_owner_fault_injection.py \
  tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_writer_paper_language_quality.py \
  tests/test_agentic_candidate_verified_split.py
# exit 0: 98 passed, 2 pre-existing warnings

python -m pytest -q
# exit 0 (full suite; two new tests added to the previous 2433-test baseline)

python -m compileall -q src tests
# exit 0

git diff --check
# exit 0
```

## 19. Proposition-first Writer/Verifier repair handoff (2026-08-13)

The full implementation and code-level rationale are recorded in
`.agent/method_proposition_writer_verifier_repair_20260813.md` §18. The product path now carries
reader-facing Method propositions from compiled repository/author evidence through Architect,
four-layer Writer input, bounded Writer-owned repair, semantic paraphrase alignment, reverse
validation, and the candidate/verified/review split. Low-level claim/fact/frame IDs remain in the
digest-bound sidecar and harness rather than competing with the Writer's sentence plan.

One vertical fixture caught and fixed an integration defect that unit tests had missed: compiler
stage groups may omit obligation IDs, causing repository propositions to disappear from argument
units despite the selected atomic claim carrying exact `covers_obligation_ids`. Architect now
propagates that exact coverage and emits a closed acyclic reader-order proposition dependency graph.

The quality report now counts candidate unsafe positives from persisted reverse-validation
failures, and candidate-only propositions are excluded from the repository-evidence validation
denominator. Required propositions have an explicit three-way product closure: reverse-validated,
visibly caveated, or deferred with a typed reason. Silent drops remain incomplete.

Final static state:

```text
python -m pytest -q
# exit 0: 2480 passed, 3 skipped, 2 warnings, 12 subtests passed in 43.75s
python -m compileall -q src tests
# exit 0
git diff --check
# exit 0
```

Fresh live acceptance is not claimed. Final probes to the authorized 8003 runtime returned HTTP
000/connection refused for both `/health` and `/v1/models`; `nvidia-smi` exited 9 because the NVIDIA
driver was unavailable. No API request or project run was submitted. Once the runtime is restored,
run a fresh RAP root first and inspect the proposition/sidecar/WriterView/alignment/repair/product
artifacts and story-spine coverage before proceeding to EBCAR, LinearRAG, and DyG-Mamba. Controlled
parallel execution is allowed only when the engine advertises safe sequence/KV capacity; use fresh
roots and reduce concurrency on waiting, KV pressure, OOM, or abort signals.
