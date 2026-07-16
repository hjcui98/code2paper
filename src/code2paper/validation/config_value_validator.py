"""Validate written config and architecture values in method drafts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from code2paper.core.schemas import (
    CodeAlignmentIR,
    ConfigValueIssue,
    ConfigValueReport,
    MethodEvidence,
    Severity,
)


_ASSIGNMENT_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)"
    r"\s*=\s*"
    r"(?P<value>[A-Za-z0-9_./${}+\-]+)"
)


@dataclass
class ExpectedValue:
    key: str
    value: Any
    source: str
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class WrittenValue:
    key: str
    value: Any
    raw_value: str
    line_no: int
    line: str
    claim_kind: str = "assignment"


def validate_config_values(
    *,
    alignment: CodeAlignmentIR,
    method_evidence: MethodEvidence,
    draft_markdown: str,
) -> ConfigValueReport:
    """Check that assignment-like values in a draft match resolved evidence.

    The validator checks explicit ``key=value`` statements and conservative
    natural-language numeric phrases whose labels can be mapped to known
    architecture/config keys. For example, ``6 encoder layers`` can map to
    ``n_layers`` and ``8 heads`` can map to ``n_head``. Unrecognized prose
    numbers are ignored rather than flagged, because generic drafts contain many
    counts that are not method parameters.
    """

    expected = _collect_expected_values(alignment, method_evidence)
    issues: list[ConfigValueIssue] = []
    issue_index = 1
    written_values = _extract_written_values(draft_markdown, _natural_aliases_for_expected(expected))

    for written in written_values:
        candidates = _lookup_expected(expected, written.key)
        if not candidates:
            issues.append(
                _issue(
                    issue_index,
                    category="unknown_quantitative_key",
                    severity=Severity.HIGH,
                    message=(
                        f"Draft writes `{_written_label(written)}` on line {written.line_no}, "
                        "but no matching architecture parameter or resolved config key was found."
                    ),
                    key=written.key,
                    written_value=written.value,
                    expected_values=[],
                    evidence_ids=[],
                )
            )
            issue_index += 1
            continue

        if not any(_values_match(written.value, candidate.value) for candidate in candidates):
            issues.append(
                _issue(
                    issue_index,
                    category="quantitative_value_mismatch",
                    severity=Severity.HIGH,
                    message=(
                        f"Draft writes `{_written_label(written)}` on line {written.line_no}, "
                        "but the evidence-backed value set is different."
                    ),
                    key=written.key,
                    written_value=written.value,
                    expected_values=_unique_values([candidate.value for candidate in candidates]),
                    evidence_ids=_unique_strings(
                        evidence_id
                        for candidate in candidates
                        for evidence_id in candidate.evidence_ids
                    ),
                )
            )
            issue_index += 1

    return ConfigValueReport(
        project_id=method_evidence.project_id,
        passed=not any(issue.severity == Severity.HIGH for issue in issues),
        checked_values=len(written_values),
        issues=issues,
    )


def validate_config_values_from_files(
    *,
    alignment_path: str | Path,
    method_evidence_path: str | Path,
    draft_markdown_path: str | Path,
) -> ConfigValueReport:
    alignment = CodeAlignmentIR.model_validate(json.loads(Path(alignment_path).read_text(encoding="utf-8")))
    method_evidence = MethodEvidence.model_validate(json.loads(Path(method_evidence_path).read_text(encoding="utf-8")))
    draft_markdown = Path(draft_markdown_path).read_text(encoding="utf-8")
    return validate_config_values(
        alignment=alignment,
        method_evidence=method_evidence,
        draft_markdown=draft_markdown,
    )


def _collect_expected_values(
    alignment: CodeAlignmentIR,
    method_evidence: MethodEvidence,
) -> dict[str, list[ExpectedValue]]:
    expected: dict[str, list[ExpectedValue]] = {}
    for parameter in method_evidence.architecture_parameters:
        _add_expected(
            expected,
            ExpectedValue(
                key=parameter.name,
                value=parameter.value,
                source=f"architecture_parameter:{parameter.parameter_id}",
                evidence_ids=parameter.evidence_ids,
            ),
        )
    for resolution in alignment.config_resolutions:
        evidence_ids = _unique_strings(
            step.evidence_id for step in resolution.resolution_chain if step.evidence_id
        )
        _add_expected(
            expected,
            ExpectedValue(
                key=resolution.resolved_key,
                value=resolution.final_value,
                source="config_resolution",
                evidence_ids=evidence_ids,
            ),
        )
    return expected


def _add_expected(expected: dict[str, list[ExpectedValue]], item: ExpectedValue) -> None:
    for key in _key_variants(item.key):
        expected.setdefault(key, []).append(item)


def _lookup_expected(expected: dict[str, list[ExpectedValue]], key: str) -> list[ExpectedValue]:
    result: list[ExpectedValue] = []
    seen: set[tuple[str, str]] = set()
    for variant in _key_variants(key):
        for item in expected.get(variant, []):
            identity = (item.key, _canonical(item.value))
            if identity in seen:
                continue
            seen.add(identity)
            result.append(item)
    return result


def _key_variants(key: str) -> list[str]:
    variants = [key, key.lower()]
    if "." in key:
        variants.append(key.rsplit(".", 1)[-1])
        variants.append(key.rsplit(".", 1)[-1].lower())
    return _unique_strings(variants)


def _extract_written_values(markdown_text: str, natural_aliases: dict[str, str] | None = None) -> list[WrittenValue]:
    values: list[WrittenValue] = []
    in_math_block = False
    for line_no, raw_line in enumerate(markdown_text.splitlines(), start=1):
        line = raw_line.strip()
        if line == "$$":
            in_math_block = not in_math_block
            continue
        if in_math_block:
            continue
        if not line or line.startswith("#") or line.startswith("<!--"):
            continue
        assignment_spans: list[tuple[int, int]] = []
        for match in _ASSIGNMENT_RE.finditer(raw_line):
            raw_value = _clean_raw_value(match.group("value"))
            if not raw_value:
                continue
            assignment_spans.append(match.span())
            values.append(
                WrittenValue(
                    key=match.group("key"),
                    value=_parse_scalar(raw_value),
                    raw_value=raw_value,
                    line_no=line_no,
                    line=raw_line.strip(),
                )
            )
        values.extend(_extract_natural_values(raw_line, line_no, assignment_spans, natural_aliases or {}))
    return values


def _extract_natural_values(
    raw_line: str,
    line_no: int,
    assignment_spans: list[tuple[int, int]],
    natural_aliases: dict[str, str],
) -> list[WrittenValue]:
    values: list[WrittenValue] = []
    lowered = raw_line.lower()
    for alias, key in natural_aliases.items():
        escaped_alias = re.escape(alias)
        for pattern in (
            re.compile(rf"(?<![\w.])(?P<value>[+-]?\d+(?:\.\d+)?)\s+{escaped_alias}\b", re.IGNORECASE),
            re.compile(rf"\b{escaped_alias}\s+(?:of|is|are|was|were|:)?\s*(?P<value>[+-]?\d+(?:\.\d+)?)\b", re.IGNORECASE),
        ):
            for match in pattern.finditer(raw_line):
                if _overlaps(match.span(), assignment_spans):
                    continue
                raw_value = _clean_raw_value(match.group("value"))
                if not raw_value or _looks_like_identifier_fragment(lowered, match.span()):
                    continue
                values.append(
                    WrittenValue(
                        key=key,
                        value=_parse_scalar(raw_value),
                        raw_value=raw_value,
                        line_no=line_no,
                        line=raw_line.strip(),
                        claim_kind="natural_language",
                    )
                )
    return _dedupe_written_values(values)


def _clean_raw_value(value: str) -> str:
    return value.strip().rstrip(".,;:)")


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in spans)


def _looks_like_identifier_fragment(line: str, span: tuple[int, int]) -> bool:
    start, end = span
    before = line[max(0, start - 2) : start]
    after = line[end : end + 2]
    return "=" in before or "=" in after


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"none", "null"}:
        return None
    if re.fullmatch(r"[+-]?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?", value):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _values_match(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)) and not isinstance(right, bool):
        return abs(float(left) - float(right)) < 1e-12
    return _canonical(left) == _canonical(right)


def _canonical(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value).strip().lower()


def _unique_values(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        canonical = _canonical(value)
        if canonical in seen:
            continue
        seen.add(canonical)
        result.append(value)
    return result


def _dedupe_written_values(values: list[WrittenValue]) -> list[WrittenValue]:
    result: list[WrittenValue] = []
    seen: set[tuple[str, str, int]] = set()
    for value in values:
        key = (value.key, _canonical(value.value), value.line_no)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _unique_strings(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _issue(
    index: int,
    *,
    category: str,
    severity: Severity,
    message: str,
    key: str,
    written_value: Any,
    expected_values: list[Any],
    evidence_ids: list[str],
) -> ConfigValueIssue:
    return ConfigValueIssue(
        issue_id=f"CV{index}",
        category=category,
        severity=severity,
        message=message,
        key=key,
        written_value=written_value,
        expected_values=expected_values,
        evidence_ids=evidence_ids,
    )


def _written_label(written: WrittenValue) -> str:
    if written.claim_kind == "natural_language":
        return f"{written.raw_value} {written.key}"
    return f"{written.key}={written.raw_value}"


def _natural_aliases_for_expected(expected: dict[str, list[ExpectedValue]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    canonical_keys = {item.key for values in expected.values() for item in values}
    for key in sorted(canonical_keys):
        for alias in _aliases_for_key(key):
            aliases.setdefault(alias, key)
    for alias, key in _STATIC_NATURAL_ALIAS_TO_KEY.items():
        if _lookup_expected(expected, key):
            aliases.setdefault(alias, key)
    return dict(sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True))


def _aliases_for_key(key: str) -> list[str]:
    text = key.lower().replace(".", "_").replace("-", "_")
    tokens = [token for token in text.split("_") if token and token not in {"env"}]
    aliases: list[str] = []
    if not tokens:
        return aliases
    aliases.append(" ".join(tokens))
    if len(tokens) > 1 and tokens[0] in {"n", "num", "number"}:
        subject = " ".join(tokens[1:])
        aliases.extend([subject, _pluralize_phrase(subject), f"number of {_pluralize_phrase(subject)}"])
    if len(tokens) > 1 and tokens[0] in {"d", "dim", "dimension"}:
        subject = " ".join(tokens[1:])
        aliases.extend([f"{subject} dimension", f"{subject} dimensions", f"{subject} dim"])
    if tokens[-1] == "size" and len(tokens) > 1:
        aliases.append(" ".join(tokens))
    if tokens[-1] in {"rate", "ratio"} and len(tokens) > 1:
        aliases.append(" ".join(tokens[:-1]))
    if len(tokens) == 1:
        aliases.extend([tokens[0], _pluralize_phrase(tokens[0])])
    return _unique_strings(alias for alias in aliases if alias)


def _pluralize_phrase(phrase: str) -> str:
    parts = phrase.split()
    if not parts:
        return phrase
    last = parts[-1]
    if last.endswith("s"):
        return phrase
    if last.endswith("y"):
        parts[-1] = last[:-1] + "ies"
    else:
        parts[-1] = last + "s"
    return " ".join(parts)


_STATIC_NATURAL_ALIAS_TO_KEY = {
    "attention head": "n_head",
    "attention heads": "n_head",
    "head": "n_head",
    "heads": "n_head",
    "encoder layer": "n_layers",
    "encoder layers": "n_layers",
    "decoder layer": "n_layers",
    "decoder layers": "n_layers",
    "layer": "n_layers",
    "layers": "n_layers",
    "model layer": "n_layers",
    "model layers": "n_layers",
    "batch size": "batch_size",
    "epoch": "epoch",
    "epochs": "epoch",
    "warmup step": "n_warmup_steps",
    "warmup steps": "n_warmup_steps",
    "dropout": "dropout",
    "dropout rate": "dropout",
    "attention dropout": "attn_dropout",
    "attention dropout rate": "attn_dropout",
    "model dimension": "d_model",
    "model dimensions": "d_model",
    "model dim": "d_model",
    "hidden dimension": "d_model",
    "hidden dimensions": "d_model",
    "hidden dim": "d_model",
    "inner dimension": "d_inner",
    "inner dimensions": "d_inner",
    "inner dim": "d_inner",
    "key dimension": "d_k",
    "key dim": "d_k",
    "value dimension": "d_v",
    "value dim": "d_v",
    "position": "n_position",
    "positions": "n_position",
    "maximum position": "n_position",
    "maximum positions": "n_position",
}
