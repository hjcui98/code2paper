#!/usr/bin/env python3
"""Build the fail-closed D3 acceptance artifact from frozen run evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.agentic.holdout_mutation import (
    HoldoutCaseEvidenceV1,
    HoldoutMutationOutcomeV1,
    build_holdout_acceptance_report,
    write_holdout_acceptance_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True, help="JSON array of HoldoutCaseEvidenceV1")
    parser.add_argument("--mutations", required=True, help="JSON array of mutation outcomes")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    cases_payload = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    mutations_payload = json.loads(Path(args.mutations).read_text(encoding="utf-8"))
    cases = [HoldoutCaseEvidenceV1.model_validate(item) for item in cases_payload]
    mutations = [HoldoutMutationOutcomeV1.model_validate(item) for item in mutations_payload]
    report = build_holdout_acceptance_report(cases, mutations)
    write_holdout_acceptance_report(args.out, report)
    print(json.dumps({"status": report.status, "failures": report.failures}))
    return 0 if report.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
