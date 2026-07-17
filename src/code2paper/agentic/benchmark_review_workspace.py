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
    "legacy_v2_audit_path",
    "legacy_v2_audit_digest",
)


def review_workspace_progress(workspace_root: str | Path) -> dict[str, Any]:
    """Report human-decision progress without interpreting any decision."""

    root = Path(workspace_root).expanduser().resolve()
    manifest, _queue, entries = _load_editable_workspace(root)
    totals = {
        "reviews": 0,
        "signed_reviews": 0,
        "claims": 0,
        "claims_pending": 0,
        "figures": 0,
        "figures_pending": 0,
        "run_decisions_pending": 0,
    }
    review_progress: list[dict[str, Any]] = []
    for item in manifest["entries"]:
        identity = _tuple_identity(item.get("identity"))
        entry = entries[identity]
        path = _contained_path(root, item.get("review_path"), "reviews")
        review = _load_json(path)
        failures = _immutable_binding_failures(entry["review_template"], review)
        if failures:
            raise ValueError(f"review immutable binding drift:{path}:{','.join(failures)}")
        claims = review.get("claims") if isinstance(review.get("claims"), list) else []
        figures = review.get("figures") if isinstance(review.get("figures"), list) else []
        claim_pending = sum(_claim_decision_pending(value) for value in claims)
        figure_pending = sum(_figure_decision_pending(value) for value in figures)
        run_pending = _run_decision_pending(review)
        signed = not _identity_pending(review)
        totals["reviews"] += 1
        totals["signed_reviews"] += int(signed)
        totals["claims"] += len(claims)
        totals["claims_pending"] += claim_pending
        totals["figures"] += len(figures)
        totals["figures_pending"] += figure_pending
        totals["run_decisions_pending"] += int(run_pending)
        review_progress.append({
            "identity": list(identity),
            "review_path": str(path),
            "signed": signed,
            "claims": len(claims),
            "claims_pending": claim_pending,
            "figures": len(figures),
            "figures_pending": figure_pending,
            "run_decisions_pending": run_pending,
            "ready_to_sign": not claim_pending and not figure_pending and not run_pending,
        })
    return {
        "schema_version": "code2paper-agentic-review-workspace-progress/v1",
        "workspace_manifest": str(root / "review_workspace_manifest.json"),
        "queue_path": str(Path(manifest["queue_path"]).resolve()),
        **totals,
        "reviews_pending": totals["reviews"] - totals["signed_reviews"],
        "review_progress": review_progress,
    }


def record_claim_adjudication(
    workspace_root: str | Path,
    review_selector: str,
    claim_id: str,
    *,
    semantic_match: str,
    gold_claim_id: str,
    mutation_match: str,
    mutation_id: str,
    direct_evidence_support: bool,
    qualifiers_preserved: bool,
) -> Path:
    root, entry, path, review = _editable_review(workspace_root, review_selector)
    del root
    _require_unsigned(review)
    gold_ids = {str(item.get("claim_id") or "") for item in entry.get("gold_claims", [])}
    mutation_ids = {
        str(item.get("mutation_id") or "")
        for item in entry["review_template"].get("mutation_trials", [])
        if isinstance(item, dict)
    }
    _validate_match("semantic", semantic_match, gold_claim_id, gold_ids)
    _validate_match("mutation", mutation_match, mutation_id, mutation_ids)
    claims = review.get("claims") if isinstance(review.get("claims"), list) else []
    matches = [item for item in claims if isinstance(item, dict) and item.get("atomic_claim_id") == claim_id]
    if len(matches) != 1:
        raise ValueError(f"claim selector must match exactly one frozen claim:{claim_id}")
    matches[0].update({
        "semantic_match": semantic_match,
        "gold_claim_id": gold_claim_id,
        "mutation_match": mutation_match,
        "mutation_id": mutation_id,
        "direct_evidence_support": direct_evidence_support,
        "qualifiers_preserved": qualifiers_preserved,
    })
    return atomic_write_json(path, review)


def record_figure_adjudication(
    workspace_root: str | Path,
    review_selector: str,
    element_id: str,
    *,
    gold_claim_id: str,
    relation_id: str,
    semantically_supported: bool,
    direct_relation_evidence: bool,
    rendered_drift: bool,
) -> Path:
    root, entry, path, review = _editable_review(workspace_root, review_selector)
    del root
    _require_unsigned(review)
    known_claims = {str(item.get("claim_id") or "") for item in entry.get("gold_claims", [])}
    known_relations = {str(item.get("relation_id") or "") for item in entry.get("gold_figure_relations", [])}
    if gold_claim_id and gold_claim_id not in known_claims:
        raise ValueError(f"unknown gold claim id:{gold_claim_id}")
    if relation_id and relation_id not in known_relations:
        raise ValueError(f"unknown gold relation id:{relation_id}")
    figures = review.get("figures") if isinstance(review.get("figures"), list) else []
    matches = [item for item in figures if isinstance(item, dict) and item.get("element_id") == element_id]
    if len(matches) != 1:
        raise ValueError(f"figure selector must match exactly one frozen element:{element_id}")
    if matches[0].get("element_kind") == "edge" and direct_relation_evidence and not relation_id:
        raise ValueError("direct edge evidence requires a gold relation id")
    if matches[0].get("element_kind") != "edge" and direct_relation_evidence:
        raise ValueError("direct relation evidence is only valid for edge elements")
    matches[0].update({
        "gold_claim_id": gold_claim_id,
        "relation_id": relation_id,
        "semantically_supported": semantically_supported,
        "direct_relation_evidence": direct_relation_evidence,
        "rendered_drift": rendered_drift,
    })
    return atomic_write_json(path, review)


def record_run_adjudication(
    workspace_root: str | Path,
    review_selector: str,
    *,
    usable_completion: bool,
    intent_fields_reviewed: bool,
    blocked_reason_review: str = "",
    blocked_reason_classification: str = "",
) -> Path:
    root, entry, path, review = _editable_review(workspace_root, review_selector)
    del root, entry
    _require_unsigned(review)
    allowed = {"", "correct_repairable", "correct_terminal", "false_block"}
    if blocked_reason_classification not in allowed:
        raise ValueError(f"invalid blocked reason classification:{blocked_reason_classification}")
    if bool(blocked_reason_review.strip()) != bool(blocked_reason_classification):
        raise ValueError("blocked review rationale and classification must be supplied together")
    _validate_run_decision_against_frozen_summary(
        review,
        usable_completion=usable_completion,
        intent_fields_reviewed=intent_fields_reviewed,
        blocked_reason_review=blocked_reason_review,
        blocked_reason_classification=blocked_reason_classification,
    )
    review.update({
        "usable_completion": usable_completion,
        "intent_fields_reviewed": intent_fields_reviewed,
        "blocked_reason_review": blocked_reason_review.strip(),
        "blocked_reason_classification": blocked_reason_classification or None,
    })
    return atomic_write_json(path, review)


def sign_review(
    workspace_root: str | Path,
    review_selector: str,
    *,
    reviewer: str,
    reviewed_at: str,
) -> Path:
    root, entry, path, review = _editable_review(workspace_root, review_selector)
    del root
    _require_unsigned(review)
    candidate = dict(review)
    candidate.update({"reviewer": reviewer.strip(), "reviewed_at": reviewed_at.strip()})
    if _has_human_placeholders(candidate):
        raise ValueError("review decisions are incomplete; refusing named-human signature")
    _validate_decisions_for_signature(entry, candidate)
    BenchmarkRunReviewV2.model_validate(candidate)
    return atomic_write_json(path, candidate)


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
            "Every claim requires explicit semantic_match, mutation_match, and qualifier decisions; empty IDs are not decisions.",
            "usable_completion and intent_fields_reviewed (when applicable) must be explicit.",
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
    expected_claims = [
        (item.get("atomic_claim_id"), item.get("text"), item.get("verdict"), item.get("high_risk"))
        for item in template.get("claims", [])
        if isinstance(item, dict)
    ]
    actual_claims = [
        (item.get("atomic_claim_id"), item.get("text"), item.get("verdict"), item.get("high_risk"))
        for item in review.get("claims", [])
        if isinstance(item, dict)
    ]
    if actual_claims != expected_claims:
        failures.append("claim_inventory_or_validator_verdict_changed")
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
        failures.append("figure_inventory_or_scene_binding_changed")
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


def _load_editable_workspace(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[str, str, str, int], dict[str, Any]]]:
    manifest_path = root / "review_workspace_manifest.json"
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != "code2paper-agentic-review-workspace/v1":
        raise ValueError("workspace manifest schema mismatch")
    queue_path = Path(str(manifest.get("queue_path") or "")).expanduser().resolve()
    if not queue_path.is_file():
        raise ValueError(f"workspace queue is unavailable:{queue_path}")
    if manifest.get("queue_digest") != _digest_file(queue_path):
        raise ValueError("review queue digest drift")
    queue = _load_json(queue_path)
    entries_list = _validated_queue_entries(queue)
    entries = {_identity(item): item for item in entries_list}
    manifest_entries = manifest.get("entries")
    if not isinstance(manifest_entries, list):
        raise ValueError("workspace manifest entries must be a list")
    identities = [_tuple_identity(item.get("identity")) for item in manifest_entries if isinstance(item, dict)]
    if len(identities) != len(manifest_entries) or len(identities) != len(set(identities)):
        raise ValueError("workspace manifest review identities are invalid or duplicated")
    if set(identities) != set(entries):
        raise ValueError("workspace review identity coverage mismatch")
    return manifest, queue, entries


def _editable_review(
    workspace_root: str | Path,
    review_selector: str,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    root = Path(workspace_root).expanduser().resolve()
    manifest, queue, entries = _load_editable_workspace(root)
    del queue
    selected: list[tuple[dict[str, Any], Path]] = []
    for item in manifest["entries"]:
        path = _contained_path(root, item.get("review_path"), "reviews")
        relative = str(path.relative_to(root))
        if review_selector in {path.name, relative, str(path)}:
            selected.append((item, path))
    if len(selected) != 1:
        raise ValueError(f"review selector must match exactly one manifest entry:{review_selector}")
    item, path = selected[0]
    if not path.is_file():
        raise ValueError(f"review file is unavailable:{path}")
    identity = _tuple_identity(item.get("identity"))
    entry = entries[identity]
    review = _load_json(path)
    failures = _immutable_binding_failures(entry["review_template"], review)
    if failures:
        raise ValueError(f"review immutable binding drift:{','.join(failures)}")
    return root, entry, path, review


def _identity_pending(review: dict[str, Any]) -> bool:
    return (
        str(review.get("reviewer") or "").strip() in {"", "__REQUIRED_NAMED_HUMAN__"}
        or str(review.get("reviewed_at") or "").strip() in {"", "__REQUIRED_ISO8601__"}
    )


def _require_unsigned(review: dict[str, Any]) -> None:
    if not _identity_pending(review):
        raise ValueError("signed review is immutable; create a new reviewed workspace for corrections")


def _validate_match(kind: str, decision: str, value: str, known_ids: set[str]) -> None:
    if decision not in {"matched", "no_match"}:
        raise ValueError(f"invalid {kind} match decision:{decision}")
    if decision == "matched":
        if not value:
            raise ValueError(f"{kind} matched decision requires an id")
        if value not in known_ids:
            raise ValueError(f"unknown {kind} match id:{value}")
    elif value:
        raise ValueError(f"{kind} no_match decision must not retain an id")


def _validate_decisions_for_signature(entry: dict[str, Any], review: dict[str, Any]) -> None:
    gold_ids = {str(item.get("claim_id") or "") for item in entry.get("gold_claims", [])}
    mutation_ids = {
        str(item.get("mutation_id") or "")
        for item in entry["review_template"].get("mutation_trials", [])
        if isinstance(item, dict)
    }
    relation_ids = {
        str(item.get("relation_id") or "") for item in entry.get("gold_figure_relations", [])
    }
    for item in review.get("claims", []):
        claim_id = str(item.get("atomic_claim_id") or "")
        _validate_match("semantic", str(item.get("semantic_match") or ""), str(item.get("gold_claim_id") or ""), gold_ids)
        _validate_match("mutation", str(item.get("mutation_match") or ""), str(item.get("mutation_id") or ""), mutation_ids)
        if not isinstance(item.get("direct_evidence_support"), bool):
            raise ValueError(f"claim direct evidence decision missing:{claim_id}")
        if not isinstance(item.get("qualifiers_preserved"), bool):
            raise ValueError(f"claim qualifier decision missing:{claim_id}")
    for item in review.get("figures", []):
        element_id = str(item.get("element_id") or "")
        gold_claim_id = str(item.get("gold_claim_id") or "")
        relation_id = str(item.get("relation_id") or "")
        if gold_claim_id and gold_claim_id not in gold_ids:
            raise ValueError(f"unknown gold claim id:{gold_claim_id}")
        if relation_id and relation_id not in relation_ids:
            raise ValueError(f"unknown gold relation id:{relation_id}")
        if item.get("element_kind") == "edge" and item.get("direct_relation_evidence") and not relation_id:
            raise ValueError(f"direct edge evidence requires a gold relation id:{element_id}")
        if item.get("element_kind") != "edge" and item.get("direct_relation_evidence"):
            raise ValueError(f"direct relation evidence is only valid for edge elements:{element_id}")
    rationale = str(review.get("blocked_reason_review") or "").strip()
    classification = str(review.get("blocked_reason_classification") or "").strip()
    if bool(rationale) != bool(classification):
        raise ValueError("blocked review rationale and classification must be supplied together")
    _validate_run_decision_against_frozen_summary(
        review,
        usable_completion=review.get("usable_completion"),
        intent_fields_reviewed=review.get("intent_fields_reviewed"),
        blocked_reason_review=rationale,
        blocked_reason_classification=classification,
    )


def _validate_run_decision_against_frozen_summary(
    review: dict[str, Any],
    *,
    usable_completion: object,
    intent_fields_reviewed: object,
    blocked_reason_review: str,
    blocked_reason_classification: str,
) -> None:
    if not isinstance(usable_completion, bool) or not isinstance(intent_fields_reviewed, bool):
        raise ValueError("run usability and intent decisions must be explicit booleans")
    summary_path = Path(str(review.get("run_summary_path") or "")).expanduser().resolve()
    if not summary_path.is_file() or _digest_file(summary_path) != review.get("run_summary_digest"):
        raise ValueError("frozen run summary is unavailable or its digest drifted")
    summary = _load_json(summary_path)
    blocked = summary.get("status") == "blocked"
    has_block_review = bool(blocked_reason_review.strip() and blocked_reason_classification)
    if blocked and not has_block_review:
        raise ValueError("blocked run requires rationale and a structured classification")
    if not blocked and has_block_review:
        raise ValueError("successful run must not carry a blocked-run classification")
    if blocked and usable_completion:
        raise ValueError("blocked run cannot be marked as a usable completion")
    if str(review.get("intent_id") or "") and intent_fields_reviewed is not True:
        raise ValueError("paired-intent run requires intent_fields_reviewed=true")


def _claim_decision_pending(value: object) -> bool:
    return bool(
        not isinstance(value, dict)
        or value.get("semantic_match") is None
        or value.get("mutation_match") is None
        or not isinstance(value.get("direct_evidence_support"), bool)
        or not isinstance(value.get("qualifiers_preserved"), bool)
    )


def _figure_decision_pending(value: object) -> bool:
    return bool(
        not isinstance(value, dict)
        or not isinstance(value.get("semantically_supported"), bool)
        or not isinstance(value.get("rendered_drift"), bool)
        or (
            value.get("element_kind") == "edge"
            and not isinstance(value.get("direct_relation_evidence"), bool)
        )
    )


def _run_decision_pending(review: dict[str, Any]) -> bool:
    return bool(
        not isinstance(review.get("usable_completion"), bool)
        or not isinstance(review.get("intent_fields_reviewed"), bool)
        or str(review.get("blocked_reason_review") or "") == "__REQUIRED_BLOCK_REVIEW__"
        or (
            bool(str(review.get("blocked_reason_review") or "").strip())
            and review.get("blocked_reason_classification") is None
        )
    )


def _has_human_placeholders(review: dict[str, Any]) -> bool:
    identity_placeholders = _identity_pending(review)
    claims = review.get("claims") if isinstance(review.get("claims"), list) else []
    figures = review.get("figures") if isinstance(review.get("figures"), list) else []
    claim_placeholders = any(_claim_decision_pending(item) for item in claims)
    figure_placeholders = any(_figure_decision_pending(item) for item in figures)
    return (
        identity_placeholders
        or _run_decision_pending(review)
        or claim_placeholders
        or figure_placeholders
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
