"""Cross-section editor with provenance-preserving scoped patches."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.llm.response_schemas import (
    PUBLICATION_METHOD_EDITOR_SCHEMA,
    PublicationMethodEditorOutputV1,
    json_schema_for,
    try_parse_structured_response,
)
from code2paper.schemas import LLMConfig


def _digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class SectionTextPatchV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    patch_id: str
    section_id: str
    before_digest: str
    replacement_text: str
    generation_source: str = "editor"
    generation_trace_ids: tuple[str, ...] = Field(default_factory=tuple)
    reason: str = ""
    scoped: bool = True

    @model_validator(mode="after")
    def _valid(self) -> "SectionTextPatchV1":
        if not self.replacement_text.strip():
            raise ValueError("editor patches cannot erase a section")
        if self.generation_source not in {"editor", "rewrite", "formalizer"}:
            raise ValueError("unknown generation source")
        if not self.scoped:
            raise ValueError("editor patch must be section-scoped")
        return self


class CrossSectionEditResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: dict[str, str] = Field(default_factory=dict)
    patches: list[SectionTextPatchV1] = Field(default_factory=list)
    duplicate_signatures: list[str] = Field(default_factory=list)
    blocked_reason: str = ""
    response_ref: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "CrossSectionEditResultV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


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
        config: LLMConfig | None = None,
        caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    ) -> CrossSectionEditResultV1:
        """Ask the owning Editor for complete section-scoped patches."""

        base_config = config or load_llm_config_from_env()
        request = LLMRequest(
            prompt_template_id="agentic_publication_method_editor_v1",
            prompt=(
                "Return only JSON matching the editor schema. Inspect the supplied sections "
                "for true repetition, terminology drift, notation drift, or broken transitions. "
                "Return complete section-scoped patches with the exact before digest. Preserve "
                "all supported explanation and do not add factual content."
            ),
            input_payload={"sections": dict(sections), "contract": "complete_scoped_patches_only"},
            schema_name=PUBLICATION_METHOD_EDITOR_SCHEMA,
            response_json_schema=json_schema_for(PublicationMethodEditorOutputV1),
        )
        try:
            response = (caller or (lambda cfg, req: LLMClient(cfg).complete(req)))(base_config, request)
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
        parsed, error = try_parse_structured_response(response.text, PublicationMethodEditorOutputV1)
        if parsed is None:
            return CrossSectionEditResultV1(
                sections={str(key): str(value) for key, value in sections.items()},
                blocked_reason=f"editor_schema_failed:{error}",
                response_ref=response.response_hash,
            )
        try:
            patches: list[SectionTextPatchV1] = []
            for item in parsed.patches:
                patch = SectionTextPatchV1.model_validate(item)
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
        return result.model_copy(update={"response_ref": response.response_hash})


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
        current[patch.section_id] = patch.replacement_text
        applied.append(patch)
    duplicates = [signature for signature, count in Counter(_sentence_signature(text) for text in current.values()).items() if count > 1 and signature]
    return CrossSectionEditResultV1(
        sections=current if not failures else {str(key): str(value) for key, value in sections.items()},
        patches=applied,
        duplicate_signatures=duplicates,
        blocked_reason=";".join(failures),
    )


def _sentence_signature(text: str) -> str:
    return " ".join(text.lower().split())[:240]


__all__ = [
    "CrossSectionEditResultV1",
    "CrossSectionEditor",
    "SectionTextPatchV1",
    "edit_sections",
]
