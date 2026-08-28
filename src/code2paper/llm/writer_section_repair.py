"""Deterministic progress policy for bounded Writer-owned section repair."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


_EMPTY_PROMISES = (
    "pending confirmation", "we aim to explain", "we aim to describe",
    "we intend to explain", "we intend to describe", "we aim to discuss",
)
_CODE_TOKEN = re.compile(r"\b(?:self\.|[A-Za-z_]\w*\.[A-Za-z_]\w*|[A-Za-z_]\w*\([^\n)]*\)|\w+_\w+)\b")
_UNSUPPORTED_AUTHORITY = re.compile(
    r"\b(?:outperforms?|state[- ]of[- ]the[- ]art|improves?\s+(?:accuracy|quality|performance|efficiency)|"
    r"guarantees?|ensures?\s+(?:robustness|accuracy|optimality|superiority)|"
    r"significantly\s+(?:better|improves?|reduces?|increases?))\b",
    re.IGNORECASE,
)


class _RepairModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WriterRepairSpanV1(_RepairModel):
    kind: str
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    reason: str


class WriterConstraintFailureV1(_RepairModel):
    proposition_id: str
    constraint_kind: str
    required_value: str


class WriterSectionRepairPacketV1(_RepairModel):
    section_id: str
    attempt: int = Field(ge=1, le=4)
    incumbent_text: str
    missing_proposition_ids: tuple[str, ...] = Field(default_factory=tuple)
    unsupported_spans: tuple[WriterRepairSpanV1, ...] = Field(default_factory=tuple)
    caveat_failures: tuple[WriterRepairSpanV1, ...] = Field(default_factory=tuple)
    qualifier_failures: tuple[WriterConstraintFailureV1, ...] = Field(default_factory=tuple)
    numeric_formula_failures: tuple[WriterConstraintFailureV1, ...] = Field(default_factory=tuple)
    style_failures: tuple[WriterRepairSpanV1, ...] = Field(default_factory=tuple)
    missing_concept_keys: tuple[str, ...] = Field(default_factory=tuple)
    missing_formula_witnesses: tuple[str, ...] = Field(default_factory=tuple)
    missing_required_facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_positive_propositions: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    allowed_caveated_propositions: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    immutable_constraints: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    mechanism_authoring_packet: dict[str, Any] = Field(default_factory=dict)
    planner_drafts: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    facet_policies: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    formula_packages: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    previous_progress: dict[str, int]
    transaction_failure: str = ""


def build_writer_section_repair_packet(
    *,
    section_id: str,
    attempt: int,
    incumbent_text: str,
    writer_view: dict[str, Any],
    progress: "WriterRepairProgressV1",
    failures: list[str] | tuple[str, ...],
) -> WriterSectionRepairPacketV1:
    """Project deterministic Writer failures into a closed, typed packet."""

    rendered: set[str] = set()
    lowered = incumbent_text.casefold()
    for proposition in [
        *(writer_view.get("positive_propositions") or ()),
        *(writer_view.get("caveated_propositions") or ()),
    ]:
        concept = " ".join(str(value) for value in proposition.values())
        concept_tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]+", concept.casefold()))
        text_tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]+", lowered))
        if concept_tokens and len(text_tokens & concept_tokens) / max(
            1, min(len(text_tokens), len(concept_tokens))
        ) >= 0.35:
            rendered.add(str(proposition.get("proposition_id") or ""))
    missing = tuple(sorted(
        set(writer_view.get("required_proposition_ids") or ()) - rendered
    ))
    rendered_concepts: set[str] = set()
    for concept in [
        *(writer_view.get("positive_concepts") or ()),
        *(writer_view.get("caveated_concepts") or ()),
    ]:
        subject = str(
            concept.get("method_subject")
            or concept.get("intended_subject")
            or ""
        )
        operation = str(
            concept.get("operation")
            or concept.get("intended_transformation")
            or ""
        )
        tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]+", f"{subject} {operation}".casefold()))
        text_tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]+", lowered))
        if tokens and len(text_tokens & tokens) / max(1, min(len(text_tokens), len(tokens))) >= 0.35:
            rendered_concepts.add(str(concept.get("concept_key") or ""))
    missing_concepts = tuple(sorted(
        set(writer_view.get("required_concept_keys") or ()) - rendered_concepts
    ))
    missing_formulas = tuple(sorted(
        str(item.get("obligation_id") or item)
        for item in (writer_view.get("formula_obligations") or ())
        if (
            isinstance(item, dict)
            and str(item.get("outcome") or "") == "unresolved"
        )
    ))
    packet = writer_view.get("mechanism_authoring_packet") or {}
    packet_facets = (
        packet.get("facets") if isinstance(packet, dict) else ()
    ) or ()
    required_facet_ids = {
        str(item)
        for item in (
            packet.get("required_facet_ids", ())
            if isinstance(packet, dict) else ()
        )
        if str(item).strip()
    }
    rendered_facet_ids: set[str] = set()
    text_tokens = set(re.findall(r"[^\W_]+", lowered, flags=re.UNICODE))
    for facet in packet_facets:
        if not isinstance(facet, dict):
            continue
        facet_id = str(facet.get("facet_id") or "")
        semantic_values: list[str] = [str(facet.get("exact_source_quote") or "")]
        fields = facet.get("semantic_fields") or {}
        if isinstance(fields, dict):
            semantic_values.extend(
                str(value)
                for value in fields.values()
                if not isinstance(value, (dict, list, tuple, set))
            )
            for value in fields.values():
                if isinstance(value, (list, tuple, set)):
                    semantic_values.extend(str(item) for item in value)
        facet_tokens = {
            token for value in semantic_values
            for token in re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE)
            if len(token) > 1
        }
        if facet_id and facet_tokens and (
            len(text_tokens & facet_tokens) / max(
                1, min(len(text_tokens), len(facet_tokens))
            ) >= 0.35
        ):
            rendered_facet_ids.add(facet_id)
    missing_facets = tuple(sorted(required_facet_ids - rendered_facet_ids))
    if missing_facets:
        failures.append("writer_missing_required_facets")
    caveat_spans: list[WriterRepairSpanV1] = []
    if "candidate_proposition_missing_visible_caveat" in failures:
        for sentence_match in re.finditer(r"[^\n.!?]+[.!?]?", incumbent_text):
            sentence = sentence_match.group(0).strip()
            if not sentence:
                continue
            caveat_spans.append(WriterRepairSpanV1(
                kind="missing_caveat", text=sentence,
                char_start=sentence_match.start(), char_end=sentence_match.end(),
                reason="candidate proposition lacks its required epistemic caveat",
            ))
    unsupported_spans = tuple(
        WriterRepairSpanV1(
            kind="unsupported_authority", text=match.group(0),
            char_start=match.start(), char_end=match.end(),
            reason="benefit, performance, or guarantee language is not authorized by a proposition",
        )
        for match in _UNSUPPORTED_AUTHORITY.finditer(incumbent_text)
    )
    style_spans = tuple(
        WriterRepairSpanV1(
            kind="code_trace_style", text=match.group(0),
            char_start=match.start(), char_end=match.end(),
            reason="raw code token should be a binding, not the sentence center",
        )
        for match in _CODE_TOKEN.finditer(incumbent_text)
    ) if "code_trace_prose_not_method_language" in failures else ()
    qualifier_failures: list[WriterConstraintFailureV1] = []
    numeric_formula_failures: list[WriterConstraintFailureV1] = []
    for constraint in writer_view.get("immutable_constraints") or ():
        proposition_id = str(constraint.get("proposition_id") or "")
        for key, kind in (
            ("required_qualifiers", "qualifier"),
            ("required_numeric_tokens", "numeric"),
            ("formula_renderings", "formula"),
            ("configuration_values", "configuration"),
        ):
            for value in constraint.get(key) or ():
                if str(value).casefold() in lowered:
                    continue
                item = WriterConstraintFailureV1(
                    proposition_id=proposition_id,
                    constraint_kind=kind,
                    required_value=str(value),
                )
                if kind == "qualifier":
                    qualifier_failures.append(item)
                else:
                    numeric_formula_failures.append(item)
    return WriterSectionRepairPacketV1(
        section_id=section_id,
        attempt=attempt,
        incumbent_text=incumbent_text,
        missing_proposition_ids=missing,
        missing_concept_keys=missing_concepts,
        missing_formula_witnesses=missing_formulas,
        missing_required_facet_ids=missing_facets,
        unsupported_spans=unsupported_spans,
        caveat_failures=tuple(caveat_spans),
        qualifier_failures=tuple(qualifier_failures),
        numeric_formula_failures=tuple(numeric_formula_failures),
        style_failures=style_spans,
        allowed_positive_propositions=tuple(
            writer_view.get("positive_propositions") or ()
        ),
        allowed_caveated_propositions=tuple(
            writer_view.get("caveated_propositions") or ()
        ),
        immutable_constraints=tuple(
            writer_view.get("immutable_constraints") or ()
        ),
        mechanism_authoring_packet=(
            packet if isinstance(packet, dict) else {}
        ),
        planner_drafts=tuple(
            item for item in (writer_view.get("mechanism_drafts") or ())
            if isinstance(item, dict)
        ),
        facet_policies=tuple(
            item for item in (
                packet.get("facet_policies", ())
                if isinstance(packet, dict) else ()
            )
            if isinstance(item, dict)
        ),
        formula_packages=tuple(
            item for item in (writer_view.get("formula_packages") or ())
            if isinstance(item, dict)
        ),
        previous_progress={
            "unsafe_uncaveated_positives": progress.unsafe_uncaveated_positives,
            "constraint_failures": progress.constraint_failures,
            "validated_propositions": progress.validated_propositions,
            "unrendered_required_propositions": progress.unrendered_required_propositions,
            "code_trace_style_failures": progress.code_trace_style_failures,
            "duplicate_sentences": progress.duplicate_sentences,
            "missing_required_facets": progress.missing_required_facets,
        },
        transaction_failure=next((
            item.removeprefix("transaction:") for item in failures
            if item.startswith("transaction:")
        ), ""),
    )


@dataclass(frozen=True, order=True)
class WriterRepairProgressV1:
    unsafe_uncaveated_positives: int
    constraint_failures: int
    negative_validated_propositions: int
    unrendered_required_propositions: int
    code_trace_style_failures: int
    duplicate_sentences: int
    missing_required_facets: int = 0

    @property
    def validated_propositions(self) -> int:
        return -self.negative_validated_propositions


def assess_writer_section_progress(
    text: str,
    *,
    writer_view: dict[str, Any],
    rendered_proposition_ids: list[str] | tuple[str, ...] = (),
) -> tuple[WriterRepairProgressV1, list[str]]:
    lowered = text.casefold()
    failures: list[str] = []
    promise_count = sum(lowered.count(marker) for marker in _EMPTY_PROMISES)
    if promise_count:
        failures.append("empty_candidate_promise")
    required = set(writer_view.get("required_proposition_ids") or ())
    rendered = set(rendered_proposition_ids)
    if not rendered:
        text_tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]+", lowered))
        for proposition in [
            *(writer_view.get("positive_propositions") or ()),
            *(writer_view.get("caveated_propositions") or ()),
        ]:
            concept_text = " ".join(
                str(value) for key, value in proposition.items()
                if key not in {"proposition_id", "optional_implementation_bindings"}
            )
            concept_tokens = set(re.findall(r"[A-Za-z][A-Za-z0-9_-]+", concept_text.casefold()))
            if concept_tokens and len(text_tokens & concept_tokens) / max(
                1, min(len(text_tokens), len(concept_tokens))
            ) >= 0.35:
                rendered.add(str(proposition.get("proposition_id") or ""))
    uncaveated_candidate_count = 0
    caveat_markers = (
        "intend", "aim", "partial", "pending", "unverified", "mismatch", "confirmation",
    )
    for proposition in writer_view.get("caveated_propositions") or ():
        proposition_id = str(proposition.get("proposition_id") or "")
        if proposition_id not in rendered:
            continue
        concept_tokens = set(re.findall(
            r"[A-Za-z][A-Za-z0-9_-]+",
            " ".join(str(value) for value in proposition.values()).casefold(),
        ))
        related_sentences = [
            sentence for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
            if concept_tokens.intersection(set(re.findall(
                r"[A-Za-z][A-Za-z0-9_-]+", sentence.casefold()
            )))
        ]
        if related_sentences and not any(
            marker in sentence.casefold()
            for sentence in related_sentences for marker in caveat_markers
        ):
            uncaveated_candidate_count += 1
    unsupported_authority_count = len(_UNSUPPORTED_AUTHORITY.findall(text))
    unsafe_count = promise_count + uncaveated_candidate_count + unsupported_authority_count
    if uncaveated_candidate_count:
        failures.append("candidate_proposition_missing_visible_caveat")
    if unsupported_authority_count:
        failures.append("unsupported_authority_language")
    unrendered = len(required - rendered)
    if unrendered:
        failures.append("required_propositions_unrendered")
    packet = writer_view.get("mechanism_authoring_packet") or {}
    packet_facets = (
        packet.get("facets") if isinstance(packet, dict) else ()
    ) or ()
    required_facet_ids = {
        str(item)
        for item in (
            packet.get("required_facet_ids", ())
            if isinstance(packet, dict) else ()
        )
        if str(item).strip()
    }
    rendered_facet_ids: set[str] = set()
    text_tokens = set(re.findall(r"[^\W_]+", lowered, flags=re.UNICODE))
    for facet in packet_facets:
        if not isinstance(facet, dict):
            continue
        facet_id = str(facet.get("facet_id") or "")
        semantic_values: list[str] = [str(facet.get("exact_source_quote") or "")]
        fields = facet.get("semantic_fields") or {}
        if isinstance(fields, dict):
            for value in fields.values():
                values = value if isinstance(value, (list, tuple, set)) else (value,)
                semantic_values.extend(str(item) for item in values)
        facet_tokens = {
            token for value in semantic_values
            for token in re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE)
            if len(token) > 1
        }
        if facet_id and facet_tokens and (
            len(text_tokens & facet_tokens) / max(
                1, min(len(text_tokens), len(facet_tokens))
            ) >= 0.35
        ):
            rendered_facet_ids.add(facet_id)
    missing_facet_count = len(required_facet_ids - rendered_facet_ids)
    if missing_facet_count:
        failures.append("writer_missing_required_facets")
    missing_constraints = 0
    for constraint in writer_view.get("immutable_constraints") or ():
        for key in ("required_qualifiers", "required_numeric_tokens", "formula_renderings", "configuration_values"):
            for token in constraint.get(key) or ():
                if str(token).casefold() not in lowered:
                    missing_constraints += 1
    if missing_constraints:
        failures.append("immutable_constraints_missing")
    code_tokens = _CODE_TOKEN.findall(text)
    sentences = [
        item.strip().casefold()
        for item in re.split(r"(?<=[.!?])\s+|\n+", text)
        if item.strip() and not item.lstrip().startswith("#")
    ]
    code_trace = int(bool(sentences) and len(code_tokens) >= max(3, len(sentences) * 2))
    if code_trace:
        failures.append("code_trace_prose_not_method_language")
    duplicates = len(sentences) - len(set(sentences))
    if duplicates:
        failures.append("duplicate_method_sentences")
    return WriterRepairProgressV1(
        unsafe_uncaveated_positives=unsafe_count,
        constraint_failures=missing_constraints,
        negative_validated_propositions=-len(required & rendered),
        unrendered_required_propositions=unrendered,
        code_trace_style_failures=code_trace,
        duplicate_sentences=duplicates,
        missing_required_facets=missing_facet_count,
    ), failures


def repair_is_monotonic(incumbent: WriterRepairProgressV1, candidate: WriterRepairProgressV1) -> bool:
    if candidate.unsafe_uncaveated_positives > incumbent.unsafe_uncaveated_positives:
        return False
    if candidate.constraint_failures > incumbent.constraint_failures:
        return False
    if candidate.missing_required_facets > incumbent.missing_required_facets:
        return False
    return candidate < incumbent
