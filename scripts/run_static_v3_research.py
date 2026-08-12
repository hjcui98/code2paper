#!/usr/bin/env python3
"""Run the current generic V3 research/data plane without an LLM provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.agentic.equation_claims import (
    bind_equations_to_claims,
    compile_equation_claims,
    derive_equation_proposals_from_facts,
)
from code2paper.agentic.obligation_fact_alignment import (
    bind_claims_to_obligations,
    build_obligation_coverage_v2,
)
from code2paper.agentic.method_content_regression import (
    build_python_behavior_inventory,
)
from code2paper.agentic.v3_runtime import (
    _recompute_claim_set_digest,
    _synthesize_terminal_gaps,
    build_v3_research_runtime,
    merge_compiled_evidence,
    run_v3_research_phase,
    write_d25_method_research_artifacts,
    write_v3_evidence_artifacts,
)
from code2paper.schemas import LLMConfig, LLMProvider


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("intent_path", type=Path)
    parser.add_argument("out_root", type=Path)
    parser.add_argument("--run-id", default="static-v3-research")
    parser.add_argument("--max-turns", type=int, default=100)
    args = parser.parse_args()
    args.out_root.mkdir(parents=True, exist_ok=True)
    runtime = build_v3_research_runtime(
        project_root=args.project_root,
        intent_path=args.intent_path,
        run_id=args.run_id,
        llm_config=LLMConfig(
            provider=LLMProvider.NONE,
            model="deterministic-supervisor",
            cache=False,
        ),
    ).model_copy(update={"artifact_root": args.out_root / "artifacts"})
    result = run_v3_research_phase(runtime, max_turns=args.max_turns)
    if not result.loop_state.compiled_evidence:
        print(json.dumps({
            "status": "incomplete",
            "termination_reason": result.termination_reason,
            "compiled_obligations": 0,
        }, indent=2))
        return 2
    packets, facts, claims = merge_compiled_evidence(
        result.loop_state.compiled_evidence,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    )
    claims = bind_claims_to_obligations(
        runtime.intent_graph,
        fact_set=facts,
        claim_set=claims,
    )
    terminal_gaps, terminal_gap_bindings = _synthesize_terminal_gaps(
        runtime,
        fact_set=facts,
    )
    if terminal_gaps:
        claims.explicit_code_gaps.extend(terminal_gaps)
        _recompute_claim_set_digest(claims)
    equations, _ = compile_equation_claims(
        derive_equation_proposals_from_facts(facts),
        facts,
        repo_snapshot_id=facts.repo_snapshot_id,
        project_tree_hash=facts.project_tree_hash,
    )
    equations = bind_equations_to_claims(equations, claims)
    paths = write_v3_evidence_artifacts(
        args.out_root,
        packet_set=packets,
        fact_set=facts,
        claim_set=claims,
        equation_set=equations,
    )
    coverage = build_obligation_coverage_v2(
        runtime.intent_graph,
        fact_set=facts,
        claim_set=claims,
        explicit_gaps=claims.explicit_code_gaps,
        gap_obligation_bindings=terminal_gap_bindings or None,
    )
    coverage_path = args.out_root / "artifacts" / "obligation_coverage_v2.json"
    coverage_path.write_text(coverage.model_dump_json(indent=2) + "\n", encoding="utf-8")
    paths["obligation_coverage_v2"] = str(coverage_path)
    paths.update(write_d25_method_research_artifacts(
        args.out_root,
        intent_graph=runtime.intent_graph,
        coverage_report=coverage,
        fact_set=facts,
        claim_set=claims,
        equation_set=equations,
    ))
    project_root = args.project_root.resolve()
    inventory_files: dict[str, str] = {}
    for entry in runtime.repo_snapshot.included_files:
        if entry.kind != "file" or not entry.path.endswith(".py"):
            continue
        source_path = (project_root / entry.path).resolve()
        if not source_path.is_relative_to(project_root) or not source_path.is_file():
            continue
        inventory_files[entry.path] = source_path.read_text(
            encoding="utf-8", errors="replace"
        )
    inventory = build_python_behavior_inventory(
        files=inventory_files,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    )
    inventory_path = args.out_root / "artifacts" / "repository_behavior_inventory_v1.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["repository_behavior_inventory_v1"] = str(inventory_path)
    if coverage.unresolved_must_cover_ids:
        status = "incomplete"
    elif coverage.explicit_gap_count:
        status = "complete_with_explicit_gaps"
    else:
        status = "supported"
    summary = {
        "status": status,
        "termination_reason": result.termination_reason,
        "compiled_obligations": len(result.loop_state.compiled_evidence),
        "packets": len(packets.packets),
        "facts": len(facts.facts),
        "claims": len(claims.claims),
        "equations": len(equations.equations),
        "explicit_gaps": len(claims.explicit_code_gaps),
        "unresolved_must_cover_ids": coverage.unresolved_must_cover_ids,
        "artifacts": paths,
    }
    summary_path = args.out_root / "artifacts" / "static_v3_research_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not coverage.unresolved_must_cover_ids else 2


if __name__ == "__main__":
    raise SystemExit(main())
