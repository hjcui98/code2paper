"""Structure-triggered compiler profile for feature-score pruning pipelines."""

from __future__ import annotations

import re
from pathlib import Path

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    EvidenceCompilerV3Result,
    EvidencePacketSetV3,
    EvidencePacketV3,
    EvidenceSpanV3,
    ExplicitCodeGapV1,
    FactPredicate,
    RejectedEvidenceCandidateV3,
    RelationEvidenceV3,
    SemanticStageGroupV1,
    _SourceIndex,
    _digest,
)
from code2paper.agentic.evidence_profiles.base import ProfileMatch
from code2paper.agentic.repo_snapshot import RepoSnapshot

def _compile_rap_evidence(repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
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
    stage_specs = [
        ("S-V3-1", "Per-primitive feature representation", ["C-RAP-FEATURE-INPUT", "C-RAP-FEATURE-TRANSFORM"]),
        ("S-V3-2", "Predictor loading and score inference", ["C-RAP-PREDICTOR", "C-RAP-SCORE"]),
        ("S-V3-3", "Score-based retention and artifact output", ["C-RAP-RANK", "C-RAP-MASK", "C-RAP-OUTPUT", "C-RAP-INFERENCE-SCOPE"]),
    ]
    claim_by_id = {item.claim_id: item for item in claims}
    stage_groups = [
        SemanticStageGroupV1(
            stage_id=stage_id,
            name=name,
            purpose=" ".join(claim_by_id[item].canonical_text for item in claim_ids if item in claim_by_id),
            ordered_claim_ids=[item for item in claim_ids if item in claim_by_id],
            relation_evidence_ids=_dedupe([
                relation
                for item in claim_ids
                if item in claim_by_id
                for relation in claim_by_id[item].relation_evidence_ids
            ]),
            organization_priority=index,
        )
        for index, (stage_id, name, claim_ids) in enumerate(stage_specs, start=1)
        if any(item in claim_by_id for item in claim_ids)
    ]
    payload = {
        "claims": [item.model_dump(mode="json") for item in claims],
        "explicit_code_gaps": [item.model_dump(mode="json") for item in gaps],
        "semantic_stage_groups": [item.model_dump(mode="json") for item in stage_groups],
    }
    return AtomicClaimSetV3(repo_snapshot_id=packets.repo_snapshot_id, project_tree_hash=packets.project_tree_hash, evidence_packet_digest=packets.content_digest, code_fact_digest=facts.content_digest, claims=claims, explicit_code_gaps=gaps, semantic_stage_groups=stage_groups, content_digest=_digest(payload))

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

def _normalize_object(value: str | list[str]) -> str | list[str]:
    return _normalize_text(value) if isinstance(value, str) else [_normalize_text(item) for item in value]

def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", value.lower()))

def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))

class RapPruningProfile:
    profile_id = "feature_predict_score_rank_filter"

    _required = [
        "pruning_entrypoint",
        "feature_builder",
        "predictor_forward_and_load",
        "descending_score_selection",
        "boolean_mask_filter",
        "artifact_write",
    ]

    def match(self, repo_snapshot: RepoSnapshot) -> ProfileMatch:
        root = Path(repo_snapshot.project_root).resolve()
        index = _SourceIndex(root, repo_snapshot)
        try:
            entrypoint_text = (root / "prune_percent.py").read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            entrypoint_text = ""
        checks = {
            "pruning_entrypoint": index.has("prune_percent.py", "prune_pure_feature"),
            "feature_builder": all((
                index.has("utils/gaussian_model.py", "GaussianModel.get_prune_input_f15"),
                index.has("utils/feature_utils.py", "compute_knn_z_score"),
                index.has("utils/feature_utils.py", "z_score_tensor"),
                index.has("utils/feature_utils.py", "percentile_cutoff_normalize"),
            )),
            "predictor_forward_and_load": all((
                index.has("utils/net_utils.py", "PrunePredictor.__init__"),
                index.has("utils/net_utils.py", "PrunePredictor.forward"),
                index.has("utils/net_utils.py", "PrunePredictor.load_model"),
            )),
            "descending_score_selection": bool(re.search(
                r"argsort\s*\(\s*descending\s*=\s*True", entrypoint_text
            )),
            "boolean_mask_filter": all(re.search(pattern, entrypoint_text) for pattern in (
                r"dtype\s*=\s*torch\.bool", r"prune_points\s*\(",
            )),
            "artifact_write": all(re.search(pattern, entrypoint_text) for pattern in (
                r"save_ply\s*\(", r"np\.save\s*\(",
            )),
        }
        matched_fingerprints = [name for name, passed in checks.items() if passed]
        missing_fingerprints = [name for name, passed in checks.items() if not passed]
        matched = not missing_fingerprints
        return ProfileMatch(
            profile_id=self.profile_id,
            matched=matched,
            required_fingerprints=list(self._required),
            matched_fingerprints=matched_fingerprints,
            missing_required_fingerprints=missing_fingerprints,
            reasons=[
                "required executable symbol and behavior fingerprints matched"
                if matched
                else "one or more executable structure fingerprints were absent"
            ],
        )

    def compile(self, repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
        return _compile_rap_evidence(repo_snapshot)


__all__ = ["RapPruningProfile"]
