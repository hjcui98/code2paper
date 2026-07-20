from __future__ import annotations

import ast
import hashlib
import json
import re
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


class AtomicClaimSetV3(CompilerV3Model):
    schema_version: str = "3.0"
    producer_version: str = "code2paper-evidence-compiler-v3"
    repo_snapshot_id: str
    project_tree_hash: str
    evidence_packet_digest: str
    code_fact_digest: str
    claims: list[AtomicClaimV3]
    explicit_code_gaps: list[ExplicitCodeGapV1] = Field(default_factory=list)
    content_digest: str


class EvidenceCompilerV3Result(CompilerV3Model):
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
        lines = (self.root / path).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
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
    """Compile a typed inference path when the required executable symbols exist.

    This first compiler profile is intentionally behavior-triggered: it activates
    from the symbol graph, never from project name, author prose, or a paper draft.
    """

    root = Path(repo_snapshot.project_root).resolve()
    index = _SourceIndex(root, repo_snapshot)
    required = (
        ("prune_percent.py", "prune_pure_feature"),
        ("utils/gaussian_model.py", "GaussianModel.get_prune_input_f15"),
        ("utils/gaussian_model.py", "GaussianModel.prune_points"),
        ("utils/gaussian_model.py", "GaussianModel.save_ply"),
        ("utils/net_utils.py", "PrunePredictor.__init__"),
        ("utils/net_utils.py", "PrunePredictor.load_model"),
        ("utils/net_utils.py", "PrunePredictor.forward"),
        ("utils/feature_utils.py", "compute_knn_z_score"),
        ("utils/feature_utils.py", "z_score_tensor"),
        ("utils/feature_utils.py", "percentile_cutoff_normalize"),
    )
    if not all(index.has(path, symbol) for path, symbol in required):
        return None
    if not _behavior_contract_satisfied(root):
        return None

    spans = {
        "EV3-FEATURE": index.span("EV3-FEATURE", "utils/gaussian_model.py", "GaussianModel.get_prune_input_f15", "anchor"),
        "EV3-KNN-Z": index.span("EV3-KNN-Z", "utils/feature_utils.py", "compute_knn_z_score", "relation"),
        "EV3-GLOBAL-Z": index.span("EV3-GLOBAL-Z", "utils/feature_utils.py", "z_score_tensor", "relation"),
        "EV3-PERCENTILE": index.span("EV3-PERCENTILE", "utils/feature_utils.py", "percentile_cutoff_normalize", "relation"),
        "EV3-PREDICTOR-INIT": index.span("EV3-PREDICTOR-INIT", "utils/net_utils.py", "PrunePredictor.__init__", "anchor"),
        "EV3-PREDICTOR-LOAD": index.span("EV3-PREDICTOR-LOAD", "utils/net_utils.py", "PrunePredictor.load_model", "relation"),
        "EV3-PREDICTOR-FORWARD": index.span("EV3-PREDICTOR-FORWARD", "utils/net_utils.py", "PrunePredictor.forward", "relation"),
        "EV3-PRUNE-MAIN": index.span("EV3-PRUNE-MAIN", "prune_percent.py", "prune_pure_feature", "anchor"),
        "EV3-PRUNE-POINTS": index.span("EV3-PRUNE-POINTS", "utils/gaussian_model.py", "GaussianModel.prune_points", "relation"),
        "EV3-SAVE-PLY": index.span("EV3-SAVE-PLY", "utils/gaussian_model.py", "GaussianModel.save_ply", "relation"),
    }

    feature_relations = [
        RelationEvidenceV3(relation_id="RV3-FEATURE-KNN", relation_type="call_flow", source_symbol="GaussianModel.get_prune_input_f15", target_symbol="compute_knn_z_score", direct_span_ids=["EV3-FEATURE", "EV3-KNN-Z"], statement="Feature construction invokes local KNN z-score transforms."),
        RelationEvidenceV3(relation_id="RV3-FEATURE-Z", relation_type="call_flow", source_symbol="GaussianModel.get_prune_input_f15", target_symbol="z_score_tensor", direct_span_ids=["EV3-FEATURE", "EV3-GLOBAL-Z"], statement="Feature construction invokes global z-score transforms."),
        RelationEvidenceV3(relation_id="RV3-FEATURE-NORM", relation_type="data_flow", source_symbol="input_features", target_symbol="percentile_cutoff_normalize", direct_span_ids=["EV3-FEATURE", "EV3-PERCENTILE"], statement="The concatenated feature tensor is percentile-clipped and rescaled."),
    ]
    predictor_relations = [
        RelationEvidenceV3(relation_id="RV3-PREDICTOR-FORWARD", relation_type="data_flow", source_symbol="PrunePredictor.forward", target_symbol="PrunePredictor.model", direct_span_ids=["EV3-PREDICTOR-INIT", "EV3-PREDICTOR-FORWARD"], statement="The forward method returns the sequential MLP output."),
        RelationEvidenceV3(relation_id="RV3-PREDICTOR-LOAD", relation_type="data_flow", source_symbol="net_weights_path", target_symbol="PrunePredictor.load_model", direct_span_ids=["EV3-PREDICTOR-LOAD", "EV3-PRUNE-MAIN"], statement="The inference entrypoint loads the predictor state dictionary from net_weights_path."),
    ]
    prune_relations = [
        RelationEvidenceV3(relation_id="RV3-MAINLINE", relation_type="control_flow", source_symbol="prune_pure_feature", target_symbol="GaussianModel.prune_points", direct_span_ids=["EV3-PRUNE-MAIN", "EV3-PRUNE-POINTS"], statement="The entrypoint scores, ranks, masks, and then filters Gaussian tensors."),
        RelationEvidenceV3(relation_id="RV3-WRITE-PLY", relation_type="writes", source_symbol="prune_pure_feature", target_symbol="GaussianModel.save_ply", direct_span_ids=["EV3-PRUNE-MAIN", "EV3-SAVE-PLY"], statement="The filtered Gaussian tensors are serialized to the requested PLY path."),
        RelationEvidenceV3(relation_id="RV3-WRITE-SCORES", relation_type="writes", source_symbol="scores", target_symbol="score_path", direct_span_ids=["EV3-PRUNE-MAIN"], statement="The predictor scores are saved as a NumPy array beside the PLY output."),
    ]

    rejected = [
        RejectedEvidenceCandidateV3(
            path="utils/feature_utils.py",
            symbol=symbol,
            reason="wrong_span_role: this helper supports only the SH anisotropy sub-feature and cannot independently support complete attribute reading, KNN statistics, concatenation, or normalization.",
            allowed_scope="SH color anisotropy sub-feature only",
        )
        for symbol in ("compute_sh_anisotropy_loop", "compute_sh_anisotropy_loop_std")
    ]
    packets = [
        _packet("EP-RAP-FEATURE", "utils/gaussian_model.py:GaussianModel.get_prune_input_f15", [spans[x] for x in ("EV3-FEATURE", "EV3-KNN-Z", "EV3-GLOBAL-Z", "EV3-PERCENTILE")], ["EV3-FEATURE"], ["EV3-KNN-Z", "EV3-GLOBAL-Z", "EV3-PERCENTILE"], feature_relations, ["KNN backend must be available for the selected knn_method"], "Four spans are necessary: the anchor establishes attribute reads and tensor construction, while three distinct helpers establish local z-score, global z-score, and percentile clipping/rescaling semantics.", rejected),
        _packet("EP-RAP-PREDICTOR", "utils/net_utils.py:PrunePredictor", [spans[x] for x in ("EV3-PREDICTOR-INIT", "EV3-PREDICTOR-LOAD", "EV3-PREDICTOR-FORWARD")], ["EV3-PREDICTOR-INIT"], ["EV3-PREDICTOR-LOAD", "EV3-PREDICTOR-FORWARD"], predictor_relations, ["use_softmax retains its default true value in prune_pure_feature"], "", []),
        _packet("EP-RAP-PRUNE", "prune_percent.py:prune_pure_feature", [spans[x] for x in ("EV3-PRUNE-MAIN", "EV3-PRUNE-POINTS", "EV3-SAVE-PLY")], ["EV3-PRUNE-MAIN"], ["EV3-PRUNE-POINTS", "EV3-SAVE-PLY"], prune_relations, ["0 <= keep_percent <= 1 is expected by the slicing logic"], "", []),
    ]
    packet_payload = [item.model_dump(mode="json") for item in packets]
    packet_set = EvidencePacketSetV3(repo_snapshot_id=repo_snapshot.snapshot_id, project_tree_hash=repo_snapshot.project_tree_hash, packets=packets, content_digest=_digest(packet_payload))

    facts = _compile_facts(packet_set)
    claims = _compile_claims(packet_set, facts)
    return EvidenceCompilerV3Result(packets=packet_set, facts=facts, claims=claims)


def _packet(packet_id: str, scope: str, spans: list[EvidenceSpanV3], anchors: list[str], relations_ids: list[str], relations: list[RelationEvidenceV3], conditions: list[str], rationale: str, rejected: list[RejectedEvidenceCandidateV3]) -> EvidencePacketV3:
    source_digest = _digest([span.excerpt_digest for span in spans])
    return EvidencePacketV3(packet_id=packet_id, obligation_tags=[], scope=scope, anchor_span_ids=anchors, relation_span_ids=relations_ids, spans=spans, relations=relations, conditions=conditions, composition_rationale=rationale, rejected_candidates=rejected, source_digest=source_digest)


def _compile_facts(packets: EvidencePacketSetV3) -> CodeFactSetV1:
    by_packet = {item.packet_id: item for item in packets.packets}
    span_by_id = {span.span_id: span for packet in packets.packets for span in packet.spans}
    specs: list[tuple[str, str, FactPredicate, str | list[str], str, list[str], list[str], list[str], list[str]]] = [
        ("F-RAP-FEATURE-READS", "GaussianModel.get_prune_input_f15", "reads", ["position", "opacity", "scale", "SH coefficients", "DC color"], "utils/gaussian_model.py:GaussianModel.get_prune_input_f15", ["EV3-FEATURE"], [], [], []),
        ("F-RAP-FEATURE-TRANSFORMS", "GaussianModel.get_prune_input_f15", "transforms", ["KNN distance statistics", "local KNN z-scores", "global log z-scores", "sorted scales", "scale volume", "SH anisotropy", "percentile clipping and rescaling"], "utils/gaussian_model.py:GaussianModel.get_prune_input_f15", ["EV3-FEATURE"], ["EV3-KNN-Z", "EV3-GLOBAL-Z", "EV3-PERCENTILE"], ["RV3-FEATURE-KNN", "RV3-FEATURE-Z", "RV3-FEATURE-NORM"], []),
        ("F-RAP-FEATURE-CONSTRUCTS", "GaussianModel.get_prune_input_f15", "constructs", "normalized per-primitive feature tensor stored in prune_features", "utils/gaussian_model.py:GaussianModel.get_prune_input_f15", ["EV3-FEATURE"], ["EV3-PERCENTILE"], ["RV3-FEATURE-NORM"], []),
        ("F-RAP-PREDICTOR-CONSTRUCTS", "PrunePredictor.__init__", "constructs", "feed-forward MLP ending in two logits and Softmax(dim=1)", "utils/net_utils.py:PrunePredictor.__init__", ["EV3-PREDICTOR-INIT"], [], [], ["use_softmax=True"]),
        ("F-RAP-PREDICTOR-LOADS", "prune_pure_feature", "loads_weights", "net_weights_path -> PrunePredictor.load_model", "prune_percent.py:prune_pure_feature", ["EV3-PRUNE-MAIN", "EV3-PREDICTOR-LOAD"], [], ["RV3-PREDICTOR-LOAD"], []),
        ("F-RAP-SCORE-SELECTS", "prune_pure_feature", "selects_column", "PrunePredictor output[:, 0] as the per-primitive score", "prune_percent.py:prune_pure_feature", ["EV3-PRUNE-MAIN", "EV3-PREDICTOR-FORWARD"], [], ["RV3-PREDICTOR-FORWARD"], ["predictor evaluation runs under torch.no_grad"]),
        ("F-RAP-SORT", "prune_pure_feature", "sorts_by", "scores.argsort(descending=True)", "prune_percent.py:prune_pure_feature", ["EV3-PRUNE-MAIN"], [], [], []),
        ("F-RAP-TOPK", "prune_pure_feature", "selects_top_k", "first int(N * keep_percent) descending-score indices", "prune_percent.py:prune_pure_feature", ["EV3-PRUNE-MAIN"], [], [], []),
        ("F-RAP-MASK", "prune_pure_feature", "constructs_mask", "boolean valid_mask with selected indices set true", "prune_percent.py:prune_pure_feature", ["EV3-PRUNE-MAIN"], [], [], []),
        ("F-RAP-FILTER", "GaussianModel.prune_points", "filters_by", ["xyz", "DC features", "remaining SH features", "scale", "rotation", "opacity"], "utils/gaussian_model.py:GaussianModel.prune_points", ["EV3-PRUNE-POINTS"], [], ["RV3-MAINLINE"], ["valid_mask is true for retained primitives"]),
        ("F-RAP-WRITES", "prune_pure_feature", "writes_artifact", ["pruned PLY at output_ply_path", "score NPY derived from output_ply_path"], "prune_percent.py:prune_pure_feature", ["EV3-PRUNE-MAIN", "EV3-SAVE-PLY"], [], ["RV3-WRITE-PLY", "RV3-WRITE-SCORES"], []),
        ("F-RAP-MAINLINE", "prune_pure_feature", "calls_in_order", ["load PLY", "construct features", "construct predictor", "load checkpoint", "forward predictor", "select score column 0", "sort descending", "select top retention count", "construct boolean mask", "filter Gaussian tensors", "save PLY", "save scores"], "prune_percent.py:prune_pure_feature", ["EV3-PRUNE-MAIN"], ["EV3-FEATURE", "EV3-PREDICTOR-INIT", "EV3-PREDICTOR-LOAD", "EV3-PREDICTOR-FORWARD", "EV3-PRUNE-POINTS", "EV3-SAVE-PLY"], ["RV3-MAINLINE", "RV3-PREDICTOR-LOAD", "RV3-PREDICTOR-FORWARD", "RV3-WRITE-PLY", "RV3-WRITE-SCORES"], []),
        ("F-RAP-NO-RENDER", "prune_pure_feature", "does_not_call", ["renderer", "training loop", "optimizer"], "prune_percent.py:prune_pure_feature", ["EV3-PRUNE-MAIN"], [], [], ["function-scoped absence only"]),
    ]
    facts: list[CodeFactV1] = []
    seen: set[str] = set()
    for fact_id, subject, predicate, obj, scope, direct, relation_spans, relation_ids, conditions in specs:
        identity_payload = {"snapshot": packets.repo_snapshot_id, "scope": scope, "subject": subject, "predicate": predicate, "object": _normalize_object(obj), "conditions": sorted(conditions)}
        identity = _digest(identity_payload)
        if identity in seen:
            continue
        seen.add(identity)
        referenced = direct + relation_spans
        failures = [f"unknown_span:{item}" for item in referenced if item not in span_by_id]
        if predicate == "does_not_call":
            scoped_text = "\n".join(span_by_id[item].exact_excerpt for item in direct if item in span_by_id)
            if re.search(r"\b(?:render\w*|train\w*|optimizer\w*)\s*\(", scoped_text, flags=re.IGNORECASE):
                failures.append("scoped_absence_certificate_violated")
        exact_digest = _digest([span_by_id[item].excerpt_digest for item in referenced if item in span_by_id])
        facts.append(CodeFactV1(fact_id=fact_id, subject=subject, predicate=predicate, object=obj, conditions=conditions, scope=scope, direct_span_ids=direct, relation_span_ids=relation_spans, relation_evidence_ids=relation_ids, exact_source_digest=exact_digest, canonical_identity=identity, validation_status="rejected" if failures else "supported", validation_failures=failures))
    payload = [item.model_dump(mode="json") for item in facts]
    return CodeFactSetV1(repo_snapshot_id=packets.repo_snapshot_id, project_tree_hash=packets.project_tree_hash, evidence_packet_digest=packets.content_digest, facts=facts, content_digest=_digest(payload))


def _compile_claims(packets: EvidencePacketSetV3, facts: CodeFactSetV1) -> AtomicClaimSetV3:
    fact_by_id = {item.fact_id: item for item in facts.facts if item.validation_status == "supported"}
    specs = [
        ("C-RAP-FEATURE-INPUT", "The feature builder reads each Gaussian's position, activated opacity and scale, spherical-harmonic coefficients, and DC color.", ["F-RAP-FEATURE-READS"], []),
        ("C-RAP-FEATURE-TRANSFORM", "It derives KNN distance statistics, local and global z-scores, sorted-scale and volume descriptors, and SH anisotropy before percentile-clipping and rescaling the concatenated features.", ["F-RAP-FEATURE-TRANSFORMS", "F-RAP-FEATURE-CONSTRUCTS"], []),
        ("C-RAP-PREDICTOR", "The inference path constructs a feed-forward predictor whose final two logits are converted by a Softmax over the class dimension, then loads its state dictionary from net_weights_path.", ["F-RAP-PREDICTOR-CONSTRUCTS", "F-RAP-PREDICTOR-LOADS"], ["in the provided inference entrypoint"]),
        ("C-RAP-SCORE", "Under no-gradient evaluation, the predictor consumes the per-primitive feature tensor and column zero of its two-class output is used as the importance score.", ["F-RAP-SCORE-SELECTS"], ["under torch.no_grad"]),
        ("C-RAP-RANK", "The entrypoint computes a retention count as int(N * keep_percent), sorts scores in descending order, and keeps the leading indices.", ["F-RAP-SORT", "F-RAP-TOPK"], []),
        ("C-RAP-MASK", "A boolean mask marks the retained indices, and prune_points applies that mask consistently to positions, color features, scales, rotations, and opacities.", ["F-RAP-MASK", "F-RAP-FILTER"], []),
        ("C-RAP-OUTPUT", "Finally, the filtered Gaussians are written to output_ply_path and the score vector is saved to a neighboring NumPy file.", ["F-RAP-WRITES"], []),
        ("C-RAP-INFERENCE-SCOPE", "Within the provided prune_pure_feature entrypoint, this feature-to-score-to-prune path does not invoke a renderer, training loop, or optimizer.", ["F-RAP-NO-RENDER"], ["within the provided prune_pure_feature entrypoint"]),
    ]
    claims: list[AtomicClaimV3] = []
    seen: set[str] = set()
    for claim_id, text, fact_ids, qualifiers in specs:
        selected = [fact_by_id[item] for item in fact_ids if item in fact_by_id]
        if len(selected) != len(fact_ids):
            continue
        identity = _digest({"behavior": _normalize_text(text), "fact_ids": sorted(fact_ids)})
        if identity in seen:
            continue
        seen.add(identity)
        claims.append(AtomicClaimV3(claim_id=claim_id, canonical_text=text, fact_ids=fact_ids, direct_evidence_ids=_dedupe([span for fact in selected for span in fact.direct_span_ids]), relation_evidence_ids=_dedupe([relation for fact in selected for relation in fact.relation_evidence_ids]), required_qualifiers=qualifiers, allowed_wording_boundary=text, canonical_identity=identity))
    gaps = [
        ExplicitCodeGapV1(gap_id="GAP-RAP-TRAINING", topic="training program and DL3DV-10K training data", scope="provided executable repository", rationale="No executable training entrypoint or dataset binding is present in the compiled inference scope."),
        ExplicitCodeGapV1(gap_id="GAP-RAP-SOFT-PRUNING", topic="soft pruning", scope="provided executable repository", rationale="The executable path constructs a hard boolean retention mask; narrative soft-pruning language is not direct implementation evidence."),
        ExplicitCodeGapV1(gap_id="GAP-RAP-LOSSES", topic="three-loss and entropy objectives", scope="provided executable repository", rationale="No executable loss or entropy-training definition is present in the compiled inference scope."),
    ]
    payload = {"claims": [item.model_dump(mode="json") for item in claims], "explicit_code_gaps": [item.model_dump(mode="json") for item in gaps]}
    return AtomicClaimSetV3(repo_snapshot_id=packets.repo_snapshot_id, project_tree_hash=packets.project_tree_hash, evidence_packet_digest=packets.content_digest, code_fact_digest=facts.content_digest, claims=claims, explicit_code_gaps=gaps, content_digest=_digest(payload))


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
        if packet.packet_id == "EP-RAP-FEATURE" and packet.anchor_span_ids != ["EV3-FEATURE"]:
            failures.append("wrong_span_role:feature_anchor")
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
    }
    models = {"evidence_packets_v3": result.packets, "code_facts_v1": result.facts, "atomic_claims_v3": result.claims}
    for key, path in paths.items():
        path.write_text(json.dumps(models[key].model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    import json
    return migrate_v2_claims_to_v3(json.loads(raw))


def _normalize_object(value: str | list[str]) -> str | list[str]:
    return _normalize_text(value) if isinstance(value, str) else [_normalize_text(item) for item in value]


def _behavior_contract_satisfied(root: Path) -> bool:
    """Reject same-name symbols that do not implement the typed predicates."""

    required_patterns = {
        "prune_percent.py": (
            r"get_prune_input_f15\s*\(", r"load_model\s*\(", r"\[:,\s*0\]",
            r"argsort\s*\(\s*descending\s*=\s*True", r"keep_num\s*=\s*int\s*\(",
            r"dtype\s*=\s*torch\.bool", r"prune_points\s*\(", r"save_ply\s*\(", r"np\.save\s*\(",
        ),
        "utils/gaussian_model.py": (
            r"positions\s*=\s*self\.get_xyz", r"opacities\s*=\s*self\.get_opacity",
            r"scales\s*=\s*self\.get_scaling", r"shs_dc\s*=\s*self\.get_features_dc",
            r"compute_knn_z_score\s*\(", r"z_score_tensor\s*\(", r"torch\.sort\s*\(",
            r"torch\.prod\s*\(", r"torch\.cat\s*\(", r"percentile_cutoff_normalize\s*\(",
            r"self\._xyz\s*=\s*self\._xyz\[valid_mask\]", r"PlyData\s*\(\[el\]\)\.write\s*\(",
        ),
        "utils/net_utils.py": (
            r"nn\.Linear\s*\(", r"nn\.Linear\s*\([^\n]*,\s*2\s*\)",
            r"nn\.Softmax\s*\(\s*dim\s*=\s*1", r"return\s+self\.model\s*\(",
            r"load_state_dict\s*\(\s*torch\.load\s*\(",
        ),
    }
    for relative, patterns in required_patterns.items():
        try:
            text = (root / relative).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        if not all(re.search(pattern, text) for pattern in patterns):
            return False
    return True


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", value.lower()))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))
