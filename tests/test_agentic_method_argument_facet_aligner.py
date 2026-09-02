"""Fail-closed field alignment and local fallback tests."""

from __future__ import annotations

from code2paper.agentic.method_argument_facet_aligner import _alignment_from_owner
from code2paper.agentic.method_argument_brief_models import AuthorMechanismFacetV1
from code2paper.agentic.method_argument_brief_models import FacetEvidenceExcerptV1


def _facet() -> AuthorMechanismFacetV1:
    return AuthorMechanismFacetV1(
        facet_id="facet:method",
        clause_id="clause:method",
        exact_source_quote="normalize the inputs",
        facet_kind="mechanism",
        semantic_fields={"operation": "normalize", "inputs": "inputs"},
    )


def _rows() -> tuple[dict, ...]:
    excerpt = FacetEvidenceExcerptV1(
        span_id="span:normalize",
        exact_excerpt="normalize the inputs",
    )
    return ({
        "evidence_index": 0,
        "exact_excerpt": "normalize the inputs",
        "claim_ids": ["claim:normalize"],
        "claim_texts": ["The implementation normalizes the inputs."],
        "fact_ids": ["fact:normalize"],
        "equation_ids": [],
        "fact_atoms": [{"predicate": "normalizes"}],
        "equation_atoms": [],
        "_excerpt": excerpt,
    },)


def test_owner_failure_keeps_closed_local_evidence_as_partial() -> None:
    alignment = _alignment_from_owner({}, facet=_facet(), rows=_rows(), owner_error="provider_unavailable")
    assert alignment.status == "partial"
    assert alignment.bound_span_ids == ("span:normalize",)
    assert any("deterministic_local_evidence_fallback" in item for item in alignment.schema_failures)
    assert all(binding.status == "partial" for binding in alignment.field_bindings)


def test_one_field_failure_does_not_clear_other_field_binding() -> None:
    alignment = _alignment_from_owner(
        {
            "status": "entailed",
            "supported_fields": ["operation", "inputs"],
            "field_bindings": [
                {
                    "field_name": "operation",
                    "status": "entailed",
                    "bound_span_indices": [0],
                },
                {
                    "field_name": "inputs",
                    "status": "entailed",
                    "bound_span_indices": [99],
                },
            ],
        },
        facet=_facet(),
        rows=_rows(),
    )
    by_name = {binding.field_name: binding for binding in alignment.field_bindings}
    assert by_name["operation"].bound_span_ids == ("span:normalize",)
    assert by_name["operation"].exact_excerpts
    assert by_name["inputs"].status == "unresolved"
    assert by_name["operation"].status in {"entailed", "partial"}


def test_threshold_polarity_reversal_is_mismatch() -> None:
    rows = ({
        **_rows()[0],
        "exact_excerpt": "select when score < threshold",
    },)
    facet = _facet().model_copy(update={
        "exact_source_quote": "select above threshold",
        "semantic_fields": {"conditions": "threshold"},
    })
    alignment = _alignment_from_owner(
        {
            "status": "entailed",
            "supported_fields": ["conditions"],
            "field_bindings": [{
                "field_name": "conditions",
                "status": "entailed",
                "polarity": "threshold_gt_selects",
                "bound_span_indices": [0],
            }],
        },
        facet=facet,
        rows=rows,
    )
    binding = alignment.field_bindings[0]
    assert binding.status == "mismatch"
    assert any("polarity_conflict" in item for item in alignment.schema_failures)


def test_formula_field_does_not_bind_on_one_generic_norm_token() -> None:
    facet = AuthorMechanismFacetV1(
        facet_id="facet:stability",
        clause_id="clause:stability",
        exact_source_quote="maintain stability through spectral norm constraints",
        facet_kind="formula",
        semantic_fields={
            "formula_goal": "maintain stability through spectral norm constraints",
        },
        formula_expectation="required",
    )
    row = {
        **_rows()[0],
        "exact_excerpt": "hidden_states = norm_f(hidden_states)",
        "fact_atoms": [{"predicate": "calls", "object": "norm_f"}],
        "equation_atoms": [{"equation_id": "equation:normalization"}],
        "_excerpt": _rows()[0]["_excerpt"].model_copy(
            update={"span_id": "span:normalization", "exact_excerpt": "hidden_states = norm_f(hidden_states)"}
        ),
    }
    alignment = _alignment_from_owner(
        {},
        facet=facet,
        rows=(row,),
        owner_error="provider_unavailable",
    )
    assert alignment.status == "unresolved"
    assert alignment.bound_span_ids == ()
    assert alignment.field_bindings[0].status == "unresolved"


def test_owner_cannot_promote_semantically_unrelated_formula_row() -> None:
    facet = AuthorMechanismFacetV1(
        facet_id="facet:stability-owner",
        clause_id="clause:stability-owner",
        exact_source_quote="maintain stability through spectral norm constraints",
        facet_kind="formula",
        semantic_fields={
            "formula_goal": "maintain stability through spectral norm constraints",
        },
        formula_expectation="required",
    )
    row = {
        **_rows()[0],
        "exact_excerpt": "hidden_states = norm_f(hidden_states)",
        "_excerpt": _rows()[0]["_excerpt"].model_copy(
            update={"span_id": "span:normalization-owner", "exact_excerpt": "hidden_states = norm_f(hidden_states)"}
        ),
    }
    alignment = _alignment_from_owner(
        {
            "status": "entailed",
            "supported_fields": ["formula_goal"],
            "field_bindings": [{
                "field_name": "formula_goal",
                "status": "entailed",
                "bound_span_indices": [0],
            }],
        },
        facet=facet,
        rows=(row,),
    )
    assert alignment.status == "unresolved"
    assert alignment.field_bindings[0].bound_span_ids == ()
