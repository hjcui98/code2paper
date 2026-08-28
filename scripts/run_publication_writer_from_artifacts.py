#!/usr/bin/env python3
"""Run the Publication Method Writer from a frozen D2.5 artifact directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.agentic.evidence_compiler_v3 import (
    load_atomic_claims_v3,
    load_code_facts_v1,
    load_evidence_packets_v3,
)
from code2paper.agentic.equation_claims import load_equation_claims
from code2paper.agentic.method_architect import (
    build_method_section_plan_with_product_readiness,
)
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
)
from code2paper.agentic.method_proposition_compiler import compile_method_propositions
from code2paper.agentic.method_proposition_provider import (
    build_method_proposition_architect,
)
from code2paper.agentic.method_proposition_evidence_provider import (
    build_method_proposition_evidence_judge,
)
from code2paper.agentic.publication_method_writer import run_publication_method_writer
from code2paper.agentic.trust_contracts import AuthoringInputProjection
from code2paper.llm.providers import load_llm_config_from_env


_INPUT_FILES = {
    "atomic_claims_v3": ("atomic_claims_v3_v3.json", "atomic_claims_v3.json"),
    "code_facts_v1": ("code_facts_v1_v3.json", "code_facts_v1.json"),
    "equation_claims_v1": ("equation_claims_v1_v3.json", "equation_claims_v1.json"),
    "configuration_claims_v1": ("configuration_claims_v1.json",),
    "method_completeness_matrix_v1": ("method_completeness_matrix_v1.json",),
    "method_section_plan_v2": ("method_section_plan_v2.json",),
}
_OPTIONAL_INPUT_FILES = {
    "evidence_packets_v3": ("evidence_packets_v3_v3.json", "evidence_packets_v3.json"),
    "authoring_projection_v1": ("authoring_projection_v1.json",),
    "method_propositions_v1": ("method_propositions_v1.json",),
    "method_proposition_bindings_v1": ("method_proposition_bindings_v1.json",),
    "method_proposition_clusters_v1": ("method_proposition_clusters_v1.json",),
    "plan_product_readiness_v1": ("plan_product_readiness_v1.json",),
    "method_evidence": (
        "method_evidence.json",
        "method_evidence_for_final_validation.json",
        "04_evidence/method_evidence.json",
    ),
    "evidence_raw": ("evidence_raw.json", "02_intake/evidence_raw.json"),
    "evidence_snapshot_v2": (
        "evidence_snapshot_v2.json",
        "04_evidence/evidence_snapshot_v2.json",
        "07_validation/evidence_snapshot_v2.json",
    ),
}


def _first_file(root: Path, candidates: tuple[str, ...]) -> Path | None:
    return next((root / name for name in candidates if (root / name).is_file()), None)


def _prepare_current_authoring_artifacts(
    *, paths: dict[str, str], out_root: Path, llm_config
) -> dict[str, str]:
    """Upgrade frozen research authority to the current proposition path.

    This performs no repository search and never edits the frozen input.  It
    recompiles only authoring artifacts from the digest-bound facts, claims,
    packets, completeness matrix and persisted authoring story spine.
    """

    required = (
        "atomic_claims_v3", "code_facts_v1", "evidence_packets_v3",
        "equation_claims_v1", "configuration_claims_v1",
        "method_completeness_matrix_v1", "authoring_projection_v1",
    )
    missing = [name for name in required if not paths.get(name)]
    if missing:
        raise ValueError("cannot prepare proposition replay; missing " + ",".join(missing))
    claims = load_atomic_claims_v3(paths["atomic_claims_v3"])
    facts = load_code_facts_v1(paths["code_facts_v1"])
    packets = load_evidence_packets_v3(paths["evidence_packets_v3"])
    equations = load_equation_claims(paths["equation_claims_v1"])
    configurations = ConfigurationClaimSetV1.model_validate_json(
        Path(paths["configuration_claims_v1"]).read_text(encoding="utf-8")
    )
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text(encoding="utf-8")
    )
    projection = AuthoringInputProjection.model_validate_json(
        Path(paths["authoring_projection_v1"]).read_text(encoding="utf-8")
    )
    prior_plan = MethodSectionPlanV2.model_validate_json(
        Path(paths["method_section_plan_v2"]).read_text(encoding="utf-8")
    )
    story_spine = tuple(projection.author_story_spine)
    architect = build_method_proposition_architect(llm_config)
    evidence_judge = build_method_proposition_evidence_judge(llm_config)
    propositions, bindings, clusters = compile_method_propositions(
        claims=claims, facts=facts, packets=packets,
        completeness=completeness, story_spine=story_spine,
        proposal_architect=architect,
        evidence_judge=evidence_judge,
        require_evidence_judge=True,
        configurations=configurations,
        equations=equations,
    )
    plan, readiness, plan_trace = build_method_section_plan_with_product_readiness(
        claims=claims, completeness=completeness, equations=equations,
        configurations=configurations, story_spine=story_spine,
        propositions=propositions,
        method_name=prior_plan.method_name,
        venue=prior_plan.venue,
        audience=prior_plan.audience,
        page_budget=prior_plan.total_page_budget,
    )
    prepared = out_root / "_prepared_inputs"
    prepared.mkdir(parents=True, exist_ok=False)
    artifacts = {
        "method_propositions_v1": propositions.model_dump(mode="json"),
        "method_proposition_bindings_v1": bindings.model_dump(mode="json"),
        "method_proposition_clusters_v1": {
            "schema_version": "1.0",
            "clusters": [item.model_dump(mode="json") for item in clusters],
        },
        "method_proposition_architect_calls_v1": {
            "schema_version": "1.0",
            "calls": list(getattr(architect, "proposal_traces", ())),
        },
        "method_proposition_evidence_judge_calls_v1": {
            "schema_version": "1.0",
            "calls": list(getattr(evidence_judge, "evidence_judge_traces", ())),
        },
        "method_section_plan_v2": plan.model_dump(mode="json"),
        "plan_product_readiness_v1": readiness.model_dump(mode="json"),
        "method_architect_plan_trace_v1": plan_trace,
    }
    for name, payload in artifacts.items():
        target = prepared / f"{name}.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths[name] = str(target)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("out_root", type=Path)
    parser.add_argument(
        "--prepare-propositions", action="store_true",
        help="Recompile current proposition/plan artifacts from frozen research authority.",
    )
    parser.add_argument(
        "--prepare-only", action="store_true",
        help="Stop after proposition/Judge/plan preparation without calling the Writer.",
    )
    args = parser.parse_args(argv)
    artifact_dir = args.artifact_dir.expanduser().resolve()
    out_root = args.out_root.expanduser().resolve()
    paths: dict[str, str] = {}
    for key, candidates in _INPUT_FILES.items():
        candidate = _first_file(artifact_dir, candidates)
        if candidate is not None:
            paths[key] = str(candidate)
    for key, candidates in _OPTIONAL_INPUT_FILES.items():
        for filename in candidates:
            candidate = artifact_dir / filename
            if candidate.is_file():
                paths[key] = str(candidate)
                break
    missing = [key for key in _INPUT_FILES if key not in paths]
    if missing:
        parser.error("missing frozen inputs: " + ", ".join(missing))
    llm_config = load_llm_config_from_env()
    if args.prepare_only:
        args.prepare_propositions = True
    if args.prepare_propositions:
        try:
            paths = _prepare_current_authoring_artifacts(
                paths=paths, out_root=out_root, llm_config=llm_config,
            )
        except (OSError, TypeError, ValueError) as exc:
            parser.error(f"failed to prepare proposition replay: {exc}")
    if args.prepare_only:
        prepared = {
            key: value
            for key, value in paths.items()
            if str(Path(value).parent).startswith(str(out_root / "_prepared_inputs"))
        }
        print(json.dumps({
            "status": "prepared",
            "outputs": prepared,
        }, ensure_ascii=False, indent=2))
        return 0
    result, outputs = run_publication_method_writer(
        out_root=out_root,
        artifact_paths=paths,
        llm_config=llm_config,
    )
    print(json.dumps({
        "status": result.status,
        "blocked_reason": result.blocked_reason,
        "accepted_section_ids": result.accepted_section_ids,
        "incomplete_section_ids": result.incomplete_section_ids,
        "binding_failures": result.binding_failures,
        "candidate_generation_status": result.candidate_generation_status,
        "candidate_available": result.candidate_available,
        "candidate_validation_status": result.candidate_validation_status,
        "candidate_warnings_by_severity": result.candidate_warnings_by_severity,
        "verified_validation_status": result.verified_validation_status,
        "publication_ready": result.publication_ready,
        "outputs": outputs,
    }, ensure_ascii=False, indent=2))
    # Q0 product exit semantics (plan 19.4.2): a generated candidate is a
    # normal exit even when it carries validation warnings and is not
    # publication-ready (review_ready_with_warnings).  Only a true generation
    # failure — no durable candidate — is a failed publication-stage exit.
    return 0 if result.candidate_generation_status == "generated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
