from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from code2paper.agentic.figure_scene import FigureSceneGraph


def render_scene_svg(scene: FigureSceneGraph, path: str | Path) -> Path:
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    width = max(640, 280 * max(1, len(scene.nodes)))
    height = 300
    node_positions = {node.element_id: (80 + index * 260, 105) for index, node in enumerate(scene.nodes)}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<metadata id="code2paper-scene-metadata">{html.escape(json.dumps({"scene_digest": scene.content_digest, "producer_version": scene.producer_version}, sort_keys=True))}</metadata>',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#334155"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
    ]
    for edge in scene.edges:
        sx, sy = node_positions[edge.source_element_id]; tx, ty = node_positions[edge.target_element_id]
        label = html.escape(edge.label)
        lines.extend([
            f'<g id="{html.escape(edge.element_id)}" data-scene-element="edge" data-relation-id="{html.escape(edge.relation_id)}" data-source="{html.escape(edge.source_element_id)}" data-target="{html.escape(edge.target_element_id)}">',
            f'<line x1="{sx + 180}" y1="{sy + 40}" x2="{tx}" y2="{ty + 40}" stroke="#334155" stroke-width="2" marker-end="url(#arrow)"/>',
            f'<text x="{(sx + tx + 180) // 2}" y="{sy + 25}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#475569">{label}</text>',
            '</g>',
        ])
    for node in scene.nodes:
        x, y = node_positions[node.element_id]
        claims = ",".join(node.claim_ids)
        evidence = ",".join(node.direct_evidence_ids)
        lines.extend([
            f'<g id="{html.escape(node.element_id)}" data-scene-element="node" data-stage-id="{html.escape(node.stage_id)}" data-claim-ids="{html.escape(claims)}" data-evidence-ids="{html.escape(evidence)}">',
            f'<rect x="{x}" y="{y}" width="180" height="80" rx="12" fill="#e0f2fe" stroke="#0369a1" stroke-width="2"/>',
            f'<text x="{x + 90}" y="{y + 45}" text-anchor="middle" font-family="sans-serif" font-size="15" fill="#0f172a">{html.escape(node.label)}</text>',
            '</g>',
        ])
    lines.append('</svg>')
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def file_sha256(path: str | Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
