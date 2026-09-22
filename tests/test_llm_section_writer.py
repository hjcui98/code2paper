"""Tests for ``code2paper.llm.section_writer`` (Phase 1 writer protocol).

Verifies the section-based Method writer:

- Per-section LLM calls are tagged ``role="method_writer"``.
- Default budget is 8192; extended budget (12288) is used only on
  ``finish_reason="length"`` and only when the extended response is
  actually longer.
- Cumulative 24576-token cap stops further section calls once reached;
  remaining sections are filled with deterministic placeholders.
- Each call emits a :class:`GenerationCallTrace` for R8 acceptance.
- Blocked LLM calls do NOT crash the writer; the section gets a
  placeholder and the run continues.
"""

from __future__ import annotations

import json
import unittest
from typing import Any

import pytest

from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.llm.role_config import (
    METHOD_WRITER,
    ROLE_GENERATION_CONFIGS,
    writer_cumulative_budget,
)
from code2paper.llm.section_writer import (
    WriterAggregateResult,
    WriterSectionInput,
    WriterSectionResult,
    _decode_publication_binding_tokens,
    _decode_publication_callback_moves,
    _decode_publication_research_requests,
    default_section_system_prompt,
    dynamic_writer_cumulative_budget,
    _llm_visible_section_payload,
    _normalize_publication_paragraph_transaction,
    _publication_section_partitions,
    _publication_paragraph_repair_contract,
    assess_publication_content_acceptance,
    assess_publication_content_progress,
    assess_publication_writer_response,
    _recover_exact_formula_block_representation,
    _project_operation_to_reader_surface,
    write_publication_method_by_sections,
    write_method_by_sections,
)
from code2paper.llm.response_schemas import (
    PublicationContentWitnessV1,
    PublicationMethodParagraphOutputV1,
    PublicationMethodSectionOutputV1,
    json_schema_for,
)
from code2paper.agentic.publication_transaction_contract import (
    _arithmetic_relation_satisfied,
    _top_level_addition_terms,
    assess_paragraph_transaction,
    bind_paragraph_witnesses,
    paragraph_binding_targets,
    splice_formula_placeholders,
    validate_paragraph_binding_response,
)
from code2paper.schemas import LLMConfig, LLMProvider


def _base_config(**overrides) -> LLMConfig:
    defaults = dict(
        provider=LLMProvider.OPENAI,
        model="gemma4-31b-nvfp4",
        temperature=0.2,
        max_output_tokens=12000,
        cache=False,
    )
    defaults.update(overrides)
    return LLMConfig(**defaults)


def _section(section_id: str, heading: str = "Section") -> WriterSectionInput:
    return WriterSectionInput(
        section_id=section_id,
        heading=heading,
        prompt_payload={"section_id": section_id, "evidence": []},
    )


def test_publication_section_pages_are_always_separate_writer_requests() -> None:
    pages = [
        '{"mechanism_id":"mech","technical_payload":{"details":[{"detail_id":"d:0"}]}}',
        '{"mechanism_id":"mech","technical_payload":{"details":[{"detail_id":"d:1"}]}}',
    ]
    metadata = [
        {"mechanism_id": "mech", "page_index": 0},
        {"mechanism_id": "mech", "page_index": 1},
    ]
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        prompt_payload={
            "section_id": "MA-S1",
            "shared_contexts": pages,
            "shared_context_metadata": metadata,
        },
        publication_mode=True,
    )

    partitions = _publication_section_partitions(
        section,
        system_prompt="Write the section.",
        response_json_schema=None,
        config=_base_config(),
    )

    assert len(partitions) == 2
    assert [part.prompt_payload["shared_contexts"] for part in partitions] == [
        [pages[0]],
        [pages[1]],
    ]
    assert all(
        len(part.prompt_payload["shared_contexts"]) == 1
        and len(part.prompt_payload["shared_context_metadata"]) == 1
        and part.prompt_payload["writer_context_partition"]["partition_kind"]
        == "shared_payload_page"
        for part in partitions
    )


def test_publication_writer_executes_one_actual_call_per_shared_page() -> None:
    pages = [
        '{"mechanism_id":"mech","technical_payload":{"details":[{"detail_id":"d:0"}]}}',
        '{"mechanism_id":"mech","technical_payload":{"details":[{"detail_id":"d:1"}]}}',
    ]
    requests: list[LLMRequest] = []

    def caller(_config, request: LLMRequest) -> LLMResponse:
        requests.append(request)
        payload = request.input_payload
        assert len(payload["shared_contexts"]) == 1
        assert len(payload["shared_context_metadata"]) == 1
        return LLMResponse(
            text=json.dumps({
                "section_id": "MA-S1",
                "heading_text": "Mechanism",
                "section_markdown": "A page-scoped explanation.",
            }),
            response_hash="sha256:page-writer",
            finish_reason="stop",
            token_usage={"completion_tokens": 1},
        )

    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        prompt_payload={
            "section_id": "MA-S1",
            "shared_contexts": pages,
            "shared_context_metadata": [
                {"mechanism_id": "mech", "page_index": 0},
                {"mechanism_id": "mech", "page_index": 1},
            ],
        },
        publication_mode=True,
    )
    result = write_publication_method_by_sections(
        _base_config(),
        [section],
        llm_caller=caller,
    )

    assert len(requests) == 2
    assert [request.input_payload["shared_context_metadata"][0]["page_index"] for request in requests] == [0, 1]
    assert result.aggregate.context_partitioned_section_ids == ["MA-S1"]


def test_unified_v2_multi_page_writer_is_not_limited_by_legacy_output_cap() -> None:
    """All frozen V2 pages can run before the one-repair allowance is used."""

    requests: list[LLMRequest] = []
    sections = [
        WriterSectionInput(
            section_id=f"MA-S1-page-{index}",
            heading="Mechanism",
            prompt_payload={
                "section_id": f"MA-S1-page-{index}",
                "shared_contexts": [f"page-{index}"],
                "shared_context_metadata": [{
                    "v2_page_id": f"page:{index}",
                    "invocation_max_output_tokens": 8192,
                }],
            },
            publication_mode=True,
        )
        for index in range(4)
    ]

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        requests.append(request)
        section_id = request.input_payload["section_id"]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "heading_text": "Mechanism",
                "section_markdown": f"Body for {section_id}.",
            }),
            response_hash=f"sha256:{section_id}",
            finish_reason="stop",
            token_usage={"completion_tokens": 8192},
        )

    result = write_publication_method_by_sections(
        _base_config(),
        sections,
        llm_caller=caller,
    )

    assert len(requests) == 4
    assert not result.aggregate.incomplete_sections
    assert [
        request.response_json_schema["properties"]["section_id"]["const"]
        for request in requests
    ] == [f"MA-S1-page-{index}" for index in range(4)]


def test_unified_v2_transaction_failure_uses_one_declared_writer_repair() -> None:
    calls: list[LLMRequest] = []
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        argument_graph={"paragraphs": [{"paragraph_id": "MA-S1:p1"}]},
        prompt_payload={
            "section_id": "MA-S1",
            "heading": "Mechanism",
            "shared_contexts": [{"page": "frozen"}],
            "shared_context_metadata": [{"v2_page_id": "page:1"}],
            "paragraph_transaction_required": True,
            "binding_contract": {
                "allowed_paragraph_ids": ["MA-S1:p1"],
            },
        },
    )

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        calls.append(request)
        if "writer_section_repair" not in request.input_payload:
            text = json.dumps({
                "section_id": "MA-S1",
                "paragraphs": [
                    {"paragraph_id": "MA-S1:p1", "paragraph_markdown": "first"},
                    {"paragraph_id": "MA-S1:p1", "paragraph_markdown": "first"},
                ],
            })
        else:
            text = json.dumps({
                "section_id": "MA-S1",
                "paragraphs": [{
                    "paragraph_id": "MA-S1:p1",
                    "paragraph_markdown": "repaired substantive Method prose.",
                }],
            })
        return LLMResponse(
            text=text,
            response_hash=f"sha256:call-{len(calls)}",
            finish_reason="stop",
            token_usage={"completion_tokens": 1},
        )

    result = write_publication_method_by_sections(
        _base_config(),
        [section],
        llm_caller=caller,
        content_transaction_assessor=lambda *_args: (True, "transaction_gain"),
    )

    assert len(calls) == 2
    assert calls[0].prompt_template_id == "unified_writer_page_v2"
    assert calls[1].prompt_template_id == "unified_writer_page_v2"
    for request in calls:
        assert request.response_json_schema["$defs"]["PublicationMethodParagraphOutputV1"][
            "properties"
        ]["paragraph_id"]["enum"] == ["MA-S1:p1"]
    assert "paragraph_transaction_repairs" in calls[1].input_payload[
        "writer_section_repair"
    ]
    # 审计 §E.1/E.2：生产修复请求必须携带 canonical 归属结论与失败段落集合，
    # 内部冻结摘要不出现在请求里。
    repair = calls[1].input_payload["writer_section_repair"]
    assert repair["owner"] == "writer_content"
    assert repair["action"] == "writer_content_repair"
    assert repair["escalation"] == "repair_in_place"
    assert "detail_witness_missing" in repair["canonical_codes"]
    assert repair["failed_paragraph_ids"] == ["MA-S1:p1"]
    assert "frozen_paragraph_digests" not in repair
    assert result.aggregate.writer_repair_rounds == 1
    assert result.aggregate.writer_repair_commits == 1
    assert not result.aggregate.incomplete_sections
    assert result.outputs[0].paragraphs[0].paragraph_markdown == (
        "repaired substantive Method prose."
    )
    assert result.outputs[0].rendered_paragraph_ids == ["MA-S1:p1"]


def test_unified_v2_formula_repair_packet_keeps_page_formula_contract() -> None:
    calls: list[LLMRequest] = []
    package = {
        "package_id": "pkg:test:v2-formula",
        "consumer_paragraph_id": "MA-S1:p1",
        "markdown_block": "$$\nL = q + k\n$$",
        "latex": "L = q + k",
    }
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        argument_graph={"paragraphs": [{"paragraph_id": "MA-S1:p1"}]},
        prompt_payload={
            "section_id": "MA-S1",
            "heading": "Mechanism",
            "shared_contexts": [{"page": "frozen"}],
            "shared_context_metadata": [{"v2_page_id": "page:1"}],
            "paragraph_transaction_required": True,
            "formula_packages": [package],
            "formula_placeholders_required": True,
            "binding_contract": {
                "allowed_paragraph_ids": ["MA-S1:p1"],
                "allowed_formula_package_ids": ["pkg:test:v2-formula"],
            },
        },
    )

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        calls.append(request)
        paragraph = "The operation is described."
        if "writer_section_repair" in request.input_payload:
            paragraph += " [[FORMULA:pkg:test:v2-formula]]"
        return LLMResponse(
            text=json.dumps({
                "section_id": "MA-S1",
                "paragraphs": [{
                    "paragraph_id": "MA-S1:p1",
                    "paragraph_markdown": paragraph,
                }],
            }),
            response_hash=f"sha256:v2-formula-{len(calls)}",
            finish_reason="stop",
            token_usage={"completion_tokens": 1},
        )

    result = write_publication_method_by_sections(
        _base_config(),
        [section],
        llm_caller=caller,
        content_transaction_assessor=lambda *_args: (True, "transaction_gain"),
    )

    assert len(calls) == 2
    repair = calls[1].input_payload["writer_section_repair"]
    assert repair["formula_packages"] == [{
        "package_id": "pkg:test:v2-formula",
        "consumer_paragraph_id": "MA-S1:p1",
        "placeholder": "[[FORMULA:pkg:test:v2-formula]]",
    }]
    assert repair["missing_formula_witnesses"] == [
        "[[FORMULA:pkg:test:v2-formula]]"
    ]
    assert "Do not write or alter the mathematical block" in repair[
        "formula_placeholder_instruction"
    ]
    assert result.aggregate.writer_repair_commits == 1
    assert "$$\nL = q + k\n$$" in result.outputs[0].paragraphs[0].paragraph_markdown


def test_unified_v2_empty_stream_failure_uses_one_declared_writer_repair() -> None:
    calls: list[LLMRequest] = []
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        argument_graph={"paragraphs": [{"paragraph_id": "MA-S1:p1"}]},
        prompt_payload={
            "section_id": "MA-S1",
            "heading": "Mechanism",
            "shared_contexts": [{"page": "frozen"}],
            "shared_context_metadata": [{"v2_page_id": "page:1"}],
            "paragraph_transaction_required": True,
            "binding_contract": {"allowed_paragraph_ids": ["MA-S1:p1"]},
        },
    )

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        calls.append(request)
        if "writer_section_repair" not in request.input_payload:
            return LLMResponse(
                text="",
                response_hash="sha256:empty-stream",
                blocked_reason="provider_stream_finished_before_complete_json",
            )
        return LLMResponse(
            text=json.dumps({
                "section_id": "MA-S1",
                "paragraphs": [{
                    "paragraph_id": "MA-S1:p1",
                    "paragraph_markdown": "recovered after representation failure.",
                }],
            }),
            response_hash="sha256:repair",
            finish_reason="stop",
            token_usage={"completion_tokens": 1},
        )

    result = write_publication_method_by_sections(
        _base_config(),
        [section],
        llm_caller=caller,
        content_transaction_assessor=lambda *_args: (True, "transaction_gain"),
    )

    assert len(calls) == 2
    assert calls[0].prompt_template_id == "unified_writer_page_v2"
    assert calls[1].prompt_template_id == "unified_writer_page_v2"
    assert "writer_section_repair" in calls[1].input_payload
    assert result.aggregate.writer_repair_rounds == 1
    assert result.aggregate.writer_repair_commits == 1
    assert not result.aggregate.incomplete_sections
    assert result.outputs[0].paragraphs[0].paragraph_markdown == (
        "recovered after representation failure."
    )


def test_unified_v2_content_failed_repair_is_not_counted_as_commit() -> None:
    """A non-empty but blocked paragraph repair stays incomplete."""

    calls: list[LLMRequest] = []
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        argument_graph={"paragraphs": [{"paragraph_id": "MA-S1:p1"}]},
        prompt_payload={
            "section_id": "MA-S1",
            "heading": "Mechanism",
            "shared_contexts": [{"page": "frozen"}],
            "shared_context_metadata": [{"v2_page_id": "page:1"}],
            "paragraph_transaction_required": True,
            "binding_contract": {"allowed_paragraph_ids": ["MA-S1:p1"]},
        },
    )

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        calls.append(request)
        if "writer_section_repair" not in request.input_payload:
            return LLMResponse(
                text="",
                response_hash="sha256:empty-content-failure",
                blocked_reason="provider_stream_finished_before_complete_json",
            )
        return LLMResponse(
            text=json.dumps({
                "section_id": "MA-S1",
                "heading_text": "Mechanism",
                "section_markdown": "## Mechanism",
                "paragraphs": [{
                    "paragraph_id": "MA-S1:p1",
                    "paragraph_markdown": "## Mechanism",
                }],
            }),
            response_hash="sha256:title-only-repair",
            finish_reason="stop",
            token_usage={"completion_tokens": 1},
        )

    result = write_publication_method_by_sections(
        _base_config(),
        [section],
        llm_caller=caller,
    )

    assert len(calls) == 2
    assert result.aggregate.writer_repair_rounds == 1
    assert result.aggregate.writer_repair_commits == 0
    assert result.aggregate.incomplete_sections == ["MA-S1"]


def test_unified_v2_repairs_unique_casefold_paragraph_id() -> None:
    recovery: list[dict[str, Any]] = []
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        argument_graph={"paragraphs": [{"paragraph_id": "MA-S1:p1"}]},
        prompt_payload={"section_id": "MA-S1"},
    )
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        paragraphs=[PublicationMethodParagraphOutputV1(
            paragraph_id="ma-s1:P1",
            paragraph_markdown="body",
        )],
    )

    normalized, failures = _normalize_publication_paragraph_transaction(
        output,
        section=section,
        require_transactions=True,
        binder_recovery_sink=recovery,
    )

    assert failures == []
    assert normalized.paragraphs[0].paragraph_id == "MA-S1:p1"
    assert recovery[0]["operation"] == "repair_casefold_paragraph_id"


def test_paragraph_heading_recovery_preserves_fused_body_and_rejects_heading_only() -> None:
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Known heading",
        publication_mode=True,
        argument_graph={"paragraphs": [{"paragraph_id": "MA-S1:p1"}]},
        prompt_payload={"paragraph_transaction_required": True},
    )
    fused = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        paragraphs=[PublicationMethodParagraphOutputV1(
            paragraph_id="MA-S1:p1",
            paragraph_markdown="## Known headingThe method maps inputs to outputs.",
        )],
    )
    recovery: list[dict[str, Any]] = []
    normalized, failures = _normalize_publication_paragraph_transaction(
        fused,
        section=section,
        require_transactions=True,
        binder_recovery_sink=recovery,
    )
    assert failures == []
    assert normalized.paragraphs[0].paragraph_markdown == (
        "The method maps inputs to outputs."
    )
    assert recovery[-1]["operation"] == "repair_known_section_heading_from_paragraph"

    heading_only = fused.model_copy(update={
        "paragraphs": [fused.paragraphs[0].model_copy(
            update={"paragraph_markdown": "## Known heading"}
        )]
    })
    _normalized, heading_failures = _normalize_publication_paragraph_transaction(
        heading_only,
        section=section,
        require_transactions=True,
    )
    assert any("paragraph_body_not_substantive" in item for item in heading_failures)


def test_arithmetic_gate_ignores_nested_shape_addition_but_rejects_wrong_sum() -> None:
    zeros = (
        "dedicated_attention_mask = torch.zeros("
        "(batch_size, num_passages + 1, num_passages + 1), "
        "device=self.device)"
    )
    assert _top_level_addition_terms(zeros) == ()
    shape_constraints = {
        "exact": (zeros,),
        "semantic_atom": (
            "transformation: calls transforms torch.zeros, "
            "(batch_size, num_passages + 1, num_passages + 1), "
            "device=self.device into dedicated_attention_mask"
        ),
        "paper_role": "operation",
        "conditions": (),
    }
    assert _arithmetic_relation_satisfied(zeros, shape_constraints)
    assert _arithmetic_relation_satisfied(
        "A zero tensor is allocated with the requested shape.",
        shape_constraints,
    )

    addition_constraints = {
        "exact": ("combined = document_embeddings + passage_embeddings",),
        "semantic_atom": "document_embeddings + passage_embeddings",
        "paper_role": "operation",
        "conditions": (),
    }
    assert _top_level_addition_terms(addition_constraints["exact"][0]) == (
        "document_embeddings",
        "passage_embeddings",
    )
    assert _arithmetic_relation_satisfied(
        "The result sums document embeddings and passage embeddings.",
        addition_constraints,
    )
    for wrong in (
        "The result multiplies document embeddings and passage embeddings.",
        "The result adds only document embeddings.",
        "The result is not added to the passage embeddings.",
    ):
        assert not _arithmetic_relation_satisfied(wrong, addition_constraints)


def test_conditioned_operations_still_require_the_authorized_sum() -> None:
    constraints = {
        "exact": ("result = left_embeddings + right_embeddings",),
        "semantic_atom": "left_embeddings + right_embeddings",
        "paper_role": "operation",
        "conditions": ("cfg.enable_fusion",),
    }
    assert _arithmetic_relation_satisfied(
        "When fusion is enabled, add left embeddings and right embeddings.",
        constraints,
    )
    for wrong in (
        "When fusion is enabled, multiply left embeddings and right embeddings.",
        "When fusion is enabled, add only left embeddings.",
    ):
        assert not _arithmetic_relation_satisfied(wrong, constraints)
    guard = {**constraints, "paper_role": "condition", "semantic_atom": "cfg.enable_fusion"}
    assert _arithmetic_relation_satisfied("When fusion is enabled.", guard)
    assert not _arithmetic_relation_satisfied(
        "When fusion is enabled.", {**guard, "semantic_atom": "unrelated_guard"}
    )


def test_publication_repair_packet_exposes_only_authorized_source_excerpts() -> None:
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        argument_graph={"paragraphs": [{
            "paragraph_id": "MA-S1:p1",
            "paragraph_role": "construction",
            "required_detail_ids": ["detail:op"],
            "witness_contract": {"targets": [{
                "target_kind": "detail",
                "target_id": "detail:op",
                "detail_id": "detail:op",
                "paper_role": "transformation",
                "semantic_atom": "transforms the input",
                "required_conditions": ["when enabled"],
                "required_polarity": "conditional",
                "allowed_exact_excerpts": ["x = transform(input)"],
            }]},
        }]},
        prompt_payload={"section_id": "MA-S1"},
    )
    response = LLMResponse(
        text="",
        response_hash="sha256:empty",
        metadata=PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            paragraphs=[PublicationMethodParagraphOutputV1(
                paragraph_id="MA-S1:p1",
                paragraph_markdown="Mechanism",
            )],
        ),
    )

    repairs = _publication_paragraph_repair_contract(section, response)

    assert len(repairs) == 1
    target = repairs[0]["missing_targets"][0]
    assert target["authorized_source_excerpts"] == ["x = transform(input)"]
    assert "target_id" not in target
    assert "source_anchor_ids" not in target


def test_publication_repair_packet_expands_missing_detail_atoms_with_owner() -> None:
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        argument_graph={"paragraphs": [{
            "paragraph_id": "MA-S1:p1",
            "required_detail_ids": ["detail:op"],
            "witness_contract": {"targets": [
                {
                    "target_kind": "atom",
                    "target_id": "atom:operation",
                    "detail_id": "detail:op",
                    "paper_role": "operation",
                    "semantic_atom": "transforms inputs into outputs",
                    "allowed_exact_excerpts": ["x = transform(inputs)"],
                    "required": True,
                },
                {
                    "target_kind": "atom",
                    "target_id": "atom:output",
                    "detail_id": "detail:op",
                    "paper_role": "output",
                    "semantic_atom": "outputs representations",
                    "allowed_exact_excerpts": ["y = representations"],
                    "required": True,
                },
            ]},
        }]},
        prompt_payload={"section_id": "MA-S1"},
    )
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        paragraphs=[PublicationMethodParagraphOutputV1(
            paragraph_id="MA-S1:p1",
            paragraph_markdown=(
                "The method transforms inputs into outputs and produces "
                "representations."
            ),
        )],
    )
    response = LLMResponse(
        text="",
        response_hash="sha256:atoms",
        blocked_reason="publication_paragraph_transaction_failed:detail",
        metadata=output,
    )
    repairs = _publication_paragraph_repair_contract(section, response)
    assert len(repairs) == 1
    atom_targets = repairs[0]["missing_atom_targets"]
    assert len(atom_targets) == 2
    assert len(repairs[0]["missing_targets"]) == 2
    assert {item["paper_role"] for item in atom_targets} == {"operation", "output"}
    assert all("target_id" not in item for item in atom_targets)
    assert all(item["repair_owner"] in {"writer", "binder"} for item in atom_targets)


def test_deterministic_binder_projects_source_atoms_to_reader_anchors() -> None:
    """A frozen prose sentence can close source-shaped CALL/interface atoms."""

    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Attention",
        prompt_payload={},
        publication_mode=True,
        argument_graph={"paragraphs": [{
            "paragraph_id": "MA-S1:p1",
            "required_detail_ids": ["detail:mask"],
            "witness_contract": {"targets": [
                {
                    "target_kind": "atom",
                    "target_id": "atom:call",
                    "detail_id": "detail:mask",
                    "paper_role": "operation",
                    "semantic_atom": "CALL operation",
                    "allowed_exact_excerpts": [
                        "dedicated_attention_mask = torch.zeros((batch_size + 1,), device=self.device)"
                    ],
                    "required": True,
                },
                {
                    "target_kind": "atom",
                    "target_id": "atom:device",
                    "detail_id": "detail:mask",
                    "paper_role": "operand",
                    "semantic_atom": "device=self.device",
                    "allowed_exact_excerpts": [
                        "dedicated_attention_mask = torch.zeros((batch_size + 1,), device=self.device)"
                    ],
                    "required": True,
                },
                {
                    "target_kind": "atom",
                    "target_id": "atom:output",
                    "detail_id": "detail:mask",
                    "paper_role": "interface",
                    "semantic_atom": "sym:attention",
                    "allowed_exact_excerpts": [
                        "dedicated_attention_mask = torch.zeros((batch_size + 1,), device=self.device)"
                    ],
                    "required": True,
                },
            ]},
        }]},
    )
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        paragraphs=[PublicationMethodParagraphOutputV1(
            paragraph_id="MA-S1:p1",
            paragraph_markdown=(
                "The dedicated attention mask is produced by calling torch.zeros "
                "with shape (batch size + 1) on the model's device."
            ),
        )],
    )

    normalized, failures = _normalize_publication_paragraph_transaction(
        output,
        section=section,
        require_transactions=True,
    )

    assert failures == []
    assert normalized.paragraphs[0].rendered_detail_ids == ["detail:mask"]
    assert {
        witness.target_id for witness in normalized.paragraphs[0].witnesses
    } == {"atom:call", "atom:device", "atom:output"}

    natural_output = output.model_copy(update={
        "paragraphs": [output.paragraphs[0].model_copy(update={
            "paragraph_markdown": (
                "The dedicated attention mask is constructed by zero-initialization "
                "on the model's device."
            ),
            "witnesses": [],
        })],
    })
    natural_normalized, natural_failures = _normalize_publication_paragraph_transaction(
        natural_output,
        section=section,
        require_transactions=True,
    )
    assert natural_failures == []
    assert {
        witness.target_id for witness in natural_normalized.paragraphs[0].witnesses
    } == {"atom:call", "atom:device", "atom:output"}


def test_atom_gain_is_a_valid_bounded_repair_progress_signal() -> None:
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        prompt_payload={},
        publication_mode=True,
        argument_graph={"paragraphs": [{
            "paragraph_id": "MA-S1:p1",
            "required_detail_ids": ["detail:op"],
            "witness_contract": {"targets": [{
                "target_kind": "atom",
                "target_id": "atom:op",
                "detail_id": "detail:op",
                "paper_role": "output",
                "semantic_atom": "produces result",
                "allowed_exact_excerpts": ["result = transform(input)"],
                "required": True,
            }, {
                "target_kind": "atom",
                "target_id": "atom:other",
                "detail_id": "detail:op",
                "paper_role": "output",
                "semantic_atom": "produces representation",
                "allowed_exact_excerpts": ["result = transform(input)"],
                "required": True,
            }]},
        }]},
    )
    incumbent = LLMResponse(
        text="",
        response_hash="sha256:incumbent",
        metadata=PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            paragraphs=[PublicationMethodParagraphOutputV1(
                paragraph_id="MA-S1:p1",
                paragraph_markdown="The transformation is described.",
            )],
        ),
    )
    candidate = LLMResponse(
        text="",
        response_hash="sha256:candidate",
        metadata=PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            paragraphs=[PublicationMethodParagraphOutputV1(
                paragraph_id="MA-S1:p1",
                paragraph_markdown="The transformation produces the result.",
                witnesses=[PublicationContentWitnessV1(
                    witness_kind="atom",
                    target_id="atom:op",
                    exact_text="The transformation produces the result.",
                )],
            )],
        ),
    )

    assert assess_publication_content_progress(section, incumbent, candidate) == (
        True,
        "atom_gain",
    )


def test_source_anchor_resolves_similar_embedding_sentences() -> None:
    """Prefer the source-derived lookup sentence when prose has a tie."""

    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Position encoding",
        prompt_payload={},
        publication_mode=True,
        argument_graph={"paragraphs": [{
            "paragraph_id": "MA-S1:p1",
            "required_detail_ids": ["detail:embedding"],
            "witness_contract": {"targets": [
                {
                    "target_kind": "atom",
                    "target_id": "atom:call",
                    "detail_id": "detail:embedding",
                    "paper_role": "operation",
                    "semantic_atom": "CALL operation",
                    "allowed_exact_excerpts": [
                        "passage_id_embeddings = self.passage_id_embedding("
                        "passage_id.long())"
                    ],
                },
                {
                    "target_kind": "atom",
                    "target_id": "atom:embedding",
                    "detail_id": "detail:embedding",
                    "paper_role": "operand",
                    "semantic_atom": "self.passage_id_embedding",
                    "allowed_exact_excerpts": [
                        "passage_id_embeddings = self.passage_id_embedding("
                        "passage_id.long())"
                    ],
                },
                {
                    "target_kind": "atom",
                    "target_id": "atom:output",
                    "detail_id": "detail:embedding",
                    "paper_role": "output",
                    "semantic_atom": "passage_id_embeddings",
                    "allowed_exact_excerpts": [
                        "passage_id_embeddings = self.passage_id_embedding("
                        "passage_id.long())"
                    ],
                },
            ]},
        }]},
    )
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        paragraphs=[PublicationMethodParagraphOutputV1(
            paragraph_id="MA-S1:p1",
            paragraph_markdown=(
                "The document and passage embeddings are added directly to the "
                "passage representation. Each passage identifier is used as the "
                "index into a passage-position embedding table, producing a "
                "passage-ID embedding."
            ),
        )],
    )

    normalized, failures = _normalize_publication_paragraph_transaction(
        output,
        section=section,
        require_transactions=True,
    )

    assert failures == []
    assert normalized.paragraphs[0].rendered_detail_ids == ["detail:embedding"]
    assert {
        witness.target_id for witness in normalized.paragraphs[0].witnesses
    } == {"atom:call", "atom:embedding", "atom:output"}


def test_unified_page_projection_keeps_page_and_compacts_duplicate_contracts() -> None:
    page = {
        "archive_digest": "sha256:page",
        "atoms": [{"_atom_id": "atom:1", "exact_excerpts": ["x = 1"]}],
    }
    target = {
        "target_id": "atom:1",
        "target_kind": "atom",
        "detail_id": "detail:1",
        "semantic_atom": "repeated semantic text",
        "allowed_anchor_ids": ["span:1"],
        "allowed_exact_excerpts": ["x = 1"],
        "required": True,
        "required_polarity": "positive",
        "required_conditions": ["when enabled"],
    }
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        prompt_payload={
            "section_id": "MA-S1",
            "heading": "Mechanism",
            "narrative_plan": {
                "section_id": "MA-S1",
                "heading": "Mechanism",
                "mechanism_ids": ["mech:1"],
                "page_id": "page:1",
                "content_digest": "sha256:narrative",
                "paragraphs": [{
                    "paragraph_id": "p:1",
                    "section_id": "MA-S1",
                    "role": "construction",
                    "required_detail_ids": ["detail:1"],
                    "witness_contract": {
                        "schema_version": "1",
                        "paragraph_id": "p:1",
                        "rhetorical_goal": "explain",
                        "targets": [target],
                    },
                }],
            },
            "shared_contexts": [page],
            "binding_contract": {
                "allowed_detail_ids": ["detail:1"],
                "required_detail_ids": ["detail:1"],
                "allowed_atom_ids": ["atom:1"],
                "required_atom_ids": ["atom:1"],
                "detail_witness_contracts": {"detail:1": [target]},
                "atom_contracts_by_detail": {"detail:1": [target]},
            },
        },
    )

    visible = _llm_visible_section_payload(section)

    assert visible["shared_contexts"] == [page]
    # 方案 §7.1：atom 由确定性 Binder 负责，Writer 视图不再把它列为必填 witness；
    # canonical 合同（section.prompt_payload）仍保留完整 atom 供 Binder 使用。
    visible_contract = visible["narrative_plan"]["paragraphs"][0]["witness_contract"]
    assert visible_contract["targets"] == []
    assert visible_contract["binder_owned"] == {"owner": "binder", "target_count": 1}
    assert section.prompt_payload["binding_contract"]["detail_witness_contracts"]["detail:1"][0] == target


def test_v2_surface_bounds_author_specification_before_writer_sees_it() -> None:
    long_intent = (
        "Extract the interaction sequence and pass it through the redesigned SSM. "
        "Then make the step size learnable and monotone, initialize the transition "
        "matrix with stable eigenvalues, constrain input-dependent matrices, and "
        "use separate encoders for downstream tasks."
    )
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Encoding",
        prompt_payload={
            "section_id": "MA-S1",
            "authoring_packets_v2": [{
                "section_id": "MA-S1",
                "paragraph_id": "paragraph:MA-S1:1",
                "rhetorical_goal": "construction",
                "ordered_targets": [{
                    "target_kind": "facet",
                    "surface_mode": "author_specification",
                    "render_policy": "optional",
                }],
                "method_unit": {
                    "reader_question": "How is the sequence encoded?",
                    "purpose": long_intent,
                    "ordered_operations": [{
                        "predicate": "author_specification",
                        "description": long_intent,
                    }],
                },
            }],
        },
    )

    visible = _llm_visible_section_payload(section)
    method_unit = visible["authoring_packets_v2"][0]["method_unit"]
    assert len(method_unit["purpose"]) <= 320
    assert method_unit["ordered_operations"] == []
    assert len(method_unit["intent_hints"]) == 1
    assert len(method_unit["intent_hints"][0]) <= 240
    assert method_unit["intent_hints"][0] != long_intent


def test_v2_merges_source_operation_variants_without_losing_conditions() -> None:
    section = WriterSectionInput(
        section_id="MA-S4",
        heading="Node encoding",
        prompt_payload={
            "section_id": "MA-S4",
            "authoring_packets_v2": [{
                "section_id": "MA-S4",
                "paragraph_id": "paragraph:MA-S4:3",
                "rhetorical_goal": "encode nodes",
                "ordered_targets": [],
                "method_unit": {
                    "authority": "mismatch_pending",
                    "ordered_operations": [
                        {
                            "source_span_id": "span:models/GraphMixer.py:118:118",
                            "predicate": "concatenates",
                            "subject": "GraphMixer",
                            "operands": ["edge features", "time features"],
                            "result": "combined_features",
                            "guard": "",
                            "conditions": [],
                        },
                        {
                            "source_span_id": "span:models/GraphMixer.py:118:118",
                            "predicate": "concatenates",
                            "subject": "GraphMixer",
                            "operands": ["edge features", "time features"],
                            "result": "combined_features",
                            "guard": "case_study",
                            "conditions": ["case_study"],
                        },
                    ],
                },
            }],
        },
    )

    visible = _llm_visible_section_payload(section)
    method_unit = visible["authoring_packets_v2"][0]["method_unit"]
    operations = method_unit["ordered_operations"]
    assert method_unit["surface_mode"] == "mismatch_statement"
    assert len(operations) == 1
    assert operations[0].get("conditions") not in (["case_study"], "case_study")
    assert "case_study" not in str(operations[0])
    assert operations[0]["predicate"] == "concatenates"


def test_v2_filters_membership_target_but_keeps_scientific_operation() -> None:
    section = WriterSectionInput(
        section_id="MA-S5",
        heading="Downstream prediction",
        prompt_payload={
            "section_id": "MA-S5",
            "authoring_packets_v2": [{
                "section_id": "MA-S5",
                "paragraph_id": "paragraph:MA-S5:1",
                "rhetorical_goal": "readout",
                "ordered_targets": [
                    {
                        "target_kind": "slot",
                        "semantic_atom": "(src_node_id, dst_node_id) in edge_memories",
                        "conditions": ["(src_node_id, dst_node_id) in edge_memories"],
                        "surface_mode": "repository_statement",
                    },
                    {
                        "target_kind": "slot",
                        "semantic_atom": "mean pooling over the sequence dimension",
                        "surface_mode": "repository_statement",
                    },
                ],
                "method_unit": {
                    "authority": "code_equivalent",
                    "ordered_operations": [
                        {
                            "source_span_id": "span:model.py:40:42",
                            "predicate": "aggregates",
                            "operands": ["sequence embeddings"],
                            "result": "fixed-size node embedding",
                        },
                        {
                            "source_span_id": "span:model.py:80:81",
                            "predicate": "branches_on",
                            "operands": ["(src_node_id, dst_node_id)"],
                            "result": "in edge_memories",
                        },
                    ],
                },
            }],
        },
    )
    visible = _llm_visible_section_payload(section)
    packet = visible["authoring_packets_v2"][0]
    atoms = [item.get("semantic_atom") for item in packet["ordered_targets"]]
    assert "mean pooling over the sequence dimension" in atoms
    assert not any("edge_memories" in str(item) for item in packet["ordered_targets"])
    operations = packet["method_unit"]["ordered_operations"]
    assert any(item.get("predicate") == "aggregates" for item in operations)
    assert not any("edge_memories" in str(item) for item in operations)


def test_reader_projection_prefers_semantic_claim_over_raw_operands() -> None:
    # Semantic-primary mode: raw operands and results are omitted
    row_with_semantic = {
        "predicate": "normalizes",
        "reader_facing_claim": "normalize routing weights across candidate positions",
        "operands": ["dst_router_logits", "dim=1"],
        "result": "dst_routing_weights",
    }
    projected = _project_operation_to_reader_surface(row_with_semantic)
    assert projected is not None
    assert projected["operation"] == "normalize routing weights across candidate positions"
    assert projected["predicate"] == "normalizes"
    assert "operands" not in projected
    assert "result" not in projected

    # Fallback mode without semantic text: scientific symbols are preserved
    row_without_semantic = {
        "predicate": "multiplies",
        "operands": ["W", "x_t"],
        "result": "h_t",
    }
    projected_fallback = _project_operation_to_reader_surface(row_without_semantic)
    assert projected_fallback is not None
    assert projected_fallback["predicate"] == "multiplies"
    assert projected_fallback["operands"] == ["W", "x_t"]
    assert projected_fallback["result"] == "h_t"


def test_motivation_context_section_isolates_raw_implementation_operations() -> None:
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Motivation",
        prompt_payload={
            "section_id": "MA-S1",
            "authoring_packets_v2": [{
                "section_id": "MA-S1",
                "paragraph_id": "paragraph:MA-S1:1",
                "rhetorical_goal": "problem_or_local_context",
                "ordered_targets": [],
                "method_unit": {
                    "section_heading": "Motivation",
                    "authority": "code_equivalent",
                    "ordered_operations": [
                        {
                            "source_span_id": "span:model.py:10:12",
                            "predicate": "computes",
                            "operands": ["fused_add_norm", "conv_state", "step_hidden_states"],
                            "result": "ssm_out",
                        },
                        {
                            "source_span_id": "span:model.py:20:22",
                            "predicate": "analyzes",
                            "reader_facing_claim": "irregular timestamps hurt uniform-step SSM",
                        },
                    ],
                },
                "dossier_summary": {
                    "operation_atoms": [
                        {
                            "operation": "fused_add_norm",
                            "operands": ["conv_state", "step_hidden_states"],
                        },
                    ],
                },
            }],
        },
    )
    visible = _llm_visible_section_payload(section)
    packet = visible["authoring_packets_v2"][0]
    operations = packet["method_unit"]["ordered_operations"]
    # Explicit rationale is visible
    assert any("irregular timestamps hurt uniform-step SSM" in str(item.get("operation", "")) for item in operations)
    # Raw implementation operations (fused_add_norm, conv_state) are suppressed
    assert not any("fused_add_norm" in str(item) for item in operations)
    assert not any("conv_state" in str(item) for item in operations)



def test_formula_placeholder_replacement_preserves_formalizer_block_verbatim() -> None:
    block = "$$\n\\bar{p}=p+e_{doc}\n$$"
    rendered, failures = splice_formula_placeholders(
        "The augmented passage is [[FORMULA:package:augmentation]].",
        [{"package_id": "package:augmentation", "markdown_block": block}],
        required_package_ids=("package:augmentation",),
        allowed_package_ids=("package:augmentation",),
    )
    assert failures == ()
    assert rendered == f"The augmented passage is {block}."
    assert block in rendered

    _, wrong_consumer = splice_formula_placeholders(
        "[[FORMULA:package:augmentation]]",
        [{"package_id": "package:augmentation", "markdown_block": block}],
        required_package_ids=("package:augmentation",),
        allowed_package_ids=("package:other",),
    )
    assert "formula_placeholder_wrong_consumer:package:augmentation" in wrong_consumer


def test_repeated_formula_bindings_follow_placeholder_occurrences() -> None:
    packages = [
        {"package_id": "pkg:first", "latex": "y = f(x)"},
        {"package_id": "pkg:second", "latex": "y = f(x)"},
    ]
    body = "Initialization: [[FORMULA:pkg:first]]. Update: [[FORMULA:pkg:second]]."
    witnesses: list[dict[str, str]] = []
    rendered, failures = splice_formula_placeholders(
        body, packages, required_package_ids=("pkg:first", "pkg:second"),
        allowed_package_ids=("pkg:first", "pkg:second"), witness_sink=witnesses,
    )
    assert not failures
    assert rendered == splice_formula_placeholders(body, packages)[0]
    assert len(witnesses) == 2
    assert witnesses[0]["target_id"] == "pkg:first"
    assert witnesses[1]["target_id"] == "pkg:second"
    assert witnesses[0]["exact_text"] != witnesses[1]["exact_text"]
    for witness in witnesses:
        assert rendered.count(witness["exact_text"]) == 1
        assert "$$\ny = f(x)\n$$" in witness["exact_text"]
    assessment = assess_paragraph_transaction({
        "paragraph_id": "p1", "paragraph_markdown": rendered,
        "used_formula_package_ids": ["pkg:first", "pkg:second"],
        "witnesses": witnesses,
    }, plan_row={"paragraph_id": "p1"})
    assert not assessment.invalid_witnesses

    # Equal rendered formulas without owner-checked placeholders supply no
    # occurrence provenance and must not gain bindings through this path.
    unbound: list[dict[str, str]] = []
    assert splice_formula_placeholders(rendered, packages, witness_sink=unbound) == (rendered, ())
    assert unbound == []


@pytest.mark.parametrize("body,allowed,expected_failure", [
    ("[[FORMULA:pkg:first]] [[FORMULA:pkg:first]]", ("pkg:first",), "formula_placeholder_duplicate:"),
    ("[[FORMULA:pkg:unknown]]", ("pkg:first",), "formula_placeholder_unknown_package:"),
    ("[[FORMULA:pkg:first]]", ("pkg:other",), "formula_placeholder_wrong_consumer:"),
])
def test_failed_formula_splice_never_publishes_occurrence_bindings(
    body: str, allowed: tuple[str, ...], expected_failure: str,
) -> None:
    witnesses: list[dict[str, str]] = []
    rendered, failures = splice_formula_placeholders(
        body, [{"package_id": "pkg:first", "latex": "y = f(x)"}],
        allowed_package_ids=allowed, witness_sink=witnesses,
    )
    assert rendered == body
    assert any(failure.startswith(expected_failure) for failure in failures)
    assert witnesses == []


def test_splice_strips_formula_memo_wrapper_to_display_math() -> None:
    latex = r"\Delta t = f(\tau)"
    rendered, failures = splice_formula_placeholders(
        "The step is [[FORMULA:pkg-s5]].",
        [{
            "package_id": "pkg-s5",
            "latex": latex,
            "markdown_block": (
                "### Core\n\n"
                f"$$\n{latex}\n$$\n\n"
                "**Symbol Definitions:**\n* step size"
            ),
        }],
        required_package_ids=("pkg-s5",),
        allowed_package_ids=("pkg-s5",),
    )
    assert failures == ()
    assert rendered == f"The step is $$\n{latex}\n$$."
    assert "###" not in rendered
    assert "Symbol Definitions" not in rendered


def test_splice_wraps_inline_latex_as_display_math_block() -> None:
    latex = r"loss_i = -pos_sim + \operatorname{logsumexp}(all_sims, dim=0)"
    rendered, failures = splice_formula_placeholders(
        "The objective is [[FORMULA:opfp:MA-S4:1]].",
        [{"package_id": "opfp:MA-S4:1", "latex": latex, "markdown_block": latex}],
        required_package_ids=("opfp:MA-S4:1",),
        allowed_package_ids=("opfp:MA-S4:1",),
    )
    assert failures == ()
    assert "[[FORMULA:" not in rendered
    assert f"$$\n{latex}\n$$" in rendered


def test_source_fact_formula_block_witnesses_its_operation_slot_once() -> None:
    block = "$$\nloss_i = -pos_sim + \\operatorname{logsumexp}(all_sims, dim=0)\n$$"
    fact_id = "fact-O-METHOD-MAINLINE-01-node:loss"
    slot_id = f"slot:{fact_id}"
    package_id = "opfp:section:loss"
    transaction = {
        "paragraph_id": "paragraph:section:loss",
        "paragraph_markdown": f"The contrastive objective is defined as:\n{block}",
        "used_formula_package_ids": [package_id],
        "witnesses": [{
            "witness_kind": "formula",
            "target_id": package_id,
            "exact_text": block,
        }],
    }
    plan_row = {
        "required_publication_slot_ids": [slot_id],
        "required_facet_ids": [],
        "formula_obligation_ids": ["formula:facet:loss"],
        "witness_contract": {"targets": [{
            "target_kind": "slot",
            "target_id": slot_id,
            "semantic_atom": "compute formula pos sim log sum exp all sims dim loss",
            "allowed_anchor_ids": [fact_id],
        }, {
            "target_kind": "formula",
            "target_id": "formula:facet:loss",
            "semantic_atom": "formal expression",
        }]},
    }
    package = {
        "package_id": package_id,
        "obligation_id": "formula:facet:loss",
        "consumer_paragraph_id": transaction["paragraph_id"],
        "bound_fact_ids": [fact_id],
        "markdown_block": block,
        "latex": "loss_i = -pos_sim + \\operatorname{logsumexp}(all_sims, dim=0)",
        "authority_status": "code_verified",
        "formula_lane": "repository_derived",
        "review_status": "accepted",
    }

    bound = bind_paragraph_witnesses(
        transaction,
        plan_row=plan_row,
        formula_packages=[package],
    )

    slot_witnesses = [
        item for item in bound["witnesses"]
        if item["witness_kind"] == "slot"
    ]
    assert bound["rendered_slot_ids"] == [slot_id]
    assert slot_witnesses == [{
        "witness_kind": "slot",
        "target_id": slot_id,
        "exact_text": block,
    }]
    assert bound["witnesses"].count({
        "witness_kind": "formula",
        "target_id": package_id,
        "exact_text": block,
    }) == 1


def test_exact_canonical_formula_block_recovers_lost_placeholder() -> None:
    block = "$$\ny = x + z\n$$"
    transaction = PublicationMethodParagraphOutputV1(
        paragraph_id="paragraph:section:formula",
        paragraph_markdown=f"The operation is specified by:\n{block}",
    )
    package = {
        "package_id": "opfp:section:formula",
        "obligation_id": "formula:section:formula",
        "consumer_paragraph_id": transaction.paragraph_id,
        "markdown_block": block,
        "authority_status": "code_verified",
        "formula_lane": "repository_derived",
        "review_status": "accepted",
    }

    recovered, package_ids = _recover_exact_formula_block_representation(
        transaction,
        missing_failures=("formula_placeholder_missing:opfp:section:formula",),
        formula_packages=[package],
    )

    assert package_ids == (package["package_id"],)
    assert recovered.used_formula_package_ids == [package["package_id"]]
    assert recovered.witnesses[0].target_id == package["package_id"]
    assert recovered.witnesses[0].exact_text == block


def test_inline_latex_without_display_math_recovers_canonical_block() -> None:
    latex = r"\pi_{t+1} = (1-\alpha) \pi_t + \alpha r_t"
    block = f"$$\n{latex}\n$$"
    transaction = PublicationMethodParagraphOutputV1(
        paragraph_id="paragraph:section:formula",
        paragraph_markdown=f"The recurrence is {latex} on the recorded path.",
    )
    package = {
        "package_id": "opfp:section:formula",
        "obligation_id": "formula:section:formula",
        "consumer_paragraph_id": transaction.paragraph_id,
        "markdown_block": block,
        "latex": latex,
        "authority_status": "code_verified",
        "formula_lane": "repository_derived",
        "review_status": "accepted",
    }

    recovered, package_ids = _recover_exact_formula_block_representation(
        transaction,
        missing_failures=("formula_placeholder_missing:opfp:section:formula",),
        formula_packages=[package],
    )

    assert package_ids == (package["package_id"],)
    assert recovered.paragraph_markdown.count(block) == 1
    assert recovered.paragraph_markdown.count(latex) == 1
    assert recovered.used_formula_package_ids == [package["package_id"]]
    assert recovered.witnesses[0].exact_text == block


def test_binder_recovers_unique_omitted_slot_from_semantic_sentence() -> None:
    transaction = {
        "paragraph_id": "paragraph:method:step",
        "paragraph_markdown": (
            "The encoder computes a weighted sum and returns the score."
        ),
        "rendered_slot_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_publication_slot_ids": ["slot:score"],
        "witness_contract": {"targets": [{
            "target_kind": "slot",
            "target_id": "slot:score",
            "semantic_atom": "encoder computes a weighted sum result score",
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_slot_ids"] == ["slot:score"]
    assert bound["witnesses"] == [{
        "witness_kind": "slot",
        "target_id": "slot:score",
        "exact_text": transaction["paragraph_markdown"],
    }]


def test_binder_does_not_bind_ambiguous_omitted_slot_sentence() -> None:
    sentence = "The encoder computes a weighted sum and returns the score."
    transaction = {
        "paragraph_id": "paragraph:method:step",
        "paragraph_markdown": f"{sentence} {sentence}",
        "rendered_slot_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_publication_slot_ids": ["slot:score"],
        "witness_contract": {"targets": [{
            "target_kind": "slot",
            "target_id": "slot:score",
            "semantic_atom": "encoder computes a weighted sum result score",
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_slot_ids"] == []
    assert bound["witnesses"] == []


def test_binder_recovers_reader_language_for_closed_library_operations() -> None:
    """Source-backed operation aliases may bridge normal Method wording.

    The model need not copy ``torch.sort``/``torch.cat`` into prose, but the
    Binder must still require distinctive operands from the same frozen
    source excerpt before deriving a required Detail from its atoms.
    """

    sort_row = {
        "paragraph_id": "paragraph:method:sort",
        "required_detail_ids": ["detail:sort"],
        "witness_contract": {"targets": [{
            "target_kind": "atom",
            "target_id": "atom:sort:operation",
            "detail_id": "detail:sort",
            "semantic_atom": "sorts_by operation",
            "paper_role": "operation",
            "allowed_exact_excerpts": [
                "relevance_scores, indices = torch.sort("
                "similarities, dim=1, descending=True)"
            ],
            "required": True,
        }]},
    }
    sort_transaction = {
        "paragraph_id": sort_row["paragraph_id"],
        "paragraph_markdown": (
            "The similarity scores are sorted in descending order via "
            "torch.sort, producing relevance scores and permutation indices."
        ),
        "witnesses": [],
    }
    sort_bound = bind_paragraph_witnesses(sort_transaction, plan_row=sort_row)
    assert sort_bound["rendered_detail_ids"] == ["detail:sort"]
    assert sort_bound["witnesses"][0]["target_id"] == "atom:sort:operation"

    concat_row = {
        "paragraph_id": "paragraph:method:concat",
        "required_detail_ids": ["detail:concat"],
        "witness_contract": {"targets": [{
            "target_kind": "atom",
            "target_id": "atom:concat:operation",
            "detail_id": "detail:concat",
            "semantic_atom": "concatenates operation",
            "paper_role": "operation",
            "allowed_exact_excerpts": [
                "temp_indices = torch.cat((torch.tensor([True]), temp_indices))"
            ],
            "required": True,
        }]},
    }
    concat_transaction = {
        "paragraph_id": concat_row["paragraph_id"],
        "paragraph_markdown": (
            "A True sentinel is prepended to the passage indices by "
            "concatenation."
        ),
        "witnesses": [],
    }
    concat_bound = bind_paragraph_witnesses(
        concat_transaction,
        plan_row=concat_row,
    )
    assert concat_bound["rendered_detail_ids"] == ["detail:concat"]
    assert concat_bound["witnesses"][0]["target_id"] == "atom:concat:operation"


def test_binder_allows_one_sentence_to_witness_two_closed_facets() -> None:
    sentence = (
        "The dense retriever produces candidate passage embeddings for the query."
    )
    transaction = {
        "paragraph_id": "paragraph:method:pipeline",
        "paragraph_markdown": sentence,
        "rendered_from_facet_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_facet_ids": ["facet:pipeline", "facet:retrieval"],
        "witness_contract": {"targets": [
            {
                "target_kind": "facet",
                "target_id": "facet:pipeline",
                "semantic_atom": "dense retriever produces candidate passage embeddings",
            },
            {
                "target_kind": "facet",
                "target_id": "facet:retrieval",
                "semantic_atom": "retrieval uses a dense retriever for candidate passages",
            },
        ]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_from_facet_ids"] == [
        "facet:pipeline",
        "facet:retrieval",
    ]
    assert [item["target_id"] for item in bound["witnesses"]] == [
        "facet:pipeline",
        "facet:retrieval",
    ]
    assert all(item["exact_text"] in sentence for item in bound["witnesses"])


def _detail_atom_plan_row() -> dict[str, Any]:
    exact = "passages + document_id_embeddings + passage_id_embeddings"
    return {
        "paragraph_id": "paragraph:method:detail",
        "required_detail_ids": ["detail:1"],
        "optional_detail_ids": [],
        "witness_contract": {
            "targets": [
                {
                    "target_kind": "atom",
                    "target_id": "atom:document",
                    "detail_id": "detail:1",
                    "semantic_atom": "document_id_embeddings",
                    "allowed_exact_excerpts": [exact],
                    "required": True,
                },
                {
                    "target_kind": "atom",
                    "target_id": "atom:passage",
                    "detail_id": "detail:1",
                    "semantic_atom": "passage_id_embeddings",
                    "allowed_exact_excerpts": [exact],
                    "required": True,
                },
                {
                    "target_kind": "atom",
                    "target_id": "atom:condition",
                    "detail_id": "detail:1",
                    "semantic_atom": "self.cfg.add_positional_encoding",
                    "required_conditions": ["self.cfg.add_positional_encoding"],
                    "allowed_exact_excerpts": [exact],
                    "required": True,
                },
            ],
        },
    }


def _detail_atom_body() -> str:
    return (
        "When positional encoding is enabled, document ID embeddings are "
        "combined with passage representations, and passage ID embeddings "
        "are added to the resulting tensor."
    )


def test_v3_atom_detail_id_is_preserved_and_complete_atoms_derive_detail() -> None:
    plan_row = _detail_atom_plan_row()
    transaction = {
        "paragraph_id": plan_row["paragraph_id"],
        "paragraph_markdown": _detail_atom_body(),
        "rendered_detail_ids": [],
        "witnesses": [],
    }

    targets = paragraph_binding_targets(transaction, plan_row=plan_row)
    assert {item["detail_id"] for item in targets} == {"detail:1"}

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)
    assert bound["rendered_detail_ids"] == ["detail:1"]
    assert len(bound["witnesses"]) == 3
    assessment = assess_paragraph_transaction(
        bound,
        plan_row=plan_row,
    )
    assert assessment.valid is True
    assert assessment.witnessed_by_kind["detail"] == ("detail:1",)


def test_v3_atom_detail_stays_incomplete_when_one_required_atom_is_absent() -> None:
    plan_row = _detail_atom_plan_row()
    transaction = {
        "paragraph_id": plan_row["paragraph_id"],
        "paragraph_markdown": (
            "When positional encoding is enabled, document ID embeddings "
            "are indexed by the document identifier."
        ),
        "rendered_detail_ids": [],
        "witnesses": [],
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)
    assert bound["rendered_detail_ids"] == []
    assessment = assess_paragraph_transaction(bound, plan_row=plan_row)
    assert assessment.valid is False
    assert assessment.missing_by_kind["detail"] == ("detail:1",)


def test_v3_complete_atoms_pass_pydantic_transaction_normalization() -> None:
    plan_row = _detail_atom_plan_row()
    section = WriterSectionInput(
        section_id="section:detail",
        heading="Detail",
        publication_mode=True,
        argument_graph={"paragraphs": [plan_row]},
        prompt_payload={"section_id": "section:detail"},
    )
    output = PublicationMethodSectionOutputV1(
        section_id="section:detail",
        paragraphs=[PublicationMethodParagraphOutputV1(
            paragraph_id=plan_row["paragraph_id"],
            paragraph_markdown=_detail_atom_body(),
        )],
    )

    normalized, failures = _normalize_publication_paragraph_transaction(
        output,
        section=section,
        require_transactions=True,
    )

    assert failures == []
    assert normalized.paragraphs[0].rendered_detail_ids == ["detail:1"]


class _RecordingCaller:
    """Records every LLM call and returns canned responses.

    Each call records ``(config, request)`` so tests can assert on the
    effective sampling config and prompt payload.  The list of canned
    responses is consumed in order; the same response is returned for
    every call once the canned list is exhausted.
    """

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[LLMConfig, LLMRequest]] = []

    def __call__(self, config: LLMConfig, request: LLMRequest) -> LLMResponse:
        self.calls.append((config, request))
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(
            text="## default",
            response_hash="sha256:default",
            finish_reason="stop",
            token_usage={"completion_tokens": 100},
        )


def _response(
    text: str = "## Section\ncontent",
    *,
    finish_reason: str = "stop",
    completion_tokens: int = 100,
    blocked_reason: str = "",
) -> LLMResponse:
    from code2paper.export.run_manifest import hash_text

    if completion_tokens is None:
        token_usage = None
    else:
        token_usage = {"completion_tokens": completion_tokens} if not blocked_reason else {}
    return LLMResponse(
        text=text,
        response_hash=hash_text(text),
        finish_reason=finish_reason,
        token_usage=token_usage,
        blocked_reason=blocked_reason,
    )


class DefaultSystemPromptTests(unittest.TestCase):
    def test_default_section_system_prompt_mentions_constraints(self) -> None:
        prompt = default_section_system_prompt()
        self.assertIn("Method writer", prompt)
        self.assertIn("Hard constraints", prompt)

    def test_default_prompt_scopes_heading_to_section_mode(self) -> None:
        prompt = default_section_system_prompt()
        self.assertIn("For a section-level response", prompt)
        self.assertIn("For a paragraph-transaction response, do not emit any heading", prompt)
        self.assertNotIn("Begin with exactly '## <supplied heading>'", prompt)

    def test_writer_view_hides_legacy_competing_content_surfaces(self) -> None:
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Overview",
            prompt_payload={
                "writer_view": {"purpose": {"heading": "Overview"}},
                "argument_flow": {"semantic_frames": ["hidden"]},
                "reader_facing_claims": [{"paper_statement": "hidden"}],
                "validation_constraints": {"claims": ["hidden"]},
                "content_first_instruction": "legacy long instruction",
                "binding_contract": {"allowed_proposition_ids": ["MP-1"]},
                "required_qualifier_bindings": [
                    "self.config.use_vectorized_retrieval",
                ],
            },
        )

        visible = _llm_visible_section_payload(section)

        self.assertEqual(visible["writer_view"]["purpose"]["heading"], "Overview")
        self.assertEqual(
            visible["required_qualifier_bindings"],
            ["self.config.use_vectorized_retrieval"],
        )
        self.assertNotIn("binding_contract", visible)
        self.assertNotIn("argument_flow", visible)
        self.assertNotIn("reader_facing_claims", visible)
        self.assertNotIn("validation_constraints", visible)
        self.assertNotIn("content_first_instruction", visible)

    def test_writer_view_hides_all_harness_id_surfaces_from_real_request(self) -> None:
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Overview",
            publication_mode=True,
            argument_graph={"argument_unit_ids": ["MA-S1:unit"]},
            prompt_payload={
                "section_id": "MA-S1",
                "heading": "Overview",
                "writer_view": {
                    "purpose": {"heading": "Overview"},
                    "positive_propositions": [{"proposition_id": "MP-1"}],
                },
                "argument_units": [{"argument_unit_id": "MA-S1:unit"}],
                "argument_flow": {"semantic_frames": [{"frame_id": "FRAME-1"}]},
                "validation_constraints": {"claims": [{"claim_id": "C1"}]},
                "grounding_contract": {"required_anchor_fields": ["fact:F1"]},
                "binding_contract": {
                    "used_argument_unit_ids": ["MA-S1:unit"],
                    "used_claim_ids": ["C1"],
                    "used_equation_ids": ["EQ1"],
                    "used_configuration_ids": ["CFG1"],
                    "allowed_proposition_ids": ["MP-1"],
                },
                "required_rhetorical_moves": ["mechanism_overview"],
                "formalization": {"equation_ids": ["EQ1"]},
            },
        )

        visible = _llm_visible_section_payload(section)

        self.assertEqual(set(visible), {"section_id", "heading", "writer_view"})
        serialized = json.dumps(visible)
        for forbidden in ("C1", "EQ1", "CFG1", "FRAME-1", "MA-S1:unit", "fact:F1"):
            self.assertNotIn(forbidden, serialized)

    def test_compact_writer_view_keeps_licensed_l2_without_claim_ids(self) -> None:
        section = WriterSectionInput(
            section_id="MA-S4",
            heading="First retrieval",
            prompt_payload={
                "writer_view": {
                    "purpose": {"heading": "First retrieval"},
                    "technical_propositions": [{
                        "proposition_id": "l2:threshold",
                        "reader_subject": "licensed technical effect",
                        "transformation": "Expansion excludes entities whose score fails the threshold.",
                    }],
                    "positive_briefs": [],
                    "caveated_briefs": [],
                },
            },
        )
        visible = _llm_visible_section_payload(section)
        rows = visible["writer_view"]["technical_propositions"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["license"], "E2")
        self.assertIn("fails the threshold", rows[0]["transformation"])
        self.assertFalse(visible["writer_view"]["claim_free_expository_bridge_allowed"])
        self.assertNotIn("l2:threshold", json.dumps(visible))


class WriteMethodBySectionsBasicTests(unittest.TestCase):
    def test_single_section_produces_concatenated_markdown(self) -> None:
        caller = _RecordingCaller([_response(text="## Overview\ncontent")])
        result = write_method_by_sections(
            _base_config(),
            [_section("overview", "Overview")],
            llm_caller=caller,
        )
        self.assertEqual(len(result.sections), 1)
        self.assertEqual(result.sections[0].text, "## Overview\ncontent")
        self.assertEqual(result.concatenated_markdown, "## Overview\ncontent")

    def test_two_sections_concatenated_with_double_newline(self) -> None:
        caller = _RecordingCaller([
            _response(text="## A\ncontent-a"),
            _response(text="## B\ncontent-b"),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a", "A"), _section("b", "B")],
            llm_caller=caller,
        )
        self.assertEqual(
            result.concatenated_markdown,
            "## A\ncontent-a\n\n## B\ncontent-b",
        )

    def test_each_call_tagged_with_method_writer_role(self) -> None:
        caller = _RecordingCaller([_response()])
        write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        config, _ = caller.calls[0]
        self.assertEqual(config.role, METHOD_WRITER)

    def test_each_call_uses_writer_protocol_temperature(self) -> None:
        caller = _RecordingCaller([_response()])
        write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        config, _ = caller.calls[0]
        self.assertEqual(
            config.temperature,
            ROLE_GENERATION_CONFIGS[METHOD_WRITER].temperature,
        )

    def test_each_call_uses_default_writer_budget_8192(self) -> None:
        caller = _RecordingCaller([_response()])
        write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        config, _ = caller.calls[0]
        self.assertEqual(config.max_output_tokens, 8192)

    def test_content_transaction_rejection_returns_feedback_for_one_correction(self) -> None:
        writer_view = {
            "purpose": {"heading": "Encoder", "reader_question": "How is input read?"},
            "positive_propositions": [{
                "proposition_id": "MP-1",
                "reader_subject": "the encoder",
                "transformation": "reads the configured input",
                "inputs": ["configured input"],
                "outputs": [],
                "conditions": [],
                "paper_terms": ["encoder"],
            }],
            "caveated_propositions": [],
            "immutable_constraints": [],
            "allowed_proposition_ids": ["MP-1"],
            "required_proposition_ids": ["MP-1"],
        }
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Encoder",
            prompt_payload={"writer_view": writer_view},
        )
        caller = _RecordingCaller([
            _response(text=(
                "## Encoder\n\nencoder.read reads the configured input through "
                "encoder.load and encoder.return_value."
            )),
            _response(text="## Encoder\n\nThe encoder reads the configured input and improves accuracy."),
            _response(text="## Encoder\n\nThe encoder reads the configured input."),
        ])
        transaction_calls: list[tuple[str, str]] = []

        def validator(_section, incumbent, candidate):
            transaction_calls.append((incumbent, candidate))
            if "improves accuracy" in candidate:
                return False, "writer_unsupported_positive_regressed"
            return True, "writer_transaction_monotonic_gain"

        result = write_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
            content_transaction_validator=validator,
        )

        self.assertEqual(len(transaction_calls), 2)
        self.assertIn("improves accuracy", transaction_calls[0][1])
        self.assertEqual(
            result.sections[0].text,
            "## Encoder\n\nThe encoder reads the configured input.",
        )
        self.assertEqual(result.writer_repair_rounds, 2)
        self.assertEqual(result.writer_repair_commits, 1)
        self.assertEqual(len(result.writer_repair_transaction_rejections), 1)
        self.assertEqual(
            result.writer_repair_transaction_rejections[0]["reason"],
            "writer_unsupported_positive_regressed",
        )

    def test_formula_placeholder_failure_enters_writer_content_repair(self) -> None:
        formula_block = "$$\nL = q + k\n$$"
        package = {
            "package_id": "opfp:test:1",
            "markdown_block": formula_block,
            "latex": "L = q + k",
            "consumer_paragraph_id": "MA-S1:p1",
            "purpose": "test operation",
            "authority_status": "code_verified",
            "formula_lane": "repository_derived",
            "review_status": "accepted",
        }
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Encoder",
            publication_mode=True,
            argument_graph={"paragraphs": [{"paragraph_id": "MA-S1:p1"}]},
            prompt_payload={
                "writer_view": {
                    "mechanism_authoring_packet": {
                        "facets": [],
                        "required_facet_ids": [],
                        "formula_packages": [package],
                    },
                },
                "formula_packages": [package],
                "formula_obligations": [],
                "paragraph_transaction_required": True,
                "formula_placeholders_required": True,
                "binding_contract": {
                    "used_argument_unit_ids": [],
                    "used_claim_ids": [],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": [],
                    "allowed_paragraph_ids": ["MA-S1:p1"],
                    "allowed_formula_package_ids": ["opfp:test:1"],
                },
            },
        )

        def payload(markdown: str) -> str:
            return json.dumps({
                "section_id": "MA-S1",
                # Exercise the paragraph-preservation bridge: some providers
                # return only paragraph transactions on a formula failure.
                "section_markdown": "",
                "paragraphs": [{
                    "paragraph_id": "MA-S1:p1",
                    "paragraph_markdown": markdown,
                }],
            })

        # The initial response and the representation retry both omit the
        # placeholder.  The third response is reached only through the
        # bounded Writer-owned content repair path.
        caller = _RecordingCaller([
            _response(text=payload("The operation is described.")),
            _response(text=payload("The operation is described.")),
            _response(text=payload(
                "The operation is described [[FORMULA:opfp:test:1]]."
            )),
        ])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 3)
        repair_payload = caller.calls[2][1].input_payload["writer_section_repair"]
        self.assertEqual(
            repair_payload["missing_formula_witnesses"],
            ["[[FORMULA:opfp:test:1]]"],
        )
        self.assertIn(
            "Do not write or alter the mathematical block",
            repair_payload["formula_placeholder_instruction"],
        )
        self.assertNotIn(formula_block, json.dumps(caller.calls[2][1].input_payload))
        self.assertEqual(result.aggregate.writer_repair_rounds, 1)
        self.assertEqual(result.aggregate.writer_repair_commits, 1)
        self.assertEqual(len(result.outputs), 1)
        self.assertIn(formula_block, result.outputs[0].section_markdown)


class FinishReasonLengthEscalationTests(unittest.TestCase):
    def test_length_triggers_extended_budget_retry(self) -> None:
        # First call returns finish_reason=length with a short response;
        # the extended retry should produce a longer response.
        caller = _RecordingCaller([
            _response(text="## truncated", finish_reason="length", completion_tokens=8192),
            _response(text="## full content that is longer than truncated", finish_reason="stop", completion_tokens=9000),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 2)
        # First call uses default budget; second uses extended.
        self.assertEqual(caller.calls[0][0].max_output_tokens, 8192)
        self.assertEqual(caller.calls[1][0].max_output_tokens, 12288)
        self.assertTrue(result.sections[0].extended_budget_used)
        self.assertEqual(result.sections[0].finish_reason, "stop")

    def test_length_does_not_trigger_extended_when_response_shorter(self) -> None:
        # Extended response is shorter than the original -> keep original.
        caller = _RecordingCaller([
            _response(text="## truncated long content here", finish_reason="length", completion_tokens=8192),
            _response(text="## short", finish_reason="stop", completion_tokens=100),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        # Two calls were made (default + extended retry), but the
        # original was kept because the extended was shorter.
        self.assertEqual(len(caller.calls), 2)
        self.assertFalse(result.sections[0].extended_budget_used)
        self.assertIn("truncated long content", result.sections[0].text)

    def test_stop_finish_reason_does_not_trigger_extended(self) -> None:
        caller = _RecordingCaller([
            _response(text="## content", finish_reason="stop"),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        self.assertFalse(result.sections[0].extended_budget_used)

    def test_content_filter_finish_reason_does_not_trigger_extended(self) -> None:
        caller = _RecordingCaller([
            _response(text="## content", finish_reason="content_filter"),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        self.assertFalse(result.sections[0].extended_budget_used)

    def test_blocked_response_does_not_trigger_extended(self) -> None:
        caller = _RecordingCaller([
            _response(text="", finish_reason="length", blocked_reason="content_filter"),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        self.assertFalse(result.sections[0].extended_budget_used)


class CumulativeBudgetTests(unittest.TestCase):
    def test_cumulative_budget_cap_is_24576(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_cap, 24576)
        self.assertEqual(result.cumulative_budget_cap, writer_cumulative_budget())

    def test_cumulative_budget_consumed_uses_completion_tokens(self) -> None:
        caller = _RecordingCaller([
            _response(completion_tokens=1000),
            _response(completion_tokens=2000),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 3000)
        self.assertFalse(result.cumulative_budget_exhausted)

    def test_cumulative_budget_exhaustion_stops_further_calls(self) -> None:
        # First call consumes the entire 24576 budget; second section
        # should get a placeholder and no further LLM call.
        caller = _RecordingCaller([
            _response(completion_tokens=24576),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        self.assertTrue(result.cumulative_budget_exhausted)
        self.assertEqual(len(result.sections), 2)
        self.assertEqual(result.sections[0].finish_reason, "stop")
        self.assertEqual(result.sections[1].finish_reason, "skipped_cumulative_budget_exhausted")
        self.assertIn("writer_placeholder", result.sections[1].text)

    def test_cumulative_budget_exhaustion_uses_placeholder_text(self) -> None:
        caller = _RecordingCaller([
            _response(completion_tokens=24576),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b", "Background")],
            llm_caller=caller,
        )
        self.assertIn("## Background", result.sections[1].text)
        self.assertIn("cumulative_budget_exhausted", result.sections[1].text)

    def test_cumulative_budget_cap_clamps_consumed(self) -> None:
        # completion_tokens > cap should clamp to cap.
        caller = _RecordingCaller([
            _response(completion_tokens=99999),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 24576)
        self.assertTrue(result.cumulative_budget_exhausted)

    def test_next_call_is_limited_to_remaining_cumulative_budget(self) -> None:
        caller = _RecordingCaller([
            _response(completion_tokens=8000),
            _response(completion_tokens=8000),
            _response(completion_tokens=8000),
            _response(completion_tokens=576),
        ])
        write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b"), _section("c"), _section("d")],
            llm_caller=caller,
        )
        self.assertEqual(caller.calls[3][0].max_output_tokens, 576)


class TokenUsageFallbackTests(unittest.TestCase):
    def test_estimated_output_tokens_is_zero_only_for_empty_text(self) -> None:
        from code2paper.llm.section_writer import _estimated_output_tokens

        self.assertEqual(_estimated_output_tokens(""), 0)
        self.assertEqual(_estimated_output_tokens(None), 0)
        # Every non-empty response is charged at least one token, including
        # one-to-three character bodies such as the schema-failed ``{}``.
        for text in ("{}", "x", "ab", "123", "a" * 4, "a" * 400):
            self.assertGreaterEqual(_estimated_output_tokens(text), 1)
        self.assertEqual(_estimated_output_tokens("a" * 400), 100)
        self.assertEqual(_estimated_output_tokens("abcd"), 1)

    def test_missing_completion_tokens_falls_back_to_text_length(self) -> None:
        # No token_usage -> fall back to len(text) // 4.
        from code2paper.export.run_manifest import hash_text

        text = "x" * 400  # 100 tokens via the // 4 fallback.
        response = LLMResponse(
            text=text,
            response_hash=hash_text(text),
            finish_reason="stop",
            token_usage=None,
        )
        caller = _RecordingCaller([response])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 100)

    def test_short_nonempty_response_without_usage_counts_at_least_one(self) -> None:
        # A one-to-three character non-empty response must never consume zero
        # budget: it is charged the shared minimum estimate of one token.
        from code2paper.export.run_manifest import hash_text

        response = LLMResponse(
            text="{}",
            response_hash=hash_text("{}"),
            finish_reason="stop",
            token_usage=None,
        )
        caller = _RecordingCaller([response])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 1)

    def test_empty_token_usage_falls_back_to_text_length(self) -> None:
        from code2paper.export.run_manifest import hash_text

        text = "y" * 80  # 20 tokens via the // 4 fallback.
        response = LLMResponse(
            text=text,
            response_hash=hash_text(text),
            finish_reason="stop",
            token_usage={},
        )
        caller = _RecordingCaller([response])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 20)


class TraceEmissionTests(unittest.TestCase):
    def test_each_call_emits_a_trace(self) -> None:
        caller = _RecordingCaller([
            _response(),
            _response(),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b")],
            llm_caller=caller,
        )
        self.assertEqual(len(result.traces), 2)
        for trace in result.traces:
            self.assertEqual(trace.role, METHOD_WRITER)

    def test_trace_records_extended_budget_used(self) -> None:
        caller = _RecordingCaller([
            _response(text="short", finish_reason="length", completion_tokens=100),
            _response(text="much longer extended response content", finish_reason="stop", completion_tokens=200),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(result.traces), 2)
        self.assertFalse(result.traces[0].extended_budget_used)
        self.assertTrue(result.traces[1].extended_budget_used)

    def test_trace_records_cumulative_budget_consumed(self) -> None:
        caller = _RecordingCaller([
            _response(completion_tokens=1000),
            _response(completion_tokens=2000),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b")],
            llm_caller=caller,
        )
        self.assertEqual(result.traces[0].cumulative_budget_consumed, 1000)
        self.assertEqual(result.traces[1].cumulative_budget_consumed, 3000)

    def test_trace_records_effective_temperature(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(
            result.traces[0].effective_config.temperature,
            ROLE_GENERATION_CONFIGS[METHOD_WRITER].temperature,
        )


class ErrorHandlingTests(unittest.TestCase):
    def test_llm_exception_does_not_crash_writer(self) -> None:
        class _ExplodingCaller:
            def __call__(self, config: LLMConfig, request: LLMRequest) -> LLMResponse:
                raise RuntimeError("boom")

        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=_ExplodingCaller(),  # type: ignore[arg-type]
        )
        self.assertEqual(len(result.sections), 1)
        self.assertTrue(result.sections[0].blocked_reason)
        self.assertIn("section_writer_llm_error", result.sections[0].blocked_reason)

    def test_empty_response_text_uses_placeholder(self) -> None:
        caller = _RecordingCaller([_response(text="")])
        result = write_method_by_sections(
            _base_config(),
            [_section("a", "Overview")],
            llm_caller=caller,
        )
        self.assertEqual(len(result.sections), 1)
        self.assertIn("## Overview", result.sections[0].text)
        self.assertIn("writer_placeholder", result.sections[0].text)


class AggregateResultTests(unittest.TestCase):
    def test_to_json_dict_has_expected_keys(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        data = result.to_json_dict()
        self.assertIn("sections", data)
        self.assertIn("traces", data)
        self.assertIn("cumulative_budget_consumed", data)
        self.assertIn("cumulative_budget_cap", data)
        self.assertIn("cumulative_budget_exhausted", data)
        self.assertIn("concatenated_markdown_length", data)

    def test_to_json_dict_section_entries_have_expected_fields(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        data = result.to_json_dict()
        section_entry = data["sections"][0]
        self.assertEqual(section_entry["section_id"], "a")
        self.assertIn("text_length", section_entry)
        self.assertIn("finish_reason", section_entry)
        self.assertIn("extended_budget_used", section_entry)
        self.assertIn("blocked_reason", section_entry)


class EmptySectionsTests(unittest.TestCase):
    def test_empty_sections_returns_empty_result(self) -> None:
        caller = _RecordingCaller([])
        result = write_method_by_sections(
            _base_config(),
            [],
            llm_caller=caller,
        )
        self.assertEqual(len(result.sections), 0)
        self.assertEqual(len(result.traces), 0)
        self.assertEqual(result.cumulative_budget_consumed, 0)
        self.assertFalse(result.cumulative_budget_exhausted)
        self.assertEqual(result.concatenated_markdown, "")


class DynamicPublicationBudgetTests(unittest.TestCase):
    def test_compact_research_callback_is_bound_to_current_section(self) -> None:
        text, fields = _decode_publication_research_requests(
            json.dumps({
                "new_research_requests": [{
                    "move": "inference_and_output",
                    "reason": "Which validated artifact establishes the returned output?",
                    "status": "unresolved",
                }]
            }),
            section_id="MA-S1",
            argument_graph={
                "argument_unit_ids": ["MA-S1:unit"],
                "moves": [{
                    "move": "inference_and_output",
                    "allowed_authority_lanes": ["executable_hard"],
                }],
            },
        )
        payload = json.loads(text)
        request = payload["new_research_requests"][0]
        self.assertEqual(fields, ["new_research_requests[0]"])
        self.assertEqual(request["request_id"], "request:MA-S1:inference_and_output:1")
        self.assertEqual(request["section_id"], "MA-S1")
        self.assertEqual(request["argument_unit_id"], "MA-S1:unit")
        self.assertEqual(request["status"], "open")
        self.assertEqual(request["required_authority_lane"], "executable_hard")

    def test_scalar_binding_tokens_bridge_back_to_exact_arrays(self) -> None:
        contract = {
            "used_claim_ids": ["claim:1", "claim:2"],
            "completed_rhetorical_moves": ["mechanism_overview"],
        }
        text, fields = _decode_publication_binding_tokens(
            json.dumps({
                "section_id": "mechanism",
                "section_markdown": "A sufficiently grounded section.",
                "used_claim_ids": '["claim:1","claim:2"]',
                "completed_rhetorical_moves": '["mechanism_overview"]',
            }),
            contract,
        )
        payload = json.loads(text)
        self.assertEqual(payload["used_claim_ids"], ["claim:1", "claim:2"])
        self.assertEqual(payload["completed_rhetorical_moves"], ["mechanism_overview"])
        self.assertEqual(fields, ["used_claim_ids", "completed_rhetorical_moves"])

    def test_fulfilled_callback_move_metadata_is_bridged_without_reopening_request(self) -> None:
        text, fields = _decode_publication_callback_moves(
            json.dumps({
                "section_markdown": "The author-confirmed objective is stated here.",
                "completed_rhetorical_moves": [],
                "new_research_requests": [],
            }),
            resolution={
                "fulfilled_moves": [{
                    "move": "design_objective",
                    "argument_unit_id": "MA-S1:unit",
                    "authority_lane": "author_attested",
                }],
            },
        )
        payload = json.loads(text)
        assert payload["completed_rhetorical_moves"] == ["design_objective"]
        assert fields == ["completed_rhetorical_moves:design_objective"]

        untouched, untouched_fields = _decode_publication_callback_moves(
            json.dumps({
                "completed_rhetorical_moves": [],
                "new_research_requests": [{
                    "missing_rhetorical_move": "design_objective",
                }],
            }),
            resolution={"fulfilled_moves": [{"move": "design_objective"}]},
        )
        assert json.loads(untouched)["completed_rhetorical_moves"] == []
        assert untouched_fields == []

    def test_publication_schema_closes_binding_ids_and_required_moves(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1", "claim:2"],
                    "used_equation_ids": [],
                    "used_configuration_ids": ["config:1"],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                }
            },
            argument_graph={
                "moves": [
                    {"move": "mechanism_overview", "required": True},
                    {"move": "transition_to_next_section", "required": False},
                ]
            },
            publication_mode=True,
        )
        caller = _RecordingCaller([_response()])

        write_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
            response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
            publication_mode=True,
        )

        schema = caller.calls[0][1].response_json_schema
        self.assertEqual(schema["properties"]["section_id"]["const"], "mechanism")
        self.assertEqual(schema["properties"]["section_markdown"]["minLength"], 180)
        self.assertEqual(schema["properties"]["section_markdown"]["maxLength"], 4800)
        claims = schema["properties"]["used_claim_ids"]
        self.assertEqual(claims["type"], "array")
        self.assertEqual(claims["items"]["enum"], ["claim:1", "claim:2"])
        self.assertEqual(schema["properties"]["used_equation_ids"]["items"], {"type": "string"})
        moves = schema["properties"]["completed_rhetorical_moves"]
        self.assertEqual(moves["items"]["enum"], ["mechanism_overview"])
        self.assertEqual(list(schema["properties"])[-1], "section_markdown")

    def test_publication_schema_allows_bounded_subsets_when_callback_is_required(self) -> None:
        section = WriterSectionInput(
            section_id="callback",
            heading="Callback",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview", "inference_and_output"],
                },
                "grounding_contract": {"callback_required": True},
            },
            argument_graph={"moves": [{"paragraph_budget": 1}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response()])

        write_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
            response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
            publication_mode=True,
        )

        schema = caller.calls[0][1].response_json_schema
        self.assertEqual(schema["properties"]["used_claim_ids"]["type"], "array")
        self.assertEqual(
            schema["properties"]["completed_rhetorical_moves"]["items"]["enum"],
            ["mechanism_overview", "inference_and_output"],
        )

    def test_publication_schema_requires_callbacks_when_move_is_unanchored(self) -> None:
        """Stage 5: when a section has unanchored required moves, the output
        schema requires a non-empty ``new_research_requests`` with closed-set
        bindings, so guided decoding cannot silently return ``[]``.  The
        harness contract validator still rejects fabricated requests."""
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Transformation and output",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["MA-S1:unit"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
                "grounding_contract": {
                    "callback_required": True,
                    "unanchored_required_moves": ["limitations_or_mismatch"],
                    "move_authority": {
                        "limitations_or_mismatch": {
                            "required": True,
                            "state": "open",
                            "required_authority_lane": "executable_hard",
                        }
                    },
                },
            },
            argument_graph={
                "argument_unit_ids": ["MA-S1:unit"],
                "moves": [
                    {"move": "limitations_or_mismatch", "argument_unit_ids": ["MA-S1:unit"], "required": True},
                ],
            },
            publication_mode=True,
        )
        caller = _RecordingCaller([_response()])

        write_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
            response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
            publication_mode=True,
        )

        schema = caller.calls[0][1].response_json_schema
        self.assertIn("new_research_requests", schema["required"])
        requests = schema["properties"]["new_research_requests"]
        self.assertEqual(requests["minItems"], 1)
        item = requests["items"]
        self.assertEqual(item["properties"]["section_id"]["const"], "MA-S1")
        self.assertEqual(
            item["properties"]["missing_rhetorical_move"]["enum"],
            ["limitations_or_mismatch"],
        )
        self.assertEqual(
            item["properties"]["required_authority_lane"]["enum"],
            ["executable_hard"],
        )
        self.assertEqual(
            item["properties"]["argument_unit_id"]["enum"],
            ["MA-S1:unit"],
        )
        self.assertEqual(item["properties"]["status"]["const"], "open")
        self.assertEqual(item["properties"]["exact_question"]["minLength"], 5)
        # Local lanes require at least one exact candidate term so the
        # harness contract (subset of authorized terms) is satisfiable.
        self.assertIn("candidate_symbols_or_terms", item["required"])
        self.assertEqual(
            item["properties"]["candidate_symbols_or_terms"]["minItems"],
            1,
        )

    def test_publication_schema_keeps_callbacks_optional_without_unanchored_moves(self) -> None:
        """A section with no unanchored moves must not be forced to emit
        research requests."""
        section = WriterSectionInput(
            section_id="MA-S2",
            heading="Extraction",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["MA-S2:unit"],
                    "used_claim_ids": [],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": [],
                },
                "grounding_contract": {"callback_required": False},
            },
            argument_graph={"argument_unit_ids": ["MA-S2:unit"], "moves": []},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response()])

        write_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
            response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
            publication_mode=True,
        )

        schema = caller.calls[0][1].response_json_schema
        self.assertNotIn("new_research_requests", schema["required"])
        self.assertNotIn(
            "minItems",
            schema["properties"]["new_research_requests"],
        )
        self.assertEqual(
            schema["properties"]["new_research_requests"].get("maxItems"),
            0,
        )

    def test_publication_schema_external_lane_callbacks_do_not_require_candidates(self) -> None:
        """Author-attested/external lanes need no candidate terms: the
        request is routed to an external queue, not repository tools."""
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Limitations",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["MA-S1:unit"],
                    "used_claim_ids": [],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": [],
                },
                "grounding_contract": {
                    "callback_required": True,
                    "unanchored_required_moves": ["limitations_or_mismatch"],
                    "move_authority": {
                        "limitations_or_mismatch": {
                            "required": True,
                            "state": "external_pending",
                            "required_authority_lane": "author_attested",
                        }
                    },
                },
            },
            argument_graph={
                "argument_unit_ids": ["MA-S1:unit"],
                "moves": [
                    {"move": "limitations_or_mismatch", "argument_unit_ids": ["MA-S1:unit"], "required": True},
                ],
            },
            publication_mode=True,
        )
        caller = _RecordingCaller([_response()])

        write_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
            response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
            publication_mode=True,
        )

        schema = caller.calls[0][1].response_json_schema
        item = schema["properties"]["new_research_requests"]["items"]
        self.assertNotIn("candidate_symbols_or_terms", item["required"])

    def test_publication_schema_keeps_concept_sidecar_fields_optional(self) -> None:
        """Harness-owned concept bindings are restored after Writer parsing."""
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Transformation and output",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["MA-S1:unit"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
                "grounding_contract": {
                    "callback_required": True,
                    "unanchored_required_moves": ["limitations_or_mismatch"],
                    "move_authority": {
                        "limitations_or_mismatch": {
                            "required": True,
                            "state": "open",
                            "required_authority_lane": "executable_hard",
                        }
                    },
                    "callback_request_prototypes": [{
                        "concept_binding": [{
                            "concept_key": "CK-C",
                            "missing_parts": ["exact standardization formula"],
                            "evidence_refs_used": ["span:gaussian.py:10:12"],
                        }],
                    }],
                },
            },
            argument_graph={
                "argument_unit_ids": ["MA-S1:unit"],
                "moves": [
                    {"move": "limitations_or_mismatch", "argument_unit_ids": ["MA-S1:unit"], "required": True},
                ],
            },
            publication_mode=True,
        )
        caller = _RecordingCaller([_response()])

        write_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
            response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
            publication_mode=True,
        )

        schema = caller.calls[0][1].response_json_schema
        item = schema["properties"]["new_research_requests"]["items"]
        self.assertNotIn("concept_key", item["required"])
        self.assertNotIn("missing_parts", item["required"])
        self.assertNotIn("evidence_refs_used", item["required"])

    def test_stop_response_with_wrong_section_binding_is_rejected(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            "section_id": "other-section",
            "section_markdown": "A grounded mechanism explanation.",
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:1"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": ["mechanism_overview"],
        }))])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(result.outputs, [])
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertIn("publication_section_binding_failed", result.aggregate.sections[0].blocked_reason)

    def test_unique_casefold_section_binding_is_recovered_from_scoped_call(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism-f6Cf",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            # The model changed the case of the hexadecimal suffix.  The
            # scoped request remains the only authority for the canonical id.
            "section_id": "MECHANISM-F6cf",
            "section_markdown": "A grounded mechanism explanation.",
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:1"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": ["mechanism_overview"],
        }))])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(result.outputs), 1)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(result.outputs[0].section_id, "mechanism-f6Cf")
        self.assertTrue(any(
            item.get("operation") == "repair_casefold_section_id"
            for item in result.aggregate.response_recovery_traces
        ))

    def test_empty_section_binding_is_recovered_from_scoped_call(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            # Qwen-class JSON-object responses can omit this metadata field;
            # the request's scoped section is the only safe recovery source.
            "section_markdown": "A grounded mechanism explanation.",
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:1"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": ["mechanism_overview"],
        }))])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(result.outputs[0].section_id, "mechanism")
        self.assertFalse(result.aggregate.sections[0].incomplete)

    def test_publication_length_retry_exposes_only_accepted_attempt(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(markdown: str) -> str:
            return json.dumps({
                "section_id": "mechanism",
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            _response(
                text=payload("A short attempt."),
                finish_reason="length",
                completion_tokens=8192,
            ),
            _response(
                text=payload("A longer accepted mechanism sentence."),
                finish_reason="stop",
                completion_tokens=9000,
            ),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(
            result.outputs[0].section_markdown,
            "A longer accepted mechanism sentence.",
        )
        self.assertEqual(result.aggregate.research_requests, [])
        self.assertEqual(len(result.aggregate.traces), 2)

    def test_publication_schema_binding_failure_triggers_owner_retry(self) -> None:
        """A finish_reason=stop response that fails schema/binding must
        trigger one bounded owner retry carrying the parse error.

        Regression: the section writer only retried on
        ``finish_reason=length``, so a wrong-section binding (or an empty
        JSON object ``{}``) with ``finish_reason=stop`` produced an
        incomplete section with no second chance — the owning Agent never
        got to see its own error and regenerate.
        """
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(section_id: str, markdown: str) -> str:
            return json.dumps({
                "section_id": section_id,
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: wrong section_id -> binding failure, finish_reason=stop.
            _response(text=payload("other-section", "wrong section binding.")),
            # Retry: correct section_id -> binding passes.
            _response(text=payload("mechanism", "A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        # Two calls: default + owner retry.
        self.assertEqual(len(caller.calls), 2)
        # The retry request carries the parse error from the first attempt.
        retry_payload = caller.calls[1][1].input_payload
        self.assertIn("previous_attempt_error", retry_payload)
        self.assertIn(
            "publication_section_binding_failed",
            str(retry_payload["previous_attempt_error"]),
        )
        # The retry resolved the failure: the section is accepted.
        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(result.outputs[0].section_id, "mechanism")
        self.assertFalse(result.aggregate.sections[0].incomplete)
        # Both attempts are recorded as traces.
        self.assertEqual(len(result.aggregate.traces), 2)

    def test_publication_request_exposes_exact_heading_to_writer(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Feature extraction and normalization",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": [],
                    "used_claim_ids": [],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": [],
                },
            },
            argument_graph={"moves": []},
            publication_mode=True,
        )

        def caller(_config, request):
            self.assertEqual(
                request.input_payload["heading"],
                "Feature extraction and normalization",
            )
            return _response(text=json.dumps({
                "section_id": "mechanism",
                "section_markdown": "## Feature extraction and normalization\n\nMethod prose.",
                "used_argument_unit_ids": [],
                "used_claim_ids": [],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": [],
                "new_research_requests": [],
            }))

        result = write_publication_method_by_sections(
            _base_config(), [section], llm_caller=caller,
        )
        self.assertEqual(len(result.outputs), 1)

    def test_publication_schema_binding_retry_failure_keeps_incomplete(self) -> None:
        """When the owner retry also fails schema/binding, the section must
        stay a credible incomplete — the rule layer never patches prose."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(section_id: str) -> str:
            return json.dumps({
                "section_id": section_id,
                "section_markdown": "binding mismatch.",
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: wrong section binding.
            _response(text=payload("other-section")),
            # Retry: still wrong section binding — second failure.
            _response(text=payload("still-wrong")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        # Two calls happened (default + retry), but the section stays incomplete.
        self.assertEqual(len(caller.calls), 2)
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.outputs), 0)
        self.assertEqual(len(result.aggregate.traces), 2)

    def test_publication_empty_object_schema_failure_triggers_owner_retry(self) -> None:
        """An empty JSON object ``{}`` with finish_reason=stop is a schema
        failure; one bounded owner retry carrying the parse error must
        regenerate a valid section (exactly two calls, two traces)."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(markdown: str) -> str:
            return json.dumps({
                "section_id": "mechanism",
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: empty object -> schema failure, finish_reason=stop.
            _response(text="{}"),
            # Retry: valid section object -> schema passes.
            _response(text=payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        # Two calls: default + owner retry.
        self.assertEqual(len(caller.calls), 2)
        retry_payload = caller.calls[1][1].input_payload
        self.assertIn("previous_attempt_error", retry_payload)
        self.assertIn(
            "publication_section_schema_failed",
            str(retry_payload["previous_attempt_error"]),
        )
        # The retry resolved the schema failure.
        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(result.outputs[0].section_markdown, "A grounded mechanism explanation.")
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.aggregate.traces), 2)

    def test_publication_empty_object_schema_failure_twice_keeps_incomplete(self) -> None:
        """Two empty-object schema failures remain incomplete after exactly
        two calls — no unbounded third path."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([
            _response(text="{}"),
            _response(text="{}"),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.outputs), 0)
        self.assertEqual(len(result.aggregate.traces), 2)

    def _publication_section(self) -> WriterSectionInput:
        return WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

    def _publication_payload(self, markdown: str) -> str:
        return json.dumps({
            "section_id": "mechanism",
            "section_markdown": markdown,
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:1"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": ["mechanism_overview"],
            "new_research_requests": [],
        })

    def test_publication_schema_failure_counts_raw_text_estimate_when_usage_absent(self) -> None:
        """A schema-failed publication call that generated non-empty output
        must count its deterministic raw-text estimate toward the cumulative
        budget even when the provider reports no token usage.

        Regression: ``structured_caller`` cleared the invalid text before
        ``_output_tokens_used`` ran, so a streaming provider without usage
        produced a zero token delta and an unauthorized retry could fire after
        the real budget was exhausted."""
        section = self._publication_section()
        raw_text = "x" * 400  # 100 tokens via the len(text)//4 fallback.
        caller = _RecordingCaller([
            _response(text=raw_text, completion_tokens=None),  # schema failure, no usage
            _response(text=self._publication_payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertEqual(len(result.outputs), 1)
        # The failed first call consumed its raw-text estimate (100), and the
        # retry consumed additional tokens: cumulative accounting is monotonic.
        self.assertGreaterEqual(result.aggregate.cumulative_budget_consumed, 100)
        trace0 = result.aggregate.traces[0]
        trace1 = result.aggregate.traces[1]
        self.assertGreaterEqual(trace0.cumulative_budget_consumed, 100)
        self.assertGreater(trace1.cumulative_budget_consumed, trace0.cumulative_budget_consumed)

    def test_publication_binding_failure_counts_raw_text_estimate_when_usage_absent(self) -> None:
        """A binding-failed publication call with non-empty output and no
        provider usage counts its raw-text estimate toward the budget (same
        accounting invariant as the schema-failure path)."""
        section = self._publication_section()
        raw_text = "y" * 200  # 50 tokens via the len(text)//4 fallback.
        wrong_binding = json.dumps({
            "section_id": "other-section",
            "section_markdown": "wrong binding.",
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:1"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": ["mechanism_overview"],
            "new_research_requests": [],
        })
        caller = _RecordingCaller([
            _response(text=wrong_binding, completion_tokens=None),  # binding failure, no usage
            _response(text=self._publication_payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertEqual(len(result.outputs), 1)
        self.assertGreaterEqual(result.aggregate.cumulative_budget_consumed, 50)
        self.assertGreater(
            result.aggregate.traces[1].cumulative_budget_consumed,
            result.aggregate.traces[0].cumulative_budget_consumed,
        )

    def test_publication_empty_object_schema_failure_without_usage_counts_at_least_one(self) -> None:
        """A schema-failed ``{}`` response with no provider usage is charged
        the shared minimum estimate of one token, not zero.

        Regression: the fallback was ``max(0, len(text) // 4)``, so the
        two-character ``{}`` body produced a zero-token delta and an owner
        retry could be authorized without accounting for the failed call."""
        section = self._publication_section()
        caller = _RecordingCaller([
            _response(text="{}", completion_tokens=None),  # schema failure, no usage
            _response(text=self._publication_payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertEqual(len(result.outputs), 1)
        trace0 = result.aggregate.traces[0]
        trace1 = result.aggregate.traces[1]
        # The failed first attempt consumed at least one token.
        self.assertGreaterEqual(trace0.cumulative_budget_consumed, 1)
        # Cumulative accounting is strictly monotonic across the retry.
        self.assertGreater(trace1.cumulative_budget_consumed, trace0.cumulative_budget_consumed)

    def test_publication_minimum_charge_consuming_remaining_budget_prevents_retry(self) -> None:
        """When the minimum one-token charge of a failed ``{}`` response
        consumes the remaining budget, the owner retry must not be authorized.

        Boundary case: the shared minimum estimate must be enforced for the
        exhausted-budget decision exactly like any larger raw-text estimate."""
        def section_input(section_id: str) -> WriterSectionInput:
            return WriterSectionInput(
                section_id=section_id,
                heading="Section",
                prompt_payload={
                    "binding_contract": {
                        "used_argument_unit_ids": ["unit:1"],
                        "used_claim_ids": ["claim:1"],
                        "used_equation_ids": [],
                        "used_configuration_ids": [],
                        "completed_rhetorical_moves": ["mechanism_overview"],
                    },
                },
                argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
                publication_mode=True,
            )

        def payload(section_id: str, markdown: str) -> str:
            return json.dumps({
                "section_id": section_id,
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        first = section_input("first")
        second = section_input("second")
        cap = dynamic_writer_cumulative_budget([first, second])
        pre_consume = cap - 1
        caller = _RecordingCaller([
            # First section consumes cap-1 tokens (valid response).
            _response(text=payload("first", "first section."), completion_tokens=pre_consume),
            # Second section: failed ``{}`` with no usage -> minimum charge 1
            # reaches the cap, so the owner retry must not fire.
            _response(text="{}", completion_tokens=None),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [first, second],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertTrue(result.aggregate.cumulative_budget_exhausted)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertTrue(result.aggregate.sections[1].incomplete)
        self.assertEqual(len(result.outputs), 1)  # only the first section accepted
        self.assertEqual(len(result.aggregate.traces), 2)
        self.assertGreaterEqual(
            result.aggregate.traces[1].cumulative_budget_consumed,
            cap,
        )

    def test_publication_schema_failure_consuming_remaining_budget_prevents_retry(self) -> None:
        """A failed raw response whose estimate consumes the remaining budget
        must prevent the unauthorized owner retry (no third call beyond the
        budget)."""
        section = self._publication_section()
        cap = dynamic_writer_cumulative_budget([section])
        # Raw text long enough that the estimate alone reaches the cap.
        raw_text = "z" * (cap * 4)
        caller = _RecordingCaller([
            _response(text=raw_text, completion_tokens=None),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 1)
        self.assertTrue(result.aggregate.cumulative_budget_exhausted)
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.outputs), 0)
        self.assertEqual(len(result.aggregate.traces), 1)
        self.assertGreaterEqual(
            result.aggregate.traces[0].cumulative_budget_consumed,
            cap,
        )

    def test_publication_owner_retry_skipped_when_budget_exhausted(self) -> None:
        """When the first call consumes the entire cumulative budget, a
        schema/binding failure must not trigger a second call — the section
        stays a credible incomplete."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([
            _response(text="{}", completion_tokens=24576),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 1)
        self.assertTrue(result.aggregate.cumulative_budget_exhausted)
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.outputs), 0)

    def test_publication_hard_provider_block_not_retried_by_owner_path(self) -> None:
        """A hard non-schema provider block (content filtering) with
        finish_reason=stop must not trigger the schema/binding owner retry —
        only typed schema/binding failures are repairable by the owning
        Agent."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([
            _response(text="", completion_tokens=0, blocked_reason="content_filter"),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 1)
        self.assertTrue(result.aggregate.sections[0].incomplete)

    def test_publication_owner_retry_discards_failed_attempt_metadata(self) -> None:
        """Research/callback metadata from a discarded wrong-binding attempt
        is not consumed or duplicated into the aggregate after the owner
        retry succeeds."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(section_id: str, markdown: str, research=()) -> str:
            return json.dumps({
                "section_id": section_id,
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": list(research),
            })

        caller = _RecordingCaller([
            _response(text=payload("other-section", "wrong.", research=[{
                "move": "mechanism_overview",
                "reason": "why?",
                "status": "open",
            }])),
            _response(text=payload("mechanism", "right.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertEqual(len(result.outputs), 1)
        # The discarded attempt's callback metadata is not consumed.
        self.assertEqual(result.aggregate.research_requests, [])

    def test_publication_structured_complete_schema_failure_triggers_owner_retry(self) -> None:
        """A schema failure carried by the streaming client's
        ``structured_complete`` finish reason must still trigger the one
        bounded owner retry.

        Regression: the owner-retry gate required ``finish_reason ==
        "stop"``, so live streaming responses that failed schema validation
        (``finish_reason="structured_complete"``) became incomplete with no
        second chance for the owning Agent."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(markdown: str) -> str:
            return json.dumps({
                "section_id": "mechanism",
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: malformed JSON -> schema failure carried with the
            # streaming client's structured_complete finish reason.
            _response(text='{"section_markdown": "truncated', finish_reason="structured_complete"),
            # Retry: valid response.
            _response(text=payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        retry_payload = caller.calls[1][1].input_payload
        self.assertIn("previous_attempt_error", retry_payload)
        self.assertIn(
            "publication_section_schema_failed",
            str(retry_payload["previous_attempt_error"]),
        )
        self.assertEqual(len(result.outputs), 1)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.aggregate.traces), 2)
        self.assertTrue(
            str(caller.calls[1][1].prompt_template_id).endswith("_representation_repair_v1")
        )
        self.assertIn("representation-retry", result.aggregate.traces[1].call_id)

    def test_publication_closed_set_claim_binding_failure_triggers_owner_retry(self) -> None:
        """A near-miss closed-set claim id (transposed characters) is a
        binding failure at the writer boundary and receives one bounded
        owner retry.

        Regression: closed-set claim/equation/config ids were only checked
        after the writer returned, so an invented or transposed id produced
        an unbounded run-level rejection with no owner repair."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:abc123", "claim:def456"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(claim_ids) -> str:
            return json.dumps({
                "section_id": "mechanism",
                "section_markdown": "A grounded mechanism explanation.",
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": list(claim_ids),
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: claim id with a transposed character -> closed-set
            # binding failure at the writer boundary.
            _response(text=payload(["claim:abc123", "claim:def465"])),
            # Retry: exact authorized claim ids -> binding passes.
            _response(text=payload(["claim:abc123", "claim:def456"])),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        retry_payload = caller.calls[1][1].input_payload
        self.assertIn("previous_attempt_error", retry_payload)
        self.assertIn(
            "publication_section_binding_failed",
            str(retry_payload["previous_attempt_error"]),
        )
        self.assertIn("unknown_claims", str(retry_payload["previous_attempt_error"]))
        self.assertEqual(len(result.outputs), 1)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.aggregate.traces), 2)
        self.assertTrue(
            str(caller.calls[1][1].prompt_template_id).endswith("_representation_repair_v1")
        )
        self.assertIn("representation-retry", result.aggregate.traces[1].call_id)


    def test_publication_missing_bindings_are_not_writer_failures(self) -> None:
        """Content-first writer semantics: the prose call is never required to
        complete every full id/config/equation/move binding.  A response that
        omits binding ids (or binds only a subset) passes the writer boundary;
        post-processing / validation decides verified inclusion."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:abc123", "claim:def456"],
                    "used_equation_ids": [],
                    "used_configuration_ids": ["config:1"],
                    "completed_rhetorical_moves": ["mechanism_overview", "inference_and_output"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            "section_id": "mechanism",
            "section_markdown": "A grounded mechanism explanation.",
            "used_argument_unit_ids": ["unit:1"],
            # Only one of the two authorized claims is bound; none of the
            # equations/configurations/moves metadata is completed.
            "used_claim_ids": ["claim:abc123"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": [],
            "new_research_requests": [],
        }))])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 1)
        self.assertEqual(len(result.outputs), 1)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(result.outputs[0].used_claim_ids, ["claim:abc123"])

    def test_publication_unknown_binding_id_still_fails_closed(self) -> None:
        """Missing ids are post-processing concerns, but an *invented* id is
        a representation defect: the harness never accepts an id the author
        never authorized."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:abc123"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            "section_id": "mechanism",
            "section_markdown": "A grounded mechanism explanation.",
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:invented"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": [],
            "new_research_requests": [],
        }))])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(result.outputs, [])
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertIn(
            "unknown_claims",
            result.aggregate.sections[0].blocked_reason,
        )

    def test_missing_required_briefs_keep_authored_markdown(self) -> None:
        """DyG 111122 / LinearRAG 100052: deferred primary briefs must not
        erase section_markdown. Candidate keeps the body; invented ids still
        discard."""
        body = (
            "## Overview\n\n"
            "The encoder applies softmax routing to temporal embeddings."
        )
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Overview",
            prompt_payload={
                "writer_view": {
                    "positive_briefs": [{"brief_id": "brief:primary"}],
                    "caveated_briefs": [{"brief_id": "brief:other"}],
                },
                "binding_contract": {
                    "primary_brief_ids": ["brief:primary", "brief:other"],
                    "required_brief_ids": ["brief:primary", "brief:other"],
                    "allowed_brief_ids": ["brief:primary", "brief:other"],
                },
            },
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            "section_id": "MA-S1",
            "heading_text": "Overview",
            "section_markdown": body,
            "rendered_brief_ids": ["brief:primary"],
            "deferred_brief_ids": ["brief:other"],
            "new_research_requests": [],
        }))])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(result.outputs[0].section_markdown, body)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(result.outputs[0].rendered_brief_ids, ["brief:primary"])
        self.assertEqual(result.outputs[0].deferred_brief_ids, ["brief:other"])

    def test_unknown_brief_id_still_discards_response(self) -> None:
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Overview",
            prompt_payload={
                "writer_view": {
                    "positive_briefs": [{"brief_id": "brief:primary"}],
                },
                "binding_contract": {
                    "primary_brief_ids": ["brief:primary"],
                    "allowed_brief_ids": ["brief:primary"],
                },
            },
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            "section_id": "MA-S1",
            "heading_text": "Overview",
            "section_markdown": "## Overview\n\nThe encoder applies softmax routing.",
            "rendered_brief_ids": ["brief:invented"],
            "deferred_brief_ids": [],
            "new_research_requests": [],
        }))])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )
        self.assertEqual(result.outputs, [])
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertIn("unknown_rendered_briefs", result.aggregate.sections[0].blocked_reason)


    def test_argument_plan_sets_dynamic_budget_below_global_cap(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "equation_ids": ["eq:1"],
                "configuration_ids": ["cfg:1", "cfg:2"],
            },
            argument_graph={
                "argument_unit_ids": ["unit:1", "unit:2"],
                "moves": [
                    {"paragraph_budget": 1},
                    {"paragraph_budget": 2},
                ],
            },
            publication_mode=True,
        )

        budget = dynamic_writer_cumulative_budget([section])

        self.assertGreater(budget, 2048)
        self.assertLess(budget, writer_cumulative_budget())

    def test_legacy_inputs_keep_audited_global_cap(self) -> None:
        self.assertEqual(
            dynamic_writer_cumulative_budget([_section("legacy")]),
            writer_cumulative_budget(),
        )


class CustomCallIdPrefixTests(unittest.TestCase):
    def test_custom_call_id_prefix_appears_in_traces(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("overview")],
            llm_caller=caller,
            call_id_prefix="LLM-method-overview",
        )
        self.assertTrue(
            result.traces[0].call_id.startswith("LLM-method-overview"),
            f"call_id was {result.traces[0].call_id}",
        )


class ParagraphTransactionTests(unittest.TestCase):
    def _anchored_field_section(self) -> tuple[WriterSectionInput, dict[str, Any]]:
        plan_row = {
            "paragraph_id": "MA-S1:p1",
            "required_field_candidate_ids": ["field:op"],
            "witness_contract": {
                "targets": [{
                    "target_kind": "field",
                    "target_id": "field:op",
                    "semantic_atom": "normalize inputs",
                    "required_conditions": ["when score exceeds threshold"],
                    "allowed_exact_excerpts": ["normalize inputs"],
                }]
            },
        }
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Encoder",
            publication_mode=True,
            argument_graph={"paragraphs": [plan_row]},
            prompt_payload={
                "writer_view": {
                    "mechanism_authoring_packet": {"facets": []}
                }
            },
        )
        return section, plan_row

    def test_metadata_binder_closes_frozen_paraphrase(self) -> None:
        section, _plan_row = self._anchored_field_section()
        output = PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            paragraphs=[PublicationMethodParagraphOutputV1(
                paragraph_id="MA-S1:p1",
                paragraph_markdown=(
                    "The method performs normalize inputs when score exceeds "
                    "threshold."
                ),
                rendered_field_candidate_ids=["field:op"],
            )],
        )
        binder_json = json.dumps({
            "paragraph_id": "MA-S1:p1",
            "witnesses": [{
                "witness_kind": "field",
                "target_id": "field:op",
                "exact_text": (
                    "The method performs normalize inputs when score exceeds "
                    "threshold."
                ),
            }],
            "unbound_target_ids": [],
        })
        caller = _RecordingCaller([_response(text=binder_json, completion_tokens=3)])

        normalized, failures = _normalize_publication_paragraph_transaction(
            output,
            section=section,
            require_transactions=True,
            binder_caller=caller,
            binder_base_config=_base_config(),
        )

        self.assertEqual(failures, [])
        self.assertEqual(len(caller.calls), 1)
        self.assertEqual(caller.calls[0][0].role, "semantic_verifier")
        self.assertEqual(caller.calls[0][0].temperature, 0.0)
        self.assertEqual(
            normalized.paragraphs[0].witnesses[0].exact_text,
            "The method performs normalize inputs when score exceeds threshold.",
        )

    def test_metadata_binder_representation_retry_is_bounded(self) -> None:
        section, _plan_row = self._anchored_field_section()
        output = PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            paragraphs=[PublicationMethodParagraphOutputV1(
                paragraph_id="MA-S1:p1",
                paragraph_markdown=(
                    "The method performs normalize inputs when score exceeds "
                    "threshold."
                ),
                rendered_field_candidate_ids=["field:op"],
            )],
        )
        invalid_json = json.dumps({
            "paragraph_id": "MA-S1:p1",
            "witnesses": [{
                "witness_kind": "field",
                "target_id": "field:op",
                "exact_text": "not present",
            }],
            "unbound_target_ids": [],
        })
        valid_json = json.dumps({
            "paragraph_id": "MA-S1:p1",
            "witnesses": [{
                "witness_kind": "field",
                "target_id": "field:op",
                "exact_text": (
                    "The method performs normalize inputs when score exceeds "
                    "threshold."
                ),
            }],
            "unbound_target_ids": [],
        })
        caller = _RecordingCaller([
            _response(text=invalid_json, completion_tokens=3),
            _response(text=valid_json, completion_tokens=3),
        ])

        normalized, failures = _normalize_publication_paragraph_transaction(
            output,
            section=section,
            require_transactions=True,
            binder_caller=caller,
            binder_base_config=_base_config(),
        )

        self.assertEqual(failures, [])
        self.assertEqual(len(caller.calls), 2)
        self.assertEqual(len(normalized.paragraphs[0].witnesses), 1)

    def test_sidecar_restores_omitted_target_before_binder(self) -> None:
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Ranking",
            publication_mode=True,
            argument_graph={"paragraphs": [{
                "paragraph_id": "MA-S1:p1",
                "required_facet_ids": ["facet:ranking"],
                "witness_contract": {"targets": [{
                    "target_kind": "facet",
                    "target_id": "facet:ranking",
                    "semantic_atom": "embedding-based reranking formulation",
                }]},
            }]},
            prompt_payload={"writer_view": {"mechanism_authoring_packet": {"facets": []}}},
        )
        output = PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            paragraphs=[PublicationMethodParagraphOutputV1(
                paragraph_id="MA-S1:p1",
                paragraph_markdown=(
                    "The model produces embedding-based reranking scores. "
                    "This embedding-based reranking representation is used downstream."
                ),
            )],
        )
        binder_json = json.dumps({
            "paragraph_id": "MA-S1:p1",
            "witnesses": [{
                "witness_kind": "facet",
                "target_id": "facet:ranking",
                "exact_text": "The model produces embedding-based reranking scores.",
            }],
            "unbound_target_ids": [],
        })
        caller = _RecordingCaller([_response(text=binder_json, completion_tokens=3)])

        targets = paragraph_binding_targets(
            output.paragraphs[0],
            plan_row=section.argument_graph["paragraphs"][0],
        )
        self.assertEqual(
            [(item["witness_kind"], item["target_id"]) for item in targets],
            [("facet", "facet:ranking")],
        )
        normalized, failures = _normalize_publication_paragraph_transaction(
            output,
            section=section,
            require_transactions=True,
            binder_caller=caller,
            binder_base_config=_base_config(),
        )

        self.assertEqual(failures, [])
        self.assertEqual(len(caller.calls), 1)
        self.assertEqual(
            normalized.paragraphs[0].rendered_from_facet_ids,
            ["facet:ranking"],
        )
        self.assertEqual(
            normalized.paragraphs[0].witnesses[0].exact_text,
            "The model produces embedding-based reranking scores.",
        )

    def test_binder_accepts_single_prefix_unbound_wire_form(self) -> None:
        transaction = PublicationMethodParagraphOutputV1(
            paragraph_id="MA-S1:p1",
            paragraph_markdown="The method uses the declared operation.",
            rendered_slot_ids=["slot:fact:operation"],
        )
        plan_row = {
            "paragraph_id": "MA-S1:p1",
            "witness_contract": {
                "targets": [{
                    "target_kind": "slot",
                    "target_id": "slot:fact:operation",
                    "semantic_atom": "declared operation",
                }],
            },
        }
        valid, errors, unbound = validate_paragraph_binding_response(
            {
                "paragraph_id": "MA-S1:p1",
                "witnesses": [],
                "unbound_target_ids": ["slot:fact:operation"],
            },
            transaction,
            plan_row=plan_row,
        )

        self.assertEqual(valid, ())
        self.assertEqual(errors, ())
        self.assertEqual(unbound, ("slot:fact:operation",))

    def test_binder_accepts_relation_id_for_edge_unbound_wire_form(self) -> None:
        transaction = PublicationMethodParagraphOutputV1(
            paragraph_id="MA-S1:p1",
            paragraph_markdown="The method follows the declared relation.",
            rendered_edge_ids=["rel:relation"],
        )
        plan_row = {
            "paragraph_id": "MA-S1:p1",
            "witness_contract": {
                "targets": [{
                    "target_kind": "edge",
                    "target_id": "rel:relation",
                    "semantic_atom": "declared relation",
                }],
            },
        }
        valid, errors, unbound = validate_paragraph_binding_response(
            {
                "paragraph_id": "MA-S1:p1",
                "witnesses": [],
                "unbound_target_ids": ["rel:relation"],
            },
            transaction,
            plan_row=plan_row,
        )

        self.assertEqual(valid, ())
        self.assertEqual(errors, ())
        self.assertEqual(unbound, ("rel:relation",))

    def test_transaction_assembles_one_heading_in_plan_order(self) -> None:
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Encoder",
            publication_mode=True,
            argument_graph={
                "paragraphs": [
                    {
                        "paragraph_id": "MA-S1:p1",
                        "required_facet_ids": ["facet:input"],
                        "ordered_semantic_slot_ids": ["slot:input"],
                    },
                    {
                        "paragraph_id": "MA-S1:p2",
                        "required_facet_ids": ["facet:output"],
                        "ordered_semantic_slot_ids": ["slot:output"],
                    },
                ],
            },
            prompt_payload={
                "writer_view": {
                    "mechanism_authoring_packet": {
                        "facets": [
                            {"facet_id": "facet:input"},
                            {"facet_id": "facet:output"},
                        ]
                    }
                }
            },
        )
        output = PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            paragraphs=[
                PublicationMethodParagraphOutputV1(
                    paragraph_id="MA-S1:p2",
                    paragraph_markdown="The output is emitted.",
                    rendered_from_facet_ids=["facet:output"],
                    rendered_slot_ids=["slot:output"],
                    witnesses=[
                        PublicationContentWitnessV1(
                            witness_kind="facet",
                            target_id="facet:output",
                            exact_text="output",
                        ),
                        PublicationContentWitnessV1(
                            witness_kind="slot",
                            target_id="slot:output",
                            exact_text="output",
                        ),
                    ],
                ),
                PublicationMethodParagraphOutputV1(
                    paragraph_id="MA-S1:p1",
                    paragraph_markdown="The input is encoded.",
                    rendered_from_facet_ids=["facet:input"],
                    rendered_slot_ids=["slot:input"],
                    witnesses=[
                        PublicationContentWitnessV1(
                            witness_kind="facet",
                            target_id="facet:input",
                            exact_text="input",
                        ),
                        PublicationContentWitnessV1(
                            witness_kind="slot",
                            target_id="slot:input",
                            exact_text="input",
                        ),
                    ],
                ),
            ],
        )
        normalized, failures = _normalize_publication_paragraph_transaction(
            output, section=section, require_transactions=True
        )
        self.assertEqual(failures, [])
        self.assertEqual(normalized.rendered_paragraph_ids, ["MA-S1:p1", "MA-S1:p2"])
        self.assertEqual(
            normalized.section_markdown,
            "## Encoder\n\nThe input is encoded.\n\nThe output is emitted.",
        )

    def test_transaction_rejects_self_report_without_exact_witness(self) -> None:
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Encoder",
            publication_mode=True,
            argument_graph={
                "paragraphs": [{
                    "paragraph_id": "MA-S1:p1",
                    "required_facet_ids": ["facet:input"],
                }],
            },
            prompt_payload={
                "writer_view": {
                    "mechanism_authoring_packet": {
                        "facets": [{"facet_id": "facet:input"}]
                    }
                }
            },
        )
        output = PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            paragraphs=[PublicationMethodParagraphOutputV1(
                paragraph_id="MA-S1:p1",
                paragraph_markdown="The encoder reads data.",
                rendered_from_facet_ids=["facet:input"],
                witnesses=[],
            )],
        )
        _normalized, failures = _normalize_publication_paragraph_transaction(
            output, section=section, require_transactions=True
        )
        self.assertIn("missing_exact_witness:MA-S1:p1:facet:facet:input", failures)

    def test_transaction_rejects_empty_required_witness_contract(self) -> None:
        section = WriterSectionInput(
            section_id="MA-S1",
            heading="Encoder",
            publication_mode=True,
            argument_graph={
                "paragraphs": [{
                    "paragraph_id": "MA-S1:p1",
                    "required_facet_ids": ["facet:input"],
                    "ordered_semantic_slot_ids": ["slot:input"],
                }],
            },
            prompt_payload={},
        )
        output = PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            paragraphs=[PublicationMethodParagraphOutputV1(
                paragraph_id="MA-S1:p1",
                paragraph_markdown="The encoder reads data.",
            )],
        )
        _normalized, failures = _normalize_publication_paragraph_transaction(
            output, section=section, require_transactions=True
        )
        self.assertIn(
            "required_target_contract:MA-S1:p1:facet:facet:input", failures
        )
        self.assertIn(
            "required_target_contract:MA-S1:p1:slot:slot:input", failures
        )


if __name__ == "__main__":
    unittest.main()


def test_transaction_condition_binding_rejects_structure_changes() -> None:
    """R5 correction: the real Binder path enforces condition structure.

    The transaction path must not accept a flipped AND/OR, an appended
    opposite condition, a widened scope, or a changed comparison boundary just
    because the same predicate words appear.
    """

    from code2paper.agentic.publication_transaction_contract import (
        assess_paragraph_transaction,
        bind_paragraph_witnesses,
    )

    def _plan_row(condition: str) -> dict:
        return {
            "paragraph_id": "paragraph:section:guard",
            "required_publication_slot_ids": ["slot:guard"],
            "witness_contract": {"targets": [{
                "target_kind": "slot",
                "target_id": "slot:guard",
                "semantic_atom": "",
                "required_conditions": [condition],
                "required_polarity": "conditional",
            }]},
        }

    def _bind(markdown: str, sentence: str, condition: str):
        transaction = {
            "paragraph_id": "paragraph:section:guard",
            "paragraph_markdown": markdown,
            "witnesses": [{
                "witness_kind": "slot",
                "target_id": "slot:guard",
                "exact_text": sentence,
            }],
        }
        plan_row = _plan_row(condition)
        bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)
        assessment = assess_paragraph_transaction(bound, plan_row=plan_row)
        return bound, assessment

    bound, assessment = _bind(
        "When alpha and beta hold, the output is computed.",
        "When alpha and beta hold",
        "alpha and beta",
    )
    assert [item["target_id"] for item in bound["witnesses"]] == ["slot:guard"]
    assert assessment.valid is True

    for markdown, sentence in (
        ("When alpha or beta holds, the output is computed.", "When alpha or beta holds"),
        (
            "When alpha and beta hold, or gamma is never built, the output is computed.",
            "When alpha and beta hold, or gamma is never built",
        ),
        ("Whenever alpha holds, the output is computed.", "Whenever alpha holds"),
    ):
        bound_bad, assessment_bad = _bind(markdown, sentence, "alpha and beta")
        assert bound_bad["witnesses"] == [], (markdown, bound_bad["witnesses"])
        assert assessment_bad.valid is False
        assert "slot:guard" in assessment_bad.missing_by_kind.get("slot", ())

    bound_cmp, assessment_cmp = _bind(
        "When x >= 3, the output is computed.", "When x >= 3", "x >= 5"
    )
    assert bound_cmp["witnesses"] == []
    assert assessment_cmp.valid is False

    bound_ok, assessment_ok = _bind(
        "When x is at least 5, the output is computed.",
        "When x is at least 5",
        "x >= 5",
    )
    assert [item["target_id"] for item in bound_ok["witnesses"]] == ["slot:guard"]
    assert assessment_ok.valid is True

    # R5 correction: the review's five counterexamples must not bind through
    # the real Writer transaction path either.
    for declared, markdown, sentence in (
        # Boolean regrouping.
        (
            "(alpha or beta) and gamma",
            "When alpha or (beta and gamma), the output is computed.",
            "When alpha or (beta and gamma)",
        ),
        # Numeric sign.
        ("value > -5", "When value > 5, the output is computed.", "When value > 5"),
        # Repeated negation.
        ("not not alpha", "When not alpha, the output is computed.", "When not alpha"),
        # Comparator operand order.
        (
            "alpha < beta",
            "When beta < alpha, the output is computed.",
            "When beta < alpha",
        ),
        # Widened operand set.
        ("alpha", "When alpha or beta, the output is computed.", "When alpha or beta"),
    ):
        bound_bad, assessment_bad = _bind(markdown, sentence, declared)
        assert bound_bad["witnesses"] == [], (declared, markdown)
        assert assessment_bad.valid is False, (declared, markdown)
        assert "slot:guard" in assessment_bad.missing_by_kind.get("slot", ())


# --------------------------------------------------------------------------- #
# 审计 §E.1/E.2：生产修复归属来自 canonical 表，载荷保留局部合同
# --------------------------------------------------------------------------- #


def test_writer_content_repairable_failure_matrix_is_unchanged() -> None:
    from code2paper.llm.section_writer import (
        _is_writer_content_repairable_failure,
    )

    # 原有四条前缀仍然可修（段落事务、公式占位符、三种流截断表示损伤）。
    assert _is_writer_content_repairable_failure(
        "publication_paragraph_transaction_failed:MA-S1:p1:invalid_count"
    )
    assert _is_writer_content_repairable_failure(
        "publication_section_binding_failed:formula_placeholder:MA-S1:p1"
    )
    for code in (
        "provider_stream_finished_before_complete_json",
        "provider_stream_done_without_json_content",
        "provider_stream_ended_before_complete_json",
    ):
        assert _is_writer_content_repairable_failure(code)

    # 未知码 / 归属别的 owner 的失败仍然是终态：不得用内容补写掩盖。
    assert not _is_writer_content_repairable_failure("")
    assert not _is_writer_content_repairable_failure("something_nobody_registered")
    assert not _is_writer_content_repairable_failure(
        "publication_section_binding_failed:unknown_claims"
    )
    assert not _is_writer_content_repairable_failure(
        "publication_section_schema_failed:section_markdown_empty"
    )


def test_repair_classification_names_the_owner_and_action() -> None:
    from code2paper.llm.section_writer import (
        _classify_writer_repair_failure,
        _classify_writer_repair_failures,
    )

    paragraph = _classify_writer_repair_failure(
        "publication_paragraph_transaction_failed:MA-S1:p1:invalid_count"
    )
    assert (paragraph.owner, paragraph.action) == ("writer_content", "writer_content_repair")
    assert paragraph.codes == ("detail_semantic_mismatch",)

    # 段落 lane 的 formula_consumer_mismatch 是"占位符缺失"的内容补写，
    # 不是 planner 的 closure 问题。
    formula = _classify_writer_repair_failure(
        "publication_paragraph_transaction_failed:MA-S1:p1:formula_consumer_mismatch"
    )
    assert formula.action == "writer_content_repair"
    assert formula.codes == ("formula_placeholder_missing",)

    # 表示层损伤归 execution owner，但仍在有界补发集合里。
    stream = _classify_writer_repair_failure(
        "provider_stream_ended_before_complete_json"
    )
    assert (stream.owner, stream.action, stream.escalation) == (
        "execution_owner",
        "representation_repair",
        "representation_retry",
    )

    # 多条失败时按责任/依赖选择，而不是第一条。
    mixed = _classify_writer_repair_failures(
        [
            "transaction:publication_paragraph_transaction_failed:MA-S1:p1:invalid_count",
            "publication_section_binding_failed:unknown_claims",
        ]
    )
    assert mixed.code == "target_out_of_scope"
    assert mixed.escalation == "replan_required"


def test_repair_packet_keeps_frozen_siblings_private() -> None:
    from code2paper.llm.writer_section_repair import (
        WriterRepairProgressV1,
        build_writer_section_repair_packet,
    )

    progress = WriterRepairProgressV1(
        unsafe_uncaveated_positives=0,
        constraint_failures=0,
        negative_validated_propositions=0,
        unrendered_required_propositions=0,
        code_trace_style_failures=0,
        duplicate_sentences=0,
        missing_required_facets=0,
        missing_formula_placeholders=0,
    )
    packet = build_writer_section_repair_packet(
        section_id="MA-S1",
        attempt=1,
        incumbent_text="incumbent",
        writer_view={},
        progress=progress,
        failures=["transaction:publication_paragraph_transaction_failed:MA-S1:p1:invalid_count"],
        canonical_codes=("detail_semantic_mismatch",),
        owner="writer_content",
        action="writer_content_repair",
        escalation="repair_in_place",
        failed_paragraph_ids=("MA-S1:p1",),
        frozen_paragraph_digests={"MA-S1:p2": "abc123"},
    )

    assert packet.owner == "writer_content"
    assert packet.frozen_paragraph_digests == {"MA-S1:p2": "abc123"}
    payload = packet.as_request_payload()
    assert "frozen_paragraph_digests" not in payload
    assert payload["failed_paragraph_ids"] == ["MA-S1:p1"]
    assert payload["canonical_codes"] == ["detail_semantic_mismatch"]
    assert payload["incumbent_text"] == "incumbent"


def test_failed_paragraph_ids_stay_inside_the_plan() -> None:
    from code2paper.llm.section_writer import _publication_failed_paragraph_ids

    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        argument_graph={
            "paragraphs": [
                {"paragraph_id": "MA-S1:p1"},
                {"paragraph_id": "MA-S1:p2"},
            ]
        },
        prompt_payload={"section_id": "MA-S1"},
    )

    # 合同条目优先。
    assert _publication_failed_paragraph_ids(
        section, [{"paragraph_id": "MA-S1:p2"}], []
    ) == ("MA-S1:p2",)
    # section 级失败（合同无条目）时从失败文本恢复，且不接受计划外段落。
    assert _publication_failed_paragraph_ids(
        section,
        [],
        [
            "transaction:publication_paragraph_transaction_failed:"
            "MA-S1:p1:invalid_count;MA-S9:pX:invalid_count"
        ],
    ) == ("MA-S1:p1",)


def test_production_repair_call_passes_the_canonical_classification(monkeypatch) -> None:
    """真实接线：生产修复调用必须把 canonical 归属结论交给 repair packet。"""

    from code2paper.llm import section_writer as writer_module

    seen: list[dict] = []
    real = writer_module.build_writer_section_repair_packet

    def _spy(**kwargs):
        seen.append(dict(kwargs))
        return real(**kwargs)

    monkeypatch.setattr(
        writer_module, "build_writer_section_repair_packet", _spy
    )

    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        publication_mode=True,
        argument_graph={"paragraphs": [{"paragraph_id": "MA-S1:p1"}]},
        prompt_payload={
            "section_id": "MA-S1",
            "heading": "Mechanism",
            "shared_contexts": [{"page": "frozen"}],
            "shared_context_metadata": [{"v2_page_id": "page:1"}],
            "paragraph_transaction_required": True,
            "binding_contract": {"allowed_paragraph_ids": ["MA-S1:p1"]},
        },
    )

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        if "writer_section_repair" not in request.input_payload:
            text = json.dumps({
                "section_id": "MA-S1",
                "paragraphs": [
                    {"paragraph_id": "MA-S1:p1", "paragraph_markdown": "first"},
                    {"paragraph_id": "MA-S1:p1", "paragraph_markdown": "first"},
                ],
            })
        else:
            text = json.dumps({
                "section_id": "MA-S1",
                "paragraphs": [{
                    "paragraph_id": "MA-S1:p1",
                    "paragraph_markdown": "repaired substantive Method prose.",
                }],
            })
        return LLMResponse(
            text=text,
            response_hash=f"sha256:spy-{len(seen)}",
            finish_reason="stop",
            token_usage={"completion_tokens": 1},
        )

    write_publication_method_by_sections(
        _base_config(),
        [section],
        llm_caller=caller,
        content_transaction_assessor=lambda *_args: (True, "transaction_gain"),
    )

    assert seen, "生产路径必须调用 build_writer_section_repair_packet"
    repair_call = seen[0]
    assert repair_call["owner"] == "writer_content"
    assert repair_call["action"] == "writer_content_repair"
    assert repair_call["escalation"] == "repair_in_place"
    assert "detail_witness_missing" in repair_call["canonical_codes"]
    assert repair_call["failed_paragraph_ids"] == ("MA-S1:p1",)
