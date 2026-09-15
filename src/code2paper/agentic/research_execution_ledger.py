"""R9 execution-layer evidence ledger and authenticated search receipts.

The R9 contract separates two things that used to be conflated:

* **What the tool arguments claim.**  A caller may describe any search it
  likes.  Arguments are model-authored text and therefore never evidence.
* **What the execution layer observed.**  Every real discovery/read/relation
  execution is appended to a run-scoped ledger by
  :func:`record_tool_execution`, which runs inside ``execute_research_tool``
  after the executor returned.  The ledger contains only tool outputs
  (status, queries, filter scope, result identity, read spans, failures).

A :class:`~code2paper.agentic.research_models.SearchReceiptV1` is *derived*
from that ledger.  ``record_explicit_code_gap`` receives a receipt id, reloads
the persisted receipt and re-derives it from the raw execution records before
it may authorize negative evidence.  A receipt that a caller invents in tool
arguments has no ledger derivation and is rejected, so an unexecuted search can
no longer produce ``negative_evidence_authorized=true``.

The same authentication verdict is reused by the terminal consumers: they call
:func:`verify_receipt_authentication` instead of repeating an ad-hoc boolean
list check on a receipt-shaped payload.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.research_models import (
    ResearchObservationV1,
    ResearchToolCallV1,
    SearchReceiptV1,
    _digest_payload,
)


EVIDENCE_KIND_DISCOVERY: Literal["discovery"] = "discovery"
EVIDENCE_KIND_READ: Literal["read"] = "read"
EVIDENCE_KIND_RELATION: Literal["relation"] = "relation"

EvidenceKind = Literal["discovery", "read", "relation"]

#: Tools that enumerate a candidate frontier.  Their result identity is what a
#: negative conclusion has to account for.
DISCOVERY_TOOLS: frozenset[str] = frozenset({
    "find_entrypoints",
    "search_symbols",
    "list_repository_tree",
    "search_code",
    "search_semantic_hints",
    "derive_code_queries_from_hint",
})

#: Tools that read or deterministically parse concrete source.
READ_TOOLS: frozenset[str] = frozenset({
    "read_symbol",
    "read_code_span",
    "build_behavior_subgraph",
    "query_behavior_graph",
    "inspect_configuration",
    "inspect_control_flow",
    "find_output_side_effects",
    "compare_implementation_branches",
    "compare_hint_to_code",
})

#: Tools that prove a relation check ran.
RELATION_TOOLS: frozenset[str] = frozenset({
    "find_references",
    "trace_call_path",
    "trace_data_flow",
})

EVIDENCE_TOOLS: frozenset[str] = DISCOVERY_TOOLS | READ_TOOLS | RELATION_TOOLS

#: Observation statuses that prove the tool actually executed.
EXECUTED_STATUSES: frozenset[str] = frozenset({
    "success",
    "success_empty",
    "scope_exhausted",
    "truncated",
})

#: The execution layer, not the caller, decides that the whole snapshot was in
#: scope.  An empty filter scope is canonicalised to this sentinel.
WHOLE_SNAPSHOT_SCOPE = "*"

EXECUTION_LEDGER_DIR = "research_tool_artifacts/execution_ledger"
SEARCH_RECEIPT_DIR = "research_tool_artifacts/search_receipts"
#: Append-only manifest of one obligation's execution records.  The ledger is
#: the authority for a negative conclusion, so a missing/corrupt record must be
#: detectable instead of silently shrinking the frontier.
EXECUTION_LEDGER_INDEX_NAME = "_index.json"


class ExecutionLedgerError(RuntimeError):
    """Base class for an unusable execution ledger."""


class ExecutionLedgerIntegrityError(ExecutionLedgerError):
    """A record, index entry or digest does not match the persisted ledger."""


class ExecutionLedgerReplayMismatch(ExecutionLedgerError):
    """One tool_call_id was reused for a different execution."""

AUTHENTICATION_LEDGER_VERIFIED = "ledger_verified"


class ReadSpanV1(BaseModel):
    """One source span a read execution actually consumed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    start_line: int
    end_line: int

    def covers(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line


class ResearchExecutionRecordV1(BaseModel):
    """One real tool execution as observed by the execution layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str
    recorded_index: int
    evidence_kind: EvidenceKind
    tool_name: str
    tool_call_id: str
    obligation_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    status: str
    query: str = ""
    filter_scope: tuple[str, ...] = Field(default_factory=tuple)
    top_k: int = 0
    truncated: bool = False
    result_ids: tuple[str, ...] = Field(default_factory=tuple)
    read_ids: tuple[str, ...] = Field(default_factory=tuple)
    read_paths: tuple[str, ...] = Field(default_factory=tuple)
    read_spans: tuple[ReadSpanV1, ...] = Field(default_factory=tuple)
    relation_checks: tuple[str, ...] = Field(default_factory=tuple)
    tool_failure: str = ""
    budget_limit: int = 0
    content_digest: str = ""

    def model_post_init(self, __context: Any) -> None:  # pragma: no cover - pydantic hook
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest_payload(payload))


class SearchReceiptAuthenticationV1(BaseModel):
    """The execution layer's authentication verdict for one receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str
    obligation_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    authentication: str = AUTHENTICATION_LEDGER_VERIFIED
    ledger_digest: str = ""
    execution_record_ids: tuple[str, ...] = Field(default_factory=tuple)
    derived_receipt_digest: str = ""
    failures: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    def model_post_init(self, __context: Any) -> None:  # pragma: no cover - pydantic hook
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest_payload(payload))


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _ledger_dir(ctx: Any, obligation_id: str) -> Path | None:
    root = getattr(ctx, "artifact_root", None)
    if root is None:
        return None
    digest = hashlib.sha256(obligation_id.encode("utf-8")).hexdigest()[:24]
    return Path(root) / EXECUTION_LEDGER_DIR / digest


def _receipt_path(ctx: Any, receipt_id: str) -> Path | None:
    root = getattr(ctx, "artifact_root", None)
    if root is None:
        return None
    digest = hashlib.sha256(receipt_id.encode("utf-8")).hexdigest()
    return Path(root) / SEARCH_RECEIPT_DIR / f"{digest}.json"


def _write_json(path: Path, payload: Any) -> None:
    from code2paper.agentic.tool_runtime import atomic_write_json

    atomic_write_json(path, payload)


def _normalized_scope(ctx: Any, scope: Iterable[str]) -> tuple[str, ...]:
    values = tuple(
        str(value).strip() for value in (scope or ()) if str(value).strip()
    )
    if not values:
        return (WHOLE_SNAPSHOT_SCOPE,)
    return tuple(dict.fromkeys(values))


def _record_identity_payload(record: Any) -> dict[str, Any]:
    """Return the execution identity of a record (everything but bookkeeping).

    ``recorded_index`` is a ledger position and ``content_digest`` is derived,
    so neither takes part in the replay comparison; every field that describes
    what actually ran does.
    """

    payload = (
        record.model_dump(mode="json")
        if hasattr(record, "model_dump")
        else dict(record)
    )
    return {
        key: value
        for key, value in payload.items()
        if key not in {"recorded_index", "content_digest"}
    }


def _payload_digest(payload: Mapping[str, Any]) -> str:
    return _digest_payload({
        key: value for key, value in payload.items() if key != "content_digest"
    })


def _load_record_file(path: Path) -> ResearchExecutionRecordV1:
    """Load one record, refusing a corrupted or self-inconsistent file."""

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_record_unreadable:{path.name}:{type(exc).__name__}"
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_record_unparsable:{path.name}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_record_not_a_mapping:{path.name}"
        )
    stored_digest = str(payload.get("content_digest") or "")
    expected_digest = _payload_digest(payload)
    if not stored_digest or stored_digest != expected_digest:
        # Never re-digest a mismatching record: a rewritten payload would look
        # authentic to every later derivation.
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_record_digest_mismatch:{path.name}"
        )
    try:
        record = ResearchExecutionRecordV1.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_record_invalid:{path.name}:{type(exc).__name__}"
        ) from exc
    if record.content_digest != stored_digest:
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_record_digest_rewritten:{path.name}"
        )
    return record


def _read_index(directory: Path) -> dict[str, str]:
    """Return ``{record_id: content_digest}`` for one obligation directory."""

    path = directory / EXECUTION_LEDGER_INDEX_NAME
    if not path.is_file():
        if any(
            item.name != EXECUTION_LEDGER_INDEX_NAME
            for item in directory.glob("*.json")
        ):
            # Records without their manifest cannot prove completeness.
            raise ExecutionLedgerIntegrityError(
                f"execution_ledger_index_missing:{directory.name}"
            )
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_index_unreadable:{directory.name}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_index_not_a_mapping:{directory.name}"
        )
    entries = payload.get("records")
    if not isinstance(entries, Mapping):
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_index_records_missing:{directory.name}"
        )
    index: dict[str, str] = {}
    for record_id, digest in entries.items():
        key = str(record_id)
        value = str(digest or "")
        if not key or not value:
            raise ExecutionLedgerIntegrityError(
                f"execution_ledger_index_entry_invalid:{directory.name}"
            )
        index[key] = value
    return index


def _write_index(directory: Path, index: Mapping[str, str]) -> None:
    _write_json(
        directory / EXECUTION_LEDGER_INDEX_NAME,
        {
            "schema_version": "execution_ledger_index_v1",
            "records": {key: index[key] for key in sorted(index)},
        },
    )


def _record_file_name(tool_call_id: str) -> str:
    return hashlib.sha256(tool_call_id.encode("utf-8")).hexdigest() + ".json"


def _call_request_projection(
    *, ctx: Any, tool_call: ResearchToolCallV1
) -> dict[str, Any]:
    """The part of a call's identity that is knowable before execution."""

    return {
        "tool_name": tool_call.tool_name,
        "obligation_id": tool_call.obligation_id,
        "repo_snapshot_id": str(ctx.repo_snapshot.snapshot_id),
        "project_tree_hash": str(ctx.repo_snapshot.project_tree_hash),
        "query": _call_query(tool_call),
        "filter_scope": list(_normalized_scope(ctx, tool_call.path_scope)),
        "top_k": int(tool_call.top_k or 0),
    }


def _call_query(tool_call: ResearchToolCallV1) -> str:
    return str(
        tool_call.arguments.get("query")
        or tool_call.arguments.get("symbol")
        or tool_call.arguments.get("path")
        or tool_call.arguments.get("term")
        or ""
    ).strip()


def _record_request_projection(record: ResearchExecutionRecordV1) -> dict[str, Any]:
    return {
        "tool_name": record.tool_name,
        "obligation_id": record.obligation_id,
        "repo_snapshot_id": record.repo_snapshot_id,
        "project_tree_hash": record.project_tree_hash,
        "query": record.query,
        "filter_scope": list(record.filter_scope),
        "top_k": int(record.top_k),
    }


def check_execution_call_identity(
    ctx: Any, tool_call: ResearchToolCallV1
) -> str:
    """Return a conflict reason when this call id already ran something else.

    The check runs *before* the executor: a rejected call must not touch the
    repository, because its observations would then be missing from the ledger
    while the older (narrower) frontier still authorized a negative conclusion.
    """

    if _classify_tool(tool_call.tool_name) is None:
        return ""
    directory = _ledger_dir(ctx, tool_call.obligation_id)
    if directory is None:
        return ""
    record_path = directory / _record_file_name(tool_call.tool_call_id)
    conflict_path = directory / _conflict_file_name(tool_call.tool_call_id)
    if conflict_path.is_file():
        return (
            "execution_ledger_call_id_conflicted:"
            f"{tool_call.tool_call_id}"
        )
    if not record_path.is_file():
        return ""
    existing = _load_record_file(record_path)
    if _record_request_projection(existing) != _call_request_projection(
        ctx=ctx, tool_call=tool_call
    ):
        return (
            "execution_ledger_replay_mismatch_pre_execution:"
            f"{tool_call.tool_call_id}:{existing.record_id}"
        )
    return ""


def record_ledger_conflict(
    ctx: Any,
    tool_call: ResearchToolCallV1,
    reason: str,
) -> ResearchExecutionRecordV1 | None:
    """Persist a blocking conflict record for an execution that cannot commit.

    The observation already happened but cannot be registered under this call
    id, so the ledger must stop proving a closed frontier until the search is
    repeated under a fresh id.
    """

    directory = _ledger_dir(ctx, tool_call.obligation_id)
    if directory is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    index = _read_index(directory)
    record = ResearchExecutionRecordV1(
        record_id=(
            "exec-conflict:" + hashlib.sha256(
                f"{tool_call.obligation_id}|{tool_call.tool_call_id}".encode("utf-8")
            ).hexdigest()[:16]
        ),
        recorded_index=(
            len([
                item for item in directory.glob("*.json")
                if item.name != EXECUTION_LEDGER_INDEX_NAME
            ])
            if directory.is_dir() else 0
        ),
        evidence_kind=_classify_tool(tool_call.tool_name) or EVIDENCE_KIND_DISCOVERY,
        tool_name=tool_call.tool_name,
        tool_call_id=tool_call.tool_call_id,
        obligation_id=tool_call.obligation_id,
        repo_snapshot_id=str(ctx.repo_snapshot.snapshot_id),
        project_tree_hash=str(ctx.repo_snapshot.project_tree_hash),
        status="ledger_conflict",
        query=_call_query(tool_call),
        filter_scope=_normalized_scope(ctx, tool_call.path_scope),
        top_k=int(tool_call.top_k or 0),
        truncated=True,
        tool_failure=f"execution_ledger_conflict:{reason}",
    )
    _write_json(
        directory / _conflict_file_name(tool_call.tool_call_id),
        record.model_dump(mode="json"),
    )
    _write_index(directory, {**index, record.record_id: record.content_digest})
    return record


def _conflict_file_name(tool_call_id: str) -> str:
    return (
        hashlib.sha256(tool_call_id.encode("utf-8")).hexdigest() + ".conflict.json"
    )


def build_context_ledger_reader(
    ctx: Any,
) -> Any:
    """Return a verifier that re-derives a receipt from this run's ledger.

    The returned callable is the adapter the terminal/coverage consumers use:
    it re-authenticates the receipt against the *current* revision and returns
    the authenticated receipt (or ``None``); an integrity failure propagates so
    the consumer can treat the receipt as unproven.
    """

    def _reader(receipt_id: str) -> Any:
        receipt, _failures = authenticate_search_receipt(ctx, str(receipt_id))
        return receipt

    return _reader


def _classify_tool(tool_name: str) -> EvidenceKind | None:
    if tool_name in DISCOVERY_TOOLS:
        return EVIDENCE_KIND_DISCOVERY
    if tool_name in READ_TOOLS:
        return EVIDENCE_KIND_READ
    if tool_name in RELATION_TOOLS:
        return EVIDENCE_KIND_RELATION
    return None


# ---------------------------------------------------------------------------
# Ref parsing (candidate identity used for read coverage)
# ---------------------------------------------------------------------------


def _parse_span_ref(ref: str) -> ReadSpanV1 | None:
    if not ref.startswith("span:"):
        return None
    parts = ref.split(":")
    if len(parts) != 4:
        return None
    _, path, start, end = parts
    try:
        return ReadSpanV1(path=path, start_line=int(start), end_line=int(end))
    except ValueError:
        return None


def _candidate_path_and_line(ref: str) -> tuple[str, int | None] | None:
    """Return ``(path, line)`` for the candidate ref forms we can resolve."""

    if ref.startswith("code:"):
        parts = ref.split(":")
        if len(parts) < 3:
            return None
        path = ":".join(parts[1:-1])
        try:
            return path, int(parts[-1])
        except ValueError:
            return None
    if ref.startswith("symbol:"):
        parts = ref.split(":")
        if len(parts) < 4:
            return None
        path = ":".join(parts[1:-2])
        try:
            return path, int(parts[-1])
        except ValueError:
            return None
    if ref.startswith("entrypoint:"):
        return ref.split(":", 1)[1], None
    return None


def _record_read_ids(
    *,
    result_refs: Iterable[str],
    exact_span_ids: Iterable[str],
    tool_name: str,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[ReadSpanV1, ...]]:
    spans: list[ReadSpanV1] = []
    read_ids: list[str] = []
    read_paths: list[str] = []
    for ref in exact_span_ids:
        span = _parse_span_ref(str(ref))
        if span is not None:
            spans.append(span)
            if span.path not in read_paths:
                read_paths.append(span.path)
            continue
        text = str(ref)
        if text and text not in read_ids:
            read_ids.append(text)
        resolved = _candidate_path_and_line(text)
        if resolved is not None and resolved[0] not in read_paths:
            read_paths.append(resolved[0])
    for ref in result_refs:
        text = str(ref)
        if not text:
            continue
        if text not in read_ids:
            read_ids.append(text)
        resolved = _candidate_path_and_line(text)
        if resolved is not None and resolved[0] not in read_paths:
            read_paths.append(resolved[0])
    # ``read_symbol`` / ``read_code_span`` prove path-level reading even when
    # the observation only carried the enclosing symbol ref.
    if tool_name in {"read_symbol", "read_code_span"}:
        for ref in result_refs:
            resolved = _candidate_path_and_line(str(ref))
            if resolved is not None and resolved[0] not in read_paths:
                read_paths.append(resolved[0])
    return tuple(read_ids), tuple(read_paths), tuple(spans)


def _candidate_is_read(
    candidate_id: str,
    *,
    record: ResearchExecutionRecordV1,
) -> bool:
    if candidate_id in record.read_ids:
        return True
    resolved = _candidate_path_and_line(candidate_id)
    if resolved is None:
        return False
    path, line = resolved
    if path not in record.read_paths:
        return False
    if line is None:
        return True
    covering = [span for span in record.read_spans if span.path == path]
    if not covering:
        # A path-level read with no recorded span still proves the file was
        # inspected, not that every line was.  Only exact refs count then.
        return f"code:{path}:{line}" in record.read_ids
    return any(span.covers(line) for span in covering)


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


def record_tool_execution(
    ctx: Any,
    tool_call: ResearchToolCallV1,
    observation: ResearchObservationV1,
) -> ResearchExecutionRecordV1 | None:
    """Append one real execution to the run-scoped ledger.

    Returns the persisted record, or ``None`` for tools that are not evidence
    producers or when the observation proves the tool never executed
    (``invalid_request`` is a policy rejection before execution).
    """

    evidence_kind = _classify_tool(tool_call.tool_name)
    if evidence_kind is None:
        return None
    status = str(observation.status)
    if status == "invalid_request":
        return None
    directory = _ledger_dir(ctx, tool_call.obligation_id)
    if directory is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    record_path = directory / _record_file_name(tool_call.tool_call_id)

    scope = _normalized_scope(ctx, tool_call.path_scope)
    query = str(
        tool_call.arguments.get("query")
        or tool_call.arguments.get("symbol")
        or tool_call.arguments.get("path")
        or tool_call.arguments.get("term")
        or ""
    ).strip()
    result_ids = tuple(
        dict.fromkeys(str(ref) for ref in observation.result_refs if str(ref))
    )
    read_ids: tuple[str, ...] = ()
    read_paths: tuple[str, ...] = ()
    read_spans: tuple[ReadSpanV1, ...] = ()
    if evidence_kind == EVIDENCE_KIND_READ:
        read_ids, read_paths, read_spans = _record_read_ids(
            result_refs=observation.result_refs,
            exact_span_ids=observation.exact_span_ids,
            tool_name=tool_call.tool_name,
        )
    relation_checks: tuple[str, ...] = ()
    if evidence_kind == EVIDENCE_KIND_RELATION:
        target = str(
            tool_call.arguments.get("symbol")
            or tool_call.arguments.get("from_symbol")
            or tool_call.arguments.get("source_symbol")
            or ""
        ).strip()
        relation_checks = (
            f"{tool_call.tool_name}:{target}" if target else tool_call.tool_name,
        )
    tool_failure = ""
    if status not in EXECUTED_STATUSES:
        tool_failure = (
            f"{tool_call.tool_name}:{observation.error_message or status}"
        )
    truncated = bool(observation.diagnostics.truncated) or status == "truncated"
    index = _read_index(directory)
    if record_path.is_file():
        # Idempotent replay is allowed only for the *same* execution.  A
        # reused tool_call_id with different arguments, results or read set is
        # rejected instead of silently returning the old record, which would
        # drop the newer candidates from the derived frontier.
        existing = _load_record_file(record_path)
        record_id = existing.record_id
        candidate = _record_payload(
            ctx=ctx,
            tool_call=tool_call,
            evidence_kind=evidence_kind,
            status=status,
            scope=scope,
            query=query,
            result_ids=result_ids,
            read_ids=read_ids,
            read_paths=read_paths,
            read_spans=read_spans,
            relation_checks=relation_checks,
            tool_failure=tool_failure,
            truncated=truncated,
            record_id=record_id,
            recorded_index=existing.recorded_index,
        )
        if _record_identity_payload(existing) != _record_identity_payload(
            candidate
        ):
            raise ExecutionLedgerReplayMismatch(
                "execution_ledger_replay_mismatch:"
                f"{tool_call.tool_call_id}:{existing.record_id}"
            )
        if index.get(record_id) not in {None, existing.content_digest}:
            raise ExecutionLedgerIntegrityError(
                f"execution_ledger_index_digest_mismatch:{record_id}"
            )
        if record_id not in index:
            _write_index(
                directory,
                {**index, record_id: existing.content_digest},
            )
        return existing

    record = ResearchExecutionRecordV1(
        record_id=(
            "exec:" + hashlib.sha256(
                f"{tool_call.obligation_id}|{tool_call.tool_call_id}".encode("utf-8")
            ).hexdigest()[:16]
        ),
        recorded_index=len([
            item for item in directory.glob("*.json")
            if item.name != EXECUTION_LEDGER_INDEX_NAME
        ]),
        evidence_kind=evidence_kind,
        tool_name=tool_call.tool_name,
        tool_call_id=tool_call.tool_call_id,
        obligation_id=tool_call.obligation_id,
        repo_snapshot_id=str(ctx.repo_snapshot.snapshot_id),
        project_tree_hash=str(ctx.repo_snapshot.project_tree_hash),
        status=status,
        query=query,
        filter_scope=scope,
        top_k=int(tool_call.top_k or 0),
        truncated=truncated,
        result_ids=result_ids,
        read_ids=read_ids,
        read_paths=read_paths,
        read_spans=read_spans,
        relation_checks=relation_checks,
        tool_failure=tool_failure,
        budget_limit=max(0, int(tool_call.node_budget or 0)),
    )
    _write_json(record_path, record.model_dump(mode="json"))
    _write_index(directory, {**index, record.record_id: record.content_digest})
    return record


def _record_payload(
    *,
    ctx: Any,
    tool_call: ResearchToolCallV1,
    evidence_kind: EvidenceKind,
    status: str,
    scope: tuple[str, ...],
    query: str,
    result_ids: tuple[str, ...],
    read_ids: tuple[str, ...],
    read_paths: tuple[str, ...],
    read_spans: tuple[ReadSpanV1, ...],
    relation_checks: tuple[str, ...],
    tool_failure: str,
    truncated: bool,
    record_id: str,
    recorded_index: int,
) -> ResearchExecutionRecordV1:
    """Rebuild the record one call/observation pair would persist."""

    return ResearchExecutionRecordV1(
        record_id=record_id,
        recorded_index=recorded_index,
        evidence_kind=evidence_kind,
        tool_name=tool_call.tool_name,
        tool_call_id=tool_call.tool_call_id,
        obligation_id=tool_call.obligation_id,
        repo_snapshot_id=str(ctx.repo_snapshot.snapshot_id),
        project_tree_hash=str(ctx.repo_snapshot.project_tree_hash),
        status=status,
        query=query,
        filter_scope=scope,
        top_k=int(tool_call.top_k or 0),
        truncated=bool(truncated),
        result_ids=result_ids,
        read_ids=read_ids,
        read_paths=read_paths,
        read_spans=read_spans,
        relation_checks=relation_checks,
        tool_failure=tool_failure,
        budget_limit=max(0, int(tool_call.node_budget or 0)),
    )


def record_ledger_write_failure(
    ctx: Any,
    tool_call: ResearchToolCallV1,
    error: BaseException,
) -> ResearchExecutionRecordV1 | None:
    """Persist a poison record when a real execution could not be recorded.

    A dropped discovery record would *shrink* the frontier a receipt sees, so
    an unrecordable execution must forbid closure rather than disappear.
    """

    directory = _ledger_dir(ctx, tool_call.obligation_id)
    if directory is None:
        return None
    evidence_kind = _classify_tool(tool_call.tool_name) or EVIDENCE_KIND_DISCOVERY
    record = ResearchExecutionRecordV1(
        record_id=(
            "exec-failed:" + hashlib.sha256(
                f"{tool_call.obligation_id}|{tool_call.tool_call_id}".encode("utf-8")
            ).hexdigest()[:16]
        ),
        recorded_index=(
            len([
                item for item in directory.glob("*.json")
                if item.name != EXECUTION_LEDGER_INDEX_NAME
            ])
            if directory.is_dir() else 0
        ),
        evidence_kind=evidence_kind,
        tool_name=tool_call.tool_name,
        tool_call_id=tool_call.tool_call_id,
        obligation_id=tool_call.obligation_id,
        repo_snapshot_id=str(ctx.repo_snapshot.snapshot_id),
        project_tree_hash=str(ctx.repo_snapshot.project_tree_hash),
        status="ledger_write_failed",
        tool_failure=f"ledger_write_failed:{type(error).__name__}",
    )
    directory.mkdir(parents=True, exist_ok=True)
    index = _read_index(directory)
    _write_json(
        directory / _record_file_name(tool_call.tool_call_id),
        record.model_dump(mode="json"),
    )
    _write_index(directory, {**index, record.record_id: record.content_digest})
    return record


def iter_execution_records(
    ctx: Any, obligation_id: str
) -> tuple[ResearchExecutionRecordV1, ...]:
    """Return the persisted records for one obligation in deterministic order.

    A record that cannot be read, parsed or digest-verified raises instead of
    being skipped: the frontier a receipt proves is only as complete as the
    ledger it was derived from, so a corrupt file must block the conclusion
    rather than disappear from it.  The append-only index is checked in both
    directions, so a deleted record is detected too.
    """

    directory = _ledger_dir(ctx, obligation_id)
    if directory is None or not directory.is_dir():
        return ()
    index = _read_index(directory)
    records: list[ResearchExecutionRecordV1] = []
    for path in sorted(directory.glob("*.json")):
        if path.name == EXECUTION_LEDGER_INDEX_NAME:
            continue
        record = _load_record_file(path)
        indexed_digest = index.get(record.record_id)
        if indexed_digest is None:
            raise ExecutionLedgerIntegrityError(
                f"execution_ledger_record_not_indexed:{record.record_id}"
            )
        if indexed_digest != record.content_digest:
            raise ExecutionLedgerIntegrityError(
                f"execution_ledger_index_digest_mismatch:{record.record_id}"
            )
        records.append(record)
    present = {record.record_id for record in records}
    missing = sorted(set(index) - present)
    if missing:
        # A record that the manifest knows about but the directory no longer
        # holds would silently shrink the frontier.
        raise ExecutionLedgerIntegrityError(
            f"execution_ledger_record_missing:{missing[0]}"
        )
    records.sort(key=lambda item: (item.recorded_index, item.record_id))
    return tuple(records)


# ---------------------------------------------------------------------------
# Derivation and authentication
# ---------------------------------------------------------------------------


def _current_snapshot_records(
    ctx: Any, obligation_id: str
) -> tuple[ResearchExecutionRecordV1, ...]:
    snapshot_id = str(ctx.repo_snapshot.snapshot_id)
    tree_hash = str(ctx.repo_snapshot.project_tree_hash)
    return tuple(
        record
        for record in iter_execution_records(ctx, obligation_id)
        if record.repo_snapshot_id == snapshot_id
        and record.project_tree_hash == tree_hash
    )


def ledger_digest(records: Iterable[ResearchExecutionRecordV1]) -> str:
    """Return the content digest of one ordered record prefix."""

    return _digest_payload(
        [
            {
                "record_id": record.record_id,
                "content_digest": record.content_digest,
            }
            for record in records
        ]
    )


def derive_frontier_receipt(
    ctx: Any, obligation_id: str
) -> tuple[SearchReceiptV1 | None, tuple[str, ...]]:
    """Derive the canonical receipt from the obligation's real executions.

    Returns ``(receipt, failures)``.  ``receipt`` is ``None`` when the ledger
    holds no executed discovery, and ``failures`` lists why no negative
    conclusion can be drawn.
    """

    records = _current_snapshot_records(ctx, obligation_id)
    executed = tuple(
        record for record in records if record.status in EXECUTED_STATUSES
    )
    discovery = tuple(
        record
        for record in executed
        if record.evidence_kind == EVIDENCE_KIND_DISCOVERY and record.query
    )
    reads = tuple(
        record for record in executed if record.evidence_kind == EVIDENCE_KIND_READ
    )
    relations = tuple(
        record for record in executed if record.evidence_kind == EVIDENCE_KIND_RELATION
    )
    if not discovery:
        return None, ("search_ledger_has_no_executed_discovery",)

    queries = tuple(
        dict.fromkeys(f"{record.tool_name}:{record.query}" for record in discovery)
    )
    scope: list[str] = []
    for record in discovery:
        for value in record.filter_scope:
            if value not in scope:
                scope.append(value)
    result_ids = tuple(
        dict.fromkeys(
            ref for record in discovery for ref in record.result_ids if ref
        )
    )
    read_candidate_ids: list[str] = []
    unread_candidate_ids: list[str] = []
    for candidate_id in result_ids:
        if any(_candidate_is_read(candidate_id, record=record) for record in reads):
            read_candidate_ids.append(candidate_id)
        else:
            unread_candidate_ids.append(candidate_id)
    truncated = any(record.truncated for record in discovery)
    tool_failures = tuple(
        dict.fromkeys(
            record.tool_failure for record in records if record.tool_failure
        )
    )
    relation_checks = tuple(
        dict.fromkeys(
            value for record in relations for value in record.relation_checks
        )
    )
    budget_limit = max((record.budget_limit for record in executed), default=0)
    receipt_id = "receipt:" + hashlib.sha256(
        "|".join((
            obligation_id,
            str(ctx.repo_snapshot.snapshot_id),
            str(ctx.repo_snapshot.project_tree_hash),
            ",".join(queries),
            ",".join(scope),
            ",".join(result_ids),
            ",".join(read_candidate_ids),
            ",".join(unread_candidate_ids),
            str(truncated),
            ",".join(tool_failures),
            ",".join(relation_checks),
        )).encode("utf-8")
    ).hexdigest()[:16]
    receipt = SearchReceiptV1(
        receipt_id=receipt_id,
        obligation_id=obligation_id,
        repo_snapshot_id=str(ctx.repo_snapshot.snapshot_id),
        project_tree_hash=str(ctx.repo_snapshot.project_tree_hash),
        queries=queries,
        filter_scope=tuple(scope) or (WHOLE_SNAPSHOT_SCOPE,),
        top_k=max((record.top_k for record in discovery), default=0),
        truncated=truncated,
        result_ids=result_ids,
        read_candidate_ids=tuple(read_candidate_ids),
        unread_candidate_ids=tuple(unread_candidate_ids),
        relation_checks=relation_checks,
        tool_failures=tool_failures,
        budget_used=len(executed),
        budget_limit=budget_limit,
        stop_reason="ledger_derived",
        ledger_digest=ledger_digest(records),
        execution_record_ids=tuple(record.record_id for record in records),
        authentication=AUTHENTICATION_LEDGER_VERIFIED,
    )
    failures = frontier_gap_reasons(receipt)
    return receipt, failures


def frontier_gap_reasons(receipt: SearchReceiptV1) -> tuple[str, ...]:
    """Return the reasons a derived receipt cannot prove a closed frontier."""

    reasons: list[str] = []
    if not receipt.queries:
        reasons.append("search_ledger_has_no_executed_query")
    if receipt.truncated:
        reasons.append("search_result_truncated")
    if receipt.tool_failures:
        reasons.extend(f"tool_failure:{value}" for value in receipt.tool_failures)
    if not receipt.result_ids:
        reasons.append("search_ledger_has_no_result_identity")
    if receipt.unread_candidate_ids:
        reasons.append(
            f"unread_candidates:{len(receipt.unread_candidate_ids)}"
        )
    if not receipt.read_candidate_ids:
        reasons.append("search_ledger_has_no_read_candidate")
    return tuple(reasons)


def mint_frontier_receipt(
    ctx: Any, obligation_id: str
) -> tuple[SearchReceiptV1 | None, tuple[str, ...]]:
    """Derive and persist the obligation's receipt from the ledger.

    Persisting is idempotent: the derivation is a pure function of the current
    ledger, so a replay writes the same bytes again.
    """

    receipt, failures = derive_frontier_receipt(ctx, obligation_id)
    if receipt is None:
        return None, failures
    path = _receipt_path(ctx, receipt.receipt_id)
    if path is not None:
        authentication = SearchReceiptAuthenticationV1(
            receipt_id=receipt.receipt_id,
            obligation_id=obligation_id,
            repo_snapshot_id=receipt.repo_snapshot_id,
            project_tree_hash=receipt.project_tree_hash,
            ledger_digest=receipt.ledger_digest,
            execution_record_ids=receipt.execution_record_ids,
            derived_receipt_digest=receipt.content_digest,
            failures=failures,
        )
        _write_json(
            path,
            {
                "receipt": receipt.model_dump(mode="json"),
                "authentication": authentication.model_dump(mode="json"),
            },
        )
    return receipt, failures


def load_persisted_receipt(
    ctx: Any, receipt_id: str
) -> tuple[SearchReceiptV1 | None, SearchReceiptAuthenticationV1 | None]:
    """Load a persisted receipt plus its authentication record."""

    path = _receipt_path(ctx, receipt_id)
    if path is None or not path.is_file():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    if not isinstance(payload, Mapping):
        return None, None
    try:
        receipt = SearchReceiptV1.model_validate(payload.get("receipt"))
        authentication = SearchReceiptAuthenticationV1.model_validate(
            payload.get("authentication")
        )
    except (TypeError, ValueError):
        return None, None
    return receipt, authentication


def authenticate_search_receipt(
    ctx: Any,
    receipt_id: str,
    *,
    obligation_id: str = "",
) -> tuple[SearchReceiptV1 | None, tuple[str, ...]]:
    """Re-verify a receipt id against the run's trusted execution ledger.

    The stored receipt must (a) exist in the artifact store, (b) carry the
    execution layer's authentication verdict, (c) match its own ledger prefix
    byte for byte, and (d) still equal the receipt the current ledger derives.
    A caller-authored receipt has no store record and fails at (a); a receipt
    minted before later executions fails at (d), which keeps a stale closure
    from authorizing a conclusion the newer frontier no longer supports.
    """

    if not str(receipt_id).strip():
        return None, ("search_receipt_id_missing",)
    receipt, authentication = load_persisted_receipt(ctx, receipt_id)
    if receipt is None or authentication is None:
        return None, ("search_receipt_unknown",)
    failures: list[str] = []
    if authentication.receipt_id != receipt.receipt_id:
        failures.append("search_receipt_authentication_id_mismatch")
    if authentication.authentication != AUTHENTICATION_LEDGER_VERIFIED:
        failures.append("search_receipt_not_ledger_verified")
    if authentication.ledger_digest != receipt.ledger_digest:
        failures.append("search_receipt_ledger_digest_mismatch")
    if authentication.derived_receipt_digest != receipt.content_digest:
        failures.append("search_receipt_derivation_digest_mismatch")
    if obligation_id and receipt.obligation_id != obligation_id:
        failures.append("search_receipt_obligation_mismatch")
    expected_id = str(ctx.repo_snapshot.snapshot_id)
    if receipt.repo_snapshot_id != expected_id:
        failures.append("search_receipt_snapshot_mismatch")
    if receipt.project_tree_hash != str(ctx.repo_snapshot.project_tree_hash):
        failures.append("search_receipt_tree_mismatch")
    # Re-derive from the records the receipt claims, then from the live ledger.
    records_by_id = {
        record.record_id: record
        for record in iter_execution_records(ctx, receipt.obligation_id)
    }
    prefix: list[ResearchExecutionRecordV1] = []
    for record_id in receipt.execution_record_ids:
        record = records_by_id.get(record_id)
        if record is None:
            failures.append(f"search_receipt_record_missing:{record_id}")
            continue
        prefix.append(record)
    if prefix and ledger_digest(prefix) != receipt.ledger_digest:
        failures.append("search_receipt_ledger_prefix_mismatch")
    try:
        current, _ = derive_frontier_receipt(ctx, receipt.obligation_id)
    except ExecutionLedgerError as exc:
        # A ledger that cannot be read completely cannot prove the frontier.
        failures.append(f"search_receipt_ledger_integrity:{exc}")
        return None, tuple(dict.fromkeys(failures))
    except Exception as exc:  # pragma: no cover - defensive: never authorize
        failures.append(f"search_receipt_ledger_integrity:{type(exc).__name__}")
        return None, tuple(dict.fromkeys(failures))
    if current is None:
        failures.append("search_receipt_ledger_no_longer_derivable")
    elif current.receipt_id != receipt.receipt_id:
        failures.append("search_receipt_stale")
    if failures:
        return None, tuple(dict.fromkeys(failures))
    return receipt, ()


def verify_receipt_authentication(
    receipt: Any,
    *,
    obligation_id: str = "",
    snapshot_id: str = "",
    ledger_reader: Any | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Consumer-side reuse of the execution layer's authentication verdict.

    When the consumer can reach the run's ledger it re-derives the receipt from
    the raw executions (``ledger_reader``), so a receipt restored from a
    truncated or corrupted ledger is refused here as well.
    """
    """Consumer-side reuse of the execution layer's authentication verdict.

    Consumers without ledger access (terminal evaluators, coverage reports)
    must not re-invent a boolean list check.  They validate the receipt contract
    and require the ledger-authenticated derivation recorded by the producer.
    """

    if receipt is None:
        return False, ("search_receipt_missing",)
    if hasattr(receipt, "model_dump"):
        payload = receipt.model_dump(mode="json")
    elif isinstance(receipt, Mapping):
        payload = dict(receipt)
    else:
        return False, ("search_receipt_not_a_receipt",)
    try:
        typed = SearchReceiptV1.model_validate(payload)
    except (TypeError, ValueError):
        return False, ("search_receipt_contract_invalid",)
    failures: list[str] = []
    if typed.authentication != AUTHENTICATION_LEDGER_VERIFIED:
        failures.append("search_receipt_not_ledger_verified")
    if not typed.ledger_digest or not typed.execution_record_ids:
        failures.append("search_receipt_without_ledger_prefix")
    if not typed.frontier_closed():
        failures.append("search_receipt_frontier_not_closed")
    if obligation_id and typed.obligation_id != obligation_id:
        failures.append("search_receipt_obligation_mismatch")
    if snapshot_id and typed.repo_snapshot_id != snapshot_id:
        failures.append("search_receipt_snapshot_mismatch")
    if failures:
        return False, tuple(dict.fromkeys(failures))
    if ledger_reader is not None:
        try:
            rederived = ledger_reader(typed.receipt_id)
        except ExecutionLedgerError as exc:
            return False, (f"search_receipt_ledger_integrity:{exc}",)
        except Exception as exc:  # pragma: no cover - defensive
            return False, (
                f"search_receipt_ledger_integrity:{type(exc).__name__}",
            )
        if rederived is None:
            return False, ("search_receipt_ledger_no_longer_derivable",)
        # Identity, not merely "an object came back": the re-derived receipt
        # must be the declared one, for the same obligation and revision.
        rederived_payload = (
            rederived.model_dump(mode="json")
            if hasattr(rederived, "model_dump")
            else dict(rederived)
            if isinstance(rederived, Mapping)
            else {}
        )
        if str(rederived_payload.get("receipt_id") or "") != typed.receipt_id:
            return False, ("search_receipt_ledger_identity_mismatch",)
        if (
            str(rederived_payload.get("content_digest") or "")
            and str(rederived_payload.get("content_digest"))
            != typed.content_digest
        ):
            return False, ("search_receipt_ledger_content_mismatch",)
        if str(rederived_payload.get("obligation_id") or "") != typed.obligation_id:
            return False, ("search_receipt_ledger_obligation_mismatch",)
        if (
            str(rederived_payload.get("repo_snapshot_id") or "")
            != typed.repo_snapshot_id
        ):
            return False, ("search_receipt_ledger_snapshot_mismatch",)
    return True, ()


def receipt_scope_covers(
    declared_scope: Iterable[str], receipt: SearchReceiptV1
) -> bool:
    """Return whether every declared scope path is inside the receipt scope."""

    declared = tuple(
        str(value).strip() for value in (declared_scope or ()) if str(value).strip()
    )
    if not declared:
        return True
    if WHOLE_SNAPSHOT_SCOPE in receipt.filter_scope:
        return True
    for path in declared:
        covered = False
        for scope in receipt.filter_scope:
            if path == scope or path.startswith(scope.rstrip("/") + "/"):
                covered = True
                break
        if not covered:
            return False
    return True


__all__ = [
    "AUTHENTICATION_LEDGER_VERIFIED",
    "EXECUTION_LEDGER_INDEX_NAME",
    "ExecutionLedgerError",
    "ExecutionLedgerIntegrityError",
    "ExecutionLedgerReplayMismatch",
    "DISCOVERY_TOOLS",
    "EVIDENCE_TOOLS",
    "EXECUTED_STATUSES",
    "EXECUTION_LEDGER_DIR",
    "READ_TOOLS",
    "RELATION_TOOLS",
    "SEARCH_RECEIPT_DIR",
    "WHOLE_SNAPSHOT_SCOPE",
    "ReadSpanV1",
    "ResearchExecutionRecordV1",
    "SearchReceiptAuthenticationV1",
    "authenticate_search_receipt",
    "build_context_ledger_reader",
    "check_execution_call_identity",
    "derive_frontier_receipt",
    "frontier_gap_reasons",
    "iter_execution_records",
    "ledger_digest",
    "load_persisted_receipt",
    "mint_frontier_receipt",
    "receipt_scope_covers",
    "record_ledger_conflict",
    "record_ledger_write_failure",
    "record_tool_execution",
    "verify_receipt_authentication",
]
