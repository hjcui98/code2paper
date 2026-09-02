"""Cross-section editor with provenance-preserving scoped patches."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.capabilities import StructuredResponseMode, load_capability_profile
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.llm.response_schemas import (
    PUBLICATION_METHOD_EDITOR_SCHEMA,
    PublicationMethodEditorOutputV1,
    PublicationMethodEditorOutputV2,
    json_schema_for,
    try_parse_structured_response,
)
from code2paper.schemas import LLMConfig


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _result_content_digest(result: "CrossSectionEditResultV1") -> str:
    """Canonical content digest of every digest-covered field of a result."""
    payload = result.model_dump(mode="json", exclude={"content_digest"})
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class SectionTextPatchV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    patch_id: str
    section_id: str
    before_digest: str
    before_text: str = ""
    replacement_text: str
    generation_source: str = "editor"
    generation_trace_ids: tuple[str, ...] = Field(default_factory=tuple)
    reason: str = ""
    scoped: bool = True
    rendered_proposition_ids: tuple[str, ...] = Field(default_factory=tuple)
    caveated_proposition_ids: tuple[str, ...] = Field(default_factory=tuple)
    deferred_proposition_ids: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _valid(self) -> "SectionTextPatchV1":
        if not self.replacement_text.strip():
            raise ValueError("editor patches cannot erase a section")
        if self.generation_source not in {"editor", "rewrite", "formalizer"}:
            raise ValueError("unknown generation source")
        if not self.scoped:
            raise ValueError("editor patch must be section-scoped")
        reported = [
            *self.rendered_proposition_ids,
            *self.caveated_proposition_ids,
            *self.deferred_proposition_ids,
        ]
        if len(reported) != len(set(reported)):
            raise ValueError("editor proposition dispositions must be disjoint")
        return self


class CrossSectionEditResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: dict[str, str] = Field(default_factory=dict)
    patches: list[SectionTextPatchV1] = Field(default_factory=list)
    duplicate_signatures: list[str] = Field(default_factory=list)
    blocked_reason: str = ""
    response_ref: str = ""
    response_refs: tuple[str, ...] = Field(default_factory=tuple)
    call_failures: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "CrossSectionEditResultV1":
        object.__setattr__(self, "content_digest", _result_content_digest(self))
        return self

    def with_updates(self, **updates: Any) -> "CrossSectionEditResultV1":
        """Return a copy with digest-covered fields replaced and the digest recomputed.

        ``BaseModel.model_copy(update=...)`` applies raw field replacement
        without rerunning model validators, so the stored ``content_digest``
        would silently cover the pre-update payload.  This typed path is the
        only sanctioned way to mutate a digest-covered field after
        construction: it applies the update and always recomputes
        ``content_digest`` from the resulting payload, so the persisted
        artifact digest always matches its actual bytes.
        """
        updated = self.model_copy(update=updates)
        object.__setattr__(updated, "content_digest", _result_content_digest(updated))
        return updated


class CrossSectionEditor:
    """Apply only complete generated patches returned by an Editor agent."""

    def edit(
        self,
        sections: Mapping[str, str],
        *,
        patch_provider: Callable[[dict[str, str]], Any] | None = None,
    ) -> CrossSectionEditResultV1:
        return edit_sections(sections, patch_provider=patch_provider)

    def edit_with_llm(
        self,
        sections: Mapping[str, str],
        *,
        section_contexts: Mapping[str, Mapping[str, Any]] | None = None,
        document_context: Mapping[str, Any] | None = None,
        config: LLMConfig | None = None,
        caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    ) -> CrossSectionEditResultV1:
        """Ask the owning Editor for document-organization patches.

        The Editor owns paragraph/section organization, transitions,
        terminology and cross-section repetition. Evidence support, missing
        propositions and numeric/formula/qualifier repair remain with the
        Verifier/Writer/Rewrite owners.
        """

        base_config = config or load_llm_config_from_env()
        ordered_ids = _ordered_editor_section_ids(sections, document_context)
        try:
            configured_batch_size = int(
                os.environ.get("CODE2PAPER_PUBLICATION_EDITOR_BATCH_SIZE", "4")
            )
        except ValueError:
            configured_batch_size = 4
        batch_size = max(1, min(configured_batch_size, 6))
        if len(ordered_ids) > batch_size:
            return self._edit_batches_with_llm(
                sections,
                ordered_ids=ordered_ids,
                batch_size=batch_size,
                section_contexts=section_contexts,
                document_context=document_context,
                config=base_config,
                caller=caller,
            )
        return self._edit_one_batch_with_llm(
            sections,
            section_contexts=section_contexts,
            document_context=document_context,
            config=base_config,
            caller=caller,
        )

    def revise_one_section_with_llm(
        self,
        section_id: str,
        section_text: str,
        *,
        section_context: Mapping[str, Any],
        document_context: Mapping[str, Any] | None = None,
        config: LLMConfig | None = None,
        caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    ) -> CrossSectionEditResultV1:
        """Public single-section semantic revision entry used for repair."""

        return self._edit_one_batch_with_llm(
            {section_id: section_text},
            section_contexts={section_id: section_context},
            document_context=document_context,
            config=config or load_llm_config_from_env(),
            caller=caller,
        )

    def _edit_batches_with_llm(
        self,
        sections: Mapping[str, str],
        *,
        ordered_ids: list[str],
        batch_size: int,
        section_contexts: Mapping[str, Mapping[str, Any]] | None,
        document_context: Mapping[str, Any] | None,
        config: LLMConfig,
        caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None,
    ) -> CrossSectionEditResultV1:
        """Edit neighboring section groups so JSON patches stay bounded.

        A 20+ section Method plus its authority context can fit the model's
        input window but still cause the Editor to exhaust its *output* budget
        while repeating the whole document.  Neighboring groups retain local
        discourse context, and the document outline remains visible in every
        call.  Each returned patch keeps the exact response reference of the
        call that generated its lexical bytes.
        """

        current = {str(key): str(value) for key, value in sections.items()}
        patches: list[SectionTextPatchV1] = []
        response_refs: list[str] = []
        failures: list[str] = []
        for index in range(0, len(ordered_ids), batch_size):
            batch_ids = ordered_ids[index:index + batch_size]
            batch = {section_id: current[section_id] for section_id in batch_ids}
            batch_contexts = {
                section_id: dict((section_contexts or {}).get(section_id, {}))
                for section_id in batch_ids
            }
            batch_document_context = {
                **dict(document_context or {}),
                "editor_batch": {
                    "batch_index": index // batch_size + 1,
                    "section_ids": batch_ids,
                    "neighbor_before": ordered_ids[index - 1] if index else "",
                    "neighbor_after": (
                        ordered_ids[index + batch_size]
                        if index + batch_size < len(ordered_ids) else ""
                    ),
                },
            }
            result = self._edit_one_batch_with_llm(
                batch,
                section_contexts=batch_contexts,
                document_context=batch_document_context,
                config=config,
                caller=caller,
            )
            if result.response_ref:
                response_refs.append(result.response_ref)
            if result.blocked_reason:
                failures.append(
                    f"batch-{index // batch_size + 1}:{result.blocked_reason}"
                )
                continue
            for section_id, text in result.sections.items():
                current[section_id] = text
            patches.extend(result.patches)
        if failures and not response_refs:
            return CrossSectionEditResultV1(
                sections={str(key): str(value) for key, value in sections.items()},
                blocked_reason=";".join(failures),
                call_failures=tuple(failures),
            )
        return CrossSectionEditResultV1(
            sections=current,
            patches=patches,
            duplicate_signatures=[
                signature for signature, count in Counter(
                    _sentence_signature(text) for text in current.values()
                ).items() if count > 1 and signature
            ],
            response_ref=response_refs[-1] if response_refs else "",
            response_refs=tuple(response_refs),
            call_failures=tuple(failures),
        )

    def _edit_one_batch_with_llm(
        self,
        sections: Mapping[str, str],
        *,
        section_contexts: Mapping[str, Mapping[str, Any]] | None,
        document_context: Mapping[str, Any] | None,
        config: LLMConfig,
        caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None,
    ) -> CrossSectionEditResultV1:
        base_config = config
        repetition_hints = _repetition_hints(sections)
        editor_contexts = {
            str(section_id): _academic_editor_context(context)
            for section_id, context in (section_contexts or {}).items()
            if str(section_id) in sections
        }
        section_bodies = {
            str(section_id): _split_fixed_heading(text)[1]
            for section_id, text in sections.items()
        }
        fixed_headings = {
            str(section_id): _split_fixed_heading(text)[0]
            for section_id, text in sections.items()
        }
        request = LLMRequest(
            prompt_template_id="agentic_academic_method_editor_v2",
            prompt=(
                "You are the academic Method Editor. Return only JSON matching the revision "
                "schema. Rewrite a complete section body when this materially improves its "
                "reader-facing logic, paragraph boundaries, transitions, terminology, or removes "
                "code-trace narration and repetition. You may paraphrase and reorganize sentences; "
                "you are not a byte patcher. Use only the supplied WriterView propositions. "
                "Preserve every required positive proposition, every required epistemic caveat, "
                "and every immutable condition, number, formula, configuration, and qualifier. "
                "When required_qualifier_bindings are supplied for a section, preserve each "
                "academic condition phrase; never paste self.cfg, self.config, or torch. "
                "identifiers into Candidate sentences, and never authorize a predicate "
                "from another section. "
                "Do not invent a mechanism, loss, dataset, benefit, causal claim, or performance "
                "claim. Describe implementation identifiers only when a minimal parenthetical "
                "binding helps; prefer academic method language. Do not emit an H2 heading: the "
                "harness owns and preserves it. Report rendered, caveated, and deferred IDs from "
                "the supplied closed set. Any candidate-only author narrative must retain an explicit "
                "author-intent, partial, mismatch, or pending caveat. If a safe material "
                "improvement is unavailable, return "
                "{\"revisions\": []}. Never compute offsets, digests, or original spans."
            ),
            input_payload={
                "section_bodies": section_bodies,
                "fixed_headings": fixed_headings,
                "section_contexts": editor_contexts,
                # Keep the original complete-section surface during the V2
                # migration.  Replay callers and frozen Editor fixtures use
                # these reader-facing values to propose a V1 whole-section
                # replacement; live providers follow ``section_bodies`` and
                # the V2 semantic revision schema above.  Both surfaces carry
                # the same prose and authority context, so this compatibility
                # alias does not broaden what the Editor may write.
                "sections": {str(key): str(value) for key, value in sections.items()},
                "document_context": dict(document_context or {}),
                "repetition_hints": repetition_hints,
                "contract": "whole_section_body_revision_v2",
            },
            schema_name=PUBLICATION_METHOD_EDITOR_SCHEMA,
            response_json_schema=json_schema_for(PublicationMethodEditorOutputV2),
        )
        try:
            try:
                configured_editor_budget = int(
                    os.environ.get(
                        "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_PUBLICATION_EDITOR",
                        "4096",
                    )
                )
            except ValueError:
                configured_editor_budget = 2048
            editor_config = base_config.model_copy(update={
                # Editing is a bounded patch decision, not a second Method
                # generation.  Disable hidden reasoning and keep the answer
                # ceiling below the largest patch contract so a provider that
                # repeats JSON cannot monopolize the run budget.
                "max_output_tokens": min(
                    base_config.max_output_tokens,
                    max(2048, min(configured_editor_budget, 8192)),
                ),
                "reasoning_effort": "none",
                "thinking_token_budget": None,
                "temperature": min(max(base_config.temperature, 0.3), 0.45),
            })
            if caller is not None:
                response = caller(editor_config, request)
            else:
                response_mode = os.environ.get(
                    "CODE2PAPER_LLM_PUBLICATION_EDITOR_RESPONSE_MODE", ""
                ).strip()
                if response_mode:
                    try:
                        mode = StructuredResponseMode(response_mode)
                    except ValueError:
                        mode = StructuredResponseMode.NATIVE_JSON_SCHEMA
                    profile = load_capability_profile(
                        provider=getattr(editor_config.provider, "value", str(editor_config.provider)),
                        model=editor_config.model,
                    ).model_copy(update={"response_mode": mode})
                    response = LLMClient(editor_config, capability_profile=profile).complete(request)
                else:
                    response = LLMClient(editor_config).complete(request)
        except Exception as exc:  # noqa: BLE001 - editor failure is a scoped block
            return CrossSectionEditResultV1(
                sections={str(key): str(value) for key, value in sections.items()},
                blocked_reason=f"editor_llm_error:{exc.__class__.__name__}",
            )
        if response.blocked_reason:
            return CrossSectionEditResultV1(
                sections={str(key): str(value) for key, value in sections.items()},
                blocked_reason=response.blocked_reason,
                response_ref=response.response_hash,
            )
        parsed_v2, error = try_parse_structured_response(
            response.text, PublicationMethodEditorOutputV2
        )
        if parsed_v2 is None:
            # Historical fixtures and frozen responses remain replayable while
            # live calls use the semantic V2 contract.
            parsed_v1, legacy_error = try_parse_structured_response(
                response.text, PublicationMethodEditorOutputV1
            )
        else:
            parsed_v1, legacy_error = None, ""
        if parsed_v2 is None and parsed_v1 is None:
            return CrossSectionEditResultV1(
                sections={str(key): str(value) for key, value in sections.items()},
                blocked_reason=f"editor_schema_failed:{error or legacy_error}",
                response_ref=response.response_hash,
            )
        try:
            patches: list[SectionTextPatchV1] = []
            if parsed_v2 is not None:
                closed_ids_by_section = {
                    section_id: _closed_editor_proposition_ids(context)
                    for section_id, context in editor_contexts.items()
                }
                seen_sections: set[str] = set()
                for item in parsed_v2.revisions:
                    section_id = str(item.section_id)
                    if section_id not in sections or section_id in seen_sections:
                        raise ValueError("editor revision contains an unknown or duplicate section")
                    seen_sections.add(section_id)
                    writer_view = editor_contexts.get(section_id, {}).get("writer_view") or {}
                    positive_ids = {
                        str(row.get("proposition_id") or "")
                        for row in writer_view.get("positive_propositions") or ()
                        if isinstance(row, Mapping)
                    }
                    caveated_ids = {
                        str(row.get("proposition_id") or "")
                        for row in writer_view.get("caveated_propositions") or ()
                        if isinstance(row, Mapping)
                    }
                    required_ids = {
                        str(value) for value in writer_view.get("required_proposition_ids") or ()
                        if str(value)
                    }
                    rendered_ids = set(item.rendered_proposition_ids)
                    caveated_reported_ids = set(item.caveated_proposition_ids)
                    deferred_ids = set(item.deferred_proposition_ids)
                    reported_ids = rendered_ids | caveated_reported_ids | deferred_ids
                    if not reported_ids.issubset(closed_ids_by_section.get(section_id, set())):
                        raise ValueError("editor revision contains a foreign proposition id")
                    if not rendered_ids.issubset(positive_ids):
                        raise ValueError("editor rendered a caveated proposition as positive")
                    if not caveated_reported_ids.issubset(caveated_ids):
                        raise ValueError("editor caveat disposition does not match WriterView")
                    if not required_ids.issubset(reported_ids):
                        raise ValueError("editor revision omitted a required proposition disposition")
                    heading, _body = _split_fixed_heading(sections[section_id])
                    revised_body = item.revised_body_markdown.strip()
                    while revised_body.startswith("## "):
                        revised_body = "\n".join(revised_body.splitlines()[1:]).lstrip()
                    replacement = f"{heading}\n\n{revised_body}" if heading else revised_body
                    patches.append(SectionTextPatchV1(
                        patch_id=f"editor-v2-{section_id}",
                        section_id=section_id,
                        before_digest=_digest(sections[section_id]),
                        replacement_text=replacement,
                        generation_source="editor",
                        generation_trace_ids=(response.response_hash,),
                        reason=";".join(item.addressed_revision_goals) or "academic_method_revision",
                        rendered_proposition_ids=tuple(item.rendered_proposition_ids),
                        caveated_proposition_ids=tuple(item.caveated_proposition_ids),
                        deferred_proposition_ids=tuple(item.deferred_proposition_ids),
                    ))
            else:
                assert parsed_v1 is not None
                for item in parsed_v1.patches:
                    patch_payload = item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                    patch = SectionTextPatchV1.model_validate(patch_payload)
                    patches.append(patch.model_copy(update={
                        "generation_trace_ids": tuple(
                            dict.fromkeys([*patch.generation_trace_ids, response.response_hash])
                        )
                    }))
        except (TypeError, ValueError) as exc:
            return CrossSectionEditResultV1(
                sections={str(key): str(value) for key, value in sections.items()},
                blocked_reason=f"editor_patch_schema_failed:{exc.__class__.__name__}",
                response_ref=response.response_hash,
            )
        result = edit_sections(sections, patch_provider=lambda _: patches)
        return result.with_updates(
            response_ref=response.response_hash,
            response_refs=(response.response_hash,),
        )


def _split_fixed_heading(text: str) -> tuple[str, str]:
    lines = str(text).lstrip().splitlines()
    if lines and lines[0].startswith("## "):
        return lines[0].strip(), "\n".join(lines[1:]).strip()
    return "", str(text).strip()


def _academic_editor_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Expose only the four-layer WriterView and reader-facing purpose."""

    writer_view = dict(context.get("writer_view") or {})
    section = dict(context.get("section") or {})
    return {
        "section_purpose": section.get("purpose") or section.get("design_objective") or "",
        "reader_question": section.get("reader_question") or "",
        "writer_view": writer_view,
        "reader_facing_claims": list(context.get("reader_facing_claims") or ()),
        "required_qualifier_bindings": list(
            context.get("required_qualifier_bindings") or ()
        ),
        "revision_goals": [
            "answer the section question directly",
            "organize one coherent idea per paragraph",
            "replace code-trace narration with academic method language",
            "remove repetition and generic placeholder prose",
            "preserve proposition authority and caveats",
        ],
    }


def _closed_editor_proposition_ids(context: Mapping[str, Any]) -> set[str]:
    writer_view = context.get("writer_view") or {}
    rows = [
        *(writer_view.get("positive_propositions") or ()),
        *(writer_view.get("caveated_propositions") or ()),
    ]
    return {
        str(row.get("proposition_id"))
        for row in rows
        if isinstance(row, Mapping) and str(row.get("proposition_id") or "")
    }


def _ordered_editor_section_ids(
    sections: Mapping[str, str],
    document_context: Mapping[str, Any] | None,
) -> list[str]:
    available = {str(item) for item in sections}
    ordered: list[str] = []
    for row in (document_context or {}).get("section_order", ()):
        if not isinstance(row, Mapping):
            continue
        section_id = str(row.get("section_id") or "")
        if section_id in available and section_id not in ordered:
            ordered.append(section_id)
    ordered.extend(section_id for section_id in sections if section_id not in ordered)
    return ordered


def edit_sections(
    sections: Mapping[str, str],
    *,
    patch_provider: Callable[[dict[str, str]], Any] | None = None,
) -> CrossSectionEditResultV1:
    current = {str(key): str(value) for key, value in sections.items()}
    if patch_provider is None:
        return CrossSectionEditResultV1(
            sections=current,
            blocked_reason="editor_generation_required_for_cross_section_mutation",
        )
    try:
        raw = patch_provider(dict(current))
        if isinstance(raw, Mapping):
            if "patches" not in raw:
                raise ValueError("editor response must contain patches")
            raw_patches = raw["patches"]
        else:
            raw_patches = raw
        patches = [
            item if isinstance(item, SectionTextPatchV1) else SectionTextPatchV1.model_validate(item)
            for item in (raw_patches or [])
        ]
    except Exception as exc:  # noqa: BLE001 - malformed agent output is a scoped repair failure
        return CrossSectionEditResultV1(
            sections=current,
            blocked_reason=f"editor_patch_schema_failed:{exc.__class__.__name__}",
        )
    failures: list[str] = []
    applied: list[SectionTextPatchV1] = []
    for patch in patches:
        before = current.get(patch.section_id)
        if before is None:
            failures.append(f"unknown_section:{patch.section_id}")
            continue
        if _digest(before) != patch.before_digest:
            failures.append(f"stale_section:{patch.section_id}")
            continue
        if patch.before_text:
            occurrences = before.count(patch.before_text)
            if occurrences != 1:
                failures.append(
                    f"editor_span_not_unique:{patch.section_id}:{occurrences}"
                )
                continue
            current[patch.section_id] = before.replace(
                patch.before_text, patch.replacement_text, 1
            )
        else:
            current[patch.section_id] = patch.replacement_text
        applied.append(patch)
    duplicates = [signature for signature, count in Counter(_sentence_signature(text) for text in current.values()).items() if count > 1 and signature]
    return CrossSectionEditResultV1(
        sections=current,
        patches=applied,
        duplicate_signatures=duplicates,
        blocked_reason=";".join(failures),
    )


def _sentence_signature(text: str) -> str:
    return " ".join(text.lower().split())[:240]


def _repetition_hints(sections: Mapping[str, str]) -> dict[str, list[str]]:
    """Return exact repeated sentence text as an Editor-only repair hint."""

    hints: dict[str, list[str]] = {}
    for section_id, text in sections.items():
        sentences = [
            " ".join(item.split())
            for item in re.split(r"(?<=[.!?])\s+|\n+", text)
            if item.strip() and not item.lstrip().startswith("#")
        ]
        counts = Counter(item.lower() for item in sentences if item)
        repeated = [
            sentence for sentence in sentences
            if counts.get(sentence.lower(), 0) > 1
        ]
        if repeated:
            hints[str(section_id)] = list(dict.fromkeys(repeated))[:8]
    return hints


__all__ = [
    "CrossSectionEditResultV1",
    "CrossSectionEditor",
    "SectionTextPatchV1",
    "edit_sections",
]
