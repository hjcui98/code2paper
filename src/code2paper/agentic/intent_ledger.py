"""IntentImplementationLedger and intent-coverage-driven scheduler for Method Research.

Implements section 5.5 of the Unified Mechanism Context Optimization Execution Plan:
- Tracks every core author-intent clause through discovery, read, promotion, and terminal status.
- Eliminates single 'coverage' blending by strictly partitioning into 7 mutually exclusive statuses.
- Enforces minimum research contract and intent-coverage-driven scheduling metrics.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json

IntentImplementationStatus = Literal[
    "implemented_exact",
    "implemented_partial",
    "author_spec_only",
    "repo_mismatch",
    "inactive_alternative",
    "not_found_after_bounded_search",
    "out_of_scope",
]

VALID_INTENT_IMPLEMENTATION_STATUSES: tuple[str, ...] = (
    "implemented_exact",
    "implemented_partial",
    "author_spec_only",
    "repo_mismatch",
    "inactive_alternative",
    "not_found_after_bounded_search",
    "out_of_scope",
)


class IntentImplementationLedgerItemV1(BaseModel):
    """Execution and implementation disposition for one author-intent clause."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    clause_id: str
    clause_text: str = ""
    is_core: bool = True
    status: IntentImplementationStatus = "not_found_after_bounded_search"
    query_attempts: tuple[str, ...] = Field(default_factory=tuple)
    first_party_candidates: tuple[str, ...] = Field(default_factory=tuple)
    candidate_symbols_read: tuple[str, ...] = Field(default_factory=tuple)
    promotion_attempted: bool = False
    promoted_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    promoted_operation_ids: tuple[str, ...] = Field(default_factory=tuple)
    rejection_code: str = ""
    evidence_authority: str = "author_spec_only"
    terminal_disposition_reason: str = ""


class IntentImplementationLedgerV1(BaseModel):
    """Aggregate ledger tracking intent clause coverage and research progress."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    items: tuple[IntentImplementationLedgerItemV1, ...] = Field(default_factory=tuple)

    # 6 Section 5.5 metrics:
    core_intent_attempt_coverage: float = 0.0
    first_party_candidate_read_rate: float = 0.0
    observation_promotion_rate: float = 0.0
    typed_rejection_coverage: float = 0.0
    novelty_mechanism_budget_share: float = 0.0
    no_progress_compile_count: int = 0
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "IntentImplementationLedgerV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = digest_json(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"intent implementation ledger content_digest mismatch: got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


def build_intent_implementation_ledger(
    *,
    clauses: Sequence[Mapping[str, Any] | Any],
    queries_by_clause: Mapping[str, Sequence[str]] | None = None,
    candidates_by_clause: Mapping[str, Sequence[str]] | None = None,
    read_symbols_by_clause: Mapping[str, Sequence[str]] | None = None,
    promoted_facts_by_clause: Mapping[str, Sequence[str]] | None = None,
    promoted_operations_by_clause: Mapping[str, Sequence[str]] | None = None,
    rejections_by_clause: Mapping[str, str] | None = None,
    statuses_by_clause: Mapping[str, str] | None = None,
    repo_snapshot_id: str = "",
    project_tree_hash: str = "",
    total_budget_turns: int = 1,
    novelty_budget_turns: int = 1,
    compile_events: Sequence[Mapping[str, Any]] | None = None,
) -> IntentImplementationLedgerV1:
    """Build the canonical IntentImplementationLedgerV1 and compute coverage metrics."""

    q_map = queries_by_clause or {}
    c_map = candidates_by_clause or {}
    r_map = read_symbols_by_clause or {}
    f_map = promoted_facts_by_clause or {}
    op_map = promoted_operations_by_clause or {}
    rej_map = rejections_by_clause or {}
    stat_map = statuses_by_clause or {}

    ledger_items: list[IntentImplementationLedgerItemV1] = []
    total_core = 0
    attempted_core = 0
    total_candidates = 0
    read_candidates = 0
    read_observations = 0
    promoted_observations = 0
    unpromoted_candidates = 0
    typed_rejections = 0

    for item in clauses:
        cid = str(
            item.get("clause_id")
            if isinstance(item, Mapping)
            else getattr(item, "clause_id", getattr(item, "obligation_id", ""))
        ).strip()
        if not cid:
            continue
        text = str(
            item.get("clause_text")
            if isinstance(item, Mapping)
            else getattr(item, "clause_text", getattr(item, "author_text", ""))
        ).strip()
        is_core = bool(
            item.get("is_core", True)
            if isinstance(item, Mapping)
            else getattr(item, "is_core", getattr(item, "priority", "must_cover") in ("must_cover", "should_cover"))
        )

        queries = tuple(dict.fromkeys(str(q).strip() for q in q_map.get(cid, ()) if str(q).strip()))
        candidates = tuple(dict.fromkeys(str(c).strip() for c in c_map.get(cid, ()) if str(c).strip()))
        reads = tuple(dict.fromkeys(str(r).strip() for r in r_map.get(cid, ()) if str(r).strip()))
        facts = tuple(dict.fromkeys(str(f).strip() for f in f_map.get(cid, ()) if str(f).strip()))
        ops = tuple(dict.fromkeys(str(o).strip() for o in op_map.get(cid, ()) if str(o).strip()))
        rejection = str(rej_map.get(cid, "")).strip()

        # A seeded candidate is a hypothesis, not a research attempt.  Core
        # breadth coverage must be earned by an actual query/read action or a
        # typed rejection; otherwise an intent-only candidate can make a
        # never-searched obligation look attempted.
        has_attempt = bool(queries or rejection)
        if is_core:
            total_core += 1
            if has_attempt:
                attempted_core += 1

        total_candidates += len(candidates)
        read_candidates += len(reads)
        read_observations += len(reads)

        promoted_count = len(facts) + len(ops)
        promoted_observations += min(len(reads), promoted_count) if reads else promoted_count
        if len(candidates) > len(facts) + len(ops):
            unpromoted_candidates += len(candidates) - (len(facts) + len(ops))
            if rejection:
                typed_rejections += 1

        # Determine terminal status
        raw_status = str(stat_map.get(cid, "")).strip()
        if raw_status in VALID_INTENT_IMPLEMENTATION_STATUSES:
            status = raw_status
        elif facts and ops:
            status = "implemented_exact"
        elif facts or ops:
            status = "implemented_partial"
        elif rejection:
            status = "repo_mismatch" if "mismatch" in rejection else "not_found_after_bounded_search"
        elif queries:
            status = "not_found_after_bounded_search"
        else:
            status = "author_spec_only"

        authority = "repository_verified" if status == "implemented_exact" else (
            "repository_partial" if status == "implemented_partial" else "author_spec_only"
        )

        ledger_items.append(
            IntentImplementationLedgerItemV1(
                clause_id=cid,
                clause_text=text,
                is_core=is_core,
                status=status,  # type: ignore[arg-type]
                query_attempts=queries,
                first_party_candidates=candidates,
                candidate_symbols_read=reads,
                promotion_attempted=bool(reads and (facts or ops or rejection)),
                promoted_fact_ids=facts,
                promoted_operation_ids=ops,
                rejection_code=rejection,
                evidence_authority=authority,
                terminal_disposition_reason=(
                    f"promoted:{len(facts)}facts,{len(ops)}ops"
                    if (facts or ops)
                    else (rejection or status)
                ),
            )
        )

    # Compute metrics
    core_attempt_coverage = (
        round(attempted_core / total_core, 4) if total_core > 0 else 1.0
    )
    read_rate = (
        round(read_candidates / total_candidates, 4) if total_candidates > 0 else 1.0
    )
    promotion_rate = (
        round(promoted_observations / read_observations, 4) if read_observations > 0 else 1.0
    )
    rejection_coverage = (
        round(typed_rejections / max(1, unpromoted_candidates), 4)
        if unpromoted_candidates > 0
        else 1.0
    )
    novelty_share = (
        round(novelty_budget_turns / max(1, total_budget_turns), 4)
    )

    # Count consecutive no-progress compiles
    no_progress_count = 0
    if compile_events:
        for event in compile_events:
            delta = (
                int(event.get("new_facts_count", 0))
                + int(event.get("new_claims_count", 0))
                + int(event.get("new_typed_slots_count", 0))
                + int(event.get("new_operations_count", 0))
            )
            if delta == 0 and not event.get("has_coverage_gain", False):
                no_progress_count += 1
            else:
                no_progress_count = 0

    return IntentImplementationLedgerV1(
        repo_snapshot_id=str(repo_snapshot_id),
        project_tree_hash=str(project_tree_hash),
        items=tuple(ledger_items),
        core_intent_attempt_coverage=core_attempt_coverage,
        first_party_candidate_read_rate=read_rate,
        observation_promotion_rate=promotion_rate,
        typed_rejection_coverage=rejection_coverage,
        novelty_mechanism_budget_share=novelty_share,
        no_progress_compile_count=no_progress_count,
    )


class IntentCoverageScheduler:
    """Scheduler ensuring intent-coverage-driven research allocation."""

    def __init__(
        self,
        *,
        min_novelty_budget_ratio: float = 0.5,
        max_no_progress_compiles: int = 2,
    ) -> None:
        self.min_novelty_budget_ratio = min_novelty_budget_ratio
        self.max_no_progress_compiles = max_no_progress_compiles

    def check_next_schedule(
        self,
        ledger: IntentImplementationLedgerV1,
        *,
        remaining_budget_turns: int,
        current_action_is_novelty: bool = True,
    ) -> dict[str, Any]:
        """Assess research progress and determine scheduling guidance.

        Enforces:
        - Prioritizes unattempted core clauses before general exploration.
        - Detects stalling on compile without progress.
        - Preserves reserved turns for unattempted core clauses.
        """
        unattempted_core = [
            item.clause_id
            for item in ledger.items
            if item.is_core and len(item.query_attempts) == 0 and len(item.first_party_candidates) == 0
        ]
        needs_replan = ledger.no_progress_compile_count >= self.max_no_progress_compiles
        reserve_turns_needed = len(unattempted_core)
        budget_constrained = remaining_budget_turns <= reserve_turns_needed

        must_prioritize_core = (
            len(unattempted_core) > 0 and (budget_constrained or not current_action_is_novelty)
        )

        return {
            "can_continue": not (needs_replan and budget_constrained),
            "needs_replan": needs_replan,
            "must_prioritize_core": must_prioritize_core,
            "unattempted_core_clause_ids": tuple(unattempted_core),
            "unresolved_core_clause_ids": tuple(
                item.clause_id
                for item in ledger.items
                if item.is_core
                and (
                    (
                        bool(item.first_party_candidates)
                        and not item.candidate_symbols_read
                        and not item.rejection_code
                        and item.status not in {
                            "repo_mismatch",
                            "out_of_scope",
                        }
                    )
                    or (
                        bool(item.candidate_symbols_read)
                        and not item.promotion_attempted
                        and not item.rejection_code
                    )
                )
            ),
            "reserve_turns_needed": reserve_turns_needed,
            "budget_constrained": budget_constrained,
            "core_intent_attempt_coverage": ledger.core_intent_attempt_coverage,
        }


__all__ = [
    "IntentImplementationStatus",
    "VALID_INTENT_IMPLEMENTATION_STATUSES",
    "IntentImplementationLedgerItemV1",
    "IntentImplementationLedgerV1",
    "build_intent_implementation_ledger",
    "IntentCoverageScheduler",
]
