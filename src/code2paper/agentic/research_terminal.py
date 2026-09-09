"""Fail-closed terminal proof for Research obligations.

Status strings are mutable scheduling state.  This module is the single
deterministic proof boundary used when a caller needs to decide whether an
obligation may leave the research queue.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json


class ResearchClosureAdmissionV1(BaseModel):
    """Research-to-authoring pre-admission, persisted before model calls.

    This is deliberately smaller than a Formalizer/Writer admission: those
    phases may not have been planned when Research is blocked, so their phase
    artifacts are not fabricated as placeholders.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    admission_id: str
    run_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    research_status: str
    model_calls_allowed: bool = False
    downstream_phases_planned: tuple[str, ...] = Field(default_factory=tuple)
    failure_codes: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "ResearchClosureAdmissionV1":
        if not self.admission_id.strip() or not self.run_id.strip():
            raise ValueError("research closure admission requires admission and run ids")
        if not self.repo_snapshot_id.strip() or not self.project_tree_hash.strip():
            raise ValueError("research closure admission requires snapshot identity")
        if self.failure_codes and self.model_calls_allowed:
            raise ValueError("failed research closure cannot allow model calls")
        expected = digest_json(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("research closure admission content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


def build_research_closure_admission(
    *,
    run_id: str,
    repo_snapshot_id: str,
    project_tree_hash: str,
    research_status: str,
    failure_codes: Iterable[str] = (),
    downstream_phases_planned: Iterable[str] = (),
) -> ResearchClosureAdmissionV1:
    """Create the single gate between Research and model-backed authoring."""

    failures = tuple(dict.fromkeys(
        str(value).strip() for value in failure_codes if str(value).strip()
    ))
    status = str(research_status or "incomplete").strip() or "incomplete"
    return ResearchClosureAdmissionV1(
        admission_id=digest_json({
            "run_id": run_id,
            "repo_snapshot_id": repo_snapshot_id,
            "project_tree_hash": project_tree_hash,
            "research_status": status,
            "failure_codes": failures,
        }),
        run_id=str(run_id or "").strip(),
        repo_snapshot_id=str(repo_snapshot_id or "").strip(),
        project_tree_hash=str(project_tree_hash or "").strip(),
        research_status=status,
        model_calls_allowed=not failures,
        downstream_phases_planned=tuple(dict.fromkeys(
            str(value).strip()
            for value in downstream_phases_planned
            if str(value).strip()
        )),
        failure_codes=failures,
    )


class ObligationTerminalProofV1(BaseModel):
    """Evidence-backed terminal decision for one agenda obligation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    obligation_id: str
    agenda_status: str
    terminal: bool = False
    promoted_repository_evidence: bool = False
    bounded_search_exhausted: bool = False
    explicit_gap_bound: bool = False
    qualifier_clear: bool = False
    promoted_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ObligationTerminalProofV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", digest_json(payload))
        return self


def _value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _terminal_gap_bound(item: Any) -> bool:
    requirements = tuple(_value(item, "gap_requirements", ()) or ())
    return bool(requirements) and all(
        str(_value(req, "terminal", "open") or "open") == "explicit_gap"
        for req in requirements
    )


def _search_exhausted(item: Any, *, explicit_gap_bound: bool) -> bool:
    if explicit_gap_bound:
        return True
    for value in (_value(item, "missing_information", ()) or ()):
        text = str(value or "").casefold()
        if "bounded_search_exhausted" in text or text.startswith("search_exhausted:"):
            return True
    return False


def _qualifier_clear(item: Any) -> bool:
    # Qualifier requirements are typed by the agenda builder.  Do not infer
    # their absence from prose; only an explicit qualifier disposition closes
    # the lane.  Existing obligations with no qualifier field remain clear.
    for value in (_value(item, "missing_information", ()) or ()):
        text = str(value or "").casefold()
        if text.startswith("qualifier:") or "required_qualifier:" in text:
            return False
    return True


def _record_claim_ids(records: Iterable[Any]) -> tuple[str, ...]:
    values: list[str] = []
    for record in records:
        status = str(_value(record, "status", "") or "")
        if status != "claim_promoted":
            continue
        values.extend(
            str(value).strip()
            for value in (_value(record, "claim_ids", ()) or ())
            if str(value).strip()
        )
    return tuple(dict.fromkeys(values))


def evaluate_obligation_terminal_proof(
    item: Any,
    *,
    promotion_records: Iterable[Any] = (),
    promoted_claim_ids: Iterable[str] = (),
    search_exhausted: bool | None = None,
) -> ObligationTerminalProofV1:
    """Evaluate whether an agenda item has a complete terminal proof.

    ``supported`` requires repository-promoted claims.  ``partial`` requires
    the same promotion plus a bounded, explicit gap and a clear qualifier
    boundary.  A status string or a discovery hit alone is never sufficient.
    """

    obligation_id = str(_value(item, "obligation_id", "") or "").strip()
    agenda_status = str(_value(item, "status", "") or "")
    record_claims = _record_claim_ids(promotion_records)
    claims = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in (*record_claims, *tuple(promoted_claim_ids))
            if str(value).strip()
        )
    )
    promoted = bool(claims)
    explicit_gap_bound = _terminal_gap_bound(item)
    exhausted = (
        _search_exhausted(item, explicit_gap_bound=explicit_gap_bound)
        if search_exhausted is None
        else bool(search_exhausted)
    )
    qualifier_clear = _qualifier_clear(item)
    reasons: list[str] = []
    terminal = False
    if agenda_status == "supported":
        if promoted:
            terminal = True
        else:
            reasons.append("promoted_repository_evidence_missing")
    elif agenda_status == "partial":
        if not promoted:
            reasons.append("promoted_repository_evidence_missing")
        if not exhausted:
            reasons.append("bounded_search_not_exhausted")
        if not explicit_gap_bound:
            reasons.append("explicit_gap_not_bound_to_missing_field")
        if not qualifier_clear:
            reasons.append("required_qualifier_not_closed")
        terminal = promoted and exhausted and explicit_gap_bound and qualifier_clear
    elif agenda_status == "explicit_gap":
        terminal = explicit_gap_bound
        if not terminal:
            reasons.append("explicit_gap_requirements_not_terminal")
    elif agenda_status == "blocked":
        terminal = True
    else:
        reasons.append("agenda_status_not_terminal")

    return ObligationTerminalProofV1(
        obligation_id=obligation_id,
        agenda_status=agenda_status,
        terminal=terminal,
        promoted_repository_evidence=promoted,
        bounded_search_exhausted=exhausted,
        explicit_gap_bound=explicit_gap_bound,
        qualifier_clear=qualifier_clear,
        promoted_claim_ids=claims,
        reasons=tuple(dict.fromkeys(reasons)),
    )


__all__ = [
    "ResearchClosureAdmissionV1",
    "build_research_closure_admission",
    "ObligationTerminalProofV1",
    "evaluate_obligation_terminal_proof",
]
