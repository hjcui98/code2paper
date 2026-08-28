"""Owning Agent for bounded final-text rewrites.

The evidence validators decide *what* is wrong.  This module owns only the
small lexical repair that is explicitly assigned to ``local_rewrite``.  The
agent returns offsets and the exact incumbent span; the harness verifies that
contract and applies the response verbatim.  It never substitutes a
projected fragment, normalizes punctuation, or inserts a deterministic
placeholder.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.research_models import TextRepairIssueV1
from code2paper.agentic.publication_quality import heading_replacement_is_coherent
from code2paper.agentic.tool_runtime import atomic_write_bytes
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.generation_trace import build_generation_call_trace
from code2paper.llm.role_config import LOCAL_REWRITE, apply_role_config
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.llm.response_schemas import (
    json_schema_for,
    try_parse_structured_response_with_trace,
)
from code2paper.schemas import LLMConfig


class LocalRewritePatchV1(BaseModel):
    """One complete replacement span returned by the Rewrite Agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    patch_id: str
    section_id: str = ""
    start: int
    end: int
    original_text: str
    replacement_text: str
    issue_ids: tuple[str, ...] = Field(min_length=1)
    allowed_scope: Literal[
        "wording_only", "sentence_atomicity", "claim_decomposition", "drop_or_gap"
    ] = "wording_only"

    @model_validator(mode="after")
    def _valid_range(self) -> "LocalRewritePatchV1":
        if self.start < 0 or self.end < self.start:
            raise ValueError("rewrite patch range is invalid")
        if not self.patch_id.strip():
            raise ValueError("rewrite patch id must not be empty")
        if not self.issue_ids:
            raise ValueError("rewrite patch must identify at least one repair issue")
        if not self.replacement_text and self.allowed_scope != "drop_or_gap":
            raise ValueError("empty replacement is only allowed for drop_or_gap")
        return self


class LocalRewriteOutputV1(BaseModel):
    """Strict content-first response contract for a local rewrite call."""

    model_config = ConfigDict(extra="forbid")

    # Multiple *disjoint* exact spans are allowed so a multi-claim paragraph
    # can be repaired sentence-by-sentence.  ``apply_local_rewrite_patches``
    # still rejects any overlap, out-of-cluster issue id, or byte mismatch,
    # so the fail-closed exact-span contract is unchanged.
    patches: tuple[LocalRewritePatchV1, ...] = Field(default_factory=tuple, max_length=8)
    self_identified_risks: tuple[str, ...] = Field(default_factory=tuple)
    incomplete: bool = False


class RepairTransitionV1(BaseModel):
    """Common transition artifact emitted by every bounded repair owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    transition_id: str
    strategy: Literal["local_rewrite", "packet_relation", "claim_decomposition", "writer"]
    owner: Literal["rewrite", "repository_tools", "writer"]
    attempt: int
    issue_ids: tuple[str, ...] = Field(default_factory=tuple)
    incumbent_digest: str
    candidate_digest: str
    status: Literal["applied", "rejected", "blocked", "no_progress"]
    reason: str = ""
    artifact_refs: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _content_digest(self) -> "RepairTransitionV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


class RewriteCallResult(BaseModel):
    """Auditable result of one Rewrite Agent call and harness application."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["applied", "rejected", "blocked", "no_progress"]
    incumbent_digest: str
    candidate_digest: str
    candidate_text: str
    output: LocalRewriteOutputV1 | None = None
    response_ref: str = ""
    blocked_reason: str = ""
    patch_failures: tuple[str, ...] = Field(default_factory=tuple)
    generation_trace: dict[str, Any] = Field(default_factory=dict)
    response_recovery_trace: dict[str, Any] = Field(default_factory=dict)


class RewriteCaller(Protocol):
    def __call__(self, config: LLMConfig, request: LLMRequest) -> LLMResponse: ...


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _default_caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
    return LLMClient(config).complete(request)


def apply_local_rewrite_patches(
    incumbent_text: str,
    patches: Iterable[LocalRewritePatchV1],
    *,
    allowed_issue_ids: set[str] | None = None,
) -> tuple[str | None, tuple[str, ...]]:
    """Apply only exact, non-overlapping response spans.

    ``None`` is returned for the candidate when any contract check fails.
    Thus a malformed or stale response can never partially mutate the draft.
    """

    patch_list = list(patches)
    failures: list[str] = []
    if allowed_issue_ids is not None:
        for patch in patch_list:
            if not set(patch.issue_ids).issubset(allowed_issue_ids):
                failures.append(f"patch:{patch.patch_id}:unknown_issue")
    ordered = sorted(patch_list, key=lambda item: (item.start, item.end, item.patch_id))
    previous_end = -1
    for patch in ordered:
        if patch.end > len(incumbent_text):
            failures.append(f"patch:{patch.patch_id}:range_out_of_bounds")
            continue
        if patch.start < previous_end:
            failures.append(f"patch:{patch.patch_id}:overlap")
        if incumbent_text[patch.start:patch.end] != patch.original_text:
            failures.append(f"patch:{patch.patch_id}:incumbent_span_mismatch")
        previous_end = max(previous_end, patch.end)
    if failures:
        return None, tuple(failures)
    candidate = incumbent_text
    for patch in sorted(patch_list, key=lambda item: item.start, reverse=True):
        candidate = candidate[:patch.start] + patch.replacement_text + candidate[patch.end:]
    return candidate, ()


def _repair_unique_patch_coordinates(
    incumbent_text: str,
    output: LocalRewriteOutputV1,
) -> tuple[LocalRewriteOutputV1, bool]:
    """Repair coordinate-only damage when the exact source span is unique.

    The model remains the lexical owner: neither ``original_text`` nor
    ``replacement_text`` is changed.  We only recompute start/end when the
    supplied original span occurs exactly once in the frozen incumbent.  An
    empty or ambiguous span is left untouched and will fail the normal patch
    contract.
    """

    repaired = False
    patches: list[LocalRewritePatchV1] = []
    for patch in output.patches:
        if incumbent_text[patch.start:patch.end] == patch.original_text:
            patches.append(patch)
            continue
        if not patch.original_text or incumbent_text.count(patch.original_text) != 1:
            patches.append(patch)
            continue
        start = incumbent_text.index(patch.original_text)
        patches.append(patch.model_copy(update={
            "start": start,
            "end": start + len(patch.original_text),
        }))
        repaired = True
    if not repaired:
        return output, False
    return output.model_copy(update={"patches": tuple(patches)}), True


def _repair_preserved_section_heading(
    incumbent_text: str,
    output: LocalRewriteOutputV1,
) -> tuple[LocalRewriteOutputV1, bool]:
    """Restore the unchanged heading omitted by a full-section model patch.

    This is representation-only recovery: the exact incumbent heading is
    retained only when the model consumes it, returns a non-empty replacement,
    and supplies no replacement heading of its own.
    """

    incumbent_lines = incumbent_text.lstrip().splitlines()
    if not incumbent_lines or not incumbent_lines[0].lstrip().startswith("#"):
        return output, False
    heading = incumbent_lines[0].strip()
    repaired = False
    patches: list[LocalRewritePatchV1] = []
    for patch in output.patches:
        replacement_lines = patch.replacement_text.lstrip().splitlines()
        consumes_heading = bool(
            patch.original_text.splitlines()
            and patch.original_text.splitlines()[0].strip() == heading
        )
        replacement_has_heading = bool(
            replacement_lines and replacement_lines[0].lstrip().startswith("#")
        )
        if consumes_heading and patch.replacement_text.strip() and not replacement_has_heading:
            patch = patch.model_copy(update={
                "replacement_text": f"{heading}\n\n{patch.replacement_text.lstrip()}",
            })
            repaired = True
        patches.append(patch)
    if not repaired:
        return output, False
    return output.model_copy(update={"patches": tuple(patches)}), True


def _candidate_readability_failures(
    incumbent_text: str,
    candidate_text: str,
    *,
    section_context: dict[str, Any] | None,
) -> tuple[str, ...]:
    """Reject safe-looking edits that collapse a Method section into debris."""

    def body(text: str) -> str:
        lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
        return " ".join(" ".join(lines).split()).strip()

    incumbent_body = body(incumbent_text)
    candidate_body = body(candidate_text)
    authority = (section_context or {}).get("writer_authority_context", {})
    candidate_points = authority.get("section_candidate_points", ())
    supported_claims = authority.get("reader_facing_claims", ())
    writer_view = authority.get("writer_view", {})
    packet = (
        writer_view.get("mechanism_authoring_packet", {})
        if isinstance(writer_view, dict) else {}
    )
    protects_section_body = bool(
        re.search(r"(?m)^#{1,6}\s+", incumbent_text)
        or candidate_points
        or supported_claims
        or (isinstance(packet, dict) and packet.get("facets"))
    )
    failures: list[str] = []
    incumbent_heading = incumbent_text.lstrip().splitlines()[:1]
    incumbent_heading = (
        incumbent_heading[0].strip()
        if incumbent_heading and incumbent_heading[0].lstrip().startswith("#")
        else ""
    )
    expected_heading = str((section_context or {}).get("writer_heading") or "").strip()
    # A rewrite may keep the incumbent heading OR repair a fused/missing
    # heading to the exact planned heading (``writer_heading``).  It can
    # never rename the heading to anything else, so the gate stays closed:
    # only the plan-authorized heading line is an acceptable replacement.
    # The one exception is a plan heading that itself is truncated mid-clause
    # (R2): completing or shortening the broken clause is an authorized
    # Writer/Rewrite generation, so a coherent replacement heading with no
    # internal ids passes while a still-truncated heading fails.
    planned_heading_line = f"## {expected_heading}" if expected_heading else ""
    required_heading_lines = {
        line
        for line in (incumbent_heading, planned_heading_line)
        if line
    }
    if required_heading_lines:
        first_line = candidate_text.lstrip().splitlines()[:1]
        first_line_text = first_line[0].strip() if first_line else ""
        if first_line_text not in required_heading_lines:
            replacement_is_coherent = bool(
                expected_heading
                and first_line_text.startswith("## ")
                and heading_replacement_is_coherent(
                    first_line_text[3:].strip(),
                    planned_heading=expected_heading,
                )
            )
            if not replacement_is_coherent:
                failures.append("candidate_removed_or_changed_section_heading")
    if protects_section_body and incumbent_body and not candidate_body:
        failures.append("candidate_body_empty")
    debris = candidate_body.lower().strip(" ,.;:-")
    if protects_section_body and debris in {"and", "or", "and and", "and or", "or and"}:
        failures.append("candidate_body_is_connective_debris")
    if protects_section_body and re.search(
        r"(?:^|\n)\s*(?:,?\s*(?:and|or)\s*)+(?:$|\n)", candidate_text, re.I
    ):
        failures.append("candidate_contains_connective_debris")
    if (
        len(incumbent_body) >= 240
        and len(candidate_body) < 80
        and len(candidate_body) < int(len(incumbent_body) * 0.18)
    ):
        failures.append("candidate_body_collapsed")
    return tuple(dict.fromkeys(failures))


def _required_facets_lost_by_empty_patches(
    incumbent_text: str,
    candidate_text: str,
    patches: Iterable[LocalRewritePatchV1],
    packet: dict[str, Any],
) -> tuple[str, ...]:
    """Return required facets whose lexical witness was deleted.

    This is a narrow local guard for empty replacements.  The publication
    transaction performs the authoritative semantic coverage check; this
    guard only prevents an obvious required-facet deletion from reaching that
    transaction.
    """

    if not any(
        not patch.replacement_text and patch.allowed_scope == "drop_or_gap"
        for patch in patches
    ):
        return ()
    required = {
        str(item).strip()
        for item in packet.get("required_facet_ids", ())
        if str(item).strip()
    }
    facets = {
        str(item.get("facet_id") or ""): item
        for item in packet.get("facets", ())
        if isinstance(item, dict) and str(item.get("facet_id") or "").strip()
    }
    if not required or not facets:
        return ()
    stop_words = {
        "a", "an", "and", "for", "in", "is", "of", "the", "to", "with",
    }

    def tokens(value: Any) -> set[str]:
        return {
            token.casefold()
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", str(value or ""))
            if token.casefold() not in stop_words
        }

    incumbent_tokens = tokens(incumbent_text)
    candidate_tokens = tokens(candidate_text)
    lost: list[str] = []
    for facet_id in sorted(required):
        facet = facets.get(facet_id)
        if facet is None:
            continue
        semantic_values = facet.get("semantic_fields") or {}
        witnesses = tokens(facet.get("exact_source_quote"))
        if isinstance(semantic_values, dict):
            for value in semantic_values.values():
                witnesses.update(tokens(value))
        if not witnesses:
            continue
        threshold = max(1, min(3, len(witnesses) // 2))
        if (
            len(incumbent_tokens & witnesses) >= threshold
            and len(candidate_tokens & witnesses) < threshold
        ):
            lost.append(facet_id)
    return tuple(lost)


@dataclass
class LocalRewriteAgent:
    """Call and validate a scoped Rewrite Agent response."""

    config: LLMConfig | None = None
    caller: RewriteCaller | None = None
    prompt_template_id: str = "agentic_local_rewrite_v1"

    def rewrite(
        self,
        incumbent_text: str,
        *,
        issues: Iterable[TextRepairIssueV1],
        section_context: dict[str, Any] | None = None,
    ) -> RewriteCallResult:
        issue_list = tuple(issues)
        incumbent_digest = _digest(incumbent_text)
        if not issue_list:
            return RewriteCallResult(
                status="no_progress",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                blocked_reason="no_rewrite_issues",
            )
        if any(
            issue.allowed_repair_scope in {"packet_relation", "code_search"}
            for issue in issue_list
        ):
            return RewriteCallResult(
                status="blocked",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                blocked_reason="rewrite_scope_not_owned_by_local_rewrite",
            )
        if (section_context or {}).get("strict_owner_routing"):
            from code2paper.agentic.publication_issue_owner_router import (
                route_publication_issues,
            )

            owner_routes = route_publication_issues(issue_list)
            wrong_owner = tuple(
                route.issue_id
                for route in owner_routes
                if route.owner != "rewrite"
            )
            if wrong_owner:
                return RewriteCallResult(
                    status="blocked",
                    incumbent_digest=incumbent_digest,
                    candidate_digest=incumbent_digest,
                    candidate_text=incumbent_text,
                    blocked_reason="wrong_owner",
                    patch_failures=tuple(
                        f"wrong_owner:{issue_id}" for issue_id in wrong_owner
                    ),
                )
        authority_context = (section_context or {}).get(
            "writer_authority_context", {}
        )
        packet = (
            authority_context.get("writer_view", {})
            if isinstance(authority_context, dict) else {}
        )
        if isinstance(packet, dict):
            packet = packet.get("mechanism_authoring_packet") or {}
        base_config = self.config or load_llm_config_from_env()
        config = apply_role_config(base_config, LOCAL_REWRITE)
        payload = {
            "incumbent_text": incumbent_text,
            "issues": [item.model_dump(mode="json") for item in issue_list],
            "section_context": section_context or {},
            "contract": {
                "replace_only_exact_spans": True,
                "preserve_unaffected_text": True,
                "do_not_invent_evidence": True,
                "return_offsets_in_incumbent_text": True,
                "do_not_resolve_authority_or_evidence_failures": True,
                "required_facet_coverage_must_not_decrease": True,
            },
        }
        method_language_instruction = (
            " For method_language_style issues, rewrite the section as a paper Method "
            "explanation: mechanisms and mathematical or data transformations are the "
            "sentence subjects; raw code identifiers are never sentence subjects or an "
            "execution inventory. Keep only the minimum exact identifiers needed as "
            "parenthetical repository bindings. A cosmetic verb swap that leaves "
            "identifier-dense prose does not resolve the issue."
            if any(issue.failure_type == "method_language_style" for issue in issue_list)
            else ""
        )
        request = LLMRequest(
            prompt_template_id=self.prompt_template_id,
            prompt=(
                "You are the owning academic Method Rewrite Agent. Return only JSON matching "
                "the schema. Diagnose each assigned issue against "
                "section_context.writer_authority_context before editing. Use that context only "
                "to preserve already-authorized semantic content and facet coverage. Use "
                "mechanisms, representations, mathematical or data transformations, assumptions, "
                "and outputs as grammatical subjects. Put only indispensable code identifiers in "
                "short parenthetical repository bindings, never as an execution inventory. Use an "
                "equation or symbol only when supplied by formalization, and never infer empirical "
                "benefit, novelty, complexity, or theory. "
                "This owner handles paper-language and local wording issues only. Evidence gaps, "
                "formula authority, missing core content, and cross-section organization belong "
                "to Research continuation, Formalizer, Writer, or Editor; do not solve them by "
                "dropping a required mechanism or replacing its subject with a code symbol. "
                "Remove generic section templates and avoid restating the complete pipeline in a "
                "component-specific section. Never leave a heading followed only by whitespace, "
                "punctuation, or connective words such as 'and'. Return one or more disjoint patches when "
                "preserving an existing candidate narrative, "
                "edits are needed: replace one complete paragraph or, when authority framing is "
                "wrong throughout, the complete section. Each patch may list every issue_id that "
                "it resolves, but only issue_ids that appear in the assigned issues payload — "
                "never section-level structure ids (e.g. 'structure:*') or ids from another "
                "repair cluster. Never return nested, overlapping, or duplicate patches. Return "
                "the exact incumbent character offsets and original_text, then the complete "
                "replacement span. original_text must be copied character-for-character from "
                "input_payload.incumbent_text at those offsets; never paraphrase, truncate, "
                "normalize whitespace, or regenerate the span. The "
                "patch MUST include a non-empty issue_ids "
                "array containing the exact atomic_claim_id from the repair issue, or its exact "
                "sentence_id when atomic_claim_id is empty, plus patch_id and "
                "allowed_scope. Never omit issue_ids or allowed_scope. Never rewrite text outside "
                "those spans, add evidence, or normalize unrelated punctuation. For wording_only, "
                "replacement_text must be non-empty and allowed_scope must be wording_only. For an "
                "empty replacement, allowed_scope MUST be drop_or_gap and every issue_id must refer "
                "only to an issue whose allowed_repair_scope is drop_or_gap; never use an empty "
                "replacement for a required mechanism facet. original_text must be the exact "
                "non-empty incumbent slice. Return an empty patches list when no safe "
                "paper-language edit is authorized."
                + method_language_instruction
            ),
            input_payload=payload,
            schema_name="LocalRewriteOutputV1",
            response_json_schema=json_schema_for(LocalRewriteOutputV1),
        )
        caller = self.caller or _default_caller
        try:
            response = caller(config, request)
        except Exception as exc:  # noqa: BLE001 - repair failure is a typed state
            return RewriteCallResult(
                status="blocked",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                blocked_reason=f"rewrite_agent_error:{exc.__class__.__name__}",
            )
        trace = build_generation_call_trace(
            call_id=f"{self.prompt_template_id}:{request.input_hash[7:19]}",
            config=config,
            request=request,
            response=response,
        ).model_dump(mode="json")
        if response.blocked_reason:
            return RewriteCallResult(
                status="blocked",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                response_ref=response.response_hash,
                blocked_reason=response.blocked_reason,
                generation_trace=trace,
            )
        parsed, recovery, error = try_parse_structured_response_with_trace(
            response.text,
            LocalRewriteOutputV1,
        )
        if parsed is None:
            return RewriteCallResult(
                status="rejected",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                response_ref=response.response_hash,
                blocked_reason=f"rewrite_schema_failed:{error}",
                patch_failures=("response_schema_invalid",),
                generation_trace=trace,
                response_recovery_trace=recovery.model_dump(mode="json"),
            )
        parsed, coordinates_repaired = _repair_unique_patch_coordinates(
            incumbent_text, parsed
        )
        parsed, heading_repaired = _repair_preserved_section_heading(
            incumbent_text, parsed
        )
        if coordinates_repaired or heading_repaired:
            recovery = recovery.model_copy(update={
                "applied": True,
                "operations": tuple(dict.fromkeys([
                    *recovery.operations,
                    *(
                        ("repair_unique_exact_span_coordinates",)
                        if coordinates_repaired else ()
                    ),
                    *(
                        ("restore_unchanged_section_heading",)
                        if heading_repaired else ()
                    ),
                ])),
            })
        scope_rank = {
            "wording_only": 0,
            "formula_rendering": 1,
            "sentence_atomicity": 2,
            "claim_decomposition": 3,
            "packet_relation": 4,
            "code_search": 5,
            "drop_or_gap": 6,
        }
        issue_by_id: dict[str, list[TextRepairIssueV1]] = {}
        for issue in issue_list:
            for issue_id in (issue.atomic_claim_id, issue.sentence_id):
                if issue_id:
                    issue_by_id.setdefault(issue_id, []).append(issue)
        scope_failures: list[str] = []
        for patch in parsed.patches:
            patch_scopes = [
                scope_rank[issue.allowed_repair_scope]
                for issue_id in patch.issue_ids
                for issue in issue_by_id.get(issue_id, ())
            ]
            # The repair contract authorizes the most permissive scope among
            # the issues it addresses (``derive_repair_issues`` /
            # ``most_permissive_scope``): a sentence whose issues include
            # ``direct_evidence_missing`` (drop_or_gap) may be dropped even
            # when another issue on the same claim is narrower.  Comparing
            # against ``min`` rejected legitimate drop repairs whenever a
            # claim carried a second, narrower issue code.
            if patch_scopes and scope_rank[patch.allowed_scope] > max(patch_scopes):
                scope_failures.append(f"patch:{patch.patch_id}:scope_exceeded")
        if scope_failures:
            return RewriteCallResult(
                status="rejected",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                output=parsed,
                response_ref=response.response_hash,
                blocked_reason="rewrite_patch_scope_failed",
                patch_failures=tuple(scope_failures),
                generation_trace=trace,
                response_recovery_trace=recovery.model_dump(mode="json"),
            )
        candidate, failures = apply_local_rewrite_patches(
            incumbent_text,
            parsed.patches,
            allowed_issue_ids={
                issue_id
                for item in issue_list
                for issue_id in (item.atomic_claim_id, item.sentence_id)
                if issue_id
            },
        )
        if candidate is None:
            return RewriteCallResult(
                status="rejected",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                output=parsed,
                response_ref=response.response_hash,
                blocked_reason="rewrite_patch_contract_failed",
                patch_failures=failures,
                generation_trace=trace,
                response_recovery_trace=recovery.model_dump(mode="json"),
            )
        readability_failures = _candidate_readability_failures(
            incumbent_text,
            candidate,
            section_context=section_context,
        )
        if readability_failures:
            return RewriteCallResult(
                status="rejected",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                output=parsed,
                response_ref=response.response_hash,
                blocked_reason="rewrite_candidate_not_readable",
                patch_failures=readability_failures,
                generation_trace=trace,
                response_recovery_trace=recovery.model_dump(mode="json"),
            )
        lost_facets = (
            _required_facets_lost_by_empty_patches(
                incumbent_text,
                candidate,
                parsed.patches,
                packet,
            )
            if isinstance(packet, dict) else ()
        )
        if lost_facets:
            return RewriteCallResult(
                status="rejected",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                output=parsed,
                response_ref=response.response_hash,
                blocked_reason="rewrite_required_facet_drop_forbidden",
                patch_failures=tuple(
                    f"required_facet_drop_forbidden:{facet_id}"
                    for facet_id in lost_facets
                ),
                generation_trace=trace,
                response_recovery_trace=recovery.model_dump(mode="json"),
            )
        status: Literal["applied", "no_progress"] = "applied" if candidate != incumbent_text else "no_progress"
        return RewriteCallResult(
            status=status,
            incumbent_digest=incumbent_digest,
            candidate_digest=_digest(candidate),
            candidate_text=candidate,
            output=parsed,
            response_ref=response.response_hash,
            blocked_reason="" if status == "applied" else "rewrite_agent_no_progress",
            generation_trace=trace,
            response_recovery_trace=recovery.model_dump(mode="json"),
        )


def write_repair_transition(path: str | Path, transition: RepairTransitionV1) -> None:
    output = Path(path)
    atomic_write_bytes(
        output,
        (transition.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )


__all__ = [
    "LocalRewriteAgent",
    "LocalRewriteOutputV1",
    "LocalRewritePatchV1",
    "RepairTransitionV1",
    "RewriteCallResult",
    "apply_local_rewrite_patches",
    "write_repair_transition",
]
