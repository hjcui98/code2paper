"""WP4 Slice 4B: callback semantic delta helpers."""

from __future__ import annotations

from code2paper.agentic.callback_semantic_contract import (
    evaluate_authoring_structural_exit,
    callback_semantic_digest,
    canonical_fact_fingerprint,
    enrich_callback_request_semantics,
    evaluate_mandatory_slot_coverage,
    mandatory_slots_from_request,
)
from code2paper.agentic.method_argument_models import (
    SectionArgumentGraphV1,
    WritingResearchRequestV1,
)


def _fact(subject: str, predicate: str, object_: str, spans: tuple[str, ...]) -> object:
    return type(
        "Fact",
        (),
        {
            "subject": subject,
            "predicate": predicate,
            "object": object_,
            "direct_span_ids": spans,
            "canonical_identity": "",
        },
    )()


def test_canonical_fingerprint_dedupes_same_fact_across_ids() -> None:
    fact_a = _fact("encoder", "masks", "padding", ("span:enc.py:1:2",))
    fact_b = _fact("encoder", "masks", "padding", ("span:enc.py:1:2",))
    assert canonical_fact_fingerprint(fact_a) == canonical_fact_fingerprint(fact_b)


def test_mandatory_slots_infer_formula_from_lane_and_missing_parts() -> None:
    request = WritingResearchRequestV1(
        request_id="request:formula",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="equation_or_derivation",
        exact_question="Which loss expression binds this section?",
        required_authority_lane="formal_derivation",
        candidate_symbols_or_terms=("loss",),
        missing_parts=("formula", "loss expression"),
        priority="high",
    )
    slots = mandatory_slots_from_request(request)
    assert "formula" in slots


def test_partial_mandatory_slot_coverage_keeps_remaining_slots() -> None:
    request = WritingResearchRequestV1(
        request_id="request:partial",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="algorithm_or_data_flow",
        exact_question="How does data flow from input to output?",
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=("forward",),
        mandatory_missing_slots=("input", "transformation", "output"),
        concept_key="CK-CORE",
        priority="high",
    )
    satisfied, remaining = evaluate_mandatory_slot_coverage(
        request,
        new_fact_ids=("fact:new",),
        concept_judgment={"CK-CORE": ["span:model.py:10:12"]},
        lane_fulfilled=False,
    )
    assert "relation" in satisfied or "transformation" in satisfied
    assert remaining
    assert len(satisfied) < len(mandatory_slots_from_request(request))


def test_enrich_callback_request_semantics_populates_binding_fields() -> None:
    request = WritingResearchRequestV1(
        request_id="request:enrich",
        section_id="MA-S2",
        argument_unit_id="MA-S2:unit",
        missing_rhetorical_move="equation_or_derivation",
        exact_question="Which formula applies?",
        required_authority_lane="formal_derivation",
        candidate_symbols_or_terms=("loss",),
        concept_key="CK-LOSS",
        current_known_facts=("claim:known",),
        priority="high",
    )
    graph = SectionArgumentGraphV1(
        section_id="MA-S2",
        heading="Loss",
        reader_question="How is loss computed?",
        argument_unit_ids=("MA-S2:unit",),
        story_node_ids=("story:loss",),
        formula_obligation_ids=("formula:equation:loss",),
        primary_concept_keys=("CK-LOSS",),
        audit_only_concept_keys=("CK-AUDIT",),
    )
    enriched = enrich_callback_request_semantics(
        request,
        graph=graph,
        baseline_facts=(
            _fact("loss", "computes", "margin", ("span:loss.py:4:6",)),
        ),
    )
    assert enriched.target_story_node_ids == ("story:loss",)
    assert enriched.target_formula_obligation_ids == ("formula:equation:loss",)
    assert enriched.target_concept_keys == ("CK-LOSS",)
    assert enriched.baseline_claim_ids == ("claim:known",)
    assert enriched.baseline_fact_fingerprints
    assert enriched.excluded_audit_concept_keys == ("CK-AUDIT",)


def test_same_fact_new_obligation_id_has_no_canonical_gain() -> None:
    baseline_fact = _fact("norm", "uses", "mean", ("span:norm.py:2:3",))
    fingerprint = canonical_fact_fingerprint(baseline_fact)
    request = WritingResearchRequestV1(
        request_id="request:gain",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="implementation_realization",
        exact_question="How is normalization applied?",
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=("normalize",),
        baseline_fact_fingerprints=(fingerprint,),
        mandatory_missing_slots=("relation", "transformation"),
        priority="high",
    )
    same = _fact("norm", "uses", "mean", ("span:norm.py:2:3",))
    satisfied, remaining = evaluate_mandatory_slot_coverage(
        request,
        new_fact_ids=("fact:recompiled",),
        new_fingerprints=(canonical_fact_fingerprint(same),),
        baseline_fingerprints=(fingerprint,),
        concept_judgment={},
        lane_fulfilled=False,
    )
    assert not satisfied
    assert remaining == ("relation", "transformation")
    assert canonical_fact_fingerprint(same) == fingerprint


def test_remaining_slots_restrict_later_rounds() -> None:
    request = WritingResearchRequestV1(
        request_id="request:remain",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="algorithm_or_data_flow",
        exact_question="How does data flow?",
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=("forward",),
        mandatory_missing_slots=("input", "transformation", "output"),
        remaining_slots=("output",),
        priority="high",
    )
    assert mandatory_slots_from_request(request) == ("output",)


def test_callback_semantic_digest_changes_only_with_delta() -> None:
    first = callback_semantic_digest(
        new_fingerprints=("sha256:aaa",),
        satisfied_slots=("input",),
        remaining_slots=("output",),
        concept_keys=("CK-CORE",),
        affected_sections=("MA-S1",),
    )
    same = callback_semantic_digest(
        new_fingerprints=("sha256:aaa",),
        satisfied_slots=("input",),
        remaining_slots=("output",),
        concept_keys=("CK-CORE",),
        affected_sections=("MA-S1",),
    )
    changed = callback_semantic_digest(
        new_fingerprints=("sha256:bbb",),
        satisfied_slots=("input",),
        remaining_slots=("output",),
        concept_keys=("CK-CORE",),
        affected_sections=("MA-S1",),
    )
    assert first == same
    assert first != changed


def test_unchanged_semantic_digest_is_not_information_gain() -> None:
    from code2paper.agentic.callback_semantic_contract import (
        authoring_semantic_delta_changed,
        callback_semantic_digest,
    )

    digest = callback_semantic_digest(
        new_fingerprints=("sha256:aaa",),
        satisfied_slots=("input",),
        remaining_slots=("output",),
    )
    assert authoring_semantic_delta_changed(
        previous_digests=set(),
        semantic_digest=digest,
        new_fingerprint_count=1,
        satisfied_slots=("input",),
    )
    assert not authoring_semantic_delta_changed(
        previous_digests={digest},
        semantic_digest=digest,
        new_fingerprint_count=1,
        satisfied_slots=("input",),
    )


def test_formalization_lane_satisfies_only_formula_slot() -> None:
    request = WritingResearchRequestV1(
        request_id="request:formula-partial",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="equation_or_derivation",
        exact_question="Which formula and output apply?",
        required_authority_lane="formal_derivation",
        candidate_symbols_or_terms=("loss",),
        mandatory_missing_slots=("formula", "output"),
        priority="high",
    )
    satisfied, remaining = evaluate_mandatory_slot_coverage(
        request,
        new_fact_ids=(),
        concept_judgment={},
        lane_fulfilled=True,
    )
    assert satisfied == ("formula",)
    assert remaining == ("output",)


def _structural_payloads(*, valid: bool = True, open_request: bool = False):
    plan = {
        "content_digest": "sha256:plan",
        "sections": [{
            "section_id": "MA-S1",
            "paragraphs": [{
                "paragraph_id": "MA-S1:P1",
                "required_facet_ids": ["facet:1"],
                "ordered_semantic_slot_ids": ["slot:transformation"],
                "required_edge_ids": ["edge:1"],
                "formula_obligation_ids": [],
            }],
        }],
    }
    assessment = {
        "content_digest": "sha256:assessment",
        "plan_digest": "sha256:plan",
        "assessments": [{
            "section_id": "MA-S1",
            "paragraph_id": "MA-S1:P1",
            "valid": valid,
            "witnessed_by_kind": {
                "facet": ["facet:1"] if valid else [],
                "slot": ["slot:transformation"] if valid else [],
                "edge": ["edge:1"] if valid else [],
            },
            "missing_by_kind": {} if valid else {"slot": ["slot:transformation"]},
        }],
    }
    trace = {
        "content_digest": "sha256:trace",
        "transaction_assessment_digest": "sha256:assessment",
        "rows": [{
            "section_id": "MA-S1",
            "paragraph_id": "MA-S1:P1",
            "terminal_state": "rendered" if valid else "rendered_invalid",
            "field_bindings": [],
        }],
    }
    callback = {"requests": []}
    if open_request:
        callback["requests"] = [{
            "request_id": "request:slot",
            "section_id": "MA-S1",
            "exact_question": "Which transformation is applied?",
            "missing_rhetorical_move": "algorithm_or_data_flow",
            "mandatory_missing_slots": ["transformation"],
            "status": "open",
        }]
    return plan, trace, assessment, {"plan_digest": "sha256:plan", "final_text_digest": "sha256:candidate"}, callback


def test_structural_exit_rejects_invalid_required_transaction() -> None:
    plan, trace, assessment, writer, callback = _structural_payloads(valid=False)
    decision = evaluate_authoring_structural_exit(
        plan_payload=plan,
        trace_payload=trace,
        assessment_payload=assessment,
        writer_payload=writer,
        callback_payload=callback,
        candidate_digest="sha256:candidate",
    )
    assert not decision.eligible
    assert "required_target_coverage_incomplete" in decision.reasons
    assert decision.invalid_paragraphs == 1


def test_structural_exit_requires_scoped_callback_for_partial_fields() -> None:
    plan, trace, assessment, writer, callback = _structural_payloads(valid=True)
    trace["rows"][0]["field_bindings"] = [{"field_name": "operation", "status": "partial"}]
    denied = evaluate_authoring_structural_exit(
        plan_payload=plan,
        trace_payload=trace,
        assessment_payload=assessment,
        writer_payload=writer,
        callback_payload=callback,
        candidate_digest="sha256:candidate",
    )
    assert not denied.eligible
    assert "unresolved_field_without_callback_request" in denied.reasons
    callback = _structural_payloads(valid=True, open_request=True)[4]
    allowed = evaluate_authoring_structural_exit(
        plan_payload=plan,
        trace_payload=trace,
        assessment_payload=assessment,
        writer_payload=writer,
        callback_payload=callback,
        candidate_digest="sha256:candidate",
    )
    assert allowed.eligible


def test_structural_exit_rejects_accepted_formula_package_not_consumed() -> None:
    plan, trace, assessment, writer, callback = _structural_payloads(valid=True)
    plan["sections"][0]["paragraphs"][0]["formula_obligation_ids"] = ["formula:1"]
    assessment["assessments"][0]["witnessed_by_kind"]["formula"] = ["formula:1"]
    formalization = {
        "sections": [{
            "section_id": "MA-S1",
            "packages": [{"package_id": "package:1"}],
            "obligation_truths": [{
                "obligation_id": "formula:1",
                "expectation": "required",
                "outcome": "rendered",
                "package_id": "package:1",
            }],
        }],
    }
    denied = evaluate_authoring_structural_exit(
        plan_payload=plan,
        trace_payload=trace,
        assessment_payload=assessment,
        writer_payload=writer,
        callback_payload=callback,
        formalization_payload=formalization,
        candidate_digest="sha256:candidate",
    )
    assert not denied.eligible
    assert any(reason.startswith("formula_packages_unconsumed:") for reason in denied.reasons)


def test_structural_exit_accepts_rhetorical_move_as_callback_target() -> None:
    plan, trace, assessment, writer, _callback = _structural_payloads(valid=True)
    callback = {"requests": [{
        "request_id": "request:move",
        "section_id": "MA-S1",
        "exact_question": "Which implementation move is missing?",
        "missing_rhetorical_move": "implementation_realization",
        "status": "open",
    }]}
    decision = evaluate_authoring_structural_exit(
        plan_payload=plan,
        trace_payload=trace,
        assessment_payload=assessment,
        writer_payload=writer,
        callback_payload=callback,
        candidate_digest="sha256:candidate",
    )
    assert decision.eligible


def test_internal_facet_id_not_emitted_as_research_search_term() -> None:
    from code2paper.agentic.writer_research_router import directed_search_terms_from_texts

    terms = directed_search_terms_from_texts(
        "facet:linear_rag_01",
        "brief:MA-S1",
        "paragraph:MA-S2:P1",
        "claim:fact-1",
        "obligation:formula-1",
        "method-unit:MU-1",
        "MA-S3",
        "How is the attention weight calculated?",
    )
    for term in terms:
        assert not term.startswith(("facet:", "brief:", "paragraph:", "claim:", "obligation:", "method-unit:", "MA-S"))
    assert any("attention weight" in term.casefold() or "attention" in term.casefold() for term in terms)


def test_semantic_missing_parts_produce_meaningful_search_terms() -> None:
    from code2paper.agentic.writer_research_router import directed_search_terms_from_texts

    terms = directed_search_terms_from_texts(
        "InfoNCE temperature scaling parameter tau",
        "facet:loss_fn",
    )
    assert "facet:loss_fn" not in terms
    assert any("temperature" in term.casefold() or "infonce" in term.casefold() for term in terms)
