from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.adversarial_campaign import _materialize_case
from code2paper.agentic.benchmark_v2 import BenchmarkCaseV2
from code2paper.agentic.final_text_claims import extract_final_text_claims
from code2paper.agentic.text_evidence_validator import validate_text_evidence


class LegacyAuditModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LegacyV2AuditReport(LegacyAuditModel):
    schema_version: str = "2.0"
    case_id: str
    legacy_run_report_digest: str
    legacy_fidelity_passed: bool
    draft_digest: str
    claim_inventory: list[dict] = Field(default_factory=list)
    factual_claims: int
    supported_claims: int
    caveated_claims: int
    unsupported_claims: int
    text_v2_gate_passed: bool
    figure_asset_present: bool
    figure_asset_digest: str = ""
    figure_inventory: list[dict] = Field(default_factory=list)
    figure_v2_relation_lineage_present: bool = False
    figure_v2_post_render_audit_present: bool = False
    v2_usable_completion: bool = False
    legacy_false_success_candidate: bool
    requires_named_human_review: bool = True
    failures: list[str] = Field(default_factory=list)


def audit_legacy_run_against_gold_v2(
    case: BenchmarkCaseV2,
    *,
    workspace_root: str | Path,
    legacy_out_root: str | Path,
    scratch_root: str | Path,
) -> LegacyV2AuditReport:
    legacy = Path(legacy_out_root).resolve()
    report_path = legacy / "paper/method/code2paper_run_report.json"
    draft_path = legacy / "paper/method/method_draft.md"
    figure_path = legacy / "paper/figures/method_overview/method_overview.svg"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    text = draft_path.read_text(encoding="utf-8")
    _project, raw, projection, _mapping = _materialize_case(
        case, Path(workspace_root).resolve(), Path(scratch_root).resolve() / case.case_id,
    )
    claims = extract_final_text_claims(text, projection)
    validation = validate_text_evidence(final_claims=claims, projection=projection, raw_evidence=raw)
    verdicts = {item.atomic_claim_id: item for item in validation.verdicts}
    claim_inventory = [
        {
            "atomic_claim_id": item.atomic_claim_id,
            "text": item.text,
            "claim_digest": item.claim_digest,
            "verdict": verdicts[item.atomic_claim_id].status,
            "direct_evidence_ids": verdicts[item.atomic_claim_id].direct_evidence_ids,
            "high_risk": bool(item.high_risk_markers),
        }
        for item in claims.atomic_claims
    ]
    figure_digest = _digest(figure_path) if figure_path.is_file() else ""
    figure_inventory = _visible_svg_inventory(figure_path, figure_digest) if figure_digest else []
    failures: list[str] = []
    if validation.status != "passed":
        failures.append("legacy_text_fails_curated_v2_semantic_gate")
    if not figure_path.is_file():
        failures.append("legacy_figure_asset_missing")
    failures.extend([
        "legacy_figure_has_no_v2_relation_lineage",
        "legacy_figure_has_no_v2_post_render_audit",
        "legacy_output_has_no_authoritative_v2_final_invariant",
    ])
    usable = validation.status == "passed" and not failures
    legacy_passed = bool(report.get("fidelity_passed"))
    return LegacyV2AuditReport(
        case_id=case.case_id,
        legacy_run_report_digest=_digest(report_path),
        legacy_fidelity_passed=legacy_passed,
        draft_digest=_digest(draft_path),
        claim_inventory=claim_inventory,
        factual_claims=validation.checked_factual_claims,
        supported_claims=validation.supported_claims,
        caveated_claims=validation.caveated_claims,
        unsupported_claims=validation.unsupported_claims,
        text_v2_gate_passed=validation.status == "passed",
        figure_asset_present=figure_path.is_file(),
        figure_asset_digest=figure_digest,
        figure_inventory=figure_inventory,
        v2_usable_completion=usable,
        legacy_false_success_candidate=legacy_passed and not usable,
        failures=failures,
    )


def write_legacy_v2_audit(path: str | Path, report: LegacyV2AuditReport) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _visible_svg_inventory(path: Path, svg_digest: str) -> list[dict]:
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"legacy method figure is not valid SVG:{path}") from exc
    inventory: list[dict] = []
    text_elements = list(item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "text")
    for index, element in enumerate(
        text_elements,
        start=1,
    ):
        label = " ".join("".join(element.itertext()).split())
        if not label:
            continue
        element_id = f"legacy-svg-text-{index}"
        element_kind = "annotation"
        payload = json.dumps(
            {
                "element_id": element_id,
                "element_kind": element_kind,
                "label": label,
                "svg_digest": svg_digest,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        inventory.append({
            "element_id": element_id,
            "element_kind": element_kind,
            "label": label,
            "scene_element_digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "scene_relation_id": "",
        })
    arrow_elements = [
        item for item in root.iter()
        if item.tag.rsplit("}", 1)[-1] in {"path", "line", "polyline"}
        and any(key.rsplit("}", 1)[-1] == "marker-end" for key in item.attrib)
    ]
    for index, element in enumerate(arrow_elements, start=1):
        element_id = f"legacy-svg-edge-{index}"
        label = f"visible arrow {index}"
        relation_id = f"legacy-svg-relation-{index}"
        payload = json.dumps(
            {
                "element_id": element_id,
                "element_kind": "edge",
                "label": label,
                "relation_id": relation_id,
                "svg_element": ET.tostring(element, encoding="unicode"),
                "svg_digest": svg_digest,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        inventory.append({
            "element_id": element_id,
            "element_kind": "edge",
            "label": label,
            "scene_element_digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "scene_relation_id": relation_id,
        })
    return inventory
