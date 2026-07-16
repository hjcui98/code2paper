"""Paper-readiness checks for generated Method drafts."""

from __future__ import annotations

import re
from typing import Any


GROUNDING_COMMENT_RE = re.compile(r"<!--\s*c2p:.*?-->", re.DOTALL)
DISPLAY_EQUATION_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
HEADING_RE = re.compile(r"^\s{0,3}#{1,4}\s+(.+?)\s*$", re.MULTILINE)


def validate_paper_readiness(markdown: str, *, reference_text: str = "") -> dict[str, Any]:
    """Check whether a Method draft reads like a paper section rather than an audit report."""

    raw_text = str(markdown or "")
    visible_text = GROUNDING_COMMENT_RE.sub("", raw_text)
    lower_text = visible_text.lower()
    issues: list[dict[str, str]] = []

    words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]*", visible_text)
    equations = DISPLAY_EQUATION_RE.findall(visible_text)
    headings = [heading.strip() for heading in HEADING_RE.findall(visible_text)]
    bullet_lines = [
        line
        for line in visible_text.splitlines()
        if re.match(r"^\s*[-*]\s+", line)
    ]
    prose_paragraphs = [
        para.strip()
        for para in re.split(r"\n\s*\n", visible_text)
        if para.strip() and not para.strip().startswith("#") and not para.strip().startswith("$$")
    ]
    orphan_explanations = _count_orphan_equation_explanations(visible_text)

    if len(words) < 600:
        _add_issue(issues, "PR1", "high", "coverage", "Method draft is too short for a directly usable paper Method section.")
    if len(words) > 1800:
        _add_issue(issues, "PR2", "medium", "conciseness", "Method draft is likely too long and may read like notes rather than a paper section.")
    if not headings or len(headings) < 4:
        _add_issue(issues, "PR3", "high", "structure", "Method draft needs multiple paper-style subsections.")
    if not _has_any_heading(headings, ("overview", "framework")):
        _add_issue(issues, "PR4", "high", "structure", "Method draft needs an overview/framework subsection.")
    if not _has_any_heading(headings, ("objective", "loss", "training")):
        _add_issue(issues, "PR5", "high", "objective", "Method draft must contain a dedicated objective/loss discussion.")
    if len(equations) < 3:
        _add_issue(issues, "PR6", "high", "equations", "Method draft has too few equations to explain the method rigorously.")
    equation_budget = _adaptive_equation_budget(word_count=len(words), heading_count=len(headings))
    if len(equations) > equation_budget:
        severity = "high" if len(equations) > equation_budget + 4 else "medium"
        _add_issue(
            issues,
            "PR7",
            severity,
            "equations",
            "Method draft has high equation density; keep equations that define the method flow and remove helper-only formulas.",
        )
    if len(bullet_lines) > 6:
        _add_issue(issues, "PR8", "high", "style", "Method draft is too bullet-heavy; rewrite as conference-paper prose.")
    audit_terms = (
        "mechanism formulation",
        "code-backed mechanism details",
        "evidence-grounded pipeline",
        "equation candidate",
        "generated from a recognized code pattern",
        "grounded objective fragment",
        "submech",
    )
    if any(term in lower_text for term in audit_terms):
        _add_issue(issues, "PR9", "high", "style", "Remove audit-style mechanism/equation report text from the Method draft.")
    if "partially supported" in lower_text or "evidence-backed" in lower_text:
        _add_issue(issues, "PR10", "medium", "style", "Avoid audit vocabulary such as 'partially supported' or 'evidence-backed' in paper prose.")
    if re.search(r"[A-Za-z]:\\|/home/|\.py\b|python -m|--[A-Za-z0-9_\-]+|`[^`]+`|\b__init__\b|\brun_net\b", visible_text):
        _add_issue(issues, "PR11", "high", "implementation_leakage", "Paper prose contains file paths, script names, or CLI arguments.")
    if re.search(
        r"\b(parsing configurations?|building datasets|deciding the task mode|experimental setup begins|global entrypoint|entrypoint|dropout|checkpoint|logger|ddp|voting mechanism|performance metrics|standard metrics|intersection over union|iou scores?|fine-tuning|finetuning|evaluation flow|downstream datasets?)\b",
        lower_text,
    ):
        _add_issue(issues, "PR16", "medium", "implementation_leakage", "Paper prose still promotes low-priority setup or regularization details.")
    if re.search(
        r"\b(validation|testing|evaluation|fine-?tune|fine-tuning|finetune|finetuning|target dataset|downstream dataset|downstream classification|downstream segmentation)\b",
        lower_text,
    ) and not re.search(r"\b(method contribution|loss|objective|prediction head|decoder|encoder|module)\b", lower_text):
        _add_issue(issues, "PR17", "medium", "experiment_protocol", "Paper prose appears to include experimental protocol details instead of method mechanics.")
    if prose_paragraphs and _median_sentence_count(prose_paragraphs) < 2:
        _add_issue(issues, "PR12", "medium", "style", "Several paragraphs are too fragmentary; use connected explanatory prose.")
    if orphan_explanations:
        _add_issue(issues, "PR15", "high", "equations", "Method draft has equation explanations that no longer follow a displayed equation.")

    if reference_text.strip():
        ref_words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]*", reference_text)
        ref_equations = DISPLAY_EQUATION_RE.findall(reference_text)
        if len(words) < max(500, int(len(ref_words) * 0.7)):
            _add_issue(issues, "PR13", "medium", "reference_coverage", "Draft is substantially shorter than the reference Method section.")
        if ref_equations and len(equations) < min(4, len(ref_equations)):
            _add_issue(issues, "PR14", "medium", "reference_equations", "Draft has fewer core equations than the reference Method section.")

    high_count = sum(1 for issue in issues if issue["severity"] == "high")
    medium_count = sum(1 for issue in issues if issue["severity"] == "medium")
    score = max(0, 100 - high_count * 18 - medium_count * 7)
    return {
        "passed": high_count == 0 and score >= 82,
        "score": score,
        "issue_count": len(issues),
        "high_issue_count": high_count,
        "medium_issue_count": medium_count,
        "metrics": {
            "word_count": len(words),
            "display_equation_count": len(equations),
            "adaptive_equation_budget": equation_budget,
            "heading_count": len(headings),
            "bullet_line_count": len(bullet_lines),
        },
        "issues": issues,
    }


def _has_any_heading(headings: list[str], needles: tuple[str, ...]) -> bool:
    return any(any(needle in heading.lower() for needle in needles) for heading in headings)


def _adaptive_equation_budget(*, word_count: int, heading_count: int) -> int:
    """Allow formula-heavy methods without letting helper equations dominate the prose."""

    by_length = max(6, word_count // 140)
    by_structure = max(6, heading_count + 3)
    return min(14, max(8, by_length, by_structure))


def _median_sentence_count(paragraphs: list[str]) -> int:
    counts = sorted(
        max(1, len(re.findall(r"[.!?](?:\s|$)", GROUNDING_COMMENT_RE.sub("", para))))
        for para in paragraphs
        if para.strip()
    )
    if not counts:
        return 0
    return counts[len(counts) // 2]


def _count_orphan_equation_explanations(text: str) -> int:
    paragraphs = [para.strip() for para in re.split(r"\n\s*\n", text) if para.strip()]
    count = 0
    previous_was_equation = False
    for paragraph in paragraphs:
        is_equation = paragraph.startswith("$$") and paragraph.endswith("$$")
        starts_like_explanation = bool(re.match(r"(?i)^(where|here|in this expression|this equation)\b", paragraph))
        if starts_like_explanation and not previous_was_equation:
            count += 1
        previous_was_equation = is_equation
    return count


def _add_issue(issues: list[dict[str, str]], issue_id: str, severity: str, category: str, message: str) -> None:
    issues.append(
        {
            "issue_id": issue_id,
            "severity": severity,
            "category": category,
            "message": message,
            "paragraph_id": "",
        }
    )
