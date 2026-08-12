from __future__ import annotations

from pathlib import Path

import pytest

from code2paper.agentic.authoring_projection import build_authoring_projection
from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.agentic.evidence_compiler_v3 import compile_legacy_profile_evidence_v3
from code2paper.agentic.evidence_profiles.linear_graph_retrieval import (
    LinearGraphRetrievalProfile,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence


CORE = "src/LinearRAG.py"


def _write_fixture(root: Path) -> None:
    (root / "src").mkdir(parents=True)
    (root / CORE).write_text(
        '''
import numpy as np
import torch

class LinearRAG:
    def index(self, passages):
        self.passage_embedding_store.insert_text(passages)
        passage_entities, sentence_entities = self.spacy_ner.batch_ner(passages, self.config.max_workers)
        entity_nodes, sentence_nodes, passage_to_entities, self.entity_to_sentence, self.sentence_to_entity = self.extract_nodes_and_edges(passage_entities, sentence_entities)
        self.sentence_embedding_store.insert_text(list(sentence_nodes))
        self.entity_embedding_store.insert_text(list(entity_nodes))
        self.add_entity_to_passage_edges(passage_to_entities)
        self.add_adjacent_passage_edges()
        self.augment_graph()

    def _precompute_sparse_matrices(self):
        entity_to_sentence_indices = build_indices(self.entity_to_sentence)
        sentence_to_entity_indices = build_indices(self.sentence_to_entity)
        self.entity_to_sentence_sparse = torch.sparse_coo_tensor(entity_to_sentence_indices, values, shape).coalesce()
        self.sentence_to_entity_sparse = torch.sparse_coo_tensor(sentence_to_entity_indices, values, reverse_shape).coalesce()

    def get_seed_entities(self, question):
        question_entities = list(self.spacy_ner.question_ner(question))
        if len(question_entities) == 0:
            return [], [], [], []
        embeddings = self.config.embedding_model.encode(question_entities, normalize_embeddings=True)
        similarities = np.dot(self.entity_embeddings, embeddings.T)
        seed_entity_indices, seed_entity_scores = [], []
        for query_entity_idx in range(len(question_entities)):
            best_entity_idx = np.argmax(similarities[:, query_entity_idx])
            seed_entity_indices.append(best_entity_idx)
            seed_entity_scores.append(similarities[best_entity_idx, query_entity_idx])
        return seed_entity_indices, question_entities, hash_ids(seed_entity_indices), seed_entity_scores

    def calculate_entity_scores_vectorized(self, question_embedding, seed_entity_indices, seed_entities, seed_hash_ids, seed_scores):
        used_sentence_mask = torch.zeros(num_sentences, dtype=torch.bool)
        entity_scores_dense = torch.zeros(num_entities)
        current_entity_scores_dense = torch.where(
            current_entity_scores_dense >= self.config.iteration_threshold,
            current_entity_scores_dense,
            torch.zeros_like(current_entity_scores_dense),
        )
        sentence_activation = torch.sparse.mm(self.entity_to_sentence_sparse.t(), current_scores)
        sentence_activation = torch.where(used_sentence_mask, torch.zeros_like(sentence_activation), sentence_activation)
        if self.config.top_k_sentence > 0:
            top_k_values, top_k_local_indices = torch.topk(sentence_similarities, self.config.top_k_sentence)
            unique_selected_sentences = torch.unique(top_k_local_indices)
            used_sentence_mask[unique_selected_sentences] = True
        weighted_sentence_scores = sentence_activation * sentence_similarities
        next_entity_scores_dense = torch.sparse.mm(self.sentence_to_entity_sparse.t(), weighted_sentence_scores)
        entity_scores_dense += next_entity_scores_dense
        return entity_scores_dense, actived_entities

    def dense_passage_retrieval(self, question_embedding):
        scores = np.dot(self.passage_embeddings, question_embedding.reshape(-1, 1)).flatten()
        indices = np.argsort(scores)[::-1]
        return indices, scores[indices]

    def calculate_passage_scores(self, question, question_embedding, actived_entities):
        passage_weights = np.zeros(num_nodes)
        dpr_passage_indices, dpr_passage_scores = self.dense_passage_retrieval(question_embedding)
        dpr_passage_scores = min_max_normalize(dpr_passage_scores)
        for entity_hash_id, (entity_id, entity_score, tier) in actived_entities.items():
            total_entity_bonus += entity_score * occurrence(entity_hash_id) / max(tier, 1)
        passage_score = self.config.passage_ratio * dpr_passage_score + log(1 + total_entity_bonus)
        passage_weights[passage_node_idx] = passage_score
        return passage_weights

    def graph_search_with_seed_entities(self, question, question_embedding, seed_indices, seeds, seed_hash_ids, seed_scores):
        entity_weights, actived_entities = self.calculate_entity_scores_vectorized(question_embedding, seed_indices, seeds, seed_hash_ids, seed_scores)
        passage_weights = self.calculate_passage_scores(question, question_embedding, actived_entities)
        node_weights = entity_weights + passage_weights
        return self.run_ppr(node_weights)

    def run_ppr(self, node_weights):
        reset_prob = np.where(node_weights < 0, 0, node_weights)
        pagerank_scores = self.graph.personalized_pagerank(vertices=nodes, reset=reset_prob)
        doc_scores = np.array([pagerank_scores[i] for i in self.passage_node_indices])
        sorted_indices = np.argsort(doc_scores)[::-1]
        return passage_ids(sorted_indices), doc_scores[sorted_indices]

    def retrieve(self, questions):
        results = []
        for question in questions:
            seed_indices, seed_entities, seed_hash_ids, seed_scores = self.get_seed_entities(question)
            if len(seed_entities) != 0:
                sorted_passages, sorted_passage_scores = self.graph_search_with_seed_entities(question, embedding, seed_indices, seed_entities, seed_hash_ids, seed_scores)
            else:
                sorted_passages, sorted_passage_scores = self.dense_passage_retrieval(embedding)
            final_passages = sorted_passages[:self.config.retrieval_top_k]
            final_scores = sorted_passage_scores[:self.config.retrieval_top_k]
            results.append((final_passages, final_scores))
        return results
''',
        encoding="utf-8",
    )
    (root / "src/ner.py").write_text(
        '''
class SpacyNER:
    def batch_ner(self, passages, max_workers):
        return merge([self.extract_entities_sentences(doc, key) for key, doc in passages.items()])

    def extract_entities_sentences(self, doc, passage_hash_id):
        sentence_to_entities = {}
        entities = set()
        for ent in doc.ents:
            sentence_to_entities.setdefault(ent.sent.text, []).append(ent.text)
            entities.add(ent.text)
        return {passage_hash_id: list(entities)}, sentence_to_entities

    def question_ner(self, question):
        return {ent.text.lower() for ent in self.spacy_model(question).ents}
''',
        encoding="utf-8",
    )


def test_profile_compiles_atomic_sparse_retrieval_path(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    result = compile_legacy_profile_evidence_v3(build_repo_snapshot(tmp_path))
    assert result is not None
    assert result.profile_id == "sparse_entity_sentence_ppr_retrieval"
    assert [packet.packet_id for packet in result.packets.packets] == [
        "EP-LR-INDEX", "EP-LR-SPARSE", "EP-LR-SEED", "EP-LR-PROPAGATE",
        "EP-LR-PASSAGE", "EP-LR-PPR", "EP-LR-RETURN",
    ]
    assert len(result.claims.claims) == 9
    assert len(result.claims.semantic_stage_groups) == 5
    assert len(result.claims.explicit_code_gaps) == 6
    assert len({claim.canonical_identity for claim in result.claims.claims}) == 9
    assert max(len(claim.direct_evidence_ids) for claim in result.claims.claims) <= 3
    fallback = next(claim for claim in result.claims.claims if claim.claim_id == "C-LR-FALLBACK")
    assert fallback.required_qualifiers == ["only when seed_entities is empty"]


def test_projection_is_prose_first_and_excludes_rationale_gaps(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    result = compile_legacy_profile_evidence_v3(build_repo_snapshot(tmp_path))
    assert result is not None
    evidence = MethodEvidence(project_id="fixture", method_name="Sparse retrieval", method_goal="Describe code.", implementation_scope="fixture")
    claims = ClaimEvidenceMap(claims=[])
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
        atomic_claims_v3=result.claims,
        evidence_packets_v3=result.packets,
    )
    assert projection.safe_equations == []
    assert len(projection.projected_claims) == 9
    assert len(projection.forbidden_claims) == 6
    positive = " ".join(item.supported_fragment for item in projection.projected_claims).lower()
    for unsupported in ("exponential growth", "linear scalability", "reduces noise", "information-lossless"):
        assert unsupported not in positive


@pytest.mark.parametrize(
    ("old", "new", "missing"),
    [
        ("iteration_threshold", "removed_threshold", "threshold_topk_masked_sparse_propagation"),
        ("torch.topk", "removed_topk", "threshold_topk_masked_sparse_propagation"),
        ("used_sentence_mask[unique_selected_sentences] = True", "pass", "threshold_topk_masked_sparse_propagation"),
        ("entity_scores_dense += next_entity_scores_dense", "entity_scores_dense = next_entity_scores_dense", "threshold_topk_masked_sparse_propagation"),
        ("np.argsort(doc_scores)[::-1]", "np.argsort(doc_scores)", "personalized_pagerank_descending"),
    ],
)
def test_required_operation_mutation_disables_claim(
    tmp_path: Path, old: str, new: str, missing: str
) -> None:
    _write_fixture(tmp_path)
    path = tmp_path / CORE
    source = path.read_text(encoding="utf-8")
    assert old in source
    path.write_text(source.replace(old, new), encoding="utf-8")
    match = LinearGraphRetrievalProfile().match(build_repo_snapshot(tmp_path))
    assert missing in match.missing_required_fingerprints
    assert compile_legacy_profile_evidence_v3(build_repo_snapshot(tmp_path)) is None


def test_paper_rationale_and_project_name_cannot_activate_profile(tmp_path: Path) -> None:
    (tmp_path / "paperdraft.md").write_text(
        "LinearRAG Tri-Graph pruning prevents exponential growth, improves efficiency, and reduces noise.",
        encoding="utf-8",
    )
    assert compile_legacy_profile_evidence_v3(build_repo_snapshot(tmp_path)) is None
