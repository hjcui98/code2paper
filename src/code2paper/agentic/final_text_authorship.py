"""Final-text lexical authorship ledger.

The evidence validators decide whether a factual span is supported.  This
module separately decides whether the final lexical span was produced by an
allowed generation owner.  Deterministic harness text can therefore not be
silently substituted for a Writer, Formalizer, Editor, or Rewrite response.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


GenerationOwnerV1 = Literal["writer", "formalizer", "editor", "rewrite"]


class GeneratedTextSpanV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    span_id: str
    text: str
    owner: GenerationOwnerV1
    response_ref: str
    section_id: str = ""
    generation_trace_id: str = ""


class AuthorshipSpanV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    final_span_id: str
    final_start: int
    final_end: int
    text_digest: str
    owner: GenerationOwnerV1
    source_span_id: str
    response_ref: str
    section_id: str = ""
    generation_trace_id: str = ""


class FinalTextAuthorshipLedgerV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    final_text_digest: str
    spans: list[AuthorshipSpanV1] = Field(default_factory=list)
    unowned_token_ranges: list[tuple[int, int]] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    hard_gate_passed: bool = False
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "FinalTextAuthorshipLedgerV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


def build_final_text_authorship_ledger(
    final_text: str,
    generated_spans: list[GeneratedTextSpanV1] | tuple[GeneratedTextSpanV1, ...],
) -> FinalTextAuthorshipLedgerV1:
    """Map generated lexical spans onto the assembled final text.

    Matching is exact and sequential.  The ledger does not normalize or
    rewrite tokens; if a final token is not covered, the hard gate fails.
    """

    final_digest = _digest(final_text)
    mapped: list[AuthorshipSpanV1] = []
    search_cursor = 0
    for span in generated_spans:
        if not span.text:
            continue
        start = final_text.find(span.text, search_cursor)
        if start < 0:
            continue
        end = start + len(span.text)
        mapped.append(AuthorshipSpanV1(
            final_span_id=f"final:{len(mapped) + 1}",
            final_start=start,
            final_end=end,
            text_digest=_digest(span.text),
            owner=span.owner,
            source_span_id=span.span_id,
            response_ref=span.response_ref,
            section_id=span.section_id,
            generation_trace_id=span.generation_trace_id,
        ))
        search_cursor = end
    owned = [False] * len(final_text)
    for span in mapped:
        for index in range(span.final_start, span.final_end):
            if index < len(owned) and not final_text[index].isspace():
                owned[index] = True
    unowned = _unowned_ranges(final_text, owned)
    failures: list[str] = []
    if not generated_spans:
        failures.append("no_generation_spans")
    if unowned:
        failures.append(f"unowned_lexical_spans:{len(unowned)}")
    previous_end = -1
    for span in mapped:
        if span.final_start < previous_end:
            failures.append("overlapping_generation_spans")
            break
        previous_end = span.final_end
    if any(not span.response_ref.strip() for span in mapped):
        failures.append("missing_generation_response_ref")
    if any(span.owner not in {"writer", "formalizer", "editor", "rewrite"} for span in mapped):
        failures.append("disallowed_generation_owner")
    return FinalTextAuthorshipLedgerV1(
        final_text_digest=final_digest,
        spans=mapped,
        unowned_token_ranges=unowned,
        failures=failures,
        hard_gate_passed=not failures,
    )


def ledger_from_section_outputs(
    final_text: str,
    sections: list[tuple[str, str, str]] | tuple[tuple[str, str, str], ...],
    *,
    owner: GenerationOwnerV1 = "writer",
) -> FinalTextAuthorshipLedgerV1:
    """Convenience adapter for ``(section_id, text, response_ref)`` outputs."""

    return build_final_text_authorship_ledger(
        final_text,
        tuple(
            GeneratedTextSpanV1(
                span_id=f"generated:{section_id}",
                text=text,
                owner=owner,
                response_ref=response_ref,
                section_id=section_id,
                generation_trace_id=response_ref,
            )
            for section_id, text, response_ref in sections
        ),
    )


def rewrite_final_text_authorship_ledger(
    *,
    incumbent_text: str,
    candidate_text: str,
    incumbent_ledger: FinalTextAuthorshipLedgerV1,
    patches: list[Any] | tuple[Any, ...],
    response_ref: str,
    generation_trace_id: str = "",
    owner: GenerationOwnerV1 = "rewrite",
) -> FinalTextAuthorshipLedgerV1:
    """Carry incumbent ownership through a verbatim owning-agent patch.

    Unaffected lexical fragments retain their original generation owner and
    response reference.  Replacement bytes are owned by the supplied response.
    The function rebuilds the ledger from exact fragments and fails closed if
    either the incumbent ledger or the candidate bytes do not authenticate.
    """

    if incumbent_ledger.final_text_digest != _digest(incumbent_text):
        raise ValueError("incumbent_authorship_digest_mismatch")
    if not incumbent_ledger.hard_gate_passed:
        raise ValueError("incumbent_authorship_gate_failed")
    if not response_ref.strip():
        raise ValueError("rewrite_response_ref_missing")
    ordered = sorted(patches, key=lambda item: (item.start, item.end, item.patch_id))
    cursor = 0
    rebuilt_text = incumbent_text
    for patch in reversed(ordered):
        rebuilt_text = rebuilt_text[:patch.start] + patch.replacement_text + rebuilt_text[patch.end:]
    if rebuilt_text != candidate_text:
        raise ValueError("rewrite_candidate_bytes_mismatch")

    generated: list[GeneratedTextSpanV1] = []
    fragment_index = 0

    def retain_interval(start: int, end: int) -> None:
        nonlocal fragment_index
        for span in incumbent_ledger.spans:
            left = max(start, span.final_start)
            right = min(end, span.final_end)
            if right <= left:
                continue
            text = incumbent_text[left:right]
            if not text:
                continue
            fragment_index += 1
            generated.append(GeneratedTextSpanV1(
                span_id=f"{span.source_span_id}:retained:{fragment_index}",
                text=text,
                owner=span.owner,
                response_ref=span.response_ref,
                section_id=span.section_id,
                generation_trace_id=span.generation_trace_id,
            ))

    for patch in ordered:
        retain_interval(cursor, patch.start)
        if patch.replacement_text:
            generated.append(GeneratedTextSpanV1(
                span_id=f"rewrite:{patch.patch_id}",
                text=patch.replacement_text,
                owner=owner,
                response_ref=response_ref,
                section_id=patch.section_id,
                generation_trace_id=generation_trace_id or response_ref,
            ))
        cursor = patch.end
    retain_interval(cursor, len(incumbent_text))
    ledger = build_final_text_authorship_ledger(candidate_text, generated)
    if not ledger.hard_gate_passed:
        raise ValueError("rewrite_authorship_gate_failed:" + ",".join(ledger.failures))
    return ledger


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unowned_ranges(text: str, owned: list[bool]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for index, char in enumerate(text):
        missing = not char.isspace() and not owned[index]
        if missing and start is None:
            start = index
        elif not missing and start is not None:
            ranges.append((start, index))
            start = None
    if start is not None:
        ranges.append((start, len(text)))
    return ranges


__all__ = [
    "AuthorshipSpanV1",
    "FinalTextAuthorshipLedgerV1",
    "GeneratedTextSpanV1",
    "GenerationOwnerV1",
    "build_final_text_authorship_ledger",
    "ledger_from_section_outputs",
    "rewrite_final_text_authorship_ledger",
]
