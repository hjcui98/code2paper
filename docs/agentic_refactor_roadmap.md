# Code2Paper Agentic Refactor Roadmap

> **Normative self-repair rule:** validation failures must become typed repair
> issues routed back to the owning Agent for bounded retry. Silent filtering,
> pass-by-fallback, hard-gate weakening, and obligation reduction are forbidden.
> See `docs/agentic_error_feedback_and_self_repair_principle.md`.

## One-Sentence Goal

Upgrade Code2Paper from a fixed Python stage pipeline into an author-intent-guided, code-evidence-constrained, LangGraph-orchestrated research writing agent, while keeping every Method claim and figure element traceable to verified implementation evidence.

## Non-Negotiable Invariants

- Author intent guides what the system looks for; code evidence decides what the system may claim.
- `MethodEvidence` and `claim_evidence_map` remain the hard gate before authoring.
- Unsupported or partially supported author claims must not be promoted into paper prose without caveats.
- Method paragraphs and figure briefs must preserve evidence bindings.
- Validators remain graph routing signals, not optional post-processing.
- Rendering must consume evidence-backed method content, not hidden planning artifacts or free-form model imagination.

## Refactor Phases

1. Standardize stage contracts.
   - Add shared `AgenticRunState`, `StageToolSpec`, and `StageToolResult`.
   - Expose current stages as LangChain-style tools.
   - Keep current CLI behavior unchanged.

2. Add the LangGraph shell.
   - Wrap existing intake, analysis, evidence, grounding, authoring, and validation stages as graph nodes.
   - Enforce an evidence gate before authoring.
   - Route validation failures back to authoring or analysis according to failure type.

3. Add model-driven decision nodes.
   - `RetrievalPlanner`: choose files, symbols, search terms, and rescan targets.
   - `CoverageCritic`: decide whether the retrieved evidence covers the author story.
   - `ClaimVerifier`: classify author claims as supported, partial, unsupported, or ambiguous.
   - `RevisionRouter`: decide whether to rewrite prose, downgrade claims, or retrieve more evidence.
   - `FigurePlanner`: select only evidence-backed nodes and edges for the method overview.

4. Improve retrieval and ranking.
   - Build an AST/symbol index for functions, classes, configs, and shell entrypoints.
   - Add hybrid ranking: author hints, keyword score, code graph proximity, symbol matches, and optional embedding similarity.
   - Keep line spans, path, symbol, and content hash on every retrieved evidence item.
   - Emit `retrieval_plan`, `coverage_report`, and `missing_evidence_report` artifacts.

5. Evaluate agentic behavior.
   - Compare fixed pipeline versus graph-agent runs on the existing benchmark.
   - Track evidence coverage, unsupported claim rate, revision loops, validator pass rate, cost, and runtime.
   - Treat better prose without evidence as a failure, not a win.

## Current First Step

The new `code2paper.agentic` package is a compatibility layer over the existing deterministic implementation. It gives the project stable tool contracts and a LangGraph-ready state shape before deeper behavior changes are made.

## Current Second Step

The intake bridge now writes an auditable `agentic_retrieval_plan.json` before code intake and an `agentic_retrieval_coverage.json` after snippet selection. This gives future LangGraph routing concrete evidence for deciding whether to continue, rescan, or ask a coverage critic for targeted queries.

## Current Third Step

The LangGraph shell now includes conservative `coverage_critic` and `revision_router` nodes. Coverage decisions can request another intake pass when a rescan budget is configured, otherwise they proceed with caveats and rely on evidence freeze/validators to suppress unsupported claims. Revision routing sends validation failures back to authoring or analysis instead of blindly continuing to rendering.

## Current Fourth Step

Evidence freeze now emits `agentic_claim_verification.json`, a claim-level audit over the frozen `claim_evidence_map` and `MethodEvidence`. It classifies claims as supported, partial, or unsupported after checking evidence ids, and gives authoring/router nodes explicit actions such as allowing evidence-backed prose, writing caveated partial claims, or returning to analysis for missing evidence.

## Current Fifth Step

Agentic authoring now consumes claim verification before writing. It builds `agentic_authoring_constraints.json`, removes unsupported claims from the writing input, carries partial claims forward only with caveats, and adds explicit writing constraints to the authoring view. The LangGraph evidence gate also requires `claim_verification`, so graph execution cannot proceed from evidence freeze without claim-level audit.

## Current Sixth Step

Method-figure planning is now evidence-backed. The agentic rendering stage builds `method_overview.intent.json` from verified `MethodEvidence` and `claim_evidence_map`, includes only supported mechanisms with evidence ids, omits unsupported claims/mechanisms, and records node/edge evidence bindings before figure generation. LangGraph now routes validation success into a real rendering node instead of ending at a placeholder.

## Current Seventh Step

The agentic graph now has a callable runner API. `run_agentic_code2paper` accepts an `AgenticRunState`, invokes a LangGraph app or injected graph-like test app, and writes `agentic_run_summary.json` with final artifacts, hashes, decision traces, loop counters, and blocked reasons. This creates a stable execution boundary for future CLI wiring and benchmark comparisons.

## Current Eighth Step

The agentic runner is now user-callable through `code2paper-agentic-run` and the unified `code2paper agentic-run` subcommand. The CLI resolves project/output paths, author markers or draft intent, LLM configuration, retrieval-loop budget, and blocked-run exit behavior into an `AgenticRunState`, then delegates execution to the LangGraph runner while preserving the old deterministic `code2paper-run` path.

## Current Ninth Step

Every agentic run now writes `agentic_invariant_audit.json` before the final run summary. The audit checks that frozen code evidence, claim verification, authoring constraints, validation artifacts, and evidence-backed figure plans are present at the points where they become mandatory. This keeps the refactor's central invariant explicit: agentic decisions may choose the path, but unsupported claims and ungrounded figure elements cannot silently become paper output.

## Current Tenth Step

Agentic intake now emits `agentic_symbol_index.json`, a deterministic AST-based symbol/ranking view over Python files. It extracts classes, functions, line spans, parent symbols, docstrings, source hashes, matched retrieval targets, scores, and ranking reasons from author-intent-derived paths, symbols, and keywords. This starts the retrieval/ranking upgrade without replacing the legacy intake selector: LangGraph can now inspect structured symbol candidates before deciding whether to rescan, proceed with caveats, or ask for more evidence.

## Current Eleventh Step

Coverage criticism is now symbol-index-aware. `coverage_critic_decision.json` records targeted rescan hints (`recommended_paths`, `recommended_symbols`, and `recommended_queries`) derived from missing/partial retrieval targets and matching symbol candidates. When LangGraph routes back to intake, the agentic intake bridge writes `agentic_rescan_focus.json` and merges those hints into the next retrieval plan and Phase 1 retrieval hints, so the graph decision changes the next scan rather than merely documenting a weakness.

## Current Twelfth Step

The invariant audit is now an execution gate, not just a report. After graph execution, `run_agentic_code2paper` writes `agentic_invariant_audit.json` and upgrades the run to `blocked` with `blocked_reason=invariant_audit_failed` when blocking evidence invariants fail and no earlier stage has already blocked. The CLI prints audit pass/failure counts in both logs and JSON output, making evidence-gate violations visible to automation instead of burying them in side artifacts.

## Current Thirteenth Step

Method text traceability is now audited at paragraph level. When any Method text artifact exists, `agentic_invariant_audit.json` requires `text_claims.json` to contain paragraph trace records, verifies that every paragraph has evidence ids, checks those evidence ids against frozen MethodEvidence/claim-map evidence ids, and blocks unknown, excluded, or unsupported claim ids from appearing in authored text traces. This tightens the core rule from "authoring had evidence available" to "authored paragraphs still point back to frozen code evidence."

## Current Fourteenth Step

Invariant auditing now participates in LangGraph routing before rendering. The `revision_router` no longer sends a validated draft directly to rendering; it routes through an `invariant_audit` node that writes `agentic_invariant_audit.json`, blocks with `invariant_audit_failed` when evidence gates fail, and only allows rendering when text/claim/evidence traceability passes. The runner still performs a final audit as a safety net, but the graph now treats evidence invariants as first-class routing signals rather than end-of-run bookkeeping.

## Current Fifteenth Step

The agentic graph now reaches final packaging. The legacy finalize stage is exposed as a canonical tool, and LangGraph routes `rendering -> finalize -> END` only when rendering has not blocked. Finalize writes the final TeX/PDF report/manifest through the existing Phase 8 packager, so the complete agentic path now covers input resolution through final method packaging while still passing through evidence freeze, validation, and invariant audit before rendering/finalization.

## Current Sixteenth Step

Agentic runs now emit the standard `run_manifest.json` in addition to `agentic_run_summary.json`. The manifest uses the existing reproducibility schema, hashes every recorded artifact, includes agentic validator reports such as `agentic_invariant_audit.json`, and records phase inputs for intake, evidence, authoring, validation, invariant audit, rendering, and finalize. This lets downstream tooling inspect agentic runs through the same manifest surface as deterministic `code2paper-run` executions while preserving the richer decision trace in the agentic summary.

## Current Seventeenth Step

Model-assisted decisioning now has a safe adapter layer. `coverage_decision_with_model` and `revision_decision_with_model` let a planner, critic, or router propose next steps through structured prompt payloads, while the system keeps measured coverage scores, artifact bindings, validation requirements, and evidence-return rules authoritative. This is the practical bridge from deterministic fallback logic to stronger LangChain/LangGraph agent behavior: the model can choose among safe routes, but it cannot route around frozen code evidence, claim verification, validation, or invariant audit.

## Current Eighteenth Step

The safe decisioning layer is now wired into LangGraph execution. `build_code2paper_graph` and `run_agentic_code2paper` accept an optional `decision_provider`; the coverage critic and revision router nodes call it through the evidence-safe merge layer before writing router decisions and updating graph state. A lightweight `build_langchain_decision_provider` adapter accepts any LangChain-style Runnable with `invoke()`, feeding it structured decision prompts and parsing dict/JSON/message outputs. Default runs remain deterministic, but real planner/critic chains can now steer retrieval rescans and revision routing without gaining permission to bypass evidence freeze, validation, or invariant audit.

## Current Nineteenth Step

Agentic routing can now be backed by the project's existing structured LLM runtime. `build_llm_decision_provider` wraps `LLMClient` with node-specific proposal schemas for the coverage critic and revision router, and `run_agentic_code2paper` automatically enables it when an agentic run explicitly configures an LLM provider or `CODE2PAPER_AGENTIC_DECISION_PROVIDER` requests model routing. Missing API keys, provider blocks, parse failures, or unsupported nodes return `None`, so the deterministic fallback remains the safety baseline while real LLM calls can propose retrieval rescans or revision routes.

## Current Twentieth Step

Invariant auditing now covers the final Method package. When `final_tex`, `final_pdf`, `final_pdf_report`, or `finalize_manifest` exists, `agentic_invariant_audit.json` requires a finalize manifest, verifies that the manifest's `text_tex` input is one of the registered audited authoring TeX artifacts, and checks that the final standalone TeX preserves the audited source body. This closes a post-validation gap: rendering and final packaging may wrap or compile method content, but they cannot silently replace evidence-traced Method prose with untracked text.

## Current Twenty-First Step

Agentic retrieval now indexes more than Python AST symbols. `agentic_symbol_index.json` includes config keys from YAML/JSON/TOML files and shell entrypoints/functions from scripts such as `.sh`, `.bash`, `.slurm`, and `.sbatch`, using the same author-intent path/symbol/query scoring as Python classes and functions. This improves targeted rescans for method details hidden in training configs, launch scripts, and experiment entrypoints while preserving the evidence-first flow: these candidates guide retrieval, but claims still require frozen evidence and validation before writing.

## Current Twenty-Second Step

Figure invariant auditing now validates evidence identities, not just evidence presence. `figure_evidence_plan` checks every node and edge evidence id against frozen `MethodEvidence`/`claim_evidence_map`, and rejects figure nodes that reference unknown, excluded, or unsupported claim ids. This closes a visual trust gap: method figures cannot pass the audit by carrying arbitrary-looking evidence labels; their visual elements must point back to real frozen code evidence.

## Current Twenty-Third Step

Agentic runs now emit an auditable LangChain-style tool catalog. `agentic_tool_catalog.json` records every canonical stage tool, its input/output artifacts, evidence policy, hard-gate status, and whether model decisions are allowed. The runner writes this catalog before invariant auditing, includes it in `agentic_run_summary.json`, and hashes it through the standard `run_manifest.json`, making the graph's available tools and evidence contracts reproducible artifacts rather than implicit Python definitions.

## Current Twenty-Fourth Step

Agentic runs now emit an auditable graph topology catalog. `agentic_graph_catalog.json` records the LangGraph entry point, direct edges, conditional router branches, terminal nodes, retrieval-loop budget binding, and evidence/validation gates such as frozen evidence, pre-render invariant audit, and evidence-backed figure planning. This makes orchestration reproducible alongside the tool catalog: model decisions may choose among documented safe routes, but the graph contract itself records that rendering must pass through invariant audit and cannot bypass claim verification.

## Current Twenty-Fifth Step

Model-assisted routing now emits auditable decision traces. Coverage critic and revision router nodes still write their final `*_decision.json` files, but they also write `*_decision_trace.json` with the structured prompt payload, deterministic fallback decision, model/provider payload when present, parsed proposal, final safety-merged decision, and notes describing any route rewrites. This lets the project use LangChain/LangGraph decision providers more freely while preserving a forensic record that model suggestions did not bypass evidence freeze, validation, invariant audit, or code-evidence traceability.

## Current Twenty-Sixth Step

Agentic runs now emit a positive evidence traceability ledger. `agentic_traceability_ledger.json` consolidates frozen claim bindings, paragraph-level text traces, and evidence-backed figure nodes/edges into one auditable map from paper-facing elements back to frozen code evidence ids. The invariant audit reads this ledger, and the runner includes it in summaries and manifests, so the core contract is visible in both directions: gates can reject unsupported output, and accepted text/figures carry a readable evidence ledger showing exactly which claims and visual elements trace to code evidence.

## Current Twenty-Seventh Step

Retrieval decisions now use a compact, auditable decision context. `agentic_retrieval_decision_context.json` summarizes retrieval coverage, weak targets, missing paths, high-scoring symbol/config/script candidates, and recommended rescan paths/symbols/queries for the coverage critic. The LangGraph coverage critic prompt receives this context, while the full retrieval plan, coverage report, and symbol index remain frozen artifacts. This improves the retrieval/ranking/summarization strategy without giving the model permission to invent evidence: it can choose targeted rescans from ranked candidates, but downstream evidence freeze and validators still decide which claims may be written.

## Current Twenty-Eighth Step

Authoring now has an explicit evidence-bound writing context. `agentic_authoring_context.json` combines the author's method goal and implementation scope with verified allowed claims, caveated partial claims, excluded unsupported claims, writing rules, negative scope, unsupported author parts, and the evidence ids available for safe prose. The legacy authoring bridge writes this context before Phase 5 and injects a compact brief into the authoring payload, so model writing is guided by author intent while still constrained by claim verification and frozen code evidence.

## Current Twenty-Ninth Step

The invariant audit now gates authored text on the evidence-bound authoring context. When Method text exists, `authoring_context_gate` requires `agentic_authoring_context.json`, verifies that writable allowed/caveated claims are not excluded or unsupported, checks that writable claims carry known frozen evidence ids, and ensures excluded/unsupported claims appear in the context exclusion list. This prevents future graph paths from producing Method prose with only raw constraints or text traces while bypassing the author-intent/evidence writing contract.

## Current Thirtieth Step

Revision routing now has a compact validator-aware decision context. `revision_decision_context.json` summarizes blocked reasons, validation manifest status, fidelity and QA issues, invariant audit failures, traceability ledger problems, recommended actions, and a safe recommended next node for the revision router. The LangGraph revision router prompt receives this context before model proposals are safety-merged, giving the model concrete validator evidence for choosing authoring vs. analysis vs. validation while preserving the existing rule that rendering cannot bypass validation or invariant audit.

## Current Thirty-First Step

The graph topology catalog now mirrors the newer runtime safety artifacts. `agentic_graph_catalog.json` records retrieval and revision decision contexts, decision trace outputs, the traceability ledger produced by invariant audit, and explicit gates for authoring context, revision context, pre-render traceability, and evidence-backed figures. This keeps the auditable graph contract aligned with the actual LangGraph runtime: contexts are not incidental files, but declared inputs/outputs and gates in the orchestration topology.

## Current Thirty-Second Step

Agentic runs now emit `agentic_run_readiness_report.json`, a run-level review contract over orchestration catalogs, frozen evidence, retrieval/revision decision contexts, router decision traces, authoring context, traceability ledger, invariant audit, and blocked status. The report is included in both `agentic_run_summary.json` and the standard `run_manifest.json`, giving CI or human review one machine-readable answer to "is this agentic run auditable and evidence-ready?" without weakening the existing invariant audit that keeps Method text and figures tied to verified code evidence.

## Current Thirty-Third Step

Agentic runs now emit `agentic_run_evaluation_report.json`, a benchmark-friendly single-run metric surface derived only from auditable artifacts. It records retrieval coverage, unsupported and partial claim rates, retrieval/revision loop counts, validation status, invariant audit status, readiness status, and traceability status, then recommends follow-up actions for weak coverage, unsupported claims, failed validators, or missing review contracts. This starts the evaluation phase of the refactor: fixed-pipeline and graph-agent runs can be compared on evidence coverage and trustworthiness, not just whether the generated prose sounds better.

## Current Thirty-Fourth Step

Agentic evaluation reports can now be aggregated into `agentic_benchmark_report.json` through the new `code2paper-agentic-benchmark` command or the unified `code2paper agentic-benchmark` subcommand. The benchmark report groups runs by variant, computes evidence coverage averages, unsupported/partial claim rates, pass rates for validation, invariant audit, readiness, and traceability, loop averages, missing metric counts, and risk flags, then chooses a current best variant with evidence-first scoring. This gives the project a concrete path for comparing fixed-pipeline and graph-agent experiments while ensuring variants with unsupported claims or traceability failures cannot win on prose quality alone.

## Current Thirty-Fifth Step

Agentic runs now emit `agentic_decision_policy.json`, an explicit policy contract for model-assisted graph decisions. The policy records hard rules, model-decision nodes, allowed and forbidden next nodes, required context artifacts, hard gate artifacts, and the requirement that model proposals pass through deterministic fallback and safety merge logic. Decision prompts now source their hard rules from this policy, and readiness/manifest outputs include it, making the agent's freedom auditable: models may steer retrieval and revision, but the recorded policy says exactly where they can act and which evidence, validation, and invariant gates remain non-negotiable.

## Current Thirty-Sixth Step

Agentic authoring now emits `agentic_authoring_plan.json`, a section-level Method writing plan derived from the evidence-bound authoring context. The plan includes only allowed and caveated verified claims, binds every planned section to claim ids and frozen evidence ids, records excluded claim ids, and carries caveat instructions for partial claims. The legacy Phase 5 bridge injects this plan into the authoring payload, readiness requires it when Method text exists, and invariant auditing blocks plans that omit evidence, reference unknown evidence, or use excluded/unsupported claims. This makes Method writing more agent-like without giving the model permission to invent structure outside verified code evidence.

## Current Thirty-Seventh Step

The Method writing plan is now a model-proposable but evidence-safety-merged decision. A new `authoring_planner` LangGraph node runs between grounding and authoring, writes `agentic_authoring_plan_decision_trace.json`, and lets a decision provider propose section headings, ordering, and grouping. The safety merge keeps only allowed/caveated verified claim ids, rewrites evidence ids to frozen code evidence, drops unsupported or unknown claims, and appends deterministic fallback sections for safe claims the model omitted. The tool catalog, graph catalog, decision policy, readiness report, invariant audit, run manifest inputs, and LLM decision provider all now recognize this node and trace, so model discretion has moved into writing structure without weakening the invariant that prose must be grounded in code evidence.

## Current Thirty-Eighth Step

Frozen evidence now has an agentic sufficiency critic before grounding. The graph runs `evidence_sufficiency` immediately after evidence freeze, writes `agentic_evidence_sufficiency_report.json`, `evidence_sufficiency_decision.json`, and `evidence_sufficiency_decision_trace.json`, and lets a model propose whether to proceed, return to analysis, or block. The safety merge only allows `grounding`, bounded `analysis` repair via `max_evidence_revision_rounds`, or `blocked`; grounding is rejected when there are no writable evidence-backed claims. Readiness, invariant audit, evaluation, benchmark aggregation, run manifests, graph catalog, decision policy, and the LLM decision provider now include this critic, making evidence sufficiency an explicit reviewable decision rather than an implicit side effect of claim verification.

## Current Thirty-Ninth Step

Evidence sufficiency repair is now actionable. When `evidence_sufficiency` routes back to analysis, the graph writes `agentic_evidence_repair_focus.json` with focus claim ids, weak claim queries, missing/unsupported claim groups, search keywords, and recommended repair actions. Phase 2 analysis receives this focus in its agent state and writes `analysis_repair_focus.json`; Phase 1 intake can also merge the same focus into retrieval hints if a future route returns to intake. Run manifests, graph catalogs, readiness checks, evaluation metrics, and benchmark aggregation now include the repair focus, so a model decision to "get more evidence" leaves a concrete handoff instead of a vague loop.

## Current Fortieth Step

Evidence repair focus now maps weak claims to ranked code candidates. When a symbol index is available, `agentic_evidence_repair_focus.json` includes `claim_targets` with candidate paths, symbols, line spans, scores, and ranking reasons derived from deterministic token matches over the existing symbol index. The graph passes `symbol_index` into evidence repair, Phase 2 analysis carries candidate paths/symbol targets into retrieval hints, and evaluation/benchmark reports count repair candidates in addition to weak claim ids. This makes bounded evidence repair more agentic and concrete while preserving the rule that candidates only suggest code to inspect; frozen evidence and validators still decide which claims may be written.

## Current Forty-First Step

Evidence repair candidates now become analysis repair tasks. When Phase 2 receives `agentic_evidence_repair_focus.json`, it writes `analysis_repair_tasks.json` with one task per weak claim, issue types, candidate file/symbol spans, ranking reasons, matched snippet ids, mapped evidence ids, and a deterministic next action such as `reassess_existing_evidence` or `rescan_candidate_code`. Intake overlays now preserve repair `search_keywords` and `claim_targets`, while the analysis tool contract and run summaries include `analysis_repair_tasks`. This tightens the repair loop: the model can decide from an explicit task sheet, but the task sheet is built from code snippets, symbol-index candidates, and evidence-index mappings rather than invented prose.

## Current Forty-Second Step

Analysis repair tasks now participate in run review and benchmark accounting. Readiness checks require `analysis_repair_tasks.json` whenever an evidence repair focus exists, and verify that every focus claim has a corresponding task with a candidate list. Single-run evaluation reports now count repair tasks, tasks already backed by existing evidence ids, and candidates already mapped to evidence; benchmark aggregation averages those fields and raises `repair_tasks_need_rescan` when repair tasks lack evidence-backed candidates. Run summaries also include `analysis_repair_tasks` in decisioning, readiness, and evaluation inputs. This makes the evidence repair loop auditable as a measurable agent behavior instead of an opaque retry.

## Current Forty-Third Step

Stage tools now have a stricter optional LangChain export path. `Code2PaperStageTool.to_langchain_tool()` adapts each canonical stage tool into a LangChain `StructuredTool` with an explicit `StageToolInvokeInput` schema carrying the serialized `AgenticRunState`, and `build_langchain_stage_tools()` exports an active registry as a list of structured tools. The adapter remains optional and raises the existing agentic-extra install guidance when `langchain_core` is unavailable, so deterministic runs and tests do not depend on LangChain. This makes the LangChain side of the refactor concrete without weakening the local evidence-gated tool contracts.

## Current Forty-Fourth Step

Analysis repair tasks now influence LangGraph routing. The graph routes `analysis -> analysis_repair_router` instead of jumping directly to evidence freeze; the router sends the run back to `intake` when repair tasks still need code candidates and retrieval budget remains, continues to `evidence` when candidates already map to evidence ids, and proceeds with caveats when the rescan budget is exhausted so evidence sufficiency can block unsafe claims. The graph catalog and decision policy now record this deterministic router and its allowed `intake|evidence|blocked` exits. This turns claim-level repair tasks into an actual graph decision while preserving the invariant that all writing still passes through evidence freeze, sufficiency review, and validators.

## Current Forty-Fifth Step

The analysis repair router now leaves an auditable decision artifact. `route_analysis_repair()` centralizes the deterministic routing policy in the routing layer, and the graph writes `analysis_repair_router_decision.json` with task counts, unbound task counts, retrieval round, budget, rationale, and the chosen next node. Readiness checks require this router decision whenever analysis repair tasks are present, and run summaries include it alongside other decisioning/readiness/evaluation inputs. This keeps the new repair-task route inspectable: a return to intake is now backed by a recorded task/budget decision rather than an implicit graph branch.

## Current Forty-Sixth Step

The analysis repair router is now model-proposable but safety-merged. `analysis_repair_decision_trace()` lets a decision provider propose `intake`, `evidence`, or `blocked`, writes `analysis_repair_router_decision_trace.json`, and records the prompt, deterministic fallback, provider payload, parsed proposal, final decision, and safety notes. The merge layer rejects unsafe next nodes, rewrites attempts to skip candidate rescans while unbound repair tasks still have retrieval budget, and refuses extra intake loops after the retrieval budget is exhausted. Graph catalog, decision policy, readiness checks, run manifests, and the LLM decision provider now recognize this trace, so the model can help decide repair routing without bypassing the code-evidence-first gate.

## Current Forty-Seventh Step

Retrieval now produces an explicit bounded rescan plan. `agentic_retrieval_rescan_plan.json` combines coverage gaps, ranked symbol/config/script candidates, and analysis repair tasks that still lack evidence ids into a next-pass retrieval queue with source, priority, query, path, symbol, target id or claim id, score, and ranking reasons. The legacy intake tool writes this artifact on every intake pass, can merge a previous rescan plan back into retrieval hints on the next bounded loop, and records rescan item counts in run evaluation and benchmark reports. Readiness now expects both `agentic_retrieval_decision_context.json` and `agentic_retrieval_rescan_plan.json` when retrieval coverage exists, making the retrieval/ranking strategy auditable without turning candidates into writable claims before evidence freeze.

## Current Forty-Eighth Step

The coverage critic now consumes the bounded rescan plan directly. `coverage_decision_trace()` accepts `RetrievalRescanPlan`, includes it in the structured decision prompt, and enriches deterministic fallback decisions with rescan-plan paths, symbols, and queries even when no model provider is configured. The LangGraph coverage critic node loads or builds `agentic_retrieval_rescan_plan.json` before routing, and graph/policy catalogs now declare it as coverage-critic context. This makes the model-facing retrieval queue operational in the actual decision path while preserving the same safety merge: rescan suggestions can only route to bounded intake, analysis, or blocked, and authoring still cannot occur before evidence freeze and validators.

## Current Forty-Ninth Step

Bounded rescans now have an auditable outcome report. `agentic_retrieval_rescan_report.json` evaluates each `RetrievalRescanPlan` item against the current intake snippets and snippet-to-evidence index, marking items as `covered` when they map to evidence ids, `partial` when snippets match without evidence ids, and `missing` when the current intake did not retrieve them. The legacy intake tool and LangGraph coverage critic can write this report, readiness requires it alongside retrieval coverage/context/rescan plan, and evaluation/benchmark reports now track rescan coverage, covered items, and missing items. This closes the retrieval feedback loop without weakening the core rule: rescan matches still become writable only after evidence freeze, claim verification, and validators approve them.

## Current Fiftieth Step

The coverage critic now consumes rescan outcomes, not only rescan plans. `coverage_decision_trace()` accepts `RetrievalRescanReport`, includes it in the structured model prompt, records it in final decision artifact keys, and enriches deterministic fallback rationales when bounded rescan items remain missing or only partially mapped to evidence ids. The LangGraph coverage critic node loads or builds the report before routing, while decision policy and graph catalog declare it as coverage-critic context. This gives model-assisted retrieval decisions feedback about whether previous bounded rescans actually found code evidence, while preserving the safety contract that any matched snippets still require evidence freeze, claim verification, and validation before writing.
