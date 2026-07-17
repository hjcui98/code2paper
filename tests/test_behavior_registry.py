import ast

from code2paper.analysis.behavior_registry import (
    BehaviorDetectionContext,
    default_behavior_registry,
)
from code2paper.analysis.symbol_behavior_extractor import (
    _evidence_ids_for_symbol,
    _evidence_scoped_source_segment,
)
from code2paper.core.schemas import EvidenceItem, SourceType


def _patterns(source: str, *, symbol: str) -> set[str]:
    result = default_behavior_registry().detect(
        BehaviorDetectionContext(
            path="model.py",
            symbol=symbol,
            source_segment=source,
            evidence_ids=["E1"],
        )
    )
    return {behavior.detected_pattern for behavior in result.behaviors}


def test_registry_detects_batched_grouped_expert_convolution() -> None:
    source = """
def dynamic_conv_experts(values, kernels):
    v = values.reshape(1, B * E * C, H, W)
    w = kernels.reshape(B * E * C, C, kH, kW)
    return F.conv2d(v, w, groups=B * E)
"""

    assert "batched_grouped_convolution" in _patterns(
        source, symbol="dynamic_conv_experts"
    )


def test_registry_detects_shared_base_expert_composition() -> None:
    source = """
def compose(self, idx, expert_base):
    selected = self.experts[idx]
    selected = F.softmax(selected, dim=2)
    return torch.einsum('bknc,ncihw->bkcihw', selected, expert_base)
"""

    assert "shared_base_expert_composition" in _patterns(source, symbol="compose")


def test_registry_detects_normalized_topk_expert_gate() -> None:
    source = """
def forward(self, x):
    logits = self.gate(x)
    probs = F.softmax(logits, dim=-1)
    score, idx = torch.topk(probs, k=self.top_k, dim=-1)
    return idx, score / score.sum(dim=-1, keepdim=True)
"""

    assert "normalized_topk_expert_gate" in _patterns(source, symbol="forward")


def test_ambiguous_symbol_fallback_is_scoped_to_evidence_lines() -> None:
    source = """def unrelated():
    return F.conv2d(v, w, groups=B * E)  # expert kernels

class Model:
    def forward(self, x):
        return x + 1
"""
    segment = _evidence_scoped_source_segment(
        text=source,
        node=ast.parse(source),
        path="model.py",
        evidence_ids=["E1"],
        evidence_by_id={
            "E1": EvidenceItem(
                evidence_id="E1",
                source_type=SourceType.SOURCE,
                path="model.py",
                line_start=5,
                line_end=6,
                content_summary="Model.forward implementation.",
                confidence=0.9,
            )
        },
    )

    assert "return x + 1" in segment
    assert "groups=B * E" not in segment


def test_symbol_evidence_filter_drops_unrelated_same_file_spans() -> None:
    evidence = {
        "E1": EvidenceItem(
            evidence_id="E1", source_type=SourceType.SOURCE, path="model.py",
            symbol="dynamic_conv_experts", line_start=1, line_end=3,
            content_summary="Grouped convolution.", confidence=0.9,
        ),
        "E2": EvidenceItem(
            evidence_id="E2", source_type=SourceType.SOURCE, path="model.py",
            symbol="Model.forward", line_start=5, line_end=7,
            content_summary="Forward method.", confidence=0.9,
        ),
    }

    assert _evidence_ids_for_symbol(
        path="model.py", symbol="forward", candidate_ids=["E1", "E2"],
        evidence_by_id=evidence,
    ) == ["E2"]
