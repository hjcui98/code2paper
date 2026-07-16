from __future__ import annotations

from typing import assert_never

from code2paper.core.schemas import (
    EvidenceItem,
    EvidenceStrength,
    Mechanism,
    MethodStageEvidence,
    RawEvidencePack,
    SourceType,
    SupportStatus,
)


def raw_evidence_fallback_stage(raw_pack: RawEvidencePack) -> MethodStageEvidence | None:
    hard_items = _hard_code_items(raw_pack.evidence_items)
    if not hard_items:
        return None
    return MethodStageEvidence(
        stage_id="S1",
        name="Implementation Evidence",
        purpose="Preserve hard implementation evidence spans for evidence-constrained method authoring.",
        inputs=_source_roles(hard_items),
        outputs=_summaries(hard_items),
        mechanisms=[
            Mechanism(
                mechanism_id="MECH1",
                description=_description(hard_items),
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=[item.evidence_id for item in hard_items],
            )
        ],
    )


def _hard_code_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    return [
        item
        for item in items
        if item.evidence_strength == EvidenceStrength.HARD
        and item.source_type in {SourceType.BASH, SourceType.CONFIG, SourceType.SOURCE}
    ]


def _source_roles(items: list[EvidenceItem]) -> list[str]:
    roles: list[str] = []
    for item in items:
        match item.source_type:
            case SourceType.SOURCE:
                roles.append("source implementation evidence")
            case SourceType.BASH:
                roles.append("command-level implementation evidence")
            case SourceType.CONFIG:
                roles.append("configuration evidence")
            case SourceType.COMMENT | SourceType.AUTHOR:
                continue
            case unreachable:
                assert_never(unreachable)
    return _dedupe(roles)


def _summaries(items: list[EvidenceItem]) -> list[str]:
    return _dedupe([item.content_summary.replace("_", " ") for item in items])


def _description(items: list[EvidenceItem]) -> str:
    summaries = ", ".join(_summaries(items))
    return f"Hard implementation evidence covers {summaries}."


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = value.strip()
        if text and text not in result:
            result.append(text)
    return result
