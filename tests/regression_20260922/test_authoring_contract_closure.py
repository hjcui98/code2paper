"""§G.2：fake-provider 写作链闭环（只替换模型/网络边界）。

复用真实产品入口 `run_publication_method_writer`、真实 adapter、真实 assessor、真实
Binder/composer 与真实产物写入；fake provider **不返回"全局通过"**，而是按请求生成
合法响应，再经过完整解析与验收。

覆盖审计点名的场景（本片：1 / 3 / 6 + 局部 repair 的真实接线）：

* 首次合法内容 → 真实 binding/composition/验收路径；
* 缺一个 detail witness → 真实拒绝 → 有界 repair → 只改失败段；
* atom-only（只声明 atom）→ Writer 阶段拒绝，不因 atom 多就通过；
* 模型返回计划外段落 → 闭集/scope 拒绝，composer 不得静默吞掉。
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from code2paper.agentic.publication_method_writer import (
    run_publication_method_writer,
)
from code2paper.llm.client import LLMRequest, LLMResponse
from tests.test_agentic_publication_method_writer_unified import (
    _clear_unified_budget_env,
    _config,
    _mock_writer_caller,
    _unified_artifacts,
)

WRITER_TEMPLATE = "unified_writer_page_v2"
INJECTED_PARAGRAPH_ID = "sec_method_1_p99"
INJECTED_PROSE = "INJECTED PARAGRAPH MUST NEVER BE PUBLISHED"


def _run(
    tmp_path: Path,
    caller: Callable[[Any, LLMRequest], LLMResponse],
    *,
    retry_reserve_tokens: int = 0,
):
    import os

    paths = _unified_artifacts(tmp_path)
    if retry_reserve_tokens:
        # 有界 repair 必须由 run 显式声明 retry reserve（没有免费重试）。
        os.environ["CODE2PAPER_UNIFIED_RETRY_RESERVE_INPUT_TOKENS_WRITER"] = str(
            retry_reserve_tokens
        )
    try:
        return run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="unified",
        )
    finally:
        os.environ.pop("CODE2PAPER_UNIFIED_RETRY_RESERVE_INPUT_TOKENS_WRITER", None)
        _clear_unified_budget_env()


def _writer_payload(response: LLMResponse) -> dict:
    return json.loads(response.text)


def _mutate_writer(
    response: LLMResponse, request: LLMRequest, mutate: Callable[[dict], None]
) -> LLMResponse:
    if getattr(request, "prompt_template_id", "") != WRITER_TEMPLATE:
        return response
    payload = _writer_payload(response)
    mutate(payload)
    return replace(response, text=json.dumps(payload))


def _acceptance_rows(tmp_path: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(
        (tmp_path / "artifacts" / "06_authoring" / "invocations").rglob(
            "*.content-acceptance.json"
        )
    ):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def _writer_calls(requests: list[LLMRequest]) -> list[LLMRequest]:
    return [
        request
        for request in requests
        if getattr(request, "prompt_template_id", "") == WRITER_TEMPLATE
    ]


def _published_text(outputs: dict[str, str]) -> str:
    for key in (
        "publication_candidate_annotated",
        "publication_candidate_method",
        "repository_verified_method",
    ):
        path = outputs.get(key)
        if path and Path(path).is_file():
            return Path(path).read_text(encoding="utf-8")
    return ""


def test_first_legal_content_runs_the_real_composition_path(tmp_path: Path) -> None:
    """场景 1：首次合法内容 → 真实 binding/composition/验收，不给"全局通过"。"""

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        return _mock_writer_caller(config, request)

    result, outputs = _run(tmp_path, caller)

    writer_requests = _writer_calls(requests)
    assert len(writer_requests) == 1, "合法内容不需要 repair"
    rows = _acceptance_rows(tmp_path)
    assert rows, "真实验收必须留下 attempt 记录"
    assert any(
        row.get("content_acceptance_status") == "accepted" for row in rows
    ), rows

    # 发布文本来自共享 composer（有序 paragraph 对象 → 单一正文源）。
    from code2paper.agentic.paragraph_prose_composer import compose_section_markdown

    published = _published_text(outputs)
    assert published
    body = [
        line.strip()
        for line in published.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert body
    assert all(part in published for part in body)
    assert result.status in {"success", "incomplete"}


def test_atom_only_witness_does_not_complete_a_detail(tmp_path: Path) -> None:
    """场景 3：只声明 atom 不足以完成 detail 义务。"""

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        response = _mock_writer_caller(config, request)

        def _drop_detail_witnesses(payload: dict) -> None:
            for paragraph in payload.get("paragraphs") or ():
                witnesses = [
                    witness
                    for witness in (paragraph.get("witnesses") or ())
                    if str(witness.get("witness_kind") or "") == "atom"
                ]
                paragraph["witnesses"] = witnesses

        return _mutate_writer(response, request, _drop_detail_witnesses)

    _result, outputs = _run(tmp_path, caller)

    rows = _acceptance_rows(tmp_path)
    assert rows
    assert all(
        row.get("content_acceptance_status") == "rejected" for row in rows
    ), rows
    failures = [failure for row in rows for failure in row.get("failures") or ()]
    assert any(
        "detail" in str(failure) or "witness" in str(failure) for failure in failures
    ), failures

    # 该 section 不得被算作完成，也不得产出任何"已验证正文"。
    import json as _json

    aggregate = _json.loads(
        Path(outputs["writer_aggregate_receipt_v2"]).read_text(encoding="utf-8")
    )
    assert aggregate["completed_section_ids"] == []
    assert aggregate["all_required_sections_complete"] is False
    verified = Path(outputs["repository_verified_method"])
    assert verified.read_text(encoding="utf-8").strip() == ""
    # Candidate checkpoint 允许保留被拒正文供复核，但不得冒充已验证内容。
    assert _published_text(outputs) != verified.read_text(encoding="utf-8")


def test_extra_paragraph_is_refused_and_never_published(tmp_path: Path) -> None:
    """场景 6：计划外段落必须被闭集拒绝，composer 不得静默吞掉。"""

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        response = _mock_writer_caller(config, request)

        def _append_extra(payload: dict) -> None:
            paragraphs = list(payload.get("paragraphs") or ())
            if not paragraphs:
                return
            extra = dict(paragraphs[0])
            extra["paragraph_id"] = INJECTED_PARAGRAPH_ID
            extra["paragraph_markdown"] = INJECTED_PROSE
            paragraphs.append(extra)
            payload["paragraphs"] = paragraphs

        return _mutate_writer(response, request, _append_extra)

    _result, outputs = _run(tmp_path, caller)

    published = _published_text(outputs)
    assert INJECTED_PROSE not in published, "计划外段落不得进入发布正文"
    rows = _acceptance_rows(tmp_path)
    assert rows
    assert any(
        row.get("content_acceptance_status") == "rejected" for row in rows
    ), rows
    failures = " ".join(
        str(failure) for row in rows for failure in row.get("failures") or ()
    )
    assert INJECTED_PARAGRAPH_ID in failures or "unknown_paragraph" in failures, failures


def test_rejected_page_enters_one_bounded_repair_and_commits(
    tmp_path: Path, monkeypatch
) -> None:
    """场景 2：真实拒绝 → 有界 repair → 只改失败段，并留下可复用接受记录。

    触发条件用生产真正会阻断的缺陷（段落正文不具实质内容），因此在 V2 page lane 上
    走的正是 `publication_paragraph_transaction_failed:*` 这条修复 lane。
    """

    from code2paper.llm import section_writer as writer_module

    spy_calls: list[dict] = []
    real_packet_builder = writer_module.build_writer_section_repair_packet

    def _spy(**kwargs):
        spy_calls.append(dict(kwargs))
        return real_packet_builder(**kwargs)

    monkeypatch.setattr(
        writer_module, "build_writer_section_repair_packet", _spy
    )

    requests: list[LLMRequest] = []
    writer_attempts = {"count": 0}

    def caller(config, request):
        requests.append(request)
        response = _mock_writer_caller(config, request)
        if getattr(request, "prompt_template_id", "") != WRITER_TEMPLATE:
            return response
        writer_attempts["count"] += 1
        if writer_attempts["count"] > 1:
            return response

        # 第一次：段落正文只有标题（不具实质内容）→ 真实内容拒绝。
        def _title_only(payload: dict) -> None:
            for paragraph in payload.get("paragraphs") or ():
                paragraph["paragraph_markdown"] = "## Method"

        return _mutate_writer(response, request, _title_only)

    result, outputs = _run(tmp_path, caller, retry_reserve_tokens=20000)

    writer_requests = _writer_calls(requests)
    assert len(writer_requests) >= 2, "被拒页面必须进入有界 repair"
    assert spy_calls, "生产路径必须真的调用 build_writer_section_repair_packet"
    repair_call = spy_calls[0]
    assert repair_call["failed_paragraph_ids"] == ("sec_method_1_p1",)
    assert repair_call["action"] in {"writer_content_repair", "representation_repair"}
    assert repair_call["owner"] in {"writer_content", "execution_owner"}
    repair_payload = writer_requests[1].input_payload["writer_section_repair"]
    assert repair_payload["failed_paragraph_ids"] == ["sec_method_1_p1"]
    # 内部冻结摘要不得进入模型请求。
    assert "frozen_paragraph_digests" not in repair_payload
    # repair 请求仍携带同一冻结页面合同：page id 与页内段落集合都不变。
    repair_request_payload = writer_requests[1].input_payload
    primary_payload = writer_requests[0].input_payload
    assert (
        repair_request_payload["narrative_plan"]["page_id"]
        == primary_payload["narrative_plan"]["page_id"]
    )
    assert (
        repair_request_payload["narrative_plan"]["page_paragraph_ids"]
        == primary_payload["narrative_plan"]["page_paragraph_ids"]
    )
    assert (
        repair_request_payload["binding_contract"]
        == primary_payload["binding_contract"]
    )
    assert repair_payload["paragraph_transaction_repairs"]

    rows = _acceptance_rows(tmp_path)
    assert any(row.get("content_acceptance_status") == "rejected" for row in rows), rows
    assert any(
        row.get("content_acceptance_status") == "accepted"
        and row.get("repair_committed") is True
        for row in rows
    ), rows
    assert result.status in {"success", "incomplete"}
    assert _published_text(outputs)


def test_writer_acceptance_alone_does_not_publish_verified_text(tmp_path: Path) -> None:
    """场景 4：Writer 阶段接受 ≠ publication acceptance；final-bound/Binder 说了算。

    默认 fake provider 的正文能过 writer_content，但确定性 Binder 的闭集不允许它声明的
    atom witness，因此不得产出任何"已验证正文"。
    """

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        return _mock_writer_caller(config, request)

    _result, outputs = _run(tmp_path, caller)

    rows = _acceptance_rows(tmp_path)
    assert any(
        row.get("content_acceptance_status") == "accepted" for row in rows
    ), "Writer 内容阶段应当接受"
    verified = Path(outputs["repository_verified_method"])
    assert verified.read_text(encoding="utf-8").strip() == "", (
        "Writer 接受不等于发布验收"
    )

    import json as _json

    receipts = _json.loads(
        Path(outputs["binder_receipts_v2"]).read_text(encoding="utf-8")
    )
    failures = [
        code
        for receipt in receipts.get("receipts", [])
        for code in (receipt.get("failure_codes") or ())
    ]
    assert any(
        "binder_" in str(code) for code in failures
    ), f"下游 Binder 失败必须被记录：{failures}"
    # Writer 阶段的回执可以如实报"内容阶段完成"（§E.4：这不是 publication acceptance），
    # 但整条 run 必须因为下游失败而保持 incomplete。
    assert _result.status == "incomplete"
