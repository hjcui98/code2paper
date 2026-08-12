#!/usr/bin/env python3
"""Verify that matched profiles are discovery-only on the production route."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2paper.agentic.evidence_compiler_v3 import (
    GENERIC_RESEARCH_PRODUCER_VERSION,
    compile_evidence_v3,
    compile_legacy_profile_evidence_v3,
)
from code2paper.agentic.evidence_profiles.registry import default_evidence_profile_registry
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.tool_runtime import atomic_write_json


def _write_matching_fixture(root: Path) -> None:
    (root / "utils").mkdir(parents=True)
    files = {
        "prune_percent.py": "import torch\nimport numpy as np\nfrom utils.net_utils import PrunePredictor\ndef prune_pure_feature(args):\n    gaussians.load_ply(args.ply_path)\n    predictor = PrunePredictor(input_dim=args.input_dim)\n    predictor.load_model(args.net_weights_path, args.data_device)\n    gaussians.get_prune_input_f15(args.knn_k, args.knn_method)\n    scores = predictor(gaussians.prune_features)[:, 0]\n    N = gaussians.get_point_number()\n    keep_num = int(N * args.keep_percent)\n    sorted_indices = scores.argsort(descending=True)\n    keep_indices = sorted_indices[:keep_num]\n    valid_mask = torch.zeros(N, dtype=torch.bool)\n    valid_mask[keep_indices] = True\n    gaussians.prune_points(valid_mask)\n    gaussians.save_ply(args.output_ply_path)\n    np.save(args.output_ply_path.replace('.ply', '.npy'), scores.numpy())\n",
        "utils/net_utils.py": "import torch\nimport torch.nn as nn\nclass PrunePredictor:\n    def __init__(self, input_dim=15, use_softmax=True):\n        layers = [nn.Linear(input_dim, 32), nn.Linear(32, 2)]\n        if use_softmax:\n            layers.append(nn.Softmax(dim=1))\n        self.model = nn.Sequential(*layers)\n    def forward(self, x):\n        return self.model(x)\n    def load_model(self, load_path, device):\n        self.load_state_dict(torch.load(load_path, map_location=device))\n",
        "utils/gaussian_model.py": "import torch\nclass GaussianModel:\n    def save_ply(self, path):\n        PlyData([el]).write(path)\n    def get_prune_input_f15(self, knn_k, knn_method='ivf'):\n        positions = self.get_xyz\n        opacities = self.get_opacity\n        scales = self.get_scaling\n        shs = self.get_features\n        shs_dc = self.get_features_dc\n        a = compute_knn_z_score(positions, knn_k)\n        b = z_score_tensor(opacities)\n        c = torch.sort(scales)\n        d = torch.prod(scales)\n        input_features = torch.cat((a, b, c, d))\n        self.prune_features = percentile_cutoff_normalize(input_features)\n    def prune_points(self, valid_mask):\n        self._xyz = self._xyz[valid_mask]\n",
        "utils/feature_utils.py": "def compute_sh_anisotropy_loop(x): return x\ndef compute_sh_anisotropy_loop_std(x): return x\ndef compute_knn_z_score(x, indices): return x\ndef z_score_tensor(x): return x\ndef percentile_cutoff_normalize(x): return x\n",
    }
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def evaluate() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="code2paper-d2-profile-authority-") as tmp:
        root = Path(tmp)
        _write_matching_fixture(root)
        snapshot = build_repo_snapshot(root)
        registry = default_evidence_profile_registry()
        discovery, matches = registry.select(snapshot)
        legacy, _ = registry.select_legacy(snapshot)
        canonical = compile_evidence_v3(snapshot)
        legacy_result = compile_legacy_profile_evidence_v3(snapshot)
        selected_match = next((item for item in matches if item.matched), None)
        invariants = {
            "profile_match_is_source_fingerprint": bool(
                discovery is not None and selected_match is not None
                and selected_match.matched
                and selected_match.missing_required_fingerprints == []
            ),
            "production_view_has_no_compile_authority": bool(
                discovery is not None and not hasattr(discovery, "compile")
            ),
            "canonical_snapshot_only_compile_disabled": canonical is None,
            "legacy_route_is_explicit": bool(
                discovery is not None and legacy is not None
                and discovery.profile_id == legacy.profile_id
                and hasattr(legacy, "_compile_legacy")
                and not hasattr(legacy, "compile")
            ),
            "legacy_result_not_generic_authority": bool(
                legacy_result is not None
                and legacy_result.packets.producer_version != GENERIC_RESEARCH_PRODUCER_VERSION
                and legacy_result.facts.producer_version != GENERIC_RESEARCH_PRODUCER_VERSION
                and legacy_result.claims.producer_version != GENERIC_RESEARCH_PRODUCER_VERSION
            ),
        }
        return {
            "schema_version": "d2_profile_authority_acceptance_v1",
            "status": "passed" if all(invariants.values()) else "failed",
            "snapshot": {
                "repo_snapshot_id": snapshot.snapshot_id,
                "project_tree_hash": snapshot.project_tree_hash,
            },
            "selected_profile_id": discovery.profile_id if discovery else "",
            "invariants": invariants,
            "diagnostic_legacy_producer_versions": (
                {
                    "packets": legacy_result.packets.producer_version,
                    "facts": legacy_result.facts.producer_version,
                    "claims": legacy_result.claims.producer_version,
                }
                if legacy_result is not None else {}
            ),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate()
    atomic_write_json(args.output, report)
    if report["status"] != "passed":
        raise SystemExit(1)
    print(report["status"])


if __name__ == "__main__":
    main()
