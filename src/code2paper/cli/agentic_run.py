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
import uuid
from pathlib import Path
from typing import Any

from code2paper.agentic.autonomous_method_agent import (
    MethodAgentRunResultV1,
    run_autonomous_method_agent,
)
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
    run_parser = subparsers.add_parser("run", help="Run the full product path.")
    run_parser.add_argument("--repo", dest="repo", required=True, help="Target code repository")
    run_parser.add_argument("--author-intent", dest="author_intent", default="", help="Author intent YAML/JSON file")
    run_parser.add_argument("--claims", default="", help="User claims JSON file")
    run_parser.add_argument("--out", dest="out_root", required=True, help="Output directory")
    run_parser.add_argument("--max-research-turns", dest="max_research_turns", type=int, default=30)
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
        "--research-stage-checkpoint",
        default="",
        help="Resume after repository research from a trusted stage checkpoint.",
    )
    return parser


def method_agent_main(argv: list[str] | None = None) -> int:
    """Entry point for ``code2paper method-agent run ...``."""

    parser = _method_agent_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.error(f"unknown method-agent command: {args.command}")

    changed_env: dict[str, str | None] = {}
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

        print(f"[code2paper method-agent] run_id={args.run_id or 'auto'}")
        print(f"[code2paper method-agent] repo={repo_path}")
        print(f"[code2paper method-agent] out_root={out_root}")
        print(
            "[code2paper method-agent] "
            f"live_llm={not args.no_live_llm and llm_config.provider != LLMProvider.NONE}"
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
            method_name=args.method_name,
            run_id=args.run_id,
            research_stage_checkpoint=(
                Path(args.research_stage_checkpoint).expanduser().resolve()
                if args.research_stage_checkpoint else None
            ),
            concept_cards=_load_concept_cards(args.concept_cards),
            compile_concept_cards=bool(args.compile_concept_cards),
            compile_argument_briefs=bool(args.compile_argument_briefs),
        )
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as exc:
        print(f"[code2paper method-agent] error={exc}")
        return 2
    finally:
        _restore_env(changed_env)

    _print_method_agent_summary(result)
    _write_method_agent_exit_artifact(out_root, result)
    return 0


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
