from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_v2 import EvidenceSnapshotV2, validate_evidence_snapshot_round_trip
from code2paper.agentic.repo_snapshot import RepoSnapshot, build_repo_snapshot


class FreshnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactDependency(FreshnessModel):
    artifact_key: str
    path: str
    content_digest: str
    schema_version: str = ""
    producer_version: str = ""
    input_digests: dict[str, str] = Field(default_factory=dict)
    repo_snapshot_id: str = ""


class ArtifactFreshnessVerdict(FreshnessModel):
    artifact_key: str
    status: Literal["fresh", "stale", "missing", "unsupported_schema"]
    failures: list[str] = Field(default_factory=list)


class ArtifactFreshnessReport(FreshnessModel):
    schema_version: str = "2.0"
    status: Literal["passed", "failed"]
    repo_snapshot_id: str
    current_project_tree_hash: str
    expected_project_tree_hash: str
    source_drift: bool
    evidence_round_trip_failures: list[str] = Field(default_factory=list)
    verdicts: list[ArtifactFreshnessVerdict] = Field(default_factory=list)
    stale_artifact_keys: list[str] = Field(default_factory=list)
    recommended_route: str = ""


class CheckArtifactFreshnessInput(FreshnessModel):
    repo_snapshot_path: str
    evidence_snapshot_path: str
    artifacts: dict[str, str] = Field(default_factory=dict)
    report_path: str = ""


TRUST_DEPENDENCY_ORDER = (
    "evidence_snapshot_v2", "atomic_claims_v2", "claim_verification", "authoring_projection",
    "authoring_plan", "final_text_claims", "text_evidence_validation", "final_text_trace",
    "evidence_relations_v2", "figure_scene", "figure_relation_validation", "pre_render_audit",
    "rendering_manifest", "post_render_audit", "final_package",
)


def check_artifact_freshness(
    *,
    repo_snapshot: RepoSnapshot,
    evidence_snapshot: EvidenceSnapshotV2,
    artifacts: dict[str, str],
) -> ArtifactFreshnessReport:
    current = build_repo_snapshot(repo_snapshot.project_root)
    source_drift = current.project_tree_hash != repo_snapshot.project_tree_hash
    round_trip = validate_evidence_snapshot_round_trip(evidence_snapshot, current)
    verdicts: list[ArtifactFreshnessVerdict] = []
    upstream_stale = source_drift or bool(round_trip)
    stale_keys: list[str] = []
    for key in TRUST_DEPENDENCY_ORDER:
        path = artifacts.get(key, "")
        if not path or not Path(path).exists():
            verdicts.append(ArtifactFreshnessVerdict(artifact_key=key, status="missing", failures=["artifact_missing"]))
            continue
        failures: list[str] = []
        if upstream_stale:
            failures.append("upstream_repo_or_evidence_stale")
        failures.extend(_artifact_contract_failures(key, Path(path), repo_snapshot, evidence_snapshot, artifacts))
        if key == "evidence_snapshot_v2" and evidence_snapshot.project_tree_hash != repo_snapshot.project_tree_hash:
            failures.append("evidence_snapshot_repo_digest_mismatch")
        status = "stale" if failures else "fresh"
        verdicts.append(ArtifactFreshnessVerdict(artifact_key=key, status=status, failures=failures))
        if failures:
            stale_keys.append(key)
            upstream_stale = True
    return ArtifactFreshnessReport(
        status="failed" if source_drift or round_trip or stale_keys else "passed",
        repo_snapshot_id=repo_snapshot.snapshot_id,
        current_project_tree_hash=current.project_tree_hash,
        expected_project_tree_hash=repo_snapshot.project_tree_hash,
        source_drift=source_drift,
        evidence_round_trip_failures=round_trip,
        verdicts=verdicts,
        stale_artifact_keys=stale_keys,
        recommended_route=(
            "intake"
            if source_drift
            else "evidence"
            if round_trip
            else _repair_route(stale_keys)
        ),
    )


def write_artifact_freshness_report(path: str | Path, report: ArtifactFreshnessReport) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def artifact_content_digest(path: str | Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freshness_cache_key(
    *, repo_snapshot_id: str, producer_version: str, input_digests: dict[str, str]
) -> str:
    return _digest_json(
        {"repo_snapshot_id": repo_snapshot_id, "producer_version": producer_version, "input_digests": input_digests}
    )


def build_check_artifact_freshness_tool():
    """Expose the deterministic freshness gate as a LangChain StructuredTool."""

    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Install the agentic extra to export LangChain freshness tools.") from exc

    from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
    from code2paper.agentic.repo_snapshot import load_repo_snapshot

    def _run(
        repo_snapshot_path: str,
        evidence_snapshot_path: str,
        artifacts: dict[str, str],
        report_path: str = "",
    ) -> dict[str, Any]:
        report = check_artifact_freshness(
            repo_snapshot=load_repo_snapshot(repo_snapshot_path),
            evidence_snapshot=load_evidence_snapshot_v2(evidence_snapshot_path),
            artifacts=artifacts,
        )
        if report_path:
            write_artifact_freshness_report(report_path, report)
        return report.model_dump(mode="json")

    return StructuredTool.from_function(
        func=_run,
        name="check_artifact_freshness",
        description=(
            "Recompute the frozen repository identity and validate EvidenceSnapshotV2 plus all downstream "
            "trust-artifact digests. A failed result must route to intake/evidence repair, never finalize."
        ),
        args_schema=CheckArtifactFreshnessInput,
        metadata={"hard_gate": True, "evidence_policy": "validates_evidence", "producer_version": "code2paper-agentic-p1"},
    )


def _artifact_contract_failures(
    key: str,
    path: Path,
    repo: RepoSnapshot,
    evidence: EvidenceSnapshotV2,
    artifacts: dict[str, str],
) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["artifact_unreadable"]
    if not isinstance(payload, dict):
        return ["artifact_not_object"]
    failures: list[str] = []
    if key == "evidence_snapshot_v2":
        if payload.get("schema_version") != "2.0": failures.append("unsupported_schema")
        if payload.get("producer_version") != "code2paper-agentic-p1": failures.append("producer_version_not_accepted")
        if payload.get("repo_snapshot_id") != repo.snapshot_id: failures.append("repo_snapshot_id_mismatch")
        if payload.get("project_tree_hash") != repo.project_tree_hash: failures.append("project_tree_hash_mismatch")
        if payload.get("content_digest") != _digest_json(payload.get("spans", [])): failures.append("content_digest_mismatch")
    elif key == "atomic_claims_v2":
        if payload.get("schema_version") != "2.0": failures.append("unsupported_schema")
        if payload.get("producer_version") != "code2paper-agentic-p1": failures.append("producer_version_not_accepted")
        if payload.get("evidence_snapshot_id") != evidence.evidence_snapshot_id: failures.append("evidence_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_digest") != evidence.content_digest: failures.append("evidence_snapshot_digest_mismatch")
        if payload.get("content_digest") != _digest_json(payload.get("claims", [])): failures.append("content_digest_mismatch")
    elif key == "claim_verification":
        if payload.get("schema_version") != "2.0": failures.append("unsupported_schema")
        if payload.get("producer_version") != "code2paper-agentic-p1": failures.append("producer_version_not_accepted")
        if payload.get("repo_snapshot_id") != repo.snapshot_id: failures.append("repo_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_id") != evidence.evidence_snapshot_id: failures.append("evidence_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_digest") != evidence.content_digest: failures.append("evidence_snapshot_digest_mismatch")
        if not payload.get("verifier_input_digest"): failures.append("verifier_input_digest_missing")
    elif key == "authoring_projection":
        if payload.get("repo_snapshot_id") != repo.snapshot_id: failures.append("repo_snapshot_id_mismatch")
        if payload.get("project_tree_hash") != repo.project_tree_hash: failures.append("project_tree_hash_mismatch")
        if payload.get("evidence_snapshot_id") != evidence.evidence_snapshot_id: failures.append("evidence_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_digest") != evidence.content_digest: failures.append("evidence_snapshot_digest_mismatch")
    elif key == "authoring_plan":
        projection = _read_artifact_json(artifacts, "authoring_projection")
        if projection and payload.get("projection_digest") != projection.get("projection_digest"):
            failures.append("projection_digest_mismatch")
    elif key == "text_evidence_validation":
        projection = _read_artifact_json(artifacts, "authoring_projection")
        if projection and payload.get("projection_digest") != projection.get("projection_digest"):
            failures.append("projection_digest_mismatch")
        if payload.get("evidence_snapshot_id") != evidence.evidence_snapshot_id:
            failures.append("evidence_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_digest") != evidence.content_digest:
            failures.append("evidence_snapshot_digest_mismatch")
        if payload.get("repo_snapshot_id") != repo.snapshot_id:
            failures.append("repo_snapshot_id_mismatch")
        if payload.get("project_tree_hash") != repo.project_tree_hash:
            failures.append("project_tree_hash_mismatch")
    elif key == "final_text_trace":
        projection = _read_artifact_json(artifacts, "authoring_projection")
        validation = _read_artifact_json(artifacts, "text_evidence_validation")
        if projection and payload.get("projection_digest") != projection.get("projection_digest"):
            failures.append("projection_digest_mismatch")
        if validation and payload.get("validation_report_digest") != _digest_json(validation):
            failures.append("validation_report_digest_mismatch")
        if payload.get("repo_snapshot_id") != repo.snapshot_id:
            failures.append("repo_snapshot_id_mismatch")
        if payload.get("project_tree_hash") != repo.project_tree_hash:
            failures.append("project_tree_hash_mismatch")
        if payload.get("evidence_snapshot_id") != evidence.evidence_snapshot_id:
            failures.append("evidence_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_digest") != evidence.content_digest:
            failures.append("evidence_snapshot_digest_mismatch")
    elif key == "evidence_relations_v2":
        if payload.get("repo_snapshot_id") != repo.snapshot_id: failures.append("repo_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_id") != evidence.evidence_snapshot_id: failures.append("evidence_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_digest") != evidence.content_digest: failures.append("evidence_snapshot_digest_mismatch")
        if payload.get("content_digest") != _digest_json(payload.get("relations", [])): failures.append("content_digest_mismatch")
    elif key == "figure_scene":
        if payload.get("repo_snapshot_id") != repo.snapshot_id: failures.append("repo_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_id") != evidence.evidence_snapshot_id: failures.append("evidence_snapshot_id_mismatch")
        if payload.get("evidence_snapshot_digest") != evidence.content_digest: failures.append("evidence_snapshot_digest_mismatch")
        try:
            from code2paper.agentic.figure_scene import FigureSceneGraph, figure_scene_content_digest
            scene = FigureSceneGraph.model_validate(payload)
            actual_scene_digest = figure_scene_content_digest(
                nodes=scene.nodes, edges=scene.edges, annotations=scene.annotations, groups=scene.groups,
                omitted_elements=scene.omitted_elements, layout=scene.layout,
            )
            if scene.content_digest != actual_scene_digest: failures.append("content_digest_mismatch")
        except ValueError:
            failures.append("unsupported_schema")
        relations = _read_artifact_json(artifacts, "evidence_relations_v2")
        if relations and payload.get("relation_set_digest") != relations.get("content_digest"): failures.append("relation_set_digest_mismatch")
        if not payload.get("hard_gate_passed"): failures.append("scene_gate_failed")
    elif key in {"figure_relation_validation", "pre_render_audit"}:
        scene = _read_artifact_json(artifacts, "figure_scene")
        relations = _read_artifact_json(artifacts, "evidence_relations_v2")
        if not payload.get("hard_gate_passed"): failures.append("figure_relation_gate_failed")
        if scene and payload.get("scene_digest") != scene.get("content_digest"): failures.append("scene_digest_mismatch")
        if relations and payload.get("relation_set_digest") != relations.get("content_digest"): failures.append("relation_set_digest_mismatch")
    elif key == "rendering_manifest":
        scene = _read_artifact_json(artifacts, "figure_scene")
        if scene and payload.get("scene_digest") != scene.get("content_digest"): failures.append("scene_digest_mismatch")
        asset = str(payload.get("asset_path") or "")
        if not asset or not Path(asset).exists(): failures.append("rendered_asset_missing")
        elif payload.get("asset_digest") != artifact_content_digest(asset): failures.append("asset_digest_mismatch")
    elif key == "post_render_audit":
        scene = _read_artifact_json(artifacts, "figure_scene")
        manifest = _read_artifact_json(artifacts, "rendering_manifest")
        if not payload.get("hard_gate_passed"): failures.append("post_render_gate_failed")
        if scene and payload.get("scene_digest") != scene.get("content_digest"): failures.append("scene_digest_mismatch")
        if manifest and payload.get("asset_digest") != manifest.get("asset_digest"): failures.append("asset_digest_mismatch")
    return failures


def _read_artifact_json(artifacts: dict[str, str], key: str) -> dict[str, Any]:
    path = artifacts.get(key, "")
    if not path:
        return {}


def _repair_route(stale_keys: list[str]) -> str:
    if any(key in stale_keys for key in ("evidence_snapshot_v2", "atomic_claims_v2", "claim_verification")):
        return "evidence"
    if any(key in stale_keys for key in ("authoring_projection", "authoring_plan")):
        return "authoring_planner"
    if any(key in stale_keys for key in ("final_text_claims", "text_evidence_validation", "final_text_trace")):
        return "authoring"
    if any(key in stale_keys for key in (
        "evidence_relations_v2", "figure_scene", "figure_relation_validation", "pre_render_audit",
        "rendering_manifest", "post_render_audit",
    )):
        return "figure_planner"
    if "final_package" in stale_keys:
        return "finalize"
    return ""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _digest_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
