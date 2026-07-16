"""Reverse-outline validation for method drafts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from code2paper.core.schemas import MethodEvidence


@dataclass
class ReverseOutlineReport:
    passed: bool
    grounded_paragraphs: int = 0
    ungrounded_paragraphs: list[str] = field(default_factory=list)
    unknown_references: list[str] = field(default_factory=list)


def validate_reverse_outline(markdown_text: str, method_evidence: MethodEvidence) -> ReverseOutlineReport:
    """Check that draft paragraphs can be traced to stages, mechanisms, and evidence IDs."""

    valid_stages = {stage.stage_id for stage in method_evidence.stages}
    valid_mechanisms = {mechanism.mechanism_id for stage in method_evidence.stages for mechanism in stage.mechanisms}
    valid_mechanisms.update(
        mechanism.mechanism_id
        for mechanism in getattr(method_evidence, "frozen_mechanisms", [])
        if getattr(mechanism, "mechanism_id", "")
    )
    valid_evidence = {
        evidence_id
        for stage in method_evidence.stages
        for mechanism in stage.mechanisms
        for evidence_id in mechanism.evidence_ids
    }
    valid_evidence.update(
        evidence_id
        for mechanism in getattr(method_evidence, "frozen_mechanisms", [])
        for evidence_id in (getattr(mechanism, "evidence_ids", None) or getattr(mechanism, "evidence_span_ids", []) or [])
        if evidence_id
    )
    last_grounding: dict[str, list[str] | str] | None = None
    grounded = 0
    ungrounded: list[str] = []
    unknown: list[str] = []
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
            ungrounded.append(line)
            continue
        stage = str(last_grounding.get("stage", ""))
        mechanisms = list(last_grounding.get("mechanisms", []))
        evidence_ids = list(last_grounding.get("evidence", []))
        if stage != "ALL" and stage not in valid_stages:
            unknown.append(f"unknown stage: {stage}")
        for mechanism_id in mechanisms:
            if mechanism_id != "none" and mechanism_id not in valid_mechanisms:
                unknown.append(f"unknown mechanism: {mechanism_id}")
        for evidence_id in evidence_ids:
            if evidence_id != "none" and evidence_id not in valid_evidence:
                unknown.append(f"unknown evidence: {evidence_id}")
        if not mechanisms or mechanisms == ["none"] or not evidence_ids or evidence_ids == ["none"]:
            ungrounded.append(line)
        else:
            grounded += 1
        last_grounding = None

    return ReverseOutlineReport(
        passed=not ungrounded and not unknown,
        grounded_paragraphs=grounded,
        ungrounded_paragraphs=ungrounded,
        unknown_references=unknown,
    )


def _parse_grounding(line: str) -> dict[str, list[str] | str]:
    content = line.removeprefix("<!-- c2p:").removesuffix("-->").strip()
    result: dict[str, list[str] | str] = {}
    for part in content.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {"mechanisms", "evidence"}:
            result[key] = [item.strip() for item in value.split(",") if item.strip()]
        else:
            result[key] = value
    return result


def _is_non_paragraph(line: str) -> bool:
    return bool(
        line.startswith("#")
        or line.startswith("- ")
        or re.match(r"^\s*<[^>]+>\s*$", line)
    )
