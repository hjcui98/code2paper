"""WP3 §7.3：Writer 定向修复包（repair packet）。

修复必须**有界**：只改被拒绝的段落、只补齐缺失的义务、并冻结其余已接受段落的
摘要；并且当失败原因本身说明"叙事归属不对"（权限越界、目标越界）时，**不得**硬让
Writer 在原段落里加一句话过门——那需要先 plan revision 再 fork/重新编译。

本模块只构造数据结构（纯函数、无 I/O），供调用边界构造 repair 请求与执行层消费。
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.digest import digest_json

RepairKindV1 = Literal[
    "missing_detail_witness",
    "missing_paragraph",
    "formula_consumer_mismatch",
    "input_material_missing",
    "authority_surface_violation",
    "target_out_of_scope",
    "detail_semantic_mismatch",
]

EscalationV1 = Literal["repair_in_place", "replan_required"]

#: 这些失败说明"位置/权限"本身有问题：原地补写会把错误事实写进正文。
_ESCALATING_CODES = {
    "authority_surface_violation",
    "target_out_of_scope",
}

_REPAIRABLE_EDITS = {
    "missing_detail_witness": ("paragraph_content", "detail_witnesses"),
    "missing_paragraph": ("paragraph_content", "detail_witnesses"),
    "formula_consumer_mismatch": ("paragraph_content", "formula_references"),
    "input_material_missing": ("paragraph_content", "detail_witnesses"),
    "detail_semantic_mismatch": ("paragraph_content", "detail_witnesses"),
}


class RepairTargetV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    id: str
    reason_code: str = ""


class WriterRepairPacketV1(BaseModel):
    """一次有界修复请求的完整语义（§7.3）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    repair_kind: str
    escalation: EscalationV1 = "repair_in_place"
    escalation_reason: str = ""
    paragraph_id: str
    section_id: str = ""
    missing_targets: tuple[RepairTargetV1, ...] = ()
    allowed_edits: tuple[str, ...] = ()
    #: 允许模型改写的段落集合：有且仅有失败段落。
    allowed_paragraph_ids: tuple[str, ...] = ()
    preserve_other_paragraphs: bool = True
    #: 已接受且**不得改变**的段落摘要（失败段落被排除在外）。
    frozen_paragraph_digests: dict[str, str] = Field(default_factory=dict)
    paragraph_markdown: str = ""
    authority_refs: tuple[str, ...] = ()
    content_digest: str = ""

    def as_request_payload(self) -> dict[str, Any]:
        """给模型的最小修复载荷（不含内部冻结摘要）。"""

        return {
            "repair_kind": self.repair_kind,
            "paragraph_id": self.paragraph_id,
            "missing_targets": [
                {"kind": item.kind, "id": item.id} for item in self.missing_targets
            ],
            "allowed_edits": list(self.allowed_edits),
            "preserve_other_paragraphs": self.preserve_other_paragraphs,
        }


def contract_failures_from_legacy_strings(
    failures: Sequence[Any], *, paragraph_id: str = ""
) -> tuple[dict[str, str], ...]:
    """兼容适配：把历史 acceptance 失败项映射为 (code, kind, target)。

    仅用于**读取历史证据**；执行层不使用拼接字符串判断（§7.5）。
    """

    mapped: list[dict[str, str]] = []
    for raw in failures or ():
        text = str(raw)
        if text.startswith("missing_paragraph:"):
            target = text.split(":", 1)[1]
            mapped.append(
                {"code": "missing_paragraph", "kind": "paragraph", "target": target}
            )
            continue
        # 形如 "<section>:<paragraph>:detail:detail:<canonical target>"：
        # 段落 id 自身含冒号，所以按 ":<kind>:" 标记切分，而不是按位置。
        for marker in ("detail", "atom", "formula"):
            token = f":{marker}:"
            if token not in text:
                continue
            _left, _sep, right = text.partition(token)
            target = right
            if target.startswith(f"{marker}:"):
                target = target[len(marker) + 1 :]
            mapped.append(
                {
                    "code": f"missing_{marker}_witness",
                    "kind": marker,
                    "target": target,
                }
            )
            break
        else:
            if text in {"invalid_count", "invalid_witness_count"}:
                mapped.append(
                    {"code": "detail_semantic_mismatch", "kind": "", "target": ""}
                )
            elif text.startswith("authority_violation"):
                mapped.append(
                    {"code": "authority_surface_violation", "kind": "", "target": ""}
                )
            continue
        continue
    return tuple(mapped)


def build_writer_repair_packet(
    *,
    paragraph_id: str,
    failures: Sequence[Any],
    paragraph_markdown: str = "",
    section_id: str = "",
    accepted_paragraph_digests: Mapping[str, str] | None = None,
    authority_refs: Sequence[str] = (),
    allowed_paragraph_ids: Sequence[str] | None = None,
) -> WriterRepairPacketV1:
    """构造有界修复包；位置/权限类失败一律升级为 plan revision。"""

    targets: list[RepairTargetV1] = []
    codes: list[str] = []
    for failure in failures or ():
        code = str(getattr(failure, "code", "") or "")
        kind = str(getattr(failure, "target_kind", "") or "")
        target = str(getattr(failure, "target_id", "") or "")
        if not code and isinstance(failure, Mapping):
            code = str(failure.get("code") or "")
            kind = str(failure.get("target_kind") or "") or str(failure.get("kind") or "")
            target = str(failure.get("target_id") or "") or str(failure.get("target") or "")
        if not code:
            continue
        codes.append(code)
        if kind and target:
            targets.append(RepairTargetV1(kind=kind, id=target, reason_code=code))

    escalating = sorted({code for code in codes if code in _ESCALATING_CODES})
    repair_kind = codes[0] if codes else "missing_detail_witness"
    if escalating:
        repair_kind = escalating[0]

    frozen = {
        str(key): str(value)
        for key, value in (accepted_paragraph_digests or {}).items()
        if str(key) != str(paragraph_id)
    }
    if escalating:
        return WriterRepairPacketV1(
            repair_kind=repair_kind,
            escalation="replan_required",
            escalation_reason=(
                "位置/权限类失败不能靠原地补写过门：需要先 plan revision 再重新编译"
                f"（{','.join(escalating)}）"
            ),
            paragraph_id=str(paragraph_id),
            section_id=str(section_id),
            missing_targets=tuple(targets),
            allowed_edits=(),
            allowed_paragraph_ids=(),
            preserve_other_paragraphs=True,
            frozen_paragraph_digests=frozen,
            paragraph_markdown=str(paragraph_markdown),
            authority_refs=tuple(authority_refs or ()),
        )

    allowed_ids = tuple(
        dict.fromkeys(
            [str(paragraph_id)]
            if allowed_paragraph_ids is None
            else [str(item) for item in allowed_paragraph_ids if str(item).strip()]
        )
    )
    payload = {
        "schema_version": "1.0",
        "repair_kind": repair_kind,
        "escalation": "repair_in_place",
        "paragraph_id": str(paragraph_id),
        "section_id": str(section_id),
        "missing_targets": [
            {"kind": item.kind, "id": item.id, "reason_code": item.reason_code}
            for item in targets
        ],
        "allowed_edits": list(_REPAIRABLE_EDITS.get(repair_kind, ("paragraph_content",))),
        "allowed_paragraph_ids": list(allowed_ids),
        "preserve_other_paragraphs": True,
        "frozen_paragraph_digests": frozen,
        "paragraph_markdown": str(paragraph_markdown),
        "authority_refs": list(authority_refs or ()),
    }
    return WriterRepairPacketV1(
        repair_kind=repair_kind,
        paragraph_id=str(paragraph_id),
        section_id=str(section_id),
        missing_targets=tuple(targets),
        allowed_edits=_REPAIRABLE_EDITS.get(repair_kind, ("paragraph_content",)),
        allowed_paragraph_ids=allowed_ids,
        preserve_other_paragraphs=True,
        frozen_paragraph_digests=frozen,
        paragraph_markdown=str(paragraph_markdown),
        authority_refs=tuple(authority_refs or ()),
        content_digest=digest_json(payload),
    )


__all__ = [
    "EscalationV1",
    "RepairKindV1",
    "RepairTargetV1",
    "WriterRepairPacketV1",
    "build_writer_repair_packet",
    "contract_failures_from_legacy_strings",
]
