"""B01 formula handoff through the production V2 Formalizer, without a model.

Only provider output is synthetic. The production executor owns parsing,
validation, package construction and receipt status. Golden receipt projections
omit clock observations explicitly; no receipt/digest is resealed by this fixture.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from code2paper.agentic.formalization_agent import (
    adapt_mechanism_formula_package_to_legacy,
    execute_formalizer_invocation_plan,
)
from code2paper.agentic.publication_transaction_contract import bind_paragraph_witnesses, splice_formula_placeholders
from code2paper.agentic.source_inventory import RepositorySourceEntryV1, RepositorySourceManifestV1
from code2paper.llm.client import LLMConfig, LLMProvider, LLMResponse

from . import legacy_fixture_builder as b

LATEX = "y = a * x"
SOURCE = Path(__file__).with_name("synthetic_rescale.py")


def _material():
    span = "span:fixtures/synthetic_rescale.py:4:5"
    operation = b.EvidenceOperationV1(
        operation_id="op:rescale", predicate="*", operands=("a", "x"), result="y",
        source_span_id=span, source_kind="first_party_executable",
        active_path_status="active_default",
    )
    detail = b.MechanismDetailV1(
        detail_id="d:rescale", primary_mechanism_id="mech_rescale", order_index=0,
        role="transformation", importance="core", claim_kind="formalization",
        evidence_authority="repository_verified", source_kind="first_party_executable",
        publication_policy="clean_candidate", semantic_atom=b._DETAIL_ANCHOR,
        predicate="*", operands=("a", "x"), result="y", formalizable=True,
        active_path_status="active_default", source_operation_ids=(operation.operation_id,), source_span_ids=(span,),
        witness_atoms=(b.DetailWitnessAtomV1(
            atom_id="atom:rescale", atom_kind="operation", semantic_anchor=b._DETAIL_ANCHOR,
            source_operation_ids=(operation.operation_id,), exact_excerpts=("return a * x",),
        ),),
    )
    context = b.MechanismContextV1(
        mechanism_id="mech_rescale", mechanism_name="Rescale mechanism",
        scientific_role="core_model", reader_question="How is the input rescaled?",
        purpose="Explain scalar rescaling.", importance="core",
        evidence_closure=b.MechanismEvidenceClosureV1(
            closure_id="closure:mech_rescale", mechanism_id="mech_rescale",
            operation_nodes=(operation,), exact_span_ids=(span,),
            operation_dispositions=(b.SourceOperationDispositionV1(
                operation_id=operation.operation_id, disposition="absorbed_by_detail",
                detail_ids=(detail.detail_id,),
            ),), source_operation_terminal_coverage=1.0,
        ), ordered_detail_ids=(detail.detail_id,), details=(detail,),
    )
    source_digest = b._sha256(SOURCE.read_bytes())
    context_set = b.MechanismContextSetV1(
        repo_snapshot_id="repo:b01-formula-synthetic", project_tree_hash=source_digest,
        intent_digest="sha256:b01-intent", alignment_digest="sha256:b01-alignment",
        research_digest="sha256:b01-research", contexts=(context,),
    )
    source_manifest = RepositorySourceManifestV1(
        repo_snapshot_id=context_set.repo_snapshot_id, project_tree_hash=source_digest,
        entries=(RepositorySourceEntryV1(
            path="fixtures/synthetic_rescale.py", source_kind="first_party_executable",
            ownership_role="target_core", executable_authority=True, content_digest=source_digest,
            classification_reason="synthetic fixture source, not a researched product claim",
        ),), target_core_paths=("fixtures/synthetic_rescale.py",),
    )
    archive = b.build_unified_context_archive_v2(
        context_set, source_manifest_digest=source_manifest.content_digest, source_manifest=source_manifest,
    )
    obligation = b.MechanismFormulaObligationV1(
        obligation_id="ob:rescale", mechanism_id="mech_rescale",
        source_detail_ids=(detail.detail_id,), source_operation_ids=(operation.operation_id,),
        mathematical_goal="Express scalar rescaling, preserving multiplication and both operands.",
        required_operator_signatures=({"predicate": "*"},), required_operand_sets=(("a", "x"),),
        source_equation_expression=LATEX, source_context_digest=context.source_context_digest,
    )
    return archive, obligation, source_digest, source_manifest


def build_fixture(*, response_mutation: str = "", evidence_root: str | Path | None = None, material_sink: dict[str, Any] | None = None, require_atom_targets: bool = False, readable_atom_targets: bool = False, budget_envelope: Any = None) -> dict[str, Any]:
    if readable_atom_targets and not require_atom_targets:
        raise ValueError("readable atom targets require the full atom contract")
    archive, obligation, source_digest, source_manifest = _material()
    envelope = budget_envelope if budget_envelope is not None else b._budget_envelope()
    manifest = b.build_consumer_workset_manifest_v2(
        archive, {"mech_rescale": (obligation,)},
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    plan = b.build_consumer_invocation_plan_v1(
        manifest, envelope, phase="formalizer", max_attempts=1,
        profile_digest=envelope.profile_digest, model_identity_digest=envelope.model_identity_digest,
        model_context_tokens=131072,
    )
    calls: list[dict[str, Any]] = []

    def provider(_config, request):
        row = {
            "obligation_id": obligation.obligation_id, "latex": LATEX,
            "prose_explanation": "The output y is the scalar a times the input x.",
            "symbol_definitions": [["y", "rescaled output"], ["a", "scalar factor"], ["x", "input"]],
            "material_conditions": [], "assumptions": [],
        }
        if response_mutation == "wrong_operator":
            row["latex"] = "y = a + x"
        elif response_mutation == "missing_obligation":
            row["obligation_id"] = "ob:unplanned"
        elif response_mutation == "unknown_field":
            row["accepted"] = True
        elif response_mutation:
            raise ValueError(response_mutation)
        raw = json.dumps({"results": [row]}, ensure_ascii=False)
        calls.append({
            "prompt_template_id": request.prompt_template_id,
            "input_payload": request.input_payload, "response_schema": request.response_json_schema,
            "response_text": raw, "response_sha256": b._sha256(raw.encode()),
        })
        return LLMResponse(text=raw, response_hash=b._sha256(raw.encode()), finish_reason="stop")

    execution = execute_formalizer_invocation_plan(
        plan=plan, workset_manifest=manifest, archive=archive,
        obligations_by_id={obligation.obligation_id: obligation},
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="b01-offline", max_output_tokens=4096, cache=False),
        caller=provider, max_attempts=1, budget_envelope=envelope,
        model_identity_digest=envelope.model_identity_digest, run_digest=archive.content_digest,
    )
    if evidence_root is not None:
        evidence = Path(evidence_root)
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "formalizer_execution.json").write_text(execution.model_dump_json(indent=2) + "\n")
        (evidence / "formalizer_provider_observations.json").write_bytes(b.golden_bytes(calls))
    # A stable observation of the real receipt is not a replacement receipt.
    omitted = {"started_at_unix", "finished_at_unix", "content_digest"}
    formalizer = {
        "accepted_package_count": len(execution.accepted_packages),
        "accepted_packages": [p.model_dump(mode="json") for p in execution.accepted_packages],
        "receipts": [{k: v for k, v in receipt.items() if k not in omitted} for receipt in execution.receipts],
        "receipt_projection_omitted_fields": sorted(omitted),
        "receipt_projection_is_not_a_durable_receipt": True,
        "actual_main_calls": execution.actual_main_calls, "actual_repair_calls": execution.actual_repair_calls,
        "task_failures": list(execution.task_failures), "assertion_failures": list(execution.assertion_failures),
        "calls": calls, "obligation": obligation.model_dump(mode="json"),
    }
    result = {"schema_version": b.FIXTURE_SCHEMA_VERSION, "scenario": "completed_formalizer_page",
              "source": {"path": "fixtures/synthetic_rescale.py", "sha256": source_digest,
                         "exact_excerpt": SOURCE.read_text(), "authority": "synthetic_fixture_only",
                         "manifest": source_manifest.model_dump(mode="json")},
              "formalizer": formalizer, "writer": None}
    if not execution.accepted_packages:
        return result
    assert not execution.task_failures and not execution.assertion_failures
    package, = execution.accepted_packages
    section_package = adapt_mechanism_formula_package_to_legacy(
        package, section_id=b.LEGAL_SECTION_ID, consumer_paragraph_id=f"{b.LEGAL_SECTION_ID}_p1",
    )
    narrative_data = b._narrative_plan(archive).model_dump(mode="json")
    narrative_data.pop("content_digest", None)
    narrative_data["sections"] = narrative_data["sections"][:1]
    narrative_data["narrative_units"] = narrative_data["narrative_units"][:1]
    for row in [narrative_data["sections"][0], narrative_data["sections"][0]["paragraphs"][0], narrative_data["narrative_units"][0]]:
        row.pop("content_digest", None)
    paragraph = narrative_data["sections"][0]["paragraphs"][0]
    paragraph["formula_obligation_ids"] = [obligation.obligation_id]
    paragraph["formula_package_ids"] = [package.package_id]
    narrative_data["narrative_units"][0]["formula_obligation_ids"] = [obligation.obligation_id]
    if require_atom_targets:
        # Ownership comes from the frozen source archive, not a Writer claim.
        # The accepted Formalizer explanation is already source-validated and
        # visible in its package; it supplies reader wording for the live
        # fixture without asking a Writer to reproduce an internal graph id.
        targets = []
        for archived_detail in archive.detail_atoms:
            detail = archived_detail.payload
            if detail["detail_id"] not in paragraph["required_detail_ids"]:
                continue
            if readable_atom_targets:
                targets.append({
                    "target_id": detail["detail_id"], "target_kind": "detail",
                    "detail_id": detail["detail_id"],
                    "semantic_atom": package.prose_explanation,
                    "paper_role": detail["role"],
                    "allowed_exact_excerpts": [excerpt for atom in detail["witness_atoms"] for excerpt in atom["exact_excerpts"]],
                    "allowed_anchor_ids": list(detail["source_span_ids"]),
                    "authority_lane": "executable_hard", "render_policy": "required",
                })
            for atom in detail["witness_atoms"]:
                if readable_atom_targets:
                    assert section_package.authority_status == "code_verified"
                    assert detail["detail_id"] in package.source_detail_ids
                    assert set(atom["source_operation_ids"]).issubset(package.bound_operation_ids)
                targets.append({
                    "target_id": atom["atom_id"], "target_kind": "atom",
                    "detail_id": detail["detail_id"],
                    "semantic_atom": package.prose_explanation if readable_atom_targets else atom["semantic_anchor"],
                    "paper_role": atom["atom_kind"],
                    "allowed_exact_excerpts": list(atom["exact_excerpts"]),
                    "allowed_anchor_ids": list(detail["source_span_ids"]),
                    "authority_lane": "executable_hard", "render_policy": "required",
                })
        assert targets
        paragraph["witness_contract"]["targets"] = targets
    narrative = b.NarrativePlanV3.model_validate(narrative_data)
    writer_manifest = b.extend_writer_worksets_from_narrative_plan(
        manifest, narrative, archive=archive, max_page_input_tokens=envelope.max_page_input_tokens,
        formula_packages=(section_package,), formula_obligations=(obligation,),
    )
    writer_plan = b.build_consumer_invocation_plan_v1(
        writer_manifest, envelope, phase="writer", max_attempts=1,
        profile_digest=envelope.profile_digest, model_identity_digest=envelope.model_identity_digest,
        model_context_tokens=131072,
    )
    section, = b._writer_section_inputs_v2(
        narrative_plan=narrative, formula_packages=(section_package,), formula_obligations=(obligation,),
        consumer_workset_manifest=writer_manifest, consumer_invocation_plan=writer_plan,
    )
    request = b.build_publication_writer_request(
        section, system_prompt=section.system_prompt, schema_name=b.SCHEMA_NAME,
        response_json_schema=b.consumer_response_json_schema("writer", section_id=section.section_id),
    )
    # The provider authors a placeholder. Only the original splice owns the formula bytes.
    raw_payload = json.loads(b.offline_provider_response(section, request).text)
    item = raw_payload["paragraphs"][0]
    item["paragraph_markdown"] += "\n\n[[FORMULA:" + package.package_id + "]]"
    item["used_formula_package_ids"] = [package.package_id]
    raw_payload["section_markdown"] = item["paragraph_markdown"]
    writer_raw = json.dumps(raw_payload, ensure_ascii=False)
    bound_payload = copy.deepcopy(raw_payload)
    witnesses: list[dict[str, str]] = []
    rendered, failures = splice_formula_placeholders(
        item["paragraph_markdown"], (section_package,), required_package_ids=(package.package_id,),
        allowed_package_ids=(package.package_id,), witness_sink=witnesses,
    )
    assert not failures, failures
    bound_payload["paragraphs"][0]["paragraph_markdown"] = rendered
    bound_payload["paragraphs"][0]["witnesses"].extend(witnesses)
    bound_payload["section_markdown"] = rendered
    bound_payload["paragraphs"][0] = bind_paragraph_witnesses(
        bound_payload["paragraphs"][0], plan_row=b._page_paragraph_rows(section)[0],
        formula_packages=tuple(section.prompt_payload["formula_packages"]),
    )
    bound_text = json.dumps(bound_payload, ensure_ascii=False)
    response = LLMResponse(text=bound_text, response_hash=b._sha256(bound_text.encode()), finish_reason="stop")
    page = next(p for p in writer_manifest.pages if p.page_id == section.prompt_payload["unified_v2_page_id"])
    invocation = next(i for i in writer_plan.invocations if i.page_id == page.page_id and not i.is_repair)
    result["writer"] = b._page_fixture(
        section=section, request=request, response_schema=request.response_json_schema,
        invocation=invocation, page=page, scenario="completed_formalizer_page", provider_response=response,
    )
    if material_sink is not None:
        material_sink.update(section=section, request=request, page=page, narrative=narrative,
                             manifest=writer_manifest, plan=writer_plan, formalizer=execution,
                             writer_raw=writer_raw, archive=archive, budget_envelope=envelope)
    result["writer"]["formula_consumption"] = {
        "raw_writer_text": writer_raw, "splice_owner": "publication_transaction_contract.splice_formula_placeholders",
        "splice_failures": list(failures), "derived_formula_witnesses": witnesses,
        "formalizer_package_digest": package.content_digest,
        "offline_response_text_origin": "local representation after original splice and Binder; not provider raw",
        "raw_writer_sha256": b._sha256(writer_raw.encode()),
        "rendered_response_sha256": b._sha256(bound_text.encode()),
    }
    return result
