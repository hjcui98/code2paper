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


def _details_for_mechanisms(contexts: Any, mechanism_ids: Sequence[str]) -> tuple[list[Any], list[Any]]:
    by_id = {
        _text(_get(context, "mechanism_id")): context
        for context in (_get(contexts, "contexts", ()) or ())
        if _text(_get(context, "mechanism_id"))
    }
    required: list[Any] = []
    optional: list[Any] = []
    for mechanism_id in mechanism_ids:
        context = by_id.get(mechanism_id)
        if context is None:
            continue
        for detail in _get(context, "details", ()) or ():
            policy = _text(_get(detail, "publication_policy"))
            status = _text(_get(detail, "active_path_status"))
            if policy in {"annotated_only", "review_only"} or status in {
                "inactive_default", "unreachable", "inactive_path", "unknown",
            }:
                optional.append(detail)
            else:
                required.append(detail)
    return required, optional


def build_intent_narrative_plan_v4(
    *,
    story_spine: Sequence[Any] = (),
    prior_plan: Any | None = None,
    contexts: Any | None = None,
    intent_atoms: Sequence[Any] = (),
    formula_obligation_ids: Sequence[str] = (),
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

    units_by_section = {
        row["section_id"]: tuple(row["argument_unit_ids"])
        for row in section_rows
    }
    sections: list[IntentNarrativeSectionV4] = []
    for row in section_rows:
        section_id = row["section_id"]
        story_ids = tuple(dict.fromkeys(assigned_stories.get(section_id, ())))
        mechanism_ids = tuple(dict.fromkeys(
            mechanism_id
            for story_id in story_ids
            for mechanism_id in (binding_by_story.get(story_id).mechanism_ids if story_id in binding_by_story else ())
        ))
        required_details, optional_details = _details_for_mechanisms(contexts, mechanism_ids)
        paragraphs: list[IntentNarrativeParagraphV4] = []
        if story_ids:
            for index, story_id in enumerate(story_ids, start=1):
                binding = binding_by_story.get(story_id)
                story_mechs = tuple(binding.mechanism_ids) if binding is not None else ()
                atom_ids = tuple(atoms_by_story.get(story_id, ()))
                surface = "repository_statement" if story_mechs and binding and binding.binding_status in {"exact", "partial"} else "author_specification"
                if binding and binding.binding_status == "mismatch":
                    surface = "mismatch_statement"
                paragraphs.append(IntentNarrativeParagraphV4(
                    paragraph_id=f"{section_id}:P{index}",
                    section_id=section_id,
                    role="step_sequence",
                    heading_intent=row["heading_intent"],
                    reader_goal=row["reader_question"],
                    ordered_story_node_ids=(story_id,),
                    ordered_argument_unit_ids=units_by_section.get(section_id, ()),
                    intent_atom_ids=atom_ids,
                    mechanism_ids=story_mechs,
                    required_detail_ids=tuple(
                        _text(_get(detail, "detail_id"))
                        for detail in required_details
                        if not story_mechs or _text(_get(detail, "primary_mechanism_id")) in story_mechs
                    ),
                    optional_detail_ids=tuple(
                        _text(_get(detail, "detail_id"))
                        for detail in optional_details
                        if not story_mechs or _text(_get(detail, "primary_mechanism_id")) in story_mechs
                    ),
                    required_intent_atom_ids=atom_ids,
                    required_author_surface_ids=(story_id,) if surface != "repository_statement" else (),
                    formula_obligation_ids=tuple(formula_obligation_ids),
                    authority_surface=surface,
                    transition_from="" if index == 1 else f"{section_id}:P{index - 1}",
                ))
        else:
            paragraphs.append(IntentNarrativeParagraphV4(
                paragraph_id=f"{section_id}:P1",
                section_id=section_id,
                role="overview",
                heading_intent=row["heading_intent"],
                reader_goal=row["reader_question"],
                ordered_argument_unit_ids=units_by_section.get(section_id, ()),
                authority_surface="author_specification",
                required_author_surface_ids=(section_id,),
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
            ordered_argument_unit_ids=units_by_section.get(section_id, ()),
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
    }
    return plan, bindings, trace


def project_intent_plan_to_narrative_v3(plan: IntentNarrativePlanV4) -> Any:
    """Duck-typed V3 view: same section/paragraph identities, optional mechanism_id."""

    from types import SimpleNamespace

    sections = []
    units = []
    for section in plan.sections:
        paragraphs = []
        for paragraph in section.paragraphs:
            paragraphs.append(SimpleNamespace(
                paragraph_id=paragraph.paragraph_id,
                section_id=paragraph.section_id,
                role=paragraph.role,
                mechanism_id=paragraph.mechanism_id,
                mechanism_ids=paragraph.mechanism_ids,
                required_detail_ids=paragraph.required_detail_ids,
                optional_detail_ids=paragraph.optional_detail_ids,
                formula_obligation_ids=paragraph.formula_obligation_ids,
                witness_contract=paragraph.witness_contract,
                transition_from=paragraph.transition_from,
                transition_to=paragraph.transition_to,
                reader_goal=paragraph.reader_goal,
                ordered_story_node_ids=paragraph.ordered_story_node_ids,
                ordered_argument_unit_ids=paragraph.ordered_argument_unit_ids,
            ))
        sections.append(SimpleNamespace(
            section_id=section.section_id,
            heading=section.heading,
            heading_intent=section.heading_intent,
            reader_question=section.reader_question,
            mechanism_ids=section.mechanism_ids,
            paragraphs=tuple(paragraphs),
            ordered_story_node_ids=section.ordered_story_node_ids,
            ordered_argument_unit_ids=section.ordered_argument_unit_ids,
        ))
        units.append(SimpleNamespace(
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
    return SimpleNamespace(
        plan_id=plan.plan_id,
        sections=tuple(sections),
        narrative_units=tuple(units),
        formula_placements=(),
        context_set_digest="",
        content_digest=plan.content_digest,
        schema_version="v4-projected",
    )
