"""Plugin-style behavior detector registry.

Detectors produce domain-neutral behavior types plus optional concrete pattern
labels. This keeps the MethodEvidence IR generic while allowing project/domain
specific detectors to be registered later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from code2paper.core.schemas import ConfidenceLevel


@dataclass(frozen=True)
class BehaviorDetectionContext:
    path: str
    symbol: str
    source_segment: str
    evidence_ids: list[str]
    language: str = "python"

    @property
    def lowered_source(self) -> str:
        return self.source_segment.lower()


@dataclass(frozen=True)
class BehaviorSpec:
    behavior_type: str
    detected_pattern: str
    description: str
    operations: list[str] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH


@dataclass(frozen=True)
class EquationSpec:
    name: str
    latex: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    caveats: list[str] = field(default_factory=lambda: ["Generated from a recognized code pattern; verify notation before paper submission."])


@dataclass
class BehaviorDetectionResult:
    behaviors: list[BehaviorSpec] = field(default_factory=list)
    equations: list[EquationSpec] = field(default_factory=list)


class BehaviorDetector(Protocol):
    name: str
    supported_languages: tuple[str, ...]
    required_evidence_types: tuple[str, ...]
    produced_behavior_types: tuple[str, ...]
    confidence_policy: str

    def detect(self, context: BehaviorDetectionContext) -> BehaviorDetectionResult:
        ...


class BehaviorDetectorRegistry:
    def __init__(self, detectors: list[BehaviorDetector] | None = None) -> None:
        self._detectors: list[BehaviorDetector] = []
        for detector in detectors or []:
            self.register(detector)

    def register(self, detector: BehaviorDetector) -> None:
        names = {existing.name for existing in self._detectors}
        if detector.name in names:
            raise ValueError(f"duplicate behavior detector: {detector.name}")
        self._detectors.append(detector)

    def detect(self, context: BehaviorDetectionContext) -> BehaviorDetectionResult:
        result = BehaviorDetectionResult()
        for detector in self._detectors:
            if context.language not in detector.supported_languages and "*" not in detector.supported_languages:
                continue
            detector_result = detector.detect(context)
            result.behaviors.extend(detector_result.behaviors)
            result.equations.extend(detector_result.equations)
        return _dedupe_detection_result(result)

    @property
    def detectors(self) -> tuple[BehaviorDetector, ...]:
        return tuple(self._detectors)


@dataclass(frozen=True)
class KeywordBehaviorDetector:
    name: str
    predicate: Callable[[BehaviorDetectionContext], bool]
    behavior: BehaviorSpec
    equations: tuple[EquationSpec, ...] = ()
    supported_languages: tuple[str, ...] = ("python",)
    required_evidence_types: tuple[str, ...] = ("source",)
    confidence_policy: str = "keyword-pattern evidence; conservative and non-novelty-judging"

    @property
    def produced_behavior_types(self) -> tuple[str, ...]:
        return (self.behavior.behavior_type,)

    def detect(self, context: BehaviorDetectionContext) -> BehaviorDetectionResult:
        if not self.predicate(context):
            return BehaviorDetectionResult()
        return BehaviorDetectionResult(behaviors=[self.behavior], equations=list(self.equations))


def default_behavior_registry() -> BehaviorDetectorRegistry:
    registry = BehaviorDetectorRegistry()
    for detector in _default_detectors():
        registry.register(detector)
    return registry


def _default_detectors() -> list[BehaviorDetector]:
    return [
        KeywordBehaviorDetector(
            name="weighted_aggregation.scaled_compatibility",
            predicate=lambda ctx: _has_any(ctx.lowered_source, ["matmul", "bmm"])
            and "softmax" in ctx.lowered_source
            and _has_any(ctx.lowered_source, ["temperature", "sqrt", "** 0.5"]),
            behavior=BehaviorSpec(
                behavior_type="weighted_aggregation",
                detected_pattern="scaled_dot_product_attention",
                description="Computes attention weights from scaled query-key compatibility scores and applies them to values.",
                operations=["scale", "similarity", "softmax", "weighted_sum"],
            ),
            equations=(
                EquationSpec(
                    name="Scaled Dot-Product Attention",
                    latex=r"\mathrm{Attention}(Q,K,V)=\mathrm{softmax}(QK^T/\sqrt{d_k})V",
                ),
            ),
        ),
        KeywordBehaviorDetector(
            name="weighted_aggregation.cross_context_attention",
            predicate=lambda ctx: "cross attention" in ctx.lowered_source
            or (
                "softmax" in ctx.lowered_source
                and _has_any(ctx.lowered_source, ["query", " q", "q_"])
                and _has_any(ctx.lowered_source, ["key", " k", "k_"])
                and _has_any(ctx.lowered_source, ["value", " v", "v_"])
                and _has_any(ctx.lowered_source, ["cat([", "concat", "cross"])
            ),
            behavior=BehaviorSpec(
                behavior_type="weighted_aggregation",
                detected_pattern="cross_context_attention",
                description="Uses one representation stream as queries and a broader context stream as keys and values to transfer information across streams.",
                operations=["form_query", "form_context", "softmax", "weighted_sum"],
            ),
            equations=(
                EquationSpec(
                    name="Cross-Context Attention",
                    latex=r"H_q=\mathrm{softmax}(QK_c^T/\sqrt{d})V_c",
                ),
            ),
        ),
        KeywordBehaviorDetector(
            name="parallel_projection.multi_branch_projection",
            predicate=lambda ctx: "multihead" in ctx.symbol.lower()
            or {"w_qs", "w_ks", "w_vs"}.issubset(set(_tokens(ctx.lowered_source))),
            behavior=BehaviorSpec(
                behavior_type="parallel_projection",
                detected_pattern="multi_head_projection",
                description="Projects inputs into multiple parallel branches, applies a transformation in parallel, and merges the branches.",
                operations=["project", "split", "parallel_apply", "concat", "project"],
            ),
            equations=(
                EquationSpec(
                    name="Multi-Branch Projection",
                    latex=r"\mathrm{MultiBranch}(X)=\mathrm{Merge}(f_1(XW_1),\ldots,f_h(XW_h))W^O",
                ),
            ),
        ),
        KeywordBehaviorDetector(
            name="repeated_composition.encoder_like_stack",
            predicate=lambda ctx: "modulelist" in ctx.lowered_source and "encoderlayer" in ctx.lowered_source,
            behavior=BehaviorSpec("repeated_composition", "encoder_stack", "Builds a representation stack from repeated encoder-like layers.", ["repeat", "compose"]),
        ),
        KeywordBehaviorDetector(
            name="parameter_sharing.shared_stack_across_streams",
            predicate=lambda ctx: "modulelist" in ctx.lowered_source
            and _has_any(ctx.lowered_source, ["self.blocks", "self.layers", "self.encoder"])
            and _has_any(ctx.lowered_source, ["x, y", "visible", "masked", "cross attention"]),
            behavior=BehaviorSpec(
                "parameter_sharing",
                "shared_stack_across_streams",
                "Reuses a shared stack of blocks across coupled representation streams while adding stream-specific interaction logic.",
                ["share_blocks", "process_streams", "exchange_context"],
            ),
        ),
        KeywordBehaviorDetector(
            name="repeated_composition.decoder_like_stack",
            predicate=lambda ctx: "modulelist" in ctx.lowered_source and "decoderlayer" in ctx.lowered_source,
            behavior=BehaviorSpec("repeated_composition", "decoder_stack", "Builds a representation stack from repeated decoder-like layers.", ["repeat", "compose"]),
        ),
        KeywordBehaviorDetector(
            name="sequential_composition.two_sublayer_block",
            predicate=lambda ctx: "pos_ffn" in ctx.lowered_source and "slf_attn" in ctx.lowered_source and "enc_attn" not in ctx.lowered_source,
            behavior=BehaviorSpec(
                "sequential_composition",
                "encoder_layer_composition",
                "Composes a block from a self-transformation sublayer followed by a point-wise transformation sublayer.",
                ["apply", "apply"],
            ),
        ),
        KeywordBehaviorDetector(
            name="sequential_composition.three_sublayer_block",
            predicate=lambda ctx: "pos_ffn" in ctx.lowered_source and "slf_attn" in ctx.lowered_source and "enc_attn" in ctx.lowered_source,
            behavior=BehaviorSpec(
                "sequential_composition",
                "decoder_layer_composition",
                "Composes a block from self-transformation, cross-context transformation, and point-wise transformation sublayers.",
                ["apply", "apply", "apply"],
            ),
        ),
        KeywordBehaviorDetector(
            name="pointwise_transformation.two_linear_layers",
            predicate=lambda ctx: _has_any(ctx.lowered_source, ["relu", "gelu"]) and ctx.lowered_source.count("linear") >= 2,
            behavior=BehaviorSpec(
                "pointwise_transformation",
                "positionwise_feed_forward",
                "Applies two point-wise linear transformations with a nonlinear activation between them.",
                ["linear", "activation", "linear"],
            ),
            equations=(
                EquationSpec(
                    name="Point-wise Feed-Forward Transformation",
                    latex=r"\mathrm{FFN}(x)=\sigma(xW_1+b_1)W_2+b_2",
                ),
            ),
        ),
        KeywordBehaviorDetector(
            name="skip_connection.residual_addition",
            predicate=lambda ctx: "residual =" in ctx.lowered_source or "+= residual" in ctx.lowered_source or "+ residual" in ctx.lowered_source,
            behavior=BehaviorSpec("skip_connection", "residual_connection", "Adds a residual connection around a sub-computation.", ["preserve", "add"]),
        ),
        KeywordBehaviorDetector(
            name="normalization.layer_normalization",
            predicate=lambda ctx: "layernorm" in ctx.lowered_source or "layer_norm" in ctx.lowered_source,
            behavior=BehaviorSpec("normalization", "layer_normalization", "Applies layer normalization around module computation.", ["normalize"]),
        ),
        KeywordBehaviorDetector(
            name="constraint_application.future_mask",
            predicate=lambda ctx: "triu" in ctx.lowered_source and "mask" in ctx.lowered_source,
            behavior=BehaviorSpec(
                "constraint_application",
                "autoregressive_subsequent_mask",
                "Builds a structural mask to block disallowed future-position access.",
                ["construct_mask", "apply_constraint"],
            ),
        ),
        KeywordBehaviorDetector(
            name="representation_injection.periodic_position_signal",
            predicate=lambda ctx: "sin" in ctx.lowered_source
            and "cos" in ctx.lowered_source
            and _has_any(ctx.lowered_source, ["position", "positional", "sinusoid"]),
            behavior=BehaviorSpec(
                "representation_injection",
                "sinusoidal_positional_encoding",
                "Constructs periodic position encodings and injects them into learned representations.",
                ["construct_encoding", "add"],
            ),
            equations=(
                EquationSpec(
                    name="Periodic Positional Encoding",
                    latex=r"\mathrm{PE}_{(pos,2i)}=\sin(pos/10000^{2i/d}),\quad \mathrm{PE}_{(pos,2i+1)}=\cos(pos/10000^{2i/d})",
                ),
            ),
        ),
        KeywordBehaviorDetector(
            name="representation_substitution.predicted_context_replaces_direct_context",
            predicate=lambda ctx: _has_any(ctx.lowered_source, ["pred", "predict"])
            and _has_any(ctx.lowered_source, ["pos", "position", "center", "context"])
            and _has_any(ctx.lowered_source, ["cat([", "concat", "replace", "instead"])
            and _has_any(ctx.lowered_source, ["decoder", "decode"]),
            behavior=BehaviorSpec(
                behavior_type="representation_substitution",
                detected_pattern="predicted_context_replaces_direct_context",
                description="Feeds a predicted conditioning representation into a downstream decoder instead of directly exposing the corresponding ground-truth conditioning signal.",
                operations=["predict_condition", "substitute_condition", "decode"],
            ),
            equations=(
                EquationSpec(
                    name="Predicted-Condition Decoding",
                    latex=r"\hat{Y}=\mathrm{Dec}(Z,\hat{C};\theta_d)",
                ),
            ),
        ),
        KeywordBehaviorDetector(
            name="parameter_sharing.shared_projection_weight",
            predicate=lambda ctx: "embedding" in ctx.lowered_source
            and _has_any(ctx.lowered_source, ["weight =", ".weight"])
            and _has_any(ctx.lowered_source, ["trg_word_prj", "word_prj", "projection"]),
            behavior=BehaviorSpec(
                "parameter_sharing",
                "embedding_projection_weight_sharing",
                "Shares parameters between representation and projection components when configured.",
                ["tie_parameter"],
            ),
        ),
        KeywordBehaviorDetector(
            name="objective_shaping.smoothed_target_distribution",
            predicate=lambda ctx: "softmax" in ctx.lowered_source and _has_any(ctx.lowered_source, ["label_smoothing", "smoothing"]),
            behavior=BehaviorSpec(
                "objective_shaping",
                "label_smoothing_loss",
                "Computes smoothed target distributions for a shaped loss objective.",
                ["smooth_target", "compute_loss"],
            ),
        ),
        KeywordBehaviorDetector(
            name="objective_shaping.composite_supervision",
            predicate=lambda ctx: "loss" in ctx.lowered_source
            and _has_any(ctx.lowered_source, ["loss1", "loss2", "aux", "recon", "reconstruction"])
            and _has_any(ctx.lowered_source, ["+", "return"])
            and _has_any(ctx.lowered_source, ["weight", "lambda", "alpha", "beta", "eta", "ita", "config."]),
            behavior=BehaviorSpec(
                behavior_type="objective_shaping",
                detected_pattern="weighted_composite_objective",
                description="Combines a primary task objective with an auxiliary or regularization objective using an explicit scalar weight.",
                operations=["compute_primary_loss", "compute_auxiliary_loss", "weight", "sum"],
            ),
            equations=(
                EquationSpec(
                    name="Weighted Composite Objective",
                    latex=r"\mathcal{L}=\mathcal{L}_{\mathrm{task}}+\lambda\,\mathcal{L}_{\mathrm{aux}}",
                    confidence=ConfidenceLevel.HIGH,
                ),
            ),
        ),
        KeywordBehaviorDetector(
            name="objective_shaping.prediction_matching_loss",
            predicate=lambda ctx: "loss" in ctx.lowered_source
            and _has_any(ctx.lowered_source, ["pred", "predict"])
            and _has_any(ctx.lowered_source, ["target", "gt", "ground", "label", "center", "pos"])
            and _has_any(ctx.lowered_source, ["mse", "smoothl1", "l1loss", "l2", "norm", "cosine"]),
            behavior=BehaviorSpec(
                behavior_type="objective_shaping",
                detected_pattern="prediction_matching_loss",
                description="Penalizes the discrepancy between a predicted conditioning representation and its evidence-backed target representation.",
                operations=["predict", "compare_to_target", "reduce_loss"],
            ),
            equations=(
                EquationSpec(
                    name="Prediction Matching Loss",
                    latex=r"\mathcal{L}_{\mathrm{aux}}=\ell(\hat{C},C)",
                    confidence=ConfidenceLevel.HIGH,
                ),
            ),
        ),
        KeywordBehaviorDetector(
            name="objective_shaping.set_reconstruction_loss",
            predicate=lambda ctx: "loss" in ctx.lowered_source
            and _has_any(ctx.lowered_source, ["rebuild", "reconstruct", "reconstruction", "decoder"])
            and _has_any(ctx.lowered_source, ["chamfer", "emd", "cdl1", "cdl2", "distance"]),
            behavior=BehaviorSpec(
                behavior_type="objective_shaping",
                detected_pattern="set_reconstruction_loss",
                description="Supervises decoded outputs with a set- or distance-based reconstruction loss such as Chamfer or EMD when those operators are present in code.",
                operations=["decode", "match_sets", "reduce_loss"],
            ),
            equations=(
                EquationSpec(
                    name="Reconstruction Loss",
                    latex=r"\mathcal{L}_{\mathrm{rec}}=D(\hat{Y},Y)",
                    confidence=ConfidenceLevel.HIGH,
                ),
            ),
        ),
        KeywordBehaviorDetector(
            name="regularization.dropout",
            predicate=lambda ctx: "dropout" in ctx.lowered_source,
            behavior=BehaviorSpec("regularization", "dropout", "Applies dropout inside module computation.", ["drop"], ConfidenceLevel.MEDIUM),
            confidence_policy="keyword-pattern evidence; medium because dropout may be auxiliary rather than a main method mechanism",
        ),
    ]


def _dedupe_detection_result(result: BehaviorDetectionResult) -> BehaviorDetectionResult:
    behavior_seen: set[tuple[str, str]] = set()
    equation_seen: set[tuple[str, str]] = set()
    behaviors: list[BehaviorSpec] = []
    equations: list[EquationSpec] = []
    for behavior in result.behaviors:
        key = (behavior.behavior_type, behavior.detected_pattern)
        if key in behavior_seen:
            continue
        behavior_seen.add(key)
        behaviors.append(behavior)
    for equation in result.equations:
        key = (equation.name, equation.latex)
        if key in equation_seen:
            continue
        equation_seen.add(key)
        equations.append(equation)
    return BehaviorDetectionResult(behaviors=behaviors, equations=equations)


def _tokens(text: str) -> list[str]:
    return text.replace(".", " ").replace("(", " ").replace(")", " ").replace("=", " ").split()


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)
