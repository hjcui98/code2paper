from __future__ import annotations

import json
import os
import urllib.request

import pytest

from code2paper.agentic.decisioning import coverage_decision_trace
from code2paper.agentic.llm_decision_provider import build_llm_decision_provider
from code2paper.agentic.retrieval import CoverageItem, RetrievalCoverageReport
from code2paper.core.schemas import LLMConfig, LLMProvider


pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("CODE2PAPER_RUN_LIVE_LLM") != "1",
        reason="set CODE2PAPER_RUN_LIVE_LLM=1 to call the configured live endpoint",
    ),
]


def _base_url() -> str:
    return (
        os.environ.get("CODE2PAPER_LIVE_LLM_BASE_URL")
        or os.environ.get("CODE2PAPER_OPENAI_BASE_URL")
        or "http://127.0.0.1:8000/v1"
    ).rstrip("/")


def _model() -> str:
    return os.environ.get("CODE2PAPER_LIVE_LLM_MODEL") or os.environ.get("CODE2PAPER_LLM_MODEL") or "gemma4-31b-nvfp4"


def test_live_l0_endpoint_and_model_identity() -> None:
    with urllib.request.urlopen(f"{_base_url()}/models", timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    model_ids = {str(item.get("id") or "") for item in payload.get("data", []) if isinstance(item, dict)}
    assert _model() in model_ids


def test_live_l1_structured_coverage_proposal_is_schema_validated_and_merged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODE2PAPER_OPENAI_BASE_URL", _base_url())
    monkeypatch.setenv("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY") or "local-live-test")
    monkeypatch.setenv(
        "CODE2PAPER_LLM_CAPABILITY_PROFILE",
        json.dumps(
            {
                "profile_name": "gemma4_mtp_vllm",
                "provider": "openai",
                "model": _model(),
                "response_mode": "prompt_only",
                "source": "live-test",
                "inference_mode": "mtp",
                "tensor_parallel_size": 2,
                "speculative_tokens": 1,
                "draft_tensor_parallel_size": 2,
            }
        ),
    )
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        model=_model(),
        temperature=0.0,
        max_output_tokens=512,
        request_timeout_seconds=120,
        retry_max_attempts=1,
        cache=False,
    )
    coverage = RetrievalCoverageReport(
        overall_score=1.0,
        covered_targets=1,
        items=[
            CoverageItem(
                target_id="RT1",
                query="training loop",
                support_status="covered",
                matched_paths=["train.py"],
            )
        ],
    )

    provider = build_llm_decision_provider(config)
    assert provider is not None
    attempts = []
    for _attempt in range(3):
        decision, trace = coverage_decision_trace(
            coverage,
            retrieval_round=0,
            max_retrieval_rounds=0,
            decision_provider=provider,
        )
        attempts.append(trace.provider_status)
        if trace.provider_status == "model_proposal_merged":
            assert trace.parsed_proposal is not None
            assert decision.recommended_next in {"analysis", "blocked"}
            break
    else:
        pytest.fail(f"no schema-valid merged proposal in three bounded attempts: {attempts}")
