from code2paper.agentic.method_proposition_models import MethodPropositionV1
from code2paper.agentic.proposition_semantic_aligner import align_sentence_to_section_propositions


def _proposition(**updates):
    values = dict(
        proposition_id="MP-1", origin="repository_evidence", evidence_lane="repository_verified",
        may_enter_verified=True, reader_subject="per-primitive descriptor",
        transformation="combines color and scale attributes", immutable_numeric_tokens=("15",),
    )
    values.update(updates)
    return MethodPropositionV1(**values)


def test_closed_aligner_accepts_paraphrase_only_with_preserved_constraints():
    result = align_sentence_to_section_propositions(
        "We form a 15-dimensional descriptor for each primitive by joining its color and scale attributes.",
        [_proposition()],
        semantic_aligner=lambda _payload: {
            "status": "matched", "matched_proposition_ids": ["MP-1"],
            "preserved_roles": ["subject", "transformation"], "missing_roles": [],
        },
    )
    assert result.status == "matched"


def test_closed_aligner_rejects_out_of_set_id_and_missing_number():
    unknown = align_sentence_to_section_propositions(
        "The descriptor joins color and scale attributes.", [_proposition()],
        semantic_aligner=lambda _payload: {
            "status": "matched", "matched_proposition_ids": ["MP-OTHER"],
            "preserved_roles": ["subject", "transformation"], "missing_roles": [],
        },
    )
    assert unknown.status == "no_match"


def test_candidate_intent_never_matches_without_visible_caveat():
    candidate = _proposition(
        origin="author_intent", evidence_lane="author_intent_unverified",
        may_enter_verified=False, requires_caveat=True, immutable_numeric_tokens=(),
    )
    result = align_sentence_to_section_propositions(
        "The per-primitive descriptor combines color and scale attributes.", [candidate],
    )
    assert result.status != "matched"


def test_exact_overlap_cannot_hide_negation_or_strength_expansion():
    proposition = _proposition(immutable_numeric_tokens=())
    negated = align_sentence_to_section_propositions(
        "The per-primitive descriptor does not combine color and scale attributes.",
        [proposition],
    )
    performance = align_sentence_to_section_propositions(
        "The per-primitive descriptor combines color and scale attributes and improves accuracy.",
        [proposition],
    )

    assert negated.status == "no_match"
    assert performance.status == "no_match"
    assert "authority strength" in negated.rationale


def test_zero_lexical_overlap_still_reaches_bounded_closed_semantic_owner():
    seen = []
    proposition = _proposition(
        immutable_numeric_tokens=(),
        reader_subject="input representation",
        transformation="is consumed by the encoder",
    )
    result = align_sentence_to_section_propositions(
        "Latent vectors enter the feature extractor.",
        [proposition],
        semantic_aligner=lambda payload: seen.append(payload) or {
            "status": "matched", "matched_proposition_ids": ["MP-1"],
            "preserved_roles": ["subject", "transformation"], "missing_roles": [],
        },
    )

    assert seen
    assert result.status == "matched"


def test_semantic_match_rejects_operand_condition_and_comparison_mutations():
    proposition = _proposition(
        immutable_numeric_tokens=(),
        inputs=("color", "scale"), outputs=("descriptor",),
        conditions=("when count > 0",),
        required_qualifiers=("when count > 0",),
    )
    owner = lambda _payload: {
        "status": "matched", "matched_proposition_ids": ["MP-1"],
        "preserved_roles": ["subject", "transformation"], "missing_roles": [],
    }

    changed_operand = align_sentence_to_section_propositions(
        "When count > 0, the descriptor combines color and opacity attributes.",
        [proposition], semantic_aligner=owner,
    )
    missing_condition = align_sentence_to_section_propositions(
        "The descriptor combines color and scale attributes.",
        [proposition], semantic_aligner=owner,
    )
    changed_operator = align_sentence_to_section_propositions(
        "When count >= 0, the descriptor combines color and scale attributes.",
        [proposition], semantic_aligner=owner,
    )

    assert changed_operand.status != "matched"
    assert missing_condition.status != "matched"
    assert changed_operator.status != "matched"
