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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.research_models import TextRepairIssueV1
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.generation_trace import build_generation_call_trace
from code2paper.llm.role_config import LOCAL_REWRITE, apply_role_config
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.llm.response_schemas import json_schema_for, try_parse_structured_response
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
    issue_ids: tuple[str, ...] = Field(default_factory=tuple)
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

    patches: tuple[LocalRewritePatchV1, ...] = Field(default_factory=tuple)
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
            },
        }
        request = LLMRequest(
            prompt_template_id=self.prompt_template_id,
            prompt=(
                "You are the owning local_rewrite Agent. Return only JSON matching the schema. "
                "For each repair, return the exact incumbent character offsets and original_text, "
                "then the complete replacement span. Never rewrite text outside those spans, add "
                "evidence, or normalize unrelated punctuation. An empty replacement is allowed only "
                "when the issue explicitly permits drop_or_gap."
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
        if response.blocked_reason:
            return RewriteCallResult(
                status="blocked",
                incumbent_digest=incumbent_digest,
                candidate_digest=incumbent_digest,
                candidate_text=incumbent_text,
                response_ref=response.response_hash,
                blocked_reason=response.blocked_reason,
            )
        parsed, error = try_parse_structured_response(response.text, LocalRewriteOutputV1)
        trace = build_generation_call_trace(
            call_id=f"{self.prompt_template_id}:{request.input_hash[7:19]}",
            config=config,
            request=request,
            response=response,
        ).model_dump(mode="json")
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
        )


def write_repair_transition(path: str | Path, transition: RepairTransitionV1) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(transition.model_dump_json(indent=2) + "\n", encoding="utf-8")


__all__ = [
    "LocalRewriteAgent",
    "LocalRewriteOutputV1",
    "LocalRewritePatchV1",
    "RepairTransitionV1",
    "RewriteCallResult",
    "apply_local_rewrite_patches",
    "write_repair_transition",
]
