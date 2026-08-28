from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.method_content_trace import (
    build_method_content_trace_from_artifact_paths,
)
from code2paper.core.output_names import method_output


def _write(root: Path, name: str, payload: dict) -> str:
    path = root / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _artifact_paths(root: Path, *, used_package: bool) -> dict[str, str]:
    plan = {
        "sections": [{
            "section_id": "section:method",
            "story_node_ids": ["story:main"],
            "primary_brief_ids": ["brief:main"],
            "paragraphs": [{
                "paragraph_id": "section:method:p1",
                "paragraph_role": "formula",
                "argument_unit_ids": ["unit:main"],
                "required_facet_ids": ["facet:formula"],
                "ordered_semantic_slot_ids": ["slot:operation", "slot:output"],
                "required_edge_ids": ["edge:main"],
                "formula_obligation_ids": ["formula:main"],
            }],
        }],
        "argument_units": [{
            "argument_unit_id": "unit:main",
            "semantic_frame": {"frame_id": "frame:main"},
        }],
    }
    facets = {"facets": [{"facet_id": "facet:formula", "brief_id": "brief:main"}]}
    alignments = {"alignments": [{
        "facet_id": "facet:formula",
        "status": "partial",
        "field_bindings": [{
            "field_name": "condition",
            "status": "partial",
            "polarity": "threshold_lt_excludes",
            "bound_span_ids": ["span:main"],
        }],
    }]}
    policies = {"policies": [{
        "facet_id": "facet:formula",
        "alignment_status": "partial",
        "prose_mode": "author_specification",
    }]}
    formalization = {"sections": [{
        "section_id": "section:method",
        "packages": [{"package_id": "package:main"}],
    }]}
    writer_output = {
        "section_markdown": "A mechanism is applied.\n\n$$x=y$$",
        "rendered_paragraph_ids": ["section:method:p1"],
        "rendered_slot_ids": ["slot:operation", "slot:output"],
        "used_formula_package_ids": ["package:main"] if used_package else [],
        "used_claim_ids": ["claim:main"],
    }
    writer = {"section_results": [{
        "section_id": "section:method",
        "accepted": True,
        "output": writer_output,
    }]}
    return {
        "method_section_plan_v2": _write(root, "plan", plan),
        "method_argument_facets_v1": _write(root, "facets", facets),
        "facet_evidence_alignments_v1": _write(root, "alignments", alignments),
        "candidate_facet_policies_v1": _write(root, "policies", policies),
        "formalization_section_results_v1": _write(root, "formalization", formalization),
        "publication_writer_result_v1": _write(root, "writer", writer),
        "publication_quality_report_v1": _write(root, "quality", {"status": "incomplete"}),
    }


def test_trace_preserves_field_polarity_and_formula_consumption(tmp_path: Path) -> None:
    trace = build_method_content_trace_from_artifact_paths(
        _artifact_paths(tmp_path, used_package=True)
    )

    assert trace.summary["planned_paragraphs"] == 1
    assert trace.summary["rendered_paragraphs"] == 1
    assert trace.summary["rendered_slots"] == 2
    assert trace.summary["consumed_formula_packages"] == 1
    row = trace.rows[0]
    assert row.terminal_state == "rendered"
    assert row.accepted_formula_package_ids == ("package:main",)
    assert row.field_bindings[0]["polarity"] == "threshold_lt_excludes"


def test_trace_marks_unconsumed_formula_package_invalid(tmp_path: Path) -> None:
    trace = build_method_content_trace_from_artifact_paths(
        _artifact_paths(tmp_path, used_package=False)
    )

    assert trace.rows[0].terminal_state == "rendered_invalid"
    assert trace.rows[0].stop_reason == "formula_package_not_consumed"


def test_trace_does_not_count_transaction_without_witness_as_rendered(
    tmp_path: Path,
) -> None:
    paths = _artifact_paths(tmp_path, used_package=True)
    writer_path = Path(paths["publication_writer_result_v1"])
    writer = json.loads(writer_path.read_text(encoding="utf-8"))
    writer["section_results"][0]["output"]["paragraphs"] = [{
        "paragraph_id": "section:method:p1",
        "paragraph_markdown": "A mechanism is applied, but no exact ids are witnessed.",
        "rendered_slot_ids": ["slot:operation"],
        "used_formula_package_ids": ["package:main"],
        "witnesses": [],
    }]
    writer_path.write_text(json.dumps(writer), encoding="utf-8")

    trace = build_method_content_trace_from_artifact_paths(paths)

    assert trace.summary["rendered_paragraphs"] == 0
    assert trace.summary["rendered_slots"] == 0
    assert trace.rows[0].terminal_state == "rendered_invalid"
    assert trace.rows[0].stop_reason == "paragraph_transaction_witness_missing"


def test_trace_labels_rejected_section_with_body_as_rendered_invalid(
    tmp_path: Path,
) -> None:
    paths = _artifact_paths(tmp_path, used_package=True)
    writer_path = Path(paths["publication_writer_result_v1"])
    writer = json.loads(writer_path.read_text(encoding="utf-8"))
    writer["section_results"][0]["accepted"] = False
    writer["section_results"][0]["output"]["paragraphs"] = [{
        "paragraph_id": "section:method:p1",
        "paragraph_markdown": "A substantive body without the required witness.",
        "rendered_slot_ids": [],
        "used_formula_package_ids": [],
        "witnesses": [],
    }]
    writer_path.write_text(json.dumps(writer), encoding="utf-8")

    trace = build_method_content_trace_from_artifact_paths(paths)

    assert trace.rows[0].terminal_state == "rendered_invalid"
    assert trace.rows[0].stop_reason == "paragraph_transaction_witness_missing"
    assert trace.summary["blocked_representation"] == 0


def test_content_trace_has_standard_output_name() -> None:
    assert method_output(Path("/tmp/run"), "method_content_trace_v1").as_posix().endswith(
        "artifacts/research_product/method_content_trace_v1.json"
    )
