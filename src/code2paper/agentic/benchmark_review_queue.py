from __future__ import annotations

import hashlib
import json
from pathlib import Path

from code2paper.agentic.benchmark_protocol import BenchmarkProtocolV2, benchmark_spec_digest
from code2paper.agentic.benchmark_observation import build_figure_review_inventory
from code2paper.agentic.benchmark_v2 import BenchmarkDatasetV2


def build_review_queue_v2(
    dataset: BenchmarkDatasetV2,
    protocol: BenchmarkProtocolV2,
    run_indexes: list[str | Path],
    *,
    mutation_roots: dict[str, str | Path],
    legacy_audit_root: str | Path,
) -> dict:
    cases = {item.case_id: item for item in dataset.cases}
    records: dict[tuple[str, str, str, int], dict] = {}
    for path in run_indexes:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for item in payload.get("runs", []):
            records[(item["case_id"], item["variant"], item.get("intent_id", ""), item["repeat_index"])] = item
    entries: list[dict] = []
    for spec in protocol.specs:
        key = (spec.case_id, spec.variant, spec.intent_id, spec.repeat_index)
        record = records.get(key)
        if not record:
            entries.append({"identity": list(key), "status": "run_record_missing"})
            continue
        case = cases[spec.case_id]
        summary_path = _summary_path(spec.variant, Path(spec.out_root))
        template = {
            "schema_version": "2.0",
            "case_id": spec.case_id,
            "variant": spec.variant,
            "repeat_index": spec.repeat_index,
            "intent_id": spec.intent_id,
            "scope": "full_pipeline",
            "run_summary_path": str(summary_path),
            "run_summary_digest": _digest(summary_path),
            "protocol_spec_digest": benchmark_spec_digest(spec),
            "repo_snapshot_id": spec.repo_snapshot_id,
            "model_id": spec.model_id,
            "capability_profile_digest": spec.capability_profile_digest,
            "reviewer": "__REQUIRED_NAMED_HUMAN__",
            "reviewed_at": "__REQUIRED_ISO8601__",
            "blocked_reason_review": "",
            "claims": _agentic_claim_templates(summary_path) if spec.variant != "fixed_legacy" else [],
            "figures": _agentic_figure_templates(summary_path) if spec.variant != "fixed_legacy" else [],
            "mutation_trials": _mutation_templates(case, mutation_roots[case.case_id]),
            "expected_retrieval_targets_observed": [],
            "section_claim_order": [],
            "figure_claim_ids": [],
            "usable_completion": False,
            "latency_seconds": record.get("duration_seconds", 0.0),
        }
        legacy_audit = ""
        if spec.variant == "fixed_legacy":
            slug = "-".join(filter(None, (spec.case_id, spec.intent_id or "default"))) + ".json"
            audit_path = Path(legacy_audit_root) / slug
            if audit_path.is_file():
                legacy_audit = str(audit_path.resolve())
        entries.append({
            "identity": list(key), "status": "human_review_required", "review_template": template,
            "gold_claims": [item.model_dump(mode="json") for item in case.supported_claims],
            "gold_figure_relations": [item.model_dump(mode="json") for item in case.figure_relations],
            "legacy_v2_audit_path": legacy_audit,
            "legacy_v2_audit_digest": _digest(Path(legacy_audit)) if legacy_audit else "",
            "review_instructions": [
                "Map each factual claim to a gold claim only after semantic comparison.",
                "Mark qualifiers_preserved only when every required qualifier is present.",
                "Review every blocked reason as specific/correct/repairable or false-block.",
                "Do not set usable_completion when V2 text, figure, lineage, or final invariant is absent.",
            ],
        })
    return {
        "schema_version": "2.0", "protocol_commit": protocol.workspace_commit,
        "entry_count": len(entries), "ready_for_cutover": False,
        "blocking_reason": "named_human_reviews_not_completed", "entries": entries,
    }


def write_review_queue_v2(path: str | Path, queue: dict) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def _summary_path(variant: str, root: Path) -> Path:
    if variant == "fixed_legacy":
        return root / "paper/method/code2paper_run_report.json"
    return root / "artifacts/10_run/agentic_run_summary.json"


def _agentic_claim_templates(summary_path: Path) -> list[dict]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    artifacts = summary.get("artifacts", {})
    claims_record = artifacts.get("final_text_claims")
    validation_record = artifacts.get("text_evidence_validation")
    if not claims_record or not validation_record:
        return []
    claims = json.loads(Path(claims_record["path"]).read_text(encoding="utf-8"))
    validation = json.loads(Path(validation_record["path"]).read_text(encoding="utf-8"))
    verdicts = {item["atomic_claim_id"]: item for item in validation.get("verdicts", [])}
    return [{
        "atomic_claim_id": item["atomic_claim_id"], "text": item.get("text", ""),
        "verdict": verdicts.get(item["atomic_claim_id"], {}).get("status", "unverified"),
        "gold_claim_id": "", "mutation_id": "", "qualifiers_preserved": False,
        "high_risk": bool(item.get("high_risk_markers")),
    } for item in claims.get("atomic_claims", [])]


def _agentic_figure_templates(summary_path: Path) -> list[dict]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    record = summary.get("artifacts", {}).get("figure_scene")
    if not record:
        return []
    path = Path(record["path"]).resolve()
    expected_digest = str(record.get("hash") or "")
    if _digest(path) != expected_digest:
        raise ValueError("figure scene digest changed before review queue construction")
    scene = json.loads(path.read_text(encoding="utf-8"))
    return build_figure_review_inventory(scene)


def _mutation_templates(case, root: str | Path) -> list[dict]:
    values = []
    for mutation in case.mutations:
        path = Path(root).resolve() / f"{mutation.mutation_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        values.append({
            "mutation_id": mutation.mutation_id, "detected": bool(payload.get("detected")),
            "trial_artifact_path": str(path), "trial_artifact_digest": _digest(path),
        })
    return values


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
