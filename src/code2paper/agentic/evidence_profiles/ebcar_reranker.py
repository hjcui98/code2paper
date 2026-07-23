"""Structure-triggered compiler profile for hybrid-attention rerankers."""

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
    FactPredicate,
    RelationEvidenceV3,
    SemanticStageGroupV1,
    _SourceIndex,
    _digest,
)
from code2paper.agentic.evidence_profiles.base import ProfileMatch
from code2paper.agentic.repo_snapshot import RepoSnapshot


_MODEL_PATH = "src/model/ebcar_dedicated_attention_model.py"
_ATTENTION_PATH = "src/model/transformer_encoder_hybrid_attention.py"
_EVALUATE_PATH = "src/evaluate.py"
_RERANKER = "EBCarRerankerHybridAttention"


def _text(index: _SourceIndex, path: str, symbol: str) -> str:
    try:
        node = index.node(path, symbol)
        lines = (index.root / path).read_text(
            encoding="utf-8", errors="replace"
        ).splitlines(keepends=True)
    except (OSError, SyntaxError, KeyError):
        return ""
    return "".join(lines[int(node.lineno) - 1 : int(node.end_lineno)])


def _has_all(text: str, patterns: tuple[str, ...]) -> bool:
    return all(re.search(pattern, text, flags=re.MULTILINE) for pattern in patterns)


class EbcarRerankerProfile:
    """Compile the executable embedding -> hybrid attention -> rerank path."""

    profile_id = "hybrid_attention_context_reranker"
    _required = [
        "forward_and_rerank",
        "structural_embedding_sum",
        "query_passage_concatenation",
        "same_document_query_mask",
        "unmasked_and_masked_attention",
        "fixed_query_contextual_passage_product",
        "descending_similarity_sort",
    ]

    def match(self, repo_snapshot: RepoSnapshot) -> ProfileMatch:
        root = Path(repo_snapshot.project_root).resolve()
        index = _SourceIndex(root, repo_snapshot)
        forward = _text(index, _MODEL_PATH, f"{_RERANKER}.forward")
        rerank = _text(index, _MODEL_PATH, f"{_RERANKER}.rerank")
        layer = _text(
            index,
            _ATTENTION_PATH,
            "TransformerEncoderLayerHybridAttention.forward",
        )
        checks = {
            "forward_and_rerank": bool(forward and rerank),
            "structural_embedding_sum": _has_all(
                forward,
                (
                    r"document_id_embeddings\s*=",
                    r"passage_id_embeddings\s*=",
                    r"passages\s*\+\s*document_id_embeddings\s*\+\s*passage_id_embeddings",
                ),
            ),
            "query_passage_concatenation": bool(
                re.search(r"torch\.cat\s*\(\s*\(query,\s*passages\).*dim\s*=\s*1", forward, re.DOTALL)
            ),
            "same_document_query_mask": _has_all(
                forward,
                (
                    r"temp_document_id\s*==\s*doc_id",
                    r"torch\.tensor\s*\(\s*\[True\]",
                    r"dedicated_attention_mask[\s\S]*?=\s*-float\s*\(\s*[\"']inf[\"']\s*\)",
                    r"dedicated_attention_mask[\s\S]*?temp_indices[\s\S]*?\]\s*=\s*0",
                ),
            ),
            "unmasked_and_masked_attention": _has_all(
                layer,
                (
                    r"shared_attn\s*\(\s*src2,\s*None",
                    r"dedicated_attn\s*\(\s*src2,\s*attn_mask",
                    r"shared_out\s*\+\s*dedicated_out",
                ),
            ),
            "fixed_query_contextual_passage_product": _has_all(
                rerank,
                (
                    r"passage_embeddings\s*=\s*outputs",
                    r"torch\.matmul\s*\(\s*query,\s*passage_embeddings\.transpose",
                ),
            ),
            "descending_similarity_sort": bool(
                re.search(
                    r"torch\.sort\s*\(\s*similarities.*descending\s*=\s*True",
                    rerank,
                    re.DOTALL,
                )
            ),
        }
        matched_fingerprints = [name for name, passed in checks.items() if passed]
        missing = [name for name, passed in checks.items() if not passed]
        return ProfileMatch(
            profile_id=self.profile_id,
            matched=not missing,
            required_fingerprints=list(self._required),
            matched_fingerprints=matched_fingerprints,
            missing_required_fingerprints=missing,
            reasons=[
                "hybrid reranker executable structure matched"
                if not missing
                else "required hybrid reranker structure was absent"
            ],
        )

    def compile(self, repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
        if not self.match(repo_snapshot).matched:
            return None
        root = Path(repo_snapshot.project_root).resolve()
        index = _SourceIndex(root, repo_snapshot)
        spans = _build_spans(index)
        packets = _build_packets(repo_snapshot, spans)
        facts = _build_facts(packets)
        claims = _build_claims(packets, facts)
        return EvidenceCompilerV3Result(packets=packets, facts=facts, claims=claims)


def _build_spans(index: _SourceIndex) -> dict[str, EvidenceSpanV3]:
    specs = (
        ("EV3-EBC-INIT", _MODEL_PATH, f"{_RERANKER}.__init__", "semantic"),
        ("EV3-EBC-POS", _MODEL_PATH, f"{_RERANKER}.get_passage_positional_encoding", "relation"),
        ("EV3-EBC-FORWARD", _MODEL_PATH, f"{_RERANKER}.forward", "anchor"),
        ("EV3-EBC-FORWARD-MASK", _MODEL_PATH, f"{_RERANKER}.forward", "relation"),
        ("EV3-EBC-RERANK", _MODEL_PATH, f"{_RERANKER}.rerank", "anchor"),
        ("EV3-EBC-ATTN", _ATTENTION_PATH, "MultiheadAttention.forward", "relation"),
        ("EV3-EBC-HYBRID", _ATTENTION_PATH, "TransformerEncoderLayerHybridAttention.forward", "anchor"),
        ("EV3-EBC-EVALUATE", _EVALUATE_PATH, "evaluate_EBCAR", "relation"),
    )
    return {
        span_id: index.span(span_id, path, symbol, role)  # type: ignore[arg-type]
        for span_id, path, symbol, role in specs
    }


def _packet(
    packet_id: str,
    scope: str,
    spans: list[EvidenceSpanV3],
    anchors: list[str],
    relation_spans: list[str],
    relations: list[RelationEvidenceV3],
    conditions: list[str],
    rationale: str = "",
    semantic_spans: list[str] | None = None,
) -> EvidencePacketV3:
    return EvidencePacketV3(
        packet_id=packet_id,
        scope=scope,
        anchor_span_ids=anchors,
        relation_span_ids=relation_spans,
        semantic_span_ids=semantic_spans or [],
        spans=spans,
        relations=relations,
        conditions=conditions,
        composition_rationale=rationale,
        source_digest=_digest([span.excerpt_digest for span in spans]),
    )


def _build_packets(
    snapshot: RepoSnapshot,
    spans: dict[str, EvidenceSpanV3],
) -> EvidencePacketSetV3:
    packets = [
        _packet(
            "EP-EMBED-STRUCTURE",
            f"{_MODEL_PATH}:{_RERANKER}.forward/rerank",
            [spans[item] for item in ("EV3-EBC-FORWARD", "EV3-EBC-RERANK", "EV3-EBC-INIT", "EV3-EBC-POS")],
            ["EV3-EBC-FORWARD", "EV3-EBC-RERANK"],
            ["EV3-EBC-POS"],
            [
                RelationEvidenceV3(
                    relation_id="RV3-EBC-POS-INIT",
                    relation_type="call_flow",
                    source_symbol=f"{_RERANKER}.__init__",
                    target_symbol=f"{_RERANKER}.get_passage_positional_encoding",
                    direct_span_ids=["EV3-EBC-INIT", "EV3-EBC-POS"],
                    statement="The initializer constructs a frozen sinusoidal passage-position table.",
                ),
                RelationEvidenceV3(
                    relation_id="RV3-EBC-AUGMENT",
                    relation_type="data_flow",
                    source_symbol="document_id/passage_id embeddings",
                    target_symbol="passages",
                    direct_span_ids=["EV3-EBC-FORWARD", "EV3-EBC-RERANK"],
                    conditions=["add_positional_encoding"],
                    statement="Document and passage-position embeddings are added to each passage representation.",
                ),
            ],
            ["cfg.add_positional_encoding controls structural augmentation"],
            "Four spans separate table construction, sinusoidal semantics, and the training/inference consumers.",
            semantic_spans=["EV3-EBC-INIT"],
        ),
        _packet(
            "EP-HYBRID-ATTN",
            f"{_ATTENTION_PATH}:TransformerEncoderLayerHybridAttention.forward",
            [spans[item] for item in ("EV3-EBC-HYBRID", "EV3-EBC-ATTN", "EV3-EBC-FORWARD-MASK")],
            ["EV3-EBC-HYBRID"],
            ["EV3-EBC-ATTN", "EV3-EBC-FORWARD-MASK"],
            [
                RelationEvidenceV3(
                    relation_id="RV3-EBC-MASK-CONSUME",
                    relation_type="data_flow",
                    source_symbol="dedicated_attention_mask",
                    target_symbol="TransformerEncoderLayerHybridAttention.dedicated_attn",
                    direct_span_ids=["EV3-EBC-FORWARD-MASK", "EV3-EBC-HYBRID", "EV3-EBC-ATTN"],
                    conditions=["use_dedicated_attention"],
                    statement="A same-document-plus-query mask is consumed only by the dedicated attention branch.",
                )
            ],
            ["the shared branch receives no attention mask"],
        ),
        _packet(
            "EP-CONTRASTIVE",
            f"{_MODEL_PATH}:{_RERANKER}.forward",
            [spans["EV3-EBC-FORWARD"]],
            ["EV3-EBC-FORWARD"],
            [],
            [],
            ["labels contain exactly one positive passage per sample"],
        ),
        _packet(
            "EP-RERANK",
            f"{_MODEL_PATH}:{_RERANKER}.rerank",
            [spans["EV3-EBC-RERANK"], spans["EV3-EBC-EVALUATE"]],
            ["EV3-EBC-RERANK"],
            ["EV3-EBC-EVALUATE"],
            [
                RelationEvidenceV3(
                    relation_id="RV3-EBC-EVALUATE-RERANK",
                    relation_type="call_flow",
                    source_symbol="evaluate_EBCAR",
                    target_symbol=f"{_RERANKER}.rerank",
                    direct_span_ids=["EV3-EBC-EVALUATE", "EV3-EBC-RERANK"],
                    statement="Evaluation passes dense query and passage embeddings plus structural IDs into rerank.",
                )
            ],
            ["evaluation executes reranking under torch.no_grad"],
        ),
    ]
    return EvidencePacketSetV3(
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        packets=packets,
        content_digest=_digest([packet.model_dump(mode="json") for packet in packets]),
    )


def _fact(
    packets: EvidencePacketSetV3,
    span_by_id: dict[str, EvidenceSpanV3],
    fact_id: str,
    subject: str,
    predicate: FactPredicate,
    obj: str | list[str],
    scope: str,
    direct: list[str],
    relation_ids: list[str] | None = None,
    conditions: list[str] | None = None,
) -> CodeFactV1:
    conditions = conditions or []
    identity = _digest(
        {
            "snapshot": packets.repo_snapshot_id,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "conditions": sorted(conditions),
        }
    )
    failures = [f"unknown_span:{item}" for item in direct if item not in span_by_id]
    return CodeFactV1(
        fact_id=fact_id,
        subject=subject,
        predicate=predicate,
        object=obj,
        conditions=conditions,
        scope=scope,
        direct_span_ids=direct,
        relation_evidence_ids=relation_ids or [],
        exact_source_digest=_digest(
            [span_by_id[item].excerpt_digest for item in direct if item in span_by_id]
        ),
        canonical_identity=identity,
        validation_status="rejected" if failures else "supported",
        validation_failures=failures,
    )


def _build_facts(packets: EvidencePacketSetV3) -> CodeFactSetV1:
    spans = {span.span_id: span for packet in packets.packets for span in packet.spans}
    scope = f"{_MODEL_PATH}:{_RERANKER}"
    specs = [
        ("F-EBC-STRUCT-TABLES", f"{_RERANKER}.__init__", "constructs", ["document-ID embedding table", "frozen sinusoidal passage-position table"], ["EV3-EBC-INIT", "EV3-EBC-POS"], ["RV3-EBC-POS-INIT"], []),
        ("F-EBC-AUGMENT", f"{_RERANKER}.forward", "transforms", "passage + document-ID embedding + passage-position embedding", ["EV3-EBC-FORWARD"], ["RV3-EBC-AUGMENT"], ["cfg.add_positional_encoding"]),
        ("F-EBC-CONCAT", f"{_RERANKER}.forward", "concatenates", "fixed query followed by structurally augmented passages along sequence dimension", ["EV3-EBC-FORWARD"], [], []),
        ("F-EBC-MASK", f"{_RERANKER}.forward", "constructs_mask", "query-visible same-document passage attention mask", ["EV3-EBC-FORWARD-MASK"], ["RV3-EBC-MASK-CONSUME"], ["cfg.use_dedicated_attention"]),
        ("F-EBC-HYBRID", "TransformerEncoderLayerHybridAttention.forward", "calls_in_order", ["unmasked shared attention", "same-document masked dedicated attention", "branch addition", "residual feed-forward update"], ["EV3-EBC-HYBRID", "EV3-EBC-ATTN"], ["RV3-EBC-MASK-CONSUME"], []),
        ("F-EBC-ATTN-FORMULA", "MultiheadAttention.forward", "computes_formula", "scaled query-key product, mask addition, softmax weights, and weighted values", ["EV3-EBC-ATTN"], [], []),
        ("F-EBC-SIMILARITY", f"{_RERANKER}.forward", "computes_formula", "fixed query dot contextual passage embeddings divided by temperature", ["EV3-EBC-FORWARD"], [], []),
        ("F-EBC-ONE-POSITIVE", f"{_RERANKER}.forward", "selects", "exactly one label-equal-one positive passage and all label-equal-zero negatives", ["EV3-EBC-FORWARD"], [], ["assert sum(pos_mask) == 1"]),
        ("F-EBC-INFONCE", f"{_RERANKER}.forward", "computes_formula", "negative positive similarity plus logsumexp over positive and negative similarities", ["EV3-EBC-FORWARD"], [], ["similarities are temperature scaled"]),
        ("F-EBC-RERANK-SIM", f"{_RERANKER}.rerank", "computes_formula", "fixed query dot contextual passage embeddings divided by temperature", ["EV3-EBC-RERANK"], ["RV3-EBC-EVALUATE-RERANK"], []),
        ("F-EBC-RERANK-SORT", f"{_RERANKER}.rerank", "sorts_by", "similarity descending", ["EV3-EBC-RERANK"], [], []),
        ("F-EBC-RERANK-RETURN", f"{_RERANKER}.rerank", "returns", ["passage text in descending similarity order", "corresponding relevance scores"], ["EV3-EBC-RERANK"], [], []),
    ]
    facts = [
        _fact(packets, spans, fact_id, subject, predicate, obj, scope, direct, relations, conditions)  # type: ignore[arg-type]
        for fact_id, subject, predicate, obj, direct, relations, conditions in specs
    ]
    return CodeFactSetV1(
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        facts=facts,
        content_digest=_digest([fact.model_dump(mode="json") for fact in facts]),
    )


def _build_claims(
    packets: EvidencePacketSetV3,
    facts: CodeFactSetV1,
) -> AtomicClaimSetV3:
    fact_by_id = {fact.fact_id: fact for fact in facts.facts if fact.validation_status == "supported"}
    specs = [
        ("C-EBC-STRUCT-TABLES", "The reranker constructs a trainable document-ID embedding table and a frozen sinusoidal passage-position table.", ["F-EBC-STRUCT-TABLES"], []),
        ("C-EBC-AUGMENT-CONCAT", "When structural augmentation is enabled, document-ID and passage-position vectors are added to passage embeddings before a fixed query embedding is prepended along the sequence dimension.", ["F-EBC-AUGMENT", "F-EBC-CONCAT"], ["when cfg.add_positional_encoding is true"]),
        ("C-EBC-SHARED-ATTENTION", "Each hybrid encoder layer applies an unmasked shared-attention branch.", ["F-EBC-HYBRID"], []),
        ("C-EBC-DEDICATED-ATTENTION", "Each hybrid encoder layer also applies a dedicated branch to the query and passages with the same document ID under the scope defined by the constructed mask.", ["F-EBC-MASK", "F-EBC-HYBRID"], ["under the scope defined by the constructed mask"]),
        ("C-EBC-ATTENTION-UPDATE", "The two attention outputs are added inside a residual update and followed by a feed-forward residual update; each attention branch uses scaled query-key logits and softmax-weighted values.", ["F-EBC-HYBRID", "F-EBC-ATTN-FORMULA"], []),
        ("C-EBC-CONTRASTIVE-SIM", "Training keeps the original query as the scoring anchor and takes its dot product with contextual passage embeddings before temperature scaling.", ["F-EBC-SIMILARITY"], []),
        ("C-EBC-INFONCE", "For each sample, exactly one positive passage is selected and the implemented contrastive loss subtracts its scaled similarity from logsumexp over that positive and all negatives.", ["F-EBC-ONE-POSITIVE", "F-EBC-INFONCE"], ["labels must contain exactly one positive"]),
        ("C-EBC-RERANK-SIM", "Inference applies the same fixed-query dot product and temperature scaling to contextual passage embeddings produced by the hybrid encoder.", ["F-EBC-RERANK-SIM"], []),
        ("C-EBC-RERANK-ORDER", "The reranker sorts similarities in descending order and returns passage text in that order together with the corresponding relevance scores.", ["F-EBC-RERANK-SORT", "F-EBC-RERANK-RETURN"], []),
    ]
    claims: list[AtomicClaimV3] = []
    for claim_id, text, fact_ids, qualifiers in specs:
        selected = [fact_by_id[item] for item in fact_ids if item in fact_by_id]
        if len(selected) != len(fact_ids):
            continue
        direct = list(dict.fromkeys(span for fact in selected for span in fact.direct_span_ids))
        relations = list(dict.fromkeys(rel for fact in selected for rel in fact.relation_evidence_ids))
        claims.append(
            AtomicClaimV3(
                claim_id=claim_id,
                canonical_text=text,
                fact_ids=fact_ids,
                direct_evidence_ids=direct,
                relation_evidence_ids=relations,
                required_qualifiers=qualifiers,
                allowed_wording_boundary=text,
                canonical_identity=_digest({"behavior": text.lower(), "facts": sorted(fact_ids)}),
            )
        )
    stage_specs = [
        ("S-EBC-1", "Embedding and structural augmentation", ["C-EBC-STRUCT-TABLES", "C-EBC-AUGMENT-CONCAT"]),
        ("S-EBC-2", "Hybrid context encoder", ["C-EBC-SHARED-ATTENTION", "C-EBC-DEDICATED-ATTENTION", "C-EBC-ATTENTION-UPDATE"]),
        ("S-EBC-3", "Contrastive objective", ["C-EBC-CONTRASTIVE-SIM", "C-EBC-INFONCE"]),
        ("S-EBC-4", "Inference reranking", ["C-EBC-RERANK-SIM", "C-EBC-RERANK-ORDER"]),
    ]
    claim_by_id = {claim.claim_id: claim for claim in claims}
    groups = [
        SemanticStageGroupV1(
            stage_id=stage_id,
            name=name,
            purpose=" ".join(claim_by_id[item].canonical_text for item in claim_ids if item in claim_by_id),
            ordered_claim_ids=[item for item in claim_ids if item in claim_by_id],
            relation_evidence_ids=list(dict.fromkeys(
                relation
                for item in claim_ids
                if item in claim_by_id
                for relation in claim_by_id[item].relation_evidence_ids
            )),
            organization_priority=priority,
        )
        for priority, (stage_id, name, claim_ids) in enumerate(stage_specs, start=1)
    ]
    payload = {
        "claims": [claim.model_dump(mode="json") for claim in claims],
        "explicit_code_gaps": [],
        "semantic_stage_groups": [group.model_dump(mode="json") for group in groups],
    }
    return AtomicClaimSetV3(
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        code_fact_digest=facts.content_digest,
        claims=claims,
        semantic_stage_groups=groups,
        content_digest=_digest(payload),
    )


__all__ = ["EbcarRerankerProfile"]
