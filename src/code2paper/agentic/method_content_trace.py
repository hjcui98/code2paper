"""Source-to-render trace for Method authoring quality diagnostics.

The trace is deliberately a ledger of identifiers and terminal states.  It
does not copy source prose into a new authority channel and it cannot promote
Candidate material to Verified.  Its purpose is to answer, for every planned
paragraph, where the source binding was found, whether a formula package was
consumed, and which downstream validation state was reached.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


TraceTerminalStateV1 = Literal[
    "not_discovered",
    "discovered_partial",
    "discovered_bound",
    "planned",
    "rendered",
    "rendered_invalid",
    "blocked_representation",
    "intent_code_mismatch",
    "deferred_with_reason",
    "context_lost",
    "writer_omitted",
    "budget_exhausted",
    "validated",
]

_TRACE_STATES: tuple[str, ...] = (
    "not_discovered",
    "discovered_partial",
    "discovered_bound",
    "planned",
    "rendered",
    "rendered_invalid",
    "blocked_representation",
    "intent_code_mismatch",
    "deferred_with_reason",
    "context_lost",
    "writer_omitted",
    "budget_exhausted",
    "validated",
)


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _ids(values: Any) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, Mapping)) or values is None:
        return ()
    if not isinstance(values, (list, tuple, set)):
        try:
            values = tuple(values)
        except TypeError:
            return ()
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _transaction_has_valid_witnesses(
    item: Mapping[str, Any],
    *,
    required_targets: Mapping[str, Any] | None = None,
    plan_row: Mapping[str, Any] | None = None,
    formula_routes: Mapping[str, Any] | None = None,
    required_anchors: Mapping[tuple[str, str], tuple[str, ...]] | None = None,
) -> bool:
    """Return whether one persisted paragraph transaction has valid witnesses.

    The Writer boundary remains the authority for rejecting malformed
    responses.  The trace is intentionally independent and re-checks the
    persisted transaction so an accepted section cannot be counted as
    rendered when it merely contains a paragraph id or self-reported ids.
    Overview paragraphs may legitimately have no ids; once a transaction
    declares a facet/slot/edge/formula/claim/equation id, every declaration
    must have one unique exact witness in that paragraph body.
    """

    # Use the same pure contract as the Writer boundary.  The legacy body
    # below remains as a defensive fallback for historical artifacts that do
    # not deserialize through the current model.
    try:
        from code2paper.agentic.publication_transaction_contract import (
            assess_paragraph_transaction,
        )

        normalized_plan_row = dict(plan_row or {})
        if not normalized_plan_row:
            normalized_plan_row = {
                "required_detail_ids": tuple((required_targets or {}).get("detail", ())),
                "required_facet_ids": tuple((required_targets or {}).get("facet", ())),
                "required_publication_slot_ids": tuple((required_targets or {}).get("slot", ())),
                "required_field_candidate_ids": tuple((required_targets or {}).get("field", ())),
                "required_edge_ids": tuple((required_targets or {}).get("edge", ())),
                "formula_obligation_ids": tuple((required_targets or {}).get("formula", ())),
            }
        return assess_paragraph_transaction(
            item,
            plan_row=normalized_plan_row,
            formula_routes=formula_routes,
            required_anchors=required_anchors,
        ).valid
    except (ImportError, TypeError, ValueError, AttributeError):
        pass
    body = str(item.get("paragraph_markdown") or "").strip()
    if not body:
        return False
    witnesses = item.get("witnesses") or ()
    witness_keys: set[tuple[str, str]] = set()
    witness_texts: dict[tuple[str, str], str] = {}
    for raw in witnesses:
        if not isinstance(raw, Mapping):
            return False
        kind = str(raw.get("witness_kind") or raw.get("kind") or "").strip()
        target = str(raw.get("target_id") or "").strip()
        exact = str(raw.get("exact_text") or "")
        if not kind or not target or not exact:
            return False
        key = (kind, target)
        if key in witness_keys or body.count(exact) != 1:
            return False
        witness_keys.add(key)
        witness_texts[key] = exact
    for field_name, kind in (
        ("rendered_from_facet_ids", "facet"),
        ("rendered_field_candidate_ids", "field"),
        ("rendered_slot_ids", "slot"),
        ("rendered_edge_ids", "edge"),
        ("used_formula_package_ids", "formula"),
        ("used_claim_ids", "claim"),
        ("used_equation_ids", "equation"),
    ):
        for value in _ids(item.get(field_name)):
            if (kind, value) not in witness_keys:
                return False
    # A transaction with a substantive body but no self-reported ids is not
    # enough for a paragraph whose Architect contract contains mandatory
    # facets/slots/edges.  Formula obligations may be witnessed by either the
    # obligation id or an accepted package id; the latter is what the
    # Formalizer/Writer contract normally exposes.
    for kind, values in (required_targets or {}).items():
        required = tuple(value for value in values if str(value).strip())
        if not required:
            continue
        witnessed_targets = {
            target for witness_kind, target in witness_keys if witness_kind == kind
        }
        if kind == "formula":
            declared = set(_ids(item.get("used_formula_package_ids")))
            if not (witnessed_targets & (set(required) | declared)):
                return False
        elif not set(required).issubset(witnessed_targets):
            return False
    return True


class MethodContentTraceRowV1(BaseModel):
    """One closed source-to-render ledger row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content_unit_id: str
    source_story_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_authority_lane: str = ""
    field_bindings: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    required_field_candidate_ids: tuple[str, ...] = Field(default_factory=tuple)
    semantic_frame_id: str = ""
    ordered_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_publication_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_edge_ids: tuple[str, ...] = Field(default_factory=tuple)
    argument_unit_id: str = ""
    section_id: str = ""
    paragraph_id: str = ""
    formula_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    accepted_formula_package_ids: tuple[str, ...] = Field(default_factory=tuple)
    writer_rendered_span_refs: tuple[str, ...] = Field(default_factory=tuple)
    writer_rendered_field_candidate_refs: tuple[str, ...] = Field(default_factory=tuple)
    writer_rendered_edge_refs: tuple[str, ...] = Field(default_factory=tuple)
    final_validation_refs: tuple[str, ...] = Field(default_factory=tuple)
    terminal_state: TraceTerminalStateV1 = "planned"
    owner: str = ""
    stop_reason: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodContentTraceRowV1":
        object.__setattr__(
            self,
            "content_digest",
            _digest(self.model_dump(mode="json", exclude={"content_digest"})),
        )
        return self


class MethodContentTraceV1(BaseModel):
    """Content-addressed source-to-render ledger for one authoring run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    rows: tuple[MethodContentTraceRowV1, ...] = Field(default_factory=tuple)
    summary: dict[str, int] = Field(default_factory=dict)
    # Digest of the paragraph transaction assessment sidecar used to decide
    # whether a row is truly rendered.  Historical traces may omit it and
    # remain readable, but current callback authorization requires the link.
    transaction_assessment_digest: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodContentTraceV1":
        paragraph_ids = {
            row.paragraph_id for row in self.rows if row.paragraph_id
        }
        rendered_paragraph_ids = {
            row.paragraph_id
            for row in self.rows
            if row.paragraph_id and row.terminal_state == "rendered"
        }
        rendered_slot_ids = {
            slot_id
            for row in self.rows
            if row.terminal_state == "rendered"
            for slot_id in row.required_publication_slot_ids
        }
        planned_slot_ids = {
            slot_id
            for row in self.rows
            for slot_id in row.required_publication_slot_ids
        }
        rendered_field_ids = {
            field_id
            for row in self.rows
            if row.terminal_state == "rendered"
            for field_id in row.writer_rendered_field_candidate_refs
        }
        planned_edge_ids = {
            edge_id
            for row in self.rows
            for edge_id in row.required_edge_ids
        }
        rendered_edge_ids = {
            edge_id
            for row in self.rows
            if row.terminal_state == "rendered"
            for edge_id in row.writer_rendered_edge_refs
        }
        story_node_ids = {
            node_id
            for row in self.rows
            for node_id in row.source_story_node_ids
        }
        rendered_story_node_ids = {
            node_id
            for row in self.rows
            if row.terminal_state == "rendered"
            for node_id in row.source_story_node_ids
        }
        formula_obligation_ids = {
            obligation_id
            for row in self.rows
            for obligation_id in row.formula_obligation_ids
        }
        rendered_formula_obligation_ids = {
            obligation_id
            for row in self.rows
            if row.terminal_state == "rendered"
            for obligation_id in row.formula_obligation_ids
        }
        consumed_formula_package_ids = {
            package_id
            for row in self.rows
            for package_id in row.accepted_formula_package_ids
        }
        formula_consumer_counts: dict[str, int] = {}
        for row in self.rows:
            if row.terminal_state != "rendered":
                continue
            for obligation_id in row.formula_obligation_ids:
                formula_consumer_counts[obligation_id] = formula_consumer_counts.get(obligation_id, 0) + 1
        field_bound_rows = sum(
            any(binding.get("status") in {"entailed", "partial"}
                for binding in row.field_bindings)
            for row in self.rows
        )
        condition_witness_rows = sum(
            any(
                str(binding.get("field_name") or "") in {"condition", "conditions"}
                and str(binding.get("polarity") or "unknown") != "unknown"
                for binding in row.field_bindings
            )
            for row in self.rows
        )
        summary = {
            "rows": len(self.rows),
            "sections": len({row.section_id for row in self.rows if row.section_id}),
            "planned_paragraphs": len(paragraph_ids),
            "rendered_paragraphs": len(rendered_paragraph_ids),
            "planned_story_nodes": len(story_node_ids),
            "rendered_story_nodes": len(rendered_story_node_ids),
            "planned_slots": len(planned_slot_ids),
            "rendered_slots": len(rendered_slot_ids),
            "rendered_field_candidates": len(rendered_field_ids),
            "planned_edges": len(planned_edge_ids),
            "rendered_edges": len(planned_edge_ids & rendered_edge_ids),
            "formula_obligations": len(formula_obligation_ids),
            "rendered_formula_obligations": len(rendered_formula_obligation_ids),
            "consumed_formula_packages": len(consumed_formula_package_ids),
            "duplicate_formula_consumers": sum(
                count - 1 for count in formula_consumer_counts.values() if count > 1
            ),
            "field_bound_rows": field_bound_rows,
            "condition_polarity_witness_rows": condition_witness_rows,
            **{
                state: sum(row.terminal_state == state for row in self.rows)
                for state in _TRACE_STATES
            },
        }
        object.__setattr__(self, "summary", summary)
        object.__setattr__(
            self,
            "content_digest",
            _digest(self.model_dump(mode="json", exclude={"content_digest"})),
        )
        return self


def _load_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows_by_id(payload: Mapping[str, Any], key: str, id_key: str) -> dict[str, dict[str, Any]]:
    values = payload.get(key) or ()
    if isinstance(values, Mapping):
        values = values.values()
    return {
        str(item.get(id_key) or ""): item
        for item in values
        if isinstance(item, Mapping) and str(item.get(id_key) or "").strip()
    }


def build_method_content_trace_from_artifact_paths(
    artifact_paths: Mapping[str, str],
) -> MethodContentTraceV1:
    """Build a trace from persisted product artifacts.

    Missing optional artifacts yield explicit non-terminal rows rather than a
    guessed success.  All IDs are copied from closed artifacts; no source text
    or model-generated prose is synthesized here.
    """

    plan = _load_json(artifact_paths.get("method_section_plan_v2"))
    facets_payload = _load_json(artifact_paths.get("method_argument_facets_v1"))
    alignments_payload = _load_json(artifact_paths.get("facet_evidence_alignments_v1"))
    policies_payload = _load_json(artifact_paths.get("candidate_facet_policies_v1"))
    formalization = _load_json(artifact_paths.get("formalization_section_results_v1"))
    writer = _load_json(artifact_paths.get("publication_writer_result_v1"))
    validation = _load_json(artifact_paths.get("publication_quality_report_v1"))
    transaction_assessments = _load_json(
        artifact_paths.get("publication_paragraph_transaction_assessments_v1")
    )
    assessment_by_key = {
        (
            str(item.get("section_id") or "").strip(),
            str(item.get("paragraph_id") or "").strip(),
        ): item
        for item in (transaction_assessments.get("assessments") or ())
        if isinstance(item, Mapping)
        and str(item.get("paragraph_id") or "").strip()
    }
    facets_by_id = _rows_by_id(facets_payload, "facets", "facet_id")
    alignments_by_id = _rows_by_id(alignments_payload, "alignments", "facet_id")
    policies_by_id = _rows_by_id(policies_payload, "policies", "facet_id")
    formalization_by_section = {
        str(item.get("section_id") or ""): item
        for item in formalization.get("sections") or ()
        if isinstance(item, Mapping)
    }
    writer_sections = {
        str(item.get("section_id") or ""): item
        for item in writer.get("section_results") or ()
        if isinstance(item, Mapping)
    }
    quality_refs = tuple(
        str(value)
        for value in (
            artifact_paths.get("publication_quality_report_v1"),
            artifact_paths.get("agentic_text_evidence_validation"),
        )
        if str(value or "").strip()
    )
    rows: list[MethodContentTraceRowV1] = []
    units_by_id = _rows_by_id(
        {"units": plan.get("argument_units") or ()}, "units", "argument_unit_id"
    )
    for section in plan.get("sections") or ():
        if not isinstance(section, Mapping):
            continue
        section_id = str(section.get("section_id") or "")
        section_writer = writer_sections.get(section_id, {})
        raw_writer_output = section_writer.get("output")
        writer_output = raw_writer_output if isinstance(raw_writer_output, Mapping) else {}
        section_formalization = formalization_by_section.get(section_id, {})
        packages = section_formalization.get("packages") or ()
        package_ids = _ids(
            item.get("package_id") or item.get("formula_package_id")
            for item in packages
            if isinstance(item, Mapping)
        )
        paragraph_transactions = {
            str(item.get("paragraph_id") or ""): item
            for item in (writer_output.get("paragraphs") or ())
            if isinstance(item, Mapping) and str(item.get("paragraph_id") or "").strip()
        }
        plan_by_id = {
            str(item.get("paragraph_id") or ""): item
            for item in (section.get("paragraphs") or ())
            if isinstance(item, Mapping)
            and str(item.get("paragraph_id") or "").strip()
        }

        def _required_targets(paragraph_id: str) -> dict[str, tuple[str, ...]]:
            row = plan_by_id.get(paragraph_id, {})
            return {
                "detail": _ids(row.get("required_detail_ids")),
                "facet": _ids(row.get("required_facet_ids")),
                "field": _ids(row.get("required_field_candidate_ids")),
                "slot": _ids(
                    row.get("required_publication_slot_ids")
                    if "required_publication_slot_ids" in row
                    else row.get("ordered_semantic_slot_ids")
                ),
                "edge": _ids(row.get("required_edge_ids")),
                "formula": _ids(row.get("formula_obligation_ids")),
            }

        def _required_anchors(paragraph_id: str) -> dict[tuple[str, str], tuple[str, ...]]:
            from code2paper.agentic.publication_transaction_contract import (
                required_anchors_from_plan_row,
            )
            return required_anchors_from_plan_row(plan_by_id.get(paragraph_id, {}))

        formula_routes: dict[str, dict[str, Any]] = {}
        from code2paper.agentic.publication_transaction_contract import (
            _formula_package_terminal_disposition,
        )
        has_explicit_package_routes = any(
            isinstance(package, Mapping)
            and (
                str(package.get("obligation_id") or "").strip()
                or bool(package.get("satisfied_obligation_ids"))
            )
            for package in packages
        )
        for obligation in (section_formalization.get("formula_obligations") or ()):
            if not isinstance(obligation, Mapping):
                continue
            obligation_id = str(obligation.get("obligation_id") or "").strip()
            if not obligation_id:
                continue
            matches = [
                package for package in packages
                if isinstance(package, Mapping)
                and obligation_id in {
                    *(
                        str(item).strip()
                        for item in (package.get("satisfied_obligation_ids") or ())
                        if str(item).strip()
                    ),
                    *(
                        [str(package.get("obligation_id") or "").strip()]
                        if str(package.get("obligation_id") or "").strip()
                        else []
                    ),
                }
            ]
            if not matches and not has_explicit_package_routes:
                matches = [
                    package for package in packages
                    if isinstance(package, Mapping)
                    and (
                        not _ids(obligation.get("facet_ids"))
                        or set(_ids(obligation.get("facet_ids"))).intersection(
                            set(_ids(package.get("bound_facet_ids")))
                        )
                    )
                ]
            formula_routes[obligation_id] = {
                "package_ids": tuple(
                    str(package.get("package_id") or "")
                    for package in matches
                    if str(package.get("package_id") or "").strip()
                ),
                "latex": str(
                    matches[0].get("markdown_block") or matches[0].get("latex") or ""
                ) if matches else "",
                "terminal_disposition": (
                    _formula_package_terminal_disposition(matches[0])
                    if len(matches) == 1
                    else "failed"
                ),
            }

        # When paragraph transactions are present, only their exact
        # witness-bearing ids count as rendered.  Aggregate self-reported ids
        # remain a frozen-replay fallback for pre-transaction artifacts.  A
        # transaction that contains substantive text but omits the required
        # witness is retained as ``rendered_invalid`` below; it must not look
        # like a successfully rendered paragraph merely because its
        # paragraph_id was present.
        transaction_validity: dict[str, bool] = {}
        invalid_transaction_ids: set[str] = set()
        if paragraph_transactions:
            rendered_paragraphs = set()
            rendered_slots = {
                value for paragraph_id, item in paragraph_transactions.items()
                if (
                    bool(assessment_by_key.get((section_id, paragraph_id), {}).get("valid"))
                    if (section_id, paragraph_id) in assessment_by_key
                    else _transaction_has_valid_witnesses(
                        item,
                        required_targets=_required_targets(paragraph_id),
                        plan_row=plan_by_id.get(paragraph_id, {}),
                        formula_routes=formula_routes,
                        required_anchors=_required_anchors(paragraph_id),
                    )
                )
                for value in _ids(item.get("rendered_slot_ids"))
            }
            rendered_edges = {
                value for paragraph_id, item in paragraph_transactions.items()
                if (
                    bool(assessment_by_key.get((section_id, paragraph_id), {}).get("valid"))
                    if (section_id, paragraph_id) in assessment_by_key
                    else _transaction_has_valid_witnesses(
                        item,
                        required_targets=_required_targets(paragraph_id),
                        plan_row=plan_by_id.get(paragraph_id, {}),
                        formula_routes=formula_routes,
                        required_anchors=_required_anchors(paragraph_id),
                    )
                )
                for value in _ids(item.get("rendered_edge_ids"))
            }
            used_packages = {
                value for paragraph_id, item in paragraph_transactions.items()
                if (
                    bool(assessment_by_key.get((section_id, paragraph_id), {}).get("valid"))
                    if (section_id, paragraph_id) in assessment_by_key
                    else _transaction_has_valid_witnesses(
                        item,
                        required_targets=_required_targets(paragraph_id),
                        plan_row=plan_by_id.get(paragraph_id, {}),
                        formula_routes=formula_routes,
                        required_anchors=_required_anchors(paragraph_id),
                    )
                )
                for value in _ids(item.get("used_formula_package_ids"))
            }
            writer_claim_refs = {
                value for paragraph_id, item in paragraph_transactions.items()
                if (
                    bool(assessment_by_key.get((section_id, paragraph_id), {}).get("valid"))
                    if (section_id, paragraph_id) in assessment_by_key
                    else _transaction_has_valid_witnesses(
                        item,
                        required_targets=_required_targets(paragraph_id),
                        plan_row=plan_by_id.get(paragraph_id, {}),
                        formula_routes=formula_routes,
                        required_anchors=_required_anchors(paragraph_id),
                    )
                )
                for value in _ids(item.get("used_claim_ids"))
            }
            for paragraph_id, item in paragraph_transactions.items():
                assessment_row = assessment_by_key.get((section_id, paragraph_id))
                valid = (
                    bool(assessment_row.get("valid"))
                    if assessment_row is not None
                    else _transaction_has_valid_witnesses(
                        item,
                        required_targets=_required_targets(paragraph_id),
                        plan_row=plan_by_id.get(paragraph_id, {}),
                        formula_routes=formula_routes,
                        required_anchors=_required_anchors(paragraph_id),
                    )
                )
                transaction_validity[paragraph_id] = valid
                if valid:
                    rendered_paragraphs.add(paragraph_id)
                elif str(item.get("paragraph_markdown") or "").strip():
                    invalid_transaction_ids.add(paragraph_id)
        else:
            rendered_paragraphs = set(_ids(writer_output.get("rendered_paragraph_ids", ())))
            rendered_slots = set(_ids(writer_output.get("rendered_slot_ids", ())))
            rendered_edges = set(_ids(writer_output.get("rendered_edge_ids", ())))
            used_packages = set(_ids(writer_output.get("used_formula_package_ids", ())))
            writer_claim_refs = set(_ids(writer_output.get("used_claim_ids", ())))
        accepted = bool(section_writer.get("accepted"))
        for paragraph_index, paragraph in enumerate(section.get("paragraphs") or ()):
            if not isinstance(paragraph, Mapping):
                continue
            paragraph_id = str(paragraph.get("paragraph_id") or "")
            unit_ids = _ids(paragraph.get("argument_unit_ids"))
            facet_ids = _ids(paragraph.get("required_facet_ids"))
            # Do not inherit every section facet onto the first paragraph.
            # A missing placement is a traceable authoring defect, not proof
            # that the first paragraph rendered the entire section.
            slot_ids = _ids(paragraph.get("ordered_semantic_slot_ids"))
            publication_slot_ids = _ids(
                paragraph.get("required_publication_slot_ids")
                if "required_publication_slot_ids" in paragraph
                else paragraph.get("ordered_semantic_slot_ids")
            )
            field_candidate_ids = _ids(paragraph.get("required_field_candidate_ids"))
            edge_ids = _ids(paragraph.get("required_edge_ids"))
            obligation_ids = _ids(paragraph.get("formula_obligation_ids"))
            unit_id = unit_ids[0] if unit_ids else ""
            unit = units_by_id.get(unit_id, {})
            semantic_frame = unit.get("semantic_frame") or {}
            semantic_frame_id = str(semantic_frame.get("frame_id") or "")
            source_facets = []
            field_bindings: list[dict[str, Any]] = []
            statuses: list[str] = []
            lanes: list[str] = []
            for facet_id in facet_ids:
                facet = facets_by_id.get(facet_id, {})
                alignment = alignments_by_id.get(facet_id, {})
                policy = policies_by_id.get(facet_id, {})
                source_facets.append(facet_id)
                statuses.append(str(alignment.get("status") or policy.get("status") or "unresolved"))
                lanes.append(str(policy.get("authority_lane") or facet.get("authority_lane") or ""))
                field_bindings.extend(
                    item for item in (alignment.get("field_bindings") or ()) if isinstance(item, Mapping)
                )
            state: TraceTerminalStateV1
            # A rejected section can still contain a substantive Writer body.
            # When its paragraph transaction omits required exact witnesses,
            # retain that distinction as ``rendered_invalid`` rather than
            # collapsing it into a representation block.  The body remains
            # diagnostic-only: it contributes no rendered ids, formula
            # consumption, callback scope, or structural-exit credit.
            if paragraph_transactions and paragraph_id in invalid_transaction_ids:
                state = "rendered_invalid"
            elif rendered_paragraphs and paragraph_id in rendered_paragraphs:
                state = "rendered"
            elif not accepted:
                # Section checkpoint failure must not erase an independently
                # valid sibling paragraph.  Only a paragraph with no valid
                # transaction remains a representation block; the section
                # itself is still fail-closed at the structural gate.
                state = "blocked_representation"
            elif rendered_slots and set(slot_ids).intersection(rendered_slots):
                state = "rendered"
            elif rendered_edges and set(edge_ids).intersection(rendered_edges):
                state = "rendered"
            elif any(value == "mismatch" for value in statuses):
                state = "intent_code_mismatch"
            elif any(value in {"unresolved", "partial"} for value in statuses):
                state = "discovered_partial"
            elif paragraph_id:
                state = "deferred_with_reason"
            else:
                state = "planned"
            if obligation_ids:
                if has_explicit_package_routes:
                    consumed = tuple(
                        str(package.get("package_id") or "")
                        for package in packages
                        if isinstance(package, Mapping)
                        and str(package.get("package_id") or "") in used_packages
                        and bool(
                            set(obligation_ids).intersection(
                                {
                                    *(
                                        str(item).strip()
                                        for item in (package.get("satisfied_obligation_ids") or ())
                                        if str(item).strip()
                                    ),
                                    *(
                                        [str(package.get("obligation_id") or "").strip()]
                                        if str(package.get("obligation_id") or "").strip()
                                        else []
                                    ),
                                }
                            )
                        )
                        and str(package.get("consumer_paragraph_id") or "").strip() == paragraph_id
                    )
                else:
                    consumed = tuple(
                        package_id for package_id in package_ids if package_id in used_packages
                    )
            else:
                consumed = ()
            if obligation_ids and package_ids and not consumed and state == "rendered":
                state = "rendered_invalid"
            rows.append(MethodContentTraceRowV1(
                content_unit_id=f"{section_id}:{paragraph_id or unit_id}",
                source_story_node_ids=_ids(section.get("story_node_ids")),
                source_facet_ids=tuple(source_facets),
                source_authority_lane=next((lane for lane in lanes if lane), ""),
                field_bindings=tuple(dict(item) for item in field_bindings),
                required_field_candidate_ids=field_candidate_ids,
                semantic_frame_id=semantic_frame_id,
                ordered_slot_ids=slot_ids,
                required_publication_slot_ids=publication_slot_ids,
                required_edge_ids=edge_ids,
                argument_unit_id=unit_id,
                section_id=section_id,
                paragraph_id=paragraph_id,
                formula_obligation_ids=obligation_ids,
                accepted_formula_package_ids=consumed,
                writer_rendered_span_refs=tuple(
                    sorted(writer_claim_refs)
                ),
                writer_rendered_field_candidate_refs=tuple(
                    sorted(
                        set(field_candidate_ids)
                        & set(_ids(
                            paragraph_transactions.get(paragraph_id, {}).get(
                                "rendered_field_candidate_ids"
                            ) if paragraph_transactions else ()
                        ))
                    )
                    if state == "rendered" else ()
                ),
                writer_rendered_edge_refs=tuple(sorted(
                    set(edge_ids).intersection(rendered_edges)
                )),
                final_validation_refs=quality_refs,
                terminal_state=state,
                owner="writer" if accepted else "architect",
                stop_reason=(
                    "paragraph_transaction_witness_missing"
                    if paragraph_id in invalid_transaction_ids
                    else "section_not_accepted" if not accepted
                    else "formula_package_not_consumed" if state == "rendered_invalid"
                    else ""
                ),
            ))
    return MethodContentTraceV1(
        rows=tuple(rows),
        transaction_assessment_digest=str(
            transaction_assessments.get("content_digest") or ""
        ).strip(),
    )


def write_method_content_trace(
    path: str | Path,
    artifact_paths: Mapping[str, str],
) -> MethodContentTraceV1:
    """Build and atomically-ish write the trace at ``path``."""

    trace = build_method_content_trace_from_artifact_paths(artifact_paths)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(trace.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return trace


class MethodContentTraceRowV2(BaseModel):
    """Unified mechanism-context-first content trace row."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism_id: str
    detail_id: str
    order_index: int = 0
    role: str = ""
    importance: str = "core"
    claim_kind: str = "specification"
    evidence_authority: str = "repository_verified"
    publication_policy: str = "clean_candidate"
    active_path_status: str = "active_default"

    source_operation_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    operation_dispositions: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    witness_atom_ids: tuple[str, ...] = Field(default_factory=tuple)
    closed_in_evidence: bool = False
    annotated: bool = False
    projected: bool = False
    core_detail: bool = False

    section_id: str = ""
    paragraph_id: str = ""
    formula_package_ids: tuple[str, ...] = Field(default_factory=tuple)
    formula_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    shared_payload_digest: str = ""
    source_context_digest: str = ""
    view_digest: str = ""
    slice_digests: tuple[str, ...] = Field(default_factory=tuple)
    formalizer_request_digest: str = ""
    writer_request_digest: str = ""
    planned_paragraph_ids: tuple[str, ...] = Field(default_factory=tuple)
    rendered_paragraph_ids: tuple[str, ...] = Field(default_factory=tuple)

    writer_witnessed: bool = False
    discovered: bool = True
    context_included: bool = False
    formalizer_delivered: bool = False
    writer_delivered: bool = False
    planned: bool = False
    rendered: bool = False
    witnessed: bool = False
    validated: bool = False
    context_lost: bool = False
    writer_omitted: bool = False
    budget_exhausted: bool = False
    callback_status: str = ""
    callback_semantic_delta_digest: str = ""
    r0_discovery_miss: bool = False
    r1_mechanism_routing_miss: bool = False
    r2_ir_compression_loss: bool = False
    r3_writer_delivery_loss: bool = False
    r4_rendering_loss: bool = False
    candidate_included: bool = False
    verified_status: str = "unverified"
    terminal_state: str = "planned"
    stop_reason: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodContentTraceRowV2":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = _digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                "method content trace row content_digest mismatch: "
                f"got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


class MechanismInformationFunnelV1(BaseModel):
    """Funnel metrics tracking content survival from Research to Validated."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    repo_snapshot_id: str
    total_research_operations: int = 0
    total_context_details: int = 0
    core_context_details: int = 0
    architect_planned_details: int = 0
    writer_rendered_details: int = 0
    candidate_accepted_details: int = 0
    verified_validated_details: int = 0
    context_lost_details: int = 0
    writer_omitted_details: int = 0
    budget_exhausted_details: int = 0
    invalid_details: int = 0
    research_discovered_operations: int = 0
    closed_operations: int = 0
    annotated_details: int = 0
    projected_details: int = 0
    formalizer_delivered_details: int = 0
    writer_delivered_details: int = 0
    core_delivery_loss_rate: float = 0.0
    context_to_writer_core_loss_rate: float = 0.0
    mechanism_discovery_recall: float = 0.0
    formula_obligation_recall: float = 0.0
    condition_recall: float = 0.0
    interface_recall: float = 0.0
    configuration_recall: float = 0.0
    rendered_core_detail_recall: float = 0.0
    review_required_formula_count: int = 0
    cross_mechanism_contamination_count: int = 0

    # Explicit cutover metrics.  The historical counters above remain for
    # compatibility, while these names mirror the revised funnel contract.
    context_core_detail_count: int = 0
    context_supporting_detail_count: int = 0
    context_unresolved_detail_count: int = 0
    writer_delivery_recall_core: float = 0.0
    writer_delivery_recall_supporting: float = 0.0
    rendered_supporting_detail_recall: float = 0.0
    strict_verified_formula_recall: float = 0.0
    formula_mechanism_mismatch_count: int = 0
    formula_operator_mismatch_count: int = 0
    formula_operand_set_mismatch_count: int = 0
    formula_condition_mismatch_count: int = 0
    mechanism_edge_realization_rate: float = 0.0
    core_step_order_violation_count: int = 0
    required_witness_atom_count: int = 0
    validated_witness_atom_count: int = 0
    validated_required_witness_atom_recall: float = 0.0
    total_tokens_per_candidate: int = 0
    tokens_per_validated_core_detail: float = 0.0
    calls_per_validated_paragraph: float = 0.0
    callback_token_fraction: float = 0.0
    formalizer_input_tokens: int = 0
    writer_input_tokens: int = 0
    shared_payload_tokens: int = 0

    funnel_survival_rates: dict[str, float] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "MechanismInformationFunnelV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = _digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                "mechanism information funnel content_digest mismatch: "
                f"got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


class MethodContentTraceV2(BaseModel):
    """V2 trace tracking mechanism details across the authoring funnel."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "2.0"
    repo_snapshot_id: str
    project_tree_hash: str = ""
    context_set_digest: str = ""
    rows: tuple[MethodContentTraceRowV2, ...]
    funnel: MechanismInformationFunnelV1 | None = None
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodContentTraceV2":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = _digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                "method content trace content_digest mismatch: "
                f"got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


def build_method_content_trace_v2(
    *,
    contexts: Any,
    narrative_plan: Any | None = None,
    paragraph_assessments: Mapping[str, Any] | None = None,
    verified_detail_ids: set[str] | frozenset[str] = frozenset(),
    shared_payload_slices: Mapping[str, Sequence[Any]] | None = None,
    formalizer_traces: Sequence[Mapping[str, Any]] = (),
    formula_packages: Sequence[Any] | None = None,
    writer_inputs: Sequence[Any] = (),
    writer_traces: Sequence[Any] = (),
    writer_outputs: Mapping[str, Any] | Sequence[Any] | None = None,
    research_discovered_operation_ids: Mapping[str, Sequence[str]] | Sequence[str] = (),
    callback_artifacts: Sequence[Any] = (),
) -> MethodContentTraceV2:
    """Build V2 trace and information funnel from unified mechanism contexts."""
    assessments = paragraph_assessments or {}
    has_materialized_delivery = shared_payload_slices is not None

    def _object_value(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, Mapping):
            return value.get(name, default)
        return getattr(value, name, default)

    def _token_usage(value: Any) -> Mapping[str, Any]:
        """Extract provider usage without requiring one concrete trace type."""

        if isinstance(value, Mapping):
            for key in ("token_usage", "usage"):
                candidate = value.get(key)
                if isinstance(candidate, Mapping):
                    return candidate
            if any(
                key in value
                for key in (
                    "total_tokens", "prompt_tokens", "input_tokens",
                    "completion_tokens", "output_tokens", "generated_tokens",
                )
            ):
                return value
        else:
            for key in ("token_usage", "usage"):
                candidate = getattr(value, key, None)
                if isinstance(candidate, Mapping):
                    return candidate
        for key in ("metadata", "trace"):
            nested = _object_value(value, key, None)
            if nested is not None and nested is not value:
                usage = _token_usage(nested)
                if usage:
                    return usage
        return {}

    def _usage_int(usage: Mapping[str, Any], *keys: str) -> int:
        for key in keys:
            value = usage.get(key)
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed >= 0:
                return parsed
        return 0

    def _usage_input(value: Any) -> int:
        usage = _token_usage(value)
        return _usage_int(usage, "prompt_tokens", "input_tokens", "prompt_token_count")

    def _usage_total(value: Any) -> int:
        usage = _token_usage(value)
        total = _usage_int(usage, "total_tokens", "token_count")
        if total:
            return total
        return _usage_input(value) + _usage_int(
            usage, "completion_tokens", "output_tokens", "generated_tokens"
        )

    def _rough_tokens(value: Any) -> int:
        try:
            encoded = json.dumps(
                value, ensure_ascii=False, sort_keys=True, default=str,
                separators=(",", ":"),
            )
        except (TypeError, ValueError):
            encoded = str(value)
        return max(1, (len(encoded) + 3) // 4) if encoded else 0

    def _payload_detail_ids(payload: Any) -> tuple[str, ...]:
        if isinstance(payload, bytes):
            try:
                payload = payload.decode("utf-8")
            except UnicodeDecodeError:
                return ()
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError, json.JSONDecodeError):
                return ()
        if isinstance(payload, Mapping):
            payload = (payload,)
        if not isinstance(payload, (list, tuple)):
            return ()
        detail_ids: list[str] = []
        for record in payload:
            technical = (
                record.get("technical_payload")
                if isinstance(record, Mapping)
                else None
            )
            if not isinstance(technical, Mapping):
                continue
            for detail in technical.get("details") or ():
                detail_id = str(
                    detail.get("detail_id") if isinstance(detail, Mapping) else ""
                ).strip()
                if detail_id and detail_id not in detail_ids:
                    detail_ids.append(detail_id)
        return tuple(detail_ids)

    trace_by_mechanism = {
        str(item.get("mechanism_id") or "").strip(): item
        for item in (formalizer_traces or ())
        if isinstance(item, Mapping) and str(item.get("mechanism_id") or "").strip()
    }
    writer_input_by_mechanism: dict[str, list[tuple[str, Any, Mapping[str, Any]]]] = {}
    for item in writer_inputs or ():
        payload = _object_value(item, "prompt_payload", {})
        if not isinstance(payload, Mapping):
            continue
        section_id = str(
            payload.get("section_id") or _object_value(item, "section_id", "")
        ).strip()
        plan_payload = payload.get("narrative_plan")
        mechanism_ids = tuple(
            str(value).strip()
            for value in (
                plan_payload.get("mechanism_ids", ())
                if isinstance(plan_payload, Mapping)
                else ()
            )
            if str(value).strip()
        )
        if not mechanism_ids and isinstance(plan_payload, Mapping):
            mechanism_ids = tuple(dict.fromkeys(
                str(row.get("mechanism_id") or "").strip()
                for row in (plan_payload.get("paragraphs") or ())
                if isinstance(row, Mapping) and str(row.get("mechanism_id") or "").strip()
            ))
        for mechanism_id in mechanism_ids:
            writer_input_by_mechanism.setdefault(mechanism_id, []).append(
                (section_id, item, payload)
            )

    output_values: list[Any] = []
    if isinstance(writer_outputs, Mapping):
        output_values = list(writer_outputs.values())
    elif writer_outputs is not None:
        output_values = list(writer_outputs)
    output_transactions: dict[str, Any] = {}
    for output in output_values:
        for transaction in (_object_value(output, "paragraphs", ()) or ()):
            paragraph_id = str(_object_value(transaction, "paragraph_id", "") or "").strip()
            if paragraph_id:
                output_transactions[paragraph_id] = transaction

    discovered_by_mechanism: dict[str, set[str]] = {}
    if isinstance(research_discovered_operation_ids, Mapping):
        discovered_by_mechanism = {
            str(mid): set(_ids(values))
            for mid, values in research_discovered_operation_ids.items()
        }
    elif research_discovered_operation_ids:
        discovered_values = set(_ids(research_discovered_operation_ids))
        discovered_by_mechanism = {
            str(getattr(ctx, "mechanism_id", "")): set(discovered_values)
            for ctx in getattr(contexts, "contexts", ())
        }

    callback_by_detail: dict[tuple[str, str], tuple[str, str]] = {}
    for artifact in callback_artifacts or ():
        mechanism_id = str(_object_value(artifact, "mechanism_id", "") or "").strip()
        detail_id = str(_object_value(artifact, "target_detail_id", "") or "").strip()
        delta_digest = str(_object_value(artifact, "semantic_delta_digest", "") or "").strip()
        if mechanism_id:
            callback_by_detail[(mechanism_id, detail_id)] = (
                str(_object_value(artifact, "validated", "fulfilled") or ""),
                delta_digest,
            )

    projected_details_by_mechanism: dict[str, set[str]] = {}
    shared_digest_by_mechanism: dict[str, str] = {}
    source_digest_by_mechanism: dict[str, str] = {}
    view_digest_by_mechanism: dict[str, str] = {}
    slice_digests_by_mechanism: dict[str, tuple[str, ...]] = {}
    if has_materialized_delivery:
        for mechanism_id, slices in (shared_payload_slices or {}).items():
            mid = str(mechanism_id).strip()
            materialized_slices = tuple(slices or ())
            projected_details_by_mechanism[mid] = {
                str(detail_id)
                for slice_obj in materialized_slices
                for detail_id in (_object_value(slice_obj, "detail_ids", ()) or ())
                if str(detail_id).strip()
            }
            if materialized_slices:
                shared_digest_by_mechanism[mid] = str(
                    _object_value(materialized_slices[0], "shared_payload_digest", "") or ""
                )
                view_digest_by_mechanism[mid] = str(
                    _object_value(materialized_slices[0], "view_digest", "") or ""
                )
                slice_digests_by_mechanism[mid] = tuple(
                    str(_object_value(slice_obj, "slice_digest", "") or "")
                    for slice_obj in materialized_slices
                )
                technical_payload = _object_value(
                    materialized_slices[0], "technical_payload", {}
                )
                source_digest_by_mechanism[mid] = str(
                    technical_payload.get("source_context_digest", "")
                    if isinstance(technical_payload, Mapping) else ""
                )

    formalizer_detail_ids_by_mechanism: dict[str, set[str]] = {}
    formalizer_request_by_mechanism: dict[str, str] = {}
    for mechanism_id, trace in trace_by_mechanism.items():
        formalizer_detail_ids_by_mechanism[mechanism_id] = set(
            _payload_detail_ids(trace.get("shared_payload"))
        )
        formalizer_request_by_mechanism[mechanism_id] = str(
            trace.get("consumer_request_digest") or ""
        )
        if not source_digest_by_mechanism.get(mechanism_id):
            source_digest_by_mechanism[mechanism_id] = str(
                trace.get("source_context_digest") or ""
            )
        if not shared_digest_by_mechanism.get(mechanism_id):
            shared_digest_by_mechanism[mechanism_id] = str(
                trace.get("shared_payload_digest") or ""
            )
        if not view_digest_by_mechanism.get(mechanism_id):
            view_digest_by_mechanism[mechanism_id] = str(
                trace.get("view_digest") or ""
            )
        if not slice_digests_by_mechanism.get(mechanism_id):
            slice_digests_by_mechanism[mechanism_id] = tuple(
                str(value) for value in (trace.get("slice_digests") or ())
            )

    writer_detail_ids_by_mechanism: dict[str, set[str]] = {}
    writer_request_by_mechanism: dict[str, str] = {}
    for mechanism_id, entries in writer_input_by_mechanism.items():
        for section_id, _item, payload in entries:
            for shared_payload in (payload.get("shared_contexts") or ()):
                writer_detail_ids_by_mechanism.setdefault(mechanism_id, set()).update(
                    _payload_detail_ids(shared_payload)
                )
            for metadata in (payload.get("shared_context_metadata") or ()):
                if not isinstance(metadata, Mapping):
                    continue
                if str(metadata.get("mechanism_id") or "").strip() != mechanism_id:
                    continue
                writer_request_by_mechanism[mechanism_id] = str(
                    metadata.get("consumer_request_digest") or ""
                )
    detail_placement: dict[str, tuple[str, str]] = {}
    paragraph_plan_rows: dict[tuple[str, str], dict[str, Any]] = {}
    formula_placement: dict[str, tuple[str, ...]] = {}
    formula_obligation_placement: dict[str, tuple[str, ...]] = {}
    if narrative_plan is not None:
        for sec in getattr(narrative_plan, "sections", ()):
            sec_id = _object_value(sec, "section_id", "")
            for para in (_object_value(sec, "paragraphs", ()) or ()):
                p_id = _object_value(para, "paragraph_id", "")
                if isinstance(para, Mapping):
                    plan_row = dict(para)
                elif hasattr(para, "model_dump"):
                    plan_row = para.model_dump(mode="json")
                else:
                    plan_row = {}
                plan_row["section_id"] = str(sec_id or "")
                plan_row["paragraph_id"] = str(p_id or "")
                if p_id:
                    paragraph_plan_rows[(str(sec_id), str(p_id))] = plan_row
                for did in (_object_value(para, "required_detail_ids", ()) or ()):
                    detail_placement[did] = (sec_id, p_id)
                for did in (_object_value(para, "optional_detail_ids", ()) or ()):
                    detail_placement.setdefault(did, (sec_id, p_id))
                formula_placement[p_id] = tuple(
                    str(value).strip()
                    for value in (_object_value(para, "formula_package_ids", ()) or ())
                    if str(value).strip()
                )
                formula_obligation_placement[p_id] = tuple(
                    str(value).strip()
                    for value in (_object_value(para, "formula_obligation_ids", ()) or ())
                    if str(value).strip()
                )

    rows: list[MethodContentTraceRowV2] = []
    total_ops = 0
    total_details = 0
    core_details = 0
    planned_details = 0
    writer_rendered = 0
    candidate_accepted = 0
    verified_validated = 0
    context_lost = 0
    writer_omitted = 0
    budget_exhausted = 0
    invalid_details = 0
    research_discovered_operations = 0
    closed_operations = 0
    projected_details = 0
    formalizer_delivered_details = 0
    writer_delivered_details = 0
    annotated_details = 0
    cross_mechanism_contamination = 0
    witnessed_detail_keys: set[tuple[str, str]] = set()
    validated_detail_keys: set[tuple[str, str]] = set()
    required_witness_atom_ids: set[tuple[str, str]] = set()
    validated_witness_atom_ids: set[tuple[str, str]] = set()

    for ctx in getattr(contexts, "contexts", ()):
        closure = getattr(ctx, "evidence_closure", None)
        closure_dispositions = {
            str(item.operation_id): str(item.disposition)
            for item in (getattr(closure, "operation_dispositions", ()) or ())
            if str(getattr(item, "operation_id", "") or "").strip()
        } if closure is not None else {}
        context_budget_exhausted = bool(
            getattr(ctx, "budget_exhausted", False)
            or getattr(closure, "budget_exhausted", False)
        ) if closure is not None else bool(getattr(ctx, "budget_exhausted", False))
        context_mechanism_id = str(getattr(ctx, "mechanism_id", ""))
        if closure is not None:
            ops = getattr(closure, "operation_nodes", ()) or getattr(closure, "operations", ()) or ()
            total_ops += len(ops)
            closed_operations += len(ops) if closure_dispositions else 0
            discovered_operations = discovered_by_mechanism.get(
                context_mechanism_id,
                {str(getattr(op, "operation_id", "")) for op in ops},
            )
            research_discovered_operations += sum(
                1 for op in ops
                if str(getattr(op, "operation_id", "")) in discovered_operations
            )
        else:
            ops = ()
            discovered_operations = discovered_by_mechanism.get(context_mechanism_id, set())

        for d in getattr(ctx, "details", ()):
            total_details += 1
            is_core = getattr(d, "importance", "") == "core"
            if is_core:
                core_details += 1

            did = str(getattr(d, "detail_id", ""))
            source_operation_ids = tuple(
                str(value) for value in (getattr(d, "source_operation_ids", ()) or ())
            )
            source_fact_ids = tuple(
                str(value) for value in (getattr(d, "source_fact_ids", ()) or ())
            )
            source_claim_ids = tuple(
                str(value) for value in (getattr(d, "source_claim_ids", ()) or ())
            )
            source_equation_ids = tuple(
                str(value) for value in (getattr(d, "source_equation_ids", ()) or ())
            )
            source_span_ids = tuple(
                str(value) for value in (getattr(d, "source_span_ids", ()) or ())
            )
            sec_id, p_id = detail_placement.get(did, ("", ""))
            if sec_id and p_id:
                planned_details += 1

            assessment = assessments.get(p_id) or assessments.get((sec_id, p_id))
            transaction = output_transactions.get(p_id) if p_id else None
            plan_row = paragraph_plan_rows.get((str(sec_id), str(p_id)), {})
            witnessed = False
            p_valid = False
            witnessed_by_kind: Mapping[str, Any] = {}
            if assessment is not None:
                p_valid = bool(getattr(assessment, "valid", False) if not isinstance(assessment, Mapping) else assessment.get("valid", False))
                witnessed_by_kind = getattr(assessment, "witnessed_by_kind", {}) if not isinstance(assessment, Mapping) else assessment.get("witnessed_by_kind", {})
            elif transaction is not None:
                # A frozen Writer output can be traced even when the optional
                # assessment sidecar was not persisted.  Re-run the same
                # deterministic transaction contract against the paragraph's
                # actual V3 witness sidecar; aggregate ids alone never count.
                from code2paper.agentic.publication_transaction_contract import (
                    assess_paragraph_transaction,
                )
                transaction_payload = (
                    transaction.model_dump(mode="json")
                    if hasattr(transaction, "model_dump")
                    else transaction
                )
                if isinstance(transaction_payload, Mapping):
                    fallback_assessment = assess_paragraph_transaction(
                        transaction_payload,
                        plan_row=plan_row,
                    )
                    p_valid = bool(fallback_assessment.valid)
                    witnessed_by_kind = fallback_assessment.witnessed_by_kind
            detail_witnessed = set(witnessed_by_kind.get("detail", ()))
            atom_witnessed = set(witnessed_by_kind.get("atom", ()))
            required_atom_ids = {
                str(target.get("target_id") or "").strip()
                for target in (
                    plan_row.get("witness_contract", {}).get("targets", ())
                    if isinstance(plan_row.get("witness_contract"), Mapping)
                    else ()
                )
                if isinstance(target, Mapping)
                and str(target.get("target_kind") or "").strip() == "atom"
                and str(target.get("detail_id") or "").strip() == did
                and bool(target.get("required", True))
                and str(target.get("target_id") or "").strip()
            }
            witnessed = did in detail_witnessed or bool(
                required_atom_ids and required_atom_ids.issubset(atom_witnessed)
            )
            required_witness_atom_ids.update(
                (context_mechanism_id, atom_id) for atom_id in required_atom_ids
            )
            if p_valid:
                validated_witness_atom_ids.update(
                    (context_mechanism_id, atom_id)
                    for atom_id in required_atom_ids.intersection(atom_witnessed)
                )

            if witnessed:
                writer_rendered += 1
                witnessed_detail_keys.add((context_mechanism_id, did))
            if witnessed and p_valid:
                candidate_accepted += 1

            if has_materialized_delivery:
                projected = did in projected_details_by_mechanism.get(
                    context_mechanism_id, set()
                )
            else:
                projected = True
            formalizer_delivered = (
                did in formalizer_detail_ids_by_mechanism.get(context_mechanism_id, set())
                if formalizer_traces
                else (bool(formula_placement.get(p_id, ())) if not has_materialized_delivery else False)
            )
            writer_delivered = (
                did in writer_detail_ids_by_mechanism.get(context_mechanism_id, set())
                if writer_inputs
                else assessment is not None or transaction is not None
            )
            planned = bool(p_id)
            rendered = bool(witnessed)
            is_verified = did in verified_detail_ids
            validated = bool(is_verified and p_valid)
            if validated:
                verified_validated += 1
                validated_detail_keys.add((context_mechanism_id, did))
            closed_in_evidence = bool(
                set(source_operation_ids).intersection(closure_dispositions)
                or source_fact_ids
                or source_claim_ids
                or source_equation_ids
                or source_span_ids
            )
            annotated = True
            annotated_details += 1
            projected_details += int(projected)
            formalizer_delivered_details += int(formalizer_delivered)
            writer_delivered_details += int(writer_delivered)
            discovered = not source_operation_ids or all(
                operation_id in discovered_operations
                for operation_id in source_operation_ids
            )
            r0_discovery_miss = not discovered
            r1_mechanism_routing_miss = discovered and not annotated
            r2_ir_compression_loss = annotated and not projected
            r3_writer_delivery_loss = projected and not writer_delivered
            r4_rendering_loss = writer_delivered and not rendered
            context_lost_flag = (
                (not projected) or (not planned)
                if has_materialized_delivery
                else not planned
            )
            writer_omitted_flag = planned and projected and not writer_delivered
            callback_status, callback_delta_digest = callback_by_detail.get(
                (context_mechanism_id, did),
                callback_by_detail.get((context_mechanism_id, ""), ("", "")),
            )
            callback_status = (
                "fulfilled" if callback_status.casefold() in {"true", "fulfilled", "validated"}
                else callback_status
            )
            if context_budget_exhausted:
                terminal_state = "budget_exhausted"
                budget_exhausted += 1
            elif r0_discovery_miss:
                terminal_state = "not_discovered"
            elif r1_mechanism_routing_miss or r2_ir_compression_loss or context_lost_flag:
                terminal_state = "context_lost"
                context_lost += 1
            elif writer_omitted_flag:
                terminal_state = "writer_omitted"
                writer_omitted += 1
            elif validated:
                terminal_state = "validated"
            elif rendered and p_valid:
                terminal_state = "rendered"
            elif rendered or writer_delivered:
                terminal_state = "rendered_invalid"
                invalid_details += 1
            else:
                terminal_state = "planned"

            if terminal_state == "not_discovered":
                stop_reason = "research_operation_not_discovered"
            elif terminal_state == "context_lost":
                stop_reason = (
                    "ir_compression_or_projection_loss"
                    if r2_ir_compression_loss else "mechanism_routing_loss"
                    if r1_mechanism_routing_miss else "detail_not_planned"
                )
            elif terminal_state == "writer_omitted":
                stop_reason = "writer_shared_payload_detail_omitted"
            elif terminal_state == "budget_exhausted":
                stop_reason = "context_budget_exhausted"
            elif terminal_state == "rendered_invalid":
                stop_reason = "paragraph_witness_or_validation_failed"
            else:
                stop_reason = ""

            rows.append(MethodContentTraceRowV2(
                mechanism_id=getattr(ctx, "mechanism_id", ""),
                detail_id=did,
                order_index=int(getattr(d, "order_index", 0)),
                role=str(getattr(d, "role", "")),
                importance=str(getattr(d, "importance", "core")),
                claim_kind=str(getattr(d, "claim_kind", "specification")),
                evidence_authority=str(getattr(d, "evidence_authority", "repository_verified")),
                publication_policy=str(getattr(d, "publication_policy", "clean_candidate")),
                active_path_status=str(getattr(d, "active_path_status", "active_default")),
                source_operation_ids=tuple(getattr(d, "source_operation_ids", ())),
                source_fact_ids=source_fact_ids,
                source_claim_ids=source_claim_ids,
                source_equation_ids=source_equation_ids,
                source_span_ids=source_span_ids,
                operation_dispositions=tuple(
                    {
                        "operation_id": operation_id,
                        "disposition": closure_dispositions[operation_id],
                    }
                    for operation_id in getattr(d, "source_operation_ids", ())
                    if operation_id in closure_dispositions
                ),
                witness_atom_ids=tuple(
                    getattr(atom, "atom_id", "")
                    for atom in getattr(d, "witness_atoms", ())
                    if getattr(atom, "atom_id", "")
                ),
                section_id=sec_id,
                paragraph_id=p_id,
                formula_package_ids=formula_placement.get(p_id, ()),
                formula_obligation_ids=formula_obligation_placement.get(p_id, ()),
                closed_in_evidence=closed_in_evidence,
                annotated=annotated,
                projected=projected,
                core_detail=is_core,
                shared_payload_digest=shared_digest_by_mechanism.get(context_mechanism_id, ""),
                source_context_digest=source_digest_by_mechanism.get(context_mechanism_id, ""),
                view_digest=view_digest_by_mechanism.get(context_mechanism_id, ""),
                slice_digests=slice_digests_by_mechanism.get(context_mechanism_id, ()),
                formalizer_request_digest=formalizer_request_by_mechanism.get(context_mechanism_id, ""),
                writer_request_digest=writer_request_by_mechanism.get(context_mechanism_id, ""),
                planned_paragraph_ids=(p_id,) if p_id else (),
                rendered_paragraph_ids=(p_id,) if rendered and p_id else (),
                writer_witnessed=witnessed,
                discovered=discovered,
                context_included=projected if has_materialized_delivery else True,
                formalizer_delivered=formalizer_delivered,
                writer_delivered=writer_delivered,
                planned=planned,
                rendered=rendered,
                witnessed=witnessed,
                validated=validated,
                context_lost=context_lost_flag,
                writer_omitted=writer_omitted_flag,
                budget_exhausted=context_budget_exhausted,
                callback_status=callback_status,
                callback_semantic_delta_digest=callback_delta_digest,
                r0_discovery_miss=r0_discovery_miss,
                r1_mechanism_routing_miss=r1_mechanism_routing_miss,
                r2_ir_compression_loss=r2_ir_compression_loss,
                r3_writer_delivery_loss=r3_writer_delivery_loss,
                r4_rendering_loss=r4_rendering_loss,
                candidate_included=witnessed and p_valid,
                verified_status="verified" if validated else "unverified",
                terminal_state=terminal_state,
                stop_reason=stop_reason,
            ))

    clean_statuses = {"active_default", "active_selected", "conditional"}
    clean_core_ids = {
        str(getattr(detail, "detail_id", ""))
        for ctx in getattr(contexts, "contexts", ())
        for detail in (getattr(ctx, "details", ()) or ())
        if getattr(detail, "importance", "") == "core"
        and getattr(detail, "publication_policy", "") == "clean_candidate"
        and getattr(detail, "active_path_status", "unknown") in clean_statuses
    }
    rendered_core_ids = {
        row.detail_id for row in rows
        if row.detail_id in clean_core_ids and row.rendered and row.validated
    }
    writer_core_ids = {
        row.detail_id for row in rows
        if row.detail_id in clean_core_ids and row.writer_delivered
    }
    all_formula_obligation_ids = {
        obligation_id
        for value in formula_obligation_placement.values()
        for obligation_id in value
    }
    placed_formula_package_ids = {
        package_id
        for value in formula_placement.values()
        for package_id in value
    }
    if formula_packages is None:
        # Historical callers only persisted plan placement.  Keep their
        # consumption metric readable, but the production writer passes an
        # explicit package sequence so strict recall cannot be inferred from
        # placement ids alone.
        formula_package_ids = placed_formula_package_ids
        accepted_formula_package_ids = set(formula_package_ids)
        accepted_formula_obligation_ids = {
            obligation_id
            for paragraph_id, obligation_ids in formula_obligation_placement.items()
            if formula_placement.get(paragraph_id)
            for obligation_id in obligation_ids
        }
    else:
        formula_package_ids = {
            str(_object_value(package, "package_id", "") or "").strip()
            for package in (formula_packages or ())
            if str(_object_value(package, "package_id", "") or "").strip()
        }
        accepted_formula_package_ids = set()
        accepted_formula_obligation_ids = set()
        for package in (formula_packages or ()):
            package_id = str(_object_value(package, "package_id", "") or "").strip()
            if not package_id:
                continue
            if (
                str(_object_value(package, "review_status", "") or "") == "accepted"
                and str(_object_value(package, "evidence_authority", "") or "")
                == "repository_verified"
                and str(_object_value(package, "formula_lane", "") or "")
                == "repository_derived"
                and any(
                    _ids(_object_value(package, field, ()))
                    for field in ("bound_operation_ids", "bound_fact_ids", "bound_equation_ids")
                )
            ):
                accepted_formula_package_ids.add(package_id)
                accepted_formula_obligation_ids.update(
                    _ids(_object_value(package, "satisfied_obligation_ids", ()))
                )
    formula_obligations_with_packages = {
        obligation_id
        for paragraph_id, obligation_ids in formula_obligation_placement.items()
        if set(formula_placement.get(paragraph_id, ())).intersection(formula_package_ids)
        for obligation_id in obligation_ids
    }
    formula_obligation_recall = (
        len(formula_obligations_with_packages) / len(all_formula_obligation_ids)
        if all_formula_obligation_ids else 1.0
    )
    strict_verified_formula_recall = (
        len(accepted_formula_obligation_ids.intersection(all_formula_obligation_ids))
        / len(all_formula_obligation_ids)
        if all_formula_obligation_ids else 1.0
    )
    condition_total = 0
    condition_rendered = 0
    interface_total = 0
    interface_rendered = 0
    configuration_total = 0
    configuration_rendered = 0
    for row in rows:
        ctx = next(
            (item for item in getattr(contexts, "contexts", ())
             if str(getattr(item, "mechanism_id", "")) == row.mechanism_id),
            None,
        )
        detail = next(
            (item for item in (getattr(ctx, "details", ()) if ctx is not None else ())
             if str(getattr(item, "detail_id", "")) == row.detail_id),
            None,
        )
        conditions = tuple(getattr(detail, "conditions", ()) or ()) if detail is not None else ()
        condition_total += len(conditions)
        if row.validated:
            condition_rendered += len(conditions)
        role = str(getattr(detail, "role", "") or "") if detail is not None else row.role
        if role in {"input", "output", "interface"}:
            interface_total += 1
            interface_rendered += int(row.validated)
        if role in {"configuration", "config", "branch"} or row.claim_kind == "configuration":
            configuration_total += 1
            configuration_rendered += int(row.validated)

    for item in writer_inputs or ():
        payload = _object_value(item, "prompt_payload", {})
        if not isinstance(payload, Mapping):
            continue
        plan_payload = payload.get("narrative_plan")
        for paragraph in (
            plan_payload.get("paragraphs", ())
            if isinstance(plan_payload, Mapping) else ()
        ):
            if not isinstance(paragraph, Mapping):
                continue
            paragraph_mechanism = str(paragraph.get("mechanism_id") or "").strip()
            for detail_id in (
                *(paragraph.get("required_detail_ids") or ()),
                *(paragraph.get("optional_detail_ids") or ()),
            ):
                owner = next(
                    (
                        str(getattr(ctx, "mechanism_id", ""))
                        for ctx in getattr(contexts, "contexts", ())
                        for detail in (getattr(ctx, "details", ()) or ())
                        if str(getattr(detail, "detail_id", "")) == str(detail_id)
                    ),
                    "",
                )
                if owner and paragraph_mechanism and owner != paragraph_mechanism:
                    cross_mechanism_contamination += 1

    context_core_keys = {
        (str(getattr(ctx, "mechanism_id", "")), str(getattr(detail, "detail_id", "")))
        for ctx in getattr(contexts, "contexts", ())
        for detail in (getattr(ctx, "details", ()) or ())
        if getattr(detail, "importance", "") == "core"
    }
    context_supporting_keys = {
        (str(getattr(ctx, "mechanism_id", "")), str(getattr(detail, "detail_id", "")))
        for ctx in getattr(contexts, "contexts", ())
        for detail in (getattr(ctx, "details", ()) or ())
        if getattr(detail, "importance", "") != "core"
    }
    context_unresolved_keys = {
        (str(getattr(ctx, "mechanism_id", "")), str(getattr(detail, "detail_id", "")))
        for ctx in getattr(contexts, "contexts", ())
        for detail in (getattr(ctx, "details", ()) or ())
        if (
            getattr(detail, "evidence_authority", "") == "unresolved"
            or getattr(detail, "active_path_status", "unknown") == "unknown"
        )
    }
    writer_supporting_keys = {
        (row.mechanism_id, row.detail_id)
        for row in rows
        if row.detail_id and not row.core_detail and row.writer_delivered
    }
    rendered_supporting_keys = {
        (row.mechanism_id, row.detail_id)
        for row in rows
        if row.detail_id and not row.core_detail and row.rendered and row.validated
    }

    # Formula failures are kept as typed counters instead of collapsing all
    # Formalizer rejection into one opaque ``review_required`` number.
    formalizer_failure_values: set[str] = set()
    for trace in formalizer_traces or ():
        raw_failures = _object_value(trace, "failures", ()) or ()
        if isinstance(raw_failures, str):
            raw_failures = (raw_failures,)
        formalizer_failure_values.update(
            str(value).strip() for value in raw_failures if str(value).strip()
        )

    def _failure_count(predicate: Any) -> int:
        return sum(1 for value in formalizer_failure_values if predicate(value))

    formula_mechanism_mismatch_count = _failure_count(
        lambda value: any(
            token in value
            for token in (
                "mechanism_id_mismatch",
                "formula_obligation_mechanism_mismatch",
                "cross_mechanism",
            )
        )
    )
    formula_operator_mismatch_count = _failure_count(
        lambda value: "missing_required_operator" in value
        or "formula_operator_mismatch" in value
    )
    formula_operand_set_mismatch_count = _failure_count(
        lambda value: "formula_operand_set_mismatch" in value
    )
    formula_condition_mismatch_count = _failure_count(
        lambda value: "missing_required_condition" in value
        or "formula_condition_mismatch" in value
    )

    edge_count = 0
    realized_edge_count = 0
    for ctx in getattr(contexts, "contexts", ()):
        mechanism_id = str(getattr(ctx, "mechanism_id", ""))
        for edge in (getattr(ctx, "edges", ()) or ()):
            edge_count += 1
            if (
                (mechanism_id, str(getattr(edge, "source_detail_id", "")))
                in witnessed_detail_keys
                and (mechanism_id, str(getattr(edge, "target_detail_id", "")))
                in witnessed_detail_keys
            ):
                realized_edge_count += 1
    mechanism_edge_realization_rate = (
        round(realized_edge_count / edge_count, 4) if edge_count else 1.0
    )

    planned_detail_order_by_mechanism: dict[str, list[str]] = {}
    for plan_row in paragraph_plan_rows.values():
        mechanism_id = str(
            plan_row.get("mechanism_id")
            or next(iter(plan_row.get("mechanism_ids") or ()), "")
        ).strip()
        if not mechanism_id:
            continue
        ordered = planned_detail_order_by_mechanism.setdefault(mechanism_id, [])
        for detail_id in (
            *(plan_row.get("required_detail_ids") or ()),
            *(plan_row.get("optional_detail_ids") or ()),
        ):
            detail_id = str(detail_id).strip()
            if detail_id and detail_id not in ordered:
                ordered.append(detail_id)
    core_step_order_violation_count = 0
    for ctx in getattr(contexts, "contexts", ()):
        mechanism_id = str(getattr(ctx, "mechanism_id", ""))
        canonical_positions = {
            str(detail_id): index
            for index, detail_id in enumerate(getattr(ctx, "ordered_detail_ids", ()) or ())
        }
        core_ids = {
            str(detail.detail_id)
            for detail in (getattr(ctx, "details", ()) or ())
            if getattr(detail, "importance", "") == "core"
        }
        planned_core_order = [
            detail_id
            for detail_id in planned_detail_order_by_mechanism.get(mechanism_id, ())
            if detail_id in core_ids and detail_id in canonical_positions
        ]
        for left_index, left_id in enumerate(planned_core_order):
            for right_id in planned_core_order[left_index + 1:]:
                if canonical_positions[left_id] > canonical_positions[right_id]:
                    core_step_order_violation_count += 1

    # Efficiency is diagnostic only, but it must be present in the same frozen
    # trace that carries correctness counters.  Prefer provider usage; when a
    # provider did not report it, retain a transparent payload-size estimate
    # rather than silently claiming zero input cost.
    formalizer_trace_values = tuple(formalizer_traces or ())
    writer_trace_values = tuple(writer_traces or ())
    formalizer_input_tokens = sum(_usage_input(item) for item in formalizer_trace_values)
    if not formalizer_input_tokens:
        formalizer_input_tokens = sum(
            _rough_tokens(_object_value(item, "shared_payload", ""))
            for item in formalizer_trace_values
            if _object_value(item, "shared_payload", "")
        )
    writer_input_tokens = sum(_usage_input(item) for item in writer_trace_values)
    if not writer_input_tokens:
        writer_input_tokens = sum(
            _rough_tokens({
                "prompt_payload": _object_value(item, "prompt_payload", {}),
                "system_prompt": _object_value(item, "system_prompt", ""),
            })
            for item in (writer_inputs or ())
        )
    callback_tokens = sum(_usage_total(item) for item in (callback_artifacts or ()))
    formalizer_total_tokens = sum(_usage_total(item) for item in formalizer_trace_values)
    writer_total_tokens = sum(_usage_total(item) for item in writer_trace_values)
    if not formalizer_total_tokens:
        formalizer_total_tokens = formalizer_input_tokens
    if not writer_total_tokens:
        writer_total_tokens = writer_input_tokens
    total_tokens = formalizer_total_tokens + writer_total_tokens + callback_tokens
    shared_payload_tokens = 0
    for mechanism_id, slices in (shared_payload_slices or {}).items():
        shared_payload_tokens += _rough_tokens({
            "mechanism_id": str(mechanism_id),
            "slices": [
                _object_value(slice_obj, "technical_payload", {})
                for slice_obj in (slices or ())
            ],
        })
    validated_paragraph_ids = {
        row.paragraph_id for row in rows if row.validated and row.paragraph_id
    }
    validated_core_detail_count = len(rendered_core_ids)
    writer_call_count = len(writer_trace_values) or len(tuple(writer_inputs or ()))
    formalizer_call_count = sum(
        int(bool(_object_value(item, "llm_call_made", False)))
        for item in formalizer_trace_values
    )
    total_call_count = writer_call_count + formalizer_call_count
    tokens_per_validated_core_detail = (
        round(total_tokens / validated_core_detail_count, 4)
        if validated_core_detail_count else 0.0
    )
    calls_per_validated_paragraph = (
        round(total_call_count / len(validated_paragraph_ids), 4)
        if validated_paragraph_ids else 0.0
    )
    callback_token_fraction = (
        round(callback_tokens / total_tokens, 4) if total_tokens else 0.0
    )

    def _ratio(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator else 1.0

    survival_rates: dict[str, float] = {
        "research_to_closure": _ratio(closed_operations, total_ops),
        "discovery_recall": _ratio(research_discovered_operations, total_ops),
        "context_to_annotation": _ratio(annotated_details, total_details),
        "annotation_to_projection": _ratio(projected_details, annotated_details),
        "projection_to_formalizer": _ratio(formalizer_delivered_details, projected_details),
        "projection_to_writer": _ratio(writer_delivered_details, projected_details),
        "context_to_plan": _ratio(planned_details, total_details),
        "plan_to_writer": _ratio(writer_rendered, planned_details),
        "writer_to_candidate": _ratio(candidate_accepted, writer_rendered),
        "candidate_to_verified": _ratio(verified_validated, candidate_accepted),
    }
    core_delivery_loss_rate = (
        round((len(clean_core_ids) - len(writer_core_ids)) / len(clean_core_ids), 4)
        if clean_core_ids else 0.0
    )
    metrics = {
        "research_discovered_operations": research_discovered_operations,
        "closed_operations": closed_operations,
        "annotated_details": annotated_details,
        "projected_details": projected_details,
        "formalizer_delivered_details": formalizer_delivered_details,
        "writer_delivered_details": writer_delivered_details,
        "core_detail_count": len(clean_core_ids),
        "context_to_writer_core_loss_rate": core_delivery_loss_rate,
        "rendered_core_detail_count": len(rendered_core_ids),
        "formula_obligation_count": len(all_formula_obligation_ids),
        "formula_package_count": len(formula_package_ids),
        "strict_verified_formula_recall": round(strict_verified_formula_recall, 4),
        "formula_mechanism_mismatch_count": formula_mechanism_mismatch_count,
        "formula_operator_mismatch_count": formula_operator_mismatch_count,
        "formula_operand_set_mismatch_count": formula_operand_set_mismatch_count,
        "formula_condition_mismatch_count": formula_condition_mismatch_count,
        "mechanism_edge_realization_rate": mechanism_edge_realization_rate,
        "core_step_order_violation_count": core_step_order_violation_count,
        "required_witness_atom_count": len(required_witness_atom_ids),
        "validated_witness_atom_count": len(validated_witness_atom_ids),
        "validated_required_witness_atom_recall": (
            round(
                len(validated_witness_atom_ids.intersection(required_witness_atom_ids))
                / len(required_witness_atom_ids),
                4,
            )
            if required_witness_atom_ids else 1.0
        ),
        "total_tokens_per_candidate": total_tokens,
        "tokens_per_validated_core_detail": tokens_per_validated_core_detail,
        "calls_per_validated_paragraph": calls_per_validated_paragraph,
        "callback_token_fraction": callback_token_fraction,
        "formalizer_input_tokens": formalizer_input_tokens,
        "writer_input_tokens": writer_input_tokens,
        "shared_payload_tokens": shared_payload_tokens,
        "validated_core_detail_count": validated_core_detail_count,
        "validated_paragraph_count": len(validated_paragraph_ids),
        "writer_call_count": writer_call_count,
        "formalizer_call_count": formalizer_call_count,
        "accepted_formula_package_count": len(accepted_formula_package_ids),
        "cross_mechanism_contamination_count": cross_mechanism_contamination,
    }

    funnel = MechanismInformationFunnelV1(
        repo_snapshot_id=str(getattr(contexts, "repo_snapshot_id", "")),
        total_research_operations=total_ops,
        total_context_details=total_details,
        core_context_details=core_details,
        architect_planned_details=planned_details,
        writer_rendered_details=writer_rendered,
        candidate_accepted_details=candidate_accepted,
        verified_validated_details=verified_validated,
        context_lost_details=context_lost,
        writer_omitted_details=writer_omitted,
        budget_exhausted_details=budget_exhausted,
        invalid_details=invalid_details,
        research_discovered_operations=research_discovered_operations,
        closed_operations=closed_operations,
        annotated_details=annotated_details,
        projected_details=projected_details,
        formalizer_delivered_details=formalizer_delivered_details,
        writer_delivered_details=writer_delivered_details,
        core_delivery_loss_rate=core_delivery_loss_rate,
        context_to_writer_core_loss_rate=core_delivery_loss_rate,
        mechanism_discovery_recall=_ratio(research_discovered_operations, total_ops),
        formula_obligation_recall=round(formula_obligation_recall, 4),
        condition_recall=_ratio(condition_rendered, condition_total),
        interface_recall=_ratio(interface_rendered, interface_total),
        configuration_recall=_ratio(configuration_rendered, configuration_total),
        rendered_core_detail_recall=_ratio(len(rendered_core_ids), len(clean_core_ids)),
        review_required_formula_count=max(
            0, len(all_formula_obligation_ids - formula_obligations_with_packages)
        ),
        cross_mechanism_contamination_count=cross_mechanism_contamination,
        context_core_detail_count=len(context_core_keys),
        context_supporting_detail_count=len(context_supporting_keys),
        context_unresolved_detail_count=len(context_unresolved_keys),
        writer_delivery_recall_core=(
            round(len(writer_core_ids) / len(clean_core_ids), 4)
            if clean_core_ids else 1.0
        ),
        writer_delivery_recall_supporting=(
            round(len(writer_supporting_keys) / len(context_supporting_keys), 4)
            if context_supporting_keys else 1.0
        ),
        rendered_supporting_detail_recall=(
            round(len(rendered_supporting_keys) / len(context_supporting_keys), 4)
            if context_supporting_keys else 1.0
        ),
        strict_verified_formula_recall=round(strict_verified_formula_recall, 4),
        formula_mechanism_mismatch_count=formula_mechanism_mismatch_count,
        formula_operator_mismatch_count=formula_operator_mismatch_count,
        formula_operand_set_mismatch_count=formula_operand_set_mismatch_count,
        formula_condition_mismatch_count=formula_condition_mismatch_count,
        mechanism_edge_realization_rate=mechanism_edge_realization_rate,
        core_step_order_violation_count=core_step_order_violation_count,
        required_witness_atom_count=len(required_witness_atom_ids),
        validated_witness_atom_count=len(validated_witness_atom_ids),
        validated_required_witness_atom_recall=(
            round(
                len(validated_witness_atom_ids.intersection(required_witness_atom_ids))
                / len(required_witness_atom_ids),
                4,
            )
            if required_witness_atom_ids else 1.0
        ),
        total_tokens_per_candidate=total_tokens,
        tokens_per_validated_core_detail=tokens_per_validated_core_detail,
        calls_per_validated_paragraph=calls_per_validated_paragraph,
        callback_token_fraction=callback_token_fraction,
        formalizer_input_tokens=formalizer_input_tokens,
        writer_input_tokens=writer_input_tokens,
        shared_payload_tokens=shared_payload_tokens,
        funnel_survival_rates=survival_rates,
        metrics=metrics,
    )

    return MethodContentTraceV2(
        repo_snapshot_id=str(getattr(contexts, "repo_snapshot_id", "")),
        project_tree_hash=str(getattr(contexts, "project_tree_hash", "")),
        context_set_digest=str(getattr(contexts, "content_digest", "") or getattr(contexts, "source_context_digest", "")),
        rows=tuple(rows),
        funnel=funnel,
    )


def write_method_content_trace_v2(
    path: str | Path,
    *,
    contexts: Any,
    narrative_plan: Any | None = None,
    paragraph_assessments: Mapping[str, Any] | None = None,
    verified_detail_ids: set[str] | frozenset[str] = frozenset(),
    shared_payload_slices: Mapping[str, Sequence[Any]] | None = None,
    formalizer_traces: Sequence[Mapping[str, Any]] = (),
    formula_packages: Sequence[Any] | None = None,
    writer_inputs: Sequence[Any] = (),
    writer_traces: Sequence[Any] = (),
    writer_outputs: Mapping[str, Any] | Sequence[Any] | None = None,
    research_discovered_operation_ids: Mapping[str, Sequence[str]] | Sequence[str] = (),
    callback_artifacts: Sequence[Any] = (),
) -> MethodContentTraceV2:
    """Build and write the V2 trace at ``path``."""
    trace = build_method_content_trace_v2(
        contexts=contexts,
        narrative_plan=narrative_plan,
        paragraph_assessments=paragraph_assessments,
        verified_detail_ids=verified_detail_ids,
        shared_payload_slices=shared_payload_slices,
        formalizer_traces=formalizer_traces,
        formula_packages=formula_packages,
        writer_inputs=writer_inputs,
        writer_traces=writer_traces,
        writer_outputs=writer_outputs,
        research_discovered_operation_ids=research_discovered_operation_ids,
        callback_artifacts=callback_artifacts,
    )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(trace.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return trace


__all__ = [
    "MethodContentTraceRowV1",
    "MethodContentTraceV1",
    "build_method_content_trace_from_artifact_paths",
    "write_method_content_trace",
    "MethodContentTraceRowV2",
    "MechanismInformationFunnelV1",
    "MethodContentTraceV2",
    "build_method_content_trace_v2",
    "write_method_content_trace_v2",
]
