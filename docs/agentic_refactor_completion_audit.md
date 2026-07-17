# Code2Paper Agentic Refactor Completion Audit

Date: 2026-07-18

Implementation branch: `codex/agentic-p4-benchmark-cutover`

Current formal benchmark commit: `9a98c17aaa4dd5134804ee057d7ff5d5d81e281e`

This audit separates implementation evidence from rollout authorization. A passing
deterministic run proves that the V2 contracts can complete; it does not replace the
fixed-vs-agentic Gemma matrix or named human review required for cutover.

## Verification baseline

- Full suite: `477 passed, 2 skipped, 6 subtests passed`.
- Formal protocol: 25 runs, frozen from a clean tracked commit.
- Completed current-commit matrix: 5/5 deterministic, 5/5 fixed legacy, and 15/15
  cache-disabled Gemma protocol records are present.
- Agentic Gemma: 11 trusted completions and 4 explicit safe blocks; every completed
  package has zero final unsupported leakage and a real model-writer provenance record.
- Projects/intents: toy train, FastGS training, FastGS rendering, Spatial-SSRL, MOS.
- Adversarial campaign: 13/13 curated mutations detected.
- Every current deterministic package binds `intent_spec`, final text trust artifacts,
  figure scene/audits/SVG, final TeX, final PDF, and delivery files by SHA-256.
- Machine-readable digests and current blockers are recorded in
  `tests/baselines/agentic/p4_live_matrix_status.json`.
- Post-matrix Domain Pruning repair now rebinds focused evidence by claim text across
  evidence-freeze claim renumbering and drops author-claim references outside frozen
  MethodEvidence. The deterministic real-project run is trusted complete; the follow-up
  Gemma run remains a safe block because model retrieval omitted the top-level pruning
  implementation before repair could run. This is a retrieval-recall gap, not cutover
  evidence, and is documented in execution-plan section 12.11.
- A follow-up deterministic retrieval-diversity patch now caps repeated paths and
  injects bounded symbol-index path seeds. The real Domain Pruning run froze all three
  core pruning files and completed with 4/4 final factual claims supported. A new Gemma
  run is still required before changing the frozen live baseline.
- Content-based mechanism rebinding now requires operator-specific code signatures and
  is shared by AtomicClaimV2, authoring projection, and final-text validation. Stage
  matching also normalizes Unicode hyphens and preserves few-shot/mixed-domain intent,
  while internal paper-facing stage-name contracts are excluded from prose facts.
- The resulting Domain Pruning deterministic v6 is trusted complete with 7/7 final
  factual claims supported and zero final unsupported leakage. Blind comparison opened
  the original only after generation: frozen surface coverage is 5/6 versus the
  original's 6/6. The generated few-shot sentence is semantically present but absent
  from the frozen alias list, so the raw 5/6 score was retained rather than post-hoc
  tuning the evaluator. The machine record is
  `docs/agentic_domain_pruning_real_project_eval_2026-07-18.json`.
- The pre-fix Gemma run safely rejected all 10 claims bound to unrelated runtime
  evidence. The post-fix Gemma rerun is pending because `127.0.0.1:8000` currently
  refuses connections; this deterministic result does not alter the formal baseline.
- Exact evidence-span scoping now prevents an ambiguous `forward` symbol from using a
  whole file to infer behavior while citing only a local span. Shared operator matching
  recognizes grouped dynamic filtering, normalized top-k gating, and base-expert
  MoE-in-MoE composition, but projects high-specificity operators only into stages that
  explicitly request them. Partial claims without an explicit qualifier are forbidden.
- The resulting three-case current-tree deterministic matrix is trusted complete with
  zero final unsupported leakage: UniMMAD 6/6, CodeQuant 4/4, and Domain-Specific
  Pruning 7/7 final factual claims supported. Frozen blind body coverage is respectively
  5/7, 5/5, and 5/6 versus original 6/7, 5/5, and 6/6. UniMMAD improved from the prior
  2/7 to 5/7 without asserting the unsupported causal general-to-specific narrative.
  The digest-bound machine record is
  `docs/agentic_real_project_operator_eval_2026-07-18.json`; it is follow-up evidence,
  not a rewrite of the formal P4 baseline.
- Cutover decisions now use schema 2.1 and carry invocation-derived
  `NamedReviewEvidenceV2`. Self-reported `--observations` remain valid report inputs but
  cannot authorize cutover; only review files whose run, trust-artifact, and mutation
  digests were actually re-read can contribute the 25 unique review digests required by
  the frozen protocol. The implicit default route also rejects old 2.0 or handwritten
  `default_ready` decisions without that evidence. The machine record is
  `docs/agentic_cutover_review_gate_2026-07-18.json`.
- The 25-entry queue can now be materialized into a non-overwriting named-review
  workspace with one editable review and one code-grounded context per protocol
  identity. Batch validation fails closed on placeholders, identity coverage,
  immutable run/protocol/snapshot/model/claim/verdict/mutation bindings, artifact
  drift, or path escape, and emits no observations until every review passes.
  The frozen workspace currently reports 0 validated, 25 pending, and 0 invalid;
  this improves review operability without claiming that human review occurred.
  The machine record is `docs/agentic_p4_review_workspace_2026-07-18.json`.
- Figure review can no longer score an empty inventory as perfect. Every visible
  scene node, edge, annotation, and group is now materialized from the
  digest-pinned scene and retained as an immutable review inventory; every element
  requires semantic-support and render-drift adjudication, while edges separately
  require direct-relation-evidence adjudication. A completed run with missing or
  incomplete inventory receives zero figure/edge precision, maximal drift, and a
  contract failure. The rebuilt formal queue contains 28 visible nodes across 16
  successful agentic deliveries; all 25 run reviews remain honestly pending. See
  `docs/agentic_p4_figure_review_inventory_2026-07-18.json`.
- Final prose review is also exact-inventory checked. The claim, validator,
  final-trace, and human-review ID sets must be identical; claim text and the
  frozen validator verdict cannot be deleted, duplicated, renamed, rewritten,
  or left implicit. The rebuilt formal workspace contains all 53 final atomic
  claims across 20 agentic records together with the 28 figure elements. It
  still reports 0 validated and 25 pending reviews. See
  `docs/agentic_p4_claim_review_inventory_2026-07-18.json`.
- Human semantic precision now requires two independent decisions: a valid
  gold-claim mapping and explicit confirmation that the frozen direct code
  evidence supports the exact final claim. The queue is bound to the protocol's
  canonical gold digest and exposes gold code spans plus final evidence/trace
  artifacts. All 25 reviewer contexts have validated digests, and context,
  template, or immutable-binding drift fails before placeholder handling. The
  53 evidence-support decisions remain pending; see
  `docs/agentic_p4_code_evidence_adjudication_2026-07-18.json`.

## Final-design Definition of Done

| # | Requirement | Status | Authoritative evidence |
|---|---|---|---|
| 1 | Author intent affects retrieval, section plan, and figure emphasis | Proven for implementation and deterministic paired intent | Digest-bound `intent_spec.json`; intent-aware decision traces; FastGS training/rendering deterministic runs; paired-intent benchmark and cutover gates |
| 2 | Every final atomic claim has semantically validated direct code evidence | Proven | `final_text_claims`, `text_evidence_validation`, EvidenceSpanV2, final text trace, invariant tests |
| 3 | Partial claims retain only supported fragments and required qualifiers | Proven | Authoring projection/plan contracts and qualifier adversarial tests |
| 4 | Final trace is reverse-built from final text without positional/first fallback | Proven | Exact final-text digest agreement across claim extraction, validation, and trace; T007/fallback regressions |
| 5 | Every figure node, label, edge, and annotation has an independent binding | Proven | Figure scene graph, EvidenceRelationV2, relation validation, figure trust tests |
| 6 | A real method figure asset is generated and post-render audited | Proven | Deterministic SVG, rendering manifest, post-render audit, drift adversarial tests |
| 7 | Validators check pass status and artifact digests, not existence alone | Proven | Status/digest invariant, freshness, package-lineage, and tampering regressions |
| 8 | Pre-render, post-render, and final invariants cannot be bypassed | Proven | LangGraph topology/route tests, render authorization, post-package lineage verification |
| 9 | LangGraph decisions have budgets, checkpoint/resume, and complete trace | Proven | Five budgets, typed state/reducers, SQLite resume, freshness-on-resume, decision traces |
| 10 | LangChain tools have structured schemas, idempotency/side-effect declarations, and evidence policy | Proven | Tool specs, LangChain/trust tool manifests, contract audit, idempotency tests |
| 11 | Toy and real projects produce trusted success or a specific repairable block | Proven by machine matrix | 11 Gemma completions, 4 specific safe blocks, plus three current-tree external deterministic trusted completions |
| 12 | Benchmark proves agentic semantic evidence precision is no worse than fixed legacy | **Machine evidence complete; human decision pending** | 25-run matrix, 13/13 mutations, 5 legacy V2 false-success candidates, and 25-entry review queue |

The overall goal must remain incomplete while item 12 is unproven.

## Additional execution-plan cutover conditions

| Condition | Status | Notes |
|---|---|---|
| Current-commit fixed legacy runs | Complete | 5/5 normal finishes; 5/5 fail authoritative V2 usability audit despite legacy fidelity success |
| Current-commit Gemma agentic repeats | Complete | 15/15 records: 11 trusted completions, 4 fail-closed authoring-budget blocks |
| Exact 25-run protocol validation | Complete | All 25 run records bind the same clean commit, gold digest, model profile, and protocol |
| Named human review | Pending | Queue has 25 entries; placeholders are schema-invalid and cannot count as reviews |
| Shadow review | Pending | CLI emits digest-pinned shadow comparison artifacts, but rollout evidence is not complete |
| Opt-in/canary evidence | Pending | Cutover policy enforces the sequence; no reviewed rollout evidence yet |
| Default route | Hold | Legacy remains implicit default; only a clean `default_ready` decision can activate agentic |

## Resume procedure

1. Have named reviewers complete all 25 digest-pinned reviews, including block/false-block
   classification and paired-intent organization checks.
2. Aggregate reviewed observations with the frozen protocol and evaluate worst-case cutover
   thresholds.
3. Run and review shadow, opt-in, and canary evidence in order. Apply a resulting
   `default_ready` decision through `--cutover-decision`; otherwise keep legacy default.
