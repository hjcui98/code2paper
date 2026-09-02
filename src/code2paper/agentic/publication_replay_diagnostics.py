"""Read-only diagnostics for one frozen publication replay root."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from code2paper.core.output_names import ALIASES, METHOD_OUTPUTS


_DISPLAY_MATH_RE = re.compile(
    r"(?s)(?:\\\[.*?\\\]|\\begin\{(?:equation|aligned|gather|split|cases)\}.*?"
    r"\\end\{(?:equation|aligned|gather|split|cases)\}|\$\$.*?\$\$)"
)
_INTERNAL_AUDIT_RE = re.compile(
    r"\b(?:audit|callback|sidecar|pending|unverified|validation\s+status|"
    r"repository\s+evidence|formalization\s+pending|typed\s+gap)\b",
    re.I,
)


def _out_root_without_mutation(base: str | Path) -> Path:
    """Resolve a run root without calling ``method_output``.

    ``method_output`` creates parent directories as a convenience for writers.
    Diagnostics and evaluators are explicitly read-only, so this small
    projection intentionally performs only path arithmetic.
    """

    path = Path(base).expanduser().resolve()
    if len(path.parts) >= 2 and path.parts[-2:] == ("paper", "method"):
        return path.parent.parent
    # A caller may pass the run directory itself (whose child ``artifacts``
    # contains the Method outputs).  This check must precede the repository
    # ancestor projection below; otherwise a run nested under a repository
    # level ``artifacts`` directory is resolved to the wrong root.
    if (path / "artifacts").is_dir() or (path / "final").is_dir():
        return path
    if path.name == "artifacts":
        return path.parent
    if "artifacts" in path.parts:
        index = path.parts.index("artifacts")
        return Path(*path.parts[:index]) if index else Path(".")
    return path


def _artifact_path(root: str | Path, key: str) -> Path:
    canonical_key = ALIASES.get(key, key)
    try:
        relative = METHOD_OUTPUTS[canonical_key]
    except KeyError as exc:
        raise KeyError(f"unknown Method artifact key: {key}") from exc
    out_root = _out_root_without_mutation(root)
    primary = out_root / relative
    if primary.is_file():
        return primary
    # Clean replay rebuilds write the derived briefs/facets beside the copied
    # research artifacts before the Writer publishes its 06_authoring
    # products.  Read that legacy-compatible location without creating or
    # preferring it over an existing canonical output.
    if relative.startswith("artifacts/06_authoring/"):
        fallback = out_root / "artifacts" / f"{canonical_key}.json"
        if fallback.is_file():
            return fallback
    return primary


def _json_artifact(root: Path, key: str) -> dict[str, Any] | None:
    path = _artifact_path(root, key)
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{key} must contain a JSON object")
    return value


def _text_size(root: Path, key: str) -> int:
    path = _artifact_path(root, key)
    return len(path.read_bytes()) if path.is_file() else 0


def _mapping_items(payload: Mapping[str, Any] | None, *keys: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(payload, Mapping):
        return ()
    value: Any = None
    for key in keys:
        if key in payload:
            value = payload.get(key)
            break
    if value is None:
        return ()
    if isinstance(value, Mapping):
        value = value.values()
    if isinstance(value, (str, bytes)):
        return ()
    try:
        return tuple(item for item in value if isinstance(item, Mapping))
    except TypeError:
        return ()


def _ids(values: Any) -> tuple[str, ...]:
    if values is None or isinstance(values, (str, bytes, Mapping)):
        return ()
    try:
        return tuple(dict.fromkeys(
            str(value).strip() for value in values if str(value).strip()
        ))
    except TypeError:
        return ()


def _section_call_rows(formalization: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return _mapping_items(formalization, "formalizer_call_traces", "call_traces")


def _section_formula_rows(formalization: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return _mapping_items(formalization, "sections", "section_results")


def _package_rows(formalization: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        package
        for section in _section_formula_rows(formalization)
        for package in _mapping_items(section, "packages", "accepted_packages")
    )


def _transaction_rows(
    transaction_assessments: Mapping[str, Any],
    section_outputs: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    fallback: list[Mapping[str, Any]] = []
    for raw in section_outputs.values():
        output = raw.get("output", raw) if isinstance(raw, Mapping) else {}
        if not isinstance(output, Mapping):
            continue
        fallback.extend(_mapping_items(output, "paragraphs"))
    if not fallback:
        return _mapping_items(transaction_assessments, "assessments", "transactions")

    # The assessment sidecar is the authority for validity, but deliberately
    # stores digests and counters rather than copying Writer prose.  Formula
    # exact-body diagnostics still need the immutable paragraph bytes.  Keep
    # the Writer transaction as the diagnostic row and merge the assessment
    # fields only when the paragraph output does not already carry them.  This
    # also keeps exact-witness counts meaningful for failed Candidate rows.
    assessments = {
        (
            str(item.get("section_id") or "").strip(),
            str(item.get("paragraph_id") or "").strip(),
        ): item
        for item in _mapping_items(transaction_assessments, "assessments", "transactions")
        if str(item.get("paragraph_id") or "").strip()
    }
    merged: list[dict[str, Any]] = []
    for raw in fallback:
        row = dict(raw)
        key = (
            str(row.get("section_id") or "").strip(),
            str(row.get("paragraph_id") or "").strip(),
        )
        assessment = assessments.get(key)
        if assessment is not None:
            for field in (
                "valid", "required_by_kind", "declared_by_kind",
                "witnessed_by_kind", "missing_by_kind", "invalid_witnesses",
                "semantic_failures", "body_digest", "content_digest",
            ):
                row.setdefault(field, assessment.get(field))
        merged.append(row)
    return tuple(merged)


def _surface_mode_counts(*payloads: Mapping[str, Any] | None) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for payload in payloads:
        for item in _mapping_items(payload, "annotations", "items", "sentences", "paragraphs"):
            mode = str(
                item.get("surface_mode")
                or item.get("candidate_surface_mode")
                or "unknown"
            ).strip() or "unknown"
            counts[mode] += 1
    return dict(sorted(counts.items()))


def _candidate_sentence_count(candidate_text: str) -> int:
    return sum(
        bool(line.strip()) and not line.lstrip().startswith("#")
        for line in re.split(r"(?<=[.!?])\s+|\n+", candidate_text)
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _formula_funnel(
    *,
    formalization_rows: Iterable[Mapping[str, Any]],
    formalizer_rows: Iterable[Mapping[str, Any]],
    package_items: Iterable[Mapping[str, Any]],
    transaction_rows: Iterable[Mapping[str, Any]],
    sections: Iterable[Mapping[str, Any]],
    accepted_package_ids: set[str],
    consumed_package_ids: set[str],
    candidate_text: str = "",
) -> dict[str, Any]:
    """Expose the formula lifecycle, including packages rejected in-flight.

    Persisted section results contain only accepted packages, so counting that
    collection cannot explain a Formalizer guard rejection.  The call trace is
    the authoritative diagnostic source for proposal and rejection counts;
    accepted/consumed/exact-body stages are joined to it by package id where
    those ids are persisted.
    """

    attempts: list[tuple[str, Mapping[str, Any]]] = []
    for section in formalizer_rows:
        section_id = str(section.get("section_id") or "").strip()
        raw_attempts = section.get("call_traces") or ()
        if isinstance(raw_attempts, Mapping) or isinstance(raw_attempts, (str, bytes)):
            raw_attempts = ()
        for attempt in raw_attempts:
            if isinstance(attempt, Mapping):
                attempts.append((section_id, attempt))

    proposed_count = 0
    rejected_count = 0
    rejected_attempt_count = 0
    route_ambiguous_failure_count = 0
    route_ambiguous_package_ids: set[str] = set()
    reason_counts: Counter[str] = Counter()
    accepted_trace_count = 0
    # Each consumer-first Formalizer invocation has its own cumulative
    # accepted-package counter.  Keep the legacy section-only key for traces
    # without consumer metadata, but do not let one consumer's counter absorb
    # another consumer's first accepted package.
    previous_accepted_by_group: dict[tuple[str, str], int] = {}

    def package_id_from_failure(value: str) -> str:
        # Failure strings are emitted as ``<package_id>:<reason>``.  Package
        # ids may themselves contain colons, so split at the known reason
        # namespace rather than at the first colon.
        for marker in (
            ":formula_package_", ":markdown_block_", ":latex_",
            ":repository_", ":hybrid_", ":author_intent_",
        ):
            if marker in value:
                return value.split(marker, 1)[0].strip()
        return ""

    for section_id, attempt in attempts:
        proposed = max(0, _safe_int(attempt.get("proposed_package_count")))
        accepted_total = max(0, _safe_int(attempt.get("accepted_package_count")))
        consumer_id = str(attempt.get("consumer_paragraph_id") or "").strip()
        accepted_group = (section_id, consumer_id)
        previous_accepted = previous_accepted_by_group.get(accepted_group, 0)
        accepted_delta = max(0, accepted_total - previous_accepted)
        previous_accepted_by_group[accepted_group] = max(previous_accepted, accepted_total)
        proposed_count += proposed
        accepted_trace_count += accepted_delta
        rejected_count += max(0, proposed - accepted_delta)
        failures = attempt.get("guard_failures") or ()
        if isinstance(failures, str):
            failures = (failures,)
        failure_values = tuple(str(item).strip() for item in failures if str(item).strip())
        if failure_values:
            rejected_attempt_count += 1
        for failure in failure_values:
            reason_counts[failure] += 1
            if "ambiguous" in failure.casefold():
                route_ambiguous_failure_count += 1
                package_id = package_id_from_failure(failure)
                if package_id:
                    route_ambiguous_package_ids.add(package_id)

    routed_obligation_ids: set[str] = set()
    unresolved_route_obligation_ids: set[str] = set()
    route_failure_values: list[str] = []
    for payload in (*formalization_rows, *formalizer_rows):
        for key in (
            "formula_route_failures", "route_failures", "binding_failures",
            "guard_failures",
        ):
            values = payload.get(key) or ()
            if isinstance(values, str):
                values = (values,)
            route_failure_values.extend(
                str(value).strip() for value in values if str(value).strip()
            )
        for value in payload.get("consumer_route_ambiguous") or ():
            unresolved_route_obligation_ids.add(str(value).strip())
        for value in payload.get("consumer_route_map", {}).items() if isinstance(
            payload.get("consumer_route_map"), Mapping
        ) else ():
            obligation_id, consumer_id = value
            if str(obligation_id).strip() and str(consumer_id).strip():
                routed_obligation_ids.add(str(obligation_id).strip())
        for obligation in _mapping_items(payload, "formula_obligations"):
            obligation_id = str(obligation.get("obligation_id") or "").strip()
            consumer_id = str(obligation.get("consumer_paragraph_id") or "").strip()
            paragraph_ids = _ids(obligation.get("paragraph_ids"))
            if obligation_id and (consumer_id or len(paragraph_ids) == 1):
                routed_obligation_ids.add(obligation_id)
            elif obligation_id:
                unresolved_route_obligation_ids.add(obligation_id)
    for failure in route_failure_values:
        reason_counts[failure] += 1
        if "ambiguous" in failure.casefold():
            route_ambiguous_failure_count += 1

    paragraph_texts: dict[str, tuple[str, ...]] = {}
    for row in transaction_rows:
        paragraph_id = str(row.get("paragraph_id") or "").strip()
        body = str(row.get("paragraph_markdown") or row.get("body") or "")
        if paragraph_id and body:
            paragraph_texts.setdefault(paragraph_id, ())
            paragraph_texts[paragraph_id] = (
                *paragraph_texts[paragraph_id], body,
            )
    formula_texts = [
        str(row.get("writer_text") or "")
        for row in sections
        if isinstance(row, Mapping)
    ]
    if candidate_text:
        formula_texts.append(candidate_text)
    exact_body_ids: set[str] = set()
    for package in package_items:
        package_id = str(
            package.get("package_id") or package.get("formula_package_id") or ""
        ).strip()
        if not package_id or package_id not in accepted_package_ids:
            continue
        block = str(package.get("markdown_block") or "")
        consumer_paragraph_id = str(
            package.get("consumer_paragraph_id") or ""
        ).strip()
        consumer_texts = paragraph_texts.get(consumer_paragraph_id, ())
        # A canonical block shared by two obligations is evidence only in the
        # package's unique consumer paragraph.  Looking through the whole
        # candidate would incorrectly mark an unconsumed package as exact
        # merely because another paragraph happens to use the same equation.
        if consumer_texts:
            exact = any(text.count(block) == 1 for text in consumer_texts)
        else:
            # Historical artifacts may not persist paragraph transactions;
            # retain the legacy fallback only when the package has no
            # consumer paragraph bytes available at all.
            exact = bool(block and any(block in text for text in formula_texts))
        if block and exact:
            exact_body_ids.add(package_id)

    return {
        "formalizer_attempts": len(attempts),
        "proposed_packages": proposed_count,
        "routed_obligations": len(routed_obligation_ids),
        "unresolved_route_obligations": len(
            unresolved_route_obligation_ids - routed_obligation_ids
        ),
        "accepted_packages": len(accepted_package_ids),
        "consumed_packages": len(consumed_package_ids & accepted_package_ids),
        "exact_body_validated_packages": len(exact_body_ids),
        "accepted_trace_packages": accepted_trace_count,
        "rejected_packages": rejected_count,
        "rejected_attempts": rejected_attempt_count,
        "route_ambiguous_failures": route_ambiguous_failure_count,
        "route_ambiguous_package_ids": sorted(route_ambiguous_package_ids),
        "rejected_reason_counts": dict(sorted(reason_counts.items())),
        "accepted_package_ids": sorted(accepted_package_ids),
        "consumed_package_ids": sorted(consumed_package_ids & accepted_package_ids),
        "exact_body_validated_package_ids": sorted(exact_body_ids),
    }


def diagnose_publication_replay(root: str | Path) -> dict[str, Any]:
    """Extract a stable comparison record without changing the replay root."""

    run_root = Path(root).expanduser().resolve()
    if not run_root.is_dir():
        raise FileNotFoundError(f"publication replay root does not exist: {run_root}")
    execution_record: dict[str, Any] = {}
    execution_path = run_root / "execution_record.json"
    if execution_path.is_file():
        try:
            payload = json.loads(execution_path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                execution_record = dict(payload)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            execution_record = {}
    failure_record: dict[str, Any] = {}
    failure_path = run_root / "artifacts" / "06_authoring" / "authoring_failure_v1.json"
    if failure_path.is_file():
        try:
            payload = json.loads(failure_path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                failure_record = dict(payload)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            failure_record = {}
    checkpoint = _json_artifact(run_root, "publication_section_checkpoint_v1") or {}
    plan = _json_artifact(run_root, "method_section_plan_v2") or {}
    formalization = _json_artifact(run_root, "formalization_section_results_v1") or {}
    writer_result = _json_artifact(run_root, "publication_writer_result_v1") or {}
    quality = _json_artifact(run_root, "publication_quality_report_v1") or {}
    validation = _json_artifact(run_root, "text_evidence_validation") or {}
    content_trace = _json_artifact(run_root, "method_content_trace_v1") or {}
    alignment = _json_artifact(run_root, "method_proposition_alignment_v1") or {}
    propositions = _json_artifact(run_root, "method_propositions_v1") or {}
    editor = _json_artifact(run_root, "publication_editor_transitions_v1") or {}
    rewrite = _json_artifact(run_root, "publication_rewrite_transitions_v1") or {}
    transaction_assessments = _json_artifact(
        run_root, "publication_paragraph_transaction_assessments_v1"
    ) or {}
    structural_exit = _json_artifact(run_root, "authoring_structural_exit_v1") or {}
    dossiers = _json_artifact(run_root, "research_mechanism_dossiers_v1") or {}
    derivations = _json_artifact(run_root, "derivation_records_v1") or {}
    candidate_authority_artifact = _json_artifact(
        run_root, "candidate_authority_validation_v1"
    ) or {}
    # The durable Candidate authority artifact wraps the validator result so
    # the outer object can bind the candidate text digest and its own digest.
    # Diagnostics consume the inner validator view while retaining support for
    # the historical top-level shape.
    candidate_authority = (
        candidate_authority_artifact.get("validation")
        if isinstance(candidate_authority_artifact.get("validation"), Mapping)
        else candidate_authority_artifact
    )
    candidate_annotations = _json_artifact(
        run_root, "publication_candidate_annotations_v1"
    ) or {}

    section_outputs = checkpoint.get("section_outputs") or checkpoint.get("sections") or {}
    if isinstance(section_outputs, list):
        section_outputs = {
            str(item.get("section_id") or ""): item
            for item in section_outputs if isinstance(item, dict)
        }
    if not isinstance(section_outputs, dict):
        section_outputs = {}
    checkpoint_parent = _artifact_path(
        run_root, "publication_section_checkpoint_v1"
    ).parent.resolve()
    resolved_outputs: dict[str, Any] = {}
    for section_id, raw in section_outputs.items():
        if not isinstance(raw, dict) or not raw.get("output_ref"):
            resolved_outputs[str(section_id)] = raw
            continue
        output_path = (checkpoint_parent / str(raw["output_ref"])).resolve()
        if checkpoint_parent not in output_path.parents or not output_path.is_file():
            resolved_outputs[str(section_id)] = {}
            continue
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        resolved_outputs[str(section_id)] = (
            payload if isinstance(payload, dict) else {}
        )
    section_outputs = resolved_outputs

    # The immutable section checkpoint intentionally contains only committed
    # sections.  Diagnostics must nevertheless inspect the Writer's retained
    # Candidate transactions for an uncommitted sibling/section; otherwise a
    # failed paragraph disappears and its exact formula body is reported as
    # absent.  Checkpoint bytes remain preferred for already committed
    # sections, while Writer output fills only sections the checkpoint did not
    # commit (or whose resolved payload has no paragraph transactions).
    checkpoint_section_ids = set(section_outputs)
    for raw in writer_result.get("section_results") or ():
        if not isinstance(raw, Mapping):
            continue
        section_id = str(raw.get("section_id") or "").strip()
        output = raw.get("output")
        if not section_id or not isinstance(output, Mapping):
            continue
        existing = section_outputs.get(section_id)
        existing_output = (
            existing.get("output", existing)
            if isinstance(existing, Mapping) else {}
        )
        if (
            section_id not in checkpoint_section_ids
            or not _mapping_items(existing_output, "paragraphs")
        ):
            section_outputs[section_id] = {
                "section_id": section_id,
                "accepted": bool(raw.get("accepted")),
                "output": dict(output),
            }
    section_rows = {
        str(row.get("section_id") or ""): row
        for row in alignment.get("sections") or () if isinstance(row, dict)
    }
    failures_by_type: dict[str, int] = {}
    for verdict in validation.get("verdicts") or ():
        if not isinstance(verdict, dict):
            continue
        for failure in verdict.get("deterministic_failures") or ():
            name = str(failure)
            failures_by_type[name] = failures_by_type.get(name, 0) + 1

    sections: list[dict[str, Any]] = []
    for section_id, raw in sorted(section_outputs.items()):
        output = raw.get("output", raw) if isinstance(raw, dict) else {}
        if not isinstance(output, dict):
            output = {}
        alignment_row = section_rows.get(section_id, {})
        sections.append({
            "section_id": section_id,
            "writer_text": str(output.get("section_markdown") or ""),
            "declared_rendered_proposition_ids": list(
                output.get("rendered_proposition_ids") or ()
            ),
            "declared_deferred_proposition_ids": list(
                output.get("deferred_proposition_ids") or ()
            ),
            "validated_proposition_ids": list(
                alignment_row.get("validated_proposition_ids") or ()
            ),
            "missing_proposition_ids": list(
                alignment_row.get("missing_proposition_ids") or ()
            ),
            "rendered_paragraph_ids": list(
                output.get("rendered_paragraph_ids") or ()
            ),
            "rendered_slot_ids": list(output.get("rendered_slot_ids") or ()),
            "rendered_edge_ids": list(output.get("rendered_edge_ids") or ()),
            "used_formula_package_ids": list(
                output.get("used_formula_package_ids") or ()
            ),
            "used_equation_ids": list(output.get("used_equation_ids") or ()),
        })

    utility = quality.get("utility") or {}
    safety = quality.get("safety") or {}
    formalizer_rows = _section_call_rows(formalization)
    formalization_rows = _section_formula_rows(formalization)
    package_items = _package_rows(formalization)
    package_ids = {
        str(item.get("package_id") or item.get("formula_package_id") or "").strip()
        for item in package_items
        if str(item.get("package_id") or item.get("formula_package_id") or "").strip()
    }
    required_formula_sections: set[str] = set()
    plan_section_by_id = {
        str(section.get("section_id") or ""): section
        for section in _mapping_items(plan, "sections")
        if str(section.get("section_id") or "").strip()
    }
    for section in formalization_rows:
        section_id = str(section.get("section_id") or "").strip()
        obligations = _mapping_items(section, "formula_obligations")
        required_ids = _ids(section.get("required_formula_obligation_ids"))
        required_ids = required_ids or tuple(
            str(item.get("obligation_id") or "").strip()
            for item in obligations
            if str(item.get("obligation_id") or "").strip()
            and str(item.get("expectation") or "required") in {"required", "preferred"}
        )
        has_consumer = bool(section.get("formula_consumer")) or any(
            str(item.get("consumer_paragraph_id") or "").strip()
            or len(_ids(item.get("paragraph_ids"))) == 1
            for item in obligations
        )
        if section_id and required_ids and has_consumer:
            required_formula_sections.add(section_id)
    if not required_formula_sections:
        for section_id, section in plan_section_by_id.items():
            paragraphs = _mapping_items(section, "paragraphs")
            if any(_ids(row.get("formula_obligation_ids")) for row in paragraphs):
                required_formula_sections.add(section_id)

    invoked_sections = {
        str(row.get("section_id") or "").strip()
        for row in formalizer_rows
        if str(row.get("section_id") or "").strip()
        and (
            bool(row.get("formalizer_invoked"))
            or int(row.get("formalizer_call_count") or 0) > 0
            or bool(row.get("call_traces"))
        )
    }
    zero_call_required_sections = required_formula_sections - invoked_sections
    ambiguous_values: list[str] = []
    for payload in (*formalization_rows, *formalizer_rows):
        for key in (
            "formula_route_failures", "route_failures", "binding_failures",
            "guard_failures",
        ):
            values = payload.get(key) or ()
            if isinstance(values, str):
                values = (values,)
            for value in values:
                if "ambiguous" in str(value).casefold():
                    ambiguous_values.append(str(value))

    transaction_rows = _transaction_rows(transaction_assessments, section_outputs)
    declared_target_count = 0
    exact_witness_count = 0
    empty_witness_count = 0
    consumed_package_ids: set[str] = set()
    for row in transaction_rows:
        declared = row.get("declared_by_kind")
        if isinstance(declared, Mapping):
            declared_target_count += sum(
                len(_ids(values)) for values in declared.values()
            )
            # A model declaration is not a consumed formula.  The Binder's
            # rendered trace is authoritative; an invalid paragraph may
            # declare a package while none of its targets are admitted to the
            # Candidate transaction.
            if not content_trace and bool(row.get("valid")):
                consumed_package_ids.update(_ids(declared.get("formula")))
        else:
            for key in (
                "rendered_from_facet_ids", "rendered_field_candidate_ids",
                "rendered_slot_ids", "rendered_edge_ids", "used_formula_package_ids",
                "used_claim_ids", "used_equation_ids",
            ):
                declared_target_count += len(_ids(row.get(key)))
            if not content_trace and bool(row.get("valid")):
                consumed_package_ids.update(_ids(row.get("used_formula_package_ids")))
        witnesses = row.get("witnesses") or ()
        exact_witness_count += len(witnesses) if not isinstance(witnesses, str) else 0
        body = str(row.get("paragraph_markdown") or row.get("body") or "").strip()
        if body and not witnesses:
            empty_witness_count += 1
    if content_trace:
        consumed_package_ids.update(
            package_id
            for row in _mapping_items(content_trace, "rows")
            if str(row.get("terminal_state") or "") == "rendered"
            for package_id in _ids(row.get("accepted_formula_package_ids"))
        )
    # The transaction contract is the sole authority for the package
    # terminal state.  In particular, ``review_status=accepted`` is not
    # sufficient when the package is author-intent or otherwise lacks the
    # repository-derived/code-verified lane.  Keeping this projection shared
    # with Binder/Trace prevents the evaluator from reporting a different
    # accepted denominator for the same package.
    from code2paper.agentic.publication_transaction_contract import (
        _formula_package_terminal_disposition,
    )
    accepted_package_items = tuple(
        item for item in package_items
        if _formula_package_terminal_disposition(item) == "accepted"
    )
    accepted_package_ids = {
        str(item.get("package_id") or item.get("formula_package_id") or "").strip()
        for item in accepted_package_items
        if str(item.get("package_id") or item.get("formula_package_id") or "").strip()
    }
    accepted_package_count = len(accepted_package_ids)
    consumed_package_count = len(consumed_package_ids & accepted_package_ids)
    renderable_package_count = sum(
        bool(_DISPLAY_MATH_RE.search(str(item.get("markdown_block") or item.get("latex") or "")))
        for item in accepted_package_items
    )

    candidate_path = _artifact_path(run_root, "publication_candidate_method")
    candidate_text = (
        candidate_path.read_text(encoding="utf-8") if candidate_path.is_file() else ""
    )
    formula_funnel = _formula_funnel(
        formalization_rows=formalization_rows,
        formalizer_rows=formalizer_rows,
        package_items=package_items,
        transaction_rows=transaction_rows,
        sections=sections,
        accepted_package_ids=accepted_package_ids,
        consumed_package_ids=consumed_package_ids,
        candidate_text=candidate_text,
    )
    surface_modes = _surface_mode_counts(candidate_annotations)
    if not surface_modes:
        surface_modes = _surface_mode_counts(writer_result)
    internal_audit_term_count = len(_INTERNAL_AUDIT_RE.findall(candidate_text))
    derivation_counts = Counter(
        str(item.get("derivation_kind") or "unknown")
        for item in _mapping_items(derivations, "items", "records", "derivations")
    )
    leakage_items = []
    for item in _mapping_items(candidate_annotations, "annotations", "items", "sentences", "paragraphs"):
        mode = str(item.get("surface_mode") or item.get("candidate_surface_mode") or "")
        if mode in {"author_specification", "mismatch_statement"} and any(
            bool(item.get(key)) for key in ("verified", "in_verified", "enters_verified", "verified_eligible")
        ):
            leakage_items.append(item)
    observations = {
        "required_formula_consumer_sections": len(required_formula_sections),
        "formalizer_invoked_sections": len(invoked_sections),
        "formalizer_zero_call_required_sections": len(zero_call_required_sections),
        "formula_route_ambiguous_packages": (
            formula_funnel["route_ambiguous_failures"]
            or len(ambiguous_values)
        ),
        "accepted_formula_packages": accepted_package_count,
        "consumed_formula_packages": consumed_package_count,
        "paragraph_declared_target_count": declared_target_count,
        "paragraph_exact_witness_count": exact_witness_count,
        "empty_witness_transaction_count": empty_witness_count,
        "candidate_internal_audit_term_count": internal_audit_term_count,
        "candidate_sentences_by_surface_mode": surface_modes,
        "derivation_records_by_kind": dict(sorted(derivation_counts.items())),
        "formula_renderable_packages": renderable_package_count,
        "formula_unrenderable_packages": max(0, accepted_package_count - renderable_package_count),
        "verified_leakage_count": len(leakage_items),
        "formula_funnel": formula_funnel,
    }
    return {
        "schema_version": "1.0",
        "run_root": str(run_root),
        "artifact_presence": {
            key: _artifact_path(run_root, key).is_file()
            for key in (
                "method_section_plan_v2",
                "method_propositions_v1",
                "method_proposition_alignment_v1",
                "method_argument_briefs_v1",
                "method_argument_facets_v1",
                "facet_evidence_alignments_v1",
                "candidate_facet_policies_v1",
                "method_argument_facet_alignment_trace_v1",
                "formalization_section_results_v1",
                "publication_writer_result_v1",
                "publication_candidate_method",
                "repository_verified_method",
                "author_review_candidates",
                "text_evidence_validation",
                "method_content_trace_v1",
                "publication_paragraph_transaction_assessments_v1",
                "publication_paragraph_checkpoint_v1",
                "authoring_structural_exit_v1",
                "research_mechanism_dossiers_v1",
                "derivation_records_v1",
                "candidate_authority_validation_v1",
                "publication_candidate_annotations_v1",
            )
        } | {"authoring_failure_v1": failure_path.is_file()},
        "execution": {
            "record_present": execution_path.is_file(),
            "exit_code": execution_record.get("exit_code"),
            "writer_status": str(
                execution_record.get("writer_status")
                or writer_result.get("status")
                or ""
            ),
            "terminal_stage": str(execution_record.get("terminal_stage") or ""),
            "terminal_reason": str(
                execution_record.get("terminal_reason")
                or writer_result.get("blocked_reason")
                or ""
            ),
            "terminal_error_code": str(
                execution_record.get("terminal_error_code") or ""
            ),
        },
        "failure": failure_record or None,
        "output_bytes": {
            "candidate": _text_size(run_root, "publication_candidate_method"),
            "verified": _text_size(run_root, "repository_verified_method"),
            "review": _text_size(run_root, "author_review_candidates"),
        },
        "propositions": {
            "planned": len(propositions.get("propositions") or ()),
            "gaps": len(propositions.get("gaps") or ()),
            "rendered": len({
                proposition_id
                for row in alignment.get("sections") or ()
                for proposition_id in (
                    (
                        row.get("rendered_proposition_ids")
                        or row.get("validated_proposition_ids")
                        or ()
                    ) if isinstance(row, dict) else ()
                )
            }),
            "validated": len({
                proposition_id
                for row in alignment.get("sections") or ()
                for proposition_id in (
                    row.get("validated_proposition_ids") or ()
                    if isinstance(row, dict) else ()
                )
            }),
            "semantic_alignment_calls": int(
                alignment.get("semantic_alignment_calls") or 0
            ),
        },
        "reverse_validation": {
            "status": validation.get("status", "not_run"),
            "supported": int(validation.get("supported_claims") or 0),
            "caveated": int(validation.get("caveated_claims") or 0),
            "unsupported": int(validation.get("unsupported_claims") or 0),
            "unverified": int(validation.get("unverified_claims") or 0),
            "failures_by_type": dict(sorted(failures_by_type.items())),
        },
        "quality": {
            "status": quality.get("status", "not_run"),
            "planned_proposition_recall": utility.get(
                "planned_proposition_recall", 0.0
            ),
            "rendered_proposition_recall": utility.get(
                "rendered_proposition_recall", 0.0
            ),
            "validated_proposition_recall": utility.get(
                "validated_proposition_recall", 0.0
            ),
            "unsupported_positive_claims": safety.get(
                "unsupported_positive_claims", 0
            ),
            "issue_codes": [
                str(item.get("code") or "")
                for item in quality.get("issues") or () if isinstance(item, dict)
            ],
        },
        "content_chain": {
            "summary": dict(
                content_trace.get("summary")
                or (quality.get("content_chain") or {}).get("summary")
                or {}
            ),
            "content_digest": str(
                content_trace.get("content_digest")
                or (quality.get("content_chain") or {}).get("content_digest")
                or ""
            ),
            "terminal_states": sorted({
                str(row.get("terminal_state") or "")
                for row in content_trace.get("rows") or ()
                if isinstance(row, dict)
            }),
        },
        "transactions": {
            "editor": len(editor.get("transitions") or ()),
            "rewrite": len(rewrite.get("transitions") or ()),
            "rewrite_applied": sum(
                item.get("status") == "applied"
                for item in rewrite.get("transitions") or ()
                if isinstance(item, dict)
            ),
            "paragraph_assessments": len(transaction_assessments.get("assessments") or ()),
            "paragraph_assessments_valid": sum(
                bool(item.get("valid"))
                for item in transaction_assessments.get("assessments") or ()
                if isinstance(item, dict)
            ),
            "paragraph_assessments_invalid": sum(
                not bool(item.get("valid"))
                for item in transaction_assessments.get("assessments") or ()
                if isinstance(item, dict)
            ),
        },
        "structural_exit": {
            "eligible": bool(structural_exit.get("eligible")),
            "reasons": list(structural_exit.get("reasons") or ()),
            "required_targets": int(structural_exit.get("required_targets") or 0),
            "valid_targets": int(structural_exit.get("valid_targets") or 0),
            "accepted_formula_packages": int(
                structural_exit.get("accepted_formula_packages") or 0
            ),
            "consumed_formula_packages": int(
                structural_exit.get("consumed_formula_packages") or 0
            ),
            "content_digest": str(structural_exit.get("content_digest") or ""),
        },
        "authoring_observations": observations,
        # These projections make the Slice 0 counters easy to consume from a
        # shell/CSV comparison while retaining the grouped view for humans.
        "required_formula_consumer_sections": observations["required_formula_consumer_sections"],
        "formalizer_invoked_sections": observations["formalizer_invoked_sections"],
        "formalizer_zero_call_required_sections": observations["formalizer_zero_call_required_sections"],
        "formula_route_ambiguous_packages": observations["formula_route_ambiguous_packages"],
        "accepted_formula_packages": observations["accepted_formula_packages"],
        "consumed_formula_packages": observations["consumed_formula_packages"],
        "paragraph_declared_target_count": observations["paragraph_declared_target_count"],
        "paragraph_exact_witness_count": observations["paragraph_exact_witness_count"],
        "empty_witness_transaction_count": observations["empty_witness_transaction_count"],
        "candidate_internal_audit_term_count": observations["candidate_internal_audit_term_count"],
        "candidate_sentences_by_surface_mode": observations["candidate_sentences_by_surface_mode"],
        "derivation_records_by_kind": observations["derivation_records_by_kind"],
        "formula": {
            "accepted_packages": observations["accepted_formula_packages"],
            "consumed_packages": observations["consumed_formula_packages"],
            "renderable_packages": observations["formula_renderable_packages"],
            "unrenderable_packages": observations["formula_unrenderable_packages"],
            "exact_body_validated_packages": formula_funnel[
                "exact_body_validated_packages"
            ],
        },
        "formula_funnel": formula_funnel,
        "candidate_surface": {
            "clean": internal_audit_term_count == 0,
            "internal_audit_term_count": internal_audit_term_count,
            "sentences_by_surface_mode": surface_modes,
            "authority_status": str(candidate_authority.get("status") or "not_run"),
            "violations": list(candidate_authority.get("violations") or ()),
            "warnings": list(candidate_authority.get("warnings") or ()),
        },
        "verified_leakage": {
            "count": len(leakage_items),
            "candidate_authority_status": str(candidate_authority.get("status") or "not_run"),
        },
        "sections": sections,
    }


__all__ = ["diagnose_publication_replay"]
