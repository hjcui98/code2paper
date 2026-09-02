from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "evaluate_research_derived_authoring.py"


def _load_evaluator():
    spec = importlib.util.spec_from_file_location(
        "evaluate_research_derived_authoring", _SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _report(*, edge_planned: int = 1, edge_rendered: int = 1) -> dict:
    artifact_names = {
        "method_section_plan_v2",
        "method_propositions_v1",
        "method_proposition_alignment_v1",
        "method_argument_briefs_v1",
        "method_argument_facets_v1",
        "facet_evidence_alignments_v1",
        "candidate_facet_policies_v1",
        "method_argument_facet_alignment_trace_v1",
        "formalization_section_results_v1",
        "publication_writer_result_v1",
        "publication_candidate_method",
        "repository_verified_method",
        "text_evidence_validation",
        "method_content_trace_v1",
        "publication_paragraph_transaction_assessments_v1",
        "publication_paragraph_checkpoint_v1",
        "authoring_structural_exit_v1",
        "research_mechanism_dossiers_v1",
        "derivation_records_v1",
        "candidate_authority_validation_v1",
        "publication_candidate_annotations_v1",
    }
    presence = {name: True for name in artifact_names}
    presence["method_propositions_v1"] = False
    return {
        "run_root": "test-root",
        "content_chain": {"summary": {
            "planned_story_nodes": 1,
            "rendered_story_nodes": 1,
            "planned_paragraphs": 1,
            "rendered_paragraphs": 1,
            "planned_slots": 1,
            "rendered_slots": 1,
            "planned_edges": edge_planned,
            "rendered_edges": edge_rendered,
            "formula_obligations": 1,
            "rendered_formula_obligations": 1,
        }},
        "artifact_presence": presence,
        "formula": {
            "accepted_packages": 1,
            "consumed_packages": 1,
            "exact_body_validated_packages": 1,
        },
        "formula_funnel": {"routed_obligations": 1},
        "candidate_surface": {
            "authority_status": "passed",
            "internal_audit_term_count": 0,
            "violations": [],
            "warnings": [],
            "sentences_by_surface_mode": {"repository_statement": 1},
        },
        "verified_leakage": {"count": 0},
        "execution": {"exit_code": 0, "writer_status": "success"},
        "structural_exit": {"eligible": True, "reasons": []},
        "quality": {"status": "publication_ready"},
        "reverse_validation": {"status": "passed"},
        "failure": None,
        "authoring_observations": {},
    }


def test_argument_brief_route_does_not_require_legacy_proposition_artifact(
    monkeypatch, tmp_path: Path,
) -> None:
    module = _load_evaluator()
    monkeypatch.setattr(module, "diagnose_publication_replay", lambda _root: _report())
    monkeypatch.setattr(module, "_candidate_text", lambda _root: "Candidate.")

    result = module.evaluate_research_derived_authoring(tmp_path)

    assert result["required_artifacts"]["authoring_route"] == "argument_briefs"
    assert result["required_artifacts"]["passed"] is True
    assert "method_propositions_v1" not in result["required_artifacts"]["missing"]
    assert result["acceptance_passed"] is True


def test_zero_over_zero_coverage_is_not_run_and_fails_acceptance(
    monkeypatch, tmp_path: Path,
) -> None:
    module = _load_evaluator()
    monkeypatch.setattr(
        module, "diagnose_publication_replay",
        lambda _root: _report(edge_planned=0, edge_rendered=0),
    )
    monkeypatch.setattr(module, "_candidate_text", lambda _root: "Candidate.")

    result = module.evaluate_research_derived_authoring(tmp_path)

    assert result["coverage"]["edge"] == {
        "planned": 0, "rendered": 0, "recall": None,
    }
    assert result["acceptance_passed"] is False
    assert "coverage_not_run:edge" in result["failure_reasons"]


def test_acceptance_rejects_process_writer_and_structural_failures(
    monkeypatch, tmp_path: Path,
) -> None:
    module = _load_evaluator()

    report = _report()
    report["execution"]["exit_code"] = 2
    monkeypatch.setattr(module, "diagnose_publication_replay", lambda _root: report)
    monkeypatch.setattr(module, "_candidate_text", lambda _root: "Candidate.")
    result = module.evaluate_research_derived_authoring(tmp_path)
    assert result["acceptance_passed"] is False
    assert "process_exit_code:2" in result["failure_reasons"]

    report = _report()
    report["execution"]["writer_status"] = "incomplete"
    report["structural_exit"] = {"eligible": False, "reasons": ["missing_target"]}
    monkeypatch.setattr(module, "diagnose_publication_replay", lambda _root: report)
    result = module.evaluate_research_derived_authoring(tmp_path)
    assert result["acceptance_passed"] is False
    assert "writer_not_complete:incomplete" in result["failure_reasons"]
    assert any(
        reason.startswith("structural_exit_not_eligible")
        for reason in result["failure_reasons"]
    )


def test_acceptance_rejects_missing_candidate_artifact(
    monkeypatch, tmp_path: Path,
) -> None:
    module = _load_evaluator()
    report = _report()
    report["artifact_presence"]["publication_candidate_method"] = False
    monkeypatch.setattr(module, "diagnose_publication_replay", lambda _root: report)
    monkeypatch.setattr(module, "_candidate_text", lambda _root: "")

    result = module.evaluate_research_derived_authoring(tmp_path)

    assert result["acceptance_passed"] is False
    assert "publication_candidate_method" in result["required_artifacts"]["missing"]
    assert any(
        reason.startswith("required_artifacts_missing:")
        for reason in result["failure_reasons"]
    )
