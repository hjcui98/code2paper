from code2paper.llm.writer_section_repair import (
    assess_writer_section_progress,
    build_writer_section_repair_packet,
    repair_is_monotonic,
)


def _view():
    return {
        "positive_propositions": [{
            "proposition_id": "MP-1",
            "reader_subject": "per-primitive descriptor",
            "transformation": "combines color and scale attributes",
        }],
        "caveated_propositions": [{
            "proposition_id": "MP-2",
            "intended_subject": "deployment path",
            "intended_transformation": "avoids rendering",
        }],
        "immutable_constraints": [{
            "proposition_id": "MP-1",
            "required_qualifiers": [],
            "required_numeric_tokens": ["15"],
            "formula_renderings": [],
            "configuration_values": [],
        }],
        "required_proposition_ids": ["MP-1", "MP-2"],
    }


def test_substantive_caveated_revision_monotonically_improves_placeholder():
    incumbent, failures = assess_writer_section_progress(
        "## Method\n\nPending confirmation, we aim to explain deployment.", writer_view=_view()
    )
    candidate, candidate_failures = assess_writer_section_progress(
        "## Method\n\nThe intended per-primitive descriptor combines 15 color and scale attributes. "
        "Pending repository confirmation, the deployment path is intended to avoid rendering.",
        writer_view=_view(),
    )
    assert "empty_candidate_promise" in failures
    assert candidate.validated_propositions == 2
    assert repair_is_monotonic(incumbent, candidate)
    assert "required_propositions_unrendered" not in candidate_failures


def test_revision_that_drops_immutable_number_is_rejected():
    incumbent, _ = assess_writer_section_progress(
        "The per-primitive descriptor combines 15 color and scale attributes.", writer_view=_view()
    )
    candidate, _ = assess_writer_section_progress(
        "The per-primitive descriptor combines color and scale attributes.", writer_view=_view()
    )
    assert candidate.constraint_failures > incumbent.constraint_failures
    assert not repair_is_monotonic(incumbent, candidate)


def test_uncaveated_candidate_proposition_is_highest_priority_unsafe():
    unsafe, failures = assess_writer_section_progress(
        "The deployment path avoids rendering.", writer_view=_view()
    )
    safe, _ = assess_writer_section_progress(
        "Pending repository confirmation, the deployment path is intended to avoid rendering.",
        writer_view=_view(),
    )
    assert "candidate_proposition_missing_visible_caveat" in failures
    assert unsafe.unsafe_uncaveated_positives > safe.unsafe_uncaveated_positives
    assert repair_is_monotonic(unsafe, safe)


def test_typed_repair_packet_carries_exact_missing_constraints_and_spans():
    text = (
        "The deployment path avoids rendering. self.model.forward(x) returns score, "
        "then self.model.output_head(score) returns final_score."
    )
    progress, failures = assess_writer_section_progress(text, writer_view=_view())
    packet = build_writer_section_repair_packet(
        section_id="MA-S4", attempt=1, incumbent_text=text,
        writer_view=_view(), progress=progress, failures=failures,
    )

    assert packet.section_id == "MA-S4"
    assert "MP-1" in packet.missing_proposition_ids
    assert packet.caveat_failures
    assert packet.style_failures
    assert any(
        item.constraint_kind == "numeric" and item.required_value == "15"
        for item in packet.numeric_formula_failures
    )
    assert all(item.char_end > item.char_start for item in packet.style_failures)


def test_typed_repair_packet_marks_unauthorized_performance_language():
    text = (
        "The per-primitive descriptor combines 15 color and scale attributes "
        "and significantly improves performance."
    )
    progress, failures = assess_writer_section_progress(text, writer_view=_view())
    packet = build_writer_section_repair_packet(
        section_id="MA-S2", attempt=1, incumbent_text=text,
        writer_view=_view(), progress=progress, failures=failures,
    )

    assert "unsupported_authority_language" in failures
    assert packet.unsupported_spans
    assert packet.unsupported_spans[0].text == "significantly improves"


def test_repair_packet_lists_missing_primary_concept_and_formula() -> None:
    progress, failures = assess_writer_section_progress(
        "## Method\n\nA padding check rejects empty batches.",
        writer_view={
            "positive_concepts": [{
                "concept_key": "CK-CORE",
                "method_subject": "hybrid attention",
                "operation": "mixes token and graph context",
            }],
            "required_concept_keys": ["CK-CORE"],
            "formula_obligations": [{
                "obligation_id": "formula:equation:loss",
                "outcome": "unresolved",
            }],
            "positive_propositions": [],
            "caveated_propositions": [],
            "required_proposition_ids": [],
            "immutable_constraints": [],
        },
    )
    packet = build_writer_section_repair_packet(
        section_id="MA-S1",
        attempt=1,
        incumbent_text="## Method\n\nA padding check rejects empty batches.",
        writer_view={
            "positive_concepts": [{
                "concept_key": "CK-CORE",
                "method_subject": "hybrid attention",
                "operation": "mixes token and graph context",
            }],
            "required_concept_keys": ["CK-CORE"],
            "formula_obligations": [{
                "obligation_id": "formula:equation:loss",
                "outcome": "unresolved",
            }],
            "positive_propositions": [],
            "caveated_propositions": [],
            "required_proposition_ids": [],
            "immutable_constraints": [],
        },
        progress=progress,
        failures=failures,
    )
    assert "CK-CORE" in packet.missing_concept_keys
    assert "formula:equation:loss" in packet.missing_formula_witnesses
