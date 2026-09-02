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
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
    MethodUnitV2,
    MoveAuthorityProofV1,
    ObligationMoveAssignmentV1,
    ReferenceMethodAgendaV1,
    SectionArgumentGraphV1,
    SectionArgumentMoveV1,
    SectionParagraphPlanV1,
    ParagraphWitnessContractV1,
    ParagraphWitnessTargetV1,
    SectionContentOpenSlotV1,
    SemanticArgumentFrameV1,
    SemanticFlowEdgeV1,
    SemanticFlowSlotV1,
)
from code2paper.agentic.method_product_models import (
    AuthorStoryNodeV1,
    MethodOutputPolicyV1,
    MethodPlanProductReadinessV1,
    assess_plan_product_readiness,
)
from code2paper.agentic.method_proposition_models import MethodPropositionSetV1
from code2paper.agentic.publication_quality import coherent_heading, heading_is_truncated


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
        story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1] = (),
        publication_field_candidates: tuple[Any, ...] | list[Any] = (),
        argument_facets: tuple[Any, ...] | list[Any] = (),
        facet_alignments: tuple[Any, ...] | list[Any] = (),
        facts: Any | None = None,
        unit_frames: dict[str, SemanticArgumentFrameV1] | None = None,
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
            story_spine=story_spine,
            publication_field_candidates=publication_field_candidates,
            argument_facets=argument_facets,
            facet_alignments=facet_alignments,
            facts=facts,
            unit_frames=unit_frames,
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
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1] = (),
    publication_field_candidates: tuple[Any, ...] | list[Any] = (),
    argument_facets: tuple[Any, ...] | list[Any] = (),
    facet_alignments: tuple[Any, ...] | list[Any] = (),
    facts: Any | None = None,
    unit_frames: dict[str, SemanticArgumentFrameV1] | None = None,
) -> MethodSectionPlanV2:
    plan, _trace = build_method_section_plan_with_trace(
        claims=claims,
        completeness=completeness,
        equations=equations,
        configurations=configurations,
        method_name=method_name,
        venue=venue,
        audience=audience,
        page_budget=page_budget,
        story_spine=story_spine,
        publication_field_candidates=publication_field_candidates,
        argument_facets=argument_facets,
        facet_alignments=facet_alignments,
        facts=facts,
        unit_frames=unit_frames,
    )
    return plan


def build_method_section_plan_with_trace(
    *,
    claims: AtomicClaimSetV3,
    completeness: MethodCompletenessMatrixV1 | None = None,
    equations: EquationClaimSetV1 | None = None,
    configurations: ConfigurationClaimSetV1 | None = None,
    method_name: str = "",
    venue: str = "",
    audience: str = "method readers",
    page_budget: float = 0.0,
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1] = (),
    propositions: MethodPropositionSetV1 | None = None,
    concept_cards: Any | None = None,
    argument_briefs: Any | None = None,
    prior_plan: MethodSectionPlanV2 | None = None,
    publication_field_candidates: tuple[Any, ...] | list[Any] = (),
    argument_facets: tuple[Any, ...] | list[Any] = (),
    facet_alignments: tuple[Any, ...] | list[Any] = (),
    facts: Any | None = None,
    unit_frames: dict[str, SemanticArgumentFrameV1] | None = None,
) -> tuple[MethodSectionPlanV2, dict[str, Any]]:
    """Create argument units and section graphs from authorized artifacts.

    Section organization follows the author story spine first (when the
    projection supplies one), then compiler-authorized semantic stage groups.
    Claims that are not in a group are assigned to a final generic section so
    a new repository cannot disappear merely because an organization hint was
    incomplete.  No project-specific heading or factual sentence is created.

    ``concept_cards`` (optional ``MethodConceptCardSetV1``) binds Stage 2/3
    concept cards to units through exact obligation ids, separating verified
    from caveated cards.  Each card is assigned to exactly one unit.
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
    spine_obligation_order = _story_spine_obligation_order(story_spine)
    for group in sorted(
        claims.semantic_stage_groups,
        key=lambda item: _group_organization_key(item, spine_obligation_order),
    ):
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
    # A semantic stage compiler is allowed to select only the most salient
    # claims for its initial stage.  Claims discovered by a later read of the
    # same obligation are continuations of that stage, not a new Method
    # section.  Coalesce them through the exact obligation edge before using
    # the generic ungrouped fallback.  Without this step the same obligation
    # was rendered twice (once as the named stage and once as "Additional
    # method mechanism"), and proposition binding then copied the complete
    # concept set into both sections.
    groups, remaining = _coalesce_remaining_claims_by_obligation(
        groups=groups,
        remaining=remaining,
    )
    # Intent-organized groups are an allow-list: ungrouped claims are commonly
    # verify-only rationale checks retained for audit, not authoring content.
    # Legacy/generic claim sets without intent groups keep the safe fallback.
    has_intent_authoring_groups = any(
        group.stage_id.startswith("SG-INTENT-")
        for group in claims.semantic_stage_groups
    )
    if remaining and not has_intent_authoring_groups:
        groups.append(("ungrouped", "Additional method mechanism", "Executable behavior not assigned to a compiler stage.", remaining, ()))

    matrix_by_id = completeness.by_id() if completeness is not None else {}
    # The compiler may emit several obligation-scoped groups for the same
    # semantic stage.  They remain distinct argument units, but they must not
    # become one repetitive section per obligation.  Merge only groups whose
    # compiler-authored stage name is identical; no project-specific taxonomy
    # or prompt literal is introduced here.
    section_buckets: list[tuple[str, list[tuple[str, str, str, list[AtomicClaimV3], tuple[str, ...]]]]] = []
    bucket_by_heading: dict[str, int] = {}
    for group in groups:
        key = " ".join(re.findall(r"[a-z0-9]+", group[1].lower())) or group[0]
        if key not in bucket_by_heading:
            bucket_by_heading[key] = len(section_buckets)
            section_buckets.append((group[1], [group]))
        else:
            section_buckets[bucket_by_heading[key]][1].append(group)

    # --- Candidate buckets (P): unrealized story/completeness rows become
    # candidate argument units instead of vanishing into the review sidecar.
    # Supported facts stay verified-capable units; partial / author /
    # external / formalization / mismatch rows become candidate units with
    # explicit lanes and caveat moves; only out-of-scope rows are skipped. ---
    candidate_buckets = _candidate_buckets_from_story_and_completeness(
        story_spine=story_spine,
        completeness=completeness,
        realized_obligation_ids=_realized_obligation_ids(groups, claim_by_id),
    )
    candidate_buckets = _fold_leftover_author_statement_buckets(
        claim_buckets=section_buckets,
        candidate_buckets=candidate_buckets,
    )

    # Merge claim and candidate buckets in story-spine order so author intent
    # (not repository code order) drives the section sequence.
    merged_buckets = _merge_plan_buckets(
        claim_buckets=section_buckets,
        candidate_buckets=candidate_buckets,
        spine_obligation_order=spine_obligation_order,
    )
    merged_buckets = _consolidate_buckets_under_organization_spine(
        merged_buckets,
        story_spine=story_spine,
        completeness=completeness,
    )
    merged_buckets = _merge_near_duplicate_section_buckets(merged_buckets)
    # A one-section Method should carry the author-supplied method/component
    # name rather than an internal compiler label such as "Implementation
    # stage 1".  This is organization only; it does not authorize prose.
    if len(merged_buckets) == 1 and method_name.strip():
        merged_buckets = [(method_name.strip(), merged_buckets[0][1])]

    units: list[MethodArgumentUnitV1] = []
    graphs: list[SectionArgumentGraphV1] = []
    unit_required_moves: dict[str, frozenset[str]] = {}
    trace_rows: list[dict[str, Any]] = []
    for section_index, (heading, bucket) in enumerate(merged_buckets, start=1):
        section_id = f"MA-S{section_index}"
        section_units: list[MethodArgumentUnitV1] = []
        for unit_index, item in enumerate(bucket, start=1):
            if isinstance(item, _CandidateRowEntry):
                unit = _candidate_argument_unit(
                    row=item.row,
                    story_node=item.story_node,
                    section_id=section_id,
                    unit_id=f"{section_id}:unit" if len(bucket) == 1 else f"{section_id}:unit-{unit_index}",
                    heading=heading,
                )
                units.append(unit)
                section_units.append(unit)
                unit_required_moves[unit.argument_unit_id] = frozenset(
                    move for move in unit.allowed_expository_moves
                    if move in {
                        "problem_or_local_context",
                        "design_objective",
                        "mechanism_overview",
                    }
                    or (
                        move == "equation_or_derivation"
                        and bool(unit.equation_ids)
                    )
                    or (
                        move == "configuration_and_branches"
                        and bool(unit.configuration_ids)
                    )
                    or (
                        move == "limitations_or_mismatch"
                        and _unresolved_requires_limitation_move(
                            unit.unresolved_inputs
                        )
                    )
                )
                trace_rows.append({
                    "section_id": section_id,
                    "unit_id": unit.argument_unit_id,
                    "heading": heading,
                    "claim_ids": list(unit.claim_ids),
                    "equation_ids": list(unit.equation_ids),
                    "configuration_ids": list(unit.configuration_ids),
                    "moves": list(unit.allowed_expository_moves),
                    "required_moves": sorted(unit_required_moves[unit.argument_unit_id]),
                    "obligation_ids": [item.obligation_id],
                    "unresolved": list(unit.unresolved_inputs),
                    "candidate_unit": True,
                })
                continue
            (_group_id, _heading, purpose, selected, obligation_ids) = item
            claim_ids = tuple(item.claim_id for item in selected)
            equation_ids = tuple(
                equation_by_claim[claim_id].equation_id
                for claim_id in claim_ids
                if claim_id in equation_by_claim
            )
            configuration_ids = tuple(
                config.configuration_id
                for config in config_items
                if config.active and _configuration_binds_unit(config, selected)
            )
            # The compiler-authored stage membership is the owner of a
            # selected claim set.  A callback claim can conservatively cover
            # several obligations, but that does not make every covered
            # obligation a member of this stage.  Expanding the unit with
            # every such edge turns one stage into a cross-document
            # container and later makes every attached brief/facet appear to
            # belong to the same paragraph.  Keep singleton claim coverage as
            # a compatibility edge when the group omitted it; retain the
            # declared stage coverage for multi-obligation claims.
            effective_obligation_ids = _closed_group_obligation_ids(
                obligation_ids,
                selected,
            )
            unresolved = _unresolved_for_obligations(effective_obligation_ids, matrix_by_id)
            lanes = ["executable_hard"]
            if equation_ids:
                lanes.append("formal_derivation")
            if configuration_ids:
                lanes.append("configuration_resolved")
            unit_id = f"{section_id}:unit" if len(bucket) == 1 else f"{section_id}:unit-{unit_index}"
            moves, required_moves = _moves(
                selected,
                bool(equation_ids),
                bool(configuration_ids),
                unresolved,
                heading=heading,
            )
            unit_required_moves[unit_id] = required_moves
            trace_rows.append({
                "section_id": section_id,
                "unit_id": unit_id,
                "heading": heading,
                "claim_ids": list(claim_ids),
                "equation_ids": list(equation_ids),
                "configuration_ids": list(configuration_ids),
                "moves": list(moves),
                "required_moves": sorted(required_moves),
                "obligation_ids": list(effective_obligation_ids),
                "unresolved": unresolved,
            })
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
                source_obligation_ids=effective_obligation_ids,
                supported=not unresolved,
                information_weight=max(1.0, len(selected) + 0.75 * len(equation_ids) + 0.5 * len(configuration_ids)),
            )
            units.append(unit)
            section_units.append(unit)

        section_moves = tuple(dict.fromkeys(
            move for unit in section_units for move in unit.allowed_expository_moves
        ))
        all_lanes = tuple(dict.fromkeys(
            lane for unit in section_units for lane in unit.authority_lanes
        ))
        unresolved = tuple(dict.fromkeys(
            item for unit in section_units for item in unit.unresolved_inputs
        ))
        move_objects = tuple(
            _bind_move_anchor(
                SectionArgumentMoveV1(
                    move=move,
                    argument_unit_ids=tuple(
                        unit.argument_unit_id
                        for unit in section_units
                        if move in unit.allowed_expository_moves
                    ),
                    paragraph_budget=0 if move == "transition_to_next_section" else max(
                        1, min(3, round(sum(
                            unit.information_weight for unit in section_units
                            if move in unit.allowed_expository_moves
                        ) / 8)),
                    ),
                    information_budget=max(0.25, round(sum(
                        unit.information_weight for unit in section_units
                        if move in unit.allowed_expository_moves
                    ) / max(1, len(section_moves)), 3)),
                    allowed_authority_lanes=_move_authority_lanes(
                        move,
                        all_lanes=all_lanes,
                    ),
                    required=any(
                        move in unit_required_moves.get(unit.argument_unit_id, frozenset())
                        for unit in section_units
                        if move in unit.allowed_expository_moves
                    ) or (
                        move == "configuration_and_branches" and any(unit.configuration_ids for unit in section_units)
                    ) or (
                        move == "limitations_or_mismatch"
                        and _unresolved_requires_limitation_move(unresolved)
                    ),
                ),
                section_units=section_units,
            )
            for move in section_moves
        )
        move_objects = _ensure_unanchored_formula_move(
            move_objects, section_units=section_units, heading=heading,
        )
        if section_index == len(merged_buckets):
            move_objects = tuple(
                move.model_copy(update={"required": False})
                if move.move == "transition_to_next_section"
                else move
                for move in move_objects
            )
        total_information = sum(unit.information_weight for unit in section_units)
        heading, heading_constraints = _planning_section_heading(
            heading,
            bucket=bucket,
        )
        graphs.append(SectionArgumentGraphV1(
            section_id=section_id,
            heading=heading,
            reader_question=_story_reader_question(
                heading=heading,
                bucket=bucket,
            ),
            argument_unit_ids=tuple(unit.argument_unit_id for unit in section_units),
            moves=move_objects,
            dependencies=tuple(graphs[-1].section_id for _ in graphs[-1:]),
            unresolved_inputs=unresolved,
            depth_budget=max(1, min(12, len(move_objects) + (len(section_units) - 1) // 2)),
            page_budget=max(0.5, min(8.0, round(total_information * 0.12 + len(move_objects) * 0.12, 3))),
            incomplete=bool(unresolved),
            heading_constraints=heading_constraints,
            paragraphs=_build_section_paragraph_plans(
                section_id=section_id,
                section_units=section_units,
                move_objects=move_objects,
                unit_frames=unit_frames,
                argument_facets=argument_facets,
                facet_alignments=facet_alignments,
                publication_field_candidates=publication_field_candidates,
            ),
        ))

    # Bind proposition cards to argument units through exact obligation IDs.
    # This changes only the Writer-facing conceptual plan; evidence authority
    # remains in the separately persisted binding sidecar.
    if propositions is not None:
        units = [
            unit.model_copy(update={
                "proposition_ids": (ordered := tuple(
                    proposition.proposition_id
                    for proposition in propositions.propositions
                    if set(proposition.source_obligation_ids).intersection(unit.source_obligation_ids)
                )),
                "positive_proposition_ids": tuple(
                    proposition.proposition_id
                    for proposition in propositions.propositions
                    if proposition.proposition_id in ordered
                    and not proposition.requires_caveat
                ),
                "caveated_proposition_ids": tuple(
                    proposition.proposition_id
                    for proposition in propositions.propositions
                    if proposition.proposition_id in ordered
                    and proposition.requires_caveat
                ),
                "proposition_order": ordered,
                # Adjacent edges encode the reader-facing order already
                # selected for this unit.  The model contract validates that
                # this graph is closed and acyclic; it is not a source-code
                # control-flow graph.
                "proposition_dependencies": tuple(zip(ordered, ordered[1:])),
            })
            for unit in units
        ]

    # Bind Stage 2/3 concept cards to argument units through exact
    # obligation IDs.  Every card is assigned to exactly one unit; verified
    # and caveated cards are separated for the Writer's four-layer view.
    if concept_cards is not None:
        cards = tuple(getattr(concept_cards, "cards", ()) or ())
        card_by_key = {card.concept_key: card for card in cards}
        # Obligation linkage lives in the digest-covered binding sidecar.
        obligation_by_card: dict[str, tuple[str, ...]] = {}
        for binding in getattr(concept_cards, "bindings", ()) or ():
            obligation_by_card[binding.concept_key] = tuple(
                binding.source_obligation_ids
            )
        placed_keys: set[str] = set()
        for unit_index, unit in enumerate(units):
            unit_claim_coverage = {
                obligation_id
                for claim_id in unit.claim_ids
                for obligation_id in (
                    getattr(claim_by_id.get(claim_id), "covers_obligation_ids", ())
                    or ()
                )
                if str(obligation_id).strip()
            }
            ordered_concepts = tuple(
                card.concept_key
                for card in cards
                if (
                    set(obligation_by_card.get(card.concept_key, ())).intersection(
                        unit.source_obligation_ids
                    )
                    or set(obligation_by_card.get(card.concept_key, ())).intersection(
                        unit_claim_coverage
                    )
                )
                and card.concept_key not in placed_keys
            )
            placed_keys.update(ordered_concepts)
            units[unit_index] = unit.model_copy(update={
                "concept_card_ids": ordered_concepts,
                "verified_concept_card_ids": tuple(
                    key for key in ordered_concepts
                    if card_by_key[key].may_enter_verified
                ),
                "caveated_concept_card_ids": tuple(
                    key for key in ordered_concepts
                    if not card_by_key[key].may_enter_verified
                ),
                "concept_card_order": ordered_concepts,
            })

    if argument_briefs is not None:
        briefs = tuple(getattr(argument_briefs, "briefs", ()) or ())
        brief_by_id = {brief.brief_id: brief for brief in briefs}
        placed_brief_ids: set[str] = set()
        for unit_index, unit in enumerate(units):
            ordered_briefs = tuple(
                brief.brief_id
                for brief in briefs
                if set(brief.obligation_ids).intersection(unit.source_obligation_ids)
                and brief.brief_id not in placed_brief_ids
            )
            placed_brief_ids.update(ordered_briefs)
            units[unit_index] = unit.model_copy(update={
                "brief_ids": ordered_briefs,
                "verified_brief_ids": tuple(
                    brief_id for brief_id in ordered_briefs
                    if brief_by_id[brief_id].may_enter_verified
                ),
                "caveated_brief_ids": tuple(
                    brief_id for brief_id in ordered_briefs
                    if not brief_by_id[brief_id].may_enter_verified
                ),
                "brief_order": ordered_briefs,
            })

    incomplete_ids = [graph.section_id for graph in graphs if graph.incomplete]
    if completeness is not None:
        incomplete_ids.extend(
            f"unresolved:{item.obligation_id}"
            for item in completeness.items
            if item.importance in {"critical", "high"}
            and item.status == "unverified_by_repository"
        )
    incomplete = tuple(dict.fromkeys(incomplete_ids))
    graphs = _enrich_section_content_contracts(
        graphs,
        units,
        story_spine=story_spine,
        concept_cards=concept_cards,
        argument_briefs=argument_briefs,
        argument_facets=argument_facets,
        facet_alignments=facet_alignments,
        publication_field_candidates=publication_field_candidates,
        equations=equations,
        unit_frames=unit_frames,
    )
    if prior_plan is not None:
        units, graphs = _stabilize_plan_section_ids(
            units=units,
            graphs=graphs,
            prior_plan=prior_plan,
        )
    if prior_plan is not None and prior_plan.method_units:
        method_units, graphs, method_unit_trace = _preserve_incumbent_method_unit_surface(
            prior_plan=prior_plan,
            rebuilt_sections=list(graphs),
        )
        units = list(prior_plan.argument_units)
        plan_id = prior_plan.plan_id
    else:
        method_units, graphs, method_unit_trace = _build_method_units_v2(
            graphs,
            units,
            argument_facets=argument_facets,
            facet_alignments=facet_alignments,
            publication_field_candidates=publication_field_candidates,
            facts=facts,
            unit_frames=unit_frames,
        )
        plan_id = "method-plan:" + _digest({
            "claims": claims.content_digest,
            "completeness": completeness.content_digest if completeness else "",
            "equations": equations.content_digest if equations else "",
            "configurations": configurations.content_digest if configurations else "",
            "publication_field_candidates": _digest([
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in publication_field_candidates
            ]),
            "story_spine": [node.story_node_id for node in story_spine],
        })[7:]
    total_page_budget = page_budget or sum(graph.page_budget for graph in graphs)
    story_usage = _story_spine_usage_trace(story_spine, graphs, units)
    trace = {
        "schema_version": "1.0",
        "plan_id": plan_id,
        "method_name": method_name,
        "input_digests": {
            "claims": claims.content_digest,
            "completeness": completeness.content_digest if completeness else "",
            "equations": equations.content_digest if equations else "",
            "configurations": configurations.content_digest if configurations else "",
            "publication_field_candidates": _digest([
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in publication_field_candidates
            ]),
            "story_spine": {
                "used": bool(spine_obligation_order),
                "node_ids": [node.story_node_id for node in story_spine],
            },
        },
        "sections": trace_rows,
        "story_spine": story_usage,
        "method_units": method_unit_trace,
    }
    return MethodSectionPlanV2(
        plan_id=plan_id,
        method_name=method_name,
        sections=tuple(graphs),
        argument_units=tuple(units),
        method_units=tuple(method_units),
        venue=venue,
        audience=audience,
        total_page_budget=round(total_page_budget, 3),
        incomplete_sections=incomplete,
    ), trace


def _story_spine_obligation_order(
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1],
) -> dict[str, int]:
    """Map obligation ids to their first story-spine position (organization key).

    Only exact ``linked_obligation_ids`` count; vocabulary overlap is never an
    organization binding.  The map is empty when no spine is supplied.
    """

    order: dict[str, int] = {}
    for index, node in enumerate(story_spine):
        for obligation_id in node.linked_obligation_ids:
            order.setdefault(str(obligation_id), index)
    return order


def _coalesce_remaining_claims_by_obligation(
    *,
    groups: list[tuple[str, str, str, list[AtomicClaimV3], tuple[str, ...]]],
    remaining: list[AtomicClaimV3],
) -> tuple[
    list[tuple[str, str, str, list[AtomicClaimV3], tuple[str, ...]]],
    list[AtomicClaimV3],
]:
    """Attach late claims to an existing stage through exact obligations.

    This is deliberately not a lexical clustering heuristic.  A claim joins
    a stage only when its closed ``covers_obligation_ids`` intersects the
    stage's declared obligations or those of the claims already in the
    stage.  Ambiguous matches choose the stage with the largest exact overlap
    and preserve compiler order as the stable tie-break.  Truly unbound
    claims remain available to the generic fallback.
    """

    mutable = [
        [group_id, heading, purpose, list(selected), list(obligation_ids)]
        for group_id, heading, purpose, selected, obligation_ids in groups
    ]
    unassigned: list[AtomicClaimV3] = []
    for claim in remaining:
        claim_obligations = {
            str(item) for item in claim.covers_obligation_ids if str(item)
        }
        candidates: list[tuple[int, int]] = []
        if claim_obligations:
            for index, group in enumerate(mutable):
                group_obligations = set(_closed_group_obligation_ids(
                    group[4], group[3],
                ))
                overlap = len(claim_obligations.intersection(group_obligations))
                if overlap:
                    candidates.append((overlap, index))
        if not candidates:
            unassigned.append(claim)
            continue
        _overlap, target = max(candidates, key=lambda item: (item[0], -item[1]))
        mutable[target][3].append(claim)
        mutable[target][4] = list(_closed_group_obligation_ids(
            mutable[target][4], mutable[target][3],
        ))
    return (
        [
            (
                str(group[0]),
                str(group[1]),
                str(group[2]),
                list(group[3]),
                tuple(group[4]),
            )
            for group in mutable
        ],
        unassigned,
    )


def _closed_group_obligation_ids(
    declared_obligation_ids: Any,
    selected_claims: Any,
) -> tuple[str, ...]:
    """Return the obligations owned by one compiler stage.

    ``covers_obligation_ids`` on an atomic claim is evidence coverage, not a
    section-membership instruction.  In particular, callback claims often
    repeat a broad set of possible obligations.  The semantic-stage group's
    declared set is therefore authoritative whenever it exists.  Singleton
    claim coverage is safe to add for legacy groups that omitted one exact
    edge; a multi-obligation claim is only used as a fallback when the group
    has no declaration at all.
    """

    declared = tuple(dict.fromkeys(
        str(value).strip()
        for value in (declared_obligation_ids or ())
        if str(value).strip()
    ))
    result = list(declared)
    claims = tuple(selected_claims or ())
    for claim in claims:
        covered = tuple(dict.fromkeys(
            str(value).strip()
            for value in (getattr(claim, "covers_obligation_ids", ()) or ())
            if str(value).strip()
        ))
        if len(covered) == 1 or not declared:
            result.extend(value for value in covered if value not in result)
    return tuple(result)


def _group_organization_key(group: Any, spine_order: dict[str, int]) -> tuple[int, int, str]:
    """Sort key: story-spine position first, then compiler priority, then id.

    Stage groups whose obligations appear in the author story spine are placed
    in spine order; groups with no spine binding come after every spine-bound
    group, still ordered by their compiler organization priority.  This makes
    the author's story the section-organization spine while preserving the
    existing deterministic order when no spine is supplied.
    """

    bound = [
        spine_order[str(obligation_id)]
        for obligation_id in getattr(group, "covers_obligation_ids", ())
        if str(obligation_id) in spine_order
    ]
    if bound:
        return (min(bound), getattr(group, "organization_priority", 0), str(getattr(group, "stage_id", "")))
    return (
        len(spine_order) + getattr(group, "organization_priority", 0),
        getattr(group, "organization_priority", 0),
        str(getattr(group, "stage_id", "")),
    )


#: Completeness statuses materialized as candidate argument units when no
#: supported claim group realizes them.  ``unverified_by_repository`` rows
#: stay in the review sidecar (research-open state); ``out_of_scope`` rows
#: are never written.
_CANDIDATE_ROW_STATUSES: frozenset[str] = frozenset({
    "partially_supported_by_repository",
    "author_confirmation_required",
    "explicit_code_gap",
    "external_evidence_required",
    "formalization_required",
    "paper_code_mismatch",
})


class _CandidateRowEntry:
    """One completeness row materialized as a candidate argument unit."""

    __slots__ = ("row", "story_node", "obligation_id")

    def __init__(self, row: Any, story_node: Any | None) -> None:
        self.row = row
        self.story_node = story_node
        self.obligation_id = str(row.obligation_id)


def _realized_obligation_ids(
    groups: list[tuple[str, str, str, list[AtomicClaimV3], tuple[str, ...]]],
    claim_by_id: dict[str, AtomicClaimV3],
) -> set[str]:
    """Obligation ids already realized by claim-based argument units.

    A row is realized when the compiler stage explicitly owns it, or when a
    legacy stage has one exact singleton claim edge.  A broad multi-obligation
    claim must not make unrelated author rows disappear from the candidate
    path.
    """

    realized: set[str] = set()
    for _group_id, _heading, _purpose, selected, obligation_ids in groups:
        realized.update(_closed_group_obligation_ids(obligation_ids, selected))
    return realized


def _row_links_organization(row: Any, story_node: Any | None) -> bool:
    obligation_id = str(getattr(row, "obligation_id", "") or "")
    story_id = str(getattr(story_node, "story_node_id", "") or "")
    role = str(getattr(row, "role", "") or "")
    return (
        "ORGANIZATION" in obligation_id.upper()
        or "ORGANIZATION" in story_id.upper()
        or role.strip().lower() == "organization"
    )


def _candidate_buckets_from_story_and_completeness(
    *,
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1],
    completeness: MethodCompletenessMatrixV1 | None,
    realized_obligation_ids: set[str],
) -> list[tuple[str, list[_CandidateRowEntry]]]:
    """Candidate-only sections from unrealized story/completeness rows.

    partial / author-confirmation / explicit-gap / external / formalization /
    mismatch rows become candidate argument units (never verified-capable);
    ``out_of_scope`` rows are skipped.  Organization story nodes remain
    section anchors even when the completeness row is still
    ``unverified_by_repository``.  Buckets are keyed by the story node
    title when the row is linked, else the row statement/role.
    """

    if completeness is None:
        return []
    story_node_by_obligation: dict[str, AuthorStoryNodeV1] = {}
    for node in story_spine:
        for obligation_id in node.linked_obligation_ids:
            story_node_by_obligation.setdefault(str(obligation_id), node)
    buckets: list[tuple[str, list[_CandidateRowEntry]]] = []
    bucket_by_heading: dict[str, int] = {}
    for row in completeness.items:
        story_node = story_node_by_obligation.get(row.obligation_id)
        is_org = _row_links_organization(row, story_node)
        status = str(row.status)
        if status == "out_of_scope":
            continue
        if status not in _CANDIDATE_ROW_STATUSES and not (
            is_org and status != "supported_by_repository"
        ):
            continue
        if row.obligation_id in realized_obligation_ids:
            continue
        heading = (
            story_node.title
            if story_node is not None and story_node.title.strip()
            else (row.statement or row.role or f"Method point {row.obligation_id}")
        )
        heading, heading_constraints = _planning_section_heading(
            heading,
            bucket=[_CandidateRowEntry(row, story_node)],
        )
        key = " ".join(re.findall(r"[a-z0-9]+", heading.lower())) or row.obligation_id
        if key not in bucket_by_heading:
            bucket_by_heading[key] = len(buckets)
            buckets.append((heading, [_CandidateRowEntry(row, story_node)]))
        else:
            buckets[bucket_by_heading[key]][1].append(_CandidateRowEntry(row, story_node))
    return buckets


_IMPERATIVE_HEAD_WORDS = frozenset({
    "initialize",
    "compute",
    "define",
    "set",
    "use",
    "apply",
    "build",
    "create",
    "update",
    "construct",
    "derive",
    "calculate",
    "encode",
    "decode",
    "train",
    "learn",
    "select",
    "extract",
    "aggregate",
    "normalize",
    "sample",
    "project",
    "embed",
})


def _heading_is_author_instruction(heading: str) -> bool:
    """Short imperative author instructions should fold into claim sections."""

    text = str(heading or "").strip()
    if not text:
        return False
    words = text.split()
    if not words:
        return False
    first = re.sub(r"[^a-z]", "", words[0].casefold())
    if first in _IMPERATIVE_HEAD_WORDS:
        return True
    if len(words) <= 16 and text.endswith(".") and not text.endswith("..."):
        return True
    return False


def _bucket_links_organization(bucket: tuple[str, list[Any]]) -> bool:
    """True when the bucket is an author organization-spine node.

    Long organization headings (multi-clause stage titles) must not be
    treated as leftover author-sentence fragments and Jaccard-merged into
    a neighboring stage.
    """

    for item in bucket[1]:
        if not isinstance(item, _CandidateRowEntry):
            continue
        obligation_id = str(item.obligation_id or "")
        story_id = str(getattr(item.story_node, "story_node_id", "") or "")
        if "ORGANIZATION" in obligation_id.upper() or "ORGANIZATION" in story_id.upper():
            return True
    return False


def _bucket_is_leftover_author_statement(bucket: tuple[str, list[Any]]) -> bool:
    if not bucket[1]:
        return False
    if _bucket_links_organization(bucket):
        return False
    if not all(isinstance(item, _CandidateRowEntry) for item in bucket[1]):
        return False
    heading = str(bucket[0] or "").strip()
    source = _bucket_story_text(bucket)
    coherent = coherent_heading(
        heading,
        limit=120,
        intended_role=_bucket_intended_role(bucket[1]),
        source_text=source or heading,
    )
    return (
        _heading_is_author_instruction(heading)
        or len(heading.split()) > 12
        or len(heading) > 96
        or heading_is_truncated(coherent)
    )


def _fold_leftover_author_statement_buckets(
    *,
    claim_buckets: list[tuple[str, list[Any]]],
    candidate_buckets: list[tuple[str, list[_CandidateRowEntry]]],
) -> list[tuple[str, list[_CandidateRowEntry]]]:
    """Fold truncated author-sentence candidate buckets into claim sections."""

    if not claim_buckets or not candidate_buckets:
        return candidate_buckets
    claim_tokens = [
        _section_cluster_tokens(_bucket_story_text(bucket))
        for bucket in claim_buckets
    ]
    retained: list[tuple[str, list[_CandidateRowEntry]]] = []
    for bucket in candidate_buckets:
        if _bucket_links_organization(bucket) or not _bucket_is_leftover_author_statement(bucket):
            retained.append(bucket)
            continue
        tokens = _section_cluster_tokens(_bucket_story_text(bucket))
        scores = [
            len(tokens & target) / max(1, len(tokens | target))
            for target in claim_tokens
        ]
        if scores and max(scores) > 0:
            target_index = scores.index(max(scores))
        else:
            target_index = len(claim_buckets) - 1
        claim_buckets[target_index][1].extend(bucket[1])
    return retained


def _graph_stable_key(graph: SectionArgumentGraphV1) -> tuple[str, ...]:
    brief_ids = tuple(sorted(str(value) for value in graph.primary_brief_ids if str(value).strip()))
    story_ids = tuple(sorted(str(value) for value in graph.story_node_ids if str(value).strip()))
    if brief_ids or story_ids:
        return tuple(sorted(set(brief_ids) | set(story_ids)))
    unit_ids = tuple(sorted(str(value) for value in graph.argument_unit_ids if str(value).strip()))
    return unit_ids


def _stabilize_plan_section_ids(
    *,
    units: list[MethodArgumentUnitV1],
    graphs: list[SectionArgumentGraphV1],
    prior_plan: MethodSectionPlanV2,
) -> tuple[list[MethodArgumentUnitV1], list[SectionArgumentGraphV1]]:
    """Reuse prior ``MA-S*`` ids when section binding keys still match."""

    prior_by_key: dict[tuple[str, ...], str] = {}
    for graph in prior_plan.sections:
        key = _graph_stable_key(graph)
        if key and graph.section_id not in prior_by_key.values():
            prior_by_key[key] = graph.section_id
    remap: dict[str, str] = {}
    for graph in graphs:
        key = _graph_stable_key(graph)
        prior_id = prior_by_key.get(key)
        if prior_id and prior_id != graph.section_id:
            remap[graph.section_id] = prior_id
    if not remap:
        return units, graphs
    updated_units: list[MethodArgumentUnitV1] = []
    for unit in units:
        new_unit = unit
        for old_section, new_section in remap.items():
            if unit.argument_unit_id.startswith(f"{old_section}:"):
                new_unit = unit.model_copy(update={
                    "argument_unit_id": unit.argument_unit_id.replace(
                        old_section, new_section, 1
                    ),
                })
                break
        updated_units.append(new_unit)
    updated_graphs: list[SectionArgumentGraphV1] = []
    for graph in graphs:
        new_section = remap.get(graph.section_id, graph.section_id)
        updated_graphs.append(graph.model_copy(update={"section_id": new_section}))
    return updated_units, updated_graphs


def _merge_plan_buckets(
    *,
    claim_buckets: list[tuple[str, list[Any]]],
    candidate_buckets: list[tuple[str, list[_CandidateRowEntry]]],
    spine_obligation_order: dict[str, int],
) -> list[tuple[str, list[Any]]]:
    """Merge claim and candidate buckets in story-spine order.

    Buckets bound to the story spine are placed by their first spine position;
    unbound buckets follow in their construction order.  The sentinel keeps
    the deterministic tie-break (original index) stable.
    """

    def _bucket_obligations(bucket: tuple[str, list[Any]]) -> set[str]:
        obligations: set[str] = set()
        for item in bucket[1]:
            if isinstance(item, _CandidateRowEntry):
                obligations.add(item.obligation_id)
                continue
            obligations.update(str(obligation_id) for obligation_id in item[4])
        return obligations

    def _spine_key(index: int, bucket: tuple[str, list[Any]]) -> tuple[int, int]:
        bound = [
            spine_obligation_order[obligation_id]
            for obligation_id in _bucket_obligations(bucket)
            if obligation_id in spine_obligation_order
        ]
        if bound:
            return (min(bound), index)
        return (len(spine_obligation_order) + index, index)

    merged: list[tuple[str, list[Any]]] = [
        *claim_buckets,
        *candidate_buckets,
    ]
    return [bucket for _key, bucket in sorted(
        ((_spine_key(index, bucket), bucket) for index, bucket in enumerate(merged)),
        key=lambda item: item[0],
    )]


_SECTION_CLUSTER_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "and", "as", "by", "for", "from", "in", "into", "of",
    "on", "or", "the", "to", "via", "with", "method", "framework",
    "module", "mechanism", "system", "approach", "design", "process",
})


def _section_cluster_tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", str(value).lower())
        if len(token) > 2 and token not in _SECTION_CLUSTER_STOPWORDS
    }


def _truncate_heading(
    value: str,
    *,
    limit: int = 120,
    intended_role: str = "",
    source_text: str = "",
) -> str:
    """Bound a heading at a complete clause, never a dangling connective."""

    return coherent_heading(
        value,
        limit=limit,
        intended_role=intended_role,
        source_text=source_text,
    )


def _planning_section_heading(
    heading: str,
    *,
    bucket: list[Any],
    limit: int = 120,
) -> tuple[str, tuple[str, ...]]:
    """Structural planning heading plus Writer-facing heading constraints.

    Author statements stay in constraints; truncated statement fragments are
  never promoted to the section graph heading.
    """

    role = _bucket_intended_role(bucket)
    source = _bucket_story_text((heading, bucket)).strip() or str(heading or "").strip()
    raw = " ".join(str(heading or "").split()).strip()
    constraints: list[str] = [
        "writer_must_produce_heading_text",
        f"max_length:{limit}",
        "must_not_use_truncated_author_statement",
    ]
    if source:
        constraints.append(f"author_statement:{source}")
    basis = raw
    if (
        len(raw) > 96
        or len(raw.split()) > 12
        or heading_is_truncated(coherent_heading(raw, limit=limit, intended_role=role, source_text=source or raw))
    ):
        basis = source or raw
    structural = coherent_heading(
        basis,
        limit=limit,
        intended_role=role,
        source_text=source or basis,
    )
    return structural, tuple(dict.fromkeys(constraints))


def _method_unit_texts(value: Any) -> tuple[str, ...]:
    """Read only scalar semantic values from an authoring field."""

    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if value is None or isinstance(value, dict):
        return ()
    try:
        return tuple(
            str(item).strip()
            for item in value
            if str(item).strip() and not isinstance(item, (dict, list, tuple))
        )
    except TypeError:
        text = str(value).strip()
        return (text,) if text else ()


_READER_SLOT_CODE_STOPWORDS = frozenset({
    "self", "cfg", "torch", "nn", "functional", "module", "modules",
    "forward", "call", "result",
})

_READER_SLOT_PREDICATE_PHRASES = {
    "computes_formula": "compute formula",
    "computes": "compute",
    "calls": "uses",
    "normalizes": "normalize",
    "concatenates": "concatenate",
    "reduces": "reduce",
    "sorts_by": "sort",
    "branches_on": "branch when",
    "configured_by": "enables",
    "loads_weights": "enable",
    "returns": "return",
    "emits": "emit",
    "outputs": "output",
    "writes_back": "write back",
}

_READER_SLOT_TERM_EXPANSIONS = {
    "logsumexp": ("log", "sum", "exp"),
    "pos_sim": ("positive", "similarity"),
    "neg_sim": ("negative", "similarity"),
    "neg_sims": ("negative", "similarities"),
    "all_sims": ("all", "similarities"),
    "dropout1": ("first", "dropout"),
    "dropout2": ("second", "dropout"),
    "top_k": ("top", "k"),
    "mrr": ("mean", "reciprocal", "rank"),
    # These aliases are semantic projections, not source facts.  They keep
    # the harness anchor stable when a Writer changes number, tense, or the
    # usual noun/verb form of an operation.
    "positional": ("position",),
    "positions": ("position",),
    "normalizes": ("normalize",),
    "normalization": ("normalize",),
    "normalized": ("normalize",),
    "retriever": ("retriever", "retrieve"),
    "retrieves": ("retriever", "retrieve"),
    "retrieval": ("retrieval", "retrieve"),
    "reranker": ("reranker", "rank"),
    "rerank": ("rerank", "rank"),
    "reranking": ("rerank", "rank"),
    "attention": ("attention", "attend"),
    "attends": ("attention", "attend"),
    "attending": ("attention", "attend"),
    "embeddings": ("embedding",),
    "documents": ("document",),
    "passages": ("passage",),
    "shared": ("shared",),
    "dedicated": ("dedicated",),
    "masked": ("masked",),
    "encoding": ("encode",),
}


def _reader_facing_slot_terms(value: Any) -> tuple[str, ...]:
    """Project a code-shaped value into short reader-level lexical terms.

    This projection is only a Binder hint.  Fact/claim ids and authority
    lanes remain on the sidecar, so shortening an identifier cannot create
    repository authority.  Keeping the projection here, next to the frame
    builder, also prevents the Writer from receiving a second source-derived
    interpretation of the operation.
    """

    text = str(value or "").strip()
    if not text:
        return ()
    text = re.sub(r"\bresult\s*=\s*", " ", text, flags=re.I)
    terms: list[str] = []
    for raw in re.findall(r"[A-Za-z_][A-Za-z0-9_.]*|[0-9]+", text):
        # A qualified call is represented by its useful terminal name; the
        # generic prefixes (torch, self.cfg, and similar) are not prose.
        pieces = re.split(r"[._]+", raw)
        for piece in pieces:
            if not piece:
                continue
            for token in re.split(r"[_\-]+|(?<=[a-z0-9])(?=[A-Z])", piece):
                token = token.casefold()
                if not token or token in _READER_SLOT_CODE_STOPWORDS:
                    continue
                expansion = _READER_SLOT_TERM_EXPANSIONS.get(token)
                candidates = expansion or (token,)
                for candidate in candidates:
                    if (
                        candidate in _READER_SLOT_CODE_STOPWORDS
                        or (len(candidate) < 3 and not candidate.isdigit())
                    ):
                        continue
                    if candidate not in terms:
                        terms.append(candidate)
    return tuple(terms)


def _reader_facing_slot_semantic_atom(slot: SemanticFlowSlotV1) -> str:
    """Build a compact semantic anchor for one closed flow slot.

    The old anchor serialized ``subject predicate operands``.  That was safe
    as an identity string but almost never occurred in natural Method prose
    (for example ``self.dropout2(src2)``).  The new anchor retains the
    operation meaning, operands, result, and guard in reader-facing terms
    while leaving exact source ids in ``allowed_anchor_ids``.
    """

    predicate = str(getattr(slot, "predicate", "") or "").strip().casefold()
    operands = tuple(
        str(value).strip()
        for value in (getattr(slot, "operands", ()) or ())
        if str(value).strip()
    )
    terms: list[str] = []
    result_terms: list[str] = []
    for value in operands:
        target = result_terms if re.search(r"\bresult\s*=", value, flags=re.I) else terms
        for term in _reader_facing_slot_terms(value):
            if term not in target:
                target.append(term)
    for value in (getattr(slot, "produced_entities", ()) or ()):
        for term in _reader_facing_slot_terms(value):
            if term not in terms:
                terms.append(term)
    conditions: list[str] = []
    for value in (getattr(slot, "conditions", ()) or ()):
        for term in _reader_facing_slot_terms(value):
            if term not in conditions:
                conditions.append(term)

    action = _READER_SLOT_PREDICATE_PHRASES.get(predicate, predicate.replace("_", " "))
    compact_terms: tuple[str, ...] = ()
    lowered_operands = " ".join(operands).casefold()
    if predicate in {"return", "returns", "emits", "outputs"}:
        # Return slots often carry implementation names such as ``src`` or
        # ``shared_attn_weights``.  The reader-facing obligation is the
        # returned artifact, not those local variable names.
        if "weight" in lowered_operands and (
            "attn" in lowered_operands or "attention" in lowered_operands
        ):
            compact_terms = ("attention", "weights")
    if predicate == "computes_formula" and any("+" in value for value in operands):
        action = (
            "combines"
            if any(
                "shared" in value.casefold() and "dedicated" in value.casefold()
                for value in operands
            )
            else "adds"
        )
        # A residual attention update is normally written with implementation
        # names such as ``src``, ``shared_out`` and ``dropout1``.  Those names
        # are useful in the sidecar, but they are not the reader-facing
        # language used by Method prose.  Project this specific operation to
        # the stable semantics that a sentence can actually state: attention
        # outputs are combined, dropout is applied, and the result is added
        # through a residual connection.  The source span/fact ids remain the
        # authority; this is only the lexical Binder hint.
        if (
            "shared" in lowered_operands
            and "dedicated" in lowered_operands
            and "dropout" in lowered_operands
            and re.search(r"\bsrc\s*\+", lowered_operands)
        ):
            compact_terms = ("attention", "dropout", "residual")
    elif predicate == "computes_formula" and any(
        "dropout1" in value.casefold() or "dropout2" in value.casefold()
        for value in operands
    ):
        action = "applies dropout"
        if any("dropout2" in value.casefold() for value in operands):
            action = "applies second dropout"
    elif predicate == "calls":
        lowered = " ".join(terms)
        if "retriever" in lowered or "retrieve" in lowered:
            action = "retrieves"
        elif "calculate" in lowered or "metric" in lowered:
            action = "calculates"
    elif predicate == "reduces" and any(term in terms for term in ("mean", "average")):
        action = "averages"

    # Keep the lexical anchor concise enough for a paraphrased sentence to
    # cover it.  Result terms are placed last but are retained even when a
    # source operation has many implementation operands.  The subject is
    # deliberately not included: source component names (for example a
    # project-specific class) are not reader-level operation evidence and
    # would make a correct paraphrase fail merely because it omits that name.
    selected_terms = list(compact_terms or terms[:8])
    if not compact_terms:
        selected_terms.extend(
            term for term in result_terms[:6] if term not in selected_terms
        )
    parts = [action, *selected_terms]
    if conditions:
        parts.extend(("when", *conditions))
    # Keep anchors bounded.  The target remains closed by the source ids; the
    # lexical hint only needs enough independent terms for a unique sentence.
    return " ".join(dict.fromkeys(part for part in parts if part))[:360]


def _reader_facing_facet_semantic_atom(facet: Any, *, fallback: str = "") -> str:
    """Make a short facet anchor from its semantic fields.

    Facet fields are already authoring-level text, but formula goals and long
    operation statements can span several sentences.  Preserve their
    distinctive terms instead of asking the Binder to match the full source
    statement as one opaque atom.
    """

    fields = getattr(facet, "semantic_fields", {}) or {}
    if not isinstance(fields, dict):
        return str(fallback or "").strip()
    priority = (
        "formula_goal", "operation", "transformation", "subject", "inputs",
        "outputs", "conditions", "interface", "boundary", "guarantee",
    )
    selected: list[str] = []
    for key in priority:
        value = fields.get(key)
        values = _method_unit_texts(value)
        if not values:
            continue
        # The first sentence carries the operation label and the distinctive
        # nouns for ordinary facets.  Formula goals need a later objective
        # sentence too, so retain up to two sentences for that field.
        text = " ".join(values)
        sentences = [
            item.strip() for item in re.split(r"(?<=[.!?])\s+", text)
            if item.strip()
        ]
        keep = sentences[:2] if key == "formula_goal" else sentences[:1]
        selected.extend(keep)
        if selected:
            break
    if not selected:
        selected = [str(fallback or "").strip()]
    tokens = _reader_facing_slot_terms(" ".join(selected))
    return " ".join(tokens[:24]) or str(fallback or "").strip()


def _method_unit_alignment_projection(
    facet_id: str,
    alignment_by_id: dict[str, Any],
) -> dict[str, Any]:
    """Project one facet alignment into MethodUnit-owned handles."""

    alignment = alignment_by_id.get(facet_id)
    statuses: list[str] = []
    span_ids: list[str] = []
    fact_ids: list[str] = []
    claim_ids: list[str] = []
    equation_ids: list[str] = []
    conditions: list[str] = []
    operations: list[dict[str, Any]] = []
    symbol_ids: list[str] = []
    shape_hints: list[str] = []
    return_values: list[str] = []
    signatures: list[dict[str, Any]] = []

    def add_ids(target: list[str], value: Any) -> None:
        if isinstance(value, str):
            values = (value,)
        else:
            try:
                values = tuple(value or ())
            except TypeError:
                values = ()
        for item in values:
            text = str(item or "").strip()
            if text and text not in target:
                target.append(text)

    def value_of(item: Any, key: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    def record_operation(atom: dict[str, Any]) -> None:
        add_ids(symbol_ids, (
            value_of(atom, "symbol_id"), value_of(atom, "symbol"),
            value_of(atom, "entry_symbol_id"),
        ))
        raw_shapes = (
            *_method_unit_texts(value_of(atom, "shape_or_type_hints", ())),
            *_method_unit_texts(value_of(atom, "shape_hints", ())),
        )
        add_ids(shape_hints, raw_shapes)
        predicate = str(
            value_of(atom, "predicate") or value_of(atom, "operation")
            or value_of(atom, "operation_id") or ""
        ).strip()
        operands = _method_unit_texts(value_of(atom, "operands", ()))
        result = str(
            value_of(atom, "result") or value_of(atom, "output")
            or value_of(atom, "return_value") or ""
        ).strip()
        if predicate.casefold() in {"return", "returns", "emits", "outputs", "writes_back"}:
            if result and result not in return_values:
                return_values.append(result)
        if predicate or operands or result:
            signatures.append({
                "predicate": predicate,
                "operands": list(dict.fromkeys(operands)),
                "result": result,
                "guard": str(value_of(atom, "guard") or "").strip(),
                "shape_or_type_hints": list(dict.fromkeys(
                    str(item).strip() for item in raw_shapes if str(item).strip()
                )),
                "source_span_id": str(
                    value_of(atom, "source_span_id") or value_of(atom, "span_id") or ""
                ).strip(),
            })

    def add_excerpt(excerpt: Any) -> None:
        span_id = str(value_of(excerpt, "span_id", "") or "").strip()
        exact = str(value_of(excerpt, "exact_excerpt", "") or "").strip()
        add_ids(span_ids, (span_id,))
        add_ids(fact_ids, value_of(excerpt, "fact_ids", ()))
        add_ids(claim_ids, value_of(excerpt, "claim_ids", ()))
        add_ids(equation_ids, value_of(excerpt, "equation_ids", ()))
        raw_atoms = value_of(excerpt, "operation_atoms", ())
        for atom_index, raw_atom in enumerate(raw_atoms or ()):
            if isinstance(raw_atom, dict):
                atom = dict(raw_atom)
                atom.setdefault("source_span_id", span_id)
                atom.setdefault("exact_excerpt", exact)
            else:
                atom_text = str(raw_atom or "").strip()
                if not atom_text:
                    continue
                atom = {
                    "operation_id": f"aligned-operation:{facet_id}:{len(operations) + 1}",
                    "predicate": "aligned_operation",
                    "description": atom_text,
                    "source_span_id": span_id,
                    "exact_excerpt": exact,
                }
            if atom not in operations:
                operations.append(atom)
                record_operation(atom)

    if alignment is None:
        return {
            "statuses": (), "span_ids": (), "fact_ids": (), "claim_ids": (),
            "equation_ids": (), "conditions": (), "operations": (),
        }
    add_ids(statuses, (value_of(alignment, "status", "") or ""))
    for name, target in (
        ("bound_span_ids", span_ids),
        ("bound_fact_ids", fact_ids),
        ("bound_claim_ids", claim_ids),
        ("bound_equation_ids", equation_ids),
    ):
        add_ids(target, value_of(alignment, name, ()) or ())
    for excerpt in (value_of(alignment, "exact_excerpts", ()) or ()):
        add_excerpt(excerpt)
    for binding in (value_of(alignment, "field_bindings", ()) or ()):
        add_ids(statuses, (value_of(binding, "status", "") or ""))
        for name, target in (
            ("bound_span_ids", span_ids),
            ("bound_fact_ids", fact_ids),
            ("bound_claim_ids", claim_ids),
            ("bound_equation_ids", equation_ids),
            ("active_path_conditions", conditions),
        ):
            add_ids(target, value_of(binding, name, ()) or ())
        for excerpt in (value_of(binding, "exact_excerpts", ()) or ()):
            add_excerpt(excerpt)
    for raw_atom in (value_of(alignment, "operation_atoms", ()) or ()):
        atom = dict(raw_atom) if isinstance(raw_atom, dict) else {
            "operation": str(raw_atom or "").strip()
        }
        if atom and atom not in operations:
            operations.append(atom)
            record_operation(atom)
    for signature in (value_of(alignment, "formalizable_signatures", ()) or ()):
        if isinstance(signature, dict) and signature not in signatures:
            signatures.append(dict(signature))
    add_ids(shape_hints, value_of(alignment, "shape_or_type_hints", ()) or ())
    add_ids(return_values, value_of(alignment, "return_value_descriptors", ()) or ())
    return {
        "statuses": tuple(statuses),
        "span_ids": tuple(span_ids),
        "fact_ids": tuple(fact_ids),
        "claim_ids": tuple(claim_ids),
        "equation_ids": tuple(equation_ids),
        "conditions": tuple(conditions),
        "operations": tuple(operations),
        "symbol_ids": tuple(symbol_ids),
        "shape_hints": tuple(shape_hints),
        "return_values": tuple(return_values),
        "signatures": tuple(signatures),
    }


def _method_unit_semantic_values(
    facets: list[Any],
) -> dict[str, tuple[str, ...]]:
    """Collect reader-level fields without inventing values."""

    inputs: list[str] = []
    outputs: list[str] = []
    conditions: list[str] = []
    formula_roles: list[str] = []
    for facet in facets:
        fields = getattr(facet, "semantic_fields", {}) or {}
        if not isinstance(fields, dict):
            continue
        for key, value in fields.items():
            key_text = str(key).casefold()
            values = _method_unit_texts(value)
            if "input" in key_text or "source" in key_text:
                for item in values:
                    if item not in inputs:
                        inputs.append(item)
            if "output" in key_text or "effect" in key_text:
                for item in values:
                    if item not in outputs:
                        outputs.append(item)
            if "condition" in key_text or "precondition" in key_text or "assumption" in key_text:
                for item in values:
                    if item not in conditions:
                        conditions.append(item)
            if "formula_role" in key_text or "formula_roles" in key_text:
                for item in values:
                    if item not in formula_roles:
                        formula_roles.append(item)
        text = " ".join(
            str(value or "") for value in fields.values()
            if isinstance(value, str)
        ).casefold()
        role_pairs = (
            ("positional_encoding", "position"),
            ("augmentation", "augment"),
            ("attention", "attention"),
            ("InfoNCE", "infonce"),
            ("contrastive", "contrastive"),
            ("ranking", "rank"),
            ("similarity", "similarity"),
            ("retrieval", "retriev"),
        )
        for label, needle in role_pairs:
            if needle in text and label not in formula_roles:
                formula_roles.append(label)
    return {
        "inputs": tuple(inputs),
        "outputs": tuple(outputs),
        "conditions": tuple(conditions),
        "formula_roles": tuple(formula_roles),
    }


def _witness_surface_contract(
    *,
    alignment: Any | None = None,
    projection: dict[str, Any] | None = None,
    candidate: Any | None = None,
    default_authority: str = "executable_hard",
) -> tuple[str, str, str]:
    """Return the one Writer-facing surface contract for a target.

    ``bound_span_ids`` answer whether a target has evidence; they do not
    answer whether the author's whole compound statement is supported by that
    evidence.  The old contract used the former as an ``executable_hard``
    switch, which let a partially aligned author sentence enter positive
    repository prose.  Keep that distinction deterministic at the Architect
    boundary so the Writer, Binder, and quality gates consume the same
    classification.
    """

    if candidate is not None:
        surface = str(
            getattr(candidate, "surface_mode", "") or "omit_and_review"
        ).strip() or "omit_and_review"
        render = str(
            getattr(candidate, "render_policy", "") or "deferred"
        ).strip() or "deferred"
        authority = str(
            getattr(candidate, "authority_lane", "") or default_authority
        ).strip() or default_authority
        return surface, render, authority

    alignment_status = str(
        getattr(alignment, "status", "") or "unresolved"
    ).strip().casefold()
    projected = projection or {}
    has_evidence = bool(
        projected.get("span_ids")
        or projected.get("fact_ids")
        or projected.get("claim_ids")
        or projected.get("equation_ids")
    )
    if alignment_status == "entailed" and has_evidence:
        return "repository_statement", "required", default_authority
    if alignment_status == "partial" and has_evidence:
        return "author_specification", "optional", "author_attested"
    if alignment_status == "mismatch":
        return "mismatch_statement", "optional", "author_attested"
    return "omit_and_review", "deferred", "author_attested"


def _attach_method_unit_witness_contracts(
    graphs: list[SectionArgumentGraphV1],
    units: list[MethodArgumentUnitV1] | tuple[MethodArgumentUnitV1, ...],
    *,
    argument_facets: tuple[Any, ...] | list[Any],
    facet_alignments: tuple[Any, ...] | list[Any],
    publication_field_candidates: tuple[Any, ...] | list[Any],
    unit_frames: dict[str, SemanticArgumentFrameV1] | None = None,
) -> list[SectionArgumentGraphV1]:
    """Rebuild Binder contracts after MethodUnit paragraph compaction."""

    facet_by_id = {
        str(getattr(item, "facet_id", "") or ""): item
        for item in argument_facets
        if str(getattr(item, "facet_id", "") or "").strip()
    }
    alignment_by_id = {
        str(getattr(item, "facet_id", "") or ""): item
        for item in facet_alignments
        if str(getattr(item, "facet_id", "") or "").strip()
    }
    candidates_by_id = {
        str(getattr(item, "candidate_id", "") or ""): item
        for item in publication_field_candidates
        if str(getattr(item, "candidate_id", "") or "").strip()
    }
    candidates_by_facet: dict[str, list[Any]] = {}
    for candidate in publication_field_candidates:
        facet_id = str(getattr(candidate, "facet_id", "") or "").strip()
        if facet_id:
            candidates_by_facet.setdefault(facet_id, []).append(candidate)
    units_by_id = {unit.argument_unit_id: unit for unit in units}
    enriched: list[SectionArgumentGraphV1] = []
    for graph in graphs:
        section_units = [
            units_by_id[item]
            for item in graph.argument_unit_ids
            if item in units_by_id
        ]
        section_paragraphs: list[SectionParagraphPlanV1] = []
        for paragraph in graph.paragraphs:
            targets: list[ParagraphWitnessTargetV1] = []
            for facet_id in paragraph.required_facet_ids:
                facet = facet_by_id.get(facet_id)
                semantic_fields = getattr(facet, "semantic_fields", {}) or {}
                semantic_atom = _reader_facing_facet_semantic_atom(
                    facet,
                    fallback=(
                        " ".join(
                            str(value).strip() for value in semantic_fields.values()
                            if str(value).strip()
                        )[:1200] if isinstance(semantic_fields, dict) else ""
                    ),
                )
                alignment = alignment_by_id.get(facet_id)
                alignment_projection = _method_unit_alignment_projection(
                    facet_id, alignment_by_id,
                )
                surface_mode, render_policy, authority_lane = _witness_surface_contract(
                    alignment=alignment,
                    projection=alignment_projection,
                )
                candidates = candidates_by_facet.get(facet_id, [])
                excerpts = tuple(dict.fromkeys(
                    str(value).strip()
                    for candidate in candidates
                    for value in (getattr(candidate, "exact_excerpts", ()) or ())
                    if str(value).strip()
                )) or tuple(
                    str(getattr(item, "exact_excerpt", "") or "").strip()
                    for item in (getattr(alignment, "exact_excerpts", ()) or ())
                    if str(getattr(item, "exact_excerpt", "") or "").strip()
                )
                targets.append(ParagraphWitnessTargetV1(
                    target_id=facet_id,
                    target_kind="facet",
                    semantic_atom=semantic_atom or facet_id,
                    paper_role=str(getattr(facet, "facet_kind", "mechanism") or "mechanism"),
                    allowed_anchor_ids=tuple(dict.fromkeys([
                        *[
                            value
                            for candidate in candidates
                            for value in (getattr(candidate, "bound_span_ids", ()) or ())
                        ],
                        *alignment_projection["span_ids"],
                    ])),
                    allowed_exact_excerpts=tuple(dict.fromkeys(excerpts)),
                    authority_lane=authority_lane,
                    surface_mode=surface_mode,
                    render_policy=render_policy,
                ))
            for candidate_id in paragraph.required_field_candidate_ids:
                candidate = candidates_by_id.get(candidate_id)
                if candidate is None:
                    continue
                targets.append(ParagraphWitnessTargetV1(
                    target_id=candidate_id,
                    target_kind="field",
                    semantic_atom=str(getattr(candidate, "semantic_atom", "") or candidate_id),
                    paper_role=str(getattr(candidate, "field_name", "mechanism") or "mechanism"),
                    required_polarity=str(getattr(candidate, "polarity", "unknown") or "unknown"),
                    required_conditions=tuple(getattr(candidate, "conditions", ()) or ()),
                    allowed_anchor_ids=tuple(getattr(candidate, "bound_span_ids", ()) or ()),
                    allowed_exact_excerpts=tuple(getattr(candidate, "exact_excerpts", ()) or ()),
                    authority_lane=_witness_surface_contract(
                        candidate=candidate,
                    )[2],
                    surface_mode=_witness_surface_contract(
                        candidate=candidate,
                    )[0],
                    render_policy=_witness_surface_contract(
                        candidate=candidate,
                    )[1],
                ))
            frames = [
                unit_frames.get(unit.argument_unit_id)
                if unit_frames is not None
                else unit.semantic_frame
                for unit in section_units
                if unit.argument_unit_id in paragraph.argument_unit_ids
            ]
            frames = [frame for frame in frames if frame is not None]
            # A compact MethodUnit may own more than one argument unit.  The
            # old first-frame lookup silently dropped publication slots owned
            # by the later unit, leaving a required slot without a Binder
            # contract.  Keep the lookup paragraph-scoped and merge all
            # contributing frames deterministically.
            slot_by_id = {
                slot.slot_id: slot
                for frame in frames
                for slot in frame.slots
            }
            for slot_id in paragraph.required_publication_slot_ids:
                slot = slot_by_id.get(slot_id)
                if slot is None:
                    continue
                targets.append(ParagraphWitnessTargetV1(
                    target_id=slot_id,
                    target_kind="slot",
                    semantic_atom=_reader_facing_slot_semantic_atom(slot) or slot_id,
                    paper_role=str(slot.role),
                    required_conditions=tuple(slot.conditions),
                    allowed_anchor_ids=tuple((*slot.fact_ids, *slot.claim_ids)),
                    authority_lane=slot.authority_lanes[0] if slot.authority_lanes else "executable_hard",
                    surface_mode="repository_statement",
                    render_policy="required",
                ))
            edge_by_id = {
                edge.relation_id: edge
                for frame in frames
                for edge in frame.edges
            }
            for edge_id in paragraph.required_edge_ids:
                edge = edge_by_id.get(edge_id)
                if edge is None:
                    continue
                targets.append(ParagraphWitnessTargetV1(
                    target_id=edge_id,
                    target_kind="edge",
                    semantic_atom=f"{edge.source_symbol} {edge.relation_type} {edge.target_symbol}",
                    paper_role="data_flow",
                    required_conditions=tuple(edge.conditions),
                    allowed_anchor_ids=tuple(edge.direct_span_ids),
                    authority_lane="executable_hard",
                    surface_mode="repository_statement",
                    render_policy="required",
                ))
            for obligation_id in paragraph.formula_obligation_ids:
                targets.append(ParagraphWitnessTargetV1(
                    target_id=obligation_id,
                    target_kind="formula",
                    semantic_atom="formal expression",
                    paper_role="formula",
                    allowed_anchor_ids=(obligation_id,),
                    authority_lane="formal_derivation",
                    surface_mode="repository_statement",
                    render_policy="required",
                ))
            target_by_key: dict[tuple[str, str], ParagraphWitnessTargetV1] = {}
            for target in targets:
                target_by_key.setdefault((target.target_kind, target.target_id), target)
            section_paragraphs.append(paragraph.model_copy(update={
                "witness_contract": ParagraphWitnessContractV1(
                    paragraph_id=paragraph.paragraph_id,
                    rhetorical_goal=str(paragraph.paragraph_role),
                    targets=tuple(target_by_key.values()),
                ) if targets else None,
            }))
        enriched.append(graph.model_copy(update={"paragraphs": tuple(section_paragraphs)}))
    return enriched


def _closed_method_unit_slots(
    *,
    section_id: str,
    paragraph_id: str,
    original_order: Any,
    support_slots: Any,
    publication_slots: Any,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Close the paragraph slot contract before Pydantic validation.

    Support/publication slots are contract members, not display hints.  The
    plan therefore keeps every required id in the ordered sequence; any
    future LLM compaction must happen on a separate reader projection.
    """

    def dedupe(values: Any) -> tuple[str, ...]:
        if isinstance(values, str):
            values = (values,)
        try:
            return tuple(dict.fromkeys(
                str(value).strip() for value in (values or ()) if str(value).strip()
            ))
        except TypeError:
            return ()

    original = dedupe(original_order)
    support = dedupe(support_slots)
    publication = dedupe(publication_slots)
    ordered = tuple(dict.fromkeys((*original, *support, *publication)))
    required = set((*support, *publication))
    missing = tuple(sorted(required - set(ordered)))
    if missing:
        raise ValueError(
            "method_unit_slot_closure_failed:"
            f"section={section_id}:paragraph={paragraph_id}:"
            f"missing={','.join(missing)}"
        )
    return support, publication, ordered



def _preserve_incumbent_method_unit_surface(
    *,
    prior_plan: MethodSectionPlanV2,
    rebuilt_sections: list[SectionArgumentGraphV1],
) -> tuple[tuple[MethodUnitV2, ...], list[SectionArgumentGraphV1], dict[str, Any]]:
    """Keep freeze MethodUnits and their paragraph contracts.

    Facet regrouping (groups of four) is a rebuild-only organization step.
    A reused or callback-resumed plan already has reader paragraphs,
    publication slots, and formula consumers; only frames/witness metadata
    on the surrounding graph may be refreshed.
    """

    prior_by_id = {graph.section_id: graph for graph in prior_plan.sections}
    preserved: list[SectionArgumentGraphV1] = []
    for graph in rebuilt_sections:
        prior = prior_by_id.get(graph.section_id)
        if prior is None or not prior.paragraphs:
            preserved.append(graph)
            continue
        preserved.append(graph.model_copy(update={
            "paragraphs": prior.paragraphs,
            "argument_unit_ids": prior.argument_unit_ids,
        }))
    rebuilt_ids = {graph.section_id for graph in preserved}
    for prior in prior_plan.sections:
        if prior.section_id not in rebuilt_ids:
            preserved.append(prior)
    preserved = _order_context_sections_before_mechanism(
        preserved,
        units=tuple(getattr(prior_plan, "argument_units", ()) or ()),
        argument_facets=(),
    )
    return (
        tuple(prior_plan.method_units),
        preserved,
        {
            "enabled": True,
            "preserved_existing_method_units": True,
            "compaction_applied": False,
            "method_unit_count": len(prior_plan.method_units),
            "paragraph_count": sum(len(graph.paragraphs) for graph in preserved),
        },
    )


_CONTEXT_RHETORICAL_MOVES = frozenset({
    "problem_or_local_context",
    "design_objective",
    "intuition_or_rationale",
})
_TECHNICAL_FACET_KINDS = frozenset({
    "mechanism", "formula", "interface", "constraint", "guarantee",
})


def _unit_is_context_only(unit: Any) -> bool:
    """Whether an argument unit is a problem/motivation/design-intent owner."""

    role = str(getattr(unit, "section_role", "") or "").casefold()
    if role in {"motivation", "context", "problem"}:
        return True
    moves = {
        str(item or "").strip()
        for item in (getattr(unit, "allowed_expository_moves", ()) or ())
        if str(item or "").strip()
    }
    if not moves:
        return False
    leftover = moves - _CONTEXT_RHETORICAL_MOVES - {"transition_to_next_section"}
    return bool(moves & _CONTEXT_RHETORICAL_MOVES) and not leftover


def _facet_is_context_rationale(facet: Any, *, section_units: list[Any]) -> bool:
    """True for a bounded motivation/rationale/design-objective facet."""

    kind = str(getattr(facet, "facet_kind", "") or "").casefold()
    if kind == "motivation":
        return True
    fields = getattr(facet, "semantic_fields", {}) or {}
    field_keys = " ".join(str(key) for key in fields).casefold() if isinstance(fields, dict) else ""
    if any(
        token in field_keys
        for token in ("rationale", "design_objective", "motivation", "problem")
    ):
        return True
    brief_id = str(getattr(facet, "brief_id", "") or "").strip()
    if kind in _TECHNICAL_FACET_KINDS:
        return False
    for unit in section_units:
        if not _unit_is_context_only(unit):
            continue
        unit_briefs = {
            str(value).strip()
            for value in (unit.brief_order or unit.brief_ids or ())
            if str(value).strip()
        }
        if brief_id and brief_id in unit_briefs:
            return True
        if not brief_id:
            return True
    return False


def _select_representative_context_facet(
    section_facets: list[Any],
    *,
    selected_ids: set[str],
    section_units: list[Any],
) -> Any | None:
    """Keep one reader-facing rationale facet; do not promote every optional."""

    for facet in section_facets:
        facet_id = str(getattr(facet, "facet_id", "") or "").strip()
        if not facet_id or facet_id in selected_ids:
            continue
        if _facet_is_context_rationale(facet, section_units=section_units):
            return facet
    return None


def _method_unit_expected_sentence_range(
    *,
    facets: list[Any],
    argument_unit_ids: tuple[str, ...],
) -> tuple[int, int]:
    """Bounded sentence guidance from conceptual payload, not required-count."""

    context = 0
    mechanism = 0
    for facet in facets:
        kind = str(getattr(facet, "facet_kind", "") or "").casefold()
        if kind == "motivation" or _facet_is_context_rationale(facet, section_units=[]):
            context += 1
        elif kind in _TECHNICAL_FACET_KINDS or bool(getattr(facet, "required", False)):
            mechanism += 1
    payload = context + mechanism + min(2, len(tuple(
        item for item in argument_unit_ids if str(item).strip()
    )))
    if payload <= 0:
        payload = max(1, len(facets) or 1)
    low = 2 if context else 1
    high = max(low + 1, min(6, payload + (1 if context else 0)))
    return (low, high)


def _section_is_pure_context(
    graph: Any,
    *,
    units_by_id: dict[str, Any],
    facets_by_id: dict[str, Any],
) -> bool:
    """Rhetorical context section: motivation/problem without mechanism payload."""

    section_units = [
        units_by_id[item]
        for item in (getattr(graph, "argument_unit_ids", ()) or ())
        if item in units_by_id
    ]
    moves = {
        str(getattr(move, "move", "") or "").strip()
        for move in (getattr(graph, "moves", ()) or ())
        if str(getattr(move, "move", "") or "").strip()
    }
    for unit in section_units:
        moves.update(
            str(item).strip()
            for item in (getattr(unit, "allowed_expository_moves", ()) or ())
            if str(item).strip()
        )
        if str(getattr(unit, "section_role", "") or "").casefold() in {
            "motivation", "context", "problem",
        }:
            moves.add("problem_or_local_context")
    facet_ids = {
        str(facet_id).strip()
        for paragraph in (getattr(graph, "paragraphs", ()) or ())
        for facet_id in (getattr(paragraph, "required_facet_ids", ()) or ())
        if str(facet_id).strip()
    }
    kinds = {
        str(getattr(facets_by_id[facet_id], "facet_kind", "") or "").casefold()
        for facet_id in facet_ids
        if facet_id in facets_by_id
    }
    has_technical_facet = bool(kinds & _TECHNICAL_FACET_KINDS)
    has_context_facet = "motivation" in kinds
    has_context_move = bool(moves & _CONTEXT_RHETORICAL_MOVES)
    technical_moves = moves - _CONTEXT_RHETORICAL_MOVES - {"transition_to_next_section"}
    if has_technical_facet or technical_moves:
        return False
    return bool(has_context_facet or has_context_move or any(
        _unit_is_context_only(unit) for unit in section_units
    ))


def _order_context_sections_before_mechanism(
    graphs: list[Any],
    *,
    units: list[Any] | tuple[Any, ...],
    argument_facets: tuple[Any, ...] | list[Any],
) -> list[Any]:
    """Place a pure context section before mechanism when a reused plan inverts them."""

    if len(graphs) < 2:
        return graphs
    units_by_id = {
        str(getattr(unit, "argument_unit_id", "") or ""): unit
        for unit in units
        if str(getattr(unit, "argument_unit_id", "") or "").strip()
    }
    facets_by_id = {
        str(getattr(facet, "facet_id", "") or ""): facet
        for facet in argument_facets
        if str(getattr(facet, "facet_id", "") or "").strip()
    }
    kinds = [
        "context" if _section_is_pure_context(
            graph, units_by_id=units_by_id, facets_by_id=facets_by_id,
        ) else "other"
        for graph in graphs
    ]
    if "context" not in kinds or "other" not in kinds:
        return graphs
    first_other = kinds.index("other")
    if not any(
        kind == "context" for kind in kinds[first_other + 1:]
    ):
        return graphs
    context = [graph for graph, kind in zip(graphs, kinds) if kind == "context"]
    rest = [graph for graph, kind in zip(graphs, kinds) if kind != "context"]
    return [*context, *rest]


def _build_method_units_v2(
    graphs: list[SectionArgumentGraphV1],
    units: list[MethodArgumentUnitV1] | tuple[MethodArgumentUnitV1, ...],
    *,
    argument_facets: tuple[Any, ...] | list[Any],
    facet_alignments: tuple[Any, ...] | list[Any],
    publication_field_candidates: tuple[Any, ...] | list[Any],
    facts: Any | None = None,
    unit_frames: dict[str, SemanticArgumentFrameV1] | None = None,
) -> tuple[tuple[MethodUnitV2, ...], list[SectionArgumentGraphV1], dict[str, Any]]:
    """Compile bounded reader units and compact paragraph transactions."""

    if not argument_facets or not facet_alignments:
        return (), graphs, {"enabled": False, "method_unit_count": 0}
    facets = tuple(argument_facets)
    fact_by_id = {
        str(getattr(item, "fact_id", "") or ""): item
        for item in (getattr(facts, "facts", ()) or ())
        if str(getattr(item, "fact_id", "") or "").strip()
    }
    fact_ids_by_span: dict[str, list[str]] = {}
    for fact_id, fact in fact_by_id.items():
        for span_id in dict.fromkeys([
            *(getattr(fact, "direct_span_ids", ()) or ()),
            *(getattr(fact, "relation_span_ids", ()) or ()),
        ]):
            span_text = str(span_id or "").strip()
            if span_text:
                fact_ids_by_span.setdefault(span_text, []).append(fact_id)
    compile_fact_chain = None
    if fact_by_id:
        from code2paper.agentic.research_derived_authoring import (
            compile_code_fact_operation_chain,
        )
        compile_fact_chain = compile_code_fact_operation_chain
    alignment_by_id = {
        str(getattr(item, "facet_id", "") or ""): item
        for item in facet_alignments
        if str(getattr(item, "facet_id", "") or "").strip()
    }
    units_by_id = {unit.argument_unit_id: unit for unit in units}
    compiled_units: list[MethodUnitV2] = []
    compacted_graphs: list[SectionArgumentGraphV1] = []
    trace_rows: list[dict[str, Any]] = []

    for graph in graphs:
        section_units = [
            units_by_id[item]
            for item in graph.argument_unit_ids
            if item in units_by_id
        ]
        unit_briefs = {
            str(brief_id).strip()
            for unit in section_units
            for brief_id in (unit.brief_order or unit.brief_ids)
            if str(brief_id).strip()
        }
        # Once the current units carry a fresh brief projection, it is the
        # only valid section ownership source.  Graph-level brief ids belong
        # to the frozen plan and may describe a paragraph that has since been
        # split or moved.  Keep the graph fallback only for legacy plans
        # where no unit has any brief binding at all.
        section_briefs = unit_briefs or {
            str(value).strip()
            for value in (
                *getattr(graph, "primary_brief_ids", ()),
                *getattr(graph, "supporting_brief_ids", ()),
            )
            if str(value).strip()
        }
        section_facet_values = [
            facet for facet in facets
            if (
                str(getattr(facet, "brief_id", "") or "").strip() in section_briefs
                or (
                    not section_briefs and len(graphs) == 1
                    and not str(getattr(facet, "brief_id", "") or "").strip()
                )
            )
        ]
        if not section_facet_values:
            compacted_graphs.append(graph)
            continue
        selected = [
            facet for facet in section_facet_values
            if bool(getattr(facet, "required", False))
            or str(getattr(facet, "formula_expectation", "none") or "none") != "none"
        ]
        if not selected:
            selected = [
                facet for facet in section_facet_values
                if str(getattr(facet, "facet_kind", "") or "") in {"mechanism", "formula"}
            ][:1]
        selected_ids = {str(getattr(facet, "facet_id", "") or "") for facet in selected}
        if not any(
            _facet_is_context_rationale(facet, section_units=section_units)
            for facet in selected
        ):
            representative = _select_representative_context_facet(
                section_facet_values,
                selected_ids=selected_ids,
                section_units=section_units,
            )
            if representative is not None:
                selected.insert(0, representative)
                selected_ids.add(
                    str(getattr(representative, "facet_id", "") or "")
                )
        if not selected:
            compacted_graphs.append(graph)
            continue
        # Preserve an already-bound facet when a frozen plan is replayed.  It
        # is assigned to the group containing its exact argument unit below.
        old_facet_ids = {
            str(facet_id)
            for paragraph in graph.paragraphs
            for facet_id in paragraph.required_facet_ids
            if str(facet_id).strip()
        }
        for facet in section_facet_values:
            facet_id = str(getattr(facet, "facet_id", "") or "")
            if facet_id in old_facet_ids and facet_id not in selected_ids:
                selected.append(facet)
                selected_ids.add(facet_id)
        # Candidate prose needs a reader-sized mechanism paragraph, not one
        # paragraph per facet.  The previous owner-first projection made a
        # 7-paragraph EBCAR plan expand to 17 paragraphs because most briefs
        # intentionally contain one facet.  That fragmentation caused the
        # Writer to emit short caveat shells and made the paragraph/facet
        # transaction impossible to close.  Keep the author-story order and
        # compact adjacent facets into bounded groups of four.  Evidence
        # ownership remains closed below through exact fact/span/slot
        # bindings; grouping is only a Candidate organization projection.
        groups = [
            selected[index:index + 4]
            for index in range(0, len(selected), 4)
        ]
        group_unit_ids: list[tuple[str, ...]] = []
        group_brief_sets: list[set[str]] = []
        for group in groups:
            group_briefs = {
                str(getattr(facet, "brief_id", "") or "")
                for facet in group
                if str(getattr(facet, "brief_id", "") or "").strip()
            }
            group_brief_sets.append(group_briefs)
            group_units = [
                unit.argument_unit_id for unit in section_units
                if group_briefs.intersection(
                    set(unit.brief_order or unit.brief_ids)
                )
            ]
            if not group_units:
                group_units = list(graph.argument_unit_ids)
            # Keep the complete unit closure.  A paragraph may be compacted
            # from several old rows, and limiting this list to two units can
            # orphan the frame that owns a carried publication slot.
            group_unit_ids.append(tuple(dict.fromkeys(group_units)))

        formula_group_indexes = [
            index for index, group in enumerate(groups)
            if any(
                str(getattr(facet, "formula_expectation", "none") or "none") != "none"
                or str(getattr(facet, "facet_kind", "") or "") == "formula"
                for facet in group
            )
        ]
        graph_formula_index = (
            formula_group_indexes[-1]
            if formula_group_indexes else len(groups) - 1
        )
        # A semantic unit may legitimately be split across two new reader
        # paragraphs.  Do not therefore copy every old paragraph into every
        # group sharing that unit: doing so duplicates facet/field/formula
        # handles in the Binder sidecar and inflates the required-target
        # denominator.  Assign each old row to its best matching group once,
        # preferring exact facet overlap and then argument-unit overlap.  The
        # stable group index is the final tie-break for deterministic replay.
        old_rows_by_group: list[list[SectionParagraphPlanV1]] = [
            [] for _ in groups
        ]
        group_unit_sets = [set(group_units) for group_units in group_unit_ids]
        group_facet_sets = [
            {
                str(getattr(facet, "facet_id", "") or "").strip()
                for facet in group
                if str(getattr(facet, "facet_id", "") or "").strip()
            }
            for group in groups
        ]

        # A compact paragraph may contain rows from several argument units,
        # while a selected component facet may have no argument unit of its
        # own.  In that case the old row boundary is not an ownership proof:
        # it can leave attention slots in the overview paragraph and leave
        # the component paragraph with no slot at all.  Build one closed
        # section-wide slot index and assign only reader-meaningful slots to
        # the group whose facet semantics support them.  This is an
        # organizational projection; fact/claim ids and their authority stay
        # untouched.
        section_slots: dict[str, SemanticFlowSlotV1] = {}
        slot_owner_units: dict[str, list[str]] = {}
        slot_owner_briefs: dict[str, set[str]] = {}
        section_slot_order: list[str] = []
        for unit in section_units:
            frame = (
                unit_frames.get(unit.argument_unit_id)
                if unit_frames is not None
                else unit.semantic_frame
            )
            for slot in (frame.slots if frame is not None else ()):
                slot_id = str(slot.slot_id).strip()
                if not slot_id:
                    continue
                if slot_id not in section_slots:
                    section_slots[slot_id] = slot
                    section_slot_order.append(slot_id)
                slot_owner_units.setdefault(slot_id, []).append(unit.argument_unit_id)
                slot_owner_briefs.setdefault(slot_id, set()).update(
                    str(value).strip()
                    for value in (unit.brief_order or unit.brief_ids or ())
                    if str(value).strip()
                )

        def _facet_projection(facet: Any) -> dict[str, Any]:
            projection = _method_unit_alignment_projection(
                str(getattr(facet, "facet_id", "") or ""), alignment_by_id,
            )
            if not projection.get("fact_ids") and fact_ids_by_span:
                recovered_fact_ids = tuple(dict.fromkeys(
                    fact_id
                    for span_id in projection.get("span_ids", ())
                    for fact_id in fact_ids_by_span.get(str(span_id), ())
                ))
                if recovered_fact_ids:
                    projection = {
                        **projection,
                        "fact_ids": recovered_fact_ids,
                    }
            return projection

        group_evidence: list[dict[str, set[str]]] = []
        for group in groups:
            evidence = {
                "fact_ids": set(),
                "claim_ids": set(),
                "span_ids": set(),
            }
            for facet in group:
                projection = _facet_projection(facet)
                for key in evidence:
                    evidence[key].update(
                        str(value).strip()
                        for value in projection.get(key, ())
                        if str(value).strip()
                    )
            group_evidence.append(evidence)

        # These are intentionally broad semantic terms rather than
        # project-specific vocabulary.  They prevent a generic word such as
        # ``embedding`` from making two unrelated groups look distinct while
        # retaining operation words (attention, position, ranking, and so on)
        # that are useful for paragraph ownership.
        semantic_noise = frozenset({
            "the", "and", "or", "with", "from", "into", "then", "when",
            "this", "that", "for", "each", "all", "only", "using", "its",
            "their", "current", "same", "fixed", "updated", "positive",
            "negative", "query", "passage", "passages", "document",
            "documents", "embedding", "embeddings", "output", "outputs",
            "input", "inputs", "model", "module", "modules", "formula",
            "compute", "computes", "computed", "operation", "operations",
        })

        def _match_terms(value: Any) -> set[str]:
            return set(_reader_facing_slot_terms(value))

        group_facet_terms = [
            [
                _match_terms(_reader_facing_facet_semantic_atom(facet))
                for facet in group
            ]
            for group in groups
        ]
        slot_group: dict[str, int] = {}
        for slot_id in section_slot_order:
            slot = section_slots[slot_id]
            # The same fact can legitimately be present in two argument
            # frames after claim projection.  Such a duplicate has no single
            # paragraph owner until an exact evidence edge disambiguates it;
            # keep it as support rather than making one copy a hard target.
            if len(set(slot_owner_units.get(slot_id, ()))) > 1:
                continue
            # Subject names identify the component, but the component name
            # alone must not bind a low-level slot.  Score the operation,
            # operands, result and guard first; the subject is used only as a
            # secondary signal for an otherwise tied operation.
            content_text = " ".join((
                str(getattr(slot, "predicate", "") or ""),
                *(str(value) for value in (getattr(slot, "operands", ()) or ())),
                *(str(value) for value in (getattr(slot, "produced_entities", ()) or ())),
                *(str(value) for value in (getattr(slot, "conditions", ()) or ())),
            ))
            content_terms = _match_terms(content_text)
            subject_terms = _match_terms(getattr(slot, "subject", ""))
            content_terms -= semantic_noise
            subject_terms -= semantic_noise
            score_rows: list[tuple[int, int, int]] = []
            for facet_terms in group_facet_terms:
                overlaps = [
                    len(content_terms.intersection(terms))
                    for terms in facet_terms
                ]
                best = max(overlaps, default=0)
                score_rows.append((
                    best,
                    sum(1 for value in overlaps if value > 0),
                    sum(sorted(overlaps, reverse=True)[:3]),
                ))
            # A subject term can disambiguate two operation groups, but a
            # subject-only match cannot create a hard slot.  Add at most one
            # point to an existing content match.
            for index, facet_terms in enumerate(group_facet_terms):
                subject_overlap = max(
                    (len(subject_terms.intersection(terms)) for terms in facet_terms),
                    default=0,
                )
                if subject_overlap and score_rows[index][0]:
                    best, count, total = score_rows[index]
                    score_rows[index] = (best + 1, count, total + 1)

            best_score = max(score_rows, default=(0, 0, 0))
            if best_score[0] < 2:
                continue
            top_indexes = [
                index for index, score in enumerate(score_rows)
                if score == best_score
            ]
            owner_groups = [
                index for index, group_briefs in enumerate(group_brief_sets)
                if slot_owner_briefs.get(slot_id, set()).intersection(group_briefs)
            ]
            # A slot whose owning argument unit is not represented by any
            # selected facet group is not safe to promote into a paragraph's
            # publication contract.  Keep it as support unless a later
            # exact fact/claim evidence pass can assign it unambiguously.
            # This prevents an unrelated evaluation/reranking slot from
            # becoming a hard target merely because generic words such as
            # ``embedding`` or ``retrieval`` overlap with a high-level facet.
            if not owner_groups:
                continue
            chosen: int | None = None
            owner_scores = [
                (score_rows[index], index)
                for index in owner_groups
            ]
            owner_choice = (
                max(owner_scores, key=lambda item: (item[0], -item[1]))
                if owner_scores else None
            )
            # An operation that is shared by a high-level facet and several
            # component facets belongs to the component group only when the
            # component group has materially broader facet support.  This
            # moves a combined shared/dedicated operation to the component
            # paragraph without moving a generic positional operation away
            # from its owning stage.
            if owner_choice is not None:
                chosen = owner_choice[1]
                top = top_indexes[0]
                if top != chosen:
                    chosen_score = score_rows[chosen]
                    top_score = score_rows[top]
                    component_terms = content_terms.intersection({
                        "shared", "dedicated", "masked", "global", "intra",
                        "cross", "hybrid", "attention", "attend",
                    })
                    external_is_materially_stronger = (
                        top_score[0] >= chosen_score[0] + 2
                        or top_score[1] >= chosen_score[1] + 2
                        or top_score[2] >= chosen_score[2] + 4
                    )
                    if (
                        len(owner_groups) == 1
                        and not len(component_terms) >= 2
                        and top_score[0] <= chosen_score[0] + 2
                    ):
                        external_is_materially_stronger = False
                    if external_is_materially_stronger:
                        chosen = top
            elif len(top_indexes) == 1:
                chosen = top_indexes[0]
            if chosen is None and len(top_indexes) == 1:
                chosen = top_indexes[0]
            if chosen is not None:
                slot_group[slot_id] = chosen

        # A slot aligned to a single group's exact evidence can be assigned
        # even when its natural-language operation label is short.  Exact
        # evidence is only a tie breaker here, never a replacement for the
        # closed slot/fact binding.
        for slot_id, slot in section_slots.items():
            if slot_id in slot_group or len(set(slot_owner_units.get(slot_id, ()))) > 1:
                continue
            slot_facts = set(str(value) for value in (slot.fact_ids or ()))
            slot_claims = set(str(value) for value in (slot.claim_ids or ()))
            evidence_groups = [
                index for index, evidence in enumerate(group_evidence)
                if (
                    slot_facts.intersection(evidence["fact_ids"])
                    or slot_claims.intersection(evidence["claim_ids"])
                )
            ]
            owner_groups = [
                index for index, group_briefs in enumerate(group_brief_sets)
                if slot_owner_briefs.get(slot_id, set()).intersection(group_briefs)
            ]
            if len(evidence_groups) == 1 and evidence_groups[0] in owner_groups:
                slot_group[slot_id] = evidence_groups[0]
        for paragraph in graph.paragraphs:
            paragraph_units = set(paragraph.argument_unit_ids)
            paragraph_facets = {
                str(facet_id).strip()
                for facet_id in paragraph.required_facet_ids
                if str(facet_id).strip()
            }
            scores = [
                (
                    len(paragraph_facets.intersection(group_facet_sets[index])),
                    len(paragraph_units.intersection(group_unit_sets[index])),
                )
                for index in range(len(groups))
            ]
            best_score = max(scores, default=(0, 0))
            if best_score == (0, 0):
                old_rows_by_group[0].append(paragraph)
                continue
            best_index = scores.index(best_score)
            old_rows_by_group[best_index].append(paragraph)
        # Replayed rows are not an ownership proof.  In particular, a frozen
        # overview row may contain every unit in a section after an earlier
        # lossy compaction.  Once the current facet->brief->unit edge has
        # selected a group, do not append those stale unit ids back into the
        # MethodUnit; doing so recreates the cross-stage evidence wall this
        # rebuild is meant to remove.  The graph-level fallback above remains
        # available only when no exact group unit could be found.
        for slot_id, group_index in slot_group.items():
            group_unit_ids[group_index] = tuple(dict.fromkeys((
                *group_unit_ids[group_index],
                *slot_owner_units.get(slot_id, ()),
            )))
        new_paragraphs: list[SectionParagraphPlanV1] = []
        group_method_unit_ids: list[str] = []
        all_group_facet_ids = set().union(*group_facet_sets) if group_facet_sets else set()
        for group_index, group in enumerate(groups, start=1):
            group_zero = group_index - 1
            facet_ids = [
                str(getattr(facet, "facet_id", "") or "")
                for facet in group
                if str(getattr(facet, "facet_id", "") or "").strip()
            ]
            for row in old_rows_by_group[group_zero]:
                # Selected facets are already assigned to exactly one group.
                # Carry only an identity that is absent from the current
                # facet selection; otherwise a replayed old row can append a
                # facet to a second paragraph after the new grouping has
                # already closed it into another group.
                facet_ids.extend(
                    facet_id for facet_id in row.required_facet_ids
                    if facet_id not in all_group_facet_ids
                    and (
                        not argument_facets
                        or any(
                            str(getattr(current_facet, "facet_id", "") or "") == facet_id
                            and (
                                bool(getattr(current_facet, "required", False))
                                or str(getattr(current_facet, "formula_expectation", "none") or "none") != "none"
                            )
                            for current_facet in section_facet_values
                        )
                    )
                )
            facet_ids = list(dict.fromkeys(item for item in facet_ids if item))
            field_ids = [
                candidate_id
                for row in old_rows_by_group[group_zero]
                for candidate_id in row.required_field_candidate_ids
            ]
            field_ids = list(dict.fromkeys(field_ids))
            group_owned_slot_ids = {
                slot_id
                for unit_id in group_unit_ids[group_zero]
                for slot_id, owners in slot_owner_units.items()
                if unit_id in owners
            }
            # A fresh facet projection has its own exact evidence-to-slot
            # assignment.  Carrying the frozen row's complete slot list would
            # put all 47 slots of a dense implementation unit back into every
            # new facet paragraph, even when only one operation belongs there.
            # Legacy plans without facets still need their old support
            # closure, so keep that compatibility path explicit.
            row_slots = []
            if not argument_facets:
                row_slots = [
                    slot_id
                    for row in old_rows_by_group[group_zero]
                    for slot_id in row.ordered_semantic_slot_ids
                    if slot_id in group_owned_slot_ids
                ]
            assigned_slots = [
                slot_id for slot_id in section_slot_order
                if slot_group.get(slot_id) == group_zero
            ]
            slots = list(dict.fromkeys((*row_slots, *assigned_slots)))
            group_owned_edge_ids = {
                edge.relation_id
                for unit_id in group_unit_ids[group_zero]
                for unit in section_units
                if unit.argument_unit_id == unit_id
                for frame in ((unit_frames.get(unit_id) if unit_frames is not None else unit.semantic_frame),)
                if frame is not None
                for edge in frame.edges
            }
            edges = [
                edge_id
                for row in old_rows_by_group[group_zero]
                for edge_id in row.required_edge_ids
                if edge_id in group_owned_edge_ids
            ]
            # Only uniquely owned semantic slots become hard publication
            # targets.  Intermediate or ambiguous slots remain in the
            # support/ordered closure and are still available to the Writer.
            # This is the same compact-spine rule used by the base planner,
            # now applied after cross-row ownership is resolved.
            role_slots: dict[str, list[str]] = {
                role: [] for role in ("input", "transformation", "condition", "output")
            }
            for slot_id in assigned_slots:
                slot = section_slots.get(slot_id)
                role = str(getattr(slot, "role", "")) if slot is not None else ""
                if role in role_slots:
                    role_slots[role].append(slot_id)
            required_slot_list: list[str] = []
            for role in ("input", "transformation", "condition", "output"):
                values = role_slots[role]
                if not values:
                    continue
                selected_values = list(values[:1])
                if role == "transformation" and len(values) > 1:
                    selected_values.append(values[-1])
                required_slot_list.extend(selected_values)
            pub_slots = tuple(dict.fromkeys(required_slot_list))
            support_slots = []
            if not argument_facets:
                support_slots = [
                    slot_id
                    for row in old_rows_by_group[group_zero]
                    for slot_id in row.support_slot_ids
                ]
            support_slots.extend(assigned_slots)
            formula_ids = [
                f"formula:facet:{getattr(facet, 'facet_id', '')}"
                for facet in group
                if str(getattr(facet, "formula_expectation", "none") or "none") != "none"
                and str(getattr(facet, "facet_id", "") or "").strip()
            ]
            if group_zero == graph_formula_index:
                formula_ids.extend(
                    obligation_id
                    for obligation_id in graph.formula_obligation_ids
                    if str(obligation_id).strip()
                )
            formula_ids = list(dict.fromkeys(formula_ids))
            method_unit_id = f"method-unit:{graph.section_id}:{group_index}"
            group_method_unit_ids.append(method_unit_id)
            role = (
                "formula" if formula_ids else
                "construction" if group_zero == 0 else "step_sequence"
            )
            support_slot_ids, publication_slot_ids, ordered_slot_ids = (
                _closed_method_unit_slots(
                    section_id=graph.section_id,
                    paragraph_id=f"paragraph:{graph.section_id}:method-unit-{group_index}",
                    original_order=slots,
                    support_slots=support_slots,
                    publication_slots=pub_slots,
                )
            )
            new_paragraphs.append(SectionParagraphPlanV1(
                paragraph_id=f"paragraph:{graph.section_id}:method-unit-{group_index}",
                paragraph_role=role,  # type: ignore[arg-type]
                argument_unit_ids=group_unit_ids[group_zero],
                required_facet_ids=tuple(facet_ids),
                required_field_candidate_ids=tuple(dict.fromkeys(field_ids)),
                support_slot_ids=support_slot_ids,
                required_publication_slot_ids=publication_slot_ids,
                ordered_semantic_slot_ids=ordered_slot_ids,
                required_edge_ids=tuple(dict.fromkeys(edges)),
                formula_obligation_ids=tuple(formula_ids),
                expected_sentence_range=_method_unit_expected_sentence_range(
                    facets=group,
                    argument_unit_ids=group_unit_ids[group_zero],
                ),
                transition_from=(
                    new_paragraphs[-1].paragraph_id if new_paragraphs else ""
                ),
            ))
        compact_graph = graph.model_copy(update={"paragraphs": tuple(new_paragraphs)})
        compacted_graphs.append(compact_graph)
        for group_index, group in enumerate(groups, start=1):
            group_zero = group_index - 1
            projection_rows = []
            for facet in group:
                projection = _method_unit_alignment_projection(
                    str(getattr(facet, "facet_id", "") or ""), alignment_by_id,
                )
                if not projection.get("fact_ids") and fact_ids_by_span:
                    # The alignment contract may preserve an exact span while
                    # omitting internal fact ids.  Restore only facts whose
                    # frozen direct/relation span is exactly that span; do not
                    # infer facts from facet prose or symbol similarity.
                    recovered_fact_ids = tuple(dict.fromkeys(
                        fact_id
                        for span_id in projection.get("span_ids", ())
                        for fact_id in fact_ids_by_span.get(str(span_id), ())
                    ))
                    if recovered_fact_ids:
                        projection = {
                            **projection,
                            "fact_ids": recovered_fact_ids,
                        }
                projection_rows.append(projection)
            semantic = _method_unit_semantic_values(group)
            operations: list[dict[str, Any]] = []
            entry_symbol_ids: list[str] = []
            shape_hints: list[str] = []
            return_values: list[str] = []
            signatures: list[dict[str, Any]] = []
            fact_span_ids: list[str] = []
            for facet, projection in zip(group, projection_rows):
                fact_chain = (
                    compile_fact_chain(
                        facts=tuple(
                            fact_by_id[fact_id]
                            for fact_id in projection.get("fact_ids", ())
                            if fact_id in fact_by_id
                        ),
                    )
                    if compile_fact_chain is not None and projection.get("fact_ids")
                    else {}
                )
                operations.extend(fact_chain.get("operation_atoms", ()))
                signatures.extend(
                    dict(item)
                    for item in fact_chain.get("formalizable_signatures", ())
                    if dict(item) not in signatures
                )
                fact_span_ids.extend(
                    span_id for span_id in fact_chain.get("exact_span_ids", ())
                    if span_id not in fact_span_ids
                )
                operations.extend(projection["operations"])
                entry_symbol_ids.extend(
                    item for item in projection.get("symbol_ids", ())
                    if item not in entry_symbol_ids
                )
                shape_hints.extend(
                    item for item in projection.get("shape_hints", ())
                    if item not in shape_hints
                )
                return_values.extend(
                    item for item in projection.get("return_values", ())
                    if item not in return_values
                )
                signatures.extend(
                    item for item in projection.get("signatures", ())
                    if item not in signatures
                )
                if not projection["operations"]:
                    fields = getattr(facet, "semantic_fields", {}) or {}
                    statement = ""
                    if isinstance(fields, dict):
                        for key in ("operation", "formula_goal", "purpose", "goal"):
                            value = fields.get(key)
                            if isinstance(value, str) and value.strip():
                                statement = value.strip()
                                break
                    statement = statement or str(getattr(facet, "exact_source_quote", "") or "").strip()
                    if statement:
                        operations.append({
                            "operation_id": f"intent-operation:{getattr(facet, 'facet_id', '')}",
                            "predicate": "author_specification",
                            "description": statement,
                        })
            unique_operations: list[dict[str, Any]] = []
            seen_operation_shapes: set[tuple[Any, ...]] = set()
            for operation in operations:
                if not isinstance(operation, dict):
                    continue
                source_span = str(
                    operation.get("source_span_id")
                    or operation.get("span_id")
                    or operation.get("exact_span_id")
                    or ""
                ).strip()
                predicate = str(
                    operation.get("predicate")
                    or operation.get("operation")
                    or ""
                ).strip().casefold()
                subject = str(operation.get("subject") or "").strip()
                operands = operation.get("operands") or ()
                if isinstance(operands, str):
                    operands = (operands,)
                try:
                    operand_shape = tuple(str(item).strip() for item in operands)
                except TypeError:
                    operand_shape = (str(operands).strip(),)
                result = str(
                    operation.get("result")
                    or operation.get("output")
                    or operation.get("return_value")
                    or ""
                ).strip()
                guard = str(operation.get("guard") or "").strip()
                free_text = str(
                    operation.get("description")
                    or operation.get("statement")
                    or ""
                ).strip()
                # The fact compiler and a facet alignment can describe the
                # same source line with different ids/metadata.  Those are
                # one reader operation, not two sentences.  Deduplicate by
                # the closed source shape while retaining distinct guards,
                # operands, and results.
                operation_shape = (
                    source_span,
                    predicate,
                    subject,
                    operand_shape,
                    result,
                    guard,
                    free_text if not source_span or predicate == "author_specification" else "",
                )
                if operation_shape in seen_operation_shapes:
                    continue
                seen_operation_shapes.add(operation_shape)
                unique_operations.append(operation)
            statuses = tuple(
                status
                for projection in projection_rows
                for status in projection["statuses"]
                if status
            )
            evidence_spans = tuple(dict.fromkeys(
                [
                    *(
                        span_id
                        for projection in projection_rows
                        for span_id in projection["span_ids"]
                    ),
                    *fact_span_ids,
                ]
            ))
            has_evidence = bool(evidence_spans or any(
                projection["fact_ids"] or projection["claim_ids"]
                for projection in projection_rows
            ))
            if (
                statuses
                and all(status == "entailed" for status in statuses)
                and has_evidence
                and signatures
            ):
                authority = "code_equivalent"
            elif any(status == "mismatch" for status in statuses) or (
                any(status == "partial" for status in statuses) and has_evidence
            ):
                authority = "mismatch_pending"
            else:
                authority = "intent_specification"
            quotes = tuple(dict.fromkeys(
                str(getattr(facet, "exact_source_quote", "") or "").strip()
                for facet in group
                if str(getattr(facet, "exact_source_quote", "") or "").strip()
            ))
            group_facet_ids = tuple(
                str(getattr(facet, "facet_id", "") or "")
                for facet in group
                if str(getattr(facet, "facet_id", "") or "").strip()
            )
            argument_ids = group_unit_ids[group_zero]
            paragraph_id = new_paragraphs[group_zero].paragraph_id
            intent_statements = tuple(dict.fromkeys(
                str(operation.get("description") or operation.get("statement") or "").strip()
                for operation in unique_operations
                if str(operation.get("predicate") or "").strip() == "author_specification"
                and str(operation.get("description") or operation.get("statement") or "").strip()
            ))
            method_unit = MethodUnitV2(
                method_unit_id=group_method_unit_ids[group_zero],
                section_id=graph.section_id,
                reader_question=graph.reader_question,
                purpose=(
                    str(getattr(group[0], "semantic_fields", {}).get("operation", "") or "").strip()
                    if isinstance(getattr(group[0], "semantic_fields", {}), dict)
                    else ""
                ) or (quotes[0] if quotes else graph.reader_question),
                inputs=semantic["inputs"],
                ordered_operations=tuple(unique_operations),
                outputs=semantic["outputs"],
                entry_symbol_ids=tuple(dict.fromkeys(entry_symbol_ids)),
                conditions=semantic["conditions"],
                shape_or_type_hints=tuple(dict.fromkeys(shape_hints)),
                return_value_descriptors=tuple(dict.fromkeys(return_values)),
                formalizable_signatures=tuple(signatures),
                formula_roles=semantic["formula_roles"],
                evidence_spans=evidence_spans,
                authority=authority,
                intent_code_status=(
                    ",".join(dict.fromkeys(statuses))
                    or ("intent_specification" if quotes else "")
                ),
                author_statement=" ".join(quotes or intent_statements),
                facet_ids=group_facet_ids,
                fact_ids=tuple(dict.fromkeys(
                    fact_id for projection in projection_rows for fact_id in projection["fact_ids"]
                )),
                claim_ids=tuple(dict.fromkeys(
                    claim_id for projection in projection_rows for claim_id in projection["claim_ids"]
                )),
                equation_ids=tuple(dict.fromkeys(
                    equation_id for projection in projection_rows for equation_id in projection["equation_ids"]
                )),
                paragraph_ids=(paragraph_id,),
                argument_unit_ids=argument_ids,
            )
            compiled_units.append(method_unit)
            trace_rows.append({
                "method_unit_id": method_unit.method_unit_id,
                "section_id": graph.section_id,
                "paragraph_id": paragraph_id,
                "facet_ids": list(group_facet_ids),
                "evidence_spans": list(evidence_spans),
                "authority": authority,
                "intent_code_status": method_unit.intent_code_status,
            })
    compacted_graphs = _attach_method_unit_witness_contracts(
        compacted_graphs,
        units,
        argument_facets=argument_facets,
        facet_alignments=facet_alignments,
        publication_field_candidates=publication_field_candidates,
        unit_frames=unit_frames,
    )
    compacted_graphs = _order_context_sections_before_mechanism(
        compacted_graphs,
        units=units,
        argument_facets=argument_facets,
    )
    return tuple(compiled_units), compacted_graphs, {
        "enabled": True,
        "method_unit_count": len(compiled_units),
        "paragraph_count": sum(len(graph.paragraphs) for graph in compacted_graphs),
        "units": trace_rows,
    }


def _enrich_section_content_contracts(
    graphs: list[SectionArgumentGraphV1],
    units: list[MethodArgumentUnitV1],
    *,
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1] = (),
    concept_cards: Any | None = None,
    argument_briefs: Any | None = None,
    argument_facets: tuple[Any, ...] | list[Any] = (),
    facet_alignments: tuple[Any, ...] | list[Any] = (),
    publication_field_candidates: tuple[Any, ...] | list[Any] = (),
    equations: EquationClaimSetV1 | None = None,
    unit_frames: dict[str, SemanticArgumentFrameV1] | None = None,
) -> list[SectionArgumentGraphV1]:
    """Populate WP1 section content contract fields on each section graph."""

    from code2paper.agentic.publication_relevance import classify_concept_card_writing_role

    card_by_key = {
        card.concept_key: card
        for card in (getattr(concept_cards, "cards", ()) or ())
    }
    brief_by_id = {
        brief.brief_id: brief
        for brief in (getattr(argument_briefs, "briefs", ()) or ())
    }
    facet_by_id = {
        str(facet.facet_id): facet
        for facet in (argument_facets or ())
        if str(getattr(facet, "facet_id", "") or "").strip()
    }
    alignment_by_facet_id = {
        str(alignment.facet_id): alignment
        for alignment in (facet_alignments or ())
        if str(getattr(alignment, "facet_id", "") or "").strip()
    }
    field_candidates_by_facet: dict[str, tuple[Any, ...]] = {}
    for candidate in publication_field_candidates or ():
        facet_id = str(getattr(candidate, "facet_id", "") or "").strip()
        if facet_id:
            field_candidates_by_facet.setdefault(facet_id, ())
            field_candidates_by_facet[facet_id] = (
                *field_candidates_by_facet[facet_id], candidate,
            )
    story_by_id = {node.story_node_id: node for node in story_spine}
    story_order = {node.story_node_id: index for index, node in enumerate(story_spine)}
    units_by_id = {unit.argument_unit_id: unit for unit in units}
    enriched: list[SectionArgumentGraphV1] = []

    for graph in graphs:
        section_units = [
            units_by_id[unit_id]
            for unit_id in graph.argument_unit_ids
            if unit_id in units_by_id
        ]
        section_card_keys = tuple(dict.fromkeys(
            key
            for unit in section_units
            for key in unit.concept_card_ids
        ))
        section_brief_ids = tuple(dict.fromkeys(
            brief_id
            for unit in section_units
            for brief_id in unit.brief_ids
        ))
        audit_only: list[str] = []
        primary: list[str] = []
        supporting: list[str] = []
        primary_briefs: list[str] = []
        supporting_briefs: list[str] = []
        if brief_by_id and section_brief_ids:
            section_story_ids = {
                node.story_node_id
                for unit in section_units
                for obligation_id in unit.source_obligation_ids
                for node in story_spine
                if obligation_id in node.linked_obligation_ids
            }
            for brief_id in section_brief_ids:
                brief = brief_by_id.get(brief_id)
                if brief is None:
                    continue
                if brief.story_node_id in section_story_ids:
                    primary_briefs.append(brief_id)
                else:
                    supporting_briefs.append(brief_id)
        # Replanning is allowed to run with a legacy/missing projection.  If a
        # current brief artifact is available, however, it is the authority
        # for section ownership.  Re-adding graph-level ids here would move
        # every old brief back into the first paragraph after the units had
        # already been refreshed.
        if not brief_by_id:
            primary_briefs.extend(graph.primary_brief_ids)
            supporting_briefs.extend(graph.supporting_brief_ids)
        for key in section_card_keys:
            card = card_by_key.get(key)
            if card is None:
                continue
            story_selected = bool(card.realized_story_node_ids)
            role = classify_concept_card_writing_role(
                card,
                story_selected=story_selected,
            )
            if role == "audit_only":
                audit_only.append(key)
            elif story_selected:
                primary.append(key)
            else:
                supporting.append(key)
        if not card_by_key:
            # Preserve the frozen concept classification when the optional
            # concept-card artifact is unavailable during a typed replan.
            primary.extend(graph.primary_concept_keys)
            supporting.extend(graph.supporting_concept_keys)
            audit_only.extend(graph.audit_only_concept_keys)

        def _primary_sort(key: str) -> tuple[int, str]:
            card = card_by_key.get(key)
            if card is None or not card.realized_story_node_ids:
                return (len(story_spine), key)
            return (
                min(
                    story_order.get(story_id, len(story_spine))
                    for story_id in card.realized_story_node_ids
                ),
                key,
            )

        primary.sort(key=_primary_sort)
        story_ids: list[str] = []
        for unit in section_units:
            for obligation_id in unit.source_obligation_ids:
                for node in story_spine:
                    if obligation_id in node.linked_obligation_ids:
                        story_ids.append(node.story_node_id)
        for key in primary:
            card = card_by_key.get(key)
            if card is not None:
                story_ids.extend(card.realized_story_node_ids)
        if not story_spine:
            story_ids.extend(graph.story_node_ids)
        # With a fresh story spine, graph-level story ids are also stale
        # organization state.  Only ids justified by current unit obligation
        # edges or current concept-card bindings are retained.
        story_node_ids = tuple(dict.fromkeys(story_ids))

        required_equation_move = any(
            move.move == "equation_or_derivation" and move.required
            for move in graph.moves
        )
        equation_by_id = {
            str(equation.equation_id): equation
            for equation in (equations.equations if equations is not None else ())
        }
        equation_ids = tuple(dict.fromkeys(
            equation_id
            for unit in section_units
            for equation_id in unit.equation_ids
            if str(equation_id) not in equation_by_id
            or str(getattr(equation_by_id[str(equation_id)], "formula_role", "") or "")
            != "incidental"
        ))
        primary_formula = any(
            card_by_key.get(key) is not None
            and card_by_key[key].formula_constraints
            for key in primary
        )
        formula_obligation_ids: tuple[str, ...] = ()
        formula_not_applicable = False
        formula_not_applicable_reason = ""
        if equation_ids:
            formula_obligation_ids = tuple(
                f"formula:{equation_id}" for equation_id in equation_ids
            )
        elif required_equation_move or primary_formula:
            formula_obligation_ids = (
                f"formula:section:{graph.section_id}:derivation",
            )
        else:
            formula_not_applicable = True
            formula_not_applicable_reason = (
                "no primary formula role and no bound equations for this section"
            )

        dataflow_ids = tuple(dict.fromkeys(
            relation_id
            for unit in section_units
            for relation_id in unit.behavior_relation_ids
        ))
        open_slots: list[SectionContentOpenSlotV1] = []
        if not primary and not primary_briefs and story_node_ids:
            for story_id in story_node_ids:
                if story_id not in story_by_id:
                    continue
                open_slots.append(SectionContentOpenSlotV1(
                    slot_id=f"slot:{graph.section_id}:{story_id}",
                    owner="architect",
                    authority_lane="author_intent_unverified",
                    target_concept_key="",
                    slot_kind="missing_primary_concept",
                    blocking_for_candidate=True,
                    blocking_for_verified=True,
                ))

        extra_constraints = [
            f"author_statement:{story_by_id[story_id].author_statement.strip()}"
            for story_id in story_node_ids
            if story_id in story_by_id
            and str(story_by_id[story_id].author_statement or "").strip()
        ]
        heading_constraints = tuple(dict.fromkeys([
            *graph.heading_constraints,
            *extra_constraints,
        ]))

        enriched_graph = graph.model_copy(update={
            "story_node_ids": story_node_ids,
            "primary_concept_keys": tuple(primary),
            "supporting_concept_keys": tuple(supporting),
            "audit_only_concept_keys": tuple(audit_only),
            "primary_brief_ids": tuple(primary_briefs),
            "supporting_brief_ids": tuple(supporting_briefs),
            "required_dataflow_relation_ids": dataflow_ids,
            "formula_obligation_ids": formula_obligation_ids,
            "formula_not_applicable": formula_not_applicable,
            "formula_not_applicable_reason": formula_not_applicable_reason,
            "open_slots": tuple(open_slots),
            "heading_constraints": heading_constraints,
        })
        enriched.append(enriched_graph.model_copy(update={
            "paragraphs": _build_section_paragraph_plans(
                section_id=enriched_graph.section_id,
                section_units=section_units,
                move_objects=enriched_graph.moves,
                formula_obligation_ids=formula_obligation_ids,
                unit_frames=unit_frames,
                argument_facets=argument_facets,
                facet_alignments=facet_alignments,
                publication_field_candidates=publication_field_candidates,
            ),
        }))
    return enriched


def _bucket_intended_role(bucket: list[Any]) -> str:
    for item in bucket:
        if isinstance(item, _CandidateRowEntry):
            role = str(getattr(item.story_node, "intended_role", "") or "")
            if role:
                return role
    return ""


def _bucket_story_node(bucket: list[Any]) -> Any | None:
    for item in bucket:
        if isinstance(item, _CandidateRowEntry) and item.story_node is not None:
            return item.story_node
    return None


def _story_reader_question(*, heading: str, bucket: list[Any] | None = None, story_node: Any = None) -> str:
    """Derive the section's scientific question from the author story.

    Never uses the transform-inputs-into-outputs template.
    """

    node = story_node if story_node is not None else (
        _bucket_story_node(bucket) if bucket is not None else None
    )
    title = str(getattr(node, "title", "") or heading).strip()
    statement = str(getattr(node, "author_statement", "") or "").strip()
    role = str(getattr(node, "intended_role", "") or "").replace("_", " ").strip()
    focus = statement or title or heading
    focus = " ".join(focus.split())
    if len(focus) > 220:
        focus = coherent_heading(focus, limit=220, intended_role=role, source_text=focus)
    if role:
        return f"How does this {role} realize {focus.rstrip('.')}?"
    return f"What method mechanism does this section realize: {focus.rstrip('.')}?"


def _bind_move_anchor(
    move: SectionArgumentMoveV1,
    *,
    section_units: list[MethodArgumentUnitV1],
) -> SectionArgumentMoveV1:
    """Bind requiredness to authorized anchors; unanchored moves keep an owner."""

    has_equations = any(unit.equation_ids for unit in section_units)
    has_configurations = any(unit.configuration_ids for unit in section_units)
    if move.move == "equation_or_derivation":
        if has_equations:
            return move.model_copy(update={"required": True, "unanchored": False, "unanchored_owner": ""})
        return move.model_copy(update={
            "required": False,
            "unanchored": True,
            "unanchored_owner": "Formalizer",
        })
    if move.move == "configuration_and_branches":
        if has_configurations:
            return move.model_copy(update={"required": True, "unanchored": False, "unanchored_owner": ""})
        return move.model_copy(update={
            "required": False,
            "unanchored": True,
            "unanchored_owner": "Research",
        })
    return move


def _ensure_unanchored_formula_move(
    move_objects: tuple[SectionArgumentMoveV1, ...],
    *,
    section_units: list[MethodArgumentUnitV1],
    heading: str = "",
) -> tuple[SectionArgumentMoveV1, ...]:
    """Keep a typed formula obligation when the section has no equation evidence."""

    if _heading_is_rhetorical_frame(heading):
        return tuple(
            item for item in move_objects
            if item.move not in {"equation_or_derivation", "mechanism_overview"}
        )
    has_equations = any(unit.equation_ids for unit in section_units)
    if has_equations or any(item.move == "equation_or_derivation" for item in move_objects):
        return move_objects
    unit_ids = tuple(unit.argument_unit_id for unit in section_units)
    extra = _bind_move_anchor(
        SectionArgumentMoveV1(
            move="equation_or_derivation",
            argument_unit_ids=unit_ids,
            paragraph_budget=1,
            information_budget=0.25,
            allowed_authority_lanes=("formal_derivation",),
            required=False,
        ),
        section_units=section_units,
    )
    return (*move_objects, extra)


def _bucket_story_text(bucket: tuple[str, list[Any]]) -> str:
    parts = [bucket[0]]
    for item in bucket[1]:
        if isinstance(item, _CandidateRowEntry):
            parts.extend((
                str(getattr(item.row, "statement", "") or ""),
                str(getattr(item.story_node, "author_statement", "") or ""),
                str(getattr(item.story_node, "title", "") or ""),
            ))
        else:
            parts.extend((str(item[1]), str(item[2])))
    return " ".join(parts)


def _organization_story_nodes(
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1],
) -> list[AuthorStoryNodeV1]:
    return [
        node
        for node in story_spine
        if "ORGANIZATION" in str(node.story_node_id).upper()
    ]


def _bucket_obligation_ids(bucket: tuple[str, list[Any]]) -> set[str]:
    ids: set[str] = set()
    for item in bucket[1]:
        if isinstance(item, _CandidateRowEntry):
            ids.add(str(item.obligation_id))
            continue
        ids.update(str(obligation_id) for obligation_id in item[4])
    return ids


def _heading_token_jaccard(left: str, right: str) -> float:
    left_tokens = _section_cluster_tokens(left)
    right_tokens = _section_cluster_tokens(right)
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


def _organization_stub_row(
    node: AuthorStoryNodeV1,
    *,
    completeness: MethodCompletenessMatrixV1 | None,
) -> MethodCompletenessItemV1:
    row_by_id = completeness.by_id() if completeness is not None else {}
    for obligation_id in node.linked_obligation_ids:
        row = row_by_id.get(str(obligation_id))
        if row is not None and str(row.status) != "out_of_scope":
            return row
    obligation_id = (
        str(node.linked_obligation_ids[0])
        if node.linked_obligation_ids
        else str(node.story_node_id)
    )
    return MethodCompletenessItemV1(
        obligation_id=obligation_id,
        role="organization",
        statement=node.author_statement or node.title,
        status="author_confirmation_required",
        importance="high",
    )


def _consolidate_buckets_under_organization_spine(
    buckets: list[tuple[str, list[Any]]],
    *,
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1],
    completeness: MethodCompletenessMatrixV1 | None = None,
) -> list[tuple[str, list[Any]]]:
    """Restore the author's document hierarchy without dropping obligations.

    Intent compilation exposes organization headings, stages, components and
    rationale checks as sibling story nodes.  Treating every sibling as a
    section produced 20+ one-paragraph headings.  When the author supplied a
    genuine organization spine, use those nodes as section anchors even if
    their completeness rows are still unresolved, and place every other
    bucket inside the nearest semantic anchor.  Argument units and exact
    obligation bindings remain unchanged; only their section grouping is
    consolidated.
    """

    org_nodes = _organization_story_nodes(story_spine)
    if 2 <= len(org_nodes) <= 8:
        return _anchors_from_organization_nodes(
            buckets,
            org_nodes=org_nodes,
            completeness=completeness,
        )

    organization_ids = {
        str(obligation_id)
        for node in org_nodes
        for obligation_id in node.linked_obligation_ids
    }
    anchors: list[tuple[int, tuple[str, list[Any]]]] = []
    for index, bucket in enumerate(buckets):
        obligation_ids = _bucket_obligation_ids(bucket)
        if obligation_ids & organization_ids or _bucket_links_organization(bucket):
            anchors.append((index, bucket))
    # Two to eight explicit organization nodes are a usable document spine.
    # Outside that range, retain the original plan rather than inventing one.
    if not 2 <= len(anchors) <= 8:
        return buckets
    return _fold_non_anchors(buckets, anchors)


def _anchors_from_organization_nodes(
    buckets: list[tuple[str, list[Any]]],
    *,
    org_nodes: list[AuthorStoryNodeV1],
    completeness: MethodCompletenessMatrixV1 | None,
) -> list[tuple[str, list[Any]]]:
    used_indexes: set[int] = set()
    anchors: list[tuple[str, list[Any]]] = []
    for node in org_nodes:
        org_ids = {str(item) for item in node.linked_obligation_ids}
        match_index: int | None = None
        for index, bucket in enumerate(buckets):
            if index in used_indexes:
                continue
            if _bucket_obligation_ids(bucket) & org_ids or (
                _bucket_links_organization(bucket)
                and any(
                    str(getattr(getattr(item, "story_node", None), "story_node_id", "") or "")
                    == str(node.story_node_id)
                    for item in bucket[1]
                    if isinstance(item, _CandidateRowEntry)
                )
            ):
                match_index = index
                break
        if match_index is None:
            node_text = " ".join((node.title, node.author_statement))
            rhetorical_anchor = _heading_is_rhetorical_frame(node.title)
            scores = []
            for index, bucket in enumerate(buckets):
                if index in used_indexes:
                    continue
                stage_bucket = _bucket_has_stage_obligation(bucket)
                if stage_bucket and rhetorical_anchor:
                    continue
                score = _heading_token_jaccard(node_text, _bucket_story_text(bucket))
                if stage_bucket:
                    node_family = _heading_family(node_text)
                    bucket_family = _heading_family(_bucket_story_text(bucket))
                    if node_family != "other" and node_family == bucket_family:
                        score += 0.5
                    if score < 0.25:
                        continue
                scores.append((index, score))
            if scores:
                best_index, best_score = max(scores, key=lambda item: item[1])
                if best_score > 0:
                    match_index = best_index
        if match_index is not None:
            used_indexes.add(match_index)
            heading, items = buckets[match_index]
            anchors.append((node.title or heading, list(items)))
            continue
        row = _organization_stub_row(node, completeness=completeness)
        heading, _constraints = _planning_section_heading(
            node.title,
            bucket=[_CandidateRowEntry(row, node)],
        )
        anchors.append((heading, [_CandidateRowEntry(row, node)]))

    non_anchor = [
        (index, bucket) for index, bucket in enumerate(buckets)
        if index not in used_indexes
    ]
    return _fold_non_anchor_buckets(anchors, non_anchor)


def _fold_non_anchors(
    buckets: list[tuple[str, list[Any]]],
    anchors: list[tuple[int, tuple[str, list[Any]]]],
) -> list[tuple[str, list[Any]]]:
    consolidated: list[tuple[str, list[Any]]] = [
        (bucket[0], list(bucket[1])) for _index, bucket in anchors
    ]
    anchor_indexes = {index for index, _bucket in anchors}
    non_anchor = [
        (index, bucket) for index, bucket in enumerate(buckets)
        if index not in anchor_indexes
    ]
    return _fold_non_anchor_buckets(consolidated, non_anchor)


def _heading_is_rhetorical_frame(heading: str) -> bool:
    return bool(re.search(
        r"\b(motivation|overview|related.?work|background|introduction|overall framework)\b",
        str(heading or ""),
        re.I,
    ))


_LOCAL_FAMILY_RE = re.compile(
    r"\b(?:first|activat(?:e|ion|ed|ing)?|bridg(?:e|ing)?|frontier|threshold|prune|exclude)\b",
    re.I,
)
_GLOBAL_FAMILY_RE = re.compile(
    r"\b(?:second|pagerank|ppr|damping|global|aggregat(?:e|ion|ed|ing)?|rank)\b",
    re.I,
)
_OFFLINE_FAMILY_RE = re.compile(
    r"\b(?:offline|construct|index|corpus|adjacenc)\b",
    re.I,
)
_TRAINING_FAMILY_RE = re.compile(
    r"\b(?:train(?:ing|s|ed)?|loss(?:es)?|optimiz(?:e|ation|er)?)\b",
    re.I,
)
_ARCHITECTURE_FAMILY_RE = re.compile(
    r"\b(?:architectur\w*|encod(?:e|ing|er|ed)?|embed(?:ding)?s?|attention|augment(?:ation|ed)?|transformer|sinusoid(?:al)?|hybrid|retriev(?:e|al|ed|ing)?)\b",
    re.I,
)


def _heading_family(text: str) -> str:
    value = str(text or "")
    if _heading_is_rhetorical_frame(value):
        return "frame"
    if _TRAINING_FAMILY_RE.search(value):
        return "training"
    if _LOCAL_FAMILY_RE.search(value):
        return "local"
    if _GLOBAL_FAMILY_RE.search(value):
        return "global"
    if _OFFLINE_FAMILY_RE.search(value):
        return "offline"
    if _ARCHITECTURE_FAMILY_RE.search(value):
        return "architecture"
    return "other"


def _heading_token_containment(subset: str, container: str) -> bool:
    left = _section_cluster_tokens(subset)
    right = _section_cluster_tokens(container)
    if len(left) < 2 or not right:
        return False
    return left <= right


def _compatible_stage_fold_target(bucket_heading: str, target_heading: str) -> bool:
    if _heading_is_rhetorical_frame(target_heading):
        return False
    source = _heading_family(bucket_heading)
    target = _heading_family(target_heading)
    if source == "training" or target == "training":
        return source == target
    if source in {"local", "global"} and target in {"local", "global"} and source != target:
        return False
    if source in {"local", "global", "offline"} and target == "architecture":
        return False
    return True


def _stage_fold_score(bucket_heading: str, target_heading: str) -> float:
    if not _compatible_stage_fold_target(bucket_heading, target_heading):
        return -1.0
    score = _heading_token_jaccard(bucket_heading, target_heading)
    if (
        _heading_token_containment(bucket_heading, target_heading)
        or _heading_token_containment(target_heading, bucket_heading)
    ):
        score = max(score, 0.51)
    source_family = _heading_family(bucket_heading)
    target_family = _heading_family(target_heading)
    if source_family not in {"other", "frame"} and source_family == target_family:
        score += 0.5
    return score


def _bucket_has_stage_obligation(bucket: tuple[str, list[Any]]) -> bool:
    return any(
        re.search(r"(STAGE|PIPELINE)", str(obligation_id), re.I)
        for obligation_id in _bucket_obligation_ids(bucket)
    )


def _fold_non_anchor_buckets(
    consolidated: list[tuple[str, list[Any]]],
    non_anchor: list[tuple[int, tuple[str, list[Any]]]],
) -> list[tuple[str, list[Any]]]:
    if not consolidated:
        return [bucket for _index, bucket in non_anchor]
    leftover: list[tuple[str, list[Any]]] = []
    heading_tokens = [_section_cluster_tokens(bucket[0]) for bucket in consolidated]
    for ordinal, (_index, bucket) in enumerate(non_anchor):
        tokens = _section_cluster_tokens(_bucket_story_text(bucket))
        stage_bucket = _bucket_has_stage_obligation(bucket)
        scores: list[float] = []
        for idx, (heading, _items) in enumerate(consolidated):
            if stage_bucket:
                scores.append(_stage_fold_score(bucket[0], heading))
                continue
            target_tokens = heading_tokens[idx]
            union = tokens | target_tokens
            scores.append((len(tokens & target_tokens) / len(union)) if union else 0.0)
        best_score = max(scores, default=0.0)
        floor = 0.25 if stage_bucket else 0.0
        merge = best_score >= floor and best_score > 0
        if (
            stage_bucket
            and not merge
            and 0.15 <= best_score < 0.25
        ):
            target_heading = consolidated[scores.index(best_score)][0]
            source_family = _heading_family(bucket[0])
            if source_family not in {"frame", "other"} and source_family == _heading_family(target_heading):
                merge = True
            elif _heading_token_containment(bucket[0], target_heading):
                merge = True
        if merge:
            target = scores.index(best_score)
            consolidated[target] = (
                consolidated[target][0],
                [*consolidated[target][1], *bucket[1]],
            )
            continue
        if stage_bucket:
            leftover.append(bucket)
            continue
        target = min(
            len(consolidated) - 1,
            (ordinal * len(consolidated)) // max(1, len(non_anchor)),
        )
        consolidated[target] = (
            consolidated[target][0],
            [*consolidated[target][1], *bucket[1]],
        )
    return [*consolidated, *leftover]


def _merge_near_duplicate_section_buckets(
    buckets: list[tuple[str, list[Any]]],
) -> list[tuple[str, list[Any]]]:
    """Collapse high-overlap headings that are not distinct organization anchors."""

    if len(buckets) < 2:
        return buckets
    merged: list[tuple[str, list[Any]]] = []
    used: set[int] = set()
    for index, bucket in enumerate(buckets):
        if index in used:
            continue
        heading, items = bucket[0], list(bucket[1])
        heading_tokens = _section_cluster_tokens(heading)
        used.add(index)
        for other_index in range(index + 1, len(buckets)):
            if other_index in used:
                continue
            other = buckets[other_index]
            if _bucket_links_organization(bucket) and _bucket_links_organization(other):
                continue
            other_tokens = _section_cluster_tokens(other[0])
            union = heading_tokens | other_tokens
            shared = heading_tokens & other_tokens
            if not union or len(shared) < 2:
                continue
            org_xor_stage = (
                _bucket_links_organization(bucket) != _bucket_links_organization(other)
            )
            overlap = len(shared) / len(union)
            contained = (
                _heading_token_containment(other[0], heading)
                or _heading_token_containment(heading, other[0])
            )
            if org_xor_stage:
                if not _compatible_stage_fold_target(
                    bucket[0] if _bucket_has_stage_obligation(bucket) else other[0],
                    other[0] if _bucket_has_stage_obligation(bucket) else heading,
                ):
                    continue
                if not contained and overlap < 0.45:
                    continue
            elif overlap < 0.6:
                continue
            items.extend(other[1])
            used.add(other_index)
        merged.append((heading, items))
    return merged


def _candidate_argument_unit(
    *,
    row: MethodCompletenessItemV1,
    story_node: AuthorStoryNodeV1 | None,
    section_id: str,
    unit_id: str,
    heading: str = "",
) -> MethodArgumentUnitV1:
    """One candidate-only argument unit from a completeness row.

    The unit's statement is organization/candidate authority (author wording
    or the completeness row statement), never a repository fact.  Moves
    include the owning content move when the row's role names one, plus
    ``limitations_or_mismatch`` so the candidate can be caveated and the
    verified side can fail closed.
    """

    role = str(row.role or "").lower()
    statement = (
        str(row.statement or "").strip()
        or (story_node.author_statement if story_node is not None else "")
        or str(row.role or "")
        or f"Method point {row.obligation_id}"
    )
    status = str(row.status)
    if status == "author_confirmation_required":
        lanes = ("author_attested",)
    elif status == "external_evidence_required":
        lanes = ("external_literature", "empirical_artifact")
    elif status == "formalization_required":
        lanes = ("formal_derivation",)
    else:
        lanes = ("executable_hard",)
    if _heading_is_rhetorical_frame(heading):
        moves = ["problem_or_local_context", "design_objective"]
        if status in {
            "partially_supported_by_repository",
            "paper_code_mismatch",
            "author_confirmation_required",
            "unverified_by_repository",
            "explicit_code_gap",
            "external_evidence_required",
        }:
            moves.append("limitations_or_mismatch")
        moves.append("transition_to_next_section")
        unresolved = (f"{row.obligation_id}:{status}",)
        return MethodArgumentUnitV1(
            argument_unit_id=unit_id,
            section_role=str(row.role or "") or (story_node.intended_role if story_node is not None else "stage"),
            research_question=(
                story_node.title if story_node is not None and story_node.title.strip()
                else (row.statement or row.role or f"Method point {row.obligation_id}")
            ),
            design_objective=statement,
            claim_ids=tuple(row.claim_ids),
            equation_ids=tuple(row.equation_ids),
            configuration_ids=tuple(row.configuration_ids),
            allowed_expository_moves=tuple(moves),
            unresolved_inputs=unresolved,
            authority_lanes=lanes,
            source_artifact_ids=tuple(dict.fromkeys([
                *row.source_artifact_ids,
                *row.matched_fact_ids,
                *row.matched_span_ids,
            ])),
            source_obligation_ids=(row.obligation_id,),
            supported=False,
            information_weight=1.0,
        )
    moves: list[str] = (
        ["problem_or_local_context", "design_objective"]
        if not tuple(row.claim_ids)
        else ["mechanism_overview"]
    )
    if status == "partially_supported_by_repository":
        moves.append("implementation_realization")
        if any(token in role for token in ("train", "loss", "objective")):
            moves.append("training_objective")
        if any(token in role for token in ("infer", "output", "predict", "return")):
            moves.append("inference_and_output")
        if any(token in role for token in ("config", "parameter", "branch")):
            moves.append("configuration_and_branches")
    else:
        if status == "formalization_required" or any(
            token in role for token in ("equation", "formula", "derivation", "notation")
        ):
            moves.append("equation_or_derivation")
        if any(token in role for token in ("config", "parameter", "branch")):
            moves.append("configuration_and_branches")
        if any(token in role for token in ("infer", "output", "predict", "return", "deploy")):
            moves.append("inference_and_output")
        if any(token in role for token in ("train", "loss", "objective")):
            moves.append("training_objective")
    moves = [*dict.fromkeys(moves)]
    if status in {
        "partially_supported_by_repository",
        "paper_code_mismatch",
        "author_confirmation_required",
        "unverified_by_repository",
        "explicit_code_gap",
        "external_evidence_required",
    }:
        moves.append("limitations_or_mismatch")
    moves.append("transition_to_next_section")
    unresolved = (f"{row.obligation_id}:{status}",)
    return MethodArgumentUnitV1(
        argument_unit_id=unit_id,
        section_role=str(row.role or "") or (story_node.intended_role if story_node is not None else "stage"),
        research_question=(
            story_node.title if story_node is not None and story_node.title.strip()
            else (row.statement or row.role or f"Method point {row.obligation_id}")
        ),
        design_objective=statement,
        claim_ids=tuple(row.claim_ids),
        equation_ids=tuple(row.equation_ids),
        configuration_ids=tuple(row.configuration_ids),
        allowed_expository_moves=tuple(moves),
        unresolved_inputs=unresolved,
        authority_lanes=lanes,
        source_artifact_ids=tuple(dict.fromkeys([
            *row.source_artifact_ids,
            *row.matched_fact_ids,
            *row.matched_span_ids,
        ])),
        source_obligation_ids=(row.obligation_id,),
        supported=False,
        information_weight=1.0,
    )


def _story_spine_usage_trace(
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1],
    graphs: list[SectionArgumentGraphV1],
    units: list[MethodArgumentUnitV1],
) -> list[dict[str, Any]]:
    """Trace which story nodes were realized by which plan sections.

    A node is realized by a section when the section's units carry the node's
    exact linked obligation ids; unbound nodes are recorded as
    ``unrealized`` so author-intent tracking never silently drops a point.
    """

    if not story_spine:
        return []
    obligations_by_unit = {
        unit.argument_unit_id: set(unit.source_obligation_ids)
        for unit in units
    }
    claims_by_unit = {
        unit.argument_unit_id: set(unit.claim_ids)
        for unit in units
    }
    sections_by_unit = {
        unit_id: graph.section_id
        for graph in graphs
        for unit_id in graph.argument_unit_ids
    }
    rows: list[dict[str, Any]] = []
    for node in story_spine:
        linked = set(node.linked_obligation_ids)
        linked_claims = set(node.linked_claim_ids)
        realized_sections = sorted({
            sections_by_unit[unit_id]
            for unit_id, obligation_ids in obligations_by_unit.items()
            if (
                obligation_ids & linked
                or claims_by_unit.get(unit_id, set()) & linked_claims
            )
            and unit_id in sections_by_unit
        })
        rows.append({
            "story_node_id": node.story_node_id,
            "title": node.title,
            "intended_role": node.intended_role,
            "evidence_lane": node.evidence_lane,
            "linked_obligation_ids": list(node.linked_obligation_ids),
            "realized_sections": realized_sections or ["unrealized"],
        })
    return rows


def build_method_section_plan_with_product_readiness(
    *,
    claims: AtomicClaimSetV3,
    completeness: MethodCompletenessMatrixV1 | None = None,
    equations: EquationClaimSetV1 | None = None,
    configurations: ConfigurationClaimSetV1 | None = None,
    method_name: str = "",
    venue: str = "",
    audience: str = "method readers",
    page_budget: float = 0.0,
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1] = (),
    policy: MethodOutputPolicyV1 | None = None,
    propositions: MethodPropositionSetV1 | None = None,
    concept_cards: Any | None = None,
    argument_briefs: Any | None = None,
    prior_plan: MethodSectionPlanV2 | None = None,
    publication_field_candidates: tuple[Any, ...] | list[Any] = (),
    argument_facets: tuple[Any, ...] | list[Any] = (),
    facet_alignments: tuple[Any, ...] | list[Any] = (),
    facts: Any | None = None,
    unit_frames: dict[str, SemanticArgumentFrameV1] | None = None,
) -> tuple[MethodSectionPlanV2, MethodPlanProductReadinessV1, dict[str, Any]]:
    """Build the section plan together with its graded product readiness.

    This is the D-package entry point: the Architect still produces the full
    typed plan (units, sections, moves) while the shared readiness assessment
    decides ``verified_ready`` / ``candidate_ready`` /
    ``candidate_ready_with_review`` / ``blocked_for_safety``.  Exact
    placement, move-authority and semantic-frame closure appear only as audit
    warnings inside the readiness report and never block candidate planning.

    ``concept_cards`` binds Stage 2/3 cards to units (verified/caveated
    separation, one placement per card).
    """

    plan, trace = build_method_section_plan_with_trace(
        claims=claims,
        completeness=completeness,
        equations=equations,
        configurations=configurations,
        method_name=method_name,
        venue=venue,
        audience=audience,
        page_budget=page_budget,
        story_spine=story_spine,
        propositions=propositions,
        concept_cards=concept_cards,
        argument_briefs=argument_briefs,
        prior_plan=prior_plan,
        publication_field_candidates=publication_field_candidates,
        argument_facets=argument_facets,
        facet_alignments=facet_alignments,
        facts=facts,
        unit_frames=unit_frames,
    )
    readiness = assess_plan_product_readiness(
        plan=plan,
        completeness=completeness,
        claims=claims,
        policy=policy,
    )
    trace["product_readiness"] = readiness.model_dump(mode="json")
    return plan, readiness, trace


def _unresolved_for_obligations(obligation_ids: tuple[str, ...], matrix: dict[str, Any]) -> list[str]:
    unresolved: list[str] = []
    for obligation_id in obligation_ids:
        item = matrix.get(obligation_id)
        if item is None:
            continue
        status = str(item.status)
        if status != "supported_by_repository":
            unresolved.append(f"{obligation_id}:{status}")
    return unresolved


def _configuration_binds_unit(config: Any, claims: list[Any]) -> bool:
    """Exact configuration-to-unit binding.

    A configuration binds to a unit only through exact source evidence: the
    config's relation chain (``override_chain`` = the ``configured_by``
    relation evidence ids) intersects the unit's claims' relation ids, or the
    config's source facts intersect the unit's claims' fact ids.  Function-name
    or token overlap is never a binding.
    """

    unit_relation_ids = {
        str(relation_id)
        for claim in claims
        for relation_id in (getattr(claim, "relation_evidence_ids", ()) or ())
    }
    unit_fact_ids = {
        str(fact_id)
        for claim in claims
        for fact_id in (getattr(claim, "fact_ids", ()) or ())
    }
    if set(str(item) for item in (getattr(config, "override_chain", ()) or ())).intersection(unit_relation_ids):
        return True
    if set(str(item) for item in (getattr(config, "source_fact_ids", ()) or ())).intersection(unit_fact_ids):
        return True
    return False


def _configuration_relevant(key: str, claims: list[AtomicClaimV3]) -> bool:
    tokens = set(re.findall(r"[a-z0-9_]+", key.lower()))
    if not tokens:
        return False
    return any(tokens & set(re.findall(r"[a-z0-9_]+", claim.canonical_text.lower())) for claim in claims)


def _moves(
    claims: list[AtomicClaimV3],
    has_equations: bool,
    has_configurations: bool,
    unresolved: list[str] | tuple[str, ...] | bool = (),
    heading: str = "",
) -> tuple[tuple[str, ...], frozenset[str]]:
    """Derive the move template from the unit's authorized content.

    Required moves follow the argument's actual content instead of applying
    one generic template to every claim group: data-flow/implementation moves
    are required only when the unit's claims carry the corresponding
    operations, and the output move only when the unit describes an output.
    Optional moves are still planned when their content (equations, branches,
    training vocabulary) is present.  ``limitations_or_mismatch`` is required
    only for mismatch/gap statuses, never for ordinary partial support.
    Motivation/overview headings keep rhetorical moves only.
    """

    if _heading_is_rhetorical_frame(heading):
        moves = (
            "problem_or_local_context",
            "design_objective",
            "transition_to_next_section",
        )
        return moves, frozenset(moves)

    if not claims and not has_equations:
        moves = (
            "problem_or_local_context",
            "design_objective",
            "transition_to_next_section",
        )
        return moves, frozenset(moves)

    texts = " ".join(claim.canonical_text.lower() for claim in claims)
    unresolved_rows: tuple[str, ...]
    if isinstance(unresolved, bool):
        unresolved_rows = ()
    else:
        unresolved_rows = tuple(unresolved)

    def has(pattern: str) -> bool:
        return re.search(pattern, texts, re.IGNORECASE) is not None

    moves: list[str] = ["problem_or_local_context", "design_objective", "mechanism_overview"]
    if has_equations:
        moves.extend(("formal_objects_and_notation", "equation_or_derivation"))
    if has(r"\b(?:computes formula|computes|calculates|concatenates|normalizes|"
           r"reduces|propagates|attends|sorts by|selects top k)\b") or has_equations:
        moves.append("algorithm_or_data_flow")
    if has(r"\b(?:loads weights|reads|stores|writes|constructs|initializes|calls|invokes|applies)\b"):
        moves.append("implementation_realization")
    if has_configurations or has(r"\b(?:branches on|if |when |guard|else )"):
        moves.append("configuration_and_branches")
    if has(r"\b(?:loss|objective|train|training)\b"):
        moves.append("training_objective")
    if has(r"\b(?:returns|emits|outputs|writes back)\b") or has(r"\boutput\b"):
        moves.append("inference_and_output")
    require_limitations = _unresolved_requires_limitation_move(unresolved_rows)
    if require_limitations:
        moves.append("limitations_or_mismatch")
    moves.append("transition_to_next_section")
    # Every unit keeps the core overview/organization moves required; the
    # content-dependent moves below are required only when the unit's claims
    # actually realize them.  This stops the generic-move-template behaviour
    # while keeping the required-move surface coherent with the gates.
    required_moves = {
        "problem_or_local_context",
        "design_objective",
        "mechanism_overview",
        "transition_to_next_section",
    }
    if has_equations:
        required_moves.add("equation_or_derivation")
    if has_configurations:
        required_moves.add("configuration_and_branches")
    if has(r"\b(?:computes formula|computes|calculates|concatenates|normalizes|"
           r"reduces|propagates|attends|sorts by|selects top k)\b") or has_equations:
        required_moves.add("algorithm_or_data_flow")
    if has(r"\b(?:loads weights|reads|stores|writes|constructs|initializes|calls|invokes|applies)\b"):
        required_moves.add("implementation_realization")
    if has(r"\b(?:returns|emits|outputs|writes back)\b") or has(r"\boutput\b"):
        required_moves.add("inference_and_output")
    if require_limitations:
        required_moves.add("limitations_or_mismatch")
    return tuple(dict.fromkeys(moves)), frozenset(required_moves)


_OPERATION_FAMILY_TO_STAGE: dict[str, dict[str, str]] = {
    "input": {
        "heading": "Input preparation",
        "reader_question": "How are the input data loaded and prepared before processing?",
        "method_point": "load and prepare the authorized inputs",
    },
    "transformation": {
        "heading": "Representation and transformation",
        "reader_question": "How are the inputs transformed into the method's internal representation?",
        "method_point": "transform the authorized inputs",
    },
    "condition": {
        "heading": "Branching and selection",
        "reader_question": "Which branches and selection rules determine the method's behavior?",
        "method_point": "select the authorized branch and order the operations",
    },
    "output": {
        "heading": "Output generation",
        "reader_question": "How is the final output produced from the processed representation?",
        "method_point": "produce the authorized output",
    },
}
_GENERIC_STAGE_HEADING = re.compile(r"^implementation\s+stage\s+\d+$", re.IGNORECASE)


def _stage_planning(unit_texts: list[str]) -> dict[str, str]:
    """Deterministic reader-facing stage planning from the unit's operations.

    The dominant operation family (input / transformation / condition /
    output) selects the stage heading, reader question, and method point.
    Falls back to the generic transformation plan when the mix is even.
    """

    counts = {"input": 0, "transformation": 0, "condition": 0, "output": 0}
    for text in unit_texts:
        lowered = text.lower()
        if re.search(r"\b(?:loads weights|reads|stores|writes|constructs|initializes)\b", lowered):
            counts["input"] += 1
        if re.search(r"\b(?:computes formula|computes|concatenates|normalizes|reduces|attends|calls)\b", lowered):
            counts["transformation"] += 1
        if re.search(r"\b(?:branches on|selects top k|sorts by|propagates|guards on)\b", lowered):
            counts["condition"] += 1
        if re.search(r"\b(?:returns|emits|outputs|writes back)\b", lowered):
            counts["output"] += 1
    dominant = max(counts, key=lambda role: (counts[role], -["input", "transformation", "condition", "output"].index(role)))
    if counts[dominant] == 0:
        dominant = "transformation"
    return _OPERATION_FAMILY_TO_STAGE[dominant]


def _unit_planning(
    unit_id: str,
    frame: SemanticArgumentFrameV1,
    *,
    obligation_roles: tuple[str, ...] = (),
) -> dict[str, str]:
    """Reader-facing unit planning derived from the closed semantic frame.

    The heading comes from the dominant closed operation family or obligation
    role; the reader question asks about the unit's input -> operation ->
    output structure; the method point names the implementation step the
    section must explain.  These are organizational strings only: they never
    become positive fact anchors, and validators reject internal IDs and
    unsupported purpose/capability/performance language in them.
    """

    slot_counts: dict[str, int] = {
        "input": 0, "transformation": 0, "condition": 0, "output": 0,
    }
    operation_families: set[str] = set()
    for slot in frame.slots:
        if slot.role in slot_counts:
            slot_counts[slot.role] += 1
        operation_families.add(slot.predicate)
    role_heading = next(
        ({"feature": "Feature preparation", "filter": "Filtering and selection"}.get(role, "")
         for role in obligation_roles
         if role in {"feature", "filter"}),
        "",
    )
    if slot_counts["output"] and not slot_counts["transformation"]:
        heading = "Output generation"
    elif slot_counts["condition"] and not slot_counts["transformation"]:
        heading = "Branching and selection"
    elif slot_counts["transformation"] and slot_counts["output"]:
        heading = "Transformation and output"
    elif slot_counts["input"] and slot_counts["transformation"]:
        heading = "Input and transformation"
    elif slot_counts["transformation"]:
        heading = "Transformation"
    elif slot_counts["input"]:
        heading = "Input handling"
    else:
        heading = role_heading or "Method operations"
    input_terms = _planning_terms(
        tuple(item.subject for item in frame.slots if item.role == "input"),
        tuple(item for item in frame.slots if item.role == "input"),
    )
    output_terms = _planning_terms(
        tuple(item.subject for item in frame.slots if item.role == "output"),
        tuple(item for item in frame.slots if item.role == "output"),
    )
    question_parts: list[str] = []
    if slot_counts["input"]:
        question_parts.append(f"how {input_terms} are loaded and prepared")
    if slot_counts["condition"]:
        question_parts.append("which branches and guards select the executed path")
    if slot_counts["transformation"]:
        question_parts.append("how the loaded inputs are transformed into the method representation")
    if slot_counts["output"]:
        question_parts.append(f"how {output_terms} are produced from the processed representation")
    reader_question = (
        "This section explains " + "; ".join(question_parts) + "."
        if question_parts
        else "This section explains the authorized method operations."
    )
    method_point_parts: list[str] = []
    if slot_counts["input"]:
        method_point_parts.append("load the authorized inputs")
    if slot_counts["condition"]:
        method_point_parts.append("apply the authorized branch and guard conditions")
    if slot_counts["transformation"]:
        method_point_parts.append("run the authorized transformations in their flow order")
    if slot_counts["output"]:
        method_point_parts.append("produce the authorized output")
    method_point = (
        " and ".join(method_point_parts) + "."
        if method_point_parts
        else "explain the authorized method operations."
    )
    return {
        "heading": heading,
        "reader_question": reader_question,
        "method_point": method_point,
    }


def _planning_terms(subjects: tuple[str, ...], slots: tuple[Any, ...]) -> str:
    """One short closed-term phrase for planning prose (never factual prose)."""

    terms: list[str] = []
    for subject in subjects:
        short = str(subject).rsplit(".", 1)[-1].rsplit("::", 1)[-1]
        if short and short not in terms:
            terms.append(short)
    if not terms:
        for slot in slots:
            for operand in (slot.operands or ()):
                short = str(operand).rsplit(".", 1)[-1].rsplit("::", 1)[-1]
                if short and short not in terms:
                    terms.append(short)
    if not terms:
        return "the authorized inputs"
    return "the " + ", ".join(terms[:3])


def build_semantic_argument_frame(
    *,
    argument_unit_id: str,
    claim_ids: tuple[str, ...],
    equation_ids: tuple[str, ...],
    configuration_ids: tuple[str, ...],
    claim_by_id: dict[str, Any],
    fact_by_id: dict[str, Any],
    relation_by_id: dict[str, Any],
    obligation_ids: tuple[str, ...],
    authority_lanes: tuple[str, ...],
) -> SemanticArgumentFrameV1:
    """Build the canonical typed semantic argument frame for one unit.

    This is the single frame builder: the Writer consumes the persisted typed
    frame and never re-derives it.  Each slot preserves the fact subject,
    predicate, every scalar or list operand, conditions, and exact claim/fact
    bindings; relations attach to a slot only when the relation ID is in that
    fact/claim's closed relation bindings and an endpoint matches the subject
    or a preserved operand.  Direction comes only from predicate roles and
    authorized typed relations.
    """

    claim_fact_map: dict[str, tuple[str, ...]] = {}
    section_facts: list[Any] = []
    seen_fact_ids: set[str] = set()
    for claim_id in claim_ids:
        claim = claim_by_id.get(claim_id)
        fact_ids = tuple(
            fact_id for fact_id in (getattr(claim, "fact_ids", ()) or ())
            if fact_id in fact_by_id
            and str(getattr(fact_by_id[fact_id], "validation_status", "") or "") == "supported"
        )
        claim_fact_map[claim_id] = fact_ids
        for fact_id in fact_ids:
            if fact_id not in seen_fact_ids:
                seen_fact_ids.add(fact_id)
                section_facts.append(fact_by_id[fact_id])

    slot_fact_ids: list[str] = []
    slots: list[SemanticFlowSlotV1] = []
    slot_by_symbol: dict[tuple[str, str], list[str]] = {}
    unit_relation_ids: set[str] = {
        relation_id
        for claim_id in claim_ids
        for relation_id in (getattr(claim_by_id.get(claim_id), "relation_evidence_ids", ()) or ())
    }
    relation_by_fact: dict[str, list[str]] = {}
    for fact in sorted(section_facts, key=lambda item: str(item.fact_id)):
        slot_id = f"slot:{fact.fact_id}"
        obj = fact.object
        operands = tuple(
            str(item) for item in obj if str(item).strip()
        ) if isinstance(obj, list) else ((str(obj),) if str(obj).strip() else ())
        role = _fact_role(fact.predicate)
        produced = tuple(operands) if role == "output" else ()
        fact_relations = tuple(
            relation_id for relation_id in (
                getattr(fact, "relation_evidence_ids", ()) or ()
            )
            if relation_id in unit_relation_ids and relation_id in relation_by_id
        )
        relation_by_fact[str(fact.fact_id)] = list(fact_relations)
        slot = SemanticFlowSlotV1(
            slot_id=slot_id,
            role=role,
            subject=str(fact.subject),
            predicate=str(fact.predicate),
            operands=operands,
            produced_entities=produced,
            conditions=tuple(str(item) for item in (fact.conditions or ()) if str(item).strip()),
            fact_ids=(str(fact.fact_id),),
            claim_ids=tuple(sorted(
                claim_id for claim_id, fact_ids in claim_fact_map.items()
                if str(fact.fact_id) in fact_ids
            )),
            exact_relation_ids=(),
            authority_lanes=tuple(authority_lanes) or ("executable_hard",),
        )
        slots.append(slot)
        slot_fact_ids.append(str(fact.fact_id))
        slot_by_symbol.setdefault((str(fact.subject), role), []).append(slot_id)
        for operand in operands:
            slot_by_symbol.setdefault((operand, role), []).append(slot_id)

    slot_ids = {item.slot_id for item in slots}
    edges: list[SemanticFlowEdgeV1] = []
    unresolved_relations: list[str] = []
    configuration_binding_relations: list[str] = []
    relation_source_slots: dict[str, list[str]] = {}
    relation_target_slots: dict[str, list[str]] = {}
    # Exact endpoint matching: a relation binds to the slots whose facts carry
    # the relation AND whose source spans equal the relation's resolved
    # operation-level endpoint spans.  Two slots matching the same endpoint is
    # ambiguous and stays unresolved; a symbol-only match is never enough.
    fact_span_to_slots: dict[str, list[str]] = {}
    slot_to_fact: dict[str, str] = {
        item.slot_id: next(iter(item.fact_ids), "") for item in slots
    }
    for item in slots:
        fact_id = next(iter(item.fact_ids), "")
        fact = fact_by_id.get(fact_id)
        for span_id in (getattr(fact, "direct_span_ids", ()) or ()) if fact is not None else ():
            fact_span_to_slots.setdefault(str(span_id), []).append(item.slot_id)
    for relation_id in sorted(unit_relation_ids):
        relation = relation_by_id.get(relation_id)
        if relation is None:
            unresolved_relations.append(relation_id)
            continue
        relation_type = str(getattr(relation, "relation_type", "") or "")
        if relation_type == "configuration_binding":
            # CONFIGURED_BY binds the consuming operation to the exact
            # configuration access/key.  The source endpoint must resolve to a
            # slot; the target is the config access itself (an exact operand
            # substring of the consuming slot, or its own slot).  A relation
            # that cannot bind exactly stays unresolved; it never becomes a
            # flow edge.
            source_slots = _endpoint_slots(
                relation=relation,
                side="source",
                fact_span_to_slots=fact_span_to_slots,
                fact_by_slot=slot_to_fact,
                relation_by_fact=relation_by_fact,
                fact_by_id=fact_by_id,
                slots=slots,
            )
            target_slots = _endpoint_slots(
                relation=relation,
                side="target",
                fact_span_to_slots=fact_span_to_slots,
                fact_by_slot=slot_to_fact,
                relation_by_fact=relation_by_fact,
                fact_by_id=fact_by_id,
                slots=slots,
            )
            target_operands = tuple(
                str(item) for item in (
                    getattr(getattr(relation, "target_endpoint", None), "operands", ()) or ()
                ) if str(item).strip()
            )
            if not source_slots:
                unresolved_relations.append(relation_id)
                continue
            if not target_slots and target_operands:
                # The config access appears as an exact operand substring of
                # the consuming slot's fact (the same check the behavior
                # adapter used to create the relation).
                for slot_id in source_slots:
                    slot_fact_id = next(iter((
                        item.fact_ids for item in slots if item.slot_id == slot_id
                    )), ())
                    slot_fact_id = slot_fact_id[0] if isinstance(slot_fact_id, tuple) and slot_fact_id else str(slot_fact_id or "")
                    fact = fact_by_id.get(str(slot_fact_id))
                    fact_object = getattr(fact, "object", None)
                    fact_terms = (
                        fact_object if isinstance(fact_object, list) else (str(fact_object),)
                    ) if fact_object is not None else ()
                    fact_text = " ".join(str(item) for item in fact_terms)
                    if any(operand and operand in fact_text for operand in target_operands):
                        target_slots.append(slot_id)
                        break
            if not source_slots or not target_slots:
                unresolved_relations.append(relation_id)
                continue
            if set(source_slots) == set(target_slots) and len(target_operands) == 0:
                unresolved_relations.append(relation_id)
                continue
            relation_source_slots[relation_id] = source_slots
            relation_target_slots[relation_id] = target_slots
            configuration_binding_relations.append(relation_id)
            continue
        if relation_type not in {"call_flow", "data_flow", "control_flow", "writes"}:
            unresolved_relations.append(relation_id)
            continue
        source_symbol = str(getattr(relation, "source_symbol", "") or "")
        target_symbol = str(getattr(relation, "target_symbol", "") or "")
        bound_facts = [
            fact_id for fact_id, relation_ids in relation_by_fact.items()
            if relation_id in relation_ids
        ]
        fact_to_slot = {
            next(iter(item.fact_ids)): item.slot_id for item in slots
        }
        bound_slot_ids = {
            fact_to_slot[fact_id] for fact_id in bound_facts
            if fact_id in fact_to_slot
        }
        if not bound_slot_ids:
            unresolved_relations.append(relation_id)
            continue
        source_slots = _endpoint_slots(
            relation=relation,
            side="source",
            fact_span_to_slots=fact_span_to_slots,
            fact_by_slot=slot_to_fact,
            relation_by_fact=relation_by_fact,
            fact_by_id=fact_by_id,
            slots=slots,
        )
        target_slots = _endpoint_slots(
            relation=relation,
            side="target",
            fact_span_to_slots=fact_span_to_slots,
            fact_by_slot=slot_to_fact,
            relation_by_fact=relation_by_fact,
            fact_by_id=fact_by_id,
            slots=slots,
        )
        # A resolved flow edge requires both exact operation-level endpoints.
        # Binding one endpoint and assigning every other bound fact to the
        # missing side invents topology, so partial matches remain explicitly
        # unresolved.
        if not source_slots or not target_slots:
            unresolved_relations.append(relation_id)
            continue
        if set(source_slots) == set(target_slots):
            # A same-slot edge (opaque self-edge) cannot express a directed
            # flow; it stays unresolved.
            unresolved_relations.append(relation_id)
            continue
        relation_source_slots[relation_id] = source_slots
        relation_target_slots[relation_id] = target_slots
        edges.append(SemanticFlowEdgeV1(
            relation_id=relation_id,
            relation_type=relation_type,
            source_symbol=source_symbol,
            target_symbol=target_symbol,
            source_slot_ids=tuple(relation_source_slots[relation_id]),
            target_slot_ids=tuple(relation_target_slots[relation_id]),
            conditions=tuple(str(item) for item in (getattr(relation, "conditions", ()) or ()) if str(item).strip()),
            direct_span_ids=tuple(
                str(item) for item in (getattr(relation, "direct_span_ids", ()) or ())
                if str(item).strip()
            ),
        ))

    # Bind each relation to its exact slot(s).
    for slot in slots:
        fact_id = next(iter(slot.fact_ids), "")
        bound_relations = tuple(
            relation_id for relation_id in relation_by_fact.get(fact_id, ())
            if relation_id in relation_source_slots or relation_id in relation_target_slots
        )
        slots[slots.index(slot)] = slot.model_copy(update={
            "exact_relation_ids": bound_relations,
        })
    slots = list(dict.fromkeys(slots))

    # Ordered slots from exact flow/control/call edges plus stable source
    # order as tie-breaker.  Cycles/ambiguous order stay explicit.
    ordered = _topological_slot_order(slots, edges)
    if ordered is None:
        unresolved_relations.extend(
            edge.relation_id for edge in edges
            if edge.relation_id not in unresolved_relations
        )
        # Cyclic/ambiguous relations are not retained as positive flow edges.
        # The slots still receive a stable serialization order, while the
        # unresolved IDs drive the planning gate fail-closed.
        edges = []
        ordered = [item.slot_id for item in slots]

    frame = SemanticArgumentFrameV1(
        frame_id=f"frame:{argument_unit_id}",
        argument_unit_id=argument_unit_id,
        slots=tuple(slots),
        edges=tuple(edges),
        ordered_slot_ids=tuple(ordered),
        claim_ids=tuple(claim_ids),
        fact_ids=tuple(slot_fact_ids),
        equation_ids=tuple(equation_ids),
        configuration_ids=tuple(configuration_ids),
        configuration_binding_relation_ids=tuple(dict.fromkeys(configuration_binding_relations)),
        unresolved_relation_ids=tuple(dict.fromkeys(unresolved_relations)),
        authority_lanes=tuple(authority_lanes) or ("executable_hard",),
    )
    return frame


def _section_has_endpoint(
    facts_here: dict[str, Any],
    *,
    relation: Any,
    endpoint: Any,
) -> bool:
    """True when an exact operation endpoint binds to a fact in this section.

    The endpoint matches a fact when the fact carries the relation, the
    endpoint's owning symbol equals the fact's scope, the endpoint span equals
    a fact span, and the endpoint operands equal the fact's object (when the
    endpoint carries operands).
    """

    span_id = str(getattr(endpoint, "source_span_id", "") or "")
    symbol_id = str(getattr(endpoint, "symbol_id", "") or "")
    endpoint_operands = tuple(
        str(item) for item in (getattr(endpoint, "operands", ()) or ())
        if str(item).strip()
    )
    if not span_id:
        return False
    relation_id = str(getattr(relation, "relation_id", "") or "")
    for fact in facts_here.values():
        if relation_id not in (getattr(fact, "relation_evidence_ids", ()) or ()):
            continue
        if symbol_id and str(getattr(fact, "scope", "") or "") and symbol_id != str(fact.scope):
            continue
        if span_id not in (getattr(fact, "direct_span_ids", ()) or ()):
            continue
        fact_object = getattr(fact, "object", None)
        fact_operands = tuple(
            str(item) for item in (
                fact_object if isinstance(fact_object, list) else (str(fact_object),)
            ) if str(item).strip()
        )
        if endpoint_operands and fact_operands != endpoint_operands:
            continue
        return True
    return False


def _endpoint_slots(
    *,
    relation: Any,
    side: str,
    fact_span_to_slots: dict[str, list[str]],
    fact_by_slot: dict[str, str],
    relation_by_fact: dict[str, list[str]],
    fact_by_id: dict[str, Any],
    slots: list[SemanticFlowSlotV1],
) -> list[str]:
    """Resolve one relation endpoint to exact slots.

    The endpoint is exact only when the relation's operation-level endpoint
    span matches the direct span of a slot whose fact carries the relation,
    the endpoint's owning symbol equals the fact's scope, and the endpoint's
    exact operands equal the fact's object.  ``fact_by_slot`` maps slot id to
    the fact id it serializes.  A missing endpoint, an unmatched
    span/symbol/operands, or a span shared by several matching slots yields no
    exact slot (the relation stays unresolved).
    """

    endpoint = getattr(relation, f"{side}_endpoint", None)
    if endpoint is None or not getattr(endpoint, "resolved", False):
        return []
    span_id = str(getattr(endpoint, "source_span_id", "") or "")
    if not span_id:
        return []
    symbol_id = str(getattr(endpoint, "symbol_id", "") or "")
    endpoint_operands = tuple(
        str(item) for item in (getattr(endpoint, "operands", ()) or ())
        if str(item).strip()
    )
    exact: list[str] = []
    for slot_id in fact_span_to_slots.get(span_id, []):
        fact_id = fact_by_slot.get(slot_id, "")
        fact = fact_by_id.get(fact_id)
        if not fact_id or fact is None:
            continue
        if relation.relation_id not in relation_by_fact.get(fact_id, []):
            continue
        if symbol_id and str(getattr(fact, "scope", "") or "") and symbol_id != str(fact.scope):
            continue
        fact_object = getattr(fact, "object", None)
        fact_operands = tuple(
            str(item) for item in (
                fact_object if isinstance(fact_object, list) else (str(fact_object),)
            ) if str(item).strip()
        )
        if endpoint_operands and fact_operands != endpoint_operands:
            continue
        exact.append(slot_id)
    return list(dict.fromkeys(exact))


def _topological_slot_order(
    slots: list[SemanticFlowSlotV1],
    edges: list[SemanticFlowEdgeV1],
) -> list[str] | None:
    """Order slots by flow edges (source before target); None on a cycle."""

    incoming: dict[str, int] = {slot.slot_id: 0 for slot in slots}
    outgoing: dict[str, list[str]] = {slot.slot_id: [] for slot in slots}
    for edge in edges:
        for source_slot in edge.source_slot_ids:
            for target_slot in edge.target_slot_ids:
                if source_slot == target_slot:
                    continue
                if source_slot not in incoming or target_slot not in incoming:
                    continue
                if target_slot not in outgoing[source_slot]:
                    outgoing[source_slot].append(target_slot)
                    incoming[target_slot] += 1
    ready = sorted(slot_id for slot_id, count in incoming.items() if count == 0)
    ordered: list[str] = []
    while ready:
        slot_id = ready.pop(0)
        ordered.append(slot_id)
        for target_slot in outgoing[slot_id]:
            incoming[target_slot] -= 1
            if incoming[target_slot] == 0:
                ready.append(target_slot)
                ready.sort()
    if len(ordered) != len(slots):
        return None
    return ordered


def _obligation_prefix(obligation_id: str) -> str:
    """Placement uses exact bindings; keep a deterministic tie-break key only."""

    parts = str(obligation_id).split("-")
    return "-".join(parts[:3]) if len(parts) >= 3 else str(obligation_id)


def _fact_role(predicate: str) -> str:
    lowered = str(predicate).lower()
    if lowered in {
        "loads_weights", "reads", "stores", "writes", "constructs", "initializes",
    }:
        return "input"
    if lowered in {"returns", "emits", "outputs", "writes_back"}:
        return "output"
    if lowered in {
        "branches_on", "selects_top_k", "sorts_by", "propagates", "guards_on",
    }:
        return "condition"
    return "transformation"


def _frame_moves(
    *,
    frame: dict[str, Any],
    equation_ids: tuple[str, ...],
    configuration_ids: tuple[str, ...],
    unresolved: list[str],
    heading: str = "",
) -> tuple[tuple[str, ...], frozenset[str]]:
    """Move template from the unit's semantic frame roles (not claim regexes)."""

    if _heading_is_rhetorical_frame(heading):
        moves = (
            "problem_or_local_context",
            "design_objective",
            "transition_to_next_section",
        )
        return moves, frozenset(moves)
    slot_roles = {str(slot.get("role") or "") for slot in frame.get("slots") or ()}
    if not slot_roles and not equation_ids:
        moves = (
            "problem_or_local_context",
            "design_objective",
            "transition_to_next_section",
        )
        return moves, frozenset(moves)
    moves: list[str] = [
        "problem_or_local_context", "design_objective", "mechanism_overview",
    ]
    required: set[str] = {
        "problem_or_local_context", "design_objective", "mechanism_overview",
        "transition_to_next_section",
    }
    if "transformation" in slot_roles or equation_ids:
        moves.append("algorithm_or_data_flow")
        required.add("algorithm_or_data_flow")
    if "input" in slot_roles or "transformation" in slot_roles:
        moves.append("implementation_realization")
        required.add("implementation_realization")
    if equation_ids:
        moves.extend(("formal_objects_and_notation", "equation_or_derivation"))
        required.add("equation_or_derivation")
    if configuration_ids or "condition" in slot_roles:
        moves.append("configuration_and_branches")
        required.add("configuration_and_branches")
    if "output" in slot_roles:
        moves.append("inference_and_output")
        required.add("inference_and_output")
    if _unresolved_requires_limitation_move(unresolved):
        moves.append("limitations_or_mismatch")
        required.add("limitations_or_mismatch")
    moves.append("transition_to_next_section")
    return tuple(dict.fromkeys(moves)), frozenset(required)


def _move_anchor_ids(
    move: str,
    frame: SemanticArgumentFrameV1 | None,
    equation_ids: tuple[str, ...],
    configuration_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Exact supporting anchor ids per move (closed set; unrelated same-unit
    claims cannot anchor a semantically different move)."""

    if frame is None:
        return ()
    slot_facts: dict[str, list[str]] = {
        "input": [], "transformation": [], "condition": [], "output": [],
    }
    slot_claims: list[str] = []
    edge_facts: list[str] = []
    for slot in frame.slots:
        if slot.role in slot_facts:
            slot_facts[slot.role].extend(slot.fact_ids)
        slot_claims.extend(slot.claim_ids)
    for edge in frame.edges:
        edge_facts.extend(
            fact_id for slot_id in (*edge.source_slot_ids, *edge.target_slot_ids)
            for slot in frame.slots
            if slot.slot_id == slot_id
            for fact_id in slot.fact_ids
        )
    if move == "mechanism_overview":
        return tuple(dict.fromkeys(slot_claims))
    if move == "algorithm_or_data_flow":
        return tuple(dict.fromkeys([*slot_facts["transformation"], *edge_facts, *equation_ids]))
    if move == "implementation_realization":
        return tuple(dict.fromkeys([*slot_facts["input"], *slot_facts["transformation"]]))
    if move == "formal_objects_and_notation":
        return tuple(dict.fromkeys(equation_ids))
    if move == "equation_or_derivation":
        return tuple(dict.fromkeys(equation_ids))
    if move == "configuration_and_branches":
        return tuple(dict.fromkeys([*configuration_ids, *slot_facts["condition"]]))
    if move == "inference_and_output":
        return tuple(dict.fromkeys([*slot_facts["output"], *edge_facts]))
    if move == "training_objective":
        return tuple(dict.fromkeys(slot_facts["transformation"]))
    if move == "limitations_or_mismatch":
        # A gap is an unresolved obligation, never a positive factual anchor.
        return ()
    return ()


def replan_moves_with_trace(
    base_plan: MethodSectionPlanV2,
    *,
    claims: AtomicClaimSetV3,
    equations: EquationClaimSetV1 | None = None,
    configurations: ConfigurationClaimSetV1 | None = None,
    completeness: MethodCompletenessMatrixV1 | None = None,
    facts: Any | None = None,
    evidence_packets_v3: Any | None = None,
    agenda: ReferenceMethodAgendaV1 | None = None,
    coverage_by_obligation: dict[str, tuple[str, ...]] | None = None,
    proposal_caller: Any | None = None,
    story_spine: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1] = (),
    argument_briefs: Any | None = None,
    concept_cards: Any | None = None,
    argument_facets: tuple[Any, ...] | list[Any] = (),
    facet_alignments: tuple[Any, ...] | list[Any] = (),
    facet_policies: tuple[Any, ...] | list[Any] = (),
    publication_field_candidates: tuple[Any, ...] | list[Any] = (),
) -> tuple[MethodSectionPlanV2, dict[str, Any]]:
    """Re-derive the typed semantic graph on the frozen plan's structure.

    The frozen section/unit structure is the planning authority; this path
    re-derives, from each unit's authorized claim content and the closed
    typed relation set: the canonical per-unit semantic argument frames, the
    exact per-row obligation placements (claim bindings, then agenda, then
    coverage fact bindings), reader-facing unit planning, the move-specific
    authority proofs, and the section dependency graph from authorized
    producer/consumer relations.  Unplaced critical/high rows remain fully
    typed assignments with an unresolved reason and fail the plan gate.
    """

    claim_by_id = {item.claim_id: item for item in claims.claims}
    equation_by_claim = {
        item.prose_claim_id: item
        for item in (equations.equations if equations is not None else [])
        if item.prose_claim_id
    }
    config_items = tuple(configurations.claims) if configurations is not None else ()
    matrix_rows = list(completeness.items) if completeness is not None else []
    unit_by_id = {item.argument_unit_id: item for item in base_plan.argument_units}
    fact_by_id = {
        str(item.fact_id): item for item in (facts.facts if facts is not None else ())
    }
    relation_by_id = {
        str(relation.relation_id): relation
        for packet in (evidence_packets_v3.packets if evidence_packets_v3 is not None else ())
        for relation in packet.relations
    }
    coverage_by_obligation = coverage_by_obligation or {}
    agenda_by_id: dict[str, Any] = {}
    for agenda_item in (agenda.obligations if agenda is not None else ()):
        agenda_by_id[str(agenda_item.obligation_id)] = agenda_item
        source_obligation_id = str(
            getattr(agenda_item, "source_obligation_id", "") or ""
        )
        if source_obligation_id:
            agenda_by_id.setdefault(source_obligation_id, agenda_item)

    unit_frames: dict[str, SemanticArgumentFrameV1] = {}
    unit_planning: dict[str, dict[str, str]] = {}
    unit_roles: dict[str, tuple[str, ...]] = {}
    unit_equation_ids: dict[str, tuple[str, ...]] = {}
    unit_configuration_ids: dict[str, tuple[str, ...]] = {}
    unit_relation_ids: dict[str, set[str]] = {}
    unit_fact_ids: dict[str, set[str]] = {}
    unit_claim_ids: dict[str, set[str]] = {}
    unit_source_obligation_ids: dict[str, set[str]] = {}
    unit_anchor_ids: dict[str, dict[str, tuple[str, ...]]] = {}
    unit_unresolved_assignments: dict[str, list[ObligationMoveAssignmentV1]] = {}
    heading_by_unit = {
        unit_id: section.heading
        for section in base_plan.sections
        for unit_id in section.argument_unit_ids
    }
    for unit in base_plan.argument_units:
        base_claim_ids = tuple(dict.fromkeys(
            str(claim_id).strip()
            for claim_id in (unit.claim_ids or ())
            if str(claim_id).strip() and str(claim_id).strip() in claim_by_id
        ))
        base_claim_id_set = set(base_claim_ids)
        persisted_source_ids = {
            str(obligation_id)
            for obligation_id in getattr(unit, "source_obligation_ids", ())
            if str(obligation_id).strip()
        }
        # Replanning is a source refresh, so a persisted membership from an
        # earlier plan cannot outrank the current semantic-stage compiler.
        # Replay only a complete stage whose ordered claims are still present
        # in this unit.  This prevents a previously polluted unit (for
        # example, one carrying every callback coverage edge) from exporting
        # those old obligations to the new paragraph plan.  Claim coverage is
        # interpreted through the same closed-group rule as the initial build.
        replayed_source_ids: set[str] = set()
        has_stage_groups = bool(getattr(claims, "semantic_stage_groups", ()))
        stage_claim_ids: list[str] = []
        for group in getattr(claims, "semantic_stage_groups", ()):
            ordered_group_claim_ids = tuple(
                str(claim_id).strip()
                for claim_id in (getattr(group, "ordered_claim_ids", ()) or ())
                if str(claim_id).strip() and str(claim_id).strip() in base_claim_id_set
            )
            if not ordered_group_claim_ids:
                continue
            selected_group_claims = [
                claim_by_id[claim_id] for claim_id in ordered_group_claim_ids
            ]
            declared_group_obligations = tuple(dict.fromkeys(
                str(obligation_id).strip()
                for obligation_id in (
                    getattr(group, "covers_obligation_ids", ()) or ()
                )
                if str(obligation_id).strip()
            ))
            closed_group_obligations = set(_closed_group_obligation_ids(
                declared_group_obligations,
                selected_group_claims,
            ))
            if set(ordered_group_claim_ids) == set(
                getattr(group, "ordered_claim_ids", ()) or ()
            ):
                replayed_source_ids.update(closed_group_obligations)
            primary_group_obligation = next(
                (
                    obligation_id for obligation_id in declared_group_obligations
                    if "O-STAGE-" in obligation_id.upper()
                ),
                declared_group_obligations[0]
                if declared_group_obligations else "",
            )
            # ``unit_source_obligation_ids`` is filled after this loop.  Use
            # the persisted source only to choose the claim projection; the
            # authoritative replayed set is assigned immediately below.
            current_group_source = set(persisted_source_ids)
            if primary_group_obligation and primary_group_obligation in current_group_source:
                stage_claim_ids.extend(ordered_group_claim_ids)
            elif closed_group_obligations.intersection(current_group_source):
                for claim_id in ordered_group_claim_ids:
                    claim = claim_by_id[claim_id]
                    covered = {
                        str(value).strip()
                        for value in (claim.covers_obligation_ids or ())
                        if str(value).strip()
                    }
                    if len(covered) == 1 or any(
                        obligation_id in claim_id
                        for obligation_id in current_group_source
                    ):
                        stage_claim_ids.append(claim_id)
        if has_stage_groups:
            replayed_source_ids = set(replayed_source_ids)
        unit_source_obligation_ids[unit.argument_unit_id] = (
            replayed_source_ids
            if has_stage_groups and replayed_source_ids
            else persisted_source_ids
        )
        source_ids_for_claim_projection = unit_source_obligation_ids[unit.argument_unit_id]
        if has_stage_groups:
            for claim_id in base_claim_ids:
                claim = claim_by_id[claim_id]
                covered = {
                    str(value).strip()
                    for value in (claim.covers_obligation_ids or ())
                    if str(value).strip()
                }
                if not covered.intersection(source_ids_for_claim_projection):
                    continue
                if len(covered) == 1 or any(
                    obligation_id in claim_id
                    for obligation_id in source_ids_for_claim_projection
                ):
                    stage_claim_ids.append(claim_id)
        effective_claim_ids = tuple(dict.fromkeys(
            stage_claim_ids if has_stage_groups and stage_claim_ids else base_claim_ids
        ))
        equation_ids = tuple(
            equation_by_claim[claim_id].equation_id
            for claim_id in effective_claim_ids
            if claim_id in equation_by_claim
        )
        configuration_ids = tuple(
            config.configuration_id
            for config in config_items
            if config.active and _configuration_binds_unit(config, [
                claim_by_id[claim_id]
                for claim_id in effective_claim_ids
                if claim_id in claim_by_id
            ])
        )
        unit_equation_ids[unit.argument_unit_id] = equation_ids
        unit_configuration_ids[unit.argument_unit_id] = configuration_ids
        # Keep every downstream projection on the same refreshed claim set.
        # In particular, ``place_obligation_assignments`` consumes this map;
        # leaving it empty made the frame look populated while placement saw
        # no claim authority at all.
        unit_claim_ids[unit.argument_unit_id] = set(effective_claim_ids)
        unit_relation_ids[unit.argument_unit_id] = {
            relation_id
            for claim_id in effective_claim_ids
            for relation_id in (
                getattr(claim_by_id.get(claim_id), "relation_evidence_ids", ()) or ()
            )
        }
        unit_fact_ids[unit.argument_unit_id] = {
            str(fact_id)
            for claim_id in effective_claim_ids
            for fact_id in (
                getattr(claim_by_id.get(claim_id), "fact_ids", ()) or ()
            )
        }
        row_roles = tuple(dict.fromkeys(
            str(item.role) for item in matrix_rows
            if item.role and (
                str(item.obligation_id) in unit_source_obligation_ids[unit.argument_unit_id]
                or (
                    bool(item.claim_ids)
                    and set(item.claim_ids) <= set(effective_claim_ids)
                )
            )
        ))
        unit_roles[unit.argument_unit_id] = row_roles
        frame = build_semantic_argument_frame(
            argument_unit_id=unit.argument_unit_id,
            claim_ids=effective_claim_ids,
            equation_ids=equation_ids,
            configuration_ids=configuration_ids,
            claim_by_id=claim_by_id,
            fact_by_id=fact_by_id,
            relation_by_id=relation_by_id,
            obligation_ids=(),
            authority_lanes=unit.authority_lanes,
        )
        unit_frames[unit.argument_unit_id] = frame
        unit_planning[unit.argument_unit_id] = _unit_planning(
            unit.argument_unit_id, frame, obligation_roles=row_roles,
        )
        unit_anchor_ids[unit.argument_unit_id] = {
            move: _move_anchor_ids(move, frame, equation_ids, configuration_ids)
            for move in _moves_from_frame(
                frame,
                equation_ids,
                configuration_ids,
                heading=heading_by_unit.get(unit.argument_unit_id, ""),
            )
        }

    assignments, placement_trace = place_obligation_assignments(
        matrix_rows=matrix_rows,
        units=base_plan.argument_units,
        section_by_unit={
            unit_id: section.section_id
            for section in base_plan.sections
            for unit_id in section.argument_unit_ids
        },
        unit_frames=unit_frames,
        unit_fact_ids=unit_fact_ids,
        unit_claim_ids=unit_claim_ids,
        unit_source_obligation_ids=unit_source_obligation_ids,
        unit_roles=unit_roles,
        unit_equation_ids=unit_equation_ids,
        unit_configuration_ids=unit_configuration_ids,
        coverage_by_obligation=coverage_by_obligation,
        agenda_by_id=agenda_by_id,
        proposal_caller=proposal_caller,
    )
    assignments_by_obligation = {
        item.obligation_id: item for item in assignments
    }
    unit_moves: dict[str, tuple[str, ...]] = {}
    for unit in base_plan.argument_units:
        unit_unresolved_assignments[unit.argument_unit_id] = [
            item for item in assignments
            if item.argument_unit_id == unit.argument_unit_id
            and item.placement_state in {"assigned", "external_pending"}
            and item.status not in _SUPPORTED_STATUSES
        ]
        frame = unit_frames.get(unit.argument_unit_id)
        moves = _moves_from_frame(
            frame,
            unit_equation_ids.get(unit.argument_unit_id, ()),
            unit_configuration_ids.get(unit.argument_unit_id, ()),
            heading=heading_by_unit.get(unit.argument_unit_id, ""),
        )
        moves = (*moves, *(
            item.required_move for item in assignments
            if item.argument_unit_id == unit.argument_unit_id
            and item.placement_state in {"assigned", "external_pending"}
            and item.required_move
        ))
        if _unresolved_requires_limitation_move(
            unit_unresolved_assignments.get(unit.argument_unit_id, [])
        ):
            moves = (*moves, "limitations_or_mismatch")
        unit_moves[unit.argument_unit_id] = tuple(dict.fromkeys(moves))

    # Materialize the refreshed unit projection before rebuilding sections.
    # The old implementation rebuilt paragraphs from ``base_plan`` and only
    # attached the refreshed source obligations at the very end.  That made
    # the paragraph planner, brief classifier, and MethodUnit compiler all
    # observe different ownership state in one replay.
    refreshed_briefs_by_unit: dict[str, tuple[str, ...]] = {}
    if argument_briefs is not None:
        briefs = tuple(getattr(argument_briefs, "briefs", ()) or ())
        assigned_brief_ids: set[str] = set()
        for unit in base_plan.argument_units:
            source_ids = unit_source_obligation_ids.get(unit.argument_unit_id, set())
            owned = []
            for brief in briefs:
                brief_id = str(getattr(brief, "brief_id", "") or "").strip()
                if not brief_id or brief_id in assigned_brief_ids:
                    continue
                brief_obligations = {
                    str(value).strip()
                    for value in (getattr(brief, "obligation_ids", ()) or ())
                    if str(value).strip()
                }
                if source_ids.intersection(brief_obligations):
                    owned.append(brief_id)
                    assigned_brief_ids.add(brief_id)
            refreshed_briefs_by_unit[unit.argument_unit_id] = tuple(owned)

    refreshed_concepts_by_unit: dict[str, tuple[str, ...]] = {}
    if concept_cards is not None:
        cards = tuple(getattr(concept_cards, "cards", ()) or ())
        binding_by_key = {
            str(getattr(binding, "concept_key", "") or "").strip(): tuple(
                str(value).strip()
                for value in (getattr(binding, "source_obligation_ids", ()) or ())
                if str(value).strip()
            )
            for binding in (getattr(concept_cards, "bindings", ()) or ())
            if str(getattr(binding, "concept_key", "") or "").strip()
        }
        assigned_concept_keys: set[str] = set()
        for unit in base_plan.argument_units:
            source_ids = unit_source_obligation_ids.get(unit.argument_unit_id, set())
            owned = []
            for card in cards:
                concept_key = str(getattr(card, "concept_key", "") or "").strip()
                if not concept_key or concept_key in assigned_concept_keys:
                    continue
                if source_ids.intersection(binding_by_key.get(concept_key, ())):
                    owned.append(concept_key)
                    assigned_concept_keys.add(concept_key)
            refreshed_concepts_by_unit[unit.argument_unit_id] = tuple(owned)

    refreshed_units: list[MethodArgumentUnitV1] = []
    for unit in base_plan.argument_units:
        update: dict[str, Any] = {
            "claim_ids": tuple(effective_claim_ids),
            "equation_ids": unit_equation_ids.get(unit.argument_unit_id, ()),
            "configuration_ids": unit_configuration_ids.get(unit.argument_unit_id, ()),
            "behavior_relation_ids": tuple(sorted(
                unit_relation_ids.get(unit.argument_unit_id, set())
            )),
            "source_obligation_ids": tuple(sorted(
                unit_source_obligation_ids.get(unit.argument_unit_id, set())
            )),
            "semantic_frame": unit_frames.get(unit.argument_unit_id),
            "obligation_assignments": tuple(
                item for item in assignments
                if item.argument_unit_id == unit.argument_unit_id
            ),
            "unresolved_inputs": tuple(
                f"{item.obligation_id}:{item.status}"
                for item in unit_unresolved_assignments.get(unit.argument_unit_id, [])
            ),
        }
        if argument_briefs is not None:
            brief_ids = refreshed_briefs_by_unit.get(unit.argument_unit_id, ())
            brief_by_id = {
                str(getattr(brief, "brief_id", "") or "").strip(): brief
                for brief in (getattr(argument_briefs, "briefs", ()) or ())
                if str(getattr(brief, "brief_id", "") or "").strip()
            }
            update.update({
                "brief_ids": brief_ids,
                "verified_brief_ids": tuple(
                    brief_id for brief_id in brief_ids
                    if bool(getattr(brief_by_id.get(brief_id), "may_enter_verified", False))
                ),
                "caveated_brief_ids": tuple(
                    brief_id for brief_id in brief_ids
                    if not bool(getattr(brief_by_id.get(brief_id), "may_enter_verified", False))
                ),
                "brief_order": brief_ids,
            })
        if concept_cards is not None:
            concept_keys = refreshed_concepts_by_unit.get(unit.argument_unit_id, ())
            card_by_key = {
                str(getattr(card, "concept_key", "") or "").strip(): card
                for card in (getattr(concept_cards, "cards", ()) or ())
                if str(getattr(card, "concept_key", "") or "").strip()
            }
            update.update({
                "concept_card_ids": concept_keys,
                "verified_concept_card_ids": tuple(
                    key for key in concept_keys
                    if bool(getattr(card_by_key.get(key), "may_enter_verified", False))
                ),
                "caveated_concept_card_ids": tuple(
                    key for key in concept_keys
                    if not bool(getattr(card_by_key.get(key), "may_enter_verified", False))
                ),
                "concept_card_order": concept_keys,
            })
        refreshed_units.append(unit.model_copy(update=update))

    refreshed_unit_by_id = {
        unit.argument_unit_id: unit for unit in refreshed_units
    }
    unit_by_id = refreshed_unit_by_id

    trace_rows: list[dict[str, Any]] = []
    section_data: list[dict[str, Any]] = []
    for section in base_plan.sections:
        section_units = [
            unit_by_id[unit_id] for unit_id in section.argument_unit_ids
            if unit_id in unit_by_id
        ]
        for unit in section_units:
            frame = unit_frames.get(unit.argument_unit_id)
            equation_ids = unit_equation_ids.get(unit.argument_unit_id, ())
            configuration_ids = unit_configuration_ids.get(unit.argument_unit_id, ())
            unresolved = [
                f"{item.obligation_id}:{item.status}"
                for item in unit_unresolved_assignments.get(unit.argument_unit_id, [])
            ]
            trace_rows.append({
                "section_id": section.section_id,
                "unit_id": unit.argument_unit_id,
                "heading": unit_planning.get(unit.argument_unit_id, {}).get("heading", section.heading),
                "reader_question": unit_planning.get(unit.argument_unit_id, {}).get("reader_question", ""),
                "method_point": unit_planning.get(unit.argument_unit_id, {}).get("method_point", ""),
                "frame": frame.model_dump(mode="json") if frame is not None else {},
                "claim_ids": list(unit.claim_ids),
                "equation_ids": list(equation_ids),
                "configuration_ids": list(configuration_ids),
                "moves": list(unit_moves.get(unit.argument_unit_id, ())),
                "move_anchor_ids": {
                    move: list(anchor_ids)
                    for move, anchor_ids in unit_anchor_ids.get(unit.argument_unit_id, {}).items()
                },
                "obligation_ids": [
                    item.obligation_id for item in unit_unresolved_assignments.get(unit.argument_unit_id, [])
                ],
                "unresolved": unresolved,
            })
        section_data.append({
            "section": section,
            "units": section_units,
        })

    # Section dependencies from authorized typed relations whose exact
    # operation-level endpoints bind to slots in different sections
    # (producer -> consumer).  Symbol-only or unresolved relations never
    # create a dependency.
    slot_to_section: dict[str, str] = {}
    section_facts: dict[str, dict[str, Any]] = {}
    section_slot_facts: dict[str, dict[str, str]] = {}
    for entry in section_data:
        section_id = entry["section"].section_id
        facts_here: dict[str, Any] = {}
        slot_facts: dict[str, str] = {}
        for unit in entry["units"]:
            frame = unit_frames.get(unit.argument_unit_id)
            if frame is not None:
                for slot in frame.slots:
                    slot_to_section[slot.slot_id] = section_id
                    fact_id = next(iter(slot.fact_ids), "")
                    if fact_id:
                        slot_facts[slot.slot_id] = fact_id
                        fact = fact_by_id.get(fact_id)
                        if fact is not None:
                            facts_here[fact_id] = fact
        section_facts[section_id] = facts_here
        section_slot_facts[section_id] = slot_facts

    ordered_section_ids = [entry["section"].section_id for entry in section_data]
    section_dependencies: dict[str, list[str]] = {}
    for index, entry in enumerate(section_data):
        section_id = entry["section"].section_id
        dependencies: list[str] = []
        for relation in relation_by_id.values():
            relation_type = str(getattr(relation, "relation_type", "") or "")
            if relation_type not in {"data_flow", "writes"}:
                continue
            source_endpoint = getattr(relation, "source_endpoint", None)
            target_endpoint = getattr(relation, "target_endpoint", None)
            if source_endpoint is None or target_endpoint is None:
                continue
            if not getattr(source_endpoint, "resolved", False) or not getattr(target_endpoint, "resolved", False):
                continue
            source_sections = [
                earlier_id for earlier_id in ordered_section_ids[:index]
                if _section_has_endpoint(
                    section_facts.get(earlier_id, {}),
                    relation=relation,
                    endpoint=source_endpoint,
                )
            ]
            target_here = _section_has_endpoint(
                section_facts.get(section_id, {}),
                relation=relation,
                endpoint=target_endpoint,
            )
            if source_sections and target_here:
                for earlier_id in source_sections:
                    if earlier_id not in dependencies:
                        dependencies.append(earlier_id)
        section_dependencies[section_id] = dependencies

    rebuilt_sections: list[SectionArgumentGraphV1] = []
    for entry in section_data:
        section = entry["section"]
        section_units = entry["units"]
        all_lanes = tuple(dict.fromkeys(
            lane for unit in section_units for lane in unit.authority_lanes
        ))
        section_unresolved = tuple(dict.fromkeys(
            item
            for unit in section_units
            for item in unit_unresolved_assignments.get(unit.argument_unit_id, [])
        ))
        section_moves = tuple(dict.fromkeys(
            move for unit in section_units
            for move in unit_moves.get(unit.argument_unit_id, ())
        ))
        move_objects = tuple(
            _bind_move_anchor(
                SectionArgumentMoveV1(
                    move=move,
                    argument_unit_ids=tuple(
                        unit.argument_unit_id
                        for unit in section_units
                        if move in unit_moves.get(unit.argument_unit_id, ())
                    ),
                    paragraph_budget=0 if move == "transition_to_next_section" else max(
                        1, min(3, round(sum(
                            unit.information_weight for unit in section_units
                            if move in unit_moves.get(unit.argument_unit_id, ())
                        ) / 8)),
                    ),
                    information_budget=max(0.25, round(sum(
                        unit.information_weight for unit in section_units
                        if move in unit_moves.get(unit.argument_unit_id, ())
                    ) / max(1, len(section_moves)), 3)),
                    allowed_authority_lanes=_move_authority_lanes(
                        move,
                        all_lanes=all_lanes,
                    ),
                    required=_required_move(
                        move,
                        section_units,
                        unit_frames,
                        unit_equation_ids,
                        unit_configuration_ids,
                        unit_unresolved_assignments,
                        heading=section.heading,
                    ),
                ),
                section_units=section_units,
            )
            for move in section_moves
        )
        move_objects = _ensure_unanchored_formula_move(
            move_objects, section_units=section_units, heading=section.heading,
        )
        if section.section_id == ordered_section_ids[-1]:
            move_objects = tuple(
                move.model_copy(update={"required": False})
                if move.move == "transition_to_next_section"
                else move
                for move in move_objects
            )
        rebuilt_sections.append(_rebuild_section(
            section=section,
            section_units=section_units,
            move_objects=move_objects,
            unit_planning=unit_planning,
            section_dependencies=section_dependencies,
            section_unresolved=section_unresolved,
            unit_frames=unit_frames,
            argument_facets=argument_facets,
            facet_alignments=facet_alignments,
            publication_field_candidates=publication_field_candidates,
        ))
    rebuilt_sections = _enrich_section_content_contracts(
        rebuilt_sections,
        refreshed_units,
        story_spine=story_spine,
        concept_cards=concept_cards,
        argument_briefs=argument_briefs,
        argument_facets=argument_facets,
        facet_alignments=facet_alignments,
        publication_field_candidates=publication_field_candidates,
        equations=equations,
        unit_frames=unit_frames,
    )
    authoritative_facet_projection = bool(argument_facets or publication_field_candidates)
    allowed_facet_ids_by_section: dict[str, set[str]] | None = None
    allowed_field_ids_by_section: dict[str, set[str]] | None = None
    allowed_formula_ids_by_section: dict[str, set[str]] | None = None
    if authoritative_facet_projection:
        facet_values = tuple(argument_facets or ())
        allowed_facet_ids_by_section = {}
        allowed_field_ids_by_section = {}
        allowed_formula_ids_by_section = {}
        for graph in rebuilt_sections:
            section_units = [
                refreshed_unit_by_id[unit_id]
                for unit_id in graph.argument_unit_ids
                if unit_id in refreshed_unit_by_id
            ]
            section_brief_ids = {
                str(brief_id).strip()
                for unit in section_units
                for brief_id in (unit.brief_order or unit.brief_ids)
                if str(brief_id).strip()
            }
            current_facet_ids = {
                str(getattr(facet, "facet_id", "") or "").strip()
                for facet in facet_values
                if str(getattr(facet, "facet_id", "") or "").strip()
                and (
                    str(getattr(facet, "brief_id", "") or "").strip() in section_brief_ids
                    or (
                        not str(getattr(facet, "brief_id", "") or "").strip()
                        and any(
                            facet_id in {
                                str(value).strip()
                                for paragraph in graph.paragraphs
                                for value in paragraph.required_facet_ids
                            }
                            for facet_id in (
                                str(getattr(facet, "facet_id", "") or "").strip(),
                            )
                        )
                    )
                )
            }
            current_facet_ids.update(
                str(value).strip()
                for paragraph in graph.paragraphs
                for value in paragraph.required_facet_ids
                if str(value).strip()
            )
            allowed_facet_ids_by_section[graph.section_id] = current_facet_ids
            allowed_field_ids_by_section[graph.section_id] = {
                str(getattr(candidate, "candidate_id", "") or "").strip()
                for candidate in (publication_field_candidates or ())
                if str(getattr(candidate, "candidate_id", "") or "").strip()
                and str(getattr(candidate, "facet_id", "") or "").strip()
                in current_facet_ids
            } | {
                str(value).strip()
                for paragraph in graph.paragraphs
                for value in paragraph.required_field_candidate_ids
                if str(value).strip()
            }
            allowed_formula_ids_by_section[graph.section_id] = {
                str(value).strip()
                for value in graph.formula_obligation_ids
                if str(value).strip()
            } | {
                str(value).strip()
                for paragraph in graph.paragraphs
                for value in paragraph.formula_obligation_ids
                if str(value).strip()
            } | {
                f"formula:facet:{facet_id}"
                for facet_id in current_facet_ids
                if any(
                    str(getattr(facet, "facet_id", "") or "").strip() == facet_id
                    and str(getattr(facet, "formula_expectation", "none") or "none") != "none"
                    for facet in facet_values
                )
            }
    rebuilt_sections = _restore_prior_paragraph_identities(
        prior_sections=base_plan.sections,
        rebuilt_sections=rebuilt_sections,
        allowed_facet_ids_by_section=allowed_facet_ids_by_section,
        allowed_field_ids_by_section=allowed_field_ids_by_section,
        allowed_formula_ids_by_section=allowed_formula_ids_by_section,
    )
    proofs = resolve_move_authority_proofs(
        sections=tuple(rebuilt_sections),
        units=refreshed_units,
        unit_frames=unit_frames,
        unit_equation_ids=unit_equation_ids,
        unit_configuration_ids=unit_configuration_ids,
        assignments=assignments,
    )
    total_page_budget = base_plan.total_page_budget or sum(
        graph.page_budget for graph in rebuilt_sections
    )
    rebuilt_units = tuple(
        unit.model_copy(update={
            "research_question": unit_planning.get(
                unit.argument_unit_id, {}
            ).get("reader_question", unit.research_question),
            "design_objective": unit_planning.get(
                unit.argument_unit_id, {}
            ).get("method_point", unit.design_objective),
            "semantic_frame": unit_frames.get(unit.argument_unit_id),
            "obligation_assignments": tuple(
                item for item in assignments
                if item.argument_unit_id == unit.argument_unit_id
            ),
            "source_obligation_ids": tuple(sorted(
                unit_source_obligation_ids.get(unit.argument_unit_id, set())
            )),
            "unresolved_inputs": tuple(
                f"{item.obligation_id}:{item.status}"
                for item in unit_unresolved_assignments.get(unit.argument_unit_id, [])
            ),
        })
        for unit in refreshed_units
    )
    if base_plan.method_units:
        method_units, rebuilt_sections, method_unit_trace = (
            _preserve_incumbent_method_unit_surface(
                prior_plan=base_plan,
                rebuilt_sections=list(rebuilt_sections),
            )
        )
    else:
        method_units, rebuilt_sections, method_unit_trace = _build_method_units_v2(
            list(rebuilt_sections),
            rebuilt_units,
            argument_facets=argument_facets,
            facet_alignments=facet_alignments,
            publication_field_candidates=publication_field_candidates,
            facts=facts,
            unit_frames=unit_frames,
        )
    # Validate the finished projection, after MethodUnit compaction has had a
    # chance to place hard facet targets.  A fresh source projection may move
    # or retire identities from a stale frozen plan, so conservation is
    # checked against the current authoritative set rather than against every
    # historical id in ``base_plan``.
    identity_regressions: list[str] = []
    actual_story_ids = {
        story_id
        for graph in rebuilt_sections
        for story_id in graph.story_node_ids
    }
    actual_brief_ids = {
        brief_id
        for graph in rebuilt_sections
        for brief_id in (*graph.primary_brief_ids, *graph.supporting_brief_ids)
    }
    actual_facet_ids = {
        facet_id
        for graph in rebuilt_sections
        for paragraph in (graph.paragraphs or ())
        for facet_id in paragraph.required_facet_ids
    }
    if argument_briefs is not None or authoritative_facet_projection or story_spine:
        expected_brief_ids = {
            brief_id
            for unit in rebuilt_units
            for brief_id in (unit.brief_order or unit.brief_ids)
            if str(brief_id).strip()
        }
        missing_briefs = sorted(expected_brief_ids - actual_brief_ids)
        if missing_briefs:
            identity_regressions.append(
                f"current:brief_ids:{','.join(missing_briefs)}"
            )
        if authoritative_facet_projection:
            expected_facet_ids = {
                str(getattr(facet, "facet_id", "") or "").strip()
                for facet in (argument_facets or ())
                if str(getattr(facet, "facet_id", "") or "").strip()
                and (
                    bool(getattr(facet, "required", False))
                    or str(getattr(facet, "formula_expectation", "none") or "none") != "none"
                )
                and str(getattr(facet, "brief_id", "") or "").strip()
                in expected_brief_ids
            }
            missing_facets = sorted(expected_facet_ids - actual_facet_ids)
            if missing_facets:
                identity_regressions.append(
                    f"current:facet_ids:{','.join(missing_facets)}"
                )
        if story_spine:
            expected_story_ids = {
                node.story_node_id
                for node in story_spine
                if any(
                    set(node.linked_obligation_ids).intersection(
                        set(unit.source_obligation_ids)
                    )
                    for unit in rebuilt_units
                )
            }
            missing_stories = sorted(expected_story_ids - actual_story_ids)
            if missing_stories:
                identity_regressions.append(
                    f"current:story_node_ids:{','.join(missing_stories)}"
                )
    else:
        before_by_section = {
            graph.section_id: {
                "story_node_ids": set(graph.story_node_ids),
                "primary_brief_ids": set(graph.primary_brief_ids),
                "supporting_brief_ids": set(graph.supporting_brief_ids),
                "facet_ids": {
                    facet_id
                    for paragraph in (graph.paragraphs or ())
                    for facet_id in paragraph.required_facet_ids
                },
            }
            for graph in base_plan.sections
        }
        for graph in rebuilt_sections:
            before = before_by_section.get(graph.section_id, {})
            after = {
                "story_node_ids": set(graph.story_node_ids),
                "primary_brief_ids": set(graph.primary_brief_ids),
                "supporting_brief_ids": set(graph.supporting_brief_ids),
                "facet_ids": {
                    facet_id
                    for paragraph in (graph.paragraphs or ())
                    for facet_id in paragraph.required_facet_ids
                },
            }
            for name in before:
                removed = sorted(before[name] - after[name])
                if removed:
                    identity_regressions.append(
                        f"{graph.section_id}:{name}:{','.join(removed)}"
                    )
    if identity_regressions:
        raise ValueError(
            "replan_identity_regression:" + ";".join(identity_regressions)
        )
    unplaced_assignments = tuple(
        item for item in assignments if item.placement_state == "unplaced"
    )
    incomplete_extra = tuple(
        f"unresolved:{item.obligation_id}" for item in unplaced_assignments
    )
    plan = base_plan.model_copy(update={
        "sections": tuple(rebuilt_sections),
        "argument_units": rebuilt_units,
        "method_units": tuple(method_units) if method_units else base_plan.method_units,
        "incomplete_sections": tuple(dict.fromkeys([
            *base_plan.incomplete_sections,
            *incomplete_extra,
        ])),
        "obligation_assignments": tuple(assignments),
        "move_authority_proofs": tuple(proofs),
        "critical_high_obligation_ids": tuple(
            item.obligation_id for item in matrix_rows
            if item.importance in {"critical", "high"}
        ),
        "completeness_digest": completeness.content_digest if completeness else "",
        "total_page_budget": round(total_page_budget, 3),
    })
    # ``model_copy`` intentionally skips Pydantic validation.  Re-parse the
    # complete production plan so duplicate/unknown assignment, proof, unit,
    # section, and move bindings cannot bypass the closed-ID contract.
    plan = MethodSectionPlanV2.model_validate(plan.model_dump(mode="json"))
    trace = {
        "schema_version": "2.0",
        "plan_id": base_plan.plan_id,
        "method_name": base_plan.method_name,
        "mode": "replan_typed_semantic_graph_on_frozen_structure",
        "input_digests": {
            "claims": claims.content_digest,
            "equations": equations.content_digest if equations else "",
            "configurations": configurations.content_digest if configurations else "",
            "completeness": completeness.content_digest if completeness else "",
            "facts": facts.content_digest if facts is not None else "",
            "agenda": agenda.content_digest if agenda is not None else "",
            "relations": (
                "sha256:" + hashlib.sha256(
                    json.dumps({
                        relation_id: {
                            "relation_type": str(getattr(relation, "relation_type", "") or ""),
                            "source": str(getattr(relation, "source_symbol", "") or ""),
                            "target": str(getattr(relation, "target_symbol", "") or ""),
                        }
                        for relation_id, relation in sorted(relation_by_id.items())
                    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                if relation_by_id else ""
            ),
        },
        "section_dependencies": section_dependencies,
        "obligation_assignments": [item.model_dump(mode="json") for item in assignments],
        "move_authority_proofs": [item.model_dump(mode="json") for item in proofs],
        "placement": placement_trace,
        "sections": trace_rows,
        "method_units": method_unit_trace,
    }
    return plan, trace


_SUPPORTED_STATUSES = frozenset({
    "supported_by_repository",
})

# Gap rows that actually need the caveat/mismatch rhetorical move.  Ordinary
# partial support and author/literature confirmation hang on the owning
# content move (or the review queue) instead of a generic limitations bucket.
_LIMITATION_REQUIRED_STATUSES = frozenset({
    "paper_code_mismatch",
    "explicit_code_gap",
    "out_of_scope",
    "unverified_by_repository",
})


def _unresolved_status(item: Any) -> str:
    """Status token from an assignment object or ``obligation:status`` string."""

    status = getattr(item, "status", None)
    if status is not None:
        return str(status)
    text = str(item or "")
    if ":" in text:
        return text.rsplit(":", 1)[-1]
    return text


def _unresolved_requires_limitation_move(unresolved: Any) -> bool:
    """True only when a row is a real mismatch/gap, not partial support."""

    return any(
        _unresolved_status(item) in _LIMITATION_REQUIRED_STATUSES
        for item in (unresolved or ())
    )


def _required_move(
    move: str,
    section_units: list[MethodArgumentUnitV1],
    unit_frames: dict[str, SemanticArgumentFrameV1],
    unit_equation_ids: dict[str, tuple[str, ...]],
    unit_configuration_ids: dict[str, tuple[str, ...]],
    unit_unresolved_assignments: dict[str, list[ObligationMoveAssignmentV1]],
    heading: str = "",
) -> bool:
    """Deterministic required-move resolution from exact frame records."""

    if _heading_is_rhetorical_frame(heading):
        return move in {
            "problem_or_local_context",
            "design_objective",
            "transition_to_next_section",
        }
    if move in {"problem_or_local_context", "design_objective", "mechanism_overview", "transition_to_next_section"}:
        return True
    has_transformation = any(
        frame is not None and "transformation" in {slot.role for slot in frame.slots}
        for frame in (unit_frames.get(unit.argument_unit_id) for unit in section_units)
    )
    has_input = any(
        frame is not None and "input" in {slot.role for slot in frame.slots}
        for frame in (unit_frames.get(unit.argument_unit_id) for unit in section_units)
    )
    has_condition = any(
        frame is not None and "condition" in {slot.role for slot in frame.slots}
        for frame in (unit_frames.get(unit.argument_unit_id) for unit in section_units)
    )
    has_output = any(
        frame is not None and "output" in {slot.role for slot in frame.slots}
        for frame in (unit_frames.get(unit.argument_unit_id) for unit in section_units)
    )
    has_equations = any(
        bool(unit_equation_ids.get(unit.argument_unit_id)) for unit in section_units
    )
    has_configurations = any(
        bool(unit_configuration_ids.get(unit.argument_unit_id)) for unit in section_units
    )
    if move == "algorithm_or_data_flow":
        return has_transformation or has_equations
    if move == "implementation_realization":
        return has_input or has_transformation
    if move in {"formal_objects_and_notation", "equation_or_derivation"}:
        return has_equations
    if move == "configuration_and_branches":
        return has_configurations or has_condition
    if move == "inference_and_output":
        return has_output
    if move == "training_objective":
        return False
    if move == "limitations_or_mismatch":
        return any(
            _unresolved_requires_limitation_move(
                unit_unresolved_assignments.get(unit.argument_unit_id, [])
            )
            for unit in section_units
        )
    return False


def _rebuild_section(
    *,
    section: SectionArgumentGraphV1,
    section_units: list[MethodArgumentUnitV1],
    move_objects: tuple[SectionArgumentMoveV1, ...],
    unit_planning: dict[str, dict[str, str]],
    section_dependencies: dict[str, list[str]],
    section_unresolved: tuple[ObligationMoveAssignmentV1, ...],
    unit_frames: dict[str, SemanticArgumentFrameV1] | None = None,
    argument_facets: tuple[Any, ...] | list[Any] = (),
    facet_alignments: tuple[Any, ...] | list[Any] = (),
    publication_field_candidates: tuple[Any, ...] | list[Any] = (),
) -> SectionArgumentGraphV1:
    """Apply reader-facing planning and move objects to one section graph."""

    dominant_planning = {
        "heading": next(
            (
                unit_planning.get(unit.argument_unit_id, {}).get("heading", section.heading)
                for unit in section_units
                if unit_planning.get(unit.argument_unit_id, {}).get("heading")
            ),
            section.heading,
        ),
        "reader_question": " ".join(
            unit_planning.get(unit.argument_unit_id, {}).get("reader_question", "")
            for unit in section_units
        ).strip(),
        "method_point": " ".join(
            unit_planning.get(unit.argument_unit_id, {}).get("method_point", "")
            for unit in section_units
        ).strip(),
    }
    heading = (
        dominant_planning.get("heading", section.heading)
        if _GENERIC_STAGE_HEADING.match(section.heading)
        else section.heading
    )
    reader_question = (
        dominant_planning["reader_question"]
        if _GENERIC_STAGE_HEADING.match(section.heading)
        else section.reader_question
    )
    dependencies = tuple(dict.fromkeys(
        section_dependencies.get(section.section_id, [])
    ))
    paragraphs = _build_section_paragraph_plans(
        section_id=section.section_id,
        section_units=section_units,
        move_objects=move_objects,
        formula_obligation_ids=tuple(section.formula_obligation_ids),
        unit_frames=unit_frames,
        argument_facets=argument_facets,
        facet_alignments=facet_alignments,
        publication_field_candidates=publication_field_candidates,
    )
    return section.model_copy(update={
        "heading": heading,
        "reader_question": reader_question,
        "moves": move_objects,
        "dependencies": dependencies,
        "unresolved_inputs": tuple(
            f"{item.obligation_id}:{item.status}" for item in section_unresolved
        ),
        "paragraphs": paragraphs,
    })


def _restore_prior_paragraph_identities(
    *,
    prior_sections: tuple[SectionArgumentGraphV1, ...] | list[SectionArgumentGraphV1],
    rebuilt_sections: list[SectionArgumentGraphV1],
    allowed_facet_ids_by_section: dict[str, set[str]] | None = None,
    allowed_field_ids_by_section: dict[str, set[str]] | None = None,
    allowed_formula_ids_by_section: dict[str, set[str]] | None = None,
) -> list[SectionArgumentGraphV1]:
    """Carry closed paragraph identities across a semantic replan.

    Replanning may change paragraph boundaries when a frame is split into
    smaller slot clusters.  That organizational change must not erase the
    already-authorized facet/field/formula handles from the base plan: those
    handles are the harness sidecar used by Binder and are not model-written
    text.  Match by the exact argument-unit edge first, then attach to the
    first rebuilt paragraph only when the old paragraph has no unit edge.
    Slot and edge ids are intentionally not copied here; they are regenerated
    from the fresh semantic frame and are validated by the paragraph closure.
    """

    rebuilt_by_section = {
        graph.section_id: graph for graph in rebuilt_sections
    }
    for prior in prior_sections:
        current = rebuilt_by_section.get(prior.section_id)
        if current is None or not current.paragraphs:
            continue
        paragraphs = list(current.paragraphs)
        for old_paragraph in prior.paragraphs:
            old_facets = tuple(
                value for value in old_paragraph.required_facet_ids
                if str(value).strip()
            )
            old_fields = tuple(
                value for value in old_paragraph.required_field_candidate_ids
                if str(value).strip()
            )
            old_formulas = tuple(
                value for value in old_paragraph.formula_obligation_ids
                if str(value).strip()
            )
            if allowed_facet_ids_by_section is not None:
                allowed = allowed_facet_ids_by_section.get(prior.section_id, set())
                old_facets = tuple(value for value in old_facets if value in allowed)
            if allowed_field_ids_by_section is not None:
                allowed = allowed_field_ids_by_section.get(prior.section_id, set())
                old_fields = tuple(value for value in old_fields if value in allowed)
            if allowed_formula_ids_by_section is not None:
                allowed = allowed_formula_ids_by_section.get(prior.section_id, set())
                old_formulas = tuple(value for value in old_formulas if value in allowed)
            if not (old_facets or old_fields or old_formulas):
                continue
            old_units = set(old_paragraph.argument_unit_ids)
            matching_indexes = [
                index for index, paragraph in enumerate(paragraphs)
                if old_units.intersection(set(paragraph.argument_unit_ids))
            ]
            if matching_indexes:
                old_facets_set = set(old_facets)
                old_fields_set = set(old_fields)
                old_formulas_set = set(old_formulas)
                target_index = max(
                    matching_indexes,
                    key=lambda index: (
                        len(old_facets_set.intersection(
                            set(paragraphs[index].required_facet_ids)
                        )),
                        len(old_fields_set.intersection(
                            set(paragraphs[index].required_field_candidate_ids)
                        )),
                        len(old_formulas_set.intersection(
                            set(paragraphs[index].formula_obligation_ids)
                        )),
                        len(old_units.intersection(
                            set(paragraphs[index].argument_unit_ids)
                        )),
                        -index,
                    ),
                )
            else:
                target_index = 0
            target = paragraphs[target_index]
            paragraphs[target_index] = target.model_copy(update={
                "required_facet_ids": tuple(dict.fromkeys((
                    *target.required_facet_ids, *old_facets,
                ))),
                "required_field_candidate_ids": tuple(dict.fromkeys((
                    *target.required_field_candidate_ids, *old_fields,
                ))),
                "formula_obligation_ids": tuple(dict.fromkeys((
                    *target.formula_obligation_ids, *old_formulas,
                ))),
            })
        rebuilt_by_section[prior.section_id] = current.model_copy(update={
            "paragraphs": tuple(paragraphs),
        })
    return [
        rebuilt_by_section.get(graph.section_id, graph)
        for graph in rebuilt_sections
    ]


def _build_section_paragraph_plans(
    *,
    section_id: str,
    section_units: list[MethodArgumentUnitV1] | tuple[MethodArgumentUnitV1, ...],
    move_objects: tuple[SectionArgumentMoveV1, ...],
    formula_obligation_ids: tuple[str, ...] = (),
    unit_frames: dict[str, SemanticArgumentFrameV1] | None = None,
    argument_facets: tuple[Any, ...] | list[Any] = (),
    facet_alignments: tuple[Any, ...] | list[Any] = (),
    publication_field_candidates: tuple[Any, ...] | list[Any] = (),
) -> tuple[SectionParagraphPlanV1, ...]:
    """Build deterministic paragraph contracts from ordered semantic slots.

    The old graph exposed only a per-move ``paragraph_budget``.  That number
    could not tell the Writer where a condition or output belonged, so a
    long mechanism frequently became one paragraph wall.  This helper keeps
    the same move graph but emits small ordered clusters; it is purely
    organizational and does not create evidence.
    """

    # Keep the lookup local to this pure planner helper.  A previous partial
    # integration created this map only in ``_enrich_section_content_contracts``
    # but still used it here, so any section plan with a facet raised a
    # ``NameError`` before the Writer received a paragraph contract.
    field_candidates_by_facet: dict[str, tuple[Any, ...]] = {}
    for candidate in publication_field_candidates or ():
        facet_id = str(getattr(candidate, "facet_id", "") or "").strip()
        if not facet_id:
            continue
        field_candidates_by_facet[facet_id] = (
            *field_candidates_by_facet.get(facet_id, ()),
            candidate,
        )

    plans: list[SectionParagraphPlanV1] = []
    paragraph_index = 0
    for unit in section_units:
        # During trace-backed replanning, frames are derived from the current
        # evidence but are attached to rebuilt units only after sections have
        # been rebuilt.  Use that authoritative map here so paragraph
        # contracts retain their semantic slots, edges, and formula consumers
        # instead of collapsing every unit to an unbound overview paragraph.
        frame = (
            unit_frames.get(unit.argument_unit_id)
            if unit_frames is not None
            else unit.semantic_frame
        )
        ordered_slots = list(
            frame.ordered_slot_ids if frame is not None else ()
        )
        slot_by_id = {
            slot.slot_id: slot
            for slot in (frame.slots if frame is not None else ())
        }
        if not ordered_slots:
            ordered_chunks = [()]
        elif len(ordered_slots) <= 8:
            ordered_chunks = [tuple(ordered_slots)]
        else:
            # Keep a bounded semantic cluster together.  Three-slot chunks
            # over-split dense implementation units (e.g. one retrieval
            # stage with dozens of code facts) into a Writer-sized wall of
            # paragraphs.  Eight slots preserves the order and condition /
            # output witnesses while keeping a section renderable.
            first = tuple(ordered_slots[:8])
            rest = ordered_slots[8:]
            ordered_chunks = [first]
            ordered_chunks.extend(tuple(rest[index:index + 8]) for index in range(0, len(rest), 8))
        unit_moves = [
            move for move in move_objects
            if unit.argument_unit_id in (move.argument_unit_ids or ())
            and move.move != "transition_to_next_section"
        ]
        for chunk_index, chunk in enumerate(ordered_chunks, start=1):
            paragraph_index += 1
            chunk_roles = {slot_by_id[item].role for item in chunk if item in slot_by_id}
            if chunk_index == 1 and "input" in chunk_roles:
                role = "construction"
            elif "output" in chunk_roles:
                role = "output"
            elif any(
                move.move in {"interface", "inference_and_output"}
                for move in unit_moves
            ):
                role = "interface"
            else:
                role = "step_sequence"
            if unit.equation_ids and chunk_index == len(ordered_chunks):
                role = "formula"
            move_names = {move.move for move in unit_moves}
            if chunk_index == 1 and not chunk_roles:
                role = "overview"
            required_edges = tuple(
                edge.relation_id
                for edge in (frame.edges if frame is not None else ())
                if set(edge.source_slot_ids).intersection(chunk)
                or set(edge.target_slot_ids).intersection(chunk)
            )
            # Formula obligations are canonical IDs.  Bind an equation-scoped
            # obligation only to a unit that owns that exact equation; any
            # section-scoped/deferred obligation is routed once below.  This
            # prevents every equation-bearing unit from becoming a consumer of
            # the whole section formula set.
            unit_formula_ids: tuple[str, ...] = ()
            if chunk_index == len(ordered_chunks) and unit.equation_ids:
                unit_equation_ids = {str(value).strip() for value in unit.equation_ids}
                unit_formula_ids = tuple(
                    obligation_id
                    for obligation_id in formula_obligation_ids
                    if (
                        str(obligation_id).strip().removeprefix("formula:")
                        in unit_equation_ids
                        or str(obligation_id).strip().removeprefix("formula:equation:")
                        in unit_equation_ids
                    )
                )
            plans.append(SectionParagraphPlanV1(
                paragraph_id=f"paragraph:{section_id}:{paragraph_index}",
                paragraph_role=role,  # type: ignore[arg-type]
                argument_unit_ids=(unit.argument_unit_id,),
                ordered_semantic_slot_ids=tuple(chunk),
                required_edge_ids=required_edges,
                formula_obligation_ids=unit_formula_ids,
                expected_sentence_range=(1, max(2, min(5, len(chunk) + 1))),
                transition_from=(
                    plans[-1].paragraph_id if plans else ""
                ),
                transition_to="",
            ))
    # Bind required author facets to the smallest paragraph that carries the
    # corresponding evidence/semantic role.  This is deliberately computed
    # from exact field bindings and frame slots; a facet id in Writer output
    # is not itself evidence of coverage.
    facet_by_id = {
        str(facet.facet_id): facet
        for facet in (argument_facets or ())
        if str(getattr(facet, "facet_id", "") or "").strip()
    }
    alignment_by_facet_id = {
        str(alignment.facet_id): alignment
        for alignment in (facet_alignments or ())
        if str(getattr(alignment, "facet_id", "") or "").strip()
    }
    for unit in section_units:
        paragraph_indexes = [
            index for index, paragraph in enumerate(plans)
            if unit.argument_unit_id in (paragraph.argument_unit_ids or ())
        ]
        if not paragraph_indexes:
            continue
        brief_ids = {
            str(value).strip()
            for value in (unit.brief_order or unit.brief_ids or ())
            if str(value).strip()
        }
        unit_facets = []
        for facet in facet_by_id.values():
            if (
                str(getattr(facet, "brief_id", "") or "").strip()
                and str(getattr(facet, "brief_id", "") or "").strip() not in brief_ids
            ):
                continue
            candidates = field_candidates_by_facet.get(str(facet.facet_id), ())
            if candidates:
                if any(str(getattr(item, "render_policy", "")) == "required" for item in candidates):
                    unit_facets.append(facet)
                continue
            # Compatibility for frozen callers that pass only aligned facets:
            # an aggregate ``facet.required`` flag is not enough to create a
            # hard target once an alignment is available.
            alignment = alignment_by_facet_id.get(str(facet.facet_id))
            if alignment is None:
                continue
            if (
                str(getattr(alignment, "status", "")) == "entailed"
                and bool(getattr(alignment, "exact_excerpts", ()))
                and bool(getattr(alignment, "bound_claim_ids", ()))
            ):
                unit_facets.append(facet)
        frame = (
            unit_frames.get(unit.argument_unit_id)
            if unit_frames is not None
            else unit.semantic_frame
        )
        slot_by_id = {
            slot.slot_id: slot for slot in (frame.slots if frame is not None else ())
        }
        for facet in unit_facets:
            facet_id = str(facet.facet_id)
            if any(facet_id in plans[index].required_facet_ids for index in paragraph_indexes):
                continue
            alignment = alignment_by_facet_id.get(facet_id)
            bound_fact_ids = {
                str(value)
                for value in (
                    getattr(alignment, "bound_fact_ids", ()) or ()
                )
                if str(value).strip()
            }
            bound_equation_ids = {
                str(value)
                for value in (
                    getattr(alignment, "bound_equation_ids", ()) or ()
                )
                if str(value).strip()
            }
            for binding in (getattr(alignment, "field_bindings", ()) or ()):
                bound_fact_ids.update(
                    str(value) for value in (getattr(binding, "bound_fact_ids", ()) or ())
                    if str(value).strip()
                )
                bound_equation_ids.update(
                    str(value) for value in (getattr(binding, "bound_equation_ids", ()) or ())
                    if str(value).strip()
                )
            for excerpt in (getattr(alignment, "exact_excerpts", ()) or ()):
                bound_fact_ids.update(
                    str(value) for value in (getattr(excerpt, "fact_ids", ()) or ())
                    if str(value).strip()
                )
                bound_equation_ids.update(
                    str(value) for value in (getattr(excerpt, "equation_ids", ()) or ())
                    if str(value).strip()
                )
            fields = {
                str(key).casefold()
                for key in (getattr(facet, "semantic_fields", {}) or {})
            }
            kind = str(getattr(facet, "facet_kind", "") or "").casefold()
            scores: dict[int, int] = {}
            for index in paragraph_indexes:
                paragraph = plans[index]
                slot_ids = set(paragraph.ordered_semantic_slot_ids or ())
                slots = [slot_by_id[slot_id] for slot_id in slot_ids if slot_id in slot_by_id]
                slot_facts = {
                    str(fact_id)
                    for slot in slots
                    for fact_id in (slot.fact_ids or ())
                }
                slot_roles = {str(slot.role).casefold() for slot in slots}
                role = str(paragraph.paragraph_role).casefold()
                score = 0
                if bound_fact_ids.intersection(slot_facts):
                    score += 100
                if bound_equation_ids.intersection(
                    str(value) for value in unit.equation_ids
                ) and role == "formula":
                    score += 120
                if kind == "formula" or "formula_goal" in fields:
                    score += 80 if role == "formula" else 0
                if fields.intersection({"conditions", "condition"}):
                    score += 35 if "condition" in slot_roles else 0
                if fields.intersection({"outputs", "output", "effects", "effect"}):
                    score += 35 if "output" in slot_roles or role == "output" else 0
                if fields.intersection({"inputs", "input"}):
                    score += 25 if "input" in slot_roles else 0
                if fields.intersection({"interface"}):
                    score += 25 if role == "interface" else 0
                if fields.intersection({"operation", "mechanism", "subject"}):
                    score += 10 if slot_roles.intersection({"transformation", "input"}) else 0
                scores[index] = score
            max_score = max(scores.values(), default=0)
            best = [index for index in paragraph_indexes if scores.get(index, 0) == max_score]
            # Author-only facets are kept on the unit's overview paragraph;
            # evidence-backed facets use the earliest tied paragraph to
            # preserve ordered procedure narration.
            target_index = best[0] if best else paragraph_indexes[0]
            if max_score == 0:
                overview = [
                    index for index in paragraph_indexes
                    if plans[index].paragraph_role == "overview"
                ]
                target_index = overview[0] if overview else paragraph_indexes[0]
            target = plans[target_index]
            required_candidates = tuple(
                str(getattr(item, "candidate_id", "") or "")
                for item in field_candidates_by_facet.get(facet_id, ())
                if str(getattr(item, "render_policy", "")) == "required"
                and str(getattr(item, "candidate_id", "") or "").strip()
            )
            facet_formula_ids = (
                (f"formula:facet:{facet_id}",)
                if str(getattr(facet, "formula_expectation", "none") or "none") == "required"
                else ()
            )
            plans[target_index] = target.model_copy(update={
                "required_facet_ids": (
                    target.required_facet_ids
                    if required_candidates
                    else tuple(dict.fromkeys([
                        *target.required_facet_ids,
                        facet_id,
                    ]))
                ),
                "required_field_candidate_ids": tuple(dict.fromkeys([
                    *target.required_field_candidate_ids,
                    *required_candidates,
                ])),
                "formula_obligation_ids": tuple(dict.fromkeys([
                    *target.formula_obligation_ids,
                    *facet_formula_ids,
                ])),
            })
    # A formula consumer is explicit and unique.  First preserve any
    # facet-scoped formula obligations that were placed with their field
    # candidate; then attach each remaining section/equation obligation to
    # one final mechanism paragraph.  The previous implementation copied the
    # complete section obligation set to every equation-bearing unit, which
    # made one obligation appear to have several consumers and prevented
    # package consumption from closing.
    assigned_formula_ids = {
        str(obligation_id)
        for paragraph in plans
        for obligation_id in paragraph.formula_obligation_ids
        if str(obligation_id).strip()
    }
    remaining_formula_ids = [
        str(obligation_id).strip()
        for obligation_id in formula_obligation_ids
        if str(obligation_id).strip() and str(obligation_id).strip() not in assigned_formula_ids
    ]
    if remaining_formula_ids and plans:
        eligible_indexes = [
            index for index, paragraph in enumerate(plans)
            if paragraph.argument_unit_ids
            and any(
                unit.argument_unit_id in paragraph.argument_unit_ids
                and (
                    bool(unit.equation_ids)
                    or any(move.move == "equation_or_derivation" and move.required for move in unit_moves)
                )
                for unit in section_units
                for unit_moves in ([move for move in move_objects if unit.argument_unit_id in (move.argument_unit_ids or ())],)
            )
        ]
        target_index = eligible_indexes[-1] if eligible_indexes else len(plans) - 1
        target = plans[target_index]
        plans[target_index] = target.model_copy(update={
            "paragraph_role": "formula",
            "formula_obligation_ids": tuple(dict.fromkeys([
                *target.formula_obligation_ids,
                *remaining_formula_ids,
            ])),
        })
    # Split low-level slots into support evidence and reader-facing
    # publication slots.  A semantic slot is publication-required only when
    # it carries a meaningful operation/input/output/condition and is not an
    # implementation-only residue.  The split is deterministic and keeps the
    # old ordered list for compatibility.
    for index, plan in enumerate(plans):
        frame = None
        for unit in section_units:
            if unit.argument_unit_id in plan.argument_unit_ids:
                frame = unit_frames.get(unit.argument_unit_id) if unit_frames is not None else unit.semantic_frame
                break
        slot_by_id_local = {slot.slot_id: slot for slot in (frame.slots if frame is not None else ())}
        role_slots: dict[str, list[str]] = {role: [] for role in ("input", "transformation", "condition", "output")}
        for slot_id in plan.ordered_semantic_slot_ids:
            role = str(getattr(slot_by_id_local.get(slot_id), "role", ""))
            if role in role_slots and slot_by_id_local.get(slot_id) is not None:
                role_slots[role].append(slot_id)
        # Publication obligations are a compact reader-facing spine: retain
        # the first input/condition/output and the endpoints of a multi-step
        # transformation chain.  All intermediate implementation atoms stay
        # in support_slot_ids and remain available to the Writer without
        # making every low-level slot a hard sentence obligation.
        required_slot_list: list[str] = []
        for role in ("input", "transformation", "condition", "output"):
            values = role_slots[role]
            if not values:
                continue
            selected = values if role == "transformation" and len(values) <= 2 else (
                values[:1] + (values[-1:] if role == "transformation" and len(values) > 1 else [])
            )
            # ``SemanticFlowSlotV1`` already requires an exact fact/claim
            # binding.  Keep this check explicit at the projection boundary so
            # low-level or partially reconstructed frames cannot become hard
            # publication obligations merely because they have a role label.
            required_slot_list.extend(
                slot_id for slot_id in selected
                if slot_by_id_local[slot_id].fact_ids or slot_by_id_local[slot_id].claim_ids
            )
        required_slots = tuple(dict.fromkeys(required_slot_list))
        support_slots = tuple(plan.ordered_semantic_slot_ids)
        plans[index] = plan.model_copy(update={
            "support_slot_ids": support_slots,
            "required_publication_slot_ids": required_slots,
        })

    # Build one paragraph-local witness contract from the exact same targets
    # used by the transaction assessor.  Exact source excerpts are anchors,
    # not prose; the Writer sees them as allowed semantic evidence and must
    # still rewrite them in reader-facing language.
    final_plans: list[SectionParagraphPlanV1] = []
    for plan in plans:
        targets: list[ParagraphWitnessTargetV1] = []
        for facet_id in plan.required_facet_ids:
            facet = facet_by_id.get(facet_id)
            candidates = field_candidates_by_facet.get(facet_id, ())
            alignment = alignment_by_facet_id.get(facet_id)
            alignment_projection = _method_unit_alignment_projection(
                facet_id,
                alignment_by_facet_id,
            )
            surface_mode, render_policy, authority_lane = _witness_surface_contract(
                alignment=alignment,
                projection=alignment_projection,
            )
            excerpts = tuple(dict.fromkeys(
                str(value)
                for candidate in candidates
                for value in (getattr(candidate, "exact_excerpts", ()) or ())
                if str(value).strip()
            ))
            if not excerpts:
                excerpts = tuple(dict.fromkeys(
                    str(getattr(item, "exact_excerpt", "") or "")
                    for item in (getattr(alignment, "exact_excerpts", ()) or ())
                    if str(getattr(item, "exact_excerpt", "") or "").strip()
                ))
            targets.append(ParagraphWitnessTargetV1(
                target_id=facet_id,
                target_kind="facet",
                semantic_atom=_reader_facing_facet_semantic_atom(
                    facet,
                    fallback=facet_id,
                ) if facet is not None else facet_id,
                paper_role=str(getattr(facet, "facet_kind", "mechanism") or "mechanism") if facet is not None else "mechanism",
                allowed_anchor_ids=tuple(
                    span_id
                    for candidate in candidates
                    for span_id in (getattr(candidate, "bound_span_ids", ()) or ())
                ),
                allowed_exact_excerpts=excerpts,
                authority_lane=authority_lane,
                surface_mode=surface_mode,
                render_policy=render_policy,
            ))
        for candidate_id in plan.required_field_candidate_ids:
            candidate = next(
                (item for values in field_candidates_by_facet.values() for item in values
                 if str(getattr(item, "candidate_id", "")) == candidate_id),
                None,
            )
            if candidate is None:
                continue
            targets.append(ParagraphWitnessTargetV1(
                target_id=candidate_id,
                target_kind="field",
                semantic_atom=str(getattr(candidate, "semantic_atom", "") or ""),
                paper_role=str(getattr(candidate, "field_name", "") or "mechanism"),
                required_polarity=str(getattr(candidate, "polarity", "unknown") or "unknown"),
                required_conditions=tuple(getattr(candidate, "conditions", ()) or ()),
                allowed_anchor_ids=tuple(getattr(candidate, "bound_span_ids", ()) or ()),
                allowed_exact_excerpts=tuple(getattr(candidate, "exact_excerpts", ()) or ()),
                authority_lane=_witness_surface_contract(
                    candidate=candidate,
                )[2],
                surface_mode=_witness_surface_contract(
                    candidate=candidate,
                )[0],
                render_policy=_witness_surface_contract(
                    candidate=candidate,
                )[1],
            ))
        for slot_id in plan.required_publication_slot_ids:
            slot = next(
                (slot for unit in section_units
                 for slot in ((unit_frames.get(unit.argument_unit_id) if unit_frames is not None else unit.semantic_frame).slots
                              if (unit_frames.get(unit.argument_unit_id) if unit_frames is not None else unit.semantic_frame) is not None else ())
                 if slot.slot_id == slot_id),
                None,
            )
            if slot is None:
                continue
            targets.append(ParagraphWitnessTargetV1(
                target_id=slot_id,
                target_kind="slot",
                semantic_atom=_reader_facing_slot_semantic_atom(slot) or slot_id,
                paper_role=str(slot.role),
                required_conditions=tuple(slot.conditions),
                allowed_anchor_ids=tuple((*slot.fact_ids, *slot.claim_ids)),
                allowed_exact_excerpts=(),
                authority_lane=(slot.authority_lanes[0] if slot.authority_lanes else "executable_hard"),
                surface_mode="repository_statement",
                render_policy="required",
            ))
        for edge_id in plan.required_edge_ids:
            edge = next(
                (edge for unit in section_units
                 for frame in ((unit_frames.get(unit.argument_unit_id) if unit_frames is not None else unit.semantic_frame),)
                 if frame is not None for edge in frame.edges if edge.relation_id == edge_id),
                None,
            )
            if edge is None:
                continue
            targets.append(ParagraphWitnessTargetV1(
                target_id=edge_id,
                target_kind="edge",
                semantic_atom=f"{edge.source_symbol} {edge.relation_type} {edge.target_symbol}",
                paper_role="data_flow",
                required_conditions=tuple(edge.conditions),
                allowed_anchor_ids=tuple(edge.direct_span_ids),
                authority_lane="executable_hard",
                surface_mode="repository_statement",
                render_policy="required",
            ))
        for obligation_id in plan.formula_obligation_ids:
            targets.append(ParagraphWitnessTargetV1(
                target_id=obligation_id,
                target_kind="formula",
                semantic_atom="formal expression",
                paper_role="formula",
                allowed_anchor_ids=(obligation_id,),
                authority_lane="formal_derivation",
                surface_mode="repository_statement",
                render_policy="required",
            ))
        final_plans.append(plan.model_copy(update={
            "witness_contract": ParagraphWitnessContractV1(
                paragraph_id=plan.paragraph_id,
                rhetorical_goal=str(plan.paragraph_role),
                targets=tuple(targets),
            ) if targets else None,
        }))
    return tuple(final_plans)


def _moves_from_frame(
    frame: SemanticArgumentFrameV1 | None,
    equation_ids: tuple[str, ...],
    configuration_ids: tuple[str, ...],
    heading: str = "",
) -> tuple[str, ...]:
    """Move template from the typed semantic frame roles (not claim regexes)."""

    if _heading_is_rhetorical_frame(heading):
        return (
            "problem_or_local_context",
            "design_objective",
            "transition_to_next_section",
        )
    if frame is None:
        return ()
    slot_roles = {item.role for item in frame.slots}
    moves: list[str] = [
        "problem_or_local_context", "design_objective", "mechanism_overview",
    ]
    if "transformation" in slot_roles or equation_ids:
        moves.append("algorithm_or_data_flow")
    if "input" in slot_roles or "transformation" in slot_roles:
        moves.append("implementation_realization")
    if equation_ids:
        moves.extend(("formal_objects_and_notation", "equation_or_derivation"))
    if configuration_ids or "condition" in slot_roles:
        moves.append("configuration_and_branches")
    if "output" in slot_roles:
        moves.append("inference_and_output")
    moves.append("transition_to_next_section")
    return tuple(dict.fromkeys(moves))


def place_obligation_assignments(
    *,
    matrix_rows: list[Any],
    units: tuple[MethodArgumentUnitV1, ...] | list[MethodArgumentUnitV1],
    section_by_unit: dict[str, str],
    unit_frames: dict[str, SemanticArgumentFrameV1],
    unit_fact_ids: dict[str, set[str]],
    unit_claim_ids: dict[str, set[str]],
    unit_source_obligation_ids: dict[str, set[str]],
    unit_roles: dict[str, tuple[str, ...]],
    unit_equation_ids: dict[str, tuple[str, ...]],
    unit_configuration_ids: dict[str, tuple[str, ...]],
    coverage_by_obligation: dict[str, tuple[str, ...]],
    agenda_by_id: dict[str, Any],
    proposal_caller: Any | None = None,
) -> tuple[tuple[ObligationMoveAssignmentV1, ...], list[dict[str, Any]]]:
    """Place every critical/high completeness row exactly once.

    Deterministic order: (1) exact claim/equation/configuration IDs bound to a
    unit; (2) exact agenda source bindings (candidate symbols, research
    queries, role); (3) exact semantic-frame fact bindings from the coverage
    artifact.  Zero or multiple closed targets invoke one bounded Architect
    owner proposal; a second failure keeps the row fully typed as ``unplaced``
    with its unresolved reason and fails the plan gate.
    """

    assignments: list[ObligationMoveAssignmentV1] = []
    placement_trace: list[dict[str, Any]] = []
    rows = [
        item for item in matrix_rows
        if item.importance in {"critical", "high"}
    ]
    for item in sorted(rows, key=lambda row: str(row.obligation_id)):
        obligation_id = str(item.obligation_id)
        agenda_row = agenda_by_id.get(obligation_id) or agenda_by_id.get(
            str(getattr(item, "source_obligation_id", "") or "")
        )
        targets: list[str] = []
        target_reason = ""
        # (1) exact claim/equation/configuration IDs bound to a unit.
        claim_candidates = [
            unit.argument_unit_id for unit in units
            if set(item.claim_ids) and set(item.claim_ids) <= unit_claim_ids.get(unit.argument_unit_id, set())
        ]
        if len(claim_candidates) == 1:
            targets = claim_candidates
            target_reason = "exact_claim_ids"
        elif len(claim_candidates) > 1:
            targets = claim_candidates
            target_reason = "claim_ids_ambiguous"
        if not targets:
            id_candidates = [
                unit.argument_unit_id for unit in units
                if (
                    set(item.claim_ids) & unit_claim_ids.get(unit.argument_unit_id, set())
                ) or (
                    set(item.equation_ids) & set(unit_equation_ids.get(unit.argument_unit_id, ()))
                ) or (
                    set(item.configuration_ids) & set(unit_configuration_ids.get(unit.argument_unit_id, ()))
                )
            ]
            if len(id_candidates) == 1:
                targets = id_candidates
                target_reason = "exact_bound_ids"
            elif len(id_candidates) > 1:
                targets = id_candidates
                target_reason = "bound_ids_ambiguous"
        # (2) exact agenda/base-plan bindings.  ``source_obligation_id`` is
        # carried by authorized claims into the frozen base-plan units; it is
        # stronger than vocabulary matching and must be tried first.
        if (not targets or target_reason.endswith("_ambiguous")) and agenda_row is not None:
            exact_source_ids = {
                str(agenda_row.obligation_id),
                str(getattr(agenda_row, "source_obligation_id", "") or ""),
            } - {""}
            source_candidates = [
                unit.argument_unit_id for unit in units
                if exact_source_ids.intersection(
                    unit_source_obligation_ids.get(unit.argument_unit_id, set())
                )
            ]
            if len(source_candidates) == 1:
                targets = source_candidates
                target_reason = "agenda_source_obligation_id"
            elif len(source_candidates) > 1:
                targets = source_candidates
                target_reason = "agenda_source_obligation_id_ambiguous"
        if (not targets or target_reason.endswith("_ambiguous")) and agenda_row is not None:
            agenda_role = str(getattr(agenda_row, "role", "") or "").strip().lower()
            role_candidates = [
                unit.argument_unit_id for unit in units
                if agenda_role
                and agenda_role in {
                    str(role).strip().lower()
                    for role in unit_roles.get(unit.argument_unit_id, ())
                    if str(role).strip()
                }
            ]
            if len(role_candidates) == 1:
                targets = role_candidates
                target_reason = "agenda_role"
            elif len(role_candidates) > 1:
                targets = role_candidates
                target_reason = "agenda_role_ambiguous"
        if (not targets or target_reason.endswith("_ambiguous")) and agenda_row is not None:
            # Candidate symbols and research queries are compared as complete
            # normalized terms.  Individual word overlap is not an exact
            # placement binding and must not choose a unit.
            agenda_terms = {
                exact_term
                for term in (
                    *getattr(agenda_row, "candidate_symbols", ()),
                    *getattr(agenda_row, "research_queries", ()),
                )
                for exact_term in _exact_symbol_terms(term)
            }
            agenda_candidates = [
                unit.argument_unit_id for unit in units
                if agenda_terms.intersection(
                    _frame_term_set(unit_frames.get(unit.argument_unit_id))
                )
            ]
            if len(agenda_candidates) == 1:
                targets = agenda_candidates
                target_reason = "agenda_symbols"
            elif len(agenda_candidates) > 1:
                targets = agenda_candidates
                target_reason = "agenda_symbols_ambiguous"
        # (3) exact semantic-frame fact bindings from the coverage artifact.
        if not targets or target_reason.endswith("_ambiguous"):
            coverage_facts = tuple(coverage_by_obligation.get(obligation_id, ()))
            coverage_candidates = [
                unit.argument_unit_id for unit in units
                if coverage_facts
                and set(coverage_facts) <= unit_fact_ids.get(unit.argument_unit_id, set())
            ]
            if len(coverage_candidates) == 1:
                targets = coverage_candidates
                target_reason = "coverage_fact_ids"
            elif len(coverage_candidates) > 1:
                targets = coverage_candidates
                target_reason = "coverage_fact_ids_ambiguous"

        placement_state = "unplaced"
        section_id = ""
        unit_id = ""
        required_move = ""
        anchor_ids: tuple[str, ...] = ()
        unresolved_reason = str(getattr(item, "reason", "") or "")
        # The assignment keeps the row's ORIGINAL authority lane intact
        # (contract §0.3); the request routing lane is derived separately.
        original_lane = str(item.authority_lane) or "executable_hard"
        if len(targets) == 1:
            unit_id = targets[0]
            placement_state = "assigned"
            required_move, routing_lane = _derive_move_and_lane(item)
            section_id = section_by_unit.get(unit_id, unit_id)
            anchor_ids = tuple(dict.fromkeys([
                *item.claim_ids,
                *item.equation_ids,
                *item.configuration_ids,
                *coverage_by_obligation.get(obligation_id, ()),
            ]))
            if routing_lane in {
                "author_attested", "empirical_artifact", "external_literature",
            }:
                placement_state = "external_pending"
        elif len(targets) > 1:
            resolved = _bounded_architect_proposal(
                obligation_id=obligation_id,
                targets=targets,
                sections=[section_by_unit.get(target, target) for target in targets],
                moves=[_derive_move_and_lane(item)[0]],
                proposal_caller=proposal_caller,
            )
            if resolved:
                unit_id = resolved
                placement_state = "assigned"
                required_move, routing_lane = _derive_move_and_lane(item)
                section_id = section_by_unit.get(unit_id, unit_id)
                anchor_ids = tuple(dict.fromkeys([
                    *item.claim_ids,
                    *item.equation_ids,
                    *item.configuration_ids,
                    *coverage_by_obligation.get(obligation_id, ()),
                ]))
                if routing_lane in {
                    "author_attested", "empirical_artifact", "external_literature",
                }:
                    placement_state = "external_pending"
            else:
                unresolved_reason = (
                    unresolved_reason
                    or f"no unique closed target for obligation {obligation_id}"
                )
        else:
            # No closed target.  The Architect is never asked to choose from
            # an empty set.  When the row's own authority contract names a
            # genuinely external owner (author confirmation, external
            # evidence/literature, formalization), the row routes there as an
            # explicit external-pending assignment with its original
            # status/lane/next-action intact.  A repository-search
            # (executable_hard) row without candidates is NOT routed: the
            # widened scope requires an authorized search scope and non-empty
            # exact candidates, so it stays fully typed ``unplaced`` and fails
            # the gate.  A supported/partially-supported row with no closed
            # target is likewise a genuine plan defect.
            if str(item.status) in _GAP_STATUSES:
                required_move, routing_lane = _derive_move_and_lane(item)
            else:
                required_move, routing_lane = "", str(item.authority_lane) or "executable_hard"
            # A no-candidate row routes to its scoped owner when the authority
            # contract names one: author confirmation, external
            # evidence/literature, formalization, or an unverified row whose
            # own next action authorizes repository research.  Such a row is
            # an explicit external-pending assignment, never an empty-set
            # Architect choice.  A supported/partially-supported row with no
            # closed target, or an executable_hard row whose contract does NOT
            # authorize research, is a genuine plan defect and stays fully
            # typed ``unplaced``.
            contract_routes = {
                "author_attested", "external_literature", "formal_derivation",
            }
            if (
                str(item.status) in _GAP_STATUSES
                and (
                    routing_lane in contract_routes
                    or (
                        routing_lane == "executable_hard"
                        and str(item.status) == "unverified_by_repository"
                        and "research" in str(item.next_action).lower()
                    )
                )
            ):
                placement_state = "external_pending"
                unresolved_reason = (
                    unresolved_reason
                    or f"no closed target; routed to {routing_lane} owner per authority contract"
                )
            else:
                required_move = ""
                unresolved_reason = (
                    unresolved_reason
                    or f"no closed target found for obligation {obligation_id}"
                )
        if placement_state == "unplaced" and not unresolved_reason:
            unresolved_reason = f"obligation {obligation_id} could not be placed"
        next_action = str(getattr(item, "next_action", "") or "")
        assignment = ObligationMoveAssignmentV1(
            obligation_id=obligation_id,
            importance=str(item.importance),
            status=str(item.status),
            authority_lane=original_lane,
            source_artifact_ids=tuple(item.source_artifact_ids),
            next_action=next_action,
            unresolved_reason=unresolved_reason,
            section_id=section_id,
            argument_unit_id=unit_id,
            required_move=required_move,
            supporting_anchor_ids=anchor_ids,
            placement_state=placement_state,
        )
        assignments.append(assignment)
        placement_trace.append({
            "obligation_id": obligation_id,
            "target_reason": target_reason,
            "candidate_targets": targets,
            "placement_state": placement_state,
            "section_id": section_id,
            "argument_unit_id": unit_id,
            "required_move": required_move,
            "authority_lane": original_lane,
        })
    return tuple(assignments), placement_trace


def _exact_symbol_terms(term: Any) -> set[str]:
    """Return only recognizable complete identifier terms.

    Natural-language word overlap is not a placement binding.  Qualified
    Python symbols, snake_case identifiers, and CamelCase identifiers are;
    the path-qualified ``module.py::Type.member`` representation additionally
    exposes the exact ``Type.member`` suffix used by executable facts.
    """

    raw = str(term).strip().replace("::", ".")
    if not raw:
        return set()
    terms: set[str] = set()
    for match in re.finditer(
        r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+",
        raw,
    ):
        symbol = match.group(0).strip(".")
        terms.add(symbol.lower())
        if ".py." in symbol.lower():
            terms.add(symbol[symbol.lower().index(".py.") + 4 :].lower())
    for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", raw):
        symbol = match.group(0)
        if "_" in symbol or (any(ch.isupper() for ch in symbol[1:])):
            terms.add(symbol.lower())
    return {item for item in terms if item}


def _frame_term_set(frame: SemanticArgumentFrameV1 | None) -> set[str]:
    if frame is None:
        return set()
    terms: set[str] = set()
    for slot in frame.slots:
        terms.update(_exact_symbol_terms(slot.subject))
        terms.add(slot.subject.strip().lower())
        for operand in slot.operands:
            terms.update(_exact_symbol_terms(operand))
            terms.add(operand.strip().lower())
    return {item for item in terms if item}


def _content_move_from_role(role: str) -> str:
    """Owning content move for a completeness row that is not a mismatch gap."""

    lowered = str(role or "").lower()
    if any(token in lowered for token in ("equation", "formula", "derivation", "notation")):
        return "equation_or_derivation"
    if any(token in lowered for token in ("config", "parameter", "branch")):
        return "configuration_and_branches"
    if any(token in lowered for token in ("output", "return", "inference", "prediction")):
        return "inference_and_output"
    if "training" in lowered:
        return "training_objective"
    return "algorithm_or_data_flow"


def _derive_move_and_lane(item: Any) -> tuple[str, str]:
    """Derive the required move and authority lane from the exact row.

    Mismatch and unverified-search rows resolve to ``limitations_or_mismatch``.
    Partial support, author confirmation, and external evidence hang on the
    owning content move so Writer can caveat the mechanism instead of opening
    a generic executable_hard limitations callback.  Formalization stays on
    ``equation_or_derivation``.
    """

    status = str(item.status)
    role = str(getattr(item, "role", "") or "")
    next_action = str(getattr(item, "next_action", "") or "").lower()
    if status == "formalization_required":
        return "equation_or_derivation", "formal_derivation"
    if status == "explicit_code_gap":
        if "widen" in next_action or "search" in next_action:
            return "limitations_or_mismatch", "executable_hard"
        return "limitations_or_mismatch", "author_attested"
    if status in {"paper_code_mismatch", "out_of_scope"}:
        return "limitations_or_mismatch", str(item.authority_lane) or "executable_hard"
    if status == "unverified_by_repository":
        lane = str(item.authority_lane) or "executable_hard"
        if "widen" in next_action or "search" in next_action or "research" in next_action:
            return "limitations_or_mismatch", "executable_hard"
        return "limitations_or_mismatch", lane
    if status == "partially_supported_by_repository":
        return _content_move_from_role(role), str(item.authority_lane) or "executable_hard"
    if status == "author_confirmation_required":
        return _content_move_from_role(role), "author_attested"
    if status == "external_evidence_required":
        return _content_move_from_role(role), "external_literature"
    if status in _GAP_STATUSES:
        return "limitations_or_mismatch", str(item.authority_lane) or "executable_hard"
    return _content_move_from_role(role), str(item.authority_lane) or "executable_hard"


_GAP_STATUSES = frozenset({
    "partially_supported_by_repository",
    "unverified_by_repository",
    "explicit_code_gap",
    "author_confirmation_required",
    "external_evidence_required",
    "formalization_required",
    "paper_code_mismatch",
    "out_of_scope",
})





def _bounded_architect_proposal(
    *,
    obligation_id: str,
    targets: list[str],
    sections: list[str],
    moves: list[str],
    proposal_caller: Any | None,
) -> str:
    """One bounded closed-ID Architect owner proposal; fail closed on failure.

    The proposal may select only an existing unit/section/move ID.  On a
    schema/binding failure the owner is asked once more; a second failure
    returns ``""`` so the row stays typed unplaced and fails the plan gate.
    """

    if proposal_caller is None:
        return ""
    raw = proposal_caller(obligation_id, targets, sections, moves)
    if not isinstance(raw, dict):
        return ""
    choice = str(raw.get("argument_unit_id") or raw.get("unit_id") or "").strip()
    if choice in targets:
        return choice
    raw = proposal_caller(obligation_id, targets, sections, moves)
    if not isinstance(raw, dict):
        return ""
    choice = str(raw.get("argument_unit_id") or raw.get("unit_id") or "").strip()
    if choice in targets:
        return choice
    return ""


def resolve_move_authority_proofs(
    *,
    sections: tuple[SectionArgumentGraphV1, ...],
    units: tuple[MethodArgumentUnitV1, ...] | list[MethodArgumentUnitV1],
    unit_frames: dict[str, SemanticArgumentFrameV1],
    unit_equation_ids: dict[str, tuple[str, ...]],
    unit_configuration_ids: dict[str, tuple[str, ...]],
    assignments: tuple[ObligationMoveAssignmentV1, ...] | list[ObligationMoveAssignmentV1],
) -> tuple[MoveAuthorityProofV1, ...]:
    """Resolve the move-specific authority proof for every section/move.

    Anchors come only from the exact typed frame records and assignments; an
    unrelated same-unit claim cannot anchor a semantically different move.
    ``limitations_or_mismatch`` always reports empty positive anchors and its
    lane/route come from the exact unresolved assignment.
    """

    proofs: list[MoveAuthorityProofV1] = []
    unit_by_id = {unit.argument_unit_id: unit for unit in units}
    for section in sections:
        section_units = [
            unit_by_id[unit_id] for unit_id in section.argument_unit_ids
            if unit_id in unit_by_id
        ]
        section_assignments = [
            item for item in assignments
            if item.section_id == section.section_id
            and item.placement_state in {"assigned", "external_pending"}
        ]
        for move in section.moves:
            move_units = [
                unit for unit in section_units
                if move.move in _moves_from_frame(
                    unit_frames.get(unit.argument_unit_id),
                    unit_equation_ids.get(unit.argument_unit_id, ()),
                    unit_configuration_ids.get(unit.argument_unit_id, ()),
                    heading=section.heading,
                )
            ]
            move_unit_ids = tuple(unit.argument_unit_id for unit in move_units)
            if not move_unit_ids:
                move_unit_ids = section.argument_unit_ids
                move_units = section_units
            frame = unit_frames.get(move_unit_ids[0]) if move_unit_ids else None
            equation_ids = tuple(dict.fromkeys(
                equation_id for unit in move_units
                for equation_id in unit_equation_ids.get(unit.argument_unit_id, ())
            ))
            configuration_ids = tuple(dict.fromkeys(
                configuration_id for unit in move_units
                for configuration_id in unit_configuration_ids.get(unit.argument_unit_id, ())
            ))
            anchor_ids = _move_anchor_ids(move.move, frame, equation_ids, configuration_ids)
            move_assignments = [
                item for item in section_assignments
                if item.required_move == move.move
                or (item.argument_unit_id in move_unit_ids and item.required_move == move.move)
            ]
            unresolved_ids = tuple(dict.fromkeys(
                item.obligation_id for item in move_assignments
                if item.status not in _SUPPORTED_STATUSES
            ))
            # The routing lane comes from the exact unresolved assignment's
            # contract (status + next action), never from the first generic
            # move lane or the row's original lane.
            lane = "executable_hard"
            if unresolved_ids:
                lane = _assignment_routing_lane(move_assignments[0])
            if move.move == "limitations_or_mismatch" and unresolved_ids:
                state = (
                    "external_pending"
                    if lane in {"author_attested", "empirical_artifact", "external_literature", "expository_bridge"}
                    else "open"
                )
            elif getattr(move, "unanchored", False):
                owner = str(getattr(move, "unanchored_owner", "") or "")
                if owner == "Formalizer" or move.move == "equation_or_derivation":
                    lane = "formal_derivation"
                elif owner == "Research" or move.move in {
                    "algorithm_or_data_flow", "mechanism_overview",
                }:
                    lane = "executable_hard"
                else:
                    lane = "author_attested"
                state = (
                    "external_pending"
                    if lane in {"author_attested", "empirical_artifact", "external_literature", "expository_bridge"}
                    else "open"
                )
            elif move.move in _ORGANIZATION_MOVES or _expository_move(move.move):
                state = "bridge"
                lane = "expository_bridge"
            elif anchor_ids:
                state = "anchored"
            elif unresolved_ids:
                state = (
                    "external_pending"
                    if lane in {"author_attested", "empirical_artifact", "external_literature", "expository_bridge"}
                    else "open"
                )
            else:
                state = "open"
            proof_unanchored = bool(getattr(move, "unanchored", False))
            if state == "open" and not anchor_ids and not unresolved_ids:
                proof_unanchored = True
            if move.move == "limitations_or_mismatch" and state in {
                "open", "external_pending",
            }:
                proof_unanchored = True
            proof_unresolved = (
                ()
                if state in {"anchored", "bridge"}
                else unresolved_ids
            )
            proofs.append(MoveAuthorityProofV1(
                section_id=section.section_id,
                argument_unit_ids=move_unit_ids,
                move=move.move,
                required=bool(move.required),
                anchor_ids=anchor_ids,
                unresolved_obligation_ids=proof_unresolved,
                required_authority_lane=lane,
                owner_route=_proof_owner_route(lane),
                state=state,
                unanchored=proof_unanchored,
                unanchored_owner=str(getattr(move, "unanchored_owner", "") or ""),
            ))
    return tuple(proofs)


_ORGANIZATION_MOVES = frozenset({
    "problem_or_local_context", "design_objective", "intuition_or_rationale",
    "transition_to_next_section",
})


def _expository_move(move: str) -> bool:
    return move in _ORGANIZATION_MOVES


def _assignment_routing_lane(assignment: ObligationMoveAssignmentV1) -> str:
    """Derive the request routing lane from the exact assignment contract.

    An explicit_code_gap is accepted by the author unless the next action
    authorizes a widened repository search; an unverified row with a
    repository-research next action stays executable_hard; author/external/
    formalization required rows keep their own lanes.
    """

    status = str(assignment.status)
    next_action = str(assignment.next_action or "").lower()
    if status == "explicit_code_gap":
        if "widen" in next_action or "search" in next_action:
            return "executable_hard"
        return "author_attested"
    if status == "author_confirmation_required":
        return "author_attested"
    if status == "external_evidence_required":
        return "external_literature"
    if status == "formalization_required":
        return "formal_derivation"
    return str(assignment.authority_lane) or "executable_hard"


def _proof_owner_route(lane: str) -> str:
    route_by_lane: dict[str, str] = {
        "executable_hard": "repository_tools",
        "configuration_resolved": "configuration_tools",
        "formal_derivation": "formalization_agent",
        "author_attested": "author_confirmation_queue",
        "empirical_artifact": "empirical_artifact_tools",
        "external_literature": "external_literature_tools",
        "expository_bridge": "author_confirmation_queue",
    }
    return route_by_lane.get(lane, "author_confirmation_queue")


def _move_authority_lanes(
    move: str,
    *,
    all_lanes: tuple[str, ...],
) -> tuple[str, ...]:
    """Return the authority lanes a rhetorical move may legitimately use.

    A section graph can contain executable claims while its problem statement,
    design objective, or rationale still lacks an authority-bearing input.
    Reusing ``all_lanes`` for those organization moves silently tells a Writer
    that executable code proves author intent.  Keep the lane explicit so an
    unresolved move becomes an author/literature callback instead of an
    implementation claim.
    """

    organization_lanes: dict[str, tuple[str, ...]] = {
        "problem_or_local_context": (
            "author_attested",
            "external_literature",
            "expository_bridge",
        ),
        "design_objective": (
            "author_attested",
            "expository_bridge",
        ),
        "intuition_or_rationale": (
            "author_attested",
            "formal_derivation",
            "expository_bridge",
        ),
        "transition_to_next_section": ("expository_bridge",),
    }
    if move in organization_lanes:
        return organization_lanes[move]
    if move == "formal_objects_and_notation":
        return tuple(dict.fromkeys((*all_lanes, "formal_derivation")))
    if move == "equation_or_derivation":
        return tuple(dict.fromkeys((*all_lanes, "formal_derivation")))
    if move == "configuration_and_branches":
        return tuple(dict.fromkeys((*all_lanes, "configuration_resolved")))
    return all_lanes or ("executable_hard",)


__all__ = [
    "MethodArchitect",
    "build_method_section_plan",
    "build_method_section_plan_with_product_readiness",
    "build_method_section_plan_with_trace",
]
