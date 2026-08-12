#!/usr/bin/env python3
"""Offline deterministic four-project plan projection (round-8 gate).

Replays the Architect replan path over the regenerated D2.5 artifacts without
any model call and reports the round-8 plan surface: critical/high placement,
configuration scoping, unresolved relations, and plan-gate truthfulness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2paper.agentic.evidence_compiler_v3 import (  # noqa: E402
    AtomicClaimSetV3,
    load_evidence_packets_v3,
    load_code_facts_v1,
)
from code2paper.agentic.equation_claims import (  # noqa: E402
    EquationClaimSetV1,
)
from code2paper.agentic.method_argument_models import (  # noqa: E402
    ConfigurationClaimSetV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
    ReferenceMethodAgendaV1,
)
from code2paper.agentic.method_architect import (  # noqa: E402
    replan_moves_with_trace,
)


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def project_projection(project_id: str, artifacts: Path) -> dict:
    def load(name: str):
        return artifacts / name

    claims = AtomicClaimSetV3.model_validate_json(load("atomic_claims_v3_v3.json").read_text())
    facts = load_code_facts_v1(str(load("code_facts_v1_v3.json")))
    equations = EquationClaimSetV1.model_validate_json(load("equation_claims_v1_v3.json").read_text())
    configurations = ConfigurationClaimSetV1.model_validate_json(
        load("configuration_claims_v1.json").read_text()
    )
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        load("method_completeness_matrix_v1.json").read_text()
    )
    plan = MethodSectionPlanV2.model_validate_json(load("method_section_plan_v2.json").read_text())
    packets = load_evidence_packets_v3(str(load("evidence_packets_v3_v3.json")))
    agenda = ReferenceMethodAgendaV1.model_validate_json(
        load("reference_method_agenda_v1.json").read_text()
    )

    new_plan, trace = replan_moves_with_trace(
        base_plan=plan,
        claims=claims,
        equations=equations,
        configurations=configurations,
        completeness=completeness,
        facts=facts,
        evidence_packets_v3=packets,
        agenda=agenda,
    )

    # Round-trip the rebuilt plan through its own model so every closed-ID
    # validator (duplicate keys, unknown bindings, proof/artifact closure)
    # runs; a validation failure is an invalid cross-reference.
    try:
        round_tripped = MethodSectionPlanV2.model_validate(new_plan.model_dump(mode="json"))
        plan_valid = True
        round_trip_error = ""
    except (TypeError, ValueError) as exc:
        round_tripped = None
        plan_valid = False
        round_trip_error = f"{exc.__class__.__name__}:{str(exc)[:240]}"
    rows = [
        item for item in completeness.items
        if item.importance in {"critical", "high"}
    ]
    by_id = new_plan.assignments_by_obligation()
    assignments = list(new_plan.obligation_assignments)
    unplaced = [item for item in assignments if item.placement_state == "unplaced"]
    external = [item for item in assignments if item.placement_state == "external_pending"]
    supported_unplaced = [
        item.obligation_id for item in unplaced
        if item.status in {"supported_by_repository", "partially_supported_by_repository"}
    ]
    unit_config_ids: dict[str, list[str]] = {}
    for unit in new_plan.argument_units:
        unit_config_ids[unit.argument_unit_id] = list(unit.configuration_ids)
    frame_unresolved: dict[str, list[str]] = {}
    for unit in new_plan.argument_units:
        if unit.semantic_frame is not None:
            frame_unresolved[unit.argument_unit_id] = list(unit.semantic_frame.unresolved_relation_ids)
    return {
        "project": project_id,
        "plan_digest": new_plan.content_digest,
        "plan_valid": plan_valid,
        "plan_round_trip_error": round_trip_error,
        "critical_high_count": len(rows),
        "assignment_counts": {
            "assigned": sum(1 for i in assignments if i.placement_state == "assigned"),
            "external_pending": len(external),
            "unplaced": len(unplaced),
        },
        "supported_unplaced_ids": supported_unplaced,
        "all_unplaced_ids": [item.obligation_id for item in unplaced],
        "external_pending_ids": [
            {"obligation_id": item.obligation_id, "status": item.status,
             "authority_lane": item.authority_lane, "required_move": item.required_move}
            for item in external
        ],
        "unit_configuration_ids": unit_config_ids,
        "frame_unresolved_relations": frame_unresolved,
        "configuration_claims": [
            {"key": c.key, "state": c.state, "value": c.value, "active": c.active,
             "override_chain": list(c.override_chain)}
            for c in configurations.claims
        ],
        "plan_gate_expected": (
            plan_valid
            and len(supported_unplaced) == 0
            and len(unplaced) == 0
            and not any(frame_unresolved.values())
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+",
                        help="per-project artifact dirs: <project>=<path>")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = {}
    for entry in args.roots:
        project_id, _, raw = entry.partition("=")
        reports[project_id] = project_projection(project_id, Path(raw))
    summary = {
        "schema_version": "r8_offline_projection_v1",
        "projects": reports,
        "aggregate": {
            "any_supported_unplaced": any(
                r["supported_unplaced_ids"] for r in reports.values()
            ),
            "any_unplaced": any(r["all_unplaced_ids"] for r in reports.values()),
            "any_unresolved_required_relation": any(
                r["frame_unresolved_relations"] for r in reports.values()
            ),
            "any_plan_gate_expected_false": any(
                not r["plan_gate_expected"] for r in reports.values()
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["aggregate"]["any_plan_gate_expected_false"] is False else 1


if __name__ == "__main__":
    raise SystemExit(main())
