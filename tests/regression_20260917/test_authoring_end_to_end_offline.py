"""S8：离线端到端（方案 §12/§13）——产品路径 + 身份/索引/doctor 全链一致。

不需要 live 授权：走产品入口的离线模式（provider=NONE），因此可纳入常规回归。
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
    assert after.active == before.active
    assert len(after.registrations) == len(before.registrations)
