"""WP6：阶段化产物索引与合同 N/A 一致性（方案 §10）。"""

from __future__ import annotations

import json

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
