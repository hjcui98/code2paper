"""Production orchestration for the publication-ready Method Writer."""

from __future__ import annotations

import hashlib
import json
import shutil
import os
import re
import tempfile
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
from code2paper.agentic.trust_contracts import (
    AuthorAttestedFragment,
    AuthoringInputProjection,
    FinalTextClaims,
)
from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.equation_claims import (
    EquationClaimSetV1,
    is_bare_binary_expression,
    load_equation_claims,
)
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
    dangling_heading_tail,
    evaluate_publication_method_quality,
    find_code_trace_prose_sections,
    heading_is_truncated,
    heading_replacement_is_coherent,
    heading_tail_leaked_into_body,
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
from code2paper.agentic.text_repair_supervisor import (
    derive_repair_issues,
    failure_to_repair_scope,
)
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
    AuthorStoryNodeV1,
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
from code2paper.agentic.method_proposition_models import (
    MethodPropositionSetV1,
    PropositionBindingSidecarV1,
)
from code2paper.agentic.writer_view_projection import build_writer_view
from code2paper.agentic.method_proposition_alignment_provider import build_proposition_semantic_aligner
from code2paper.agentic.proposition_semantic_aligner import align_sentence_to_section_propositions
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
    directed_callback_question,
    directed_search_terms_from_texts,
    fill_writing_research_search_terms,
    route_writing_research_request,
)
from code2paper.agentic.product_authoring_graph import (
    ProductAuthoringIssueV1,
    persist_product_authoring_state_from_writer,
)
from code2paper.agentic.publication_transaction_contract import (
    assess_paragraph_transaction,
)
from code2paper.core.output_names import method_output
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1
from code2paper.llm.section_writer import (
    WriterSectionInput,
    write_publication_method_by_sections,
)
from code2paper.schemas import ClaimEvidenceMap, LLMConfig, LLMProvider, MethodEvidence, RawEvidencePack


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

_UNANCHORED_OWNER_CALLBACK_MOVES = frozenset({
    "equation_or_derivation",
    "algorithm_or_data_flow",
    "mechanism_overview",
})


def _default_llm_caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
    """Live LLM caller used when no caller is injected (Q2 repair).

    Mirrors the section Writer's default: the live client is the product
    runtime.  Fail-closed: without a configured provider/key the client
    returns a blocked response and the deterministic fallback keeps the
    section honest instead of fabricating formulas.
    """

    return LLMClient(config).complete(request)


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
    transaction_assessment_digest: str = ""
    rendered_text_digest: str = ""
    resumed_section_ids: tuple[str, ...] = ()
    blocked_reason: str = ""
    # Q0 candidate-first independent states (plan 19.2): generation, candidate
    # validation, verified validation, and publication readiness are separate.
    # Only candidate_generation_status == "failed" is a generation failure;
    # validation warnings/errors never erase a durable candidate.
    candidate_generation_status: Literal["not_started", "generated", "failed"] = "not_started"
    candidate_available: bool = False
    candidate_validation_status: Literal["not_run", "passed", "warnings", "error"] = "not_run"
    candidate_warnings_by_severity: dict[str, int] = Field(default_factory=dict)
    verified_validation_status: Literal["not_run", "passed", "incomplete", "error"] = "not_run"
    publication_ready: bool = False
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
    # R1 explicit author-story override: concept keys the author story names
    # as scientifically material are never filtered as audit_only.
    concept_audit_override_keys: tuple[str, ...] = (),
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
        from code2paper.agentic.scientific_claim_ir import (
            append_technical_claims,
            write_technical_claims_sidecar,
        )

        claims = append_technical_claims(claims, facts)
        try:
            write_technical_claims_sidecar(
                artifact_paths["atomic_claims_v3"], claims
            )
        except OSError:
            pass
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
        propositions = None
        proposition_bindings = None
        proposition_value = artifact_paths.get("method_propositions_v1", "")
        if proposition_value and Path(proposition_value).is_file():
            propositions = MethodPropositionSetV1.model_validate_json(
                Path(proposition_value).read_text(encoding="utf-8")
            )
            binding_value = artifact_paths.get(
                "method_proposition_bindings_v1", ""
            )
            if not binding_value or not Path(binding_value).is_file():
                raise ValueError("method proposition binding sidecar is missing")
            proposition_bindings = PropositionBindingSidecarV1.model_validate_json(
                Path(binding_value).read_text(encoding="utf-8")
            )
        concept_cards = None
        argument_briefs = None
        argument_facets = ()
        facet_alignments = ()
        facet_policies = ()
        brief_value = artifact_paths.get("method_argument_briefs_v1", "")
        if brief_value and Path(brief_value).is_file():
            from code2paper.agentic.method_argument_brief_models import (
                MethodArgumentBriefSetV1,
            )

            argument_briefs = MethodArgumentBriefSetV1.model_validate_json(
                Path(brief_value).read_text(encoding="utf-8")
            )
            if propositions is not None:
                raise ValueError(
                    "a writer run must use either propositions or argument briefs, not both"
                )
        facet_value = artifact_paths.get("method_argument_facets_v1", "")
        alignment_value = artifact_paths.get("facet_evidence_alignments_v1", "")
        policy_value = artifact_paths.get("candidate_facet_policies_v1", "")
        if facet_value and Path(facet_value).is_file():
            from code2paper.agentic.method_argument_brief_models import (
                AuthorMechanismFacetV1,
            )

            facet_payload = json.loads(
                Path(facet_value).read_text(encoding="utf-8")
            )
            argument_facets = tuple(
                AuthorMechanismFacetV1.model_validate(item)
                for item in (
                    facet_payload.get("facets", ())
                    if isinstance(facet_payload, dict)
                    else facet_payload
                )
            )
        if alignment_value and Path(alignment_value).is_file():
            from code2paper.agentic.method_argument_brief_models import (
                FacetEvidenceAlignmentV1,
            )

            alignment_payload = json.loads(
                Path(alignment_value).read_text(encoding="utf-8")
            )
            facet_alignments = tuple(
                FacetEvidenceAlignmentV1.model_validate(item)
                for item in (
                    alignment_payload.get("alignments", ())
                    if isinstance(alignment_payload, dict)
                    else alignment_payload
                )
            )
        if policy_value and Path(policy_value).is_file():
            from code2paper.agentic.method_argument_brief_models import (
                CandidateFacetPolicyV1,
            )

            policy_payload = json.loads(
                Path(policy_value).read_text(encoding="utf-8")
            )
            facet_policies = tuple(
                CandidateFacetPolicyV1.model_validate(item)
                for item in (
                    policy_payload.get("policies", ())
                    if isinstance(policy_payload, dict)
                    else policy_payload
                )
            )
        concept_value = artifact_paths.get("method_concept_cards_v1", "")
        if argument_briefs is None and concept_value and Path(concept_value).is_file():
            from code2paper.agentic.method_concept_card_models import (
                MethodConceptCardSetV1,
            )

            concept_cards = MethodConceptCardSetV1.model_validate_json(
                Path(concept_value).read_text(encoding="utf-8")
            )
            if propositions is not None:
                raise ValueError(
                    "a writer run must use either propositions or concept cards, not both"
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
    if propositions is not None:
        proposition_ids = {
            item.proposition_id for item in propositions.propositions
        }
        binding_ids = {
            item.proposition_id for item in proposition_bindings.bindings
        }
        known_claim_ids = {item.claim_id for item in claims.claims}
        known_fact_ids = {item.fact_id for item in facts.facts}
        known_span_ids = {
            span.span_id
            for packet in (evidence_packets_v3.packets if evidence_packets_v3 else ())
            for span in packet.spans
        }
        known_relation_ids = {
            relation.relation_id
            for packet in (evidence_packets_v3.packets if evidence_packets_v3 else ())
            for relation in packet.relations
        }
        known_equation_ids = {item.equation_id for item in equations.equations}
        known_configuration_ids = {
            item.configuration_id for item in configurations.claims
        }
        binding_failures = []
        if proposition_bindings.content_digest != propositions.binding_sidecar_digest:
            binding_failures.append("sidecar_digest_mismatch")
        if (
            proposition_bindings.repo_snapshot_id != propositions.repo_snapshot_id
            or proposition_bindings.project_tree_hash != propositions.project_tree_hash
        ):
            binding_failures.append("sidecar_snapshot_mismatch")
        if binding_ids != proposition_ids:
            binding_failures.append("sidecar_proposition_set_not_closed")
        for binding in proposition_bindings.bindings:
            if set(binding.claim_ids) - known_claim_ids:
                binding_failures.append(
                    f"{binding.proposition_id}:unknown_claim_ids"
                )
            if set(binding.fact_ids) - known_fact_ids:
                binding_failures.append(
                    f"{binding.proposition_id}:unknown_fact_ids"
                )
            if set(binding.span_ids) - known_span_ids:
                binding_failures.append(
                    f"{binding.proposition_id}:unknown_span_ids"
                )
            if set(binding.relation_ids) - known_relation_ids:
                binding_failures.append(
                    f"{binding.proposition_id}:unknown_relation_ids"
                )
            if set(binding.equation_ids) - known_equation_ids:
                binding_failures.append(
                    f"{binding.proposition_id}:unknown_equation_ids"
                )
            if set(binding.configuration_ids) - known_configuration_ids:
                binding_failures.append(
                    f"{binding.proposition_id}:unknown_configuration_ids"
                )
            proposition = next(
                item for item in propositions.propositions
                if item.proposition_id == binding.proposition_id
            )
            if proposition.may_enter_verified and (
                not binding.claim_ids or not binding.fact_ids or not binding.span_ids
            ):
                binding_failures.append(
                    f"{binding.proposition_id}:verified_binding_incomplete"
                )
        if binding_failures:
            result = PublicationWriterRunResultV1(
                status="blocked",
                plan_digest=plan.content_digest,
                claim_digest=claims.content_digest,
                blocked_reason=(
                    "method_proposition_binding_invalid:"
                    + ";".join(dict.fromkeys(binding_failures))
                ),
            )
            return result, _write_result_only(out_root, result)

    architect_trace_path = ""
    architect_plan_path = ""
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
            story_spine=tuple(_story_spine_models_from_artifact_paths(artifact_paths)),
            argument_briefs=argument_briefs,
            concept_cards=concept_cards,
            argument_facets=argument_facets,
            facet_alignments=facet_alignments,
            facet_policies=facet_policies,
        )
        architect_trace_path = str(method_output(Path(out_root), "method_architect_trace_v1"))
        _atomic_write_text(
            architect_trace_path,
            json.dumps(architect_trace, ensure_ascii=False, indent=2) + "\n",
        )
        # Replanning upgrades legacy plans with the freshly derived semantic
        # frames.  Persist that exact plan beside the architect trace so
        # downstream content-trace/quality readers do not reload the stale
        # pre-replan plan and erase slot, edge, and formula-consumer bindings.
        architect_plan_path = str(method_output(Path(out_root), "method_section_plan_v2"))
        _atomic_write_text(
            architect_plan_path,
            plan.model_dump_json(indent=2) + "\n",
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

    # Q2 (plan 19.6): the section-scoped Formalizer produces paper-level
    # formula packages (or typed dispositions) per section, bound to the
    # section's own core equations.  Empty proposal results are never
    # silently treated as completion.
    # R1: audit-only concept cards are excluded from the Writer sentence
    # plan, coverage, qualifier repair and Formalizer inputs; the explicit
    # author-story override re-admits material cards.
    # Review Q1: the story override is derived from the frozen story spine /
    # placement on every production path (cards whose story_node is named by
    # the spine are never filtered as audit_only), and unioned with any
    # caller-supplied explicit keys.
    from code2paper.agentic.publication_relevance import classify_concept_card_writing_role

    effective_override_keys = set(concept_audit_override_keys)
    if concept_cards is not None:
        effective_override_keys.update(_story_override_concept_keys(
            artifact_paths=artifact_paths,
            concept_cards=concept_cards,
        ))
    audit_concept_keys: frozenset[str] = frozenset()
    if concept_cards is not None:
        audit_concept_keys = frozenset(
            str(card.concept_key)
            for card in concept_cards.cards
            if classify_concept_card_writing_role(
                card,
                story_selected=str(card.concept_key) in effective_override_keys,
            )
            == "audit_only"
        )
    audit_only_claim_ids = _audit_only_claim_ids(
        propositions=propositions,
        proposition_bindings=proposition_bindings,
        concept_cards=concept_cards,
        audit_concept_keys=audit_concept_keys,
        claims=claims,
        facts=facts,
    )
    # Q2 repair (review P0): the section Formalizer must make a real
    # low-temperature model call in product and replay execution.  When no
    # caller is injected, the live client is the default (fail-closed: a
    # missing key yields a blocked response and the deterministic fallback).
    effective_formalization_caller = formalization_caller or llm_caller or _default_llm_caller
    section_formula_results, formalization_section_path = _run_section_formalizer(
        out_root=out_root,
        plan=plan,
        equations=equations,
        facts=facts,
        claims=claims,
        propositions=propositions,
        proposition_bindings=proposition_bindings,
        concept_cards=concept_cards,
        llm_config=llm_config,
        caller=effective_formalization_caller,
        agenda=agenda,
        audit_concept_keys=audit_concept_keys,
        argument_facets=argument_facets,
        facet_alignments=facet_alignments,
        facet_policies=facet_policies,
    )
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
        proposition_set_digest=(propositions.content_digest if propositions is not None else ""),
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
            propositions=propositions,
            concept_cards=concept_cards,
            argument_briefs=argument_briefs,
            argument_facets=argument_facets,
            facet_alignments=facet_alignments,
            facet_policies=facet_policies,
            formula_packages_by_section={
                result.section_id: _writer_visible_formula_packages(result)
                for result in section_formula_results
            },
            formula_obligations_by_section={
                result.section_id: _writer_visible_formula_obligations(result)
                for result in section_formula_results
            },
            exclude_audit_only_concepts=True,
            audit_override_concept_keys=frozenset(effective_override_keys),
            audit_only_claim_ids=audit_only_claim_ids,
            story_spine_nodes=_story_spine_nodes_from_artifact_paths(artifact_paths),
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
    # Qualifier authority is derived from the persisted Architect plan and
    # frozen claims, not from the (deliberately compact) Writer prompt
    # projection.  Keep this map for every downstream quality owner so a
    # low-level required predicate cannot disappear merely because a
    # concept-card grouping omitted it from one model payload.
    # Q1: audit-only claims never trigger qualifier Rewrite requests; their
    # qualifiers stay in evidence and validation, not in prose obligations.
    qualifier_terms_by_section = _qualifier_terms_by_section(
        plan=plan,
        claims=claims,
        exclude_claim_ids=audit_only_claim_ids,
    )
    # Keep the exact validator predicates visible to the Writer as a compact
    # binding channel.  This is not a prose template and carries no internal
    # fact/claim/frame identifiers; it prevents a proposition-only projection
    # from silently dropping a condition that the reverse validator requires.
    writer_inputs = [
        item.__class__(
            section_id=item.section_id,
            heading=item.heading,
            prompt_payload={
                **item.prompt_payload,
                "required_qualifier_bindings": list(
                    qualifier_terms_by_section.get(item.section_id, ())
                ),
            },
            system_prompt=item.system_prompt,
            publication_mode=item.publication_mode,
            argument_graph=item.argument_graph,
        )
        for item in writer_inputs
    ]
    if effective_resume_section_ids:
        unresolved_callback_ids = _unresolved_local_resume_callback_ids(
            resume_section_ids=effective_resume_section_ids,
            prior_outputs=prior_outputs,
            callback_bundle=callback_bundle,
            callback_artifacts=callback_artifacts,
        )
        if unresolved_callback_ids:
            incumbent = _incumbent_candidate_available(out_root)
            result = PublicationWriterRunResultV1(
                status="blocked",
                plan_digest=plan.content_digest,
                claim_digest=claims.content_digest,
                resumed_section_ids=_pre_writer_resumed_section_ids(effective_resume_section_ids),
                blocked_reason=(
                    "writing_research_callback_artifacts_missing:"
                    + ",".join(sorted(set(unresolved_callback_ids)))
                ),
                candidate_generation_status="generated" if incumbent else "failed",
                candidate_available=incumbent,
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
    writer_transaction_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def writer_transaction_metrics(
        section: WriterSectionInput,
        text: str,
    ) -> dict[str, Any]:
        key = (section.section_id, hashlib.sha256(text.encode()).hexdigest())
        if key not in writer_transaction_cache:
            output = PublicationMethodSectionOutputV1(
                section_id=section.section_id,
                section_markdown=text,
            )
            writer_transaction_cache[key] = _rewrite_transaction_metrics(
                accepted=[(section.section_id, text, "writer-repair-candidate")],
                output_by_section={section.section_id: output},
                writer_inputs={section.section_id: section},
                artifact_paths=artifact_paths,
                claims=claims,
                equations=equations,
                plan=plan,
                propositions=propositions,
                proposition_bindings=proposition_bindings,
                concept_cards=concept_cards,
                llm_config=llm_config,
            )
        return writer_transaction_cache[key]

    def validate_writer_transaction(
        section: WriterSectionInput,
        incumbent_text: str,
        candidate_text: str,
    ) -> tuple[bool, str]:
        return _writer_transaction_has_safe_gain(
            writer_transaction_metrics(section, incumbent_text),
            writer_transaction_metrics(section, candidate_text),
        )

    def _assess_structured_writer_output(
        section: WriterSectionInput,
        response: LLMResponse,
    ) -> dict[str, Any]:
        """Summarize required target progress from the actual parsed output."""

        output = response.metadata
        if not isinstance(output, PublicationMethodSectionOutputV1):
            return {
                "valid_target_count": 0,
                "invalid_count": 1,
                "missing": ("transaction_metadata_missing",),
            }
        packages = tuple(
            item for item in (section.prompt_payload.get("formula_packages") or ())
            if isinstance(item, Mapping)
        )
        obligations = tuple(
            item for item in (section.prompt_payload.get("formula_obligations") or ())
            if isinstance(item, Mapping)
        )
        formula_routes: dict[str, dict[str, Any]] = {}
        for obligation in obligations:
            obligation_id = str(obligation.get("obligation_id") or "").strip()
            if not obligation_id:
                continue
            matches = [
                package for package in packages
                if (
                    str(package.get("obligation_id") or "").strip() == obligation_id
                    or (
                        set(str(item) for item in (obligation.get("facet_ids") or ()))
                        & set(str(item) for item in (package.get("bound_facet_ids") or ()))
                    )
                )
            ]
            formula_routes[obligation_id] = {
                "package_ids": tuple(
                    str(package.get("package_id") or "")
                    for package in matches
                    if str(package.get("package_id") or "").strip()
                ),
                "latex": str(
                    matches[0].get("markdown_block") or matches[0].get("latex") or ""
                ) if matches else "",
            }
        plans = tuple(
            item for item in (section.argument_graph.get("paragraphs") or ())
            if isinstance(item, Mapping)
        )
        transactions = {
            str(item.paragraph_id): item
            for item in (output.paragraphs or ())
            if str(item.paragraph_id or "").strip()
        }
        valid_target_count = 0
        invalid_count = 0
        missing: list[str] = []
        for plan_row in plans:
            transaction = transactions.get(str(plan_row.get("paragraph_id") or ""))
            if transaction is None:
                invalid_count += 1
                missing.append(f"missing_paragraph:{plan_row.get('paragraph_id')}")
                continue
            assessment = assess_paragraph_transaction(
                transaction,
                plan_row=plan_row,
                formula_routes=formula_routes,
            )
            required_count = sum(
                len(values) for values in assessment.required_by_kind.values()
            )
            valid_target_count += sum(
                len(values) for values in assessment.witnessed_by_kind.values()
            )
            if not assessment.valid and required_count:
                invalid_count += 1
                missing.extend(
                    f"{plan_row.get('paragraph_id')}:{kind}:{target}"
                    for kind, values in assessment.missing_by_kind.items()
                    for target in values
                )
        return {
            "valid_target_count": valid_target_count,
            "invalid_count": invalid_count,
            "missing": tuple(dict.fromkeys(missing)),
        }

    def assess_writer_transaction_responses(
        section: WriterSectionInput,
        incumbent_response: LLMResponse,
        candidate_response: LLMResponse,
    ) -> tuple[bool, str]:
        incumbent = _assess_structured_writer_output(section, incumbent_response)
        candidate = _assess_structured_writer_output(section, candidate_response)
        if candidate["invalid_count"] > incumbent["invalid_count"]:
            return False, "transaction_invalid_count_regressed"
        if candidate["valid_target_count"] <= incumbent["valid_target_count"]:
            return False, "required_target_coverage_no_gain"
        return True, "required_target_coverage_gain"

    writer = write_publication_method_by_sections(
        llm_config,
        selected_inputs,
        llm_caller=llm_caller,
        content_transaction_validator=(
            validate_writer_transaction if propositions is not None else None
        ),
        content_transaction_assessor=assess_writer_transaction_responses,
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
    # Binding-contract faults (unknown or duplicate IDs) are malformed Writer
    # responses rather than reviewable prose.  Keep the old blocked semantics
    # for those sections; paragraph-transaction failures below still retain
    # their authored body in the Candidate view.
    candidate_excluded_section_ids: set[str] = set()
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
                persisted_retry = _with_normalized_section_markdown(
                    retry_output,
                    expected_heading=graph.heading,
                )
                output_by_section[graph.section_id] = persisted_retry or retry_output
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
    # WP-W: a structured facet witness is a Writer-owned coverage contract.
    # Give the same Writer a bounded repair turn when required facets are
    # omitted (or when the body is only a caveat shell).  The retry carries
    # the packet, planner drafts, policies, formula packages, and the prior
    # attempt; neither the harness nor Rewrite may fill the missing mechanism.
    facet_retry_inputs: list[WriterSectionInput] = []
    facet_missing_by_section: dict[str, tuple[str, ...]] = {}
    for graph in plan.sections:
        output = output_by_section.get(graph.section_id)
        original_input = input_by_section.get(graph.section_id)
        if output is None or original_input is None:
            continue
        # Paragraph transactions already have a bounded per-section content
        # repair loop.  A second whole-section facet retry would throw away
        # the transaction metadata, duplicate calls, and commonly produce a
        # lexical-only ``no_information_gain`` tail.  Leave the invalid
        # paragraph for its owning transaction repair/assessment instead.
        if bool(original_input.prompt_payload.get("paragraph_transaction_required")):
            continue
        _unknown_facets, _overlap_facets, missing_facets = _writer_facet_coverage(
            output,
            original_input,
        )
        if not missing_facets:
            continue
        facet_missing_by_section[graph.section_id] = tuple(sorted(missing_facets))
        writer_view_payload = original_input.prompt_payload.get("writer_view") or {}
        packet_payload = (
            writer_view_payload.get("mechanism_authoring_packet")
            if isinstance(writer_view_payload, dict) else {}
        ) or {}
        facet_retry_inputs.append(WriterSectionInput(
            section_id=original_input.section_id,
            heading=original_input.heading,
            prompt_payload={
                **original_input.prompt_payload,
                "previous_attempt_error": (
                    "writer_missing_required_facets:"
                    + ",".join(sorted(missing_facets))
                ),
                "previous_attempt_section_markdown": output.section_markdown[:6000],
                "writer_facet_coverage_repair": {
                    "required_facet_ids": list(
                        packet_payload.get("required_facet_ids") or ()
                    ),
                    "missing_facet_ids": list(sorted(missing_facets)),
                    "mechanism_authoring_packet": packet_payload,
                    "mechanism_drafts": list(
                        writer_view_payload.get("mechanism_drafts") or ()
                    ) if isinstance(writer_view_payload, dict) else [],
                    "facet_policies": list(
                        packet_payload.get("facet_policies") or ()
                    ),
                    "formula_packages": list(
                        original_input.prompt_payload.get("formula_packages") or ()
                    ),
                    "previous_attempt": output.section_markdown[:6000],
                    "required_action": (
                        "Rewrite the same section as substantive Method prose. "
                        "Digest each planner_filled draft as an organization seed, "
                        "cover every missing required facet, report its exact id in "
                        "rendered_from_facet_ids, and use deferred_facet_ids only "
                        "for genuinely omitted non-required facets. A caveat may "
                        "qualify content but may not be the content. Never replace "
                        "the mechanism with a deferral memo about missing formula "
                        "packages. When formula_packages is present, embed each "
                        "display-math environment, not a second heading."
                    ),
                },
            },
            system_prompt=original_input.system_prompt,
            publication_mode=original_input.publication_mode,
            argument_graph=original_input.argument_graph,
        ))
    if facet_retry_inputs:
        facet_retry_writer = write_publication_method_by_sections(
            llm_config,
            facet_retry_inputs,
            llm_caller=llm_caller,
            call_id_prefix="LLM-publication-method-section-facet-retry",
        )
        writer.aggregate.traces.extend(facet_retry_writer.aggregate.traces)
        writer.aggregate.response_recovery_traces.extend(
            facet_retry_writer.aggregate.response_recovery_traces
        )
        retry_outputs = {
            item.section_id: item for item in facet_retry_writer.outputs
        }
        retry_aggregate = {
            item.section_id: item for item in facet_retry_writer.aggregate.sections
        }
        replaced_facet_sections: set[str] = set()
        for graph in plan.sections:
            retry_output = retry_outputs.get(graph.section_id)
            original_input = input_by_section.get(graph.section_id)
            if retry_output is None or original_input is None:
                continue
            before_missing = set(facet_missing_by_section.get(graph.section_id, ()))
            _retry_unknown, _retry_overlap, retry_missing = _writer_facet_coverage(
                retry_output,
                original_input,
            )
            if (
                _markdown_has_non_heading_body(
                    _normalize_section_heading_breaks(
                        retry_output.section_markdown,
                        expected_heading=graph.heading,
                    )
                )
                and len(retry_missing) < len(before_missing)
            ):
                persisted_retry = _with_normalized_section_markdown(
                    retry_output,
                    expected_heading=graph.heading,
                )
                output_by_section[graph.section_id] = persisted_retry or retry_output
                if graph.section_id in retry_aggregate:
                    aggregate_by_section[graph.section_id] = retry_aggregate[
                        graph.section_id
                    ]
                facet_missing_by_section[graph.section_id] = tuple(
                    sorted(retry_missing)
                )
                replaced_facet_sections.add(graph.section_id)
        if replaced_facet_sections:
            writer.outputs = [
                output_by_section.get(item.section_id, retry_outputs.get(item.section_id, item))
                if item.section_id in replaced_facet_sections else item
                for item in writer.outputs
            ]
            aggregate_sections = {
                item.section_id: item for item in writer.aggregate.sections
            }
            aggregate_sections.update({
                section_id: retry_aggregate[section_id]
                for section_id in replaced_facet_sections
                if section_id in retry_aggregate
            })
            writer.aggregate.sections = [
                aggregate_sections[item.section_id]
                for item in writer.aggregate.sections
                if item.section_id in aggregate_sections
            ]
        writer.aggregate.cumulative_budget_consumed += (
            facet_retry_writer.aggregate.cumulative_budget_consumed
        )
    # R2: every planned section must have a non-empty coherent Method body.
    # A section whose Writer call produced no usable output is routed BACK to
    # the Writer exactly once (bounded owner retry) with its author-intent
    # purpose and allowed caveated propositions; the harness never omits the
    # section because repository research is incomplete.  A section that
    # still fails after the retry remains honestly incomplete.
    missing_section_trace: list[dict[str, Any]] = []
    retried_section_ids: set[str] = set()
    # Bounded retry rounds (at most two): the local model occasionally emits
    # a body-degenerate or still-truncated section twice in a row; one more
    # whole-section generation is cheap and materially improves the chance
    # that every planned section lands with a coherent non-empty body.
    for retry_round in (1, 2):
        missing_section_inputs: list[WriterSectionInput] = []
        for graph in plan.sections:
            original_input = input_by_section.get(graph.section_id)
            if original_input is None:
                continue
            existing_output = output_by_section.get(graph.section_id)
            if existing_output is not None and _section_output_acceptable(
                existing_output.section_markdown,
                expected_heading=graph.heading,
            ):
                continue
            failure_code = _writer_retry_failure_code(
                existing_output,
                expected_heading=graph.heading,
            )
            retried_section_ids.add(graph.section_id)
            writer_view_payload = (
                original_input.prompt_payload.get("writer_view")
                if isinstance(original_input.prompt_payload, Mapping)
                else {}
            ) or {}
            missing_section_inputs.append(WriterSectionInput(
                section_id=original_input.section_id,
                heading=original_input.heading,
                prompt_payload={
                    **original_input.prompt_payload,
                    "previous_attempt_error": failure_code,
                    "retry_round": retry_round,
                    "previous_attempt_section_markdown": (
                        existing_output.section_markdown[:6000]
                        if existing_output is not None
                        else ""
                    ),
                    "missing_section_retry_instruction": {
                        "reason": (
                            f"The previous Writer call produced no usable output "
                            f"for this planned section ({failure_code})."
                        ),
                        "required_action": _writer_retry_required_action(
                            failure_code,
                            heading=graph.heading,
                        ),
                        "mechanism_drafts": list(
                            writer_view_payload.get("mechanism_drafts") or ()
                        ) if isinstance(writer_view_payload, dict) else [],
                    },
                },
                system_prompt=original_input.system_prompt,
                publication_mode=original_input.publication_mode,
                argument_graph=original_input.argument_graph,
            ))
        if not missing_section_inputs:
            break
        missing_retry_writer = write_publication_method_by_sections(
            llm_config,
            missing_section_inputs,
            llm_caller=llm_caller,
            call_id_prefix=f"LLM-publication-method-section-missing-retry-{retry_round}",
        )
        writer.aggregate.traces.extend(missing_retry_writer.aggregate.traces)
        writer.aggregate.response_recovery_traces.extend(
            missing_retry_writer.aggregate.response_recovery_traces
        )
        missing_outputs = {
            item.section_id: item for item in missing_retry_writer.outputs
        }
        missing_aggregate = {
            item.section_id: item for item in missing_retry_writer.aggregate.sections
        }
        for graph in plan.sections:
            if graph.section_id not in missing_outputs:
                continue
            existing_output = output_by_section.get(graph.section_id)
            retry_output = missing_outputs[graph.section_id]
            retry_ok = _section_output_acceptable(
                retry_output.section_markdown,
                expected_heading=graph.heading,
            )
            incumbent_ok = existing_output is not None and _section_output_acceptable(
                existing_output.section_markdown,
                expected_heading=graph.heading,
            )
            if incumbent_ok and not retry_ok:
                continue
            retry_normalized = _normalize_section_heading_breaks(
                retry_output.section_markdown,
                expected_heading=graph.heading,
            )
            if not retry_ok and (
                not _markdown_has_non_heading_body(retry_normalized)
                or _prose_has_repeated_phrase_spam(retry_normalized)
                or _looks_like_caveat_shell(retry_normalized)
            ):
                # Keep the previous attempt rather than replacing a
                # headings-only or spam body with equally unusable text.
                continue
            persisted_retry = _with_normalized_section_markdown(
                retry_output,
                expected_heading=graph.heading,
            )
            output_by_section[graph.section_id] = persisted_retry or retry_output
            if graph.section_id in missing_aggregate:
                aggregate_by_section[graph.section_id] = missing_aggregate[graph.section_id]
            retry_failure_code = (
                "writer_output_missing_or_incomplete"
                if existing_output is None
                else "section_body_missing_or_headings_only"
                if not _markdown_has_non_heading_body(
                    _normalize_section_heading_breaks(
                        existing_output.section_markdown,
                        expected_heading=graph.heading,
                    )
                )
                else "section_heading_truncated"
            )
            missing_section_trace.append({
                "section_id": graph.section_id,
                "retry_round": retry_round,
                "applied": True,
                "provenance": "writer_missing_section_retry",
                "operations": [
                    "owner_retry_for_missing_section_output:" + retry_failure_code
                ],
                "response_hash": (
                    missing_aggregate[graph.section_id].trace.response_hash
                    if graph.section_id in missing_aggregate
                    and missing_aggregate[graph.section_id].trace is not None
                    else ""
                ),
            })
        outputs_by_id = {item.section_id: item for item in writer.outputs}
        outputs_by_id.update({
            section_id: output_by_section[section_id]
            for section_id in output_by_section
            if section_id in outputs_by_id
        })
        for graph in plan.sections:
            if graph.section_id not in output_by_section:
                continue
            outputs_by_id[graph.section_id] = output_by_section[graph.section_id]
        writer.outputs = [
            outputs_by_id[graph.section_id]
            for graph in plan.sections
            if graph.section_id in outputs_by_id
        ]
        sections_by_id = {
            item.section_id: item for item in writer.aggregate.sections
        }
        sections_by_id.update(aggregate_by_section)
        writer.aggregate.sections = [
            sections_by_id[graph.section_id]
            for graph in plan.sections
            if graph.section_id in sections_by_id
        ]
        sections_by_id = {
            item.section_id: item for item in writer.aggregate.sections
        }
        sections_by_id.update(aggregate_by_section)
        writer.aggregate.sections = [
            sections_by_id[graph.section_id]
            for graph in plan.sections
            if graph.section_id in sections_by_id
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
            persisted_early = _with_normalized_section_markdown(
                output,
                expected_heading=graph.heading,
                formula_packages=(
                    input_by_section[graph.section_id].prompt_payload.get("formula_packages")
                    if graph.section_id in input_by_section
                    and isinstance(input_by_section[graph.section_id].prompt_payload, Mapping)
                    else ()
                ),
                paragraph_plan=(
                    input_by_section[graph.section_id].prompt_payload.get("paragraph_plan") or None
                    if graph.section_id in input_by_section
                    else ()
                ),
            )
            if persisted_early is not None:
                output = persisted_early
                output_by_section[graph.section_id] = output
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
        if output is None or not response_ref:
            candidate_excluded_section_ids.add(graph.section_id)
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
            if aggregate is not None and aggregate.incomplete:
                # Preserve the non-empty model body in Candidate while
                # keeping the section explicitly incomplete for quality and
                # Verified gates.  The transaction assessment below remains
                # the source of the precise missing-target diagnostics.
                section_failures.append("writer_output_incomplete")
            has_research_callbacks = bool(output.new_research_requests)
            proposition_mode = propositions is not None
            if not proposition_mode:
                for label, values in (
                    ("argument_units", output.used_argument_unit_ids),
                    ("claims", output.used_claim_ids),
                    ("equations", output.used_equation_ids),
                    ("configurations", output.used_configuration_ids),
                ):
                    if len(values) != len(set(values)):
                        section_failures.append(f"duplicate_{label}")
                        candidate_excluded_section_ids.add(graph.section_id)
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
                if any(
                    failure.startswith((
                        "unknown_argument_units", "missing_argument_units",
                        "unknown_claims", "missing_claims",
                        "unknown_equations", "missing_equations",
                        "unknown_configurations", "missing_configurations",
                    ))
                    for failure in section_failures
                ):
                    candidate_excluded_section_ids.add(graph.section_id)
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
            if not proposition_mode:
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
                concept_cards=concept_cards,
            )
            primary_briefs = {
                str(value)
                for value in getattr(graph, "primary_brief_ids", ())
                if str(value).strip()
            }
            if primary_briefs:
                missing_briefs = primary_briefs - {
                    str(value) for value in output.rendered_brief_ids
                }
                if missing_briefs:
                    # Completeness warning only: do not drop authored markdown
                    # from Candidate because some primary brief ids were
                    # deferred.  Verified/publication_ready stay fail-closed.
                    quality_failures.append(
                        "missing_required_briefs:" + ",".join(sorted(missing_briefs))
                    )
            for raw_request in output.new_research_requests:
                try:
                    request = WritingResearchRequestV1.model_validate(raw_request)
                except ValueError:
                    section_failures.append("writing_research_request_schema_invalid")
                    continue
                request = fill_writing_research_search_terms(request)
                routed_request = _populate_request_candidates(
                    request,
                    graph=graph,
                    unit_by_id=unit_by_id,
                    authority_proofs=authority_proofs,
                    concept_cards=concept_cards,
                )
                if routed_request is not None:
                    from code2paper.agentic.callback_semantic_contract import (
                        enrich_callback_request_semantics,
                    )
                    from code2paper.agentic.writing_callback_fulfillment import (
                        enrich_writing_research_request_baseline,
                    )

                    binding_by_key = {}
                    if concept_cards is not None:
                        binding_by_key = {
                            str(item.concept_key): item
                            for item in (
                                getattr(concept_cards, "bindings", ()) or ()
                            )
                        }
                    research_requests.append(
                        enrich_writing_research_request_baseline(
                            enrich_callback_request_semantics(
                                routed_request,
                                graph=graph,
                                concept_bindings=binding_by_key,
                            ),
                            concept_bindings=binding_by_key,
                            argument_briefs=argument_briefs,
                        )
                    )
        if section_failures:
            failures.extend(f"{graph.section_id}:{failure}" for failure in section_failures)
        elif output is not None:
            if not response_ref:
                failures.append(f"{graph.section_id}:missing_writer_response_ref")
            else:
                normalized_markdown = _normalize_section_heading_breaks(
                    output.section_markdown,
                    expected_heading=graph.heading,
                )
                persisted = _with_normalized_section_markdown(
                    output,
                    expected_heading=graph.heading,
                    formula_packages=(
                        input_by_section[graph.section_id].prompt_payload.get("formula_packages")
                        if graph.section_id in input_by_section
                        and isinstance(input_by_section[graph.section_id].prompt_payload, Mapping)
                        else ()
                    ),
                    paragraph_plan=(
                        input_by_section[graph.section_id].prompt_payload.get("paragraph_plan") or None
                        if graph.section_id in input_by_section
                        else ()
                    ),
                )
                if persisted is not None:
                    output = persisted
                    if not output.used_claim_ids:
                        inferred = _infer_used_claim_ids(
                            output.section_markdown,
                            claims,
                            allowed_claim_ids=allowed_claims,
                        )
                        if inferred:
                            output = output.model_copy(update={"used_claim_ids": inferred})
                    output_by_section[graph.section_id] = output
                    normalized_markdown = output.section_markdown
                # The paragraph plan is an organization contract, not a
                # request to copy planner wording.  Still record when the
                # Writer collapses a multi-paragraph plan into one body block;
                # Candidate prose remains available, while Verified quality
                # gates can route this typed signal to a bounded rewrite.
                paragraph_plan = (
                    input_by_section[graph.section_id].prompt_payload.get("paragraph_plan", ())
                    if graph.section_id in input_by_section
                    else ()
                )
                if isinstance(paragraph_plan, (list, tuple)) and len(paragraph_plan) > 1:
                    normalized_text = _normalize_writer_representation_noise(
                        str(normalized_markdown or "")
                    )
                    body_blocks = [
                        block.strip()
                        for block in re.split(r"\n\s*\n", normalized_text)
                        if block.strip() and not all(
                            line.lstrip().startswith("#")
                            for line in block.splitlines()
                            if line.strip()
                        )
                    ]
                    if len(body_blocks) < 2:
                        quality_failures.append(
                            f"paragraph_plan_collapsed:{len(body_blocks)}/{len(paragraph_plan)}"
                        )
                    declared_paragraphs = {
                        str(value) for value in output.rendered_paragraph_ids if str(value).strip()
                    }
                    if declared_paragraphs and len(declared_paragraphs) < len(paragraph_plan):
                        quality_failures.append(
                            "paragraph_witness_incomplete:"
                            f"{len(declared_paragraphs)}/{len(paragraph_plan)}"
                        )
                # R2: every planned section must have a non-empty coherent
                # body.  A structured response that contains only heading
                # lines (or a degenerate repeated-heading line) has no
                # Method content; it is not accepted and is routed back to
                # the Writer by the missing-section retry, exactly like a
                # missing output.
                if not _markdown_has_non_heading_body(normalized_markdown):
                    section_failures.append("section_body_missing_or_headings_only")
                    failures.extend(
                        f"{graph.section_id}:{failure}"
                        for failure in section_failures
                    )
                elif _looks_like_caveat_shell(normalized_markdown):
                    section_failures.append("caveat_token_shell")
                    failures.extend(
                        f"{graph.section_id}:{failure}"
                        for failure in section_failures
                    )
                elif _section_body_truncated(normalized_markdown) and graph.section_id not in retried_section_ids:
                    section_failures.append("section_body_truncated")
                    failures.extend(
                        f"{graph.section_id}:{failure}"
                        for failure in section_failures
                    )
                elif _prose_has_repeated_phrase_spam(normalized_markdown):
                    section_failures.append("repeated_token_spam")
                    failures.extend(
                        f"{graph.section_id}:{failure}"
                        for failure in section_failures
                    )
                elif _section_heading_still_truncated(
                    normalized_markdown,
                    expected_heading=graph.heading,
                ) and graph.section_id not in retried_section_ids:
                    # A truncated plan heading copied verbatim (or another
                    # mid-clause cut) is rejected on the FIRST attempt:
                    # completing or shortening the clause is a Writer
                    # generation, and the missing-section retry re-invokes
                    # the Writer with an explicit heading instruction.  A
                    # retried section is accepted even when the model still
                    # truncates; its exact truncated-heading issue then goes
                    # to the Rewrite round (bounded), so the section is never
                    # silently omitted from the candidate.
                    section_failures.append("section_heading_truncated")
                    failures.extend(
                        f"{graph.section_id}:{failure}"
                        for failure in section_failures
                    )
                else:
                    accepted.append((
                        graph.section_id,
                        normalized_markdown,
                        response_ref,
                    ))
        failures.extend(f"{graph.section_id}:{failure}" for failure in quality_failures)
        section_rows.append({
            "section_id": graph.section_id,
            "heading": graph.heading,
            "accepted": not section_failures and bool(response_ref),
            "failures": section_failures + quality_failures,
            "output": output.model_dump(mode="json") if output is not None else None,
        })

    incumbent_digest_before_run = _incumbent_candidate_digest(out_root)
    accepted, output_by_section, incumbent_merge_warnings = _merge_accepted_with_incumbent(
        accepted=accepted,
        output_by_section=output_by_section,
        plan=plan,
        effective_resume_section_ids=effective_resume_section_ids,
        out_root=out_root,
        plan_digest=plan.content_digest,
        claim_digest=claims.content_digest,
        proposition_set_digest=(
            propositions.content_digest if propositions is not None else ""
        ),
    )
    if incumbent_merge_warnings:
        failures.extend(incumbent_merge_warnings)

    # Q0: the first non-empty Writer output becomes the durable incumbent
    # candidate immediately — before validation, Editor, or Rewrite run.
    # A later validator/quality/model failure must never erase it.  Invalid
    # paragraph transactions remain in this Candidate snapshot for review;
    # only ``accepted`` is used for rendered/Verified accounting.
    candidate_checkpoint_written = False
    candidate_preview = _compose_candidate_markdown(
        accepted=accepted,
        plan=plan,
        section_outputs=output_by_section,
        excluded_section_ids=candidate_excluded_section_ids,
    )
    if candidate_preview:
        _write_candidate_checkpoint(
            out_root=out_root,
            stage="initial_writer",
            final_text=candidate_preview,
            accepted=accepted,
            rendered_text="\n\n".join(text for _section_id, text, _ref in accepted),
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            proposition_set_digest=(propositions.content_digest if propositions is not None else ""),
            reason="first_nonempty_writer_output",
        )
        candidate_checkpoint_written = True

    # Content-first writer surface (E1): unresolved prose points become
    # explicit review items; they are never silently dropped.
    unresolved_points: list[tuple[str, str]] = []
    for graph in plan.sections:
        output = output_by_section.get(graph.section_id)
        if output is None:
            continue
        for raw_point in getattr(output, "unresolved_points", ()) or ():
            if hasattr(raw_point, "reason"):
                point = str(raw_point.reason or "").strip()
            elif isinstance(raw_point, dict):
                point = str(raw_point.get("reason") or raw_point.get("text") or "").strip()
            else:
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
                    "unify_symbols_and_formula_placement_without_changing_operations",
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
                llm_config=llm_config,
                editor_caller=editor_caller or llm_caller,
                qualifier_terms_by_section=qualifier_terms_by_section,
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
                        qualifier_terms_by_section=qualifier_terms_by_section,
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
                    if not decision_reasons:
                        decision_reasons = ["document_level_no_gain_without_reason"]
                    failures.append(f"editor:editor_candidate_rejected:{';'.join(decision_reasons)}")
                    regressed_sections = _editor_regressed_section_ids(
                        incumbent_snapshot, candidate_snapshot,
                    )
                    if (
                        decision_reasons == ["document_level_no_gain_without_reason"]
                        or not regressed_sections
                    ):
                        accepted = candidate_accepted
                    else:
                        incumbent_by_id = {
                            section_id: (text, response_ref)
                            for section_id, text, response_ref in editor_incumbent_accepted
                        }
                        accepted = [
                            (
                                section_id,
                                incumbent_by_id[section_id][0],
                                incumbent_by_id[section_id][1],
                            )
                            if section_id in regressed_sections
                            and section_id in incumbent_by_id
                            else (section_id, text, response_ref)
                            for section_id, text, response_ref in candidate_accepted
                        ]
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
                    _write_candidate_checkpoint(
                        out_root=out_root,
                        stage="editor_accepted",
                        final_text="\n\n".join(text for _section_id, text, _ref in accepted),
                        accepted=accepted,
                        plan_digest=plan.content_digest,
                        claim_digest=claims.content_digest,
                        proposition_set_digest=(propositions.content_digest if propositions is not None else ""),
                        reason="editor_transaction_accepted",
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
    # Routing is a separate harness gate from the Writer response schema.
    # Preserve the authored section when one callback is rejected (for example
    # an executable request with no bounded search terms), but surface the
    # rejection in the run diagnostics and omit it from the route artifact.
    for request in research_requests:
        try:
            route_writing_research_request(request)
        except (TypeError, ValueError) as exc:
            failures.append(
                f"{request.section_id}:invalid_writing_research_callback:"
                f"{request.request_id}:{type(exc).__name__}:{str(exc)[:160]}"
            )
    binding_failures = tuple(
        failure for failure in failures
        if any(token in failure for token in (
            "unknown_argument_units", "missing_argument_units",
            "unknown_claims", "missing_claims",
            "unknown_equations", "missing_equations",
            "unknown_configurations", "missing_configurations",
        ))
    )
    final_text_validation_status, final_validation_paths = _safe_validate_final_text(
        out_root=out_root,
        artifact_paths=artifact_paths,
        claims=claims,
        equations=equations,
        final_text=final_text,
        accepted=accepted,
        plan=plan,
        propositions=propositions,
        proposition_bindings=proposition_bindings,
        concept_cards=concept_cards,
        llm_config=llm_config,
    )
    writer_input_by_section = {item.section_id: item for item in writer_inputs}
    style_repair_issues = _academic_rewrite_issues_by_section(
        output_by_section,
        claims=claims,
        writer_inputs=writer_input_by_section,
        qualifier_terms_by_section=qualifier_terms_by_section,
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
    revision_budget = min(1, _section_revision_budget())
    rewrite_enabled = (
        revision_budget > 0
        and bool(style_repair_issues)
        and (
            rewrite_caller is not None
            or _llm_provider_value(llm_config) not in {"", "none"}
        )
    )
    if rewrite_enabled:
        # Q4 (plan 19.8): a unified, configurable section revision budget
        # (default 3 content-revision rounds; product hard cap 5).  Each round
        # re-derives the typed issues, routes them to the Rewrite owner, and
        # commits only when the round shows real gain; a round without gain or
        # with nothing left to fix stops the loop.  The best incumbent is
        # preserved across every round, and audit-only qualifier/style issues
        # never consume budget (Q1 filter).
        for revision_round in range(1, revision_budget + 1):
            if revision_round > 1:
                style_repair_issues = _academic_rewrite_issues_by_section(
                    output_by_section,
                    claims=claims,
                    writer_inputs=writer_input_by_section,
                    qualifier_terms_by_section=qualifier_terms_by_section,
                )
                final_text = "\n\n".join(text for _section_id, text, _response_ref in accepted)
                if not style_repair_issues and not _has_local_validation_repair_issue(
                    final_validation_paths
                ):
                    break  # nothing left to fix: stop, never rerun for luck
            incumbent_accepted = list(accepted)
            incumbent_output_by_section = dict(output_by_section)
            incumbent_generation_owner_by_section = dict(generation_owner_by_section)
            incumbent_final_text = final_text
            incumbent_ledger = ledger
            incumbent_validation_status = final_text_validation_status
            incumbent_validation_counts = _validation_failure_counts(final_validation_paths)
            incumbent_style_issue_count = sum(len(items) for items in style_repair_issues.values())
            transaction_state: dict[str, Any] = {
                "metrics": _rewrite_transaction_metrics(
                    accepted=incumbent_accepted,
                    output_by_section=incumbent_output_by_section,
                    writer_inputs=writer_input_by_section,
                    artifact_paths=artifact_paths,
                    claims=claims,
                    equations=equations,
                    plan=plan,
                    propositions=propositions,
                    proposition_bindings=proposition_bindings,
                    concept_cards=concept_cards,
                    llm_config=llm_config,
                )
            }

            def validate_rewrite_transaction(
                _section_id: str,
                cluster_name: str,
                candidate_sections: list[tuple[str, str, str]],
            ) -> tuple[bool, str, dict[str, Any]]:
                candidate_metrics = _rewrite_transaction_metrics(
                    accepted=candidate_sections,
                    output_by_section=output_by_section,
                    writer_inputs=writer_input_by_section,
                    artifact_paths=artifact_paths,
                    claims=claims,
                    equations=equations,
                    plan=plan,
                    propositions=propositions,
                    proposition_bindings=proposition_bindings,
                    concept_cards=concept_cards,
                    llm_config=llm_config,
                )
                # Persist both sides of the decision so a future rejected
                # transaction identifies the exact non-exempt fragment and
                # the qualifier authority that was used, rather than only
                # reporting an aggregate ``method_style_regressed`` count.
                candidate_metrics = {
                    **candidate_metrics,
                    "before_style_issue_fragments_by_section": (
                        transaction_state["metrics"].get(
                            "style_issue_fragments_by_section", {}
                        )
                    ),
                    "before_qualifier_terms_by_section": (
                        transaction_state["metrics"].get(
                            "qualifier_terms_by_section", {}
                        )
                    ),
                }
                accepted_transaction, reason = _rewrite_transaction_has_cluster_gain(
                    transaction_state["metrics"],
                    candidate_metrics,
                    cluster_name=cluster_name,
                )
                if accepted_transaction:
                    transaction_state["metrics"] = candidate_metrics
                return accepted_transaction, reason, candidate_metrics

            (
                accepted,
                output_by_section,
                generation_owner_by_section,
                round_transitions,
                round_results,
                round_failures,
                round_ledger,
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
                qualifier_terms_by_section=qualifier_terms_by_section,
                transaction_validator=validate_rewrite_transaction,
            )
            rewrite_transitions.extend(round_transitions)
            rewrite_results.extend(round_results)
            rewrite_failures.extend(round_failures)
            failures.extend(round_failures)
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
            # The Rewrite Agent owns only the bytes in its exact patches.
            # Keep the incumbent Writer/Editor spans in the ledger instead of
            # attributing an entire rewritten section to the latest response.
            ledger = round_ledger or build_final_text_authorship_ledger(
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
            final_text_validation_status, final_validation_paths = _safe_validate_final_text(
                out_root=out_root,
                artifact_paths=artifact_paths,
                claims=claims,
                equations=equations,
                final_text=final_text,
                accepted=accepted,
                plan=plan,
                propositions=propositions,
                proposition_bindings=proposition_bindings,
                concept_cards=concept_cards,
                llm_config=llm_config,
            )
            candidate_validation_counts = _validation_failure_counts(final_validation_paths)
            candidate_style_issue_count = sum(
                len(items)
                for items in _academic_rewrite_issues_by_section(
                    output_by_section,
                    claims=claims,
                    writer_inputs=writer_input_by_section,
                    qualifier_terms_by_section=qualifier_terms_by_section,
                ).values()
            )
            applied_transitions = [
                item for item in round_transitions if item.status == "applied"
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
                # A syntactically valid patch is not enough.  Keep a local
                # rewrite only when repository safety does not regress and at
                # least one validator or Method-language issue improves.
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
                # Restore the frozen validation artifacts to the incumbent
                # text as well, so artifact digests and the published
                # candidate agree.
                final_text_validation_status, final_validation_paths = _maybe_validate_final_text(
                    out_root=out_root,
                    artifact_paths=artifact_paths,
                    claims=claims,
                    equations=equations,
                    final_text=final_text,
                    accepted=accepted,
                    plan=plan,
                    propositions=propositions,
                    proposition_bindings=proposition_bindings,
                    concept_cards=concept_cards,
                    llm_config=llm_config,
                )
                for row in section_rows:
                    section_id = row["section_id"]
                    if section_id in output_by_section:
                        row["output"] = output_by_section[section_id].model_dump(mode="json")
                break
            if not applied_transitions:
                break  # no further semantic gain this round: stop
    # Q0: persist the incumbent after every accepted rewrite transaction (or
    # after the rollback restored the pre-rewrite incumbent).
    candidate_after_rewrite = _compose_candidate_markdown(
        accepted=accepted,
        plan=plan,
        section_outputs=output_by_section,
        excluded_section_ids=candidate_excluded_section_ids,
    )
    if candidate_after_rewrite:
        _write_candidate_checkpoint(
            out_root=out_root,
            stage="rewrite_accepted",
            final_text=candidate_after_rewrite,
            accepted=accepted,
            rendered_text="\n\n".join(text for _section_id, text, _ref in accepted),
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            proposition_set_digest=(propositions.content_digest if propositions is not None else ""),
            reason="rewrite_round_completed",
        )
    final_validation_failures = _final_validation_failures_by_section(
        final_validation_paths,
        ledger=ledger,
    )
    required_formula_failures_by_section: dict[str, tuple[str, ...]] = {
        str(item.section_id): tuple(
            str(obligation_id)
            for obligation_id in (
                getattr(item, "required_formula_failures", ()) or ()
            )
            if str(obligation_id).strip()
        )
        for item in section_formula_results
        if getattr(item, "required_formula_failures", ())
    }
    for section_id, obligation_ids in required_formula_failures_by_section.items():
        failures.append(
            "formalization_required_obligation_unresolved:"
            + section_id
            + ":"
            + ",".join(obligation_ids)
        )
    required_facet_failures_by_section: dict[str, tuple[str, ...]] = {}
    for graph in plan.sections:
        output = output_by_section.get(graph.section_id)
        writer_input = writer_input_by_section.get(graph.section_id)
        _unknown_facets, overlap_facets, missing_facets = _writer_facet_coverage(
            output,
            writer_input,
        )
        if _unknown_facets:
            failures.append(
                f"{graph.section_id}:unknown_writer_facets:"
                + ",".join(sorted(_unknown_facets))
            )
        if overlap_facets:
            failures.append(
                f"{graph.section_id}:writer_facet_witness_overlap:"
                + ",".join(sorted(overlap_facets))
            )
        if missing_facets:
            required_facet_failures_by_section[graph.section_id] = tuple(
                sorted(missing_facets)
            )
            failures.append(
                f"{graph.section_id}:writer_missing_required_facets:"
                + ",".join(sorted(missing_facets))
            )
    accepted_section_ids = {section_id for section_id, _text, _ref in accepted}
    incomplete_ids = _candidate_incomplete_section_ids(
        plan_section_ids=tuple(graph.section_id for graph in plan.sections),
        accepted_section_ids=accepted_section_ids,
        callback_section_ids=callback_section_ids,
        required_facet_failures_by_section=required_facet_failures_by_section,
        required_formula_failures_by_section=required_formula_failures_by_section,
        output_by_section=output_by_section,
        writer_input_by_section=writer_input_by_section,
    )
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
    try:
        proposition_alignment_report = _audit_proposition_alignment(
            accepted=accepted,
            plan=plan,
            propositions=propositions,
            llm_config=llm_config,
            validation_paths=final_validation_paths,
        )
    except Exception as exc:  # noqa: BLE001 — model fault: candidate survives as a warning
        proposition_alignment_report = {"error": f"{type(exc).__name__}:{str(exc)[:200]}", "sections": []}
        failures.append(f"proposition_alignment_fault:{type(exc).__name__}")
    try:
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
        propositions=propositions,
        proposition_bindings=proposition_bindings,
        proposition_alignment_report=proposition_alignment_report,
        binding_failures=binding_failures,
        configurations=configurations,
        equations=equations,
        concept_cards=concept_cards,
        facts=facts,
        formula_packages_by_section={
            result.section_id: _writer_visible_formula_packages(result)
            for result in section_formula_results
        },
        concept_audit_override_keys=frozenset(effective_override_keys),
        open_research_requests=tuple(research_requests),
        utility_failures=tuple(failure for failure in failures if failure not in binding_failures),
        # The reverse validator is the product authority for this number.
        # Previously the quality report silently kept its default zero even
        # when the persisted candidate report contained unsupported or
        # unverified positive claims.
        unsupported_positive_claims=len(final_validation_failures),
        final_text_validation_status=final_text_validation_status,
        final_validation_failures=final_validation_failures,
        # Concept-card lane: the reverse validator's supported verdicts are
        # the binding authority for supported-unit recall and the coverage
        # matrix (the Writer's used_claim_ids may be empty and there is no
        # proposition sidecar to expand).  Only status=supported verdicts
        # are expanded; caveated verdicts never authorize repository
        # support.  Each claim is bound to the exact section that rendered
        # its supported sentence (no cross-section false coverage).
        sentence_validated_claim_ids=_sentence_validated_concept_claim_ids(
            validation_paths=final_validation_paths,
            concept_cards=concept_cards,
            claims=claims,
            ledger=ledger,
            facts=facts,
            exclude_concept_keys=audit_concept_keys,
        ),
    )
    except Exception as exc:  # noqa: BLE001 — report/model fault: republish the durable candidate
        return _publish_checkpoint_fallback(
            out_root=out_root,
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            failure=f"quality:{type(exc).__name__}:{str(exc)[:200]}",
        )
    try:
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
        propositions=propositions,
        proposition_alignment_report=proposition_alignment_report,
        section_outputs=tuple(output_by_section.values()),
        excluded_section_ids=candidate_excluded_section_ids,
        )
    except Exception as exc:  # noqa: BLE001 — bundle fault: republish the durable candidate
        return _publish_checkpoint_fallback(
            out_root=out_root,
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            failure=f"bundle:{type(exc).__name__}:{str(exc)[:200]}",
        )
    # Q2 (plan 19.6.4.3): typed formalizer dispositions become review items,
    # never silent completion.
    for _formula_result in section_formula_results:
        _disposition = getattr(_formula_result, "disposition", None)
        required_formula_failures = tuple(
            str(item)
            for item in (
                getattr(_formula_result, "required_formula_failures", ()) or ()
            )
            if str(item).strip()
        )
        preferred_formula_reviews = tuple(
            str(item)
            for item in (
                getattr(_formula_result, "preferred_formula_review_ids", ()) or ()
            )
            if str(item).strip()
        )
        if (
            _disposition is None
            and not required_formula_failures
            and not preferred_formula_reviews
        ) or (
            _disposition is not None
            and not str(getattr(_disposition, "review_question", "") or "")
            and not required_formula_failures
            and not preferred_formula_reviews
        ):
            continue
        review_question = str(
            getattr(_disposition, "review_question", "") or ""
        ) or "Which Formalizer output should close the formula obligation?"
        review_note = str(getattr(_disposition, "review_note", "") or "")
        missing_note = (
            "Required formula obligations remain unresolved: "
            + ", ".join(required_formula_failures)
            if required_formula_failures
            else (
                "Preferred formula obligations remain open for review: "
                + ", ".join(preferred_formula_reviews)
                if preferred_formula_reviews
                else ""
            )
        )
        review_items = tuple(review_items) + (
            MethodReviewCandidateV1(
                candidate_id=f"review-formalization:{_formula_result.section_id}",
                source_obligation_id="",
                section_id=_formula_result.section_id,
                lane="formalization_pending",
                status="formalization_disposition",
                proposed_body=(
                    "The section Formalizer ended with the typed disposition "
                    + str(getattr(_disposition, "disposition", "unknown"))
                    + " for this section's core formula work. "
                    + " ".join(item for item in (review_note, missing_note) if item)
                ),
                confirmation_question=review_question,
                needed_evidence=(
                    (str(getattr(_disposition, "review_note", "") or ""),)
                    if str(getattr(_disposition, "review_note", "") or "").strip()
                    else ()
                ),
                suggested_action="resolve_formalization_disposition",
                blocks_verified=True,
                blocks_candidate=False,
                trace_refs=(),
            ),
        )
    for section_id, facet_ids in required_facet_failures_by_section.items():
        review_items = tuple(review_items) + (
            MethodReviewCandidateV1(
                candidate_id=f"review-writer-missing-facets:{section_id}",
                source_obligation_id="",
                section_id=section_id,
                lane="author_intent_unverified",
                status="writer_missing_required_facets",
                proposed_body=(
                    "The Writer did not substantively cover the required mechanism "
                    "facets after its bounded Writer Repair opportunity: "
                    + ", ".join(facet_ids)
                ),
                confirmation_question=(
                    "Which Writer-owned Method paragraph should cover the missing "
                    "required facets?"
                ),
                needed_evidence=tuple(facet_ids),
                suggested_action="repair_writer_required_facet_coverage",
                blocks_verified=True,
                blocks_candidate=False,
                trace_refs=(),
            ),
        )
    for issue in getattr(quality, "issues", ()) or ():
        if str(getattr(issue, "code", "") or "") != "move_unanchored":
            continue
        section_id = str(getattr(issue, "section_id", "") or "")
        candidate_id = f"review-move-unanchored:{section_id}:{getattr(issue, 'issue_id', issue.code)}"
        review_items = tuple(review_items) + (
            MethodReviewCandidateV1(
                candidate_id=candidate_id[:120],
                source_obligation_id="",
                section_id=section_id,
                lane="formalization_pending",
                status="move_unanchored",
                proposed_body=str(getattr(issue, "message", "") or issue.code),
                confirmation_question=(
                    "Which owner should close this unanchored rhetorical move?"
                ),
                needed_evidence=(),
                suggested_action="resolve_unanchored_rhetorical_move",
                blocks_verified=True,
                blocks_candidate=False,
                trace_refs=(),
            ),
        )
    if final_text_validation_status == "error":
        # Q0: the validator itself failed.  Verified must not be guessed from
        # an unvalidated candidate: reuse the previous same-binding view or be
        # honestly empty, and record an actionable review item.
        same_binding = _same_binding_verified_view(
            out_root=out_root,
            final_text=final_text,
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
        )
        if same_binding is not None:
            verified_markdown = same_binding
            split_report = {
                "split_mode": "validator_error_reused_same_binding_verified",
                "note": "final reverse validator errored; previous same-binding verified view reused",
            }
        else:
            verified_markdown = ""
            split_report = {
                "split_mode": "validator_error_no_verified_reuse",
                "note": "final reverse validator errored; no same-binding verified view exists; Verified left empty",
            }
        review_items = tuple(review_items) + (
            MethodReviewCandidateV1(
                candidate_id="review-validator-error",
                source_obligation_id="",
                section_id="",
                lane="author_intent_unverified",
                status="validator_error",
                proposed_body=(
                    "The final sentence-to-evidence validator raised an exception for this "
                    "candidate. The candidate text is preserved; the Verified view was not "
                    "recomputed from it. Rerun validation on the same binding to rebuild Verified."
                ),
                confirmation_question=(
                    "The final reverse validator errored; should validation be rerun on this "
                    "same binding before Verified is trusted?"
                ),
                needed_evidence=("final_text_validation_error",),
                suggested_action="rerun_final_reverse_validation",
                blocks_verified=True,
                blocks_candidate=False,
                trace_refs=(),
            ),
        )

    # Q0 candidate-first product status: a durable candidate exists whenever
    # any non-empty authored section was produced, even if its transaction
    # failed a required witness check.  Validation verdicts, quality gates,
    # Editor/Rewrite no-progress, callback exhaustion, and later model/API
    # failures become warnings/review items; they never erase the candidate
    # and never turn a generated run into a blocked product run.  "blocked"
    # now means only: no candidate was ever generated (or it could not be
    # persisted).
    persisted_incumbent_digest = _incumbent_candidate_digest(out_root)
    candidate_generation_status: Literal["not_started", "generated", "failed"] = (
        "generated"
        if candidate_markdown.strip() or (
            effective_resume_section_ids and persisted_incumbent_digest
        )
        else "failed"
    )
    candidate_available = candidate_generation_status == "generated"
    status: Literal["success", "incomplete", "blocked"] = (
        "blocked"
        if not candidate_available
        else "success"
        if (
            quality.status == "publication_ready"
            and final_text_validation_status == "passed"
            and not failures
            and not incomplete_ids
            and not plan.incomplete_sections
            and not review_items
            and not external_queue_items
            and verified_markdown.strip()
        )
        else "incomplete"
    )
    blocked_reason = (
        "no_authored_section_passed_binding_and_authorship_gates"
        if status == "blocked"
        else (
            "blocked_authoring_incomplete:"
            + ";".join(
                f"{section_id}:{','.join(facet_ids)}"
                for section_id, facet_ids in sorted(
                    required_facet_failures_by_section.items()
                )
            )
            if required_facet_failures_by_section
            else ""
        )
    )
    # Effective readiness reflects the actual split: any review item, any
    # external queue item, or any sentence excluded from verified demotes a
    # plan-level ``verified_ready`` to ``candidate_ready_with_review``.
    effective_readiness: str = (
        "candidate_ready_with_review"
        if review_items or external_queue_items or verified_markdown != candidate_markdown
        else readiness.readiness
    )
    # Q0 final checkpoint: bind the published candidate and, when the reverse
    # validator passed, the same-binding Verified view for error recovery.
    final_candidate_digest = _digest_text(candidate_markdown) if candidate_markdown else ""
    if candidate_markdown and final_candidate_digest:
        _write_candidate_checkpoint(
            out_root=out_root,
            stage="final",
            final_text=candidate_markdown,
            accepted=accepted,
            rendered_text=final_text,
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            proposition_set_digest=(propositions.content_digest if propositions is not None else ""),
            verified_markdown=(
                verified_markdown if final_text_validation_status == "passed" else ""
            ),
            reason="final_publication",
            last_committed_attempt_id=_publication_attempt_id(
                out_root=out_root,
                plan_digest=plan.content_digest,
                claim_digest=claims.content_digest,
                resumed_section_ids=effective_resume_section_ids,
            ),
        )
    elif not final_candidate_digest and persisted_incumbent_digest:
        failures.append("incumbent_commit_rolled_back_empty_attempt")
        return _publish_checkpoint_fallback(
            out_root=out_root,
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            failure="empty_candidate_attempt_rolled_back_to_incumbent",
        )
    try:
        paths = _write_publication_outputs(
        out_root=out_root,
        candidate_markdown=candidate_markdown,
        verified_markdown=verified_markdown,
        review_items=review_items,
        external_queue_items=external_queue_items,
        split_report=split_report,
        proposition_alignment_report=proposition_alignment_report,
        readiness=readiness,
        effective_readiness=effective_readiness,
        research_requests=research_requests,
        writer=writer,
        ledger=ledger,
        quality=quality,
        section_outputs=output_by_section,
        section_response_refs={section_id: response_ref for section_id, _text, response_ref in accepted},
        proposition_set_digest=(propositions.content_digest if propositions is not None else ""),
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
    except Exception as exc:  # noqa: BLE001 — output publish fault: republish the durable candidate
        return _publish_checkpoint_fallback(
            out_root=out_root,
            plan_digest=plan.content_digest,
            claim_digest=claims.content_digest,
            failure=f"outputs:{type(exc).__name__}:{str(exc)[:200]}",
        )
    transaction_assessment_path, transaction_assessment_digest = (
        _write_paragraph_transaction_assessments(
            out_root=out_root,
            plan=plan,
            section_inputs={item.section_id: item for item in writer_inputs},
            section_outputs=output_by_section,
            formalization_path=formalization_section_path,
        )
    )
    paths["publication_paragraph_transaction_assessments_v1"] = (
        transaction_assessment_path
    )
    paths.update(final_validation_paths)
    generation_trace_path = _write_method_generation_trace(
        out_root=out_root,
        artifact_paths=artifact_paths,
        paths=paths,
        plan=plan,
        writer=writer,
        section_outputs=tuple(output_by_section.values()),
        quality=quality,
        status=status,
        blocked_reason=blocked_reason,
    )
    if generation_trace_path:
        paths["method_generation_trace_v1"] = generation_trace_path
    if concept_cards is not None and ledger is not None:
        try:
            claims_snapshot_path = final_validation_paths.get("final_text_claims", "")
            if claims_snapshot_path and Path(claims_snapshot_path).is_file():
                witness_set = _build_section_content_witness_set(
                    final_claims=load_final_text_claims(claims_snapshot_path),
                    ledger=ledger,
                    concept_cards=concept_cards,
                    claims=claims,
                    facts=facts,
                )
                if witness_set.witnesses:
                    witness_path = method_output(Path(out_root), "section_content_witness_v1")
                    _atomic_write_text(
                        witness_path,
                        witness_set.model_dump_json(indent=2) + "\n",
                    )
                    paths["section_content_witness_v1"] = str(witness_path)
        except (OSError, TypeError, ValueError):
            pass
    if formalization_agent_path:
        paths["formalization_agent_result_v1"] = formalization_agent_path
    if formalization_section_path:
        paths["formalization_section_results_v1"] = formalization_section_path
    if architect_trace_path:
        paths["method_architect_trace_v1"] = architect_trace_path
    if architect_plan_path:
        paths["method_section_plan_v2"] = architect_plan_path
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
            *missing_section_trace,
        ]),
        # ``final_text_digest`` identifies the durable Candidate file.  The
        # rendered/accepted subset used by the strict validator is exposed
        # separately so a Candidate containing invalid paragraphs remains
        # auditable without creating a digest mismatch at callback gating.
        final_text_digest=(
            _digest_text(candidate_markdown)
            if candidate_markdown else persisted_incumbent_digest
        ),
        authorship_ledger_digest=ledger.content_digest,
        publication_quality_digest=quality.content_digest,
        rewrite_transition_digest=rewrite_transition_digest,
        callback_bundle_digest=callback_bundle_digest,
        transaction_assessment_digest=transaction_assessment_digest,
        rendered_text_digest=_digest_text(final_text) if final_text else "",
        # Truthful resume telemetry: zero Writer generation/recovery traces or
        # zero model-call delta means zero actually regenerated sections.  The
        # admitted set (effective resume ids) is reported separately so an
        # admitted-but-blocked resume is never labeled as a resumed section.
        resumed_section_ids=_actually_regenerated_section_ids(
            writer.aggregate,
            effective_resume_section_ids,
        ),
        blocked_reason=blocked_reason,
        candidate_generation_status=candidate_generation_status,
        candidate_available=candidate_available,
        candidate_validation_status=_candidate_validation_status(
            final_text_validation_status
        ),
        candidate_warnings_by_severity=dict(
            quality.candidate_warnings_by_severity or {}
        ),
        verified_validation_status=_verified_validation_status(
            final_text_validation_status=final_text_validation_status,
            verified_markdown=verified_markdown,
        ),
        publication_ready=bool(
            quality.status == "publication_ready"
            and quality.final_integrity_gate_passed
        ),
    )
    result_path = method_output(Path(out_root), "publication_writer_result_v1")
    _atomic_write_text(result_path, result.model_dump_json(indent=2) + "\n")
    paths["publication_writer_result_v1"] = str(result_path)
    # Persist the shared product-authoring overlay after the existing Writer
    # transaction has committed its artifacts.  The overlay is orchestration
    # state only; it does not replace the established local_text_repair path
    # or any of the content-authority gates above.
    product_issues: list[Any] = [
        issue
        for section_issues in style_repair_issues.values()
        for issue in section_issues
    ]
    for section_id in incomplete_ids:
        missing_facets = required_facet_failures_by_section.get(section_id, ())
        product_issues.append(ProductAuthoringIssueV1(
            issue_id=f"writer:{section_id}",
            issue_type=(
                "writer_missing_required_facets"
                if missing_facets else "section_incomplete"
            ),
            owner="writer",
            section_id=str(section_id),
            source="publication_method_writer",
            reason=(
                "required facets missing:" + ",".join(missing_facets)
                if missing_facets else "section was not admitted"
            ),
        ))
    for request in research_requests:
        if request.status == "open":
            product_issues.append(ProductAuthoringIssueV1(
                issue_id=f"research:{request.request_id}",
                issue_type="writing_research_continue",
                owner="research_continuation",
                section_id=request.section_id,
                source="section_writer_callback",
                reason="Writer requested bounded research continuation",
            ))
    try:
        _product_state, product_state_path = (
            persist_product_authoring_state_from_writer(
                out_root=out_root,
                artifact_paths={**artifact_paths, **paths},
                run_id=str(artifact_paths.get("run_id") or ""),
                open_issues=product_issues,
                affected_section_ids=(
                    *incomplete_ids,
                    *result.resumed_section_ids,
                ),
                terminal_status=(
                    "completed"
                    if status == "success"
                    else "blocked"
                    if status == "blocked"
                    else "review_ready_with_warnings"
                ),
                stop_reason=blocked_reason or (
                    "authoring_complete" if status == "success"
                    else "authoring_requires_review"
                ),
            )
        )
        paths["product_authoring_state_v1"] = product_state_path
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        # State telemetry must be fail-closed and observable without erasing
        # the already committed Candidate/Verified publication outputs.
        pass
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
                "6144",
            )
        )
    except ValueError:
        configured_budget = 6144
    formalizer_config = config.model_copy(update={
        "max_output_tokens": min(config.max_output_tokens, max(1024, min(configured_budget, 16384))),
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
                **_formalizer_observability(response, config=formalizer_config),
            })
            continue
        parsed, error = try_parse_structured_response(response.text, FormalizationProposalV1)
        if parsed is None:
            attempt_log.append({
                "attempt": attempt,
                "status": _formalizer_schema_status(response),
                "error": str(error)[:200],
                "response_ref": response.response_hash,
                "guard_failures": [],
                **_formalizer_observability(response, config=formalizer_config),
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


def _writer_visible_formula_packages(result: Any) -> tuple[dict[str, Any], ...]:
    """Project section formula packages onto the Writer reader surface.

    Package ids are exposed only as closed response bindings; bound evidence
    ids remain harness-private.  The Writer must report which package it
    consumed, while prose never contains these identifiers.
    """

    visible: list[dict[str, Any]] = []
    for item in (getattr(result, "packages", ()) or ()):
        if str(getattr(item, "authority_status", "") or "") not in {
            "code_verified", "accepted", "author_intent", "partial",
        }:
            continue
        latex = str(getattr(item, "latex", "") or "").strip()
        if not latex or is_bare_binary_expression(latex):
            continue
        visible.append({
            "package_id": item.package_id,
            "purpose": item.purpose,
            "latex": item.latex,
            "markdown_block": item.markdown_block,
            "prose_explanation": item.prose_explanation,
            "symbol_definitions": [
                {"symbol": symbol, "meaning": meaning}
                for symbol, meaning in item.symbol_definitions
            ],
            "symbol_table": [
                symbol.model_dump(mode="json")
                for symbol in (item.symbol_table or ())
            ],
            "material_conditions": list(item.material_conditions),
            "assumptions": list(item.assumptions),
            "authority_status": item.authority_status,
            "formula_lane": item.formula_lane,
            "bound_facet_ids": list(item.bound_facet_ids),
            "bound_equation_ids": list(item.bound_equation_ids),
            "review_status": item.review_status,
            "risks": list(item.risks),
            "review_question": item.review_question,
        })
    return tuple(visible)


def _writer_visible_formula_obligations(result: Any) -> tuple[dict[str, Any], ...]:
    """Project per-obligation formula truth for the Writer (WP3 Slice 3B)."""

    return tuple({
        "obligation_id": truth.obligation_id,
        "outcome": truth.outcome,
        "review_question": truth.review_question,
        "reason": truth.reason,
        "expectation": truth.expectation,
        "blocking": truth.blocking,
    } for truth in (getattr(result, "obligation_truths", ()) or ()))


def _mechanism_section_payload(
    *,
    graph: Any,
    writer_view: Any | None,
    formula_packages: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    formula_obligations: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> dict[str, Any]:
    """WP5 primary Writer structure: mechanism first, supporting facts nested."""

    view = {}
    if writer_view is not None:
        view = (
            writer_view.model_dump(mode="json")
            if hasattr(writer_view, "model_dump")
            else dict(writer_view)
        )
    positive = list(view.get("positive_concepts") or ())
    caveated = list(view.get("caveated_concepts") or ())
    by_key = {
        str(item.get("concept_key") or ""): item
        for item in (*positive, *caveated)
        if str(item.get("concept_key") or "").strip()
    }
    supporting_keys = {
        str(key) for key in (getattr(graph, "supporting_concept_keys", ()) or ())
        if str(key).strip()
    }
    supporting_facts = [
        {
            "concept_key": item.get("concept_key"),
            "method_subject": item.get("method_subject") or item.get("intended_subject"),
            "operation": item.get("operation") or item.get("intended_transformation"),
            "role": "supporting",
        }
        for key, item in by_key.items()
        if key in supporting_keys
    ]
    primary_keys = [
        str(key) for key in (getattr(graph, "primary_concept_keys", ()) or ())
        if str(key).strip()
    ] or [
        key for key in by_key if key not in supporting_keys
    ]
    ordered_primary: list[dict[str, Any]] = []
    for index, key in enumerate(primary_keys):
        item = by_key.get(key)
        if item is None:
            continue
        ordered_primary.append({
            "concept_key": key,
            "method_subject": item.get("method_subject") or item.get("intended_subject") or "",
            "operation": item.get("operation") or item.get("intended_transformation") or "",
            "inputs": list(item.get("inputs") or ()),
            "outputs": list(item.get("outputs") or ()),
            "conditions": list(item.get("conditions") or ()),
            "supporting_facts": list(item.get("supporting_facts") or ()) or (
                supporting_facts if index == 0 else []
            ),
        })
    accepted_formulas = [
        package for package in formula_packages
        if str(package.get("authority_status") or "") in {"code_verified", "accepted"}
        and str(package.get("latex") or "").strip()
    ]
    candidate_formulas = [
        package for package in formula_packages
        if str(package.get("latex") or "").strip()
    ]
    unresolved_formula = [
        truth for truth in formula_obligations
        if str(truth.get("outcome") or "") == "unresolved"
    ]
    open_slots = [
        *(
            (
                slot.model_dump(mode="json")
                if hasattr(slot, "model_dump")
                else dict(slot)
            )
            for slot in (getattr(graph, "open_slots", ()) or ())
        ),
        *(
            {
                "slot_id": f"slot:{graph.section_id}:{truth.get('obligation_id')}",
                "owner": "formalizer",
                "authority_lane": "formal_derivation",
                "target_concept_key": "",
                "slot_kind": "missing_formula_obligation",
                "blocking_for_candidate": False,
                "blocking_for_verified": True,
            }
            for truth in unresolved_formula
        ),
    ]
    chain: list[str] = []
    if getattr(graph, "required_dataflow_relation_ids", ()):
        chain.extend(("input", "transformation", "output"))
    if getattr(graph, "formula_obligation_ids", ()) and not getattr(
        graph, "formula_not_applicable", False
    ):
        chain.append("formula")
    return {
        "reader_question": graph.reader_question,
        "ordered_primary_concepts": ordered_primary,
        "required_dataflow_relation_ids": list(
            getattr(graph, "required_dataflow_relation_ids", ()) or ()
        ),
        "accepted_formulas": accepted_formulas,
        "candidate_formulas": candidate_formulas,
        "caveated_open_slots": open_slots,
        "chain_contract": list(dict.fromkeys(chain)),
        "formula_obligation_ids": list(getattr(graph, "formula_obligation_ids", ()) or ()),
        "primary_concept_keys": list(getattr(graph, "primary_concept_keys", ()) or ()),
        "supporting_concept_keys": list(getattr(graph, "supporting_concept_keys", ()) or ()),
        "open_slots": open_slots,
    }


def _section_formalizer_reader_points(
    *,
    units: list[Any],
    proposition_by_id: dict[str, Any],
    card_by_key: dict[str, Any],
    audit_concept_keys: frozenset[str] = frozenset(),
) -> list[dict[str, str]]:
    """Reader-facing formalization points for one section (R2).

    Proposition lane: the section's propositions (reader surface only).
    Concept lane: the section's concept cards (reader surface only), with
    audit_only cards excluded unless the author story overrides them.
    """

    points: list[dict[str, str]] = []
    for unit in units:
        for proposition_id in (unit.proposition_order or unit.proposition_ids):
            proposition = proposition_by_id.get(str(proposition_id))
            if proposition is None:
                continue
            points.append({
                "reader_subject": str(getattr(proposition, "reader_subject", "") or ""),
                "transformation": str(getattr(proposition, "transformation", "") or ""),
                "conditions": "; ".join(str(item) for item in (proposition.conditions or ())),
                "authority_lane": str(getattr(proposition, "evidence_lane", "") or ""),
            })
        for concept_key in (unit.concept_card_order or unit.concept_card_ids):
            card = card_by_key.get(str(concept_key))
            if card is None:
                continue
            if str(concept_key) in audit_concept_keys:
                continue
            points.append({
                "reader_subject": str(getattr(card, "method_subject", "") or ""),
                "transformation": str(getattr(card, "operation", "") or ""),
                "conditions": "; ".join(str(item) for item in (card.conditions or ())),
                "authority_lane": str(getattr(card, "authority_lane", "") or ""),
            })
    return points


def _section_formalizer_constraints(
    *,
    units: list[Any],
    proposition_by_id: dict[str, Any],
    card_by_key: dict[str, Any],
) -> list[str]:
    """Immutable numeric/formula constraints for one section (R2)."""

    constraints: list[str] = []
    for unit in units:
        for proposition_id in (unit.proposition_order or unit.proposition_ids):
            proposition = proposition_by_id.get(str(proposition_id))
            if proposition is None:
                continue
            constraints.extend(
                str(item) for item in (
                    *(getattr(proposition, "immutable_numeric_tokens", ()) or ()),
                    *(getattr(proposition, "immutable_formula_tokens", ()) or ()),
                ) if str(item).strip()
            )
        for concept_key in (unit.concept_card_order or unit.concept_card_ids):
            card = card_by_key.get(str(concept_key))
            if card is None:
                continue
            constraints.extend(
                str(item) for item in (
                    *(getattr(card, "numeric_constraints", ()) or ()),
                    *(getattr(card, "formula_constraints", ()) or ()),
                ) if str(item).strip()
            )
    return list(dict.fromkeys(constraints))


def _section_formula_obligations(
    *,
    graph: Any,
    facets: tuple[Any, ...] | list[Any],
    obligation_ids: tuple[str, ...],
    core: list[Any],
    formula_constraints: list[str],
    primary_brief_ids: set[str] | frozenset[str] = frozenset(),
) -> tuple[Any, ...]:
    """Build typed formula obligations from facets and section planning.

    The graph's legacy opaque ids remain valid.  Facet expectations add
    stable ids for the new required/preferred/none contract without making
    incidental equations into obligations.  Equation ids from the plan are
    kept only when they match this section's selected core equations, so a
    neighboring SSM obligation cannot flood a readout section.
    """

    from code2paper.agentic.formalization_agent import MethodFormulaObligationV2

    if bool(getattr(graph, "formula_not_applicable", False)):
        return ()

    core_ids = {
        str(getattr(equation, "equation_id", "") or "").strip()
        for equation in core
        if str(getattr(equation, "equation_id", "") or "").strip()
    }
    primary = {str(item).strip() for item in primary_brief_ids if str(item).strip()}
    obligations: list[Any] = []
    seen_ids: set[str] = set()
    for facet in facets:
        expectation = str(getattr(facet, "formula_expectation", "none") or "none")
        if expectation == "none":
            continue
        brief_id = str(getattr(facet, "brief_id", "") or "").strip()
        if primary and brief_id and brief_id not in primary:
            continue
        facet_id = str(getattr(facet, "facet_id", "") or "").strip()
        if not facet_id:
            continue
        obligation_id = f"formula:facet:{facet_id}"
        semantic_fields = getattr(facet, "semantic_fields", {}) or {}
        mathematical_goal = str(
            semantic_fields.get("mathematical_goal")
            or semantic_fields.get("formula_goal")
            or getattr(facet, "exact_source_quote", "")
            or "Formalize the mechanism facet."
        ).strip()
        facet_paragraphs = tuple(
            paragraph for paragraph in (getattr(graph, "paragraphs", ()) or ())
            if facet_id in (getattr(paragraph, "required_facet_ids", ()) or ())
            or (
                str(getattr(paragraph, "paragraph_role", "") or "") == "formula"
                and facet_id in (getattr(paragraph, "required_facet_ids", ()) or ())
            )
        )
        paragraph_ids = tuple(
            str(getattr(paragraph, "paragraph_id", "") or "")
            for paragraph in facet_paragraphs
            if str(getattr(paragraph, "paragraph_id", "") or "").strip()
        )
        formula_paragraph_ids = tuple(
            str(getattr(paragraph, "paragraph_id", "") or "")
            for paragraph in facet_paragraphs
            if str(getattr(paragraph, "paragraph_role", "") or "") == "formula"
            and str(getattr(paragraph, "paragraph_id", "") or "").strip()
        )
        consumer_paragraph_id = (
            formula_paragraph_ids[0]
            if len(formula_paragraph_ids) == 1
            else paragraph_ids[0]
            if len(paragraph_ids) == 1
            else ""
        )
        ordered_slots = tuple(dict.fromkeys(
            str(slot_id)
            for paragraph in facet_paragraphs
            for slot_id in (getattr(paragraph, "ordered_semantic_slot_ids", ()) or ())
            if str(slot_id).strip()
        ))
        required_edges = tuple(dict.fromkeys(
            str(edge_id)
            for paragraph in facet_paragraphs
            for edge_id in (getattr(paragraph, "required_edge_ids", ()) or ())
            if str(edge_id).strip()
        ))
        raw_preconditions = semantic_fields.get("conditions") or semantic_fields.get("preconditions") or ()
        if isinstance(raw_preconditions, str):
            raw_preconditions = (raw_preconditions,)
        obligation = MethodFormulaObligationV2(
            obligation_id=obligation_id,
            facet_ids=(facet_id,),
            expectation=expectation,
            mathematical_goal=mathematical_goal,
            authority_requirements=(
                "repository_derived_or_explicit_author_intent",
            ),
            section_id=str(graph.section_id),
            consumer_paragraph_id=consumer_paragraph_id,
            paragraph_ids=paragraph_ids,
            ordered_semantic_slot_ids=ordered_slots,
            required_edge_ids=required_edges,
            preconditions=tuple(
                str(value).strip() for value in raw_preconditions if str(value).strip()
            ),
            formula_lane="repository_derived" if core else "author_intent_academic",
            exact_source_quotes=(
                str(getattr(facet, "exact_source_quote", "") or "").strip(),
            ) if str(getattr(facet, "exact_source_quote", "") or "").strip() else (),
        )
        obligations.append(obligation)
        seen_ids.add(obligation_id)
    for obligation_id in obligation_ids:
        normalized = str(obligation_id).strip()
        if not normalized or normalized in seen_ids:
            continue
        if not _formula_obligation_matches_core(normalized, core_ids):
            continue
        obligation_paragraphs = tuple(
            paragraph
            for paragraph in (getattr(graph, "paragraphs", ()) or ())
            if normalized in (getattr(paragraph, "formula_obligation_ids", ()) or ())
        )
        obligations.append(MethodFormulaObligationV2(
            obligation_id=normalized,
            expectation="required",
            mathematical_goal=(
                "Formalize the section's authorized mechanism equation."
                if core or formula_constraints
                else "Resolve the planned formula obligation."
            ),
            authority_requirements=("closed_repository_evidence",),
            section_id=str(graph.section_id),
            consumer_paragraph_id=(
                str(getattr(obligation_paragraphs[0], "paragraph_id", "") or "")
                if len(obligation_paragraphs) == 1 else ""
            ),
            paragraph_ids=tuple(
                str(getattr(paragraph, "paragraph_id", "") or "")
                for paragraph in obligation_paragraphs
                if str(getattr(paragraph, "paragraph_id", "") or "").strip()
            ),
            ordered_semantic_slot_ids=tuple(dict.fromkeys(
                str(slot_id)
                for paragraph in obligation_paragraphs
                for slot_id in (getattr(paragraph, "ordered_semantic_slot_ids", ()) or ())
                if str(slot_id).strip()
            )),
            required_edge_ids=tuple(dict.fromkeys(
                str(edge_id)
                for paragraph in obligation_paragraphs
                for edge_id in (getattr(paragraph, "required_edge_ids", ()) or ())
                if str(edge_id).strip()
            )),
            formula_lane="repository_derived",
        ))
        seen_ids.add(normalized)
    if not obligations:
        formula_not_applicable = bool(getattr(graph, "formula_not_applicable", False))
        author_formula = False
        if not formula_not_applicable:
            from code2paper.agentic.method_argument_facet_aligner import (
                _has_author_formula_signal,
            )
            for facet in facets:
                brief_id = str(getattr(facet, "brief_id", "") or "").strip()
                if primary and brief_id and brief_id not in primary:
                    continue
                quote = str(getattr(facet, "exact_source_quote", "") or "")
                if _has_author_formula_signal(quote):
                    author_formula = True
                    break
        # LinearRAG 234218 MA-S2/S3: Architect attached formula:equation
        # ids whose compiled expressions were incidental ``x+y`` / ``x*y``.
        # Those ids do not match empty ``core``, so they never become
        # formula_obligations and the author-intent Formalizer is skipped.
        # Keep a section derivation obligation so one bounded academic
        # attempt still runs.  Incidental arithmetic stays out of ``core``
        # and cannot count as repository-derived success.  Do not synthesize
        # when formula_not_applicable (DyG readout / LinearRAG MA-S1).
        plan_needs_formula = bool(obligation_ids) and not formula_not_applicable
        if core or formula_constraints or author_formula or plan_needs_formula:
            obligations.append(MethodFormulaObligationV2(
                obligation_id=f"formula:section:{graph.section_id}:derivation",
                expectation="required",
                mathematical_goal="Formalize the section's mechanism in reader-facing notation.",
                authority_requirements=("closed_repository_evidence_or_author_intent",),
                section_id=str(graph.section_id),
            ))
    return tuple(obligations)


def _formula_obligation_matches_core(
    obligation_id: str,
    core_ids: set[str],
) -> bool:
    """Keep plan equation obligations only when this section selected them."""

    if not core_ids:
        return False
    tail = str(obligation_id or "").strip()
    if tail.startswith("formula:"):
        tail = tail[len("formula:"):]
    if tail.startswith("equation:"):
        candidates = {tail, tail[len("equation:"):]}
    else:
        candidates = {tail, f"equation:{tail}"}
    return bool(candidates & core_ids) or any(
        core_id.endswith(tail) or tail.endswith(core_id)
        for core_id in core_ids
        if core_id and tail
    )


def _facet_alignment_excerpts(
    *,
    facets: tuple[Any, ...] | list[Any],
    alignments: tuple[Any, ...] | list[Any],
) -> tuple[dict[str, Any], ...]:
    """Project exact alignment excerpts into the Formalizer request."""

    facet_ids = {
        str(getattr(facet, "facet_id", "") or "")
        for facet in facets
        if str(getattr(facet, "facet_id", "") or "").strip()
    }
    rows: list[dict[str, Any]] = []
    for alignment in alignments:
        facet_id = str(getattr(alignment, "facet_id", "") or "")
        if facet_ids and facet_id not in facet_ids:
            continue
        for excerpt in (getattr(alignment, "exact_excerpts", ()) or ()):
            rows.append(
                excerpt.model_dump(mode="json")
                if hasattr(excerpt, "model_dump")
                else dict(excerpt)
            )
    return tuple(rows)


def _run_section_formalizer(
    *,
    out_root: str | Path,
    plan: MethodSectionPlanV2,
    equations: EquationClaimSetV1,
    facts: Any,
    claims: AtomicClaimSetV3,
    propositions: MethodPropositionSetV1 | None,
    proposition_bindings: PropositionBindingSidecarV1 | None,
    concept_cards: Any | None,
    llm_config: LLMConfig,
    caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None,
    agenda: Any | None = None,
    audit_concept_keys: frozenset[str] = frozenset(),
    argument_facets: tuple[Any, ...] | list[Any] = (),
    facet_alignments: tuple[Any, ...] | list[Any] = (),
    facet_policies: tuple[Any, ...] | list[Any] = (),
) -> tuple[tuple[Any, ...], str]:
    """Run the section-scoped Formalizer (R2) for every planned section.

    Each section's input is built from its story objective, reader-facing
    propositions or audit-filtered concept cards, the exact repository
    bindings of its claims' facts, formula constraints, and author notation
    hints.  Equations are derived from the section's claims' facts in
    addition to any unit-attached equation ids, so a formula-centric section
    is never blanket-labeled not_applicable merely because its plan unit
    lacks a preattached equation id.  A section with core equation evidence
    must end with accepted packages or a typed disposition; an empty result
    is never silent completion.
    """

    from code2paper.agentic.formalization_agent import (
        FormalizationSectionResultV1,
        build_deterministic_formula_packages,
        build_mechanism_equation_evidence_packs,
        section_result_from_packages,
        select_core_equations,
        validate_section_formula_package,
    )

    unit_by_id = {item.argument_unit_id: item for item in plan.argument_units}
    proposition_by_id = {
        item.proposition_id: item
        for item in (propositions.propositions if propositions is not None else ())
    }
    card_by_key = {
        str(card.concept_key): card
        for card in (concept_cards.cards if concept_cards is not None else ())
    }
    claim_by_id = {str(item.claim_id): item for item in claims.claims}
    fact_by_id = {str(fact.fact_id): fact for fact in facts.facts}
    equation_by_id = {
        str(item.equation_id): item for item in (equations.equations if equations is not None else ())
    }
    # Author notation hints: candidate symbols/notes from the reference
    # agenda's formal-objects obligations (project-neutral).
    notation_hints = tuple(dict.fromkeys(
        str(value).strip()
        for obligation in (agenda.obligations if agenda is not None else ())
        if str(getattr(obligation, "obligation_class", "") or "").strip()
        in {"formal_objects_and_notation", "notation"}
        for value in (
            *(getattr(obligation, "candidate_symbols", ()) or ()),
            *(getattr(obligation, "notes", ()) or ()),
        )
        if str(value).strip()
    ))
    results: list[FormalizationSectionResultV1] = []
    section_call_traces: list[dict[str, Any]] = []
    for graph in plan.sections:
        units = [
            unit_by_id[unit_id]
            for unit_id in graph.argument_unit_ids
            if unit_id in unit_by_id
        ]
        section_brief_ids = {
            str(brief_id)
            for unit in units
            for brief_id in (getattr(unit, "brief_order", ()) or getattr(unit, "brief_ids", ()) or ())
            if str(brief_id).strip()
        }
        section_facets = tuple(
            facet
            for facet in argument_facets
            if not str(getattr(facet, "brief_id", "") or "").strip()
            or str(getattr(facet, "brief_id", "")) in section_brief_ids
        )
        obligation_ids = tuple(
            str(item) for item in (getattr(graph, "formula_obligation_ids", ()) or ())
            if str(item).strip()
        )
        formula_not_applicable = bool(getattr(graph, "formula_not_applicable", False))
        direct_equation_ids = {
            str(equation_id)
            for unit in units
            for equation_id in unit.equation_ids
        }
        section_claim_ids = {
            str(claim_id) for unit in units for claim_id in unit.claim_ids
        }
        section_fact_ids = {
            str(fact_id)
            for claim_id in section_claim_ids
            if claim_id in claim_by_id
            for fact_id in claim_by_id[claim_id].fact_ids
        }
        # Concept-card lane: resolve section facts and claims through the
        # exact Concept -> fact -> claim span projection (review Q1).  A
        # concept binds only the facts whose own spans overlap its bound
        # fragments; source obligation ids never expand the section set.
        concept_keys = {
            str(k)
            for unit in units
            for k in (unit.concept_card_order or unit.concept_card_ids)
            if str(k).strip()
        }
        if concept_cards is not None and concept_keys:
            from code2paper.agentic.publication_relevance import (
                concept_bound_claim_ids,
                concept_bound_fact_ids,
            )

            concept_fact_ids = concept_bound_fact_ids(
                concept_cards=concept_cards,
                concept_keys=concept_keys,
                facts=facts,
            )
            section_fact_ids.update(concept_fact_ids)
            concept_claim_ids = concept_bound_claim_ids(
                concept_cards=concept_cards,
                concept_keys=concept_keys,
                claims=claims,
                facts=facts,
            )
            for claim_id in concept_claim_ids:
                section_claim_ids.add(str(claim_id))
                claim = claim_by_id.get(str(claim_id))
                if claim is not None:
                    section_fact_ids.update(
                        str(f) for f in (getattr(claim, "fact_ids", ()) or ())
                    )
        # Proposition lane: resolve section facts, claims, and equations through proposition bindings
        prop_ids = {
            str(p)
            for unit in units
            for p in (unit.proposition_order or unit.proposition_ids)
            if str(p).strip()
        }
        if proposition_bindings is not None and prop_ids:
            for binding in (getattr(proposition_bindings, "bindings", ()) or ()):
                if binding.proposition_id in prop_ids:
                    section_claim_ids.update(str(c) for c in (getattr(binding, "claim_ids", ()) or ()))
                    section_fact_ids.update(str(f) for f in (getattr(binding, "bound_fact_ids", ()) or ()))
                    direct_equation_ids.update(str(e) for e in (getattr(binding, "equation_ids", ()) or ()))

        bound_equation_ids = direct_equation_ids | {
            str(equation_id)
            for equation_id, equation in equation_by_id.items()
            if set(equation.fact_ids) & section_fact_ids
        }
        core = select_core_equations(
            equations=equations,
            facts=facts,
            allowed_equation_ids=bound_equation_ids,
        )
        reader_points = _section_formalizer_reader_points(
            units=units,
            proposition_by_id=proposition_by_id,
            card_by_key=card_by_key,
            audit_concept_keys=audit_concept_keys,
        )
        formula_constraints = _section_formalizer_constraints(
            units=units,
            proposition_by_id=proposition_by_id,
            card_by_key=card_by_key,
        )
        formula_obligations = _section_formula_obligations(
            graph=graph,
            facets=section_facets,
            obligation_ids=obligation_ids,
            core=core,
            formula_constraints=formula_constraints,
            primary_brief_ids={
                str(value)
                for value in getattr(graph, "primary_brief_ids", ()) or ()
                if str(value).strip()
            },
        )
        evidence_packs = build_mechanism_equation_evidence_packs(
            section_id=graph.section_id,
            equations=equations,
            facts=facts,
            allowed_equation_ids=bound_equation_ids,
            author_statements=tuple(
                str(getattr(facet, "exact_source_quote", "") or "")
                for facet in section_facets
                if str(getattr(facet, "exact_source_quote", "") or "").strip()
            ),
        )
        exact_excerpts = _facet_alignment_excerpts(
            facets=section_facets,
            alignments=facet_alignments,
        )
        required_formula = any(
            item.expectation == "required" for item in formula_obligations
        )
        # Formula packages are generated only when the section plan exposes a
        # paragraph-level consumer.  Older hand-built plans do not carry the
        # new paragraph field, so retain their explicit obligation/core
        # behaviour for compatibility with persisted pre-ledger artifacts.
        planned_paragraphs = tuple(getattr(graph, "paragraphs", ()) or ())
        # A section-level boolean is too coarse: it used to invoke the
        # Formalizer for one connected-looking obligation and then discard
        # packages for obligations that had no Writer consumer.  Treat each
        # obligation independently and require exactly one current consumer;
        # retain the single-entry legacy paragraph_ids fallback for frozen
        # pre-ledger plans only.
        consumer_obligations = tuple(
            obligation
            for obligation in formula_obligations
            if obligation.expectation in {"required", "preferred"}
            and bool(
                str(getattr(obligation, "consumer_paragraph_id", "") or "").strip()
                or len(tuple(getattr(obligation, "paragraph_ids", ()) or ())) == 1
            )
        )
        formula_consumer = (
            bool(consumer_obligations)
            if planned_paragraphs
            else bool(required_formula or core)
        )
        from code2paper.agentic.scientific_claim_ir import l1_chain_length

        chain_length = l1_chain_length(facts) if facts is not None else 0
        if not core:
            # Formalizer LLM is not on the default path.  A required
            # obligation plus an L1 chain of length >= 2 may request paper
            # notation; lone incidental binary ops never do.
            packages = ()
            call_traces: list[dict[str, Any]] = []
            if caller is not None and required_formula and chain_length >= 2 and formula_consumer:
                packages, call_traces = _invoke_section_formalizer_llm(
                    graph=graph,
                    unit_by_id=unit_by_id,
                    proposition_by_id=proposition_by_id,
                    card_by_key=card_by_key,
                    core=(),
                    equations=equations,
                    facts=facts,
                    reader_points=reader_points,
                    formula_constraints=formula_constraints,
                    notation_hints=notation_hints,
                    llm_config=llm_config,
                    caller=caller,
                    author_intent_lane=True,
                    formula_not_applicable=bool(
                        getattr(graph, "formula_not_applicable", False)
                    ),
                    formula_obligation_required=required_formula,
                    formula_obligations=formula_obligations,
                    evidence_packs=evidence_packs,
                    exact_excerpts=exact_excerpts,
                    author_facets=section_facets,
                    organization_seed="; ".join(
                        str(getattr(unit, "design_objective", "") or "").strip()
                        for unit in units
                        if str(getattr(unit, "design_objective", "") or "").strip()
                    ),
                )
            if packages:
                results.append(section_result_from_packages(
                    section_id=graph.section_id,
                    packages=packages,
                    obligation_ids=obligation_ids,
                    formula_not_applicable=formula_not_applicable,
                    formula_obligations=formula_obligations,
                    evidence_packs=evidence_packs,
                ))
                section_call_traces.append({
                    "section_id": graph.section_id,
                    "core_equation_ids": [],
                    "call_traces": call_traces,
                    "author_intent_lane": True,
                    "formula_consumer": formula_consumer,
                    "deterministic_fallback": False,
                    "preferred_formula_obligation_ids": [
                        item.obligation_id
                        for item in formula_obligations
                        if item.expectation == "preferred"
                    ],
                })
                continue
            results.append(section_result_from_packages(
                section_id=graph.section_id,
                packages=(),
                obligation_ids=obligation_ids,
                formula_not_applicable=formula_not_applicable and not formula_obligations,
                formula_obligations=formula_obligations,
                evidence_packs=evidence_packs,
            ))
            section_call_traces.append({
                "section_id": graph.section_id,
                "core_equation_ids": [],
                "call_traces": call_traces,
                "author_intent_lane": True,
                "deterministic_fallback": True,
                "formula_consumer": formula_consumer,
                "required_formula_obligation_ids": [
                    item.obligation_id
                    for item in formula_obligations
                    if item.expectation == "required"
                ],
                "preferred_formula_obligation_ids": [
                    item.obligation_id
                    for item in formula_obligations
                    if item.expectation == "preferred"
                ],
            })
            continue
        packages = ()
        call_traces: list[dict[str, Any]] = []
        if caller is not None and formula_consumer:
            packages, call_traces = _invoke_section_formalizer_llm(
                graph=graph,
                unit_by_id=unit_by_id,
                proposition_by_id=proposition_by_id,
                card_by_key=card_by_key,
                core=core,
                equations=equations,
                facts=facts,
                reader_points=reader_points,
                formula_constraints=formula_constraints,
                notation_hints=notation_hints,
                llm_config=llm_config,
                caller=caller,
                formula_not_applicable=bool(
                    getattr(graph, "formula_not_applicable", False)
                ),
                formula_obligation_required=required_formula,
                formula_obligations=formula_obligations,
                evidence_packs=evidence_packs,
                exact_excerpts=exact_excerpts,
                author_facets=section_facets,
                organization_seed="; ".join(
                    str(getattr(unit, "design_objective", "") or "").strip()
                    for unit in units
                    if str(getattr(unit, "design_objective", "") or "").strip()
                ),
            )
        if not packages and formula_consumer:
            packages = build_deterministic_formula_packages(
                section_id=graph.section_id,
                equations=equations,
                facts=facts,
                allowed_equation_ids=bound_equation_ids,
            )
        if packages:
            valid_packages: list[Any] = []
            allowed_facet_ids = {
                str(getattr(facet, "facet_id", "") or "")
                for facet in section_facets
                if str(getattr(facet, "facet_id", "") or "").strip()
            }
            for package in packages:
                package_failures = validate_section_formula_package(
                    package,
                    equations=equations,
                    facts=facts,
                    allowed_facet_ids=allowed_facet_ids or None,
                    formula_obligations=tuple(formula_obligations),
                    require_consumer=bool(
                        formula_obligations and (getattr(graph, "paragraphs", ()) or ())
                    ),
                )
                if not package_failures:
                    valid_packages.append(package)
            packages = tuple(valid_packages)
        results.append(section_result_from_packages(
            section_id=graph.section_id,
            packages=packages,
            obligation_ids=obligation_ids,
            formula_not_applicable=formula_not_applicable,
            formula_obligations=formula_obligations,
            evidence_packs=evidence_packs,
        ))
        section_call_traces.append({
            "section_id": graph.section_id,
            "core_equation_ids": [str(item.equation_id) for item in core],
            "call_traces": call_traces,
            "deterministic_fallback": bool(call_traces) is False,
            "formula_consumer": formula_consumer,
            "required_formula_obligation_ids": [
                item.obligation_id
                for item in formula_obligations
                if item.expectation == "required"
            ],
            "preferred_formula_obligation_ids": [
                item.obligation_id
                for item in formula_obligations
                if item.expectation == "preferred"
            ],
        })
    payload = {
        "schema_version": "1.0",
        "sections": [item.model_dump(mode="json") for item in results],
        "formalizer_call_traces": section_call_traces,
    }
    path = method_output(Path(out_root), "formalization_section_results_v1")
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return tuple(results), str(path)

def _formalizer_observability(response: Any, *, config: Any, raw_preview_limit: int = 400) -> dict[str, Any]:
    """Trace fields that distinguish truncation from malformed JSON."""

    usage = getattr(response, "token_usage", None) or {}
    finish = str(getattr(response, "finish_reason", "") or "")
    text = str(getattr(response, "text", "") or "")
    completion = 0
    for key in ("completion_tokens", "output_tokens", "generated_tokens"):
        value = usage.get(key) if isinstance(usage, dict) else None
        if isinstance(value, int) and value > 0:
            completion = value
            break
    return {
        "finish_reason": finish,
        "completion_tokens": completion,
        "max_output_tokens": int(getattr(config, "max_output_tokens", 0) or 0),
        "raw_preview": text[:raw_preview_limit],
    }


def _formalizer_schema_status(response: Any) -> str:
    finish = str(getattr(response, "finish_reason", "") or "")
    if finish == "length":
        return "schema_failed_truncated"
    return "schema_failed_malformed"


def _invoke_section_formalizer_llm(
    *,
    graph: Any,
    unit_by_id: dict[str, Any],
    proposition_by_id: dict[str, Any],
    card_by_key: dict[str, Any],
    core: list[Any],
    equations: EquationClaimSetV1,
    facts: Any,
    reader_points: list[dict[str, str]],
    formula_constraints: list[str],
    notation_hints: tuple[str, ...],
    llm_config: LLMConfig,
    caller: Callable[[LLMConfig, LLMRequest], LLMResponse],
    author_intent_lane: bool = False,
    formula_not_applicable: bool = False,
    formula_obligation_required: bool = False,
    formula_obligations: tuple[Any, ...] = (),
    evidence_packs: tuple[Any, ...] = (),
    exact_excerpts: tuple[dict[str, Any], ...] = (),
    author_facets: tuple[Any, ...] = (),
    organization_seed: str = "",
) -> tuple[Any, ...]:
    """Bounded LLM Formalizer call for one section (Q2, low temperature).

    Every proposed package passes the deterministic authority guards; a
    guard failure returns to the owning Agent for exactly one bounded retry.
    A second failure keeps the package out (typed disposition downstream).

    ``author_intent_lane`` (review P0-Q2): the section has a formula
    obligation (author/architect formula constraints) but no code-licensed
    core equation.  The Formalizer may then propose at most one
    ``author_intent`` / ``partial`` / ``paper_code_mismatch`` formula that
    states the story mechanism in paper notation and preserves the
    constraints exactly; ``code_verified`` is rejected in this lane.
    """

    from code2paper.agentic.formalization_agent import (
        AuthorIntentSectionFormalizerResponseV1,
        SectionFormalizerResponseV1,
        coerce_section_formalizer_response,
        validate_section_formalizer_response,
        validate_section_formula_package,
    )
    from code2paper.llm.response_schemas import (
        _loads_json_or_extract_object,
        json_schema_for,
        try_parse_structured_response,
    )
    from code2paper.llm.role_config import (
        METHOD_SECTION_FORMALIZER,
        apply_role_config,
        role_generation_config,
    )

    role_config = role_generation_config(METHOD_SECTION_FORMALIZER)
    try:
        configured_budget = int(os.environ.get(
            "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_PUBLICATION_FORMALIZER",
            str(role_config.max_output_tokens_default),
        ))
    except ValueError:
        configured_budget = role_config.max_output_tokens_default
    formalizer_base_config = apply_role_config(llm_config, METHOD_SECTION_FORMALIZER)
    formalizer_config = formalizer_base_config.model_copy(update={
        "max_output_tokens": min(
            formalizer_base_config.max_output_tokens,
            max(1024, min(configured_budget, role_config.max_output_tokens_default)),
        ),
        "reasoning_effort": "none",
        "thinking_token_budget": None,
        "temperature": min(
            formalizer_base_config.temperature,
            0.2,
        ),
    })
    del proposition_by_id, card_by_key, unit_by_id
    reader_propositions = reader_points
    obligation_rows = [
        item.model_dump(mode="json")
        if hasattr(item, "model_dump")
        else dict(item)
        for item in formula_obligations
    ]
    facet_rows = [
        {
            "facet_id": str(getattr(facet, "facet_id", "") or ""),
            "clause_id": str(getattr(facet, "clause_id", "") or ""),
            "exact_source_quote": str(
                getattr(facet, "exact_source_quote", "") or ""
            ),
            "facet_kind": str(getattr(facet, "facet_kind", "") or ""),
            "semantic_fields": dict(getattr(facet, "semantic_fields", {}) or {}),
            "formula_expectation": str(
                getattr(facet, "formula_expectation", "none") or "none"
            ),
            "search_terms": list(getattr(facet, "search_terms", ()) or ()),
            "required": bool(getattr(facet, "required", False)),
        }
        for facet in author_facets
    ]
    evidence_pack_rows = [
        item.model_dump(mode="json")
        if hasattr(item, "model_dump")
        else dict(item)
        for item in evidence_packs
    ]
    equation_rows = [
        {
            "equation_id": item.equation_id,
            "expression": item.expression,
            "conditions": list(item.conditions),
            "operation_descriptors": list(item.operation_descriptors),
            "formula_role": str(
                getattr(item, "formula_role", "publication_candidate")
                or "publication_candidate"
            ),
            "symbol_bindings": [
                {"symbol": binding.symbol, "operand_value": binding.operand_value}
                for binding in item.symbol_bindings
            ],
        }
        for item in core
    ]
    accepted: list[Any] = []
    guard_log: list[list[str]] = []
    self_trace_rows: list[dict[str, Any]] = []
    must_emit_author_package = bool(author_intent_lane) and (
        formula_obligation_required
        or any(
            str(getattr(item, "expectation", "") or "") in {"required", "preferred"}
            for item in formula_obligations
        )
    )
    lane_contract = (
        (
            "This section has NO code-licensed core equation. You MUST produce "
            "at most ONE formula package with authority_status author_intent, "
            "partial or paper_code_mismatch (NEVER code_verified): state the "
            "section's core mechanism in academic paper notation. Use the "
            "supplied formula obligation and author quote as scope; do not "
            "invent a module, loss, guarantee, or implementation fact. Return "
            "a renderable markdown_block with display math, define the symbols, "
            "and state assumptions explicitly. Missing repository line numbers "
            "are NOT a reason to omit latex: put the upgrade question in "
            "review_question on the emitted author_intent_academic package. "
            "Do not return outcome=unresolved with an empty package list."
        )
        if author_intent_lane
        else (
            "Produce paper-level LaTeX formula packages for the authorized core equations. "
            "For each package provide formula_lane repository_derived, purpose "
            "(the Method question the formula answers), latex (display math body preserving "
            "the exact operands, operators, numbers "
            "and dimensions of the authorized expression; you may choose notation and "
            "symbol names but must NOT add operations, constants, dimensions or causal "
            "conclusions), prose_explanation (one to three reader sentences), "
            "markdown_block containing renderable display math, "
            "symbol_definitions (every symbol used in latex), material_conditions and "
            "assumptions from the equation conditions, authority_status "
            "(code_verified only when bound to the supplied equations; otherwise "
            "author_intent, partial or paper_code_mismatch with a review_question), "
            "risks, and bound_fact_ids/bound_equation_ids from the supplied sets. "
            "The reader_propositions/concept points carry the section's story "
            "mechanisms: prefer them when choosing which core equation each package "
            "formalizes. Preserve the supplied formula_constraints exactly, and "
            "honor the author notation_hints when naming symbols. "
            "Never claim convergence, optimality, statistical significance, or any "
            "property the code facts cannot license."
        )
    )
    lane_name = "author_intent_academic" if author_intent_lane else "repository_derived"
    author_intent_retry_instruction = (
        " Previous attempt returned outcome=unresolved with no packages. "
        "That is not allowed on the author_intent_academic lane. Emit ONE "
        "academic package now; put the missing-code question in review_question. "
        "Do not refuse to write latex because code_verified line numbers are absent."
    )
    response_model = (
        AuthorIntentSectionFormalizerResponseV1
        if must_emit_author_package
        else SectionFormalizerResponseV1
    )
    for attempt in (1, 2):
        retry_suffix = (
            " Previous packages failed deterministic guards: "
            + "; ".join(guard_log[-1])
            if guard_log and guard_log[-1]
            else ""
        )
        if must_emit_author_package and attempt == 2:
            retry_suffix = author_intent_retry_instruction + (
                (" " + retry_suffix) if retry_suffix else ""
            )
        must_emit_prefix = (
            "Return JSON with outcome=rendered and at least one packages item. "
            if must_emit_author_package
            else "Return only JSON matching the section formalizer response schema for "
        )
        request = LLMRequest(
            prompt_template_id="agentic_publication_section_formalizer_v1",
            prompt=(
                must_emit_prefix
                + f"section {graph.section_id}. The section answers: "
                f"{graph.reader_question}. "
                + lane_contract
                + (
                    ""
                    if must_emit_author_package
                    else (
                        " Use outcome rendered with packages when a formula is authorized; "
                        "outcome unresolved with review_question when evidence is incomplete; "
                        "outcome not_applicable only when no formula obligation applies."
                        if formula_obligation_required
                        else ""
                    )
                )
                + " Formula lane: " + lane_name + ". "
                + retry_suffix
            ),
            input_payload={
                "section_id": graph.section_id,
                "reader_question": graph.reader_question,
                "reader_propositions": reader_propositions,
                "formula_constraints": list(formula_constraints),
                "formula_obligations": obligation_rows,
                "author_facets": facet_rows,
                "organization_seed": organization_seed,
                "evidence_packs": evidence_pack_rows,
                "exact_evidence_excerpts": list(exact_excerpts),
                "notation_hints": list(notation_hints),
                "core_equations": equation_rows,
                "formula_obligation_required": formula_obligation_required,
                "formula_not_applicable": (
                    False if must_emit_author_package else formula_not_applicable
                ),
                "formula_lane": lane_name,
                "contract": (
                    "author_intent_academic_scoped"
                    if author_intent_lane
                    else "repository_derived_exact_closure"
                ),
            },
            schema_name=(
                "agentic_publication_section_formalizer_author_intent_v1"
                if must_emit_author_package
                else "agentic_publication_section_formalizer_v1"
            ),
            response_json_schema=json_schema_for(response_model),
        )
        response = caller(formalizer_config, request)
        response_ref = getattr(response, "response_hash", "")
        if response.blocked_reason or not (response.text or "").strip():
            guard_log.append(["response_blocked"])
            self_trace_rows.append({
                "attempt": attempt,
                "status": "blocked",
                "blocked_reason": str(response.blocked_reason or "")[:200],
                "response_ref": response_ref,
                "guard_failures": [],
                **_formalizer_observability(response, config=formalizer_config),
            })
            continue
        parsed_raw, _error = try_parse_structured_response(
            response.text, response_model
        )
        parsed = coerce_section_formalizer_response(
            parsed_raw,
            section_id=graph.section_id,
        )
        if parsed is None:
            try:
                extracted = _loads_json_or_extract_object(response.text)
            except (TypeError, ValueError, json.JSONDecodeError):
                extracted = None
            parsed = coerce_section_formalizer_response(
                extracted,
                section_id=graph.section_id,
            )
        if parsed is None or parsed.section_id != graph.section_id:
            guard_log.append(["schema_failed"])
            self_trace_rows.append({
                "attempt": attempt,
                "status": _formalizer_schema_status(response),
                "error": str(_error)[:200],
                "response_ref": response_ref,
                "guard_failures": [],
                **_formalizer_observability(response, config=formalizer_config),
            })
            continue
        obligation_failures = validate_section_formalizer_response(
            parsed,
            section_id=graph.section_id,
            formula_obligation_required=formula_obligation_required,
            formula_not_applicable=formula_not_applicable,
            formula_obligations=tuple(formula_obligations),
        )
        if obligation_failures:
            guard_log.append(obligation_failures)
            self_trace_rows.append({
                "attempt": attempt,
                "status": "obligation_failed",
                "response_ref": response_ref,
                "guard_failures": obligation_failures,
                **_formalizer_observability(response, config=formalizer_config),
            })
            continue
        if parsed.outcome == "unresolved" and parsed.packages:
            parsed = parsed.model_copy(update={"outcome": "rendered"})
        if parsed.outcome == "unresolved":
            empty_code = (
                "author_intent_empty_forbidden"
                if must_emit_author_package
                else "formalizer_unresolved"
            )
            guard_log.append([empty_code])
            self_trace_rows.append({
                "attempt": attempt,
                "status": "declined_empty",
                "outcome": parsed.outcome,
                "review_question": parsed.review_question,
                "response_ref": response_ref,
                "guard_failures": [empty_code],
                **_formalizer_observability(response, config=formalizer_config),
            })
            if must_emit_author_package and attempt == 1:
                continue
            break
        if parsed.outcome == "not_applicable":
            guard_log.append(["formalizer_not_applicable"])
            self_trace_rows.append({
                "attempt": attempt,
                "status": "declined_empty",
                "outcome": parsed.outcome,
                "reason": parsed.reason,
                "response_ref": response_ref,
                "guard_failures": [],
                **_formalizer_observability(response, config=formalizer_config),
            })
            if must_emit_author_package and attempt == 1:
                continue
            break
        failures: list[str] = []
        allowed_facet_ids = {
            str(getattr(facet, "facet_id", "") or "")
            for facet in author_facets
            if str(getattr(facet, "facet_id", "") or "").strip()
        }
        for package in parsed.packages:
            if author_intent_lane and package.authority_status == "code_verified":
                failures.append(
                    f"{package.package_id}:author_intent_lane_forbids_code_verified"
                )
            if author_intent_lane and package.formula_lane == "repository_derived":
                failures.append(
                    f"{package.package_id}:author_intent_lane_requires_academic_lane"
                )
            if not author_intent_lane and package.formula_lane == "author_intent_academic":
                failures.append(
                    f"{package.package_id}:repository_lane_forbids_author_intent_formula"
                )
            package_failures = validate_section_formula_package(
                package,
                equations=equations,
                facts=facts,
                allowed_facet_ids=allowed_facet_ids or None,
                formula_obligations=tuple(formula_obligations),
                require_consumer=bool(
                    formula_obligations and (getattr(graph, "paragraphs", ()) or ())
                ),
            )
            if package_failures:
                failures.extend(
                    f"{package.package_id}:{failure}" for failure in package_failures
                )
            else:
                accepted.append(package)
        guard_log.append(failures)
        if not failures and not parsed.packages:
            status = "declined_empty" if author_intent_lane else "accepted"
        elif not failures:
            status = "accepted"
        else:
            status = "guards_failed"
        self_trace_rows.append({
            "attempt": attempt,
            "status": status,
            "outcome": parsed.outcome,
            "proposed_package_count": len(parsed.packages),
            "accepted_package_count": len(accepted),
            "response_ref": response_ref,
            "guard_failures": failures,
            **_formalizer_observability(response, config=formalizer_config),
        })
        if not failures and parsed.packages:
            break
        if status == "declined_empty":
            if must_emit_author_package and attempt == 1:
                continue
            break
    return tuple(accepted), self_trace_rows


def _editor_section_snapshot(
    *,
    sections: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    claims: Any,
    equations: Any,
    configurations: Any,
    outputs: dict[str, PublicationMethodSectionOutputV1] | None = None,
    section_contexts: Mapping[str, Mapping[str, Any]] | None = None,
    qualifier_terms_by_section: Mapping[str, tuple[str, ...]] | None = None,
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
    rendered_propositions: set[str] = set()
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
        section_rendered: dict[str, set[str]] = {
            "claims": set(), "equations": set(), "configs": set(),
            "propositions": set(),
        }
        # Publication Editor works against Method propositions. Atomic code
        # claims remain reverse-validation anchors, but their lexical
        # ``loads/calls/range`` surface is not a writing-retention contract.
        # On proposition-backed sections, do not force an academic paraphrase
        # to retain those low-level tokens.
        has_writer_view = bool(
            (section_contexts.get(section_id, {}) or {}).get("writer_view")
        )
        if not has_writer_view:
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
        section_propositions = _editor_rendered_proposition_ids(
            text, section_contexts.get(section_id, {})
        )
        if output is not None and output.rendered_proposition_ids:
            # The structured Writer response is the incumbent proposition
            # disposition. Lexical matching remains only a legacy fallback;
            # it must not turn academic paraphrase into an apparent loss.
            section_propositions.update(output.rendered_proposition_ids)
        rendered_propositions.update(section_propositions)
        section_rendered["propositions"].update(section_propositions)
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
    formula_environment_count = sum(
        len(_FORMULA_ENVIRONMENT_RE.findall(text))
        for _section_id, text, _ref in sections
    )
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
    ], exempt_qualifier_terms=qualifier_terms_by_section))
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
        "rendered_propositions": rendered_propositions,
        "rendered_by_section": rendered_by_section,
        "generic_style_issue_count": generic_style_issue_count,
        "candidate_authority_violations": candidate_authority_violations,
        "formula_environment_count": formula_environment_count,
        "coherent": required_moves and all(
            item[0] in section_ids for item in required_moves
        ),
    }


def _ratio_count(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


#: Display/inline math environments the Editor must never delete (Q2).
#: Symbol unification may change content inside an environment, but removing
#: a formula environment regresses the document and is rejected.
_FORMULA_ENVIRONMENT_RE = re.compile(
    r"\$\$[^$]+\$\$"
    r"|\\\[[\s\S]+?\\\]"
    r"|\\\([^)]+\\\)"
    r"|\\begin\{(?:equation\*?|align\*?|aligned|gather\*?|multline\*?)\}"
    r"[\s\S]+?"
    r"\\end\{(?:equation\*?|align\*?|aligned|gather\*?|multline\*?)\}"
)


_CANDIDATE_AUTHORITY_MARKERS = (
    "we aim", "we intend", "we formulate", "we hypothesize", "we assume",
    "we propose to", "our intended design", "the intended design",
    "repository evidence partially", "available repository evidence partially",
    "the current repository covers", "pending", "awaiting", "unverified",
    "requires confirmation", "mismatch", "not yet verified",
)


def _editor_rendered_proposition_ids(
    text: str,
    context: Mapping[str, Any],
) -> set[str]:
    """Conservatively detect WriterView propositions retained by Editor."""

    writer_view = context.get("writer_view") or {}
    rows = [
        *(writer_view.get("positive_propositions") or ()),
        *(writer_view.get("caveated_propositions") or ()),
    ]
    sentences = [
        sentence for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
        if sentence.strip() and not sentence.lstrip().startswith("#")
    ]
    rendered: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        proposition_id = str(row.get("proposition_id") or "")
        subject = str(row.get("reader_subject") or row.get("intended_subject") or "")
        transformation = str(
            row.get("transformation") or row.get("intended_transformation") or ""
        )
        key_tokens = set(_content_tokens(" ".join((subject, transformation))))
        if not proposition_id or not key_tokens:
            continue
        caveated = "required_caveat_kind" in row
        for sentence in sentences:
            sentence_tokens = set(_content_tokens(sentence))
            overlap = len(sentence_tokens & key_tokens) / max(1, len(key_tokens))
            if overlap < 0.6:
                continue
            if caveated and not any(
                marker in sentence.casefold() for marker in _CANDIDATE_AUTHORITY_MARKERS
            ):
                continue
            rendered.add(proposition_id)
            break
    return rendered


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

    del claims  # Evidence bindings remain in the harness, outside the Editor prompt.
    contexts: dict[str, dict[str, Any]] = {}
    for writer_input in writer_inputs:
        section_id = str(writer_input.section_id)
        output = outputs.get(section_id)
        payload = writer_input.prompt_payload
        authorized_heading = str(writer_input.heading or "").strip()
        if output is not None:
            first_line = str(output.section_markdown or "").lstrip().splitlines()[:1]
            if first_line and first_line[0].lstrip().startswith("#"):
                rendered = first_line[0].lstrip("# ").strip()
                if rendered:
                    authorized_heading = rendered
        contexts[section_id] = {
            "authorized_heading": authorized_heading,
            "section": dict(payload.get("section") or {}),
            "writer_view": dict(payload.get("writer_view") or {}),
            # Reader-facing claims remain useful to replayed V1 Editor
            # responses and provide a compact semantic cross-check during the
            # V2 transition. They never carry source spans or authorize facts
            # beyond the four-layer WriterView.
            "reader_facing_claims": list(
                payload.get("reader_facing_claims") or ()
            ),
            "required_qualifier_bindings": list(
                payload.get("required_qualifier_bindings") or ()
            ),
            "incumbent_rendered_proposition_ids": list(
                output.rendered_proposition_ids if output is not None else ()
            ),
            "incumbent_deferred_proposition_ids": list(
                output.deferred_proposition_ids if output is not None else ()
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
    candidate_reported_proposition_ids: Mapping[str, set[str]] | None = None,
    qualifier_terms_by_section: Mapping[str, tuple[str, ...]] | None = None,
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
        qualifier_terms_by_section=qualifier_terms_by_section,
    )
    candidate_snapshot = _editor_section_snapshot(
        sections=candidate,
        plan=plan,
        claims=claims,
        equations=equations,
        configurations=configurations,
        outputs=outputs,
        section_contexts=section_contexts,
        qualifier_terms_by_section=qualifier_terms_by_section,
    )
    for section_id, proposition_ids in (
        candidate_reported_proposition_ids or {}
    ).items():
        candidate_snapshot["rendered_propositions"].update(proposition_ids)
        candidate_snapshot["rendered_by_section"].setdefault(
            section_id,
            {"claims": set(), "equations": set(), "configs": set(), "propositions": set()},
        )["propositions"].update(proposition_ids)
    reasons: list[str] = []
    for section_id in sorted(
        set(incumbent_snapshot["rendered_by_section"]) | set(candidate_snapshot["rendered_by_section"])
    ):
        incumbent_rendered = incumbent_snapshot["rendered_by_section"].get(
            section_id, {
                "claims": set(), "equations": set(), "configs": set(),
                "propositions": set(),
            }
        )
        candidate_rendered = candidate_snapshot["rendered_by_section"].get(
            section_id, {
                "claims": set(), "equations": set(), "configs": set(),
                "propositions": set(),
            }
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
        lost_propositions = sorted(
            incumbent_rendered["propositions"]
            - candidate_rendered["propositions"]
        )
        if lost_propositions:
            reasons.append(
                f"candidate_proposition_loss:{section_id}:"
                f"{','.join(lost_propositions[:6])}"
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
    if (
        candidate_snapshot["formula_environment_count"]
        < incumbent_snapshot["formula_environment_count"]
    ):
        reasons.append("candidate_formula_environment_lost")
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
        len(candidate_snapshot["rendered_propositions"])
        > len(incumbent_snapshot["rendered_propositions"]),
        bool(candidate_reported_proposition_ids) and candidate != incumbent,
    ]
    if reasons:
        decision = "reject"
    elif any(improvements):
        decision = "accept"
    else:
        decision = "reject"
        reasons = ["document_level_no_gain_without_reason"]
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
    llm_config: LLMConfig | None = None,
    editor_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    qualifier_terms_by_section: Mapping[str, tuple[str, ...]] | None = None,
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
    try:
        requested_repairs = int(
            os.environ.get("CODE2PAPER_PUBLICATION_EDITOR_REPAIR_ATTEMPTS", "1")
        )
    except ValueError:
        requested_repairs = 1
    repair_attempts = max(0, min(requested_repairs, 2))
    for section_id in [item[0] for item in incumbent]:
        section_patches = patches_by_section.get(section_id, [])
        if not section_patches:
            continue
        proposed_text = str(editor_result.sections.get(section_id) or "")
        expected_heading = str(
            (section_contexts.get(section_id) or {}).get("authorized_heading") or ""
        ).strip() or next(
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
            qualifier_terms_by_section=qualifier_terms_by_section,
            candidate_reported_proposition_ids={
                section_id: {
                    *section_patches[-1].rendered_proposition_ids,
                    *section_patches[-1].caveated_proposition_ids,
                }
            },
        )
        if regressions or decision != "accept":
            local_reasons = [*regressions, *reasons] or [f"{section_id}:no_local_gain"]
            repaired = False
            for _attempt in range(repair_attempts):
                base_context = dict(section_contexts.get(section_id, {}))
                base_context["editor_feedback"] = list(local_reasons)
                repair_result = CrossSectionEditor().revise_one_section_with_llm(
                    section_id,
                    original_sections[section_id],
                    section_context=base_context,
                    document_context={
                        "repair_mode": "semantic_academic_editor",
                        "failed_reasons": list(local_reasons),
                    },
                    config=llm_config,
                    caller=editor_caller,
                )
                if repair_result.blocked_reason or not repair_result.patches:
                    break
                repair_patches = list(repair_result.patches)
                repair_text = str(repair_result.sections.get(section_id) or "")
                repair_candidate = [
                    (
                        sid,
                        repair_text if sid == section_id else text,
                        (
                            repair_patches[-1].generation_trace_ids[-1]
                            if sid == section_id and repair_patches[-1].generation_trace_ids
                            else response_ref
                        ),
                    )
                    for sid, text, response_ref in working
                ]
                repair_decision, repair_reasons, _rb, _ra = _editor_candidate_decision(
                    incumbent=working,
                    candidate=repair_candidate,
                    plan=plan,
                    claims=claims,
                    equations=equations,
                    configurations=configurations,
                    outputs=outputs,
                    section_contexts=section_contexts,
                    qualifier_terms_by_section=qualifier_terms_by_section,
                    candidate_reported_proposition_ids={
                        section_id: {
                            *repair_patches[-1].rendered_proposition_ids,
                            *repair_patches[-1].caveated_proposition_ids,
                        }
                    },
                )
                if repair_decision == "accept":
                    working = repair_candidate
                    selected.extend(repair_patches)
                    repaired = True
                    break
                local_reasons = list(repair_reasons) or local_reasons
            if repaired:
                continue
            rejected.extend(local_reasons)
            continue
        working = candidate
        selected.extend(section_patches)
    if not selected:
        only_no_gain = bool(rejected) and all(
            str(reason).endswith(":no_local_gain") for reason in rejected
        )
        if not only_no_gain:
            return editor_result.with_updates(
                # Keep a genuinely regressing candidate visible to the
                # aggregate rejection path so claim/configuration/move loss
                # remains an explicit binding failure.
                sections=dict(editor_result.sections),
                patches=list(editor_result.patches),
                blocked_reason="",
                call_failures=tuple([*editor_result.call_failures, *rejected]),
            )
        return editor_result.with_updates(
            # Every proposed section was independently rejected.  This is a
            # valid Editor no-op, not a document-level rejection with an empty
            # reason.  Keep the exact incumbent and retain local diagnostics
            # in call_failures; the aggregate patch branch must not run.
            sections={sid: text for sid, text, _ref in incumbent},
            patches=[],
            blocked_reason="",
            call_failures=tuple([*editor_result.call_failures, *rejected]),
        )
    return editor_result.with_updates(
        sections={sid: text for sid, text, _ref in working},
        patches=selected,
        blocked_reason="",
        call_failures=tuple([*editor_result.call_failures, *rejected]),
    )


def _editor_regressed_dimensions(
    incumbent_snapshot: dict[str, Any],
    candidate_snapshot: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Per-dimension before→after snapshot for Editor document-level decisions."""

    def _count(snapshot: dict[str, Any], key: str) -> int:
        rendered = snapshot.get("rendered_by_section") or {}
        total = 0
        for section_values in rendered.values():
            values = section_values.get(key, set())
            total += len(values) if hasattr(values, "__len__") else 0
        return total

    before_after = {
        "claims": {
            "before": _count(incumbent_snapshot, "claims"),
            "after": _count(candidate_snapshot, "claims"),
        },
        "equations": {
            "before": _count(incumbent_snapshot, "equations"),
            "after": _count(candidate_snapshot, "equations"),
        },
        "configurations": {
            "before": _count(incumbent_snapshot, "configs"),
            "after": _count(candidate_snapshot, "configs"),
        },
        "moves": {
            "before": len(incumbent_snapshot.get("bound_moves") or ()),
            "after": len(candidate_snapshot.get("bound_moves") or ()),
        },
        "duplicate": {
            "before": incumbent_snapshot.get("duplicate_rate"),
            "after": candidate_snapshot.get("duplicate_rate"),
        },
        "editable": {
            "before": incumbent_snapshot.get("editable_rate"),
            "after": candidate_snapshot.get("editable_rate"),
        },
        "coherent": {
            "before": incumbent_snapshot.get("coherent"),
            "after": candidate_snapshot.get("coherent"),
        },
    }
    return before_after


def _editor_regressed_section_ids(
    incumbent_snapshot: dict[str, Any],
    candidate_snapshot: dict[str, Any],
) -> set[str]:
    """Sections that lost claims/equations/configs/propositions."""

    regressed: set[str] = set()
    incumbent_rendered = incumbent_snapshot.get("rendered_by_section") or {}
    candidate_rendered = candidate_snapshot.get("rendered_by_section") or {}
    for section_id in set(incumbent_rendered) | set(candidate_rendered):
        before = incumbent_rendered.get(section_id, {})
        after = candidate_rendered.get(section_id, {})
        for key in ("claims", "equations", "configs", "propositions"):
            lost = set(before.get(key) or ()) - set(after.get(key) or ())
            if lost:
                regressed.add(section_id)
                break
    lost_move_sections = {
        section
        for section, move in (incumbent_snapshot.get("bound_moves") or ())
        if (section, move) not in set(candidate_snapshot.get("bound_moves") or ())
    }
    return regressed | lost_move_sections


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
        "regressed_dimensions": _editor_regressed_dimensions(
            incumbent_snapshot, candidate_snapshot,
        ),
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
    accepted: list[tuple[str, str, str]] | None = None,
    plan: MethodSectionPlanV2 | None = None,
    propositions: MethodPropositionSetV1 | None = None,
    proposition_bindings: PropositionBindingSidecarV1 | None = None,
    concept_cards: Any | None = None,
    llm_config: LLMConfig | None = None,
) -> tuple[Literal["pending", "passed", "failed", "error"], dict[str, str]]:
    """Run the final reverse gate when the frozen V3 inputs are available.

    The isolated publication Writer is intentionally usable without the full
    LangGraph validation stage.  In that mode its quality report remains
    ``pending``.  A caller that supplies both the V3 packet artifact and the
    frozen MethodEvidence artifact gets the same sentence-to-evidence reverse
    validator used by the production graph, with exact claims/validation
    artifacts written beside the publication quality report.

    When ``concept_cards`` is supplied (Stage 4 concept lane), final-text
    claims are aligned to concept keys and validated through the same
    proposition-validation surface via the harness's concept->claim map.
    """

    packet_value = artifact_paths.get("evidence_packets_v3", "")
    method_value = artifact_paths.get("method_evidence") or artifact_paths.get("evidence", "")
    if not final_text or not packet_value or not method_value:
        return "pending", {}
    packet_path = Path(packet_value)
    method_path = Path(method_value)
    if not packet_path.is_file() or not method_path.is_file():
        return "pending", {}
    argument_briefs = None
    brief_value = artifact_paths.get("method_argument_briefs_v1", "")
    if brief_value and Path(brief_value).is_file():
        from code2paper.agentic.method_argument_brief_models import MethodArgumentBriefSetV1

        argument_briefs = MethodArgumentBriefSetV1.model_validate_json(
            Path(brief_value).read_text(encoding="utf-8")
        )
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
        proposition_alignment_calls: list[dict[str, Any]] = []
        if propositions is not None and plan is not None and accepted is not None:
            final_claims = _align_final_claims_to_method_propositions(
                final_claims=final_claims,
                accepted=accepted,
                plan=plan,
                propositions=propositions,
                llm_config=llm_config,
                trace_sink=proposition_alignment_calls,
            )
        elif argument_briefs is not None and plan is not None and accepted is not None:
            final_claims = _align_final_claims_to_argument_briefs(
                final_claims=final_claims,
                accepted=accepted,
                plan=plan,
                argument_briefs=argument_briefs,
                claims=claims,
                llm_config=llm_config,
                trace_sink=proposition_alignment_calls,
            )
        elif concept_cards is not None and plan is not None and accepted is not None:
            final_claims = _align_final_claims_to_concept_cards(
                final_claims=final_claims,
                accepted=accepted,
                plan=plan,
                concept_cards=concept_cards,
                llm_config=llm_config,
                trace_sink=proposition_alignment_calls,
            )
        proposition_claim_ids = {
            binding.proposition_id: binding.claim_ids
            for binding in (
                proposition_bindings.bindings if proposition_bindings is not None else ()
            )
        }
        candidate_only_proposition_ids = {
            proposition.proposition_id
            for proposition in (propositions.propositions if propositions is not None else ())
            if not proposition.may_enter_verified
        }
        evidence_entailed_proposition_ids = {
            proposition.proposition_id
            for proposition in (propositions.propositions if propositions is not None else ())
            if proposition.may_enter_verified
            and proposition.evidence_verdict == "entailed"
        }
        if concept_cards is not None:
            # Concept lane: the harness maps concept keys onto the
            # proposition-validation surface.  ``proposition_claim_ids``
            # becomes concept_key -> claims of its source obligations;
            # verified/caveated sets become concept key sets.  Final-text
            # claims carry the aligned concept keys in
            # ``candidate_method_proposition_ids``.
            facts_for_concepts = None
            facts_value = artifact_paths.get("code_facts_v1", "")
            if facts_value and Path(facts_value).is_file():
                facts_for_concepts = load_code_facts_v1(facts_value)
            concept_claim_ids = _concept_claim_ids(
                concept_cards=concept_cards,
                claims=claims,
                facts=facts_for_concepts,
            )
            if concept_claim_ids:
                proposition_claim_ids = concept_claim_ids
            candidate_only_proposition_ids = {
                card.concept_key
                for card in (concept_cards.cards if concept_cards is not None else ())
                if not card.may_enter_verified
            }
            evidence_entailed_proposition_ids = {
                card.concept_key
                for card in (concept_cards.cards if concept_cards is not None else ())
                if card.may_enter_verified
                and card.evidence_verdict == "entailed"
            }
        validation = validate_text_evidence(
            final_claims=final_claims,
            projection=projection,
            raw_evidence=raw_evidence,
            evidence_snapshot_v2=snapshot,
            evidence_packets_v3=packets,
            require_semantic_verifier=False,
            max_semantic_verifier_calls=0,
            proposition_claim_ids=proposition_claim_ids,
            candidate_only_proposition_ids=candidate_only_proposition_ids,
            evidence_entailed_proposition_ids=evidence_entailed_proposition_ids,
        )
    except (OSError, TypeError, ValueError, KeyError):
        # Supplying malformed frozen inputs is an integrity failure, not a
        # reason to silently keep a pending quality report.  It is also not a
        # candidate verdict: Q0 keeps the durable candidate and reports
        # candidate_validation_status=error instead of erasing the draft.
        return "error", {}
    claims_path = method_output(Path(out_root), "final_text_claims")
    validation_path = method_output(Path(out_root), "text_evidence_validation")
    projection_path = method_output(Path(out_root), "authoring_projection_v1")
    alignment_calls_path = method_output(
        Path(out_root), "method_proposition_alignment_calls_v1"
    )
    write_final_text_claims(claims_path, final_claims)
    write_text_evidence_validation(validation_path, validation)
    _atomic_write_text(projection_path, projection.model_dump_json(indent=2) + "\n")
    _atomic_write_text(
        alignment_calls_path,
        json.dumps({
            "schema_version": "1.0",
            "calls": proposition_alignment_calls,
        }, ensure_ascii=False, indent=2) + "\n",
    )
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
        "method_proposition_alignment_calls_v1": str(alignment_calls_path),
    }


def _safe_validate_final_text(
    *args: Any,
    **kwargs: Any,
) -> tuple[Literal["pending", "passed", "failed", "error"], dict[str, str]]:
    """Run the final reverse gate without letting a validator fault erase text.

    Q0 fail-closed rule: a validator exception is reported as
    ``candidate_validation_status=error`` with an actionable warning; the durable
    candidate checkpoint stays the publication fallback and Verified is never
    guessed from an unvalidated draft.
    """

    try:
        return _maybe_validate_final_text(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — validator faults are warnings, not erasure
        return "error", {}


def _align_final_claims_to_method_propositions(
    *,
    final_claims: FinalTextClaims,
    accepted: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    propositions: MethodPropositionSetV1,
    llm_config: LLMConfig | None,
    trace_sink: list[dict[str, Any]] | None = None,
) -> FinalTextClaims:
    """Bind final atomic prose to section-closed proposition IDs.

    This is deliberately a navigation step.  A semantic match only chooses a
    proposition; the reverse validator still expands that card through the
    sidecar and independently enforces frozen claims, evidence spans,
    qualifiers, numerics, formulae and wording strength.
    """

    proposition_by_id = {
        item.proposition_id: item for item in propositions.propositions
    }
    units = {item.argument_unit_id: item for item in plan.argument_units}
    section_propositions = {
        section.section_id: tuple(
            proposition_by_id[proposition_id]
            for unit_id in section.argument_unit_ids if unit_id in units
            for proposition_id in (
                units[unit_id].proposition_order or units[unit_id].proposition_ids
            )
            if proposition_id in proposition_by_id
        )
        for section in plan.sections
    }
    section_ranges: list[tuple[str, int, int]] = []
    cursor = 0
    for section_id, text, _response_ref in accepted:
        section_ranges.append((section_id, cursor, cursor + len(text)))
        cursor += len(text) + 2
    aligner = build_proposition_semantic_aligner(llm_config) if llm_config is not None else None
    try:
        configured_budget = int(os.environ.get(
            "CODE2PAPER_MAX_PROPOSITION_ALIGNMENT_CALLS_PER_SECTION", "8"
        ))
    except ValueError:
        configured_budget = 8
    budget = max(0, min(configured_budget, 12))
    calls_by_section: dict[str, int] = {}
    updated = []
    for claim in final_claims.atomic_claims:
        section_id = next((
            section_id for section_id, start, end in section_ranges
            if claim.char_start < end and claim.char_end > start
        ), "")
        closed = section_propositions.get(section_id, ())
        semantic_owner = (
            aligner if calls_by_section.get(section_id, 0) < budget else None
        )
        alignment = align_sentence_to_section_propositions(
            claim.text, closed, semantic_aligner=semantic_owner,
        )
        if semantic_owner is not None and alignment.rationale not in {
            "No closed section proposition was retrieved.",
            "Deterministic exact semantic-field overlap.",
            "Candidate-only proposition lacks a visible caveat.",
            "Immutable proposition constraints were not preserved.",
            "Sentence changes proposition polarity or authority strength.",
        }:
            calls_by_section[section_id] = calls_by_section.get(section_id, 0) + 1
        updated.append(claim.model_copy(update={
            "candidate_method_proposition_ids": list(
                alignment.matched_proposition_ids
                if alignment.status == "matched" else ()
            ),
        }))
    if trace_sink is not None and aligner is not None:
        trace_sink.extend(getattr(aligner, "alignment_traces", ()))
    return final_claims.model_copy(update={"atomic_claims": updated})


def _concept_semantic_surface(card: Any) -> str:
    """Reader-facing semantic surface of a concept card for claim alignment."""

    return " ".join((
        str(getattr(card, "method_subject", "") or ""),
        str(getattr(card, "operation", "") or ""),
        *[str(item) for item in getattr(card, "inputs", ()) or ()],
        *[str(item) for item in getattr(card, "outputs", ()) or ()],
        *[str(item) for item in getattr(card, "conditions", ()) or ()],
    ))


def _concept_callback_prototype_payload(
    *,
    section_concepts: list[Any],
    concept_bindings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stage 5: concept-bearing payload for a writer callback prototype.

    A callback for an open move should name the caveated concept card it
    targets, the parts of that card that are still missing, and the
    evidence refs the card already binds — the Research Manager needs the
    semantic gap, not a rhetorical-move label.  Only caveated concepts
    with missing parts or a required caveat are eligible; verified cards
    never produce a callback.  The evidence refs come from the card's
    binding sidecar ``source_span_ids`` when available (falling back to the
    card's ``evidence_fragment_refs``), so fulfillment knows exactly which
    spans are already bound.  No evidence authority is created here.
    """

    concept_bindings = concept_bindings or {}
    eligible = [
        card for card in section_concepts
        if not getattr(card, "may_enter_verified", False)
        and (
            getattr(card, "missing_parts", ()) or ()
            or getattr(card, "requires_caveat", False)
        )
    ]
    if not eligible:
        return {}
    missing_parts = [
        str(item)
        for card in eligible
        for item in (getattr(card, "missing_parts", ()) or ())
        if str(item).strip()
    ]
    search_terms = directed_search_terms_from_texts(
        *missing_parts,
        *[str(getattr(card, "method_subject", "") or "") for card in eligible],
        *[str(part) for card in eligible for part in (getattr(card, "known_parts", ()) or ())],
    )
    return {
        "concept_binding": [
            {
                "concept_key": str(card.concept_key),
                "method_subject": str(getattr(card, "method_subject", "") or ""),
                "missing_parts": list(getattr(card, "missing_parts", ()) or ()),
                "evidence_refs_used": list(dict.fromkeys([
                    *(
                        str(item)
                        for item in (
                            getattr(concept_bindings.get(card.concept_key), "source_span_ids", ())
                            or ()
                        )
                        if str(item).strip()
                    ),
                    *(
                        str(item)
                        for item in (
                            getattr(card, "evidence_fragment_refs", ()) or ()
                        )
                        if str(item).strip()
                    ),
                ])),
                "known_parts": list(getattr(card, "known_parts", ()) or ()),
                "candidate_caveat": str(getattr(card, "candidate_caveat", "") or ""),
            }
            for card in eligible
        ],
        "why_needed_for_reader": (
            "Directed repository search for missing parts of a caveated "
            "concept. Keep writing the full author-logic Candidate as author "
            "specification in parallel; do not omit the mechanism while this "
            "callback is open."
        ),
        "exact_question": (
            directed_callback_question(search_terms)
            or (
                "Which repository spans, symbols, or functions implement the "
                "missing parts of the caveated concept(s) listed in "
                "concept_binding?"
            )
        ),
        "candidate_symbols_or_terms": list(search_terms),
    }


def _brief_callback_prototype_payload(
    *,
    section_briefs: list[Any],
) -> dict[str, Any]:
    """Stage 5 brief-bearing payload for a writer callback prototype.

    Callbacks on the brief mainline target unlicensed author clauses and/or
    empty mechanism drafts instead of concept cards.  Evidence refs come from
    the brief's closed span and claim ids so fulfillment can resolve a
    digest-bound baseline without concept-card bindings.
    """

    eligible = [
        brief for brief in section_briefs
        if not getattr(brief, "may_enter_verified", False)
        and (
            getattr(brief, "requires_caveat", False)
            or getattr(getattr(brief, "mechanism_draft", None), "status", "") == "empty"
        )
    ]
    if not eligible:
        return {}
    bindings: list[dict[str, Any]] = []
    target_brief_ids: list[str] = []
    target_clause_ids: list[str] = []
    missing_parts: list[str] = []
    evidence_refs: list[str] = []
    for brief in eligible:
        unlicensed = [
            clause for clause in (getattr(brief, "clauses", ()) or ())
            if getattr(clause, "license", "") in {"unlicensed", "partially_licensed"}
        ]
        draft = getattr(brief, "mechanism_draft", None)
        draft_empty = str(getattr(draft, "status", "") or "") == "empty"
        if not unlicensed and not draft_empty:
            continue
        refs = list(dict.fromkeys([
            *(
                str(span).strip()
                if str(span).startswith("span:")
                else f"span:{span}"
                for span in (getattr(brief, "span_ids", ()) or ())
                if str(span).strip()
            ),
            *(
                f"claim:{claim_id}"
                for claim_id in (getattr(brief, "claim_ids", ()) or ())
                if str(claim_id).strip()
            ),
        ]))
        bindings.append({
            "brief_id": str(brief.brief_id),
            "unlicensed_clauses": [
                {
                    "clause_id": str(clause.clause_id),
                    "text": str(clause.text),
                    "license": str(clause.license),
                }
                for clause in unlicensed
            ],
            "mechanism_draft_status": str(getattr(draft, "status", "") or ""),
            "missing_parts": list(dict.fromkeys(
                [str(clause.text) for clause in unlicensed if str(clause.text).strip()]
                + (["empty mechanism draft"] if draft_empty else [])
            )),
            "evidence_refs_used": refs,
        })
        target_brief_ids.append(str(brief.brief_id))
        target_clause_ids.extend(str(clause.clause_id) for clause in unlicensed)
        missing_parts.extend(
            str(clause.text) for clause in unlicensed if str(clause.text).strip()
        )
        if draft_empty:
            missing_parts.append("empty mechanism draft")
        evidence_refs.extend(refs)
    if not bindings:
        return {}
    search_terms = directed_search_terms_from_texts(*missing_parts)
    return {
        "brief_binding": bindings,
        "target_brief_ids": list(dict.fromkeys(target_brief_ids)),
        "target_clause_ids": list(dict.fromkeys(target_clause_ids)),
        "missing_parts": list(dict.fromkeys(missing_parts)),
        "evidence_refs_used": list(dict.fromkeys(evidence_refs)),
        "candidate_symbols_or_terms": list(search_terms),
        "why_needed_for_reader": (
            "Directed repository search for unlicensed author-mechanism "
            "fields. Keep writing the full author-logic Candidate as author "
            "specification in parallel; do not omit the mechanism while this "
            "callback is open."
        ),
        "exact_question": (
            directed_callback_question(search_terms)
            or (
                "Which repository spans, symbols, or functions implement the "
                "unlicensed clause(s) listed in brief_binding?"
            )
        ),
    }


def _align_final_claims_to_argument_briefs(
    *,
    final_claims: FinalTextClaims,
    accepted: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    argument_briefs: Any,
    claims: AtomicClaimSetV3,
    llm_config: LLMConfig | None,
    trace_sink: list[dict[str, Any]] | None = None,
) -> FinalTextClaims:
    """Bind final prose claims to section-closed brief claim ids only."""

    _ = llm_config, trace_sink
    brief_by_id = {
        brief.brief_id: brief
        for brief in (getattr(argument_briefs, "briefs", ()) or ())
    }
    units = {item.argument_unit_id: item for item in plan.argument_units}
    claim_by_id = {item.claim_id: item for item in claims.claims}
    section_closed_claim_ids: dict[str, tuple[str, ...]] = {}
    for section in plan.sections:
        closed: list[str] = []
        for unit_id in section.argument_unit_ids:
            unit = units.get(unit_id)
            if unit is None:
                continue
            for brief_id in unit.brief_order or unit.brief_ids:
                brief = brief_by_id.get(brief_id)
                if brief is None:
                    continue
                for clause in brief.clauses:
                    if clause.license == "positively_licensed":
                        closed.extend(clause.bound_claim_ids)
                closed.extend(brief.mechanism_draft.cited_claim_ids)
        section_closed_claim_ids[section.section_id] = tuple(dict.fromkeys(closed))

    section_ranges: list[tuple[str, int, int]] = []
    cursor = 0
    for section_id, text, _response_ref in accepted:
        section_ranges.append((section_id, cursor, cursor + len(text)))
        cursor += len(text) + 2

    def _token_set(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", value.casefold().replace("_", " "))
            if len(token) > 1
        }

    updated = []
    for claim in final_claims.atomic_claims:
        section_id = next((
            sid for sid, start, end in section_ranges
            if claim.char_start < end and claim.char_end > start
        ), "")
        closed_ids = section_closed_claim_ids.get(section_id, ())
        if not closed_ids:
            updated.append(claim)
            continue
        claim_tokens = _token_set(claim.text)
        scored = [
            (
                len(claim_tokens & _token_set(claim_by_id[claim_id].canonical_text)),
                claim_id,
            )
            for claim_id in closed_ids
            if claim_id in claim_by_id
        ]
        best_score, best_id = max(scored, default=(0, ""))
        matched = (best_id,) if best_score > 0 and best_id else ()
        updated.append(claim.model_copy(update={
            "candidate_method_proposition_ids": list(matched),
        }))
    return final_claims.model_copy(update={"atomic_claims": updated})


def _align_final_claims_to_concept_cards(
    *,
    final_claims: FinalTextClaims,
    accepted: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    concept_cards: Any,
    llm_config: LLMConfig | None,
    trace_sink: list[dict[str, Any]] | None = None,
) -> FinalTextClaims:
    """Bind final atomic prose to section-closed concept keys.

    Deterministic navigation step (Stage 4): each final-text claim is
    matched against the concept cards of its section by token overlap of
    the card's reader-facing surface.  The matched concept keys land in
    ``candidate_method_proposition_ids`` so the reverse validator can
    separate verified from caveated concepts exactly as it does for
    propositions.  No new evidence authority is created here.
    """

    cards_by_key = {
        item.concept_key: item for item in (concept_cards.cards or ())
    }
    units = {item.argument_unit_id: item for item in plan.argument_units}
    section_concept_keys = {
        section.section_id: tuple(
            cards_by_key[concept_key].concept_key
            for unit_id in section.argument_unit_ids if unit_id in units
            for concept_key in (
                units[unit_id].concept_card_order or units[unit_id].concept_card_ids
            )
            if concept_key in cards_by_key
        )
        for section in plan.sections
    }
    section_ranges: list[tuple[str, int, int]] = []
    cursor = 0
    for section_id, text, _response_ref in accepted:
        section_ranges.append((section_id, cursor, cursor + len(text)))
        cursor += len(text) + 2

    def _token_set(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", value.casefold().replace("_", " "))
            if len(token) > 1
        }

    updated = []
    for claim in final_claims.atomic_claims:
        section_id = next((
            section_id for section_id, start, end in section_ranges
            if claim.char_start < end and claim.char_end > start
        ), "")
        closed_keys = section_concept_keys.get(section_id, ())
        if not closed_keys:
            updated.append(claim)
            continue
        claim_tokens = _token_set(claim.text)
        scored = [
            (len(claim_tokens & _token_set(_concept_semantic_surface(cards_by_key[key]))),
             -index, key)
            for index, key in enumerate(closed_keys)
        ]
        best_score, _neg_index, best_key = max(scored, default=(0, 0, ""))
        matched = (best_key,) if best_score > 0 else ()
        # Fail-closed epistemic binding: a sentence that carries
        # author-intent / unverified / pending markers must bind a caveated
        # concept (when one matches at all), never a verified one.  A
        # verified concept's repository behavior cannot license author
        # intent language.
        if matched:
            epistemic = _claim_has_epistemic_markers(claim.text)
            if epistemic:
                caveated_matches = [
                    (score, key)
                    for score, _neg, key in scored
                    if not getattr(
                        cards_by_key[key], "may_enter_verified", False
                    )
                    and score > 0
                ]
                if caveated_matches:
                    _alt_score, _alt_key = max(caveated_matches)
                    matched = (_alt_key,)
                else:
                    matched = ()
        updated.append(claim.model_copy(update={
            "candidate_method_proposition_ids": list(matched),
        }))
    return final_claims.model_copy(update={"atomic_claims": updated})


_EPISTEMIC_MARKERS = (
    "author-intended", "author intended", "author-attested", "author attested",
    "unverified", "not verified", "pending confirmation", "pending",
    "our intended", "we aim", "remains intended", "intended design",
    "requires confirmation", "exact standardization formula",
    "predictor interface specification",
)


def _claim_has_epistemic_markers(text: str) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in _EPISTEMIC_MARKERS)


def _concept_claim_ids(
    *,
    concept_cards: Any,
    claims: AtomicClaimSetV3,
    facts: Any | None = None,
) -> dict[str, tuple[str, ...]]:
    """Map verified concept keys to claims through exact span-bound facts only.

    Obligation-wide expansion is forbidden (WP2): a concept authorizes only
    the claims whose facts overlap the concept binding's exact spans.
    """

    from code2paper.agentic.publication_relevance import (
        concept_bound_claim_ids,
        concept_bound_fact_ids,
    )

    result: dict[str, tuple[str, ...]] = {}
    for card in (concept_cards.cards or ()):
        if not getattr(card, "may_enter_verified", False):
            continue
        concept_key = str(card.concept_key or "")
        if not concept_key:
            continue
        claim_ids = concept_bound_claim_ids(
            concept_cards,
            [concept_key],
            claims,
            facts,
        )
        if claim_ids:
            result[concept_key] = tuple(sorted(claim_ids))
    return result


def _concept_fact_ids(
    *,
    concept_cards: Any,
    concept_keys: Iterable[str],
    facts: Any | None,
) -> dict[str, tuple[str, ...]]:
    from code2paper.agentic.publication_relevance import concept_bound_fact_ids

    result: dict[str, tuple[str, ...]] = {}
    for concept_key in concept_keys:
        key = str(concept_key or "")
        if not key:
            continue
        bound = concept_bound_fact_ids(concept_cards, [key], facts)
        if bound:
            result[key] = tuple(sorted(bound))
    return result


def _build_section_content_witness_set(
    *,
    final_claims: Any,
    ledger: Any,
    concept_cards: Any,
    claims: AtomicClaimSetV3,
    facts: Any | None,
) -> Any:
    """Build sentence-scoped content witnesses from final-text claim alignment."""

    from code2paper.agentic.method_argument_models import (
        SectionContentWitnessSetV1,
        SectionSentenceContentWitnessV1,
    )

    witnesses: list[SectionSentenceContentWitnessV1] = []
    for claim in getattr(final_claims, "atomic_claims", ()) or ():
        concept_keys = tuple(
            str(key)
            for key in (getattr(claim, "candidate_method_proposition_ids", ()) or ())
            if str(key).strip()
        )
        if not concept_keys:
            continue
        section_id = ""
        start = int(getattr(claim, "char_start", 0) or 0)
        end = int(getattr(claim, "char_end", 0) or 0)
        for span in getattr(ledger, "spans", ()) or ():
            if start < int(span.final_end) and end > int(span.final_start):
                section_id = str(getattr(span, "section_id", "") or "")
                break
        if not section_id:
            continue
        primary_key = concept_keys[0]
        exact_claim_ids = tuple(sorted({
            claim_id
            for key in concept_keys
            for claim_id in _concept_claim_ids(
                concept_cards=concept_cards,
                claims=claims,
                facts=facts,
            ).get(key, ())
        }))
        exact_fact_ids = tuple(sorted({
            fact_id
            for key in concept_keys
            for fact_id in _concept_fact_ids(
                concept_cards=concept_cards,
                concept_keys=[key],
                facts=facts,
            ).get(key, ())
        }))
        witnesses.append(SectionSentenceContentWitnessV1(
            section_id=section_id,
            char_start=start,
            char_end=end,
            sentence_text=str(getattr(claim, "text", "") or ""),
            concept_key=primary_key,
            exact_claim_ids=exact_claim_ids,
            exact_fact_ids=exact_fact_ids,
            authority_lane="executable_hard" if exact_claim_ids else "author_intent",
            reverse_validation_status="pending",
        ))
    return SectionContentWitnessSetV1(witnesses=tuple(witnesses))


def _sentence_validated_concept_claim_ids(
    *,
    validation_paths: Mapping[str, str],
    concept_cards: Any | None,
    claims: AtomicClaimSetV3,
    ledger: Any,
    facts: Any | None = None,
    exclude_concept_keys: frozenset[str] = frozenset(),
) -> dict[str, tuple[str, ...]]:
    """Expand the reverse validator's supported verdicts into claim IDs,
    bound to the exact section that rendered each supported sentence.

    In the concept-card lane there is no proposition sidecar, so the final
    quality evaluation would otherwise see only the Writer's (possibly
    empty) ``used_claim_ids`` and report every supported unit as
    ``planned_but_not_rendered``.  The persisted sentence validation is the
    binding authority: each ``status=supported`` verdict carries the
    concept keys its sentence aligned to, and ``_concept_claim_ids`` maps
    verified concept keys back to their frozen repository claim IDs.

    Section binding is derived from the persisted final-text claim identity:
    the verdict's ``atomic_claim_id`` resolves to its char range in the
    final claims snapshot, and the authorship ledger maps that range to
    exactly one authored section.  A verdict whose atomic claim identity is
    missing, unknown, or not mappable to a section authorizes NO coverage
    (fail closed).  Caveated/unsupported verdicts never authorize
    repository support.
    """

    result: dict[str, list[str]] = {}
    if concept_cards is None:
        return {}
    report_path = validation_paths.get("text_evidence_validation", "")
    claims_snapshot_path = validation_paths.get("final_text_claims", "")
    if not report_path or not Path(report_path).is_file():
        return {}
    if not claims_snapshot_path or not Path(claims_snapshot_path).is_file():
        # Without the final-text claim identity no sentence can be bound to
        # a section; flat document-level claims would create exactly the
        # cross-section false coverage the section-scoped contract forbids.
        return {}
    try:
        report = load_text_evidence_validation(report_path)
        claims_snapshot = load_final_text_claims(claims_snapshot_path)
    except (OSError, TypeError, ValueError):
        return {}
    claim_range_by_id = {
        str(item.atomic_claim_id): (int(item.char_start), int(item.char_end))
        for item in claims_snapshot.atomic_claims
        if item.atomic_claim_id
    }
    concept_claim_ids = _concept_claim_ids(
        concept_cards=concept_cards, claims=claims, facts=facts,
    )
    for verdict in report.verdicts:
        if verdict.status != "supported":
            continue
        range_for_claim = claim_range_by_id.get(str(verdict.atomic_claim_id))
        if range_for_claim is None:
            continue
        start, end = range_for_claim
        section_id = ""
        for span in getattr(ledger, "spans", ()):
            if start < int(span.final_end) and end > int(span.final_start):
                candidate = str(getattr(span, "section_id", "") or "")
                if candidate and section_id and candidate != section_id:
                    section_id = ""
                    break
                if candidate:
                    section_id = candidate
        if not section_id:
            # No unique section owns the supported sentence: no coverage.
            continue
        for concept_key in verdict.matched_method_proposition_ids:
            if str(concept_key) in exclude_concept_keys:
                continue  # R1: audit-only cards never authorize coverage
            for claim_id in concept_claim_ids.get(str(concept_key), ()):
                if claim_id not in result.setdefault(section_id, []):
                    result[section_id].append(claim_id)
    return {
        section_id: tuple(claim_ids)
        for section_id, claim_ids in result.items()
        if claim_ids
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
    *,
    exempt_qualifier_terms: Mapping[str, tuple[str, ...]] | None = None,
) -> dict[str, list[TextRepairIssueV1]]:
    """Translate the shared Method-language detector into Rewrite issues.

    ``exempt_qualifier_terms`` carries each section's exact required
    qualifier conditions (digest-bound): the reverse validator demands those
    exact predicates, so they are not code narration and must not be flagged
    as a style regression.
    """

    issues: dict[str, list[TextRepairIssueV1]] = {}
    for section_id, section_text in find_code_trace_prose_sections(
        list(output_by_section.values()),
        exempt_qualifier_terms=exempt_qualifier_terms,
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
    for section_id, output in output_by_section.items():
        text = str(output.section_markdown or "")
        lines = [line for line in text.splitlines() if line.strip()]
        heading_text = ""
        body = text
        if lines and lines[0].lstrip().startswith("#"):
            heading_text = lines[0].lstrip("# ").strip()
            body = "\n".join(text.splitlines()[1:])
        plan_heading = str(getattr(output, "heading", "") or heading_text)
        leaked = heading_tail_leaked_into_body(
            plan_heading=plan_heading,
            rendered_heading=heading_text,
            body=body,
        )
        if leaked:
            issues.setdefault(section_id, []).append(TextRepairIssueV1(
                sentence_id=f"structure:{section_id}:heading-tail-leaked",
                failure_type="heading_tail_leaked_into_body",
                offending_fragment=leaked[:200],
                missing_fact_or_relation=(
                    "The unused suffix of the planned heading leaked into the "
                    "first body sentence. Discard that dangling tail or rewrite "
                    "it as a complete Method sentence; do not leave a heading "
                    "fragment at the start of the body."
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


_READER_FACING_INTERNAL_ID_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Case-study / knowledge-chunk ids (e.g. ``CK-9c5360a570a6c8c7``).
    re.compile(r"\bCK-[A-Za-z0-9_-]+"),
    # Evidence/fact/claim/obligation/packet ids.
    re.compile(r"\bfact-[A-Za-z0-9:_-]+"),
    re.compile(r"\bclaim-[A-Za-z0-9:_-]+"),
    re.compile(r"\bobligation-[A-Za-z0-9:_-]+"),
    re.compile(r"\bpacket-[A-Za-z0-9:_-]+"),
    # Typed repository refs that must never appear in reader prose.
    re.compile(r"\bnode:[0-9a-f]{6,}"),
    re.compile(r"\bspan:[^\s]+"),
    re.compile(r"\bsym:[0-9a-f]{6,}"),
    re.compile(r"\brel:[0-9a-f]{6,}"),
    # Markdown heading auto-identifiers such as ``{#MA-S3:purpose}``: the
    # model must never leak section ids into reader headings.
    re.compile(r"\{#[A-Za-z0-9_:.-]+\}"),
    # Repair/protocol vocabulary leaking from the harness into prose.
    re.compile(r"\ballowed_repair_scope\b"),
    re.compile(r"\bmissing_fact_or_relation\b"),
    re.compile(r"\bdeterministic_failures\b"),
    re.compile(r"\batomic_claim_id\b"),
    re.compile(r"\bsentence_id\b"),
    re.compile(r"\brepair_action\b"),
    re.compile(r"\bmay_enter_verified\b"),
    re.compile(r"\bcandidate_only_proposition\b"),
)


def _reader_facing_leakage_issues_by_section(
    output_by_section: Mapping[str, PublicationMethodSectionOutputV1],
) -> dict[str, list[TextRepairIssueV1]]:
    """Find harness-internal ids/protocol vocabulary in reader prose.

    A hit creates an exact Rewrite issue; it is never repaired by regex
    deletion here.  The Rewrite owner rewrites the sentence so the reader
    content survives without the internal id.
    """

    issues: dict[str, list[TextRepairIssueV1]] = {}
    for section_id, output in output_by_section.items():
        text = str(output.section_markdown or "")
        if not text:
            continue
        # When the leaked token sits inside the heading line, the only
        # reader-safe repair is to restore the exact planned heading (the
        # rewrite readability gate accepts the planned heading line).
        first_line = text.lstrip().splitlines()[:1]
        heading_text = first_line[0] if first_line else ""
        for pattern in _READER_FACING_INTERNAL_ID_PATTERNS:
            for index, match in enumerate(pattern.finditer(text)):
                in_heading = heading_text and match.start() < len(heading_text)
                hint = (
                    "This internal id/protocol token must not appear in reader-facing "
                    "Method prose. Rewrite the sentence so the supported repository "
                    "content is expressed in natural Method language; never keep the "
                    "raw id and never invent evidence to replace it."
                )
                if in_heading:
                    hint = (
                        "This internal id/protocol token is inside the section heading "
                        "line. Restore the exact planned heading (section_context."
                        "writer_heading) for this section; do not keep any part of the "
                        "leaked id and do not invent a new heading."
                    )
                issues.setdefault(section_id, []).append(TextRepairIssueV1(
                    sentence_id=(
                        f"leakage:{section_id}:{pattern.pattern[:40]}:{index}"
                    ),
                    failure_type="reader_facing_internal_id",
                    offending_fragment=match.group(0),
                    missing_fact_or_relation=hint,
                    allowed_repair_scope="wording_only",
                    attempt=1,
                ))
    return issues


def _section_structure_issues_by_section(
    output_by_section: Mapping[str, PublicationMethodSectionOutputV1],
    *,
    writer_inputs: Mapping[str, WriterSectionInput],
) -> dict[str, list[TextRepairIssueV1]]:
    """Enforce exactly one Architect heading + blank line + non-empty body.

    Deterministic normalization is allowed only when it inserts missing
    whitespace around an exact, unchanged expected heading (handled by
    ``_normalize_section_heading_breaks``).  A fused lexical suffix such as
    ``...initialization)Local`` is routed to the authorized text owner
    because silently removing the suffix could change content.
    """

    issues: dict[str, list[TextRepairIssueV1]] = {}
    for section_id, output in output_by_section.items():
        writer_input = writer_inputs.get(section_id)
        if writer_input is None:
            continue
        text = str(output.section_markdown or "")
        expected_heading = " ".join(writer_input.heading.split()).strip()
        lines = text.splitlines()
        nonempty = [line for line in lines if line.strip()]
        if not nonempty:
            issues.setdefault(section_id, []).append(TextRepairIssueV1(
                sentence_id=f"structure:{section_id}:empty",
                failure_type="section_structure",
                offending_fragment=text,
                missing_fact_or_relation=(
                    "The section body is empty. Write the full section starting with "
                    f"exactly '## {expected_heading}', then a blank line, then the body."
                ),
                allowed_repair_scope="wording_only",
                attempt=1,
            ))
            continue
        first = nonempty[0]
        if not first.startswith("#"):
            issues.setdefault(section_id, []).append(TextRepairIssueV1(
                sentence_id=f"structure:{section_id}:missing-heading",
                failure_type="section_structure",
                offending_fragment=first[:160],
                missing_fact_or_relation=(
                    "The section must start with exactly one heading line "
                    f"'## {expected_heading}' followed by a blank line and the body."
                ),
                allowed_repair_scope="wording_only",
                attempt=1,
            ))
        else:
            heading_text = first.lstrip("# ").strip()
            normalized_heading = " ".join(heading_text.split()).casefold()
            expected_norm = expected_heading.casefold()
            expected_truncated = heading_is_truncated(expected_heading)
            if expected_truncated:
                # The Architect's plan heading itself stopped mid-clause.  The
                # Writer/Rewrite is the authorized owner to complete or shorten
                # the broken clause: a coherent replacement heading is valid,
                # a still-truncated heading is an exact repair issue, and a
                # fused lexical suffix still routes to the owner (silently
                # removing it could change content).  The fused check runs
                # first: ``...initialization)Local`` is the plan heading plus
                # a suffix, not a truncated heading by itself.
                if normalized_heading.startswith(expected_norm):
                    suffix = heading_text[len(expected_heading):].strip()
                    if suffix:
                        issues.setdefault(section_id, []).append(TextRepairIssueV1(
                            sentence_id=f"structure:{section_id}:fused-heading-suffix",
                            failure_type="section_structure",
                            offending_fragment=first[:200],
                            missing_fact_or_relation=(
                                f"The heading line fuses the planned heading with "
                                f"extra text ({suffix!r}). Rewrite the section so the "
                                "first line is exactly one coherent '## ' heading, then "
                                "a blank line, then the body. Do not delete content; "
                                "move the suffix into the body if it is reader meaning."
                            ),
                            allowed_repair_scope="wording_only",
                            attempt=1,
                        ))
                    elif not heading_replacement_is_coherent(
                        heading_text,
                        planned_heading=expected_heading,
                    ):
                        tail = dangling_heading_tail(heading_text)
                        issues.setdefault(section_id, []).append(TextRepairIssueV1(
                            sentence_id=f"structure:{section_id}:truncated-heading",
                            failure_type="section_structure",
                            offending_fragment=first[:200],
                            missing_fact_or_relation=(
                                "The planned heading is truncated mid-clause "
                                f"({expected_heading!r}). Complete or shorten it into one "
                                "coherent H2 heading line: keep '## ', end at a complete "
                                "clause, do not add internal ids or new factual content, "
                                "and keep the section body unchanged."
                                + (
                                    f" The dangling tail to complete or drop is "
                                    f"{tail!r}: replace exactly that tail span in the "
                                    "heading line (or remove it) and keep the rest of "
                                    "the heading unchanged."
                                    if tail else ""
                                )
                            ),
                            allowed_repair_scope="wording_only",
                            attempt=1,
                        ))
                elif not heading_replacement_is_coherent(
                    heading_text,
                    planned_heading=expected_heading,
                ):
                    tail = dangling_heading_tail(heading_text)
                    issues.setdefault(section_id, []).append(TextRepairIssueV1(
                        sentence_id=f"structure:{section_id}:truncated-heading",
                        failure_type="section_structure",
                        offending_fragment=first[:200],
                        missing_fact_or_relation=(
                            "The planned heading is truncated mid-clause "
                            f"({expected_heading!r}). Complete or shorten it into one "
                            "coherent H2 heading line: keep '## ', end at a complete "
                            "clause, use at least two content words, do not add "
                            "internal ids or new factual content, and keep the "
                            "section body unchanged."
                            + (
                                f" The dangling tail to complete or drop is "
                                f"{tail!r}: replace exactly that tail span in the "
                                "heading line (or remove it) and keep the rest of "
                                "the heading unchanged."
                                if tail else ""
                            )
                        ),
                        allowed_repair_scope="wording_only",
                        attempt=1,
                    ))
            elif normalized_heading != expected_norm:
                # Fused lexical suffix (e.g. ``...initialization)Local``) or a
                # wrong heading: route to Rewrite, never strip silently.
                if normalized_heading.startswith(expected_norm):
                    suffix = heading_text[len(expected_heading):].strip()
                    if suffix:
                        issues.setdefault(section_id, []).append(TextRepairIssueV1(
                            sentence_id=f"structure:{section_id}:fused-heading-suffix",
                            failure_type="section_structure",
                            offending_fragment=first[:200],
                            missing_fact_or_relation=(
                                f"The heading line fuses the exact expected heading with "
                                f"extra text ({suffix!r}). Rewrite the section so the "
                                f"first line is exactly '## {expected_heading}', then a "
                                "blank line, then the body. Do not delete content; move "
                                "the suffix into the body if it is reader meaning."
                            ),
                            allowed_repair_scope="wording_only",
                            attempt=1,
                        ))
                else:
                    issues.setdefault(section_id, []).append(TextRepairIssueV1(
                        sentence_id=f"structure:{section_id}:wrong-heading",
                        failure_type="section_structure",
                        offending_fragment=first[:200],
                        missing_fact_or_relation=(
                            f"The heading must be exactly '## {expected_heading}'."
                        ),
                        allowed_repair_scope="wording_only",
                        attempt=1,
                    ))
            leaked_tail = heading_tail_leaked_into_body(
                plan_heading=expected_heading,
                rendered_heading=heading_text,
                body="\n".join(lines[1:]),
            )
            if leaked_tail:
                issues.setdefault(section_id, []).append(TextRepairIssueV1(
                    sentence_id=f"structure:{section_id}:heading-tail-leaked",
                    failure_type="heading_tail_leaked_into_body",
                    offending_fragment=leaked_tail[:200],
                    missing_fact_or_relation=(
                        "The unused suffix of the planned heading leaked into "
                        "the first body sentence. Discard that dangling tail "
                        "or rewrite it as a complete Method sentence; do not "
                        "leave a heading fragment at the start of the body."
                    ),
                    allowed_repair_scope="wording_only",
                    attempt=1,
                ))
            # Duplicate H2 headings inside one section body.
            body_lines = lines[1:]
            duplicate_h2 = [
                line.strip()
                for line in body_lines
                if line.lstrip().startswith("## ")
            ]
            if duplicate_h2:
                issues.setdefault(section_id, []).append(TextRepairIssueV1(
                    sentence_id=f"structure:{section_id}:duplicate-heading",
                    failure_type="section_structure",
                    offending_fragment=duplicate_h2[0][:160],
                    missing_fact_or_relation=(
                        "Exactly one H2 heading is allowed per section. Fold duplicate "
                        "headings into the single Architect heading or move their "
                        "content under it."
                    ),
                    allowed_repair_scope="wording_only",
                    attempt=1,
                ))
        # Heading must be followed by a blank line and a non-empty body.
        if len(nonempty) == 1 and first.startswith("#"):
            issues.setdefault(section_id, []).append(TextRepairIssueV1(
                sentence_id=f"structure:{section_id}:heading-only",
                failure_type="section_structure",
                offending_fragment=text,
                missing_fact_or_relation=(
                    "The section is headings-only. Add a non-empty body after the "
                    f"'## {expected_heading}' heading."
                ),
                allowed_repair_scope="wording_only",
                attempt=1,
            ))
    return issues


_DANGLING_BODY_TAIL_TOKENS = frozenset({
    "and", "or", "but", "with", "to", "the", "that", "for", "of", "by",
    "at", "from", "into", "onto", "upon", "while", "when", "if", "then",
    "also", "not", "as", "than", "so", "yet", "nor",
})

#: Short tokens that are legitimate sentence endings ("... it", "... to",
#: "..." by itself).  Any other 1-2 letter trailing token with no terminal
#: punctuation is a mid-word generation cut (e.g. the EBCAR ``... , un``
#: fragment) and must be repaired by the authorized text owner.
_COMMON_SHORT_BODY_ENDINGS = frozenset({
    "a", "i", "it", "to", "be", "at", "in", "of", "or", "is", "on", "as",
    "an", "we", "us", "by", "so", "no", "do", "go", "up", "if", "me", "my",
    "he", "ok", "re", "id", "vs", "et", "al",
})


def _malformed_punctuation_issues_by_section(
    output_by_section: Mapping[str, PublicationMethodSectionOutputV1],
) -> dict[str, list[TextRepairIssueV1]]:
    """Route mechanically malformed punctuation/transitions to Rewrite.

    Dangling fragments such as ``steps. , and result return operations``,
    trailing ellipses, a body ending in a dangling conjunction, unbalanced
    body parentheses, and fused heading-tail fragments separated by doubled
    whitespace are not representation damage: repairing them requires
    choosing reader-facing wording, so the authorized text owner (Rewrite)
    owns the fix.  Inline code spans (``(`...`)`` parenthetical bindings)
    are excluded before the scan.
    """

    issues: dict[str, list[TextRepairIssueV1]] = {}
    for section_id, output in output_by_section.items():
        text = str(output.section_markdown or "")
        if not text.strip():
            continue
        body = re.sub(r"\([^()\n]*`[^`\n]+`[^()\n]*\)", "", text)
        body = re.sub(r"`[^`\n]+`", "", body)
        hits: list[tuple[str, str]] = []
        # Sentence terminator immediately followed by a comma (``. , and``).
        for match in re.finditer(r"[.!?]\s*,", body):
            start = max(0, match.start() - 60)
            hits.append((
                "sentence-terminator-comma",
                body[start:match.end() + 60].replace("\n", " ").strip(),
            ))
        # Trailing ellipsis runs inside prose.
        for match in re.finditer(r"\.{3,}", body):
            start = max(0, match.start() - 60)
            hits.append((
                "ellipsis-in-prose",
                body[start:match.end() + 60].replace("\n", " ").strip(),
            ))
        # Consecutive commas.
        for match in re.finditer(r",{2,}", body):
            start = max(0, match.start() - 60)
            hits.append((
                "consecutive-commas",
                body[start:match.end() + 60].replace("\n", " ").strip(),
            ))
        # Body ends with a dangling conjunction ("... and" with nothing
        # after it) — a truncated clause fragment, not a sentence end.
        body_words = re.findall(r"[A-Za-z][A-Za-z0-9'-]*", body)
        if body_words and body_words[-1].casefold() in _DANGLING_BODY_TAIL_TOKENS:
            tail = " ".join(body_words[-3:])
            start = max(0, body.rfind(tail))
            hits.append((
                "body-ends-with-dangling-conjunction",
                body[start:].replace("\n", " ").strip()[-160:],
            ))
        # Body ends in a bare mid-word fragment ("... dot-product
        # similarities, un") — a truncated generation, not a sentence end.
        if (
            body_words
            and len(body_words[-1]) <= 2
            and body_words[-1].casefold() not in _COMMON_SHORT_BODY_ENDINGS
            and not re.search(r"[.!?]\s*$", body)
        ):
            tail = " ".join(body_words[-3:])
            start = max(0, body.rfind(tail))
            hits.append((
                "body-ends-with-bare-fragment",
                body[start:].replace("\n", " ").strip()[-160:],
            ))
        # Unbalanced parentheses in the body (for example an unclosed
        # ``(Intended:`` fragment).  Balanced parentheticals are untouched.
        if body.count("(") != body.count(")"):
            unbalanced = body[max(0, body.rfind("(")):]
            hits.append((
                "body-unbalanced-parenthesis",
                unbalanced.replace("\n", " ").strip()[-160:],
            ))
        # Fused heading-tail fragments separated by doubled whitespace
        # inside one line ("contain/message adjacency  offline tri-graph
        # construction") are not sentence spacing.
        for match in re.finditer(r"(?<!\n)\S {2,}\S(?!\n)", body):
            start = max(0, match.start() - 60)
            hits.append((
                "body-doubled-whitespace",
                body[start:match.end() + 60].replace("\n", " ").strip(),
            ))
        if not hits:
            continue
        for index, (code, fragment) in enumerate(dict.fromkeys(hits)):
            issues.setdefault(section_id, []).append(TextRepairIssueV1(
                sentence_id=f"style:{section_id}:{code}-{index}",
                failure_type="method_language_style",
                offending_fragment=fragment,
                missing_fact_or_relation=(
                    "Repair the malformed punctuation/transition into one coherent "
                    "reader-facing sentence. Remove the dangling comma after sentence "
                    "terminators, the trailing ellipsis, the consecutive commas, the "
                    "dangling conjunction at the body end, the bare mid-word fragment "
                    "at the body end, the unbalanced parenthesis, or the doubled "
                    "whitespace between fused fragments; preserve all supported "
                    "meaning, qualifiers, numeric values, and formulas."
                ),
                allowed_repair_scope="wording_only",
                attempt=1,
            ))
    return issues


def _story_override_concept_keys(
    *,
    artifact_paths: Mapping[str, str],
    concept_cards: Any,
) -> set[str]:
    """Story-derived Concept relevance override (review Q1).

    Loads the frozen author-story spine from ``authoring_projection_v1``
    (the placement artifact the product flow always persists) and returns
    the concept keys the story names as material.  When no projection is
    present the override is empty — the deterministic audit classifier
    remains the only relevance authority.
    """

    from code2paper.agentic.publication_relevance import (
        story_override_concept_keys,
    )

    value = artifact_paths.get("authoring_projection_v1", "")
    if not value or not Path(value).is_file():
        return set()
    try:
        payload = json.loads(Path(value).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    spine = payload.get("author_story_spine") or ()
    if not isinstance(spine, list):
        return set()
    nodes = [
        node for node in spine
        if isinstance(node, dict) and (node.get("story_node_id") or node.get("title"))
    ]
    if not nodes:
        return set()
    return set(story_override_concept_keys(
        concept_cards=concept_cards,
        story_spine_nodes=nodes,
    ))


def _story_spine_nodes_from_artifact_paths(
    artifact_paths: Mapping[str, str],
) -> list[Any]:
    value = artifact_paths.get("authoring_projection_v1", "")
    if not value or not Path(value).is_file():
        return []
    try:
        payload = json.loads(Path(value).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    spine = payload.get("author_story_spine") or ()
    if not isinstance(spine, list):
        return []
    return [node for node in spine if isinstance(node, dict)]


def _story_spine_models_from_artifact_paths(
    artifact_paths: Mapping[str, str],
) -> list[AuthorStoryNodeV1]:
    """Load the typed story spine for Architect re-planning.

    The Writer view intentionally accepts dictionaries for a compact prompt,
    while the Architect accesses typed node attributes.  Keeping this
    conversion at the artifact boundary prevents a missing/incorrect
    projection from being silently interpreted as an empty story.
    """

    models: list[AuthorStoryNodeV1] = []
    for node in _story_spine_nodes_from_artifact_paths(artifact_paths):
        try:
            models.append(AuthorStoryNodeV1.model_validate(node))
        except (TypeError, ValueError):
            # The enclosing replan identity invariant will fail closed if the
            # frozen plan carried identities that this projection cannot
            # hydrate; do not invent a partial story node here.
            continue
    return models


def _audit_only_claim_ids(
    *,
    propositions: MethodPropositionSetV1 | None,
    proposition_bindings: PropositionBindingSidecarV1 | None,
    concept_cards: Any | None = None,
    audit_concept_keys: frozenset[str] = frozenset(),
    claims: AtomicClaimSetV3 | None = None,
    facts: Any | None = None,
) -> set[str]:
    """Claim ids whose propositions/concepts are audit_only (plan 19.5.4).

    These claims remain fully auditable in evidence and validation; they are
    excluded only from Writer obligations and qualifier Rewrite triggers.

    On the proposition lane the audit set comes from the exact
    proposition-sidecar bindings.  On the concept-card lane it comes from
    the exact Concept -> fact -> claim span projection
    (``concept_audit_claim_ids_exact``): a claim is excluded only when every
    fact it carries is bound to an audit card's own fragments.  Source
    obligation ids never expand the exclusion set (review Q1).
    """

    from code2paper.agentic.publication_relevance import (
        concept_audit_claim_ids_exact,
    )

    result: set[str] = set()
    if propositions is not None and proposition_bindings is not None:
        audit_proposition_ids = {
            item.proposition_id
            for item in propositions.propositions
            if item.writing_role == "audit_only"
        }
        result.update(
            str(claim_id)
            for binding in proposition_bindings.bindings
            if binding.proposition_id in audit_proposition_ids
            for claim_id in binding.claim_ids
        )
    if concept_cards is not None and audit_concept_keys and claims is not None:
        result.update(concept_audit_claim_ids_exact(
            concept_cards=concept_cards,
            audit_concept_keys=audit_concept_keys,
            claims=claims,
            facts=facts,
        ))
    if claims is not None:
        from code2paper.agentic.publication_relevance import classify_claim_writing_role

        facts_by_id = {
            str(getattr(fact, "fact_id", "") or ""): fact
            for fact in (getattr(facts, "facts", ()) or ())
        }
        for claim in claims.claims:
            if classify_claim_writing_role(claim, facts_by_id=facts_by_id) == "audit_only":
                result.add(str(claim.claim_id))
    return result


def _qualifier_terms_by_section(
    *,
    plan: MethodSectionPlanV2,
    claims: AtomicClaimSetV3,
    exclude_claim_ids: set[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Project frozen required qualifiers onto the Architect's sections.

    The Writer payload is intentionally a reader-facing projection and may
    omit a low-level claim from a section's prompt after concept-card
    grouping.  Qualifier authority must therefore come from the persisted
    plan/claim relation, not from whichever subset the model happened to
    receive.  This map is the canonical baseline shared by quality,
    Rewrite, Editor and transaction metrics.
    """

    claims_by_id = {str(item.claim_id): item for item in claims.claims}
    units_by_id = {
        str(item.argument_unit_id): item for item in plan.argument_units
    }
    claim_sections: dict[str, set[str]] = {}
    for section in plan.sections:
        for unit_id in section.argument_unit_ids:
            unit = units_by_id.get(str(unit_id))
            if unit is None:
                continue
            for claim_id in unit.claim_ids:
                claim_sections.setdefault(str(claim_id), set()).add(
                    str(section.section_id)
                )
    result: dict[str, list[str]] = {}
    for section in plan.sections:
        terms: list[str] = []
        for unit_id in section.argument_unit_ids:
            unit = units_by_id.get(str(unit_id))
            if unit is None:
                continue
            for claim_id in unit.claim_ids:
                if exclude_claim_ids and str(claim_id) in exclude_claim_ids:
                    continue
                claim = claims_by_id.get(str(claim_id))
                # A claim that is missing from the plan or appears in more
                # than one section has no unique lexical owner.  Do not
                # authorize its predicate in either section; the validator's
                # persisted final-claim span will provide a scoped term only
                # after a unique section is known.
                if claim is None or len(
                    claim_sections.get(str(claim_id), set())
                ) != 1:
                    continue
                terms.extend(
                    str(qualifier).strip()
                    for qualifier in (getattr(claim, "required_qualifiers", ()) or ())
                    if str(qualifier).strip()
                )
        if terms:
            result[str(section.section_id)] = list(dict.fromkeys(terms))
    return {
        section_id: tuple(terms)
        for section_id, terms in result.items()
    }


def _merge_qualifier_terms_by_section(
    base: Mapping[str, tuple[str, ...]],
    extra: Mapping[str, Iterable[str]],
) -> dict[str, tuple[str, ...]]:
    """Merge validator-discovered terms into the canonical section map."""

    merged: dict[str, list[str]] = {
        str(section_id): list(dict.fromkeys(terms))
        for section_id, terms in base.items()
    }
    for section_id, terms in extra.items():
        values = merged.setdefault(str(section_id), [])
        values.extend(
            str(term).strip()
            for term in terms
            if str(term).strip()
        )
        merged[str(section_id)] = list(dict.fromkeys(values))
    return {
        section_id: tuple(terms)
        for section_id, terms in merged.items()
        if terms
    }



def _prose_has_repeated_phrase_spam(text: str) -> bool:
    """Reject bodies that repeat the same parenthetical or 5-gram."""

    from collections import Counter

    parens = re.findall(r"\([^()]{8,}\)", str(text or ""))
    if parens:
        counts = Counter(item.strip() for item in parens)
        if any(count >= 4 for count in counts.values()):
            return True
    codes = re.findall(r"`[^`\n]{8,}`", str(text or ""))
    if codes:
        counts = Counter(item.strip() for item in codes)
        if any(count >= 4 for count in counts.values()):
            return True
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]*", str(text or ""))
    if len(tokens) >= 30:
        grams = [" ".join(tokens[index:index + 5]) for index in range(len(tokens) - 4)]
        counts = Counter(grams)
        if counts and max(counts.values()) >= 6:
            return True
    return False


def _writer_retry_failure_code(
    existing_output: PublicationMethodSectionOutputV1 | None,
    *,
    expected_heading: str,
) -> str:
    """Typed retry reason for a missing or degenerate Writer section."""

    if existing_output is None:
        return "writer_output_missing_or_incomplete"
    normalized = _normalize_section_heading_breaks(
        existing_output.section_markdown,
        expected_heading=expected_heading,
    )
    if not _markdown_has_non_heading_body(normalized):
        return "section_body_missing_or_headings_only"
    if _looks_like_caveat_shell(normalized):
        return "caveat_token_shell"
    if _section_body_truncated(normalized):
        return "section_body_truncated"
    if _prose_has_repeated_phrase_spam(normalized):
        return "repeated_token_spam"
    if _section_heading_still_truncated(normalized, expected_heading=expected_heading):
        return "section_heading_truncated"
    return "writer_output_missing_or_incomplete"


def _writer_retry_required_action(failure_code: str, *, heading: str) -> str:
    """Owner-retry instruction.  Never invents mechanism text."""

    action = (
        "Write the full section now. Every planned section must have "
        "a non-empty coherent Method body: start with exactly one "
        "coherent H2 heading, then a blank line, then the body. Use "
        "the section's author-intent purpose and its argument units; "
        "render repository-supported content as normal Method "
        "statements and candidate-only/partial/external content as "
        "visibly caveated narrative. Do not omit the section, do not "
        "repeat the heading, do not leave it headings-only, and do "
        "not stuff pending/intended tokens into the H2 heading. "
        "Digest any planner_filled draft as an organization seed "
        "and write the mechanism as author specification even if a "
        "research callback remains open. Do not emit a deferral "
        "memo such as 'no accepted formula' or 'therefore deferred' "
        "in place of the mechanism. When formula_packages is "
        "present, embed each display-math environment beside the "
        "mechanism; do not paste a second heading or duplicate H3."
    )
    if failure_code == "section_body_missing_or_headings_only":
        action += (
            " A research callback is not a substitute for the body. "
            "Write the mechanism steps in paper language now from the "
            "section briefs and planner_filled drafts; you may still "
            "open a callback for a missing formula after the body exists."
        )
    if failure_code == "repeated_token_spam":
        action += (
            " The previous body repeated the same parenthetical, XML/extract "
            "tag, heading identifier, inline code span, or five-word run. "
            "Write each mechanism step once in paper language; do not paste "
            "the same code guard, identifier, or tag more than once."
        )
    if failure_code == "section_body_truncated":
        action += (
            " The previous body ended mid-clause. Finish every sentence "
            "with a complete clause; do not stop on a connective such as "
            "'extracted in' or 'passed to a'."
        )
    if failure_code == "caveat_token_shell":
        action += (
            " The previous body only said the repository lacks an "
            "operational specification. If claims or technical_propositions "
            "are present, write the licensed mechanism now; do not emit an "
            "empty-shell caveat."
        )
    if heading_is_truncated(heading):
        action += (
            " The supplied plan heading is truncated mid-clause: "
            "complete or shorten it into ONE coherent H2 heading line "
            "that ends at a complete clause, and do not move the "
            "heading's remaining words into the body."
        )
        tail = dangling_heading_tail(heading)
        if tail:
            action += (
                f" The exact dangling tail to complete or drop is {tail!r}; "
                "your section will be rejected if the heading still ends "
                "mid-clause."
            )
    return action


def _latex_has_repeated_token_spam(text: str) -> bool:
    """Reject typeset spam such as the same non-stopword repeated ≥8 times."""

    tokens = [
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_]*", str(text or ""))
    ]
    run = 1
    for index in range(1, len(tokens)):
        current = tokens[index]
        previous = tokens[index - 1]
        if (
            current == previous
            and current not in _FORMULA_TOKEN_STOP_EXTRA
            and current not in _FACET_COVERAGE_STOP_WORDS
        ):
            run += 1
            if run >= 8:
                return True
        else:
            run = 1
    return False


def _formula_package_rendered(text: str, package: Mapping[str, Any]) -> bool:
    """Whether the section body renders one formula package (R2).

    A package counts as rendered only when a math environment is present
    and the latex tokens overlap that environment (or the Formalizer
    ``markdown_block`` is embedded verbatim). Letter overlap in prose
    without math is not enough. Token-spam latex is never rendered.
    """

    latex = str(package.get("latex") or "")
    markdown_block = str(package.get("markdown_block") or "").strip()
    if not latex.strip() and not markdown_block:
        return False
    if _latex_has_repeated_token_spam(text) or _latex_has_repeated_token_spam(latex):
        return False
    if markdown_block and markdown_block in str(text or ""):
        return bool(_FORMULA_ENVIRONMENT_RE.search(markdown_block) or _FORMULA_ENVIRONMENT_RE.search(text))
    if not _FORMULA_ENVIRONMENT_RE.search(str(text or "")):
        return False
    tokens = set(re.findall(r"[a-z][a-z0-9_]*", latex.casefold())) - _FORMULA_TOKEN_STOP_EXTRA
    if not tokens:
        return True
    math_bodies = _FORMULA_ENVIRONMENT_RE.findall(text)
    return any(
        len(tokens & set(re.findall(r"[a-z][a-z0-9_]*", body.casefold()))) / len(tokens) >= 0.5
        for body in math_bodies
    )


_FACET_COVERAGE_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "be", "by", "for", "from", "in", "into",
    "is", "of", "on", "or", "the", "their", "this", "to", "with",
})
_FACET_COVERAGE_FIELD_KEYS = (
    "operation",
    "subject",
    "transformation",
    "inputs",
    "outputs",
    "paper_terms",
    "conditions",
    "interface",
    "interfaces",
    "boundary",
)


def _facet_coverage_tokens(facet: Mapping[str, Any]) -> set[str]:
    """Distinctive semantic-field tokens for coverage (not author quotes)."""

    coverage_values: list[Any] = []
    fields = facet.get("semantic_fields")
    if isinstance(fields, Mapping):
        for key in _FACET_COVERAGE_FIELD_KEYS:
            if key in fields:
                coverage_values.append(fields[key])
    search_terms = facet.get("search_terms") or ()
    if search_terms:
        coverage_values.append(search_terms)
    tokens = _facet_content_tokens(coverage_values)
    return {token for token in tokens if len(token) > 2}


def _facet_required_for_section(
    facet: Any,
    primary_brief_ids: set[str],
) -> bool:
    """Required facets must be core kinds bound to the section's primary briefs."""

    if not getattr(facet, "required", False):
        return False
    brief_id = str(getattr(facet, "brief_id", "") or "").strip()
    if not brief_id:
        return bool(primary_brief_ids)
    if not primary_brief_ids:
        return True
    return brief_id in primary_brief_ids


def _facet_content_tokens(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        tokens: set[str] = set()
        for nested in value.values():
            tokens.update(_facet_content_tokens(nested))
        return tokens
    if isinstance(value, (list, tuple, set)):
        tokens: set[str] = set()
        for nested in value:
            tokens.update(_facet_content_tokens(nested))
        return tokens
    return {
        token.casefold()
        for token in re.findall(r"[^\W_]+", str(value or ""), flags=re.UNICODE)
        if len(token) > 1 and token.casefold() not in _FACET_COVERAGE_STOP_WORDS
    }


def _facet_body_covers(
    text: str,
    facet: Mapping[str, Any],
    *,
    expected_heading: str = "",
) -> bool:
    """Check substantive facet coverage without copying planner wording."""

    normalized = _normalize_section_heading_breaks(
        str(text or ""),
        expected_heading=expected_heading,
    )
    if _looks_like_caveat_shell(normalized):
        return False
    body = "\n".join(
        line for line in normalized.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    body_tokens = _facet_content_tokens(body)
    facet_tokens = _facet_coverage_tokens(facet)
    if not facet_tokens:
        return True
    return bool(body_tokens & facet_tokens)


def _mechanism_packet_from_prompt_payload(
    payload: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    """Return the packet regardless of its compatible payload placement."""

    payload = payload or {}
    writer_view = payload.get("writer_view")
    if isinstance(writer_view, Mapping):
        packet = writer_view.get("mechanism_authoring_packet")
        if isinstance(packet, Mapping):
            return packet
    packet = payload.get("mechanism_authoring_packet")
    return packet if isinstance(packet, Mapping) else None


def _writer_facet_coverage(
    output: PublicationMethodSectionOutputV1 | None,
    writer_input: WriterSectionInput | None,
) -> tuple[set[str], set[str], set[str]]:
    """Return ``(unknown, overlap, missing_required)`` facet ids.

    The structured witness is closed by the harness, while the small lexical
    check prevents a model from claiming an id alongside a pending-token shell.
    Planner draft text is intentionally never used as a coverage substring
    target.
    """

    if output is None or writer_input is None:
        return set(), set(), set()
    payload = writer_input.prompt_payload or {}
    contract = payload.get("binding_contract") or {}
    packet = _mechanism_packet_from_prompt_payload(payload)
    contract_allowed = contract.get("allowed_facet_ids") or ()
    allowed = {
        str(value) for value in contract_allowed
        if str(value).strip()
    }
    if not allowed and isinstance(packet, Mapping):
        allowed = {
            str(item.get("facet_id") or "")
            for item in (packet.get("facets") or ())
            if isinstance(item, Mapping) and str(item.get("facet_id") or "").strip()
        }
    required = {
        str(value) for value in (
            contract.get("required_facet_ids")
            or (packet.get("required_facet_ids", ()) if isinstance(packet, Mapping) else ())
        )
        if str(value).strip()
    }
    rendered = {str(value) for value in output.rendered_from_facet_ids}
    deferred = {str(value) for value in output.deferred_facet_ids}
    unknown = (rendered | deferred) - allowed
    overlap = rendered & deferred
    facet_by_id = {
        str(item.get("facet_id") or ""): item
        for item in (packet.get("facets", ()) if isinstance(packet, Mapping) else ())
        if isinstance(item, Mapping) and str(item.get("facet_id") or "").strip()
    }
    expected_heading = str(writer_input.heading or "")
    body_rendered = {
        facet_id
        for facet_id, facet in facet_by_id.items()
        if _facet_body_covers(
            output.section_markdown,
            facet,
            expected_heading=expected_heading,
        )
    }
    # Harness infers coverage from body; model witness is advisory only.
    effective_rendered = (rendered & allowed) | (body_rendered & allowed)
    missing = required - effective_rendered
    for facet_id in effective_rendered & set(facet_by_id):
        if not _facet_body_covers(
            output.section_markdown,
            facet_by_id[facet_id],
            expected_heading=expected_heading,
        ):
            missing.add(facet_id)
    drafts = []
    writer_view = payload.get("writer_view")
    if isinstance(writer_view, Mapping):
        drafts = list(writer_view.get("mechanism_drafts") or ())
    planner_brief_ids = {
        str(item.get("brief_id") or "").strip()
        for item in drafts
        if isinstance(item, Mapping)
        and str(item.get("status") or "") == "planner_filled"
        and str(item.get("text") or "").strip()
        and str(item.get("brief_id") or "").strip()
    }
    planner_mechanism_facets = {
        facet_id
        for facet_id, facet in facet_by_id.items()
        if str(facet.get("brief_id") or "").strip() in planner_brief_ids
        and str(facet.get("facet_kind") or "") in {
            "mechanism", "formula", "constraint", "interface",
        }
    }
    if planner_mechanism_facets and planner_mechanism_facets <= deferred:
        missing |= planner_mechanism_facets
    return unknown, overlap, missing


_FORMULA_TOKEN_STOP_EXTRA = frozenset({
    "frac", "text", "times", "cdot", "left", "right", "begin", "end", "cases",
    "sum", "prod", "max", "min", "exp", "log", "sqrt", "mathbf", "mathrm",
})


def _formula_rendering_issues_by_section(
    output_by_section: Mapping[str, PublicationMethodSectionOutputV1],
    writer_inputs: Mapping[str, WriterSectionInput],
) -> dict[str, list[TextRepairIssueV1]]:
    """Typed issues for formula packages the Writer did not render (R2).

    A section that received accepted formula packages must render each one
    beside its mechanism and explain its symbols.  Unrendered packages become
    ``formula_not_rendered`` Rewrite issues with the package latex and symbol
    guidance in the reader-facing repair field.
    """

    issues: dict[str, list[TextRepairIssueV1]] = {}
    for section_id, output in output_by_section.items():
        writer_input = writer_inputs.get(str(section_id))
        if writer_input is None:
            continue
        packages = tuple(
            writer_input.prompt_payload.get("formula_packages", ()) or ()
        )
        if not packages:
            continue
        text = str(output.section_markdown or "")
        for index, package in enumerate(packages):
            if _formula_package_rendered(text, package):
                continue
            symbols = " ".join(
                f"{item.get('symbol', '')}={item.get('meaning', '')}"
                for item in (package.get("symbol_definitions") or ())
            )
            issues.setdefault(str(section_id), []).append(TextRepairIssueV1(
                sentence_id=f"formula:{section_id}:{index}",
                failure_type="formula_not_rendered",
                matched_claim_ids=(),
                offending_fragment="",
                missing_fact_or_relation=(
                    "Render this authorized formula in the section body beside the "
                    "mechanism it formalizes (never stacked at the section end), define "
                    "its symbols at first use, and keep its conditions exactly: "
                    + str(package.get("latex") or "")
                    + (f" Symbols: {symbols}" if symbols else "")
                ),
                allowed_repair_scope="formula_rendering",
                attempt=1,
            ))
    return issues


def _academic_rewrite_issues_by_section(
    output_by_section: Mapping[str, PublicationMethodSectionOutputV1],
    *,
    claims: AtomicClaimSetV3,
    writer_inputs: Mapping[str, WriterSectionInput],
    qualifier_terms_by_section: Mapping[str, tuple[str, ...]] | None = None,
) -> dict[str, list[TextRepairIssueV1]]:
    """Build promptable academic-revision concerns for the Rewrite owner.

    Rules only identify a scoped concern.  They do not rewrite prose.  The
    Rewrite Agent receives the Writer's original authority context and decides
    how to express a supported claim, caveat a candidate-only point, or remove
    unsupported detail.
    """

    # Production callers pass the canonical plan/claim map.  Keep the
    # Writer-payload fallback for focused legacy callers, but never let it
    # override or narrow the canonical authority.
    exempt_qualifier_terms: dict[str, tuple[str, ...]] = {
        str(section_id): tuple(terms)
        for section_id, terms in (qualifier_terms_by_section or {}).items()
    }
    if qualifier_terms_by_section is None:
        for section_id, writer_input in writer_inputs.items():
            terms: list[str] = []
            for raw in (
                writer_input.prompt_payload.get("validation_constraints", {})
                .get("claims", ())
                or ()
            ):
                if not isinstance(raw, dict):
                    continue
                terms.extend(
                    str(qualifier).strip()
                    for qualifier in raw.get("required_qualifiers", ())
                    if str(qualifier).strip()
                )
            if terms:
                exempt_qualifier_terms[section_id] = tuple(dict.fromkeys(terms))

    issues = _method_language_repair_issues_by_section(
        output_by_section,
        exempt_qualifier_terms=exempt_qualifier_terms,
    )
    for section_id, leakage_issues in _reader_facing_leakage_issues_by_section(
        output_by_section
    ).items():
        issues.setdefault(section_id, []).extend(leakage_issues)
    for section_id, structure_issues in _section_structure_issues_by_section(
        output_by_section, writer_inputs=writer_inputs
    ).items():
        issues.setdefault(section_id, []).extend(structure_issues)
    for section_id, punctuation_issues in _malformed_punctuation_issues_by_section(
        output_by_section
    ).items():
        issues.setdefault(section_id, []).extend(punctuation_issues)
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
    # R2: formula packages that the Writer did not render become typed
    # Rewrite issues (the owner may repair rendering in a bounded round).
    for _section_id, _items in _formula_rendering_issues_by_section(
        output_by_section, writer_inputs
    ).items():
        issues.setdefault(_section_id, []).extend(_items)
    # On the mechanism packet path, owner routing is strict: evidence,
    # formula, and missing-content issues must return to Research, Formalizer,
    # or Writer respectively.  Legacy proposition-only callers retain their
    # compatibility behavior while the new packet path is migrated.
    from code2paper.agentic.publication_issue_owner_router import (
        rewrite_owned_issues,
    )
    for section_id, section_issues in tuple(issues.items()):
        issues[section_id] = list(
            rewrite_owned_issues(section_issues, section_id=str(section_id))
        )
        if not issues[section_id]:
            issues.pop(section_id)
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


def _section_revision_budget() -> int:
    """Configured section revision budget (Q4, plan 19.8.1).

    Defaults to 3 content-revision rounds; configurable via
    ``CODE2PAPER_SECTION_REVISION_BUDGET`` and clamped to the product hard
    cap of 5.  Callback tool calls keep their own independent budget.
    """

    try:
        configured = int(os.environ.get("CODE2PAPER_SECTION_REVISION_BUDGET", "3"))
    except ValueError:
        configured = 3
    return max(0, min(configured, 5))


def _candidate_validation_status(
    final_text_validation_status: str,
) -> Literal["not_run", "passed", "warnings", "error"]:
    """Map the reverse-gate result onto the independent candidate validation state.

    Q0: validation failures are warnings for the candidate (never erasure),
    and a validator exception is its own ``error`` state so it cannot be
    mistaken for an honest failed verdict.
    """

    return {
        "pending": "not_run",
        "passed": "passed",
        "failed": "warnings",
        "error": "error",
    }.get(final_text_validation_status, "not_run")


def _verified_validation_status(
    *,
    final_text_validation_status: str,
    verified_markdown: str,
) -> Literal["not_run", "passed", "incomplete", "error"]:
    """Map the reverse-gate result onto the independent Verified validation state.

    Verified is fail-closed: any factual warning excludes the sentence; a
    validator error leaves Verified at ``error`` (previous same-binding view
    or empty), never a guessed view.
    """

    if final_text_validation_status == "error":
        return "error"
    if final_text_validation_status == "failed":
        return "incomplete"
    if final_text_validation_status == "passed":
        return "passed" if verified_markdown.strip() else "incomplete"
    return "not_run"


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


def _transaction_formula_missing_count(
    accepted: list[tuple[str, str, str]],
    writer_inputs: Mapping[str, WriterSectionInput],
) -> int:
    """Count formula packages not rendered in the transaction text (R2)."""

    missing = 0
    for section_id, text, _ref in accepted:
        writer_input = writer_inputs.get(str(section_id))
        if writer_input is None:
            continue
        for package in writer_input.prompt_payload.get("formula_packages", ()) or ():
            if not _formula_package_rendered(text, package):
                missing += 1
    return missing


def _rewrite_transaction_metrics(
    *,
    accepted: list[tuple[str, str, str]],
    output_by_section: Mapping[str, PublicationMethodSectionOutputV1],
    writer_inputs: Mapping[str, WriterSectionInput],
    artifact_paths: dict[str, str],
    claims: AtomicClaimSetV3,
    equations: EquationClaimSetV1,
    plan: MethodSectionPlanV2,
    propositions: MethodPropositionSetV1 | None,
    proposition_bindings: PropositionBindingSidecarV1 | None = None,
    concept_cards: Any | None = None,
    llm_config: LLMConfig,
) -> dict[str, Any]:
    """Evaluate one intermediate candidate without another full LLM audit.

    The initial draft and the final accepted document still receive the
    independent proposition/evidence alignment.  During bounded Writer and
    Rewrite transactions, however, every proposed local edit used to invoke
    that sentence-level LLM aligner over the whole document again.  This made
    one style repair expand into dozens of model calls and did not add new
    authority: the proposal is provisional until the final reverse gate.
    Transaction checks therefore use the deterministic closed proposition
    projection plus the ordinary evidence/style metrics.  The final gate
    remains fail-closed and LLM-assisted.
    """

    final_text = "\n\n".join(text for _section_id, text, _ref in accepted)
    # Keep validator-discovered qualifier terms separate until the temporary
    # validation snapshot has mapped its atomic-claim spans back to sections.
    # The frozen plan is the baseline authority; these terms cover claims that
    # the final-text validator materializes from a persisted evidence record
    # even when the compact Writer projection did not include that claim.
    validator_qualifiers_by_section: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory(prefix="code2paper-rewrite-transaction-") as root:
        validation_status, validation_paths = _maybe_validate_final_text(
            out_root=root,
            artifact_paths=artifact_paths,
            claims=claims,
            equations=equations,
            final_text=final_text,
            accepted=accepted,
            plan=plan,
            propositions=propositions,
            proposition_bindings=proposition_bindings,
            concept_cards=concept_cards,
            # Intermediate transaction only: do not construct the semantic
            # LLM aligner.  Final publication validation below the repair loop
            # is still called with the real role configuration.
            llm_config=None,
        )
        validation_counts = _validation_failure_counts(validation_paths)
        validation_detail: dict[str, int] | None = None
        unsupported_by_section: dict[str, list[dict[str, Any]]] = {}
        validation_path = validation_paths.get("text_evidence_validation", "")
        claims_snapshot_path = validation_paths.get("final_text_claims", "")
        section_ranges: list[tuple[str, int, int]] = []
        cursor = 0
        for section_id, text, _response_ref in accepted:
            section_ranges.append((section_id, cursor, cursor + len(text)))
            cursor += len(text) + 2
        if validation_path and Path(validation_path).is_file():
            report = load_text_evidence_validation(validation_path)
            validation_detail = {
                "supported": int(report.supported_claims),
                "caveated": int(report.caveated_claims),
                "unsupported": int(report.unsupported_claims),
                "unverified": int(report.unverified_claims),
            }
            # Map every unsupported/unverified verdict back to its section so
            # the bounded Rewrite loop can spend its next attempt on a
            # section the deterministic validator still marks as failing,
            # instead of trusting the model's ``incomplete`` self-report.
            claim_ranges: dict[str, tuple[int, int]] = {}
            if claims_snapshot_path and Path(claims_snapshot_path).is_file():
                try:
                    claims_snapshot = json.loads(
                        Path(claims_snapshot_path).read_text(encoding="utf-8")
                    )
                    claim_ranges = {
                        str(item.get("atomic_claim_id") or ""): (
                            int(item.get("char_start") or -1),
                            int(item.get("char_end") or -1),
                        )
                        for item in claims_snapshot.get("atomic_claims", ())
                        if item.get("atomic_claim_id")
                    }
                except (OSError, TypeError, ValueError, json.JSONDecodeError):
                    claim_ranges = {}
            for verdict in report.verdicts:
                start, end = claim_ranges.get(str(verdict.atomic_claim_id), (-1, -1))
                section_id = next((
                    section_id
                    for section_id, s_start, s_end in section_ranges
                    if start >= s_start and start < s_end
                ), "")
                if not section_id:
                    continue
                if verdict.required_qualifiers:
                    validator_qualifiers_by_section.setdefault(
                        section_id, []
                    ).extend(
                        str(qualifier).strip()
                        for qualifier in verdict.required_qualifiers
                        if str(qualifier).strip()
                    )
                if verdict.status not in {"unsupported", "unverified"}:
                    continue
                unsupported_by_section.setdefault(section_id, []).append({
                    "atomic_claim_id": verdict.atomic_claim_id,
                    "status": verdict.status,
                    "failures": list(verdict.deterministic_failures or ()),
                    "required_qualifiers": list(verdict.required_qualifiers or ()),
                    "fragment": str(verdict.unsupported_fragment or ""),
                })
    candidate_outputs = dict(output_by_section)
    for section_id, text, _response_ref in accepted:
        output = candidate_outputs.get(section_id)
        if output is not None:
            candidate_outputs[section_id] = output.model_copy(update={
                "section_markdown": text,
            })
    transaction_qualifier_terms = _merge_qualifier_terms_by_section(
        _qualifier_terms_by_section(plan=plan, claims=claims),
        validator_qualifiers_by_section,
    )
    transaction_style_issues = _academic_rewrite_issues_by_section(
        candidate_outputs,
        claims=claims,
        writer_inputs=writer_inputs,
        qualifier_terms_by_section=transaction_qualifier_terms,
    )
    style_issue_fragments_by_section = {
        str(section_id): [
            {
                "sentence_id": issue.sentence_id,
                "failure_type": issue.failure_type,
                "fragment": str(issue.offending_fragment or ""),
            }
            for issue in items
            if issue.failure_type == "method_language_style"
        ]
        for section_id, items in transaction_style_issues.items()
        if any(issue.failure_type == "method_language_style" for issue in items)
    }
    style_count = sum(
        sum(issue.failure_type == "method_language_style" for issue in items)
        for items in transaction_style_issues.values()
    )
    structure_count = sum(
        sum(issue.failure_type == "section_structure" for issue in items)
        for items in transaction_style_issues.values()
    )
    deterministic_config = llm_config.model_copy(update={
        "provider": LLMProvider.NONE,
    })
    alignment = _audit_proposition_alignment(
        accepted=accepted,
        plan=plan,
        propositions=propositions,
        llm_config=deterministic_config,
    )
    missing_propositions = sum(
        len(row.get("missing_proposition_ids") or ())
        for row in alignment.get("sections") or ()
    )
    # Internal-id leakage is a deterministic reader-facing defect that the
    # reverse validator does not count (validated claims may still carry
    # harness ids).  Count matches of the same patterns the issue builder
    # uses so the ``internal_id_leakage`` cluster has a measurable,
    # fail-closed transaction gain, and record the exact remaining matches
    # per section so the bounded loop can spend its next attempt on them.
    leakage_count = 0
    leakage_by_section: dict[str, list[dict[str, Any]]] = {}
    for output in candidate_outputs.values():
        if not isinstance(output, PublicationMethodSectionOutputV1):
            continue
        section_text = str(output.section_markdown or "")
        for pattern in _READER_FACING_INTERNAL_ID_PATTERNS:
            for match in pattern.finditer(section_text):
                leakage_count += 1
                leakage_by_section.setdefault(output.section_id, []).append({
                    "pattern": pattern.pattern[:60],
                    "fragment": match.group(0),
                    "offset": match.start(),
                })
    facet_missing_by_section: dict[str, int] = {}
    for section_id, output in candidate_outputs.items():
        writer_input = writer_inputs.get(str(section_id))
        if writer_input is None:
            continue
        _unknown_facets, overlap_facets, missing_facets = _writer_facet_coverage(
            output,
            writer_input,
        )
        missing_count = len(set(missing_facets) | set(overlap_facets))
        if missing_count:
            facet_missing_by_section[str(section_id)] = missing_count
    return {
        "validation_status": validation_status,
        "validation_counts": validation_counts,
        "validation_detail": validation_detail,
        "unsupported_by_section": unsupported_by_section,
        "style_issue_count": style_count,
        "style_issue_fragments_by_section": style_issue_fragments_by_section,
        "qualifier_terms_by_section": {
            str(section_id): list(terms)
            for section_id, terms in transaction_qualifier_terms.items()
        },
        "structure_issue_count": structure_count,
        "missing_propositions": missing_propositions,
        "leakage_count": leakage_count,
        "leakage_by_section": leakage_by_section,
        "facet_missing_count": sum(facet_missing_by_section.values()),
        "facet_missing_by_section": facet_missing_by_section,
        "formula_missing_count": _transaction_formula_missing_count(
            accepted=accepted,
            writer_inputs=writer_inputs,
        ),
    }


def _rewrite_transaction_has_cluster_gain(
    incumbent: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    cluster_name: str,
) -> tuple[bool, str]:
    """Require non-regression everywhere and gain in the assigned cluster."""

    if (
        incumbent.get("validation_status") == "passed"
        and candidate.get("validation_status") != "passed"
    ):
        return False, "reverse_validation_regressed"
    incumbent_counts = incumbent.get("validation_counts")
    candidate_counts = candidate.get("validation_counts")
    validation_improved = False
    if incumbent_counts is not None:
        if candidate_counts is None:
            return False, "reverse_validation_missing"
        if any(
            candidate_value > incumbent_value
            for candidate_value, incumbent_value in zip(
                candidate_counts, incumbent_counts, strict=True
            )
        ):
            return False, "reverse_validation_counts_regressed"
        validation_improved = candidate_counts < incumbent_counts
    if int(candidate.get("style_issue_count", 0)) > int(
        incumbent.get("style_issue_count", 0)
    ):
        return False, "method_style_regressed"
    if int(candidate.get("structure_issue_count", 0)) > int(
        incumbent.get("structure_issue_count", 0)
    ):
        return False, "section_structure_regressed"
    if int(candidate.get("missing_propositions", 0)) > int(
        incumbent.get("missing_propositions", 0)
    ):
        return False, "proposition_coverage_regressed"
    if int(candidate.get("leakage_count", 0)) > int(
        incumbent.get("leakage_count", 0)
    ):
        return False, "internal_id_leakage_regressed"
    if int(candidate.get("formula_missing_count", 0)) > int(
        incumbent.get("formula_missing_count", 0)
    ):
        return False, "formula_rendering_regressed"
    if int(candidate.get("facet_missing_count", 0)) > int(
        incumbent.get("facet_missing_count", 0)
    ):
        return False, "required_facet_coverage_regressed"
    if cluster_name == "qualifier_numeric_formula":
        incumbent_target = _rewrite_cluster_remaining_count(
            incumbent,
            cluster_name,
        )
        candidate_target = _rewrite_cluster_remaining_count(
            candidate,
            cluster_name,
        )
        if candidate_target >= incumbent_target:
            return False, "qualifier_target_not_reduced"
    style_improved = int(candidate.get("style_issue_count", 0)) < int(
        incumbent.get("style_issue_count", 0)
    )
    structure_improved = int(candidate.get("structure_issue_count", 0)) < int(
        incumbent.get("structure_issue_count", 0)
    )
    proposition_improved = int(candidate.get("missing_propositions", 0)) < int(
        incumbent.get("missing_propositions", 0)
    )
    leakage_improved = int(candidate.get("leakage_count", 0)) < int(
        incumbent.get("leakage_count", 0)
    )
    status_improved = (
        incumbent.get("validation_status") != "passed"
        and candidate.get("validation_status") == "passed"
    )
    expected_gain = {
        "internal_id_leakage": leakage_improved,
        "unsafe_positive_or_authority": validation_improved or status_improved,
        "qualifier_numeric_formula": validation_improved or status_improved,
        "formula_rendering": int(candidate.get("formula_missing_count", 0))
        < int(incumbent.get("formula_missing_count", 0)),
        "missing_supported_proposition": proposition_improved or validation_improved,
        "section_structure": structure_improved,
        "method_language_style": style_improved,
        "duplicate_or_transition": style_improved,
    }.get(cluster_name, False)
    if not expected_gain:
        return False, f"no_{cluster_name}_gain"
    return True, "monotonic_cluster_gain"


def _rewrite_cluster_remaining_count(
    metrics: Mapping[str, Any],
    cluster_name: str,
) -> int:
    """Count the targeted failures in one transaction snapshot.

    Aggregate validation counts are necessary safety dimensions but are not
    sufficient evidence that a qualifier repair fixed the qualifier it was
    asked to repair.  Keep this small projection next to the transaction
    gate so a patch cannot be admitted merely because an unrelated sentence
    became supported.
    """

    if cluster_name == "qualifier_numeric_formula":
        return sum(
            sum(
                _verdict_belongs_to_rewrite_cluster(row, cluster_name)
                for row in rows
            )
            for rows in (metrics.get("unsupported_by_section", {}) or {}).values()
        )
    if cluster_name == "internal_id_leakage":
        return int(metrics.get("leakage_count", 0))
    if cluster_name in {"method_language_style", "duplicate_or_transition"}:
        return int(metrics.get("style_issue_count", 0))
    if cluster_name == "section_structure":
        return int(metrics.get("structure_issue_count", 0))
    if cluster_name == "missing_supported_proposition":
        return int(metrics.get("missing_propositions", 0))
    return int((metrics.get("validation_counts") or (0,))[0])


def _writer_transaction_has_safe_gain(
    incumbent: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> tuple[bool, str]:
    """Accept Writer repair only for a measured safe content improvement."""

    incumbent_detail = incumbent.get("validation_detail")
    candidate_detail = candidate.get("validation_detail")
    evidence_gain = False
    if incumbent_detail is not None:
        if candidate_detail is None:
            return False, "writer_reverse_validation_missing"
        if candidate_detail["unsupported"] > incumbent_detail["unsupported"]:
            return False, "writer_unsupported_positive_regressed"
        if candidate_detail["unverified"] > incumbent_detail["unverified"]:
            return False, "writer_unverified_positive_regressed"
        evidence_gain = (
            candidate_detail["supported"] > incumbent_detail["supported"]
            or candidate_detail["caveated"] > incumbent_detail["caveated"]
            or candidate_detail["unsupported"] < incumbent_detail["unsupported"]
            or candidate_detail["unverified"] < incumbent_detail["unverified"]
        )
    if int(candidate.get("style_issue_count", 0)) > int(
        incumbent.get("style_issue_count", 0)
    ):
        return False, "writer_method_style_regressed"
    if int(candidate.get("missing_propositions", 0)) > int(
        incumbent.get("missing_propositions", 0)
    ):
        return False, "writer_proposition_coverage_regressed"
    style_gain = int(candidate.get("style_issue_count", 0)) < int(
        incumbent.get("style_issue_count", 0)
    )
    proposition_gain = int(candidate.get("missing_propositions", 0)) < int(
        incumbent.get("missing_propositions", 0)
    )
    if not (evidence_gain or style_gain or proposition_gain):
        return False, "writer_transaction_no_measured_gain"
    return True, "writer_transaction_monotonic_gain"


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


_REWRITE_ISSUE_CLUSTER_ORDER = (
    "internal_id_leakage",
    "unsafe_positive_or_authority",
    "qualifier_numeric_formula",
    "formula_rendering",
    "missing_supported_proposition",
    "section_structure",
    "method_language_style",
    "duplicate_or_transition",
)


def _rewrite_issue_cluster(issue: TextRepairIssueV1) -> str:
    """Assign one repair issue to one ordered Rewrite responsibility.

    Rewrite calls intentionally receive a single concern class.  Evidence and
    authority failures are handled first so a later fluency edit cannot hide
    an unsupported positive assertion.  The issue's typed validator fields,
    rather than lexical similarity between prose fragments, determine the
    cluster.
    """

    diagnostic = " ".join((
        issue.sentence_id,
        issue.missing_fact_or_relation,
    )).lower()
    if issue.failure_type == "reader_facing_internal_id":
        # Internal id/protocol vocabulary is a standalone reader-facing
        # defect.  Its own cluster keeps the exact-span repair small (one
        # token per patch) and its transaction gain deterministic (counted
        # by the same patterns), instead of being bundled with authority
        # failures whose gain metric is validation-count based.
        return "internal_id_leakage"
    if issue.failure_type == "formula_not_rendered":
        return "formula_rendering"
    if issue.failure_type in {"missing_qualifier", "formula_unsupported"}:
        return "qualifier_numeric_formula"
    if issue.failure_type == "supported_claim_not_rendered" or (
        issue.failure_type == "no_semantically_matching_projected_claim"
        and "planned_claim_missing" in diagnostic
    ):
        return "missing_supported_proposition"
    if issue.failure_type == "section_structure":
        # Heading/body structure (missing, wrong, fused, truncated, heading-
        # only, duplicate) is a reader-facing defect the reverse validator
        # does not count.  Its own cluster measures deterministic structure
        # gain so a pure structure repair is accepted like a leakage fix.
        return "section_structure"
    if issue.failure_type == "heading_tail_leaked_into_body":
        return "section_structure"
    if issue.failure_type == "method_language_style":
        if any(token in diagnostic for token in (
            "academic-specificity",
            "duplicate",
            "restatement",
            "transition",
        )):
            return "duplicate_or_transition"
        return "method_language_style"
    return "unsafe_positive_or_authority"


def _cluster_validation_failures(
    attempt_context: Mapping[str, Any],
    cluster_issues: Iterable[TextRepairIssueV1],
) -> list[dict[str, Any]]:
    """Restrict the Rewrite context to the assigned cluster's failures.

    The shared section context records every section failure, but the patch
    contract accepts only issue_ids drawn from the current cluster.  Exposing
    out-of-cluster rows (e.g. ``structure:*`` issues already repaired by an
    earlier cluster) invites the model to reference ids it cannot resolve,
    which rejects the whole patch as ``unknown_issue``.  Each row keeps its
    original payload; only membership is filtered.
    """

    cluster_issue_ids = {
        issue.atomic_claim_id or issue.sentence_id
        for issue in cluster_issues
        if (issue.atomic_claim_id or issue.sentence_id)
    }
    return [
        dict(row)
        for row in attempt_context.get("validation_failures", ())
        if isinstance(row, Mapping)
        and (row.get("atomic_claim_id") or row.get("sentence_id"))
        in cluster_issue_ids
    ]


def _verdict_belongs_to_rewrite_cluster(
    row: Mapping[str, Any],
    cluster_name: str,
) -> bool:
    """Whether a remaining validation verdict belongs to one rewrite cluster.

    A rewrite legitimately re-segments prose, so the surviving fragment may
    carry a fresh atomic claim id.  The verdict is therefore matched by the
    failure types it reports, projected onto the same cluster taxonomy the
    Rewrite loop uses (``_rewrite_issue_cluster``).  An unknown failure code
    is routed to the safety-first default cluster so it cannot silently skip
    repair.
    """

    failures = tuple(str(item) for item in row.get("failures") or ())
    if not failures:
        return cluster_name == "unsafe_positive_or_authority"
    for failure in failures:
        repair_type, _scope, _hint = failure_to_repair_scope(failure)
        probe = TextRepairIssueV1(
            sentence_id=row.get("sentence_id") or row.get("atomic_claim_id") or "",
            atomic_claim_id=row.get("atomic_claim_id") or "",
            failure_type=repair_type,
            allowed_repair_scope=_scope,
        )
        if _rewrite_issue_cluster(probe) == cluster_name:
            return True
    return False


def _cluster_rewrite_issues(
    issues: Iterable[TextRepairIssueV1],
) -> tuple[tuple[str, tuple[TextRepairIssueV1, ...]], ...]:
    """Return non-empty issue clusters in safety-first execution order."""

    grouped: dict[str, list[TextRepairIssueV1]] = {
        name: [] for name in _REWRITE_ISSUE_CLUSTER_ORDER
    }
    for issue in issues:
        grouped[_rewrite_issue_cluster(issue)].append(issue)
    return tuple(
        (name, tuple(grouped[name]))
        for name in _REWRITE_ISSUE_CLUSTER_ORDER
        if grouped[name]
    )


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
    qualifier_terms_by_section: Mapping[str, tuple[str, ...]] | None = None,
    transaction_validator: Callable[
        [str, str, list[tuple[str, str, str]]], tuple[bool, str]
    ] | None = None,
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
    qualifier_terms_by_section = qualifier_terms_by_section or {}
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
        "formula_rendering": 1,
        "sentence_atomicity": 2,
        "claim_decomposition": 3,
        "packet_relation": 4,
        "code_search": 5,
        "drop_or_gap": 6,
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
        writer_input = writer_context_by_section.get(section_id)
        packet = _mechanism_packet_from_prompt_payload(
            writer_input.prompt_payload if writer_input is not None else None
        )
        if isinstance(packet, Mapping) and packet.get("facets"):
            from code2paper.agentic.publication_issue_owner_router import (
                route_publication_issue,
            )

            owner_route = route_publication_issue(issue, section_id=section_id)
            if owner_route.owner != "rewrite":
                # Evidence/FAC/formula owners stay on their sidecar paths.
                # Do not record rewrite:wrong_owner; that noise drowned
                # Rewrite-owned code-trace repairs on the Candidate lane.
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
        writer_input = writer_context_by_section.get(section_id)
        packet = _mechanism_packet_from_prompt_payload(
            writer_input.prompt_payload if writer_input is not None else None
        )
        if isinstance(packet, Mapping) and packet.get("facets"):
            from code2paper.agentic.publication_issue_owner_router import (
                rewrite_owned_issues,
            )

            section_issues = list(
                rewrite_owned_issues(section_issues, section_id=str(section_id))
            )
        if not section_issues:
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
        # Rewrite receives the Writer's authority surface so it can preserve
        # authorized semantics while repairing paper language.  Authority,
        # evidence, formula, and missing-content decisions stay on their
        # owning routes.
        section_context["writer_authority_context"] = dict(
            writer_input.prompt_payload
        )
        packet = _mechanism_packet_from_prompt_payload(
            writer_input.prompt_payload
        )
        section_context["strict_owner_routing"] = bool(
            isinstance(packet, Mapping) and packet.get("facets")
        )
        section_context["writer_heading"] = str(
            section_context.get("authorized_heading")
            or writer_input.heading
        )
        output = output_by_section.get(section_id)
        if output is not None:
            first_line = str(output.section_markdown or "").lstrip().splitlines()[:1]
            if first_line and first_line[0].lstrip().startswith("#"):
                rendered = first_line[0].lstrip("# ").strip()
                if rendered:
                    section_context["writer_heading"] = rendered
                    section_context["authorized_heading"] = rendered
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
    for section_id, section_context in issue_context_by_section.items():
        section_context["authorized_qualifier_terms"] = list(
            qualifier_terms_by_section.get(section_id, ())
        )
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
            os.environ.get("CODE2PAPER_LOCAL_REWRITE_MAX_ATTEMPTS", "3")
        )
    except ValueError:
        configured_rewrite_attempts = 3
    max_rewrite_attempts = max(1, min(configured_rewrite_attempts, 3))
    for section_id, section_issues in issues_by_section.items():
        incumbent_text, incumbent_ref = accepted_by_id[section_id]
        working_text = incumbent_text
        working_ref = incumbent_ref
        working_ledger = incumbent_section_ledgers[section_id]
        applied_any = False
        strict_owner_routing = bool(
            issue_context_by_section.get(section_id, {}).get(
                "strict_owner_routing"
            )
        )
        section_max_rewrite_attempts = (
            max(1, min(configured_rewrite_attempts, 3))
            if strict_owner_routing
            else max_rewrite_attempts
        )
        clusters = (
            (("method_language_style", tuple(section_issues)),)
            if strict_owner_routing
            else _cluster_rewrite_issues(section_issues)
        )
        for cluster_name, cluster_issues in clusters:
            cluster_applied = False
            prior_cluster_result: dict[str, Any] = {}
            transaction_metrics: dict[str, Any] = {}
            for attempt in range(1, section_max_rewrite_attempts + 1):
                attempt_issues = [
                    issue.model_copy(update={"attempt": attempt})
                    for issue in cluster_issues
                ]
                attempt_context = dict(issue_context_by_section.get(section_id, {}))
                attempt_context["issue_cluster"] = cluster_name
                # The Rewrite contract accepts patches whose issue_ids are a
                # subset of this cluster's issues only.  If the context still
                # listed every section failure (including structure:* issues
                # from an earlier cluster), the model would legitimately
                # reference out-of-cluster ids and every patch would be
                # rejected as unknown_issue.  Expose only the assigned
                # cluster's failures so the model can name exactly the ids it
                # is allowed to resolve.
                attempt_context["validation_failures"] = _cluster_validation_failures(
                    attempt_context,
                    cluster_issues,
                )
                attempt_context["cluster_instruction"] = (
                    "Repair only this issue cluster. Preserve every already-corrected "
                    "fact, qualifier, formula, caveat, heading, and proposition outside "
                    "the assigned spans. Do not use a fluency edit to hide an evidence "
                    "or authority failure."
                )
                attempt_context["attempt"] = attempt
                attempt_context["max_attempts"] = section_max_rewrite_attempts
                if attempt > 1:
                    attempt_context["prior_attempt_feedback"] = {
                        "status": prior_cluster_result.get("status", ""),
                        "blocked_reason": prior_cluster_result.get("blocked_reason", ""),
                        "patch_failures": prior_cluster_result.get("patch_failures", ()),
                        "remaining_validation_failures": prior_cluster_result.get(
                            "remaining_validation_failures", ()
                        ),
                    }
                    attempt_context["prior_attempt_instruction"] = (
                        "Re-audit the current incumbent and address only the assigned cluster. "
                        "The prior attempt was incomplete or rejected by the patch/readability "
                        "contract; use prior_attempt_feedback to correct it. If "
                        "remaining_validation_failures is non-empty, the deterministic reverse "
                        "validator still rejects the assigned claims: repair exactly those "
                        "fragments (for example split a qualifier-bound branch statement from "
                        "the general-path formula it does not scope). If "
                        "remaining_internal_id_leakage is non-empty, remove exactly those "
                        "harness-internal tokens from the reader prose while keeping the "
                        "surrounding supported content. Return one or more "
                        "disjoint non-overlapping patches; copy each original_text "
                        "character-for-character from the incumbent. A patch list of several "
                        "small exact spans is preferred over one full-paragraph or full-section "
                        "patch. Preserve a readable candidate paragraph for "
                        "typed candidate points instead of deleting the section. Return "
                        "incomplete=false only when this cluster needs no further safe edit."
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
                        candidate_ledger = rewrite_final_text_authorship_ledger(
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
                        if transaction_validator is not None:
                            candidate_sections = [
                                (
                                    candidate_section_id,
                                    result.candidate_text
                                    if candidate_section_id == section_id
                                    else accepted_by_id[candidate_section_id][0],
                                    result.response_ref
                                    if candidate_section_id == section_id
                                    else accepted_by_id[candidate_section_id][1],
                                )
                                for candidate_section_id, _text, _ref in accepted
                            ]
                            transaction_ok, transaction_reason, transaction_metrics = (
                                transaction_validator(
                                    section_id,
                                    cluster_name,
                                    candidate_sections,
                                )
                            )
                            if not transaction_ok:
                                result = result.model_copy(update={
                                    "status": "rejected",
                                    "candidate_digest": result.incumbent_digest,
                                    "candidate_text": working_text,
                                    "blocked_reason": (
                                        "rewrite_transaction_rejected:"
                                        + transaction_reason
                                    ),
                                    "patch_failures": tuple([
                                        *result.patch_failures,
                                        "transaction_no_monotonic_gain",
                                    ]),
                                })
                        if result.status == "applied":
                            working_ledger = candidate_ledger
                        else:
                            candidate_ledger = working_ledger
                    if result.status == "applied":
                        applied_any = True
                        cluster_applied = True
                        working_text = result.candidate_text
                        working_ref = result.response_ref or working_ref
                        rewritten_ledger_by_section[section_id] = working_ledger
                result_payload = result.model_dump(mode="json")
                prior_cluster_result = result_payload
                # The model's ``incomplete`` self-report is not authoritative:
                # the deterministic transaction snapshot decides whether the
                # section still carries unsupported/unverified claims, and the
                # next attempt receives the exact remaining fragments.  Only
                # verdicts that belong to this cluster's concern count, so an
                # unrelated section failure cannot burn this cluster's bounded
                # attempt budget.  Matching is by failure type, not claim id:
                # a rewrite legitimately re-segments prose, so the surviving
                # fragment may carry a fresh atomic claim id.
                remaining_failures = [
                    row for row in transaction_metrics.get(
                        "unsupported_by_section", {}
                    ).get(section_id, ())
                    if _verdict_belongs_to_rewrite_cluster(row, cluster_name)
                ]
                remaining_leakage = (
                    list(transaction_metrics.get("leakage_by_section", {}).get(
                        section_id, ()
                    ))
                    if cluster_name == "internal_id_leakage"
                    else []
                )
                if remaining_failures or remaining_leakage:
                    prior_cluster_result = {
                        **prior_cluster_result,
                        "remaining_validation_failures": remaining_failures,
                        "remaining_internal_id_leakage": remaining_leakage,
                    }
                from code2paper.agentic.publication_issue_owner_router import (
                    route_publication_issues,
                )
                owner_routes = route_publication_issues(
                    attempt_issues,
                    section_id=section_id,
                    attempt=attempt,
                    input_digest=result.incumbent_digest,
                    output_digest=result.candidate_digest,
                    stop_reason=result.blocked_reason,
                )
                results.append({
                    "section_id": section_id,
                    "issue_cluster": cluster_name,
                    "attempt": attempt,
                    "result": result_payload,
                    "transaction_metrics": transaction_metrics,
                    "owner_routes": [
                        route.model_dump(mode="json")
                        for route in owner_routes
                    ],
                })
                transitions.append(RepairTransitionV1(
                    transition_id=(
                        f"local-rewrite:{section_id}:{cluster_name}:attempt-{attempt}"
                    ),
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
                        and (
                            result.output.incomplete
                            or _applied_rewrite_still_needs_method_language_repair(
                                section_id=section_id,
                                candidate_text=result.candidate_text,
                                section_issues=attempt_issues,
                                output_by_section=output_by_section,
                                qualifier_terms_by_section=qualifier_terms_by_section,
                            )
                            or bool(remaining_failures)
                            or bool(remaining_leakage)
                        )
                    )
                    or (
                        result.status == "rejected"
                        and (
                            result.blocked_reason in {
                                "rewrite_patch_contract_failed",
                                "rewrite_candidate_not_readable",
                            }
                            or result.blocked_reason.startswith(
                                "rewrite_transaction_rejected:"
                            )
                            or result.blocked_reason.startswith(
                                "rewrite_schema_failed:"
                            )
                        )
                    )
                )
                if not wants_another_attempt:
                    if result.status != "applied" and not cluster_applied:
                        failures.append(
                            f"rewrite:{section_id}:{cluster_name}:{result.status}"
                        )
                    break
                if attempt == section_max_rewrite_attempts:
                    failures.append(
                        f"rewrite:{section_id}:{cluster_name}:attempt_budget_exhausted"
                    )
                    failures.append("rewrite_budget_exhausted_kept_incumbent")
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


def _applied_rewrite_still_needs_method_language_repair(
    *,
    section_id: str,
    candidate_text: str,
    section_issues: Iterable[TextRepairIssueV1],
    output_by_section: Mapping[str, PublicationMethodSectionOutputV1],
    qualifier_terms_by_section: Mapping[str, tuple[str, ...]] | None = None,
) -> bool:
    """Spend the bounded second attempt when code-trace style remains."""

    if not any(issue.failure_type == "method_language_style" for issue in section_issues):
        return False
    output = output_by_section.get(section_id)
    if output is None:
        return False
    candidate_output = output.model_copy(update={"section_markdown": candidate_text})
    return bool(find_code_trace_prose_sections(
        [candidate_output],
        exempt_qualifier_terms={
            section_id: tuple((qualifier_terms_by_section or {}).get(section_id, ()))
        },
    ))


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


_HTML_BREAK_RE = re.compile(
    r"</?(?:br|p|div|hr)\b[^>]*>",
    flags=re.IGNORECASE,
)
_HEADING_ANCHOR_RE = re.compile(r"\{#[A-Za-z0-9_:.-]+\}")
_EXTRACT_TAG_RE = re.compile(r"\[/?extract_[a-z]+\]", flags=re.IGNORECASE)
_RESEARCH_REQUEST_TOKEN_RE = re.compile(
    r"\[research-request:[^\]]+\]",
    flags=re.IGNORECASE,
)
_BRACKET_QUALIFIER_RUN_RE = re.compile(
    r"(?:\s*\[(?:intended|partial|pending|author[- ]intent)"
    r"(?:\s*,\s*(?:intended|partial|pending|author[- ]intent))*\]){2,}",
    flags=re.IGNORECASE,
)
_EMPTY_PAREN_RE = re.compile(r"\(\s*\)")
_EMPTY_BRACE_RUN_RE = re.compile(r"(?:\{\}){2,}")
_GLUED_HTML_RESIDUE_RE = re.compile(r"^(?:</?[a-zA-Z][^>]*>|p>)(.*)$", flags=re.DOTALL)


def _normalize_writer_representation_noise(markdown: str) -> str:
    """Strip Writer representation noise without inventing wording.

    HTML block tags, extract_itex-style wrappers, empty ``{}`` runs, and
    Pandoc heading identifiers are not Method content.
    """

    text = _HTML_BREAK_RE.sub("\n", str(markdown or ""))
    text = _EXTRACT_TAG_RE.sub("", text)
    text = _RESEARCH_REQUEST_TOKEN_RE.sub("", text)
    text = _BRACKET_QUALIFIER_RUN_RE.sub("", text)
    text = _EMPTY_BRACE_RUN_RE.sub("", text)
    text = _HEADING_ANCHOR_RE.sub("", text)
    text = re.sub(r"\$\s*\$", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text


def _collapse_repeated_matches_if_body_remains(
    text: str,
    *,
    find_pattern: str,
    strip_pattern: str,
) -> str:
    """Keep the first copy of a span that appears ≥4 times.

    Only applied when the remainder is still a real paragraph.  A body that
    is only the repeated span stays intact so the spam gate can reject it.
    """

    from collections import Counter

    matches = re.findall(find_pattern, str(text or ""))
    if not matches:
        return text
    counts = Counter(matches)
    collapsed = str(text)
    changed = False
    for phrase, count in counts.items():
        if count < 4:
            continue
        state = {"seen": 0}

        def _keep_first(match: re.Match[str], target: str = phrase, box: dict[str, int] = state) -> str:
            if match.group(0) != target:
                return match.group(0)
            box["seen"] += 1
            return match.group(0) if box["seen"] == 1 else ""

        collapsed = re.sub(re.escape(phrase), _keep_first, collapsed)
        changed = True
    if not changed:
        return text
    stripped = re.sub(strip_pattern, " ", collapsed)
    body_lines = [
        line for line in stripped.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    words = re.findall(r"[A-Za-z]{3,}", " ".join(body_lines))
    if len(words) < 12:
        return text
    collapsed = re.sub(r"[ \t]{2,}", " ", collapsed)
    collapsed = re.sub(r" *\n", "\n", collapsed)
    return collapsed


def _collapse_repeated_parentheticals_if_body_remains(text: str) -> str:
    """Keep the first copy of a parenthetical that appears ≥4 times."""

    return _collapse_repeated_matches_if_body_remains(
        text,
        find_pattern=r"\([^()]{8,}\)",
        strip_pattern=r"\([^()]*\)",
    )


def _collapse_repeated_inline_code_if_body_remains(text: str) -> str:
    """Keep the first copy of an inline-code span that appears ≥4 times.

    Live LinearRAG Writer glued the same backtick-wrapped code guard onto
    every sentence.  Collapsing extra copies is representation-only; the
    remaining body must still be a real paragraph.
    """

    return _collapse_repeated_matches_if_body_remains(
        text,
        find_pattern=r"`[^`\n]{8,}`",
        strip_pattern=r"`[^`]*`",
    )


def _strip_empty_parentheticals_left_by_collapse(text: str) -> str:
    """Remove empty ``()`` left when extra inline-code copies are dropped."""

    cleaned = _EMPTY_PAREN_RE.sub("", str(text or ""))
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" *\n", "\n", cleaned)
    return cleaned


def _writing_request_is_locally_unfulfillable(request: Any, *, graph: Any) -> bool:
    """Skip local formal_derivation when Architect marked the section N/A.

    LinearRAG 234218 opened ``req:MA-S1:001`` on a ``formula_not_applicable``
    section.  Fulfillment found no package and stopped the whole callback
    loop as ``no_progress`` while external requests stayed pending.
    """

    lane = ""
    if isinstance(request, Mapping):
        lane = str(request.get("required_authority_lane") or "").strip()
    else:
        lane = str(getattr(request, "required_authority_lane", "") or "").strip()
    if lane != "formal_derivation":
        return False
    return bool(getattr(graph, "formula_not_applicable", False))


def _canonical_section_heading_phrase(heading: str) -> str:
    """Reader-facing heading phrase: no markdown hashes, collapsed whitespace."""

    text = str(heading or "").strip()
    while text.startswith("#"):
        text = text[1:].lstrip()
    return " ".join(text.split()).strip()


def _markdown_has_non_heading_body(markdown: str) -> bool:
    """Whether a normalized section markdown carries any non-heading body.

    A section that is empty, or whose only non-empty lines are heading
    lines (including a degenerate single line of repeated headings), has no
    Method content and must not be accepted into the final document.
    HTML ``<br>`` is representation noise from some writers; treat it as a
    line break so a fused heading+body line is not classified as
    headings-only (LinearRAG 100052 MA-S2).
    """

    text = _normalize_writer_representation_noise(str(markdown or ""))
    nonempty = [line for line in text.splitlines() if line.strip()]
    if not nonempty:
        return False
    if len(nonempty) == 1 and nonempty[0].lstrip().startswith("#"):
        line = nonempty[0].lstrip()
        rest = line.lstrip("#").strip()
        period = rest.find(". ")
        if period >= 8 and period + 2 < len(rest) and rest[period + 2:period + 3].isupper():
            return True
        return False
    body_lines = [line for line in nonempty if not line.lstrip().startswith("#")]
    if not body_lines:
        return False
    body_text = " ".join(body_lines)
    stripped = re.sub(
        r"\((?:intended|partial|pending|author-intent)"
        r"(?:,\s*(?:intended|partial|pending|author-intent))*\)",
        "",
        body_text,
        flags=re.IGNORECASE,
    )
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return len(stripped) >= 8


_CAVEAT_SHELL_WORDS = frozenset({
    "a", "an", "and", "be", "confirmation", "details", "design", "for",
    "information", "intended", "is", "mechanism", "method", "of", "partial",
    "pending", "repository", "the", "this", "unverified", "we", "with",
})
_DEFERRAL_SHELL_MARKERS = (
    "therefore deferred",
    "no accepted formula",
    "pending resolution of the formal",
    "not provided in the repository",
    "operational specification is not provided",
    "repository does not provide",
    "repository-authorized propositions",
    "no authorized method operations",
    "no repository-supported propositions",
    "no repository-supported method operations",
    "currently available for this section",
    "currently authorized for this section",
    "section awaits authorized mechanism",
)
_INCOMPLETE_CLAUSE_RE = re.compile(
    r"(?:\b(?:in|to|a|an|the|and|or|of|for|with|by|from|as|into|onto|via)\s*|"
    r"[,:;]\s*|"
    r"(?:从而|因此|并且|以及|防止|使得|通过|根据|由于|然后|进而)\s*)$",
    re.I,
)
_PROVENANCE_TOKEN_RE = re.compile(
    r"`?(?:brief:story:|O-(?:ORGANIZATION|STAGE|COMPONENT|RATIONALE)-)\S+`?",
    re.I,
)
_MECHANISM_VERB_TOKENS = frozenset({
    "apply", "applies", "applied", "compute", "computes", "computed",
    "condition", "conditions", "discretize", "discretizes", "encode",
    "encodes", "encoded", "evolve", "evolves", "initialize", "initializes",
    "initialized", "integrate", "integrates", "map", "maps", "mapped",
    "modulate", "modulates", "parameterize", "parameterizes", "project",
    "projects", "propagate", "propagates", "select", "selects", "transform",
    "transforms", "transformed", "update", "updates", "updated",
})


def _looks_like_caveat_shell(markdown: str) -> bool:
    """Return whether a non-empty body is only a pending/caveat shell.

    A minimum character count is not a semantic coverage gate: repeated
    ``pending``/``intended`` tokens can satisfy it while omitting the
    planner-filled mechanism.  This narrow check rejects only bodies made of
    caveat boilerplate and generic nouns; substantive candidate prose remains
    eligible even when it contains a caveat.  A deferral memo that names
    missing formula packages instead of a mechanism is also a shell.
    """

    text = re.sub(r"<br\s*/?>", "\n", str(markdown or ""), flags=re.IGNORECASE)
    body = " ".join(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    folded = body.casefold()
    if any(marker in folded for marker in _DEFERRAL_SHELL_MARKERS):
        mechanism_tokens = {
            token.casefold()
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", body)
        } & _MECHANISM_VERB_TOKENS
        if not mechanism_tokens:
            return True
    body = re.sub(r"\([^)]*\)", " ", body)
    tokens = [
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", body)
    ]
    if not tokens:
        return not any(character.isalnum() for character in body)
    has_caveat = any(
        token in {"intended", "partial", "pending", "unverified"}
        for token in tokens
    )
    return has_caveat and len(tokens) <= 18 and set(tokens) <= _CAVEAT_SHELL_WORDS


def _section_body_truncated(markdown: str) -> bool:
    """Whether the last prose clause is cut mid-connective."""

    body = " ".join(
        line.strip()
        for line in str(markdown or "").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ).strip()
    if not body:
        return False
    stripped = re.sub(r"[`*]+$", "", body).rstrip()
    if stripped.endswith(("...", "…")):
        return True
    if stripped.count("$") % 2 == 1:
        return True
    if stripped.endswith(("{", "\\", "(", "[")):
        return True
    if re.search(r"[\u4e00-\u9fff]$", stripped) and not stripped.endswith(("。", "！", "？")):
        return True
    if _INCOMPLETE_CLAUSE_RE.search(stripped) and not stripped.endswith((".", "!", "?", "$$", "]", "。", "！", "？")):
        return True
    return False


def _formula_block_complete(markdown_block: str) -> bool:
    block = str(markdown_block or "").strip()
    if not block:
        return False
    if _section_body_truncated(block):
        return False
    return True


def _strip_provenance_tokens(markdown: str) -> str:
    return _PROVENANCE_TOKEN_RE.sub("", str(markdown or "")).replace("  ", " ")


def _infer_used_claim_ids(
    markdown: str,
    claims: Any,
    *,
    allowed_claim_ids: set[str] | frozenset[str] | None = None,
) -> list[str]:
    hay = str(markdown or "").casefold()
    allowed = {str(item) for item in (allowed_claim_ids or ()) if str(item)}
    used: list[str] = []
    for claim in getattr(claims, "claims", ()) or ():
        claim_id = str(getattr(claim, "claim_id", "") or "")
        if allowed and claim_id not in allowed:
            continue
        if not allowed:
            continue
        text = str(getattr(claim, "canonical_text", "") or "").casefold()
        tokens = [token for token in re.findall(r"[a-z0-9]{4,}", text) if token not in {
            "this", "that", "with", "from", "into", "when", "then",
        }]
        if not tokens:
            continue
        overlap = sum(1 for token in tokens if token in hay)
        if overlap >= max(2, min(4, len(tokens) // 3)):
            used.append(claim_id)
    return list(dict.fromkeys(used))


def _section_heading_still_truncated(
    markdown: str,
    *,
    expected_heading: str,
) -> bool:
    """Whether a normalized section's emitted heading is deterministically
    truncated when the plan heading itself was truncated.

    The Writer is the authorized owner to complete or shorten a broken plan
    clause.  If it copied the broken clause verbatim (or produced another
    mid-clause cut or a degenerate one-word heading), the section is
    rejected on its first attempt and routed back to the Writer by the
    missing-section retry instead of being patched span-by-span (the local
    model repeatedly fails exact-span patches on long Unicode headings).
    """

    if not heading_is_truncated(expected_heading):
        return False
    nonempty = [line for line in str(markdown or "").splitlines() if line.strip()]
    if not nonempty or not nonempty[0].lstrip().startswith("#"):
        return False
    emitted = nonempty[0].lstrip("# ").strip()
    return not heading_replacement_is_coherent(
        emitted,
        planned_heading=expected_heading,
    )


def _section_output_acceptable(markdown: str, *, expected_heading: str) -> bool:
    """Whether a Writer output may be accepted into the final document."""

    normalized = _normalize_section_heading_breaks(
        markdown,
        expected_heading=expected_heading,
    )
    if not _markdown_has_non_heading_body(normalized):
        return False
    if _looks_like_caveat_shell(normalized):
        return False
    if _section_body_truncated(normalized):
        return False
    if _prose_has_repeated_phrase_spam(normalized):
        return False
    if _section_heading_still_truncated(normalized, expected_heading=expected_heading):
        return False
    return True


def _section_has_candidate_mechanism(
    markdown: str,
    *,
    expected_heading: str = "",
) -> bool:
    """Whether the section body is a non-shell Candidate mechanism."""

    normalized = _normalize_section_heading_breaks(
        markdown,
        expected_heading=expected_heading,
    )
    if not _markdown_has_non_heading_body(normalized):
        return False
    return not _looks_like_caveat_shell(normalized)


def _candidate_incomplete_section_ids(
    *,
    plan_section_ids: tuple[str, ...],
    accepted_section_ids: set[str],
    callback_section_ids: set[str],
    required_facet_failures_by_section: Mapping[str, Any],
    required_formula_failures_by_section: Mapping[str, Any],
    output_by_section: Mapping[str, Any],
    writer_input_by_section: Mapping[str, Any],
) -> tuple[str, ...]:
    """Candidate-lane incomplete ids: shells, missing facets, empty formula+no story.

    Reverse-validation FAC failures stay on the Verified/review sidecar.  They
    do not mark an already-accepted non-shell section incomplete.
    """

    formula_incomplete: set[str] = set()
    for section_id in required_formula_failures_by_section:
        output = output_by_section.get(section_id)
        writer_input = writer_input_by_section.get(section_id)
        packages = ()
        heading = ""
        if writer_input is not None:
            heading = str(getattr(writer_input, "heading", "") or "")
            packages = (writer_input.prompt_payload or {}).get("formula_packages") or ()
        if packages:
            continue
        markdown = str(getattr(output, "section_markdown", "") or "")
        if output is not None and _section_has_candidate_mechanism(
            markdown,
            expected_heading=heading,
        ):
            continue
        formula_incomplete.add(str(section_id))
    return tuple(dict.fromkeys(
        [
            section_id for section_id in plan_section_ids
            if section_id not in accepted_section_ids
            or section_id in callback_section_ids
            or section_id in required_facet_failures_by_section
            or section_id in formula_incomplete
        ]
    ))


def _repair_writer_text_commands(markdown: str) -> str:
    """Restore ``\\text{`` / ``\\begin{`` after non-raw interpolation damage."""

    text = str(markdown or "")
    text = text.replace("\t" + "ext{", "\\text{")
    text = text.replace("\b" + "egin{", "\\begin{")
    text = re.sub(r"(?<![A-Za-z\\\\])ext\{", r"\\text{", text)
    text = re.sub(r"(?<![A-Za-z\\\\])egin\{", r"\\begin{", text)
    return text


def _formula_latex_already_in_prose(text: str, package: Mapping[str, Any]) -> bool:
    """Whether distinctive latex tokens already appear in the section body."""

    latex = str(package.get("latex") or "").strip()
    if not latex:
        latex = str(package.get("markdown_block") or "")
    tokens = set(re.findall(r"[a-z][a-z0-9_]*", latex.casefold())) - _FORMULA_TOKEN_STOP_EXTRA
    if len(tokens) < 4:
        return False
    found = set(re.findall(r"[a-z][a-z0-9_]*", str(text or "").casefold()))
    return (len(tokens & found) / len(tokens)) >= 0.6


def _formula_display_math(package: Mapping[str, Any]) -> str:
    """Display math only: never a second H3 or Formalizer prose wrapper."""

    latex = str(package.get("latex") or "").strip()
    block = str(package.get("markdown_block") or "").strip()
    if block:
        environments = _FORMULA_ENVIRONMENT_RE.findall(block)
        if environments:
            return "\n\n".join(environments)
    if latex:
        return f"$$\n{latex}\n$$"
    return ""


def _paste_missing_formula_blocks(
    markdown: str,
    packages: Iterable[Mapping[str, Any]] | None,
) -> str:
    """Harness-insert Formalizer display math when the Writer paraphrased it."""

    text = _repair_writer_text_commands(markdown)
    for package in packages or ():
        if not isinstance(package, Mapping):
            continue
        latex = str(package.get("latex") or "").strip()
        if is_bare_binary_expression(latex):
            continue
        if _formula_package_rendered(text, package):
            continue
        if _formula_latex_already_in_prose(text, package):
            continue
        block = _formula_display_math(package)
        if not block:
            continue
        text = text.rstrip() + "\n\n" + block + "\n"
    return text


def _with_normalized_section_markdown(
    output: PublicationMethodSectionOutputV1 | None,
    *,
    expected_heading: str,
    formula_packages: Iterable[Mapping[str, Any]] | None = None,
    paragraph_plan: Iterable[Mapping[str, Any]] | None = None,
) -> PublicationMethodSectionOutputV1 | None:
    """Write heading-break normalization back onto the stored output."""

    if output is None:
        return None
    normalized = _normalize_section_heading_breaks(
        output.section_markdown,
        expected_heading=expected_heading,
    )
    normalized = _strip_provenance_tokens(normalized)
    before_paste = normalized
    # When a paragraph plan is present, formula placement belongs to the
    # Writer's paragraph transaction.  The harness may repair representation
    # noise, but must not append a missing display block at the section tail
    # and thereby hide a formula/consumer mismatch.  Legacy callers without a
    # plan retain the representation-only paste compatibility path.
    pasted = (
        _paste_missing_formula_blocks(normalized, formula_packages)
        if paragraph_plan is None
        else normalized
    )
    if (
        pasted != before_paste
        and _prose_has_repeated_phrase_spam(pasted)
        and not _prose_has_repeated_phrase_spam(before_paste)
    ):
        normalized = before_paste
    else:
        normalized = pasted
    updates: dict[str, Any] = {}
    rendered_package_ids = list(dict.fromkeys(
        [str(value) for value in (output.used_formula_package_ids or ()) if str(value).strip()]
        + [
            str(package.get("package_id") or "")
            for package in (formula_packages or ())
            if isinstance(package, Mapping)
            and str(package.get("package_id") or "").strip()
            and _formula_package_rendered(normalized, package)
        ]
    ))
    if rendered_package_ids != list(output.used_formula_package_ids):
        updates["used_formula_package_ids"] = rendered_package_ids
    rendered_equation_ids = list(dict.fromkeys(
        [str(value) for value in (output.used_equation_ids or ()) if str(value).strip()]
        + [
            str(equation_id)
            for package in (formula_packages or ())
            if isinstance(package, Mapping)
            and str(package.get("package_id") or "") in rendered_package_ids
            for equation_id in (package.get("bound_equation_ids") or ())
            if str(equation_id).strip()
        ]
    ))
    if rendered_equation_ids != list(output.used_equation_ids):
        updates["used_equation_ids"] = rendered_equation_ids
    if normalized != output.section_markdown:
        updates["section_markdown"] = normalized
    if updates:
        return output.model_copy(update=updates)
    return output



def _strip_heading_fence_junk(markdown: str, expected_phrase: str) -> str:
    """Drop a trailing backtick fence glued to the plan heading."""

    phrase = str(expected_phrase or "").strip()
    if not phrase:
        return markdown
    lines = str(markdown or "").splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        rest = stripped.lstrip("#").strip()
        if not rest.casefold().startswith(phrase.casefold()):
            continue
        tail = rest[len(phrase):]
        if tail.startswith("`"):
            lines[index] = f"## {phrase}"
            return chr(10).join(lines)
        break
    return markdown


def _rejoin_wrapped_expected_heading(markdown: str, expected_phrase: str) -> str:
    """Join a heading that the Writer wrapped onto the next line.

    Representation-only: a plan heading split after ``and`` onto the next
    line is not two semantic blocks.
    """

    phrase = str(expected_phrase or "").strip()
    if not phrase:
        return markdown
    expected_fold = " ".join(phrase.split()).casefold()
    lines = str(markdown or "").splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        head = stripped.lstrip("#").strip()
        head_fold = " ".join(head.split()).casefold()
        if not expected_fold.startswith(head_fold) or head_fold == expected_fold:
            continue
        cursor = index + 1
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        if cursor >= len(lines):
            break
        nxt = lines[cursor].strip()
        nxt_fold = " ".join(nxt.split()).casefold()
        rest_fold = expected_fold[len(head_fold):].strip()
        if not rest_fold or not nxt_fold.startswith(rest_fold):
            continue
        rest_words = rest_fold.split()
        nxt_words = nxt.split()
        leftover = " ".join(nxt_words[len(rest_words):]).lstrip(" ,;:")
        rebuilt = lines[:index] + [f"## {phrase}", ""]
        if leftover:
            rebuilt.append(leftover)
        rebuilt.extend(lines[cursor + 1:])
        return "\n".join(rebuilt)
    return markdown


def _normalize_section_heading_breaks(markdown: str, *, expected_heading: str = "") -> str:
    """Ensure a markdown heading is followed by a line break.

    Representation-only normalization: when a writer response puts the
    first body sentence on the same line as its ``#`` heading, the
    sentence-level extractor would classify the whole line as a heading
    and no factual claim would be validated.  Splitting the heading onto
    its own line changes no wording and no semantics.

    A fused line looks like ``## Heading  Sentence text...`` (the writer
    separates heading and body with two spaces, or the body begins with
    a capitalised long clause).  Clean ``## Heading`` lines are untouched.

    HTML block tags (``<br>``, ``<p>``) are representation-only noise:
    convert them to newlines before splitting so a fused
    ``## Heading<p>Body`` line becomes a real heading plus body
    (LinearRAG 071734 MA-S2 used a glued ``p>`` residue).

    When ``expected_heading`` is supplied (the Architect's heading for
    this section, which the Writer is instructed to copy verbatim), the
    split happens at that exact known boundary even when the writer fused
    the body to the heading without any whitespace (e.g.
    ``## Transformation and outputScale values undergo sorting...`` with
    expected heading ``Transformation and output``).  A ``## `` prefix on
    ``expected_heading`` is ignored.  The generic whitespace heuristic
    alone cannot recover the no-space case, and leaving it fused lets the
    extractor treat a whole factual paragraph as a heading.
    """

    markdown = _normalize_writer_representation_noise(str(markdown or ""))
    markdown = _collapse_repeated_inline_code_if_body_remains(markdown)
    markdown = _collapse_repeated_parentheticals_if_body_remains(markdown)
    markdown = _strip_empty_parentheticals_left_by_collapse(markdown)
    expected_phrase = _canonical_section_heading_phrase(expected_heading)
    expected = expected_phrase.casefold()
    markdown = _rejoin_wrapped_expected_heading(markdown, expected_phrase)
    markdown = _strip_heading_fence_junk(markdown, expected_phrase)

    def _split_at_expected(stripped: str) -> tuple[str, str] | None:
        if not expected or not stripped.startswith("#"):
            return None
        # Strip every leading hash/space so ``heading_text`` values that
        # include ``## `` still match the Architect phrase.
        rest = stripped.lstrip("#").strip()
        rest_norm = " ".join(rest.split()).casefold()
        if not rest_norm.startswith(expected):
            return None
        if rest[: len(expected_phrase)].casefold() != expected_phrase.casefold():
            return None
        remainder = rest[len(expected_phrase):].lstrip()
        if not remainder:
            return None
        if remainder.startswith("."):
            leftover = remainder[1:].lstrip()
            if leftover and leftover[0].isupper():
                return rest[: len(expected_phrase)], leftover
        glued = _GLUED_HTML_RESIDUE_RE.match(remainder)
        if glued is not None:
            leftover = glued.group(1).lstrip()
            if leftover:
                return rest[: len(expected_phrase)], leftover
        # Providers occasionally close the heading with Markdown emphasis and
        # glue the body directly after it (``## Heading**Body``).  This is a
        # representation defect, not a content defect; remove only the marker
        # and retain the body bytes for downstream validation.
        if remainder.startswith("**") or remainder.startswith("__"):
            leftover = remainder[2:].lstrip()
            if leftover:
                return rest[: len(expected_phrase)], leftover
        if remainder[0].isupper():
            return rest[: len(expected_phrase)], remainder
        # Fused body may start with a parenthetical or inline-code guard
        # before the first sentence (LinearRAG 125126 MA-S3).  Repeated
        # heading debris such as ``.## Output interface.## …`` must stay
        # headings-only so the Writer retry still fires.  A later ``###``
        # subsection in the same fused line is body, not debris.
        if re.match(r"\.?##[^#]", remainder):
            return None
        if remainder[0] in {"(", "`"} and (
            re.search(r"[)`]\s+[A-Z][A-Za-z]", remainder) is not None
            or (
                re.search(r"\s[A-Z][A-Za-z]", remainder) is not None
                and len(re.findall(r"[A-Za-z]{3,}", remainder)) >= 12
            )
        ):
            return rest[: len(expected_phrase)], remainder
        return None

    lines = markdown.splitlines()
    if not lines:
        return markdown
    normalized: list[str] = []
    for line in lines:
        stripped = line.strip()
        expected_split = _split_at_expected(stripped)
        if expected_split is not None:
            head, remainder = expected_split
            normalized.append(f"## {head}")
            normalized.append("")
            normalized.append(remainder)
            continue
        match = re.match(r"(#{1,6}\s+\S[^.]*?)(?:\s{2,}|\s)([A-Z][^#].*)", stripped)
        if match is not None and len(match.group(2).split()) > 3:
            head = match.group(1).rstrip()
            rest = match.group(2).strip()
            if rest.endswith((".", "!", "?")):
                normalized.append(head)
                normalized.append("")
                normalized.append(rest)
                continue
        normalized.append(line)
    return "\n".join(normalized)


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
    propositions: MethodPropositionSetV1 | None = None,
    concept_cards: Any | None = None,
    argument_briefs: Any | None = None,
    argument_facets: tuple[Any, ...] | list[Any] = (),
    facet_alignments: tuple[Any, ...] | list[Any] = (),
    facet_policies: tuple[Any, ...] | list[Any] = (),
    formula_packages_by_section: dict[str, tuple[dict[str, Any], ...]] | None = None,
    formula_obligations_by_section: dict[str, tuple[dict[str, Any], ...]] | None = None,
    exclude_audit_only_concepts: bool = True,
    audit_override_concept_keys: frozenset[str] = frozenset(),
    audit_only_claim_ids: set[str] | frozenset[str] | None = None,
    story_spine_nodes: tuple[Any, ...] | list[Any] = (),
) -> list[WriterSectionInput]:
    """Build the Writer-facing projection for each planned section.

    The projection is derived from the Architect's persisted typed semantic
    frames and move authority proofs — the Writer never re-derives a frame.
    ``argument_flow`` carries the closed typed frames (subject, predicate,
    every operand, conditions, edges) and ``validation_constraints`` carries
    the exact canonical wording/qualifier/formula/config tokens that the
    reverse validator enforces; the constraints are NOT a sentence plan.

    When ``concept_cards`` (``MethodConceptCardSetV1``) is supplied, each
    section's WriterView is built from Stage 2/3 concept cards (positive =
    repository-supported, caveated = author-intent/partial) instead of raw
    propositions; the proposition layer is then omitted for that section.
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
            "paragraphs": [
                {
                    "paragraph_id": paragraph.get("paragraph_id", ""),
                    "paragraph_role": paragraph.get("paragraph_role", "step_sequence"),
                    "argument_unit_ids": list(paragraph.get("argument_unit_ids") or ()),
                    "required_facet_ids": list(paragraph.get("required_facet_ids") or ()),
                    "ordered_semantic_slot_ids": list(
                        paragraph.get("ordered_semantic_slot_ids") or ()
                    ),
                    "required_edge_ids": list(paragraph.get("required_edge_ids") or ()),
                    "formula_obligation_ids": list(
                        paragraph.get("formula_obligation_ids") or ()
                    ),
                    "expected_sentence_range": list(
                        paragraph.get("expected_sentence_range") or (1, 4)
                    ),
                    "transition_from": paragraph.get("transition_from", ""),
                    "transition_to": paragraph.get("transition_to", ""),
                }
                for paragraph in (raw.get("paragraphs") or ())
                if isinstance(paragraph, dict)
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
            "brief_ids": list(raw.get("brief_ids") or ()),
            "verified_brief_ids": list(raw.get("verified_brief_ids") or ()),
            "caveated_brief_ids": list(raw.get("caveated_brief_ids") or ()),
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
            "inference_level": raw.get("inference_level", "E0"),
            "parent_claim_ids": list(raw.get("parent_claim_ids") or ()),
            "math_op_kind": raw.get("math_op_kind", ""),
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
            "formula_role": raw.get("formula_role", "publication_candidate"),
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
                "formula_role": item.get("formula_role", "publication_candidate"),
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
    proposition_by_id = {
        item.proposition_id: item
        for item in (propositions.propositions if propositions is not None else ())
    }
    callback_requests = {
        request.request_id: request
        for request in (callback_bundle.requests if callback_bundle is not None else ())
    }
    proofs_by_key = plan.proofs_by_key()
    story_by_id: dict[str, Any] = {}
    for node in story_spine_nodes:
        if isinstance(node, dict):
            story_id = str(node.get("story_node_id") or "")
            if story_id:
                story_by_id[story_id] = node
            continue
        story_id = str(getattr(node, "story_node_id", "") or "")
        if story_id:
            story_by_id[story_id] = node
    heading_to_claim_ids = {
        graph.heading: {
            claim_id
            for unit_id in graph.argument_unit_ids
            if unit_id in unit_by_id
            for claim_id in unit_by_id[unit_id].claim_ids
        }
        for graph in plan.sections
    }
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
        section_propositions = [
            proposition_by_id[proposition_id]
            for unit in units
            for proposition_id in (unit.proposition_order or unit.proposition_ids)
            if proposition_id in proposition_by_id
        ]
        # Stage 4 concept layer: when the Architect bound concept cards to
        # this section's units, the WriterView is built from those cards
        # (positive = repository-supported, caveated = author-intent/
        # partial) instead of raw propositions.
        section_concepts: list[Any] = []
        section_briefs: list[Any] = []
        concept_binding_by_key: dict[str, Any] = {}
        brief_by_id: dict[str, Any] = {}
        if argument_briefs is not None:
            brief_by_id = {
                item.brief_id: item
                for item in (getattr(argument_briefs, "briefs", ()) or ())
            }
            section_briefs = [
                brief_by_id[brief_id]
                for unit in units
                for brief_id in (unit.brief_order or unit.brief_ids)
                if brief_id in brief_by_id
            ]
        section_brief_ids = {brief.brief_id for brief in section_briefs}
        section_facets = [
            facet
            for facet in argument_facets
            if not getattr(facet, "brief_id", "")
            or facet.brief_id in section_brief_ids
        ]
        section_facet_ids = {facet.facet_id for facet in section_facets}
        section_facet_alignments = [
            alignment
            for alignment in facet_alignments
            if alignment.facet_id in section_facet_ids
        ]
        section_facet_policies = [
            policy
            for policy in facet_policies
            if policy.facet_id in section_facet_ids
        ]
        if concept_cards is not None and not section_briefs:
            concept_by_key = {
                item.concept_key: item
                for item in (getattr(concept_cards, "cards", ()) or ())
            }
            concept_binding_by_key = {
                item.concept_key: item
                for item in (getattr(concept_cards, "bindings", ()) or ())
            }
            section_concepts = [
                concept_by_key[concept_key]
                for unit in units
                for concept_key in (
                    unit.concept_card_order or unit.concept_card_ids
                )
                if concept_key in concept_by_key
            ]
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
        section_paragraphs = [
            paragraph.model_dump(mode="json")
            for paragraph in (getattr(graph, "paragraphs", ()) or ())
        ]
        if not section_paragraphs:
            # Backward-compatible projection for frozen plans created before
            # paragraph contracts existed: retain move order as a minimal
            # organization plan without fabricating semantic slots.
            section_paragraphs = [
                {
                    "paragraph_id": f"paragraph:{graph.section_id}:{index}",
                    "paragraph_role": "overview" if index == 1 else "step_sequence",
                    "argument_unit_ids": list(move.argument_unit_ids or graph.argument_unit_ids),
                    "required_facet_ids": [],
                    "ordered_semantic_slot_ids": [],
                    "required_edge_ids": [],
                    "formula_obligation_ids": [],
                    "expected_sentence_range": [1, 4],
                    "transition_from": "",
                    "transition_to": "",
                }
                for index, move in enumerate(
                    (move for move in graph.moves if move.move != "transition_to_next_section"),
                    start=1,
                )
            ]
        required_section_facets = [
            facet
            for facet in section_facets
            if _facet_required_for_section(
                facet,
                {str(value) for value in graph.primary_brief_ids if str(value).strip()},
            )
        ]
        if required_section_facets and section_paragraphs:
            # Bind each required facet to the paragraph whose argument unit
            # carries its brief.  Formula facets prefer the final formula
            # paragraph, so the Formalizer and Writer share the same consumer
            # rather than attaching every facet to paragraph one.
            unit_briefs = {
                str(unit.argument_unit_id): {
                    str(value)
                    for value in (
                        getattr(unit, "brief_order", ())
                        or getattr(unit, "brief_ids", ())
                        or ()
                    )
                    if str(value).strip()
                }
                for unit in units
            }
            for facet in required_section_facets:
                facet_id = str(facet.facet_id)
                # The Architect's paragraph contract is the authoritative
                # placement.  Do not collapse an already precise
                # facet→paragraph binding onto the last paragraph merely
                # because this legacy projection also knows the facet's
                # brief.  The fallback below is only for frozen plans that
                # predate paragraph facet bindings.
                if any(
                    facet_id in (paragraph.get("required_facet_ids") or ())
                    for paragraph in section_paragraphs
                ):
                    continue
                facet_brief_id = str(getattr(facet, "brief_id", "") or "")
                candidate_indexes = [
                    index
                    for index, paragraph in enumerate(section_paragraphs)
                    if facet_brief_id
                    and any(
                        facet_brief_id in unit_briefs.get(str(unit_id), set())
                        for unit_id in (paragraph.get("argument_unit_ids") or ())
                    )
                ]
                if str(getattr(facet, "facet_kind", "") or "") == "formula":
                    formula_indexes = [
                        index
                        for index, paragraph in enumerate(section_paragraphs)
                        if str(paragraph.get("paragraph_role") or "") == "formula"
                    ]
                    if formula_indexes:
                        candidate_indexes = formula_indexes
                target_index = candidate_indexes[-1] if candidate_indexes else 0
                target = section_paragraphs[target_index]
                target["required_facet_ids"] = list(dict.fromkeys([
                    *(target.get("required_facet_ids") or ()),
                    facet_id,
                ]))
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
                "unanchored": bool(getattr(move, "unanchored", False)),
                "unanchored_owner": str(getattr(move, "unanchored_owner", "") or ""),
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
                    section_concepts=section_concepts,
                ),
            }
        writer_graph = writer_graph_payload(graph)
        writer_claims = [
            writer_claim_payload(claim_by_id[item])
            for item in claim_ids
            if item in claim_by_id
            and item not in (audit_only_claim_ids or ())
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
                and item["formula_role"] != "incidental"
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
            if value["state"] in {"open", "external_pending"}
            and (
                value["required"]
                or value.get("unanchored")
                or name in _UNANCHORED_OWNER_CALLBACK_MOVES
            )
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

        brief_callback_payload = (
            _brief_callback_prototype_payload(section_briefs=section_briefs)
            if section_briefs else {}
        )
        concept_callback_payload = (
            _concept_callback_prototype_payload(
                section_concepts=section_concepts,
                concept_bindings=concept_binding_by_key,
            )
            if section_concepts and not brief_callback_payload else {}
        )
        shared_callback_payload = brief_callback_payload or concept_callback_payload
        callback_request_prototypes = [
            {
                **shared_callback_payload,
                "request_id": f"request:{graph.section_id}:{move_name}",
                "section_id": graph.section_id,
                "argument_unit_id": callback_argument_unit_id(move_name),
                "missing_rhetorical_move": move_name,
                "exact_question": (
                    shared_callback_payload.get("exact_question")
                    or (
                        "Replace this with one precise missing-information "
                        "question needed to write the unresolved move."
                    )
                ),
                "required_authority_lane": str(
                    move_authority[move_name].get("required_authority_lane") or ""
                ),
                "candidate_symbols_or_terms": list(
                    move_authority[move_name].get("candidate_symbols_or_terms")
                    or shared_callback_payload.get("candidate_symbols_or_terms")
                    or ()
                ),
                "current_known_facts": [],
                "why_needed_for_reader": (
                    shared_callback_payload.get("why_needed_for_reader")
                    or (
                        "The section has a required move that lacks an "
                        "authorized factual anchor. Write author-specification "
                        "prose in parallel with this directed search."
                    )
                ),
                "priority": "high",
                "status": "open",
            }
            for move_name in unanchored_required_moves
            if move_name in move_authority
        ]
        if brief_callback_payload and not any(
            prototype.get("brief_binding") for prototype in callback_request_prototypes
        ):
            brief_callback_move = next(
                (
                    move_name
                    for move_name in (
                        *unanchored_required_moves,
                        *required_moves,
                        *(move.move for move in graph.moves),
                    )
                    if move_name in {move.move for move in graph.moves}
                ),
                "",
            )
            if not brief_callback_move:
                raise ValueError(
                    f"brief callback for section {graph.section_id} has no real section move"
                )
            callback_request_prototypes.append({
                "request_id": f"request:{graph.section_id}:brief_slots",
                "section_id": graph.section_id,
                "argument_unit_id": callback_argument_unit_id(
                    brief_callback_move
                ),
                # A callback must bind to an actual move in this section.  A
                # synthetic empty/section-global move cannot be fulfilled by the
                # research router and must never reach the Writer schema.
                "missing_rhetorical_move": brief_callback_move,
                "exact_question": brief_callback_payload.get(
                    "exact_question",
                    "Which repository evidence resolves the unlicensed brief slots?",
                ),
                "required_authority_lane": "executable_hard",
                "candidate_symbols_or_terms": list(
                    brief_callback_payload.get("candidate_symbols_or_terms") or ()
                ),
                "current_known_facts": [],
                "why_needed_for_reader": brief_callback_payload.get(
                    "why_needed_for_reader",
                    "Directed repository search for unlicensed author-mechanism "
                    "fields. Keep writing the full author-logic Candidate as "
                    "author specification in parallel.",
                ),
                "priority": "high",
                "status": "open",
                **brief_callback_payload,
            })
        brief_callback_required = bool(brief_callback_payload)
        callback_required = bool(
            unanchored_required_moves or brief_callback_required
        )
        for truth in (
            formula_obligations_by_section.get(graph.section_id, ())
            if formula_obligations_by_section else ()
        ):
            if "equation_or_derivation" not in unanchored_required_moves:
                break
            if str(truth.get("outcome") or "") != "unresolved":
                continue
            obligation_id = str(truth.get("obligation_id") or "").strip()
            if not obligation_id:
                continue
            callback_request_prototypes.append({
                "request_id": f"request:{graph.section_id}:formula:{obligation_id}",
                "section_id": graph.section_id,
                "argument_unit_id": callback_argument_unit_id("equation_or_derivation"),
                "missing_rhetorical_move": "equation_or_derivation",
                "exact_question": str(
                    truth.get("review_question")
                    or "Which repository evidence binds this section formula obligation?"
                ),
                "required_authority_lane": "formal_derivation",
                "candidate_symbols_or_terms": [],
                "current_known_facts": [],
                "why_needed_for_reader": (
                    "An unresolved formula obligation must be rendered or "
                    "kept as a typed formula slot, not a generic limitation."
                ),
                "priority": "high",
                "status": "open",
                "mandatory_missing_slots": ["formula"],
                "target_formula_obligation_ids": [obligation_id],
            })
        for prototype in callback_request_prototypes:
            if prototype.get("candidate_symbols_or_terms"):
                continue
            prototype["candidate_symbols_or_terms"] = list(
                directed_search_terms_from_texts(
                    *(prototype.get("missing_parts") or ()),
                )
            )
            question = str(prototype.get("exact_question") or "")
            if (
                prototype["candidate_symbols_or_terms"]
                and "which repository evidence" in question.casefold()
            ):
                prototype["exact_question"] = directed_callback_question(
                    prototype["candidate_symbols_or_terms"]
                )
        writer_view = None
        if section_briefs:
            from code2paper.agentic.writer_view_projection import (
                build_writer_view_from_argument_briefs,
            )

            writer_view = build_writer_view_from_argument_briefs(
                heading=graph.heading,
                reader_question=graph.reader_question,
                section_goal="; ".join(
                    str(unit.design_objective).strip()
                    for unit in units if str(unit.design_objective).strip()
                ),
                briefs=section_briefs,
                callback_opportunities=callback_request_prototypes,
                primary_brief_ids=tuple(graph.primary_brief_ids),
                supporting_brief_ids=tuple(graph.supporting_brief_ids),
                claims_by_id=claim_by_id,
                facts_by_id=fact_by_id,
                heading_to_claim_ids=heading_to_claim_ids,
                facets=tuple(section_facets),
                facet_alignments=tuple(section_facet_alignments),
                facet_policies=tuple(section_facet_policies),
                formula_packages=tuple(
                    formula_packages_by_section.get(graph.section_id, ())
                    if formula_packages_by_section else ()
                ),
                required_facet_ids=tuple(
                    facet.facet_id
                    for facet in section_facets
                    if _facet_required_for_section(
                        facet,
                        {
                            str(value)
                            for value in graph.primary_brief_ids
                            if str(value).strip()
                        },
                    )
                ),
                organization_seed="; ".join(
                    str(getattr(brief.mechanism_draft, "text", "") or "").strip()
                    for brief in section_briefs
                    if str(getattr(brief.mechanism_draft, "text", "") or "").strip()
                ),
            )
        elif section_concepts:
            from code2paper.agentic.writer_view_projection import (
                build_writer_view_from_concept_cards,
            )

            story_nodes_for_section = tuple(
                story_by_id[story_id]
                for story_id in graph.story_node_ids
                if story_id in story_by_id
            )
            writer_view = build_writer_view_from_concept_cards(
                heading=graph.heading,
                reader_question=graph.reader_question,
                section_goal="; ".join(
                    str(unit.design_objective).strip()
                    for unit in units if str(unit.design_objective).strip()
                ),
                cards=section_concepts,
                callback_opportunities=callback_request_prototypes,
                exclude_audit_only=exclude_audit_only_concepts,
                audit_override_concept_keys=audit_override_concept_keys,
                primary_concept_keys=tuple(graph.primary_concept_keys),
                supporting_concept_keys=tuple(graph.supporting_concept_keys),
                audit_only_concept_keys=tuple(graph.audit_only_concept_keys),
                story_nodes=story_nodes_for_section,
            )
        elif propositions is not None:
            writer_view = build_writer_view(
                heading=graph.heading,
                reader_question=graph.reader_question,
                section_goal="; ".join(
                    str(unit.design_objective).strip()
                    for unit in units if str(unit.design_objective).strip()
                ),
                propositions=section_propositions,
                callback_opportunities=callback_request_prototypes,
                configuration_values_by_proposition={
                    proposition.proposition_id: tuple(
                        f"{configuration_by_id[item].key}={configuration_by_id[item].value}"
                        for item in proposition.required_configuration_ids
                        if item in configuration_by_id
                    )
                    for proposition in section_propositions
                },
            )
        licensed_l2 = tuple(
            getattr(writer_view, "technical_propositions", ()) or ()
            if writer_view is not None else ()
        )
        if licensed_l2:
            existing_claim_ids = {item["claim_id"] for item in writer_claims}
            existing_reader_ids = {
                str(item.get("claim_id") or "") for item in reader_facing_claims
            }
            for item in licensed_l2:
                claim_id = str(item.proposition_id)
                claim = claim_by_id.get(claim_id)
                if claim is None:
                    continue
                if claim_id not in existing_claim_ids:
                    writer_claims.append(writer_claim_payload(claim))
                    existing_claim_ids.add(claim_id)
                if claim_id not in existing_reader_ids:
                    obligation_id = next(
                        iter(getattr(claim, "covers_obligation_ids", ()) or ("",)),
                        "",
                    )
                    reader_facing_claims.append({
                        "claim_id": claim_id,
                        "obligation_id": obligation_id,
                        "section_id": graph.section_id,
                        "lane": "repository_partial",
                        "paper_statement": str(item.transformation or "").strip(),
                        "code_binding_terms": extract_code_binding_terms(
                            str(getattr(claim, "canonical_text", "") or "")
                        ),
                        "required_qualifiers": tuple(
                            getattr(claim, "required_qualifiers", ()) or ()
                        ),
                        "may_enter_verified": False,
                        "requires_caveat": False,
                    })
                    existing_reader_ids.add(claim_id)
            callback_request_prototypes = [
                prototype for prototype in callback_request_prototypes
                if str(prototype.get("required_authority_lane") or "") != "expository_bridge"
                and str(prototype.get("missing_rhetorical_move") or "") != "expository_bridge"
            ]
            callback_required = bool(
                unanchored_required_moves or callback_request_prototypes
            )
        # Paragraph transactions are the production contract for the
        # intent-first (brief/facet or concept-card) lane.  Frozen
        # proposition-only replays predate that contract and intentionally
        # retain the legacy section_markdown path so their checkpoints remain
        # readable; the presence of the typed authoring layer is the explicit
        # capability marker rather than the synthetic fallback paragraph plan.
        paragraph_transactions_enabled = bool(
            section_paragraphs
            and (
                argument_briefs is not None
                or bool(argument_facets)
                or concept_cards is not None
            )
        )
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
                "formula_packages": list(
                    formula_packages_by_section.get(graph.section_id, ())
                    if formula_packages_by_section else (),
                ),
                "formula_obligations": list(
                    formula_obligations_by_section.get(graph.section_id, ())
                    if formula_obligations_by_section else (),
                ),
                "mechanism_section": _mechanism_section_payload(
                    graph=graph,
                    writer_view=writer_view,
                    formula_packages=tuple(
                        formula_packages_by_section.get(graph.section_id, ())
                        if formula_packages_by_section else ()
                    ),
                    formula_obligations=tuple(
                        formula_obligations_by_section.get(graph.section_id, ())
                        if formula_obligations_by_section else ()
                    ),
                ),
                "argument_flow": {
                    "semantic_frames": section_frames,
                    "frame_digests": section_frame_digests,
                },
                "paragraph_plan": section_paragraphs,
                "paragraph_transaction_required": paragraph_transactions_enabled,
                "validation_constraints": validation_constraints,
                "reader_facing_claims": reader_facing_claims,
                "section_candidate_points": section_candidate_points,
                "paper_term_hints": [
                    item["paper_statement"] for item in reader_facing_claims
                    if item["paper_statement"].strip()
                ],
                **({"writer_view": writer_view.model_dump(mode="json")} if writer_view is not None else {}),
                **({"argument_briefs": [
                    {
                        "brief_id": brief.brief_id,
                        "licensed_wording": brief.licensed_wording,
                        "unlicensed_clauses": [
                            {
                                "clause_id": clause.clause_id,
                                "text": clause.text,
                                "license": clause.license,
                            }
                            for clause in brief.clauses
                            if clause.license in {"unlicensed", "partially_licensed"}
                        ],
                        "mechanism_draft": brief.mechanism_draft.text,
                        "claim_texts": [
                            claim_by_id[claim_id].canonical_text
                            for claim_id in brief.claim_ids
                            if claim_id in claim_by_id
                        ],
                    }
                    for brief in section_briefs
                ]} if section_briefs else {}),
                "required_rhetorical_moves": list(required_moves),
                "anchored_required_moves": anchored_required_moves,
                "unanchored_required_moves": unanchored_required_moves,
                "expository_bridge_required_moves": expository_bridge_required_moves,
                "callback_required": callback_required,
                "response_protocol": {
                    "write_only_anchored_required_moves": True,
                    "combine_anchors_into_connected_operations": True,
                    "claim_free_expository_bridge_allowed": not bool(licensed_l2),
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
                            **({
                                "target_brief_ids": (
                                    "copy callback_request_prototypes[].target_brief_ids"
                                ),
                                "target_clause_ids": (
                                    "copy callback_request_prototypes[].target_clause_ids"
                                ),
                                "missing_parts": (
                                    "copy the matching brief_binding[].missing_parts list"
                                ),
                                "evidence_refs_used": (
                                    "copy the matching brief_binding[].evidence_refs_used list"
                                ),
                            } if any(
                                item.get("brief_binding") for item in callback_request_prototypes
                            ) else {
                                "concept_key": "one concept key from callback_request_prototypes[].concept_binding",
                                "missing_parts": "copy the matching concept_binding[].missing_parts list",
                                "evidence_refs_used": "copy the matching concept_binding[].evidence_refs_used list",
                            } if any(
                                item.get("concept_binding") for item in callback_request_prototypes
                            ) else {}),
                        },
                        "callback_request_prototypes": callback_request_prototypes,
                    } if callback_required else {}),
                },
                "content_first_instruction": (
                    (
                        "Use paragraph_plan as the only organization skeleton. "
                        "Return one paragraphs item for every paragraph_plan row. "
                        "Each item must contain only that paragraph's substantive "
                        "Markdown and exact witness strings for every rendered facet, "
                        "slot, edge, formula package, claim, or equation id. The "
                        "harness assembles section_markdown from these transactions; "
                        "do not use a single section paragraph to stand in for several "
                        "planned paragraphs. A witness must occur exactly once in its "
                        "paragraph text. "
                        "Use writer_view and its facet policies to decide the "
                        "author-intent scope and caveat mode, but use the supplied "
                        "argument_flow semantic frames as the only repository fact "
                        "source. For each paragraph plan, preserve its ordered "
                        "semantic slots and write one connected operation flow; "
                        "do not flatten all plans into one paragraph. Render each "
                        "positive_briefs.licensed_wording entry as a normal Method "
                        "sentence in reader language without expanding beyond its "
                        "bound claim ids. Render each caveated_briefs entry as a "
                        "substantive intended or partial Method sentence with its "
                        "required caveat visible; never emit empty pending shells or "
                        "repeat bare caveat tokens such as (intended) without "
                        "mechanism content. Rewrite each mechanism_drafts entry into "
                        "reader-facing prose while preserving cited claim meaning and "
                        "any draft caveat. Use evidence_claim_texts only to align "
                        "factual mechanism sentences with closed-set repository claims; "
                        "never paste L0 canonical_text verbatim as publication prose. "
                        "technical_propositions are licensed E2/E3 effects: render them "
                        "as Method sentences, put identifiers in parentheses, and do "
                        "not ask for repository-authorized propositions when they are "
                        "present. Effect expansion is allowed only for listed "
                        "technical_propositions; polarity must match parent comparisons. "
                        "E4 claims (unstated percents, outperformance) are forbidden. "
                        "Primary brief ids in required_brief_ids must appear in "
                        "rendered_brief_ids; deferred_brief_ids are only for "
                        "supporting briefs explicitly omitted from this section. "
                        "Never place every primary brief into deferred_brief_ids. "
                        + (
                            "The mechanism_authoring_packet is the primary "
                            "mechanism contract. Follow its story order from "
                            "motivation/problem through mechanism, notation or "
                            "formula, algorithm/interface, and output. For every "
                            "required_facet_id, write substantive mechanism content "
                            "authorized by that facet's prose_mode and report the "
                            "exact id in rendered_from_facet_ids. Do not satisfy "
                            "facet coverage with a bare 'pending', 'intended', "
                            "'partial', or 'pending confirmation' token; a caveat "
                            "may qualify a substantive sentence but may not replace "
                            "it. Do not copy planner text or frag ids verbatim: "
                            "digest the planner_filled draft as an organization seed "
                            "and rewrite it in academic Method language. Keep "
                            "repository_statement, author_specification, and "
                            "mismatch_statement visibly distinct. Open callbacks "
                            "request directed repository search; they do not "
                            "authorize omitting required facets. Write the full "
                            "author-logic Candidate now as author specification "
                            "and keep the callback. If formula_packages is empty, "
                            "write the author specification in prose and put the "
                            "formula gap in review; never replace the mechanism "
                            "with a deferral such as 'no accepted formula' or "
                            "'therefore deferred'. If formula_packages is present, "
                            "embed each complete display-math environment beside "
                            "the mechanism and skip any truncated block or second "
                            "heading. "
                            "Do not copy brief:story: or obligation ids into prose. "
                            if section_facets else ""
                        )
                        + "Begin section_markdown with exactly one Markdown H2 heading "
                        "copied from the supplied heading field, then write substantive "
                        "Method body sentences."
                        + (
                            " When callback_request_prototypes carries brief_binding, "
                            "emit one callback with the listed target_brief_ids, "
                            "target_clause_ids, missing_parts, and evidence_refs_used."
                            if brief_callback_payload else ""
                        )
                    )
                    if section_briefs else
                    (
                        (
                            "Use paragraph_plan as the only organization skeleton. "
                            "Return one paragraphs item for every paragraph_plan row. "
                            "Each paragraph_markdown must be substantive body text "
                            "without a section H2 heading, and every rendered facet, "
                            "slot, edge, formula package, claim, or equation id must "
                            "have one exact witness occurring exactly once in that "
                            "paragraph. The harness assembles one section H2 and the "
                            "paragraphs in plan order; do not collapse multiple plan "
                            "rows into one transaction. "
                        )
                        if section_paragraphs else ""
                    )
                    + "Use writer_view as the only content plan. Answer purpose, "
                    "render positive_propositions as normal Method statements, and "
                    "render caveated_propositions as substantive intended/partial/"
                    "pending Method statements. When the view carries "
                    "positive_concepts/caveated_concepts instead (Stage 4 concept "
                    "cards), render each positive_concept's method_subject and "
                    "operation as one normal Method statement in reader language, "
                    "preserve its numeric_constraints/formula_constraints exactly, "
                    "and render each caveated_concept visibly caveated with its "
                    "candidate_caveat. Never emit an empty promise such as Pending "
                    "confirmation or We aim to explain. Write required moves listed in "
                    "anchored_required_moves and the "
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
                    "the required_qualifier_bindings list is the complete "
                    "section-scoped predicate authority even when the compact "
                    "validation_constraints claim projection omits a row; "
                    "do not preserve raw code token spelling unless it is the "
                    "paper-level term or an implementation-realization detail, and "
                    "never emit a constraint record itself as a sentence. An exact "
                    "required qualifier condition (for example `doc['chunk_id'] == "
                    "query['chunk_id']` or `loss_i.shape[0] == 0`) is a repository "
                    "predicate the validator must see verbatim: render it as "
                    "academic prose plus the exact predicate in ONE compact "
                    "parenthetical backtick binding, e.g. (when the chunk "
                    "identifiers match, `doc['chunk_id'] == query['chunk_id']`), "
                    "never as bare inline code. Write a "
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
                    "not factual evidence. "
                    + (
                        "The supplied heading is truncated mid-clause. "
                        "Shorten it to its last complete clause or complete it "
                        "into ONE coherent H2 heading line that ends at a "
                        "complete clause; never copy the broken tail verbatim "
                        "and never move the heading's remaining words into the "
                        "body: after the heading line, write the section's "
                        "first content sentence normally. "
                        if heading_is_truncated(graph.heading) else ""
                    )
                    + " Never "
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
                        "When callback_request_prototypes carries concept_binding, "
                        "copy one concept_key, its missing_parts, and its "
                        "evidence_refs_used into the request so the owning researcher "
                        "knows exactly which caveated concept to resolve.  Omitting the "
                        "request leaves the section incomplete: the harness never "
                        "manufactures a callback, and the section cannot be accepted "
                        "without one."
                        if unanchored_required_moves else ""
                    )
                    + "A move listed in grounding_contract.expository_bridge_allowed_moves "
                    "may instead be completed by one claim-free organization sentence "
                    "without a callback."
                    + (
                        " The mechanism_authoring_packet is an organization and "
                        "coverage contract, not an evidence shortcut: planner "
                        "drafts must be rewritten rather than copied, and every "
                        "required facet must be reported in rendered_from_facet_ids "
                        "after substantive prose covers it."
                        if section_facets else ""
                    )
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
                        "research_question", "moves",
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
                    "callback_required": callback_required,
                    **({
                        "callback_response_shape": {
                            "new_research_requests": callback_request_prototypes
                        }
                    } if callback_required else {}),
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
                    "allowed_proposition_ids": list(writer_view.allowed_proposition_ids) if writer_view is not None and getattr(writer_view, "allowed_proposition_ids", None) else [],
                    "required_proposition_ids": list(writer_view.required_proposition_ids) if writer_view is not None and getattr(writer_view, "required_proposition_ids", None) else [],
                    "allowed_concept_keys": list(writer_view.allowed_concept_keys) if writer_view is not None and getattr(writer_view, "allowed_concept_keys", None) else [],
                    "required_concept_keys": list(writer_view.required_concept_keys) if writer_view is not None and getattr(writer_view, "required_concept_keys", None) else [],
                    "allowed_brief_ids": list(writer_view.allowed_brief_ids) if writer_view is not None and getattr(writer_view, "allowed_brief_ids", None) else [],
                    "required_brief_ids": list(writer_view.required_brief_ids) if writer_view is not None and getattr(writer_view, "required_brief_ids", None) else [],
                    "allowed_facet_ids": list(
                        section_facet_ids
                    ),
                    "allowed_paragraph_ids": [
                        str(item.get("paragraph_id") or "")
                        for item in section_paragraphs
                        if str(item.get("paragraph_id") or "").strip()
                    ],
                    "allowed_slot_ids": [
                        str(slot_id)
                        for item in section_paragraphs
                        for slot_id in (item.get("ordered_semantic_slot_ids") or ())
                        if str(slot_id).strip()
                    ],
                    "allowed_edge_ids": [
                        str(edge_id)
                        for item in section_paragraphs
                        for edge_id in (item.get("required_edge_ids") or ())
                        if str(edge_id).strip()
                    ],
                    "allowed_formula_package_ids": [
                        str(item.get("package_id") or "")
                        for item in (
                            formula_packages_by_section.get(graph.section_id, ())
                            if formula_packages_by_section else ()
                        )
                        if str(item.get("package_id") or "").strip()
                    ],
                    "required_facet_ids": list(
                        facet.facet_id
                        for facet in section_facets
                        if _facet_required_for_section(
                            facet,
                            {
                                str(value)
                                for value in graph.primary_brief_ids
                                if str(value).strip()
                            },
                        )
                    ),
                    "primary_brief_ids": list(graph.primary_brief_ids),
                    "primary_concept_keys": list(graph.primary_concept_keys),
                    "required_rhetorical_moves": list(required_moves),
                    "completed_rhetorical_moves": anchored_required_moves,
                    "anchored_required_rhetorical_moves": anchored_required_moves,
                    "unanchored_required_rhetorical_moves": unanchored_required_moves,
                    "content_first": True,
                },
            },
        ))
    return result


def _writer_proposition_payload(proposition: Any) -> dict[str, Any]:
    """Reader-facing proposition surface; no claim/fact/span IDs."""

    return {
        "proposition_id": proposition.proposition_id,
        "authority_lane": proposition.evidence_lane,
        "reader_subject": proposition.reader_subject,
        "transformation": proposition.transformation,
        "inputs": list(proposition.inputs),
        "outputs": list(proposition.outputs),
        "conditions": list(proposition.conditions),
        "boundary": proposition.boundary,
        "paper_terms": list(proposition.paper_terms),
        "implementation_binding_terms": list(proposition.implementation_binding_terms),
        "required_qualifiers": list(proposition.required_qualifiers),
        "missing_or_uncertain_parts": list(proposition.missing_or_uncertain_parts),
    }


def _writer_immutable_constraints(
    propositions: Iterable[Any],
    *,
    equations: Iterable[Mapping[str, Any]],
    configurations: Iterable[Any],
) -> dict[str, Any]:
    return {
        "numeric_tokens": list(dict.fromkeys(
            token for item in propositions for token in item.immutable_numeric_tokens
        )),
        "formula_tokens": list(dict.fromkeys(
            token for item in propositions for token in item.immutable_formula_tokens
        )),
        "qualifiers": list(dict.fromkeys(
            qualifier for item in propositions for qualifier in item.required_qualifiers
        )),
        "equations": [
            {
                "equation_id": str(item.get("equation_id") or ""),
                "expression": str(item.get("concrete_expression") or item.get("expression") or ""),
                "conditions": list(item.get("conditions") or ()),
            }
            for item in equations
        ],
        "configurations": [
            {
                "configuration_id": item.configuration_id,
                "key": item.key,
                "value": item.value,
                "conditions": list(item.conditions),
            }
            for item in configurations
        ],
    }


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
            level = str(getattr(claim, "inference_level", "E0") or "E0")
            kind = str(getattr(claim, "claim_kind", "") or "")
            may_enter_verified = bool(
                supported
                and getattr(claim, "status", "") == "supported"
                and level in {"E0", "E1", ""}
                and kind != "technical_semantic"
            )
            claims_out.append({
                "claim_id": claim_id,
                "obligation_id": obligation_id,
                "section_id": graph.section_id,
                "lane": (
                    "repository_verified"
                    if may_enter_verified
                    else "repository_partial"
                    if getattr(claim, "status", "") == "partial" or level in {"E2", "E3"}
                    else "author_intent_unverified"
                ),
                "paper_statement": str(getattr(claim, "canonical_text", "") or "").strip(),
                "code_binding_terms": extract_code_binding_terms(
                    str(getattr(claim, "canonical_text", "") or "")
                ),
                "required_qualifiers": tuple(getattr(claim, "required_qualifiers", ()) or ()),
                "may_enter_verified": may_enter_verified,
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
    section_concepts: list[Any] | None = None,
) -> list[str]:
    """Exact search-term candidates for one move proof.

    Repository candidates are exact subjects, operands, and relation endpoints
    from the bound frames; configuration candidates are exact keys/IDs;
    formalization candidates are exact equation IDs and operands.  Claim IDs
    alone are never search terms.  In the concept lane, the reader-facing
    surface of the section's bound concept cards (subject, operation,
    inputs, outputs, conditions, known parts) also authorizes search terms —
    a caveated concept whose missing parts need repository evidence must be
    searchable even when its unit frame is thin.
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
    for card in (section_concepts or ()):
        candidates.extend(_concept_search_terms(card))
    if lane == "configuration_resolved":
        candidates.extend(str(item) for item in configuration_ids)
    if lane == "formal_derivation":
        candidates.extend(str(item) for item in equation_ids)
    return list(dict.fromkeys(item for item in candidates if str(item).strip()))


def _concept_search_terms(card: Any) -> list[str]:
    """Exact search-term candidates from one concept card's reader surface.

    The card's method_subject, operation, inputs, outputs, conditions, and
    known parts are the authorized vocabulary for researching its missing
    parts.  Claim IDs, concept keys, and internal refs are never search
    terms.
    """

    terms: list[str] = []
    for value in (
        getattr(card, "method_subject", "") or "",
        getattr(card, "operation", "") or "",
        *[str(item) for item in getattr(card, "inputs", ()) or ()],
        *[str(item) for item in getattr(card, "outputs", ()) or ()],
        *[str(item) for item in getattr(card, "conditions", ()) or ()],
        *[str(item) for item in getattr(card, "known_parts", ()) or ()],
    ):
        cleaned = str(value or "").strip()
        if cleaned:
            terms.append(cleaned)
    return terms


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


def _optional_unanchored_callback_moves(
    graph: Any,
    authority_proofs: dict[tuple[str, str], Any] | None,
) -> dict[str, Any]:
    """Typed unanchored obligations the Writer may callback without requiring them.

    W3 keeps ``equation_or_derivation`` (and similar) as ``required=False`` plus
    ``unanchored=True`` when the section has no equation evidence.  W7 still
    lets the Writer emit a Formalizer-owned request for that obligation; the
    missing callback is a quality/review item, not a Writer-retry contract.
    """

    optional: dict[str, Any] = {}
    for move in graph.moves or ():
        if getattr(move, "required", False):
            continue
        proof = (
            authority_proofs.get((graph.section_id, move.move))
            if authority_proofs is not None
            else None
        )
        if (
            bool(getattr(move, "unanchored", False))
            or bool(proof is not None and getattr(proof, "unanchored", False))
            or move.move in _UNANCHORED_OWNER_CALLBACK_MOVES
        ):
            optional[move.move] = move
    return optional


def _local_lane_candidates_ok(
    *,
    lane: str,
    requested: tuple[str, ...],
    authorized: set[str] | tuple[str, ...],
    unanchored: bool,
) -> bool:
    """Exact-candidate rule for locally owned callbacks.

    Anchored local lanes require at least one model-emitted candidate inside
    the authorized term set.  Unanchored Formalizer/Research obligations have
    no equation or configuration IDs to name yet, so an empty candidate list
    is the honest request; invented terms are still rejected.
    """

    if lane not in _LOCALLY_OWNED_LANES:
        return True
    requested_set = {str(item) for item in requested if str(item).strip()}
    authorized_set = {str(item) for item in authorized if str(item).strip()}
    if unanchored:
        if not requested_set:
            return True
        return bool(authorized_set) and requested_set.issubset(authorized_set)
    return bool(requested_set) and requested_set.issubset(authorized_set)


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
    concept_cards: Any | None = None,
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
    optional_unanchored = _optional_unanchored_callback_moves(graph, authority_proofs)
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
        move_spec = required_moves.get(move) or optional_unanchored.get(move)
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
        unanchored_proof = bool(
            (proof is not None and (
                getattr(proof, "unanchored", False)
                or getattr(proof, "state", "") in {"open", "external_pending"}
            ))
            or (move_spec is not None and getattr(move_spec, "unanchored", False))
        )
        candidate_binding_valid = True
        if request_lane in _LOCALLY_OWNED_LANES and move_spec is not None:
            try:
                typed_request = WritingResearchRequestV1.model_validate(raw)
            except (TypeError, ValueError):
                candidate_binding_valid = False
            else:
                allowed_candidates = set(_request_candidate_terms(
                    typed_request,
                    allowed_units=tuple(allowed_units),
                    unit_by_id=unit_by_id,
                    concept_cards=concept_cards,
                ))
                candidate_binding_valid = _local_lane_candidates_ok(
                    lane=request_lane,
                    requested=request_candidates,
                    authorized=allowed_candidates,
                    unanchored=unanchored_proof,
                )
        # Stage 5 concept closure: a request may name a concept card only
        # when that card is bound to the section.  An invented concept key
        # is a contract failure, not a hint to be forwarded.
        concept_key = str(raw.get("concept_key") or "").strip()
        concept_closed = True
        if concept_key:
            section_concept_keys = {
                str(key)
                for unit_id in (
                    move_spec.argument_unit_ids
                    if move_spec is not None
                    else graph.argument_unit_ids
                ) or ()
                for key in (
                    getattr(unit_by_id.get(unit_id), "concept_card_ids", ()) or ()
                )
            }
            concept_closed = concept_key in section_concept_keys
        if (
            move in unanchored or move in optional_unanchored
        ) and (
            bool(request_id)
            and request_section == graph.section_id
            and request_unit in allowed_units
            and bool(exact_question)
            and (not proof_lane or request_lane == proof_lane)
            and status == "open"
            and candidate_binding_valid
            and concept_closed
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
    elif (
        output.new_research_requests
        and not unresolved_unanchored
        and not valid_requests
        and not reopened
    ):
        failures.append("unexpected_writing_research_callback")


def _unresolved_local_resume_callback_ids(
    *,
    resume_section_ids: tuple[str, ...],
    prior_outputs: dict[str, Any] | None,
    callback_bundle: Any | None,
    callback_artifacts: dict[str, tuple[WritingResearchCallbackArtifactV1, ...]],
) -> list[str]:
    """Local requests that still gate Writer resume.

    A section checkpoint can list Writer-emitted extras that the fulfillment
    bundle never admitted (typically unanchored ``configuration_and_branches``
    whose candidate list failed the exact-term subset).  W7 treats those as
    quality/review, not as Writer-retry reconstruction.  Every locally owned
    request the bundle did admit still fails closed without a matching
    artifact.  With no bundle, every locally owned checkpoint request gates.
    """

    admitted_ids = {
        item.request_id
        for item in (callback_bundle.requests if callback_bundle is not None else ())
        if item.required_authority_lane in _LOCALLY_OWNED_LANES
    }
    unresolved: list[str] = []
    for section_id in resume_section_ids:
        prior = (prior_outputs or {}).get(section_id)
        for raw_request in (prior.new_research_requests if prior is not None else ()):
            try:
                request = WritingResearchRequestV1.model_validate(raw_request)
            except ValueError:
                unresolved.append("invalid_request")
                continue
            if request.required_authority_lane not in _LOCALLY_OWNED_LANES:
                continue
            if admitted_ids and request.request_id not in admitted_ids:
                continue
            artifacts_for_request = callback_artifacts.get(request.request_id, ())
            if not artifacts_for_request or not all(
                artifact.request_id == request.request_id
                and artifact.section_id == request.section_id
                and artifact.argument_unit_id == request.argument_unit_id
                and artifact.authority_lane == request.required_authority_lane
                for artifact in artifacts_for_request
            ):
                unresolved.append(request.request_id)
    return unresolved


def _incumbent_candidate_available(out_root: str | Path) -> bool:
    """True when a prior Writer turn already published non-empty Candidate text."""

    return bool(_incumbent_candidate_digest(out_root))


def _incumbent_candidate_digest(out_root: str | Path) -> str:
    """Return the durable incumbent candidate text digest when one exists."""

    payload = _load_candidate_checkpoint(out_root)
    if payload is not None:
        checkpoint_digest = str(payload.get("final_text_digest") or "").strip()
        if checkpoint_digest:
            return checkpoint_digest
        final_text = str(payload.get("final_text") or "")
        if final_text.strip():
            return _digest_text(final_text)
    path = method_output(Path(out_root), "publication_candidate_method")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return _digest_text(text) if text.strip() else ""


def _incumbent_accepted_sections(
    out_root: str | Path,
    *,
    plan_digest: str = "",
    claim_digest: str = "",
    proposition_set_digest: str = "",
) -> list[tuple[str, str, str]]:
    """Load plan-ordered incumbent section bodies from the durable checkpoint."""

    payload = _load_candidate_checkpoint(out_root)
    if payload is None:
        return []
    if plan_digest and str(payload.get("plan_digest") or "") != plan_digest:
        return []
    if claim_digest and str(payload.get("claim_digest") or "") != claim_digest:
        return []
    checkpoint_proposition_digest = str(payload.get("proposition_set_digest") or "")
    if proposition_set_digest:
        if checkpoint_proposition_digest != proposition_set_digest:
            return []
    elif checkpoint_proposition_digest:
        return []
    sections = payload.get("sections")
    if not isinstance(sections, dict):
        return []
    accepted: list[tuple[str, str, str]] = []
    for section_id, row in sections.items():
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "")
        if not text.strip():
            continue
        accepted.append((
            str(section_id),
            text,
            str(row.get("response_ref") or ""),
        ))
    return accepted


def _merge_accepted_with_incumbent(
    *,
    accepted: list[tuple[str, str, str]],
    output_by_section: dict[str, PublicationMethodSectionOutputV1],
    plan: MethodSectionPlanV2,
    effective_resume_section_ids: tuple[str, ...],
    out_root: str | Path,
    plan_digest: str,
    claim_digest: str,
    proposition_set_digest: str,
) -> tuple[
    list[tuple[str, str, str]],
    dict[str, PublicationMethodSectionOutputV1],
    list[str],
]:
    """Preserve incumbent sections when a resume attempt fails or omits them."""

    if not effective_resume_section_ids:
        return accepted, output_by_section, []
    incumbent_sections = _incumbent_accepted_sections(
        out_root,
        plan_digest=plan_digest,
        claim_digest=claim_digest,
        proposition_set_digest=proposition_set_digest,
    )
    if not incumbent_sections:
        return accepted, output_by_section, []
    incumbent_by_id = {
        section_id: (text, response_ref)
        for section_id, text, response_ref in incumbent_sections
    }
    accepted_by_id = {
        section_id: (text, response_ref)
        for section_id, text, response_ref in accepted
    }
    resume_section_set = set(effective_resume_section_ids)
    merged_outputs = dict(output_by_section)
    warnings: list[str] = []
    merged_accepted: list[tuple[str, str, str]] = []
    for graph in plan.sections:
        section_id = graph.section_id
        if section_id in accepted_by_id:
            text, response_ref = accepted_by_id[section_id]
            merged_accepted.append((section_id, text, response_ref))
            continue
        incumbent = incumbent_by_id.get(section_id)
        if incumbent is None:
            continue
        text, response_ref = incumbent
        merged_accepted.append((section_id, text, response_ref))
        if section_id in resume_section_set:
            warnings.append(f"resume_section_preserved_incumbent:{section_id}")
        if section_id not in merged_outputs:
            merged_outputs[section_id] = PublicationMethodSectionOutputV1(
                section_id=section_id,
                section_markdown=text,
            )
    if not accepted and merged_accepted:
        warnings.append("incumbent_candidate_restored_from_checkpoint")
    return merged_accepted, merged_outputs, warnings


def _publication_attempt_id(
    *,
    out_root: str | Path,
    plan_digest: str,
    claim_digest: str,
    resumed_section_ids: tuple[str, ...],
) -> str:
    payload = {
        "out_root": str(Path(out_root).expanduser().resolve()),
        "plan_digest": plan_digest,
        "claim_digest": claim_digest,
        "resumed_section_ids": list(resumed_section_ids),
    }
    return _digest_json(payload)


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
    concept_cards: Any | None = None,
) -> WritingResearchRequestV1 | None:
    """Validate a model request's exact candidates without inventing them.

    A model-emitted request must match one unresolved proof's section/unit/
    move/lane and may only narrow its exact question or candidates.
    Empty executable terms are filled from the request's own closed-set
    ``missing_parts`` (author clauses already on the callback).  Invented
    terms outside that set still reject routing.
    """
    proof = (
        authority_proofs.get((graph.section_id, request.missing_rhetorical_move))
        if authority_proofs is not None
        else None
    )
    if proof is None:
        return None
    request = fill_writing_research_search_terms(request)
    allowed_units = tuple(proof.argument_unit_ids or graph.argument_unit_ids or ())
    authorized_terms = set(_request_candidate_terms(
        request,
        allowed_units=allowed_units,
        unit_by_id=unit_by_id,
        concept_cards=concept_cards,
    ))
    requested = tuple(dict.fromkeys(
        str(item) for item in request.candidate_symbols_or_terms
        if str(item).strip()
    ))
    unanchored = bool(getattr(proof, "unanchored", False))
    if not _local_lane_candidates_ok(
        lane=request.required_authority_lane,
        requested=requested,
        authorized=authorized_terms,
        unanchored=unanchored,
    ):
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
    concept_cards: Any | None = None,
) -> tuple[str, ...]:
    """Lane-specific exact candidate terms for one request.

    Repository candidates are exact subjects, operands, and relation endpoints
    from the bound frames; configuration candidates add exact keys/IDs;
    formalization candidates add exact equation IDs and operands.  In the
    concept lane, the reader surface of the units' bound concept cards
    (subject, operation, inputs, outputs, conditions, known parts) is also
    authorized — a caveated concept's missing parts must be researchable even
    when its frame is thin.
    """

    candidates = list(dict.fromkeys(
        str(item)
        for unit_id in allowed_units
        if unit_id in unit_by_id
        for item in _unit_candidate_terms(unit_by_id[unit_id])
    ))
    candidates.extend(
        directed_search_terms_from_texts(*request.missing_parts)
    )
    if concept_cards is not None:
        concept_by_key = {
            item.concept_key: item
            for item in (getattr(concept_cards, "cards", ()) or ())
        }
        for unit_id in allowed_units:
            unit = unit_by_id.get(unit_id)
            if unit is None:
                continue
            for concept_key in (
                getattr(unit, "concept_card_ids", ()) or ()
            ):
                card = concept_by_key.get(concept_key)
                if card is not None:
                    candidates.extend(_concept_search_terms(card))
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


def _audit_proposition_alignment(
    *,
    accepted: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    propositions: MethodPropositionSetV1 | None,
    llm_config: LLMConfig,
    validation_paths: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Audit section prose against its exact proposition set.

    This report does not upgrade evidence authority. It records rendered,
    missing and ambiguous propositions for repair/metrics while the existing
    reverse evidence validator remains the verified-output gate.
    """

    if propositions is None:
        return {
            "schema_version": "1.0", "status": "not_run",
            "reason": "method_propositions_v1_missing", "sections": [],
            "semantic_alignment_calls": 0, "semantic_alignment_ambiguous": 0,
        }
    proposition_by_id = {
        item.proposition_id: item for item in propositions.propositions
    }
    evidence_fragments: list[tuple[str, str, tuple[str, ...]]] = []
    validation_paths = validation_paths or {}
    final_claims_path = validation_paths.get("final_text_claims", "")
    validation_path = validation_paths.get("text_evidence_validation", "")
    if final_claims_path and validation_path:
        try:
            final_claims = load_final_text_claims(final_claims_path)
            validation = load_text_evidence_validation(validation_path)
            verdict_by_id = {
                item.atomic_claim_id: item.status for item in validation.verdicts
            }
            evidence_fragments = [
                (
                    item.text,
                    verdict_by_id.get(item.atomic_claim_id, "unverified"),
                    tuple(item.candidate_method_proposition_ids),
                )
                for item in final_claims.atomic_claims
                if item.text.strip()
            ]
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            evidence_fragments = []
    units = {item.argument_unit_id: item for item in plan.argument_units}
    propositions_by_section: dict[str, list[Any]] = {}
    for section in plan.sections:
        propositions_by_section[section.section_id] = [
            proposition_by_id[proposition_id]
            for unit_id in section.argument_unit_ids if unit_id in units
            for proposition_id in (
                units[unit_id].proposition_order or units[unit_id].proposition_ids
            )
            if proposition_id in proposition_by_id
        ]
    aligner = build_proposition_semantic_aligner(llm_config)
    max_calls_per_section = max(0, min(int(os.environ.get(
        "CODE2PAPER_MAX_PROPOSITION_ALIGNMENT_CALLS_PER_SECTION", "8"
    )), 12))
    rows: list[dict[str, Any]] = []
    total_calls = 0
    ambiguous = 0
    for section_id, text, _response_ref in accepted:
        closed = propositions_by_section.get(section_id, [])
        required = {item.proposition_id for item in closed}
        matched: set[str] = set()
        evidence_validated: set[str] = set()
        sentence_rows: list[dict[str, Any]] = []
        calls = 0
        for sentence in (
            item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", text)
            if item.strip() and not item.lstrip().startswith("#")
        ):
            normalized_sentence = " ".join(_content_tokens(sentence))
            contained_evidence = [
                (status, proposition_ids)
                for fragment, status, proposition_ids in evidence_fragments
                if (
                    (normalized_fragment := " ".join(_content_tokens(fragment)))
                    and (
                        normalized_fragment in normalized_sentence
                        or normalized_sentence in normalized_fragment
                    )
                )
            ]
            persisted_matches = {
                proposition_id
                for _status, proposition_ids in contained_evidence
                for proposition_id in proposition_ids
                if proposition_id in required
            }
            if persisted_matches:
                matched.update(persisted_matches)
                supported_ids = {
                    proposition_id
                    for status, proposition_ids in contained_evidence
                    if status == "supported"
                    for proposition_id in proposition_ids
                }
                evidence_validated.update(persisted_matches & supported_ids)
                sentence_rows.append({
                    "sentence": sentence,
                    "status": "matched",
                    "matched_proposition_ids": sorted(persisted_matches),
                    "preserved_roles": [],
                    "missing_roles": [],
                    "rationale": "Reused reverse-validation proposition binding.",
                })
                continue
            semantic_owner = aligner if calls < max_calls_per_section else None
            alignment = align_sentence_to_section_propositions(
                sentence, closed, semantic_aligner=semantic_owner,
            )
            # A call happens only for non-exact retrieved candidates. The
            # aligner module intentionally skips no-candidate inventions.
            if semantic_owner is not None and alignment.rationale not in {
                "No closed section proposition was retrieved.",
                "Deterministic exact semantic-field overlap.",
                "Candidate-only proposition lacks a visible caveat.",
                "Immutable proposition constraints were not preserved.",
            }:
                calls += 1
            if alignment.status == "matched":
                matched.update(alignment.matched_proposition_ids)
                contained_verdicts = [
                    status
                    for fragment, status, _proposition_ids in evidence_fragments
                    if (
                        (normalized_fragment := " ".join(_content_tokens(fragment)))
                        and (
                            normalized_fragment in normalized_sentence
                            or normalized_sentence in normalized_fragment
                        )
                    )
                ]
                if contained_verdicts and all(
                    status == "supported" for status in contained_verdicts
                ):
                    evidence_validated.update(alignment.matched_proposition_ids)
            if alignment.status == "ambiguous":
                ambiguous += 1
            sentence_rows.append({
                "sentence": sentence,
                **alignment.model_dump(mode="json"),
            })
        total_calls += calls
        rows.append({
            "section_id": section_id,
            "required_proposition_ids": sorted(required),
            "required_evidence_proposition_ids": sorted(
                proposition_id
                for proposition_id in required
                if bool(getattr(proposition_by_id.get(proposition_id), "may_enter_verified", False))
            ),
            "rendered_proposition_ids": sorted(required & matched),
            "validated_proposition_ids": sorted(required & evidence_validated),
            "missing_proposition_ids": sorted(required - matched),
            "semantic_alignment_calls": calls,
            "sentence_alignments": sentence_rows,
        })
    return {
        "schema_version": "1.0",
        "status": "passed" if all(not row["missing_proposition_ids"] for row in rows) else "incomplete",
        "render_status": (
            "passed" if all(not row["missing_proposition_ids"] for row in rows)
            else "incomplete"
        ),
        "evidence_validation_status": (
            "not_run" if not evidence_fragments
            else "passed" if all(
                set(row["required_evidence_proposition_ids"])
                <= set(row["validated_proposition_ids"])
                for row in rows
            ) else "incomplete"
        ),
        "sections": rows,
        "semantic_alignment_calls": total_calls,
        "semantic_alignment_ambiguous": ambiguous,
    }


def _compose_candidate_markdown(
    *,
    accepted: list[tuple[str, str, str]],
    plan: MethodSectionPlanV2,
    section_outputs: Mapping[str, PublicationMethodSectionOutputV1],
    excluded_section_ids: Iterable[str] = (),
) -> str:
    """Keep every non-empty authored section in the Candidate view.

    ``accepted`` is deliberately narrower than the Candidate product: a
    section can fail a required witness transaction and still contain useful
    author-intent prose for diagnosis/review.  Such prose must never enter the
    rendered/Verified counters, but dropping it from the Candidate would hide
    the exact failure the author needs to repair.  Accepted sections retain
    their post-editor text; failed sections retain the Writer's normalized
    body verbatim.
    """

    excluded = {str(value) for value in excluded_section_ids if str(value).strip()}
    accepted_by_id = {
        str(section_id): str(text or "").strip()
        for section_id, text, _response_ref in accepted
        if str(text or "").strip() and str(section_id) not in excluded
    }
    output_by_id = {
        str(section_id): output
        for section_id, output in section_outputs.items()
        if output is not None
    }
    ordered_ids = [str(section.section_id) for section in plan.sections]
    ordered_ids.extend(
        section_id for section_id in output_by_id if section_id not in ordered_ids
    )
    sections: list[str] = []
    for section_id in ordered_ids:
        if section_id in excluded:
            continue
        text = accepted_by_id.get(section_id, "")
        if not text:
            output = output_by_id.get(section_id)
            text = str(getattr(output, "section_markdown", "") or "").strip()
        if text:
            sections.append(text)
    return "\n\n".join(sections)


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
    propositions: MethodPropositionSetV1 | None = None,
    proposition_alignment_report: dict[str, Any] | None = None,
    section_outputs: tuple[PublicationMethodSectionOutputV1, ...] = (),
    excluded_section_ids: Iterable[str] = (),
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
    # ``final_text`` is the rendered/accepted view used by validation and
    # Verified projection.  The Candidate additionally retains non-empty
    # section bodies whose paragraph transaction was rejected, so the author
    # can inspect and repair the exact prose instead of losing it.
    candidate_markdown = _compose_candidate_markdown(
        accepted=accepted,
        plan=plan,
        section_outputs={
            str(output.section_id): output
            for output in section_outputs
            if output is not None
        },
        excluded_section_ids=excluded_section_ids,
    ) or final_text
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
            expected_headings={section.heading for section in plan.sections},
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

    # Required propositions must never disappear between planning and the
    # three products. A proposition that is neither evidence-validated nor a
    # visible caveated sentence must have an explicit Writer defer reason;
    # expose that reason as an editable review item.
    proposition_by_id = {
        item.proposition_id: item
        for item in (propositions.propositions if propositions is not None else ())
    }
    aligned = {
        str(proposition_id)
        for row in (proposition_alignment_report or {}).get("sections", ())
        for proposition_id in (
            *(row.get("validated_proposition_ids") or ()),
            *(row.get("rendered_proposition_ids") or ()),
        )
    }
    deferred_reasons: dict[str, tuple[str, str]] = {}
    for output in section_outputs:
        reason_parts = tuple(dict.fromkeys(
            str(value).strip()
            for value in (
                *output.unresolved_points,
                *output.self_identified_risks,
                *(
                    str(request.get("exact_question") or request.get("reason") or "")
                    for request in output.new_research_requests
                    if isinstance(request, dict)
                ),
            )
            if str(value).strip()
        ))
        for proposition_id in output.deferred_proposition_ids:
            if reason_parts:
                deferred_reasons[str(proposition_id)] = (
                    output.section_id, "; ".join(reason_parts)
                )
    for proposition_id, (section_id, reason) in sorted(deferred_reasons.items()):
        if proposition_id in aligned or proposition_id not in proposition_by_id:
            continue
        candidate_id = f"review-proposition:{proposition_id}"
        if candidate_id in seen_ids:
            continue
        proposition = proposition_by_id[proposition_id]
        review_items.append(MethodReviewCandidateV1(
            candidate_id=candidate_id,
            source_obligation_id=(
                proposition.source_obligation_ids[0]
                if proposition.source_obligation_ids else ""
            ),
            section_id=section_id,
            lane=proposition.evidence_lane,
            status="deferred_proposition",
            proposed_body=" ".join((
                proposition.reader_subject,
                proposition.transformation,
            )).strip(),
            confirmation_question=reason,
            needed_evidence=(reason,),
            suggested_action="resolve_deferred_method_proposition",
            blocks_verified=True,
            blocks_candidate=False,
            trace_refs=(proposition_id,),
        ))
        seen_ids.add(candidate_id)

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

    # Reader-facing quality applies to verified too (plan 14.3.5): verified
    # filtering does not exempt the document from internal-id or structure
    # checks.  A leaked id in verified becomes a blocking review item, never
    # a silent regex deletion.
    verified_leaks = [
        match.group(0)
        for pattern in _READER_FACING_INTERNAL_ID_PATTERNS
        if (match := pattern.search(verified_markdown)) is not None
    ]
    # Verified is fail-closed: a leaked harness token is stripped from the
    # verified document deterministically (it is not author prose and cannot
    # be kept), while the exact sentence/heading remains in the candidate and
    # a blocking review item preserves the rewrite obligation.
    for leak in dict.fromkeys(verified_leaks):
        verified_markdown = verified_markdown.replace(leak, "")
    if verified_leaks:
        split_report = {**split_report, "verified_leak_fragments_removed": list(dict.fromkeys(verified_leaks))}
    for leak in dict.fromkeys(verified_leaks):
        candidate_id = f"review-verified-leak:{_stable_token(leak)}"
        if candidate_id in seen_ids:
            continue
        review_items.append(MethodReviewCandidateV1(
            candidate_id=candidate_id,
            source_claim_id="",
            section_id=_section_for_text(accepted, verified_markdown, leak),
            lane="repository_verified",
            status="unverified",
            proposed_body=leak,
            confirmation_question=(
                "The repository-verified document contains a harness-internal "
                f"id ({leak!r}). Rewrite the sentence in natural Method "
                "language so the supported content survives without the id."
            ),
            needed_evidence=("reader_facing_internal_id",),
            suggested_action="rewrite_remove_internal_id",
            blocks_verified=True,
            blocks_candidate=False,
            trace_refs=(candidate_id,),
        ))
        seen_ids.add(candidate_id)
    return (
        candidate_markdown,
        verified_markdown,
        tuple(review_items),
        external_queue_items,
        split_report,
    )


def _stable_token(value: str) -> str:
    """Deterministic short token for review-item ids (no hashing surprises)."""

    import re as _re

    cleaned = _re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned[:48] or "leak"


def _section_for_text(
    accepted: list[tuple[str, str, str]],
    document_text: str,
    needle: str,
) -> str:
    """Return the section owning the first occurrence of ``needle``."""

    index = document_text.find(needle)
    if index < 0:
        return ""
    cursor = 0
    for section_id, text, _ref in accepted:
        start = cursor
        cursor += len(text) + 2
        if start <= index < cursor:
            return section_id
    return ""


def _write_paragraph_transaction_assessments(
    *,
    out_root: str | Path,
    plan: MethodSectionPlanV2,
    section_inputs: Mapping[str, WriterSectionInput],
    section_outputs: Mapping[str, PublicationMethodSectionOutputV1],
    formalization_path: str | Path = "",
) -> tuple[str, str]:
    """Persist the single paragraph-transaction assessment authority.

    The trace and callback gate consume this sidecar rather than trying to
    infer rendered coverage from aggregate section ids.  Every planned
    paragraph receives a row, including missing outputs, so a failed Writer
    response remains diagnosable without turning into a successful render.
    """

    formalization_payload: dict[str, Any] = {}
    if formalization_path:
        try:
            raw = json.loads(Path(formalization_path).read_text(encoding="utf-8"))
            formalization_payload = raw if isinstance(raw, dict) else {}
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            formalization_payload = {}
    formalization_by_section = {
        str(item.get("section_id") or ""): item
        for item in formalization_payload.get("sections") or ()
        if isinstance(item, Mapping)
    }

    def _routes_for(section_id: str, section: WriterSectionInput) -> dict[str, dict[str, Any]]:
        formal = formalization_by_section.get(section_id, {})
        packages = tuple(
            item for item in (formal.get("packages") or ()) if isinstance(item, Mapping)
        )
        obligations = tuple(
            item for item in (
                formal.get("formula_obligations")
                or section.prompt_payload.get("formula_obligations")
                or ()
            )
            if isinstance(item, Mapping)
        )
        routes: dict[str, dict[str, Any]] = {}
        for obligation in obligations:
            obligation_id = str(obligation.get("obligation_id") or "").strip()
            if not obligation_id:
                continue
            matches = [
                package for package in packages
                if (
                    str(package.get("obligation_id") or "").strip() == obligation_id
                    or (
                        set(str(item) for item in (obligation.get("facet_ids") or ()))
                        & set(str(item) for item in (package.get("bound_facet_ids") or ()))
                    )
                )
            ]
            routes[obligation_id] = {
                "package_ids": tuple(
                    str(package.get("package_id") or "")
                    for package in matches
                    if str(package.get("package_id") or "").strip()
                ),
                "latex": str(
                    matches[0].get("latex") or matches[0].get("markdown_block") or ""
                ) if matches else "",
            }
        # A prompt may carry packages even when the persisted Formalizer
        # result is unavailable (e.g. a unit test or a resumed section).  Keep
        # those package ids routed, but never create a route without an
        # obligation id.
        if not packages:
            packages = tuple(
                item for item in (section.prompt_payload.get("formula_packages") or ())
                if isinstance(item, Mapping)
            )
            for package in packages:
                obligation_id = str(package.get("obligation_id") or "").strip()
                package_id = str(package.get("package_id") or "").strip()
                if obligation_id and package_id:
                    routes.setdefault(obligation_id, {
                        "package_ids": (package_id,),
                        "latex": str(package.get("latex") or package.get("markdown_block") or ""),
                    })
        return routes

    rows: list[dict[str, Any]] = []
    for graph in plan.sections:
        section_id = str(graph.section_id)
        section_input = section_inputs.get(section_id)
        output = section_outputs.get(section_id)
        transactions = {
            str(item.paragraph_id): item
            for item in (getattr(output, "paragraphs", ()) or ())
            if str(getattr(item, "paragraph_id", "") or "").strip()
        }
        routes = _routes_for(section_id, section_input) if section_input else {}
        for plan_row in graph.paragraphs or ():
            paragraph_id = str(plan_row.paragraph_id)
            transaction = transactions.get(paragraph_id)
            assessment = assess_paragraph_transaction(
                transaction or {"paragraph_id": paragraph_id},
                plan_row=plan_row.model_dump(mode="json")
                if hasattr(plan_row, "model_dump") else plan_row,
                formula_routes=routes,
            )
            row = {
                "section_id": section_id,
                **assessment.model_dump(mode="json"),
            }
            rows.append(row)
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "plan_digest": str(plan.content_digest or ""),
        "assessments": rows,
    }
    payload["content_digest"] = _digest_json(payload)
    path = method_output(Path(out_root), "publication_paragraph_transaction_assessments_v1")
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return str(path), str(payload["content_digest"])


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


def _rebase_published_bundle_refs(
    payload: dict[str, Any],
    *,
    out_root: str | Path,
    bundle_dir: str | Path,
) -> dict[str, Any]:
    """Rewrite file-backed artifact refs so the PUBLISHED bundle resolves
    them from its own persisted directory, then revalidate every digest.

    The input bundle's refs are relative to the top-level artifacts
    directory; the published hand-off lives one level deeper under
    ``06_authoring/``, so the same refs would resolve to a path that does
    not exist.  Each referenced file must resolve inside the run root and
    match its recorded digest, or the caller must fail closed (R3).
    """

    root = Path(out_root).expanduser().resolve()
    directory = Path(bundle_dir).expanduser().resolve()
    rebased = json.loads(json.dumps(payload))
    # The persisted digest covered the INPUT refs; the published payload is
    # a new artifact, so drop the stale digest and let the model recompute.
    rebased.pop("content_digest", None)
    for _request_id, artifacts in (rebased.get("artifacts") or {}).items():
        for raw in artifacts or ():
            if not isinstance(raw, dict):
                continue
            reference = str(raw.get("artifact_ref") or "").strip()
            if not reference or reference.startswith(_OPAQUE_CALLBACK_REF_PREFIXES):
                continue
            if not _looks_like_callback_file_reference(reference):
                # Opaque evidence handles (compact non-path ids) are resolved
                # by the owning tool; only path-shaped refs need rebasing.
                continue
            candidate = (directory / reference).resolve()
            if not (candidate.is_file() and candidate.is_relative_to(root)):
                candidate = ((root / "artifacts") / reference).resolve()
            if not (candidate.is_file() and candidate.is_relative_to(root)):
                candidate = (root / reference).resolve()
            if not (candidate.is_file() and candidate.is_relative_to(root)):
                raise ValueError(
                    f"callback artifact ref does not resolve inside the run root: "
                    f"{reference}"
                )
            relative = candidate.relative_to(root)
            target = root / relative
            actual_digest = "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
            if actual_digest != str(raw.get("artifact_digest") or ""):
                raise ValueError(
                    f"callback artifact digest mismatch after publication: "
                    f"{raw.get('artifact_id')}"
                )
            # Rebase relative to the PUBLISHED bundle's own directory (one
            # level deeper than the top-level input bundle).
            rebased_ref = os.path.relpath(target, directory)
            raw["artifact_ref"] = rebased_ref.replace(os.sep, "/")
    return rebased


def _write_publication_outputs(
    *,
    out_root: str | Path,
    candidate_markdown: str,
    verified_markdown: str,
    review_items: tuple[MethodReviewCandidateV1, ...],
    external_queue_items: tuple[ExternalResearchQueueItemV1, ...],
    split_report: dict[str, Any],
    proposition_alignment_report: dict[str, Any],
    readiness: MethodPlanProductReadinessV1,
    effective_readiness: str,
    research_requests: list[WritingResearchRequestV1],
    writer,
    ledger,
    quality,
    section_outputs: dict[str, PublicationMethodSectionOutputV1],
    section_response_refs: dict[str, str],
    proposition_set_digest: str = "",
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
    proposition_alignment_path = method_output(root, "method_proposition_alignment_v1")
    checkpoint_path = method_output(root, "publication_section_checkpoint_v1")
    routes_path = method_output(root, "writing_research_routes_v1")
    callback_bundle_path = method_output(root, "writing_research_callback_artifacts_v1")
    editor_path = method_output(root, "publication_editor_result_v1")
    external_queue_path = method_output(root, "external_research_queue_v1")
    bundle_path = method_output(root, "method_draft_bundle_v1")
    published_paths: dict[str, str] = {}
    # Q0: the candidate is the primary product.  Once any non-empty incumbent
    # exists it is durably published even when validation reports warnings,
    # quality is blocked, or the repair budget is exhausted.  Only a truly
    # empty draft (generation failure) leaves the candidate unpublished.
    if candidate_markdown.strip():
        # The verified document contains only repository-supported positive
        # implementation facts; it may be shorter or empty without
        # invalidating the candidate.
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
    _atomic_write_text(
        proposition_alignment_path,
        json.dumps(proposition_alignment_report, ensure_ascii=False, indent=2) + "\n",
    )
    _write_section_checkpoint(
        checkpoint_path,
        section_outputs=section_outputs,
        section_response_refs=section_response_refs,
        proposition_set_digest=proposition_set_digest,
    )
    route_rows: list[dict[str, Any]] = []
    route_rejections: list[dict[str, str]] = []
    for request in research_requests:
        try:
            route_rows.append(route_writing_research_request(request).model_dump(mode="json"))
        except (TypeError, ValueError) as exc:
            # Keep one durable routing receipt per Writer request without
            # pretending that a rejected request was executable.  The request
            # remains visible in the callback bundle/review sidecar, while the
            # rejection is explicit and cannot be consumed as a route.
            rejection = {
                "request_id": request.request_id,
                "section_id": request.section_id,
                "owner": "rejected",
                "required_authority_lane": request.required_authority_lane,
                "status": "rejected",
                "reason": f"{type(exc).__name__}:{str(exc)[:160]}",
            }
            route_rejections.append(rejection)
            route_rows.append(rejection)
    _atomic_write_text(routes_path, json.dumps({
        "schema_version": "1.0",
        "routes": route_rows,
        "rejections": route_rejections,
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
        callback_payload = None
    if callback_payload is not None:
        try:
            # R3: the published bundle lives under 06_authoring/; its
            # file-backed refs must resolve from THAT directory (not the
            # input location) and every digest must survive publication.
            rebased_payload = _rebase_published_bundle_refs(
                callback_payload.model_dump(mode="json"),
                out_root=root,
                bundle_dir=callback_bundle_path.parent,
            )
            callback_payload = WritingResearchCallbackBundleV1.model_validate(
                rebased_payload
            )
        except ValueError:
            callback_payload = None
    if callback_payload is None:
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
        "method_proposition_alignment_v1": str(proposition_alignment_path),
        "publication_section_checkpoint_v1": str(checkpoint_path),
        "publication_candidate_checkpoint_v1": str(method_output(root, "publication_candidate_checkpoint_v1")),
        "writing_research_routes_v1": str(routes_path),
        "writing_research_callback_artifacts_v1": str(callback_bundle_path),
        "formalization_result_v1": str(formalization_path),
        **({"publication_editor_result_v1": str(editor_path)} if editor_result is not None else {}),
    }


def _write_method_generation_trace(
    *,
    out_root: str | Path,
    artifact_paths: Mapping[str, str],
    paths: Mapping[str, str],
    plan: MethodSectionPlanV2,
    writer: Any,
    section_outputs: tuple[Any, ...],
    quality: Any,
    status: str,
    blocked_reason: str = "",
) -> str:
    """Persist one auditable trace for the complete Method generation chain.

    Existing role traces are intentionally preserved verbatim.  This sidecar
    only adds stage boundaries and semantic-delta counters so a later repair
    can distinguish a real evidence/witness change from a character-count or
    digest change.
    """

    try:
        from code2paper.llm.generation_trace import get_run_generation_traces

        calls = get_run_generation_traces()
    except Exception:
        calls = []

    def _file_digest(value: str) -> str:
        if not value or not Path(value).is_file():
            return ""
        try:
            return "sha256:" + hashlib.sha256(
                Path(value).read_bytes()
            ).hexdigest()
        except OSError:
            return ""

    def _stage_for_call(call: Mapping[str, Any]) -> str:
        role = str(call.get("role") or "").casefold()
        template = str(call.get("prompt_template_id") or "").casefold()
        if (
            "architect" in role
            or "architect" in template
            or "planner" in role
            or "argument_brief_planner" in template
        ):
            return "architect"
        if "facet_alignment" in template or "aligner" in role:
            return "aligner"
        if "formal" in role or "formal" in template:
            return "formalizer"
        # Repair calls retain the ``method_writer`` role for provider
        # configuration, so classify their explicit repair/rewrite template
        # before the broad writer-role match.  Otherwise the generation
        # ledger reports every content/representation repair as an ordinary
        # Writer call and hides the very tail-loop evidence it is meant to
        # expose.
        if "repair" in template or "rewrite" in template:
            return "repair"
        if "callback" in template or "research" in template:
            return "callback"
        if "editor" in role or "editor" in template:
            return "editor"
        if "writer" in role or "publication" in template:
            return "writer"
        return "other"

    events: list[dict[str, Any]] = []
    for call in calls:
        row = dict(call)
        row["stage"] = _stage_for_call(row)
        row["semantic_delta"] = {
            "validated_witnesses_added": 0,
            "field_bindings_added": 0,
            "formula_packages_consumed": 0,
            "resolved_mismatches": 0,
        }
        events.append(row)
    aggregate = getattr(writer, "aggregate", None)
    if aggregate is not None:
        for rejection in (getattr(aggregate, "writer_repair_transaction_rejections", ()) or ()):
            events.append({
                "stage": "repair",
                "owner": "method_writer",
                "section_id": str(rejection.get("section_id") or ""),
                "stop_reason": str(rejection.get("reason") or ""),
                "commit": False,
                "semantic_delta": {
                    "validated_witnesses_added": 0,
                    "field_bindings_added": 0,
                    "formula_packages_consumed": 0,
                    "resolved_mismatches": 0,
                },
            })

    planned_paragraphs = sum(
        len(getattr(section, "paragraphs", ()) or ())
        for section in plan.sections
    )
    rendered_paragraphs = sum(
        len(getattr(output, "paragraphs", ()) or ())
        for output in section_outputs
    )
    rendered_witnesses = sum(
        len(getattr(paragraph, "witnesses", ()) or ())
        for output in section_outputs
        for paragraph in (getattr(output, "paragraphs", ()) or ())
    )
    stage_events = [
        {
            "stage": "architect",
            "input_digest": _file_digest(artifact_paths.get("method_section_plan_v2", "")),
            "output_digest": plan.content_digest,
            "affected_sections": [section.section_id for section in plan.sections],
            "semantic_delta": {
                "field_bindings_added": sum(
                    len(paragraph.required_facet_ids)
                    for section in plan.sections
                    for paragraph in (section.paragraphs or ())
                ),
                "validated_witnesses_added": 0,
                "formula_packages_consumed": 0,
                "resolved_mismatches": 0,
            },
            "commit": True,
        },
        {
            "stage": "writer_transaction_summary",
            "output_digest": _digest_text("\n\n".join(
                str(getattr(output, "section_markdown", "") or "")
                for output in section_outputs
            )),
            "affected_paragraphs": rendered_paragraphs,
            "planned_paragraphs": planned_paragraphs,
            "validated_witnesses": rendered_witnesses,
            "semantic_delta": {
                "validated_witnesses_added": rendered_witnesses,
                "field_bindings_added": 0,
                "formula_packages_consumed": sum(
                    len(getattr(output, "used_formula_package_ids", ()) or ())
                    for output in section_outputs
                ),
                "resolved_mismatches": 0,
            },
            "commit": bool(rendered_paragraphs or section_outputs),
        },
    ]
    payload = {
        "schema_version": "1.0",
        "status": status,
        "blocked_reason": blocked_reason,
        "input_digests": {
            key: _file_digest(value)
            for key, value in artifact_paths.items()
            if key in {
                "method_argument_briefs_v1", "method_argument_facets_v1",
                "facet_evidence_alignments_v1", "method_section_plan_v2",
                "code_facts_v1", "equation_claims_v1",
            }
        },
        "calls": events,
        "stages": stage_events,
        "writer_counters": (
            aggregate.to_json_dict() if aggregate is not None else {}
        ),
        "quality_summary": {
            "status": str(getattr(quality, "status", "") or ""),
            "argument_move_coverage": getattr(quality, "argument_move_coverage", None),
            "equation_coverage": getattr(quality, "equation_coverage", None),
            "config_coverage": getattr(quality, "configuration_coverage", None),
            "publication_utility": getattr(quality, "publication_utility", None),
        },
        "stop_policy": {
            "no_gain_repairs": int(getattr(aggregate, "writer_repair_no_progress_stops", 0) or 0)
            if aggregate is not None else 0,
            "whole_section_retries": sum(
                1 for row in events
                if row.get("stage") == "repair" and row.get("commit") is False
            ),
            "candidate_incumbent_preserved": True,
        },
    }
    try:
        path = method_output(Path(out_root), "method_generation_trace_v1")
        _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return str(path)
    except (OSError, TypeError, ValueError):
        return ""


def _write_result_only(
    out_root: str | Path,
    result: PublicationWriterRunResultV1,
) -> dict[str, str]:
    # Q0: an early blocked result is a true generation failure only when no
    # durable candidate exists.  A later resume/callback block must not
    # rewrite an incumbent Candidate as ``failed`` / ``not_run``.
    incumbent_digest = _incumbent_candidate_digest(out_root)
    if incumbent_digest:
        result = result.model_copy(update={
            "candidate_generation_status": "generated",
            "candidate_available": True,
            "final_text_digest": result.final_text_digest or incumbent_digest,
        })
    elif result.status == "blocked" and not result.candidate_available:
        result = result.model_copy(update={
            "candidate_generation_status": "failed",
            "candidate_available": False,
        })
    path = method_output(Path(out_root), "publication_writer_result_v1")
    _atomic_write_text(path, result.model_dump_json(indent=2) + "\n")
    return {"publication_writer_result_v1": str(path)}


def _publish_checkpoint_fallback(
    *,
    out_root: str | Path,
    plan_digest: str,
    claim_digest: str,
    failure: str,
) -> tuple[PublicationWriterRunResultV1, dict[str, str]]:
    """Publish the best durable candidate when a post-Writer stage faults.

    Q0 rule (plan 19.4.2): an Editor/Rewrite/validator/report/model failure
    must never erase the incumbent candidate.  The latest intact checkpoint
    is republished with an honest error status; Verified is rebuilt only
    from a same-binding validated view, never guessed.  If no checkpoint
    exists this is a true generation failure.
    """

    root = Path(out_root)
    payload = _load_candidate_checkpoint(root)
    if payload is None:
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest=plan_digest,
            claim_digest=claim_digest,
            blocked_reason=f"candidate_checkpoint_unavailable_after_failure:{failure}",
            candidate_generation_status="failed",
            candidate_available=False,
        )
        return result, _write_result_only(root, result)
    final_text = str(payload.get("final_text") or "")
    rendered_text = str(payload.get("rendered_text") or final_text)
    candidate_path = method_output(root, "publication_candidate_method")
    verified_path = method_output(root, "repository_verified_method")
    _atomic_write_text(candidate_path, final_text)
    verified_markdown = ""
    view = payload.get("verified_view")
    if isinstance(view, dict):
        ok_binding = (
            str(payload.get("plan_digest") or "") == plan_digest
            and str(payload.get("claim_digest") or "") == claim_digest
            and str(view.get("final_text_digest") or "") == (
                str(payload.get("rendered_text_digest") or "")
                or (_digest_text(rendered_text) if rendered_text else "")
            )
        )
        if ok_binding:
            verified_markdown = str(view.get("markdown") or "")
    _atomic_write_text(verified_path, verified_markdown)
    paths: dict[str, str] = {
        "publication_candidate_method": str(candidate_path),
        "repository_verified_method": str(verified_path),
        "text_md": str(candidate_path),
        "text_clean_md": str(candidate_path),
    }
    result = PublicationWriterRunResultV1(
        status="incomplete",
        plan_digest=plan_digest,
        claim_digest=claim_digest,
        candidate_generation_status="generated",
        candidate_available=True,
        candidate_validation_status="error",
        verified_validation_status="error",
        publication_ready=False,
        final_text_digest=_digest_text(final_text) if final_text else "",
        rendered_text_digest=_digest_text(rendered_text) if rendered_text else "",
        blocked_reason=f"publication_stage_fault_recovered_from_candidate_checkpoint:{failure}",
        binding_failures=(f"publication_stage_fault:{failure}",),
    )
    result_path = method_output(root, "publication_writer_result_v1")
    _atomic_write_text(result_path, result.model_dump_json(indent=2) + "\n")
    paths["publication_writer_result_v1"] = str(result_path)
    return result, paths


def _atomic_write_text(path: Path, content: str) -> None:
    """Persist a hand-off artifact with an fsync + atomic replace boundary."""

    atomic_write_bytes(path, content.encode("utf-8"))


def _write_section_checkpoint(
    checkpoint_path: Path,
    *,
    section_outputs: Mapping[str, PublicationMethodSectionOutputV1],
    section_response_refs: Mapping[str, str],
    proposition_set_digest: str = "",
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
        "schema_version": "1.1",
        "checkpoint_format": "immutable_section_refs_v1",
        "sections": sections,
        "proposition_set_digest": proposition_set_digest,
    }
    checkpoint_payload["content_digest"] = _digest_json(checkpoint_payload)
    _atomic_write_text(
        checkpoint_path,
        json.dumps(checkpoint_payload, ensure_ascii=False, indent=2) + "\n",
    )


def _write_candidate_checkpoint(
    *,
    out_root: str | Path,
    stage: str,
    final_text: str,
    accepted: list[tuple[str, str, str]],
    rendered_text: str = "",
    plan_digest: str,
    claim_digest: str,
    proposition_set_digest: str = "",
    verified_markdown: str = "",
    reason: str = "",
    last_committed_attempt_id: str = "",
    warnings: tuple[str, ...] = (),
) -> Path:
    """Atomically persist the best durable Candidate draft (Q0).

    The checkpoint is written as soon as the Writer produces its first non-empty
    sections and updated after every accepted Editor/Rewrite transaction.  It is
    a recovery/durability record only: its digests are never used as article
    quality scores, and later validation/quality/model failures must fall back
    to the latest checkpoint instead of erasing the candidate.  When the final
    reverse validation passed, the same-binding Verified view is stored beside
    the text so a later validator error can reuse it instead of guessing.
    """

    root = Path(out_root)
    checkpoint_path = method_output(root, "publication_candidate_checkpoint_v1")
    sections = {
        str(section_id): {
            "text": text,
            "response_ref": response_ref,
            "section_digest": _digest_text(text) if text else "",
        }
        for section_id, text, response_ref in accepted
    }
    section_digests = {
        str(section_id): row["section_digest"]
        for section_id, row in sections.items()
    }
    attempt_id = last_committed_attempt_id or _publication_attempt_id(
        out_root=out_root,
        plan_digest=plan_digest,
        claim_digest=claim_digest,
        resumed_section_ids=(),
    )
    rendered_text = str(rendered_text or final_text)
    payload: dict[str, Any] = {
        "schema_version": "1.1",
        "stage": stage,
        "reason": reason,
        "plan_digest": plan_digest,
        "claim_digest": claim_digest,
        "proposition_set_digest": proposition_set_digest,
        "accepted_section_ids": [section_id for section_id, _text, _ref in accepted],
        "sections": sections,
        "section_digests": section_digests,
        # ``final_text`` is the durable Candidate view and may include
        # sections whose paragraph transaction is currently invalid.  The
        # accepted/rendered subset stays separately digest-bound for resume
        # and Verified recovery.
        "final_text": final_text,
        "final_text_digest": _digest_text(final_text) if final_text else "",
        "candidate_digest": _digest_text(final_text) if final_text else "",
        "rendered_text": rendered_text,
        "rendered_text_digest": _digest_text(rendered_text) if rendered_text else "",
        "last_committed_attempt_id": attempt_id,
        "warnings": list(warnings),
    }
    if verified_markdown.strip():
        payload["verified_view"] = {
            "final_text_digest": payload["rendered_text_digest"],
            "markdown": verified_markdown,
        }
    payload["content_digest"] = _digest_json(payload)
    _atomic_write_text(checkpoint_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return checkpoint_path


def _load_candidate_checkpoint(out_root: str | Path) -> dict[str, Any] | None:
    """Load the latest durable Candidate checkpoint, if intact."""

    checkpoint_path = method_output(Path(out_root), "publication_candidate_checkpoint_v1")
    if not checkpoint_path.is_file():
        return None
    try:
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    declared = str(payload.get("content_digest") or "")
    if not declared or declared != _digest_json({
        key: value for key, value in payload.items() if key != "content_digest"
    }):
        return None
    return payload


def _same_binding_verified_view(
    *,
    out_root: str | Path,
    final_text: str,
    plan_digest: str,
    claim_digest: str,
) -> str | None:
    """Reuse the previous same-binding Verified view, never a guessed one.

    Q0 rule: Verified must not be generated from an unvalidated Candidate.  When
    the final reverse validator errors, the run may reuse the verified view that
    was persisted for the exact same plan/claims/text binding, or honestly write
    nothing.
    """

    payload = _load_candidate_checkpoint(out_root)
    if payload is None:
        return None
    if str(payload.get("plan_digest") or "") != plan_digest:
        return None
    if str(payload.get("claim_digest") or "") != claim_digest:
        return None
    text_digest = _digest_text(final_text) if final_text else ""
    view = payload.get("verified_view") or {}
    if not isinstance(view, dict):
        return None
    if str(view.get("final_text_digest") or "") != text_digest:
        return None
    markdown = str(view.get("markdown") or "")
    return markdown if markdown.strip() else None


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
    slot_progress: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] | None = None,
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
    slot_progress = slot_progress or {}
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
        if request.status not in {"open", "partial"}:
            raise ValueError(f"callback artifact request is not open: {request_id}")
        if not normalized:
            raise ValueError(f"callback artifact list is empty: {request_id}")
        merged[str(request_id)] = normalized
        progress = slot_progress.get(str(request_id))
        satisfied_slots = tuple(request.satisfied_slots or ())
        remaining_slots = tuple(request.remaining_slots or ())
        if progress is not None:
            satisfied_slots = tuple(dict.fromkeys((*satisfied_slots, *progress[0])))
            remaining_slots = tuple(progress[1])
        next_status: Literal["fulfilled", "partial"] = (
            "partial" if remaining_slots else "fulfilled"
        )
        requests_by_id[str(request_id)] = request.model_copy(update={
            "status": next_status,
            "fulfilled_artifact_ids": tuple(item.artifact_id for item in normalized),
            "satisfied_slots": satisfied_slots,
            "remaining_slots": remaining_slots,
        })
    for request_id, progress in slot_progress.items():
        if str(request_id) in artifacts:
            continue
        request = requests_by_id.get(str(request_id))
        if request is None or request.status not in {"open", "partial"}:
            continue
        satisfied_slots = tuple(dict.fromkeys(
            (*request.satisfied_slots, *progress[0])
        ))
        remaining_slots = tuple(progress[1])
        next_status: Literal["open", "partial", "fulfilled"] = (
            "partial" if remaining_slots else "fulfilled"
        )
        requests_by_id[str(request_id)] = request.model_copy(update={
            "status": next_status,
            "satisfied_slots": satisfied_slots,
            "remaining_slots": remaining_slots,
        })
    updated = WritingResearchCallbackBundleV1(
        requests=tuple(requests_by_id.values()),
        artifacts=merged,
        resume_section_ids=tuple(dict.fromkeys([
            *bundle.resume_section_ids,
            *[
                request.section_id for request in requests_by_id.values()
                if request.status in {"fulfilled", "partial"}
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
    proposition_set_digest: str = "",
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
        checkpoint_proposition_digest = str(payload.get("proposition_set_digest") or "")
        if proposition_set_digest:
            if checkpoint_proposition_digest != proposition_set_digest:
                return None, {}
        elif checkpoint_proposition_digest:
            # A proposition-bound checkpoint cannot be replayed by a caller
            # that omitted the proposition artifact.
            return None, {}
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


def rebase_callback_bundle_artifacts(
    *,
    bundle_path: str | Path,
    frozen_root: str | Path,
    fresh_root: str | Path,
) -> dict[str, Any]:
    """Transitively copy digest-pinned callback files into a fresh replay root.

    ``bundle_path`` is the FROZEN bundle location (the persisted hand-off
    whose ``artifact_ref`` values resolve against the frozen bundle's own
    directory).  The persisted bundle only records ``artifact_ref`` strings;
    a replay must copy each referenced file, revalidate its recorded digest,
    and rebase the relative reference into the fresh root so Writer
    consumption stays file-backed (R3).  Traversal outside the frozen root,
    missing files, symlinked sources, and digest mismatches fail closed: the
    caller receives a non-empty ``failures`` list and must NOT publish a
    rebased bundle.

    Returns a report dict:
      - ``bundle``: the rebased bundle payload with ``artifact_ref`` values
        rewritten relative to the fresh bundle directory (``<fresh_root>/
        artifacts/writing_research_callback_artifacts_v1.json``), or
        ``None`` when any failure occurred;
      - ``copied_refs``: list of ``{artifact_id, source, target, digest}``;
      - ``reused_fulfilled_callback_ids``: request ids whose validated
        artifacts were reused in full.  Reuse is truthful telemetry: it is
        NOT a new resume event and must never be reported as one.
      - ``failures``: list of typed failure strings (empty on success).
    """

    frozen = Path(frozen_root).expanduser().resolve()
    fresh = Path(fresh_root).expanduser().resolve()
    bundle = Path(bundle_path).expanduser().resolve()
    report: dict[str, Any] = {
        "bundle": None,
        "copied_refs": [],
        "reused_fulfilled_callback_ids": [],
        "failures": [],
    }
    try:
        raw_payload = json.loads(bundle.read_text(encoding="utf-8"))
        model = WritingResearchCallbackBundleV1.model_validate(raw_payload)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        report["failures"].append(
            f"bundle_invalid:{exc.__class__.__name__}"
        )
        return report
    bundle_dir = bundle.parent
    rebased = json.loads(bundle.read_text(encoding="utf-8"))
    # Carry every persisted entry over; fulfilled requests below are
    # re-validated and their file refs rebased in place.
    rebased_artifacts: dict[str, list[dict[str, Any]]] = {
        key: list(value) for key, value in (rebased.get("artifacts", {}) or {}).items()
    }
    reused: list[str] = []
    for request in model.requests:
        if request.status != "fulfilled":
            continue
        raw_artifacts = list(rebased.get("artifacts", {}).get(request.request_id, ()))
        copied: list[dict[str, Any]] = []
        request_failed = False
        for raw in raw_artifacts:
            if not isinstance(raw, dict):
                report["failures"].append(f"{request.request_id}:artifact_schema_invalid")
                request_failed = True
                continue
            try:
                artifact = WritingResearchCallbackArtifactV1.model_validate(raw)
            except (TypeError, ValueError):
                report["failures"].append(f"{request.request_id}:artifact_schema_invalid")
                request_failed = True
                continue
            reference = str(artifact.artifact_ref or "").strip()
            if not reference or reference.startswith(_OPAQUE_CALLBACK_REF_PREFIXES):
                # Opaque evidence handles (span:/fact:/relation: ...) need no
                # file copy; they are resolved by the owning tool.
                copied.append(raw)
                continue
            raw_path = bundle_dir / reference
            if raw_path.is_symlink():
                report["failures"].append(f"{artifact.artifact_id}:artifact_ref_symlink")
                request_failed = True
                continue
            source = raw_path.resolve()
            if not source.is_relative_to(frozen):
                report["failures"].append(
                    f"{artifact.artifact_id}:artifact_ref_outside_frozen_root"
                )
                request_failed = True
                continue
            if not source.is_file():
                report["failures"].append(f"{artifact.artifact_id}:artifact_ref_missing")
                request_failed = True
                continue
            try:
                source_bytes = source.read_bytes()
            except OSError as exc:
                report["failures"].append(
                    f"{artifact.artifact_id}:artifact_ref_unreadable:{exc.__class__.__name__}"
                )
                request_failed = True
                continue
            actual_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
            if actual_digest != artifact.artifact_digest:
                report["failures"].append(f"{artifact.artifact_id}:artifact_digest_mismatch")
                request_failed = True
                continue
            relative = source.relative_to(frozen)
            # Normalize a frozen layout where the callback file itself lives
            # under ``artifacts/``: the fresh bundle sits at
            # ``<fresh>/artifacts/``, so ``../research_tool_data/...`` must
            # resolve to ``<fresh>/research_tool_data/...`` exactly like the
            # original run's layout.
            relative_parts = relative.parts
            if relative_parts and relative_parts[0] == "artifacts":
                relative = Path(*relative_parts[1:])
            target = fresh / relative
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            except OSError as exc:
                report["failures"].append(
                    f"{artifact.artifact_id}:artifact_copy_failed:{exc.__class__.__name__}"
                )
                request_failed = True
                continue
            raw["artifact_ref"] = str(Path("..") / relative)
            copied.append(raw)
            report["copied_refs"].append({
                "artifact_id": artifact.artifact_id,
                "source": str(source),
                "target": str(target),
                "digest": actual_digest,
            })
        rebased_artifacts[request.request_id] = copied
        if not request_failed and copied:
            reused.append(request.request_id)
    rebased["artifacts"] = rebased_artifacts
    # The persisted digest covered the FROZEN refs; the rebased payload is a
    # new artifact, so drop the stale digest and let the model recompute it.
    rebased.pop("content_digest", None)
    if report["failures"]:
        return report
    try:
        rebased_bundle = WritingResearchCallbackBundleV1.model_validate(rebased)
    except (TypeError, ValueError) as exc:
        report["failures"].append(f"bundle_rebase_invalid:{exc.__class__.__name__}")
        return report
    report["bundle"] = rebased_bundle.model_dump(mode="json")
    report["reused_fulfilled_callback_ids"] = reused
    return report


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
        # New publication runs give Editor a closed WriterView. Proposition
        # preservation and final reverse validation own semantic safety there;
        # retaining the lexical surface of low-level atomic claims would block
        # the intended code-trace -> academic-language rewrite. Legacy runs
        # without proposition bindings keep the old conservative check.
        if output.rendered_proposition_ids or output.deferred_proposition_ids:
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
