"""V3 research runtime builder and graph wrapper (R8 wiring).

Builds the bridge between the legacy ``code2paper-agentic-run`` CLI and
the V3 research plane (design section 8 + R0.3).  When
``CODE2PAPER_AGENTIC_RESEARCH_V3=1`` is set, the runner uses this
module to:

1. Build a ``ResearchGraphRuntime`` configured with
   ``GemmaSupervisorBackend`` (so research decisions are made by the
   local Gemma endpoint instead of the deterministic fallback).
2. Run the V3 research subgraph (``build_research_subgraph``) to
   produce a ``ResearchLoopResult`` containing the V3 decision trace,
   observations and agenda updates.  The subgraph is the multi-node
   LangGraph topology from design section 8 (linear_prefix →
   research_supervisor → research_tool → observation_pipeline →
   evidence_critic → compile_candidate / gap_finalizer →
   obligation_advancer → terminator), so each step is individually
   checkpointable and the node execution trace is available for R8
   verification.
3. Convert the V3 decisions to legacy ``AgentDecision`` records and
   merge them into the ``AgenticRunState.decisions`` list so the R8
   acceptance checker can verify the trace.
4. Run the legacy ``build_code2paper_graph`` pipeline (evidence,
   authoring, validation) as usual so the full Method text is still
   produced.

Design invariants:

- The V3 research subgraph and the legacy pipeline exchange state ONLY
  through explicit adapters in this module (no implicit channel
  sharing).  This honors the R0.3 hard rule that V2 and V3 exchange
  only through explicit adapters.
- The V3 research runtime is constructed ONCE per run and reused for
  every research turn.  The supervisor backend is ``GemmaSupervisorBackend``
  when an LLM config is provided, falling back to
  ``DeterministicSupervisorBackend`` when the LLM is unavailable.
- The supervisor's per-role R8 sampling config (temperature=0.20,
  max_output_tokens=1536) is applied via ``apply_role_config`` inside
  ``GemmaSupervisorBackend``.  ``cache`` is forced off for R8 protocol
  compliance.
- The V3 decision trace is preserved verbatim in the run summary's
  ``decisions`` list so ``compute_trace_digest`` and the R8 acceptance
  checker can verify reproducibility.
- V3 research failures are NOT silently swallowed: the wrapper records
  the failure reason and surfaces it in the run summary's
  ``v3_error`` field so the R8 acceptance checker can fail the run
  instead of silently downgrading to a non-V3 pipeline.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Mapping

from code2paper.agentic.author_intent_summary import (
    AuthorIntentSummary,
    load_author_intent_summary,
)
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    EvidencePacketSetV3,
    EvidencePacketV3,
    ExplicitCodeGapV1,
    GENERIC_RESEARCH_PRODUCER_VERSION,
)
from code2paper.agentic.gemma_supervisor_backend import GemmaSupervisorBackend
from code2paper.agentic.equation_claims import (
    EquationClaimSetV1,
    bind_equations_to_claims,
    compile_equation_claims,
    derive_equation_proposals_from_facts,
    write_equation_claims,
)
from code2paper.agentic.execution_profile import ExecutionProfileV1
from code2paper.agentic.graph import build_code2paper_graph
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    compile_intent_obligation_graph_v2,
)
from code2paper.agentic.intent_target_proposer import enrich_intent_graph_with_llm
from code2paper.agentic.research_graph import (
    CompiledEvidence,
    CompiledResearchSubgraph,
    ResearchLoopResult,
    build_research_subgraph,
    load_immutable_loop_payload,
    run_research_loop,
)
from code2paper.agentic.research_models import (
    ResearchAction,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchDecisionV1,
    TypedBehaviorTargetV1,
)
from code2paper.agentic.research_nodes import ResearchGraphRuntime
from code2paper.agentic.repo_snapshot import RepoSnapshot, build_repo_snapshot
from code2paper.agentic.research_supervisor import DeterministicSupervisorBackend
from code2paper.agentic.state_v3 import (
    AgentStateV3,
    AgentStateV3Record,
    empty_agent_state_v3,
)
from code2paper.agentic.tools import Code2PaperStageTool
from code2paper.agentic.decision_core import DecisionProvider
from code2paper.agentic.text_evidence_validator import SemanticVerifier
from code2paper.agentic.tool_runtime import atomic_write_bytes
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.schemas import LLMConfig

_logger = logging.getLogger(__name__)


def _atomic_write_text(path: Path, content: str) -> None:
    """Write a V3 hand-off artifact with a crash-safe replacement boundary."""

    atomic_write_bytes(path, content.encode("utf-8"))


def _extract_out_root(state: Any) -> Path | None:
    """Best-effort extraction of ``out_root`` from a legacy state payload.

    The legacy ``AgenticRunState`` carries ``out_root`` as a ``Path``; when
    the state is a dict (the common case for LangGraph payloads) the same
    key holds a string or Path.  Returns ``None`` when no ``out_root`` can
    be found so the caller can skip artifact serialization.
    """

    if state is None:
        return None
    if isinstance(state, dict):
        out_root = state.get("out_root")
    else:
        out_root = getattr(state, "out_root", None)
    if out_root is None or str(out_root).strip() == "":
        return None
    return Path(out_root)


def _persist_execution_profile_artifacts(
    out_root: Path,
    runtime: ResearchGraphRuntime,
) -> dict[str, str]:
    """Persist the selected D6 route without granting it evidence authority."""

    if not isinstance(runtime.execution_profile, ExecutionProfileV1):
        return {}
    artifacts_dir = Path(out_root) / "artifacts" / "10_run"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    profile_path = artifacts_dir / "execution_profile_v1.json"
    route_path = artifacts_dir / "execution_route_v1.json"
    _atomic_write_text(
        profile_path,
        json.dumps(
            runtime.execution_profile.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    _atomic_write_text(
        route_path,
        json.dumps(runtime.execution_manifest(), ensure_ascii=False, indent=2) + "\n",
    )
    return {
        "execution_profile": str(profile_path),
        "execution_route": str(route_path),
    }


def _execution_control_payload(runtime: ResearchGraphRuntime) -> dict[str, Any]:
    """Carry resolved rollout inputs through the legacy checkpoint state.

    Environment variables are useful for the first invocation, but must not
    silently change a resumed route.  The resolved values therefore travel in
    the typed state returned by the wrapper; the next invocation can reuse
    them without consulting a changed process environment.
    """

    if runtime.execution_profile is None:
        return {}
    return {
        "execution_opt_in": bool(runtime.execution_opt_in),
        "execution_rollback": bool(runtime.execution_rollback),
        "execution_canary_key": runtime.execution_canary_key or runtime.run_id,
    }


def _recompute_claim_set_digest(claim_set: AtomicClaimSetV3) -> None:
    """Recompute ``content_digest`` after in-place mutation of the claim set.

    The freshness checker hashes ``claims`` / ``explicit_code_gaps`` /
    ``semantic_stage_groups``; any mutation of those lists (e.g. appending
    synthetic gaps) invalidates the stored digest and must be followed by
    this recomputation so resume validation sees a consistent artifact.
    """

    payload = {
        "claims": [claim.model_dump(mode="json") for claim in claim_set.claims],
        "explicit_code_gaps": [
            gap.model_dump(mode="json") for gap in claim_set.explicit_code_gaps
        ],
        "semantic_stage_groups": [
            group.model_dump(mode="json")
            for group in claim_set.semantic_stage_groups
        ],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    claim_set.content_digest = "sha256:" + hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# Intent graph -> Research agenda converter
# ---------------------------------------------------------------------------


def build_research_agenda_from_intent_graph(
    intent_graph: IntentObligationGraphV2,
    *,
    run_id: str,
    repo_snapshot: RepoSnapshot,
) -> ResearchAgendaV1:
    """Convert a V2 intent obligation graph into a V1 research agenda.

    Each V2 obligation becomes a V1 agenda item.  Typed behavior targets
    are copied verbatim (they use the same ``TypedBehaviorTargetV1``
    model).  Missing information is seeded from the obligation's
    retrieval queries and candidate paths so the supervisor has a
    starting point for SEARCH_SYMBOLS.

    The agenda is content-addressed (``content_digest`` is computed by
    ``ResearchAgendaV1._compute_digest``) so checkpoint drift is
    detectable.
    """

    snapshot_root = Path(repo_snapshot.project_root).resolve()
    snapshot_paths = {entry.path for entry in repo_snapshot.included_files}

    def _snapshot_candidate_paths(paths: tuple[str, ...]) -> list[str]:
        normalized: list[str] = []
        for raw in paths:
            candidate = str(raw or "").strip()
            if not candidate:
                continue
            path = Path(candidate)
            if path.is_absolute():
                try:
                    candidate = path.resolve().relative_to(snapshot_root).as_posix()
                except (OSError, ValueError):
                    continue
            else:
                candidate = candidate.replace("\\", "/").lstrip("./")
            if candidate not in snapshot_paths and not any(
                value.startswith(candidate.rstrip("/") + "/")
                for value in snapshot_paths
            ):
                continue
            if candidate not in normalized:
                normalized.append(candidate)
        return normalized

    items: list[ResearchAgendaItemV1] = []
    for obl in intent_graph.obligations:
        candidate_paths = _snapshot_candidate_paths(obl.candidate_paths)
        missing_info: list[str] = []
        for query in obl.retrieval_queries:
            if query and query not in missing_info:
                missing_info.append(query)
        for path in candidate_paths:
            label = f"candidate_path:{path}"
            if label not in missing_info:
                missing_info.append(label)
        # If no missing information was derived, fall back to the
        # obligation's author text so the supervisor still has a search
        # query.
        if not missing_info and obl.author_text:
            missing_info.append(obl.author_text[:120])

        items.append(
            ResearchAgendaItemV1(
                obligation_id=obl.obligation_id,
                priority=obl.priority,  # type: ignore[arg-type]
                author_text=obl.author_text,
                typed_behavior_targets=[
                    TypedBehaviorTargetV1(**t.model_dump())
                    for t in obl.typed_behavior_targets
                ],
                status="pending",  # type: ignore[arg-type]
                missing_information=missing_info,
                candidate_symbol_ids=candidate_paths,
            )
        )

    return ResearchAgendaV1(
        run_id=run_id,
        repo_snapshot_id=repo_snapshot.snapshot_id,
        project_tree_hash=repo_snapshot.project_tree_hash,
        intent_graph_digest=intent_graph.content_digest,
        items=items,
    )


# ---------------------------------------------------------------------------
# V3 research runtime builder
# ---------------------------------------------------------------------------


def build_v3_research_runtime(
    *,
    project_root: str | Path,
    intent_path: str | Path,
    run_id: str,
    llm_config: LLMConfig | None = None,
    ready_tools: tuple[str, ...] = (
        "find_entrypoints",
        "search_symbols",
        "read_symbol",
        "find_references",
        "build_behavior_subgraph",
        "trace_call_path",
        "trace_data_flow",
        "inspect_control_flow",
        "inspect_configuration",
    ),
    hard_rules: tuple[str, ...] = (
        "no_snapshot_external_paths",
        "no_unregistered_tools",
        "no_authority_upgrade",
        "no_skipped_validators",
        "no_duplicate_no_gain_calls",
        "obligation_must_exist",
        "budgets_must_be_available",
        "fallback_must_be_safe",
    ),
    execution_profile: ExecutionProfileV1 | None = None,
    execution_opt_in: bool = False,
    execution_canary_key: str = "",
    execution_rollback: bool = False,
    execution_default_authorized: bool = False,
    evidence_policy_digest: str = "",
) -> ResearchGraphRuntime:
    """Build a ``ResearchGraphRuntime`` configured with ``GemmaSupervisorBackend``.

    Steps:

    1. Build ``RepoSnapshot`` from ``project_root``.
    2. Load ``AuthorIntentSummary`` from ``intent_path``.
    3. Compile ``IntentObligationGraphV2`` from the summary.
    4. Convert the intent graph to ``ResearchAgendaV1``.
    5. Build ``GemmaSupervisorBackend`` from ``llm_config`` (falls back
       to ``DeterministicSupervisorBackend`` when the LLM is
       unavailable).
    6. Return the assembled ``ResearchGraphRuntime``.

    When ``llm_config`` is ``None``, the config is loaded from
    environment variables via ``load_llm_config_from_env``.
    """

    resolved_root = Path(project_root).expanduser().resolve()
    if not resolved_root.is_dir():
        raise FileNotFoundError(f"project_root not found: {resolved_root}")

    repo_snapshot = build_repo_snapshot(resolved_root)

    intent_summary: AuthorIntentSummary | None = None
    if intent_path:
        intent_summary = load_author_intent_summary(intent_path)
    intent_graph = compile_intent_obligation_graph_v2(intent_summary)
    effective_llm_config = llm_config or load_llm_config_from_env()
    if execution_profile is not None:
        # Provider/model selection is an execution concern only.  Rebuild the
        # typed config so capability negotiation can choose a different
        # transport while all evidence/authorization gates remain unchanged.
        updates: dict[str, Any] = {}
        if execution_profile.provider.strip():
            updates["provider"] = execution_profile.provider.strip().lower()
        if execution_profile.model.strip():
            updates["model"] = execution_profile.model.strip()
        if updates:
            effective_llm_config = LLMConfig.model_validate(
                {**effective_llm_config.model_dump(mode="json"), **updates}
            )
    intent_graph, intent_proposal_report = enrich_intent_graph_with_llm(
        intent_graph,
        effective_llm_config,
    )

    agenda = build_research_agenda_from_intent_graph(
        intent_graph,
        run_id=run_id,
        repo_snapshot=repo_snapshot,
    )

    supervisor_backend = GemmaSupervisorBackend(
        llm_config=effective_llm_config,
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
        intent_target_proposal_report=intent_proposal_report.model_dump(mode="json"),
        supervisor_backend=supervisor_backend,
        ready_tools=ready_tools,
        hard_rules=hard_rules,
        adapter_language=execution_profile.language if execution_profile is not None else "",
        execution_profile=execution_profile,
        execution_opt_in=execution_opt_in,
        execution_canary_key=execution_canary_key,
        execution_rollback=execution_rollback,
        execution_default_authorized=execution_default_authorized,
        evidence_policy_digest=evidence_policy_digest,
    )


# ---------------------------------------------------------------------------
# V3 research phase execution
# ---------------------------------------------------------------------------


def run_v3_research_phase(
    runtime: ResearchGraphRuntime,
    *,
    max_turns: int = 50,
    checkpointer: Any = None,
    thread_id: str | None = None,
) -> ResearchLoopResult:
    """Run the V3 research subgraph and return the loop result.

    The research subgraph is built fresh each call so the runtime
    (including the supervisor backend) is respected.  The result carries
    the full decision trace, observation list and final state.

    The subgraph is the multi-node LangGraph topology from
    ``build_research_subgraph`` (9 checkpointable nodes: linear_prefix →
    research_supervisor → research_tool → observation_pipeline →
    evidence_critic → compile_candidate / gap_finalizer →
    obligation_advancer → terminator).  This is the production path for
    V3 research — the procedural ``run_research_loop`` helper is kept
    only for unit tests that need to bypass LangGraph.

    When ``checkpointer`` and ``thread_id`` are provided, the subgraph
    is compiled with the checkpointer and invoked with the thread_id in
    the LangGraph config so checkpoint/resume works across instances.
    """

    initial_state = empty_agent_state_v3(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    )
    subgraph = build_research_subgraph(
        runtime,
        max_turns=max_turns,
        checkpointer=checkpointer,
    )
    config: dict[str, Any] | None = None
    if thread_id:
        config = {"configurable": {"thread_id": thread_id}}
    subgraph.invoke(initial_state.to_state_dict(), config=config)
    result = subgraph.last_result
    if result is None:
        raise RuntimeError(
            "V3 research subgraph did not produce a ResearchLoopResult — "
            "the terminator node may not have run.  Check max_turns and "
            "the supervisor backend configuration."
        )
    return result


# ---------------------------------------------------------------------------
# V3 compiled evidence merger (R4 -> legacy artifact bridge)
# ---------------------------------------------------------------------------


def merge_compiled_evidence(
    compiled_evidence: dict[str, CompiledEvidence],
    *,
    repo_snapshot_id: str,
    project_tree_hash: str,
) -> tuple[EvidencePacketSetV3 | None, CodeFactSetV1 | None, AtomicClaimSetV3 | None]:
    """Merge all per-obligation ``CompiledEvidence`` into aggregate sets.

    Returns ``(packet_set, fact_set, claim_set)``.  Any element is ``None``
    when no obligation produced compiled evidence for that artifact kind.
    The merged sets are content-addressed so downstream consumers (legacy
    writer, R8 acceptance checker) can verify integrity.
    """

    if not compiled_evidence:
        return None, None, None

    all_packets: list[EvidencePacketV3] = []
    all_facts: list[CodeFactV1] = []
    all_claims: list[AtomicClaimV3] = []
    all_gaps: list[ExplicitCodeGapV1] = []
    all_stage_groups: list[Any] = []
    evidence_packet_digest = ""
    code_fact_digest = ""
    for entry in compiled_evidence.values():
        all_packets.extend(entry.packet_set.packets)
        all_facts.extend(entry.fact_set.facts)
        all_claims.extend(entry.claim_set.claims)
        all_gaps.extend(entry.claim_set.explicit_code_gaps)
        all_stage_groups.extend(entry.claim_set.semantic_stage_groups)
        if not evidence_packet_digest:
            evidence_packet_digest = entry.fact_set.evidence_packet_digest
        if not code_fact_digest:
            code_fact_digest = entry.claim_set.code_fact_digest

    import hashlib
    import json as _json

    def _digest(payload: Any) -> str:
        encoded = _json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    # Research is obligation-scoped, so the same executable operation may be
    # rediscovered for a stage, a component, and an organization preference.
    # Evidence authority belongs to the operation, not to the search route.
    # Collapse exact canonical facts before authoring and remap/merge claims;
    # otherwise downstream plans repeat the same sentence once per obligation.
    canonical_facts: list[CodeFactV1] = []
    fact_index_by_identity: dict[str, int] = {}
    canonical_fact_id_by_input_id: dict[str, str] = {}
    for fact in all_facts:
        # Include the semantic payload alongside the producer identity so a
        # malformed/colliding identity can never merge different operations.
        identity = _digest({
            "canonical_identity": fact.canonical_identity,
            "subject": fact.subject,
            "predicate": fact.predicate,
            "object": fact.object,
            "conditions": fact.conditions,
            "scope": fact.scope,
            "exact_source_digest": fact.exact_source_digest,
        })
        existing_index = fact_index_by_identity.get(identity)
        if existing_index is None:
            fact_index_by_identity[identity] = len(canonical_facts)
            canonical_facts.append(fact)
            canonical_fact_id_by_input_id[fact.fact_id] = fact.fact_id
            continue
        existing = canonical_facts[existing_index]
        canonical_fact_id_by_input_id[fact.fact_id] = existing.fact_id
        canonical_facts[existing_index] = existing.model_copy(update={
            "direct_span_ids": list(dict.fromkeys([
                *existing.direct_span_ids, *fact.direct_span_ids,
            ])),
            "relation_evidence_ids": list(dict.fromkeys([
                *existing.relation_evidence_ids, *fact.relation_evidence_ids,
            ])),
            "relation_kinds": list(dict.fromkeys([
                *existing.relation_kinds, *fact.relation_kinds,
            ])),
            "semantic_context": list(dict.fromkeys([
                *existing.semantic_context, *fact.semantic_context,
            ])),
        })
    all_facts = canonical_facts

    canonical_claims: list[AtomicClaimV3] = []
    claim_index_by_identity: dict[str, int] = {}
    canonical_claim_id_by_input_id: dict[str, str] = {}
    for claim in all_claims:
        remapped_fact_ids = list(dict.fromkeys(
            canonical_fact_id_by_input_id.get(fact_id, fact_id)
            for fact_id in claim.fact_ids
        ))
        identity_payload = {
            "text": " ".join(re.findall(r"[a-z0-9_]+", claim.canonical_text.lower())),
            "fact_ids": sorted(remapped_fact_ids),
            "claim_kind": claim.claim_kind,
            "required_qualifiers": sorted(claim.required_qualifiers),
            "status": claim.status,
        }
        identity = _digest(identity_payload)
        existing_index = claim_index_by_identity.get(identity)
        if existing_index is None:
            claim_index_by_identity[identity] = len(canonical_claims)
            canonical_claim_id_by_input_id[claim.claim_id] = claim.claim_id
            canonical_claims.append(claim.model_copy(update={
                "fact_ids": remapped_fact_ids,
                "canonical_identity": identity,
            }))
            continue
        existing = canonical_claims[existing_index]
        canonical_claim_id_by_input_id[claim.claim_id] = existing.claim_id
        canonical_claims[existing_index] = existing.model_copy(update={
            "covers_obligation_ids": list(dict.fromkeys([
                *existing.covers_obligation_ids, *claim.covers_obligation_ids,
            ])),
            "direct_evidence_ids": list(dict.fromkeys([
                *existing.direct_evidence_ids, *claim.direct_evidence_ids,
            ])),
            "relation_evidence_ids": list(dict.fromkeys([
                *existing.relation_evidence_ids, *claim.relation_evidence_ids,
            ])),
            "unsupported_author_fragments": list(dict.fromkeys([
                *existing.unsupported_author_fragments,
                *claim.unsupported_author_fragments,
            ])),
        })
    all_claims = canonical_claims

    remapped_stage_groups: list[Any] = []
    for group in all_stage_groups:
        ordered_claim_ids = list(dict.fromkeys(
            canonical_claim_id_by_input_id.get(claim_id, claim_id)
            for claim_id in group.ordered_claim_ids
            if canonical_claim_id_by_input_id.get(claim_id, claim_id)
            in {claim.claim_id for claim in all_claims}
        ))
        if not ordered_claim_ids:
            continue
        remapped_stage_groups.append(group.model_copy(update={
            "ordered_claim_ids": ordered_claim_ids,
        }))
    all_stage_groups = remapped_stage_groups

    packet_set: EvidencePacketSetV3 | None = None
    if all_packets:
        packet_payload = [p.model_dump(mode="json") for p in all_packets]
        packet_set = EvidencePacketSetV3(
            producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
            repo_snapshot_id=repo_snapshot_id,
            project_tree_hash=project_tree_hash,
            packets=all_packets,
            content_digest=_digest(packet_payload),
        )
        evidence_packet_digest = packet_set.content_digest

    fact_set: CodeFactSetV1 | None = None
    if all_facts:
        fact_payload = [f.model_dump(mode="json") for f in all_facts]
        fact_set = CodeFactSetV1(
            producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
            repo_snapshot_id=repo_snapshot_id,
            project_tree_hash=project_tree_hash,
            evidence_packet_digest=evidence_packet_digest,
            facts=all_facts,
            content_digest=_digest(fact_payload),
        )
        code_fact_digest = fact_set.content_digest

    claim_set: AtomicClaimSetV3 | None = None
    if all_claims or all_gaps or all_facts:
        claim_payload = {
            "claims": [c.model_dump(mode="json") for c in all_claims],
            "explicit_code_gaps": [g.model_dump(mode="json") for g in all_gaps],
            "semantic_stage_groups": [
                group.model_dump(mode="json") for group in all_stage_groups
            ],
        }
        claim_set = AtomicClaimSetV3(
            producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
            repo_snapshot_id=repo_snapshot_id,
            project_tree_hash=project_tree_hash,
            evidence_packet_digest=evidence_packet_digest,
            code_fact_digest=code_fact_digest,
            claims=all_claims,
            explicit_code_gaps=all_gaps,
            semantic_stage_groups=all_stage_groups,
            content_digest=_digest(claim_payload),
        )

    return packet_set, fact_set, claim_set


def _synthesize_terminal_gaps(
    runtime: ResearchGraphRuntime,
    *,
    fact_set: CodeFactSetV1 | None = None,
) -> tuple[list[ExplicitCodeGapV1], dict[str, list[str]]]:
    """Synthesize explicit gaps for must_cover obligations the gap_finalizer accepted.

    When the gap_finalizer node formally accepts an obligation as
    ``explicit_gap``, it updates ``runtime.agenda.items.status`` to
    ``explicit_gap`` but does not create a corresponding
    ``ExplicitCodeGapV1`` serialization object.  Without this synthesis,
    the coverage report would see no gap binding for that obligation and
    mark it as ``unresolved`` (non-terminal), blocking the authoring
    plan gate even when the gap was already accepted.

    Only obligations with ``status == "explicit_gap"`` are synthesized.
    Obligations that are still ``pending``, ``in_progress``, or
    ``blocked`` are NOT converted to terminal gaps; they remain
    unresolved and MUST block the authoring gate.  Budget exhaustion
    and search exhaustion are independent conditions that should not
    be conflated with ``not_implemented_in_repo``.
    """

    gaps: list[ExplicitCodeGapV1] = []
    bindings: dict[str, list[str]] = {}
    intent_by_id = {
        obligation.obligation_id: obligation
        for obligation in getattr(runtime, "intent_graph", None).obligations
    } if getattr(runtime, "intent_graph", None) is not None else {}
    for item in runtime.agenda.items:
        if item.priority != "must_cover":
            continue
        if item.status != "explicit_gap":
            # Only synthesize for obligations the gap_finalizer has
            # already formally accepted.  ``pending``, ``in_progress``,
            # ``blocked`` and ``supported`` remain as-is; they will
            # appear as unresolved in the coverage report and block
            # the authoring gate.
            continue
        # An obligation can gap early and later be repaired indirectly by
        # evidence gathered for its child stages/components.  Recompute the
        # exact typed boundary against the final aggregate facts before
        # serializing a terminal absence claim.
        obligation = intent_by_id.get(item.obligation_id)
        if fact_set is not None and obligation is not None and obligation.typed_behavior_targets:
            from code2paper.agentic.obligation_fact_alignment import (
                align_target_to_facts,
            )

            if all(
                align_target_to_facts(target, fact_set.facts).status == "resolved"
                for target in obligation.typed_behavior_targets
            ):
                continue
        gap_id = f"gap:synthetic:{item.obligation_id}"
        predicates = sorted(
            {
                p
                for target in item.typed_behavior_targets
                for p in target.desired_predicates
            }
        )
        gap = ExplicitCodeGapV1(
            gap_id=gap_id,
            topic=(
                f"Explicit gap for must_cover obligation {item.obligation_id}"
                f" (predicates: {', '.join(predicates)})"
            ),
            scope="any",
            rationale=(
                f"Gap_finalizer accepted obligation "
                f"{item.obligation_id} as explicit_gap; synthesizing "
                f"terminal gap object for coverage report."
            ),
            source_kind="author_obligation",
        )
        gaps.append(gap)
        bindings[gap_id] = [item.obligation_id]
    return gaps, bindings


def write_v3_evidence_artifacts(
    out_root: str | Path,
    *,
    packet_set: EvidencePacketSetV3 | None,
    fact_set: CodeFactSetV1 | None,
    claim_set: AtomicClaimSetV3 | None,
    equation_set: EquationClaimSetV1 | None = None,
    suffix: str = "_v3",
) -> dict[str, str]:
    """Serialize V3 compiled evidence to the output directory.

    Writes ``evidence_packets_v3_v3.json``, ``code_facts_v1_v3.json`` and
    ``atomic_claims_v3_v3.json`` under ``out_root/artifacts/``.  Returns a
    mapping from artifact key to file path for the keys that were written.
    Missing sets are skipped (no file is written).
    """

    artifacts_dir = Path(out_root) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    if packet_set is not None:
        path = artifacts_dir / f"evidence_packets_v3{suffix}.json"
        _atomic_write_text(
            path,
            json.dumps(packet_set.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        )
        paths["evidence_packets_v3"] = str(path)
    if fact_set is not None:
        path = artifacts_dir / f"code_facts_v1{suffix}.json"
        _atomic_write_text(
            path,
            json.dumps(fact_set.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        )
        paths["code_facts_v1"] = str(path)
    if claim_set is not None:
        path = artifacts_dir / f"atomic_claims_v3{suffix}.json"
        _atomic_write_text(
            path,
            json.dumps(claim_set.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        )
        paths["atomic_claims_v3"] = str(path)
        # Keep the legacy four-artifact contract when no L2 rows exist.  A
        # technical sidecar is an additive artifact only when the claim set
        # actually contains technical-semantic claims; this also avoids
        # creating an empty, non-provenance file on every ordinary L0 run.
        if any(
            getattr(claim, "claim_kind", "") == "technical_semantic"
            or getattr(claim, "inference_level", "") in {"E2", "E3"}
            for claim in claim_set.claims
        ):
            from code2paper.agentic.scientific_claim_ir import write_technical_claims_sidecar

            paths["technical_claims_v1"] = write_technical_claims_sidecar(
                paths["atomic_claims_v3"], claim_set
            )
    if equation_set is None and fact_set is not None:
        proposals = derive_equation_proposals_from_facts(fact_set)
        equation_set, _reports = compile_equation_claims(
            proposals,
            fact_set,
            repo_snapshot_id=fact_set.repo_snapshot_id,
            project_tree_hash=fact_set.project_tree_hash,
        )
    if equation_set is not None:
        path = artifacts_dir / f"equation_claims_v1{suffix}.json"
        write_equation_claims(path, equation_set)
        paths["equation_claims_v1"] = str(path)
    return paths


def write_d25_method_research_artifacts(
    out_root: str | Path,
    *,
    intent_graph: IntentObligationGraphV2,
    coverage_report: Any,
    fact_set: CodeFactSetV1,
    claim_set: AtomicClaimSetV3,
    equation_set: EquationClaimSetV1,
    method_name: str = "",
) -> dict[str, str]:
    """Persist the D2.5 reference/completeness/configuration/plan chain."""

    from code2paper.agentic.configuration_claims import (
        compile_configuration_claims,
    )
    from code2paper.agentic.method_architect import build_method_section_plan
    from code2paper.agentic.method_argument_models import (
        build_completeness_matrix,
        build_reference_method_agenda,
    )

    artifacts_dir = Path(out_root) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    agenda = build_reference_method_agenda(
        intent_graph,
        repo_snapshot_id=claim_set.repo_snapshot_id,
        project_tree_hash=claim_set.project_tree_hash,
        author_goal=str(getattr(intent_graph, "method_goal", "")),
    )
    configurations = compile_configuration_claims(fact_set)

    equation_ids_by_obligation: dict[str, list[str]] = {}
    configuration_ids_by_obligation: dict[str, list[str]] = {}
    for claim in claim_set.claims:
        claim_facts = set(claim.fact_ids)
        claim_relations = set(claim.relation_evidence_ids)
        for obligation_id in claim.covers_obligation_ids:
            equation_ids_by_obligation.setdefault(obligation_id, []).extend(
                equation.equation_id
                for equation in equation_set.equations
                if claim_facts.intersection(equation.fact_ids)
            )
            configuration_ids_by_obligation.setdefault(obligation_id, []).extend(
                configuration.configuration_id
                for configuration in configurations.claims
                if claim_facts.intersection(configuration.source_fact_ids)
                or claim_relations.intersection(configuration.override_chain)
            )
    completeness = build_completeness_matrix(
        agenda,
        coverage_report,
        claim_set=claim_set,
        equation_ids_by_obligation={
            key: tuple(dict.fromkeys(value))
            for key, value in equation_ids_by_obligation.items()
        },
        configuration_ids_by_obligation={
            key: tuple(dict.fromkeys(value))
            for key, value in configuration_ids_by_obligation.items()
        },
    )
    section_plan = build_method_section_plan(
        claims=claim_set,
        completeness=completeness,
        equations=equation_set,
        configurations=configurations,
        method_name=method_name,
    )
    values = {
        "reference_method_agenda_v1": agenda,
        "method_completeness_matrix_v1": completeness,
        "configuration_claims_v1": configurations,
        "method_section_plan_v2": section_plan,
    }
    paths: dict[str, str] = {}
    for key, value in values.items():
        path = artifacts_dir / f"{key}.json"
        _atomic_write_text(path, value.model_dump_json(indent=2) + "\n")
        paths[key] = str(path)
    return paths


# ---------------------------------------------------------------------------
# V3 -> V2 decision conversion
# ---------------------------------------------------------------------------


def convert_v3_decisions_to_agent_decisions(
    v3_decisions: list[ResearchDecisionV1],
) -> list[AgentDecision]:
    """Convert V3 ``ResearchDecisionV1`` records to legacy ``AgentDecision``.

    The legacy ``AgentDecision`` model is what the runner's
    ``AgenticRunState.decisions`` list holds, and what
    ``compute_trace_digest`` consumes.  Each V3 decision becomes one
    ``AgentDecision`` with:

    - ``node`` = ``"research_supervisor"``
    - ``decision`` = the V3 action (e.g. ``"SEARCH_SYMBOLS"``)
    - ``rationale`` = ``f"{produced_by}:{action}"`` plus the V3 rationale
    - ``evidence_ids`` = the V3 decision's tool call IDs
    - ``artifact_keys`` = the obligation ID (for traceability)
    - ``goal`` / ``issue_id`` / ``expected_information_gain`` = preserved
      from the V3 decision so the R8 ``gap_driven_tool_selection``
      criterion can inspect the LLM-originated gap indicators.
    """

    converted: list[AgentDecision] = []
    for dec in v3_decisions:
        tool_call_ids = [call.tool_call_id for call in dec.selected_tool_calls]
        rationale = f"{dec.produced_by}:{dec.action}"
        if dec.rationale:
            rationale = f"{rationale} | {dec.rationale}"
        converted.append(
            AgentDecision(
                node="research_supervisor",
                decision=dec.action,
                rationale=rationale,
                evidence_ids=tool_call_ids,
                artifact_keys=[dec.obligation_id] if dec.obligation_id else [],
                goal=dec.goal,
                issue_id=dec.issue_id,
                expected_information_gain=dec.expected_information_gain,
            )
        )
    return converted


def extract_v3_tool_call_trace_refs(
    v3_decisions: list[ResearchDecisionV1],
) -> list[str]:
    """Extract the tool-call trace references from V3 decisions.

    The R8 acceptance checker uses these refs to verify trace
    reproducibility.  Each ref is a ``tool_call_id`` from a V3
    decision's ``selected_tool_calls``.
    """

    refs: list[str] = []
    for dec in v3_decisions:
        for call in dec.selected_tool_calls:
            refs.append(call.tool_call_id)
    return refs


# ---------------------------------------------------------------------------
# V3 graph wrapper
# ---------------------------------------------------------------------------


class _V3AwareStateSnapshot:
    """Wrapper around a LangGraph ``StateSnapshot`` that also exposes V3 state.

    When the runner calls ``app.get_state(config)`` on a
    :class:`V3GraphWrapper`, the wrapper returns an instance of this
    class so the caller can inspect both the legacy pipeline state
    (via ``.values`` / ``.next`` / ``.metadata``) and the V3 research
    subgraph state (via ``.v3_values`` / ``.v3_next``).

    When V3 checkpointer is not configured or the V3 subgraph has no
    checkpoint for the given thread_id, ``v3_values`` / ``v3_next``
    are ``None`` and the wrapper behaves exactly like the legacy
    snapshot (all attributes are delegated via ``__getattr__``).

    This design lets the runner resume the legacy pipeline using the
    same code path (``app.get_state(config).values``) while also
    making the V3 research subgraph's checkpoint state available for
    diagnostic inspection and V3-aware resume logic.
    """

    def __init__(
        self,
        legacy_snapshot: Any,
        v3_snapshot: Any | None = None,
    ) -> None:
        self._legacy = legacy_snapshot
        self._v3 = v3_snapshot

    # --- legacy delegation -------------------------------------------------

    @property
    def values(self) -> Any:
        """Legacy pipeline state values (``AgenticRunState`` dict)."""

        return self._legacy.values

    @property
    def next(self) -> Any:
        """Next node(s) in the legacy pipeline."""

        return self._legacy.next

    @property
    def metadata(self) -> Any:
        """Legacy checkpoint metadata."""

        return self._legacy.metadata

    @property
    def config(self) -> Any:
        """Legacy checkpoint config."""

        return self._legacy.config

    def __getattr__(self, name: str) -> Any:
        # Delegate any other attribute (e.g. ``tasks``, ``created_at``)
        # to the legacy snapshot so the wrapper is transparent for
        # callers that introspect LangGraph internals.
        return getattr(self._legacy, name)

    # --- V3 accessors ------------------------------------------------------

    @property
    def v3_values(self) -> Any:
        """V3 subgraph state values, or ``None`` when not available.

        Returns the ``AgentStateV3`` dict from the V3 research
        subgraph's checkpoint.  ``None`` means V3 checkpointer is not
        configured or no checkpoint exists for the V3 thread_id.
        """

        if self._v3 is None:
            return None
        return self._v3.values

    @property
    def v3_next(self) -> Any:
        """V3 subgraph next node(s), or ``None`` when not available."""

        if self._v3 is None:
            return None
        return self._v3.next

    @property
    def v3_metadata(self) -> Any:
        """V3 subgraph checkpoint metadata, or ``None`` when not available."""

        if self._v3 is None:
            return None
        return self._v3.metadata

    @property
    def has_v3_state(self) -> bool:
        """``True`` when a V3 checkpoint is available for inspection."""

        return self._v3 is not None


class V3GraphWrapper:
    """Wraps the V3 research subgraph and the legacy pipeline.

    When ``CODE2PAPER_AGENTIC_RESEARCH_V3=1`` is set, the runner
    instantiates this wrapper and passes it as ``graph_app`` to
    ``run_agentic_code2paper``.  The wrapper:

    1. Runs the V3 research subgraph (with ``GemmaSupervisorBackend``)
       to produce the V3 decision trace.  The subgraph is the
       multi-node LangGraph topology (9 checkpointable nodes) so each
       step is individually inspectable and the node execution trace
       is available for R8 verification.
    2. Runs the legacy ``build_code2paper_graph`` pipeline to produce
       the full Method text, evidence and validation reports.
    3. Merges the V3 decisions and tool-call trace refs into the
       legacy state so the R8 acceptance checker can verify the trace.

    The wrapper exposes ``invoke(state, config=...)`` so it is
    interchangeable with a compiled LangGraph app.  ``get_state(config)``
    returns a :class:`_V3AwareStateSnapshot` that exposes both the
    legacy pipeline state (via ``.values``) and the V3 research
    subgraph state (via ``.v3_values``) when a V3 checkpointer is
    configured.

    V3 research failures are NOT silently swallowed: the wrapper
    records the failure in ``self._last_v3_error`` and surfaces it in
    the legacy payload's ``v3_error`` field so the R8 acceptance
    checker can fail the run instead of silently downgrading.
    """

    def __init__(
        self,
        *,
        v3_runtime: ResearchGraphRuntime,
        legacy_graph: Any,
        max_research_turns: int = 50,
        v3_checkpointer: Any = None,
        v3_thread_id: str | None = None,
        packet_repair_owner: Any | None = None,
    ) -> None:
        self._runtime = v3_runtime
        self._legacy = legacy_graph
        self._max_research_turns = max_research_turns
        self._last_v3_result: ResearchLoopResult | None = None
        self._last_v3_error: str | None = None
        self._v3_checkpointer = v3_checkpointer
        self._v3_thread_id = v3_thread_id
        self._packet_repair_owner = packet_repair_owner

    @property
    def v3_runtime(self) -> ResearchGraphRuntime:
        return self._runtime

    @property
    def last_v3_result(self) -> ResearchLoopResult | None:
        """Most recent V3 ``ResearchLoopResult`` (for inspection/tests)."""

        return self._last_v3_result

    @property
    def last_v3_error(self) -> str | None:
        """Most recent V3 error message (None when V3 succeeded)."""

        return self._last_v3_error

    def invoke(
        self,
        state: dict[str, Any] | None,
        *args: Any,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run V3 research then the legacy pipeline, merging decisions.

        Per the P0 fix for the V3 evidence chain: after V3 research
        completes, the compiled evidence packets / facts / claims are
        serialized to the output directory and their file paths are
        injected into the legacy state's ``artifacts`` dict under the
        standard keys (``evidence_packets_v3`` / ``code_facts_v1`` /
        ``atomic_claims_v3``) so the legacy writer and the R8 acceptance
        checker can consume them.

        V3 research failures are recorded in ``self._last_v3_error``
        and surfaced in the legacy payload's ``v3_error`` field.  The
        legacy pipeline still runs (so partial artifacts are preserved
        for debugging), but the R8 acceptance checker will fail the
        run because the V3 evidence chain is broken.
        """

        # A completed LangGraph checkpoint is resumed with ``state=None``.
        # Its V3 research and evidence are already represented by the stored
        # legacy state.  Rerunning V3 here would consume new model/tool budget
        # and make an otherwise identical resume produce a different trace.
        if state is None:
            resumed = self._legacy.invoke(None, *args, config=config, **kwargs)
            if isinstance(resumed, dict):
                payload = dict(resumed)
            elif resumed:
                payload = dict(resumed)
            else:
                # LangGraph returns ``None`` when the checkpoint already has
                # no pending tasks.  The completed state is still available
                # through get_state and must be returned to the runner.
                snapshot = self._legacy.get_state(config)
                payload = dict(getattr(snapshot, "values", {}) or {})
            self._restore_v3_checkpoint_evidence(payload)
            self._register_generic_research_manifest(payload)
            return payload

        # 1. Run the V3 research phase via the multi-node LangGraph
        # subgraph (build_research_subgraph).  This is the production
        # path — the procedural run_research_loop helper is not used.
        v3_decisions: list[ResearchDecisionV1] = []
        v3_tool_call_refs: list[str] = []
        v3_artifact_paths: dict[str, str] = {}
        v3_error: str | None = None
        v3_node_trace: list[dict[str, Any]] = []
        out_root_for_tools = _extract_out_root(state)
        if out_root_for_tools is not None and self._runtime.artifact_root is None:
            self._runtime = self._runtime.model_copy(
                update={"artifact_root": Path(out_root_for_tools) / "artifacts"}
            )
        execution_artifact_paths = (
            _persist_execution_profile_artifacts(out_root_for_tools, self._runtime)
            if out_root_for_tools is not None
            else {}
        )

        # Opt-in and rollback routes that are not authorized to execute must
        # leave the legacy default untouched.  Shadow routes still execute so
        # their observations can be compared, while the route artifact makes
        # the distinction explicit to rollout tooling.
        if (
            self._runtime.execution_profile is not None
            and not self._runtime.execution_enabled
            and not self._runtime.execution_shadow
        ):
            legacy_payload = self._legacy.invoke(state, *args, config=config, **kwargs)
            if not isinstance(legacy_payload, dict):
                legacy_payload = dict(legacy_payload or {})
            legacy_payload.update(_execution_control_payload(self._runtime))
            if execution_artifact_paths:
                payload_artifacts = dict(legacy_payload.get("artifacts") or {})
                payload_artifacts.update(execution_artifact_paths)
                legacy_payload["artifacts"] = payload_artifacts
            return legacy_payload
        try:
            v3_result = run_v3_research_phase(
                self._runtime,
                max_turns=self._max_research_turns,
                checkpointer=self._v3_checkpointer,
                thread_id=self._v3_thread_id,
            )
            self._last_v3_result = v3_result
            if self._packet_repair_owner is not None:
                self._packet_repair_owner.bind_loop_state(v3_result.loop_state)
            v3_decisions = list(v3_result.decision_trace)
            v3_tool_call_refs = extract_v3_tool_call_trace_refs(v3_decisions)
            # Phase 2.5: collect the formal node execution trace for
            # R8 verification.  Each entry records the node name,
            # timestamp, duration, turn index, status and error.
            v3_node_trace = list(getattr(v3_result, "node_trace", []) or [])
            # R4 evidence chain: merge per-obligation compiled evidence
            # and serialize it to the output directory so the legacy
            # pipeline can consume the V3 artifacts.
            compiled_evidence = getattr(v3_result.loop_state, "compiled_evidence", {})
            packet_set: EvidencePacketSetV3 | None = None
            fact_set: CodeFactSetV1 | None = None
            claim_set: AtomicClaimSetV3 | None = None
            equation_set: EquationClaimSetV1 | None = None
            # Synthesize terminal gaps for must_cover obligations the
            # research loop did not resolve (e.g. max_turns reached
            # before gap_finalizer accepted a gap).  This prevents
            # non-terminal ``unresolved`` must_cover items from blocking
            # the authoring plan gate.
            synthetic_gaps: list[ExplicitCodeGapV1] = []
            synthetic_gap_bindings: dict[str, list[str]] = {}
            if compiled_evidence:
                packet_set, fact_set, claim_set = merge_compiled_evidence(
                    compiled_evidence,
                    repo_snapshot_id=self._runtime.repo_snapshot.snapshot_id,
                    project_tree_hash=self._runtime.repo_snapshot.project_tree_hash,
                )
                intent_graph = getattr(self._runtime, "intent_graph", None)
                if intent_graph is not None and fact_set is not None and claim_set is not None:
                    from code2paper.agentic.obligation_fact_alignment import (
                        bind_claims_to_obligations,
                    )

                    claim_set = bind_claims_to_obligations(
                        intent_graph,
                        fact_set=fact_set,
                        claim_set=claim_set,
                    )
                synthetic_gaps, synthetic_gap_bindings = _synthesize_terminal_gaps(
                    self._runtime,
                    fact_set=fact_set,
                )
                # Append synthetic gaps to the claim_set so the coverage
                # report marks unresolved must_cover obligations as
                # ``explicit_gap`` (terminal).  The content_digest must be
                # recomputed so the freshness checker (which hashes
                # claims/explicit_code_gaps/semantic_stage_groups) sees a
                # consistent artifact; otherwise resume validation flags
                # the claim set as stale.
                if synthetic_gaps and claim_set is not None:
                    claim_set.explicit_code_gaps.extend(synthetic_gaps)
                    _recompute_claim_set_digest(claim_set)
                if fact_set is not None:
                    equation_set, _equation_reports = compile_equation_claims(
                        derive_equation_proposals_from_facts(fact_set),
                        fact_set,
                        repo_snapshot_id=fact_set.repo_snapshot_id,
                        project_tree_hash=fact_set.project_tree_hash,
                    )
                    if claim_set is not None:
                        equation_set = bind_equations_to_claims(
                            equation_set,
                            claim_set,
                        )
                out_root = _extract_out_root(state)
                if out_root is not None:
                    v3_artifact_paths = write_v3_evidence_artifacts(
                        out_root,
                        packet_set=packet_set,
                        fact_set=fact_set,
                        claim_set=claim_set,
                        equation_set=equation_set,
                    )
                    # source_authority_policy is written unconditionally
                    # below (outside the ``if compiled_evidence`` block)
                    # so runs where no obligation compiled still persist the
                    # policy for the R8 protocol-settings check.
                    artifacts_dir = Path(out_root) / "artifacts"
                    artifacts_dir.mkdir(parents=True, exist_ok=True)
                    if intent_graph is not None:
                        intent_path = artifacts_dir / "intent_obligation_graph_v2.json"
                        _atomic_write_text(
                            intent_path,
                            json.dumps(
                                intent_graph.model_dump(mode="json"),
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n",
                        )
                        v3_artifact_paths["intent_obligation_graph_v2"] = str(intent_path)
                        if fact_set is not None and claim_set is not None:
                            from code2paper.agentic.obligation_fact_alignment import (
                                build_obligation_coverage_v2,
                            )

                            coverage = build_obligation_coverage_v2(
                                intent_graph,
                                fact_set=fact_set,
                                claim_set=claim_set,
                                explicit_gaps=claim_set.explicit_code_gaps,
                                gap_obligation_bindings=synthetic_gap_bindings or None,
                            )
                            coverage_path = artifacts_dir / "obligation_coverage_v2.json"
                            _atomic_write_text(
                                coverage_path,
                                json.dumps(
                                    coverage.model_dump(mode="json"),
                                    ensure_ascii=False,
                                    indent=2,
                                )
                                + "\n",
                            )
                            v3_artifact_paths["obligation_coverage_v2"] = str(coverage_path)
                            if equation_set is not None:
                                v3_artifact_paths.update(
                                    write_d25_method_research_artifacts(
                                        out_root,
                                        intent_graph=intent_graph,
                                        coverage_report=coverage,
                                        fact_set=fact_set,
                                        claim_set=claim_set,
                                        equation_set=equation_set,
                                    )
                                )
                    if os.environ.get(
                        "CODE2PAPER_AGENTIC_BEHAVIOR_TEMPLATES", "1"
                    ).strip().lower() not in {"0", "false", "no", "off"}:
                        from code2paper.agentic.behavior_templates import (
                            DEFAULT_BEHAVIOR_DISCOVERY_TEMPLATES,
                            match_all_templates,
                        )

                        behavior_graph = v3_result.loop_state.behavior_graph
                        matches = match_all_templates(
                            DEFAULT_BEHAVIOR_DISCOVERY_TEMPLATES,
                            behavior_graph,
                        )
                        templates_by_id = {
                            item.template_id: item
                            for item in DEFAULT_BEHAVIOR_DISCOVERY_TEMPLATES
                        }
                        template_payload = {
                            "mode": "behavior-template-organization-hints-v1",
                            "behavior_graph_digest": behavior_graph.content_digest,
                            "authorization_effect": "none",
                            "matches": [
                                match.model_dump(mode="json")
                                for match in matches
                                if match.matched
                            ],
                            "stage_hints": [
                                hint.model_dump(mode="json")
                                for match in matches
                                if match.matched
                                for hint in templates_by_id[match.template_id].stage_hints
                            ],
                        }
                        template_path = artifacts_dir / "behavior_template_matches_v1.json"
                        _atomic_write_text(
                            template_path,
                            json.dumps(template_payload, ensure_ascii=False, indent=2) + "\n",
                        )
                        v3_artifact_paths["behavior_template_matches_v1"] = str(template_path)
            # Intent proposal provenance is required even when every generic
            # obligation ends as an explicit gap and no evidence set exists.
            out_root = _extract_out_root(state)
            if out_root is not None:
                artifacts_dir = Path(out_root) / "artifacts"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                # The V3 state always carries the exact source-authority
                # policy used during research.  Persist and bridge it into
                # the legacy artifact map; otherwise the R8 summary sees an
                # empty policy and cannot prove that paper/README/TeX were
                # kept below executable authority.
                #
                # This write is unconditional (not gated on
                # ``compiled_evidence``) so runs where no obligation
                # compiled still persist the policy for the R8
                # protocol-settings check.  When the final state lost the
                # policy (e.g. LangGraph channel quirk), fall back to the
                # default policy used at V3 state initialization.
                if "source_authority_policy" not in v3_artifact_paths:
                    source_policy = dict(
                        (getattr(v3_result, "final_state", {}) or {}).get(
                            "source_authority_policy", {}
                        )
                    )
                    if not source_policy:
                        from code2paper.agentic.source_authority import (
                            default_source_authority_policy,
                        )

                        source_policy = default_source_authority_policy().model_dump(
                            mode="json"
                        )
                    if source_policy:
                        policy_path = artifacts_dir / "source_authority_policy_v1.json"
                        _atomic_write_text(
                            policy_path,
                            json.dumps(source_policy, ensure_ascii=False, indent=2) + "\n",
                        )
                        v3_artifact_paths["source_authority_policy"] = str(policy_path)
                intent_graph = getattr(self._runtime, "intent_graph", None)
                if intent_graph is not None and "intent_obligation_graph_v2" not in v3_artifact_paths:
                    intent_path = artifacts_dir / "intent_obligation_graph_v2.json"
                    _atomic_write_text(
                        intent_path,
                        json.dumps(
                            intent_graph.model_dump(mode="json"),
                            ensure_ascii=False,
                            indent=2,
                        ) + "\n",
                    )
                    v3_artifact_paths["intent_obligation_graph_v2"] = str(intent_path)
                proposal_report = dict(
                    getattr(self._runtime, "intent_target_proposal_report", {}) or {}
                )
                proposal_path = artifacts_dir / "intent_target_proposal_report_v1.json"
                _atomic_write_text(
                    proposal_path,
                    json.dumps(proposal_report, ensure_ascii=False, indent=2) + "\n",
                )
                v3_artifact_paths["intent_target_proposal_report_v1"] = str(proposal_path)
                # Fallback: when no obligation compiled successfully
                # (``compiled_evidence`` was empty) but there are
                # synthetic gaps, create a minimal claim_set with the
                # gaps, write V3 artifacts and build the coverage
                # report so the legacy authoring stage does not block
                # on ``generic_path_compilation_required``.
                if (
                    "obligation_coverage_v2" not in v3_artifact_paths
                    and synthetic_gaps
                ):
                    intent_graph = getattr(self._runtime, "intent_graph", None)
                    if intent_graph is not None:
                        import hashlib as _hashlib

                        def _digest_fallback(payload: Any) -> str:
                            encoded = json.dumps(
                                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                            ).encode("utf-8")
                            return "sha256:" + _hashlib.sha256(encoded).hexdigest()

                        # Minimal packet_set with empty packets so the
                        # legacy authoring stage's ``evidence_packets_v3``
                        # artifact check passes.  The content_digest must
                        # match _digest_json(packets) so the artifact
                        # freshness check passes on resume.
                        if packet_set is None:
                            packet_set = EvidencePacketSetV3(
                                producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
                                repo_snapshot_id=self._runtime.repo_snapshot.snapshot_id,
                                project_tree_hash=self._runtime.repo_snapshot.project_tree_hash,
                                packets=[],
                                content_digest=_digest_fallback([]),
                            )
                        gap_payload = [g.model_dump(mode="json") for g in synthetic_gaps]
                        claim_payload = {
                            "claims": [],
                            "explicit_code_gaps": gap_payload,
                            "semantic_stage_groups": [],
                        }
                        claim_set = AtomicClaimSetV3(
                            producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
                            repo_snapshot_id=self._runtime.repo_snapshot.snapshot_id,
                            project_tree_hash=self._runtime.repo_snapshot.project_tree_hash,
                            evidence_packet_digest=packet_set.content_digest,
                            code_fact_digest="",
                            claims=[],
                            explicit_code_gaps=list(synthetic_gaps),
                            content_digest=_digest_fallback(claim_payload),
                        )
                        v3_artifact_paths.update(
                            write_v3_evidence_artifacts(
                                out_root,
                                packet_set=packet_set,
                                fact_set=fact_set,
                                claim_set=claim_set,
                            )
                        )
                        from code2paper.agentic.obligation_fact_alignment import (
                            build_obligation_coverage_v2,
                        )

                        coverage = build_obligation_coverage_v2(
                            intent_graph,
                            fact_set=fact_set,
                            claim_set=claim_set,
                            explicit_gaps=claim_set.explicit_code_gaps,
                            gap_obligation_bindings=synthetic_gap_bindings or None,
                        )
                        coverage_path = (
                            artifacts_dir / "obligation_coverage_v2.json"
                        )
                        _atomic_write_text(
                            coverage_path,
                            json.dumps(
                                coverage.model_dump(mode="json"),
                                ensure_ascii=False,
                                indent=2,
                            )
                            + "\n",
                        )
                        v3_artifact_paths["obligation_coverage_v2"] = str(
                            coverage_path
                        )
        except Exception as exc:  # noqa: BLE001 — record error, then run legacy
            v3_error = f"{type(exc).__name__}: {exc}"
            self._last_v3_error = v3_error
            _logger.warning("v3_research_phase_failed: %s", exc)

        # 1.5 Inject the authoritative generic V3 artifacts before the
        # compatibility pipeline runs.  Existing same-key profile artifacts
        # are diagnostics only and cannot shadow the research owner.
        if v3_artifact_paths and isinstance(state, dict):
            existing_artifacts = dict(state.get("artifacts") or {})
            for key, path in v3_artifact_paths.items():
                existing_artifacts[key] = path
            state["artifacts"] = existing_artifacts

        # 2. Run the legacy pipeline.
        legacy_payload = self._legacy.invoke(state, *args, config=config, **kwargs)
        if not isinstance(legacy_payload, dict):
            legacy_payload = dict(legacy_payload or {})
        legacy_payload.update(_execution_control_payload(self._runtime))

        # 3. Merge V3 decisions and tool-call trace refs.
        if v3_decisions:
            converted = convert_v3_decisions_to_agent_decisions(v3_decisions)
            existing_decisions = legacy_payload.get("decisions") or []
            legacy_payload["decisions"] = [*existing_decisions, *converted]
        if v3_tool_call_refs:
            existing_refs = list(legacy_payload.get("tool_call_trace_refs") or [])
            for ref in v3_tool_call_refs:
                if ref not in existing_refs:
                    existing_refs.append(ref)
            legacy_payload["tool_call_trace_refs"] = existing_refs

        # 3.5 Also merge V3 artifact paths into the legacy payload so
        # downstream consumers (R8 checker) can find them even when the
        # legacy pipeline did not produce its own evidence artifacts.
        if v3_artifact_paths:
            payload_artifacts = dict(legacy_payload.get("artifacts") or {})
            for key, path in v3_artifact_paths.items():
                # The V3 research owner is authoritative for canonical
                # research artifacts.  A legacy checkpoint/profile artifact
                # with the same key must not shadow the generic chain.
                payload_artifacts[key] = path
            legacy_payload["artifacts"] = payload_artifacts

        if execution_artifact_paths:
            payload_artifacts = dict(legacy_payload.get("artifacts") or {})
            payload_artifacts.update(execution_artifact_paths)
            legacy_payload["artifacts"] = payload_artifacts

        # 3.5.1 Register a provenance sidecar only when the canonical typed
        # sets already identify the generic research data plane.  Legacy or
        # profile-produced artifacts are never relabelled.
        self._register_generic_research_manifest(legacy_payload)

        # 3.6 Surface V3 errors in the legacy payload so the R8
        # acceptance checker can fail the run instead of silently
        # downgrading to a non-V3 pipeline.  When ``v3_error`` is None
        # the field is omitted so existing tests that don't check for
        # it continue to work.
        if v3_error:
            legacy_payload["v3_error"] = v3_error

        # 3.7 Inject V3 node execution trace (Phase 2.5) so the R8
        # acceptance checker and the run summary can verify the
        # multi-node LangGraph topology actually executed.  Each entry
        # records the node name, timestamp, duration, turn index,
        # status and error.  The trace is always a list (empty when V3
        # research failed before producing a trace).
        legacy_payload["v3_node_trace"] = v3_node_trace

        return legacy_payload

    def _restore_v3_checkpoint_evidence(self, payload: dict[str, Any]) -> None:
        """Reattach post-graph V3 evidence to a completed legacy resume.

        V3 decisions are intentionally merged after the legacy LangGraph
        finishes, so they are not part of the legacy graph checkpoint.  A
        completed resume therefore has to recover the decision trace from the
        V3 checkpoint; otherwise the resumed state silently loses the V3
        supervisor decisions and produces a different final-state digest.
        """

        if self._v3_checkpointer is None or self._v3_thread_id is None:
            return
        try:
            subgraph = build_research_subgraph(
                self._runtime,
                max_turns=self._max_research_turns,
                checkpointer=self._v3_checkpointer,
            )
            snapshot = subgraph.get_state(
                {"configurable": {"thread_id": self._v3_thread_id}}
            )
            values = dict(getattr(snapshot, "values", {}) or {})
            loop_snapshot = dict(values.get("loop_state_snapshot") or {})
            immutable = load_immutable_loop_payload(self._runtime, loop_snapshot) or {}
            raw_decisions = list(
                immutable.get("decision_trace")
                or loop_snapshot.get("decision_trace")
                or []
            )
            v3_decisions = [
                item
                if isinstance(item, ResearchDecisionV1)
                else ResearchDecisionV1.model_validate(item)
                for item in raw_decisions
            ]
            if v3_decisions:
                existing_decisions = list(payload.get("decisions") or [])
                payload["decisions"] = [
                    *existing_decisions,
                    *convert_v3_decisions_to_agent_decisions(v3_decisions),
                ]
                existing_refs = list(payload.get("tool_call_trace_refs") or [])
                for ref in extract_v3_tool_call_trace_refs(v3_decisions):
                    if ref not in existing_refs:
                        existing_refs.append(ref)
                payload["tool_call_trace_refs"] = existing_refs
        except Exception as exc:  # noqa: BLE001 -- surfaced to R8, not hidden
            message = f"{type(exc).__name__}: {exc}"
            self._last_v3_error = message
            payload["v3_error"] = message

    def _register_generic_research_manifest(self, payload: dict[str, Any]) -> None:
        """Register provenance only for already-generic typed artifacts.

        D2 forbids producer laundering: a legacy/profile producer is never
        rewritten into a generic producer.  The manifest is emitted only when
        all three canonical sets already carry the exact generic data-plane
        version and agree on snapshot identity.
        """

        artifacts = dict(payload.get("artifacts") or {})
        typed_keys = (
            ("evidence_packets_v3", "packets"),
            ("code_facts_v1", "facts"),
            ("atomic_claims_v3", "claims"),
        )
        loaded: dict[str, dict[str, Any]] = {}
        evidence_dir: Path | None = None
        for artifact_key, _collection_key in typed_keys:
            path_value = str(artifacts.get(artifact_key) or "")
            path = Path(path_value) if path_value else None
            if path is None or not path.is_file():
                return
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return
            if not isinstance(value, dict):
                return
            if (
                str(value.get("producer_version") or "")
                != GENERIC_RESEARCH_PRODUCER_VERSION
            ):
                return
            loaded[artifact_key] = value
            evidence_dir = evidence_dir or path.parent

        snapshot_ids = {
            str(value.get("repo_snapshot_id") or "")
            for value in loaded.values()
        }
        tree_hashes = {
            str(value.get("project_tree_hash") or "")
            for value in loaded.values()
        }
        if (
            len(snapshot_ids) != 1
            or "" in snapshot_ids
            or len(tree_hashes) != 1
            or "" in tree_hashes
            or evidence_dir is None
        ):
            return

        packets = loaded["evidence_packets_v3"]
        facts = loaded["code_facts_v1"]
        claims = loaded["atomic_claims_v3"]
        manifest = {
            "schema_version": "1.0",
            "producer": "generic_research_data_plane",
            "producer_version": GENERIC_RESEARCH_PRODUCER_VERSION,
            "profile_authoritative": False,
            "repo_snapshot_id": next(iter(snapshot_ids)),
            "project_tree_hash": next(iter(tree_hashes)),
            "evidence_packet_digest": str(packets.get("content_digest") or ""),
            "code_fact_digest": str(facts.get("content_digest") or ""),
            "claim_set_digest": str(claims.get("content_digest") or ""),
            "compiled_claim_count": len(claims.get("claims") or []),
            "compiled_fact_count": len(facts.get("facts") or []),
        }
        manifest["content_digest"] = "sha256:" + hashlib.sha256(
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        manifest_path = (
            evidence_dir / "generic_research_compilation_manifest_v3.json"
        )
        _atomic_write_text(
            manifest_path,
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        artifacts["generic_research_compilation_manifest"] = str(manifest_path)
        payload["artifacts"] = artifacts

    def get_state(self, config: dict[str, Any] | None = None) -> Any:
        """Return a V3-aware state snapshot for checkpoint resume.

        When V3 checkpointer and thread_id are configured, the returned
        object exposes both the legacy pipeline state (via ``.values``)
        and the V3 research subgraph state (via ``.v3_values``).  This
        lets the runner resume the legacy pipeline using the standard
        ``app.get_state(config).values`` code path while also making
        the V3 research subgraph's checkpoint state available for
        diagnostic inspection and V3-aware resume logic.

        When V3 checkpointer is not configured, the returned object
        delegates everything to the legacy snapshot (transparent
        passthrough — existing callers see no difference).
        """

        legacy_snapshot = self._legacy.get_state(config)

        # When V3 checkpointer is not configured, return the legacy
        # snapshot directly (transparent passthrough).
        if self._v3_checkpointer is None or self._v3_thread_id is None:
            return legacy_snapshot

        # Build a temporary subgraph to query V3 state from the
        # checkpointer.  This does NOT execute any nodes — LangGraph's
        # ``get_state`` reads from the checkpointer's storage without
        # invoking the graph.  The temporary subgraph is discarded
        # after the query.
        try:
            v3_subgraph = build_research_subgraph(
                self._runtime,
                max_turns=self._max_research_turns,
                checkpointer=self._v3_checkpointer,
            )
            v3_config = {"configurable": {"thread_id": self._v3_thread_id}}
            v3_snapshot = v3_subgraph.get_state(v3_config)
            return _V3AwareStateSnapshot(legacy_snapshot, v3_snapshot)
        except Exception as exc:  # noqa: BLE001 — V3 state query is best-effort
            _logger.debug("v3_state_query_failed: %s", exc)
            return legacy_snapshot

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to the legacy graph."""

        return getattr(self._legacy, name)


# ---------------------------------------------------------------------------
# V3 graph builder (entry point for the runner)
# ---------------------------------------------------------------------------


def build_code2paper_v3_graph(
    tool_registry: Mapping[str, Code2PaperStageTool],
    *,
    v3_runtime: ResearchGraphRuntime,
    decision_provider: DecisionProvider | None = None,
    semantic_verifier: SemanticVerifier | None = None,
    checkpointer: Any = None,
    max_research_turns: int = 50,
    v3_checkpointer: Any = None,
    v3_thread_id: str | None = None,
) -> V3GraphWrapper:
    """Build a V3 graph wrapper around the legacy pipeline.

    When ``CODE2PAPER_AGENTIC_RESEARCH_V3=1`` is set, the runner uses
    this instead of ``build_code2paper_graph``.  The wrapper runs the
    V3 research subgraph first (with ``GemmaSupervisorBackend``), then
    the legacy pipeline, and merges the V3 decisions into the final
    state.

    ``checkpointer`` is the LEGACY pipeline's checkpointer (used by
    ``build_code2paper_graph``).  ``v3_checkpointer`` and
    ``v3_thread_id`` are the V3 research subgraph's checkpointer and
    thread ID — when provided, the V3 subgraph is compiled with the
    checkpointer and invoked with the thread_id so checkpoint/resume
    works for the V3 research phase.
    """

    from code2paper.agentic.packet_repair_owner import ScopedPacketRepairOwner

    packet_repair_owner = ScopedPacketRepairOwner(v3_runtime)
    legacy_graph = build_code2paper_graph(
        tool_registry,
        decision_provider=decision_provider,
        semantic_verifier=semantic_verifier,
        checkpointer=checkpointer,
        packet_repair_owner=packet_repair_owner,
    )
    return V3GraphWrapper(
        v3_runtime=v3_runtime,
        legacy_graph=legacy_graph,
        max_research_turns=max_research_turns,
        v3_checkpointer=v3_checkpointer,
        v3_thread_id=v3_thread_id,
        packet_repair_owner=packet_repair_owner,
    )


__all__ = [
    "V3GraphWrapper",
    "build_code2paper_v3_graph",
    "build_research_agenda_from_intent_graph",
    "build_v3_research_runtime",
    "convert_v3_decisions_to_agent_decisions",
    "extract_v3_tool_call_trace_refs",
    "merge_compiled_evidence",
    "run_v3_research_phase",
    "write_v3_evidence_artifacts",
]
