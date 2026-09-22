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
