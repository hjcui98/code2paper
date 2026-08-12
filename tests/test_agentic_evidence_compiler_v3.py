from __future__ import annotations

from pathlib import Path

from code2paper.agentic.authoring_projection import build_authoring_projection
from code2paper.agentic.evidence_compiler_v3 import (
    compile_evidence_v3,
    compile_legacy_profile_evidence_v3,
    validate_evidence_compiler_v3,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.core.schemas import MethodEvidence


def _write_fixture(root: Path) -> None:
    (root / "utils").mkdir(parents=True)
    (root / "prune_percent.py").write_text(
        """import torch
import numpy as np
from utils.net_utils import PrunePredictor
def prune_pure_feature(args):
    gaussians.load_ply(args.ply_path)
    predictor = PrunePredictor(input_dim=args.input_dim)
    predictor.load_model(args.net_weights_path, args.data_device)
    gaussians.get_prune_input_f15(args.knn_k, args.knn_method)
    scores = predictor(gaussians.prune_features)[:, 0]
    N = gaussians.get_point_number()
    keep_num = int(N * args.keep_percent)
    sorted_indices = scores.argsort(descending=True)
    keep_indices = sorted_indices[:keep_num]
    valid_mask = torch.zeros(N, dtype=torch.bool)
    valid_mask[keep_indices] = True
    gaussians.prune_points(valid_mask)
    gaussians.save_ply(args.output_ply_path)
    np.save(args.output_ply_path.replace('.ply', '.npy'), scores.numpy())
""",
        encoding="utf-8",
    )
    (root / "utils" / "net_utils.py").write_text(
        """import torch
import torch.nn as nn
class PrunePredictor:
    def __init__(self, input_dim=15, use_softmax=True):
        layers = [nn.Linear(input_dim, 32), nn.Linear(32, 2)]
        if use_softmax:
            layers.append(nn.Softmax(dim=1))
        self.model = nn.Sequential(*layers)
    def forward(self, x):
        return self.model(x)
    def load_model(self, load_path, device):
        self.load_state_dict(torch.load(load_path, map_location=device))
""",
        encoding="utf-8",
    )
    (root / "utils" / "gaussian_model.py").write_text(
        """import torch
class GaussianModel:
    def save_ply(self, path):
        PlyData([el]).write(path)
    def get_prune_input_f15(self, knn_k, knn_method='ivf'):
        positions = self.get_xyz
        opacities = self.get_opacity
        scales = self.get_scaling
        shs = self.get_features
        shs_dc = self.get_features_dc
        a = compute_knn_z_score(positions, knn_k)
        b = z_score_tensor(opacities)
        c = torch.sort(scales)
        d = torch.prod(scales)
        input_features = torch.cat((a, b, c, d))
        self.prune_features = percentile_cutoff_normalize(input_features)
    def prune_points(self, valid_mask):
        self._xyz = self._xyz[valid_mask]
        self._features_dc = self._features_dc[valid_mask]
        self._features_rest = self._features_rest[valid_mask]
        self._scaling = self._scaling[valid_mask]
        self._rotation = self._rotation[valid_mask]
        self._opacity = self._opacity[valid_mask]
""",
        encoding="utf-8",
    )
    (root / "utils" / "feature_utils.py").write_text(
        """def compute_sh_anisotropy_loop(x): return x
def compute_sh_anisotropy_loop_std(x): return x
def compute_knn_z_score(x, indices): return x
def z_score_tensor(x): return x
def percentile_cutoff_normalize(x): return x
""",
        encoding="utf-8",
    )


def test_canonical_snapshot_only_entrypoint_cannot_authorize_profile_facts(
    tmp_path: Path,
) -> None:
    _write_fixture(tmp_path)
    assert compile_evidence_v3(build_repo_snapshot(tmp_path)) is None


def test_v3_compiles_packets_facts_claims_and_gaps_from_executable_behavior(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    result = compile_legacy_profile_evidence_v3(snapshot)

    assert result is not None
    assert validate_evidence_compiler_v3(result, snapshot) == []
    assert [item.packet_id for item in result.packets.packets] == [
        "EP-RAP-FEATURE", "EP-RAP-PREDICTOR", "EP-RAP-PRUNE"
    ]
    assert len(result.facts.facts) >= 13
    assert len(result.claims.claims) == len({item.canonical_identity for item in result.claims.claims}) == 8
    assert {item.topic for item in result.claims.explicit_code_gaps} >= {
        "soft pruning", "three-loss and entropy objectives"
    }
    feature = result.packets.packets[0]
    assert feature.anchor_span_ids == ["EV3-FEATURE"]
    assert len(feature.spans) == 4
    assert feature.composition_rationale
    assert all("wrong_span_role" in item.reason for item in feature.rejected_candidates)


def test_v3_projection_replaces_legacy_wide_claims_and_groups_semantic_stages(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    result = compile_legacy_profile_evidence_v3(snapshot)
    assert result is not None
    method = MethodEvidence(
        project_id="fixture",
        method_name="Typed pruning",
        method_goal="Describe typed pruning inference",
        implementation_scope="inference",
    )
    # The V3 branch does not consume legacy claim wording; minimal placeholders
    # make that precedence explicit.
    from code2paper.core.schemas import ClaimEvidenceMap
    from code2paper.agentic.claim_verifier import ClaimVerificationReport
    projection = build_authoring_projection(
        method_evidence=method,
        claim_map=ClaimEvidenceMap(claims=[]),
        verification=ClaimVerificationReport(
            checked_claims=0, hard_gate_passed=True,
        ),
        atomic_claims_v3=result.claims,
        evidence_packets_v3=result.packets,
    )

    assert projection.hard_gate_passed
    assert len(projection.projected_claims) == 8
    assert [item["name"] for item in projection.stage_packets] == [
        "Per-primitive feature representation",
        "Predictor loading and score inference",
        "Score-based retention and artifact output",
    ]
    assert "two logits" in projection.projected_claims[2].supported_fragment
    assert any(item.claim_id == "GAP-RAP-LOSSES" for item in projection.forbidden_claims)
