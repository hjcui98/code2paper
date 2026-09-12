"""Project the narrative geometry onto the existing publication controller.

Evidence identities match sections; ordinal positions never match mechanisms.
The original obligation assignments and authority proofs remain present.
"""
from __future__ import annotations

from code2paper.agentic.callback_plan_repair import _strings


def bridge_narrative_plan(prior, narrative, contexts):
    from code2paper.agentic.method_argument_models import MethodSectionPlanV2, SectionArgumentGraphV1, SectionParagraphPlanV1
    context_by_id = {c.mechanism_id: c for c in contexts.contexts}
    old = prior.model_dump(mode="json")
    old_units = {u["argument_unit_id"]: u for u in old["argument_units"]}
    section_refs = {}
    for section in narrative.sections:
        section_refs[section.section_id] = set().union(*(
            _strings(context_by_id[mid].model_dump(mode="json"))
            for mid in section.mechanism_ids if mid in context_by_id
        )) if section.mechanism_ids else set()
    mapping = {}
    for section in old["sections"]:
        sid = section["section_id"]
        if sid in section_refs:
            mapping[sid] = sid
            continue
        values = _strings([section, *(old_units[u] for u in section["argument_unit_ids"] if u in old_units)])
        # Restrict matching to provenance handles, never boilerplate prose,
        # status strings, labels or section position.
        refs = {v for v in values if ":" in v or v.startswith(("claim-", "fact-", "brief-", "facet-"))}
        scores = [(len(refs & values), target) for target, values in section_refs.items()]
        scores.sort(key=lambda row: (-row[0], row[1]))
        if not scores or scores[0][0] == 0:
            raise ValueError(f"unified_controller_section_unbound:{sid}")
        mapping[sid] = scores[0][1]
    sections = []
    for section in narrative.sections:
        sources = [s for s in old["sections"] if mapping[s["section_id"]] == section.section_id]
        unit_ids = tuple(dict.fromkeys(u for s in sources for u in s["argument_unit_ids"]))
        moves = {}
        for s in sources:
            for move in s["moves"]:
                key = move["move"]
                if key not in moves:
                    moves[key] = dict(move)
                else:
                    moves[key]["argument_unit_ids"] = list(dict.fromkeys([*moves[key]["argument_unit_ids"], *move["argument_unit_ids"]]))
                    moves[key]["required"] = moves[key]["required"] or move["required"]
                    moves[key]["allowed_authority_lanes"] = list(dict.fromkeys([*moves[key]["allowed_authority_lanes"], *move["allowed_authority_lanes"]]))
        payload = sources[0].copy() if sources else {}
        for field in ("story_node_ids", "primary_concept_keys", "supporting_concept_keys",
                      "audit_only_concept_keys", "primary_brief_ids", "supporting_brief_ids",
                      "required_dataflow_relation_ids", "unresolved_inputs"):
            payload[field] = tuple(dict.fromkeys(v for s in sources for v in s.get(field, ())))
        questions = [u.reader_question for u in narrative.narrative_units if u.section_id == section.section_id]
        payload.update(section_id=section.section_id, heading=section.heading,
                       reader_question=" ".join(dict.fromkeys(questions)) or payload.get("reader_question", section.heading), argument_unit_ids=unit_ids,
                       moves=list(moves.values()), dependencies=(), content_digest="",
                       paragraphs=[SectionParagraphPlanV1(paragraph_id=p.paragraph_id,
                           argument_unit_ids=unit_ids, formula_obligation_ids=p.formula_obligation_ids).model_dump(mode="json") for p in section.paragraphs])
        sections.append(SectionArgumentGraphV1.model_validate(payload))
    new = dict(old)
    new.update(plan_id=f"{prior.plan_id}:narrative", sections=[s.model_dump(mode="json") for s in sections], content_digest="")
    paragraph_ids = {s.section_id: tuple(p.paragraph_id for p in s.paragraphs) for s in narrative.sections}
    for field in ("method_units", "obligation_assignments", "move_authority_proofs"):
        new[field] = []
        for row in old.get(field, ()):
            row = dict(row)
            old_section = row.get("section_id", "")
            if old_section:
                row["section_id"] = mapping[old_section]
                if "paragraph_ids" in row:
                    row["paragraph_ids"] = paragraph_ids[row["section_id"]]
                row["content_digest"] = ""
            new[field].append(row)
    # Merging sections also merges per-move proofs without dropping their
    # unresolved obligation identities.
    proofs = {}
    for proof in new["move_authority_proofs"]:
        key = (proof["section_id"], proof["move"])
        if key not in proofs:
            proofs[key] = proof
        else:
            for name, value in proof.items():
                if isinstance(value, (tuple, list)) and all(isinstance(v, str) for v in value):
                    proofs[key][name] = list(dict.fromkeys([*proofs[key].get(name, ()), *value]))
    new["move_authority_proofs"] = list(proofs.values())
    new["incomplete_sections"] = list(dict.fromkeys(mapping[s] for s in old.get("incomplete_sections", ()) if s in mapping))
    return MethodSectionPlanV2.model_validate(new)
