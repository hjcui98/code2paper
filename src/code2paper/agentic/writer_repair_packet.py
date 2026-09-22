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
from code2paper.agentic.publication_transaction_contract import (
    CANONICAL_FAILURE_ALLOWED_EDITS,
    canonical_failure_code,
    select_failure_action,
)

RepairKindV1 = Literal[
    "detail_witness_missing",
    "paragraph_missing",
    "formula_placeholder_missing",
    "formula_consumer_mismatch",
    "input_material_missing",
    "authority_surface_violation",
    "target_out_of_scope",
    "atom_witness_missing",
    "exact_span_not_in_body",
    "detail_semantic_mismatch",
    "transport_failure",
    "send_outcome_unknown",
    "ledger_corrupt",
    "unknown_failure",
]

#: ``repair_in_place`` 只对 writer_content 类失败开放；``typed_block`` 表示失败码
#: 未知/账本损坏，不得默认允许改正文（审计 §E.1）。
EscalationV1 = Literal["repair_in_place", "replan_required", "typed_block"]


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
        """给模型的最小修复载荷。

        审计 §E.2：可以隐藏内部冻结摘要（其它已接受段落的 digest），但**修复所必需的
        局部内容**（失败段正文、权限引用、允许修改的段落与缺失 target 的原因）必须
        留下；否则模型只能盲写。
        """

        return {
            "repair_kind": self.repair_kind,
            "escalation": self.escalation,
            "paragraph_id": self.paragraph_id,
            "section_id": self.section_id,
            "paragraph_markdown": self.paragraph_markdown,
            "missing_targets": [
                {"kind": item.kind, "id": item.id, "reason_code": item.reason_code}
                for item in self.missing_targets
            ],
            "allowed_edits": list(self.allowed_edits),
            "allowed_paragraph_ids": list(self.allowed_paragraph_ids),
            "preserve_other_paragraphs": self.preserve_other_paragraphs,
            # 权限引用是作者/仓库授权边界，修复时必须可见。
            "authority_refs": list(self.authority_refs),
        }


def contract_failures_from_legacy_strings(
    failures: Sequence[Any], *, paragraph_id: str = ""
) -> tuple[dict[str, str], ...]:
    """兼容适配：把历史 acceptance 失败项映射为 canonical (code, kind, target)。

    仅用于**读取历史证据**；执行层不使用拼接字符串判断（§7.5），返回的 code 已经是
    ``publication_transaction_contract`` 的 canonical 集合（审计 §E.1）。
    """

    mapped: list[dict[str, str]] = []
    for raw in failures or ():
        text = str(raw)
        if text.startswith("missing_paragraph:"):
            target = text.split(":", 1)[1]
            mapped.append(
                {
                    "code": canonical_failure_code("missing_paragraph"),
                    "kind": "paragraph",
                    "target": target,
                }
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
                    "code": canonical_failure_code(f"missing_{marker}_witness"),
                    "kind": marker,
                    "target": target,
                }
            )
            break
        else:
            if text in {"invalid_count", "invalid_witness_count"}:
                mapped.append(
                    {
                        "code": canonical_failure_code("detail_semantic_mismatch"),
                        "kind": "",
                        "target": "",
                    }
                )
            elif text.startswith("authority_violation"):
                mapped.append(
                    {
                        "code": canonical_failure_code("authority_surface_violation"),
                        "kind": "",
                        "target": "",
                    }
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
    """构造有界修复包：动作由 canonical 失败表按责任/依赖选择（审计 §E.1）。"""

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
        canonical = canonical_failure_code(code)
        codes.append(canonical)
        if kind and target:
            targets.append(RepairTargetV1(kind=kind, id=target, reason_code=canonical))

    selection = select_failure_action(codes)
    repair_kind = selection.code
    frozen = {
        str(key): str(value)
        for key, value in (accepted_paragraph_digests or {}).items()
        if str(key) != str(paragraph_id)
    }
    if selection.escalation == "typed_block":
        # 未知失败码 / 账本损坏：typed block，不默认允许改正文。
        return WriterRepairPacketV1(
            repair_kind=repair_kind,
            escalation="typed_block",
            escalation_reason=(
                "失败无法归因到已注册的 owner（"
                f"{','.join(selection.codes)}）；按 system typed block 处理，"
                "不允许用内容补写掩盖未知失败"
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
    if selection.escalation == "replan_required":
        return WriterRepairPacketV1(
            repair_kind=repair_kind,
            escalation="replan_required",
            escalation_reason=(
                "该失败属于"
                f"{selection.owner}（{selection.action}），不能靠原地补写过门："
                "需要先 plan revision / 重新编译"
                f"（{','.join(selection.codes)}）"
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
    allowed_edits = CANONICAL_FAILURE_ALLOWED_EDITS.get(
        repair_kind, ("paragraph_content", "detail_witnesses")
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
        "allowed_edits": list(allowed_edits),
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
        allowed_edits=allowed_edits,
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
