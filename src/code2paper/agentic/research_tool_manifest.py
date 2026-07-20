"""R1.3 LangChain StructuredTool manifest for the V3 research tools.

Exports the four minimal read-only research tools
(``find_entrypoints``, ``search_symbols``, ``read_symbol``, ``find_references``)
as a serializable manifest and as LangChain ``StructuredTool`` objects.

The manifest is the contract surface a model sees: it records each tool's
name, kind, description, input schema (JSON Schema) and the R1.2 contract
fields every observation must return.  It is content-addressed so a
checkpoint resume can detect manifest drift between the persisted run and
the reloaded code.

R1.3 also exposes ``build_research_structured_tools`` which returns real
LangChain ``StructuredTool`` objects bound to a :class:`ResearchToolContext`.
The tool wrappers funnel every call through ``execute_research_tool`` so the
security floor (snapshot-external path refusal, authority tagging, digest
stability) applies even when the model invokes the tool directly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.research_models import ResearchToolCallV1
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_EXECUTORS,
    RESEARCH_TOOL_INPUT_SCHEMAS,
    RESEARCH_TOOL_KINDS,
    RESEARCH_TOOL_NAMES,
    ResearchToolContext,
    execute_research_tool,
)


MANIFEST_SCHEMA_VERSION = "1.0"
MANIFEST_MODE = "agentic-research-tool-manifest-v1"


# ---------------------------------------------------------------------------
# Tool descriptions (used by the manifest and the StructuredTool wrappers)
# ---------------------------------------------------------------------------


RESEARCH_TOOL_DESCRIPTIONS: dict[str, str] = {
    "find_entrypoints": (
        "Locate repository entrypoints (main.py, train.py, shell scripts, "
        "Makefile/Dockerfile) within a snapshot scope.  Returns one "
        "'entrypoint:<path>' ref per match."
    ),
    "search_symbols": (
        "Query the deterministic symbol index for classes/functions matching "
        "a substring or regex.  Returns 'symbol:<path>:<symbol>:<line>' refs."
    ),
    "read_symbol": (
        "Read the exact source span of a specific symbol (dotted paths "
        "supported, e.g. 'Trainer.train_loop').  Returns "
        "'span:<path>:<start>:<end>' ids."
    ),
    "find_references": (
        "Find imports and usages of a symbol across the snapshot.  Returns "
        "'ref:<path>:<line>' refs.  Use import_only=True to restrict to "
        "import sites."
    ),
}


# ---------------------------------------------------------------------------
# Manifest models
# ---------------------------------------------------------------------------


# Fields every ResearchToolCallV1 must bind (R1.2 contract).
RESEARCH_TOOL_CALL_REQUIRED_FIELDS: tuple[str, ...] = (
    "tool_call_id",
    "tool_name",
    "tool_kind",
    "obligation_id",
    "goal",
    "repo_snapshot_id",
    "path_scope",
    "top_k",
    "depth",
    "node_budget",
)


# Fields every ResearchObservationV1 must return (R1.2 contract).
RESEARCH_TOOL_RETURN_FIELDS: tuple[str, ...] = (
    "observation_id",
    "tool_call_id",
    "tool_name",
    "obligation_id",
    "repo_snapshot_id",
    "status",
    "source_authority",
    "result_refs",
    "exact_span_ids",
    "diagnostics",
    "input_digest",
    "output_digest",
    "error_message",
)


# Mutation guarantees enforced by the tool layer (R1.4 exit conditions).
RESEARCH_TOOL_SECURITY_MUTATIONS: tuple[str, ...] = (
    "snapshot_external_path_rejected",
    "hint_authority_cannot_anchor_positive_claim",
    "forged_symbol_id_rejected",
    "truncated_not_treated_as_exhausted",
    "digest_stable_for_same_input",
    "freshness_fails_when_repo_drifts",
)


class LangChainResearchToolExport(BaseModel):
    """Per-tool export record in the research tool manifest."""

    model_config = ConfigDict(extra="forbid")

    name: str
    tool_kind: str
    description: str
    args_schema_name: str
    args_schema: dict[str, Any] = Field(default_factory=dict)
    required_input_fields: tuple[str, ...] = RESEARCH_TOOL_CALL_REQUIRED_FIELDS
    return_fields: tuple[str, ...] = RESEARCH_TOOL_RETURN_FIELDS
    security_mutations: tuple[str, ...] = RESEARCH_TOOL_SECURITY_MUTATIONS


class LangChainResearchToolManifest(BaseModel):
    """Serializable manifest of all registered research tools."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = MANIFEST_SCHEMA_VERSION
    mode: str = MANIFEST_MODE
    tool_count: int = 0
    tools: list[LangChainResearchToolExport] = Field(default_factory=list)
    content_digest: str = ""

    @classmethod
    def empty(cls) -> "LangChainResearchToolManifest":
        return cls()


def build_research_tool_manifest(
    tool_names: tuple[str, ...] | None = None,
) -> LangChainResearchToolManifest:
    """Build the canonical manifest for the V3 research tools.

    The manifest is content-addressed: its ``content_digest`` covers every
    tool's name, kind, args_schema_name, args_schema JSON, and the static
    contract field lists.  A checkpoint resume that observes a different
    digest MUST treat the persisted run as stale.
    """

    names = tool_names or RESEARCH_TOOL_NAMES
    exports: list[LangChainResearchToolExport] = []
    for name in names:
        if name not in RESEARCH_TOOL_INPUT_SCHEMAS:
            raise KeyError(f"unknown research tool: {name}")
        schema_cls = RESEARCH_TOOL_INPUT_SCHEMAS[name]
        exports.append(
            LangChainResearchToolExport(
                name=name,
                tool_kind=RESEARCH_TOOL_KINDS.get(name, "other"),
                description=RESEARCH_TOOL_DESCRIPTIONS.get(name, ""),
                args_schema_name=schema_cls.__name__,
                args_schema=schema_cls.model_json_schema(),
            )
        )
    digest = _manifest_digest(exports)
    return LangChainResearchToolManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        mode=MANIFEST_MODE,
        tool_count=len(exports),
        tools=exports,
        content_digest=digest,
    )


def write_research_tool_manifest(
    path: str | Path, manifest: LangChainResearchToolManifest
) -> Path:
    """Persist the manifest as pretty-printed JSON."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def load_research_tool_manifest(path: str | Path) -> LangChainResearchToolManifest:
    """Load a manifest from disk and re-validate it."""

    return LangChainResearchToolManifest.model_validate(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )


# ---------------------------------------------------------------------------
# LangChain StructuredTool wrappers
# ---------------------------------------------------------------------------


def build_research_structured_tools(
    ctx: ResearchToolContext,
    tool_names: tuple[str, ...] | None = None,
) -> list[Any]:
    """Return LangChain ``StructuredTool`` objects bound to ``ctx``.

    Each tool wrapper accepts the matching input schema (e.g.
    :class:`FindEntrypointsInput`), converts it to a
    :class:`ResearchToolCallV1`, and dispatches through
    ``execute_research_tool`` so the security floor applies uniformly.

    Raises ``RuntimeError`` if ``langchain_core`` is not installed.
    """

    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "Install the optional agentic extra to export LangChain tools: "
            "pip install -e .[agentic]"
        ) from exc

    names = tool_names or RESEARCH_TOOL_NAMES
    tools: list[Any] = []
    for name in names:
        if name not in RESEARCH_TOOL_INPUT_SCHEMAS:
            raise KeyError(f"unknown research tool: {name}")
        schema_cls = RESEARCH_TOOL_INPUT_SCHEMAS[name]
        kind = RESEARCH_TOOL_KINDS.get(name, "other")
        description = RESEARCH_TOOL_DESCRIPTIONS.get(name, "")
        executor = RESEARCH_TOOL_EXECUTORS[name]

        def _make_runner(tool_name: str, tool_kind: str, executor_fn: Any):
            def _run(**kwargs: Any) -> dict[str, Any]:
                tool_call = _tool_call_from_kwargs(
                    tool_name=tool_name,
                    tool_kind=tool_kind,
                    ctx=ctx,
                    kwargs=kwargs,
                )
                observation = executor_fn(ctx, tool_call)
                return observation.model_dump(mode="json")

            return _run

        tool = StructuredTool.from_function(
            func=_make_runner(name, kind, executor),
            name=name,
            description=description,
            args_schema=schema_cls,
            metadata={
                "mode": MANIFEST_MODE,
                "tool_kind": kind,
                "repo_snapshot_id": ctx.repo_snapshot.snapshot_id,
                "contract": "ResearchObservationV1",
            },
        )
        tools.append(tool)
    return tools


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tool_call_from_kwargs(
    *,
    tool_name: str,
    tool_kind: str,
    ctx: ResearchToolContext,
    kwargs: dict[str, Any],
) -> ResearchToolCallV1:
    """Build a ResearchToolCallV1 from a StructuredTool kwargs payload."""

    payload = dict(kwargs or {})
    tool_call_id = str(payload.pop("tool_call_id", "") or f"sc-{tool_name}")
    obligation_id = str(payload.pop("obligation_id", "") or "obl-1")
    goal = str(payload.pop("goal", "") or f"invoke {tool_name}")
    repo_snapshot_id = str(
        payload.pop("repo_snapshot_id", "") or ctx.repo_snapshot.snapshot_id
    )
    path_scope = tuple(payload.pop("path_scope", ()) or ())
    top_k = int(payload.pop("top_k", 0) or 0)
    depth = int(payload.pop("depth", 0) or 0)
    node_budget = int(payload.pop("node_budget", 0) or 0)
    # Remaining kwargs are tool-specific arguments (query, path, symbol, etc.).
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=tool_kind,
        obligation_id=obligation_id,
        goal=goal,
        repo_snapshot_id=repo_snapshot_id,
        path_scope=path_scope,
        top_k=top_k,
        depth=depth,
        node_budget=node_budget,
        arguments=payload,
    )


def _manifest_digest(exports: list[LangChainResearchToolExport]) -> str:
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "mode": MANIFEST_MODE,
        "tools": [
            {
                "name": export.name,
                "tool_kind": export.tool_kind,
                "args_schema_name": export.args_schema_name,
                "args_schema": export.args_schema,
                "required_input_fields": list(export.required_input_fields),
                "return_fields": list(export.return_fields),
                "security_mutations": list(export.security_mutations),
            }
            for export in exports
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "MANIFEST_MODE",
    "MANIFEST_SCHEMA_VERSION",
    "LangChainResearchToolExport",
    "LangChainResearchToolManifest",
    "RESEARCH_TOOL_CALL_REQUIRED_FIELDS",
    "RESEARCH_TOOL_RETURN_FIELDS",
    "RESEARCH_TOOL_SECURITY_MUTATIONS",
    "RESEARCH_TOOL_DESCRIPTIONS",
    "build_research_structured_tools",
    "build_research_tool_manifest",
    "load_research_tool_manifest",
    "write_research_tool_manifest",
]
