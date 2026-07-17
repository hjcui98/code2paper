from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.cutover import CutoverDecisionV2, ValidatedRolloutEvidenceV2


class RolloutArtifactModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RolloutTrialArtifactV2(RolloutArtifactModel):
    schema_version: Literal["code2paper-agentic-rollout-trial/v1"] = "code2paper-agentic-rollout-trial/v1"
    stage: Literal["shadow", "opt_in", "canary"]
    case_id: str
    authorization_decision_path: str
    authorization_decision_digest: str
    agentic_run_summary_path: str
    agentic_run_summary_digest: str
    legacy_run_summary_path: str = ""
    legacy_run_summary_digest: str = ""
    reviewer: str
    reviewed_at: str
    accepted: bool
    incident_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _trial_is_attributable(self) -> "RolloutTrialArtifactV2":
        if not self.case_id.strip():
            raise ValueError("rollout trial requires case_id")
        if not self.reviewer.strip() or self.reviewer == "__REQUIRED_NAMED_HUMAN__":
            raise ValueError("rollout trial requires a named reviewer")
        try:
            timestamp = datetime.fromisoformat(self.reviewed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("rollout reviewed_at must be ISO-8601") from exc
        if timestamp.tzinfo is None:
            raise ValueError("rollout reviewed_at must include a timezone")
        if self.stage == "shadow" and (not self.legacy_run_summary_path or not self.legacy_run_summary_digest):
            raise ValueError("shadow rollout requires a legacy comparison run")
        if self.stage != "canary" and self.incident_ids:
            raise ValueError("only canary rollout artifacts may report incidents")
        if len(self.incident_ids) != len(set(self.incident_ids)):
            raise ValueError("rollout incident IDs must be unique")
        return self


def validate_rollout_artifacts(
    paths: list[str | Path],
    *,
    expected_case_ids: set[str],
    protocol_commit: str,
    gold_digest: str,
) -> ValidatedRolloutEvidenceV2:
    trials: list[RolloutTrialArtifactV2] = []
    digests: list[str] = []
    identities: set[tuple[str, str]] = set()
    for source in paths:
        path = Path(source).expanduser().resolve()
        trial = RolloutTrialArtifactV2.model_validate_json(path.read_text(encoding="utf-8"))
        identity = (trial.stage, trial.case_id)
        if identity in identities:
            raise ValueError(f"duplicate rollout trial:{trial.stage}:{trial.case_id}")
        identities.add(identity)
        if trial.case_id not in expected_case_ids:
            raise ValueError(f"rollout trial case is outside the benchmark:{trial.case_id}")
        _validate_authorization(
            trial,
            protocol_commit=protocol_commit,
            gold_digest=gold_digest,
        )
        _validate_agentic_run(trial.agentic_run_summary_path, trial.agentic_run_summary_digest)
        if trial.stage == "shadow":
            _validate_legacy_run(trial.legacy_run_summary_path, trial.legacy_run_summary_digest)
        if not trial.accepted:
            raise ValueError(f"rollout trial was not accepted:{trial.stage}:{trial.case_id}")
        trials.append(trial)
        digests.append(_digest(path))
    return ValidatedRolloutEvidenceV2(
        source="digest_pinned_rollout_artifacts" if trials else "none",
        artifact_digests=digests,
        shadow_case_ids=sorted(item.case_id for item in trials if item.stage == "shadow"),
        opt_in_case_ids=sorted(item.case_id for item in trials if item.stage == "opt_in"),
        canary_case_ids=sorted(item.case_id for item in trials if item.stage == "canary"),
        canary_incidents=sum(len(item.incident_ids) for item in trials if item.stage == "canary"),
    )


def _validate_authorization(
    trial: RolloutTrialArtifactV2,
    *,
    protocol_commit: str,
    gold_digest: str,
) -> None:
    path = Path(trial.authorization_decision_path).expanduser().resolve()
    _require_digest(path, trial.authorization_decision_digest, "rollout authorization decision")
    decision = CutoverDecisionV2.model_validate_json(path.read_text(encoding="utf-8"))
    expected_status = {
        "shadow": "shadow_ready",
        "opt_in": "opt_in_ready",
        "canary": "canary_ready",
    }[trial.stage]
    if decision.status != expected_status or not decision.hard_gates_passed:
        raise ValueError(f"rollout stage lacks {expected_status} authorization")
    if decision.default_mode != "legacy":
        raise ValueError("pre-default rollout authorization must retain the legacy default")
    if decision.protocol_commit != protocol_commit or decision.gold_digest != gold_digest:
        raise ValueError("rollout authorization does not match the frozen benchmark protocol")
    if decision.named_review_evidence.source != "digest_pinned_review_artifacts":
        raise ValueError("rollout authorization lacks digest-pinned named reviews")


def _validate_agentic_run(path_value: str, digest: str) -> None:
    path = Path(path_value).expanduser().resolve()
    _require_digest(path, digest, "rollout agentic run summary")
    summary = _read_json(path)
    if summary.get("status") != "success" or not summary.get("invariant_audit_passed"):
        raise ValueError("rollout agentic run is not a trusted success")
    completion_record = summary.get("artifacts", {}).get("agentic_run_completion_report")
    if not isinstance(completion_record, dict):
        raise ValueError("rollout agentic run lacks a completion report")
    completion_path = Path(str(completion_record.get("path") or "")).resolve()
    _require_digest(completion_path, str(completion_record.get("hash") or ""), "rollout completion report")
    if not _read_json(completion_path).get("complete"):
        raise ValueError("rollout agentic run completion is not complete")


def _validate_legacy_run(path_value: str, digest: str) -> None:
    path = Path(path_value).expanduser().resolve()
    _require_digest(path, digest, "rollout legacy run summary")
    summary = _read_json(path)
    if not summary.get("fidelity_passed"):
        raise ValueError("rollout legacy comparison did not complete its legacy contract")


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required:{path}")
    return payload


def _require_digest(path: Path, expected: str, label: str) -> None:
    if not path.is_file() or _digest(path) != expected:
        raise ValueError(f"{label} digest mismatch")


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
