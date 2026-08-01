from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from code2paper.agentic.artifact_freshness import (
    _artifact_contract_failures,
    _digest_json,
)


@pytest.mark.parametrize(
    "producer_version",
    [
        "code2paper-evidence-compiler-v3",
        "code2paper-generic-research-data-plane-v1",
    ],
)
def test_evidence_packets_v3_accepts_legacy_and_generic_producers(
    tmp_path, producer_version: str
) -> None:
    packets = [{"packet_id": "P-1"}]
    path = tmp_path / "evidence_packets_v3.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "3.0",
                "producer_version": producer_version,
                "repo_snapshot_id": "snapshot-1",
                "project_tree_hash": "tree-1",
                "content_digest": _digest_json(packets),
                "packets": packets,
            }
        ),
        encoding="utf-8",
    )

    failures = _artifact_contract_failures(
        "evidence_packets_v3",
        path,
        SimpleNamespace(snapshot_id="snapshot-1", project_tree_hash="tree-1"),
        SimpleNamespace(),
        {"evidence_packets_v3": str(path)},
    )

    assert failures == []


def test_evidence_packets_v3_rejects_unknown_producer(tmp_path) -> None:
    packets = [{"packet_id": "P-1"}]
    path = tmp_path / "evidence_packets_v3.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "3.0",
                "producer_version": "code2paper-untrusted-generic-v1",
                "repo_snapshot_id": "snapshot-1",
                "project_tree_hash": "tree-1",
                "content_digest": _digest_json(packets),
                "packets": packets,
            }
        ),
        encoding="utf-8",
    )

    failures = _artifact_contract_failures(
        "evidence_packets_v3",
        path,
        SimpleNamespace(snapshot_id="snapshot-1", project_tree_hash="tree-1"),
        SimpleNamespace(),
        {"evidence_packets_v3": str(path)},
    )

    assert failures == ["producer_version_not_accepted"]
