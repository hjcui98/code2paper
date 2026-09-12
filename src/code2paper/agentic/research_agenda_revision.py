"""Bounded, source-backed revisions of research hypotheses.

Author goal identities/text and validation status remain outside model control.
The agenda itself carries the journal through ordinary checkpoint persistence.
"""
from __future__ import annotations

import hashlib
from typing import Any

from code2paper.agentic.behavior_graph import BEHAVIOR_PREDICATES, BEHAVIOR_RELATION_KINDS
from code2paper.agentic.research_models import ResearchAgendaItemV1


def apply_agenda_revisions(agenda: Any, decision: Any, observations: Any) -> list[dict[str, Any]]:
    if decision.produced_by != "llm_proposal":
        return []
    known_spans = {span for obs in observations for span in obs.exact_span_ids}
    by_id = {item.obligation_id: item for item in agenda.items}
    results = []
    for revision in decision.agenda_revisions:
        parent = by_id.get(revision.parent_obligation_id)
        reason = ""
        if parent is None or parent.obligation_id != decision.obligation_id:
            reason = "revision_parent_not_active"
        elif parent.status in {"supported", "explicit_gap", "blocked"} or parent.priority == "must_not_claim":
            reason = "revision_parent_not_open"
        elif not set(revision.source_span_ids).issubset(known_spans):
            reason = "revision_source_not_observed"
        elif any(not (t.desired_predicates or t.required_relations) or
                 not set(t.desired_predicates).issubset(BEHAVIOR_PREDICATES) or
                 not set(t.required_relations).issubset(BEHAVIOR_RELATION_KINDS) for t in revision.targets):
            reason = "revision_unregistered_target"
        elif len(parent.revision_history) >= 4:
            reason = "revision_budget_exhausted"
        payload = revision.model_dump(mode="json")
        digest = hashlib.sha256(revision.model_dump_json().encode()).hexdigest()[:16]
        if parent is not None and any(r.get("digest") == digest for r in parent.revision_history):
            continue
        if not reason and revision.mode == "add_subquestion":
            if sum(bool(i.parent_obligation_id) for i in agenda.items) >= 8:
                reason = "subquestion_budget_exhausted"
            else:
                child = ResearchAgendaItemV1(
                    obligation_id=f"research:{parent.obligation_id}:{digest}",
                    parent_obligation_id=parent.obligation_id,
                    priority="should_cover", author_text=revision.question,
                    typed_behavior_targets=list(revision.targets),
                    missing_information=[revision.question],
                    revision_history=[{**payload, "digest": digest, "accepted": True}],
                )
                agenda.items.append(child)
        elif not reason:
            payload["previous_targets"] = [t.model_dump(mode="json") for t in parent.typed_behavior_targets]
            parent.typed_behavior_targets = list(revision.targets)
            parent.missing_information = list(dict.fromkeys([*parent.missing_information, revision.question]))
        record = {**payload, "digest": digest, "accepted": not reason, "rejection_reason": reason}
        results.append(record)
        if parent is not None and len(parent.revision_history) < 8:
            parent.revision_history.append(record)
    agenda.refresh_content_digest()
    return results


def selected_entry_roots(agenda, graph):
    """Resolve sourced selection to observed call roots, not lexical scores."""
    roots = set()
    for item in agenda.items:
        for record in item.revision_history:
            if not record.get("accepted"):
                continue
            spans = set(record.get("source_span_ids", ()))
            requested = set(record.get("selected_entry_symbol_ids", ()))
            for relation in graph.relations:
                if relation.kind == "CALLS" and relation.source_span_id in spans and relation.source_symbol_id in requested:
                    roots.add(relation.source_symbol_id)
    return tuple(sorted(roots))


def intent_graph_with_research_revisions(graph, agenda):
    """Project journaled hypotheses to coverage/planning, keeping original input immutable."""
    from code2paper.agentic.intent_compiler_v2 import IntentObligationRelationV2
    originals = {item.obligation_id: item for item in graph.obligations}
    obligations = list(graph.obligations)
    relations = list(graph.relations)
    by_id = {item.obligation_id: item for item in agenda.items}
    obligations = [item.model_copy(update={"typed_behavior_targets": tuple(by_id[item.obligation_id].typed_behavior_targets)})
                   if item.obligation_id in by_id and any(r.get("accepted") and r.get("mode") == "revise_hypothesis" for r in by_id[item.obligation_id].revision_history)
                   else item for item in obligations]
    for item in agenda.items:
        if item.obligation_id in originals or item.parent_obligation_id not in originals:
            continue
        parent = originals[item.parent_obligation_id]
        obligations.append(parent.model_copy(update={"obligation_id": item.obligation_id, "kind": "component",
            "priority": "should_cover", "source_field": "research_subquestion", "author_text": item.author_text,
            "typed_behavior_targets": tuple(item.typed_behavior_targets), "status": "unresolved"}))
        relations.append(IntentObligationRelationV2(source_obligation_id=item.obligation_id, target_obligation_id=parent.obligation_id, relation="supports"))
    payload = graph.model_dump(mode="json")
    payload.update(obligations=[o.model_dump(mode="json") for o in obligations], relations=[r.model_dump(mode="json") for r in relations], content_digest="")
    return graph.__class__.model_validate(payload)
