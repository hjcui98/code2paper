"""Validate draft terminology against the Phase 4 terminology table."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from code2paper.schemas import Severity, TerminologyTable


@dataclass
class TerminologyIssue:
    issue_id: str
    severity: Severity
    category: str
    message: str
    term_id: str = ""
    term: str = ""


@dataclass
class TerminologyConsistencyReport:
    passed: bool
    checked_terms: int = 0
    issues: list[TerminologyIssue] = field(default_factory=list)

    def model_dump(self, mode: str = "python") -> dict:
        return {
            "passed": self.passed,
            "checked_terms": self.checked_terms,
            "issues": [
                {
                    "issue_id": issue.issue_id,
                    "severity": issue.severity.value,
                    "category": issue.category,
                    "message": issue.message,
                    "term_id": issue.term_id,
                    "term": issue.term,
                }
                for issue in self.issues
            ],
        }


def validate_terminology_consistency(
    *,
    terminology_table: TerminologyTable,
    draft_markdown: str,
    draft_latex: str = "",
) -> TerminologyConsistencyReport:
    """Check table-level conflicts and explicitly forbidden replacements.

    The validator intentionally avoids requiring every table term to appear in
    the draft. A paragraph may legitimately omit a mechanism. It only flags
    contradictions the terminology table can state with high confidence.
    """

    combined = _strip_markup_comments(f"{draft_markdown}\n{draft_latex}")
    issues: list[TerminologyIssue] = []
    issue_index = 1

    canonical_to_ids: dict[str, list[str]] = {}
    for term in terminology_table.terms:
        canonical_key = _normalize_term(term.canonical)
        if canonical_key:
            canonical_to_ids.setdefault(canonical_key, []).append(term.term_id)

        forbidden_terms = _dedupe(term.forbidden_replacements)
        for replacement in forbidden_terms:
            if not replacement.strip():
                continue
            if _contains_phrase(combined, replacement):
                issues.append(
                    TerminologyIssue(
                        issue_id=f"TERM{issue_index}",
                        severity=Severity.HIGH,
                        category="forbidden_replacement_used",
                        message=(
                            f"Draft uses forbidden replacement `{replacement}` for "
                            f"canonical term `{term.canonical}`."
                        ),
                        term_id=term.term_id,
                        term=replacement,
                    )
                )
                issue_index += 1

    for canonical_key, term_ids in sorted(canonical_to_ids.items()):
        unique_ids = _dedupe(term_ids)
        if len(unique_ids) <= 1:
            continue
        issues.append(
            TerminologyIssue(
                issue_id=f"TERM{issue_index}",
                severity=Severity.MEDIUM,
                category="canonical_term_collision",
                message="Terminology table maps one canonical term to multiple term IDs.",
                term_id=",".join(unique_ids),
                term=canonical_key,
            )
        )
        issue_index += 1

    return TerminologyConsistencyReport(
        passed=not any(issue.severity == Severity.HIGH for issue in issues),
        checked_terms=len(terminology_table.terms),
        issues=issues,
    )


def _contains_phrase(text: str, phrase: str) -> bool:
    escaped = re.escape(phrase.strip())
    if not escaped:
        return False
    return re.search(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", text, re.IGNORECASE) is not None


def _normalize_term(term: str) -> str:
    return re.sub(r"\s+", " ", term.strip().lower())


def _strip_markup_comments(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"%.*", " ", text)
    return text


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _normalize_term(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
