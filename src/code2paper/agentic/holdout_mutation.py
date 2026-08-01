"""Blind holdout and mutation protocol for the generic research plane.

This harness deliberately knows only snapshot files, an author-intent digest,
and generic adapter/compiler contracts.  It has no project profile, symbol
literal, paper text, or repository name.  A holdout is therefore useful for
checking that support boundaries come from executable behavior rather than a
look-ahead template.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph
from code2paper.agentic.evidence_compiler_v3 import AtomicClaimSetV3, CodeFactSetV1
from code2paper.agentic.generic_claim_compiler import ClaimProposalV1, compile_atomic_claims
from code2paper.agentic.generic_fact_compiler import FactCompilerInputV1, compile_facts_from_behavior_graph
from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter
from code2paper.agentic.repo_snapshot import RepoSnapshot, build_repo_snapshot


MutationClass = Literal[
    "move_file", "rename_symbol", "extract_helper", "inline_helper",
    "move_default", "behavior_change", "text_only",
]


class HoldoutProtocolV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    protocol_id: str
    snapshot_digest: str
    author_intent_digest: str
    prohibited_literals: tuple[str, ...] = Field(default_factory=tuple)
    prohibited_paths: tuple[str, ...] = Field(default_factory=tuple)
    allowed_languages: tuple[str, ...] = ("python",)
    mutation_classes: tuple[MutationClass, ...] = Field(default_factory=tuple)
    source_commit: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "HoldoutProtocolV1":
        if not self.protocol_id.strip() or not self.snapshot_digest.strip():
            raise ValueError("holdout protocol requires stable identity")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


class MutationSpecV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mutation_id: str
    mutation_class: MutationClass
    target_path: str
    description: str = ""
    expected_boundary: Literal["preserve", "change", "incomplete"] = "preserve"
    transform_id: str = ""


class SupportBoundaryV1(BaseModel):
    """Canonical support boundary with volatile source ids removed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str
    project_tree_hash: str
    language: str
    graph_predicates: tuple[str, ...] = Field(default_factory=tuple)
    graph_relations: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_relation_reasons: tuple[str, ...] = Field(default_factory=tuple)
    fact_signatures: tuple[str, ...] = Field(default_factory=tuple)
    claim_signatures: tuple[str, ...] = Field(default_factory=tuple)
    supported_claim_count: int = 0
    explicit_gap_count: int = 0
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "SupportBoundaryV1":
        payload = self.model_dump(mode="json", exclude={"content_digest", "snapshot_id", "project_tree_hash"})
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


class HoldoutMutationOutcomeV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mutation_id: str
    mutation_class: MutationClass
    expected_boundary: Literal["preserve", "change", "incomplete"]
    observed_boundary_relation: Literal["preserved", "changed", "incomplete"]
    passed: bool
    isolation_passed: bool
    before_boundary_digest: str
    after_boundary_digest: str
    failures: tuple[str, ...] = Field(default_factory=tuple)
    artifact_digests: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True)
class HoldoutAnalysis:
    snapshot: RepoSnapshot
    graph: CodeBehaviorGraphV1
    facts: CodeFactSetV1 | None = None
    claims: AtomicClaimSetV3 | None = None


def freeze_holdout_protocol(
    project_root: str | Path,
    *,
    author_intent: str,
    protocol_id: str = "holdout-v1",
    prohibited_literals: tuple[str, ...] = (),
    prohibited_paths: tuple[str, ...] = (),
    source_commit: str = "",
) -> HoldoutProtocolV1:
    snapshot = build_repo_snapshot(project_root)
    return HoldoutProtocolV1(
        protocol_id=protocol_id,
        snapshot_digest=snapshot.project_tree_hash,
        author_intent_digest=_digest(author_intent),
        prohibited_literals=tuple(dict.fromkeys(prohibited_literals)),
        prohibited_paths=tuple(dict.fromkeys(prohibited_paths)),
        source_commit=source_commit,
    )


def assert_holdout_isolation(
    protocol: HoldoutProtocolV1,
    *,
    generation_inputs: dict[str, Any],
    project_root: str | Path | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Check that a generation payload does not contain look-ahead material."""

    encoded = json.dumps(generation_inputs, ensure_ascii=False, sort_keys=True)
    failures: list[str] = []
    for literal in protocol.prohibited_literals:
        if literal and literal in encoded:
            failures.append(f"prohibited_literal:{literal}")
    for path in protocol.prohibited_paths:
        if path and path in encoded:
            failures.append(f"prohibited_path:{path}")
    if project_root is not None:
        root = Path(project_root).resolve()
        if any(str(root / path) in encoded for path in protocol.prohibited_paths):
            failures.append("absolute_prohibited_path")
    return not failures, tuple(failures)


def analyze_python_holdout(
    project_root: str | Path,
    *,
    facts: CodeFactSetV1 | None = None,
    claims: AtomicClaimSetV3 | None = None,
) -> HoldoutAnalysis:
    """Build a generic Python behavior graph with no profile selection."""

    snapshot = build_repo_snapshot(project_root)
    files = {
        item.path: (Path(project_root) / item.path).read_text(encoding="utf-8", errors="replace")
        for item in snapshot.included_files
        if item.kind == "file" and item.path.endswith(".py")
    }
    adapter = PythonBehaviorAdapter()
    index = adapter.index_symbols(
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        files=files,
    )
    graph_result = build_behavior_subgraph(
        adapter=adapter,
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        files=files,
        symbol_index=index,
        symbol_ids=[item.symbol_id for item in index.symbols],
        depth=1,
        node_budget=10000,
    )
    graph = graph_result.graph
    if facts is None and graph.nodes:
        facts = compile_facts_from_behavior_graph(
            graph,
            FactCompilerInputV1(
                obligation_id="holdout",
                behavior_node_ids=[node.node_id for node in graph.nodes],
                behavior_relation_ids=[relation.relation_id for relation in graph.relations],
                evidence_span_ids=[node.source_span_id for node in graph.nodes if node.source_span_id],
            ),
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            evidence_packet_digest=graph.content_digest,
        )
    if claims is None and facts is not None:
        proposals = [
            ClaimProposalV1(
                claim_id=f"holdout-claim:{fact.fact_id}",
                canonical_text=f"The executable path records predicate {fact.predicate}.",
                proposed_fact_ids=[fact.fact_id],
                allowed_wording_boundary=f"predicate {fact.predicate}",
            )
            for fact in facts.facts
            if fact.validation_status == "supported"
        ]
        claims, _ = compile_atomic_claims(
            proposals,
            facts,
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            evidence_packet_digest=graph.content_digest,
        )
    return HoldoutAnalysis(snapshot=snapshot, graph=graph, facts=facts, claims=claims)


def support_boundary_from_analysis(analysis: HoldoutAnalysis) -> SupportBoundaryV1:
    graph = analysis.graph
    fact_signatures = tuple(sorted(_fact_signature(fact) for fact in (analysis.facts.facts if analysis.facts else ())))
    claim_signatures = tuple(sorted(_claim_signature(claim) for claim in (analysis.claims.claims if analysis.claims else ())))
    return SupportBoundaryV1(
        snapshot_id=analysis.snapshot.snapshot_id,
        project_tree_hash=analysis.snapshot.project_tree_hash,
        language=graph.language,
        graph_predicates=tuple(sorted(graph.predicates())),
        graph_relations=tuple(sorted(graph.relation_kinds())),
        unresolved_relation_reasons=tuple(sorted(item.reason for item in graph.unresolved_relations)),
        fact_signatures=fact_signatures,
        claim_signatures=claim_signatures,
        supported_claim_count=sum(1 for claim in (analysis.claims.claims if analysis.claims else ()) if claim.status in {"supported", "partial"}),
        explicit_gap_count=len(analysis.claims.explicit_code_gaps) if analysis.claims else 0,
    )


def compare_support_boundaries(
    before: SupportBoundaryV1,
    after: SupportBoundaryV1,
    *,
    expected: Literal["preserve", "change", "incomplete"],
) -> tuple[Literal["preserved", "changed", "incomplete"], tuple[str, ...]]:
    if not before.fact_signatures and not before.claim_signatures and not after.fact_signatures and not after.claim_signatures:
        semantic_relation: Literal["preserved", "changed", "incomplete"] = "incomplete"
    else:
        semantic_relation = "preserved" if _semantic_key(before) == _semantic_key(after) else "changed"
    failures: list[str] = []
    if expected == "preserve" and semantic_relation != "preserved":
        failures.append("semantic_preserving_mutation_changed_support_boundary")
    elif expected == "change" and semantic_relation != "changed":
        failures.append("behavior_mutation_did_not_change_support_boundary")
    elif expected == "incomplete" and semantic_relation not in {"incomplete", "changed"}:
        failures.append("mutation_should_remain_incomplete")
    return semantic_relation, tuple(failures)


def apply_mutation_copy(
    project_root: str | Path,
    mutation: MutationSpecV1,
    *,
    transform: Callable[[Path, MutationSpecV1], None],
) -> Path:
    """Create an isolated temporary copy and apply one declared mutation."""

    source = Path(project_root)
    target = Path(tempfile.mkdtemp(prefix="code2paper-holdout-")) / "project"
    shutil.copytree(source, target)
    transform(target, mutation)
    return target


def evaluate_mutation(
    project_root: str | Path,
    protocol: HoldoutProtocolV1,
    mutation: MutationSpecV1,
    *,
    transform: Callable[[Path, MutationSpecV1], None],
    before_analysis: HoldoutAnalysis | None = None,
) -> HoldoutMutationOutcomeV1:
    """Run one isolated mutation and compare generic support boundaries."""

    before = before_analysis or analyze_python_holdout(project_root)
    before_boundary = support_boundary_from_analysis(before)
    isolated_ok, isolation_failures = assert_holdout_isolation(
        protocol,
        generation_inputs={
            "mutation_id": mutation.mutation_id,
            "mutation_class": mutation.mutation_class,
            "target_path": mutation.target_path,
            "description": mutation.description,
        },
        project_root=project_root,
    )
    if not isolated_ok:
        return HoldoutMutationOutcomeV1(
            mutation_id=mutation.mutation_id,
            mutation_class=mutation.mutation_class,
            expected_boundary=mutation.expected_boundary,
            observed_boundary_relation="incomplete",
            passed=False,
            isolation_passed=False,
            before_boundary_digest=before_boundary.content_digest,
            after_boundary_digest=before_boundary.content_digest,
            failures=isolation_failures,
        )
    try:
        target = apply_mutation_copy(project_root, mutation, transform=transform)
        after = analyze_python_holdout(target)
        after_boundary = support_boundary_from_analysis(after)
        relation, relation_failures = compare_support_boundaries(
            before_boundary,
            after_boundary,
            expected=mutation.expected_boundary,
        )
        return HoldoutMutationOutcomeV1(
            mutation_id=mutation.mutation_id,
            mutation_class=mutation.mutation_class,
            expected_boundary=mutation.expected_boundary,
            observed_boundary_relation=relation,
            passed=not relation_failures,
            isolation_passed=True,
            before_boundary_digest=before_boundary.content_digest,
            after_boundary_digest=after_boundary.content_digest,
            failures=relation_failures,
            artifact_digests={
                "before_snapshot": before.snapshot.project_tree_hash,
                "after_snapshot": after.snapshot.project_tree_hash,
                "before_graph": before.graph.content_digest,
                "after_graph": after.graph.content_digest,
            },
        )
    except (OSError, ValueError, RuntimeError) as exc:
        return HoldoutMutationOutcomeV1(
            mutation_id=mutation.mutation_id,
            mutation_class=mutation.mutation_class,
            expected_boundary=mutation.expected_boundary,
            observed_boundary_relation="incomplete",
            passed=mutation.expected_boundary == "incomplete",
            isolation_passed=True,
            before_boundary_digest=before_boundary.content_digest,
            after_boundary_digest=before_boundary.content_digest,
            failures=(f"mutation_analysis_failed:{exc.__class__.__name__}",),
        )


def _semantic_key(boundary: SupportBoundaryV1) -> tuple[Any, ...]:
    return (
        boundary.language,
        boundary.graph_predicates,
        boundary.graph_relations,
        boundary.unresolved_relation_reasons,
        boundary.fact_signatures,
        boundary.claim_signatures,
        boundary.supported_claim_count,
        boundary.explicit_gap_count,
    )


def _fact_signature(fact: Any) -> str:
    payload = {
        "predicate": str(getattr(fact, "predicate", "")),
        "object": getattr(fact, "object", ""),
        "conditions": tuple(getattr(fact, "conditions", ())),
        "strength": str(getattr(fact, "strength", "")),
        "validation_status": str(getattr(fact, "validation_status", "")),
    }
    return _digest(payload)


def _claim_signature(claim: Any) -> str:
    payload = {
        "canonical_text": str(getattr(claim, "canonical_text", "")),
        "claim_kind": str(getattr(claim, "claim_kind", "")),
        "status": str(getattr(claim, "status", "")),
        "qualifiers": tuple(getattr(claim, "required_qualifiers", ())),
    }
    return _digest(payload)


def _digest(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


__all__ = [
    "HoldoutAnalysis",
    "HoldoutMutationOutcomeV1",
    "HoldoutProtocolV1",
    "MutationSpecV1",
    "SupportBoundaryV1",
    "analyze_python_holdout",
    "apply_mutation_copy",
    "assert_holdout_isolation",
    "compare_support_boundaries",
    "freeze_holdout_protocol",
    "evaluate_mutation",
    "support_boundary_from_analysis",
]
