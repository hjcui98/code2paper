from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.text_evidence_validator import report_digest
from code2paper.agentic.trust_contracts import (
    AuthoringInputProjection,
    FinalTextClaims,
    FinalTextTrace,
    TextEvidenceValidationReport,
    TextTraceEntry,
)


def build_final_text_trace(
    *,
    final_claims: FinalTextClaims,
    validation: TextEvidenceValidationReport,
    projection: AuthoringInputProjection,
    validator_report_ref: str,
    projection_ref: str,
) -> FinalTextTrace:
    failures: list[str] = []
    if validation.status != "passed":
        failures.append("text_evidence_validation_not_passed")
    if validation.input_text_digest != final_claims.input_text_digest:
        failures.append("validator_text_digest_mismatch")
    if validation.projection_digest != projection.projection_digest:
        failures.append("validator_projection_digest_mismatch")
    if validation.repo_snapshot_id != projection.repo_snapshot_id:
        failures.append("validator_repo_snapshot_id_mismatch")
    if validation.project_tree_hash != projection.project_tree_hash:
        failures.append("validator_project_tree_hash_mismatch")
    if validation.evidence_snapshot_id != projection.evidence_snapshot_id:
        failures.append("validator_evidence_snapshot_id_mismatch")
    if validation.evidence_snapshot_digest != projection.evidence_snapshot_digest:
        failures.append("validator_evidence_snapshot_digest_mismatch")
    claim_by_id = {claim.atomic_claim_id: claim for claim in final_claims.atomic_claims}
    entries: list[TextTraceEntry] = []
    for verdict in validation.verdicts:
        if verdict.status not in {"supported", "caveated"}:
            continue
        claim = claim_by_id.get(verdict.atomic_claim_id)
        if claim is None:
            failures.append(f"unknown_atomic_claim:{verdict.atomic_claim_id}")
            continue
        unit = next((item for item in final_claims.units if item.unit_id == claim.unit_id), None)
        if unit is None:
            failures.append(f"unknown_text_unit:{claim.unit_id}")
            continue
        entries.append(
            TextTraceEntry(
                trace_id=f"TTE{len(entries) + 1}",
                atomic_claim_id=claim.atomic_claim_id,
                final_text_span_digest=unit.span_digest,
                claim_digest=claim.claim_digest,
                verdict_status=verdict.status,
                direct_evidence_ids=verdict.direct_evidence_ids,
                relation_evidence_ids=verdict.relation_evidence_ids,
                projection_claim_ids=verdict.matched_projection_claim_ids,
                validator_report_ref=validator_report_ref,
                projection_ref=projection_ref,
            )
        )
    if len(entries) != len(final_claims.atomic_claims):
        failures.append("not_every_factual_atomic_claim_has_trace")
    return FinalTextTrace(
        input_text_digest=final_claims.input_text_digest,
        projection_digest=projection.projection_digest,
        validation_report_digest=report_digest(validation),
        repo_snapshot_id=projection.repo_snapshot_id,
        project_tree_hash=projection.project_tree_hash,
        evidence_snapshot_id=projection.evidence_snapshot_id,
        evidence_snapshot_digest=projection.evidence_snapshot_digest,
        entries=entries,
        hard_gate_passed=not failures,
        failures=list(dict.fromkeys(failures)),
    )


def write_final_text_trace(path: str | Path, trace: FinalTextTrace) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_final_text_trace(path: str | Path) -> FinalTextTrace:
    return FinalTextTrace.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
