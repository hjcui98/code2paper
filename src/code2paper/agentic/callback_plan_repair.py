"""Keep unaffected narrative contracts fixed across a research callback."""
from __future__ import annotations


def _strings(value):
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        return set().union(*(_strings(v) for v in value.values())) if value else set()
    if isinstance(value, (tuple, list)):
        return set().union(*(_strings(v) for v in value)) if value else set()
    return set()


def preserve_unaffected_narrative(prior, proposed, *, affected_section_ids):
    """Keep a local resume inside its existing section ownership boundary."""
    affected = set(affected_section_ids)
    old = prior.model_dump(mode="json")
    new = proposed.model_dump(mode="json")
    old_sections = {s["section_id"]: s for s in old["sections"]}
    replacements = {s["section_id"]: s for s in new["sections"]}
    if not affected.issubset(old_sections) or set(replacements) != set(old_sections):
        raise ValueError("callback_narrative_section_ownership_changed")
    new["sections"] = [replacements[sid] if sid in affected else section for sid, section in old_sections.items()]
    for field in ("narrative_units", "formula_placements"):
        new[field] = [r for r in new[field] if r["section_id"] in affected] + [r for r in old[field] if r["section_id"] not in affected]
    new["content_digest"] = ""
    return proposed.__class__.model_validate(new)


def preserve_unaffected_plan(prior, proposed, *, affected_section_ids, authority_diff=()):
    if prior is None or proposed is None:
        return proposed, ()
    affected = set(affected_section_ids)
    changed_refs = _strings(list(authority_diff))
    old = prior.model_dump(mode="json")
    new = proposed.model_dump(mode="json")
    # Authority changes can affect a sibling even when the original request
    # named one section. Reopen those siblings rather than retaining stale
    # proof contracts. Pure narrative reordering does not justify reopening.
    for section in old["sections"]:
        unit_ids = set(section.get("argument_unit_ids", ()))
        bound = [u for u in old.get("argument_units", ()) if u.get("argument_unit_id") in unit_ids]
        if changed_refs & _strings([section, *bound]):
            affected.add(section["section_id"])
    preserved = {s["section_id"] for s in old["sections"] if s["section_id"] not in affected}
    old_sections = {s["section_id"]: s for s in old["sections"]}
    new_sections = {s["section_id"]: s for s in new["sections"]}
    new["sections"] = [old_sections[s["section_id"]] if s["section_id"] in preserved else new_sections.get(s["section_id"], s) for s in old["sections"]]
    new["sections"].extend(s for sid, s in new_sections.items() if sid not in old_sections)
    preserved_unit_ids = {u for s in old["sections"] if s["section_id"] in preserved for u in s.get("argument_unit_ids", ())}
    new["argument_units"] = [u for u in new.get("argument_units", ()) if u["argument_unit_id"] not in preserved_unit_ids]
    new["argument_units"].extend(u for u in old.get("argument_units", ()) if u["argument_unit_id"] in preserved_unit_ids)
    for field in ("method_units", "obligation_assignments", "move_authority_proofs"):
        retained = [r for r in old.get(field, ()) if r.get("section_id") in preserved]
        old_ids = {r.get("obligation_id") for r in retained} if field == "obligation_assignments" else set()
        new[field] = [r for r in new.get(field, ()) if r.get("section_id") not in preserved and r.get("obligation_id") not in old_ids] + retained
    new["critical_high_obligation_ids"] = list(dict.fromkeys([*old.get("critical_high_obligation_ids", ()), *new.get("critical_high_obligation_ids", ())]))
    new["content_digest"] = ""
    # Validation fails closed if a changed authority set cannot be reconciled
    # locally. A callback cannot silently discard a prior required witness.
    return proposed.__class__.model_validate(new), tuple(sorted(preserved))
