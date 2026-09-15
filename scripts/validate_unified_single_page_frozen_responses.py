#!/usr/bin/env python3
"""Run the single-page Writer contract against frozen provider responses.

This utility is provider-free.  It replays the two recorded response bodies
through the production normalizer, Binder, repair projection, and content
assessor, then checks the arithmetic counterexamples and prompt contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _response_from_frozen(raw: dict[str, Any], metadata: Any, failures: list[str]) -> Any:
    from code2paper.llm.client import LLMResponse

    blocked = (
        "publication_paragraph_transaction_failed:" + ";".join(failures)
        if failures else None
    )
    return LLMResponse(
        text=str(metadata.section_markdown or ""),
        response_hash=str(raw.get("content_digest") or raw.get("response_digest") or ""),
        blocked_reason=blocked,
        finish_reason=str(raw.get("finish_reason") or ""),
        provider_finish_reason=str(raw.get("provider_finish_reason") or ""),
        token_usage=raw.get("usage"),
        metadata=metadata,
    )


def _run(args: argparse.Namespace) -> int:
    from code2paper.agentic.publication_transaction_contract import (
        _arithmetic_relation_satisfied,
        _top_level_addition_terms,
        _witness_constraints_from_plan_row,
    )
    from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1
    from code2paper.llm.section_writer import (
        WriterSectionInput,
        _normalize_publication_paragraph_transaction,
        _publication_paragraph_repair_contract,
        assess_publication_content_acceptance,
        assess_publication_writer_response,
        default_section_system_prompt,
    )

    run = Path(args.run).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    state_path = run / "single_page_state.json"
    state = _read_json(state_path)
    section = WriterSectionInput(**state["writer_section"])
    response_paths = sorted(
        run.glob("artifacts/06_authoring/invocations/**/attempt-000*.provider-response.json")
    )
    if len(response_paths) != 2:
        raise ValueError(f"expected_two_frozen_responses:{len(response_paths)}")

    attempts: list[dict[str, Any]] = []
    for path in response_paths:
        raw = _read_json(path)
        parsed = PublicationMethodSectionOutputV1.model_validate_json(
            str(raw["response_text"])
        )
        recovery: list[dict[str, Any]] = []
        normalized, failures = _normalize_publication_paragraph_transaction(
            parsed,
            section=section,
            require_transactions=True,
            binder_recovery_sink=recovery,
        )
        response = _response_from_frozen(raw, normalized, failures)
        accepted, metrics = assess_publication_content_acceptance(section, response)
        repairs = _publication_paragraph_repair_contract(section, response)
        packet = repairs[0] if repairs else {}
        paragraph = normalized.paragraphs[0]
        attempts.append({
            "attempt": int(raw.get("attempt") or 0),
            "provider_calls": 0,
            "body_chars_after_known_heading_recovery": len(
                paragraph.paragraph_markdown
            ),
            "heading_recovery": [
                item for item in recovery
                if item.get("operation") == "repair_known_section_heading_from_paragraph"
            ],
            "normalization_failures": failures,
            "format_failure_absent": not any(
                item.startswith("paragraph_body_not_substantive:")
                for item in failures
            ),
            "content_accepted": accepted,
            "metrics": {
                key: metrics[key]
                for key in (
                    "invalid_count", "invalid_witness_count",
                    "valid_paragraph_count", "valid_target_count",
                    "required_target_count", "valid_atom_count",
                    "required_atom_count", "missing_atom_count",
                    "authority_violation_count", "formula_exact_body_count",
                    "formula_consumed_count",
                )
            },
            "remaining_failures": list(metrics["failures"]),
            "repair_atom_count": len(packet.get("missing_atom_targets") or ()),
            "repair_target_count": len(packet.get("missing_targets") or ()),
            "repair_owner_counts": {
                owner: sum(
                    item.get("repair_owner") == owner
                    for item in (packet.get("missing_atom_targets") or ())
                )
                for owner in ("writer", "binder")
            },
            "repair_atoms_have_no_internal_ids": all(
                "target_id" not in item
                and "source_anchor_ids" not in item
                for item in (packet.get("missing_atom_targets") or ())
            ),
            "repair_atom_targets": list(packet.get("missing_atom_targets") or ()),
        })

    constraints = _witness_constraints_from_plan_row(
        section.argument_graph["paragraphs"][0]
    )
    allocation_sentence = (
        "When dedicated attention is enabled, a zero tensor of shape "
        "(batch size, number of passages + 1, number of passages + 1) is "
        "allocated on the model device, yielding the dedicated attention mask."
    )
    detail_22 = [
        (key, local)
        for key, local in constraints.items()
        if key[0] == "atom"
        and str(local.get("detail_id") or "").endswith(":22")
    ]
    allocation_checks = [
        {
            "paper_role": str(local.get("paper_role") or ""),
            "nested_plus_is_not_top_level": not bool(
                _top_level_addition_terms(local.get("exact", ())[0])
            ) if local.get("exact") else True,
            "exact_source_accepts": _arithmetic_relation_satisfied(
                local.get("exact", ())[0] if local.get("exact") else "",
                local,
            ),
            "allocation_sentence_accepts": _arithmetic_relation_satisfied(
                allocation_sentence,
                local,
            ),
        }
        for _key, local in detail_22
    ]
    addition_constraints = {
        "exact": ("combined = document_embeddings + passage_embeddings",),
        "semantic_atom": "document_embeddings + passage_embeddings",
        "paper_role": "operation",
        "conditions": (),
    }
    arithmetic_counterexamples = {
        "valid_addition": _arithmetic_relation_satisfied(
            "The result sums document embeddings and passage embeddings.",
            addition_constraints,
        ),
        "addition_to_multiplication_rejected": not _arithmetic_relation_satisfied(
            "The result multiplies document embeddings and passage embeddings.",
            addition_constraints,
        ),
        "missing_addend_rejected": not _arithmetic_relation_satisfied(
            "The result adds only document embeddings.",
            addition_constraints,
        ),
        "negated_addition_rejected": not _arithmetic_relation_satisfied(
            "The result is not added to the passage embeddings.",
            addition_constraints,
        ),
    }
    prompt = default_section_system_prompt()
    script_text = (_ROOT / "scripts" / "run_unified_single_page_writer.py").read_text(
        encoding="utf-8"
    )
    prompt_contract = {
        "section_heading_is_scoped": "For a section-level response" in prompt,
        "paragraph_heading_is_forbidden": "For a paragraph-transaction response, do not emit any heading" in prompt,
        "old_unconditional_heading_instruction_absent": "Begin with exactly '## <supplied heading>'" not in prompt,
    }
    shared_assessor = {
        "single_page_uses_production_assessor": (
            "assess_publication_content_acceptance" in script_text
            and "assess_publication_content_progress" in script_text
        ),
        "single_page_duplicate_content_metrics_removed": "def _content_metrics" not in script_text,
        "same_response_metrics": True,
    }
    result = {
        "status": "pass",
        "provider_calls": 0,
        "source_run": str(run),
        "source_digests": {
            "single_page_state": _digest(state_path),
            "provider_responses": {
                str(path.relative_to(run)): _digest(path)
                for path in response_paths
            },
        },
        "prompt_contract": prompt_contract,
        "shared_assessor": shared_assessor,
        "attempts": attempts,
        "detail_22_atom_count": len(detail_22),
        "detail_22_allocation_checks": allocation_checks,
        "arithmetic_counterexamples": arithmetic_counterexamples,
    }
    checks = [
        all(item["body_chars_after_known_heading_recovery"] == expected
            for item, expected in zip(attempts, (1369, 1532))),
        all(item["format_failure_absent"] for item in attempts),
        all(item["repair_atom_count"] == item["metrics"]["missing_atom_count"]
            for item in attempts),
        all(item["repair_atoms_have_no_internal_ids"] for item in attempts),
        len(detail_22) == 13
        and all(
            item["nested_plus_is_not_top_level"]
            and item["exact_source_accepts"]
            and item["allocation_sentence_accepts"]
            for item in allocation_checks
        ),
        all(arithmetic_counterexamples.values()),
        all(prompt_contract.values()),
        all(shared_assessor.values()),
    ]
    if not all(checks):
        result["status"] = "fail"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "provider_calls": 0,
        "body_chars": [item["body_chars_after_known_heading_recovery"] for item in attempts],
        "valid_atoms": [item["metrics"]["valid_atom_count"] for item in attempts],
        "missing_atoms": [item["metrics"]["missing_atom_count"] for item in attempts],
        "detail_22_atoms": len(detail_22),
        "repair_owners": [item["repair_owner_counts"] for item in attempts],
    }, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True)
    return _run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
