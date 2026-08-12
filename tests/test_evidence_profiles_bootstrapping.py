"""Tests for BootstrappingMultiViewProfile: match, compile, behavior contract, and evidence chain."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.evidence_compiler_v3 import (
    compile_legacy_profile_evidence_v3,
    validate_evidence_compiler_v3,
)
from code2paper.agentic.evidence_profiles.bootstrapping_multiview import (
    BootstrappingMultiViewProfile,
    _behavior_contract_satisfied,
    _behavior_contract_missing_patterns,
)
from code2paper.agentic.evidence_profiles.registry import (
    default_evidence_profile_registry,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot

MULTI_VIEW = "multi_view.py"


def _write_minimal_fixture(root: Path) -> None:
    """Write a minimal multi_view.py with all required symbols and weighted fusion patterns."""
    (root / MULTI_VIEW).write_text(
        '''import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from torch.utils.data import Dataset

class NC_MultiViewDataset(Dataset):
    def __init__(self, data, labels, noise_ratio=0.3, noise_seed=42):
        self.data = data
        self.labels = labels
        self.noise_ratio = noise_ratio
        self.noise_seed = noise_seed
        self.noise_indicator = None

    def NoiseCorrespondence_inject(self):
        M = self.data.shape[1]
        self.noise_indicator = np.ones((self.data.shape[0], M))
        rng = np.random.RandomState(self.noise_seed)
        for i in range(self.data.shape[0]):
            if rng.rand() < self.noise_ratio:
                max_corrupt = max(1, int(np.floor(M / 2)))
                corrupt_views = rng.choice(M, size=max_corrupt, replace=False)
                self.noise_indicator[i, corrupt_views] = 0
        return self.data, self.labels, self.noise_indicator

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx], self.labels[idx]


class ReliabilityEstimator(nn.Module):
    def __init__(self, num_views, feat_dim, num_classes, hidden_dim=64):
        super().__init__()
        self.num_views = num_views
        self.feat_dim = feat_dim
        self.num_classes = num_classes
        self._build_router_mlps()

    def _build_router_mlps(self):
        self.router_mlps = nn.ModuleList([
            nn.Sequential(
                nn.Linear(self.feat_dim + 2, 32),
                nn.ReLU(),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )
            for _ in range(self.num_views)
        ])

    def _compute_entropy(self, probs):
        eps = 1e-8
        log_probs = torch.log(probs + eps)
        entropy = -(probs * log_probs).sum(dim=-1)
        max_entropy = np.log(self.num_classes)
        return entropy / max_entropy

    def _compute_pairwise_agreement(self, view_probs, target_idx):
        target = F.log_softmax(view_probs[target_idx], dim=-1)
        others = [F.log_softmax(view_probs[i], dim=-1) for i in range(len(view_probs)) if i != target_idx]
        divergences = []
        for other in others:
            kl = F.kl_div(target, other, reduction='none').sum(dim=-1)
            divergences.append(kl)
        return torch.stack(divergences, dim=0).mean(dim=0)

    def _compute_reliability_features(self, view_logits):
        view_probs = [F.softmax(logits, dim=-1) for logits in view_logits]
        entropy = torch.stack([self._compute_entropy(probs) for probs in view_probs], dim=1)
        agreement = torch.stack([
            self._compute_pairwise_agreement(view_probs, i) for i in range(len(view_probs))
        ], dim=1)
        reliability_features = torch.cat([entropy.unsqueeze(-1), agreement.unsqueeze(-1)], dim=-1)
        return reliability_features

    def _router_forward(self, view_features, reliability_features):
        reliabilities = []
        for v in range(self.num_views):
            combined = torch.cat([view_features[v], reliability_features[:, v, :]], dim=-1)
            alpha = self.router_mlps[v](combined).squeeze(-1)
            reliabilities.append(alpha)
        return torch.stack(reliabilities, dim=1)

    def _finalize_forward(self, logits_list, view_features):
        reliability_features = self._compute_reliability_features(logits_list)
        reliabilities = self._router_forward(view_features, reliability_features)
        logits_stack = torch.stack(logits_list, dim=1)
        fused_logits = (
            reliabilities.unsqueeze(-1) * logits_stack
        ).sum(dim=1)
        return logits_list, fused_logits, reliabilities


class MultiViewBackbone(ReliabilityEstimator):
    def __init__(self, num_views, input_dim, num_classes, hidden_dims=(64, 32)):
        super().__init__(num_views, hidden_dims[-1], num_classes)
        self.input_dim = input_dim
        self.encoders = nn.ModuleList([
            nn.Sequential(
                nn.Linear(input_dim, hidden_dims[0]),
                nn.BatchNorm1d(hidden_dims[0]),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(hidden_dims[0], hidden_dims[1]),
            )
            for _ in range(num_views)
        ])
        self.classifiers = nn.ModuleList([
            nn.Linear(hidden_dims[1], num_classes)
            for _ in range(num_views)
        ])

    def forward(self, x_views):
        view_features = []
        logits_list = []
        for v in range(self.num_views):
            feat = self.encoders[v](x_views[:, v, :])
            view_features.append(feat)
            logits = self.classifiers[v](feat)
            logits_list.append(logits)
        logits_list, fused_logits, reliabilities = self._finalize_forward(
            logits_list, view_features
        )
        return fused_logits, reliabilities


def load_multiviewdata(dataset_path):
    import scipy.io as sio
    from sklearn.preprocessing import minmax_scale
    data = sio.loadmat(dataset_path)
    X = data['X']
    Y = data['Y']
    for v in range(X.shape[1]):
        X[:, v, :] = minmax_scale(X[:, v, :])
    return X, Y


def train_one_seed(seed, X, Y, noise_ratio, num_epochs=100, lr=0.001, lambda_w=0.5):
    torch.manual_seed(seed)
    num_views = X.shape[1]
    num_classes = len(np.unique(Y))
    model = MultiViewBackbone(num_views, X.shape[2], num_classes)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)
    criterion_ce = nn.CrossEntropyLoss()

    for epoch in range(num_epochs):
        dataset = NC_MultiViewDataset(X, Y, noise_ratio=noise_ratio, noise_seed=seed + epoch)
        X_noisy, Y_tensor, noise_indicator = dataset.NoiseCorrespondence_inject()
        fused_logits, reliabilities = model(torch.FloatTensor(X_noisy))
        loss_ce = criterion_ce(fused_logits, torch.LongTensor(Y_tensor))
        clean_indicators = torch.FloatTensor(noise_indicator)
        loss_bce = F.binary_cross_entropy(reliabilities, clean_indicators)
        loss = loss_ce + lambda_w * loss_bce
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        scheduler.step()

    return model
''',
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Fixture-based match/compile tests
# ---------------------------------------------------------------------------

def test_minimal_fixture_match_and_compile_positive(tmp_path: Path) -> None:
    """Profile matches and compiles with minimal real source fixture."""
    _write_minimal_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)

    profile = BootstrappingMultiViewProfile()
    match_result = profile.match(snapshot)
    assert match_result.matched, f"match failed: {match_result.reasons}"
    assert match_result.missing_required_fingerprints == []

    result = compile_legacy_profile_evidence_v3(snapshot)
    assert result is not None, "compile returned None"
    assert result.profile_id == "bootstrapping_multiview_tnc_reliability"
    assert not validate_evidence_compiler_v3(result, snapshot)


def test_no_late_fusion_text_but_weighted_fusion_passes(tmp_path: Path) -> None:
    """Behavior contract must pass when weighted fusion is present WITHOUT 'late fusion' text."""
    _write_minimal_fixture(tmp_path)
    root = tmp_path

    # Verify there is no 'late fusion' text
    text = (root / MULTI_VIEW).read_text(encoding="utf-8")
    assert "late fusion" not in text.lower(), "fixture accidentally contains 'late fusion'"

    # Verify behavior contract passes
    assert _behavior_contract_satisfied(root), "behavior contract should pass with weighted fusion patterns"

    # Verify full match + compile
    snapshot = build_repo_snapshot(tmp_path)
    profile = BootstrappingMultiViewProfile()
    assert profile.match(snapshot).matched
    assert profile._compile_legacy(snapshot) is not None


def test_remove_weighted_sum_rejects_behavior_contract(tmp_path: Path) -> None:
    """Removing .sum(dim=1) from the data flow causes behavior contract rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / MULTI_VIEW
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            ").sum(dim=1)",
            ")  # sum removed",
        ),
        encoding="utf-8",
    )
    assert not _behavior_contract_satisfied(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    profile = BootstrappingMultiViewProfile()
    assert not profile.match(snapshot).matched


def test_remove_reliability_weight_multiplication_rejects(tmp_path: Path) -> None:
    """Removing reliability.unsqueeze(-1) * logits_stack causes rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / MULTI_VIEW
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "reliabilities.unsqueeze(-1) * logits_stack",
            "logits_stack  # weight multiplication removed",
        ),
        encoding="utf-8",
    )
    assert not _behavior_contract_satisfied(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_legacy_profile_evidence_v3(snapshot) is None


def test_remove_torch_stack_rejects(tmp_path: Path) -> None:
    """Removing torch.stack(logits_list, dim=1) causes rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / MULTI_VIEW
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "torch.stack(logits_list, dim=1)",
            "logits_list  # stack removed",
        ),
        encoding="utf-8",
    )
    assert not _behavior_contract_satisfied(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_legacy_profile_evidence_v3(snapshot) is None


def test_same_name_symbols_no_behavior_no_match(tmp_path: Path) -> None:
    """Symbols with the same names but no corresponding behavior must not match."""
    # Write symbols that have the right names but wrong behavior
    (tmp_path / MULTI_VIEW).write_text(
        '''import torch
import torch.nn as nn

class NC_MultiViewDataset:
    def __init__(self, data, labels):
        self.data = data
        self.labels = labels
    def NoiseCorrespondence_inject(self):
        return self.data, self.labels, None

class ReliabilityEstimator(nn.Module):
    def __init__(self): super().__init__()
    def _build_router_mlps(self): pass
    def _compute_entropy(self, p): return p
    def _compute_pairwise_agreement(self, p, i): return p
    def _compute_reliability_features(self, l): return l
    def _router_forward(self, f, r): return r
    def _finalize_forward(self, logits_list, view_features):
        # Missing: torch.stack, reliability.unsqueeze * logits_stack, sum(dim=1)
        return logits_list, logits_list[0], torch.ones(len(logits_list))

class MultiViewBackbone(ReliabilityEstimator):
    def __init__(self): super().__init__()
    def forward(self, x):
        return None, None

def train_one_seed(seed): pass
def load_multiviewdata(path): return None, None
''',
        encoding="utf-8",
    )
    profile = BootstrappingMultiViewProfile()
    snapshot = build_repo_snapshot(tmp_path)
    match_result = profile.match(snapshot)
    assert not match_result.matched, f"should not match without behavior: {match_result.reasons}"
    assert not _behavior_contract_satisfied(tmp_path)


# ---------------------------------------------------------------------------
# Claim evidence chain tests
# ---------------------------------------------------------------------------

def test_each_supported_claim_has_facts_and_direct_spans(tmp_path: Path) -> None:
    """Every supported claim must have at least one fact and one direct span from real code."""
    _write_minimal_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    result = compile_legacy_profile_evidence_v3(snapshot)
    assert result is not None, "compile failed"

    fact_by_id = {f.fact_id: f for f in result.facts.facts if f.validation_status == "supported"}
    span_by_id = {s.span_id: s for packet in result.packets.packets for s in packet.spans}

    for claim in result.claims.claims:
        assert claim.status in ("supported", "partial"), f"{claim.claim_id}: status={claim.status}"
        assert len(claim.fact_ids) > 0, f"{claim.claim_id}: no fact_ids"
        assert len(claim.direct_evidence_ids) > 0, f"{claim.claim_id}: no direct_evidence_ids"

        for fact_id in claim.fact_ids:
            assert fact_id in fact_by_id, f"{claim.claim_id}: unknown fact {fact_id}"

        for span_id in claim.direct_evidence_ids:
            assert span_id in span_by_id, f"{claim.claim_id}: unknown span {span_id}"


def test_claim_c_bml_tnc_formalize_references_finalize_forward(tmp_path: Path) -> None:
    """C-BML-TNC-FORMALIZE must directly reference F-BML-FINALIZE-FWD and its span."""
    _write_minimal_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    result = compile_legacy_profile_evidence_v3(snapshot)
    assert result is not None

    claim = next((c for c in result.claims.claims if c.claim_id == "C-BML-TNC-FORMALIZE"), None)
    assert claim is not None, "C-BML-TNC-FORMALIZE claim not found"
    assert "F-BML-FINALIZE-FWD" in claim.fact_ids, (
        f"C-BML-TNC-FORMALIZE must reference F-BML-FINALIZE-FWD, got {claim.fact_ids}"
    )
    assert "F-BML-BACKBONE-FWD" in claim.fact_ids
    assert "EV3-BML-FINALIZE-FWD" in claim.direct_evidence_ids, (
        f"C-BML-TNC-FORMALIZE direct_evidence must include EV3-BML-FINALIZE-FWD, got {claim.direct_evidence_ids}"
    )


def test_claim_c_bml_backbone_includes_finalize_fwd_fact_and_span(tmp_path: Path) -> None:
    """C-BML-BACKBONE must reference F-BML-FINALIZE-FWD and its direct span."""
    _write_minimal_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    result = compile_legacy_profile_evidence_v3(snapshot)
    assert result is not None

    claim = next((c for c in result.claims.claims if c.claim_id == "C-BML-BACKBONE"), None)
    assert claim is not None, "C-BML-BACKBONE claim not found"
    assert "F-BML-FINALIZE-FWD" in claim.fact_ids
    assert "EV3-BML-FINALIZE-FWD" in claim.direct_evidence_ids


def test_finalize_fwd_fact_describes_weighted_fusion_operations(tmp_path: Path) -> None:
    """F-BML-FINALIZE-FWD fact object must describe torch.stack, weight multiply, and sum."""
    _write_minimal_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    result = compile_legacy_profile_evidence_v3(snapshot)
    assert result is not None

    fact = next((f for f in result.facts.facts if f.fact_id == "F-BML-FINALIZE-FWD"), None)
    assert fact is not None, "F-BML-FINALIZE-FWD fact not found"
    assert fact.validation_status == "supported"
    obj_text = " ".join(fact.object) if isinstance(fact.object, list) else fact.object
    assert "stack" in obj_text.lower(), f"fact object should mention stack: {obj_text}"
    assert "sum" in obj_text.lower(), f"fact object should mention sum: {obj_text}"


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

def test_registry_selects_bootstrapping_profile(tmp_path: Path) -> None:
    """Registry correctly selects BootstrappingMultiViewProfile for the fixture."""
    _write_minimal_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    profile, matches = default_evidence_profile_registry().select(snapshot)
    assert profile is not None
    assert profile.profile_id == "bootstrapping_multiview_tnc_reliability"
    boot_match = next(m for m in matches if m.profile_id == "bootstrapping_multiview_tnc_reliability")
    assert boot_match.matched
    assert boot_match.missing_required_fingerprints == []


def test_registry_does_not_select_bootstrapping_without_finalize_forward(tmp_path: Path) -> None:
    """Registry must not select Bootstrapping profile when _finalize_forward is missing."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / MULTI_VIEW
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "def _finalize_forward(self, logits_list, view_features):",
            "def _finalize_forward_renamed(self, logits_list, view_features):",
        ),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    profile, matches = default_evidence_profile_registry().select(snapshot)
    assert profile is None or profile.profile_id != "bootstrapping_multiview_tnc_reliability"
    boot_match = next(m for m in matches if m.profile_id == "bootstrapping_multiview_tnc_reliability")
    assert "weighted_forward_fusion" in boot_match.missing_required_fingerprints


# ---------------------------------------------------------------------------
# Behavior contract specific tests
# ---------------------------------------------------------------------------

def test_behavior_contract_requires_noise_ratio_and_indicator(tmp_path: Path) -> None:
    """Behavior contract must require noise_ratio and noise_indicator patterns."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / MULTI_VIEW
    path.write_text(
        path.read_text(encoding="utf-8").replace("noise_ratio", "corruption_rate"),
        encoding="utf-8",
    )
    assert not _behavior_contract_satisfied(tmp_path)


def test_behavior_contract_requires_nn_linear_and_sigmoid(tmp_path: Path) -> None:
    """Behavior contract must require nn.Linear and nn.Sigmoid."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / MULTI_VIEW
    path.write_text(
        path.read_text(encoding="utf-8").replace("nn.Sigmoid", "nn.Tanh"),
        encoding="utf-8",
    )
    assert not _behavior_contract_satisfied(tmp_path)


def test_behavior_contract_requires_cross_entropy_and_bce(tmp_path: Path) -> None:
    """Behavior contract must require CrossEntropyLoss and F.binary_cross_entropy."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / MULTI_VIEW
    path.write_text(
        path.read_text(encoding="utf-8").replace("CrossEntropyLoss", "MSELoss"),
        encoding="utf-8",
    )
    assert not _behavior_contract_satisfied(tmp_path)


def test_profile_does_not_activate_from_project_name_or_prose(tmp_path: Path) -> None:
    """Profile must not activate from project name or paper prose alone."""
    (tmp_path / "paper.md").write_text(
        "Bootstrapping Multi-view Learning for TNC uses weighted fusion with reliability estimation.",
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_legacy_profile_evidence_v3(snapshot) is None


# ---------------------------------------------------------------------------
# Executable predicate tests
# ---------------------------------------------------------------------------

def test_remove_return_fused_logits_rejects_behavior_contract(tmp_path: Path) -> None:
    """Removing all 'return.*fused_logits' occurrences causes behavior contract rejection."""
    _write_minimal_fixture(tmp_path)
    path = tmp_path / MULTI_VIEW
    text = path.read_text(encoding="utf-8")
    # Replace all occurrences of return.*fused_logits
    text = text.replace("return logits_list, fused_logits, reliabilities", "return logits_list, None, reliabilities")
    text = text.replace("return fused_logits, reliabilities", "return None, reliabilities")
    path.write_text(text, encoding="utf-8")
    assert not _behavior_contract_satisfied(tmp_path)
    missing = _behavior_contract_missing_patterns(tmp_path)
    assert any("return fused_logits" in m for m in missing), f"should report missing return fused_logits, got: {missing}"


def test_behavior_contract_missing_patterns_reports_specific_predicates(tmp_path: Path) -> None:
    """When multiple patterns fail, missing_patterns lists each specific missing predicate."""
    (tmp_path / MULTI_VIEW).write_text(
        '''import torch
import torch.nn as nn
import torch.nn.functional as F

class NC_MultiViewDataset:
    def __init__(self): pass
    def NoiseCorrespondence_inject(self): pass

class ReliabilityEstimator(nn.Module):
    def __init__(self): super().__init__()
    def _build_router_mlps(self): pass
    def _compute_entropy(self, p): return p
    def _compute_pairwise_agreement(self, p, i): return p
    def _compute_reliability_features(self, l): return l
    def _router_forward(self, f, r): return r
    def _finalize_forward(self, logits_list, view_features):
        return logits_list, logits_list[0], None

class MultiViewBackbone(ReliabilityEstimator):
    def __init__(self): super().__init__()
    def forward(self, x): return None, None

def train_one_seed(seed): pass
def load_multiviewdata(path): return None, None
''',
        encoding="utf-8",
    )
    assert not _behavior_contract_satisfied(tmp_path)
    missing = _behavior_contract_missing_patterns(tmp_path)
    assert len(missing) > 0, "should report missing patterns"
    assert "torch.stack(logits_list, dim=1)" in missing, f"should report missing torch.stack, got: {missing}"
    assert "sum(dim=1) weighted reduction" in missing, f"should report missing sum(dim=1), got: {missing}"
    assert "return fused_logits" in missing, f"should report missing return fused_logits, got: {missing}"
