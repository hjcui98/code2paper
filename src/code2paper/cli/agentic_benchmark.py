"""Aggregate agentic run evaluation reports for benchmark comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from code2paper.agentic.benchmark_report import (
    AgenticBenchmarkRunSpec,
    build_agentic_benchmark_report,
    write_agentic_benchmark_report,
)
from code2paper.agentic.benchmark_v2 import (
    build_benchmark_report_v2,
    load_benchmark_dataset_v2,
    load_benchmark_observations_v2,
    validate_gold_evidence,
    write_benchmark_report_v2,
)
from code2paper.agentic.benchmark_observation import extract_benchmark_observation_v2, load_benchmark_run_review_v2
from code2paper.agentic.benchmark_review_workspace import validate_review_workspace
from code2paper.agentic.cutover import NamedReviewEvidenceV2, RolloutEvidenceV2, decide_cutover
from code2paper.agentic.tool_runtime import atomic_write_json
from code2paper.agentic.benchmark_protocol import load_benchmark_protocol_v2, validate_protocol_observations_v2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-agentic-benchmark",
        description="Aggregate agentic_run_evaluation_report.json files into a benchmark report.",
    )
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        metavar="[variant=][label=]PATH",
        help="Evaluation report path. Optional prefixes set variant and label.",
    )
    parser.add_argument("reports", nargs="*", help="Evaluation report paths using variant=agentic and path stem labels.")
    parser.add_argument("--out", required=True, help="Output path for agentic_benchmark_report.json")
    parser.add_argument("--gold", default="", help="P4 BenchmarkDatasetV2 gold/adversarial JSON.")
    parser.add_argument(
        "--observations",
        default="",
        help="P4 BenchmarkObservationV2 JSON list for reporting; this input cannot authorize cutover.",
    )
    parser.add_argument(
        "--review", action="append", default=[],
        help="Digest-pinned BenchmarkRunReviewV2 JSON; repeat for every run. Required to authorize cutover beyond hold.",
    )
    parser.add_argument(
        "--review-workspace",
        default="",
        help="Validated review workspace root; consumes every exact queue entry without 25 repeated --review flags.",
    )
    parser.add_argument(
        "--review-queue",
        default="",
        help="Frozen review queue used to materialize --review-workspace.",
    )
    parser.add_argument("--observations-out", default="", help="Write artifact-extracted observations to this JSON path.")
    parser.add_argument("--workspace-root", default=".", help="Root used to verify gold code excerpts.")
    parser.add_argument("--rollout", default="", help="Optional RolloutEvidenceV2 JSON for cutover decision.")
    parser.add_argument("--cutover-out", default="", help="Output path for CutoverDecisionV2 JSON.")
    parser.add_argument("--protocol", default="", help="Frozen BenchmarkProtocolV2 used to validate the exact run matrix.")
    args = parser.parse_args(argv)

    if args.gold or args.observations or args.review or args.review_workspace:
        sources = sum(bool(item) for item in (args.observations, args.review, args.review_workspace))
        if not args.gold or sources != 1:
            parser.error("P4 mode requires --gold and exactly one of --observations, --review, or --review-workspace")
        if args.review_workspace and (not args.review_queue or not args.protocol):
            parser.error("--review-workspace requires --review-queue and --protocol")
        dataset = load_benchmark_dataset_v2(args.gold)
        gold_failures = validate_gold_evidence(dataset, args.workspace_root)
        if gold_failures:
            print(f"[code2paper-agentic-benchmark] error={gold_failures[0]}", file=sys.stderr)
            return 2
        review_evidence = NamedReviewEvidenceV2()
        protocol = load_benchmark_protocol_v2(args.protocol) if args.protocol else None
        if args.review_workspace:
            workspace_report, observations = validate_review_workspace(
                args.review_queue,
                args.review_workspace,
                dataset,
                protocol,
            )
            if not workspace_report["hard_gate_passed"]:
                print(
                    f"[code2paper-agentic-benchmark] error=review_workspace_{workspace_report['status']}",
                    file=sys.stderr,
                )
                return 2
            review_paths = [item["review_path"] for item in workspace_report["validated_reviews"]]
            review_evidence = NamedReviewEvidenceV2(
                source="digest_pinned_review_artifacts",
                review_artifact_digests=[
                    "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
                    for path in review_paths
                ],
            )
        elif args.review:
            case_by_id = {item.case_id: item for item in dataset.cases}
            reviews = [load_benchmark_run_review_v2(path) for path in args.review]
            observations = [extract_benchmark_observation_v2(case_by_id[item.case_id], item) for item in reviews]
            review_evidence = NamedReviewEvidenceV2(
                source="digest_pinned_review_artifacts",
                review_artifact_digests=[
                    "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
                    for path in args.review
                ],
            )
        else:
            observations = load_benchmark_observations_v2(args.observations)
        if (args.review or args.review_workspace) and args.observations_out:
            atomic_write_json(args.observations_out, [item.model_dump(mode="json") for item in observations])
        protocol_validated = False
        if protocol is not None:
            protocol_failures = validate_protocol_observations_v2(protocol, observations)
            if protocol_failures:
                print(f"[code2paper-agentic-benchmark] error={protocol_failures[0]}", file=sys.stderr)
                return 2
            protocol_validated = True
        report = build_benchmark_report_v2(dataset, observations)
        output = write_benchmark_report_v2(args.out, report)
        rollout = RolloutEvidenceV2()
        if args.rollout:
            rollout = RolloutEvidenceV2.model_validate_json(Path(args.rollout).read_text(encoding="utf-8"))
        rollout = rollout.model_copy(update={"protocol_validated": protocol_validated})
        decision = decide_cutover(
            dataset,
            report.evaluated_runs,
            rollout,
            named_review_evidence=review_evidence,
        )
        if args.cutover_out:
            atomic_write_json(args.cutover_out, decision)
        print(f"[code2paper-agentic-benchmark] report={output}")
        print(json.dumps({
            "case_count": report.case_count,
            "run_count": len(report.evaluated_runs),
            "variants": [item.variant for item in report.variant_summaries],
            "paired_intent_sensitivity_passed": report.paired_intent_sensitivity_passed,
            "cutover_status": decision.status,
            "default_mode": decision.default_mode,
            "cutover_failures": decision.failures,
        }, ensure_ascii=False, indent=2))
        return 0

    specs = [_parse_run_spec(raw) for raw in args.run]
    specs.extend(
        AgenticBenchmarkRunSpec(path=str(Path(path).expanduser().resolve()), variant="agentic", label=Path(path).stem)
        for path in args.reports
    )
    if not specs:
        parser.error("at least one --run or positional report path is required")
    missing_reports = [spec.path for spec in specs if not Path(spec.path).exists()]
    if missing_reports:
        print(f"[code2paper-agentic-benchmark] error=report_not_found:{missing_reports[0]}", file=sys.stderr)
        return 2
    report = build_agentic_benchmark_report(specs)
    output = write_agentic_benchmark_report(args.out, report)
    print(f"[code2paper-agentic-benchmark] report={output}")
    print(
        json.dumps(
            {
                "run_count": report.run_count,
                "variants": report.variants,
                "best_variant": report.best_variant,
                "recommended_actions": report.recommended_actions,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _parse_run_spec(raw: str) -> AgenticBenchmarkRunSpec:
    parts = raw.split("=", 2)
    if len(parts) == 1:
        path = Path(parts[0]).expanduser().resolve()
        return AgenticBenchmarkRunSpec(path=str(path), variant="agentic", label=path.stem)
    if len(parts) == 2:
        variant, path_text = parts
        path = Path(path_text).expanduser().resolve()
        return AgenticBenchmarkRunSpec(path=str(path), variant=variant or "agentic", label=path.stem)
    variant, label, path_text = parts
    path = Path(path_text).expanduser().resolve()
    return AgenticBenchmarkRunSpec(path=str(path), variant=variant or "agentic", label=label or path.stem)


if __name__ == "__main__":
    raise SystemExit(main())
