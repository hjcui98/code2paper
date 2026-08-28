# Codex acceptance review — R1–R4 WP-D quality repair (2026-08-22)

- Date: 2026-08-22
- Outcome: **REPAIR**
- Review mode: read-only; no tests, linters, APIs, model calls, replays, benchmarks, or monitors were run
- Authority: 2026-08-21 argument-brief plan + the post-WP-D repair guide (P1–P4 / R1–R4)
- Submitted handoff: `.agent/implementation.md` section **R1–R4 — WP-D repair slices (2026-08-22) — COMPLETE (static)**
- Recorded evidence (not rerun): focused 129 passed; `compileall` clean; **no new live `/tmp` canary**

## Decision

R1 and most of R3 land at the owning layer and can stay. R2’s equation-independent license and R4’s Writer callback gate do not yet implement the claimed mechanism. Do not run R5 on this code. Same worktree, no new task: in-direction `/implement` for the two failed mechanisms below, then R5.

This is not Gate 6B/6C, D5, or a live canary PASS. The `/tmp/c2p-wp-brief-dyg-qwen38-20260822-010218` artifacts are pre-repair and are not evidence for this slice.

## Accepted (keep)

### R1 — Planner budget, traces, bounded batching (P2)

- New role `method_mechanism_draft_planner` with default 8192 output tokens; planner no longer inherits proposition-architect 3072.
- Every attempt writes `planner_call_traces` (`blocked_reason`, `finish_reason`, 2k `response_preview`, `parse_error`) onto `MethodArgumentBriefSetV1`.
- Default remains one request; oversized sets split into at most four ordered batches with monotonic `frag-N`.
- Recorded tests: 8-brief parse failure leaves empty drafts + traces; 8-brief valid batch fills; formula-like Δt draft without equation binding is rejected without caveat.

Residual, not blocking this item: split is count-based (compile happens before the section plan), and the 8-brief fixture never crosses the split threshold. That is weaker than “split by plan section” but is not 23 one-brief calls.

### R2 partial — distinctive-key binding + WriterView evidence (P1.1 / P1.3)

- `_binding_matches_clause` no longer binds every obligation claim that shares a generic key such as `dygmamba`.
- Frozen DyG test: licensed clauses must not pick up softmax / `pad_sequences` claims unless those tokens appear in the clause.
- `evidence_claim_texts` is a read-only claim-text channel; `licensed_wording` is still not the full author statement.
- No return to Concept Architect; no whole-statement license.

### R3 — Writer primary coverage + caveat-shell body (P3)

- `missing_required_briefs` is `required - rendered`; deferred no longer covers primary.
- `rendered_brief_ids.minItems = 1` when `primary_brief_ids` exist; binding contract still passes `primary_brief_ids`.
- Brief-mode `content_first_instruction` names licensed wording, caveated clauses, drafts, and `evidence_claim_texts`.
- `_markdown_has_non_heading_body` strips repeated `(intended|partial|pending)` shells.
- Recorded tests: all-defer fails; repeated caveat tokens are headings-only.

### R4 partial — empty anchor is not `anchored` (P4.1)

- `resolve_move_authority_proofs`: no anchors and no unresolved rows → `state=open` with `unanchored=True`, not `anchored`.
- Recorded test: `test_empty_anchor_move_is_not_anchored`.
- WP-B “anchored clears unresolved” is preserved.

## Failed mechanisms (must repair before R5)

### 1. Equation-only positive/partial license cannot be constructed (R2 / P1.2)

Compiler now puts `binding.equation_id` into `positive_bindings`, but `AuthorClauseLicenseV1` still requires `bound_claim_ids` for `positively_licensed` and claim/target ids for `partially_licensed`. An equation-only hit therefore raises at compile time instead of licensing the clause. There is no regression that a clause hitting equation symbols gets nonempty `bound_equation_ids`.

**Repair (fail-closed, same design):**

- Allow `positively_licensed` when `bound_equation_ids` is nonempty even if `bound_claim_ids` is empty.
- Allow `partially_licensed` when `bound_equation_ids` is nonempty.
- Keep unlicensed clauses evidence-free.
- Regression: clause that hits only a supported equation identifier → `bound_equation_ids` nonempty, compile does not raise, `licensed_wording` still ≠ full author statement.

### 2. Brief callback is not on the Writer schema gate (R4 / P4.2)

`_brief_callback_prototype_payload` can append a `brief_slots` prototype, and the top-level payload sets `callback_required` from that payload. The field the Writer actually reads is `grounding_contract.callback_required`, which is still:

```text
required move ∧ state in {open, external_pending}
```

`_closed_set_publication_schema` still enters the forced `new_research_requests` / `target_brief_ids` branch only when `unanchored_moves and callback_required`. The requested `test_llm_publication_schema_closed_sets.py` brief-mode+callback case was not added. The `brief_slots` prototype uses `missing_rhetorical_move=""`; `WritingResearchRequestV1` cannot accept that.

Empty-anchor→`open` covers the WP-D “empty anchored overview” sample, but a section with real anchors and empty caveat drafts still will not force a brief callback. That is the remaining search-loop hole.

**Repair:**

- Set `grounding_contract.callback_required` (and `callback_response_shape`) true when the brief payload is present, not only when a required move is open.
- Schema: `callback_required` + `brief_binding` forces `new_research_requests.minItems ≥ 1` and required `target_brief_ids` / `target_clause_ids` even if `unanchored_required_moves` is empty.
- Prototype `missing_rhetorical_move` must be a real section move, never `""`.
- Add the closed-set schema test named in the repair guide.

## Explicitly not accepted

- R5 live DyG canary (not run; do not start until the two repairs above are in the same worktree)
- P5 Formalizer `x*y` / FAC-as-success (deferred by the guide)
- Gate 6B / 6C / D5 / default cutover
- Treating 129 static tests as publication quality
- Whole-statement license, Concept Architect revival, or drafts as Candidate prose

## Next

Same worktree, `/implement` only the two REPAIR items, add the named regressions, record commands in `.agent/implementation.md`. Then one fresh `/tmp` DyG canary (R5) on the frozen Research root: planner gaps ≪ 23, traces present, primary briefs rendered, four sections with non-shell body. Still ≠ Gate 6B.
