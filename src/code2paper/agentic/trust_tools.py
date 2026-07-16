from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from code2paper.agentic.artifact_freshness import build_check_artifact_freshness_tool
from code2paper.agentic.atomic_claim_v2 import AtomicClaimSetV2
from code2paper.agentic.authoring_projection import build_authoring_projection, load_authoring_projection
from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.evidence_relations_v2 import build_evidence_relations_v2, load_evidence_relations_v2
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.figure_relation_validator import validate_figure_relations
from code2paper.agentic.figure_scene import load_figure_scene_graph
from code2paper.agentic.final_text_claims import extract_final_text_claims, load_final_text_claims
from code2paper.agentic.post_render_audit import audit_rendered_svg
from code2paper.agentic.text_evidence_validator import load_text_evidence_validation, validate_text_evidence
from code2paper.agentic.text_trace_builder import build_final_text_trace
from code2paper.agentic.tool_runtime import FineGrainedToolContract, atomic_write_json
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence, RawEvidencePack
from code2paper.rendering.figure_manifest import StructuredFigureManifest, build_figure_manifest
from code2paper.rendering.scene_svg import render_scene_svg


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrustToolManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.0"
    producer_version: str = "code2paper-agentic-p3"
    tools: list[FineGrainedToolContract]


class ProjectionInput(ToolInput):
    method_evidence_path: str
    claim_map_path: str
    verification_path: str
    raw_evidence_path: str
    evidence_snapshot_path: str
    atomic_claims_path: str
    output_path: str


class ExtractClaimsInput(ToolInput):
    text_path: str
    projection_path: str
    output_path: str


class ValidateClaimsInput(ToolInput):
    final_claims_path: str
    projection_path: str
    raw_evidence_path: str
    evidence_snapshot_path: str
    output_path: str


class TextTraceInput(ToolInput):
    final_claims_path: str
    validation_path: str
    projection_path: str
    output_path: str


class EvidenceRelationInput(ToolInput):
    method_evidence_path: str
    evidence_snapshot_path: str
    output_path: str
    code_graph_path: str = ""


class FigureRelationInput(ToolInput):
    scene_path: str
    relations_path: str
    evidence_snapshot_path: str
    output_path: str


class RenderFigureInput(ToolInput):
    scene_path: str
    asset_path: str
    manifest_path: str


class ValidateRenderedFigureInput(ToolInput):
    scene_path: str
    manifest_path: str
    output_path: str


def build_trust_tools() -> list[Any]:
    """Export P0-P2 trust-plane capabilities as file-oriented StructuredTools."""

    from langchain_core.tools import StructuredTool

    contracts = {item.name: item for item in build_trust_tool_contracts()}

    def projection(**kwargs):
        args = ProjectionInput.model_validate(kwargs)
        result = build_authoring_projection(
            method_evidence=_load(MethodEvidence, args.method_evidence_path),
            claim_map=_load(ClaimEvidenceMap, args.claim_map_path),
            verification=_load(ClaimVerificationReport, args.verification_path),
            raw_evidence=_load(RawEvidencePack, args.raw_evidence_path),
            evidence_snapshot_v2=load_evidence_snapshot_v2(args.evidence_snapshot_path),
            atomic_claims_v2=_load(AtomicClaimSetV2, args.atomic_claims_path),
        )
        atomic_write_json(args.output_path, result); return result.model_dump(mode="json")

    def extract(**kwargs):
        args = ExtractClaimsInput.model_validate(kwargs)
        result = extract_final_text_claims(Path(args.text_path).read_text(encoding="utf-8"), load_authoring_projection(args.projection_path))
        atomic_write_json(args.output_path, result); return result.model_dump(mode="json")

    def validate(**kwargs):
        args = ValidateClaimsInput.model_validate(kwargs)
        result = validate_text_evidence(
            final_claims=load_final_text_claims(args.final_claims_path),
            projection=load_authoring_projection(args.projection_path),
            raw_evidence=_load(RawEvidencePack, args.raw_evidence_path),
            evidence_snapshot_v2=load_evidence_snapshot_v2(args.evidence_snapshot_path),
        )
        atomic_write_json(args.output_path, result); return result.model_dump(mode="json")

    def trace(**kwargs):
        args = TextTraceInput.model_validate(kwargs)
        result = build_final_text_trace(
            final_claims=load_final_text_claims(args.final_claims_path), validation=load_text_evidence_validation(args.validation_path),
            projection=load_authoring_projection(args.projection_path), validator_report_ref=args.validation_path,
            projection_ref=args.projection_path,
        )
        atomic_write_json(args.output_path, result); return result.model_dump(mode="json")

    def relations(**kwargs):
        args = EvidenceRelationInput.model_validate(kwargs)
        graph = json.loads(Path(args.code_graph_path).read_text(encoding="utf-8")) if args.code_graph_path else None
        result = build_evidence_relations_v2(_load(MethodEvidence, args.method_evidence_path), load_evidence_snapshot_v2(args.evidence_snapshot_path), code_graph=graph)
        atomic_write_json(args.output_path, result); return result.model_dump(mode="json")

    def validate_relations(**kwargs):
        args = FigureRelationInput.model_validate(kwargs)
        result = validate_figure_relations(load_figure_scene_graph(args.scene_path), load_evidence_relations_v2(args.relations_path), load_evidence_snapshot_v2(args.evidence_snapshot_path))
        atomic_write_json(args.output_path, result); return result.model_dump(mode="json")

    def render(**kwargs):
        args = RenderFigureInput.model_validate(kwargs); scene = load_figure_scene_graph(args.scene_path)
        target = Path(args.asset_path); target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".svg", dir=target.parent); os.close(descriptor)
        try:
            render_scene_svg(scene, temporary); os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True); raise
        manifest = build_figure_manifest(scene_digest=scene.content_digest, asset_path=target)
        atomic_write_json(args.manifest_path, manifest); return manifest.model_dump(mode="json")

    def audit(**kwargs):
        args = ValidateRenderedFigureInput.model_validate(kwargs)
        result = audit_rendered_svg(load_figure_scene_graph(args.scene_path), _load(StructuredFigureManifest, args.manifest_path))
        atomic_write_json(args.output_path, result); return result.model_dump(mode="json")

    definitions = [
        ("build_authoring_projection", projection, ProjectionInput),
        ("extract_final_text_claims", extract, ExtractClaimsInput),
        ("validate_claim_against_evidence", validate, ValidateClaimsInput),
        ("build_text_trace", trace, TextTraceInput),
        ("build_evidence_relation", relations, EvidenceRelationInput),
        ("validate_figure_relation", validate_relations, FigureRelationInput),
        ("render_structured_figure", render, RenderFigureInput),
        ("validate_rendered_figure", audit, ValidateRenderedFigureInput),
    ]
    tools = [StructuredTool.from_function(func=fn, name=name, description=_description(contracts[name]), args_schema=schema, metadata=contracts[name].model_dump(mode="json")) for name, fn, schema in definitions]
    tools.insert(4, build_check_artifact_freshness_tool())
    return tools


def build_trust_tool_contracts() -> list[FineGrainedToolContract]:
    rows = [
        ("build_authoring_projection", "ProjectionInput", "AuthoringInputProjection", ["method_evidence", "claim_verification", "evidence_snapshot_v2"], "consumes_frozen_evidence", False, "repair evidence or projection inputs"),
        ("extract_final_text_claims", "ExtractClaimsInput", "FinalTextClaims", ["final_text", "authoring_projection"], "analyzes_evidence", False, "repair claim extraction completeness"),
        ("validate_claim_against_evidence", "ValidateClaimsInput", "TextEvidenceValidationReport", ["final_text_claims", "evidence_snapshot_v2"], "validates_evidence", True, "rewrite claim or request direct evidence"),
        ("build_text_trace", "TextTraceInput", "FinalTextTrace", ["passed_text_validation"], "validates_evidence", True, "return to text validation"),
        ("check_artifact_freshness", "CheckArtifactFreshnessInput", "ArtifactFreshnessReport", ["repo_snapshot", "evidence_snapshot_v2"], "validates_evidence", True, "route to reported producer"),
        ("build_evidence_relation", "EvidenceRelationInput", "EvidenceRelationSetV2", ["method_evidence", "evidence_snapshot_v2"], "consumes_frozen_evidence", False, "omit unsupported relation or gather evidence"),
        ("validate_figure_relation", "FigureRelationInput", "FigureRelationValidation", ["figure_scene", "evidence_relations_v2"], "validates_evidence", True, "repair relation or omit edge"),
        ("render_structured_figure", "RenderFigureInput", "StructuredFigureManifest", ["passed_pre_render_audit", "figure_scene"], "consumes_frozen_evidence", True, "retry deterministic renderer"),
        ("validate_rendered_figure", "ValidateRenderedFigureInput", "PostRenderAudit", ["rendering_manifest", "figure_scene"], "validates_evidence", True, "rerender from unchanged scene"),
    ]
    return [FineGrainedToolContract(name=name, input_schema=input_schema, output_schema=output_schema, artifact_requirements=requirements, evidence_policy=policy, side_effects=["atomic_artifact_write"], idempotency_fields=["producer_version", "repo_snapshot_id", "input_digests", "model_profile", "configuration", "schema_version"], hard_failure="schema_or_gate_failure", safe_recovery=recovery, hard_gate=gate) for name, input_schema, output_schema, requirements, policy, gate, recovery in rows]


def write_trust_tool_manifest(path: str | Path) -> Path:
    return atomic_write_json(path, TrustToolManifest(tools=build_trust_tool_contracts()))


def _load(model, path: str):
    return model.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _description(contract: FineGrainedToolContract) -> str:
    return f"{contract.name}: evidence_policy={contract.evidence_policy}; failure={contract.hard_failure}; recovery={contract.safe_recovery}."
