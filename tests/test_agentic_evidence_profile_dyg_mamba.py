from __future__ import annotations

from pathlib import Path

from code2paper.agentic.authoring_projection import build_authoring_projection
from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.agentic.evidence_compiler_v3 import compile_evidence_v3
from code2paper.agentic.evidence_profiles.dynamic_graph_mamba import (
    DynamicGraphMambaProfile,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence


MODEL = "models/DyGMamba.py"


def _write_fixture(root: Path) -> None:
    (root / "models").mkdir(parents=True)
    (root / MODEL).write_text(
        '''
import torch
import torch.nn.functional as F

class DyGMamba:
    def compute_src_dst_node_temporal_embeddings(self, src_node_ids, dst_node_ids, node_interact_times, edge_ids):
        src_history = self.neighbor_sampler.get_all_first_hop_neighbors(src_node_ids, node_interact_times)
        dst_history = self.neighbor_sampler.get_all_first_hop_neighbors(dst_node_ids, node_interact_times)
        src_ids, src_edges, src_times = self.pad_sequences(*src_history)
        dst_ids, dst_edges, dst_times = self.pad_sequences(*dst_history)
        src_node, src_edge, src_time = self.get_features(node_interact_times, src_ids, src_edges, src_times, self.time_encoder)
        dst_node, dst_edge, dst_time = self.get_features(node_interact_times, dst_ids, dst_edges, dst_times, self.time_encoder)
        src_co, dst_co = self.neighbor_co_occurrence_encoder(src_ids, dst_ids)
        src_dt = self.projection_dt(self.get_dt_features(src_times, src_ids, self.dt_time_encoder))
        dst_dt = self.projection_dt(self.get_dt_features(dst_times, dst_ids, self.dt_time_encoder))
        src_node = self.projection_layer['node'](src_node)
        src_edge = self.projection_layer['edge'](src_edge)
        src_time = self.projection_layer['time'](src_time)
        src_co = self.projection_layer['neighbor_co_occurrence'](src_co)
        dst_node = self.projection_layer['node'](dst_node)
        dst_edge = self.projection_layer['edge'](dst_edge)
        dst_time = self.projection_layer['time'](dst_time)
        dst_co = self.projection_layer['neighbor_co_occurrence'](dst_co)
        src_padded_data = torch.stack([src_node, src_edge, src_time, src_co], dim=2).reshape(batch, src_len, -1)
        dst_padded_data = torch.stack([dst_node, dst_edge, dst_time, dst_co], dim=2).reshape(batch, dst_len, -1)
        for encoder in self.encoders:
            src_padded_data = encoder(src_padded_data, dts=src_padded_dt_features)
            dst_padded_data = encoder(dst_padded_data, dts=dst_padded_dt_features)
        src_padded_data = self.cross_linear_attention(src_padded_data, dst_padded_data)
        dst_padded_data = self.cross_linear_attention(dst_padded_data, src_padded_data)
        src_router_logits = self.src_gate(src_padded_data)
        dst_router_logits = self.dst_gate(dst_padded_data)
        src_routing_weights = F.softmax(src_router_logits, dim=1)
        dst_routing_weights = F.softmax(dst_router_logits, dim=1)
        src_routing_weights, src_selected = torch.topk(src_routing_weights, self.top_k, dim=1)
        dst_routing_weights, dst_selected = torch.topk(dst_routing_weights, self.top_k, dim=1)
        src_routing_weights /= src_routing_weights.sum(dim=1, keepdim=True)
        dst_routing_weights /= dst_routing_weights.sum(dim=1, keepdim=True)
        src_routing_weights_expand = scatter(src_selected, src_routing_weights)
        dst_routing_weights_expand = scatter(dst_selected, dst_routing_weights)
        src_padded_data = (src_padded_data * src_routing_weights_expand).sum(1)
        dst_padded_data = (dst_padded_data * dst_routing_weights_expand).sum(1)
        return self.output_layer(src_padded_data), self.output_layer(dst_padded_data)

    def pad_sequences(self, nodes_neighbor_ids_list, nodes_edge_ids_list, nodes_neighbor_times_list):
        return pad(nodes_neighbor_ids_list), pad(nodes_edge_ids_list), pad(nodes_neighbor_times_list)

    def get_features(self, node_interact_times, ids, edges, times, time_encoder):
        return self.node_raw_features[ids], self.edge_raw_features[edges], time_encoder(node_interact_times - times)

    def get_dt_features(self, times, ids, time_encoder):
        t_seq = times[:, 0] - times[:, 1] + 1e-6
        dt = clip(insert(diff(times), 0, 1), 0, max(t_seq)) / t_seq
        features = time_encoder(dt)
        features[ids == 0] = 0
        return features

class NeighborCooccurrenceEncoder:
    def forward(self, src_ids, dst_ids):
        return self.encode(src_ids), self.encode(dst_ids)

class MambaEncoder:
    def forward(self, hidden_states, inference_params=None, dts=None):
        for layer in self.layers:
            hidden_states, residual = layer(hidden_states, dts=dts)
        return hidden_states

class CrossAttention:
    def forward(self, x, context=None):
        return linear_attn(self.to_q(x), self.to_k(context), self.to_v(context))
''',
        encoding="utf-8",
    )
    (root / "models/mamba_simple.py").write_text(
        '''
import torch

class MambaTimeDelta:
    def forward(self, hidden_states, inference_params=None, dts=None):
        xz = self.in_proj(hidden_states)
        A = -torch.exp(self.A_log.float())
        x, z = xz.chunk(2, dim=1)
        x = self.act(self.conv1d(x))
        if self.time_mamba and dts != None:
            dts_x_dbl = self.x_proj(dts)
            dt, B, C = torch.split(dts_x_dbl, [self.dt_rank, self.d_state, self.d_state], dim=-1)
        y = selective_scan_fn(x, dt, A, B, C, self.D, z=z)
        return self.out_proj(y)
''',
        encoding="utf-8",
    )
    (root / "models/modules.py").write_text(
        '''
class MergeLayer:
    def forward(self, input_1, input_2):
        return self.linear_output(self.linear_hidden(concat(input_1, input_2)))
''',
        encoding="utf-8",
    )
    (root / "train_link_prediction.py").write_text(
        '''
link_predictor = MergeLayer(input_dim1=dim, input_dim2=dim, hidden_dim=dim, output_dim=1)
model = nn.Sequential(dynamic_backbone, link_predictor)
loss_func = nn.BCELoss()

batch_src_node_embeddings, batch_dst_node_embeddings = model[0].compute_src_dst_node_temporal_embeddings(src, dst, times, edges)
positive_probabilities = model[1](input_1=batch_src_node_embeddings, input_2=batch_dst_node_embeddings).sigmoid()
negative_probabilities = model[1](input_1=batch_neg_src_node_embeddings, input_2=batch_neg_dst_node_embeddings).sigmoid()
predicts = torch.cat([positive_probabilities, negative_probabilities])
labels = torch.cat([ones, zeros])
loss = loss_func(input=predicts, target=labels)
''',
        encoding="utf-8",
    )


def test_profile_compiles_time_conditioned_path_and_conflict_gaps(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    result = compile_evidence_v3(build_repo_snapshot(tmp_path))
    assert result is not None
    assert result.profile_id == "temporal_graph_time_conditioned_sequence"
    assert [packet.packet_id for packet in result.packets.packets] == [
        "EP-DYG-HISTORY",
        "EP-DYG-CHANNELS",
        "EP-DYG-DELTAT",
        "EP-DYG-SSM",
        "EP-DYG-READOUT",
        "EP-DYG-TASK",
    ]
    assert len(result.claims.claims) == 9
    assert {
        "C-DYG-SSM-PROJECTION",
        "C-DYG-SSM-PARAMETERS",
        "C-DYG-SSM-SCAN",
    }.issubset({claim.claim_id for claim in result.claims.claims})
    assert len(result.claims.semantic_stage_groups) == 5
    assert max(len(claim.direct_evidence_ids) for claim in result.claims.claims) <= 3
    positive = " ".join(claim.canonical_text for claim in result.claims.claims).lower()
    assert "mean pooling" not in positive
    assert "spectral" not in positive
    gaps = {gap.gap_id for gap in result.claims.explicit_code_gaps}
    assert {"GAP-DYG-SPECTRAL", "GAP-DYG-MEAN", "GAP-DYG-PAPER-TIMESPAN", "GAP-DYG-PERFORMANCE"} == gaps


def test_projection_keeps_conflicts_out_of_positive_prose(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    result = compile_evidence_v3(build_repo_snapshot(tmp_path))
    assert result is not None
    evidence = MethodEvidence(project_id="fixture", method_name="Temporal model", method_goal="Describe code.", implementation_scope="fixture")
    claim_map = ClaimEvidenceMap(claims=[])
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claim_map,
        verification=build_claim_verification_report(evidence, claim_map),
        atomic_claims_v3=result.claims,
        evidence_packets_v3=result.packets,
    )
    assert projection.safe_equations == []
    assert len(projection.stage_packets) == 5
    assert len(projection.forbidden_claims) == 4
    assert "mean pooling" not in " ".join(item.supported_fragment for item in projection.projected_claims).lower()


def test_removing_dts_delivery_disables_time_conditioned_profile(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    path = tmp_path / MODEL
    path.write_text(
        path.read_text(encoding="utf-8")
        .replace("encoder(src_padded_data, dts=src_padded_dt_features)", "encoder(src_padded_data)")
        .replace("encoder(dst_padded_data, dts=dst_padded_dt_features)", "encoder(dst_padded_data)"),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    match = DynamicGraphMambaProfile().match(snapshot)
    assert "elapsed_time_to_encoder_dts" in match.missing_required_fingerprints
    assert compile_evidence_v3(snapshot) is None


def test_removing_topk_or_renormalization_disables_readout_claim(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    path = tmp_path / MODEL
    path.write_text(
        path.read_text(encoding="utf-8")
        .replace("torch.topk", "removed_topk")
        .replace("src_routing_weights /= src_routing_weights.sum", "src_routing_weights = src_routing_weights"),
        encoding="utf-8",
    )
    match = DynamicGraphMambaProfile().match(build_repo_snapshot(tmp_path))
    assert "gated_topk_renormalized_readout" in match.missing_required_fingerprints


def test_paper_only_conflict_language_cannot_activate_profile(tmp_path: Path) -> None:
    (tmp_path / "paperdraft.md").write_text(
        "DyG-Mamba uses spectral normalization, MEAN pooling, robust continuous states, and low complexity.",
        encoding="utf-8",
    )
    assert compile_evidence_v3(build_repo_snapshot(tmp_path)) is None
