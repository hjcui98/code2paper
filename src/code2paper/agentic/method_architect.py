"""Method Architect: claims and completeness into a publication argument graph."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from code2paper.agentic.evidence_compiler_v3 import AtomicClaimSetV3, AtomicClaimV3
from code2paper.agentic.equation_claims import EquationClaimSetV1
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    MethodArgumentUnitV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
    SectionArgumentGraphV1,
    SectionArgumentMoveV1,
)


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()[:24]


class MethodArchitect:
    """Build a section plan without generating final prose."""

    def build(
        self,
        *,
        claims: AtomicClaimSetV3,
        completeness: MethodCompletenessMatrixV1 | None = None,
        equations: EquationClaimSetV1 | None = None,
        configurations: ConfigurationClaimSetV1 | None = None,
        method_name: str = "",
        venue: str = "",
        audience: str = "method readers",
        page_budget: float = 0.0,
    ) -> MethodSectionPlanV2:
        return build_method_section_plan(
            claims=claims,
            completeness=completeness,
            equations=equations,
            configurations=configurations,
            method_name=method_name,
            venue=venue,
            audience=audience,
            page_budget=page_budget,
        )


def build_method_section_plan(
    *,
    claims: AtomicClaimSetV3,
    completeness: MethodCompletenessMatrixV1 | None = None,
    equations: EquationClaimSetV1 | None = None,
    configurations: ConfigurationClaimSetV1 | None = None,
    method_name: str = "",
    venue: str = "",
    audience: str = "method readers",
    page_budget: float = 0.0,
) -> MethodSectionPlanV2:
    """Create argument units and section graphs from authorized artifacts.

    The grouping order comes from compiler-authorized semantic stage groups.
    Claims that are not in a group are assigned to a final generic section so
    a new repository cannot disappear merely because an organization hint was
    incomplete.  No project-specific heading or factual sentence is created.
    """

    claim_by_id = {item.claim_id: item for item in claims.claims}
    equation_by_claim = {
        item.prose_claim_id: item
        for item in (equations.equations if equations is not None else [])
        if item.prose_claim_id
    }
    config_items = tuple(configurations.claims) if configurations is not None else ()
    groups: list[tuple[str, str, str, list[AtomicClaimV3], tuple[str, ...]]] = []
    used: set[str] = set()
    for group in sorted(claims.semantic_stage_groups, key=lambda item: (item.organization_priority, item.stage_id)):
        selected = [
            claim_by_id[claim_id]
            for claim_id in group.ordered_claim_ids
            if claim_id in claim_by_id
            and claim_id not in used
            and claim_by_id[claim_id].status in {"supported", "partial"}
        ]
        if not selected:
            continue
        used.update(item.claim_id for item in selected)
        groups.append((group.stage_id, group.name, group.purpose, selected, tuple(group.covers_obligation_ids)))
    remaining = [
        item for item in claims.claims
        if item.claim_id not in used and item.status in {"supported", "partial"}
    ]
    if remaining:
        groups.append(("ungrouped", "Additional method mechanism", "Executable behavior not assigned to a compiler stage.", remaining, ()))

    matrix_by_id = completeness.by_id() if completeness is not None else {}
    units: list[MethodArgumentUnitV1] = []
    graphs: list[SectionArgumentGraphV1] = []
    for index, (group_id, heading, purpose, selected, obligation_ids) in enumerate(groups, start=1):
        section_id = f"MA-S{index}"
        claim_ids = tuple(item.claim_id for item in selected)
        equation_ids = tuple(
            equation_by_claim[claim_id].equation_id
            for claim_id in claim_ids
            if claim_id in equation_by_claim
        )
        configuration_ids = tuple(
            config.configuration_id
            for config in config_items
            if config.active and _configuration_relevant(config.key, selected)
        )
        unresolved = _unresolved_for_obligations(obligation_ids, matrix_by_id)
        lanes = ["executable_hard"]
        if equation_ids:
            lanes.append("formal_derivation")
        if configuration_ids:
            lanes.append("configuration_resolved")
        unit_id = f"{section_id}:unit"
        moves = _moves(selected, bool(equation_ids), bool(configuration_ids), bool(unresolved))
        unit = MethodArgumentUnitV1(
            argument_unit_id=unit_id,
            section_role="stage",
            research_question=purpose or heading,
            design_objective=purpose,
            claim_ids=claim_ids,
            equation_ids=equation_ids,
            configuration_ids=configuration_ids,
            behavior_relation_ids=tuple(
                relation_id
                for claim in selected
                for relation_id in claim.relation_evidence_ids
            ),
            allowed_expository_moves=moves,
            unresolved_inputs=tuple(unresolved),
            authority_lanes=tuple(lanes),
            source_artifact_ids=tuple(
                evidence_id
                for claim in selected
                for evidence_id in (claim.direct_evidence_ids + claim.relation_evidence_ids)
            ),
            supported=not unresolved,
            information_weight=max(1.0, len(selected) + 0.75 * len(equation_ids) + 0.5 * len(configuration_ids)),
        )
        units.append(unit)
        move_objects = tuple(
            SectionArgumentMoveV1(
                move=move,
                argument_unit_ids=(unit_id,),
                paragraph_budget=1 if move not in {"transition_to_next_section"} else 0,
                information_budget=max(0.25, unit.information_weight / len(moves)),
                allowed_authority_lanes=tuple(lanes),
                required=move in {"mechanism_overview", "implementation_realization"} or (
                    move == "limitations_or_mismatch" and bool(unresolved)
                ),
            )
            for move in moves
        )
        graphs.append(SectionArgumentGraphV1(
            section_id=section_id,
            heading=heading,
            reader_question=purpose or heading,
            argument_unit_ids=(unit_id,),
            moves=move_objects,
            dependencies=tuple(graphs[-1].section_id for _ in graphs[-1:]),
            unresolved_inputs=tuple(unresolved),
            depth_budget=max(1, min(8, len(move_objects) + (len(selected) - 1) // 2)),
            page_budget=max(0.25, round(unit.information_weight * 0.35 + len(move_objects) * 0.05, 3)),
            incomplete=bool(unresolved),
        ))

    incomplete_ids = [graph.section_id for graph in graphs if graph.incomplete]
    if completeness is not None:
        incomplete_ids.extend(
            f"unresolved:{item.obligation_id}"
            for item in completeness.items
            if item.importance in {"critical", "high"}
            and item.status == "unverified_by_repository"
        )
    incomplete = tuple(dict.fromkeys(incomplete_ids))
    total_page_budget = page_budget or sum(graph.page_budget for graph in graphs)
    plan_id = "method-plan:" + _digest({
        "claims": claims.content_digest,
        "completeness": completeness.content_digest if completeness else "",
        "equations": equations.content_digest if equations else "",
        "configurations": configurations.content_digest if configurations else "",
    })[7:]
    return MethodSectionPlanV2(
        plan_id=plan_id,
        method_name=method_name,
        sections=tuple(graphs),
        argument_units=tuple(units),
        venue=venue,
        audience=audience,
        total_page_budget=round(total_page_budget, 3),
        incomplete_sections=incomplete,
    )


def _unresolved_for_obligations(obligation_ids: tuple[str, ...], matrix: dict[str, Any]) -> list[str]:
    unresolved: list[str] = []
    for obligation_id in obligation_ids:
        item = matrix.get(obligation_id)
        if item is None:
            continue
        status = str(item.status)
        if status not in {"supported_by_repository", "partially_supported_by_repository"}:
            unresolved.append(f"{obligation_id}:{status}")
    return unresolved


def _configuration_relevant(key: str, claims: list[AtomicClaimV3]) -> bool:
    tokens = set(re.findall(r"[a-z0-9_]+", key.lower()))
    if not tokens:
        return False
    return any(tokens & set(re.findall(r"[a-z0-9_]+", claim.canonical_text.lower())) for claim in claims)


def _moves(
    claims: list[AtomicClaimV3],
    has_equations: bool,
    has_configurations: bool,
    has_unresolved: bool,
) -> tuple[str, ...]:
    moves: list[str] = ["problem_or_local_context", "design_objective", "mechanism_overview"]
    if has_equations:
        moves.extend(("formal_objects_and_notation", "equation_or_derivation"))
    moves.extend(("algorithm_or_data_flow", "implementation_realization"))
    if has_configurations:
        moves.append("configuration_and_branches")
    if any(claim.claim_kind == "configuration_fact" for claim in claims):
        moves.append("inference_and_output")
    if has_unresolved:
        moves.append("limitations_or_mismatch")
    moves.append("transition_to_next_section")
    return tuple(dict.fromkeys(moves))


__all__ = ["MethodArchitect", "build_method_section_plan"]
