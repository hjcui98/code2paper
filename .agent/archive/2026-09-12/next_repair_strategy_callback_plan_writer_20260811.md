# Next repair strategy — callback fulfillment, candidate planning, Writer paper quality

- Date: 2026-08-11
- Scope: next large repair after the RAP real run at `/tmp/code2paper-method-agent-live-rap-rerun-20260811`
- Purpose: restore the intended autonomous Agent product path:

```text
author intent / draft / claims
  -> research agenda
  -> autonomous repository search/read/trace/config/data-flow research
  -> evidence packets / facts / atomic claims
  -> supported / partial / mismatch / author / literature / formalization classification
  -> Method Architect organizes a candidate argument
  -> Writer writes paper-language candidate sections
  -> missing information triggers bounded callback research
  -> only affected sections resume
  -> final outputs: editable candidate + repository-verified split + review items
```

This document is a repair guide, not a new architecture.  The existing phase design is still basically right; the current problem is that several pieces are implemented as half-bridges but not connected in the product runner, and the Writer input/prompt still over-exposes low-level code records.

## 1. Confirmed current behavior

RAP rerun after the MethodEvidence/validation fix:

- Output root: `/tmp/code2paper-method-agent-live-rap-rerun-20260811`
- Product path now reaches:
  - autonomous research loop;
  - evidence/facts/claims/completeness;
  - story-spine plan/readiness;
  - candidate writing;
  - final sentence-level reverse validation;
  - verified split.
- `repository_verified_method.md` and `publication_candidate_method.md` are both 636 bytes and identical.
- Final validation passed:
  - checked factual claims: 4
  - supported claims: 4
  - unsupported/unverified positives: 0
- Current text is safe but not yet paper-useful:

```text
The feature extraction pipeline begins by loading the weights `self._features_dc` through `GaussianModel.capture`.
Subsequently, `GaussianModel.construct_list_of_attributes` loads the weights `self._features_dc`,
`self._features_dc.shape[2]`, `self._features_rest`, and `self._features_rest.shape[1]`.
Following this input stage, `GaussianModel.construct_list_of_attributes` calls `range` ...
```

Original RAP Method skeleton has five main sections:

- Overview
- Feature Extraction
- Importance Score Prediction
- Training
- Feedforward Inference

Current generated plan has only one section:

- `MA-S1`: Feature Extraction and Normalization

Current completeness matrix:

- `supported_by_repository`: 1
- `partially_supported_by_repository`: 18
- `explicit_code_gap`: 2
- `author_confirmation_required`: 2

Current callback sidecar:

- Writer emitted one open `limitations_or_mismatch` request.
- Router correctly routed it to `repository_tools`.
- Request has populated `candidate_symbols_or_terms`.
- No artifact was fulfilled.
- No section was resumed.

## 2. Root cause A — callback request/router/resume exist, but product runner does not fulfill

Implemented pieces already present:

- `src/code2paper/agentic/method_argument_models.py`
  - `WritingResearchRequestV1`
  - `WritingResearchCallbackArtifactV1`
  - `WritingResearchCallbackBundleV1`
- `src/code2paper/agentic/writer_research_router.py`
  - `route_writing_research_request`
  - `route_writing_research_requests`
  - `execute_writing_research_route`
  - `execute_open_requests_for_routes`
  - local lanes: repository/config/formalization
  - external lanes: author/literature/empirical/expository queue
- `src/code2paper/agentic/publication_method_writer.py`
  - `fulfill_writing_research_callbacks`
  - `run_publication_method_writer(..., resume_section_ids=..., research_callback_artifacts=...)`
  - checkpoint handling for section-only resume
  - resume integrity checks
- `tests/test_agentic_callback_resume_product.py`
  - proves manual flow:
    1. first Writer emits open request;
    2. route executor returns artifact;
    3. `fulfill_writing_research_callbacks` writes bundle;
    4. second Writer call resumes only `MA-S1`;
    5. unaffected checkpoint entries remain unchanged.
- `scripts/run_d5_consolidated_matrix.py`
  - contains a script-local `_repository_route_provider` and `_auto_fulfill_owned_routes`.

Missing product connection:

- `src/code2paper/agentic/autonomous_method_agent.py::run_autonomous_method_agent`
  currently runs:

```text
research -> evidence_compile -> planning -> persist_product_artifacts
  -> _run_writer_surface() once
  -> callback summary
  -> final summary
```

It never:

- reads `writing_research_callback_artifacts_v1.json` after the first Writer run;
- executes open local-owned routes;
- writes validated callback artifacts;
- passes the callback bundle/checkpoint paths back into a second Writer run;
- repeats bounded callback/resume rounds until no local progress remains.

Therefore the system has a Writer callback protocol but not an autonomous callback loop.

### A.1 Required repair

Add a production callback fulfillment loop after the first Writer call in `run_autonomous_method_agent`.

Do not hard-code “one retry”.  The loop should be budgeted and progress-driven:

- `max_callback_rounds`, default 3.
- `max_callback_tool_turns_per_request`, default 8.
- `max_callback_requests_per_round`, default 8.
- `max_callback_artifacts_per_request`, default 3.
- Stop when:
  - no open local-owned requests remain;
  - a round produces no new validated artifacts;
  - writer returns success and no new local-owned open request;
  - budget is exhausted.
- If budget is exhausted, keep the draft `incomplete` with pending/review items; do not fabricate completion.

Suggested new module:

```text
src/code2paper/agentic/writing_callback_fulfillment.py
```

Suggested public API:

```python
class WritingCallbackFulfillmentBudgetV1(BaseModel):
    max_callback_rounds: int = 3
    max_tool_turns_per_request: int = 8
    max_requests_per_round: int = 8
    max_artifacts_per_request: int = 3


class WritingCallbackFulfillmentResultV1(BaseModel):
    rounds_attempted: int
    local_requests_seen: int
    local_requests_fulfilled: int
    external_requests_seen: int
    resumed_section_ids: tuple[str, ...]
    stopped_reason: str
    trace_path: str = ""


def fulfill_and_resume_writing_callbacks(
    *,
    runtime: ResearchGraphRuntime,
    out_root: Path,
    artifact_paths: dict[str, str],
    writer_paths: dict[str, str],
    llm_config: LLMConfig,
    budget: WritingCallbackFulfillmentBudgetV1 | None = None,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
) -> tuple[dict[str, str], str, str, WritingCallbackFulfillmentResultV1]:
    ...
```

The runner should call it only after the first Writer returns `incomplete` or after the callback sidecar contains open local-owned requests.  The function returns updated Writer paths/status/reason, and the runner updates summary with:

- `callbacks.local_requests_seen`
- `callbacks.callbacks_fulfilled`
- `callbacks.callbacks_pending`
- `callbacks.external_queue_items`
- `callbacks.rounds_attempted`
- `callbacks.resumed_section_ids`
- `callbacks.stopped_reason`

### A.2 Repository fulfillment must be a local research loop, not a one-shot match

The script-local `_repository_route_provider` in `scripts/run_d5_consolidated_matrix.py` is useful as a minimum fallback, but production `repository_tools` should be stronger:

1. Seed the local search from the exact request:
   - `request.exact_question`
   - `request.candidate_symbols_or_terms`
   - `request.current_known_facts`
   - bound section/unit ids
   - bound obligation ids from the plan/completeness row
2. Use `runtime.tool_context()` and `execute_research_tool()` from `src/code2paper/agentic/research_tools.py`.
3. Allow the LLM/supervisor strategy to choose multiple tool calls under budget, for example:
   - `search_symbols`
   - `search_code`
   - `read_symbol`
   - `read_code_span`
   - `find_references`
   - `trace_call_path`
   - `trace_data_flow`
   - `inspect_configuration`
   - `query_behavior_graph`
   - `compile_code_facts` / `validate_code_facts` when a new local packet is assembled
4. De-duplicate tool calls by `(tool_name, arguments, path_scope)`.
5. Stop a request when:
   - a validated artifact is produced;
   - no new observation is produced for two consecutive tool turns;
   - request budget is exhausted;
   - the proposed call violates snapshot/path/scope policy.

Important: callback research may use author intent to choose what to search for, but it may only produce `executable_hard` artifacts from frozen repository evidence.  If it cannot find evidence, it leaves the request pending and candidate prose remains caveated/reviewable.

### A.3 Artifact must be Writer-readable

Current `WritingResearchCallbackArtifactV1` supports both opaque refs and file-backed refs.  In `publication_method_writer._callback_artifact_prompt_payload`, only file-backed refs get `artifact_preview`; opaque refs such as `span:` and `fact:` are passed to the Writer without a preview.

Therefore repository callback fulfillment should write a small digest-pinned artifact file, not only return `fact:...`.

Suggested artifact file:

```text
artifacts/research_tool_data/writing_callbacks/<request_id>/<artifact_id>.json
```

Suggested JSON shape:

```json
{
  "schema_version": "1.0",
  "request_id": "...",
  "section_id": "...",
  "argument_unit_id": "...",
  "authority_lane": "executable_hard",
  "summary_for_writer": "One or two paper-level sentences describing what the repository evidence supports.",
  "matched_fact_ids": ["..."],
  "matched_span_ids": ["..."],
  "matched_relation_ids": ["..."],
  "tool_observation_refs": ["..."],
  "remaining_limits": ["..."],
  "source_snapshot_id": "...",
  "project_tree_hash": "sha256:..."
}
```

Then create:

```python
WritingResearchCallbackArtifactV1(
    artifact_id="writing-callback:<request_id>:<short_digest>",
    request_id=request.request_id,
    section_id=request.section_id,
    argument_unit_id=request.argument_unit_id,
    authority_lane=request.required_authority_lane,
    artifact_ref="<relative path to json>",
    artifact_digest="sha256:<file bytes>",
    validated=True,
)
```

This preserves the fail-closed digest rule while giving the resumed Writer enough local content to write prose.

### A.4 Runner wiring

In `src/code2paper/agentic/autonomous_method_agent.py`:

1. Add function arguments:

```python
max_callback_rounds: int = 3
max_callback_tool_turns_per_request: int = 8
```

2. After first `_run_writer_surface(...)`, if `write_method_text` is true:

```python
writer_artifact_paths = {
    **_writer_artifact_paths(resolved_out),
    **writer_paths,
}
writer_paths, writer_status, writer_blocked_reason, callback_fulfillment = (
    fulfill_and_resume_writing_callbacks(...)
)
```

3. Each resume call must pass a complete artifact path map including:

- original research/planning artifacts;
- `publication_section_checkpoint_v1`;
- `writing_research_callback_artifacts_v1`;
- any updated callback artifact paths.

4. Record a distinct phase:

```text
phase = "writer_callback_fulfillment"
status = ok / no_open_local_requests / budget_exhausted / incomplete / blocked
```

5. Do not rerun the whole research phase or rewrite unaffected sections.

## 3. Root cause B — partial/supportable obligations are classified but not materialized as candidate units

The current model layer is not the problem by itself:

- `src/code2paper/agentic/method_product_models.py` has `repository_partial`.
- `assess_plan_product_readiness` allows candidate output for review-required lanes.
- `MethodReviewCandidateV1.blocks_candidate` is independent from `blocks_verified`.

The problem occurs earlier in `src/code2paper/agentic/method_architect.py::build_method_section_plan_with_trace`.

Current plan construction:

- starts from `claims.semantic_stage_groups`;
- selects only claim ids whose claim status is `supported` or `partial`;
- if intent authoring groups exist, ungrouped claims are not placed through the old fallback;
- completeness rows without claim ids do not become `MethodArgumentUnitV1`;
- story spine is used mostly for ordering and trace, not for creating candidate sections.

In the RAP rerun:

- story spine has 23 nodes;
- only 1 node is `repository_verified`;
- 22 nodes are `author_intent_unverified`;
- completeness has 18 partial rows;
- generated plan has 1 section and 1 unit;
- the other nodes become review sidecar items instead of candidate argument material.

This is why the product is safe but short and not useful.

### B.1 Required repair

Architect must build candidate sections from the author story spine plus completeness rows, not only from supported atomic claims.

Core rule:

- supported repository facts become verified-capable argument units;
- partial/supportable obligations become candidate argument units with explicit lane/caveat;
- author/external/formalization gaps become candidate/review units or external queues;
- only unsupported positive repository wording without caveat blocks.

### B.2 Add candidate units for story/completeness rows

In `build_method_section_plan_with_trace`, after the current claim-group section buckets are created, add a pass that materializes unrealized story nodes/completeness rows.

Candidate rows:

- `partially_supported_by_repository`
- `author_confirmation_required`
- `explicit_code_gap`
- `external_evidence_required`
- `formalization_required`
- `paper_code_mismatch`

Do not materialize `out_of_scope`.

Suggested helper:

```python
def _candidate_units_from_story_and_completeness(
    *,
    story_spine: tuple[AuthorStoryNodeV1, ...],
    completeness: MethodCompletenessMatrixV1,
    existing_units: list[MethodArgumentUnitV1],
    coverage_by_obligation: dict[str, tuple[str, ...]],
    claim_by_id: dict[str, AtomicClaimV3],
) -> list[tuple[str, MethodArgumentUnitV1]]:
    ...
```

Each returned pair is `(section_heading, unit)`.

Unit fields:

- `argument_unit_id`: deterministic, e.g. `MA-CAND-<n>:unit` initially, then renumbered into final `MA-S*`.
- `section_role`: from story node role, usually `stage`, `component`, `objective`, `training`, `inference`, etc.
- `research_question`: story node title or row statement.
- `design_objective`: row statement/story statement as organization authority, not repository fact.
- `claim_ids`: exact row claim ids if present; otherwise empty.
- `source_obligation_ids`: row obligation id.
- `source_artifact_ids`: row `source_artifact_ids` + coverage matched fact ids if available.
- `authority_lanes`: from row authority lane, or lane mapping:
  - partial repository: `("executable_hard",)`
  - author confirmation: `("author_attested",)`
  - external: `("external_literature",)` / empirical as applicable
  - formalization: `("formal_derivation",)`
- `allowed_expository_moves`:
  - partial: include `mechanism_overview`, `implementation_realization`, `limitations_or_mismatch`, and the stage-specific move if known (`training_objective`, `inference_and_output`, etc.).
  - author/external/formalization: include `mechanism_overview` plus `limitations_or_mismatch` or exact owning move.
- `unresolved_inputs`: include typed status, e.g. `O-STAGE-02:partially_supported_by_repository` or `O-STAGE-03:author_confirmation_required`.
- `supported`: false unless every positive required claim is supported and the row is verified-ready.

The section graph for candidate-only units must be `incomplete=True` when unresolved inputs exist, but still `candidate_ready`.

### B.3 Preserve coverage details for partial rows

`MethodCompletenessItemV1` already has:

- `source_artifact_ids`
- `claim_ids`
- `equation_ids`
- `configuration_ids`
- `reason`
- `next_action`

If the existing coverage report has matched fact ids but completeness rows lose them, add a backward-compatible field:

```python
matched_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
matched_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
matched_span_ids: tuple[str, ...] = Field(default_factory=tuple)
```

Then populate it wherever `MethodCompletenessMatrixV1` is compiled from `obligation_coverage_v2`.

This is important because partial rows should not become empty prose shells.  They need enough evidence handles for the Writer to say what is known and what remains unresolved.

### B.4 Writer input must include candidate/review lanes, not only supported claims

After candidate units exist, `_writer_section_inputs` must expose lane-aware context per section:

```json
{
  "section_candidate_points": [
    {
      "obligation_id": "...",
      "lane": "repository_partial",
      "statement": "...",
      "supported_fragments": ["..."],
      "missing_or_uncertain_parts": ["..."],
      "required_caveat": true,
      "review_question_ids": ["..."]
    }
  ]
}
```

Candidate prose may include these points with a clear caveat/review marker.  Verified prose still depends on final reverse validation and repository-supported facts only.

### B.5 Expected RAP effect

After this repair, RAP candidate should not remain a single feature-extraction paragraph.  It should at least produce a candidate structure close to:

- Overview / motivation and scope
- Feature extraction and normalization
- Importance score prediction
- Training / differentiable pruning simulation
- Feedforward inference and output

Only the supported subset enters `repository_verified_method.md`; the candidate draft may carry caveated author-intent / partial / callback-pending material with review items.

## 4. Root cause C — Writer prompt is partially wrong, but prompt-only repair is insufficient

There is a real prompt issue.

Current `src/code2paper/authoring/writer_skill.py` and `src/code2paper/agentic/publication_method_writer.py` contain good instructions:

- write from reader perspective;
- write paper prose only;
- do not expose ids/bookkeeping;
- do not write optional unanchored moves;
- emit callback when required move lacks evidence.

But they also contain safety instructions that pull in the opposite direction:

- preserve exact canonical wording/tokens;
- reverse validator requires overlap with slot vocabulary;
- Writer input exposes semantic frames, canonical claim text, operands, code identifiers and shape/range/config tokens.

When the plan has only low-level code facts and no reader-facing claim abstraction, the model learns that the safest way to pass validation is to serialize code operations:

- `self._features_dc`
- `self._features_rest.shape[1]`
- `range`
- `percentile_cutoff_normalize`

So yes: system prompt/payload design contributes to the bad output.  But changing the prompt alone cannot:

- execute callback routes;
- create candidate sections from partial obligations;
- provide Writer with higher-level paper concepts;
- maintain verified/candidate split.

### C.1 Required repair: introduce reader-facing claim surfaces

Add reader-facing abstraction before Writer prompt construction.

Suggested model extension, preferably in `method_product_models.py` or a small authoring model module:

```python
class ReaderFacingClaimV1(BaseModel):
    claim_id: str = ""
    obligation_id: str = ""
    section_id: str = ""
    lane: MethodEvidenceLane
    paper_statement: str
    code_binding_terms: tuple[str, ...] = ()
    required_qualifiers: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    may_enter_verified: bool = False
    requires_caveat: bool = False
    content_digest: str = ""
```

Generation rule:

- `paper_statement` is derived from author intent + claim/coverage semantics.
- It must not invent implementation facts.
- It can translate code symbols to paper terms:
  - e.g. code symbol `self._features_dc` can remain a binding term while prose says “the DC color feature component”.
  - `range` should normally not appear unless the method really needs a loop-bound implementation detail.
- For supported rows, it is a safe paraphrase of repository-supported facts.
- For partial/review rows, it is candidate-only and must carry `requires_caveat=True`.

Expose this to Writer as:

```json
"reader_facing_claims": [...]
"paper_term_hints": [...]
"code_binding_terms": [...]
```

### C.2 Prompt changes

Version bump `PublicationMethodWriterSkillV1.version`.

Replace the current validation-token instruction with a hierarchy like:

```text
Use reader_facing_claims as the sentence plan.
Use code_binding_terms only to preserve factual binding and only mention raw identifiers when the paper needs implementation realization.
Do not copy validation_constraints.canonical_text as prose.
The validation constraints are for checking meaning, not for choosing wording.
Prefer paper terms over raw symbols; if a raw identifier must be mentioned, put it in a short implementation clause, not as the grammatical center of every sentence.
```

Change `content_first_instruction` in `publication_method_writer.py` similarly:

- Current bad pressure:
  - “preserve those tokens and meanings”
- Replace with:
  - “preserve required qualifiers, equations, numeric values, and semantic roles; do not preserve raw code token spelling unless it is the paper-level term or an implementation-realization detail.”

Add generic examples, not RAP-specific examples:

Bad:

```text
The module calls range with operand x.shape[1] and then passes normalized to normalize.
```

Good:

```text
The feature representation is assembled by iterating over the available feature channels and then applying the recorded normalization step before downstream scoring.
```

This good example is only allowed when the supplied facts actually authorize “feature representation”, “feature channels”, “normalization”, and “downstream scoring”; otherwise it remains a style example, not reusable content.

### C.3 Add a style-quality guard that triggers Rewrite, not evidence weakening

Add a publication-quality issue for code-trace prose:

Possible heuristic:

- too many inline code identifiers per 100 words;
- repeated `self.`, `.shape`, function names as sentence subjects;
- more than N consecutive clauses matching `loads/calls/applies <raw symbol>`;
- section has no reader-facing nouns from `reader_facing_claims`;
- section consists of a single chronological code trace but plan expects mechanism/training/inference moves.

Suggested issue code:

```text
code_trace_prose_not_method_language
```

Handling:

- If factual validation passes but style guard fails, call Rewrite/Editor with:
  - original Writer text;
  - reader-facing claims;
  - code binding terms;
  - validation constraints;
  - instruction to reduce raw identifiers while preserving supported meaning.
- Do not filter facts out to make style pass.
- Do not let Rewrite introduce unsupported positives; final reverse validation still runs.

## 5. Integrated repair order

Do these in the order below.  They are connected, but each has a clear owner and tests.

### Package F — callback fulfillment/resume loop

Files:

- `src/code2paper/agentic/writing_callback_fulfillment.py` (new)
- `src/code2paper/agentic/autonomous_method_agent.py`
- `src/code2paper/agentic/writer_research_router.py` (small extension only if needed)
- tests:
  - `tests/test_agentic_callback_resume_product.py`
  - `tests/test_agentic_writing_route_execution.py`
  - new `tests/test_agentic_autonomous_callback_fulfillment.py`

Implementation steps:

1. Move script-local repository provider logic from `scripts/run_d5_consolidated_matrix.py` into production as the simple fallback provider.
2. Add the stronger budgeted repository callback researcher using `ResearchToolContext` / `execute_research_tool`.
3. Add file-backed callback artifact writer with digest validation.
4. Add `fulfill_and_resume_writing_callbacks`.
5. Wire it into `run_autonomous_method_agent` after first Writer.
6. Add summary fields and phase trace.

Tests:

- Unit: open executable request with matching frozen fact produces file-backed artifact and digest.
- Unit: no matching fact leaves request pending, no resume.
- Unit: repeated same tool call is de-duped; budget exhaustion is recorded.
- Product stub: first Writer emits two local requests; fulfillment creates artifacts; second Writer resumes exactly affected sections.
- Product stub: external author/literature requests go to external queue and do not block resume of local requests.

Exit criteria:

- RAP live run shows `callbacks_fulfilled > 0` when repository evidence exists.
- `resumed_section_ids` is non-empty.
- callback artifact JSON files exist and have digest-pinned previews.
- unaffected section checkpoints are unchanged.

### Package P — partial/supportable candidate planning

Files:

- `src/code2paper/agentic/method_argument_models.py` if matched evidence fields are missing
- `src/code2paper/agentic/intent_obligations.py` or the completeness compiler path that builds `MethodCompletenessMatrixV1`
- `src/code2paper/agentic/method_architect.py`
- `src/code2paper/agentic/method_product_models.py`
- tests:
  - `tests/test_agentic_method_architect_product_readiness.py`
  - `tests/test_agentic_method_product_models.py`
  - new RAP-like fixture test

Implementation steps:

1. Preserve matched fact/span/relation ids on completeness rows for partial coverage.
2. In Architect, compute realized obligation ids from existing claim-based units.
3. For unrealized story/completeness rows, create candidate-only units with exact `source_obligation_ids`.
4. Bucket these units by story spine order and title, not by repository code order.
5. Mark unresolved/caveat moves explicitly.
6. Ensure readiness says candidate-ready-with-review, not blocked, unless unsupported positive without caveat.
7. Ensure review candidates bind to the new section/unit ids.

Tests:

- Partial row with no claim id but matched fact ids creates a candidate section/unit.
- Author-confirmation row creates candidate/review item, not verified fact.
- Explicit code gap creates `limitations_or_mismatch` move and callback-required unit.
- Same evidence with different story spine order changes section order.
- `out_of_scope` row is not materialized as candidate prose.

Exit criteria:

- RAP plan has multiple candidate sections aligned with the author story spine.
- Partial/supportable obligations are visible in candidate sections, not only review sidecar.
- Verified split still excludes unsupported positives.

### Package W — Writer paper-language quality

Files:

- `src/code2paper/agentic/authoring_projection.py`
- `src/code2paper/agentic/publication_method_writer.py`
- `src/code2paper/authoring/writer_skill.py`
- `src/code2paper/agentic/publication_quality.py`
- `src/code2paper/agentic/rewrite_agent.py` if current Rewrite payload cannot consume reader-facing claims
- tests:
  - `tests/test_agentic_publication_method_writer.py`
  - `tests/test_llm_section_writer.py`
  - new `tests/test_agentic_writer_paper_language_quality.py`

Implementation steps:

1. Build `ReaderFacingClaimV1` / equivalent projection records from story spine + supported/partial claims.
2. Expose `reader_facing_claims`, `paper_term_hints`, `candidate_points`, and `code_binding_terms` in each Writer section prompt.
3. Modify prompt hierarchy:
   - sentence plan comes from reader-facing claims;
   - code identifiers are bindings, not prose subjects;
   - validation constraints check meaning, not wording.
4. Add `code_trace_prose_not_method_language` quality issue.
5. Route this issue to Rewrite/Editor with validation-preserving constraints.
6. Re-run final reverse validation after Rewrite.

Tests:

- Prompt payload contains reader-facing claims for a unit whose canonical fact contains code identifiers.
- A Writer output that serializes code records triggers the style-quality issue.
- Rewrite can reduce code-token density while preserving used claim ids.
- Reverse validation still rejects unsupported new positives.

Exit criteria:

- RAP candidate reads like Method prose, not a source-code execution log.
- Raw identifiers appear only where they clarify implementation realization.
- Candidate includes author-intent structure with caveats/review where evidence is incomplete.
- Repository verified output remains narrower and evidence-supported.

## 6. System prompt diagnosis

The current prompt is not completely wrong; it is internally conflicted and underfed.

Prompt-side problems:

- It tells Writer to write paper prose, but also to preserve exact canonical tokens.
- It tells Writer reverse validation needs lexical overlap.
- It gives validation constraints and semantic frames as the dominant content surface.
- It lacks a stronger reader-facing sentence plan.

Non-prompt problems:

- `autonomous_method_agent` does not run callback fulfillment/resume.
- partial/supportable obligations are not materialized into candidate units.
- Writer prompt does not consume the authoring projection as the main writing surface.
- callback artifacts are often opaque refs, so resume may lack readable evidence.

Conclusion:

- Prompt must be repaired, but prompt-only work will not solve this.
- The correct repair is product-loop wiring + candidate planning + reader-facing Writer payload.

## 7. Acceptance after repair

One RAP live canary is enough for first integration only if it shows all of:

- First Writer emits at least one real local-owned callback request when a move lacks evidence.
- Callback fulfillment executes bounded repository/config/formalization research.
- At least one callback artifact is file-backed and digest-pinned.
- Only affected section ids resume.
- Candidate output has multiple Method sections aligned with author intent.
- Partial/supportable obligations appear as candidate/caveated content instead of disappearing into sidecar only.
- Final verified output has zero unsupported positives.
- `run_summary.json` reports the real validation status, callback rounds, fulfilled/pending counts, and resumed section ids.

Four-project follow-up should check:

- RAP
- EBCAR
- LinearRAG
- DyG-Mamba

Do not require every author claim to become repository verified.  The product goal is:

- useful editable candidate draft guided by author intent;
- strict repository-verified split for supported implementation claims;
- explicit review/callback queues for everything else.
