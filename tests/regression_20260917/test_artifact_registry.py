"""PR F / §F.1：producer 发布时向索引注册真实身份。

审计反例：索引只能靠扫描器 + `_KNOWN_ARTIFACTS` 文件名穷举来猜"当前生产对象"——
新增一代必须再写一个后缀分支，注册信息（角色/phase/generation/schema/字节与语义摘要/
upstream refs）都不存在。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.authoring_artifact_index import (
    ArtifactIndexError,
    build_artifact_index,
    publish_artifact_index,
    read_artifact_validated,
    resolve_artifact,
)
from code2paper.agentic.authoring_artifact_registry import (
    ArtifactRegistryError,
    load_artifact_registry,
    register_authoring_artifact,
    registry_dir,
    registry_pointer_path,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _manifest(*, worksets: int = 1) -> dict:
    return {
        "schema_version": "2.0",
        "archive_digest": "sha256:archive",
        "source_manifest_digest": "sha256:source",
        "content_digest": "sha256:manifest",
        "pages": [{"page_id": "page:1"}],
        "worksets": [{"workset_id": f"ws:{index}"} for index in range(worksets)],
    }


def test_registering_a_published_artifact_records_its_identity(tmp_path: Path) -> None:
    root = tmp_path / "run"
    path = _write_json(root / "artifacts/06_authoring/mine.json", _manifest())

    registration = register_authoring_artifact(
        root,
        role="consumer_workset_manifest",
        phase="quarantine-probe",
        path=path,
        generation=1,
        producer="unit-test",
        upstream_refs=("engine:sha256:abc", "target:sha256:def"),
    )

    assert registration.path == "artifacts/06_authoring/mine.json"
    assert registration.file_bytes_digest.startswith("sha256:")
    assert registration.semantic_digest == "sha256:manifest"
    assert registration.artifact_schema_version == "2.0"
    assert registration.upstream_refs == ("engine:sha256:abc", "target:sha256:def")

    registry = load_artifact_registry(root)
    assert registry.active == {
        "consumer_workset_manifest:quarantine-probe": registration.registration_id
    }
    assert registry.active_registrations() == (registration,)
    assert registry_pointer_path(root).is_file()

    # 同**完整逻辑内容**重复注册：幂等，不新增记录、不改摘要（K01 后 upstream/producer
    # 也进入 registration_id，因此重复注册必须给出同一份来源身份）。
    again = register_authoring_artifact(
        root,
        role="consumer_workset_manifest",
        phase="quarantine-probe",
        path=path,
        generation=1,
        producer="unit-test",
        upstream_refs=("engine:sha256:abc", "target:sha256:def"),
    )
    assert again.registration_id == registration.registration_id
    assert len(load_artifact_registry(root).registrations) == 1

    # 丢掉 provenance 不能换取同一个 ID：那是另一个来源身份，各自有不可变记录。
    other_root = tmp_path / "run-other-source"
    other_path = _write_json(other_root / "artifacts/06_authoring/mine.json", _manifest())
    bare = register_authoring_artifact(
        other_root,
        role="consumer_workset_manifest",
        phase="quarantine-probe",
        path=other_path,
        generation=1,
        producer="unit-test",
    )
    assert bare.registration_id != registration.registration_id


def test_registered_new_generation_is_recognized_without_a_known_artifacts_row(
    tmp_path: Path,
) -> None:
    """§F.1 反例：新的 generation 不应靠再写一个后缀分支才能被识别。"""

    root = tmp_path / "run"
    # legacy 表里已知的一代（generation 2）。
    _write_json(
        root / "artifacts/06_authoring/consumer_workset_manifest_v2.writer.2.json",
        _manifest(worksets=1),
    )
    # 新的一代：文件名完全不在 _KNOWN_ARTIFACTS 里。
    novel = _write_json(
        root / "artifacts/06_authoring/consumer_workset_manifest_v2.writer.9.json",
        _manifest(worksets=3),
    )
    registration = register_authoring_artifact(
        root,
        role="consumer_workset_manifest",
        phase="writer",
        path=novel,
        generation=9,
        producer="unit-test",
    )

    index = build_artifact_index(root)
    entries = [
        entry
        for entry in index.entries
        if entry.logical_role == "consumer_workset_manifest"
        and entry.phase == "writer"
    ]
    registered = [
        entry for entry in entries if entry.discovery == "producer_registration"
    ]
    assert len(registered) == 1, entries
    assert registered[0].path.endswith("writer.9.json")
    assert registered[0].generation == 9
    assert registered[0].status == "active"
    assert index.active["consumer_workset_manifest:writer"].endswith("writer.9.json")
    assert resolve_artifact(
        index, "consumer_workset_manifest", "writer", out_root=root
    ).name == "consumer_workset_manifest_v2.writer.9.json"
    # 注册表里的 upstream refs 原样进入索引条目。
    assert registered[0].upstream_refs == registration.upstream_refs
    # 同一份内容不再以 legacy_scan 结论重复出现。
    assert not [
        entry
        for entry in entries
        if entry.discovery == "legacy_scan"
        and entry.path == registered[0].path
    ]


def test_registered_bytes_changing_is_detected_and_never_falls_back(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    known = _write_json(
        root / "artifacts/06_authoring/consumer_workset_manifest_v2.writer.2.json",
        _manifest(worksets=1),
    )
    novel = _write_json(
        root / "artifacts/06_authoring/consumer_workset_manifest_v2.writer.9.json",
        _manifest(worksets=3),
    )
    register_authoring_artifact(
        root,
        role="consumer_workset_manifest",
        phase="writer",
        path=novel,
        generation=9,
        producer="unit-test",
    )
    assert known.is_file()

    # 注册之后内容被改动：注册指向的内容不可用 → 该 key 显式不可解析，
    # 不允许静默回退到 legacy 扫描出的另一代。
    novel.write_text(json.dumps(_manifest(worksets=99)) + "\n", encoding="utf-8")
    index = build_artifact_index(root)
    entry = next(
        item
        for item in index.entries
        if item.discovery == "producer_registration"
        and item.logical_role == "consumer_workset_manifest"
    )
    assert entry.status == "invalid"
    assert "registry_bytes_changed" in entry.detail
    assert index.active["consumer_workset_manifest:writer"] == ""
    with pytest.raises(ArtifactIndexError):
        resolve_artifact(index, "consumer_workset_manifest", "writer", out_root=root)


def test_missing_registered_target_is_invalid(tmp_path: Path) -> None:
    root = tmp_path / "run"
    path = _write_json(root / "artifacts/06_authoring/gone.json", _manifest())
    register_authoring_artifact(
        root,
        role="consumer_workset_manifest",
        phase="writer",
        path=path,
        generation=5,
        producer="unit-test",
    )
    path.unlink()

    index = build_artifact_index(root)
    entry = next(
        item
        for item in index.entries
        if item.discovery == "producer_registration"
    )
    assert entry.status == "invalid"
    assert "registry target missing" in entry.detail


def test_corrupt_registry_pointer_is_reported_not_ignored(tmp_path: Path) -> None:
    root = tmp_path / "run"
    pointer = registry_pointer_path(root)
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text("{ not json", encoding="utf-8")

    with pytest.raises(ArtifactRegistryError):
        load_artifact_registry(root)

    index = build_artifact_index(root)
    entry = next(
        item
        for item in index.entries
        if item.logical_role == "authoring_artifact_registry"
    )
    assert entry.status == "invalid"
    assert "artifact_registry_unreadable" in entry.detail


def test_registration_rejects_paths_outside_the_run_root(tmp_path: Path) -> None:
    outside = _write_json(tmp_path / "outside.json", _manifest())
    with pytest.raises(ArtifactRegistryError, match="path_escape"):
        register_authoring_artifact(
            tmp_path / "run",
            role="consumer_workset_manifest",
            phase="writer",
            path=outside,
            generation=1,
        )


def test_legacy_scan_still_works_without_a_registry(tmp_path: Path) -> None:
    root = tmp_path / "run"
    _write_json(
        root / "artifacts/06_authoring/consumer_workset_manifest_v2.writer.2.json",
        _manifest(),
    )
    index = build_artifact_index(root)
    entry = index.entry_for("consumer_workset_manifest", "writer")
    assert entry is not None
    assert entry.discovery == "legacy_scan"
    assert index.active["consumer_workset_manifest:writer"].endswith("writer.2.json")


def test_validated_read_verifies_registered_artifact_bytes(tmp_path: Path) -> None:
    root = tmp_path / "run"
    path = _write_json(root / "artifacts/06_authoring/mine.json", _manifest())
    register_authoring_artifact(
        root,
        role="consumer_workset_manifest",
        phase="quarantine-probe",
        path=path,
        generation=1,
        producer="unit-test",
    )
    index_path, _published = publish_artifact_index(root)
    assert Path(index_path).is_file()

    read = read_artifact_validated(
        index=build_artifact_index(root),
        role="consumer_workset_manifest",
        phase="quarantine-probe",
        out_root=root,
    )
    assert read.payload["content_digest"] == "sha256:manifest"
    assert read.status == "active"


# --------------------------------------------------------------------------- #
# K01：创建封摘要与加载验摘要分离；加载核对磁盘不可变 record
# --------------------------------------------------------------------------- #


def _sealed(payload: dict) -> dict:
    """按注册表自己的规则重算封存摘要（测试夹具用同一算法，不构造非法形状）。"""

    from code2paper.agentic.digest import digest_json

    sealed = dict(payload)
    sealed["content_digest"] = digest_json(
        {key: value for key, value in sealed.items() if key != "content_digest"}
    )
    return sealed


def _pointer(root: Path) -> Path:
    return registry_pointer_path(root)


def _read_pointer(root: Path) -> dict:
    return json.loads(_pointer(root).read_text(encoding="utf-8"))


def _write_pointer(root: Path, payload: dict) -> None:
    _pointer(root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _register_once(root: Path, *, producer: str = "unit-test") -> object:
    path = _write_json(root / "artifacts/06_authoring/mine.json", _manifest())
    return register_authoring_artifact(
        root,
        role="consumer_workset_manifest",
        phase="writer",
        path=path,
        generation=1,
        producer=producer,
        upstream_refs=("engine:sha256:abc",),
    )


def test_k01_repeat_registration_is_idempotent_without_a_new_generation(
    tmp_path: Path,
) -> None:
    """合法重复：同一次提交不得因为观察时间/自动 generation 变成新产物。"""

    root = tmp_path / "run"
    first = _register_once(root)
    records = sorted(registry_dir(root).glob("registration.*.json"))
    assert len(records) == 1
    before = records[0].read_bytes()

    second = register_authoring_artifact(
        root,
        role="consumer_workset_manifest",
        phase="writer",
        path=root / "artifacts/06_authoring/mine.json",
        producer="unit-test",
        upstream_refs=("engine:sha256:abc",),
    )
    assert second.registration_id == first.registration_id
    assert second.generation == first.generation
    registry = load_artifact_registry(root)
    assert len(registry.registrations) == 1
    assert sorted(registry_dir(root).glob("registration.*.json"))[0].read_bytes() == before


def test_k01_tampered_producer_or_upstream_with_kept_digest_is_rejected(
    tmp_path: Path,
) -> None:
    """篡改 upstream/producer 而保留声明摘要 → 加载拒绝，且不重新封印。"""

    root = tmp_path / "run"
    registration = _register_once(root)
    pointer = _read_pointer(root)

    # 只改注册行的 producer，保留原声明摘要。
    row = next(
        item for item in pointer["registrations"]
        if item["registration_id"] == registration.registration_id
    )
    row["producer"] = "attacker"
    _write_pointer(root, pointer)
    with pytest.raises(ArtifactRegistryError, match="digest_mismatch"):
        load_artifact_registry(root)

    # 只改 upstream_refs 的磁盘 record，保留原声明摘要 → 同样拒绝。
    _write_pointer(root, _read_pointer(root) | {"registrations": [
        {**item, "producer": registration.producer} for item in pointer["registrations"]
    ]})
    record = sorted(registry_dir(root).glob("registration.*.json"))[0]
    record_payload = json.loads(record.read_text(encoding="utf-8"))
    record_payload["upstream_refs"] = ["engine:sha256:forged"]
    record.write_text(json.dumps(record_payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ArtifactRegistryError, match="record_digest_mismatch"):
        load_artifact_registry(root)


def test_k01_deleted_immutable_record_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "run"
    _register_once(root)
    for record in registry_dir(root).glob("registration.*.json"):
        record.unlink()
    with pytest.raises(ArtifactRegistryError, match="record_missing"):
        load_artifact_registry(root)


def test_k01_replaced_pointer_is_rejected(tmp_path: Path) -> None:
    """指针替换：active 悬空 / 指向没有不可变 record 的注册 → 拒绝。"""

    root = tmp_path / "run"
    registration = _register_once(root)
    pointer = _read_pointer(root)

    dangling = dict(pointer)
    dangling["active"] = {"consumer_workset_manifest:writer": "reg:not-a-record"}
    _write_pointer(root, _sealed(dangling))
    with pytest.raises(ArtifactRegistryError, match="active_dangling"):
        load_artifact_registry(root)

    forged = dict(pointer)
    forged["registrations"] = [
        *pointer["registrations"],
        _sealed({
            **{key: value for key, value in pointer["registrations"][0].items()
               if key != "content_digest"},
            "registration_id": "reg:forged",
            "path": "artifacts/06_authoring/forged.json",
        }),
    ]
    _write_pointer(root, _sealed(forged))
    with pytest.raises(ArtifactRegistryError, match="record_missing"):
        load_artifact_registry(root)

    # 原指针仍然可读（替换失败不污染已有记录）。
    _write_pointer(root, pointer)
    assert load_artifact_registry(root).active_registrations() == (registration,)


def test_k01_same_registration_id_with_a_different_source_is_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    registration = _register_once(root)
    pointer = _read_pointer(root)
    row = pointer["registrations"][0]
    forged_row = _sealed({**row, "producer": "attacker"})
    # 伪造行把 registration_id 钉回原 ID（摘要自洽也不例外）。
    forged_row["registration_id"] = registration.registration_id
    forged_row = _sealed(forged_row)
    # 给伪造行补一条磁盘 record，绕过 record_missing，只留"同 ID 不同来源"。
    record_dir = registry_dir(root)
    (record_dir / (
        f"registration.{forged_row['logical_role']}.{forged_row['phase']}."
        f"g{forged_row['generation']}."
        f"{forged_row['content_digest'].removeprefix('sha256:')[:16]}.json"
    )).write_text(json.dumps(forged_row, indent=2) + "\n", encoding="utf-8")

    _write_pointer(root, _sealed({**pointer, "registrations": [row, forged_row]}))
    with pytest.raises(ArtifactRegistryError, match="id_conflict"):
        load_artifact_registry(root)


def test_k01_legacy_registry_is_read_only_and_named(tmp_path: Path) -> None:
    """旧格式只能由具名只读 reader 打开：严格 reader 明确拒绝，且不原地迁移。"""

    from code2paper.agentic.authoring_artifact_registry import (
        LEGACY_REGISTRY_SCHEMA_VERSION,
        load_legacy_artifact_registry,
    )

    root = tmp_path / "run"
    registration = _register_once(root)
    pointer = _read_pointer(root)
    legacy = _sealed({**pointer, "schema_version": LEGACY_REGISTRY_SCHEMA_VERSION})
    _write_pointer(root, legacy)
    before = _pointer(root).read_bytes()

    with pytest.raises(ArtifactRegistryError, match="legacy_requires_named_reader"):
        load_artifact_registry(root)

    loaded = load_legacy_artifact_registry(root)
    assert loaded.schema_version == LEGACY_REGISTRY_SCHEMA_VERSION
    assert loaded.active_registrations() == (registration,)
    # 只读：读取不重写、不迁移、不重封。
    assert _pointer(root).read_bytes() == before
    # 反向：新格式不得由 legacy reader 冒充读取（反之亦然）。
    modern_root = tmp_path / "run-modern"
    _register_once(modern_root)
    with pytest.raises(ArtifactRegistryError, match="not_legacy"):
        load_legacy_artifact_registry(modern_root)


def test_k01_registry_is_a_versioned_validator_source(tmp_path: Path) -> None:
    """注册表裁决逻辑进入 validator 来源清单；来源缺失具名拒绝。"""

    from code2paper.agentic.authoring_execution_identity import (
        VALIDATOR_BUNDLE_SOURCES,
        capture_validator_bundle_snapshot,
    )

    assert "src/code2paper/agentic/authoring_artifact_registry.py" in (
        VALIDATOR_BUNDLE_SOURCES
    )
    snapshot = capture_validator_bundle_snapshot()
    assert snapshot.failure_code == ""
    sources = dict(snapshot.entries)
    assert "src/code2paper/agentic/authoring_artifact_registry.py" in sources
    assert sources["src/code2paper/agentic/authoring_artifact_registry.py"].startswith(
        "sha256:"
    )


_FROZEN_REGISTRY_COMMIT = "0918ee76d079b9392ec03400c0c4c9fdff5bc784"
_FROZEN_REGISTRY_PATHS = (
    "src/code2paper/agentic/authoring_artifact_registry.py",
    "src/code2paper/agentic/digest.py",
    "src/code2paper/agentic/tool_runtime.py",
)


def test_k01_frozen_0918_owner_bytes_stay_read_only(tmp_path: Path) -> None:
    """真实 1.0 字节由冻结 owner 在隔离子进程生成，不是给新指针改版本号。"""

    import hashlib
    import os
    import subprocess
    import sys

    from code2paper.agentic.authoring_artifact_registry import (
        LEGACY_REGISTRY_SCHEMA_VERSION,
        load_legacy_artifact_registry,
        registry_dir,
    )

    repo = Path(__file__).resolve().parents[2]
    vendor = tmp_path / "frozen-owner"
    identities: dict[str, dict[str, str]] = {}
    for relative in _FROZEN_REGISTRY_PATHS:
        target = vendor / "code2paper" / "agentic" / Path(relative).name
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = subprocess.check_output(
            ["git", "show", f"{_FROZEN_REGISTRY_COMMIT}:{relative}"],
            cwd=repo,
        )
        target.write_bytes(payload)
        blob = subprocess.check_output(
            ["git", "rev-parse", f"{_FROZEN_REGISTRY_COMMIT}:{relative}"],
            cwd=repo,
            text=True,
        ).strip()
        identities[relative] = {
            "blob": blob,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        assert identities[relative]["sha256"] == hashlib.sha256(
            target.read_bytes()
        ).hexdigest()
    (vendor / "code2paper" / "__init__.py").write_text("", encoding="utf-8")
    (vendor / "code2paper" / "agentic" / "__init__.py").write_text("", encoding="utf-8")
    assert identities["src/code2paper/agentic/authoring_artifact_registry.py"]["blob"]
    assert "REGISTRY_SCHEMA_VERSION = \"1.0\"" in (
        vendor / "code2paper" / "agentic" / "authoring_artifact_registry.py"
    ).read_text(encoding="utf-8")

    out = tmp_path / "legacy-run"
    script = """
import json, os, sys
sys.path = [item for item in sys.path if not item.endswith("/src") and "Code2Paper copy/src" not in item]
sys.path.insert(0, os.environ["VENDOR"])
from pathlib import Path
root = Path(os.environ["OUT"])
artifact = root / "artifacts" / "sample.json"
artifact.parent.mkdir(parents=True, exist_ok=True)
artifact.write_text(
    json.dumps({"schema_version": "1.0", "content_digest": "sha256:frozen", "value": "frozen-owner"}) + "\\n",
    encoding="utf-8",
)
import code2paper.agentic.authoring_artifact_registry as frozen_registry
from code2paper.agentic.authoring_artifact_registry import (
    REGISTRY_SCHEMA_VERSION,
    register_authoring_artifact,
)
registration = register_authoring_artifact(
    root,
    role="section_draft",
    phase="writer",
    path=artifact,
    producer="frozen-0918",
    upstream_refs=("up:frozen",),
)
print(json.dumps({
    "module": frozen_registry.__file__,
    "schema_version": REGISTRY_SCHEMA_VERSION,
    "registration_id": registration.registration_id,
    "producer": registration.producer,
    "content_digest": registration.content_digest,
}))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(vendor)
    env["OUT"] = str(out)
    env["VENDOR"] = str(vendor)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    produced = json.loads(completed.stdout)
    assert produced["schema_version"] == "1.0"
    assert produced["producer"] == "frozen-0918"

    def _snapshot(path: Path) -> dict[str, bytes]:
        return {
            item.relative_to(path).as_posix(): item.read_bytes()
            for item in sorted(path.rglob("*"))
            if item.is_file()
        }

    before = _snapshot(registry_dir(out))
    assert before
    with pytest.raises(ArtifactRegistryError, match="legacy_requires_named_reader"):
        load_artifact_registry(out)
    loaded = load_legacy_artifact_registry(out)
    after = _snapshot(registry_dir(out))
    assert after == before
    assert loaded.schema_version == LEGACY_REGISTRY_SCHEMA_VERSION
    assert loaded.active_registrations()[0].registration_id == produced["registration_id"]
    assert loaded.active_registrations()[0].producer == "frozen-0918"
    assert loaded.active_registrations()[0].upstream_refs == ("up:frozen",)
    assert _snapshot(registry_dir(out)) == before

    modern = tmp_path / "corrupt-modern"
    _register_once(modern, producer="current")
    pointer = _pointer(modern)
    raw = json.loads(pointer.read_text(encoding="utf-8"))
    raw["content_digest"] = "sha256:" + "ab" * 32
    pointer.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    corrupt_before = pointer.read_bytes()
    with pytest.raises(ArtifactRegistryError, match="digest_mismatch"):
        load_artifact_registry(modern, allow_legacy=True)
    with pytest.raises(ArtifactRegistryError, match="not_legacy"):
        load_legacy_artifact_registry(modern)
    assert pointer.read_bytes() == corrupt_before
