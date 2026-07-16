from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from code2paper.agentic.revision_context import RevisionDecisionContext


def revision_validation_attention(
    context: RevisionDecisionContext | None,
    *,
    validation: dict[str, Any],
) -> dict[str, Any]:
    if context is None:
        return {
            "validation": validation,
            "issue_count": 0,
            "recommended_next": "",
            "top_issues": [],
            "invariant_passed": None,
            "traceability_passed": None,
        }
    return {
        "validation": validation,
        "blocked_reason": context.blocked_reason,
        "validation_status": context.validation_status,
        "issue_count": context.issue_count,
        "recommended_next": context.recommended_next,
        "recommended_actions": context.recommended_actions[:12],
        "invariant_passed": context.invariant_passed,
        "traceability_passed": context.traceability_passed,
        "top_issues": [
            {
                "source_artifact": issue.source_artifact,
                "category": issue.category,
                "severity": issue.severity,
                "message": issue.message,
                "evidence_ids": issue.evidence_ids,
                "recommended_next": issue.recommended_next,
            }
            for issue in context.issues[:8]
        ],
    }
