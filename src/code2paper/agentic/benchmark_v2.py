from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BenchmarkModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GoldEvidenceSpan(BenchmarkModel):
    evidence_id: str
    path: str
    line_start: int
    line_end: int
    exact_excerpt_digest: str = ""


class GoldAtomicClaim(BenchmarkModel):
    claim_id: str
    text: str
    direct_evidence_ids: list[str]
    required_qualifiers: list[str] = Field(default_factory=list)
    high_risk: bool = False


class GoldFigureRelation(BenchmarkModel):
    relation_id: str
    source_claim_id: str
    target_claim_id: str
    direct_evidence_ids: list[str]
    allowed: bool = True


class AdversarialMutation(BenchmarkModel):
    mutation_id: str
    category: Literal[
        "legal_id_mismatch", "unsupported_paraphrase", "relevance_exaggeration", "causal_strengthening",
        "numeric_injection", "formula_injection", "figure_edge_pseudoevidence", "post_render_drift",
        "source_stale", "artifact_stale",
    ]
    payload: str
    candidate_text: str = ""
    expected_outcome: Literal["reject", "caveat", "block"]


class IntentGold(BenchmarkModel):
    intent_id: str
    emphasis: str
    expected_retrieval_targets: list[str]
    expected_section_claim_order: list[str]
    expected_figure_claim_ids: list[str]


class BenchmarkCaseV2(BenchmarkModel):
    case_id: str
    project_kind: Literal["toy", "real"]
    repo_root: str
    supported_claims: list[GoldAtomicClaim]
    evidence_spans: list[GoldEvidenceSpan]
    figure_relations: list[GoldFigureRelation] = Field(default_factory=list)
    mutations: list[AdversarialMutation] = Field(default_factory=list)
    intents: list[IntentGold] = Field(default_factory=list)
    expected_run_outcome: Literal["success", "block", "either_trustworthy"] = "either_trustworthy"
    human_reviewed: bool = False


class BenchmarkDatasetV2(BenchmarkModel):
    schema_version: str = "2.0"
    producer_version: str = "code2paper-agentic-p4"
    cases: list[BenchmarkCaseV2]

    @model_validator(mode="after")
    def _minimum_scope(self) -> "BenchmarkDatasetV2":
        ids = [item.case_id for item in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("benchmark case ids must be unique")
        if not any(item.project_kind == "toy" for item in self.cases):
            raise ValueError("benchmark requires a toy case")
        if len([item for item in self.cases if item.project_kind == "real"]) < 3:
            raise ValueError("benchmark requires at least three real projects")
        if not any("fastgs" in item.case_id.lower() for item in self.cases):
            raise ValueError("benchmark requires FastGS")
        if not any(len(item.intents) >= 2 for item in self.cases if item.project_kind == "real"):
            raise ValueError("benchmark requires paired intents for a real project")
        return self


class ObservedClaim(BenchmarkModel):
    text: str
    verdict: Literal["supported", "caveated", "unsupported", "unverified"]
    gold_claim_id: str = ""
    direct_evidence_ids: list[str] = Field(default_factory=list)
    direct_evidence_support: bool = False
    qualifiers_preserved: bool = True
    trace_exact: bool = False
    mutation_id: str = ""
    high_risk: bool = False


class ObservedFigureElement(BenchmarkModel):
    element_id: str
    element_kind: Literal["node", "edge", "annotation", "group"] = "node"
    gold_claim_id: str = ""
    relation_id: str = ""
    semantically_supported: bool
    direct_relation_evidence: bool = False
    rendered_drift: bool = False


class BenchmarkObservationV2(BenchmarkModel):
    case_id: str
    variant: Literal["fixed_legacy", "agentic_deterministic", "agentic_gemma4_mtp"]
    repeat_index: int = 1
    scope: Literal["trust_slice", "full_pipeline"] = "trust_slice"
    intent_id: str = ""
    run_status: Literal["success", "blocked"]
    blocked_reason: str = ""
    claims: list[ObservedClaim] = Field(default_factory=list)
    figure_elements: list[ObservedFigureElement] = Field(default_factory=list)
    figure_inventory_expected: int = 0
    figure_relation_inventory_expected: int = 0
    figure_inventory_reviewed: bool = False
    figure_inventory_validated: bool = False
    detected_mutation_ids: list[str] = Field(default_factory=list)
    stale_trials: int = 0
    stale_detected: int = 0
    final_invariant_passed: bool = False
    completion_complete: bool = False
    asset_lineage_complete: bool = False
    usable_completion: bool = False
    blocked_run_human_reviewed: bool = False
    false_block_human_reviewed: bool = False
    blocked_run_validated: bool = False
    false_block_validated: bool = False
    expected_retrieval_targets_observed: list[str] = Field(default_factory=list)
    section_claim_order: list[str] = Field(default_factory=list)
    figure_claim_ids: list[str] = Field(default_factory=list)
    support_verdict_signature: str = ""
    model_calls: int = 0
    latency_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hits: int = 0
    checkpoint_nodes_skipped: int = 0
    retrieval_loops: int = 0
    evidence_revision_loops: int = 0
    authoring_revision_loops: int = 0
    figure_revision_loops: int = 0
    provenance: dict[str, str] = Field(default_factory=dict)


class TrustMetricVectorV2(BenchmarkModel):
    atomic_claim_semantic_precision: float
    atomic_claim_semantic_recall: float
    unsupported_leakage_rate: float
    paraphrased_unsupported_leakage_rate: float
    high_risk_false_supported_rate: float
    qualifier_preservation_rate: float
    text_trace_exactness: float
    figure_element_semantic_precision: float
    direct_edge_evidence_rate: float
    rendered_element_drift_rate: float
    stale_detection_rate: float
    correct_block_rate: float
    false_block_rate: float
    usable_completion_rate: float
    author_intent_adherence: float


class EvaluatedBenchmarkRunV2(BenchmarkModel):
    observation: BenchmarkObservationV2
    metrics: TrustMetricVectorV2
    failures: list[str] = Field(default_factory=list)


class BenchmarkVariantSummaryV2(BenchmarkModel):
    variant: str
    run_count: int
    average_metrics: dict[str, float]
    worst_case_metrics: dict[str, float]
    trust_contract_failures: int
    usable_completion_rate: float
    average_operational_metrics: dict[str, float] = Field(default_factory=dict)
    worst_case_operational_metrics: dict[str, float] = Field(default_factory=dict)


class BenchmarkReportV2(BenchmarkModel):
    schema_version: str = "2.0"
    producer_version: str = "code2paper-agentic-p4"
    case_count: int
    real_project_count: int
    mutation_count: int
    evaluated_runs: list[EvaluatedBenchmarkRunV2]
    variant_summaries: list[BenchmarkVariantSummaryV2]
    paired_intent_sensitivity_passed: bool
    paired_intent_failures: list[str] = Field(default_factory=list)


def evaluate_observation(case: BenchmarkCaseV2, observation: BenchmarkObservationV2) -> EvaluatedBenchmarkRunV2:
    if case.case_id != observation.case_id:
        raise ValueError("observation case does not match gold case")
    gold_claims = {item.claim_id: item for item in case.supported_claims}
    mutations = {item.mutation_id: item for item in case.mutations}
    positive = [item for item in observation.claims if item.verdict in {"supported", "caveated"}]
    correct_positive = [
        item for item in positive
        if item.gold_claim_id in gold_claims and item.direct_evidence_support
    ]
    recovered = {item.gold_claim_id for item in correct_positive}
    supported_mutation_ids = {item.mutation_id for item in positive if item.mutation_id in mutations}
    rejected_mutation_ids = set(observation.detected_mutation_ids)
    leaked_mutation_ids = (set(mutations) - rejected_mutation_ids) | supported_mutation_ids
    paraphrased_ids = {key for key, item in mutations.items() if item.category == "unsupported_paraphrase"}
    high_risk_ids = {
        key for key, item in mutations.items()
        if item.category in {"causal_strengthening", "numeric_injection", "formula_injection"}
    }
    qualified = [item for item in correct_positive if gold_claims[item.gold_claim_id].required_qualifiers]
    traceable = [item for item in correct_positive]
    elements = observation.figure_elements
    edges = [item for item in elements if item.element_kind == "edge"]
    figure_review_required = bool(
        observation.completion_complete
        or elements
        or observation.figure_inventory_expected
        or observation.figure_relation_inventory_expected
    )
    figure_inventory_complete = (
        not figure_review_required
        or (
            (observation.figure_inventory_validated or observation.figure_inventory_reviewed)
            and len(elements) == observation.figure_inventory_expected
            and len(edges) == observation.figure_relation_inventory_expected
            and (not observation.completion_complete or observation.figure_inventory_expected > 0)
        )
    )
    expected_block = case.expected_run_outcome == "block"
    false_block = observation.run_status == "blocked" and case.expected_run_outcome == "success"
    intent = next((item for item in case.intents if item.intent_id == observation.intent_id), None)
    intent_checks: list[bool] = []
    if intent:
        intent_checks = [
            set(intent.expected_retrieval_targets).issubset(observation.expected_retrieval_targets_observed),
            _is_subsequence(intent.expected_section_claim_order, observation.section_claim_order),
            set(intent.expected_figure_claim_ids).issubset(observation.figure_claim_ids),
        ]
    metrics = TrustMetricVectorV2(
        atomic_claim_semantic_precision=_rate(len(correct_positive), len(positive), empty=1.0),
        atomic_claim_semantic_recall=_rate(len(recovered), len(gold_claims), empty=1.0),
        unsupported_leakage_rate=_rate(len(leaked_mutation_ids), len(mutations), empty=0.0),
        paraphrased_unsupported_leakage_rate=_rate(len(leaked_mutation_ids & paraphrased_ids), len(paraphrased_ids), empty=0.0),
        high_risk_false_supported_rate=_rate(len(leaked_mutation_ids & high_risk_ids), len(high_risk_ids), empty=0.0),
        qualifier_preservation_rate=_rate(sum(item.qualifiers_preserved for item in qualified), len(qualified), empty=1.0),
        text_trace_exactness=_rate(sum(item.trace_exact for item in traceable), len(traceable), empty=1.0),
        figure_element_semantic_precision=(
            _rate(sum(item.semantically_supported for item in elements), len(elements), empty=1.0)
            if figure_inventory_complete else 0.0
        ),
        direct_edge_evidence_rate=(
            _rate(sum(item.direct_relation_evidence for item in edges), len(edges), empty=1.0)
            if figure_inventory_complete else 0.0
        ),
        rendered_element_drift_rate=(
            _rate(sum(item.rendered_drift for item in elements), len(elements), empty=0.0)
            if figure_inventory_complete else 1.0
        ),
        stale_detection_rate=_rate(observation.stale_detected, observation.stale_trials, empty=1.0),
        correct_block_rate=1.0 if (not expected_block or observation.run_status == "blocked") else 0.0,
        false_block_rate=1.0 if false_block else 0.0,
        usable_completion_rate=1.0 if observation.usable_completion else 0.0,
        author_intent_adherence=_rate(sum(intent_checks), len(intent_checks), empty=1.0),
    )
    failures: list[str] = []
    if observation.run_status == "success" and not observation.final_invariant_passed:
        failures.append("success_without_final_invariant")
    if observation.completion_complete and not observation.asset_lineage_complete:
        failures.append("complete_without_asset_lineage")
    if observation.completion_complete and not figure_inventory_complete:
        failures.append("complete_without_validated_figure_inventory")
    if false_block and not (observation.false_block_validated or observation.false_block_human_reviewed):
        failures.append("false_block_not_validated")
    return EvaluatedBenchmarkRunV2(observation=observation, metrics=metrics, failures=failures)


def load_benchmark_dataset_v2(path: str | Path) -> BenchmarkDatasetV2:
    return BenchmarkDatasetV2.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_benchmark_observations_v2(path: str | Path) -> list[BenchmarkObservationV2]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [BenchmarkObservationV2.model_validate(item) for item in payload]


def validate_gold_evidence(dataset: BenchmarkDatasetV2, workspace_root: str | Path) -> list[str]:
    root = Path(workspace_root).resolve()
    failures: list[str] = []
    for case in dataset.cases:
        repo = (root / case.repo_root).resolve()
        try:
            repo.relative_to(root)
        except ValueError:
            failures.append(f"repo_outside_workspace:{case.case_id}")
            continue
        evidence_ids = {item.evidence_id for item in case.evidence_spans}
        for claim in case.supported_claims:
            for evidence_id in claim.direct_evidence_ids:
                if evidence_id not in evidence_ids:
                    failures.append(f"unknown_gold_evidence:{case.case_id}:{claim.claim_id}:{evidence_id}")
        for span in case.evidence_spans:
            path = (repo / span.path).resolve()
            try:
                path.relative_to(repo)
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
                excerpt = "".join(lines[span.line_start - 1 : span.line_end])
            except (OSError, ValueError):
                failures.append(f"gold_span_unreadable:{case.case_id}:{span.evidence_id}")
                continue
            digest = "sha256:" + hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
            if digest != span.exact_excerpt_digest:
                failures.append(f"gold_span_digest_mismatch:{case.case_id}:{span.evidence_id}")
    return failures


def build_benchmark_report_v2(
    dataset: BenchmarkDatasetV2,
    observations: list[BenchmarkObservationV2],
) -> BenchmarkReportV2:
    case_by_id = {item.case_id: item for item in dataset.cases}
    evaluated = [evaluate_observation(case_by_id[item.case_id], item) for item in observations]
    variants = sorted({item.observation.variant for item in evaluated})
    summaries = [_summarize_variant(variant, [item for item in evaluated if item.observation.variant == variant]) for variant in variants]
    paired_failures = _paired_intent_failures(dataset, evaluated)
    return BenchmarkReportV2(
        case_count=len(dataset.cases),
        real_project_count=sum(item.project_kind == "real" for item in dataset.cases),
        mutation_count=sum(len(item.mutations) for item in dataset.cases),
        evaluated_runs=evaluated,
        variant_summaries=summaries,
        paired_intent_sensitivity_passed=not paired_failures,
        paired_intent_failures=paired_failures,
    )


def write_benchmark_report_v2(path: str | Path, report: BenchmarkReportV2) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return output


def _summarize_variant(variant: str, runs: list[EvaluatedBenchmarkRunV2]) -> BenchmarkVariantSummaryV2:
    names = list(TrustMetricVectorV2.model_fields)
    lower_is_better = {
        "unsupported_leakage_rate", "paraphrased_unsupported_leakage_rate", "high_risk_false_supported_rate",
        "rendered_element_drift_rate", "false_block_rate",
    }
    average = {name: round(sum(getattr(item.metrics, name) for item in runs) / len(runs), 6) for name in names}
    worst = {
        name: (max if name in lower_is_better else min)(getattr(item.metrics, name) for item in runs)
        for name in names
    }
    operational = (
        "model_calls", "latency_seconds", "input_tokens", "output_tokens", "cache_hits",
        "checkpoint_nodes_skipped", "retrieval_loops", "evidence_revision_loops",
        "authoring_revision_loops", "figure_revision_loops",
    )
    return BenchmarkVariantSummaryV2(
        variant=variant,
        run_count=len(runs),
        average_metrics=average,
        worst_case_metrics=worst,
        trust_contract_failures=sum(bool(item.failures) for item in runs),
        usable_completion_rate=average["usable_completion_rate"],
        average_operational_metrics={
            name: round(sum(getattr(item.observation, name) for item in runs) / len(runs), 6)
            for name in operational
        },
        worst_case_operational_metrics={
            name: max(getattr(item.observation, name) for item in runs) for name in operational
        },
    )


def _paired_intent_failures(dataset: BenchmarkDatasetV2, runs: list[EvaluatedBenchmarkRunV2]) -> list[str]:
    failures: list[str] = []
    for case in [item for item in dataset.cases if len(item.intents) >= 2]:
        candidates = [
            item.observation for item in runs
            if item.observation.case_id == case.case_id and item.observation.variant == "agentic_gemma4_mtp"
        ]
        for repeat in sorted({item.repeat_index for item in candidates}):
            paired = [item for item in candidates if item.repeat_index == repeat]
            if {item.intent_id for item in paired} != {item.intent_id for item in case.intents}:
                failures.append(f"paired_intent_missing:{case.case_id}:repeat_{repeat}")
                continue
            signatures = {item.support_verdict_signature for item in paired}
            organizations = {(tuple(item.section_claim_order), tuple(item.figure_claim_ids)) for item in paired}
            if len(signatures) != 1 or "" in signatures:
                failures.append(f"paired_intent_support_changed:{case.case_id}:repeat_{repeat}")
            if len(organizations) < 2:
                failures.append(f"paired_intent_organization_unchanged:{case.case_id}:repeat_{repeat}")
    return failures


def _rate(numerator: int, denominator: int, *, empty: float) -> float:
    return round(numerator / denominator, 6) if denominator else empty


def _is_subsequence(expected: list[str], observed: list[str]) -> bool:
    iterator = iter(observed)
    return all(any(value == candidate for candidate in iterator) for value in expected)
