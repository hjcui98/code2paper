"""Structure-triggered compiler profile for time-conditioned graph sequence models."""

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
    RelationEvidenceV3,
    SemanticStageGroupV1,
    _SourceIndex,
    _digest,
)
from code2paper.agentic.evidence_profiles.base import ProfileMatch
from code2paper.agentic.repo_snapshot import RepoSnapshot


_MODEL = "models/DyGMamba.py"
_MAMBA = "models/mamba_simple.py"
_MODULES = "models/modules.py"
_TRAIN_LINK = "train_link_prediction.py"
_MAIN = "DyGMamba.compute_src_dst_node_temporal_embeddings"


def _text(index: _SourceIndex, path: str, symbol: str) -> str:
    try:
        span = index.span("probe", path, symbol, "anchor")
    except (OSError, SyntaxError, KeyError):
        return ""
    return span.exact_excerpt


def _all(text: str, *patterns: str) -> bool:
    return all(re.search(pattern, text, flags=re.DOTALL) for pattern in patterns)


class DynamicGraphMambaProfile:
    profile_id = "temporal_graph_time_conditioned_sequence"
    _required = [
        "first_hop_history_and_padding",
        "four_projected_channels",
        "elapsed_time_to_encoder_dts",
        "time_conditioned_selective_scan",
        "cross_attention",
        "gated_topk_renormalized_readout",
        "task_head",
    ]

    def match(self, repo_snapshot: RepoSnapshot) -> ProfileMatch:
        index = _SourceIndex(Path(repo_snapshot.project_root).resolve(), repo_snapshot)
        main = _text(index, _MODEL, _MAIN)
        dt = _text(index, _MODEL, "DyGMamba.get_dt_features")
        ssm = _text(index, _MAMBA, "MambaTimeDelta.forward")
        task = _read(index.root, _TRAIN_LINK)
        checks = {
            "first_hop_history_and_padding": _all(
                main, r"get_all_first_hop_neighbors\s*\(", r"self\.pad_sequences\s*\("
            ),
            "four_projected_channels": _all(
                main,
                r"projection_layer\s*\[\s*['\"]node['\"]\s*\]",
                r"projection_layer\s*\[\s*['\"]edge['\"]\s*\]",
                r"projection_layer\s*\[\s*['\"]time['\"]\s*\]",
                r"projection_layer\s*\[\s*['\"]neighbor_co_occurrence['\"]\s*\]",
                r"torch\.stack\s*\(",
                r"\.reshape\s*\(",
            ),
            "elapsed_time_to_encoder_dts": bool(dt) and _all(
                main,
                r"self\.get_dt_features\s*\(",
                r"self\.projection_dt\s*\(",
                r"encoder\s*\([^\)]*dts\s*=\s*src_padded_dt_features",
                r"encoder\s*\([^\)]*dts\s*=\s*dst_padded_dt_features",
            ),
            "time_conditioned_selective_scan": _all(
                ssm,
                r"dts\s*!=\s*None",
                r"dt\s*,\s*B\s*,\s*C\s*=\s*torch\.split\s*\(",
                r"A\s*=\s*-torch\.exp\s*\(",
                r"selective_scan_fn\s*\(",
            ),
            "cross_attention": _all(
                main,
                r"cross_linear_attention\s*\(\s*src_padded_data,\s*dst_padded_data",
                r"cross_linear_attention\s*\(\s*dst_padded_data,\s*src_padded_data",
            ),
            "gated_topk_renormalized_readout": _all(
                main,
                r"src_gate\s*\(",
                r"F\.softmax\s*\(",
                r"src_routing_weights\s*,[^=]*=\s*torch\.topk\s*\(\s*src_routing_weights",
                r"dst_routing_weights\s*,[^=]*=\s*torch\.topk\s*\(\s*dst_routing_weights",
                r"src_routing_weights\s*/=\s*src_routing_weights\.sum",
                r"dst_routing_weights\s*/=\s*dst_routing_weights\.sum",
                r"src_padded_data\s*\*\s*src_routing_weights_expand",
                r"dst_padded_data\s*\*\s*dst_routing_weights_expand",
                r"\.sum\s*\(\s*1\s*\)",
                r"self\.output_layer\s*\(",
            ),
            "task_head": _all(
                task,
                r"MergeLayer\s*\(",
                r"compute_src_dst_node_temporal_embeddings\s*\(",
                r"\.sigmoid\s*\(",
                r"BCELoss\s*\(",
            ),
        }
        matched = [name for name, passed in checks.items() if passed]
        missing = [name for name, passed in checks.items() if not passed]
        return ProfileMatch(
            profile_id=self.profile_id,
            matched=not missing,
            required_fingerprints=list(self._required),
            matched_fingerprints=matched,
            missing_required_fingerprints=missing,
            reasons=[
                "time-conditioned temporal graph path matched"
                if not missing
                else "required temporal graph structure was absent"
            ],
        )

    def compile(self, repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
        if not self.match(repo_snapshot).matched:
            return None
        index = _SourceIndex(Path(repo_snapshot.project_root).resolve(), repo_snapshot)
        spans = _spans(index)
        packets = _packets(repo_snapshot, spans)
        facts = _facts(packets)
        claims = _claims(packets, facts)
        return EvidenceCompilerV3Result(packets=packets, facts=facts, claims=claims)


def _read(root: Path, path: str) -> str:
    try:
        return (root / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _module_span(
    index: _SourceIndex,
    span_id: str,
    path: str,
    symbol: str,
    start_pattern: str,
    end_pattern: str,
    role: str = "relation",
) -> EvidenceSpanV3:
    lines = _read(index.root, path).splitlines()
    start = next(i for i, line in enumerate(lines, start=1) if re.search(start_pattern, line))
    end = next(
        i for i, line in enumerate(lines[start - 1 :], start=start) if re.search(end_pattern, line)
    )
    return index.line_span(span_id, path, symbol, start, end, role)  # type: ignore[arg-type]


def _spans(index: _SourceIndex) -> dict[str, EvidenceSpanV3]:
    spans = {
        "EV3-DYG-MAIN": index.span("EV3-DYG-MAIN", _MODEL, _MAIN, "anchor"),
        "EV3-DYG-MAIN-DTS": index.span("EV3-DYG-MAIN-DTS", _MODEL, _MAIN, "relation"),
        "EV3-DYG-PAD": index.span("EV3-DYG-PAD", _MODEL, "DyGMamba.pad_sequences", "relation"),
        "EV3-DYG-FEATURES": index.span("EV3-DYG-FEATURES", _MODEL, "DyGMamba.get_features", "relation"),
        "EV3-DYG-COOCCUR": index.span("EV3-DYG-COOCCUR", _MODEL, "NeighborCooccurrenceEncoder.forward", "relation"),
        "EV3-DYG-DT": index.span("EV3-DYG-DT", _MODEL, "DyGMamba.get_dt_features", "anchor"),
        "EV3-DYG-ENCODER": index.span("EV3-DYG-ENCODER", _MODEL, "MambaEncoder.forward", "relation"),
        "EV3-DYG-SSM": index.span("EV3-DYG-SSM", _MAMBA, "MambaTimeDelta.forward", "anchor"),
        "EV3-DYG-CROSS": index.span("EV3-DYG-CROSS", _MODEL, "CrossAttention.forward", "relation"),
        "EV3-DYG-MERGE": index.span("EV3-DYG-MERGE", _MODULES, "MergeLayer.forward", "relation"),
    }
    spans["EV3-DYG-TASK-SETUP"] = _module_span(
        index, "EV3-DYG-TASK-SETUP", _TRAIN_LINK, "link-prediction task setup",
        r"link_predictor\s*=\s*MergeLayer", r"loss_func\s*=\s*nn\.BCELoss",
    )
    spans["EV3-DYG-TASK-USE"] = _module_span(
        index, "EV3-DYG-TASK-USE", _TRAIN_LINK, "link-prediction task application",
        r"positive_probabilities\s*=", r"loss\s*=\s*loss_func",
        "anchor",
    )
    return spans


def _packet(
    packet_id: str,
    scope: str,
    spans: list[EvidenceSpanV3],
    anchors: list[str],
    relation_spans: list[str],
    relations: list[RelationEvidenceV3],
    conditions: list[str] | None = None,
    rationale: str = "",
) -> EvidencePacketV3:
    return EvidencePacketV3(
        packet_id=packet_id,
        scope=scope,
        anchor_span_ids=anchors,
        relation_span_ids=relation_spans,
        spans=spans,
        relations=relations,
        conditions=conditions or [],
        composition_rationale=rationale,
        source_digest=_digest([span.excerpt_digest for span in spans]),
    )


def _relation(
    relation_id: str,
    source: str,
    target: str,
    span_ids: list[str],
    statement: str,
    relation_type: str = "data_flow",
) -> RelationEvidenceV3:
    return RelationEvidenceV3(
        relation_id=relation_id,
        relation_type=relation_type,  # type: ignore[arg-type]
        source_symbol=source,
        target_symbol=target,
        direct_span_ids=span_ids,
        statement=statement,
    )


def _packets(snapshot: RepoSnapshot, s: dict[str, EvidenceSpanV3]) -> EvidencePacketSetV3:
    packets = [
        _packet("EP-DYG-HISTORY", f"{_MODEL}:{_MAIN}", [s["EV3-DYG-MAIN"], s["EV3-DYG-PAD"]], ["EV3-DYG-MAIN"], ["EV3-DYG-PAD"], [_relation("RV3-DYG-HISTORY", _MAIN, "DyGMamba.pad_sequences", ["EV3-DYG-MAIN", "EV3-DYG-PAD"], "First-hop source and destination histories are padded before encoding.", "call_flow")]),
        _packet("EP-DYG-CHANNELS", f"{_MODEL}:{_MAIN}", [s["EV3-DYG-MAIN"], s["EV3-DYG-FEATURES"], s["EV3-DYG-COOCCUR"]], ["EV3-DYG-MAIN"], ["EV3-DYG-FEATURES", "EV3-DYG-COOCCUR"], [_relation("RV3-DYG-CHANNELS", "get_features/NeighborCooccurrenceEncoder", _MAIN, ["EV3-DYG-MAIN", "EV3-DYG-FEATURES", "EV3-DYG-COOCCUR"], "Node, edge, time, and co-occurrence channels are independently projected and stacked.")]),
        _packet("EP-DYG-DELTAT", f"{_MODEL}:DyGMamba.get_dt_features", [s["EV3-DYG-DT"], s["EV3-DYG-MAIN-DTS"], s["EV3-DYG-ENCODER"]], ["EV3-DYG-DT"], ["EV3-DYG-MAIN-DTS", "EV3-DYG-ENCODER"], [_relation("RV3-DYG-DTS", "DyGMamba.get_dt_features", "MambaEncoder.forward(dts)", ["EV3-DYG-DT", "EV3-DYG-MAIN-DTS", "EV3-DYG-ENCODER"], "Normalized elapsed-time features are projected and passed through the dts argument.")]),
        _packet("EP-DYG-SSM", f"{_MAMBA}:MambaTimeDelta.forward", [s["EV3-DYG-SSM"]], ["EV3-DYG-SSM"], [], [], ["the time-conditioned branch requires non-null dts"]),
        _packet("EP-DYG-READOUT", f"{_MODEL}:{_MAIN}", [s["EV3-DYG-MAIN"], s["EV3-DYG-CROSS"]], ["EV3-DYG-MAIN"], ["EV3-DYG-CROSS"], [_relation("RV3-DYG-READOUT", "source/destination sequences", "gated top-k weighted node embeddings", ["EV3-DYG-MAIN", "EV3-DYG-CROSS"], "Bidirectional cross attention precedes gated top-k renormalized weighted pooling.")]),
        _packet("EP-DYG-TASK", f"{_TRAIN_LINK}:link-prediction task", [s["EV3-DYG-TASK-SETUP"], s["EV3-DYG-TASK-USE"], s["EV3-DYG-MERGE"]], ["EV3-DYG-TASK-USE"], ["EV3-DYG-TASK-SETUP", "EV3-DYG-MERGE"], [_relation("RV3-DYG-TASK", "source/destination node embeddings", "MergeLayer sigmoid BCELoss", ["EV3-DYG-TASK-SETUP", "EV3-DYG-TASK-USE", "EV3-DYG-MERGE"], "Node-pair embeddings enter a merge head, sigmoid probabilities, and binary cross-entropy.", "call_flow")]),
    ]
    return EvidencePacketSetV3(
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        packets=packets,
        content_digest=_digest([packet.model_dump(mode="json") for packet in packets]),
    )


def _make_fact(
    packets: EvidencePacketSetV3,
    spans: dict[str, EvidenceSpanV3],
    fact_id: str,
    subject: str,
    predicate: FactPredicate,
    obj: str | list[str],
    direct: list[str],
    relations: list[str] | None = None,
    conditions: list[str] | None = None,
) -> CodeFactV1:
    conditions = conditions or []
    return CodeFactV1(
        fact_id=fact_id,
        subject=subject,
        predicate=predicate,
        object=obj,
        conditions=conditions,
        scope=f"{_MODEL}:{_MAIN}",
        direct_span_ids=direct,
        relation_evidence_ids=relations or [],
        exact_source_digest=_digest([spans[item].excerpt_digest for item in direct]),
        canonical_identity=_digest({"snapshot": packets.repo_snapshot_id, "subject": subject, "predicate": predicate, "object": obj, "conditions": sorted(conditions)}),
    )


def _facts(packets: EvidencePacketSetV3) -> CodeFactSetV1:
    spans = {span.span_id: span for packet in packets.packets for span in packet.spans}
    specs = [
        ("F-DYG-HISTORY", _MAIN, "calls_in_order", ["sample first-hop source/destination histories", "pad both histories"], ["EV3-DYG-MAIN", "EV3-DYG-PAD"], ["RV3-DYG-HISTORY"], []),
        ("F-DYG-CHANNELS", _MAIN, "stacks", ["projected node channel", "projected edge channel", "projected elapsed-time channel", "projected neighbor co-occurrence channel"], ["EV3-DYG-MAIN", "EV3-DYG-FEATURES", "EV3-DYG-COOCCUR"], ["RV3-DYG-CHANNELS"], []),
        ("F-DYG-DT", "DyGMamba.get_dt_features", "transforms", "clipped normalized adjacent timestamp differences encoded and projected as dts", ["EV3-DYG-DT", "EV3-DYG-MAIN-DTS"], ["RV3-DYG-DTS"], []),
        ("F-DYG-DTS-PASS", _MAIN, "calls", "MambaEncoder.forward with source/destination dts", ["EV3-DYG-MAIN-DTS", "EV3-DYG-ENCODER"], ["RV3-DYG-DTS"], []),
        ("F-DYG-SSM-PROJECTION", "MambaTimeDelta.forward", "calls_in_order", ["input projection", "causal convolution"], ["EV3-DYG-SSM"], [], ["dts is not None"]),
        ("F-DYG-SSM-PARAMETERS", "MambaTimeDelta.forward", "constructs", ["dts-conditioned dt/B/C construction", "negative exponential A"], ["EV3-DYG-SSM"], [], ["dts is not None"]),
        ("F-DYG-SSM-SCAN", "MambaTimeDelta.forward", "calls_in_order", ["selective scan", "output projection"], ["EV3-DYG-SSM"], [], ["dts is not None"]),
        ("F-DYG-CROSS", _MAIN, "attends", "source sequence to destination context and destination sequence to updated source context", ["EV3-DYG-MAIN", "EV3-DYG-CROSS"], ["RV3-DYG-READOUT"], []),
        ("F-DYG-GATE", _MAIN, "calls_in_order", ["learned gate logits", "sequence softmax", "top-k selection", "selected-weight renormalization", "scatter", "weighted sum", "output projection"], ["EV3-DYG-MAIN"], ["RV3-DYG-READOUT"], []),
        ("F-DYG-TASK", "link-prediction task", "calls_in_order", ["source/destination temporal embeddings", "MergeLayer", "sigmoid", "binary cross-entropy"], ["EV3-DYG-TASK-SETUP", "EV3-DYG-TASK-USE", "EV3-DYG-MERGE"], ["RV3-DYG-TASK"], []),
    ]
    facts = [_make_fact(packets, spans, *spec) for spec in specs]  # type: ignore[arg-type]
    return CodeFactSetV1(
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        facts=facts,
        content_digest=_digest([fact.model_dump(mode="json") for fact in facts]),
    )


def _claims(packets: EvidencePacketSetV3, facts: CodeFactSetV1) -> AtomicClaimSetV3:
    by_id = {fact.fact_id: fact for fact in facts.facts}
    specs = [
        ("C-DYG-HISTORY", "For each source and destination node, the executable path samples first-hop interaction histories and pads the two histories into aligned sequences.", ["F-DYG-HISTORY"], []),
        ("C-DYG-CHANNELS", "Node, edge, elapsed-time, and neighbor co-occurrence features are projected separately, stacked as four channels, and reshaped into each history sequence.", ["F-DYG-CHANNELS"], []),
        ("C-DYG-DT", "Adjacent history timestamps are clipped and normalized, time-encoded, projected, and passed to each sequence encoder through its dts argument.", ["F-DYG-DT", "F-DYG-DTS-PASS"], []),
        ("C-DYG-SSM-PROJECTION", "For the non-null dts branch, the sequence block performs input projection followed by causal convolution.", ["F-DYG-SSM-PROJECTION"], ["for the non-null dts branch"]),
        ("C-DYG-SSM-PARAMETERS", "For the non-null dts branch, the sequence block derives time-conditioned dt, B, and C terms and uses a negative exponential state matrix.", ["F-DYG-SSM-PARAMETERS"], ["for the non-null dts branch"]),
        ("C-DYG-SSM-SCAN", "For the non-null dts branch, the sequence block applies selective scan before output projection.", ["F-DYG-SSM-SCAN"], ["for the non-null dts branch"]),
        ("C-DYG-CROSS", "The encoded source history attends to the destination history, and the destination history then attends to the updated source representation.", ["F-DYG-CROSS"], []),
        ("C-DYG-READOUT", "Learned gates produce sequence-softmax weights; the implementation selects top-k entries, renormalizes their weights, scatters them back, and computes a weighted sum followed by an output projection.", ["F-DYG-GATE"], []),
        ("C-DYG-TASK", "For link prediction, source and destination node embeddings enter a MergeLayer, sigmoid probabilities, and binary cross-entropy against positive and negative labels.", ["F-DYG-TASK"], ["in the link-prediction training entrypoint"]),
    ]
    claims: list[AtomicClaimV3] = []
    for claim_id, text, fact_ids, qualifiers in specs:
        selected = [by_id[item] for item in fact_ids]
        claims.append(AtomicClaimV3(
            claim_id=claim_id,
            canonical_text=text,
            fact_ids=fact_ids,
            direct_evidence_ids=list(dict.fromkeys(span for fact in selected for span in fact.direct_span_ids)),
            relation_evidence_ids=list(dict.fromkeys(rel for fact in selected for rel in fact.relation_evidence_ids)),
            required_qualifiers=qualifiers,
            allowed_wording_boundary=text,
            canonical_identity=_digest({"behavior": text.lower(), "facts": sorted(fact_ids)}),
        ))
    gaps = [
        ExplicitCodeGapV1(gap_id="GAP-DYG-SPECTRAL", topic="spectral-norm constraints on B and C", scope="compiled executable path", rationale="The inspected time-conditioned selective-scan path constructs B and C without an executable spectral-normalization operation."),
        ExplicitCodeGapV1(gap_id="GAP-DYG-MEAN", topic="MEAN pooling", scope="compiled executable path", rationale="The executable readout uses learned gates, top-k selection, renormalization, and weighted summation rather than mean pooling."),
        ExplicitCodeGapV1(gap_id="GAP-DYG-PAPER-TIMESPAN", topic="paper-form learnable exponential timespan equation", scope="compiled executable path", rationale="No equation claim reconstructing that paper expression is authorized from the exact operations."),
        ExplicitCodeGapV1(gap_id="GAP-DYG-PERFORMANCE", topic="performance, robustness, or complexity conclusions", scope="compiled executable path", rationale="Executable structure alone does not support empirical or complexity conclusions."),
    ]
    stage_specs = [
        ("S-DYG-1", "Temporal history construction", ["C-DYG-HISTORY"]),
        ("S-DYG-2", "Four-channel history representation", ["C-DYG-CHANNELS", "C-DYG-DT"]),
        ("S-DYG-3", "Time-conditioned state-space encoding", ["C-DYG-SSM-PROJECTION", "C-DYG-SSM-PARAMETERS", "C-DYG-SSM-SCAN"]),
        ("S-DYG-4", "Cross-history gated readout", ["C-DYG-CROSS", "C-DYG-READOUT"]),
        ("S-DYG-5", "Downstream task head", ["C-DYG-TASK"]),
    ]
    claim_by_id = {claim.claim_id: claim for claim in claims}
    groups = [SemanticStageGroupV1(
        stage_id=stage_id,
        name=name,
        purpose=" ".join(claim_by_id[item].canonical_text for item in claim_ids),
        ordered_claim_ids=claim_ids,
        relation_evidence_ids=list(dict.fromkeys(rel for item in claim_ids for rel in claim_by_id[item].relation_evidence_ids)),
        organization_priority=priority,
    ) for priority, (stage_id, name, claim_ids) in enumerate(stage_specs, start=1)]
    payload = {"claims": [claim.model_dump(mode="json") for claim in claims], "explicit_code_gaps": [gap.model_dump(mode="json") for gap in gaps], "semantic_stage_groups": [group.model_dump(mode="json") for group in groups]}
    return AtomicClaimSetV3(
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        code_fact_digest=facts.content_digest,
        claims=claims,
        explicit_code_gaps=gaps,
        semantic_stage_groups=groups,
        content_digest=_digest(payload),
    )


__all__ = ["DynamicGraphMambaProfile"]
