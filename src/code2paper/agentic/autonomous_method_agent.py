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
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.author_intent_summary import load_author_intent_summary
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
    ResearchDecisionV1,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchObservationV1,
)
from code2paper.agentic.research_policy import PolicyMergeResult
from code2paper.agentic.research_nodes import ResearchGraphRuntime
from code2paper.agentic.product_authoring_graph import (
    ProductAuthoringIssueV1,
    persist_product_authoring_state_from_writer,
)
from code2paper.agentic.state_v3 import empty_agent_state_v3
from code2paper.agentic.v3_runtime import (
    build_research_agenda_from_intent_graph,
    merge_compiled_evidence,
)
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
) -> ResearchLoopResult:
    """Run the research subgraph to termination (direct product path)."""

    if max_turns < 1:
        raise ValueError("max_research_turns must be at least 1")
    initial = empty_agent_state_v3(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    )
    subgraph = build_research_subgraph(runtime, max_turns=max_turns)
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


def merge_product_evidence(
    result: ResearchLoopResult,
    runtime: ResearchGraphRuntime,
) -> tuple[EvidencePacketSetV3 | None, CodeFactSetV1 | None, AtomicClaimSetV3 | None]:
    """Aggregate the loop's per-obligation compiled evidence.

    ``merge_compiled_evidence`` is a pure aggregation adapter (dedupe by
    canonical identity, remap stage groups); no synthetic gaps are added.
    Claims are then bound to typed obligations through their fact IDs.
    """

    compiled = getattr(result.loop_state, "compiled_evidence", {})
    if not compiled:
        return None, None, None
    packet_set, fact_set, claim_set = merge_compiled_evidence(
        compiled,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
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
) -> str:
    """Commit completed repository research before any planning model call.

    Proposition synthesis, semantic judging, or Writer transport may fail
    independently of repository research.  Persisting this compact stage
    boundary lets a later run continue from the exact frozen evidence rather
    than repeating code searches to obtain another sample.
    """

    root = Path(out_root).expanduser().resolve()
    path = root / "artifacts" / "research_product" / "research_stage_checkpoint_v1.json"
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
        "research_state": _research_run_state(loop_result, runtime),
    }
    _atomic_write_text(path, _json_text(payload))
    return str(path)


def load_research_stage_checkpoint(
    *,
    path: str | Path,
    runtime: ResearchGraphRuntime,
) -> tuple[
    ResearchLoopResult,
    EvidencePacketSetV3 | None,
    CodeFactSetV1 | None,
    AtomicClaimSetV3 | None,
    UserClaimsInputV1,
]:
    """Authenticate and restore the product research-stage boundary."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if str(payload.get("run_id") or "") != runtime.run_id:
        raise ValueError("research_stage_checkpoint_run_id_mismatch")
    if str(payload.get("repo_snapshot_id") or "") != runtime.repo_snapshot.snapshot_id:
        raise ValueError("research_stage_checkpoint_snapshot_mismatch")
    if str(payload.get("project_tree_hash") or "") != runtime.repo_snapshot.project_tree_hash:
        raise ValueError("research_stage_checkpoint_tree_hash_mismatch")
    checkpoint_intent = payload.get("intent_graph") or {}
    if checkpoint_intent != runtime.intent_graph.model_dump(mode="json"):
        raise ValueError("research_stage_checkpoint_intent_mismatch")
    checkpoint_agenda = ResearchAgendaV1.model_validate(payload.get("agenda") or {})
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
    final_state = empty_agent_state_v3(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    ).to_state_dict()
    final_state["status"] = str(terminal.get("final_status") or "incomplete")
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
        elif item.status in {"pending", "in_progress"}:
            attempted = tuple(dict.fromkeys(item.attempted_actions))
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
            attempted = tuple(dict.fromkeys(item.attempted_actions))
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

    The research loop persists one idempotent terminal-gap payload per
    accepted ``explicit_gap`` obligation (``record_explicit_code_gap``).
    These are converted into the coverage-report representation with exact
    ``{gap_id: [obligation_id]}`` bindings so the completeness matrix can
    mark the obligation ``explicit_code_gap`` — no gap is ever fabricated.
    """

    from code2paper.agentic.evidence_compiler_v3 import ExplicitCodeGapV1

    gap_root = runtime.tool_context().artifact_root / "research_tool_artifacts" / "terminal_gaps"
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

    # Research closure sidecars.  These are diagnostic provenance artifacts,
    # not a second authority path: positive claims still come only from the
    # frozen packets/facts/claims below.
    loop_scope = getattr(loop_result.loop_state, "implementation_scope", None)
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
    paths["story_spine"] = _write(
        "story_spine",
        [node.model_dump(mode="json") for node in story_spine],
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
    unresolved = sum(not item.terminal for item in target_records)
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

    metrics = {
        "schema_version": "1.0",
        "research": {
            "must_cover_candidates": len(target_records),
            "acquired": acquired,
            "explicitly_rejected": rejected,
            "unresolved_acquisition": unresolved,
            "target_core_packet_ratio": (acquired / len(target_records)) if target_records else 0.0,
            "comparand_packet_ratio": (comparand_packets / len(comparand_records)) if comparand_records else 0.0,
        },
        "alignment": {
            "atomic_fields": len(candidates),
            "renderable_fields": sum(bool(getattr(item, "is_consumable", False)) for item in candidates),
            "deferred_fields": len(deferred),
            "hard_target_from_unresolved": hard_from_unresolved,
        },
        "planning": {
            "hard_targets": hard_targets,
            "support_slots": support_slots,
            "publication_slots": publication_slots,
        },
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


def run_autonomous_method_agent(
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    out_root: str | Path,
    llm_config: LLMConfig | None = None,
    max_research_turns: int = 30,
    max_callback_rounds: int = 3,
    max_callback_tool_turns_per_request: int = 8,
    method_name: str = "",
    run_id: str = "",
    write_method_text: bool | None = None,
    research_stage_checkpoint: str | Path | None = None,
    concept_cards: Any | None = None,
    compile_concept_cards: bool = False,
    compile_argument_briefs: bool = True,
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
        )
    else:
        loop_result = run_product_research_phase(
            runtime,
            max_turns=int(max_research_turns),
        )
        packet_set, fact_set, claim_set = merge_product_evidence(loop_result, runtime)
    research_run_state = _research_run_state(loop_result, runtime)
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
        llm_config=effective_llm if live_llm else None,
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
    if readiness is not None:
        plan_readiness = readiness.readiness
        blocked_reasons = tuple(readiness.blocked_for_safety_reasons)
    else:
        plan_readiness = "candidate_ready_with_review"
        blocked_reasons = tuple(
            reason
            for item in completeness.items
            if item.status not in {"supported_by_repository", "out_of_scope"}
            for reason in (f"unverified obligation: {item.obligation_id}",)
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
    )
    paths["research_stage_checkpoint_v1"] = research_checkpoint_path

    writer_status = "skipped_no_live_llm"
    writer_blocked_reason = ""
    writer_paths: dict[str, str] = {}
    writer_artifact_paths = _writer_artifact_paths(resolved_out)
    if write_method_text:
        writer_paths, writer_status, writer_blocked_reason = _run_writer_surface(
            out_root=resolved_out,
            artifact_paths=dict(sorted(writer_artifact_paths.items())),
            llm_config=effective_llm,
            run_id=effective_run_id,
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
                terminal_status=(
                    "completed"
                    if writer_status == "success" and not product_issues
                    else "incomplete"
                    if writer_status == "skipped_no_live_llm"
                    else "review_ready_with_warnings"
                ),
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
    summary["artifacts"] = dict(sorted(paths.items()))

    agent_trace.append({
        "phase": "finalize",
        "status": "ok",
        "detail": {"total_duration_ms": round((time.time() - started) * 1000, 1)},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((time.time() - started) * 1000, 1),
    })
    _atomic_write_text(resolved_out / "artifacts" / "research_product" / "agent_trace.json", _json_text(agent_trace))
    _atomic_write_text(resolved_out / "artifacts" / "research_product" / "run_summary.json", _json_text(summary))

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


def _writer_artifact_paths(out_root: Path) -> dict[str, str]:
    names = (
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
        "method_authoring_closure_metrics_v1",
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
) -> tuple[dict[str, str], str, str]:
    """Call the shared Writer surface and map its status onto the product run.

    The Writer surface owns the candidate/verified/review output semantics
    (Agent 2's package); this runner only feeds it the frozen product
    artifacts and reports its status.  Blocked reasons stay typed.
    """

    from code2paper.agentic.publication_method_writer import (
        run_publication_method_writer,
    )

    try:
        result, paths = run_publication_method_writer(
            out_root=out_root,
            artifact_paths=artifact_paths,
            llm_config=llm_config,
            llm_caller=None,
            editor_caller=None,
            rewrite_caller=None,
            formalization_caller=None,
            architect_proposal_caller=None,
        )
    except Exception as exc:  # noqa: BLE001 — the product run must not crash on writer faults
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
    "persist_research_stage_checkpoint",
    "persist_product_artifacts",
    "run_autonomous_method_agent",
    "run_product_research_phase",
]
