"""R4.5 tests for the generic evidence packet validator (R4.1).

Verifies the deterministic validator checklist:

- snapshot/freshness mismatch is flagged;
- hint-only anchor is rejected (source authority);
- wrong span role is flagged (anchor_span_ids must map to anchor spans);
- relation existence is checked (unknown / unresolved relations fail);
- guard coverage: a missing guard on a selected node fails;
- minimality: >3 spans without composition_rationale fails;
- rejected candidate without reason fails;
- fan-in > 3 is supported when composition_rationale is supplied (minimal
  connected subgraph requirement);
- semantic verifier cannot override a deterministic failure.
"""

from __future__ import annotations

import pytest

from code2paper.agentic.behavior_graph import (
    BehaviorNodeV1,
    BehaviorRelationV1,
    CodeBehaviorGraphV1,
    UnresolvedRelationV1,
)
from code2paper.agentic.generic_evidence_compiler import (
    EvidencePacketProposalV1,
    RejectedCandidateProposalV1,
    compile_evidence_packet_proposal,
    validate_evidence_packet_proposal,
)
from code2paper.agentic.evidence_compiler_v3 import EvidencePacketV3


_REPO_SNAPSHOT_ID = "repo:test-snapshot"
_PROJECT_TREE_HASH = "sha256:tree"


def _node(
    *,
    node_id: str,
    symbol_id: str = "sym:module.func",
    predicate: str = "READ",
    operands: tuple[str, ...] = ("x",),
    result: str = "",
    guard: str = "",
    source_span_id: str = "span:module.py:1:10",
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
    kind: str = "CALLS",
    source_node_id: str = "node:a",
    target_node_id: str = "node:b",
    source_symbol_id: str = "sym:module.func",
    target_symbol_id: str = "sym:module.other",
    source_span_id: str = "span:module.py:1:10",
    target_span_id: str = "span:other.py:1:5",
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


def _graph(
    nodes: list[BehaviorNodeV1] | None = None,
    relations: list[BehaviorRelationV1] | None = None,
    unresolved: list[UnresolvedRelationV1] | None = None,
) -> CodeBehaviorGraphV1:
    return CodeBehaviorGraphV1(
        repo_snapshot_id=_REPO_SNAPSHOT_ID,
        project_tree_hash=_PROJECT_TREE_HASH,
        language="python",
        nodes=nodes or [],
        relations=relations or [],
        unresolved_relations=unresolved or [],
    ).with_digest()


def _proposal(
    *,
    packet_id: str = "pkt-1",
    obligation_id: str = "obl-1",
    scope: str = "module.py:func",
    anchor_span_ids: list[str] | None = None,
    relation_span_ids: list[str] | None = None,
    semantic_span_ids: list[str] | None = None,
    behavior_node_ids: list[str] | None = None,
    behavior_relation_ids: list[str] | None = None,
    conditions: list[str] | None = None,
    composition_rationale: str = "",
    rejected_candidates: list[RejectedCandidateProposalV1] | None = None,
) -> EvidencePacketProposalV1:
    return EvidencePacketProposalV1(
        packet_id=packet_id,
        obligation_id=obligation_id,
        scope=scope,
        anchor_span_ids=anchor_span_ids or [],
        relation_span_ids=relation_span_ids or [],
        semantic_span_ids=semantic_span_ids or [],
        behavior_node_ids=behavior_node_ids or [],
        behavior_relation_ids=behavior_relation_ids or [],
        conditions=conditions or [],
        composition_rationale=composition_rationale,
        rejected_candidates=rejected_candidates or [],
    )


# ---------------------------------------------------------------------------
# Accepted proposals
# ---------------------------------------------------------------------------


class TestAcceptedProposal:
    def test_minimal_packet_with_single_anchor_is_accepted(self) -> None:
        node = _node(node_id="node:anchor", predicate="READ")
        graph = _graph(nodes=[node])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            behavior_node_ids=["node:anchor"],
        )
        packet, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert report.accepted, f"unexpected failures: {report.failures}"
        assert packet is not None
        assert packet.anchor_span_ids == ["span:module.py:1:10"]

    def test_packet_with_anchor_and_relation_span_is_accepted(self) -> None:
        node_a = _node(node_id="node:a", predicate="READ", source_span_id="span:module.py:1:10")
        node_b = _node(node_id="node:b", predicate="CALL", source_span_id="span:other.py:1:5")
        rel = _relation(relation_id="rel:1")
        graph = _graph(nodes=[node_a, node_b], relations=[rel])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            relation_span_ids=["span:other.py:1:5"],
            behavior_node_ids=["node:a", "node:b"],
            behavior_relation_ids=["rel:1"],
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert report.accepted, f"unexpected failures: {report.failures}"


# ---------------------------------------------------------------------------
# Source authority: hint-only anchor rejected
# ---------------------------------------------------------------------------


class TestHintOnlyAnchorRejected:
    def test_hint_only_anchor_is_rejected(self) -> None:
        node = _node(
            node_id="node:hint",
            predicate="READ",
            source_authority="semantic_hint",
        )
        graph = _graph(nodes=[node])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            behavior_node_ids=["node:hint"],
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert not report.accepted
        assert any("hint_only_anchor" in f for f in report.failures)

    def test_executable_hard_anchor_is_accepted(self) -> None:
        node = _node(
            node_id="node:hard",
            predicate="READ",
            source_authority="executable_hard",
        )
        graph = _graph(nodes=[node])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            behavior_node_ids=["node:hard"],
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert report.accepted, f"unexpected failures: {report.failures}"


# ---------------------------------------------------------------------------
# Wrong span role
# ---------------------------------------------------------------------------


class TestWrongSpanRole:
    def test_anchor_declared_but_no_behavior_node_supplies_it(self) -> None:
        # The proposal declares an anchor span id, but no behavior node
        # supplies that span id.  The validator must flag the span as
        # missing (anchor_span_missing) rather than silently accepting it.
        node_a = _node(node_id="node:a", predicate="READ", source_span_id="span:module.py:1:10")
        graph = _graph(nodes=[node_a])
        proposal = _proposal(
            # Declare a span that no behavior node supplies.
            anchor_span_ids=["span:nonexistent.py:1:5"],
            behavior_node_ids=["node:a"],
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert any("anchor_span_missing" in f or "anchor_span_has_no_behavior_node" in f
                   for f in report.failures)


# ---------------------------------------------------------------------------
# Relation existence
# ---------------------------------------------------------------------------


class TestRelationExistence:
    def test_unknown_relation_is_flagged(self) -> None:
        node = _node(node_id="node:a", predicate="READ")
        graph = _graph(nodes=[node])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            behavior_node_ids=["node:a"],
            behavior_relation_ids=["rel:does-not-exist"],
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert any("relation_unknown" in f for f in report.failures)

    def test_unresolved_relation_is_flagged(self) -> None:
        node = _node(node_id="node:a", predicate="CALL")
        unresolved = UnresolvedRelationV1(
            relation_id="rel:unresolved",
            kind="CALLS",
            source_node_id="node:a",
            source_symbol_id="sym:module.func",
            source_span_id="span:module.py:1:10",
            reason="dynamic_call",
            target_hint="external_fn",
        )
        graph = _graph(nodes=[node], unresolved=[unresolved])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            behavior_node_ids=["node:a"],
            behavior_relation_ids=["rel:unresolved"],
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert any("relation_unresolved" in f for f in report.failures)


# ---------------------------------------------------------------------------
# Guard coverage
# ---------------------------------------------------------------------------


class TestGuardCoverage:
    def test_missing_guard_is_flagged(self) -> None:
        node = _node(node_id="node:guarded", predicate="READ", guard="use_feature_x=True")
        graph = _graph(nodes=[node])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            behavior_node_ids=["node:guarded"],
            conditions=[],  # guard not declared
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert any("missing_guard" in f for f in report.failures)

    def test_declared_guard_is_accepted(self) -> None:
        node = _node(node_id="node:guarded", predicate="READ", guard="use_feature_x=True")
        graph = _graph(nodes=[node])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            behavior_node_ids=["node:guarded"],
            conditions=["use_feature_x=True"],
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert report.accepted, f"unexpected failures: {report.failures}"


# ---------------------------------------------------------------------------
# Minimality / fan-in
# ---------------------------------------------------------------------------


class TestMinimality:
    def test_four_spans_without_rationale_is_rejected(self) -> None:
        nodes = [
            _node(node_id=f"node:{i}", predicate="READ", source_span_id=f"span:f{i}.py:1:10")
            for i in range(4)
        ]
        graph = _graph(nodes=nodes)
        proposal = _proposal(
            anchor_span_ids=["span:f0.py:1:10"],
            relation_span_ids=["span:f1.py:1:10", "span:f2.py:1:10", "span:f3.py:1:10"],
            behavior_node_ids=[f"node:{i}" for i in range(4)],
            composition_rationale="",  # missing
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert any("missing_composition_rationale" in f for f in report.failures)

    def test_four_spans_with_rationale_is_accepted(self) -> None:
        # Build a connected subgraph: anchor + 3 relation spans linked by
        # CALLS relations so the "unrelated span" check passes.
        nodes = [
            _node(node_id="node:0", predicate="READ", source_span_id="span:f0.py:1:10"),
            _node(node_id="node:1", predicate="CALL", source_span_id="span:f1.py:1:10"),
            _node(node_id="node:2", predicate="CALL", source_span_id="span:f2.py:1:10"),
            _node(node_id="node:3", predicate="CALL", source_span_id="span:f3.py:1:10"),
        ]
        rels = [
            _relation(
                relation_id=f"rel:{i}",
                kind="CALLS",
                source_node_id=f"node:{i}",
                target_node_id=f"node:{i+1}",
                source_span_id=f"span:f{i}.py:1:10",
                target_span_id=f"span:f{i+1}.py:1:10",
            )
            for i in range(3)
        ]
        graph = _graph(nodes=nodes, relations=rels)
        proposal = _proposal(
            anchor_span_ids=["span:f0.py:1:10"],
            relation_span_ids=["span:f1.py:1:10", "span:f2.py:1:10", "span:f3.py:1:10"],
            behavior_node_ids=[f"node:{i}" for i in range(4)],
            behavior_relation_ids=[f"rel:{i}" for i in range(3)],
            composition_rationale="All four spans are needed to trace the call chain.",
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert report.accepted, f"unexpected failures: {report.failures}"

    def test_rejected_candidate_without_reason_is_flagged(self) -> None:
        node = _node(node_id="node:a", predicate="READ")
        graph = _graph(nodes=[node])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            behavior_node_ids=["node:a"],
            rejected_candidates=[
                RejectedCandidateProposalV1(
                    path="other.py",
                    symbol="sym:other",
                    reason="",  # missing reason
                ),
            ],
        )
        _, report = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert any("rejected_candidate_without_reason" in f for f in report.failures)


# ---------------------------------------------------------------------------
# Semantic verifier cannot override deterministic failure
# ---------------------------------------------------------------------------


class TestSemanticOverrideBlocked:
    def test_semantic_notes_cannot_remove_failures(self) -> None:
        """The validation report model must not allow ``semantic_notes`` to
        clear ``failures``.  We verify the ``accepted`` property is read-only
        and derived solely from ``failures``."""
        from code2paper.agentic.generic_evidence_compiler import (
            EvidencePacketValidationReportV1,
        )

        report = EvidencePacketValidationReportV1(
            packet_id="pkt-1",
            failures=["hint_only_anchor:span:x"],
            semantic_notes=["the LLM thinks this is fine"],
        )
        assert not report.accepted
        assert "hint_only_anchor:span:x" in report.failures


# ---------------------------------------------------------------------------
# Snapshot / freshness
# ---------------------------------------------------------------------------


class TestSnapshotFreshness:
    def test_span_snapshot_mismatch_is_flagged(self) -> None:
        # Build a packet proposal whose spans carry a different snapshot id
        # by compiling with a mismatched repo_snapshot_id.
        node = _node(node_id="node:a", predicate="READ")
        graph = _graph(nodes=[node])
        proposal = _proposal(
            anchor_span_ids=["span:module.py:1:10"],
            behavior_node_ids=["node:a"],
        )
        # Compile with the correct snapshot id, then re-validate against a
        # different snapshot id.
        packet, _ = compile_evidence_packet_proposal(
            proposal, graph,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert packet is not None
        report = validate_evidence_packet_proposal(
            proposal=proposal,
            graph=graph,
            compiled_packet=packet,
            repo_snapshot_id="repo:DIFFERENT",  # mismatch
            project_tree_hash=_PROJECT_TREE_HASH,
            selected_nodes=[node],
            selected_relations=[],
            spans=packet.spans,
            unresolved_ids=set(),
        )
        assert any("span_snapshot_mismatch" in f for f in report.failures)
