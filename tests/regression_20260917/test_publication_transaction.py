"""PR F / §F.4：发布是事务——中断只能留下 orphan/incomplete，active 不得指向半成品。"""

from __future__ import annotations

import json

import pytest
from pathlib import Path

from code2paper.agentic.authoring_artifact_index import (
    build_artifact_index,
    publish_artifact_index,
)
from code2paper.agentic.authoring_artifact_publication import (
    journal_dir,
    publish_artifact_transaction,
    scan_orphan_temp_files,
    scan_publication_transactions,
)
from code2paper.agentic.authoring_artifact_registry import load_artifact_registry
from code2paper.agentic.authoring_doctor import run_authoring_doctor


def _payload(schema_version: str = "2.0", *, content_digest: str = "sha256:new") -> bytes:
    return (
        json.dumps(
            {
                "schema_version": schema_version,
                "archive_digest": "sha256:archive",
                "source_manifest_digest": "sha256:source",
                "content_digest": content_digest,
                "pages": [{"page_id": "page:1"}],
                "worksets": [{"workset_id": "ws:1"}],
            }
        )
        + "\n"
    ).encode("utf-8")


def test_successful_publication_runs_every_step(tmp_path: Path) -> None:
    root = tmp_path / "run"
    target = root / "artifacts/06_authoring/consumer_workset_manifest_v2.writer.2.json"

    record = publish_artifact_transaction(
        root,
        role="consumer_workset_manifest",
        phase="writer",
        target_path=target,
        payload=_payload(),
        generation=2,
        producer="unit-test",
        upstream_refs=("narrative_plan:sha256:plan",),
    )

    assert record.state == "complete"
    assert record.failures == ()
    assert target.is_file()
    assert not list(target.parent.glob(".*.tmp")), "事务完成后不得留下临时文件"

    states = [
        item.state
        for item in scan_publication_transactions(root)
        if item.transaction_id == record.transaction_id
    ]
    # journal 是 append-only 的状态推进：每一步都有自己的不可变记录。
    assert states == ["complete"]
    journal_states = sorted(
        path.name for path in journal_dir(root).glob(f"tx.*{record.transaction_id[3:]}*.json")
    )
    assert journal_states, "journal 必须留下每一步的记录"
    assert len(journal_states) == 5, journal_states

    registry = load_artifact_registry(root)
    assert registry.active["consumer_workset_manifest:writer"]
    index = build_artifact_index(root)
    assert index.active["consumer_workset_manifest:writer"].endswith("writer.2.json")


def test_validation_failure_publishes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "run"
    target = root / "artifacts/06_authoring/mine.json"

    record = publish_artifact_transaction(
        root,
        role="some_role",
        phase="writer",
        target_path=target,
        payload=b"{ not json",
        generation=1,
        producer="unit-test",
    )

    assert record.state == "incomplete"
    assert record.failures == ("publication_payload_unparsable",)
    assert not target.exists(), "验证失败不得发布半成品"
    assert not list(target.parent.glob(".*.tmp"))
    assert scan_publication_transactions(root)[0].state == "incomplete"


def test_publish_never_overwrites_on_failed_validation(tmp_path: Path) -> None:
    root = tmp_path / "run"
    target = root / "artifacts/06_authoring/mine.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"schema_version": "1.0", "value": "old"}\n', encoding="utf-8")

    def _reject(_payload):
        return ("unit_test_rejected",)

    record = publish_artifact_transaction(
        root,
        role="some_role",
        phase="writer",
        target_path=target,
        payload=_payload(),
        generation=1,
        validator=_reject,
    )

    assert record.state == "incomplete"
    assert record.failures == ("unit_test_rejected",)
    assert json.loads(target.read_text(encoding="utf-8"))["value"] == "old"


def test_interrupted_publication_is_reported_and_not_active(tmp_path: Path) -> None:
    """模拟"已发布但尚未注册"的崩溃点：journal 停在 published，索引看不到它。"""

    root = tmp_path / "run"
    target = root / "artifacts/06_authoring/consumer_workset_manifest_v2.writer.2.json"
    target.parent.mkdir(parents=True)
    payload = _payload()
    target.write_bytes(payload)

    from code2paper.agentic.authoring_artifact_publication import (
        PublicationTransactionV1,
    )
    from code2paper.agentic.tool_runtime import atomic_write_bytes

    record = PublicationTransactionV1(
        transaction_id="tx:interrupted",
        sequence=3,
        state="published",
        logical_role="consumer_workset_manifest",
        phase="writer",
        generation=2,
        target_path="artifacts/06_authoring/consumer_workset_manifest_v2.writer.2.json",
        file_bytes_digest="sha256:" + "0" * 64,
        producer="unit-test",
    )
    path = journal_dir(root) / "tx.interrupted.s3.published.json"
    atomic_write_bytes(path, (record.model_dump_json(indent=2) + "\n").encode("utf-8"))

    index = build_artifact_index(root)
    # 没有注册 → 索引不会把它当成已发布的当前对象。
    assert not load_artifact_registry(root).active

    report = run_authoring_doctor(root)
    assert any(
        item.state == "published" for item in report.publications
    )
    assert (
        "publication_incomplete:consumer_workset_manifest:writer:published"
        in report.critical_blockers
    )
    assert "PUBLICATION" in report.render()
    publish_artifact_index(root)  # 索引仍可发布（只读诊断不阻断）
    assert index.entries


def test_orphan_temp_file_is_reported(tmp_path: Path) -> None:
    root = tmp_path / "run"
    directory = root / "artifacts/06_authoring"
    directory.mkdir(parents=True)
    orphan = directory / ".consumer_workset_manifest_v2.json.999.publish.tmp"
    orphan.write_bytes(b'{"partial":')

    assert scan_orphan_temp_files(root) == (
        "artifacts/06_authoring/.consumer_workset_manifest_v2.json.999.publish.tmp",
    )

    report = run_authoring_doctor(root)
    assert (
        "publication_orphan_temp:artifacts/06_authoring/"
        ".consumer_workset_manifest_v2.json.999.publish.tmp"
        in report.critical_blockers
    )
    assert "ORPHAN TEMP" in report.render()
