from __future__ import annotations

from pathlib import Path
import json

from code2paper.agentic.authoring_projection import build_authoring_projection
from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.agentic.evidence_compiler_v3 import (
    compile_legacy_profile_evidence_v3,
    validate_evidence_compiler_v3,
    write_compiler_v3_artifacts,
)
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.graph_text_trust_nodes import packet_binding_repair_node
from code2paper.agentic.evidence_profiles.registry import (
    default_evidence_profile_registry,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot, write_repo_snapshot
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence


MODEL = "src/model/ebcar_dedicated_attention_model.py"
ATTENTION = "src/model/transformer_encoder_hybrid_attention.py"


def _write_fixture(root: Path) -> None:
    (root / "src/model").mkdir(parents=True)
    (root / MODEL).write_text(
        '''
import torch

class EBCarRerankerHybridAttention:
    def __init__(self, cfg, device):
        self.cfg = cfg
        self.device = device
        self.document_id_embedding = Embedding(cfg.retrieval.top_k, cfg.d_model)
        table = self.get_passage_positional_encoding(torch.tensor([[0, 1]]))
        self.passage_id_embedding = Embedding.from_pretrained(table, freeze=True)

    def get_passage_positional_encoding(self, input_ids):
        positions = torch.arange(input_ids.shape[1])
        div_term = torch.exp(torch.arange(0, self.cfg.d_model, 2))
        positional_encoding = torch.zeros(1, input_ids.shape[1], self.cfg.d_model)
        positional_encoding[:, :, 0::2] = torch.sin(positions.unsqueeze(1) * div_term)
        positional_encoding[:, :, 1::2] = torch.cos(positions.unsqueeze(1) * div_term)
        return torch.nn.functional.normalize(positional_encoding, p=2, dim=2)

    def forward(self, query, passages, labels, document_id, passage_id, passage_text):
        query = query.unsqueeze(1)
        if self.cfg.add_positional_encoding:
            document_id_embeddings = self.document_id_embedding(document_id)
            passage_id_embeddings = self.passage_id_embedding(passage_id)
            passages = passages + document_id_embeddings + passage_id_embeddings
        concat_embeddings = torch.cat((query, passages), dim=1)
        dedicated_attention_mask = torch.zeros((passages.shape[0], passages.shape[1] + 1, passages.shape[1] + 1))
        if self.cfg.use_dedicated_attention:
            for i in range(passages.shape[0]):
                temp_document_id = document_id[i]
                for row, doc_id in enumerate(temp_document_id):
                    dedicated_attention_mask[i, row, :] = -float("inf")
                    temp_indices = temp_document_id == doc_id
                    temp_indices = torch.cat((torch.tensor([True]), temp_indices))
                    dedicated_attention_mask[i, row, temp_indices] = 0
        outputs = self.model(concat_embeddings, dedicated_attention_mask.unsqueeze(1))
        passage_embeddings = outputs[:, 1:, :]
        similarities = torch.matmul(query, passage_embeddings.transpose(-2, -1)).squeeze(1)
        similarities = similarities / self.cfg.temperature
        losses = []
        for i in range(similarities.shape[0]):
            pos_mask = labels[i] == 1
            neg_mask = labels[i] == 0
            assert torch.sum(pos_mask) == 1
            pos_sim = similarities[i][pos_mask]
            neg_sims = similarities[i][neg_mask]
            all_sims = torch.cat([pos_sim, neg_sims])
            losses.append(-pos_sim + torch.logsumexp(all_sims, dim=0))
        return torch.stack(losses).mean()

    def rerank(self, query, passages, document_id, passage_id, passage_text):
        query = query.unsqueeze(1)
        if self.cfg.add_positional_encoding:
            document_id_embeddings = self.document_id_embedding(document_id)
            passage_id_embeddings = self.passage_id_embedding(passage_id)
            passages = passages + document_id_embeddings + passage_id_embeddings
        dedicated_attention_mask = torch.zeros((passages.shape[0], passages.shape[1] + 1, passages.shape[1] + 1))
        for i in range(passages.shape[0]):
            temp_document_id = document_id[i]
            for row, doc_id in enumerate(temp_document_id):
                dedicated_attention_mask[i, row, :] = -float("inf")
                temp_indices = temp_document_id == doc_id
                temp_indices = torch.cat((torch.tensor([True]), temp_indices))
                dedicated_attention_mask[i, row, temp_indices] = 0
        outputs = self.model(torch.cat((query, passages), dim=1), dedicated_attention_mask.unsqueeze(1))
        passage_embeddings = outputs[:, 1:, :]
        similarities = torch.matmul(query, passage_embeddings.transpose(-2, -1)).squeeze(1)
        similarities = similarities / self.cfg.temperature
        relevance_scores, indices = torch.sort(similarities, dim=1, descending=True)
        reranked_passages = [[passage_text[i][j] for j in indices[i]] for i in range(len(indices))]
        return reranked_passages, relevance_scores
''',
        encoding="utf-8",
    )
    (root / ATTENTION).write_text(
        '''
import torch

class MultiheadAttention:
    def forward(self, x, attn_mask=None, key_padding_mask=None, causal_mask=False):
        Q, K, V = self.q_proj(x), self.k_proj(x), self.v_proj(x)
        attn_logits = torch.matmul(Q, K.transpose(-2, -1)) / (self.head_dim ** 0.5)
        if attn_mask is not None:
            attn_logits += attn_mask
        attn_weights = softmax(attn_logits, dim=-1)
        return torch.matmul(attn_weights, V)

class TransformerEncoderLayerHybridAttention:
    def forward(self, src, attn_mask=None, key_padding_mask=None, causal_mask=False):
        src2 = self.norm1(src)
        shared_out = self.shared_attn(src2, None, key_padding_mask, causal_mask)
        dedicated_out = self.dedicated_attn(src2, attn_mask, key_padding_mask, causal_mask)
        src = src + self.dropout1(shared_out + dedicated_out)
        src2 = self.linear2(self.linear1(self.norm2(src)))
        return src + self.dropout2(src2)
''',
        encoding="utf-8",
    )
    (root / "src/evaluate.py").write_text(
        '''
def evaluate_EBCAR(cfg):
    with torch.no_grad():
        reranked_passages, scores = reranker.rerank(
            query_embedding, document_embeddings, document_ids, passage_ids, documents
        )
    return reranked_passages, scores
''',
        encoding="utf-8",
    )


def test_profile_compiles_four_supported_semantic_stages(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    result = compile_legacy_profile_evidence_v3(snapshot)
    assert result is not None
    assert result.profile_id == "hybrid_attention_context_reranker"
    assert [packet.packet_id for packet in result.packets.packets] == [
        "EP-EMBED-STRUCTURE",
        "EP-HYBRID-ATTN",
        "EP-CONTRASTIVE",
        "EP-RERANK",
    ]
    assert len(result.claims.claims) == 9
    assert {"C-EBC-SHARED-ATTENTION", "C-EBC-DEDICATED-ATTENTION"}.issubset(
        {claim.claim_id for claim in result.claims.claims}
    )
    assert [group.name for group in result.claims.semantic_stage_groups] == [
        "Embedding and structural augmentation",
        "Hybrid context encoder",
        "Contrastive objective",
        "Inference reranking",
    ]
    assert not validate_evidence_compiler_v3(result, snapshot)
    assert max(len(claim.direct_evidence_ids) for claim in result.claims.claims) <= 3
    assert all(
        len(set(packet.anchor_span_ids + packet.relation_span_ids + packet.semantic_span_ids)) <= 3
        or packet.composition_rationale
        for packet in result.packets.packets
    )


def test_v3_projection_is_prose_first_and_has_no_equations(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    result = compile_legacy_profile_evidence_v3(build_repo_snapshot(tmp_path))
    assert result is not None
    evidence = MethodEvidence(
        project_id="fixture",
        method_name="Hybrid reranker",
        method_goal="Describe executable reranking.",
        implementation_scope="fixture",
    )
    claims = ClaimEvidenceMap(claims=[])
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
        atomic_claims_v3=result.claims,
        evidence_packets_v3=result.packets,
    )
    assert projection.hard_gate_passed
    assert projection.safe_equations == []
    assert len(projection.stage_packets) == 4
    assert len({claim.supported_fragment for claim in projection.projected_claims}) == 9


def test_legacy_text_stage_cannot_recompile_packet_with_profile_authority(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    run_root = tmp_path / "run"
    _write_fixture(project)
    snapshot = build_repo_snapshot(project)
    fresh = compile_legacy_profile_evidence_v3(snapshot)
    assert fresh is not None

    target = fresh.packets.packets[0]
    corrupted_target = target.model_copy(
        update={"conditions": [*target.conditions, "corrupted-test-condition"]}
    )
    corrupted_packets = fresh.packets.model_copy(
        update={
            "packets": [
                corrupted_target,
                *fresh.packets.packets[1:],
            ]
        }
    )
    corrupted = fresh.model_copy(update={"packets": corrupted_packets})
    artifacts = write_compiler_v3_artifacts(run_root / "artifacts", corrupted)
    snapshot_path = write_repo_snapshot(run_root / "repo_snapshot.json", snapshot)
    evidence_path = run_root / "method_evidence.json"
    evidence_path.write_text(MethodEvidence(
        project_id="fixture",
        method_name="Hybrid reranker",
        method_goal="Describe executable reranking.",
        implementation_scope="fixture",
    ).model_dump_json(indent=2), encoding="utf-8")
    request_path = run_root / "packet_repair_requests.json"
    request_path.write_text(json.dumps({
        "attempt": 1,
        "requests": [{
            "claim_id": fresh.claims.claims[0].claim_id,
            "packet_id": target.packet_id,
            "failure_type": "wrong_span_role",
            "offending_span_ids": target.anchor_span_ids,
            "missing_relation_type": "",
            "requested_scope": "packet_relation",
            "attempt": 1,
        }],
    }), encoding="utf-8")
    state = AgenticRunState(
        project_root=project,
        out_root=run_root,
        artifacts={
            **artifacts,
            "repo_snapshot": str(snapshot_path),
            "evidence": str(evidence_path),
            "packet_repair_requests_v1": str(request_path),
        },
    )

    repaired = AgenticRunState.model_validate(
        packet_binding_repair_node(state.model_dump(mode="json"))
    )
    assert repaired.next_node == "blocked"
    assert (
        repaired.blocked_reason
        == "packet_scoped_repair_requires_research_owner"
    )


def test_same_document_mask_mutation_prevents_attention_claims(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    path = tmp_path / MODEL
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "temp_document_id == doc_id",
            "torch.zeros_like(temp_document_id, dtype=torch.bool)",
        ),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    profile, matches = default_evidence_profile_registry().select(snapshot)
    assert profile is None
    ebcar_match = next(item for item in matches if item.profile_id == "hybrid_attention_context_reranker")
    assert "same_document_query_mask" in ebcar_match.missing_required_fingerprints
    assert compile_legacy_profile_evidence_v3(snapshot) is None


def test_ascending_sort_mutation_prevents_rerank_claim(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    path = tmp_path / MODEL
    path.write_text(
        path.read_text(encoding="utf-8").replace("descending=True", "descending=False"),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_legacy_profile_evidence_v3(snapshot) is None


def test_project_name_and_paper_prose_cannot_activate_profile(tmp_path: Path) -> None:
    (tmp_path / "paperdraft.md").write_text(
        "EBCAR uses document IDs, hybrid attention, InfoNCE, and descending reranking.",
        encoding="utf-8",
    )
    assert compile_legacy_profile_evidence_v3(build_repo_snapshot(tmp_path)) is None
