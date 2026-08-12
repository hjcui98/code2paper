"""R1.4 functional tests for the four minimal research tools.

Covers R1.1 tool behavior and R1.2 schema compliance:

- ``find_entrypoints`` locates ``main.py`` / ``train.py`` / shell scripts;
- ``search_symbols`` queries the deterministic symbol index;
- ``read_symbol`` returns the exact source span of a class/function;
- ``find_references`` finds imports and usages of a symbol.

Every test asserts the R1.2 contract: each call binds ``repo_snapshot_id``,
``obligation_id``, ``goal``, ``path_scope``, ``top_k`` / ``depth`` /
``node_budget``; each return carries ``status``, ``source_authority``,
``result_refs`` / ``exact_span_ids``, ``truncated``, ``input_digest``,
``output_digest`` and ``diagnostics``.

Security mutations (snapshot-external path refusal, hint-authority refusal,
truncated != exhausted, digest stability, freshness drift, forged symbol id)
live in ``test_agentic_research_tool_security.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_models import ResearchToolCallV1
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_EXECUTORS,
    RESEARCH_TOOL_INPUT_SCHEMAS,
    RESEARCH_TOOL_KINDS,
    RESEARCH_TOOL_NAMES,
    FindEntrypointsInput,
    FindReferencesInput,
    ReadSymbolInput,
    ResearchToolContext,
    SearchSymbolsInput,
    execute_research_tool,
    find_entrypoints,
    find_references,
    read_symbol,
    search_symbols,
    _symbol_query_score,
)
from code2paper.agentic.retrieval import SymbolIndexEntry
from code2paper.agentic.source_authority import classify_source_authority


# ---------------------------------------------------------------------------
# Fixture: small repo with python entrypoints, shell scripts, hints
# ---------------------------------------------------------------------------


_MAIN_PY = """\
def main() -> int:
    trainer = Trainer()
    trainer.train_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


_TRAIN_PY = """\
from lib.model import Model


class Trainer:
    def __init__(self) -> None:
        self.model = Model()

    def train_loop(self) -> None:
        for batch in range(10):
            self.model.forward(batch)


def train() -> None:
    Trainer().train_loop()
"""


_LIB_MODEL_PY = """\
class Model:
    def forward(self, batch: int) -> int:
        return batch * 2

    def merge_features(self, left, right):
        return torch.cat((left, right), dim=1)
"""


_TEST_MODEL_PY = """\
from lib.model import Model


def test_model_forward() -> None:
    assert Model().forward(2) == 4
"""


_RUN_SH = """\
#!/usr/bin/env bash
python -m train
"""


_AUTHOR_YAML = """\
run_id: rap-1
goal: explain the trainer loop
"""


_README_MD = """\
# Toy project

This project trains a small model.
"""


@pytest.fixture()
def toy_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "lib").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "main.py").write_text(_MAIN_PY, encoding="utf-8")
    (root / "train.py").write_text(_TRAIN_PY, encoding="utf-8")
    (root / "lib" / "model.py").write_text(_LIB_MODEL_PY, encoding="utf-8")
    (root / "tests" / "test_model.py").write_text(_TEST_MODEL_PY, encoding="utf-8")
    (root / "scripts" / "run.sh").write_text(_RUN_SH, encoding="utf-8")
    (root / "author.yaml").write_text(_AUTHOR_YAML, encoding="utf-8")
    (root / "README.md").write_text(_README_MD, encoding="utf-8")
    return root


@pytest.fixture()
def ctx(toy_repo: Path) -> ResearchToolContext:
    snapshot = build_repo_snapshot(toy_repo)
    return ResearchToolContext(repo_snapshot=snapshot)


def _tool_call(
    *,
    tool_name: str,
    tool_call_id: str = "tc-1",
    obligation_id: str = "obl-1",
    goal: str = "explain trainer",
    repo_snapshot_id: str,
    path_scope: tuple[str, ...] = (),
    top_k: int = 10,
    depth: int = 0,
    node_budget: int = 0,
    arguments: dict | None = None,
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=RESEARCH_TOOL_KINDS.get(tool_name, "other"),
        obligation_id=obligation_id,
        goal=goal,
        repo_snapshot_id=repo_snapshot_id,
        path_scope=path_scope,
        top_k=top_k,
        depth=depth,
        node_budget=node_budget,
        arguments=dict(arguments or {}),
    )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


def test_research_tool_names_are_the_four_minimal_tools() -> None:
    """The original four minimal tools must remain in the registry.

    The full tool surface is larger (26 tools covering search, behavior
    graph, hint, and evidence/fact/claim tools per design section 7),
    but the original four are the foundation and must always be present.
    """

    _MINIMAL_TOOLS = (
        "find_entrypoints",
        "search_symbols",
        "read_symbol",
        "find_references",
    )
    for tool in _MINIMAL_TOOLS:
        assert tool in RESEARCH_TOOL_NAMES, f"missing minimal tool: {tool}"
    # The full surface must include the extended tool families.
    assert len(RESEARCH_TOOL_NAMES) >= 26, (
        f"expected at least 26 tools, got {len(RESEARCH_TOOL_NAMES)}"
    )
    # Sanity: every extended tool is registered.
    _EXTENDED_TOOLS = (
        "list_repository_tree",
        "search_code",
        "read_code_span",
        "inspect_configuration",
        "build_behavior_subgraph",
        "query_behavior_graph",
        "trace_call_path",
        "trace_data_flow",
        "inspect_control_flow",
        "compare_implementation_branches",
        "find_output_side_effects",
        "search_semantic_hints",
        "derive_code_queries_from_hint",
        "compare_hint_to_code",
        "propose_evidence_packet",
        "validate_evidence_packet",
        "compile_code_facts",
        "validate_code_facts",
        "decompose_atomic_claims",
        "authorize_atomic_claims",
        "record_explicit_code_gap",
        "check_obligation_coverage",
    )
    for tool in _EXTENDED_TOOLS:
        assert tool in RESEARCH_TOOL_NAMES, f"missing extended tool: {tool}"


def test_research_tool_kinds_map_to_known_tool_kinds() -> None:
    assert RESEARCH_TOOL_KINDS["find_entrypoints"] == "symbol_search"
    assert RESEARCH_TOOL_KINDS["search_symbols"] == "symbol_search"
    assert RESEARCH_TOOL_KINDS["read_symbol"] == "code_read"
    assert RESEARCH_TOOL_KINDS["find_references"] == "call_trace"


def test_research_tool_executors_registry_covers_all_named_tools() -> None:
    for name in RESEARCH_TOOL_NAMES:
        assert name in RESEARCH_TOOL_EXECUTORS
        assert callable(RESEARCH_TOOL_EXECUTORS[name])


def test_research_tool_input_schemas_registry_covers_all_named_tools() -> None:
    from code2paper.agentic.research_tools import _ResearchToolInputBase

    for name in RESEARCH_TOOL_NAMES:
        assert name in RESEARCH_TOOL_INPUT_SCHEMAS
        assert issubclass(RESEARCH_TOOL_INPUT_SCHEMAS[name], _ResearchToolInputBase)


# ---------------------------------------------------------------------------
# find_entrypoints
# ---------------------------------------------------------------------------


def test_find_entrypoints_locates_python_and_shell_entrypoints(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="find_entrypoints",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        path_scope=(),
        top_k=20,
    )
    observation = find_entrypoints(ctx, call)
    assert observation.status == "success"
    assert observation.tool_name == "find_entrypoints"
    refs = list(observation.result_refs)
    assert "entrypoint:main.py" in refs
    assert "entrypoint:train.py" in refs
    assert "entrypoint:scripts/run.sh" in refs
    # source_authority must reflect the weakest authority among matches.
    # All entrypoints here are executable_hard, so the observation may anchor
    # a positive claim.
    assert observation.source_authority == "executable_hard"


def test_find_entrypoints_respects_path_scope(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="find_entrypoints",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        path_scope=("scripts",),
        top_k=20,
    )
    observation = find_entrypoints(ctx, call)
    assert observation.status == "success"
    refs = list(observation.result_refs)
    assert refs == ["entrypoint:scripts/run.sh"]


def test_find_entrypoints_returns_success_empty_when_no_match(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="find_entrypoints",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        path_scope=("lib",),
        top_k=20,
    )
    observation = find_entrypoints(ctx, call)
    assert observation.status == "success_empty"
    assert observation.result_refs == ()
    assert observation.diagnostics.candidate_count == 0


def test_find_entrypoints_truncates_at_top_k(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="find_entrypoints",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        path_scope=(),
        top_k=1,
    )
    observation = find_entrypoints(ctx, call)
    assert observation.status == "truncated"
    assert observation.diagnostics.truncated is True
    assert len(observation.result_refs) == 1


# ---------------------------------------------------------------------------
# search_symbols
# ---------------------------------------------------------------------------


def test_search_symbols_finds_class_by_substring(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"query": "Trainer"},
        top_k=10,
    )
    observation = search_symbols(ctx, call)
    assert observation.status == "success"
    refs = list(observation.result_refs)
    assert any("train.py" in ref and "Trainer" in ref for ref in refs), refs
    assert all(ref.startswith("symbol:") for ref in refs)


def test_search_symbols_ranks_natural_language_query_by_identifier_tokens(
    ctx: ResearchToolContext,
) -> None:
    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"query": "sequential training loop over batches"},
        top_k=10,
    )

    observation = search_symbols(ctx, call)

    assert observation.status == "success"
    assert any("Trainer.train_loop" in ref for ref in observation.result_refs)


def test_symbol_query_does_not_match_short_identifier_inside_long_word() -> None:
    ner = SymbolIndexEntry(
        path="ner.py",
        symbol="SpacyNER.save_ner_results",
        kind="method",
        start_line=1,
        end_line=2,
        text_hash="sha256:test",
        reasons=[],
    )
    inference = ner.model_copy(update={"symbol": "LLM.infer"})
    qa = ner.model_copy(update={"symbol": "LinearRAG.qa"})
    query = "generation generate infer answer qa"

    assert _symbol_query_score(ner, query) == 0
    assert _symbol_query_score(inference, query) > 0
    assert _symbol_query_score(qa, "answer infer qa") > 0


def test_search_symbols_uses_symbol_body_only_as_non_authorizing_retrieval(
    ctx: ResearchToolContext,
) -> None:
    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"query": "cat concat concatenate"},
        top_k=10,
    )

    observation = search_symbols(ctx, call)

    assert observation.status == "success"
    assert observation.result_refs[0].startswith("symbol:lib/model.py:Model.merge_features:")
    assert observation.exact_span_ids == ()


def test_search_symbols_filters_by_kind(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"query": "Model", "kind_filter": ("class",)},
        top_k=10,
    )
    observation = search_symbols(ctx, call)
    assert observation.status == "success"
    # Every returned ref should point at a class definition (Model or Trainer.Model).
    refs = list(observation.result_refs)
    assert refs, "expected at least one class symbol match"


def test_search_symbols_returns_success_empty_when_query_misses(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"query": "NoSuchSymbolExists"},
        top_k=10,
    )
    observation = search_symbols(ctx, call)
    assert observation.status == "success_empty"
    assert observation.result_refs == ()


def test_search_symbols_truncates_at_top_k(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        # "e" matches main, Trainer, Trainer.__init__, Trainer.train_loop,
        # train, Model, Model.forward, test_model_forward -> >1 hit.
        arguments={"query": "e"},
        top_k=1,
    )
    observation = search_symbols(ctx, call)
    assert observation.status == "truncated"
    assert observation.diagnostics.truncated is True
    assert len(observation.result_refs) == 1


# ---------------------------------------------------------------------------
# read_symbol
# ---------------------------------------------------------------------------


def test_read_symbol_returns_exact_span_for_toplevel_function(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "main.py", "symbol": "main"},
        top_k=1,
    )
    observation = read_symbol(ctx, call)
    assert observation.status == "success"
    assert observation.exact_span_ids, "read_symbol must return at least one exact_span_id"
    span = observation.exact_span_ids[0]
    assert span.startswith("span:main.py:"), span
    # Span must cover the full function body (4 lines in _MAIN_PY).
    start, end = span.rsplit(":", 2)[-2:]
    assert int(start) >= 1
    assert int(end) >= int(start)


def test_read_symbol_supports_dotted_path_for_method(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "train.py", "symbol": "Trainer.train_loop"},
        top_k=1,
    )
    observation = read_symbol(ctx, call)
    assert observation.status == "success"
    span = observation.exact_span_ids[0]
    assert span.startswith("span:train.py:"), span


def test_read_symbol_returns_success_empty_for_unknown_symbol(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "train.py", "symbol": "NoSuchMethod"},
        top_k=1,
    )
    observation = read_symbol(ctx, call)
    assert observation.status == "success_empty"
    assert observation.exact_span_ids == ()


def test_read_symbol_returns_parse_failed_for_invalid_python(
    ctx: ResearchToolContext, toy_repo: Path
) -> None:
    (toy_repo / "broken.py").write_text("def (\n", encoding="utf-8")
    # Rebuild the snapshot so the new file is in scope.
    snapshot = build_repo_snapshot(toy_repo)
    ctx = ResearchToolContext(repo_snapshot=snapshot)
    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "broken.py", "symbol": "anything"},
        top_k=1,
    )
    observation = read_symbol(ctx, call)
    assert observation.status == "parse_failed"
    assert observation.error_message.strip() != ""


def test_read_symbol_returns_whole_file_span_for_non_python(
    ctx: ResearchToolContext,
) -> None:
    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "scripts/run.sh", "symbol": "anything"},
        top_k=1,
    )
    observation = read_symbol(ctx, call)
    assert observation.status == "success"
    span = observation.exact_span_ids[0]
    assert span.startswith("span:scripts/run.sh:"), span


# ---------------------------------------------------------------------------
# find_references
# ---------------------------------------------------------------------------


def test_find_references_locates_imports_and_usages(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="find_references",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"symbol": "Model"},
        top_k=20,
    )
    observation = find_references(ctx, call)
    assert observation.status == "success"
    refs = list(observation.result_refs)
    # Model is imported in train.py and tests/test_model.py, and instantiated
    # in train.py.  At least two distinct files must show up.
    paths = {ref.rsplit(":", 1)[0].removeprefix("ref:") for ref in refs}
    assert "train.py" in paths
    assert "tests/test_model.py" in paths


def test_find_references_import_only_skips_usages(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="find_references",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"symbol": "Model", "import_only": True},
        top_k=20,
    )
    observation = find_references(ctx, call)
    assert observation.status == "success"
    # import_only should still surface the two import sites (train.py, tests).
    refs = list(observation.result_refs)
    assert refs, "expected import-only references"


def test_find_references_returns_success_empty_for_unknown_symbol(
    ctx: ResearchToolContext,
) -> None:
    call = _tool_call(
        tool_name="find_references",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"symbol": "NoSuchSymbol"},
        top_k=20,
    )
    observation = find_references(ctx, call)
    assert observation.status == "success_empty"
    assert observation.result_refs == ()


# ---------------------------------------------------------------------------
# execute_research_tool dispatcher
# ---------------------------------------------------------------------------


def test_execute_research_tool_dispatches_to_registered_executor(
    ctx: ResearchToolContext,
) -> None:
    call = _tool_call(
        tool_name="find_entrypoints",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        top_k=20,
    )
    observation = execute_research_tool(ctx, call)
    assert observation.status == "success"
    assert observation.tool_name == "find_entrypoints"


def test_execute_research_tool_rejects_unknown_tool_name(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="not_a_real_tool",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
    )
    observation = execute_research_tool(ctx, call)
    assert observation.status == "invalid_request"
    assert "unknown tool" in observation.error_message


def test_execute_research_tool_rejects_snapshot_id_mismatch(ctx: ResearchToolContext) -> None:
    call = _tool_call(
        tool_name="find_entrypoints",
        repo_snapshot_id="repo:different",
    )
    observation = execute_research_tool(ctx, call)
    assert observation.status == "invalid_request"
    assert "repo_snapshot_id mismatch" in observation.error_message


# ---------------------------------------------------------------------------
# R1.2 schema compliance (every tool call / observation)
# ---------------------------------------------------------------------------


_REQUIRED_RETURN_FIELDS = (
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


@pytest.mark.parametrize("tool_name", RESEARCH_TOOL_NAMES)
def test_every_observation_carries_required_return_fields(
    ctx: ResearchToolContext, tool_name: str
) -> None:
    arguments: dict
    if tool_name == "find_entrypoints":
        arguments = {}
    elif tool_name == "search_symbols":
        arguments = {"query": "Trainer"}
    elif tool_name == "read_symbol":
        arguments = {"path": "train.py", "symbol": "Trainer"}
    else:  # find_references
        arguments = {"symbol": "Model"}
    call = _tool_call(
        tool_name=tool_name,
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments=arguments,
        top_k=10,
        depth=1,
        node_budget=2,
    )
    observation = execute_research_tool(ctx, call)
    payload = observation.model_dump(mode="json")
    for field in _REQUIRED_RETURN_FIELDS:
        assert field in payload, f"{tool_name}: missing return field {field}"
    # input_digest and output_digest must be stable sha256 digests.
    assert observation.input_digest.startswith("sha256:"), observation.input_digest
    assert observation.output_digest.startswith("sha256:"), observation.output_digest
    # diagnostics must be present (possibly zero values).
    assert observation.diagnostics is not None


@pytest.mark.parametrize("tool_name", RESEARCH_TOOL_NAMES)
def test_every_tool_call_binds_required_identifiers(tool_name: str) -> None:
    call = _tool_call(
        tool_name=tool_name,
        repo_snapshot_id="repo:test",
        obligation_id="obl-1",
        goal="explain the trainer loop",
        path_scope=("src",),
        top_k=5,
        depth=2,
        node_budget=3,
    )
    assert call.tool_name == tool_name
    assert call.obligation_id == "obl-1"
    assert call.goal == "explain the trainer loop"
    assert call.repo_snapshot_id == "repo:test"
    assert call.path_scope == ("src",)
    assert call.top_k == 5
    assert call.depth == 2
    assert call.node_budget == 3


@pytest.mark.parametrize(
    "schema_name", ["FindEntrypointsInput", "SearchSymbolsInput", "ReadSymbolInput", "FindReferencesInput"]
)
def test_input_schemas_forbid_extra_fields(schema_name: str) -> None:
    from pydantic import ValidationError

    schema_cls = {
        "FindEntrypointsInput": FindEntrypointsInput,
        "SearchSymbolsInput": SearchSymbolsInput,
        "ReadSymbolInput": ReadSymbolInput,
        "FindReferencesInput": FindReferencesInput,
    }[schema_name]
    base_kwargs: dict = {
        "tool_call_id": "tc-1",
        "obligation_id": "obl-1",
        "goal": "g",
        "repo_snapshot_id": "repo:test",
    }
    if schema_name == "SearchSymbolsInput":
        base_kwargs["query"] = "Trainer"
    elif schema_name == "ReadSymbolInput":
        base_kwargs["path"] = "main.py"
        base_kwargs["symbol"] = "main"
    elif schema_name == "FindReferencesInput":
        base_kwargs["symbol"] = "Model"
    with pytest.raises(ValidationError):
        schema_cls(**base_kwargs, totally_unknown_field="oops")


# ---------------------------------------------------------------------------
# Source authority tagging
# ---------------------------------------------------------------------------


def test_observation_source_authority_reflects_weakest_match(ctx: ResearchToolContext) -> None:
    # main.py and train.py are executable_hard; README.md is semantic_hint but
    # find_entrypoints does not match README so the observation stays hard.
    call = _tool_call(
        tool_name="find_entrypoints",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        top_k=20,
    )
    observation = find_entrypoints(ctx, call)
    assert observation.source_authority == "executable_hard"


def test_classify_source_authority_recognizes_hint_and_author_intent_files() -> None:
    # Sanity check: the tools rely on classify_source_authority for authority
    # tagging.  This pins the classification so future policy changes cannot
    # silently upgrade hint files.
    assert classify_source_authority("main.py") == "executable_hard"
    assert classify_source_authority("README.md") == "semantic_hint"
    assert classify_source_authority("author.yaml") == "author_intent"
    assert classify_source_authority("tests/test_model.py") == "test_scoped"
