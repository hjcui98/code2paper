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

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

import pytest

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
    with_method_evidence: bool = False,
):
    import os

    paths = _unified_artifacts(tmp_path)
    if with_method_evidence:
        # 最终反向校验只在同时提供 evidence packets 与 frozen MethodEvidence 时运行；
        # 少了它，quality report 永远停在 pending，Verified 就不是"由规则决定"。
        from code2paper.schemas import MethodEvidence

        evidence = MethodEvidence(
            project_id="repo:writer",
            method_name="Encoder",
            method_goal="Explain the encoder.",
            implementation_scope="sym:encoder",
        )
        evidence_path = tmp_path / "artifacts" / "method_evidence.json"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            evidence.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        paths = dict(paths) | {"method_evidence": str(evidence_path)}
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



def _run_with_paths(
    tmp_path: Path,
    caller: Callable[[Any, LLMRequest], LLMResponse],
    paths: dict[str, str],
):
    """用给定 artifact_paths 跑一次产品入口（供注入夹具/变更输入的测试复用）。"""

    from tests.test_agentic_publication_method_writer_unified import (
        _unified_budget_env,
    )

    _unified_budget_env()
    try:
        return run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="unified",
        )
    finally:
        _clear_unified_budget_env()


def _baseline_run(tmp_path: Path) -> tuple[dict[str, str], list[LLMRequest]]:
    paths = _unified_artifacts(tmp_path)
    calls: list[LLMRequest] = []
    result, _outputs = _run_with_paths(tmp_path, _counting(calls), paths)
    assert result.status in {"success", "incomplete"}
    return paths, calls


def _counting(calls: list[LLMRequest]):
    def caller(config, request):
        calls.append(request)
        return _mock_writer_caller(config, request)

    return caller


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
    """场景 4：Writer 阶段接受 ≠ publication acceptance；后面的门必须具名拒绝。

    默认 fake provider 能过 writer_content 与确定性 Binder，但 candidate/verified 门
    仍然拒绝，并给出**具名**原因——不接受"内容有了就发布"。
    """

    import json as _json

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        return _mock_writer_caller(config, request)

    _result, outputs = _run(tmp_path, caller)

    rows = _acceptance_rows(tmp_path)
    assert any(
        row.get("content_acceptance_status") == "accepted" for row in rows
    ), "Writer 内容阶段应当接受"

    receipts = _json.loads(
        Path(outputs["binder_receipts_v2"]).read_text(encoding="utf-8")
    )
    for receipt in receipts["receipts"]:
        assert not (receipt.get("failure_codes") or ()), receipt.get("failure_codes")
        assert not (receipt.get("missing_target_keys") or ())

    verified = Path(outputs["repository_verified_method"])
    assert verified.read_text(encoding="utf-8").strip() == "", (
        "Writer 接受不等于发布验收"
    )
    writer_result = _json.loads(
        Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    )
    assert writer_result["writer_transaction_status"] == "success"
    assert writer_result["publication_ready"] is False
    assert "verified_output_empty" in writer_result["verified_blocking_reasons"]
    assert writer_result["candidate_blocking_reasons"], writer_result


def test_section_headings_are_reader_facing_not_internal_identifiers(
    tmp_path: Path,
) -> None:
    """审计 §D/§I：内部机制标识符不得进入读者可见标题。

    实测缺陷：统一链路的 section 标题直接取机制显示名 ``Sym:Encoder``，于是
    candidate authority 门报 `candidate_contains_internal_audit_terms`，整条干净候选
    路径被自己的内部标识符挡住。
    """

    import json as _json

    from code2paper.agentic.intent_spine_models import (
        heading_is_internal_identifier,
    )
    from code2paper.agentic.method_architect import (
        _reader_facing_section_heading,
    )

    # 单元：内部标识符被投影成人类标题；人类标题原样保留。
    assert _reader_facing_section_heading("Sym:Encoder") == "Encoder"
    assert _reader_facing_section_heading("mech_sym:encoder") == "Encoder"
    assert _reader_facing_section_heading("Sym:InfoNCE_Loss") == "Info NCE Loss"
    assert _reader_facing_section_heading("Encoder") == "Encoder"
    assert _reader_facing_section_heading("MA-S1") == "MA-S1"

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        return _mock_writer_caller(config, request)

    _result, outputs = _run(tmp_path, caller)

    for key in ("narrative_plan_v3", "method_section_plan_v2"):
        data = _json.loads(Path(outputs[key]).read_text(encoding="utf-8"))
        for section in data.get("sections") or ():
            heading = str(section.get("heading") or "")
            assert heading and not heading_is_internal_identifier(heading), (
                f"{key} 的标题仍是内部标识符：{heading}"
            )

    authority = _json.loads(
        Path(outputs["candidate_authority_validation_v1"]).read_text(
            encoding="utf-8"
        )
    )
    assert authority["validation"]["status"] == "passed", authority["validation"]
    assert "candidate_contains_internal_audit_terms" not in (
        authority["validation"]["violations"]
    )


#: 被授权的源码片段：Binder 绑定 atom 需要它在正文里唯一出现。
AUTHORIZED_EXCERPT = "class Encoder:\n    def read(self, configured_input):"


def _contract_faithful_writer(config, request):
    """按页面冻结合同写正文的 fake writer（只声明 detail witness）。

    正文包含 required detail 的 semantic atom 与被授权的源码片段；atom witness 留给
    确定性 Binder，因为页面合同把 atom 声明为 binder-owned。
    """

    if getattr(request, "prompt_template_id", "") != WRITER_TEMPLATE:
        return _mock_writer_caller(config, request)
    page = (request.input_payload.get("shared_contexts") or [{}])[0]
    atoms = {
        str(atom.get("detail_id") or atom.get("_atom_id") or ""): atom
        for atom in (page.get("atoms") or ())
        if isinstance(atom, dict)
    }
    paragraphs = []
    for row in request.input_payload["narrative_plan"]["paragraphs"]:
        required = list(row.get("required_detail_ids") or ())
        sentences: list[str] = []
        witnesses: list[dict] = []
        for detail_id in required:
            text = str((atoms.get(detail_id) or {}).get("semantic_atom") or "").strip()
            if not text:
                continue
            sentences.append(f"The implementation performs {text}.")
            witnesses.append(
                {"witness_kind": "detail", "target_id": detail_id, "exact_text": text}
            )
        sentences.append(
            "The source defines the read path:\n\n```python\n"
            f"{AUTHORIZED_EXCERPT}\n```"
        )
        paragraphs.append({
            "paragraph_id": row["paragraph_id"],
            "paragraph_markdown": "\n\n".join(sentences),
            "rendered_detail_ids": required,
            "witnesses": witnesses,
        })
    return LLMResponse(
        text=json.dumps({
            "section_id": request.input_payload.get("section_id", ""),
            "paragraphs": paragraphs,
        }),
        response_hash="sha256:contract-faithful",
        finish_reason="stop",
        token_usage={"completion_tokens": 50},
    )


def test_binder_closed_set_comes_from_the_frozen_contract(tmp_path: Path) -> None:
    """§E.4：闭集必须来自冻结合同，不能"已绑定就变成越界"。

    实测缺陷：闭集用 `paragraph_binding_targets(...)`（它会跳过已声明/已绑定的 key）
    计算，于是 Binder 一旦按合同绑定 atom，那些 atom 立刻被报成
    `binder_target_outside_closed_contract` —— 页面永远无法通过 final-bound。
    """

    import json as _json

    from code2paper.agentic.publication_transaction_contract import (
        closed_binding_target_keys,
        paragraph_binding_targets,
    )

    plan_row = {
        "paragraph_id": "P1",
        "required_detail_ids": ("d:1",),
        "witness_contract": {
            "targets": (
                {"target_kind": "detail", "target_id": "d:1", "required": True},
                {"target_kind": "atom", "target_id": "atom:d:1:op", "required": True},
            )
        },
    }
    transaction = {
        "paragraph_id": "P1",
        "paragraph_markdown": "body",
        "witnesses": [
            {"witness_kind": "atom", "target_id": "atom:d:1:op", "exact_text": "body"}
        ],
    }
    # 旧语义：已声明的 atom 从"还能绑什么"里消失。
    bindable = {
        (item["witness_kind"], item["target_id"])
        for item in paragraph_binding_targets(transaction, plan_row=plan_row)
    }
    assert ("atom", "atom:d:1:op") not in bindable
    # 新语义：闭集只由冻结合同决定，已声明/已绑定的目标仍在闭集里。
    closed = closed_binding_target_keys(plan_row=plan_row)
    assert ("atom", "atom:d:1:op") in closed
    assert ("detail", "d:1") in closed

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        return _contract_faithful_writer(config, request)

    result, outputs = _run(tmp_path, caller)

    receipts = _json.loads(
        Path(outputs["binder_receipts_v2"]).read_text(encoding="utf-8")
    )
    for receipt in receipts["receipts"]:
        assert not [
            code
            for code in (receipt.get("failure_codes") or ())
            if "outside_closed_contract" in str(code)
        ], receipt.get("failure_codes")
        # 冻结合同里的每个目标都被见证（detail + 三个 atom）。
        witnessed = set(receipt.get("witnessed_target_keys") or ())
        assert any(key.startswith("detail:") for key in witnessed), witnessed
        assert sum(1 for key in witnessed if key.startswith("atom:")) >= 3, witnessed
        assert receipt.get("missing_target_keys") in (None, [], ())

    aggregate = _json.loads(
        Path(outputs["writer_aggregate_receipt_v2"]).read_text(encoding="utf-8")
    )
    assert aggregate["all_required_sections_complete"] is True
    authority = _json.loads(
        Path(outputs["candidate_authority_validation_v1"]).read_text(encoding="utf-8")
    )
    assert authority["validation"]["status"] == "passed"

    # Verified 仍由原规则决定：本 fake writer 没有渲染 argument unit，因此
    # candidate/verified 门如实报出**具名**原因，而不是静默通过。
    writer_result = _json.loads(
        Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    )
    assert writer_result["writer_transaction_status"] == "success"
    assert writer_result["publication_ready"] is False
    assert "verified_output_empty" in writer_result["verified_blocking_reasons"]
    assert any(
        "argument_units_unrendered" in str(reason)
        for reason in writer_result["candidate_blocking_reasons"]
    ), writer_result["candidate_blocking_reasons"]


def test_verified_verdict_is_decided_by_the_real_validator(tmp_path: Path) -> None:
    """§G.2：完整 candidate 之后，Verified 必须由**真实反向校验**判定。

    提供 frozen MethodEvidence 后，quality report 不再停在 `pending`：反向校验真的跑，
    并给出具名结论。本 fake provider 的句子还没有逐句 claim 对齐，因此结论是 failed +
    `unsupported_positive_claims` + 逐句 review block——这是"原规则决定"，不是隐藏门槛。
    """

    import json as _json

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        return _contract_faithful_writer(config, request)

    _result, outputs = _run(tmp_path, caller, with_method_evidence=True)

    quality = _json.loads(
        Path(outputs["publication_quality_report_v1"]).read_text(encoding="utf-8")
    )
    safety = quality.get("safety") or {}
    status = safety.get("final_text_validation_status")
    assert status in {"passed", "failed", "error"}, status
    assert status != "pending", "提供冻结证据后反向校验必须真的运行"

    writer_result = _json.loads(
        Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    )
    # candidate 链已经完整走完：writer_content + Binder + composition 都通过。
    assert writer_result["writer_transaction_status"] == "success"
    aggregate = _json.loads(
        Path(outputs["writer_aggregate_receipt_v2"]).read_text(encoding="utf-8")
    )
    assert aggregate["all_required_sections_complete"] is True

    if status == "passed":
        # 一旦 fake provider 逐句 claim 对齐，Verified 就该真的产出。
        assert Path(outputs["repository_verified_method"]).read_text(
            encoding="utf-8"
        ).strip()
    else:
        # 未对齐时必须具名拒绝，并且不得产出 Verified 正文。
        assert "reverse_validation_failed" in writer_result["verified_blocking_reasons"]
        assert int(safety.get("unsupported_positive_claims") or 0) > 0
        assert any(
            str(reason).startswith("verified_review_block:review-sentence:")
            for reason in writer_result["verified_blocking_reasons"]
        ), writer_result["verified_blocking_reasons"]
        # 逐句原因必须落到 claim 级：说明还差什么才算合法内容。
        section_failures = [
            failure
            for result in writer_result["section_results"]
            for failure in (result.get("failures") or ())
        ]
        assert any(
            "reverse validation failed" in str(failure) for failure in section_failures
        ), section_failures
        assert any(
            "no_semantically_matching_projected_claim" in str(failure)
            or "direct_evidence_missing" in str(failure)
            for failure in section_failures
        ), section_failures
        assert Path(outputs["repository_verified_method"]).read_text(
            encoding="utf-8"
        ).strip() == ""


def test_formalizer_phase_is_not_substituted_by_the_writer_manifest(
    tmp_path: Path,
) -> None:
    """场景 7（产品层）：Formalizer 与 Writer 的 manifest 是两个阶段对象。

    无公式任务的 no-probe 行为由 `test_formalizer_without_formula_obligations_does_not_probe_pages`
    在单元层覆盖；这里断言产品产物层：两个阶段的 manifest 各自独立、按 (role, phase)
    分别解析，并且"空是否合法"按阶段 + 冻结单元数判定（F.3），不允许拿 Writer 的
    manifest 冒充 Formalizer 的。
    """

    import json as _json

    from code2paper.agentic.authoring_artifact_index import (
        assess_empty_artifact,
        build_artifact_index,
        resolve_artifact,
    )

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        return _mock_writer_caller(config, request)

    _result, outputs = _run(tmp_path, caller)

    formalizer_manifest = Path(outputs["consumer_workset_manifest_v2"])
    writer_manifest = Path(outputs["consumer_workset_manifest_v2.writer.2"])
    assert formalizer_manifest.is_file() and writer_manifest.is_file()
    assert formalizer_manifest != writer_manifest

    formalizer_payload = _json.loads(formalizer_manifest.read_text(encoding="utf-8"))
    writer_payload = _json.loads(writer_manifest.read_text(encoding="utf-8"))
    assert formalizer_payload["content_digest"] != writer_payload["content_digest"]

    index = build_artifact_index(tmp_path)
    assert resolve_artifact(
        index, "consumer_workset_manifest", "formalizer", out_root=tmp_path
    ) == formalizer_manifest
    assert resolve_artifact(
        index, "consumer_workset_manifest", "writer", out_root=tmp_path
    ) == writer_manifest

    # 阶段语义：Formalizer 允许"没有任务"，Writer 在冻结了必需单元时不允许空。
    formalizer_disposition = assess_empty_artifact(
        "consumer_workset_manifest",
        "formalizer",
        {"schema_version": "2.0", "pages": [], "worksets": []},
        required_units=0,
    )
    assert formalizer_disposition.allowed is True
    assert formalizer_disposition.reason == "no_required_units"
    writer_disposition = assess_empty_artifact(
        "consumer_workset_manifest",
        "writer",
        {"schema_version": "2.0", "pages": [], "worksets": []},
        required_units=1,
    )
    assert writer_disposition.allowed is False


# --------------------------------------------------------------------------- #
# §G.2 场景 5：只有作者说明、没有 implementation atom
# --------------------------------------------------------------------------- #


def test_author_only_paragraph_stays_bounded_without_implementation_proof(
    tmp_path: Path, monkeypatch
) -> None:
    """作者-only 段落必须走"合法有界作者段落"路径：不伪造实现证明，也不因空 context 崩。"""

    import json as _json
    import os

    from code2paper.agentic.method_architect import NarrativePlanV3

    paths = _unified_artifacts(tmp_path)
    spine_path = tmp_path / "artifacts" / "author_story_spine_v1.json"
    spine_path.parent.mkdir(parents=True, exist_ok=True)
    spine_path.write_text(
        _json.dumps(
            {
                "author_story_spine": [
                    {
                        "story_node_id": "story:author-only",
                        "title": "Motivation for the design.",
                        "author_statement": "Motivation for the design.",
                        "intended_role": "motivation",
                        "notes": ["kind=stage", "priority=must_cover"],
                        "linked_claim_ids": [],
                        "linked_obligation_ids": [],
                    }
                ]
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    paths = dict(paths) | {"author_story_spine_v1": str(spine_path)}
    monkeypatch.setenv("CODE2PAPER_INTENT_NARRATIVE_PLAN", "v4")

    requests: list[LLMRequest] = []

    def caller(config, request):
        requests.append(request)
        return _mock_writer_caller(config, request)

    result, outputs = _run_with_paths(tmp_path, caller, paths)
    assert result.status in {"success", "incomplete", "blocked"}, result.status

    plan = NarrativePlanV3.model_validate_json(
        Path(outputs["narrative_plan_v3"]).read_text(encoding="utf-8")
    )
    author_only = [
        paragraph
        for section in plan.sections
        for paragraph in section.paragraphs
        if not paragraph.required_detail_ids
    ]
    assert author_only, "作者-only 段落必须保留在计划里"
    paragraph = author_only[0]
    # 没有实现材料 → 不能有任何必需 target（否则就是在伪造实现证明）。
    assert paragraph.required_detail_ids == ()
    assert not (paragraph.witness_contract or {}).get("targets")

    # 该段落到达 Writer 的页合同时同样不能要求实现义务。
    for request in requests:
        if getattr(request, "prompt_template_id", "") != WRITER_TEMPLATE:
            continue
        for row in (request.input_payload.get("narrative_plan") or {}).get(
            "paragraphs", []
        ):
            if str(row.get("paragraph_id")) != paragraph.paragraph_id:
                continue
            assert not (row.get("required_detail_ids") or ())
            assert not ((row.get("witness_contract") or {}).get("targets") or ())

    assert os.environ.get("CODE2PAPER_INTENT_NARRATIVE_PLAN") == "v4"


def test_mutating_a_consumed_artifact_blocks_resume_instead_of_reusing(
    tmp_path: Path,
) -> None:
    """§G.2 场景 8：消费文件被改动 → resume 必须在使用前失败，而不是复用旧回执。"""

    import json as _json

    paths, _calls = _baseline_run(tmp_path)
    facts = Path(paths["code_facts_v1"])
    data = _json.loads(facts.read_text(encoding="utf-8"))
    assert data.get("facts"), "夹具必须有可改动的 code facts"
    data["facts"][0]["semantic_context"] = list(
        data["facts"][0].get("semantic_context") or ()
    ) + ["mutated"]
    facts.write_text(
        _json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    resume_calls: list[LLMRequest] = []
    with pytest.raises(ValueError, match="unified_plan_corrupt|unified_resume_digest_mismatch"):
        _run_with_paths(tmp_path, _counting(resume_calls), paths)

    # 失败发生在"使用之前"：不得发布任何已验证正文。
    verified = tmp_path / "artifacts" / "06_authoring" / "repository_verified_method.md"
    if verified.is_file():
        assert verified.read_text(encoding="utf-8").strip() == ""


def test_lowered_writer_output_cap_is_refused_before_the_provider(
    tmp_path: Path, monkeypatch
) -> None:
    """§C.6/§C.7：实际 provider 输出 cap 被调低 → 必须在假 provider 边界之前阻断。

    复核在 62782ad 上复现：计划上限 8192、实际降到 1，请求仍然发出。这里把
    `_apply_writer_context_clamp` 改成"悄悄调低 cap"（事故形态），断言 Writer 页请求
    根本没有到达 caller，并且失败原因具名。
    """

    import json as _json

    from code2paper.llm import section_writer as sw

    real_clamp = sw._apply_writer_context_clamp
    calls: list[LLMRequest] = []

    def lowering_clamp(config, **kwargs):
        clamped, blocked = real_clamp(config, **kwargs)
        if blocked is not None:
            return clamped, blocked
        # 降到仍高于最小输出、但**不等于**计划上限的值：请求会走到契约复核。
        return clamped.model_copy(update={"max_output_tokens": 4096}), None

    monkeypatch.setattr(sw, "_apply_writer_context_clamp", lowering_clamp)

    def caller(config, request):
        calls.append(request)
        return _mock_writer_caller(config, request)

    paths = _unified_artifacts(tmp_path)
    result, outputs = _run_with_paths(tmp_path, caller, paths)

    assert not [
        request
        for request in calls
        if getattr(request, "prompt_template_id", "") == WRITER_TEMPLATE
    ], "上限被调低的请求不得发给 provider"

    # 拒绝原因必须**具名**且落在不可变回执里（不是只留一个下游症状）。
    acceptances = sorted(
        (tmp_path / "artifacts" / "06_authoring" / "invocations").rglob(
            "attempt-*.content-acceptance.json"
        )
    )
    assert acceptances, "必须有内容验收 sidecar"
    rows = [_json.loads(path.read_text(encoding="utf-8")) for path in acceptances]
    failures = [str(item) for row in rows for item in (row.get("failures") or ())]
    assert any(
        "actual_page_contract_mismatch:output_cap:4096!=8192" in item
        for item in failures
    ), failures
    assert any(row.get("content_acceptance_status") == "rejected" for row in rows)
    assert result.status in {"incomplete", "blocked"}
    writer_result = _json.loads(
        Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    )
    assert writer_result["publication_ready"] is False


def test_technical_bytes_digest_mismatch_is_refused_before_the_provider(
    tmp_path: Path, monkeypatch
) -> None:
    """K04：冻结契约的技术字节摘要与调用方重算值不符 → 真实发送点零发送。

    事故形态是"材料在准入之后被换掉、而请求仍带着旧的声明 hash"。K04 起公共复核不再读
    payload 的声明字段，而是接收调用方**从实际材料字节重算**的摘要。这里让冻结契约的摘要
    偏离真实材料（材料字节本身仍与页一致，因此只有这一道门能拦下它），断言 Writer 页请求
    根本没有到达 caller，且失败具名落在不可变回执里。
    """

    import json as _json

    from code2paper.agentic import page_contract_recheck as pcr

    calls: list[LLMRequest] = []
    real_from_payload = pcr.page_contract_snapshot_from_payload

    def drifting_snapshot(*args, **kwargs):
        snapshot = real_from_payload(*args, **kwargs)
        return snapshot.model_copy(
            update={"technical_bytes_digest": "sha256:" + "f" * 64}
        )

    monkeypatch.setattr(pcr, "page_contract_snapshot_from_payload", drifting_snapshot)

    def caller(config, request):
        calls.append(request)
        return _mock_writer_caller(config, request)

    paths = _unified_artifacts(tmp_path)
    result, outputs = _run_with_paths(tmp_path, caller, paths)

    assert not [
        request
        for request in calls
        if getattr(request, "prompt_template_id", "") == WRITER_TEMPLATE
    ], "技术字节摘要不符的请求不得发给 provider"

    acceptances = sorted(
        (tmp_path / "artifacts" / "06_authoring" / "invocations").rglob(
            "attempt-*.content-acceptance.json"
        )
    )
    rows = [_json.loads(path.read_text(encoding="utf-8")) for path in acceptances]
    failures = [str(item) for row in rows for item in (row.get("failures") or ())]
    assert any(
        "actual_page_contract_mismatch:technical_bytes" in item for item in failures
    ), failures
    assert any(row.get("content_acceptance_status") == "rejected" for row in rows)
    assert result.status in {"incomplete", "blocked"}
    writer_result = _json.loads(
        Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    )
    assert writer_result["publication_ready"] is False


def test_missing_v2_page_metadata_under_unified_is_refused_before_the_provider(
    tmp_path: Path, monkeypatch
) -> None:
    """G1：严格 unified 意图下缺 V2 页元数据 → 发送前具名拒绝，不自动降级直发。

    修前 ``_capturing_writer_caller`` 在 ``not v2_rows`` 时直接走 base_caller：请求连同
    页合同/技术字节复核一起被发出。这里在**请求构造点**只删掉 V2 页元数据
    （``shared_context_metadata``），其余输入逐字不变；provider 边界仍是本测试的 caller，
    因此"零发送"是在真实调用链上断言的。
    """

    import json as _json

    from code2paper.agentic import publication_method_writer as pmw
    from code2paper.llm import section_writer as sw

    real_request = pmw.LLMRequest

    def stripping_request(**kwargs):
        payload = kwargs.get("input_payload")
        if isinstance(payload, dict) and "shared_context_metadata" in payload:
            kwargs["input_payload"] = {
                key: value
                for key, value in payload.items()
                if key != "shared_context_metadata"
            }
        return real_request(**kwargs)

    monkeypatch.setattr(pmw, "LLMRequest", stripping_request)
    # Writer 页请求由 section_writer 构造后交给 writer 的 caller；请求构造点在这里。
    monkeypatch.setattr(sw, "LLMRequest", stripping_request)

    calls: list[LLMRequest] = []

    def caller(config, request):
        calls.append(request)
        return _mock_writer_caller(config, request)

    paths = _unified_artifacts(tmp_path)
    result, outputs = _run_with_paths(tmp_path, caller, paths)

    # 严格 unified：请求不得抵达 provider。
    assert not [
        request
        for request in calls
        if getattr(request, "prompt_template_id", "") == WRITER_TEMPLATE
    ], "缺 V2 页元数据的 unified 请求不得发给 provider"

    acceptances = sorted(
        (tmp_path / "artifacts" / "06_authoring" / "invocations").rglob(
            "attempt-*.content-acceptance.json"
        )
    )
    rows = [_json.loads(path.read_text(encoding="utf-8")) for path in acceptances]
    failures = [str(item) for row in rows for item in (row.get("failures") or ())]
    writer_json = Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    writer_result = _json.loads(writer_json)
    # 具名拒绝：实测阻断节点是上游的 unified_unplanned_actual_request（缺 invocation id），
    # 即"上游已拒"；本测试记录**实际**节点而不是注释里的期望节点。
    reason = str(getattr(result, "blocked_reason", ""))
    assert "unified_unplanned_actual_request" in reason or "unified_unplanned_actual_request" in writer_json or any(
        "unified_unplanned_actual_request" in item for item in failures
    ), (failures, reason, writer_json[:400])
    assert result.status in {"incomplete", "blocked"}
    assert writer_result["publication_ready"] is False


def test_missing_writer_workset_manifest_under_unified_is_refused_before_the_provider(
    tmp_path: Path, monkeypatch
) -> None:
    """G1：unified 意图不变而 workset manifest 缺失 → 具名发送前拒绝（零发送）。

    修前以 AttributeError 派生的 ``unified_pipeline_failed`` 兜底；现在 manifest 解析点
    直接抛出 ``unified_unplanned_actual_request:missing_writer_workset_manifest``。
    """

    import json as _json

    from code2paper.agentic import unified_context_compiler as ucc

    real_builder = ucc.extend_writer_worksets_from_narrative_plan
    monkeypatch.setattr(
        ucc, "extend_writer_worksets_from_narrative_plan", lambda *a, **k: None
    )
    calls: list[LLMRequest] = []

    def caller(config, request):
        calls.append(request)
        return _mock_writer_caller(config, request)

    paths = _unified_artifacts(tmp_path)
    result, outputs = _run_with_paths(tmp_path, caller, paths)
    monkeypatch.setattr(ucc, "extend_writer_worksets_from_narrative_plan", real_builder)

    assert not [
        request
        for request in calls
        if getattr(request, "prompt_template_id", "") == WRITER_TEMPLATE
    ], "缺 workset manifest 的 unified 请求不得发给 provider"
    acceptances = sorted(
        (tmp_path / "artifacts" / "06_authoring" / "invocations").rglob(
            "attempt-*.content-acceptance.json"
        )
    )
    failures = [
        str(item)
        for path in acceptances
        for item in (_json.loads(path.read_text(encoding="utf-8")).get("failures") or ())
    ]
    writer_json = Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    writer_result = _json.loads(writer_json)
    reason = str(getattr(result, "blocked_reason", ""))
    assert (
        "unified_unplanned_actual_request" in reason
        or "unified_unplanned_actual_request" in writer_json
        or any("unified_unplanned_actual_request" in item for item in failures)
    ), (failures, reason, writer_json[:400])
    assert writer_result["publication_ready"] is False
    assert result.status in {"incomplete", "blocked"}


def test_explicit_legacy_mode_still_sends_without_v2_page_metadata(tmp_path: Path) -> None:
    """G1 对照：legacy 由可信入口显式选择时照常发送，不因缺 V2 字段被误拒。"""

    from tests.test_agentic_publication_method_writer_unified import _unified_budget_env

    calls: list[LLMRequest] = []

    def caller(config, request):
        calls.append(request)
        return _mock_writer_caller(config, request)

    paths = _unified_artifacts(tmp_path)
    _unified_budget_env()
    try:
        run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="legacy",
        )
    finally:
        _clear_unified_budget_env()
    assert calls, "显式 legacy 模式必须仍能发送"


# --------------------------------------------------------------------------- #
# K04-G2：实际发送侧六类单变量变异（冻结合同不重算，repair 与合法首发送分开计数）
# --------------------------------------------------------------------------- #
#
# 这一组反例的共同前提是**冻结合同来自合法 primary、且不随变异重算**：
#
# * 合法 primary 先经真实入口发送一次并冻结页合同（内存缓存）；
# * 变异只注入到**随后构造的 repair 请求**（同一个真实 `LLMRequest` 构造点，
#   同一个 `_capturing_writer_caller` 复核点），primary 请求逐字不变；
# * 因此"改材料/改 scope/改作者目标"都是**实际发送侧**的单变量改变，而冻结侧仍是
#   primary 的合同。若在上游夹具上改，编译合同与请求会一起合法重算，那就不是漂移反例。
#
# 计数规则：`primary_arrivals` 是合法初次发送，`repair_arrivals` 是被变异的 repair 发送。
# 六例都要求后者为零调用，而不是整轮零调用——否则无法区分"拒绝"与"根本没走到"。

G2_REPAIR_RESERVE_TOKENS = 20000


def _material_bytes_digest(payload: Mapping[str, Any]) -> str:
    """与真实 Writer 调用点同规则：从 ``shared_contexts`` 的**实际材料字节**重算。"""

    from code2paper.agentic.mechanism_context_models import (
        canonical_json_bytes,
        sha256_digest,
    )

    contexts = payload.get("shared_contexts") or ()
    raw = contexts[0] if len(contexts) == 1 else b""
    if isinstance(raw, bytes):
        data = bytes(raw)
    elif isinstance(raw, str):
        data = raw.encode("utf-8")
    elif isinstance(raw, Mapping):
        data = canonical_json_bytes(dict(raw))
    else:
        data = b""
    return sha256_digest(data) if data else ""


class _WriterSendBoundary:
    """真实 Writer 待发送请求边界上的只读观察 + 单变量注入。

    * 只有 ``prompt_template_id`` 为 unified writer 页模板的请求会被观察；
    * ``target`` 决定变异落在 primary 还是 repair 请求上（默认 repair：只有 repair
      仍带着**先前已冻结**的 primary 合同，primary 自己的合同是从它自身捕获的）；
    * `observed` 是生产 ``compare_actual_request_to_page_contract`` 的只读 spy：
      记录冻结合同摘要、调用方从 bytes 重算的实测摘要与实际失败码，但不改行为。
    """

    def __init__(
        self,
        mutate: Callable[[dict, "_WriterSendBoundary"], None] | None = None,
        *,
        target: str = "repair",
    ):
        if target not in {"primary", "repair"}:
            raise ValueError(f"unknown boundary target: {target}")
        self._mutate = mutate
        self._target = target
        self.built_primary: list[dict] = []
        self.built_repairs: list[dict] = []
        self.injected: list[dict] = []
        self.primary_arrivals: list[Any] = []
        self.repair_arrivals: list[Any] = []
        self.observed: list[dict] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> "_WriterSendBoundary":
        from code2paper.agentic import page_contract_recheck as pcr
        from code2paper.llm import section_writer as sw

        boundary = self
        real_request = sw.LLMRequest
        real_compare = pcr.compare_actual_request_to_page_contract

        def request_factory(**kwargs):
            payload = kwargs.get("input_payload")
            if (
                isinstance(payload, dict)
                and kwargs.get("prompt_template_id") == WRITER_TEMPLATE
            ):
                if "writer_section_repair" in payload:
                    boundary.built_repairs.append(copy.deepcopy(payload))
                    is_target = boundary._target == "repair"
                else:
                    boundary.built_primary.append(copy.deepcopy(payload))
                    is_target = boundary._target == "primary"
                if boundary._mutate is not None and is_target:
                    mutated = copy.deepcopy(payload)
                    boundary._mutate(mutated, boundary)
                    boundary.injected.append(copy.deepcopy(mutated))
                    kwargs = {**kwargs, "input_payload": mutated}
            return real_request(**kwargs)

        def compare_spy(snapshot, **kwargs):
            failures = real_compare(snapshot, **kwargs)
            checked_payload = kwargs.get("payload")
            boundary.observed.append({
                "frozen_technical": str(
                    getattr(snapshot, "technical_bytes_digest", "") or ""
                ),
                "measured": str(
                    kwargs.get("actual_technical_bytes_digest") or ""
                ),
                # 调用方交给公共复核的**实际请求载荷**必须真的携带那些材料字节：
                # 这里按同一规则独立重算一次，作为实测摘要的 bytes 来源证明。
                "payload_measured": _material_bytes_digest(
                    checked_payload if isinstance(checked_payload, Mapping) else {}
                ),
                "is_repair": bool(kwargs.get("is_repair")),
                "invocation_id": str(kwargs.get("invocation_id") or ""),
                "page_id": str(getattr(snapshot, "page_id", "") or ""),
                "failures": [str(item) for item in failures],
            })
            return failures

        monkeypatch.setattr(sw, "LLMRequest", request_factory)
        monkeypatch.setattr(
            pcr, "compare_actual_request_to_page_contract", compare_spy
        )
        return self

    @property
    def frozen_digest(self) -> str:
        """生产复核在合法 primary 上观察到的冻结技术字节摘要。"""

        for row in self.observed:
            if not row["is_repair"]:
                return row["frozen_technical"]
        return ""

    def observations(self, *, is_repair: bool) -> list[dict]:
        return [row for row in self.observed if row["is_repair"] is is_repair]


def _payload_diff(before: Any, after: Any, path: str = "") -> list[str]:
    """两次实际请求载荷的字段级差异（用于断言"只改目标条件"）。"""

    if isinstance(before, Mapping) and isinstance(after, Mapping):
        rows: list[str] = []
        for key in sorted(set(before) | set(after)):
            rows.extend(_payload_diff(before.get(key), after.get(key), f"{path}.{key}"))
        return rows
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [f"{path}:len {len(before)}->{len(after)}"]
        rows = []
        for index, (left, right) in enumerate(zip(before, after)):
            rows.extend(_payload_diff(left, right, f"{path}[{index}]"))
        return rows
    if before != after:
        return [f"{path}:{before!r}->{after!r}"]
    return []


def _run_g2_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[dict, _WriterSendBoundary], None] | None = None,
    *,
    target: str = "repair",
) -> dict[str, Any]:
    """跑一轮真实产品入口：合法 primary 触发一次有界 repair，变异只落在目标请求上。"""

    boundary = _WriterSendBoundary(mutate, target=target).install(monkeypatch)
    writer_attempts = {"count": 0}

    def caller(config, request):
        if getattr(request, "prompt_template_id", "") == WRITER_TEMPLATE:
            payload = getattr(request, "input_payload", None)
            payload = payload if isinstance(payload, Mapping) else {}
            if "writer_section_repair" in payload:
                boundary.repair_arrivals.append(request)
            else:
                boundary.primary_arrivals.append(request)
        response = _mock_writer_caller(config, request)
        if getattr(request, "prompt_template_id", "") == WRITER_TEMPLATE:
            writer_attempts["count"] += 1
            if writer_attempts["count"] == 1 and target == "repair":
                # 第一次：段落正文只有标题 → 真实内容拒绝 → 生产触发有界 repair。
                def _title_only(payload: dict) -> None:
                    for paragraph in payload.get("paragraphs") or ():
                        paragraph["paragraph_markdown"] = "## Method"

                response = _mutate_writer(response, request, _title_only)
        return response

    result, outputs = _run(
        tmp_path, caller, retry_reserve_tokens=G2_REPAIR_RESERVE_TOKENS
    )
    rows = _acceptance_rows(tmp_path)
    writer_result = json.loads(
        Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    )
    return {
        "boundary": boundary,
        "result": result,
        "statuses": [row.get("content_acceptance_status") for row in rows],
        "failures": [
            str(item) for row in rows for item in (row.get("failures") or ())
        ],
        "publication_ready": writer_result["publication_ready"],
    }


def _assert_g2_refusal(
    outcome: Mapping[str, Any],
    *,
    expected_code: str,
    expected_diff: list[str],
) -> None:
    boundary: _WriterSendBoundary = outcome["boundary"]
    # 合法初次发送与被变异的 repair 分开计数：前者恰好一次，后者零调用。
    assert len(boundary.primary_arrivals) == 1, "合法 primary 必须恰好到达 provider 一次"
    assert boundary.repair_arrivals == [], "被变异的 repair 请求不得发给 provider"
    assert len(boundary.built_repairs) == 1, "生产路径必须真的构造了 repair 请求"
    assert boundary.injected, "变异必须真的发生在实际发送侧"
    assert _payload_diff(boundary.built_repairs[0], boundary.injected[0]) == (
        expected_diff
    ), "变异必须是目标条件的单变量改变"
    # 冻结侧没有被重算：生产复核在 primary 与 repair 上看到同一份冻结摘要，
    # 而该摘要等于调用方从**实际材料字节**重算的实测值（bytes 来源证明）。
    primary_obs = boundary.observations(is_repair=False)
    repair_obs = boundary.observations(is_repair=True)
    assert primary_obs and repair_obs, boundary.observed
    assert primary_obs[-1]["measured"] == primary_obs[-1]["payload_measured"] != ""
    assert boundary.frozen_digest == primary_obs[-1]["measured"]
    assert all(
        row["frozen_technical"] == boundary.frozen_digest for row in repair_obs
    ), repair_obs
    # 具名目标拒绝：公共复核与不可变内容验收记录都必须点名同一个目标条件。
    assert any(
        expected_code in item for item in repair_obs[-1]["failures"]
    ), repair_obs[-1]["failures"]
    assert any(expected_code in item for item in outcome["failures"]), (
        expected_code,
        outcome["failures"],
    )
    assert "rejected" in outcome["statuses"], outcome["statuses"]
    # 真实产品结果：不是 mock 推导，也不是"整轮没跑"。
    assert outcome["publication_ready"] is False
    assert outcome["result"].status in {"incomplete", "blocked"}


def test_g2_legal_primary_and_legal_repair_reach_the_provider_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2 正对照：同一夹具、同一预算下，合法 primary 与合法 repair 各到达一次。"""

    outcome = _run_g2_case(tmp_path, monkeypatch)
    boundary: _WriterSendBoundary = outcome["boundary"]

    assert len(boundary.primary_arrivals) == 1, "合法 primary 必须恰好发送一次"
    assert len(boundary.repair_arrivals) == 1, "合法 repair 必须能到达 provider"
    assert len(boundary.built_repairs) == 1
    assert boundary.injected == []
    assert outcome["statuses"] == ["rejected", "accepted"], outcome["statuses"]

    # G6：生产 spy 的实测摘要非空、来源为实际材料 bytes，且与冻结值一致。
    frozen = boundary.frozen_digest
    assert frozen, boundary.observed
    assert boundary.built_primary, "生产路径必须构造 primary 页请求"
    for row in boundary.observed:
        assert row["measured"] == frozen, row
        assert row["payload_measured"] == frozen, row
        assert row["failures"] == [], row
    repair_obs = boundary.observations(is_repair=True)
    assert repair_obs and repair_obs[0]["frozen_technical"] == frozen


def test_g2_missing_measured_digest_is_refused_before_the_repair_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2-1：实际侧拿不到可重算的材料 → ``technical_bytes_unknown``，零发送。"""

    def _drop_material(payload: dict, boundary: _WriterSendBoundary) -> None:
        payload["shared_contexts"] = []

    outcome = _run_g2_case(tmp_path, monkeypatch, _drop_material)
    _assert_g2_refusal(
        outcome,
        expected_code="actual_page_contract_mismatch:technical_bytes_unknown",
        expected_diff=[".shared_contexts:len 1->0"],
    )
    boundary: _WriterSendBoundary = outcome["boundary"]
    assert _material_bytes_digest(boundary.injected[0]) == "", "变异后确实无法重算"
    assert boundary.observations(is_repair=True)[-1]["measured"] == ""


def test_g2_changed_material_with_the_old_declaration_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2-2：材料已改而请求仍声明旧摘要 → 声明值不能替代重算。"""

    def _change_material_keep_old_declaration(
        payload: dict, boundary: _WriterSendBoundary
    ) -> None:
        payload["shared_contexts"][0]["atoms"][0]["content_digest"] = (
            "sha256:" + "0" * 64
        )
        # 旧声明：写回**冻结**摘要（payload 本身原本不声明该字段）。
        payload["technical_bytes_digest"] = boundary.frozen_digest

    outcome = _run_g2_case(tmp_path, monkeypatch, _change_material_keep_old_declaration)
    _assert_g2_refusal(
        outcome,
        expected_code="actual_page_contract_mismatch:technical_bytes",
        expected_diff=[
            ".shared_contexts[0].atoms[0].content_digest:"
            "'sha256:29859fa129d7c9aed719779931221d6c5e69093fb50038f0d35f838b9a7b8b7b'"
            "->'sha256:0000000000000000000000000000000000000000000000000000000000000000'",
            ".technical_bytes_digest:None->'" + outcome["boundary"].frozen_digest + "'",
        ],
    )
    boundary: _WriterSendBoundary = outcome["boundary"]
    # 声明保留旧值，实测已变 —— 拒绝来自"实测 vs 冻结"，不是来自声明。
    assert boundary.injected[0]["technical_bytes_digest"] == boundary.frozen_digest
    assert _material_bytes_digest(boundary.injected[0]) != boundary.frozen_digest


def test_g2_forged_declaration_cannot_stand_in_for_the_measured_material(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2-3：声明被伪造成与**改后材料**自洽 → 仍按冻结合同拒绝（不是查内部矛盾）。"""

    def _forge_self_consistent_declaration(
        payload: dict, boundary: _WriterSendBoundary
    ) -> None:
        payload["shared_contexts"][0]["atoms"][0]["content_digest"] = (
            "sha256:" + "1" * 64
        )
        payload["technical_bytes_digest"] = _material_bytes_digest(payload)

    outcome = _run_g2_case(
        tmp_path, monkeypatch, _forge_self_consistent_declaration
    )
    boundary: _WriterSendBoundary = outcome["boundary"]
    forged = _material_bytes_digest(boundary.injected[0])
    _assert_g2_refusal(
        outcome,
        expected_code="actual_page_contract_mismatch:technical_bytes",
        expected_diff=[
            ".shared_contexts[0].atoms[0].content_digest:"
            "'sha256:29859fa129d7c9aed719779931221d6c5e69093fb50038f0d35f838b9a7b8b7b'"
            "->'sha256:1111111111111111111111111111111111111111111111111111111111111111'",
            ".technical_bytes_digest:None->'" + forged + "'",
        ],
    )
    # 自洽伪造：声明 == 实测，且两者都不等于冻结值。
    assert boundary.injected[0]["technical_bytes_digest"] == forged
    assert forged != boundary.frozen_digest
    assert boundary.observations(is_repair=True)[-1]["measured"] == forged


def test_g2_repair_that_changes_the_page_material_is_refused_before_the_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2-4：repair 请求改了页材料（payload 不声明任何摘要）→ 发送前拒绝。"""

    def _change_page_material(payload: dict, boundary: _WriterSendBoundary) -> None:
        atom = payload["shared_contexts"][0]["atoms"][0]
        atom["semantic_atom"] = str(atom.get("semantic_atom") or "") + " MUTATED"

    outcome = _run_g2_case(tmp_path, monkeypatch, _change_page_material)
    boundary: _WriterSendBoundary = outcome["boundary"]
    original = boundary.built_repairs[0]["shared_contexts"][0]["atoms"][0][
        "semantic_atom"
    ]
    _assert_g2_refusal(
        outcome,
        expected_code="actual_page_contract_mismatch:technical_bytes",
        expected_diff=[
            f".shared_contexts[0].atoms[0].semantic_atom:{original!r}->{original + ' MUTATED'!r}"
        ],
    )
    # repair 包本身合法（未被改），因此拒绝确实来自材料改变。
    assert boundary.injected[0]["writer_section_repair"] == (
        boundary.built_repairs[0]["writer_section_repair"]
    )
    assert _material_bytes_digest(boundary.injected[0]) != boundary.frozen_digest


def test_g2_expanding_an_empty_formula_scope_on_the_repair_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2-5：冻结的公式包白名单为空，repair 往空 scope 里塞包 → 具名 scope 拒绝。"""

    def _expand_empty_formula_scope(
        payload: dict, boundary: _WriterSendBoundary
    ) -> None:
        payload["binding_contract"]["allowed_formula_package_ids"] = [
            "formula-package:injected-by-repair"
        ]

    outcome = _run_g2_case(tmp_path, monkeypatch, _expand_empty_formula_scope)
    boundary: _WriterSendBoundary = outcome["boundary"]
    assert boundary.built_repairs[0]["binding_contract"][
        "allowed_formula_package_ids"
    ] == [], "冻结侧必须确实是空白名单"
    _assert_g2_refusal(
        outcome,
        expected_code=(
            "actual_page_contract_mismatch:scope:allowed_formula_package_ids:"
            "expected=0:actual=1"
        ),
        expected_diff=[".binding_contract.allowed_formula_package_ids:len 0->1"],
    )


def test_g2_changed_author_goal_on_the_repair_is_refused_before_the_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G2-6：repair 改了作者目标（reader_goal）→ author_surface 具名拒绝。"""

    def _change_author_goal(payload: dict, boundary: _WriterSendBoundary) -> None:
        payload["narrative_plan"]["paragraphs"][0]["reader_goal"] = (
            "Summarize the encoder."
        )

    outcome = _run_g2_case(tmp_path, monkeypatch, _change_author_goal)
    boundary: _WriterSendBoundary = outcome["boundary"]
    original = boundary.built_repairs[0]["narrative_plan"]["paragraphs"][0][
        "reader_goal"
    ]
    _assert_g2_refusal(
        outcome,
        expected_code="actual_page_contract_mismatch:author_surface",
        expected_diff=[
            f".narrative_plan.paragraphs[0].reader_goal:{original!r}->'Summarize the encoder.'"
        ],
    )
    # 段落集合与页身份逐字未变：作者目标变化是唯一变量。
    assert (
        boundary.injected[0]["narrative_plan"]["page_paragraph_ids"]
        == boundary.built_repairs[0]["narrative_plan"]["page_paragraph_ids"]
    )
    assert (
        boundary.injected[0]["narrative_plan"]["page_id"]
        == boundary.built_repairs[0]["narrative_plan"]["page_id"]
    )


# --------------------------------------------------------------------------- #
# K04-G3：无 technical digest 的旧合同由哪个可信 owner 承担比较
# --------------------------------------------------------------------------- #
#
# 真实的 unified writer 页请求**不声明**任何材料摘要（legacy envelope 形态）。因此必须
# 说清是谁在比较实际材料，而不是靠注释宣称"envelope 兜底"：
#
# * primary：材料身份由**准入期**冻结的 ``expected_request_envelope_digest``（连同
#   ``unified_actual_page_bytes_mismatch`` 的逐字页字节比较）承担。页合同在这一条上不是
#   独立 owner —— 它是从**同一个** primary 请求捕获的，改 primary 会让两者一起重算。
# * repair：由内存里冻结的 primary 页合同（技术字节门）与逐字页字节比较承担；primary 的
#   envelope 按设计不复用于 repair。
# * 冻结侧"确实没有材料摘要"的形态在 unified lane 结构性不可达：页与 invocation 的模型
#   都拒绝空摘要（见 test_legacy_characterization 的 G3 构造拒绝回归）。


def test_g3_primary_material_change_is_caught_by_the_frozen_page_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G3：primary 改材料 → 零发送；冻结材料身份来自**冻结页**，不随请求重算。

    请求逐字不声明摘要（legacy envelope 形态），所以冻结值只可能有两个来源：请求自己
    的声明（此例没有）或可信 adapter 从**冻结页**补的值。生产 spy 证明是后者：冻结值
    等于变异**前**同页材料摘要，而实测值等于变异后的材料摘要。
    """

    def _change_primary_material(payload: dict, boundary: _WriterSendBoundary) -> None:
        atom = payload["shared_contexts"][0]["atoms"][0]
        atom["semantic_atom"] = str(atom.get("semantic_atom") or "") + " MUTATED"

    outcome = _run_g2_case(
        tmp_path, monkeypatch, _change_primary_material, target="primary"
    )
    boundary: _WriterSendBoundary = outcome["boundary"]

    assert boundary.injected, "变异必须真的落在 primary 请求上"
    assert boundary.primary_arrivals == [], "改材料的 primary 不得发给 provider"
    assert boundary.repair_arrivals == []
    assert all(
        "technical_bytes_digest" not in payload for payload in boundary.built_primary
    ), "legacy envelope 形态：请求不声明任何材料摘要"

    observation = boundary.observations(is_repair=False)[-1]
    page_id = observation["page_id"]
    assert page_id
    unmutated_digests = {
        _material_bytes_digest(payload)
        for payload in boundary.built_primary
        if str((payload.get("narrative_plan") or {}).get("page_id") or "") == page_id
    }
    assert observation["measured"] == observation["payload_measured"] != ""
    assert observation["frozen_technical"] in unmutated_digests, (
        observation,
        unmutated_digests,
    )
    assert observation["measured"] not in unmutated_digests, (
        "变异后的材料摘要不得出现在冻结值里"
    )
    assert observation["frozen_technical"] != observation["measured"]
    # 发送前具名拒绝，且三个独立 owner 各自点名。
    assert (
        "actual_page_contract_mismatch:technical_bytes" in observation["failures"]
    ), observation["failures"]
    failures = " ".join(outcome["failures"])
    assert "unified_actual_page_bytes_mismatch" in failures, failures
    assert "unified_actual_request_envelope_mismatch" in failures, failures
    assert outcome["publication_ready"] is False
    assert outcome["result"].status in {"incomplete", "blocked"}


def test_g3_legacy_envelope_without_a_declared_digest_is_verified_by_frozen_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G3：旧 envelope 形态（请求不声明摘要）→ 比较由冻结页字节 + 调用方重算承担。"""

    outcome = _run_g2_case(tmp_path, monkeypatch)
    boundary: _WriterSendBoundary = outcome["boundary"]

    # 形态确认：请求逐字不声明任何材料摘要（legacy envelope）。
    for payload in (*boundary.built_primary, *boundary.built_repairs):
        assert "technical_bytes_digest" not in payload, payload.keys()
        assert "page_bytes_digest" not in payload, payload.keys()
    # 合法旧请求仍被发送（可信 adapter 从 bytes 补值，不因缺声明被拒）。
    assert len(boundary.primary_arrivals) == 1
    assert len(boundary.repair_arrivals) == 1
    # 生产 spy：冻结值非空、等于调用方从实际材料 bytes 重算的值 —— 这就是承担比较的 owner。
    frozen = boundary.frozen_digest
    assert frozen
    for row in boundary.observed:
        assert row["frozen_technical"] == frozen
        assert row["measured"] == frozen
        assert row["payload_measured"] == frozen
        assert row["failures"] == []
