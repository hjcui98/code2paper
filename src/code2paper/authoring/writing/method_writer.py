"""Phase 5 method draft writer."""

from __future__ import annotations

import json
from pathlib import Path
import re

from code2paper.core.schemas import (
    ClaimEvidenceMap,
    ClaimEvidenceItem,
    ConfidenceLevel,
    MethodEvidence,
    MethodModule,
    MethodStageEvidence,
    ModuleCategory,
    SupportStatus,
)
from code2paper.authoring.writing.md_formatter import grounding_comment, normalize_markdown
from code2paper.authoring.writing.section_planner import plan_method_sections
from code2paper.authoring.writing.tex_formatter import format_method_draft_tex


def build_method_draft_markdown(
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap | None = None,
    supplemental_equations_tex: str = "",
) -> str:
    """Generate an evidence-grounded Markdown method draft."""

    if _is_authoring_projection_input(method_evidence):
        return _build_projection_only_draft(method_evidence, claim_map or ClaimEvidenceMap())

    lines: list[str] = ["# Method", ""]
    sections = {section.key: section for section in plan_method_sections(method_evidence)}
    all_mechanisms = [mechanism for stage in method_evidence.stages for mechanism in stage.mechanisms]
    all_mechanism_ids = [mechanism.mechanism_id for mechanism in all_mechanisms]
    all_evidence_ids = _dedupe([evidence_id for mechanism in all_mechanisms for evidence_id in mechanism.evidence_ids])
    overview_confidence = _combined_confidence([mechanism.confidence for mechanism in all_mechanisms])

    lines.extend(
        [
            f"## {sections['overview'].title}",
            grounding_comment(
                stage_id="ALL",
                mechanism_ids=all_mechanism_ids,
                evidence_ids=all_evidence_ids,
                confidence=overview_confidence,
            ),
            (
                _goal_sentence(method_evidence)
                + " "
                + _overview_context_sentence(method_evidence, claim_map)
                + _stage_count_sentence(method_evidence)
            ),
            "",
            f"## {sections['pipeline'].title}",
        ]
    )

    deferred_setup_notes: list[tuple[MethodStageEvidence, list, list[str], list[str], str]] = []
    packet_by_stage = {
        str(packet.get("stage_id") or ""): packet
        for packet in method_evidence.stage_packets
        if isinstance(packet, dict)
    }
    seen_stage_signatures: set[tuple[str, tuple[str, ...]]] = set()
    for stage in method_evidence.stages:
        stage_mechanisms = [mechanism for mechanism in stage.mechanisms if mechanism.support_status != SupportStatus.UNSUPPORTED]
        if not stage_mechanisms:
            continue
        packet = packet_by_stage.get(stage.stage_id)
        evidence_ids = _dedupe(
            _packet_evidence_ids(packet)
            or [evidence_id for mechanism in stage_mechanisms for evidence_id in mechanism.evidence_ids]
        )
        mechanism_ids = [mechanism.mechanism_id for mechanism in stage_mechanisms]
        confidence = _combined_confidence([mechanism.confidence for mechanism in stage_mechanisms])
        stage_signature = (
            _normalize_text(stage.purpose),
            tuple(sorted(evidence_ids)),
        )
        if (
            _is_low_priority_setup_stage(stage, packet, stage_mechanisms)
            or stage_signature in seen_stage_signatures
        ) and len(method_evidence.stages) > 1:
            deferred_setup_notes.append((stage, stage_mechanisms, mechanism_ids, evidence_ids, confidence))
            continue
        seen_stage_signatures.add(stage_signature)
        stage_paragraph = (
            _stage_packet_paragraph(stage, packet)
            if packet
            else _fallback_stage_paragraph(stage, stage_mechanisms)
        )
        lines.extend(
            [
                grounding_comment(
                    stage_id=stage.stage_id,
                    mechanism_ids=mechanism_ids,
                    evidence_ids=evidence_ids,
                    confidence=confidence,
                ),
                stage_paragraph,
                "",
            ]
        )

    objective_lines = _objective_detail_lines(method_evidence, supplemental_equations_tex=supplemental_equations_tex)
    if objective_lines:
        lines.extend(["## Objective and Optimization"])
        lines.extend(objective_lines)

    distinguishing_lines = _distinguishing_mechanism_lines(method_evidence)
    if distinguishing_lines:
        lines.extend(["## Distinguishing Mechanisms"])
        lines.extend(distinguishing_lines)

    component_paragraph = _core_component_paragraph(method_evidence)
    if component_paragraph:
        lines.extend([f"## {sections['components'].title}"])
        lines.extend(
            [
                grounding_comment(
                    stage_id="ALL",
                    mechanism_ids=all_mechanism_ids,
                    evidence_ids=all_evidence_ids,
                    confidence=overview_confidence,
                ),
                component_paragraph,
                "",
            ]
        )

    detail_lines = _mechanism_detail_lines(method_evidence)
    if detail_lines:
        lines.extend(["## Code-Backed Mechanism Details"])
        lines.extend(detail_lines)

    for stage, _stage_mechanisms, mechanism_ids, evidence_ids, confidence in deferred_setup_notes:
        if not evidence_ids:
            continue
        lines.extend(
            [
                grounding_comment(
                    stage_id=stage.stage_id,
                    mechanism_ids=mechanism_ids,
                    evidence_ids=evidence_ids,
                    confidence=confidence,
                ),
                (
                    f"{stage.name} is treated as supporting setup for the method narrative: "
                    f"{_lower_first(_rstrip_period(_clean_logic(stage.purpose)))}. "
                    "It is kept separate from the innovation-bearing mechanism description."
                ),
                "",
            ]
        )

    note_paragraphs = _implementation_notes(method_evidence, claim_map)
    if note_paragraphs:
        lines.extend([f"## {sections['notes'].title}"])
        for paragraph, mechanism_ids, evidence_ids, confidence in note_paragraphs:
            lines.extend(
                [
                    grounding_comment(
                        stage_id="ALL",
                        mechanism_ids=mechanism_ids,
                        evidence_ids=evidence_ids,
                        confidence=confidence,
                    ),
                    paragraph,
                    "",
                ]
            )

    return normalize_markdown(lines)


def _is_authoring_projection_input(method_evidence: MethodEvidence) -> bool:
    return "The projection is the writer's only positive method-fact input." in method_evidence.writing_constraints


def _build_projection_only_draft(method_evidence: MethodEvidence, claim_map: ClaimEvidenceMap) -> str:
    """Conservative fallback whose factual sentences are exactly projected claims."""

    claim_by_id = {claim.claim_id: claim for claim in claim_map.claims}
    emitted: set[str] = set()
    lines: list[str] = ["# Method", ""]
    for packet in method_evidence.stage_packets:
        claim_ids = [str(item) for item in packet.get("claim_ids", []) if str(item) in claim_by_id]
        claim_ids = [claim_id for claim_id in claim_ids if claim_id not in emitted]
        if not claim_ids:
            continue
        lines.extend([f"## {str(packet.get('name') or 'Method stage')}"])
        for claim_id in claim_ids:
            claim = claim_by_id[claim_id]
            sentence = claim.claim_text.strip().rstrip(".")
            if claim.caveats:
                sentence += "; " + "; ".join(item.strip().rstrip(".") for item in claim.caveats if item.strip())
            lines.extend(
                [
                    grounding_comment(
                        stage_id=str(packet.get("stage_id") or "ALL"),
                        mechanism_ids=[],
                        evidence_ids=claim.evidence_ids,
                        confidence="high",
                    ),
                    sentence + ".",
                    "",
                ]
            )
            emitted.add(claim_id)
    remaining = [claim for claim in claim_map.claims if claim.claim_id not in emitted]
    if remaining:
        lines.extend(["## Additional supported behavior"])
        for claim in remaining:
            sentence = claim.claim_text.strip().rstrip(".")
            if claim.caveats:
                sentence += "; " + "; ".join(item.strip().rstrip(".") for item in claim.caveats if item.strip())
            lines.extend(
                [grounding_comment(stage_id="ALL", mechanism_ids=[], evidence_ids=claim.evidence_ids, confidence="high"), sentence + ".", ""]
            )
    return normalize_markdown(lines)


def build_method_draft_tex(
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap | None = None,
    supplemental_equations_tex: str = "",
) -> str:
    return format_method_draft_tex(
        build_method_draft_markdown(method_evidence, claim_map, supplemental_equations_tex=supplemental_equations_tex)
    )


def build_method_draft_from_files(
    method_evidence_path: str | Path,
    *,
    claim_map_path: str | Path | None = None,
    supplemental_equations_tex_path: str | Path | None = None,
) -> tuple[str, str]:
    method_evidence = MethodEvidence.model_validate(json.loads(Path(method_evidence_path).read_text(encoding="utf-8")))
    claim_map = None
    if claim_map_path is not None:
        claim_map = ClaimEvidenceMap.model_validate(json.loads(Path(claim_map_path).read_text(encoding="utf-8")))
    supplemental_equations_tex = ""
    if supplemental_equations_tex_path is not None:
        supplemental_equations_tex = Path(supplemental_equations_tex_path).read_text(encoding="utf-8")
    markdown = build_method_draft_markdown(method_evidence, claim_map, supplemental_equations_tex=supplemental_equations_tex)
    return markdown, format_method_draft_tex(markdown)


def _core_component_paragraph(method_evidence: MethodEvidence) -> str:
    alias_sentence = _paper_alias_sentence(method_evidence)
    if method_evidence.stage_packets:
        labels = _dedupe(
            [
                str(action.get("role") or action.get("name") or "").strip()
                for packet in method_evidence.stage_packets
                if isinstance(packet, dict)
                for action in packet.get("module_actions", [])
                if isinstance(action, dict) and str(action.get("role") or action.get("name") or "").strip()
            ]
        )
        if labels:
            return (
                "The core method components support the following paper-facing roles: "
                + _join_human(labels)
                + ". "
                + alias_sentence
                + "Utility and experiment-support modules are not treated as method innovations."
            )
    core_modules = []
    for stage in method_evidence.stages:
        core_modules.extend(_core_modules(stage.modules))
    labels = _module_role_labels(_dedupe_modules(core_modules))
    if not labels:
        return ""
    return (
        "The core method components support the following paper-facing roles: "
        + _join_human(labels)
        + ". "
        + alias_sentence
        + "Utility and experiment-support modules are not treated as method innovations."
    )


def _paper_alias_sentence(method_evidence: MethodEvidence) -> str:
    aliases = [
        alias
        for alias in method_evidence.paper_module_aliases
        if alias.alias.strip() and alias.expansion.strip() and alias.evidence_span_ids
    ]
    if not aliases:
        return ""
    fragments = [
        f"{alias.expansion} ({alias.alias}) is retained as a paper-facing alias for {alias.matched_name or alias.matched_role}"
        for alias in aliases[:4]
    ]
    return _join_human(fragments) + ". "


def _overview_context_sentence(method_evidence: MethodEvidence, claim_map: ClaimEvidenceMap | None = None) -> str:
    overview = method_evidence.method_overview or {}
    training = str(overview.get("training_summary") or "").strip()
    architecture = str(overview.get("architecture_summary") or "").strip()
    implementation = str(overview.get("implementation_summary") or "").strip()
    selected = _sanitize_unsupported_phrases(training or architecture or implementation, claim_map)
    if not selected:
        return ""
    return _rstrip_period(selected) + ". "


def _stage_packet_paragraph(stage: MethodStageEvidence, packet: dict) -> str:
    purpose = str(packet.get("purpose") or stage.purpose).strip()
    evidence_ids = _packet_evidence_ids(packet)
    support_status = str(packet.get("support_status") or "").strip()
    if not evidence_ids and support_status != "supported":
        return (
            f"**{stage.name}.** {_default_low_evidence_stage_sentence(stage)}"
        ).strip()
    inputs_raw = _packet_list(packet, "inputs")
    outputs_raw = _packet_list(packet, "outputs")
    action_sentence = _module_action_sentence(packet)
    operation_sentence = _operation_sentence(packet)
    claim = str(packet.get("stage_claim") or "").strip()
    claim_sentence = ""
    if claim and _normalize_text(claim) != _normalize_text(purpose):
        claim_sentence = _rstrip_period(claim) + ". "
    sentences = [f"**{stage.name}.** {_clean_sentence(purpose)}"]
    if inputs_raw or outputs_raw:
        inputs = _io_phrase(inputs_raw, "the previous stage outputs")
        outputs = _io_phrase(outputs_raw, "the next stage inputs")
        sentences.append(f"It consumes {inputs} and produces {outputs}.")
    for extra in (action_sentence, operation_sentence, claim_sentence):
        if extra.strip():
            sentences.append(extra.strip())
    return " ".join(sentences).strip()


def _fallback_stage_paragraph(stage: MethodStageEvidence, stage_mechanisms: list) -> str:
    if not any(mechanism.evidence_ids for mechanism in stage_mechanisms):
        return f"**{stage.name}.** {_default_low_evidence_stage_sentence(stage)}"
    return (
        f"**{stage.name}.** {_clean_sentence(stage.purpose)} "
        f"It consumes {_io_phrase(stage.inputs, 'the previous stage outputs')} and produces "
        f"{_io_phrase(stage.outputs, 'the next stage inputs')}. "
        f"{_stage_mechanism_summary(stage, stage_mechanisms)}"
    ).strip()


def _module_action_sentence(packet: dict) -> str:
    actions = [
        action
        for action in packet.get("module_actions", [])
        if isinstance(action, dict)
        and str(action.get("support_status") or "supported") != "unsupported"
    ]
    if not actions:
        return ""
    role_fragments: list[str] = []
    logic_fragments: list[str] = []
    for action in actions[:4]:
        name = _clean_component_name(str(action.get("name") or ""))
        role = str(action.get("role") or "").strip()
        logic = _clean_logic(str(action.get("key_logic") or "").strip())
        if role and name and _normalize_text(role) != _normalize_text(name):
            role_fragments.append(f"{name} for {_role_phrase(role)}")
        elif role or name:
            role_fragments.append(role or name)
        if logic:
            logic_fragments.append(f"{name} {_lower_first(_rstrip_period(logic))}")
    if not role_fragments and not logic_fragments:
        return ""
    sentences = []
    if role_fragments:
        sentences.append("The stage uses " + _join_human(role_fragments) + ".")
    if logic_fragments:
        sentences.append(_join_human(logic_fragments) + ".")
    return " ".join(sentences) + " "


def _stage_count_sentence(method_evidence: MethodEvidence) -> str:
    stage_names = [stage.name for stage in method_evidence.stages]
    evidence_backed = [
        stage
        for stage in method_evidence.stages
        if any(mechanism.evidence_ids for mechanism in stage.mechanisms)
    ]
    if len(evidence_backed) == len(method_evidence.stages):
        return (
            f"The paper-facing method is organized into {len(stage_names)} method stages: "
            + f"{_join_human(stage_names)}."
        )
    return (
        f"The paper-facing method is organized into {len(stage_names)} stages: "
        + f"{_join_human(stage_names)}. "
        + f"{len(evidence_backed)} of these stages are linked to direct implementation evidence in this run."
    )


def _default_low_evidence_stage_sentence(stage: MethodStageEvidence) -> str:
    purpose = _clean_sentence(stage.purpose)
    if _is_author_marker_placeholder(purpose):
        return "This stage is present in the author story order, but no direct implementation evidence was linked to it in this run."
    return purpose + " The current evidence set does not link this stage to a direct implementation span."


def _clean_sentence(text: str) -> str:
    cleaned = _rstrip_period(_clean_logic(text))
    if not cleaned:
        return ""
    if _is_author_marker_placeholder(cleaned):
        return "This stage is present in the author story order, but direct implementation evidence is incomplete"
    return cleaned[0].upper() + cleaned[1:] + "."


def _is_author_marker_placeholder(text: str) -> bool:
    normalized = _normalize_text(text)
    return "author marker method stage" in normalized or "author-marker method stage" in normalized


def _clean_logic(text: str) -> str:
    if not text:
        return ""
    fragments = []
    for raw in re.split(r"[\n;]+", text):
        item = raw.strip()
        if not item or item.startswith("#"):
            continue
        lowered = item.lower()
        if "address of config file" in lowered or "print relevant info" in lowered:
            continue
        fragments.append(item)
    cleaned = " ".join(fragments)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _operation_sentence(packet: dict) -> str:
    operations = _packet_list(packet, "key_operations")
    if operations:
        return "Key operations include " + _join_human([_lower_first(_rstrip_period(op)) for op in operations[:4]]) + ". "
    flow = packet.get("data_flow") if isinstance(packet.get("data_flow"), list) else []
    flow_ops = [
        f"{item.get('from')} to {item.get('to')} via {item.get('op')}"
        for item in flow[:3]
        if isinstance(item, dict) and item.get("from") and item.get("to")
    ]
    if flow_ops:
        return "The data flow links " + _join_human(flow_ops) + ". "
    return ""


def _packet_list(packet: dict, key: str) -> list[str]:
    value = packet.get(key)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _packet_evidence_ids(packet: dict | None) -> list[str]:
    if not packet:
        return []
    return _dedupe(_packet_list(packet, "evidence_ids"))


def _clean_component_name(name: str) -> str:
    text = name.strip()
    if not text:
        return "the component"
    text = text.split("/")[-1]
    text = re.sub(r"\.py$", "", text)
    text = text.replace("_", " ")
    return text


def _role_phrase(role: str) -> str:
    text = _lower_first(_rstrip_period(role))
    replacements = {
        "inject ": "injecting ",
        "convert ": "converting ",
        "compact ": "compacting ",
        "shared ": "a shared ",
        "load ": "loading ",
        "control ": "controlling ",
    }
    for prefix, replacement in replacements.items():
        if text.startswith(prefix):
            return replacement + text[len(prefix) :]
    return text


def _goal_sentence(method_evidence: MethodEvidence) -> str:
    goal = _rstrip_period(method_evidence.method_goal)
    if not goal:
        return f"{method_evidence.method_name} summarizes the implementation-grounded method."
    lowered = goal.lower()
    if lowered.startswith(("coordinate ", "describe ", "train ", "show ", "enable ", "organize ", "connect ")):
        return f"{method_evidence.method_name} is designed to {_lower_first(goal)}."
    return f"{method_evidence.method_name} targets {_lower_first(goal)}."


def _objective_detail_lines(method_evidence: MethodEvidence, *, supplemental_equations_tex: str = "") -> list[str]:
    equations = [
        equation
        for equation in method_evidence.equation_candidates
        if equation.evidence_ids
        and _is_objective_equation(equation.name, equation.latex)
        and not _is_helper_or_audit_equation(equation.name, equation.latex)
    ]
    if not equations:
        equations = [
            equation
            for equation in method_evidence.equation_candidates
            if equation.evidence_ids and not _is_helper_or_audit_equation(equation.name, equation.latex)
        ][:4]
    supplemental_equations = _parse_supplemental_equations(supplemental_equations_tex)
    if not equations and not supplemental_equations:
        return []

    lines: list[str] = []
    evidence_ids = _dedupe([evidence_id for equation in equations for evidence_id in equation.evidence_ids])
    if not evidence_ids:
        evidence_ids = _all_supported_evidence_ids(method_evidence)
    lines.extend(
        [
            grounding_comment(
                stage_id=_stage_for_evidence(method_evidence, evidence_ids),
                mechanism_ids=_mechanisms_for_evidence(method_evidence, evidence_ids),
                evidence_ids=evidence_ids,
                confidence=_combined_confidence([equation.confidence for equation in equations]) if equations else "medium",
            ),
            "The objective keeps only the relations needed to define the method's training signal and main transformations.",
            "",
        ]
    )
    equation_items: list[tuple[str, str, list[str], str]] = []
    for equation in equations:
        equation_items.append((equation.name, equation.latex, equation.evidence_ids, equation.confidence.value))
    for latex in supplemental_equations:
        equation_items.append(("Code-supported relation", latex, evidence_ids, "medium"))

    seen_latex: set[str] = set()
    selected_items: list[tuple[str, str, list[str], str]] = []
    for name, latex, item_evidence_ids, confidence in equation_items:
        key = re.sub(r"\s+", "", latex)
        if not key or key in seen_latex:
            continue
        seen_latex.add(key)
        selected_items.append((name, latex, item_evidence_ids, confidence))
        if len(selected_items) >= 7:
            break

    for name, latex, item_evidence_ids, confidence in selected_items:
        lines.extend(
            [
                grounding_comment(
                    stage_id=_stage_for_evidence(method_evidence, item_evidence_ids),
                    mechanism_ids=_mechanisms_for_evidence(method_evidence, item_evidence_ids),
                    evidence_ids=item_evidence_ids,
                    confidence=confidence,
                ),
                "$$",
                latex,
                "$$",
                "",
            ]
        )
    return lines


def _distinguishing_mechanism_lines(method_evidence: MethodEvidence) -> list[str]:
    distinguishing_ids = set(method_evidence.distinguishing_mechanisms)
    frozen = [
        mechanism
        for mechanism in method_evidence.frozen_mechanisms
        if mechanism.evidence_span_ids
        and (
            mechanism.mechanism_id in distinguishing_ids
            or mechanism.distinguishing_level in {"main", "secondary"}
            or _looks_innovation_bearing(mechanism.mechanism_name, mechanism.mechanism_description)
        )
        and not _looks_setup_or_utility(mechanism.mechanism_name + " " + mechanism.mechanism_description)
    ]
    if not frozen:
        return []
    lines: list[str] = []
    for mechanism in frozen[:6]:
        io_parts = []
        if mechanism.inputs:
            io_parts.append("inputs " + _io_phrase(mechanism.inputs, "the previous stage outputs"))
        if mechanism.outputs:
            io_parts.append("outputs " + _io_phrase(mechanism.outputs, "the next stage inputs"))
        io_sentence = f" It uses {_join_human(io_parts)}." if io_parts else ""
        level = "primary" if mechanism.distinguishing_level == "main" else "supporting"
        lines.extend(
            [
                grounding_comment(
                    stage_id=mechanism.parent_stage_id or "ALL",
                    mechanism_ids=[mechanism.mechanism_id],
                    evidence_ids=mechanism.evidence_span_ids,
                    confidence="high",
                ),
                (
                    f"**{mechanism.mechanism_name}.** This {level} mechanism is explicit in the implementation: "
                    f"{_clean_sentence(mechanism.mechanism_description)}{io_sentence}"
                ),
                "",
            ]
        )
    return lines


def _mechanism_detail_lines(method_evidence: MethodEvidence) -> list[str]:
    return []
    lines: list[str] = []
    behavior_by_id = {pattern.behavior_id: pattern for pattern in method_evidence.behavior_patterns}
    equation_by_id = {equation.equation_id: equation for equation in method_evidence.equation_candidates}
    parameter_by_id = {parameter.parameter_id: parameter for parameter in method_evidence.architecture_parameters}
    tensor_by_id = {tensor.tensor_id: tensor for tensor in method_evidence.tensor_roles}
    seen_submechanisms: set[str] = set()

    for stage in method_evidence.stages:
        for mechanism in stage.mechanisms:
            for submechanism in mechanism.submechanisms:
                if submechanism.submechanism_id in seen_submechanisms:
                    continue
                seen_submechanisms.add(submechanism.submechanism_id)
                behavior_descriptions = [
                    _lower_first(_rstrip_period(behavior_by_id[behavior_id].description))
                    for behavior_id in submechanism.behavior_ids
                    if behavior_id in behavior_by_id
                ]
                parameter_text = _parameter_text(
                    [parameter_by_id[parameter_id] for parameter_id in submechanism.parameter_ids if parameter_id in parameter_by_id]
                )
                tensor_text = _tensor_text(
                    [tensor_by_id[tensor_id] for tensor_id in submechanism.tensor_ids if tensor_id in tensor_by_id]
                )
                detail_sentence = f"**{submechanism.submechanism_id}.** {submechanism.description}"
                if behavior_descriptions:
                    detail_sentence += f" It {_join_human(behavior_descriptions)}."
                if parameter_text:
                    detail_sentence += f" Detected structural parameters include {parameter_text}."
                if tensor_text:
                    detail_sentence += f" Detected tensor roles include {tensor_text}."
                lines.extend(
                    [
                        grounding_comment(
                            stage_id=stage.stage_id,
                            mechanism_ids=[mechanism.mechanism_id],
                            evidence_ids=submechanism.evidence_ids,
                            confidence=submechanism.confidence.value,
                        ),
                        detail_sentence,
                        "",
                    ]
                )
                for equation_id in submechanism.equation_ids:
                    equation = equation_by_id.get(equation_id)
                    if equation is None:
                        continue
                    lines.extend(
                        [
                            grounding_comment(
                                stage_id=stage.stage_id,
                                mechanism_ids=[mechanism.mechanism_id],
                                evidence_ids=equation.evidence_ids,
                                confidence=equation.confidence.value,
                            ),
                            f"Equation candidate **{equation.name}** is supported by the detected code pattern:",
                            "$$",
                            equation.latex,
                            "$$",
                            "",
                        ]
                    )
    return lines


def _is_objective_equation(name: str, latex: str) -> bool:
    text = f"{name} {latex}".lower()
    return any(
        token in text
        for token in (
            "objective",
            "loss",
            "criterion",
            "reconstruct",
            "reconstruction",
            "contrast",
            "classification",
            "cross",
            "\\mathcal{l}",
            "\\ell",
        )
    )


def _is_helper_or_audit_equation(name: str, latex: str) -> bool:
    text = f"{name} {latex}".lower()
    helper_terms = (
        "feed-forward",
        "point-wise",
        "\\mathrm{ffn}",
        "periodic positional",
        "\\mathrm{pe}_{",
        "cross-context attention",
        "scaled dot-product attention",
        "softmax(qk",
        "multibranch",
    )
    return any(term in text for term in helper_terms)


def _parse_supplemental_equations(equations_tex: str) -> list[str]:
    text = str(equations_tex or "")
    equations = re.findall(r"\\begin\{equation\*?\}\s*(.*?)\s*\\end\{equation\*?\}", text, flags=re.DOTALL)
    if not equations:
        equations = re.findall(r"\\\[\s*(.*?)\s*\\\]", text, flags=re.DOTALL)
    cleaned = [re.sub(r"\s+", " ", equation).strip() for equation in equations]
    objective = [equation for equation in cleaned if _is_objective_equation("", equation)]
    return _dedupe(objective or cleaned[:6])


def _stage_for_evidence(method_evidence: MethodEvidence, evidence_ids: list[str]) -> str:
    evidence = set(evidence_ids)
    stage_ids = [
        stage.stage_id
        for stage in method_evidence.stages
        if any(evidence.intersection(mechanism.evidence_ids) for mechanism in stage.mechanisms)
    ]
    stage_ids = _dedupe(stage_ids)
    return stage_ids[0] if len(stage_ids) == 1 else "ALL"


def _mechanisms_for_evidence(method_evidence: MethodEvidence, evidence_ids: list[str]) -> list[str]:
    evidence = set(evidence_ids)
    return _dedupe(
        [
            mechanism.mechanism_id
            for stage in method_evidence.stages
            for mechanism in stage.mechanisms
            if evidence.intersection(mechanism.evidence_ids)
        ]
    )


def _all_supported_evidence_ids(method_evidence: MethodEvidence) -> list[str]:
    return _dedupe(
        [
            evidence_id
            for stage in method_evidence.stages
            for mechanism in stage.mechanisms
            if mechanism.support_status != SupportStatus.UNSUPPORTED
            for evidence_id in mechanism.evidence_ids
        ]
    )


def _parameter_text(parameters: list) -> str:
    if not parameters:
        return ""
    return _join_human([f"{parameter.name}={parameter.value}" for parameter in parameters])


def _tensor_text(tensor_roles: list) -> str:
    if not tensor_roles:
        return ""
    return _join_human([f"{tensor.name} ({tensor.role})" for tensor in tensor_roles])


def _implementation_notes(
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap | None,
) -> list[tuple[str, list[str], list[str], str]]:
    notes: list[tuple[str, list[str], list[str], str]] = []
    all_mechanisms = [mechanism for stage in method_evidence.stages for mechanism in stage.mechanisms]
    all_mechanism_ids = [mechanism.mechanism_id for mechanism in all_mechanisms]
    all_evidence_ids = _dedupe([evidence_id for mechanism in all_mechanisms for evidence_id in mechanism.evidence_ids])
    confidence = _combined_confidence([mechanism.confidence for mechanism in all_mechanisms])

    if method_evidence.author_confirmation_required:
        notes.append(
            (
                "No author markers were provided for this run, so the draft should be treated as a low-confirmation method summary until the author reviews the stage and mechanism mapping.",
                all_mechanism_ids,
                all_evidence_ids,
                confidence,
            )
        )

    lower_confidence = [
        mechanism
        for mechanism in all_mechanisms
        if mechanism.confidence != ConfidenceLevel.HIGH or mechanism.support_status != SupportStatus.SUPPORTED
    ]
    lower_confidence_evidence_ids = _dedupe([evidence_id for mechanism in lower_confidence for evidence_id in mechanism.evidence_ids])
    if lower_confidence and lower_confidence_evidence_ids:
        notes.append(
            (
                "Lower-confidence or partially supported mechanisms are phrased conservatively and should not be promoted into stronger claims without additional evidence.",
                [mechanism.mechanism_id for mechanism in lower_confidence],
                lower_confidence_evidence_ids,
                _combined_confidence([mechanism.confidence for mechanism in lower_confidence]),
            )
        )

    for claim in _supported_author_claims(claim_map):
        notes.append(
            (
                f"An author-highlighted distinguishing mechanism is retained as an implementation-grounded method claim: {claim.claim_text.rstrip('.')}.",
                claim.mechanism_ids or all_mechanism_ids,
                claim.evidence_ids,
                "medium" if claim.support_status == SupportStatus.PARTIAL else "high",
            )
        )
    return notes


def _supported_author_claims(claim_map: ClaimEvidenceMap | None) -> list[ClaimEvidenceItem]:
    if claim_map is None:
        return []
    return [
        claim
        for claim in claim_map.claims
        if claim.source.startswith("author_claim:")
        and claim.support_status != SupportStatus.UNSUPPORTED
        and claim.evidence_ids
    ]


def _sanitize_unsupported_phrases(text: str, claim_map: ClaimEvidenceMap | None) -> str:
    result = str(text or "")
    if claim_map is None:
        return result
    for claim in claim_map.claims:
        if claim.support_status != SupportStatus.UNSUPPORTED:
            continue
        claim_text = str(claim.claim_text or "").strip()
        if len(claim_text) < 12:
            continue
        result = re.sub(re.escape(claim_text), "", result, flags=re.IGNORECASE)
    result = re.sub(r"\b(Optimization is driven by|Driven by)\s*\.\s*", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\s{2,}", " ", result)
    result = re.sub(r"\.\s*\.", ".", result)
    return result.strip(" ;.")


def _core_modules(modules: list[MethodModule]) -> list[MethodModule]:
    return [module for module in modules if module.category == ModuleCategory.METHOD_CORE]


def _module_labels(modules: list[MethodModule]) -> list[str]:
    labels: list[str] = []
    for module in modules:
        if module.symbols:
            labels.append(f"{module.path}:{'/'.join(module.symbols)}")
        else:
            labels.append(module.path)
    return labels


def _stage_mechanism_summary(stage: MethodStageEvidence, mechanisms: list) -> str:
    descriptions = [
        _rstrip_period(mechanism.description)
        for mechanism in mechanisms
        if _normalize_text(mechanism.description) != _normalize_text(stage.purpose)
    ]
    if not descriptions:
        return ""
    return _join_human(descriptions) + "."


def _is_low_priority_setup_stage(stage: MethodStageEvidence, packet: dict | None, mechanisms: list) -> bool:
    text = " ".join(
        [
            stage.name,
            stage.purpose,
            " ".join(stage.inputs),
            " ".join(stage.outputs),
            " ".join(str(item) for item in _packet_list(packet or {}, "key_operations")),
        ]
    )
    if not _looks_setup_or_utility(text):
        return False
    if any(_mechanism_has_equation(mechanism) for mechanism in mechanisms):
        return False
    if any(_looks_innovation_bearing("", mechanism.description) for mechanism in mechanisms):
        return False
    return True


def _mechanism_has_equation(mechanism) -> bool:
    return any(submechanism.equation_ids for submechanism in getattr(mechanism, "submechanisms", []))


def _looks_setup_or_utility(text: str) -> bool:
    normalized = _normalize_text(text)
    setup_terms = {
        "setup",
        "overview",
        "prelim",
        "introduction",
        "configuration",
        "config",
        "parse",
        "parser",
        "argument",
        "cli",
        "launcher",
        "entrypoint",
        "logging",
        "checkpoint",
        "environment",
        "seed",
        "load data",
        "data loader",
        "dataset loading",
        "utility",
    }
    method_terms = {
        "objective",
        "loss",
        "forward",
        "encoder",
        "decoder",
        "attention",
        "mask",
        "reconstruct",
        "classification",
        "segmentation",
        "contrast",
        "feature",
        "representation",
    }
    return any(term in normalized for term in setup_terms) and not any(term in normalized for term in method_terms)


def _looks_innovation_bearing(name: str, description: str) -> bool:
    normalized = _normalize_text(f"{name} {description}")
    return any(
        token in normalized
        for token in (
            "innovation",
            "distinguishing",
            "novel",
            "mechanism",
            "objective",
            "loss",
            "mask",
            "attention",
            "reconstruct",
            "contrast",
            "alignment",
            "fusion",
        )
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", _rstrip_period(str(value)).lower()).strip()


def _module_role_labels(modules: list[MethodModule]) -> list[str]:
    labels = []
    for module in modules:
        role = module.role.strip()
        if role and role.lower() not in {"model_arch", "unknown"}:
            labels.append(role)
        elif module.symbols:
            labels.append(_humanize_identifier(module.symbols[0]))
    return _dedupe(labels)


def _io_phrase(items: list[str], fallback: str) -> str:
    cleaned = [_clean_io_item(item) for item in items]
    cleaned = [item for item in cleaned if item and not _is_placeholder_io(item)]
    if not cleaned:
        return fallback
    return _join_human(_dedupe(cleaned))


def _clean_io_item(item: str) -> str:
    text = str(item).strip()
    text = text.strip("[]")
    text = text.strip("'\"")
    text = text.replace("_", " ")
    return text


def _is_placeholder_io(item: str) -> bool:
    normalized = item.strip().lower().replace(" ", "_")
    return bool(re.fullmatch(r"(input|output)_\d+", normalized))


def _humanize_identifier(value: str) -> str:
    text = re.sub(r"(?<!^)(?=[A-Z])", " ", value)
    text = text.replace("_", " ").strip()
    return text.lower()


def _third_person_phrase(value: str) -> str:
    text = _lower_first(_rstrip_period(value))
    replacements = {
        "establish ": "establishes ",
        "expand ": "expands ",
        "use ": "uses ",
        "control ": "controls ",
        "connect ": "connects ",
        "show ": "shows ",
        "train ": "trains ",
        "perform ": "performs ",
        "execute ": "executes ",
    }
    for prefix, replacement in replacements.items():
        if text.startswith(prefix):
            return replacement + text[len(prefix) :]
    return text


def _dedupe_modules(modules: list[MethodModule]) -> list[MethodModule]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    result: list[MethodModule] = []
    for module in modules:
        key = (module.path, tuple(module.symbols))
        if key in seen:
            continue
        seen.add(key)
        result.append(module)
    return result


def _join_human(values: list[str]) -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _lower_first(value: str) -> str:
    if not value:
        return value
    return value[0].lower() + value[1:]


def _rstrip_period(value: str) -> str:
    return value.rstrip().rstrip(".")


def _combined_confidence(confidences: list[ConfidenceLevel]) -> str:
    if not confidences:
        return "medium"
    values = [ConfidenceLevel(confidence) for confidence in confidences]
    if any(value == ConfidenceLevel.LOW for value in values):
        return "low"
    if any(value == ConfidenceLevel.MEDIUM for value in values):
        return "medium"
    return "high"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
