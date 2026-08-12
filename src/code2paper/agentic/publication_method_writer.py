"""Production orchestration for the publication-ready Method Writer."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    load_atomic_claims_v3,
    load_code_facts_v1,
    load_evidence_packets_v3,
)
from code2paper.agentic.authoring_projection import build_authoring_projection
from code2paper.agentic.trust_contracts import AuthorAttestedFragment, AuthoringInputProjection
from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.equation_claims import EquationClaimSetV1, load_equation_claims
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.final_text_claims import (
    classify_final_text_unit_lanes,
    extract_final_text_claims,
    load_final_text_claims,
    write_final_text_claims,
)
from code2paper.agentic.final_text_authorship import (
    GeneratedTextSpanV1,
    build_final_text_authorship_ledger,
    rewrite_final_text_authorship_ledger,
)
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
from code2paper.agentic.cross_section_editor import CrossSectionEditor
from code2paper.agentic.publication_quality import (
    _claim_rendered_in,
    _content_tokens,
    _configuration_rendered,
    _duplicate_rate,
    _equation_rendered,
    _move_witness_span,
    _section_editable,
    evaluate_publication_method_quality,
    find_code_trace_prose_sections,
)
from code2paper.agentic.formalization_agent import (
    FormalizationProposalItemV1,
    FormalizationProposalV1,
    FormalizationResultV1,
    FormalizationRiskV1,
    _binding_concrete_expression,
    formalize_code_facts,
    validate_formalization_proposal,
)
from code2paper.agentic.rewrite_agent import (
    LocalRewriteAgent,
    LocalRewritePatchV1,
    RepairTransitionV1,
)
from code2paper.agentic.text_repair_supervisor import derive_repair_issues
from code2paper.agentic.research_models import TextRepairIssueV1
from code2paper.agentic.tool_runtime import atomic_write_bytes
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
    MoveAuthorityProofV1,
    ReferenceMethodAgendaV1,
    WritingResearchRequestV1,
    WritingResearchCallbackArtifactV1,
    WritingResearchCallbackBundleV1,
)
from code2paper.agentic.method_product_models import (
    MethodDraftBundleV1,
    MethodOutputPolicyV1,
    MethodPlanProductReadinessV1,
    MethodReviewCandidateV1,
    assess_plan_product_readiness,
    build_default_method_output_policy,
    build_review_candidates_from_completeness,
    extract_code_binding_terms,
    method_lane_from_reference_status,
)
from code2paper.agentic.text_evidence_validator import (
    build_repository_verified_text,
    load_text_evidence_validation,
    validate_text_evidence,
    write_text_evidence_validation,
)
from code2paper.agentic.writer_research_router import (
    ExternalResearchQueueItemV1,
    build_external_research_queue_items,
    build_review_candidates_from_requests,
    route_writing_research_requests,
)
from code2paper.core.output_names import method_output
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1
from code2paper.llm.section_writer import (
    WriterSectionInput,
    write_publication_method_by_sections,
)
from code2paper.schemas import ClaimEvidenceMap, LLMConfig, MethodEvidence, RawEvidencePack


_ORGANIZATION_ONLY_RHETORICAL_MOVES = frozenset({
    "problem_or_local_context",
    "design_objective",
    "intuition_or_rationale",
    "transition_to_next_section",
})

_LOCALLY_OWNED_LANES = frozenset({
    "executable_hard",
    "configuration_resolved",
    "formal_derivation",
})


class PublicationWriterRunResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    status: Literal["success", "incomplete", "blocked"]
    plan_digest: str
    claim_digest: str
    section_results: tuple[dict[str, Any], ...] = ()
    accepted_section_ids: tuple[str, ...] = ()
    incomplete_section_ids: tuple[str, ...] = ()
    binding_failures: tuple[str, ...] = ()
    writer_aggregate: dict[str, Any] = Field(default_factory=dict)
    response_recovery_traces: tuple[dict[str, Any], ...] = ()
    final_text_digest: str = ""
    authorship_ledger_digest: str = ""
    publication_quality_digest: str = ""
    rewrite_transition_digest: str = ""
    callback_bundle_digest: str = ""
    resumed_section_ids: tuple[str, ...] = ()
    blocked_reason: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "PublicationWriterRunResultV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest_json(payload))
        return self


def run_publication_method_writer(
    *,
    out_root: str | Path,
    artifact_paths: dict[str, str],
    llm_config: LLMConfig,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    resume_section_ids: tuple[str, ...] = (),
    research_callback_artifacts: dict[str, tuple[Any, ...]] | None = None,
    editor_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    rewrite_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    formalization_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    architect_proposal_caller: Callable[..., str | None] | None = None,
    rebuild_architect_plan: bool = False,
) -> tuple[PublicationWriterRunResultV1, dict[str, str]]:
    """Write section-scoped Method prose from the multi-authority plan."""

    required = (
        "atomic_claims_v3",
        "code_facts_v1",
        "equation_claims_v1",
        "configuration_claims_v1",
        "method_completeness_matrix_v1",
        "method_section_plan_v2",
    )
    missing = [key for key in required if not artifact_paths.get(key) or not Path(artifact_paths[key]).is_file()]
    if missing:
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest="",
            claim_digest="",
            blocked_reason="publication_writer_inputs_missing:" + ",".join(missing),
        )
        return result, _write_result_only(out_root, result)

    try:
        claims = load_atomic_claims_v3(artifact_paths["atomic_claims_v3"])
        facts = load_code_facts_v1(artifact_paths["code_facts_v1"])
        equations = load_equation_claims(artifact_paths["equation_claims_v1"])
        evidence_packets_v3 = None
        packet_value = artifact_paths.get("evidence_packets_v3", "")
        if packet_value and Path(packet_value).is_file():
            evidence_packets_v3 = load_evidence_packets_v3(packet_value)
        configurations = ConfigurationClaimSetV1.model_validate_json(
            Path(artifact_paths["configuration_claims_v1"]).read_text(encoding="utf-8")
        )
        completeness = MethodCompletenessMatrixV1.model_validate_json(
            Path(artifact_paths["method_completeness_matrix_v1"]).read_text(encoding="utf-8")
        )
        plan = MethodSectionPlanV2.model_validate_json(
            Path(artifact_paths["method_section_plan_v2"]).read_text(encoding="utf-8")
        )
        agenda = None
        agenda_value = artifact_paths.get("reference_method_agenda_v1", "")
        if agenda_value and Path(agenda_value).is_file():
            agenda = ReferenceMethodAgendaV1.model_validate_json(
                Path(agenda_value).read_text(encoding="utf-8")
            )
        coverage_by_obligation: dict[str, tuple[str, ...]] = {}
        coverage_value = artifact_paths.get("obligation_coverage_v2", "")
        if coverage_value and Path(coverage_value).is_file():
            coverage_doc = json.loads(Path(coverage_value).read_text(encoding="utf-8"))
            coverage_by_obligation = {
                str(item.get("obligation_id") or ""): tuple(
                    str(fact_id)
                    for target in item.get("target_alignments") or ()
                    for fact_id in target.get("matched_fact_ids") or ()
                )
                for item in coverage_doc.get("items") or ()
                if item.get("obligation_id")
            }
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        # A corrupt frozen input is an integrity failure.  Keep the failure
        # typed and durable so a LangGraph stage can stop without exposing a
        # stale candidate from an earlier run in the same output directory.
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest="",
            claim_digest="",
            blocked_reason=(
                "publication_writer_inputs_invalid:"
                f"{exc.__class__.__name__}:{str(exc)[:240]}"
            ),
        )
        return result, _write_result_only(out_root, result)
    if not plan.sections or not plan.argument_units:
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            blocked_reason="publication_method_plan_has_no_supported_sections",
        )
        return result, _write_result_only(out_root, result)

    architect_trace_path = ""
    if rebuild_architect_plan or not any(
        unit.semantic_frame is not None for unit in plan.argument_units
    ):
        # The tracked matrix consumes the prebuilt frozen plan as the
        # planning authority.  The Architect must still be a real, traceable
        # decision path for the final milestone: re-derive each unit's
        # typed semantic frame, obligation placements, and move authority on
        # the frozen section/unit structure and persist the decision trace.
        # A plan that lacks typed frames (legacy builder output) is upgraded
        # automatically because the Writer now consumes only the typed frame.
        from code2paper.agentic.method_architect import replan_moves_with_trace

        plan, architect_trace = replan_moves_with_trace(
            base_plan=plan,
            claims=claims,
            equations=equations,
            configurations=configurations,
            completeness=completeness,
            facts=facts,
            evidence_packets_v3=evidence_packets_v3,
            agenda=agenda,
            coverage_by_obligation=coverage_by_obligation,
            proposal_caller=architect_proposal_caller,
        )
        architect_trace_path = str(method_output(Path(out_root), "method_architect_trace_v1"))
        _atomic_write_text(
            architect_trace_path,
            json.dumps(architect_trace, ensure_ascii=False, indent=2) + "\n",
        )

    # Product-level plan readiness (A4/D contract): ordinary unplaced /
    # external / partial obligations NEVER block candidate generation.  They
    # become review items (verified excluded).  The only pre-Writer block is
    # ``blocked_for_safety``: an unsupported positive could be written
    # without any caveat route.  Exact placement / move-authority / semantic
    # frame closure are audit warnings, not candidate gates.
    readiness = assess_plan_product_readiness(
        plan=plan,
        completeness=completeness,
        claims=claims,
    )
    if readiness.readiness == "blocked_for_safety":
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            blocked_reason=(
                "plan_blocked_for_safety:"
                + ",".join(readiness.blocked_for_safety_reasons or ("unsupported_positive_risk",))
            ),
        )
        return result, _write_result_only(out_root, result)

    formalization = formalize_code_facts(facts=facts, equations=equations)
    formalization_path = method_output(Path(out_root), "formalization_result_v1")
    _atomic_write_text(formalization_path, formalization.model_dump_json(indent=2) + "\n")
    formalization_agent_path = ""
    if formalization_caller is not None:
        formalization, formalization_agent_result = _run_formalization_agent(
            base=formalization,
            facts=facts,
            equations=equations,
            config=llm_config,
            caller=formalization_caller,
            out_root=out_root,
        )
        formalization_agent_path = str(
            method_output(Path(out_root), "formalization_agent_result_v1")
        )
        _atomic_write_text(
            formalization_agent_path,
            json.dumps(formalization_agent_result, ensure_ascii=False, indent=2) + "\n",
        )
        _atomic_write_text(formalization_path, formalization.model_dump_json(indent=2) + "\n")

    effective_resume_section_ids = tuple(resume_section_ids)
    callback_bundle = _load_callback_bundle(artifact_paths)
    callback_bundle_value = artifact_paths.get(
        "writing_research_callback_artifacts_v1", ""
    )
    if callback_bundle_value and callback_bundle is None:
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            blocked_reason="writing_research_callback_bundle_invalid",
        )
        return result, _write_result_only(out_root, result)
    raw_callback_artifacts = (
        dict(callback_bundle.artifacts) if callback_bundle is not None else {}
    )
    if research_callback_artifacts is not None:
        # An explicit owner response may add/replace only the request IDs it
        # names; preserve the rest of a persisted bundle for the same resume.
        raw_callback_artifacts.update(research_callback_artifacts)
    if callback_bundle is not None and not effective_resume_section_ids:
        effective_resume_section_ids = callback_bundle.resume_section_ids
    prior_outputs, prior_response_refs = _load_section_checkpoint(
        out_root=out_root,
        artifact_paths=artifact_paths,
        resume_section_ids=effective_resume_section_ids,
    )
    if effective_resume_section_ids and prior_outputs is None:
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            resumed_section_ids=_pre_writer_resumed_section_ids(effective_resume_section_ids),
            blocked_reason="publication_section_checkpoint_missing_or_invalid",
        )
        return result, _write_result_only(out_root, result)
    raw_callback_artifacts = raw_callback_artifacts or {}
    callback_artifacts: dict[str, tuple[WritingResearchCallbackArtifactV1, ...]] = {}
    try:
        callback_artifacts = {
            request_id: tuple(
                item if isinstance(item, WritingResearchCallbackArtifactV1)
                else WritingResearchCallbackArtifactV1.model_validate(item)
                for item in items
            )
            for request_id, items in raw_callback_artifacts.items()
        }
    except (TypeError, ValueError) as exc:
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            resumed_section_ids=_pre_writer_resumed_section_ids(effective_resume_section_ids),
            blocked_reason=(
                "writing_research_callback_artifacts_invalid:"
                f"{exc.__class__.__name__}:{str(exc)[:160]}"
            ),
        )
        return result, _write_result_only(out_root, result)
    if callback_artifacts:
        known_request_ids: set[str] = set()
        if callback_bundle is not None:
            known_request_ids.update(item.request_id for item in callback_bundle.requests)
        for prior in (prior_outputs or {}).values():
            for raw_request in prior.new_research_requests:
                try:
                    known_request_ids.add(
                        WritingResearchRequestV1.model_validate(raw_request).request_id
                    )
                except ValueError:
                    continue
        unknown_request_ids = sorted(set(callback_artifacts) - known_request_ids)
        if unknown_request_ids:
            result = PublicationWriterRunResultV1(
                status="blocked",
                plan_digest=plan.content_digest,
                claim_digest=claims.content_digest,
                resumed_section_ids=_pre_writer_resumed_section_ids(effective_resume_section_ids),
                blocked_reason=(
                    "writing_research_callback_artifacts_unbound:"
                    + ",".join(unknown_request_ids)
                ),
            )
            return result, _write_result_only(out_root, result)
    try:
        writer_inputs = _writer_section_inputs(
            plan=plan,
            claims=claims,
            equations=equations,
            configurations=configurations,
            formalization=formalization,
            facts=facts,
            evidence_packets_v3=evidence_packets_v3,
            callback_bundle=callback_bundle,
            callback_artifacts=callback_artifacts,
        )
    except ValueError as exc:
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            resumed_section_ids=_pre_writer_resumed_section_ids(effective_resume_section_ids),
            blocked_reason=f"move_authority_callback_binding_invalid:{str(exc)[:240]}",
        )
        return result, _write_result_only(out_root, result)
    if effective_resume_section_ids:
        unresolved_callback_ids: list[str] = []
        for section_id in effective_resume_section_ids:
            prior = (prior_outputs or {}).get(section_id)
            for raw_request in (prior.new_research_requests if prior is not None else ()):
                try:
                    request = WritingResearchRequestV1.model_validate(raw_request)
                except ValueError:
                    unresolved_callback_ids.append("invalid_request")
                    continue
                # Only blocking locally owned requests gate the resume;
                # external-pending rows stay pending and never block Writer
                # regeneration of the affected section.
                if request.required_authority_lane not in _LOCALLY_OWNED_LANES:
                    continue
                artifacts_for_request = callback_artifacts.get(request.request_id, ())
                if not artifacts_for_request or not all(
                    artifact.request_id == request.request_id
                    and artifact.section_id == request.section_id
                    and artifact.argument_unit_id == request.argument_unit_id
                    and artifact.authority_lane == request.required_authority_lane
                    for artifact in artifacts_for_request
                ):
                    unresolved_callback_ids.append(request.request_id)
        if unresolved_callback_ids:
            result = PublicationWriterRunResultV1(
                status="blocked",
                plan_digest=plan.content_digest,
                claim_digest=claims.content_digest,
                resumed_section_ids=_pre_writer_resumed_section_ids(effective_resume_section_ids),
                blocked_reason=(
                    "writing_research_callback_artifacts_missing:"
                    + ",".join(sorted(set(unresolved_callback_ids)))
                ),
            )
            return result, _write_result_only(out_root, result)
    selected_inputs = (
        [item for item in writer_inputs if item.section_id in set(effective_resume_section_ids)]
        if effective_resume_section_ids else writer_inputs
    )
    if effective_resume_section_ids:
        resume_section_set = set(effective_resume_section_ids)
        callback_reference_base = (
            Path(callback_bundle_value).expanduser().resolve().parent
            if callback_bundle_value
            else Path(out_root).expanduser().resolve()
        )
        callback_prompt_payloads: dict[str, list[dict[str, Any]]] = {}
        callback_reference_failures: list[str] = []
        for request_id, artifacts in callback_artifacts.items():
            payloads: list[dict[str, Any]] = []
            for artifact in artifacts:
                payload, failure = _callback_artifact_prompt_payload(
                    artifact,
                    base_dir=callback_reference_base,
                )
                if failure:
                    callback_reference_failures.append(
                        f"{request_id}:{failure}"
                    )
                payloads.append(payload)
            callback_prompt_payloads[request_id] = payloads
        if callback_reference_failures:
            result = PublicationWriterRunResultV1(
                status="blocked",
                plan_digest=plan.content_digest,
                claim_digest=claims.content_digest,
                resumed_section_ids=_pre_writer_resumed_section_ids(effective_resume_section_ids),
                blocked_reason=(
                    "writing_research_callback_artifact_integrity_failed:"
                    + ";".join(sorted(callback_reference_failures))
                ),
            )
            return result, _write_result_only(out_root, result)
        callback_resolution_by_section: dict[str, dict[str, Any]] = {}
        callback_requests_by_id = {
            item.request_id: item
            for item in (callback_bundle.requests if callback_bundle is not None else ())
        }
        for request_id, artifacts in callback_artifacts.items():
            request = callback_requests_by_id.get(request_id)
            if request is None or request.status != "fulfilled":
                continue
            section_resolution = callback_resolution_by_section.setdefault(
                request.section_id,
                {
                    "fulfilled_requests": [],
                    "fulfilled_moves": [],
                    "instruction": (
                        "The owning authority has already validated these callback artifacts. "
                        "Use the artifact preview for the listed move, include that move in "
                        "completed_rhetorical_moves, and do not emit a new research request "
                        "for a fulfilled move."
                    ),
                },
            )
            section_resolution["fulfilled_requests"].append(request_id)
            section_resolution["fulfilled_moves"].append({
                "move": request.missing_rhetorical_move,
                "argument_unit_id": request.argument_unit_id,
                "authority_lane": request.required_authority_lane,
            })
        selected_inputs = [
            item.__class__(
                section_id=item.section_id,
                heading=item.heading,
                prompt_payload={
                    **item.prompt_payload,
                    "writing_research_callback_artifacts": {
                        request_id: callback_prompt_payloads.get(request_id, [])
                        for request_id, artifacts in callback_artifacts.items()
                        if item.section_id in resume_section_set
                        and any(
                            artifact.section_id == item.section_id
                            for artifact in artifacts
                        )
                    },
                    "writing_research_callback_resolution": callback_resolution_by_section.get(
                        item.section_id,
                        {
                            "fulfilled_requests": [],
                            "fulfilled_moves": [],
                            "instruction": (
                                "No callback artifact is fulfilled for this section."
                            ),
                        },
                    ),
                },
                system_prompt=item.system_prompt,
                publication_mode=item.publication_mode,
                argument_graph=item.argument_graph,
            )
            for item in selected_inputs
        ]
    writer = write_publication_method_by_sections(
        llm_config,
        selected_inputs,
        llm_caller=llm_caller,
    )
    output_by_section = dict(prior_outputs or {})
    for section_id in effective_resume_section_ids:
        output_by_section.pop(section_id, None)
    output_by_section.update({item.section_id: item for item in writer.outputs})
    aggregate_by_section = {item.section_id: item for item in writer.aggregate.sections}
    unit_by_id = {item.argument_unit_id: item for item in plan.argument_units}
    authority_proofs = plan.proofs_by_key()
    accepted: list[tuple[str, str, str]] = []
    failures: list[str] = []
    section_rows: list[dict[str, Any]] = []
    research_requests: list[WritingResearchRequestV1] = []
    fulfilled_callback_bindings: dict[str, set[tuple[str, str]]] = {}
    if callback_bundle is not None:
        callback_requests_by_id = {
            item.request_id: item for item in callback_bundle.requests
        }
        for request_id, artifacts in callback_artifacts.items():
            request = callback_requests_by_id.get(request_id)
            if request is None or request.status != "fulfilled" or not artifacts:
                continue
            fulfilled_callback_bindings.setdefault(request.section_id, set()).add(
                (request.missing_rhetorical_move, request.argument_unit_id)
            )
    callback_recovery_traces: list[dict[str, Any]] = []
    retry_inputs: list[WriterSectionInput] = []
    retry_missing_by_section: dict[str, tuple[str, ...]] = {}
    input_by_section = {item.section_id: item for item in selected_inputs}
    for graph in plan.sections:
        output = output_by_section.get(graph.section_id)
        original_input = input_by_section.get(graph.section_id)
        if output is None or original_input is None:
            continue
        _recovered, _emitted, _dropped, missing_moves = _recover_missing_writing_callbacks(
            output=output,
            graph=graph,
            unit_by_id=unit_by_id,
            authority_proofs=authority_proofs,
        )
        if not missing_moves:
            continue
        retry_missing_by_section[graph.section_id] = missing_moves
        retry_inputs.append(WriterSectionInput(
            section_id=original_input.section_id,
            heading=original_input.heading,
            prompt_payload={
                **original_input.prompt_payload,
                "previous_attempt_error": (
                    "publication_section_binding_failed:"
                    "missing_writing_research_callback:"
                    + ",".join(missing_moves)
                ),
                "previous_attempt_section_markdown": output.section_markdown[:6000],
                "callback_owner_retry_instruction": {
                    "reason": (
                        "The previous Writer response left one or more "
                        "unanchored required moves without a scoped "
                        "new_research_requests entry."
                    ),
                    "missing_moves": list(missing_moves),
                    "required_action": (
                        "Regenerate this same section. Keep completed_rhetorical_moves "
                        "limited to anchored moves, leave the missing move unresolved, "
                        "and emit the matching object from "
                        "grounding_contract.callback_request_prototypes with a precise "
                        "exact_question."
                    ),
                },
            },
            system_prompt=original_input.system_prompt,
            publication_mode=original_input.publication_mode,
            argument_graph=original_input.argument_graph,
        ))
    if retry_inputs:
        retry_writer = write_publication_method_by_sections(
            llm_config,
            retry_inputs,
            llm_caller=llm_caller,
            call_id_prefix="LLM-publication-method-section-callback-retry",
        )
        writer.aggregate.traces.extend(retry_writer.aggregate.traces)
        writer.aggregate.response_recovery_traces.extend(
            retry_writer.aggregate.response_recovery_traces
        )
        retry_outputs = {item.section_id: item for item in retry_writer.outputs}
        retry_aggregate = {
            item.section_id: item for item in retry_writer.aggregate.sections
        }
        replaced_sections: list[str] = []
        for graph in plan.sections:
            retry_output = retry_outputs.get(graph.section_id)
            if retry_output is None:
                continue
            retry_output, emitted, dropped, missing_after = _recover_missing_writing_callbacks(
                output=retry_output,
                graph=graph,
                unit_by_id=unit_by_id,
                authority_proofs=authority_proofs,
            )
            original_missing = set(retry_missing_by_section.get(graph.section_id, ()))
            if not original_missing:
                continue
            if emitted or set(missing_after) < original_missing:
                output_by_section[graph.section_id] = retry_output
                if graph.section_id in retry_aggregate:
                    aggregate_by_section[graph.section_id] = retry_aggregate[graph.section_id]
                replaced_sections.append(graph.section_id)
                callback_recovery_traces.append({
                    "section_id": graph.section_id,
                    "applied": True,
                    "provenance": "writer_owner_retry",
                    "operations": [
                        "owner_retry_for_missing_writing_callback:"
                        + ",".join(retry_missing_by_section[graph.section_id]),
                        *(
                            [f"rejected_malformed_writing_research_request:{dropped}"]
                            if dropped else []
                        ),
                        *[
                            f"model_emitted_writing_callback:{item.missing_rhetorical_move}"
                            for item in emitted
                        ],
                    ],
                    "request_ids": [item.request_id for item in emitted],
                    "parsed_request_digests": [
                        item.content_digest for item in emitted
                    ],
                    "missing_request_moves_after_retry": list(missing_after),
                })
        if replaced_sections:
            outputs_by_id = {item.section_id: item for item in writer.outputs}
            outputs_by_id.update(
                {
                    section_id: output_by_section[section_id]
                    for section_id in replaced_sections
                    if section_id in output_by_section
                }
            )
            writer.outputs = [
                outputs_by_id[graph.section_id]
                for graph in plan.sections
                if graph.section_id in outputs_by_id
            ]
            sections_by_id = {
                item.section_id: item for item in writer.aggregate.sections
            }
            sections_by_id.update({
                section_id: aggregate_by_section[section_id]
                for section_id in replaced_sections
                if section_id in aggregate_by_section
            })
            writer.aggregate.sections = [
                sections_by_id[section.section_id]
                for section in writer.aggregate.sections
                if section.section_id in sections_by_id
            ]
            writer.aggregate.incomplete_sections = [
                section_id
                for section_id in writer.aggregate.incomplete_sections
                if section_id not in set(replaced_sections)
            ]
    # Callback existence and its semantic question are Writer-owned content.
    # The harness may reject malformed representations, but it must never
    # manufacture a request from an unanchored proof when the Writer emitted
    # none.  Doing so would turn a deterministic expectation into false live
    # callback evidence.
    for graph in plan.sections:
        output = output_by_section.get(graph.section_id)
        aggregate = aggregate_by_section.get(graph.section_id)
        if output is not None:
            output, emitted_requests, dropped_malformed, missing_moves = _recover_missing_writing_callbacks(
                output=output,
                graph=graph,
                unit_by_id=unit_by_id,
                authority_proofs=authority_proofs,
            )
            if dropped_malformed:
                output_by_section[graph.section_id] = output
            if emitted_requests or dropped_malformed or missing_moves:
                operations: list[str] = []
                if emitted_requests:
                    operations.extend(
                        f"model_emitted_writing_callback:{item.missing_rhetorical_move}"
                        for item in emitted_requests
                    )
                if dropped_malformed:
                    operations.append(
                        f"rejected_malformed_writing_research_request:{dropped_malformed}"
                    )
                operations.extend(
                    f"rejected_missing_writing_callback:{move_name}"
                    for move_name in missing_moves
                )
                callback_recovery_traces.append({
                    "section_id": graph.section_id,
                    "applied": False,
                    "provenance": (
                        "model_emitted" if emitted_requests and not dropped_malformed
                        and not missing_moves else "rejected_missing"
                    ),
                    "operations": operations,
                    "raw_response_hash": (
                        aggregate.trace.response_hash
                        if aggregate is not None and aggregate.trace is not None
                        else ""
                    ),
                    "request_ids": [item.request_id for item in emitted_requests],
                    "parsed_request_digests": [
                        item.content_digest for item in emitted_requests
                    ],
                    "dropped_malformed_requests": dropped_malformed,
                    "missing_request_moves": list(missing_moves),
                })
        allowed_units = {
            unit_id for unit_id in graph.argument_unit_ids if unit_id in unit_by_id
        }
        allowed_claims = {
            claim_id
            for unit_id in allowed_units
            for claim_id in unit_by_id[unit_id].claim_ids
        }
        required_equations = {
            equation_id
            for unit_id in allowed_units
            for equation_id in unit_by_id[unit_id].equation_ids
        }
        required_configurations = {
            configuration_id
            for unit_id in allowed_units
            for configuration_id in unit_by_id[unit_id].configuration_ids
        }
        section_failures: list[str] = []
        quality_failures: list[str] = []
        response_ref = (
            aggregate.trace.response_hash
            if aggregate is not None and aggregate.trace is not None
            else prior_response_refs.get(graph.section_id, "")
        )
        if output is None or not response_ref or (aggregate is not None and aggregate.incomplete):
            section_failures.append("writer_output_missing_or_incomplete")
            # The writer may have consumed its one bounded owner retry and
            # still hold a typed binding failure (e.g. a near-miss claim id
            # that failed the closed-set check at the writer boundary).
            # Surface the precise ``unknown_*``/``missing_*`` codes here so
            # the run-level binding-failure report and repair routing keep
            # seeing the actionable issue even when no output object exists.
            if aggregate is not None:
                blocked = str(aggregate.blocked_reason or "")
                prefix = "publication_section_binding_failed:"
                if blocked.startswith(prefix):
                    for code in blocked[len(prefix):].split(";"):
                        if code and any(
                            token in code for token in (
                                "unknown_argument_units", "missing_argument_units",
                                "unknown_claims", "missing_claims",
                                "unknown_equations", "missing_equations",
                                "unknown_configurations", "missing_configurations",
                            )
                        ):
                            section_failures.append(code)
        else:
            has_research_callbacks = bool(output.new_research_requests)
            for label, values in (
                ("argument_units", output.used_argument_unit_ids),
                ("claims", output.used_claim_ids),
                ("equations", output.used_equation_ids),
                ("configurations", output.used_configuration_ids),
            ):
                if len(values) != len(set(values)):
                    section_failures.append(f"duplicate_{label}")
            _require_exact_or_subset(
                section_failures,
                "argument_units",
                required=allowed_units,
                used=set(output.used_argument_unit_ids),
                allow_missing=has_research_callbacks,
            )
            _require_exact_or_subset(
                section_failures,
                "claims",
                required=allowed_claims,
                used=set(output.used_claim_ids),
                allow_missing=has_research_callbacks,
            )
            _require_exact_or_subset(
                section_failures,
                "equations",
                required=required_equations,
                used=set(output.used_equation_ids),
                allow_missing=has_research_callbacks,
            )
            _require_exact_or_subset(
                section_failures,
                "configurations",
                required=required_configurations,
                used=set(output.used_configuration_ids),
                allow_missing=has_research_callbacks,
            )
            # Declared-use is a proposal, not proof.  A section that binds a
            # claim/equation/configuration id must render that content in its
            # own authored bytes.  An unrendered declared id is a utility
            # failure (fail closed on publication), while the final reverse
            # validator remains the epistemic-safety authority on the prose.
            claim_objects = {item.claim_id: item for item in claims.claims}
            equation_objects = {
                item.equation_id: item for item in equations.equations
            }
            configuration_objects = {
                item.configuration_id: item for item in configurations.claims
            }
            unrendered_claims = [
                claim_id for claim_id in output.used_claim_ids
                if claim_id in claim_objects
                and not _claim_rendered_in(output.section_markdown, claim_objects[claim_id])
            ]
            unrendered_equations = [
                equation_id for equation_id in output.used_equation_ids
                if equation_id in equation_objects
                and not _equation_rendered(output.section_markdown, equation_objects[equation_id])
            ]
            unrendered_configurations = [
                configuration_id for configuration_id in output.used_configuration_ids
                if configuration_id in configuration_objects
                and not _configuration_rendered(
                    output.section_markdown, configuration_objects[configuration_id]
                )
            ]
            if unrendered_claims:
                quality_failures.append("unrendered_claims:" + ",".join(sorted(unrendered_claims)))
            if unrendered_equations:
                quality_failures.append("unrendered_equations:" + ",".join(sorted(unrendered_equations)))
            if unrendered_configurations:
                quality_failures.append(
                    "unrendered_configurations:" + ",".join(sorted(unrendered_configurations))
                )
            _require_exact_or_subset(
                quality_failures,
                "rhetorical_moves",
                required={move.move for move in graph.moves if move.required},
                used=set(output.completed_rhetorical_moves),
                # An open callback deliberately leaves its move unresolved;
                # report the typed callback state below rather than also
                # presenting it as an ordinary missing-move binding failure.
                allow_missing=has_research_callbacks,
            )
            if len(output.completed_rhetorical_moves) != len(set(output.completed_rhetorical_moves)):
                quality_failures.append("duplicate_rhetorical_moves")
            _check_writing_callback_contract(
                quality_failures,
                output=output,
                graph=graph,
                unit_by_id=unit_by_id,
                authority_proofs=authority_proofs,
                fulfilled_callback_bindings=fulfilled_callback_bindings.get(
                    graph.section_id,
                    set(),
                ),
            )
            for raw_request in output.new_research_requests:
                try:
                    request = WritingResearchRequestV1.model_validate(raw_request)
                except ValueError:
                    section_failures.append("writing_research_request_schema_invalid")
                    continue
                routed_request = _populate_request_candidates(
                    request,
                    graph=graph,
                    unit_by_id=unit_by_id,
                    authority_proofs=authority_proofs,
                )
                if routed_request is not None:
                    research_requests.append(routed_request)
        if section_failures:
            failures.extend(f"{graph.section_id}:{failure}" for failure in section_failures)
        elif output is not None:
            if not response_ref:
                failures.append(f"{graph.section_id}:missing_writer_response_ref")
            else:
                accepted.append((graph.section_id, output.section_markdown, response_ref))
        failures.extend(f"{graph.section_id}:{failure}" for failure in quality_failures)
        section_rows.append({
            "section_id": graph.section_id,
            "heading": graph.heading,
            "accepted": not section_failures and bool(response_ref),
            "failures": section_failures + quality_failures,
            "output": output.model_dump(mode="json") if output is not None else None,
        })

    # Content-first writer surface (E1): unresolved prose points become
    # explicit review items; they are never silently dropped.
    unresolved_points: list[tuple[str, str]] = []
    for graph in plan.sections:
        output = output_by_section.get(graph.section_id)
        if output is None:
            continue
        for raw_point in getattr(output, "unresolved_points", ()) or ():
            point = str(raw_point or "").strip()
            if point:
                unresolved_points.append((graph.section_id, point))

    editor_result = None
    editor_incumbent_accepted: list[tuple[str, str, str]] = []
    editor_local_ledgers: dict[str, Any] = {}
    editor_transition_path = ""
    editor_transition_digest = ""
    generation_owner_by_section = {section_id: "writer" for section_id, _text, _ref in accepted}
    if len(accepted) > 1:
        editor_incumbent_accepted = list(accepted)
        editor_section_contexts = _editor_section_contexts(
            writer_inputs=writer_inputs,
            outputs=output_by_section,
            claims=claims,
        )
        editor_result = CrossSectionEditor().edit_with_llm(
            {section_id: text for section_id, text, _ref in accepted},
            section_contexts=editor_section_contexts,
            document_context={
                "method_name": plan.method_name,
                "audience": plan.audience,
                "section_order": [
                    {
                        "section_id": section.section_id,
                        "heading": section.heading,
                        "reader_question": section.reader_question,
                    }
                    for section in plan.sections
                ],
                "revision_priorities": [
                    "preserve_author_story_order",
                    "separate_repository_fact_from_candidate_narrative",
                    "render_supported_claims_once_in_academic_language",
                    "remove_cross_section_repetition",
                    "keep_code_identifiers_as_parenthetical_bindings_only",
                ],
            },
            config=llm_config,
            caller=editor_caller or llm_caller,
        )
        if not editor_result.blocked_reason and editor_result.patches:
            editor_result = _select_safe_editor_section_transactions(
                editor_result=editor_result,
                incumbent=editor_incumbent_accepted,
                plan=plan,
                claims=claims,
                equations=equations,
                configurations=configurations,
                outputs=output_by_section,
                section_contexts=editor_section_contexts,
            )
        if editor_result.blocked_reason:
            failures.append(f"editor:{editor_result.blocked_reason}")
            failures.extend(
                f"editor:{failure}" for failure in editor_result.call_failures
            )
        elif editor_result.duplicate_signatures:
            failures.append("editor:duplicate_information_introduced")
        elif editor_result.patches:
            editor_regressions = _editor_claim_regressions(
                patches=editor_result.patches,
                original_sections={section_id: text for section_id, text, _ref in accepted},
                edited_sections=editor_result.sections,
                outputs=output_by_section,
                claims_by_id={item.claim_id: item for item in claims.claims},
            )
            if editor_regressions:
                failures.extend(f"editor:{failure}" for failure in editor_regressions)
                editor_result = editor_result.with_updates(
                    sections={section_id: text for section_id, text, _ref in accepted},
                    blocked_reason=";".join(editor_regressions),
                )
            else:
                response_ref = editor_result.response_ref
                candidate_accepted = [
                    (
                        section_id,
                        editor_result.sections.get(section_id, text),
                        response_ref if any(patch.section_id == section_id for patch in editor_result.patches) else old_ref,
                    )
                    for section_id, text, old_ref in accepted
                ]
                decision, decision_reasons, incumbent_snapshot, candidate_snapshot = (
                    _editor_candidate_decision(
                        incumbent=editor_incumbent_accepted,
                        candidate=candidate_accepted,
                        plan=plan,
                        claims=claims,
                        equations=equations,
                        configurations=configurations,
                        outputs=output_by_section,
                        section_contexts=editor_section_contexts,
                    )
                )
                editor_transition_path, editor_transition_digest = _write_editor_transitions(
                    out_root=out_root,
                    decision=decision,
                    reasons=decision_reasons,
                    incumbent_snapshot=incumbent_snapshot,
                    candidate_snapshot=candidate_snapshot,
                    incumbent_text="\n\n".join(
                        text for _section_id, text, _ref in editor_incumbent_accepted
                    ),
                    candidate_text="\n\n".join(
                        text for _section_id, text, _ref in candidate_accepted
                    ),
                    response_ref=response_ref,
                )
                if decision == "reject":
                    failures.append(f"editor:editor_candidate_rejected:{';'.join(decision_reasons)}")
                    accepted = list(editor_incumbent_accepted)
                    output_by_section = dict(output_by_section)
                    for section_id, text, _response_ref in accepted:
                        if section_id in output_by_section:
                            output_by_section[section_id] = output_by_section[section_id].model_copy(
                                update={"section_markdown": text}
                            )
                    editor_result = editor_result.with_updates(
                        sections={section_id: text for section_id, text, _ref in accepted},
                        blocked_reason=f"editor_candidate_rejected:{';'.join(decision_reasons)}",
                    )
                    editor_local_ledgers = {}
                else:
                    accepted = candidate_accepted
                    for patch in editor_result.patches:
                        if patch.section_id in output_by_section:
                            output_by_section[patch.section_id] = output_by_section[patch.section_id].model_copy(
                                update={"section_markdown": editor_result.sections[patch.section_id]}
                            )
                    try:
                        editor_local_ledgers = _build_editor_local_ledgers(
                            incumbent_sections={
                                section_id: (text, response_ref)
                                for section_id, text, response_ref in editor_incumbent_accepted
                            },
                            edited_sections={
                                section_id: text
                                for section_id, text, _response_ref in accepted
                            },
                            patches=editor_result.patches,
                            response_ref=editor_result.response_ref,
                        )
                    except (TypeError, ValueError) as exc:
                        failures.append(f"editor:authorship_reconstruction_failed:{exc}")
                        accepted = list(editor_incumbent_accepted)
                        output_by_section = dict(output_by_section)
                        for section_id, text, _response_ref in accepted:
                            if section_id in output_by_section:
                                output_by_section[section_id] = output_by_section[section_id].model_copy(
                                    update={"section_markdown": text}
                                )
                        editor_result = editor_result.with_updates(
                            sections={section_id: text for section_id, text, _ref in accepted},
                            blocked_reason=f"authorship_reconstruction_failed:{exc}",
                        )
                        editor_local_ledgers = {}
    final_text = "\n\n".join(text for _section_id, text, _response_ref in accepted)
    generated_spans: list[GeneratedTextSpanV1] = []
    for section_id, text, response_ref in accepted:
        local_ledger = editor_local_ledgers.get(section_id)
        if local_ledger is None:
            generated_spans.append(GeneratedTextSpanV1(
                span_id=f"writer:{section_id}",
                text=text,
                owner="writer",
                response_ref=response_ref,
                section_id=section_id,
                generation_trace_id=response_ref,
            ))
            continue
        for span in local_ledger.spans:
            generated_spans.append(GeneratedTextSpanV1(
                span_id=f"{span.source_span_id}:{section_id}",
                text=text[span.final_start:span.final_end],
                owner=span.owner,
                response_ref=span.response_ref,
                section_id=section_id,
                generation_trace_id=span.generation_trace_id,
            ))
    ledger = build_final_text_authorship_ledger(final_text, tuple(generated_spans))
    callback_section_ids = {
        request.section_id for request in research_requests if request.status == "open"
    }
    binding_failures = tuple(
        failure for failure in failures
        if any(token in failure for token in (
            "unknown_argument_units", "missing_argument_units",
            "unknown_claims", "missing_claims",
            "unknown_equations", "missing_equations",
            "unknown_configurations", "missing_configurations",
        ))
    )
    final_text_validation_status, final_validation_paths = _maybe_validate_final_text(
        out_root=out_root,
        artifact_paths=artifact_paths,
        claims=claims,
        equations=equations,
        final_text=final_text,
    )
    writer_input_by_section = {item.section_id: item for item in writer_inputs}
    style_repair_issues = _academic_rewrite_issues_by_section(
        output_by_section,
        claims=claims,
        writer_inputs=writer_input_by_section,
    )
    incumbent_validation_status = final_text_validation_status
    incumbent_validation_counts = _validation_failure_counts(final_validation_paths)
    incumbent_style_issue_count = sum(len(items) for items in style_repair_issues.values())
    rewrite_transitions: list[RepairTransitionV1] = []
    rewrite_results: list[dict[str, Any]] = []
    rewrite_failures: list[str] = []
    rewrite_transition_path = ""
    rewrite_results_path = ""
    rewrite_transition_digest = ""
    rewrite_enabled = (
        bool(style_repair_issues)
        or _has_local_validation_repair_issue(final_validation_paths)
    ) and (
        rewrite_caller is not None
        or _llm_provider_value(llm_config) not in {"", "none"}
    )
    if rewrite_enabled:
        incumbent_accepted = list(accepted)
        incumbent_output_by_section = dict(output_by_section)
        incumbent_generation_owner_by_section = dict(generation_owner_by_section)
        incumbent_final_text = final_text
        incumbent_ledger = ledger
        (
            accepted,
            output_by_section,
            generation_owner_by_section,
            rewrite_transitions,
            rewrite_results,
            rewrite_failures,
            rewrite_ledger,
        ) = _apply_local_rewrite_repairs(
            accepted=accepted,
            output_by_section=output_by_section,
            generation_owner_by_section=generation_owner_by_section,
            incumbent_ledger=ledger,
            incumbent_final_text=incumbent_final_text,
            claims=claims,
            validation_paths=final_validation_paths,
            llm_config=llm_config,
            rewrite_caller=rewrite_caller,
            additional_issues_by_section=style_repair_issues,
            writer_context_by_section=writer_input_by_section,
        )
        failures.extend(rewrite_failures)
        (
            rewrite_transition_path,
            rewrite_results_path,
            rewrite_transition_digest,
        ) = _write_rewrite_transitions(
            out_root=out_root,
            initial_validation_status=final_text_validation_status,
            transitions=rewrite_transitions,
            results=rewrite_results,
            failures=rewrite_failures,
        )
        final_text = "\n\n".join(text for _section_id, text, _response_ref in accepted)
        # The Rewrite Agent owns only the bytes in its exact patches.  Keep
        # the incumbent Writer/Editor spans in the ledger instead of
        # attributing an entire rewritten section to the latest response.
        # This makes the final lexical provenance auditable and prevents an
        # owning-agent response from becoming a blanket author for unchanged
        # text.
        ledger = rewrite_ledger or build_final_text_authorship_ledger(
            final_text,
            tuple(
                GeneratedTextSpanV1(
                    span_id=f"{generation_owner_by_section[section_id]}:{section_id}",
                    text=text,
                    owner=generation_owner_by_section[section_id],
                    response_ref=response_ref,
                    section_id=section_id,
                    generation_trace_id=response_ref,
                )
                for section_id, text, response_ref in accepted
            ),
        )
        for row in section_rows:
            section_id = row["section_id"]
            if section_id in output_by_section:
                row["output"] = output_by_section[section_id].model_dump(mode="json")
        final_text_validation_status, final_validation_paths = _maybe_validate_final_text(
            out_root=out_root,
            artifact_paths=artifact_paths,
            claims=claims,
            equations=equations,
            final_text=final_text,
        )
        candidate_validation_counts = _validation_failure_counts(final_validation_paths)
        candidate_style_issue_count = sum(
            len(items)
            for items in _academic_rewrite_issues_by_section(
                output_by_section,
                claims=claims,
                writer_inputs=writer_input_by_section,
            ).values()
        )
        applied_transitions = [
            item for item in rewrite_transitions if item.status == "applied"
        ]
        rewrite_improved = _rewrite_candidate_has_safe_gain(
            incumbent_validation_status=incumbent_validation_status,
            candidate_validation_status=final_text_validation_status,
            incumbent_validation_counts=incumbent_validation_counts,
            candidate_validation_counts=candidate_validation_counts,
            incumbent_style_issue_count=incumbent_style_issue_count,
            candidate_style_issue_count=candidate_style_issue_count,
        )
        if applied_transitions and not rewrite_improved:
            # A syntactically valid patch is not enough.  Keep a local rewrite
            # only when repository safety does not regress and at least one
            # validator or Method-language issue improves.  Candidate review
            # material is allowed to remain, so an unrelated open review item
            # must not roll back a genuine section-scoped style repair.
            accepted = incumbent_accepted
            output_by_section = incumbent_output_by_section
            generation_owner_by_section = incumbent_generation_owner_by_section
            final_text = incumbent_final_text
            ledger = incumbent_ledger
            failures.append("rewrite:rolled_back_no_safe_quality_gain")
            rewrite_failures.append("rewrite:rolled_back_no_safe_quality_gain")
            applied_sections = {
                item.transition_id.removeprefix("local-rewrite:").rsplit(":attempt-", 1)[0]
                for item in applied_transitions
            }
            rewritten_transitions: list[RepairTransitionV1] = []
            for item in rewrite_transitions:
                payload = item.model_dump(mode="json")
                if item.status == "applied":
                    payload.update({
                        "status": "rejected",
                        "candidate_digest": item.incumbent_digest,
                        "reason": "rewrite_candidate_no_safe_quality_gain",
                    })
                rewritten_transitions.append(RepairTransitionV1.model_validate(payload))
            rewrite_transitions = rewritten_transitions
            for item in rewrite_results:
                section_id = str(item.get("section_id") or "")
                result_payload = item.get("result")
                if (
                    section_id in applied_sections
                    and isinstance(result_payload, dict)
                    and result_payload.get("status") == "applied"
                ):
                    incumbent_section = {
                        incumbent_section_id: (incumbent_text, incumbent_response_ref)
                        for incumbent_section_id, incumbent_text, incumbent_response_ref
                        in incumbent_accepted
                    }.get(section_id, ("", ""))[0]
                    result_payload.update({
                        "status": "rejected",
                        "candidate_text": incumbent_section,
                        "candidate_digest": result_payload.get("incumbent_digest", ""),
                        "blocked_reason": "rewrite_candidate_no_safe_quality_gain",
                        "patch_failures": [
                            *result_payload.get("patch_failures", []),
                            "candidate_no_safe_quality_gain",
                        ],
                    })
            rewrite_transition_path, rewrite_results_path, rewrite_transition_digest = _write_rewrite_transitions(
                out_root=out_root,
                initial_validation_status="failed",
                transitions=rewrite_transitions,
                results=rewrite_results,
                failures=rewrite_failures,
            )
            # Restore the frozen validation artifacts to the incumbent text as
            # well, so artifact digests and the published candidate agree.
            final_text_validation_status, final_validation_paths = _maybe_validate_final_text(
                out_root=out_root,
                artifact_paths=artifact_paths,
                claims=claims,
                equations=equations,
                final_text=final_text,
            )
            for row in section_rows:
                section_id = row["section_id"]
                if section_id in output_by_section:
                    row["output"] = output_by_section[section_id].model_dump(mode="json")
    final_validation_failures = _final_validation_failures_by_section(
        final_validation_paths,
        ledger=ledger,
    )
    final_validation_failure_sections = {
        str(item.get("section_id") or "")
        for item in final_validation_failures
        if str(item.get("section_id") or "")
    }
    accepted_section_ids = {section_id for section_id, _text, _ref in accepted}
    incomplete_ids = tuple(dict.fromkeys(
        [
            graph.section_id for graph in plan.sections
            if graph.section_id not in accepted_section_ids
            or graph.section_id in callback_section_ids
            or graph.section_id in final_validation_failure_sections
        ]
        + [
            section_id for section_id in final_validation_failure_sections
            if section_id not in {graph.section_id for graph in plan.sections}
        ]
    ))
    for row in section_rows:
        section_id = str(row.get("section_id") or "")
        section_failures = [
            str(item.get("message") or "final_text_claim_validation_failed")
            for item in final_validation_failures
            if str(item.get("section_id") or "") == section_id
        ]
        if section_failures:
            row["failures"] = list(dict.fromkeys([*row.get("failures", []), *section_failures]))
    if not ledger.hard_gate_passed:
        failures.extend(ledger.failures)
    quality = evaluate_publication_method_quality(
        final_text=final_text,
        plan=plan,
        completeness=completeness,
        section_outputs=tuple(
            output_by_section[section_id]
            for section_id, _text, _ref in accepted
            if section_id in output_by_section
        ),
        ledger=ledger,
        claims=claims,
        binding_failures=binding_failures,
        configurations=configurations,
        equations=equations,
        open_research_requests=tuple(research_requests),
        utility_failures=tuple(failure for failure in failures if failure not in binding_failures),
        final_text_validation_status=final_text_validation_status,
        final_validation_failures=final_validation_failures,
    )
    (
        candidate_markdown,
        verified_markdown,
        review_items,
        external_queue_items,
        split_report,
    ) = _build_product_bundle(
        final_text=final_text,
        accepted=accepted,
        plan=plan,
        completeness=completeness,
        readiness=readiness,
        research_requests=research_requests,
        unresolved_points=unresolved_points,
        validation_paths=final_validation_paths,
    )
    # A/E/G product status: a failed reverse validation blocks *verified*
    # inclusion, never the candidate document.  Candidate output is blocked
    # only for intrinsic safety failures (authorship gate, invented ids,
    # source integrity, plan blocked-for-safety) that make fact/caveat
    # boundaries indistinguishable.
    intrinsic_block = (
        not ledger.hard_gate_passed
        or bool(binding_failures)
        or not quality.safety.source_integrity
    )
    status: Literal["success", "incomplete", "blocked"] = (
        "blocked"
        if not accepted
        or intrinsic_block
        or (quality.status == "blocked" and final_text_validation_status != "failed")
        else "incomplete"
        if (
            quality.status == "incomplete"
            or incomplete_ids
            or plan.incomplete_sections
            or failures
            or final_text_validation_status == "failed"
            or review_items
            or external_queue_items
            or not verified_markdown.strip()
        )
        else "success"
    )
    # Effective readiness reflects the actual split: any review item, any
    # external queue item, or any sentence excluded from verified demotes a
    # plan-level ``verified_ready`` to ``candidate_ready_with_review``.
    effective_readiness: str = (
        "candidate_ready_with_review"
        if review_items or external_queue_items or verified_markdown != candidate_markdown
        else readiness.readiness
    )
    paths = _write_publication_outputs(
        out_root=out_root,
        candidate_markdown=candidate_markdown,
        verified_markdown=verified_markdown,
        review_items=review_items,
        external_queue_items=external_queue_items,
        split_report=split_report,
        readiness=readiness,
        effective_readiness=effective_readiness,
        research_requests=research_requests,
        writer=writer,
        ledger=ledger,
        quality=quality,
        section_outputs=output_by_section,
        section_response_refs={section_id: response_ref for section_id, _text, response_ref in accepted},
        editor_result=editor_result,
        formalization_path=formalization_path,
        status=status,
        incomplete_section_ids=incomplete_ids,
        callback_bundle=callback_bundle,
        callback_artifacts=callback_artifacts,
        resumed_section_ids=_actually_regenerated_section_ids(
            writer.aggregate,
            effective_resume_section_ids,
        ),
    )
    paths.update(final_validation_paths)
    if formalization_agent_path:
        paths["formalization_agent_result_v1"] = formalization_agent_path
    if architect_trace_path:
        paths["method_architect_trace_v1"] = architect_trace_path
    if editor_transition_path:
        paths["publication_editor_transitions_v1"] = editor_transition_path
    if rewrite_transition_path:
        paths["publication_rewrite_transitions_v1"] = rewrite_transition_path
    if rewrite_results_path:
        paths["publication_rewrite_results_v1"] = rewrite_results_path
    callback_bundle_digest = ""
    callback_bundle_path = paths.get("writing_research_callback_artifacts_v1", "")
    if callback_bundle_path:
        try:
            callback_bundle_digest = WritingResearchCallbackBundleV1.model_validate_json(
                Path(callback_bundle_path).read_text(encoding="utf-8")
            ).content_digest
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            callback_bundle_digest = ""
    result = PublicationWriterRunResultV1(
        status=status,
        plan_digest=plan.content_digest,
        claim_digest=claims.content_digest,
        section_results=tuple(section_rows),
        accepted_section_ids=tuple(section_id for section_id, _text, _ref in accepted),
        incomplete_section_ids=incomplete_ids,
        binding_failures=tuple(failures),
        writer_aggregate=writer.aggregate.to_json_dict(),
        response_recovery_traces=tuple([
            *writer.aggregate.response_recovery_traces,
            *callback_recovery_traces,
        ]),
        final_text_digest=_digest_text(final_text) if final_text else "",
        authorship_ledger_digest=ledger.content_digest,
        publication_quality_digest=quality.content_digest,
        rewrite_transition_digest=rewrite_transition_digest,
        callback_bundle_digest=callback_bundle_digest,
        # Truthful resume telemetry: zero Writer generation/recovery traces or
        # zero model-call delta means zero actually regenerated sections.  The
        # admitted set (effective resume ids) is reported separately so an
        # admitted-but-blocked resume is never labeled as a resumed section.
        resumed_section_ids=_actually_regenerated_section_ids(
            writer.aggregate,
            effective_resume_section_ids,
        ),
        blocked_reason=(
            "publication_final_reverse_validation_failed"
            if status == "blocked" and final_text_validation_status == "failed"
            else "no_authored_section_passed_binding_and_authorship_gates"
            if status == "blocked"
            else ""
        ),
    )
    result_path = method_output(Path(out_root), "publication_writer_result_v1")
    _atomic_write_text(result_path, result.model_dump_json(indent=2) + "\n")
    paths["publication_writer_result_v1"] = str(result_path)
    return result, paths


def _run_formalization_agent(
    *,
    base: FormalizationResultV1,
    facts: Any,
    equations: Any,
    config: LLMConfig,
    caller: Callable[[LLMConfig, LLMRequest], LLMResponse],
    out_root: str | Path,
) -> tuple[FormalizationResultV1, dict[str, Any]]:
    """Run the bounded Formalization owner path with deterministic guards.

    The Formalization Agent proposes pseudocode, derivation steps, notation
    notes, or validation conclusions bound to closed fact/equation ids.  Every
    proposal passes the deterministic authority guards (closed ids, operand/
    value preservation, operator preservation, no theoretical upgrade) before
    it may reach the Writer.  Guard failures are returned to the owning Agent
    for exactly one bounded retry; a second failure keeps the proposal out and
    records the typed risk instead of fabricating formal content.
    """

    from code2paper.llm.response_schemas import json_schema_for, try_parse_structured_response

    fact_rows = [
        {
            "fact_id": fact.fact_id,
            "subject": fact.subject,
            "predicate": fact.predicate,
            "object": fact.object,
            "conditions": list(fact.conditions),
        }
        for fact in facts.facts
    ]
    equation_rows = [
        {
            "equation_id": item.equation_id,
            "expression": item.expression,
            "conditions": list(item.conditions),
            "operation_descriptors": list(item.operation_descriptors),
            "symbol_bindings": [
                {
                    "symbol": binding.symbol,
                    "operand_value": binding.operand_value,
                    "fact_id": binding.fact_id,
                }
                for binding in item.symbol_bindings
            ],
        }
        for item in equations.equations
    ]
    try:
        configured_budget = int(
            os.environ.get(
                "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_PUBLICATION_FORMALIZER",
                "2048",
            )
        )
    except ValueError:
        configured_budget = 2048
    formalizer_config = config.model_copy(update={
        "max_output_tokens": min(config.max_output_tokens, max(1024, min(configured_budget, 8192))),
        "reasoning_effort": "none",
        "thinking_token_budget": None,
        "temperature": min(config.temperature, 0.2),
    })
    attempt_log: list[dict[str, Any]] = []
    approved_items: list[FormalizationProposalItemV1] = []
    response_refs: list[str] = []
    for attempt in (1, 2):
        request = LLMRequest(
            prompt_template_id="agentic_publication_method_formalizer_v1",
            prompt=(
                "Return only JSON matching the formalization proposal schema. "
                "Propose bounded pseudocode, derivation steps, notation notes, or "
                "validation conclusions that restate the supplied code facts "
                "exactly. Bind every item to exact fact_id/equation_id values "
                "from the supplied sets. Do not introduce new constants, change "
                "operands or operators, and do not claim convergence, optimality, "
                "statistical significance, or any property the code facts cannot "
                "license. If nothing safe can be proposed, return "
                '{"items": []}.'
                + (
                    f" Previous proposal failed deterministic guards: "
                    + "; ".join(attempt_log[-1].get("guard_failures", []))
                    if attempt_log and attempt_log[-1].get("guard_failures")
                    else ""
                )
            ),
            input_payload={
                "facts": fact_rows,
                "equations": equation_rows,
                "assumptions": list(dict.fromkeys(
                    assumption
                    for obligation in base.proof_obligations
                    for assumption in obligation.assumptions
                )),
                "contract": "exact_fact_equivalence_only",
            },
            schema_name="agentic_publication_method_formalizer_v1",
            response_json_schema=json_schema_for(FormalizationProposalV1),
        )
        response = caller(formalizer_config, request)
        response_refs.append(response.response_hash)
        if response.blocked_reason or not (response.text or "").strip():
            attempt_log.append({
                "attempt": attempt,
                "status": "blocked",
                "blocked_reason": response.blocked_reason,
                "response_ref": response.response_hash,
                "guard_failures": [],
            })
            continue
        parsed, error = try_parse_structured_response(response.text, FormalizationProposalV1)
        if parsed is None:
            attempt_log.append({
                "attempt": attempt,
                "status": "schema_failed",
                "error": str(error)[:200],
                "response_ref": response.response_hash,
                "guard_failures": [],
            })
            continue
        guard_failures = validate_formalization_proposal(
            parsed,
            facts=facts,
            equations=equations,
        )
        attempt_log.append({
            "attempt": attempt,
            "status": "accepted" if not guard_failures else "guards_failed",
            "proposal_id": parsed.proposal_id,
            "response_ref": response.response_hash,
            "guard_failures": guard_failures,
            "item_count": len(parsed.items),
        })
        if not guard_failures:
            approved_items.extend(parsed.items)
            break
    risks = list(base.risks)
    for index, entry in enumerate(attempt_log):
        if entry.get("guard_failures"):
            risks.append(FormalizationRiskV1(
                risk_id=f"risk:formalizer:attempt-{index + 1}",
                kind="proposal_guards_failed",
                message="; ".join(entry["guard_failures"][:6]),
                blocking=False,
            ))
    result = base.model_copy(update={
        "proposal_items": tuple(approved_items),
        "risks": tuple(risks),
    })
    return result, {
        "schema_version": "1.0",
        "attempts": attempt_log,
        "approved_item_count": len(approved_items),
        "approved_items": [item.model_dump(mode="json") for item in approved_items],
        "response_refs": response_refs,
        "budget": {
            "max_output_tokens": formalizer_config.max_output_tokens,
            "attempt_count": len(attempt_log),
        },
    }


def _editor_section_snapshot(
    *,
    sections: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    claims: Any,
    equations: Any,
    configurations: Any,
    outputs: dict[str, PublicationMethodSectionOutputV1] | None = None,
    section_contexts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deterministic utility snapshot of a section set for candidate decisions."""
    claims_by_id = {item.claim_id: item for item in claims.claims}
    equation_by_id = {item.equation_id: item for item in equations.equations}
    configuration_by_id = {item.configuration_id: item for item in configurations.claims}
    outputs = outputs or {}
    section_contexts = section_contexts or {}
    section_texts: list[str] = []
    rendered_claims: set[str] = set()
    rendered_equations: set[str] = set()
    rendered_configurations: set[str] = set()
    rendered_by_section: dict[str, dict[str, set[str]]] = {}
    bound_moves: set[tuple[str, str]] = set()
    editable_count = 0
    section_ids = {section_id for section_id, _text, _ref in sections}
    for section_id, text, _ref in sections:
        section_texts.append(text)
        if _section_editable(text):
            editable_count += 1
        output = outputs.get(section_id)
        used_claim_objects = {
            claim_id: claims_by_id[claim_id]
            for claim_id in (output.used_claim_ids if output is not None else ())
            if claim_id in claims_by_id
        }
        used_equation_objects = {
            equation_id: equation_by_id[equation_id]
            for equation_id in (output.used_equation_ids if output is not None else ())
            if equation_id in equation_by_id
        }
        used_configuration_objects = {
            configuration_id: configuration_by_id[configuration_id]
            for configuration_id in (output.used_configuration_ids if output is not None else ())
            if configuration_id in configuration_by_id
        }
        section_rendered: dict[str, set[str]] = {"claims": set(), "equations": set(), "configs": set()}
        for claim_id, claim in claims_by_id.items():
            if _claim_rendered_in(text, claim):
                rendered_claims.add(claim_id)
                section_rendered["claims"].add(claim_id)
        for equation_id, equation in equation_by_id.items():
            if _equation_rendered(text, equation):
                rendered_equations.add(equation_id)
                section_rendered["equations"].add(equation_id)
        for configuration_id, configuration in configuration_by_id.items():
            if _configuration_rendered(text, configuration):
                rendered_configurations.add(configuration_id)
                section_rendered["configs"].add(configuration_id)
        rendered_by_section[section_id] = section_rendered
        for move in {
            move.move for section in plan.sections
            if section.section_id == section_id
            for move in section.moves
            if move.required
        }:
            if _move_witness_span(
                text,
                move,
                used_claims=used_claim_objects,
                used_equations=used_equation_objects,
                used_configurations=used_configuration_objects,
            ) is not None:
                bound_moves.add((section_id, move))
    duplicate_rate, _messages = _duplicate_rate(
        section_texts,
        used_claims=claims_by_id,
    )
    required_moves = {
        (section.section_id, move.move)
        for section in plan.sections
        for move in section.moves
        if move.required
    }
    generic_style_issue_count = sum(
        len(pattern.findall(text))
        for _section_id, text, _ref in sections
        for pattern in _GENERIC_METHOD_PATTERNS
    ) + len(find_code_trace_prose_sections([
        PublicationMethodSectionOutputV1(
            section_id=section_id,
            section_markdown=text,
        )
        for section_id, text, _ref in sections
    ]))
    candidate_authority_violations = _candidate_authority_violation_count(
        sections,
        section_contexts=section_contexts,
    )
    return {
        "duplicate_rate": duplicate_rate,
        "editable_rate": _ratio_count(editable_count, len(section_texts)),
        "bound_moves": bound_moves,
        "required_moves": required_moves,
        "rendered_claims": rendered_claims,
        "rendered_equations": rendered_equations,
        "rendered_configurations": rendered_configurations,
        "rendered_by_section": rendered_by_section,
        "generic_style_issue_count": generic_style_issue_count,
        "candidate_authority_violations": candidate_authority_violations,
        "coherent": required_moves and all(
            item[0] in section_ids for item in required_moves
        ),
    }


def _ratio_count(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


_CANDIDATE_AUTHORITY_MARKERS = (
    "we aim", "we intend", "we formulate", "we hypothesize", "we assume",
    "we propose to", "our intended design", "the intended design",
    "repository evidence partially", "available repository evidence partially",
    "the current repository covers", "pending", "awaiting", "unverified",
    "requires confirmation", "mismatch", "not yet verified",
)


def _candidate_authority_violation_count(
    sections: Iterable[tuple[str, str, str]],
    *,
    section_contexts: Mapping[str, Mapping[str, Any]],
) -> int:
    """Count candidate-point restatements that hide their authority lane."""

    violations = 0
    for section_id, text, _ref in sections:
        context = section_contexts.get(section_id, {})
        point_token_sets = [
            set(_content_tokens(str(item.get("statement") or "")))
            for item in (context.get("section_candidate_points") or ())
            if isinstance(item, dict) and str(item.get("statement") or "").strip()
        ]
        if not point_token_sets:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
            lowered = sentence.lower()
            if not sentence.strip() or sentence.lstrip().startswith("#"):
                continue
            tokens = set(_content_tokens(sentence))
            if not tokens or not any(
                len(tokens & point_tokens) / max(
                    1, min(len(tokens), len(point_tokens))
                ) >= 0.45
                for point_tokens in point_token_sets
            ):
                continue
            if not any(marker in lowered for marker in _CANDIDATE_AUTHORITY_MARKERS):
                violations += 1
    return violations


def _editor_section_contexts(
    *,
    writer_inputs: Iterable[WriterSectionInput],
    outputs: Mapping[str, PublicationMethodSectionOutputV1],
    claims: AtomicClaimSetV3,
) -> dict[str, dict[str, Any]]:
    """Project the Writer's authority surfaces into the global Editor call.

    The earlier Editor saw only raw prose, so it could detect an exact repeat
    but could not know whether a sentence was a repository fact, an intended
    contribution awaiting confirmation, or an unsupported invention.  This
    compact projection gives it the semantic material required for academic
    revision while omitting raw source files and internal validation records.
    """

    claim_by_id = {item.claim_id: item for item in claims.claims}
    contexts: dict[str, dict[str, Any]] = {}
    for writer_input in writer_inputs:
        section_id = str(writer_input.section_id)
        output = outputs.get(section_id)
        payload = writer_input.prompt_payload
        reader_claims: list[dict[str, Any]] = []
        for raw in payload.get("reader_facing_claims") or ():
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            claim_id = str(item.get("claim_id") or "")
            claim = claim_by_id.get(claim_id)
            item["rendered_in_incumbent"] = bool(
                claim is not None
                and output is not None
                and _claim_rendered_in(output.section_markdown, claim)
            )
            reader_claims.append(item)
        contexts[section_id] = {
            "section": dict(payload.get("section") or {}),
            "reader_facing_claims": reader_claims,
            "section_candidate_points": list(
                payload.get("section_candidate_points") or ()
            ),
            "formalization": dict(payload.get("formalization") or {}),
            "paper_term_hints": list(payload.get("paper_term_hints") or ()),
            "required_rhetorical_moves": list(
                payload.get("required_rhetorical_moves") or ()
            ),
            "used_claim_ids": list(
                output.used_claim_ids if output is not None else ()
            ),
            "authority_policy": {
                "repository_claims": (
                    "May be stated as positive implementation facts, with all "
                    "qualifiers preserved."
                ),
                "candidate_points": (
                    "May be retained only with visible author-intent, partial, "
                    "mismatch, or pending framing; never as repository fact."
                ),
                "unlisted_positive_details": "Remove rather than rationalize.",
                "code_identifiers": "Use only as minimal parenthetical bindings.",
                "mathematics": "Use only supplied formalization; do not invent.",
            },
        }
    return contexts


def _editor_candidate_decision(
    *,
    incumbent: list[tuple[str, str, str]],
    candidate: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    claims: Any,
    equations: Any,
    configurations: Any,
    outputs: dict[str, PublicationMethodSectionOutputV1] | None = None,
    section_contexts: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[str, list[str], dict[str, Any], dict[str, Any]]:
    """Pareto/no-loss decision over an Editor candidate.

    The candidate replaces the incumbent only when no hard dimension regresses
    (rendered claims/equations/configurations, bound moves, duplicate rate,
    editability, coherence) and at least one required dimension improves.
    Improving duplication by deleting unique supported content is rejected by
    the no-loss comparisons.
    """

    incumbent_snapshot = _editor_section_snapshot(
        sections=incumbent,
        plan=plan,
        claims=claims,
        equations=equations,
        configurations=configurations,
        outputs=outputs,
        section_contexts=section_contexts,
    )
    candidate_snapshot = _editor_section_snapshot(
        sections=candidate,
        plan=plan,
        claims=claims,
        equations=equations,
        configurations=configurations,
        outputs=outputs,
        section_contexts=section_contexts,
    )
    reasons: list[str] = []
    for section_id in sorted(
        set(incumbent_snapshot["rendered_by_section"]) | set(candidate_snapshot["rendered_by_section"])
    ):
        incumbent_rendered = incumbent_snapshot["rendered_by_section"].get(
            section_id, {"claims": set(), "equations": set(), "configs": set()}
        )
        candidate_rendered = candidate_snapshot["rendered_by_section"].get(
            section_id, {"claims": set(), "equations": set(), "configs": set()}
        )
        lost_claims = sorted(incumbent_rendered["claims"] - candidate_rendered["claims"])
        if lost_claims:
            reasons.append(
                f"candidate_claim_loss:{section_id}:{','.join(lost_claims[:6])}"
            )
        lost_equations = sorted(
            incumbent_rendered["equations"] - candidate_rendered["equations"]
        )
        if lost_equations:
            reasons.append(
                f"candidate_equation_loss:{section_id}:{','.join(lost_equations[:6])}"
            )
        lost_configurations = sorted(
            incumbent_rendered["configs"] - candidate_rendered["configs"]
        )
        if lost_configurations:
            reasons.append(
                f"candidate_configuration_loss:{section_id}:{','.join(lost_configurations[:6])}"
            )
    lost_moves = sorted(
        incumbent_snapshot["bound_moves"] - candidate_snapshot["bound_moves"]
    )
    if lost_moves:
        reasons.append(
            "candidate_move_regression:"
            + ",".join(f"{section}:{move}" for section, move in lost_moves[:6])
        )
    if candidate_snapshot["duplicate_rate"] > incumbent_snapshot["duplicate_rate"]:
        reasons.append("candidate_duplicate_worsened")
    if candidate_snapshot["editable_rate"] < incumbent_snapshot["editable_rate"]:
        reasons.append("candidate_editable_regressed")
    if incumbent_snapshot["coherent"] and not candidate_snapshot["coherent"]:
        reasons.append("candidate_coherence_regressed")
    if (
        candidate_snapshot["candidate_authority_violations"]
        > incumbent_snapshot["candidate_authority_violations"]
    ):
        reasons.append("candidate_authority_framing_regressed")
    if (
        candidate_snapshot["generic_style_issue_count"]
        > incumbent_snapshot["generic_style_issue_count"]
    ):
        reasons.append("candidate_academic_style_regressed")
    improvements = [
        candidate_snapshot["duplicate_rate"] < incumbent_snapshot["duplicate_rate"],
        candidate_snapshot["editable_rate"] > incumbent_snapshot["editable_rate"],
        len(candidate_snapshot["bound_moves"]) > len(incumbent_snapshot["bound_moves"]),
        candidate_snapshot["candidate_authority_violations"]
        < incumbent_snapshot["candidate_authority_violations"],
        candidate_snapshot["generic_style_issue_count"]
        < incumbent_snapshot["generic_style_issue_count"],
    ]
    decision = "reject" if reasons or not any(improvements) else "accept"
    return (
        decision,
        reasons,
        incumbent_snapshot,
        candidate_snapshot,
    )


def _select_safe_editor_section_transactions(
    *,
    editor_result: Any,
    incumbent: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    claims: Any,
    equations: Any,
    configurations: Any,
    outputs: dict[str, PublicationMethodSectionOutputV1],
    section_contexts: Mapping[str, Mapping[str, Any]],
) -> Any:
    """Commit safe Editor sections independently instead of all-or-nothing.

    Grouped Editor calls can return useful changes for many sections while a
    single patch loses one configuration or move anchor.  Evaluate each
    section against the latest accepted incumbent and retain only a local
    Pareto improvement.  This preserves exact patch provenance and prevents
    one bad section from rolling back the rest of the document.
    """

    incumbent_by_id = {
        section_id: (text, response_ref)
        for section_id, text, response_ref in incumbent
    }
    working = list(incumbent)
    selected: list[Any] = []
    rejected: list[str] = []
    patches_by_section: dict[str, list[Any]] = {}
    for patch in editor_result.patches:
        patches_by_section.setdefault(str(patch.section_id), []).append(patch)
    claims_by_id = {item.claim_id: item for item in claims.claims}
    for section_id in [item[0] for item in incumbent]:
        section_patches = patches_by_section.get(section_id, [])
        if not section_patches:
            continue
        proposed_text = str(editor_result.sections.get(section_id) or "")
        expected_heading = next(
            (item.heading for item in plan.sections if item.section_id == section_id),
            "",
        )
        if expected_heading and not _has_exact_section_heading(
            proposed_text, expected_heading,
        ):
            rejected.append(f"{section_id}:editor_removed_or_changed_heading")
            continue
        original_sections = {sid: text for sid, text, _ref in working}
        candidate_sections = dict(original_sections)
        candidate_sections[section_id] = proposed_text
        regressions = _editor_claim_regressions(
            patches=section_patches,
            original_sections=original_sections,
            edited_sections=candidate_sections,
            outputs=outputs,
            claims_by_id=claims_by_id,
        )
        candidate = [
            (
                sid,
                proposed_text if sid == section_id else text,
                (
                    section_patches[-1].generation_trace_ids[-1]
                    if sid == section_id and section_patches[-1].generation_trace_ids
                    else response_ref
                ),
            )
            for sid, text, response_ref in working
        ]
        decision, reasons, _before, _after = _editor_candidate_decision(
            incumbent=working,
            candidate=candidate,
            plan=plan,
            claims=claims,
            equations=equations,
            configurations=configurations,
            outputs=outputs,
            section_contexts=section_contexts,
        )
        if regressions or decision != "accept":
            rejected.extend([*regressions, *reasons] or [f"{section_id}:no_local_gain"])
            continue
        working = candidate
        selected.extend(section_patches)
    if not selected:
        return editor_result.with_updates(
            # Keep the rejected candidate visible to the existing aggregate
            # decision/transition path.  It will restore the incumbent after
            # recording the exact loss reason and candidate digest.
            sections=dict(editor_result.sections),
            patches=list(editor_result.patches),
            blocked_reason="",
            call_failures=tuple([*editor_result.call_failures, *rejected]),
        )
    return editor_result.with_updates(
        sections={sid: text for sid, text, _ref in working},
        patches=selected,
        blocked_reason="",
        call_failures=tuple([*editor_result.call_failures, *rejected]),
    )


def _has_exact_section_heading(text: str, heading: str) -> bool:
    first_line = (text or "").lstrip().splitlines()[:1]
    return bool(first_line and first_line[0].strip() == f"## {heading}")


def _write_editor_transitions(
    out_root: str | Path,
    *,
    decision: str,
    reasons: list[str],
    incumbent_snapshot: dict[str, Any],
    candidate_snapshot: dict[str, Any],
    incumbent_text: str,
    candidate_text: str,
    response_ref: str,
) -> tuple[str, str]:
    """Persist the Editor candidate decision with both side digests."""
    payload = {
        "schema_version": "1.0",
        "decision": decision,
        "reasons": reasons,
        "response_ref": response_ref,
        "incumbent_text_digest": _digest_text(incumbent_text),
        "candidate_text_digest": _digest_text(candidate_text),
        "incumbent": {
            key: {
                section_id: {
                    label: sorted(values)
                    for label, values in section_values.items()
                }
                for section_id, section_values in value.items()
            }
            if isinstance(value, dict) and value and isinstance(next(iter(value.values())), dict)
            else sorted(value) if isinstance(value, set) else value
            for key, value in incumbent_snapshot.items()
            if key != "bound_moves"
        },
        "candidate": {
            key: {
                section_id: {
                    label: sorted(values)
                    for label, values in section_values.items()
                }
                for section_id, section_values in value.items()
            }
            if isinstance(value, dict) and value and isinstance(next(iter(value.values())), dict)
            else sorted(value) if isinstance(value, set) else value
            for key, value in candidate_snapshot.items()
            if key != "bound_moves"
        },
        "bound_moves": {
            "incumbent": sorted(incumbent_snapshot["bound_moves"]),
            "candidate": sorted(candidate_snapshot["bound_moves"]),
        },
    }
    path = method_output(Path(out_root), "publication_editor_transitions_v1")
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    digest = _digest_text(path.read_text(encoding="utf-8"))
    return str(path), digest


def _extend_projection_with_callback_fragments(
    projection: Any,
    bundle_path: Path,
) -> Any:
    """Add fulfilled callback artifact content as author_attested_fragments.

    When a Writer resume consumes fulfilled ``author_attested`` callbacks, the
    generated prose for ``problem_or_local_context`` and ``design_objective``
    moves is grounded in the callback artifact files.  The reverse validator
    must see these as ``author_attested_fragments`` so it treats matching
    sentences as ``caveated`` (author-attested, no code evidence required)
    instead of ``unsupported``.

    Only artifacts with ``authority_lane == "author_attested"`` and a readable
    file reference are projected.  The digest is verified to prevent stale
    content from being authorized.
    """

    try:
        raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return projection
    artifacts = raw.get("artifacts") or {}
    if not isinstance(artifacts, dict):
        return projection
    base_dir = bundle_path.parent
    new_fragments: list[AuthorAttestedFragment] = []
    for request_id, items in artifacts.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("authority_lane") != "author_attested":
                continue
            ref = str(item.get("artifact_ref") or "").strip()
            if not ref:
                continue
            candidate = Path(ref).expanduser()
            if not candidate.is_absolute():
                candidate = base_dir / candidate
            if not candidate.is_file():
                continue
            try:
                content = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            actual_digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
            if actual_digest != item.get("artifact_digest"):
                continue
            fragment_id = f"callback:{request_id}"
            payload = {
                "fragment_id": fragment_id,
                "supported_fragment": content,
                "allowed_wording_boundary": content,
                "source_ref": ref,
            }
            new_fragments.append(
                AuthorAttestedFragment(**payload, input_digest=_digest_json(payload))
            )
    if not new_fragments:
        return projection
    existing = list(projection.author_attested_fragments)
    existing_ids = {f.fragment_id for f in existing}
    for frag in new_fragments:
        if frag.fragment_id not in existing_ids:
            existing.append(frag)
    return projection.model_copy(update={"author_attested_fragments": existing})


def _maybe_validate_final_text(
    *,
    out_root: str | Path,
    artifact_paths: dict[str, str],
    claims: AtomicClaimSetV3,
    equations: EquationClaimSetV1,
    final_text: str,
) -> tuple[Literal["pending", "passed", "failed"], dict[str, str]]:
    """Run the final reverse gate when the frozen V3 inputs are available.

    The isolated publication Writer is intentionally usable without the full
    LangGraph validation stage.  In that mode its quality report remains
    ``pending``.  A caller that supplies both the V3 packet artifact and the
    frozen MethodEvidence artifact gets the same sentence-to-evidence reverse
    validator used by the production graph, with exact claims/validation
    artifacts written beside the publication quality report.
    """

    packet_value = artifact_paths.get("evidence_packets_v3", "")
    method_value = artifact_paths.get("method_evidence") or artifact_paths.get("evidence", "")
    if not final_text or not packet_value or not method_value:
        return "pending", {}
    packet_path = Path(packet_value)
    method_path = Path(method_value)
    if not packet_path.is_file() or not method_path.is_file():
        return "pending", {}
    try:
        method_evidence = MethodEvidence.model_validate_json(
            method_path.read_text(encoding="utf-8")
        )
        packets = load_evidence_packets_v3(packet_path)
        if (
            packets.repo_snapshot_id != claims.repo_snapshot_id
            or packets.project_tree_hash != claims.project_tree_hash
            or claims.evidence_packet_digest != packets.content_digest
        ):
            return "failed", {}
        raw_value = artifact_paths.get("evidence_raw", "")
        if raw_value and Path(raw_value).is_file():
            raw_evidence = RawEvidencePack.model_validate_json(
                Path(raw_value).read_text(encoding="utf-8")
            )
        else:
            raw_evidence = RawEvidencePack(
                project_id=method_evidence.project_id,
                project_root=".",
            )
        snapshot_value = artifact_paths.get("evidence_snapshot_v2", "")
        snapshot = (
            load_evidence_snapshot_v2(snapshot_value)
            if snapshot_value and Path(snapshot_value).is_file()
            else None
        )
        intent_graph = None
        intent_value = artifact_paths.get("intent_obligation_graph_v2", "")
        if intent_value and Path(intent_value).is_file():
            intent_graph = IntentObligationGraphV2.model_validate_json(
                Path(intent_value).read_text(encoding="utf-8")
            )
        completeness = None
        completeness_value = artifact_paths.get("method_completeness_matrix_v1", "")
        if completeness_value and Path(completeness_value).is_file():
            completeness = MethodCompletenessMatrixV1.model_validate_json(
                Path(completeness_value).read_text(encoding="utf-8")
            )
        projection = None
        projection_value = artifact_paths.get("authoring_projection_v1", "")
        if projection_value and Path(projection_value).is_file():
            projection = AuthoringInputProjection.model_validate_json(
                Path(projection_value).read_text(encoding="utf-8")
            )
        if projection is None:
            projection = build_authoring_projection(
                method_evidence=method_evidence,
                claim_map=ClaimEvidenceMap(),
                verification=ClaimVerificationReport(),
                raw_evidence=raw_evidence,
                evidence_snapshot_v2=snapshot,
                atomic_claims_v3=claims,
                evidence_packets_v3=packets,
                equation_claims_v1=equations,
                intent_obligation_graph_v2=intent_graph,
                completeness=completeness,
            )
        # When a callback bundle with fulfilled author_attested artifacts is
        # supplied, the Writer writes prose grounded in those artifacts for
        # the problem_or_local_context and design_objective moves.  The reverse
        # validator must see them as author_attested_fragments so it treats
        # matching sentences as ``caveated`` instead of ``unsupported``.
        callback_value = artifact_paths.get("writing_research_callback_artifacts_v1", "")
        if callback_value and Path(callback_value).is_file():
            projection = _extend_projection_with_callback_fragments(
                projection, Path(callback_value)
            )
        final_claims = extract_final_text_claims(final_text, projection)
        validation = validate_text_evidence(
            final_claims=final_claims,
            projection=projection,
            raw_evidence=raw_evidence,
            evidence_snapshot_v2=snapshot,
            evidence_packets_v3=packets,
            require_semantic_verifier=False,
            max_semantic_verifier_calls=0,
        )
    except (OSError, TypeError, ValueError, KeyError):
        # Supplying malformed frozen inputs is an integrity failure, not a
        # reason to silently keep a pending quality report.
        return "failed", {}
    claims_path = method_output(Path(out_root), "final_text_claims")
    validation_path = method_output(Path(out_root), "text_evidence_validation")
    projection_path = method_output(Path(out_root), "authoring_projection_v1")
    write_final_text_claims(claims_path, final_claims)
    write_text_evidence_validation(validation_path, validation)
    _atomic_write_text(projection_path, projection.model_dump_json(indent=2) + "\n")
    status: Literal["passed", "failed"] = (
        "passed"
        if validation.status == "passed"
        and validation.unsupported_claims == 0
        and validation.unverified_claims == 0
        else "failed"
    )
    return status, {
        "final_text_claims": str(claims_path),
        "text_evidence_validation": str(validation_path),
        "authoring_projection_v1": str(projection_path),
    }


def _final_validation_failures_by_section(
    validation_paths: dict[str, str],
    *,
    ledger: Any,
) -> tuple[dict[str, str], ...]:
    """Project reverse-validator failures back onto authored sections.

    The reverse validator works on final-text claim spans, while the Writer
    owns section spans.  Keeping this small projection in the publication
    artifact makes a blocked run actionable: a later Rewrite/Research turn
    can resume only the section containing the unsupported claim instead of
    treating the entire Method as one opaque failure.
    """

    claims_path = validation_paths.get("final_text_claims", "")
    report_path = validation_paths.get("text_evidence_validation", "")
    if not claims_path or not report_path:
        return ()
    try:
        final_claims = load_final_text_claims(claims_path)
        report = load_text_evidence_validation(report_path)
    except (OSError, TypeError, ValueError):
        return ()
    verdict_by_id = {item.atomic_claim_id: item for item in report.verdicts}
    failures: list[dict[str, str]] = []
    for claim in final_claims.atomic_claims:
        verdict = verdict_by_id.get(claim.atomic_claim_id)
        if verdict is None or verdict.status not in {"unsupported", "unverified"}:
            continue
        section_id = ""
        for span in getattr(ledger, "spans", ()):
            if claim.char_start < span.final_end and claim.char_end > span.final_start:
                section_id = str(span.section_id or "")
                break
        reasons = "; ".join(str(item) for item in verdict.deterministic_failures if str(item))
        message = (
            f"Final claim {claim.atomic_claim_id} reverse validation failed"
            + (f": {reasons}" if reasons else "")
        )
        failures.append({
            "claim_id": claim.atomic_claim_id,
            "section_id": section_id,
            "message": message,
        })
    return tuple(failures)


def _section_ledger_from_document_ledger(
    *,
    section_id: str,
    section_text: str,
    accepted: Iterable[tuple[str, str, str]],
    document_text: str,
    document_ledger: Any,
) -> Any:
    """Project a document ledger onto one section before a local Rewrite."""

    if getattr(document_ledger, "final_text_digest", "") != _digest_text(document_text):
        raise ValueError("incumbent_document_authorship_digest_mismatch")
    section_start = 0
    found = False
    for current_id, current_text, _response_ref in accepted:
        if current_id == section_id:
            found = True
            break
        section_start += len(current_text) + 2
    if not found or document_text[section_start:section_start + len(section_text)] != section_text:
        raise ValueError(f"incumbent_section_not_found:{section_id}")
    generated: list[GeneratedTextSpanV1] = []
    for span in getattr(document_ledger, "spans", ()):
        if str(span.section_id or "") != section_id:
            continue
        local_start = span.final_start - section_start
        local_end = span.final_end - section_start
        if local_start < 0 or local_end > len(section_text) or local_end <= local_start:
            raise ValueError(f"incumbent_section_span_out_of_bounds:{section_id}")
        generated.append(GeneratedTextSpanV1(
            span_id=span.source_span_id,
            text=section_text[local_start:local_end],
            owner=span.owner,
            response_ref=span.response_ref,
            section_id=section_id,
            generation_trace_id=span.generation_trace_id,
        ))
    if not generated:
        raise ValueError(f"incumbent_section_ledger_missing:{section_id}")
    ledger = build_final_text_authorship_ledger(section_text, tuple(generated))
    if not ledger.hard_gate_passed:
        raise ValueError("incumbent_section_authorship_gate_failed")
    return ledger


def _llm_provider_value(config: LLMConfig) -> str:
    value = getattr(config.provider, "value", config.provider)
    return str(value or "").strip().lower()


def _method_language_repair_issues_by_section(
    output_by_section: Mapping[str, PublicationMethodSectionOutputV1],
) -> dict[str, list[TextRepairIssueV1]]:
    """Translate the shared Method-language detector into Rewrite issues."""

    issues: dict[str, list[TextRepairIssueV1]] = {}
    for section_id, section_text in find_code_trace_prose_sections(
        list(output_by_section.values())
    ):
        if not section_id:
            continue
        issues.setdefault(section_id, []).append(TextRepairIssueV1(
            sentence_id=f"style:{section_id}:code-trace",
            failure_type="method_language_style",
            offending_fragment=section_text,
            missing_fact_or_relation=(
                "Rewrite from the reader-facing Method perspective; preserve all "
                "supported meaning, qualifiers, numeric values, and formulas."
            ),
            allowed_repair_scope="wording_only",
            attempt=1,
        ))
    return issues


_GENERIC_METHOD_PATTERNS = (
    re.compile(r"\bin this section,? we (?:describe|present|explain)\b", re.I),
    re.compile(r"\bthe design objective is\b", re.I),
    re.compile(r"\bthe mechanism overview\b", re.I),
    re.compile(r"\bthe implementation realization\b", re.I),
    re.compile(r"\bwe now describe the mechanism\b", re.I),
    re.compile(r"\bnext,? we (?:discuss|describe|transition)\b", re.I),
)


def _academic_rewrite_issues_by_section(
    output_by_section: Mapping[str, PublicationMethodSectionOutputV1],
    *,
    claims: AtomicClaimSetV3,
    writer_inputs: Mapping[str, WriterSectionInput],
) -> dict[str, list[TextRepairIssueV1]]:
    """Build promptable academic-revision concerns for the Rewrite owner.

    Rules only identify a scoped concern.  They do not rewrite prose.  The
    Rewrite Agent receives the Writer's original authority context and decides
    how to express a supported claim, caveat a candidate-only point, or remove
    unsupported detail.
    """

    issues = _method_language_repair_issues_by_section(output_by_section)
    claim_by_id = {item.claim_id: item for item in claims.claims}

    # Repeated template rhetoric is a document-level symptom, but repair stays
    # section-scoped.  The later section is assigned to Rewrite so the first
    # valid explanation remains the document's anchor.
    seen_sentence_tokens: list[set[str]] = []
    for section_id, output in output_by_section.items():
        text = str(output.section_markdown or "")
        generic_hits = sum(
            len(pattern.findall(text)) for pattern in _GENERIC_METHOD_PATTERNS
        )
        repeated_with_prior = False
        current_sentence_tokens: list[set[str]] = []
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
            if not sentence.strip() or sentence.lstrip().startswith("#"):
                continue
            tokens = set(_content_tokens(sentence))
            if len(tokens) < 6:
                continue
            if any(
                len(tokens & prior) / max(1, len(tokens | prior)) >= 0.72
                for prior in seen_sentence_tokens
            ):
                repeated_with_prior = True
            current_sentence_tokens.append(tokens)
        seen_sentence_tokens.extend(current_sentence_tokens)
        if generic_hits >= 2 or repeated_with_prior:
            issue_id = f"style:{section_id}:academic-specificity"
            issues.setdefault(section_id, []).append(TextRepairIssueV1(
                sentence_id=issue_id,
                failure_type="method_language_style",
                offending_fragment=text,
                missing_fact_or_relation=(
                    "Remove generic template rhetoric and cross-section restatement. "
                    "Make this section answer its own reader question using only its "
                    "authorized claims or visibly caveated candidate points."
                ),
                allowed_repair_scope="wording_only",
                attempt=1,
            ))

        writer_input = writer_inputs.get(section_id)
        if writer_input is None:
            continue
        if not re.search(r"(?m)^#{1,6}\s+", text):
            issues.setdefault(section_id, []).append(TextRepairIssueV1(
                sentence_id=f"style:{section_id}:section-heading",
                failure_type="method_language_style",
                offending_fragment=text,
                missing_fact_or_relation=(
                    "Rewrite the complete section so its first line is exactly "
                    f"'## {writer_input.heading}'. Preserve the body and all authority "
                    "caveats; do not invent a replacement heading."
                ),
                allowed_repair_scope="wording_only",
                attempt=1,
            ))
        for raw in writer_input.prompt_payload.get("reader_facing_claims") or ():
            if not isinstance(raw, dict) or not raw.get("may_enter_verified"):
                continue
            claim_id = str(raw.get("claim_id") or "")
            claim = claim_by_id.get(claim_id)
            if claim is None or _claim_rendered_in(text, claim):
                continue
            issues.setdefault(section_id, []).append(TextRepairIssueV1(
                sentence_id=f"coverage:{section_id}:{claim_id}",
                failure_type="supported_claim_not_rendered",
                matched_claim_ids=(claim_id,),
                offending_fragment="",
                missing_fact_or_relation=(
                    "Integrate this repository-supported reader-facing claim exactly "
                    "once into a relevant paragraph in natural Method language: "
                    + str(raw.get("paper_statement") or "")
                ),
                allowed_repair_scope="claim_decomposition",
                attempt=1,
            ))
    return issues


def _validation_failure_counts(
    validation_paths: Mapping[str, str],
) -> tuple[int, int, int] | None:
    """Load Pareto dimensions for candidate reverse validation.

    The negative supported count makes "more supported claims" a lower/better
    dimension alongside fewer unsupported and unverified claims.
    """

    path_value = validation_paths.get("text_evidence_validation", "")
    if not path_value or not Path(path_value).is_file():
        return None
    try:
        report = load_text_evidence_validation(path_value)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return (
        int(report.unsupported_claims),
        int(report.unverified_claims),
        -int(report.supported_claims),
    )


def _has_local_validation_repair_issue(
    validation_paths: Mapping[str, str],
) -> bool:
    """Whether reverse validation exposes a safely targetable lexical issue."""

    path_value = validation_paths.get("text_evidence_validation", "")
    if not path_value or not Path(path_value).is_file():
        return False
    try:
        report = load_text_evidence_validation(path_value)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False
    return any(
        issue.allowed_repair_scope not in {"packet_relation", "code_search"}
        for issue in derive_repair_issues(report)
    )


def _rewrite_candidate_has_safe_gain(
    *,
    incumbent_validation_status: str,
    candidate_validation_status: str,
    incumbent_validation_counts: tuple[int, ...] | None,
    candidate_validation_counts: tuple[int, ...] | None,
    incumbent_style_issue_count: int,
    candidate_style_issue_count: int,
) -> bool:
    """Accept a rewrite only when safety is non-regressing and quality improves."""

    if incumbent_validation_status == "passed" and candidate_validation_status != "passed":
        return False
    validation_improved = (
        incumbent_validation_status != "passed" and candidate_validation_status == "passed"
    )
    if incumbent_validation_counts is not None:
        if candidate_validation_counts is None:
            return False
        if any(
            candidate > incumbent
            for candidate, incumbent in zip(
                candidate_validation_counts, incumbent_validation_counts, strict=True
            )
        ):
            return False
        validation_improved = validation_improved or (
            sum(candidate_validation_counts) < sum(incumbent_validation_counts)
        )
    style_improved = candidate_style_issue_count < incumbent_style_issue_count
    return validation_improved or style_improved


def _anchor_text_with_qualifiers(text: str, qualifiers: list[str] | tuple[str, ...]) -> str:
    """Append required qualifiers to an anchor's canonical text.

    The reverse validator checks that every factual sentence preserves its
    required qualifiers (e.g. ``self.cfg.use_dedicated_attention``).  When the
    canonical text omits the condition, the Writer copies only the predicate
    and operands, producing prose that fails ``required_qualifier_missing``.
    Merging qualifiers into the anchor text ensures the Writer sees the full
    authorized wording as a single copyable string.
    """
    cleaned = [str(item).strip() for item in qualifiers if str(item).strip()]
    if not cleaned:
        return text
    return f"{text} when {', '.join(cleaned)}"


def _apply_local_rewrite_repairs(
    *,
    accepted: list[tuple[str, str, str]],
    output_by_section: dict[str, PublicationMethodSectionOutputV1],
    generation_owner_by_section: dict[str, str],
    incumbent_ledger: Any,
    incumbent_final_text: str,
    claims: AtomicClaimSetV3,
    validation_paths: dict[str, str],
    llm_config: LLMConfig,
    rewrite_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None,
    additional_issues_by_section: Mapping[str, list[TextRepairIssueV1]] | None = None,
    writer_context_by_section: Mapping[str, WriterSectionInput] | None = None,
) -> tuple[
    list[tuple[str, str, str]],
    dict[str, PublicationMethodSectionOutputV1],
    dict[str, str],
    list[RepairTransitionV1],
    list[dict[str, Any]],
    list[str],
    Any | None,
]:
    """Run bounded local rewrites for failed final-text verdicts.

    The validator remains the authority for what failed.  This helper only
    translates those verdicts into typed repair issues and delegates the
    exact-span mutation to ``LocalRewriteAgent``.  No deterministic text
    substitution is performed here; rejected, blocked, and no-progress calls
    leave the incumbent section unchanged and are recorded as transitions.
    """

    transitions: list[RepairTransitionV1] = []
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    rewrite_ledger: Any | None = None
    claims_path = validation_paths.get("final_text_claims", "")
    validation_path = validation_paths.get("text_evidence_validation", "")
    additional_issues_by_section = additional_issues_by_section or {}
    writer_context_by_section = writer_context_by_section or {}
    if (not claims_path or not validation_path) and not additional_issues_by_section:
        failures.append("rewrite:validation_artifacts_missing")
        return (
            accepted,
            output_by_section,
            generation_owner_by_section,
            transitions,
            results,
            failures,
            rewrite_ledger,
        )
    final_claims = None
    validation = None
    if claims_path and validation_path:
        try:
            final_claims = load_final_text_claims(claims_path)
            validation = load_text_evidence_validation(validation_path)
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            if not additional_issues_by_section:
                failures.append("rewrite:validation_artifacts_invalid")
                return (
                    accepted,
                    output_by_section,
                    generation_owner_by_section,
                    transitions,
                    results,
                    failures,
                    rewrite_ledger,
                )

    raw_issues = derive_repair_issues(validation) if validation is not None else []
    # One failed atomic fragment often produces both a matching failure and a
    # direct-evidence failure.  Give Rewrite one consolidated task at the most
    # permissive authorized scope instead of duplicating the same span in the
    # prompt.  The original validator codes remain in the diagnostic string.
    scope_rank = {
        "wording_only": 0,
        "sentence_atomicity": 1,
        "claim_decomposition": 2,
        "packet_relation": 3,
        "code_search": 4,
        "drop_or_gap": 5,
    }
    grouped_issues: dict[str, list[TextRepairIssueV1]] = {}
    for issue in raw_issues:
        grouped_issues.setdefault(
            issue.atomic_claim_id or issue.sentence_id, []
        ).append(issue)
    issues: list[TextRepairIssueV1] = []
    for grouped in grouped_issues.values():
        selected = max(
            grouped,
            key=lambda item: scope_rank[item.allowed_repair_scope],
        )
        issues.append(selected.model_copy(update={
            "attempt": 1,
            "missing_fact_or_relation": "; ".join(dict.fromkeys([
                *[
                    f"validator:{item.failure_type}"
                    for item in grouped
                ],
                *[
                    item.missing_fact_or_relation
                    for item in grouped
                    if item.missing_fact_or_relation
                ],
            ])),
        }))
    if not issues and not additional_issues_by_section:
        failures.append("rewrite:no_typed_repair_issues")
        return (
            accepted,
            output_by_section,
            generation_owner_by_section,
            transitions,
            results,
            failures,
            rewrite_ledger,
        )

    atomic_by_id = {
        item.atomic_claim_id: item
        for item in (final_claims.atomic_claims if final_claims is not None else ())
    }
    section_spans: dict[str, tuple[int, int]] = {}
    cursor = 0
    for section_id, text, _response_ref in accepted:
        section_spans[section_id] = (cursor, cursor + len(text))
        cursor += len(text) + 2
    issues_by_section: dict[str, list[Any]] = {}
    issue_context_by_section: dict[str, dict[str, Any]] = {}
    unmapped: set[str] = set()
    claims_by_id = {item.claim_id: item for item in claims.claims}
    for issue in issues:
        if issue.allowed_repair_scope in {"packet_relation", "code_search"}:
            # These scopes belong to the repository/evidence repair owner;
            # sending them to a lexical Rewrite Agent would let wording hide
            # a missing relation or missing source search.
            failures.append(
                f"rewrite:non_local_scope:{issue.atomic_claim_id or issue.sentence_id}:"
                f"{issue.allowed_repair_scope}"
            )
            continue
        atomic = atomic_by_id.get(issue.atomic_claim_id)
        section_id = ""
        if atomic is not None:
            for candidate_section, (start, end) in section_spans.items():
                if start <= atomic.char_start < end:
                    section_id = candidate_section
                    break
        if not section_id:
            unmapped.add(issue.atomic_claim_id or issue.sentence_id)
            continue
        issues_by_section.setdefault(section_id, []).append(issue)
        start, _end = section_spans[section_id]
        section_context = issue_context_by_section.setdefault(section_id, {
            "section_id": section_id,
            "validation_failures": [],
            "atomic_claim_spans": {},
            "authorized_claims": [],
        })
        if atomic is not None:
            section_context["atomic_claim_spans"][atomic.atomic_claim_id] = {
                "start": atomic.char_start - start,
                "end": atomic.char_end - start,
                "text": atomic.text,
            }
        section_context["validation_failures"].append({
            "atomic_claim_id": issue.atomic_claim_id,
            "failure_type": issue.failure_type,
            "allowed_repair_scope": issue.allowed_repair_scope,
            "missing_fact_or_relation": issue.missing_fact_or_relation,
        })
        for claim_id in issue.matched_claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is not None and claim_id not in {
                item.get("claim_id") for item in section_context["authorized_claims"]
            }:
                section_context["authorized_claims"].append(
                    claim.model_dump(mode="json")
                )
    known_section_ids = {section_id for section_id, _text, _ref in accepted}
    for section_id, section_issues in additional_issues_by_section.items():
        if section_id not in known_section_ids:
            failures.append(f"rewrite:unknown_style_section:{section_id}")
            continue
        issues_by_section.setdefault(section_id, []).extend(section_issues)
        section_context = issue_context_by_section.setdefault(section_id, {
            "section_id": section_id,
            "validation_failures": [],
            "atomic_claim_spans": {},
            "authorized_claims": [],
        })
        for issue in section_issues:
            section_context["validation_failures"].append({
                "atomic_claim_id": issue.atomic_claim_id,
                "sentence_id": issue.sentence_id,
                "failure_type": issue.failure_type,
                "allowed_repair_scope": issue.allowed_repair_scope,
                "missing_fact_or_relation": issue.missing_fact_or_relation,
            })
        output = output_by_section.get(section_id)
        for claim_id in (output.used_claim_ids if output is not None else ()):
            claim = claims_by_id.get(claim_id)
            if claim is not None and claim_id not in {
                item.get("claim_id") for item in section_context["authorized_claims"]
            }:
                section_context["authorized_claims"].append(
                    claim.model_dump(mode="json")
                )
    for section_id, writer_input in writer_context_by_section.items():
        if section_id not in known_section_ids:
            continue
        section_context = issue_context_by_section.setdefault(section_id, {
            "section_id": section_id,
            "validation_failures": [],
            "atomic_claim_spans": {},
            "authorized_claims": [],
        })
        # Rewrite receives the Writer's complete semantic input, not just a
        # failed code-like sentence.  This is what lets it choose among a
        # supported academic rendering, a visibly caveated author narrative,
        # and deletion of an unsupported positive assertion.
        section_context["writer_authority_context"] = dict(
            writer_input.prompt_payload
        )
        section_context["writer_heading"] = writer_input.heading
        output = output_by_section.get(section_id)
        section_context["writer_binding_metadata"] = {
            "used_argument_unit_ids": list(
                output.used_argument_unit_ids if output is not None else ()
            ),
            "used_claim_ids": list(
                output.used_claim_ids if output is not None else ()
            ),
            "used_equation_ids": list(
                output.used_equation_ids if output is not None else ()
            ),
            "used_configuration_ids": list(
                output.used_configuration_ids if output is not None else ()
            ),
        }
    if unmapped:
        failures.extend(
            f"rewrite:unmapped_atomic_claim:{item}" for item in sorted(unmapped)
        )

    # Snapshot the incumbent owner before this helper mutates the owner map.
    # A local ledger is built against this exact incumbent span and then
    # replayed with the Rewrite Agent's patch response reference.
    incumbent_owner_by_section = dict(generation_owner_by_section)
    accepted_by_id = {
        section_id: (text, response_ref)
        for section_id, text, response_ref in accepted
    }
    incumbent_section_ledgers: dict[str, Any] = {}
    for section_id, (section_text, section_ref) in accepted_by_id.items():
        try:
            incumbent_section_ledgers[section_id] = _section_ledger_from_document_ledger(
                section_id=section_id,
                section_text=section_text,
                accepted=accepted,
                document_text=incumbent_final_text,
                document_ledger=incumbent_ledger,
            )
        except (TypeError, ValueError):
            # Keep backwards compatibility for callers that invoke this
            # private repair helper with a legacy blanket Writer ledger.
            incumbent_section_ledgers[section_id] = build_final_text_authorship_ledger(
                section_text,
                (GeneratedTextSpanV1(
                    span_id=f"{incumbent_owner_by_section[section_id]}:{section_id}",
                    text=section_text,
                    owner=incumbent_owner_by_section[section_id],
                    response_ref=section_ref,
                    section_id=section_id,
                    generation_trace_id=section_ref,
                ),),
            )
    rewritten_ledger_by_section: dict[str, Any] = {}
    try:
        configured_rewrite_attempts = int(
            os.environ.get("CODE2PAPER_LOCAL_REWRITE_MAX_ATTEMPTS", "2")
        )
    except ValueError:
        configured_rewrite_attempts = 2
    max_rewrite_attempts = max(1, min(configured_rewrite_attempts, 4))
    for section_id, section_issues in issues_by_section.items():
        incumbent_text, incumbent_ref = accepted_by_id[section_id]
        working_text = incumbent_text
        working_ref = incumbent_ref
        working_ledger = incumbent_section_ledgers[section_id]
        applied_any = False
        for attempt in range(1, max_rewrite_attempts + 1):
            attempt_issues = [
                issue.model_copy(update={"attempt": attempt})
                for issue in section_issues
            ]
            attempt_context = dict(issue_context_by_section.get(section_id, {}))
            attempt_context["attempt"] = attempt
            attempt_context["max_attempts"] = max_rewrite_attempts
            if attempt > 1:
                prior_result = results[-1].get("result", {}) if results else {}
                attempt_context["prior_attempt_feedback"] = {
                    "status": prior_result.get("status", ""),
                    "blocked_reason": prior_result.get("blocked_reason", ""),
                    "patch_failures": prior_result.get("patch_failures", ()),
                }
                attempt_context["prior_attempt_instruction"] = (
                    "Re-audit the current incumbent and address the assigned issues. The prior "
                    "attempt was incomplete or rejected by the patch/readability contract; use "
                    "prior_attempt_feedback to correct it. Return one non-overlapping full "
                    "paragraph or full-section patch when nested patches caused overlap. Preserve "
                    "a readable candidate paragraph for typed candidate points instead of "
                    "deleting the section. Return incomplete=false only when no further safe edit "
                    "is needed."
                )
            result = LocalRewriteAgent(
                config=llm_config,
                caller=rewrite_caller,
            ).rewrite(
                working_text,
                issues=attempt_issues,
                section_context=attempt_context,
            )
            if result.status == "applied":
                try:
                    patches = (
                        tuple(result.output.patches)
                        if result.output is not None else ()
                    )
                    working_ledger = rewrite_final_text_authorship_ledger(
                        incumbent_text=working_text,
                        candidate_text=result.candidate_text,
                        incumbent_ledger=working_ledger,
                        patches=patches,
                        response_ref=result.response_ref,
                        generation_trace_id=result.response_ref,
                    )
                except (TypeError, ValueError) as exc:
                    result = result.model_copy(update={
                        "status": "rejected",
                        "candidate_digest": result.incumbent_digest,
                        "candidate_text": working_text,
                        "blocked_reason": f"rewrite_authorship_failed:{exc}",
                        "patch_failures": tuple([
                            *result.patch_failures,
                            "authorship_reconstruction_failed",
                        ]),
                    })
                else:
                    applied_any = True
                    working_text = result.candidate_text
                    working_ref = result.response_ref or working_ref
                    rewritten_ledger_by_section[section_id] = working_ledger
            results.append({
                "section_id": section_id,
                "attempt": attempt,
                "result": result.model_dump(mode="json"),
            })
            transitions.append(RepairTransitionV1(
                transition_id=f"local-rewrite:{section_id}:attempt-{attempt}",
                strategy="local_rewrite",
                owner="rewrite",
                attempt=attempt,
                issue_ids=tuple(dict.fromkeys(
                    issue.atomic_claim_id or issue.sentence_id
                    for issue in attempt_issues
                )),
                incumbent_digest=result.incumbent_digest,
                candidate_digest=result.candidate_digest,
                status=result.status,
                reason=result.blocked_reason,
                artifact_refs=((result.response_ref,) if result.response_ref else ()),
            ))
            wants_another_attempt = bool(
                (
                    result.status == "applied"
                    and result.output is not None
                    and result.output.incomplete
                )
                or (
                    result.status == "rejected"
                    and result.blocked_reason in {
                        "rewrite_patch_contract_failed",
                        "rewrite_candidate_not_readable",
                    }
                )
            )
            if not wants_another_attempt:
                if result.status != "applied" and not applied_any:
                    failures.append(f"rewrite:{section_id}:{result.status}")
                break
            if attempt == max_rewrite_attempts:
                failures.append(f"rewrite:{section_id}:attempt_budget_exhausted")
        if applied_any:
            accepted_by_id[section_id] = (working_text, working_ref)
            generation_owner_by_section[section_id] = "rewrite"
            output = output_by_section.get(section_id)
            if output is not None:
                output_by_section[section_id] = output.model_copy(update={
                    "section_markdown": working_text,
                })

    rewritten = [
        (section_id, accepted_by_id[section_id][0], accepted_by_id[section_id][1])
        for section_id, _text, _response_ref in accepted
    ]
    if rewritten_ledger_by_section:
        # Reassemble generated spans in document order.  Section separators
        # are whitespace and therefore need no owner, while every lexical
        # token remains covered by Writer/Editor or the exact Rewrite patch.
        generated_spans: list[GeneratedTextSpanV1] = []
        for section_id, text, response_ref in rewritten:
            local_ledger = rewritten_ledger_by_section.get(section_id)
            if local_ledger is None:
                local_ledger = incumbent_section_ledgers.get(section_id)
            if local_ledger is None:
                generated_spans.append(GeneratedTextSpanV1(
                    span_id=f"{incumbent_owner_by_section.get(section_id, generation_owner_by_section[section_id])}:{section_id}",
                    text=text,
                    owner=incumbent_owner_by_section.get(section_id, generation_owner_by_section[section_id]),
                    response_ref=response_ref,
                    section_id=section_id,
                    generation_trace_id=response_ref,
                ))
                continue
            for span in local_ledger.spans:
                generated_spans.append(GeneratedTextSpanV1(
                    span_id=f"{span.source_span_id}:{section_id}",
                    text=text[span.final_start:span.final_end],
                    owner=span.owner,
                    response_ref=span.response_ref,
                    section_id=section_id,
                    generation_trace_id=span.generation_trace_id,
                ))
        rewrite_ledger = build_final_text_authorship_ledger(
            "\n\n".join(text for _section_id, text, _response_ref in rewritten),
            tuple(generated_spans),
        )
    return (
        rewritten,
        output_by_section,
        generation_owner_by_section,
        transitions,
        results,
        failures,
        rewrite_ledger,
    )


def _write_rewrite_transitions(
    *,
    out_root: str | Path,
    initial_validation_status: str,
    transitions: list[RepairTransitionV1],
    results: list[dict[str, Any]],
    failures: list[str],
) -> tuple[str, str, str]:
    path = method_output(Path(out_root), "publication_rewrite_transitions_v1")
    payload = {
        "schema_version": "1.0",
        "initial_validation_status": initial_validation_status,
        "transitions": [item.model_dump(mode="json") for item in transitions],
        "results": results,
        "failures": list(failures),
    }
    digest = _digest_json(payload)
    _atomic_write_text(path,
        json.dumps({**payload, "content_digest": digest}, ensure_ascii=False, indent=2)
        + "\n",
    )
    results_path = method_output(Path(out_root), "publication_rewrite_results_v1")
    results_payload = {
        "schema_version": "1.0",
        "results": results,
        "content_digest": digest,
    }
    _atomic_write_text(results_path,
        json.dumps(results_payload, ensure_ascii=False, indent=2) + "\n",
    )
    return str(path), str(results_path), digest


_INPUT_PREDICATES = frozenset({
    "loads_weights", "reads", "stores", "writes", "constructs", "initializes",
})
_OUTPUT_PREDICATES = frozenset({"returns", "emits", "outputs", "writes_back"})
_CONDITION_PREDICATES = frozenset({
    "branches_on", "selects_top_k", "sorts_by", "propagates", "guards_on",
})
_TRANSFORM_PREDICATES = frozenset({
    "computes", "computes_formula", "concatenates", "normalizes", "reduces",
    "attends", "calls",
})


def _request_matches_authority_proof(
    request: WritingResearchRequestV1,
    proof: MoveAuthorityProofV1,
) -> bool:
    """Require one callback request to match one closed move proof exactly."""

    return bool(
        request.section_id == proof.section_id
        and request.argument_unit_id in proof.argument_unit_ids
        and request.missing_rhetorical_move == proof.move
        and request.required_authority_lane == proof.required_authority_lane
    )


def _writer_section_inputs(
    *,
    plan: MethodSectionPlanV2,
    claims: AtomicClaimSetV3,
    equations: EquationClaimSetV1,
    configurations: ConfigurationClaimSetV1,
    formalization: FormalizationResultV1 | None = None,
    facts: Any | None = None,
    evidence_packets_v3: Any | None = None,
    callback_bundle: WritingResearchCallbackBundleV1 | None = None,
    callback_artifacts: dict[str, tuple[WritingResearchCallbackArtifactV1, ...]] | None = None,
) -> list[WriterSectionInput]:
    """Build the Writer-facing projection for each planned section.

    The projection is derived from the Architect's persisted typed semantic
    frames and move authority proofs — the Writer never re-derives a frame.
    ``argument_flow`` carries the closed typed frames (subject, predicate,
    every operand, conditions, edges) and ``validation_constraints`` carries
    the exact canonical wording/qualifier/formula/config tokens that the
    reverse validator enforces; the constraints are NOT a sentence plan.
    """

    def writer_graph_payload(graph: Any) -> dict[str, Any]:
        raw = graph.model_dump(mode="json")
        return {
            "section_id": raw.get("section_id", ""),
            "heading": raw.get("heading", ""),
            "argument_unit_ids": list(raw.get("argument_unit_ids") or ()),
            "moves": [
                {
                    "move": move.get("move", ""),
                    "argument_unit_ids": list(move.get("argument_unit_ids") or ()),
                    "paragraph_budget": move.get("paragraph_budget", 0),
                    "information_budget": move.get("information_budget", 0.0),
                    "allowed_authority_lanes": list(
                        move.get("allowed_authority_lanes") or ()
                    ),
                    "required": bool(move.get("required", False)),
                }
                for move in (raw.get("moves") or ())
                if isinstance(move, dict)
            ],
            "dependencies": list(raw.get("dependencies") or ()),
            "unresolved_inputs": list(raw.get("unresolved_inputs") or ()),
            "depth_budget": raw.get("depth_budget", 0),
            "page_budget": raw.get("page_budget", 0.0),
            "incomplete": bool(raw.get("incomplete", False)),
        }

    def writer_unit_payload(unit: Any) -> dict[str, Any]:
        raw = unit.model_dump(mode="json")
        return {
            "argument_unit_id": raw.get("argument_unit_id", ""),
            "section_role": raw.get("section_role", ""),
            "claim_ids": list(raw.get("claim_ids") or ()),
            "equation_ids": list(raw.get("equation_ids") or ()),
            "configuration_ids": list(raw.get("configuration_ids") or ()),
            "allowed_expository_moves": list(raw.get("allowed_expository_moves") or ()),
            "unresolved_inputs": list(raw.get("unresolved_inputs") or ()),
            "authority_lanes": list(raw.get("authority_lanes") or ()),
            "source_artifact_ids": list(raw.get("source_artifact_ids") or ()),
            "supported": bool(raw.get("supported", False)),
            "information_weight": raw.get("information_weight", 0.0),
        }

    def writer_claim_payload(claim: Any) -> dict[str, Any]:
        raw = claim.model_dump(mode="json")
        return {
            "claim_id": raw.get("claim_id", ""),
            "canonical_text": raw.get("canonical_text", ""),
            "claim_kind": raw.get("claim_kind", "implementation_behavior"),
            "required_qualifiers": list(raw.get("required_qualifiers") or ()),
            "allowed_wording_boundary": raw.get("allowed_wording_boundary", ""),
            "status": raw.get("status", "unsupported"),
        }

    def writer_equation_payload(equation: Any) -> dict[str, Any]:
        raw = equation.model_dump(mode="json")
        return {
            "equation_id": raw.get("equation_id", ""),
            "expression": raw.get("expression", ""),
            "concrete_expression": _binding_concrete_expression(equation),
            "prose_claim_id": raw.get("prose_claim_id", ""),
            "conditions": list(raw.get("conditions") or ()),
            "operation_predicates": list(raw.get("operation_predicates") or ()),
            "operation_descriptors": list(raw.get("operation_descriptors") or ()),
            "validation_status": raw.get("validation_status", "rejected"),
        }

    def writer_configuration_payload(configuration: Any) -> dict[str, Any]:
        raw = configuration.model_dump(mode="json")
        return {
            "configuration_id": raw.get("configuration_id", ""),
            "key": raw.get("key", ""),
            "value": raw.get("value"),
            "state": raw.get("state", "unreachable"),
            "conditions": list(raw.get("conditions") or ()),
            "authority_lane": raw.get("authority_lane", "configuration_resolved"),
            "active": bool(raw.get("active", False)),
            "unresolved_reason": raw.get("unresolved_reason", ""),
        }

    def writer_formalization_payload(value: dict[str, Any]) -> dict[str, Any]:
        symbols = [
            {
                "symbol": item.get("symbol", ""),
                "meaning": item.get("meaning", ""),
                "conditions": list(item.get("conditions") or ()),
            }
            for item in (value.get("symbols") or ())
            if isinstance(item, dict)
        ]
        equations = [
            {
                "equation_id": item.get("equation_id", ""),
                "expression": item.get("expression", ""),
                "conditions": list(item.get("conditions") or ()),
                "operation_descriptors": list(item.get("operation_descriptors") or ()),
            }
            for item in (value.get("equations") or ())
            if isinstance(item, dict)
        ]
        obligations = [
            {
                "proof_obligation_id": item.get("proof_obligation_id", ""),
                "statement": item.get("statement", ""),
                "assumptions": list(item.get("assumptions") or ()),
                "conclusion": item.get("conclusion", ""),
                "derivation_steps": list(item.get("derivation_steps") or ()),
                "status": item.get("status", "unproved"),
            }
            for item in (value.get("proof_obligations") or ())
            if isinstance(item, dict)
        ]
        return {
            "symbols": symbols,
            "equations": equations,
            "proof_obligations": obligations,
            "proposal_items": [
                {
                    "kind": item.get("kind", ""),
                    "statement": item.get("statement", ""),
                    "fact_ids": list(item.get("fact_ids") or ()),
                    "equation_ids": list(item.get("equation_ids") or ()),
                    "conditions": list(item.get("conditions") or ()),
                    "symbols": list(item.get("symbols") or ()),
                }
                for item in (value.get("proposal_items") or ())
                if isinstance(item, dict)
            ],
            "risks": [
                {
                    "risk_id": item.get("risk_id", ""),
                    "kind": item.get("kind", ""),
                    "blocking": bool(item.get("blocking", False)),
                    "limitations": list(item.get("limitations") or ()),
                }
                for item in (value.get("risks") or ())
                if isinstance(item, dict)
            ],
        }

    claim_by_id = {item.claim_id: item for item in claims.claims}
    equation_by_id = {item.equation_id: item for item in equations.equations}
    configuration_by_id = {item.configuration_id: item for item in configurations.claims}
    unit_by_id = {item.argument_unit_id: item for item in plan.argument_units}
    fact_by_id = {
        str(fact.fact_id): fact for fact in (facts.facts if facts is not None else ())
    }
    relation_by_id = {
        str(relation.relation_id): relation
        for packet in (evidence_packets_v3.packets if evidence_packets_v3 is not None else ())
        for relation in packet.relations
    }
    callback_artifacts = callback_artifacts or {}
    callback_requests = {
        request.request_id: request
        for request in (callback_bundle.requests if callback_bundle is not None else ())
    }
    proofs_by_key = plan.proofs_by_key()
    result: list[WriterSectionInput] = []
    for graph in plan.sections:
        units = [unit_by_id[item] for item in graph.argument_unit_ids if item in unit_by_id]
        claim_ids = tuple(dict.fromkeys(claim_id for unit in units for claim_id in unit.claim_ids))
        equation_ids = tuple(dict.fromkeys(item for unit in units for item in unit.equation_ids))
        configuration_ids = tuple(dict.fromkeys(item for unit in units for item in unit.configuration_ids))
        section_fact_ids = {
            fact_id
            for claim_id in claim_ids
            for fact_id in (
                claim_by_id[claim_id].fact_ids
                if claim_id in claim_by_id
                else ()
            )
        }
        section_formalization = {
            "symbols": [
                symbol.model_dump(mode="json")
                for symbol in (formalization.symbols if formalization is not None else ())
                if not section_fact_ids or section_fact_ids.intersection(symbol.fact_ids)
            ],
            "equations": [
                equation
                for equation in (formalization.equations if formalization is not None else ())
                if str(equation.get("equation_id") or "") in set(equation_ids)
            ],
            "proposal_items": [
                item.model_dump(mode="json")
                for item in (formalization.proposal_items if formalization is not None else ())
                if set(item.fact_ids).intersection(section_fact_ids)
                or set(item.equation_ids).intersection(set(equation_ids))
            ],
            "proof_obligations": [
                proof.model_dump(mode="json")
                for proof in (formalization.proof_obligations if formalization is not None else ())
                if set(proof.supporting_fact_ids).intersection(section_fact_ids)
            ],
            "risks": [
                risk.model_dump(mode="json")
                for risk in (formalization.risks if formalization is not None else ())
                if not section_fact_ids or set(risk.fact_ids).intersection(section_fact_ids)
            ],
        }
        required_moves = tuple(move.move for move in graph.moves if move.required)
        reader_facing_claims = _section_reader_facing_claims(
            graph=graph,
            units=units,
            claim_by_id=claim_by_id,
        )
        section_candidate_points = _section_candidate_points(
            graph,
            units,
            fact_by_id=fact_by_id,
        )
        # Typed semantic frames come from the Architect's plan units; the
        # Writer serializes them without re-derivation, so both sides observe
        # the identical frame digests.
        section_frames = [
            unit.semantic_frame.model_dump(mode="json")
            for unit in units
            if unit.semantic_frame is not None
        ]
        section_frame_digests = {
            str(unit.argument_unit_id): str(unit.semantic_frame.content_digest)
            for unit in units
            if unit.semantic_frame is not None
        }
        # Move authority comes from the persisted typed proofs; fulfilled
        # artifacts upgrade an open/external proof to ``fulfilled`` with the
        # digest-pinned artifact ids and digest recorded.
        move_authority: dict[str, dict[str, Any]] = {}
        for move in graph.moves:
            proof = proofs_by_key.get((graph.section_id, move.move))
            if proof is None:
                continue
            fulfillment_ids = list(proof.fulfillment_artifact_ids)
            fulfillment_digest = proof.fulfillment_artifact_digest
            state = proof.state
            proof_request_ids = tuple(proof.request_ids)
            for request_id in proof_request_ids:
                request = callback_requests.get(request_id)
                if request is None:
                    raise ValueError(
                        f"proof {graph.section_id}/{move.move} references unknown callback request {request_id}"
                    )
                if not _request_matches_authority_proof(request, proof):
                    raise ValueError(
                        f"proof {graph.section_id}/{move.move} request binding mismatch {request_id}"
                    )
            matched_requests = tuple(
                request
                for request in callback_requests.values()
                if _request_matches_authority_proof(request, proof)
            )
            matched_request_ids = tuple(request.request_id for request in matched_requests)
            if proof_request_ids and set(proof_request_ids) != set(matched_request_ids):
                raise ValueError(
                    f"proof {graph.section_id}/{move.move} callback request set is not closed"
                )
            matched_artifacts = [
                artifact
                for request in matched_requests
                if request.status == "fulfilled"
                for request_id in (request.request_id,)
                for artifact in callback_artifacts.get(request_id, ())
            ]
            if matched_artifacts:
                state = "fulfilled"
                fulfillment_ids = tuple(dict.fromkeys([
                    *fulfillment_ids,
                    *[artifact.artifact_id for artifact in matched_artifacts],
                ]))
                fulfillment_digest = _digest_json([
                    {
                        "artifact_id": artifact.artifact_id,
                        "request_id": artifact.request_id,
                        "artifact_digest": artifact.artifact_digest,
                    }
                    for artifact in sorted(matched_artifacts, key=lambda item: item.artifact_id)
                ])
            if proof.state == "fulfilled":
                if not proof_request_ids or not matched_artifacts:
                    raise ValueError(
                        f"fulfilled proof {graph.section_id}/{move.move} lacks its callback artifacts"
                    )
                artifact_ids = {artifact.artifact_id for artifact in matched_artifacts}
                if artifact_ids != set(proof.fulfillment_artifact_ids):
                    raise ValueError(
                        f"fulfilled proof {graph.section_id}/{move.move} artifact IDs are not closed"
                    )
                if proof.fulfillment_artifact_digest != fulfillment_digest:
                    raise ValueError(
                        f"fulfilled proof {graph.section_id}/{move.move} artifact digest mismatch"
                    )
            move_authority[move.move] = {
                "required": bool(move.required),
                "allowed_authority_lanes": (
                    [proof.required_authority_lane]
                    if proof.required_authority_lane
                    else list(move.allowed_authority_lanes)
                ),
                "state": state,
                "anchor_ids": list(proof.anchor_ids),
                "unresolved_obligation_ids": list(proof.unresolved_obligation_ids),
                "required_authority_lane": proof.required_authority_lane,
                "owner_route": proof.owner_route,
                "request_ids": list(matched_request_ids or proof_request_ids),
                "fulfillment_artifact_ids": list(fulfillment_ids),
                "fulfillment_artifact_digest": fulfillment_digest,
                "candidate_symbols_or_terms": _proof_candidates(
                    proof, section_frames, equation_ids, configuration_ids,
                ),
            }
        writer_graph = writer_graph_payload(graph)
        writer_claims = [
            writer_claim_payload(claim_by_id[item])
            for item in claim_ids
            if item in claim_by_id
        ]
        writer_equations = [
            writer_equation_payload(equation_by_id[item])
            for item in equation_ids
            if item in equation_by_id
        ]
        writer_configurations = [
            writer_configuration_payload(configuration_by_id[item])
            for item in configuration_ids
            if item in configuration_by_id
        ]
        # Validation constraints carry the exact canonical tokens the reverse
        # validator enforces.  They are a validation-only channel: the Writer
        # renders operations from ``argument_flow`` and never treats these
        # records as a sentence plan.
        validation_constraints = {
            "claims": [
                {
                    "claim_id": item["claim_id"],
                    "canonical_text": item["canonical_text"],
                    "required_qualifiers": item["required_qualifiers"],
                    "allowed_wording_boundary": item["allowed_wording_boundary"],
                    "validation_only": True,
                }
                for item in writer_claims
                if item["status"] in {"supported", "partial"}
                and item["canonical_text"].strip()
            ],
            "equations": [
                {
                    "equation_id": item["equation_id"],
                    "expression": item["concrete_expression"] or item["expression"],
                    "conditions": item["conditions"],
                    "validation_only": True,
                }
                for item in writer_equations
                if item["validation_status"] == "supported"
                and (item["expression"].strip() or item["concrete_expression"].strip())
            ],
            "configurations": [
                {
                    "configuration_id": item["configuration_id"],
                    "key": item["key"],
                    "value": item["value"],
                    "conditions": item["conditions"],
                    "validation_only": True,
                }
                for item in writer_configurations
                if item["active"] and item["state"] in {"actual", "default", "conditional"}
            ],
        }
        anchored_required_moves = [
            name for name, value in move_authority.items()
            if value["required"] and value["state"] in {"anchored", "fulfilled"}
        ]
        unanchored_required_moves = [
            name for name, value in move_authority.items()
            if value["required"] and value["state"] in {"open", "external_pending"}
        ]
        expository_bridge_required_moves = [
            name for name, value in move_authority.items()
            if value["required"] and value["state"] == "bridge"
        ]
        move_by_name = {move.move: move for move in graph.moves}

        def callback_argument_unit_id(move_name: str) -> str:
            move_spec = move_by_name.get(move_name)
            unit_ids = tuple(
                (move_spec.argument_unit_ids if move_spec is not None else ())
                or graph.argument_unit_ids
                or ()
            )
            return str(unit_ids[0]) if unit_ids else ""

        callback_request_prototypes = [
            {
                "request_id": f"request:{graph.section_id}:{move_name}",
                "section_id": graph.section_id,
                "argument_unit_id": callback_argument_unit_id(move_name),
                "missing_rhetorical_move": move_name,
                "exact_question": (
                    "Replace this with one precise missing-information question "
                    "needed to write the unresolved move."
                ),
                "required_authority_lane": str(
                    move_authority[move_name].get("required_authority_lane") or ""
                ),
                "candidate_symbols_or_terms": list(
                    move_authority[move_name].get("candidate_symbols_or_terms") or ()
                ),
                "current_known_facts": [],
                "why_needed_for_reader": (
                    "The section has a required move that lacks an authorized "
                    "factual anchor."
                ),
                "priority": "high",
                "status": "open",
            }
            for move_name in unanchored_required_moves
            if move_name in move_authority
        ]
        result.append(WriterSectionInput(
            section_id=graph.section_id,
            heading=graph.heading,
            publication_mode=True,
            argument_graph=writer_graph,
            prompt_payload={
                "audience": plan.audience,
                "heading": graph.heading,
                "section": writer_graph,
                "argument_units": [writer_unit_payload(unit) for unit in units],
                "formalization": writer_formalization_payload(section_formalization),
                "argument_flow": {
                    "semantic_frames": section_frames,
                    "frame_digests": section_frame_digests,
                },
                "validation_constraints": validation_constraints,
                "reader_facing_claims": reader_facing_claims,
                "section_candidate_points": section_candidate_points,
                "paper_term_hints": [
                    item["paper_statement"] for item in reader_facing_claims
                    if item["paper_statement"].strip()
                ],
                "required_rhetorical_moves": list(required_moves),
                "anchored_required_moves": anchored_required_moves,
                "unanchored_required_moves": unanchored_required_moves,
                "expository_bridge_required_moves": expository_bridge_required_moves,
                "callback_required": bool(unanchored_required_moves),
                "response_protocol": {
                    "write_only_anchored_required_moves": True,
                    "combine_anchors_into_connected_operations": True,
                    "claim_free_expository_bridge_allowed": True,
                    "do_not_write_optional_moves_without_an_anchor": True,
                    **({
                        "callback_request_shape": {
                            "request_id": "request:<section_id>:<move>",
                            "section_id": graph.section_id,
                            "argument_unit_id": "one id from the move's argument_unit_ids",
                            "missing_rhetorical_move": "one item from unanchored_required_moves",
                            "exact_question": "one precise missing-information question",
                            "required_authority_lane": "the lane listed in move_authority for that move",
                            "candidate_symbols_or_terms": "copy the move_authority candidate_symbols_or_terms list; local executable/configuration/formal lanes require it to be non-empty",
                            "current_known_facts": [],
                            "why_needed_for_reader": "why this missing information matters for this section",
                            "priority": "high",
                            "status": "open",
                        },
                        "callback_request_prototypes": callback_request_prototypes,
                    } if unanchored_required_moves else {}),
                },
                "content_first_instruction": (
                    "Write required moves listed in anchored_required_moves and the "
                    "editable candidate narrative in section_candidate_points. Candidate "
                    "points are authorized only as visibly caveated author-intent, partial, "
                    "mismatch, external, or formalization narrative; they are not repository "
                    "implementation facts. Group related candidate points into coherent "
                    "paragraphs in their argument-unit order and state each point once. "
                    "Use reader_facing_claims as the sentence plan: every factual "
                    "sentence should express one of those paper-level statements in "
                    "your own Method language. code_binding_terms exist only to "
                    "preserve factual binding; prefer paper terms over raw "
                    "identifiers, and when a raw identifier must be mentioned put it "
                    "in a short implementation clause, not as the grammatical center "
                    "of the sentence. Do not copy validation_constraints canonical "
                    "text as prose: that channel is for checking meaning, not for "
                    "choosing wording. Render each operation from the argument_flow "
                    "semantic frames (subject, predicate, operands, conditions, "
                    "edges) as a normal Method sentence in your own words, from the "
                    "reader's perspective: write what the operation does, not the "
                    "record itself. Never copy an example sentence from the skill or "
                    "the prompt into the section. You MAY combine several slots that "
                    "form one connected operation flow into a single sentence using "
                    "sequence connectives (then, after, first, before, once); keep "
                    "every operand and predicate meaning attributable to one of the "
                    "slots. The same operation may complete mechanism overview, algorithm "
                    "or data flow, and implementation realization simultaneously: write "
                    "that operation once, then list all genuinely completed moves only in "
                    "completed_rhetorical_moves. Never generate three paraphrases of one "
                    "fact merely to satisfy three moves. For multiple argument units, use "
                    "paragraph breaks for conceptual subtopics; do not collapse them into a "
                    "generic overview. The validation_constraints channel lists the exact "
                    "canonical wording, qualifiers, equations, and configuration "
                    "values the reverse validator will enforce; preserve required "
                    "qualifiers, equations, numeric values, and semantic roles, but "
                    "do not preserve raw code token spelling unless it is the "
                    "paper-level term or an implementation-realization detail, and "
                    "never emit a constraint record itself as a sentence. Write a "
                    "reader_facing_claim with requires_caveat=true only as candidate "
                    "narrative. Preserve its paper_statement but visibly frame its "
                    "authority with wording such as 'we aim', 'our intended design', "
                    "'repository evidence partially supports', an explicit mismatch, "
                    "or 'pending confirmation'. Never add implementation details from "
                    "a neighboring section or from supported_fragments that are not "
                    "bound as a reader_facing_claim. You may add at most one claim-free "
                    "organization or transition sentence when the logical connection "
                    "is not already clear; do not use stock openings such as 'In this "
                    "section', 'The design objective is', 'The mechanism overview', "
                    "'The implementation realization', or 'Next, we discuss'. Such "
                    "scaffolding must not contain any claim/equation/configuration "
                    "operand, behavior predicate, number, or formula. Begin "
                    "section_markdown with "
                    "exactly one Markdown H2 heading copied from the supplied "
                    "heading field (format: '## <heading>'), then write the first "
                    "anchored Method sentence. The heading is section structure, "
                    "not factual evidence. Never "
                    "write a sentence that names rhetorical moves or recaps the "
                    "section organization. An equation constraint is covered by its "
                    "prose claim sentence (prose_claim_id): write that claim "
                    "sentence, bind both the claim id and the equation id, and "
                    "never emit a separate equation sentence. Never write 'The "
                    "expression ...', 'The equation ... is computed', '... "
                    "corresponds to the selected code operations', or any sentence "
                    "that references an id. "
                    + (
                        "For every move in "
                        "unanchored_required_moves, leave it unresolved and emit exactly one "
                        "callback request using response_protocol.callback_request_shape "
                        "with the move's required_authority_lane from move_authority. "
                        if unanchored_required_moves else ""
                    )
                    + "A move listed in grounding_contract.expository_bridge_allowed_moves "
                    "may instead be completed by one claim-free organization sentence "
                    "without a callback."
                ),
                "grounding_contract": {
                    "positive_fact_source": "argument_flow_semantic_frames_only",
                    "required_anchor_fields": [
                        "argument_flow.semantic_frames[].slots[].subject",
                        "argument_flow.semantic_frames[].slots[].predicate",
                        "argument_flow.semantic_frames[].slots[].operands",
                        "argument_flow.semantic_frames[].slots[].conditions",
                        "argument_flow.semantic_frames[].slots[].produced_entities",
                        "argument_flow.semantic_frames[].edges[]",
                        "validation_constraints.claims[].required_qualifiers",
                        "validation_constraints.equations[].expression",
                        "validation_constraints.configurations[].key",
                    ],
                    "organization_only_fields": [
                        "method_name", "audience", "heading", "reader_question",
                        "research_question", "design_objective", "moves",
                    ],
                    "organization_only_moves": sorted(_ORGANIZATION_ONLY_RHETORICAL_MOVES),
                    "expository_bridge_allowed_moves": sorted({
                        name for name, value in move_authority.items()
                        if value["state"] == "bridge"
                    }),
                    "unanchored_move_action": "emit_one_scoped_writing_research_request_and_leave_move_unresolved",
                    "move_authority": move_authority,
                    "unanchored_required_moves": unanchored_required_moves,
                    "callback_request_prototypes": callback_request_prototypes,
                    "callback_required": any(
                        value["required"] and value["state"] in {"open", "external_pending"}
                        for value in move_authority.values()
                    ),
                    **({
                        "callback_response_shape": {
                            "new_research_requests": callback_request_prototypes
                        }
                    } if any(
                        value["required"] and value["state"] in {"open", "external_pending"}
                        for value in move_authority.values()
                    ) else {}),
                    "prohibited_unless_explicitly_authorized": [
                        "purpose", "benefit", "robustness", "consistency", "determinism",
                        "causality", "performance", "novelty",
                    ],
                },
                "binding_contract": {
                    "used_argument_unit_ids": list(graph.argument_unit_ids),
                    "used_claim_ids": list(claim_ids),
                    "used_equation_ids": list(equation_ids),
                    "used_configuration_ids": list(configuration_ids),
                    "required_rhetorical_moves": list(required_moves),
                    "completed_rhetorical_moves": anchored_required_moves,
                    "anchored_required_rhetorical_moves": anchored_required_moves,
                    "unanchored_required_rhetorical_moves": unanchored_required_moves,
                    "content_first": True,
                },
            },
        ))
    return result


def _section_reader_facing_claims(
    *,
    graph: Any,
    units: list[Any],
    claim_by_id: dict[str, Any],
) -> list[dict[str, Any]]:
    """Paper-language sentence plan for one section (W package).

    Claim-backed units expose their canonical statement as the paper
    statement with extracted code binding terms; candidate-only units expose
    their organization statement with ``requires_caveat=True`` so the Writer
    plans sentences from reader-facing claims instead of code records.
    """

    claims_out: list[dict[str, Any]] = []
    for unit in units:
        obligation_id = (
            unit.source_obligation_ids[0] if unit.source_obligation_ids else ""
        )
        for claim_id in unit.claim_ids:
            claim = claim_by_id.get(claim_id)
            if claim is None:
                continue
            supported = bool(
                getattr(claim, "status", "") in {"supported", "partial"}
                and unit.supported
            )
            claims_out.append({
                "claim_id": claim_id,
                "obligation_id": obligation_id,
                "section_id": graph.section_id,
                "lane": (
                    "repository_verified"
                    if supported and getattr(claim, "status", "") == "supported"
                    else "repository_partial"
                    if getattr(claim, "status", "") == "partial"
                    else "author_intent_unverified"
                ),
                "paper_statement": str(getattr(claim, "canonical_text", "") or "").strip(),
                "code_binding_terms": extract_code_binding_terms(
                    str(getattr(claim, "canonical_text", "") or "")
                ),
                "required_qualifiers": tuple(getattr(claim, "required_qualifiers", ()) or ()),
                "may_enter_verified": bool(supported),
                "requires_caveat": not bool(unit.supported),
            })
        if not unit.claim_ids and str(getattr(unit, "design_objective", "") or "").strip():
            statement = str(unit.design_objective).strip()
            claims_out.append({
                "claim_id": "",
                "obligation_id": obligation_id,
                "section_id": graph.section_id,
                "lane": (
                    "repository_partial"
                    if any(
                        "partially_supported" in item
                        for item in (unit.unresolved_inputs or ())
                    )
                    else "author_intent_unverified"
                ),
                "paper_statement": statement,
                "code_binding_terms": extract_code_binding_terms(statement),
                "required_qualifiers": (),
                "may_enter_verified": False,
                "requires_caveat": True,
            })
    return claims_out


def _section_candidate_points(
    graph: Any,
    units: list[Any],
    *,
    fact_by_id: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Lane-aware candidate context for one section (B.4).

    Every unresolved input of the section's units becomes an explicit
    candidate point with its lane, statement, and caveat requirement so the
    Writer can mention the known parts and mark the uncertain parts, while
    verified prose stays governed by reverse validation.
    """

    points: list[dict[str, Any]] = []
    fact_by_id = fact_by_id or {}
    for unit in units:
        for unresolved in (unit.unresolved_inputs or ()):
            obligation_id, _sep, status = str(unresolved).partition(":")
            points.append({
                "obligation_id": obligation_id,
                "lane": method_lane_from_reference_status(status),
                "statement": (
                    str(getattr(unit, "design_objective", "") or "").strip()
                    or str(getattr(unit, "research_question", "") or "").strip()
                ),
                "supported_fragments": [
                    {
                        "fact_id": artifact_id,
                        "subject": str(getattr(fact_by_id[artifact_id], "subject", "")),
                        "predicate": str(getattr(fact_by_id[artifact_id], "predicate", "")),
                        "object": str(getattr(fact_by_id[artifact_id], "object", "")),
                        "conditions": list(
                            getattr(fact_by_id[artifact_id], "conditions", ()) or ()
                        ),
                    }
                    for artifact_id in (
                        str(item)
                        for item in (getattr(unit, "source_artifact_ids", ()) or ())
                    )
                    if artifact_id in fact_by_id
                ][:8],
                "missing_or_uncertain_parts": [status],
                "required_caveat": True,
                "review_question_ids": (
                    [f"review:{obligation_id}"] if obligation_id else []
                ),
            })
    return points


def _proof_candidates(
    proof: Any,
    section_frames: list[dict[str, Any]],
    equation_ids: tuple[str, ...],
    configuration_ids: tuple[str, ...],
) -> list[str]:
    """Exact search-term candidates for one move proof.

    Repository candidates are exact subjects, operands, and relation endpoints
    from the bound frames; configuration candidates are exact keys/IDs;
    formalization candidates are exact equation IDs and operands.  Claim IDs
    alone are never search terms.
    """

    candidates: list[str] = []
    lane = str(getattr(proof, "required_authority_lane", "") or "")
    for frame in section_frames:
        for slot in frame.get("slots") or ():
            candidates.append(str(slot.get("subject") or ""))
            candidates.extend(str(item) for item in (slot.get("operands") or ()))
        for edge in frame.get("edges") or ():
            candidates.append(str(edge.get("source_symbol") or ""))
            candidates.append(str(edge.get("target_symbol") or ""))
    if lane == "configuration_resolved":
        candidates.extend(str(item) for item in configuration_ids)
    if lane == "formal_derivation":
        candidates.extend(str(item) for item in equation_ids)
    return list(dict.fromkeys(item for item in candidates if str(item).strip()))


def _require_exact_or_subset(
    failures: list[str],
    label: str,
    *,
    required: set[str],
    used: set[str],
    allow_missing: bool = False,
) -> None:
    """Content-first binding gate (E3): unknown ids fail, missing ids do not.

    The Writer is never required to complete every full id/move binding in
    the prose call.  Missing bindings are a post-processing / validator
    concern (the reverse validator decides which sentences enter verified);
    the harness must never invent ids, so *unknown* ids always fail.
    """

    if used - required:
        failures.append(f"unknown_{label}:{','.join(sorted(used - required))}")


def _expository_bridge_completable(move: Any) -> bool:
    """Whether a required move may complete claim-free through the expository lane.

    An organization-only move whose authority lanes include
    ``expository_bridge`` may be written as claim-free organization,
    transition, or definition scaffolding.  The claim-free nature is enforced
    fail-closed at the final-text layer: a bridge-marked sentence carrying a
    factual payload (claim tokens, risk markers, code-fact inventory shape)
    stays factual and is reverse-validated.
    """

    return bool(
        str(getattr(move, "move", "") or "") in _ORGANIZATION_ONLY_RHETORICAL_MOVES
        and "expository_bridge" in set(getattr(move, "allowed_authority_lanes", ()) or ())
    )


def _recover_missing_writing_callbacks(
    *,
    output: PublicationMethodSectionOutputV1,
    graph: Any,
    unit_by_id: dict[str, Any],
    authority_proofs: dict[tuple[str, str], Any] | None = None,
) -> tuple[
    PublicationMethodSectionOutputV1,
    tuple[WritingResearchRequestV1, ...],
    int,
    tuple[str, ...],
]:
    """Classify Writer-emitted callbacks without creating semantic content.

    A callback's existence, missing move, exact question, lane, and scope are
    Writer-owned content.  Malformed objects are rejected and an omitted
    request remains omitted; the deterministic proof may identify which move
    is still missing, but it cannot be serialized into a replacement request.
    """

    valid_raw: list[Any] = []
    emitted: list[WritingResearchRequestV1] = []
    dropped_malformed = 0
    for raw in output.new_research_requests:
        try:
            request = WritingResearchRequestV1.model_validate(raw)
        except (TypeError, ValueError):
            dropped_malformed += 1
            continue
        valid_raw.append(raw)
        emitted.append(request)
    if dropped_malformed:
        output = output.model_copy(update={"new_research_requests": valid_raw})

    required_moves = {
        move.move: move
        for move in (graph.moves or ())
        if move.required
    }
    unanchored: set[str] = set()
    for name, move in required_moves.items():
        if authority_proofs is not None:
            proof = authority_proofs.get((graph.section_id, name))
            anchored = bool(
                proof is not None
                and proof.state in {"anchored", "fulfilled"}
            )
        else:
            unit_ids = tuple(move.argument_unit_ids or graph.argument_unit_ids or ())
            anchored = name not in _ORGANIZATION_ONLY_RHETORICAL_MOVES and any(
                bool(
                    getattr(unit_by_id.get(unit_id), "claim_ids", ())
                    or getattr(unit_by_id.get(unit_id), "equation_ids", ())
                    or getattr(unit_by_id.get(unit_id), "configuration_ids", ())
                )
                for unit_id in unit_ids
            )
        if not anchored:
            unanchored.add(name)
    # Organization moves that can complete claim-free via the expository lane
    # need no callback request and are not recovered.
    unanchored = {
        name for name in unanchored
        if not _expository_bridge_completable(required_moves[name])
    }
    if not unanchored:
        return output, tuple(emitted), dropped_malformed, ()
    completed = {
        str(item).strip()
        for item in output.completed_rhetorical_moves
        if str(item).strip()
    }
    requested = {
        str(raw.get("missing_rhetorical_move") or raw.get("move") or "").strip()
        for raw in output.new_research_requests
        if isinstance(raw, dict)
    }
    # A model claiming an unanchored move is a hard contract failure.  Missing
    # requests are likewise left missing so the normal callback contract marks
    # the section incomplete and no route/artifact/resume state can be created.
    missing = tuple(sorted(unanchored - completed - requested))
    return output, tuple(emitted), dropped_malformed, missing


def _unit_candidate_terms(unit: Any) -> tuple[str, ...]:
    """Exact semantic search terms from one unit's typed frame.

    Repository candidates are exact subjects, operands, and relation endpoints;
    claim IDs alone are never search terms.
    """

    frame = getattr(unit, "semantic_frame", None)
    if frame is None:
        return ()
    terms: list[str] = []
    for slot in frame.slots:
        terms.append(str(slot.subject))
        terms.extend(str(item) for item in slot.operands)
    for edge in frame.edges:
        terms.append(str(edge.source_symbol))
        terms.append(str(edge.target_symbol))
    return tuple(dict.fromkeys(item for item in terms if item.strip()))


def _check_writing_callback_contract(
    failures: list[str],
    *,
    output: PublicationMethodSectionOutputV1,
    graph: Any,
    unit_by_id: dict[str, Any],
    authority_proofs: dict[tuple[str, str], Any] | None = None,
    fulfilled_callback_bindings: set[tuple[str, str]] | None = None,
) -> None:
    """Enforce the callback lane for required moves without positive anchors.

    The typed ``authority_proofs`` decide which moves are anchored
    (``anchored``/``fulfilled``), which may complete claim-free (``bridge``),
    and which require an open or external-pending callback.  A model request
    is valid only when it matches one unresolved proof's section/unit/move/
    lane exactly and may only narrow the exact question or candidates;
    unknown, extra, duplicate, fulfilled-without-artifact, and all
    expository-bridge requests are rejected.
    """

    required_moves = {
        move.move: move
        for move in (graph.moves or ())
        if move.required
    }
    unanchored: set[str] = set()
    for name, move in required_moves.items():
        if authority_proofs is not None:
            proof = authority_proofs.get((graph.section_id, name))
            anchored = bool(
                proof is not None
                and proof.state in {"anchored", "fulfilled"}
            )
        else:
            unit_ids = tuple(move.argument_unit_ids or graph.argument_unit_ids or ())
            anchored = name not in _ORGANIZATION_ONLY_RHETORICAL_MOVES and any(
                bool(
                    getattr(unit_by_id.get(unit_id), "claim_ids", ())
                    or getattr(unit_by_id.get(unit_id), "equation_ids", ())
                    or getattr(unit_by_id.get(unit_id), "configuration_ids", ())
                )
                for unit_id in unit_ids
            )
        if not anchored:
            unanchored.add(name)
    # A required organization move whose lanes include ``expository_bridge``
    # may complete as claim-free organization prose without a callback.  The
    # claim-free nature is enforced fail-closed at the final-text layer.
    unanchored = {
        name for name in unanchored
        if not _expository_bridge_completable(required_moves[name])
    }

    fulfilled_callback_bindings = fulfilled_callback_bindings or set()
    callback_satisfied = {
        name
        for name in unanchored
        if any(
            (name, unit_id) in fulfilled_callback_bindings
            for unit_id in (
                required_moves[name].argument_unit_ids
                or graph.argument_unit_ids
                or ()
            )
        )
    }
    unresolved_unanchored = unanchored - callback_satisfied
    used = set(output.completed_rhetorical_moves)
    claimed_unanchored = sorted(used.intersection(unresolved_unanchored))
    if claimed_unanchored:
        failures.append(
            "unanchored_rhetorical_moves_claimed:" + ",".join(claimed_unanchored)
        )
    reopened = sorted(
        str(raw.get("missing_rhetorical_move") or raw.get("move") or "").strip()
        for raw in output.new_research_requests
        if isinstance(raw, dict)
        and str(raw.get("missing_rhetorical_move") or raw.get("move") or "").strip()
        in callback_satisfied
    )
    if reopened:
        failures.append(
            "fulfilled_writing_research_callback_reopened:"
            + ",".join(dict.fromkeys(reopened))
        )
    if not unresolved_unanchored:
        if output.new_research_requests:
            if not reopened:
                failures.append("unexpected_writing_research_callback")
        return

    valid_requests: set[str] = set()
    invalid_requests: list[str] = []
    for raw in output.new_research_requests:
        if not isinstance(raw, dict):
            continue
        move = str(
            raw.get("missing_rhetorical_move")
            or raw.get("move")
            or raw.get("missing_move")
            or ""
        ).strip()
        request_section = str(raw.get("section_id") or "").strip()
        request_unit = str(raw.get("argument_unit_id") or "").strip()
        request_id = str(raw.get("request_id") or "").strip()
        exact_question = str(raw.get("exact_question") or raw.get("reason") or "").strip()
        request_lane = str(raw.get("required_authority_lane") or "").strip()
        status = str(raw.get("status") or "open").strip()
        request_candidates = tuple(
            str(item) for item in (raw.get("candidate_symbols_or_terms") or ())
            if str(item).strip()
        )
        move_spec = required_moves.get(move)
        allowed_units = set(
            move_spec.argument_unit_ids or graph.argument_unit_ids or ()
        ) if move_spec is not None else set()
        proof = (
            authority_proofs.get((graph.section_id, move))
            if authority_proofs is not None
            else None
        )
        proof_lane = (
            proof.required_authority_lane
            if proof is not None
            else ""
        )
        local_lane = request_lane in {
            "executable_hard", "configuration_resolved", "formal_derivation",
        }
        candidate_binding_valid = True
        if local_lane and move_spec is not None:
            try:
                typed_request = WritingResearchRequestV1.model_validate(raw)
            except (TypeError, ValueError):
                candidate_binding_valid = False
            else:
                allowed_candidates = set(_request_candidate_terms(
                    typed_request,
                    allowed_units=tuple(allowed_units),
                    unit_by_id=unit_by_id,
                ))
                candidate_binding_valid = bool(request_candidates) and set(
                    request_candidates
                ).issubset(allowed_candidates)
        if (
            move in unanchored
            and bool(request_id)
            and request_section == graph.section_id
            and request_unit in allowed_units
            and bool(exact_question)
            and (not proof_lane or request_lane == proof_lane)
            and status == "open"
            and candidate_binding_valid
        ):
            valid_requests.add(move)
            continue
        # Any other request (unknown move, wrong section/unit/lane, a request
        # for an anchored/fulfilled/bridge move, duplicate, or non-open
        # status) is a contract failure: model requests must match one
        # unresolved proof and may only narrow its question or candidates.
        invalid_requests.append(f"{move or 'unknown'}@{request_section or '?'}/{request_unit or '?'}/{request_lane or '?'}")
    missing_callbacks = sorted(unresolved_unanchored - valid_requests)
    if missing_callbacks:
        failures.append(
            "missing_writing_research_callback:" + ",".join(missing_callbacks)
        )
    if invalid_requests:
        failures.append(
            "invalid_writing_research_callback:" + ";".join(dict.fromkeys(invalid_requests))
        )


def _pre_writer_resumed_section_ids(effective_resume_section_ids: tuple[str, ...]) -> tuple[str, ...]:
    """No Writer call happened on these fail-closed paths: zero generation.

    Truthful resume telemetry requires zero resumed sections whenever the
    Writer never regenerated anything, even when a resume was admitted.
    """

    return ()


def _actually_regenerated_section_ids(
    writer_aggregate: Any,
    effective_resume_section_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Sections actually regenerated in this run (Writer generation traces).

    Zero Writer generation traces or zero model-call delta means zero resumed
    sections, even when a resume was admitted; ``effective_resume_section_ids``
    is the admission set, never a substitute for actual regeneration.
    """

    if not effective_resume_section_ids:
        return ()
    if isinstance(writer_aggregate, dict):
        generated_sections = writer_aggregate.get("sections", [])
    else:
        generated_sections = getattr(writer_aggregate, "sections", ()) or ()
    traced_sections = tuple(sorted({
        str(
            item.get("section_id")
            if isinstance(item, dict)
            else getattr(item, "section_id", "")
        )
        for item in generated_sections
        if str(
            item.get("section_id")
            if isinstance(item, dict)
            else getattr(item, "section_id", "")
        ).strip()
    }))
    if not traced_sections:
        return ()
    return tuple(dict.fromkeys([
        section_id for section_id in effective_resume_section_ids
        if section_id in traced_sections
    ]))


def _populate_request_candidates(
    request: WritingResearchRequestV1,
    *,
    graph: Any,
    unit_by_id: dict[str, Any],
    authority_proofs: dict[tuple[str, str], Any] | None,
) -> WritingResearchRequestV1 | None:
    """Validate a model request's exact candidates without inventing them.

    A model-emitted request must match one unresolved proof's section/unit/
    move/lane and may only narrow its exact question or candidates; when it
    Locally owned requests require at least one model-emitted exact candidate.
    Missing or unauthorized candidates reject routing; the harness does not
    populate or silently filter the semantic search scope.
    """
    proof = (
        authority_proofs.get((graph.section_id, request.missing_rhetorical_move))
        if authority_proofs is not None
        else None
    )
    if proof is None:
        return None
    allowed_units = tuple(proof.argument_unit_ids or graph.argument_unit_ids or ())
    authorized_terms = set(_request_candidate_terms(
        request,
        allowed_units=allowed_units,
        unit_by_id=unit_by_id,
    ))
    requested = tuple(dict.fromkeys(
        str(item) for item in request.candidate_symbols_or_terms
        if str(item).strip()
    ))
    if request.required_authority_lane in {
        "executable_hard", "configuration_resolved", "formal_derivation",
    } and (not requested or not set(requested).issubset(authorized_terms)):
        return None
    if requested and not set(requested).issubset(authorized_terms):
        return None
    if not requested:
        return request
    return request.model_copy(update={"candidate_symbols_or_terms": requested})


def _request_candidate_terms(
    request: WritingResearchRequestV1,
    *,
    allowed_units: tuple[str, ...],
    unit_by_id: dict[str, Any],
) -> tuple[str, ...]:
    """Lane-specific exact candidate terms for one request.

    Repository candidates are exact subjects, operands, and relation endpoints
    from the bound frames; configuration candidates add exact keys/IDs;
    formalization candidates add exact equation IDs and operands.
    """

    candidates = list(dict.fromkeys(
        str(item)
        for unit_id in allowed_units
        if unit_id in unit_by_id
        for item in _unit_candidate_terms(unit_by_id[unit_id])
    ))
    if request.required_authority_lane == "configuration_resolved":
        for unit_id in allowed_units:
            unit = unit_by_id.get(unit_id)
            if unit is None:
                continue
            candidates.extend(
                str(item) for item in getattr(unit, "configuration_ids", ()) or ()
            )
    if request.required_authority_lane == "formal_derivation":
        for unit_id in allowed_units:
            unit = unit_by_id.get(unit_id)
            if unit is None:
                continue
            candidates.extend(
                str(item) for item in getattr(unit, "equation_ids", ()) or ()
            )
    return tuple(dict.fromkeys(item for item in candidates if str(item).strip()))


def _load_product_validation_artifacts(
    validation_paths: dict[str, str],
) -> tuple[Any | None, Any | None, Any | None]:
    """Load the reverse-validation artifacts for the candidate/verified split.

    All three artifacts are optional: when the frozen V3 inputs were not
    supplied the writer runs with a ``pending`` validation state and the
    split falls back to unit-granular plan readiness.  A malformed artifact
    is treated as unavailable (the unit-granular fallback is fail-closed).
    """

    final_claims: Any = None
    report: Any = None
    projection: Any = None
    try:
        claims_path = validation_paths.get("final_text_claims", "")
        if claims_path and Path(claims_path).is_file():
            final_claims = load_final_text_claims(claims_path)
        report_path = validation_paths.get("text_evidence_validation", "")
        if report_path and Path(report_path).is_file():
            report = load_text_evidence_validation(report_path)
        projection_path = validation_paths.get("authoring_projection_v1", "")
        if projection_path and Path(projection_path).is_file():
            projection = AuthoringInputProjection.model_validate_json(
                Path(projection_path).read_text(encoding="utf-8")
            )
    except (OSError, TypeError, ValueError):
        return None, None, None
    if final_claims is None or report is None or projection is None:
        return None, None, None
    return final_claims, report, projection


#: Map the G1 final-text lane vocabulary onto the shared product lanes.
_LANE_FINAL_TO_EVIDENCE: dict[str, str] = {
    "repository_positive": "repository_verified",
    "repository_partial": "repository_partial",
    "author_intent_caveated": "author_intent_unverified",
    "review_question": "author_intent_unverified",
    "mismatch_warning": "repository_mismatch",
    "literature_pending": "literature_pending",
    "formalization_pending": "formalization_pending",
    "expository_bridge": "out_of_scope",
    "unsafe_unsupported_positive": "author_intent_unverified",
}


def _section_for_span(
    accepted: list[tuple[str, str, str]],
    char_start: int,
) -> str:
    """Map an absolute final-text offset back to its authored section id."""

    cursor = 0
    for section_id, text, _ref in accepted:
        if char_start < cursor + len(text):
            return section_id
        cursor += len(text) + 2
    return ""


def _build_product_bundle(
    *,
    final_text: str,
    accepted: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    completeness: MethodCompletenessMatrixV1,
    readiness: MethodPlanProductReadinessV1,
    research_requests: list[WritingResearchRequestV1],
    unresolved_points: list[tuple[str, str]] | None = None,
    validation_paths: dict[str, str],
) -> tuple[
    str,
    str,
    tuple[MethodReviewCandidateV1, ...],
    tuple[ExternalResearchQueueItemV1, ...],
    dict[str, Any],
]:
    """Split candidate/verified output and build the review surface (A/G/F).

    - ``candidate`` keeps the full authored text, including caveated
      author-intent, mismatch, and external-pending material;
    - ``verified`` keeps only repository-supported positive implementation
      facts plus structural scaffolding.  When the reverse validator ran,
      filtering is sentence-level; otherwise it falls back to unit-granular
      plan readiness (fail-closed: sections with any review-required unit
      are excluded);
    - every review item carries a non-empty ``proposed_body`` and an exact
      confirmation question.  Missing evidence never blanks the candidate;
      it becomes a review/callback item that blocks verified inclusion only.
    """

    policy = build_default_method_output_policy()
    candidate_markdown = final_text
    split_report: dict[str, Any] = {}
    verified_markdown = ""
    final_claims, validation_report, projection = _load_product_validation_artifacts(
        validation_paths
    )
    if validation_report is not None:
        verified_markdown, split_report = build_repository_verified_text(
            final_text=final_text,
            final_claims=final_claims,
            validation_report=validation_report,
            projection=projection,
            include_partial="repository_partial" in policy.verified_positive_lanes,
        )
    else:
        # Unit-granular fallback: keep only sections whose units are all
        # verified-capable and carry no review-required obligation.
        verified_ready_sections = {
            section.section_id
            for section in readiness.section_readiness
            if section.verified_ready and not section.review_required_ids
        }
        verified_markdown = "\n\n".join(
            text
            for section_id, text, _ref in accepted
            if section_id in verified_ready_sections
        )
        split_report = {
            "verified_ready_sections": sorted(verified_ready_sections),
            "split_mode": "unit_granular_readiness",
        }

    review_items: list[MethodReviewCandidateV1] = []
    seen_ids: set[str] = set()
    for item in readiness.review_candidates:
        seen_ids.add(item.candidate_id)
        review_items.append(item)
    for item in build_review_candidates_from_requests(research_requests):
        if item.candidate_id not in seen_ids:
            seen_ids.add(item.candidate_id)
            review_items.append(item)

    # Writer-declared unresolved points (E1): prose points the Writer could
    # not write safely become review items with the Writer's own wording as
    # the proposed body.
    for index, (section_id, point) in enumerate(unresolved_points or ()):
        candidate_id = f"review-unresolved:{section_id}:{index}"
        if candidate_id in seen_ids:
            continue
        review_items.append(MethodReviewCandidateV1(
            candidate_id=candidate_id,
            source_obligation_id="",
            section_id=section_id,
            lane="author_intent_unverified",
            status="unresolved_writer_point",
            proposed_body=point,
            confirmation_question=(
                f"Should the Method resolve this unresolved point in section "
                f"{section_id}?"
            ),
            needed_evidence=(),
            suggested_action="resolve_writer_unresolved_point",
            blocks_verified=True,
            blocks_candidate=False,
            trace_refs=(candidate_id,),
        ))
        seen_ids.add(candidate_id)

    # Sentence-derived review items: every factual unit the reverse validator
    # excluded from verified becomes an editable review item (A3 priority 1:
    # the Writer's own span is the proposed body).
    if final_claims is not None and validation_report is not None and projection is not None:
        verdicts_by_unit: dict[str, list[Any]] = {}
        for verdict in validation_report.verdicts:
            unit_id = _unit_id_for_verdict(verdict, final_claims)
            verdicts_by_unit.setdefault(unit_id, []).append(verdict)
        lanes_by_unit = classify_final_text_unit_lanes(final_claims, projection)
        for excluded in split_report.get("excluded_units", []):
            unit_id = str(excluded.get("unit_id") or "")
            if not unit_id:
                continue
            candidate_id = f"review-sentence:{unit_id}"
            if candidate_id in seen_ids:
                continue
            verdicts = verdicts_by_unit.get(unit_id, [])
            failures = [
                str(item)
                for verdict in verdicts
                for item in verdict.deterministic_failures
            ]
            final_lane = lanes_by_unit.get(unit_id, "unsafe_unsupported_positive")
            review_items.append(MethodReviewCandidateV1(
                candidate_id=candidate_id,
                source_claim_id="",
                section_id=_section_for_span(accepted, int(excluded.get("char_start", 0) or 0)),
                lane=str(_LANE_FINAL_TO_EVIDENCE.get(final_lane, "author_intent_unverified")),
                status="unverified",
                proposed_body=str(excluded.get("text") or "") or (
                    "A Method point in this section awaits evidence or author "
                    "confirmation and is not asserted as a repository-verified fact."
                ),
                confirmation_question=(
                    "Should the Method keep this sentence as a repository-verified "
                    f"implementation fact? ({candidate_id})"
                ),
                needed_evidence=tuple(dict.fromkeys(failures)),
                suggested_action=_suggested_action_from_failures(failures),
                blocks_verified=True,
                blocks_candidate=False,
                trace_refs=(candidate_id,),
            ))
            seen_ids.add(candidate_id)

    # Unplaced critical/high obligations: repository evidence exists but the
    # plan never bound it to a section.  Candidate is not blocked; the
    # obligation becomes an explicit coverage review item.
    matrix_by_id = completeness.by_id()
    bound_claim_ids = {
        claim_id
        for unit in plan.argument_units
        for claim_id in unit.claim_ids
    }
    bound_obligations = {
        assignment.obligation_id
        for unit in plan.argument_units
        for assignment in unit.obligation_assignments
        if assignment.argument_unit_id == unit.argument_unit_id
    }
    bound_obligations.update({
        obligation_id
        for unit in plan.argument_units
        for obligation_id in unit.source_obligation_ids
    })
    for row in completeness.items:
        if row.obligation_id in bound_obligations or set(row.claim_ids) & bound_claim_ids:
            continue
        if row.importance not in {"critical", "high"}:
            continue
        lane = method_lane_from_reference_status(str(row.status))
        if lane not in {"repository_verified", "repository_partial"}:
            continue
        candidate_id = f"review-unplaced:{row.obligation_id}"
        if candidate_id in seen_ids:
            continue
        statement = str(row.statement or "").strip()
        proposed_body = (
            "The repository supports this method point, but the Method plan does "
            "not place it into any section yet; confirm whether the Method "
            "should cover it."
            + (f" Point: {statement}" if statement else "")
        )
        review_items.append(MethodReviewCandidateV1(
            candidate_id=candidate_id,
            source_obligation_id=row.obligation_id,
            lane=lane,
            status="unplaced",
            proposed_body=proposed_body,
            confirmation_question=(
                f"Should the Method cover obligation {row.obligation_id}?"
            ),
            needed_evidence=tuple(dict.fromkeys(
                value for value in (str(row.reason or ""), str(row.next_action or ""))
                if str(value).strip()
            )),
            suggested_action="confirm_obligation_coverage_or_place_in_plan",
            blocks_verified=False,
            blocks_candidate=False,
            trace_refs=(row.obligation_id,),
        ))
        seen_ids.add(candidate_id)

    external_queue_items = build_external_research_queue_items(research_requests)
    return (
        candidate_markdown,
        verified_markdown,
        tuple(review_items),
        external_queue_items,
        split_report,
    )


def _unit_id_for_verdict(verdict: Any, final_claims: Any) -> str:
    """Resolve the unit id of one verdict through its atomic claim."""

    for claim in final_claims.atomic_claims:
        if claim.atomic_claim_id == verdict.atomic_claim_id:
            return str(claim.unit_id or "")
    return ""


def _suggested_action_from_failures(failures: list[str]) -> str:
    if any("semantic_verifier" in item for item in failures):
        return "block_for_semantic_verifier_review"
    if "no_semantically_matching_projected_claim" in failures:
        return "revise_authoring_wording"
    if "direct_evidence_missing" in failures:
        return "return_to_analysis_for_direct_evidence"
    if "required_qualifier_missing" in failures:
        return "preserve_required_qualifiers"
    if failures:
        return "revise_authoring_wording"
    return "confirm_author_intent_or_provide_evidence"


def _write_publication_outputs(
    *,
    out_root: str | Path,
    candidate_markdown: str,
    verified_markdown: str,
    review_items: tuple[MethodReviewCandidateV1, ...],
    external_queue_items: tuple[ExternalResearchQueueItemV1, ...],
    split_report: dict[str, Any],
    readiness: MethodPlanProductReadinessV1,
    effective_readiness: str,
    research_requests: list[WritingResearchRequestV1],
    writer,
    ledger,
    quality,
    section_outputs: dict[str, PublicationMethodSectionOutputV1],
    section_response_refs: dict[str, str],
    editor_result,
    formalization_path: Path,
    status: str,
    incomplete_section_ids: tuple[str, ...] = (),
    callback_bundle: WritingResearchCallbackBundleV1 | None = None,
    callback_artifacts: dict[str, tuple[WritingResearchCallbackArtifactV1, ...]] | None = None,
    resumed_section_ids: tuple[str, ...] = (),
) -> dict[str, str]:
    root = Path(out_root)
    repository_path = method_output(root, "repository_verified_method")
    candidate_path = method_output(root, "publication_candidate_method")
    review_path = method_output(root, "author_review_candidates")
    ledger_path = method_output(root, "final_text_authorship_ledger_v1")
    quality_path = method_output(root, "publication_quality_report_v1")
    checkpoint_path = method_output(root, "publication_section_checkpoint_v1")
    routes_path = method_output(root, "writing_research_routes_v1")
    callback_bundle_path = method_output(root, "writing_research_callback_artifacts_v1")
    editor_path = method_output(root, "publication_editor_result_v1")
    external_queue_path = method_output(root, "external_research_queue_v1")
    bundle_path = method_output(root, "method_draft_bundle_v1")
    published_paths: dict[str, str] = {}
    if status != "blocked":
        # A-run product semantics: the candidate is the full authored draft
        # (it may carry clearly marked author-intent / external-pending
        # material); the verified document contains only repository-supported
        # positive implementation facts plus structural scaffolding.
        _atomic_write_text(repository_path, verified_markdown)
        _atomic_write_text(candidate_path, candidate_markdown)
        published_paths = {
            "repository_verified_method": str(repository_path),
            "publication_candidate_method": str(candidate_path),
            "text_md": str(candidate_path),
            "text_clean_md": str(candidate_path),
        }
    review_payload = {
        "schema_version": "1.1",
        "publication_status": status,
        "items": [item.model_dump(mode="json") for item in review_items],
        "writer_research_requests": [item.model_dump(mode="json") for item in research_requests],
        "external_research_queue": [
            item.model_dump(mode="json") for item in external_queue_items
        ],
        "incomplete_sections": list(dict.fromkeys([
            *writer.incomplete_sections,
            *incomplete_section_ids,
            *[item.section_id for item in research_requests if item.status == "open"],
        ])),
    }
    _atomic_write_text(review_path, json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(external_queue_path, json.dumps({
        "schema_version": "1.0",
        "items": [item.model_dump(mode="json") for item in external_queue_items],
    }, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(ledger_path, ledger.model_dump_json(indent=2) + "\n")
    _atomic_write_text(quality_path, quality.model_dump_json(indent=2) + "\n")
    _write_section_checkpoint(
        checkpoint_path,
        section_outputs=section_outputs,
        section_response_refs=section_response_refs,
    )
    routes = route_writing_research_requests(research_requests)
    _atomic_write_text(routes_path, json.dumps({
        "schema_version": "1.0",
        "routes": [item.model_dump(mode="json") for item in routes],
    }, ensure_ascii=False, indent=2) + "\n")
    callback_requests = {
        item.request_id: item
        for item in (callback_bundle.requests if callback_bundle is not None else ())
    }
    callback_requests.update({item.request_id: item for item in research_requests})
    for request_id, artifacts in (callback_artifacts or {}).items():
        request = callback_requests.get(request_id)
        if request is not None and artifacts:
            callback_requests[request_id] = request.model_copy(update={
                "status": "fulfilled",
                "fulfilled_artifact_ids": tuple(item.artifact_id for item in artifacts),
            })
    try:
        # The persisted admitted set keeps only sections that were admitted
        # but NOT actually regenerated in this run: a successfully
        # regenerated section consumed its fulfilled artifacts and clears its
        # replay marker instead of being resubmitted forever.  Zero Writer
        # calls therefore leave the marker intact (fail-closed admission).
        admitted_but_not_regenerated = tuple(sorted(
            section_id for section_id in (
                callback_bundle.resume_section_ids
                if callback_bundle is not None else ()
            )
            if section_id not in set(resumed_section_ids)
        ))
        callback_payload = WritingResearchCallbackBundleV1(
            requests=tuple(callback_requests.values()),
            artifacts=callback_artifacts or {},
            resume_section_ids=admitted_but_not_regenerated,
        )
    except ValueError:
        # Never let an optional hand-off sidecar change the publication text
        # result.  Persist a typed empty bundle; the next resume will fail
        # closed rather than accepting an unbound artifact.
        callback_payload = WritingResearchCallbackBundleV1(
            requests=tuple(research_requests),
            artifacts={},
            resume_section_ids=(),
        )
    _atomic_write_text(
        callback_bundle_path,
        callback_payload.model_dump_json(indent=2) + "\n",
    )
    try:
        bundle = MethodDraftBundleV1(
            candidate_markdown=candidate_markdown,
            verified_markdown=verified_markdown,
            review_items=review_items,
            plan_readiness=effective_readiness,
            blocked_reasons=readiness.blocked_for_safety_reasons,
            validation_split_report=split_report,
        )
        _atomic_write_text(bundle_path, bundle.model_dump_json(indent=2) + "\n")
    except ValueError:
        # The bundle validator is fail-closed about readiness consistency; a
        # ``verified_ready`` label must never be paired with an empty verified
        # document.  Write the split report instead and keep the text outputs.
        _atomic_write_text(bundle_path, json.dumps({
            "schema_version": "1.0",
            "plan_readiness": effective_readiness,
            "split_report": split_report,
            "bundle_validation_failed": True,
        }, ensure_ascii=False, indent=2) + "\n")
    if editor_result is not None:
        _atomic_write_text(editor_path, editor_result.model_dump_json(indent=2) + "\n")
    return {
        **published_paths,
        "author_review_candidates": str(review_path),
        "external_research_queue_v1": str(external_queue_path),
        "method_draft_bundle_v1": str(bundle_path),
        "final_text_authorship_ledger_v1": str(ledger_path),
        "publication_quality_report_v1": str(quality_path),
        "publication_section_checkpoint_v1": str(checkpoint_path),
        "writing_research_routes_v1": str(routes_path),
        "writing_research_callback_artifacts_v1": str(callback_bundle_path),
        "formalization_result_v1": str(formalization_path),
        **({"publication_editor_result_v1": str(editor_path)} if editor_result is not None else {}),
    }


def _write_result_only(
    out_root: str | Path,
    result: PublicationWriterRunResultV1,
) -> dict[str, str]:
    path = method_output(Path(out_root), "publication_writer_result_v1")
    _atomic_write_text(path, result.model_dump_json(indent=2) + "\n")
    return {"publication_writer_result_v1": str(path)}


def _atomic_write_text(path: Path, content: str) -> None:
    """Persist a hand-off artifact with an fsync + atomic replace boundary."""

    atomic_write_bytes(path, content.encode("utf-8"))


def _write_section_checkpoint(
    checkpoint_path: Path,
    *,
    section_outputs: Mapping[str, PublicationMethodSectionOutputV1],
    section_response_refs: Mapping[str, str],
) -> None:
    """Persist compact section refs while keeping output payloads immutable.

    A resume checkpoint is a routing record, not a second mutable copy of the
    Writer output.  Each section payload is content-addressed under the
    checkpoint directory; the compact manifest records only its reference,
    digest, and Writer response reference.  Existing inline checkpoints remain
    readable through ``_load_section_checkpoint`` for backwards compatibility.
    """

    store_root = checkpoint_path.parent / "immutable_section_checkpoints"
    sections: dict[str, dict[str, str]] = {}
    for section_id, output in section_outputs.items():
        response_ref = str(section_response_refs.get(section_id, ""))
        if not response_ref:
            continue
        output_payload = output.model_dump(mode="json")
        output_digest = _digest_json(output_payload)
        store_payload: dict[str, Any] = {
            "schema_version": "1.0",
            "section_id": str(section_id),
            "response_ref": response_ref,
            "output": output_payload,
            "output_digest": output_digest,
        }
        store_payload["content_digest"] = _digest_json(store_payload)
        # The output digest authenticates the Writer payload, while the store
        # digest also binds its response reference.  Keeping those identities
        # separate avoids a valid same-text/different-response resume from
        # colliding on one immutable file.
        store_digest = str(store_payload["content_digest"])
        store_path = store_root / f"{store_digest.removeprefix('sha256:')}.json"
        if not store_path.is_file():
            _atomic_write_text(
                store_path,
                json.dumps(store_payload, ensure_ascii=False, indent=2) + "\n",
            )
        sections[str(section_id)] = {
            # Relative refs survive copying a frozen run to another output
            # root.  The loader still accepts historical absolute refs.
            "output_ref": str(store_path.relative_to(checkpoint_path.parent)),
            "output_digest": output_digest,
            "response_ref": response_ref,
        }
    checkpoint_payload: dict[str, Any] = {
        "schema_version": "1.0",
        "checkpoint_format": "immutable_section_refs_v1",
        "sections": sections,
    }
    checkpoint_payload["content_digest"] = _digest_json(checkpoint_payload)
    _atomic_write_text(
        checkpoint_path,
        json.dumps(checkpoint_payload, ensure_ascii=False, indent=2) + "\n",
    )


def _load_callback_bundle(
    artifact_paths: dict[str, str],
) -> WritingResearchCallbackBundleV1 | None:
    """Load the persisted Writer→research hand-off, if one is supplied."""

    value = artifact_paths.get("writing_research_callback_artifacts_v1", "")
    if not value:
        return None
    path = Path(value)
    if not path.is_file():
        return None
    try:
        return _read_verified_callback_bundle(path)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        # A malformed callback bundle is not a reason to run all sections
        # again with unknown authority; resume will be disabled and the
        # caller can inspect the existing sidecar for repair.
        return None


def fulfill_writing_research_callbacks(
    bundle_path: str | Path,
    artifacts: Mapping[str, Iterable[WritingResearchCallbackArtifactV1 | Mapping[str, Any]]],
) -> WritingResearchCallbackBundleV1:
    """Atomically persist owner-validated callback artifacts.

    This is the only mutation helper for the Writer callback sidecar.  It does
    not search the repository or upgrade authority itself; the caller must
    provide typed artifacts that already passed the owning lane's validator.
    """

    path = Path(bundle_path)
    bundle = _read_verified_callback_bundle(path)
    merged = {
        request_id: tuple(items)
        for request_id, items in bundle.artifacts.items()
    }
    requests_by_id = {item.request_id: item for item in bundle.requests}
    for request_id, raw_items in artifacts.items():
        request = requests_by_id.get(str(request_id))
        if request is None:
            raise ValueError(f"callback artifact request is not pending: {request_id}")
        normalized = tuple(
            item if isinstance(item, WritingResearchCallbackArtifactV1)
            else WritingResearchCallbackArtifactV1.model_validate(item)
            for item in raw_items
        )
        if request.status == "fulfilled":
            # Idempotent re-fulfillment: an already fulfilled request whose
            # artifacts match is left intact (a repeated runner resume must
            # not corrupt the persisted proof).
            existing_ids = set(request.fulfilled_artifact_ids)
            provided_ids = {item.artifact_id for item in normalized}
            if provided_ids != existing_ids:
                raise ValueError(
                    f"callback artifact request is already fulfilled with different artifacts: {request_id}"
                )
            continue
        if request.status != "open":
            raise ValueError(f"callback artifact request is not open: {request_id}")
        if not normalized:
            raise ValueError(f"callback artifact list is empty: {request_id}")
        merged[str(request_id)] = normalized
        requests_by_id[str(request_id)] = request.model_copy(update={
            "status": "fulfilled",
            "fulfilled_artifact_ids": tuple(item.artifact_id for item in normalized),
        })
    updated = WritingResearchCallbackBundleV1(
        requests=tuple(requests_by_id.values()),
        artifacts=merged,
        resume_section_ids=tuple(dict.fromkeys([
            *bundle.resume_section_ids,
            *[
                request.section_id for request in requests_by_id.values()
                if request.status == "fulfilled"
                and request.required_authority_lane in _LOCALLY_OWNED_LANES
            ],
        ])),
    )
    _atomic_write_text(path, updated.model_dump_json(indent=2) + "\n")
    return updated


def _read_verified_callback_bundle(
    path: Path,
) -> WritingResearchCallbackBundleV1:
    """Read a callback sidecar only when its persisted digest is intact."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("writing callback bundle must be a JSON object")
    declared_digest = str(raw.get("content_digest") or "")
    if not declared_digest or declared_digest != _digest_json({
        key: value for key, value in raw.items() if key != "content_digest"
    }):
        raise ValueError("writing callback bundle content digest mismatch")
    bundle = WritingResearchCallbackBundleV1.model_validate(raw)
    if bundle.content_digest != declared_digest:
        raise ValueError("writing callback bundle normalized digest mismatch")
    return bundle


def _load_section_checkpoint(
    *,
    out_root: str | Path,
    artifact_paths: dict[str, str],
    resume_section_ids: tuple[str, ...],
) -> tuple[dict[str, PublicationMethodSectionOutputV1] | None, dict[str, str]]:
    if not resume_section_ids:
        return {}, {}
    value = artifact_paths.get("publication_section_checkpoint_v1", "")
    path = Path(value) if value else method_output(Path(out_root), "publication_section_checkpoint_v1")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        checkpoint_digest = payload.get("content_digest")
        if checkpoint_digest:
            digest_payload = {
                key: item for key, item in payload.items() if key != "content_digest"
            }
            if checkpoint_digest != _digest_json(digest_payload):
                return None, {}
        rows = payload["sections"]
        outputs: dict[str, PublicationMethodSectionOutputV1] = {}
        refs: dict[str, str] = {}
        for section_id, row in rows.items():
            section_key = str(section_id)
            if not isinstance(row, dict):
                return None, {}
            output_payload = row.get("output")
            output_ref = str(row.get("output_ref") or "")
            if output_ref:
                store_path = Path(output_ref)
                if not store_path.is_absolute():
                    store_path = path.parent / store_path
                store_root = (path.parent / "immutable_section_checkpoints").resolve()
                try:
                    if store_path.is_symlink() or store_path.resolve().parent != store_root:
                        return None, {}
                except OSError:
                    return None, {}
                store = json.loads(store_path.read_text(encoding="utf-8"))
                store_digest = store.get("content_digest")
                store_without_digest = {
                    key: item for key, item in store.items() if key != "content_digest"
                }
                if not store_digest or store_digest != _digest_json(store_without_digest):
                    return None, {}
                if str(store.get("section_id") or "") != section_key:
                    return None, {}
                output_payload = store.get("output")
                if row.get("output_digest") != _digest_json(output_payload):
                    return None, {}
                if str(store.get("response_ref") or "") != str(row.get("response_ref") or ""):
                    return None, {}
            if not isinstance(output_payload, dict):
                return None, {}
            output = PublicationMethodSectionOutputV1.model_validate(output_payload)
            if output.section_id and output.section_id != section_key:
                return None, {}
            outputs[section_key] = output
            refs[section_key] = str(row.get("response_ref") or "")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, {}
    return outputs, refs


def _callback_artifact_prompt_payload(
    artifact: WritingResearchCallbackArtifactV1,
    *,
    base_dir: Path,
    max_preview_chars: int = 8000,
) -> tuple[dict[str, Any], str]:
    """Bind a file-backed callback artifact before exposing it to Writer.

    Callback artifacts are normally opaque evidence references (for example a
    ``span:...`` identifier), so those references remain unchanged.  When the
    owner points at a real file, however, the Writer needs a bounded view of
    the validated result rather than a filename it cannot inspect.  Verify the
    declared digest before adding that preview; a stale or tampered file must
    stop the resume before another model call.
    """

    payload = artifact.model_dump(mode="json")
    reference = str(artifact.artifact_ref or "").strip()
    if not reference:
        return payload, "artifact_ref_empty"
    candidate = Path(reference).expanduser()
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    try:
        if not candidate.exists():
            # Non-file references (span IDs, relation IDs, and similar typed
            # handles) are resolved by the owning tool and remain opaque to
            # the Writer.  Do not reinterpret them as local paths.  A
            # path-shaped reference, however, is an integrity failure when
            # its file has disappeared: treating a missing absolute path as
            # an opaque handle would let a stale callback resume without the
            # digest-pinned artifact the owner validated.
            if _looks_like_callback_file_reference(reference):
                return payload, "artifact_ref_missing"
            return payload, ""
        if candidate.is_symlink() or not candidate.is_file():
            return payload, "artifact_ref_not_regular_file"
        actual_digest = "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual_digest != artifact.artifact_digest:
            return payload, "artifact_digest_mismatch"
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Binary evidence can still be consumed by its owning lane through
            # the digest-pinned ref; it is not safe to coerce it into prose.
            return payload, ""
        payload["artifact_preview"] = text[:max_preview_chars]
        payload["artifact_preview_truncated"] = len(text) > max_preview_chars
        return payload, ""
    except OSError:
        return payload, "artifact_ref_unreadable"


_OPAQUE_CALLBACK_REF_PREFIXES = (
    "span:",
    "fact:",
    "claim:",
    "equation:",
    "config:",
    "relation:",
    "artifact:",
)


def _looks_like_callback_file_reference(reference: str) -> bool:
    """Distinguish missing file refs from typed opaque evidence handles.

    Callback artifacts deliberately support both filesystem refs and compact
    evidence IDs.  Evidence IDs may themselves contain source-path slashes,
    so a slash alone is not sufficient to classify a ref as a file.  Absolute
    paths, common relative-path forms, and filename extensions are
    unambiguously file-shaped; known typed prefixes remain opaque.
    """

    value = str(reference or "").strip()
    if not value or value.startswith(_OPAQUE_CALLBACK_REF_PREFIXES):
        return False
    path = Path(value)
    if path.is_absolute() or value.startswith(("./", "../")):
        return True
    if "/" in value or "\\" in value:
        return True
    return bool(path.suffix and path.suffix.lower() in {
        ".json", ".jsonl", ".txt", ".md", ".yaml", ".yml", ".csv",
        ".py", ".js", ".jsx", ".ts", ".tsx", ".toml", ".ini", ".xml",
        ".html", ".parquet", ".bin", ".pdf", ".png", ".jpg", ".jpeg",
    })


def _build_editor_local_ledgers(
    *,
    incumbent_sections: Mapping[str, tuple[str, str]],
    edited_sections: Mapping[str, str],
    patches: Iterable[Any],
    response_ref: str,
) -> dict[str, Any]:
    """Authenticate Editor bytes while retaining unaffected Writer spans."""

    patches_by_section: dict[str, list[Any]] = {}
    for patch in patches:
        patches_by_section.setdefault(str(patch.section_id), []).append(patch)
    ledgers: dict[str, Any] = {}
    for section_id, section_patches in patches_by_section.items():
        incumbent = incumbent_sections.get(section_id)
        if incumbent is None:
            raise ValueError(f"editor_unknown_section:{section_id}")
        working_text, writer_ref = incumbent
        local_ledger = build_final_text_authorship_ledger(
            working_text,
            (GeneratedTextSpanV1(
                span_id=f"writer:{section_id}",
                text=working_text,
                owner="writer",
                response_ref=writer_ref,
                section_id=section_id,
                generation_trace_id=writer_ref,
            ),),
        )
        if not local_ledger.hard_gate_passed:
            raise ValueError("editor_incumbent_authorship_gate_failed")
        for patch in section_patches:
            if _digest_text(working_text) != patch.before_digest:
                raise ValueError(f"editor_stale_section:{section_id}")
            before_text = patch.before_text or working_text
            if working_text.count(before_text) != 1:
                raise ValueError(f"editor_span_not_unique:{section_id}")
            start = working_text.find(before_text)
            if start < 0:
                raise ValueError(f"editor_span_missing:{section_id}")
            end = start + len(before_text)
            candidate_text = working_text[:start] + patch.replacement_text + working_text[end:]
            local_patch = SimpleNamespace(
                start=start,
                end=end,
                replacement_text=patch.replacement_text,
                patch_id=patch.patch_id,
                section_id=section_id,
            )
            local_ledger = rewrite_final_text_authorship_ledger(
                incumbent_text=working_text,
                candidate_text=candidate_text,
                incumbent_ledger=local_ledger,
                patches=(local_patch,),
                response_ref=(
                    patch.generation_trace_ids[-1]
                    if patch.generation_trace_ids
                    else response_ref
                ),
                generation_trace_id=(
                    patch.generation_trace_ids[-1]
                    if patch.generation_trace_ids
                    else response_ref
                ),
                owner="editor",
            )
            working_text = candidate_text
        if working_text != str(edited_sections.get(section_id) or ""):
            raise ValueError(f"editor_candidate_bytes_mismatch:{section_id}")
        ledgers[section_id] = local_ledger
    return ledgers


def _editor_claim_regressions(
    *,
    patches,
    original_sections: dict[str, str],
    edited_sections: dict[str, str],
    outputs: dict[str, PublicationMethodSectionOutputV1],
    claims_by_id: dict[str, Any],
) -> list[str]:
    """Reject an Editor patch that loses an incumbent claim/qualifier anchor."""

    failures: list[str] = []
    for patch in patches:
        original = original_sections.get(patch.section_id, "")
        candidate = edited_sections.get(patch.section_id, "")
        output = outputs.get(patch.section_id)
        if output is None:
            failures.append(f"{patch.section_id}:binding_missing")
            continue
        for claim_id in output.used_claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is None:
                failures.append(f"{patch.section_id}:unknown_claim:{claim_id}")
                continue
            before = _claim_anchor_score(original, claim.canonical_text)
            after = _claim_anchor_score(candidate, claim.canonical_text)
            if before >= 0.35 and after < 0.35:
                failures.append(f"{patch.section_id}:supported_claim_lost:{claim_id}")
            for qualifier in claim.required_qualifiers:
                if _claim_anchor_score(original, qualifier) >= 0.5 and _claim_anchor_score(candidate, qualifier) < 0.5:
                    failures.append(f"{patch.section_id}:required_qualifier_lost:{claim_id}")
    return list(dict.fromkeys(failures))


def _claim_anchor_score(text: str, anchor: str) -> float:
    stop = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "is", "are", "its"}
    anchor_tokens = set(re.findall(r"[a-z0-9_]+", anchor.lower())) - stop
    if not anchor_tokens:
        return 1.0
    text_tokens = set(re.findall(r"[a-z0-9_]+", text.lower())) - stop
    return len(anchor_tokens & text_tokens) / len(anchor_tokens)


def _digest_json(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "PublicationWriterRunResultV1",
    "fulfill_writing_research_callbacks",
    "run_publication_method_writer",
]
