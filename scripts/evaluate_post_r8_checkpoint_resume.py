"""Produce a deterministic D4 checkpoint/resume acceptance artifact.

The report is intentionally a small fixture-level proof.  It does not claim
live-provider equivalence; it verifies the production checkpoint invariants
that can be established without a model call:

* interrupted + fresh-runtime resume has the same support boundary as a
  continuous deterministic run;
* the immutable payload namespace is stable across runtime instances;
* completed replay returns before the supervisor is invoked;
* tampered immutable content fails closed instead of starting a fresh loop.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2paper.agentic.research_graph import (
    initial_loop_state,
    run_research_loop,
    snapshot_loop_state,
)
from code2paper.agentic.research_models import (
    GlobalSafetyBudgetV1,
    GapRequirementV1,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
)
from code2paper.agentic.research_nodes import BudgetPolicyV1, ResearchGraphRuntime
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.state_v3 import empty_agent_state_v3


def _obligation(obligation_id: str, *, status: str = "in_progress") -> ResearchAgendaItemV1:
    gaps = (
        GapRequirementV1(
            requirement_id=f"gap:{obligation_id}",
            description=f"fixture gap for {obligation_id}",
            terminal="explicit_gap",
        ),
    ) if status == "explicit_gap" else ()
    return ResearchAgendaItemV1(
        obligation_id=obligation_id,
        priority="must_cover",
        status=status,  # type: ignore[arg-type]
        missing_information=["fixture evidence"],
        gap_requirements=list(gaps),
    )


def _runtime(snapshot: Any, run_id: str, *, terminal: bool = False) -> ResearchGraphRuntime:
    agenda = ResearchAgendaV1(
        run_id=run_id,
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[
            _obligation("obl-train", status="explicit_gap" if terminal else "in_progress"),
            _obligation("obl-eval", status="explicit_gap" if terminal else "in_progress"),
        ],
    )
    return ResearchGraphRuntime(
        run_id=run_id,
        repo_snapshot=snapshot,
        agenda=agenda,
        budget_policy=BudgetPolicyV1(),
        global_safety_budget=GlobalSafetyBudgetV1(),
    )


def _support_boundary(runtime: ResearchGraphRuntime, result: Any) -> dict[str, Any]:
    return {
        item.obligation_id: {
            "status": item.status,
            "supported_claim_ids": sorted(item.supported_claim_ids),
            "compiled_claim_identities": sorted(
                claim.canonical_identity
                for compiled in result.loop_state.compiled_evidence.values()
                if compiled.obligation_id == item.obligation_id
                for claim in compiled.claim_set.claims
                if claim.status == "supported"
            ),
        }
        for item in runtime.agenda.items
    }


def evaluate() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="code2paper-d4-fixture-") as temporary:
        root = Path(temporary)
        (root / "train.py").write_text(
            "def train():\n    return 1\n", encoding="utf-8"
        )
        (root / "eval.py").write_text(
            "def evaluate():\n    return 1\n", encoding="utf-8"
        )
        snapshot = build_repo_snapshot(root)

        uninterrupted_runtime = _runtime(snapshot, "d4-acceptance")
        uninterrupted = run_research_loop(uninterrupted_runtime, max_turns=20)

        interrupted_runtime = _runtime(snapshot, "d4-acceptance")
        interrupted = run_research_loop(interrupted_runtime, max_turns=1)
        checkpoint = snapshot_loop_state(interrupted.loop_state)
        resumed_state = dict(interrupted.final_state)
        resumed_state["status"] = "researching"
        resumed_state["blocked_reason"] = ""
        resumed_state["loop_state_snapshot"] = checkpoint

        # Build a new runtime object to model a process restart.  The stable
        # default artifact namespace must locate the same immutable payload.
        resumed_runtime = _runtime(snapshot, "d4-acceptance")
        resumed = run_research_loop(
            resumed_runtime,
            initial_state=resumed_state,
            max_turns=20,
        )
        uninterrupted_boundary = _support_boundary(uninterrupted_runtime, uninterrupted)
        resumed_boundary = _support_boundary(resumed_runtime, resumed)

        terminal_runtime = _runtime(snapshot, "d4-terminal", terminal=True)
        terminal_loop = initial_loop_state(terminal_runtime)
        terminal_loop.terminated = True
        terminal_loop.termination_reason = "all_obligations_terminal"
        terminal_snapshot = snapshot_loop_state(terminal_loop)
        terminal_state = empty_agent_state_v3(
            run_id=terminal_runtime.run_id,
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).model_copy(update={"status": "trusted"}).to_state_dict()
        terminal_state["loop_state_snapshot"] = terminal_snapshot
        terminal = run_research_loop(
            terminal_runtime,
            initial_state=terminal_state,
            max_turns=20,
        )

        tamper_path = Path(checkpoint["immutable_payload_ref"])
        original = tamper_path.read_bytes()
        tamper_path.write_bytes(b"{}\n")
        tamper_rejected = False
        try:
            run_research_loop(
                _runtime(snapshot, "d4-acceptance"),
                initial_state=resumed_state,
                max_turns=20,
            )
        except ValueError as exc:
            tamper_rejected = str(exc).startswith("invalid_loop_state_snapshot:")
        finally:
            tamper_path.write_bytes(original)

        stable_root = (
            str(interrupted_runtime.tool_context().artifact_root)
            == str(resumed_runtime.tool_context().artifact_root)
        )
        invariants = {
            "support_boundary_equivalent": uninterrupted_boundary == resumed_boundary,
            "stable_immutable_store_across_runtime_instances": stable_root,
            "completed_resume_zero_turns": terminal.turns_executed == 0,
            "tampered_checkpoint_rejected": tamper_rejected,
        }
        return {
            "schema_version": "d4_checkpoint_resume_acceptance_v1",
            "status": "passed" if all(invariants.values()) else "failed",
            "snapshot": {
                "immutable_payload_ref": checkpoint["immutable_payload_ref"],
                "immutable_payload_digest": checkpoint["immutable_payload_digest"],
                "snapshot_version": checkpoint["snapshot_version"],
            },
            "uninterrupted": {
                "terminated": uninterrupted.terminated,
                "termination_reason": uninterrupted.termination_reason,
                "turns_executed": uninterrupted.turns_executed,
                "support_boundary": uninterrupted_boundary,
            },
            "interrupted": {
                "termination_reason": interrupted.termination_reason,
                "turns_executed": interrupted.turns_executed,
            },
            "resumed": {
                "terminated": resumed.terminated,
                "termination_reason": resumed.termination_reason,
                "turns_executed": resumed.turns_executed,
                "support_boundary": resumed_boundary,
            },
            "completed_resume": {
                "terminated": terminal.terminated,
                "turns_executed": terminal.turns_executed,
                "termination_reason": terminal.termination_reason,
            },
            "invariants": invariants,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
