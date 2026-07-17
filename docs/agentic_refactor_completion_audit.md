# Code2Paper Agentic Refactor Completion Audit

Date: 2026-07-17

Implementation branch: `codex/agentic-p4-benchmark-cutover`

Current formal benchmark commit: `e9ab53db85d40281043d40885f4b4bd462ab8ed7`

This audit separates implementation evidence from rollout authorization. A passing
deterministic run proves that the V2 contracts can complete; it does not replace the
fixed-vs-agentic Gemma matrix or named human review required for cutover.

## Verification baseline

- Full suite: `415 passed, 2 skipped, 6 subtests passed`.
- Formal protocol: 25 runs, frozen from a clean tracked commit.
- Completed current-commit submatrix: 5/5 agentic deterministic runs finished with
  `status=success`, `completion=complete`, and complete package lineage.
- Projects/intents: toy train, FastGS training, FastGS rendering, Spatial-SSRL, MOS.
- Adversarial campaign: 13/13 curated mutations detected.
- Every current deterministic package binds `intent_spec`, final text trust artifacts,
  figure scene/audits/SVG, final TeX, final PDF, and delivery files by SHA-256.
- Machine-readable digests and current blockers are recorded in
  `tests/baselines/agentic/p4_live_matrix_status.json`.

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
| 11 | Toy and real projects produce trusted success or a specific repairable block | Proven for deterministic route | 5/5 current-commit deterministic successes across toy and three real repositories |
| 12 | Benchmark proves agentic semantic evidence precision is no worse than fixed legacy | **Not yet proven** | Current-commit fixed/Gemma matrix and named human reviews are missing |

The overall goal must remain incomplete while item 12 is unproven.

## Additional execution-plan cutover conditions

| Condition | Status | Notes |
|---|---|---|
| Current-commit fixed legacy runs | Blocked | 5 runs require the unavailable Gemma endpoint |
| Current-commit Gemma agentic repeats | Blocked | 15 runs require the unavailable Gemma endpoint |
| Exact 25-run protocol validation | Partial | Protocol is frozen; 5 deterministic records exist and 20 records are missing |
| Named human review | Pending | Queue has 25 entries; placeholders are schema-invalid and cannot count as reviews |
| Shadow review | Pending | CLI emits digest-pinned shadow comparison artifacts, but rollout evidence is not complete |
| Opt-in/canary evidence | Pending | Cutover policy enforces the sequence; no reviewed rollout evidence yet |
| Default route | Hold | Legacy remains implicit default; only a clean `default_ready` decision can activate agentic |

## Resume procedure

1. Restore and verify `http://127.0.0.1:8000/health` and `/v1/models` for
   `gemma4-31b-nvfp4`, including the expected MTP deployment profile.
2. Execute the remaining fixed and Gemma variants from the exact frozen protocol.
3. Run legacy V2 audits and regenerate the complete review queue.
4. Have named reviewers complete all digest-pinned reviews, including block/false-block
   classification and paired-intent organization checks.
5. Aggregate observations with the frozen protocol and evaluate worst-case cutover
   thresholds.
6. Run and review shadow, opt-in, and canary evidence in order. Apply a resulting
   `default_ready` decision through `--cutover-decision`; otherwise keep legacy default.

