"""LangGraph-orchestrated Code2Paper runner CLI.

Also hosts the ``method-agent`` product CLI (Agent 3, merged packages B+H):
``code2paper method-agent run --repo <repo> --author-intent <file>
--claims <file> --out <dir>`` runs the autonomous Method Agent product
path and prints a reader-facing summary of candidate/verified/review/
callback/gap state.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from code2paper.agentic.autonomous_method_agent import (
    MethodAgentSignal,
    MethodAgentRunResultV1,
    run_autonomous_method_agent,
)
from code2paper.agentic.authoring_execution_identity import preflight_run_open
from code2paper.agentic.completion_report import AgenticRunCompletionReport, load_run_completion_report
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.runner import AgenticRunResult, run_agentic_code2paper
from code2paper.agentic.checkpointing import build_memory_checkpointer, open_sqlite_checkpointer
from code2paper.core.output_paths import resolve_out_root, resolve_project_id
from code2paper.core.schemas import LLMProvider
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.schemas import LLMConfig


_LLM_PROVIDER_CHOICES = [provider.value for provider in LLMProvider] + ["moonshot", "aihubmix", "kimi"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-agentic-run",
        description="Run Code2Paper through the LangGraph agentic orchestration layer.",
    )
    parser.add_argument("project_root", help="Target code repository")
    parser.add_argument("--author", dest="author_markers_path", default="", help="Resolved or seed AuthorMarkers YAML/JSON")
    parser.add_argument(
        "--draft",
        "--intent",
        "--template",
        dest="intent_path",
        default="",
        help="Rough author intent/template YAML to resolve before evidence grounding.",
    )
    parser.add_argument("--project-id", default="")
    parser.add_argument(
        "--out-root",
        default="",
        help="Output root. Defaults to ./outputs/<repo_name>_<timestamp>/.",
    )
    parser.add_argument("--core-top-k", type=int, default=12)
    parser.add_argument("--skip-draft-bootstrap", action="store_true")
    parser.add_argument("--max-retrieval-rounds", type=int, default=0)
    parser.add_argument("--max-evidence-revision-rounds", type=int, default=0)
    parser.add_argument("--max-authoring-revision-rounds", type=int, default=0)
    parser.add_argument("--max-figure-revision-rounds", type=int, default=0)
    parser.add_argument("--max-semantic-verifier-calls", type=int, default=0)
    parser.add_argument("--llm-provider", choices=_LLM_PROVIDER_CHOICES, default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument(
        "--execution-profile",
        default="",
        help="Digest-bound D6 execution profile JSON; absent keeps the legacy route.",
    )
    parser.add_argument(
        "--execution-opt-in",
        action="store_true",
        help="Authorize an opt-in profile for this run (never overrides evidence gates).",
    )
    parser.add_argument(
        "--execution-rollback",
        action="store_true",
        help="Force the profile's rollback route and preserve the legacy default.",
    )
    parser.add_argument(
        "--execution-canary-key",
        default="",
        help="Stable key used for deterministic canary bucketing.",
    )
    parser.add_argument("--run-id", default="", help="Stable run identity used by durable checkpoints.")
    parser.add_argument("--checkpoint-db", default="", help="SQLite checkpoint database path.")
    parser.add_argument(
        "--checkpoint-backend", choices=("none", "memory", "sqlite"), default="none",
        help="Checkpoint backend; --checkpoint-db implies sqlite.",
    )
    parser.add_argument("--resume", action="store_true", help="Resume the matching run/snapshot checkpoint.")
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Return exit code 1 when the agentic graph ends with blocked_reason.",
    )
    args = parser.parse_args(argv)
    checkpoint_backend = "sqlite" if args.checkpoint_db and args.checkpoint_backend == "none" else args.checkpoint_backend
    if checkpoint_backend == "sqlite" and not args.checkpoint_db:
        parser.error("--checkpoint-backend sqlite requires --checkpoint-db")
    if args.resume and (checkpoint_backend != "sqlite" or not args.run_id):
        parser.error("--resume requires both --checkpoint-db and --run-id")

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"[code2paper-agentic-run] error=project_root_not_found:{project_root}")
        return 2
    intent_path = str(Path(args.intent_path).expanduser().resolve()) if args.intent_path else ""
    author_markers_path = str(Path(args.author_markers_path).expanduser().resolve()) if args.author_markers_path else ""
    execution_profile_path = ""
    if args.execution_profile:
        execution_profile_path = str(Path(args.execution_profile).expanduser().resolve())
        if not Path(execution_profile_path).is_file():
            parser.error(f"execution profile not found: {execution_profile_path}")
    out_root = resolve_out_root(args.out_root, project_root=project_root, intent_path=intent_path)
    project_id = resolve_project_id(args.project_id, project_root=project_root, intent_path=intent_path)

    state = AgenticRunState(
        project_root=project_root,
        out_root=out_root,
        project_id=project_id,
        run_id=args.run_id or str(uuid.uuid4()),
        author_markers_path=author_markers_path,
        intent_path=intent_path,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        execution_opt_in=bool(args.execution_opt_in),
        execution_rollback=bool(args.execution_rollback),
        execution_canary_key=str(args.execution_canary_key or ""),
        core_top_k=int(args.core_top_k),
        skip_draft_bootstrap=bool(args.skip_draft_bootstrap),
        max_retrieval_rounds=max(0, int(args.max_retrieval_rounds)),
        max_evidence_revision_rounds=max(0, int(args.max_evidence_revision_rounds)),
        max_authoring_revision_rounds=max(0, int(args.max_authoring_revision_rounds)),
        max_figure_revision_rounds=max(0, int(args.max_figure_revision_rounds)),
        max_semantic_verifier_calls=max(0, int(args.max_semantic_verifier_calls)),
        checkpoint_metadata={
            "checkpoint_backend": checkpoint_backend,
            "checkpoint_path": str(Path(args.checkpoint_db).expanduser().resolve())
            if args.checkpoint_db
            else "",
        },
        artifacts=(
            {"execution_profile": execution_profile_path}
            if execution_profile_path
            else {}
        ),
    )

    print(f"[code2paper-agentic-run] out_root={out_root}")
    try:
        if checkpoint_backend == "sqlite":
            with open_sqlite_checkpointer(Path(args.checkpoint_db).expanduser().resolve()) as checkpointer:
                result = run_agentic_code2paper(
                    state,
                    checkpointer=checkpointer,
                    resume=bool(args.resume),
                    checkpoint_backend="sqlite",
                )
        elif checkpoint_backend == "memory":
            result = run_agentic_code2paper(
                state,
                checkpointer=build_memory_checkpointer(),
                checkpoint_backend="memory",
            )
        else:
            result = run_agentic_code2paper(state)
    except (RuntimeError, ValueError) as exc:
        print(f"[code2paper-agentic-run] error={exc}")
        return 2

    print(f"[code2paper-agentic-run] status={result.summary.status}")
    if result.summary.blocked_reason:
        print(f"[code2paper-agentic-run] blocked_reason={result.summary.blocked_reason}")
    print(
        "[code2paper-agentic-run] "
        f"invariant_audit_passed={result.summary.invariant_audit_passed} "
        f"blocking_failures={result.summary.invariant_blocking_failures}"
    )
    completion_report = _load_completion_report(result)
    if completion_report:
        print(
            "[code2paper-agentic-run] "
            f"completion_status={completion_report.status} complete={completion_report.complete}"
        )
        if completion_report.missing_deliverables:
            print(
                "[code2paper-agentic-run] "
                f"missing_deliverables={','.join(completion_report.missing_deliverables)}"
            )
    print(f"[code2paper-agentic-run] decisions={len(result.summary.decisions)}")
    print(f"[code2paper-agentic-run] summary={result.summary_path}")
    print(
        json.dumps(
            {
                "status": result.summary.status,
                "blocked_reason": result.summary.blocked_reason,
                "invariant_audit_passed": result.summary.invariant_audit_passed,
                "invariant_blocking_failures": result.summary.invariant_blocking_failures,
                "completion_status": completion_report.status if completion_report else "",
                "completion_complete": completion_report.complete if completion_report else None,
                "missing_deliverables": completion_report.missing_deliverables if completion_report else [],
                "summary": str(result.summary_path),
                "artifacts": {name: record.path for name, record in result.summary.artifacts.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if args.fail_on_blocked and result.summary.blocked_reason else 0


def _load_completion_report(result: AgenticRunResult) -> AgenticRunCompletionReport | None:
    path = result.state.artifacts.get("agentic_run_completion_report")
    if not path:
        record = result.summary.artifacts.get("agentic_run_completion_report")
        path = record.path if record else ""
    return load_run_completion_report(path) if path else None


# ---------------------------------------------------------------------------
# method-agent product CLI (Agent 3, merged packages B + H)
# ---------------------------------------------------------------------------


def _apply_llm_profile(path: str) -> dict[str, str | None]:
    """Apply a bash-style ``KEY=VALUE`` LLM profile into the process env.

    Lines starting with ``#`` are skipped.  Values containing ``$``
    (shell expansion) are skipped so no command substitution is ever
    evaluated; real secrets stay in the user's shell environment.

    Returns the previous value of every key that was changed (``None``
    when the key was absent) so the caller can restore the environment
    after the run.
    """

    profile_path = Path(path)
    if not profile_path.is_file():
        raise FileNotFoundError(f"llm profile not found: {profile_path}")
    changed: dict[str, str | None] = {}
    for raw_line in profile_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not key or key.startswith("_") or not value or "$" in value:
            continue
        if key not in changed:
            changed[key] = os.environ.get(key)
        os.environ[key] = value.strip("'").strip('"')
    return changed


def _restore_env(changed: dict[str, str | None]) -> None:
    for key, previous in changed.items():
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def _load_concept_cards(path: str) -> Any | None:
    """Load an optional Stage 2/3 MethodConceptCardSetV1 JSON artifact.

    Returns ``None`` when the flag is empty (proposition lane); a missing or
    malformed file is an integrity failure, not a silent fallback.
    """
    if not str(path or "").strip():
        return None
    from code2paper.agentic.method_concept_card_models import (
        MethodConceptCardSetV1,
    )

    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"concept cards artifact not found: {resolved}")
    try:
        return MethodConceptCardSetV1.model_validate_json(
            resolved.read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(
            f"concept cards artifact invalid: {exc.__class__.__name__}:{str(exc)[:200]}"
        ) from exc


class _TeeStream:
    """Copy live CLI output to a durable run log and the caller's stream."""

    def __init__(self, primary: Any, log_file: Any) -> None:
        self._primary = primary
        self._log_file = log_file

    def write(self, value: str) -> int:
        self._primary.write(value)
        self._log_file.write(value)
        self._primary.flush()
        self._log_file.flush()
        return len(value)

    def flush(self) -> None:
        self._primary.flush()
        self._log_file.flush()

    def isatty(self) -> bool:
        return bool(getattr(self._primary, "isatty", lambda: False)())


def _write_json_atomically(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_method_process_artifact(
    out_root: Path,
    *,
    status: str,
    pid: int,
    started_at: float,
    exit_code: int | None,
    stdout_path: Path,
    stderr_path: Path,
    run_id: str,
    terminal_reason: str = "",
    attempt_id: str = "",
    supervisor_pid: int | None = None,
    worker_pid: int | None = None,
) -> Path:
    path = (
        out_root / "method_agent_attempts" / f"{attempt_id}.json"
        if attempt_id
        else out_root / "method_agent_process.json"
    )
    payload = {
        "schema_version": "1.0",
        "run_id": run_id,
        "pid": pid,
        "supervisor_pid": supervisor_pid,
        "worker_pid": worker_pid or pid,
        "attempt_id": attempt_id,
        "status": status,
        "started_at_unix": started_at,
        "ended_at_unix": time.time() if status != "running" else None,
        "exit_code": exit_code,
        "terminal_reason": terminal_reason,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }
    try:
        _write_json_atomically(path, payload)
    except OSError:
        pass
    return path


def _mark_stale_method_process(out_root: Path) -> None:
    """Mark a prior unclosed child when its PID is no longer alive.

    SIGKILL cannot be caught by the child.  This small next-start check leaves
    an explicit external-termination marker instead of treating a stale
    ``status=running`` process artifact as a successful run.
    """

    path = out_root / "method_agent_process.json"
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return
    if payload.get("status") != "running" or pid == os.getpid():
        return
    try:
        os.kill(pid, 0)
        return
    except PermissionError:
        # An inaccessible PID is not evidence that the prior process died.
        return
    except (ProcessLookupError, OSError):
        pass
    payload.update({
        "status": "external_termination_detected",
        "ended_at_unix": time.time(),
        "terminal_reason": "external_termination_detected",
        "exit_code": None,
    })
    try:
        _write_json_atomically(path, payload)
    except OSError:
        pass
    try:
        from code2paper.agentic.unified_invocation_ledger import write_run_terminal_event

        write_run_terminal_event(
            out_root / "artifacts" / "06_authoring" / "invocations",
            run_digest=str(payload.get("run_id") or "external-run"),
            terminal_reason="external_termination_detected",
            terminal_stage="method_agent",
            extra={
                "run_id": str(payload.get("run_id") or ""),
                "pid": pid,
                "stdout_path": str(payload.get("stdout_path") or ""),
                "stderr_path": str(payload.get("stderr_path") or ""),
            },
        )
    except (OSError, TypeError, ValueError):
        pass


def _latest_checkpoint_for_external_termination(out_root: Path) -> dict[str, Any]:
    try:
        from code2paper.agentic.autonomous_method_agent import (
            _latest_research_checkpoint,
        )

        return _latest_research_checkpoint(out_root)
    except (ImportError, OSError, TypeError, ValueError):
        return {}


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _worker_attempt_artifact_state(
    out_root: Path,
    attempt_id: str,
) -> dict[str, Any]:
    """Read worker-owned closure artifacts without treating stale files as current."""

    partial_path = out_root / "artifacts" / "research_product" / "run_summary.partial.json"
    terminal_path = (
        out_root
        / "artifacts"
        / "06_authoring"
        / "invocations"
        / f"run_terminal_event.{attempt_id}.json"
    )
    partial = _read_json_object(partial_path)
    terminal = _read_json_object(terminal_path)
    terminal_extra = terminal.get("extra") if isinstance(terminal, dict) else None
    partial_valid = bool(
        partial
        and str(partial.get("attempt_id") or "").strip() == attempt_id
        and str(partial.get("terminal_reason") or "").strip()
    )
    terminal_valid = bool(
        terminal
        and str(terminal.get("terminal_reason") or "").strip()
        and isinstance(terminal_extra, dict)
        and str(terminal_extra.get("attempt_id") or "").strip() == attempt_id
    )
    return {
        "partial_path": partial_path,
        "terminal_path": terminal_path,
        "partial_valid": partial_valid,
        "terminal_valid": terminal_valid,
        "terminal_reason": (
            str(terminal.get("terminal_reason") or "").strip()
            if terminal_valid
            else ""
        ),
        "exit_type": (
            str(terminal_extra.get("exit_type") or "").strip()
            if terminal_valid and isinstance(terminal_extra, dict)
            else ""
        ),
    }


def _worker_primary_terminal_source(worker_artifacts: dict[str, Any]) -> str:
    """Worker-owned evidence wins only when both closure artifacts validate."""

    return (
        "worker"
        if worker_artifacts.get("partial_valid") and worker_artifacts.get("terminal_valid")
        else "supervisor"
    )


def _persist_supervisor_observation(
    *,
    out_root: Path,
    run_id: str,
    attempt_id: str,
    worker_returncode: int,
    stop_signal: int | None,
    worker_artifacts: dict[str, Any],
    fallback_artifacts: dict[str, str],
) -> str:
    """Persist parent observations separately from worker-owned terminal evidence."""

    path = (
        out_root
        / "artifacts"
        / "06_authoring"
        / "invocations"
        / f"run_supervisor_event.{attempt_id}.json"
    )
    payload = {
        "schema_version": "1.0",
        "event_kind": "method_agent_supervisor_observation",
        "run_id": run_id,
        "attempt_id": attempt_id,
        "recorded_at_unix": time.time(),
        "worker_returncode": worker_returncode,
        "parent_stop_signal": stop_signal,
        "worker_terminal_reason": str(worker_artifacts.get("terminal_reason") or ""),
        "worker_exit_type": str(worker_artifacts.get("exit_type") or ""),
        "worker_partial_valid": bool(worker_artifacts.get("partial_valid")),
        "worker_terminal_valid": bool(worker_artifacts.get("terminal_valid")),
        "primary_terminal_source": _worker_primary_terminal_source(worker_artifacts),
        "worker_partial_path": str(worker_artifacts.get("partial_path") or ""),
        "worker_terminal_path": str(worker_artifacts.get("terminal_path") or ""),
        "fallback_artifacts": dict(fallback_artifacts),
    }
    try:
        _write_json_atomically(path, payload)
    except OSError:
        pass
    return str(path)


def _persist_external_method_termination(
    *,
    out_root: Path,
    run_id: str,
    attempt_id: str,
    returncode: int,
) -> dict[str, str]:
    """Close a worker killed outside its Python signal handlers.

    This function only writes fallback artifacts.  Worker-owned artifacts are
    preserved when they carry the current attempt id; the parent observation
    is written by ``_persist_supervisor_observation`` in a separate sidecar.
    """

    worker_artifacts = _worker_attempt_artifact_state(out_root, attempt_id)
    checkpoint = _latest_checkpoint_for_external_termination(out_root)
    if returncode < 0:
        signal_number = -returncode
        terminal_reason = f"external_termination_signal_{signal_number}"
        exit_type = "external_signal"
    else:
        terminal_reason = "external_termination"
        exit_type = "external_exit"
    preferred_partial_path = (
        out_root / "artifacts" / "research_product" / "run_summary.partial.json"
    )
    fallback_paths: dict[str, str] = {}
    if not worker_artifacts["partial_valid"]:
        partial_path = preferred_partial_path
        if partial_path.exists():
            partial_path = (
                out_root
                / "artifacts"
                / "research_product"
                / f"run_summary.partial.{attempt_id}.json"
            )
        partial_payload = {
            "schema_version": "1.0",
            "run_id": run_id,
            "attempt_id": attempt_id,
            "out_root": str(out_root),
            "status": "interrupted",
            "terminal_reason": terminal_reason,
            "exit_type": exit_type,
            "returncode": returncode,
            "checkpoint": checkpoint,
            "research": {
                "status": "incomplete",
                "termination_reason": terminal_reason,
                "turn_index": checkpoint.get("turn_index", 0),
                "agenda_statuses": checkpoint.get("agenda_statuses", {}),
            },
            "artifacts": {
                "latest_checkpoint": checkpoint.get("path", ""),
                "latest_checkpoint_digest": checkpoint.get("digest", ""),
            },
        }
        try:
            _write_json_atomically(partial_path, partial_payload)
            fallback_paths["run_summary_partial"] = str(partial_path)
        except OSError:
            pass

    terminal_path = (
        out_root
        / "artifacts"
        / "06_authoring"
        / "invocations"
        / f"run_terminal_event.supervisor.{attempt_id}.json"
    )
    if not worker_artifacts["terminal_valid"]:
        try:
            from code2paper.agentic.unified_invocation_ledger import write_run_terminal_event

            write_run_terminal_event(
                terminal_path.parent,
                run_digest=checkpoint.get("digest", "") or run_id,
                terminal_reason=terminal_reason,
                terminal_stage="method_agent_supervisor",
                extra={
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "returncode": returncode,
                    "checkpoint_path": checkpoint.get("path", ""),
                    "checkpoint_digest": checkpoint.get("digest", ""),
                },
                filename=terminal_path.name,
            )
            fallback_paths["run_terminal_event"] = str(terminal_path)
        except (OSError, TypeError, ValueError):
            pass
    return fallback_paths


def _recover_stale_method_attempts(out_root: Path) -> None:
    """Recover dead workers without overwriting prior attempt evidence."""

    attempts_root = out_root / "method_agent_attempts"
    try:
        attempt_paths = tuple(attempts_root.glob("*.json"))
    except OSError:
        return
    for attempt_path in attempt_paths:
        try:
            payload = json.loads(attempt_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("status") != "running":
                continue
            worker_pid = int(payload.get("worker_pid") or payload.get("pid") or 0)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if worker_pid <= 0:
            continue
        try:
            os.kill(worker_pid, 0)
            continue
        except PermissionError:
            continue
        except (ProcessLookupError, OSError):
            pass
        attempt_id = str(payload.get("attempt_id") or attempt_path.stem)
        run_id = str(payload.get("run_id") or "external-run")
        payload.update({
            "status": "external_termination_detected",
            "ended_at_unix": time.time(),
            "terminal_reason": "external_termination_detected",
            "exit_code": None,
        })
        try:
            _write_json_atomically(attempt_path, payload)
        except OSError:
            pass
        _persist_external_method_termination(
            out_root=out_root,
            run_id=run_id,
            attempt_id=attempt_id,
            returncode=-signal.SIGKILL,
        )


#: 只读/离线诊断命令：由 method_agent_main 直接执行，不进入 worker 监督进程。
_READ_ONLY_METHOD_AGENT_COMMANDS = frozenset(
    {
        "doctor",
        "quality-report",
        "compare-quality",
        "live-admission",
        "record-offline-receipt",
    }
)


def _read_json_optional(path: str) -> Any | None:
    value = str(path or "").strip()
    if not value:
        return None
    try:
        return json.loads(Path(value).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _live_admission_main(args: argparse.Namespace) -> int:
    """§14.1：live 准入预检（只读；不建目录、不发请求）。"""

    from code2paper.agentic.live_admission_preflight import (
        parse_runtime_probe,
        preflight_live_admission,
    )

    repo_path = Path(args.repo).expanduser().resolve()
    if not repo_path.is_dir():
        print(f"[code2paper method-agent] error=repo_not_found:{repo_path}")
        return 2
    for label in (
        "--author-intent",
        "--claims",
        "--offline-receipt",
        "--health-json",
        "--models-json",
        "--llm-profile",
        "--research-import",
    ):
        value = str(getattr(args, label.lstrip("-").replace("-", "_"), "") or "")
        if value and not Path(value).expanduser().is_file():
            print(f"[code2paper method-agent] error=input_not_found:{label}:{value}")
            return 2

    changed_env: dict[str, str | None] = {}
    try:
        if args.llm_profile:
            changed_env = _apply_llm_profile(args.llm_profile)
        llm_config = load_llm_config_from_env(
            provider=args.llm_provider or None,
            model=args.llm_model or None,
        )
        probe = None
        if args.health_json or args.models_json:
            probe = parse_runtime_probe(
                models_payload=_read_json_optional(args.models_json),
                health_payload=_read_json_optional(args.health_json),
            )
        report = preflight_live_admission(
            args.out_root,
            repo_path=repo_path,
            author_intent_path=args.author_intent or None,
            claims_path=args.claims or None,
            llm_config=llm_config,
            run_open_mode=args.run_open_mode,
            model_context_tokens=args.context_tokens,
            max_writer_calls=args.max_writer_calls,
            max_total_input_tokens=args.max_input_tokens,
            runtime_probe=probe,
            offline_suite_receipt=args.offline_receipt or None,
            research_import_path=args.research_import or None,
        )
    finally:
        _restore_env(changed_env)

    if bool(getattr(args, "json", False)):
        print(report.model_dump_json(indent=2))
    else:
        print(report.render())
    # 审计 §G.5：offline-ready 与 live-ready 用不同退出码区分，脚本无法把
    # "离线全链通过"误当成"当前服务可用"。
    #   0 = live-ready；3 = 不可进入；4 = 仅 offline-ready（未声明 --require-live-ready 时）
    if report.live_ready:
        return 0
    if not report.ready:
        return 3
    return 0 if not bool(getattr(args, "require_live_ready", False)) else 4


def _record_offline_receipt_main(args: argparse.Namespace) -> int:
    """记录一次真实离线全链结果，并绑定当前 engine source digest。"""

    from code2paper.agentic.live_admission_preflight import (
        build_offline_suite_receipt,
        write_offline_suite_receipt,
    )

    from code2paper.agentic.authoring_execution_identity import resolve_engine_root

    engine_root = resolve_engine_root() or Path.cwd()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        str(args.marker),
        str(args.pytest_target),
    ]
    exit_code = 124
    output = ""
    try:
        completed = subprocess.run(
            command,
            cwd=str(engine_root),
            capture_output=True,
            text=True,
            timeout=float(args.timeout_seconds),
            check=False,
        )
        exit_code = int(completed.returncode)
        output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    except subprocess.TimeoutExpired as exc:
        output = f"timeout after {args.timeout_seconds}s\n" + str(exc.stdout or "")
    except OSError as exc:
        output = f"failed to launch pytest: {type(exc).__name__}: {exc}"
        exit_code = 126

    receipt = build_offline_suite_receipt(
        command=f"cd {engine_root} && " + " ".join(command),
        exit_code=exit_code,
        output=output,
    )
    path = write_offline_suite_receipt(args.receipt_out, receipt)
    print(
        "[code2paper method-agent] offline receipt "
        f"path={path} passed={receipt.passed} passed_count={receipt.passed_count} "
        f"failed={receipt.failed_count} exit={receipt.exit_code} "
        f"engine={receipt.engine_source_digest[:19]}"
    )
    return 0 if receipt.passed else 1


def _method_agent_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code2paper method-agent",
        description=(
            "Run the autonomous Method Agent product path: repo + author "
            "intent + claims -> research loop -> evidence/facts/claims -> "
            "completeness -> plan readiness -> candidate/verified/review."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Read-only diagnosis of an existing run directory (no model calls).",
    )
    doctor_parser.add_argument("--out", dest="out_root", required=True, help="Run directory to inspect")
    doctor_parser.add_argument(
        "--json", action="store_true", help="Emit the structured report as JSON"
    )
    quality_parser = subparsers.add_parser(
        "quality-report",
        help=(
            "§14.3 read-only quality report: mechanically recomputable dimensions plus "
            "explicit not-measured markers (no model calls)."
        ),
    )
    quality_parser.add_argument("--out", dest="out_root", required=True, help="Run directory to measure")
    quality_parser.add_argument("--json", action="store_true", help="Emit the structured report as JSON")
    compare_parser = subparsers.add_parser(
        "compare-quality",
        help=(
            "§14.3 read-only comparison of two quality reports; refuses when the frozen "
            "input or model identity differ."
        ),
    )
    compare_parser.add_argument(
        "--baseline", required=True, help="Baseline run directory or quality report JSON"
    )
    compare_parser.add_argument(
        "--candidate", required=True, help="Candidate run directory or quality report JSON"
    )
    compare_parser.add_argument("--json", action="store_true")
    admission_parser = subparsers.add_parser(
        "live-admission",
        help=(
            "§14.1 read-only live admission preflight: identity, inputs, offline "
            "receipt, budget and run-directory state (no model calls)."
        ),
    )
    admission_parser.add_argument("--repo", dest="repo", required=True, help="Target code repository")
    admission_parser.add_argument("--out", dest="out_root", required=True, help="Planned run directory")
    admission_parser.add_argument("--author-intent", dest="author_intent", default="")
    admission_parser.add_argument("--claims", default="")
    admission_parser.add_argument("--llm-profile", dest="llm_profile", default="")
    admission_parser.add_argument("--llm-provider", default="")
    admission_parser.add_argument("--llm-model", default="")
    admission_parser.add_argument(
        "--run-open-mode",
        choices=("auto", "new", "resume", "fork_authoring"),
        default="auto",
    )
    admission_parser.add_argument("--context-tokens", dest="context_tokens", type=int, default=0)
    admission_parser.add_argument(
        "--max-writer-calls", dest="max_writer_calls", type=int, default=0
    )
    admission_parser.add_argument(
        "--max-input-tokens", dest="max_input_tokens", type=int, default=0
    )
    admission_parser.add_argument(
        "--offline-receipt",
        dest="offline_receipt",
        default="",
        help="Receipt JSON from `record-offline-receipt`, bound to the current engine digest",
    )
    admission_parser.add_argument("--health-json", dest="health_json", default="")
    admission_parser.add_argument(
        "--require-live-ready",
        dest="require_live_ready",
        action="store_true",
        help=(
            "Require live-ready (deployment probe + role budgets + output limits + "
            "stop conditions), not just offline-ready"
        ),
    )
    admission_parser.add_argument("--models-json", dest="models_json", default="")
    admission_parser.add_argument(
        "--research-import",
        dest="research_import",
        default="",
        help="Verified research checkpoint required by --run-open-mode fork_authoring",
    )
    admission_parser.add_argument("--json", action="store_true")
    receipt_parser = subparsers.add_parser(
        "record-offline-receipt",
        help=(
            "Run the offline suite (no live_llm) and record a receipt bound to the "
            "current engine source digest."
        ),
    )
    receipt_parser.add_argument("--out", dest="receipt_out", required=True, help="Receipt JSON path")
    receipt_parser.add_argument(
        "--marker", default="not live_llm", help="pytest -m expression (default: not live_llm)"
    )
    receipt_parser.add_argument(
        "--timeout-seconds", dest="timeout_seconds", type=float, default=7200.0
    )
    receipt_parser.add_argument(
        "--pytest-target", dest="pytest_target", default="tests", help="Path passed to pytest"
    )
    run_parser = subparsers.add_parser("run", help="Run the full product path.")
    run_parser.add_argument("--repo", dest="repo", required=True, help="Target code repository")
    run_parser.add_argument("--author-intent", dest="author_intent", default="", help="Author intent YAML/JSON file")
    run_parser.add_argument("--claims", default="", help="User claims JSON file")
    run_parser.add_argument("--out", dest="out_root", required=True, help="Output directory")
    run_parser.add_argument("--max-research-turns", dest="max_research_turns", type=int, default=30)
    run_parser.add_argument(
        "--max-wall-clock-seconds",
        dest="max_wall_clock_seconds",
        type=float,
        default=0.0,
        help="Research wall-clock deadline; 0 disables the deadline (default).",
    )
    run_parser.add_argument("--llm-profile", dest="llm_profile", default="", help="Bash-style LLM env profile file")
    run_parser.add_argument("--no-live-llm", action="store_true", help="Force the deterministic research path; never call a model")
    run_parser.add_argument("--llm-provider", default="", help="LLM provider override")
    run_parser.add_argument("--llm-model", default="", help="LLM model override")
    run_parser.add_argument("--method-name", default="", help="Method name used by the Architect")
    run_parser.add_argument("--run-id", default="", help="Stable run identity")
    run_parser.add_argument(
        "--concept-cards",
        default="",
        help="Stage 2/3 MethodConceptCardSetV1 JSON; switches the plan and Writer to the concept lane",
    )
    run_parser.add_argument(
        "--compile-concept-cards",
        action="store_true",
        help="Deprecated no-op: live planning uses deterministic argument briefs instead",
    )
    run_parser.add_argument(
        "--compile-argument-briefs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Compile method_argument_briefs_v1 during planning (default: enabled)",
    )
    run_parser.add_argument(
        "--authoring-context-mode",
        choices=("legacy", "shadow_unified", "unified"),
        default=None,
        help="Authoring context lane; explicit CLI input wins over the environment",
    )
    run_parser.add_argument(
        "--research-stage-checkpoint",
        default="",
        help="Resume after repository research from a trusted stage checkpoint.",
    )
    run_parser.add_argument(
        "--authoring-phase-checkpoint",
        default="",
        help="Resume/reuse a validated Formalizer authoring phase checkpoint.",
    )
    run_parser.add_argument(
        "--run-open-mode",
        choices=("auto", "new", "resume", "fork_authoring"),
        default="auto",
        help=(
            "Run-directory admission: new refuses a non-empty root, resume requires a "
            "matching AuthoringExecutionIdentityV2 with unused content budget, "
            "fork_authoring imports verified research evidence only (default: auto)."
        ),
    )
    return parser


def method_agent_main(argv: list[str] | None = None) -> int:
    """Entry point for ``code2paper method-agent run ...``."""

    parser = _method_agent_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        from code2paper.agentic.authoring_doctor import run_authoring_doctor

        report = run_authoring_doctor(Path(args.out_root).expanduser().resolve())
        if bool(getattr(args, "json", False)):
            print(report.model_dump_json(indent=2))
        else:
            print(report.render())
        return 0
    if args.command == "quality-report":
        from code2paper.agentic.authoring_quality_report import (
            build_authoring_quality_report,
        )

        report = build_authoring_quality_report(Path(args.out_root).expanduser().resolve())
        if bool(getattr(args, "json", False)):
            print(report.model_dump_json(indent=2))
        else:
            print(report.render())
        return 0
    if args.command == "compare-quality":
        from code2paper.agentic.authoring_quality_comparison import (
            compare_authoring_quality_reports,
        )

        baseline_path = Path(args.baseline).expanduser()
        candidate_path = Path(args.candidate).expanduser()
        for label, path in (("baseline", baseline_path), ("candidate", candidate_path)):
            if not path.exists():
                print(f"[code2paper method-agent] error=input_not_found:--{label}:{path}")
                return 2
        comparison = compare_authoring_quality_reports(baseline_path, candidate_path)
        if bool(getattr(args, "json", False)):
            print(comparison.model_dump_json(indent=2))
        else:
            print(comparison.render())
        # 0 = 可比（差值有效）；3 = 不可比（原因已打印），便于脚本判定。
        return 0 if comparison.comparable else 3
    if args.command == "live-admission":
        return _live_admission_main(args)
    if args.command == "record-offline-receipt":
        return _record_offline_receipt_main(args)
    if args.command != "run":
        parser.error(f"unknown method-agent command: {args.command}")

    changed_env: dict[str, str | None] = {}
    out_root: Path | None = None
    result: MethodAgentRunResultV1 | None = None
    exit_code = 2
    process_started_at = 0.0
    process_stdout = Path()
    process_stderr = Path()
    process_pid = os.getpid()
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stdout_log = None
    stderr_log = None
    terminal_reason = ""
    try:
        if args.llm_profile:
            changed_env = _apply_llm_profile(args.llm_profile)

        repo_path = Path(args.repo).expanduser().resolve()
        if not repo_path.is_dir():
            print(f"[code2paper method-agent] error=repo_not_found:{repo_path}")
            return 2
        for label, value in (("--author-intent", args.author_intent), ("--claims", args.claims)):
            if value and not Path(value).expanduser().resolve().is_file():
                print(f"[code2paper method-agent] error=input_not_found:{label}:{value}")
                return 2

        llm_config = load_llm_config_from_env(
            provider=args.llm_provider or None,
            model=args.llm_model or None,
        )
        if args.no_live_llm:
            llm_config = LLMConfig.model_validate({
                **llm_config.model_dump(mode="json"),
                "provider": LLMProvider.NONE.value,
            })
        out_root = Path(args.out_root).expanduser().resolve()
        out_root.mkdir(parents=True, exist_ok=True)
        # WP1 §5.4：目录准入预检必须先于启动器写入任何进程产物（日志/监督清单）。
        # 正式准入会在锁内复查一次，防止预检与加锁之间出现竞争。
        run_open_mode = str(getattr(args, "run_open_mode", "auto") or "auto")
        preflight = preflight_run_open(
            out_root,
            run_open_mode,
            repo_path=repo_path,
            author_intent_path=(
                Path(args.author_intent).expanduser().resolve() if args.author_intent else None
            ),
            claims_path=(
                Path(args.claims).expanduser().resolve() if args.claims else None
            ),
            llm_config=llm_config,
        )
        if not preflight.allowed:
            print(
                "[code2paper method-agent] error="
                f"{preflight.code}:{preflight.detail or preflight.allowed_next_action}"
            )
            print(
                "[code2paper method-agent] next_action="
                f"{preflight.allowed_next_action}"
            )
            return 2
        attempt_id = str(
            os.environ.get("CODE2PAPER_METHOD_AGENT_ATTEMPT_ID", "") or ""
        ).strip()
        if not attempt_id:
            _mark_stale_method_process(out_root)
        process_stdout = (
            out_root / f"run_stdout.{attempt_id}.log"
            if attempt_id
            else out_root / "run_stdout.log"
        )
        process_stderr = (
            out_root / f"run_stderr.{attempt_id}.log"
            if attempt_id
            else out_root / "run_stderr.log"
        )
        stdout_log = process_stdout.open("w", encoding="utf-8")
        stderr_log = process_stderr.open("w", encoding="utf-8")
        sys.stdout = _TeeStream(original_stdout, stdout_log)
        sys.stderr = _TeeStream(original_stderr, stderr_log)
        process_started_at = time.time()
        _write_method_process_artifact(
            out_root,
            status="running",
            pid=process_pid,
            started_at=process_started_at,
            exit_code=None,
            stdout_path=process_stdout,
            stderr_path=process_stderr,
            run_id=args.run_id or "auto",
            attempt_id=attempt_id,
            supervisor_pid=(
                int(os.environ.get("CODE2PAPER_METHOD_AGENT_SUPERVISOR_PID", "0") or 0)
                or None
            ),
            worker_pid=process_pid,
        )

        print(f"[code2paper method-agent] run_id={args.run_id or 'auto'}")
        print(f"[code2paper method-agent] repo={repo_path}")
        print(f"[code2paper method-agent] out_root={out_root}")
        live_llm = not args.no_live_llm and llm_config.provider != LLMProvider.NONE
        print(
            "[code2paper method-agent] "
            f"live_llm={live_llm}"
        )
        result = run_autonomous_method_agent(
            repo_path=repo_path,
            author_intent_path=(
                Path(args.author_intent).expanduser().resolve()
                if args.author_intent
                else None
            ),
            claims_path=(
                Path(args.claims).expanduser().resolve() if args.claims else None
            ),
            out_root=out_root,
            llm_config=llm_config,
            max_research_turns=max(1, int(args.max_research_turns)),
            max_wall_clock_seconds=(
                float(args.max_wall_clock_seconds)
                if float(args.max_wall_clock_seconds) > 0
                else None
            ),
            method_name=args.method_name,
            run_id=args.run_id,
            research_stage_checkpoint=(
                Path(args.research_stage_checkpoint).expanduser().resolve()
                if args.research_stage_checkpoint else None
            ),
            authoring_phase_checkpoint=(
                Path(args.authoring_phase_checkpoint).expanduser().resolve()
                if args.authoring_phase_checkpoint else None
            ),
            concept_cards=_load_concept_cards(args.concept_cards),
            compile_concept_cards=bool(args.compile_concept_cards),
            compile_argument_briefs=bool(args.compile_argument_briefs),
            authoring_context_mode=args.authoring_context_mode,
            run_open_mode=str(getattr(args, "run_open_mode", "auto") or "auto"),
        )
        _print_method_agent_summary(result)
        _write_method_agent_exit_artifact(out_root, result)
        if live_llm:
            writer_summary = result.summary.get("writer") or {}
            exit_code = _live_method_agent_exit_code(result)
            if exit_code:
                terminal_reason = "candidate_incomplete:" + str(
                    writer_summary.get("blocked_reason")
                    or writer_summary.get("candidate_completion_status")
                    or "candidate_not_complete"
                )
                print(
                    "[code2paper method-agent] error=" + terminal_reason
                )
        else:
            # An explicitly offline invocation is a diagnostic/research
            # command.  Its successful execution does not claim a Candidate.
            exit_code = 0
    except MethodAgentSignal as exc:
        print(f"[code2paper method-agent] error={exc}")
        exit_code = 128 + int(exc.signum)
    except KeyboardInterrupt:
        print("[code2paper method-agent] error=keyboard_interrupt")
        exit_code = 130
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        print(f"[code2paper method-agent] error={exc}")
        exit_code = 2
    except BaseException as exc:  # noqa: BLE001 — durable failure boundary
        print(f"[code2paper method-agent] error={type(exc).__name__}:{exc}")
        exit_code = 2
    finally:
        if out_root is not None and process_started_at:
            _write_method_process_artifact(
                out_root,
                status="completed" if exit_code == 0 else "failed",
                pid=process_pid,
                started_at=process_started_at,
                exit_code=exit_code,
                stdout_path=process_stdout,
                stderr_path=process_stderr,
                run_id=(result.run_id if result is not None else args.run_id or "auto"),
                terminal_reason=(
                    terminal_reason
                    or (
                        result.research_termination_reason
                        if result is not None
                        else "cli_error"
                    )
                ),
                attempt_id=attempt_id,
                supervisor_pid=(
                    int(os.environ.get("CODE2PAPER_METHOD_AGENT_SUPERVISOR_PID", "0") or 0)
                    or None
                ),
                worker_pid=process_pid,
            )
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if stdout_log is not None:
            stdout_log.close()
        if stderr_log is not None:
            stderr_log.close()
        _restore_env(changed_env)
    return exit_code


def supervised_method_agent_main(argv: list[str] | None = None) -> int:
    """Run the Method Agent as a supervised worker process.

    The worker owns normal signal/exception closure.  This parent remains
    outside the worker so a SIGKILL or abnormal worker exit is observable and
    can immediately persist a partial summary and a uniquely named terminal
    event.
    """

    raw_argv = list(argv) if argv is not None else list(sys.argv[1:])
    parser = _method_agent_parser()
    args = parser.parse_args(raw_argv)
    if args.command != "run":
        # 只读/离线诊断命令不能被包进 worker 监督进程：监督器会先创建 attempt
        # 目录、进程清单与日志——对 `doctor` / `live-admission` 是纯副作用，
        # 而且会让"预检只读"的承诺失效。
        if args.command in _READ_ONLY_METHOD_AGENT_COMMANDS:
            return method_agent_main(raw_argv)
        parser.error(f"unknown method-agent command: {args.command}")
    out_root = Path(args.out_root).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    _recover_stale_method_attempts(out_root)

    attempt_id = (
        time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        + "-"
        + uuid.uuid4().hex[:12]
    )
    attempt_root = out_root / "method_agent_attempts"
    attempt_root.mkdir(parents=True, exist_ok=True)
    attempt_path = attempt_root / f"{attempt_id}.json"
    stdout_path = out_root / f"run_stdout.{attempt_id}.log"
    stderr_path = out_root / f"run_stderr.{attempt_id}.log"
    run_id = str(args.run_id or "auto")
    started_at = time.time()
    # Create the immutable attempt log names before spawning the worker.  A
    # worker can disappear before importing the CLI or opening its streams;
    # the parent must still leave a concrete, attempt-scoped log target.
    stdout_path.touch(exist_ok=True)
    stderr_path.touch(exist_ok=True)
    attempt_payload = {
        "schema_version": "1.0",
        "attempt_id": attempt_id,
        "run_id": run_id,
        "status": "running",
        "supervisor_pid": os.getpid(),
        "worker_pid": None,
        "started_at_unix": started_at,
        "ended_at_unix": None,
        "exit_code": None,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "argv": raw_argv,
    }
    _write_json_atomically(attempt_path, attempt_payload)
    _write_json_atomically(
        out_root / "method_agent_process.json",
        {
            **attempt_payload,
            "process_role": "supervisor",
            "attempt_path": str(attempt_path),
        },
    )

    child: subprocess.Popen[bytes] | None = None
    stop_signal: int | None = None
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    old_handlers: dict[int, Any] = {}
    worker_returncode = 2

    def _forward(pipe: Any, target: Any) -> None:
        try:
            while True:
                chunk = pipe.readline()
                if not chunk:
                    break
                target.write(chunk.decode("utf-8", errors="replace"))
                target.flush()
        finally:
            try:
                pipe.close()
            except OSError:
                pass

    def _on_parent_signal(signum: int, _frame: Any) -> None:
        nonlocal stop_signal
        stop_signal = int(signum)
        if child is not None and child.poll() is None:
            try:
                child.terminate()
            except OSError:
                pass

    try:
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
                old_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, _on_parent_signal)
        child_env = os.environ.copy()
        child_env["CODE2PAPER_METHOD_AGENT_WORKER"] = "1"
        child_env["CODE2PAPER_METHOD_AGENT_ATTEMPT_ID"] = attempt_id
        child_env["CODE2PAPER_METHOD_AGENT_SUPERVISOR_PID"] = str(os.getpid())
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "code2paper.cli.main",
                "method-agent",
                *raw_argv,
            ],
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        attempt_payload["worker_pid"] = child.pid
        _write_json_atomically(attempt_path, attempt_payload)
        _write_json_atomically(
            out_root / "method_agent_process.json",
            {
                **attempt_payload,
                "process_role": "supervisor",
                "attempt_path": str(attempt_path),
            },
        )
        stdout_thread = threading.Thread(
            target=_forward,
            args=(child.stdout, original_stdout),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_forward,
            args=(child.stderr, original_stderr),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        worker_returncode = child.wait()
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
    except KeyboardInterrupt:
        # Keep Ctrl-C inside the same durable finalizer path as an installed
        # SIGINT handler.  This also covers embedders/tests that raise
        # KeyboardInterrupt directly from ``wait``.
        stop_signal = int(getattr(signal, "SIGINT", 2))
        if child is not None and child.poll() is None:
            try:
                child.terminate()
            except OSError:
                pass
        if child is None:
            worker_returncode = 128 + stop_signal
        else:
            try:
                worker_returncode = child.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt):
                polled = child.poll()
                worker_returncode = (
                    int(polled)
                    if polled is not None
                    else -int(getattr(signal, "SIGTERM", 15))
                )
    except (OSError, ValueError) as exc:
        worker_returncode = 2
        attempt_payload.update({
            "status": "failed",
            "ended_at_unix": time.time(),
            "exit_code": worker_returncode,
            "terminal_reason": f"supervisor_error:{type(exc).__name__}",
            "error": str(exc)[:500],
        })
        _write_json_atomically(attempt_path, attempt_payload)
        _write_json_atomically(
            out_root / "method_agent_process.json",
            {
                **attempt_payload,
                "process_role": "supervisor",
                "attempt_path": str(attempt_path),
            },
        )
        return worker_returncode
    finally:
        if child is not None and child.poll() is None:
            try:
                child.kill()
                child.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)

    externally_terminated = bool(stop_signal) or worker_returncode < 0
    worker_artifacts = _worker_attempt_artifact_state(out_root, attempt_id)
    if externally_terminated or worker_returncode != 0:
        external_code = (
            -int(stop_signal)
            if stop_signal is not None
            else int(worker_returncode)
        )
        if worker_artifacts["partial_valid"] and worker_artifacts["terminal_valid"]:
            partial_paths = {}
        else:
            partial_paths = _persist_external_method_termination(
                out_root=out_root,
                run_id=run_id,
                attempt_id=attempt_id,
                returncode=external_code,
            )
        partial_paths["supervisor_observation"] = _persist_supervisor_observation(
            out_root=out_root,
            run_id=run_id,
            attempt_id=attempt_id,
            worker_returncode=worker_returncode,
            stop_signal=stop_signal,
            worker_artifacts=worker_artifacts,
            fallback_artifacts=partial_paths,
        )
        terminal_reason = (
            f"parent_signal_{stop_signal}"
            if stop_signal is not None
            else (
                f"worker_signal_{-worker_returncode}"
                if worker_returncode < 0
                else f"worker_exit_{worker_returncode}"
            )
        )
    else:
        partial_paths = {}
        terminal_reason = "completed"
    final_exit_code = (
        128 + int(stop_signal)
        if stop_signal is not None
        else 128 + (-worker_returncode)
        if worker_returncode < 0
        else worker_returncode
    )
    attempt_payload.update({
        "status": (
            "external_termination"
            if externally_terminated
            else "completed"
            if worker_returncode == 0
            else "failed"
        ),
        "ended_at_unix": time.time(),
        "exit_code": final_exit_code,
        "worker_returncode": worker_returncode,
        "terminal_reason": terminal_reason,
        "parent_stop_signal": stop_signal,
        "worker_terminal_reason": str(worker_artifacts.get("terminal_reason") or ""),
        "worker_exit_type": str(worker_artifacts.get("exit_type") or ""),
        "primary_terminal_source": _worker_primary_terminal_source(worker_artifacts),
        "partial_artifacts": partial_paths,
    })
    _write_json_atomically(attempt_path, attempt_payload)
    _write_json_atomically(
        out_root / "method_agent_process.json",
        {
            **attempt_payload,
            "process_role": "supervisor",
            "attempt_path": str(attempt_path),
        },
    )
    return final_exit_code


def _live_method_agent_exit_code(result: MethodAgentRunResultV1) -> int:
    """Return success only for a persisted, complete live Candidate."""

    writer = result.summary.get("writer") or {}
    return 0 if (
        bool(writer.get("candidate_available"))
        and bool(writer.get("candidate_complete"))
    ) else 2


def _print_method_agent_summary(result: MethodAgentRunResultV1) -> None:
    summary = result.summary
    writer = summary.get("writer", {})
    evidence = summary.get("evidence", {})
    plan = summary.get("plan", {})
    callbacks = summary.get("callbacks", {})
    review = summary.get("review", {})
    print("[code2paper method-agent] -----------------------------")
    print(f"[code2paper method-agent] run_id={result.run_id}")
    print(
        "[code2paper method-agent] "
        f"candidate written: {'yes' if writer.get('candidate_written') else 'no'}"
    )
    print(
        "[code2paper method-agent] "
        f"verified written: {'yes' if writer.get('verified_written') else 'no'}"
    )
    print(f"[code2paper method-agent] verified facts: {evidence.get('verified_facts', 0)}")
    print(f"[code2paper method-agent] supported claims: {evidence.get('supported_claims', 0)}")
    print(f"[code2paper method-agent] review items: {review.get('review_items', 0)}")
    print(
        f"[code2paper method-agent] callbacks fulfilled: "
        f"{callbacks.get('callbacks_fulfilled', 0)}"
    )
    print(
        f"[code2paper method-agent] external queues: "
        f"{callbacks.get('external_queue_items', 0)}"
    )
    print(
        f"[code2paper method-agent] gaps: {evidence.get('typed_gaps', 0)} "
        f"(explicit={evidence.get('explicit_gaps', 0)}, "
        f"unresolved={evidence.get('unresolved_obligations', 0)})"
    )
    print(
        "[code2paper method-agent] "
        f"unsupported positives: candidate={summary.get('unsupported_positive_claims_in_candidate', 0)} "
        f"verified={summary.get('unsupported_positive_claims_in_verified', 0)}"
    )
    print(
        "[code2paper method-agent] "
        f"plan readiness: {plan.get('readiness', '')}"
    )
    print(
        "[code2paper method-agent] "
        f"research: {summary.get('research', {}).get('status', '')} "
        f"({summary.get('research', {}).get('termination_reason', '')}, "
        f"{summary.get('research', {}).get('turns_executed', 0)} turns)"
    )
    if writer.get("blocked_reason"):
        print(f"[code2paper method-agent] writer blocked reason: {writer.get('blocked_reason')}")
    print("[code2paper method-agent] -----------------------------")
    print(f"[code2paper method-agent] summary={result.artifact_paths.get('run_summary', '')}")


def _write_method_agent_exit_artifact(out_root: Path, result: MethodAgentRunResultV1) -> None:
    try:
        target = Path(out_root) / "method_agent_result.json"
        target.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


if __name__ == "__main__":
    raise SystemExit(main())
