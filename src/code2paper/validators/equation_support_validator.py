"""Validate that draft equations are supported by Method Evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from code2paper.schemas import MethodEvidence, Severity


@dataclass
class EquationSupportIssue:
    issue_id: str
    severity: Severity
    category: str
    message: str
    equation: str
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class EquationSupportReport:
    project_id: str
    passed: bool
    checked_equations: int = 0
    issues: list[EquationSupportIssue] = field(default_factory=list)

    def model_dump(self, mode: str = "python") -> dict:
        return {
            "project_id": self.project_id,
            "passed": self.passed,
            "checked_equations": self.checked_equations,
            "issues": [
                {
                    "issue_id": issue.issue_id,
                    "severity": issue.severity.value,
                    "category": issue.category,
                    "message": issue.message,
                    "equation": issue.equation,
                    "evidence_ids": issue.evidence_ids,
                }
                for issue in self.issues
            ],
        }


def validate_equation_support(
    *,
    method_evidence: MethodEvidence,
    draft_markdown: str,
    draft_latex: str = "",
) -> EquationSupportReport:
    supported = [
        (equation.latex, equation.evidence_ids)
        for equation in method_evidence.equation_candidates
        if equation.evidence_ids
    ]
    equations = _dedupe(_extract_markdown_equations(draft_markdown) + _extract_latex_equations(draft_latex))
    issues: list[EquationSupportIssue] = []
    for index, equation in enumerate(equations, start=1):
        match = _matching_supported_equation(equation, supported)
        if match is None:
            issues.append(
                EquationSupportIssue(
                    issue_id=f"EQV{len(issues) + 1}",
                    severity=Severity.HIGH,
                    category="unsupported_equation",
                    message="Draft equation is not backed by a Method Evidence equation candidate.",
                    equation=equation,
                )
            )
    return EquationSupportReport(
        project_id=method_evidence.project_id,
        passed=not any(issue.severity == Severity.HIGH for issue in issues),
        checked_equations=len(equations),
        issues=issues,
    )


def _extract_markdown_equations(markdown: str) -> list[str]:
    equations: list[str] = []
    in_block = False
    block_lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line == "$$":
            if in_block:
                equation = "\n".join(block_lines).strip()
                if equation:
                    equations.append(equation)
                block_lines = []
            in_block = not in_block
            continue
        if in_block:
            block_lines.append(raw_line)
    equations.extend(match.strip() for match in re.findall(r"\$(?!\$)(.+?)(?<!\$)\$", markdown, flags=re.DOTALL))
    return [equation for equation in equations if equation]


def _extract_latex_equations(latex: str) -> list[str]:
    equations: list[str] = []
    patterns = [
        re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
        re.compile(r"\\begin\{equation\*?\}(.+?)\\end\{equation\*?\}", re.DOTALL),
        re.compile(r"\\begin\{align\*?\}(.+?)\\end\{align\*?\}", re.DOTALL),
    ]
    for pattern in patterns:
        equations.extend(match.strip() for match in pattern.findall(latex))
    return [equation for equation in equations if equation]


def _matching_supported_equation(equation: str, supported: list[tuple[str, list[str]]]) -> list[str] | None:
    normalized = _normalize_equation(equation)
    for candidate, evidence_ids in supported:
        candidate_normalized = _normalize_equation(candidate)
        if not candidate_normalized:
            continue
        if candidate_normalized in normalized or normalized in candidate_normalized:
            return evidence_ids
    return None


def _normalize_equation(equation: str) -> str:
    equation = re.sub(r"%.*", "", equation)
    equation = equation.replace(r"\left", "").replace(r"\right", "")
    return re.sub(r"\s+", "", equation)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _normalize_equation(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
