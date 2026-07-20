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
   observations and agenda updates.
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
- Temperature is forced to 0 and cache is forced off (R8.1 protocol
  rules 2 and 3) by ``GemmaSupervisorBackend`` regardless of the input
  ``LLMConfig``.
- The V3 decision trace is preserved verbatim in the run summary's
  ``decisions`` list so ``compute_trace_digest`` and the R8 acceptance
  checker can verify reproducibility.
"""

from __future__ import annotations

import json
import logging
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
)
from code2paper.agentic.gemma_supervisor_backend import GemmaSupervisorBackend
from code2paper.agentic.graph import build_code2paper_graph
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    compile_intent_obligation_graph_v2,
)
from code2paper.agentic.research_graph import (
    CompiledEvidence,
    CompiledResearchSubgraph,
    ResearchLoopResult,
    build_research_subgraph,
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
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.schemas import LLMConfig

_logger = logging.getLogger(__name__)


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

    items: list[ResearchAgendaItemV1] = []
    for obl in intent_graph.obligations:
        missing_info: list[str] = []
        for query in obl.retrieval_queries:
            if query and query not in missing_info:
                missing_info.append(query)
        for path in obl.candidate_paths:
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
                candidate_symbol_ids=list(obl.candidate_paths),
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

    agenda = build_research_agenda_from_intent_graph(
        intent_graph,
        run_id=run_id,
        repo_snapshot=repo_snapshot,
    )

    effective_llm_config = llm_config or load_llm_config_from_env()
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
        supervisor_backend=supervisor_backend,
        ready_tools=ready_tools,
        hard_rules=hard_rules,
    )


# ---------------------------------------------------------------------------
# V3 research phase execution
# ---------------------------------------------------------------------------


def run_v3_research_phase(
    runtime: ResearchGraphRuntime,
    *,
    max_turns: int = 50,
) -> ResearchLoopResult:
    """Run the V3 research subgraph and return the loop result.

    The research subgraph is built fresh each call so the runtime
    (including the supervisor backend) is respected.  The result carries
    the full decision trace, observation list and final state.
    """

    initial_state = empty_agent_state_v3(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    )
    return run_research_loop(runtime, initial_state=initial_state.to_state_dict(), max_turns=max_turns)


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
    evidence_packet_digest = ""
    code_fact_digest = ""
    for entry in compiled_evidence.values():
        all_packets.extend(entry.packet_set.packets)
        all_facts.extend(entry.fact_set.facts)
        all_claims.extend(entry.claim_set.claims)
        all_gaps.extend(entry.claim_set.explicit_code_gaps)
        if not evidence_packet_digest:
            evidence_packet_digest = entry.fact_set.evidence_packet_digest
        if not code_fact_digest:
            code_fact_digest = entry.claim_set.code_fact_digest

    import hashlib
    import json as _json

    def _digest(payload: Any) -> str:
        encoded = _json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    packet_set: EvidencePacketSetV3 | None = None
    if all_packets:
        packet_payload = [p.model_dump(mode="json") for p in all_packets]
        packet_set = EvidencePacketSetV3(
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
            repo_snapshot_id=repo_snapshot_id,
            project_tree_hash=project_tree_hash,
            evidence_packet_digest=evidence_packet_digest,
            facts=all_facts,
            content_digest=_digest(fact_payload),
        )
        code_fact_digest = fact_set.content_digest

    claim_set: AtomicClaimSetV3 | None = None
    if all_claims:
        claim_payload = {
            "claims": [c.model_dump(mode="json") for c in all_claims],
            "explicit_code_gaps": [g.model_dump(mode="json") for g in all_gaps],
        }
        claim_set = AtomicClaimSetV3(
            repo_snapshot_id=repo_snapshot_id,
            project_tree_hash=project_tree_hash,
            evidence_packet_digest=evidence_packet_digest,
            code_fact_digest=code_fact_digest,
            claims=all_claims,
            explicit_code_gaps=all_gaps,
            content_digest=_digest(claim_payload),
        )

    return packet_set, fact_set, claim_set


def write_v3_evidence_artifacts(
    out_root: str | Path,
    *,
    packet_set: EvidencePacketSetV3 | None,
    fact_set: CodeFactSetV1 | None,
    claim_set: AtomicClaimSetV3 | None,
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
        path.write_text(
            json.dumps(packet_set.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths["evidence_packets_v3"] = str(path)
    if fact_set is not None:
        path = artifacts_dir / f"code_facts_v1{suffix}.json"
        path.write_text(
            json.dumps(fact_set.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths["code_facts_v1"] = str(path)
    if claim_set is not None:
        path = artifacts_dir / f"atomic_claims_v3{suffix}.json"
        path.write_text(
            json.dumps(claim_set.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths["atomic_claims_v3"] = str(path)
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


class V3GraphWrapper:
    """Wraps the V3 research subgraph and the legacy pipeline.

    When ``CODE2PAPER_AGENTIC_RESEARCH_V3=1`` is set, the runner
    instantiates this wrapper and passes it as ``graph_app`` to
    ``run_agentic_code2paper``.  The wrapper:

    1. Runs the V3 research subgraph (with ``GemmaSupervisorBackend``)
       to produce the V3 decision trace.
    2. Runs the legacy ``build_code2paper_graph`` pipeline to produce
       the full Method text, evidence and validation reports.
    3. Merges the V3 decisions and tool-call trace refs into the
       legacy state so the R8 acceptance checker can verify the trace.

    The wrapper exposes ``invoke(state, config=...)`` so it is
    interchangeable with a compiled LangGraph app.
    """

    def __init__(
        self,
        *,
        v3_runtime: ResearchGraphRuntime,
        legacy_graph: Any,
        max_research_turns: int = 50,
    ) -> None:
        self._runtime = v3_runtime
        self._legacy = legacy_graph
        self._max_research_turns = max_research_turns
        self._last_v3_result: ResearchLoopResult | None = None

    @property
    def v3_runtime(self) -> ResearchGraphRuntime:
        return self._runtime

    @property
    def last_v3_result(self) -> ResearchLoopResult | None:
        """Most recent V3 ``ResearchLoopResult`` (for inspection/tests)."""

        return self._last_v3_result

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
        """

        # 1. Run the V3 research phase.
        v3_decisions: list[ResearchDecisionV1] = []
        v3_tool_call_refs: list[str] = []
        v3_artifact_paths: dict[str, str] = {}
        try:
            v3_result = run_v3_research_phase(
                self._runtime, max_turns=self._max_research_turns
            )
            self._last_v3_result = v3_result
            v3_decisions = list(v3_result.decision_trace)
            v3_tool_call_refs = extract_v3_tool_call_trace_refs(v3_decisions)
            # R4 evidence chain: merge per-obligation compiled evidence
            # and serialize it to the output directory so the legacy
            # pipeline can consume the V3 artifacts.
            compiled_evidence = getattr(v3_result.loop_state, "compiled_evidence", {})
            if compiled_evidence:
                packet_set, fact_set, claim_set = merge_compiled_evidence(
                    compiled_evidence,
                    repo_snapshot_id=self._runtime.repo_snapshot.snapshot_id,
                    project_tree_hash=self._runtime.repo_snapshot.project_tree_hash,
                )
                out_root = _extract_out_root(state)
                if out_root is not None:
                    v3_artifact_paths = write_v3_evidence_artifacts(
                        out_root,
                        packet_set=packet_set,
                        fact_set=fact_set,
                        claim_set=claim_set,
                    )
        except Exception as exc:  # noqa: BLE001 — V3 failures must not block legacy
            _logger.warning("v3_research_phase_failed: %s", exc)

        # 1.5 Inject V3 evidence artifacts into the legacy input state so
        # the legacy writer can consume them.  We do NOT overwrite existing
        # artifact paths: if the caller already pointed at a specific
        # evidence file we respect that choice.
        if v3_artifact_paths and isinstance(state, dict):
            existing_artifacts = dict(state.get("artifacts") or {})
            for key, path in v3_artifact_paths.items():
                existing_artifacts.setdefault(key, path)
            state["artifacts"] = existing_artifacts

        # 2. Run the legacy pipeline.
        legacy_payload = self._legacy.invoke(state, *args, config=config, **kwargs)
        if not isinstance(legacy_payload, dict):
            legacy_payload = dict(legacy_payload or {})

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
                payload_artifacts.setdefault(key, path)
            legacy_payload["artifacts"] = payload_artifacts

        return legacy_payload

    def get_state(self, config: dict[str, Any] | None = None) -> Any:
        """Delegate ``get_state`` to the legacy graph (for checkpoint resume)."""

        return self._legacy.get_state(config)

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
) -> V3GraphWrapper:
    """Build a V3 graph wrapper around the legacy pipeline.

    When ``CODE2PAPER_AGENTIC_RESEARCH_V3=1`` is set, the runner uses
    this instead of ``build_code2paper_graph``.  The wrapper runs the
    V3 research subgraph first (with ``GemmaSupervisorBackend``), then
    the legacy pipeline, and merges the V3 decisions into the final
    state.
    """

    legacy_graph = build_code2paper_graph(
        tool_registry,
        decision_provider=decision_provider,
        semantic_verifier=semantic_verifier,
        checkpointer=checkpointer,
    )
    return V3GraphWrapper(
        v3_runtime=v3_runtime,
        legacy_graph=legacy_graph,
        max_research_turns=max_research_turns,
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
