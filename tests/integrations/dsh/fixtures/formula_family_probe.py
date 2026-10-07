"""K04-GAP-2 探针：**非空**公式义务/包家族的单变量顺序对照（真实编译器与页请求）。

只调用生产入口：
  * 页与请求：`extend_writer_worksets_from_narrative_plan` → `_writer_section_inputs_v2`
    → `build_publication_writer_request`；
  * 判定：`compare_actual_request_to_page_contract`（公共发送前复核）。

三层事实分别报告：
  ① 页/请求的 Narrative 段落序与闭包关联（package → source detail）；
  ② 实际冻结/重算身份（page_id / technical_bytes_digest）；
  ③ scope（按排序集合比较）与整体 binding contract 摘要的复核结果。

`page_split_probe` 的默认输入不受影响：这里显式传入 `package_ids` / `order`。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from code2paper.agentic.page_contract_recheck import (
    compare_actual_request_to_page_contract,
    page_contract_snapshot_from_payload,
)
from code2paper.agentic.publication_method_writer import _writer_section_inputs_v2
from code2paper.agentic.unified_context_compiler import (
    build_consumer_invocation_plan_v1,
    build_consumer_workset_manifest_v2,
    build_run_invocation_budget_envelope_v1,
    consumer_response_json_schema,
    extend_writer_worksets_from_narrative_plan,
)
from code2paper.llm.section_writer import build_publication_writer_request

from . import page_split_probe as split

#: 公式家族名（与计划/payload 的字段一一对应）。
OBLIGATION_FAMILY = "obligation"
PACKAGE_FAMILY = "package"
ORDER_FAMILIES: tuple[str, ...] = (OBLIGATION_FAMILY, PACKAGE_FAMILY)

#: 与真实请求 payload 的 `formula_packages` 同形的最小序列化记录：本层只消费
#: `package_id` / `satisfied_obligation_ids` / `source_detail_ids` 三个键。
_PACKAGE_ID_PREFIX = "pkg:formula:"


def packages_for(obligations: Sequence[Any]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "package_id": f"{_PACKAGE_ID_PREFIX}{obligation.obligation_id}",
            "satisfied_obligation_ids": [str(obligation.obligation_id)],
            "source_detail_ids": [str(item) for item in obligation.source_detail_ids],
            "authority_status": "code_verified",
        }
        for obligation in obligations
    )


def _profile_budget() -> dict[str, int]:
    profile = {
        "max_page_input_tokens": 20000,
        "max_total_input_tokens": 400000,
        "max_formalizer_calls": 8,
        "max_writer_calls": 8,
        "max_realizer_calls": 8,
        "max_binder_calls": 0,
        "max_obligations_per_page": 8,
        "max_formula_repair_calls": 0,
        "safety_margin_tokens": 1024,
        "prompt_token_reserve": 2048,
        "thinking_token_reserve": 0,
    }
    for role in ("formalizer", "writer", "realizer", "binder"):
        profile[f"output_token_reserve_{role}"] = 4096 if role != "binder" else 2048
        profile[f"max_request_input_tokens_{role}"] = 60000
        profile[f"scaffolding_token_reserve_{role}"] = (
            4096 if role in {"writer", "realizer"} else 0
        )
        profile[f"retry_reserve_input_tokens_{role}"] = 0
    return profile


def _envelope():
    return build_run_invocation_budget_envelope_v1(
        profile_budget=_profile_budget(),
        model_capabilities={"context_tokens": 131072},
        run_digest="sha256:gap2-run",
        profile_digest="sha256:gap2-profile",
        model_identity_digest="sha256:gap2-model",
    )


@dataclass(frozen=True)
class CompiledFormulaMaterial:
    """一次真实编译的页 + 真实 writer 请求载荷。"""

    order: str
    page_id: str
    page_digest: str
    page_payload: Mapping[str, Any]
    request_payload: Mapping[str, Any]


def compile_material(order: str = "") -> CompiledFormulaMaterial:
    """按给定家族顺序真跑一次编译与请求构建。``order`` 只反转目标家族的 ID 顺序。"""

    if order and order not in ORDER_FAMILIES:
        raise ValueError(f"unknown formula order family: {order}")
    archive = split._archive()
    obligations = split._obligations()
    packages = packages_for(obligations)
    envelope = _envelope()
    plan = split._plan(
        obligations,
        targets=(),
        package_ids=tuple(str(item["package_id"]) for item in packages),
        order=order,
    )
    base = build_consumer_workset_manifest_v2(
        archive,
        {split.MECHANISM_ID: obligations},
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    manifest = extend_writer_worksets_from_narrative_plan(
        base,
        plan,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
        formula_packages=packages,
        formula_obligations=obligations,
    )
    invocation_plan = build_consumer_invocation_plan_v1(
        manifest,
        envelope,
        phase="writer",
        plan_revision=1,
        profile_digest=envelope.profile_digest,
        model_identity_digest=envelope.model_identity_digest,
        model_context_tokens=131072,
    )
    writer_inputs = _writer_section_inputs_v2(
        narrative_plan=plan,
        formula_packages=packages,
        formula_obligations=obligations,
        consumer_workset_manifest=manifest,
        consumer_invocation_plan=invocation_plan,
    )
    assert len(writer_inputs) == 1, "该最小材料恰好一个 writer section"
    section = writer_inputs[0]
    page_index = {str(page.page_id): page for page in manifest.pages}
    page = page_index[str(section.prompt_payload.get("unified_v2_page_id") or "")]
    request = build_publication_writer_request(
        section,
        system_prompt=section.system_prompt,
        schema_name="publication_method_section_v1",
        response_json_schema=consumer_response_json_schema(
            "writer", section_id=section.section_id
        ),
    )
    return CompiledFormulaMaterial(
        order=order,
        page_id=str(page.page_id),
        page_digest=str(page.technical_bytes_digest),
        page_payload=dict(page.technical_payload),
        request_payload=dict(request.input_payload),
    )


def measured_material_digest(payload: Mapping[str, Any]) -> str:
    """与真实 Writer 调用点同规则：从 `shared_contexts` 的实际材料字节重算。"""

    from code2paper.agentic.mechanism_context_models import (
        canonical_json_bytes,
        sha256_digest,
    )

    contexts = payload.get("shared_contexts") or ()
    raw = contexts[0] if len(contexts) == 1 else None
    if isinstance(raw, Mapping):
        return sha256_digest(canonical_json_bytes(dict(raw)))
    if isinstance(raw, bytes):
        return sha256_digest(bytes(raw))
    if isinstance(raw, str):
        return sha256_digest(raw.encode("utf-8"))
    return ""


@dataclass(frozen=True)
class RecheckOutcome:
    label: str
    failures: tuple[str, ...]
    scope_failures: tuple[str, ...]
    binding_failure: bool
    material_failure: bool


def recheck(
    baseline: CompiledFormulaMaterial,
    *,
    label: str,
    payload: Mapping[str, Any] | None = None,
    family: str = "",
    sites: str = "binding",
) -> RecheckOutcome:
    """对给定载荷跑公共复核；`sites` 决定顺序改变落在哪些合同位点。"""

    candidate = json.loads(
        json.dumps(payload if payload is not None else baseline.request_payload, ensure_ascii=False)
    )
    if family:
        if family not in ORDER_FAMILIES:
            raise ValueError(f"unknown formula order family: {family}")
        key = (
            "allowed_formula_obligation_ids"
            if family == OBLIGATION_FAMILY
            else "allowed_formula_package_ids"
        )
        row_key = (
            "formula_obligation_ids"
            if family == OBLIGATION_FAMILY
            else "formula_package_ids"
        )
        if sites == "binding":
            candidate["binding_contract"][key] = list(
                reversed(list(candidate["binding_contract"][key]))
            )
        elif sites == "all":
            candidate["binding_contract"][key] = list(
                reversed(list(candidate["binding_contract"][key]))
            )
            for row in (candidate.get("narrative_plan") or {}).get("paragraphs") or ():
                row[row_key] = list(reversed(list(row.get(row_key) or ())))
            context = (candidate.get("shared_contexts") or [{}])[0]
            if isinstance(context, dict) and row_key in context:
                context[row_key] = list(reversed(list(context[row_key])))
        else:
            raise ValueError(f"unknown reorder sites: {sites}")

    snapshot = page_contract_snapshot_from_payload(
        invocation_id="inv:gap2",
        payload=baseline.request_payload,
        request_digest="sha256:request",
    ).model_copy(update={"technical_bytes_digest": baseline.page_digest})
    failures = tuple(
        compare_actual_request_to_page_contract(
            snapshot,
            invocation_id="inv:gap2",
            payload=candidate,
            page_id=str(
                (candidate.get("narrative_plan") or {}).get("page_id")
                or baseline.page_id
            ),
            max_output_tokens=snapshot.max_output_tokens,
            actual_technical_bytes_digest=measured_material_digest(candidate),
        )
    )
    return RecheckOutcome(
        label=label,
        failures=failures,
        scope_failures=tuple(
            item for item in failures if ":scope:" in item
        ),
        binding_failure=any(
            item.endswith(":binding_contract") for item in failures
        ),
        material_failure=any(item.endswith(":technical_bytes") for item in failures),
    )


def package_source_detail_map(payload: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    """package → source detail 闭包关联（顺序无关的映射事实）。

    同时接受页材料载荷本身与 writer 请求载荷（后者把页材料放在 ``shared_contexts[0]``）。
    """

    context: Mapping[str, Any] = payload
    contexts = payload.get("shared_contexts")
    if isinstance(contexts, (list, tuple)) and contexts:
        first = contexts[0]
        if isinstance(first, Mapping):
            context = first
    mapping = context.get("formula_package_source_detail_ids") or {}
    return {
        str(package_id): tuple(str(item) for item in (detail_ids or ()))
        for package_id, detail_ids in (mapping or {}).items()
    }


def family_ids(payload: Mapping[str, Any], family: str) -> tuple[str, ...]:
    """从页材料或请求载荷里读出某个公式家族的 ID 序列（保序）。"""

    if family not in ORDER_FAMILIES:
        raise ValueError(f"unknown formula order family: {family}")
    key = (
        "formula_obligation_ids"
        if family == OBLIGATION_FAMILY
        else "formula_package_ids"
    )
    context: Mapping[str, Any] = payload
    contexts = payload.get("shared_contexts")
    if isinstance(contexts, (list, tuple)) and contexts:
        first = contexts[0]
        if isinstance(first, Mapping):
            context = first
    values = context.get(key)
    if values is None:
        values = payload.get(key)
    return tuple(str(item) for item in (values or ()))


def binding_family_ids(payload: Mapping[str, Any], family: str) -> tuple[str, ...]:
    """请求 payload 的 binding contract 里该家族的 ID 序列（保序）。"""

    key = (
        "allowed_formula_obligation_ids"
        if family == OBLIGATION_FAMILY
        else "allowed_formula_package_ids"
    )
    binding = payload.get("binding_contract") or {}
    return tuple(str(item) for item in (binding.get(key) or ()))


def plan_row_family_ids(payload: Mapping[str, Any], family: str) -> tuple[str, ...]:
    """请求 payload 的 Narrative 计划行里该家族的 ID 序列（保序，逐行拼接）。"""

    key = (
        "formula_obligation_ids"
        if family == OBLIGATION_FAMILY
        else "formula_package_ids"
    )
    rows = (payload.get("narrative_plan") or {}).get("paragraphs") or ()
    return tuple(
        str(item)
        for row in rows
        for item in (row.get(key) or ())
    )
