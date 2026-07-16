from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import AgenticRunState


class RevisionIssue(BaseModel):
    """Compact validator or invariant issue for revision routing."""

    model_config = ConfigDict(extra="forbid")

    source_artifact: str
    category: str = ""
    severity: str = ""
    message: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    recommended_next: str = ""


class RevisionDecisionContext(BaseModel):
    """Model-facing revision context derived from validators and evidence gates."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "revision-decision-context"
    blocked_reason: str = ""
    validation_status: str = ""
    invariant_passed: bool | None = None
    traceability_passed: bool | None = None
    issue_count: int = 0
    issues: list[RevisionIssue] = Field(default_factory=list)
    recommended_next: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    summary: str = ""


def build_revision_decision_context(state: AgenticRunState) -> RevisionDecisionContext:
    """Build a compact revision-routing context from current validation artifacts."""

    issues: list[RevisionIssue] = []
    validation_manifest = _artifact_json(state, "validation_manifest")
    validation_status = str(validation_manifest.get("status") or "")
    issues.extend(_issues_from_fidelity(state))
    issues.extend(_issues_from_validation_reports(state))
    issues.extend(_issues_from_invariant_audit(state))
    issues.extend(_issues_from_traceability_ledger(state))
    recommended_next = _recommended_next(blocked_reason=state.blocked_reason, issues=issues)
    actions = _recommended_actions(blocked_reason=state.blocked_reason, recommended_next=recommended_next, issues=issues)
    invariant_payload = _artifact_json(state, "agentic_invariant_audit")
    ledger_payload = _artifact_json(state, "traceability_ledger")
    return RevisionDecisionContext(
        blocked_reason=state.blocked_reason,
        validation_status=validation_status,
        invariant_passed=bool(invariant_payload.get("passed")) if invariant_payload else None,
        traceability_passed=bool(ledger_payload.get("hard_gate_passed")) if ledger_payload else None,
        issue_count=len(issues),
        issues=issues[:40],
        recommended_next=recommended_next,
        recommended_actions=actions,
        summary=_summary(blocked_reason=state.blocked_reason, validation_status=validation_status, issues=issues, recommended_next=recommended_next),
    )


def write_revision_decision_context(path: str | Path, context: RevisionDecisionContext) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(context.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_revision_decision_context(path: str | Path) -> RevisionDecisionContext | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return RevisionDecisionContext.model_validate(payload)
    except Exception:
        return None


def _issues_from_fidelity(state: AgenticRunState) -> list[RevisionIssue]:
    payload = _artifact_json(state, "fidelity")
    issues = []
    for issue in _as_list(payload.get("issues")):
        if not isinstance(issue, dict):
            continue
        issues.append(
            RevisionIssue(
                source_artifact="fidelity",
                category=str(issue.get("category") or "fidelity"),
                severity=str(issue.get("severity") or ""),
                message=str(issue.get("message") or ""),
                evidence_ids=_as_string_list(issue.get("evidence_ids")),
                recommended_next=_issue_route(str(issue.get("category") or ""), str(issue.get("message") or "")),
            )
        )
    return issues


def _issues_from_validation_reports(state: AgenticRunState) -> list[RevisionIssue]:
    issues: list[RevisionIssue] = []
    for key in ("qa_claims", "qa_numbers", "qa_equations", "qa_terms", "qa_latex"):
        payload = _artifact_json(state, key)
        for issue in _extract_generic_issues(payload):
            issues.append(issue.model_copy(update={"source_artifact": key}))
    return issues


def _issues_from_invariant_audit(state: AgenticRunState) -> list[RevisionIssue]:
    payload = _artifact_json(state, "agentic_invariant_audit")
    issues: list[RevisionIssue] = []
    for check in _as_list(payload.get("checks")):
        if not isinstance(check, dict) or bool(check.get("passed")):
            continue
        issues.append(
            RevisionIssue(
                source_artifact="agentic_invariant_audit",
                category=str(check.get("name") or "invariant"),
                severity="blocking" if check.get("blocking", True) else "warning",
                message=str(check.get("message") or ""),
                recommended_next=_issue_route(str(check.get("name") or ""), str(check.get("message") or "")),
            )
        )
    return issues


def _issues_from_traceability_ledger(state: AgenticRunState) -> list[RevisionIssue]:
    payload = _artifact_json(state, "traceability_ledger")
    if not payload or bool(payload.get("hard_gate_passed", True)):
        return []
    issues: list[RevisionIssue] = []
    for entry in _as_list(payload.get("entries")):
        if not isinstance(entry, dict) or str(entry.get("trace_status") or "") in {"", "supported", "excluded_claim"}:
            continue
        issues.append(
            RevisionIssue(
                source_artifact="traceability_ledger",
                category=str(entry.get("trace_status") or "traceability"),
                severity="blocking",
                message=str(entry.get("entry_id") or "") + ": " + "; ".join(_as_string_list(entry.get("notes"))),
                evidence_ids=_as_string_list(entry.get("evidence_ids")),
                recommended_next=_issue_route(str(entry.get("trace_status") or ""), "; ".join(_as_string_list(entry.get("notes")))),
            )
        )
    return issues


def _extract_generic_issues(payload: dict[str, Any]) -> list[RevisionIssue]:
    candidates: list[Any] = []
    for key in ("issues", "findings", "failures", "errors"):
        candidates.extend(_as_list(payload.get(key)))
    issues: list[RevisionIssue] = []
    for item in candidates:
        if isinstance(item, str):
            issues.append(RevisionIssue(source_artifact="", message=item, recommended_next=_issue_route("", item)))
        elif isinstance(item, dict):
            message = str(item.get("message") or item.get("detail") or item.get("reason") or "")
            issues.append(
                RevisionIssue(
                    source_artifact="",
                    category=str(item.get("category") or item.get("type") or ""),
                    severity=str(item.get("severity") or ""),
                    message=message,
                    evidence_ids=_as_string_list(item.get("evidence_ids")),
                    recommended_next=_issue_route(str(item.get("category") or item.get("type") or ""), message),
                )
            )
    return issues


def _recommended_next(*, blocked_reason: str, issues: list[RevisionIssue]) -> str:
    reason = str(blocked_reason or "").lower()
    routes = [issue.recommended_next for issue in issues if issue.recommended_next]
    if any(route == "analysis" for route in routes) or any(token in reason for token in ("evidence", "coverage", "missing", "unsupported")):
        return "analysis"
    if any(route == "authoring" for route in routes) or any(token in reason for token in ("fidelity", "claim", "latex", "number", "term", "equation")):
        return "authoring"
    if "llm_api_key_missing" in reason or "llm_required" in reason:
        return "blocked"
    if blocked_reason:
        return "blocked"
    return "validation"


def _recommended_actions(*, blocked_reason: str, recommended_next: str, issues: list[RevisionIssue]) -> list[str]:
    actions: list[str] = []
    if recommended_next == "analysis":
        actions.append("return_to_analysis_or_retrieval_for_evidence_repair")
    elif recommended_next == "authoring":
        actions.append("revise_authoring_against_validator_issues")
    elif recommended_next == "validation":
        actions.append("run_validation_before_rendering")
    elif recommended_next == "blocked":
        actions.append("manual_or_configuration_intervention_required")
    if not issues and not blocked_reason:
        actions.append("no_revision_issues_detected")
    return _dedupe(actions)


def _issue_route(category: str, message: str) -> str:
    text = f"{category} {message}".lower()
    if any(token in text for token in ("evidence", "coverage", "missing", "unknown", "unsupported", "traceability")):
        return "analysis"
    if any(token in text for token in ("fidelity", "claim", "latex", "number", "term", "equation", "paragraph")):
        return "authoring"
    return ""


def _summary(*, blocked_reason: str, validation_status: str, issues: list[RevisionIssue], recommended_next: str) -> str:
    parts = []
    if blocked_reason:
        parts.append(f"blocked_reason={blocked_reason}")
    if validation_status:
        parts.append(f"validation_status={validation_status}")
    parts.append(f"issues={len(issues)}")
    parts.append(f"recommended_next={recommended_next}")
    if issues:
        parts.append("top_issues=" + "; ".join(issue.message[:80] for issue in issues[:3] if issue.message))
    return "; ".join(parts)


def _artifact_json(state: AgenticRunState, key: str) -> dict[str, Any]:
    path = state.artifacts.get(key, "")
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
