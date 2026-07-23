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
    "evidence_snapshot_v2", "evidence_packets_v3", "code_facts_v1", "atomic_claims_v3", "equation_claims_v1",
    "atomic_claims_v2", "claim_verification", "authoring_projection",
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
    elif key == "evidence_packets_v3":
        if payload.get("schema_version") != "3.0": failures.append("unsupported_schema")
        if payload.get("producer_version") != "code2paper-evidence-compiler-v3": failures.append("producer_version_not_accepted")
        if payload.get("repo_snapshot_id") != repo.snapshot_id: failures.append("repo_snapshot_id_mismatch")
        if payload.get("project_tree_hash") != repo.project_tree_hash: failures.append("project_tree_hash_mismatch")
        if payload.get("content_digest") != _digest_json(payload.get("packets", [])): failures.append("content_digest_mismatch")
    elif key == "code_facts_v1":
        packets = _read_artifact_json(artifacts, "evidence_packets_v3")
        if payload.get("schema_version") != "1.0": failures.append("unsupported_schema")
        if payload.get("repo_snapshot_id") != repo.snapshot_id: failures.append("repo_snapshot_id_mismatch")
        if payload.get("project_tree_hash") != repo.project_tree_hash: failures.append("project_tree_hash_mismatch")
        if packets and payload.get("evidence_packet_digest") != packets.get("content_digest"): failures.append("evidence_packet_digest_mismatch")
        if payload.get("content_digest") != _digest_json(payload.get("facts", [])): failures.append("content_digest_mismatch")
    elif key == "atomic_claims_v3":
        packets = _read_artifact_json(artifacts, "evidence_packets_v3")
        facts = _read_artifact_json(artifacts, "code_facts_v1")
        if payload.get("schema_version") != "3.0": failures.append("unsupported_schema")
        if payload.get("repo_snapshot_id") != repo.snapshot_id: failures.append("repo_snapshot_id_mismatch")
        if payload.get("project_tree_hash") != repo.project_tree_hash: failures.append("project_tree_hash_mismatch")
        if packets and payload.get("evidence_packet_digest") != packets.get("content_digest"): failures.append("evidence_packet_digest_mismatch")
        if facts and payload.get("code_fact_digest") != facts.get("content_digest"): failures.append("code_fact_digest_mismatch")
        # Semantic stage groups are part of AtomicClaimSetV3's authoritative
        # payload.  Obligation binding may update both claim bindings and stage
        # organization before the set is written; excluding the groups here
        # made a valid, freshly rebuilt claim set look stale and cascaded the
        # failure through every downstream artifact.
        expected = _digest_json({
            "claims": payload.get("claims", []),
            "explicit_code_gaps": payload.get("explicit_code_gaps", []),
            "semantic_stage_groups": payload.get("semantic_stage_groups", []),
        })
        if payload.get("content_digest") != expected: failures.append("content_digest_mismatch")
    elif key == "equation_claims_v1":
        facts = _read_artifact_json(artifacts, "code_facts_v1")
        if payload.get("schema_version") != "1.0": failures.append("unsupported_schema")
        if payload.get("repo_snapshot_id") != repo.snapshot_id: failures.append("repo_snapshot_id_mismatch")
        if payload.get("project_tree_hash") != repo.project_tree_hash: failures.append("project_tree_hash_mismatch")
        if facts and payload.get("code_fact_digest") != facts.get("content_digest"): failures.append("code_fact_digest_mismatch")
        if payload.get("content_digest") != _digest_json(payload.get("equations", [])): failures.append("content_digest_mismatch")
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
        source_digests = payload.get("source_digests") if isinstance(payload.get("source_digests"), dict) else {}
        for dependency_key, digest_key in (
            ("evidence_packets_v3", "evidence_packets_v3"),
            ("code_facts_v1", "code_facts_v1"),
            ("atomic_claims_v3", "atomic_claims_v3"),
            ("equation_claims_v1", "equation_claims_v1"),
        ):
            dependency = _read_artifact_json(artifacts, dependency_key)
            if dependency and source_digests.get(digest_key) != dependency.get("content_digest"):
                failures.append(f"{dependency_key}_digest_mismatch")
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
    if any(key in stale_keys for key in (
        "evidence_snapshot_v2", "evidence_packets_v3", "code_facts_v1",
        "atomic_claims_v3", "atomic_claims_v2", "claim_verification",
    )):
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


# ---------------------------------------------------------------------------
# V3 research-plane freshness (R0.4)
# ---------------------------------------------------------------------------


V3_TRUST_DEPENDENCY_ORDER: tuple[str, ...] = (
    "source_authority_classification_v1",
    "behavior_graph_v1",
    "tool_observations_v1",
    "research_agenda_v1",
    "research_decision_trace_v1",
    "quality_state_v2",
    "text_repair_issues_v1",
    # V3 research plane may also reference V2/V3 evidence artifacts compiled by
    # the generic compiler; reuse the V2 contract checks for those when an
    # evidence_snapshot is available.
    "evidence_packets_v3",
    "code_facts_v1",
    "atomic_claims_v3",
)


V3_ARTIFACT_SCHEMAS: dict[str, str] = {
    "source_authority_classification_v1": "1.0",
    "behavior_graph_v1": "1.0",
    "tool_observations_v1": "1.0",
    "research_agenda_v1": "1.0",
    "research_decision_trace_v1": "1.0",
    "quality_state_v2": "1.0",
    "text_repair_issues_v1": "1.0",
}


class ArtifactFreshnessVerdictV3(FreshnessModel):
    artifact_key: str
    status: Literal["fresh", "stale", "missing", "unsupported_schema", "out_of_scope"]
    failures: list[str] = Field(default_factory=list)


class ArtifactFreshnessReportV3(FreshnessModel):
    """Freshness report for the V3 research plane.

    The V3 plane does not require an ``EvidenceSnapshotV2``: facts are
    compiled from tool observations and the behavior graph.  When a V3 run
    also references V2 evidence artifacts (e.g. ``evidence_packets_v3``
    compiled by the generic compiler), the caller may pass an optional
    ``evidence_snapshot`` to enable cross-artifact digest checks.
    """

    schema_version: str = "3.0"
    status: Literal["passed", "failed"]
    repo_snapshot_id: str
    current_project_tree_hash: str
    expected_project_tree_hash: str
    source_drift: bool
    evidence_snapshot_id: str = ""
    evidence_round_trip_failures: list[str] = Field(default_factory=list)
    verdicts: list[ArtifactFreshnessVerdictV3] = Field(default_factory=list)
    stale_artifact_keys: list[str] = Field(default_factory=list)
    recommended_route: str = ""


def check_artifact_freshness_v3(
    *,
    repo_snapshot: RepoSnapshot,
    artifacts: dict[str, str],
    evidence_snapshot: EvidenceSnapshotV2 | None = None,
) -> ArtifactFreshnessReportV3:
    """V3 freshness gate for tool observations, behavior graph and agenda refs.

    R0.4 contract: artifact freshness must support tool observation sets and
    behavior graph references produced by the V3 research plane, without
    requiring the V2 ``EvidenceSnapshotV2`` that the legacy gate mandates.

    The function checks, for every V3 artifact key in
    ``V3_TRUST_DEPENDENCY_ORDER``:

    - the artifact file exists and is readable JSON;
    - ``schema_version`` matches the expected V3 schema;
    - ``repo_snapshot_id`` and ``project_tree_hash`` match the current repo
      snapshot (when the artifact records them);
    - ``content_digest`` matches the payload's actual digest (when the
      artifact records one).

    Cross-artifact digest checks (e.g. ``research_agenda_v1`` referencing
    ``intent_graph_digest``) are added incrementally in R1+; R0 only
    enforces the per-artifact invariants above so the contract is stable.
    """

    current = build_repo_snapshot(repo_snapshot.project_root)
    source_drift = current.project_tree_hash != repo_snapshot.project_tree_hash
    round_trip: list[str] = []
    if evidence_snapshot is not None:
        round_trip = validate_evidence_snapshot_round_trip(evidence_snapshot, current)
    verdicts: list[ArtifactFreshnessVerdictV3] = []
    stale_keys: list[str] = []
    upstream_stale = source_drift or bool(round_trip)
    for key in V3_TRUST_DEPENDENCY_ORDER:
        path = artifacts.get(key, "")
        if not path or not Path(path).exists():
            verdicts.append(ArtifactFreshnessVerdictV3(artifact_key=key, status="missing", failures=["artifact_missing"]))
            continue
        failures = _v3_artifact_contract_failures(key, Path(path), repo_snapshot, evidence_snapshot, artifacts)
        if upstream_stale:
            failures.append("upstream_repo_or_evidence_stale")
        status = "stale" if failures else "fresh"
        verdicts.append(ArtifactFreshnessVerdictV3(artifact_key=key, status=status, failures=failures))
        if failures:
            stale_keys.append(key)
            upstream_stale = True
    return ArtifactFreshnessReportV3(
        status="failed" if source_drift or round_trip or stale_keys else "passed",
        repo_snapshot_id=repo_snapshot.snapshot_id,
        current_project_tree_hash=current.project_tree_hash,
        expected_project_tree_hash=repo_snapshot.project_tree_hash,
        source_drift=source_drift,
        evidence_snapshot_id=evidence_snapshot.evidence_snapshot_id if evidence_snapshot else "",
        evidence_round_trip_failures=round_trip,
        verdicts=verdicts,
        stale_artifact_keys=stale_keys,
        recommended_route=_v3_repair_route(stale_keys),
    )


def write_artifact_freshness_report_v3(path: str | Path, report: ArtifactFreshnessReportV3) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _v3_artifact_contract_failures(
    key: str,
    path: Path,
    repo: RepoSnapshot,
    evidence: EvidenceSnapshotV2 | None,
    artifacts: dict[str, str],
) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["artifact_unreadable"]
    if not isinstance(payload, dict):
        return ["artifact_not_object"]
    failures: list[str] = []
    expected_schema = V3_ARTIFACT_SCHEMAS.get(key)
    if expected_schema:
        if str(payload.get("schema_version") or "") != expected_schema:
            failures.append("unsupported_schema")
    # repo_snapshot_id / project_tree_hash checks (when the artifact records them)
    if payload.get("repo_snapshot_id") and payload.get("repo_snapshot_id") != repo.snapshot_id:
        failures.append("repo_snapshot_id_mismatch")
    if payload.get("project_tree_hash") and payload.get("project_tree_hash") != repo.project_tree_hash:
        failures.append("project_tree_hash_mismatch")
    # content_digest check (when the artifact records one)
    content_digest = payload.get("content_digest")
    if content_digest:
        # Reconstruct the digestable payload by stripping the digest itself.
        digestable = {k: v for k, v in payload.items() if k != "content_digest"}
        actual = _digest_json(digestable)
        if content_digest != actual:
            failures.append("content_digest_mismatch")
    # V2-shared keys: delegate to the existing V2 contract checks when an
    # evidence_snapshot is available so cross-artifact digest relations are
    # honored for ``evidence_packets_v3`` / ``code_facts_v1`` / ``atomic_claims_v3``.
    if key in {"evidence_packets_v3", "code_facts_v1", "atomic_claims_v3"} and evidence is not None:
        v2_failures = _artifact_contract_failures(key, path, repo, evidence, artifacts)
        failures.extend(v2_failures)
    return failures


def _v3_repair_route(stale_keys: list[str]) -> str:
    if any(key in stale_keys for key in ("source_authority_classification_v1", "behavior_graph_v1")):
        return "repository_indexer"
    if any(key in stale_keys for key in ("tool_observations_v1", "research_agenda_v1", "research_decision_trace_v1")):
        return "research_supervisor"
    if any(key in stale_keys for key in ("quality_state_v2", "text_repair_issues_v1")):
        return "repair_supervisor"
    if any(key in stale_keys for key in ("evidence_packets_v3", "code_facts_v1", "atomic_claims_v3")):
        return "generic_fact_compiler"
    return ""


def _read_v3_artifact_json(artifacts: dict[str, str], key: str) -> dict[str, Any]:
    """Correct artifact reader for V3 freshness checks.

    R0 does not modify the legacy ``_read_artifact_json`` (which is a no-op
    for non-empty paths) to avoid changing V2 freshness behavior.  V3
    freshness uses this dedicated reader so cross-artifact digest checks
    actually execute.
    """

    path = artifacts.get(key, "")
    if not path:
        return {}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
