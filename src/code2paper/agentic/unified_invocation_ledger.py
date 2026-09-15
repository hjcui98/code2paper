"""Durable invocation ledger: atomic receipts, fragments, and resume.

Implements section 9.8 of
``docs/dyg_mamba_unified_live_run_failure_diagnosis_and_remediation_2026-09-08.md``.

Every actual request produces independent, atomically published files:

    <ledger_root>/<invocation_id>/
        attempt-0001.started.json
        attempt-0001.completed.json
        package-fragment.json      # formalizer success fragment
        output-fragment.json       # writer/realizer success fragment

``started`` files are published with ``os.replace`` before the model call;
the ``completed`` receipt is the commit marker published last.  Aggregate
artifacts are rebuilt from receipts, never treated as the resume authority.
Resume reuses an invocation only when exactly one completed receipt has an
accepted delivery and every upstream, page, envelope, model, and fragment
digest matches the current plan; any mismatch invalidates the invocation and
its downstream dependency closure only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from code2paper.agentic.unified_context_models import (
    UNIFIED_RESUME_DIGEST_MISMATCH,
    UNIFIED_UNPLANNED_ACTUAL_REQUEST,
    ActualRequestReceiptV2,
    ConsumerInvocationPlanV1,
    InvocationAttemptStartedV1,
    sha256_digest,
)

_LEDGER_SCHEMA_VERSION = "2.0"
_SAFE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_invocation_dir_name(invocation_id: str) -> str:
    """Content-addressed, filesystem-safe directory name for one invocation."""

    component = _SAFE_COMPONENT_RE.sub("-", invocation_id).strip("-.")
    digest = hashlib.sha256(
        b"code2paper-invocation-ledger-v2\0" + invocation_id.encode("utf-8")
    ).hexdigest()[:16]
    return f"{component or 'invocation'}-{digest}"


def invocation_dir(ledger_root: Path, invocation_id: str) -> Path:
    return Path(ledger_root) / _safe_invocation_dir_name(invocation_id)


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to a temp file in the same directory, then os.replace."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.tmp-{os.getpid()}"
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.tmp-{os.getpid()}"
    temp_path.write_bytes(payload)
    os.replace(temp_path, path)


def _dump(model: Any) -> str:
    import json

    return json.dumps(
        model.model_dump(mode="json") if hasattr(model, "model_dump") else model,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _fragment_payload_digest(payload: Mapping[str, Any]) -> str:
    """Digest the canonical fragment envelope, independent of file spacing."""

    import json

    return sha256_digest(json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8"))


def publish_attempt_started(
    ledger_root: Path,
    started: InvocationAttemptStartedV1,
) -> Path:
    """Publish the durable start marker for one attempt before the call."""

    path = invocation_dir(ledger_root, started.invocation_id) / (
        f"attempt-{started.attempt:04d}.started.json"
    )
    _atomic_write_text(path, _dump(started))
    return path


def publish_package_fragment(
    ledger_root: Path,
    *,
    invocation_id: str,
    attempt: int,
    fragment: Mapping[str, Any],
) -> str:
    """Publish one formalizer package fragment; return its digest."""

    import json

    payload = {
        "schema_version": _LEDGER_SCHEMA_VERSION,
        "invocation_id": invocation_id,
        "attempt": attempt,
        "fragment": dict(fragment),
    }
    digest = _fragment_payload_digest(payload)
    path = invocation_dir(ledger_root, invocation_id) / (
        f"attempt-{attempt:04d}.package-fragment-"
        f"{digest.removeprefix('sha256:')[:16]}.json"
    )
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return digest


def publish_output_fragment(
    ledger_root: Path,
    *,
    invocation_id: str,
    attempt: int,
    fragment: Mapping[str, Any],
) -> str:
    """Publish one writer/realizer output fragment; return its digest."""

    import json

    payload = {
        "schema_version": _LEDGER_SCHEMA_VERSION,
        "invocation_id": invocation_id,
        "attempt": attempt,
        "fragment": dict(fragment),
    }
    digest = _fragment_payload_digest(payload)
    path = invocation_dir(ledger_root, invocation_id) / (
        f"attempt-{attempt:04d}.output-fragment-"
        f"{digest.removeprefix('sha256:')[:16]}.json"
    )
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return digest


def publish_attempt_completed(
    ledger_root: Path,
    receipt: ActualRequestReceiptV2,
) -> Path:
    """Publish the completed receipt: the commit marker for one invocation."""

    path = invocation_dir(ledger_root, receipt.invocation_id) / (
        f"attempt-{receipt.attempt:04d}.completed.json"
    )
    _atomic_write_text(path, _dump(receipt))
    return path


def _diagnostic_path(root: Path, invocation_id: str, attempt: int, kind: str) -> Path:
    return invocation_dir(root, invocation_id) / f"attempt-{attempt:04d}.provider-{kind}.json"


def _write_diagnostic(path: Path, payload: dict[str, Any]) -> str:
    digest = _fragment_payload_digest(payload)
    value = {**payload, "content_digest": digest}
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError("unified_provider_diagnostic_replay_mismatch")
        return digest
    _atomic_write_text(path, _dump(value))
    return digest


def _json_safe(value: Any) -> Any:
    """Return bounded JSON-safe diagnostic data without leaking credentials."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump(mode="json"))
        except Exception:  # noqa: BLE001 - diagnostics must never mask a receipt
            return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _response_value(response: Any, name: str, default: Any = None) -> Any:
    if isinstance(response, Mapping):
        return response.get(name, default)
    return getattr(response, name, default)


def publish_provider_request(root: Path, invocation_id: str, attempt: int, request: Any, config: Any) -> str:
    """Persist the actual request before transport; never serialize credentials."""
    def redact(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): ("<redacted>" if str(k).lower() in {
                "api_key", "authorization", "access_token", "password", "secret",
            } else redact(v)) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [redact(v) for v in value]
        return value

    return _write_diagnostic(_diagnostic_path(root, invocation_id, attempt, "request"), {
        "schema_version": "1.0", "invocation_id": invocation_id, "attempt": attempt,
        "request_digest": request.input_hash,
        "prompt_template_id": request.prompt_template_id,
        "prompt": request.prompt, "input_payload": redact(request.input_payload),
        "response_schema": request.response_json_schema,
        "config": {key: getattr(config, key, None) for key in (
            "model", "role", "max_output_tokens", "thinking_token_budget",
            "reasoning_effort", "temperature", "top_p", "top_k", "seed",
        )},
    })


def publish_provider_response(root: Path, invocation_id: str, attempt: int, response: Any) -> str:
    request = _diagnostic_path(root, invocation_id, attempt, "request")
    value = json.loads(request.read_text())
    request_digest = value.pop("content_digest")
    if _fragment_payload_digest(value) != request_digest:
        raise ValueError("unified_provider_request_corrupt")
    text = response if isinstance(response, str) else str(_response_value(response, "text", "") or "")
    usage = _response_value(response, "token_usage", None)
    if not isinstance(usage, Mapping):
        usage = _response_value(response, "usage", None)
    if not isinstance(usage, Mapping):
        usage = None
    blocked_reason = str(_response_value(response, "blocked_reason", "") or "")
    finish_reason = str(_response_value(response, "finish_reason", "") or "")
    provider_finish_reason = str(
        _response_value(response, "provider_finish_reason", "") or ""
    )
    provider_diagnostics = _response_value(response, "provider_diagnostics", None)
    return _write_diagnostic(_diagnostic_path(root, invocation_id, attempt, "response"), {
        "schema_version": "1.0", "invocation_id": invocation_id, "attempt": attempt,
        "request_diagnostics_digest": request_digest,
        "response_text": text, "response_digest": sha256_digest(text.encode()),
        "finish_reason": finish_reason,
        "provider_finish_reason": provider_finish_reason,
        "thinking_chars": int(_response_value(response, "thinking_chars", 0) or 0),
        "usage": _json_safe(usage),
        "blocked_reason": blocked_reason,
        "diagnostics": _json_safe(provider_diagnostics),
    })


def _verify_provider_diagnostics(root: Path, receipt: ActualRequestReceiptV2) -> None:
    if not receipt.provider_diagnostics_digest:
        return
    value = json.loads(_diagnostic_path(root, receipt.invocation_id, receipt.attempt, "response").read_text())
    digest = value.pop("content_digest")
    if digest != receipt.provider_diagnostics_digest or _fragment_payload_digest(value) != digest:
        raise ValueError("unified_provider_response_corrupt")
    if (value["invocation_id"], value["attempt"], value["usage"]) != (
        receipt.invocation_id, receipt.attempt, receipt.provider_usage,
    ):
        raise ValueError("unified_provider_receipt_identity_mismatch")
    request = json.loads(_diagnostic_path(root, receipt.invocation_id, receipt.attempt, "request").read_text())
    request_digest = request.pop("content_digest")
    if request_digest != value["request_diagnostics_digest"] or _fragment_payload_digest(request) != request_digest:
        raise ValueError("unified_provider_request_corrupt")


def publish_writer_content_acceptance(
    root: Path, receipt: ActualRequestReceiptV2, *, accepted: bool,
    response_text: str, failures: list[str],
) -> str:
    """Append content acceptance without rewriting the transport receipt."""
    path = invocation_dir(root, receipt.invocation_id) / f"attempt-{receipt.attempt:04d}.content-acceptance.json"
    transport_accepted = bool(
        receipt.delivery_status == "accepted"
        and receipt.sent_to_caller
        and receipt.response_digest
    )
    transport_response_status = (
        "nonempty"
        if receipt.response_digest and receipt.task_status != "failed"
        else "empty"
    )
    return _write_diagnostic(path, {
        "schema_version": "1.0", "validator": "writer-paragraph-transaction-v1",
        "invocation_id": receipt.invocation_id, "attempt": receipt.attempt,
        "receipt_digest": receipt.content_digest, "plan_digest": receipt.upstream_plan_digest,
        # These fields deliberately do not overwrite the transport receipt.
        # They describe the next gates in the contract independently.
        "transport_status": "accepted" if transport_accepted else "rejected",
        "transport_response_status": transport_response_status,
        "transport_task_status": receipt.task_status,
        "content_acceptance_status": "accepted" if accepted else "rejected",
        "accepted": bool(accepted),
        "repair_committed": bool(receipt.content_repair_attempt and accepted),
        "resume_eligible": bool(transport_accepted and accepted),
        "response_text": response_text, "failures": list(failures),
    })


def read_writer_content_acceptance(root: Path, receipt: ActualRequestReceiptV2) -> dict[str, Any] | None:
    path = invocation_dir(root, receipt.invocation_id) / f"attempt-{receipt.attempt:04d}.content-acceptance.json"
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    digest = value.pop("content_digest")
    if _fragment_payload_digest(value) != digest or (
        value["invocation_id"], value["attempt"], value["receipt_digest"], value["plan_digest"]
    ) != (receipt.invocation_id, receipt.attempt, receipt.content_digest, receipt.upstream_plan_digest):
        raise ValueError("unified_writer_content_acceptance_corrupt")
    accepted = bool(value.get("accepted", False))
    status = str(value.get("content_acceptance_status") or (
        "accepted" if accepted else "rejected"
    ))
    if status not in {"accepted", "rejected"} or (status == "accepted") != accepted:
        raise ValueError("unified_writer_content_acceptance_status_invalid")
    transport_accepted = bool(
        receipt.delivery_status == "accepted"
        and receipt.sent_to_caller
        and receipt.response_digest
    )
    # Old acceptance sidecars did not carry the four-way status projection;
    # derive it after verifying their legacy digest. New sidecars must satisfy
    # the same invariants and are returned with explicit fields.
    value.setdefault(
        "transport_status", "accepted" if transport_accepted else "rejected"
    )
    value.setdefault(
        "transport_response_status",
        "nonempty"
        if receipt.response_digest and receipt.task_status != "failed"
        else "empty",
    )
    value.setdefault("transport_task_status", receipt.task_status)
    value.setdefault("content_acceptance_status", status)
    value.setdefault("repair_committed", bool(receipt.content_repair_attempt and accepted))
    value.setdefault("resume_eligible", bool(transport_accepted and accepted))
    if value["transport_status"] != ("accepted" if transport_accepted else "rejected"):
        raise ValueError("unified_writer_content_acceptance_transport_status_invalid")
    expected_response_status = (
        "nonempty"
        if receipt.response_digest and receipt.task_status != "failed"
        else "empty"
    )
    if value["transport_response_status"] != expected_response_status:
        raise ValueError("unified_writer_content_acceptance_response_status_invalid")
    if bool(value["repair_committed"]) != bool(receipt.content_repair_attempt and accepted):
        raise ValueError("unified_writer_content_acceptance_repair_status_invalid")
    if bool(value["resume_eligible"]) != bool(transport_accepted and accepted):
        raise ValueError("unified_writer_content_acceptance_resume_status_invalid")
    return value


def read_completed_receipts(
    ledger_root: Path,
    invocation_id: str,
) -> tuple[ActualRequestReceiptV2, ...]:
    """Return every parseable completed receipt for one invocation."""

    directory = invocation_dir(ledger_root, invocation_id)
    if not directory.is_dir():
        return ()
    import json

    receipts: list[ActualRequestReceiptV2] = []
    for path in sorted(directory.glob("attempt-*.completed.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            receipt = ActualRequestReceiptV2.model_validate(payload)
            _verify_provider_diagnostics(ledger_root, receipt)
            receipts.append(receipt)
        except Exception:
            # A half-written or corrupt receipt is not success evidence; it
            # simply cannot authorize resume reuse.
            continue
    return tuple(receipts)


def read_all_completed_receipts(
    ledger_root: Path,
    *,
    strict: bool = False,
) -> tuple[ActualRequestReceiptV2, ...]:
    """Return every completed receipt under one ledger root.

    A run-level budget debit must see every phase's receipts, not one
    invocation's, so retries and resumed attempts consume the same
    reservation.  ``strict=True`` refuses to silently skip a corrupt receipt:
    an unreadable record cannot prove the run did not spend that budget.
    """

    root = Path(ledger_root)
    if not root.is_dir():
        return ()
    receipts: list[ActualRequestReceiptV2] = []
    corrupt: list[str] = []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        for path in sorted(directory.glob("attempt-*.completed.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                receipt = ActualRequestReceiptV2.model_validate(payload)
                _verify_provider_diagnostics(root, receipt)
                receipts.append(receipt)
            except Exception:
                corrupt.append(path.name)
                continue
    if strict and corrupt:
        raise ValueError("unified_receipt_corrupt:" + ",".join(sorted(corrupt)[:5]))
    return tuple(receipts)


def register_invocation_plan(ledger_root: Path, plan: Any) -> Path | None:
    """Persist one plan's per-invocation input allowance.

    R6 correction: an attempt that started under an older revision is not in
    the current plan, so its conservative reserve cannot be read from the
    current invocation list.  The durable plan record lets a later revision
    meter that attempt from its *original* allowance instead of zero.
    """

    digest = str(getattr(plan, "content_digest", "") or "").strip()
    if not digest:
        return None
    invocations: dict[str, Any] = {}
    for invocation in (getattr(plan, "invocations", ()) or ()):
        invocation_id = str(getattr(invocation, "invocation_id", "") or "")
        if not invocation_id:
            continue
        invocations[invocation_id] = {
            "max_input_tokens": int(
                getattr(invocation, "max_input_tokens", 0) or 0
            ),
            "role": str(getattr(invocation, "role", "") or ""),
            "phase": str(getattr(invocation, "phase", "") or ""),
            "is_repair": bool(getattr(invocation, "is_repair", False)),
            "page_id": str(getattr(invocation, "page_id", "") or ""),
        }
    if not invocations:
        return None
    directory = Path(ledger_root) / "plans"
    path = directory / f"{_SAFE_COMPONENT_RE.sub('-', digest).strip('-')[:120]}.json"
    if path.is_file():
        return path
    _atomic_write_text(
        path,
        json.dumps(
            {
                "schema_version": _LEDGER_SCHEMA_VERSION,
                "plan_digest": digest,
                "plan_revision": int(getattr(plan, "plan_revision", 1)),
                "reserved_input_tokens_by_role": dict(
                    getattr(plan, "reserved_input_tokens_by_role", {}) or {}
                ),
                "invocations": invocations,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return path


def _recorded_plan_invocation_tokens(
    ledger_root: Path, plan_digest: str
) -> dict[str, int]:
    """Return ``{invocation_id: max_input_tokens}`` for one recorded plan."""

    digest = str(plan_digest or "").strip()
    if not digest:
        return {}
    directory = Path(ledger_root) / "plans"
    path = directory / f"{_SAFE_COMPONENT_RE.sub('-', digest).strip('-')[:120]}.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    invocations = payload.get("invocations") if isinstance(payload, Mapping) else None
    if not isinstance(invocations, Mapping):
        return {}
    return {
        str(invocation_id): int(
            (entry or {}).get("max_input_tokens", 0)
            if isinstance(entry, Mapping) else 0
        )
        for invocation_id, entry in invocations.items()
    }


@dataclass(frozen=True)
class UnsettledAttemptV1:
    """One started attempt that never published a completed receipt.

    ``plan_source`` says where the reserve came from: the current plan, the
    plan record the attempt started under, or ``unknown`` when neither can
    meter it.  An ``unknown`` attempt must block a run-budget decision instead
    of being counted as zero.
    """

    invocation_id: str
    attempt: int
    planned_input_tokens: int
    plan_source: Literal["current_plan", "recorded_plan", "unknown"]
    plan_digest: str = ""
    consumer_role: str = ""
    content_repair_attempt: bool = False


def unsettled_started_attempt_records(
    ledger_root: Path,
    plan: Any,
    *,
    exclude: tuple[str, int] | None = None,
) -> tuple[UnsettledAttemptV1, ...]:
    """Return typed started attempts that never produced a receipt."""

    root = Path(ledger_root)
    if not root.is_dir():
        return ()
    invocation_tokens = {
        str(getattr(invocation, "invocation_id", "")): int(
            getattr(invocation, "max_input_tokens", 0) or 0
        )
        for invocation in (getattr(plan, "invocations", ()) or ())
        if str(getattr(invocation, "invocation_id", ""))
    }
    invocation_roles = {
        str(getattr(invocation, "invocation_id", "")): str(
            getattr(invocation, "role", "") or ""
        )
        for invocation in (getattr(plan, "invocations", ()) or ())
        if str(getattr(invocation, "invocation_id", ""))
    }
    records: list[UnsettledAttemptV1] = []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        if directory.name == "plans":
            continue
        started = {
            path.name.removeprefix("attempt-").removesuffix(".started.json"): path
            for path in directory.glob("attempt-*.started.json")
        }
        completed = {
            path.name.removeprefix("attempt-").removesuffix(".completed.json")
            for path in directory.glob("attempt-*.completed.json")
        }
        invocation_id = directory.name.replace("-", ":", 0)
        for attempt in sorted(started.keys() - completed, key=lambda value: value):
            started_path = started[attempt]
            matched = next(
                (
                    candidate
                    for candidate in invocation_tokens
                    if _safe_invocation_dir_name(candidate) == directory.name
                ),
                "",
            )
            try:
                attempt_number = int(attempt)
            except ValueError:
                attempt_number = 0
            resolved_id = matched or invocation_id
            if exclude is not None and (
                str(resolved_id),
                attempt_number,
            ) == (str(exclude[0]), int(exclude[1])):
                # The attempt being measured right now is not an unsettled
                # crash; it is about to be sent under this very measurement.
                continue
            started_plan_digest = ""
            marker_verified = False
            content_repair_attempt = False
            try:
                marker = json.loads(started_path.read_text(encoding="utf-8"))
                if isinstance(marker, Mapping):
                    started_plan_digest = str(marker.get("plan_digest") or "")
                    marker_verified = bool(started_plan_digest)
                    content_repair_attempt = bool(marker.get("content_repair_attempt", False))
            except (OSError, ValueError, json.JSONDecodeError):
                marker_verified = False
            current_plan_digest = str(getattr(plan, "content_digest", "") or "")
            if matched and marker_verified and started_plan_digest == current_plan_digest:
                # The attempt started under this very plan: its own allowance is
                # the current one.
                records.append(UnsettledAttemptV1(
                    invocation_id=matched,
                    attempt=attempt_number,
                    planned_input_tokens=invocation_tokens.get(matched, 0),
                    plan_source="current_plan",
                    plan_digest=started_plan_digest,
                    consumer_role=invocation_roles.get(matched, ""),
                    content_repair_attempt=content_repair_attempt,
                ))
                continue
            # R6 correction: the same invocation id can survive a revision with
            # a different allowance, so a matched id alone is not proof that the
            # current plan's number applies.  Meter the attempt from the plan it
            # actually started under.
            recorded = _recorded_plan_invocation_tokens(
                root, started_plan_digest
            )
            recorded_tokens = next(
                (
                    tokens
                    for candidate, tokens in recorded.items()
                    if _safe_invocation_dir_name(candidate) == directory.name
                ),
                None,
            )
            if marker_verified and recorded_tokens is not None:
                records.append(UnsettledAttemptV1(
                    invocation_id=matched or resolved_id,
                    attempt=attempt_number,
                    planned_input_tokens=int(recorded_tokens),
                    plan_source="recorded_plan",
                    plan_digest=started_plan_digest,
                    consumer_role=invocation_roles.get(matched, ""),
                    content_repair_attempt=content_repair_attempt,
                ))
                continue
            # Either the marker carries no plan identity or that plan record is
            # missing: the attempt cannot be metered, so it is reported as
            # unknown and the caller blocks instead of reserving zero.
            records.append(UnsettledAttemptV1(
                invocation_id=matched or resolved_id,
                attempt=attempt_number,
                planned_input_tokens=0,
                plan_source="unknown",
                plan_digest=started_plan_digest,
                consumer_role=invocation_roles.get(matched, ""),
                content_repair_attempt=content_repair_attempt,
            ))
    return tuple(records)


def unsettled_started_attempts(
    ledger_root: Path,
    plan: Any,
    *,
    exclude: tuple[str, int] | None = None,
) -> tuple[tuple[str, int, int], ...]:
    """Return started attempts that never produced a completed receipt.

    A crash between the provider call and the receipt may still have spent the
    request's input tokens, so the run budget conservatively reserves the
    planned tokens for each unsettled attempt.  An attempt whose original plan
    cannot be read is reported with ``0`` here; callers that must not guess use
    :func:`unsettled_started_attempt_records` and fail closed on
    ``plan_source == "unknown"``.
    """

    return tuple(
        (record.invocation_id, record.attempt, record.planned_input_tokens)
        for record in unsettled_started_attempt_records(
            ledger_root, plan, exclude=exclude
        )
    )


def read_run_budget_state(ledger_root: Path) -> dict[str, Any]:
    """Read the durable whole-run debit state used by every authoring lane.

    Page invocations have a typed ``ConsumerInvocationPlanV1``.  Auxiliary
    authoring requests (planner, verifier and organization proposal) cannot
    honestly be represented as pages, so their accounting files are folded
    into this ledger-level view instead.  The function is deliberately
    fail-closed: a corrupt receipt, plan, started marker or auxiliary tally is
    reported as a failure rather than treated as an empty run.

    ``reserved_input_tokens`` is the amount that must remain unavailable for a
    new request: the latest durable page-plan reservation plus page unsettled
    reservations, and the measured/pending auxiliary debits.  A completed
    auxiliary request releases any difference between its reservation and its
    measured input; an unsent refusal contributes neither spent nor pending
    cost.
    """

    root = Path(ledger_root)
    failures: list[str] = []
    page_spent: dict[str, int] = {}
    page_pending: dict[str, int] = {}
    page_pending_content_repair: dict[str, int] = {}
    page_reserved: dict[str, int] = {}
    page_completed_calls: dict[str, int] = {}
    page_pending_calls: dict[str, int] = {}
    active_primary_plans: dict[str, tuple[int, str, dict[str, Any]]] = {}
    covered_primary: set[tuple[str, str]] = set()
    plan_invocations: dict[tuple[str, str], dict[str, Any]] = {}
    completed_receipts: tuple[ActualRequestReceiptV2, ...] = ()
    provider_usage_missing_receipts: list[str] = []
    provider_usage_missing_input_tokens = 0

    try:
        completed_receipts = read_all_completed_receipts(root, strict=True)
        from code2paper.agentic.unified_context_compiler import (
            spend_input_tokens_by_role,
        )

        page_spent = spend_input_tokens_by_role(completed_receipts)
        covered_primary.update((r.upstream_plan_digest, r.invocation_id)
                               for r in completed_receipts if r.sent_to_caller)
        for receipt in completed_receipts:
            role = str(getattr(receipt, "consumer_role", "") or "")
            if role and bool(getattr(receipt, "sent_to_caller", True)):
                page_completed_calls[role] = page_completed_calls.get(role, 0) + 1
            if bool(getattr(receipt, "sent_to_caller", True)) and (
                getattr(receipt, "provider_usage", None) is None
            ):
                provider_usage_missing_receipts.append(
                    f"{receipt.invocation_id}:{receipt.attempt}"
                )
                accounting = getattr(receipt, "token_accounting", None)
                if accounting is not None:
                    provider_usage_missing_input_tokens += max(
                        0, int(getattr(accounting, "input_tokens", 0) or 0)
                    )
    except Exception as exc:  # noqa: BLE001 - unknown spend must block
        failures.append(f"unified_receipt_corrupt:{type(exc).__name__}")

    plan_root = root / "plans"
    if plan_root.is_dir():
        for plan_path in sorted(plan_root.glob("*.json")):
            try:
                payload = json.loads(plan_path.read_text(encoding="utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError("plan payload is not an object")
                plan_digest = str(payload.get("plan_digest") or "").strip()
                if not plan_digest:
                    raise ValueError("plan digest is missing")
                reserved = payload.get("reserved_input_tokens_by_role") or {}
                if not isinstance(reserved, Mapping):
                    raise ValueError("plan reservations are not an object")
                for role, value in reserved.items():
                    page_reserved[str(role)] = max(
                        page_reserved.get(str(role), 0), int(value)
                    )
                invocations = payload.get("invocations") or {}
                if not isinstance(invocations, Mapping):
                    raise ValueError("plan invocations are not an object")
                if "plan_revision" in payload:
                    revision = int(payload["plan_revision"])
                    for role in {str(e.get("role", "")) for e in invocations.values()}:
                        entries = {key: e for key, e in invocations.items() if e.get("role") == role}
                        prior = active_primary_plans.get(role)
                        if prior and prior[0] == revision and prior[1] != plan_digest and prior[2] != entries:
                            raise ValueError("ambiguous primary plan revision")
                        if prior is None or revision > prior[0]:
                            active_primary_plans[role] = (revision, plan_digest, entries)
                for invocation_id, entry in invocations.items():
                    if not isinstance(entry, Mapping):
                        raise ValueError("plan invocation entry is not an object")
                    normalized_id = str(invocation_id)
                    plan_invocations[(plan_digest, normalized_id)] = {
                        "max_input_tokens": max(
                            0, int(entry.get("max_input_tokens", 0) or 0)
                        ),
                        "role": str(entry.get("role") or ""),
                        "is_repair": bool(entry.get("is_repair", False)),
                    }
            except Exception as exc:  # noqa: BLE001 - plan is an authority
                failures.append(
                    f"unified_plan_corrupt:{plan_path.name}:{type(exc).__name__}"
                )

    # A started page attempt without a completion receipt retains its original
    # plan reservation.  It is not enough to scan only the current plan: a
    # resumed run may have changed revision and the old plan is the authority
    # for the unfinished attempt.
    if root.is_dir():
        for directory in sorted(path for path in root.iterdir() if path.is_dir()):
            if directory.name == "plans":
                continue
            completed_attempts = {
                path.name.removeprefix("attempt-").removesuffix(".completed.json")
                for path in directory.glob("attempt-*.completed.json")
            }
            for started_path in sorted(directory.glob("attempt-*.started.json")):
                attempt_key = started_path.name.removeprefix("attempt-").removesuffix(
                    ".started.json"
                )
                if attempt_key in completed_attempts:
                    continue
                try:
                    marker = json.loads(started_path.read_text(encoding="utf-8"))
                    if not isinstance(marker, Mapping):
                        raise ValueError("started marker is not an object")
                    plan_digest = str(marker.get("plan_digest") or "").strip()
                    invocation_id = str(marker.get("invocation_id") or "").strip()
                    if not plan_digest or not invocation_id:
                        raise ValueError("started marker identity is incomplete")
                    info = plan_invocations.get((plan_digest, invocation_id))
                    if info is None:
                        raise ValueError("started attempt has no recorded plan")
                    role = str(info.get("role") or "")
                    if not role:
                        raise ValueError("started attempt has no recorded role")
                    content_repair_attempt = bool(
                        marker.get("content_repair_attempt", False)
                    )
                    covered_primary.add((plan_digest, invocation_id))
                    page_pending_calls[role] = page_pending_calls.get(role, 0) + 1
                    page_pending[role] = page_pending.get(role, 0) + int(
                        info.get("max_input_tokens", 0) or 0
                    )
                    if content_repair_attempt:
                        page_pending_content_repair[role] = (
                            page_pending_content_repair.get(role, 0)
                            + int(info.get("max_input_tokens", 0) or 0)
                        )
                except Exception as exc:  # noqa: BLE001 - unknown is not zero
                    failures.append(
                        f"unified_unsettled_attempt_unmetered:{started_path.name}:"
                        f"{type(exc).__name__}"
                    )

    auxiliary_spent: dict[str, int] = {}
    auxiliary_pending: dict[str, int] = {}
    auxiliary_completed_calls: dict[str, int] = {}
    auxiliary_pending_calls: dict[str, int] = {}
    accounting_root = root.parent
    if accounting_root.is_dir():
        try:
            from code2paper.agentic.proposal_call_accounting import (
                ProposalCallAccountingV1,
            )

            accounting_paths = sorted(
                accounting_root.glob("proposal_call_accounting*.json")
            )
            for accounting_path in accounting_paths:
                try:
                    accounting = ProposalCallAccountingV1.model_validate_json(
                        accounting_path.read_text(encoding="utf-8")
                    )
                except Exception as exc:  # noqa: BLE001 - tally is an authority
                    failures.append(
                        f"unified_auxiliary_accounting_corrupt:{accounting_path.name}:"
                        f"{type(exc).__name__}"
                    )
                    continue
                for row in accounting.rows:
                    role = str(getattr(row, "consumer_role", "") or "")
                    if role:
                        auxiliary_completed_calls[role] = (
                            auxiliary_completed_calls.get(role, 0) + 1
                        )
                    # ``sent_to_caller`` was added after the first tally
                    # format; getattr keeps old completed real calls charged
                    # while allowing new unsent refusals to cost zero.
                    if not bool(getattr(row, "sent_to_caller", True)):
                        continue
                    if not role:
                        failures.append(
                            f"unified_auxiliary_accounting_role_missing:{accounting_path.name}"
                        )
                        continue
                    auxiliary_spent[role] = auxiliary_spent.get(role, 0) + max(
                        0, int(getattr(row, "measured_input_tokens", 0) or 0)
                    )
                for pending in accounting.pending:
                    role = str(getattr(pending, "consumer_role", "") or "")
                    if not role:
                        failures.append(
                            f"unified_auxiliary_accounting_role_missing:{accounting_path.name}"
                        )
                        continue
                    auxiliary_pending_calls[role] = (
                        auxiliary_pending_calls.get(role, 0) + 1
                    )
                    auxiliary_pending[role] = auxiliary_pending.get(role, 0) + max(
                        0,
                        int(
                            getattr(pending, "reserved_input_tokens", 0)
                            or getattr(pending, "planned_input_tokens", 0)
                            or 0
                        ),
                    )
        except Exception as exc:  # noqa: BLE001 - import/schema is authoritative
            failures.append(f"unified_auxiliary_accounting_unreadable:{type(exc).__name__}")

    future_primary: dict[str, dict[str, Any]] = {}
    future_primary_by_role: dict[str, int] = {}
    for role, (_, digest, entries) in active_primary_plans.items():
        for invocation_id, entry in entries.items():
            if not entry.get("is_repair", False) and (digest, invocation_id) not in covered_primary:
                future_primary[invocation_id] = {"role": role, "input_tokens": int(entry["max_input_tokens"])}
                future_primary_by_role[role] = future_primary_by_role.get(role, 0) + int(
                    entry["max_input_tokens"]
                )
    repair_spent = spend_input_tokens_by_role(
        r for r in completed_receipts if r.content_repair_attempt
    ) if "completed_receipts" in locals() else {}
    effective_reserved: dict[str, int] = {}
    for role in set(page_reserved) | set(page_spent) | set(page_pending):
        effective_reserved[role] = max(
            int(page_reserved.get(role, 0) or 0),
            int(page_spent.get(role, 0) or 0)
            + int(page_pending.get(role, 0) or 0),
        )
    for role in set(auxiliary_spent) | set(auxiliary_pending):
        effective_reserved[role] = effective_reserved.get(role, 0) + int(
            auxiliary_spent.get(role, 0) or 0
        ) + int(auxiliary_pending.get(role, 0) or 0)

    spent_by_role = dict(page_spent)
    for role, value in auxiliary_spent.items():
        spent_by_role[role] = spent_by_role.get(role, 0) + int(value)
    pending_by_role = dict(page_pending)
    for role, value in auxiliary_pending.items():
        pending_by_role[role] = pending_by_role.get(role, 0) + int(value)
    completed_calls_by_role = dict(page_completed_calls)
    for role, value in auxiliary_completed_calls.items():
        completed_calls_by_role[role] = completed_calls_by_role.get(role, 0) + int(value)
    pending_calls_by_role = dict(page_pending_calls)
    for role, value in auxiliary_pending_calls.items():
        pending_calls_by_role[role] = pending_calls_by_role.get(role, 0) + int(value)
    committed_by_role = {
        role: int(spent_by_role.get(role, 0) or 0)
        + int(pending_by_role.get(role, 0) or 0)
        for role in set(spent_by_role) | set(pending_by_role)
    }
    committed_input_tokens = sum(committed_by_role.values())
    return {
        "status": "fail" if failures else "pass",
        "failure_codes": list(dict.fromkeys(failures)),
        "spent_input_tokens_by_role": spent_by_role,
        "pending_input_tokens_by_role": pending_by_role,
        "reserved_input_tokens_by_role": effective_reserved,
        # ``committed`` is the amount already spent or conservatively retained
        # by an unsettled start.  Plan files are exposed separately because a
        # phase plan is not itself provider spend and must not be charged in
        # full when the run has not reached all of its pages.
        "future_primary_reservations": future_primary,
        "future_primary_input_tokens": sum(v["input_tokens"] for v in future_primary.values()),
        "future_primary_input_tokens_by_role": future_primary_by_role,
        "pending_content_repair_input_tokens_by_role": page_pending_content_repair,
        "content_repair_spent_by_role": repair_spent,
        "provider_usage_status": (
            "validated" if not provider_usage_missing_receipts else "partial"
        ),
        "provider_usage_missing_receipts": provider_usage_missing_receipts,
        "provider_usage_missing_call_count": len(provider_usage_missing_receipts),
        "provider_usage_missing_input_tokens": provider_usage_missing_input_tokens,
        "committed_input_tokens_by_role": committed_by_role,
        "committed_input_tokens": committed_input_tokens,
        "spent_input_tokens": sum(spent_by_role.values()),
        "pending_input_tokens": sum(pending_by_role.values()),
        "completed_calls_by_role": completed_calls_by_role,
        "pending_calls_by_role": pending_calls_by_role,
        "call_count_by_role": {
            role: int(completed_calls_by_role.get(role, 0) or 0)
            + int(pending_calls_by_role.get(role, 0) or 0)
            for role in set(completed_calls_by_role) | set(pending_calls_by_role)
        },
        "completed_call_count": sum(completed_calls_by_role.values()),
        "pending_call_count": sum(pending_calls_by_role.values()),
        "call_count": sum(completed_calls_by_role.values())
        + sum(pending_calls_by_role.values()),
        "reserved_input_tokens": sum(effective_reserved.values()),
        "completed_receipt_count": len(completed_receipts)
        if "completed_receipts" in locals()
        else 0,
        "plan_count": sum(1 for _ in plan_root.glob("*.json"))
        if plan_root.is_dir() else 0,
        "auxiliary_accounting_files": [
            path.name
            for path in sorted(accounting_root.glob("proposal_call_accounting*.json"))
        ] if accounting_root.is_dir() else [],
    }


def check_run_budget_before_send(
    ledger_root: Path,
    envelope: Any,
    *,
    role: str,
    request_input_tokens: int,
    current_reserved_input_tokens: int = 0,
    current_attempt_recorded: bool = True,
    invocation_id: str = "",
    is_content_repair: bool = False,
) -> tuple[str, ...]:
    """Check cumulative calls and input before a transport boundary.

    ``current_attempt_recorded`` is true for both page and auxiliary callers
    in production: each publishes its started/pending record before entering
    this function.  The current reservation is replaced by the measured
    request when it is smaller, rather than double-counted; a larger measured
    request is rejected against the same run total.
    """

    from code2paper.agentic.unified_context_models import (
        UNIFIED_INVOCATION_BUDGET_EXCEEDED,
        UNIFIED_INVOCATION_BUDGET_MISSING,
    )

    state = read_run_budget_state(Path(ledger_root))
    failures = list(state.get("failure_codes") or ())
    role_name = str(role or "").strip()
    if not role_name:
        failures.append(f"{UNIFIED_INVOCATION_BUDGET_MISSING}:role_missing")
        return tuple(dict.fromkeys(failures))
    max_calls_by_role = getattr(envelope, "max_calls_by_role", None) or {}
    max_total = int(getattr(envelope, "max_total_input_tokens", 0) or 0)
    max_input_by_role = getattr(envelope, "max_input_tokens_by_role", None) or {}
    if role_name not in max_calls_by_role or role_name not in max_input_by_role:
        failures.append(
            f"{UNIFIED_INVOCATION_BUDGET_MISSING}:role_budget:{role_name}"
        )
        return tuple(dict.fromkeys(failures))
    if max_total <= 0:
        failures.append(f"{UNIFIED_INVOCATION_BUDGET_MISSING}:run_total")
        return tuple(dict.fromkeys(failures))

    calls = int((state.get("call_count_by_role") or {}).get(role_name, 0) or 0)
    if not current_attempt_recorded:
        calls += 1
    max_calls = int(max_calls_by_role[role_name])
    if calls > max_calls:
        failures.append(
            f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:calls:{role_name}:"
            f"{calls}>{max_calls}"
        )

    committed = int(state.get("committed_input_tokens", 0) or 0)
    pending_by_role = state.get("pending_input_tokens_by_role") or {}
    current_reserve = max(0, int(current_reserved_input_tokens or 0))
    removable = (min(current_reserve, int(pending_by_role.get(role_name, 0) or 0))
                 if current_attempt_recorded else 0)
    request_tokens = max(0, int(request_input_tokens or 0))
    # A content retry reuses the primary invocation's reservation. Its current
    # marker must be removed and replaced by the measured retry cost; retaining
    # ``current_reserve`` here would charge the primary page twice.
    current_add = request_tokens if is_content_repair else max(
        current_reserve, request_tokens
    )
    candidate_total = committed - removable + current_add
    future = state.get("future_primary_reservations") or {}
    protected = {key: value for key, value in future.items()
                 if key != invocation_id or is_content_repair}
    candidate_total += sum(int(value["input_tokens"]) for value in protected.values())
    if is_content_repair:
        reserve = int((getattr(envelope, "retry_reserve_input_tokens_by_role", {}) or {}).get(role_name, 0))
        repair_spent = int((state.get("content_repair_spent_by_role") or {}).get(role_name, 0))
        pending_repairs = int(
            (state.get("pending_content_repair_input_tokens_by_role") or {}).get(
                role_name, 0
            )
        )
        # The current content-repair marker is included in the pending scan;
        # remove its primary-sized reservation before adding its measured
        # request. Other unsettled primary attempts stay outside this retry
        # reserve but remain protected by the global candidate below.
        prior_pending_repairs = max(
            0,
            pending_repairs - (current_reserve if current_attempt_recorded else 0),
        )
        needed = repair_spent + prior_pending_repairs + request_tokens
        if needed > reserve:
            failures.append(f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:retry_reserve:{role_name}:{needed}>{reserve}")
    if candidate_total > max_total:
        failures.append(
            f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:total_input_tokens:"
            f"{candidate_total}>{max_total}"
        )
    committed_role = int(
        (state.get("committed_input_tokens_by_role") or {}).get(role_name, 0)
        or 0
    )
    candidate_role = committed_role - removable + current_add
    candidate_role += sum(int(value["input_tokens"]) for value in protected.values() if value["role"] == role_name)
    max_role = int(max_input_by_role.get(role_name, 0) or 0)
    if max_role <= 0:
        failures.append(
            f"{UNIFIED_INVOCATION_BUDGET_MISSING}:role_input:{role_name}"
        )
    elif candidate_role > max_role:
        failures.append(
            f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:input_tokens:{role_name}:"
            f"{candidate_role}>{max_role}"
        )
    return tuple(dict.fromkeys(str(item) for item in failures if str(item)))


def last_started_attempt(ledger_root: Path, invocation_id: str) -> int:
    directory = invocation_dir(ledger_root, invocation_id)
    if not directory.is_dir():
        return 0
    highest = 0
    for path in directory.glob("attempt-*.started.json"):
        try:
            attempt = int(path.name.split(".")[0].split("-")[1])
        except (IndexError, ValueError):
            continue
        highest = max(highest, attempt)
    return highest


def last_completed_invocation_id(ledger_root: Path) -> str:
    """Return the most recently committed invocation, if one exists.

    The ledger directory names are intentionally sanitized and content
    addressed, so the original invocation ID must be read from a validated
    completed receipt rather than reconstructed from a path component.
    """

    candidates: list[tuple[float, str]] = []
    root = Path(ledger_root)
    if not root.is_dir():
        return ""
    for directory in root.iterdir():
        if not directory.is_dir():
            continue
        for path in directory.glob("attempt-*.completed.json"):
            try:
                import json

                receipt = ActualRequestReceiptV2.model_validate(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except Exception:
                continue
            candidates.append((float(receipt.finished_at_unix), receipt.invocation_id))
    if not candidates:
        return ""
    return max(candidates, key=lambda item: (item[0], item[1]))[1]


def _read_started_markers(
    ledger_root: Path,
    invocation_id: str,
) -> dict[int, InvocationAttemptStartedV1]:
    """Parse every durable started marker keyed by attempt number."""

    import json

    directory = invocation_dir(ledger_root, invocation_id)
    if not directory.is_dir():
        return {}
    markers: dict[int, InvocationAttemptStartedV1] = {}
    for path in sorted(directory.glob("attempt-*.started.json")):
        try:
            attempt = int(path.name.split(".")[0].split("-")[1])
            payload = json.loads(path.read_text(encoding="utf-8"))
            markers[attempt] = InvocationAttemptStartedV1.model_validate(payload)
        except Exception:
            # A corrupt marker cannot authorize anything; resume treats the
            # attempt as interrupted.
            continue
    return markers


LiteralResult = Literal["reuse", "invalidate", "execute"]


@dataclass
class ResumeDecision:
    invocation_id: str
    decision: LiteralResult = "execute"
    reason: str = ""
    reuse_receipt_digest: str = ""
    reuse_fragment_digests: tuple[str, ...] = ()
    next_attempt: int = 1


@dataclass
class ResumePlan:
    decisions: dict[str, ResumeDecision] = field(default_factory=dict)

    def reusable_invocation_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                invocation_id
                for invocation_id, decision in self.decisions.items()
                if decision.decision == "reuse"
            )
        )

    def invalidated_invocation_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                invocation_id
                for invocation_id, decision in self.decisions.items()
                if decision.decision == "invalidate"
            )
        )


def build_resume_plan(
    ledger_root: Path,
    plan: ConsumerInvocationPlanV1,
    *,
    archive_digest: str,
    workset_manifest_digest: str,
    model_identity_digest: str,
) -> ResumePlan:
    """Decide reuse/invalidate/execute per invocation in dependency order.

    An invocation is reused only when exactly one completed receipt exists
    with an accepted delivery whose page, envelope, model, archive, workset,
    plan, and fragment digests all match the current plan.  Any mismatch
    invalidates the invocation and its downstream dependency closure; other
    mechanisms' completed results stay valid.
    """

    plan_invocations = {item.invocation_id: item for item in plan.invocations}
    downstream: dict[str, set[str]] = {}
    for invocation in plan.invocations:
        for dependency in invocation.dependency_invocation_ids:
            downstream.setdefault(dependency, set()).add(invocation.invocation_id)

    decisions: dict[str, ResumeDecision] = {}

    def _invalidate_closure(root_ids: set[str]) -> None:
        pending = list(root_ids)
        while pending:
            invocation_id = pending.pop()
            if decisions.get(invocation_id, ResumeDecision(invocation_id)).decision == "invalidate":
                continue
            decisions[invocation_id] = ResumeDecision(
                invocation_id=invocation_id,
                decision="invalidate",
                reason=UNIFIED_RESUME_DIGEST_MISMATCH,
                next_attempt=max(
                    1,
                    last_started_attempt(ledger_root, invocation_id) + 1,
                ),
            )
            pending.extend(sorted(downstream.get(invocation_id, ())))

    for invocation in plan.invocations:
        if decisions.get(invocation.invocation_id) is not None and decisions[
            invocation.invocation_id
        ].decision == "invalidate":
            continue
        if invocation.invocation_id not in plan_invocations:
            decisions[invocation.invocation_id] = ResumeDecision(
                invocation_id=invocation.invocation_id,
                decision="invalidate",
                reason=UNIFIED_UNPLANNED_ACTUAL_REQUEST,
            )
            continue
        receipts = read_completed_receipts(ledger_root, invocation.invocation_id)
        started_markers = _read_started_markers(ledger_root, invocation.invocation_id)

        def _envelope_matches(receipt: ActualRequestReceiptV2) -> bool:
            if receipt.content_repair_attempt:
                # A bounded content retry may carry a repair-specific request
                # envelope.  Its exact digest is bound by the attempt-started
                # marker published immediately before that retry; accepting
                # the primary plan digest here would silently make the repair
                # payload unverifiable.
                marker = started_markers.get(receipt.attempt)
                return bool(
                    marker
                    and marker.expected_request_envelope_digest
                    == receipt.actual_request_envelope_digest
                    and marker.expected_technical_bytes_digest
                    == receipt.actual_technical_bytes_digest
                    and marker.plan_digest == plan.content_digest
                )
            if invocation.expected_request_envelope_digest:
                return (
                    receipt.actual_request_envelope_digest
                    == invocation.expected_request_envelope_digest
                )
            # The plan binds the envelope digest at execution time; the
            # durable started marker published before the call is then the
            # expectation the receipt must match.
            marker = started_markers.get(receipt.attempt)
            return bool(
                marker
                and marker.expected_request_envelope_digest
                == receipt.actual_request_envelope_digest
                and marker.expected_technical_bytes_digest
                == receipt.actual_technical_bytes_digest
                and marker.plan_digest == plan.content_digest
            )

        def _fragments_match(receipt: ActualRequestReceiptV2) -> bool:
            """Validate every fragment named by the receipt for its attempt."""

            if not receipt.fragment_digests:
                # A receipt with successful tasks must name their durable
                # fragments.  A failed delivery can have none; non-formula
                # consumers may legitimately publish no output fragment.
                return not receipt.succeeded_task_ids
            directory = invocation_dir(ledger_root, invocation.invocation_id)
            expected = set(receipt.fragment_digests)
            found: set[str] = set()
            import json

            pattern = f"attempt-{receipt.attempt:04d}.*-fragment*.json"
            for path in sorted(directory.glob(pattern)):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if not isinstance(payload, Mapping):
                    continue
                if payload.get("invocation_id") != invocation.invocation_id:
                    continue
                try:
                    payload_attempt = int(payload.get("attempt", -1))
                except (TypeError, ValueError):
                    continue
                if payload_attempt != receipt.attempt:
                    continue
                digest = _fragment_payload_digest(payload)
                if digest in expected:
                    found.add(digest)
            return found == expected

        accepted = [
            receipt for receipt in receipts
            if receipt.delivery_status == "accepted"
            and receipt.invocation_id == invocation.invocation_id
            and receipt.consumer_role == invocation.role
            and receipt.phase == invocation.phase
            and receipt.workset_id == invocation.workset_id
            and receipt.page_id == invocation.page_id
            and set(receipt.task_ids) == set(invocation.task_ids)
            and receipt.is_repair == invocation.is_repair
            and receipt.actual_technical_bytes_digest
            == invocation.expected_technical_bytes_digest
            and _envelope_matches(receipt)
            and receipt.model_identity_digest == model_identity_digest
            and receipt.upstream_archive_digest == archive_digest
            and receipt.upstream_workset_manifest_digest == workset_manifest_digest
            and receipt.upstream_plan_digest == plan.content_digest
            and _fragments_match(receipt)
        ]
        accepted_delivery_count = sum(
            1 for receipt in receipts
            if receipt.delivery_status == "accepted"
            and not receipt.content_repair_attempt
        )
        if accepted_delivery_count > 1:
            _invalidate_closure({invocation.invocation_id})
            continue
        accepted_primary = tuple(
            receipt for receipt in accepted if not receipt.content_repair_attempt
        )
        if len(accepted_primary) == 1:
            # Prefer the latest successful Writer content repair when one
            # exists.  It is the same page/envelope delivery with a newer
            # response, not a second immutable page delivery.
            successful = tuple(
                item for item in accepted if (
                    bool((read_writer_content_acceptance(ledger_root, item) or {}).get("accepted"))
                    if item.consumer_role == "writer" else item.task_status == "complete"
                )
            )
            if not successful:
                decisions[invocation.invocation_id] = ResumeDecision(
                    invocation_id=invocation.invocation_id,
                    decision="execute",
                    reason="accepted_delivery_task_incomplete",
                    next_attempt=max(
                        1,
                        last_started_attempt(ledger_root, invocation.invocation_id)
                        + 1,
                    ),
                )
                continue
            receipt = max(
                successful,
                key=lambda item: (item.attempt, item.content_digest),
            )
            decisions[invocation.invocation_id] = ResumeDecision(
                invocation_id=invocation.invocation_id,
                decision="reuse",
                reason="completed_receipt_digests_match",
                reuse_receipt_digest=receipt.content_digest,
                reuse_fragment_digests=tuple(receipt.fragment_digests),
                next_attempt=receipt.attempt + 1,
            )
            continue
        if len(accepted_primary) > 1:
            _invalidate_closure({invocation.invocation_id})
            continue
        if accepted_delivery_count:
            _invalidate_closure({invocation.invocation_id})
            continue
        next_attempt = max(1, last_started_attempt(ledger_root, invocation.invocation_id) + 1)
        decisions[invocation.invocation_id] = ResumeDecision(
            invocation_id=invocation.invocation_id,
            decision="execute",
            reason="no_matching_completed_receipt",
            next_attempt=next_attempt,
        )
    return ResumePlan(decisions=decisions)


def write_run_terminal_event(
    ledger_root: Path,
    *,
    run_digest: str,
    terminal_reason: str,
    terminal_stage: str,
    last_completed_invocation_id: str = "",
    extra: Mapping[str, Any] | None = None,
    filename: str = "run_terminal_event.json",
) -> Path:
    """Persist the run terminal event (normal end, stop, signal, or failure)."""

    import json
    import time

    payload = {
        "schema_version": _LEDGER_SCHEMA_VERSION,
        "event_kind": "run_terminal",
        "run_digest": str(run_digest),
        "terminal_reason": str(terminal_reason),
        "terminal_stage": str(terminal_stage),
        "last_completed_invocation_id": str(last_completed_invocation_id),
        "recorded_at_unix": time.time(),
        "extra": dict(extra or {}),
    }
    safe_filename = Path(str(filename or "run_terminal_event.json")).name
    if not safe_filename.endswith(".json"):
        safe_filename += ".json"
    path = Path(ledger_root) / safe_filename
    _atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return path


def read_run_terminal_event(ledger_root: Path) -> dict[str, Any] | None:
    import json

    path = Path(ledger_root) / "run_terminal_event.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def rebuild_aggregate_fragments(
    ledger_root: Path,
    plan: ConsumerInvocationPlanV1,
    *,
    role: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """Deterministically rebuild successful fragments from completed receipts.

    Aggregate artifacts are derived views; the receipts remain the only
    resume authority.
    """

    import json

    fragments: list[dict[str, Any]] = []
    for invocation in plan.invocations:
        if role is not None and invocation.role != role:
            continue
        receipts = read_completed_receipts(ledger_root, invocation.invocation_id)
        accepted = [
            receipt for receipt in receipts
            if receipt.delivery_status == "accepted"
        ]
        if not accepted:
            continue
        directory = invocation_dir(ledger_root, invocation.invocation_id)
        for receipt in accepted:
            expected_digests = set(receipt.fragment_digests)
            if not expected_digests:
                continue
            pattern = f"attempt-{receipt.attempt:04d}.*-fragment*.json"
            for path in sorted(directory.glob(pattern)):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if not isinstance(payload, Mapping):
                    continue
                if payload.get("invocation_id") != invocation.invocation_id:
                    continue
                try:
                    payload_attempt = int(payload.get("attempt", -1))
                except (TypeError, ValueError):
                    continue
                if payload_attempt != receipt.attempt:
                    continue
                fragment_digest = _fragment_payload_digest(payload)
                if fragment_digest not in expected_digests:
                    continue
                fragments.append({
                    "invocation_id": invocation.invocation_id,
                    "attempt": receipt.attempt,
                    "fragment": payload.get("fragment", {}),
                    "fragment_digest": fragment_digest,
                    "receipt_digest": receipt.content_digest,
                })
    return tuple(fragments)


__all__ = [
    "invocation_dir",
    "publish_attempt_started",
    "publish_attempt_completed",
    "publish_package_fragment",
    "publish_output_fragment",
    "read_completed_receipts",
    "read_all_completed_receipts",
    "register_invocation_plan",
    "last_started_attempt",
    "read_run_budget_state",
    "check_run_budget_before_send",
    "last_completed_invocation_id",
    "ResumeDecision",
    "ResumePlan",
    "build_resume_plan",
    "write_run_terminal_event",
    "read_run_terminal_event",
    "rebuild_aggregate_fragments",
]
