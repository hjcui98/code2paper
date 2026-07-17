from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.translate(str.maketrans({"‐": "-", "‑": "-", "–": "-", "—": "-"}))
    return re.sub(r"\s+", " ", text).strip()


def _body_text(markdown: str) -> str:
    return "\n".join(
        line for line in markdown.splitlines() if not line.lstrip().startswith("#")
    )


def _concept_result(text: str, concepts: list[dict[str, Any]]) -> dict[str, Any]:
    body = _normalize(_body_text(text))
    hits: list[str] = []
    misses: list[str] = []
    matched_aliases: dict[str, str] = {}
    for concept in concepts:
        concept_id = str(concept["id"])
        aliases = [_normalize(str(alias)) for alias in concept.get("aliases", [])]
        matched = next((alias for alias in aliases if alias and alias in body), "")
        if matched:
            hits.append(concept_id)
            matched_aliases[concept_id] = matched
        else:
            misses.append(concept_id)
    total = len(concepts)
    return {
        "concept_count": total,
        "hit_count": len(hits),
        "coverage": round(len(hits) / total, 4) if total else 1.0,
        "hits": hits,
        "misses": misses,
        "matched_aliases": matched_aliases,
    }


def _repetition_metrics(text: str) -> dict[str, Any]:
    lines = [
        _normalize(line)
        for line in _body_text(text).splitlines()
        if _normalize(line)
    ]
    unique = set(lines)
    return {
        "nonempty_body_lines": len(lines),
        "unique_body_lines": len(unique),
        "duplicate_body_lines": len(lines) - len(unique),
        "unique_body_line_ratio": round(len(unique) / len(lines), 4) if lines else 1.0,
    }


def evaluate_case(
    case: dict[str, Any], *, data_root: Path, runs_root: Path
) -> dict[str, Any]:
    run_root = runs_root / str(case["run_dir"])
    original_path = data_root / str(case["original"])
    input_manifest_path = run_root / "artifacts/01_input/input_manifest.json"
    completion_path = run_root / "artifacts/10_run/agentic_run_completion_report.json"
    summary_path = run_root / "artifacts/10_run/agentic_run_summary.json"
    evaluation_path = run_root / "artifacts/10_run/agentic_run_evaluation_report.json"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    run_evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    input_manifest_text = input_manifest_path.read_text(encoding="utf-8")

    complete = bool(completion.get("complete"))
    generated_path = run_root / (
        "final/method.md" if complete else "artifacts/06_authoring/method_clean.md"
    )
    generated_text = generated_path.read_text(encoding="utf-8")

    # The reference is deliberately opened only after generation artifacts and status
    # have been resolved. It is an evaluator input, never an authoring/evidence input.
    original_digest = _sha256(original_path)
    original_text = original_path.read_text(encoding="utf-8")
    isolation_haystack = input_manifest_text + "\n" + json.dumps(summary, sort_keys=True)
    isolation_passed = (
        str(original_path) not in isolation_haystack
        and original_digest not in isolation_haystack
    )

    generated_concepts = _concept_result(generated_text, list(case["concepts"]))
    original_concepts = _concept_result(original_text, list(case["concepts"]))
    return {
        "case_id": case["case_id"],
        "generation_status": summary.get("status"),
        "blocked_reason": summary.get("blocked_reason", ""),
        "completion_status": completion.get("status"),
        "accepted_for_delivery": complete and summary.get("status") == "success",
        "original_role": "evaluation_only",
        "reference_isolation_passed": isolation_passed,
        "digests": {
            "input_manifest": _sha256(input_manifest_path),
            "generated_method": _sha256(generated_path),
            "original_method": original_digest,
        },
        "generated_method_source": (
            "final_method" if complete else "blocked_candidate_not_for_delivery"
        ),
        "generated_intent_concepts": generated_concepts,
        "original_intent_concepts": original_concepts,
        "intent_coverage_gap_vs_original": round(
            generated_concepts["coverage"] - original_concepts["coverage"], 4
        ),
        "generated_repetition": _repetition_metrics(generated_text),
        "trust_metrics": {
            key: run_evaluation.get(key)
            for key in (
                "evidence_target_coverage_score",
                "evidence_support_rate",
                "final_text_unsupported_claim_rate",
                "text_evidence_validation_passed",
                "invariant_audit_passed",
                "traceability_passed",
            )
        },
    }


def evaluate_manifest(
    manifest_path: Path, *, data_root: Path, runs_root: Path
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = [
        evaluate_case(case, data_root=data_root, runs_root=runs_root)
        for case in manifest["cases"]
    ]
    return {
        "schema_version": "code2paper.real-project-blind-eval.v1",
        "protocol": {
            "generation_inputs": ["code", "author_intent"],
            "original_paper_role": "evaluation_only_after_generation",
            "concept_metric_scope": "intent-derived substantive body phrase coverage",
            "manifest_digest": _sha256(manifest_path),
        },
        "case_count": len(cases),
        "reference_isolation_passed": all(
            case["reference_isolation_passed"] for case in cases
        ),
        "delivery_complete_count": sum(
            bool(case["accepted_for_delivery"]) for case in cases
        ),
        "cases": cases,
    }
