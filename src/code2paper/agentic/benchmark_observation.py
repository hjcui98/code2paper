from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.benchmark_v2 import (
    BenchmarkCaseV2,
    BenchmarkObservationV2,
    ObservedClaim,
    ObservedFigureElement,
)


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimAdjudicationV2(ReviewModel):
    atomic_claim_id: str = ""
    text: str = ""
    verdict: Literal["supported", "caveated", "unsupported", "unverified"] | None = None
    gold_claim_id: str = ""
    mutation_id: str = ""
    qualifiers_preserved: bool = False
    high_risk: bool = False


class FigureAdjudicationV2(ReviewModel):
    element_id: str
    gold_claim_id: str = ""
    relation_id: str = ""
    semantically_supported: bool
    direct_relation_evidence: bool = False
    rendered_drift: bool = False


class MutationTrialAdjudicationV2(ReviewModel):
    mutation_id: str
    detected: bool
    trial_artifact_path: str
    trial_artifact_digest: str


class BenchmarkRunReviewV2(ReviewModel):
    schema_version: str = "2.0"
    case_id: str
    variant: Literal["fixed_legacy", "agentic_deterministic", "agentic_gemma4_mtp"]
    repeat_index: int = 1
    intent_id: str = ""
    scope: Literal["full_pipeline"] = "full_pipeline"
    run_summary_path: str
    run_summary_digest: str
    protocol_spec_digest: str = ""
    repo_snapshot_id: str = ""
    model_id: str = ""
    capability_profile_digest: str = ""
    reviewer: str
    reviewed_at: str
    blocked_reason_review: str = ""
    claims: list[ClaimAdjudicationV2] = Field(default_factory=list)
    figures: list[FigureAdjudicationV2] = Field(default_factory=list)
    mutation_trials: list[MutationTrialAdjudicationV2] = Field(default_factory=list)
    expected_retrieval_targets_observed: list[str] = Field(default_factory=list)
    section_claim_order: list[str] = Field(default_factory=list)
    figure_claim_ids: list[str] = Field(default_factory=list)
    usable_completion: bool = False
    latency_seconds: float = 0.0

    @model_validator(mode="after")
    def _review_is_attributable(self) -> "BenchmarkRunReviewV2":
        reviewer = self.reviewer.strip()
        reviewed_at = self.reviewed_at.strip()
        if (
            not reviewer
            or reviewer == "__REQUIRED_NAMED_HUMAN__"
            or not reviewed_at
            or reviewed_at == "__REQUIRED_ISO8601__"
        ):
            raise ValueError("benchmark review requires reviewer and reviewed_at")
        try:
            timestamp = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("benchmark reviewed_at must be ISO-8601") from exc
        if timestamp.tzinfo is None:
            raise ValueError("benchmark reviewed_at must include a timezone")
        if self.variant != "fixed_legacy" and any(not item.atomic_claim_id for item in self.claims):
            raise ValueError("agentic claim adjudications require atomic_claim_id")
        return self


def load_benchmark_run_review_v2(path: str | Path) -> BenchmarkRunReviewV2:
    return BenchmarkRunReviewV2.model_validate_json(Path(path).read_text(encoding="utf-8"))


def extract_benchmark_observation_v2(case: BenchmarkCaseV2, review: BenchmarkRunReviewV2) -> BenchmarkObservationV2:
    if review.case_id != case.case_id:
        raise ValueError("review case does not match gold case")
    summary_path = Path(review.run_summary_path).resolve()
    _require_digest(summary_path, review.run_summary_digest, "run_summary")
    summary = _read_json(summary_path)
    if review.variant == "fixed_legacy":
        return _legacy_observation(case, review, summary_path, summary)
    return _agentic_observation(case, review, summary_path, summary)


def _agentic_observation(
    case: BenchmarkCaseV2,
    review: BenchmarkRunReviewV2,
    summary_path: Path,
    summary: dict,
) -> BenchmarkObservationV2:
    artifacts = summary.get("artifacts", {})
    claims_payload, claims_digest = _artifact_json(artifacts, "final_text_claims", required=False)
    validation, validation_digest = _artifact_json(artifacts, "text_evidence_validation", required=False)
    trace, trace_digest = _artifact_json(artifacts, "final_text_trace", required=False)
    completion, completion_digest = _artifact_json(artifacts, "agentic_run_completion_report", required=True)
    evaluation, evaluation_digest = _artifact_json(artifacts, "agentic_run_evaluation_report", required=True)
    freshness, freshness_digest = _artifact_json(artifacts, "artifact_freshness", required=True)
    repo_snapshot, repo_snapshot_digest = _artifact_json(artifacts, "repo_snapshot", required=True)
    if review.repo_snapshot_id and review.repo_snapshot_id != repo_snapshot.get("snapshot_id"):
        raise ValueError("review repo snapshot contradicts run artifact")
    atomic_by_id = {item["atomic_claim_id"]: item for item in claims_payload.get("atomic_claims", [])}
    verdict_by_id = {item["atomic_claim_id"]: item for item in validation.get("verdicts", [])}
    trace_by_id = {item["atomic_claim_id"]: item for item in trace.get("entries", [])}
    observed_claims: list[ObservedClaim] = []
    for adjudication in review.claims:
        atomic = atomic_by_id.get(adjudication.atomic_claim_id)
        verdict = verdict_by_id.get(adjudication.atomic_claim_id)
        if atomic is None or verdict is None:
            raise ValueError(f"reviewed atomic claim missing from artifacts:{adjudication.atomic_claim_id}")
        artifact_verdict = verdict.get("status", "unverified")
        if adjudication.verdict is not None and adjudication.verdict != artifact_verdict:
            raise ValueError(f"review verdict contradicts validator:{adjudication.atomic_claim_id}")
        trace_entry = trace_by_id.get(adjudication.atomic_claim_id)
        trace_exact = bool(
            trace_entry
            and trace_entry.get("claim_digest") == atomic.get("claim_digest")
            and trace_entry.get("final_text_span_digest") == atomic.get("claim_digest")
            and trace_entry.get("verdict_status") == artifact_verdict
            and trace_entry.get("direct_evidence_ids") == verdict.get("direct_evidence_ids")
        )
        observed_claims.append(ObservedClaim(
            text=atomic.get("text", ""),
            verdict=artifact_verdict,
            gold_claim_id=adjudication.gold_claim_id,
            direct_evidence_ids=verdict.get("direct_evidence_ids", []),
            qualifiers_preserved=adjudication.qualifiers_preserved,
            trace_exact=trace_exact,
            mutation_id=adjudication.mutation_id,
            high_risk=adjudication.high_risk,
        ))
    detected, stale_trials, stale_detected, trial_provenance = _mutation_trials(case, review)
    completion_complete = bool(completion.get("complete"))
    asset_lineage = _completion_asset_lineage(completion)
    loops = summary.get("loop_counters", {})
    semantic_trace, semantic_trace_digest = _artifact_json(
        artifacts, "semantic_verifier_call_trace", required=False,
    )
    model_calls = semantic_trace.get("calls", [])
    observed_models = {str(item.get("model") or "") for item in model_calls if str(item.get("model") or "")}
    observed_profiles = {
        str(item.get("capability_profile_source_digest") or "")
        for item in model_calls if str(item.get("capability_profile_source_digest") or "")
    }
    if len(observed_models) > 1 or len(observed_profiles) > 1:
        raise ValueError("semantic verifier calls used inconsistent model capability profiles")
    observed_model = next(iter(observed_models), "")
    observed_profile = next(iter(observed_profiles), "")
    if review.model_id and observed_model and review.model_id != observed_model:
        raise ValueError("review model_id contradicts semantic verifier trace")
    if review.capability_profile_digest and observed_profile and review.capability_profile_digest != observed_profile:
        raise ValueError("review capability profile contradicts semantic verifier trace")
    provenance = {
        "run_summary": _digest_file(summary_path),
        "final_text_claims": claims_digest,
        "text_evidence_validation": validation_digest,
        "final_text_trace": trace_digest,
        "completion_report": completion_digest,
        "evaluation_report": evaluation_digest,
        "freshness_report": freshness_digest,
        "repo_snapshot": repo_snapshot_digest,
        "repo_snapshot_id": repo_snapshot.get("snapshot_id", ""),
        "protocol_spec_digest": review.protocol_spec_digest,
        "model_id": observed_model or review.model_id,
        "capability_profile_digest": observed_profile or review.capability_profile_digest,
        "semantic_verifier_call_trace": semantic_trace_digest,
        "reviewer": review.reviewer,
        "reviewed_at": review.reviewed_at,
        **trial_provenance,
    }
    return BenchmarkObservationV2(
        case_id=case.case_id,
        variant=review.variant,
        repeat_index=review.repeat_index,
        scope=review.scope,
        intent_id=review.intent_id,
        run_status="success" if summary.get("status") == "success" else "blocked",
        blocked_reason=summary.get("blocked_reason", ""),
        claims=observed_claims,
        figure_elements=[ObservedFigureElement(**item.model_dump()) for item in review.figures],
        detected_mutation_ids=detected,
        stale_trials=stale_trials,
        stale_detected=stale_detected,
        final_invariant_passed=bool(summary.get("invariant_audit_passed")),
        completion_complete=completion_complete,
        asset_lineage_complete=asset_lineage,
        usable_completion=review.usable_completion and completion_complete and asset_lineage,
        blocked_run_human_reviewed=bool(review.blocked_reason_review) if summary.get("status") != "success" else False,
        false_block_human_reviewed=bool(review.blocked_reason_review),
        expected_retrieval_targets_observed=review.expected_retrieval_targets_observed,
        section_claim_order=review.section_claim_order,
        figure_claim_ids=review.figure_claim_ids,
        support_verdict_signature=_support_signature(observed_claims),
        model_calls=len(model_calls),
        latency_seconds=review.latency_seconds,
        input_tokens=sum(item.get("token_usage", {}).get("prompt_tokens", 0) for item in model_calls),
        output_tokens=sum(item.get("token_usage", {}).get("completion_tokens", 0) for item in model_calls),
        cache_hits=sum(bool(item.get("cached")) for item in model_calls),
        retrieval_loops=int(evaluation.get("retrieval_loops", loops.get("retrieval", 0)) or 0),
        evidence_revision_loops=int(evaluation.get("evidence_revision_loops", loops.get("evidence_revision", 0)) or 0),
        authoring_revision_loops=int(evaluation.get("revision_loops", loops.get("authoring_revision", 0)) or 0),
        figure_revision_loops=int(loops.get("figure_revision", 0) or 0),
        provenance=provenance,
    )


def _legacy_observation(case: BenchmarkCaseV2, review: BenchmarkRunReviewV2, summary_path: Path, summary: dict) -> BenchmarkObservationV2:
    observed: list[ObservedClaim] = []
    for item in review.claims:
        if item.verdict is None or not item.text:
            raise ValueError("legacy claim review requires text and verdict")
        observed.append(ObservedClaim(
            text=item.text,
            verdict=item.verdict,
            gold_claim_id=item.gold_claim_id,
            qualifiers_preserved=item.qualifiers_preserved,
            trace_exact=False,
            mutation_id=item.mutation_id,
            high_risk=item.high_risk,
        ))
    detected, stale_trials, stale_detected, trial_provenance = _mutation_trials(case, review)
    return BenchmarkObservationV2(
        case_id=case.case_id,
        variant="fixed_legacy",
        repeat_index=review.repeat_index,
        scope="full_pipeline",
        intent_id=review.intent_id,
        run_status="success" if summary.get("status", "success") == "success" else "blocked",
        blocked_reason=summary.get("blocked_reason", ""),
        claims=observed,
        figure_elements=[ObservedFigureElement(**item.model_dump()) for item in review.figures],
        detected_mutation_ids=detected,
        stale_trials=stale_trials,
        stale_detected=stale_detected,
        usable_completion=review.usable_completion,
        blocked_run_human_reviewed=bool(review.blocked_reason_review) if summary.get("status") == "blocked" else False,
        false_block_human_reviewed=bool(review.blocked_reason_review),
        expected_retrieval_targets_observed=review.expected_retrieval_targets_observed,
        section_claim_order=review.section_claim_order,
        figure_claim_ids=review.figure_claim_ids,
        support_verdict_signature=_support_signature(observed),
        latency_seconds=review.latency_seconds,
        provenance={
            "run_summary": _digest_file(summary_path), "reviewer": review.reviewer,
            "reviewed_at": review.reviewed_at, "protocol_spec_digest": review.protocol_spec_digest,
            "repo_snapshot_id": review.repo_snapshot_id, "model_id": review.model_id,
            "capability_profile_digest": review.capability_profile_digest, **trial_provenance,
        },
    )


def _mutation_trials(case: BenchmarkCaseV2, review: BenchmarkRunReviewV2) -> tuple[list[str], int, int, dict[str, str]]:
    expected = {item.mutation_id: item for item in case.mutations}
    reviewed = {item.mutation_id: item for item in review.mutation_trials}
    if set(reviewed) != set(expected):
        missing = sorted(set(expected) - set(reviewed))
        extra = sorted(set(reviewed) - set(expected))
        raise ValueError(f"mutation trial coverage mismatch:missing={missing}:extra={extra}")
    provenance: dict[str, str] = {}
    stale_trials = stale_detected = 0
    for mutation_id, trial in reviewed.items():
        path = Path(trial.trial_artifact_path).resolve()
        _require_digest(path, trial.trial_artifact_digest, f"mutation_trial:{mutation_id}")
        provenance[f"mutation_trial:{mutation_id}"] = trial.trial_artifact_digest
        if expected[mutation_id].category in {"source_stale", "artifact_stale"}:
            stale_trials += 1
            stale_detected += int(trial.detected)
    return sorted(key for key, item in reviewed.items() if item.detected), stale_trials, stale_detected, provenance


def _artifact_json(artifacts: dict, key: str, *, required: bool) -> tuple[dict, str]:
    record = artifacts.get(key)
    if not record:
        if required:
            raise ValueError(f"required benchmark artifact missing:{key}")
        return {}, ""
    path = Path(record["path"]).resolve()
    digest = record.get("hash", "")
    _require_digest(path, digest, key)
    return _read_json(path), digest


def _completion_asset_lineage(completion: dict) -> bool:
    checks = {item.get("name"): bool(item.get("passed")) for item in completion.get("checks", [])}
    return all(checks.get(name, False) for name in ("method_figure", "traceability", "final_package"))


def _support_signature(claims: list[ObservedClaim]) -> str:
    values = sorted((item.gold_claim_id, item.verdict) for item in claims if item.gold_claim_id)
    payload = json.dumps(values, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _require_digest(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"reviewed artifact missing:{label}:{path}")
    actual = _digest_file(path)
    if not expected or actual != expected:
        raise ValueError(f"reviewed artifact digest mismatch:{label}")
