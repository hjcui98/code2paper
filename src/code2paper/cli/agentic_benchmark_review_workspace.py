from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.agentic.benchmark_protocol import load_benchmark_protocol_v2
from code2paper.agentic.benchmark_review_workspace import (
    build_review_dossier,
    materialize_review_workspace,
    materialize_review_dossiers,
    record_claim_adjudication,
    record_figure_adjudication,
    record_run_adjudication,
    review_workspace_progress,
    sign_review,
    validate_review_workspace,
)
from code2paper.agentic.benchmark_v2 import load_benchmark_dataset_v2
from code2paper.agentic.tool_runtime import atomic_write_bytes, atomic_write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-agentic-benchmark-review-workspace",
        description="Materialize or validate digest-pinned named-human P4 review files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize", help="Create one non-overwriting review file per queue entry.")
    materialize.add_argument("--queue", required=True)
    materialize.add_argument("--out-root", required=True)
    progress = subparsers.add_parser("progress", help="Show unresolved human decisions without adjudicating them.")
    progress.add_argument("--workspace", required=True)
    inspect = subparsers.add_parser("inspect", help="Render one digest-verified, read-only review dossier.")
    _review_selector_arguments(inspect)
    inspect.add_argument("--out", default="", help="Optional non-existing Markdown output path; stdout otherwise.")
    inspect_all = subparsers.add_parser("inspect-all", help="Materialize non-overwriting dossiers for every review.")
    inspect_all.add_argument("--workspace", required=True)
    inspect_all.add_argument("--out-root", required=True)
    claim = subparsers.add_parser("claim", help="Record all explicit decisions for one frozen claim.")
    _review_selector_arguments(claim)
    claim.add_argument("--claim-id", required=True)
    claim.add_argument("--semantic-match", required=True, choices=("matched", "no_match"))
    claim.add_argument("--gold-claim-id", default="")
    claim.add_argument("--mutation-match", required=True, choices=("matched", "no_match"))
    claim.add_argument("--mutation-id", default="")
    claim.add_argument("--direct-evidence-support", required=True, type=_boolean)
    claim.add_argument("--qualifiers-preserved", required=True, type=_boolean)
    figure = subparsers.add_parser("figure", help="Record all explicit decisions for one frozen figure element.")
    _review_selector_arguments(figure)
    figure.add_argument("--element-id", required=True)
    figure.add_argument("--gold-claim-id", default="")
    figure.add_argument("--relation-id", default="")
    figure.add_argument("--semantically-supported", required=True, type=_boolean)
    figure.add_argument("--direct-relation-evidence", required=True, type=_boolean)
    figure.add_argument("--rendered-drift", required=True, type=_boolean)
    run = subparsers.add_parser("run", help="Record explicit run-level usability, intent, and block decisions.")
    _review_selector_arguments(run)
    run.add_argument("--usable-completion", required=True, type=_boolean)
    run.add_argument("--intent-fields-reviewed", required=True, type=_boolean)
    run.add_argument("--blocked-reason-review", default="")
    run.add_argument(
        "--blocked-reason-classification",
        default="",
        choices=("", "correct_repairable", "correct_terminal", "false_block"),
    )
    sign = subparsers.add_parser("sign", help="Apply an attributable signature only after every decision is complete.")
    _review_selector_arguments(sign)
    sign.add_argument("--reviewer", required=True)
    sign.add_argument("--reviewed-at", required=True)
    validate = subparsers.add_parser("validate", help="Validate exact review coverage and artifact bindings.")
    validate.add_argument("--queue", required=True)
    validate.add_argument("--workspace", required=True)
    validate.add_argument("--gold", required=True)
    validate.add_argument("--protocol", required=True)
    validate.add_argument("--report-out", required=True)
    validate.add_argument("--observations-out", default="")
    args = parser.parse_args(argv)
    if args.command == "materialize":
        manifest = materialize_review_workspace(args.queue, args.out_root)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        print(json.dumps({
            "workspace_manifest": str(manifest),
            "expected_reviews": payload["expected_reviews"],
            "status": payload["status"],
        }, ensure_ascii=False, indent=2))
        return 0
    if args.command == "progress":
        print(json.dumps(review_workspace_progress(args.workspace), ensure_ascii=False, indent=2))
        return 0
    if args.command == "inspect":
        dossier = build_review_dossier(args.workspace, args.review)
        if not args.out:
            print(dossier)
            return 0
        output = Path(args.out).expanduser().resolve()
        if output.exists():
            raise FileExistsError(f"review dossier output already exists:{output}")
        atomic_write_bytes(output, dossier.encode("utf-8"))
        print(json.dumps({"dossier": str(output), "read_only": True}, indent=2))
        return 0
    if args.command == "inspect-all":
        dossier_manifest = materialize_review_dossiers(args.workspace, args.out_root)
        payload = json.loads(dossier_manifest.read_text(encoding="utf-8"))
        print(json.dumps({
            "dossier_manifest": str(dossier_manifest),
            "dossier_count": payload["dossier_count"],
            "read_only": True,
        }, indent=2))
        return 0
    if args.command == "claim":
        path = record_claim_adjudication(
            args.workspace,
            args.review,
            args.claim_id,
            semantic_match=args.semantic_match,
            gold_claim_id=args.gold_claim_id,
            mutation_match=args.mutation_match,
            mutation_id=args.mutation_id,
            direct_evidence_support=args.direct_evidence_support,
            qualifiers_preserved=args.qualifiers_preserved,
        )
        print(json.dumps({"review": str(path), "updated": "claim", "claim_id": args.claim_id}, indent=2))
        return 0
    if args.command == "figure":
        path = record_figure_adjudication(
            args.workspace,
            args.review,
            args.element_id,
            gold_claim_id=args.gold_claim_id,
            relation_id=args.relation_id,
            semantically_supported=args.semantically_supported,
            direct_relation_evidence=args.direct_relation_evidence,
            rendered_drift=args.rendered_drift,
        )
        print(json.dumps({"review": str(path), "updated": "figure", "element_id": args.element_id}, indent=2))
        return 0
    if args.command == "run":
        path = record_run_adjudication(
            args.workspace,
            args.review,
            usable_completion=args.usable_completion,
            intent_fields_reviewed=args.intent_fields_reviewed,
            blocked_reason_review=args.blocked_reason_review,
            blocked_reason_classification=args.blocked_reason_classification,
        )
        print(json.dumps({"review": str(path), "updated": "run"}, indent=2))
        return 0
    if args.command == "sign":
        path = sign_review(
            args.workspace,
            args.review,
            reviewer=args.reviewer,
            reviewed_at=args.reviewed_at,
        )
        print(json.dumps({"review": str(path), "signed": True, "reviewer": args.reviewer}, indent=2))
        return 0
    report, observations = validate_review_workspace(
        args.queue,
        args.workspace,
        load_benchmark_dataset_v2(args.gold),
        load_benchmark_protocol_v2(args.protocol),
    )
    atomic_write_json(args.report_out, report)
    if report["hard_gate_passed"] and args.observations_out:
        atomic_write_json(args.observations_out, [item.model_dump(mode="json") for item in observations])
    print(json.dumps({
        "report": str(Path(args.report_out).resolve()),
        "status": report["status"],
        "validated": report["validated_review_count"],
        "pending": report["pending_review_count"],
        "invalid": report["invalid_review_count"],
        "observations_emitted": report["observations_emitted"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["hard_gate_passed"] else (1 if report["status"] == "pending_human_review" else 2)


def _review_selector_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace", required=True)
    parser.add_argument(
        "--review",
        required=True,
        help="Manifest review basename, reviews/... relative path, or exact absolute path.",
    )


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("expected true or false")


if __name__ == "__main__":
    raise SystemExit(main())
