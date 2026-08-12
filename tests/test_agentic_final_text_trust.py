from __future__ import annotations

from code2paper.agentic.final_text_claims import extract_final_text_claims, text_digest
from code2paper.agentic.text_evidence_validator import validate_text_evidence
from code2paper.agentic.text_evidence_validator import _numeric_tokens_supported
from code2paper.agentic.text_trace_builder import build_final_text_trace
from code2paper.agentic.trust_contracts import (
    AuthorAttestedFragment,
    AuthoringInputProjection,
    ForbiddenClaim,
    ProjectedClaim,
)
from code2paper.core.schemas import EvidenceItem, RawEvidencePack, SourceType


def _projection(*, partial: bool = False) -> AuthoringInputProjection:
    claim = ProjectedClaim(
        claim_id="C1",
        claim_text="The encoder reads configured features.",
        support_status="partial" if partial else "supported",
        direct_evidence_ids=["E1"],
        supported_fragment="The encoder reads configured features.",
        required_qualifiers=["Only configured features are read."] if partial else [],
        allowed_wording_boundary="The encoder reads configured features.",
        input_digest="sha256:claim",
    )
    return AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="Use projected claims.",
        implementation_scope="test",
        projected_claims=[claim],
        forbidden_claims=[ForbiddenClaim(claim_id="C2", reason="unsupported")],
        projection_digest="sha256:projection",
    )


def _raw(summary: str = "The encoder reads configured features from the input configuration.") -> RawEvidencePack:
    return RawEvidencePack(
        project_id="demo",
        project_root="/repo",
        evidence_items=[
            EvidenceItem(
                evidence_id="E1",
                source_type=SourceType.SOURCE,
                path="encoder.py",
                symbol="read_features",
                content_summary=summary,
                line_start=1,
                line_end=4,
                confidence=0.9,
            )
        ],
    )


def test_final_extractor_splits_compound_claims_and_ignores_discourse() -> None:
    text = (
        "# Method\n\n"
        "In this section, we describe our approach.\n\n"
        "The encoder reads configured features and the decoder returns scores.\n"
    )
    extracted = extract_final_text_claims(text, _projection())

    assert any(unit.kind == "discourse" and not unit.factual for unit in extracted.units)
    assert [claim.text for claim in extracted.atomic_claims] == [
        "The encoder reads configured features",
        "the decoder returns scores.",
    ]


def test_final_extractor_ignores_non_rendered_html_claim_metadata() -> None:
    text = (
        "# Method\n"
        "<!-- c2p: stage=ALL; evidence=E1; confidence=high -->\n"
        "The encoder reads configured features.\n"
    )

    extracted = extract_final_text_claims(text, _projection())

    assert [claim.text for claim in extracted.atomic_claims] == [
        "The encoder reads configured features.",
    ]
    assert extracted.atomic_claims[0].line_start == 3


def test_final_extractor_keeps_dotted_code_identifier_with_its_qualifier() -> None:
    text = "Under torch.no_grad, the encoder reads configured features."

    extracted = extract_final_text_claims(text, _projection())

    assert [unit.text for unit in extracted.units] == [text]
    assert [claim.text for claim in extracted.atomic_claims] == [text]


def test_final_extractor_does_not_split_on_not_equal_operator() -> None:
    """``!=`` is a code comparison operator, not a sentence boundary.

    Regression: ``sum(temp_label_list) != 1.`` was split into
    ``sum(temp_label_list) !`` and ``= 1.``, producing an orphaned
    numeric fragment that failed reverse validation.
    """
    text = "The loader calls append, when sum(temp_label_list) != 1."

    extracted = extract_final_text_claims(text, _projection())

    assert [unit.text for unit in extracted.units] == [text]
    assert [claim.text for claim in extracted.atomic_claims] == [text]
    # No orphaned ``= 1.`` fragment should appear.
    assert not any(claim.text.strip().startswith("= ") for claim in extracted.atomic_claims)


def test_final_extractor_does_not_detach_operand_after_and() -> None:
    """``and`` between formula operands must not split a factual sentence.

    Regression: ``computes the formula for num_passages and 1 when ...``
    was split at ``and``, producing an orphaned ``1 when ...`` fragment
    that failed projection matching.
    """
    text = "The module computes the formula for num_passages and 1 when self.cfg.use_dedicated_attention."

    extracted = extract_final_text_claims(text, _projection())

    assert [unit.text for unit in extracted.units] == [text]
    assert [claim.text for claim in extracted.atomic_claims] == [text]
    # No orphaned ``1 when ...`` fragment should appear.
    assert not any(
        claim.text.strip().startswith("1 ") or claim.text.strip().startswith("1\t")
        for claim in extracted.atomic_claims
    )


def test_valid_direct_evidence_claim_passes_and_builds_posthoc_trace() -> None:
    text = "The encoder reads configured features."
    projection = _projection()
    extracted = extract_final_text_claims(text, projection)
    report = validate_text_evidence(final_claims=extracted, projection=projection, raw_evidence=_raw())
    trace = build_final_text_trace(
        final_claims=extracted,
        validation=report,
        projection=projection,
        validator_report_ref="validation.json",
        projection_ref="projection.json",
    )

    assert report.status == "passed"
    assert trace.hard_gate_passed
    assert trace.input_text_digest == text_digest(text)
    assert trace.entries[0].direct_evidence_ids == ["E1"]


def test_legal_but_semantically_unrelated_evidence_is_rejected() -> None:
    text = "The encoder reads configured features."
    projection = _projection()
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=_raw("The license permits redistribution under stated legal terms."),
    )

    assert report.status == "failed"
    assert "direct_evidence_semantically_unrelated" in report.verdicts[0].deterministic_failures


def test_drifted_wording_with_related_evidence_routes_to_writer_not_packet() -> None:
    """A fragment whose wording drifted below the projection overlap is a
    Writer-wording failure; it must not be misrouted to the packet owner."""

    text = "The resulting scores are then extracted by calling scores.numpy to convert the output."
    projection = _projection()
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=_raw("np.save(path, scores.numpy())"),
    )

    assert report.status == "failed"
    failures = report.verdicts[0].deterministic_failures
    assert "no_semantically_matching_projected_claim" in failures
    assert "direct_evidence_semantically_unrelated" not in failures
    assert report.verdicts[0].repair_action == "revise_authoring_wording"


def test_paraphrased_unsupported_numeric_claim_is_rejected() -> None:
    text = "The system reduces training time by 99%."
    projection = _projection()
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=_raw(),
    )

    assert report.status == "failed"
    assert "no_semantically_matching_projected_claim" in report.verdicts[0].deterministic_failures
    assert report.verdicts[0].repair_action == "revise_authoring_wording"


def test_numeric_gate_ignores_digits_embedded_in_code_identifiers() -> None:
    assert _numeric_tokens_supported(
        "GaussianModel.get_prune_input_f15 concatenates tensors with dim=1.",
        "GaussianModel.get_prune_input_f15 concatenates tensors with dim=1.",
        _projection(),
    )


def test_unsupported_scientific_verb_cannot_bypass_factual_extraction() -> None:
    text = "Hard mining closes the optical-SAR modality gap."
    projection = _projection()
    extracted = extract_final_text_claims(text, projection)
    report = validate_text_evidence(final_claims=extracted, projection=projection, raw_evidence=_raw())

    assert extracted.units[0].factual
    assert len(extracted.atomic_claims) == 1
    assert report.status == "failed"


def test_stronger_causal_wording_cannot_cross_projection_boundary() -> None:
    text = "The encoder reads configured features and guarantees improved accuracy."
    projection = _projection()
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=_raw(),
    )

    assert report.status == "failed"
    assert any(
        "allowed_wording_boundary_exceeded" in verdict.deterministic_failures
        or "no_semantically_matching_projected_claim" in verdict.deterministic_failures
        for verdict in report.verdicts
    )


def test_partial_claim_without_required_qualifier_is_rejected() -> None:
    text = "The encoder reads configured features."
    projection = _projection(partial=True)
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=_raw(),
    )

    assert report.status == "failed"
    assert "required_qualifier_missing" in report.verdicts[0].deterministic_failures


def test_qualifier_in_sentence_prefix_satisfies_fragment_check() -> None:
    """A conditional prefix scopes the whole sentence.

    The atomic-fragment splitter breaks "When self.time_mamba is active, the
    encoder reads configured features." on the comma, detaching the qualifier
    from the matching fragment.  The qualifier check must consult the full
    sentence (unit) text, not just the fragment, or a correct conditional
    sentence is falsely rejected.
    """

    projection = AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="Use projected claims.",
        implementation_scope="test",
        projected_claims=[
            ProjectedClaim(
                claim_id="C1",
                claim_text="The encoder reads configured features.",
                support_status="supported",
                direct_evidence_ids=["E1"],
                supported_fragment="The encoder reads configured features.",
                required_qualifiers=["self.time_mamba is active"],
                allowed_wording_boundary="The encoder reads configured features.",
                input_digest="sha256:claim",
            ),
        ],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )
    text = "When self.time_mamba is active, the encoder reads configured features."
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=_raw(),
    )

    assert report.status == "passed"
    assert not any(
        "required_qualifier_missing" in v.deterministic_failures for v in report.verdicts
    )


def test_projection_matching_does_not_union_qualifiers_from_lower_scoring_claims() -> None:
    unconditional = ProjectedClaim(
        claim_id="C-unconditional",
        claim_text="The model loads self_features_dc and self_features_rest weights.",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment="The model loads weights self_features_dc and self_features_rest.",
        required_qualifiers=[],
        allowed_wording_boundary="The model loads weights self_features_dc and self_features_rest.",
        input_digest="sha256:unconditional",
    )
    conditional = ProjectedClaim(
        claim_id="C-conditional",
        claim_text="GaussianModel.get_features_dc returns self_features_dc.",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment="GaussianModel.get_features_dc returns self_features_dc.",
        required_qualifiers=["knn_method in ['ivf', 'brute_force']"],
        allowed_wording_boundary="GaussianModel.get_features_dc returns self_features_dc.",
        input_digest="sha256:conditional",
    )
    projection = AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="test",
        implementation_scope="test",
        projected_claims=[unconditional, conditional],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )
    text = "The model loads weights self_features_dc and self_features_rest."
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=_raw("The model loads self_features_dc and self_features_rest weights."),
    )

    assert report.status == "passed"
    assert report.verdicts[0].matched_projection_claim_ids == ["C-unconditional"]


def test_author_attested_fragment_is_caveated_without_repository_evidence() -> None:
    fragment = AuthorAttestedFragment(
        fragment_id="author:goal",
        supported_fragment="The method targets view-agnostic importance scores.",
        allowed_wording_boundary="The method targets view-agnostic importance scores.",
        source_ref="callback:author-goal",
        input_digest="sha256:author-goal",
    )
    projection = _projection().model_copy(update={"author_attested_fragments": [fragment]})
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(fragment.supported_fragment, projection),
        projection=projection,
        raw_evidence=RawEvidencePack(project_id="demo", project_root="."),
    )

    assert report.status == "passed"
    assert report.verdicts[0].status == "caveated"
    assert report.verdicts[0].direct_evidence_ids == []
    assert report.verdicts[0].matched_projection_claim_ids == ["author:goal"]


def test_author_attested_fragment_cannot_absorb_new_factual_tokens() -> None:
    fragment = AuthorAttestedFragment(
        fragment_id="author:goal",
        supported_fragment="The method targets view-agnostic importance scores.",
        allowed_wording_boundary="The method targets view-agnostic importance scores.",
        source_ref="callback:author-goal",
        input_digest="sha256:author-goal",
    )
    projection = _projection().model_copy(update={"author_attested_fragments": [fragment]})
    text = "The method targets view-agnostic importance scores, improving accuracy."
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=RawEvidencePack(project_id="demo", project_root="."),
    )

    assert report.status == "failed"
    assert report.verdicts[0].status == "unsupported"


def test_trace_rejects_report_bound_to_different_final_text_digest() -> None:
    projection = _projection()
    extracted = extract_final_text_claims("The encoder reads configured features.", projection)
    report = validate_text_evidence(final_claims=extracted, projection=projection, raw_evidence=_raw())
    stale = report.model_copy(update={"input_text_digest": "sha256:stale"})
    trace = build_final_text_trace(
        final_claims=extracted,
        validation=stale,
        projection=projection,
        validator_report_ref="validation.json",
        projection_ref="projection.json",
    )

    assert not trace.hard_gate_passed
    assert "validator_text_digest_mismatch" in trace.failures


def test_semantic_verifier_rejection_returns_precise_authoring_revision() -> None:
    text = "The encoder reads configured features to resolve training settings."
    projection = _projection()
    extracted = extract_final_text_claims(text, projection)
    report = validate_text_evidence(
        final_claims=extracted,
        projection=projection,
        raw_evidence=_raw(),
        semantic_verifier=lambda _payload: {
            "status": "unsupported",
            "rationale": "The resolution outcome is not shown.",
            "supported_fragment": "The encoder reads configured features.",
            "unsupported_fragment": "to resolve training settings",
        },
        max_semantic_verifier_calls=1,
    )

    verdict = report.verdicts[0]
    assert verdict.repair_action == "revise_authoring_from_verifier_fragments"
    assert verdict.supported_fragment == "The encoder reads configured features."
    assert verdict.unsupported_fragment == "to resolve training settings"


def test_numeric_and_formula_tokens_in_qualifiers_are_exempt_from_evidence_check() -> None:
    """Numbers and formulas inside authorized qualifiers are already validated
    by ``_qualifier_preserved``; they must not be re-checked against direct
    evidence.

    Regression: ``current_layer_num == 0`` in a qualifier caused
    ``numeric_token_not_in_direct_evidence`` and
    ``formula_not_in_direct_evidence`` failures because the number ``0`` and
    the ``==`` formula did not appear in the narrow single-line evidence
    excerpt, even though the qualifier itself was authorized by the
    projection.
    """
    claim = ProjectedClaim(
        claim_id="C-qual",
        claim_text="The module computes features when current_layer_num == 0.",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment="The module computes features when current_layer_num == 0.",
        required_qualifiers=["current_layer_num == 0"],
        allowed_wording_boundary="The module computes features when current_layer_num == 0.",
        input_digest="sha256:qual",
    )
    projection = AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="test",
        implementation_scope="test",
        projected_claims=[claim],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )
    text = "The module computes features when current_layer_num == 0."
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=_raw("features = compute()"),
    )

    assert report.status == "passed"
    assert not any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        or "formula_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_formula_tokens_in_authorized_projection_fragments_are_exempt() -> None:
    """Code expressions like ``dim=1`` in the projection's
    ``supported_fragment`` are pre-authorized wording, not free-form formulas
    that require separate direct-evidence lookup.

    Regression: ``unsqueeze(dim=1)`` in the claim text was matched by the
    formula regex and checked against a narrow evidence excerpt that did not
    contain that exact expression, causing ``formula_not_in_direct_evidence``
    even though the projection authorized the wording.
    """
    claim = ProjectedClaim(
        claim_id="C-frag",
        claim_text="The module reshapes node_time_intervals.unsqueeze(dim=1).",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment="The module reshapes node_time_intervals.unsqueeze(dim=1).",
        required_qualifiers=[],
        allowed_wording_boundary="The module reshapes node_time_intervals.unsqueeze(dim=1).",
        input_digest="sha256:frag",
    )
    projection = AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="test",
        implementation_scope="test",
        projected_claims=[claim],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )
    text = "The module reshapes node_time_intervals.unsqueeze(dim=1)."
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(text, projection),
        projection=projection,
        raw_evidence=_raw("out = layer(x)"),
    )

    assert not any(
        "formula_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_keyword_arguments_are_not_treated_as_formulas() -> None:
    """Python keyword arguments like ``dim=1``, ``node_ids=node_ids`` are not
    mathematical formulas and must not trigger ``formula_not_in_direct_evidence``.

    Regression: ``unsqueeze(dim=1)`` in claim text was matched by the formula
    regex ``[A-Za-z]\\s*=\\s*[^,.;]+`` (matching ``m=1`` from ``dim=1``),
    causing a false ``formula_not_in_direct_evidence`` failure because the
    narrow evidence excerpt did not contain that exact substring.
    """
    claim = ProjectedClaim(
        claim_id="C-kwarg",
        claim_text="The module calls torch.fft.rfft, hidden_states, n=self.max_input_length, dim=1, norm='forward'.",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment="The module calls torch.fft.rfft, hidden_states, n=self.max_input_length, dim=1, norm='forward'.",
        required_qualifiers=[],
        allowed_wording_boundary="The module calls torch.fft.rfft, hidden_states, n=self.max_input_length, dim=1, norm='forward'.",
        input_digest="sha256:kwarg",
    )
    projection = AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="test",
        implementation_scope="test",
        projected_claims=[claim],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )
    text = "The module calls torch.fft.rfft, hidden_states, n=self.max_input_length, dim=1, norm='forward'."
    extracted = extract_final_text_claims(text, projection)
    # Verify no formula risk marker is set for keyword arguments
    for unit in extracted.units:
        assert "formula" not in unit.high_risk_markers, f"Keyword argument triggered formula marker: {unit.text}"
    report = validate_text_evidence(
        final_claims=extracted,
        projection=projection,
        raw_evidence=_raw("out = fft(x)"),
    )
    assert not any(
        "formula_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_code_list_assignment_is_not_treated_as_formula() -> None:
    """Code patterns like ``Method.name = ["config_value"]`` are not
    mathematical formulas and must not trigger ``formula_not_in_direct_evidence``.

    Regression: ``get_passage_positional_encoding = ["self.cfg.d_model"]`` was
    matched by the formula regex (spaces around ``=``), extracting a truncated
    ``g=["self`` that failed evidence lookup.
    """
    claim = ProjectedClaim(
        claim_id="C-list",
        claim_text="EBCarRerankerHybridAttention.get_passage_positional_encoding = [\"self.cfg.d_model\"].",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment="EBCarRerankerHybridAttention.get_passage_positional_encoding = [\"self.cfg.d_model\"].",
        required_qualifiers=[],
        allowed_wording_boundary="EBCarRerankerHybridAttention.get_passage_positional_encoding = [\"self.cfg.d_model\"].",
        input_digest="sha256:list",
    )
    projection = AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="test",
        implementation_scope="test",
        projected_claims=[claim],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )
    text = "EBCarRerankerHybridAttention.get_passage_positional_encoding = [\"self.cfg.d_model\"]."
    extracted = extract_final_text_claims(text, projection)
    for unit in extracted.units:
        assert "formula" not in unit.high_risk_markers, f"List assignment triggered formula marker: {unit.text}"
    report = validate_text_evidence(
        final_claims=extracted,
        projection=projection,
        raw_evidence=_raw("def get_passage_positional_encoding(): pass"),
    )
    assert not any(
        "formula_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def _comparison_projection(expression: str) -> AuthoringInputProjection:
    claim = ProjectedClaim(
        claim_id="C-cmp",
        claim_text=f"The guard checks count {expression}.",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment=f"The guard checks count {expression}.",
        required_qualifiers=[],
        allowed_wording_boundary=f"The guard checks count {expression}.",
        input_digest="sha256:cmp",
    )
    return AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="test",
        implementation_scope="test",
        projected_claims=[claim],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )


def test_comparator_threshold_tampering_gt_999_rejected() -> None:
    """A tampered comparison threshold (``count > 0`` -> ``count > 999``)
    must be rejected.  Regression: the ``[<>!=]=?\\s*\\d+`` regex deleted
    every threshold, so both ``count > 0`` and ``count > 999`` reduced to
    an empty numeric-token set and passed."""
    projection = _comparison_projection("> 0")
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count > 999.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if count > 0: process()"),
    )
    assert report.status == "failed"
    assert any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_comparator_threshold_tampering_ne_999_rejected() -> None:
    """A tampered ``!=`` threshold (``count != 0`` -> ``count != 999``) must
    be rejected.  Same regression class as ``>``: the threshold digit was
    deleted by regex, so ``!= 0`` and ``!= 999`` were indistinguishable."""
    projection = _comparison_projection("!= 0")
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count != 999.", projection
        ),
        projection=projection,
        raw_evidence=_raw("assert count != 0"),
    )
    assert report.status == "failed"
    assert any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_authorized_comparison_threshold_passes() -> None:
    """An authorized comparison expression (``count > 0`` in both the
    projection and the final text) must pass -- the fix must not over-block
    legitimate conditional thresholds."""
    projection = _comparison_projection("> 0")
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count > 0.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if count > 0: process()"),
    )
    assert not any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_operator_mutation_is_rejected() -> None:
    """Changing only the comparison operator (``count > 0`` -> ``count >= 0``)
    must fail.  Regression: the comparison unit check compares the complete
    ``var + operator + threshold`` expression, so an operator-only mutation
    can no longer ride on an authorized threshold digit."""
    projection = _comparison_projection("> 0")
    for tampered in (">= 0", "<= 0", "< 0", "== 0"):
        report = validate_text_evidence(
            final_claims=extract_final_text_claims(
                f"The guard checks count {tampered}.", projection
            ),
            projection=projection,
            raw_evidence=_raw("if count > 0: process()"),
        )
        assert report.status == "failed", f"{tampered} must be rejected"
        assert any(
            "numeric_token_not_in_direct_evidence" in v.deterministic_failures
            for v in report.verdicts
        ), f"{tampered} must fail the numeric gate"


def test_value_mutation_away_from_authorized_threshold_is_rejected() -> None:
    """Changing only the threshold value (``count > 0`` -> ``count > 5``) must
    fail even when the operator matches.  The exact authorized predicate/value
    pair is the only allowed form."""
    projection = _comparison_projection("> 0")
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count > 5.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if count > 0: process()"),
    )
    assert report.status == "failed"
    assert any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def _comparison_collision_projection(expression: str, variable: str) -> AuthoringInputProjection:
    claim = ProjectedClaim(
        claim_id="C-cmp",
        claim_text=f"The guard checks {variable} {expression}.",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment=f"The guard checks {variable} {expression}.",
        required_qualifiers=[],
        allowed_wording_boundary=f"The guard checks {variable} {expression}.",
        input_digest="sha256:cmp",
    )
    return AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="test",
        implementation_scope="test",
        projected_claims=[claim],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )


def test_comparison_variable_suffix_collision_is_rejected() -> None:
    """An authorized ``discount > 0`` must not authorize ``count > 0``.

    Regression: the old check compared whitespace variants of the whole
    expression with substring membership, so ``count > 0`` matched inside
    ``discount > 0`` and a tampered variable suffix passed."""
    projection = _comparison_collision_projection("> 0", "discount")
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count > 0.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if discount > 0: process()"),
    )
    assert report.status == "failed"
    assert any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_comparison_value_prefix_collision_is_rejected() -> None:
    """An authorized ``count > 10`` must not authorize ``count > 1``.

    Regression: the substring check let the shorter value ``1`` match inside
    the authorized ``10``, so a value-prefix tamper passed."""
    projection = _comparison_collision_projection("> 10", "count")
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count > 1.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if count > 10: process()"),
    )
    assert report.status == "failed"
    assert any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_comparison_signed_threshold_mutation_is_rejected() -> None:
    """A signed threshold (``count > -1``) is an exact value: it must not
    authorize ``count > 1`` and must still pass when copied exactly.

    Regression: the tuple regex only matched unsigned integers, so an
    operator/value mutation that flipped the sign evaded the exact-predicate
    check."""
    projection = _comparison_collision_projection("> -1", "count")
    tampered = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count > 1.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if count > -1: process()"),
    )
    assert tampered.status == "failed"
    assert any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in tampered.verdicts
    )
    exact = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count > -1.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if count > -1: process()"),
    )
    assert not any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in exact.verdicts
    )


def test_comparison_scientific_threshold_is_exact() -> None:
    """A scientific threshold (``count > 1e5``) is an exact value: the
    authorized form passes and a value-prefix tamper (``count > 1``) fails."""
    projection = _comparison_collision_projection("> 1e5", "count")
    exact = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count > 1e5.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if count > 1e5: process()"),
    )
    assert not any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in exact.verdicts
    )
    tampered = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks count > 1.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if count > 1e5: process()"),
    )
    assert tampered.status == "failed"
    assert any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in tampered.verdicts
    )


def test_indexed_operand_comparison_is_exact() -> None:
    """An indexed operand comparison (``tensor.shape[0] > 1``) is verified as
    an exact identifier/operator/value unit: the authorized form passes and
    operator/value mutations fail.

    Regression: the comparison grammar accepted only plain/dotted identifiers,
    so ``tensor.shape[0] >= 1`` produced no claim tuple and fell through to
    loose standalone numeric membership where both digits were authorized."""
    projection = _comparison_collision_projection("> 1", "tensor.shape[0]")
    exact = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks tensor.shape[0] > 1.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if tensor.shape[0] > 1: process()"),
    )
    assert not any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in exact.verdicts
    )
    for tampered in (">= 1", "> 2", "< 1", "== 1"):
        report = validate_text_evidence(
            final_claims=extract_final_text_claims(
                f"The guard checks tensor.shape[0] {tampered}.", projection
            ),
            projection=projection,
            raw_evidence=_raw("if tensor.shape[0] > 1: process()"),
        )
        assert report.status == "failed", f"{tampered} must be rejected"
        assert any(
            "numeric_token_not_in_direct_evidence" in v.deterministic_failures
            for v in report.verdicts
        ), f"{tampered} must fail the numeric gate"


def test_indexed_list_index_comparison_is_exact() -> None:
    """A list-indexed operand (``counts[i] >= 1``) is an exact comparison
    unit: authorized passes, operator/value mutation fails."""
    projection = _comparison_collision_projection(">= 1", "counts[i]")
    exact = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks counts[i] >= 1.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if counts[i] >= 1: process()"),
    )
    assert not any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in exact.verdicts
    )
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The guard checks counts[i] > 1.", projection
        ),
        projection=projection,
        raw_evidence=_raw("if counts[i] >= 1: process()"),
    )
    assert report.status == "failed"
    assert any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_unparsed_comparison_shape_fails_closed() -> None:
    """A comparison-shaped expression whose left-hand operand the exact parser
    cannot represent must fail closed instead of degrading to loose numeric
    membership (plan §3.1.2: every comparison threshold is an exact
    predicate/value unit)."""
    from code2paper.agentic.text_evidence_validator import _numeric_tokens_supported

    projection = _projection()
    supported = _numeric_tokens_supported(
        "The guard checks count > 0.",
        "if count > 0: process()",
        projection,
    )
    assert supported
    unsupported = _numeric_tokens_supported(
        "The guard checks $x$ > 1.",
        "if $x$ > 1: process()",
        projection,
    )
    assert not unsupported


def test_short_factual_sentence_with_number_is_checked() -> None:
    """A short sentence (<=4 tokens) carrying a numeric risk after stripping
    ordinal labels is fail-closed factual.  Regression: ``Loader reads 999
    files.`` was classified non-factual because ``reads`` is not in the
    closed factual-verb set, so the tampered ``999`` escaped reverse
    validation (checked_factual_claims=0 -> passed)."""
    projection = _projection()
    extracted = extract_final_text_claims("Loader reads 999 files.", projection)
    assert extracted.units[0].factual
    assert len(extracted.atomic_claims) >= 1


def test_short_sentence_unsupported_value_fails_reverse_validation() -> None:
    """A tampered value in a short factual sentence must fail reverse
    validation, not merely be extracted.  ``Loader reads 999 files.`` is
    extracted as factual and the unsupported ``999`` value is rejected."""
    claim = ProjectedClaim(
        claim_id="C-loader",
        claim_text="Loader reads 1 file.",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment="Loader reads 1 file.",
        required_qualifiers=[],
        allowed_wording_boundary="Loader reads 1 file.",
        input_digest="sha256:loader",
    )
    projection = AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="test",
        implementation_scope="test",
        projected_claims=[claim],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )
    report = validate_text_evidence(
        final_claims=extract_final_text_claims("Loader reads 999 files.", projection),
        projection=projection,
        raw_evidence=_raw("loader = load(1)"),
    )
    assert report.status == "failed"
    assert report.checked_factual_claims >= 1
    assert any(
        "numeric_token_not_in_direct_evidence" in v.deterministic_failures
        for v in report.verdicts
    )


def test_equation_meta_description_sentence_is_rejected() -> None:
    """A Writer meta-description sentence about an equation (``The
    displayed expression is equivalent to the selected code operations for
    equation:...``) is extracted as factual and fails reverse validation.

    Regression: the live RAP Writer emitted this sentence next to the
    authorized equation expression ``x * y``; the validator must not accept
    it just because the section also contains anchored claims."""
    projection = _projection()
    text = (
        "The module computes features.\n"
        "The displayed expression is equivalent to the selected code "
        "operations for equation:fact-node:24ae0d974a7ec4f4."
    )
    extracted = extract_final_text_claims(text, projection)
    meta_units = [
        unit for unit in extracted.units
        if "displayed expression" in unit.text
    ]
    assert meta_units and meta_units[0].factual
    report = validate_text_evidence(
        final_claims=extracted,
        projection=projection,
        raw_evidence=_raw(),
    )
    assert report.status == "failed"
    assert any(
        "no_semantically_matching_projected_claim" in v.deterministic_failures
        for v in report.verdicts
    )


def test_move_name_recap_sentence_is_rejected() -> None:
    """A Writer recap sentence that names rhetorical moves (``The
    implementation stage 1 begins with the mechanism overview and
    implementation realization``) is extracted as factual and fails reverse
    validation.

    Regression: live RAP MA-S5 opened with this organization recap instead
    of an anchored sentence; the validator must reject it as a new
    unsupported claim."""
    projection = _projection()
    text = (
        "The implementation stage 1 begins with the mechanism overview and "
        "implementation realization.\n"
        "The module computes features."
    )
    extracted = extract_final_text_claims(text, projection)
    recap_units = [
        unit for unit in extracted.units if "mechanism overview" in unit.text
    ]
    assert recap_units and recap_units[0].factual
    report = validate_text_evidence(
        final_claims=extracted,
        projection=projection,
        raw_evidence=_raw(),
    )
    assert report.status == "failed"
    assert any(
        "no_semantically_matching_projected_claim" in v.deterministic_failures
        for v in report.verdicts
    )


def test_ordinal_label_remains_non_factual() -> None:
    """An ordinal label (``Implementation stage 1``) stays non-factual after
    the short-sentence fix: the ordinal label is stripped, leaving no risk
    marker, and ``Implementation`` is not a factual verb."""
    projection = _projection()
    extracted = extract_final_text_claims("Implementation stage 1", projection)
    assert not extracted.units[0].factual


def test_short_nonallowlisted_predicate_is_extracted_and_rejected() -> None:
    """A short predicate whose verb is absent from every allowlist (``Cache
    stores embeddings.``) is extracted as factual and fails reverse
    validation.

    Regression: the token-count/verb-allowlist classification treated any
    sentence with at most four tokens and no allowlisted verb as a label or
    discourse, so ``stores`` disappeared from validation and an unsupported
    short predicate silently passed (checked_factual_claims=0)."""
    projection = _projection()
    extracted = extract_final_text_claims("Cache stores embeddings.", projection)
    assert extracted.units[0].factual
    assert extracted.units[0].kind == "sentence"
    assert len(extracted.atomic_claims) >= 1
    report = validate_text_evidence(
        final_claims=extracted,
        projection=projection,
        raw_evidence=_raw(),
    )
    assert report.status == "failed"
    assert report.checked_factual_claims >= 1
    assert any(
        "no_semantically_matching_projected_claim" in v.deterministic_failures
        for v in report.verdicts
    )


def test_short_discourse_without_prefix_is_factual() -> None:
    """Token count alone never makes a sentence discourse: only an explicit
    discourse prefix does.  ``Cache stores embeddings.`` has no prefix, so it
    must not be classified as discourse merely because it is short."""
    projection = _projection()
    extracted = extract_final_text_claims("Cache stores embeddings.", projection)
    assert extracted.units[0].kind != "discourse"


def test_discourse_prefix_cannot_hide_predicate_suffix() -> None:
    """A discourse prefix must not authorize factual suffix content: ``Next,
    cache stores embeddings.`` is extracted as factual and rejected, even
    though the sentence starts with the ``next`` discourse prefix.

    Regression: the previous prefix-only discourse check exempted any text
    starting with ``next``/``finally``/etc. unless it carried a risk marker
    or an allowlisted factual hint, so the short predicate disappeared
    because ``stores`` is absent from the hint list."""
    projection = _projection()
    text = "Next, cache stores embeddings."
    extracted = extract_final_text_claims(text, projection)
    assert extracted.units[0].kind != "discourse"
    assert extracted.units[0].factual
    assert len(extracted.atomic_claims) >= 1
    report = validate_text_evidence(
        final_claims=extracted,
        projection=projection,
        raw_evidence=_raw(),
    )
    assert report.status == "failed"
    assert report.checked_factual_claims >= 1
    assert any(
        "no_semantically_matching_projected_claim" in v.deterministic_failures
        for v in report.verdicts
    )


def test_exact_discourse_only_unit_remains_non_factual() -> None:
    """A complete unit that is demonstrably discourse-only (``Next.``,
    ``In this section, we describe our approach.``) stays non-factual while a
    prefix-plus-predicate unit does not."""
    projection = _projection()
    for text in ("Next.", "In this section, we describe our approach."):
        extracted = extract_final_text_claims(text, projection)
        assert extracted.units[0].kind == "discourse"
        assert not extracted.units[0].factual


def test_configuration_assignment_without_risk_is_factual_and_rejected_if_unsupported() -> None:
    """A non-numeric configuration-assignment sentence (``The configuration X
    is set to Y``) is extracted as factual and fails reverse validation when
    no projected claim authorizes it.

    Regression: the previous ``_CONFIGURATION_LABEL`` bypass forced such
    sentences non-factual whenever no numeric/formula marker existed, so the
    final reverse validator never saw an unsupported ``args.ply_path``
    statement.  There is no configuration-authority lane in
    ``AuthoringInputProjection``, so unsupported configuration prose must be
    extracted and rejected like any other claim."""
    projection = _projection()
    extracted = extract_final_text_claims(
        'The configuration `prune_pure_feature` is set to `["args.ply_path"]` '
        "to specify the input point cloud file path.",
        projection,
    )
    assert extracted.units[0].factual
    assert len(extracted.atomic_claims) >= 1
    report = validate_text_evidence(
        final_claims=extracted,
        projection=projection,
        raw_evidence=_raw(),
    )
    assert report.status == "failed"
    assert any(
        "no_semantically_matching_projected_claim" in v.deterministic_failures
        for v in report.verdicts
    )


def test_authorized_configuration_sentence_passes_reverse_validation() -> None:
    """An authorized configuration sentence that is represented through the
    projected-claim/evidence contract passes reverse validation.  This is the
    exact positive counterpart: no new authority lane is invented; the
    configuration wording is carried by a projected claim with direct code
    evidence."""
    claim = ProjectedClaim(
        claim_id="C-config",
        claim_text="The configuration prune_pure_feature is set to args.ply_path.",
        support_status="supported",
        direct_evidence_ids=["E1"],
        supported_fragment=(
            "The configuration prune_pure_feature is set to args.ply_path."
        ),
        required_qualifiers=[],
        allowed_wording_boundary=(
            "The configuration prune_pure_feature is set to args.ply_path."
        ),
        input_digest="sha256:config",
    )
    projection = AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="test",
        implementation_scope="test",
        projected_claims=[claim],
        forbidden_claims=[],
        projection_digest="sha256:projection",
    )
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The configuration prune_pure_feature is set to args.ply_path.",
            projection,
        ),
        projection=projection,
        raw_evidence=_raw("args.ply_path = Path(...)"),
    )
    assert report.status == "passed"
    assert report.unsupported_claims == 0


def test_configuration_assignment_with_numeric_risk_is_factual() -> None:
    """A configuration sentence that carries a numeric risk (e.g.
    ``defaults to 0.001``) is still fail-closed factual — the number must
    be validated against authorized sources."""
    projection = _projection()
    extracted = extract_final_text_claims(
        "The parameter `learning_rate` defaults to 0.001 for the optimizer.",
        projection,
    )
    assert extracted.units[0].factual


def test_empty_evidence_excerpt_is_explicit_failure() -> None:
    """When direct evidence ids exist but the excerpt is empty (a D1
    evidence extraction gap), the claim must fail explicitly rather than
    slip through when no other gate fires.  Regression: the empty-excerpt
    branch skipped numeric/formula checks and relied on other gates to
    indirectly block the claim."""
    projection = _projection()
    raw = RawEvidencePack(
        project_id="demo",
        project_root="/nonexistent-repo",
        evidence_items=[
            EvidenceItem(
                evidence_id="E1",
                source_type=SourceType.SOURCE,
                path="notes.md",
                symbol="read_features",
                content_summary="narrative notes about the encoder",
                line_start=1,
                line_end=4,
                confidence=0.9,
            ),
        ],
    )
    report = validate_text_evidence(
        final_claims=extract_final_text_claims(
            "The encoder reads configured features.", projection
        ),
        projection=projection,
        raw_evidence=raw,
    )
    assert report.status == "failed"
    assert any(
        "direct_evidence_excerpt_empty" in v.deterministic_failures
        for v in report.verdicts
    )
