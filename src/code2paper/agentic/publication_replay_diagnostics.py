"""Read-only diagnostics for one frozen publication replay root."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.core.output_names import method_output


def _json_artifact(root: Path, key: str) -> dict[str, Any] | None:
    path = method_output(root, key)
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{key} must contain a JSON object")
    return value


def _text_size(root: Path, key: str) -> int:
    path = method_output(root, key)
    return len(path.read_bytes()) if path.is_file() else 0


def diagnose_publication_replay(root: str | Path) -> dict[str, Any]:
    """Extract a stable comparison record without changing the replay root."""

    run_root = Path(root).expanduser().resolve()
    if not run_root.is_dir():
        raise FileNotFoundError(f"publication replay root does not exist: {run_root}")
    checkpoint = _json_artifact(run_root, "publication_section_checkpoint_v1") or {}
    quality = _json_artifact(run_root, "publication_quality_report_v1") or {}
    validation = _json_artifact(run_root, "text_evidence_validation") or {}
    content_trace = _json_artifact(run_root, "method_content_trace_v1") or {}
    alignment = _json_artifact(run_root, "method_proposition_alignment_v1") or {}
    propositions = _json_artifact(run_root, "method_propositions_v1") or {}
    editor = _json_artifact(run_root, "publication_editor_transitions_v1") or {}
    rewrite = _json_artifact(run_root, "publication_rewrite_transitions_v1") or {}
    transaction_assessments = _json_artifact(
        run_root, "publication_paragraph_transaction_assessments_v1"
    ) or {}
    structural_exit = _json_artifact(run_root, "authoring_structural_exit_v1") or {}

    section_outputs = checkpoint.get("section_outputs") or checkpoint.get("sections") or {}
    if isinstance(section_outputs, list):
        section_outputs = {
            str(item.get("section_id") or ""): item
            for item in section_outputs if isinstance(item, dict)
        }
    if not isinstance(section_outputs, dict):
        section_outputs = {}
    checkpoint_parent = method_output(
        run_root, "publication_section_checkpoint_v1"
    ).parent.resolve()
    resolved_outputs: dict[str, Any] = {}
    for section_id, raw in section_outputs.items():
        if not isinstance(raw, dict) or not raw.get("output_ref"):
            resolved_outputs[str(section_id)] = raw
            continue
        output_path = (checkpoint_parent / str(raw["output_ref"])).resolve()
        if checkpoint_parent not in output_path.parents or not output_path.is_file():
            resolved_outputs[str(section_id)] = {}
            continue
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        resolved_outputs[str(section_id)] = (
            payload if isinstance(payload, dict) else {}
        )
    section_outputs = resolved_outputs
    section_rows = {
        str(row.get("section_id") or ""): row
        for row in alignment.get("sections") or () if isinstance(row, dict)
    }
    failures_by_type: dict[str, int] = {}
    for verdict in validation.get("verdicts") or ():
        if not isinstance(verdict, dict):
            continue
        for failure in verdict.get("deterministic_failures") or ():
            name = str(failure)
            failures_by_type[name] = failures_by_type.get(name, 0) + 1

    sections: list[dict[str, Any]] = []
    for section_id, raw in sorted(section_outputs.items()):
        output = raw.get("output", raw) if isinstance(raw, dict) else {}
        if not isinstance(output, dict):
            output = {}
        alignment_row = section_rows.get(section_id, {})
        sections.append({
            "section_id": section_id,
            "writer_text": str(output.get("section_markdown") or ""),
            "declared_rendered_proposition_ids": list(
                output.get("rendered_proposition_ids") or ()
            ),
            "declared_deferred_proposition_ids": list(
                output.get("deferred_proposition_ids") or ()
            ),
            "validated_proposition_ids": list(
                alignment_row.get("validated_proposition_ids") or ()
            ),
            "missing_proposition_ids": list(
                alignment_row.get("missing_proposition_ids") or ()
            ),
            "rendered_paragraph_ids": list(
                output.get("rendered_paragraph_ids") or ()
            ),
            "rendered_slot_ids": list(output.get("rendered_slot_ids") or ()),
            "rendered_edge_ids": list(output.get("rendered_edge_ids") or ()),
            "used_formula_package_ids": list(
                output.get("used_formula_package_ids") or ()
            ),
            "used_equation_ids": list(output.get("used_equation_ids") or ()),
        })

    utility = quality.get("utility") or {}
    safety = quality.get("safety") or {}
    return {
        "schema_version": "1.0",
        "run_root": str(run_root),
        "artifact_presence": {
            key: method_output(run_root, key).is_file()
            for key in (
                "method_propositions_v1",
                "method_proposition_alignment_v1",
                "publication_candidate_method",
                "repository_verified_method",
                "author_review_candidates",
                "text_evidence_validation",
                "method_content_trace_v1",
                "publication_paragraph_transaction_assessments_v1",
                "authoring_structural_exit_v1",
            )
        },
        "output_bytes": {
            "candidate": _text_size(run_root, "publication_candidate_method"),
            "verified": _text_size(run_root, "repository_verified_method"),
            "review": _text_size(run_root, "author_review_candidates"),
        },
        "propositions": {
            "planned": len(propositions.get("propositions") or ()),
            "gaps": len(propositions.get("gaps") or ()),
            "rendered": len({
                proposition_id
                for row in alignment.get("sections") or ()
                for proposition_id in (
                    (
                        row.get("rendered_proposition_ids")
                        or row.get("validated_proposition_ids")
                        or ()
                    ) if isinstance(row, dict) else ()
                )
            }),
            "validated": len({
                proposition_id
                for row in alignment.get("sections") or ()
                for proposition_id in (
                    row.get("validated_proposition_ids") or ()
                    if isinstance(row, dict) else ()
                )
            }),
            "semantic_alignment_calls": int(
                alignment.get("semantic_alignment_calls") or 0
            ),
        },
        "reverse_validation": {
            "status": validation.get("status", "not_run"),
            "supported": int(validation.get("supported_claims") or 0),
            "caveated": int(validation.get("caveated_claims") or 0),
            "unsupported": int(validation.get("unsupported_claims") or 0),
            "unverified": int(validation.get("unverified_claims") or 0),
            "failures_by_type": dict(sorted(failures_by_type.items())),
        },
        "quality": {
            "status": quality.get("status", "not_run"),
            "planned_proposition_recall": utility.get(
                "planned_proposition_recall", 0.0
            ),
            "rendered_proposition_recall": utility.get(
                "rendered_proposition_recall", 0.0
            ),
            "validated_proposition_recall": utility.get(
                "validated_proposition_recall", 0.0
            ),
            "unsupported_positive_claims": safety.get(
                "unsupported_positive_claims", 0
            ),
            "issue_codes": [
                str(item.get("code") or "")
                for item in quality.get("issues") or () if isinstance(item, dict)
            ],
        },
        "content_chain": {
            "summary": dict(
                content_trace.get("summary")
                or (quality.get("content_chain") or {}).get("summary")
                or {}
            ),
            "content_digest": str(
                content_trace.get("content_digest")
                or (quality.get("content_chain") or {}).get("content_digest")
                or ""
            ),
            "terminal_states": sorted({
                str(row.get("terminal_state") or "")
                for row in content_trace.get("rows") or ()
                if isinstance(row, dict)
            }),
        },
        "transactions": {
            "editor": len(editor.get("transitions") or ()),
            "rewrite": len(rewrite.get("transitions") or ()),
            "rewrite_applied": sum(
                item.get("status") == "applied"
                for item in rewrite.get("transitions") or ()
                if isinstance(item, dict)
            ),
            "paragraph_assessments": len(transaction_assessments.get("assessments") or ()),
            "paragraph_assessments_valid": sum(
                bool(item.get("valid"))
                for item in transaction_assessments.get("assessments") or ()
                if isinstance(item, dict)
            ),
            "paragraph_assessments_invalid": sum(
                not bool(item.get("valid"))
                for item in transaction_assessments.get("assessments") or ()
                if isinstance(item, dict)
            ),
        },
        "structural_exit": {
            "eligible": bool(structural_exit.get("eligible")),
            "reasons": list(structural_exit.get("reasons") or ()),
            "required_targets": int(structural_exit.get("required_targets") or 0),
            "valid_targets": int(structural_exit.get("valid_targets") or 0),
            "accepted_formula_packages": int(
                structural_exit.get("accepted_formula_packages") or 0
            ),
            "consumed_formula_packages": int(
                structural_exit.get("consumed_formula_packages") or 0
            ),
            "content_digest": str(structural_exit.get("content_digest") or ""),
        },
        "sections": sections,
    }


__all__ = ["diagnose_publication_replay"]
