"""R4 wiring tests for ``compile_candidate_node``.

Verifies that the node (replacing the R3 stub) correctly:

1. Selects behavior nodes for an obligation using heterogeneous candidate
   identifier formats (``path:name``, bare path, ``sym:<digest>``).
2. Builds an ``EvidencePacketProposalV1`` and produces a validated
   ``EvidencePacketV3`` via ``compile_evidence_packet_proposal``.
3. Produces a ``CodeFactSetV1`` with at least one ``supported`` fact via
   ``compile_facts_from_behavior_graph``.
4. Produces an ``AtomicClaimSetV3`` with at least one authorized claim via
   ``compile_atomic_claims``.
5. Marks the active obligation as ``supported`` with
   ``supported_claim_ids`` populated.
6. Returns a private ``_compiled_evidence`` channel carrying the
   packet_set / fact_set / claim_set.
7. Delegates to ``gap_finalizer_node`` when no behavior nodes match the
   obligation's candidates.
8. Short-circuits when the obligation is already terminal.
9. Returns ``blocked`` when there is no active obligation or the
   obligation is not in the agenda.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from code2paper.agentic.behavior_graph import (
    BehaviorNodeV1,
    BehaviorRelationV1,
    CodeBehaviorGraphV1,
    make_symbol_id,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    CodeFactSetV1,
    EvidencePacketSetV3,
)
from code2paper.agentic.research_graph import (
    CompiledEvidence,
    ResearchLoopDriver,
    ResearchLoopState,
    initial_loop_state,
    run_research_loop,
)
from code2paper.agentic.research_models import (
    GapRequirementV1,
    GlobalSafetyBudgetV1,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    TypedBehaviorTargetV1,
)
from code2paper.agentic.research_nodes import (
    BudgetPolicyV1,
    InformationGainTracker,
    ResearchGraphRuntime,
    _alignment_semantic_context,
    _build_evidence_packet_proposal,
    _rank_relevant_behavior_nodes,
    compile_candidate_node,
)
from code2paper.agentic.repo_snapshot import RepoSnapshot, build_repo_snapshot


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


_REPO_SNAPSHOT_ID = "repo:test-snapshot"
_PROJECT_TREE_HASH = "sha256:tree"


def test_unread_candidate_symbol_name_is_not_semantic_evidence() -> None:
    obligation = _obligation(
        "obl-candidate-hint",
        candidate_symbol_ids=(
            "symbol:model.py:LLM.infer:30",
            "symbol:index.py:build_index:4",
        ),
    )
    selected = _node(
        node_id="node:index-call",
        symbol_id="sym:index.build_index",
        predicate="CALL",
        operands=("store.write",),
        source_span_id="span:index.py:4:8",
    )

    context = _alignment_semantic_context(obligation, [selected])

    assert "LLM.infer" not in context
    assert "model.py" not in context
    assert "store.write" in context


def test_packet_proposal_carries_unselected_configuration_relation_endpoint() -> None:
    operation = _node(
        node_id="node:operation",
        symbol_id="sym:model.forward",
        predicate="FILTER",
        operands=("score < self.threshold",),
        source_span_id="span:model.py:20:21",
    )
    relation = _relation(
        relation_id="rel:configured",
        kind="CONFIGURED_BY",
        source_node_id=operation.node_id,
        target_node_id="node:config-default",
        source_span_id=operation.source_span_id,
        target_span_id="span:model.py:5:5",
    )

    proposal = _build_evidence_packet_proposal(
        obligation_id="obl-config",
        selected_nodes=[operation],
        selected_relations=[relation],
    )

    assert proposal is not None
    assert proposal.behavior_node_ids == [
        "node:operation",
        "node:config-default",
    ]
    assert proposal.relation_span_ids == ["span:model.py:5:5"]


_TRAIN_PY = """\
\"\"\"Training entrypoint.\"\"\"

import torch

from model import GaussianModel


def train(model: GaussianModel, epochs: int = 10) -> None:
    optimizer = torch.optim.Adam(model.parameters(), lr=1.0e-4)
    for epoch in range(epochs):
        loss = model.forward()
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()


def main() -> None:
    model = GaussianModel()
    train(model)


if __name__ == "__main__":
    main()
"""


_MODEL_PY = """\
\"\"\"Model definition.\"\"\"

import torch
import torch.nn as nn


class GaussianModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.gaussians = nn.Parameter(torch.zeros(64, 3))

    def forward(self) -> torch.Tensor:
        return self.gaussians.sum()
"""


@pytest.fixture()
def ml_repo(tmp_path: Path) -> Path:
    root = tmp_path / "ml_repo"
    root.mkdir(parents=True)
    (root / "train.py").write_text(_TRAIN_PY, encoding="utf-8")
    (root / "model.py").write_text(_MODEL_PY, encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "model.py").write_text("value = 1\n", encoding="utf-8")
    (root / "src" / "data.py").write_text("value = 2\n", encoding="utf-8")
    return root


@pytest.fixture()
def snapshot(ml_repo: Path) -> RepoSnapshot:
    return build_repo_snapshot(ml_repo)


def _node(
    *,
    node_id: str,
    symbol_id: str = "sym:train.train",
    predicate: str = "READ",
    operands: tuple[str, ...] = ("x",),
    result: str = "",
    guard: str = "",
    source_span_id: str = "span:train.py:1:10",
    source_authority: str = "executable_hard",
    operation_id: str = "op-1",
) -> BehaviorNodeV1:
    return BehaviorNodeV1(
        node_id=node_id,
        symbol_id=symbol_id,
        operation_id=operation_id,
        predicate=predicate,
        operands=operands,
        result=result,
        guard=guard,
        source_span_id=source_span_id,
        source_authority=source_authority,  # type: ignore[arg-type]
    )


def _relation(
    *,
    relation_id: str,
    kind: str = "NEXT_CONTROL",
    source_node_id: str = "node:a",
    target_node_id: str = "node:b",
    source_symbol_id: str = "sym:train.train",
    target_symbol_id: str = "",
    source_span_id: str = "span:train.py:1:10",
    target_span_id: str = "",
    guard: str = "",
) -> BehaviorRelationV1:
    return BehaviorRelationV1(
        relation_id=relation_id,
        kind=kind,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        source_symbol_id=source_symbol_id,
        target_symbol_id=target_symbol_id,
        source_span_id=source_span_id,
        target_span_id=target_span_id,
        guard=guard,
    )


def test_strong_semantic_anchor_excludes_unrelated_same_predicate_symbol() -> None:
    mamba_symbol = make_symbol_id("models.py", "MambaEncoder.forward", 1)
    other_symbol = make_symbol_id("models.py", "OtherTemporalModel.forward", 20)
    nodes = [
        _node(
            node_id="node:mamba",
            symbol_id=mamba_symbol,
            predicate="COMPUTE",
            operands=("state space update",),
        ),
        _node(
            node_id="node:other",
            symbol_id=other_symbol,
            predicate="COMPUTE",
            operands=("temporal attention output",),
        ),
    ]
    obligation = ResearchAgendaItemV1(
        obligation_id="obl-state-space",
        priority="must_cover",
        author_text="Apply a continuous state space update.",
        typed_behavior_targets=[TypedBehaviorTargetV1(
            target_id="target-state-space",
            role="temporal",
            desired_predicates=("COMPUTE",),
            transformations=("state space",),
        )],
        candidate_symbol_ids=[
            "symbol:models.py:MambaEncoder.forward:1",
            "symbol:models.py:OtherTemporalModel.forward:20",
        ],
    )

    selected = _rank_relevant_behavior_nodes(nodes, obligation)

    assert [node.node_id for node in selected] == ["node:mamba"]


def test_relevant_symbol_adds_bounded_method_completeness_operations() -> None:
    symbol = make_symbol_id("model.py", "NamedEncoder.forward", 1)
    other_symbol = make_symbol_id("model.py", "Baseline.forward", 50)
    nodes = [
        _node(node_id="node:compute", symbol_id=symbol, predicate="COMPUTE"),
        _node(
            node_id="node:branch",
            symbol_id=symbol,
            predicate="BRANCH",
            guard="special_mode",
        ),
        _node(
            node_id="node:irrelevant-branch",
            symbol_id=symbol,
            predicate="BRANCH",
            guard="cache_available",
        ),
        _node(node_id="node:norm", symbol_id=symbol, predicate="NORMALIZE"),
        _node(node_id="node:topk", symbol_id=symbol, predicate="TOPK"),
        _node(node_id="node:other-topk", symbol_id=other_symbol, predicate="TOPK"),
    ]
    obligation = ResearchAgendaItemV1(
        obligation_id="obl-completeness",
        priority="must_cover",
        author_text="Compute an encoded representation in special mode.",
        typed_behavior_targets=[TypedBehaviorTargetV1(
            target_id="target-compute",
            role="feature",
            desired_predicates=("COMPUTE",),
        )],
    )

    selected = _rank_relevant_behavior_nodes(nodes, obligation)
    selected_ids = {node.node_id for node in selected}

    assert {"node:compute", "node:branch", "node:norm", "node:topk"} <= selected_ids
    assert "node:irrelevant-branch" not in selected_ids
    assert "node:other-topk" not in selected_ids


def test_disjoint_typed_targets_select_their_own_semantic_witnesses() -> None:
    index_symbol = make_symbol_id("system.py", "Pipeline.index", 1)
    infer_symbol = make_symbol_id("system.py", "LLM.infer", 20)
    answer_helper_symbol = make_symbol_id("system.py", "normalize_answer", 40)
    nodes = [
        _node(
            node_id="node:index-write",
            symbol_id=index_symbol,
            predicate="WRITE",
            operands=("graph_store",),
        ),
        _node(
            node_id="node:infer-call",
            symbol_id=infer_symbol,
            predicate="CALL",
            operands=("client.infer",),
        ),
        _node(
            node_id="node:answer-helper",
            symbol_id=answer_helper_symbol,
            predicate="CALL",
            operands=("text.lower",),
        ),
    ]
    obligation = ResearchAgendaItemV1(
        obligation_id="obl-lifecycle",
        priority="should_cover",
        author_text="Index a graph and invoke generation.",
        typed_behavior_targets=[
            TypedBehaviorTargetV1(
                target_id="target-index",
                role="graph_builder",
                desired_predicates=("CALL", "WRITE"),
                predicate_groups=(("CALL", "WRITE"),),
                transformations=("indexing",),
            ),
            TypedBehaviorTargetV1(
                target_id="target-generation",
                role="generation",
                desired_predicates=("CALL", "RETURN"),
                predicate_groups=(("CALL", "RETURN"),),
                transformations=("generation",),
            ),
        ],
        candidate_symbol_ids=[
            "symbol:system.py:Pipeline.index:1",
            "symbol:system.py:LLM.infer:20",
            "symbol:system.py:normalize_answer:40",
        ],
    )

    selected = _rank_relevant_behavior_nodes(nodes, obligation)
    selected_ids = {node.node_id for node in selected}

    assert {"node:index-write", "node:infer-call"} <= selected_ids
    assert "node:answer-helper" not in selected_ids


def _graph(
    nodes: list[BehaviorNodeV1] | None = None,
    relations: list[BehaviorRelationV1] | None = None,
    *,
    repo_snapshot_id: str = _REPO_SNAPSHOT_ID,
    project_tree_hash: str = _PROJECT_TREE_HASH,
) -> CodeBehaviorGraphV1:
    return CodeBehaviorGraphV1(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        language="python",
        nodes=nodes or [],
        relations=relations or [],
        unresolved_relations=[],
    ).with_digest()


def _obligation(
    obligation_id: str,
    *,
    candidate_symbol_ids: tuple[str, ...] = (),
    missing_information: tuple[str, ...] = (),
    status: str = "in_progress",
    candidate_behavior_node_ids: tuple[str, ...] = (),
    author_text: str = "",
    typed_behavior_targets: tuple[TypedBehaviorTargetV1, ...] | None = None,
) -> ResearchAgendaItemV1:
    # Terminal states require their accompanying fields per the
    # ``ResearchAgendaItemV1._terminal_status_consistency`` validator.
    if typed_behavior_targets is None:
        typed_behavior_targets = (
            TypedBehaviorTargetV1(
                target_id=f"target-{obligation_id}",
                desired_predicates=("READ",),
            ),
        )
    kwargs: dict[str, Any] = {
        "obligation_id": obligation_id,
        "priority": "must_cover",
        "status": status,  # type: ignore[arg-type]
        "candidate_symbol_ids": list(candidate_symbol_ids),
        "candidate_behavior_node_ids": list(candidate_behavior_node_ids),
        "missing_information": list(missing_information),
        "author_text": author_text,
        "typed_behavior_targets": list(typed_behavior_targets),
    }
    if status == "supported":
        kwargs["supported_claim_ids"] = ["claim-fake-supported"]
    elif status == "explicit_gap":
        kwargs["gap_requirements"] = [
            GapRequirementV1(
                requirement_id=f"req-{obligation_id}",
                description="test gap requirement",
                terminal="explicit_gap",
            )
        ]
    return ResearchAgendaItemV1(**kwargs)


def _agenda(
    run_id: str,
    snapshot: RepoSnapshot,
    *items: ResearchAgendaItemV1,
) -> ResearchAgendaV1:
    return ResearchAgendaV1(
        run_id=run_id,
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=list(items),
    )


def _runtime(
    snapshot: RepoSnapshot,
    agenda: ResearchAgendaV1,
    *,
    run_id: str = "run-compile-test",
) -> ResearchGraphRuntime:
    return ResearchGraphRuntime(
        run_id=run_id,
        repo_snapshot=snapshot,
        agenda=agenda,
        budget_policy=BudgetPolicyV1(),
        global_safety_budget=GlobalSafetyBudgetV1(),
    )


def _state(active_obligation_id: str = "") -> dict[str, Any]:
    return {
        "run_id": "run-compile-test",
        "repo_snapshot_id": _REPO_SNAPSHOT_ID,
        "project_tree_hash": _PROJECT_TREE_HASH,
        "active_obligation_id": active_obligation_id,
        "status": "researching",
    }


# ---------------------------------------------------------------------------
# 1. Successful compilation: produces _compiled_evidence
# ---------------------------------------------------------------------------


class TestCompileCandidateSuccess:
    """``compile_candidate_node`` produces authorized claims for a
    well-formed obligation with matching behavior nodes."""

    def test_returns_compiled_evidence_channel(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-compile-1",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-1", snapshot, obl))
        # Build a behavior graph with nodes whose source_span_id matches
        # the path component of the candidate ("train.py").
        node_a = _node(
            node_id="node:read-1",
            symbol_id="sym:train.train",
            predicate="READ",
            operands=("optimizer",),
            result="opt",
            source_span_id="span:train.py:9:10",
        )
        node_b = _node(
            node_id="node:call-1",
            symbol_id="sym:train.train",
            predicate="CALL",
            operands=("model.forward",),
            result="loss",
            source_span_id="span:train.py:11:12",
        )
        rel = _relation(
            relation_id="rel:next-1",
            kind="NEXT_CONTROL",
            source_node_id="node:read-1",
            target_node_id="node:call-1",
            source_span_id="span:train.py:9:10",
            target_span_id="span:train.py:11:12",
        )
        bg = _graph(nodes=[node_a, node_b], relations=[rel])
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-compile-1"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-compile-1",
            gain_tracker=gain,
        )

        # The private _compiled_evidence channel must be present.
        assert "_compiled_evidence" in update
        compiled = update["_compiled_evidence"]
        assert compiled["obligation_id"] == "obl-compile-1"
        assert isinstance(compiled["packet_set"], EvidencePacketSetV3)
        assert isinstance(compiled["fact_set"], CodeFactSetV1)
        assert isinstance(compiled["claim_set"], AtomicClaimSetV3)
        # The compatibility node must replay through all six D1 tools rather
        # than calling the generic compilers through a second implementation.
        assert len(update["tool_call_trace_refs"]) == 6
        artifact_root = runtime.tool_context(
            behavior_graph=bg
        ).artifact_root / "research_tool_artifacts"
        for artifact_kind in (
            "packet_proposals",
            "packet_validation_reports",
            "validated_packets",
            "fact_sets",
            "fact_validation_reports",
            "claim_proposal_sets",
            "claim_authorization_reports",
            "authorized_claim_sets",
        ):
            assert list((artifact_root / artifact_kind).glob("*.json")), artifact_kind

    def test_obligation_marked_supported_with_claim_ids(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-compile-2",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-2", snapshot, obl))
        node = _node(
            node_id="node:read-2",
            symbol_id="sym:train.train",
            predicate="READ",
            operands=("optimizer",),
            result="opt",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()

        compile_candidate_node(
            _state("obl-compile-2"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-compile-2",
            gain_tracker=gain,
        )

        # The obligation must be mutated in place to supported.
        assert obl.status == "supported"
        assert len(obl.supported_claim_ids) >= 1

    def test_compiled_evidence_carries_at_least_one_packet(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-compile-3",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-3", snapshot, obl))
        node = _node(
            node_id="node:read-3",
            symbol_id="sym:train.train",
            predicate="READ",
            operands=("optimizer",),
            result="opt",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-compile-3"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-compile-3",
            gain_tracker=gain,
        )
        compiled = update["_compiled_evidence"]
        assert len(compiled["packet_set"].packets) >= 1
        # The packet must carry at least one anchor span.
        packet = compiled["packet_set"].packets[0]
        assert len(packet.anchor_span_ids) >= 1

    def test_compiled_evidence_carries_supported_facts(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-compile-4",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-4", snapshot, obl))
        node = _node(
            node_id="node:read-4",
            symbol_id="sym:train.train",
            predicate="READ",
            operands=("optimizer",),
            result="opt",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-compile-4"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-compile-4",
            gain_tracker=gain,
        )
        compiled = update["_compiled_evidence"]
        supported_facts = [
            f for f in compiled["fact_set"].facts
            if f.validation_status == "supported"
        ]
        assert len(supported_facts) >= 1

    def test_compiled_evidence_carries_authorized_claims(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-compile-5",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-5", snapshot, obl))
        node = _node(
            node_id="node:read-5",
            symbol_id="sym:train.train",
            predicate="READ",
            operands=("optimizer",),
            result="opt",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-compile-5"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-compile-5",
            gain_tracker=gain,
        )
        compiled = update["_compiled_evidence"]
        assert len(compiled["claim_set"].claims) >= 1
        # Every authorized claim must reference at least one fact.
        for claim in compiled["claim_set"].claims:
            assert len(claim.fact_ids) >= 1

    def test_state_refs_updated_with_digests(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-compile-6",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-6", snapshot, obl))
        node = _node(
            node_id="node:read-6",
            symbol_id="sym:train.train",
            predicate="READ",
            operands=("optimizer",),
            result="opt",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-compile-6"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-compile-6",
            gain_tracker=gain,
        )
        # The state update must carry the digest refs.
        assert update["evidence_packet_set_ref"]
        assert update["code_fact_set_ref"]
        assert update["atomic_claim_set_ref"]
        # The digest refs must match the compiled set digests.
        compiled = update["_compiled_evidence"]
        assert update["evidence_packet_set_ref"] == compiled["packet_set"].content_digest
        assert update["code_fact_set_ref"] == compiled["fact_set"].content_digest
        assert update["atomic_claim_set_ref"] == compiled["claim_set"].content_digest

    def test_semantic_relevance_bounds_facts_and_drops_unrelated_nodes(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-semantic-slice",
            candidate_symbol_ids=("train.py",),
            author_text="Normalize query embeddings before retrieval.",
            typed_behavior_targets=(TypedBehaviorTargetV1(
                target_id="target-normalize",
                desired_predicates=("NORMALIZE",),
                search_terms=("query embeddings",),
            ),),
        )
        runtime = _runtime(snapshot, _agenda("run-semantic", snapshot, obl))
        relevant = _node(
            node_id="node:normalize-query",
            predicate="NORMALIZE",
            operands=("query_embeddings",),
            result="normalized_queries",
            source_span_id="span:train.py:9:10",
        )
        unrelated = [
            _node(
                node_id=f"node:unrelated-{index}",
                predicate="LOAD",
                operands=(f"checkpoint_{index}",),
                result=f"weights_{index}",
                source_span_id=f"span:train.py:{11 + index}:{11 + index}",
            )
            for index in range(6)
        ]
        update = compile_candidate_node(
            _state("obl-semantic-slice"),
            runtime=runtime,
            behavior_graph=_graph(nodes=[relevant, *unrelated]),
            active_obligation_id="obl-semantic-slice",
            gain_tracker=InformationGainTracker(),
        )

        compiled = update["_compiled_evidence"]
        assert len(compiled["fact_set"].facts) <= 3
        assert [fact.object for fact in compiled["fact_set"].facts] == [[
            "query_embeddings", "result=normalized_queries",
        ]]
        assert len(compiled["claim_set"].claims) <= 3

    def test_semantic_mismatch_fails_closed_instead_of_authorizing_claim(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-semantic-miss",
            candidate_symbol_ids=("train.py",),
            author_text="Normalize query embeddings before retrieval.",
            typed_behavior_targets=(TypedBehaviorTargetV1(
                target_id="target-normalize-miss",
                desired_predicates=("NORMALIZE",),
                search_terms=("query embeddings",),
            ),),
        )
        runtime = _runtime(snapshot, _agenda("run-semantic-miss", snapshot, obl))
        update = compile_candidate_node(
            _state("obl-semantic-miss"),
            runtime=runtime,
            behavior_graph=_graph(nodes=[_node(
                node_id="node:load-checkpoint",
                predicate="LOAD",
                operands=("checkpoint",),
                result="weights",
            )]),
            active_obligation_id="obl-semantic-miss",
            gain_tracker=InformationGainTracker(),
        )

        assert "_compiled_evidence" not in update
        assert obl.status != "supported"

    def test_typed_symbol_ref_binds_exact_symbol_not_entire_file(
        self, snapshot: RepoSnapshot
    ) -> None:
        train_symbol = make_symbol_id("train.py", "train", 7)
        eval_symbol = make_symbol_id("train.py", "evaluate", 30)
        obl = _obligation(
            "obl-exact-symbol",
            candidate_symbol_ids=("train.py", "symbol:train.py:train:7"),
        )
        runtime = _runtime(snapshot, _agenda("run-exact-symbol", snapshot, obl))
        train_node = _node(
            node_id="node:train-symbol",
            symbol_id=train_symbol,
            result="training_loss",
        )
        eval_node = _node(
            node_id="node:eval-symbol",
            symbol_id=eval_symbol,
            result="evaluation_metric",
        )
        update = compile_candidate_node(
            _state("obl-exact-symbol"),
            runtime=runtime,
            behavior_graph=_graph(nodes=[train_node, eval_node]),
            active_obligation_id="obl-exact-symbol",
            gain_tracker=InformationGainTracker(),
        )

        facts = update["_compiled_evidence"]["fact_set"].facts
        assert {fact.scope for fact in facts} == {train_symbol}


# ---------------------------------------------------------------------------
# 2. Heterogeneous candidate identifier matching
# ---------------------------------------------------------------------------


class TestHeterogeneousCandidateMatching:
    """``_select_behavior_nodes_for_obligation`` handles multiple candidate
    formats: ``path:name``, bare path, ``sym:<digest>``, ``node:<digest>``."""

    def test_path_name_format_matches_span_prefix(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-path-name",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-pn", snapshot, obl))
        node = _node(
            node_id="node:pn",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()
        update = compile_candidate_node(
            _state("obl-path-name"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-path-name",
            gain_tracker=gain,
        )
        assert "_compiled_evidence" in update

    def test_bare_path_format_matches_span_prefix(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-bare-path",
            candidate_symbol_ids=("train.py",),
        )
        runtime = _runtime(snapshot, _agenda("run-bp", snapshot, obl))
        node = _node(
            node_id="node:bp",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()
        update = compile_candidate_node(
            _state("obl-bare-path"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-bare-path",
            gain_tracker=gain,
        )
        assert "_compiled_evidence" in update

    def test_symbol_id_format_matches_directly(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-sym-id",
            candidate_symbol_ids=("sym:train.train",),
        )
        runtime = _runtime(snapshot, _agenda("run-sid", snapshot, obl))
        node = _node(
            node_id="node:sid",
            symbol_id="sym:train.train",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()
        update = compile_candidate_node(
            _state("obl-sym-id"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-sym-id",
            gain_tracker=gain,
        )
        assert "_compiled_evidence" in update

    def test_node_id_format_matches_directly(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-node-id",
            candidate_behavior_node_ids=("node:nid",),
        )
        runtime = _runtime(snapshot, _agenda("run-nid", snapshot, obl))
        node = _node(
            node_id="node:nid",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()
        update = compile_candidate_node(
            _state("obl-node-id"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-node-id",
            gain_tracker=gain,
        )
        assert "_compiled_evidence" in update

    def test_directory_prefix_matches_multiple_files(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-dir",
            candidate_symbol_ids=("src/",),
        )
        runtime = _runtime(snapshot, _agenda("run-dir", snapshot, obl))
        node_a = _node(
            node_id="node:dir-a",
            source_span_id="span:src/model.py:1:10",
        )
        node_b = _node(
            node_id="node:dir-b",
            source_span_id="span:src/data.py:1:10",
        )
        bg = _graph(nodes=[node_a, node_b])
        gain = InformationGainTracker()
        update = compile_candidate_node(
            _state("obl-dir"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-dir",
            gain_tracker=gain,
        )
        assert "_compiled_evidence" in update
        compiled = update["_compiled_evidence"]
        # Both nodes must be selected (directory prefix matches both).
        # The compiled packet carries spans derived from the selected
        # nodes' source_span_ids.
        packet = compiled["packet_set"].packets[0]
        span_ids = {span.span_id for span in packet.spans}
        assert "span:src/model.py:1:10" in span_ids
        assert "span:src/data.py:1:10" in span_ids


# ---------------------------------------------------------------------------
# 3. Delegation to gap_finalizer_node
# ---------------------------------------------------------------------------


class TestGapFinalizerDelegation:
    """When no behavior nodes match, the node delegates to
    ``gap_finalizer_node`` instead of producing compiled evidence."""

    def test_no_matching_nodes_routes_to_gap_finalizer(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-no-match",
            candidate_symbol_ids=("nonexistent.py:foo",),
        )
        runtime = _runtime(snapshot, _agenda("run-nm", snapshot, obl))
        # Behavior graph has nodes for train.py, not nonexistent.py.
        node = _node(
            node_id="node:nm",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-no-match"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-no-match",
            gain_tracker=gain,
        )
        # No compiled evidence must be returned.
        assert "_compiled_evidence" not in update
        # The gap finalizer returns a _gap_accepted flag (False when the
        # gap threshold is not reached, since gain_tracker is fresh).
        assert update.get("_gap_accepted") is False

    def test_untyped_obligation_cannot_become_supported_by_lexical_match(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-untyped",
            candidate_symbol_ids=("train.py",),
            author_text="Read optimizer configuration.",
            typed_behavior_targets=(),
        )
        runtime = _runtime(snapshot, _agenda("run-untyped", snapshot, obl))
        update = compile_candidate_node(
            _state("obl-untyped"),
            runtime=runtime,
            behavior_graph=_graph(nodes=[_node(
                node_id="node:untyped-read",
                predicate="READ",
                operands=("optimizer",),
                result="optimizer_config",
            )]),
            active_obligation_id="obl-untyped",
            gain_tracker=InformationGainTracker(),
        )

        assert "_compiled_evidence" not in update
        assert obl.status != "supported"

    def test_validated_facts_survive_unresolved_semantic_detail(
        self, snapshot: RepoSnapshot
    ) -> None:
        target = TypedBehaviorTargetV1(
            target_id="target-dimension",
            role="feature",
            desired_predicates=("READ",),
            outputs=("dimension 15",),
        )
        obl = _obligation(
            "obl-partial-facts",
            candidate_symbol_ids=("train.py",),
            typed_behavior_targets=(target,),
        )
        runtime = _runtime(snapshot, _agenda("run-partial", snapshot, obl))
        update = compile_candidate_node(
            _state("obl-partial-facts"),
            runtime=runtime,
            behavior_graph=_graph(nodes=[_node(
                node_id="node:partial-read",
                predicate="READ",
                operands=("optimizer",),
                result="optimizer_config",
                source_span_id="span:train.py:9:10",
            )]),
            active_obligation_id="obl-partial-facts",
            gain_tracker=InformationGainTracker(),
        )

        assert "_compiled_evidence" not in update
        partial = update["_partial_evidence"]
        assert partial["fact_set"].facts
        assert partial["claim_set"].claims
        assert all(
            claim.status == "supported" for claim in partial["claim_set"].claims
        )
        assert obl.status != "supported"

    def test_empty_behavior_graph_routes_to_gap_finalizer(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-empty-bg",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-ebg", snapshot, obl))
        bg = _graph()  # empty
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-empty-bg"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-empty-bg",
            gain_tracker=gain,
        )
        assert "_compiled_evidence" not in update
        assert update.get("_gap_accepted") is False

    def test_packet_validator_failure_returns_retryable_owner_issue(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-weak-anchor",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-weak", snapshot, obl))
        node = _node(
            node_id="node:weak-anchor",
            source_span_id="span:train.py:9:10",
            source_authority="semantic_hint",
        )

        update = compile_candidate_node(
            _state("obl-weak-anchor"),
            runtime=runtime,
            behavior_graph=_graph(nodes=[node]),
            active_obligation_id="obl-weak-anchor",
            gain_tracker=InformationGainTracker(),
        )

        assert "_compiled_evidence" not in update
        assert "_gap_accepted" not in update
        assert update["active_issue_id"].startswith("issue:data-plane:")
        assert any(
            item.startswith("tool_data_plane:validate_evidence_packet:")
            for item in obl.missing_information
        )

    def test_no_anchor_spans_routes_to_gap_finalizer(
        self, snapshot: RepoSnapshot
    ) -> None:
        """Nodes without source_span_id cannot anchor a packet."""
        obl = _obligation(
            "obl-no-anchor",
            candidate_symbol_ids=("sym:train.train",),
        )
        runtime = _runtime(snapshot, _agenda("run-na", snapshot, obl))
        # Node matches by symbol_id but has no source_span_id (the
        # proposal builder returns None when no anchor spans exist).
        node = BehaviorNodeV1(
            node_id="node:no-span",
            symbol_id="sym:train.train",
            operation_id="op-no-span",
            predicate="READ",
            operands=("x",),
            result="",
            guard="",
            source_span_id="",
            source_authority="executable_hard",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-no-anchor"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-no-anchor",
            gain_tracker=gain,
        )
        assert "_compiled_evidence" not in update


# ---------------------------------------------------------------------------
# 4. Terminal obligation short-circuit
# ---------------------------------------------------------------------------


class TestTerminalObligationShortCircuit:
    """When the obligation is already terminal, the node returns early."""

    @pytest.mark.parametrize("status", ["supported", "explicit_gap", "blocked"])
    def test_terminal_obligation_returns_researching(
        self, snapshot: RepoSnapshot, status: str
    ) -> None:
        obl = _obligation(
            "obl-terminal",
            candidate_symbol_ids=("train.py:train",),
            status=status,
        )
        runtime = _runtime(snapshot, _agenda("run-term", snapshot, obl))
        node = _node(
            node_id="node:term",
            source_span_id="span:train.py:9:10",
        )
        bg = _graph(nodes=[node])
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-terminal"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-terminal",
            gain_tracker=gain,
        )
        # No compiled evidence, no gap flag.
        assert "_compiled_evidence" not in update
        assert "_gap_accepted" not in update
        assert update.get("status") == "researching"


# ---------------------------------------------------------------------------
# 5. Error / edge cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    """``compile_candidate_node`` handles missing obligation / runtime
    errors gracefully."""

    def test_no_active_obligation_returns_blocked(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-no-active",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-noa", snapshot, obl))
        bg = _graph()
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state(""),  # no active obligation
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="",
            gain_tracker=gain,
        )
        assert update["status"] == "blocked"
        assert update["blocked_reason"] == "compile_candidate_without_active_obligation"

    def test_obligation_not_in_agenda_returns_blocked(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-in-agenda",
            candidate_symbol_ids=("train.py:train",),
        )
        runtime = _runtime(snapshot, _agenda("run-nia", snapshot, obl))
        bg = _graph()
        gain = InformationGainTracker()

        update = compile_candidate_node(
            _state("obl-not-in-agenda"),
            runtime=runtime,
            behavior_graph=bg,
            active_obligation_id="obl-not-in-agenda",
            gain_tracker=gain,
        )
        assert update["status"] == "blocked"
        assert update["blocked_reason"] == "compile_candidate_obligation_not_in_agenda"


# ---------------------------------------------------------------------------
# 6. End-to-end: research loop produces compiled evidence sidecar
# ---------------------------------------------------------------------------


class TestResearchLoopProducesCompiledEvidence:
    """The full research loop (driven by ``ResearchLoopDriver``) must
    populate ``loop_state.compiled_evidence`` when an obligation is
    successfully compiled."""

    def test_loop_state_compiled_evidence_populated(
        self, snapshot: RepoSnapshot
    ) -> None:
        """When the evidence_critic routes to ``compile_candidate``, the
        driver stashes the result in ``loop_state.compiled_evidence``."""

        obl = _obligation(
            "obl-loop-compile",
            candidate_symbol_ids=("train.py:train",),
            typed_behavior_targets=(TypedBehaviorTargetV1(
                target_id="target-loop-call",
                desired_predicates=("CALL",),
            ),),
            # No missing_information: evidence_critic routes to
            # compile_candidate immediately.
        )
        runtime = _runtime(snapshot, _agenda("run-loop", snapshot, obl))
        loop = initial_loop_state(runtime)
        # Pre-populate the behavior graph with matching nodes so
        # ``compile_candidate_node`` has something to compile.
        node = _node(
            node_id="node:loop-read",
            symbol_id="sym:train.train",
            predicate="READ",
            operands=("optimizer",),
            result="opt",
            source_span_id="span:train.py:9:10",
        )
        loop.behavior_graph = _graph(
            nodes=[node],
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )

        driver = ResearchLoopDriver(runtime, max_turns=10)
        result = driver.run(loop_state=loop)

        # The loop must have produced compiled evidence for the obligation.
        assert "obl-loop-compile" in result.loop_state.compiled_evidence
        compiled = result.loop_state.compiled_evidence["obl-loop-compile"]
        assert isinstance(compiled, CompiledEvidence)
        assert isinstance(compiled.packet_set, EvidencePacketSetV3)
        assert isinstance(compiled.fact_set, CodeFactSetV1)
        assert isinstance(compiled.claim_set, AtomicClaimSetV3)

    def test_loop_obligation_marked_supported(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-loop-supported",
            candidate_symbol_ids=("train.py:train",),
            typed_behavior_targets=(TypedBehaviorTargetV1(
                target_id="target-loop-supported-call",
                desired_predicates=("CALL",),
            ),),
        )
        runtime = _runtime(snapshot, _agenda("run-sup", snapshot, obl))
        loop = initial_loop_state(runtime)
        node = _node(
            node_id="node:sup-read",
            symbol_id="sym:train.train",
            predicate="READ",
            operands=("optimizer",),
            result="opt",
            source_span_id="span:train.py:9:10",
        )
        loop.behavior_graph = _graph(
            nodes=[node],
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )

        driver = ResearchLoopDriver(runtime, max_turns=10)
        driver.run(loop_state=loop)

        # The obligation must be marked supported.
        assert obl.status == "supported"
        assert len(obl.supported_claim_ids) >= 1


# ---------------------------------------------------------------------------
# 7. Determinism: same inputs produce same compiled evidence digests
# ---------------------------------------------------------------------------


class TestCompileDeterminism:
    """``compile_candidate_node`` is deterministic: the same obligation +
    behavior graph produce the same packet/fact/claim digests."""

    def test_same_inputs_produce_same_digests(
        self, snapshot: RepoSnapshot
    ) -> None:
        def _run() -> tuple[str, str, str]:
            obl = _obligation(
                "obl-det",
                candidate_symbol_ids=("train.py:train",),
            )
            runtime = _runtime(snapshot, _agenda("run-det", snapshot, obl))
            node = _node(
                node_id="node:det-read",
                symbol_id="sym:train.train",
                predicate="READ",
                operands=("optimizer",),
                result="opt",
                source_span_id="span:train.py:9:10",
            )
            bg = _graph(nodes=[node])
            gain = InformationGainTracker()
            update = compile_candidate_node(
                _state("obl-det"),
                runtime=runtime,
                behavior_graph=bg,
                active_obligation_id="obl-det",
                gain_tracker=gain,
            )
            compiled = update["_compiled_evidence"]
            return (
                compiled["packet_set"].content_digest,
                compiled["fact_set"].content_digest,
                compiled["claim_set"].content_digest,
            )

        digests1 = _run()
        digests2 = _run()
        assert digests1 == digests2
