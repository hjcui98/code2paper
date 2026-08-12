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
from typing import Any, Callable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    CodeFactSetV1,
    EvidencePacketSetV3,
)
from code2paper.agentic.generic_evidence_compiler import (
    EvidencePacketProposalV1,
    EvidencePacketValidationReportV1,
    build_evidence_packet_set,
    compile_evidence_packet_proposal,
)
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
    behavior_value_signatures: tuple[str, ...] = Field(default_factory=tuple)
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


class HoldoutCaseEvidenceV1(BaseModel):
    """Fail-closed evidence for one frozen, profile-free holdout run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    protocol_digest: str
    frozen_snapshot_digest: str
    observed_snapshot_digest: str
    isolation_passed: bool = False
    profile_used: bool = False
    fallback_used: bool = False
    supported_must_cover_mainline_count: int = 0
    unsupported_positive_sentence_count: int = 0
    incomplete_sections: tuple[str, ...] = Field(default_factory=tuple)
    gap_search_scopes: tuple[str, ...] = Field(default_factory=tuple)
    gap_tool_attempts: tuple[str, ...] = Field(default_factory=tuple)
    gap_missing_relations: tuple[str, ...] = Field(default_factory=tuple)
    supported_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    artifact_digests: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True)
class HoldoutArtifactBundleV1:
    """Materialized generic artifacts for one frozen holdout.

    The bundle is intentionally not an authoring shortcut.  Packet and fact
    artifacts are compiled from the observed behavior graph; claim text is
    accepted only through ``ClaimProposalV1`` supplied by the proposing
    Agent.  Keeping the packet validation reports alongside the typed sets
    makes a failed or partial holdout replayable without silently promoting a
    rejected span.
    """

    analysis: HoldoutAnalysis
    packet_set: EvidencePacketSetV3
    fact_set: CodeFactSetV1
    claim_set: AtomicClaimSetV3 | None
    packet_validation_reports: tuple[EvidencePacketValidationReportV1, ...]
    claim_authorization_reports: tuple[Any, ...]
    artifact_digests: dict[str, str]
    artifact_file_digests: dict[str, str]


class HoldoutAcceptanceReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["passed", "failed"]
    case_count: int
    mutation_count: int
    failures: tuple[str, ...] = Field(default_factory=tuple)
    case_protocol_digests: dict[str, str] = Field(default_factory=dict)
    mutation_artifact_digests: dict[str, dict[str, str]] = Field(default_factory=dict)


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
    mutation_classes: tuple[MutationClass, ...] = (),
) -> HoldoutProtocolV1:
    snapshot = build_repo_snapshot(project_root)
    return HoldoutProtocolV1(
        protocol_id=protocol_id,
        snapshot_digest=snapshot.project_tree_hash,
        author_intent_digest=_digest(author_intent),
        prohibited_literals=tuple(dict.fromkeys(prohibited_literals)),
        prohibited_paths=tuple(dict.fromkeys(prohibited_paths)),
        source_commit=source_commit,
        mutation_classes=mutation_classes,
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
    claim_proposals: Sequence[ClaimProposalV1] | None = None,
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
    # Claim wording belongs to the proposing Agent.  The harness may compile
    # and authorize supplied proposals, but must never synthesize final prose
    # from predicates merely to make a holdout appear successful.
    if claims is None and facts is not None and claim_proposals is not None:
        claims, _ = compile_atomic_claims(
            list(claim_proposals),
            facts,
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            evidence_packet_digest=graph.content_digest,
        )
    return HoldoutAnalysis(snapshot=snapshot, graph=graph, facts=facts, claims=claims)


def materialize_holdout_artifacts(
    analysis: HoldoutAnalysis,
    *,
    protocol: HoldoutProtocolV1,
    case_id: str,
    output_dir: str | Path,
    claim_proposals: Sequence[ClaimProposalV1] = (),
    must_cover_claim_ids: Sequence[str] = (),
    generation_inputs: dict[str, Any] | None = None,
    incomplete_sections: Sequence[str] = (),
    gap_search_scopes: Sequence[str] = (),
    gap_tool_attempts: Sequence[str] = (),
    gap_missing_relations: Sequence[str] = (),
    unsupported_positive_sentence_count: int = 0,
) -> tuple[HoldoutCaseEvidenceV1, HoldoutArtifactBundleV1]:
    """Compile and persist a profile-free holdout artifact chain.

    This is the concrete D3 integration boundary.  It freezes the observed
    snapshot identity, compiles one validated packet for each distinct source
    span, then recompiles facts against that packet-set digest.  Natural
    language claims are never derived from predicates here: callers must pass
    proposals produced by an Agent and the generic claim authorizer decides
    whether they are supported.

    ``must_cover_claim_ids`` is an explicit, caller-owned mapping from the
    holdout's frozen intent to authorized claims.  The harness counts only
    claims that actually survived authorization, so a stale or invented id
    fails closed instead of inflating the mainline count.
    """

    if analysis.snapshot.project_tree_hash != protocol.snapshot_digest:
        raise ValueError("holdout analysis does not match frozen protocol snapshot")
    if not case_id.strip():
        raise ValueError("case_id must be non-empty")

    isolation_ok, isolation_failures = assert_holdout_isolation(
        protocol,
        generation_inputs=generation_inputs or {},
        project_root=analysis.snapshot.project_root,
    )

    # One packet per distinct source span keeps packets minimal while still
    # giving every source-derived fact a packet anchor.  A packet is included
    # only when the deterministic validator accepts it.
    packets = []
    packet_reports: list[EvidencePacketValidationReportV1] = []
    first_node_for_span: dict[str, Any] = {}
    for node in analysis.graph.nodes:
        if node.source_span_id and node.source_span_id not in first_node_for_span:
            first_node_for_span[node.source_span_id] = node
    for index, node in enumerate(first_node_for_span.values(), start=1):
        proposal = EvidencePacketProposalV1(
            packet_id=f"holdout-{case_id}-packet-{index:06d}",
            obligation_id="holdout-mainline",
            scope=node.symbol_id,
            anchor_span_ids=[node.source_span_id],
            behavior_node_ids=[node.node_id],
        )
        packet, report = compile_evidence_packet_proposal(
            proposal,
            analysis.graph,
            repo_snapshot_id=analysis.snapshot.snapshot_id,
            project_tree_hash=analysis.snapshot.project_tree_hash,
            repo_snapshot=analysis.snapshot,
        )
        packet_reports.append(report)
        if packet is not None and report.accepted:
            packets.append(packet)
    packet_set = build_evidence_packet_set(
        packets,
        repo_snapshot_id=analysis.snapshot.snapshot_id,
        project_tree_hash=analysis.snapshot.project_tree_hash,
    )

    # Facts must point to the packet-set digest.  Recompiling here avoids the
    # old graph-digest shortcut and gives the persisted chain the same
    # cross-artifact identity checks as the production V3 route.
    fact_set = compile_facts_from_behavior_graph(
        analysis.graph,
        FactCompilerInputV1(
            # Keep the generic fact identity stable with ``analyze_python_holdout``
            # so an Agent can inspect that analysis, propose claims, and have
            # the proposals replayed against the packet-bound recompilation.
            obligation_id="holdout",
            behavior_node_ids=[node.node_id for node in analysis.graph.nodes],
            behavior_relation_ids=[
                relation.relation_id for relation in analysis.graph.relations
            ],
            evidence_span_ids=[
                node.source_span_id
                for node in analysis.graph.nodes
                if node.source_span_id
            ],
        ),
        repo_snapshot_id=analysis.snapshot.snapshot_id,
        project_tree_hash=analysis.snapshot.project_tree_hash,
        evidence_packet_digest=packet_set.content_digest,
    )

    claim_set: AtomicClaimSetV3 | None = None
    claim_reports: list[Any] = []
    if claim_proposals:
        claim_set, claim_reports = compile_atomic_claims(
            list(claim_proposals),
            fact_set,
            repo_snapshot_id=analysis.snapshot.snapshot_id,
            project_tree_hash=analysis.snapshot.project_tree_hash,
            evidence_packet_digest=packet_set.content_digest,
        )

    authorized_ids = {
        claim.claim_id
        for claim in (claim_set.claims if claim_set is not None else ())
        if claim.status in {"supported", "partial"}
    }
    requested_mainline_ids = tuple(dict.fromkeys(must_cover_claim_ids))
    supported_mainline_ids = tuple(
        claim_id for claim_id in requested_mainline_ids if claim_id in authorized_ids
    )
    mainline_failures = tuple(
        f"missing_authorized_mainline_claim:{claim_id}"
        for claim_id in requested_mainline_ids
        if claim_id not in authorized_ids
    )
    if mainline_failures:
        isolation_ok = False
        isolation_failures = tuple([*isolation_failures, *mainline_failures])

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    artifact_payloads: dict[str, Any] = {
        "protocol": protocol.model_dump(mode="json"),
        "snapshot": analysis.snapshot.model_dump(mode="json"),
        "behavior_graph": analysis.graph.model_dump(mode="json"),
        "evidence_packets": packet_set.model_dump(mode="json"),
        "facts": fact_set.model_dump(mode="json"),
        "packet_validation": [item.model_dump(mode="json") for item in packet_reports],
        "claim_authorization": [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in claim_reports
        ],
    }
    if claim_set is not None:
        artifact_payloads["claims"] = claim_set.model_dump(mode="json")

    artifact_digests: dict[str, str] = {
        "snapshot": analysis.snapshot.project_tree_hash,
        "behavior_graph": analysis.graph.content_digest,
        "evidence_packets": packet_set.content_digest,
        "facts": fact_set.content_digest,
    }
    if claim_set is not None:
        artifact_digests["claims"] = claim_set.content_digest

    artifact_file_digests: dict[str, str] = {}
    for name, payload in artifact_payloads.items():
        destination = output / f"{name}_v1.json"
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(encoded + b"\n")
        temporary.replace(destination)
        artifact_file_digests[name] = _digest_bytes(encoded + b"\n")

    manifest_payload = {
        "schema_version": "1.0",
        "case_id": case_id,
        "protocol_digest": protocol.content_digest,
        "isolation_failures": list(isolation_failures),
        "artifact_digests": artifact_digests,
        "artifact_file_digests": artifact_file_digests,
        "packet_validation_failure_count": sum(
            1 for report in packet_reports if not report.accepted
        ),
        "claim_authorization_failure_count": sum(
            1 for report in claim_reports if getattr(report, "failures", ())
        ),
    }
    manifest_path = output / "holdout_artifact_manifest_v1.json"
    manifest_encoded = json.dumps(
        manifest_payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")
    manifest_path.write_bytes(manifest_encoded + b"\n")
    artifact_file_digests["manifest"] = _digest_bytes(manifest_encoded + b"\n")

    case = HoldoutCaseEvidenceV1(
        case_id=case_id,
        protocol_digest=protocol.content_digest,
        frozen_snapshot_digest=protocol.snapshot_digest,
        observed_snapshot_digest=analysis.snapshot.project_tree_hash,
        isolation_passed=isolation_ok,
        profile_used=False,
        fallback_used=False,
        supported_must_cover_mainline_count=len(supported_mainline_ids),
        unsupported_positive_sentence_count=unsupported_positive_sentence_count,
        incomplete_sections=tuple(incomplete_sections),
        gap_search_scopes=tuple(gap_search_scopes),
        gap_tool_attempts=tuple(gap_tool_attempts),
        gap_missing_relations=tuple(gap_missing_relations),
        supported_claim_ids=supported_mainline_ids,
        artifact_digests=artifact_digests,
    )
    (output / "case_evidence_v1.json").write_text(
        case.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    bundle = HoldoutArtifactBundleV1(
        analysis=HoldoutAnalysis(
            snapshot=analysis.snapshot,
            graph=analysis.graph,
            facts=fact_set,
            claims=claim_set,
        ),
        packet_set=packet_set,
        fact_set=fact_set,
        claim_set=claim_set,
        packet_validation_reports=tuple(packet_reports),
        claim_authorization_reports=tuple(claim_reports),
        artifact_digests=artifact_digests,
        artifact_file_digests=artifact_file_digests,
    )
    return case, bundle


def support_boundary_from_analysis(analysis: HoldoutAnalysis) -> SupportBoundaryV1:
    graph = analysis.graph
    fact_signatures = tuple(
        sorted(
            signature
            for signature in (
                _fact_signature(fact)
                for fact in (analysis.facts.facts if analysis.facts else ())
            )
            if signature
        )
    )
    claim_signatures = tuple(sorted(_claim_signature(claim) for claim in (analysis.claims.claims if analysis.claims else ())))
    return SupportBoundaryV1(
        snapshot_id=analysis.snapshot.snapshot_id,
        project_tree_hash=analysis.snapshot.project_tree_hash,
        language=graph.language,
        graph_predicates=tuple(sorted(graph.predicates())),
        graph_relations=tuple(sorted(graph.relation_kinds())),
        behavior_value_signatures=tuple(sorted(_behavior_value_signatures(graph))),
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


def build_holdout_acceptance_report(
    cases: Sequence[HoldoutCaseEvidenceV1],
    mutations: Sequence[HoldoutMutationOutcomeV1],
) -> HoldoutAcceptanceReportV1:
    """Evaluate the D3 exit contract without granting evidence authority.

    Exactly two or more independently frozen protocols are required.  A
    precise incomplete section is allowed, but it cannot replace the
    requirement that every holdout has a supported must-cover mainline.
    """

    failures: list[str] = []
    if len(cases) < 2 or len({case.protocol_digest for case in cases}) < 2:
        failures.append("two_independent_frozen_holdouts_required")
    for case in cases:
        prefix = f"case:{case.case_id}:"
        if case.frozen_snapshot_digest != case.observed_snapshot_digest:
            failures.append(prefix + "source_changed_after_freeze")
        if not case.isolation_passed:
            failures.append(prefix + "isolation_failed")
        if case.profile_used:
            failures.append(prefix + "project_profile_used")
        if case.fallback_used:
            failures.append(prefix + "fallback_used")
        if case.supported_must_cover_mainline_count < 1:
            failures.append(prefix + "no_supported_must_cover_mainline")
        if case.supported_must_cover_mainline_count > len(case.supported_claim_ids):
            failures.append(prefix + "supported_mainline_claim_ids_missing")
        required_artifacts = {
            "snapshot", "behavior_graph", "evidence_packets", "facts", "claims",
        }
        if not required_artifacts <= set(case.artifact_digests):
            failures.append(prefix + "research_artifact_chain_incomplete")
        elif any(
            not str(case.artifact_digests[key]).startswith("sha256:")
            or len(str(case.artifact_digests[key])) != 71
            for key in required_artifacts
        ):
            failures.append(prefix + "research_artifact_digest_invalid")
        if case.unsupported_positive_sentence_count:
            failures.append(prefix + "unsupported_positive_sentences")
        if case.incomplete_sections and not (
            case.gap_search_scopes
            and case.gap_tool_attempts
            and case.gap_missing_relations
        ):
            failures.append(prefix + "incomplete_without_precise_gap")
    for mutation in mutations:
        if not mutation.isolation_passed:
            failures.append(f"mutation:{mutation.mutation_id}:isolation_failed")
        if not mutation.passed:
            failures.append(f"mutation:{mutation.mutation_id}:boundary_mismatch")
    return HoldoutAcceptanceReportV1(
        status="failed" if failures else "passed",
        case_count=len(cases),
        mutation_count=len(mutations),
        failures=tuple(failures),
        case_protocol_digests={case.case_id: case.protocol_digest for case in cases},
        mutation_artifact_digests={
            mutation.mutation_id: dict(mutation.artifact_digests)
            for mutation in mutations
        },
    )


def write_holdout_acceptance_report(
    path: str | Path,
    report: HoldoutAcceptanceReportV1,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination


def load_holdout_acceptance_report(path: str | Path) -> HoldoutAcceptanceReportV1:
    return HoldoutAcceptanceReportV1.model_validate_json(Path(path).read_text(encoding="utf-8"))


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
    target: Path | None = None
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
    finally:
        if target is not None and target.parent.name.startswith("code2paper-holdout-"):
            shutil.rmtree(target.parent, ignore_errors=True)


def _semantic_key(boundary: SupportBoundaryV1) -> tuple[Any, ...]:
    # Plumbing operations are unstable under helper extraction/inlining and
    # therefore cannot define the semantic support boundary.  Concrete
    # operation predicates and literal/operator signatures still distinguish
    # behavior changes such as TOPK -> SORT or a moved default changing value.
    plumbing = {"CALL", "RETURN", "READ", "WRITE", "LOAD"}
    topology_relations = {
        "CONTAINS", "NEXT_CONTROL", "CALLS", "RETURNS_TO",
        "DATA_DEPENDS_ON", "CONTROL_DEPENDS_ON",
    }
    return (
        boundary.language,
        tuple(item for item in boundary.graph_predicates if item not in plumbing),
        tuple(item for item in boundary.graph_relations if item not in topology_relations),
        boundary.behavior_value_signatures,
        # Predicate/object/guard signatures are source-derived and stable
        # across path and symbol renames, while still detecting an operation
        # replacement that leaves the coarse predicate set unchanged (for
        # example one sort key being removed from a multi-stage module).
        boundary.fact_signatures,
        boundary.explicit_gap_count,
    )


def _behavior_value_signatures(graph: CodeBehaviorGraphV1) -> set[str]:
    """Retain behavior-significant literals/operators, not local names."""

    import re

    signatures: set[str] = set()
    plumbing = {"CALL", "RETURN", "READ", "WRITE", "LOAD"}
    for node in graph.nodes:
        config_evidence = any(
            marker in node.diagnostics
            for marker in ("parameter_default", "config_access")
        )
        if node.predicate in plumbing and not config_evidence:
            continue
        text = " ".join([*node.operands, node.result, node.guard])
        literals = re.findall(
            r"(?<![A-Za-z_])(?:-?\d+(?:\.\d+)?|True|False|None)(?![A-Za-z_])",
            text,
        )
        operators = re.findall(r">=|<=|==|!=|>|<|\+|-|\*|/|%", text)
        if literals or operators:
            signatures.add(_digest({
                "predicate": node.predicate,
                "literals": literals,
                "operators": operators,
            }))
    return signatures


def _fact_signature(fact: Any) -> str:
    predicate = str(getattr(fact, "predicate", ""))
    # Plumbing operations are deliberately excluded: helper extraction and
    # symbol renames introduce CALL/READ/RETURN noise without changing the
    # supported behavior.  Semantic predicates remain in the boundary.
    if predicate in {"reads", "writes", "calls", "returns", "loads_weights"}:
        return ""
    semantic_context = tuple(
        item
        for item in getattr(fact, "semantic_context", ())
        if not item.startswith(("sym:", "node:"))
        and (
            item.startswith(("method:", "name:", "qualified:", "key="))
        or any(character.isdigit() for character in item)
        or any(operator in item for operator in ("==", "!=", ">=", "<=", ">", "<", "+", "-", "*", "/", "%"))
        or item in {"guarded_continue", "parameter_default", "config_access"}
        )
    )
    payload = {
        "predicate": predicate,
        # Keep operation/method markers and literals, but not local variable
        # names.  This makes extract-helper/inlining preserve the boundary
        # while still distinguishing two different sort keys or reductions.
        "semantic_context": semantic_context,
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


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


__all__ = [
    "HoldoutAnalysis",
    "HoldoutArtifactBundleV1",
    "HoldoutAcceptanceReportV1",
    "HoldoutCaseEvidenceV1",
    "HoldoutMutationOutcomeV1",
    "HoldoutProtocolV1",
    "MutationSpecV1",
    "SupportBoundaryV1",
    "analyze_python_holdout",
    "materialize_holdout_artifacts",
    "apply_mutation_copy",
    "assert_holdout_isolation",
    "build_holdout_acceptance_report",
    "compare_support_boundaries",
    "freeze_holdout_protocol",
    "evaluate_mutation",
    "load_holdout_acceptance_report",
    "support_boundary_from_analysis",
    "write_holdout_acceptance_report",
]
