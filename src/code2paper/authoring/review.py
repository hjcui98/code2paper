"""Generate author confirmation questions from low-confirmation method evidence."""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.core.schemas import (
    ClaimEvidenceMap,
    CodeAlignmentIR,
    ConfidenceLevel,
    MethodEvidence,
    ModuleCategory,
    RawEvidencePack,
    SupportStatus,
)


def build_author_review_questions(
    *,
    raw_pack: RawEvidencePack,
    alignment: CodeAlignmentIR,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap | None = None,
) -> str:
    """Build a markdown review artifact for author confirmation.

    The artifact is intentionally generic. It asks the author to confirm stage
    order, core modules, low-confidence mechanisms, quantitative parameters, and
    novelty-adjacent claims without assuming a specific paper domain.
    """

    lines: list[str] = [
        "# Author Review Questions",
        "",
        f"Project: `{method_evidence.project_id}`",
        f"Author mode: `{method_evidence.author_mode.value}`",
        f"Author confirmation required: `{str(method_evidence.author_confirmation_required).lower()}`",
        "",
    ]
    if method_evidence.author_confirmation_required:
        lines.extend(
            [
                "This run needs author confirmation before the draft is treated as paper-ready.",
                "Please answer or edit the questions below; unresolved items should keep the method draft conservative.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Author markers were available for this run. The questions below are still useful as a final sanity check.",
                "",
            ]
        )

    lines.extend(_stage_questions(alignment, method_evidence))
    lines.extend(_module_questions(alignment, method_evidence))
    lines.extend(_mechanism_questions(method_evidence))
    lines.extend(_parameter_questions(method_evidence))
    lines.extend(_claim_questions(alignment, claim_map))
    lines.extend(_source_boundary_questions(raw_pack, method_evidence))
    return "\n".join(lines).rstrip() + "\n"


def build_author_review_questions_from_files(
    *,
    raw_evidence_path: str | Path,
    alignment_path: str | Path,
    method_evidence_path: str | Path,
    claim_map_path: str | Path | None = None,
) -> str:
    raw_pack = RawEvidencePack.model_validate(json.loads(Path(raw_evidence_path).read_text(encoding="utf-8")))
    alignment = CodeAlignmentIR.model_validate(json.loads(Path(alignment_path).read_text(encoding="utf-8")))
    method_evidence = MethodEvidence.model_validate(json.loads(Path(method_evidence_path).read_text(encoding="utf-8")))
    claim_map = None
    if claim_map_path is not None:
        claim_map = ClaimEvidenceMap.model_validate(json.loads(Path(claim_map_path).read_text(encoding="utf-8")))
    return build_author_review_questions(
        raw_pack=raw_pack,
        alignment=alignment,
        method_evidence=method_evidence,
        claim_map=claim_map,
    )


def _stage_questions(alignment: CodeAlignmentIR, method_evidence: MethodEvidence) -> list[str]:
    lines = ["## Stage And Pipeline Confirmation", ""]
    if not method_evidence.stages:
        return lines + ["- [ ] No method stages were extracted. What are the paper-facing method stages?", ""]
    stage_names = " -> ".join(stage.name for stage in method_evidence.stages)
    lines.append(f"- [ ] Is this paper-facing method order correct: `{stage_names}`?")
    for stage in method_evidence.stages:
        evidence_ids = _stage_evidence(stage)
        lines.append(
            f"- [ ] Should `{stage.name}` be a main method stage? Purpose: {stage.purpose} Evidence: `{', '.join(evidence_ids) or 'none'}`."
        )
    for mapping in alignment.stage_mappings:
        execution = next((stage for stage in alignment.execution_stages if stage.stage_id == mapping.execution_stage_id), None)
        method = next((stage for stage in alignment.method_stages if stage.stage_id == mapping.method_stage_id), None)
        if execution and method and mapping.confidence < 0.9:
            lines.append(
                f"- [ ] Is execution stage `{execution.name}` correctly mapped to method stage `{method.name}`? Confidence: {mapping.confidence:.2f}."
            )
    return lines + [""]


def _module_questions(alignment: CodeAlignmentIR, method_evidence: MethodEvidence) -> list[str]:
    lines = ["## Module Role Confirmation", ""]
    core_roles = [role for role in alignment.module_roles if role.category == ModuleCategory.METHOD_CORE]
    support_roles = [role for role in alignment.module_roles if role.category != ModuleCategory.METHOD_CORE]
    for role in core_roles[:20]:
        lines.append(
            f"- [ ] Should `{role.path}:{role.symbol}` be treated as method-core? Current role: {role.role}. Confidence: {role.confidence:.2f}."
        )
    if len(core_roles) > 20:
        lines.append(f"- [ ] {len(core_roles) - 20} additional method-core modules were omitted from this checklist; review the alignment IR if needed.")
    ambiguous_support = [role for role in support_roles if role.confidence < 0.8][:10]
    for role in ambiguous_support:
        lines.append(
            f"- [ ] Should `{role.path}:{role.symbol}` remain outside the main method? Current category: `{role.category.value}`."
        )
    if not core_roles:
        lines.append("- [ ] No method-core modules were detected. Which files/symbols should define the main method?")
    return lines + [""]


def _mechanism_questions(method_evidence: MethodEvidence) -> list[str]:
    lines = ["## Mechanism Confirmation", ""]
    low_or_partial = []
    for stage in method_evidence.stages:
        for mechanism in stage.mechanisms:
            if mechanism.confidence != ConfidenceLevel.HIGH or mechanism.support_status != SupportStatus.SUPPORTED:
                low_or_partial.append((stage.name, mechanism))
    target = low_or_partial
    if not target:
        target = [(stage.name, mechanism) for stage in method_evidence.stages for mechanism in stage.mechanisms]
    for stage_name, mechanism in target[:20]:
        lines.append(
            f"- [ ] In `{stage_name}`, is this mechanism description accurate? `{mechanism.description}`"
        )
    for pattern in method_evidence.behavior_patterns:
        if pattern.confidence != ConfidenceLevel.HIGH:
            lines.append(
                f"- [ ] Should detected behavior `{pattern.behavior_type}` in `{pattern.path}:{pattern.symbol}` be mentioned in the main method, appendix, or omitted?"
            )
    return lines + [""]


def _parameter_questions(method_evidence: MethodEvidence) -> list[str]:
    lines = ["## Quantitative Parameter Confirmation", ""]
    if not method_evidence.architecture_parameters:
        return lines + ["- [ ] No architecture/config parameters were extracted. Which numeric values must be stated in the method?", ""]
    for parameter in method_evidence.architecture_parameters[:30]:
        lines.append(
            f"- [ ] Is `{parameter.name}={parameter.value}` in `{parameter.path}:{parameter.symbol}` an architecture parameter, a training hyperparameter, or an implementation default that should stay out of the main method?"
        )
    if len(method_evidence.architecture_parameters) > 30:
        lines.append(f"- [ ] {len(method_evidence.architecture_parameters) - 30} additional parameters were omitted from this checklist; review method_evidence if needed.")
    return lines + [""]


def _claim_questions(alignment: CodeAlignmentIR, claim_map: ClaimEvidenceMap | None) -> list[str]:
    lines = ["## Claim And Novelty Boundary Confirmation", ""]
    unsupported = alignment.author_alignment.unsupported_claims
    for claim in unsupported:
        lines.append(f"- [ ] This author claim was unsupported by current evidence and kept out of the draft. Should it be revised, removed, or supported with more files? `{claim}`")
    if claim_map is not None:
        for claim in claim_map.claims:
            if claim.source.startswith("author_claim") or claim.support_status != SupportStatus.SUPPORTED:
                lines.append(
                    f"- [ ] Claim `{claim.claim_text}` has support status `{claim.support_status.value}`. Should it appear in the main method, notes, appendix, or nowhere?"
                )
    if not unsupported and claim_map is None:
        lines.append("- [ ] Which statements, if any, are true novelty claims rather than ordinary implementation descriptions?")
    return lines + [""]


def _source_boundary_questions(raw_pack: RawEvidencePack, method_evidence: MethodEvidence) -> list[str]:
    lines = ["## Source Boundary Confirmation", ""]
    if raw_pack.excluded_sources or method_evidence.excluded_sources:
        for source in raw_pack.excluded_sources or method_evidence.excluded_sources:
            lines.append(f"- [ ] `{source.path}` is excluded from the main evidence chain because: {source.reason}. Is this correct?")
    else:
        lines.append("- [ ] Are there files, generated artifacts, logs, or README-only statements that should be excluded from the method evidence chain?")
    return lines + [""]


def _stage_evidence(stage) -> list[str]:
    evidence_ids: list[str] = []
    for mechanism in stage.mechanisms:
        evidence_ids.extend(mechanism.evidence_ids)
    return _dedupe(evidence_ids)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
