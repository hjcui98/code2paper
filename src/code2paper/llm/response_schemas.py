"""Helpers for structured LLM response contracts."""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Iterable
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ANALYSIS_NAVIGATION_PLAN_SCHEMA = "analysis_navigation_plan"
TARGETED_CODE_TRACING_SCHEMA = "targeted_code_tracing"
CODE_METHOD_ANALYSIS_SCHEMA = "code_method_analysis"
METHOD_OUTLINE_SCHEMA = "method_outline"
METHOD_PLAN_SCHEMA = "method_plan"
METHOD_DRAFT_SCHEMA = "method_draft"
PUBLICATION_METHOD_SECTION_SCHEMA = "publication_method_section_v1"
PUBLICATION_METHOD_EDITOR_SCHEMA = "publication_method_editor_v1"

T = TypeVar("T", bound=BaseModel)


class PublicationMethodSectionOutputV1(BaseModel):
    """Content-first Writer response; ids are bindings, not prose substitutes."""

    model_config = ConfigDict(extra="forbid")

    section_id: str = ""
    section_markdown: str
    used_argument_unit_ids: list[str] = Field(default_factory=list)
    used_claim_ids: list[str] = Field(default_factory=list)
    used_equation_ids: list[str] = Field(default_factory=list)
    new_research_requests: list[dict[str, Any]] = Field(default_factory=list)
    self_identified_risks: list[str] = Field(default_factory=list)


class PublicationMethodEditorOutputV1(BaseModel):
    """Editor output is a list of complete, section-scoped generated patches."""

    model_config = ConfigDict(extra="forbid")

    patches: list[dict[str, Any]] = Field(default_factory=list)


def json_schema_for(model_type: type[BaseModel]) -> dict:
    """Return a provider-friendly JSON schema for a Pydantic model."""

    return model_type.model_json_schema(mode="validation")


def parse_structured_response(text: str, model_type: type[T]) -> T:
    """Parse provider text into a Pydantic model, with a small JSON repair pass."""

    payload = _loads_json_or_extract_object(text)
    try:
        return model_type.model_validate(payload)
    except ValidationError:
        repaired = _best_effort_schema_repair(payload, model_type)
        return model_type.model_validate(repaired)


def try_parse_structured_response(text: str, model_type: type[T]) -> tuple[T | None, str]:
    try:
        return parse_structured_response(text, model_type), ""
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return None, f"schema_validation_failed:{exc.__class__.__name__}:{str(exc)[:500]}"


def _loads_json_or_extract_object(text: str) -> object:
    stripped = _strip_markdown_fence(text.strip())
    parse_attempts: list[str] = []
    parse_attempts.append(stripped)

    extracted = _extract_balanced_json_block(stripped)
    if extracted and extracted != stripped:
        parse_attempts.append(extracted)

    # Some models (e.g. Qwen3.6) add one extra opening or closing brace
    # around otherwise valid JSON.  Add conservative one-brace repairs.
    # The asymmetric ``{{...}`` form is observed in real provider output.
    for candidate in list(parse_attempts):
        repaired_braces: list[str] = []
        if candidate.startswith("{{"):
            repaired_braces.append(candidate[1:])
        if candidate.endswith("}}"):
            repaired_braces.append(candidate[:-1])
        if candidate.startswith("{{") and candidate.endswith("}}"):
            repaired_braces.append(candidate[1:-1])
        for repaired in repaired_braces:
            if repaired not in parse_attempts:
                parse_attempts.append(repaired)
            repaired_extracted = _extract_balanced_json_block(repaired)
            if (
                repaired_extracted
                and repaired_extracted not in parse_attempts
            ):
                parse_attempts.append(repaired_extracted)

    repaired_candidates: list[str] = []
    for candidate in parse_attempts:
        repaired = _best_effort_json_text_repair(candidate)
        if repaired and repaired != candidate:
            repaired_candidates.append(repaired)
        closed = _close_unambiguous_json_container_suffix(repaired)
        if closed:
            # Closing an otherwise complete container can expose a trailing
            # comma immediately before the synthesized close token.
            repaired_candidates.append(_best_effort_json_text_repair(closed))
        extracted_repaired = _extract_balanced_json_block(repaired) if repaired else ""
        if extracted_repaired and extracted_repaired != repaired:
            repaired_candidates.append(extracted_repaired)
    parse_attempts.extend(repaired_candidates)

    for candidate in _dedupe_candidates(parse_attempts):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        python_obj = _try_literal_eval(candidate)
        if python_obj is not None:
            return python_obj

    raise ValueError("no valid JSON object or array found after repair attempts")


def _strip_markdown_fence(text: str) -> str:
    # Strip only an outer response fence.  Removing every fence marker would
    # silently mutate valid JSON strings whose content contains Markdown.
    opening = re.match(r"\A```(?:json)?[ \t]*(?:\r?\n)?", text, flags=re.IGNORECASE)
    if opening is None:
        return text
    stripped = text[opening.end() :]
    stripped = re.sub(r"(?:\r?\n)?[ \t]*```\s*\Z", "", stripped)
    return stripped.strip()


def _best_effort_json_text_repair(text: str) -> str:
    repaired = text
    # normalize common smart punctuation without changing content semantics
    repaired = (
        repaired.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    # remove trailing commas before object/array close
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    # fix common missing comma between adjacent key-value pairs
    repaired = re.sub(r'([}\]"0-9])(\s*)("([^"\\]|\\.)+"\s*:)', r"\1,\2\3", repaired)
    return repaired


def _close_unambiguous_json_container_suffix(text: str) -> str:
    """Close only missing outer JSON containers after a complete value.

    This intentionally refuses strings, scalar fragments, dangling commas,
    mismatched delimiters, or output ending mid-field.  It handles the narrow
    provider drift case where valid nested objects/arrays were emitted and
    only one or more final ``]``/``}`` tokens are missing.
    """

    stripped = text.rstrip()
    if not stripped or stripped[-1] not in "}]":
        return ""
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in stripped:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if not stack:
                return ""
            opening = stack.pop()
            if (opening, ch) not in {("{", "}"), ("[", "]")}:
                return ""
    if in_string or not stack:
        return ""
    closing = "".join("}" if opening == "{" else "]" for opening in reversed(stack))
    return stripped + closing


def repair_unambiguous_known_identifier(
    value: str,
    allowed_values: Iterable[str],
) -> tuple[str | None, dict[str, Any] | None]:
    """Repair presentation-only suffix drift against a closed identifier set.

    The repair is allowed only when trimming whitespace and terminal prose
    punctuation maps to exactly one known identifier.  It never uses fuzzy
    matching, edit distance, case folding, prefix matching, or content
    deletion, so a semantic/reference error remains a validator failure.
    """

    allowed = tuple(dict.fromkeys(str(item) for item in allowed_values))
    if value in allowed:
        return value, None
    stripped = value.strip()
    normalized = stripped.rstrip(",;:，；：。.").rstrip()
    matches = [item for item in allowed if item == normalized]
    if len(matches) != 1:
        return None, None
    repaired = matches[0]
    return repaired, {
        "repair_kind": "known_identifier_terminal_punctuation",
        "before": value,
        "after": repaired,
        "semantic_change": False,
    }


def structured_response_diagnostics(
    text: str,
    *,
    excerpt_chars: int = 240,
) -> dict[str, Any]:
    """Return bounded diagnostics for a rejected structured response.

    The prefix/suffix excerpts make truncation and repetition debuggable
    without persisting an unbounded model response in the acceptance report.
    They are diagnostics only and never participate in authorization.
    """

    stripped = text.strip()
    limit = max(0, min(int(excerpt_chars), 1000))
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    unique_line_ratio = (
        round(len(set(lines)) / len(lines), 4)
        if lines
        else 0.0
    )
    return {
        "character_count": len(text),
        "nonempty": bool(stripped),
        "starts_with_json_container": stripped.startswith(("{", "[")),
        "ends_with_json_container": stripped.endswith(("}", "]")),
        "line_count": len(lines),
        "unique_line_ratio": unique_line_ratio,
        "prefix_excerpt": stripped[:limit] if limit else "",
        "suffix_excerpt": stripped[-limit:] if limit else "",
    }


def _extract_balanced_json_block(text: str) -> str:
    start_candidates = [index for index in [text.find("{"), text.find("[")] if index >= 0]
    if not start_candidates:
        return ""
    start = min(start_candidates)
    stack: list[str] = []
    in_string = False
    escape = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in "{[":
            stack.append(ch)
            continue
        if ch in "}]":
            if not stack:
                continue
            top = stack[-1]
            if (top == "{" and ch == "}") or (top == "[" and ch == "]"):
                stack.pop()
                if not stack:
                    return text[start : index + 1]
    return ""


def _try_literal_eval(text: str) -> object | None:
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError, TypeError):
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


def _dedupe_candidates(candidates: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _best_effort_schema_repair(payload: object, model_type: type[BaseModel]) -> object:
    """Conservative schema repair for common provider drift patterns.

    We only fix known-safe shape issues and avoid fabricating semantic content.
    """

    model_name = model_type.__name__
    if model_name == "AnalysisNavigationPlan" and isinstance(payload, dict):
        if "navigation_plan" in payload or "claims" in payload:
            return _repair_navigation_plan(payload)
    if model_name == "TargetedCodeTracing" and isinstance(payload, dict):
        if "claims" in payload and "author_claim_verification" not in payload:
            return _repair_targeted_code_tracing(payload)
    if model_name == "CodeMethodAnalysis" and isinstance(payload, dict):
        if "frozen_mechanisms" in payload and "candidate_mechanisms" not in payload:
            return _repair_code_method_analysis(payload)
    if model_name.startswith("Phase3") and isinstance(payload, dict):
        repaired_phase3 = _repair_phase3_output(payload, model_name=model_name)
        if repaired_phase3 is not None:
            return repaired_phase3
    if model_name == "MethodOutline" and isinstance(payload, dict):
        return _repair_method_outline(payload)
    if model_name == "TerminologyTable" and isinstance(payload, dict):
        return _repair_terminology_table(payload)
    if model_name == "DraftMarkdownOutput" and isinstance(payload, dict):
        markdown = payload.get("markdown") or payload.get("method_draft_md") or payload.get("draft_markdown") or payload.get("content") or payload.get("text")
        return {"markdown": str(markdown or "")}
    if model_name == "DraftLatexOutput" and isinstance(payload, dict):
        latex = payload.get("latex") or payload.get("method_draft_tex") or payload.get("draft_latex") or payload.get("content") or payload.get("text")
        return {"latex": str(latex or "")}
    if model_name == "TargetedRevisionOutput" and isinstance(payload, dict):
        markdown = payload.get("markdown") or payload.get("revised_markdown") or payload.get("method_draft_md") or payload.get("draft_markdown") or ""
        latex = payload.get("latex") or payload.get("revised_latex") or payload.get("method_draft_tex") or payload.get("draft_latex") or ""
        return {
            "markdown": str(markdown),
            "latex": str(latex),
            "revision_notes": _as_str_list(payload.get("revision_notes") or payload.get("notes")),
            "resolved_issue_ids": _as_str_list(payload.get("resolved_issue_ids") or payload.get("resolved_issues")),
        }
    if model_name == "DraftClaimMap" and isinstance(payload, dict):
        paragraphs = payload.get("paragraphs", [])
        if isinstance(paragraphs, list):
            cleaned_paragraphs: list[dict] = []
            for index, item in enumerate(paragraphs, start=1):
                if not isinstance(item, dict):
                    continue
                claim_ids = _as_str_list(item.get("claim_ids")) + _as_str_list(item.get("claims")) + _as_str_list(item.get("claim_id"))
                mechanism_ids = _as_str_list(item.get("mechanism_ids")) + _as_str_list(item.get("mechanisms")) + _as_str_list(item.get("mechanism_id"))
                evidence_ids = (
                    _as_str_list(item.get("evidence_span_ids"))
                    + _as_str_list(item.get("evidence_ids"))
                    + _as_str_list(item.get("evidence"))
                )
                cleaned_paragraphs.append(
                    {
                        "paragraph_id": str(item.get("paragraph_id") or f"P{index}"),
                        "claim_ids": _dedupe_str(claim_ids),
                        "mechanism_ids": _dedupe_str(mechanism_ids),
                        "evidence_span_ids": _dedupe_str(evidence_ids),
                    }
                )
            return {"paragraphs": cleaned_paragraphs}
    if model_name == "SelfCriticReport" and isinstance(payload, dict):
        issues = payload.get("issues", [])
        if isinstance(issues, list):
            cleaned_issues: list[dict] = []
            for index, item in enumerate(issues, start=1):
                if not isinstance(item, dict):
                    continue
                severity = str(item.get("severity") or "medium").lower()
                if severity not in {"low", "medium", "high"}:
                    severity = "medium"
                cleaned_issues.append(
                    {
                        "issue_id": str(item.get("issue_id") or f"SC{index}"),
                        "severity": severity,
                        "category": str(item.get("category") or item.get("issue_type") or "quality_issue"),
                        "message": str(item.get("message") or item.get("issue_description") or "Self critic flagged an issue."),
                        "paragraph_id": str(item.get("paragraph_id") or item.get("paragraph") or ""),
                    }
                )
            return {"issues": cleaned_issues}
    return payload


def _repair_method_outline(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections") or payload.get("paragraphs") or payload.get("outline")
    if not isinstance(sections, list):
        sections = []
    cleaned_sections: list[dict] = []
    for index, item in enumerate(sections, start=1):
        if not isinstance(item, dict):
            continue
        purpose = item.get("purpose") or item.get("content") or item.get("summary") or item.get("description")
        if not isinstance(purpose, str) or not purpose.strip():
            title = str(item.get("title") or item.get("heading") or "").strip()
            purpose = f"Describe {title}." if title else "Describe an evidence-backed method segment."
        cleaned_sections.append(
            {
                "paragraph_id": str(item.get("paragraph_id") or item.get("id") or f"P{index}"),
                "purpose": str(purpose),
                "stage_ids": _as_str_list(item.get("stage_ids") or item.get("stages") or item.get("stage_id")),
                "mechanism_ids": _as_str_list(item.get("mechanism_ids") or item.get("mechanisms") or item.get("mechanism_id")),
                "claim_ids": _as_str_list(item.get("claim_ids") or item.get("claims") or item.get("claim_id")),
                "evidence_span_ids": _dedupe_str(
                    _as_str_list(item.get("evidence_span_ids"))
                    + _as_str_list(item.get("evidence_ids"))
                    + _as_str_list(item.get("evidence"))
                ),
            }
        )
    return {
        "sections": cleaned_sections,
        "author_logic_order": _as_str_list(payload.get("author_logic_order") or payload.get("logic_order")),
    }


def _repair_terminology_table(payload: dict[str, Any]) -> dict[str, Any]:
    terms = payload.get("terms") or payload.get("terminology") or payload.get("terminology_table")
    if isinstance(terms, dict):
        terms = terms.get("terms")
    if not isinstance(terms, list):
        terms = []
    cleaned_terms: list[dict] = []
    for index, item in enumerate(terms, start=1):
        if not isinstance(item, dict):
            continue
        canonical = str(
            item.get("canonical")
            or item.get("term")
            or item.get("name")
            or item.get("label")
            or f"Term {index}"
        ).strip()
        if not canonical:
            canonical = f"Term {index}"
        term_type = str(item.get("term_type") or item.get("type") or item.get("category") or "concept").strip()
        if not term_type:
            term_type = "concept"
        cleaned_terms.append(
            {
                "term_id": str(item.get("term_id") or item.get("id") or f"TERM-{index}"),
                "canonical": canonical,
                "term_type": term_type,
                "allowed_synonyms": _dedupe_str(
                    _as_str_list(item.get("allowed_synonyms"))
                    + _as_str_list(item.get("synonyms"))
                    + _as_str_list(item.get("aliases"))
                ),
                "forbidden_replacements": _dedupe_str(
                    _as_str_list(item.get("forbidden_replacements"))
                    + _as_str_list(item.get("forbidden_synonyms"))
                    + _as_str_list(item.get("forbidden_terms"))
                ),
                "source_ids": _dedupe_str(
                    _as_str_list(item.get("source_ids"))
                    + _as_str_list(item.get("sources"))
                    + _as_str_list(item.get("stage_ids"))
                    + _as_str_list(item.get("mechanism_ids"))
                    + _as_str_list(item.get("claim_ids"))
                ),
                "evidence_span_ids": _dedupe_str(
                    _as_str_list(item.get("evidence_span_ids"))
                    + _as_str_list(item.get("evidence_ids"))
                    + _as_str_list(item.get("evidence"))
                ),
            }
        )
    return {"terms": cleaned_terms}


def _repair_phase3_output(payload: dict[str, Any], *, model_name: str) -> dict[str, Any] | None:
    expected_fields_by_model: dict[str, list[str]] = {
        "Phase3StageBuilderOutput": ["stages"],
        "Phase3MechanismBuilderOutput": ["frozen_mechanisms"],
        "Phase3DistinguishingMechanismOutput": ["distinguishing_mechanisms", "frozen_mechanisms"],
        "Phase3AuthorLogicOutput": ["author_logic_mapping", "unsupported_author_parts"],
        "Phase3ClaimContractOutput": ["claim_contracts"],
        "Phase3NegativeScopeOutput": ["negative_scope"],
    }
    expected_fields = expected_fields_by_model.get(model_name, [])
    if not expected_fields:
        return None
    if model_name == "Phase3StageBuilderOutput" and isinstance(payload.get("stages"), list):
        return {"stages": _repair_phase3_stages(payload.get("stages"))}
    if model_name == "Phase3MechanismBuilderOutput" and isinstance(payload.get("frozen_mechanisms"), list):
        return {"frozen_mechanisms": _repair_phase3_frozen_mechanisms(payload.get("frozen_mechanisms"))}
    if model_name == "Phase3DistinguishingMechanismOutput" and isinstance(payload.get("distinguishing_mechanisms"), list):
        return {
            "distinguishing_mechanisms": _as_str_list(payload.get("distinguishing_mechanisms")),
            "frozen_mechanisms": _repair_phase3_frozen_mechanisms(payload.get("frozen_mechanisms")),
        }
    if all(field in payload for field in expected_fields):
        return {
            field: _repair_phase3_field(model_name=model_name, field=field, value=payload.get(field))
            for field in expected_fields
        }

    wrappers: list[object] = [
        payload.get("method_evidence"),
        payload.get("data"),
        payload.get("result"),
        payload.get("output"),
    ]
    for wrapped in wrappers:
        if not isinstance(wrapped, (dict, list)):
            continue
        if len(expected_fields) == 1:
            field = expected_fields[0]
            if isinstance(wrapped, dict) and field in wrapped:
                return {
                    field: _repair_phase3_field(model_name=model_name, field=field, value=wrapped.get(field))
                }
            if isinstance(wrapped, list):
                return {
                    field: _repair_phase3_field(model_name=model_name, field=field, value=wrapped)
                }
        if isinstance(wrapped, dict):
            repaired = {
                field: _repair_phase3_field(model_name=model_name, field=field, value=wrapped.get(field))
                for field in expected_fields
                if field in wrapped
            }
            if repaired:
                for field in expected_fields:
                    repaired.setdefault(field, [] if field.endswith("s") else {})
                return repaired
    return None


def _repair_phase3_field(*, model_name: str, field: str, value: object) -> object:
    if model_name == "Phase3StageBuilderOutput" and field == "stages":
        return _repair_phase3_stages(value)
    if field == "frozen_mechanisms" and model_name in {
        "Phase3MechanismBuilderOutput",
        "Phase3DistinguishingMechanismOutput",
    }:
        return _repair_phase3_frozen_mechanisms(value)
    if model_name == "Phase3DistinguishingMechanismOutput" and field == "distinguishing_mechanisms":
        return _as_str_list(value)
    return value


def _repair_phase3_stages(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for stage_index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        stage_id = str(item.get("stage_id") or item.get("id") or f"S{stage_index}").strip()
        if not stage_id.startswith("S"):
            stage_id = f"S{stage_index}"
        name = str(item.get("name") or item.get("title") or f"Stage {stage_index}").strip() or f"Stage {stage_index}"
        purpose = str(item.get("purpose") or item.get("description") or f"Evidence-backed stage: {name}.").strip()
        if not purpose:
            purpose = f"Evidence-backed stage: {name}."
        legacy_mechanism_ids = _as_str_list(item.get("mechanism_ids"))
        legacy_evidence_ids = _as_str_list(item.get("evidence_span_ids")) + _as_str_list(item.get("evidence_ids"))
        cleaned.append(
            {
                "stage_id": stage_id,
                "name": name,
                "purpose": purpose,
                "inputs": _as_str_list(item.get("inputs") or item.get("input")),
                "outputs": _as_str_list(item.get("outputs") or item.get("output")),
                "modules": _repair_phase3_modules(item.get("modules")),
                "mechanisms": _repair_phase3_mechanisms(
                    item.get("mechanisms"),
                    stage_index=stage_index,
                    stage_name=name,
                    legacy_mechanism_ids=legacy_mechanism_ids,
                    legacy_evidence_ids=legacy_evidence_ids,
                ),
            }
        )
    return cleaned


def _repair_phase3_modules(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip() or "unknown.py"
        category_raw = str(item.get("category") or item.get("module_class") or "method-core").strip().lower().replace("_", "-")
        if category_raw not in {"method-core", "experiment-support", "infra-utility"}:
            category_raw = "method-core"
        cleaned.append(
            {
                "path": path,
                "symbols": _as_str_list(item.get("symbols")),
                "role": str(item.get("role") or item.get("paper_role") or "implementation module").strip()
                or "implementation module",
                "category": category_raw,
                "is_novel": bool(item.get("is_novel", False)),
            }
        )
    return cleaned


def _repair_phase3_mechanisms(
    value: object,
    *,
    stage_index: int,
    stage_name: str,
    legacy_mechanism_ids: list[str],
    legacy_evidence_ids: list[str],
) -> list[dict[str, Any]]:
    def _normalized_mechanism_id(raw: str, index: int) -> str:
        text = str(raw or "").strip()
        if text.startswith("MECH"):
            return text
        return f"MECH{stage_index:02d}{index:02d}"

    cleaned: list[dict[str, Any]] = []
    if isinstance(value, list):
        for mechanism_index, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                continue
            evidence_ids = _as_str_list(item.get("evidence_ids")) + _as_str_list(item.get("evidence_span_ids"))
            support_status = _normalize_phase3_support_status(
                item.get("support_status") or item.get("status"),
                has_evidence=bool(evidence_ids),
            )
            cleaned.append(
                {
                    "mechanism_id": _normalized_mechanism_id(item.get("mechanism_id") or item.get("id"), mechanism_index),
                    "description": str(item.get("description") or item.get("summary") or item.get("name") or f"Mechanism {mechanism_index} for {stage_name}.").strip()
                    or f"Mechanism {mechanism_index} for {stage_name}.",
                    "support_status": support_status,
                    "evidence_ids": evidence_ids,
                    "confidence": _normalize_phase3_confidence(item.get("confidence")),
                    "submechanisms": [],
                }
            )
    if cleaned:
        return cleaned

    fallback_ids = legacy_mechanism_ids or ([""] if legacy_evidence_ids else [])
    for mechanism_index, mechanism_id in enumerate(fallback_ids, start=1):
        cleaned.append(
            {
                "mechanism_id": _normalized_mechanism_id(mechanism_id, mechanism_index),
                "description": f"Recovered mechanism {mechanism_index} for {stage_name}.",
                "support_status": "supported" if legacy_evidence_ids else "partial",
                "evidence_ids": legacy_evidence_ids,
                "confidence": "medium",
                "submechanisms": [],
            }
        )
    return cleaned


def _repair_phase3_frozen_mechanisms(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for mechanism_index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        mechanism_id = str(item.get("mechanism_id") or item.get("id") or f"MECH{mechanism_index:03d}").strip()
        if not mechanism_id.startswith("MECH"):
            mechanism_id = f"MECH{mechanism_index:03d}"
        evidence_span_ids = _dedupe_str(
            _as_str_list(item.get("evidence_span_ids")) + _as_str_list(item.get("evidence_ids"))
        )
        mechanism_name = (
            str(item.get("mechanism_name") or item.get("name") or item.get("title") or f"Mechanism {mechanism_index}").strip()
            or f"Mechanism {mechanism_index}"
        )
        mechanism_description = (
            str(item.get("mechanism_description") or item.get("description") or item.get("summary") or mechanism_name).strip()
            or mechanism_name
        )
        anchor = item.get("implementation_anchor")
        if not isinstance(anchor, dict):
            anchor = {}
        anchor_path = str(anchor.get("path") or item.get("path") or "").strip()
        anchor_symbols = _dedupe_str(
            _as_str_list(anchor.get("symbols"))
            + _as_str_list(anchor.get("symbol"))
            + _as_str_list(item.get("symbols"))
            + _as_str_list(item.get("symbol"))
        )
        cleaned.append(
            {
                "mechanism_id": mechanism_id,
                "mechanism_name": mechanism_name,
                "mechanism_description": mechanism_description,
                "parent_stage_id": str(item.get("parent_stage_id") or item.get("stage_id") or "").strip(),
                "inputs": _as_str_list(item.get("inputs")),
                "outputs": _as_str_list(item.get("outputs")),
                "implementation_anchor": {"path": anchor_path, "symbols": anchor_symbols},
                "distinguishing_level": _normalize_phase3_distinguishing_level(
                    item.get("distinguishing_level") or item.get("level")
                ),
                "author_claim_relation": _normalize_phase3_conflict_status(
                    item.get("author_claim_relation") or item.get("support_status") or item.get("status"),
                    has_evidence=bool(evidence_span_ids),
                ),
                "evidence_span_ids": evidence_span_ids,
            }
        )
    return cleaned


def _normalize_phase3_support_status(value: object, *, has_evidence: bool) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"supported", "partial", "unsupported"}:
        return lowered
    if lowered in {"partially_supported", "partially-supported"}:
        return "partial"
    return "supported" if has_evidence else "partial"


def _normalize_phase3_confidence(value: object) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"low", "medium", "high"}:
        return lowered
    return "medium"


def _normalize_phase3_distinguishing_level(value: object) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"main", "primary", "key"}:
        return "main"
    if lowered in {"secondary", "auxiliary", "minor"}:
        return "secondary"
    return "none"


def _normalize_phase3_conflict_status(value: object, *, has_evidence: bool) -> str:
    lowered = str(value or "").strip().lower()
    if lowered == "supported":
        return "supported"
    if lowered in {"partially_supported", "partially-supported", "partial"}:
        return "partially_supported"
    if lowered == "unsupported":
        return "unsupported"
    if lowered in {
        "ambiguous",
        "ambiguous_due_to_missing_context",
        "not_in_bounded_context",
        "missing_context",
        "insufficient_context",
    }:
        return "ambiguous_due_to_missing_context"
    return "supported" if has_evidence else "ambiguous_due_to_missing_context"


def _repair_navigation_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan = payload.get("navigation_plan", {})
    targets = plan.get("targets", []) if isinstance(plan, dict) else []
    claims = payload.get("claims", [])
    questions: list[dict[str, Any]] = []
    suspected: list[str] = []
    for index, target in enumerate(targets, start=1):
        if not isinstance(target, dict):
            continue
        path = str(target.get("path") or "").strip()
        symbol = str(target.get("symbol") or "").strip()
        target_ref = f"{path}::{symbol}" if path and symbol else path or symbol
        if target_ref:
            suspected.append(target_ref)
        question = str(target.get("question") or "").strip()
        if not question:
            question = f"Which source/config/bash spans verify {target_ref or 'this target'}?"
        questions.append(
            {
                "question_id": f"Q{index}",
                "question": question,
                "driven_by": ["comment"],
                "seed_span_ids": _as_str_list(target.get("evidence_spans")) + _as_str_list(target.get("evidence_ids")),
                "target_paths_or_symbols": [target_ref] if target_ref else [],
                "priority": _normalize_priority(target.get("priority")),
            }
        )
    claims_to_verify: list[str] = []
    for item in claims if isinstance(claims, list) else []:
        if isinstance(item, dict):
            text = str(item.get("claim") or item.get("text") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            claims_to_verify.append(text)
    return {
        "author_logic_summary": str(payload.get("author_logic_summary") or payload.get("summary") or ""),
        "navigation_questions": questions,
        "suspected_core_symbols": _dedupe_str(suspected + _as_str_list(payload.get("suspected_core_symbols"))),
        "suspected_config_behavior_links": _as_str_list(payload.get("suspected_config_behavior_links")),
        "claims_to_verify": _dedupe_str(claims_to_verify + _as_str_list(payload.get("claims_to_verify"))),
        "comment_triage": _repair_comment_triage(payload.get("comment_triage")),
    }


def _repair_targeted_code_tracing(payload: dict[str, Any]) -> dict[str, Any]:
    claims = payload.get("claims", [])
    claim_findings: list[dict[str, Any]] = []
    for index, item in enumerate(claims if isinstance(claims, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        summary = str(item.get("claim") or item.get("summary") or "").strip()
        if not summary:
            continue
        claim_findings.append(
            {
                "finding_id": f"TRACE-claim-{index:03d}",
                "question_id": "",
                "trace_type": "author_claim_verification",
                "summary": summary,
                "hard_span_ids": _as_str_list(item.get("evidence_ids")) + _as_str_list(item.get("evidence_spans")),
                "soft_span_ids": [],
                "status": "partially_supported",
            }
        )
    return {
        "entrypoint_pipeline_tracing": [],
        "core_mechanism_tracing": [],
        "config_to_behavior_tracing": [],
        "author_claim_verification": claim_findings,
    }


def _repair_code_method_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    frozen = payload.get("frozen_mechanisms", [])
    candidate_mechanisms: list[dict[str, Any]] = []
    method_modules: list[dict[str, Any]] = []
    module_seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(frozen if isinstance(frozen, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        evidence_ids = _as_str_list(item.get("evidence_span_ids"))
        if not evidence_ids:
            continue
        mechanism_id = str(item.get("mechanism_id") or f"MECH-{index:03d}")
        name = str(item.get("mechanism_name") or item.get("name") or f"Mechanism {index}")
        description = str(item.get("mechanism_description") or item.get("description") or f"{name} mechanism.")
        candidate_mechanisms.append(
            {
                "mechanism_id": mechanism_id,
                "name": name,
                "description": description,
                "inputs": _as_str_list(item.get("inputs")),
                "outputs": _as_str_list(item.get("outputs")),
                "supporting_span_ids": evidence_ids,
                "unsupported_parts": [],
            }
        )
        anchor = item.get("implementation_anchor", {})
        if not isinstance(anchor, dict):
            anchor = {}
        path = str(anchor.get("path") or "").strip()
        symbols = _as_str_list(anchor.get("symbols"))
        role = name or "method mechanism"
        key = (path, ",".join(symbols), role)
        if path and key not in module_seen:
            module_seen.add(key)
            method_modules.append(
                {
                    "path": path,
                    "symbols": symbols,
                    "module_class": "method-core",
                    "paper_role": role,
                    "evidence_span_ids": evidence_ids,
                    "llm_confidence": "medium",
                }
            )
    mapping = payload.get("author_logic_mapping", {})
    if not isinstance(mapping, dict):
        mapping = {}
    return {
        "navigation_questions": [],
        "execution_flows": [],
        "method_modules": method_modules,
        "candidate_mechanisms": candidate_mechanisms,
        "comment_driven_insights": [],
        "author_alignment": {
            "author_proposed_flow": _as_str_list(mapping.get("author_proposed_flow")),
            "author_supported_flow": _as_str_list(mapping.get("author_supported_flow")),
            "author_unsupported_parts": _as_str_list(mapping.get("author_unsupported_parts")),
        },
        "candidate_distinguishing_mechanisms": [],
        "evidence_spans": [],
        "gaps": [],
    }


def _repair_comment_triage(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {
            "high_priority_comment_ids": [],
            "medium_priority_comment_ids": [],
            "low_priority_comment_ids": [],
            "excluded_comment_ids": [],
        }
    return {
        "high_priority_comment_ids": _as_str_list(value.get("high_priority_comment_ids")),
        "medium_priority_comment_ids": _as_str_list(value.get("medium_priority_comment_ids")),
        "low_priority_comment_ids": _as_str_list(value.get("low_priority_comment_ids")),
        "excluded_comment_ids": _as_str_list(value.get("excluded_comment_ids")),
    }


def _normalize_priority(value: object) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"high", "medium", "low"}:
        return lowered
    return "medium"


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    return []


def _dedupe_str(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
