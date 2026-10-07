"""K02：不可变多成员发布与 CAS/fence 的真实发布回归。

交付终点要求：**先有完整 g1，再让 g2 在每个写点崩溃**，之后只能读到完整 g1 或 g2；
旧 fence、并发 CAS、已 commit 回包丢失、重复激活均安全；成员与来源不能被后代覆盖。
"""

from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path

import pytest

from code2paper.agentic.digest import digest_json


def _member_payload(value: str) -> bytes:
    return (json.dumps({"content_digest": f"sha256:{value}", "value": value}) + "\n").encode(
        "utf-8"
    )


def _generation(
    root: Path,
    *,
    generation: int,
    value: str,
    export: bool = False,
    media_types: dict[str, str] | None = None,
    members: dict[str, bytes] | None = None,
):
    """真实地 stage 成员并构建 manifest（内容寻址 + 封摘要 + 媒体类型）。"""

    from code2paper.agentic.authoring_artifact_publication import (
        build_publication_manifest,
        stage_publication_members,
    )

    payloads = members if members is not None else {"draft": _member_payload(value)}
    semantic_digests: dict[str, str] = {}
    for key, payload in payloads.items():
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            parsed = None
        declared = ""
        if isinstance(parsed, dict) and isinstance(parsed.get("content_digest"), str):
            declared = str(parsed["content_digest"])
        semantic_digests[key] = declared
    staged = stage_publication_members(
        root,
        role="section_draft",
        phase="writer",
        members=payloads,
        semantic_digests=semantic_digests,
        schema_versions={key: "1.0" for key in payloads},
        media_types=media_types or {},
    )
    manifest = build_publication_manifest(
        role="section_draft",
        phase="writer",
        generation=generation,
        members=staged,
        export_path=f"artifacts/06_authoring/section_draft.g{generation}.json" if export else "",
        read_set=("engine:sha256:engine",),
        producer="unit-test",
        upstream_refs=("intent:sha256:intent",),
    )
    return manifest, staged


def _write_export(root: Path, manifest) -> None:
    if not manifest.export_path:
        return
    path = root / manifest.export_path
    path.parent.mkdir(parents=True, exist_ok=True)
    member = manifest.members[0]
    path.write_bytes((root / member.path).read_bytes())


def _publish_g1(root: Path, *, value: str = "g1"):
    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
        switch_publication_active,
    )

    manifest, _members = _generation(root, generation=1, value=value, export=True)
    _write_export(root, manifest)
    commit_publication_generation(root, manifest=manifest)
    switch_publication_active(
        root, manifest=manifest, expected_active_manifest_digest=None
    )
    return manifest




def test_k02_generation_is_immutable_members_plus_manifest_and_cas_active(
    tmp_path: Path,
) -> None:
    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
        load_active_publication_pointer,
        switch_publication_active,
        verify_publication_generation,
    )

    root = tmp_path / "run"
    manifest, members = _generation(root, generation=1, value="alpha", export=True)
    _write_export(root, manifest)

    # 固定路径导出只是投影：权威成员在内容寻址存储里。
    assert (root / members[0].path).is_file()
    assert manifest.export_path and (root / manifest.export_path).is_file()

    record = commit_publication_generation(root, manifest=manifest)
    assert record.state == "registered", record.state
    assert verify_publication_generation(root, manifest.content_digest) == ()

    # 未切换前 active 为空（"已提交未切换"）。
    assert load_active_publication_pointer(root).active == {}
    pointer = switch_publication_active(
        root, manifest=manifest, expected_active_manifest_digest=None
    )
    assert pointer.active["section_draft:writer"] == manifest.content_digest
    assert pointer.fences["section_draft:writer"] == 1
    assert pointer.history == (manifest.content_digest,)

    # 同内容幂等：再次提交不新增 manifest、成员字节不变。
    member_before = (root / members[0].path).read_bytes()
    again = commit_publication_generation(root, manifest=manifest)
    assert again.content_digest == record.content_digest
    assert (root / members[0].path).read_bytes() == member_before


def test_k02_g2_crash_at_every_write_point_never_replaces_g1(
    tmp_path: Path,
) -> None:
    """交付终点要求：g1 已在、g2 在每个写点崩溃 → 旧 active 永不被半成品覆盖。"""

    from code2paper.agentic.authoring_artifact_publication import (
        CRASH_POINTS,
        PublicationInterruptedError,
        commit_publication_generation,
        load_active_publication_pointer,
        publication_generation_dir,
        recover_publication_generation,
        switch_publication_active,
        verify_publication_generation,
    )

    root = tmp_path / "run"
    g1 = _publish_g1(root)
    g1_member = (root / g1.members[0].path).read_bytes()
    g1_manifest_bytes = next(
        publication_generation_dir(root).glob(f"generation.*.g1.*.json")
    ).read_bytes()

    seen: dict[str, str] = {}
    for point in CRASH_POINTS:
        case_root = tmp_path / f"case-{point}"
        g1_case = _publish_g1(case_root)
        g2, _members = _generation(case_root, generation=2, value=f"g2-{point}", export=True)
        _write_export(case_root, g2)
        try:
            record = commit_publication_generation(
                case_root, manifest=g2, crash_at=point
            )
            assert record.state == "registered", record.state
            switch_publication_active(
                case_root,
                manifest=g2,
                expected_active_manifest_digest=g1_case.content_digest,
                crash_at=point,
            )
            crashed = False
        except PublicationInterruptedError:
            crashed = True
        assert crashed == (point in CRASH_POINTS)

        state, failures, digest = recover_publication_generation(
            case_root, role="section_draft", phase="writer", generation=2
        )
        seen[point] = state
        pointer = load_active_publication_pointer(case_root)
        if point in {
            "after_reserved",
            "after_member_write",
            "after_validated",
        }:
            # 未提交：没有 manifest，active 仍是 g1。
            assert state == "uncommitted", (point, state, failures)
            assert digest == ""
            assert pointer.active["section_draft:writer"] == g1_case.content_digest
        elif point in {
            "after_manifest_write",
            "after_committed_record",
            "after_registered",
        }:
            # 已提交未切换：manifest 完整可复核，active 仍是 g1（半成品没有上位）。
            assert state == "committed_unswitched", (point, state, failures)
            assert verify_publication_generation(case_root, digest) == ()
            assert pointer.active["section_draft:writer"] == g1_case.content_digest
            # 运维恢复动作：用正确的期望值重试 CAS 即可完成切换（不需要重发产物）。
            switch_publication_active(
                case_root,
                manifest=g2,
                expected_active_manifest_digest=g1_case.content_digest,
            )
            assert recover_publication_generation(
                case_root, role="section_draft", phase="writer", generation=2
            )[0] == "switched"
        elif point in {"after_active_pointer_write", "after_active_switch"}:
            # 权威指针已落盘。after_active_pointer_write 停在注册表 active 切换之前，
            # 本进程异常只证明指针写入后抛错；真实进程退出见下方子进程测试。
            assert state == "switched", (point, state, failures)
            assert pointer.active["section_draft:writer"] == g2.content_digest
        else:
            raise AssertionError(f"unmapped crash point: {point}")

        # g1 的不可变成员与 manifest 在任何崩溃点都逐字未变。
        assert (case_root / g1_case.members[0].path).read_bytes() == g1_member
        assert next(
            publication_generation_dir(case_root).glob("generation.*.g1.*.json")
        ).read_bytes() == g1_manifest_bytes

    assert seen["after_active_switch"] == "switched"


def test_k02_tampering_members_manifest_and_export_is_detected(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
        publication_generation_dir,
        recover_publication_generation,
        switch_publication_active,
        verify_publication_generation,
    )

    root = tmp_path / "run"
    manifest, members = _generation(root, generation=1, value="alpha", export=True)
    _write_export(root, manifest)
    commit_publication_generation(root, manifest=manifest)
    switch_publication_active(
        root, manifest=manifest, expected_active_manifest_digest=None
    )
    assert verify_publication_generation(root, manifest.content_digest) == ()

    # 成员字节被替换。
    member_path = root / members[0].path
    original = member_path.read_bytes()
    member_path.write_bytes(_member_payload("tampered"))
    failures = verify_publication_generation(root, manifest.content_digest)
    assert f"publication_member_bytes_mismatch:{members[0].member_id}" in failures, failures
    state, recover_failures, _digest = recover_publication_generation(
        root, role="section_draft", phase="writer", generation=1
    )
    assert state == "invalid" and recover_failures
    member_path.write_bytes(original)

    # 导出目标漂移（切换 active 之后仍须检出投影不一致）。
    export = root / manifest.export_path
    export.write_bytes(_member_payload("drifted"))
    assert (
        f"publication_export_drift:{manifest.export_path}"
        in verify_publication_generation(root, manifest.content_digest)
    )
    export.write_bytes(original)

    # 半写 manifest。
    manifest_path = next(publication_generation_dir(root).glob("generation.*.g1.*.json"))
    manifest_bytes = manifest_path.read_bytes()
    manifest_path.write_bytes(manifest_bytes[: len(manifest_bytes) // 2])
    assert verify_publication_generation(
        root, manifest.content_digest
    ) == ("publication_manifest_half_written",)
    manifest_path.write_bytes(manifest_bytes)

    # manifest 与成员不一致（成员行摘要被改后重新封摘要）。
    from code2paper.agentic.digest import digest_json

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["members"][0]["file_bytes_digest"] = "sha256:" + "0" * 64
    payload["member_set_digest"] = digest_json([
        {
            "member_id": item["member_id"],
            "path": item["path"],
            "file_bytes_digest": item["file_bytes_digest"],
            "semantic_digest": item["semantic_digest"],
            "artifact_schema_version": item["artifact_schema_version"],
        }
        for item in sorted(payload["members"], key=lambda row: row["member_id"])
    ])
    payload["content_digest"] = digest_json(
        {key: value for key, value in payload.items() if key != "content_digest"}
    )
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # 用**被改后**的声明摘要复核：manifest 自身自洽，但成员字节与成员行不符。
    assert (
        f"publication_member_bytes_mismatch:{members[0].member_id}"
        in verify_publication_generation(root, payload["content_digest"])
    )


def test_k02_same_identity_different_bytes_is_rejected_and_cas_is_respected(
    tmp_path: Path,
) -> None:
    """同 (role, phase, generation) 不同字节 → 拒绝；CAS 失败不得覆盖新 active。"""

    from code2paper.agentic.authoring_artifact_publication import (
        PublicationCasError,
        commit_publication_generation,
        load_active_publication_pointer,
        publication_active_pointer_path,
        recover_publication_generation,
        switch_publication_active,
        verify_publication_generation,
    )

    root = tmp_path / "run"
    g1 = _publish_g1(root, value="alpha")

    # 同一代、不同字节：第二个 manifest 也落盘（不可变），恢复判定必须是 invalid。
    conflicting, _members = _generation(root, generation=1, value="beta")
    commit_publication_generation(root, manifest=conflicting)
    state, failures, _digest = recover_publication_generation(
        root, role="section_draft", phase="writer", generation=1
    )
    assert state == "invalid"
    assert failures == ("publication_multiple_manifests",), failures
    assert load_active_publication_pointer(root).active["section_draft:writer"] == (
        g1.content_digest
    )

    # CAS 失败（期望旧值，实际已是新值）→ 不覆盖新 active。
    g2, _members = _generation(root, generation=2, value="gamma")
    commit_publication_generation(root, manifest=g2)
    switch_publication_active(
        root, manifest=g2, expected_active_manifest_digest=g1.content_digest
    )
    pointer_path = publication_active_pointer_path(root)
    before = pointer_path.read_bytes()
    with pytest.raises(PublicationCasError, match="publication_active_cas_failed"):
        switch_publication_active(
            root, manifest=g1, expected_active_manifest_digest=g1.content_digest
        )
    assert pointer_path.read_bytes() == before
    assert load_active_publication_pointer(root).active["section_draft:writer"] == (
        g2.content_digest
    )
    assert verify_publication_generation(root, g2.content_digest) == ()


# --------------------------------------------------------------------------- #
# K02 剩余 AT：媒体类型、派生回执/重放、fence 与并发、角色混代
# --------------------------------------------------------------------------- #


def test_k02_markdown_and_bytes_members_are_media_validated(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
        verify_publication_generation,
    )

    root = tmp_path / "run"
    markdown = "# 标题\n\n正文没有 JSON 结构。\n".encode("utf-8")
    binary = b"\x00\x01\x02not-utf8\xff"
    manifest, members = _generation(
        root,
        generation=1,
        value="media",
        export=False,
        media_types={
            "notes": "text/markdown",
            "blob": "application/octet-stream",
        },
        members={"notes": markdown, "blob": binary},
    )
    record = commit_publication_generation(root, manifest=manifest)
    assert record.state == "registered", record.state
    assert verify_publication_generation(root, manifest.content_digest) == ()
    media = {item.member_id: item.media_type for item in members}
    assert media == {"notes": "text/markdown", "blob": "application/octet-stream"}

    # 未支持的媒体类型在 stage 阶段就拒绝（不落盘成"看起来合法"的成员）。
    from code2paper.agentic.authoring_artifact_publication import (
        PublicationError,
        stage_publication_members,
    )

    with pytest.raises(PublicationError, match="publication_media_unsupported"):
        stage_publication_members(
            root,
            role="section_draft",
            phase="writer",
            members={"weird": b"x"},
            media_types={"weird": "application/x-weird"},
        )

    # 声明为 JSON 但内容不是 JSON → 提交时具名 incomplete。
    bad, _members = _generation(
        root,
        generation=2,
        value="bad-json",
        members={"draft": b"not json at all\n"},
    )
    bad_record = commit_publication_generation(root, manifest=bad)
    assert bad_record.state == "incomplete"
    assert any(
        "publication_payload_unparsable" in item for item in bad_record.failures
    ), bad_record.failures


def test_k02_receipt_is_derived_and_replay_is_idempotent(tmp_path: Path) -> None:
    """回执可从持久事实重建；重放 commit/switch 不新生产物、不改摘要。"""

    from code2paper.agentic.authoring_artifact_publication import (
        build_publication_receipt,
        commit_publication_generation,
        load_active_publication_pointer,
        publication_generation_dir,
        switch_publication_active,
    )

    root = tmp_path / "run"
    g1 = _publish_g1(root, value="alpha")
    receipt = build_publication_receipt(root, role="section_draft", phase="writer")
    assert receipt.active is True
    assert receipt.state == "switched"
    assert receipt.generation == 1
    assert receipt.manifest_digest == g1.content_digest
    assert receipt.fence == 1
    assert receipt.member_digests["draft"] == g1.members[0].file_bytes_digest
    assert receipt.rebuilt_from and receipt.registration_id

    # 回执是派生的：重建两次逐字相同，且不需要先写回执才能激活。
    again = build_publication_receipt(root, role="section_draft", phase="writer")
    assert again.content_digest == receipt.content_digest

    # 重放：同内容再提交一次 + 再激活一次，不新生产物、fence 仍单调可信。
    before = {
        path.name: path.read_bytes()
        for path in publication_generation_dir(root).glob("generation.*.json")
    }
    replay_commit = commit_publication_generation(root, manifest=g1)
    assert replay_commit.content_digest == commit_publication_generation(
        root, manifest=g1
    ).content_digest
    replay_switch = switch_publication_active(
        root,
        manifest=g1,
        expected_active_manifest_digest=g1.content_digest,
        expected_fence=1,
    )
    assert replay_switch.fences["section_draft:writer"] == 2
    assert replay_switch.active["section_draft:writer"] == g1.content_digest
    after = {
        path.name: path.read_bytes()
        for path in publication_generation_dir(root).glob("generation.*.json")
    }
    assert after == before, "重放不得新生产物或改写已提交字节"
    assert load_active_publication_pointer(root).history == (g1.content_digest,)


def test_k02_stale_fence_and_concurrent_switches_are_safe(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_artifact_publication import (
        PublicationCasError,
        commit_publication_generation,
        load_active_publication_pointer,
        switch_publication_active,
    )

    root = tmp_path / "run"
    g1 = _publish_g1(root, value="alpha")
    g2, _members = _generation(root, generation=2, value="beta")
    commit_publication_generation(root, manifest=g2)

    # 旧 fence 的持有者不能覆盖新 active。
    with pytest.raises(PublicationCasError, match="publication_active_fence_stale"):
        switch_publication_active(
            root,
            manifest=g2,
            expected_active_manifest_digest=g1.content_digest,
            expected_fence=99,
        )
    assert load_active_publication_pointer(root).active["section_draft:writer"] == (
        g1.content_digest
    )

    # 并发 CAS：两个切换都用同一期望值，只有一个能成功。
    first = switch_publication_active(
        root,
        manifest=g2,
        expected_active_manifest_digest=g1.content_digest,
        expected_fence=1,
    )
    assert first.active["section_draft:writer"] == g2.content_digest
    with pytest.raises(PublicationCasError, match="publication_active_cas_failed"):
        switch_publication_active(
            root,
            manifest=g2,
            expected_active_manifest_digest=g1.content_digest,
            expected_fence=1,
        )
    assert load_active_publication_pointer(root).active["section_draft:writer"] == (
        g2.content_digest
    )

    # 后代不得覆盖前代的成员与来源：g1 的内容寻址成员逐字仍在、仍可复核。
    from code2paper.agentic.authoring_artifact_publication import (
        verify_publication_generation,
    )

    assert verify_publication_generation(root, g1.content_digest) == ()
    assert json.loads(
        (root / g1.members[0].path).read_text(encoding="utf-8")
    )["value"] == "alpha"
    pointer = load_active_publication_pointer(root)
    assert pointer.history == (g1.content_digest, g2.content_digest)


def test_k02_member_role_mixing_and_missing_members_are_rejected(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
        stage_publication_members,
        verify_publication_generation,
    )

    root = tmp_path / "run"
    # 用另一个 (role, phase) 的成员直接拼进本代 manifest（角色混代）。
    foreign = stage_publication_members(
        root,
        role="section_draft",
        phase="binder",
        members={"draft": _member_payload("foreign")},
        semantic_digests={"draft": "sha256:foreign"},
    )
    manifest, _members = _generation(root, generation=1, value="alpha")
    mixed = manifest.model_copy(update={"members": (foreign[0],)})
    record = commit_publication_generation(root, manifest=mixed)
    assert record.state == "incomplete"
    assert any(
        "publication_member_role_mismatch:draft" in item for item in record.failures
    ), record.failures

    # 成员不全（record 在、成员文件被删）→ 复核具名拒绝。
    good, members = _generation(root, generation=2, value="beta")
    commit_publication_generation(root, manifest=good)
    (root / members[0].path).unlink()
    assert (
        f"publication_member_missing:{members[0].member_id}"
        in verify_publication_generation(root, good.content_digest)
    )


def _repo_src() -> str:
    return str(Path(__file__).resolve().parents[3] / "src")


def publication_cas_race_worker(spec: dict, barrier, queue) -> None:
    """两个进程在同一 barrier 后竞争同一次 expected-active/fence。"""

    barrier.wait(30)
    from code2paper.agentic.authoring_artifact_publication import (
        PublicationCasError,
        PublicationManifestV1,
        switch_publication_active,
    )

    manifest = PublicationManifestV1.model_validate(spec["manifest"])
    try:
        pointer = switch_publication_active(
            spec["root"],
            manifest=manifest,
            expected_active_manifest_digest=spec["expected"],
            expected_fence=spec["fence"],
        )
        queue.put({
            "status": "ok",
            "active": pointer.active["section_draft:writer"],
            "fence": pointer.fences["section_draft:writer"],
        })
    except PublicationCasError as exc:
        queue.put({"status": "conflict", "error": str(exc)})


def publication_reader_worker(root: str, queue) -> None:
    """新进程里的真实 reader，不继承父进程内存。"""

    from code2paper.agentic.authoring_artifact_index import (
        build_artifact_index,
        read_artifact_validated,
    )
    from code2paper.agentic.authoring_artifact_publication import (
        load_active_publication_pointer,
        recover_publication_generation,
    )
    from code2paper.agentic.authoring_artifact_registry import load_artifact_registry

    pointer = load_active_publication_pointer(root)
    registry = load_artifact_registry(root)
    index = build_artifact_index(root)
    read = read_artifact_validated(
        index=index, role="section_draft", phase="writer", out_root=root
    )
    state, failures, digest = recover_publication_generation(
        root, role="section_draft", phase="writer", generation=2
    )
    active_id = registry.active.get("section_draft:writer", "")
    active_generation = 0
    for item in registry.registrations:
        if item.registration_id == active_id:
            active_generation = int(item.generation)
    queue.put({
        "value": read.members["draft"]["value"],
        "publication_digest": pointer.active.get("section_draft:writer", ""),
        "fence": int(pointer.fences.get("section_draft:writer", 0)),
        "registry_generation": active_generation,
        "recovery": state,
        "recovery_failures": list(failures),
        "recovery_digest": digest,
    })


def _publication_child_main(argv: list[str]) -> None:
    mode, root = argv[0], argv[1]
    from code2paper.agentic.authoring_artifact_publication import (
        PublicationManifestV1,
        commit_publication_generation,
        stage_publication_members,
        switch_publication_active,
    )

    if mode == "stage-exit":
        stage_publication_members(
            root,
            role="section_draft",
            phase="writer",
            members={"draft": _member_payload("gamma")},
            semantic_digests={"draft": "sha256:gamma"},
            crash_at="after_member_durable_write",
            crash_exit=True,
        )
    elif mode == "manifest-exit":
        manifest = PublicationManifestV1.model_validate_json(Path(argv[2]).read_text())
        commit_publication_generation(
            root,
            manifest=manifest,
            crash_at="after_manifest_write",
            crash_exit=True,
        )
    elif mode == "pointer-exit":
        manifest = PublicationManifestV1.model_validate_json(Path(argv[2]).read_text())
        switch_publication_active(
            root,
            manifest=manifest,
            expected_active_manifest_digest=argv[3],
            expected_fence=int(argv[4]),
            crash_at="after_active_pointer_write",
            crash_exit=True,
        )
    else:
        raise SystemExit(f"unknown publication child mode:{mode}")
    raise SystemExit("child returned instead of exiting at the write point")


def _run_publication_child(mode: str, root: Path, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = _repo_src() + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--publication-child",
            mode,
            str(root),
            *extra,
        ],
        cwd=str(Path(__file__).resolve().parents[3]),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _read_in_new_process(root: Path) -> dict:
    ctx = multiprocessing.get_context("spawn")
    os.environ["PYTHONPATH"] = _repo_src() + os.pathsep + os.environ.get("PYTHONPATH", "")
    queue = ctx.Queue()
    process = ctx.Process(target=publication_reader_worker, args=(str(root), queue))
    process.start()
    process.join(60)
    assert process.exitcode == 0, process.exitcode
    return queue.get(timeout=10)


def test_k02_persistence_points_name_real_owners() -> None:
    from code2paper.agentic.authoring_artifact_publication import PERSISTENCE_POINTS

    by_id = {item["id"]: item for item in PERSISTENCE_POINTS}
    assert by_id["stage_member"]["crash"] == "after_member_durable_write"
    assert by_id["stage_member"]["crash"] != "after_member_write"
    assert by_id["manifest"]["kind"] == "durable_manifest_write"
    assert by_id["active_pointer"]["crash"] == "after_active_pointer_write"
    assert by_id["commit_receipt"]["kind"] == "derived_no_write"
    assert by_id["commit_receipt"]["crash"] == ""
    assert by_id["export_projection"]["kind"] == "projection_verified_not_commit_write"


def test_k02_subprocess_exit_at_real_write_points_recovers_in_a_new_reader(
    tmp_path: Path,
) -> None:
    """关键写点用子进程退出；新进程 reader 恢复。本进程异常不能折抵。"""

    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
        publication_generation_dir,
    )

    root = tmp_path / "member-exit"
    g1 = _publish_g1(root, value="alpha")
    g1_bytes = (root / g1.members[0].path).read_bytes()
    exited = _run_publication_child("stage-exit", root)
    assert exited.returncode == 86, (exited.returncode, exited.stderr)
    read = _read_in_new_process(root)
    assert read["value"] == "alpha"
    assert read["publication_digest"] == g1.content_digest
    assert (root / g1.members[0].path).read_bytes() == g1_bytes

    root = tmp_path / "manifest-exit"
    g1 = _publish_g1(root, value="alpha")
    g2, _members = _generation(root, generation=2, value="beta", export=True)
    _write_export(root, g2)
    side = tmp_path / "g2-manifest.json"
    side.write_text(g2.model_dump_json(), encoding="utf-8")
    exited = _run_publication_child("manifest-exit", root, (str(side),))
    assert exited.returncode == 86, (exited.returncode, exited.stderr)
    assert any(publication_generation_dir(root).glob("generation.*.g2.*.json"))
    read = _read_in_new_process(root)
    assert read["value"] == "alpha"
    assert read["publication_digest"] == g1.content_digest
    assert read["recovery"] == "committed_unswitched"

    root = tmp_path / "pointer-exit"
    g1 = _publish_g1(root, value="alpha")
    g2, _members = _generation(root, generation=2, value="beta", export=True)
    _write_export(root, g2)
    commit_publication_generation(root, manifest=g2)
    side = tmp_path / "g2-pointer.json"
    side.write_text(g2.model_dump_json(), encoding="utf-8")
    g1_bytes = (root / g1.members[0].path).read_bytes()
    exited = _run_publication_child(
        "pointer-exit", root, (str(side), g1.content_digest, "1")
    )
    assert exited.returncode == 86, (exited.returncode, exited.stderr)
    read = _read_in_new_process(root)
    assert read["value"] == "beta"
    assert read["publication_digest"] == g2.content_digest
    assert read["fence"] == 2
    assert read["recovery"] == "switched"
    # 指针写入后进程退出，注册表 active 还停在 g1；reader 仍认发布权威。
    assert read["registry_generation"] == 1
    assert (root / g1.members[0].path).read_bytes() == g1_bytes


def test_k02_two_processes_race_the_same_fence(tmp_path: Path) -> None:
    """两个进程 barrier 后竞争同一 expected-active/fence；新进程只看到一个成功者。"""

    from code2paper.agentic.authoring_artifact_publication import (
        commit_publication_generation,
    )

    root = tmp_path / "race"
    g1 = _publish_g1(root, value="alpha")
    g2, _members = _generation(root, generation=2, value="beta", export=True)
    _write_export(root, g2)
    commit_publication_generation(root, manifest=g2)
    os.environ["PYTHONPATH"] = _repo_src() + os.pathsep + os.environ.get("PYTHONPATH", "")
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(2)
    queue = ctx.Queue()
    spec = {
        "root": str(root),
        "manifest": g2.model_dump(mode="json"),
        "expected": g1.content_digest,
        "fence": 1,
    }
    processes = [
        ctx.Process(target=publication_cas_race_worker, args=(spec, barrier, queue))
        for _index in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(60)
    assert [process.exitcode for process in processes] == [0, 0]
    results = [queue.get(timeout=10) for _index in range(2)]
    winners = [item for item in results if item["status"] == "ok"]
    losers = [item for item in results if item["status"] == "conflict"]
    assert len(winners) == 1, results
    assert len(losers) == 1, results
    assert winners[0]["active"] == g2.content_digest
    assert winners[0]["fence"] == 2
    assert "publication_active_cas_failed" in losers[0]["error"] or (
        "publication_active_fence_stale" in losers[0]["error"]
    )
    read = _read_in_new_process(root)
    assert read["value"] == "beta"
    assert read["fence"] == 2
    assert read["publication_digest"] == g2.content_digest


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--publication-child":
    _publication_child_main(sys.argv[2:])
