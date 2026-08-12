from __future__ import annotations

import json

from code2paper.agentic.v3_runtime import V3GraphWrapper


GENERIC_PRODUCER = "code2paper-generic-research-data-plane-v1"
LEGACY_PRODUCER = "code2paper-evidence-compiler-v3"


def _write_typed_artifacts(tmp_path, producer_version: str) -> dict[str, str]:
    specifications = {
        "evidence_packets_v3": ("evidence_packets_v3.json", "packets", [{"packet_id": "P-1"}]),
        "code_facts_v1": ("code_facts_v1.json", "facts", [{"fact_id": "F-1"}]),
        "atomic_claims_v3": ("atomic_claims_v3.json", "claims", [{"claim_id": "C-1"}]),
    }
    artifacts: dict[str, str] = {}
    for key, (filename, collection_key, values) in specifications.items():
        path = tmp_path / filename
        path.write_text(
            json.dumps(
                {
                    "schema_version": "3.0" if key != "code_facts_v1" else "1.0",
                    "producer_version": producer_version,
                    "repo_snapshot_id": "snapshot-1",
                    "project_tree_hash": "tree-1",
                    "content_digest": f"sha256:{key}",
                    collection_key: values,
                }
            ),
            encoding="utf-8",
        )
        artifacts[key] = str(path)
    return artifacts


def test_already_generic_evidence_registers_manifest_without_rewriting(
    tmp_path,
) -> None:
    artifacts = _write_typed_artifacts(tmp_path, GENERIC_PRODUCER)
    payload = {"artifacts": artifacts}
    before = {
        key: (tmp_path / f"{key}.json").read_bytes()
        for key in artifacts
    }

    V3GraphWrapper._register_generic_research_manifest(object(), payload)

    manifest_path = tmp_path / "generic_research_compilation_manifest_v3.json"
    assert payload["artifacts"]["generic_research_compilation_manifest"] == str(
        manifest_path
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["producer"] == "generic_research_data_plane"
    assert manifest["producer_version"] == GENERIC_PRODUCER
    assert manifest["compiled_fact_count"] == 1
    assert manifest["compiled_claim_count"] == 1
    for key in ("evidence_packets_v3", "code_facts_v1", "atomic_claims_v3"):
        artifact = json.loads(
            (tmp_path / f"{key}.json").read_text(encoding="utf-8")
        )
        assert artifact["producer_version"] == GENERIC_PRODUCER
        assert (tmp_path / f"{key}.json").read_bytes() == before[key]


def test_legacy_profile_producer_is_not_laundered(tmp_path) -> None:
    artifacts = _write_typed_artifacts(tmp_path, LEGACY_PRODUCER)
    payload = {"artifacts": artifacts}

    V3GraphWrapper._register_generic_research_manifest(object(), payload)

    assert "generic_research_compilation_manifest" not in payload["artifacts"]
    assert not (tmp_path / "generic_research_compilation_manifest_v3.json").exists()
    for key in artifacts:
        artifact = json.loads(
            (tmp_path / f"{key}.json").read_text(encoding="utf-8")
        )
        assert artifact["producer_version"] == LEGACY_PRODUCER


def test_patch_evidence_does_not_launder_unknown_producer(tmp_path) -> None:
    artifacts = _write_typed_artifacts(tmp_path, "code2paper-untrusted-generic-v1")
    payload = {"artifacts": artifacts}

    V3GraphWrapper._register_generic_research_manifest(object(), payload)

    assert "generic_research_compilation_manifest" not in payload["artifacts"]
    assert not (tmp_path / "generic_research_compilation_manifest_v3.json").exists()
    packet_payload = json.loads(
        (tmp_path / "evidence_packets_v3.json").read_text(encoding="utf-8")
    )
    assert packet_payload["producer_version"] == "code2paper-untrusted-generic-v1"
