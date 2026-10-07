"""B01：合法正例与旧路径特征测试（AT-B01）。

本文件只做两件事：

1. **证明夹具是真的**：``fixtures/golden`` 里的页、请求、响应与判定必须逐字等于
   真实生产入口在本次运行中重新算出的结果（生成器见
   ``fixtures/legacy_fixture_builder.py``）。夹具不是手写 JSON。
2. **固定旧路径的真实行为**：合法正例通过它**自己声明**的局部门
   （writer_content + final_bound 页事务），具名反例按名字被拒；同时把旧路径的
   全局 Verified 为空、以及真实存在的两个特征缺口记录成断言，避免后续把
   "旧夹具合法"误读成"新桥已验证"。

AT-B01 的三条：
* 正例可通过其声明的局部门 → ``test_legal_page_passes_its_declared_local_gate`` 等；
* 反例具名拒绝 → ``test_named_counterexamples_are_rejected_by_name``；
* 旧夹具 Verified 为空不能当作新桥已验证 → ``test_positive_fixtures_do_not_claim_global_verified``
  与 ``test_legacy_pipeline_reports_verified_not_run``。
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

from code2paper.agentic.page_contract_recheck import (
    ACTUAL_PAGE_CONTRACT_MISMATCH,
    compare_actual_request_to_page_contract,
    page_contract_snapshot_from_payload,
    page_output_cap_failures,
    resolve_frozen_page_output_cap,
)
from code2paper.agentic.publication_transaction_contract import (
    assess_paragraph_transaction,
    bind_paragraph_witnesses,
    closed_binding_target_keys,
    required_targets_from_plan_row,
)
from code2paper.agentic.digest import canonical_json_bytes
from code2paper.agentic.mechanism_context_models import conservative_token_estimate
from code2paper.export.run_manifest import hash_text
from code2paper.agentic.unified_context_models import (
    ConsumerTechnicalPageV2,
    compute_technical_page_id,
)
from code2paper.llm.client import LLMResponse
from code2paper.llm.response_schemas import (
    PublicationMethodSectionOutputV1,
    try_parse_structured_response_with_trace,
)
from code2paper.llm.section_writer import (
    WriterSectionInput,
    _normalize_publication_paragraph_transaction,
    assess_publication_content_acceptance,
    assess_publication_writer_response,
)

from .fixtures import legacy_fixture_builder as builder

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
GOLDEN_DIR = FIXTURE_DIR / "golden"
REPO_ROOT = Path(__file__).resolve().parents[3]

GOLDEN_FILES = (
    "legal_page_with_atoms",
    "author_no_atom_page",
    "invalid_counterexamples",
    "completed_formalizer_page",
)
SCENARIOS = {
    "legal_page_with_atoms": "legal_page_with_atoms",
    "author_no_atom_page": "author_no_atom_page",
}


# --------------------------------------------------------------------------- #
# 夹具装载与离线保证
# --------------------------------------------------------------------------- #


def _load_golden(name: str) -> dict[str, Any]:
    return json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """B01 全是离线夹具：任何 socket 都被拒绝。"""

    def _blocked(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("B01 夹具测试不得访问网络")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    return {name: _load_golden(name) for name in GOLDEN_FILES}


# --------------------------------------------------------------------------- #
# §1 夹具由真实编译器生成，且没有随时间漂移
# --------------------------------------------------------------------------- #


def test_golden_files_are_byte_identical_to_the_real_compiler_output() -> None:
    """重新跑真实生产入口，必须逐字复现冻结夹具。"""

    rebuilt = builder.build_all()
    for name in GOLDEN_FILES:
        expected = (GOLDEN_DIR / f"{name}.json").read_bytes()
        actual = builder.golden_bytes(rebuilt[name])
        assert actual == expected, (
            f"{name}.json 与真实编译器输出不一致；"
            "行为变化必须显式重新生成夹具并登记新证据"
        )


def test_provenance_pins_every_golden_digest_and_real_owner() -> None:
    provenance = _load_golden("provenance")
    for name in GOLDEN_FILES:
        data = (GOLDEN_DIR / f"{name}.json").read_bytes()
        assert provenance["golden_digests"][name] == builder._sha256(data)

    owners = set(provenance["real_owners"])
    # 三个关键 owner 必须被点名：编译器、请求 builder、Binder。
    assert any("extend_writer_worksets_from_narrative_plan" in item for item in owners)
    assert any("build_publication_writer_request" in item for item in owners)
    assert any("bind_paragraph_witnesses" in item for item in owners)
    assert provenance["legacy_verified"]["verified_complete"] is False
    assert provenance["legacy_verified"]["verified_validation_status"] == "not_run"


def test_fixtures_carry_no_credentials_or_absolute_run_paths(golden: Mapping[str, Any]) -> None:
    """夹具不得内嵌凭据，也不得绑定某次运行的家目录/临时根。"""

    serialized = json.dumps(golden, ensure_ascii=False)
    for token in ("api_key", "API_KEY", "sk-", "Bearer "):
        assert token not in serialized
    assert "/tmp/" not in serialized
    assert str(Path.home()) not in serialized


# --------------------------------------------------------------------------- #
# §2 合法正例：Unified V2 页 + 已完成 Formalizer + 冻结 Narrative
# --------------------------------------------------------------------------- #


def test_legal_page_is_a_real_unified_v2_writer_page(golden: Mapping[str, Any]) -> None:
    page = golden["legal_page_with_atoms"]
    assert page["scenario"] == "legal_page_with_atoms"
    assert page["prompt_template_id"] == "unified_writer_page_v2"
    assert page["page"]["page_kind"] == "technical"
    assert page["page"]["atom_ids"], "技术页必须带真实 atom"
    assert page["invocation"]["role"] == "writer"
    assert page["invocation"]["is_repair"] is False
    # 页身份由 payload 真实重算，不是夹具自报。
    page_id, technical_bytes, technical_digest = compute_technical_page_id(
        archive_digest=page["page"]["technical_payload"]["archive_digest"],
        technical_payload=page["page"]["technical_payload"],
    )
    assert page_id == page["page"]["page_id"]
    assert builder._sha256(technical_bytes) == page["page"]["technical_bytes_sha256"]
    assert technical_digest == page["page"]["technical_bytes_digest"]


def test_legal_page_request_is_the_real_builder_output(golden: Mapping[str, Any]) -> None:
    page = golden["legal_page_with_atoms"]
    payload = page["request"]["input_payload"]
    metadata = payload["shared_context_metadata"][0]
    assert metadata["v2_page_id"] == page["page"]["page_id"]
    assert metadata["page_bytes_digest"] == page["page"]["technical_bytes_digest"]
    # 页合同把段落 id 收成闭集；夹具里的 enum 必须与页段落一致。
    assert page["request"]["response_schema_paragraph_id_enum"] == [
        row["plan_row"]["paragraph_id"] for row in page["paragraphs"]
    ]
    assert payload["binding_contract"]["required_detail_ids"], "合法页必须声明 detail 义务"


def test_completed_formalizer_formula_enters_real_writer_and_binder() -> None:
    fixture = builder.build_completed_formalizer_fixture()
    formalizer = fixture["formalizer"]
    assert formalizer["accepted_package_count"] == 1
    assert formalizer["task_failures"] == []
    assert formalizer["assertion_failures"] == []
    assert formalizer["actual_main_calls"] == 1
    assert formalizer["actual_repair_calls"] == 0
    receipt, = formalizer["receipts"]
    assert receipt["delivery_status"] == "accepted"
    assert receipt["task_status"] == "complete"
    assert receipt["succeeded_task_ids"] == ["ob:rescale"]
    assert receipt["failed_task_ids"] == []
    package, = formalizer["accepted_packages"]
    assert package["review_status"] == "accepted"
    assert package["bound_operation_ids"] == ["op:rescale"]
    assert package["satisfied_obligation_ids"] == ["ob:rescale"]
    writer = fixture["writer"]
    payload = writer["request"]["input_payload"]
    assert payload["formula_packages"][0]["package_id"] == package["package_id"]
    assert payload["binding_contract"]["allowed_formula_obligation_ids"] == ["ob:rescale"]
    assert writer["observed_local_gate"]["content_accepted"] is True
    assert writer["observed_local_gate"]["binder_transaction_valid"] is True
    assert writer["observed_local_gate"]["metrics"]["formula_exact_body_count"] == 1
    assert package["markdown_block"] in writer["paragraphs"][0]["response"]["paragraph_markdown"]
    assert "formula:ob:rescale" in writer["paragraphs"][0]["closed_target_keys"]
    assert writer["verified"]["global_verified_complete"] is False
    assert writer["observed_local_gate"]["metrics"]["formula_consumed_count"] == 1
    assert writer["page"]["technical_payload"]["formula_obligation_ids"] == ["ob:rescale"]
    assert writer["page"]["technical_payload"]["formula_package_ids"] == [package["package_id"]]
    assert "[[FORMULA:" in writer["formula_consumption"]["raw_writer_text"]
    assert package["markdown_block"] not in writer["formula_consumption"]["raw_writer_text"]


@pytest.mark.parametrize(("mutation", "failure_code"), [
    ("unknown_field", "llm_response_parse_error"),
    ("missing_obligation", "llm_result_missing"),
    ("wrong_operator", "missing_required_operator"),
])
def test_formalizer_rejects_invalid_results_before_writer(mutation: str, failure_code: str) -> None:
    fixture = builder.build_completed_formalizer_fixture(response_mutation=mutation)
    assert fixture["formalizer"]["accepted_package_count"] == 0
    assert fixture["formalizer"]["task_failures"]
    assert any(failure_code in failure for failure in fixture["formalizer"]["task_failures"])
    assert fixture["formalizer"]["actual_main_calls"] == 1
    assert fixture["formalizer"]["actual_repair_calls"] == 0
    assert all(receipt["task_status"] != "complete" for receipt in fixture["formalizer"]["receipts"])
    assert fixture["writer"] is None


def test_legal_page_passes_its_declared_local_gate(golden: Mapping[str, Any]) -> None:
    page = golden["legal_page_with_atoms"]
    gate = page["observed_local_gate"]
    assert gate["content_accepted"] is True
    assert gate["metrics"]["failures"] == []
    assert gate["metrics"]["invalid_count"] == 0
    assert gate["metrics"]["authority_violation_count"] == 0
    assert gate["metrics"]["valid_paragraph_count"] == len(page["paragraphs"])
    assert gate["writer_transaction_valid"] is True
    assert gate["binder_transaction_valid"] is True


def test_legal_page_replays_through_the_real_transaction_gates(
    golden: Mapping[str, Any],
) -> None:
    """用冻结响应重放真实 writer_content / final_bound 判定。"""

    page = golden["legal_page_with_atoms"]
    for row in page["paragraphs"]:
        transaction = dict(row["response"])
        transaction["rendered_detail_ids"] = list(row["response"]["rendered_detail_ids"])
        writer_stage = assess_paragraph_transaction(
            transaction, plan_row=row["plan_row"], validation_stage="writer_content"
        )
        assert writer_stage.valid is True
        assert [str(item.code) for item in writer_stage.failures] == []

        bound = bind_paragraph_witnesses(transaction, plan_row=row["plan_row"])
        binder_stage = assess_paragraph_transaction(
            bound, plan_row=row["plan_row"], validation_stage="final_bound"
        )
        assert binder_stage.valid is True
        assert [str(item.code) for item in binder_stage.failures] == []
        assert sorted(bound["rendered_detail_ids"]) == sorted(
            row["observed"]["final_bound"]["derived_rendered_detail_ids"]
        )


def test_legal_page_sentence_claim_map_is_complete(golden: Mapping[str, Any]) -> None:
    """逐句 claim 映射：每句都必须有归属，且必须能追到 closed target。"""

    page = golden["legal_page_with_atoms"]
    for row in page["paragraphs"]:
        mapping = row["sentence_claim_map"]
        assert mapping, "正文至少一句"
        joined = " ".join(item["sentence"] for item in mapping)
        assert joined.strip() == row["response"]["paragraph_markdown"].strip()
        closed = set(row["closed_target_keys"])
        witnessed = [key for item in mapping for key in item["target_keys"]]
        assert witnessed, "合法正例的句子必须承载至少一个 witness"
        assert set(witnessed) <= closed, "句子映射不得引入页合同之外的 target"


def test_legal_page_exact_excerpts_are_verbatim_material(golden: Mapping[str, Any]) -> None:
    page = golden["legal_page_with_atoms"]
    for row in page["paragraphs"]:
        prose = row["response"]["paragraph_markdown"]
        for excerpt in row["exact_excerpts"]:
            assert excerpt["exact_text"] in prose, (
                "可读 exact excerpt 必须逐字来自冻结正文与页材料"
            )


def test_legal_page_request_matches_its_frozen_contract(golden: Mapping[str, Any]) -> None:
    """真实发送前复核：未改动的实际请求与冻结契约一致（空失败集）。"""

    snapshot, payload, cap = _snapshot_for(golden["legal_page_with_atoms"])
    measured = _measured_technical_digest(payload)
    # 合法请求：从真实材料重算的摘要与冻结契约一致（K04 起公共复核要求传入重算值）。
    assert measured == snapshot.technical_bytes_digest
    assert compare_actual_request_to_page_contract(
        snapshot,
        invocation_id=snapshot.invocation_id,
        payload=payload,
        max_output_tokens=cap,
        is_repair=False,
        actual_technical_bytes_digest=measured,
    ) == ()
    assert page_output_cap_failures(
        snapshot,
        _Invocation(cap),
        actual_max_output_tokens=cap,
    ) == ()


# --------------------------------------------------------------------------- #
# §3 合法正例：作者无 atom 页
# --------------------------------------------------------------------------- #


def test_author_no_atom_page_is_a_legal_header_page(golden: Mapping[str, Any]) -> None:
    page = golden["author_no_atom_page"]
    assert page["scenario"] == "author_no_atom_page"
    assert page["page"]["page_kind"] == "header"
    assert list(page["page"]["atom_ids"]) == []
    assert not (page["page"]["technical_payload"].get("atoms") or ())
    assert not (page["page"]["technical_payload"].get("detail_ids") or ())
    assert page["paragraphs"][0]["closed_target_keys"] == []
    # 没有 required_detail_ids 的行走 facet/field/slot/edge 分支，detail 键不出现。
    required = page["paragraphs"][0]["required_targets"]
    assert required.get("detail", []) == []
    assert not any(required.get(kind) for kind in ("facet", "field", "slot", "edge"))


def test_author_no_atom_page_passes_the_same_local_gate(golden: Mapping[str, Any]) -> None:
    page = golden["author_no_atom_page"]
    gate = page["observed_local_gate"]
    assert gate["content_accepted"] is True
    assert gate["metrics"]["required_target_count"] == 0
    assert gate["metrics"]["required_atom_count"] == 0
    assert gate["metrics"]["authority_violation_count"] == 0
    assert gate["writer_transaction_valid"] is True
    assert gate["binder_transaction_valid"] is True


def test_atom_obligation_is_carried_by_the_detail_not_a_separate_target(
    golden: Mapping[str, Any],
) -> None:
    """B01-G2：仅刻画空witness targets的detail-only样例，不证明atom闭包。"""

    page = golden["legal_page_with_atoms"]
    for row in page["paragraphs"]:
        required = required_targets_from_plan_row(row["plan_row"])
        assert set(required) == {"detail", "formula"}
        assert required["detail"] == ("d:rescale",)
        closed = set(row["closed_target_keys"])
        assert closed == {"detail:d:rescale"}
        assert not any(key.startswith("atom:") for key in closed)
        assert row["plan_row"]["witness_contract"]["targets"] == []
    assert page["observed_local_gate"]["metrics"]["required_atom_count"] == 0


# --------------------------------------------------------------------------- #
# §4 具名非法反例
# --------------------------------------------------------------------------- #


def _measured_technical_digest(payload: Mapping[str, Any]) -> str:
    """从 payload 的**实际材料字节**重算技术字节摘要（K04 的公共复核入参）。

    与真实 Writer 调用点同规则：取 ``shared_contexts`` 的第一个元素，Mapping 走规范化
    JSON 字节；空材料返回空串（由公共复核 fail-closed）。
    """

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
    return hash_text(data.decode("utf-8")) if data else ""


def _snapshot_for(fixture: Mapping[str, Any]):
    """按生产接线重建冻结契约（含 cap / 技术字节摘要的注入）。"""

    payload = fixture["request"]["input_payload"]
    frozen = fixture["page_contract_frozen"]
    snapshot = page_contract_snapshot_from_payload(
        invocation_id=fixture["invocation"]["invocation_id"],
        payload=payload,
        request_digest=fixture["request"]["page_contract_snapshot"]["request_digest"],
    )
    updates: dict[str, Any] = {}
    if frozen["effective_max_output_tokens"] > 0:
        updates["max_output_tokens"] = frozen["effective_max_output_tokens"]
    if frozen["effective_technical_bytes_digest"]:
        updates["technical_bytes_digest"] = frozen["effective_technical_bytes_digest"]
    if updates:
        snapshot = snapshot.model_copy(update=updates)
    return snapshot, payload, resolve_frozen_page_output_cap(snapshot)


class _Invocation:
    """生产里 invocation 计划对象的最小替身，只提供真实读取的字段。"""

    def __init__(self, max_output_tokens: int) -> None:
        self.max_output_tokens = max_output_tokens


def _section_stub(fixture: Mapping[str, Any]) -> WriterSectionInput:
    rows = [row["plan_row"] for row in fixture["paragraphs"]]
    return WriterSectionInput(
        section_id=fixture["section_id"],
        heading=fixture["heading"],
        prompt_payload={
            "section_id": fixture["section_id"],
            "heading": fixture["heading"],
            "narrative_plan": {
                "section_id": fixture["section_id"],
                "page_id": fixture["page"]["page_id"],
                "page_paragraph_ids": [row["paragraph_id"] for row in rows],
                "paragraphs": rows,
            },
            "shared_context_metadata": [{"v2_page_id": fixture["page"]["page_id"]}],
        },
        argument_graph={"paragraphs": rows},
    )


def _observed_for_surface(
    fixture: Mapping[str, Any], surface: str, mutated: Mapping[str, Any]
) -> list[str]:
    if surface == "page_contract":
        raise AssertionError("page_contract 反例由 _observed_page_contract 处理")
    if surface == "response_parser":
        parsed, _trace, error = try_parse_structured_response_with_trace(
            json.dumps(mutated, ensure_ascii=False), PublicationMethodSectionOutputV1
        )
        if error:
            return [error]
        _normalized, failures = _normalize_publication_paragraph_transaction(
            parsed, section=_section_stub(fixture), require_transactions=True
        )
        return [str(item) for item in failures]
    if surface in {"paragraph_assessor", "binder"}:
        row = fixture["paragraphs"][0]
        transaction = {
            "paragraph_id": mutated["paragraphs"][0]["paragraph_id"],
            "paragraph_markdown": mutated["paragraphs"][0]["paragraph_markdown"],
            "rendered_detail_ids": list(mutated["paragraphs"][0]["rendered_detail_ids"]),
            "witnesses": list(mutated["paragraphs"][0]["witnesses"]),
        }
        stage = "writer_content" if surface == "paragraph_assessor" else "final_bound"
        subject = (
            transaction
            if stage == "writer_content"
            else bind_paragraph_witnesses(transaction, plan_row=row["plan_row"])
        )
        assessment = assess_paragraph_transaction(
            subject, plan_row=row["plan_row"], validation_stage=stage
        )
        return [str(item.code) for item in assessment.failures]
    raise AssertionError(f"未知 surface：{surface}")


def _observed_page_contract(
    fixture: Mapping[str, Any], mutation: Mapping[str, Any]
) -> list[str]:
    snapshot, payload, cap = _snapshot_for(fixture)
    mutated = builder.apply_mutation(payload, mutation)
    if mutation["operation"] == "drop_frozen_contract":
        mutated.pop("__frozen_contract__", None)
        return list(compare_actual_request_to_page_contract(
            None,
            invocation_id=snapshot.invocation_id,
            payload=mutated,
            max_output_tokens=cap,
            is_repair=True,
        ))
    delta = int(mutated.pop("__max_output_tokens_delta__", 0))
    actual_cap = cap + delta if mutation["operation"] == "cap_delta" else cap
    contract_failures = list(compare_actual_request_to_page_contract(
        snapshot,
        invocation_id=snapshot.invocation_id,
        payload=mutated,
        max_output_tokens=actual_cap,
        is_repair=False,
    ))
    contract_failures.extend(page_output_cap_failures(
        snapshot, _Invocation(cap), actual_max_output_tokens=actual_cap
    ))
    return contract_failures


def _observed_page_model(fixture: Mapping[str, Any], mutation: Mapping[str, Any]) -> list[str]:
    page = fixture["page"]
    payload = dict(page["technical_payload"])
    operation = str(mutation["operation"])
    if operation == "page_kind_without_atoms":
        payload = {**payload, "atoms": [], "projection_proof": {}}
        atom_ids: tuple[str, ...] = ()
    else:
        payload = {**payload, "projection_proof": {}}
        atom_ids = tuple(page["atom_ids"])
    page_id, _bytes, technical_digest = compute_technical_page_id(
        archive_digest=payload["archive_digest"], technical_payload=payload
    )
    # token_estimate 也是被校验字段；先按真实规则重算，避免它抢先报错。
    token_estimate = conservative_token_estimate(payload)
    try:
        ConsumerTechnicalPageV2(
            page_id=page_id,
            page_kind="technical",
            archive_digest=payload["archive_digest"],
            mechanism_id=page["mechanism_id"],
            atom_ids=atom_ids,
            technical_payload=payload,
            technical_bytes_digest=technical_digest,
            token_estimate=token_estimate,
        )
    except Exception as exc:  # noqa: BLE001 - 这里就是要记录真实拒绝文本
        return [str(exc)]
    return []


@pytest.mark.parametrize(
    "case",
    _load_golden("invalid_counterexamples")["cases"],
    ids=lambda case: case["name"],
)
def test_named_counterexamples_are_rejected_by_name(
    golden: Mapping[str, Any], case: Mapping[str, Any]
) -> None:
    fixture = golden[case["base"]]
    surface = case["surface"]
    if surface == "page_contract":
        observed = _observed_page_contract(fixture, case["mutation"])
    elif surface == "page_model":
        observed = _observed_page_model(fixture, case["mutation"])
    else:
        mutated = builder.apply_mutation(
            builder.frozen_subject(fixture, surface), case["mutation"]
        )
        observed = _observed_for_surface(fixture, surface, mutated)
    assert observed, f"{case['name']} 竟然没有被拒绝"
    assert any(case["expected"] in item for item in observed), (
        f"{case['name']} 未按具名结果被拒：expected={case['expected']!r} observed={observed}"
    )


def test_every_counterexample_is_exactly_one_mutation(golden: Mapping[str, Any]) -> None:
    """反例必须是"冻结正例 + 一处改动"，且两侧都有具名期望。"""

    names = set()
    for case in golden["invalid_counterexamples"]["cases"]:
        assert case["name"] not in names
        names.add(case["name"])
        assert case["base"] in SCENARIOS
        assert case["expected_kind"] in {
            "page_contract", "response_parser", "paragraph_assessor", "binder", "page_model",
        }
        assert case["expected"]
        mutation = case["mutation"]
        assert mutation["operation"] in {
            "set", "append", "cap_delta", "drop_frozen_contract",
            "page_kind_without_atoms", "projection_proof_mismatch",
        }
    # 五个面都要有真实反例，不能只测页合同。
    assert {case["expected_kind"] for case in golden["invalid_counterexamples"]["cases"]} == {
        "page_contract", "response_parser", "paragraph_assessor", "binder", "page_model",
    }


# --------------------------------------------------------------------------- #
# §5 旧路径特征：Verified 为空，不能当作新桥已验证
# --------------------------------------------------------------------------- #


def test_positive_fixtures_do_not_claim_global_verified(golden: Mapping[str, Any]) -> None:
    for name in ("legal_page_with_atoms", "author_no_atom_page"):
        verified = golden[name]["verified"]
        assert verified["global_verified_status"] == "not_run"
        assert verified["global_verified_complete"] is False
        assert verified["local_gate"] == "writer_content+final_bound page transaction"


def test_legacy_pipeline_reports_verified_not_run(tmp_path: Path) -> None:
    """跑一次真实旧产品路径：局部接受为真，全局 Verified 仍未运行。"""

    from code2paper.agentic.publication_method_writer import (
        run_publication_method_writer,
    )
    from tests.test_agentic_publication_method_writer import _config
    from tests.test_agentic_publication_method_writer_unified import (
        _clear_unified_budget_env,
        _mock_writer_caller,
        _unified_artifacts,
    )

    try:
        paths = _unified_artifacts(tmp_path)
        result, outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=_mock_writer_caller,
            authoring_context_mode="unified",
        )
    finally:
        _clear_unified_budget_env()

    writer_result = json.loads(
        Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    )
    # 局部：本节 Writer 事务真的成功了。
    assert writer_result["writer_transaction_status"] == "success"
    assert writer_result["section_results"][0]["accepted"] is True
    # 全局：没有验证、没有 Verified、不能发布。
    assert writer_result["candidate_validation_status"] == "not_run"
    assert writer_result["verified_validation_status"] == "not_run"
    assert writer_result["verified_complete"] is False
    assert writer_result["publication_ready"] is False
    assert result.status != "blocked"
    assert writer_result["status"] != "success" or writer_result["verified_complete"] is False


def test_missing_measured_technical_digest_is_refused_by_the_helper(
    golden: Mapping[str, Any],
) -> None:
    """B01-G1 / K04：实际材料被改而调用方给不出重算值时，公共复核 fail-closed。

    B01 记录的现状是"payload 不声明摘要 → 比较被跳过"；K04 把公共入口改为接收**从实际
    材料字节重算**的摘要，缺重算值即具名拒绝。原特征断言
    ``test_absent_actual_technical_digest_is_not_detected_by_the_helper`` 已由本测试取代，
    原日志保持原字节。
    """

    fixture = golden["legal_page_with_atoms"]
    snapshot, payload, cap = _snapshot_for(fixture)
    assert payload.get("technical_bytes_digest") is None
    measured = _measured_technical_digest(payload)
    assert measured == snapshot.technical_bytes_digest

    # 未改动的合法请求：重算值与冻结值一致 → 放行。
    assert compare_actual_request_to_page_contract(
        snapshot,
        invocation_id=snapshot.invocation_id,
        payload=payload,
        max_output_tokens=cap,
        is_repair=False,
        actual_technical_bytes_digest=measured,
    ) == ()

    tampered = dict(payload)
    tampered["shared_contexts"] = [
        {**tampered["shared_contexts"][0], "tampered": True}
    ]
    tampered_measured = _measured_technical_digest(tampered)
    assert tampered_measured and tampered_measured != measured

    # 缺重算值（旧实现会跳过比较）→ 具名拒绝。
    assert compare_actual_request_to_page_contract(
        snapshot,
        invocation_id=snapshot.invocation_id,
        payload=tampered,
        max_output_tokens=cap,
        is_repair=False,
    ) == (f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:technical_bytes_unknown",)

    # 传入从被改材料重算的值 → 具名拒绝。
    assert compare_actual_request_to_page_contract(
        snapshot,
        invocation_id=snapshot.invocation_id,
        payload=tampered,
        max_output_tokens=cap,
        is_repair=False,
        actual_technical_bytes_digest=tampered_measured,
    ) == (f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:technical_bytes",)

    # 声明字段写着旧摘要也不能替代重算（伪造 hash）。
    declared = dict(tampered)
    declared["technical_bytes_digest"] = measured
    assert compare_actual_request_to_page_contract(
        snapshot,
        invocation_id=snapshot.invocation_id,
        payload=declared,
        max_output_tokens=cap,
        is_repair=False,
        actual_technical_bytes_digest=tampered_measured,
    ) == (f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:technical_bytes",)


def test_g3_unified_contract_cannot_freeze_a_page_without_a_material_identity(
    golden: Mapping[str, Any],
) -> None:
    """K04-G3：冻结侧"确实没有 technical digest"的形态在 unified lane 被构造性拒绝。

    公共复核在冻结摘要缺失时不产出技术字节失败码（由 envelope/逐字比较兜底），但这条
    分支**不是** unified lane 的兼容路径：页与 invocation 两个 owner 都拒绝空材料身份。
    因此不存在"冻结侧无摘要却仍被发送"的合法 unified 形态；旧档案必须走具名只读 reader，
    不能靠放宽新合同获得兼容。golden 夹具本身证明合法旧**请求**（payload 不声明摘要）
    仍可经可信 adapter 从 bytes 补实测值放行。
    """

    fixture = golden["legal_page_with_atoms"]
    page = fixture["page"]
    page_payload = dict(page["technical_payload"])
    page_id, _bytes, technical_digest = compute_technical_page_id(
        archive_digest=page_payload["archive_digest"],
        technical_payload=page_payload,
    )
    assert technical_digest == page["technical_bytes_digest"]

    # 1) 页 owner：空材料摘要不是合法页。
    with pytest.raises(Exception, match="technical_bytes_digest"):
        ConsumerTechnicalPageV2(
            page_id=page_id,
            page_kind=page["page_kind"],
            archive_digest=page_payload["archive_digest"],
            mechanism_id=page["mechanism_id"],
            atom_ids=tuple(page["atom_ids"]),
            technical_payload=page_payload,
            technical_bytes_digest="",
            token_estimate=conservative_token_estimate(page_payload),
        )

    # 2) invocation owner：空 expected 材料摘要不是合法合同。
    from code2paper.agentic.unified_context_models import ConsumerInvocationV1

    with pytest.raises(Exception, match="expected_technical_bytes_digest"):
        ConsumerInvocationV1(
            invocation_id="inv:g3:legacy",
            role="writer",
            phase="writer",
            workset_id="workset:g3",
            task_ids=("task:g3",),
            mechanism_id=page["mechanism_id"],
            section_id=fixture["section_id"],
            page_id=page_id,
            expected_technical_bytes_digest="",
            expected_request_envelope_digest="sha256:envelope",
            max_input_tokens=1024,
            max_output_tokens=512,
            max_attempts=1,
        )

    # 3) 合法旧请求（payload 不声明摘要）仍从 bytes 补实测值放行，与冻结页身份一致。
    snapshot, payload, cap = _snapshot_for(fixture)
    assert payload.get("technical_bytes_digest") is None
    assert snapshot.technical_bytes_digest == technical_digest
    assert compare_actual_request_to_page_contract(
        snapshot,
        invocation_id=snapshot.invocation_id,
        payload=payload,
        max_output_tokens=cap,
        is_repair=False,
        actual_technical_bytes_digest=_measured_technical_digest(payload),
    ) == ()


# --------------------------------------------------------------------------- #
# §6 已记录的生产缺陷（B01-D1）
# --------------------------------------------------------------------------- #


def test_join_page_identity_and_narrative_order_are_stable_across_hash_seeds() -> None:
    """B01-D1（K04 修复）：多段落 join 页跨进程保持 Narrative 顺序与页身份。

    修复前这是缺陷特征断言（``len(set(observed.values())) > 1``）：``_flush_current``
    把 ``current_paragraph_ids`` 以 ``set`` 传出，段落顺序取决于 ``PYTHONHASHSEED``。
    K04 把累加器改为保序结构后，同一输入在多个独立进程与 hash seed 下必须得到相同的
    段落顺序、``technical_bytes_digest`` 与 ``page_id``；探针的默认计划是**非字典序**
    的（叙述顺序 p2 在 p10 之前），因此"保序"与"恰好等于字典序"不会混淆。

    这里不固定 seed、不排序、不改夹具材料：seed 只用于证明跨进程稳定。
    """

    seeds = ("0", "1", "2", "3", "random")
    for mode in ("narrative", "lexicographic"):
        observed: dict[str, tuple[str, str, str]] = {}
        for seed in seeds:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tests.integrations.dsh.fixtures.join_page_probe",
                    *([] if mode == "narrative" else ["lexicographic"]),
                ],
                cwd=REPO_ROOT,
                env={**_subprocess_env(), "PYTHONHASHSEED": seed},
                capture_output=True,
                text=True,
                check=False,
            )
            assert completed.returncode == 0, completed.stderr
            lines = completed.stdout.strip().splitlines()
            paragraph_line = next(
                line for line in lines if line.startswith("paragraph_ids=")
            )
            digest_line = next(
                line for line in lines if line.startswith("technical_bytes_digest=")
            )
            page_id = lines[-1]
            observed[seed] = (paragraph_line, digest_line, page_id)

        assert len(set(observed.values())) == 1, (
            "B01-D1 回归：同一输入在不同 hash seed 下不再稳定 "
            f"(mode={mode}): {observed}"
        )
        paragraph_ids = observed["0"][0].split("=", 1)[1].split(",")
        if mode == "narrative":
            # Narrative 顺序来自计划，不是字典序（字典序会把 p10 排在 p2 前）。
            assert paragraph_ids == ["MA-P1_p2", "MA-P1_p10"], paragraph_ids
            assert paragraph_ids != sorted(paragraph_ids), (
                "探针计划必须是非字典序的，否则无法区分保序与排序"
            )
        else:
            assert paragraph_ids == ["MA-P1_p1", "MA-P1_p2"], paragraph_ids
        assert observed["0"][2].startswith("page:")
        assert observed["0"][1].startswith("technical_bytes_digest=sha256:")

    # 两种计划必须给出不同的页身份，否则本测试无法证明顺序真的参与身份计算。
    narrative = subprocess.run(
        [sys.executable, "-m", "tests.integrations.dsh.fixtures.join_page_probe"],
        cwd=REPO_ROOT,
        env={**_subprocess_env(), "PYTHONHASHSEED": "0"},
        capture_output=True,
        text=True,
        check=False,
    )
    lexicographic = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.integrations.dsh.fixtures.join_page_probe",
            "lexicographic",
        ],
        cwd=REPO_ROOT,
        env={**_subprocess_env(), "PYTHONHASHSEED": "0"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert narrative.stdout.strip().splitlines()[-1] != (
        lexicographic.stdout.strip().splitlines()[-1]
    ), "段落顺序必须参与 page_id 计算"


def _subprocess_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + str(REPO_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def test_g5_order_families_are_classified_by_single_variable_reordering() -> None:
    """K04-G5：分别只改一个家族顺序，核查实际请求的 Narrative 段落序列。

    判据不是"所有 sorted 都是缺陷"，而是按语义分族：

    * ``narrative``（段落序列，承担渲染语义）：顺序来自计划且参与页身份；重排计划即
      重排实际请求的 Narrative 段落列表。
    * ``unit_details`` / ``unit_mechanisms``（纯集合型 ID）：重排同一集合**不重排**
      Narrative 段落序列，也不改变页材料身份 —— 它们是集合语义，规范排序允许。

    探针调用真实编译入口；默认（无 family）输出与 B01-D1 跨 seed 回归登记的字节一致。
    """

    from .fixtures import join_page_probe

    baseline = join_page_probe.probe_page()
    base_paragraphs = [str(item) for item in baseline.technical_payload["paragraph_ids"]]
    assert base_paragraphs == ["MA-P1_p2", "MA-P1_p10"], base_paragraphs

    for family in ("unit_details", "unit_mechanisms"):
        page = join_page_probe.probe_page(family=family)
        assert [
            str(item) for item in page.technical_payload["paragraph_ids"]
        ] == base_paragraphs, f"{family} 重排不得改动 Narrative 段落序列"
        assert page.page_id == baseline.page_id, (
            f"{family} 是纯集合族：只换顺序不构成新材料身份"
        )
        assert page.technical_bytes_digest == baseline.technical_bytes_digest

    swapped = join_page_probe.probe_page(family="narrative")
    swapped_paragraphs = [
        str(item) for item in swapped.technical_payload["paragraph_ids"]
    ]
    assert swapped_paragraphs == list(reversed(base_paragraphs)), swapped_paragraphs
    assert set(swapped_paragraphs) == set(base_paragraphs), "只换顺序，段落集合不变"
    assert swapped.page_id != baseline.page_id, "Narrative 顺序必须参与页身份"
    assert swapped.technical_bytes_digest != baseline.technical_bytes_digest


def test_g6_every_golden_registers_an_independent_historical_digest_source() -> None:
    """K04-G6：四个 golden 各自登记独立旧摘要出处；无出处的如实标未证明。

    登记同时绑定**出处文件自身的 sha256**：出处被改写时登记立即失效，不能靠重新生成
    夹具把历史改写成"一直如此"。夹具目录当前未被 git 跟踪 —— 未跟踪状态不是测试失败，
    也不授权 add/commit。
    """

    provenance = _load_golden("provenance")
    registry = provenance["golden_historical_digests"]
    assert set(registry) == set(GOLDEN_FILES)

    attested: list[str] = []
    for name in GOLDEN_FILES:
        row = registry[name]
        assert row["digest"] == provenance["golden_digests"][name], row
        assert row["digest"] == builder._sha256(
            (GOLDEN_DIR / f"{name}.json").read_bytes()
        ), row
        if row["status"] == "not_proven":
            assert row["source"] == "" and row["source_sha256"] == "", row
            continue
        assert row["status"] == "attested", row
        source = REPO_ROOT / str(row["source"])
        assert source.is_file(), row
        assert builder._sha256(source.read_bytes()) == row["source_sha256"], (
            f"{name} 的旧摘要出处文件已被改写，登记失效"
        )
        source_text = source.read_text(encoding="utf-8")
        # 交接记录里登记的是裸 hex（无 ``sha256:`` 前缀），两种写法都接受。
        assert row["digest"] in source_text or (
            row["digest"].removeprefix("sha256:") in source_text
        ), row
        attested.append(name)

    # 诚实边界：三个 golden 有独立旧出处，第四个（completed_formalizer_page）没有。
    assert len(attested) == 3, attested
    assert registry["completed_formalizer_page"]["status"] == "not_proven"
    assert "未证明" in registry["completed_formalizer_page"]["note"]


def test_g4_partial_witness_split_must_conserve_the_obligation_multiset() -> None:
    """K04-G4：witness 只覆盖部分义务的合法最小计划，分裂后义务多重集必须守恒。

    真实反例（修前）：同一段落里 ob1 有 formula target、ob3 没有；段落因页预算分裂成
    三个分片后 ob3 不出现在任何分片，而 **target** 多重集仍然守恒，于是 ``failures`` 为空
    —— 静默丢义务。K04 起按输入行与全部分片比较完整义务/公式包多重集，不守恒即具名阻断。

    合法对照（无 target / 只有 detail target）必须守恒且不产生失败：排除义务需要显式
    合同前置与可验证的授权变更，当前合同没有这种前置。
    """

    from .fixtures import page_split_probe as probe

    # 反例：只给 ob1 一个 formula target（witness 部分覆盖）。
    partial = probe.split_paragraph(targets=({
        "target_kind": "formula",
        "target_id": probe.OBLIGATION_IDS[0],
        "required": True,
    },))
    assert partial.input_obligations == {
        probe.OBLIGATION_IDS[0]: 1,
        probe.OBLIGATION_IDS[1]: 1,
    }, partial.input_obligations
    assert len(partial.fragment_ids) >= 2, partial.fragment_ids
    assert partial.fragment_obligations != partial.input_obligations, (
        "该产物形态必须仍被检出：分片并没有补上未覆盖的义务"
    )
    assert partial.failures == (
        f"paragraph_split_obligation_contract_not_conserved:"
        f"{probe.PARAGRAPH_ID}:missing=1:duplicated=0",
    ), partial.failures
    # 明细多重集不受影响（分裂只按明细闭包切分）。
    assert partial.fragment_details == partial.input_details

    # 合法对照：无 target 与只有 detail target 都必须守恒且零失败。
    for label, targets in (
        ("no_targets", ()),
        ("detail_target_only", ({
            "target_kind": "detail",
            "target_id": probe.DETAIL_IDS[0],
            "required": True,
        },)),
    ):
        control = probe.split_paragraph(targets=targets)
        assert len(control.fragment_ids) >= 2, (label, control.fragment_ids)
        assert control.fragment_obligations == control.input_obligations, label
        assert control.fragment_details == control.input_details, label
        assert control.failures == (), (label, control.failures)


def test_gap2_nonempty_formula_families_order_contract_three_layers() -> None:
    """K04-GAP-2：**非空** formula_obligation_ids / formula_package_ids 的单变量顺序对照。

    与 G4 的 `page_split_probe` 同一份材料（单机制技术页），但计划里两个公式家族都**非空**
    （各 2 个 ID，真实 obligation 对象 + 与真实 payload 同形的序列化 package 记录）。
    逐层报告：

    ① Narrative 段落序与闭包关联：任何家族重排都不改动页/请求的段落序列，package→source
       detail 关联（顺序无关映射）逐字不变；
    ② 实际冻结/重算身份：页材料在 `_section_page_payload` 里对两个家族做**规范排序**，因此
       计划层重排被吸收，page_id 与技术字节摘要不变；请求侧的 Narrative 计划行保留计划顺序
       （`allowed_formula_obligation_ids` 随之、`allowed_formula_package_ids` 取页材料顺序）；
    ③ 公共复核：scope 按排序集合比较 → 同一 ID 集重排**不产生** `scope:` 失败；整体
       `binding_contract_digest` 仍按有序序列计算 → 具名拒绝；若同时改材料位点，还多一条
       `technical_bytes`。不为了"通过"弱化摘要。
    """

    from .fixtures import formula_family_probe as probe

    baseline = probe.compile_material()
    assert probe.family_ids(baseline.page_payload, "obligation") == (
        "ob:g4:1",
        "ob:g4:3",
    )
    assert probe.family_ids(baseline.page_payload, "package") == (
        "pkg:formula:ob:g4:1",
        "pkg:formula:ob:g4:3",
    )
    base_paragraphs = tuple(str(item) for item in baseline.page_payload["paragraph_ids"])
    base_closure = probe.package_source_detail_map(baseline.page_payload)
    assert base_closure == {
        "pkg:formula:ob:g4:1": ("d:g4:1",),
        "pkg:formula:ob:g4:3": ("d:g4:3",),
    }
    assert probe.recheck(baseline, label="baseline").failures == ()

    for family in probe.ORDER_FAMILIES:
        page = probe.compile_material(order=family)
        # ① Narrative 段落序与闭包关联不受家族顺序影响。
        assert tuple(
            str(item) for item in page.page_payload["paragraph_ids"]
        ) == base_paragraphs, family
        assert probe.package_source_detail_map(page.page_payload) == base_closure, family
        assert (
            (page.request_payload.get("narrative_plan") or {}).get("page_paragraph_ids")
            == ["MA-G4_p1"]
        ), family
        # ② 页材料规范排序：计划层重排被吸收，页身份与摘要不变。
        assert probe.family_ids(page.page_payload, family) == probe.family_ids(
            baseline.page_payload, family
        ), family
        assert page.page_id == baseline.page_id, family
        assert page.page_digest == baseline.page_digest, family
        # 请求侧保留计划顺序（单变量），且包→明细关联仍是同一映射。
        reversed_ids = tuple(
            reversed(probe.plan_row_family_ids(baseline.request_payload, family))
        )
        assert probe.plan_row_family_ids(page.request_payload, family) == reversed_ids, family
        assert probe.package_source_detail_map(page.request_payload) == base_closure, family

        # ③ binding contract 单独重排：具名整体摘要拒绝，但**没有** scope 失败。
        binding_only = probe.recheck(
            baseline, label=f"{family}/binding", family=family, sites="binding"
        )
        assert binding_only.binding_failure is True, binding_only
        assert binding_only.scope_failures == (), binding_only
        assert binding_only.material_failure is False, binding_only
        # ③ 连同材料位点一起重排：材料身份也随之具名拒绝，scope 仍无失败。
        all_sites = probe.recheck(
            baseline, label=f"{family}/all", family=family, sites="all"
        )
        assert all_sites.binding_failure is True, all_sites
        assert all_sites.material_failure is True, all_sites
        assert all_sites.scope_failures == (), all_sites

    # 本用例只覆盖非空 formula obligation/package 两个家族；unit_mechanisms 对照不折抵它们。
    assert set(probe.ORDER_FAMILIES) == {"obligation", "package"}
