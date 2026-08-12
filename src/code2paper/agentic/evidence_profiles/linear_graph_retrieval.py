"""Structure-triggered compiler profile for sparse graph retrieval pipelines."""

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


_CORE = "src/LinearRAG.py"
_NER = "src/ner.py"
_CLASS = "LinearRAG"


def _text(index: _SourceIndex, path: str, symbol: str) -> str:
    try:
        return index.span("probe", path, symbol, "anchor").exact_excerpt
    except (OSError, SyntaxError, KeyError):
        return ""


def _all(text: str, *patterns: str) -> bool:
    return all(re.search(pattern, text, flags=re.DOTALL) for pattern in patterns)


class LinearGraphRetrievalProfile:
    profile_id = "sparse_entity_sentence_ppr_retrieval"
    _required = [
        "offline_index_mappings",
        "bidirectional_sparse_matrices",
        "query_entity_seed_matching",
        "threshold_topk_masked_sparse_propagation",
        "hybrid_passage_initialization",
        "personalized_pagerank_descending",
        "dense_no_seed_fallback",
    ]

    def match(self, repo_snapshot: RepoSnapshot) -> ProfileMatch:
        index = _SourceIndex(Path(repo_snapshot.project_root).resolve(), repo_snapshot)
        indexing = _text(index, _CORE, f"{_CLASS}.index")
        sparse = _text(index, _CORE, f"{_CLASS}._precompute_sparse_matrices")
        seed = _text(index, _CORE, f"{_CLASS}.get_seed_entities")
        propagate = _text(index, _CORE, f"{_CLASS}.calculate_entity_scores_vectorized")
        passage = _text(index, _CORE, f"{_CLASS}.calculate_passage_scores")
        search = _text(index, _CORE, f"{_CLASS}.graph_search_with_seed_entities")
        ppr = _text(index, _CORE, f"{_CLASS}.run_ppr")
        retrieve = _text(index, _CORE, f"{_CLASS}.retrieve")
        checks = {
            "offline_index_mappings": _all(
                indexing,
                r"passage_embedding_store\.insert_text\s*\(",
                r"spacy_ner\.batch_ner\s*\(",
                r"extract_nodes_and_edges\s*\(",
                r"sentence_embedding_store\.insert_text\s*\(",
                r"entity_embedding_store\.insert_text\s*\(",
                r"add_entity_to_passage_edges\s*\(",
            ),
            "bidirectional_sparse_matrices": _all(
                sparse,
                r"entity_to_sentence_indices",
                r"sentence_to_entity_indices",
                r"entity_to_sentence_sparse\s*=\s*torch\.sparse_coo_tensor",
                r"sentence_to_entity_sparse\s*=\s*torch\.sparse_coo_tensor",
            ),
            "query_entity_seed_matching": _all(
                seed,
                r"question_ner\s*\(",
                r"normalize_embeddings\s*=\s*True",
                r"np\.dot\s*\(",
                r"np\.argmax\s*\(",
                r"seed_entity_scores\.append",
            ),
            "threshold_topk_masked_sparse_propagation": _all(
                propagate,
                r"used_sentence_mask\s*=\s*torch\.zeros",
                r"iteration_threshold",
                r"top_k_sentence",
                r"torch\.topk\s*\(",
                r"used_sentence_mask\s*\[.*\]\s*=\s*True",
                r"entity_to_sentence_sparse\.t\s*\(",
                r"sentence_to_entity_sparse\.t\s*\(",
                r"weighted_sentence_scores\s*=\s*sentence_activation\s*\*\s*sentence_similarities",
                r"entity_scores_dense\s*\+=\s*next_entity_scores_dense",
            ),
            "hybrid_passage_initialization": _all(
                passage,
                r"dense_passage_retrieval\s*\(",
                r"min_max_normalize\s*\(",
                r"for\s+entity_hash_id.*actived_entities\.items",
                r"total_entity_bonus\s*\+=",
                r"passage_score\s*=.*dpr_passage_score.*total_entity_bonus",
                r"passage_weights\s*\[.*\]\s*=",
            ),
            "personalized_pagerank_descending": _all(
                search + ppr,
                r"node_weights\s*=\s*entity_weights\s*\+\s*passage_weights",
                r"personalized_pagerank\s*\(",
                r"reset\s*=\s*reset_prob",
                r"np\.argsort\s*\(\s*doc_scores\s*\)\s*\[::\s*-1\]",
            ),
            "dense_no_seed_fallback": _all(
                retrieve,
                r"if\s+len\s*\(\s*seed_entities\s*\)\s*!=\s*0",
                r"else\s*:",
                r"dense_passage_retrieval\s*\(",
                r"retrieval_top_k",
                r"sorted_passage_scores",
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
                "sparse entity-sentence propagation and PPR path matched"
                if not missing
                else "required sparse graph retrieval structure was absent"
            ],
        )

    def _compile_legacy(self, repo_snapshot: RepoSnapshot) -> EvidenceCompilerV3Result | None:
        """Archived migration fixture; never exposed by the production view."""
        if not self.match(repo_snapshot).matched:
            return None
        index = _SourceIndex(Path(repo_snapshot.project_root).resolve(), repo_snapshot)
        spans = _spans(index)
        packets = _packets(repo_snapshot, spans)
        facts = _facts(packets)
        claims = _claims(packets, facts)
        return EvidenceCompilerV3Result(packets=packets, facts=facts, claims=claims)


def _spans(index: _SourceIndex) -> dict[str, EvidenceSpanV3]:
    specs = (
        ("EV3-LR-INDEX", _CORE, f"{_CLASS}.index", "anchor"),
        ("EV3-LR-NER-BATCH", _NER, "SpacyNER.batch_ner", "relation"),
        ("EV3-LR-NER-EXTRACT", _NER, "SpacyNER.extract_entities_sentences", "relation"),
        ("EV3-LR-SPARSE", _CORE, f"{_CLASS}._precompute_sparse_matrices", "anchor"),
        ("EV3-LR-SEED", _CORE, f"{_CLASS}.get_seed_entities", "anchor"),
        ("EV3-LR-QUESTION-NER", _NER, "SpacyNER.question_ner", "relation"),
        ("EV3-LR-PROPAGATE", _CORE, f"{_CLASS}.calculate_entity_scores_vectorized", "anchor"),
        ("EV3-LR-PASSAGE", _CORE, f"{_CLASS}.calculate_passage_scores", "anchor"),
        ("EV3-LR-DENSE", _CORE, f"{_CLASS}.dense_passage_retrieval", "relation"),
        ("EV3-LR-SEARCH", _CORE, f"{_CLASS}.graph_search_with_seed_entities", "anchor"),
        ("EV3-LR-PPR", _CORE, f"{_CLASS}.run_ppr", "relation"),
        ("EV3-LR-RETRIEVE", _CORE, f"{_CLASS}.retrieve", "anchor"),
        ("EV3-LR-DENSE-RETURN", _CORE, f"{_CLASS}.dense_passage_retrieval", "relation"),
    )
    return {
        span_id: index.span(span_id, path, symbol, role)  # type: ignore[arg-type]
        for span_id, path, symbol, role in specs
    }


def _relation(
    relation_id: str,
    source: str,
    target: str,
    spans: list[str],
    statement: str,
    relation_type: str = "data_flow",
) -> RelationEvidenceV3:
    return RelationEvidenceV3(
        relation_id=relation_id,
        relation_type=relation_type,  # type: ignore[arg-type]
        source_symbol=source,
        target_symbol=target,
        direct_span_ids=spans,
        statement=statement,
    )


def _packet(
    packet_id: str,
    scope: str,
    spans: list[EvidenceSpanV3],
    anchors: list[str],
    relation_spans: list[str],
    relations: list[RelationEvidenceV3],
    conditions: list[str] | None = None,
) -> EvidencePacketV3:
    return EvidencePacketV3(
        packet_id=packet_id,
        scope=scope,
        anchor_span_ids=anchors,
        relation_span_ids=relation_spans,
        spans=spans,
        relations=relations,
        conditions=conditions or [],
        source_digest=_digest([span.excerpt_digest for span in spans]),
    )


def _packets(snapshot: RepoSnapshot, s: dict[str, EvidenceSpanV3]) -> EvidencePacketSetV3:
    packets = [
        _packet("EP-LR-INDEX", f"{_CORE}:{_CLASS}.index", [s["EV3-LR-INDEX"], s["EV3-LR-NER-BATCH"], s["EV3-LR-NER-EXTRACT"]], ["EV3-LR-INDEX"], ["EV3-LR-NER-BATCH", "EV3-LR-NER-EXTRACT"], [_relation("RV3-LR-INDEX", f"{_CLASS}.index", "SpacyNER.batch_ner/extract_entities_sentences", ["EV3-LR-INDEX", "EV3-LR-NER-BATCH", "EV3-LR-NER-EXTRACT"], "Indexing extracts entities and sentences, embeds them, and materializes entity/passage mappings.", "call_flow")]),
        _packet("EP-LR-SPARSE", f"{_CORE}:{_CLASS}._precompute_sparse_matrices", [s["EV3-LR-SPARSE"]], ["EV3-LR-SPARSE"], [], []),
        _packet("EP-LR-SEED", f"{_CORE}:{_CLASS}.get_seed_entities", [s["EV3-LR-SEED"], s["EV3-LR-QUESTION-NER"]], ["EV3-LR-SEED"], ["EV3-LR-QUESTION-NER"], [_relation("RV3-LR-SEED", "SpacyNER.question_ner", f"{_CLASS}.get_seed_entities", ["EV3-LR-QUESTION-NER", "EV3-LR-SEED"], "Query entities are embedded and matched to stored entities by maximum similarity.")]),
        _packet("EP-LR-PROPAGATE", f"{_CORE}:{_CLASS}.calculate_entity_scores_vectorized", [s["EV3-LR-PROPAGATE"]], ["EV3-LR-PROPAGATE"], [], [], ["only active entities above iteration_threshold continue"]),
        _packet("EP-LR-PASSAGE", f"{_CORE}:{_CLASS}.calculate_passage_scores", [s["EV3-LR-PASSAGE"], s["EV3-LR-DENSE"]], ["EV3-LR-PASSAGE"], ["EV3-LR-DENSE"], [_relation("RV3-LR-PASSAGE", f"{_CLASS}.dense_passage_retrieval", f"{_CLASS}.calculate_passage_scores", ["EV3-LR-DENSE", "EV3-LR-PASSAGE"], "Normalized dense similarity is combined with activated-entity occurrence and tier bonuses.")]),
        _packet("EP-LR-PPR", f"{_CORE}:{_CLASS}.graph_search_with_seed_entities/run_ppr", [s["EV3-LR-SEARCH"], s["EV3-LR-PPR"]], ["EV3-LR-SEARCH"], ["EV3-LR-PPR"], [_relation("RV3-LR-PPR", "entity and passage node weights", f"{_CLASS}.run_ppr", ["EV3-LR-SEARCH", "EV3-LR-PPR"], "Entity and passage weights form the personalized PageRank reset vector and passage scores are sorted descending.")]),
        _packet("EP-LR-RETURN", f"{_CORE}:{_CLASS}.retrieve", [s["EV3-LR-RETRIEVE"], s["EV3-LR-DENSE-RETURN"]], ["EV3-LR-RETRIEVE"], ["EV3-LR-DENSE-RETURN"], [_relation("RV3-LR-FALLBACK", f"{_CLASS}.retrieve", f"{_CLASS}.dense_passage_retrieval", ["EV3-LR-RETRIEVE", "EV3-LR-DENSE-RETURN"], "When query NER yields no seed entity, retrieval uses the dense passage ranking branch.", "control_flow")], ["dense fallback applies only when seed_entities is empty"]),
    ]
    return EvidencePacketSetV3(repo_snapshot_id=snapshot.snapshot_id, project_tree_hash=snapshot.project_tree_hash, packets=packets, content_digest=_digest([packet.model_dump(mode="json") for packet in packets]))


def _fact(
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
        scope=f"{_CORE}:{subject}",
        direct_span_ids=direct,
        relation_evidence_ids=relations or [],
        exact_source_digest=_digest([spans[item].excerpt_digest for item in direct]),
        canonical_identity=_digest({"snapshot": packets.repo_snapshot_id, "subject": subject, "predicate": predicate, "object": obj, "conditions": sorted(conditions)}),
    )


def _facts(packets: EvidencePacketSetV3) -> CodeFactSetV1:
    spans = {span.span_id: span for packet in packets.packets for span in packet.spans}
    specs = [
        ("F-LR-INDEX", f"{_CLASS}.index", "calls_in_order", ["embed passages", "batch NER and sentence extraction", "embed sentences/entities", "build entity-sentence and passage-entity mappings", "add graph edges"], ["EV3-LR-INDEX", "EV3-LR-NER-BATCH", "EV3-LR-NER-EXTRACT"], ["RV3-LR-INDEX"], []),
        ("F-LR-SPARSE", f"{_CLASS}._precompute_sparse_matrices", "constructs", ["entity-to-sentence COO sparse tensor", "sentence-to-entity COO sparse tensor"], ["EV3-LR-SPARSE"], [], []),
        ("F-LR-SEED", f"{_CLASS}.get_seed_entities", "calls_in_order", ["query NER", "normalized query-entity embeddings", "stored/query entity dot products", "per-query-entity argmax", "seed score"], ["EV3-LR-SEED", "EV3-LR-QUESTION-NER"], ["RV3-LR-SEED"], []),
        ("F-LR-THRESHOLD", f"{_CLASS}.calculate_entity_scores_vectorized", "filters_by", "current entity score >= iteration_threshold", ["EV3-LR-PROPAGATE"], [], []),
        ("F-LR-TOPK", f"{_CLASS}.calculate_entity_scores_vectorized", "selects_top_k", "per-active-entity highest-similarity unused sentences", ["EV3-LR-PROPAGATE"], [], ["used_sentence_mask excludes previously selected sentences"]),
        ("F-LR-PROPAGATE", f"{_CLASS}.calculate_entity_scores_vectorized", "calls_in_order", ["entity-to-sentence sparse multiplication", "query-sentence similarity weighting", "selected-sentence masking", "sentence-to-entity sparse multiplication", "dense score accumulation"], ["EV3-LR-PROPAGATE"], [], []),
        ("F-LR-PASSAGE", f"{_CLASS}.calculate_passage_scores", "aggregates", ["normalized dense passage similarity", "activated-entity occurrence and tier bonus", "optional attribute overlap bonus"], ["EV3-LR-PASSAGE", "EV3-LR-DENSE"], ["RV3-LR-PASSAGE"], []),
        ("F-LR-PPR", f"{_CLASS}.run_ppr", "calls_in_order", ["entity plus passage node weights", "nonnegative reset vector", "personalized PageRank", "descending passage score order"], ["EV3-LR-SEARCH", "EV3-LR-PPR"], ["RV3-LR-PPR"], []),
        ("F-LR-FALLBACK", f"{_CLASS}.retrieve", "branches_on", "empty seed entities -> dense passage retrieval; otherwise graph search", ["EV3-LR-RETRIEVE", "EV3-LR-DENSE-RETURN"], ["RV3-LR-FALLBACK"], ["seed_entities is empty"]),
        ("F-LR-RETURN", f"{_CLASS}.retrieve", "returns", ["top-k passage texts", "corresponding branch scores"], ["EV3-LR-RETRIEVE"], [], []),
    ]
    facts = [_fact(packets, spans, *spec) for spec in specs]  # type: ignore[arg-type]
    return CodeFactSetV1(repo_snapshot_id=packets.repo_snapshot_id, project_tree_hash=packets.project_tree_hash, evidence_packet_digest=packets.content_digest, facts=facts, content_digest=_digest([fact.model_dump(mode="json") for fact in facts]))


def _claims(packets: EvidencePacketSetV3, facts: CodeFactSetV1) -> AtomicClaimSetV3:
    by_id = {fact.fact_id: fact for fact in facts.facts}
    specs = [
        ("C-LR-INDEX", "Offline indexing embeds passages, applies batched entity and sentence extraction, embeds the extracted sentences and entities, and builds entity-sentence and passage-entity graph mappings.", ["F-LR-INDEX"], []),
        ("C-LR-SPARSE", "The vectorized retrieval setup constructs separate entity-to-sentence and sentence-to-entity COO sparse tensors from the stored mappings.", ["F-LR-SPARSE"], []),
        ("C-LR-SEED", "At query time, detected query entities are normalized and embedded, compared with stored entity embeddings, and each query entity contributes its maximum-similarity entity and score as a seed.", ["F-LR-SEED"], []),
        ("C-LR-THRESHOLD", "At each propagation iteration, only current entity scores at or above iteration_threshold remain active.", ["F-LR-THRESHOLD"], []),
        ("C-LR-TOPK", "Each active entity independently selects up to top_k_sentence highest-similarity connected sentences that have not already been marked as used.", ["F-LR-TOPK"], ["selection is conditioned on the used-sentence mask"]),
        ("C-LR-PROPAGATE", "Entity scores are propagated through the entity-to-sentence sparse matrix, weighted by query-sentence similarity and the selected-sentence mask, propagated through the sentence-to-entity matrix, and accumulated into dense entity scores.", ["F-LR-PROPAGATE"], []),
        ("C-LR-PASSAGE", "Passage node weights combine normalized dense similarity with activated-entity occurrence and tier bonuses, with an additional attribute-overlap term only on the configured attribute branch.", ["F-LR-PASSAGE"], ["the attribute term is conditional"]),
        ("C-LR-PPR", "For the seeded branch, entity and passage weights form a nonnegative personalized-PageRank reset vector, and passage scores are returned in descending order before top-k truncation.", ["F-LR-PPR", "F-LR-RETURN"], ["when at least one seed entity is available"]),
        ("C-LR-FALLBACK", "When query NER produces no seed entity, retrieve bypasses graph propagation and returns the top-k dense passage ranking and its scores.", ["F-LR-FALLBACK", "F-LR-RETURN"], ["only when seed_entities is empty"]),
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
    gap_topics = [
        ("GAP-LR-EXPONENTIAL", "prevents exponential growth"),
        ("GAP-LR-EFFICIENCY", "improves efficiency or linear scalability"),
        ("GAP-LR-NOISE", "reduces noise"),
        ("GAP-LR-LOSSLESS", "information-lossless construction"),
        ("GAP-LR-QUALITY", "retrieval quality or performance"),
        ("GAP-LR-MAX-EQUATION", "paper compact MAX propagation equation"),
    ]
    gaps = [ExplicitCodeGapV1(gap_id=gap_id, topic=topic, scope="compiled executable retrieval path", rationale="The executable operations support the branch mechanics but do not directly establish this rationale, complexity, empirical, or paper-equation claim.") for gap_id, topic in gap_topics]
    stage_specs = [
        ("S-LR-1", "Offline graph indexing", ["C-LR-INDEX", "C-LR-SPARSE"]),
        ("S-LR-2", "Query seed construction", ["C-LR-SEED"]),
        ("S-LR-3", "Thresholded sparse entity propagation", ["C-LR-THRESHOLD", "C-LR-TOPK", "C-LR-PROPAGATE"]),
        ("S-LR-4", "Hybrid passage initialization", ["C-LR-PASSAGE"]),
        ("S-LR-5", "Graph ranking and dense fallback", ["C-LR-PPR", "C-LR-FALLBACK"]),
    ]
    by_claim = {claim.claim_id: claim for claim in claims}
    groups = [SemanticStageGroupV1(stage_id=stage_id, name=name, purpose=" ".join(by_claim[item].canonical_text for item in claim_ids), ordered_claim_ids=claim_ids, relation_evidence_ids=list(dict.fromkeys(rel for item in claim_ids for rel in by_claim[item].relation_evidence_ids)), organization_priority=priority) for priority, (stage_id, name, claim_ids) in enumerate(stage_specs, start=1)]
    payload = {"claims": [claim.model_dump(mode="json") for claim in claims], "explicit_code_gaps": [gap.model_dump(mode="json") for gap in gaps], "semantic_stage_groups": [group.model_dump(mode="json") for group in groups]}
    return AtomicClaimSetV3(repo_snapshot_id=packets.repo_snapshot_id, project_tree_hash=packets.project_tree_hash, evidence_packet_digest=packets.content_digest, code_fact_digest=facts.content_digest, claims=claims, explicit_code_gaps=gaps, semantic_stage_groups=groups, content_digest=_digest(payload))


__all__ = ["LinearGraphRetrievalProfile"]
