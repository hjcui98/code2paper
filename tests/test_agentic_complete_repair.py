from types import SimpleNamespace as NS

import pytest

from code2paper.agentic.research_agenda_revision import apply_agenda_revisions, selected_entry_roots
from code2paper.agentic.research_models import ResearchAgendaV1, ResearchAgendaItemV1, ResearchAgendaRevisionV1, TypedBehaviorTargetV1
from code2paper.agentic.publication_transaction_contract import splice_formula_placeholders
from code2paper.llm.section_writer import _compact_formula_packages_for_llm
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.schemas import LLMConfig, LLMProvider


def agenda():
    return ResearchAgendaV1(run_id="run", repo_snapshot_id="snapshot", project_tree_hash="tree", intent_graph_digest="intent",
        items=[ResearchAgendaItemV1(obligation_id="goal", priority="must_cover", author_text="Explain feature fusion")])


def revision(**kw):
    return ResearchAgendaRevisionV1(parent_obligation_id="goal", question="Is fusion a weighted sum?", reason="Observed multiplication and reduction",
        source_span_ids=("span:model.py:3:5",), targets=(TypedBehaviorTargetV1(target_id="sum", desired_predicates=("COMPUTE",)),), **kw)


def test_agenda_child_preserves_goal_and_checkpoint_identity():
    a = agenda()
    before = a.content_digest
    d = NS(produced_by="llm_proposal", obligation_id="goal", agenda_revisions=(revision(),))
    obs = [NS(exact_span_ids=("span:model.py:3:5",))]
    assert apply_agenda_revisions(a, d, obs)[0]["accepted"]
    assert len(a.items) == 2 and a.items[0].author_text == "Explain feature fusion"
    assert a.items[0].priority == "must_cover" and a.items[0].status == "pending"
    assert a.items[1].parent_obligation_id == "goal"
    assert a.content_digest != before
    restored = ResearchAgendaV1.model_validate_json(a.model_dump_json())
    apply_agenda_revisions(restored, d, obs)
    assert len(restored.items) == 2


def test_agenda_rejects_unobserved_source_and_keeps_target():
    a = agenda()
    d = NS(produced_by="llm_proposal", obligation_id="goal", agenda_revisions=(revision(mode="revise_hypothesis"),))
    result = apply_agenda_revisions(a, d, [])
    assert result[0]["rejection_reason"] == "revision_source_not_observed"
    assert a.items[0].typed_behavior_targets == []


def test_agenda_revises_inferred_targets_without_author_goal_loss():
    a = agenda()
    a.items[0].typed_behavior_targets = [TypedBehaviorTargetV1(target_id="guess", desired_predicates=("CONCAT",))]
    d = NS(produced_by="llm_proposal", obligation_id="goal", agenda_revisions=(revision(mode="revise_hypothesis"),))
    result = apply_agenda_revisions(a, d, [NS(exact_span_ids=("span:model.py:3:5",))])
    assert result[0]["previous_targets"][0]["desired_predicates"] == ["CONCAT"]
    assert a.items[0].typed_behavior_targets[0].desired_predicates == ("COMPUTE",)
    assert a.items[0].status == "pending"


def test_entry_selection_requires_observed_call_relation():
    a = agenda()
    r = revision(selected_entry_symbol_ids=("sym:root",))
    d = NS(produced_by="llm_proposal", obligation_id="goal", agenda_revisions=(r,))
    apply_agenda_revisions(a, d, [NS(exact_span_ids=r.source_span_ids)])
    assert selected_entry_roots(a, NS(relations=[])) == ()
    rel = NS(kind="CALLS", source_span_id=r.source_span_ids[0], source_symbol_id="sym:root")
    assert selected_entry_roots(a, NS(relations=[rel])) == ("sym:root",)
    rel.source_span_id = "span:other.py:1:2"
    assert selected_entry_roots(a, NS(relations=[rel])) == ()


def test_lexical_relevance_never_grants_scope_authority():
    from code2paper.agentic.implementation_scope import infer_implementation_scope
    symbols = [NS(symbol_id="symbol:x", qualified_name="fusion_forward", path="model.py", kind="function", docstring="fusion")]
    s = infer_implementation_scope(symbols, author_texts=["fusion forward"])
    assert s.candidate_entry_symbol_ids == ("symbol:x",)
    assert s.target_core_symbol_ids == () and s.unknown_symbol_ids == ("symbol:x",)


def formula(**kw):
    return {"package_id": "f", "latex": "y=x", "review_status": "accepted", "authority_status": "code_verified", "formula_lane": "repository_derived", **kw}


def test_formula_review_authority_reaches_writer_and_cannot_leak():
    f = formula(formula_lane="author_intent", authority_status="author_intent", review_status="review_required")
    compact = _compact_formula_packages_for_llm([f])[0]
    assert compact["review_status"] == "review_required"
    assert "never assert" in compact["publication_policy"]
    body, failures = splice_formula_placeholders("We implement [[FORMULA:f]].", [f])
    assert failures == ("formula_authority_unqualified:f",)
    assert "[[FORMULA:f]]" in body
    body, failures = splice_formula_placeholders("Author-proposed design hypothesis: [[FORMULA:f]].", [f])
    assert not failures and "y=x" in body


def test_formula_condition_must_survive_in_same_paragraph():
    f = formula(material_conditions=["training only"])
    assert splice_formula_placeholders("[[FORMULA:f]]", [f])[1] == ("formula_material_condition_missing:f",)
    assert not splice_formula_placeholders("For training only: [[FORMULA:f]]", [f])[1]


def test_client_budget_blocks_before_network(monkeypatch):
    client = LLMClient(LLMConfig(provider="openai", model="offline", max_input_tokens=20))
    monkeypatch.setattr(client, "_complete_provider", lambda _: pytest.fail("network must not be called"))
    result = client.complete(LLMRequest("budget", "中文" * 100, {}))
    assert result.blocked_reason.startswith("input_budget_exhausted:")


def test_formula_obligations_separate_disconnected_calculations():
    from code2paper.agentic.formalization_agent import compile_mechanism_formula_obligations
    from tests.test_agentic_mechanism_formula_obligations import _make_context
    ctx = _make_context()
    loss = ctx.details[0].model_copy(update={"active_path_status": "active_default"})
    other = loss.model_copy(update={"detail_id": "d:mask", "predicate": "MASK", "operands": ("doc_ids",), "result": "mask", "source_operation_ids": ("op:mask",)})
    obligations = compile_mechanism_formula_obligations(ctx.model_copy(update={"details": (loss, other)}))
    assert {o.source_detail_ids for o in obligations} == {("d:loss",), ("d:mask",)}


def test_formula_obligation_includes_positive_logit_dependency():
    from code2paper.agentic.formalization_agent import compile_mechanism_formula_obligations
    from tests.test_agentic_mechanism_formula_obligations import _make_context
    ctx = _make_context()
    loss = ctx.details[0].model_copy(update={"active_path_status": "active_default"})
    concat = loss.model_copy(update={"detail_id": "d:concat", "predicate": "CONCAT", "operands": ("positive", "negatives"), "result": "logits", "source_operation_ids": ("op:concat",)})
    obligations = compile_mechanism_formula_obligations(ctx.model_copy(update={"details": (concat, loss)}))
    assert len(obligations) == 1
    assert obligations[0].source_detail_ids == ("d:concat", "d:loss")


def test_architect_calls_real_request_contract_and_rejects_dropped_coverage():
    from code2paper.agentic.method_architect import build_narrative_plan_v3
    from tests.test_agentic_narrative_architect_v3 import _make_context_set
    calls = []
    def caller(config, request):
        calls.append(request)
        payload = dict(request.input_payload["base_plan"])
        payload["sections"] = []
        payload["content_digest"] = ""
        import json
        return LLMResponse(text=json.dumps(payload), response_hash="offline")
    plan, trace = build_narrative_plan_v3(contexts=_make_context_set(), proposal_caller=caller, llm_config=NS())
    assert len(calls) == 1 and isinstance(calls[0], LLMRequest)
    assert not trace["proposal_accepted"] and plan.sections


def test_legacy_empty_search_checkpoint_does_not_prove_absence():
    from code2paper.agentic.research_nodes import InformationGainTracker
    tracker = InformationGainTracker.from_snapshot({"exhausted_tools": {"goal": ["search_symbols", "search_code"]}})
    assert not tracker.targeted_search_exhausted("goal")


def test_architect_accepts_proposal_without_changing_evidence():
    import json
    from code2paper.agentic.method_architect import build_narrative_plan_v3
    from tests.test_agentic_narrative_architect_v3 import _make_context_set
    def caller(_, request):
        payload = request.input_payload["base_plan"]
        payload["sections"][0]["heading"] = "Representation and learning objective"
        payload["content_digest"] = ""
        return LLMResponse(text=json.dumps(payload), response_hash="offline")
    plan, trace = build_narrative_plan_v3(contexts=_make_context_set(), proposal_caller=caller, llm_config=NS())
    assert trace["proposal_accepted"], trace.get("proposal_failure")
    assert plan.sections[0].heading == "Representation and learning objective"


def test_callback_preserves_unaffected_plan_and_required_set():
    from code2paper.agentic.callback_plan_repair import preserve_unaffected_plan
    from code2paper.agentic.method_argument_models import MethodSectionPlanV2, SectionArgumentGraphV1
    old = MethodSectionPlanV2(plan_id="p", sections=(SectionArgumentGraphV1(section_id="s1", heading="First", reader_question="How?"), SectionArgumentGraphV1(section_id="s2", heading="Stable", reader_question="Why?")))
    proposed = MethodSectionPlanV2(plan_id="p2", sections=(SectionArgumentGraphV1(section_id="s1", heading="Repaired", reader_question="How?"), SectionArgumentGraphV1(section_id="s2", heading="Unrequested rewrite", reader_question="Why?")))
    plan, preserved = preserve_unaffected_plan(old, proposed, affected_section_ids=("s1",))
    assert preserved == ("s2",)
    assert plan.sections[0].heading == "Repaired"
    assert plan.sections[1].model_dump() == old.sections[1].model_dump()


def test_shared_pages_keep_oversized_source_and_mark_budget():
    from code2paper.agentic.mechanism_context_projection import build_mechanism_context_slices, serialize_shared_mechanism_payload
    from tests.test_agentic_mechanism_formula_obligations import _make_context
    context = _make_context()
    closure = context.evidence_closure.model_copy(update={"exact_excerpts": ("x" * 5000,)})
    slices = build_mechanism_context_slices(context.model_copy(update={"evidence_closure": closure}), max_page_tokens=100)
    assert any(s.technical_payload["budget_exhausted"] for s in slices)
    assert b"x" * 5000 in serialize_shared_mechanism_payload(slices)


def test_ambiguous_file_hint_does_not_select_arbitrary_entry():
    from code2paper.agentic.implementation_scope import infer_implementation_scope
    symbols = [NS(symbol_id=f"s:{i}", path="model.py", qualified_name=f"f{i}", kind="function") for i in range(2)]
    scope = infer_implementation_scope(symbols, entry_symbol_ids=("model.py",))
    assert scope.target_entry_symbol_ids == ()


def test_callback_gain_cannot_change_comparison_denominator():
    from code2paper.agentic.publication_method_writer import _rewrite_transaction_has_cluster_gain
    assert _rewrite_transaction_has_cluster_gain({"required_target_set_digest": "before"}, {"required_target_set_digest": "after"}, cluster_name="formula_rendering") == (False, "comparison_target_set_changed")


def test_formula_batch_sends_shared_payload_once_and_accounts_missing_rows():
    from code2paper.agentic.formalization_agent import compile_mechanism_formula_obligations, run_mechanism_formalizer
    from tests.test_agentic_mechanism_formalizer import _make_context
    context = _make_context()
    base = compile_mechanism_formula_obligations(context)[0]
    other = base.model_copy(update={"obligation_id": "ob:other"})
    calls = []
    def caller(_, request):
        calls.append(request)
        return LLMResponse(text='{"formulas":[]}', response_hash="offline")
    packages, trace = run_mechanism_formalizer(context=context, obligations=(base, other), shared_payload="canonical-pages", caller=caller,
        llm_config=NS(), allow_deterministic_operation_fallback=False)
    assert len(calls) == 1 and calls[0].input_payload["shared_payload"] == "canonical-pages"
    assert "canonical-pages" not in calls[0].prompt
    assert packages == () and trace["batch_request_count"] == 1
    assert sum(f.startswith("formula_batch_missing:") for f in trace["failures"]) == 2


def test_research_revisions_reach_planning_without_mutating_author_input():
    from code2paper.agentic.research_agenda_revision import intent_graph_with_research_revisions
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2, IntentObligationV2
    graph = IntentObligationGraphV2(obligations=[IntentObligationV2(obligation_id="goal", kind="method_mainline", priority="must_cover", source_field="method_goal", author_text="Explain feature fusion")])
    a = agenda()
    d = NS(produced_by="llm_proposal", obligation_id="goal", agenda_revisions=(revision(),))
    apply_agenda_revisions(a, d, [NS(exact_span_ids=revision().source_span_ids)])
    projected = intent_graph_with_research_revisions(graph, a)
    assert len(projected.obligations) == 2 and len(graph.obligations) == 1
    assert projected.relations[0].target_obligation_id == "goal"


def test_formula_batch_binds_each_response_to_its_own_obligation():
    import json
    from code2paper.agentic.formalization_agent import compile_mechanism_formula_obligations, run_mechanism_formalizer
    from tests.test_agentic_mechanism_formalizer import _make_context
    context = _make_context()
    base = compile_mechanism_formula_obligations(context)[0]
    obligations = (base, base.model_copy(update={"obligation_id": "ob:second"}))
    calls = []
    def caller(_, request):
        calls.append(request)
        return LLMResponse(text=json.dumps({"formulas": [{"obligation_id": ob.obligation_id,
            "latex": r"loss = \operatorname{compute_loss}(logits, labels)",
            "prose_explanation": "The objective compares predictions with labels.",
            "symbol_definitions": [["logits", "scores"], ["labels", "targets"], ["loss", "objective"]],
            "material_conditions": [], "assumptions": []} for ob in obligations]}), response_hash="offline")
    packages, trace = run_mechanism_formalizer(context=context, obligations=obligations,
        shared_payload="canonical-pages", caller=caller, llm_config=NS(), allow_deterministic_operation_fallback=False)
    assert len(calls) == 1 and len(packages) == 2, trace["failures"]
    assert {p.satisfied_obligation_ids for p in packages} == {(o.obligation_id,) for o in obligations}
    assert all(p.bound_operation_ids == ("op:loss",) for p in packages)


def test_narrative_bridge_reorders_and_merges_by_evidence_identity():
    from code2paper.agentic.unified_plan_bridge import bridge_narrative_plan
    from code2paper.agentic.method_argument_models import MethodSectionPlanV2, SectionArgumentGraphV1
    from code2paper.agentic.method_architect import NarrativePlanV3, NarrativeSectionPlanV3
    from tests.test_agentic_mechanism_formula_obligations import _make_context
    contexts = NS(contexts=tuple(_make_context().model_copy(update={"mechanism_id": mid, "brief_ids": (bid,)}) for mid, bid in (("m1", "brief-one"), ("m2", "brief-two"))))
    prior = MethodSectionPlanV2(plan_id="p", sections=tuple(SectionArgumentGraphV1(section_id=sid, heading=sid, reader_question="How?", primary_brief_ids=(bid,)) for sid, bid in (("old1", "brief-one"), ("old2", "brief-two"))))
    narrative = NS(sections=(NarrativeSectionPlanV3(section_id="new2", heading="Second", mechanism_ids=("m2",)), NarrativeSectionPlanV3(section_id="new1", heading="First", mechanism_ids=("m1",))), narrative_units=())
    result = bridge_narrative_plan(prior, narrative, contexts)
    assert result.sections[0].primary_brief_ids == ("brief-two",)
    assert result.sections[1].primary_brief_ids == ("brief-one",)
    narrative.sections = (NarrativeSectionPlanV3(section_id="merged", heading="Joint", mechanism_ids=("m1", "m2")),)
    merged = bridge_narrative_plan(prior, narrative, contexts)
    assert set(merged.sections[0].primary_brief_ids) == {"brief-one", "brief-two"}


def test_local_unified_resume_preserves_sibling_and_rejects_global_rename():
    from code2paper.agentic.callback_plan_repair import preserve_unaffected_narrative
    from code2paper.agentic.method_architect import NarrativePlanV3, NarrativeSectionPlanV3
    old = NarrativePlanV3(plan_id="p", sections=tuple(NarrativeSectionPlanV3(section_id=s, heading=s) for s in ("s1", "s2")), narrative_units=())
    proposed = NarrativePlanV3(plan_id="next", sections=tuple(NarrativeSectionPlanV3(section_id=s, heading="changed " + s) for s in ("s2", "s1")), narrative_units=())
    result = preserve_unaffected_narrative(old, proposed, affected_section_ids=("s1",))
    assert result.sections[0].heading == "changed s1"
    assert result.sections[1] == old.sections[1]
    renamed = proposed.model_copy(update={"sections": (NarrativeSectionPlanV3(section_id="new", heading="New"),)})
    with pytest.raises(ValueError, match="ownership_changed"):
        preserve_unaffected_narrative(old, renamed, affected_section_ids=("s1",))
