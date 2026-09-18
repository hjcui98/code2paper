"""WP4：Writer 页级输出工作量估量与页契约联合评估（方案 §8.2）。

分页决策必须同时看**输入闭包**与**输出工作量**：事故页要求一次写出 16 个段落、
7 个 detail 与 witness，输入预算却显示"装得下"。本模块提供纯函数形式的估量层，
供分页器（`unified_context_compiler`）在候选页评估时调用；它不修改任何产物、
不发请求、不做 I/O。

刻意保留的不确定性：
* ``DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE`` 是**待标定候选**，不是普遍正确值；
* 经验正文系数与安全余量可经 ``calibrated_profile`` 注入，未标定时
  ``confidence="uncalibrated"`` 并给出 ``unknown_reasons``；
* Binder 负责的 atom 不计入 Writer 输出负担。
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

RESPONSE_PROTOCOL_JSON_PARAGRAPH_OBJECTS = "json_paragraph_objects"
WORKLOAD_BASIS_VERSION = "writer-output-workload-v1"

#: 待标定候选（方案 §8.2 明确"初始 4–6 仅可作为待标定候选"）。
DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE = 6
DEFAULT_JSON_STRUCTURE_TOKENS = 48
DEFAULT_PER_PARAGRAPH_JSON_TOKENS = 24
DEFAULT_SAFETY_RESERVE_TOKENS = 512
DEFAULT_MIN_PARAGRAPH_PROSE_TOKENS = 48
_CHARS_PER_TOKEN = 4

BINDER_OWNED_TARGET_KINDS = {"atom"}


def _get(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    return tuple(
        text for item in value if (text := str(item or "").strip())
    )


def narrative_ordinal(paragraph_id: str) -> tuple[Any, ...]:
    """段落顺序使用叙事序号，而不是字典序（P2 必须排在 P10 之前）。"""

    parts = re.split(r"(\d+)", str(paragraph_id or ""))
    return tuple(int(part) if part.isdigit() else part for part in parts if part != "")


def _default_text_tokens(text: str) -> int:
    stripped = str(text or "").strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


class WriterOutputWorkloadV1(BaseModel):
    """一次 Writer 页调用的输出工作量估量（不是数学保证）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    basis_version: str = WORKLOAD_BASIS_VERSION
    response_protocol: str = RESPONSE_PROTOCOL_JSON_PARAGRAPH_OBJECTS

    semantic_paragraph_count: int = 0
    required_detail_occurrences: int = 0
    writer_owned_witness_count: int = 0
    binder_owned_witness_count: int = 0
    formula_consumption_count: int = 0

    json_overhead_tokens: int = 0
    target_prose_tokens: int = 0
    detail_binding_tokens: int = 0
    formula_reference_tokens: int = 0
    safety_reserve_tokens: int = 0
    estimated_output_tokens: int = 0

    confidence: Literal["calibrated", "uncalibrated", "unknown"] = "uncalibrated"
    unknown_reasons: tuple[str, ...] = ()

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _targets(paragraph: Any) -> tuple[Any, ...]:
    contract = _get(paragraph, "witness_contract") or {}
    targets = _get(contract, "targets") or ()
    if isinstance(targets, (str, bytes)):
        return ()
    return tuple(targets)


def estimate_writer_output_workload(
    paragraph_contracts: Sequence[Any],
    *,
    response_protocol: str = RESPONSE_PROTOCOL_JSON_PARAGRAPH_OBJECTS,
    calibrated_profile: Mapping[str, Any] | None = None,
    token_estimator: Callable[[str], int] | None = None,
) -> WriterOutputWorkloadV1:
    """估量一页的输出工作量；Binder-owned atom 不计入 Writer 负担。"""

    estimator = token_estimator or _default_text_tokens
    profile = dict(calibrated_profile or {})
    per_paragraph_json = int(
        profile.get("per_paragraph_json_tokens", DEFAULT_PER_PARAGRAPH_JSON_TOKENS)
    )
    structure_tokens = int(
        profile.get("json_structure_tokens", DEFAULT_JSON_STRUCTURE_TOKENS)
    )
    safety_reserve = int(
        profile.get("safety_reserve_tokens", DEFAULT_SAFETY_RESERVE_TOKENS)
    )
    min_paragraph_tokens = int(
        profile.get("min_paragraph_prose_tokens", DEFAULT_MIN_PARAGRAPH_PROSE_TOKENS)
    )

    paragraphs = tuple(paragraph_contracts or ())
    detail_occurrences = 0
    writer_witnesses = 0
    binder_witnesses = 0
    formula_consumptions = 0
    prose_tokens = 0
    detail_tokens = 0

    for paragraph in paragraphs:
        required_details = _ids(_get(paragraph, "required_detail_ids"))
        detail_occurrences += len(required_details)

        targets = _targets(paragraph)
        for target in targets:
            kind = str(_get(target, "target_kind") or "").strip()
            required = bool(_get(target, "required", True))
            if kind in BINDER_OWNED_TARGET_KINDS:
                binder_witnesses += 1
                continue
            if required:
                writer_witnesses += 1

        formula_consumptions += len(_ids(_get(paragraph, "formula_package_ids")))
        formula_consumptions += len(_ids(_get(paragraph, "formula_obligation_ids")))

        text_parts = [str(_get(paragraph, "reader_goal") or "")]
        for surface in _get(paragraph, "author_intent_surfaces") or ():
            text_parts.append(str(_get(surface, "author_statement") or ""))
        paragraph_tokens = sum(estimator(part) for part in text_parts)
        prose_tokens += max(min_paragraph_tokens, paragraph_tokens)
        detail_tokens += len(required_details) * int(
            profile.get("detail_binding_tokens", 12)
        )

    formula_reference_tokens = formula_consumptions * int(
        profile.get("formula_reference_tokens", 16)
    )
    json_overhead = structure_tokens + per_paragraph_json * len(paragraphs)
    estimated = (
        json_overhead
        + prose_tokens
        + detail_tokens
        + formula_reference_tokens
        + safety_reserve
    )

    unknown: list[str] = []
    confidence: Literal["calibrated", "uncalibrated", "unknown"] = "uncalibrated"
    if not profile:
        unknown.append("no_calibrated_profile")
    else:
        confidence = "calibrated"
    if token_estimator is None:
        unknown.append("token_estimator_is_character_proxy")

    return WriterOutputWorkloadV1(
        response_protocol=str(response_protocol or RESPONSE_PROTOCOL_JSON_PARAGRAPH_OBJECTS),
        semantic_paragraph_count=len(paragraphs),
        required_detail_occurrences=detail_occurrences,
        writer_owned_witness_count=writer_witnesses,
        binder_owned_witness_count=binder_witnesses,
        formula_consumption_count=formula_consumptions,
        json_overhead_tokens=json_overhead,
        target_prose_tokens=prose_tokens,
        detail_binding_tokens=detail_tokens,
        formula_reference_tokens=formula_reference_tokens,
        safety_reserve_tokens=safety_reserve,
        estimated_output_tokens=estimated,
        confidence=confidence,
        unknown_reasons=tuple(unknown),
    )


class PageContractEvaluationV1(BaseModel):
    """候选页是否同时满足输入预算与输出工作量（方案 §8.2/§8.3）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fits: bool
    reasons: tuple[str, ...] = ()
    input_tokens: int = 0
    max_page_input_tokens: int = 0
    estimated_output_tokens: int = 0
    max_output_tokens: int = 0
    max_semantic_paragraphs_per_page: int = 0
    workload: WriterOutputWorkloadV1 | None = None

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def evaluate_page_contract(
    paragraph_contracts: Sequence[Any],
    *,
    input_tokens: int,
    max_page_input_tokens: int,
    max_output_tokens: int | None = None,
    output_reserve_tokens: int = 0,
    response_protocol: str = RESPONSE_PROTOCOL_JSON_PARAGRAPH_OBJECTS,
    calibrated_profile: Mapping[str, Any] | None = None,
    token_estimator: Callable[[str], int] | None = None,
    max_semantic_paragraphs_per_page: int | None = None,
    require_output_budget: bool = True,
) -> PageContractEvaluationV1:
    """联合评估一个候选页；未知输出预算在默认配置下 fail-closed。"""

    workload = estimate_writer_output_workload(
        paragraph_contracts,
        response_protocol=response_protocol,
        calibrated_profile=calibrated_profile,
        token_estimator=token_estimator,
    )
    limit = int(
        max_semantic_paragraphs_per_page
        if max_semantic_paragraphs_per_page is not None
        else DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE
    )
    reasons: list[str] = []
    if int(input_tokens) > int(max_page_input_tokens):
        reasons.append("input_tokens_exceed_page_budget")
    if limit > 0 and workload.semantic_paragraph_count > limit:
        reasons.append("semantic_paragraph_count_exceeds_candidate_limit")
    if max_output_tokens is None:
        if require_output_budget:
            reasons.append("output_budget_unknown")
    else:
        available = int(max_output_tokens) - int(output_reserve_tokens)
        if workload.estimated_output_tokens > available:
            reasons.append("estimated_output_exceeds_available_output_budget")
    return PageContractEvaluationV1(
        fits=not reasons,
        reasons=tuple(reasons),
        input_tokens=int(input_tokens),
        max_page_input_tokens=int(max_page_input_tokens),
        estimated_output_tokens=workload.estimated_output_tokens,
        max_output_tokens=int(max_output_tokens or 0),
        max_semantic_paragraphs_per_page=limit,
        workload=workload,
    )


__all__ = [
    "BINDER_OWNED_TARGET_KINDS",
    "DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE",
    "PageContractEvaluationV1",
    "RESPONSE_PROTOCOL_JSON_PARAGRAPH_OBJECTS",
    "WORKLOAD_BASIS_VERSION",
    "WriterOutputWorkloadV1",
    "estimate_writer_output_workload",
    "evaluate_page_contract",
    "narrative_ordinal",
]
