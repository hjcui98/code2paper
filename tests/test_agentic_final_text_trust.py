from __future__ import annotations

from code2paper.agentic.final_text_claims import extract_final_text_claims, text_digest
from code2paper.agentic.text_evidence_validator import validate_text_evidence
from code2paper.agentic.text_trace_builder import build_final_text_trace
from code2paper.agentic.trust_contracts import AuthoringInputProjection, ForbiddenClaim, ProjectedClaim
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
