"""WP6：阶段化产物索引与合同 N/A 一致性（方案 §10）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.authoring_artifact_index import (
    ArtifactIndexError,
    build_artifact_index,
    resolve_artifact,
)
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
