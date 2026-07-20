from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.benchmark_v2 import BenchmarkDatasetV2, EvaluatedBenchmarkRunV2


class CutoverModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrustThresholdsV2(CutoverModel):
    author_intent_adherence_min: float = 1.0
    semantic_precision_min: float = 1.0
    unsupported_leakage_max: float = 0.0
    paraphrased_leakage_max: float = 0.0
    high_risk_false_supported_max: float = 0.0
    qualifier_preservation_min: float = 1.0
    text_trace_exactness_min: float = 1.0
    figure_element_precision_min: float = 1.0
    direct_edge_evidence_min: float = 1.0
    rendered_drift_max: float = 0.0
    stale_detection_min: float = 1.0


class RolloutEvidenceV2(CutoverModel):
    """Policy inputs only; rollout progress counters are deprecated self-reports."""

    protocol_validated: bool = False
    shadow_cases: int = 0
    shadow_reviewed: bool = False
    opt_in_cases: int = 0
    canary_cases: int = 0
    canary_incidents: int = Field(default=0, ge=0)
    team_false_block_threshold: float | None = None
    migration_guide_complete: bool = False
    legacy_contract_marked: bool = False


class ValidatedRolloutEvidenceV2(CutoverModel):
    source: Literal["none", "digest_pinned_rollout_artifacts"] = "none"
    artifact_digests: list[str] = Field(default_factory=list)
    shadow_case_ids: list[str] = Field(default_factory=list)
    opt_in_case_ids: list[str] = Field(default_factory=list)
    canary_case_ids: list[str] = Field(default_factory=list)
    canary_incidents: int = 0

    @model_validator(mode="after")
    def _validated_rollout_is_consistent(self) -> "ValidatedRolloutEvidenceV2":
        values = [*self.shadow_case_ids, *self.opt_in_case_ids, *self.canary_case_ids]
        if self.source == "none" and (self.artifact_digests or values or self.canary_incidents):
            raise ValueError("rollout progress requires digest_pinned_rollout_artifacts source")
        if self.source == "digest_pinned_rollout_artifacts" and not self.artifact_digests:
            raise ValueError("validated rollout source requires artifact digests")
        expected_artifacts = len(self.shadow_case_ids) + len(self.opt_in_case_ids) + len(self.canary_case_ids)
        if self.source == "digest_pinned_rollout_artifacts" and len(self.artifact_digests) != expected_artifacts:
            raise ValueError("rollout artifact digest count must match stage-case coverage")
        if len(self.artifact_digests) != len(set(self.artifact_digests)):
            raise ValueError("rollout artifact digests must be unique")
        if any(not _is_sha256_digest(item) for item in self.artifact_digests):
            raise ValueError("rollout artifact digests must be sha256 values")
        for stage, case_ids in (
            ("shadow", self.shadow_case_ids),
            ("opt_in", self.opt_in_case_ids),
            ("canary", self.canary_case_ids),
        ):
            if len(case_ids) != len(set(case_ids)):
                raise ValueError(f"validated rollout contains duplicate {stage} cases")
        if not set(self.opt_in_case_ids).issubset(self.shadow_case_ids):
            raise ValueError("opt-in rollout cases require validated shadow evidence")
        if not set(self.canary_case_ids).issubset(self.opt_in_case_ids):
            raise ValueError("canary rollout cases require validated opt-in evidence")
        return self


class NamedReviewEvidenceV2(CutoverModel):
    """Invocation-derived proof that observations came from validated review files.

    This evidence is deliberately separate from ``RolloutEvidenceV2`` so a rollout JSON
    cannot self-assert that named reviews were loaded and digest checked.
    """

    source: Literal["none", "digest_pinned_review_artifacts"] = "none"
    review_artifact_digests: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _review_artifacts_are_consistent(self) -> "NamedReviewEvidenceV2":
        digests = self.review_artifact_digests
        if self.source == "none" and digests:
            raise ValueError("review digests require digest_pinned_review_artifacts source")
        if self.source == "digest_pinned_review_artifacts" and not digests:
            raise ValueError("digest-pinned review source requires review artifact digests")
        if len(set(digests)) != len(digests):
            raise ValueError("review artifact digests must be unique")
        if any(not _is_sha256_digest(item) for item in digests):
            raise ValueError("review artifact digests must be sha256 values")
        return self


class ValidatedBenchmarkEvidenceV2(CutoverModel):
    """Invocation-derived proof for the exact protocol-bound observation matrix.

    The source observations must be produced by an extractor that re-reads their
    run/gold/mutation bindings (the optional review extractor is one such source).
    Merely hashing a caller-authored BenchmarkObservationV2 JSON file is insufficient:
    a digest proves immutability, not the truth of self-reported trust fields.
    """

    source: Literal["none", "digest_pinned_observation_artifacts"] = "none"
    artifact_digests: list[str] = Field(default_factory=list)
    observation_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _benchmark_artifacts_are_consistent(self) -> "ValidatedBenchmarkEvidenceV2":
        if self.source == "none" and (self.artifact_digests or self.observation_count):
            raise ValueError("benchmark evidence requires digest_pinned_observation_artifacts source")
        if self.source == "digest_pinned_observation_artifacts" and (
            not self.artifact_digests or not self.observation_count
        ):
            raise ValueError("digest-pinned benchmark evidence requires artifacts and observations")
        if len(set(self.artifact_digests)) != len(self.artifact_digests):
            raise ValueError("benchmark artifact digests must be unique")
        if any(not _is_sha256_digest(item) for item in self.artifact_digests):
            raise ValueError("benchmark artifact digests must be sha256 values")
        return self


class CutoverDecisionV2(CutoverModel):
    schema_version: str = "2.3"
    status: Literal["hold", "shadow_ready", "opt_in_ready", "canary_ready", "default_ready"]
    default_mode: Literal["legacy", "agentic"]
    hard_gates_passed: bool
    worst_case_metrics: dict[str, float] = Field(default_factory=dict)
    failures: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    named_review_evidence: NamedReviewEvidenceV2 = Field(default_factory=NamedReviewEvidenceV2)
    validated_benchmark_evidence: ValidatedBenchmarkEvidenceV2 = Field(
        default_factory=ValidatedBenchmarkEvidenceV2
    )
    validated_rollout_evidence: ValidatedRolloutEvidenceV2 = Field(default_factory=ValidatedRolloutEvidenceV2)
    protocol_commit: str = ""
    gold_digest: str = ""
    benchmark_case_ids: list[str] = Field(default_factory=list)


class LegacyTrustContractV1(CutoverModel):
    contract_version: str = "legacy-v1-weaker-trust"
    authoritative_v2_final_invariant: bool = False
    limitations: list[str] = Field(default_factory=lambda: [
        "no_authoritative_final_atomic_claim_semantic_gate",
        "no_direct_relation_evidence_requirement_for_every_figure_edge",
        "no_repo_snapshot_bound_post_render_lineage",
    ])
    warning: str = "Legacy output must not be represented as Evidence V2 final-invariant passed."


def decide_cutover(
    dataset: BenchmarkDatasetV2,
    runs: list[EvaluatedBenchmarkRunV2],
    rollout: RolloutEvidenceV2,
    thresholds: TrustThresholdsV2 | None = None,
    *,
    named_review_evidence: NamedReviewEvidenceV2 | None = None,
    validated_benchmark_evidence: ValidatedBenchmarkEvidenceV2 | None = None,
    validated_rollout_evidence: ValidatedRolloutEvidenceV2 | None = None,
    protocol_commit: str = "",
    gold_digest: str = "",
) -> CutoverDecisionV2:
    policy = thresholds or TrustThresholdsV2()
    review_evidence = named_review_evidence or NamedReviewEvidenceV2()
    benchmark_evidence = validated_benchmark_evidence or ValidatedBenchmarkEvidenceV2()
    rollout_evidence = validated_rollout_evidence or ValidatedRolloutEvidenceV2()
    failures: list[str] = []
    agentic = [item for item in runs if item.observation.variant in {"agentic_deterministic", "agentic_gemma4_mtp"}]
    variants = {item.observation.variant for item in runs}
    covered_cases = {item.observation.case_id for item in runs}
    if covered_cases != {item.case_id for item in dataset.cases}:
        failures.append("benchmark_case_coverage_incomplete")
    if not rollout.protocol_validated:
        failures.append("frozen_benchmark_protocol_not_validated")
    if any((rollout.shadow_cases, rollout.shadow_reviewed, rollout.opt_in_cases, rollout.canary_cases, rollout.canary_incidents)):
        failures.append("self_reported_rollout_progress_not_accepted")
    for required in ("fixed_legacy", "agentic_deterministic", "agentic_gemma4_mtp"):
        if required not in variants:
            failures.append(f"missing_variant:{required}")
    identity_list = [
        (
            item.observation.case_id,
            item.observation.variant,
            item.observation.intent_id,
            item.observation.repeat_index,
        )
        for item in runs
    ]
    actual_identities = set(identity_list)
    if len(identity_list) != len(actual_identities):
        failures.append("duplicate_matrix_run_identity")
    expected_identities: set[tuple[str, str, str, int]] = set()
    for case in dataset.cases:
        intent_ids = [item.intent_id for item in case.intents] or [""]
        for intent_id in intent_ids:
            for variant, repeats_required in (
                ("fixed_legacy", (1,)),
                ("agentic_deterministic", (1,)),
                ("agentic_gemma4_mtp", (1, 2, 3)),
            ):
                for repeat_index in repeats_required:
                    identity = (case.case_id, variant, intent_id, repeat_index)
                    expected_identities.add(identity)
                    if identity not in actual_identities:
                        failures.append(
                            "missing_matrix_run:"
                            f"{case.case_id}:{variant}:{intent_id or 'default'}:{repeat_index}"
                        )
    if not (
        benchmark_evidence.source == "digest_pinned_observation_artifacts"
        and benchmark_evidence.observation_count == len(expected_identities)
    ):
        failures.append("digest_pinned_benchmark_observations_not_validated")
    for case_id, variant, intent_id, repeat_index in sorted(actual_identities - expected_identities):
        failures.append(
            "unexpected_matrix_run:"
            f"{case_id}:{variant}:{intent_id or 'default'}:{repeat_index}"
        )
    repeats: dict[tuple[str, str], set[int]] = defaultdict(set)
    for item in runs:
        if item.observation.variant == "agentic_gemma4_mtp":
            repeats[(item.observation.case_id, item.observation.intent_id)].add(item.observation.repeat_index)
    for case in dataset.cases:
        intent_ids = [item.intent_id for item in case.intents] or [""]
        for intent_id in intent_ids:
            if len(repeats[(case.case_id, intent_id)]) < 3:
                failures.append(f"gemma_repeats_below_three:{case.case_id}:{intent_id or 'default'}")
    if not agentic:
        failures.append("no_agentic_runs")
    worst = _worst_metrics(agentic)
    checks = {
        "author_intent_adherence": (">=", policy.author_intent_adherence_min),
        "atomic_claim_semantic_precision": (">=", policy.semantic_precision_min),
        "unsupported_leakage_rate": ("<=", policy.unsupported_leakage_max),
        "paraphrased_unsupported_leakage_rate": ("<=", policy.paraphrased_leakage_max),
        "high_risk_false_supported_rate": ("<=", policy.high_risk_false_supported_max),
        "qualifier_preservation_rate": (">=", policy.qualifier_preservation_min),
        "text_trace_exactness": (">=", policy.text_trace_exactness_min),
        "figure_element_semantic_precision": (">=", policy.figure_element_precision_min),
        "direct_edge_evidence_rate": (">=", policy.direct_edge_evidence_min),
        "rendered_element_drift_rate": ("<=", policy.rendered_drift_max),
        "stale_detection_rate": (">=", policy.stale_detection_min),
    }
    for name, (operator, threshold) in checks.items():
        value = worst.get(name)
        if value is None or (operator == ">=" and value < threshold) or (operator == "<=" and value > threshold):
            failures.append(f"hard_threshold_failed:{name}")
    if any(item.failures for item in agentic):
        failures.append("run_contract_failures_present")
    if any(item.observation.scope != "full_pipeline" for item in runs):
        failures.append("full_pipeline_observations_required")
    case_by_id = {item.case_id: item for item in dataset.cases}
    for item in runs:
        provenance = item.observation.provenance
        for mutation in case_by_id[item.observation.case_id].mutations:
            if not provenance.get(f"mutation_trial:{mutation.mutation_id}"):
                failures.append(f"missing_mutation_trial_provenance:{item.observation.case_id}:{mutation.mutation_id}")
    if any(item.observation.run_status == "success" and not item.observation.final_invariant_passed for item in agentic):
        failures.append("success_without_final_invariant")
    if any(item.observation.completion_complete and not item.observation.asset_lineage_complete for item in agentic):
        failures.append("complete_without_asset_lineage")
    legacy = [item for item in runs if item.observation.variant == "fixed_legacy"]
    if legacy and agentic:
        legacy_completion = sum(item.observation.usable_completion for item in legacy) / len(legacy)
        agentic_completion = sum(item.observation.usable_completion for item in agentic) / len(agentic)
        if agentic_completion < legacy_completion:
            failures.append("agentic_usable_completion_below_legacy_requires_false_success_evidence")
    failures.extend(_paired_intent_cutover_failures(dataset, agentic))
    if rollout.team_false_block_threshold is None:
        failures.append("team_false_block_threshold_unset")
    elif worst.get("false_block_rate", 1.0) > rollout.team_false_block_threshold:
        failures.append("false_block_rate_above_team_threshold")
    hard_passed = not failures
    status: Literal["hold", "shadow_ready", "opt_in_ready", "canary_ready", "default_ready"] = "hold"
    if hard_passed:
        status = "shadow_ready"
        expected_rollout_cases = {item.case_id for item in dataset.cases}
        if set(rollout_evidence.shadow_case_ids) == expected_rollout_cases:
            status = "opt_in_ready"
        if status == "opt_in_ready" and set(rollout_evidence.opt_in_case_ids) == expected_rollout_cases:
            status = "canary_ready"
        if (
            status == "canary_ready"
            and set(rollout_evidence.canary_case_ids) == expected_rollout_cases
            and rollout_evidence.canary_incidents == 0
            and rollout.migration_guide_complete and rollout.legacy_contract_marked
        ):
            status = "default_ready"
    actions = _actions(failures, status, len(dataset.cases))
    return CutoverDecisionV2(
        status=status,
        default_mode="agentic" if status == "default_ready" else "legacy",
        hard_gates_passed=hard_passed,
        worst_case_metrics=worst,
        failures=list(dict.fromkeys(failures)),
        next_actions=actions,
        named_review_evidence=review_evidence,
        validated_benchmark_evidence=benchmark_evidence,
        validated_rollout_evidence=rollout_evidence,
        protocol_commit=protocol_commit,
        gold_digest=gold_digest,
        benchmark_case_ids=sorted(item.case_id for item in dataset.cases),
    )


def _paired_intent_cutover_failures(
    dataset: BenchmarkDatasetV2,
    agentic: list[EvaluatedBenchmarkRunV2],
) -> list[str]:
    failures: list[str] = []
    for case in [item for item in dataset.cases if len(item.intents) >= 2]:
        candidates = [
            item.observation for item in agentic
            if item.observation.case_id == case.case_id
            and item.observation.variant == "agentic_gemma4_mtp"
        ]
        expected_intents = {item.intent_id for item in case.intents}
        for repeat in (1, 2, 3):
            paired = [item for item in candidates if item.repeat_index == repeat]
            if {item.intent_id for item in paired} != expected_intents:
                failures.append(f"paired_intent_missing:{case.case_id}:repeat_{repeat}")
                continue
            signatures = {item.support_verdict_signature for item in paired}
            organizations = {
                (tuple(item.section_claim_order), tuple(item.figure_claim_ids))
                for item in paired
            }
            if len(signatures) != 1 or "" in signatures:
                failures.append(f"paired_intent_support_changed:{case.case_id}:repeat_{repeat}")
            if len(organizations) < 2:
                failures.append(f"paired_intent_organization_unchanged:{case.case_id}:repeat_{repeat}")
    return failures


def _worst_metrics(runs: list[EvaluatedBenchmarkRunV2]) -> dict[str, float]:
    if not runs:
        return {}
    names = type(runs[0].metrics).model_fields
    lower_is_better = {
        "unsupported_leakage_rate", "paraphrased_unsupported_leakage_rate", "high_risk_false_supported_rate",
        "rendered_element_drift_rate", "false_block_rate",
    }
    metrics = {
        name: (max if name in lower_is_better else min)(getattr(item.metrics, name) for item in runs)
        for name in names
    }
    # False-block usability is a fleet rate, unlike a trust-plane bypass where one
    # failing run is already disqualifying. Taking max over per-run binary values made
    # every non-zero team tolerance meaningless: one conservative block always became
    # 1.0. Keep worst-case aggregation for leakage/precision/drift, but compare the
    # configured team threshold to the actual fraction of false-blocked agentic runs.
    metrics["false_block_rate"] = sum(
        item.metrics.false_block_rate for item in runs
    ) / len(runs)
    return metrics


def _actions(failures: list[str], status: str, case_count: int) -> list[str]:
    if failures:
        return ["repair_benchmark_or_trust_failures", "keep_legacy_default", *failures]
    if status == "shadow_ready":
        return [f"run_and_review_{case_count}_shadow_cases"]
    if status == "opt_in_ready":
        return [f"run_{case_count}_opt_in_cases"]
    if status == "canary_ready":
        return [f"run_{case_count}_canary_cases_and_complete_migration_guide"]
    return ["agentic_default_authorized_with_explicit_legacy_fallback"]


def _is_sha256_digest(value: str) -> bool:
    prefix = "sha256:"
    if not value.startswith(prefix) or len(value) != len(prefix) + 64:
        return False
    return all(character in "0123456789abcdef" for character in value[len(prefix):])
