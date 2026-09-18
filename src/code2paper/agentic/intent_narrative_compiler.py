"""Compile author-intent narrative plans independently of mechanism count."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from code2paper.agentic.intent_spine_models import (
    AuthorIntentSurfaceV1,
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


def compile_author_intent_surfaces(
    story_spine: Sequence[Any],
) -> dict[str, AuthorIntentSurfaceV1]:
    """把作者 story 解析成页内可用的局部语义条目（不是 ID 清单）。"""

    surfaces: dict[str, AuthorIntentSurfaceV1] = {}
    for node in story_spine:
        story_id = _text(_get(node, "story_node_id"))
        if not story_id:
            continue
        statement = _text(_get(node, "author_statement")) or _text(_get(node, "title"))
        if not statement:
            continue
        payload = _story_intent_payload(node)
        surfaces[story_id] = AuthorIntentSurfaceV1(
            surface_id=f"surface:{story_id}",
            story_node_id=story_id,
            author_statement=statement,
            intended_role=_text(_get(node, "intended_role")),
            local_reader_goal=_text(_get(node, "reader_question")) or statement,
            authority_surface="author_specification",
            implementation_status="unresolved",
            source_content_digest=_digest(
                json.dumps(payload, ensure_ascii=False, sort_keys=True)
            ),
        )
    return surfaces


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


@dataclass(frozen=True)
class SlotBindingDecision:
    """一次槽位绑定的可审计结论（方案 §6.4）。

    ``status`` 为 ``grounded`` 时才有证据依据；``organizational_fallback``
    只是确定性的组织落位，不得把证据等级升级为仓库实现事实。
    """

    slot_id: str | None
    overlap_ids: tuple[str, ...]
    status: str
    needs_research: bool


@dataclass(frozen=True)
class AuthoringUnitV1:
    """一个可写单元：段落身份、作者语义、义务与可审计去向。"""

    unit_id: str
    section_id: str
    paragraph_kind: str
    intended_role: str
    local_reader_goal: str
    authority_surface: str
    implementation_status: str
    disposition: str
    story_ids: tuple[str, ...] = ()
    slot_ids: tuple[str, ...] = ()
    surfaces: tuple[Any, ...] = ()
    mechanism_ids: tuple[str, ...] = ()
    required_details: tuple[Any, ...] = ()
    optional_details: tuple[Any, ...] = ()
    argument_unit_ids: tuple[str, ...] = ()
    intent_atom_ids: tuple[str, ...] = ()
    formula_obligation_ids: tuple[str, ...] = ()
    formula_package_ids: tuple[str, ...] = ()
    unresolved_ids: tuple[str, ...] = ()

    @property
    def is_writable(self) -> bool:
        """structural_only 不生成段落；unresolved 以受限作者描述出现。

        unresolved 单元仍要写出作者说明（否则 must-cover story 会被静默丢弃），
        但它的 ``authority_surface``/``implementation_status`` 明确禁止把它当成
        仓库已验证实现。
        """

        return self.paragraph_kind != "structural_only"

    def as_trace(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "section_id": self.section_id,
            "paragraph_kind": self.paragraph_kind,
            "intended_role": self.intended_role,
            "authority_surface": self.authority_surface,
            "implementation_status": self.implementation_status,
            "disposition": self.disposition,
            "source_story_ids": list(self.story_ids),
            "source_slot_ids": list(self.slot_ids),
            "required_detail_ids": [
                _text(_get(detail, "detail_id")) for detail in self.required_details
            ],
            "unresolved_ids": list(self.unresolved_ids),
        }


def _slot_binding_decision(
    slots: Sequence[dict[str, Any]], handles: set[str]
) -> SlotBindingDecision:
    """把"选一个槽位"变成带依据与状态的决策，而不是裸槽位。"""

    if not slots:
        return SlotBindingDecision(None, (), "unresolved", bool(handles))
    best: dict[str, Any] | None = None
    best_count = -1
    for slot in slots:
        count = len(handles & slot["story_handles"])
        if count > best_count:
            best, best_count = slot, count
    assert best is not None
    overlap = tuple(sorted(handles & best["story_handles"]))
    if best_count <= 0:
        return SlotBindingDecision(
            _text(best.get("slot_id")), (), "organizational_fallback", bool(handles)
        )
    return SlotBindingDecision(_text(best.get("slot_id")), overlap, "grounded", False)


def _story_intent_payload(node: Any) -> dict[str, Any]:
    """作者语义内容（不含路径/运行时间），用于 v2 意图指纹。"""

    return {
        "story_node_id": _text(_get(node, "story_node_id")),
        "title": _text(_get(node, "title")),
        "author_statement": _text(_get(node, "author_statement")),
        "intended_role": _text(_get(node, "intended_role")),
        "priority": _priority(node),
        "notes": list(_ids(_get(node, "notes"))),
        "linked_claim_ids": list(_ids(_get(node, "linked_claim_ids"))),
        "linked_obligation_ids": list(_ids(_get(node, "linked_obligation_ids"))),
        "source_refs": list(_ids(_get(node, "source_refs"))),
    }


def compile_intent_content_digest(
    story_spine: Sequence[Any], intent_atoms: Sequence[Any] = ()
) -> str:
    """覆盖 statement/role/priority/notes/关联证据/顺序与 atom 内容的意图指纹。"""

    payload = {
        "version": "intent-content-v2",
        "stories": [_story_intent_payload(node) for node in story_spine],
        "intent_atoms": [
            {
                "atom_id": _text(_get(atom, "atom_id")),
                "story_node_id": _text(_get(atom, "story_node_id")),
                "statement": _text(_get(atom, "statement") or _get(atom, "text")),
            }
            for atom in intent_atoms
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _slot_kind(
    slot: Mapping[str, Any],
    *,
    binding: Any,
    story_node: Any,
) -> tuple[str, str]:
    """分类一个槽位，返回 (paragraph_kind, implementation_status)。"""

    required = tuple(slot.get("required_details") or ())
    optional = tuple(slot.get("optional_details") or ())
    packages = tuple(slot.get("formula_package_ids") or ())
    if required or packages:
        status = "supported" if binding is not None and binding.binding_status == "exact" else "partial"
        return "grounded_content", status
    statement = _text(_get(story_node, "author_statement")) or _text(_get(story_node, "title"))
    if not statement and not (slot.get("argument_unit_ids") or slot.get("intent_atom_ids")):
        # 既无作者说明也无 argument unit / intent atom：纯结构槽位。
        return "structural_only", "unresolved"
    if binding is not None and binding.binding_status == "mismatch":
        return "unresolved", "mismatch"
    if binding is not None and binding.binding_status == "unresolved":
        return "unresolved", "unresolved"
    if optional:
        return "author_specification", "partial"
    role = _text(_get(story_node, "intended_role"))
    if _notes_kind(story_node) == "organization" or role in {"motivation", "setup"}:
        return "expository_bridge", "partial"
    if _priority(story_node) == "must_cover":
        # 必须覆盖但没有任何可解释的实现归属：保留为未解决义务，
        # 不做成"必须有 detail"的伪实现段落（方案 §6.4/§6.5）。
        return "unresolved", "unresolved"
    return "author_specification", "unresolved"


def compile_authoring_units(
    slots: Sequence[Mapping[str, Any]],
    *,
    section_id: str,
    story_by_id: Mapping[str, Any],
    binding_by_story: Mapping[str, Any],
    surfaces_by_story: Mapping[str, Any],
) -> tuple[AuthoringUnitV1, ...]:
    """把槽位编译为可写单元：分类、合并、保留 coverage（方案 §6.3）。"""

    units: list[AuthoringUnitV1] = []
    merge_index: dict[tuple[str, str, str], int] = {}

    def _merge_key(kind: str, role: str, authority: str) -> tuple[str, str, str]:
        return (kind, role, authority)

    for index, slot in enumerate(slots, start=1):
        story_id = _text(slot.get("story_id"))
        mechanism_id = _text(slot.get("mechanism_id"))
        binding = binding_by_story.get(story_id)
        story_node = story_by_id.get(story_id)
        kind, implementation_status = _slot_kind(slot, binding=binding, story_node=story_node)
        role = _text(_get(story_node, "intended_role")) or (
            "step_sequence" if story_id else "overview"
        )
        surface = surfaces_by_story.get(story_id)
        if kind == "grounded_content" and mechanism_id and binding is not None and binding.binding_status in {"exact", "partial"}:
            authority = "repository_statement"
        elif kind == "unresolved" and binding is not None and binding.binding_status == "mismatch":
            authority = "mismatch_statement"
        else:
            authority = "author_specification"
        surfaces = tuple(
            item for item in (surface,) if item is not None
        )
        if surface is not None and surface.implementation_status != implementation_status:
            surfaces = (surface.model_copy(update={"implementation_status": implementation_status}),)
        local_goal = (
            _text(_get(story_node, "reader_question"))
            or (surfaces[0].local_reader_goal if surfaces else "")
        )
        unresolved_ids = tuple(
            dict.fromkeys(
                [
                    *(
                        _ids(_get(story_node, "linked_obligation_ids"))
                        if kind == "unresolved"
                        else ()
                    ),
                    *(
                        binding.unresolved_atom_ids
                        if kind == "unresolved" and binding is not None
                        else ()
                    ),
                ]
            )
        )
        if kind == "unresolved" and not unresolved_ids:
            # 没有可枚举的 obligation/atom 时，至少把 story 本身标为未解决项，
            # 保证 can't silently disappear。
            fallback = story_id or _text(slot.get("slot_id"))
            unresolved_ids = (fallback,) if fallback else ()
        unit = AuthoringUnitV1(
            unit_id=f"{section_id}:U{index}",
            section_id=section_id,
            paragraph_kind=kind,
            intended_role=role,
            local_reader_goal=local_goal,
            authority_surface=authority,
            implementation_status=implementation_status,
            disposition="",
            story_ids=(story_id,) if story_id else (),
            slot_ids=(_text(slot.get("slot_id")),) if _text(slot.get("slot_id")) else (),
            surfaces=surfaces,
            mechanism_ids=(mechanism_id,) if mechanism_id else (),
            required_details=tuple(slot.get("required_details") or ()),
            optional_details=tuple(slot.get("optional_details") or ()),
            argument_unit_ids=tuple(slot.get("argument_unit_ids") or ()),
            intent_atom_ids=tuple(slot.get("intent_atom_ids") or ()),
            formula_obligation_ids=tuple(dict.fromkeys(slot.get("formula_obligation_ids") or ())),
            formula_package_ids=tuple(dict.fromkeys(slot.get("formula_package_ids") or ())),
            unresolved_ids=unresolved_ids,
        )
        key = _merge_key(kind, role, authority)
        existing_index = merge_index.get(key)
        can_merge = (
            existing_index is not None
            and units[existing_index].paragraph_kind in {"author_specification", "expository_bridge", "structural_only", "unresolved"}
            # 承载 argument unit / intent atom 的槽位是作者覆盖锚点，不参与合并。
            and not units[existing_index].argument_unit_ids
            and not unit.argument_unit_ids
            and not units[existing_index].intent_atom_ids
            and not unit.intent_atom_ids
            and units[existing_index].mechanism_ids in {(), unit.mechanism_ids}
            and unit.mechanism_ids in {(), units[existing_index].mechanism_ids}
        )
        if can_merge:
            current = units[existing_index]
            units[existing_index] = replace(
                current,
                story_ids=tuple(dict.fromkeys((*current.story_ids, *unit.story_ids))),
                slot_ids=tuple(dict.fromkeys((*current.slot_ids, *unit.slot_ids))),
                surfaces=tuple((*current.surfaces, *unit.surfaces)),
                argument_unit_ids=tuple(dict.fromkeys((*current.argument_unit_ids, *unit.argument_unit_ids))),
                intent_atom_ids=tuple(dict.fromkeys((*current.intent_atom_ids, *unit.intent_atom_ids))),
                unresolved_ids=tuple(dict.fromkeys((*current.unresolved_ids, *unit.unresolved_ids))),
            )
            continue
        merge_index[key] = len(units)
        units.append(unit)

    # 去向必须可审计：每条单元都要有明确的处置。
    disposition_by_kind = {
        "grounded_content": "rendered_as_implementation_prose",
        "author_specification": "rendered_as_bounded_author_description",
        "expository_bridge": "context_only_no_implementation_claims",
        "structural_only": "coverage_only_no_prose",
        "unresolved": "pending_bounded_binding_or_research",
    }
    return tuple(
        replace(unit, disposition=disposition_by_kind[unit.paragraph_kind]) for unit in units
    )



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
    surfaces_by_story = compile_author_intent_surfaces(story_values)
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
                    "slot_id": f"{section_id}:slot{len(slots) + 1}",
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
                "slot_id": f"{section_id}:slot{len(slots_by_section[section_id]) + 1}",
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
    all_units: list[AuthoringUnitV1] = []
    for row in section_rows:
        section_id = row["section_id"]
        story_ids = tuple(dict.fromkeys(assigned_stories.get(section_id, ())))
        mechanism_ids = tuple(dict.fromkeys(
            slot["mechanism_id"] for slot in slots_by_section[section_id]
            if slot["mechanism_id"]
        ))
        units = compile_authoring_units(
            slots_by_section[section_id],
            section_id=section_id,
            story_by_id=story_by_id,
            binding_by_story=binding_by_story,
            surfaces_by_story=surfaces_by_story,
        )
        all_units.extend(units)
        paragraphs: list[IntentNarrativeParagraphV4] = []
        paragraph_index = 0
        for unit in units:
            if not unit.is_writable:
                # structural-only / unresolved 保留 coverage 与义务，但不强制
                # 生成独立正文段落（方案 §6.3）。
                continue
            paragraph_index += 1
            required_details = unit.required_details
            optional_details = unit.optional_details
            witness_targets = [
                target for detail in required_details
                for target in _v3_detail_witness_contract(detail, required=True)
            ]
            if unit.paragraph_kind == "grounded_content":
                witness_targets.extend(
                    target for detail in optional_details
                    for target in _v3_detail_witness_contract(detail, required=False)
                )
            paragraphs.append(IntentNarrativeParagraphV4(
                paragraph_id=f"{section_id}:P{paragraph_index}",
                section_id=section_id,
                role=unit.intended_role or "overview",
                heading_intent=row["heading_intent"],
                reader_goal=unit.local_reader_goal or row["reader_question"],
                ordered_story_node_ids=unit.story_ids,
                ordered_argument_unit_ids=unit.argument_unit_ids,
                intent_atom_ids=unit.intent_atom_ids,
                mechanism_id=unit.mechanism_ids[0] if unit.mechanism_ids else "",
                mechanism_ids=unit.mechanism_ids,
                required_detail_ids=tuple(
                    _text(_get(detail, "detail_id")) for detail in required_details
                ),
                optional_detail_ids=tuple(
                    _text(_get(detail, "detail_id")) for detail in optional_details
                ),
                required_intent_atom_ids=(
                    unit.intent_atom_ids if unit.paragraph_kind == "grounded_content" else ()
                ),
                required_author_surface_ids=(
                    tuple(item.surface_id for item in unit.surfaces)
                    if unit.authority_surface != "repository_statement"
                    else ()
                ),
                formula_obligation_ids=unit.formula_obligation_ids,
                formula_package_ids=unit.formula_package_ids,
                authority_surface=unit.authority_surface,
                witness_contract={"targets": witness_targets},
                transition_from=(
                    "" if paragraph_index == 1 else f"{section_id}:P{paragraph_index - 1}"
                ),
                paragraph_kind=unit.paragraph_kind,
                author_intent_surfaces=unit.surfaces,
                implementation_status=unit.implementation_status,
                unresolved_ids=unit.unresolved_ids,
                source_story_ids=unit.story_ids,
                source_slot_ids=unit.slot_ids,
                disposition=unit.disposition,
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
        # WP2：意图指纹覆盖 statement/role/priority/notes/关联证据/顺序/atom 内容，
        # 而不是只有 story ID（改说明文字必须改变指纹）。
        source_intent_digest=compile_intent_content_digest(story_values, intent_atoms),
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
        "source_intent_digest_version": plan.source_intent_digest_version,
        "units": [unit.as_trace() for unit in all_units],
        "unit_kind_counts": {
            kind: sum(1 for unit in all_units if unit.paragraph_kind == kind)
            for kind in (
                "grounded_content",
                "author_specification",
                "expository_bridge",
                "structural_only",
                "unresolved",
            )
        },
        "unresolved_story_ids": sorted({
            story_id for unit in all_units if unit.paragraph_kind == "unresolved"
            for story_id in unit.story_ids
        }),
        "structural_only_story_ids": sorted({
            story_id for unit in all_units if unit.paragraph_kind == "structural_only"
            for story_id in unit.story_ids
        }),
        "non_writable_unit_ids": [
            unit.unit_id for unit in all_units if not unit.is_writable
        ],
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
                # WP2：页内作者语义、可写性分类与去向随投影保留（V3 允许额外字段）。
                paragraph_kind=paragraph.paragraph_kind,
                author_intent_surfaces=[
                    surface.model_dump(mode="json")
                    for surface in paragraph.author_intent_surfaces
                ],
                surface_digest=paragraph.surface_digest,
                implementation_status=paragraph.implementation_status,
                unresolved_ids=paragraph.unresolved_ids,
                source_story_ids=paragraph.source_story_ids,
                source_slot_ids=paragraph.source_slot_ids,
                disposition=paragraph.disposition,
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
