"""Compile author-intent narrative plans independently of mechanism count."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from code2paper.agentic.intent_spine_models import (
    IntentNarrativeParagraphV4,
    IntentNarrativePlanV4,
    IntentNarrativeSectionV4,
    StoryMechanismBindingV1,
    heading_is_internal_identifier,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_text(value),) if _text(value) else ()
    return tuple(dict.fromkeys(_text(item) for item in value if _text(item)))


def _get(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _notes_kind(node: Any) -> str:
    for note in _ids(_get(node, "notes")):
        if note.startswith("kind="):
            return note.split("=", 1)[1].split(";")[0].strip()
    return ""


def _priority(node: Any) -> str:
    for note in _ids(_get(node, "notes")):
        if "priority=" in note:
            for part in note.split(";"):
                part = part.strip()
                if part.startswith("priority="):
                    return part.split("=", 1)[1].strip()
    return ""


def _digest(*parts: str) -> str:
    return "sha256:" + hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def compile_story_mechanism_bindings(
    *,
    story_spine: Sequence[Any],
    contexts: Any | None = None,
    intent_atoms: Sequence[Any] = (),
) -> tuple[StoryMechanismBindingV1, ...]:
    """Join story nodes to mechanisms by closed evidence IDs, not section count."""

    context_rows = tuple(_get(contexts, "contexts", ()) or ()) if contexts is not None else ()
    atoms_by_story: dict[str, list[str]] = defaultdict(list)
    for atom in intent_atoms:
        story_id = _text(_get(atom, "story_node_id"))
        atom_id = _text(_get(atom, "atom_id"))
        if story_id and atom_id:
            atoms_by_story[story_id].append(atom_id)

    mechanism_handles: dict[str, set[str]] = {}
    for context in context_rows:
        mechanism_id = _text(_get(context, "mechanism_id"))
        if not mechanism_id:
            continue
        handles: set[str] = set(_ids(_get(context, "story_node_ids")))
        closure = _get(context, "evidence_closure")
        handles.update(_ids(_get(closure, "fact_ids")))
        handles.update(_ids(_get(closure, "claim_ids")))
        handles.update(_ids(_get(closure, "equation_ids")))
        handles.update(_ids(_get(closure, "exact_span_ids")))
        handles.update(_ids(_get(closure, "seed_obligation_ids")))
        handles.update(_ids(_get(context, "entry_symbol_ids")))
        for detail in _get(context, "details", ()) or ():
            handles.update(_ids(_get(detail, "source_claim_ids")))
            handles.update(_ids(_get(detail, "source_fact_ids")))
            handles.update(_ids(_get(detail, "source_span_ids")))
            handles.update(_ids(_get(detail, "source_equation_ids")))
        mechanism_handles[mechanism_id] = {item for item in handles if item}

    bindings: list[StoryMechanismBindingV1] = []
    for node in story_spine:
        story_id = _text(_get(node, "story_node_id") or _get(node, "node_id"))
        if not story_id:
            continue
        story_handles = set()
        story_handles.update(_ids(_get(node, "linked_claim_ids")))
        story_handles.update(_ids(_get(node, "linked_obligation_ids")))
        story_handles.update(_ids(_get(node, "source_refs")))
        matches: list[tuple[int, str, tuple[str, ...]]] = []
        for mechanism_id, handles in mechanism_handles.items():
            overlap = tuple(sorted(story_handles & handles))
            if overlap:
                matches.append((len(overlap), mechanism_id, overlap))
        matches.sort(key=lambda item: (-item[0], item[1]))
        mechanism_ids = tuple(item[1] for item in matches)
        basis = tuple(dict.fromkeys(handle for item in matches for handle in item[2]))
        atom_ids = tuple(dict.fromkeys(atoms_by_story.get(story_id, ())))
        if not mechanism_ids:
            status = "unresolved"
        elif len(mechanism_ids) == 1 and basis:
            status = "exact" if _priority(node) != "must_cover" or basis else "partial"
            if _ids(_get(node, "linked_claim_ids")) and not (
                set(_ids(_get(node, "linked_claim_ids"))) & set(basis)
            ):
                status = "partial"
        else:
            status = "partial"
        unresolved = atom_ids if status in {"unresolved", "partial", "mismatch"} else ()
        bindings.append(StoryMechanismBindingV1(
            story_node_id=story_id,
            intent_atom_ids=atom_ids,
            mechanism_ids=mechanism_ids,
            binding_basis_ids=basis,
            binding_status=status,  # type: ignore[arg-type]
            unresolved_atom_ids=unresolved,
        ))
    return tuple(bindings)


def _section_rows_from_prior_plan(prior_plan: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section in _get(prior_plan, "sections", ()) or ():
        section_id = _text(_get(section, "section_id"))
        heading = _text(_get(section, "heading") or _get(section, "heading_intent"))
        if not section_id or not heading:
            continue
        unit_ids = _ids(_get(section, "argument_unit_ids"))
        reader_question = _text(_get(section, "reader_question"))
        rows.append({
            "section_id": section_id,
            "heading_intent": heading,
            "reader_question": reader_question or heading,
            "argument_unit_ids": unit_ids,
            "obligation_ids": set(),
            "claim_ids": set(),
        })
    units = _get(prior_plan, "argument_units", ()) or ()
    by_id = {_text(_get(unit, "argument_unit_id")): unit for unit in units}
    for row in rows:
        for unit_id in row["argument_unit_ids"]:
            unit = by_id.get(unit_id)
            if unit is None:
                continue
            row["obligation_ids"].update(_ids(_get(unit, "source_obligation_ids")))
            row["claim_ids"].update(_ids(_get(unit, "claim_ids")))
    return rows


def _section_rows_from_story(story_spine: Sequence[Any]) -> list[dict[str, Any]]:
    org_nodes = [
        node for node in story_spine
        if _notes_kind(node) == "organization" or _text(_get(node, "intended_role")) in {
            "motivation", "setup", "training", "inference"
        } and _notes_kind(node) in {"organization", ""}
    ]
    if not org_nodes:
        org_nodes = [
            node for node in story_spine
            if _priority(node) == "must_cover"
        ]
    rows: list[dict[str, Any]] = []
    for index, node in enumerate(org_nodes, start=1):
        heading = _text(_get(node, "title") or _get(node, "author_statement"))
        section_id = f"MA-S{index}"
        rows.append({
            "section_id": section_id,
            "heading_intent": heading,
            "reader_question": heading,
            "argument_unit_ids": (),
            "obligation_ids": set(_ids(_get(node, "linked_obligation_ids"))),
            "claim_ids": set(_ids(_get(node, "linked_claim_ids"))),
            "organization_story_id": _text(_get(node, "story_node_id")),
        })
    return rows


def _assign_story_to_sections(
    story_spine: Sequence[Any],
    section_rows: list[dict[str, Any]],
) -> dict[str, list[str]]:
    assigned: dict[str, list[str]] = {row["section_id"]: [] for row in section_rows}
    used: set[str] = set()
    heading_index = {
        _text(row["heading_intent"]).casefold(): row["section_id"]
        for row in section_rows
    }
    for node in story_spine:
        story_id = _text(_get(node, "story_node_id"))
        title = _text(_get(node, "title")).casefold()
        if story_id and title in heading_index:
            assigned[heading_index[title]].append(story_id)
            used.add(story_id)
    for node in story_spine:
        story_id = _text(_get(node, "story_node_id"))
        if not story_id or story_id in used:
            continue
        obligations = set(_ids(_get(node, "linked_obligation_ids")))
        claims = set(_ids(_get(node, "linked_claim_ids")))
        scores = []
        for row in section_rows:
            score = len(obligations & row["obligation_ids"]) * 2 + len(claims & row["claim_ids"])
            scores.append((score, row["section_id"]))
        scores.sort(key=lambda item: (-item[0], item[1]))
        if scores and scores[0][0] > 0:
            assigned[scores[0][1]].append(story_id)
            used.add(story_id)
    role_map = {
        "motivation": 0,
        "setup": 1,
        "algorithm_step": 2,
        "training": 3,
        "inference": 4,
    }
    leftovers = [
        node for node in story_spine
        if _text(_get(node, "story_node_id")) not in used
    ]
    for node in leftovers:
        story_id = _text(_get(node, "story_node_id"))
        if not story_id:
            continue
        role = _text(_get(node, "intended_role"))
        index = role_map.get(role, min(2, len(section_rows) - 1))
        index = min(index, len(section_rows) - 1)
        assigned[section_rows[index]["section_id"]].append(story_id)
        used.add(story_id)
    return assigned


def _story_handles(node: Any) -> set[str]:
    return set(_ids(_get(node, "linked_claim_ids"))) | set(_ids(_get(node, "linked_obligation_ids"))) | set(_ids(_get(node, "source_refs")))


def _detail_handles(detail: Any) -> set[str]:
    return set().union(*(
        set(_ids(_get(detail, field)))
        for field in (
            "source_claim_ids", "source_obligation_ids", "source_fact_ids",
            "source_span_ids", "source_equation_ids", "source_operation_ids",
        )
    ))


def _detail_is_required(detail: Any) -> bool:
    return _text(_get(detail, "publication_policy")) not in {"annotated_only", "review_only"} and _text(
        _get(detail, "active_path_status")
    ) in {"active_default", "active_selected", "conditional"}


def _best_slot(slots: Sequence[dict[str, Any]], handles: set[str]) -> dict[str, Any]:
    # Stable tie-breaking retains the author's story order. A zero-overlap
    # assignment is an organizational fallback, never evidence authorization.
    return max(slots, key=lambda slot: len(handles & slot["story_handles"]))


def build_intent_narrative_plan_v4(
    *,
    story_spine: Sequence[Any] = (),
    prior_plan: Any | None = None,
    contexts: Any | None = None,
    intent_atoms: Sequence[Any] = (),
    formula_obligation_ids: Sequence[str] = (),
    formula_packages: Sequence[Any] = (),
) -> tuple[IntentNarrativePlanV4, tuple[StoryMechanismBindingV1, ...], dict[str, Any]]:
    """Freeze author section identity, then bind mechanisms as evidence providers."""

    story_values = tuple(story_spine or ())
    if prior_plan is not None and _get(prior_plan, "sections"):
        section_rows = _section_rows_from_prior_plan(prior_plan)
        order_source = "accepted_author_plan"
    else:
        section_rows = _section_rows_from_story(story_values)
        order_source = "author_intent"
    if not section_rows:
        raise ValueError("intent narrative plan requires author section identity")

    bindings = compile_story_mechanism_bindings(
        story_spine=story_values,
        contexts=contexts,
        intent_atoms=intent_atoms,
    )
    binding_by_story = {item.story_node_id: item for item in bindings}
    assigned_stories = _assign_story_to_sections(story_values, section_rows)
    atoms_by_story: dict[str, list[str]] = defaultdict(list)
    for atom in intent_atoms:
        story_id = _text(_get(atom, "story_node_id"))
        atom_id = _text(_get(atom, "atom_id"))
        if story_id and atom_id:
            atoms_by_story[story_id].append(atom_id)

    story_by_id = {
        _text(_get(node, "story_node_id")): node for node in story_values
        if _text(_get(node, "story_node_id"))
    }
    unit_by_id = {
        _text(_get(unit, "argument_unit_id")): unit
        for unit in (_get(prior_plan, "argument_units", ()) or ())
    }
    slots_by_section: dict[str, list[dict[str, Any]]] = {}
    slots_by_mechanism: dict[str, list[dict[str, Any]]] = defaultdict(list)
    mechanism_binding_fallbacks: list[str] = []
    binding_fallbacks: list[str] = []
    required_binding_fallbacks: list[str] = []
    for row in section_rows:
        section_id = row["section_id"]
        slots: list[dict[str, Any]] = []
        story_ids = tuple(dict.fromkeys(assigned_stories.get(section_id, ())))
        for story_id in story_ids or ("",):
            binding = binding_by_story.get(story_id)
            owners = tuple(binding.mechanism_ids) if binding and binding.mechanism_ids else ("",)
            for owner_index, mechanism_id in enumerate(owners):
                slot = {
                    "section_id": section_id,
                    "story_id": story_id,
                    "mechanism_id": mechanism_id,
                    "story_handles": _story_handles(story_by_id.get(story_id)),
                    "argument_unit_ids": [],
                    "intent_atom_ids": list(atoms_by_story.get(story_id, ())) if owner_index == 0 else [],
                    "required_details": [],
                    "optional_details": [],
                    "formula_obligation_ids": [],
                    "formula_package_ids": [],
                }
                slots.append(slot)
                if mechanism_id:
                    slots_by_mechanism[mechanism_id].append(slot)
        slots_by_section[section_id] = slots
        for unit_id in row["argument_unit_ids"]:
            unit = unit_by_id.get(unit_id)
            handles = set(_ids(_get(unit, "source_obligation_ids"))) | set(_ids(_get(unit, "claim_ids")))
            _best_slot(slots, handles)["argument_unit_ids"].append(unit_id)

    packages_by_mechanism: dict[str, list[Any]] = defaultdict(list)
    for package in formula_packages:
        packages_by_mechanism[_text(_get(package, "mechanism_id"))].append(package)

    for context in (_get(contexts, "contexts", ()) or ()):
        mechanism_id = _text(_get(context, "mechanism_id"))
        details = tuple(_get(context, "details", ()) or ())
        packages = packages_by_mechanism.pop(mechanism_id, [])
        if not details and not packages:
            continue
        eligible = slots_by_mechanism.get(mechanism_id, ())
        if not eligible:
            handles = set().union(*(_detail_handles(detail) for detail in details)) if details else set()
            section_id = max(
                slots_by_section,
                key=lambda candidate: len(handles & set().union(*(
                    slot["story_handles"] for slot in slots_by_section[candidate]
                ))),
            )
            slot = {
                "section_id": section_id,
                "story_id": "",
                "mechanism_id": mechanism_id,
                "story_handles": set(),
                "argument_unit_ids": [],
                "intent_atom_ids": [],
                "required_details": [],
                "optional_details": [],
                "formula_obligation_ids": [],
                "formula_package_ids": [],
            }
            slots_by_section[section_id].append(slot)
            slots_by_mechanism[mechanism_id].append(slot)
            eligible = (slot,)
            mechanism_binding_fallbacks.append(mechanism_id)
        detail_by_id = {_text(_get(detail, "detail_id")): detail for detail in details}
        package_detail_ids = {
            detail_id
            for package in packages
            for detail_id in _ids(_get(package, "source_detail_ids"))
        }
        unknown_package_details = package_detail_ids - detail_by_id.keys()
        if unknown_package_details:
            raise ValueError(
                f"intent_plan_v4_formula_unknown_detail:{mechanism_id}:{','.join(sorted(unknown_package_details))}"
            )
        # Formula sources must share one paragraph with every package that
        # consumes them. Other details can follow their own story anchors.
        package_slot = _best_slot(
            eligible,
            set().union(*(_detail_handles(detail_by_id[did]) for did in package_detail_ids))
            if package_detail_ids else set(),
        ) if packages else None
        for detail in details:
            detail_id = _text(_get(detail, "detail_id"))
            if not detail_id:
                raise ValueError(f"intent_plan_v4_empty_detail_id:{mechanism_id}")
            if _text(_get(detail, "primary_mechanism_id")) not in {"", mechanism_id}:
                raise ValueError(f"intent_plan_v4_detail_owner_mismatch:{detail_id}:{mechanism_id}")
            handles = _detail_handles(detail)
            slot = package_slot if detail_id in package_detail_ids else _best_slot(eligible, handles)
            if not handles.intersection(slot["story_handles"]):
                binding_fallbacks.append(detail_id)
                if _detail_is_required(detail):
                    required_binding_fallbacks.append(detail_id)
            slot["required_details" if _detail_is_required(detail) else "optional_details"].append(detail)
        if package_slot is not None:
            for package in packages:
                package_slot["formula_package_ids"].append(_text(_get(package, "package_id")))
                package_slot["formula_obligation_ids"].extend(_ids(_get(package, "satisfied_obligation_ids")))
    if packages_by_mechanism:
        raise ValueError(
            "intent_plan_v4_formula_unknown_mechanism:"
            + ",".join(sorted(packages_by_mechanism))
        )
    # Legacy callers may provide obligation identities without packages. Keep
    # each identity once; validation still decides whether it is compiled.
    placed_obligations = {
        obligation_id
        for slots in slots_by_section.values()
        for slot in slots
        for obligation_id in slot["formula_obligation_ids"]
    }
    for obligation_id in _ids(formula_obligation_ids):
        if obligation_id not in placed_obligations:
            owner_slots = next((items for items in slots_by_mechanism.values() if items), ())
            if not owner_slots:
                raise ValueError(f"intent_plan_v4_formula_without_mechanism:{obligation_id}")
            owner_slots[0]["formula_obligation_ids"].append(obligation_id)
            placed_obligations.add(obligation_id)

    from code2paper.agentic.method_architect import _v3_detail_witness_contract

    sections: list[IntentNarrativeSectionV4] = []
    for row in section_rows:
        section_id = row["section_id"]
        story_ids = tuple(dict.fromkeys(assigned_stories.get(section_id, ())))
        mechanism_ids = tuple(dict.fromkeys(
            slot["mechanism_id"] for slot in slots_by_section[section_id]
            if slot["mechanism_id"]
        ))
        paragraphs: list[IntentNarrativeParagraphV4] = []
        for index, slot in enumerate(slots_by_section[section_id], start=1):
            story_id = slot["story_id"]
            mechanism_id = slot["mechanism_id"]
            binding = binding_by_story.get(story_id)
            surface = "repository_statement" if mechanism_id and (not story_id or binding and binding.binding_status in {"exact", "partial"}) else "author_specification"
            if binding and binding.binding_status == "mismatch":
                surface = "mismatch_statement"
            required_details = slot["required_details"]
            optional_details = slot["optional_details"]
            witness_targets = [
                target for detail in required_details
                for target in _v3_detail_witness_contract(detail, required=True)
            ]
            witness_targets.extend(
                target for detail in optional_details
                for target in _v3_detail_witness_contract(detail, required=False)
            )
            paragraphs.append(IntentNarrativeParagraphV4(
                paragraph_id=f"{section_id}:P{index}",
                section_id=section_id,
                role="step_sequence" if story_id else "overview",
                heading_intent=row["heading_intent"],
                reader_goal=row["reader_question"],
                ordered_story_node_ids=(story_id,) if story_id else (),
                ordered_argument_unit_ids=tuple(slot["argument_unit_ids"]),
                intent_atom_ids=tuple(slot["intent_atom_ids"]),
                mechanism_id=mechanism_id,
                mechanism_ids=(mechanism_id,) if mechanism_id else (),
                required_detail_ids=tuple(_text(_get(detail, "detail_id")) for detail in required_details),
                optional_detail_ids=tuple(_text(_get(detail, "detail_id")) for detail in optional_details),
                required_intent_atom_ids=tuple(slot["intent_atom_ids"]),
                required_author_surface_ids=(story_id or section_id,) if surface != "repository_statement" else (),
                formula_obligation_ids=tuple(dict.fromkeys(slot["formula_obligation_ids"])),
                formula_package_ids=tuple(dict.fromkeys(slot["formula_package_ids"])),
                authority_surface=surface,
                witness_contract={"targets": witness_targets},
                transition_from="" if index == 1 else f"{section_id}:P{index - 1}",
            ))
        heading = row["heading_intent"]
        if heading_is_internal_identifier(heading):
            heading = row["reader_question"] or "Method"
        sections.append(IntentNarrativeSectionV4(
            section_id=section_id,
            heading_intent=row["heading_intent"],
            heading=heading,
            reader_question=row["reader_question"],
            ordered_story_node_ids=story_ids,
            ordered_argument_unit_ids=tuple(row["argument_unit_ids"]),
            mechanism_ids=mechanism_ids,
            paragraphs=tuple(paragraphs),
        ))

    plan = IntentNarrativePlanV4(
        plan_id="intent-narrative-v4",
        source_intent_digest=_digest(
            *( _text(_get(node, "story_node_id")) for node in story_values )
        ),
        sections=tuple(sections),
        section_order_source=order_source,  # type: ignore[arg-type]
    )
    trace = {
        "section_count": len(plan.sections),
        "section_ids": [section.section_id for section in plan.sections],
        "headings": [section.heading for section in plan.sections],
        "mechanism_count": len({
            mechanism_id
            for section in plan.sections
            for mechanism_id in section.mechanism_ids
        }),
        "unresolved_bindings": [
            item.story_node_id for item in bindings if item.binding_status == "unresolved"
        ],
        "internal_headings": [
            section.section_id for section in plan.sections
            if heading_is_internal_identifier(section.heading)
        ],
        "order_source": order_source,
        "detail_binding_fallback_count": len(binding_fallbacks),
        "detail_binding_fallback_ids": binding_fallbacks,
        "mechanism_binding_fallback_ids": mechanism_binding_fallbacks,
        "required_detail_binding_fallback_count": len(required_binding_fallbacks),
        "required_detail_binding_fallback_ids": required_binding_fallbacks,
    }
    return plan, bindings, trace


def project_intent_plan_to_narrative_v3(plan: IntentNarrativePlanV4) -> Any:
    """Project V4 plan into NarrativePlanV3 with preserved section/paragraph identities and intent metadata."""

    from code2paper.agentic.method_architect import (
        NarrativeParagraphPlanV3,
        NarrativeSectionPlanV3,
        NarrativeUnitV1,
        NarrativePlanV3,
    )
    from code2paper.agentic.formalization_agent import FormulaPlacementV1

    sections = []
    units = []
    placements = []
    for section in plan.sections:
        paragraphs = []
        for paragraph in section.paragraphs:
            paragraphs.append(NarrativeParagraphPlanV3(
                paragraph_id=paragraph.paragraph_id,
                section_id=paragraph.section_id,
                role=paragraph.role,
                mechanism_id=paragraph.mechanism_id,
                required_detail_ids=paragraph.required_detail_ids,
                optional_detail_ids=paragraph.optional_detail_ids,
                formula_obligation_ids=paragraph.formula_obligation_ids,
                formula_package_ids=paragraph.formula_package_ids,
                shared_detail_refs=getattr(paragraph, "shared_detail_refs", ()),
                witness_contract=paragraph.witness_contract,
                transition_from=paragraph.transition_from,
                transition_to=paragraph.transition_to,
                reader_goal=paragraph.reader_goal,
                ordered_story_node_ids=paragraph.ordered_story_node_ids,
                ordered_argument_unit_ids=paragraph.ordered_argument_unit_ids,
                intent_atom_ids=paragraph.intent_atom_ids,
                required_intent_atom_ids=paragraph.required_intent_atom_ids,
                required_author_surface_ids=paragraph.required_author_surface_ids,
                required_repository_proposition_ids=paragraph.required_repository_proposition_ids,
                authority_surface=paragraph.authority_surface,
                mechanism_ids=paragraph.mechanism_ids,
            ))
            placements.extend(
                FormulaPlacementV1(
                    package_id=package_id,
                    section_id=section.section_id,
                    paragraph_id=paragraph.paragraph_id,
                )
                for package_id in paragraph.formula_package_ids
            )
        sections.append(NarrativeSectionPlanV3(
            section_id=section.section_id,
            heading=section.heading,
            heading_intent=section.heading_intent,
            reader_question=section.reader_question,
            mechanism_ids=section.mechanism_ids,
            paragraphs=tuple(paragraphs),
            ordered_story_node_ids=section.ordered_story_node_ids,
            ordered_argument_unit_ids=section.ordered_argument_unit_ids,
        ))
        units.append(NarrativeUnitV1(
            unit_id=f"unit:{section.section_id}",
            section_id=section.section_id,
            mechanism_context_ids=section.mechanism_ids,
            rhetorical_role="method",
            reader_question=section.reader_question,
            paragraph_ids=tuple(item.paragraph_id for item in paragraphs),
            required_detail_ids=tuple(
                detail_id
                for paragraph in section.paragraphs
                for detail_id in paragraph.required_detail_ids
            ),
            optional_detail_ids=tuple(
                detail_id
                for paragraph in section.paragraphs
                for detail_id in paragraph.optional_detail_ids
            ),
            formula_obligation_ids=tuple(
                obligation_id
                for paragraph in section.paragraphs
                for obligation_id in paragraph.formula_obligation_ids
            ),
            suggested_depth="standard",
        ))
    return NarrativePlanV3(
        plan_id=plan.plan_id,
        sections=tuple(sections),
        narrative_units=tuple(units),
        formula_placements=tuple(placements),
        context_set_digest="",
        content_digest="",
    )
