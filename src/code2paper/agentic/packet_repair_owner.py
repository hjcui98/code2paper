"""Owning repository-agent loop for packet/relation repair requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.equation_claims import (
    bind_equations_to_claims,
    compile_equation_claims,
    derive_equation_proposals_from_facts,
)
from code2paper.agentic.obligation_fact_alignment import build_obligation_coverage_v2
from code2paper.agentic.research_graph import (
    ResearchLoopState,
    initial_loop_state,
    run_research_loop,
)
from code2paper.agentic.research_models import (
    PacketRepairRequestV1,
    ResearchAgendaV1,
)
from code2paper.agentic.research_nodes import ResearchGraphRuntime


class PacketRepairOwnerResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["applied", "no_progress", "blocked"]
    obligation_id: str = ""
    request_claim_ids: tuple[str, ...] = ()
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    decision_trace: tuple[dict[str, Any], ...] = ()
    tool_call_trace_refs: tuple[str, ...] = ()
    reason: str = ""


class ScopedPacketRepairOwner:
    """Run only the obligation that owns the rejected packet binding."""

    def __init__(self, runtime: ResearchGraphRuntime, *, max_turns: int = 6) -> None:
        self.runtime = runtime
        self.max_turns = max(1, int(max_turns))
        self.latest_loop_state: ResearchLoopState | None = None

    def bind_loop_state(self, loop_state: ResearchLoopState) -> None:
        self.latest_loop_state = loop_state

    def __call__(
        self,
        state: AgenticRunState,
        requests: tuple[PacketRepairRequestV1, ...],
    ) -> PacketRepairOwnerResultV1:
        loop = self.latest_loop_state
        if loop is None:
            return self._blocked(requests, "research_loop_state_unavailable")
        obligation_id = self._resolve_obligation(loop, requests)
        if not obligation_id:
            return self._blocked(requests, "packet_repair_obligation_binding_missing")
        source_item = next(
            (item for item in self.runtime.agenda.items if item.obligation_id == obligation_id),
            None,
        )
        if source_item is None:
            return self._blocked(requests, "packet_repair_obligation_not_in_agenda")

        missing = tuple(
            dict.fromkeys(
                request.missing_relation_type
                for request in requests
                if request.missing_relation_type
            )
        )
        repair_item = source_item.model_copy(update={
            "status": "pending",
            "supported_claim_ids": [],
            "gap_requirements": [],
            "missing_information": list(dict.fromkeys([*source_item.missing_information, *missing])),
            "no_progress_counter": 0,
        })
        repair_agenda = ResearchAgendaV1(
            run_id=f"{self.runtime.run_id}:packet-repair",
            repo_snapshot_id=self.runtime.repo_snapshot.snapshot_id,
            project_tree_hash=self.runtime.repo_snapshot.project_tree_hash,
            intent_graph_digest=self.runtime.agenda.intent_graph_digest,
            items=[repair_item],
        )
        scoped_runtime = self.runtime.model_copy(update={
            "run_id": repair_agenda.run_id,
            "agenda": repair_agenda,
        })
        scoped_loop = initial_loop_state(scoped_runtime)
        scoped_loop.behavior_graph = loop.behavior_graph.model_copy(deep=True)
        result = run_research_loop(
            scoped_runtime,
            max_turns=self.max_turns,
            loop_state=scoped_loop,
        )
        candidate = result.loop_state.compiled_evidence.get(obligation_id)
        incumbent = loop.compiled_evidence.get(obligation_id)
        if candidate is None:
            return PacketRepairOwnerResultV1(
                status="no_progress",
                obligation_id=obligation_id,
                request_claim_ids=tuple(request.claim_id for request in requests),
                decision_trace=tuple(item.model_dump(mode="json") for item in result.decision_trace),
                tool_call_trace_refs=tuple(_tool_refs(result.decision_trace)),
                reason=result.termination_reason or "repair_produced_no_compiled_evidence",
            )
        candidate_identity = (
            candidate.packet_set.content_digest,
            candidate.fact_set.content_digest,
            candidate.claim_set.content_digest,
        )
        incumbent_identity = (
            incumbent.packet_set.content_digest,
            incumbent.fact_set.content_digest,
            incumbent.claim_set.content_digest,
        ) if incumbent is not None else ()
        if candidate_identity == incumbent_identity:
            return PacketRepairOwnerResultV1(
                status="no_progress",
                obligation_id=obligation_id,
                request_claim_ids=tuple(request.claim_id for request in requests),
                decision_trace=tuple(item.model_dump(mode="json") for item in result.decision_trace),
                tool_call_trace_refs=tuple(_tool_refs(result.decision_trace)),
                reason="scoped_research_did_not_change_packet_fact_claim_boundary",
            )

        # Commit only a positively compiled candidate.  A failed repair never
        # replaces incumbent supported evidence with a gap or partial object.
        loop.behavior_graph = result.loop_state.behavior_graph
        loop.compiled_evidence[obligation_id] = candidate
        paths = self._persist_canonical_artifacts(state, loop)
        return PacketRepairOwnerResultV1(
            status="applied",
            obligation_id=obligation_id,
            request_claim_ids=tuple(request.claim_id for request in requests),
            artifact_paths=paths,
            decision_trace=tuple(item.model_dump(mode="json") for item in result.decision_trace),
            tool_call_trace_refs=tuple(_tool_refs(result.decision_trace)),
        )

    def _resolve_obligation(
        self,
        loop: ResearchLoopState,
        requests: tuple[PacketRepairRequestV1, ...],
    ) -> str:
        packet_ids = {request.packet_id for request in requests if request.packet_id}
        source_claim_ids = {
            claim_id for request in requests for claim_id in request.source_claim_ids
        }
        for obligation_id, compiled in loop.compiled_evidence.items():
            if packet_ids.intersection(packet.packet_id for packet in compiled.packet_set.packets):
                return obligation_id
            if source_claim_ids.intersection(claim.claim_id for claim in compiled.claim_set.claims):
                return obligation_id
        return ""

    def _persist_canonical_artifacts(
        self,
        state: AgenticRunState,
        loop: ResearchLoopState,
    ) -> dict[str, str]:
        from code2paper.agentic.obligation_fact_alignment import bind_claims_to_obligations
        from code2paper.agentic.v3_runtime import (
            merge_compiled_evidence,
            write_d25_method_research_artifacts,
            write_v3_evidence_artifacts,
        )

        packet_set, fact_set, claim_set = merge_compiled_evidence(
            loop.compiled_evidence,
            repo_snapshot_id=self.runtime.repo_snapshot.snapshot_id,
            project_tree_hash=self.runtime.repo_snapshot.project_tree_hash,
        )
        intent_graph = self.runtime.intent_graph
        if intent_graph is not None:
            claim_set = bind_claims_to_obligations(
                intent_graph,
                fact_set=fact_set,
                claim_set=claim_set,
            )
        equations, _ = compile_equation_claims(
            derive_equation_proposals_from_facts(fact_set),
            fact_set,
            repo_snapshot_id=fact_set.repo_snapshot_id,
            project_tree_hash=fact_set.project_tree_hash,
        )
        equations = bind_equations_to_claims(equations, claim_set)
        paths = write_v3_evidence_artifacts(
            state.out_root,
            packet_set=packet_set,
            fact_set=fact_set,
            claim_set=claim_set,
            equation_set=equations,
        )
        if intent_graph is not None:
            coverage = build_obligation_coverage_v2(
                intent_graph,
                fact_set=fact_set,
                claim_set=claim_set,
                explicit_gaps=claim_set.explicit_code_gaps,
            )
            coverage_path = Path(state.out_root) / "artifacts" / "obligation_coverage_v2.json"
            coverage_path.write_text(coverage.model_dump_json(indent=2) + "\n", encoding="utf-8")
            paths["obligation_coverage_v2"] = str(coverage_path)
            paths.update(write_d25_method_research_artifacts(
                state.out_root,
                intent_graph=intent_graph,
                coverage_report=coverage,
                fact_set=fact_set,
                claim_set=claim_set,
                equation_set=equations,
            ))
        return paths

    @staticmethod
    def _blocked(
        requests: tuple[PacketRepairRequestV1, ...],
        reason: str,
    ) -> PacketRepairOwnerResultV1:
        return PacketRepairOwnerResultV1(
            status="blocked",
            request_claim_ids=tuple(request.claim_id for request in requests),
            reason=reason,
        )


def _tool_refs(decisions) -> list[str]:
    return list(dict.fromkeys(
        call.tool_call_id
        for decision in decisions
        for call in decision.selected_tool_calls
    ))


__all__ = ["PacketRepairOwnerResultV1", "ScopedPacketRepairOwner"]
