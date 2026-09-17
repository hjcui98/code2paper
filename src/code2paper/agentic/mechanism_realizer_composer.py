"""Two-step authoring architecture: Mechanism Realizer + Section Composer.

Implements section 5.10 of the Unified Mechanism Context Optimization Execution Plan:
1. Mechanism Realizer: Generates draft paragraph(s) per mechanism/page, fulfilling
   required details and formula packages under strict authority rules.
2. Section Composer: Assembles verified mechanism drafts, transitions, and section
   coherence without inventing technical implementation facts.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json
from code2paper.agentic.mechanism_context_models import (
    MechanismContextSliceV1,
    MechanismContextV1,
)
from code2paper.agentic.method_architect import (
    NarrativeSectionPlanV3,
)
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.llm.response_schemas import (
    PublicationContentWitnessV1,
    PublicationFormulaDispositionV1,
    PublicationMethodParagraphOutputV1,
    PublicationMethodSectionOutputV1,
)
from code2paper.schemas import LLMConfig


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _canonical_v2_detail_id(value: Any) -> str:
    """Use the prefixed detail identity at the V2 Realizer boundary."""

    text = str(value or "").strip()
    if not text:
        return ""
    return "detail:" + text.removeprefix("detail:")


class MechanismDraftV1(BaseModel):
    """Scoped draft for one mechanism or mechanism page."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draft_id: str
    mechanism_id: str
    page_index: int = 0
    heading: str = ""
    draft_markdown: str = ""
    required_detail_ids: tuple[str, ...] = Field(default_factory=tuple)
    realized_detail_ids: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_detail_ids: tuple[str, ...] = Field(default_factory=tuple)
    formula_package_ids: tuple[str, ...] = Field(default_factory=tuple)
    authority_disposition: str = "repository_verified"
    witness_atoms: tuple[str, ...] = Field(default_factory=tuple)
    witnesses: tuple[PublicationContentWitnessV1, ...] = Field(default_factory=tuple)
    status: str = "blocked"
    blocked_reason: str = ""
    request_digest: str = ""
    representation_diff_class: str = "none"
    # Deterministic, page-local repair hints returned with a blocked draft.
    # They are not publication text or authority; they identify the failed
    # witness binding and the frozen source excerpts that the owning Realizer
    # may use on its one bounded content-repair attempt.
    repair_feedback: tuple[Mapping[str, Any], ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "MechanismDraftV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = digest_json(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"mechanism draft content_digest mismatch: got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


class SectionCompositionV1(BaseModel):
    """Full section composed strictly from verified mechanism drafts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    heading: str
    section_markdown: str
    paragraphs: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    used_mechanism_draft_ids: tuple[str, ...] = Field(default_factory=tuple)
    status: str = "blocked"
    blocked_reason: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "SectionCompositionV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = digest_json(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"section composition content_digest mismatch: got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


def sanitize_representation_only(text: str) -> tuple[str, str]:
    """Sanitize representation shell (control characters, unicode clean) without changing semantics.

    Returns (cleaned_text, diff_class).
    diff_class is 'none' if unchanged, or 'control_chars_removed'.
    """
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    diff_class = "none" if cleaned == text else "control_chars_removed"
    return cleaned, diff_class


def _representation_tokens(value: Any) -> tuple[str, ...]:
    """Tokenize prose/code while treating safe display variants as equivalent.

    Some JSON-native providers double-escape a newline inside a Markdown code
    span (``\\n``) while emitting the witness as ordinary spaces.  This helper
    also treats ASCII and typographic quotation marks as the same display
    representation.  It is used only for a representation-only comparison;
    the returned witness is always taken from the already frozen draft body.
    """

    text = str(value or "")
    text = re.sub(r"\\(?:r\\n|n|r|t)", " ", text)
    text = text.translate(str.maketrans({
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }))
    return tuple(re.findall(r"\S+", text))


def _representation_token_pattern(token: str) -> str:
    """Build a body matcher for one normalized token.

    The match may accept only the four common typographic quote variants for
    their ASCII counterparts.  Returning the matched body substring preserves
    the model's own bytes and therefore cannot synthesize or rewrite prose.
    """

    quote_variants = {
        "'": "['\\u2018\\u2019]",
        '"': '["\\u201c\\u201d]',
    }
    return "".join(
        quote_variants.get(character, re.escape(character))
        for character in token
    )


def _unique_representation_substring(
    body: str,
    candidate: str,
) -> str:
    """Return a unique body substring equal modulo whitespace representation."""

    tokens = _representation_tokens(candidate)
    if not tokens:
        return ""
    separator = r"(?:\s|\\(?:r\\n|n|r|t))+"
    pattern = separator.join(
        _representation_token_pattern(token) for token in tokens
    )
    matches = tuple(re.finditer(pattern, body, flags=re.DOTALL))
    if len(matches) != 1:
        return ""
    return matches[0].group(0)


def _unique_conditional_line_excerpt(
    raw_detail: Mapping[str, Any],
    nested_atoms: Sequence[Any],
) -> str:
    """Select one exact guard line from a larger frozen conditional span.

    A detail source span may contain an entire branch body even though the
    detail itself binds only the branch condition.  Requiring that whole span
    as one publication witness makes a bounded repair copy unrelated body
    lines.  This helper narrows only when the immutable detail/atom contract
    names every condition and exactly one source line contains all of them.
    The returned value is an unchanged substring of the frozen excerpt; an
    ambiguous or multiline condition keeps the original full-span fallback.
    """

    if str(raw_detail.get("role", "")) not in {"branch", "condition"}:
        return ""

    condition_groups: list[tuple[str, ...]] = []
    detail_conditions = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in (raw_detail.get("conditions", ()) or ())
            if str(value).strip()
        )
    )
    if detail_conditions:
        condition_groups.append(detail_conditions)
    for raw_atom in nested_atoms:
        if not isinstance(raw_atom, Mapping):
            continue
        if str(raw_atom.get("atom_kind", "")) != "condition":
            continue
        atom_conditions = tuple(
            dict.fromkeys(
                str(value).strip()
                for value in (raw_atom.get("required_conditions", ()) or ())
                if str(value).strip()
            )
        )
        if atom_conditions and atom_conditions not in condition_groups:
            condition_groups.append(atom_conditions)
    if not condition_groups:
        return ""

    # Conditions are expressions, not substrings: ``cfg.enabled`` must not
    # match ``cfg.enabled_extra`` or a comment/string mentioning the flag.
    # Every declared condition must survive narrowing, including enclosing
    # conditions carried only by the detail or only by a nested atom.
    def conjuncts(node: ast.AST) -> set[str]:
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
            return {part for value in node.values for part in conjuncts(value)}
        return {ast.dump(node)}

    try:
        required_expressions = {
            part
            for group in condition_groups for condition in group
            for part in conjuncts(ast.parse(condition, mode="eval").body)
        }
    except (SyntaxError, ValueError):
        return ""

    candidates: list[str] = []
    seen_excerpts: set[str] = set()
    for raw_atom in nested_atoms:
        if not isinstance(raw_atom, Mapping):
            continue
        for raw_excerpt in (raw_atom.get("exact_excerpts", ()) or ()):
            excerpt = str(raw_excerpt)
            if excerpt in seen_excerpts:
                continue
            seen_excerpts.add(excerpt)
            for raw_line in excerpt.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                parse_line = re.sub(r"^elif\b", "if", line)
                try:
                    statement = ast.parse(parse_line + "\n    pass").body
                except (SyntaxError, ValueError):
                    continue
                if len(statement) != 1 or not isinstance(statement[0], (ast.If, ast.While)):
                    continue
                expressions = conjuncts(statement[0].test)
                if required_expressions == expressions:
                    candidates.append(line)
    return candidates[0] if len(candidates) == 1 else ""


class MechanismRealizer:
    """Step 1: Realizes mechanism-level draft prose bound to delivered details and formulas."""

    def __init__(self, llm_config: LLMConfig | None = None) -> None:
        self.llm_config = llm_config

    def realize_draft(
        self,
        *,
        context: MechanismContextV1,
        page_index: int = 0,
        page_slice: MechanismContextSliceV1 | None = None,
        formula_packages: Sequence[Any] = (),
        caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
        # V2 callers pass the immutable ConsumerTechnicalPageV2 and its
        # frozen invocation.  The old ``page_slice`` surface remains for V1
        # compatibility, but it is never used to reconstruct a V2 request.
        consumer_page: Any | None = None,
        consumer_invocation: Any | None = None,
        required_detail_ids: Sequence[str] | None = None,
        section_id: str = "",
        repair_feedback: Sequence[Mapping[str, Any]] | None = None,
    ) -> MechanismDraftV1:
        """Generate one page draft through the authorized Writer caller.

        The harness may assemble the request envelope and validate the
        response, but it may not author technical sentences or witnesses.  A
        missing caller, malformed response, or incomplete witness set returns
        a blocked draft with no realized details and no publication text.
        """
        mech_id = str(context.mechanism_id)
        v2_detail_ids = consumer_page is not None

        def detail_id(value: Any) -> str:
            return (
                _canonical_v2_detail_id(value)
                if v2_detail_ids
                else str(value).strip()
            )

        details = list(context.details)
        if required_detail_ids is not None:
            requested_detail_ids = {
                detail_id(value)
                for value in required_detail_ids
                if str(value).strip()
            }
            details = [
                detail for detail in details
                if detail_id(detail.detail_id) in requested_detail_ids
            ]
        elif consumer_page is not None:
            # A V2 page carries archive atom markers.  Derive the local detail
            # closure from those markers instead of handing the Realizer the
            # whole mechanism context.
            page_atom_ids = {
                str(raw.get("_atom_id", ""))
                for raw in (
                    getattr(consumer_page, "technical_payload", {}).get("atoms", ())
                    if isinstance(getattr(consumer_page, "technical_payload", {}), Mapping)
                    else ()
                )
                if isinstance(raw, Mapping)
            }
            requested_detail_ids = {
                _canonical_v2_detail_id(atom_id)
                for atom_id in page_atom_ids
                if atom_id.startswith("detail:")
            }
            details = [
                detail for detail in details
                if detail_id(detail.detail_id) in requested_detail_ids
            ]
        elif page_slice is not None:
            slice_dids = {str(d) for d in (getattr(page_slice, "detail_ids", ()) or ())}
            details = [d for d in details if str(d.detail_id) in slice_dids]

        required_dids = tuple(detail_id(d.detail_id) for d in details)
        pkg_ids = tuple(
            str(getattr(pkg, "package_id", ""))
            for pkg in formula_packages
            if consumer_page is not None
            or str(getattr(pkg, "mechanism_id", "")) == mech_id
        )

        # Classify overall authority disposition for the response contract;
        # this value is not a license to synthesize prose.
        authorities = {str(d.evidence_authority) for d in details}
        unresolved_details = tuple(
            detail for detail in details
            if str(detail.evidence_authority) == "unresolved"
        )
        partial_unresolved_ids = tuple(
            detail_id(detail.detail_id) for detail in unresolved_details
        )

        def is_conditional_partial(detail: Any) -> bool:
            return bool(
                str(getattr(detail, "role", "")) == "branch"
                and str(getattr(detail, "polarity", "")) == "conditional"
                and str(getattr(detail, "source_kind", ""))
                == "first_party_executable"
                and bool(getattr(detail, "conditions", ()) or ())
                and str(getattr(detail, "semantic_atom", "")).startswith("branch:")
            )

        if "repo_mismatch" in authorities:
            authority = "repo_mismatch_flagged"
        elif "unresolved" in authorities:
            # A branch whose code span is frozen but whose selected
            # configuration value remains unresolved is a legitimate
            # Candidate-side qualified partial.  It may be rendered only as
            # a conditional/annotated branch; it is never promoted to a
            # repository-verified active path.  Other unresolved details stay
            # fail-closed and return to the owning evidence lane.
            authority = (
                "qualified_partial"
                if unresolved_details
                and all(is_conditional_partial(item) for item in unresolved_details)
                else "unresolved"
            )
        elif "author_spec_only" in authorities and "repository_verified" not in authorities:
            authority = "author_spec_only"
        elif "repository_partial" in authorities or "implemented_partial" in authorities:
            authority = "qualified_partial"
        else:
            authority = "repository_verified"

        normalized_repair_feedback = tuple(
            dict(item)
            for item in (repair_feedback or ())
            if isinstance(item, Mapping)
        )

        def blocked(
            reason: str,
            *,
            request_digest: str = "",
            repair_items: Sequence[Mapping[str, Any]] = (),
        ) -> MechanismDraftV1:
            return MechanismDraftV1(
                draft_id=f"draft:{mech_id}:p{page_index}",
                mechanism_id=mech_id,
                page_index=page_index,
                heading=str(getattr(context, "mechanism_name", "") or getattr(context, "name", "") or mech_id),
                draft_markdown="",
                required_detail_ids=required_dids,
                realized_detail_ids=(),
                unresolved_detail_ids=partial_unresolved_ids,
                formula_package_ids=(),
                authority_disposition=authority,
                witness_atoms=(),
                witnesses=(),
                status="blocked",
                blocked_reason=reason,
                request_digest=request_digest,
                repair_feedback=tuple(
                    dict(item)
                    for item in (repair_items or normalized_repair_feedback)
                    if isinstance(item, Mapping)
                ),
            )

        if caller is None or self.llm_config is None:
            return blocked("realizer_caller_missing")
        if authority in {"repo_mismatch_flagged", "unresolved"}:
            # A model may not choose a nicer wording for an unresolved or
            # contradictory source.  Route it back to the owning evidence /
            # callback lane instead of allowing an accepted draft to carry
            # positive implementation prose.
            return blocked(f"realizer_authority_{authority}")

        package_by_id = {
            str(getattr(pkg, "package_id", "")): pkg
            for pkg in formula_packages
            if str(getattr(pkg, "mechanism_id", "")) == mech_id
            and str(getattr(pkg, "package_id", ""))
        }
        if page_slice is not None:
            page_bytes = page_slice.serialized_payload
        elif hasattr(context, "model_dump"):
            page_bytes = json.dumps(
                context.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        elif isinstance(context, Mapping):
            page_bytes = json.dumps(
                dict(context),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        else:
            context_dict = {
                "mechanism_id": str(getattr(context, "mechanism_id", "")),
                "mechanism_name": str(getattr(context, "mechanism_name", "")),
                "details": [
                    d.model_dump(mode="json") if hasattr(d, "model_dump") else dict(d)
                    for d in (getattr(context, "details", ()) or ())
                ],
            }
            page_bytes = json.dumps(
                context_dict,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        allowed_atoms = {
            str(atom.atom_id)
            for detail in details
            for atom in getattr(detail, "witness_atoms", ()) or ()
            if str(atom.atom_id).strip()
        }
        incumbent_witnesses_by_target: dict[
            tuple[str, str], PublicationContentWitnessV1
        ] = {}
        if consumer_page is not None:
            # V2 request identity is deliberately produced by the same
            # canonical helper as the invocation-plan compiler.  The full
            # writer/narrative payload is not merged into the technical page;
            # the page itself remains the only technical authority crossing
            # this Realizer boundary.
            page_payload = getattr(consumer_page, "technical_payload", {})
            if isinstance(page_payload, Mapping):
                for raw in (page_payload.get("atoms", ()) or ()):
                    if not isinstance(raw, Mapping):
                        continue
                    atom_id = str(raw.get("_atom_id", "")).strip()
                    if atom_id and str(raw.get("_atom_kind", "")) != "detail":
                        allowed_atoms.add(atom_id)
                    for raw_atom in (raw.get("witness_atoms", ()) or ()):
                        if not isinstance(raw_atom, Mapping):
                            continue
                        nested_id = str(raw_atom.get("atom_id", "")).strip()
                        if nested_id:
                            allowed_atoms.add(nested_id)

            incumbent_drafts = tuple(dict.fromkeys(
                str(item.get("previous_draft_markdown") or "")
                for item in normalized_repair_feedback
                if str(item.get("previous_draft_markdown") or "")
            ))
            for feedback_item in normalized_repair_feedback:
                for raw_witness in (
                    feedback_item.get("validated_incumbent_witnesses", ()) or ()
                ):
                    if not isinstance(raw_witness, Mapping):
                        return blocked("realizer_incumbent_witness_invalid")
                    witness_payload = dict(raw_witness)
                    if str(witness_payload.get("witness_kind", "")) == "detail":
                        witness_payload["target_id"] = detail_id(
                            witness_payload.get("target_id", "")
                        )
                    try:
                        incumbent_witness = PublicationContentWitnessV1.model_validate(
                            witness_payload
                        )
                    except Exception:
                        return blocked("realizer_incumbent_witness_invalid")
                    if (
                        incumbent_witness.witness_kind == "detail"
                        and incumbent_witness.target_id not in set(required_dids)
                    ):
                        return blocked("realizer_incumbent_detail_witness_out_of_scope")
                    if (
                        incumbent_witness.witness_kind == "atom"
                        and incumbent_witness.target_id not in allowed_atoms
                    ):
                        return blocked("realizer_incumbent_atom_witness_out_of_scope")
                    if (
                        incumbent_witness.witness_kind == "formula"
                        and incumbent_witness.target_id not in set(pkg_ids)
                    ):
                        return blocked("realizer_incumbent_formula_witness_out_of_scope")
                    key = (
                        incumbent_witness.witness_kind,
                        incumbent_witness.target_id,
                    )
                    previous = incumbent_witnesses_by_target.get(key)
                    if previous is not None and previous.exact_text != incumbent_witness.exact_text:
                        return blocked("realizer_incumbent_witness_conflict")
                    incumbent_witnesses_by_target[key] = incumbent_witness
            if incumbent_witnesses_by_target:
                if len(incumbent_drafts) != 1:
                    return blocked("realizer_incumbent_draft_invalid")
                incumbent_markdown = incumbent_drafts[0]
                if any(
                    witness.exact_text not in incumbent_markdown
                    for witness in incumbent_witnesses_by_target.values()
                ):
                    return blocked("realizer_incumbent_witness_text_missing")
            from code2paper.agentic.unified_context_compiler import (
                build_consumer_request_payload,
                consumer_response_json_schema,
                render_consumer_page_prompt,
            )

            invocation_section_id = str(
                section_id
                or getattr(consumer_invocation, "section_id", "")
                or getattr(consumer_page, "technical_payload", {}).get("section_id", "")
            )
            task_ids = tuple(
                str(value)
                for value in (
                    getattr(consumer_invocation, "task_ids", ())
                    or ((invocation_section_id,) if invocation_section_id else ())
                )
                if str(value).strip()
            )
            request_payload = build_consumer_request_payload(
                page=consumer_page,
                role="realizer",
                task_ids=task_ids,
                section_id=invocation_section_id,
                repair_feedback=normalized_repair_feedback,
            )
            prompt = render_consumer_page_prompt(
                page=consumer_page,
                role="realizer",
                task_ids=task_ids,
                section_id=invocation_section_id,
                repair_feedback=normalized_repair_feedback,
            )
            response_json_schema = consumer_response_json_schema("realizer")
            request = LLMRequest(
                prompt_template_id="unified_realizer_page_v2",
                prompt=prompt,
                input_payload=request_payload,
                schema_name="unified_consumer_response_v2",
                response_json_schema=response_json_schema,
            )
        else:
            prompt = (
                "You are the Mechanism Realizer. Return JSON only.\n"
                f"Mechanism ID: {mech_id}\n"
                f"Page index: {page_index}\n"
                f"Required detail IDs: {list(required_dids)}\n"
                f"Required formula package IDs: {list(pkg_ids)}\n"
                "Use only the supplied page bytes and formula package IDs. Do not invent facts.\n"
                "Return draft_markdown, rendered_detail_ids, used_formula_package_ids, "
                "and witnesses with witness_kind/target_id/exact_text.\n"
                f"Shared page bytes (UTF-8 JSON): {page_bytes.decode('utf-8', errors='strict')}\n"
            )
            request = LLMRequest(
                prompt_template_id="phase5_mechanism_realizer_v1",
                prompt=prompt,
                input_payload={
                    "mechanism_id": mech_id,
                    "page_index": page_index,
                    "required_detail_ids": list(required_dids),
                    "required_formula_package_ids": list(pkg_ids),
                    "shared_page_bytes": page_bytes.decode("utf-8"),
                },
            )
        request_digest = request.input_hash
        try:
            if consumer_invocation is not None:
                from code2paper.agentic.unified_context_compiler import (
                    bound_consumer_llm_config,
                )

                consumer_config = bound_consumer_llm_config(
                    self.llm_config,
                    consumer_invocation,
                )
            else:
                consumer_config = self.llm_config
            response = caller(consumer_config, request)
        except Exception as exc:
            return blocked(f"realizer_call_error:{type(exc).__name__}", request_digest=request_digest)
        if response is None or response.blocked_reason or not (response.text or "").strip():
            return blocked(
                f"realizer_response_blocked:{getattr(response, 'blocked_reason', '') or 'empty'}",
                request_digest=request_digest,
            )
        try:
            payload = json.loads(response.text)
        except (TypeError, json.JSONDecodeError):
            # Representation-only recovery for providers that wrap an
            # otherwise complete structured response in a Markdown fence.
            # A complete fence is required; truncated or arbitrary JSON-like
            # substrings remain blocked and cannot be safely reconstructed.
            fenced = re.fullmatch(
                r"\s*```(?:json)?\s*(.*?)\s*```\s*",
                str(response.text or ""),
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not fenced:
                return blocked(
                    "realizer_response_not_json",
                    request_digest=request_digest,
                    repair_items=({
                        "failure_code": "realizer_response_not_json",
                        "witness_kind": "",
                        "target_id": "",
                        "source_exact_excerpts": (),
                        "previous_draft_markdown": "",
                    },),
                )
            try:
                payload = json.loads(fenced.group(1))
            except (TypeError, json.JSONDecodeError):
                return blocked(
                    "realizer_response_not_json",
                    request_digest=request_digest,
                    repair_items=({
                        "failure_code": "realizer_response_not_json",
                        "witness_kind": "",
                        "target_id": "",
                        "source_exact_excerpts": (),
                        "previous_draft_markdown": "",
                    },),
                )
        if not isinstance(payload, Mapping):
            return blocked(
                "realizer_response_not_object",
                request_digest=request_digest,
                repair_items=({
                    "failure_code": "realizer_response_not_object",
                    "witness_kind": "",
                    "target_id": "",
                    "source_exact_excerpts": (),
                    "previous_draft_markdown": "",
                },),
            )
        markdown = str(payload.get("draft_markdown") or payload.get("section_markdown") or "").strip()
        rendered = tuple(dict.fromkeys(
            detail_id(value)
            for value in (payload.get("rendered_detail_ids") or ())
            if str(value).strip()
        ))
        used_packages = tuple(dict.fromkeys(
            str(value).strip() for value in (payload.get("used_formula_package_ids") or ())
            if str(value).strip()
        ))
        if not markdown:
            return blocked("realizer_markdown_empty", request_digest=request_digest)
        if set(rendered) - set(required_dids):
            return blocked("realizer_detail_out_of_scope", request_digest=request_digest)
        if set(used_packages) - set(pkg_ids):
            return blocked("realizer_formula_out_of_scope", request_digest=request_digest)
        if set(required_dids) - set(rendered):
            return blocked("realizer_required_detail_missing", request_digest=request_digest)
        if set(pkg_ids) - set(used_packages):
            return blocked("realizer_required_formula_missing", request_digest=request_digest)

        def source_exact_excerpts(target_id: str, witness_kind: str) -> tuple[str, ...]:
            """Return frozen source excerpts for one page-local witness target.

            This is intentionally a page-payload lookup, not a reconstruction
            from the model response or a source-file read.  It gives the
            representation-only recovery below a closed, immutable authority
            set and prevents a malformed witness from being repaired with
            newly authored text.
            """

            if consumer_page is None:
                return ()
            page_payload = getattr(consumer_page, "technical_payload", {})
            if not isinstance(page_payload, Mapping):
                return ()
            excerpts: list[str] = []
            for raw_detail in (page_payload.get("atoms", ()) or ()):
                if not isinstance(raw_detail, Mapping):
                    continue
                detail_target = _canonical_v2_detail_id(
                    raw_detail.get("detail_id") or raw_detail.get("_atom_id")
                )
                nested_atoms = raw_detail.get("witness_atoms", ()) or ()
                if witness_kind == "detail" and detail_target == target_id:
                    conditional_line = _unique_conditional_line_excerpt(
                        raw_detail, nested_atoms
                    )
                    if conditional_line:
                        return (conditional_line,)
                    nested_candidates = nested_atoms
                elif witness_kind == "atom":
                    nested_candidates = (
                        raw_atom
                        for raw_atom in nested_atoms
                        if isinstance(raw_atom, Mapping)
                        and str(raw_atom.get("atom_id", "")).strip() == target_id
                    )
                elif witness_kind == "formula":
                    package = package_by_id.get(target_id)
                    package_detail_values = (
                        package.get("source_detail_ids", ())
                        if isinstance(package, Mapping)
                        else getattr(package, "source_detail_ids", ())
                        if package is not None
                        else ()
                    ) or ()
                    package_detail_ids = {
                        _canonical_v2_detail_id(value)
                        for value in package_detail_values
                        if str(value).strip()
                    }
                    nested_candidates = (
                        nested_atoms
                        if detail_target in package_detail_ids
                        else ()
                    )
                else:
                    nested_candidates = ()
                for raw_atom in nested_candidates:
                    if not isinstance(raw_atom, Mapping):
                        continue
                    for raw_excerpt in (raw_atom.get("exact_excerpts", ()) or ()):
                        excerpt = str(raw_excerpt)
                        if excerpt and excerpt not in excerpts:
                            excerpts.append(excerpt)
            return tuple(excerpts)

        representation_witness_repairs = 0
        whitespace_witness_repairs = 0
        raw_witnesses = payload.get("witnesses") or ()
        witnesses: list[PublicationContentWitnessV1] = []
        missing_witness_repairs: list[dict[str, Any]] = []
        for raw in raw_witnesses:
            if not isinstance(raw, Mapping):
                return blocked("realizer_witness_not_object", request_digest=request_digest)
            witness_payload = dict(raw)
            if (
                v2_detail_ids
                and str(witness_payload.get("witness_kind", "")) == "detail"
            ):
                witness_payload["target_id"] = detail_id(
                    witness_payload.get("target_id", "")
                )
            witness_kind = str(witness_payload.get("witness_kind", ""))
            witness_target = str(witness_payload.get("target_id", "")).strip()
            witness_exact_text = str(witness_payload.get("exact_text", ""))
            source_excerpts: tuple[str, ...] = ()
            if witness_exact_text.strip() and witness_exact_text not in markdown:
                # The provider may copy a source line into a code block while
                # normalizing its indentation/newlines in the witness field.
                # If that representation maps to exactly one substring of the
                # model's own draft, bind to those draft bytes directly.  It
                # is representation-only recovery and is valid for formula
                # witnesses whose package source-detail closure is carried by
                # the technical page.
                direct_match = _unique_representation_substring(
                    markdown, witness_exact_text
                )
                if direct_match:
                    witness_payload["exact_text"] = direct_match
                    whitespace_witness_repairs += 1
                    witness_exact_text = direct_match
                else:
                    # Qwen occasionally preserves the source meaning while
                    # changing quote/indentation characters in ``exact_text``.
                    # Recover only a representation mismatch when the exact
                    # source excerpt for this same frozen target is already an
                    # unchanged substring of the model's own draft.  This
                    # never invents prose, expands scope, or turns an invalid
                    # target into an allowed one.
                    source_excerpts = source_exact_excerpts(
                        witness_target, witness_kind
                    )
                    candidates = tuple(
                        excerpt for excerpt in source_excerpts if excerpt in markdown
                    )
                    if candidates:
                        witness_payload["exact_text"] = sorted(
                            set(candidates), key=lambda value: (-len(value), value)
                        )[0]
                        representation_witness_repairs += 1
                    else:
                        # A JSON provider can preserve the same source excerpt in
                        # the draft while serializing a newline as the literal
                        # two-character sequence ``\\n``.  Allow only the
                        # whitespace-equivalent case: the model witness and one
                        # frozen source excerpt must have identical non-whitespace
                        # tokens, and that excerpt must map to exactly one body
                        # substring.  The replacement is the body's own bytes;
                        # no prose or authority is synthesized.
                        witness_tokens = _representation_tokens(witness_exact_text)
                        equivalent_matches: list[str] = []
                        for excerpt in source_excerpts:
                            if _representation_tokens(excerpt) != witness_tokens:
                                continue
                            match = _unique_representation_substring(markdown, excerpt)
                            if match:
                                equivalent_matches.append(match)
                        unique_matches = tuple(dict.fromkeys(equivalent_matches))
                        if len(unique_matches) == 1:
                            witness_payload["exact_text"] = unique_matches[0]
                            whitespace_witness_repairs += 1
            try:
                witness = PublicationContentWitnessV1.model_validate(witness_payload)
            except Exception:
                return blocked("realizer_witness_invalid", request_digest=request_digest)
            if witness.witness_kind == "detail" and witness.target_id not in set(required_dids):
                return blocked("realizer_detail_witness_out_of_scope", request_digest=request_digest)
            if witness.witness_kind == "atom" and witness.target_id not in allowed_atoms:
                return blocked("realizer_atom_witness_out_of_scope", request_digest=request_digest)
            if witness.witness_kind == "formula" and witness.target_id not in set(pkg_ids):
                return blocked("realizer_formula_witness_out_of_scope", request_digest=request_digest)
            if not witness.exact_text.strip() or witness.exact_text not in markdown:
                if not source_excerpts:
                    source_excerpts = source_exact_excerpts(
                        witness.target_id, witness.witness_kind
                    )
                missing_witness_repairs.append({
                    "failure_code": "realizer_witness_text_missing",
                    "witness_kind": witness.witness_kind,
                    "target_id": witness.target_id,
                    "source_exact_excerpts": list(source_excerpts),
                    "previous_draft_markdown": markdown,
                })
                continue
            witnesses.append(witness)

        # A bounded repair may omit metadata for incumbent witnesses that the
        # previous attempt already bound successfully.  Carry those model-
        # authored mappings only when their exact bytes still occur in both
        # the prior and repaired drafts.  Any rewritten or removed witness is
        # left unsatisfied and returns to the Realizer; no prose is generated
        # or rebound by the harness.
        current_witness_keys = {
            (item.witness_kind, item.target_id) for item in witnesses
        }
        carried_incumbent_witnesses = 0
        for key, incumbent_witness in incumbent_witnesses_by_target.items():
            if key in current_witness_keys:
                continue
            if incumbent_witness.exact_text not in markdown:
                continue
            witnesses.append(incumbent_witness)
            current_witness_keys.add(key)
            carried_incumbent_witnesses += 1
        if current_witness_keys:
            missing_witness_repairs = [
                item
                for item in missing_witness_repairs
                if (str(item.get("witness_kind", "")), str(item.get("target_id", "")))
                not in current_witness_keys
            ]

        def preserve_validated_witnesses(
            repair_items: Sequence[Mapping[str, Any]],
        ) -> tuple[dict[str, Any], ...]:
            items = [dict(item) for item in repair_items]
            if items and witnesses:
                items[0]["validated_incumbent_witnesses"] = [
                    witness.model_dump(mode="json") for witness in witnesses
                ]
            return tuple(items)

        if missing_witness_repairs:
            return blocked(
                "realizer_witness_text_missing",
                request_digest=request_digest,
                repair_items=preserve_validated_witnesses(
                    missing_witness_repairs
                ),
            )
        required_witness_targets = set(required_dids) | set(pkg_ids)
        witnessed_targets = {item.target_id for item in witnesses}
        if required_witness_targets - witnessed_targets:
            repair_items = []
            for target_id in sorted(required_witness_targets - witnessed_targets):
                target_kind = "formula" if target_id in set(pkg_ids) else "detail"
                repair_items.append({
                    "failure_code": "realizer_required_witness_missing",
                    "witness_kind": target_kind,
                    "target_id": target_id,
                    "source_exact_excerpts": list(
                        source_exact_excerpts(target_id, target_kind)
                    ),
                    "previous_draft_markdown": markdown,
                })
            return blocked(
                "realizer_required_witness_missing",
                request_digest=request_digest,
                repair_items=preserve_validated_witnesses(repair_items),
            )
        cleaned_draft, diff_class = sanitize_representation_only(markdown)
        if representation_witness_repairs:
            diff_class = (
                f"{diff_class}+witness_exact_text_repaired"
                if diff_class != "none"
                else "witness_exact_text_repaired"
            )
        if whitespace_witness_repairs:
            diff_class = (
                f"{diff_class}+witness_exact_text_whitespace_repaired"
                if diff_class != "none"
                else "witness_exact_text_whitespace_repaired"
            )
        if carried_incumbent_witnesses:
            diff_class = (
                f"{diff_class}+incumbent_witnesses_revalidated"
                if diff_class != "none"
                else "incumbent_witnesses_revalidated"
            )
        return MechanismDraftV1(
            draft_id=f"draft:{mech_id}:p{page_index}",
            mechanism_id=mech_id,
            page_index=page_index,
            heading=str(getattr(context, "mechanism_name", "") or getattr(context, "name", "") or mech_id),
            draft_markdown=cleaned_draft,
            required_detail_ids=required_dids,
            realized_detail_ids=rendered,
            unresolved_detail_ids=partial_unresolved_ids,
            formula_package_ids=used_packages,
            authority_disposition=authority,
            witness_atoms=tuple(
                item.target_id for item in witnesses if item.witness_kind == "atom"
            ),
            witnesses=tuple(witnesses),
            status="accepted",
            request_digest=request_digest,
            representation_diff_class=diff_class,
        )


class SectionComposer:
    """Step 2: Composes complete section markdown from verified mechanism drafts."""

    def __init__(self, llm_config: LLMConfig | None = None) -> None:
        self.llm_config = llm_config

    def compose_section(
        self,
        *,
        section_plan: NarrativeSectionPlanV3,
        drafts: Sequence[MechanismDraftV1],
        caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    ) -> SectionCompositionV1:
        """Assemble mechanism drafts into structured section markdown."""
        sec_id = str(section_plan.section_id)
        heading = str(section_plan.heading or "Method")

        relevant_drafts = [
            d for d in drafts
            if d.mechanism_id in section_plan.mechanism_ids
            and d.status == "accepted"
            and bool(d.draft_markdown.strip())
        ]
        used_ids = tuple(d.draft_id for d in relevant_drafts)

        paragraphs: list[dict[str, Any]] = []
        p_markdowns: list[str] = []

        for idx, draft in enumerate(relevant_drafts, start=1):
            pid = f"{sec_id}_p{idx}"
            p_markdowns.append(draft.draft_markdown)
            paragraphs.append({
                "paragraph_id": pid,
                "paragraph_markdown": draft.draft_markdown,
                "mechanism_id": draft.mechanism_id,
                "draft_id": draft.draft_id,
                "realized_detail_ids": list(draft.realized_detail_ids),
                "formula_package_ids": list(draft.formula_package_ids),
                "authority_disposition": draft.authority_disposition,
            })

        if not p_markdowns:
            return SectionCompositionV1(
                section_id=sec_id,
                heading=heading,
                section_markdown="",
                paragraphs=(),
                used_mechanism_draft_ids=(),
                status="blocked",
                blocked_reason="no_accepted_mechanism_draft",
            )

        full_markdown = f"## {heading}\n\n" + "\n\n".join(p_markdowns)
        cleaned_markdown, _ = sanitize_representation_only(full_markdown)

        return SectionCompositionV1(
            section_id=sec_id,
            heading=heading,
            section_markdown=cleaned_markdown,
            paragraphs=tuple(paragraphs),
            used_mechanism_draft_ids=used_ids,
            status="accepted",
        )

    def compose_publication_section(
        self,
        *,
        section_plan: Any,
        drafts: Sequence[MechanismDraftV1] = (),
        contexts: Sequence[MechanismContextV1] = (),
        formula_packages: Sequence[Any] = (),
        formula_obligations: Sequence[Any] = (),
        caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    ) -> PublicationMethodSectionOutputV1:
        """Assemble only accepted Realizer drafts.

        Composition is an organizational operation.  It never fills a
        missing mechanism with a sentence, creates a witness, or derives a
        formula from a detail id.  An incomplete set of drafts returns an
        empty structured output so the owning Writer/Binder can block or
        request repair.
        """
        sec_id = str(getattr(section_plan, "section_id", ""))
        heading = str(getattr(section_plan, "heading", "") or "Method")
        planned_paragraphs = list(getattr(section_plan, "paragraphs", ()) or ())
        para_outputs: list[PublicationMethodParagraphOutputV1] = []
        rendered_section_details: list[str] = []
        used_section_formula_pkgs: list[str] = []
        drafts_by_mechanism: dict[str, list[MechanismDraftV1]] = {}
        for draft in drafts:
            if draft.status == "accepted" and draft.draft_markdown.strip():
                drafts_by_mechanism.setdefault(draft.mechanism_id, []).append(draft)

        if not planned_paragraphs:
            return PublicationMethodSectionOutputV1(
                section_id=sec_id,
                heading_text=heading,
                section_markdown="",
                paragraphs=[],
                rendered_detail_ids=[],
                used_formula_package_ids=[],
            )

        for p in planned_paragraphs:
            pid = str(getattr(p, "paragraph_id", ""))
            mid = str(getattr(p, "mechanism_id", ""))
            req_dids = {str(x) for x in (getattr(p, "required_detail_ids", ()) or ())}
            req_formula_pkgs = {str(x) for x in (getattr(p, "formula_package_ids", ()) or ())}
            selected = drafts_by_mechanism.get(mid, [])
            realized_dids = set().union(*(set(d.realized_detail_ids) for d in selected)) if selected else set()
            used_pkgs = set().union(*(set(d.formula_package_ids) for d in selected)) if selected else set()
            if not selected or req_dids - realized_dids or req_formula_pkgs - used_pkgs:
                # Do not emit a partial section that could be mistaken for a
                # completed mechanism.  The caller retains the typed failure
                # in the draft trace and can route a callback.
                return PublicationMethodSectionOutputV1(
                    section_id=sec_id,
                    heading_text=heading,
                    section_markdown="",
                    paragraphs=[],
                    rendered_detail_ids=[],
                    used_formula_package_ids=[],
                )
            markdown = "\n\n".join(d.draft_markdown for d in selected).strip()
            witnesses = [w for d in selected for w in d.witnesses]
            formula_dispositions = [
                PublicationFormulaDispositionV1(package_id=package_id, disposition="consumed")
                for package_id in sorted(used_pkgs)
            ]
            para_outputs.append(PublicationMethodParagraphOutputV1(
                paragraph_id=pid,
                paragraph_markdown=markdown,
                rendered_detail_ids=sorted(realized_dids),
                used_formula_package_ids=sorted(used_pkgs),
                witnesses=witnesses,
                formula_disposition="consumed" if used_pkgs else None,
                formula_dispositions=formula_dispositions,
            ))
            rendered_section_details.extend(sorted(realized_dids))
            used_section_formula_pkgs.extend(sorted(used_pkgs))

        full_sec_md = f"## {heading}\n\n" + "\n\n".join(p.paragraph_markdown for p in para_outputs)
        cleaned_sec_md, _ = sanitize_representation_only(full_sec_md)

        return PublicationMethodSectionOutputV1(
            section_id=sec_id,
            heading_text=heading,
            section_markdown=cleaned_sec_md,
            paragraphs=para_outputs,
            rendered_detail_ids=list(dict.fromkeys(rendered_section_details)),
            used_formula_package_ids=list(dict.fromkeys(used_section_formula_pkgs)),
        )


__all__ = [
    "MechanismDraftV1",
    "SectionCompositionV1",
    "sanitize_representation_only",
    "MechanismRealizer",
    "SectionComposer",
]
