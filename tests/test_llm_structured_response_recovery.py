from __future__ import annotations

import pytest

from code2paper.llm.response_schemas import (
    PublicationMethodSectionOutputV1,
    try_parse_structured_response,
    try_parse_structured_response_with_trace,
)


@pytest.mark.parametrize(
    ("response", "expected_operation"),
    [
        (
            '```json\n{"section_markdown":"Mechanism."}\n```',
            "strip_outer_markdown_fence",
        ),
        (
            '{"section_markdown":"Mechanism.",}',
            "remove_trailing_comma",
        ),
        (
            '{"section_markdown":"Mechanism.","used_claim_ids":[]',
            "close_unambiguous_container_suffix",
        ),
    ],
)
def test_representation_recovery_is_lossless_and_traced(
    response: str,
    expected_operation: str,
) -> None:
    parsed, trace, error = try_parse_structured_response_with_trace(
        response,
        PublicationMethodSectionOutputV1,
    )

    assert error == ""
    assert parsed is not None
    assert parsed.section_markdown == "Mechanism."
    assert trace.applied
    assert expected_operation in trace.operations
    assert trace.original_text_digest.startswith("sha256:")
    assert trace.parsed_payload_digest.startswith("sha256:")


def test_strict_json_has_a_trace_but_no_recovery_operation() -> None:
    parsed, trace, error = try_parse_structured_response_with_trace(
        '{"section_markdown":"Mechanism."}',
        PublicationMethodSectionOutputV1,
    )

    assert parsed is not None and error == ""
    assert not trace.applied
    assert trace.operations == ()


def test_deeply_nested_response_fails_closed_without_crashing() -> None:
    pathological = '{"section_markdown": ' + "[" * 20000 + '1' + "]" * 20000 + "}"

    parsed, error = try_parse_structured_response(
        pathological,
        PublicationMethodSectionOutputV1,
    )

    assert parsed is None
    assert error.startswith("schema_validation_failed:")


def test_research_manager_proposal_strips_harness_owned_tool_call_fields() -> None:
    """The Research Manager repair drops echoed harness-owned identity
    fields (obligation_id / repo_snapshot_id / tool_call_id) from tool-call
    items and keeps every model-owned field.

    Regression (fresh EBCAR run): the schema-guided model echoed
    ``obligation_id`` as a sibling of ``arguments``; ``_ResearchManagerToolCallV1``
    forbids extra fields, so the whole proposal was rejected as a parse
    error and the run churned deterministic fallbacks."""
    from code2paper.agentic.gemma_supervisor_backend import (
        _ResearchManagerProposalV1,
    )

    response = (
        '{"goal":"READ_CANDIDATE for obligation=O-1",'
        '"rationale":"read the reranker",'
        '"terminal_action":"",'
        '"tool_calls":[{"tool_name":"read_symbol",'
        '"arguments":{"path":"model.py","symbol":"Reranker.forward"},'
        '"obligation_id":"O-COMPONENT-01-c301ecdd",'
        '"repo_snapshot_id":"repo:abc",'
        '"tool_call_id":"tc-echoed",'
        '"goal":"read the reranker"}]}'
    )
    parsed, trace, error = try_parse_structured_response_with_trace(
        response,
        _ResearchManagerProposalV1,
    )

    assert error == ""
    assert parsed is not None
    assert len(parsed.tool_calls) == 1
    call = parsed.tool_calls[0]
    assert call.tool_name == "read_symbol"
    assert call.arguments == {"path": "model.py", "symbol": "Reranker.forward"}
    assert call.goal == "read the reranker"
    assert trace.applied
    assert "known_schema_shape_repair" in trace.operations


def test_quoted_brace_prefix_is_representation_only_repair() -> None:
    """Qwen3.6 occasionally prefixes a large structured object with a
    quoted opening brace (``{"{``).  The quoted ``{"`` is representation
    noise, not content: after the repair the object must parse and keep
    every model-owned field (EBCAR supervisor regression)."""
    from code2paper.agentic.gemma_supervisor_backend import (
        _ResearchManagerProposalV1,
    )

    response = (
        '\n\n{"{\n'
        '  "goal": "Find the retriever",\n'
        '  "rationale": "search",\n'
        '  "terminal_action": "",\n'
        '  "tool_calls": [{"tool_name": "search_symbols",'
        '"arguments": {"query": "retriever", "kind_filter": []}}]\n'
        "}"
    )
    parsed, trace, error = try_parse_structured_response_with_trace(
        response,
        _ResearchManagerProposalV1,
    )
    assert error == ""
    assert parsed is not None
    assert parsed.goal == "Find the retriever"
    assert parsed.tool_calls[0].tool_name == "search_symbols"
    assert trace.applied


def test_raw_latex_backslash_escape_is_representation_only_repair() -> None:
    """Live Formalizer regression: models emit raw single backslashes inside
    JSON strings (``"latex": "s = \\Delta t + b"``), which are invalid JSON
    escapes.  The recovery layer must escape the backslash WITHOUT changing
    the LaTeX content — representation-only repair (Q2 live Formalizer)."""
    from code2paper.agentic.formalization_agent import SectionFormulaPackageBatchV1

    response = (
        '{"section_id": "MA-S1", "packages": [{"package_id": "fp:MA-S1:1", '
        '"section_id": "MA-S1", "purpose": "State update", '
        '"latex": "s = \\Delta t + b", '
        '"prose_explanation": "The state advances by Delta t.", '
        '"symbol_definitions": [["s", "state"], ["t", "time"]], '
        '"authority_status": "author_intent", '
        '"review_question": "Which code binds Delta t?"}]}'
    )
    parsed, trace, error = try_parse_structured_response_with_trace(
        response,
        SectionFormulaPackageBatchV1,
    )
    assert error == ""
    assert parsed is not None
    package = parsed.packages[0]
    # The LaTeX content is preserved exactly: a single backslash before D.
    assert package.latex == "s = \\Delta t + b"
    assert trace.applied
