from __future__ import annotations

import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.figure_scene import FigureSceneGraph
from code2paper.rendering.figure_manifest import StructuredFigureManifest
from code2paper.rendering.scene_svg import file_sha256


class PostRenderAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "2.0"
    status: str
    scene_digest: str
    asset_digest: str
    expected_elements: int
    rendered_elements: int
    failures: list[str] = Field(default_factory=list)
    hard_gate_passed: bool


def audit_rendered_svg(scene: FigureSceneGraph, manifest: StructuredFigureManifest) -> PostRenderAudit:
    failures: list[str] = []
    asset = Path(manifest.asset_path)
    try:
        root = ET.parse(asset).getroot()
    except (OSError, ET.ParseError):
        return PostRenderAudit(status="failed", scene_digest=scene.content_digest, asset_digest="", expected_elements=len(scene.nodes)+len(scene.edges), rendered_elements=0, failures=["svg_unreadable"], hard_gate_passed=False)
    ns = "{http://www.w3.org/2000/svg}"
    metadata = root.find(f"{ns}metadata")
    try:
        meta_payload = json.loads(html.unescape(metadata.text or "")) if metadata is not None else {}
    except json.JSONDecodeError:
        meta_payload = {}
    if meta_payload.get("scene_digest") != scene.content_digest:
        failures.append("scene_digest_metadata_mismatch")
    digest = file_sha256(asset)
    if digest != manifest.asset_digest:
        failures.append("asset_digest_mismatch")
    elements = {item.get("id", ""): item for item in root.iter() if item.get("data-scene-element")}
    parents = {child: parent for parent in root.iter() for child in parent}
    def scene_ancestor(element):
        current = element
        while current in parents:
            current = parents[current]
            if current.get("data-scene-element"):
                return current
        return None
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1]
        if local_name == "line":
            owner = scene_ancestor(element)
            if owner is None or owner.get("data-scene-element") != "edge":
                failures.append("extra_uncontracted_arrow")
        if local_name == "text" and scene_ancestor(element) is None:
            failures.append("extra_uncontracted_label")
    expected_ids = {item.element_id for item in [*scene.nodes, *scene.edges, *scene.annotations]}
    if set(elements) != expected_ids:
        for item in sorted(expected_ids - set(elements)): failures.append(f"missing_element:{item}")
        for item in sorted(set(elements) - expected_ids): failures.append(f"extra_element:{item}")
    for node in scene.nodes:
        element = elements.get(node.element_id)
        if element is None: continue
        text = "".join(element.itertext()).strip()
        if text != node.label: failures.append(f"node_label_mismatch:{node.element_id}")
        if element.get("data-stage-id") != node.stage_id: failures.append(f"node_stage_mismatch:{node.element_id}")
    for edge in scene.edges:
        element = elements.get(edge.element_id)
        if element is None: continue
        if element.get("data-relation-id") != edge.relation_id: failures.append(f"edge_relation_mismatch:{edge.element_id}")
        if element.get("data-source") != edge.source_element_id or element.get("data-target") != edge.target_element_id:
            failures.append(f"edge_endpoint_mismatch:{edge.element_id}")
        if "".join(element.itertext()).strip() != edge.label: failures.append(f"edge_label_mismatch:{edge.element_id}")
    passed = not failures
    return PostRenderAudit(status="passed" if passed else "failed", scene_digest=scene.content_digest, asset_digest=digest, expected_elements=len(expected_ids), rendered_elements=len(elements), failures=failures, hard_gate_passed=passed)


def write_post_render_audit(path: str | Path, audit: PostRenderAudit) -> Path:
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(audit.model_dump_json(indent=2), encoding="utf-8"); return output
