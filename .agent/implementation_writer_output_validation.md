# Agent 2 — Writer / Output / Validation / Callback Surface: implementation record

- Date: 2026-08-11
- Assignment: `.agent/merged_agent_assignments_20260811.md` Agent 2 (merged packages A + E + G + F)
- Execution owner: OpenCode default build
- Delivery record: this file (per merged-assignment §3.8, `.agent/implementation.md` is not used)
- Reused contracts: `src/code2paper/agentic/method_product_models.py` (Agent 1 P0) — no duplicate
  lane/readiness/review schema was created.

## 1. Scope executed

1. A — candidate/verified/review output separation.
2. E — Writer content-first: prose is the primary surface, bindings are auxiliary
   post-processing metadata, unresolved points surface as review items.
3. G — candidate/verified validation split: sentence-level verified filter stays
   fail-closed; unsupported content is review-linked, not silently dropped.
4. F — callback/resume product surface: author/literature/empirical lanes emit
   explicit queue/review artifacts (no silent `None`); repository/config/formalization
   lanes execute locally; resume stays affected-section-only.

## 2. Changed files

Production:

- `src/code2paper/agentic/publication_method_writer.py` — readiness-gated pre-writer
  block (only `blocked_for_safety`), `_build_product_bundle`, `_write_publication_outputs`
  split, review JSON with non-empty proposed bodies, `external_research_queue_v1`,
  `method_draft_bundle_v1`, effective-readiness computation, `unresolved_points`
  collection, `_require_exact_or_subset` subset-only binding, `allowed_authority_lanes`
  string-vs-list bug fix, `_maybe_validate_final_text` persists `authoring_projection_v1`.
- `src/code2paper/llm/section_writer.py` — content-first closed-set schema (enum arrays,
  subsets always legal, unknown ids still rejected at decode), `_publication_contract_failures`
  drops missing-binding failures (unknown only), `unresolved_points` in ordered schema.
- `src/code2paper/llm/response_schemas.py` — `unresolved_points` added to
  `PublicationMethodSectionOutputV1`.
- `src/code2paper/llm/role_config.py` — `METHOD_WRITER` prose sampling:
  temperature 0.20→0.70, top_p 0.95→0.90, seed 42 (role-level seed applied when caller
  leaves it unset); decision/verifier roles unchanged (low/greedy).
- `src/code2paper/agentic/final_text_claims.py` — G1 lane classification
  (`classify_final_text_unit_lanes` + `FINAL_TEXT_LANES` + caveat markers).
- `src/code2paper/agentic/text_evidence_validator.py` — G2 `build_repository_verified_text`
  (sentence-level fail-closed verified filter) with a split report; `_verdict_is_repository_supported`.
- `src/code2paper/agentic/writer_research_router.py` — `ExternalResearchQueueItemV1`,
  `build_external_research_queue_items`, `build_review_candidates_from_requests`
  (author lane → `MethodReviewCandidateV1` with proposed body).
- `src/code2paper/core/output_names.py` — registered `external_research_queue_v1`,
  `authoring_projection_v1`, `method_draft_bundle_v1`.

Not touched (per assignment): `method_architect.py`, `authoring_projection.py`,
`research_graph.py`, `cli/agentic_run.py`, `.agent-team/`.

Tests:

- `tests/test_agentic_candidate_verified_split.py` (NEW, 8 tests) — supported+unverified
  split, mismatch lane, expository bridge, unsafe-positive review linking, unresolved
  points, G1/G2 unit tests.
- `tests/test_agentic_callback_resume_product.py` (NEW, 4 tests) — author callback →
  review item + queue artifact, literature callback → external queue, repository route
  execution + affected-section-only resume, queue-builder unit test.
- `tests/test_agentic_publication_method_writer.py` — updated 4 tests to the new
  candidate/verified semantics (reverse-validation failure no longer blocks the whole
  run; unplaced critical/high is a review item, not a pre-writer block).
- `tests/test_agentic_writing_route_execution.py` — +2 tests (queue builder, author
  review candidates).
- `tests/test_llm_section_writer.py` — +2 content-first binding tests, schema test
  updates for enum-array form.
- `tests/test_llm_publication_schema_closed_sets.py` — const-form test → enum-array form.
- `tests/test_llm_role_config.py` — writer sampling defaults 0.70/0.90/seed 42.
- `tests/test_agentic_r8_acceptance.py` — expected writer temperature 0.7.

## 3. Product behavior changes

- `publication_candidate_method.md` and `repository_verified_method.md` are now distinct
  documents.  Candidate keeps the full authored text (caveated author-intent, mismatch,
  external-pending, review-linked unsupported content); verified keeps only
  repository-supported positive implementation facts plus headings/discourse/bridge
  scaffolding (sentence-level when the reverse validator ran, unit-granular via plan
  readiness otherwise).
- `author_review_candidates.json` items always carry non-empty `proposed_body` and
  `confirmation_question` (schema v1.1).  Sources: completeness-derived review
  candidates (Agent 1 contract), writer-request-derived author items, sentence-derived
  items (Writer span as proposed body), writer `unresolved_points`, and unplaced
  critical/high coverage items.
- `external_research_queue_v1.json` materializes every open author/literature/empirical
  request as a queued artifact — the old silent-`None` path is gone.
- `method_draft_bundle_v1.json` persists the shared `MethodDraftBundleV1` contract with
  effective readiness (plan-level `verified_ready` is demoted to
  `candidate_ready_with_review` when any sentence/item was excluded).
- Ordinary evidence gaps no longer block candidate generation; they block verified
  inclusion only.  `blocked_for_safety` (unsupported positive without a caveat route)
  remains the only pre-Writer block.
- Failed reverse validation changes status from `blocked` to `incomplete`: candidate is
  written, the unsupported sentence is excluded from verified and review-linked.
- Writer prose call no longer must complete every full id/config/equation/move binding;
  missing bindings are validator/post-processing concerns.  Unknown ids still fail
  closed (harness never invents or accepts invented ids).
- Writer prose sampling is now creative (0.7 / 0.90 / seed 42); strict roles keep
  low/greedy sampling.  R8 per-role acceptance updated to the new writer default.
- Latent fix: `_writer_section_inputs` serialized `allowed_authority_lanes` from a
  string proof lane into single characters; now a proper one-element list.

## 4. Callback/resume surface (F)

- repository lane: executes through the local route executor with a supplied
  repository provider (research-tools surface); artifact is digest-pinned, validated.
- configuration lane: matched from the frozen closed config set.
- formalization lane: binds the validated Formalization result digest.
- author lane: becomes a `MethodReviewCandidateV1` (proposed body + exact question,
  blocks verified only) AND a queued external item; candidate continues.
- literature/empirical lanes: queued external artifacts (exact question + truthful
  proposed body + needed evidence), never silent `None`.
- Fulfilled callbacks resume only the affected section; unaffected section checkpoints
  stay byte-identical (covered by existing writer resume tests + new product test).

## 5. Verification

Focused (new + touched subsystems):

```text
python -m pytest -q tests/test_agentic_publication_method_writer.py \
  tests/test_agentic_candidate_verified_split.py \
  tests/test_agentic_callback_resume_product.py \
  tests/test_agentic_writing_route_execution.py tests/test_llm_section_writer.py \
  tests/test_llm_publication_schema_closed_sets.py tests/test_llm_role_config.py \
  tests/test_agentic_final_text_trust.py tests/test_agentic_final_text_trust_v3.py \
  tests/test_agentic_method_product_models.py \
  tests/test_agentic_method_architect_product_readiness.py \
  tests/test_agentic_authoring_projection.py tests/test_agentic_r8_acceptance.py \
  tests/test_r8_acceptance_regression.py
# 325 passed, exit 0
```

Broad agentic/llm regression:

```text
python -m pytest -q --ignore=tests/live -x tests -k "agentic or llm"
# 2197 passed, 3 skipped, 12 subtests passed, exit 0
```

Full static suite:

```text
python -m pytest -q --ignore=tests/live -x
# 2406 passed, 3 skipped, 12 subtests passed, exit 0
```

Syntax/import and patch hygiene:

```text
python -m compileall -q src tests          # exit 0
git diff --check                            # exit 0
```

## 6. What product behavior changed (delivery summary)

- candidate / verified are distinct documents with a shared bundle contract;
- missing evidence produces review items / queue artifacts, never blank candidates;
- verified stays fail-closed: only repository-supported positives (+ structural
  scaffolding) enter `repository_verified_method.md`;
- author/literature/empirical lanes are executable-as-queues (no silent drop);
- repository/config/formalization callbacks execute locally and resume only the
  affected section.

## 7. Known limitations / handoff notes

- The empirical lane has no completeness status mapping to an
  `empirical_artifact` proof lane, so a product-level writer-emitted empirical
  request cannot be produced from the current Architect fixture; the queue
  builder and artifact surface are covered by unit tests and are ready for the
  Architect/CLI packages to expose such lanes.
- `publication_quality.py` was not touched (not owned by this package): its
  report still labels a failed reverse validation as `blocked` at the quality
  level; the writer maps that to `incomplete` at the run level so the candidate
  document is still produced.  A later package may realign the quality report
  status vocabulary with the product readiness states.
- `_write_publication_outputs` writes review/bundle/queue artifacts even on a
  blocked run (blocked reasons remain visible); text documents are written only
  when the run is not blocked.
