from __future__ import annotations

from pathlib import Path
import re

from code2paper.agentic.evidence_relations_v2 import build_evidence_relations_v2
from code2paper.agentic.evidence_v2 import build_evidence_snapshot_v2
from code2paper.agentic.figure_planner import build_evidence_backed_figure_plan, figure_plan_trace
from code2paper.agentic.figure_relation_validator import validate_figure_relations
from code2paper.agentic.figure_scene import build_figure_scene_graph
from code2paper.agentic.post_render_audit import audit_rendered_svg
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.contracts import AgenticRunState, StageStatus
from code2paper.agentic.legacy_late_stage_tools import run_rendering
from code2paper.agentic.figure_scene import write_figure_scene_graph
from code2paper.rendering.figure_manifest import build_figure_manifest
from code2paper.rendering.scene_svg import render_scene_svg
from code2paper.core.schemas import (
    ClaimEvidenceItem, ClaimEvidenceMap, EvidenceItem, Mechanism, MethodEvidence,
    MethodStageEvidence, RawEvidencePack, SourceType, SupportStatus,
)


def _fixture(tmp_path: Path):
    (tmp_path / "config.yaml").write_text("trainer:\n  epochs: 2\n", encoding="utf-8")
    (tmp_path / "train.py").write_text("def main():\n    pass\n", encoding="utf-8")
    (tmp_path / "run.sh").write_text("python train.py --config config.yaml\n", encoding="utf-8")
    raw = RawEvidencePack(project_id="p2", project_root=str(tmp_path), evidence_items=[
        EvidenceItem(evidence_id="EC", source_type=SourceType.CONFIG, path="config.yaml", symbol="trainer", line_start=1, line_end=2, content_summary="trainer config", confidence=.9),
        EvidenceItem(evidence_id="ES", source_type=SourceType.SOURCE, path="train.py", symbol="main", line_start=1, line_end=2, content_summary="entrypoint", confidence=.9),
        EvidenceItem(evidence_id="EH", source_type=SourceType.BASH, path="run.sh", line_start=1, line_end=1, content_summary="shell invokes train with config", confidence=.9),
    ])
    method = MethodEvidence(project_id="p2", method_name="P2", method_goal="show flow", implementation_scope="test", stages=[
        MethodStageEvidence(stage_id="S1", name="Configuration", purpose="Configure training", mechanisms=[Mechanism(mechanism_id="MECH1", description="Trainer configuration", support_status=SupportStatus.SUPPORTED, evidence_ids=["EC"])]),
        MethodStageEvidence(stage_id="S2", name="Training", purpose="Run training", mechanisms=[Mechanism(mechanism_id="MECH2", description="Training entrypoint", support_status=SupportStatus.SUPPORTED, evidence_ids=["ES"])]),
    ])
    claims = ClaimEvidenceMap(claims=[
        ClaimEvidenceItem(claim_id="C1", claim_text="The configuration defines trainer settings.", support_status=SupportStatus.SUPPORTED, evidence_ids=["EC"], mechanism_ids=["MECH1"]),
        ClaimEvidenceItem(claim_id="C2", claim_text="The training entrypoint defines main.", support_status=SupportStatus.SUPPORTED, evidence_ids=["ES"], mechanism_ids=["MECH2"]),
    ])
    evidence = build_evidence_snapshot_v2(raw, build_repo_snapshot(tmp_path))
    return method, claims, evidence


def test_node_evidence_union_does_not_create_relation_edge(tmp_path: Path) -> None:
    method, claims, _evidence = _fixture(tmp_path)
    plan = build_evidence_backed_figure_plan(method_evidence=method, claim_map=claims)
    assert len(plan.nodes) == 2
    assert plan.edges == []


def test_direct_shell_relation_builds_scene_edge(tmp_path: Path) -> None:
    method, claims, evidence = _fixture(tmp_path)
    relations = build_evidence_relations_v2(method, evidence)
    plan = build_evidence_backed_figure_plan(method_evidence=method, claim_map=claims, evidence_relations=relations)
    scene = build_figure_scene_graph(plan, relations)
    validation = validate_figure_relations(scene, relations, evidence)
    assert len(relations.relations) == 1
    assert plan.edges[0].evidence_ids == ["EH"]
    assert scene.edges[0].relation_id == relations.relations[0].relation_id
    assert validation.hard_gate_passed


def test_model_cannot_relabel_node_as_new_mechanism(tmp_path: Path) -> None:
    method, claims, evidence = _fixture(tmp_path)
    relations = build_evidence_relations_v2(method, evidence)
    plan, trace = figure_plan_trace(
        method_evidence=method, claim_map=claims, evidence_relations=relations,
        decision_provider=lambda _prompt: {"nodes": [{"node_id": "N1", "stage_id": "S1", "label": "Guaranteed causal optimizer", "evidence_ids": ["EC"]}], "edges": []},
    )
    assert plan.nodes[0].label == "Configuration"
    assert any("Rewrote" in note for note in trace.safety_notes)


def test_deterministic_svg_and_post_render_drift_detection(tmp_path: Path) -> None:
    project = tmp_path / "project"; project.mkdir()
    method, claims, evidence = _fixture(project)
    relations = build_evidence_relations_v2(method, evidence)
    scene = build_figure_scene_graph(build_evidence_backed_figure_plan(method_evidence=method, claim_map=claims, evidence_relations=relations), relations)
    first = render_scene_svg(scene, tmp_path / "first.svg")
    second = render_scene_svg(scene, tmp_path / "second.svg")
    assert first.read_bytes() == second.read_bytes()
    manifest = build_figure_manifest(scene_digest=scene.content_digest, asset_path=first)
    assert audit_rendered_svg(scene, manifest).hard_gate_passed

    tampered = first.read_text(encoding="utf-8").replace('data-target="scene-N2"', 'data-target="scene-N1"')
    first.write_text(tampered, encoding="utf-8")
    drift = audit_rendered_svg(scene, manifest)
    assert not drift.hard_gate_passed
    assert "asset_digest_mismatch" in drift.failures
    assert "edge_endpoint_mismatch:scene-edge-R1" in drift.failures


def test_formal_rendering_stage_emits_real_svg_and_passed_post_audit(tmp_path: Path) -> None:
    project = tmp_path / "project"; project.mkdir()
    method, claims, evidence = _fixture(project)
    relations = build_evidence_relations_v2(method, evidence)
    scene = build_figure_scene_graph(build_evidence_backed_figure_plan(method_evidence=method, claim_map=claims, evidence_relations=relations), relations)
    state = AgenticRunState(project_root=project, out_root=tmp_path / "out")
    scene_path = tmp_path / "scene.json"; write_figure_scene_graph(scene_path, scene)
    pre = tmp_path / "pre.json"; pre.write_text('{"hard_gate_passed":true}', encoding="utf-8")
    audit = tmp_path / "audit.json"; audit.write_text('{"passed":true,"blocking_failures":0}', encoding="utf-8")
    ledger = tmp_path / "ledger.json"; ledger.write_text('{"hard_gate_passed":true}', encoding="utf-8")
    text = state.method_root / "06_authoring" / "method_clean.md"; text.parent.mkdir(parents=True); text.write_text("# Method\n", encoding="utf-8")
    state = state.model_copy(update={"artifacts": {
        "repo_snapshot": str(tmp_path / "repo.json"), "figure_scene": str(scene_path), "pre_render_audit": str(pre),
        "agentic_invariant_audit": str(audit), "traceability_ledger": str(ledger),
        "figure_plan": str(tmp_path / "plan.json"), "figure_plan_decision_trace": str(tmp_path / "trace.json"),
    }})
    result = run_rendering(state)
    assert result.status == StageStatus.SUCCESS
    assert Path(result.artifacts["method_overview_svg"]).exists()
    assert Path(result.artifacts["post_render_audit"]).read_text(encoding="utf-8").find('"hard_gate_passed": true') >= 0


def test_post_render_detects_missing_extra_and_relabelled_elements(tmp_path: Path) -> None:
    project = tmp_path / "project"; project.mkdir()
    method, claims, evidence = _fixture(project)
    relations = build_evidence_relations_v2(method, evidence)
    scene = build_figure_scene_graph(build_evidence_backed_figure_plan(method_evidence=method, claim_map=claims, evidence_relations=relations), relations)
    original_path = render_scene_svg(scene, tmp_path / "base.svg")
    original = original_path.read_text(encoding="utf-8")

    variants = {
        "missing": re.sub(r'<g id="scene-N1".*?</g>\n', "", original, count=1, flags=re.S),
        "extra": original.replace("</svg>", '<g id="scene-extra" data-scene-element="node"><text>Invented</text></g>\n</svg>'),
        "relabel": original.replace(">Configuration</text>", ">Guaranteed optimizer</text>"),
        "metadata": original.replace(scene.content_digest, "sha256:wrong", 1),
        "extra_arrow": original.replace("</svg>", '<line x1="0" y1="0" x2="10" y2="10" marker-end="url(#arrow)"/>\n</svg>'),
        "extra_label": original.replace("</svg>", '<text x="1" y="1">Invented mechanism</text>\n</svg>'),
    }
    expected = {
        "missing": "missing_element:scene-N1", "extra": "extra_element:scene-extra",
        "relabel": "node_label_mismatch:scene-N1", "metadata": "scene_digest_metadata_mismatch",
        "extra_arrow": "extra_uncontracted_arrow", "extra_label": "extra_uncontracted_label",
    }
    for name, content in variants.items():
        path = tmp_path / f"{name}.svg"; path.write_text(content, encoding="utf-8")
        manifest = build_figure_manifest(scene_digest=scene.content_digest, asset_path=path)
        audit = audit_rendered_svg(scene, manifest)
        assert not audit.hard_gate_passed
        assert expected[name] in audit.failures
