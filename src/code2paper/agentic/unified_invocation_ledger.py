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
            receipts.append(ActualRequestReceiptV2.model_validate(payload))
        except Exception:
            # A half-written or corrupt receipt is not success evidence; it
            # simply cannot authorize resume reuse.
            continue
    return tuple(receipts)


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
            1 for receipt in receipts if receipt.delivery_status == "accepted"
        )
        if accepted_delivery_count > 1:
            _invalidate_closure({invocation.invocation_id})
            continue
        if len(accepted) == 1:
            receipt = accepted[0]
            decisions[invocation.invocation_id] = ResumeDecision(
                invocation_id=invocation.invocation_id,
                decision="reuse",
                reason="completed_receipt_digests_match",
                reuse_receipt_digest=receipt.content_digest,
                reuse_fragment_digests=tuple(receipt.fragment_digests),
                next_attempt=receipt.attempt + 1,
            )
            continue
        if len(accepted) > 1:
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
    path = Path(ledger_root) / "run_terminal_event.json"
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
    "last_started_attempt",
    "last_completed_invocation_id",
    "ResumeDecision",
    "ResumePlan",
    "build_resume_plan",
    "write_run_terminal_event",
    "read_run_terminal_event",
    "rebuild_aggregate_fragments",
]
