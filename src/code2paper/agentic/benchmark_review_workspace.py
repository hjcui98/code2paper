from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from code2paper.agentic.benchmark_observation import (
    BenchmarkRunReviewV2,
    extract_benchmark_observation_v2,
    load_benchmark_run_review_v2,
)
from code2paper.agentic.benchmark_protocol import BenchmarkProtocolV2, validate_protocol_observations_v2
from code2paper.agentic.benchmark_v2 import BenchmarkDatasetV2, BenchmarkObservationV2
from code2paper.agentic.tool_runtime import atomic_write_json


_IMMUTABLE_REVIEW_FIELDS = (
    "schema_version",
    "case_id",
    "variant",
    "repeat_index",
    "intent_id",
    "scope",
    "run_summary_path",
    "run_summary_digest",
    "protocol_spec_digest",
    "repo_snapshot_id",
    "model_id",
    "capability_profile_digest",
)


def materialize_review_workspace(queue_path: str | Path, out_root: str | Path) -> Path:
    """Materialize one human-editable review file per frozen queue entry.

    Existing workspaces are never overwritten because review files contain human work.
    """

    source = Path(queue_path).expanduser().resolve()
    root = Path(out_root).expanduser().resolve()
    queue = _load_json(source)
    entries = _validated_queue_entries(queue)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"review workspace is not empty:{root}")
    reviews_root = root / "reviews"
    contexts_root = root / "contexts"
    reviews_root.mkdir(parents=True, exist_ok=True)
    contexts_root.mkdir(parents=True, exist_ok=True)
    manifest_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        identity = _identity(entry)
        stem = f"{index:03d}-{_identity_slug(identity)}"
        review_path = reviews_root / f"{stem}.json"
        context_path = contexts_root / f"{stem}.md"
        template = entry["review_template"]
        atomic_write_json(review_path, template)
        context_path.write_text(_review_context(entry), encoding="utf-8")
        manifest_entries.append({
            "identity": list(identity),
            "review_path": str(review_path.relative_to(root)),
            "context_path": str(context_path.relative_to(root)),
            "context_digest": _digest_file(context_path),
            "template_digest": _digest_json(template),
        })
    manifest = {
        "schema_version": "code2paper-agentic-review-workspace/v1",
        "queue_path": str(source),
        "queue_digest": _digest_file(source),
        "protocol_commit": str(queue.get("protocol_commit") or ""),
        "gold_digest": str(queue.get("gold_digest") or ""),
        "expected_reviews": len(entries),
        "status": "human_review_required",
        "instructions": [
            "Edit only files under reviews/; contexts/ are read-only reviewer aids.",
            "Replace reviewer and reviewed_at placeholders with an attributable name and timezone-aware ISO-8601 timestamp.",
            "Do not change run, protocol, snapshot, model, claim-text, validator-verdict, or mutation-artifact bindings.",
            "Every claim requires an explicit direct_evidence_support decision based on the frozen code spans.",
            "The validator never supplies semantic adjudications and cannot replace the named reviewer.",
        ],
        "entries": manifest_entries,
    }
    manifest_path = root / "review_workspace_manifest.json"
    atomic_write_json(manifest_path, manifest)
    return manifest_path


def validate_review_workspace(
    queue_path: str | Path,
    workspace_root: str | Path,
    dataset: BenchmarkDatasetV2,
    protocol: BenchmarkProtocolV2,
) -> tuple[dict[str, Any], list[BenchmarkObservationV2]]:
    """Validate exact review coverage and extract observations only from clean reviews."""

    queue_source = Path(queue_path).expanduser().resolve()
    root = Path(workspace_root).expanduser().resolve()
    manifest_path = root / "review_workspace_manifest.json"
    global_failures: list[str] = []
    pending: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    observations: list[BenchmarkObservationV2] = []
    validated_reviews: list[dict[str, Any]] = []
    try:
        queue = _load_json(queue_source)
        queue_entries = _validated_queue_entries(queue)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _report("failed", [], [], [f"queue_invalid:{exc}"], [], []), []
    try:
        manifest = _load_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return _report("failed", [], [], [f"manifest_invalid:{exc}"], [], []), []
    if manifest.get("schema_version") != "code2paper-agentic-review-workspace/v1":
        global_failures.append("workspace_manifest_schema_mismatch")
    if manifest.get("queue_digest") != _digest_file(queue_source):
        global_failures.append("review_queue_digest_drift")
    if manifest.get("protocol_commit") != protocol.workspace_commit:
        global_failures.append("workspace_protocol_commit_mismatch")
    if queue.get("gold_digest") != protocol.gold_digest:
        global_failures.append("review_queue_gold_digest_mismatch")
    if manifest.get("gold_digest") != protocol.gold_digest:
        global_failures.append("workspace_gold_digest_mismatch")
    expected = {_identity(entry): entry for entry in queue_entries}
    protocol_identities = {
        (spec.case_id, spec.variant, spec.intent_id, spec.repeat_index)
        for spec in protocol.specs
    }
    if set(expected) != protocol_identities:
        global_failures.append("queue_protocol_identity_mismatch")
    if manifest.get("expected_reviews") != len(expected):
        global_failures.append("workspace_expected_review_count_mismatch")
    manifest_entries = manifest.get("entries") if isinstance(manifest.get("entries"), list) else []
    manifest_identities: list[tuple[str, str, str, int]] = []
    for item in manifest_entries:
        if not isinstance(item, dict):
            continue
        try:
            manifest_identities.append(_tuple_identity(item.get("identity")))
        except (TypeError, ValueError):
            global_failures.append("workspace_manifest_contains_invalid_identity")
    if len(manifest_identities) != len(set(manifest_identities)):
        global_failures.append("workspace_contains_duplicate_review_identity")
    if set(manifest_identities) != set(expected):
        global_failures.append("workspace_review_identity_coverage_mismatch")
    case_by_id = {case.case_id: case for case in dataset.cases}
    for item in manifest_entries:
        if not isinstance(item, dict):
            invalid.append({"identity": [], "failures": ["manifest_entry_not_object"]})
            continue
        try:
            identity = _tuple_identity(item.get("identity"))
        except (TypeError, ValueError):
            invalid.append({"identity": [], "failures": ["invalid_review_identity"]})
            continue
        queue_entry = expected.get(identity)
        if queue_entry is None:
            invalid.append({"identity": list(identity), "failures": ["review_identity_not_in_queue"]})
            continue
        failures: list[str] = []
        try:
            context_path = _contained_path(root, item.get("context_path"), "contexts")
        except ValueError as exc:
            failures.append(str(exc).replace("review_path", "context_path"))
        else:
            if not context_path.is_file():
                failures.append("review_context_file_missing")
            else:
                expected_context_digest = _digest_text(_review_context(queue_entry))
                if item.get("context_digest") != expected_context_digest:
                    failures.append("workspace_context_digest_mismatch")
                if _digest_file(context_path) != expected_context_digest:
                    failures.append("review_context_content_drift")
        if item.get("template_digest") != _digest_json(queue_entry["review_template"]):
            failures.append("workspace_template_digest_mismatch")
        try:
            review_path = _contained_path(root, item.get("review_path"), "reviews")
        except ValueError as exc:
            invalid.append({"identity": list(identity), "failures": [str(exc)]})
            continue
        if not review_path.is_file():
            invalid.append({"identity": list(identity), "failures": ["review_file_missing"]})
            continue
        try:
            raw_review = _load_json(review_path)
        except (OSError, json.JSONDecodeError) as exc:
            invalid.append({"identity": list(identity), "failures": [f"review_json_invalid:{exc}"]})
            continue
        failures.extend(_immutable_binding_failures(queue_entry["review_template"], raw_review))
        if failures:
            invalid.append({"identity": list(identity), "review_path": str(review_path), "failures": failures})
            continue
        if _has_human_placeholders(raw_review):
            pending.append({"identity": list(identity), "review_path": str(review_path)})
            continue
        review: BenchmarkRunReviewV2 | None = None
        if not failures:
            try:
                review = load_benchmark_run_review_v2(review_path)
            except (OSError, ValueError) as exc:
                failures.append(f"review_schema_invalid:{exc}")
        if review is not None and (
            review.case_id,
            review.variant,
            review.intent_id,
            review.repeat_index,
        ) != identity:
            failures.append("review_identity_contradicts_manifest")
        if review is not None and not failures:
            case = case_by_id.get(review.case_id)
            if case is None:
                failures.append("review_case_missing_from_gold")
            else:
                try:
                    observations.append(extract_benchmark_observation_v2(case, review))
                except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    failures.append(f"review_artifact_validation_failed:{exc}")
        if failures:
            invalid.append({"identity": list(identity), "review_path": str(review_path), "failures": failures})
            continue
        validated_reviews.append({
            "identity": list(identity),
            "review_path": str(review_path),
            "review_digest": _digest_file(review_path),
            "reviewer": review.reviewer if review is not None else "",
            "reviewed_at": review.reviewed_at if review is not None else "",
        })
    if not global_failures and not pending and not invalid:
        global_failures.extend(validate_protocol_observations_v2(protocol, observations))
    status = "passed"
    if pending and not invalid and not global_failures:
        status = "pending_human_review"
    elif invalid or global_failures:
        status = "failed"
    if status != "passed":
        observations = []
    report = _report(status, pending, invalid, global_failures, validated_reviews, manifest_entries)
    report.update({
        "queue_path": str(queue_source),
        "queue_digest": _digest_file(queue_source),
        "workspace_manifest_path": str(manifest_path),
        "workspace_manifest_digest": _digest_file(manifest_path),
        "protocol_commit": protocol.workspace_commit,
        "expected_reviews": len(expected),
    })
    return report, observations


def _validated_queue_entries(queue: dict[str, Any]) -> list[dict[str, Any]]:
    if queue.get("schema_version") != "2.0":
        raise ValueError("review queue schema must be 2.0")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(queue.get("gold_digest") or "")):
        raise ValueError("review queue requires a frozen gold dataset digest")
    entries = queue.get("entries")
    if not isinstance(entries, list) or queue.get("entry_count") != len(entries):
        raise ValueError("review queue entry count mismatch")
    identities: list[tuple[str, str, str, int]] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("status") != "human_review_required":
            raise ValueError("every queue entry must be ready for human review")
        if not isinstance(entry.get("review_template"), dict):
            raise ValueError("review queue entry is missing its template")
        gold_claims = entry.get("gold_claims")
        gold_spans = entry.get("gold_evidence_spans")
        if not isinstance(gold_claims, list) or not isinstance(gold_spans, list):
            raise ValueError("review queue entry requires gold claims and code evidence spans")
        if not str(entry.get("gold_repo_root") or "").strip():
            raise ValueError("review queue entry requires the frozen gold repository root")
        span_ids = [
            str(item.get("evidence_id") or "") for item in gold_spans if isinstance(item, dict)
        ]
        if len(span_ids) != len(gold_spans) or any(not item for item in span_ids):
            raise ValueError("gold code evidence spans require evidence ids")
        if len(span_ids) != len(set(span_ids)):
            raise ValueError("gold code evidence spans contain duplicate evidence ids")
        known_spans = set(span_ids)
        for claim in gold_claims:
            if not isinstance(claim, dict):
                raise ValueError("gold claim inventory must contain objects")
            direct_ids = claim.get("direct_evidence_ids")
            if not isinstance(direct_ids, list) or not direct_ids or not set(direct_ids).issubset(known_spans):
                raise ValueError("gold claim references missing code evidence spans")
        identity = _identity(entry)
        template = entry["review_template"]
        template_identity = (
            str(template.get("case_id") or ""),
            str(template.get("variant") or ""),
            str(template.get("intent_id") or ""),
            int(template.get("repeat_index") or 0),
        )
        if identity != template_identity:
            raise ValueError("review queue identity contradicts template")
        identities.append(identity)
    if len(identities) != len(set(identities)):
        raise ValueError("review queue contains duplicate identities")
    return entries


def _immutable_binding_failures(template: dict[str, Any], review: dict[str, Any]) -> list[str]:
    failures = [
        f"immutable_review_field_changed:{field}"
        for field in _IMMUTABLE_REVIEW_FIELDS
        if review.get(field) != template.get(field)
    ]
    if template.get("variant") != "fixed_legacy":
        expected_claims = [
            (item.get("atomic_claim_id"), item.get("text"), item.get("verdict"))
            for item in template.get("claims", [])
        ]
        actual_claims = [
            (item.get("atomic_claim_id"), item.get("text"), item.get("verdict"))
            for item in review.get("claims", [])
            if isinstance(item, dict)
        ]
        if actual_claims != expected_claims:
            failures.append("agentic_claim_inventory_or_validator_verdict_changed")
        immutable_figure_fields = (
            "element_id", "element_kind", "label", "scene_element_digest", "scene_relation_id",
        )
        expected_figures = [
            tuple(item.get(field) for field in immutable_figure_fields)
            for item in template.get("figures", [])
            if isinstance(item, dict)
        ]
        actual_figures = [
            tuple(item.get(field) for field in immutable_figure_fields)
            for item in review.get("figures", [])
            if isinstance(item, dict)
        ]
        if actual_figures != expected_figures:
            failures.append("agentic_figure_inventory_or_scene_binding_changed")
    expected_trials = sorted(
        (
            str(item.get("mutation_id") or ""),
            str(item.get("trial_artifact_path") or ""),
            str(item.get("trial_artifact_digest") or ""),
        )
        for item in template.get("mutation_trials", [])
        if isinstance(item, dict)
    )
    actual_trials = sorted(
        (
            str(item.get("mutation_id") or ""),
            str(item.get("trial_artifact_path") or ""),
            str(item.get("trial_artifact_digest") or ""),
        )
        for item in review.get("mutation_trials", [])
        if isinstance(item, dict)
    )
    if actual_trials != expected_trials:
        failures.append("mutation_trial_artifact_binding_changed")
    return failures


def _review_context(entry: dict[str, Any]) -> str:
    template = entry["review_template"]
    lines = [
        f"# Review: {' / '.join(str(item or 'default') for item in _identity(entry))}",
        "",
        "This file is reviewer context only. Record judgments in the matching JSON under `reviews/`.",
        "The paper reference is not evidence and is intentionally absent from this workspace.",
        "",
        "## Immutable run binding",
        "",
        f"- Run summary: `{template.get('run_summary_path', '')}`",
        f"- Run summary digest: `{template.get('run_summary_digest', '')}`",
        f"- Protocol spec digest: `{template.get('protocol_spec_digest', '')}`",
        f"- Repository snapshot: `{template.get('repo_snapshot_id', '')}`",
        "",
        "## Review artifacts",
        "",
        *_review_artifact_lines(template),
        "",
        "## Human review instructions",
        "",
    ]
    lines.extend(f"- {instruction}" for instruction in entry.get("review_instructions", []))
    lines.extend(["", "## Gold claims grounded in code", "", "```json"])
    lines.append(json.dumps(entry.get("gold_claims", []), ensure_ascii=False, indent=2))
    lines.extend(["```", "", "## Gold code evidence spans", "", "```json"])
    lines.append(json.dumps(entry.get("gold_evidence_spans", []), ensure_ascii=False, indent=2))
    lines.extend(["```", "", f"- Frozen repository root: `{entry.get('gold_repo_root', '')}`"])
    lines.extend(["", "## Gold figure relations grounded in code", "", "```json"])
    lines.append(json.dumps(entry.get("gold_figure_relations", []), ensure_ascii=False, indent=2))
    lines.extend(["```", "", "## Frozen visible figure inventory requiring human decisions", "", "```json"])
    lines.append(json.dumps(template.get("figures", []), ensure_ascii=False, indent=2))
    lines.extend(["```", ""])
    legacy_path = str(entry.get("legacy_v2_audit_path") or "")
    if legacy_path:
        lines.extend([
            "## Legacy V2 audit", "",
            f"- Path: `{legacy_path}`",
            f"- Digest: `{entry.get('legacy_v2_audit_digest', '')}`",
            "",
        ])
    return "\n".join(lines)


def _review_artifact_lines(template: dict[str, Any]) -> list[str]:
    summary_path = Path(str(template.get("run_summary_path") or ""))
    try:
        summary = _load_json(summary_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return ["- Run artifacts are unavailable; validation will fail until the frozen run is restored."]
    selected_agentic = (
        "evidence_snapshot_v2",
        "evidence",
        "evidence_index",
        "final_text_claims",
        "text_clean_md",
        "final_text_trace",
        "method_overview_svg",
        "text_evidence_validation",
        "final_invariant_audit",
        "package_manifest",
        "agentic_run_evaluation_report",
    )
    lines: list[str] = []
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), dict) else {}
    for key in selected_agentic:
        record = artifacts.get(key)
        if not isinstance(record, dict) or not record.get("path"):
            continue
        lines.append(f"- {key}: `{record['path']}` (`{record.get('hash', '')}`)")
    if lines:
        return lines
    outputs = summary.get("outputs") if isinstance(summary.get("outputs"), dict) else {}
    for key in ("method_draft_md", "method_draft_tex", "method_overview_svg", "method_fidelity_report"):
        path = str(outputs.get(key) or "")
        if path:
            lines.append(f"- {key}: `{path}`")
    return lines or ["- No reviewable text or figure artifact is recorded for this run."]


def _report(status, pending, invalid, failures, validated, manifest_entries) -> dict[str, Any]:
    return {
        "schema_version": "code2paper-agentic-review-workspace-validation/v1",
        "status": status,
        "hard_gate_passed": status == "passed",
        "manifest_entry_count": len(manifest_entries),
        "validated_review_count": len(validated),
        "pending_review_count": len(pending),
        "invalid_review_count": len(invalid),
        "global_failures": failures,
        "pending_reviews": pending,
        "invalid_reviews": invalid,
        "validated_reviews": validated,
        "observations_emitted": status == "passed",
    }


def _identity(entry: dict[str, Any]) -> tuple[str, str, str, int]:
    return _tuple_identity(entry.get("identity"))


def _tuple_identity(value: object) -> tuple[str, str, str, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("invalid review identity")
    return str(value[0]), str(value[1]), str(value[2]), int(value[3])


def _identity_slug(identity: tuple[str, str, str, int]) -> str:
    raw = "-".join((identity[0], identity[1], identity[2] or "default", f"r{identity[3]}"))
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", raw).strip("-")


def _contained_path(root: Path, relative: object, required_parent: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("review_path_missing")
    path = (root / relative).resolve()
    allowed = (root / required_parent).resolve()
    try:
        path.relative_to(allowed)
    except ValueError as exc:
        raise ValueError("review_path_escapes_workspace") from exc
    return path


def _has_human_placeholders(review: dict[str, Any]) -> bool:
    return (
        str(review.get("reviewer") or "").strip() in {"", "__REQUIRED_NAMED_HUMAN__"}
        or str(review.get("reviewed_at") or "").strip() in {"", "__REQUIRED_ISO8601__"}
    )


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required:{path}")
    return value


def _digest_json(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
