# Current task

## Active Candidate-first Method quality repair (2026-09-01)

The completed serial replay at
`/tmp/c2p-v34p0p3-8006-{ebcar,dyg,linearrag}-20260901` is the current bound
counterexample. All three runs ended `exit=2`; Candidate prose became cleaner and gained display
math, but organization and formula academicization remain below the frozen v34/v33/08-30 outputs
and the original paper Methods. This is not D5 and structural closure is not the objective of this
repair.

The user-visible objective is the Markdown body in `publication_candidate_method.md`: it should
read like a coherent academic Method section, with the author's problem/motivation, ordered
mechanism, useful paragraph development, paper notation, and clean section boundaries. Evidence
gaps may remain warnings and Verified must remain fail-closed. Do not weaken, filter, or game a
structural/evidence/formula metric to declare success.

### Bound root causes to repair

1. **Author rationale is dropped before Writer.**
   `method_architect._build_method_units_v2` selects only required or formula-bearing facets. In
   the frozen LinearRAG plan this retains the Tri-Graph mechanism but drops the optional rationale
   unit containing the author statement “Avoid explicit relation extraction entirely.” V2 Writer
   then receives no rationale brief and opens Motivation with mechanism detail. Preserve a bounded,
   representative motivation/rationale/design-objective facet and its owning argument unit in the
   MethodUnit projection. Do not promote every optional audit facet or create one paragraph per
   facet.
2. **Academic operation formulas are generated and then discarded.**
   `publication_method_writer._run_section_formalizer` removes accepted LLM packages intersecting
   operation obligations and unconditionally substitutes
   `build_deterministic_operation_formula_packages`. The EBCAR MA-S4 trace contains an academic
   loss formula, but Candidate receives Python-shaped assignment/function-call notation. A valid,
   evidence-bound academic `repository_derived` package must take precedence; exact-operation
   compilation is a fallback/audit representation, not a Candidate display formula. If no
   academic package is valid, leave a typed review/unresolved result rather than publishing code as
   math. Verified continues to accept only its existing code-verified repository lane.
3. **Formula blocks can contain an entire Markdown memo.**
   Formula validation currently checks that `markdown_block` contains display math, not that it is
   exactly a display block. The DyG S5 package therefore inserts `###`, prose, Symbol Definitions,
   bullets, and assumptions verbatim. Canonicalize representation to exactly
   `$$\n<latex>\n$$` (or reject and repair it) for every package lane. Structured explanations,
   symbols, and assumptions are Writer inputs, not placeholder replacement bytes.
4. **V2 Writer packets bypass publication-language filtering.**
   Field candidates pass through `_is_implementation_trace_text`, but MethodUnit
   `ordered_operations` and target rows do not. Generic audit/debug/type-label branches and raw
   code membership expressions therefore survive as ordinal/cardinal prose and
   `(src_node_id, dst_node_id) in edge_memories`. Apply project-neutral filtering or safe
   paper-language projection to every LLM-visible operation/target surface while retaining exact
   audit sidecars. Preserve scientifically material transformations; do not hard-code these three
   projects, paths, identifiers, or desired sentences.
5. **The Writer may repair a truncated heading, but assembly overwrites it.**
   Section assembly uses `section.heading or output.heading_text`, while the prompt and validators
   authorize a coherent replacement only when the frozen heading is deterministically truncated.
   Preserve a validated Writer/Rewrite replacement in that case; keep exact Architect headings for
   all normal sections.
6. **Reader order and paragraph budgets remain too compiler-shaped.**
   Use semantic/rhetorical roles, not heading keywords or project identities, to place a pure
   problem/motivation/context section before technical mechanism sections when a reused plan has
   the reverse order. Preserve relative order otherwise. Derive a useful bounded sentence range
   from conceptual payload (rationale plus mechanism facets/argument units), not merely the count
   of required facets; this must recover developed Motivation/Framework prose without length-only
   padding or repeated paraphrases.

### Required implementation and verification

- Add project-neutral synthetic regressions for: optional rationale surviving MethodUnit
  compaction; academic operation formulas taking precedence over deterministic code notation;
  display-only formula-block canonicalization; V2 operation/target publication filtering while a
  scientific transformation is retained; coherent truncated-heading replacement surviving
  assembly; and rhetorical context ordering/paragraph development.
- Extend the focused quality tests around
  `tests/test_v34prose_formula_and_leak_repair.py`,
  `tests/test_v34like_candidate_plan_freeze.py`,
  `tests/test_llm_section_writer.py`,
  `tests/test_agentic_formalization_guards.py`,
  `tests/test_agentic_publication_method_writer.py`, and
  `tests/test_agentic_method_architect_product_readiness.py` as appropriate.
- Run the focused tests, `python -m compileall -q src tests`, and `git diff --check`; record exact
  commands, exit codes, summaries, code state, and deviations in `.agent/implementation.md`.
- Do not start a new 8006 replay or real API/model job in this repair. First return the static
  implementation for Codex read-only acceptance. A later live replay must use a fresh output root
  and is evidence of prose quality only, never D5 by itself.
- Preserve all unrelated dirty-tree changes. Do not reset, clean, checkout, commit, merge, edit
  authority documents, or weaken Candidate/Verified separation.

## Active implementation handoff — attachment root-cause audit (2026-08-28)

The user-requested implementation basis is the attached audit
`method_agent_architecture_three_project_root_cause_audit_2026-08-28.md`. The attachment is a
diagnosis and implementation proposal, not a replacement for the repository authority map above.
Apply its P0-A through P0-J controls in the current dirty worktree, while preserving the accepted
Candidate durability and Verified fail-closed behavior from the parent design.

The existing uncommitted changes are a partial implementation baseline. Preserve them and repair
their integration defects; do not reset, clean, checkout, commit, merge, or discard unrelated user
work. In particular, verify and complete the currently visible gaps: the Architect's field-candidate
projection and enrichment call path, cumulative observation history for acquisition closure,
post-behavior implementation-scope propagation, ledger-driven terminal routing, full frozen-ledger
rebinding of atomic publication fields, paragraph witness contracts with non-empty authorized
anchors, and one canonical formula obligation/consumer identity.

### Required implementation outcome

Deliver one coherent, generic source-to-render closure across Research → evidence/facts/claims →
atomic facet fields → semantic frames/argument units → paragraph plans → formula consumers → Writer
transactions → content trace. It must:

- infer `target_core`, `target_dependency`, `comparand`, `evaluation`, `configuration`, and
  `unknown` ownership generically from author intent, entry points, imports/call graph, and
  repository topology; never use the three audited project names, paths, claims, or known answers
  in production code;
- retain a `CandidateAcquisitionRecordV1` for every high-priority candidate, including discovered,
  read, behavior-graph, packet, fact/claim, and terminal status; a candidate may terminate only as
  `acquired_and_compiled`, `explicitly_rejected_with_reason`, or `superseded`, and may not disappear
  when the active obligation changes;
- propagate parent/mainline candidates to semantically overlapping child obligations only when
  ownership and call-graph evidence support the propagation; avoid sibling baseline contamination;
- retain proven facet fields when another field is partial/unresolved/mismatched, and rebind each
  atomic publication field from the complete frozen evidence ledger with exact excerpts, polarity,
  conditions, authority lane, stable IDs, and `required|optional|deferred` render policy;
- let Architect promote only consumable, non-conflicting field/slot targets to hard publication
  obligations. Author intent and low-level support slots remain Candidate/review material unless a
  reader-worthy publication target is consumable;
- expose paragraph-local witness targets/contracts to Writer and validation, pass authorized
  semantic anchors into paragraph transactions/content trace, and reject missing or incompatible
  condition/polarity/slot/edge witnesses without relying on generic keyword overlap;
- canonicalize formula-obligation identity so each routed formula has exactly one paragraph
  consumer; reject or report generated-but-unconsumed packages rather than counting them as gain;
- preserve the existing bounded callback route, but continue only when a field/slot/paragraph or
  formula-consumption semantic digest changes. No unchanged compile/rewrite loop, no
  `resume_section_ids=[]` continuation, and no callback-only fallback to a shell;
- emit the source-to-render and closure-metrics artifacts needed to distinguish not-discovered,
  discovered-blocked, rendered-invalid, and rendered-low-quality outcomes. These artifacts are
  observability only and cannot grant Verified permission.

### Required verification and handoff

Add project-neutral synthetic tests for sibling contamination, acquisition closure and candidate
non-disappearance, partial-field preservation, condition/polarity mutation, unknown hard-target
rejection, paragraph anchor/slot/edge coverage, formula-without-consumer, byte-preserving heading
repair, and callback no-delta stop. Extend the existing three-project evaluation fixtures only in
fixture/evaluation code; do not hard-code their identities in generic production modules.

Run the focused tests named by the active source-ledger execution plan as implementation proceeds,
then the required static milestone (`pytest`, `compileall`, and `git diff --check`) when the work
packages are complete. Record exact commands, exit codes, summaries, worktree state, artifact roots,
and any live/replay evidence in `.agent/implementation.md`. Do not edit `.agent/task.md`,
`.agent/plan.md`, `.agent/review.md`, AGENTS.md, or authority documents during implementation.

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
