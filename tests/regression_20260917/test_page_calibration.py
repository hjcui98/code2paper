"""WP4 标定：用事故归档的真实请求测出页内语义段落边界（方案 §8.2）。

边界是**证据**，不是策略选择：本测试从冻结归档重算分布，任何"改答案"都会失败。
"""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.writer_output_workload import (
    CALIBRATION_SOURCE,
    DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE,
    FIRST_ATTEMPT_ACCEPTED_MAX_PARAGRAPHS,
    OBSERVED_UNRECOVERABLE_PARAGRAPHS,
    REPAIR_RECOVERABLE_MAX_PARAGRAPHS,
)

from . import incident_archive


def _writer_requests() -> list[tuple[int, str, bool | None]]:
    """(段落数, invocation, accepted) —— 只统计 Writer 调用，Realizer 无段落列表。"""

    root = incident_archive.archive_root() / "artifacts/06_authoring/invocations"
    rows: list[tuple[int, str, bool | None]] = []
    for directory in sorted(root.glob("inv-writer-*")):
        for request in sorted(directory.glob("attempt-*.provider-request.json")):
            envelope = json.loads(request.read_text(encoding="utf-8"))
            plan = (envelope.get("input_payload") or {}).get("narrative_plan") or {}
            attempt = request.name.split("-")[1].split(".")[0]
            acceptance = directory / f"attempt-{attempt}.content-acceptance.json"
            accepted: bool | None = None
            if acceptance.is_file():
                accepted = bool(
                    json.loads(acceptance.read_text(encoding="utf-8")).get("accepted")
                )
            rows.append((len(plan.get("paragraphs") or ()), directory.name, accepted))
    return rows


def test_measured_paragraph_boundaries_are_frozen() -> None:
    rows = _writer_requests()
    assert len(rows) == 24, "Writer 请求数变化即标定基线变化"

    accepted = {count for count, _name, ok in rows if ok is True}
    rejected = {count for count, _name, ok in rows if ok is False}
    assert accepted == {1, 2, 4, 6}, accepted
    assert rejected == {1, 4, 6, 16}, rejected

    assert FIRST_ATTEMPT_ACCEPTED_MAX_PARAGRAPHS == 2

    # 4 段与 6 段页都是"首次 rejected、repair 后 accepted"（repair 可恢复边界）。
    for count in (4, 6):
        pattern = sorted(
            bool(value) for c, _name, value in rows if c == count
        )
        assert pattern == [False, True], (count, pattern)

    # 2 段页首次即接受；1 段页中有一例需要 repair。
    assert all(value is True for c, _name, value in rows if c == 2)
    ones = [value for c, _name, value in rows if c == 1]
    assert True in ones and False in ones

    # 16 段页首次与 repair 都 rejected → 实测不可一次完成（事故页）。
    sixteen = [ok for count, _name, ok in rows if count == 16]
    assert sixteen == [False, False]
    assert OBSERVED_UNRECOVERABLE_PARAGRAPHS == 16


def test_default_cap_sits_at_the_repair_recoverable_boundary() -> None:
    """默认上限 = 实测的 repair 可恢复边界；更严的首次即接受边界是 2。"""

    assert REPAIR_RECOVERABLE_MAX_PARAGRAPHS == 6
    assert DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE == 6
    assert FIRST_ATTEMPT_ACCEPTED_MAX_PARAGRAPHS < REPAIR_RECOVERABLE_MAX_PARAGRAPHS
    assert REPAIR_RECOVERABLE_MAX_PARAGRAPHS < OBSERVED_UNRECOVERABLE_PARAGRAPHS
    assert CALIBRATION_SOURCE.endswith("2026-09-17-ebcar-intent-v4-p7-j9L1bn")


def test_incident_page_shape_exceeds_the_calibrated_cap() -> None:
    from code2paper.agentic.writer_output_workload import evaluate_page_contract

    request = incident_archive.read_json("attempt_0002_request")
    paragraphs = request["input_payload"]["narrative_plan"]["paragraphs"]
    evaluation = evaluate_page_contract(
        paragraphs,
        input_tokens=31_792,          # 事故真实 prompt_tokens
        max_page_input_tokens=80_000,
        max_output_tokens=8_192,
    )
    assert evaluation.fits is False
    assert "semantic_paragraph_count_exceeds_candidate_limit" in evaluation.reasons
