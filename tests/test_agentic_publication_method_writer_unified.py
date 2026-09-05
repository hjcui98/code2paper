"""Integration tests for unified and shadow_unified modes in publication_method_writer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from code2paper.agentic.mechanism_context_models import MechanismContextSetV1
from code2paper.agentic.method_architect import NarrativePlanV3
from code2paper.agentic.method_content_trace import (
    MechanismInformationFunnelV1,
    MethodContentTraceV2,
)
from code2paper.agentic.publication_method_writer import (
    AuthoringContextMode,
    run_publication_method_writer,
)
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.schemas import LLMConfig
from tests.test_agentic_publication_method_writer import _artifacts, _config


def _mock_writer_caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
    """Mock section writer caller returning structured publication output."""
    if "binder" in getattr(request, "prompt_template_id", ""):
        binder_out = {
            "paragraph_id": request.input_payload.get("paragraph_id", ""),
            "witnesses": [],
            "unbound_target_ids": [],
        }
        return LLMResponse(
            text=json.dumps(binder_out),
            metadata=binder_out,
            response_hash="sha256:mock-binder-response",
            finish_reason="stop",
            token_usage={"completion_tokens": 50},
        )

    payload = request.prompt if isinstance(request.prompt, dict) else {}
    if isinstance(request.prompt, str):
        try:
            payload = json.loads(request.prompt)
        except Exception:
            payload = {}

    section_id = str(
        request.input_payload.get("section_id")
        or payload.get("section_id")
        or "sec_method_1"
    )
    heading = str(
        request.input_payload.get("heading")
        or payload.get("heading")
        or "Method"
    )
    p_plan = (
        request.input_payload.get("paragraph_plan")
        or payload.get("paragraph_plan")
        or ()
    )

    paragraphs_out = []
    if p_plan and isinstance(p_plan, (list, tuple)):
        for item in p_plan:
            pid = (
                item.get("paragraph_id")
                if isinstance(item, dict)
                else getattr(item, "paragraph_id", "")
            )
            if pid:
                paragraphs_out.append({
                    "paragraph_id": str(pid),
                    "paragraph_markdown": "The encoder reads the configured input reliably.",
                })
    if not paragraphs_out:
        paragraphs_out.append({
            "paragraph_id": f"{section_id}_p1",
            "paragraph_markdown": "The encoder reads the configured input reliably.",
        })

    body_prose = "\n\n".join(p["paragraph_markdown"] for p in paragraphs_out)
    prose = f"## {heading}\n\n{body_prose}"
    binding = request.input_payload.get("binding_contract") or {}
    completed_moves = list(binding.get("completed_rhetorical_moves", ["overview"]))
    if not completed_moves:
        completed_moves = ["overview"]

    structured = {
        "section_id": section_id,
        "heading_text": heading,
        "section_markdown": prose,
        "paragraphs": paragraphs_out,
        "used_argument_unit_ids": binding.get("used_argument_unit_ids", []),
        "used_claim_ids": binding.get("used_claim_ids", []),
        "used_equation_ids": binding.get("used_equation_ids", []),
        "used_configuration_ids": binding.get("used_configuration_ids", []),
        "completed_rhetorical_moves": completed_moves,
    }

    return LLMResponse(
        text=json.dumps(structured),
        metadata=structured,
        response_hash="sha256:mock-writer-response",
        finish_reason="stop",
        token_usage={"completion_tokens": 150, "prompt_tokens": 300},
    )


def test_run_publication_method_writer_unified_mode(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_mock_writer_caller,
        authoring_context_mode="unified",
    )

    assert result.status in ("success", "incomplete")
    assert result.status != "blocked"

    # Check that unified artifacts exist in outputs
    assert "mechanism_context_set_v1" in outputs
    assert "narrative_plan_v3" in outputs
    assert "method_content_trace_v2" in outputs
    assert "mechanism_information_funnel_v1" in outputs

    # Validate MechanismContextSetV1
    context_set = MechanismContextSetV1.model_validate_json(
        Path(outputs["mechanism_context_set_v1"]).read_text(encoding="utf-8")
    )
    assert len(context_set.contexts) >= 1
    assert context_set.contexts[0].mechanism_id == "mech_core"

    # Validate NarrativePlanV3
    plan_v3 = NarrativePlanV3.model_validate_json(
        Path(outputs["narrative_plan_v3"]).read_text(encoding="utf-8")
    )
    assert len(plan_v3.sections) >= 1
    assert len(plan_v3.narrative_units) >= 1

    # Validate MethodContentTraceV2
    trace_v2 = MethodContentTraceV2.model_validate_json(
        Path(outputs["method_content_trace_v2"]).read_text(encoding="utf-8")
    )
    assert len(trace_v2.rows) >= 1
    assert trace_v2.funnel is not None

    # Validate MechanismInformationFunnelV1
    funnel = MechanismInformationFunnelV1.model_validate_json(
        Path(outputs["mechanism_information_funnel_v1"]).read_text(encoding="utf-8")
    )
    assert funnel.total_context_details >= 1
    assert funnel.architect_planned_details >= 1
    assert "context_to_plan" in funnel.funnel_survival_rates


def test_run_publication_method_writer_shadow_unified_mode(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_mock_writer_caller,
        authoring_context_mode="shadow_unified",
    )

    assert result.status in ("success", "incomplete")
    assert result.status != "blocked"

    # Shadow mode produces both unified diagnostics and legacy outputs
    assert "mechanism_context_set_v1" in outputs
    assert "narrative_plan_v3" in outputs
    assert "method_content_trace_v2" in outputs
    assert "mechanism_information_funnel_v1" in outputs
    assert "publication_candidate_method" in outputs


def test_run_publication_method_writer_env_var_unified_cutover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODE2PAPER_AUTHORING_CONTEXT_MODE", "unified")
    paths = _artifacts(tmp_path)

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_mock_writer_caller,
    )

    assert result.status in ("success", "incomplete")
    assert "mechanism_context_set_v1" in outputs
    assert "narrative_plan_v3" in outputs
    assert "method_content_trace_v2" in outputs
    assert "mechanism_information_funnel_v1" in outputs
