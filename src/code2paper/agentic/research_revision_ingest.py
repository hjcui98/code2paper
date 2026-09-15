"""R10 revision submission and harness ingestion.

§15.2 separates *who may propose* from *who may decide*:

* the research loop (model or deterministic fallback) may only **submit** a
  :class:`RevisionProposalV1` through the ``propose_target_revision`` tool;
* the harness **ingests** that submission: it re-derives the proposal
  identity, authenticates every cited reference against the R9 execution
  ledger, spends the run's proposal budget and applies the revision through
  :func:`revise_research_targets`, which is the single application point.

Nothing in this module trusts the submitting call.  The tool writes a frozen
submission envelope under the run's artifact root; ingestion re-reads it,
verifies its digest, and rejects any proposal that cites a reference the
execution layer never recorded.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.research_revision_contract import (
    RevisionApplicationV1,
    RevisionJournalV1,
    RevisionProposalV1,
    RevisionTargetV1,
    revise_research_targets,
)


#: Tool name the loop uses to submit a proposal.  It is a submission surface,
#: never an acceptance surface.
REVISION_PROPOSAL_TOOL_NAME = "propose_target_revision"

#: Artifact kind (directory) that holds submitted proposals.
REVISION_PROPOSAL_ARTIFACT_KIND = "target_revision_proposals"

#: Artifact kind that holds the harness ingestion result of one loop boundary.
REVISION_INGEST_ARTIFACT_KIND = "research_revision_ingests"

#: Default number of target revisions one run may *apply*.  The charge is one
#: per applied revision and is decided by the harness: a proposal cannot make
#: itself free by requesting zero budget.  The remaining count is derived from
#: the append-only journal, so a resume cannot refill it.
DEFAULT_REVISION_PROPOSAL_BUDGET = 3

#: Default research allowance a run's revisions may request in total.  This is a
#: *request* budget for the new sub-question's research, kept separate from the
#: application count and from the per-obligation tool budget the loop owns.
DEFAULT_REVISION_RESEARCH_ALLOWANCE = 6

RevisionIngestStatus = Literal[
    "applied",
    "rejected",
    "pending_review",
    "already_applied",
    "invalid",
]


def _digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class RevisionProposalSubmissionV1(BaseModel):
    """The frozen envelope the tool writes; the harness reads only this."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    proposal: RevisionProposalV1
    tool_call_id: str = ""
    obligation_id: str = ""
    content_digest: str = ""

    def model_post_init(self, __context: Any) -> None:
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))


class RevisionIngestOutcomeV1(BaseModel):
    """What the harness did with one submitted proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    proposal_id: str
    revision_id: str
    submission_digest: str = ""
    parent_obligation_id: str = ""
    status: RevisionIngestStatus
    verdict: str = ""
    failures: tuple[str, ...] = Field(default_factory=tuple)
    assessment_id: str = ""
    # ``budget_spent`` is the harness application charge (always 1 for an
    # applied revision); the research allowance request is reported separately.
    budget_spent: int = 0
    budget_remaining: int = 0
    application_charge: int = 0
    research_allowance_requested: int = 0
    research_allowance_remaining: int = 0
    applied_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    removed_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    revalidation_rows: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    content_digest: str = ""

    def model_post_init(self, __context: Any) -> None:
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))


class RevisionIngestResultV1(BaseModel):
    """The append-only outcome record of one ingestion pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    run_id: str = ""
    outcomes: tuple[RevisionIngestOutcomeV1, ...] = Field(default_factory=tuple)
    journal: RevisionJournalV1 = Field(default_factory=RevisionJournalV1)
    applied_count: int = 0
    budget_remaining: int = 0
    research_allowance_remaining: int = 0
    ledger_failures: tuple[str, ...] = Field(default_factory=tuple)
    current_revision_id: str = ""
    content_digest: str = ""

    def model_post_init(self, __context: Any) -> None:
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))

    def applied_outcomes(self) -> tuple[RevisionIngestOutcomeV1, ...]:
        return tuple(
            outcome for outcome in self.outcomes if outcome.status == "applied"
        )


def _digest(payload: Any) -> str:
    return _sha256(json.dumps(payload, sort_keys=True, default=str))


# ---------------------------------------------------------------------------
# Submission store
# ---------------------------------------------------------------------------


def proposal_directory(artifact_root: Any) -> Path | None:
    """Return the submission directory under an artifact root."""

    if artifact_root is None:
        return None
    return (
        Path(artifact_root)
        / "research_tool_artifacts"
        / REVISION_PROPOSAL_ARTIFACT_KIND
    )


def proposal_path(artifact_root: Any, revision_id: str) -> Path | None:
    directory = proposal_directory(artifact_root)
    if directory is None:
        return None
    safe_id = _sha256(str(revision_id))
    return directory / f"{safe_id}.json"


def persist_revision_proposal(
    artifact_root: Any,
    proposal: RevisionProposalV1,
    *,
    tool_call_id: str = "",
) -> Path:
    """Write one submission envelope, idempotently.

    The path is derived from the proposal's content identity, so a replayed
    submission of the same proposal lands on the same file.  Bytes that
    differ under the same identity mean the store was tampered with; that is
    refused instead of overwritten.
    """

    path = proposal_path(artifact_root, proposal.revision_id)
    if path is None:
        raise ValueError("revision proposal store is unavailable")
    submission = RevisionProposalSubmissionV1(
        proposal=proposal,
        tool_call_id=str(tool_call_id or ""),
        obligation_id=proposal.parent_obligation_id,
    )
    payload = submission.model_dump(mode="json")
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"revision_proposal_unreadable:{path.name}:{exc}"
            ) from exc
        if existing != payload:
            raise ValueError(
                "revision_proposal_identity_conflict:"
                f"{proposal.revision_id}"
            )
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    from code2paper.agentic.tool_runtime import atomic_write_json

    atomic_write_json(path, payload)
    return path


def iter_revision_submissions(
    artifact_root: Any,
) -> tuple[RevisionProposalSubmissionV1, ...]:
    """Load every submitted proposal in deterministic order.

    Ordering is by submission identity (``tool_call_id`` then file name) so a
    resume reads the same sequence the original run read; a file whose bytes
    do not re-derive its own identity raises instead of being skipped.
    """

    directory = proposal_directory(artifact_root)
    if directory is None or not directory.is_dir():
        return ()
    submissions: list[RevisionProposalSubmissionV1] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"revision_proposal_unreadable:{path.name}:{exc}") from exc
        submission = RevisionProposalSubmissionV1.model_validate(payload)
        expected = proposal_path(artifact_root, submission.proposal.revision_id)
        if expected is not None and expected.name != path.name:
            raise ValueError(
                "revision_proposal_path_identity_mismatch:"
                f"{submission.proposal.revision_id}"
            )
        if submission.content_digest != _digest(
            submission.model_dump(mode="json", exclude={"content_digest"})
        ):
            raise ValueError(
                "revision_proposal_digest_mismatch:"
                f"{submission.proposal.revision_id}"
            )
        submissions.append(submission)
    submissions.sort(key=lambda item: (item.tool_call_id, item.proposal.revision_id))
    return tuple(submissions)


# ---------------------------------------------------------------------------
# Ledger-authenticated observations
# ---------------------------------------------------------------------------


def authenticated_observed_ref_ids(
    ctx: Any,
    obligation_ids: Iterable[str] = (),
    *,
    failures: list[str] | None = None,
) -> tuple[str, ...]:
    """Return the refs this run's execution ledger actually produced.

    Only executions recorded by the R9 ledger count.  A corrupt ledger yields
    no authenticated refs (and a typed failure) so a proposal citing those
    refs cannot be accepted on the strength of an unreadable record.
    """

    from code2paper.agentic.research_execution_ledger import (
        ExecutionLedgerError,
        iter_execution_records,
    )

    snapshot_id = str(getattr(ctx.repo_snapshot, "snapshot_id", "") or "")
    tree_hash = str(getattr(ctx.repo_snapshot, "project_tree_hash", "") or "")
    refs: list[str] = []
    for obligation_id in dict.fromkeys(
        str(value) for value in obligation_ids if str(value).strip()
    ):
        try:
            records = iter_execution_records(ctx, obligation_id)
        except ExecutionLedgerError as exc:
            if failures is not None:
                failures.append(f"revision_ledger_unreadable:{obligation_id}:{exc}")
            continue
        for record in records:
            if str(getattr(record, "tool_name", "") or "") == (
                REVISION_PROPOSAL_TOOL_NAME
            ):
                # Defensive: a submission is never repository evidence, so if a
                # future ledger classification ever records it, it still cannot
                # authenticate the next proposal's citations.
                continue
            if (
                snapshot_id
                and str(getattr(record, "repo_snapshot_id", "")) != snapshot_id
            ):
                continue
            if tree_hash and str(getattr(record, "project_tree_hash", "")) != tree_hash:
                continue
            for value in (
                *(getattr(record, "result_ids", ()) or ()),
                *(getattr(record, "read_ids", ()) or ()),
                *(getattr(record, "relation_checks", ()) or ()),
            ):
                text = str(value or "").strip()
                if text:
                    refs.append(text)
            # A read record keeps its exact spans structurally; the span id the
            # observation returned is authenticated by that record even though
            # the string itself is derived here.
            for span in getattr(record, "read_spans", ()) or ():
                path = str(getattr(span, "path", "") or "").strip()
                if not path:
                    continue
                refs.append(
                    f"span:{path}:{int(getattr(span, 'start_line', 0) or 0)}:"
                    f"{int(getattr(span, 'end_line', 0) or 0)}"
                )
    return tuple(dict.fromkeys(refs))


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def _parse_span_ref(ref: str) -> tuple[str, int, int] | None:
    parts = str(ref).split(":")
    if len(parts) != 4 or parts[0] != "span":
        return None
    try:
        return parts[1], int(parts[2]), int(parts[3])
    except ValueError:
        return None


def _ref_rel_path(ref: str) -> str:
    text = str(ref)
    if text.startswith("span:"):
        parts = text.split(":")
        return ":".join(parts[1:-2]) if len(parts) >= 4 else ""
    if text.startswith(("symbol:", "behavior:")):
        parts = text.split(":")
        return ":".join(parts[1:-2]) if len(parts) >= 4 else ""
    return ""


def _resolve_v2_symbol_index(
    ctx: Any,
    symbol_index: Any | None,
    rel_paths: Iterable[str],
) -> Any | None:
    """Return a V2 symbol index that covers the cited files.

    The behavior extractor needs ``SymbolIndexV2``; the R1 symbol report the
    tool context caches does not qualify, so an index is built from the frozen
    snapshot bytes when the caller has not supplied one.
    """

    wanted = {str(path) for path in rel_paths if str(path).strip()}
    for candidate in (symbol_index, getattr(ctx, "symbol_index", None)):
        if candidate is None or not hasattr(candidate, "symbols"):
            continue
        covered = {
            str(getattr(symbol, "path", "") or "")
            for symbol in (getattr(candidate, "symbols", ()) or ())
        }
        if not wanted or wanted <= covered:
            return candidate
    adapter = ctx.language_adapter()
    from code2paper.agentic.research_tools import _read_snapshot_file

    files: dict[str, str] = {}
    for path in sorted(wanted):
        text, read_error = _read_snapshot_file(ctx.repo_snapshot, path)
        if read_error is None and text:
            files[path] = text
    if not files:
        return None
    try:
        return adapter.index_symbols(
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            project_tree_hash=ctx.repo_snapshot.project_tree_hash,
            files=files,
        )
    except Exception:  # pragma: no cover - unparsable input yields no support
        return None


def _predicate_index_for_file(
    ctx: Any,
    rel_path: str,
    symbols_index: Any | None,
) -> tuple[tuple[int, int, str], ...]:
    """Extract ``(start, end, predicate)`` rows for one snapshot file."""

    from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph
    from code2paper.agentic.research_tools import _read_snapshot_file

    text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
    if read_error is not None or not text:
        return ()
    if symbols_index is None:
        return ()
    symbol_ids = [
        str(getattr(symbol, "symbol_id", "") or "")
        for symbol in (getattr(symbols_index, "symbols", ()) or ())
        if str(getattr(symbol, "path", "") or "") == rel_path
        and str(getattr(symbol, "symbol_id", "") or "")
    ]
    if not symbol_ids:
        return ()
    try:
        result = build_behavior_subgraph(
            adapter=ctx.language_adapter(),
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            project_tree_hash=ctx.repo_snapshot.project_tree_hash,
            files={rel_path: text},
            symbol_index=symbols_index,
            symbol_ids=symbol_ids,
            depth=0,
        )
    except Exception:  # pragma: no cover - unparsable file yields no support
        return ()
    rows: list[tuple[int, int, str]] = []
    for node in getattr(result.graph, "nodes", ()) or ():
        span = _parse_span_ref(str(getattr(node, "source_span_id", "") or ""))
        predicate = str(getattr(node, "predicate", "") or "")
        if span is None or not predicate:
            continue
        rows.append((span[1], span[2], predicate))
    return tuple(rows)


def cited_predicate_support(
    ctx: Any,
    refs: Iterable[str],
    *,
    behavior_graph: Any | None = None,
    symbol_index: Any | None = None,
) -> dict[str, tuple[str, ...]]:
    """Map each cited ref to the predicates the run really extracted for it.

    Support comes from two deterministic sources: the run's live behavior graph
    (``source_span_id -> predicate``) and, for a cited span or symbol the graph
    has not covered yet, the same static extractor run over the frozen snapshot
    file.  A ref with no extracted support maps to an empty tuple, so a
    proposal citing it can never be accepted on the citation alone.
    """

    support: dict[str, set[str]] = {}
    for node in (getattr(behavior_graph, "nodes", ()) or ()):
        span = str(getattr(node, "source_span_id", "") or "")
        predicate = str(getattr(node, "predicate", "") or "")
        if span and predicate:
            support.setdefault(span, set()).add(predicate)
    ordered_refs = list(
        dict.fromkeys(str(value) for value in refs if str(value).strip())
    )
    index = _resolve_v2_symbol_index(
        ctx,
        symbol_index,
        (_ref_rel_path(ref) for ref in ordered_refs),
    )
    symbols_by_path: dict[str, list[Any]] = {}
    for symbol in (getattr(index, "symbols", ()) or ()):
        symbols_by_path.setdefault(
            str(getattr(symbol, "path", "") or ""), []
        ).append(symbol)
    file_rows: dict[str, tuple[tuple[int, int, str], ...]] = {}
    for text in ordered_refs:
        span = _parse_span_ref(text)
        if span is None and text.startswith(("symbol:", "behavior:")):
            path = _ref_rel_path(text)
            parts = text.split(":")
            name = parts[-2] if len(parts) >= 4 else ""
            try:
                line = int(parts[-1])
            except ValueError:
                line = 0
            span = (path, line, line)
            for symbol in symbols_by_path.get(path, ()):
                if str(getattr(symbol, "qualified_name", "") or "") != name:
                    continue
                # A symbol ref covers the symbol's whole snapshot span.
                span = (
                    path,
                    int(getattr(symbol, "start_line", line) or line),
                    int(getattr(symbol, "end_line", line) or line),
                )
                break
        if span is None:
            support.setdefault(text, set())
            continue
        path, start, end = span
        if path not in file_rows:
            file_rows[path] = _predicate_index_for_file(ctx, path, index)
        predicates = set(support.get(text, set()))
        for row_start, row_end, predicate in file_rows[path]:
            if row_start <= end and row_end >= start:
                predicates.add(predicate)
        support[text] = predicates
    return {key: tuple(sorted(value)) for key, value in support.items()}


def _compiled_sets(
    compiled_by_obligation: Mapping[str, Any] | None,
    obligation_id: str,
) -> tuple[Any | None, Any | None]:
    compiled = (compiled_by_obligation or {}).get(obligation_id)
    if compiled is None:
        return None, None
    return (
        getattr(compiled, "fact_set", None),
        getattr(compiled, "claim_set", None),
    )


def ingest_revision_submissions(
    *,
    runtime: Any,
    artifact_root: Any = None,
    journal: RevisionJournalV1 | None = None,
    remaining_budget: int | None = None,
    remaining_research_allowance: int | None = None,
    semantic_verifier: Callable[[Any, RevisionTargetV1], bool] | None = None,
    compiled_by_obligation: Mapping[str, Any] | None = None,
    object_digests_by_obligation: Mapping[str, Mapping[str, str]] | None = None,
    behavior_graph: Any | None = None,
    symbol_index: Any | None = None,
) -> RevisionIngestResultV1:
    """Assess and apply every pending submission against the live research state.

    ``remaining_budget`` is the harness-owned count of revisions this run may
    still *apply*.  One application costs one, whatever the proposal requests,
    and the count is bounded by the append-only journal so a resume cannot
    refill it.  ``remaining_research_allowance`` bounds the separate research
    budget the proposals request (``budget_requests``).  Both are distinct from
    the per-obligation tool budget the loop already spends.
    """

    if artifact_root is None:
        artifact_root = getattr(runtime, "artifact_root", None)
    if journal is None:
        journal = RevisionJournalV1()
    applied_so_far = len(getattr(journal, "entries", ()) or ())
    journal_bound = max(0, DEFAULT_REVISION_PROPOSAL_BUDGET - applied_so_far)
    budget = (
        journal_bound
        if remaining_budget is None
        else max(0, min(int(remaining_budget), journal_bound))
    )
    requested_so_far = sum(
        max(0, int(getattr(entry, "requested_budget", 0) or 0))
        for entry in (getattr(journal, "entries", ()) or ())
    )
    allowance = (
        max(0, DEFAULT_REVISION_RESEARCH_ALLOWANCE - requested_so_far)
        if remaining_research_allowance is None
        else max(
            0,
            min(
                int(remaining_research_allowance),
                DEFAULT_REVISION_RESEARCH_ALLOWANCE - requested_so_far,
            ),
        )
    )
    ledger_failures: list[str] = []
    try:
        submissions = iter_revision_submissions(artifact_root)
    except ValueError as exc:
        return RevisionIngestResultV1(
            run_id=str(getattr(runtime, "run_id", "") or ""),
            journal=journal,
            budget_remaining=budget,
            research_allowance_remaining=allowance,
            ledger_failures=(str(exc),),
            current_revision_id=journal.current_revision_id(),
        )

    outcomes: list[RevisionIngestOutcomeV1] = []
    applied_count = 0
    for submission in submissions:
        proposal = submission.proposal
        if journal.has_applied(proposal.revision_id):
            outcomes.append(
                RevisionIngestOutcomeV1(
                    proposal_id=proposal.proposal_id,
                    revision_id=proposal.revision_id,
                    submission_digest=submission.content_digest,
                    parent_obligation_id=proposal.parent_obligation_id,
                    status="already_applied",
                    budget_remaining=budget,
                )
            )
            continue
        known_obligations = {
            str(getattr(obligation, "obligation_id", "") or "")
            for obligation in (
                getattr(getattr(runtime, "intent_graph", None), "obligations", ())
                or ()
            )
        }
        if (
            known_obligations
            and proposal.parent_obligation_id not in known_obligations
        ):
            # Report the wrong owner first: a citation failure would hide it.
            outcomes.append(
                RevisionIngestOutcomeV1(
                    proposal_id=proposal.proposal_id,
                    revision_id=proposal.revision_id,
                    submission_digest=submission.content_digest,
                    parent_obligation_id=proposal.parent_obligation_id,
                    status="rejected",
                    verdict="rejected",
                    failures=(
                        f"revision_unknown_parent:{proposal.parent_obligation_id}",
                    ),
                    budget_remaining=budget,
                )
            )
            continue
        if budget <= 0:
            outcomes.append(
                RevisionIngestOutcomeV1(
                    proposal_id=proposal.proposal_id,
                    revision_id=proposal.revision_id,
                    submission_digest=submission.content_digest,
                    parent_obligation_id=proposal.parent_obligation_id,
                    status="rejected",
                    verdict="rejected",
                    failures=(
                        "revision_application_budget_exhausted:"
                        f"{budget}/{DEFAULT_REVISION_PROPOSAL_BUDGET}",
                    ),
                    budget_remaining=budget,
                    research_allowance_requested=max(
                        0, int(proposal.budget_requests)
                    ),
                    research_allowance_remaining=allowance,
                )
            )
            continue
        if max(0, int(proposal.budget_requests)) > allowance:
            outcomes.append(
                RevisionIngestOutcomeV1(
                    proposal_id=proposal.proposal_id,
                    revision_id=proposal.revision_id,
                    submission_digest=submission.content_digest,
                    parent_obligation_id=proposal.parent_obligation_id,
                    status="rejected",
                    verdict="rejected",
                    failures=(
                        "revision_research_allowance_exhausted:"
                        f"{int(proposal.budget_requests)}/{allowance}",
                    ),
                    budget_remaining=budget,
                    research_allowance_requested=max(
                        0, int(proposal.budget_requests)
                    ),
                    research_allowance_remaining=allowance,
                )
            )
            continue
        observed_refs = authenticated_observed_ref_ids(
            _tool_context(runtime),
            (proposal.parent_obligation_id,),
            failures=ledger_failures,
        )
        cited = tuple(
            dict.fromkeys(
                str(value)
                for value in (*proposal.observation_refs, *proposal.relation_refs)
                if str(value).strip()
            )
        )
        unobserved = sorted(
            value for value in cited if value not in set(observed_refs)
        )
        if unobserved:
            # The ledger is the authority for what this run actually saw.
            # ``assess_revision_proposal`` skips this check when it is called
            # without an observation set; ingestion always has one, so the
            # stricter form applies here and a fabricated citation is refused
            # before the proposal reaches the graph.
            failures = tuple(
                f"revision_ref_unobserved:{value}" for value in unobserved[:5]
            )
            outcomes.append(
                RevisionIngestOutcomeV1(
                    proposal_id=proposal.proposal_id,
                    revision_id=proposal.revision_id,
                    submission_digest=submission.content_digest,
                    parent_obligation_id=proposal.parent_obligation_id,
                    status="rejected",
                    verdict="rejected",
                    failures=failures,
                    budget_remaining=budget,
                )
            )
            continue
        fact_set, claim_set = _compiled_sets(
            compiled_by_obligation, proposal.parent_obligation_id
        )
        predicate_support = cited_predicate_support(
            _tool_context(runtime),
            (*proposal.observation_refs, *proposal.relation_refs),
            behavior_graph=behavior_graph,
            symbol_index=symbol_index,
        )
        application: RevisionApplicationV1 = revise_research_targets(
            runtime=runtime,
            proposal=proposal,
            observed_ref_ids=observed_refs,
            remaining_budget=allowance,
            semantic_verifier=semantic_verifier,
            previous_journal=journal,
            fact_set=fact_set,
            claim_set=claim_set,
            observed_ref_predicates=predicate_support,
            object_digests=(
                (object_digests_by_obligation or {}).get(
                    proposal.parent_obligation_id
                )
            ),
        )
        verdict = str(application.assessment.verdict)
        requested = max(0, int(proposal.budget_requests))
        if verdict == "accepted" and not application.failures:
            journal = application.journal
            entry = journal.entries[-1]
            # One application costs one harness charge, regardless of what the
            # proposal asked for; the research allowance is charged separately.
            spent = 1
            budget = max(0, budget - spent)
            allowance = max(0, allowance - requested)
            rebind_failures = _rebind_runtime(runtime, application)
            if rebind_failures:
                # The journal now holds a revision the live run does not use.
                # That is an integrity failure, not a rejected proposal.
                ledger_failures.extend(rebind_failures)
                outcomes.append(
                    RevisionIngestOutcomeV1(
                        proposal_id=proposal.proposal_id,
                        revision_id=proposal.revision_id,
                        submission_digest=submission.content_digest,
                        parent_obligation_id=proposal.parent_obligation_id,
                        status="invalid",
                        verdict=verdict,
                        failures=rebind_failures,
                        assessment_id=application.assessment.assessment_id,
                        budget_spent=spent,
                        budget_remaining=budget,
                        application_charge=spent,
                        research_allowance_requested=requested,
                        research_allowance_remaining=allowance,
                        applied_target_ids=entry.applied_target_ids,
                        removed_target_ids=entry.removed_target_ids,
                        revalidation_rows=application.revalidation_rows,
                    )
                )
                continue
            applied_count += 1
            outcomes.append(
                RevisionIngestOutcomeV1(
                    proposal_id=proposal.proposal_id,
                    revision_id=proposal.revision_id,
                    submission_digest=submission.content_digest,
                    parent_obligation_id=proposal.parent_obligation_id,
                    status="applied",
                    verdict=verdict,
                    assessment_id=application.assessment.assessment_id,
                    budget_spent=spent,
                    budget_remaining=budget,
                    application_charge=spent,
                    research_allowance_requested=requested,
                    research_allowance_remaining=allowance,
                    applied_target_ids=entry.applied_target_ids,
                    removed_target_ids=entry.removed_target_ids,
                    revalidation_rows=application.revalidation_rows,
                )
            )
            continue
        status: RevisionIngestStatus = (
            "pending_review" if verdict == "pending_review" else "rejected"
        )
        outcomes.append(
            RevisionIngestOutcomeV1(
                proposal_id=proposal.proposal_id,
                revision_id=proposal.revision_id,
                submission_digest=submission.content_digest,
                parent_obligation_id=proposal.parent_obligation_id,
                status=status,
                verdict=verdict,
                failures=tuple(
                    dict.fromkeys((*application.failures, *application.assessment.failures))
                ),
                assessment_id=application.assessment.assessment_id,
                budget_remaining=budget,
                research_allowance_requested=requested,
                research_allowance_remaining=allowance,
            )
        )

    return RevisionIngestResultV1(
        run_id=str(getattr(runtime, "run_id", "") or ""),
        outcomes=tuple(outcomes),
        journal=journal,
        applied_count=applied_count,
        budget_remaining=budget,
        research_allowance_remaining=allowance,
        ledger_failures=tuple(dict.fromkeys(ledger_failures)),
        current_revision_id=journal.current_revision_id(),
    )


def _tool_context(runtime: Any) -> Any:
    """Return a tool context for ledger access without a live behavior graph."""

    builder = getattr(runtime, "tool_context", None)
    if callable(builder):
        try:
            return builder()
        except TypeError:  # pragma: no cover - defensive signature drift
            return builder(behavior_graph=None)
    return runtime


def _rebind_runtime(runtime: Any, application: RevisionApplicationV1) -> tuple[str, ...]:
    """Write the revised graph/agenda back onto the live runtime objects.

    ``ResearchGraphRuntime`` is frozen, so the revision is bound by updating
    the objects every holder already references.  Copying the digest fields of
    the revised objects keeps the agenda -> graph link truthful, and the
    journal entry already covers both digests.
    """

    from code2paper.agentic.research_revision_contract import (
        rebind_revision_in_place,
    )

    return rebind_revision_in_place(
        runtime_intent_graph=getattr(runtime, "intent_graph", None),
        runtime_agenda=getattr(runtime, "agenda", None),
        revised_graph=getattr(application, "graph", None),
        revised_agenda=getattr(application, "agenda", None),
    )


def write_revision_ingest_result(
    artifact_root: Any,
    result: RevisionIngestResultV1,
    *,
    ingestion_index: int = 0,
) -> Path | None:
    """Persist one ingestion pass under the run's artifact root."""

    directory = (
        None
        if artifact_root is None
        else Path(artifact_root)
        / "research_tool_artifacts"
        / REVISION_INGEST_ARTIFACT_KIND
    )
    if directory is None:
        return None
    path = directory / f"{int(ingestion_index):04d}-{result.content_digest[:16]}.json"
    payload = result.model_dump(mode="json")
    from code2paper.agentic.tool_runtime import atomic_write_json

    atomic_write_json(path, payload)
    return path


__all__ = [
    "DEFAULT_REVISION_PROPOSAL_BUDGET",
    "REVISION_INGEST_ARTIFACT_KIND",
    "REVISION_PROPOSAL_ARTIFACT_KIND",
    "REVISION_PROPOSAL_TOOL_NAME",
    "RevisionIngestOutcomeV1",
    "RevisionIngestResultV1",
    "RevisionIngestStatus",
    "RevisionProposalSubmissionV1",
    "authenticated_observed_ref_ids",
    "ingest_revision_submissions",
    "iter_revision_submissions",
    "persist_revision_proposal",
    "proposal_directory",
    "proposal_path",
    "write_revision_ingest_result",
]
