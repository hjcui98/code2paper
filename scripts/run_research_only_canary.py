#!/usr/bin/env python3
"""Stage 1 canary: research-only RAP run against the LLM Research Manager.

Purpose (diagnosis handoff ``autonomous_method_agent_pause_diagnosis_and_handoff_20260813.md``
Stage 1): prove that the Research Manager truly reads recent observations
(source excerpts / discovered symbols) and autonomously decides the next
query instead of repeating reads or falling back to the deterministic
script.  This script runs ONLY the V3 research subgraph (no Writer/Editor):

- builds the product research runtime with the LLM-backed
  ``GemmaSupervisorBackend`` (no live LLM => abort, not deterministic),
- runs the research phase with a bounded turn budget,
- emits a JSON decision-trace report with, per turn: the LLM proposal,
  policy merge outcome (accepted / rejected + repair), the executed tool
  calls, and the observation notebook (semantic summary + code excerpt).

Exit criteria checked in the report (not enforced here so partial evidence
is preserved):

1. The Manager reads ``GaussianModel.get_prune_input_f15`` and then chooses
   a follow-up that is justified by the code content (trace normalizer /
   inputs / caller), not a repeated read of the same symbol.
2. After a policy rejection, the same exact tool call is not proposed again.
3. Termination is ``all_obligations_terminal`` / ``ready_to_author`` /
   partial-with-explicit-gap, not ``max_turns_reached`` or fallback
   exhaustion.

Usage::

    python scripts/run_research_only_canary.py \\
        --repo .tmp/c2p-stage1-canary/rap-fixture \\
        --intent .tmp/c2p-stage1-canary/rap_intent.yaml \\
        --out /tmp/... (use a persistent dir under the repo worktree) \\
        --max-turns 12 \\
        --profile tests/live/profiles/qwen36_vllm_budgeted.example.env \\
        --run-id stage1-research-only-rap
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2paper.agentic.autonomous_method_agent import (  # noqa: E402
    UserClaimsInputV1,
    build_product_research_runtime,
    run_product_research_phase,
)
from code2paper.llm.providers import load_llm_config_from_env  # noqa: E402


def _apply_profile(path: str) -> None:
    profile_path = Path(path)
    if not profile_path.is_file():
        raise FileNotFoundError(f"llm profile not found: {profile_path}")
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
        os.environ[key] = value.strip("'").strip('"')


def _observation_payload(obs) -> dict:
    return {
        "observation_id": getattr(obs, "observation_id", ""),
        "tool_name": getattr(obs, "tool_name", ""),
        "status": getattr(obs, "status", ""),
        "result_refs": list(getattr(obs, "result_refs", ()))[:8],
        "exact_span_ids": list(getattr(obs, "exact_span_ids", ()))[:8],
        "notebook_summary": getattr(getattr(obs, "notebook", None), "summary", ""),
        "code_excerpt": getattr(getattr(obs, "notebook", None), "code_excerpt", ""),
        "discovered_symbols": list(
            getattr(getattr(obs, "notebook", None), "discovered_symbols", ())
        )[:12],
        "discovered_relations": list(
            getattr(getattr(obs, "notebook", None), "discovered_relations", ())
        )[:12],
    }


def _decision_payload(decision) -> dict:
    return {
        "turn_index": getattr(decision, "turn_index", 0),
        "action": getattr(decision, "action", ""),
        "produced_by": getattr(decision, "produced_by", ""),
        "obligation_id": getattr(decision, "obligation_id", ""),
        "goal": getattr(decision, "goal", ""),
        "rationale": getattr(decision, "rationale", ""),
        "expected_information_gain": getattr(
            decision, "expected_information_gain", ""
        ),
        "tool_calls": [
            {
                "tool_name": call.tool_name,
                "arguments": call.arguments,
                "path_scope": list(call.path_scope),
                "top_k": call.top_k,
                "goal": call.goal,
            }
            for call in getattr(decision, "selected_tool_calls", ())
        ],
    }


def _install_raw_response_capture(raw_log: list[dict]) -> None:
    """Monkeypatch LLMClient.complete to record raw responses for diagnosis.

    The raw text is needed to diagnose transport/parse failures (e.g. the
    double-brace ``{{...}}`` provider drift) that the recovery layer could
    not repair.  This is a diagnostic hook inside the canary script only;
    production code is not modified.
    """

    from code2paper.llm import client as llm_client_module

    original_complete = llm_client_module.LLMClient.complete

    def _wrapped_complete(self, request):
        response = original_complete(self, request)
        raw_log.append(
            {
                "prompt_template_id": getattr(request, "prompt_template_id", ""),
                "blocked_reason": getattr(response, "blocked_reason", ""),
                "response_mode": getattr(response, "response_mode", ""),
                "finish_reason": getattr(response, "finish_reason", ""),
                "text": (getattr(response, "text", "") or "")[-6000:],
            }
        )
        return response

    llm_client_module.LLMClient.complete = _wrapped_complete


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--profile", default="")
    parser.add_argument("--run-id", default="stage1-research-only-rap")
    parser.add_argument(
        "--allow-deterministic",
        action="store_true",
        help="Allow the run to proceed without a live LLM (for plumbing tests).",
    )
    args = parser.parse_args()

    if args.profile:
        _apply_profile(args.profile)

    out_root = Path(args.out).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    llm_config = load_llm_config_from_env()
    from code2paper.llm.providers import has_provider_api_key

    if not has_provider_api_key(llm_config) and not args.allow_deterministic:
        print(
            json.dumps(
                {"status": "aborted", "reason": "no_live_llm_configured"},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    raw_log: list[dict] = []
    _install_raw_response_capture(raw_log)

    runtime = build_product_research_runtime(
        repo_path=Path(args.repo).expanduser().resolve(),
        author_intent_path=Path(args.intent).expanduser().resolve(),
        claims=UserClaimsInputV1(claims=[]),
        run_id=args.run_id,
        llm_config=llm_config,
        artifact_root=out_root / "artifacts" / "research_tool_data",
    )

    result = run_product_research_phase(runtime, max_turns=int(args.max_turns))

    # --- Report -----------------------------------------------------------------
    report: dict = {
        "run_id": args.run_id,
        "repo": str(Path(args.repo).expanduser().resolve()),
        "intent": str(Path(args.intent).expanduser().resolve()),
        "max_turns": int(args.max_turns),
        "turns_executed": result.turns_executed,
        "terminated": result.terminated,
        "termination_reason": result.termination_reason,
        "final_status": str(result.final_state.get("status") or "incomplete"),
        "obligations": [
            {
                "obligation_id": item.obligation_id,
                "priority": item.priority,
                "status": item.status,
                "author_text": item.author_text[:200],
                "missing_information": list(item.missing_information)[:10],
                "candidate_symbol_ids": list(item.candidate_symbol_ids)[:10],
            }
            for item in runtime.agenda.items
        ],
    }

    # Manager backend honesty.
    backend = runtime.supervisor_backend
    llm_decisions = max(
        int(getattr(backend, "llm_decision_count", 0)),
        sum(
            1
            for d in result.decision_trace
            if d.produced_by == "llm_proposal"
        ),
    )
    deterministic_decisions = sum(
        1
        for d in result.decision_trace
        if d.produced_by == "deterministic_fallback"
    )
    degraded_events = list(getattr(backend, "degraded_events", ()))
    policy_fallbacks = sum(
        1 for merge in result.loop_state.policy_merge_trace if merge.fallback_used
    )
    repairs = len(result.loop_state.policy_merge_trace) - policy_fallbacks
    report["manager"] = {
        "llm_decisions": llm_decisions,
        "deterministic_fallback_decisions": deterministic_decisions,
        "degraded_events": degraded_events,
        "policy_fallback_merges": policy_fallbacks,
        "representation_repairs": list(
            getattr(backend, "representation_repairs", ())
        )[:20],
        "autonomous": (
            llm_decisions > 0
            and deterministic_decisions == 0
            and not degraded_events
            and policy_fallbacks == 0
        ),
    }

    # Decision trace with per-decision policy merge outcome.
    by_turn: dict[int, dict] = {}
    for merge in result.loop_state.policy_merge_trace:
        decision = merge.decision
        if decision is None:
            continue
        entry = by_turn.setdefault(decision.turn_index, {})
        entry.setdefault("merges", []).append(
            {
                "accepted": merge.accepted,
                "fallback_used": merge.fallback_used,
                "rejections": [
                    {
                        "rule": r.rule,
                        "reason": r.reason,
                        "tool_call_id": r.tool_call_id,
                    }
                    for r in merge.rejections
                ],
            }
        )
    trace: list[dict] = []
    for decision in result.decision_trace:
        payload = _decision_payload(decision)
        payload["merges"] = by_turn.get(decision.turn_index, {}).get("merges", [])
        trace.append(payload)
    report["decisions"] = trace

    report["observations"] = [_observation_payload(o) for o in result.loop_state.recent_observations]

    # All observations across the run (the loop keeps only the recent window).
    all_observations: list[dict] = []
    for obs in result.loop_state.recent_observations:
        payload = _observation_payload(obs)
        if payload not in all_observations:
            all_observations.append(payload)
    report["all_observations"] = all_observations

    report["evidence_critic_routes"] = list(result.evidence_critic_routes)

    # Compiled evidence summary.
    compiled: list[dict] = []
    for entry in result.loop_state.compiled_evidence.values():
        compiled.append(
            {
                "obligation_id": entry.obligation_id,
                "packets": len(entry.packet_set.packets) if entry.packet_set else 0,
                "facts": len(entry.fact_set.facts) if entry.fact_set else 0,
                "claims": len(entry.claim_set.claims) if entry.claim_set else 0,
                "gaps": len(entry.claim_set.explicit_code_gaps) if entry.claim_set else 0,
            }
        )
    report["compiled_evidence"] = compiled

    # --- Stage 1 acceptance probes ----------------------------------------------
    probes: dict = {}
    read_symbol_calls = [
        d
        for d in trace
        for c in d["tool_calls"]
        if c["tool_name"] == "read_symbol"
    ]
    probes["read_symbol_calls"] = [
        {
            "turn": d["turn_index"],
            "produced_by": d["produced_by"],
            "path": next(
                (c["arguments"].get("path") for c in d["tool_calls"] if c["tool_name"] == "read_symbol"),
                "",
            ),
            "symbol": next(
                (c["arguments"].get("symbol") for c in d["tool_calls"] if c["tool_name"] == "read_symbol"),
                "",
            ),
        }
        for d in trace
        if any(c["tool_name"] == "read_symbol" for c in d["tool_calls"])
    ]
    # Duplicate exact read detection across LLM proposals.
    seen_reads: set[tuple[str, str]] = set()
    duplicate_llm_reads: list[dict] = []
    for d in trace:
        for c in d["tool_calls"]:
            if c["tool_name"] == "read_symbol" and d["produced_by"] == "llm_proposal":
                key = (c["arguments"].get("path", ""), c["arguments"].get("symbol", ""))
                if key in seen_reads:
                    duplicate_llm_reads.append({"turn": d["turn_index"], "path": key[0], "symbol": key[1]})
                seen_reads.add(key)
    probes["duplicate_llm_read_symbol_calls"] = duplicate_llm_reads
    probes["termination_reason"] = result.termination_reason
    probes["final_status"] = report["final_status"]
    probes["llm_decisions"] = llm_decisions
    probes["deterministic_fallback_decisions"] = deterministic_decisions
    probes["policy_fallback_merges"] = policy_fallbacks
    probes["degraded_events"] = degraded_events
    probes["manager_autonomous"] = report["manager"]["autonomous"]
    report["stage1_probes"] = probes

    # Raw LLM responses (diagnostic; provider drift such as ``{{...}}``
    # recovery failures can only be understood from the original text).
    report["raw_llm_responses"] = raw_log

    report_path = out_root / "research_only_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(
        {
            "status": "done",
            "turns_executed": result.turns_executed,
            "termination_reason": result.termination_reason,
            "final_status": report["final_status"],
            "manager": report["manager"],
            "stage1_probes": probes,
            "report": str(report_path),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
