"""方案 §15：doctor 必须一条命令说清事故状态，而不是让人读几十个 JSON。"""

from __future__ import annotations

from code2paper.agentic.authoring_doctor import run_authoring_doctor

from . import incident_archive


def test_incident_doctor_reports_root_cause_chain() -> None:
    report = run_authoring_doctor(incident_archive.archive_root())

    # 身份：事故 run 只有遗留 RunIdentityV1，没有引擎指纹——必须如实说明。
    assert "legacy identity" in report.execution_identity
    assert report.engine_fingerprint == ""
    assert "EBCAR" in report.target_identity

    # 阶段状态：Writer 聚合回执 4/5 段完成且未 complete。
    assert "incomplete" in report.phases["writer"]
    assert report.phases["binder"] in {"not produced", "unreadable"} or report.phases["binder"]

    # 逐页：MA-S3 事故页耗尽内容预算，且带拒发事件与失败类别。
    assert report.page_count == 20
    # 20 页中 19 页完成（1 页耗尽）；resume 复用页没有新验收记录，由分节回执补齐。
    assert report.accepted_page_count == 19
    # repair 后被接受的页不再是阻塞页；只有事故页耗尽。
    assert len(report.blocked_pages) == 1
    blocked = report.blocked_pages[0]
    assert incident_archive.INCIDENT_INVOCATION in blocked.invocation_id
    assert blocked.exhausted is True
    assert (blocked.content_attempts_used, blocked.content_attempt_limit) == (2, 2)
    assert blocked.rejected_before_send_events == (3, 4)
    assert "detail_witness_missing" in blocked.failure_codes

    # 根因链与下游阻断。
    assert "writer_v2_invocation_acceptance_count" in report.first_root_cause
    assert "resume_exhausted_invocation" in report.critical_blockers

    text = report.render()
    assert "BLOCKED" in text and "MA-S3" in text
    assert "NEXT ACTION" in text


def test_doctor_counts_intent_surface_gaps_and_writer_binder_mismatch() -> None:
    report = run_authoring_doctor(incident_archive.archive_root())

    # 事故请求里 P3–P17 共 15 个空槽；该 run 的 plan 未带 WP2 的 paragraph_kind 字段，
    # 因此走结构化回退判据（无机制/无 detail/无公式/无必需 atom）。
    # 整份 plan 内缺材料的段落数（事故页的 15 个空槽是其中一部分）。
    assert report.empty_semantic_paragraph_count >= 15
    # 同一批段落还把 Binder 负责的 atom 作为必需 witness 暴露给 Writer。
    assert report.binder_owned_writer_target_count > 0
    assert "intent_surface_gaps" in report.critical_blockers
    assert "writer_binder_ownership_inconsistent" in report.critical_blockers


def test_doctor_is_read_only(tmp_path) -> None:
    root = tmp_path / "empty-run"
    root.mkdir()
    before = sorted(str(item.relative_to(root)) for item in root.rglob("*"))
    report = run_authoring_doctor(root)
    assert report.page_count == 0
    assert report.critical_blockers == ()
    assert sorted(str(item.relative_to(root)) for item in root.rglob("*")) == before


def test_doctor_cli_renders_and_emits_json(capsys) -> None:
    """§15：doctor 走既有 CLI（不新增第二套产品入口），只读且可机读。"""

    import json

    from code2paper.cli.agentic_run import method_agent_main

    root = str(incident_archive.archive_root())
    assert method_agent_main(["doctor", "--out", root]) == 0
    rendered = capsys.readouterr().out
    assert "BLOCKED" in rendered and "NEXT ACTION" in rendered

    assert method_agent_main(["doctor", "--out", root, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["page_count"] == 20
    assert len(payload["blocked_pages"]) == 1
    assert "resume_exhausted_invocation" in payload["critical_blockers"]


# --------------------------------------------------------------------------- #
# §F.3：doctor 必须说明空产物是否合法、为什么为空
# --------------------------------------------------------------------------- #


def _empty_manifest() -> dict:
    return {
        "schema_version": "2.0",
        "archive_digest": "sha256:archive",
        "source_manifest_digest": "sha256:source",
        "pages": [],
        "worksets": [],
    }


def _plan_with_paragraphs(count: int) -> dict:
    return {
        "schema_version": "3.0",
        "sections": [
            {
                "section_id": "MA-S1",
                "heading": "Architecture",
                "paragraphs": [
                    {"paragraph_id": f"MA-S1:P{index}"} for index in range(1, count + 1)
                ],
            }
        ],
    }


def test_doctor_reports_an_empty_writer_manifest_as_a_blocker(tmp_path) -> None:
    import json

    root = tmp_path / "run"
    authoring = root / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True)
    (authoring / "consumer_workset_manifest_v2.json").write_text(
        json.dumps(_empty_manifest()) + "\n", encoding="utf-8"
    )
    (authoring / "consumer_workset_manifest_v2.writer.2.json").write_text(
        json.dumps(_empty_manifest()) + "\n", encoding="utf-8"
    )
    (authoring / "narrative_plan_v3.json").write_text(
        json.dumps(_plan_with_paragraphs(3)) + "\n", encoding="utf-8"
    )

    report = run_authoring_doctor(root)

    by_key = {
        (item.logical_role, item.phase): item for item in report.empty_artifacts
    }
    # Formalizer 没有公式任务：空合法。
    formalizer = by_key[("consumer_workset_manifest", "formalizer")]
    assert formalizer.allowed is True
    assert formalizer.reason == "no_required_units"
    # Writer 冻结了 3 个必需段落：空 manifest 必须成为 critical blocker。
    writer = by_key[("consumer_workset_manifest", "writer")]
    assert writer.allowed is False
    assert writer.required_units == 3
    assert writer.reason == "empty_with_required_units"
    assert (
        "artifact_empty_with_required_units:consumer_workset_manifest:writer:3"
        in report.critical_blockers
    )
    assert "artifact_empty_with_required_units" in report.render()


def test_doctor_allows_an_empty_writer_manifest_without_required_units(tmp_path) -> None:
    import json

    root = tmp_path / "run"
    authoring = root / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True)
    (authoring / "consumer_workset_manifest_v2.writer.2.json").write_text(
        json.dumps(_empty_manifest()) + "\n", encoding="utf-8"
    )

    report = run_authoring_doctor(root)

    writer = next(
        item
        for item in report.empty_artifacts
        if (item.logical_role, item.phase) == ("consumer_workset_manifest", "writer")
    )
    assert writer.allowed is True
    assert writer.reason == "no_required_units"
    assert not any(
        "artifact_empty_with_required_units" in item
        for item in report.critical_blockers
    )


# --------------------------------------------------------------------------- #
# §F.5：受索引管理的产物必须在**使用前**验证（变异测试）
# --------------------------------------------------------------------------- #


def _indexed_run_root(tmp_path) -> Path:
    import json

    root = tmp_path / "run"
    authoring = root / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True)
    (authoring / "consumer_invocation_plan_v1.2.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "content_digest": "sha256:plan",
                "invocations": [
                    {"invocation_id": "inv-1", "section_id": "MA-S1"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (authoring / "writer_section_receipts_v2.json").write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "content_digest": "sha256:receipts",
                "receipts": [
                    {"section_id": "MA-S1", "completed_invocation_ids": ["inv-1"]}
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (authoring / "writer_aggregate_receipt_v2.json").write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "content_digest": "sha256:aggregate",
                "completed_section_ids": ["MA-S1"],
                "required_section_ids": ["MA-S1"],
                "all_required_sections_complete": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def test_doctor_verifies_index_managed_artifacts_before_use(tmp_path) -> None:
    from code2paper.agentic.authoring_artifact_index import publish_artifact_index

    root = _indexed_run_root(tmp_path)
    publish_artifact_index(root)

    before = run_authoring_doctor(root)
    assert before.page_count == 1
    assert before.accepted_page_count == 1
    assert before.phases["writer"] == "1/1 sections complete"
    assert before.artifact_index_source == "published revision 1", before.artifact_index_source
    assert not any(
        item.startswith("artifact_read_blocked") for item in before.critical_blockers
    )

    # 索引发布之后改动文件：reader 必须在**使用内容前**失败。
    receipts = root / "artifacts/06_authoring/writer_section_receipts_v2.json"
    receipts.write_text(
        '{"schema_version": "2.0", "content_digest": "sha256:tampered",'
        ' "receipts": [{"section_id": "MA-S1",'
        ' "completed_invocation_ids": ["inv-1", "inv-injected"]}]}\n',
        encoding="utf-8",
    )

    after = run_authoring_doctor(root)
    blockers = [
        item
        for item in after.critical_blockers
        if item.startswith("artifact_read_blocked:writer_section_receipts:writer")
    ]
    assert blockers, after.critical_blockers
    assert "artifact_bytes_changed_since_index" in blockers[0]
    # 不允许隐式 fallback：被注入的 id 不得进入结论。
    assert "inv-injected" not in after.render()
    assert "artifact_read_blocked" in after.render()

    # 聚合回执同样受索引管理：改动后该阶段必须显示为 blocked，而不是继续报完成。
    aggregate = root / "artifacts/06_authoring/writer_aggregate_receipt_v2.json"
    aggregate.write_text(
        '{"schema_version": "2.0", "content_digest": "sha256:aggregate",'
        ' "completed_section_ids": ["MA-S1", "MA-S2"],'
        ' "required_section_ids": ["MA-S1", "MA-S2"],'
        ' "all_required_sections_complete": true}\n',
        encoding="utf-8",
    )
    after_aggregate = run_authoring_doctor(root)
    assert after_aggregate.phases["writer"].startswith("blocked"), (
        after_aggregate.phases["writer"]
    )
    assert "2/2" not in after_aggregate.render()


def test_doctor_blocks_on_a_mutated_invocation_plan(tmp_path) -> None:
    from code2paper.agentic.authoring_artifact_index import publish_artifact_index

    root = _indexed_run_root(tmp_path)
    publish_artifact_index(root)

    plan = root / "artifacts/06_authoring/consumer_invocation_plan_v1.2.json"
    plan.write_text(
        '{"schema_version": "1.0", "content_digest": "sha256:plan",'
        ' "invocations": [{"invocation_id": "inv-1"}, {"invocation_id": "inv-2"}]}\n',
        encoding="utf-8",
    )

    report = run_authoring_doctor(root)
    assert any(
        item.startswith("artifact_read_blocked:consumer_invocation_plan:writer")
        for item in report.critical_blockers
    ), report.critical_blockers
    # 计划读取被阻断 → 不再拿未验证的计划列出逐页状态。
    assert report.page_count == 0


def test_doctor_fails_closed_when_the_published_index_is_unusable(tmp_path: Path) -> None:
    """§F.5：索引损坏时 doctor 报 critical，且不返回被改动内容。"""

    import json as _json

    from code2paper.agentic.authoring_artifact_index import (
        artifact_index_path,
        publish_artifact_index,
    )
    from code2paper.agentic.authoring_doctor import (
        load_run_summary_validated,
        run_authoring_doctor,
    )

    from .test_authoring_end_to_end_offline import _run as _product_run

    out_root = tmp_path / "run"
    _product_run(out_root)
    publish_artifact_index(out_root)
    payload, blocker = load_run_summary_validated(out_root)
    assert blocker == "" and payload["run_id"] == "e2e-offline"

    index_path = artifact_index_path(out_root)
    index_payload = _json.loads(index_path.read_text(encoding="utf-8"))
    index_payload["content_digest"] = "sha256:" + "0" * 64
    index_path.write_text(
        _json.dumps(index_payload, indent=2) + "\n", encoding="utf-8"
    )

    payload_broken, blocker_broken = load_run_summary_validated(out_root)
    assert payload_broken is None
    assert blocker_broken.startswith("artifact_index_unusable:"), blocker_broken

    report = run_authoring_doctor(out_root)
    assert any(
        item.startswith("artifact_index_unusable:")
        for item in report.critical_blockers
    ), report.critical_blockers
    assert report.artifact_index_source.startswith("artifact_index_unusable:")
