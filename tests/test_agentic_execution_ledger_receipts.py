"""R9: negative evidence requires a receipt the execution layer produced.

The pre-R9 path built a ``SearchReceiptV1`` out of ``record_explicit_code_gap``
arguments, so a caller could claim a search that never ran and receive
``negative_evidence_authorized=true``.  These tests drive the real dispatcher
(``execute_research_tool``) and prove that:

* caller-authored receipt content is rejected outright;
* an unknown/forged receipt id cannot authorize a negative conclusion;
* a receipt is only minted from executions that really happened, and it stays
  unclosed while any discovered candidate is unread;
* a stale receipt (minted before later executions) is refused;
* terminal consumers reuse the execution-layer authentication verdict instead
  of repeating a boolean list check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_execution_ledger import (
    authenticate_search_receipt,
    derive_frontier_receipt,
    iter_execution_records,
    mint_frontier_receipt,
    record_ledger_write_failure,
    verify_receipt_authentication,
)
from code2paper.agentic.research_models import ResearchToolCallV1
from code2paper.agentic.research_terminal import evaluate_obligation_terminal_proof
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_KINDS,
    ResearchToolContext,
    execute_research_tool,
)


_MAIN_PY = """\
def main() -> int:
    trainer = Trainer()
    trainer.train_loop()
    return 0
"""

_TRAIN_PY = """\
from lib.model import Model


class Trainer:
    def train_loop(self) -> None:
        for batch in range(10):
            self.model.forward(batch)
"""

_LIB_MODEL_PY = """\
class Model:
    def forward(self, batch: int) -> int:
        return batch + 1
"""


@pytest.fixture()
def tool_ctx(tmp_path: Path) -> ResearchToolContext:
    root = tmp_path / "repo"
    (root / "lib").mkdir(parents=True)
    (root / "main.py").write_text(_MAIN_PY, encoding="utf-8")
    (root / "train.py").write_text(_TRAIN_PY, encoding="utf-8")
    (root / "lib" / "model.py").write_text(_LIB_MODEL_PY, encoding="utf-8")
    snapshot = build_repo_snapshot(root)
    return ResearchToolContext(
        repo_snapshot=snapshot,
        artifact_root=tmp_path / "artifacts",
    )


def _call(
    ctx: ResearchToolContext,
    *,
    tool_name: str,
    arguments: dict,
    tool_call_id: str,
    obligation_id: str = "obl-1",
    path_scope: tuple[str, ...] = (),
    top_k: int = 10,
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=RESEARCH_TOOL_KINDS.get(tool_name, "other"),
        obligation_id=obligation_id,
        goal="prove the obligation",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        path_scope=path_scope,
        top_k=top_k,
        arguments=arguments,
    )


def _gap_arguments(**overrides) -> dict:
    payload = {
        "obligation_id_ref": "obl-1",
        "termination_reason": "bounded search found no implementation",
        "search_scope": ("train.py",),
        "attempted_tools": ("search_code", "read_code_span"),
        "search_complete": True,
        "scope_exhausted": True,
    }
    payload.update(overrides)
    return payload


def _terminal_gap(tmp_path: Path, obligation_id: str = "obl-1") -> dict | None:
    import hashlib

    root = tmp_path / "artifacts" / "research_tool_artifacts" / "terminal_gaps"
    if not root.is_dir():
        return None
    name = hashlib.sha256(obligation_id.encode("utf-8")).hexdigest() + ".json"
    path = root / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


# ---------------------------------------------------------------------------
# P1-A: caller-authored receipts are not evidence
# ---------------------------------------------------------------------------


def test_fabricated_receipt_content_in_arguments_is_rejected(
    tool_ctx: ResearchToolContext,
) -> None:
    observation = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="record_explicit_code_gap",
            tool_call_id="tc-forged-content",
            arguments=_gap_arguments(
                search_receipt={
                    "receipt_id": "receipt:invented",
                    "queries": ("never executed",),
                    "filter_scope": ("README.md",),
                    "result_ids": ("code:train.py:1",),
                    "read_candidate_ids": ("code:train.py:1",),
                    "unread_candidate_ids": (),
                    "truncated": False,
                    "tool_failures": (),
                },
            ),
        ),
    )
    assert observation.status == "invalid_request"
    assert "gap_search_receipt_content_not_evidence" in observation.error_message


def test_unexecuted_search_cannot_authorize_negative_evidence(
    tool_ctx: ResearchToolContext, tmp_path: Path
) -> None:
    """The pre-R9 repro: zero search/read calls plus invented receipt fields."""

    observation = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="record_explicit_code_gap",
            tool_call_id="tc-forged-id",
            arguments=_gap_arguments(search_receipt_id="receipt:never-minted"),
        ),
    )
    assert observation.status == "invalid_request"
    assert "search_receipt_unknown" in observation.error_message
    # Nothing was persisted, so no consumer can read this as a code gap.
    assert _terminal_gap(tmp_path) is None
    assert derive_frontier_receipt(tool_ctx, "obl-1")[0] is None


def test_unauthenticated_receipt_does_not_authorize_terminal_proof() -> None:
    forged = {
        "receipt_id": "receipt:forged",
        "obligation_id": "obl-1",
        "repo_snapshot_id": "repo:forged",
        "project_tree_hash": "sha256:forged",
        "queries": ("never executed",),
        "filter_scope": ("train.py",),
        "result_ids": ("code:train.py:1",),
        "read_candidate_ids": ("code:train.py:1",),
        "unread_candidate_ids": (),
        "truncated": False,
        "tool_failures": (),
        "stop_reason": "scope_exhausted",
    }
    ok, failures = verify_receipt_authentication(forged)
    assert ok is False
    assert "search_receipt_not_ledger_verified" in failures

    item = {
        "obligation_id": "obl-1",
        "status": "explicit_gap",
        "gap_requirements": ({
            "terminal": "explicit_gap",
            "terminal_outcome": "unsupported_with_scoped_evidence",
            "negative_evidence_authorized": True,
            "search_receipt": forged,
        },),
    }
    proof = evaluate_obligation_terminal_proof(item)
    assert proof.terminal is False
    assert proof.bounded_search_exhausted is False


# ---------------------------------------------------------------------------
# Receipts are derived from real executions
# ---------------------------------------------------------------------------


def _closed_frontier_observation(tool_ctx: ResearchToolContext):
    """Run one real search plus reads for every result, then close."""

    search = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-search-1",
            arguments={"query": "forward"},
            path_scope=("lib/model.py",),
            top_k=20,
        ),
    )
    assert search.status == "success"
    for index, ref in enumerate(search.result_refs):
        path, line = str(ref).removeprefix("code:").rsplit(":", 1)
        read = execute_research_tool(
            tool_ctx,
            _call(
                tool_ctx,
                tool_name="read_code_span",
                tool_call_id=f"tc-read-{index}",
                arguments={
                    "path": path,
                    "start_line": max(1, int(line) - 2),
                    "end_line": int(line) + 2,
                },
            ),
        )
        assert read.status == "success", read.error_message
    closure = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="close_search_frontier",
            tool_call_id="tc-close-1",
            arguments={},
            path_scope=("lib/model.py",),
        ),
    )
    return search, closure


def test_receipt_is_derived_from_executions_not_arguments(
    tool_ctx: ResearchToolContext, tmp_path: Path
) -> None:
    search, closure = _closed_frontier_observation(tool_ctx)
    assert closure.status == "success"
    assert closure.result_refs[0].startswith("search-receipt:")
    receipt_id = closure.result_refs[0].split(":", 1)[1]
    assert "search_frontier_closed=true" in closure.diagnostics.notes

    receipt, failures = authenticate_search_receipt(
        tool_ctx, receipt_id, obligation_id="obl-1"
    )
    assert failures == ()
    assert receipt is not None
    assert receipt.queries == ("search_code:forward",)
    assert set(receipt.result_ids) == set(search.result_refs)
    assert receipt.filter_scope == ("lib/model.py",)
    assert receipt.authentication == "ledger_verified"
    assert receipt.ledger_digest and receipt.execution_record_ids

    gap = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="record_explicit_code_gap",
            tool_call_id="tc-gap-1",
            arguments=_gap_arguments(
                search_scope=("lib/model.py",),
                search_receipt_id=receipt_id,
            ),
        ),
    )
    assert gap.status == "success", gap.error_message
    payload = _terminal_gap(tmp_path)
    assert payload is not None
    assert payload["terminal_outcome"] == "unsupported_with_scoped_evidence"
    assert payload["negative_evidence_authorized"] is True
    assert payload["receipt_authentication"] == "ledger_verified"
    assert payload["search_receipt"]["authentication"] == "ledger_verified"


def test_unread_candidate_keeps_the_frontier_open(
    tool_ctx: ResearchToolContext, tmp_path: Path
) -> None:
    search = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-search-unread",
            arguments={"query": "def"},
            path_scope=("lib/model.py",),
            top_k=20,
        ),
    )
    assert search.status == "success"
    assert len(search.result_refs) >= 1

    closure = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="close_search_frontier",
            tool_call_id="tc-close-unread",
            arguments={},
            path_scope=("lib/model.py",),
        ),
    )
    assert closure.status == "success"
    assert "search_frontier_closed=false" in closure.diagnostics.notes
    assert any("unread_candidates:" in note for note in closure.diagnostics.notes)

    receipt_id = closure.result_refs[0].split(":", 1)[1]
    gap = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="record_explicit_code_gap",
            tool_call_id="tc-gap-unread",
            arguments=_gap_arguments(
                search_scope=("lib/model.py",),
                search_receipt_id=receipt_id,
            ),
        ),
    )
    assert gap.status == "success", gap.error_message
    payload = _terminal_gap(tmp_path)
    assert payload is not None
    assert payload["terminal_outcome"] == "search_inconclusive"
    assert payload["negative_evidence_authorized"] is False


def test_truncated_search_forbids_closure(tool_ctx: ResearchToolContext) -> None:
    search = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-search-trunc",
            arguments={"query": "def"},
            path_scope=("lib/model.py",),
            top_k=1,
        ),
    )
    assert search.status == "truncated"
    closure = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="close_search_frontier",
            tool_call_id="tc-close-trunc",
            arguments={},
            path_scope=("lib/model.py",),
        ),
    )
    assert "search_frontier_closed=false" in closure.diagnostics.notes
    assert any("search_result_truncated" in note for note in closure.diagnostics.notes)


def test_stale_receipt_is_refused(tool_ctx: ResearchToolContext) -> None:
    _search, closure = _closed_frontier_observation(tool_ctx)
    stale_id = closure.result_refs[0].split(":", 1)[1]
    # A later discovery adds an unread candidate: the old closure no longer
    # describes the frontier the conclusion would cover.
    later = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-search-later",
            arguments={"query": "class"},
            path_scope=("lib/model.py",),
            top_k=20,
        ),
    )
    assert later.status == "success"
    receipt, failures = authenticate_search_receipt(
        tool_ctx, stale_id, obligation_id="obl-1"
    )
    assert receipt is None
    assert "search_receipt_stale" in failures


def test_ledger_write_failure_poisons_closure(
    tool_ctx: ResearchToolContext,
) -> None:
    _search, closure = _closed_frontier_observation(tool_ctx)
    assert "search_frontier_closed=true" in closure.diagnostics.notes
    record_ledger_write_failure(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-search-lost",
            arguments={"query": "lost"},
            path_scope=("lib/model.py",),
        ),
        RuntimeError("disk"),
    )
    receipt, failures = mint_frontier_receipt(tool_ctx, "obl-1")
    assert receipt is not None
    assert any("ledger_write_failed" in value for value in failures)
    assert receipt.frontier_closed() is False
    assert any(
        value.startswith("ledger_write_failed")
        for value in receipt.tool_failures
    )


def test_ledger_records_only_real_executions(tool_ctx: ResearchToolContext) -> None:
    execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-ledger-1",
            arguments={"query": "forward"},
            path_scope=("lib/model.py",),
        ),
    )
    # A policy-rejected call never executed and must not enter the ledger.
    rejected = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-ledger-2",
            arguments={"query": ""},
            path_scope=("lib/model.py",),
        ),
    )
    assert rejected.status == "invalid_request"
    records = iter_execution_records(tool_ctx, "obl-1")
    assert [record.tool_call_id for record in records] == ["tc-ledger-1"]
    assert records[0].query == "forward"
    assert records[0].filter_scope == ("lib/model.py",)
    assert records[0].result_ids


def test_complete_scope_metadata_license_flow(
    tool_ctx: ResearchToolContext, tmp_path: Path
) -> None:
    """A receipt-derived conclusion satisfies the terminal proof consumer."""

    _search, closure = _closed_frontier_observation(tool_ctx)
    receipt_id = closure.result_refs[0].split(":", 1)[1]
    execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="record_explicit_code_gap",
            tool_call_id="tc-gap-proof",
            arguments=_gap_arguments(
                search_scope=("lib/model.py",),
                search_receipt_id=receipt_id,
            ),
        ),
    )
    payload = _terminal_gap(tmp_path)
    assert payload is not None
    item = {
        "obligation_id": "obl-1",
        "status": "explicit_gap",
        "gap_requirements": ({
            "terminal": "explicit_gap",
            "terminal_outcome": payload["terminal_outcome"],
            "negative_evidence_authorized": payload[
                "negative_evidence_authorized"
            ],
            "search_receipt": payload["search_receipt"],
        },),
    }
    from code2paper.agentic.research_execution_ledger import (
        build_context_ledger_reader,
    )

    proof = evaluate_obligation_terminal_proof(
        item, receipt_verifier=build_context_ledger_reader(tool_ctx)
    )
    assert proof.explicit_gap_bound is True
    assert proof.terminal is True
    assert proof.reasons == ()

    # Without the current-revision re-authentication adapter the same stored
    # receipt is not negative evidence.
    assert evaluate_obligation_terminal_proof(item).explicit_gap_bound is False


# ---------------------------------------------------------------------------
# P1-A (third review): ledger integrity and replay identity
# ---------------------------------------------------------------------------


def _ledger_dir(tool_ctx: ResearchToolContext, obligation_id: str = "obl-1"):
    import hashlib

    digest = hashlib.sha256(obligation_id.encode("utf-8")).hexdigest()[:24]
    return (
        tool_ctx.artifact_root
        / "research_tool_artifacts"
        / "execution_ledger"
        / digest
    )


def test_corrupt_ledger_record_cannot_reauthorize_a_closed_receipt(
    tool_ctx: ResearchToolContext, tmp_path: Path
) -> None:
    """A damaged record must keep the frontier open, not shrink it."""

    from code2paper.agentic.research_execution_ledger import (
        ExecutionLedgerIntegrityError,
        derive_frontier_receipt,
        iter_execution_records,
    )

    _search, closure = _closed_frontier_observation(tool_ctx)
    receipt_id = closure.result_refs[0].split(":", 1)[1]
    directory = _ledger_dir(tool_ctx)
    record_files = sorted(
        path for path in directory.glob("*.json") if path.name != "_index.json"
    )
    assert record_files
    # Damage the newest record the way a truncated write would.
    record_files[-1].write_text("{not json", encoding="utf-8")

    with pytest.raises(ExecutionLedgerIntegrityError):
        iter_execution_records(tool_ctx, "obl-1")
    with pytest.raises(ExecutionLedgerIntegrityError):
        derive_frontier_receipt(tool_ctx, "obl-1")

    gap = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="record_explicit_code_gap",
            tool_call_id="tc-gap-corrupt",
            arguments=_gap_arguments(
                search_scope=("lib/model.py",),
                search_receipt_id=receipt_id,
            ),
        ),
    )
    assert gap.status == "invalid_request"
    assert "ledger_integrity" in gap.error_message
    assert _terminal_gap(tmp_path) is None


def test_tampered_record_digest_is_not_silently_redigested(
    tool_ctx: ResearchToolContext,
) -> None:
    """A rewritten payload must not be re-digested into an authentic record."""

    import json

    from code2paper.agentic.research_execution_ledger import (
        ExecutionLedgerIntegrityError,
        iter_execution_records,
    )

    execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-tamper",
            arguments={"query": "forward"},
            path_scope=("lib/model.py",),
        ),
    )
    directory = _ledger_dir(tool_ctx)
    record_path = next(
        path for path in directory.glob("*.json") if path.name != "_index.json"
    )
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    payload["result_ids"] = ["code:lib/model.py:1"]
    record_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ExecutionLedgerIntegrityError) as excinfo:
        iter_execution_records(tool_ctx, "obl-1")
    assert "digest_mismatch" in str(excinfo.value)


def test_deleted_record_is_detected_by_the_ledger_index(
    tool_ctx: ResearchToolContext,
) -> None:
    """The append-only manifest notices a record removed outside the process."""

    from code2paper.agentic.research_execution_ledger import (
        ExecutionLedgerIntegrityError,
        derive_frontier_receipt,
    )

    _search, _closure = _closed_frontier_observation(tool_ctx)
    directory = _ledger_dir(tool_ctx)
    record_files = sorted(
        path for path in directory.glob("*.json") if path.name != "_index.json"
    )
    record_files[-1].unlink()
    with pytest.raises(ExecutionLedgerIntegrityError) as excinfo:
        derive_frontier_receipt(tool_ctx, "obl-1")
    assert "record_missing" in str(excinfo.value)


def test_same_tool_call_id_replay_is_idempotent(tool_ctx: ResearchToolContext) -> None:
    """The same call replayed records once and keeps the same record."""

    from code2paper.agentic.research_execution_ledger import iter_execution_records

    for _attempt in range(2):
        observation = execute_research_tool(
            tool_ctx,
            _call(
                tool_ctx,
                tool_name="search_code",
                tool_call_id="tc-replay",
                arguments={"query": "forward"},
                path_scope=("lib/model.py",),
            ),
        )
        assert observation.status == "success"
    records = iter_execution_records(tool_ctx, "obl-1")
    assert [record.tool_call_id for record in records] == ["tc-replay"]


def test_same_tool_call_id_with_a_different_request_is_rejected(
    tool_ctx: ResearchToolContext, tmp_path: Path
) -> None:
    """A reused id must not hide the newer search from the frontier."""

    first = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-reused",
            arguments={"query": "forward"},
            path_scope=("lib/model.py",),
        ),
    )
    assert first.status == "success"
    second = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-reused",
            arguments={"query": "class"},
            path_scope=("lib/model.py",),
        ),
    )
    assert second.status == "invalid_request"
    assert "replay_mismatch" in second.error_message

    from code2paper.agentic.research_execution_ledger import iter_execution_records

    records = iter_execution_records(tool_ctx, "obl-1")
    assert [record.query for record in records] == ["forward"]

    # A receipt minted from this ledger stays open: the reused call never
    # entered it as a successful second search.
    closure = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="close_search_frontier",
            tool_call_id="tc-close-reused",
            arguments={},
            path_scope=("lib/model.py",),
        ),
    )
    assert "search_frontier_closed=false" in closure.diagnostics.notes


def test_post_execution_conflict_persists_a_blocking_state(
    tool_ctx: ResearchToolContext, tmp_path: Path
) -> None:
    """An execution that cannot be registered keeps the frontier open.

    The same request replayed with different results (a non-deterministic tool
    or a damaged store) must not leave the older, narrower frontier authorizing
    a negative conclusion.
    """

    from unittest.mock import patch

    from code2paper.agentic import research_tools
    from code2paper.agentic.research_execution_ledger import (
        derive_frontier_receipt,
    )

    search = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-nondet",
            arguments={"query": "forward"},
            path_scope=("lib/model.py",),
        ),
    )
    assert search.status == "success"
    original = research_tools.RESEARCH_TOOL_EXECUTORS["search_code"]

    def _different_results(context, tool_call):
        observation = original(context, tool_call)
        return observation.model_copy(update={
            "result_refs": (*observation.result_refs, "code:lib/model.py:99"),
        })

    with patch.dict(
        research_tools.RESEARCH_TOOL_EXECUTORS,
        {"search_code": _different_results},
    ):
        replay = execute_research_tool(
            tool_ctx,
            _call(
                tool_ctx,
                tool_name="search_code",
                tool_call_id="tc-nondet",
                arguments={"query": "forward"},
                path_scope=("lib/model.py",),
            ),
        )
    assert replay.status == "invalid_request"
    assert "replay_mismatch" in replay.error_message

    receipt, failures = derive_frontier_receipt(tool_ctx, "obl-1")
    assert receipt is not None
    assert receipt.frontier_closed() is False
    assert any("execution_ledger_conflict" in value for value in failures)


def test_pre_execution_conflict_never_runs_the_executor(
    tool_ctx: ResearchToolContext,
) -> None:
    """A reused id with a different request is rejected before execution."""

    from unittest.mock import patch

    from code2paper.agentic import research_tools

    execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="tc-precheck",
            arguments={"query": "forward"},
            path_scope=("lib/model.py",),
        ),
    )
    executions: list[str] = []
    original = research_tools.RESEARCH_TOOL_EXECUTORS["search_code"]

    def _observed(context, tool_call):
        executions.append(str(tool_call.arguments.get("query")))
        return original(context, tool_call)

    with patch.dict(
        research_tools.RESEARCH_TOOL_EXECUTORS, {"search_code": _observed}
    ):
        rejected = execute_research_tool(
            tool_ctx,
            _call(
                tool_ctx,
                tool_name="search_code",
                tool_call_id="tc-precheck",
                arguments={"query": "class"},
                path_scope=("lib/model.py",),
            ),
        )
    assert rejected.status == "invalid_request"
    assert "replay_mismatch_pre_execution" in rejected.error_message
    assert executions == [], "the rejected request must not reach the executor"
