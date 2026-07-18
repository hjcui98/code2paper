from __future__ import annotations

from pathlib import Path
import subprocess

from code2paper.agentic.artifact_freshness import (
    build_check_artifact_freshness_tool,
    check_artifact_freshness,
    freshness_cache_key,
)
from code2paper.agentic.atomic_claim_v2 import convert_claims_to_v2, verify_atomic_claims_v2
from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.agentic.evidence_v2 import (
    build_evidence_snapshot_v2,
    is_direct_code_span,
    validate_evidence_snapshot_round_trip,
    write_evidence_snapshot_v2,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot, write_repo_snapshot
from code2paper.agentic.contracts import AgenticRunState, StageStatus
from code2paper.agentic.legacy_intake_stage_tool import run_intake
from code2paper.core.schemas import (
    AuthorMode,
    ClaimContract,
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    ConflictStatus,
    EvidenceItem,
    MethodEvidence,
    RawEvidencePack,
    SourceType,
    SupportStatus,
)


def _raw(root: Path) -> RawEvidencePack:
    return RawEvidencePack(
        project_id="demo",
        project_root=str(root),
        evidence_items=[
            EvidenceItem(
                evidence_id="E1",
                source_type=SourceType.SOURCE,
                path="model.py",
                symbol="encode",
                line_start=1,
                line_end=2,
                content_summary="encoder reads features",
                confidence=0.9,
            )
        ],
    )


def _claims() -> tuple[MethodEvidence, ClaimEvidenceMap]:
    method = MethodEvidence(
        project_id="demo",
        author_mode=AuthorMode.NONE,
        method_name="Demo",
        method_goal="Describe encoder.",
        implementation_scope="test",
        claim_contracts=[
            ClaimContract(
                claim_id="C1",
                claim_intent="The encoder reads configured features.",
                support_status=ConflictStatus.SUPPORTED,
                evidence_span_ids=["E1"],
                allowed_wording_boundary="The encoder reads configured features.",
            )
        ],
    )
    claim_map = ClaimEvidenceMap(
        claims=[
            ClaimEvidenceItem(
                claim_id="C1",
                claim_text="The encoder reads configured features.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
            )
        ]
    )
    return method, claim_map


def test_exact_excerpt_digest_round_trip_and_output_exclusion(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text("def encode(features):\n    return features\n", encoding="utf-8")
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs" / "generated.txt").write_text("ignored", encoding="utf-8")
    repo = build_repo_snapshot(tmp_path)
    evidence = build_evidence_snapshot_v2(_raw(tmp_path), repo)

    assert [item.path for item in repo.included_files] == ["model.py"]
    assert evidence.spans[0].exact_excerpt == "def encode(features):\n    return features\n"
    assert validate_evidence_snapshot_round_trip(evidence, repo) == []

    before = repo.project_tree_hash
    (tmp_path / "outputs" / "generated.txt").write_text("changed", encoding="utf-8")
    assert build_repo_snapshot(tmp_path).project_tree_hash == before


def test_narrative_markdown_is_semantic_hint_never_direct_code_evidence(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text(
        "class Predictor:\n    def forward(self, features): return features\n",
        encoding="utf-8",
    )
    (tmp_path / "paperdraft.md").write_text(
        "The MLP uses soft reweighting and a rendering loss.\n",
        encoding="utf-8",
    )
    raw = RawEvidencePack(
        project_id="demo", project_root=str(tmp_path),
        evidence_items=[
            EvidenceItem(
                evidence_id="E1", source_type=SourceType.SOURCE, path="model.py",
                line_start=1, line_end=2, content_summary="predictor code", confidence=0.9,
            ),
            EvidenceItem(
                evidence_id="E2", source_type=SourceType.SOURCE, path="paperdraft.md",
                line_start=1, line_end=1, content_summary="paper narrative", confidence=0.9,
            ),
        ],
    )
    claim_map = ClaimEvidenceMap(claims=[ClaimEvidenceItem(
        claim_id="C1",
        claim_text="The MLP uses soft reweighting and a rendering loss.",
        support_status=SupportStatus.SUPPORTED,
        evidence_ids=["E2"],
    )])
    method = MethodEvidence(
        project_id="demo", method_name="Demo", method_goal="Describe code.",
        implementation_scope="test",
    )
    snapshot = build_evidence_snapshot_v2(raw, build_repo_snapshot(tmp_path))
    converted = convert_claims_to_v2(
        claim_map, build_claim_verification_report(method, claim_map), snapshot
    )
    verified = verify_atomic_claims_v2(converted, snapshot)
    code_span = next(item for item in snapshot.spans if item.evidence_id == "E1")
    narrative_span = next(item for item in snapshot.spans if item.evidence_id == "E2")

    assert is_direct_code_span(code_span)
    assert narrative_span.strength == "semantic_hint"
    assert not is_direct_code_span(narrative_span)
    assert converted.claims[0].direct_evidence_ids == []
    assert verified.claims[0].verdict_status == "unsupported"


def test_excerpt_and_file_drift_invalidate_snapshot_and_downstream(tmp_path: Path) -> None:
    source = tmp_path / "model.py"
    source.write_text("def encode(features):\n    return features\n# outside\n", encoding="utf-8")
    repo = build_repo_snapshot(tmp_path)
    evidence = build_evidence_snapshot_v2(_raw(tmp_path), repo)
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(evidence.model_dump_json(), encoding="utf-8")
    downstream = tmp_path / "projection.json"
    downstream.write_text("{}", encoding="utf-8")

    source.write_text("def encode(features):\n    return normalized\n# outside\n", encoding="utf-8")
    report = check_artifact_freshness(
        repo_snapshot=repo,
        evidence_snapshot=evidence,
        artifacts={"evidence_snapshot_v2": str(evidence_path), "authoring_projection": str(downstream)},
    )
    assert report.status == "failed"
    assert report.source_drift
    assert "excerpt_digest_mismatch:E1" in report.evidence_round_trip_failures
    assert "authoring_projection" in report.stale_artifact_keys


def test_change_outside_excerpt_still_triggers_file_and_tree_drift(tmp_path: Path) -> None:
    source = tmp_path / "model.py"
    source.write_text("def encode(features):\n    return features\n# outside\n", encoding="utf-8")
    repo = build_repo_snapshot(tmp_path)
    evidence = build_evidence_snapshot_v2(_raw(tmp_path), repo)
    source.write_text("def encode(features):\n    return features\n# changed outside\n", encoding="utf-8")
    current = build_repo_snapshot(tmp_path)

    failures = validate_evidence_snapshot_round_trip(evidence, current)
    assert "file_digest_mismatch:E1" in failures
    assert "excerpt_digest_mismatch:E1" not in failures
    assert current.project_tree_hash != repo.project_tree_hash


def test_v1_claim_conversion_is_unverified_until_explicit_v2_verification(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text(
        "def encode(configured_features):\n    return configured_features\n",
        encoding="utf-8",
    )
    method, claim_map = _claims()
    verification = build_claim_verification_report(method, claim_map)
    evidence = build_evidence_snapshot_v2(_raw(tmp_path), build_repo_snapshot(tmp_path))

    converted = convert_claims_to_v2(claim_map, verification, evidence)
    verified = verify_atomic_claims_v2(converted, evidence)

    assert converted.claims[0].verdict_status == "unverified"
    assert converted.claims[0].supported_fragment == ""
    assert verified.claims[0].verdict_status == "supported"
    assert verified.claims[0].supported_fragment == claim_map.claims[0].claim_text


def test_tampered_atomic_claim_digest_marks_it_and_downstream_stale(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "model.py").write_text("def encode(features):\n    return features\n", encoding="utf-8")
    repo = build_repo_snapshot(project)
    evidence = build_evidence_snapshot_v2(_raw(project), repo)
    evidence_path = tmp_path / "evidence_v2.json"
    evidence_path.write_text(evidence.model_dump_json(), encoding="utf-8")
    atomic = tmp_path / "atomic.json"
    atomic.write_text(
        '{"schema_version":"2.0","evidence_snapshot_id":"%s","evidence_snapshot_digest":"stale",'
        '"claims":[],"content_digest":"stale"}' % evidence.evidence_snapshot_id,
        encoding="utf-8",
    )
    projection = tmp_path / "projection.json"
    projection.write_text("{}", encoding="utf-8")

    report = check_artifact_freshness(
        repo_snapshot=repo,
        evidence_snapshot=evidence,
        artifacts={
            "evidence_snapshot_v2": str(evidence_path),
            "atomic_claims_v2": str(atomic),
            "authoring_projection": str(projection),
        },
    )
    atomic_verdict = next(item for item in report.verdicts if item.artifact_key == "atomic_claims_v2")
    assert atomic_verdict.status == "stale"
    assert "evidence_snapshot_digest_mismatch" in atomic_verdict.failures
    assert "authoring_projection" in report.stale_artifact_keys
    assert report.recommended_route == "evidence"


def test_cache_key_binds_snapshot_producer_and_inputs() -> None:
    base = freshness_cache_key(repo_snapshot_id="repo:1", producer_version="p1", input_digests={"evidence": "a"})
    assert base != freshness_cache_key(repo_snapshot_id="repo:2", producer_version="p1", input_digests={"evidence": "a"})
    assert base != freshness_cache_key(repo_snapshot_id="repo:1", producer_version="p2", input_digests={"evidence": "a"})
    assert base != freshness_cache_key(repo_snapshot_id="repo:1", producer_version="p1", input_digests={"evidence": "b"})


def test_symlink_records_target_without_following_external_content(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("external", encoding="utf-8")
    (tmp_path / "link.py").symlink_to(outside)
    snapshot = build_repo_snapshot(tmp_path)

    link = snapshot.included_files[0]
    assert link.kind == "symlink"
    assert link.link_target == str(outside)
    before = snapshot.project_tree_hash
    outside.write_text("external changed", encoding="utf-8")
    assert build_repo_snapshot(tmp_path).project_tree_hash == before


def test_continuing_with_frozen_snapshot_after_source_change_blocks_at_intake(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = project / "model.py"
    source.write_text("value = 1\n", encoding="utf-8")
    author = project / "author.yaml"
    author.write_text("paper_method_goal: describe value\n", encoding="utf-8")
    snapshot_path = tmp_path / "repo_snapshot.json"
    write_repo_snapshot(snapshot_path, build_repo_snapshot(project))
    source.write_text("value = 2\n", encoding="utf-8")
    state = AgenticRunState(
        project_root=project,
        out_root=tmp_path / "out",
        author_markers_path=str(author),
        artifacts={"repo_snapshot": str(snapshot_path)},
    )

    result = run_intake(state)
    assert result.status == StageStatus.BLOCKED
    assert result.blocked_reason == "source_drift"


def test_evidence_repair_creates_immutable_parent_child_lineage(tmp_path: Path) -> None:
    source = tmp_path / "model.py"
    source.write_text("def encode(features):\n    return features\n", encoding="utf-8")
    first = build_evidence_snapshot_v2(_raw(tmp_path), build_repo_snapshot(tmp_path))
    first_path = tmp_path / "evidence_snapshot_v1.json"
    write_evidence_snapshot_v2(first_path, first)
    frozen_parent_bytes = first_path.read_bytes()

    source.write_text("def encode(features):\n    return normalized_features\n", encoding="utf-8")
    second = build_evidence_snapshot_v2(
        _raw(tmp_path),
        build_repo_snapshot(tmp_path),
        parent=first,
        repair_reason="source_change_reanalysis",
    )

    assert second.snapshot_version == 2
    assert second.parent_evidence_snapshot_id == first.evidence_snapshot_id
    assert second.evidence_snapshot_id != first.evidence_snapshot_id
    assert second.repair_reason == "source_change_reanalysis"
    assert first_path.read_bytes() == frozen_parent_bytes


def test_existing_validation_with_old_evidence_digest_is_stale(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text("def encode(features):\n    return features\n", encoding="utf-8")
    repo = build_repo_snapshot(tmp_path)
    evidence = build_evidence_snapshot_v2(_raw(tmp_path), repo)
    evidence_path = tmp_path / "evidence_v2.json"
    write_evidence_snapshot_v2(evidence_path, evidence)
    validation = tmp_path / "validation.json"
    validation.write_text(
        '{"repo_snapshot_id":"%s","project_tree_hash":"%s",'
        '"evidence_snapshot_id":"%s","evidence_snapshot_digest":"old"}'
        % (repo.snapshot_id, repo.project_tree_hash, evidence.evidence_snapshot_id),
        encoding="utf-8",
    )
    trace = tmp_path / "trace.json"
    trace.write_text("{}", encoding="utf-8")

    report = check_artifact_freshness(
        repo_snapshot=repo,
        evidence_snapshot=evidence,
        artifacts={
            "evidence_snapshot_v2": str(evidence_path),
            "text_evidence_validation": str(validation),
            "final_text_trace": str(trace),
        },
    )

    validation_verdict = next(item for item in report.verdicts if item.artifact_key == "text_evidence_validation")
    assert "evidence_snapshot_digest_mismatch" in validation_verdict.failures
    assert "final_text_trace" in report.stale_artifact_keys


def test_repo_snapshot_records_dirty_git_identity(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Code2Paper Test"], check=True)
    source = tmp_path / "model.py"
    source.write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "model.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "baseline"], check=True)
    clean = build_repo_snapshot(tmp_path)
    source.write_text("value = 2\n", encoding="utf-8")
    dirty = build_repo_snapshot(tmp_path)

    assert clean.git_commit
    assert clean.git_dirty is False
    assert dirty.git_commit == clean.git_commit
    assert dirty.git_dirty is True
    assert dirty.project_tree_hash != clean.project_tree_hash


def test_langchain_freshness_tool_exposes_deterministic_hard_gate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    artifacts = tmp_path / "artifacts"
    project.mkdir()
    artifacts.mkdir()
    (project / "model.py").write_text("def encode(features):\n    return features\n", encoding="utf-8")
    repo = build_repo_snapshot(project)
    evidence = build_evidence_snapshot_v2(_raw(project), repo)
    repo_path = artifacts / "repo.json"
    evidence_path = artifacts / "evidence.json"
    report_path = artifacts / "freshness.json"
    write_repo_snapshot(repo_path, repo)
    write_evidence_snapshot_v2(evidence_path, evidence)

    tool = build_check_artifact_freshness_tool()
    result = tool.invoke(
        {
            "repo_snapshot_path": str(repo_path),
            "evidence_snapshot_path": str(evidence_path),
            "artifacts": {"evidence_snapshot_v2": str(evidence_path)},
            "report_path": str(report_path),
        }
    )

    assert tool.name == "check_artifact_freshness"
    assert tool.metadata["hard_gate"] is True
    assert result["status"] == "passed"
    assert report_path.exists()
