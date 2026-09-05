"""WP4 Slice 4B: callback semantic delta helpers (mandatory slots, fingerprints)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.method_argument_models import (
    MechanismResearchRequestV2,
    SectionArgumentGraphV1,
    WritingResearchRequestV1,
)

_MANDATORY_SLOT_ORDER = (
    "input",
    "representation",
    "transformation",
    "relation",
    "condition",
    "formula",
    "output",
)


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            result = dump(mode="json")
        except TypeError:
            result = dump()
        return result if isinstance(result, dict) else {}
    return {}


class AuthoringStructuralExitV1(BaseModel):
    """Fail-closed authorization receipt for a repository callback round.

    This is intentionally a derived decision, not a readiness claim.  A
    callback may run only after the source-to-render transaction is closed;
    missing witnesses, unconsumed formula packages, or an unscoped request
    keep the round stopped while preserving the Candidate for review.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    eligible: bool = False
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    plan_digest: str = ""
    trace_digest: str = ""
    assessment_digest: str = ""
    candidate_digest: str = ""
    required_paragraphs: int = 0
    valid_required_paragraphs: int = 0
    required_targets: int = 0
    valid_targets: int = 0
    required_slots: int = 0
    witnessed_slots: int = 0
    required_edges: int = 0
    witnessed_edges: int = 0
    invalid_paragraphs: int = 0
    blocked_representation: int = 0
    accepted_formula_packages: int = 0
    consumed_formula_packages: int = 0
    unresolved_required_formula_obligations: tuple[str, ...] = ()
    open_callback_requests: int = 0
    scoped_callback_requests: int = 0
    content_digest: str = ""

    @model_validator(mode="after")
    def _set_digest(self) -> "AuthoringStructuralExitV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


def _formula_package_uniquely_in_body(body: str, package: Mapping[str, Any]) -> bool:
    """True when accepted package latex occurs once inside display math."""

    from code2paper.agentic.publication_transaction_contract import _DISPLAY_MATH_RE

    block = str(package.get("markdown_block") or "")
    latex = str(package.get("latex") or "").strip()
    if not _DISPLAY_MATH_RE.search(str(body or "")):
        return False
    if block and body.count(block) == 1:
        return True
    if latex and body.count(latex) == 1:
        return True
    return False


def _ids(values: Any) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, dict)) or values is None:
        return ()
    try:
        values = tuple(values)
    except TypeError:
        return ()
    return tuple(dict.fromkeys(
        str(value).strip() for value in values if str(value).strip()
    ))


def _required_targets(row: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    from code2paper.agentic.publication_transaction_contract import (
        _publication_slot_ids,
    )

    result = {
        "facet": _ids(row.get("required_facet_ids")),
        "detail": _ids(row.get("required_detail_ids")),
        "slot": _publication_slot_ids(row),
        "edge": _ids(row.get("required_edge_ids")),
        "formula": _ids(row.get("formula_obligation_ids")),
    }
    # Atom ids are nested in the paragraph-local contract.  They remain
    # separate targets so a Detail declaration cannot hide a missing required
    # semantic atom.
    contract = row.get("witness_contract") or {}
    raw_targets = contract.get("targets", ()) if isinstance(contract, Mapping) else ()
    result["atom"] = tuple(dict.fromkeys(
        str(item.get("target_id") or "").strip()
        for item in raw_targets
        if isinstance(item, Mapping)
        and str(item.get("target_kind") or "") == "atom"
        and str(item.get("target_id") or "").strip()
        and bool(
            item.get(
                "required",
                True if "render_policy" not in item else item.get("render_policy") == "required",
            )
        )
    ))
    return {kind: values for kind, values in result.items() if values}


def _open_callback_scope(request: dict[str, Any]) -> bool:
    """A callback request must identify one technical owner and one gap."""

    if not str(request.get("request_id") or "").strip():
        return False
    mechanism_id = str(request.get("mechanism_id") or "").strip()
    if mechanism_id:
        # V2 deliberately does not require section/paragraph ownership.  A
        # detail, atom, operation, or typed unresolved kind is sufficient to
        # make the request auditable.
        if not str(request.get("unresolved_kind") or "").strip():
            return False
        if not any(
            str(request.get(name) or "").strip()
            for name in ("target_detail_id", "target_operation_ids", "target_atom_ids", "unresolved_kind")
        ):
            return False
    elif not str(request.get("section_id") or "").strip():
        return False
    if not str(request.get("exact_question") or "").strip():
        return False
    targets = (
        request.get("mandatory_missing_slots")
        or request.get("remaining_slots")
        or request.get("missing_parts")
        or request.get("target_formula_obligation_ids")
        or request.get("target_story_node_ids")
        or request.get("target_concept_keys")
        or request.get("target_brief_ids")
        or request.get("target_clause_ids")
        or request.get("target_detail_id")
        or request.get("target_operation_ids")
        or request.get("target_atom_ids")
        or request.get("unresolved_kind")
        or request.get("missing_rhetorical_move")
    )
    if isinstance(targets, str):
        targets = (targets,)
    return bool(_ids(targets))


def evaluate_authoring_structural_exit(
    *,
    plan_payload: Any = None,
    trace_payload: Any = None,
    writer_payload: Any = None,
    formalization_payload: Any = None,
    callback_payload: Any = None,
    assessment_payload: Any = None,
    candidate_digest: str = "",
    candidate_markdown: str = "",
) -> AuthoringStructuralExitV1:
    """Evaluate whether callback=1 is structurally authorized.

    The evaluator consumes persisted identifiers only.  It never searches
    source code or promotes model-declared ids to witnesses.  ``assessment``
    is mandatory for a current transaction run; old artifacts therefore stay
    ineligible instead of being silently upgraded by the callback path.
    """

    plan = _as_mapping(plan_payload)
    trace = _as_mapping(trace_payload)
    writer = _as_mapping(writer_payload)
    formalization = _as_mapping(formalization_payload)
    callback = _as_mapping(callback_payload)
    assessments = _as_mapping(assessment_payload)
    reasons: list[str] = []
    plan_digest = str(plan.get("content_digest") or writer.get("plan_digest") or "").strip()
    trace_digest = str(trace.get("content_digest") or "").strip()
    assessment_digest = str(assessments.get("content_digest") or "").strip()
    if not plan:
        reasons.append("plan_missing")
    if not trace:
        reasons.append("trace_missing")
    if not assessments:
        reasons.append("transaction_assessments_missing")
    if assessment_digest and trace.get("transaction_assessment_digest") not in {
        "", assessment_digest,
    }:
        reasons.append("transaction_assessment_digest_mismatch")
    writer_plan_digest = str(writer.get("plan_digest") or "").strip()
    if plan_digest and writer_plan_digest and plan_digest != writer_plan_digest:
        reasons.append("plan_digest_mismatch")
    writer_candidate_digest = str(writer.get("final_text_digest") or "").strip()
    candidate_digest = str(candidate_digest or writer_candidate_digest or "").strip()
    if candidate_digest and writer_candidate_digest and candidate_digest != writer_candidate_digest:
        reasons.append("candidate_digest_mismatch")
    assessment_plan_digest = str(assessments.get("plan_digest") or "").strip()
    if plan_digest and assessment_plan_digest and plan_digest != assessment_plan_digest:
        reasons.append("assessment_plan_digest_mismatch")
    if not candidate_digest:
        reasons.append("candidate_missing")

    plan_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for section in plan.get("sections") or ():
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "").strip()
        for row in section.get("paragraphs") or ():
            if isinstance(row, dict) and str(row.get("paragraph_id") or "").strip():
                plan_rows[(section_id, str(row["paragraph_id"]).strip())] = row

    assessment_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in assessments.get("assessments") or ():
        if not isinstance(raw, dict):
            continue
        key = (str(raw.get("section_id") or "").strip(), str(raw.get("paragraph_id") or "").strip())
        if key[1]:
            assessment_rows[key] = raw
    trace_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in trace.get("rows") or ():
        if not isinstance(raw, dict):
            continue
        key = (str(raw.get("section_id") or "").strip(), str(raw.get("paragraph_id") or "").strip())
        if key[1]:
            trace_rows[key] = raw

    # Formula obligations are not all hard Writer targets.  The Formalizer's
    # terminal state is the only authority for this distinction: an
    # ``intent_ready``/``review_required`` or ``not_applicable`` result stays
    # visible as a review/terminal outcome, but cannot inflate the accepted
    # code-equivalent target denominator.  Failed/unresolved obligations are
    # deliberately retained so the callback gate remains fail-closed.
    from code2paper.agentic.publication_transaction_contract import (
        _formula_package_terminal_disposition,
    )
    non_hard_formula_obligation_ids: set[str] = set()
    for section in formalization.get("sections") or ():
        if not isinstance(section, dict):
            continue
        package_dispositions = {
            str(package.get("package_id") or "").strip():
            _formula_package_terminal_disposition(package)
            for package in section.get("packages") or ()
            if isinstance(package, dict)
            and str(package.get("package_id") or "").strip()
        }
        for truth in section.get("obligation_truths") or ():
            if not isinstance(truth, dict):
                continue
            obligation_id = str(truth.get("obligation_id") or "").strip()
            terminal = str(truth.get("terminal_disposition") or "").strip()
            package_id = str(truth.get("package_id") or "").strip()
            if not terminal and package_id:
                terminal = package_dispositions.get(package_id, "")
            if obligation_id and terminal in {"review_required", "not_applicable"}:
                non_hard_formula_obligation_ids.add(obligation_id)

    required_paragraph_count = 0
    valid_required_paragraph_count = 0
    required_target_count = 0
    valid_target_count = 0
    required_slots = witnessed_slots = required_edges = witnessed_edges = 0
    invalid_keys: set[str] = set()
    blocked_keys: set[str] = set()
    for key, row in plan_rows.items():
        required = _required_targets(row)
        required["formula"] = tuple(
            obligation_id
            for obligation_id in required.get("formula", ())
            if obligation_id not in non_hard_formula_obligation_ids
        )
        target_count = sum(len(values) for values in required.values())
        if not target_count:
            continue
        required_paragraph_count += 1
        required_target_count += target_count
        required_slots += len(required.get("slot", ()))
        required_edges += len(required.get("edge", ()))
        assessment = assessment_rows.get(key)
        if assessment is None:
            reasons.append(f"required_paragraph_unassessed:{key[0]}:{key[1]}")
            invalid_keys.add(f"{key[0]}:{key[1]}")
            continue
        if not bool(assessment.get("valid")):
            invalid_keys.add(f"{key[0]}:{key[1]}")
            reasons.append(f"required_paragraph_invalid:{key[0]}:{key[1]}")
        else:
            trace_row = trace_rows.get(key)
            if trace_row is None or str(trace_row.get("terminal_state") or "") != "rendered":
                invalid_keys.add(f"{key[0]}:{key[1]}")
                reasons.append(f"required_paragraph_not_rendered:{key[0]}:{key[1]}")
            else:
                valid_required_paragraph_count += 1
        witnessed = {
            kind: set(_ids(values))
            for kind, values in (assessment.get("witnessed_by_kind") or {}).items()
        }
        for kind, values in required.items():
            valid_target_count += len(set(values) & witnessed.get(kind, set()))
        witnessed_slots += len(set(required.get("slot", ())) & witnessed.get("slot", set()))
        witnessed_edges += len(set(required.get("edge", ())) & witnessed.get("edge", set()))
        for missing_kind, missing_values in (assessment.get("missing_by_kind") or {}).items():
            if missing_values:
                reasons.append(
                    f"required_target_uncovered:{key[0]}:{key[1]}:{missing_kind}"
                )

    for raw in trace.get("rows") or ():
        if not isinstance(raw, dict):
            continue
        state = str(raw.get("terminal_state") or "")
        if state == "rendered_invalid":
            key = f"{raw.get('section_id') or ''}:{raw.get('paragraph_id') or ''}"
            invalid_keys.add(key)
        elif state == "blocked_representation":
            key = f"{raw.get('section_id') or ''}:{raw.get('paragraph_id') or ''}"
            blocked_keys.add(key)
    invalid_count = len(invalid_keys)
    blocked_count = len(blocked_keys)
    if invalid_count:
        reasons.append(f"rendered_invalid:{invalid_count}")
    if blocked_count:
        reasons.append(f"blocked_representation:{blocked_count}")
    if required_target_count and valid_target_count != required_target_count:
        reasons.append("required_target_coverage_incomplete")
    if required_slots != witnessed_slots:
        reasons.append("required_slot_coverage_incomplete")
    if required_edges != witnessed_edges:
        reasons.append("required_edge_coverage_incomplete")

    accepted_packages: set[str] = set()
    for section in formalization.get("sections") or ():
        if not isinstance(section, dict):
            continue
        for package in section.get("packages") or ():
            if (
                isinstance(package, dict)
                and str(package.get("package_id") or "").strip()
                and _formula_package_terminal_disposition(package) == "accepted"
            ):
                accepted_packages.add(str(package["package_id"]).strip())
    consumed_packages = {
        package_id
        for raw in trace.get("rows") or ()
        if isinstance(raw, dict) and str(raw.get("terminal_state") or "") == "rendered"
        for package_id in _ids(raw.get("accepted_formula_package_ids"))
    }
    body = str(candidate_markdown or "").strip()
    if not body:
        aggregate = writer.get("writer_aggregate") or {}
        parts = []
        for section in aggregate.get("sections") or ():
            if not isinstance(section, dict):
                continue
            text = str(section.get("section_markdown") or section.get("text") or "")
            if text.strip():
                parts.append(text)
        body = "\n\n".join(parts)
    if body:
        body_consumed: set[str] = set()
        for section in formalization.get("sections") or ():
            if not isinstance(section, dict):
                continue
            for package in section.get("packages") or ():
                if not isinstance(package, dict):
                    continue
                package_id = str(package.get("package_id") or "").strip()
                if package_id not in accepted_packages:
                    continue
                if _formula_package_uniquely_in_body(body, package):
                    body_consumed.add(package_id)
        # Assembled Candidate text is the consume authority.  A paragraph
        # transaction that still has ``$$`` while the published section lost
        # display math must not count as consumed.
        consumed_packages = body_consumed
    unresolved_required: list[str] = []
    for section in formalization.get("sections") or ():
        if not isinstance(section, dict):
            continue
        disposition = section.get("disposition")
        disposition_name = (
            str(disposition.get("disposition") or "")
            if isinstance(disposition, dict) else str(disposition or "")
        )
        typed_no_safe = disposition_name in {
            "not_applicable", "insufficient_binding", "paper_code_mismatch",
            "formalizer_empty", "declined_empty",
        }
        for truth in section.get("obligation_truths") or ():
            if not isinstance(truth, dict) or str(truth.get("expectation") or "required") != "required":
                continue
            obligation_id = str(truth.get("obligation_id") or "").strip()
            terminal = str(truth.get("terminal_disposition") or "").strip()
            if terminal in {"review_required", "not_applicable"}:
                continue
            if str(truth.get("outcome") or "") == "rendered":
                continue
            if not typed_no_safe:
                unresolved_required.append(obligation_id or str(section.get("section_id") or ""))
    unconsumed = accepted_packages - consumed_packages
    if unconsumed:
        reasons.append("formula_packages_unconsumed:" + ",".join(sorted(unconsumed)))
    if unresolved_required:
        reasons.append("required_formula_unresolved:" + ",".join(sorted(set(unresolved_required))))

    callback_request_items = [
        item for item in (
            *(callback.get("requests") or ()),
            *(callback.get("mechanism_requests") or ()),
        )
        if isinstance(item, dict)
    ]
    # Mechanism V2 requests have no mutable ``status`` field.  Their terminal
    # state is represented by the typed artifact map in the same bundle.  Do
    # not leave a fulfilled V2 request looking open merely because its request
    # record is intentionally immutable; doing so would make every successful
    # mechanism callback permanently block structural exit.
    fulfilled_mechanism_request_ids = {
        str(request_id).strip()
        for request_id in (callback.get("mechanism_artifacts") or {})
        if str(request_id).strip()
    }
    open_requests = [
        item for item in callback_request_items
        if not (
            str(item.get("request_id") or "").strip()
            and str(item.get("request_id") or "").strip()
            in fulfilled_mechanism_request_ids
            and (
                str(item.get("mechanism_id") or "").strip()
                or str(item.get("unresolved_kind") or "").strip()
            )
        )
        # V2 requests have no mutable section status: their presence in the
        # callback bundle means the unresolved owner is open.
        if not str(item.get("status") or "").strip()
        or str(item.get("status") or "").casefold() in {"open", "partial"}
    ]
    scoped_requests = [item for item in open_requests if _open_callback_scope(item)]
    if len(scoped_requests) != len(open_requests):
        reasons.append("callback_request_unscoped")
    # An open callback is a continuation opportunity, not a substitute for a
    # missing required transaction.  This explicit reason makes that policy
    # observable in execution_record.json.
    if open_requests and not scoped_requests:
        reasons.append("callback_request_has_no_unique_target")
    request_targets = []
    for item in scoped_requests:
        target_values = (
            item.get("mandatory_missing_slots")
            or item.get("remaining_slots")
            or item.get("missing_parts")
            or item.get("target_formula_obligation_ids")
            or item.get("target_story_node_ids")
            or item.get("target_concept_keys")
            or item.get("target_brief_ids")
            or item.get("target_clause_ids")
            or (item.get("missing_rhetorical_move"),)
        )
        # A target is paragraph/operation scoped, not merely a section plus a
        # generic slot name.  EBCAR exposed the previous coarse key: several
        # independent units in one section legitimately requested the same
        # ``transformation`` slot and were incorrectly treated as duplicate
        # callbacks.  Keep the duplicate guard, but include the stable owner
        # and semantic target identity; two requests for the same owner and
        # same target still fail closed.
        request_targets.append((
            str(item.get("mechanism_id") or ""),
            str(item.get("target_detail_id") or ""),
            str(item.get("unresolved_kind") or ""),
            str(item.get("section_id") or ""),
            str(item.get("argument_unit_id") or ""),
            str(item.get("missing_rhetorical_move") or ""),
            str(item.get("concept_key") or ""),
            tuple(sorted(_ids(target_values))),
            tuple(sorted(_ids(item.get("target_formula_obligation_ids")))),
            tuple(sorted(_ids(item.get("target_story_node_ids")))),
            tuple(sorted(_ids(item.get("target_concept_keys")))),
            tuple(sorted(_ids(item.get("target_brief_ids")))),
            tuple(sorted(_ids(item.get("target_clause_ids")))),
            tuple(sorted(_ids(item.get("target_operation_ids")))),
            tuple(sorted(_ids(item.get("target_atom_ids")))),
        ))
    if len(request_targets) != len(set(request_targets)):
        reasons.append("callback_request_targets_not_unique")

    unresolved_fields = [
        (str(raw.get("section_id") or ""), str(raw.get("paragraph_id") or ""), str(binding.get("field_name") or ""))
        for raw in trace.get("rows") or ()
        if isinstance(raw, dict)
        for binding in (raw.get("field_bindings") or ())
        if isinstance(binding, dict)
        and str(binding.get("status") or "").casefold() in {"partial", "unresolved"}
    ]
    if unresolved_fields and not scoped_requests:
        reasons.append("unresolved_field_without_callback_request")

    reasons = list(dict.fromkeys(reasons))
    return AuthoringStructuralExitV1(
        eligible=not reasons,
        reasons=tuple(reasons),
        plan_digest=plan_digest,
        trace_digest=trace_digest,
        assessment_digest=assessment_digest,
        candidate_digest=candidate_digest,
        required_paragraphs=required_paragraph_count,
        valid_required_paragraphs=valid_required_paragraph_count,
        required_targets=required_target_count,
        valid_targets=valid_target_count,
        required_slots=required_slots,
        witnessed_slots=witnessed_slots,
        required_edges=required_edges,
        witnessed_edges=witnessed_edges,
        invalid_paragraphs=invalid_count,
        blocked_representation=blocked_count,
        accepted_formula_packages=len(accepted_packages),
        consumed_formula_packages=len(accepted_packages & consumed_packages),
        unresolved_required_formula_obligations=tuple(sorted(set(unresolved_required))),
        open_callback_requests=len(open_requests),
        scoped_callback_requests=len(scoped_requests),
    )


def canonical_fact_fingerprint(fact: Any) -> str:
    """Stable fingerprint for cross-obligation dedup (4B)."""

    identity = str(getattr(fact, "canonical_identity", "") or "").strip()
    if identity.startswith("sha256:"):
        return identity
    payload = {
        "subject": str(getattr(fact, "subject", "") or ""),
        "predicate": str(getattr(fact, "predicate", "") or ""),
        "object": str(getattr(fact, "object", "") or ""),
        "spans": sorted(
            str(item) for item in (getattr(fact, "direct_span_ids", ()) or ())
            if str(item).strip()
        ),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


def callback_semantic_digest(
    *,
    new_fingerprints: tuple[str, ...] | list[str] = (),
    satisfied_slots: tuple[str, ...] | list[str] = (),
    remaining_slots: tuple[str, ...] | list[str] = (),
    concept_keys: tuple[str, ...] | list[str] = (),
    affected_sections: tuple[str, ...] | list[str] = (),
) -> str:
    """Digest of the authoring-relevant semantic delta for one callback round."""

    payload = {
        "fingerprints": sorted(str(item) for item in new_fingerprints if str(item).strip()),
        "satisfied": list(dict.fromkeys(str(item) for item in satisfied_slots if str(item).strip())),
        "remaining": list(dict.fromkeys(str(item) for item in remaining_slots if str(item).strip())),
        "concepts": sorted(str(item) for item in concept_keys if str(item).strip()),
        "sections": sorted(str(item) for item in affected_sections if str(item).strip()),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode()).hexdigest()


def mandatory_slots_from_request(request: WritingResearchRequestV1) -> tuple[str, ...]:
    """Derive mandatory open slots from the request contract.

    After a partial round, only ``remaining_slots`` stay in scope.
    """

    remaining = [
        str(item).strip()
        for item in (request.remaining_slots or ())
        if str(item).strip()
    ]
    if remaining:
        return tuple(dict.fromkeys(remaining))
    explicit = [
        str(item).strip()
        for item in (request.mandatory_missing_slots or ())
        if str(item).strip()
    ]
    if explicit:
        return tuple(dict.fromkeys(explicit))
    inferred: list[str] = []
    for part in (request.missing_parts or ()):
        lowered = str(part).casefold()
        if any(token in lowered for token in ("formula", "equation", "derivation", "loss")):
            inferred.append("formula")
        elif any(token in lowered for token in ("mask", "relation", "dataflow", "edge")):
            inferred.append("relation")
        elif any(token in lowered for token in ("input", "operand", "source")):
            inferred.append("input")
        elif any(token in lowered for token in ("output", "return", "downstream")):
            inferred.append("output")
        elif any(token in lowered for token in ("condition", "qualifier", "when")):
            inferred.append("condition")
        else:
            inferred.append("transformation")
    lane = str(request.required_authority_lane or "")
    if lane == "formal_derivation" and "formula" not in inferred:
        inferred.append("formula")
    return tuple(dict.fromkeys(inferred))


def evaluate_mandatory_slot_coverage(
    request: WritingResearchRequestV1,
    *,
    new_fact_ids: tuple[str, ...] | list[str] = (),
    new_fingerprints: tuple[str, ...] | list[str] = (),
    baseline_fingerprints: tuple[str, ...] | list[str] = (),
    concept_judgment: dict[str, list[str]] | None = None,
    lane_fulfilled: bool = False,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return satisfied and remaining mandatory slots for one callback."""

    mandatory = mandatory_slots_from_request(request)
    if not mandatory:
        return (), ()
    satisfied: list[str] = []
    remaining = list(mandatory)
    concept_judgment = concept_judgment or {}
    target = str(request.concept_key or "").strip()
    gained = {
        str(item).strip() for item in (new_fingerprints or ()) if str(item).strip()
    } - {
        str(item).strip() for item in (baseline_fingerprints or ()) if str(item).strip()
    }
    has_canonical_gain = (
        bool(gained)
        if (new_fingerprints or baseline_fingerprints)
        else bool(new_fact_ids)
    )
    if target and concept_judgment.get(target):
        for slot in ("representation", "transformation", "input"):
            if slot in remaining:
                satisfied.append(slot)
                remaining.remove(slot)
    if has_canonical_gain:
        if "relation" in remaining:
            satisfied.append("relation")
            remaining.remove("relation")
        if "transformation" in remaining:
            satisfied.append("transformation")
            remaining.remove("transformation")
    if "formula" in remaining and lane_fulfilled:
        satisfied.append("formula")
        remaining.remove("formula")
    return tuple(satisfied), tuple(remaining)


def authoring_semantic_delta_changed(
    *,
    previous_digests: set[str] | frozenset[str],
    semantic_digest: str,
    new_fingerprint_count: int,
    satisfied_slots: tuple[str, ...] | list[str] = (),
    baseline_context_digest: str = "",
    current_context_digest: str = "",
    baseline_unresolved_count: int | None = None,
    current_unresolved_count: int | None = None,
    baseline_core_detail_count: int | None = None,
    current_core_detail_count: int | None = None,
    target_gaps_before: tuple[str, ...] | list[str] = (),
    target_gaps_after: tuple[str, ...] | list[str] = (),
    new_source_operation_ids: tuple[str, ...] | list[str] = (),
    new_detail_ids: tuple[str, ...] | list[str] = (),
) -> bool:
    """True only when this round adds a new authoring semantic digest.

    Legacy callers use fingerprints/slots.  Unified callers additionally pass
    context quality counters and owner ids; for that lane a changed digest by
    itself is *not* progress.  At least one source/detail/gap/readiness
    improvement must accompany it.
    """

    digest = str(semantic_digest or "").strip()
    if digest and digest in previous_digests:
        return False
    unified_quality_fields = any(
        value is not None
        for value in (
            baseline_unresolved_count,
            current_unresolved_count,
            baseline_core_detail_count,
            current_core_detail_count,
        )
    ) or bool(
        baseline_context_digest
        or current_context_digest
        or new_source_operation_ids
        or new_detail_ids
        or target_gaps_before
        or target_gaps_after
    )
    if not unified_quality_fields:
        return bool(new_fingerprint_count or satisfied_slots)
    context_changed = bool(
        baseline_context_digest
        and current_context_digest
        and baseline_context_digest != current_context_digest
    )
    unresolved_improved = (
        baseline_unresolved_count is not None
        and current_unresolved_count is not None
        and current_unresolved_count < baseline_unresolved_count
    )
    core_improved = (
        baseline_core_detail_count is not None
        and current_core_detail_count is not None
        and current_core_detail_count > baseline_core_detail_count
    )
    gap_improved = bool(
        target_gaps_before
        and len(set(target_gaps_after)) < len(set(target_gaps_before))
    )
    owner_gain = bool(new_source_operation_ids or new_detail_ids)
    explicit_semantic_gain = bool(new_fingerprint_count or satisfied_slots)
    return bool(
        digest
        and context_changed
        and (unresolved_improved or core_improved or gap_improved or owner_gain or explicit_semantic_gain)
    )


def enrich_callback_request_semantics(
    request: WritingResearchRequestV1,
    *,
    graph: SectionArgumentGraphV1 | Any | None = None,
    concept_bindings: dict[str, Any] | None = None,
    baseline_facts: tuple[Any, ...] | tuple = (),
) -> WritingResearchRequestV1:
    """Populate WP4 4B binding fields on a Writer-emitted request."""

    concept_bindings = concept_bindings or {}
    target_concept_keys: list[str] = []
    if str(request.concept_key or "").strip():
        target_concept_keys.append(str(request.concept_key).strip())
    target_story_node_ids: list[str] = []
    target_formula_obligation_ids: list[str] = []
    excluded_audit: list[str] = []
    if graph is not None:
        target_story_node_ids.extend(
            str(item) for item in (getattr(graph, "story_node_ids", ()) or ())
        )
        target_formula_obligation_ids.extend(
            str(item) for item in (getattr(graph, "formula_obligation_ids", ()) or ())
        )
        excluded_audit.extend(
            str(item) for item in (getattr(graph, "audit_only_concept_keys", ()) or ())
        )
    mandatory_missing_slots = mandatory_slots_from_request(request)
    baseline_claim_ids: list[str] = list(request.current_known_facts or ())
    fingerprints = tuple(dict.fromkeys(
        canonical_fact_fingerprint(fact)
        for fact in baseline_facts
        if canonical_fact_fingerprint(fact)
    ))
    payload = request.model_dump(mode="python")
    payload.update({
        "target_story_node_ids": tuple(dict.fromkeys(target_story_node_ids)),
        "target_concept_keys": tuple(dict.fromkeys(target_concept_keys)),
        "target_formula_obligation_ids": tuple(dict.fromkeys(target_formula_obligation_ids)),
        "mandatory_missing_slots": tuple(mandatory_missing_slots),
        "baseline_claim_ids": tuple(dict.fromkeys(
            str(item) for item in baseline_claim_ids if str(item).strip()
        )),
        "baseline_fact_fingerprints": fingerprints,
        "excluded_audit_concept_keys": tuple(dict.fromkeys(excluded_audit)),
        "content_digest": "",
    })
    return WritingResearchRequestV1.model_validate(payload)


def build_mechanism_research_request_v2(
    *,
    request_id: str,
    mechanism_id: str,
    exact_question: str,
    unresolved_kind: str,
    baseline_context_digest: str,
    target_detail_id: str = "",
    candidate_symbols_or_terms: tuple[str, ...] | list[str] = (),
    baseline_span_ids: tuple[str, ...] | list[str] = (),
    target_operation_ids: tuple[str, ...] | list[str] = (),
    target_atom_ids: tuple[str, ...] | list[str] = (),
    affected_section_ids: tuple[str, ...] | list[str] = (),
    affected_paragraph_ids: tuple[str, ...] | list[str] = (),
) -> MechanismResearchRequestV2:
    """Construct the canonical mechanism/detail callback request.

    This helper is intentionally explicit about the owner and baseline.  It is
    used by production adapters as well as tests so a section-scoped request
    cannot be silently promoted to a mechanism callback.
    """

    return MechanismResearchRequestV2(
        request_id=request_id,
        mechanism_id=mechanism_id,
        target_detail_id=target_detail_id,
        unresolved_kind=unresolved_kind,  # type: ignore[arg-type]
        exact_question=exact_question,
        candidate_symbols_or_terms=tuple(candidate_symbols_or_terms),
        baseline_span_ids=tuple(baseline_span_ids),
        baseline_context_digest=baseline_context_digest,
        target_operation_ids=tuple(target_operation_ids),
        target_atom_ids=tuple(target_atom_ids),
        affected_section_ids=tuple(affected_section_ids),
        affected_paragraph_ids=tuple(affected_paragraph_ids),
    )


__all__ = [
    "AuthoringStructuralExitV1",
    "authoring_semantic_delta_changed",
    "callback_semantic_digest",
    "canonical_fact_fingerprint",
    "build_mechanism_research_request_v2",
    "enrich_callback_request_semantics",
    "evaluate_authoring_structural_exit",
    "evaluate_mandatory_slot_coverage",
    "mandatory_slots_from_request",
]
