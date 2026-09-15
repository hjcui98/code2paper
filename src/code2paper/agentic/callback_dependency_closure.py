"""Typed dependency closure for one callback authority delta.

R8: a callback must revalidate exactly the sections its authority delta can
reach, and it must keep every other committed sibling byte-for-byte.  The
mapping runs over typed references only:

    detail/claim/equation/configuration/formula -> argument unit -> section

Headings, section order, wording and generation time are not part of the
closure, so a pure heading or ordering change never invalidates unrelated
prose.  A delta target that cannot be mapped is reported in
``unresolved_target_ids`` instead of being dropped or matched by string
search.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.mechanism_context_models import (
    canonical_json_bytes,
    sha256_digest,
)


class CallbackAuthorityDeltaV1(BaseModel):
    """The typed authority change one callback round actually introduced."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detail_ids: tuple[str, ...] = Field(default_factory=tuple)
    operation_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    configuration_ids: tuple[str, ...] = Field(default_factory=tuple)
    condition_ids: tuple[str, ...] = Field(default_factory=tuple)
    formula_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)

    def is_empty(self) -> bool:
        return not any(
            (
                self.detail_ids,
                self.operation_ids,
                self.fact_ids,
                self.claim_ids,
                self.equation_ids,
                self.configuration_ids,
                self.condition_ids,
                self.formula_obligation_ids,
            )
        )


class CallbackDependencyClosureV1(BaseModel):
    """Sections, units and paragraphs one authority delta can reach."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    delta_digest: str
    affected_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    affected_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    affected_paragraph_ids: tuple[str, ...] = Field(default_factory=tuple)
    #: ``target_kind:target_id`` -> ``section_id`` provenance so a reviewer can
    #: see why one section is in scope without re-running the mapping.
    basis: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    unresolved_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    #: Newly added authority that no planned section owns.  It cannot
    #: invalidate committed prose, so it is reported instead of blocking the
    #: resume scope; a changed or removed target that cannot be mapped still
    #: lands in ``unresolved_target_ids`` and blocks.
    unmapped_added_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "CallbackDependencyClosureV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("callback dependency closure content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


def compute_callback_dependency_closure(
    delta: CallbackAuthorityDeltaV1,
    *,
    plan: Any | None = None,
    narrative_plan: Any | None = None,
    previous_plan: Any | None = None,
    previous_narrative_plan: Any | None = None,
    target_owner_map: Mapping[str, Any] | None = None,
    added_target_ids: Iterable[str] = (),
) -> CallbackDependencyClosureV1:
    """Map one authority delta onto the sections that own it.

    R8 correction: ownership is resolved through *both* dependency graphs.  A
    detail, fact or operation that the rebuild removed or downgraded no longer
    appears in the new plan, so the previous plan and narrative plan are part
    of the lookup; otherwise deleted authority would either be dropped or
    reported as an unmappable target and block the whole resume.
    """

    unit_maps = [
        {
            str(getattr(unit, "argument_unit_id", "") or ""): unit
            for unit in (getattr(candidate, "argument_units", ()) or ())
        }
        for candidate in (plan, previous_plan)
        if candidate is not None
    ]
    narrative_plans = [
        candidate
        for candidate in (narrative_plan, previous_narrative_plan)
        if candidate is not None
    ]
    pre_resolved: dict[str, tuple[str, ...]] = {}
    for key, value in (target_owner_map or {}).items():
        owners = tuple(
            str(item) for item in (value or ()) if str(item).strip()
        )
        if owners:
            pre_resolved[str(key)] = owners

    added_targets = {
        str(value) for value in (added_target_ids or ()) if str(value).strip()
    }
    basis: dict[str, list[str]] = {}
    unresolved: list[str] = []
    unmapped_added: list[str] = []
    unit_ids: set[str] = set()
    paragraph_ids: set[str] = set()
    section_ids: set[str] = set()

    def _record(target_key: str, unit_id: str, section_id: str) -> None:
        if unit_id:
            unit_ids.add(unit_id)
        if section_id:
            section_ids.add(section_id)
        basis.setdefault(target_key, [])
        owner = section_id or unit_id
        if owner and owner not in basis[target_key]:
            basis[target_key].append(owner)

    unit_targets: dict[str, set[str]] = {
        "claim_ids": set(delta.claim_ids),
        "equation_ids": set(delta.equation_ids),
        "configuration_ids": set(delta.configuration_ids),
    }
    # One unit may be owned by several sections (a shared configuration or a
    # merge), so the mapping is a multimap: every owning section is affected.
    sections_by_unit: dict[str, list[str]] = {}
    for candidate in (plan, previous_plan):
        for section in (getattr(candidate, "sections", ()) or ()):
            section_id = str(getattr(section, "section_id", "") or "")
            for unit_id in (getattr(section, "argument_unit_ids", ()) or ()):
                key = str(unit_id)
                if section_id and section_id not in sections_by_unit.setdefault(key, []):
                    sections_by_unit[key].append(section_id)

    for field_name, targets in unit_targets.items():
        for target_id in sorted(targets):
            matched = False
            for unit_by_id in unit_maps:
                for unit_id, unit in unit_by_id.items():
                    values = {
                        str(value)
                        for value in (getattr(unit, field_name, ()) or ())
                        if str(value).strip()
                    }
                    if target_id in values:
                        matched = True
                        for section_id in sections_by_unit.get(unit_id, [""]):
                            _record(
                                f"{field_name.removesuffix('_ids')}:{target_id}",
                                unit_id,
                                section_id,
                            )
            if not matched:
                unresolved.append(f"{field_name.removesuffix('_ids')}:{target_id}")

    # Detail ownership is a narrative-plan fact: a paragraph names its
    # mechanism and its required details, and its section owns the paragraph.
    paragraph_unit_by_id: dict[str, str] = {}
    for candidate in narrative_plans:
        for section in (getattr(candidate, "sections", ()) or ()):
            section_id = str(getattr(section, "section_id", "") or "")
            for paragraph in (getattr(section, "paragraphs", ()) or ()):
                paragraph_id = str(getattr(paragraph, "paragraph_id", "") or "")
                if not paragraph_id:
                    continue
                detail_ids = {
                    str(value)
                    for value in (
                        tuple(getattr(paragraph, "required_detail_ids", ()) or ())
                        + tuple(getattr(paragraph, "optional_detail_ids", ()) or ())
                    )
                    if str(value).strip()
                }
                paragraph_unit_by_id[paragraph_id] = str(
                    getattr(paragraph, "mechanism_id", "") or ""
                )
                for detail_id in sorted(
                    set(delta.detail_ids) & detail_ids
                ):
                    # Only a paragraph that actually owns a delta target enters
                    # the closure; an untouched sibling stays out of scope.
                    paragraph_ids.add(paragraph_id)
                    section_ids.add(section_id)
                    basis.setdefault(f"detail:{detail_id}", [])
                    if section_id and section_id not in basis[f"detail:{detail_id}"]:
                        basis[f"detail:{detail_id}"].append(section_id)

    for detail_id in sorted(delta.detail_ids):
        if f"detail:{detail_id}" in basis or pre_resolved.get(f"detail:{detail_id}"):
            continue
        if f"detail:{detail_id}" in added_targets:
            unmapped_added.append(f"detail:{detail_id}")
        else:
            unresolved.append(f"detail:{detail_id}")

    for field_name, values in (
        ("operation", delta.operation_ids),
        ("fact", delta.fact_ids),
        ("condition", delta.condition_ids),
        ("formula_obligation", delta.formula_obligation_ids),
    ):
        for value in sorted(str(item) for item in values if str(item).strip()):
            target_key = f"{field_name}:{value}"
            owners = pre_resolved.get(target_key, ())
            if owners:
                for owner in owners:
                    _record(target_key, "", owner)
            elif target_key in added_targets:
                unmapped_added.append(target_key)
            else:
                unresolved.append(target_key)

    delta_digest = sha256_digest(canonical_json_bytes(
        delta.model_dump(mode="json")
    ))
    return CallbackDependencyClosureV1(
        delta_digest=delta_digest,
        affected_section_ids=tuple(sorted(section_ids)),
        affected_unit_ids=tuple(sorted(unit_ids)),
        affected_paragraph_ids=tuple(sorted(paragraph_ids)),
        basis={key: tuple(value) for key, value in sorted(basis.items())},
        unresolved_target_ids=tuple(dict.fromkeys(unresolved)),
        unmapped_added_target_ids=tuple(dict.fromkeys(unmapped_added)),
    )


def narrow_resume_sections(
    *,
    requested_section_ids: Any,
    closure: CallbackDependencyClosureV1,
) -> tuple[tuple[str, ...], str, tuple[str, ...]]:
    """Resolve the resume scope from the proven closure.

    Returns ``(sections, reason, unresolved_target_ids)``.

    R8 correction: the resume set must never be narrower than the proven
    impact.  When the closure reaches sections outside the requested set the
    scope is *expanded* (revalidating more is safe); when a delta target
    cannot be mapped at all the caller cannot prove the requested scope is
    sufficient and must block instead of proceeding.
    """

    requested = tuple(
        dict.fromkeys(
            str(value) for value in (requested_section_ids or ()) if str(value).strip()
        )
    )
    if closure.unresolved_target_ids:
        # Fail closed: an unmappable target may affect any section.
        return requested, "closure_unresolved_targets_blocked", (
            closure.unresolved_target_ids
        )
    if not closure.affected_section_ids:
        return requested, "closure_empty", ()
    closure_sections = set(closure.affected_section_ids)
    requested_set = set(requested)
    if not closure_sections.issubset(requested_set):
        expanded = tuple(dict.fromkeys((*requested, *closure.affected_section_ids)))
        return expanded, "closure_expanded", ()
    if closure_sections == requested_set:
        return requested, "closure_matches_request", ()
    narrowed = tuple(
        section_id for section_id in requested if section_id in closure_sections
    )
    return narrowed, "closure_narrowed", ()


__all__ = [
    "CallbackAuthorityDeltaV1",
    "CallbackDependencyClosureV1",
    "compute_callback_dependency_closure",
    "narrow_resume_sections",
]
