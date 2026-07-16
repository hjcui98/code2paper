from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.traceability_artifacts import (
    artifact_json,
    as_list,
    as_string_list,
    dedupe,
    known_claim_ids as collect_known_claim_ids,
    known_evidence_ids as collect_known_evidence_ids,
    unsupported_claim_ids as collect_unsupported_claim_ids,
)
from code2paper.agentic.traceability_figures import figure_entries
from code2paper.agentic.traceability_models import EvidenceTraceabilityLedger, TraceabilityLedgerEntry


def build_traceability_ledger(state: AgenticRunState) -> EvidenceTraceabilityLedger:
    """Build a unified evidence ledger from frozen claims, text traces, and figure plan."""

    known_evidence_ids = collect_known_evidence_ids(state)
    known_claim_ids = collect_known_claim_ids(state)
    unsupported_claim_ids = collect_unsupported_claim_ids(state)
    excluded_claim_ids = set(as_string_list(artifact_json(state, "authoring_constraints").get("excluded_claim_ids")))
    entries: list[TraceabilityLedgerEntry] = []
    entries.extend(_claim_entries(state))
    entries.extend(_text_entries(state))
    entries.extend(figure_entries(state))
    checked_entries = [
        _check_entry(
            entry,
            known_evidence_ids=known_evidence_ids,
            known_claim_ids=known_claim_ids,
            forbidden_claim_ids=unsupported_claim_ids | excluded_claim_ids,
        )
        for entry in entries
    ]
    missing_evidence = sum(1 for entry in checked_entries if _has_missing_evidence_problem(entry))
    unknown_claims = sum(1 for entry in checked_entries if _has_unknown_claim_problem(entry))
    forbidden_claims = sum(1 for entry in checked_entries if _has_forbidden_claim_problem(entry))
    actions = _recommended_actions(
        entries=checked_entries,
        missing_evidence=missing_evidence,
        unknown_claims=unknown_claims,
        forbidden_claims=forbidden_claims,
    )
    return EvidenceTraceabilityLedger(
        known_evidence_ids=sorted(known_evidence_ids),
        known_claim_ids=sorted(known_claim_ids),
        excluded_claim_ids=sorted(excluded_claim_ids),
        unsupported_claim_ids=sorted(unsupported_claim_ids),
        entries=checked_entries,
        entries_with_missing_evidence=missing_evidence,
        entries_with_unknown_claims=unknown_claims,
        entries_with_forbidden_claims=forbidden_claims,
        hard_gate_passed=missing_evidence == 0 and unknown_claims == 0 and forbidden_claims == 0,
        recommended_actions=actions,
    )


def write_traceability_ledger(path: str | Path, ledger: EvidenceTraceabilityLedger) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(ledger.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_traceability_ledger(path: str | Path) -> EvidenceTraceabilityLedger:
    return EvidenceTraceabilityLedger.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _claim_entries(state: AgenticRunState) -> list[TraceabilityLedgerEntry]:
    entries: list[TraceabilityLedgerEntry] = []
    verification = {
        str(claim.get("claim_id") or ""): claim
        for claim in as_list(artifact_json(state, "claim_verification").get("claims"))
        if isinstance(claim, dict)
    }
    for claim in as_list(artifact_json(state, "claims").get("claims")):
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or "").strip()
        if not claim_id:
            continue
        verified = verification.get(claim_id, {})
        entries.append(
            TraceabilityLedgerEntry(
                entry_id=f"claim:{claim_id}",
                kind="claim",
                source_artifact="claims",
                claim_ids=[claim_id],
                evidence_ids=as_string_list(claim.get("evidence_ids")),
                support_status=str(verified.get("support_status") or claim.get("support_status") or ""),
                notes=as_string_list(verified.get("caveats")),
            )
        )
    return entries


def _text_entries(state: AgenticRunState) -> list[TraceabilityLedgerEntry]:
    entries: list[TraceabilityLedgerEntry] = []
    final_trace = artifact_json(state, "final_text_trace")
    if final_trace:
        for index, trace in enumerate(as_list(final_trace.get("entries")), start=1):
            if not isinstance(trace, dict):
                continue
            atomic_claim_id = str(trace.get("atomic_claim_id") or f"FAC{index}")
            entries.append(
                TraceabilityLedgerEntry(
                    entry_id=f"text:{atomic_claim_id}",
                    kind="text_atomic_claim",
                    source_artifact="final_text_trace",
                    claim_ids=as_string_list(trace.get("projection_claim_ids")),
                    evidence_ids=as_string_list(trace.get("direct_evidence_ids")),
                    support_status=str(trace.get("verdict_status") or ""),
                )
            )
        return entries
    for index, paragraph in enumerate(as_list(artifact_json(state, "text_claims").get("paragraphs")), start=1):
        if not isinstance(paragraph, dict):
            continue
        paragraph_id = str(paragraph.get("paragraph_id") or f"P{index}")
        entries.append(
            TraceabilityLedgerEntry(
                entry_id=f"text:{paragraph_id}",
                kind="text_paragraph",
                source_artifact="text_claims",
                claim_ids=as_string_list(paragraph.get("claim_ids")),
                evidence_ids=as_string_list(paragraph.get("evidence_span_ids")),
            )
        )
    return entries


def _check_entry(
    entry: TraceabilityLedgerEntry,
    *,
    known_evidence_ids: set[str],
    known_claim_ids: set[str],
    forbidden_claim_ids: set[str],
) -> TraceabilityLedgerEntry:
    if entry.kind == "claim" and entry.support_status == "unsupported":
        notes = dedupe([*entry.notes, "unsupported claim is recorded for exclusion from text and figures"])
        return entry.model_copy(update={"trace_status": "excluded_claim", "notes": notes})
    missing_evidence = [evidence_id for evidence_id in entry.evidence_ids if evidence_id not in known_evidence_ids]
    unknown_claims = [claim_id for claim_id in entry.claim_ids if claim_id not in known_claim_ids]
    forbidden_claims = [claim_id for claim_id in entry.claim_ids if claim_id in forbidden_claim_ids]
    notes = list(entry.notes)
    statuses: list[str] = []
    if missing_evidence or (entry.kind in {"claim", "text_paragraph", "text_atomic_claim", "figure_node", "figure_edge"} and not entry.evidence_ids):
        statuses.append("missing_evidence")
        if missing_evidence:
            notes.append("unknown evidence ids: " + ", ".join(missing_evidence[:8]))
        else:
            notes.append("no evidence ids recorded")
    if unknown_claims:
        statuses.append("unknown_claim")
        notes.append("unknown claim ids: " + ", ".join(unknown_claims[:8]))
    if forbidden_claims:
        statuses.append("forbidden_claim")
        notes.append("excluded or unsupported claim ids: " + ", ".join(forbidden_claims[:8]))
    if len(set(statuses)) > 1:
        trace_status = "invalid_trace"
    elif statuses:
        trace_status = statuses[0]
    else:
        trace_status = "supported"
    return entry.model_copy(update={"trace_status": trace_status, "notes": dedupe(notes)})


def _recommended_actions(
    *,
    entries: list[TraceabilityLedgerEntry],
    missing_evidence: int,
    unknown_claims: int,
    forbidden_claims: int,
) -> list[str]:
    actions: list[str] = []
    if not entries:
        actions.append("no_traceable_text_or_figure_entries_yet")
    if missing_evidence:
        actions.append("repair_entries_with_missing_or_unknown_evidence_ids")
    if unknown_claims:
        actions.append("repair_entries_with_unknown_claim_ids")
    if forbidden_claims:
        actions.append("remove_excluded_or_unsupported_claims_from_text_and_figures")
    if not actions:
        actions.append("all_text_claim_and_figure_entries_trace_to_frozen_code_evidence")
    return actions


def _has_missing_evidence_problem(entry: TraceabilityLedgerEntry) -> bool:
    return entry.trace_status == "missing_evidence" or any(
        note.startswith("unknown evidence ids:") or note == "no evidence ids recorded" for note in entry.notes
    )


def _has_unknown_claim_problem(entry: TraceabilityLedgerEntry) -> bool:
    return entry.trace_status == "unknown_claim" or any(note.startswith("unknown claim ids:") for note in entry.notes)


def _has_forbidden_claim_problem(entry: TraceabilityLedgerEntry) -> bool:
    return entry.trace_status == "forbidden_claim" or any(
        note.startswith("excluded or unsupported claim ids:") for note in entry.notes
    )
