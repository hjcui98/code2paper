"""Autonomous Method Agent product runner (merged packages B + H).

This module is the product entry point of the autonomous Method Agent:

::

    repo + author intent + user claims
      -> research loop (research_graph / research_tools)
      -> evidence packets / code facts / atomic claims
      -> completeness matrix / typed gaps / research trace
      -> author-intent-first section plan + product readiness
      -> candidate / verified / review outputs (Writer surface)
      -> run summary + agent trace

The product path starts the research loop directly from the shared
``ResearchGraphRuntime`` / ``build_research_subgraph`` machinery.  It does
NOT use the R8 legacy bridge (``V3GraphWrapper`` /
``build_code2paper_v3_graph``), does NOT synthesize terminal gaps, and does
NOT depend on the D5 matrix runner.  Missing evidence is a typed gap or
review item, never a synthetic support.

The sequential product operations are exposed through the shared
``product_authoring_graph`` overlay and checkpoint; they remain adapters for
the existing owning implementations rather than a second content pipeline.

Shared product contracts come from ``method_product_models`` (Agent 1's P0
layer): lanes, review candidates, plan readiness, output policy.  This
module consumes them and never re-defines a parallel lane/readiness/review
schema.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.author_intent_summary import load_author_intent_summary
from code2paper.agentic.authoring_context_contract import (
    build_authoring_run_contract,
    build_run_identity,
    expected_authoring_artifact_keys,
    resolve_authoring_context_mode,
    write_authoring_run_contract,
    write_run_identity,
)
from code2paper.agentic.authoring_execution_identity import (
    PENDING_LEASE_OWNER,
    AuthoringExecutionIdentityV2,
    RunLease,
    RunOpenDecision,
    RunOpenRejected,
    acquire_run_lease,
    create_or_validate_execution_identity,
    preflight_run_open,
    resolve_open_identity,
    validate_run_open,
    verify_research_import,
)
from code2paper.agentic.authoring_projection import (
    build_authoring_projection,
    projected_writer_inputs,
)
from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.configuration_claims import compile_configuration_claims
from code2paper.agentic.equation_claims import (
    bind_equations_to_claims,
    compile_equation_claims,
    derive_equation_proposals_from_facts,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    CodeFactSetV1,
    EvidencePacketSetV3,
)
from code2paper.agentic.gemma_supervisor_backend import GemmaSupervisorBackend
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    IntentObligationV2,
    _build_typed_targets,
    _clean,
    _match_concepts,
    _retrieval_queries,
    _stable_id,
    build_story_spine_from_intent_graph,
    compile_intent_obligation_graph_v2,
)
from code2paper.agentic.intent_target_proposer import enrich_intent_graph_with_llm
from code2paper.agentic.research_revision_contract import (
    AuthorConstraintSetV1,
    build_author_constraint_set,
)
from code2paper.agentic.method_argument_models import (
    MethodCompletenessMatrixV1,
    build_completeness_matrix,
    build_reference_method_agenda,
)
from code2paper.agentic.method_architect import (
    build_method_section_plan_with_product_readiness,
)
from code2paper.agentic.method_product_models import (
    METHOD_EVIDENCE_LANES,
    AuthorStoryNodeV1,
    MethodEvidenceLane,
    MethodPlanProductReadinessV1,
    MethodPlanReadiness,
    MethodReviewCandidateV1,
    StoryNodeRoleV1,
    build_default_method_output_policy,
    build_review_candidates_from_completeness,
)
from code2paper.agentic.method_proposition_compiler import compile_method_propositions
from code2paper.agentic.method_proposition_evidence_provider import (
    build_method_proposition_evidence_judge,
)
from code2paper.agentic.method_proposition_provider import build_method_proposition_architect
from code2paper.agentic.method_concept_card_compiler import (
    compile_method_concept_cards,
)
from code2paper.agentic.method_concept_card_evidence_provider import (
    build_concept_card_evidence_judge,
)
from code2paper.agentic.method_concept_card_provider import (
    build_concept_card_architect,
)
from code2paper.agentic.method_argument_brief_compiler import compile_method_argument_briefs
from code2paper.agentic.method_argument_facet_aligner import (
    bind_facets_to_argument_briefs,
    decompose_and_align_argument_facets,
)
from code2paper.agentic.obligation_fact_alignment import (
    bind_claims_to_obligations,
    build_obligation_coverage_v2,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_graph import (
    CompiledEvidence,
    ResearchLoopResult,
    build_research_subgraph,
    initial_loop_state,
)
from code2paper.agentic.implementation_scope import scope_role_for_candidate
from code2paper.agentic.research_models import (
    CandidateAcquisitionLedgerV1,
    ResearchDecisionV1,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchObservationV1,
)
from code2paper.agentic.research_promotion import ObservationPromotionLedgerV1
from code2paper.agentic.research_policy import PolicyMergeResult
from code2paper.agentic.research_nodes import ResearchGraphRuntime
from code2paper.agentic.research_promotion import (
    promotion_record_blocks_strict_research,
    remap_promotion_ledger_claim_ids,
)
from code2paper.agentic.research_terminal import (
    CandidateHandoffV1,
    CandidateRetryLedgerV1,
    build_candidate_handoff,
    build_candidate_retry_ledger,
    build_research_closure_admission,
    evaluate_obligation_terminal_proof,
)
from code2paper.agentic.product_authoring_graph import (
    ProductAuthoringIssueV1,
    persist_product_authoring_state_from_writer,
)
from code2paper.agentic.state_v3 import empty_agent_state_v3
from code2paper.agentic.v3_runtime import (
    build_research_agenda_from_intent_graph,
    merge_compiled_evidence,
)
from code2paper.core.output_names import method_output
from code2paper.llm.providers import has_provider_api_key, load_llm_config_from_env
from code2paper.schemas import ClaimEvidenceMap, LLMConfig, MethodEvidence

PRODUCT_RESEARCH_READY_TOOLS: tuple[str, ...] = (
    "list_repository_tree",
    "find_entrypoints",
    "search_symbols",
    "search_code",
    "read_symbol",
    "read_code_span",
    "find_references",
    "build_behavior_subgraph",
    "trace_call_path",
    "trace_data_flow",
    "inspect_control_flow",
    "inspect_configuration",
    "propose_target_revision",
)

PRODUCT_RESEARCH_HARD_RULES: tuple[str, ...] = (
    "no_snapshot_external_paths",
    "no_unregistered_tools",
    "no_authority_upgrade",
    "no_skipped_validators",
    "no_duplicate_no_gain_calls",
    "obligation_must_exist",
    "budgets_must_be_available",
    "fallback_must_be_safe",
    "revision_proposal_is_not_acceptance",
)

CLAIM_PRIORITY_VALUES = ("must_cover", "should_cover", "preference")

_CLAIM_KIND_BY_PRIORITY = {
    "must_cover": "method_mainline",
    "should_cover": "component",
    "preference": "organization",
}


def _method_evidence_template(
    *,
    runtime: ResearchGraphRuntime,
    method_name: str = "",
) -> MethodEvidence:
    """Build the minimal writer template for V3 authoring projection.

    The product runner no longer has a legacy Phase-3 ``MethodEvidence``
    stage.  Projection still needs a template for stable project identity and
    author-facing method scope; positive implementation facts are filled only
    by ``projected_writer_inputs`` from compiler-verified V3 claims.
    """

    intent_graph = runtime.intent_graph
    project_root = str(runtime.repo_snapshot.project_root or "").strip()
    fallback_name = Path(project_root).name if project_root else "repository"
    resolved_method_name = (
        method_name.strip()
        or str(getattr(intent_graph, "method_name", "") or "").strip()
        or fallback_name
        or "Method"
    )
    method_goal = (
        str(getattr(intent_graph, "method_goal", "") or "").strip()
        or str(getattr(intent_graph, "project_goal", "") or "").strip()
        or "Describe the repository implementation."
    )
    implementation_scope = (
        str(getattr(intent_graph, "implementation_scope", "") or "").strip()
        or project_root
        or "current repository implementation"
    )
    entrypoints = [
        item.path
        for item in runtime.repo_snapshot.included_files[:12]
        if item.path.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c", ".h"))
    ]
    return MethodEvidence(
        project_id=runtime.repo_snapshot.snapshot_id,
        method_name=resolved_method_name,
        method_goal=method_goal,
        implementation_scope=implementation_scope,
        entrypoints=entrypoints,
        author_logic_priority=True,
        writing_constraints=[
            "Author intent may determine scope and organization, but only projected V3 claims authorize repository-positive prose.",
            "Unverified author intent, explicit gaps, external literature needs, and formalization needs must remain caveated or review-bound.",
        ],
    )


class UserClaimInputV1(BaseModel):
    """One user-supplied Method claim that seeds a research obligation.

    The claim text is author wording: it may become candidate/review
    material but is never a repository implementation fact by itself.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    text: str
    priority: Literal["must_cover", "should_cover", "preference"] = "should_cover"
    role: StoryNodeRoleV1 = "algorithm_step"
    lane: MethodEvidenceLane = "author_intent_unverified"
    notes: str = ""

    @field_validator("claim_id", "text")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        stripped = str(value).strip()
        if not stripped:
            raise ValueError("claim id and text must not be empty")
        return stripped


class UserClaimsInputV1(BaseModel):
    """Parsed ``--claims`` input file."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    claims: tuple[UserClaimInputV1, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _unique_ids(self) -> "UserClaimsInputV1":
        seen: set[str] = set()
        for claim in self.claims:
            if claim.claim_id in seen:
                raise ValueError(f"duplicate claim_id: {claim.claim_id}")
            seen.add(claim.claim_id)
        return self


class TypedResearchGapV1(BaseModel):
    """One typed research gap with a stopping reason (never synthetic).

    ``status`` distinguishes an obligation the loop formally accepted as
    ``explicit_gap`` from one that stayed ``unresolved`` when the loop
    stopped (budget, blocked) — the two must never be conflated.
    """

    model_config = ConfigDict(extra="forbid")

    gap_id: str
    obligation_id: str
    status: Literal["explicit_gap", "unresolved", "blocked"]
    reason: str
    attempted_tools: tuple[str, ...] = Field(default_factory=tuple)
    search_scope: tuple[str, ...] = Field(default_factory=tuple)
    missing_relations: tuple[str, ...] = Field(default_factory=tuple)
    stopping_reason: str = ""
    lane: MethodEvidenceLane = "author_intent_unverified"
    trace_refs: tuple[str, ...] = Field(default_factory=tuple)


class MethodAgentRunResultV1(BaseModel):
    """Durable result of one autonomous Method Agent product run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    run_id: str
    repo_path: str
    out_root: str
    research_status: str = ""
    research_termination_reason: str = ""
    research_turns: int = 0
    plan_built: bool = False
    plan_readiness: MethodPlanReadiness = "candidate_ready_with_review"
    plan_blocked_reasons: tuple[str, ...] = Field(default_factory=tuple)
    writer_status: str = "skipped_no_live_llm"
    writer_blocked_reason: str = ""
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodAgentRunResultV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


def load_user_claims(path: str | Path | None) -> UserClaimsInputV1:
    """Load and validate a ``--claims`` JSON file (or an empty input)."""
    if not path:
        return UserClaimsInputV1()
    claims_path = Path(path)
    if not claims_path.is_file():
        raise FileNotFoundError(f"claims file not found: {claims_path}")
    try:
        payload = json.loads(claims_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"claims file is not valid JSON: {claims_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("claims file must be a JSON object")
    return UserClaimsInputV1.model_validate(payload)


def append_claims_to_intent_graph(
    intent_graph: IntentObligationGraphV2,
    claims: UserClaimsInputV1,
    *,
    project_root: str | Path,
) -> IntentObligationGraphV2:
    """Turn user claims into typed obligations without touching the originals.

    Each claim reuses the deterministic intent-compiler concept matching so
    the research loop treats it exactly like an author obligation.  The
    returned graph is a fresh instance with a recomputed content digest.
    """

    if not claims.claims:
        return intent_graph
    existing_ids = {item.obligation_id for item in intent_graph.obligations}
    obligations: list[IntentObligationV2] = list(intent_graph.obligations)
    for index, claim in enumerate(claims.claims):
        obligation_id = _stable_id("claim", claim.claim_id)
        if obligation_id in existing_ids:
            continue
        existing_ids.add(obligation_id)
        clean = _clean(claim.text)
        concepts = _match_concepts(clean)
        targets = _build_typed_targets(
            obligation_id=obligation_id,
            author_text=clean,
            concepts=concepts,
            organization_preference=clean if claim.priority == "preference" else "",
        )
        obligations.append(IntentObligationV2(
            obligation_id=obligation_id,
            kind=_CLAIM_KIND_BY_PRIORITY[claim.priority],  # type: ignore[arg-type]
            priority=claim.priority,  # type: ignore[arg-type]
            source_field="user_claims",
            source_index=index,
            author_text=clean,
            typed_behavior_targets=tuple(targets),
            retrieval_queries=_retrieval_queries(clean, concepts),
            candidate_paths=(),
        ))
    return IntentObligationGraphV2(
        schema_version=intent_graph.schema_version,
        mode=intent_graph.mode,
        project_goal=intent_graph.project_goal,
        method_goal=intent_graph.method_goal,
        implementation_scope=intent_graph.implementation_scope,
        obligations=obligations,
        relations=list(intent_graph.relations),
    )


def build_product_research_runtime(
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None,
    claims: UserClaimsInputV1 | None,
    run_id: str,
    llm_config: LLMConfig | None = None,
    artifact_root: str | Path | None = None,
    ready_tools: tuple[str, ...] = PRODUCT_RESEARCH_READY_TOOLS,
    hard_rules: tuple[str, ...] = PRODUCT_RESEARCH_HARD_RULES,
    intent_graph_override: IntentObligationGraphV2 | None = None,
    agenda_override: ResearchAgendaV1 | None = None,
    author_constraints_override: Any | None = None,
) -> ResearchGraphRuntime:
    """Build the research runtime directly from repo + intent + claims.

    This is the product path: no legacy bridge, no execution-profile
    routing, no synthetic artifacts.  The supervisor is
    ``GemmaSupervisorBackend`` when an LLM is configured and available;
    otherwise the runtime falls back to the deterministic supervisor
    (``ResearchGraphRuntime.supervisor()``).
    """

    resolved_root = Path(repo_path).expanduser().resolve()
    if not resolved_root.is_dir():
        raise FileNotFoundError(f"repo path not found: {resolved_root}")
    repo_snapshot = build_repo_snapshot(resolved_root)

    effective_llm = llm_config or load_llm_config_from_env()
    if intent_graph_override is not None:
        intent_graph = intent_graph_override
        proposal_report_payload: dict[str, Any] = {
            "status": "resumed_from_research_stage_checkpoint",
        }
        # A resumed graph is already enriched: without the checkpoint's frozen
        # set there is no author authority to restore, and inventing one from
        # the enriched graph would be a false claim.
        author_constraints = (
            author_constraints_override
            or build_author_constraint_set(intent_graph)
        )
    else:
        intent_summary = None
        if author_intent_path:
            intent_path = Path(author_intent_path)
            if not intent_path.is_file():
                raise FileNotFoundError(f"author intent file not found: {intent_path}")
            intent_summary = load_author_intent_summary(intent_path)
        intent_graph = compile_intent_obligation_graph_v2(intent_summary)
        if claims is not None and claims.claims:
            intent_graph = append_claims_to_intent_graph(
                intent_graph,
                claims,
                project_root=resolved_root,
            )
        # R10 §15.1: freeze the author boundary *before* enrichment replaces the
        # deterministic targets.  Everything downstream (revision assessment,
        # coverage denominator, checkpoint/resume) reads this frozen set instead
        # of rebuilding author authority from the mutable graph.
        author_constraints = (
            author_constraints_override
            or build_author_constraint_set(intent_graph)
        )
        intent_graph, proposal_report = enrich_intent_graph_with_llm(
            intent_graph,
            effective_llm,
        )
        proposal_report_payload = proposal_report.model_dump(mode="json")

    agenda = agenda_override or build_research_agenda_from_intent_graph(
        intent_graph,
        run_id=run_id,
        repo_snapshot=repo_snapshot,
    )
    if agenda.run_id != run_id:
        raise ValueError("research agenda run id does not match runtime")
    if (
        agenda.repo_snapshot_id != repo_snapshot.snapshot_id
        or agenda.project_tree_hash != repo_snapshot.project_tree_hash
    ):
        raise ValueError("research agenda snapshot identity does not match runtime")

    supervisor_backend = GemmaSupervisorBackend(
        llm_config=effective_llm,
        run_id=run_id,
        repo_snapshot_id=repo_snapshot.snapshot_id,
        ready_tools=ready_tools,
        hard_rules=hard_rules,
    )

    return ResearchGraphRuntime(
        run_id=run_id,
        repo_snapshot=repo_snapshot,
        agenda=agenda,
        intent_graph=intent_graph,
        author_constraints=(
            author_constraints if author_constraints.obligations else None
        ),
        intent_target_proposal_report=proposal_report_payload,
        supervisor_backend=supervisor_backend,
        artifact_root=(
            Path(artifact_root).expanduser().resolve() if artifact_root else None
        ),
        ready_tools=ready_tools,
        hard_rules=hard_rules,
    )


def run_product_research_phase(
    runtime: ResearchGraphRuntime,
    *,
    max_turns: int = 30,
    max_wall_clock_seconds: float | None = None,
) -> ResearchLoopResult:
    """Run the research subgraph to termination (direct product path)."""

    if max_turns < 1:
        raise ValueError("max_research_turns must be at least 1")
    initial = empty_agent_state_v3(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    )
    subgraph = build_research_subgraph(
        runtime,
        max_turns=max_turns,
        max_wall_clock_seconds=max_wall_clock_seconds,
    )
    subgraph.invoke(initial.to_state_dict(), config=None)
    result = subgraph.last_result
    if result is None:
        raise RuntimeError("research subgraph did not produce a ResearchLoopResult")
    return result


def _research_run_state(
    result: ResearchLoopResult,
    runtime: ResearchGraphRuntime,
) -> dict[str, Any]:
    """Return the honest product status of the repository research loop.

    Graph termination only means execution stopped.  It does not mean that
    the research succeeded: max-turn exhaustion, policy stops and a silent
    deterministic compatibility fallback are materially different states.
    """

    final_status = str(result.final_state.get("status") or "incomplete")
    backend = runtime.supervisor_backend
    degraded_events = tuple(getattr(backend, "degraded_events", ()))
    llm_decisions = max(
        int(getattr(backend, "llm_decision_count", 0)),
        sum(
            1
            for decision in result.decision_trace
            if decision.produced_by == "llm_proposal"
        ),
    )
    deterministic_decisions = sum(
        1
        for decision in result.decision_trace
        if decision.produced_by == "deterministic_fallback"
    )
    policy_fallbacks = sum(
        1 for merge in result.loop_state.policy_merge_trace if merge.fallback_used
    )
    degraded_reasons = list(degraded_events)
    if policy_fallbacks:
        degraded_reasons.append(f"policy_fallback:{policy_fallbacks}")
    autonomous = (
        llm_decisions > 0
        and deterministic_decisions == 0
        and not degraded_reasons
    )
    if result.termination_reason == "max_turns_reached":
        final_status = "incomplete"
    elif final_status == "trusted" and not autonomous:
        # Evidence remains usable, but the product must not claim that an
        # autonomous Research Agent completed the work when it actually ran
        # through scripted fallback decisions.
        final_status = "degraded"
    return {
        "status": final_status,
        "autonomous": autonomous,
        "llm_decisions": llm_decisions,
        "deterministic_fallback_decisions": deterministic_decisions,
        "policy_fallback_decisions": policy_fallbacks,
        "degraded_reasons": list(dict.fromkeys(degraded_reasons)),
    }


def _candidate_handoff_from_loop(
    loop_result: ResearchLoopResult,
) -> CandidateHandoffV1 | None:
    """Load the scheduler's authenticated Candidate handoff, if eligible."""

    payload = (
        loop_result.loop_state.intent_schedule.get("candidate_handoff")
        if isinstance(loop_result.loop_state.intent_schedule, dict)
        else None
    )
    if not isinstance(payload, dict):
        return None
    try:
        handoff = CandidateHandoffV1.model_validate(payload)
    except (TypeError, ValueError):
        return None
    return handoff


def _proposal_accounting_summary(paths: Mapping[str, Any]) -> dict[str, Any]:
    """Return the run-summary keys for a measured proposal-call tally.

    No measured tally means no keys: a run must not claim metering it never
    performed, and a missing/corrupt artifact is not a reason to fail a run.
    """

    path_value = str(paths.get("proposal_call_accounting_v1") or "")
    if not path_value:
        return {}
    try:
        from code2paper.agentic.proposal_call_accounting import (
            load_proposal_call_accounting,
        )

        accounting = load_proposal_call_accounting(path_value)
    except Exception:  # noqa: BLE001 - accounting is evidence, not a gate
        return {}
    return {
        "proposal_call_accounting": accounting.totals(),
        "proposal_call_accounting_digest": accounting.content_digest,
    }


def _run_revision_state(
    loop_result: ResearchLoopResult,
    runtime: ResearchGraphRuntime,
    *,
    previous: Any | None = None,
) -> tuple[Any, Any]:
    """Return this run's applied-revision journal and its checkpoint binding.

    §15.6: the journal is the authority for which targets the run's evidence
    was produced under.  A run that applied no revision keeps an empty journal
    and no binding, which is exactly the pre-R10 state.
    """

    from code2paper.agentic.research_revision_contract import (
        RevisionJournalV1,
        bind_research_revision,
    )

    journal = getattr(loop_result, "revision_journal", None)
    if journal is None or not getattr(journal, "entries", ()):
        journal = previous if previous is not None else RevisionJournalV1()
    if not getattr(journal, "entries", ()):
        return journal, None
    binding = bind_research_revision(
        journal=journal,
        graph=getattr(runtime, "intent_graph", None),
        agenda=getattr(runtime, "agenda", None),
        coverage_denominator_ids=journal.entries[-1].coverage_denominator_ids,
    )
    return journal, binding


def _candidate_retry_ledger_for_run(
    loop_result: ResearchLoopResult,
    runtime: ResearchGraphRuntime,
) -> CandidateRetryLedgerV1:
    """Build the frozen retry ledger once for both handoff and persistence."""

    loop = loop_result.loop_state
    retry_gain_by_obligation: dict[str, bool | None] = {}
    for event in loop.intent_compile_events or ():
        obligation_id = str(event.get("obligation_id") or "").strip()
        if not obligation_id:
            continue
        if int((loop.post_partial_retry_counts or {}).get(obligation_id, 0) or 0) < 1:
            continue
        retry_gain_by_obligation[obligation_id] = bool(
            event.get("has_coverage_gain", False)
        )
    return build_candidate_retry_ledger(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        post_partial_retry_counts=loop.post_partial_retry_counts,
        semantic_gain_by_obligation=retry_gain_by_obligation,
    )


def _rebuild_candidate_handoff_from_product_claims(
    *,
    loop_result: ResearchLoopResult,
    runtime: ResearchGraphRuntime,
    claim_id_map: dict[str, str],
    claim_set: AtomicClaimSetV3 | None,
    previous: CandidateHandoffV1 | None,
    retry_ledger: CandidateRetryLedgerV1,
    revision_id: str = "",
) -> CandidateHandoffV1 | None:
    """Freeze the Candidate lane against the merged product claim identities.

    The loop's handoff is built from per-obligation compiled claims.  Product
    evidence merges duplicate claims and remaps claim ids, so persisting the
    loop handoff unchanged makes the Writer's independent revalidation fail
    with an identity mismatch even when the Candidate evidence is intact.
    Re-key the promotion lineage first and rebuild the handoff from the
    merged claim set; the rebuilt handoff is what gets persisted and
    revalidated, so the Candidate lane stays reproducible rather than
    accidentally open.
    """

    if previous is None or claim_set is None:
        return previous
    loop = loop_result.loop_state
    ledger = getattr(loop, "observation_promotion_ledger", None)
    if ledger is not None:
        ledger = remap_promotion_ledger_claim_ids(ledger, claim_id_map)
        loop.observation_promotion_ledger = ledger
    claims_by_obligation: dict[str, tuple[Any, ...]] = {}
    for claim in claim_set.claims:
        for obligation_id in claim.covers_obligation_ids or ():
            key = str(obligation_id)
            claims_by_obligation[key] = (*claims_by_obligation.get(key, ()), claim)
    return build_candidate_handoff(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        agenda_items=tuple(runtime.agenda.items),
        promotion_records=tuple(getattr(ledger, "records", ()) or ()),
        compiled_claims_by_obligation=claims_by_obligation,
        post_partial_retry_counts=loop.post_partial_retry_counts,
        retry_gain_by_obligation=retry_ledger.semantic_gain_by_obligation,
        structural_failure_codes=previous.structural_failure_codes,
        agenda_digest=runtime.agenda.refresh_content_digest(),
        promotion_ledger_digest=str(getattr(ledger, "content_digest", "") or ""),
        retry_ledger_digest=retry_ledger.content_digest,
        # R10 §15.6: a handoff built under a previous revision must not be
        # reusable once the run revised its targets.
        revision_id=revision_id,
    )


def _research_closure_failure_codes(
    *,
    loop_result: ResearchLoopResult,
    runtime: ResearchGraphRuntime,
    research_run_state: Mapping[str, Any],
    packet_set: EvidencePacketSetV3 | None,
    fact_set: CodeFactSetV1 | None,
    claim_set: AtomicClaimSetV3 | None,
) -> tuple[str, ...]:
    """Return typed failures for the Research -> authoring boundary.

    This gate is intentionally independent of plan/readiness.  A plan can be
    organized from author intent while the repository closure is still
    incomplete; that must not authorize any model-backed authoring request.
    """

    failures: list[str] = []
    status = str(research_run_state.get("status") or "incomplete")
    if status != "trusted":
        failures.append(f"research_status:{status}")

    loop = loop_result.loop_state
    promotion_records = tuple(
        getattr(getattr(loop, "observation_promotion_ledger", None), "records", ())
        or ()
    )
    compiled_by_obligation = getattr(loop, "compiled_evidence", {}) or {}
    for item in runtime.agenda.items:
        if item.priority != "must_cover":
            continue
        compiled = compiled_by_obligation.get(str(item.obligation_id))
        promoted_claim_ids = tuple(
            str(getattr(claim, "claim_id", "") or "")
            for claim in (
                getattr(getattr(compiled, "claim_set", None), "claims", ()) or ()
            )
            if str(getattr(claim, "claim_id", "") or "")
        )
        item_records = tuple(
            record
            for record in promotion_records
            if str(getattr(record, "obligation_id", "") or "")
            == str(item.obligation_id)
        )
        proof = evaluate_obligation_terminal_proof(
            item,
            promotion_records=item_records,
            promoted_claim_ids=promoted_claim_ids,
        )
        if proof.terminal:
            continue
        attempted = bool(item.attempted_actions or item_records)
        if not attempted:
            failures.append(f"unified_core_intent_unsearched:{item.obligation_id}")
        else:
            failures.append(
                "unified_core_intent_terminal_proof_missing:"
                f"{item.obligation_id}"
            )

    for record in promotion_records:
        if not promotion_record_blocks_strict_research(record):
            continue
        failures.append(
            "unified_observation_promotion_incomplete:"
            f"{getattr(record, 'observation_id', '')}"
        )

    missing_evidence: list[str] = []
    if packet_set is None or not packet_set.packets:
        missing_evidence.append("evidence_packets_v3")
    if fact_set is None or not fact_set.facts:
        missing_evidence.append("code_facts_v1")
    if claim_set is None or not claim_set.claims:
        missing_evidence.append("atomic_claims_v3")
    if missing_evidence:
        failures.append("research_evidence_missing:" + ",".join(missing_evidence))
    return tuple(dict.fromkeys(failures))


def merge_product_evidence(
    result: ResearchLoopResult,
    runtime: ResearchGraphRuntime,
    *,
    claim_id_map: dict[str, str] | None = None,
) -> tuple[EvidencePacketSetV3 | None, CodeFactSetV1 | None, AtomicClaimSetV3 | None]:
    """Aggregate the loop's per-obligation compiled evidence.

    ``merge_compiled_evidence`` is a pure aggregation adapter (dedupe by
    canonical identity, remap stage groups); no synthetic gaps are added.
    Claims are then bound to typed obligations through their fact IDs.  When
    ``claim_id_map`` is supplied it receives the per-input-claim to canonical
    id mapping so the Candidate handoff can freeze the same identities the
    product persists.
    """

    compiled = getattr(result.loop_state, "compiled_evidence", {})
    if not compiled:
        return None, None, None
    packet_set, fact_set, claim_set = merge_compiled_evidence(
        compiled,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        claim_id_map=claim_id_map,
    )
    if (
        fact_set is not None
        and claim_set is not None
        and getattr(runtime, "intent_graph", None) is not None
    ):
        claim_set = bind_claims_to_obligations(
            runtime.intent_graph,
            fact_set=fact_set,
            claim_set=claim_set,
        )
    return packet_set, fact_set, claim_set


def persist_research_stage_checkpoint(
    *,
    out_root: str | Path,
    runtime: ResearchGraphRuntime,
    claims_input: UserClaimsInputV1,
    loop_result: ResearchLoopResult,
    packet_set: EvidencePacketSetV3 | None,
    fact_set: CodeFactSetV1 | None,
    claim_set: AtomicClaimSetV3 | None,
    revision_binding: Any | None = None,
    revision_journal: Any | None = None,
    candidate_handoff: CandidateHandoffV1 | None = None,
) -> str:
    """Commit completed repository research before any planning model call.

    Proposition synthesis, semantic judging, or Writer transport may fail
    independently of repository research.  Persisting this compact stage
    boundary lets a later run continue from the exact frozen evidence rather
    than repeating code searches to obtain another sample.
    """

    root = Path(out_root).expanduser().resolve()
    path = root / "artifacts" / "research_product" / "research_stage_checkpoint_v1.json"
    final_schedule = dict(loop_result.loop_state.intent_schedule or {})
    loop_state = loop_result.loop_state
    source_authoring_identity = None
    if all(
        getattr(loop_state, field_name, None) is not None
        for field_name in (
            "symbol_index",
            "source_manifest",
            "implementation_scope",
            "behavior_graph",
        )
    ):
        from code2paper.agentic.repository_authoring_artifacts import (
            repository_authoring_identity_payload,
        )

        source_authoring_identity = repository_authoring_identity_payload(
            snapshot=runtime.repo_snapshot,
            symbol_index=loop_state.symbol_index,
            implementation_scope=loop_state.implementation_scope,
            source_manifest=loop_state.source_manifest,
        )
    payload = {
        "schema_version": "1.0",
        "run_id": runtime.run_id,
        "repo_snapshot_id": runtime.repo_snapshot.snapshot_id,
        "project_tree_hash": runtime.repo_snapshot.project_tree_hash,
        "intent_graph": runtime.intent_graph.model_dump(mode="json"),
        "agenda": runtime.agenda.model_dump(mode="json"),
        "claims_input": claims_input.model_dump(mode="json"),
        "termination": {
            "turns_executed": loop_result.turns_executed,
            "terminated": loop_result.terminated,
            "termination_reason": loop_result.termination_reason,
            "final_status": str(loop_result.final_state.get("status") or "incomplete"),
        },
        # Keep the scheduler's legal-action verdict at the checkpoint top
        # level so a resumed run cannot read a stale ``can_continue`` while
        # every per-obligation budget is exhausted.
        "can_continue": bool(final_schedule.get("can_continue", False))
        and not bool(loop_result.terminated),
        "can_terminate": bool(final_schedule.get("can_terminate", False)),
        "budget_constrained": bool(final_schedule.get("budget_constrained", False)),
        "legal_action_available": bool(
            final_schedule.get("legal_action_available", True)
        ),
        "decision_trace": [
            item.model_dump(mode="json") for item in loop_result.decision_trace
        ],
        "policy_merge_trace": [
            item.model_dump(mode="json") for item in loop_result.policy_merge_trace
        ],
        "recent_observations": [
            item.model_dump(mode="json")
            for item in loop_result.loop_state.recent_observations
        ],
        "evidence_packets": (
            packet_set.model_dump(mode="json") if packet_set is not None else None
        ),
        "code_facts": (
            fact_set.model_dump(mode="json") if fact_set is not None else None
        ),
        "atomic_claims": (
            claim_set.model_dump(mode="json") if claim_set is not None else None
        ),
        # The source-authority closure is part of the Research stage boundary,
        # not a best-effort Writer sidecar.  Persist it inline so a checkpoint
        # can be resumed in a different output root without rebuilding source
        # partitions from an already-enriched graph.  Older checkpoints are
        # handled by the sibling-artifact compatibility path in the loader.
        "behavior_graph": (
            loop_state.behavior_graph.model_dump(mode="json")
            if getattr(loop_state, "behavior_graph", None) is not None
            else None
        ),
        "symbol_index": (
            loop_state.symbol_index.model_dump(mode="json")
            if getattr(loop_state, "symbol_index", None) is not None
            else None
        ),
        "source_manifest": (
            loop_state.source_manifest.model_dump(mode="json")
            if getattr(loop_state, "source_manifest", None) is not None
            else None
        ),
        "implementation_scope": (
            loop_state.implementation_scope.model_dump(mode="json")
            if getattr(loop_state, "implementation_scope", None) is not None
            else None
        ),
        "repository_authoring_artifacts_v1": source_authoring_identity,
        "research_state": _research_run_state(loop_result, runtime),
        "intent_schedule": final_schedule,
        "post_partial_retry_counts": dict(
            loop_result.loop_state.post_partial_retry_counts or {}
        ),
        # The Candidate handoff is authenticated against the promotion
        # lineage.  Keep both ledgers at the Research checkpoint boundary so
        # a normal-entry resume can rebuild the handoff without treating a
        # missing ledger as an empty one.
        "candidate_acquisition_ledger": (
            loop_result.loop_state.candidate_acquisition_ledger.model_dump(
                mode="json"
            )
            if getattr(loop_result.loop_state, "candidate_acquisition_ledger", None)
            is not None
            and hasattr(
                loop_result.loop_state.candidate_acquisition_ledger,
                "model_dump",
            )
            else None
        ),
        "observation_promotion_ledger": (
            loop_result.loop_state.observation_promotion_ledger.model_dump(
                mode="json"
            )
            if getattr(loop_result.loop_state, "observation_promotion_ledger", None)
            is not None
            and hasattr(
                loop_result.loop_state.observation_promotion_ledger,
                "model_dump",
            )
            else None
        ),
        "candidate_handoff": (
            candidate_handoff.model_dump(mode="json")
            if candidate_handoff is not None
            else (
                loop_result.loop_state.intent_schedule.get("candidate_handoff")
                if isinstance(loop_result.loop_state.intent_schedule, dict)
                else None
            )
        ),
        # R10 §15.6: the revision identity a resume must agree with.  Absent
        # for a run that never revised its targets.
        "research_revision_binding_v1": (
            revision_binding.model_dump(mode="json")
            if revision_binding is not None else None
        ),
        "revision_journal": (
            revision_journal.model_dump(mode="json")
            if revision_journal is not None and revision_journal.entries
            else None
        ),
        "revision_ingest_outcomes": list(
            getattr(loop_result, "revision_ingest_outcomes", ()) or ()
        ),
        "revision_ingest_failures": list(
            getattr(loop_result, "revision_ingest_failures", ()) or ()
        ),
        # §15.1: the author boundary is frozen before enrichment and travels
        # with the run; a resume must restore the same boundary, not re-derive
        # one from the already-enriched graph.
        "author_constraints_v1": (
            runtime.author_constraints.model_dump(mode="json")
            if getattr(runtime, "author_constraints", None) is not None
            else None
        ),
        "author_constraints_digest": str(
            getattr(
                getattr(runtime, "author_constraints", None),
                "content_digest",
                "",
            )
            or ""
        ),
    }
    _atomic_write_text(path, _json_text(payload))
    return str(path)


def load_research_stage_checkpoint(
    *,
    path: str | Path,
    runtime: ResearchGraphRuntime,
    revision_journal: Any | None = None,
) -> tuple[
    ResearchLoopResult,
    EvidencePacketSetV3 | None,
    CodeFactSetV1 | None,
    AtomicClaimSetV3 | None,
    UserClaimsInputV1,
]:
    """Authenticate and restore the product research-stage boundary."""

    from code2paper.agentic.research_revision_contract import RevisionJournalV1

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if str(payload.get("run_id") or "") != runtime.run_id:
        raise ValueError("research_stage_checkpoint_run_id_mismatch")
    if str(payload.get("repo_snapshot_id") or "") != runtime.repo_snapshot.snapshot_id:
        raise ValueError("research_stage_checkpoint_snapshot_mismatch")
    if str(payload.get("project_tree_hash") or "") != runtime.repo_snapshot.project_tree_hash:
        raise ValueError("research_stage_checkpoint_tree_hash_mismatch")
    checkpoint_intent = payload.get("intent_graph") or {}
    # R10 added target provenance and the graph-level target identity digest.
    # These are deterministic schema-derived fields: old checkpoints do not
    # contain them, while the current Pydantic model materializes them on
    # load.  Compare after this narrow, in-memory migration so a valid legacy
    # checkpoint remains reusable without rewriting its bytes or accepting
    # changes to any persisted field that carries research meaning.
    checkpoint_intent_model = IntentObligationGraphV2.model_validate(
        checkpoint_intent
    )
    comparable_checkpoint_intent = deepcopy(checkpoint_intent)
    comparable_checkpoint_intent.setdefault(
        "target_identity_digest",
        checkpoint_intent_model.target_identity_digest,
    )
    for raw_obligation, normalized_obligation in zip(
        comparable_checkpoint_intent.get("obligations") or (),
        checkpoint_intent_model.obligations,
    ):
        for raw_target, normalized_target in zip(
            raw_obligation.get("typed_behavior_targets") or (),
            normalized_obligation.typed_behavior_targets,
        ):
            if "provenance" not in raw_target:
                raw_target["provenance"] = normalized_target.provenance
    if comparable_checkpoint_intent != runtime.intent_graph.model_dump(mode="json"):
        raise ValueError("research_stage_checkpoint_intent_mismatch")
    checkpoint_agenda = ResearchAgendaV1.model_validate(payload.get("agenda") or {})
    checkpoint_constraints = payload.get("author_constraints_v1")
    runtime_constraints = getattr(runtime, "author_constraints", None)
    if checkpoint_constraints and runtime_constraints is not None:
        from code2paper.agentic.research_revision_contract import (
            AuthorConstraintSetV1,
        )

        restored_constraints = AuthorConstraintSetV1.model_validate(
            checkpoint_constraints
        )
        if restored_constraints.content_digest != runtime_constraints.content_digest:
            raise ValueError(
                "research_stage_checkpoint_author_constraints_mismatch"
            )
    binding_payload = payload.get("research_revision_binding_v1")
    if binding_payload and revision_journal is not None:
        # R10 §15.6: a checkpoint bound to another revision (or whose journal
        # already holds the revision it wants to apply) must not resume.  The
        # binding is checked against the *checkpoint's* objects, which are what
        # this call is about to install.
        from code2paper.agentic.research_revision_contract import (
            ResearchRevisionBindingV1,
            revision_resume_failures,
        )

        binding = ResearchRevisionBindingV1.model_validate(binding_payload)
        failures = revision_resume_failures(
            binding=binding,
            journal=revision_journal,
            graph=runtime.intent_graph,
            agenda=checkpoint_agenda,
        )
        if failures:
            raise ValueError(
                "research_stage_checkpoint_revision_stale:"
                + ";".join(failures)
            )
    runtime.agenda.items[:] = checkpoint_agenda.items
    packet_set = (
        EvidencePacketSetV3.model_validate(payload["evidence_packets"])
        if payload.get("evidence_packets") is not None else None
    )
    fact_set = (
        CodeFactSetV1.model_validate(payload["code_facts"])
        if payload.get("code_facts") is not None else None
    )
    claim_set = (
        AtomicClaimSetV3.model_validate(payload["atomic_claims"])
        if payload.get("atomic_claims") is not None else None
    )
    loop = initial_loop_state(runtime)
    if packet_set is not None and fact_set is not None and claim_set is not None:
        obligation_id = (
            runtime.agenda.items[0].obligation_id
            if len(runtime.agenda.items) == 1 else "research-stage-aggregate"
        )
        loop.compiled_evidence[obligation_id] = CompiledEvidence(
            obligation_id=obligation_id,
            packet_set=packet_set,
            fact_set=fact_set,
            claim_set=claim_set,
        )
    loop.recent_observations = [
        ResearchObservationV1.model_validate(item)
        for item in payload.get("recent_observations") or ()
    ]
    loop.decision_trace = [
        ResearchDecisionV1.model_validate(item)
        for item in payload.get("decision_trace") or ()
    ]
    loop.policy_merge_trace = [
        PolicyMergeResult.model_validate(item)
        for item in payload.get("policy_merge_trace") or ()
    ]
    terminal = payload.get("termination") or {}
    loop.turn_index = int(terminal.get("turns_executed") or 0)
    loop.terminated = bool(terminal.get("terminated"))
    loop.termination_reason = str(terminal.get("termination_reason") or "")
    loop.intent_schedule = dict(payload.get("intent_schedule") or {})
    loop.post_partial_retry_counts = {
        str(key): max(0, int(value or 0))
        for key, value in (payload.get("post_partial_retry_counts") or {}).items()
        if str(key).strip()
    }

    def _checkpoint_ledger_payload(
        key: str,
        filename: str,
    ) -> Any | None:
        """Read a ledger embedded in the checkpoint or its legacy sibling."""

        embedded = payload.get(key)
        if embedded is not None:
            return embedded
        checkpoint_file = Path(path).expanduser().resolve()
        candidates = (
            checkpoint_file.parent / filename,
            checkpoint_file.parent.parent / filename,
            checkpoint_file.parent.parent / "artifacts" / filename,
            checkpoint_file.parent.parent.parent / "artifacts" / filename,
        )
        for candidate in candidates:
            if candidate.is_file():
                try:
                    loaded = json.loads(candidate.read_text(encoding="utf-8"))
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"research_stage_checkpoint_{key}_invalid"
                    ) from exc
                return loaded
        return None

    def _checkpoint_sibling_payload(filename: str) -> Any | None:
        """Read a same-run sibling artifact for legacy checkpoint repair."""

        checkpoint_file = Path(path).expanduser().resolve()
        candidates = (
            checkpoint_file.parent / filename,
            checkpoint_file.parent.parent / filename,
            checkpoint_file.parent.parent / "artifacts" / filename,
            checkpoint_file.parent.parent.parent / "artifacts" / filename,
        )
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"research_stage_checkpoint_sibling_invalid:{filename}"
                ) from exc
            return loaded
        return None

    def _checkpoint_source_payload(key: str, filename: str) -> Any | None:
        """Load an inline source artifact, or its legacy same-run sibling."""

        embedded = payload.get(key)
        if embedded is not None:
            return embedded
        return _checkpoint_sibling_payload(filename)

    # Source authority is a four-artifact closure.  New checkpoints carry the
    # closure inline; pre-inline checkpoints may reuse only the exact sibling
    # artifacts emitted by the same run, after validating their common
    # identity and every snapshot/tree binding.  A partial closure is never
    # completed by rebuilding one member from the live repository.
    raw_source_artifacts = {
        "behavior_graph": _checkpoint_source_payload(
            "behavior_graph", "behavior_graph_v1.json"
        ),
        "symbol_index": _checkpoint_source_payload(
            "symbol_index", "symbol_index_v2.json"
        ),
        "source_manifest": _checkpoint_source_payload(
            "source_manifest", "repository_source_manifest_v1.json"
        ),
        "implementation_scope": _checkpoint_source_payload(
            "implementation_scope", "implementation_scope_v1.json"
        ),
        "repository_authoring_artifacts_v1": _checkpoint_source_payload(
            "repository_authoring_artifacts_v1",
            "repository_authoring_artifacts_v1.json",
        ),
    }
    source_present = any(
        value is not None for value in raw_source_artifacts.values()
    )
    if source_present:
        missing_source_keys = tuple(
            key
            for key, value in raw_source_artifacts.items()
            if value is None
        )
        if missing_source_keys:
            raise ValueError(
                "research_stage_checkpoint_source_artifacts_incomplete:"
                + ",".join(missing_source_keys)
            )
        try:
            from code2paper.agentic.behavior_graph import (
                CodeBehaviorGraphV1,
                SymbolIndexV2,
            )
            from code2paper.agentic.implementation_scope import (
                ImplementationScopeV1,
            )
            from code2paper.agentic.repository_authoring_artifacts import (
                repository_authoring_identity_payload,
            )
            from code2paper.agentic.source_inventory import (
                RepositorySourceManifestV1,
                source_manifest_snapshot_failures,
            )

            restored_behavior_graph = CodeBehaviorGraphV1.model_validate(
                raw_source_artifacts["behavior_graph"]
            )
            restored_symbol_index = SymbolIndexV2.model_validate(
                raw_source_artifacts["symbol_index"]
            )
            restored_source_manifest = RepositorySourceManifestV1.model_validate(
                raw_source_artifacts["source_manifest"]
            )
            restored_scope = ImplementationScopeV1.model_validate(
                raw_source_artifacts["implementation_scope"]
            )
            identity_payload = raw_source_artifacts[
                "repository_authoring_artifacts_v1"
            ]
            if not isinstance(identity_payload, Mapping):
                raise ValueError("repository authoring identity must be a mapping")
            if (
                restored_behavior_graph.repo_snapshot_id
                != runtime.repo_snapshot.snapshot_id
                or restored_behavior_graph.project_tree_hash
                != runtime.repo_snapshot.project_tree_hash
                or restored_symbol_index.repo_snapshot_id
                != runtime.repo_snapshot.snapshot_id
                or restored_symbol_index.project_tree_hash
                != runtime.repo_snapshot.project_tree_hash
            ):
                raise ValueError("source graph/index snapshot identity mismatch")
            manifest_failures = source_manifest_snapshot_failures(
                restored_source_manifest,
                runtime.repo_snapshot,
            )
            if manifest_failures:
                raise ValueError(
                    "source manifest snapshot identity mismatch:"
                    + ";".join(manifest_failures)
                )
            expected_identity = repository_authoring_identity_payload(
                snapshot=runtime.repo_snapshot,
                symbol_index=restored_symbol_index,
                implementation_scope=restored_scope,
                source_manifest=restored_source_manifest,
            )
            if dict(identity_payload) != expected_identity:
                raise ValueError("repository authoring identity mismatch")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "research_stage_checkpoint_source_artifacts_invalid"
            ) from exc
        loop.behavior_graph = restored_behavior_graph
        loop.symbol_index = restored_symbol_index
        loop.source_manifest = restored_source_manifest
        loop.implementation_scope = restored_scope

    raw_candidate_ledger = _checkpoint_ledger_payload(
        "candidate_acquisition_ledger",
        "candidate_acquisition_ledger_v1.json",
    )
    if raw_candidate_ledger is not None:
        try:
            loop.candidate_acquisition_ledger = (
                CandidateAcquisitionLedgerV1.model_validate(raw_candidate_ledger)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "research_stage_checkpoint_candidate_acquisition_ledger_invalid"
            ) from exc
        if (
            loop.candidate_acquisition_ledger.repo_snapshot_id
            != runtime.repo_snapshot.snapshot_id
            or loop.candidate_acquisition_ledger.project_tree_hash
            != runtime.repo_snapshot.project_tree_hash
        ):
            raise ValueError(
                "research_stage_checkpoint_candidate_acquisition_ledger_identity_mismatch"
            )

    raw_promotion_ledger = _checkpoint_ledger_payload(
        "observation_promotion_ledger",
        "observation_promotion_ledger_v1.json",
    )
    if raw_promotion_ledger is not None:
        try:
            loop.observation_promotion_ledger = (
                ObservationPromotionLedgerV1.model_validate(raw_promotion_ledger)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "research_stage_checkpoint_observation_promotion_ledger_invalid"
            ) from exc
        if (
            loop.observation_promotion_ledger.repo_snapshot_id
            != runtime.repo_snapshot.snapshot_id
            or loop.observation_promotion_ledger.project_tree_hash
            != runtime.repo_snapshot.project_tree_hash
        ):
            raise ValueError(
                "research_stage_checkpoint_observation_promotion_ledger_identity_mismatch"
            )
    checkpoint_handoff = payload.get("candidate_handoff")
    if not isinstance(checkpoint_handoff, dict):
        checkpoint_handoff = loop.intent_schedule.get("candidate_handoff")
    expected_promotion_digest = str(
        (checkpoint_handoff or {}).get("promotion_ledger_digest") or ""
    ) if isinstance(checkpoint_handoff, dict) else ""
    actual_promotion_digest = str(
        getattr(loop.observation_promotion_ledger, "content_digest", "") or ""
    )
    if expected_promotion_digest and not actual_promotion_digest:
        raise ValueError(
            "research_stage_checkpoint_observation_promotion_ledger_missing"
        )
    if (
        expected_promotion_digest
        and actual_promotion_digest != expected_promotion_digest
    ):
        # Pre-fix checkpoints persisted the pre-merge handoff from the
        # scheduler in their top-level field, while the canonical merged
        # handoff was written to ``artifacts/candidate_handoff_v1.json``.
        # Accept that narrowly identifiable legacy shape only when the
        # sibling handoff is independently valid, belongs to this run/tree,
        # and binds to the restored promotion ledger.  A mismatched or
        # missing sibling remains a hard failure.
        sibling_payload = _checkpoint_sibling_payload("candidate_handoff_v1.json")
        try:
            sibling_handoff = (
                CandidateHandoffV1.model_validate(sibling_payload)
                if sibling_payload is not None
                else None
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "research_stage_checkpoint_candidate_handoff_sibling_invalid"
            ) from exc
        if (
            sibling_handoff is None
            or sibling_handoff.run_id != runtime.run_id
            or sibling_handoff.repo_snapshot_id != runtime.repo_snapshot.snapshot_id
            or sibling_handoff.project_tree_hash
            != runtime.repo_snapshot.project_tree_hash
            or sibling_handoff.promotion_ledger_digest != actual_promotion_digest
        ):
            raise ValueError(
                "research_stage_checkpoint_observation_promotion_ledger_digest_mismatch"
            )
        checkpoint_handoff = sibling_handoff.model_dump(mode="json")
        loop.intent_schedule["candidate_handoff"] = checkpoint_handoff
    final_state = empty_agent_state_v3(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    ).to_state_dict()
    final_state["status"] = str(terminal.get("final_status") or "incomplete")
    restored_journal = revision_journal
    if restored_journal is None:
        journal_payload = payload.get("revision_journal")
        if journal_payload:
            restored_journal = RevisionJournalV1.model_validate(journal_payload)
    return (
        ResearchLoopResult(
            loop_state=loop,
            final_state=final_state,
            turns_executed=loop.turn_index,
            terminated=loop.terminated,
            termination_reason=loop.termination_reason,
            decision_trace=loop.decision_trace,
            policy_merge_trace=loop.policy_merge_trace,
            evidence_critic_routes=[],
            revision_journal=(
                restored_journal
                if restored_journal is not None
                else RevisionJournalV1()
            ),
            revision_ingest_outcomes=list(
                payload.get("revision_ingest_outcomes") or ()
            ),
            revision_ingest_failures=list(
                payload.get("revision_ingest_failures") or ()
            ),
        ),
        packet_set,
        fact_set,
        claim_set,
        UserClaimsInputV1.model_validate(payload.get("claims_input") or {}),
    )


def build_typed_gaps(
    runtime: ResearchGraphRuntime,
    result: ResearchLoopResult,
    *,
    claim_set: AtomicClaimSetV3 | None,
) -> tuple[TypedResearchGapV1, ...]:
    """Collect typed gaps from the loop's real terminal state.

    ``explicit_gap`` items come from the gap finalizer's accepted
    ``GapRequirementV1`` records (with the frozen search scope and the
    attempted-tool provenance).  Items that the loop stopped on while
    still open are typed ``unresolved`` with the loop's stopping reason.
    Nothing here is synthesized: a missing gap is a missing gap.
    """

    agenda = runtime.agenda
    loop_state = getattr(result, "loop_state", None)
    observation_history = tuple(
        getattr(loop_state, "observation_history", ()) or ()
    )

    def _attempted_tools_for(item: Any) -> tuple[str, ...]:
        """Use agenda actions first, then observed tool names as fallback."""

        actions = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in getattr(item, "attempted_actions", ()) or ()
                if str(value).strip()
            )
        )
        if actions:
            return actions
        return tuple(dict.fromkeys(
            str(getattr(observation, "tool_name", "") or "")
            for observation in observation_history
            if str(getattr(observation, "obligation_id", "") or "")
            == str(getattr(item, "obligation_id", "") or "")
            and str(getattr(observation, "tool_name", "") or "")
        ))

    gaps: list[TypedResearchGapV1] = []
    for item in agenda.items:
        if item.status == "explicit_gap":
            requirement = item.gap_requirements[-1] if item.gap_requirements else None
            reason = (
                requirement.rationale
                if requirement is not None and requirement.rationale
                else (
                    f"Exhaustive search for obligation {item.obligation_id} "
                    "did not yield sufficient executable evidence."
                )
            )
            gaps.append(TypedResearchGapV1(
                gap_id=f"gap:{item.obligation_id}",
                obligation_id=item.obligation_id,
                status="explicit_gap",
                reason=reason,
                attempted_tools=(
                    requirement.attempted_tools if requirement is not None else ()
                ),
                search_scope=(
                    tuple(
                        part.strip()
                        for part in str(requirement.search_scope or "").split(",")
                        if part.strip()
                    )
                    if requirement is not None
                    else ()
                ),
                stopping_reason="gap_finalizer_accepted",
                trace_refs=(f"agenda:{item.obligation_id}",),
            ))
        elif item.status == "partial" and item.missing_information:
            attempted = _attempted_tools_for(item)
            gaps.append(TypedResearchGapV1(
                gap_id=f"gap-partial:{item.obligation_id}",
                obligation_id=item.obligation_id,
                status="unresolved",
                reason=(
                    f"Obligation {item.obligation_id} produced promoted partial evidence; "
                    "the following fields remain unresolved for Candidate review: "
                    + ", ".join(str(value) for value in item.missing_information)
                ),
                attempted_tools=attempted,
                search_scope=tuple(dict.fromkeys(item.candidate_symbol_ids)),
                missing_relations=tuple(dict.fromkeys(item.missing_information)),
                stopping_reason="candidate_partial_unresolved",
                trace_refs=(f"agenda:{item.obligation_id}",),
            ))
        elif item.status in {"pending", "in_progress"}:
            attempted = _attempted_tools_for(item)
            stopping_reason = str(result.termination_reason or "").strip()
            if not attempted:
                stopping_reason = "never_attempted"
            reason = (
                f"Obligation {item.obligation_id} was still open when the "
                f"research loop stopped ({result.termination_reason})."
            )
            if (
                item.priority == "preference"
                and "ORGANIZATION" in str(item.obligation_id).upper()
            ):
                reason = (
                    f"Organization preference {item.obligation_id} remained open; "
                    "it does not consume must-cover code search."
                )
                if stopping_reason == "never_attempted":
                    stopping_reason = "organization_preference"
            gaps.append(TypedResearchGapV1(
                gap_id=f"gap-unresolved:{item.obligation_id}",
                obligation_id=item.obligation_id,
                status="unresolved",
                reason=reason,
                attempted_tools=attempted,
                search_scope=tuple(dict.fromkeys(
                    path for path in item.candidate_symbol_ids
                )),
                stopping_reason=stopping_reason,
                trace_refs=(f"agenda:{item.obligation_id}",),
            ))
        elif item.status == "blocked":
            attempted = _attempted_tools_for(item)
            stopping_reason = str(result.termination_reason or "").strip()
            if not attempted:
                stopping_reason = "never_attempted"
            gaps.append(TypedResearchGapV1(
                gap_id=f"gap-blocked:{item.obligation_id}",
                obligation_id=item.obligation_id,
                status="blocked",
                reason=f"Obligation {item.obligation_id} ended blocked.",
                attempted_tools=attempted,
                stopping_reason=stopping_reason,
                trace_refs=(f"agenda:{item.obligation_id}",),
            ))
    known = {item.gap_id for item in gaps}
    for gap in (claim_set.explicit_code_gaps if claim_set is not None else ()):
        if gap.gap_id in known:
            continue
        gaps.append(TypedResearchGapV1(
            gap_id=gap.gap_id,
            obligation_id="",
            status="explicit_gap",
            reason=gap.rationale or gap.topic,
            stopping_reason="compiled_explicit_code_gap",
            trace_refs=(f"claim_gap:{gap.gap_id}",),
        ))
    return tuple(gaps)


def _requires_mechanism_planner(*, llm_config: LLMConfig | None) -> bool:
    return bool(llm_config is not None and has_provider_api_key(llm_config))


def _build_argument_brief_planner(
    *,
    llm_config: LLMConfig | None,
    claims: AtomicClaimSetV3 | None,
    equations: Any | None,
) -> Any | None:
    if not _requires_mechanism_planner(llm_config=llm_config) or claims is None:
        return None
    from code2paper.agentic.method_argument_brief_planner import build_mechanism_draft_planner

    return build_mechanism_draft_planner(
        llm_config,  # type: ignore[arg-type]
        claims=claims,
        equations=equations,
    )


def build_product_planning(
    *,
    runtime: ResearchGraphRuntime,
    packet_set: EvidencePacketSetV3 | None,
    fact_set: CodeFactSetV1 | None,
    claim_set: AtomicClaimSetV3 | None,
    claims_input: UserClaimsInputV1 | None = None,
    method_name: str = "",
    llm_config: LLMConfig | None = None,
    concept_cards: Any | None = None,
    compile_concept_cards: bool = False,
    argument_briefs: Any | None = None,
    compile_argument_briefs: bool = True,
    facet_decomposer: Any | None = None,
    facet_evidence_aligner: Any | None = None,
    prior_plan: MethodSectionPlanV2 | None = None,
    implementation_scope: Any | None = None,
    behavior_graph: Any | None = None,
) -> dict[str, Any]:
    """Compile coverage, completeness, equations, configs, plan, readiness.

    Returns a dict with keys: ``coverage``, ``agenda_ref``,
    ``completeness``, ``equations``, ``configurations``, ``story_spine``,
    ``argument_facets``, ``facet_alignments``, ``facet_policies``,
    ``facet_alignment_result``, ``plan`` (or None), ``readiness`` (or None),
    ``review_candidates``.

    ``concept_cards`` (optional ``MethodConceptCardSetV1``) switches the
    plan to the Stage 2/3 concept lane: the Architect binds concept cards
    to units instead of propositions, and the Writer surface consumes
    ``method_concept_cards_v1``.  Proposition compilation is skipped in
    that mode (propositions and concept cards are mutually exclusive).

    ``compile_concept_cards`` is deprecated and ignored on the live mainline.
    The default lane compiles deterministic ``method_argument_briefs_v1``
    via ``compile_argument_briefs`` (no LLM).  Proposition compilation is
    skipped when argument briefs are present.
    """

    intent_graph = runtime.intent_graph
    repo_snapshot_id = runtime.repo_snapshot.snapshot_id
    project_tree_hash = runtime.repo_snapshot.project_tree_hash

    terminal_gaps, gap_bindings = _load_terminal_gap_artifacts(runtime)
    coverage = build_obligation_coverage_v2(
        intent_graph,
        fact_set=fact_set,
        claim_set=claim_set,
        explicit_gaps=terminal_gaps,
        gap_obligation_bindings=gap_bindings,
    )
    agenda_ref = build_reference_method_agenda(
        intent_graph,
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        author_goal=str(getattr(intent_graph, "method_goal", "")),
    )
    equations = None
    if fact_set is not None:
        equations, _equation_reports = compile_equation_claims(
            derive_equation_proposals_from_facts(fact_set),
            fact_set,
            repo_snapshot_id=repo_snapshot_id,
            project_tree_hash=project_tree_hash,
        )
        if claim_set is not None:
            equations = bind_equations_to_claims(equations, claim_set)
    configurations = compile_configuration_claims(fact_set) if fact_set is not None else None

    equation_ids_by_obligation: dict[str, tuple[str, ...]] = {}
    configuration_ids_by_obligation: dict[str, tuple[str, ...]] = {}
    if claim_set is not None:
        for claim in claim_set.claims:
            claim_facts = set(claim.fact_ids)
            claim_relations = set(claim.relation_evidence_ids)
            for obligation_id in claim.covers_obligation_ids:
                if equations is not None:
                    equation_ids_by_obligation.setdefault(obligation_id, [])
                    equation_ids_by_obligation[obligation_id] = tuple(dict.fromkeys(
                        [
                            *equation_ids_by_obligation[obligation_id],
                            *[
                                equation.equation_id
                                for equation in equations.equations
                                if str(getattr(equation, "formula_role", "") or "")
                                != "incidental"
                                if claim_facts.intersection(equation.fact_ids)
                            ],
                        ]
                    ))
                if configurations is not None:
                    configuration_ids_by_obligation.setdefault(obligation_id, [])
                    configuration_ids_by_obligation[obligation_id] = tuple(dict.fromkeys(
                        [
                            *configuration_ids_by_obligation[obligation_id],
                            *[
                                configuration.configuration_id
                                for configuration in configurations.claims
                                if claim_facts.intersection(configuration.source_fact_ids)
                                or claim_relations.intersection(configuration.override_chain)
                            ],
                        ]
                    ))

    completeness = build_completeness_matrix(
        agenda_ref,
        coverage,
        claim_set=claim_set,
        equation_ids_by_obligation=equation_ids_by_obligation,
        configuration_ids_by_obligation=configuration_ids_by_obligation,
    )
    story_spine = build_story_spine_from_intent_graph(
        intent_graph,
        claim_set=claim_set,
    )
    story_spine = _refine_claim_story_roles(story_spine, claims_input)
    authoring_projection = None
    method_evidence = None
    claim_evidence_map = None
    if packet_set is not None and claim_set is not None:
        method_template = _method_evidence_template(
            runtime=runtime,
            method_name=method_name,
        )
        authoring_projection = build_authoring_projection(
            method_evidence=method_template,
            claim_map=ClaimEvidenceMap(),
            verification=ClaimVerificationReport(),
            atomic_claims_v3=claim_set,
            evidence_packets_v3=packet_set,
            equation_claims_v1=equations,
            intent_obligation_graph_v2=intent_graph,
            completeness=completeness,
        )
        if authoring_projection.author_story_spine:
            story_spine = list(authoring_projection.author_story_spine)
        method_evidence, claim_evidence_map = projected_writer_inputs(
            authoring_projection,
            template=method_template,
        )
    if (
        argument_briefs is None
        and concept_cards is None
        and compile_argument_briefs
        and claim_set is not None
        and claim_set.claims
    ):
        argument_briefs = compile_method_argument_briefs(
            claims=claim_set,
            completeness=completeness,
            coverage=coverage,
            intent_graph=intent_graph,
            story_spine=story_spine,
            equations=equations,
            configurations=configurations,
            planner=_build_argument_brief_planner(
                llm_config=llm_config,
                claims=claim_set,
                equations=equations,
            ),
            require_planner_for_unlicensed=_requires_mechanism_planner(
                llm_config=llm_config,
            ),
        )
    facet_alignment_result = None
    if argument_briefs is not None:
        # Candidate semantic alignment is a sidecar.  It receives the frozen
        # research evidence but never mutates the deterministic clause
        # licenses or the brief set's Verified digest.
        ownership_roles_by_symbol: dict[str, str] = {}
        loop_scope = implementation_scope
        loop_behavior_graph = behavior_graph
        if loop_scope is not None and loop_behavior_graph is not None:
            for node in getattr(loop_behavior_graph, "nodes", ()) or ():
                node_symbol = str(getattr(node, "symbol_id", "") or "").strip()
                if not node_symbol:
                    continue
                role = scope_role_for_candidate(
                    loop_scope,
                    node_symbol,
                    behavior_graph=loop_behavior_graph,
                )
                span_id = str(getattr(node, "source_span_id", "") or "")
                ownership_roles_by_symbol[node_symbol] = role
                if span_id.startswith("span:"):
                    parts = span_id.rsplit(":", 2)
                    if len(parts) == 3:
                        path = parts[0].removeprefix("span:")
                        # Evidence spans carry the owning symbol separately;
                        # path-only aliases are still useful for adapters that
                        # expose a short symbol name.
                        ownership_roles_by_symbol[path] = role
        facet_alignment_result = decompose_and_align_argument_facets(
            briefs=argument_briefs,
            claims=claim_set,
            facts=fact_set,
            evidence_packets=packet_set,
            equations=equations,
            facet_decomposer=facet_decomposer,
            evidence_aligner=facet_evidence_aligner,
            llm_config=(
                llm_config
                if llm_config is not None and has_provider_api_key(llm_config)
                else None
            ),
            intent_graph=intent_graph,
            implementation_scope=loop_scope,
            behavior_graph=loop_behavior_graph,
            ownership_roles_by_symbol=ownership_roles_by_symbol,
        )
        if hasattr(argument_briefs, "model_copy"):
            argument_briefs = bind_facets_to_argument_briefs(
                argument_briefs,
                facets=facet_alignment_result.facets,
                alignments=facet_alignment_result.alignments,
                policies=facet_alignment_result.policies,
            )
    # Deprecated: ``compile_concept_cards`` is ignored on the live mainline.
    _ = compile_concept_cards
    propositions = None
    proposition_bindings = None
    proposition_clusters = ()
    proposition_architect_traces = ()
    proposition_evidence_judge_traces = ()
    if (
        argument_briefs is None
        and concept_cards is None
        and packet_set is not None
        and fact_set is not None
        and claim_set is not None
    ):
        proposition_architect = (
            build_method_proposition_architect(llm_config)
            if llm_config is not None and has_provider_api_key(llm_config)
            else None
        )
        proposition_evidence_judge = (
            build_method_proposition_evidence_judge(llm_config)
            if llm_config is not None and has_provider_api_key(llm_config)
            else None
        )
        propositions, proposition_bindings, proposition_clusters = compile_method_propositions(
            claims=claim_set,
            facts=fact_set,
            packets=packet_set,
            completeness=completeness,
            story_spine=story_spine,
            proposal_architect=proposition_architect,
            evidence_judge=proposition_evidence_judge,
            require_evidence_judge=True,
            configurations=configurations,
            equations=equations,
        )
        proposition_architect_traces = tuple(
            getattr(proposition_architect, "proposal_traces", ())
            if proposition_architect is not None else ()
        )
        proposition_evidence_judge_traces = tuple(
            getattr(proposition_evidence_judge, "evidence_judge_traces", ())
            if proposition_evidence_judge is not None else ()
        )
    # Argument briefs and the validation proposition set are parallel, not
    # mutually exclusive.  V2 is compiled even when briefs already exist.
    intent_atoms: tuple[Any, ...] = ()
    intent_atom_closures: tuple[Any, ...] = ()
    legacy_field_to_atom_trace: dict[str, tuple[str, ...]] = {}
    if facet_alignment_result is not None:
        from code2paper.agentic.intent_evidence_atoms import compile_intent_evidence_from_facets

        atom_bundle = compile_intent_evidence_from_facets(
            facets=facet_alignment_result.facets,
            alignments=facet_alignment_result.alignments,
            story_spine=story_spine,
        )
        intent_atoms = tuple(atom_bundle.get("atoms") or ())
        intent_atom_closures = tuple(atom_bundle.get("closures") or ())
        legacy_field_to_atom_trace = dict(atom_bundle.get("legacy_field_to_atom_trace") or {})
    propositions_v2 = None
    try:
        from code2paper.agentic.intent_proposition_compiler import compile_method_propositions_v2

        mechanism_details = ()
        propositions_v2 = compile_method_propositions_v2(
            intent_atoms=intent_atoms,
            publication_field_candidates=(
                facet_alignment_result.publication_field_candidates
                if facet_alignment_result is not None
                else ()
            ),
            candidate_facet_policies=(
                facet_alignment_result.policies
                if facet_alignment_result is not None
                else ()
            ),
            mechanism_details=mechanism_details,
        )
    except (TypeError, ValueError):
        propositions_v2 = None
    plan = None
    readiness = None
    if claim_set is not None and claim_set.claims:
        plan, readiness, _trace = build_method_section_plan_with_product_readiness(
            claims=claim_set,
            completeness=completeness,
            equations=equations,
            configurations=configurations,
            method_name=method_name,
            story_spine=story_spine,
            policy=build_default_method_output_policy(),
            propositions=propositions,
            concept_cards=concept_cards,
            argument_briefs=argument_briefs,
            prior_plan=prior_plan,
            facts=fact_set,
            publication_field_candidates=(
                facet_alignment_result.publication_field_candidates
                if facet_alignment_result is not None
                else ()
            ),
            argument_facets=(
                facet_alignment_result.facets
                if facet_alignment_result is not None
                else ()
            ),
            facet_alignments=(
                facet_alignment_result.alignments
                if facet_alignment_result is not None
                else ()
            ),
        )
    review_candidates = build_review_candidates_from_completeness(
        completeness,
        agenda=agenda_ref,
        plan=plan,
        policy=build_default_method_output_policy(),
    )
    return {
        "coverage": coverage,
        "agenda_ref": agenda_ref,
        "completeness": completeness,
        "equations": equations,
        "configurations": configurations,
        "story_spine": story_spine,
        "authoring_projection": authoring_projection,
        "method_evidence": method_evidence,
        "claim_evidence_map": claim_evidence_map,
        "plan": plan,
        "readiness": readiness,
        "review_candidates": review_candidates,
        "method_propositions": propositions,
        "proposition_bindings": proposition_bindings,
        "proposition_clusters": proposition_clusters,
        "proposition_architect_traces": proposition_architect_traces,
        "proposition_evidence_judge_traces": proposition_evidence_judge_traces,
        "method_propositions_v2": propositions_v2,
        "intent_atoms": intent_atoms,
        "intent_atom_closures": intent_atom_closures,
        "legacy_field_to_atom_trace": legacy_field_to_atom_trace,
        "concept_cards": concept_cards,
        "argument_briefs": argument_briefs,
        "argument_facets": (
            facet_alignment_result.facets
            if facet_alignment_result is not None
            else ()
        ),
        "facet_alignments": (
            facet_alignment_result.alignments
            if facet_alignment_result is not None
            else ()
        ),
        "facet_policies": (
            facet_alignment_result.policies
            if facet_alignment_result is not None
            else ()
        ),
        "publication_field_candidates": (
            facet_alignment_result.publication_field_candidates
            if facet_alignment_result is not None
            else ()
        ),
        "typed_field_deferred": (
            facet_alignment_result.typed_field_deferred
            if facet_alignment_result is not None
            else ()
        ),
        "facet_alignment_result": facet_alignment_result,
    }


def _load_terminal_gap_artifacts(
    runtime: ResearchGraphRuntime,
) -> tuple[list[Any], dict[str, list[str]]]:
    """Load the gap finalizer's real terminal-gap artifacts from the data plane.

    The research loop persists one idempotent terminal-gap payload per accepted
    obligation (``record_explicit_code_gap``).  R9: only a payload whose typed
    outcome is a ledger-authenticated ``unsupported_with_scoped_evidence``
    conclusion becomes a coverage ``ExplicitCodeGapV1``.  A bounded stop
    (``search_inconclusive`` / ``budget_exhausted``) keeps its honest
    ``unresolved`` coverage instead of being promoted into a code gap.
    """

    from code2paper.agentic.evidence_compiler_v3 import ExplicitCodeGapV1
    from code2paper.agentic.research_execution_ledger import (
        ExecutionLedgerError,
        build_context_ledger_reader,
        verify_receipt_authentication,
    )

    tool_context = runtime.tool_context()
    try:
        ledger_reader = build_context_ledger_reader(tool_context)
    except Exception:  # pragma: no cover - defensive: no reader, no gap
        ledger_reader = None
    gap_root = tool_context.artifact_root / "research_tool_artifacts" / "terminal_gaps"
    gaps: list[Any] = []
    bindings: dict[str, list[str]] = {}
    if not gap_root.is_dir():
        return gaps, bindings
    for path in sorted(gap_root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        obligation_id = str(payload.get("obligation_id") or "").strip()
        gap_id = str(payload.get("gap_id") or "").strip()
        if not obligation_id or not gap_id:
            continue
        if str(payload.get("terminal_outcome") or "") != (
            "unsupported_with_scoped_evidence"
        ) or not bool(payload.get("negative_evidence_authorized", False)):
            continue
        try:
            authorized, _failures = verify_receipt_authentication(
                payload.get("search_receipt"),
                obligation_id=obligation_id,
                # R9: re-derive from the current revision's execution ledger.
                # A stored ``ledger_verified`` marker is not enough once the
                # records behind it can be damaged, deleted or stale.
                ledger_reader=ledger_reader,
            )
        except ExecutionLedgerError:
            authorized = False
        if not authorized:
            continue
        gaps.append(ExplicitCodeGapV1(
            gap_id=gap_id,
            topic=f"Explicit gap for obligation {obligation_id}",
            scope=",".join(payload.get("search_scope") or ()),
            rationale=str(payload.get("termination_reason") or ""),
            source_kind="author_obligation",
        ))
        bindings[gap_id] = [obligation_id]
    return gaps, bindings


def _refine_claim_story_roles(
    spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1],
    claims_input: UserClaimsInputV1 | None,
) -> list[AuthorStoryNodeV1]:
    """Apply the user-declared story role to claim-backed spine nodes."""

    if claims_input is None or not claims_input.claims:
        return list(spine)
    role_by_obligation = {
        _stable_id("claim", claim.claim_id): claim.role
        for claim in claims_input.claims
    }
    refined: list[AuthorStoryNodeV1] = []
    for node in spine:
        linked = set(node.linked_obligation_ids)
        role = next(
            (
                role_by_obligation[obligation_id]
                for obligation_id in node.linked_obligation_ids
                if obligation_id in role_by_obligation
            ),
            None,
        )
        if role is not None and role != node.intended_role:
            node = node.model_copy(update={"intended_role": role})
        refined.append(node)
    return refined


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def persist_product_artifacts(
    *,
    out_root: str | Path,
    runtime: ResearchGraphRuntime,
    claims_input: UserClaimsInputV1,
    loop_result: ResearchLoopResult,
    packet_set: EvidencePacketSetV3 | None,
    fact_set: CodeFactSetV1 | None,
    claim_set: AtomicClaimSetV3 | None,
    typed_gaps: tuple[TypedResearchGapV1, ...],
    planning: dict[str, Any],
    agent_trace: list[dict[str, Any]],
    summary: dict[str, Any],
    candidate_handoff: CandidateHandoffV1 | None = None,
    candidate_retry_ledger: CandidateRetryLedgerV1 | None = None,
    revision_journal: Any | None = None,
) -> dict[str, str]:
    """Persist every product artifact and return the path map.

    The writer-facing keys (``method_evidence``, ``claim_evidence_map``,
    ``authoring_projection_v1``, ``atomic_claims_v3``, ``code_facts_v1``,
    ``evidence_packets_v3``, ``equation_claims_v1``,
    ``configuration_claims_v1``, ``method_completeness_matrix_v1``,
    ``method_section_plan_v2``, ``reference_method_agenda_v1``,
    ``obligation_coverage_v2``) live under ``out_root/artifacts/`` so the
    Writer surface can consume them unchanged.  Product-named copies live
    under ``out_root/artifacts/research_product/``.
    """

    root = Path(out_root).expanduser().resolve()
    artifacts_dir = root / "artifacts"
    product_dir = artifacts_dir / "research_product"
    product_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}

    def _write(key: str, payload: Any, *, product: bool = True) -> str:
        target = (product_dir if product else artifacts_dir) / f"{key}.json"
        _atomic_write_text(target, _json_text(payload))
        paths[key] = str(target)
        return str(target)

    # R3: persist the live behavior graph so facts/claims can be regenerated
    # from frozen research evidence (exact-guard recompilation input).
    _behavior_graph = getattr(
        getattr(loop_result, "loop_state", None), "behavior_graph", None
    )
    if _behavior_graph is not None:
        paths["behavior_graph_v1"] = _write(
            "behavior_graph_v1",
            _behavior_graph.model_dump(mode="json"),
            product=False,
        )

    # The snapshot is the repository authority identity for every downstream
    # context consumer.  Persist it beside the research artifacts so replay,
    # unified reconstruction, and callback resume all bind to the same tree.
    snapshot_path = _write(
        "repo_snapshot_v2",
        runtime.repo_snapshot.model_dump(mode="json"),
        product=False,
    )
    paths["repo_snapshot"] = snapshot_path
    loop_symbol_index = getattr(loop_result.loop_state, "symbol_index", None)
    if loop_symbol_index is not None:
        paths["symbol_index_v2"] = _write(
            "symbol_index_v2",
            loop_symbol_index.model_dump(mode="json"),
            product=False,
        )
        paths["symbol_index"] = paths["symbol_index_v2"]
    loop_scope = getattr(loop_result.loop_state, "implementation_scope", None)
    loop_source_manifest = getattr(loop_result.loop_state, "source_manifest", None)
    if loop_source_manifest is not None:
        paths["repository_source_manifest_v1"] = _write(
            "repository_source_manifest_v1",
            loop_source_manifest.model_dump(mode="json"),
            product=False,
        )
    if (
        runtime.repo_snapshot is not None
        and loop_symbol_index is not None
        and loop_scope is not None
        and loop_source_manifest is not None
    ):
        from code2paper.agentic.repository_authoring_artifacts import (
            repository_authoring_identity_payload,
        )

        paths["repository_authoring_artifacts_v1"] = _write(
            "repository_authoring_artifacts_v1",
            repository_authoring_identity_payload(
                snapshot=runtime.repo_snapshot,
                symbol_index=loop_symbol_index,
                implementation_scope=loop_scope,
                source_manifest=loop_source_manifest,
            ),
            product=False,
        )

    paths["intent_obligation_graph_v2"] = _write(
        "intent_obligation_graph_v2",
        runtime.intent_graph.model_dump(mode="json"),
        product=False,
    )
    paths["research_agenda_v1"] = _write(
        "research_agenda_v1",
        runtime.agenda.model_dump(mode="json"),
        product=False,
    )
    paths["user_claims_input_v1"] = _write(
        "user_claims_input_v1",
        claims_input.model_dump(mode="json"),
        product=False,
    )
    paths["research_trace"] = _write("research_trace", _build_research_trace(loop_result))
    paths["typed_gaps"] = _write("typed_gaps", [gap.model_dump(mode="json") for gap in typed_gaps])
    if candidate_handoff is not None:
        # Candidate receives this independent handoff plus the ordinary
        # evidence artifacts.  It is never used as a Verified terminal proof.
        paths["candidate_handoff_v1"] = _write(
            "candidate_handoff_v1",
            candidate_handoff.model_dump(mode="json"),
            product=False,
        )
    retry_gain_by_obligation: dict[str, bool | None] = {}
    for event in loop_result.loop_state.intent_compile_events or ():
        obligation_id = str(event.get("obligation_id") or "").strip()
        if not obligation_id:
            continue
        if int(
            (loop_result.loop_state.post_partial_retry_counts or {}).get(
                obligation_id,
                0,
            )
            or 0
        ) >= 1:
            retry_gain_by_obligation[obligation_id] = bool(
                event.get("has_coverage_gain", False)
            )
    retry_ledger = (
        candidate_retry_ledger
        if candidate_retry_ledger is not None
        else build_candidate_retry_ledger(
            run_id=runtime.run_id,
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
            post_partial_retry_counts=loop_result.loop_state.post_partial_retry_counts,
            semantic_gain_by_obligation=retry_gain_by_obligation,
        )
    )
    paths["candidate_retry_ledger_v1"] = _write(
        "candidate_retry_ledger_v1",
        retry_ledger.model_dump(mode="json"),
        product=False,
    )

    # Research closure sidecars.  These are diagnostic provenance artifacts,
    # not a second authority path: positive claims still come only from the
    # frozen packets/facts/claims below.
    if loop_scope is not None:
        paths["implementation_scope_v1"] = _write(
            "implementation_scope_v1",
            loop_scope.model_dump(mode="json"),
            product=False,
        )
    loop_ledger = getattr(loop_result.loop_state, "candidate_acquisition_ledger", None)
    if loop_ledger is not None:
        paths["candidate_acquisition_ledger_v1"] = _write(
            "candidate_acquisition_ledger_v1",
            loop_ledger.model_dump(mode="json"),
            product=False,
        )
    promotion_ledger = getattr(loop_result.loop_state, "observation_promotion_ledger", None)
    if promotion_ledger is not None:
        paths["observation_promotion_ledger_v1"] = _write(
            "observation_promotion_ledger_v1",
            promotion_ledger.model_dump(mode="json"),
            product=False,
        )

    coverage = planning["coverage"]
    agenda_ref = planning["agenda_ref"]
    completeness = planning["completeness"]
    equations = planning["equations"]
    configurations = planning["configurations"]
    story_spine = planning["story_spine"]
    authoring_projection = planning.get("authoring_projection")
    method_evidence = planning.get("method_evidence")
    claim_evidence_map = planning.get("claim_evidence_map")
    plan = planning["plan"]
    readiness = planning["readiness"]
    review_candidates = planning["review_candidates"]
    propositions = planning.get("method_propositions")
    propositions_v2 = planning.get("method_propositions_v2")
    proposition_bindings = planning.get("proposition_bindings")
    proposition_clusters = planning.get("proposition_clusters") or ()
    proposition_architect_traces = planning.get("proposition_architect_traces") or ()
    proposition_evidence_judge_traces = planning.get(
        "proposition_evidence_judge_traces"
    ) or ()
    concept_cards = planning.get("concept_cards")
    argument_facets = planning.get("argument_facets") or ()
    facet_alignments = planning.get("facet_alignments") or ()
    facet_policies = planning.get("facet_policies") or ()
    facet_alignment_result = planning.get("facet_alignment_result")
    publication_field_candidates = planning.get("publication_field_candidates") or ()
    typed_field_deferred = planning.get("typed_field_deferred") or ()

    paths["obligation_coverage_v2"] = _write(
        "obligation_coverage_v2",
        coverage.model_dump(mode="json"),
        product=False,
    )
    paths["reference_method_agenda_v1"] = _write(
        "reference_method_agenda_v1",
        agenda_ref.model_dump(mode="json"),
        product=False,
    )
    paths["method_completeness_matrix_v1"] = _write(
        "method_completeness_matrix_v1",
        completeness.model_dump(mode="json"),
        product=False,
    )
    paths["completeness_matrix"] = _write(
        "completeness_matrix",
        completeness.model_dump(mode="json"),
    )
    story_spine_payload = [node.model_dump(mode="json") for node in story_spine]
    paths["story_spine"] = _write("story_spine", story_spine_payload)
    # The Writer artifact collector consumes the frozen product surface from
    # ``artifacts/``.  Persist the same bytes under the canonical v1 key; the
    # two names are aliases, not independently generated story artifacts.
    paths["author_story_spine_v1"] = _write(
        "author_story_spine_v1", story_spine_payload, product=False
    )
    paths["method_story_nodes_v1"] = _write(
        "method_story_nodes_v1", story_spine_payload, product=False
    )
    if authoring_projection is not None:
        paths["authoring_projection_v1"] = _write(
            "authoring_projection_v1",
            authoring_projection.model_dump(mode="json"),
            product=False,
        )
    if method_evidence is not None:
        paths["method_evidence"] = _write(
            "method_evidence",
            method_evidence.model_dump(mode="json"),
            product=False,
        )
    if claim_evidence_map is not None:
        paths["claim_evidence_map"] = _write(
            "claim_evidence_map",
            claim_evidence_map.model_dump(mode="json"),
            product=False,
        )
    if equations is not None:
        paths["equation_claims_v1"] = _write(
            "equation_claims_v1",
            equations.model_dump(mode="json"),
            product=False,
        )
    if configurations is not None:
        paths["configuration_claims_v1"] = _write(
            "configuration_claims_v1",
            configurations.model_dump(mode="json"),
            product=False,
        )
    if packet_set is not None:
        paths["evidence_packets_v3"] = _write(
            "evidence_packets_v3",
            packet_set.model_dump(mode="json"),
            product=False,
        )
        paths["evidence_packets"] = _write(
            "evidence_packets",
            packet_set.model_dump(mode="json"),
        )
    if fact_set is not None:
        paths["code_facts_v1"] = _write(
            "code_facts_v1",
            fact_set.model_dump(mode="json"),
            product=False,
        )
        paths["code_facts"] = _write(
            "code_facts",
            fact_set.model_dump(mode="json"),
        )
    if claim_set is not None:
        paths["atomic_claims_v3"] = _write(
            "atomic_claims_v3",
            claim_set.model_dump(mode="json"),
            product=False,
        )
        paths["atomic_claims"] = _write(
            "atomic_claims",
            claim_set.model_dump(mode="json"),
        )
        from code2paper.agentic.scientific_claim_ir import write_technical_claims_sidecar

        paths["technical_claims_v1"] = write_technical_claims_sidecar(
            paths["atomic_claims_v3"], claim_set
        )
    if plan is not None:
        # An incumbent MethodUnit plan is freeze authority.  Callback Research
        # may rebuild claims and dossiers, but must not remint paragraph
        # identity, publication slots, or formula consumers.
        incumbent_plan = next(
            (
                path
                for path in (
                    root / "artifacts" / "06_authoring" / "method_section_plan_v2.json",
                    artifacts_dir / "method_section_plan_v2.json",
                )
                if path.is_file()
            ),
            None,
        )
        if incumbent_plan is not None:
            paths["method_section_plan_v2"] = str(incumbent_plan)
        else:
            paths["method_section_plan_v2"] = _write(
                "method_section_plan_v2",
                plan.model_dump(mode="json"),
                product=False,
            )
    if propositions is not None:
        paths["method_propositions_v1"] = _write(
            "method_propositions_v1",
            propositions.model_dump(mode="json"),
            product=False,
        )
    if propositions_v2 is not None:
        paths["method_propositions_v2"] = _write(
            "method_propositions_v2",
            propositions_v2.model_dump(mode="json"),
            product=False,
        )
    intent_atoms = planning.get("intent_atoms") or ()
    intent_atom_closures = planning.get("intent_atom_closures") or ()
    legacy_field_to_atom_trace = planning.get("legacy_field_to_atom_trace") or {}
    if intent_atoms or intent_atom_closures:
        paths["intent_evidence_atoms_v1"] = _write(
            "intent_evidence_atoms_v1",
            {
                "schema_version": "1.0",
                "atoms": [
                    item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
                    for item in intent_atoms
                ],
                "closures": [
                    item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
                    for item in intent_atom_closures
                ],
                "legacy_field_to_atom_trace": {
                    str(key): list(values)
                    for key, values in dict(legacy_field_to_atom_trace).items()
                },
            },
            product=False,
        )
    if proposition_bindings is not None:
        paths["method_proposition_bindings_v1"] = _write(
            "method_proposition_bindings_v1",
            proposition_bindings.model_dump(mode="json"),
            product=False,
        )
    if proposition_clusters:
        paths["method_proposition_clusters_v1"] = _write(
            "method_proposition_clusters_v1",
            {
                "schema_version": "1.0",
                "clusters": [
                    item.model_dump(mode="json") for item in proposition_clusters
                ],
            },
            product=False,
        )
    if proposition_architect_traces:
        paths["method_proposition_architect_calls_v1"] = _write(
            "method_proposition_architect_calls_v1",
            {
                "schema_version": "1.0",
                "calls": list(proposition_architect_traces),
            },
            product=False,
        )
    if proposition_evidence_judge_traces:
        paths["method_proposition_evidence_judge_calls_v1"] = _write(
            "method_proposition_evidence_judge_calls_v1",
            {
                "schema_version": "1.0",
                "calls": list(proposition_evidence_judge_traces),
            },
            product=False,
        )
    if concept_cards is not None:
        paths["method_concept_cards_v1"] = _write(
            "method_concept_cards_v1",
            concept_cards.model_dump(mode="json"),
            product=False,
        )
    argument_briefs = planning.get("argument_briefs")
    if argument_briefs is not None:
        paths["method_argument_briefs_v1"] = _write(
            "method_argument_briefs_v1",
            argument_briefs.model_dump(mode="json"),
            product=False,
        )
    if argument_facets or facet_alignment_result is not None:
        paths["method_argument_facets_v1"] = _write(
            "method_argument_facets_v1",
            {
                "schema_version": "1.0",
                "facets": [
                    item.model_dump(mode="json") for item in argument_facets
                ],
            },
            product=False,
        )
        paths["facet_evidence_alignments_v1"] = _write(
            "facet_evidence_alignments_v1",
            {
                "schema_version": "1.0",
                "alignments": [
                    item.model_dump(mode="json") for item in facet_alignments
                ],
            },
            product=False,
        )
        paths["candidate_facet_policies_v1"] = _write(
            "candidate_facet_policies_v1",
            {
                "schema_version": "1.0",
                "policies": [
                    item.model_dump(mode="json") for item in facet_policies
                ],
            },
            product=False,
        )
        if facet_alignment_result is not None:
            paths["method_argument_facet_alignment_trace_v1"] = _write(
                "method_argument_facet_alignment_trace_v1",
                {
                    "schema_version": "1.0",
                    "content_digest": facet_alignment_result.content_digest,
                    "schema_failures": list(
                        facet_alignment_result.schema_failures
                    ),
                    "traces": list(facet_alignment_result.traces),
                },
                product=False,
            )
        paths["publication_field_candidates_v1"] = _write(
            "publication_field_candidates_v1",
            {
                "schema_version": "1.0",
                "candidates": [
                    item.model_dump(mode="json") for item in publication_field_candidates
                ],
            },
            product=False,
        )
        paths["typed_field_deferred_v1"] = _write(
            "typed_field_deferred_v1",
            {
                "schema_version": "1.0",
                "deferred": [
                    item.model_dump(mode="json") for item in typed_field_deferred
                ],
            },
            product=False,
        )
    if readiness is not None:
        paths["plan_product_readiness_v1"] = _write(
            "plan_product_readiness_v1",
            readiness.model_dump(mode="json"),
            product=False,
        )
    paths["review_candidates"] = _write(
        "review_candidates",
        [item.model_dump(mode="json") for item in review_candidates],
    )
    paths["agent_trace"] = _write("agent_trace", agent_trace)
    paths["run_summary"] = _write("run_summary", summary)
    if revision_journal is not None:
        # R10 §15.6: the revision journal travels with the same artifact map as
        # the handoff/checkpoint so resume can check which revision is current.
        from code2paper.agentic.research_revision_contract import (
            write_revision_journal,
        )

        journal_path = write_revision_journal(out_root, revision_journal)
        paths["research_revision_journal_v1"] = str(journal_path)
    return paths


def _build_research_trace(loop_result: ResearchLoopResult) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "turns_executed": loop_result.turns_executed,
        "terminated": loop_result.terminated,
        "termination_reason": loop_result.termination_reason,
        "evidence_critic_routes": list(loop_result.evidence_critic_routes),
        "decision_trace": [
            item.model_dump(mode="json") for item in loop_result.decision_trace
        ],
        "policy_merge_trace": [
            item.model_dump(mode="json") for item in loop_result.policy_merge_trace
        ],
        "node_trace": list(loop_result.node_trace),
    }


def _write_closure_metrics(
    *,
    out_root: Path,
    loop_result: ResearchLoopResult,
    planning: dict[str, Any],
    summary: Mapping[str, Any] | None = None,
) -> str:
    """Persist the compact quality-closure dashboard from frozen artifacts."""

    root = Path(out_root).expanduser().resolve()
    artifact_dir = root / "artifacts"
    ledger = getattr(loop_result.loop_state, "candidate_acquisition_ledger", None)
    records = tuple(getattr(ledger, "records", ()) or ())
    target_records = tuple(
        item for item in records
        if item.ownership_role in {"target_core", "target_dependency"}
    )
    acquired = sum(item.terminal_status == "acquired_and_compiled" for item in target_records)
    rejected = sum(item.terminal_status in {"explicitly_rejected", "superseded"} for item in target_records)
    comparand_records = tuple(item for item in records if item.ownership_role in {"comparand", "evaluation"})
    comparand_packets = sum(bool(item.packet_ids) for item in comparand_records)

    candidates = tuple(planning.get("publication_field_candidates") or ())
    deferred = tuple(planning.get("typed_field_deferred") or ())
    candidate_by_id = {str(item.candidate_id): item for item in candidates}
    hard_targets = 0
    hard_from_unresolved = 0
    support_slots = 0
    publication_slots = 0
    required_formula_ids: set[str] = set()
    plan = planning.get("plan")
    if plan is not None:
        for section in getattr(plan, "sections", ()) or ():
            for paragraph in getattr(section, "paragraphs", ()) or ():
                required_fields = tuple(getattr(paragraph, "required_field_candidate_ids", ()) or ())
                hard_targets += len(required_fields)
                for candidate_id in required_fields:
                    candidate = candidate_by_id.get(str(candidate_id))
                    if candidate is None or not getattr(candidate, "is_consumable", False):
                        hard_from_unresolved += 1
                support_slots += len(getattr(paragraph, "support_slot_ids", ()) or ())
                publication_slots += len(getattr(paragraph, "required_publication_slot_ids", ()) or ())
                required_formula_ids.update(str(item) for item in getattr(paragraph, "formula_obligation_ids", ()) or ())

    writer_paragraphs = 0
    writer_witnesses = 0
    valid_required_paragraphs = 0
    writer_path = artifact_dir / "06_authoring" / "publication_writer_result_v1.json"
    if writer_path.is_file():
        try:
            writer_payload = json.loads(writer_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            writer_payload = {}
        for section in writer_payload.get("section_results") or ():
            output = section.get("output") if isinstance(section, Mapping) else None
            if not isinstance(output, Mapping):
                continue
            for paragraph in output.get("paragraphs") or ():
                if not isinstance(paragraph, Mapping):
                    continue
                writer_paragraphs += 1
                writer_witnesses += len(paragraph.get("witnesses") or ())
                if paragraph.get("transaction_valid") is True or paragraph.get("valid") is True:
                    valid_required_paragraphs += 1

    trace_summary: Mapping[str, Any] = {}
    trace_path = artifact_dir / "research_product" / "method_content_trace_v1.json"
    if trace_path.is_file():
        try:
            trace_payload = json.loads(trace_path.read_text(encoding="utf-8"))
            trace_summary = trace_payload.get("summary") or {}
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            trace_summary = {}
    formalization_path = artifact_dir / "06_authoring" / "formalization_section_results_v1.json"
    accepted_formula = 0
    if formalization_path.is_file():
        try:
            formalization_payload = json.loads(formalization_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            formalization_payload = {}
        accepted_formula = sum(
            1 for section in formalization_payload.get("sections") or ()
            for package in (section.get("packages") or ())
            if isinstance(package, Mapping) and str(package.get("package_id") or "").strip()
        )

    from code2paper.agentic.intent_spine_metrics import compile_research_closure_dashboard

    facets_payload: dict[str, Any] = {}
    facets_path = artifact_dir / "method_argument_facets_v1.json"
    if facets_path.is_file():
        try:
            facets_payload = json.loads(facets_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            facets_payload = {}
    facet_rows = tuple(facets_payload.get("facets") or ())
    atoms_payload: dict[str, Any] = {}
    atoms_path = artifact_dir / "06_authoring" / "intent_evidence_atoms_v1.json"
    if not atoms_path.is_file():
        atoms_path = artifact_dir / "intent_evidence_atoms_v1.json"
    if atoms_path.is_file():
        try:
            atoms_payload = json.loads(atoms_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            atoms_payload = {}
    author_formula_ids = tuple(sorted(required_formula_ids))
    mechanism_obligations: list[Any] = []
    formula_ob_path = artifact_dir / "06_authoring" / "mechanism_formula_obligations_v1.json"
    if formula_ob_path.is_file():
        try:
            formula_ob_payload = json.loads(formula_ob_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            formula_ob_payload = {}
        by_mechanism = formula_ob_payload.get("by_mechanism") or {}
        if isinstance(by_mechanism, Mapping):
            for rows in by_mechanism.values():
                if isinstance(rows, list):
                    mechanism_obligations.extend(rows)
    accepted_packages: list[Any] = []
    package_path = artifact_dir / "06_authoring" / "mechanism_formula_packages_v2.json"
    if package_path.is_file():
        try:
            package_payload = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            package_payload = {}
        accepted_packages = list(package_payload.get("packages") or ())
    dashboard = compile_research_closure_dashboard(
        records=target_records,
        publication_field_candidates=candidates,
        typed_field_deferred=deferred,
        intent_atoms=tuple(atoms_payload.get("atoms") or ()),
        atom_closures=tuple(atoms_payload.get("closures") or ()),
        atom_ids_by_legacy_field={
            str(key): tuple(str(item) for item in (values or ()))
            for key, values in dict(atoms_payload.get("legacy_field_to_atom_trace") or {}).items()
        },
        legacy_field_ids=tuple(
            str(item.get("facet_id") or "")
            for item in facet_rows
            if isinstance(item, Mapping) and str(item.get("facet_id") or "").strip()
        ),
        must_cover_obligation_ids=tuple(
            dict.fromkeys(
                str(getattr(item, "obligation_id", "") or "")
                for item in target_records
                if str(getattr(item, "obligation_id", "") or "").strip()
            )
        ),
        author_formula_ids=author_formula_ids,
        mechanism_obligations=mechanism_obligations,
        accepted_packages=accepted_packages,
        consumed_package_ids=tuple(
            str(item)
            for item in (
                (trace_summary.get("consumed_formula_package_ids") or ())
                if isinstance(trace_summary, Mapping) else ()
            )
            if str(item).strip()
        ),
        planning_targets={
            "hard_targets": hard_targets,
            "support_slots": support_slots,
            "publication_slots": publication_slots,
        },
    )
    identity_path = artifact_dir / "06_authoring" / "formula_identity_conservation_v1.json"
    try:
        identity_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(identity_path, _json_text(dashboard.get("formula_identity") or {}))
    except OSError:
        identity_path = artifact_dir / "formula_identity_conservation_v1.json"
        _atomic_write_text(identity_path, _json_text(dashboard.get("formula_identity") or {}))
    research_metrics = dict(dashboard.get("research") or {})
    research_metrics.update({
        "acquired": acquired,
        "explicitly_rejected": rejected,
        "comparand_packet_ratio": (
            (comparand_packets / len(comparand_records)) if comparand_records else 0.0
        ),
    })
    alignment_metrics = dict(dashboard.get("alignment") or {})
    alignment_metrics["hard_target_from_unresolved"] = hard_from_unresolved
    metrics = {
        "schema_version": "2.0",
        "research": research_metrics,
        "alignment": alignment_metrics,
        "planning": dict(dashboard.get("planning") or {
            "hard_targets": hard_targets,
            "support_slots": support_slots,
            "publication_slots": publication_slots,
        }),
        "formula_identity_path": str(identity_path),
        "writer": {
            "paragraphs": writer_paragraphs,
            "witnesses": writer_witnesses,
            "valid_required_paragraphs": valid_required_paragraphs,
        },
        "formula": {
            "required": len(required_formula_ids),
            "accepted": accepted_formula,
            "consumed": int(trace_summary.get("consumed_formula_packages") or 0),
            "duplicate_consumers": int(trace_summary.get("duplicate_formula_consumers") or 0),
        },
        "verification": {
            "rendered_invalid": int(trace_summary.get("rendered_invalid") or 0),
            "repository_verified_nonempty": bool(
                (artifact_dir / "06_authoring" / "repository_verified_method.md").is_file()
                and (artifact_dir / "06_authoring" / "repository_verified_method.md").stat().st_size > 0
            ),
            "structural_exit": bool((summary or {}).get("structural_exit", False)),
        },
    }
    path = artifact_dir / "method_authoring_closure_metrics_v1.json"
    _atomic_write_text(path, _json_text(metrics))
    return str(path)


def _writer_callback_summary(out_root: str | Path) -> dict[str, int]:
    bundle_path = (
        Path(out_root).expanduser().resolve()
        / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json"
    )
    fulfilled = 0
    external = 0
    pending = 0
    if bundle_path.is_file():
        try:
            payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        for request in payload.get("requests") or ():
            lane = str(request.get("required_authority_lane") or "")
            if lane in {"author_attested", "empirical_artifact", "external_literature", "expository_bridge"}:
                external += 1
            if request.get("status") == "fulfilled":
                fulfilled += 1
            elif request.get("status") == "open":
                pending += 1
    return {
        "callbacks_fulfilled": fulfilled,
        "external_queue_items": external,
        "callbacks_pending": pending,
    }


def _load_review_counts(out_root: str | Path) -> dict[str, int]:
    review_path = (
        Path(out_root).expanduser().resolve()
        / "artifacts" / "06_authoring" / "author_review_candidates.json"
    )
    if not review_path.is_file():
        return {"review_items": 0}
    try:
        payload = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"review_items": 0}
    return {"review_items": len(payload.get("items") or [])}


def _candidate_validation_state(out_root: str | Path) -> dict[str, Any]:
    """Read reverse-validation results for the full editable candidate."""

    root = Path(out_root).expanduser().resolve()
    validation_path = root / "artifacts" / "07_validation" / "agentic_text_evidence_validation.json"
    if validation_path.is_file():
        try:
            payload = json.loads(validation_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "status": "unknown",
                "unsupported_positive_claims": 0,
            }
        return {
            "status": str(payload.get("status") or "unknown"),
            "unsupported_positive_claims": int(payload.get("unsupported_claims") or 0),
            "unverified_claims": int(payload.get("unverified_claims") or 0),
            "checked_factual_claims": int(payload.get("checked_factual_claims") or 0),
            "supported_claims": int(payload.get("supported_claims") or 0),
        }
    quality_path = root / "artifacts" / "07_validation" / "publication_quality_report_v1.json"
    if not quality_path.is_file():
        return {
            "status": "not_run",
            "unsupported_positive_claims": 0,
        }
    try:
        payload = json.loads(quality_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "unknown",
            "unsupported_positive_claims": 0,
        }
    safety = payload.get("safety") or {}
    return {
        "status": str(payload.get("status") or "unknown"),
        "unsupported_positive_claims": int(
            safety.get("unsupported_positive_claims") or 0
        ),
    }


def _proposition_quality_state(out_root: str | Path) -> dict[str, Any]:
    root = Path(out_root).expanduser().resolve()
    quality_path = root / "artifacts" / "07_validation" / "publication_quality_report_v1.json"
    alignment_path = root / "artifacts" / "07_validation" / "method_proposition_alignment_v1.json"
    alignment_calls_path = root / "artifacts" / "07_validation" / "method_proposition_alignment_calls_v1.json"
    result: dict[str, Any] = {
        "planned_required_propositions": 0,
        "rendered_required_propositions": 0,
        "validated_required_propositions": 0,
        "deferred_required_propositions": 0,
        "rendered_proposition_recall": 0.0,
        "validated_proposition_recall": 0.0,
        "semantic_alignment_calls": 0,
        "semantic_alignment_ambiguous": 0,
        "semantic_alignment_trace_count": 0,
        "unresolved_required_propositions": 0,
    }
    try:
        if quality_path.is_file():
            utility = (json.loads(quality_path.read_text(encoding="utf-8")).get("utility") or {})
            for key in (
                "planned_required_propositions",
                "rendered_required_propositions",
                "validated_required_propositions",
                "deferred_required_propositions",
                "rendered_proposition_recall",
                "validated_proposition_recall",
                "unresolved_required_propositions",
            ):
                if key in utility:
                    result[key] = utility[key]
        if alignment_path.is_file():
            alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
            result["semantic_alignment_calls"] = int(alignment.get("semantic_alignment_calls") or 0)
            result["semantic_alignment_ambiguous"] = int(alignment.get("semantic_alignment_ambiguous") or 0)
        if alignment_calls_path.is_file():
            call_payload = json.loads(alignment_calls_path.read_text(encoding="utf-8"))
            result["semantic_alignment_trace_count"] = len(call_payload.get("calls") or ())
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        result["status"] = "unknown"
    return result


def _verified_validation_state(out_root: str | Path) -> dict[str, Any]:
    """Report the verified document's own fail-closed split semantics.

    The sentence validator runs on the candidate.  The verified document is
    then reconstructed solely from qualifying verdicts, so its status must be
    read from the persisted split report rather than copied from the candidate
    validation artifact.
    """

    root = Path(out_root).expanduser().resolve()
    bundle_path = root / "artifacts" / "06_authoring" / "method_draft_bundle_v1.json"
    verified_path = root / "artifacts" / "06_authoring" / "repository_verified_method.md"
    if not bundle_path.is_file() or not verified_path.is_file():
        return {"status": "not_run", "unsupported_positive_claims": 0}
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unknown", "unsupported_positive_claims": 0}
    split = bundle.get("validation_split_report") or {}
    split_mode = str(split.get("split_mode") or "")
    if split_mode != "sentence_reverse_validation":
        return {
            "status": "not_run",
            "unsupported_positive_claims": 0,
            "split_mode": split_mode or "unavailable",
        }
    return {
        "status": "passed",
        "unsupported_positive_claims": 0,
        "checked_positive_units": int(split.get("verified_positive_unit_count") or 0),
        "excluded_candidate_units": len(split.get("excluded_units") or ()),
        "split_mode": split_mode,
    }


def _run_autonomous_method_agent_impl(
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    out_root: str | Path,
    llm_config: LLMConfig | None = None,
    max_research_turns: int = 30,
    max_wall_clock_seconds: float | None = None,
    max_callback_rounds: int = 3,
    max_callback_tool_turns_per_request: int = 8,
    method_name: str = "",
    run_id: str = "",
    write_method_text: bool | None = None,
    research_stage_checkpoint: str | Path | None = None,
    authoring_phase_checkpoint: str | Path | None = None,
    concept_cards: Any | None = None,
    compile_concept_cards: bool = False,
    compile_argument_briefs: bool = True,
    authoring_context_mode: str | None = None,
    execution_identity: AuthoringExecutionIdentityV2 | None = None,
) -> MethodAgentRunResultV1:
    """Run the full autonomous Method Agent product path.

    One call takes repo + author intent + claims and produces the research
    artifacts (evidence/facts/claims/completeness/trace/typed gaps), the
    author-intent-first plan with product readiness, and — when a live LLM
    is available and ``write_method_text`` is not False — the
    candidate/verified/review outputs through the Writer surface.

    ``write_method_text`` defaults to ``True`` when a live LLM is
    configured (``has_provider_api_key``), ``False`` otherwise.  Setting it
    to ``False`` keeps the run fully deterministic (research + planning
    artifacts only) with an explicit ``skipped_no_live_llm`` / explicit
    writer status in the summary.

    ``concept_cards`` (optional ``MethodConceptCardSetV1``) switches the
    plan and Writer to the Stage 2/3 concept lane: the Architect binds
    concept cards to units (verified/caveated separation), the Writer
    consumes ``method_concept_cards_v1``, and the callback/fulfillment
    loop carries concept-bearing requests.  Propositions are skipped in
    this mode (mutually exclusive lanes).
    """

    resolved_out = Path(out_root).expanduser().resolve()
    resolved_out.mkdir(parents=True, exist_ok=True)
    effective_run_id = (run_id or "").strip() or (
        "method-agent-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        + "-"
        + hashlib.sha256(str(resolved_out).encode("utf-8")).hexdigest()[:8]
    )
    requested_authoring_context_mode = (
        str(authoring_context_mode or "").strip().casefold() or None
    )
    effective_context_mode, context_mode_source = resolve_authoring_context_mode(
        requested_authoring_context_mode
    )

    effective_llm = llm_config or load_llm_config_from_env()
    live_llm = bool(has_provider_api_key(effective_llm))
    if write_method_text is None:
        write_method_text = live_llm

    agent_trace: list[dict[str, Any]] = []
    started = time.time()

    def _phase(name: str, status: str, detail: dict[str, Any] | None = None) -> None:
        agent_trace.append({
            "phase": name,
            "status": status,
            "detail": detail or {},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 0.0,
        })

    claims_input = load_user_claims(claims_path)
    checkpoint_payload: dict[str, Any] | None = None
    if research_stage_checkpoint:
        checkpoint_payload = json.loads(
            Path(research_stage_checkpoint).read_text(encoding="utf-8")
        )
        checkpoint_claims = UserClaimsInputV1.model_validate(
            checkpoint_payload.get("claims_input") or {}
        )
        if claims_path and checkpoint_claims != claims_input:
            raise ValueError("research_stage_checkpoint_claims_mismatch")
        claims_input = checkpoint_claims
    runtime = build_product_research_runtime(
        repo_path=repo_path,
        author_intent_path=author_intent_path,
        claims=claims_input,
        run_id=effective_run_id,
        llm_config=effective_llm,
        artifact_root=resolved_out / "artifacts" / "research_tool_data",
        intent_graph_override=(
            IntentObligationGraphV2.model_validate(checkpoint_payload["intent_graph"])
            if checkpoint_payload is not None else None
        ),
        agenda_override=(
            ResearchAgendaV1.model_validate(checkpoint_payload["agenda"])
            if checkpoint_payload is not None else None
        ),
        author_constraints_override=(
            AuthorConstraintSetV1.model_validate(
                checkpoint_payload["author_constraints_v1"]
            )
            if checkpoint_payload is not None
            and checkpoint_payload.get("author_constraints_v1")
            else None
        ),
    )
    _phase(
        "input_resolution",
        "ok",
        {
            "repo_path": str(Path(repo_path).expanduser().resolve()),
            "author_intent": str(author_intent_path) if author_intent_path else "",
            "claims": len(claims_input.claims),
            "obligations": len(runtime.agenda.items),
            "live_llm": live_llm,
        },
    )

    candidate_claim_id_map: dict[str, str] = {}
    resumed_revision_journal = None
    if checkpoint_payload is not None:
        from code2paper.agentic.research_revision_contract import (
            RevisionJournalV1 as _RevisionJournalV1,
            load_revision_journal as _load_revision_journal,
        )

        journal_payload = checkpoint_payload.get("revision_journal")
        if journal_payload:
            resumed_revision_journal = _RevisionJournalV1.model_validate(
                journal_payload
            )
        elif checkpoint_payload.get("research_revision_binding_v1"):
            # §15.6: a checkpoint bound to a revision may not resume without
            # that revision's journal.  Resuming with an empty journal would
            # let the same proposal be applied a second time.
            from code2paper.core.output_names import method_output as _method_output

            journal_path = _method_output(
                resolved_out, "research_revision_journal_v1"
            )
            if not Path(journal_path).is_file():
                raise ValueError(
                    "research_stage_checkpoint_revision_journal_missing"
                )
            resumed_revision_journal = _load_revision_journal(journal_path)
    if research_stage_checkpoint:
        (
            loop_result,
            packet_set,
            fact_set,
            claim_set,
            _checkpoint_claims,
        ) = load_research_stage_checkpoint(
            path=research_stage_checkpoint,
            runtime=runtime,
            revision_journal=resumed_revision_journal,
        )
    else:
        loop_result = run_product_research_phase(
            runtime,
            max_turns=int(max_research_turns),
            max_wall_clock_seconds=max_wall_clock_seconds,
        )
        packet_set, fact_set, claim_set = merge_product_evidence(
            loop_result,
            runtime,
            claim_id_map=candidate_claim_id_map,
        )
    research_run_state = _research_run_state(loop_result, runtime)
    revision_journal, revision_binding = _run_revision_state(
        loop_result,
        runtime,
        previous=resumed_revision_journal,
    )
    candidate_handoff = _candidate_handoff_from_loop(loop_result)
    candidate_retry_ledger = _candidate_retry_ledger_for_run(loop_result, runtime)
    candidate_handoff = _rebuild_candidate_handoff_from_product_claims(
        loop_result=loop_result,
        runtime=runtime,
        claim_id_map=candidate_claim_id_map,
        claim_set=claim_set,
        previous=candidate_handoff,
        retry_ledger=candidate_retry_ledger,
        revision_id=revision_journal.current_revision_id(),
    )
    if candidate_handoff is not None:
        # Keep the mutable scheduler snapshot and the explicit checkpoint
        # handoff on the same post-merge identity.  Older runs wrote the
        # scheduler's pre-merge handoff here and the canonical artifact later,
        # which made a valid resume appear to have a missing promotion ledger.
        loop_result.loop_state.intent_schedule["candidate_handoff"] = (
            candidate_handoff.model_dump(mode="json")
        )
    _phase(
        "research_loop",
        "ok" if research_run_state["status"] == "trusted" else research_run_state["status"],
        {
            "turns_executed": loop_result.turns_executed,
            "termination_reason": loop_result.termination_reason,
            "decisions": len(loop_result.decision_trace),
            "autonomous": research_run_state["autonomous"],
            "llm_decisions": research_run_state["llm_decisions"],
            "deterministic_fallback_decisions": research_run_state[
                "deterministic_fallback_decisions"
            ],
            "resumed_from_stage_checkpoint": bool(research_stage_checkpoint),
            "candidate_handoff_ready": bool(
                candidate_handoff is not None and candidate_handoff.eligible
            ),
        },
    )
    _phase(
        "evidence_compile",
        "ok",
        {
            "packets": len(packet_set.packets) if packet_set is not None else 0,
            "facts": len(fact_set.facts) if fact_set is not None else 0,
            "claims": len(claim_set.claims) if claim_set is not None else 0,
            "synthetic_gaps": 0,
        },
    )

    research_checkpoint_path = persist_research_stage_checkpoint(
        out_root=resolved_out,
        runtime=runtime,
        claims_input=claims_input,
        loop_result=loop_result,
        packet_set=packet_set,
        fact_set=fact_set,
        claim_set=claim_set,
        revision_binding=revision_binding,
        revision_journal=revision_journal,
        candidate_handoff=candidate_handoff,
    )

    research_failure_codes = _research_closure_failure_codes(
        loop_result=loop_result,
        runtime=runtime,
        research_run_state=research_run_state,
        packet_set=packet_set,
        fact_set=fact_set,
        claim_set=claim_set,
    )
    loop_identity = loop_result.loop_state
    # WP1 复查：准入阶段用目标仓库 HEAD 作为代理身份；runtime 建立后必须一致，
    # 否则这次执行不能被解释为同一目标身份（拒绝写入写作产物）。
    if execution_identity is not None:
        runtime_target_commit = str(
            getattr(runtime.repo_snapshot, "git_commit", "") or ""
        )
        admitted_commit = str(execution_identity.target_git_commit or "")
        if (
            runtime_target_commit
            and admitted_commit
            and admitted_commit != "unknown"
            and runtime_target_commit != admitted_commit
        ):
            raise ValueError(
                "resume_identity_mismatch:target_repo_commit:"
                f"admitted={admitted_commit}:runtime={runtime_target_commit}"
            )
        # 审计 §A.1.2：准入绑定的目标身份是**内容**身份，runtime 建立后必须复核
        # project tree hash；commit 只作诊断（同一内容换 commit 不应失效）。
        runtime_tree_hash = str(
            getattr(runtime.repo_snapshot, "project_tree_hash", "") or ""
        )
        admitted_tree_hash = str(execution_identity.target_project_tree_hash or "")
        if (
            runtime_tree_hash
            and admitted_tree_hash
            and admitted_tree_hash != "unavailable"
            and runtime_tree_hash != admitted_tree_hash
        ):
            raise ValueError(
                "resume_identity_mismatch:target_project_tree_hash:"
                f"admitted={admitted_tree_hash}:runtime={runtime_tree_hash}"
            )
    run_identity = build_run_identity(
        run_id=effective_run_id,
        repo_root=repo_path,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        symbol_index_digest=str(
            getattr(getattr(loop_identity, "symbol_index", None), "content_digest", "")
            or ""
        ),
        source_manifest_digest=str(
            getattr(getattr(loop_identity, "source_manifest", None), "content_digest", "")
            or ""
        ),
        model_identity=(
            f"{getattr(effective_llm, 'provider', '')}:{getattr(effective_llm, 'model', '')}"
        ).strip(":") or "unknown",
        model_identity_payload=effective_llm.model_dump(mode="json"),
        launcher_payload={
            "entrypoint": "run_autonomous_method_agent",
            "authoring_context_mode": effective_context_mode,
            "max_research_turns": int(max_research_turns),
            "max_wall_clock_seconds": (
                float(max_wall_clock_seconds)
                if max_wall_clock_seconds is not None
                else 0.0
            ),
            "max_callback_rounds": int(max_callback_rounds),
        },
        profile_payload={
            "llm_role": str(getattr(effective_llm, "role", "") or ""),
            "prompt_template_version": str(
                getattr(effective_llm, "prompt_template_version", "") or ""
            ),
            "authoring_context_mode_source": context_mode_source,
        },
        code_sha=str(getattr(runtime.repo_snapshot, "git_commit", "") or "") or None,
    )
    run_identity_path = write_run_identity(resolved_out, run_identity)
    downstream_phases = ("planning",)
    candidate_handoff_allowed = bool(
        candidate_handoff is not None and candidate_handoff.eligible
    )
    if write_method_text and (not research_failure_codes or candidate_handoff_allowed):
        downstream_phases = ("planning", "formalizer", "writer")
    research_admission = build_research_closure_admission(
        run_id=effective_run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        research_status=str(research_run_state.get("status") or "incomplete"),
        failure_codes=research_failure_codes,
        downstream_phases_planned=downstream_phases,
        candidate_handoff_allowed=candidate_handoff_allowed,
        candidate_handoff_id=(
            candidate_handoff.handoff_id if candidate_handoff is not None else ""
        ),
        candidate_warning_codes=(
            candidate_handoff.warning_codes if candidate_handoff is not None else ()
        ),
    )
    research_admission_path = method_output(
        resolved_out,
        "research_closure_admission_v1",
    )
    _atomic_write_text(
        research_admission_path,
        research_admission.model_dump_json(indent=2) + "\n",
    )

    typed_gaps = build_typed_gaps(
        runtime,
        loop_result,
        claim_set=claim_set,
    )
    planning = build_product_planning(
        runtime=runtime,
        packet_set=packet_set,
        fact_set=fact_set,
        claim_set=claim_set,
        claims_input=claims_input,
        method_name=method_name,
        llm_config=(
            effective_llm
            if live_llm
            and not (
                effective_context_mode in {"unified", "shadow_unified"}
                and research_failure_codes
                and not candidate_handoff_allowed
            )
            else None
        ),
        concept_cards=concept_cards,
        compile_concept_cards=compile_concept_cards and live_llm,
        compile_argument_briefs=compile_argument_briefs,
        implementation_scope=getattr(loop_result.loop_state, "implementation_scope", None),
        behavior_graph=getattr(loop_result.loop_state, "behavior_graph", None),
    )
    _phase(
        "planning",
        "ok",
        {
            "plan_built": planning["plan"] is not None,
            "readiness": (
                planning["readiness"].readiness
                if planning["readiness"] is not None
                else "candidate_ready_with_review"
            ),
            "review_candidates": len(planning["review_candidates"]),
            "method_propositions": len(
                planning["method_propositions"].propositions
                if planning.get("method_propositions") is not None else ()
            ),
            "proposition_gaps": len(
                planning["method_propositions"].gaps
                if planning.get("method_propositions") is not None else ()
            ),
        },
    )

    completeness = planning["completeness"]
    review_candidates = planning["review_candidates"]
    readiness = planning["readiness"]
    plan = planning["plan"]
    readiness_failures = (
        tuple(research_failure_codes)
        if effective_context_mode == "unified"
        else ()
    )
    if readiness is not None:
        plan_readiness = (
            "candidate_ready_with_review"
            if effective_context_mode == "unified" and candidate_handoff_allowed
            else "blocked_by_research"
            if effective_context_mode == "unified" and research_failure_codes
            else readiness.readiness
        )
        blocked_reasons = tuple(
            dict.fromkeys((
                *readiness_failures,
                *tuple(readiness.blocked_for_safety_reasons),
            ))
        )
    else:
        plan_readiness = (
            "candidate_ready_with_review"
            if effective_context_mode == "unified" and candidate_handoff_allowed
            else "blocked_by_research"
            if effective_context_mode == "unified" and research_failure_codes
            else "not_built"
        )
        blocked_reasons = tuple(
            dict.fromkeys((
                *readiness_failures,
                *(
                    f"unverified obligation: {item.obligation_id}"
                    for item in completeness.items
                    if item.status not in {"supported_by_repository", "out_of_scope"}
                ),
            ))
        )

    verified_facts = 0
    if fact_set is not None:
        verified_facts = len(fact_set.facts)
    supported_claims = (
        len([item for item in claim_set.claims if item.status in {"supported", "partial"}])
        if claim_set is not None
        else 0
    )

    summary: dict[str, Any] = {
        "schema_version": "1.0",
        "run_id": effective_run_id,
        "repo_path": str(Path(repo_path).expanduser().resolve()),
        "out_root": str(resolved_out),
        "live_llm": live_llm,
        "research": {
            **research_run_state,
            "termination_reason": loop_result.termination_reason,
            "turns_executed": loop_result.turns_executed,
        },
        "run_identity": {
            **run_identity.model_dump(mode="json"),
            "path": run_identity_path,
        },
        "research_admission": research_admission.model_dump(mode="json"),
        "candidate_handoff": (
            candidate_handoff.model_dump(mode="json")
            if candidate_handoff is not None
            else {"eligible": False, "status": "unavailable"}
        ),
        "evidence": {
            "evidence_packets": len(packet_set.packets) if packet_set is not None else 0,
            "code_facts": len(fact_set.facts) if fact_set is not None else 0,
            "verified_facts": verified_facts,
            "atomic_claims": len(claim_set.claims) if claim_set is not None else 0,
            "supported_claims": supported_claims,
            "typed_gaps": len(typed_gaps),
            "explicit_gaps": len(
                [gap for gap in typed_gaps if gap.status == "explicit_gap"]
            ),
            "unresolved_obligations": len(
                [gap for gap in typed_gaps if gap.status == "unresolved"]
            ),
            "synthetic_support_used": False,
        },
        "plan": {
            "plan_built": plan is not None,
            "readiness": plan_readiness,
            "blocked_for_safety_reasons": list(blocked_reasons),
            "review_candidates": len(review_candidates),
            "audit_warnings": (
                len(readiness.audit_warnings) if readiness is not None else 0
            ),
        },
        "writer": {
            "status": "pending",
            "blocked_reason": "",
            "candidate_written": False,
            "verified_written": False,
        },
        "callbacks": {
            "callbacks_fulfilled": 0,
            "external_queue_items": 0,
            "callbacks_pending": 0,
        },
        "review": {"review_items": 0},
        "candidate_validation": {
            "status": "not_run",
            "unsupported_positive_claims": 0,
        },
        "verified_validation": {
            "status": "not_run",
            "unsupported_positive_claims": 0,
        },
        "unsupported_positive_claims_in_verified": 0,
        "artifacts": {},
    }

    paths = persist_product_artifacts(
        out_root=resolved_out,
        runtime=runtime,
        claims_input=claims_input,
        loop_result=loop_result,
        packet_set=packet_set,
        fact_set=fact_set,
        claim_set=claim_set,
        typed_gaps=typed_gaps,
        planning=planning,
        agent_trace=agent_trace,
        summary=summary,
        candidate_handoff=candidate_handoff,
        candidate_retry_ledger=candidate_retry_ledger,
        revision_journal=(
            revision_journal if revision_journal.entries else None
        ),
    )
    paths["research_stage_checkpoint_v1"] = research_checkpoint_path
    paths["run_identity_v1"] = run_identity_path
    paths["research_closure_admission_v1"] = str(research_admission_path)

    writer_status = "skipped_no_live_llm"
    writer_blocked_reason = ""
    writer_paths: dict[str, str] = {}
    writer_artifact_paths = _writer_artifact_paths(resolved_out, persisted_paths=paths)
    writer_artifact_paths.update({
        "run_identity_v1": run_identity_path,
        "research_closure_admission_v1": str(research_admission_path),
    })
    if paths.get("candidate_handoff_v1"):
        writer_artifact_paths["candidate_handoff_v1"] = paths["candidate_handoff_v1"]
    if paths.get("candidate_retry_ledger_v1"):
        writer_artifact_paths["candidate_retry_ledger_v1"] = paths[
            "candidate_retry_ledger_v1"
        ]
    if (
        effective_context_mode == "unified"
        and research_failure_codes
        and not candidate_handoff_allowed
    ):
        # Research closure is a terminal upstream boundary.  Persist one
        # explicit run event and a staged contract here even when the Writer
        # is not requested; downstream phase artifacts are N/A, not missing.
        from code2paper.agentic.unified_invocation_ledger import (
            write_run_terminal_event,
        )

        terminal_path = write_run_terminal_event(
            resolved_out / "artifacts" / "06_authoring" / "invocations",
            run_digest=run_identity.content_digest,
            terminal_reason="research_closure_admission_failed",
            terminal_stage="research_closure",
            extra={
                "failure_codes": list(research_failure_codes),
                "model_calls_allowed": False,
                "downstream_phases_planned": ["planning"],
                "research_admission_id": research_admission.admission_id,
            },
        )
        paths["run_terminal_event"] = str(terminal_path)
        writer_artifact_paths["run_terminal_event"] = str(terminal_path)

        research_boundary_keys = {
            "repo_snapshot_v2",
            "symbol_index_v2",
            "repository_source_manifest_v1",
            "implementation_scope_v1",
            "repository_authoring_artifacts_v1",
            "atomic_claims_v3",
            "code_facts_v1",
            "equation_claims_v1",
            "configuration_claims_v1",
            "method_completeness_matrix_v1",
            "intent_obligation_graph_v2",
            "research_agenda_v1",
            "candidate_handoff_v1",
        }
        contract = build_authoring_run_contract(
            requested_mode=effective_context_mode,
            effective_mode=effective_context_mode,
            mode_source=context_mode_source,
            artifact_paths={**writer_artifact_paths, **paths},
            run_id=effective_run_id,
            repo_snapshot_id=run_identity.repo_snapshot_id,
            project_tree_hash=run_identity.project_tree_hash,
            code_sha=run_identity.code_commit_sha,
            run_identity=run_identity,
            not_applicable_artifact_keys=tuple(
                key
                for key in expected_authoring_artifact_keys(effective_context_mode)
                if key not in research_boundary_keys
            ),
            contract_stage="research_closure",
        )
        contract_path = write_authoring_run_contract(resolved_out, contract)
        paths["authoring_run_contract_v1"] = contract_path
        writer_artifact_paths["authoring_run_contract_v1"] = contract_path
    if (
        write_method_text
        and effective_context_mode == "unified"
        and research_failure_codes
        and not candidate_handoff_allowed
    ):
        # Research closure is a hard pre-admission boundary.  Do not invoke
        # the Writer (or create Formalizer/Writer phase admissions) when the
        # repository evidence is still unresolved.
        writer_status = "blocked"
        writer_blocked_reason = (
            "research_closure_admission_failed:"
            + ",".join(research_failure_codes)
        )
    elif write_method_text:
        writer_paths, writer_status, writer_blocked_reason = _run_writer_surface(
            out_root=resolved_out,
            artifact_paths=dict(sorted(writer_artifact_paths.items())),
            llm_config=effective_llm,
            run_id=effective_run_id,
            authoring_context_mode=requested_authoring_context_mode,
            authoring_phase_checkpoint=authoring_phase_checkpoint,
        )
    else:
        writer_blocked_reason = (
            "no_live_llm" if not live_llm else "write_method_text_disabled"
        )
    _phase(
        "writer",
        writer_status,
        {"blocked_reason": writer_blocked_reason},
    )

    callback_fulfillment = None
    callback_bundle_path = str(
        writer_paths.get("writing_research_callback_artifacts_v1")
        or writer_artifact_paths.get("writing_research_callback_artifacts_v1")
        or ""
    )
    if write_method_text and (
        writer_status in {"incomplete", "success"}
        or (
            callback_bundle_path
            and Path(callback_bundle_path).is_file()
        )
    ):
        # Package F: run the bounded callback fulfillment/resume loop after the
        # first Writer call.  Open local-owned requests (repository/config/
        # formalization) are executed against the frozen repository evidence;
        # external lanes stay in their queues.  Only affected sections resume.
        from code2paper.agentic.writing_callback_fulfillment import (
            WritingCallbackFulfillmentBudgetV1,
            fulfill_and_resume_writing_callbacks,
        )

        writer_paths, writer_status, writer_blocked_reason, callback_fulfillment = (
            fulfill_and_resume_writing_callbacks(
                runtime=runtime,
                out_root=resolved_out,
                artifact_paths=dict(sorted(writer_artifact_paths.items())),
                writer_paths=writer_paths,
                llm_config=effective_llm,
                budget=WritingCallbackFulfillmentBudgetV1(
                    max_callback_rounds=max(0, int(max_callback_rounds)),
                    max_tool_turns_per_request=max(1, int(max_callback_tool_turns_per_request)),
                ),
                llm_caller=None,
                # Review P0 (Q4): route Writer callbacks through the ORIGINAL
                # checkpointed Research LangGraph — the same research thread,
                # agenda and evidence restored from the stage checkpoint.
                research_stage_checkpoint=paths["research_stage_checkpoint_v1"],
                method_name=method_name,
                authoring_context_mode=requested_authoring_context_mode,
            )
        )
        _phase(
            "writer_callback_fulfillment",
            (
                "ok"
                if callback_fulfillment.stopped_reason
                in {"writer_success", "no_open_local_requests", "no_open_requests"}
                else "incomplete"
            ),
            callback_fulfillment.model_dump(mode="json"),
        )

    callback_counts = _writer_callback_summary(resolved_out)
    review_counts = _load_review_counts(resolved_out)
    if review_counts["review_items"] == 0 and review_candidates:
        review_counts["review_items"] = len(review_candidates)
    candidate_validation = _candidate_validation_state(resolved_out)
    verified_validation = _verified_validation_state(resolved_out)

    paths.update(writer_paths)
    if callback_fulfillment is not None:
        if callback_fulfillment.trace_path:
            paths["research_continuation_trace_v1"] = (
                callback_fulfillment.trace_path
            )
        callback_counts.update({
            "local_requests_seen": callback_fulfillment.local_requests_seen,
            "callbacks_fulfilled": callback_fulfillment.local_requests_fulfilled,
            "callbacks_pending": max(
                0,
                callback_fulfillment.local_requests_seen
                - callback_fulfillment.local_requests_fulfilled,
            ),
            "external_queue_items": callback_fulfillment.external_requests_seen,
            "rounds_attempted": callback_fulfillment.rounds_attempted,
            "resumed_section_ids": list(callback_fulfillment.resumed_section_ids),
            "stopped_reason": callback_fulfillment.stopped_reason,
        })
    # WP0/WP7: build the source-to-render ledger only after Writer and any
    # bounded callback resume have committed their artifacts.  The ledger is
    # diagnostic metadata (ids/statuses/digests), never a new authority path.
    try:
        from code2paper.agentic.method_content_trace import write_method_content_trace

        content_trace_path = (
            resolved_out / "artifacts" / "research_product" / "method_content_trace_v1.json"
        )
        content_trace = write_method_content_trace(
            content_trace_path,
            {**paths, **writer_paths},
        )
        paths["method_content_trace_v1"] = str(content_trace_path)
        summary["content_chain"] = {
            **content_trace.summary,
            "content_digest": content_trace.content_digest,
            "trace_path": str(content_trace_path),
        }
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        summary["content_chain"] = {
            "rows": 0,
            "status": "unavailable",
        }
    try:
        summary["closure_metrics_path"] = _write_closure_metrics(
            out_root=resolved_out,
            loop_result=loop_result,
            planning=planning,
            summary=summary,
        )
        paths["method_authoring_closure_metrics_v1"] = summary["closure_metrics_path"]
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    # The product-authoring graph is a durable orchestration overlay around
    # the existing research and Writer owners.  Persist it only after the
    # concrete artifacts above are committed; it must never alter the legacy
    # local_text_repair route or turn missing evidence into support.
    product_issues: list[ProductAuthoringIssueV1] = []
    for gap in typed_gaps:
        if gap.status not in {"explicit_gap", "unresolved", "blocked"}:
            continue
        product_issues.append(ProductAuthoringIssueV1(
            issue_id=f"research:{gap.gap_id}",
            issue_type="evidence_gap",
            owner=(
                "review"
                if gap.status == "explicit_gap"
                else "research_continuation"
            ),
            source="research_graph",
            reason=gap.reason or gap.stopping_reason,
        ))
    for failure_code in research_failure_codes:
        product_issues.append(ProductAuthoringIssueV1(
            issue_id=f"research-admission:{failure_code}",
            issue_type="research_admission",
            owner="research_continuation",
            source="research_closure_admission_v1",
            reason=failure_code,
        ))
    if writer_status in {"incomplete", "blocked"}:
        product_issues.append(ProductAuthoringIssueV1(
            issue_id="writer:product_status",
            issue_type="writer_incomplete",
            owner="writer",
            source="publication_method_writer",
            reason=writer_blocked_reason or writer_status,
        ))
    callback_bundle_value = (
        paths.get("writing_research_callback_artifacts_v1")
        or writer_paths.get("writing_research_callback_artifacts_v1")
        or ""
    )
    if callback_bundle_value and Path(callback_bundle_value).is_file():
        try:
            callback_payload = json.loads(
                Path(callback_bundle_value).read_text(encoding="utf-8")
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            callback_payload = {}
        for request in callback_payload.get("requests") or ():
            if not isinstance(request, dict):
                continue
            if str(request.get("status") or "") not in {"open", "partial"}:
                continue
            request_id = str(request.get("request_id") or "").strip()
            if not request_id:
                continue
            lane = str(request.get("required_authority_lane") or "")
            product_issues.append(ProductAuthoringIssueV1(
                issue_id=f"callback:{request_id}",
                issue_type="writing_research_callback",
                owner=(
                    "research_continuation"
                    if lane in {
                        "executable_hard",
                        "configuration_resolved",
                        "formal_derivation",
                    }
                    else "review"
                ),
                section_id=str(request.get("section_id") or ""),
                source="section_writer_callback",
                reason="writing-time callback remains open",
            ))
    candidate_path_value = str(
        writer_paths.get("publication_candidate_method")
        or paths.get("publication_candidate_method")
        or ""
    )
    verified_path_value = str(
        writer_paths.get("repository_verified_method")
        or paths.get("repository_verified_method")
        or ""
    )

    def _nonempty_file(value: str) -> bool:
        if not value:
            return False
        path = Path(value)
        if not path.is_file():
            return False
        try:
            return bool(path.read_text(encoding="utf-8").strip())
        except (OSError, UnicodeError):
            return False

    candidate_nonempty = _nonempty_file(candidate_path_value)
    verified_nonempty = _nonempty_file(verified_path_value)
    verified_integrity_passed = verified_validation.get("status") == "passed"
    research_blocked = bool(research_failure_codes) or research_run_state.get(
        "status"
    ) in {"blocked", "incomplete"}
    if research_blocked and not candidate_nonempty:
        product_terminal_status = "blocked"
    elif writer_status == "blocked" and not candidate_nonempty:
        product_terminal_status = "blocked"
    elif (
        candidate_nonempty
        and verified_nonempty
        and verified_integrity_passed
        and writer_status == "success"
        and not product_issues
    ):
        product_terminal_status = "completed"
    elif candidate_nonempty:
        product_terminal_status = "review_ready_with_warnings"
    else:
        product_terminal_status = "incomplete"
    try:
        _product_state, product_state_path = (
            persist_product_authoring_state_from_writer(
                out_root=resolved_out,
                artifact_paths={**writer_artifact_paths, **paths},
                run_id=effective_run_id,
                open_issues=product_issues,
                affected_section_ids=(
                    *tuple(
                        callback_fulfillment.resumed_section_ids
                        if callback_fulfillment is not None else ()
                    ),
                ),
                terminal_status=product_terminal_status,
                stop_reason=(
                    writer_blocked_reason
                    or (
                        callback_fulfillment.stopped_reason
                        if callback_fulfillment is not None else ""
                    )
                    or (
                        "authoring_complete"
                        if writer_status == "success" and not product_issues
                        else "authoring_requires_review"
                    )
                ),
            )
        )
        paths["product_authoring_state_v1"] = product_state_path
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    product_state_path = paths.get("product_authoring_state_v1", "")
    if product_state_path and Path(product_state_path).is_file():
        try:
            product_state_payload = json.loads(
                Path(product_state_path).read_text(encoding="utf-8")
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            product_state_payload = {}
        summary["product_authoring"] = {
            "state_path": product_state_path,
            "content_digest": str(
                product_state_payload.get("content_digest") or ""
            ),
            "revision_id": str(product_state_payload.get("revision_id") or ""),
            "terminal_status": str(
                product_state_payload.get("terminal_status") or ""
            ),
            "invalidated_surfaces": list(
                product_state_payload.get("invalidated_surfaces") or ()
            ),
        }
    writer_summary: dict[str, Any] = {
        "status": writer_status,
        "blocked_reason": writer_blocked_reason,
        "candidate_written": bool(
            writer_paths.get("publication_candidate_method")
        ),
        "verified_written": bool(writer_paths.get("repository_verified_method")),
    }
    # Q0: the runner summary reads the independent candidate-first status
    # fields from the persisted Writer result (plan 19.9).
    writer_result_path = resolved_out / "artifacts" / "06_authoring" / "publication_writer_result_v1.json"
    if writer_result_path.is_file():
        try:
            writer_payload = json.loads(writer_result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            writer_payload = {}
        for key in (
            "requested_authoring_context_mode",
            "effective_authoring_context_mode",
            "authoring_context_mode_source",
            "authoring_run_contract_digest",
            "candidate_generation_status",
            "candidate_available",
            "candidate_completion_status",
            "candidate_complete",
            "candidate_blocking_reasons",
            "verified_complete",
            "verified_blocking_reasons",
            "candidate_validation_status",
            "candidate_warnings_by_severity",
            "verified_validation_status",
            "publication_ready",
        ):
            if key in writer_payload:
                writer_summary[key] = writer_payload[key]
    summary["writer"] = writer_summary
    summary["callbacks"] = callback_counts
    summary["review"] = review_counts
    summary["candidate_validation"] = candidate_validation
    summary["verified_validation"] = verified_validation
    summary["proposition_quality"] = _proposition_quality_state(resolved_out)
    # The reverse-validator's ``unsupported_claims`` counts sentences in the
    # CANDIDATE that no repository evidence supports (author-intent /
    # candidate material is expected there).  The verified document is built
    # by the fail-closed sentence splitter and can only contain supported (or
    # qualifier-guarded partial) units, so the verified-side count is 0 by
    # construction once the split ran.  Report both numbers honestly.
    summary["unsupported_positive_claims_in_candidate"] = (
        candidate_validation["unsupported_positive_claims"]
    )
    summary["unsupported_positive_claims_in_verified"] = (
        verified_validation["unsupported_positive_claims"]
    )
    # Route-2 visibility (see `.agent/implementation.md`): a run whose
    # proposal calls were measured records the tally in its summary and names
    # the accounting it belongs to, so "proposal calls are metered" can never
    # be read as "they are part of the run's planned/reserved accounting".
    # Runs without measured proposal calls add nothing.
    summary.update(_proposal_accounting_summary(paths))
    summary["artifacts"] = dict(sorted(paths.items()))
    summary["authoring_context"] = {
        "requested_mode": requested_authoring_context_mode or "",
        "writer_mode": str(writer_summary.get("effective_authoring_context_mode") or ""),
        "run_contract_path": str(paths.get("authoring_run_contract_v1") or ""),
    }

    if not paths.get("run_terminal_event"):
        try:
            from code2paper.agentic.unified_invocation_ledger import write_run_terminal_event

            terminal_path = write_run_terminal_event(
                resolved_out / "artifacts" / "06_authoring" / "invocations",
                run_digest=run_identity.content_digest,
                terminal_reason=loop_result.termination_reason,
                terminal_stage="writer" if write_method_text else "research",
                extra={
                    "run_id": effective_run_id,
                    "research_status": research_run_state.get("status", ""),
                    "candidate_handoff_allowed": candidate_handoff_allowed,
                    "writer_status": writer_status,
                },
            )
            paths["run_terminal_event"] = str(terminal_path)
        except (OSError, TypeError, ValueError):
            pass
    summary["artifacts"] = dict(sorted(paths.items()))

    agent_trace.append({
        "phase": "finalize",
        "status": "ok",
        "detail": {"total_duration_ms": round((time.time() - started) * 1000, 1)},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((time.time() - started) * 1000, 1),
    })
    _atomic_write_text(resolved_out / "artifacts" / "research_product" / "agent_trace.json", _json_text(agent_trace))
    # 审计 §F.1/§F.4/§F.5：run summary 是索引里的 run_summary:terminal 产物，发布时
    # 走 journaled 事务并注册，读者再用 read_artifact_validated 验证字节后使用。
    from code2paper.agentic.authoring_artifact_publication import (
        publish_artifact_transaction,
    )

    _summary_target = resolved_out / "artifacts" / "research_product" / "run_summary.json"
    _summary_tx = publish_artifact_transaction(
        resolved_out,
        role="run_summary",
        phase="terminal",
        target_path=_summary_target,
        payload=_json_text(summary).encode("utf-8"),
        generation=1,
        producer="autonomous_method_agent.finalize",
        upstream_refs=(
            f"run:{effective_run_id}",
            f"repo:{Path(repo_path).expanduser().resolve()}",
        ),
    )
    if _summary_tx.state != "complete":
        raise ValueError(
            "run_summary_publish_incomplete:"
            + ",".join(_summary_tx.failures or (_summary_tx.state,))
        )

    return MethodAgentRunResultV1(
        run_id=effective_run_id,
        repo_path=str(Path(repo_path).expanduser().resolve()),
        out_root=str(resolved_out),
        research_status=(
            research_run_state["status"]
        ),
        research_termination_reason=loop_result.termination_reason,
        research_turns=loop_result.turns_executed,
        plan_built=plan is not None,
        plan_readiness=plan_readiness,
        plan_blocked_reasons=blocked_reasons,
        writer_status=writer_status,
        writer_blocked_reason=writer_blocked_reason,
        artifact_paths=paths,
        summary=summary,
    )


class MethodAgentSignal(RuntimeError):
    """Internal signal exception used to durable-close the product run."""

    def __init__(self, signum: int) -> None:
        self.signum = int(signum)
        super().__init__(f"method agent interrupted by signal {self.signum}")


def _effective_method_run_id(out_root: str | Path, run_id: str) -> str:
    resolved_out = Path(out_root).expanduser().resolve()
    return (run_id or "").strip() or (
        "method-agent-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        + "-"
        + hashlib.sha256(str(resolved_out).encode("utf-8")).hexdigest()[:8]
    )


def _latest_research_checkpoint(out_root: Path) -> dict[str, Any]:
    """Read the newest immutable checkpoint without trusting its contents."""

    checkpoint_root = out_root / "artifacts" / "research_tool_data" / "immutable_checkpoints"
    candidates: list[Path] = []
    if checkpoint_root.is_dir():
        try:
            candidates = [
                path for path in checkpoint_root.glob("*.json") if path.is_file()
            ]
        except OSError:
            candidates = []

    def _mtime_key(path: Path) -> tuple[int, str]:
        try:
            return path.stat().st_mtime_ns, path.name
        except OSError:
            return 0, path.name

    candidates.sort(key=_mtime_key)
    if not candidates:
        return {}
    path = candidates[-1]
    try:
        encoded = path.read_bytes()
        payload = json.loads(encoded)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return {"path": str(path), "readable": False}
    if not isinstance(payload, dict):
        payload = {}
    agenda = payload.get("agenda_items") or ()
    checkpoint_digest = (
        "sha256:" + path.stem
        if len(path.stem) == 64
        else "sha256:" + hashlib.sha256(encoded.rstrip(b"\n")).hexdigest()
    )
    return {
        "path": str(path),
        "digest": checkpoint_digest,
        "file_digest": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        "readable": True,
        "turn_index": int(payload.get("turn_index") or 0),
        "agenda_statuses": {
            str(item.get("obligation_id") or ""): str(item.get("status") or "")
            for item in agenda
            if isinstance(item, dict) and str(item.get("obligation_id") or "").strip()
        },
        "post_partial_retry_counts": dict(payload.get("post_partial_retry_counts") or {}),
        "intent_schedule": dict(payload.get("intent_schedule") or {}),
    }


def _persist_partial_method_run(
    *,
    out_root: Path,
    run_id: str,
    exc: BaseException,
) -> dict[str, str]:
    """Persist failure evidence even when the synchronous graph never returns."""

    checkpoint = _latest_research_checkpoint(out_root)
    attempt_id = str(
        os.environ.get("CODE2PAPER_METHOD_AGENT_ATTEMPT_ID", "") or ""
    ).strip()
    if isinstance(exc, MethodAgentSignal):
        terminal_reason = f"signal_{exc.signum}"
        exit_type = "signal"
    elif isinstance(exc, KeyboardInterrupt):
        terminal_reason = "keyboard_interrupt"
        exit_type = "keyboard_interrupt"
    elif isinstance(exc, SystemExit):
        terminal_reason = "system_exit"
        exit_type = "system_exit"
    else:
        terminal_reason = "exception"
        exit_type = "exception"
    partial_path = out_root / "artifacts" / "research_product" / "run_summary.partial.json"
    payload = {
        "schema_version": "1.0",
        "run_id": run_id,
        "attempt_id": attempt_id,
        "out_root": str(out_root),
        "status": "interrupted",
        "terminal_reason": terminal_reason,
        "exit_type": exit_type,
        "exception_type": type(exc).__name__,
        "exception_message": str(exc)[:1000],
        "research": {
            "status": "incomplete",
            "termination_reason": terminal_reason,
            "turn_index": checkpoint.get("turn_index", 0),
            "agenda_statuses": checkpoint.get("agenda_statuses", {}),
        },
        "checkpoint": checkpoint,
        "artifacts": {
            "latest_checkpoint": checkpoint.get("path", ""),
            "latest_checkpoint_digest": checkpoint.get("digest", ""),
        },
    }
    try:
        _atomic_write_text(partial_path, _json_text(payload))
    except OSError:
        pass

    terminal_filename = (
        f"run_terminal_event.{attempt_id}.json"
        if attempt_id
        else "run_terminal_event.json"
    )
    terminal_path = (
        out_root
        / "artifacts"
        / "06_authoring"
        / "invocations"
        / terminal_filename
    )
    try:
        from code2paper.agentic.unified_invocation_ledger import write_run_terminal_event

        terminal_path = write_run_terminal_event(
            terminal_path.parent,
            run_digest=checkpoint.get("digest", "") or run_id,
            terminal_reason=terminal_reason,
            terminal_stage="method_agent",
            extra={
                "run_id": run_id,
                "attempt_id": attempt_id,
                "exit_type": exit_type,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc)[:1000],
                "checkpoint_path": checkpoint.get("path", ""),
                "checkpoint_digest": checkpoint.get("digest", ""),
                "turn_index": checkpoint.get("turn_index", 0),
            },
            filename=terminal_filename,
        )
    except (OSError, TypeError, ValueError):
        pass
    return {
        "run_summary_partial": str(partial_path),
        "run_terminal_event": str(terminal_path),
    }


_ACTIVE_RUN_LEASES: set[RunLease] = set()


def open_authoring_execution(
    *,
    out_root: Path,
    run_open_mode: str,
    repo_path: str | Path,
    author_intent_path: str | Path | None,
    claims_path: str | Path | None,
    llm_config: LLMConfig | None,
    research_stage_checkpoint: str | Path | None = None,
    research_import_digest: str | None = None,
) -> tuple[AuthoringExecutionIdentityV2, RunLease]:
    """目录准入 + 单写者租约 + create-or-validate 身份（WP1 §5.3/§5.4）。

    必须在任何研究/写作产物写入之前执行：拒绝时零模型调用、零写入。

    产品入口（``run_autonomous_method_agent``）与回放入口
    （``scripts/run_authoring_replay.py``）共用同一实现，使 L1/L2 的准入判据与
    execution_id 完全一致，而不是两套相近但不相同的准入。

    ``research_import_digest`` 供回放入口在非 fork 模式下也绑定"导入的冻结研究
    证据"：回放永远从冻结证据出发，若不绑定，两份不同冻结输入会得到同一个身份。
    fork 模式仍以 checkpoint 文件自身的校验结果为准，显式摘要与之冲突即拒绝。
    """

    mode = str(run_open_mode or "auto")
    explicit_import = str(research_import_digest or "")
    # 审计 §A.3：只读预检（不取锁、不写）先暴露明显错误；目录/身份判定留到锁内重做，
    # 因为预检与取锁之间可能有别的进程结束并留下产物。
    preflight_decision = preflight_run_open(
        out_root,
        mode,
        repo_path=repo_path,
        author_intent_path=author_intent_path,
        claims_path=claims_path,
        llm_config=llm_config,
        research_import_path=research_stage_checkpoint,
    )
    if not preflight_decision.allowed:
        raise RunOpenRejected(preflight_decision)

    # 取锁（owner 待定），然后在锁内重新解析身份与目录状态，再判定一次。
    lease = acquire_run_lease(out_root, execution_id=PENDING_LEASE_OWNER)
    try:
        if mode.strip().casefold() == "fork_authoring":
            verifiable, import_digest, _detail = verify_research_import(
                research_stage_checkpoint
            )
            if verifiable and explicit_import and explicit_import != import_digest:
                raise RunOpenRejected(
                    RunOpenDecision(
                        allowed=False,
                        code="research_import_digest_mismatch",
                        requested_mode=mode,
                        effective_mode=mode,
                        allowed_next_action="recompute_the_import_digest_from_the_checkpoint",
                        detail="显式研究导入摘要与 checkpoint 文件内容不一致",
                    )
                )
        else:
            verifiable, import_digest = True, explicit_import
        identity, verifiable, _detail = resolve_open_identity(
            out_root,
            run_open_mode=mode,
            repo_path=repo_path,
            author_intent_path=author_intent_path,
            claims_path=claims_path,
            llm_config=llm_config,
            research_stage_checkpoint=research_stage_checkpoint,
            research_import_digest=import_digest,
        )
        decision = validate_run_open(
            out_root, mode, identity, research_import_verifiable=verifiable
        )
        if not decision.allowed:
            raise RunOpenRejected(decision)
        lease.bind(identity.execution_id)
        create_or_validate_execution_identity(out_root, identity)
    except BaseException:
        # 拒绝/异常都不留下锁：调用方拿不到 lease，后续尝试必须能重新取锁。
        lease.release()
        raise
    return identity, lease


def run_autonomous_method_agent(
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    out_root: str | Path,
    llm_config: LLMConfig | None = None,
    max_research_turns: int = 30,
    max_wall_clock_seconds: float | None = None,
    max_callback_rounds: int = 3,
    max_callback_tool_turns_per_request: int = 8,
    method_name: str = "",
    run_id: str = "",
    write_method_text: bool | None = None,
    research_stage_checkpoint: str | Path | None = None,
    authoring_phase_checkpoint: str | Path | None = None,
    concept_cards: Any | None = None,
    compile_concept_cards: bool = False,
    compile_argument_briefs: bool = True,
    authoring_context_mode: str | None = None,
    run_open_mode: str = "auto",
) -> MethodAgentRunResultV1:
    """Run the product path with durable closure for exceptions/signals."""

    resolved_out = Path(out_root).expanduser().resolve()
    resolved_out.mkdir(parents=True, exist_ok=True)
    effective_run_id = _effective_method_run_id(resolved_out, run_id)
    # WP1：目录准入与单写者租约先于一切产物写入；租约由模块级集合持有到进程退出，
    # 避免局部变量被回收时提前释放 flock。
    execution_identity, run_lease = open_authoring_execution(
        out_root=resolved_out,
        run_open_mode=run_open_mode,
        repo_path=repo_path,
        author_intent_path=author_intent_path,
        claims_path=claims_path,
        llm_config=llm_config,
        research_stage_checkpoint=research_stage_checkpoint,
    )
    _ACTIVE_RUN_LEASES.add(run_lease)
    old_handlers: dict[int, Any] = {}
    can_install_handlers = threading.current_thread() is threading.main_thread()
    if can_install_handlers:
        def _raise_on_signal(received: int, _frame: Any) -> None:
            raise MethodAgentSignal(received)

        for signum in (
            getattr(signal, "SIGTERM", None),
            getattr(signal, "SIGHUP", None),
            getattr(signal, "SIGINT", None),
        ):
            if signum is None:
                continue
            old_handlers[int(signum)] = signal.getsignal(signum)
            signal.signal(signum, _raise_on_signal)
    try:
        return _run_autonomous_method_agent_impl(
            repo_path=repo_path,
            author_intent_path=author_intent_path,
            claims_path=claims_path,
            out_root=resolved_out,
            llm_config=llm_config,
            max_research_turns=max_research_turns,
            max_wall_clock_seconds=max_wall_clock_seconds,
            max_callback_rounds=max_callback_rounds,
            max_callback_tool_turns_per_request=max_callback_tool_turns_per_request,
            method_name=method_name,
            run_id=effective_run_id,
            write_method_text=write_method_text,
            research_stage_checkpoint=research_stage_checkpoint,
            authoring_phase_checkpoint=authoring_phase_checkpoint,
            concept_cards=concept_cards,
            compile_concept_cards=compile_concept_cards,
            compile_argument_briefs=compile_argument_briefs,
            authoring_context_mode=authoring_context_mode,
            execution_identity=execution_identity,
        )
    except BaseException as exc:
        _persist_partial_method_run(
            out_root=resolved_out,
            run_id=effective_run_id,
            exc=exc,
        )
        raise
    finally:
        if can_install_handlers:
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
        # 审计 §A.3：入口持有 lease、finally 释放——异常/失败/长寿命进程中的下一次任务
        # 都不能泄漏 flock（否则同一进程的后续 run 会被自己的旧锁挡住）。
        _ACTIVE_RUN_LEASES.discard(run_lease)
        run_lease.release()


def _writer_artifact_paths(
    out_root: Path,
    *,
    persisted_paths: Mapping[str, str] | None = None,
    allow_legacy_discovery: bool = False,
) -> dict[str, str]:
    """Resolve the Writer's artifact inputs for one revision.

    The product mainline passes ``persisted_paths`` -- the map returned by
    :func:`persist_product_artifacts` for *this* revision -- and only those
    files may become Writer inputs.  A stale file that happens to share a
    name inside ``out_root/artifacts`` must never be promoted into a current
    revision.

    Directory discovery by file name remains available for explicitly marked
    legacy/replay entry points: a caller that supplies no manifest must also
    pass ``allow_legacy_discovery=True``.  Anything else is refused instead of
    silently guessing which files belong to the run.
    """

    names = (
        "repo_snapshot_v2",
        "repository_authoring_artifacts_v1",
        "repo_snapshot",
        "symbol_index_v2",
        "symbol_index",
        "repository_source_manifest_v1",
        "intent_obligation_graph_v2",
        "research_agenda_v1",
        "authoring_projection_v1",
        "method_evidence",
        "claim_evidence_map",
        "obligation_coverage_v2",
        "reference_method_agenda_v1",
        "method_completeness_matrix_v1",
        "method_section_plan_v2",
        "equation_claims_v1",
        "configuration_claims_v1",
        "evidence_packets_v3",
        "code_facts_v1",
        "atomic_claims_v3",
        "method_propositions_v1",
        "method_proposition_bindings_v1",
        "method_concept_cards_v1",
        "method_argument_facets_v1",
        "facet_evidence_alignments_v1",
        "candidate_facet_policies_v1",
        "publication_field_candidates_v1",
        "typed_field_deferred_v1",
        "implementation_scope_v1",
        "behavior_graph_v1",
        "candidate_acquisition_ledger_v1",
        "observation_promotion_ledger_v1",
        "candidate_handoff_v1",
        "candidate_retry_ledger_v1",
        "method_authoring_closure_metrics_v1",
        "method_argument_briefs_v1",
        "author_story_spine_v1",
        "story_spine",
        "method_story_nodes_v1",
    )
    if persisted_paths is not None:
        resolved: dict[str, str] = {}
        for name in names:
            raw = str(persisted_paths.get(name) or "").strip()
            if not raw:
                continue
            candidate = Path(raw)
            if candidate.is_file():
                resolved[name] = str(candidate)
        return resolved
    if not allow_legacy_discovery:
        raise ValueError(
            "writer_artifact_manifest_required: pass this revision's persisted "
            "path map, or mark a legacy entry point with allow_legacy_discovery"
        )
    return {
        name: str(out_root / "artifacts" / f"{name}.json")
        for name in names
        if (out_root / "artifacts" / f"{name}.json").is_file()
    }


def _run_writer_surface(
    *,
    out_root: Path,
    artifact_paths: dict[str, str],
    llm_config: LLMConfig,
    run_id: str,
    authoring_context_mode: str | None = None,
    authoring_phase_checkpoint: str | Path | None = None,
) -> tuple[dict[str, str], str, str]:
    """Call the shared Writer surface and map its status onto the product run.

    The Writer surface owns the candidate/verified/review output semantics
    (Agent 2's package); this runner only feeds it the frozen product
    artifacts and reports its status.  Blocked reasons stay typed.
    """

    from code2paper.agentic.publication_method_writer import (
        run_publication_method_writer,
    )

    unified_tokenizer = None
    resolved_mode = str(authoring_context_mode or "").strip().casefold()
    env_mode = str(
        os.environ.get("CODE2PAPER_AUTHORING_CONTEXT_MODE", "") or ""
    ).strip().casefold()
    if resolved_mode == "unified" or (not resolved_mode and env_mode == "unified"):
        try:
            from code2paper.llm.tokenizer import prepare_vllm_openai_chat_tokenizer

            unified_tokenizer = prepare_vllm_openai_chat_tokenizer(
                llm_config=llm_config,
                out_root=out_root,
                require_loopback_8006=True,
            )
        except Exception as exc:  # noqa: BLE001 - product admission is fail-closed
            return {}, "blocked", (
                "writer_tokenizer_admission_failed:"
                f"{type(exc).__name__}:{str(exc)[:200]}"
            )

    try:
        result, paths = run_publication_method_writer(
            out_root=out_root,
            artifact_paths=artifact_paths,
            llm_config=llm_config,
            run_id=run_id,
            llm_caller=None,
            editor_caller=None,
            rewrite_caller=None,
            formalization_caller=None,
            # R7 default wiring: ``None`` means "build the bounded proposal
            # caller from ``llm_config``" inside the narrative builder; it is
            # not a request to skip proposals.  The caller stays unused when
            # the config has no usable provider.
            architect_proposal_caller=None,
            authoring_context_mode=authoring_context_mode,
            unified_tokenizer=unified_tokenizer,
            proposal_tokenizer=unified_tokenizer,
            formalizer_phase_checkpoint=authoring_phase_checkpoint,
        )
    except Exception as exc:  # noqa: BLE001 — the product run must not crash on writer faults
        import traceback
        traceback.print_exc()
        return {}, "blocked", f"writer_surface_fault:{type(exc).__name__}:{str(exc)[:200]}"
    status = result.status if hasattr(result, "status") else "blocked"
    blocked_reason = (
        getattr(result, "blocked_reason", "") if hasattr(result, "blocked_reason") else ""
    )
    if status == "blocked" and not blocked_reason:
        blocked_reason = "writer_surface_blocked"
    return paths, status, blocked_reason


__all__ = [
    "CLAIM_PRIORITY_VALUES",
    "MethodAgentRunResultV1",
    "MethodAgentSignal",
    "PRODUCT_RESEARCH_HARD_RULES",
    "PRODUCT_RESEARCH_READY_TOOLS",
    "TypedResearchGapV1",
    "UserClaimInputV1",
    "UserClaimsInputV1",
    "append_claims_to_intent_graph",
    "build_product_planning",
    "build_product_research_runtime",
    "build_typed_gaps",
    "load_user_claims",
    "load_research_stage_checkpoint",
    "merge_product_evidence",
    "open_authoring_execution",
    "persist_research_stage_checkpoint",
    "persist_product_artifacts",
    "run_autonomous_method_agent",
    "run_product_research_phase",
]
