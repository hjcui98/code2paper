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

#: 事故归档（`artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn`，24 个 Writer 请求）
#: 实测出的三条边界——它们是**证据**，不是策略：
#:   * 首次调用即 accepted 的请求最大段落数 = 2；
#:   * 首次 rejected、经一次 content repair 后 accepted 的最大段落数 = 6；
#:   * 首次 + repair 都 rejected（内容预算耗尽）的段落数 = 16。
#: 也就是说：段落数越多，"首次即接受"的概率越低；6 已经处在依赖 repair 的边界，
#: 16 则被实测证明一次事务写不完。默认上限取 6（repair 可恢复边界）；若要追求首次
#: 即接受，应显式下调到 2，代价是更多页与更多调用。两条边界都必须由回归钉住。
FIRST_ATTEMPT_ACCEPTED_MAX_PARAGRAPHS = 2
REPAIR_RECOVERABLE_MAX_PARAGRAPHS = 6
OBSERVED_UNRECOVERABLE_PARAGRAPHS = 16
CALIBRATION_SOURCE = "artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn"

#: 默认上限 = 实测的"repair 可恢复边界"。方案 §8.2 明确它不是普遍正确值。
DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE = REPAIR_RECOVERABLE_MAX_PARAGRAPHS
DEFAULT_JSON_STRUCTURE_TOKENS = 48
DEFAULT_PER_PARAGRAPH_JSON_TOKENS = 24
DEFAULT_SAFETY_RESERVE_TOKENS = 512
DEFAULT_MIN_PARAGRAPH_PROSE_TOKENS = 48
#: 一个 Writer-owned witness 的对象骨架成本（键名/括号/引号等）。
DEFAULT_PER_WITNESS_OBJECT_TOKENS = 24
#: 没有给出精确 span 文本时的保守 span 长度（字符）。
DEFAULT_WITNESS_SPAN_CHARS = 48
#: 一个 formula placeholder 的输出成本。
DEFAULT_PER_FORMULA_PLACEHOLDER_TOKENS = 16
#: 审计 §C.3：calibrated profile 必须自证来源与适用范围；仅"非空字典"不算标定。
CALIBRATION_REQUIRED_KEYS: tuple[str, ...] = (
    "model_identity",
    "tokenizer_identity",
    "schema_or_prompt_identity",
    "sample_scope",
    "method",
)
#: span 文本可能出现的字段名（按顺序取第一个非空）。
_WITNESS_SPAN_FIELDS: tuple[str, ...] = (
    "exact_span",
    "span_text",
    "expected_span",
    "witness_text",
    "target_text",
)
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
    #: 审计 §C.3：Writer-owned witness 必须按 occurrence 与预期 span 长度计入输出负担
    #: （旧实现只统计数量、从不计入总量，于是"增加合法 witness"估量不变）。
    writer_witness_tokens: int = 0
    formula_placeholder_count: int = 0
    formula_placeholder_tokens: int = 0
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
    formula_references: set[str] = set()
    formula_placeholders = 0
    prose_tokens = 0
    detail_tokens = 0
    witness_tokens = 0

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
            if not required:
                continue
            writer_witnesses += 1
            # occurrence + 预期 span 长度：span 文本可用时按真实长度估量，
            # 否则用保守默认长度（不允许"witness 增多而估量不变"）。
            span_text = ""
            for field in _WITNESS_SPAN_FIELDS:
                candidate = str(_get(target, field) or "").strip()
                if candidate:
                    span_text = candidate
                    break
            span_tokens = (
                estimator(span_text)
                if span_text
                else max(1, DEFAULT_WITNESS_SPAN_CHARS // _CHARS_PER_TOKEN)
            )
            witness_tokens += int(
                profile.get("per_witness_object_tokens", DEFAULT_PER_WITNESS_OBJECT_TOKENS)
            ) + span_tokens

        # §C.3：同一个输出引用不得因为"义务"与"package"都列了一次而被双计。
        paragraph_formula_refs = set(_ids(_get(paragraph, "formula_package_ids"))) | set(
            _ids(_get(paragraph, "formula_obligation_ids"))
        )
        formula_references |= paragraph_formula_refs
        formula_consumptions += len(paragraph_formula_refs)
        formula_placeholders += len(
            _ids(_get(paragraph, "formula_placeholder_ids"))
        )

        text_parts = [str(_get(paragraph, "reader_goal") or "")]
        for surface in _get(paragraph, "author_intent_surfaces") or ():
            text_parts.append(str(_get(surface, "author_statement") or ""))
        paragraph_tokens = sum(estimator(part) for part in text_parts)
        prose_tokens += max(min_paragraph_tokens, paragraph_tokens)
        detail_tokens += len(required_details) * int(
            profile.get("detail_binding_tokens", 12)
        )

    formula_reference_tokens = len(formula_references) * int(
        profile.get("formula_reference_tokens", 16)
    )
    formula_placeholder_tokens = formula_placeholders * int(
        profile.get("formula_placeholder_tokens", DEFAULT_PER_FORMULA_PLACEHOLDER_TOKENS)
    )
    json_overhead = structure_tokens + per_paragraph_json * len(paragraphs)
    estimated = (
        json_overhead
        + prose_tokens
        + detail_tokens
        + formula_reference_tokens
        + formula_placeholder_tokens
        + witness_tokens
        + safety_reserve
    )

    unknown: list[str] = []
    confidence: Literal["calibrated", "uncalibrated", "unknown"] = "uncalibrated"
    if not profile:
        unknown.append("no_calibrated_profile")
    else:
        # §C.3：仅"非空字典"不能升级 confidence——必须自证模型/tokenizer/schema 或
        # prompt 身份、样本范围与估量方法。
        missing = [
            key for key in CALIBRATION_REQUIRED_KEYS if not str(profile.get(key) or "").strip()
        ]
        if missing:
            unknown.append("calibration_profile_incomplete:" + ",".join(missing))
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
        writer_witness_tokens=witness_tokens,
        formula_placeholder_count=formula_placeholders,
        formula_placeholder_tokens=formula_placeholder_tokens,
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
    "CALIBRATION_SOURCE",
    "DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE",
    "FIRST_ATTEMPT_ACCEPTED_MAX_PARAGRAPHS",
    "OBSERVED_UNRECOVERABLE_PARAGRAPHS",
    "REPAIR_RECOVERABLE_MAX_PARAGRAPHS",
    "PageContractEvaluationV1",
    "RESPONSE_PROTOCOL_JSON_PARAGRAPH_OBJECTS",
    "WORKLOAD_BASIS_VERSION",
    "WriterOutputWorkloadV1",
    "estimate_writer_output_workload",
    "evaluate_page_contract",
    "narrative_ordinal",
]
