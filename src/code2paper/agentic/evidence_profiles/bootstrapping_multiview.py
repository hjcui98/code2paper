"""Structure-triggered compiler profile for Bootstrapping Multi-view Learning (TNC)."""

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


def _compile_bootstrapping_evidence(repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
    """Compile evidence for Bootstrapping Multi-view Learning against TNC."""

    root = Path(repo_snapshot.project_root).resolve()
    index = _SourceIndex(root, repo_snapshot)
    required = (
        ("multi_view.py", "NC_MultiViewDataset.__init__"),
        ("multi_view.py", "NC_MultiViewDataset.NoiseCorrespondence_inject"),
        ("multi_view.py", "ReliabilityEstimator.__init__"),
        ("multi_view.py", "ReliabilityEstimator._build_router_mlps"),
        ("multi_view.py", "ReliabilityEstimator._compute_entropy"),
        ("multi_view.py", "ReliabilityEstimator._compute_pairwise_agreement"),
        ("multi_view.py", "ReliabilityEstimator._compute_reliability_features"),
        ("multi_view.py", "ReliabilityEstimator._router_forward"),
        ("multi_view.py", "ReliabilityEstimator._finalize_forward"),
        ("multi_view.py", "MultiViewBackbone.__init__"),
        ("multi_view.py", "MultiViewBackbone.forward"),
        ("multi_view.py", "train_one_seed"),
        ("multi_view.py", "load_multiviewdata"),
    )
    if not all(index.has(path, symbol) for path, symbol in required):
        return None
    if not _behavior_contract_satisfied(root):
        return None

    spans = {
        "EV3-BML-DATASET-INIT": index.span("EV3-BML-DATASET-INIT", "multi_view.py", "NC_MultiViewDataset.__init__", "anchor"),
        "EV3-BML-NOISE-INJECT": index.span("EV3-BML-NOISE-INJECT", "multi_view.py", "NC_MultiViewDataset.NoiseCorrespondence_inject", "relation"),
        "EV3-BML-REL-INIT": index.span("EV3-BML-REL-INIT", "multi_view.py", "ReliabilityEstimator.__init__", "anchor"),
        "EV3-BML-ROUTER-MLPS": index.span("EV3-BML-ROUTER-MLPS", "multi_view.py", "ReliabilityEstimator._build_router_mlps", "relation"),
        "EV3-BML-ENTROPY": index.span("EV3-BML-ENTROPY", "multi_view.py", "ReliabilityEstimator._compute_entropy", "relation"),
        "EV3-BML-AGREEMENT": index.span("EV3-BML-AGREEMENT", "multi_view.py", "ReliabilityEstimator._compute_pairwise_agreement", "relation"),
        "EV3-BML-REL-FEATURES": index.span("EV3-BML-REL-FEATURES", "multi_view.py", "ReliabilityEstimator._compute_reliability_features", "relation"),
        "EV3-BML-ROUTER-FWD": index.span("EV3-BML-ROUTER-FWD", "multi_view.py", "ReliabilityEstimator._router_forward", "relation"),
        "EV3-BML-FINALIZE-FWD": index.span("EV3-BML-FINALIZE-FWD", "multi_view.py", "ReliabilityEstimator._finalize_forward", "anchor"),
        "EV3-BML-BACKBONE-INIT": index.span("EV3-BML-BACKBONE-INIT", "multi_view.py", "MultiViewBackbone.__init__", "anchor"),
        "EV3-BML-BACKBONE-FWD": index.span("EV3-BML-BACKBONE-FWD", "multi_view.py", "MultiViewBackbone.forward", "relation"),
        "EV3-BML-TRAIN": index.span("EV3-BML-TRAIN", "multi_view.py", "train_one_seed", "anchor"),
        "EV3-BML-LOAD-DATA": index.span("EV3-BML-LOAD-DATA", "multi_view.py", "load_multiviewdata", "anchor"),
    }

    noise_relations = [
        RelationEvidenceV3(
            relation_id="RV3-BML-NOISE-FLOW",
            relation_type="call_flow",
            source_symbol="NC_MultiViewDataset.__init__",
            target_symbol="NC_MultiViewDataset.NoiseCorrespondence_inject",
            direct_span_ids=["EV3-BML-DATASET-INIT", "EV3-BML-NOISE-INJECT"],
            statement="Dataset construction invokes on-the-fly noise injection per epoch.",
        ),
    ]

    reliability_relations = [
        RelationEvidenceV3(
            relation_id="RV3-BML-ENTROPY-FLOW",
            relation_type="call_flow",
            source_symbol="ReliabilityEstimator._compute_reliability_features",
            target_symbol="ReliabilityEstimator._compute_entropy",
            direct_span_ids=["EV3-BML-REL-FEATURES", "EV3-BML-ENTROPY"],
            statement="Reliability features include per-view intra-view uncertainty (normalized Shannon entropy).",
        ),
        RelationEvidenceV3(
            relation_id="RV3-BML-AGREEMENT-FLOW",
            relation_type="call_flow",
            source_symbol="ReliabilityEstimator._compute_reliability_features",
            target_symbol="ReliabilityEstimator._compute_pairwise_agreement",
            direct_span_ids=["EV3-BML-REL-FEATURES", "EV3-BML-AGREEMENT"],
            statement="Reliability features include inter-view discrepancy (Jeffreys divergence between predictions).",
        ),
        RelationEvidenceV3(
            relation_id="RV3-BML-ROUTER-FLOW",
            relation_type="call_flow",
            source_symbol="ReliabilityEstimator._router_forward",
            target_symbol="ReliabilityEstimator._build_router_mlps",
            direct_span_ids=["EV3-BML-ROUTER-FWD", "EV3-BML-ROUTER-MLPS"],
            statement="The router MLPs (one per view) map features+reliability signals to per-view weights via sigmoid.",
        ),
    ]

    finalize_relations = [
        RelationEvidenceV3(
            relation_id="RV3-BML-FINALIZE-RELIABILITY",
            relation_type="call_flow",
            source_symbol="ReliabilityEstimator._finalize_forward",
            target_symbol="ReliabilityEstimator._compute_reliability_features",
            direct_span_ids=["EV3-BML-FINALIZE-FWD", "EV3-BML-REL-FEATURES"],
            statement="Weighted fusion first computes per-view reliability features (entropy + agreement signals).",
        ),
        RelationEvidenceV3(
            relation_id="RV3-BML-FINALIZE-ROUTER",
            relation_type="call_flow",
            source_symbol="ReliabilityEstimator._finalize_forward",
            target_symbol="ReliabilityEstimator._router_forward",
            direct_span_ids=["EV3-BML-FINALIZE-FWD", "EV3-BML-ROUTER-FWD"],
            statement="Weighted fusion passes features+reliability signals through per-view router MLPs to get scalar reliability weights.",
        ),
    ]

    backbone_relations = [
        RelationEvidenceV3(
            relation_id="RV3-BML-BACKBONE-FINALIZE",
            relation_type="call_flow",
            source_symbol="MultiViewBackbone.forward",
            target_symbol="ReliabilityEstimator._finalize_forward",
            direct_span_ids=["EV3-BML-BACKBONE-FWD", "EV3-BML-FINALIZE-FWD"],
            statement="Backbone forward delegates to _finalize_forward for reliability-weighted fusion of per-view logits.",
        ),
        RelationEvidenceV3(
            relation_id="RV3-BML-TRAIN-FLOW",
            relation_type="control_flow",
            source_symbol="train_one_seed",
            target_symbol="MultiViewBackbone.forward",
            direct_span_ids=["EV3-BML-TRAIN", "EV3-BML-BACKBONE-FWD"],
            statement="Training loop calls backbone forward, then computes classification loss and BCE alignment loss.",
        ),
    ]

    data_relations = [
        RelationEvidenceV3(
            relation_id="RV3-BML-DATA-FLOW",
            relation_type="data_flow",
            source_symbol="load_multiviewdata",
            target_symbol="NC_MultiViewDataset.__init__",
            direct_span_ids=["EV3-BML-LOAD-DATA", "EV3-BML-DATASET-INIT"],
            statement="Multi-view data is loaded from .mat files, normalized, and fed into the noise-injecting dataset.",
        ),
    ]

    packets = [
        _packet(
            "EP-BML-DATA",
            "multi_view.py:NC_MultiViewDataset, load_multiviewdata",
            [spans[x] for x in ("EV3-BML-DATASET-INIT", "EV3-BML-NOISE-INJECT", "EV3-BML-LOAD-DATA")],
            ["EV3-BML-DATASET-INIT", "EV3-BML-LOAD-DATA"],
            ["EV3-BML-NOISE-INJECT"],
            noise_relations + data_relations,
            ["noise_ratio controls the proportion of corrupted instances; at least ceil(M/2) views are kept clean"],
            "Three spans establish the data pipeline: multi-view data is loaded and normalized, then noise injection randomly corrupts a subset of views per epoch with recorded corruption masks.",
            [],
        ),
        _packet(
            "EP-BML-RELIABILITY",
            "multi_view.py:ReliabilityEstimator",
            [spans[x] for x in ("EV3-BML-REL-INIT", "EV3-BML-ROUTER-MLPS", "EV3-BML-ENTROPY", "EV3-BML-AGREEMENT", "EV3-BML-REL-FEATURES", "EV3-BML-ROUTER-FWD")],
            ["EV3-BML-REL-INIT"],
            ["EV3-BML-ROUTER-MLPS", "EV3-BML-ENTROPY", "EV3-BML-AGREEMENT", "EV3-BML-REL-FEATURES", "EV3-BML-ROUTER-FWD"],
            reliability_relations,
            ["the reliability estimator uses per-view MLPs with sigmoid output in (0,1)"],
            "Six spans establish the reliability estimation mechanism: entropy-based intra-view uncertainty, Jeffreys divergence for inter-view discrepancy, and lightweight MLP router producing per-view reliability weights.",
            [],
        ),
        _packet(
            "EP-BML-BACKBONE",
            "multi_view.py:MultiViewBackbone, ReliabilityEstimator._finalize_forward",
            [spans[x] for x in ("EV3-BML-BACKBONE-INIT", "EV3-BML-BACKBONE-FWD", "EV3-BML-FINALIZE-FWD")],
            ["EV3-BML-BACKBONE-INIT", "EV3-BML-FINALIZE-FWD"],
            ["EV3-BML-BACKBONE-FWD"],
            backbone_relations + finalize_relations,
            ["MultiViewBackbone inherits ReliabilityEstimator and adds per-view encoder-classifier pairs", "weighted fusion uses torch.stack(dim=1), reliability.unsqueeze(-1) * logits_stack, sum(dim=1)"],
            "Three spans establish the backbone: per-view encoders extract features, classifiers produce logits, and _finalize_forward performs reliability-weighted fusion via torch.stack + weighted sum reduction.",
            [],
        ),
        _packet(
            "EP-BML-TRAINING",
            "multi_view.py:train_one_seed",
            [spans[x] for x in ("EV3-BML-TRAIN",)],
            ["EV3-BML-TRAIN"],
            [],
            [],
            ["training uses Adam optimizer with CosineAnnealingLR", "joint loss = classification CE + lambda_w * BCE alignment"],
            "One span establishes the training loop: per-epoch noise injection, forward pass through backbone, joint optimization of classification and reliability alignment losses.",
            [],
        ),
    ]
    packet_payload = [item.model_dump(mode="json") for item in packets]
    packet_set = EvidencePacketSetV3(
        repo_snapshot_id=repo_snapshot.snapshot_id,
        project_tree_hash=repo_snapshot.project_tree_hash,
        packets=packets,
        content_digest=_digest(packet_payload),
    )

    facts = _compile_facts(packet_set)
    claims = _compile_claims(packet_set, facts)
    return EvidenceCompilerV3Result(packets=packet_set, facts=facts, claims=claims)


def _packet(
    packet_id: str,
    scope: str,
    spans: list[EvidenceSpanV3],
    anchors: list[str],
    relations_ids: list[str],
    relations: list[RelationEvidenceV3],
    conditions: list[str],
    rationale: str,
    rejected: list[RejectedEvidenceCandidateV3],
) -> EvidencePacketV3:
    source_digest = _digest([span.excerpt_digest for span in spans])
    return EvidencePacketV3(
        packet_id=packet_id,
        obligation_tags=[],
        scope=scope,
        anchor_span_ids=anchors,
        relation_span_ids=relations_ids,
        spans=spans,
        relations=relations,
        conditions=conditions,
        composition_rationale=rationale,
        rejected_candidates=rejected,
        source_digest=source_digest,
    )


def _compile_facts(packets: EvidencePacketSetV3) -> CodeFactSetV1:
    span_by_id = {span.span_id: span for packet in packets.packets for span in packet.spans}
    specs: list[tuple[str, str, FactPredicate, str | list[str], str, list[str], list[str], list[str], list[str]]] = [
        ("F-BML-DATA-LOAD", "load_multiviewdata", "reads", ["multi-view .mat files", "extracts per-view data matrices", "normalizes via minmax_scale"], "multi_view.py:load_multiviewdata", ["EV3-BML-LOAD-DATA"], [], [], []),
        ("F-BML-NOISE-INJECT", "NC_MultiViewDataset.NoiseCorrespondence_inject", "implements", "on-the-fly TNC bootstrapping: samples noise_ratio instances, corrupts up to floor(M/2) views by shuffling with other instances, records per-view corruption mask", "multi_view.py:NC_MultiViewDataset.NoiseCorrespondence_inject", ["EV3-BML-NOISE-INJECT"], [], [], []),
        ("F-BML-NOISE-MASK", "NC_MultiViewDataset.NoiseCorrespondence_inject", "constructs_mask", "per-view noise_indicator mask (1=clean, 0=corrupted) recording which views were shuffled", "multi_view.py:NC_MultiViewDataset.NoiseCorrespondence_inject", ["EV3-BML-NOISE-INJECT"], [], [], []),
        ("F-BML-NOISE-SELECT", "NC_MultiViewDataset.NoiseCorrespondence_inject", "selects", "instances to corrupt via noise_ratio threshold and views to corrupt via floor(M/2) random selection", "multi_view.py:NC_MultiViewDataset.NoiseCorrespondence_inject", ["EV3-BML-NOISE-INJECT"], [], [], []),
        ("F-BML-DATASET-CONSTRUCT", "NC_MultiViewDataset.__init__", "calls", "NoiseCorrespondence_inject with noise_ratio and noise_seed to build per-epoch augmented dataset", "multi_view.py:NC_MultiViewDataset.__init__", ["EV3-BML-DATASET-INIT"], ["EV3-BML-NOISE-INJECT"], ["RV3-BML-NOISE-FLOW"], []),
        ("F-BML-ENTROPY", "ReliabilityEstimator._compute_entropy", "computes", "normalized Shannon entropy of per-view predictions as intra-view uncertainty Q_i", "multi_view.py:ReliabilityEstimator._compute_entropy", ["EV3-BML-ENTROPY"], [], [], []),
        ("F-BML-AGREEMENT", "ReliabilityEstimator._compute_pairwise_agreement", "computes", "averaged symmetric KL divergence (Jeffreys divergence) between a view's prediction and others as inter-view discrepancy J_i", "multi_view.py:ReliabilityEstimator._compute_pairwise_agreement", ["EV3-BML-AGREEMENT"], [], [], []),
        ("F-BML-REL-FEATURES", "ReliabilityEstimator._compute_reliability_features", "constructs", "per-view reliability features by concatenating entropy Q_i and disagreement J_i", "multi_view.py:ReliabilityEstimator._compute_reliability_features", ["EV3-BML-REL-FEATURES"], ["EV3-BML-ENTROPY", "EV3-BML-AGREEMENT"], ["RV3-BML-ENTROPY-FLOW", "RV3-BML-AGREEMENT-FLOW"], []),
        ("F-BML-ROUTER", "ReliabilityEstimator._build_router_mlps", "constructs", "per-view lightweight MLPs (Linear-ReLU-Linear-Sigmoid) mapping feat_dim+2 to scalar reliability in (0,1)", "multi_view.py:ReliabilityEstimator._build_router_mlps", ["EV3-BML-ROUTER-MLPS"], [], [], []),
        ("F-BML-ROUTER-FWD", "ReliabilityEstimator._router_forward", "computes", "per-view reliability weight alpha_i via concatenating view features with reliability features and passing through router MLP", "multi_view.py:ReliabilityEstimator._router_forward", ["EV3-BML-ROUTER-FWD"], ["EV3-BML-ROUTER-MLPS"], ["RV3-BML-ROUTER-FLOW"], []),
        ("F-BML-FINALIZE-FWD", "ReliabilityEstimator._finalize_forward", "calls_in_order", ["call _compute_reliability_features to get entropy+agreement signals", "call _router_forward to get per-view reliability weights", "stack logits via torch.stack(logits_list, dim=1)", "multiply reliability weights via reliabilities.unsqueeze(-1) * logits_stack", "reduce via sum(dim=1) to produce fused_logits", "return (logits_list, fused_logits, reliabilities)"], "multi_view.py:ReliabilityEstimator._finalize_forward", ["EV3-BML-FINALIZE-FWD"], ["EV3-BML-REL-FEATURES", "EV3-BML-ROUTER-FWD"], ["RV3-BML-FINALIZE-RELIABILITY", "RV3-BML-FINALIZE-ROUTER"], []),
        ("F-BML-STACK", "ReliabilityEstimator._finalize_forward", "stacks", "per-view logits via torch.stack(logits_list, dim=1) into a (B, M, C) tensor", "multi_view.py:ReliabilityEstimator._finalize_forward", ["EV3-BML-FINALIZE-FWD"], [], [], []),
        ("F-BML-REDUCE", "ReliabilityEstimator._finalize_forward", "reduces", "reliability-weighted logits via sum(dim=1) to produce fused_logits of shape (B, C)", "multi_view.py:ReliabilityEstimator._finalize_forward", ["EV3-BML-FINALIZE-FWD"], [], [], []),
        ("F-BML-BACKBONE-INIT", "MultiViewBackbone.__init__", "constructs", "per-view encoder networks (Linear-BN-ReLU-Dropout stacks) and classifier heads", "multi_view.py:MultiViewBackbone.__init__", ["EV3-BML-BACKBONE-INIT"], [], [], []),
        ("F-BML-BACKBONE-FWD", "MultiViewBackbone.forward", "calls_in_order", ["encode each view through per-view encoder", "compute per-view logits via classifier", "delegate to _finalize_forward for reliability-weighted fusion"], "multi_view.py:MultiViewBackbone.forward", ["EV3-BML-BACKBONE-FWD"], ["EV3-BML-FINALIZE-FWD"], ["RV3-BML-BACKBONE-FINALIZE"], []),
        ("F-BML-TRAIN-LOOP", "train_one_seed", "calls_in_order", ["build per-epoch noise-augmented dataset", "forward pass through backbone", "compute classification CE loss on fused_logits", "compute BCE alignment loss between reliabilities and corruption mask", "backward and optimize with joint loss", "test on multiple noise ratios"], "multi_view.py:train_one_seed", ["EV3-BML-TRAIN"], ["EV3-BML-BACKBONE-FWD", "EV3-BML-DATASET-INIT"], ["RV3-BML-TRAIN-FLOW"], []),
        ("F-BML-JOINT-LOSS", "train_one_seed", "optimizes", "joint loss = CrossEntropy(fused_logits, labels) + lambda_w * BCE(reliabilities, clean_indicators)", "multi_view.py:train_one_seed", ["EV3-BML-TRAIN"], [], [], []),
    ]
    facts: list[CodeFactV1] = []
    seen: set[str] = set()
    for fact_id, subject, predicate, obj, scope, direct, relation_spans, relation_ids, conditions in specs:
        identity_payload = {
            "snapshot": packets.repo_snapshot_id,
            "scope": scope,
            "subject": subject,
            "predicate": predicate,
            "object": _normalize_object(obj),
            "conditions": sorted(conditions),
        }
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
        facts.append(
            CodeFactV1(
                fact_id=fact_id,
                subject=subject,
                predicate=predicate,
                object=obj,
                conditions=conditions,
                scope=scope,
                direct_span_ids=direct,
                relation_span_ids=relation_spans,
                relation_evidence_ids=relation_ids,
                exact_source_digest=exact_digest,
                canonical_identity=identity,
                validation_status="rejected" if failures else "supported",
                validation_failures=failures,
            )
        )
    payload = [item.model_dump(mode="json") for item in facts]
    return CodeFactSetV1(
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        facts=facts,
        content_digest=_digest(payload),
    )


def _compile_claims(packets: EvidencePacketSetV3, facts: CodeFactSetV1) -> AtomicClaimSetV3:
    fact_by_id = {item.fact_id: item for item in facts.facts if item.validation_status == "supported"}
    specs = [
        ("C-BML-TNC-FORMALIZE", "The method formalizes Test-time Noisy Correspondence (TNC) and poses robust late fusion using per-view reliability weights.", ["F-BML-FINALIZE-FWD", "F-BML-BACKBONE-FWD", "F-BML-DATA-LOAD"], []),
        ("C-BML-BOOTSTRAP", "During training, each epoch samples a subset of data, randomly corrupts up to floor(M/2) views per instance by shuffling, and records the per-view corruption mask as ground-truth supervision for reliability.", ["F-BML-NOISE-INJECT", "F-BML-DATASET-CONSTRUCT"], []),
        ("C-BML-RELIABILITY-SIGNALS", "The reliability estimator computes two complementary signals: intra-view uncertainty Q_i (normalized entropy) and inter-view discrepancy J_i (averaged Jeffreys divergence).", ["F-BML-ENTROPY", "F-BML-AGREEMENT", "F-BML-REL-FEATURES"], []),
        ("C-BML-RELIABILITY-ESTIMATOR", "A lightweight per-view MLP (Linear-ReLU-Linear-Sigmoid) maps concatenated features and reliability signals to a scalar reliability weight in (0,1).", ["F-BML-ROUTER", "F-BML-ROUTER-FWD"], []),
        ("C-BML-BACKBONE", "Per-view encoder-classifier pairs extract features and logits; _finalize_forward performs reliability-weighted fusion via torch.stack, reliability.unsqueeze(-1) * logits_stack, and sum(dim=1).", ["F-BML-BACKBONE-INIT", "F-BML-BACKBONE-FWD", "F-BML-FINALIZE-FWD"], []),
        ("C-BML-JOINT-TRAINING", "The system is jointly optimized with classification cross-entropy on fused_logits and binary cross-entropy that aligns reliabilities with the ground-truth corruption indicator.", ["F-BML-TRAIN-LOOP", "F-BML-JOINT-LOSS"], []),
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
        claims.append(
            AtomicClaimV3(
                claim_id=claim_id,
                canonical_text=text,
                fact_ids=fact_ids,
                direct_evidence_ids=_dedupe([span for fact in selected for span in fact.direct_span_ids]),
                relation_evidence_ids=_dedupe([relation for fact in selected for relation in fact.relation_evidence_ids]),
                required_qualifiers=qualifiers,
                allowed_wording_boundary=text,
                canonical_identity=identity,
            )
        )
    gaps = [
        ExplicitCodeGapV1(
            gap_id="GAP-BML-DATASETS",
            topic="specific dataset .mat files and preprocessing",
            scope="provided executable repository",
            rationale="The repository reads .mat files from a local dataset_path; the actual dataset files are not included in the repository.",
        ),
        ExplicitCodeGapV1(
            gap_id="GAP-BML-MULTIMODAL",
            topic="multi-modal variant (SUN-R-D-T dataset)",
            scope="provided executable repository",
            rationale="The multi_modal.py variant for text-image datasets exists but is profiled separately; this profile covers the tabular multi-view variant.",
        ),
        ExplicitCodeGapV1(
            gap_id="GAP-BML-HYPERPARAMS",
            topic="exact hyperparameter values (lambda_w, learning rate, epochs, batch size)",
            scope="provided executable repository",
            rationale="These are tunable parameters; the structure evidence captures the pipeline architecture, not the specific numerical settings.",
        ),
    ]
    stage_specs = [
        ("S-V3-BML-1", "TNC Formalization and Data Bootstrapping", ["C-BML-TNC-FORMALIZE", "C-BML-BOOTSTRAP"]),
        ("S-V3-BML-2", "Reliability Signal Extraction", ["C-BML-RELIABILITY-SIGNALS"]),
        ("S-V3-BML-3", "Reliability Estimator and Weighted Fusion", ["C-BML-RELIABILITY-ESTIMATOR", "C-BML-BACKBONE"]),
        ("S-V3-BML-4", "Joint Training", ["C-BML-JOINT-TRAINING"]),
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
    return AtomicClaimSetV3(
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        code_fact_digest=facts.content_digest,
        claims=claims,
        explicit_code_gaps=gaps,
        semantic_stage_groups=stage_groups,
        content_digest=_digest(payload),
    )


_BEHAVIOR_REQUIRED_PATTERNS: dict[str, tuple[str, ...]] = {
    "multi_view.py": (
        r"class NC_MultiViewDataset", r"NoiseCorrespondence_inject",
        r"class ReliabilityEstimator", r"_build_router_mlps",
        r"_compute_entropy", r"_compute_pairwise_agreement",
        r"_compute_reliability_features", r"_router_forward",
        r"_finalize_forward",
        r"class MultiViewBackbone", r"def forward\s*\(self",
        r"def train_one_seed", r"def load_multiviewdata",
        r"nn\.Linear", r"nn\.Sigmoid",
        r"F\.binary_cross_entropy", r"CrossEntropyLoss",
        r"F\.kl_div", r"F\.log_softmax",
        r"noise_ratio", r"noise_indicator",
        r"reliabilit",
        # Weighted fusion: torch.stack, reliability * logits, sum reduction, return
        r"torch\.stack\(logits_list,\s*dim=1\)",
        r"reliabilities\.unsqueeze\(-1\)\s*\*\s*logits_stack",
        r"\.sum\(dim=1\)",
        r"return.*fused_logits",
    ),
}

_EXECUTABLE_PREDICATE_LABELS: dict[str, str] = {
    r"torch\.stack\(logits_list,\s*dim=1\)": "torch.stack(logits_list, dim=1)",
    r"reliabilities\.unsqueeze\(-1\)\s*\*\s*logits_stack": "reliabilities.unsqueeze(-1) * logits_stack",
    r"\.sum\(dim=1\)": "sum(dim=1) weighted reduction",
    r"return.*fused_logits": "return fused_logits",
    r"nn\.Linear": "nn.Linear",
    r"nn\.Sigmoid": "nn.Sigmoid",
    r"F\.binary_cross_entropy": "F.binary_cross_entropy",
    r"CrossEntropyLoss": "CrossEntropyLoss",
    r"F\.kl_div": "F.kl_div",
    r"F\.log_softmax": "F.log_softmax",
    r"noise_ratio": "noise_ratio",
    r"noise_indicator": "noise_indicator",
    r"reliabilit": "reliability estimation",
    r"_finalize_forward": "_finalize_forward method",
    r"_router_forward": "_router_forward method",
    r"_compute_entropy": "_compute_entropy method",
    r"_compute_pairwise_agreement": "_compute_pairwise_agreement method",
    r"_compute_reliability_features": "_compute_reliability_features method",
    r"_build_router_mlps": "_build_router_mlps method",
    r"def forward\s*\(self": "forward(self) method",
    r"def train_one_seed": "train_one_seed function",
    r"def load_multiviewdata": "load_multiviewdata function",
    r"class NC_MultiViewDataset": "NC_MultiViewDataset class",
    r"class ReliabilityEstimator": "ReliabilityEstimator class",
    r"class MultiViewBackbone": "MultiViewBackbone class",
    r"NoiseCorrespondence_inject": "NoiseCorrespondence_inject method",
}


def _behavior_contract_satisfied(root: Path) -> bool:
    """Reject same-name symbols that do not implement the typed predicates."""
    return not _behavior_contract_missing_patterns(root)


def _behavior_contract_missing_patterns(root: Path) -> list[str]:
    """Return the list of human-readable patterns that failed to match."""
    missing: list[str] = []
    for relative, patterns in _BEHAVIOR_REQUIRED_PATTERNS.items():
        try:
            text = (root / relative).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ["file_not_found:" + relative]
        for pattern in patterns:
            if not re.search(pattern, text):
                label = _EXECUTABLE_PREDICATE_LABELS.get(pattern, pattern)
                missing.append(label)
    return missing


def _normalize_object(value: str | list[str]) -> str | list[str]:
    return _normalize_text(value) if isinstance(value, str) else [_normalize_text(item) for item in value]


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", value.lower()))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in values if item))


class BootstrappingMultiViewProfile:
    profile_id = "bootstrapping_multiview_tnc_reliability"

    _required = [
        "noise_injection_dataset",
        "reliability_estimator",
        "weighted_forward_fusion",
        "multi_view_backbone",
        "joint_training_loop",
        "data_loading",
    ]

    def match(self, repo_snapshot: RepoSnapshot) -> ProfileMatch:
        root = Path(repo_snapshot.project_root).resolve()
        index = _SourceIndex(root, repo_snapshot)
        checks = {
            "noise_injection_dataset": all((
                index.has("multi_view.py", "NC_MultiViewDataset.__init__"),
                index.has("multi_view.py", "NC_MultiViewDataset.NoiseCorrespondence_inject"),
            )),
            "reliability_estimator": all((
                index.has("multi_view.py", "ReliabilityEstimator.__init__"),
                index.has("multi_view.py", "ReliabilityEstimator._compute_entropy"),
                index.has("multi_view.py", "ReliabilityEstimator._compute_pairwise_agreement"),
                index.has("multi_view.py", "ReliabilityEstimator._compute_reliability_features"),
                index.has("multi_view.py", "ReliabilityEstimator._build_router_mlps"),
                index.has("multi_view.py", "ReliabilityEstimator._router_forward"),
            )),
            "weighted_forward_fusion": all((
                index.has("multi_view.py", "ReliabilityEstimator._finalize_forward"),
            )),
            "multi_view_backbone": all((
                index.has("multi_view.py", "MultiViewBackbone.__init__"),
                index.has("multi_view.py", "MultiViewBackbone.forward"),
            )),
            "joint_training_loop": index.has("multi_view.py", "train_one_seed"),
            "data_loading": index.has("multi_view.py", "load_multiviewdata"),
        }
        matched_fingerprints = [name for name, passed in checks.items() if passed]
        missing_fingerprints = [name for name, passed in checks.items() if not passed]
        symbol_matched = not missing_fingerprints

        # Also check behavior contract to avoid match=True but compile=None
        missing_patterns = _behavior_contract_missing_patterns(root)
        behavior_ok = not missing_patterns
        matched = symbol_matched and behavior_ok

        reasons = []
        if symbol_matched:
            reasons.append(f"required executable symbols matched: {', '.join(matched_fingerprints)}")
        else:
            reasons.append(f"missing executable symbols: {', '.join(missing_fingerprints)}")
        if behavior_ok:
            reasons.append("behavior contract satisfied (weighted fusion, router MLPs, noise injection)")
        else:
            reasons.append(f"behavior contract FAILED: missing executable predicates: {', '.join(missing_patterns)}")

        return ProfileMatch(
            profile_id=self.profile_id,
            matched=matched,
            required_fingerprints=list(self._required),
            matched_fingerprints=matched_fingerprints,
            missing_required_fingerprints=missing_fingerprints,
            reasons=reasons,
        )

    def compile(self, repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
        return _compile_bootstrapping_evidence(repo_snapshot)


__all__ = ["BootstrappingMultiViewProfile"]