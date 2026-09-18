"""WP3 §7.6：单一正文表面。

事故响应同时带两份正文：完整响应里的 ``section_markdown``（23176 字符）与逐段
``paragraph_markdown``（compact fragment 6913 字符）。同一篇正文两处生成，就可能漂移，
也让"以哪一份为准"变成隐患。

本模块确立一条规则：**有序 paragraph 对象是唯一正文真源**，``section_markdown`` 只能由
确定性 composer 派生，并标记为派生物；同时保留**本地闭集校验**（每个 required 段落 id
恰好出现一次、顺序符合叙事序号）——这一层不依赖 provider 是否支持 JSON Schema 的
数组约束，因此无论 provider 能力如何都必须执行。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict

from code2paper.agentic.writer_output_workload import narrative_ordinal


class ProseSurfaceAuditV1(BaseModel):
    """一次响应正文表面的审计结果（只读、可离线重放）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prose_source: str = "paragraph_objects"
    paragraph_ids: tuple[str, ...] = ()
    paragraph_count: int = 0
    duplicate_paragraph_ids: tuple[str, ...] = ()
    missing_paragraph_ids: tuple[str, ...] = ()
    unexpected_paragraph_ids: tuple[str, ...] = ()
    order_matches_narrative_ordinal: bool = True
    section_markdown_present: bool = False
    section_markdown_is_derivative_only: bool = True
    derived_section_matches_response: bool = False
    failures: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.failures


def _paragraphs_of(payload: Any) -> tuple[Mapping[str, Any], ...]:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    if not isinstance(payload, Mapping):
        return ()
    rows = payload.get("paragraphs") or ()
    return tuple(row for row in rows if isinstance(row, Mapping))


def compose_section_markdown(
    payload: Any,
    *,
    section_id: str = "",
    heading: str = "",
) -> str:
    """由有序段落确定性拼接正文；空段落正文不产生内容。

    顺序采用**叙事序号**（P2 在 P10 之前），不使用字典序。
    """

    rows = sorted(
        _paragraphs_of(payload),
        key=lambda row: narrative_ordinal(str(row.get("paragraph_id") or "")),
    )
    parts: list[str] = []
    resolved_heading = str(heading or "").strip()
    if not resolved_heading and isinstance(payload, Mapping):
        resolved_heading = str(payload.get("heading_text") or "").strip()
    if resolved_heading and not resolved_heading.startswith("#"):
        resolved_heading = f"## {resolved_heading}"
    if resolved_heading:
        parts.append(resolved_heading)
    for row in rows:
        text = str(row.get("paragraph_markdown") or "").strip()
        if text:
            parts.append(text)
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n"


def audit_prose_surface(
    payload: Any,
    *,
    required_paragraph_ids: Sequence[str] = (),
    heading: str = "",
) -> ProseSurfaceAuditV1:
    """本地闭集校验 + 派生物判定（不依赖 provider schema 能力）。"""

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    rows = _paragraphs_of(payload)
    ids = [str(row.get("paragraph_id") or "").strip() for row in rows]
    ids = [item for item in ids if item]

    seen: list[str] = []
    duplicates: list[str] = []
    for item in ids:
        if item in seen and item not in duplicates:
            duplicates.append(item)
        seen.append(item)

    required = tuple(str(item) for item in required_paragraph_ids if str(item).strip())
    missing = tuple(item for item in required if item not in set(ids))
    unexpected = tuple(
        item for item in dict.fromkeys(ids) if required and item not in set(required)
    )
    ordinal_order = sorted(ids, key=narrative_ordinal)
    order_ok = ids == ordinal_order

    section_markdown = ""
    if isinstance(payload, Mapping):
        section_markdown = str(payload.get("section_markdown") or "")
    composed = compose_section_markdown(payload, heading=heading)

    failures: list[str] = []
    if duplicates:
        failures.append("duplicate_paragraph:" + ",".join(duplicates))
    if missing:
        failures.append("paragraph_missing:" + ",".join(missing))
    if unexpected:
        failures.append("target_out_of_scope:" + ",".join(unexpected))
    if not order_ok:
        failures.append("paragraph_order_mismatch")

    return ProseSurfaceAuditV1(
        paragraph_ids=tuple(ids),
        paragraph_count=len(ids),
        duplicate_paragraph_ids=tuple(duplicates),
        missing_paragraph_ids=tuple(missing),
        unexpected_paragraph_ids=tuple(unexpected),
        order_matches_narrative_ordinal=order_ok,
        section_markdown_present=bool(section_markdown.strip()),
        section_markdown_is_derivative_only=True,
        derived_section_matches_response=(
            bool(section_markdown.strip())
            and section_markdown.strip() == composed.strip()
        ),
        failures=tuple(failures),
    )


def normalize_writer_section_payload(
    payload: Any,
    *,
    required_paragraph_ids: Sequence[str] = (),
    heading: str = "",
) -> dict[str, Any]:
    """把响应归一为"段落对象唯一真源"的载荷。

    ``section_markdown`` 一律替换为确定性派生结果，并显式标注为派生物；模型自带的那份
    不再作为正文来源（避免两个表面漂移）。
    """

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    source = dict(payload) if isinstance(payload, Mapping) else {}
    audit = audit_prose_surface(
        source, required_paragraph_ids=required_paragraph_ids, heading=heading
    )
    rows = sorted(_paragraphs_of(source), key=lambda row: narrative_ordinal(
        str(row.get("paragraph_id") or "")
    ))
    normalized = {
        **source,
        "paragraphs": [dict(row) for row in rows],
        "section_markdown": compose_section_markdown(source, heading=heading),
        "section_markdown_derived": True,
        "prose_source": "paragraph_objects",
        # ``valid`` 是派生属性：显式写入序列化结果，读者无需重算。
        "prose_audit": {**audit.model_dump(mode="json"), "valid": audit.valid},
    }
    return normalized


__all__ = [
    "ProseSurfaceAuditV1",
    "audit_prose_surface",
    "compose_section_markdown",
    "normalize_writer_section_payload",
]
