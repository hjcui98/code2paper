#!/usr/bin/env python3
"""Run the Publication Method Writer from a frozen D2.5 artifact directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.agentic.publication_method_writer import run_publication_method_writer
from code2paper.llm.providers import load_llm_config_from_env


_INPUT_FILES = {
    "atomic_claims_v3": "atomic_claims_v3_v3.json",
    "code_facts_v1": "code_facts_v1_v3.json",
    "equation_claims_v1": "equation_claims_v1_v3.json",
    "configuration_claims_v1": "configuration_claims_v1.json",
    "method_completeness_matrix_v1": "method_completeness_matrix_v1.json",
    "method_section_plan_v2": "method_section_plan_v2.json",
}
_OPTIONAL_INPUT_FILES = {
    "evidence_packets_v3": ("evidence_packets_v3_v3.json",),
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path)
    parser.add_argument("out_root", type=Path)
    args = parser.parse_args(argv)
    artifact_dir = args.artifact_dir.expanduser().resolve()
    out_root = args.out_root.expanduser().resolve()
    paths = {key: str(artifact_dir / filename) for key, filename in _INPUT_FILES.items()}
    for key, candidates in _OPTIONAL_INPUT_FILES.items():
        for filename in candidates:
            candidate = artifact_dir / filename
            if candidate.is_file():
                paths[key] = str(candidate)
                break
    missing = [key for key, path in paths.items() if not Path(path).is_file()]
    if missing:
        parser.error("missing frozen inputs: " + ", ".join(missing))
    result, outputs = run_publication_method_writer(
        out_root=out_root,
        artifact_paths=paths,
        llm_config=load_llm_config_from_env(),
    )
    print(json.dumps({
        "status": result.status,
        "blocked_reason": result.blocked_reason,
        "accepted_section_ids": result.accepted_section_ids,
        "incomplete_section_ids": result.incomplete_section_ids,
        "binding_failures": result.binding_failures,
        "outputs": outputs,
    }, ensure_ascii=False, indent=2))
    # When optional V3 packet + MethodEvidence inputs are present, the Writer
    # also emits final_text_claims/text_evidence_validation and fails closed on
    # unsupported final sentences. Without them, reverse validation remains
    # explicitly pending at this isolated milestone.  Neither a blocked run
    # nor a quality-incomplete draft is a successful publication-stage exit.
    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
