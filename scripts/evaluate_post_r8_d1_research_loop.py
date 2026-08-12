#!/usr/bin/env python3
"""Accept the production V3 search/read -> generic compile route.

Unlike the direct tool smoke test, this command executes the LangGraph
research phase.  It therefore catches supervisor ordering regressions where a
semantic word such as ``config`` prevents an exact source read from reaching
the generic packet/fact/claim data plane.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2paper.agentic.evidence_compiler_v3 import (  # noqa: E402
    GENERIC_RESEARCH_PRODUCER_VERSION,
)
from code2paper.agentic.v3_runtime import (  # noqa: E402
    build_v3_research_runtime,
    run_v3_research_phase,
)
from code2paper.schemas import LLMConfig, LLMProvider  # noqa: E402


_CHAIN_DIRS = (
    "packet_proposals",
    "packet_validation_reports",
    "validated_packets",
    "fact_sets",
    "fact_validation_reports",
    "claim_proposal_sets",
    "claim_authorization_reports",
    "authorized_claim_sets",
)


def _json_files(root: Path, directory: str) -> list[Path]:
    path = root / "research_tool_artifacts" / directory
    return sorted(path.glob("*.json")) if path.is_dir() else []


def _payloads(root: Path, directory: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in _json_files(root, directory):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            payloads.append(value)
    return payloads


def evaluate(
    *,
    project_root: Path,
    intent_path: Path,
    artifact_root: Path,
    run_id: str,
    max_turns: int,
) -> dict[str, Any]:
    runtime = build_v3_research_runtime(
        project_root=project_root,
        intent_path=intent_path,
        run_id=run_id,
        llm_config=LLMConfig(
            provider=LLMProvider.NONE,
            model="deterministic-supervisor",
            cache=False,
        ),
    ).model_copy(update={"artifact_root": artifact_root})
    result = run_v3_research_phase(runtime, max_turns=max_turns)
    compiled = list(result.loop_state.compiled_evidence.values())
    supported = [
        item for item in runtime.agenda.items if item.status == "supported"
    ]
    search_actions = [
        decision
        for decision in result.decision_trace
        if any(call.tool_name == "search_symbols" for call in decision.selected_tool_calls)
    ]
    read_actions = [
        decision
        for decision in result.decision_trace
        if any(call.tool_name == "read_symbol" for call in decision.selected_tool_calls)
    ]
    packet_payloads = _payloads(artifact_root, "validated_packets")
    fact_payloads = _payloads(artifact_root, "fact_sets")
    claim_payloads = _payloads(artifact_root, "authorized_claim_sets")
    all_generic = all(
        payload.get("producer_version") == GENERIC_RESEARCH_PRODUCER_VERSION
        for payload in (*fact_payloads, *claim_payloads)
    )
    claims_nonempty = all(payload.get("claims") for payload in claim_payloads)
    packet_digests = {
        payload.get("source_digest")
        for payload in packet_payloads
        if payload.get("source_digest")
    }
    fact_digests = {
        fact.get("content_digest")
        for fact in fact_payloads
        if fact.get("content_digest")
    }
    fact_packet_replay = bool(
        fact_payloads
        and all(
            payload.get("evidence_packet_digest") in packet_digests
            for payload in fact_payloads
        )
    )
    claims_replay = bool(
        claim_payloads
        and all(
            payload.get("evidence_packet_digest") in packet_digests
            and payload.get("code_fact_digest") in fact_digests
            for payload in claim_payloads
        )
    )
    compiled_count = len(compiled)
    chain_counts = {
        directory: len(_json_files(artifact_root, directory))
        for directory in _CHAIN_DIRS
    }
    invariants = {
        "search_read_reached_from_supervisor": bool(search_actions and read_actions),
        "behavior_graph_has_exact_operations": bool(result.loop_state.behavior_graph.nodes),
        "compile_route_reached": "compile_candidate" in result.evidence_critic_routes,
        "all_obligations_terminal": result.termination_reason == "all_obligations_terminal",
        "compiled_supported_obligations": bool(compiled_count and supported),
        "generic_chain_artifacts_persisted": all(
            chain_counts[directory] >= compiled_count
            for directory in _CHAIN_DIRS
        ),
        "generic_producer_exact": bool(fact_payloads and claim_payloads and all_generic),
        "claims_nonempty": bool(claim_payloads and claims_nonempty),
        "fact_packet_digest_replay": fact_packet_replay,
        "claim_chain_digest_replay": bool(claim_payloads and claims_replay),
        "loop_trace_refs_present": bool(result.final_state.get("tool_call_trace_refs")),
    }
    return {
        "schema_version": "d1_research_loop_acceptance_v1",
        "status": "passed" if all(invariants.values()) else "failed",
        "run": {
            "run_id": run_id,
            "project_root": str(project_root.resolve()),
            "intent_path": str(intent_path.resolve()),
            "termination_reason": result.termination_reason,
            "turns_executed": result.turns_executed,
            "compiled_obligations": compiled_count,
            "supported_obligations": [item.obligation_id for item in supported],
            "behavior_nodes": len(result.loop_state.behavior_graph.nodes),
            "behavior_relations": len(result.loop_state.behavior_graph.relations),
            "tool_call_trace_refs": len(result.final_state.get("tool_call_trace_refs", [])),
        },
        "chain_counts": chain_counts,
        "invariants": invariants,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument("intent_path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", default="d1-research-loop")
    parser.add_argument("--max-turns", type=int, default=40)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Namespace the immutable tool artifacts by run id so a rerun cannot
    # accidentally satisfy chain-count checks with stale files from another
    # execution.
    artifact_root = output.parent / "tool_artifacts" / args.run_id
    report = evaluate(
        project_root=args.project_root,
        intent_path=args.intent_path,
        artifact_root=artifact_root,
        run_id=args.run_id,
        max_turns=args.max_turns,
    )
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
