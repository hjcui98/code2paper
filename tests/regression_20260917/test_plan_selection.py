"""WP7：单一计划选择与 fail-closed（方案 §11.1）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from code2paper.agentic import method_architect

from . import incident_archive
from code2paper.agentic.publication_method_writer import _build_narrative_plan_v3

ENV_KEY = "CODE2PAPER_INTENT_NARRATIVE_PLAN"


def _story(story_id: str, statement: str) -> SimpleNamespace:
    return SimpleNamespace(
        story_node_id=story_id,
        title=statement,
        author_statement=statement,
        intended_role="algorithm_step",
        notes=("kind=stage", "priority=must_cover"),
        linked_claim_ids=(),
        linked_obligation_ids=(),
        source_refs=(),
        reader_question=f"How does this realize {statement}?",
    )


def _prior() -> SimpleNamespace:
    return SimpleNamespace(
        sections=[
            SimpleNamespace(
                section_id="MA-S1",
                heading="Motivation",
                argument_unit_ids=(),
                reader_question="Motivation",
            )
        ],
        argument_units=[],
    )


def _inputs() -> tuple[SimpleNamespace, tuple[SimpleNamespace, ...], SimpleNamespace]:
    return SimpleNamespace(contexts=()), (
        _story("story:a", "The encoder averages the loss."),
    ), _prior()


def test_v4_selection_does_not_execute_legacy_builder(monkeypatch) -> None:
    calls: list[str] = []

    def _spy(**kwargs: object) -> tuple[object, dict[str, object]]:
        calls.append("legacy")
        return SimpleNamespace(sections=(), narrative_units=()), {"legacy": True}

    monkeypatch.setattr(method_architect, "build_narrative_plan_v3", _spy)
    monkeypatch.setenv(ENV_KEY, "v4")
    contexts, story_spine, prior = _inputs()

    plan, trace = _build_narrative_plan_v3(
        contexts, story_spine=story_spine, prior_plan=prior
    )

    assert calls == [], "选定 v4 时不得执行 legacy builder"
    envelope = trace["intent_narrative_envelope"]
    assert envelope["selected_plan_version"] == "v4"
    assert envelope["executable_plan_version"] == "v4"
    assert envelope["intent_plan_v4"] is not None
    assert trace["legacy_builder_executed"] is False
    # 返回的是 V4 的一次兼容投影（唯一语义计划仍为 V4）。
    assert getattr(plan, "sections", None)


def test_v3_selection_executes_legacy_builder(monkeypatch) -> None:
    calls: list[str] = []

    def _spy(**kwargs: object) -> tuple[object, dict[str, object]]:
        calls.append("legacy")
        return SimpleNamespace(sections=(), narrative_units=()), {"legacy": True}

    monkeypatch.setattr(method_architect, "build_narrative_plan_v3", _spy)
    monkeypatch.setenv(ENV_KEY, "v3")
    contexts, story_spine, prior = _inputs()

    _plan, trace = _build_narrative_plan_v3(
        contexts, story_spine=story_spine, prior_plan=prior
    )
    assert calls == ["legacy"]
    assert trace["legacy_builder_executed"] is True
    assert trace["intent_narrative_envelope"]["executable_plan_version"] == "v3"


def test_selected_v4_compile_failure_stays_a_failure(monkeypatch) -> None:
    """不变量 I2：显式选定 v4 时编译失败必须失败，不能静默退回 V3。"""

    from code2paper.agentic import intent_narrative_compiler

    def _boom(**kwargs: object) -> None:
        raise ValueError("synthetic v4 compile failure")

    monkeypatch.setattr(
        intent_narrative_compiler, "build_intent_narrative_plan_v4", _boom
    )
    monkeypatch.setenv(ENV_KEY, "v4")
    contexts, story_spine, prior = _inputs()

    with pytest.raises(ValueError, match="synthetic v4 compile failure"):
        _build_narrative_plan_v3(contexts, story_spine=story_spine, prior_plan=prior)


def test_shadow_mode_builds_both_with_one_executable(monkeypatch) -> None:
    calls: list[str] = []

    def _spy(**kwargs: object) -> tuple[object, dict[str, object]]:
        calls.append("legacy")
        return SimpleNamespace(sections=(), narrative_units=()), {"legacy": True}

    monkeypatch.setattr(method_architect, "build_narrative_plan_v3", _spy)
    monkeypatch.setenv(ENV_KEY, "shadow")
    contexts, story_spine, prior = _inputs()

    _plan, trace = _build_narrative_plan_v3(
        contexts, story_spine=story_spine, prior_plan=prior
    )
    assert calls == ["legacy"]
    envelope = trace["intent_narrative_envelope"]
    assert envelope["selected_plan_version"] == "shadow"
    assert envelope["intent_plan_v4"] is not None
    # 影子模式只有一个可执行计划，且明确标注。
    assert envelope["executable_plan_version"] == "v3"


def test_writer_phase_boundary_blocks_on_exhausted_page() -> None:
    """§11.2：必需页已耗尽时在 phase boundary 阻断，并给出阶段/根因/下游链。"""

    from code2paper.agentic.writer_attempt_ledger import build_resume_preflight

    incident = incident_archive.read_json("writer_result")
    # 事故的终态原因是"跑到最后才发现 0 accepted"；新的边界检查应在循环之前
    # 就用同类根因阻断。这里验证边界检查产出的根因链内容完整。
    preflight = build_resume_preflight(
        incident_archive.archive_root(),
        [incident_archive.INCIDENT_INVOCATION],
    )
    assert preflight.allowed is False
    assert preflight.code == "resume_exhausted_invocation"
    assert preflight.content_attempts_used == preflight.content_attempt_limit == 2
    assert preflight.last_provider_attempt == 2
    assert preflight.rejected_before_send_events == (3, 4)
    assert "writer_v2_invocation_acceptance_count" in incident["blocked_reason"]
