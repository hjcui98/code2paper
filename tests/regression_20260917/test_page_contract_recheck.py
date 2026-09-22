"""PR C.6 / F01：发送前用最终实际请求复核冻结 page contract（审计 §C.6）。

冻结 oracle = 事故归档里 MA-S3 页的第一次 provider-request（16 段契约、7 个 allowed
detail、输出上限 8192）。反例全部在这份真实请求上构造：adapter 追加段落、重排段落、
缩小 detail scope、抬高输出上限，以及"repair 却没有冻结契约"。
"""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.page_contract_recheck import (
    ACTUAL_PAGE_CONTRACT_MISMATCH,
    capture_page_contract_snapshot,
    compare_actual_request_to_page_contract,
)

from . import incident_archive

INCIDENT_INVOCATION = incident_archive.INCIDENT_INVOCATION


def _snapshot():
    return capture_page_contract_snapshot(incident_archive.archive_root(), INCIDENT_INVOCATION)


def _payload() -> dict:
    snapshot = _snapshot()
    assert snapshot is not None
    request = json.loads(Path(snapshot.source_path).read_text(encoding="utf-8"))
    return json.loads(json.dumps(request["input_payload"]))


def _compare(payload: dict, **overrides):
    snapshot = _snapshot()
    kwargs = {
        "invocation_id": INCIDENT_INVOCATION,
        "payload": payload,
        "max_output_tokens": snapshot.max_output_tokens,
        "is_repair": False,
    }
    kwargs.update(overrides)
    return compare_actual_request_to_page_contract(snapshot, **kwargs)


def test_frozen_contract_matches_the_incident_page_facts() -> None:
    snapshot = _snapshot()
    assert snapshot is not None
    assert len(snapshot.paragraph_ids) == 16
    assert set(snapshot.paragraph_ids) == set(incident_archive.INCIDENT_PAGE_PARAGRAPH_IDS)
    assert len(snapshot.scope["allowed_detail_ids"]) == 7
    assert snapshot.max_output_tokens == 8192
    assert snapshot.source_path.startswith(str(incident_archive.archive_root()))


def test_frozen_request_order_is_lexical_not_narrative() -> None:
    """**已复现、待 PR C 修**：冻结请求里的段落顺序是字典序，不是计划的叙述顺序。

    审计 §C.1 要求 packing unit 携带"explicit narrative order"，§4 的 I5 要求实际请求的
    段落顺序与冻结 page contract 一致。事故归档里两者不同：请求先给 ``P10..P17`` 再给
    ``P1__f1, P3..P9``。本测试固定该事实，修好后应改为断言顺序等于叙述顺序。
    """

    snapshot = _snapshot()
    assert snapshot is not None
    assert list(snapshot.paragraph_ids) == sorted(snapshot.paragraph_ids), "当前是字典序"
    assert list(snapshot.paragraph_ids) != list(
        incident_archive.INCIDENT_PAGE_PARAGRAPH_IDS
    ), "与计划的叙述顺序不同（待修）"
    assert snapshot.paragraph_ids[0] == "MA-S3:P10"


def test_unchanged_request_passes_the_recheck() -> None:
    assert _compare(_payload()) == ()


def test_adapter_appending_paragraphs_is_rejected() -> None:
    """审计点名的反例：adapter 后来又追加 15 段，必须在发送前拒绝。"""

    payload = _payload()
    payload["narrative_plan"]["page_paragraph_ids"] = list(
        payload["narrative_plan"]["page_paragraph_ids"]
    ) + [f"MA-S3:EXTRA{n}" for n in range(15)]

    failures = _compare(payload, is_repair=True)
    assert failures == (
        f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:paragraph_ids:expected=16:actual=31",
    )


def test_reordering_paragraphs_is_rejected() -> None:
    payload = _payload()
    ids = list(payload["narrative_plan"]["page_paragraph_ids"])
    payload["narrative_plan"]["page_paragraph_ids"] = ids[1:] + ids[:1]

    failures = _compare(payload)
    assert failures and "paragraph_ids" in failures[0]


def test_shrinking_the_detail_scope_is_rejected() -> None:
    payload = _payload()
    payload["binding_contract"]["allowed_detail_ids"] = []

    failures = _compare(payload)
    assert failures == (f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:scope:allowed_detail_ids",)


def test_raising_the_output_cap_is_rejected() -> None:
    snapshot = _snapshot()
    failures = _compare(_payload(), max_output_tokens=snapshot.max_output_tokens + 1)
    assert failures == (
        f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:output_cap:"
        f"{snapshot.max_output_tokens + 1}>{snapshot.max_output_tokens}",
    )


def test_repair_without_a_frozen_contract_is_rejected() -> None:
    """repair 不比对 envelope：失去冻结契约就没有任何东西能证明它没被改页。"""

    failures = compare_actual_request_to_page_contract(
        None,
        invocation_id=INCIDENT_INVOCATION,
        payload=_payload(),
        is_repair=True,
    )
    assert failures == (f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:frozen_page_contract_missing",)
    # primary 由 envelope digest 兜底，因此没有持久化契约时不额外阻断。
    assert (
        compare_actual_request_to_page_contract(
            None, invocation_id=INCIDENT_INVOCATION, payload=_payload(), is_repair=False
        )
        == ()
    )


def test_snapshot_is_read_only_and_deterministic() -> None:
    root = incident_archive.archive_root()
    before = {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }
    first = _snapshot()
    second = _snapshot()
    after = {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert first == second
