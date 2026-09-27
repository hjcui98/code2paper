"""审计 §4：I1–I10 不变量的可执行核对。

这不是新增第十一套门禁，而是把每个不变量**已有的 owner** 指出来并钉住其行为：
每条测试只断言"违反该不变量就会失败"的最小事实。审计 §4 的边界列在每条 docstring 里。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.regression_20260922.test_authoring_contract_closure import (
    _counting,
    _run_with_paths,
)
from tests.test_agentic_publication_method_writer_unified import _unified_artifacts


# --------------------------------------------------------------------------- #
# I1：Author intent 只能授权叙事与有界作者描述，不能凭空证明代码实现
# --------------------------------------------------------------------------- #


def test_i1_author_intent_never_authorizes_implementation_claims(
    tmp_path: Path, monkeypatch
) -> None:
    """Owner：intent compiler + candidate authority validation。

    产品级证据：只有作者说明的 story 编译出的段落不得带任何实现义务，其页也不得携带
    技术 atom（否则就是"用作者意图证明代码实现"）。
    """

    from code2paper.agentic.method_architect import NarrativePlanV3

    paths = _unified_artifacts(tmp_path)
    spine_path = tmp_path / "artifacts" / "author_story_spine_v1.json"
    spine_path.write_text(
        json.dumps(
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
    monkeypatch.setenv("CODE2PAPER_INTENT_NARRATIVE_PLAN", "v4")
    _result, outputs = _run_with_paths(
        tmp_path, _counting([]), dict(paths) | {"author_story_spine_v1": str(spine_path)}
    )

    plan = NarrativePlanV3.model_validate_json(
        Path(outputs["narrative_plan_v3"]).read_text(encoding="utf-8")
    )
    author_only = [
        paragraph
        for section in plan.sections
        for paragraph in section.paragraphs
        if not paragraph.required_detail_ids
    ]
    assert author_only, "作者-only 段落必须保留"
    paragraph = author_only[0]
    assert not (paragraph.witness_contract or {}).get("targets")

    manifest = json.loads(
        Path(outputs["consumer_workset_manifest_v2.writer.2"]).read_text(
            encoding="utf-8"
        )
    )
    for page in manifest["pages"]:
        payload = page.get("technical_payload") or {}
        if paragraph.paragraph_id not in (payload.get("paragraph_ids") or ()):
            continue
        assert not (payload.get("atoms") or ()), "作者段落不得携带实现 atom"
        assert not (payload.get("detail_ids") or ())
        assert page.get("page_kind") == "header"


# --------------------------------------------------------------------------- #
# I2：同一执行只存在一个 executable semantic plan；未知配置不得静默改主线
# --------------------------------------------------------------------------- #


def test_i2_unknown_plan_mode_is_refused_not_silently_switched() -> None:
    """Owner：authoring_run_config（入口配置与 planner selection 的唯一 owner）。"""

    from code2paper.agentic.authoring_run_config import normalize_narrative_plan_mode

    assert normalize_narrative_plan_mode("v4") == "v4"
    assert normalize_narrative_plan_mode("shadow") == "shadow"
    with pytest.raises(Exception) as excinfo:
        normalize_narrative_plan_mode("v9-experimental")
    assert "unknown_narrative_plan_mode" in str(excinfo.value)
    # 空值走显式默认（v3），而不是"随便挑一条主线"。
    assert normalize_narrative_plan_mode("") == "v3"


# --------------------------------------------------------------------------- #
# I3：每个 required 义务有唯一主归属；重分页不减少义务
# --------------------------------------------------------------------------- #


def test_i3_every_required_detail_has_exactly_one_owning_paragraph(
    tmp_path: Path,
) -> None:
    """Owner：narrative/page compiler（义务守恒 + 唯一主归属）。"""

    from code2paper.agentic.method_architect import NarrativePlanV3

    paths = _unified_artifacts(tmp_path)
    _result, outputs = _run_with_paths(tmp_path, _counting([]), paths)
    plan = NarrativePlanV3.model_validate_json(
        Path(outputs["narrative_plan_v3"]).read_text(encoding="utf-8")
    )

    owners: dict[str, list[str]] = {}
    for section in plan.sections:
        for paragraph in section.paragraphs:
            for detail_id in paragraph.required_detail_ids:
                owners.setdefault(str(detail_id), []).append(paragraph.paragraph_id)

    assert owners, "夹具必须产生至少一个 required detail"
    for detail_id, paragraph_ids in owners.items():
        assert len(paragraph_ids) == 1, (
            f"required detail {detail_id} 必须唯一主归属，实际 {paragraph_ids}"
        )

    # 页合同同样不得让某个 detail 同时成为两个段落的主义务。
    manifest = json.loads(
        Path(outputs["consumer_workset_manifest_v2.writer.2"]).read_text(
            encoding="utf-8"
        )
    )
    for page in manifest["pages"]:
        required = (page.get("technical_payload") or {}).get("required_detail_ids") or ()
        assert len(set(required)) == len(tuple(required)), page.get("page_id")


# --------------------------------------------------------------------------- #
# I4：技术闭包按内容守恒；共享 atom 可重复但不能重复计算成果
# --------------------------------------------------------------------------- #


def test_i4_page_atoms_are_a_subset_of_the_workset_closure(tmp_path: Path) -> None:
    """Owner：unified archive/workset（共享 atom 可跨页，但成果只计一次）。"""

    paths = _unified_artifacts(tmp_path)
    _result, outputs = _run_with_paths(tmp_path, _counting([]), paths)
    archive = json.loads(
        Path(outputs["unified_context_archive_v2"]).read_text(encoding="utf-8")
    )
    closure: set[str] = set()
    for key, value in archive.items():
        if not key.endswith("_atoms") or not isinstance(value, list):
            continue
        for atom in value:
            if isinstance(atom, dict) and atom.get("atom_id"):
                closure.add(str(atom["atom_id"]))
    assert closure, "archive 必须给出技术闭包"

    manifest = json.loads(
        Path(outputs["consumer_workset_manifest_v2.writer.2"]).read_text(
            encoding="utf-8"
        )
    )
    page_atom_counts: dict[str, int] = {}
    for page in manifest["pages"]:
        for atom_id in page.get("atom_ids") or ():
            page_atom_counts[str(atom_id)] = page_atom_counts.get(str(atom_id), 0) + 1
    assert page_atom_counts, "页必须携带 atom"
    assert set(page_atom_counts).issubset(closure), set(page_atom_counts) - closure

    # 共享 atom 允许跨页重复（页视图），但 workset 的义务集合是集合语义：
    # 重复引用不会让它"多做一份成果"。
    for workset in manifest.get("worksets") or ():
        required = [str(item) for item in workset.get("required_atom_ids") or ()]
        assert len(set(required)) == len(required), workset.get("workset_id")


# --------------------------------------------------------------------------- #
# I5：实际请求与冻结 page contract 一致
# --------------------------------------------------------------------------- #


def test_i5_actual_request_must_match_the_frozen_page_contract() -> None:
    """Owner：page_contract_recheck（request builder / pre-send 共用同一比较）。"""

    from code2paper.agentic.page_contract_recheck import (
        ACTUAL_PAGE_CONTRACT_MISMATCH,
        compare_actual_request_to_page_contract,
        page_contract_snapshot_from_payload,
    )

    payload = {
        "section_id": "MA-S1",
        "narrative_plan": {
            "page_id": "page:1",
            "page_paragraph_ids": ["MA-S1:P1", "MA-S1:P2"],
            "paragraphs": [
                {"paragraph_id": "MA-S1:P1"},
                {"paragraph_id": "MA-S1:P2"},
            ],
        },
        "binding_contract": {
            "allowed_detail_ids": ["detail:d1"],
            "allowed_formula_package_ids": [],
        },
        "config": {"max_output_tokens": 8192},
    }
    snapshot = page_contract_snapshot_from_payload(
        invocation_id="inv:1", payload=payload
    )
    assert compare_actual_request_to_page_contract(
        snapshot,
        invocation_id="inv:1",
        payload=payload,
        max_output_tokens=snapshot.max_output_tokens,
    ) == ()

    # 顺序/集合/权限/输出上限任一改变都必须被拒。
    mutated = json.loads(json.dumps(payload))
    mutated["narrative_plan"]["page_paragraph_ids"] = ["MA-S1:P2", "MA-S1:P1"]
    failures = compare_actual_request_to_page_contract(
        snapshot,
        invocation_id="inv:1",
        payload=mutated,
        max_output_tokens=snapshot.max_output_tokens,
    )
    assert failures and failures[0].startswith(ACTUAL_PAGE_CONTRACT_MISMATCH)

    # 输出上限：不得超过冻结值（比较的是**实际发送**的 max_output_tokens）。
    raised_cap = compare_actual_request_to_page_contract(
        snapshot,
        invocation_id="inv:1",
        payload=payload,
        max_output_tokens=16384,
    )
    assert any("output_cap" in failure for failure in raised_cap), raised_cap
    assert compare_actual_request_to_page_contract(
        snapshot,
        invocation_id="inv:1",
        payload=payload,
        max_output_tokens=8192,
    ) == ()


# --------------------------------------------------------------------------- #
# I6：Writer 接受 ≠ final-bound 接受
# --------------------------------------------------------------------------- #


def test_i6_writer_content_acceptance_is_not_final_bound_acceptance(
    tmp_path: Path,
) -> None:
    """Owner：Writer 两阶段验收 + Binder + publication。

    产品级证据：Writer 内容阶段接受（`validation_stage=writer_content`），但缺少
    final-bound 侧的确定性绑定/最终语义门时，`publication_ready=False` 且不产出
    任何已验证正文。
    """

    from tests.regression_20260922.test_authoring_contract_closure import (
        _contract_faithful_writer,
    )

    paths = _unified_artifacts(tmp_path)
    _result, outputs = _run_with_paths(tmp_path, _contract_faithful_writer, paths)

    acceptances = sorted(
        (tmp_path / "artifacts" / "06_authoring" / "invocations").rglob(
            "inv-*writer*/attempt-*.content-acceptance.json"
        )
    )
    assert acceptances, "必须有内容验收 sidecar"
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in acceptances]
    assert any(row.get("content_acceptance_status") == "accepted" for row in rows)

    # 冻结合同里 atom 义务是**存在**的（闭集包含它们），只是 writer_content 阶段
    # 不要求 Writer 枚举——这正是"两阶段"的含义。
    from code2paper.agentic.publication_transaction_contract import (
        assess_paragraph_transaction,
        closed_binding_target_keys,
    )

    excerpt = "class Encoder:\n    def read(self, configured_input):"
    plan_row = {
        "paragraph_id": "P1",
        "required_detail_ids": ("detail:mech_sym:encoder:1",),
        "witness_contract": {
            "schema_version": "1.0",
            "paragraph_id": "P1",
            "rhetorical_goal": "mechanism",
            "targets": [
                {
                    "target_kind": "detail",
                    "target_id": "detail:mech_sym:encoder:1",
                    "required": True,
                },
                {
                    "target_kind": "atom",
                    "target_id": "atom:detail:mech_sym:encoder:1:operation",
                    "required": True,
                    "exact_excerpts": [excerpt],
                },
            ],
        },
    }
    closed = closed_binding_target_keys(plan_row=plan_row)
    assert ("atom", "atom:detail:mech_sym:encoder:1:operation") in closed
    writer_only = {
        "paragraph_id": "P1",
        "paragraph_markdown": f"The encoder reads the input.\n\n```python\n{excerpt}\n```",
        "rendered_detail_ids": ["detail:mech_sym:encoder:1"],
        "witnesses": [
            {
                "witness_kind": "detail",
                "target_id": "detail:mech_sym:encoder:1",
                "exact_text": excerpt,
            }
        ],
    }
    assert assess_paragraph_transaction(
        writer_only, plan_row=plan_row, validation_stage="writer_content"
    ).valid is True

    writer_result = json.loads(
        Path(outputs["publication_writer_result_v1"]).read_text(encoding="utf-8")
    )
    assert writer_result["writer_transaction_status"] == "success"
    assert writer_result["publication_ready"] is False
    assert writer_result["verified_blocking_reasons"]
    verified = Path(outputs["repository_verified_method"])
    assert verified.read_text(encoding="utf-8").strip() == ""


# --------------------------------------------------------------------------- #
# I7：transport 未知结果不得当作未发送，也不得无界重调
# --------------------------------------------------------------------------- #


def test_i7_unknown_outcome_is_not_resent_and_retries_are_bounded() -> None:
    """Owner：invocation ledger 的 reducer + transport retry policy。"""

    from code2paper.agentic.transport_retry_policy import (
        load_transport_retry_policy,
        transport_failure_failure_code,
    )

    policy = load_transport_retry_policy()
    assert int(policy.unknown_outcome_retries) <= 0, "未知结果不得自动重试"
    assert bool(policy.counts_against_call_budget) is True
    assert int(policy.max_transport_retries) >= 0

    class _Timeout(Exception):
        pass

    code = transport_failure_failure_code(_Timeout("timed out"), sent=True)
    assert code.startswith("send_outcome_unknown"), code
    unsent = transport_failure_failure_code(_Timeout("timed out"), sent=False)
    assert not unsent.startswith("send_outcome_unknown"), unsent


# --------------------------------------------------------------------------- #
# I8：历史产物/回执不改写；重验生成独立结果
# --------------------------------------------------------------------------- #


def test_i8_revalidation_is_append_only_and_never_rewrites_history(
    tmp_path: Path,
) -> None:
    """Owner：writer_attempt_ledger 的 validation replay + artifact publication journal。"""

    from code2paper.agentic.writer_attempt_ledger import (
        publish_validation_replay,
    )

    invocation_id = "inv:writer:sec:page:abc"
    directory = tmp_path / "artifacts" / "06_authoring" / "invocations" / (
        "inv-writer-sec-page-abc"
    )
    directory.mkdir(parents=True)
    historical = directory / "attempt-0001.content-acceptance.json"
    historical.write_text('{"accepted": false, "attempt": 1}\n', encoding="utf-8")

    # 历史验收结论不可被"本地重放"冒充。
    with pytest.raises(ValueError, match="validation_replay_refuses_to_shadow"):
        publish_validation_replay(
            tmp_path,
            invocation_id,
            attempt=1,
            accepted=True,
            validator_bundle_digest="sha256:rules",
        )
    assert json.loads(historical.read_text(encoding="utf-8"))["accepted"] is False


# --------------------------------------------------------------------------- #
# I9：reader 消费冻结字节与明确 upstream，不猜最新文件
# --------------------------------------------------------------------------- #


def test_i9_explicit_reference_never_falls_back_to_the_newest_file(
    tmp_path: Path,
) -> None:
    """Owner：authoring_artifact_index（解析/读取的唯一 owner）。"""

    from code2paper.agentic.authoring_artifact_index import (
        ArtifactIndexError,
        build_artifact_index,
        resolve_artifact,
    )

    root = tmp_path / "run"
    authoring = root / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True)
    (authoring / "narrative_plan_v3.json").write_text(
        json.dumps({"schema_version": "3.0", "sections": [], "content_digest": "sha256:a"})
        + "\n",
        encoding="utf-8",
    )
    index = build_artifact_index(
        root, reference_digests={"narrative_plan:authoring": "sha256:" + "0" * 64}
    )
    with pytest.raises(ArtifactIndexError):
        resolve_artifact(index, "narrative_plan", "authoring", out_root=root)
    assert not index.active.get("narrative_plan:authoring")


# --------------------------------------------------------------------------- #
# I10：完成率/效率不能靠删任务、缩 scope 或隐藏失败提高
# --------------------------------------------------------------------------- #


def test_i10_fewer_tasks_or_empty_candidate_is_not_an_improvement() -> None:
    """Owner：quality comparison + admission gates。"""

    from code2paper.agentic.authoring_quality_comparison import (
        compare_authoring_quality_reports,
    )
    from code2paper.agentic.unified_context_compiler import (
        semantic_paragraph_limit_policy,
    )
    from tests.regression_20260917 import incident_archive
    from code2paper.agentic.authoring_quality_report import (
        build_authoring_quality_report,
    )

    report = build_authoring_quality_report(incident_archive.archive_root())

    def _dimension(source, dimension: str, **metrics):
        return source.model_copy(
            update={
                "dimensions": tuple(
                    item.model_copy(update={"metrics": {**item.metrics, **metrics}})
                    if item.dimension == dimension
                    else item
                    for item in source.dimensions
                )
            }
        )

    fewer_tasks = _dimension(report, "information_utilization", **{"formula.required": 0})
    comparison = compare_authoring_quality_reports(report, fewer_tasks)
    required = next(
        item for item in comparison.metric_deltas if item.metric == "formula.required"
    )
    assert required.direction == "unknown", "删任务不是改善"

    empty_candidate = _dimension(report, "efficiency", **{"total_tokens": 0})
    empty_candidate = _dimension(empty_candidate, "recovery_robustness", **{"pages_accepted": 0})
    empty = compare_authoring_quality_reports(report, empty_candidate)
    assert next(
        item for item in empty.metric_deltas if item.metric == "total_tokens"
    ).direction == "unknown", "空候选的零 token 不是效率提升"

    # 关闭段数上限只能是显式实验配置（准入据此阻断）。
    disabled = semantic_paragraph_limit_policy(
        {"CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE": "0"}
    )
    assert disabled["disabled"] is True
    assert disabled["experiment_acknowledged"] is False
