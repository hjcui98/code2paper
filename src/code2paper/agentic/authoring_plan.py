from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.authoring_context import EvidenceBoundAuthoringClaim, EvidenceBoundAuthoringContext


class EvidenceBoundAuthoringSection(BaseModel):
    """One planned Method section backed by verified claim and evidence ids."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    heading: str
    purpose: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    caveat_required: bool = False
    writing_instructions: list[str] = Field(default_factory=list)


class EvidenceBoundAuthoringPlan(BaseModel):
    """Auditable Method writing plan derived from the evidence-bound authoring context."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "evidence-bound-authoring-plan"
    method_name: str = ""
    author_goal: str = ""
    sections: list[EvidenceBoundAuthoringSection] = Field(default_factory=list)
    excluded_claim_ids: list[str] = Field(default_factory=list)
    excluded_evidence_ids: list[str] = Field(default_factory=list)
    hard_gate_passed: bool = True
    recommended_actions: list[str] = Field(default_factory=list)


def build_authoring_plan(context: EvidenceBoundAuthoringContext) -> EvidenceBoundAuthoringPlan:
    """Create a section-level writing plan without admitting unsupported claims."""

    safe_claims = [*context.allowed_claims, *context.caveated_claims]
    sections = [_section_for_claim(index, claim) for index, claim in enumerate(safe_claims, start=1)]
    excluded_claim_ids = [claim.claim_id for claim in context.excluded_claims]
    excluded_evidence_ids = _dedupe([evidence_id for claim in context.excluded_claims for evidence_id in claim.evidence_ids])
    missing_evidence_sections = [section.section_id for section in sections if not section.evidence_ids]
    forbidden_claims = sorted(set(excluded_claim_ids).intersection({claim_id for section in sections for claim_id in section.claim_ids}))
    actions: list[str] = []
    if not sections:
        actions.append("return_to_analysis_for_evidence_backed_authoring_claims")
    if missing_evidence_sections:
        actions.append("repair_authoring_plan_sections_without_evidence")
    if forbidden_claims:
        actions.append("remove_excluded_claims_from_authoring_plan")
    if not actions:
        actions.append("authoring_plan_ready_for_evidence_constrained_method_writing")
    return EvidenceBoundAuthoringPlan(
        method_name=context.method_name,
        author_goal=context.author_goal,
        sections=sections,
        excluded_claim_ids=excluded_claim_ids,
        excluded_evidence_ids=excluded_evidence_ids,
        hard_gate_passed=bool(sections) and not missing_evidence_sections and not forbidden_claims,
        recommended_actions=actions,
    )


def authoring_plan_brief(plan: EvidenceBoundAuthoringPlan) -> str:
    lines = [
        "Evidence-bound Method writing plan:",
        f"- Method: {plan.method_name or 'unspecified'}.",
        f"- Author goal: {plan.author_goal or 'unspecified'}.",
        "- Follow these planned sections only when their claim and evidence ids are present.",
    ]
    for section in plan.sections[:20]:
        caveat = " yes" if section.caveat_required else " no"
        lines.append(
            f"- {section.section_id} {section.heading}: claims={', '.join(section.claim_ids) or 'none'}; "
            f"evidence={', '.join(section.evidence_ids) or 'none'}; caveat_required={caveat}."
        )
        for instruction in section.writing_instructions[:3]:
            lines.append(f"  - {instruction}")
    if plan.excluded_claim_ids:
        lines.append("- Excluded claim ids not allowed in prose: " + ", ".join(plan.excluded_claim_ids) + ".")
    return "\n".join(lines)


def write_authoring_plan(path: str | Path, plan: EvidenceBoundAuthoringPlan) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_authoring_plan(path: str | Path) -> EvidenceBoundAuthoringPlan:
    return EvidenceBoundAuthoringPlan.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _section_for_claim(index: int, claim: EvidenceBoundAuthoringClaim) -> EvidenceBoundAuthoringSection:
    caveat_required = claim.writing_boundary == "write_only_with_caveats" or claim.support_status == "partial"
    instructions = [
        "Write only the implementation behavior supported by the listed evidence ids.",
        "Do not add mechanisms, motivations, or results that are absent from frozen code evidence.",
    ]
    if caveat_required:
        caveat = "; ".join(claim.caveats[:3]) or "state the implemented fragment and omit unsupported extensions"
        instructions.append("Caveat this claim: " + caveat)
    return EvidenceBoundAuthoringSection(
        section_id=f"AP-S{index}",
        heading=_heading_from_claim(claim),
        purpose=claim.claim_text,
        claim_ids=[claim.claim_id],
        evidence_ids=claim.evidence_ids,
        caveat_required=caveat_required,
        writing_instructions=instructions,
    )


def _heading_from_claim(claim: EvidenceBoundAuthoringClaim) -> str:
    text = claim.claim_text.strip().rstrip(".")
    if not text:
        return f"Evidence-backed claim {claim.claim_id}"
    words = text.split()
    heading = " ".join(words[:7])
    return heading[:1].upper() + heading[1:]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
