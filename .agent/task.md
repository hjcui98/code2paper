# Current task

- Task: improve the author-intent-first Method Agent from a heading-complete Candidate into a
  source-traceable, paragraph-structured, formula-consuming Method writer.
- State: `QUALITY_REPAIR_REQUIRED` — same task and worktree; do not create a replacement task.
- Active repair authority:
  `docs/method_authoring_source_ledger_quality_execution_plan_2026-08-27.md`, under the parent
  execution authority `docs/method_intent_first_authoring_redesign_2026-08-22.md`.
  `.agent/plan.md` Active assignment 2026-08-27 points at the new bounded work package. 2026-07-19
  architecture and 2026-07-31 Writer design remain the specifications; Verified stays fail-closed.
- Primary diagnosis (bound `225116`, 2026-08-27): the main quality loss is upstream of prose style.
  Research misses or fails to connect author story slots; facet merge clears useful partial evidence;
  Planner/Architect flatten ordered mechanisms; Formalizer packages have no paragraph consumer;
  the brief Writer prompt conflicts with the semantic-frame grounding contract; whole-section repair
  and callback recompilation consume time without a semantic delta. Writer repair commits were zero
  across all three final replays and no section used an equation id.
- Architect/final reviewer: Codex.
- Execution owner: implementation agent or human developer in this same dirty worktree.
- Worktree: preserve current user changes; do not reset, clean, checkout, commit, merge, or discard.

## Current acceptance checkpoint — 2026-08-27

The six-round report and the final `225116` replays are quality-failure evidence, not a PASS.
Candidate sections now usually exist, but multi-step mechanisms remain paragraph walls, LinearRAG
can invert pruning polarity, DyG can lose Downstream text at a fused heading, EBCAR core code is
classified as unavailable, and code-backed formulas are not consumed. The next implementation must
build the source-to-render content chain defined by the 2026-08-27 plan. It must not respond by only
raising maxLength, retry counts, or callback rounds.

The same task continues. Existing 2026-08-22 repairs remain accepted baseline behavior where they do
not conflict with the new work package.

## Prior acceptance checkpoint — 2026-08-22

Live serial canary `133302` is quality-failure evidence, not a PASS. Earlier 2026-08-18 and
R1–R4 REPAIR decisions remain: Candidate durability and Verified fail-closed are accepted;
equation-only deterministic license and brief-callback schema gates still need the repairs
named in `.agent/review.md`, now folded into WP-L / WP-W / WP-C of the 2026-08-22 document.

Still required (same task):

- Candidate semantic license (LLM) over unlicensed clauses, without upgrading `may_enter_verified`;
- Writer must render `planner_filled` drafts as venue Method prose; ban pending-token shells;
- real Formalizer: academic LaTeX/MD per author mechanism; reject incidental `x*y` as success;
- Rewrite owns de-code-trace / paper language, not drop-FAC deletion of author story;
- writing-time Research-subgraph continuation with brief recompile and section resume, including
  synthetic checkpoint when frozen replay has no `research_stage_checkpoint_v1.json`;
- after search exhaustion, write the full author-logic Candidate with warnings rather than
  omitting the mechanism.

Do not add a Candidate hard gate or require zero Candidate warnings.

## Governing intent

The product must behave as an autonomous Method Agent:

```text
author intent / original paper / claims
  -> research agenda
  -> autonomous code/config/data-flow/control-flow search
  -> evidence packets / facts / atomic claims
  -> support status: supported / partial / mismatch / external pending / author review
  -> semantic license (Candidate) + deterministic license (Verified)
  -> Method Architect organizes the argument by author intent
  -> Formalizer writes academic formulas (code-derived or author-intent)
  -> Writer writes reader-facing Method prose
  -> missing information triggers callback to research (recompile briefs, resume section)
  -> if still missing: full author-logic Candidate + warning
  -> Rewrite converts code-trace sentences into paper language
  -> final outputs: publication candidate, repository verified version, author review items
```

## Output semantics and accepted trust boundary

`publication_candidate_method.md` is the primary editable product. Once non-empty prose has been
generated, validation, Editor/Rewrite regressions, exhausted repair budgets, or later model/API
failures must not erase it. Such findings become warnings and author revision items. A run with a
durably published candidate may be `review_ready_with_warnings` even when it is not
`publication_ready`.

`repository_verified_method.md` is a separate, conservative projection. It may contain only the
sentences that pass repository-evidence reverse validation; it may be incomplete or empty without
invalidating the Candidate.

Keep these as verified-output and audit safeguards:

- Final positive implementation claims require repository evidence and reverse validation.
- Author intent guides scope, organization, candidate wording, and review questions; it does not
  authorize repository implementation facts.
- Unsupported implementation positives must not enter `repository_verified_method.md`.
- Evidence, qualifier, numeric/formula, authorship, checkpoint, and final-integrity checks remain
  strict for verified output and remain visible as Candidate warnings/audit evidence.
- Missing evidence is not failure by itself. It must become explicit candidate caveat, callback,
  or author/literature/formalization review item.
- Defensive source branches, tensor-shape checks, cache/index mechanics, progress logging, and
  similar audit-only details are not Method-writing obligations unless the author story or exact
  selected mechanism makes them scientifically material.

## What changes now

The old R9 objective and the old candidate hard-gate acceptance are superseded for implementation
purposes. Do not continue optimizing hashes, proof closure, matrix counts, repeated lucky samples,
or a stronger model checkpoint in place of improving the actual paper.

The immediate objective is:

1. make Candidate durability and independent Candidate/Verified/publication-readiness states real
   in every publication exit path;
2. fix exact condition ownership so a packet-wide guard cannot contaminate unrelated facts;
3. project evidence into paper-relevant propositions and keep audit-only implementation mechanics
   out of Writer coverage and qualifier repair;
4. upgrade the existing Formalizer into a section-scoped, evidence-bound LaTeX and notation Agent;
5. make Writer and Editor organize the author's story into coherent paper paragraphs rather than
   code-operation prose, placeholders, or repeated protocol caveats;
6. retain flexible but bounded Writer/Editor/Rewrite/callback iteration, always falling back to the
   best durable candidate;
7. prove the change once on frozen DyG-Mamba, LinearRAG, and EBCAR authoring inputs, with strict
   Verified filtering and no unchanged reruns for sample luck.

## Primary handoff document

Use these handoff documents in this order:

1. `docs/method_authoring_source_ledger_quality_execution_plan_2026-08-27.md` — current next-stage
   work package: content-unit diagnosis, source-to-render trace, WP0–WP7, tests and live protocol.
2. `docs/method_intent_first_authoring_redesign_2026-08-22.md` — parent Method Authoring quality
   execution authority and trust boundaries.
3. `.agent/plan.md` Active assignment 2026-08-27 — task-local pointer; do not treat older
   numbered sections as a competing assignment.
4. `.agent/review.md` — prior REPAIR items (equation-only license, brief callback schema)
   still in-direction and folded into the 2026-08-22 WPs.
5. `docs/publication_ready_method_writer_design_2026-07-31.md` — Writer specification.
6. `docs/method_agent_master_agent_mainline_execution_repair_plan_2026-08-17.md` — Master
   Agent mainline.
7. `docs/method_argument_brief_compile_replacing_concept_cards_plan_2026-08-21.md` —
   deterministic Verified license; Candidate wording revised by the 2026-08-22 document.
