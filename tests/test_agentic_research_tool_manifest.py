"""R1.3 tests for the research tool manifest and LangChain StructuredTool wrappers.

Covers:

- ``build_research_tool_manifest`` produces a manifest covering all four
  minimal research tools with content-addressed digest;
- the manifest round-trips through ``write_research_tool_manifest`` /
  ``load_research_tool_manifest`` without loss;
- each export carries the R1.2 contract field lists
  (``required_input_fields`` / ``return_fields``) and the R1.4 security
  mutation list;
- ``build_research_structured_tools`` returns real LangChain
  ``StructuredTool`` objects bound to a :class:`ResearchToolContext` that
  funnel through ``execute_research_tool`` so the security floor applies.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_tool_manifest import (
    MANIFEST_MODE,
    MANIFEST_SCHEMA_VERSION,
    RESEARCH_TOOL_CALL_REQUIRED_FIELDS,
    RESEARCH_TOOL_RETURN_FIELDS,
    RESEARCH_TOOL_SECURITY_MUTATIONS,
    LangChainResearchToolExport,
    LangChainResearchToolManifest,
    build_research_structured_tools,
    build_research_tool_manifest,
    load_research_tool_manifest,
    write_research_tool_manifest,
)
from code2paper.agentic.research_tools import RESEARCH_TOOL_NAMES, ResearchToolContext


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


_TRAIN_PY = """\
from lib.model import Model


class Trainer:
    def train_loop(self) -> None:
        self.model = Model()
"""


_LIB_MODEL_PY = """\
class Model:
    def forward(self, batch: int) -> int:
        return batch * 2
"""


@pytest.fixture()
def ctx(tmp_path: Path) -> ResearchToolContext:
    root = tmp_path / "repo"
    (root / "lib").mkdir(parents=True)
    (root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "train.py").write_text(_TRAIN_PY, encoding="utf-8")
    (root / "lib" / "model.py").write_text(_LIB_MODEL_PY, encoding="utf-8")
    snapshot = build_repo_snapshot(root)
    return ResearchToolContext(repo_snapshot=snapshot)


# ---------------------------------------------------------------------------
# build_research_tool_manifest
# ---------------------------------------------------------------------------


def test_build_research_tool_manifest_covers_all_minimal_tools() -> None:
    manifest = build_research_tool_manifest()
    assert manifest.schema_version == MANIFEST_SCHEMA_VERSION
    assert manifest.mode == MANIFEST_MODE
    assert manifest.tool_count == len(RESEARCH_TOOL_NAMES)
    names = {tool.name for tool in manifest.tools}
    assert names == set(RESEARCH_TOOL_NAMES)


def test_build_research_tool_manifest_is_content_addressed() -> None:
    m1 = build_research_tool_manifest()
    m2 = build_research_tool_manifest()
    assert m1.content_digest == m2.content_digest
    assert m1.content_digest.startswith("sha256:")


def test_build_research_tool_manifest_rejects_unknown_tool_name() -> None:
    with pytest.raises(KeyError):
        build_research_tool_manifest(tool_names=("not_a_real_tool",))


def test_every_export_carries_required_input_fields() -> None:
    manifest = build_research_tool_manifest()
    for export in manifest.tools:
        assert export.required_input_fields == RESEARCH_TOOL_CALL_REQUIRED_FIELDS


def test_every_export_carries_return_fields() -> None:
    manifest = build_research_tool_manifest()
    for export in manifest.tools:
        assert export.return_fields == RESEARCH_TOOL_RETURN_FIELDS
        # Spot-check the most important return fields.
        for required in (
            "status",
            "source_authority",
            "result_refs",
            "exact_span_ids",
            "input_digest",
            "output_digest",
            "diagnostics",
        ):
            assert required in export.return_fields


def test_every_export_carries_security_mutations() -> None:
    manifest = build_research_tool_manifest()
    for export in manifest.tools:
        assert export.security_mutations == RESEARCH_TOOL_SECURITY_MUTATIONS
        # The six R1.4 mutations must all be listed.
        for mutation in (
            "snapshot_external_path_rejected",
            "hint_authority_cannot_anchor_positive_claim",
            "forged_symbol_id_rejected",
            "truncated_not_treated_as_exhausted",
            "digest_stable_for_same_input",
            "freshness_fails_when_repo_drifts",
        ):
            assert mutation in export.security_mutations


def test_every_export_carries_args_schema_json() -> None:
    manifest = build_research_tool_manifest()
    for export in manifest.tools:
        assert export.args_schema_name, "args_schema_name must not be empty"
        assert export.args_schema, "args_schema JSON must not be empty"
        # The schema must be a valid JSON Schema dict with at least the
        # common fields every research tool input binds.
        assert export.args_schema.get("type") == "object"
        properties = export.args_schema.get("properties", {})
        for required in ("tool_call_id", "obligation_id", "goal", "repo_snapshot_id"):
            assert required in properties, f"{export.name}: missing input field {required}"


def test_export_tool_kind_matches_research_tool_kinds() -> None:
    from code2paper.agentic.research_tools import RESEARCH_TOOL_KINDS

    manifest = build_research_tool_manifest()
    for export in manifest.tools:
        assert export.tool_kind == RESEARCH_TOOL_KINDS[export.name]


# ---------------------------------------------------------------------------
# Round-trip serialization
# ---------------------------------------------------------------------------


def test_manifest_round_trips_through_json(tmp_path: Path) -> None:
    manifest = build_research_tool_manifest()
    path = tmp_path / "manifest.json"
    written = write_research_tool_manifest(path, manifest)
    assert written == path
    assert path.exists()
    # The manifest must be valid JSON.
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert payload["mode"] == MANIFEST_MODE
    assert payload["tool_count"] == len(RESEARCH_TOOL_NAMES)
    # And reload must produce an equal manifest.
    reloaded = load_research_tool_manifest(path)
    assert reloaded == manifest


def test_manifest_forbids_extra_top_level_fields() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LangChainResearchToolManifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            mode=MANIFEST_MODE,
            tool_count=0,
            tools=[],
            totally_unknown_field="oops",
        )


def test_export_forbids_extra_fields() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LangChainResearchToolExport(
            name="find_entrypoints",
            tool_kind="symbol_search",
            description="d",
            args_schema_name="FindEntrypointsInput",
            args_schema={},
            totally_unknown_field="oops",
        )


def test_empty_manifest_factory_has_zero_tools() -> None:
    manifest = LangChainResearchToolManifest.empty()
    assert manifest.tool_count == 0
    assert manifest.tools == []
    # The empty manifest still carries schema/version for stable dispatch.
    assert manifest.schema_version == MANIFEST_SCHEMA_VERSION
    assert manifest.mode == MANIFEST_MODE


# ---------------------------------------------------------------------------
# LangChain StructuredTool wrappers
# ---------------------------------------------------------------------------


def test_build_research_structured_tools_returns_one_tool_per_name(
    ctx: ResearchToolContext,
) -> None:
    tools = build_research_structured_tools(ctx)
    assert len(tools) == len(RESEARCH_TOOL_NAMES)
    names = {tool.name for tool in tools}
    assert names == set(RESEARCH_TOOL_NAMES)


def test_structured_tool_invoke_returns_observation_payload(
    ctx: ResearchToolContext,
) -> None:
    tools = build_research_structured_tools(ctx)
    find_entrypoints = next(tool for tool in tools if tool.name == "find_entrypoints")
    payload = find_entrypoints.invoke(
        {
            "tool_call_id": "tc-manifest-1",
            "obligation_id": "obl-1",
            "goal": "find entrypoints",
            "repo_snapshot_id": ctx.repo_snapshot.snapshot_id,
            "path_scope": (),
            "top_k": 10,
        }
    )
    assert isinstance(payload, dict)
    assert payload["status"] == "success"
    assert payload["tool_name"] == "find_entrypoints"
    assert any(ref.startswith("entrypoint:") for ref in payload["result_refs"])
    # Every return field from the manifest must be present.
    for field in RESEARCH_TOOL_RETURN_FIELDS:
        assert field in payload, f"missing return field {field}"


def test_structured_tool_invoke_search_symbols_passes_arguments(
    ctx: ResearchToolContext,
) -> None:
    tools = build_research_structured_tools(ctx)
    search_symbols = next(tool for tool in tools if tool.name == "search_symbols")
    payload = search_symbols.invoke(
        {
            "tool_call_id": "tc-manifest-2",
            "obligation_id": "obl-1",
            "goal": "find Trainer",
            "repo_snapshot_id": ctx.repo_snapshot.snapshot_id,
            "path_scope": (),
            "top_k": 10,
            "query": "Trainer",
        }
    )
    assert payload["status"] == "success"
    assert any("Trainer" in ref for ref in payload["result_refs"])


def test_structured_tool_invoke_read_symbol_returns_span(
    ctx: ResearchToolContext,
) -> None:
    tools = build_research_structured_tools(ctx)
    read_symbol = next(tool for tool in tools if tool.name == "read_symbol")
    payload = read_symbol.invoke(
        {
            "tool_call_id": "tc-manifest-3",
            "obligation_id": "obl-1",
            "goal": "read Trainer",
            "repo_snapshot_id": ctx.repo_snapshot.snapshot_id,
            "path_scope": (),
            "top_k": 1,
            "path": "train.py",
            "symbol": "Trainer",
        }
    )
    assert payload["status"] == "success"
    assert any(span.startswith("span:train.py:") for span in payload["exact_span_ids"])


def test_structured_tool_invoke_find_references_returns_refs(
    ctx: ResearchToolContext,
) -> None:
    tools = build_research_structured_tools(ctx)
    find_references = next(tool for tool in tools if tool.name == "find_references")
    payload = find_references.invoke(
        {
            "tool_call_id": "tc-manifest-4",
            "obligation_id": "obl-1",
            "goal": "find Model refs",
            "repo_snapshot_id": ctx.repo_snapshot.snapshot_id,
            "path_scope": (),
            "top_k": 20,
            "symbol": "Model",
        }
    )
    assert payload["status"] == "success"
    assert any(ref.startswith("ref:") for ref in payload["result_refs"])


def test_structured_tool_invokes_funnel_through_execute_research_tool(
    ctx: ResearchToolContext,
) -> None:
    """The StructuredTool wrappers must NOT bypass the security floor.

    A snapshot-external path passed via the LangChain wrapper must still
    produce an ``invalid_request`` observation, proving the wrapper routes
    through ``execute_research_tool``.
    """

    tools = build_research_structured_tools(ctx)
    read_symbol = next(tool for tool in tools if tool.name == "read_symbol")
    payload = read_symbol.invoke(
        {
            "tool_call_id": "tc-manifest-5",
            "obligation_id": "obl-1",
            "goal": "escape attempt",
            "repo_snapshot_id": ctx.repo_snapshot.snapshot_id,
            "path_scope": (),
            "top_k": 1,
            "path": "/etc/passwd",
            "symbol": "whatever",
        }
    )
    assert payload["status"] == "invalid_request"
    assert "outside repo snapshot" in payload["error_message"]


def test_structured_tool_metadata_records_repo_snapshot_id(
    ctx: ResearchToolContext,
) -> None:
    tools = build_research_structured_tools(ctx)
    for tool in tools:
        metadata = tool.metadata or {}
        assert metadata.get("mode") == MANIFEST_MODE
        assert metadata.get("repo_snapshot_id") == ctx.repo_snapshot.snapshot_id
        assert metadata.get("contract") == "ResearchObservationV1"
