"""Phase 4 deterministic method planning and authoring."""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.export.run_manifest import hash_file
from code2paper.schemas import (
    ArtifactHash,
    ClaimEvidenceMap,
    CodeAlignmentIR,
    DraftClaimMap,
    LLMConfig,
    MethodAuthoringSidecar,
    MethodAuthoringSidecarParagraph,
    MethodEvidence,
    MethodOutline,
    MethodOutlineParagraph,
    Phase4BlockedReport,
    Phase4Manifest,
    SelfCriticReport,
    TerminologyTable,
    TerminologyTerm,
)
from code2paper.validators.equation_support_validator import validate_equation_support
from code2paper.validators.claim_evidence_validator import validate_claim_evidence
from code2paper.validators.latex_smoke_validator import validate_latex_smoke
from code2paper.validators.numeric_fact_validator import validate_numeric_facts
from code2paper.validators.terminology_validator import validate_terminology_consistency
from code2paper.writing.method_writer import build_method_draft_markdown, build_method_draft_tex


def write_phase4_artifacts(
    *,
    method_root: Path,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    llm_config: LLMConfig,
    alignment: CodeAlignmentIR | None = None,
    preflight_blocked_reason: str = "",
) -> tuple[str | None, str | None, dict[str, Path]]:
    method_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "method_authoring_prompt": method_root / "method_authoring_prompt.md",
        "phase4_blocked_report": method_root / "phase4_blocked_report.json",
        "method_outline": method_root / "method_outline.json",
        "terminology_table": method_root / "terminology_table.json",
        "method_draft_md": method_root / "method_draft.md",
        "method_draft_tex": method_root / "method_draft.tex",
        "draft_claim_map": method_root / "draft_claim_map.json",
        "method_authoring_sidecar": method_root / "method_authoring_sidecar.json",
        "self_critic_report": method_root / "self_critic_report.json",
        "claim_evidence_report": method_root / "claim_evidence_report.json",
        "numeric_fact_report": method_root / "numeric_fact_report.json",
        "equation_support_report": method_root / "equation_support_report.json",
        "terminology_consistency_report": method_root / "terminology_consistency_report.json",
        "latex_smoke_report": method_root / "latex_smoke_report.json",
        "phase4_manifest": method_root / "phase4_manifest.json",
    }
    paths["method_authoring_prompt"].write_text(_authoring_prompt(method_evidence, claim_map), encoding="utf-8")

    if preflight_blocked_reason:
        blocked_report = Phase4BlockedReport(
            project_id=method_evidence.project_id,
            blocked_reason=preflight_blocked_reason,
            generated_prompt_artifacts=[str(paths["method_authoring_prompt"])],
        )
        _write_json(paths["phase4_blocked_report"], blocked_report.model_dump(mode="json"))
        manifest = Phase4Manifest(
            project_id=method_evidence.project_id,
            mode="blocked_with_insufficient_analysis",
            llm_available=False,
            blocked_reason=preflight_blocked_reason,
            outputs=_artifact_hashes(paths, existing_only=True, exclude={"phase4_manifest"}),
            llm_call_logs=[],
            validator_reports=[],
        )
        _write_json(paths["phase4_manifest"], manifest.model_dump(mode="json"))
        return None, None, paths

    outline = _outline_scaffold(method_evidence)
    terminology = _terminology_scaffold(method_evidence)
    markdown = build_method_draft_markdown(method_evidence, claim_map)
    latex = build_method_draft_tex(method_evidence, claim_map)
    claim_map_output = _draft_claim_map_scaffold(outline)
    claim_map_output = _normalize_draft_claim_map(
        draft_claim_map=claim_map_output,
        outline=outline,
        method_evidence=method_evidence,
        claim_map=claim_map,
    )
    sidecar = MethodAuthoringSidecar(
        draft_version=1,
        method_outline_path="paper/method/method_outline.json",
        terminology_table_path="paper/method/terminology_table.json",
        draft_claim_map_path="paper/method/draft_claim_map.json",
        paragraphs=[
            MethodAuthoringSidecarParagraph(
                paragraph_id=paragraph.paragraph_id,
                claim_ids=paragraph.claim_ids,
                evidence_span_ids=paragraph.evidence_span_ids,
                llm_call_id="deterministic-authoring",
                validator_status="pending",
            )
            for paragraph in claim_map_output.paragraphs
        ],
    )
    claim_report, numeric_report, equation_report, terminology_report, latex_report = _run_quality_checks(
        method_evidence=method_evidence,
        terminology=terminology,
        markdown=markdown,
        latex=latex,
        alignment=alignment,
        draft_claim_map=claim_map_output,
    )
    _write_json(paths["method_outline"], outline.model_dump(mode="json"))
    _write_json(paths["terminology_table"], terminology.model_dump(mode="json"))
    paths["method_draft_md"].write_text(markdown, encoding="utf-8")
    paths["method_draft_tex"].write_text(latex, encoding="utf-8")
    _write_json(paths["draft_claim_map"], claim_map_output.model_dump(mode="json"))
    _write_json(paths["method_authoring_sidecar"], sidecar.model_dump(mode="json"))
    _write_json(paths["self_critic_report"], SelfCriticReport().model_dump(mode="json"))
    _write_json(paths["claim_evidence_report"], claim_report)
    _write_json(paths["numeric_fact_report"], numeric_report.model_dump(mode="json"))
    _write_json(paths["equation_support_report"], equation_report.model_dump())
    _write_json(paths["terminology_consistency_report"], terminology_report.model_dump())
    _write_json(paths["latex_smoke_report"], latex_report)
    manifest = Phase4Manifest(
        project_id=method_evidence.project_id,
        mode="deterministic-authoring",
        llm_available=False,
        outputs=_artifact_hashes(paths, existing_only=True, exclude={"phase4_manifest", "phase4_blocked_report"}),
        llm_call_logs=[],
        validator_reports=[
            str(paths["claim_evidence_report"]),
            str(paths["numeric_fact_report"]),
            str(paths["equation_support_report"]),
            str(paths["terminology_consistency_report"]),
            str(paths["latex_smoke_report"]),
        ],
    )
    _write_json(paths["phase4_manifest"], manifest.model_dump(mode="json"))
    return markdown, latex, paths

def _outline_scaffold(method_evidence: MethodEvidence) -> MethodOutline:
    ordered_stages = _ordered_stages_for_authoring(method_evidence)
    sections = [
        MethodOutlineParagraph(
            paragraph_id="P1",
            purpose="Overview of the evidence-backed method.",
            stage_ids=[stage.stage_id for stage in ordered_stages],
            mechanism_ids=[],
            claim_ids=[contract.claim_id for contract in method_evidence.claim_contracts if contract.support_status.value != "unsupported"][:3],
            evidence_span_ids=[],
        )
    ]
    for index, stage in enumerate(ordered_stages, start=2):
        stage_frozen_mechanisms = [
            mechanism
            for mechanism in method_evidence.frozen_mechanisms
            if mechanism.parent_stage_id == stage.stage_id
        ]
        stage_frozen_mechanism_ids = [mechanism.mechanism_id for mechanism in stage_frozen_mechanisms if mechanism.mechanism_id]
        stage_method_mechanism_ids = [mechanism.mechanism_id for mechanism in stage.mechanisms if mechanism.mechanism_id]
        stage_mechanism_ids = _dedupe(stage_frozen_mechanism_ids + stage_method_mechanism_ids)
        stage_evidence_ids = _dedupe(
            [eid for mechanism in stage_frozen_mechanisms for eid in mechanism.evidence_span_ids]
            + [eid for mechanism in stage.mechanisms for eid in mechanism.evidence_ids]
        )
        sections.append(
            MethodOutlineParagraph(
                paragraph_id=f"P{index}",
                purpose=f"Describe {stage.name}.",
                stage_ids=[stage.stage_id],
                mechanism_ids=stage_mechanism_ids,
                claim_ids=[contract.claim_id for contract in method_evidence.claim_contracts if stage.name in contract.claim_intent],
                evidence_span_ids=stage_evidence_ids,
            )
        )
    return MethodOutline(
        sections=sections,
        author_logic_order=method_evidence.author_logic_mapping.author_proposed_flow
        or method_evidence.author_logic_mapping.author_supported_flow,
    )


def _ordered_stages_for_authoring(method_evidence: MethodEvidence) -> list:
    stages = list(method_evidence.stages)
    if not stages:
        return stages
    desired = method_evidence.author_logic_mapping.author_proposed_flow or method_evidence.author_logic_mapping.author_supported_flow
    if not desired:
        return stages
    by_normalized = {_normalize_story_name(stage.name): stage for stage in stages}
    ordered = []
    for story_item in desired:
        stage = by_normalized.get(_normalize_story_name(story_item))
        if stage and stage not in ordered:
            ordered.append(stage)
    for stage in stages:
        if stage not in ordered:
            ordered.append(stage)
    return ordered


def _normalize_story_name(value: str) -> str:
    lowered = value.lower().replace("_", " ").replace("-", " ")
    return " ".join(lowered.split())


def _terminology_scaffold(method_evidence: MethodEvidence) -> TerminologyTable:
    terms: list[TerminologyTerm] = []
    for index, stage in enumerate(method_evidence.stages, start=1):
        terms.append(
            TerminologyTerm(
                term_id=f"TERM-STAGE-{index}",
                canonical=stage.name,
                term_type="stage",
                source_ids=[stage.stage_id],
                evidence_span_ids=_dedupe([eid for mechanism in stage.mechanisms for eid in mechanism.evidence_ids]),
            )
        )
    for index, mechanism in enumerate(method_evidence.frozen_mechanisms, start=1):
        terms.append(
            TerminologyTerm(
                term_id=f"TERM-MECH-{index}",
                canonical=mechanism.mechanism_name,
                term_type="mechanism",
                source_ids=[mechanism.mechanism_id],
                evidence_span_ids=mechanism.evidence_span_ids,
            )
        )
    return TerminologyTable(terms=terms)


def _draft_claim_map_scaffold(outline: MethodOutline) -> DraftClaimMap:
    return DraftClaimMap(
        paragraphs=[
            {
                "paragraph_id": paragraph.paragraph_id,
                "claim_ids": paragraph.claim_ids,
                "mechanism_ids": paragraph.mechanism_ids,
                "evidence_span_ids": paragraph.evidence_span_ids,
            }
            for paragraph in outline.sections
        ]
    )


def _normalize_draft_claim_map(
    *,
    draft_claim_map: DraftClaimMap,
    outline: MethodOutline,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
) -> DraftClaimMap:
    contracts = list(method_evidence.claim_contracts)
    known_claim_ids = {contract.claim_id for contract in contracts}
    max_claim_ids_per_paragraph = 6
    max_evidence_ids_per_paragraph = 80
    max_mechanism_ids_per_paragraph = 8
    supported_claim_ids = [
        contract.claim_id
        for contract in contracts
        if contract.claim_id in known_claim_ids and contract.support_status.value != "unsupported"
    ] or [contract.claim_id for contract in contracts if contract.claim_id in known_claim_ids]
    known_mechanism_ids = {
        mechanism.mechanism_id
        for mechanism in method_evidence.frozen_mechanisms
        if mechanism.mechanism_id
    }
    mechanism_evidence: dict[str, list[str]] = {}
    stage_mechanisms_by_stage: dict[str, list[str]] = {stage.stage_id: [] for stage in method_evidence.stages}
    for stage in method_evidence.stages:
        for mechanism in stage.mechanisms:
            if not mechanism.mechanism_id:
                continue
            known_mechanism_ids.add(mechanism.mechanism_id)
            stage_mechanisms_by_stage.setdefault(stage.stage_id, []).append(mechanism.mechanism_id)
            mechanism_evidence.setdefault(mechanism.mechanism_id, [])
            mechanism_evidence[mechanism.mechanism_id].extend(
                [evidence_id for evidence_id in mechanism.evidence_ids if evidence_id]
            )
    for mechanism in method_evidence.frozen_mechanisms:
        if not mechanism.mechanism_id:
            continue
        mechanism_evidence.setdefault(mechanism.mechanism_id, [])
        mechanism_evidence[mechanism.mechanism_id].extend(
            [evidence_id for evidence_id in mechanism.evidence_span_ids if evidence_id]
        )
    mechanism_evidence = {
        mechanism_id: _dedupe(evidence_ids)
        for mechanism_id, evidence_ids in mechanism_evidence.items()
    }
    stage_mechanisms_by_stage = {
        stage_id: _dedupe(mechanism_ids)
        for stage_id, mechanism_ids in stage_mechanisms_by_stage.items()
    }
    mechanism_to_stage: dict[str, str] = {
        mechanism_id: stage_id
        for stage_id, mechanism_ids in stage_mechanisms_by_stage.items()
        for mechanism_id in mechanism_ids
        if mechanism_id
    }
    for mechanism in method_evidence.frozen_mechanisms:
        if mechanism.mechanism_id and mechanism.parent_stage_id:
            mechanism_to_stage.setdefault(mechanism.mechanism_id, mechanism.parent_stage_id)
    known_evidence_ids = {
        evidence_id
        for evidence_ids in mechanism_evidence.values()
        for evidence_id in evidence_ids
    }
    known_evidence_ids.update(
        {
            evidence_id
            for contract in contracts
            for evidence_id in contract.evidence_span_ids
            if evidence_id
        }
    )

    claim_to_evidence = {
        contract.claim_id: [evidence_id for evidence_id in contract.evidence_span_ids if evidence_id in known_evidence_ids]
        for contract in contracts
        if contract.claim_id in known_claim_ids
    }
    claim_to_mechanisms: dict[str, list[str]] = {claim_id: [] for claim_id in known_claim_ids}
    mechanism_to_claims: dict[str, list[str]] = {mechanism_id: [] for mechanism_id in known_mechanism_ids}
    for claim_entry in claim_map.claims:
        claim_id = claim_entry.claim_id
        if claim_id not in known_claim_ids:
            continue
        for mechanism_id in claim_entry.mechanism_ids:
            if mechanism_id not in known_mechanism_ids:
                continue
            claim_to_mechanisms.setdefault(claim_id, []).append(mechanism_id)
            mechanism_to_claims.setdefault(mechanism_id, []).append(claim_id)
    claim_to_mechanisms = {claim_id: _dedupe(values) for claim_id, values in claim_to_mechanisms.items()}
    mechanism_to_claims = {mechanism_id: _dedupe(values) for mechanism_id, values in mechanism_to_claims.items()}

    stage_names = {stage.stage_id: stage.name for stage in method_evidence.stages}
    claim_ids_by_stage: dict[str, list[str]] = {stage_id: [] for stage_id in stage_names}
    for contract in contracts:
        claim_id = contract.claim_id
        if claim_id not in known_claim_ids:
            continue
        normalized_intent = _normalize_story_name(contract.claim_intent)
        for stage_id, stage_name in stage_names.items():
            if _normalize_story_name(stage_name) in normalized_intent:
                claim_ids_by_stage[stage_id].append(claim_id)
    claim_ids_by_stage = {stage_id: _dedupe(values) for stage_id, values in claim_ids_by_stage.items()}

    outline_by_paragraph = {paragraph.paragraph_id: paragraph for paragraph in outline.sections}
    source_paragraphs = list(draft_claim_map.paragraphs) or _draft_claim_map_scaffold(outline).paragraphs
    normalized_paragraphs: list[dict] = []
    seen_paragraph_ids: set[str] = set()

    for index, paragraph in enumerate(source_paragraphs, start=1):
        paragraph_id = paragraph.paragraph_id or f"P{index}"
        seen_paragraph_ids.add(paragraph_id)
        outline_paragraph = outline_by_paragraph.get(paragraph_id)

        mechanism_ids = _dedupe(
            [mechanism_id for mechanism_id in paragraph.mechanism_ids if mechanism_id in known_mechanism_ids]
            + (
                [
                    mechanism_id
                    for mechanism_id in (outline_paragraph.mechanism_ids if outline_paragraph else [])
                    if mechanism_id in known_mechanism_ids
                ]
            )
        )[:max_mechanism_ids_per_paragraph]
        evidence_ids = _dedupe(
            [evidence_id for evidence_id in paragraph.evidence_span_ids if evidence_id in known_evidence_ids]
            + (
                [
                    evidence_id
                    for evidence_id in (outline_paragraph.evidence_span_ids if outline_paragraph else [])
                    if evidence_id in known_evidence_ids
                ]
            )
            + [evidence_id for mechanism_id in mechanism_ids for evidence_id in mechanism_evidence.get(mechanism_id, [])]
        )[:max_evidence_ids_per_paragraph]

        claim_ids = _dedupe([claim_id for claim_id in paragraph.claim_ids if claim_id in known_claim_ids])
        if not claim_ids:
            claim_candidates: list[str] = []
            if outline_paragraph:
                outline_claims = [claim_id for claim_id in outline_paragraph.claim_ids if claim_id in known_claim_ids]
                claim_candidates.extend(outline_claims)
            if not claim_candidates:
                for mechanism_id in mechanism_ids:
                    claim_candidates.extend(mechanism_to_claims.get(mechanism_id, []))
            if not claim_candidates and evidence_ids:
                evidence_set = set(evidence_ids)
                for claim_id in supported_claim_ids:
                    claim_evidence = set(claim_to_evidence.get(claim_id, []))
                    if claim_evidence and claim_evidence.intersection(evidence_set):
                        claim_candidates.append(claim_id)
            if not claim_candidates and outline_paragraph:
                for stage_id in outline_paragraph.stage_ids:
                    claim_candidates.extend(claim_ids_by_stage.get(stage_id, []))
            if not claim_candidates and supported_claim_ids:
                claim_candidates.append(supported_claim_ids[0])
            claim_ids = _dedupe(claim_candidates)[:max_claim_ids_per_paragraph]

        if not mechanism_ids:
            mechanism_ids = _dedupe(
                [mechanism_id for claim_id in claim_ids for mechanism_id in claim_to_mechanisms.get(claim_id, [])]
            )[:max_mechanism_ids_per_paragraph]
            if not mechanism_ids and outline_paragraph:
                mechanism_ids = _dedupe(
                    [
                        mechanism_id
                        for mechanism_id in outline_paragraph.mechanism_ids
                        if mechanism_id in known_mechanism_ids
                    ]
                )[:max_mechanism_ids_per_paragraph]
            if not mechanism_ids and outline_paragraph:
                mechanism_ids = _dedupe(
                    [
                        mechanism_id
                        for stage_id in outline_paragraph.stage_ids
                        for mechanism_id in stage_mechanisms_by_stage.get(stage_id, [])
                        if mechanism_id in known_mechanism_ids
                    ]
                )[:max_mechanism_ids_per_paragraph]

        if not evidence_ids:
            evidence_ids = _dedupe(
                [evidence_id for claim_id in claim_ids for evidence_id in claim_to_evidence.get(claim_id, [])]
            )[:max_evidence_ids_per_paragraph]
            if not evidence_ids:
                evidence_ids = _dedupe(
                    [evidence_id for mechanism_id in mechanism_ids for evidence_id in mechanism_evidence.get(mechanism_id, [])]
                )[:max_evidence_ids_per_paragraph]
            if not evidence_ids and known_evidence_ids:
                evidence_ids = [next(iter(sorted(known_evidence_ids)))]

        normalized_paragraphs.append(
            {
                "paragraph_id": paragraph_id,
                "claim_ids": claim_ids,
                "mechanism_ids": mechanism_ids,
                "evidence_span_ids": evidence_ids,
            }
        )

    for outline_paragraph in outline.sections:
        if outline_paragraph.paragraph_id in seen_paragraph_ids:
            continue
        fallback_claim_ids = _dedupe(
            [claim_id for claim_id in outline_paragraph.claim_ids if claim_id in known_claim_ids]
            or supported_claim_ids[:1]
        )[:max_claim_ids_per_paragraph]
        fallback_mechanism_ids = _dedupe(
            [
                mechanism_id
                for mechanism_id in outline_paragraph.mechanism_ids
                if mechanism_id in known_mechanism_ids
            ]
        )[:max_mechanism_ids_per_paragraph]
        if not fallback_mechanism_ids:
            fallback_mechanism_ids = _dedupe(
                [
                    mechanism_id
                    for stage_id in outline_paragraph.stage_ids
                    for mechanism_id in stage_mechanisms_by_stage.get(stage_id, [])
                    if mechanism_id in known_mechanism_ids
                ]
            )[:max_mechanism_ids_per_paragraph]
        fallback_evidence_ids = _dedupe(
            [
                evidence_id
                for evidence_id in outline_paragraph.evidence_span_ids
                if evidence_id in known_evidence_ids
            ]
            or [evidence_id for claim_id in fallback_claim_ids for evidence_id in claim_to_evidence.get(claim_id, [])]
            or [evidence_id for mechanism_id in fallback_mechanism_ids for evidence_id in mechanism_evidence.get(mechanism_id, [])]
        )[:max_evidence_ids_per_paragraph]
        if not fallback_evidence_ids and known_evidence_ids:
            fallback_evidence_ids = [next(iter(sorted(known_evidence_ids)))]
        normalized_paragraphs.append(
            {
                "paragraph_id": outline_paragraph.paragraph_id,
                "claim_ids": fallback_claim_ids,
                "mechanism_ids": fallback_mechanism_ids,
                "evidence_span_ids": fallback_evidence_ids,
            }
        )

    covered_stage_ids = {
        mechanism_to_stage.get(mechanism_id, "")
        for paragraph in normalized_paragraphs
        for mechanism_id in paragraph["mechanism_ids"]
        if mechanism_to_stage.get(mechanism_id, "")
    }
    existing_paragraph_ids = {paragraph["paragraph_id"] for paragraph in normalized_paragraphs}
    next_paragraph_index = len(normalized_paragraphs) + 1
    for stage in method_evidence.stages:
        if stage.stage_id in covered_stage_ids:
            continue
        stage_mechanism_ids = _dedupe(
            [mechanism_id for mechanism_id in stage_mechanisms_by_stage.get(stage.stage_id, []) if mechanism_id in known_mechanism_ids]
        )[:max_mechanism_ids_per_paragraph]
        if not stage_mechanism_ids:
            continue
        fallback_claim_ids = _dedupe(claim_ids_by_stage.get(stage.stage_id, []) or supported_claim_ids[:1])[:max_claim_ids_per_paragraph]
        fallback_evidence_ids = _dedupe(
            [evidence_id for mechanism_id in stage_mechanism_ids for evidence_id in mechanism_evidence.get(mechanism_id, [])]
            or [evidence_id for claim_id in fallback_claim_ids for evidence_id in claim_to_evidence.get(claim_id, [])]
        )[:max_evidence_ids_per_paragraph]
        if not fallback_evidence_ids and known_evidence_ids:
            fallback_evidence_ids = [next(iter(sorted(known_evidence_ids)))]
        paragraph_id = f"P{next_paragraph_index}"
        while paragraph_id in existing_paragraph_ids:
            next_paragraph_index += 1
            paragraph_id = f"P{next_paragraph_index}"
        normalized_paragraphs.append(
            {
                "paragraph_id": paragraph_id,
                "claim_ids": fallback_claim_ids,
                "mechanism_ids": stage_mechanism_ids,
                "evidence_span_ids": fallback_evidence_ids,
            }
        )
        existing_paragraph_ids.add(paragraph_id)
        next_paragraph_index += 1

    return DraftClaimMap(paragraphs=normalized_paragraphs)


def _latex_style_instruction(style: str) -> str:
    normalized = (style or "balanced").strip().lower()
    if normalized == "implementation-faithful":
        return (
            "Writing style preference is implementation-faithful: prioritize concrete implementation behavior, "
            "explicit modules, tensors, and update flow over abstract framing."
        )
    if normalized == "paper-abstract":
        return (
            "Writing style preference is paper-abstract: emphasize conceptual method logic and concise abstraction, "
            "while keeping all claims evidence-grounded."
        )
    return (
        "Writing style preference is balanced: combine conceptual explanation with implementation-grounded details."
    )


def _latex_constraints(method_evidence: MethodEvidence) -> list[str]:
    constraints = [
        "Use section/subsection/paragraph commands.",
        "Do not introduce new claims.",
    ]
    style = method_evidence.latex_expression_preference.value
    if style == "implementation-faithful":
        constraints.append("Prefer explicit implementation-level phrasing and concrete module references.")
    elif style == "paper-abstract":
        constraints.append("Prefer concise abstract phrasing and avoid unnecessary low-level implementation digressions.")
    else:
        constraints.append("Balance abstract explanation with concrete implementation details.")
    return constraints


def _method_evidence_for_authoring(method_evidence: MethodEvidence) -> dict:
    """Build a role-aware view for generation without deleting valid evidence."""

    stage_packets = _stage_authoring_packets(method_evidence)
    return {
        "project_id": method_evidence.project_id,
        "method_name": method_evidence.method_name,
        "method_goal": method_evidence.method_goal,
        "implementation_scope": method_evidence.implementation_scope,
        "latex_expression_preference": method_evidence.latex_expression_preference.value,
        "author_logic_priority": method_evidence.author_logic_priority,
        "author_logic_mapping": method_evidence.author_logic_mapping.model_dump(mode="json"),
        "authoring_policy": {
            "primary_rule": "Write from stage_packets.primary_mechanisms and primary_evidence_ids first.",
            "supporting_rule": "Use supporting behavior/equation evidence only when it is linked to a stage, mechanism, or claim.",
            "background_rule": "Background/backbone evidence may be mentioned as implementation context, but must not be promoted to contribution unless a stage or claim explicitly binds it.",
            "excluded_rule": "Generated artifacts and pretrained asset packaging are not method evidence.",
            "overview_rule": "The overview should summarize stage logic and should not enumerate low-level backbone internals.",
        },
        "stage_packets": stage_packets,
        "frozen_mechanisms": [mechanism.model_dump(mode="json") for mechanism in method_evidence.frozen_mechanisms],
        "claim_contracts": [contract.model_dump(mode="json") for contract in method_evidence.claim_contracts],
        "behavior_patterns_by_role": _behavior_authoring_roles(method_evidence, stage_packets),
        "equation_candidates_by_role": _equation_authoring_roles(method_evidence, stage_packets),
        "architecture_parameters": [param.model_dump(mode="json") for param in method_evidence.architecture_parameters[:80]],
        "tensor_roles": [tensor.model_dump(mode="json") for tensor in method_evidence.tensor_roles[:80]],
        "writing_constraints": method_evidence.writing_constraints,
        "negative_scope": method_evidence.negative_scope,
        "alignment_notes": method_evidence.alignment_notes,
        "excluded_sources": [source.model_dump(mode="json") for source in method_evidence.excluded_sources],
    }


def _stage_authoring_packets(method_evidence: MethodEvidence) -> list[dict]:
    frozen_by_stage: dict[str, list] = {stage.stage_id: [] for stage in method_evidence.stages}
    for mechanism in method_evidence.frozen_mechanisms:
        if mechanism.parent_stage_id:
            frozen_by_stage.setdefault(mechanism.parent_stage_id, []).append(mechanism)

    claim_ids_by_stage: dict[str, list[str]] = {stage.stage_id: [] for stage in method_evidence.stages}
    for contract in method_evidence.claim_contracts:
        normalized_intent = _normalize_story_name(contract.claim_intent)
        for stage in method_evidence.stages:
            if _normalize_story_name(stage.name) in normalized_intent:
                claim_ids_by_stage.setdefault(stage.stage_id, []).append(contract.claim_id)

    packets: list[dict] = []
    for stage in _ordered_stages_for_authoring(method_evidence):
        stage_mechanisms = list(stage.mechanisms)
        frozen_mechanisms = frozen_by_stage.get(stage.stage_id, [])
        primary_evidence_ids = _dedupe(
            [evidence_id for mechanism in stage_mechanisms for evidence_id in mechanism.evidence_ids]
            + [evidence_id for mechanism in frozen_mechanisms for evidence_id in mechanism.evidence_span_ids]
        )
        primary_mechanism_ids = _dedupe(
            [mechanism.mechanism_id for mechanism in frozen_mechanisms if mechanism.mechanism_id]
            + [mechanism.mechanism_id for mechanism in stage_mechanisms if mechanism.mechanism_id]
        )
        packets.append(
            {
                "stage_id": stage.stage_id,
                "name": stage.name,
                "purpose": stage.purpose,
                "inputs": stage.inputs,
                "outputs": stage.outputs,
                "primary_mechanism_ids": primary_mechanism_ids,
                "primary_evidence_ids": primary_evidence_ids,
                "claim_ids": _dedupe(claim_ids_by_stage.get(stage.stage_id, [])),
                "modules": [module.model_dump(mode="json") for module in stage.modules],
                "mechanisms": [mechanism.model_dump(mode="json") for mechanism in stage_mechanisms],
                "frozen_mechanisms": [mechanism.model_dump(mode="json") for mechanism in frozen_mechanisms],
                "writing_instruction": (
                    "Use this packet as the main source for the stage paragraph. "
                    "Do not replace this stage's author-facing purpose with unbound backbone internals."
                ),
            }
        )
    return packets


def _behavior_authoring_roles(method_evidence: MethodEvidence, stage_packets: list[dict]) -> dict[str, list[dict]]:
    stage_context = _stage_context_from_packets(stage_packets)
    grouped: dict[str, list[dict]] = {"primary": [], "supporting": [], "background": [], "excluded": []}
    for pattern in method_evidence.behavior_patterns:
        role, stage_ids, reason = _classify_evidence_for_authoring(
            path=pattern.path,
            evidence_ids=pattern.evidence_ids,
            stage_context=stage_context,
        )
        item = pattern.model_dump(mode="json")
        item["authoring_role"] = role
        item["stage_ids"] = stage_ids
        item["role_reason"] = reason
        grouped[role].append(item)
    return {role: items[:80] for role, items in grouped.items()}


def _equation_authoring_roles(method_evidence: MethodEvidence, stage_packets: list[dict]) -> dict[str, list[dict]]:
    stage_context = _stage_context_from_packets(stage_packets)
    grouped: dict[str, list[dict]] = {"primary": [], "supporting": [], "background": [], "excluded": []}
    for equation in method_evidence.equation_candidates:
        role, stage_ids, reason = _classify_evidence_for_authoring(
            path="",
            evidence_ids=equation.evidence_ids,
            stage_context=stage_context,
        )
        if not equation.evidence_ids and role != "excluded":
            role = "background"
            reason = "No direct stage/claim evidence binding; use only if a claim contract explicitly requires it."
        item = equation.model_dump(mode="json")
        item["authoring_role"] = role
        item["stage_ids"] = stage_ids
        item["role_reason"] = reason
        grouped[role].append(item)
    return {role: items[:80] for role, items in grouped.items()}


def _stage_context_from_packets(stage_packets: list[dict]) -> dict:
    evidence_to_stage: dict[str, list[str]] = {}
    path_to_stage: dict[str, list[str]] = {}
    for packet in stage_packets:
        stage_id = str(packet.get("stage_id") or "")
        for evidence_id in packet.get("primary_evidence_ids", []):
            evidence_to_stage.setdefault(str(evidence_id), []).append(stage_id)
        for module in packet.get("modules", []):
            path = _normalize_path(str(module.get("path") or ""))
            if path:
                path_to_stage.setdefault(path, []).append(stage_id)
    return {
        "evidence_to_stage": {key: _dedupe(value) for key, value in evidence_to_stage.items()},
        "path_to_stage": {key: _dedupe(value) for key, value in path_to_stage.items()},
    }


def _classify_evidence_for_authoring(*, path: str, evidence_ids: list[str], stage_context: dict) -> tuple[str, list[str], str]:
    normalized_path = _normalize_path(path)
    if _is_generated_or_asset_path(normalized_path):
        return "excluded", [], "Generated artifact or pretrained asset packaging; not method evidence."
    evidence_to_stage = stage_context["evidence_to_stage"]
    path_to_stage = stage_context["path_to_stage"]
    stage_ids = _dedupe(
        [stage_id for evidence_id in evidence_ids for stage_id in evidence_to_stage.get(evidence_id, [])]
        + [
            stage_id
            for module_path, stage_ids_for_path in path_to_stage.items()
            if normalized_path
            and (
                normalized_path == module_path
                or normalized_path.endswith("/" + module_path)
                or module_path.endswith("/" + normalized_path)
            )
            for stage_id in stage_ids_for_path
        ]
    )
    if stage_ids and evidence_ids:
        return "primary", stage_ids, "Evidence IDs are directly bound to stage mechanisms."
    if stage_ids:
        return "supporting", stage_ids, "Path is bound to a stage module, but evidence IDs are not directly mechanism-bound."
    return "background", [], "No direct author-stage binding; keep as implementation/backbone context only."


def _is_generated_or_asset_path(path: str) -> bool:
    lowered = path.lower()
    return (
        "swark-output/" in lowered
        or "/code2paper_agent/output/" in lowered
        or lowered.startswith("code2paper_agent/output/")
        or "/.codeboarding/" in lowered
        or lowered.startswith(".codeboarding/")
        or "pretrained_weight/" in lowered
        or lowered.endswith((".safetensors", ".bin", ".pt", ".pth", ".ckpt"))
    )


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _authoring_prompt(method_evidence: MethodEvidence, claim_map: ClaimEvidenceMap) -> str:
    return "\n".join(
        [
            "# Phase 4 Method Authoring Prompt",
            "",
            "Use the frozen Method Evidence, claim contracts, and negative scope to author the Method section.",
            "Prioritize the Authoring View stage packets. Treat background evidence as context, not as contribution.",
            "",
            f"- latex_expression_preference: {method_evidence.latex_expression_preference.value}",
            "",
            "## Authoring View",
            "```json",
            json.dumps(_method_evidence_for_authoring(method_evidence), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Claim Evidence Map",
            "```json",
            json.dumps(claim_map.model_dump(mode="json"), ensure_ascii=False, indent=2),
            "```",
        ]
    )


def _run_quality_checks(
    *,
    method_evidence: MethodEvidence,
    terminology: TerminologyTable,
    markdown: str,
    latex: str,
    alignment: CodeAlignmentIR | None,
    draft_claim_map: DraftClaimMap,
):
    claim_report = validate_claim_evidence(
        method_evidence=method_evidence,
        draft_claim_map=draft_claim_map,
    )
    numeric_report = validate_numeric_facts(
        method_evidence=method_evidence,
        draft_markdown=markdown,
        alignment=alignment,
    )
    equation_report = validate_equation_support(
        method_evidence=method_evidence,
        draft_markdown=markdown,
        draft_latex=latex,
    )
    terminology_report = validate_terminology_consistency(
        terminology_table=terminology,
        draft_markdown=markdown,
        draft_latex=latex,
    )
    latex_report = validate_latex_smoke(latex)
    return claim_report, numeric_report, equation_report, terminology_report, latex_report


def _artifact_hashes(paths: dict[str, Path], *, existing_only: bool, exclude: set[str]) -> dict[str, ArtifactHash]:
    result = {}
    for name, path in paths.items():
        if name in exclude:
            continue
        if existing_only and not path.exists():
            continue
        result[name] = ArtifactHash(path=str(path), hash=hash_file(path))
    return result


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_markdown_grounding_comments(
    *,
    markdown: str,
    draft_claim_map: DraftClaimMap,
    method_evidence: MethodEvidence,
) -> str:
    lines = markdown.splitlines()
    paragraphs = list(draft_claim_map.paragraphs)
    mechanism_to_stage = {
        mechanism.mechanism_id: mechanism.parent_stage_id
        for mechanism in method_evidence.frozen_mechanisms
    }
    normalized: list[str] = []
    in_math = False
    paragraph_index = 0
    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped == "$$":
            in_math = not in_math
            normalized.append(line)
            continue
        if in_math:
            normalized.append(line)
            continue
        if stripped.startswith("<!-- c2p:"):
            if paragraph_index < len(paragraphs):
                normalized.append(_grounding_comment_for_paragraph(paragraphs[paragraph_index], mechanism_to_stage))
            else:
                normalized.append(line)
            continue
        if _is_markdown_paragraph_line(stripped):
            if not _last_non_empty_line(normalized).startswith("<!-- c2p:"):
                if paragraph_index < len(paragraphs):
                    normalized.append(_grounding_comment_for_paragraph(paragraphs[paragraph_index], mechanism_to_stage))
                else:
                    normalized.append("<!-- c2p: stage=ALL; mechanisms=none; evidence=none; confidence=low -->")
            normalized.append(line)
            paragraph_index += 1
            continue
        normalized.append(line)
    return "\n".join(normalized).rstrip() + "\n"


def _grounding_comment_for_paragraph(
    paragraph: object,
    mechanism_to_stage: dict[str, str],
) -> str:
    mechanisms = _dedupe([mechanism_id for mechanism_id in paragraph.mechanism_ids if mechanism_id])
    evidences = _dedupe([evidence_id for evidence_id in paragraph.evidence_span_ids if evidence_id])
    stage_ids = _dedupe([mechanism_to_stage.get(mechanism_id, "") for mechanism_id in mechanisms if mechanism_to_stage.get(mechanism_id, "")])
    stage_id = "ALL" if len(stage_ids) != 1 else stage_ids[0]
    mechanism_text = ",".join(mechanisms) if mechanisms else "none"
    evidence_text = ",".join(evidences) if evidences else "none"
    confidence = "high" if evidences else "low"
    return (
        f"<!-- c2p: stage={stage_id}; mechanisms={mechanism_text}; "
        f"evidence={evidence_text}; confidence={confidence} -->"
    )


def _is_markdown_paragraph_line(line: str) -> bool:
    if not line:
        return False
    if line.startswith("#"):
        return False
    if line.startswith("- "):
        return False
    if line.startswith("<!--"):
        return False
    if line.startswith("$$"):
        return False
    return True


def _last_non_empty_line(lines: list[str]) -> str:
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return ""


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
