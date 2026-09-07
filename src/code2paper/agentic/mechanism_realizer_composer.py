"""Two-step authoring architecture: Mechanism Realizer + Section Composer.

Implements section 5.10 of the Unified Mechanism Context Optimization Execution Plan:
1. Mechanism Realizer: Generates draft paragraph(s) per mechanism/page, fulfilling
   required details and formula packages under strict authority rules.
2. Section Composer: Assembles verified mechanism drafts, transitions, and section
   coherence without inventing technical implementation facts.
"""

from __future__ import annotations

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
    formula_package_ids: tuple[str, ...] = Field(default_factory=tuple)
    authority_disposition: str = "repository_verified"
    witness_atoms: tuple[str, ...] = Field(default_factory=tuple)
    witnesses: tuple[PublicationContentWitnessV1, ...] = Field(default_factory=tuple)
    status: str = "blocked"
    blocked_reason: str = ""
    request_digest: str = ""
    representation_diff_class: str = "none"
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
    ) -> MechanismDraftV1:
        """Generate one page draft through the authorized Writer caller.

        The harness may assemble the request envelope and validate the
        response, but it may not author technical sentences or witnesses.  A
        missing caller, malformed response, or incomplete witness set returns
        a blocked draft with no realized details and no publication text.
        """
        mech_id = str(context.mechanism_id)
        details = list(context.details)
        if page_slice is not None:
            slice_dids = {str(d) for d in (getattr(page_slice, "detail_ids", ()) or ())}
            details = [d for d in details if str(d.detail_id) in slice_dids]

        required_dids = tuple(str(d.detail_id) for d in details)
        pkg_ids = tuple(
            str(getattr(pkg, "package_id", ""))
            for pkg in formula_packages
            if str(getattr(pkg, "mechanism_id", "")) == mech_id
        )

        # Classify overall authority disposition for the response contract;
        # this value is not a license to synthesize prose.
        authorities = {str(d.evidence_authority) for d in details}
        if "repo_mismatch" in authorities:
            authority = "repo_mismatch_flagged"
        elif "unresolved" in authorities:
            authority = "unresolved"
        elif "author_spec_only" in authorities and "repository_verified" not in authorities:
            authority = "author_spec_only"
        elif "repository_partial" in authorities or "implemented_partial" in authorities:
            authority = "qualified_partial"
        else:
            authority = "repository_verified"

        def blocked(reason: str, *, request_digest: str = "") -> MechanismDraftV1:
            return MechanismDraftV1(
                draft_id=f"draft:{mech_id}:p{page_index}",
                mechanism_id=mech_id,
                page_index=page_index,
                heading=str(getattr(context, "mechanism_name", "") or getattr(context, "name", "") or mech_id),
                draft_markdown="",
                required_detail_ids=required_dids,
                realized_detail_ids=(),
                formula_package_ids=(),
                authority_disposition=authority,
                witness_atoms=(),
                witnesses=(),
                status="blocked",
                blocked_reason=reason,
                request_digest=request_digest,
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
        page_bytes = (
            page_slice.serialized_payload
            if page_slice is not None
            else json.dumps(
                context.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        allowed_atoms = {
            str(atom.atom_id)
            for detail in details
            for atom in getattr(detail, "witness_atoms", ()) or ()
            if str(atom.atom_id).strip()
        }
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
            response = caller(self.llm_config, request)
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
            return blocked("realizer_response_not_json", request_digest=request_digest)
        if not isinstance(payload, Mapping):
            return blocked("realizer_response_not_object", request_digest=request_digest)
        markdown = str(payload.get("draft_markdown") or payload.get("section_markdown") or "").strip()
        rendered = tuple(dict.fromkeys(
            str(value).strip() for value in (payload.get("rendered_detail_ids") or ())
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

        raw_witnesses = payload.get("witnesses") or ()
        witnesses: list[PublicationContentWitnessV1] = []
        for raw in raw_witnesses:
            if not isinstance(raw, Mapping):
                return blocked("realizer_witness_not_object", request_digest=request_digest)
            try:
                witness = PublicationContentWitnessV1.model_validate(raw)
            except Exception:
                return blocked("realizer_witness_invalid", request_digest=request_digest)
            if witness.witness_kind == "detail" and witness.target_id not in set(required_dids):
                return blocked("realizer_detail_witness_out_of_scope", request_digest=request_digest)
            if witness.witness_kind == "atom" and witness.target_id not in allowed_atoms:
                return blocked("realizer_atom_witness_out_of_scope", request_digest=request_digest)
            if witness.witness_kind == "formula" and witness.target_id not in set(pkg_ids):
                return blocked("realizer_formula_witness_out_of_scope", request_digest=request_digest)
            if not witness.exact_text.strip() or witness.exact_text not in markdown:
                return blocked("realizer_witness_text_missing", request_digest=request_digest)
            witnesses.append(witness)
        required_witness_targets = set(required_dids) | set(pkg_ids)
        witnessed_targets = {item.target_id for item in witnesses}
        if required_witness_targets - witnessed_targets:
            return blocked("realizer_required_witness_missing", request_digest=request_digest)
        cleaned_draft, diff_class = sanitize_representation_only(markdown)
        return MechanismDraftV1(
            draft_id=f"draft:{mech_id}:p{page_index}",
            mechanism_id=mech_id,
            page_index=page_index,
            heading=str(getattr(context, "mechanism_name", "") or getattr(context, "name", "") or mech_id),
            draft_markdown=cleaned_draft,
            required_detail_ids=required_dids,
            realized_detail_ids=rendered,
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
