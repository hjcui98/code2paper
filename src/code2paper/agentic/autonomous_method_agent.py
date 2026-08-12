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
from typing import Any, Literal

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
from code2paper.agentic.obligation_fact_alignment import (
    bind_claims_to_obligations,
    build_obligation_coverage_v2,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_graph import (
    ResearchLoopResult,
    build_research_subgraph,
)
from code2paper.agentic.research_models import (
    ResearchAgendaItemV1,
    ResearchAgendaV1,
)
from code2paper.agentic.research_nodes import ResearchGraphRuntime
from code2paper.agentic.state_v3 import empty_agent_state_v3
from code2paper.agentic.v3_runtime import (
    build_research_agenda_from_intent_graph,
    merge_compiled_evidence,
)
from code2paper.llm.providers import has_provider_api_key, load_llm_config_from_env
from code2paper.schemas import ClaimEvidenceMap, LLMConfig, MethodEvidence

PRODUCT_RESEARCH_READY_TOOLS: tuple[str, ...] = (
    "find_entrypoints",
    "search_symbols",
    "read_symbol",
    "find_references",
    "build_behavior_subgraph",
    "trace_call_path",
    "trace_data_flow",
    "inspect_control_flow",
    "inspect_configuration",
    "search_code",
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

    effective_llm = llm_config or load_llm_config_from_env()
    intent_graph, proposal_report = enrich_intent_graph_with_llm(
        intent_graph,
        effective_llm,
    )

    agenda = build_research_agenda_from_intent_graph(
        intent_graph,
        run_id=run_id,
        repo_snapshot=repo_snapshot,
    )

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
        intent_target_proposal_report=proposal_report.model_dump(mode="json"),
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
            gaps.append(TypedResearchGapV1(
                gap_id=f"gap-unresolved:{item.obligation_id}",
                obligation_id=item.obligation_id,
                status="unresolved",
                reason=(
                    f"Obligation {item.obligation_id} was still open when the "
                    f"research loop stopped ({result.termination_reason})."
                ),
                attempted_tools=tuple(dict.fromkeys(item.attempted_actions)),
                search_scope=tuple(dict.fromkeys(
                    path for path in item.candidate_symbol_ids
                )),
                stopping_reason=result.termination_reason,
                trace_refs=(f"agenda:{item.obligation_id}",),
            ))
        elif item.status == "blocked":
            gaps.append(TypedResearchGapV1(
                gap_id=f"gap-blocked:{item.obligation_id}",
                obligation_id=item.obligation_id,
                status="blocked",
                reason=f"Obligation {item.obligation_id} ended blocked.",
                attempted_tools=tuple(dict.fromkeys(item.attempted_actions)),
                stopping_reason=result.termination_reason,
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


def build_product_planning(
    *,
    runtime: ResearchGraphRuntime,
    packet_set: EvidencePacketSetV3 | None,
    fact_set: CodeFactSetV1 | None,
    claim_set: AtomicClaimSetV3 | None,
    claims_input: UserClaimsInputV1 | None = None,
    method_name: str = "",
) -> dict[str, Any]:
    """Compile coverage, completeness, equations, configs, plan, readiness.

    Returns a dict with keys: ``coverage``, ``agenda_ref``,
    ``completeness``, ``equations``, ``configurations``, ``story_spine``,
    ``plan`` (or None), ``readiness`` (or None), ``review_candidates``.
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
    if plan is not None:
        paths["method_section_plan_v2"] = _write(
            "method_section_plan_v2",
            plan.model_dump(mode="json"),
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
    runtime = build_product_research_runtime(
        repo_path=repo_path,
        author_intent_path=author_intent_path,
        claims=claims_input,
        run_id=effective_run_id,
        llm_config=effective_llm,
        artifact_root=resolved_out / "artifacts" / "research_tool_data",
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

    loop_result = run_product_research_phase(
        runtime,
        max_turns=int(max_research_turns),
    )
    _phase(
        "research_loop",
        "ok" if loop_result.terminated else "incomplete",
        {
            "turns_executed": loop_result.turns_executed,
            "termination_reason": loop_result.termination_reason,
            "decisions": len(loop_result.decision_trace),
        },
    )

    packet_set, fact_set, claim_set = merge_product_evidence(loop_result, runtime)
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
            "status": "trusted" if loop_result.terminated else "incomplete",
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
    if write_method_text and writer_status in {"incomplete", "success"}:
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
                    max_callback_rounds=max(1, int(max_callback_rounds)),
                    max_tool_turns_per_request=max(1, int(max_callback_tool_turns_per_request)),
                ),
                llm_caller=None,
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
    summary["writer"] = {
        "status": writer_status,
        "blocked_reason": writer_blocked_reason,
        "candidate_written": bool(
            writer_paths.get("publication_candidate_method")
        ),
        "verified_written": bool(writer_paths.get("repository_verified_method")),
    }
    summary["callbacks"] = callback_counts
    summary["review"] = review_counts
    summary["candidate_validation"] = candidate_validation
    summary["verified_validation"] = verified_validation
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
            "trusted" if loop_result.terminated else "incomplete"
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
    "merge_product_evidence",
    "persist_product_artifacts",
    "run_autonomous_method_agent",
    "run_product_research_phase",
]
