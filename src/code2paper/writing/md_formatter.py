"""Markdown formatting helpers for method drafts."""

from __future__ import annotations


def grounding_comment(
    *,
    stage_id: str,
    mechanism_ids: list[str],
    evidence_ids: list[str],
    confidence: str,
) -> str:
    mechanisms = ",".join(mechanism_ids) if mechanism_ids else "none"
    evidence = ",".join(evidence_ids) if evidence_ids else "none"
    return f"<!-- c2p: stage={stage_id}; mechanisms={mechanisms}; evidence={evidence}; confidence={confidence} -->"


def normalize_markdown(lines: list[str]) -> str:
    """Collapse excessive blank lines while preserving readable Markdown."""

    normalized: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                normalized.append("")
            blank = True
            continue
        normalized.append(line.rstrip())
        blank = False
    while normalized and not normalized[-1]:
        normalized.pop()
    return "\n".join(normalized) + "\n"

