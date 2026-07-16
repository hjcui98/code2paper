"""Basic alignment validation helpers."""

from __future__ import annotations

from code2paper.core.schemas import CodeAlignmentIR


def check_alignment(alignment: CodeAlignmentIR) -> list[str]:
    issues: list[str] = []
    if not alignment.entrypoints:
        issues.append("no_entrypoints_detected")
    if not alignment.method_stages:
        issues.append("no_method_stages_detected")
    if not alignment.stage_mappings:
        issues.append("no_stage_mappings_detected")
    return issues

