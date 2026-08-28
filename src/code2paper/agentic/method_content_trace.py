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
from typing import Any, Literal, Mapping

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
    required_targets: Mapping[str, tuple[str, ...]] | None = None,
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

        plan_row = {
            "required_facet_ids": tuple((required_targets or {}).get("facet", ())),
            "required_publication_slot_ids": tuple((required_targets or {}).get("slot", ())),
            "required_field_candidate_ids": tuple((required_targets or {}).get("field", ())),
            "required_edge_ids": tuple((required_targets or {}).get("edge", ())),
            "formula_obligation_ids": tuple((required_targets or {}).get("formula", ())),
        }
        return assess_paragraph_transaction(
            item,
            plan_row=plan_row,
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
        formula_obligation_ids = {
            obligation_id
            for row in self.rows
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
            "rendered_slots": len(rendered_slot_ids),
            "rendered_field_candidates": len(rendered_field_ids),
            "planned_edges": len(planned_edge_ids),
            "rendered_edges": len(planned_edge_ids & rendered_edge_ids),
            "formula_obligations": len(formula_obligation_ids),
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
                "facet": _ids(row.get("required_facet_ids")),
                "field": _ids(row.get("required_field_candidate_ids")),
                "slot": _ids(
                    row.get("required_publication_slot_ids")
                    or row.get("ordered_semantic_slot_ids")
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
        has_explicit_package_routes = any(
            isinstance(package, Mapping)
            and str(package.get("obligation_id") or "").strip()
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
                and str(package.get("obligation_id") or "").strip() == obligation_id
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
                if _transaction_has_valid_witnesses(
                    item,
                    required_targets=_required_targets(paragraph_id),
                    formula_routes=formula_routes,
                    required_anchors=_required_anchors(paragraph_id),
                )
                for value in _ids(item.get("rendered_slot_ids"))
            }
            rendered_edges = {
                value for paragraph_id, item in paragraph_transactions.items()
                if _transaction_has_valid_witnesses(
                    item,
                    required_targets=_required_targets(paragraph_id),
                    formula_routes=formula_routes,
                    required_anchors=_required_anchors(paragraph_id),
                )
                for value in _ids(item.get("rendered_edge_ids"))
            }
            used_packages = {
                value for paragraph_id, item in paragraph_transactions.items()
                if _transaction_has_valid_witnesses(
                    item,
                    required_targets=_required_targets(paragraph_id),
                    formula_routes=formula_routes,
                    required_anchors=_required_anchors(paragraph_id),
                )
                for value in _ids(item.get("used_formula_package_ids"))
            }
            writer_claim_refs = {
                value for paragraph_id, item in paragraph_transactions.items()
                if _transaction_has_valid_witnesses(
                    item,
                    required_targets=_required_targets(paragraph_id),
                    formula_routes=formula_routes,
                    required_anchors=_required_anchors(paragraph_id),
                )
                for value in _ids(item.get("used_claim_ids"))
            }
            for paragraph_id, item in paragraph_transactions.items():
                valid = _transaction_has_valid_witnesses(
                    item,
                    required_targets=_required_targets(paragraph_id),
                    formula_routes=formula_routes,
                    required_anchors=_required_anchors(paragraph_id),
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
                or paragraph.get("ordered_semantic_slot_ids")
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
            elif not accepted:
                state = "blocked_representation"
            elif rendered_paragraphs and paragraph_id in rendered_paragraphs:
                state = "rendered"
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
                        and str(package.get("obligation_id") or "").strip() in set(obligation_ids)
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


__all__ = [
    "MethodContentTraceRowV1",
    "MethodContentTraceV1",
    "build_method_content_trace_from_artifact_paths",
    "write_method_content_trace",
]
