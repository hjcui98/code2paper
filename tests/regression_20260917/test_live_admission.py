"""§14.1：live 准入预检（离线可跑；不联网、不写 run 目录）。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from code2paper.agentic.live_admission_preflight import (
    build_offline_suite_receipt,
    parse_runtime_probe,
    preflight_live_admission,
    read_offline_suite_receipt,
    write_offline_suite_receipt,
)
from code2paper.llm.client import LLMConfig, LLMProvider

from . import incident_archive

LIVE_MODEL = "qwen38-27b-nvfp4"
OFFLINE_COMMAND = "python -m pytest -q -m 'not live_llm' tests"
OFFLINE_OUTPUT = "3714 passed, 3 deselected, 12 subtests passed in 900.00s"


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _authored_repo(tmp_path: Path, *, name: str = "target") -> Path:
    """构造一个可做目标身份的仓库：一次提交 + 一个被声明的源文件。"""

    root = tmp_path / name
    if (root / ".git").is_dir():
        return root
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "README.md").write_text("# target\n", encoding="utf-8")
    _git("init", "-q", cwd=root)
    _git("add", "-A", cwd=root)
    _git(
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=test",
        "commit",
        "-q",
        "-m",
        "init",
        cwd=root,
    )
    return root


def _materials(tmp_path: Path) -> tuple[Path, Path]:
    intent = tmp_path / "author_intent.yaml"
    intent.write_text("title: demo\nscope: [core]\n", encoding="utf-8")
    claims = tmp_path / "claims.json"
    claims.write_text('{"claims": []}\n', encoding="utf-8")
    return intent, claims


def _live_config() -> LLMConfig:
    return LLMConfig(provider=LLMProvider.OPENAI, model=LIVE_MODEL)


def _ready_probe() -> object:
    return parse_runtime_probe(
        models_payload={"data": [{"id": LIVE_MODEL}]},
        health_payload={"status": "ok"},
    )


def _offline_receipt(**overrides: object):
    payload: dict[str, object] = {
        "command": OFFLINE_COMMAND,
        "exit_code": 0,
        "output": OFFLINE_OUTPUT,
    }
    payload.update(overrides)
    return build_offline_suite_receipt(**payload)  # type: ignore[arg-type]


def _preflight(tmp_path: Path, out_root: Path, **overrides: object):
    repo = overrides.pop("repo_path", None) or _authored_repo(tmp_path)
    intent, claims = _materials(tmp_path)
    payload: dict[str, object] = {
        "repo_path": repo,
        "author_intent_path": intent,
        "claims_path": claims,
        "llm_config": _live_config(),
        "run_open_mode": "new",
        "model_context_tokens": 131072,
        "max_writer_calls": 40,
        "max_total_input_tokens": 4_000_000,
        "runtime_probe": _ready_probe(),
        "offline_suite_receipt": _offline_receipt(),
    }
    payload.update(overrides)
    return preflight_live_admission(out_root, **payload)  # type: ignore[arg-type]


def test_all_conditions_declared_makes_a_fresh_run_ready(tmp_path: Path) -> None:
    out_root = tmp_path / "out"
    report = _preflight(tmp_path, out_root)

    assert report.ready is True, report.render()
    assert report.blockers == ()
    assert report.execution_id
    assert report.execution_identity_digest
    assert not out_root.exists(), "预检必须只读：不得创建 run 目录"
    names = {gate.name for gate in report.gates}
    assert {
        "engine_identity",
        "target_identity",
        "author_materials",
        "model_profile_identity",
        "declared_budget",
        "transport_policy",
        "runtime_model_identity",
        "run_open_decision",
    } <= names
    assert "READY" in report.render()


def test_undeclared_budget_blocks_admission(tmp_path: Path) -> None:
    report = _preflight(
        tmp_path,
        tmp_path / "out",
        model_context_tokens=0,
        max_writer_calls=0,
        max_total_input_tokens=0,
    )
    assert report.ready is False
    assert "run_budget_not_declared" in report.blockers
    budget = next(gate for gate in report.gates if gate.name == "declared_budget")
    assert budget.passed is False


def test_unset_model_blocks_admission(tmp_path: Path) -> None:
    report = _preflight(tmp_path, tmp_path / "out", llm_config=None)
    assert report.ready is False
    assert "model_identity_unresolved" in report.blockers


def test_missing_author_material_blocks_admission(tmp_path: Path) -> None:
    absent_intent = _preflight(tmp_path, tmp_path / "out-a", author_intent_path=None)
    assert absent_intent.ready is False
    assert "author_material_missing" in absent_intent.blockers

    # 声明了 claims 却不存在 → 阻断（不静默把身份降级成"无 claims"）。
    declared_missing = _preflight(
        tmp_path, tmp_path / "out-b", claims_path=tmp_path / "absent.json"
    )
    assert declared_missing.ready is False
    assert "author_material_missing" in declared_missing.blockers

    # claims 未声明是产品允许的输入组合 → 只告警，不影响准入。
    omitted = _preflight(tmp_path, tmp_path / "out-c", claims_path=None)
    assert omitted.ready is True
    assert any("claims not supplied" in warning for warning in omitted.warnings)


def test_fork_authoring_requires_verified_research_import(tmp_path: Path) -> None:
    """L2 走 fork_authoring：没有可信研究导入时必须在预检就被拒。"""

    unverifiable = _preflight(tmp_path, tmp_path / "fork-a", run_open_mode="fork_authoring")
    assert unverifiable.ready is False
    assert "research_import_unverifiable" in unverifiable.blockers
    assert "run_open_rejected:research_import_unverifiable" in unverifiable.blockers

    # 空壳 JSON（无身份绑定）同样不算可信导入。
    shell = tmp_path / "checkpoint.json"
    shell.write_text('{"run_id": "x"}\n', encoding="utf-8")
    shell_only = _preflight(
        tmp_path,
        tmp_path / "fork-b",
        run_open_mode="fork_authoring",
        research_import_path=shell,
    )
    assert shell_only.ready is False
    assert "research_import_unverifiable" in shell_only.blockers

    bound = tmp_path / "checkpoint_bound.json"
    bound.write_text(
        json.dumps(
            {
                "run_id": "research-1",
                "repo_snapshot_id": "commit-1",
                "project_tree_hash": "sha256:tree",
            }
        ),
        encoding="utf-8",
    )
    verifiable = _preflight(
        tmp_path,
        tmp_path / "fork-c",
        run_open_mode="fork_authoring",
        research_import_path=bound,
    )
    assert verifiable.ready is True, verifiable.render()
    # 研究导入参与身份：不同 checkpoint 内容 → 不同 execution_id。
    assert verifiable.execution_id != unverifiable.execution_id


def test_non_empty_directory_rejected_for_new_mode(tmp_path: Path) -> None:
    out_root = tmp_path / "out"
    out_root.mkdir(parents=True)
    (out_root / "leftover.txt").write_text("x", encoding="utf-8")

    report = _preflight(tmp_path, out_root)
    assert report.ready is False
    assert "run_open_rejected:run_directory_not_empty" in report.blockers
    assert report.run_open_decision["allowed_next_action"]


def test_runtime_probe_must_serve_configured_model(tmp_path: Path) -> None:
    mismatch = _preflight(
        tmp_path,
        tmp_path / "out-mismatch",
        runtime_probe=parse_runtime_probe(
            models_payload={"data": [{"id": "some-other-model"}]},
            health_payload={"status": "ok"},
        ),
    )
    assert mismatch.ready is False
    assert "runtime_model_identity_mismatch" in mismatch.blockers

    unhealthy = _preflight(
        tmp_path,
        tmp_path / "out-unhealthy",
        runtime_probe=parse_runtime_probe(
            models_payload={"data": [{"id": LIVE_MODEL}]},
            health_payload={"status": "loading"},
        ),
    )
    assert unhealthy.ready is False
    assert "runtime_model_identity_mismatch" in unhealthy.blockers

    absent = _preflight(tmp_path, tmp_path / "out-absent", runtime_probe=None)
    assert absent.ready is True
    assert any("runtime probe not supplied" in warning for warning in absent.warnings)


def test_probe_parser_reads_served_models_and_health() -> None:
    probe = parse_runtime_probe(
        models_payload={"data": [{"id": f"{LIVE_MODEL}:latest"}, {"id": "other"}]},
        health_payload={"status": "ok"},
    )
    assert probe.health_ok is True
    assert probe.served_models == ("other", f"{LIVE_MODEL}:latest")
    assert probe.serves(LIVE_MODEL) is True
    assert probe.serves("unconfigured-model") is False
    assert probe.serves("") is False


def test_offline_receipt_is_required_and_bound_to_engine_digest(tmp_path: Path) -> None:
    """§14.1："offline 全链通过" 必须是有证据、且绑定当前引擎指纹的前置条件。"""

    missing = _preflight(tmp_path, tmp_path / "out-a", offline_suite_receipt=None)
    assert missing.ready is False
    assert "offline_suite_receipt_missing" in missing.blockers

    failed = _preflight(
        tmp_path,
        tmp_path / "out-b",
        offline_suite_receipt=_offline_receipt(
            exit_code=1, output="1 failed, 3713 passed, 3 deselected in 900.00s"
        ),
    )
    assert failed.ready is False
    assert "offline_suite_not_passed" in failed.blockers

    stale = _preflight(
        tmp_path,
        tmp_path / "out-c",
        offline_suite_receipt=_offline_receipt().model_copy(
            update={"engine_source_digest": "sha256:from-an-older-edit"}
        ),
    )
    assert stale.ready is False
    assert "offline_suite_receipt_stale" in stale.blockers

    # 未修改引擎时，回执与当前指纹一致 → 放行；只读、不建目录。
    assert _preflight(tmp_path, tmp_path / "out-d").ready is True


def test_receipt_parses_real_pytest_summary_and_roundtrips(tmp_path: Path) -> None:
    receipt = build_offline_suite_receipt(
        command=OFFLINE_COMMAND, exit_code=0, output=OFFLINE_OUTPUT
    )
    assert (receipt.passed, receipt.passed_count, receipt.failed_count) == (True, 3714, 0)
    assert receipt.deselected_count == 3

    timeout = build_offline_suite_receipt(
        command=OFFLINE_COMMAND, exit_code=124, output="timeout after 7200s"
    )
    assert timeout.passed is False and timeout.passed_count == 0

    path = write_offline_suite_receipt(tmp_path / "receipts" / "offline.json", receipt)
    assert read_offline_suite_receipt(path) == receipt
    assert _preflight(tmp_path, tmp_path / "out-path", offline_suite_receipt=path).ready is True


def test_preflight_cli_reports_ready_and_not_ready(tmp_path: Path, capsys) -> None:
    from code2paper.cli.agentic_run import method_agent_main

    repo = _authored_repo(tmp_path)
    intent, claims = _materials(tmp_path)
    receipt_path = write_offline_suite_receipt(tmp_path / "receipt.json", _offline_receipt())
    common = [
        "--repo",
        str(repo),
        "--author-intent",
        str(intent),
        "--claims",
        str(claims),
        "--llm-provider",
        "openai",
        "--llm-model",
        LIVE_MODEL,
        "--run-open-mode",
        "new",
        "--offline-receipt",
        str(receipt_path),
    ]

    # 未声明预算 → 不可进入 live，退出码 3，且不创建目录。
    out_root = tmp_path / "cli-out"
    assert (
        method_agent_main(
            ["live-admission", "--out", str(out_root), "--context-tokens", "0", *common]
        )
        == 3
    )
    rendered = capsys.readouterr().out
    assert "NOT READY" in rendered and "run_budget_not_declared" in rendered
    assert not out_root.exists()

    # 预算与部署探测齐备 → READY，退出码 0。
    exit_code = method_agent_main(
        [
            "live-admission",
            "--out",
            str(out_root),
            "--context-tokens",
            "131072",
            "--max-writer-calls",
            "40",
            "--max-input-tokens",
            "4000000",
            "--json",
            *common,
        ]
    )
    assert exit_code == 0, capsys.readouterr().out
    payload = json.loads(capsys.readouterr().out)
    assert payload["ready"] is True
    assert payload["execution_id"]


def test_read_only_subcommands_bypass_the_worker_supervisor(tmp_path: Path, capsys) -> None:
    """`method-agent doctor|live-admission` 不能被包进 worker 监督进程。"""

    from code2paper.cli.agentic_run import supervised_method_agent_main

    repo = _authored_repo(tmp_path)
    intent, claims = _materials(tmp_path)
    receipt_path = write_offline_suite_receipt(tmp_path / "receipt.json", _offline_receipt())
    out_root = tmp_path / "supervised-out"
    exit_code = supervised_method_agent_main(
        [
            "live-admission",
            "--out",
            str(out_root),
            "--repo",
            str(repo),
            "--author-intent",
            str(intent),
            "--claims",
            str(claims),
            "--llm-provider",
            "openai",
            "--llm-model",
            LIVE_MODEL,
            "--run-open-mode",
            "new",
            "--offline-receipt",
            str(receipt_path),
        ]
    )
    assert exit_code == 3, capsys.readouterr().out
    assert "NOT READY" in capsys.readouterr().out
    # 监督器会创建 attempt 目录、进程清单与日志；只读命令不得留下这些副作用。
    assert not out_root.exists()

    assert supervised_method_agent_main(["doctor", "--out", str(incident_archive.archive_root())]) == 0
    assert "NEXT ACTION" in capsys.readouterr().out


def test_determinism_and_dirty_engine_are_recorded(tmp_path: Path) -> None:
    out_root = tmp_path / "out"
    first = _preflight(tmp_path, out_root)
    second = _preflight(tmp_path, out_root)

    assert first.execution_identity_digest == second.execution_identity_digest
    assert first.engine["commit_sha"] == second.engine["commit_sha"]
    # 本仓库工作树有意的未提交改动必须被显式记录，而不是静默忽略。
    if first.engine["dirty_entry_count"]:
        assert any("dirty" in warning for warning in first.warnings)


def test_incident_archive_cannot_be_admitted_for_resume() -> None:
    """冻结事故归档必须被拒：它没有引擎指纹，且 invocation 已耗尽内容预算。"""

    report = preflight_live_admission(
        incident_archive.archive_root(),
        repo_path=incident_archive.archive_root(),
        llm_config=LLMConfig(provider=LLMProvider.OPENAI, model=LIVE_MODEL),
        run_open_mode="resume",
        model_context_tokens=131072,
        max_writer_calls=16,
        max_total_input_tokens=1_000_000,
    )
    assert report.ready is False
    assert any(blocker.startswith("run_open_rejected:") for blocker in report.blockers)
    assert "model_identity_unresolved" not in report.blockers
    assert report.run_open_decision["effective_mode"] == "resume"
    assert report.render().splitlines()[0] == "LIVE ADMISSION  NOT READY"
