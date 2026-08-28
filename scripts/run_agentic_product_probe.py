#!/usr/bin/env python3
"""Run the agentic Method-Agent product path and summarize its artifacts.

This is the maintained diagnostic entry point for the Stage 6 product
probe (plan section 15).  It replaces the one-off shell snippets that
failed with ``TypeError: unsupported operand type(s) for /: 'str' and
'str'``: every output-root value is converted to ``Path`` once at the
command boundary, and product execution is separated from read-only
artifact summarization.

Exit contract:

- product step failed        -> exit 2 (product exit code, if captured)
- summarizer failed          -> exit 3
- both succeeded             -> exit 0
- ``--summarize-only``       -> only the read-only summarizer runs

The summarizer never modifies candidate/verified/validation/callback
artifacts; it writes exactly one new file (``probe_result.json``) next to
the product root and reports missing files deterministically.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def summarize_run(out_root: Path) -> dict:
    """Read-only product summary for one run root.

    Returns a JSON-serializable dict with deterministic keys.  Missing
    files are reported as ``None`` values (never raised, never silently
    treated as success).  This function must not write to any artifact
    path under ``out_root``.
    """

    out_root = Path(out_root)
    research_product = out_root / "artifacts" / "research_product"
    run_summary_path = research_product / "run_summary.json"
    run_summary: dict | None = None
    if run_summary_path.is_file():
        try:
            run_summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            run_summary = None
    research = {}
    evidence = {}
    plan = {}
    if isinstance(run_summary, dict):
        research = run_summary.get("research") or {}
        evidence = run_summary.get("evidence") or {}
        plan = run_summary.get("plan") or {}
    candidate_path = out_root / "artifacts" / "06_authoring" / "publication_candidate_method.md"
    verified_path = out_root / "artifacts" / "06_authoring" / "repository_verified_method.md"
    validation_path = out_root / "artifacts" / "07_validation" / "agentic_text_evidence_validation.json"
    return {
        "run_id": str((run_summary or {}).get("run_id") or ""),
        "research": {
            "status": research.get("status"),
            "termination_reason": research.get("termination_reason"),
            "turns_executed": research.get("turns_executed"),
            "autonomous": research.get("autonomous"),
            "llm_decisions": research.get("llm_decisions"),
            "deterministic_fallback_decisions": research.get("deterministic_fallback_decisions"),
            "policy_fallback_decisions": research.get("policy_fallback_decisions"),
            "degraded_reasons": research.get("degraded_reasons"),
        },
        "evidence": {
            "evidence_packets": evidence.get("evidence_packets"),
            "verified_facts": evidence.get("verified_facts"),
            "supported_claims": evidence.get("supported_claims"),
            "typed_gaps": evidence.get("typed_gaps"),
            "unresolved_obligations": evidence.get("unresolved_obligations"),
            "synthetic_support_used": evidence.get("synthetic_support_used"),
        },
        "plan": {
            "plan_built": plan.get("plan_built"),
            "readiness": plan.get("readiness"),
        },
        "artifacts": {
            "run_summary": _file_or_none(run_summary_path),
            "candidate_method": _file_or_none(candidate_path),
            "verified_method": _file_or_none(verified_path),
            "text_evidence_validation": _file_or_none(validation_path),
        },
        "missing_files": sorted(
            str(path)
            for path in (run_summary_path, candidate_path, verified_path, validation_path)
            if not path.is_file()
        ),
    }


def _file_or_none(path: Path) -> str | None:
    return str(path) if path.is_file() else None


def write_probe_result(out_root: Path, payload: dict) -> Path:
    """Write the read-only probe summary next to the run root.

    This is the ONLY write the summarizer performs.  It never touches
    candidate/verified/validation/callback artifacts.
    """

    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    probe_path = out_root / "probe_result.json"
    probe_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return probe_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="Repository path (product step)")
    parser.add_argument("--author-intent", help="Author intent YAML (product step)")
    parser.add_argument("--out", required=True, help="Fresh output root")
    parser.add_argument("--method", default="", help="Method name")
    parser.add_argument("--run-id", default="", help="Stable run id")
    parser.add_argument("--max-research-turns", type=int, default=25)
    parser.add_argument("--max-callback-rounds", type=int, default=2)
    parser.add_argument("--max-callback-tool-turns-per-request", type=int, default=6)
    parser.add_argument(
        "--compile-concept-cards",
        action="store_true",
        help="Live-compile concept cards from research claims",
    )
    parser.add_argument(
        "--profile",
        default="tests/live/profiles/qwen36_vllm_budgeted.example.env",
        help="Path to an env profile with base URL and model settings",
    )
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="Only summarize an existing run root; never run the product",
    )
    arguments = parser.parse_args(argv)

    # Path boundary: every output-root value becomes a Path exactly once.
    out_root = Path(arguments.out).expanduser().resolve()

    # Load profile into environment if provided.
    profile = Path(arguments.profile)
    if profile.is_file():
        for line in profile.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            line = line.removeprefix("export ").strip()
            key, _, value = line.partition("=")
            key = key.strip(); value = value.strip().strip("'").strip('"')
            if key and not key.startswith("_") and value and "$" not in value:
                __import__("os").environ[key] = value

    product_exit: int | None = None
    if not arguments.summarize_only:
        if not arguments.repo or not arguments.author_intent:
            parser.error("--repo and --author-intent are required for the product step")
        from code2paper.agentic.autonomous_method_agent import run_autonomous_method_agent
        from code2paper.llm.providers import load_llm_config_from_env

        llm_config = load_llm_config_from_env()
        try:
            result = run_autonomous_method_agent(
                repo_path=Path(arguments.repo).expanduser().resolve(),
                author_intent_path=Path(arguments.author_intent).expanduser().resolve(),
                out_root=out_root,
                llm_config=llm_config,
                max_research_turns=max(1, int(arguments.max_research_turns)),
                max_callback_rounds=max(0, int(arguments.max_callback_rounds)),
                max_callback_tool_turns_per_request=max(
                    1, int(arguments.max_callback_tool_turns_per_request)
                ),
                method_name=arguments.method or None,
                run_id=arguments.run_id or None,
                compile_concept_cards=bool(arguments.compile_concept_cards),
            )
        except Exception as exc:  # pragma: no cover - defensive product boundary
            print(f"[probe] product step failed: {exc.__class__.__name__}: {exc}")
            return 2
        payload = {
            "run_id": result.run_id,
            "research_status": result.research_status,
            "research_termination_reason": result.research_termination_reason,
            "research_turns": result.research_turns,
            "plan_built": result.plan_built,
            "plan_readiness": result.plan_readiness,
            "writer_status": result.writer_status,
            "writer_blocked_reason": result.writer_blocked_reason,
            "summary": result.summary,
        }
        probe_path = write_probe_result(out_root, payload)
        print(f"[probe] probe_result written: {probe_path}")
        product_exit = 0

    try:
        summary = summarize_run(out_root)
    except Exception as exc:  # pragma: no cover - defensive summarizer boundary
        print(f"[probe] summarizer failed: {exc.__class__.__name__}: {exc}")
        return 3
    print("[probe] summary: " + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if product_exit is not None and product_exit != 0:
        return product_exit
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
