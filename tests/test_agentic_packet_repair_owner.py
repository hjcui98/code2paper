from __future__ import annotations

from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.packet_repair_owner import ScopedPacketRepairOwner
from code2paper.agentic.research_graph import run_research_loop
from code2paper.agentic.research_models import (
    GlobalSafetyBudgetV1,
    PacketRepairRequestV1,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    TypedBehaviorTargetV1,
)
from code2paper.agentic.research_nodes import ResearchGraphRuntime
from code2paper.agentic.repo_snapshot import build_repo_snapshot


def test_packet_repair_runs_scoped_repository_owner_and_preserves_incumbent(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "train.py").write_text(
        "def train():\n    print('train')\n",
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(repo)
    obligation = ResearchAgendaItemV1(
        obligation_id="obl-main",
        priority="must_cover",
        status="in_progress",
        typed_behavior_targets=[TypedBehaviorTargetV1(
            target_id="target-main",
            desired_predicates=("WRITE",),
            search_terms=("train",),
        )],
    )
    agenda = ResearchAgendaV1(
        run_id="run-packet-owner",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[obligation],
    )
    runtime = ResearchGraphRuntime(
        run_id=agenda.run_id,
        repo_snapshot=snapshot,
        agenda=agenda,
        global_safety_budget=GlobalSafetyBudgetV1(),
        artifact_root=tmp_path / "artifacts",
    )
    initial = run_research_loop(runtime, max_turns=8)
    compiled = initial.loop_state.compiled_evidence["obl-main"]
    incumbent_digest = compiled.claim_set.content_digest
    claim_id = compiled.claim_set.claims[0].claim_id
    packet_id = compiled.packet_set.packets[0].packet_id
    owner = ScopedPacketRepairOwner(runtime, max_turns=6)
    owner.bind_loop_state(initial.loop_state)
    state = AgenticRunState(project_root=repo, out_root=tmp_path / "out")

    result = owner(state, (
        PacketRepairRequestV1(
            claim_id="final-claim-1",
            source_claim_ids=(claim_id,),
            packet_id=packet_id,
            failure_type="wrong_span_role",
            missing_relation_type="relation_evidence:CALLS",
            requested_scope="packet_relation",
            attempt=1,
        ),
    ))

    assert result.status in {"applied", "no_progress"}
    assert result.obligation_id == "obl-main"
    assert result.decision_trace
    assert result.tool_call_trace_refs
    assert "obl-main" in initial.loop_state.compiled_evidence
    assert (
        initial.loop_state.compiled_evidence["obl-main"].claim_set.content_digest
        == incumbent_digest
        or result.status == "applied"
    )


def test_packet_repair_without_exact_claim_or_packet_binding_fails_closed(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("x = 1\n", encoding="utf-8")
    snapshot = build_repo_snapshot(repo)
    agenda = ResearchAgendaV1(
        run_id="run-unbound",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[],
    )
    runtime = ResearchGraphRuntime(
        run_id=agenda.run_id,
        repo_snapshot=snapshot,
        agenda=agenda,
        artifact_root=tmp_path / "artifacts",
    )
    owner = ScopedPacketRepairOwner(runtime)
    from code2paper.agentic.research_graph import initial_loop_state

    owner.bind_loop_state(initial_loop_state(runtime))
    result = owner(
        AgenticRunState(project_root=repo, out_root=tmp_path / "out"),
        (PacketRepairRequestV1(
            claim_id="unknown-final-claim",
            source_claim_ids=("unknown-source-claim",),
            failure_type="wrong_span_role",
            requested_scope="packet_relation",
        ),),
    )

    assert result.status == "blocked"
    assert result.reason == "packet_repair_obligation_binding_missing"
