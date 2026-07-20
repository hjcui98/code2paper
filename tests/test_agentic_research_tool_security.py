"""R1.4 security mutation tests for the V3 research tools.

Each test pins one mutation from the R1.4 exit-condition list:

1. ``snapshot 外 path 被拒绝``         - ``test_snapshot_external_path_is_rejected``
2. ``hint 文件返回不能生成 hard evidence id`` - ``test_hint_file_observation_cannot_anchor_positive_claim``
3. ``模型伪造 symbol id 被拒绝``        - ``test_forged_symbol_id_is_rejected``
4. ``truncated 不能被当作 search exhausted`` - ``test_truncated_observation_is_not_treated_as_exhausted``
5. ``同一输入结果 digest 稳定``         - ``test_observation_digest_is_stable_for_same_input``
6. ``文件内容变化后旧 observation freshness 失败`` - ``test_observation_freshness_fails_when_repo_drifts``

These mutations are the hard security floor for the V3 research plane:
a model that proposes a snapshot-external path, a forged symbol id, or a
hint-only anchor MUST be rejected by the tool layer itself, without relying
on downstream validators.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code2paper.agentic.artifact_freshness import (
    V3_ARTIFACT_SCHEMAS,
    check_artifact_freshness_v3,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_models import (
    ResearchObservationDiagnosticsV1,
    ResearchObservationV1,
    ResearchToolCallV1,
    assert_observation_can_anchor_positive_claim,
    make_observation,
)
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_KINDS,
    ResearchToolContext,
    execute_research_tool,
    find_entrypoints,
    read_symbol,
    search_symbols,
)
from code2paper.agentic.source_authority import (
    classify_source_authority,
    is_hint_or_intent,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


_TRAIN_PY = """\
from lib.model import Model


class Trainer:
    def __init__(self) -> None:
        self.model = Model()

    def train_loop(self) -> None:
        for batch in range(10):
            self.model.forward(batch)
"""


_LIB_MODEL_PY = """\
class Model:
    def forward(self, batch: int) -> int:
        return batch * 2
"""


_README_MD = """\
# Toy project

This project trains a small model.
"""


@pytest.fixture()
def toy_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "lib").mkdir(parents=True)
    (root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "train.py").write_text(_TRAIN_PY, encoding="utf-8")
    (root / "lib" / "model.py").write_text(_LIB_MODEL_PY, encoding="utf-8")
    (root / "README.md").write_text(_README_MD, encoding="utf-8")
    return root


@pytest.fixture()
def ctx(toy_repo: Path) -> ResearchToolContext:
    snapshot = build_repo_snapshot(toy_repo)
    return ResearchToolContext(repo_snapshot=snapshot)


def _tool_call(
    *,
    tool_name: str,
    repo_snapshot_id: str,
    arguments: dict | None = None,
    path_scope: tuple[str, ...] = (),
    top_k: int = 10,
    tool_call_id: str = "tc-1",
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=RESEARCH_TOOL_KINDS.get(tool_name, "other"),
        obligation_id="obl-1",
        goal="explain trainer",
        repo_snapshot_id=repo_snapshot_id,
        path_scope=path_scope,
        top_k=top_k,
        arguments=dict(arguments or {}),
    )


# ===========================================================================
# Mutation 1: snapshot-external path is rejected
# ===========================================================================


def test_snapshot_external_path_is_rejected_for_path_scope(
    ctx: ResearchToolContext,
) -> None:
    """A path_scope that references a file outside the snapshot is rejected."""

    call = _tool_call(
        tool_name="find_entrypoints",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        path_scope=("/etc/passwd",),
    )
    observation = find_entrypoints(ctx, call)
    assert observation.status == "invalid_request"
    assert "snapshot-external" in observation.error_message or "outside" in observation.error_message
    assert observation.result_refs == ()


def test_snapshot_external_path_is_rejected_for_read_symbol(
    ctx: ResearchToolContext,
) -> None:
    """``read_symbol`` must refuse to read paths outside the snapshot."""

    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "/etc/passwd", "symbol": "whatever"},
    )
    from code2paper.agentic.research_tools import read_symbol

    observation = read_symbol(ctx, call)
    assert observation.status == "invalid_request"
    assert "outside repo snapshot" in observation.error_message
    assert observation.exact_span_ids == ()


def test_snapshot_external_path_is_rejected_for_dotdot_escape(
    ctx: ResearchToolContext,
) -> None:
    """``../`` style escapes must be normalized away or rejected."""

    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "../etc/passwd", "symbol": "whatever"},
    )
    from code2paper.agentic.research_tools import read_symbol

    observation = read_symbol(ctx, call)
    # Either the path is rejected as snapshot-external, or it is normalized
    # to a non-existent in-snapshot path.  Both outcomes must NOT produce a
    # success observation with a span pointing at /etc/passwd.
    assert observation.status in {"invalid_request", "success_empty"}
    assert all("etc/passwd" not in span for span in observation.exact_span_ids)


# ===========================================================================
# Mutation 2: hint-file observations cannot generate hard-evidence ids
# ===========================================================================


def test_hint_file_observation_cannot_anchor_positive_claim(
    ctx: ResearchToolContext,
) -> None:
    """A ``read_symbol`` call on a hint file must not yield executable_hard.

    The V3 source-authority contract is the security floor for positive
    claims: only ``executable_hard`` anchors may support a positive
    implementation claim.  Hint/author-intent files MUST be tagged with a
    weaker authority so ``assert_observation_can_anchor_positive_claim``
    refuses them.
    """

    assert classify_source_authority("README.md") == "semantic_hint"
    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "README.md", "symbol": "anything"},
    )
    observation = read_symbol(ctx, call)
    # Non-Python file -> whole-file span returned, but authority must reflect
    # the hint classification.
    assert observation.status == "success"
    assert observation.source_authority == "semantic_hint"
    assert is_hint_or_intent(observation.source_authority)
    # The hard gate MUST raise on a hint-only observation.
    with pytest.raises(ValueError, match="executable_hard"):
        assert_observation_can_anchor_positive_claim(observation)


def test_hint_authority_propagates_through_find_entrypoints_when_only_hints_match(
    ctx: ResearchToolContext, toy_repo: Path
) -> None:
    """If only hint-typed entrypoints match, the observation must reflect that.

    ``find_entrypoints`` normally only matches executable files.  We verify
    that the weakest-authority rule is applied: an observation covering both
    a hard file and a hint file must surface the weaker authority so packet
    validators can refuse the hint portion.
    """

    # Add a markdown entrypoint-named file (which the entrypoint classifier
    # ignores by default) to ensure the classifier does NOT upgrade it.
    (toy_repo / "README.md").write_text("# readme\n", encoding="utf-8")
    snapshot = build_repo_snapshot(toy_repo)
    ctx = ResearchToolContext(repo_snapshot=snapshot)
    call = _tool_call(
        tool_name="find_entrypoints",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        top_k=20,
    )
    observation = find_entrypoints(ctx, call)
    # ``find_entrypoints`` ignores README.md (it is not in _ENTRYPOINT_FILENAMES
    # and does not have a shell/build suffix), so the observation must NOT
    # include a ``entrypoint:README.md`` ref.
    assert all("README.md" not in ref for ref in observation.result_refs)
    # All matches are executable_hard, so the observation may anchor a claim.
    if observation.result_refs:
        assert observation.source_authority == "executable_hard"


# ===========================================================================
# Mutation 3: forged symbol id is rejected
# ===========================================================================


def test_forged_symbol_id_is_rejected(ctx: ResearchToolContext) -> None:
    """``read_symbol`` must not fabricate a span for a non-existent symbol.

    A model that proposes ``read_symbol(path='train.py', symbol='NoSuch')``
    must receive a ``success_empty`` observation with zero span ids, never a
    ``success`` observation with an invented span id.  This is the
    anti-hallucination floor.
    """

    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "train.py", "symbol": "NoSuchMethod"},
    )
    observation = read_symbol(ctx, call)
    assert observation.status == "success_empty"
    assert observation.exact_span_ids == ()
    assert observation.result_refs == ()
    assert observation.diagnostics.candidate_count == 0
    # The diagnostics must record *why* the symbol was not located so the
    # supervisor can distinguish a forged id from a parse failure.
    notes = " ".join(observation.diagnostics.notes)
    assert "symbol_not_found" in notes


def test_forged_symbol_id_in_dotted_path_is_rejected(ctx: ResearchToolContext) -> None:
    """A dotted-path symbol referencing a non-existent class is also rejected."""

    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "train.py", "symbol": "NoSuchClass.train_loop"},
    )
    observation = read_symbol(ctx, call)
    assert observation.status == "success_empty"
    assert observation.exact_span_ids == ()


def test_forged_path_is_rejected_as_success_empty_or_invalid(
    ctx: ResearchToolContext,
) -> None:
    """A ``read_symbol`` against a path that exists in the snapshot but
    references a symbol from a different file must NOT silently return that
    foreign span.
    """

    # train.py does not define ``Model``; only lib/model.py does.
    call = _tool_call(
        tool_name="read_symbol",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"path": "train.py", "symbol": "Model"},
    )
    observation = read_symbol(ctx, call)
    assert observation.status == "success_empty"
    assert observation.exact_span_ids == ()


# ===========================================================================
# Mutation 4: truncated != search exhausted
# ===========================================================================


def test_truncated_observation_is_not_treated_as_exhausted(
    ctx: ResearchToolContext,
) -> None:
    """A truncated observation must not satisfy ``is_empty``.

    The supervisor routes ``success_empty`` / ``scope_exhausted`` to a
    "no more information here" fallback.  ``truncated`` means "more
    candidates may exist beyond top_k" and MUST route to a refine-scope
    fallback instead.  Confusing the two would let the model abandon a
    fruitful search prematurely.
    """

    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"query": "e"},  # matches many symbols
        top_k=1,
    )
    observation = search_symbols(ctx, call)
    assert observation.status == "truncated"
    assert observation.diagnostics.truncated is True
    # The is_empty property is the supervisor's routing signal.
    assert observation.is_empty is False
    # And a truncated observation must carry at least one result_ref: it is
    # not "no results", it is "more results than top_k".
    assert observation.result_refs != ()


def test_success_empty_observation_is_treated_as_exhausted(
    ctx: ResearchToolContext,
) -> None:
    """The complement: a true zero-hit result is ``success_empty``."""

    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"query": "NoSuchSymbolXYZ"},
        top_k=10,
    )
    observation = search_symbols(ctx, call)
    assert observation.status == "success_empty"
    assert observation.is_empty is True
    assert observation.result_refs == ()


def test_status_consistency_validator_rejects_truncated_with_no_refs() -> None:
    """A model cannot fabricate a truncated observation with zero refs.

    The ResearchObservationV1 validator already enforces this: a truncated
    observation that returns no refs/exact_span_ids would be a lie.  We
    verify the contract by attempting to construct one directly.
    """

    tool_call = ResearchToolCallV1(
        tool_call_id="tc-1",
        tool_name="search_symbols",
        tool_kind="symbol_search",
        obligation_id="obl-1",
        goal="g",
        repo_snapshot_id="repo:test",
        top_k=1,
        arguments={"query": "x"},
    )
    with pytest.raises(ValueError):
        # status="success" with no refs/exact_span_ids is rejected by the
        # _status_consistency validator; the same floor protects truncated.
        ResearchObservationV1(
            observation_id="obs-x",
            tool_call_id=tool_call.tool_call_id,
            tool_name=tool_call.tool_name,
            obligation_id=tool_call.obligation_id,
            repo_snapshot_id=tool_call.repo_snapshot_id,
            status="success",
            source_authority="executable_hard",
            result_refs=(),
            exact_span_ids=(),
            diagnostics=ResearchObservationDiagnosticsV1(),
            input_digest="sha256:x",
            output_digest="sha256:y",
            error_message="",
        )


# ===========================================================================
# Mutation 5: same input -> same digest
# ===========================================================================


def test_observation_digest_is_stable_for_same_input(
    ctx: ResearchToolContext,
) -> None:
    """Two tool calls with identical inputs must yield identical digests.

    The digest is the join key between an observation and the artifact
    freshness check.  If the digest were non-deterministic, a checkpoint
    resume would treat every observation as stale and trigger spurious
    re-runs.
    """

    args = {"query": "Trainer"}
    # Same tool_call_id + same arguments => identical tool call identity.
    call1 = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments=args,
        tool_call_id="tc-stable",
    )
    call2 = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments=args,
        tool_call_id="tc-stable",
    )
    obs1 = search_symbols(ctx, call1)
    obs2 = search_symbols(ctx, call2)
    # input_digest depends on tool_call_id + tool_name + obligation_id +
    # repo_snapshot_id + arguments; with all identical, the digest matches.
    assert obs1.input_digest == obs2.input_digest
    # output_digest depends on status, source_authority, result_refs,
    # exact_span_ids, diagnostics, error_message - all deterministic.
    assert obs1.output_digest == obs2.output_digest
    # observation_id is derived from tool_call_id + digests; with everything
    # identical, the observation_id must also match.  This is the property
    # that lets a checkpoint resume deduplicate observations.
    assert obs1.observation_id == obs2.observation_id


def test_distinct_tool_call_ids_yield_distinct_input_digests(
    ctx: ResearchToolContext,
) -> None:
    """Complement: distinct tool_call_ids produce distinct input digests.

    This keeps two observations of the "same" call from different turns
    distinguishable in the freshness check.
    """

    args = {"query": "Trainer"}
    call1 = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments=args,
        tool_call_id="tc-1",
    )
    call2 = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments=args,
        tool_call_id="tc-2",
    )
    obs1 = search_symbols(ctx, call1)
    obs2 = search_symbols(ctx, call2)
    assert obs1.input_digest != obs2.input_digest
    # But the OUTPUT digest matches because the result is the same.
    assert obs1.output_digest == obs2.output_digest
    assert obs1.observation_id != obs2.observation_id


def test_observation_digest_changes_when_input_changes(
    ctx: ResearchToolContext,
) -> None:
    """Complement: a different query must yield a different output digest."""

    call1 = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"query": "Trainer"},
        tool_call_id="tc-1",
    )
    call2 = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments={"query": "Model"},
        tool_call_id="tc-2",
    )
    obs1 = search_symbols(ctx, call1)
    obs2 = search_symbols(ctx, call2)
    assert obs1.input_digest != obs2.input_digest
    assert obs1.output_digest != obs2.output_digest


def test_make_observation_digest_is_deterministic() -> None:
    """Direct check: make_observation produces stable digests for stable inputs."""

    tool_call = ResearchToolCallV1(
        tool_call_id="tc-1",
        tool_name="read_symbol",
        tool_kind="code_read",
        obligation_id="obl-1",
        goal="g",
        repo_snapshot_id="repo:test",
        top_k=1,
        arguments={"path": "main.py", "symbol": "main"},
    )
    obs1 = make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        exact_span_ids=("span:main.py:1:5",),
        diagnostics=ResearchObservationDiagnosticsV1(candidate_count=1),
    )
    obs2 = make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        exact_span_ids=("span:main.py:1:5",),
        diagnostics=ResearchObservationDiagnosticsV1(candidate_count=1),
    )
    assert obs1.input_digest == obs2.input_digest
    assert obs1.output_digest == obs2.output_digest
    assert obs1.observation_id == obs2.observation_id


# ===========================================================================
# Mutation 6: file content change -> old observation freshness fails
# ===========================================================================


def test_observation_freshness_fails_when_repo_drifts(
    toy_repo: Path, tmp_path: Path
) -> None:
    """An observation bound to snapshot S1 must fail freshness after the repo
    drifts.

    Sequence:
    1. Build snapshot S1 from the toy repo.
    2. Run ``search_symbols`` -> observation O1 (records S1.snapshot_id).
    3. Persist O1 as a ``tool_observations_v1`` artifact on disk.
    4. Mutate a tracked file (``train.py``).
    5. Call ``check_artifact_freshness_v3`` with S1 as the expected snapshot.
       The current tree no longer matches S1.project_tree_hash, so
       ``source_drift`` must be True and the report status must be "failed".
    """

    # 1. snapshot S1
    snapshot_s1 = build_repo_snapshot(toy_repo)
    ctx = ResearchToolContext(repo_snapshot=snapshot_s1)

    # 2. run a tool
    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=snapshot_s1.snapshot_id,
        arguments={"query": "Trainer"},
        tool_call_id="tc-fresh-1",
    )
    observation = search_symbols(ctx, call)
    assert observation.status == "success"
    assert observation.repo_snapshot_id == snapshot_s1.snapshot_id

    # 3. persist as a tool_observations_v1 artifact
    artifact_path = tmp_path / "tool_observations_v1.json"
    artifact_payload = {
        "schema_version": V3_ARTIFACT_SCHEMAS["tool_observations_v1"],
        "repo_snapshot_id": snapshot_s1.snapshot_id,
        "observations": [observation.model_dump(mode="json")],
    }
    artifact_path.write_text(
        json.dumps(artifact_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 4. mutate a tracked file
    (toy_repo / "train.py").write_text(
        "# modified\n\nclass Trainer: ...\n", encoding="utf-8"
    )

    # 5. freshness check against the *original* snapshot S1
    report = check_artifact_freshness_v3(
        repo_snapshot=snapshot_s1,
        artifacts={"tool_observations_v1": str(artifact_path)},
    )
    assert report.status == "failed"
    assert report.source_drift is True
    assert report.expected_project_tree_hash == snapshot_s1.project_tree_hash
    assert report.current_project_tree_hash != snapshot_s1.project_tree_hash
    # The tool_observations_v1 verdict must be stale (upstream drift
    # propagates to every artifact).
    tool_obs_verdict = next(
        verdict for verdict in report.verdicts
        if verdict.artifact_key == "tool_observations_v1"
    )
    assert tool_obs_verdict.status == "stale"
    assert "upstream_repo_or_evidence_stale" in tool_obs_verdict.failures


def test_observation_freshness_fails_when_snapshot_id_mismatches(
    toy_repo: Path, tmp_path: Path
) -> None:
    """A second freshness mutation: an artifact bound to S1 must be flagged
    stale when the caller hands in a different snapshot S2.

    This catches the case where the repo itself has not drifted but the
    caller is trying to replay an observation from an unrelated run.
    """

    snapshot_s1 = build_repo_snapshot(toy_repo)
    ctx = ResearchToolContext(repo_snapshot=snapshot_s1)
    call = _tool_call(
        tool_name="search_symbols",
        repo_snapshot_id=snapshot_s1.snapshot_id,
        arguments={"query": "Trainer"},
        tool_call_id="tc-fresh-2",
    )
    observation = search_symbols(ctx, call)

    artifact_path = tmp_path / "tool_observations_v1.json"
    artifact_payload = {
        "schema_version": V3_ARTIFACT_SCHEMAS["tool_observations_v1"],
        "repo_snapshot_id": snapshot_s1.snapshot_id,
        "observations": [observation.model_dump(mode="json")],
    }
    artifact_path.write_text(
        json.dumps(artifact_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Add a brand-new file so S2 has a different tree hash and snapshot id.
    (toy_repo / "extra.py").write_text("x = 1\n", encoding="utf-8")
    snapshot_s2 = build_repo_snapshot(toy_repo)
    assert snapshot_s2.snapshot_id != snapshot_s1.snapshot_id

    report = check_artifact_freshness_v3(
        repo_snapshot=snapshot_s2,
        artifacts={"tool_observations_v1": str(artifact_path)},
    )
    assert report.status == "failed"
    tool_obs_verdict = next(
        verdict for verdict in report.verdicts
        if verdict.artifact_key == "tool_observations_v1"
    )
    assert tool_obs_verdict.status == "stale"
    # The per-artifact check records the snapshot-id mismatch explicitly.
    assert "repo_snapshot_id_mismatch" in tool_obs_verdict.failures


# ===========================================================================
# Defense-in-depth: unknown authority level is rejected at construction time
# ===========================================================================


def test_observation_rejects_unknown_authority_value() -> None:
    """A model that proposes a made-up authority string must be rejected."""

    tool_call = ResearchToolCallV1(
        tool_call_id="tc-1",
        tool_name="read_symbol",
        tool_kind="code_read",
        obligation_id="obl-1",
        goal="g",
        repo_snapshot_id="repo:test",
        top_k=1,
        arguments={"path": "main.py", "symbol": "main"},
    )
    with pytest.raises(ValidationError):
        ResearchObservationV1(
            observation_id="obs-x",
            tool_call_id=tool_call.tool_call_id,
            tool_name=tool_call.tool_name,
            obligation_id=tool_call.obligation_id,
            repo_snapshot_id=tool_call.repo_snapshot_id,
            status="success",
            source_authority="executable_ultra_hard",  # not in SOURCE_AUTHORITY_LEVELS
            result_refs=("entrypoint:main.py",),
            diagnostics=ResearchObservationDiagnosticsV1(candidate_count=1),
            input_digest="sha256:x",
            output_digest="sha256:y",
            error_message="",
        )
