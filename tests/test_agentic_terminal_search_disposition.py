"""R9: the three terminal search outcomes are typed and not interchangeable."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from code2paper.agentic.research_models import (
    SearchReceiptV1,
    TerminalSearchDispositionV1,
)
from code2paper.agentic.research_terminal import evaluate_obligation_terminal_proof


def _receipt(**overrides) -> SearchReceiptV1:
    payload = {
        "receipt_id": "receipt:one",
        "obligation_id": "ob:one",
        "repo_snapshot_id": "repo:tree",
        "project_tree_hash": "sha256:tree",
        "queries": ("normalize hidden state",),
        "filter_scope": ("model.py",),
        "top_k": 10,
        "result_ids": ("sym:normalize",),
        "read_candidate_ids": ("sym:normalize",),
        "stop_reason": "scope_exhausted",
        # R9: terminal consumers require the execution layer's authentication
        # verdict, not just receipt-shaped fields.
        "ledger_digest": "sha256:ledger",
        "execution_record_ids": ("exec:one",),
        "authentication": "ledger_verified",
    }
    payload.update(overrides)
    return SearchReceiptV1(**payload)


def test_receipt_requires_identity_and_proves_closure_only_when_read() -> None:
    receipt = _receipt()
    assert receipt.frontier_closed() is True
    # An unread candidate means the frontier is not closed.
    assert _receipt(unread_candidate_ids=("sym:other",)).frontier_closed() is False
    # A truncated query means the top-k was not exhausted.
    assert _receipt(truncated=True).frontier_closed() is False
    # A failed tool means coverage is unknown.
    assert _receipt(tool_failures=("read_symbol:timeout",)).frontier_closed() is False
    # A search with no read evidence proves nothing.
    assert _receipt(read_candidate_ids=()).frontier_closed() is False
    with pytest.raises(ValidationError):
        SearchReceiptV1(
            receipt_id="",
            obligation_id="ob:one",
            repo_snapshot_id="repo:tree",
            project_tree_hash="sha256:tree",
        )


def test_scoped_negative_evidence_requires_a_closed_receipt() -> None:
    with pytest.raises(ValidationError):
        TerminalSearchDispositionV1(
            disposition_id="d1",
            obligation_id="ob:one",
            outcome="unsupported_with_scoped_evidence",
            frozen_scope=("model.py",),
            scope_basis="gap_search_scope",
        )
    with pytest.raises(ValidationError):
        TerminalSearchDispositionV1(
            disposition_id="d1",
            obligation_id="ob:one",
            outcome="unsupported_with_scoped_evidence",
            frozen_scope=("model.py",),
            scope_basis="gap_search_scope",
            receipts=(_receipt(unread_candidate_ids=("sym:other",)),),
        )
    ok = TerminalSearchDispositionV1(
        disposition_id="d1",
        obligation_id="ob:one",
        outcome="unsupported_with_scoped_evidence",
        frozen_scope=("model.py",),
        scope_basis="gap_search_scope",
        receipts=(_receipt(),),
    )
    assert ok.content_digest.startswith("sha256:")


def test_inconclusive_and_budget_states_require_their_own_proof() -> None:
    with pytest.raises(ValidationError):
        TerminalSearchDispositionV1(
            disposition_id="d2",
            obligation_id="ob:one",
            outcome="search_inconclusive",
        )
    inconclusive = TerminalSearchDispositionV1(
        disposition_id="d2",
        obligation_id="ob:one",
        outcome="search_inconclusive",
        stop_reason="no_information_gain",
        queries=("normalize hidden state",),
        observations=("search_code",),
        open_questions=("typed_predicate:normalize",),
    )
    assert inconclusive.outcome == "search_inconclusive"

    with pytest.raises(ValidationError):
        TerminalSearchDispositionV1(
            disposition_id="d3",
            obligation_id="ob:one",
            outcome="budget_exhausted",
            stop_reason="max_turns_reached",
        )
    budget = TerminalSearchDispositionV1(
        disposition_id="d3",
        obligation_id="ob:one",
        outcome="budget_exhausted",
        stop_reason="max_turns_reached",
        budget_used=12,
        budget_limit=12,
        remaining_frontier_ids=("sym:other",),
    )
    assert budget.outcome == "budget_exhausted"


def test_terminal_proof_reads_typed_outcomes_not_notes() -> None:
    """A note claiming a closed frontier is not negative evidence."""

    legacy_item = {
        "obligation_id": "ob:legacy",
        "status": "explicit_gap",
        "gap_requirements": ({"terminal": "explicit_gap"},),
        "missing_information": ("bounded_search_exhausted",),
    }
    proof = evaluate_obligation_terminal_proof(legacy_item)
    # A legacy requirement that claims a gap without a typed, receipt-backed
    # disposition reads as unresolved and keeps its raw data.
    assert proof.terminal is False
    assert proof.bounded_search_exhausted is False
    assert "explicit_gap_requirements_not_terminal" in proof.reasons

    typed_item = {
        "obligation_id": "ob:typed",
        "status": "partial",
        "gap_requirements": ({
            "terminal": "explicit_gap",
            "terminal_outcome": "unsupported_with_scoped_evidence",
            "negative_evidence_authorized": True,
            "search_receipt": _receipt(obligation_id="ob:typed").model_dump(
                mode="json"
            ),
        },),
        "required_qualifiers": ("only on the frozen scope",),
    }
    # R9 correction: a stored receipt is not enough by itself.  The consumer
    # must supply the current-revision re-authentication adapter.
    def _verifier(receipt_id: str) -> SearchReceiptV1:
        return _receipt(
            receipt_id=receipt_id,
            obligation_id="ob:typed",
            repo_snapshot_id="repo:tree",
            project_tree_hash="sha256:tree",
        )

    typed_proof = evaluate_obligation_terminal_proof(
        typed_item,
        promoted_claim_ids=("claim:one",),
        receipt_verifier=_verifier,
    )
    assert typed_proof.bounded_search_exhausted is True
    assert typed_proof.terminal is True
    # Without the adapter the same requirement reads as unproven.
    assert evaluate_obligation_terminal_proof(
        typed_item, promoted_claim_ids=("claim:one",)
    ).terminal is False

    inconclusive_item = {
        "obligation_id": "ob:stop",
        "status": "partial",
        "gap_requirements": ({
            "terminal": "explicit_gap",
            "terminal_outcome": "search_inconclusive",
            "terminal_record_only": True,
            "negative_evidence_authorized": False,
        },),
        "required_qualifiers": ("only on the frozen scope",),
    }
    stop_proof = evaluate_obligation_terminal_proof(
        inconclusive_item,
        promoted_claim_ids=("claim:one",),
    )
    assert stop_proof.bounded_search_exhausted is False
    assert stop_proof.terminal is False
