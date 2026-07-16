from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TraceabilityLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    kind: str
    source_artifact: str
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    support_status: str = ""
    trace_status: str = "supported"
    notes: list[str] = Field(default_factory=list)


class EvidenceTraceabilityLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-evidence-traceability-ledger"
    known_evidence_ids: list[str] = Field(default_factory=list)
    known_claim_ids: list[str] = Field(default_factory=list)
    excluded_claim_ids: list[str] = Field(default_factory=list)
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    entries: list[TraceabilityLedgerEntry] = Field(default_factory=list)
    entries_with_missing_evidence: int = 0
    entries_with_unknown_claims: int = 0
    entries_with_forbidden_claims: int = 0
    hard_gate_passed: bool = True
    recommended_actions: list[str] = Field(default_factory=list)
