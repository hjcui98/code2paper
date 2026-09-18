"""产物根归一化：run 根位于 `artifacts/` 之下时不得被截断到引擎树。

实测缺陷（§14.1 预检冒烟中发现）：`_out_root` 无条件截断到第一个 `artifacts`
之前，因此 out_root = `<workspace>/artifacts/runs/<run>` 的全部产物被静默写到
`<workspace>`（引擎树）里，run 自己的目录反而空空如也——证据错位且污染仓库。
"""

from __future__ import annotations

from pathlib import Path

from code2paper.core.output_names import _out_root, method_output


def test_legacy_artifact_subdirectories_still_normalize_to_the_run_root() -> None:
    root = Path("/tmp/plain-run")
    assert _out_root(root) == root
    assert _out_root(root / "artifacts") == root
    assert _out_root(root / "artifacts" / "06_authoring") == root
    assert _out_root(root / "artifacts" / "06_authoring" / "invocations") == root
    assert _out_root(root / "artifacts" / "research_product") == root
    assert _out_root(Path("/tmp/paper/method")) == Path("/tmp")


def test_run_root_nested_under_artifacts_is_never_truncated() -> None:
    root = Path("/workspace/artifacts/runs/2026-09-18-live-L1")
    assert _out_root(root) == root
    assert _out_root(root / "nested") == root / "nested"
    # 「runs」不是产物阶段目录，因此不得被当作 <run>/artifacts/<stage> 简写。
    assert _out_root(Path("/workspace/artifacts/runs")) == Path("/workspace/artifacts/runs")


def test_method_output_stays_inside_a_nested_run_root(tmp_path: Path) -> None:
    root = tmp_path / "artifacts" / "runs" / "L1"
    path = method_output(root, "publication_writer_result_v1")
    assert path == root / "artifacts" / "06_authoring" / "publication_writer_result_v1.json"
    assert root in path.parents


def test_blocked_writer_result_is_written_inside_the_nested_run_root(
    tmp_path: Path, monkeypatch
) -> None:
    """回归缺陷本体：写失败结果也不得落到 run 根之外（更不得落到引擎树）。"""

    from code2paper.agentic.publication_method_writer import run_publication_method_writer
    from code2paper.llm.client import LLMConfig, LLMProvider

    workspace = tmp_path / "engine"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    run_root = workspace / "artifacts" / "runs" / "L1"
    run_root.mkdir(parents=True)

    result, paths = run_publication_method_writer(
        out_root=run_root,
        artifact_paths={},
        llm_config=LLMConfig(provider=LLMProvider.NONE),
        run_id="nested-root-regression",
    )

    assert result.status == "blocked"
    written = Path(paths["publication_writer_result_v1"])
    assert written == run_root / "artifacts" / "06_authoring" / "publication_writer_result_v1.json"
    assert written.is_file()
    # 引擎树（cwd）下不得出现任何旁路产物。
    assert not (workspace / "artifacts" / "06_authoring").exists()
