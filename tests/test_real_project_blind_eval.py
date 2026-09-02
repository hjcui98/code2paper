from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.real_project_blind_eval import evaluate_manifest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_blind_eval_keeps_original_out_of_generation_and_labels_blocked_candidate(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    runs_root = tmp_path / "runs"
    run = runs_root / "case"
    original = data_root / "paper.md"
    original.parent.mkdir(parents=True)
    original.write_text("Method\nThe model uses a condition router.\n", encoding="utf-8")
    candidate = run / "artifacts/06_authoring/method_clean.md"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("# Method\nThe model uses a condition router.\n", encoding="utf-8")
    _write_json(run / "artifacts/01_input/input_manifest.json", {"project_root": "code"})
    _write_json(
        run / "artifacts/10_run/agentic_run_summary.json",
        {"status": "blocked", "blocked_reason": "evidence_missing"},
    )
    _write_json(
        run / "artifacts/10_run/agentic_run_completion_report.json",
        {"status": "blocked", "complete": False},
    )
    _write_json(
        run / "artifacts/10_run/agentic_run_evaluation_report.json",
        {"traceability_passed": True},
    )
    _write_json(
        run / "artifacts/06_authoring/formalization_section_results_v1.json",
        {
            "sections": [{
                "section_id": "MA-S1",
                "formula_obligations": [{
                    "obligation_id": "formula:MA-S1:1",
                    "consumer_paragraph_id": "paragraph:MA-S1:1",
                    "expectation": "required",
                }],
                "packages": [],
            }],
            "formalizer_call_traces": [{
                "section_id": "MA-S1",
                "call_traces": [{
                    "proposed_package_count": 1,
                    "accepted_package_count": 0,
                    "status": "guards_failed",
                    "guard_failures": [
                        "pkg:rejected:formula_package_consumer_route_ambiguous"
                    ],
                }],
            }],
        },
    )
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "cases": [
                {
                    "case_id": "case",
                    "run_dir": "case",
                    "original": "paper.md",
                    "concepts": [
                        {"id": "router", "aliases": ["condition router"]}
                    ],
                }
            ]
        },
    )

    report = evaluate_manifest(manifest, data_root=data_root, runs_root=runs_root)

    case = report["cases"][0]
    assert report["reference_isolation_passed"] is True
    assert case["accepted_for_delivery"] is False
    assert case["generated_method_source"] == "blocked_candidate_not_for_delivery"
    assert case["generated_intent_concepts"]["coverage"] == 1.0
    assert case["original_role"] == "evaluation_only"
    assert case["formula_funnel"]["proposed_packages"] == 1
    assert case["formula_funnel"]["rejected_packages"] == 1
    assert case["formula_funnel"]["route_ambiguous_failures"] == 1
    assert case["replay_diagnostics"]["formula_funnel"] == case["formula_funnel"]


def test_blind_eval_rejects_original_digest_in_generation_manifest(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    runs_root = tmp_path / "runs"
    run = runs_root / "case"
    original = data_root / "paper.md"
    original.parent.mkdir(parents=True)
    original.write_text("Method body", encoding="utf-8")
    digest = "sha256:" + __import__("hashlib").sha256(original.read_bytes()).hexdigest()
    final_method = run / "final/method.md"
    final_method.parent.mkdir(parents=True)
    final_method.write_text("Method body", encoding="utf-8")
    _write_json(
        run / "artifacts/01_input/input_manifest.json", {"forbidden_reference": digest}
    )
    _write_json(
        run / "artifacts/10_run/agentic_run_summary.json", {"status": "success"}
    )
    _write_json(
        run / "artifacts/10_run/agentic_run_completion_report.json",
        {"status": "complete", "complete": True},
    )
    _write_json(run / "artifacts/10_run/agentic_run_evaluation_report.json", {})
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "cases": [
                {
                    "case_id": "case",
                    "run_dir": "case",
                    "original": "paper.md",
                    "concepts": [],
                }
            ]
        },
    )

    report = evaluate_manifest(manifest, data_root=data_root, runs_root=runs_root)

    assert report["reference_isolation_passed"] is False
