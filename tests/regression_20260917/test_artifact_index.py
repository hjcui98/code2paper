"""WP6：阶段化产物索引与合同 N/A 一致性（方案 §10）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.authoring_artifact_index import (
    ArtifactIndexError,
    build_artifact_index,
    read_artifact_validated,
    resolve_artifact,
)
from code2paper.agentic.digest import digest_json
from code2paper.agentic.authoring_context_contract import (
    build_authoring_run_contract,
    validate_authoring_run_contract,
)

from . import incident_archive


def test_empty_formalizer_manifest_does_not_shadow_writer_manifest() -> None:
    """事故里空基础 manifest 与 Writer 真身并存：两者各自可解析。"""

    root = incident_archive.archive_root()
    index = build_artifact_index(root)

    formalizer = resolve_artifact(
        index, "consumer_workset_manifest", "formalizer", out_root=root
    )
    writer = resolve_artifact(
        index, "consumer_workset_manifest", "writer", out_root=root
    )
    assert formalizer.name == "consumer_workset_manifest_v2.json"
    assert writer.name == "consumer_workset_manifest_v2.writer.2.json"

    formalizer_entry = index.entry_for("consumer_workset_manifest", "formalizer")
    writer_entry = index.entry_for("consumer_workset_manifest", "writer")
    assert formalizer_entry is not None and formalizer_entry.status == "valid_empty"
    assert writer_entry is not None and writer_entry.status == "active"

    # 空 manifest 只对明确允许为空的调用方有效。
    with pytest.raises(ArtifactIndexError, match="artifact_empty_not_allowed"):
        resolve_artifact(
            index,
            "consumer_workset_manifest",
            "formalizer",
            out_root=root,
            allow_empty=False,
        )


def test_current_plan_generation_is_resolved_by_reference_digest() -> None:
    root = incident_archive.archive_root()
    v3_path = root / "artifacts/06_authoring/narrative_plan_v3.json"
    revision_path = root / "artifacts/06_authoring/narrative_plan_v3.revision.2.json"
    v3_digest = json.loads(v3_path.read_text(encoding="utf-8"))["content_digest"]
    revision_digest = json.loads(revision_path.read_text(encoding="utf-8"))["content_digest"]

    default_index = build_artifact_index(root)
    assert default_index.entry_for("narrative_plan", "authoring").path.endswith(
        "revision.2.json"
    )

    referenced = build_artifact_index(
        root, reference_digests={"narrative_plan:authoring": v3_digest}
    )
    chosen = referenced.entry_for("narrative_plan", "authoring")
    assert chosen is not None and chosen.path.endswith("narrative_plan_v3.json")
    superseded = [
        entry for entry in referenced.entries
        if entry.logical_role == "narrative_plan" and entry.path.endswith("revision.2.json")
    ]
    assert superseded and superseded[0].status == "superseded"

    # 摘要不符必须阻断，不允许"就近取值"。
    with pytest.raises(ArtifactIndexError, match="artifact_digest_mismatch"):
        resolve_artifact(
            referenced,
            "narrative_plan",
            "authoring",
            out_root=root,
            expected_digest=revision_digest,
        )


def test_unknown_role_phase_is_not_silently_resolved() -> None:
    root = incident_archive.archive_root()
    index = build_artifact_index(root)
    with pytest.raises(ArtifactIndexError, match="artifact_role_phase_unknown"):
        resolve_artifact(index, "consumer_workset_manifest", "nope", out_root=root)


def test_contract_builder_and_validator_agree_on_not_applicable(tmp_path) -> None:
    """§10.5：builder 认可的 N/A 不再被 validator 报成缺失。"""

    produced = tmp_path / "produced.json"
    produced.write_text("{}", encoding="utf-8")
    contract = build_authoring_run_contract(
        requested_mode="unified",
        effective_mode="unified",
        mode_source="argument",
        artifact_paths={"run_identity_v1": str(produced)},
        not_applicable_artifact_keys=("mechanism_formula_packages_v2",),
    )
    satisfied, missing = validate_authoring_run_contract(contract)
    assert "mechanism_formula_packages_v2" not in contract.expected_artifact_keys or (
        "mechanism_formula_packages_v2" not in missing
    )
    assert satisfied == (len(missing) == 0)

    # allow_blocked 只是展示开关，绝不改变 satisfied。
    blocked_satisfied, blocked_missing = validate_authoring_run_contract(
        contract, allow_blocked=True
    )
    assert blocked_satisfied == satisfied
    assert blocked_missing == missing


def test_publish_increments_revision_and_verifies_readback(tmp_path) -> None:
    """§10.2：先写不可变对象再原子发布 index revision，读回校验后才算成功。"""

    from code2paper.agentic.authoring_artifact_index import (
        artifact_index_path,
        publish_artifact_index,
    )

    root = tmp_path / "run"
    manifest = root / "artifacts/06_authoring/consumer_workset_manifest_v2.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"schema_version": "2.0", "worksets": [], "pages": []}),
        encoding="utf-8",
    )

    first_path, first = publish_artifact_index(root, execution_identity_digest="exec-x")
    assert first.index_revision == 1
    assert Path(first_path) == artifact_index_path(root)
    assert first.active["consumer_workset_manifest:formalizer"].endswith(
        "consumer_workset_manifest_v2.json"
    )

    second_path, second = publish_artifact_index(root, execution_identity_digest="exec-x")
    assert second_path == first_path
    assert second.index_revision == 2
    # 读回的索引必须与内存对象一致（半写对象不得成为 active）。
    on_disk = json.loads(Path(second_path).read_text(encoding="utf-8"))
    assert on_disk["content_digest"] == second.content_digest
    assert on_disk["index_revision"] == 2


def test_resolved_snapshot_freezes_phase_inputs_and_fails_closed(tmp_path) -> None:
    from code2paper.agentic.authoring_artifact_index import (
        ArtifactIndexError,
        build_resolved_authoring_snapshot,
        publish_artifact_index,
        write_resolved_authoring_snapshot,
    )

    root = tmp_path / "run"
    plan = root / "artifacts/06_authoring/narrative_plan_v3.revision.2.json"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        json.dumps({"schema_version": "3.0", "content_digest": "sha256:plan"}),
        encoding="utf-8",
    )
    _path, index = publish_artifact_index(root, execution_identity_digest="exec-y")

    snapshot = build_resolved_authoring_snapshot(
        index,
        out_root=root,
        phase="writer",
        required_roles=("narrative_plan:authoring",),
    )
    assert snapshot.phase == "writer"
    assert snapshot.resolved["narrative_plan:authoring"].endswith(
        "narrative_plan_v3.revision.2.json"
    )
    assert snapshot.digests["narrative_plan:authoring"].startswith("sha256:")
    assert snapshot.index_digest == index.content_digest

    written = write_resolved_authoring_snapshot(root, snapshot)
    assert Path(written).name == "resolved_authoring_snapshot_v1.writer.json"
    assert json.loads(Path(written).read_text(encoding="utf-8"))["content_digest"] == (
        snapshot.content_digest
    )

    # 该阶段缺少必需产物时 fail-closed，不静默跳过。
    with pytest.raises(ArtifactIndexError, match="artifact_missing|artifact_role_phase_unknown"):
        build_resolved_authoring_snapshot(
            index,
            out_root=root,
            phase="writer",
            required_roles=("binder_receipts:binder",),
        )


# --------------------------------------------------------------------------- #
# PR F / F.2：索引必须验证它声称冻结的字节（变异测试）
# --------------------------------------------------------------------------- #


def _synthetic_root(tmp_path: Path, *, plan_id: str = "plan:index-test") -> Path:
    """用真实 producer 模型生成产物（自带自洽的 content_digest）。"""

    from code2paper.agentic.method_architect import NarrativePlanV3

    root = tmp_path / "run"
    authoring = root / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True)
    plan = NarrativePlanV3(
        plan_id=plan_id,
        sections=(),
        narrative_units=(),
        context_set_digest="sha256:ctx",
    )
    (authoring / "narrative_plan_v3.json").write_text(
        plan.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return root


def _entry(index, role: str, needle: str):
    """按路径片段取条目（`entry_for` 只返回 active，非 active 状态要直接扫 entries）。"""

    return next(
        entry
        for entry in index.entries
        if entry.logical_role == role and entry.path.endswith(needle)
    )


def test_unparsable_artifact_is_invalid_and_never_active(tmp_path: Path) -> None:
    """审计 §F.2 反例：非法 JSON 不得获得 active 状态。"""

    root = _synthetic_root(tmp_path)
    (root / "artifacts/06_authoring/narrative_plan_v3.json").write_text(
        "{ not json", encoding="utf-8"
    )
    index = build_artifact_index(root)
    entry = _entry(index, "narrative_plan", "narrative_plan_v3.json")
    assert entry.status == "invalid"
    assert "narrative_plan:authoring" not in index.active or not index.active[
        "narrative_plan:authoring"
    ]
    with pytest.raises(ArtifactIndexError):
        resolve_artifact(index, "narrative_plan", "authoring", out_root=root)


def test_unsupported_schema_version_is_invalid(tmp_path: Path) -> None:
    root = _synthetic_root(tmp_path)
    (root / "artifacts/06_authoring/consumer_workset_manifest_v2.json").write_text(
        json.dumps({"schema_version": "9.9", "pages": [], "worksets": []}) + "\n",
        encoding="utf-8",
    )
    index = build_artifact_index(root)
    entry = _entry(index, "consumer_workset_manifest", "consumer_workset_manifest_v2.json")
    assert entry.status == "invalid"


def test_explicit_reference_with_zero_matches_does_not_fall_back(tmp_path: Path) -> None:
    """审计 §F.2 反例：指定了不存在的摘要时不得回退到最高代。"""

    root = _synthetic_root(tmp_path)
    authoring = root / "artifacts" / "06_authoring"
    revision_root = _synthetic_root(tmp_path / "rev", plan_id="plan:revision-2")
    (authoring / "narrative_plan_v3.revision.2.json").write_text(
        (revision_root / "artifacts/06_authoring/narrative_plan_v3.json").read_text(),
        encoding="utf-8",
    )

    # 默认解析：最高代。
    default_index = build_artifact_index(root)
    assert default_index.entry_for("narrative_plan", "authoring").path.endswith(
        "revision.2.json"
    )

    # 显式引用一个不存在的摘要：必须零命中 → 不可解析，而不是"回退选最高代"。
    referenced = build_artifact_index(
        root, reference_digests={"narrative_plan:authoring": "sha256:" + "0" * 64}
    )
    assert not referenced.active.get("narrative_plan:authoring")
    with pytest.raises(ArtifactIndexError):
        resolve_artifact(referenced, "narrative_plan", "authoring", out_root=root)


def test_mutating_the_active_file_after_indexing_is_detected(tmp_path: Path) -> None:
    """F.5 变异测试：索引发布后改动文件，reader 必须在使用内容前失败。"""

    from code2paper.agentic.authoring_artifact_index import read_artifact_validated

    root = _synthetic_root(tmp_path)
    index = build_artifact_index(root)
    first = read_artifact_validated(index, "narrative_plan", "authoring", out_root=root)
    assert first.semantic_digest_verification == "recomputed"
    assert first.payload["plan_id"] == "plan:index-test"

    # 改动内容但保留原来的 content_digest 声明（最隐蔽的篡改）。
    path = root / "artifacts/06_authoring/narrative_plan_v3.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["plan_id"] = "plan:tampered"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ArtifactIndexError, match="artifact_bytes_changed_since_index"):
        read_artifact_validated(index, "narrative_plan", "authoring", out_root=root)


def test_registered_roles_recompute_the_semantic_digest(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_artifact_index import read_artifact_validated

    root = _synthetic_root(tmp_path)
    index = build_artifact_index(root)
    result = read_artifact_validated(index, "narrative_plan", "authoring", out_root=root)
    assert result.semantic_digest_verification == "recomputed"

    # 未注册 producer 模型的 role 如实标为 declared_only，不假装已复算。
    authoring = root / "artifacts" / "06_authoring"
    (authoring / "writer_section_receipts_v2.json").write_text(
        json.dumps({"schema_version": "2.0", "content_digest": "sha256:declared"}) + "\n",
        encoding="utf-8",
    )
    index = build_artifact_index(root)
    other = read_artifact_validated(
        index, "writer_section_receipts", "writer", out_root=root
    )
    assert other.semantic_digest_verification == "declared_only"


# --------------------------------------------------------------------------- #
# PR F / F.4：阶段快照不可覆盖（不可变证据 + 原子指针）
# --------------------------------------------------------------------------- #


def _snapshot(root: Path, *, plan_body: str = "a"):
    """构造阶段快照：先真实发布索引，再按该索引冻结阶段输入。"""

    from code2paper.agentic.authoring_artifact_index import (
        build_resolved_authoring_snapshot,
        publish_artifact_index,
    )
    from code2paper.agentic.method_architect import NarrativePlanV3

    authoring = root / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True, exist_ok=True)
    plan = NarrativePlanV3(
        plan_id=f"plan:{plan_body}",
        sections=(),
        narrative_units=(),
        context_set_digest="sha256:ctx",
    )
    (authoring / "narrative_plan_v3.json").write_text(
        plan.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    _path, index = publish_artifact_index(root, execution_identity_digest="exec-y")
    return build_resolved_authoring_snapshot(
        index,
        out_root=root,
        phase="writer",
        required_roles=("narrative_plan:authoring",),
    )


def test_stage_snapshot_evidence_is_immutable_and_pointer_is_atomic(tmp_path: Path) -> None:
    """审计 §F.4 反例：第二次运行不得抹掉第一次的输入证据。"""

    from code2paper.agentic.authoring_artifact_index import (
        frozen_snapshot_evidence,
        resolved_snapshot_evidence_path,
        write_resolved_authoring_snapshot,
    )

    root = tmp_path / "run"
    first = _snapshot(root, plan_body="a")
    pointer = Path(write_resolved_authoring_snapshot(root, first))
    assert pointer.name == "resolved_authoring_snapshot_v1.writer.json"
    evidence_first = resolved_snapshot_evidence_path(root, first)
    assert evidence_first.is_file()
    first_bytes = evidence_first.read_bytes()

    # 同内容重复写入：幂等，证据字节不变。
    assert Path(write_resolved_authoring_snapshot(root, first)) == pointer
    assert evidence_first.read_bytes() == first_bytes

    # 第二次运行（输入变了）→ 新证据文件，旧证据**原样保留**，指针指向新证据。
    second = _snapshot(root, plan_body="b")
    write_resolved_authoring_snapshot(root, second)
    evidence_second = resolved_snapshot_evidence_path(root, second)
    assert evidence_second.is_file() and evidence_second != evidence_first
    assert evidence_first.read_bytes() == first_bytes, "历史证据不得被覆盖"

    frozen = frozen_snapshot_evidence(root, "writer")
    assert frozen.file_bytes_digest.startswith("sha256:")
    assert (
        frozen.payload["digests"]["narrative_plan:authoring"]
        == second.digests["narrative_plan:authoring"]
    )
    assert frozen.payload["index_revision"] == second.index_revision == 2


def test_stage_snapshot_evidence_change_is_detected(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_artifact_index import (
        ArtifactIndexError,
        frozen_snapshot_evidence,
        resolved_snapshot_evidence_path,
        write_resolved_authoring_snapshot,
    )

    root = tmp_path / "run"
    snapshot = _snapshot(root, plan_body="a")
    write_resolved_authoring_snapshot(root, snapshot)
    evidence = resolved_snapshot_evidence_path(root, snapshot)

    # 只改证据文件：指针与证据不再描述同一份快照，必须拒绝。
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["digests"] = {"narrative_plan:authoring": "sha256:tampered"}
    evidence.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(
        ArtifactIndexError,
        match="stage_snapshot_pointer_evidence_mismatch|stage_snapshot_evidence_changed",
    ):
        frozen_snapshot_evidence(root, "writer")

    # 指针与证据一起改成"互相自洽"的内容：身份一致，但声明的语义摘要重算不上。
    pointer = root / "artifacts/06_authoring/resolved_authoring_snapshot_v1.writer.json"
    shared = {
        "schema_version": "1.0",
        "phase": "writer",
        "execution_identity_digest": str(payload.get("execution_identity_digest") or ""),
        "index_revision": int(payload.get("index_revision") or 0),
        "index_digest": str(payload.get("index_digest") or ""),
        "resolved": {"narrative_plan:authoring": "artifacts/06_authoring/other.json"},
        "digests": dict(payload.get("digests") or {}),
        "content_digest": str(payload.get("content_digest") or ""),
    }
    evidence.write_text(json.dumps(shared, indent=2) + "\n", encoding="utf-8")
    (root / "artifacts/06_authoring/resolved_authoring_snapshot_v1.writer.json").write_text(
        json.dumps({**shared, "evidence_path": str(evidence)}, indent=2) + "\n",
        encoding="utf-8",
    )
    assert pointer.is_file()
    with pytest.raises(ArtifactIndexError, match="stage_snapshot_evidence_changed"):
        frozen_snapshot_evidence(root, "writer")


def test_legacy_snapshot_without_evidence_is_reported(tmp_path: Path) -> None:
    """旧格式（固定名、无证据副本）不得被当成"已冻结"。"""

    from code2paper.agentic.authoring_artifact_index import (
        ArtifactIndexError,
        frozen_snapshot_evidence,
    )

    root = tmp_path / "run"
    authoring = root / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True)
    (authoring / "resolved_authoring_snapshot_v1.writer.json").write_text(
        json.dumps({"schema_version": "1.0", "phase": "writer", "content_digest": "sha256:x"})
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ArtifactIndexError, match="stage_snapshot_evidence_missing"):
        frozen_snapshot_evidence(root, "writer")


# --------------------------------------------------------------------------- #
# PR F / F.3：空产物是否合法取决于该阶段冻结的 required units
# --------------------------------------------------------------------------- #


def _empty_manifest_payload(*, diagnostics: tuple = ()) -> dict:
    return {
        "schema_version": "2.0",
        "archive_digest": "sha256:archive",
        "source_manifest_digest": "sha256:source",
        "pages": [],
        "worksets": [],
        "projection_diagnostics": list(diagnostics),
    }


def test_empty_artifact_is_judged_by_phase_and_required_units() -> None:
    from code2paper.agentic.authoring_artifact_index import assess_empty_artifact

    # Formalizer 没有公式任务：空是合法的，并记录原因。
    formalizer = assess_empty_artifact(
        "consumer_workset_manifest", "formalizer", _empty_manifest_payload(), required_units=0
    )
    assert formalizer.allowed is True
    assert formalizer.empty is True
    assert formalizer.reason == "no_required_units"
    assert formalizer.policy == "allowed_when_no_required_units"

    # Writer 阶段冻结了 3 个必需单元：同样的空 payload 不再合法。
    writer = assess_empty_artifact(
        "consumer_workset_manifest", "writer", _empty_manifest_payload(), required_units=3
    )
    assert writer.allowed is False
    assert writer.reason == "empty_with_required_units"
    assert writer.failures == (
        "artifact_empty_with_required_units:consumer_workset_manifest:writer:3",
    )

    # 同一阶段但没有必需单元：空仍是合法的（不是所有 phase 共用 allow_empty）。
    writer_idle = assess_empty_artifact(
        "consumer_workset_manifest", "writer", _empty_manifest_payload(), required_units=0
    )
    assert writer_idle.allowed is True


def test_empty_artifact_records_why_it_is_empty() -> None:
    from code2paper.agentic.authoring_artifact_index import assess_empty_artifact

    payload = _empty_manifest_payload(
        diagnostics=(
            {"kind": "not_applicable", "task_ids": ["formula:ob-1", "formula:ob-2"]},
            {"kind": "other", "task_ids": ["ignored"]},
        )
    )
    payload["note"] = "no formula obligations in this run"

    disposition = assess_empty_artifact(
        "consumer_workset_manifest", "formalizer", payload, required_units=0
    )
    assert disposition.allowed is True
    assert disposition.declared_not_applicable_task_ids == (
        "formula:ob-1",
        "formula:ob-2",
    )


def test_reader_blocks_empty_artifacts_with_frozen_required_units(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_artifact_index import (
        ArtifactIndexError,
        build_artifact_index,
        read_artifact_validated,
    )

    root = tmp_path / "run"
    authoring = root / "artifacts/06_authoring"
    authoring.mkdir(parents=True)
    (authoring / "consumer_workset_manifest_v2.writer.2.json").write_text(
        json.dumps(_empty_manifest_payload()) + "\n", encoding="utf-8"
    )
    index = build_artifact_index(root)
    entry = _entry(index, "consumer_workset_manifest", "writer.2.json")
    assert entry.status == "valid_empty"

    # 没有冻结单元：读得出来，并如实标注为什么为空。
    read = read_artifact_validated(
        index, "consumer_workset_manifest", "writer", out_root=root, required_units=0
    )
    assert read.empty_disposition is not None
    assert read.empty_disposition.allowed is True

    # 冻结了必需单元：使用前 typed block，而不是拿空 manifest 继续写。
    with pytest.raises(
        ArtifactIndexError, match="artifact_empty_with_required_units"
    ):
        read_artifact_validated(
            index,
            "consumer_workset_manifest",
            "writer",
            out_root=root,
            required_units=2,
        )


# --------------------------------------------------------------------------- #
# K03：真实读取与恢复接线（一代产物按持久 active 指针读取，成员在同一次读取里复算）
# --------------------------------------------------------------------------- #


def _k03_member(value: str) -> bytes:
    return (json.dumps({"content_digest": f"sha256:{value}", "value": value}) + "\n").encode()


def _k03_generation(root: Path, *, generation: int, value: str):
    from code2paper.agentic.authoring_artifact_publication import (
        build_publication_manifest,
        stage_publication_members,
    )

    members = stage_publication_members(
        root,
        role="section_draft",
        phase="writer",
        members={"draft": _k03_member(value)},
        semantic_digests={"draft": f"sha256:{value}"},
        schema_versions={"draft": "1.0"},
    )
    manifest = build_publication_manifest(
        role="section_draft",
        phase="writer",
        generation=generation,
        members=members,
        export_path=f"artifacts/06_authoring/section_draft.g{generation}.json",
        read_set=("engine:sha256:engine",),
        producer="unit-test",
        upstream_refs=("intent:sha256:intent",),
    )
    export = root / manifest.export_path
    export.parent.mkdir(parents=True, exist_ok=True)
    export.write_bytes((root / members[0].path).read_bytes())
    return manifest, members


def _k03_publish(root: Path, *, generation: int, value: str, crash_at: str = ""):
    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
        switch_publication_active,
    )

    from code2paper.agentic.authoring_artifact_publication import (
        PublicationInterruptedError,
    )

    manifest, members = _k03_generation(root, generation=generation, value=value)
    try:
        commit_publication_generation(root, manifest=manifest, crash_at=crash_at)
        switch_publication_active(
            root,
            manifest=manifest,
            expected_active_manifest_digest=None
            if generation == 1
            else _k03_active_digest(root),
            crash_at=crash_at,
        )
    except PublicationInterruptedError:
        pass  # 注入的崩溃：写入已发生，进程"死亡"。
    return manifest, members


def _k03_active_digest(root: Path) -> str:
    from code2paper.agentic.authoring_artifact_publication import (
        load_active_publication_pointer,
    )

    return load_active_publication_pointer(root).active.get("section_draft:writer", "")


def test_k03_index_and_reader_follow_the_durable_active_generation(tmp_path: Path) -> None:
    root = tmp_path / "run"
    g1, _members = _k03_publish(root, generation=1, value="alpha")

    index = build_artifact_index(root)
    entry = index.entry_for("section_draft", "writer")
    assert entry is not None
    assert entry.discovery == "publication_generation"
    assert entry.status == "active"
    assert entry.publication_recovery == "switched"
    assert entry.publication_fence == 1
    assert entry.publication_members and entry.publication_members[0].endswith(".json")
    assert entry.publication_read_set == ("engine:sha256:engine",)
    assert entry.semantic_digest == g1.content_digest

    read = read_artifact_validated(
        index=index, role="section_draft", phase="writer", out_root=root
    )
    assert read.semantic_digest_verification == "generation_members_recomputed"
    assert read.members["draft"]["value"] == "alpha"
    assert read.member_digests["draft"].startswith("sha256:")
    assert read.status == "active"


def test_k03_committed_unswitched_g2_does_not_take_over_the_read(tmp_path: Path) -> None:
    """g2 已提交未切换：索引/读取仍必须是 g1（旧 active 不被半成品覆盖）。"""

    root = tmp_path / "run"
    g1, _members = _k03_publish(root, generation=1, value="alpha")
    g2, _members2 = _k03_publish(root, generation=2, value="beta", crash_at="after_registered")

    index = build_artifact_index(root)
    entries = {
        (item.generation): item
        for item in index.entries
        if item.logical_role == "section_draft" and item.phase == "writer"
    }
    assert entries[1].status == "active"
    assert entries[1].path.endswith(next(iter([p.name for p in [Path(entries[1].path)]])))
    assert entries[2].status == "superseded"
    assert entries[2].publication_recovery == "committed_unswitched"
    active_entry = index.entry_for("section_draft", "writer")
    assert active_entry is not None and active_entry.generation == 1

    read = read_artifact_validated(
        index=index, role="section_draft", phase="writer", out_root=root
    )
    assert read.members["draft"]["value"] == "alpha", "未切换的下一代不得被读到"

    # 运维完成切换后才轮到 g2（一次 CAS，不重发产物）。
    from code2paper.agentic.authoring_artifact_publication import (
        switch_publication_active,
    )

    switch_publication_active(
        root, manifest=g2, expected_active_manifest_digest=g1.content_digest
    )
    after = build_artifact_index(root)
    read_after = read_artifact_validated(
        index=after, role="section_draft", phase="writer", out_root=root
    )
    assert read_after.members["draft"]["value"] == "beta"
    assert after.entry_for("section_draft", "writer").generation == 2
    assert after.entry_for("section_draft", "writer").publication_fence == 2


def test_k03_member_drift_after_index_publish_is_refused_at_read(tmp_path: Path) -> None:
    root = tmp_path / "run"
    _g1, members = _k03_publish(root, generation=1, value="alpha")
    index = build_artifact_index(root)

    member_path = root / members[0].path
    original = member_path.read_bytes()
    member_path.write_bytes(_k03_member("tampered"))
    with pytest.raises(ArtifactIndexError, match="artifact_generation_invalid"):
        read_artifact_validated(
            index=index, role="section_draft", phase="writer", out_root=root
        )
    member_path.write_bytes(original)

    # 半写 manifest 同样在读取点具名拒绝。
    from code2paper.agentic.authoring_artifact_publication import (
        publication_generation_dir,
    )

    manifest_path = next(publication_generation_dir(root).glob("generation.*.g1.*.json"))
    payload = manifest_path.read_bytes()
    manifest_path.write_bytes(payload[: len(payload) // 2])
    # 半写 manifest 在读取点具名拒绝（字节摘要先于成员复核被发现）。
    with pytest.raises(
        ArtifactIndexError,
        match="artifact_(bytes_changed_since_index|generation_invalid|publication_authority_unreadable)",
    ):
        read_artifact_validated(
            index=index, role="section_draft", phase="writer", out_root=root
        )


def test_k03_legacy_registry_requires_the_named_reader(tmp_path: Path) -> None:
    """旧注册表：默认 fail-closed；显式只读开关才可见，且不迁移、不重封。"""

    from code2paper.agentic.authoring_artifact_registry import (
        LEGACY_REGISTRY_SCHEMA_VERSION,
        registry_pointer_path,
    )

    root = tmp_path / "run"
    _k03_publish(root, generation=1, value="alpha")
    pointer_path = registry_pointer_path(root)
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["schema_version"] = LEGACY_REGISTRY_SCHEMA_VERSION
    pointer["content_digest"] = digest_json(
        {key: value for key, value in pointer.items() if key != "content_digest"}
    )
    pointer_path.write_text(json.dumps(pointer, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    before = pointer_path.read_bytes()

    default_index = build_artifact_index(root)
    registry_entry = next(
        item
        for item in default_index.entries
        if item.logical_role == "authoring_artifact_registry"
    )
    assert registry_entry.status == "invalid"
    assert "legacy_requires_named_reader" in registry_entry.detail

    legacy_index = build_artifact_index(root, allow_legacy_registry=True)
    generation_entry = legacy_index.entry_for("section_draft", "writer")
    assert generation_entry is not None
    assert generation_entry.status == "active"
    assert pointer_path.read_bytes() == before, "只读读取不得重写旧注册表"


def test_k03_markdown_member_is_read_as_verified_text(tmp_path: Path) -> None:
    """JSON 与 Markdown 都按**同一次已验证字节**读取；媒体类型随成员冻结。"""

    from code2paper.agentic.authoring_artifact_publication import (
        build_publication_manifest,
        commit_publication_generation,
        stage_publication_members,
        switch_publication_active,
    )

    root = tmp_path / "run"
    markdown = "# 方法\n\n正文只有 Markdown。\n".encode("utf-8")
    members = stage_publication_members(
        root,
        role="section_draft",
        phase="writer",
        members={"notes": markdown},
        media_types={"notes": "text/markdown"},
        schema_versions={"notes": "1.0"},
    )
    manifest = build_publication_manifest(
        role="section_draft",
        phase="writer",
        generation=1,
        members=members,
        export_path="artifacts/06_authoring/section_draft.md",
        read_set=("engine:sha256:engine",),
        producer="unit-test",
    )
    export = root / manifest.export_path
    export.parent.mkdir(parents=True, exist_ok=True)
    export.write_bytes(markdown)
    commit_publication_generation(root, manifest=manifest)
    switch_publication_active(
        root, manifest=manifest, expected_active_manifest_digest=None
    )

    index = build_artifact_index(root)
    read = read_artifact_validated(
        index=index, role="section_draft", phase="writer", out_root=root
    )
    assert read.member_media == {"notes": "text/markdown"}
    assert read.members["notes"] == markdown.decode("utf-8")
    assert read.member_digests["notes"].startswith("sha256:")

    # Markdown 成员漂移同样在读取点具名拒绝（投影损坏不影响权威 active）。
    from code2paper.agentic.authoring_artifact_publication import (
        load_active_publication_pointer,
        verify_publication_generation,
    )

    member_path = root / members[0].path
    original = member_path.read_bytes()
    member_path.write_bytes(b"# tampered\n")
    with pytest.raises(ArtifactIndexError, match="artifact_generation_invalid"):
        read_artifact_validated(
            index=index, role="section_draft", phase="writer", out_root=root
        )
    assert load_active_publication_pointer(root).active["section_draft:writer"] == (
        manifest.content_digest
    )

    # 修投影（导出）不需要重提交：成员/ manifest 未变，修好后仍然只读同一权威版本。
    export.write_bytes(b"drifted projection\n")
    assert (
        f"publication_export_drift:{manifest.export_path}"
        in verify_publication_generation(root, manifest.content_digest)
    )
    member_path.write_bytes(markdown)  # 修成员（不是修投影）
    export.write_bytes(markdown)
    assert verify_publication_generation(root, manifest.content_digest) == ()
    from code2paper.agentic.authoring_artifact_publication import (
        build_publication_receipt,
    )

    assert build_publication_receipt(
        root, role="section_draft", phase="writer"
    ).manifest_digest == manifest.content_digest
    assert original  # 原成员字节在漂移前被记录过


def test_k03_read_refuses_role_mixing_and_missing_manifest_without_fallback(
    tmp_path: Path,
) -> None:
    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
        stage_publication_members,
        switch_publication_active,
    )

    root = tmp_path / "run"
    _g1, _members = _k03_publish(root, generation=1, value="alpha")
    index = build_artifact_index(root)

    # 显式摘要零命中：不回退到"反正有 active"。
    with pytest.raises(ArtifactIndexError):
        read_artifact_validated(
            index=index,
            role="section_draft",
            phase="writer",
            out_root=root,
            expected_digest="sha256:" + "f" * 64,
        )

    # 角色混代：成员自称 binder，manifest 说 writer → 提交就拒绝。
    foreign = stage_publication_members(
        root,
        role="section_draft",
        phase="binder",
        members={"draft": _k03_member("foreign")},
    )
    manifest, _m = _k03_generation(root, generation=2, value="mixed")
    mixed = manifest.model_copy(update={"members": (foreign[0],)})
    record = commit_publication_generation(root, manifest=mixed)
    assert record.state == "incomplete"
    assert any(
        "publication_member_role_mismatch:draft" in item for item in record.failures
    ), record.failures

    # manifest 缺失（被删）：读取点按索引 path 拒绝，不回退到别代。
    from code2paper.agentic.authoring_artifact_publication import (
        publication_generation_dir,
    )

    active_entry = index.entry_for("section_draft", "writer")
    manifest_path = root / active_entry.path
    payload = manifest_path.read_bytes()
    manifest_path.unlink()
    with pytest.raises(ArtifactIndexError):
        read_artifact_validated(
            index=index, role="section_draft", phase="writer", out_root=root
        )
    manifest_path.write_bytes(payload)

    # 下一代经 CAS 切换后才成为 active（旧 active 不被"已登记"本身替换）。
    g2, _members2 = _k03_publish(root, generation=2, value="beta")
    from code2paper.agentic.authoring_artifact_publication import (
        load_active_publication_pointer,
    )

    assert load_active_publication_pointer(root).active["section_draft:writer"] == (
        g2.content_digest
    )
    assert switch_publication_active is not None


def test_k03_registration_record_drift_is_refused(tmp_path: Path) -> None:
    """record 漂移：严格注册表读取即拒绝，索引条目 invalid，读取不回退。"""

    from code2paper.agentic.authoring_artifact_registry import registry_dir

    root = tmp_path / "run"
    _g1, _members = _k03_publish(root, generation=1, value="alpha")
    records = sorted(registry_dir(root).glob("registration.*.json"))
    assert records
    payload = json.loads(records[0].read_text(encoding="utf-8"))
    payload["producer"] = "attacker"  # 保留声明摘要 → 加载拒绝，不重新封印
    records[0].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    drifted = build_artifact_index(root)
    registry_entry = next(
        item
        for item in drifted.entries
        if item.logical_role == "authoring_artifact_registry"
    )
    assert registry_entry.status == "invalid"
    assert "digest_mismatch" in registry_entry.detail
    # 权威 active 指针不受影响（注册表损坏不改变发布权威）。
    from code2paper.agentic.authoring_artifact_publication import (
        load_active_publication_pointer,
    )

    assert load_active_publication_pointer(root).active["section_draft:writer"] == (
        _g1.content_digest
    )


def test_k03_reader_trusts_publication_when_registry_and_index_diverge(
    tmp_path: Path,
) -> None:
    """发布 active、注册表 active、派生索引三者不同时，reader 只认发布权威。"""

    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
        load_active_publication_pointer,
        publication_generation_dir,
    )
    from code2paper.agentic.authoring_artifact_registry import (
        activate_artifact_registration,
        load_artifact_registry,
        registry_dir,
    )

    root = tmp_path / "run"
    g1, _members = _k03_publish(root, generation=1, value="alpha")
    g2, _members2 = _k03_generation(root, generation=2, value="beta")
    g3, _members3 = _k03_generation(root, generation=3, value="gamma")
    commit_publication_generation(root, manifest=g2)
    commit_publication_generation(root, manifest=g3)

    records = {
        json.loads(path.read_text(encoding="utf-8"))["generation"]: json.loads(
            path.read_text(encoding="utf-8")
        )
        for path in registry_dir(root).glob("registration.*.json")
    }
    from code2paper.agentic.authoring_artifact_registry import ArtifactRegistrationV1

    activate_artifact_registration(
        root, ArtifactRegistrationV1.model_validate(records[2])
    )
    registry = load_artifact_registry(root)
    active_id = registry.active["section_draft:writer"]
    assert registry.by_id()[active_id].generation == 2
    assert load_active_publication_pointer(root).active["section_draft:writer"] == (
        g1.content_digest
    )

    g3_path = next(publication_generation_dir(root).glob("generation.*.g3.*.json"))
    index = build_artifact_index(root)
    divergent = index.model_copy(update={
        "active": {
            **index.active,
            "section_draft:writer": str(g3_path.relative_to(root)),
        }
    })
    assert divergent.active["section_draft:writer"] != index.entry_for(
        "section_draft", "writer"
    ).path
    assert registry.by_id()[active_id].semantic_digest == g2.content_digest

    read = read_artifact_validated(
        index=divergent, role="section_draft", phase="writer", out_root=root
    )
    assert read.members["draft"]["value"] == "alpha"
    assert read.semantic_digest == g1.content_digest
    assert load_active_publication_pointer(root).active["section_draft:writer"] == (
        g1.content_digest
    )


def test_k03_projection_repair_does_not_resubmit(tmp_path: Path) -> None:
    """只损坏导出投影：权威 active 不变；修好投影不产生新提交。"""

    from code2paper.agentic.authoring_artifact_publication import (
        build_publication_receipt,
        load_active_publication_pointer,
        publication_active_pointer_path,
        publication_generation_dir,
        verify_publication_generation,
    )

    root = tmp_path / "run"
    manifest, members = _k03_publish(root, generation=1, value="alpha")
    pointer_before = publication_active_pointer_path(root).read_bytes()
    fence_before = load_active_publication_pointer(root).fences["section_draft:writer"]
    manifests_before = {
        path.name: path.read_bytes()
        for path in publication_generation_dir(root).glob("generation.*.json")
    }
    export = root / manifest.export_path
    member_bytes = (root / members[0].path).read_bytes()
    export.write_bytes(b'{"content_digest": "sha256:other", "value": "other"}\n')
    assert (
        f"publication_export_drift:{manifest.export_path}"
        in verify_publication_generation(root, manifest.content_digest)
    )
    assert publication_active_pointer_path(root).read_bytes() == pointer_before

    export.write_bytes(member_bytes)
    assert verify_publication_generation(root, manifest.content_digest) == ()
    assert {
        path.name: path.read_bytes()
        for path in publication_generation_dir(root).glob("generation.*.json")
    } == manifests_before
    assert load_active_publication_pointer(root).fences["section_draft:writer"] == (
        fence_before
    )
    assert build_publication_receipt(
        root, role="section_draft", phase="writer"
    ).manifest_digest == manifest.content_digest


def test_k03_replaced_manifest_bytes_are_not_read_as_the_verified_generation(
    tmp_path: Path,
) -> None:
    """verifier 通过后、reader 再次读取前替换 manifest，不能把 g2 成员标成 g1 摘要。"""

    from code2paper.agentic.authoring_artifact_publication import (
        publication_generation_dir,
        verify_publication_generation,
    )
    import code2paper.agentic.authoring_artifact_registry as registry

    root = tmp_path / "run"
    g1, _members = _k03_publish(root, generation=1, value="authoritative-g1")
    g2, _members2 = _k03_generation(root, generation=2, value="unverified-g2")
    index = build_artifact_index(root)
    control = read_artifact_validated(
        index=index, role="section_draft", phase="writer", out_root=root
    )
    assert control.members["draft"]["value"] == "authoritative-g1"
    assert control.semantic_digest == g1.content_digest
    assert verify_publication_generation(root, g1.content_digest) == ()
    manifest_path = next(publication_generation_dir(root).glob("generation.*.g1.*.json"))
    original = registry.load_artifact_registry
    fired = {"value": False}

    def replace_after_verification(*args, **kwargs):
        loaded = original(*args, **kwargs)
        if not fired["value"]:
            fired["value"] = True
            manifest_path.write_text(g2.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return loaded

    registry.load_artifact_registry = replace_after_verification
    try:
        with pytest.raises(ArtifactIndexError, match="artifact_manifest_digest_mismatch"):
            read_artifact_validated(
                index=index, role="section_draft", phase="writer", out_root=root
            )
    finally:
        registry.load_artifact_registry = original
    assert fired["value"] is True
    assert registry.load_artifact_registry is original
    mismatch = verify_publication_generation(root, g1.content_digest)
    assert mismatch and mismatch[0].startswith("publication_manifest_digest_mismatch")
