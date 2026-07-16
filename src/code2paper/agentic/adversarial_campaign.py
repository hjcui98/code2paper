from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.artifact_freshness import check_artifact_freshness
from code2paper.agentic.benchmark_v2 import BenchmarkCaseV2
from code2paper.agentic.evidence_relations_v2 import EvidenceRelationSetV2
from code2paper.agentic.evidence_v2 import build_evidence_snapshot_v2
from code2paper.agentic.figure_relation_validator import validate_figure_relations
from code2paper.agentic.figure_scene import (
    FigureSceneEdge,
    FigureSceneGraph,
    FigureSceneNode,
    figure_scene_content_digest,
)
from code2paper.agentic.final_text_claims import extract_final_text_claims
from code2paper.agentic.post_render_audit import audit_rendered_svg
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.text_evidence_validator import validate_text_evidence
from code2paper.agentic.trust_contracts import AuthoringInputProjection, ProjectedClaim
from code2paper.core.schemas import EvidenceItem, RawEvidencePack, SourceType
from code2paper.rendering.figure_manifest import build_figure_manifest
from code2paper.rendering.scene_svg import render_scene_svg


class CampaignModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MutationTrialResultV2(CampaignModel):
    schema_version: str = "2.0"
    case_id: str
    mutation_id: str
    category: str
    expected_outcome: str
    candidate_text: str
    detected: bool
    validator: str
    failures: list[str] = Field(default_factory=list)
    gold_evidence_digests: list[str] = Field(default_factory=list)


def run_adversarial_campaign_v2(case: BenchmarkCaseV2, *, workspace_root: str | Path, out_root: str | Path) -> list[Path]:
    root = Path(workspace_root).resolve()
    output = Path(out_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    project, raw, projection, evidence_id_map = _materialize_case(case, root, output / "fixture")
    results: list[Path] = []
    for mutation in case.mutations:
        if mutation.category in {
            "legal_id_mismatch", "unsupported_paraphrase", "relevance_exaggeration",
            "causal_strengthening", "numeric_injection", "formula_injection",
        }:
            result = _text_trial(case, mutation, raw, projection)
        elif mutation.category == "figure_edge_pseudoevidence":
            result = _figure_edge_trial(case, mutation, raw, project, evidence_id_map)
        elif mutation.category == "post_render_drift":
            result = _post_render_trial(case, mutation, raw, project, output)
        elif mutation.category == "source_stale":
            result = _source_stale_trial(case, mutation, raw, project)
        elif mutation.category == "artifact_stale":
            result = _artifact_stale_trial(case, mutation, raw, project, output)
        else:  # pragma: no cover - schema prevents this branch
            raise ValueError(f"unsupported mutation category:{mutation.category}")
        path = output / f"{mutation.mutation_id}.json"
        path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
        results.append(path)
    return results


def _materialize_case(case: BenchmarkCaseV2, root: Path, fixture: Path):
    fixture.mkdir(parents=True, exist_ok=True)
    source_repo = (root / case.repo_root).resolve()
    items: list[EvidenceItem] = []
    evidence_id_map: dict[str, str] = {}
    for index, span in enumerate(case.evidence_spans, start=1):
        source = source_repo / span.path
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        excerpt = "".join(lines[span.line_start - 1:span.line_end])
        target = fixture / "gold_spans" / f"{span.evidence_id}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(excerpt, encoding="utf-8")
        evidence_id = f"E{index}"
        evidence_id_map[span.evidence_id] = evidence_id
        items.append(EvidenceItem(
            evidence_id=evidence_id, source_type=SourceType.SOURCE, path=target.relative_to(fixture).as_posix(),
            line_start=1, line_end=max(1, len(excerpt.splitlines())), content_summary=excerpt,
            confidence=1.0,
        ))
    raw = RawEvidencePack(project_id=case.case_id, project_root=str(fixture), evidence_items=items)
    claims = [ProjectedClaim(
        claim_id=item.claim_id,
        claim_text=item.text,
        support_status="partial" if item.required_qualifiers else "supported",
        direct_evidence_ids=[evidence_id_map[key] for key in item.direct_evidence_ids],
        supported_fragment=item.text,
        required_qualifiers=item.required_qualifiers,
        allowed_wording_boundary=item.text,
        input_digest="sha256:" + hashlib.sha256(item.text.encode()).hexdigest(),
    ) for item in case.supported_claims]
    projection = AuthoringInputProjection(
        project_id=case.case_id, method_name=case.case_id, author_goal="adversarial validation",
        implementation_scope="curated P4 mutation", projected_claims=claims,
        projection_digest="sha256:" + hashlib.sha256(case.case_id.encode()).hexdigest(),
    )
    return fixture, raw, projection, evidence_id_map


def _text_trial(case, mutation, raw, projection) -> MutationTrialResultV2:
    extracted = extract_final_text_claims(mutation.candidate_text, projection)
    report = validate_text_evidence(final_claims=extracted, projection=projection, raw_evidence=raw)
    failures = sorted({failure for verdict in report.verdicts for failure in verdict.deterministic_failures})
    return _result(case, mutation, detected=report.status == "failed", validator="text_evidence_validator", failures=failures)


def _figure_edge_trial(case, mutation, raw, project, evidence_id_map) -> MutationTrialResultV2:
    evidence = build_evidence_snapshot_v2(raw, build_repo_snapshot(project))
    relations = EvidenceRelationSetV2(
        repo_snapshot_id=evidence.repo_snapshot_id, evidence_snapshot_id=evidence.evidence_snapshot_id,
        evidence_snapshot_digest=evidence.content_digest, relations=[], content_digest="sha256:empty-relations",
    )
    nodes = [FigureSceneNode(
        element_id=f"scene-N{index}", stage_id=f"S{index}", label=claim.text,
        claim_ids=[claim.claim_id],
        direct_evidence_ids=[evidence_id_map[key] for key in claim.direct_evidence_ids],
        visible_text_boundary=claim.text,
    ) for index, claim in enumerate(case.supported_claims[:2], start=1)]
    if len(nodes) == 1:
        nodes.append(nodes[0].model_copy(update={"element_id": "scene-N2", "stage_id": "S2"}))
    edge = FigureSceneEdge(
        element_id="scene-edge-mutated", relation_id="MUTATED", source_element_id=nodes[0].element_id,
        target_element_id=nodes[1].element_id, label=mutation.candidate_text,
        direct_evidence_ids=sorted({eid for node in nodes for eid in node.direct_evidence_ids}),
        visible_text_boundary=mutation.candidate_text,
    )
    digest = figure_scene_content_digest(nodes=nodes, edges=[edge], annotations=[], groups=[], omitted_elements=[], layout="left_to_right")
    scene = FigureSceneGraph(
        repo_snapshot_id=evidence.repo_snapshot_id, evidence_snapshot_id=evidence.evidence_snapshot_id,
        evidence_snapshot_digest=evidence.content_digest, relation_set_digest=relations.content_digest,
        nodes=nodes, edges=[edge], content_digest=digest,
    )
    report = validate_figure_relations(scene, relations, evidence)
    return _result(case, mutation, detected=not report.hard_gate_passed, validator="figure_relation_validator", failures=report.failures)


def _post_render_trial(case, mutation, raw, project, output) -> MutationTrialResultV2:
    evidence = build_evidence_snapshot_v2(raw, build_repo_snapshot(project))
    claim = case.supported_claims[0]
    node = FigureSceneNode(
        element_id="scene-N1", stage_id="S1", label=claim.text, claim_ids=[claim.claim_id],
        direct_evidence_ids=[raw.evidence_items[0].evidence_id], visible_text_boundary=claim.text,
    )
    digest = figure_scene_content_digest(nodes=[node], edges=[], annotations=[], groups=[], omitted_elements=[], layout="left_to_right")
    scene = FigureSceneGraph(
        repo_snapshot_id=evidence.repo_snapshot_id, evidence_snapshot_id=evidence.evidence_snapshot_id,
        evidence_snapshot_digest=evidence.content_digest, relation_set_digest="sha256:none",
        nodes=[node], content_digest=digest,
    )
    asset = render_scene_svg(scene, output / f"{mutation.mutation_id}.svg")
    manifest = build_figure_manifest(scene_digest=scene.content_digest, asset_path=asset)
    asset.write_text(asset.read_text(encoding="utf-8").replace("</svg>", f'<text x="1" y="1">{mutation.candidate_text}</text></svg>'), encoding="utf-8")
    report = audit_rendered_svg(scene, manifest)
    return _result(case, mutation, detected=not report.hard_gate_passed, validator="post_render_audit", failures=report.failures)


def _source_stale_trial(case, mutation, raw, project) -> MutationTrialResultV2:
    snapshot = build_repo_snapshot(project)
    evidence = build_evidence_snapshot_v2(raw, snapshot)
    target = project / raw.evidence_items[0].path
    target.write_text(target.read_text(encoding="utf-8") + "\n# P4 source mutation\n", encoding="utf-8")
    report = check_artifact_freshness(repo_snapshot=snapshot, evidence_snapshot=evidence, artifacts={})
    failures = (["source_drift"] if report.source_drift else []) + report.evidence_round_trip_failures
    return _result(case, mutation, detected=report.status == "failed", validator="artifact_freshness", failures=failures)


def _artifact_stale_trial(case, mutation, raw, project, output) -> MutationTrialResultV2:
    snapshot = build_repo_snapshot(project)
    evidence = build_evidence_snapshot_v2(raw, snapshot)
    validation = output / f"{mutation.mutation_id}-stale-validation.json"
    validation.write_text(json.dumps({
        "repo_snapshot_id": snapshot.snapshot_id, "project_tree_hash": snapshot.project_tree_hash,
        "evidence_snapshot_id": evidence.evidence_snapshot_id, "evidence_snapshot_digest": "sha256:stale",
    }), encoding="utf-8")
    report = check_artifact_freshness(
        repo_snapshot=snapshot, evidence_snapshot=evidence,
        artifacts={"text_evidence_validation": str(validation)},
    )
    verdict = next(item for item in report.verdicts if item.artifact_key == "text_evidence_validation")
    return _result(case, mutation, detected=verdict.status == "stale", validator="artifact_freshness", failures=verdict.failures)


def _result(case, mutation, *, detected: bool, validator: str, failures: list[str]) -> MutationTrialResultV2:
    return MutationTrialResultV2(
        case_id=case.case_id, mutation_id=mutation.mutation_id, category=mutation.category,
        expected_outcome=mutation.expected_outcome, candidate_text=mutation.candidate_text,
        detected=detected, validator=validator, failures=failures,
        gold_evidence_digests=[item.exact_excerpt_digest for item in case.evidence_spans],
    )
