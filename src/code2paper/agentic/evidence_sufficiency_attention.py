from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from code2paper.agentic.evidence_sufficiency import EvidenceSufficiencyReport


def evidence_sufficiency_attention(
    report: EvidenceSufficiencyReport,
    *,
    evidence_revision_round: int,
    max_evidence_revision_rounds: int,
) -> dict[str, Any]:
    repair_focus = _dedupe([*report.missing_evidence_claim_ids, *report.unsupported_claim_ids])
    return {
        "safe_claim_ids": report.safe_claim_ids[:20],
        "caveated_claim_ids": report.caveated_claim_ids[:20],
        "unsupported_claim_ids": report.unsupported_claim_ids[:20],
        "missing_evidence_claim_ids": report.missing_evidence_claim_ids[:20],
        "repair_focus_claim_ids": repair_focus[:20],
        "frozen_evidence_ids": report.frozen_evidence_ids[:20],
        "revision_budget_remaining": max(0, max_evidence_revision_rounds - evidence_revision_round),
        "hard_gate_passed": report.hard_gate_passed,
        "support_rate": report.support_rate,
    }


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
