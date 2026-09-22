"""S8：离线端到端 = **product admission / diagnostic smoke**（不是写作链证明）。

范围声明（审计 §G.1）：本文件使用 ``provider=NONE`` 且 ``write_method_text=False``，
覆盖产品入口、运行身份、summary、artifact index/registry、doctor 与"不伪造正文"这条边界；
它**不能**代替 §G.2 的 fake-provider 写作链验收——这里没有任何一次 Writer/Binder/Realizer
模型调用，也没有发布过 Method 正文。写作链结论只能来自 G.2/G.3 的测试。

不需要 live 授权：走产品入口的离线模式，因此可纳入常规回归。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.authoring_artifact_index import (
    build_artifact_index,
    publish_artifact_index,
    read_artifact_validated,
)
from code2paper.agentic.authoring_doctor import run_authoring_doctor
from code2paper.agentic.authoring_execution_identity import (
    RunOpenRejected,
    load_execution_identity,
)
from code2paper.agentic.autonomous_method_agent import run_autonomous_method_agent
from code2paper.llm.client import LLMConfig, LLMProvider

#: 本文件的证明范围（供测试报告单列）。
TEST_SCOPE = (
    "product admission/diagnostic smoke: provider=NONE, write_method_text=False; "
    "no writing-chain evidence"
)

FIXTURE_REPO = Path(__file__).resolve().parents[1] / "fixtures" / "research_loop_project"
FIXTURE_INTENT = Path(__file__).resolve().parents[1] / "fixtures" / "author_intent.yaml"


def _run(out_root: Path, *, mode: str = "new", run_id: str = "e2e-offline"):
    return run_autonomous_method_agent(
        repo_path=FIXTURE_REPO,
        author_intent_path=FIXTURE_INTENT if FIXTURE_INTENT.is_file() else None,
        out_root=out_root,
        llm_config=LLMConfig(provider=LLMProvider.NONE),
        write_method_text=False,
        run_id=run_id,
        max_research_turns=2,
        run_open_mode=mode,
    )


@pytest.fixture(scope="module")
def offline_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, object]:
    out_root = tmp_path_factory.mktemp("e2e-offline") / "out"
    result = _run(out_root)
    return out_root, result


def test_offline_product_run_writes_identity_and_summary(offline_run) -> None:
    out_root, result = offline_run
    assert out_root.joinpath("artifacts/research_product/run_summary.json").is_file()
    identity = load_execution_identity(out_root)
    assert identity is not None, "产品入口必须写出 AuthoringExecutionIdentityV2"
    assert identity.engine_commit_sha != "unknown"
    assert identity.target_repo_snapshot_digest not in {"", "unknown"}
    assert identity.intent_content_digest and identity.claims_digest
    summary = json.loads(
        out_root.joinpath("artifacts/research_product/run_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary.get("run_id")


def test_index_and_doctor_agree_on_a_real_run(offline_run) -> None:
    out_root, _result = offline_run
    index = build_artifact_index(out_root)
    assert index.entry_for("run_identity", "research") is not None
    execution_entry = index.entry_for("authoring_execution_identity", "research")
    assert execution_entry is not None and execution_entry.status == "active"

    path, published = publish_artifact_index(out_root)
    assert Path(path).is_file()
    assert published.index_revision == 1

    report = run_authoring_doctor(out_root)
    assert "AuthoringExecutionIdentityV2" in report.execution_identity
    assert report.engine_fingerprint
    # 引擎指纹可用时不得报该 critical 阻断。
    assert "engine_fingerprint_unavailable" not in report.critical_blockers
    assert report.next_action


def test_reopening_requires_explicit_mode(offline_run) -> None:
    """WP1 准入在真实 run 上生效：new 拒绝非空目录、auto 走身份校验恢复。"""

    out_root, _result = offline_run
    with pytest.raises(RunOpenRejected) as excinfo:
        _run(out_root, mode="new")
    assert excinfo.value.decision.code == "run_directory_not_empty"

    # 同一身份 + 相同输入 → auto 解析为 resume 并保持身份字节不变。
    identity_path = out_root / "artifacts/research_product/authoring_execution_identity_v2.json"
    before = identity_path.read_bytes()
    resumed = _run(out_root, mode="auto")
    assert resumed is not None
    assert identity_path.read_bytes() == before


def test_offline_run_keeps_fail_closed_invariants(offline_run) -> None:
    """离线 run 不得伪造 candidate/verified，也不得写出未接受的正文。"""

    out_root, _result = offline_run
    for name in (
        "artifacts/06_authoring/publication_candidate_method.md",
        "artifacts/06_authoring/repository_verified_method.md",
    ):
        candidate = out_root / name
        if candidate.is_file():
            assert candidate.read_text(encoding="utf-8").strip() == ""
    report = run_authoring_doctor(out_root)
    assert "resume_exhausted_invocation" not in report.critical_blockers


def test_product_run_registers_its_identity_artifact(offline_run) -> None:
    """§F.1 真实接线：产品入口发布身份产物时必须同时注册它。"""

    from code2paper.agentic.authoring_artifact_registry import (
        load_artifact_registry,
    )

    out_root, _result = offline_run
    registry = load_artifact_registry(out_root)
    registrations = registry.active_registrations()
    assert registrations, "产品运行必须留下 producer 注册记录"

    identity = next(
        item
        for item in registrations
        if item.logical_role == "authoring_execution_identity"
    )
    assert identity.phase == "research"
    assert identity.file_bytes_digest.startswith("sha256:")
    assert identity.semantic_digest
    assert identity.producer.endswith("create_or_validate_execution_identity")
    assert any(ref.startswith("engine:") for ref in identity.upstream_refs)
    assert any(ref.startswith("target:") for ref in identity.upstream_refs)

    # 索引把注册当作权威：条目来源是 producer_registration，且能通过验证读取。
    index = build_artifact_index(out_root)
    entry = next(
        item
        for item in index.entries
        if item.logical_role == "authoring_execution_identity"
        and item.discovery == "producer_registration"
    )
    assert entry.status == "active"
    assert entry.upstream_refs == identity.upstream_refs
    read = read_artifact_validated(
        index, "authoring_execution_identity", "research", out_root=out_root
    )
    assert read.payload["content_digest"] == identity.semantic_digest
    assert read.file_bytes_digest == identity.file_bytes_digest


def test_resume_does_not_rewrite_the_registration(offline_run) -> None:
    """resume/auto 走"校验既有身份"分支：不得产生第二条注册记录。"""

    from code2paper.agentic.authoring_artifact_registry import (
        load_artifact_registry,
    )

    out_root, _result = offline_run
    before = load_artifact_registry(out_root)
    _run(out_root, mode="auto")
    after = load_artifact_registry(out_root)
    # 身份产物走"校验既有身份"分支：不得产生第二条身份注册。
    assert (
        after.active["authoring_execution_identity:research"]
        == before.active["authoring_execution_identity:research"]
    )
    identity_registrations = lambda registry: [  # noqa: E731
        item for item in registry.registrations
        if item.key() == "authoring_execution_identity:research"
    ]
    assert len(identity_registrations(after)) == len(identity_registrations(before))
    # run summary 每次 finalize 都是新内容 → 新的不可变注册记录（指针前移是预期的）。
    assert after.active["run_summary:terminal"]


def test_offline_run_scope_is_admission_only(offline_run) -> None:
    """§G.1：这个 smoke 的证明范围必须能被断言，而不是只写在文档里。

    provider=NONE + write_method_text=False ⇒ 没有 Writer 阶段、没有已接受页、
    没有发布正文；写作链结论只能来自 fake-provider 全链测试。
    """

    out_root, result = offline_run
    report = run_authoring_doctor(out_root)

    # 没有任何逐页调用：Writer 阶段从未运行。
    assert report.page_count == 0
    assert report.accepted_page_count == 0
    assert report.phases.get("writer") in {"not produced", "blocked"}
    # 没有发布过的 Method 正文。
    assert not (
        out_root / "artifacts" / "06_authoring" / "repository_verified_method.md"
    ).is_file()
    # 范围声明可在测试报告里单列。
    assert TEST_SCOPE.startswith("product admission/diagnostic smoke")
    assert "no writing-chain evidence" in TEST_SCOPE


def test_run_summary_is_registered_and_read_after_verification(offline_run) -> None:
    """§F.1/§F.4/§F.5：summary 发布时注册，读取时验证字节（改动后必须失败）。"""

    from code2paper.agentic.authoring_artifact_index import (
        build_artifact_index,
        publish_artifact_index,
    )
    from code2paper.agentic.authoring_artifact_publication import (
        scan_publication_transactions,
    )
    from code2paper.agentic.authoring_artifact_registry import (
        load_artifact_registry,
    )
    from code2paper.agentic.authoring_doctor import load_run_summary_validated

    out_root, _result = offline_run

    registry = load_artifact_registry(out_root)
    keys = {item.key() for item in registry.active_registrations()}
    assert "run_summary:terminal" in keys, keys

    transactions = [
        item
        for item in scan_publication_transactions(out_root)
        if item.logical_role == "run_summary"
    ]
    assert transactions and transactions[0].state == "complete", transactions

    # 先让索引与当前字节一致（resume 会重写 summary），再验证读取成功。
    publish_artifact_index(out_root)
    payload, blocker = load_run_summary_validated(out_root)
    assert blocker == "", blocker
    assert payload["run_id"] == "e2e-offline"

    # 发布索引后改动 summary：reader 必须在使用前失败，不返回被改动内容。
    summary_path = out_root / "artifacts" / "research_product" / "run_summary.json"
    mutated = json.loads(summary_path.read_text(encoding="utf-8"))
    mutated["run_id"] = "mutated-run-id"
    summary_path.write_text(
        json.dumps(mutated, indent=2) + "\n", encoding="utf-8"
    )
    payload_after, blocker_after = load_run_summary_validated(out_root)
    assert payload_after is None
    assert "artifact_bytes_changed_since_index" in blocker_after, blocker_after
    assert build_artifact_index(out_root).entries
