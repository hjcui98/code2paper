"""Method draft fidelity validation."""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.schemas import (
    ClaimEvidenceMap,
    EvidenceStrength,
    FidelityIssue,
    MethodEvidence,
    MethodFidelityReport,
    RawEvidencePack,
    Severity,
    SupportStatus,
)
from code2paper.validators.reverse_outline_validator import _is_non_paragraph, _parse_grounding, validate_reverse_outline


def validate_method_fidelity(
    *,
    raw_pack: RawEvidencePack,
    method_evidence: MethodEvidence,
    draft_markdown: str,
    claim_map: ClaimEvidenceMap | None = None,
) -> MethodFidelityReport:
    """Validate that a method draft remains grounded in hard implementation evidence."""

    issues: list[FidelityIssue] = []
    issue_counter = 1
    reverse_report = validate_reverse_outline(draft_markdown, method_evidence)
    for paragraph in reverse_report.ungrounded_paragraphs:
        issues.append(
            _issue(
                issue_counter,
                category="ungrounded_paragraph",
                severity=Severity.HIGH,
                message="Draft paragraph has no c2p grounding metadata.",
                paragraph=paragraph,
            )
        )
        issue_counter += 1
    for unknown in reverse_report.unknown_references:
        issues.append(
            _issue(
                issue_counter,
                category="unknown_reference",
                severity=Severity.HIGH,
                message=unknown,
            )
        )
        issue_counter += 1

    evidence_by_id = {item.evidence_id: item for item in raw_pack.evidence_items}
    grounded_paragraphs = _grounded_paragraphs(draft_markdown)
    for paragraph, evidence_ids in grounded_paragraphs:
        known_items = [evidence_by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in evidence_by_id]
        if not known_items:
            issues.append(
                _issue(
                    issue_counter,
                    category="missing_evidence_item",
                    severity=Severity.HIGH,
                    message="Grounded paragraph references no known raw evidence item.",
                    evidence_ids=evidence_ids,
                    paragraph=paragraph,
                )
            )
            issue_counter += 1
            continue
        strengths = {item.evidence_strength for item in known_items}
        if EvidenceStrength.HARD not in strengths:
            issues.append(
                _issue(
                    issue_counter,
                    category="soft_or_author_only_support",
                    severity=Severity.HIGH,
                    message="Main draft paragraph is supported only by soft/comment or author semantic-hint evidence.",
                    evidence_ids=evidence_ids,
                    paragraph=paragraph,
                )
            )
            issue_counter += 1

    if claim_map is not None:
        draft_lower = draft_markdown.lower()
        for claim in claim_map.claims:
            if claim.support_status != SupportStatus.UNSUPPORTED:
                continue
            claim_text = claim.claim_text.strip()
            if claim_text and claim_text.lower() in draft_lower:
                issues.append(
                    _issue(
                        issue_counter,
                        category="unsupported_claim_leaked",
                        severity=Severity.HIGH,
                        message="Unsupported claim text appears in method draft.",
                        evidence_ids=claim.evidence_ids,
                        paragraph=claim_text,
                    )
                )
                issue_counter += 1

    return MethodFidelityReport(
        project_id=method_evidence.project_id,
        passed=not any(issue.severity == Severity.HIGH for issue in issues),
        grounded_paragraphs=reverse_report.grounded_paragraphs,
        issues=issues,
        checked_claims=len(claim_map.claims) if claim_map else 0,
        checked_evidence_items=len(raw_pack.evidence_items),
    )


def validate_method_fidelity_from_files(
    *,
    raw_evidence_path: str | Path,
    method_evidence_path: str | Path,
    draft_markdown_path: str | Path,
    claim_map_path: str | Path | None = None,
) -> MethodFidelityReport:
    raw_pack = RawEvidencePack.model_validate(json.loads(Path(raw_evidence_path).read_text(encoding="utf-8")))
    method_evidence = MethodEvidence.model_validate(json.loads(Path(method_evidence_path).read_text(encoding="utf-8")))
    draft_markdown = Path(draft_markdown_path).read_text(encoding="utf-8")
    claim_map = None
    if claim_map_path is not None:
        claim_map = ClaimEvidenceMap.model_validate(json.loads(Path(claim_map_path).read_text(encoding="utf-8")))
    return validate_method_fidelity(
        raw_pack=raw_pack,
        method_evidence=method_evidence,
        draft_markdown=draft_markdown,
        claim_map=claim_map,
    )


def _grounded_paragraphs(markdown_text: str) -> list[tuple[str, list[str]]]:
    result: list[tuple[str, list[str]]] = []
    last_grounding: dict[str, list[str] | str] | None = None
    in_math = False
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "$$":
            in_math = not in_math
            continue
        if in_math:
            continue
        if line.startswith("<!-- c2p:"):
            last_grounding = _parse_grounding(line)
            continue
        if _is_non_paragraph(line):
            continue
        if last_grounding is None:
            continue
        evidence_ids = [item for item in list(last_grounding.get("evidence", [])) if item != "none"]
        result.append((line, evidence_ids))
        last_grounding = None
    return result


def _issue(
    index: int,
    *,
    category: str,
    severity: Severity,
    message: str,
    evidence_ids: list[str] | None = None,
    paragraph: str = "",
) -> FidelityIssue:
    return FidelityIssue(
        issue_id=f"F{index}",
        category=category,
        severity=severity,
        message=message,
        evidence_ids=evidence_ids or [],
        paragraph=paragraph,
    )
