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
