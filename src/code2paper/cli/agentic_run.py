"""LangGraph-orchestrated Code2Paper runner CLI."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from code2paper.agentic.completion_report import AgenticRunCompletionReport, load_run_completion_report
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.runner import AgenticRunResult, run_agentic_code2paper
from code2paper.agentic.checkpointing import build_memory_checkpointer, open_sqlite_checkpointer
from code2paper.core.output_paths import resolve_out_root, resolve_project_id
from code2paper.core.schemas import LLMProvider


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
        core_top_k=int(args.core_top_k),
        skip_draft_bootstrap=bool(args.skip_draft_bootstrap),
        max_retrieval_rounds=max(0, int(args.max_retrieval_rounds)),
        max_evidence_revision_rounds=max(0, int(args.max_evidence_revision_rounds)),
        max_authoring_revision_rounds=max(0, int(args.max_authoring_revision_rounds)),
        max_figure_revision_rounds=max(0, int(args.max_figure_revision_rounds)),
        max_semantic_verifier_calls=max(0, int(args.max_semantic_verifier_calls)),
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


if __name__ == "__main__":
    raise SystemExit(main())
