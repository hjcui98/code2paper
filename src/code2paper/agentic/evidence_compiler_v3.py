from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.repo_snapshot import RepoSnapshot

def _digest(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

class CompilerV3Model(BaseModel):
    model_config = ConfigDict(extra="forbid")

class EvidenceSpanV3(CompilerV3Model):
    span_id: str
    snapshot_id: str
    project_tree_hash: str
    path: str
    symbol: str
    line_start: int
    line_end: int
    exact_excerpt: str
    excerpt_digest: str
    file_digest: str
    role: Literal["anchor", "relation", "semantic"]

class RejectedEvidenceCandidateV3(CompilerV3Model):
    path: str
    symbol: str
    reason: str
    allowed_scope: str = ""

class RelationEvidenceV3(CompilerV3Model):
    relation_id: str
    relation_type: Literal["call_flow", "data_flow", "control_flow", "writes"]
    source_symbol: str
    target_symbol: str
    direct_span_ids: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    statement: str

class EvidencePacketV3(CompilerV3Model):
    packet_id: str
    obligation_tags: list[str] = Field(default_factory=list)
    scope: str
    anchor_span_ids: list[str]
    relation_span_ids: list[str] = Field(default_factory=list)
    semantic_span_ids: list[str] = Field(default_factory=list)
    spans: list[EvidenceSpanV3]
    relations: list[RelationEvidenceV3] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    composition_rationale: str = ""
    rejected_candidates: list[RejectedEvidenceCandidateV3] = Field(default_factory=list)
    source_digest: str

    @model_validator(mode="after")
    def _packet_is_minimal_or_explained(self) -> "EvidencePacketV3":
        used = set(self.anchor_span_ids + self.relation_span_ids + self.semantic_span_ids)
        known = {span.span_id for span in self.spans}
        if not set(self.anchor_span_ids).issubset(known) or not used.issubset(known):
            raise ValueError("packet references unknown span ids")
        if len(used) > 3 and not self.composition_rationale.strip():
            raise ValueError("packets with more than three spans require composition rationale")
        return self

class EvidencePacketSetV3(CompilerV3Model):
    schema_version: str = "3.0"
    producer_version: str = "code2paper-evidence-compiler-v3"
    repo_snapshot_id: str
    project_tree_hash: str
    packets: list[EvidencePacketV3]
    content_digest: str

FactPredicate = Literal[
    # First-batch predicates (preserved for backward compatibility with the
    # project-specific profile in ``compile_evidence_v3``).
    "reads", "transforms", "constructs", "loads_weights", "calls", "calls_in_order",
    "returns", "selects", "selects_column", "sorts_by", "selects_top_k",
    "constructs_mask", "filters_by", "writes", "writes_artifact", "branches_on",
    "computes_formula", "does_not_call",
    # Generic predicates (R4.2): emitted by ``generic_fact_compiler`` from
    # ``CodeBehaviorGraphV1`` nodes/relations.  These cover every behavior
    # predicate in ``BEHAVIOR_PREDICATES`` plus the ``configured_by`` fact
    # derived from a ``CONFIGURED_BY`` relation.
    "concatenates", "stacks", "normalizes", "reduces", "aggregates", "compares",
    "loops", "reshapes", "projects", "attends", "samples", "propagates",
    "configured_by",
]

class CodeFactV1(CompilerV3Model):
    fact_id: str
    subject: str
    predicate: FactPredicate
    object: str | list[str]
    conditions: list[str] = Field(default_factory=list)
    scope: str
    direct_span_ids: list[str]
    relation_span_ids: list[str] = Field(default_factory=list)
    relation_evidence_ids: list[str] = Field(default_factory=list)
    # Source-derived descriptors retained for deterministic coverage replay.
    # They are extracted from the same behavior nodes/relations as the source
    # spans, never from author intent.
    relation_kinds: list[str] = Field(default_factory=list)
    semantic_context: list[str] = Field(default_factory=list)
    strength: Literal["direct", "scoped_negative"] = "direct"
    exact_source_digest: str
    canonical_identity: str
    validation_status: Literal["supported", "rejected"] = "supported"
    validation_failures: list[str] = Field(default_factory=list)

class CodeFactSetV1(CompilerV3Model):
    schema_version: str = "1.0"
    producer_version: str = "code2paper-evidence-compiler-v3"
    repo_snapshot_id: str
    project_tree_hash: str
    evidence_packet_digest: str
    facts: list[CodeFactV1]
    content_digest: str

class AtomicClaimV3(CompilerV3Model):
    claim_id: str
    canonical_text: str
    claim_kind: Literal[
        "implementation_behavior", "configuration_fact", "design_rationale", "performance_or_novelty"
    ] = "implementation_behavior"
    fact_ids: list[str]
    covers_obligation_ids: list[str] = Field(default_factory=list)
    direct_evidence_ids: list[str]
    relation_evidence_ids: list[str] = Field(default_factory=list)
    required_qualifiers: list[str] = Field(default_factory=list)
    unsupported_author_fragments: list[str] = Field(default_factory=list)
    allowed_wording_boundary: str
    canonical_identity: str
    status: Literal["supported", "partial", "unsupported", "code_gap"] = "supported"

class ExplicitCodeGapV1(CompilerV3Model):
    gap_id: str
    topic: str
    status: Literal["not_implemented_in_repo"] = "not_implemented_in_repo"
    scope: str
    rationale: str
    source_kind: Literal["semantic_hint", "author_obligation"] = "semantic_hint"

class SemanticStageGroupV1(CompilerV3Model):
    """Project-agnostic organization metadata for authorized V3 claims."""

    stage_id: str
    name: str
    purpose: str
    ordered_claim_ids: list[str]
    covers_obligation_ids: list[str] = Field(default_factory=list)
    relation_evidence_ids: list[str] = Field(default_factory=list)
    organization_priority: int = 0

class AtomicClaimSetV3(CompilerV3Model):
    schema_version: str = "3.0"
    producer_version: str = "code2paper-evidence-compiler-v3"
    repo_snapshot_id: str
    project_tree_hash: str
    evidence_packet_digest: str
    code_fact_digest: str
    claims: list[AtomicClaimV3]
    explicit_code_gaps: list[ExplicitCodeGapV1] = Field(default_factory=list)
    semantic_stage_groups: list[SemanticStageGroupV1] = Field(default_factory=list)
    content_digest: str

class EvidenceCompilerV3Result(CompilerV3Model):
    profile_id: str = ""
    profile_match: dict[str, Any] = Field(default_factory=dict)
    packets: EvidencePacketSetV3
    facts: CodeFactSetV1
    claims: AtomicClaimSetV3

class _SourceIndex:
    def __init__(self, root: Path, snapshot: RepoSnapshot):
        self.root = root
        self.snapshot = snapshot
        self._files = {item.path: item for item in snapshot.included_files if item.kind == "file"}
        self._nodes: dict[tuple[str, str], ast.AST] = {}

    def has(self, path: str, symbol: str) -> bool:
        try:
            self.node(path, symbol)
            return True
        except (OSError, SyntaxError, KeyError):
            return False

    def node(self, path: str, symbol: str) -> ast.AST:
        key = (path, symbol)
        if key in self._nodes:
            return self._nodes[key]
        source = (self.root / path).read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
        parts = symbol.split(".")
        nodes: list[ast.AST] = list(tree.body)
        current: ast.AST | None = None
        for part in parts:
            current = next(
                (item for item in nodes if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == part),
                None,
            )
            if current is None:
                raise KeyError(f"symbol not found: {path}:{symbol}")
            nodes = list(getattr(current, "body", []))
        self._nodes[key] = current
        return current

    def span(self, span_id: str, path: str, symbol: str, role: Literal["anchor", "relation", "semantic"]) -> EvidenceSpanV3:
        node = self.node(path, symbol)
        line_start = int(getattr(node, "lineno"))
        line_end = int(getattr(node, "end_lineno"))
        return self.line_span(
            span_id,
            path,
            symbol,
            line_start,
            line_end,
            role,
        )

    def line_span(
        self,
        span_id: str,
        path: str,
        symbol: str,
        line_start: int,
        line_end: int,
        role: Literal["anchor", "relation", "semantic"],
    ) -> EvidenceSpanV3:
        """Create an exact span for executable module-level statements."""

        lines = (self.root / path).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if line_start < 1 or line_end < line_start or line_end > len(lines):
            raise ValueError(f"invalid line span: {path}:{line_start}-{line_end}")
        excerpt = "".join(lines[line_start - 1:line_end])
        file_entry = self._files.get(path)
        return EvidenceSpanV3(
            span_id=span_id,
            snapshot_id=self.snapshot.snapshot_id,
            project_tree_hash=self.snapshot.project_tree_hash,
            path=path,
            symbol=symbol,
            line_start=line_start,
            line_end=line_end,
            exact_excerpt=excerpt,
            excerpt_digest=_digest(excerpt),
            file_digest=str(file_entry.content_digest if file_entry else _digest("")),
            role=role,
        )

def compile_evidence_v3(repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
    """Select a structure profile, compile it, and run common validation.

    Returning ``None`` is a fail-closed profile miss; callers may retain V2
    diagnostics but must not authorize Method prose from the V2 fallback.
    """

    from code2paper.agentic.evidence_profiles.registry import (
        default_evidence_profile_registry,
    )

    profile, matches = default_evidence_profile_registry().select(repo_snapshot)
    if profile is None:
        return None
    result = profile.compile(repo_snapshot)
    if result is None:
        return None
    if validate_evidence_compiler_v3(result, repo_snapshot):
        return None
    selected_match = next(
        (match for match in matches if match.profile_id == profile.profile_id),
        None,
    )
    return result.model_copy(
        update={
            "profile_id": profile.profile_id,
            "profile_match": (
                selected_match.model_dump(mode="json") if selected_match else {}
            ),
        }
    )

def validate_evidence_compiler_v3(result: EvidenceCompilerV3Result, repo_snapshot: RepoSnapshot) -> list[str]:
    failures: list[str] = []
    root = Path(repo_snapshot.project_root).resolve()
    if result.packets.repo_snapshot_id != repo_snapshot.snapshot_id or result.packets.project_tree_hash != repo_snapshot.project_tree_hash:
        failures.append("packet_snapshot_mismatch")
    for packet in result.packets.packets:
        for span in packet.spans:
            try:
                lines = (root / span.path).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                excerpt = "".join(lines[span.line_start - 1:span.line_end])
            except OSError:
                failures.append(f"span_missing:{span.span_id}")
                continue
            if _digest(excerpt) != span.excerpt_digest:
                failures.append(f"span_digest_mismatch:{span.span_id}")
        spans_by_id = {span.span_id: span for span in packet.spans}
        for span_id in packet.anchor_span_ids:
            span = spans_by_id.get(span_id)
            if span is not None and span.role != "anchor":
                failures.append(f"wrong_span_role:{packet.packet_id}:{span_id}:anchor")
        for span_id in packet.relation_span_ids:
            span = spans_by_id.get(span_id)
            if span is not None and span.role not in {"relation", "semantic"}:
                failures.append(f"wrong_span_role:{packet.packet_id}:{span_id}:relation")
    fact_ids = {item.fact_id for item in result.facts.facts if item.validation_status == "supported"}
    identities: set[str] = set()
    for claim in result.claims.claims:
        if not set(claim.fact_ids).issubset(fact_ids):
            failures.append(f"claim_unknown_fact:{claim.claim_id}")
        if claim.canonical_identity in identities:
            failures.append(f"duplicate_canonical_behavior:{claim.claim_id}")
        identities.add(claim.canonical_identity)
    return failures

def write_compiler_v3_artifacts(root: str | Path, result: EvidenceCompilerV3Result, *, suffix: str = "") -> dict[str, str]:
    output = Path(root)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "evidence_packets_v3": output / f"evidence_packets_v3{suffix}.json",
        "code_facts_v1": output / f"code_facts_v1{suffix}.json",
        "atomic_claims_v3": output / f"atomic_claims_v3{suffix}.json",
        "evidence_profile_match": output / f"evidence_profile_match{suffix}.json",
    }
    payloads = {
        "evidence_packets_v3": result.packets.model_dump(mode="json"),
        "code_facts_v1": result.facts.model_dump(mode="json"),
        "atomic_claims_v3": result.claims.model_dump(mode="json"),
        "evidence_profile_match": {
            "profile_id": result.profile_id,
            "profile_match": result.profile_match,
            "repo_snapshot_id": result.packets.repo_snapshot_id,
            "project_tree_hash": result.packets.project_tree_hash,
        },
    }
    for key, path in paths.items():
        path.write_text(
            json.dumps(payloads[key], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return {key: str(path) for key, path in paths.items()}

def load_atomic_claims_v3(path: str | Path) -> AtomicClaimSetV3:
    return AtomicClaimSetV3.model_validate_json(Path(path).read_text(encoding="utf-8"))

def load_evidence_packets_v3(path: str | Path) -> EvidencePacketSetV3:
    return EvidencePacketSetV3.model_validate_json(Path(path).read_text(encoding="utf-8"))

def load_code_facts_v1(path: str | Path) -> CodeFactSetV1:
    return CodeFactSetV1.model_validate_json(Path(path).read_text(encoding="utf-8"))

def migrate_v2_claims_to_v3(v2_payload: dict) -> AtomicClaimSetV3:
    """Convert a V2 atomic-claims payload into an ``AtomicClaimSetV3``.

    The R8 acceptance checker and the V3 coverage builder consume V3
    claims.  Runs that used the legacy V2 evidence pipeline do not
    produce an ``atomic_claims_v3.json`` artifact, so this migrator
    lets the acceptance checker evaluate those runs by converting
    their V2 claims on-the-fly.

    Field mapping (V2 -> V3):

    - ``claim_text`` -> ``canonical_text``
    - ``verdict_status`` -> ``status`` (with ``unsupported_fragment``
      mapping to ``unsupported``)
    - ``direct_evidence_ids`` -> ``direct_evidence_ids`` and ``fact_ids``
    - ``context_evidence_ids`` -> ``relation_evidence_ids``
    - ``allowed_wording_boundary`` -> ``allowed_wording_boundary``
    - ``claim_id`` -> ``claim_id`` and ``canonical_identity``
    - ``covers_obligation_ids`` is set to ``[]`` (V2 does not track
      obligation coverage per claim)

    Claims whose V2 ``verdict_status`` is ``excluded`` are dropped
    (they were not authorized for authoring).
    """

    v2_claims = v2_payload.get("claims", []) or []
    v3_claims: list[AtomicClaimV3] = []
    for v2 in v2_claims:
        verdict = str(v2.get("verdict_status", "")).lower()
        if verdict == "excluded":
            continue
        # Map V2 verdict to V3 status.
        if verdict in {"supported", "unsupported", "code_gap"}:
            status = verdict  # type: ignore[assignment]
        elif verdict in {"partial", "caveated"}:
            status = "partial"  # type: ignore[assignment]
        else:
            status = "unsupported"  # type: ignore[assignment]
        direct_ev = list(v2.get("direct_evidence_ids", []) or [])
        claim_id = str(v2.get("claim_id", f"C{len(v3_claims) + 1}"))
        canonical_text = str(v2.get("claim_text", ""))
        v3_claims.append(
            AtomicClaimV3(
                claim_id=claim_id,
                canonical_text=canonical_text,
                fact_ids=direct_ev,
                covers_obligation_ids=[],
                direct_evidence_ids=direct_ev,
                relation_evidence_ids=list(v2.get("context_evidence_ids", []) or []),
                required_qualifiers=list(v2.get("qualifiers", []) or []),
                unsupported_author_fragments=[
                    v2.get("unsupported_fragment", "")
                ] if v2.get("unsupported_fragment") else [],
                allowed_wording_boundary=str(v2.get("allowed_wording_boundary", canonical_text)),
                canonical_identity=claim_id,
                status=status,
            )
        )
    return AtomicClaimSetV3(
        schema_version="3.0",
        producer_version="code2paper-evidence-compiler-v3-migrated-from-v2",
        repo_snapshot_id=str(v2_payload.get("evidence_snapshot_id", "")),
        project_tree_hash="",
        evidence_packet_digest=str(v2_payload.get("evidence_snapshot_digest", "")),
        code_fact_digest="",
        claims=v3_claims,
        content_digest=str(v2_payload.get("content_digest", "")),
    )

def load_atomic_claims_v3_or_v2(path: str | Path) -> AtomicClaimSetV3:
    """Load an ``AtomicClaimSetV3`` from a V3 or V2 claims file.

    Tries ``AtomicClaimSetV3.model_validate_json`` first; if that
    fails (e.g., the file is a V2 claims file), falls back to
    ``migrate_v2_claims_to_v3``.
    """

    raw = Path(path).read_text(encoding="utf-8")
    try:
        return AtomicClaimSetV3.model_validate_json(raw)
    except Exception:
        pass
    return migrate_v2_claims_to_v3(json.loads(raw))
