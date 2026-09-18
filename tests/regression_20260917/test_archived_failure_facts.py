"""WP0：固定 2026-09-17 EBCAR intent-v4 P7 authoring 事故的既有事实（方案 §4.2）。

这些用例**不是**修复后的行为断言，而是历史事实的冻结：
它们保证后续 WP1–WP7 的改动不能靠"重新解释这次失败"来宣称成功。
所有输入来自仓库内已提交的归档，离线运行，不读宿主 `/tmp`。
"""

from __future__ import annotations

import hashlib
import json

from . import incident_archive as archive

EMPTY_SLOT_KEYS = {
    "content_digest",
    "formula_obligation_ids",
    "formula_package_ids",
    "mechanism_id",
    "optional_detail_ids",
    "paragraph_id",
    "reader_goal",
    "required_detail_ids",
    "role",
    "section_id",
    "suggested_depth",
    "transition_from",
    "transition_to",
    "witness_contract",
}

IDENTITY_KEYS = {
    "schema_version",
    "run_id",
    "code_commit_sha",
    "dirty_manifest_digest",
    "launcher_digest",
    "profile_digest",
    "model_identity",
    "model_identity_digest",
    "repo_snapshot_id",
    "project_tree_hash",
    "symbol_index_digest",
    "source_manifest_digest",
    "content_digest",
}


def _detail_failure(paragraph_id: str, target: str) -> str:
    return f"{paragraph_id}:detail:detail:{target}"


# --------------------------------------------------------------------------- #
# 0. 冻结 oracle 本身
# --------------------------------------------------------------------------- #


def test_archived_oracle_matches_pinned_identity() -> None:
    """每个固定条目必须同时匹配 Git blob SHA 与 sha256。"""

    for key, item in archive.PINNED.items():
        data = archive.archive_path(key).read_bytes()
        assert archive.git_blob_sha1(data) == item.git_blob_sha, key
        assert "sha256:" + hashlib.sha256(data).hexdigest() == item.sha256, key


# --------------------------------------------------------------------------- #
# 1. 第 4 次记录是拒发，不是新的模型内容试验
# --------------------------------------------------------------------------- #


def test_attempt4_is_not_a_new_content_trial() -> None:
    record = archive.read_json("attempt_0004_completed")

    assert record["attempt"] == 4
    assert record["sent_to_caller"] is False
    assert record["provider_usage"] is None
    assert record["delivery_status"] == "rejected"
    assert record["delivery_rejection_code"] == (
        f"attempt_limit_exhausted:{archive.INCIDENT_INVOCATION}:4>2"
    )
    assert record["content_repair_attempt"] is False
    assert record["failed_task_ids"] == ["MA-S3"]

    # 拒发不会留下 provider 请求/响应——它不是一次内容试验。
    assert not archive.incident_attempt_path("attempt-0004.provider-request.json").exists()
    assert not archive.incident_attempt_path(
        "attempt-0004.provider-response.json"
    ).exists()


def test_attempt3_is_also_a_presend_rejection() -> None:
    record = archive.read_json("attempt_0003_completed")

    assert record["attempt"] == 3
    assert record["sent_to_caller"] is False
    assert record["provider_usage"] is None
    assert record["delivery_status"] == "rejected"
    assert record["delivery_rejection_code"] == (
        f"attempt_limit_exhausted:{archive.INCIDENT_INVOCATION}:3>2"
    )
    assert not archive.incident_attempt_path("attempt-0003.provider-request.json").exists()


def test_only_attempts_1_and_2_reached_the_provider() -> None:
    first = archive.read_json("attempt_0001_request")
    second = archive.read_json("attempt_0002_request")
    assert first["attempt"] == 1
    assert second["attempt"] == 2
    assert archive.incident_attempt_path("attempt-0001.provider-response.json").exists()
    assert archive.incident_attempt_path("attempt-0002.provider-response.json").exists()

    first_done = json.loads(
        archive.incident_attempt_path("attempt-0001.completed.json").read_text()
    )
    second_done = json.loads(
        archive.incident_attempt_path("attempt-0002.completed.json").read_text()
    )
    assert first_done["sent_to_caller"] is True
    assert second_done["sent_to_caller"] is True
    assert first_done["content_repair_attempt"] is False
    assert second_done["content_repair_attempt"] is True


# --------------------------------------------------------------------------- #
# 2. 回执核对：MA-S3 是 15/16，聚合未完成
# --------------------------------------------------------------------------- #


def test_s3_receipt_is_15_of_16() -> None:
    receipts = archive.read_json("writer_section_receipts")["receipts"]
    by_section = {item["section_id"]: item for item in receipts}
    s3 = by_section["MA-S3"]

    required = set(s3["required_invocation_ids"])
    completed = set(s3["completed_invocation_ids"])
    assert len(required) == 16
    assert len(completed) == 15
    assert required - completed == {archive.INCIDENT_INVOCATION}
    assert len(s3["completed_receipt_digests"]) == 15

    # 目录存在（含 4 个 attempt 记录）不等于 accepted/complete。
    for name in (
        "attempt-0001.completed.json",
        "attempt-0002.completed.json",
        "attempt-0003.completed.json",
        "attempt-0004.completed.json",
    ):
        assert archive.incident_attempt_path(name).is_file()


def test_writer_aggregate_is_not_complete() -> None:
    aggregate = archive.read_json("writer_aggregate_receipt")

    assert aggregate["required_section_ids"] == [
        "MA-S1",
        "MA-S2",
        "MA-S3",
        "MA-S4",
        "MA-S5",
    ]
    assert aggregate["completed_section_ids"] == [
        "MA-S1",
        "MA-S2",
        "MA-S4",
        "MA-S5",
    ]
    assert "MA-S3" not in aggregate["completed_section_ids"]
    assert aggregate["all_required_sections_complete"] is False

    result = archive.read_json("writer_result")
    assert result["status"] == "blocked"
    assert result["candidate_available"] is False
    assert result["writer_transaction_status"] == "not_run"
    assert "writer_v2_invocation_acceptance_count" in result["blocked_reason"]
    assert result["blocked_reason"].endswith(
        f"{archive.INCIDENT_INVOCATION}:0"
    )


# --------------------------------------------------------------------------- #
# 3. 第 2 次缺的是两个 detail witness，不能用 atom 数量替代
# --------------------------------------------------------------------------- #


def test_attempt1_lost_fifteen_paragraphs() -> None:
    acceptance = archive.read_json("attempt_0001_acceptance")
    assert acceptance["accepted"] is False
    missing = {
        failure.split(":", 1)[1]
        for failure in acceptance["failures"]
        if failure.startswith("missing_paragraph:")
    }
    assert missing == {f"MA-S3:P{n}" for n in range(3, 18)}

    fragment = json.loads(archive.read_json("attempt_0002_response")["response_text"])
    assert [item["paragraph_id"] for item in fragment["paragraphs"]] == list(
        archive.INCIDENT_PAGE_PARAGRAPH_IDS
    )

    first_record = json.loads(
        archive.incident_attempt_path("attempt-0001.provider-response.json").read_text()
    )
    first_fragment = json.loads(first_record["response_text"])
    assert [item["paragraph_id"] for item in first_fragment["paragraphs"]] == [
        "MA-S3:P1__f1"
    ]


def test_attempt2_missing_detail_not_atom() -> None:
    acceptance = archive.read_json("attempt_0002_acceptance")
    assert acceptance["accepted"] is False
    assert acceptance["content_acceptance_status"] == "rejected"
    assert acceptance["validator"] == "writer-paragraph-transaction-v1"
    assert acceptance["repair_committed"] is False

    expected = {
        _detail_failure("MA-S3:P1__f1", target)
        for target in archive.INCIDENT_MISSING_DETAIL_TARGETS
    } | {"invalid_count", "invalid_witness_count"}
    assert set(acceptance["failures"]) == expected
    assert not [
        failure for failure in acceptance["failures"] if failure.startswith("missing_paragraph:")
    ]

    # 完整响应表面：有 atom 声明，但没有任何 detail 声明，rendered_detail_ids 为空。
    full_text = acceptance["response_text"]
    assert full_text.count('"witness_kind":"atom"') > 0
    assert '"witness_kind":"detail"' not in full_text
    for target in archive.INCIDENT_MISSING_DETAIL_TARGETS:
        assert f'"target_id":"atom:detail:{target}' in full_text
    assert '"rendered_detail_ids":[]' in full_text

    # 两个表面并存：完整响应含 section_markdown，compact fragment 不含。
    fragment_text = archive.read_json("attempt_0002_response")["response_text"]
    assert '"section_markdown"' in full_text
    assert '"section_markdown"' not in fragment_text


# --------------------------------------------------------------------------- #
# 4. 15 个槽位在 Writer 表面没有各自材料
# --------------------------------------------------------------------------- #


def test_s3_slots_carry_no_per_paragraph_material() -> None:
    request = archive.read_json("attempt_0002_request")
    plan = request["input_payload"]["narrative_plan"]
    paragraphs = plan["paragraphs"]
    assert plan["section_id"] == "MA-S3"
    assert plan["page_id"] == archive.INCIDENT_PAGE_ID
    assert [item["paragraph_id"] for item in paragraphs] == list(
        archive.INCIDENT_PAGE_PARAGRAPH_IDS
    )

    by_id = {item["paragraph_id"]: item for item in paragraphs}
    for paragraph_id in archive.INCIDENT_EMPTY_SLOT_IDS:
        slot = by_id[paragraph_id]
        assert set(slot) == EMPTY_SLOT_KEYS
        assert slot["mechanism_id"] == ""
        assert slot["required_detail_ids"] == []
        assert slot["optional_detail_ids"] == []
        assert slot["formula_obligation_ids"] == []
        assert slot["formula_package_ids"] == []
        assert slot["role"] == "step_sequence"
        assert (slot["witness_contract"] or {}).get("targets") == []

    # 16 段共用同一个 section 级 reader_goal；`set(slot) == EMPTY_SLOT_KEYS`
    # 已证明对象里不存在任何逐段作者 statement / intent 字段。
    assert len({item["reader_goal"] for item in paragraphs}) == 1

    # 失败段落与空槽不同：它带机制、可选 detail 与 witness 目标。
    failing = by_id["MA-S3:P1__f1"]
    assert failing["mechanism_id"] == "mech_sym:f6cf5bdfe2ae16f0"
    assert failing["optional_detail_ids"]
    assert (failing["witness_contract"] or {}).get("targets")


def test_writer_and_binder_responsibility_statements_differ() -> None:
    request = archive.read_json("attempt_0002_request")
    contract = request["input_payload"]["binding_contract"]

    assert contract["required_detail_ids"] == list(archive.INCIDENT_MISSING_DETAIL_TARGETS)
    assert contract["atom_binding"]["owner"] == "binder"
    assert "Do not treat atom witness declarations as completed binding" in (
        contract["atom_binding"]["instruction"]
    )
    # 同一个请求里，narrative witness targets 仍向 Writer 暴露 required atom 项，
    # 而 binding_contract 已声明 atom 由 Binder 负责——责任表述不一致（WP3 修复点）。
    failing = next(
        item
        for item in request["input_payload"]["narrative_plan"]["paragraphs"]
        if item["paragraph_id"] == "MA-S3:P1__f1"
    )
    targets = (failing["witness_contract"] or {}).get("targets") or []
    required_detail_targets = {
        target["target_id"]
        for target in targets
        if target.get("target_kind") == "detail" and target.get("required") is True
    }
    assert required_detail_targets == {
        f"detail:{target}" for target in archive.INCIDENT_MISSING_DETAIL_TARGETS
    }
    # 5 个 optional detail 也在同一表面出现，说明 targets 不只是必需项。
    all_detail_targets = {
        target["target_id"] for target in targets if target.get("target_kind") == "detail"
    }
    assert required_detail_targets < all_detail_targets
    assert any(
        target.get("target_kind") == "atom" and target.get("required") is True
        for target in targets
    )


# --------------------------------------------------------------------------- #
# 5. 合同里的 code_commit_sha 是目标仓库身份，不是引擎 HEAD
# --------------------------------------------------------------------------- #


def test_target_sha_is_not_engine_sha() -> None:
    identity = archive.read_json("run_identity")
    snapshot = archive.read_json("repo_snapshot")

    assert set(identity) == IDENTITY_KEYS
    assert not [key for key in IDENTITY_KEYS if "engine" in key]

    assert identity["code_commit_sha"] == snapshot["git_commit"] == archive.TARGET_REPO_COMMIT
    assert snapshot["project_root"] == archive.TARGET_REPO_ROOT
    assert snapshot["git_branch"] == "main"
    assert snapshot["git_dirty"] is True
    assert identity["repo_snapshot_id"] == snapshot["snapshot_id"]
    assert identity["project_tree_hash"] == snapshot["project_tree_hash"]


# --------------------------------------------------------------------------- #
# 6. Formalizer 空 manifest 与 Writer manifest 可以同时合法存在
# --------------------------------------------------------------------------- #


def test_formalizer_empty_and_writer_manifest_coexist() -> None:
    formalizer = archive.read_json("formalizer_workset_manifest")
    writer = archive.read_json("writer_workset_manifest")

    assert formalizer["schema_version"] == "2.0"
    assert formalizer["worksets"] == []
    assert formalizer["pages"] == []

    assert writer["schema_version"] == "2.0"
    assert len(writer["worksets"]) == 5
    assert len(writer["pages"]) == 20
    assert len({page["page_id"] for page in writer["pages"]}) == 20
    assert formalizer["archive_digest"] == writer["archive_digest"]

    incident_page = next(
        page for page in writer["pages"] if page["page_id"] == archive.INCIDENT_PAGE_ID
    )
    assert incident_page["page_kind"] == "join"
    assert incident_page["mechanism_id"] == "join:MA-S3"
    assert incident_page["token_estimate"] > 0
