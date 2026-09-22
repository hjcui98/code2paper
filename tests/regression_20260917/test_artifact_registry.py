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

    # 同内容重复注册：幂等，不新增记录、不改摘要。
    again = register_authoring_artifact(
        root,
        role="consumer_workset_manifest",
        phase="quarantine-probe",
        path=path,
        generation=1,
        producer="unit-test",
    )
    assert again.registration_id == registration.registration_id
    assert len(load_artifact_registry(root).registrations) == 1


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
