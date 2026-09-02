from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from code2paper.agentic.equation_claims import EquationClaimSetV1, EquationClaimV1, compile_equation_claims
from code2paper.agentic.authoring_projection import build_authoring_projection
from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    EvidencePacketV3,
    EvidencePacketSetV3,
    EvidenceSpanV3,
    GENERIC_RESEARCH_PRODUCER_VERSION,
    SemanticStageGroupV1,
)
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2, IntentObligationV2
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    ConfigurationClaimV1,
    MethodArgumentUnitV1,
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
    ObligationMoveAssignmentV1,
    SectionArgumentGraphV1,
    SectionArgumentMoveV1,
    SectionParagraphPlanV1,
    WritingResearchCallbackArtifactV1,
    WritingResearchCallbackBundleV1,
    WritingResearchRequestV1,
)
from code2paper.agentic.method_architect import build_method_section_plan
from code2paper.agentic.obligation_fact_alignment import ObligationAlignmentV1, ObligationCoverageReportV2
from code2paper.agentic.publication_method_writer import (
    _audit_proposition_alignment,
    _build_editor_local_ledgers,
    _callback_artifact_prompt_payload,
    _editor_claim_regressions,
    _editor_rendered_proposition_ids,
    _select_safe_editor_section_transactions,
    _load_valid_paragraph_checkpoint,
    _load_section_checkpoint,
    _sentence_validated_concept_claim_ids,
    _compose_candidate_markdown,
    _dedupe_writing_research_requests,
    _restore_callback_request_sidecar,
    _write_paragraph_checkpoint,
    _write_section_checkpoint,
    fulfill_writing_research_callbacks,
    run_publication_method_writer,
)


def test_candidate_view_keeps_invalid_transaction_body_but_excludes_malformed_binding(
    tmp_path: Path,
) -> None:
    plan = SimpleNamespace(sections=(
        SimpleNamespace(section_id="MA-S1"),
        SimpleNamespace(section_id="MA-S2"),
        SimpleNamespace(section_id="MA-S3"),
    ))
    outputs = {
        "MA-S1": PublicationMethodSectionOutputV1(
            section_id="MA-S1", section_markdown="## Overview\n\nAccepted body."
        ),
        "MA-S2": PublicationMethodSectionOutputV1(
            section_id="MA-S2", section_markdown="## Mechanism\n\nInvalid witness body."
        ),
        "MA-S3": PublicationMethodSectionOutputV1(
            section_id="MA-S3", section_markdown="Malformed binding body."
        ),
    }
    candidate = _compose_candidate_markdown(
        accepted=[("MA-S1", "## Overview\n\nAccepted body.", "sha256:s1")],
        plan=plan,
        section_outputs=outputs,
        excluded_section_ids=("MA-S3",),
    )
    assert "Accepted body." in candidate
    assert "Invalid witness body." in candidate
    assert "Malformed binding body." not in candidate


def test_paragraph_checkpoint_keeps_valid_sibling_of_failed_section(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "publication_section_checkpoint_v1.json"
    assessment = tmp_path / "publication_paragraph_transaction_assessments_v1.json"
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        paragraphs=[
            PublicationMethodParagraphOutputV1(
                paragraph_id="paragraph:MA-S1:valid",
                paragraph_markdown="A valid paragraph.",
            ),
            PublicationMethodParagraphOutputV1(
                paragraph_id="paragraph:MA-S1:invalid",
                paragraph_markdown="A failed paragraph.",
            ),
        ],
    )
    assessment.write_text(json.dumps({
        "assessments": [
            {
                "section_id": "MA-S1",
                "paragraph_id": "paragraph:MA-S1:valid",
                "valid": True,
                "content_digest": "sha256:valid-assessment",
            },
            {
                "section_id": "MA-S1",
                "paragraph_id": "paragraph:MA-S1:invalid",
                "valid": False,
                "content_digest": "sha256:invalid-assessment",
            },
        ],
        "content_digest": "sha256:assessments",
    }))

    _write_paragraph_checkpoint(
        checkpoint,
        section_outputs={"MA-S1": output},
        assessment_path=assessment,
    )

    manifest = json.loads(checkpoint.read_text())
    assert "MA-S1:paragraph:MA-S1:valid" in manifest["paragraphs"]
    assert "MA-S1:paragraph:MA-S1:invalid" not in manifest["paragraphs"]
    loaded = _load_valid_paragraph_checkpoint(
        out_root=tmp_path,
        artifact_paths={"publication_paragraph_checkpoint_v1": str(checkpoint)},
        resume_section_ids=("MA-S1",),
    )
    assert set(loaded) == {("MA-S1", "paragraph:MA-S1:valid")}
from code2paper.agentic.method_proposition_models import (
    MethodPropositionSetV1,
    MethodPropositionV1,
    PropositionBindingSidecarV1,
    PropositionBindingV1,
)
from code2paper.agentic.method_concept_card_models import (
    ConceptCardBindingV1,
    ConceptCardEvidenceVerdictV1,
    ConceptCardFieldJudgmentV1,
    MethodConceptCardSetV1,
    MethodConceptCardV1,
)
from code2paper.agentic.trust_contracts import (
    FinalAtomicClaim,
    FinalTextClaims,
    TextClaimEvidenceVerdict,
    TextEvidenceValidationReport,
)
from code2paper.agentic.cross_section_editor import CrossSectionEditor
from code2paper.agentic.publication_quality import (
    PublicationQualityReportV1,
    _phrase_present,
    evaluate_publication_method_quality,
)
from code2paper.agentic.final_text_authorship import ledger_from_section_outputs
from code2paper.agentic.cross_section_editor import (
    CrossSectionEditResultV1,
    SectionTextPatchV1,
    edit_sections,
)
from code2paper.llm.response_schemas import (
    PublicationMethodParagraphOutputV1,
    PublicationMethodSectionOutputV1,
)
from code2paper.agentic.v3_runtime import write_d25_method_research_artifacts, write_v3_evidence_artifacts
from code2paper.agentic.writer_research_router import route_writing_research_request
from code2paper.llm.client import LLMResponse
from code2paper.schemas import ClaimEvidenceMap, LLMConfig, LLMProvider, MethodEvidence


_COMPLETED_CORE_MOVES = [
    "problem_or_local_context",
    "design_objective",
    "mechanism_overview",
    "algorithm_or_data_flow",
    "implementation_realization",
    "configuration_and_branches",
    "inference_and_output",
]

def _completed_moves(binding: dict) -> list[str]:
    """Complete exactly the anchored required moves of the section payload."""
    return list(binding.get("anchored_required_rhetorical_moves") or ())


def test_section_checkpoint_rejects_changed_or_missing_proposition_set_digest(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "publication_section_checkpoint_v1.json"
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown="## Overview\n\nThe descriptor combines the authorized attributes.",
        rendered_proposition_ids=["MP-1"],
    )
    _write_section_checkpoint(
        checkpoint,
        section_outputs={"MA-S1": output},
        section_response_refs={"MA-S1": "sha256:writer"},
        proposition_set_digest="sha256:" + "a" * 64,
    )
    artifact_paths = {"publication_section_checkpoint_v1": str(checkpoint)}
    loaded, _ = _load_section_checkpoint(
        out_root=tmp_path,
        artifact_paths=artifact_paths,
        resume_section_ids=("MA-S1",),
        proposition_set_digest="sha256:" + "a" * 64,
    )
    assert loaded == {"MA-S1": output}
    changed, _ = _load_section_checkpoint(
        out_root=tmp_path,
        artifact_paths=artifact_paths,
        resume_section_ids=("MA-S1",),
        proposition_set_digest="sha256:" + "b" * 64,
    )
    assert changed is None
    omitted, _ = _load_section_checkpoint(
        out_root=tmp_path,
        artifact_paths=artifact_paths,
        resume_section_ids=("MA-S1",),
        proposition_set_digest="",
    )
    assert omitted is None


def test_proposition_is_validated_only_when_reverse_verdict_is_supported(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    plan = MethodSectionPlanV2.model_validate_json(
        Path(paths["method_section_plan_v2"]).read_text()
    )
    proposition = MethodPropositionV1(
        proposition_id="MP-READ",
        origin="repository_evidence",
        evidence_lane="repository_verified",
        may_enter_verified=True,
        reader_subject="the encoder",
        transformation="reads the configured input",
    )
    proposition_set = MethodPropositionSetV1(
        repo_snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        propositions=(proposition,),
        binding_sidecar_digest="sha256:" + "a" * 64,
    )
    unit = plan.argument_units[0].model_copy(update={
        "proposition_ids": (proposition.proposition_id,),
        "positive_proposition_ids": (proposition.proposition_id,),
        "proposition_order": (proposition.proposition_id,),
    })
    plan = plan.model_copy(update={"argument_units": (unit,)})
    sentence = "The encoder reads the configured input."
    final_claims = FinalTextClaims(
        input_text_digest="sha256:text",
        atomic_claims=[FinalAtomicClaim(
            atomic_claim_id="FAC-1",
            unit_id="FU-1",
            text=sentence,
            normalized_text="the encoder reads the configured input",
            line_start=3,
            line_end=3,
            char_start=12,
            char_end=12 + len(sentence),
            claim_digest="sha256:fac",
        )],
    )
    claims_path = tmp_path / "final_claims.json"
    claims_path.write_text(final_claims.model_dump_json(), encoding="utf-8")

    def report(status: str) -> TextEvidenceValidationReport:
        return TextEvidenceValidationReport(
            status="passed" if status == "supported" else "failed",
            input_text_digest="sha256:text",
            projection_digest="sha256:projection",
            checked_factual_claims=1,
            supported_claims=int(status == "supported"),
            unsupported_claims=int(status == "unsupported"),
            verdicts=[TextClaimEvidenceVerdict(
                atomic_claim_id="FAC-1",
                status=status,
            )],
        )

    validation_path = tmp_path / "validation.json"
    validation_path.write_text(report("unsupported").model_dump_json(), encoding="utf-8")
    alignment = _audit_proposition_alignment(
        accepted=[("MA-S1", f"## Encoder\n\n{sentence}", "sha256:writer")],
        plan=plan,
        propositions=proposition_set,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none", cache=False),
        validation_paths={
            "final_text_claims": str(claims_path),
            "text_evidence_validation": str(validation_path),
        },
    )
    row = alignment["sections"][0]
    assert row["rendered_proposition_ids"] == ["MP-READ"]
    assert row["validated_proposition_ids"] == []

    validation_path.write_text(report("supported").model_dump_json(), encoding="utf-8")
    supported = _audit_proposition_alignment(
        accepted=[("MA-S1", f"## Encoder\n\n{sentence}", "sha256:writer")],
        plan=plan,
        propositions=proposition_set,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none", cache=False),
        validation_paths={
            "final_text_claims": str(claims_path),
            "text_evidence_validation": str(validation_path),
        },
    )
    assert supported["sections"][0]["validated_proposition_ids"] == ["MP-READ"]


def test_publication_writer_requires_digest_matching_proposition_sidecar(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    proposition = MethodPropositionV1(
        proposition_id="MP-READ",
        origin="repository_evidence",
        evidence_lane="repository_verified",
        may_enter_verified=True,
        reader_subject="the encoder",
        transformation="reads the configured input",
    )
    sidecar = PropositionBindingSidecarV1(
        repo_snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        bindings=(PropositionBindingV1(
            proposition_id="MP-READ",
            claim_ids=("claim-read",),
            fact_ids=("fact-read",),
            span_ids=("span:encoder.py:1:2",),
        ),),
    )
    proposition_set = MethodPropositionSetV1(
        repo_snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        propositions=(proposition,),
        binding_sidecar_digest=sidecar.content_digest,
    )
    proposition_path = tmp_path / "method_propositions_v1.json"
    proposition_path.write_text(proposition_set.model_dump_json(), encoding="utf-8")
    paths["method_propositions_v1"] = str(proposition_path)

    missing, _outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none", cache=False),
    )
    assert "binding sidecar is missing" in missing.blocked_reason

    sidecar_path = tmp_path / "method_proposition_bindings_v1.json"
    mismatched = sidecar.model_copy(update={
        "content_digest": "sha256:" + "b" * 64,
    })
    # model_copy deliberately preserves an invalid supplied digest so the
    # loader, rather than the fixture constructor, exercises fail-closed replay.
    sidecar_path.write_text(mismatched.model_dump_json(), encoding="utf-8")
    paths["method_proposition_bindings_v1"] = str(sidecar_path)
    invalid, _outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none", cache=False),
    )
    assert invalid.blocked_reason.startswith("publication_writer_inputs_invalid:")
    assert "sidecar digest mismatch" in invalid.blocked_reason


def test_method_architect_merges_identical_stage_headings_without_merging_argument_units() -> None:
    claims = tuple(
        AtomicClaimV3(
            claim_id=f"claim-{index}",
            canonical_text=f"The implementation transforms input {index}.",
            fact_ids=[f"fact-{index}"],
            covers_obligation_ids=[f"obl-{index}"],
            direct_evidence_ids=[f"span:module.py:{index}:{index}"],
            allowed_wording_boundary=f"input {index} transformation only",
            canonical_identity=f"sha256:claim-{index}",
            status="supported",
        )
        for index in (1, 2)
    )
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=list(claims),
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id=f"stage-{index}",
                name="Implementation stage 1",
                purpose=f"Explain obligation {index}.",
                ordered_claim_ids=[f"claim-{index}"],
                covers_obligation_ids=[f"obl-{index}"],
                organization_priority=index,
            )
            for index in (1, 2)
        ],
        content_digest="sha256:claims",
    )

    plan = build_method_section_plan(claims=claim_set)

    assert len(plan.sections) == 1
    assert plan.sections[0].heading == "Implementation stage 1"
    assert plan.sections[0].argument_unit_ids == ("MA-S1:unit-1", "MA-S1:unit-2")
    assert [unit.claim_ids for unit in plan.argument_units] == [("claim-1",), ("claim-2",)]
    assert plan.sections[0].required_moves
    assert all(
        set(move.argument_unit_ids) <= set(plan.sections[0].argument_unit_ids)
        for move in plan.sections[0].moves
    )


def test_method_architect_does_not_authorize_code_as_design_objective() -> None:
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:authority-lanes",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[AtomicClaimV3(
            claim_id="claim-operation",
            canonical_text="The implementation reads the input.",
            fact_ids=["fact-operation"],
            covers_obligation_ids=["obl-operation"],
            direct_evidence_ids=["span:module.py:1:2"],
            allowed_wording_boundary="reads input only",
            canonical_identity="sha256:operation",
            status="supported",
        )],
        semantic_stage_groups=[SemanticStageGroupV1(
            stage_id="stage-operation",
            name="Input handling",
            purpose="Explain the input handling.",
            ordered_claim_ids=["claim-operation"],
            covers_obligation_ids=["obl-operation"],
        )],
        content_digest="sha256:authority-claims",
    )

    plan = build_method_section_plan(claims=claim_set)
    moves = {item.move: item for item in plan.sections[0].moves}

    assert moves["problem_or_local_context"].allowed_authority_lanes[0] == "author_attested"
    assert moves["design_objective"].allowed_authority_lanes[0] == "author_attested"
    assert "executable_hard" not in moves["design_objective"].allowed_authority_lanes
    assert moves["transition_to_next_section"].allowed_authority_lanes == (
        "expository_bridge",
    )

    request = WritingResearchRequestV1(
        request_id="request:objective",
        section_id=plan.sections[0].section_id,
        argument_unit_id=plan.sections[0].argument_unit_ids[0],
        missing_rhetorical_move="design_objective",
        exact_question="Which author-confirmed objective should be stated?",
        required_authority_lane="author_attested",
    )
    route = route_writing_research_request(request)
    assert route.owner == "author_confirmation_queue"


def test_duplicate_writing_callbacks_merge_missing_parts_by_target_scope() -> None:
    first = WritingResearchRequestV1(
        request_id="request:first",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit-1",
        missing_rhetorical_move="algorithm_or_data_flow",
        exact_question="Which implementation detail is missing?",
        required_authority_lane="author_attested",
        missing_parts=("input",),
        evidence_refs_used=("span:input",),
        mandatory_missing_slots=("transformation",),
    )
    second = first.model_copy(update={
        "request_id": "request:second",
        "missing_parts": ("output",),
        "evidence_refs_used": ("span:output",),
    })

    merged = _dedupe_writing_research_requests((first, second))

    assert len(merged) == 1
    assert merged[0].request_id == "request:first"
    assert merged[0].missing_parts == ("input", "output")
    assert merged[0].evidence_refs_used == ("span:input", "span:output")


def test_callback_request_sidecar_restores_internal_targets_and_placeholder_terms() -> None:
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown="## Method\n\nBody.",
        new_research_requests=[{
            "request_id": "request:MA-S1:mechanism_overview",
            "section_id": "MA-S1",
            "argument_unit_id": "MA-S1:unit-1",
            "missing_rhetorical_move": "mechanism_overview",
            "exact_question": "Which implementation span is still needed?",
            "required_authority_lane": "executable_hard",
            "candidate_symbols_or_terms": [":"],
            "target_brief_ids": [":"],
            "target_clause_ids": [","],
            "status": "open",
        }],
    )

    restored, operations = _restore_callback_request_sidecar(
        output=output,
        callback_request_prototypes=[{
            "missing_rhetorical_move": "mechanism_overview",
            "candidate_symbols_or_terms": ["Encoder.forward"],
            "target_brief_ids": ["brief:story:mechanism"],
            "target_clause_ids": ["clause:mechanism"],
            "brief_binding": [{
                "missing_parts": ["state update"],
                "evidence_refs_used": ["span:encoder.py:10:12"],
            }],
        }],
    )

    request = restored.new_research_requests[0]
    assert request["candidate_symbols_or_terms"] == ["Encoder.forward"]
    assert request["target_brief_ids"] == ["brief:story:mechanism"]
    assert request["target_clause_ids"] == ["clause:mechanism"]
    assert request["missing_parts"] == ["state update"]
    assert request["evidence_refs_used"] == ["span:encoder.py:10:12"]
    assert "restore_callback_sidecar:target_brief_ids" in operations
    assert "restore_callback_sidecar:candidate_symbols_or_terms" in operations


def test_callback_request_sidecar_does_not_cross_bind_same_move_between_units() -> None:
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown="## Method\n\nBody.",
        new_research_requests=[{
            "request_id": "request:MA-S1:unit-2",
            "section_id": "MA-S1",
            "argument_unit_id": "MA-S1:unit-2",
            "missing_rhetorical_move": "mechanism_overview",
            "exact_question": "Which implementation span is still needed?",
            "required_authority_lane": "executable_hard",
            "candidate_symbols_or_terms": [":"],
            "status": "open",
        }],
    )

    restored, operations = _restore_callback_request_sidecar(
        output=output,
        callback_request_prototypes=[
            {
                "missing_rhetorical_move": "mechanism_overview",
                "argument_unit_id": "MA-S1:unit-1",
                "target_brief_ids": ["brief:unit-1"],
            },
            {
                "missing_rhetorical_move": "mechanism_overview",
                "argument_unit_id": "MA-S1:unit-2",
                "target_brief_ids": ["brief:unit-2"],
            },
        ],
    )

    request = restored.new_research_requests[0]
    assert request["target_brief_ids"] == ["brief:unit-2"]
    assert "restore_callback_sidecar:target_brief_ids" in operations


def test_intent_stage_groups_are_an_authoring_allow_list() -> None:
    claims = [
        AtomicClaimV3(
            claim_id="claim-stage",
            canonical_text="The ranker sorts passage scores.",
            fact_ids=["fact-stage"],
            covers_obligation_ids=["obl-stage"],
            direct_evidence_ids=["span:rank.py:1:2"],
            allowed_wording_boundary="sorting only",
            canonical_identity="sha256:stage",
        ),
        AtomicClaimV3(
            claim_id="claim-review-only",
            canonical_text="The ranker sorts a diagnostic score vector.",
            fact_ids=["fact-review"],
            covers_obligation_ids=["obl-rationale"],
            direct_evidence_ids=["span:rank.py:3:4"],
            allowed_wording_boundary="diagnostic sorting only",
            canonical_identity="sha256:review",
        ),
    ]
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:intent-plan",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=claims,
        semantic_stage_groups=[SemanticStageGroupV1(
            stage_id="SG-INTENT-01-stage",
            name="Passage ranking",
            purpose="Rank passages by score.",
            ordered_claim_ids=["claim-stage"],
            covers_obligation_ids=["obl-stage"],
        )],
        content_digest="sha256:claims",
    )

    plan = build_method_section_plan(claims=claim_set)

    assert [section.heading for section in plan.sections] == ["Passage ranking"]
    assert [claim_id for unit in plan.argument_units for claim_id in unit.claim_ids] == [
        "claim-stage"
    ]


def _artifacts(tmp_path: Path) -> dict[str, str]:
    fact = CodeFactV1(
        fact_id="fact-read",
        subject="sym:encoder",
        predicate="reads",
        object="configured_input",
        scope="sym:encoder",
        direct_span_ids=["span:encoder.py:1:2"],
        semantic_context=["READ", "config_access"],
        exact_source_digest="sha256:source",
        canonical_identity="sha256:fact",
        validation_status="supported",
    )
    packets = EvidencePacketSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        packets=[],
        content_digest="sha256:packets",
    )
    facts = CodeFactSetV1(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        facts=[fact],
        content_digest="sha256:facts",
    )
    claim = AtomicClaimV3(
        claim_id="claim-read",
        canonical_text="The encoder reads the configured input.",
        fact_ids=[fact.fact_id],
        covers_obligation_ids=["obl-main"],
        direct_evidence_ids=fact.direct_span_ids,
        allowed_wording_boundary="encoder reads configured input only",
        canonical_identity="sha256:claim",
        status="supported",
    )
    claims = AtomicClaimSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id=packets.repo_snapshot_id,
        project_tree_hash=packets.project_tree_hash,
        evidence_packet_digest=packets.content_digest,
        code_fact_digest=facts.content_digest,
        claims=[claim],
        content_digest="sha256:claims",
    )
    equations, _ = compile_equation_claims(
        [], facts,
        repo_snapshot_id=facts.repo_snapshot_id,
        project_tree_hash=facts.project_tree_hash,
    )
    paths = write_v3_evidence_artifacts(
        tmp_path,
        packet_set=packets,
        fact_set=facts,
        claim_set=claims,
        equation_set=equations,
    )
    graph = IntentObligationGraphV2(
        method_goal="Explain the encoder.",
        obligations=[IntentObligationV2(
            obligation_id="obl-main",
            kind="method_mainline",
            priority="must_cover",
            source_field="method_mainline",
            author_text="Explain the encoder.",
        )],
    )
    coverage = ObligationCoverageReportV2(
        intent_graph_digest=graph.content_digest,
        fact_set_digest=facts.content_digest,
        claim_set_digest=claims.content_digest,
        items=[ObligationAlignmentV1(
            obligation_id="obl-main",
            obligation_kind="method_mainline",
            obligation_priority="must_cover",
            matched_claim_ids=(claim.claim_id,),
            coverage_status="supported",
            rationale="generic fact and claim",
        )],
        must_cover_count=1,
        terminal_must_cover_count=1,
        supported_must_cover_count=1,
    )
    paths.update(write_d25_method_research_artifacts(
        tmp_path,
        intent_graph=graph,
        coverage_report=coverage,
        fact_set=facts,
        claim_set=claims,
        equation_set=equations,
        method_name="Encoder",
    ))
    return paths



def _with_unverified_gap(paths: dict[str, str]) -> MethodCompletenessMatrixV1:
    """Completeness matrix with a claim-bearing unverified gap row.

    The claim-bearing row places via exact claim IDs onto the fixture unit,
    so the limitations move is required, unanchored, and locally owned
    (executable_hard) with exact semantic candidates.
    """

    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    return MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    ).model_copy(update={
        "items": (
            *MethodCompletenessMatrixV1.model_validate_json(
                Path(paths["method_completeness_matrix_v1"]).read_text()
            ).items,
            MethodCompletenessItemV1(
                obligation_id="O-MAIN-LOCAL",
                status="unverified_by_repository",
                claim_ids=(claims.claims[0].claim_id,),
                importance="critical",
                next_action="run scoped repository research",
                reason="No supported code fact covers the remaining behavior.",
            ),
        ),
    })



def _two_section_gap_artifacts(tmp_path: Path) -> dict[str, str]:
    """Two-section fixture with distinct units and a locally owned gap.

    MA-S1 owns the original claim (the unverified gap row binds to it, so its
    limitations move is open at executable_hard); MA-S2 owns a second claim
    and has no gap, so it completes and must stay byte-identical on resume.
    """

    paths = _artifacts(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    original = claims.claims[0]
    second = original.model_copy(update={
        "claim_id": "claim-read-2",
        "canonical_identity": "sha256:claim-2",
    })
    claims = claims.model_copy(update={
        "claims": (*claims.claims, second),
    })
    Path(paths["atomic_claims_v3"]).write_text(
        claims.model_dump_json(indent=2), encoding="utf-8"
    )
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    ).model_copy(update={
        "items": (
            *MethodCompletenessMatrixV1.model_validate_json(
                Path(paths["method_completeness_matrix_v1"]).read_text()
            ).items,
            MethodCompletenessItemV1(
                obligation_id="O-MAIN-LOCAL",
                status="unverified_by_repository",
                claim_ids=(original.claim_id,),
                importance="critical",
                next_action="run scoped repository research",
                reason="No supported code fact covers the remaining behavior.",
            ),
            # MA-S2 owns a second supported claim; it needs its own positive
            # completeness row so the new product readiness gate binds it
            # (an unbound positive without a caveat route is
            # ``blocked_for_safety`` by contract).
            MethodCompletenessItemV1(
                obligation_id="O-MAIN-S2",
                status="supported_by_repository",
                claim_ids=(second.claim_id,),
                importance="critical",
                next_action="",
                reason="Second output stage is repository supported.",
            ),
        ),
    })
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )
    unit_one = MethodArgumentUnitV1(
        argument_unit_id="MA-S1:unit",
        section_role="stage",
        research_question="How is the input prepared?",
        claim_ids=(original.claim_id,),
        authority_lanes=("executable_hard",),
    )
    unit_two = MethodArgumentUnitV1(
        argument_unit_id="MA-S2:unit",
        section_role="stage",
        research_question="How is the output produced?",
        claim_ids=(second.claim_id,),
        authority_lanes=("executable_hard",),
    )
    section_one = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Feature preparation",
        reader_question="How is the input prepared?",
        argument_unit_ids=(unit_one.argument_unit_id,),
        moves=(),
    )
    section_two = SectionArgumentGraphV1(
        section_id="MA-S2",
        heading="Output generation",
        reader_question="How is the output produced?",
        argument_unit_ids=(unit_two.argument_unit_id,),
        moves=(),
    )
    plan = MethodSectionPlanV2.model_validate_json(
        Path(paths["method_section_plan_v2"]).read_text()
    ).model_copy(update={
        "argument_units": (unit_one, unit_two),
        "sections": (section_one, section_two),
    })
    Path(paths["method_section_plan_v2"]).write_text(
        plan.model_dump_json(indent=2), encoding="utf-8"
    )
    return paths


def _config() -> LLMConfig:
    return LLMConfig(
        provider=LLMProvider.NONE,
        model="fixture-writer",
        max_output_tokens=8192,
        cache=False,
    )


def test_publication_writer_emits_three_visible_deliverables_and_authorship_ledger(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        grounding = request.input_payload["grounding_contract"]
        assert grounding["positive_fact_source"] == "argument_flow_semantic_frames_only"
        assert "design_objective" not in grounding["organization_only_fields"]
        assert grounding["unanchored_move_action"].startswith("emit_one_scoped")
        assert "problem_or_local_context" in grounding["expository_bridge_allowed_moves"]
        assert request.input_payload["formalization"]["symbols"]
        # The Architect's reader question/design objective stay in the
        # planning plane; the model receives only the closed content anchors.
        assert "reader_question" not in request.input_payload["section"]
        assert "design_objective" not in request.input_payload["section"]
        assert all(
            "research_question" not in unit and "design_objective" not in unit
            for unit in request.input_payload["argument_units"]
        )
        # The typed semantic frame is the writing basis and the constraint
        # channel is validation-only: no inventory sentence plan is present.
        flow = request.input_payload["argument_flow"]
        assert flow["semantic_frames"]
        assert all(
            "content_digest" in frame for frame in flow["semantic_frames"]
        )
        paragraph_plan = request.input_payload["paragraph_plan"]
        assert any(item["ordered_semantic_slot_ids"] for item in paragraph_plan)
        assert any(item["paragraph_role"] != "overview" for item in paragraph_plan)
        constraints = request.input_payload["validation_constraints"]
        assert constraints["claims"] and all(
            item["validation_only"] for item in constraints["claims"]
        )
        assert "authorized_sentence_anchors" not in request.input_payload
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
                "self_identified_risks": [],
            }),
            response_hash="sha256:writer-response",
            finish_reason="stop",
            token_usage={"completion_tokens": 120},
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    assert Path(outputs["repository_verified_method"]).read_text().startswith("## Encoder")
    assert Path(outputs["publication_candidate_method"]).read_text() == Path(
        outputs["repository_verified_method"]
    ).read_text()
    assert Path(outputs["author_review_candidates"]).is_file()
    persisted_plan = json.loads(Path(outputs["method_section_plan_v2"]).read_text())
    assert any(
        paragraph["ordered_semantic_slot_ids"]
        for section in persisted_plan["sections"]
        for paragraph in section.get("paragraphs", ())
    )
    ledger = json.loads(Path(outputs["final_text_authorship_ledger_v1"]).read_text())
    assert ledger["hard_gate_passed"] is True
    assert ledger["spans"][0]["owner"] == "writer"
    quality = json.loads(Path(outputs["publication_quality_report_v1"]).read_text())
    assert quality["safety"]["final_text_validation_status"] == "pending"


def test_publication_writer_blocks_corrupt_frozen_inputs_without_raising(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    Path(paths["atomic_claims_v3"]).write_text("{not-json", encoding="utf-8")

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=lambda *_args: (_ for _ in ()).throw(AssertionError("must not call")),
    )

    assert result.status == "blocked"
    assert result.blocked_reason.startswith("publication_writer_inputs_invalid:")
    assert set(outputs) == {"publication_writer_result_v1"}
    persisted = json.loads(Path(outputs["publication_writer_result_v1"]).read_text())
    assert persisted["status"] == "blocked"


def test_publication_writer_blocks_invalid_callback_sidecar_before_new_generation(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    callback_path = tmp_path / "invalid-callback-bundle.json"
    callback_path.write_text("{not-json", encoding="utf-8")
    paths["writing_research_callback_artifacts_v1"] = str(callback_path)

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=lambda *_args: (_ for _ in ()).throw(AssertionError("must not call")),
    )

    assert result.status == "blocked"
    assert result.blocked_reason == "writing_research_callback_bundle_invalid"
    assert set(outputs) == {"publication_writer_result_v1"}


def test_publication_writer_blocks_malformed_explicit_callback_artifact(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        research_callback_artifacts={"request:unknown": ({"validated": False},)},
        llm_caller=lambda *_args: (_ for _ in ()).throw(AssertionError("must not call")),
    )

    assert result.status == "blocked"
    assert result.blocked_reason.startswith("writing_research_callback_artifacts_invalid:")
    assert set(outputs) == {"publication_writer_result_v1"}


def test_callback_fulfillment_preserves_one_shot_resume_section(tmp_path: Path) -> None:
    request = WritingResearchRequestV1(
        request_id="request:callback",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="inference_and_output",
        exact_question="Which return span is authoritative?",
        required_authority_lane="executable_hard",
    )
    bundle_path = tmp_path / "writing_research_callback_artifacts_v1.json"
    bundle_path.write_text(
        WritingResearchCallbackBundleV1(
            requests=(request,),
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    artifact = WritingResearchCallbackArtifactV1(
        artifact_id="artifact:return",
        request_id=request.request_id,
        section_id=request.section_id,
        argument_unit_id=request.argument_unit_id,
        authority_lane=request.required_authority_lane,
        artifact_ref="span:encoder.py:2:2",
        artifact_digest="sha256:return",
        validated=True,
    )

    fulfilled = fulfill_writing_research_callbacks(
        bundle_path,
        {request.request_id: (artifact,)},
    )

    assert fulfilled.requests[0].status == "fulfilled"
    assert fulfilled.resume_section_ids == ("MA-S1",)
    assert fulfilled.artifacts[request.request_id][0].artifact_id == artifact.artifact_id


def test_callback_bundle_digest_tamper_blocks_fulfillment(tmp_path: Path) -> None:
    request = WritingResearchRequestV1(
        request_id="request:digest",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="inference_and_output",
        exact_question="Which return span is authoritative?",
        required_authority_lane="executable_hard",
    )
    bundle_path = tmp_path / "writing_research_callback_artifacts_v1.json"
    bundle_path.write_text(
        WritingResearchCallbackBundleV1(requests=(request,)).model_dump_json(indent=2),
        encoding="utf-8",
    )
    raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    raw["requests"][0]["exact_question"] = "tampered"
    bundle_path.write_text(json.dumps(raw), encoding="utf-8")

    try:
        fulfill_writing_research_callbacks(bundle_path, {})
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("tampered callback bundle must fail closed")


def test_file_backed_callback_preview_is_digest_bound_and_bounded(tmp_path: Path) -> None:
    payload_path = tmp_path / "author-confirmation.json"
    payload_path.write_text('{"objective":"use the verified feature path"}\n', encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(payload_path.read_bytes()).hexdigest()
    artifact = WritingResearchCallbackArtifactV1(
        artifact_id="artifact:author-confirmation",
        request_id="request:author-confirmation",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        authority_lane="author_attested",
        artifact_ref=str(payload_path),
        artifact_digest=digest,
        validated=True,
    )

    prompt_payload, failure = _callback_artifact_prompt_payload(
        artifact,
        base_dir=tmp_path,
        max_preview_chars=12,
    )

    assert failure == ""
    assert prompt_payload["artifact_preview"] == '{"objective"'
    assert prompt_payload["artifact_preview_truncated"] is True

    tampered = payload_path.with_name("tampered.json")
    tampered.write_text("different\n", encoding="utf-8")
    tampered_artifact = artifact.model_copy(update={"artifact_ref": str(tampered)})
    _payload, tamper_failure = _callback_artifact_prompt_payload(
        tampered_artifact,
        base_dir=tmp_path,
    )
    assert tamper_failure == "artifact_digest_mismatch"


def test_missing_file_backed_callback_ref_fails_closed_but_opaque_span_survives(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "owner-confirmation.json"
    artifact = WritingResearchCallbackArtifactV1(
        artifact_id="artifact:missing",
        request_id="request:missing",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        authority_lane="author_attested",
        artifact_ref=str(missing),
        artifact_digest="sha256:" + "0" * 64,
        validated=True,
    )
    _payload, failure = _callback_artifact_prompt_payload(
        artifact,
        base_dir=tmp_path,
    )
    assert failure == "artifact_ref_missing"

    opaque = artifact.model_copy(update={
        "artifact_id": "artifact:span",
        "artifact_ref": "span:src/encoder.py:2:2",
    })
    opaque_payload, opaque_failure = _callback_artifact_prompt_payload(
        opaque,
        base_dir=tmp_path,
    )
    assert opaque_failure == ""
    assert "artifact_preview" not in opaque_payload


def test_writing_research_request_requires_nonempty_exact_question() -> None:
    try:
        WritingResearchRequestV1(
            request_id="request:empty-question",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="inference_and_output",
            exact_question="",
            required_authority_lane="executable_hard",
        )
    except ValueError as exc:
        assert "binding text must not be empty" in str(exc)
    else:
        raise AssertionError("empty callback questions must fail closed")


def test_publication_writer_rejects_unknown_binding_without_publishing_candidate(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)

    def caller(_config, request):
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "An unbound method statement.",
                "used_argument_unit_ids": ["unknown-unit"],
                "used_claim_ids": ["unknown-claim"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
            }),
            response_hash="sha256:invalid-writer-response",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "blocked"
    assert any("unknown_argument_units" in item for item in result.binding_failures)
    assert "publication_candidate_method" not in outputs
    assert not (tmp_path / "artifacts" / "06_authoring" / "publication_candidate_method.md").exists()


def test_publication_writer_rejects_duplicate_binding_ids(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "A bound method statement.",
                "used_argument_unit_ids": [binding["used_argument_unit_ids"][0]] * 2,
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:duplicate-binding-response",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "blocked"
    assert any("duplicate_argument_units" in item for item in result.binding_failures)
    assert "publication_candidate_method" not in outputs


def test_section_checkpoint_relative_ref_survives_run_root_copy(tmp_path: Path) -> None:
    source = tmp_path / "source"
    checkpoint = source / "artifacts" / "06_authoring" / "publication_section_checkpoint_v1.json"
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown="The encoder reads the configured input.",
    )
    _write_section_checkpoint(
        checkpoint,
        section_outputs={"MA-S1": output},
        section_response_refs={"MA-S1": "sha256:writer-v1"},
    )
    target = tmp_path / "target"
    shutil.copytree(source, target)

    loaded, refs = _load_section_checkpoint(
        out_root=target,
        artifact_paths={
            "publication_section_checkpoint_v1": str(
                target / "artifacts" / "06_authoring" / "publication_section_checkpoint_v1.json"
            ),
        },
        resume_section_ids=("MA-S1",),
    )

    assert loaded is not None
    assert loaded["MA-S1"].section_markdown == output.section_markdown
    assert refs == {"MA-S1": "sha256:writer-v1"}
    manifest = json.loads(checkpoint.read_text())
    assert not Path(manifest["sections"]["MA-S1"]["output_ref"]).is_absolute()


def test_publication_quality_gate_blocks_safe_but_argument_incomplete_text(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": ["mechanism_overview"],
            }),
            response_hash="sha256:writer-incomplete",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    report = json.loads(Path(outputs["publication_quality_report_v1"]).read_text())
    assert report["safety"]["authorship_gate_passed"] is True
    assert report["safety"]["hard_gate_passed"] is False
    assert report["utility"]["utility_gate_passed"] is False
    assert any(
        issue["code"] == "required_argument_move_missing"
        and issue["scope"] == "section"
        for issue in report["issues"]
    )


def test_publication_writer_runs_final_reverse_validation_when_frozen_v3_inputs_are_bound(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    method_path = tmp_path / "method_evidence.json"
    method_path.write_text(
        MethodEvidence(
            project_id="fixture",
            method_name="Encoder",
            method_goal="Describe the encoder.",
            implementation_scope="fixture repository",
        ).model_dump_json(),
        encoding="utf-8",
    )
    paths["method_evidence"] = str(method_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-reverse-validation",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    # A failed reverse validation blocks *verified* inclusion, never the
    # candidate document: the unsupported sentence is review-linked, the
    # verified document drops it, and the run stays incomplete.
    assert result.status == "incomplete"
    assert result.incomplete_section_ids == ()
    assert Path(outputs["final_text_claims"]).is_file()
    validation = json.loads(Path(outputs["text_evidence_validation"]).read_text())
    assert validation["status"] == "failed"
    quality = json.loads(Path(outputs["publication_quality_report_v1"]).read_text())
    assert quality["safety"]["final_text_validation_status"] == "failed"
    assert any(
        issue["code"] == "final_text_claim_validation_failed"
        and issue["scope"] == "claim"
        and issue["section_id"] == "MA-S1"
        for issue in quality["issues"]
    )
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    verified = Path(outputs["repository_verified_method"]).read_text()
    assert "The encoder reads the configured input." in candidate
    assert "The encoder reads the configured input." not in verified
    # W8: after the unsupported sentence is dropped, a heading-only leftover
    # is omitted from the verified projection rather than published as a
    # heading with an empty body.
    assert not any(
        line.strip() and not line.lstrip().startswith("#")
        for line in verified.splitlines()
    )
    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    assert any(
        item["proposed_body"] and item["confirmation_question"]
        for item in review["items"]
    )
    bundle = json.loads(Path(outputs["method_draft_bundle_v1"]).read_text())
    assert bundle["plan_readiness"] == "candidate_ready_with_review"
    assert bundle["verified_markdown"].strip() == verified.strip()


def test_publication_writer_blocks_generic_paraphrase_of_anchor(
    tmp_path: Path,
) -> None:
    """A Writer response that paraphrases the authorized anchor into generic
    prose (no canonical tokens preserved) must fail final reverse
    validation and be blocked — the validator never accepts a near-miss
    gloss.

    Regression: live MA-S2 emitted sentences such as 'The system loads the
    direct feature weights from the model state' for the anchor 'sym:...
    loads weights self._features_dc'; all seven such sentences were
    rejected and the run was blocked."""
    paths = _artifacts(tmp_path)
    method_path = tmp_path / "method_evidence.json"
    method_path.write_text(
        MethodEvidence(
            project_id="fixture",
            method_name="Encoder",
            method_goal="Describe the encoder.",
            implementation_scope="fixture repository",
        ).model_dump_json(),
        encoding="utf-8",
    )
    paths["method_evidence"] = str(method_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": (
                    "## Encoder\n\nThe system reads the direct feature weights "
                    "from the model state."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-generic-paraphrase",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    # The validator never accepts a near-miss gloss: the paraphrase stays in
    # the candidate as an explicitly review-linked item and is excluded from
    # the verified document (fail-closed on verified, candidate preserved).
    assert result.status == "incomplete"
    assert result.incomplete_section_ids == ()
    validation = json.loads(Path(outputs["text_evidence_validation"]).read_text())
    assert validation["status"] == "failed"
    assert validation["unsupported_claims"] >= 1
    assert any(
        "no_semantically_matching_projected_claim" in v["deterministic_failures"]
        for v in validation["verdicts"]
    )
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    verified = Path(outputs["repository_verified_method"]).read_text()
    assert "reads the direct feature weights" in candidate
    assert "reads the direct feature weights" not in verified
    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    assert any(
        item["proposed_body"] and "direct feature weights" in item["proposed_body"]
        for item in review["items"]
    )


def test_publication_writer_requires_callbacks_for_unanchored_organization_moves(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    plan_path = Path(paths["method_section_plan_v2"])
    plan = MethodSectionPlanV2.model_validate_json(plan_path.read_text())
    # Force the zero-budget transition move into the required set so this
    # integration check covers every organization-only move, not just the
    # problem/objective pair produced by the default fixture.
    section = plan.sections[0]
    section = section.model_copy(update={
        "moves": tuple(
            move.model_copy(update={"required": True})
            if move.move == "transition_to_next_section"
            else move
            for move in section.moves
        )
    })
    plan_path.write_text(
        plan.model_copy(update={"sections": (section,)}).model_dump_json(indent=2),
        encoding="utf-8",
    )

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        grounding = request.input_payload["grounding_contract"]
        anchored_moves = [
            move
            for move in binding["completed_rhetorical_moves"]
        ]
        assert set(anchored_moves).isdisjoint(
            grounding["unanchored_required_moves"]
        )
        callbacks = [
            {
                "request_id": f"request:{request.input_payload['section_id']}:{move}",
                "section_id": request.input_payload["section_id"],
                "argument_unit_id": binding["used_argument_unit_ids"][0],
                "missing_rhetorical_move": move,
                "exact_question": f"Which validated artifact supports {move}?",
                "required_authority_lane": grounding["move_authority"][move]["allowed_authority_lanes"][0],
                "status": "open",
            }
            for move in grounding["unanchored_required_moves"]
        ]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": anchored_moves,
                "new_research_requests": callbacks,
                "self_identified_risks": [],
            }),
            response_hash="sha256:writer-callback-contract",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    assert result.accepted_section_ids == ("MA-S1",)
    routes = json.loads(Path(outputs["writing_research_routes_v1"]).read_text())
    requests = json.loads(Path(outputs["publication_writer_result_v1"]).read_text())[
        "section_results"
    ][0]["output"]["new_research_requests"]
    assert len(routes["routes"]) == len(requests)
    assert any(
        item["missing_rhetorical_move"] == "equation_or_derivation"
        for item in requests
    )
    assert any(
        item["owner"] == "formalization_agent"
        and item["required_authority_lane"] == "formal_derivation"
        for item in routes["routes"]
    )
    assert not any("unanchored_rhetorical_moves_claimed" in item for item in result.binding_failures)


def test_publication_writer_does_not_synthesize_omitted_unanchored_callback(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    completeness = _with_unverified_gap(paths)
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                # Callback existence is semantic owner output.  Omitting the
                # array must remain a missing request, not be reconstructed
                # from the deterministic proof.
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer-omitted-callback",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
        rebuild_architect_plan=True,
    )

    assert result.status == "incomplete"
    assert result.accepted_section_ids == ("MA-S1",)
    section = json.loads(Path(outputs["publication_writer_result_v1"]).read_text())["section_results"][0]
    assert section["output"]["new_research_requests"] == []
    assert any(
        "missing_writing_research_callback:limitations_or_mismatch" in item
        for item in result.binding_failures
    )
    assert any(
        "rejected_missing_writing_callback:limitations_or_mismatch" in item["operations"]
        for item in result.response_recovery_traces
    )
    routes = json.loads(Path(outputs["writing_research_routes_v1"]).read_text())
    assert routes["routes"] == []


def test_publication_writer_retries_missing_unanchored_callback_with_writer_owner(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    completeness = _with_unverified_gap(paths)
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )
    seen_payloads: list[dict] = []

    def caller(_config, request):
        payload = request.input_payload
        seen_payloads.append(payload)
        binding = payload["binding_contract"]
        section_id = payload["section_id"]
        requests = []
        if payload.get("previous_attempt_error"):
            limitations = payload["grounding_contract"]["move_authority"][
                "limitations_or_mismatch"
            ]
            requests = [{
                "request_id": "request:MA-S1:limitations_or_mismatch",
                "section_id": "MA-S1",
                "argument_unit_id": binding["used_argument_unit_ids"][0],
                "missing_rhetorical_move": "limitations_or_mismatch",
                "exact_question": (
                    "Which validated repository artifact resolves the "
                    "remaining limitation or mismatch?"
                ),
                "required_authority_lane": "executable_hard",
                "candidate_symbols_or_terms": list(
                    limitations["candidate_symbols_or_terms"]
                ),
                "status": "open",
            }]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": requests,
            }),
            response_hash=(
                "sha256:writer-callback-retry"
                if requests else "sha256:writer-omitted-callback"
            ),
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
        rebuild_architect_plan=True,
    )

    assert len(seen_payloads) == 2
    assert seen_payloads[1]["previous_attempt_error"].startswith(
        "publication_section_binding_failed:missing_writing_research_callback"
    )
    assert result.accepted_section_ids == ("MA-S1",)
    bundle = json.loads(Path(
        outputs["writing_research_callback_artifacts_v1"]
    ).read_text())
    assert [
        item["missing_rhetorical_move"]
        for item in bundle["requests"]
    ] == ["limitations_or_mismatch"]
    routes = json.loads(Path(outputs["writing_research_routes_v1"]).read_text())
    assert len(routes["routes"]) == 1
    assert any(
        trace.get("applied") is True
        and trace.get("provenance") == "writer_owner_retry"
        for trace in result.response_recovery_traces
    )


def test_publication_writer_rejects_malformed_callback_without_synthesizing_routing(
    tmp_path: Path,
) -> None:
    """A partial semantic request cannot be replaced from the frozen proof.

    The model may produce ``new_research_requests`` entries that fail the
    ``WritingResearchRequestV1`` schema (missing ``request_id`` /
    ``missing_rhetorical_move`` / required bindings).  Such entries are
    unusable; the harness rejects them and leaves the owner contract missing.
    """

    paths = _artifacts(tmp_path)
    completeness = _with_unverified_gap(paths)
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        section_id = request.input_payload["section_id"]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                # Partial request objects missing request_id and
                # missing_rhetorical_move: they fail schema validation and
                # must be rejected without constructing a replacement.
                "new_research_requests": [
                    {
                        "section_id": section_id,
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "required_authority_lane": "executable_hard",
                        "status": "open",
                        "exact_question": "What resolves the unverified gap?",
                    },
                    {
                        "section_id": section_id,
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "required_authority_lane": "executable_hard",
                        "status": "open",
                        "exact_question": "What else is unverified?",
                    },
                ],
            }),
            response_hash="sha256:writer-malformed-callback",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
        rebuild_architect_plan=True,
    )

    assert result.status == "incomplete"
    assert result.accepted_section_ids == ("MA-S1",)
    section = json.loads(Path(outputs["publication_writer_result_v1"]).read_text())[
        "section_results"
    ][0]
    assert section["output"]["new_research_requests"] == []
    assert any(
        "missing_writing_research_callback:limitations_or_mismatch" in item
        for item in result.binding_failures
    )
    trace = next(
        item for item in result.response_recovery_traces
        if item.get("section_id") == "MA-S1"
        and item.get("provenance") == "rejected_missing"
    )
    assert trace["dropped_malformed_requests"] == 2
    assert any(
        "rejected_malformed_writing_research_request:2" in op for op in trace["operations"]
    )
    assert any(
        "rejected_missing_writing_callback:limitations_or_mismatch" in op
        for op in trace["operations"]
    )


def test_publication_writer_upgrades_final_validation_only_for_packet_bound_text(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    span = EvidenceSpanV3(
        span_id="span:encoder.py:1:2",
        snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        path="encoder.py",
        symbol="encoder",
        line_start=1,
        line_end=2,
        exact_excerpt="The encoder reads the configured input.",
        excerpt_digest="sha256:excerpt",
        file_digest="sha256:file",
        role="anchor",
    )
    packets = EvidencePacketSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        packets=[EvidencePacketV3(
            packet_id="packet:encoder",
            scope="sym:encoder",
            anchor_span_ids=[span.span_id],
            spans=[span],
            source_digest="sha256:packet-source",
        )],
        content_digest="sha256:packets-with-span",
    )
    Path(paths["evidence_packets_v3"]).write_text(
        packets.model_dump_json(indent=2), encoding="utf-8"
    )
    claims = claims.model_copy(update={"evidence_packet_digest": packets.content_digest})
    Path(paths["atomic_claims_v3"]).write_text(
        claims.model_dump_json(indent=2), encoding="utf-8"
    )
    method_path = tmp_path / "method_evidence.json"
    method_path.write_text(
        MethodEvidence(
            project_id="fixture",
            method_name="Encoder",
            method_goal="Describe the encoder.",
            implementation_scope="fixture repository",
        ).model_dump_json(),
        encoding="utf-8",
    )
    paths["method_evidence"] = str(method_path)
    method_evidence = MethodEvidence.model_validate_json(
        method_path.read_text(encoding="utf-8")
    )
    intent_graph = IntentObligationGraphV2(
        method_goal="Explain the encoder.",
        obligations=[IntentObligationV2(
            obligation_id="obl-main",
            kind="method_mainline",
            priority="must_cover",
            source_field="method_mainline",
            author_text="Explain the encoder.",
        )],
    )
    projection_path = tmp_path / "artifacts" / "authoring_projection_v1.json"
    projection = build_authoring_projection(
        method_evidence=method_evidence,
        claim_map=ClaimEvidenceMap(),
        verification=ClaimVerificationReport(),
        atomic_claims_v3=claims,
        evidence_packets_v3=packets,
        equation_claims_v1=EquationClaimSetV1.model_validate_json(
            Path(paths["equation_claims_v1"]).read_text(encoding="utf-8")
        ),
        intent_obligation_graph_v2=intent_graph,
        completeness=MethodCompletenessMatrixV1.model_validate_json(
            Path(paths["method_completeness_matrix_v1"]).read_text(encoding="utf-8")
        ),
    )
    projection_path.write_text(
        projection.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    paths["authoring_projection_v1"] = str(projection_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-reverse-passed",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status != "blocked"
    validation = json.loads(Path(outputs["text_evidence_validation"]).read_text())
    assert validation["status"] == "passed"
    assert validation["unsupported_claims"] == 0
    quality = json.loads(Path(outputs["publication_quality_report_v1"]).read_text())
    assert quality["safety"]["final_text_validation_status"] == "passed"
    assert quality["safety"]["hard_gate_passed"] is True
    assert quality["utility"]["completeness_coverage"] == 1.0
    assert quality["utility"]["qualifier_coverage"] == 1.0
    assert quality["utility"]["coherence_score"] == 1.0
    assert quality["coverage_matrix"][0]["coverage_status"] == "covered"
    projection = json.loads(Path(outputs["authoring_projection_v1"]).read_text())
    assert projection["author_story_spine"]
    assert projection["author_story_spine"][0]["linked_obligation_ids"] == ["obl-main"]
    assert projection["author_story_spine"][0]["evidence_lane"] == "repository_verified"


def test_publication_writer_invokes_owned_rewrite_after_failed_reverse_validation(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    span = EvidenceSpanV3(
        span_id="span:encoder.py:1:2",
        snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        path="encoder.py",
        symbol="encoder",
        line_start=1,
        line_end=2,
        exact_excerpt="The encoder reads the configured input.",
        excerpt_digest="sha256:excerpt",
        file_digest="sha256:file",
        role="anchor",
    )
    packets = EvidencePacketSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        packets=[EvidencePacketV3(
            packet_id="packet:encoder",
            scope="sym:encoder",
            anchor_span_ids=[span.span_id],
            spans=[span],
            source_digest="sha256:packet-source",
        )],
        content_digest="sha256:packets-with-span",
    )
    Path(paths["evidence_packets_v3"]).write_text(
        packets.model_dump_json(indent=2), encoding="utf-8"
    )
    claims = claims.model_copy(update={"evidence_packet_digest": packets.content_digest})
    Path(paths["atomic_claims_v3"]).write_text(
        claims.model_dump_json(indent=2), encoding="utf-8"
    )
    method_path = tmp_path / "method_evidence.json"
    method_path.write_text(
        MethodEvidence(
            project_id="fixture",
            method_name="Encoder",
            method_goal="Describe the encoder.",
            implementation_scope="fixture repository",
        ).model_dump_json(),
        encoding="utf-8",
    )
    paths["method_evidence"] = str(method_path)
    rewrite_calls: list[str] = []

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder guarantees the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-rewrite-incumbent",
            finish_reason="stop",
        )

    def rewrite_caller(_config, request):
        rewrite_calls.append(request.input_payload["incumbent_text"])
        incumbent = request.input_payload["incumbent_text"]
        original = "The encoder guarantees the configured input."
        start = incumbent.index(original)
        issue_id = request.input_payload["issues"][0]["atomic_claim_id"]
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "rewrite:qualifier",
                    "section_id": request.input_payload["section_context"]["section_id"],
                    "start": start,
                    "end": start + len(original),
                    "original_text": original,
                    "replacement_text": "The encoder reads the configured input.",
                    "issue_ids": [issue_id],
                    "allowed_scope": "wording_only",
                }],
                "self_identified_risks": [],
                "incomplete": False,
            }),
            response_hash="sha256:rewrite-response",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=rewrite_caller,
    )

    assert rewrite_calls == []
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "guarantees the configured input" in candidate
    validation = json.loads(Path(outputs["text_evidence_validation"]).read_text())
    assert validation["status"] != "passed"
    assert result.status != "blocked"


def test_publication_writer_rewrite_spends_second_attempt_when_section_still_fails(
    tmp_path: Path,
) -> None:
    """The bounded Rewrite loop trusts the deterministic reverse validator,
    not the model's ``incomplete`` self-report.

    Regression: an applied rewrite that left the section still failing was
    treated as complete when the model returned ``incomplete=False``, so the
    residual unsupported positive stayed in the candidate.  The transaction
    snapshot now reports the remaining failures and the loop spends its
    bounded next attempt on them."""
    paths = _artifacts(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    span = EvidenceSpanV3(
        span_id="span:encoder.py:1:2",
        snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        path="encoder.py",
        symbol="encoder",
        line_start=1,
        line_end=2,
        exact_excerpt="The encoder reads the configured input.",
        excerpt_digest="sha256:excerpt",
        file_digest="sha256:file",
        role="anchor",
    )
    packets = EvidencePacketSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        packets=[EvidencePacketV3(
            packet_id="packet:encoder",
            scope="sym:encoder",
            anchor_span_ids=[span.span_id],
            spans=[span],
            source_digest="sha256:packet-source",
        )],
        content_digest="sha256:packets-with-span",
    )
    Path(paths["evidence_packets_v3"]).write_text(
        packets.model_dump_json(indent=2), encoding="utf-8"
    )
    claims = claims.model_copy(update={"evidence_packet_digest": packets.content_digest})
    Path(paths["atomic_claims_v3"]).write_text(
        claims.model_dump_json(indent=2), encoding="utf-8"
    )
    method_path = tmp_path / "method_evidence.json"
    method_path.write_text(
        MethodEvidence(
            project_id="fixture",
            method_name="Encoder",
            method_goal="Describe the encoder.",
            implementation_scope="fixture repository",
        ).model_dump_json(),
        encoding="utf-8",
    )
    paths["method_evidence"] = str(method_path)
    rewrite_calls: list[str] = []

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": (
                    "## Encoder\n\nThe encoder guarantees the configured input. "
                    "The encoder guarantees the input."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-rewrite-incumbent",
            finish_reason="stop",
        )

    def rewrite_caller(_config, request):
        attempt = int(request.input_payload["section_context"]["attempt"])
        rewrite_calls.append(request.input_payload["incumbent_text"])
        incumbent = request.input_payload["incumbent_text"]
        issue_id = request.input_payload["issues"][0]["atomic_claim_id"]
        if attempt == 1:
            # Fix only the first sentence; the second must still fail so the
            # deterministic snapshot reports a remaining failure even though
            # the model claims the cluster is complete.
            original = "The encoder guarantees the configured input."
        else:
            original = "The encoder guarantees the input."
            assert request.input_payload["section_context"][
                "prior_attempt_feedback"
            ]["remaining_validation_failures"], (
                "attempt-2 must receive the deterministic remaining failures"
            )
        start = incumbent.index(original)
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": f"rewrite:qualifier:{attempt}",
                    "section_id": request.input_payload["section_context"]["section_id"],
                    "start": start,
                    "end": start + len(original),
                    "original_text": original,
                    "replacement_text": "The encoder reads the configured input.",
                    "issue_ids": [issue_id],
                    "allowed_scope": "wording_only",
                }],
                "self_identified_risks": [],
                "incomplete": False,
            }),
            response_hash=f"sha256:rewrite-response:{attempt}",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=rewrite_caller,
    )

    assert rewrite_calls == []
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "guarantees" in candidate
    assert result.status != "blocked"


def test_publication_writer_routes_code_trace_style_issue_to_rewrite(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    rewrite_issue_types: list[str] = []
    rewrite_attempts: list[int] = []

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": (
                    "## Encoder\n\nencoder.read reads the configured input through "
                    "encoder.load. encoder.return_value then returns the configured input."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-code-trace",
            finish_reason="stop",
        )

    def rewrite_caller(_config, request):
        rewrite_attempts.append(int(request.input_payload["section_context"]["attempt"]))
        issues = request.input_payload["issues"]
        rewrite_issue_types.extend(item["failure_type"] for item in issues)
        assert "raw code identifiers are never sentence subjects" in request.prompt
        authority_context = request.input_payload["section_context"][
            "writer_authority_context"
        ]
        assert authority_context["reader_facing_claims"]
        assert authority_context["validation_constraints"]["claims"]
        assert "candidate narrative" in request.prompt
        style_issue = next(
            item for item in issues if item["failure_type"] == "method_language_style"
        )
        incumbent = request.input_payload["incumbent_text"]
        first_attempt = len(rewrite_attempts) == 1
        replacement = (
            "## Encoder\n\nencoder.read reads the configured input."
            if first_attempt
            else "## Encoder\n\nThe encoder reads the configured input."
        )
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "rewrite:method-language",
                    "section_id": request.input_payload["section_context"]["section_id"],
                    "start": 0,
                    "end": len(incumbent),
                    "original_text": incumbent,
                    "replacement_text": replacement,
                    "issue_ids": [style_issue["sentence_id"]],
                    "allowed_scope": "wording_only",
                }],
                "self_identified_risks": [],
                "incomplete": first_attempt,
            }),
            response_hash=f"sha256:rewrite-method-language:{len(rewrite_attempts)}",
            finish_reason="stop",
        )

    _result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=rewrite_caller,
    )

    assert "method_language_style" in rewrite_issue_types
    assert rewrite_attempts == [1, 2]
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "The encoder reads the configured input." in candidate
    assert "encoder.read" not in candidate
    quality = json.loads(Path(outputs["publication_quality_report_v1"]).read_text())
    assert "code_trace_prose_not_method_language" not in {
        item["code"] for item in quality["issues"]
    }
    transitions = json.loads(
        Path(outputs["publication_rewrite_transitions_v1"]).read_text()
    )["transitions"]
    assert [item["status"] for item in transitions] == ["rejected", "applied"]
    assert transitions[0]["reason"].startswith("rewrite_transaction_rejected:")


def test_rewrite_clusters_are_ordered_and_later_cluster_inherits_text() -> None:
    from code2paper.agentic.publication_method_writer import _cluster_rewrite_issues
    from code2paper.agentic.research_models import TextRepairIssueV1

    issues = [
        TextRepairIssueV1(
            sentence_id="leakage:MA-S1:CK-",
            failure_type="reader_facing_internal_id",
            allowed_repair_scope="wording_only",
        ),
        TextRepairIssueV1(
            sentence_id="style:MA-S1:academic-specificity",
            failure_type="method_language_style",
            allowed_repair_scope="wording_only",
        ),
        TextRepairIssueV1(
            sentence_id="coverage:MA-S1:C1",
            failure_type="supported_claim_not_rendered",
            matched_claim_ids=("C1",),
            allowed_repair_scope="claim_decomposition",
        ),
        TextRepairIssueV1(
            sentence_id="FAC-unsafe",
            failure_type="unsupported_rationale",
            allowed_repair_scope="drop_or_gap",
        ),
        TextRepairIssueV1(
            sentence_id="FAC-qualifier",
            failure_type="missing_qualifier",
            allowed_repair_scope="wording_only",
        ),
        TextRepairIssueV1(
            sentence_id="style:MA-S1:code-trace",
            failure_type="method_language_style",
            allowed_repair_scope="wording_only",
        ),
        TextRepairIssueV1(
            sentence_id="structure:MA-S1:heading-only",
            failure_type="section_structure",
            allowed_repair_scope="wording_only",
        ),
    ]

    clusters = _cluster_rewrite_issues(issues)

    assert [name for name, _items in clusters] == [
        "internal_id_leakage",
        "unsafe_positive_or_authority",
        "qualifier_numeric_formula",
        "missing_supported_proposition",
        "section_structure",
        "method_language_style",
        "duplicate_or_transition",
    ]
    assert all(len(items) == 1 for _name, items in clusters)


def test_internal_id_leakage_cluster_requires_deterministic_leakage_gain() -> None:
    from code2paper.agentic.publication_method_writer import (
        _rewrite_transaction_has_cluster_gain,
    )

    incumbent = {
        "validation_status": "failed",
        "validation_counts": (1, 0, -3),
        "style_issue_count": 4,
        "missing_propositions": 0,
        "leakage_count": 3,
    }
    # Removing one internal id is a strict gain for the leakage cluster even
    # though the reverse-validation counts are unchanged (the validator does
    # not count harness ids).
    candidate = {
        "validation_status": "failed",
        "validation_counts": (1, 0, -3),
        "style_issue_count": 4,
        "missing_propositions": 0,
        "leakage_count": 2,
    }
    ok, reason = _rewrite_transaction_has_cluster_gain(
        incumbent, candidate, cluster_name="internal_id_leakage"
    )
    assert ok is True
    assert reason == "monotonic_cluster_gain"
    # Re-introducing an internal id must never be accepted.
    regression = dict(candidate, leakage_count=4)
    ok, reason = _rewrite_transaction_has_cluster_gain(
        incumbent, regression, cluster_name="internal_id_leakage"
    )
    assert ok is False
    assert reason == "internal_id_leakage_regressed"


def test_rewrite_cluster_context_exposes_only_assigned_failures() -> None:
    from code2paper.agentic.publication_method_writer import (
        _cluster_validation_failures,
    )
    from code2paper.agentic.research_models import TextRepairIssueV1

    # The shared section context lists every section failure, including
    # structure:* rows that belong to an earlier, already-applied cluster.
    context = {
        "validation_failures": [
            {
                "atomic_claim_id": "FAC20",
                "failure_type": "missing_qualifier",
                "allowed_repair_scope": "wording_only",
            },
            {
                "atomic_claim_id": None,
                "sentence_id": "structure:MA-S2:fused-heading-suffix",
                "failure_type": "section_structure",
                "allowed_repair_scope": "wording_only",
            },
            {
                "atomic_claim_id": "FAC29",
                "failure_type": "formula_unsupported",
                "allowed_repair_scope": "drop_or_gap",
            },
        ],
    }
    cluster_issues = [
        TextRepairIssueV1(
            sentence_id="FAC20",
            atomic_claim_id="FAC20",
            failure_type="missing_qualifier",
            allowed_repair_scope="wording_only",
        ),
        TextRepairIssueV1(
            sentence_id="FAC29",
            atomic_claim_id="FAC29",
            failure_type="formula_unsupported",
            allowed_repair_scope="drop_or_gap",
        ),
    ]

    filtered = _cluster_validation_failures(context, cluster_issues)

    assert [row["atomic_claim_id"] for row in filtered] == ["FAC20", "FAC29"]
    assert all(
        row.get("sentence_id") != "structure:MA-S2:fused-heading-suffix"
        for row in filtered
    )


def test_writer_research_callback_requires_artifact_and_resumes_only_affected_section(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    completeness = _with_unverified_gap(paths)
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )
    first_calls: list[str] = []

    def first_caller(_config, request):
        section_id = request.input_payload["section_id"]
        first_calls.append(section_id)
        binding = request.input_payload["binding_contract"]
        move_authority = request.input_payload["grounding_contract"]["move_authority"]
        limitations = move_authority["limitations_or_mismatch"]
        assert limitations["required_authority_lane"] == "executable_hard"
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                # A callback may leave one authorized claim unresolved while
                # it requests the missing artifact; the section remains
                # resumable instead of being rejected as a binding failure.
                "used_claim_ids": binding["used_claim_ids"][:-1],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [{
                    "request_id": "request:MA-S1:limitations_or_mismatch",
                    "section_id": section_id,
                    "argument_unit_id": binding["used_argument_unit_ids"][0],
                    "missing_rhetorical_move": "limitations_or_mismatch",
                    "exact_question": "Which validated artifact resolves the unverified gap?",
                    "required_authority_lane": "executable_hard",
                    "candidate_symbols_or_terms": list(
                        limitations.get("candidate_symbols_or_terms", ())
                    ),
                    "why_needed_for_reader": "Close the remaining behavior gap.",
                    "priority": "high",
                }],
            }),
            response_hash="sha256:writer-callback",
            finish_reason="stop",
        )

    first, first_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=first_caller,
        rebuild_architect_plan=True,
    )
    assert first.status == "incomplete"
    assert first.accepted_section_ids == ("MA-S1",)
    assert first.incomplete_section_ids == ("MA-S1",)
    assert first_calls == ["MA-S1"]
    checkpoint = json.loads(Path(
        first_outputs["publication_section_checkpoint_v1"]
    ).read_text())
    checkpoint_row = checkpoint["sections"]["MA-S1"]
    assert "output" not in checkpoint_row
    immutable_output = Path(checkpoint_row["output_ref"])
    if not immutable_output.is_absolute():
        immutable_output = Path(first_outputs["publication_section_checkpoint_v1"]).parent / immutable_output
    immutable_bytes = immutable_output.read_bytes()
    routes = json.loads(Path(first_outputs["writing_research_routes_v1"]).read_text())
    assert routes["routes"][0]["owner"] == "repository_tools"
    callback_bundle = json.loads(Path(
        first_outputs["writing_research_callback_artifacts_v1"]
    ).read_text())
    # An open locally owned request never populates the admitted resume set.
    assert callback_bundle["resume_section_ids"] == []
    assert callback_bundle["requests"][0]["status"] == "open"
    paths.update(first_outputs)

    blocked, _ = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=lambda *_args: (_ for _ in ()).throw(AssertionError("must not call")),
        resume_section_ids=("MA-S1",),
    )
    assert blocked.status == "blocked"
    assert blocked.blocked_reason.startswith("writing_research_callback_artifacts_missing:")

    fulfilled = fulfill_writing_research_callbacks(
        first_outputs["writing_research_callback_artifacts_v1"],
        {
            "request:MA-S1:limitations_or_mismatch": ({
                "artifact_id": "artifact:fact-read",
                "request_id": "request:MA-S1:limitations_or_mismatch",
                "section_id": "MA-S1",
                "argument_unit_id": "MA-S1:unit",
                "authority_lane": "executable_hard",
                "artifact_ref": "fact-read",
                "artifact_digest": "sha256:fact-read",
                "validated": True,
            },),
        },
    )
    assert fulfilled.requests[0].status == "fulfilled"
    # Fulfillment admits the affected section only.
    assert fulfilled.resume_section_ids == ("MA-S1",)

    # A tampered immutable checkpoint still fails closed at admission: the
    # resume is admitted but the prior output digest does not verify.
    fulfilled_bundle = Path(
        first_outputs["writing_research_callback_artifacts_v1"]
    )
    immutable_output.write_text("{}\n", encoding="utf-8")
    try:
        tampered, _ = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=lambda *_args: (_ for _ in ()).throw(AssertionError("must not call")),
            resume_section_ids=("MA-S1",),
            research_callback_artifacts={
                "request:MA-S1:limitations_or_mismatch": ({
                    "artifact_id": "artifact:fact-read",
                    "request_id": "request:MA-S1:limitations_or_mismatch",
                    "section_id": "MA-S1",
                    "argument_unit_id": "MA-S1:unit",
                    "authority_lane": "executable_hard",
                    "artifact_ref": "fact-read",
                    "artifact_digest": "sha256:fact-read",
                    "validated": True,
                },),
            },
        )
    finally:
        immutable_output.write_bytes(immutable_bytes)
    assert tampered.status == "blocked"
    assert tampered.blocked_reason == "publication_section_checkpoint_missing_or_invalid"

    resumed_calls: list[str] = []

    def resumed_caller(_config, request):
        section_id = request.input_payload["section_id"]
        resumed_calls.append(section_id)
        assert request.input_payload["writing_research_callback_artifacts"] == {
            "request:MA-S1:limitations_or_mismatch": [{
                "artifact_id": "artifact:fact-read",
                "request_id": "request:MA-S1:limitations_or_mismatch",
                "section_id": "MA-S1",
                "argument_unit_id": "MA-S1:unit",
                "authority_lane": "executable_hard",
                "artifact_ref": "fact-read",
                "artifact_digest": "sha256:fact-read",
                "validated": True,
            }]
        }
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input and leaves the remaining gap explicit.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
                "self_identified_risks": [],
            }),
            response_hash="sha256:writer-resumed",
            finish_reason="stop",
        )

    resumed, resumed_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=resumed_caller,
    )

    assert resumed.status == "incomplete"
    assert resumed.resumed_section_ids == ("MA-S1",)
    assert resumed_calls == ["MA-S1"]
    assert "remaining gap" in Path(
        resumed_outputs["publication_candidate_method"]
    ).read_text()
    resumed_bundle = json.loads(Path(
        resumed_outputs["writing_research_callback_artifacts_v1"]
    ).read_text())
    assert resumed_bundle["resume_section_ids"] == []
    assert resumed_bundle["requests"][0]["status"] == "fulfilled"


def test_resume_ignores_unrouted_checkpoint_configuration_callback(
    tmp_path: Path,
) -> None:
    """r4: unrouted configuration in the checkpoint must not block resume.

    Live Writer checkpoints listed both ``configuration_and_branches`` and
    ``limitations_or_mismatch``.  Populate dropped configuration (unauthorized
    candidates), so the bundle/routes only admitted limitations.  Resume must
    still require the admitted limitations artifact and must not treat the
    extra checkpoint row as a missing reconstruction obligation.  A blocked
    resume also keeps the incumbent Candidate.
    """

    paths = _artifacts(tmp_path)
    completeness = _with_unverified_gap(paths)
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )

    def first_caller(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        move_authority = request.input_payload["grounding_contract"]["move_authority"]
        limitations = move_authority["limitations_or_mismatch"]
        unit_id = binding["used_argument_unit_ids"][0]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"][:-1],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [
                    {
                        "request_id": "request:MA-S1:configuration_and_branches",
                        "section_id": section_id,
                        "argument_unit_id": unit_id,
                        "missing_rhetorical_move": "configuration_and_branches",
                        "exact_question": "Which configuration branch is authoritative?",
                        "required_authority_lane": "executable_hard",
                        "candidate_symbols_or_terms": [
                            "not-an-authorized-configuration-term",
                        ],
                        "why_needed_for_reader": "Name the unresolved branch.",
                        "priority": "medium",
                    },
                    {
                        "request_id": "request:MA-S1:limitations_or_mismatch",
                        "section_id": section_id,
                        "argument_unit_id": unit_id,
                        "missing_rhetorical_move": "limitations_or_mismatch",
                        "exact_question": "Which validated artifact resolves the unverified gap?",
                        "required_authority_lane": "executable_hard",
                        "candidate_symbols_or_terms": list(
                            limitations.get("candidate_symbols_or_terms", ())
                        ),
                        "why_needed_for_reader": "Close the remaining behavior gap.",
                        "priority": "high",
                    },
                ],
            }),
            response_hash="sha256:writer-callback-split",
            finish_reason="stop",
        )

    first, first_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=first_caller,
        rebuild_architect_plan=True,
    )
    assert first.status == "incomplete"
    checkpoint = json.loads(Path(
        first_outputs["publication_section_checkpoint_v1"]
    ).read_text())
    output_ref = Path(checkpoint["sections"]["MA-S1"]["output_ref"])
    if not output_ref.is_absolute():
        output_ref = Path(first_outputs["publication_section_checkpoint_v1"]).parent / output_ref
    checkpoint_requests = [
        item["request_id"]
        for item in json.loads(output_ref.read_text())["output"]["new_research_requests"]
    ]
    assert "request:MA-S1:configuration_and_branches" in checkpoint_requests
    assert "request:MA-S1:limitations_or_mismatch" in checkpoint_requests
    bundle = json.loads(Path(
        first_outputs["writing_research_callback_artifacts_v1"]
    ).read_text())
    bundle_ids = [item["request_id"] for item in bundle["requests"]]
    assert bundle_ids == ["request:MA-S1:limitations_or_mismatch"]
    paths.update(first_outputs)

    blocked, blocked_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=lambda *_args: (_ for _ in ()).throw(AssertionError("must not call")),
        resume_section_ids=("MA-S1",),
    )
    assert blocked.status == "blocked"
    assert blocked.blocked_reason == (
        "writing_research_callback_artifacts_missing:"
        "request:MA-S1:limitations_or_mismatch"
    )
    assert "configuration_and_branches" not in blocked.blocked_reason
    assert blocked.candidate_available is True
    assert blocked.candidate_generation_status == "generated"
    persisted = json.loads(Path(
        blocked_outputs["publication_writer_result_v1"]
    ).read_text())
    assert persisted["candidate_available"] is True
    assert persisted["candidate_generation_status"] == "generated"
    assert Path(first_outputs["publication_candidate_method"]).read_text().strip()

    fulfill_writing_research_callbacks(
        first_outputs["writing_research_callback_artifacts_v1"],
        {
            "request:MA-S1:limitations_or_mismatch": ({
                "artifact_id": "artifact:fact-read",
                "request_id": "request:MA-S1:limitations_or_mismatch",
                "section_id": "MA-S1",
                "argument_unit_id": "MA-S1:unit",
                "authority_lane": "executable_hard",
                "artifact_ref": "fact-read",
                "artifact_digest": "sha256:fact-read",
                "validated": True,
            },),
        },
    )

    resumed_calls: list[str] = []

    def resumed_caller(_config, request):
        section_id = request.input_payload["section_id"]
        resumed_calls.append(section_id)
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": (
                    "## Encoder\n\nThe encoder reads the configured input "
                    "and leaves the remaining gap explicit."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
                "self_identified_risks": [],
            }),
            response_hash="sha256:writer-resumed-split",
            finish_reason="stop",
        )

    resumed, _ = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=resumed_caller,
    )
    assert resumed.status != "blocked"
    assert resumed_calls == ["MA-S1"]


def test_resume_fulfills_only_affected_section_and_leaves_unaffected_checkpoint(
    tmp_path: Path,
) -> None:
    paths = _two_section_gap_artifacts(tmp_path)

    def first_writer_caller(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        if section_id == "MA-S1":
            return LLMResponse(
                text=json.dumps({
                    "section_id": section_id,
                    "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                    "used_argument_unit_ids": binding["used_argument_unit_ids"],
                    "used_claim_ids": binding["used_claim_ids"],
                    "used_equation_ids": binding["used_equation_ids"],
                    "used_configuration_ids": binding["used_configuration_ids"],
                    "completed_rhetorical_moves": _completed_moves(binding),
                    "new_research_requests": [{
                        "request_id": "request:MA-S1:limitations_or_mismatch",
                        "section_id": section_id,
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "missing_rhetorical_move": "limitations_or_mismatch",
                        "exact_question": "Which validated artifact resolves the scoped gap?",
                        "required_authority_lane": "executable_hard",
                        "candidate_symbols_or_terms": ["sym:encoder"],
                        "why_needed_for_reader": "Close the scoped repository gap.",
                        "priority": "high",
                    }],
                }),
                response_hash="sha256:writer:MA-S1",
                finish_reason="stop",
            )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": (
                    "## Output interface\n\nIts representation is returned to the downstream stage."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer:MA-S2",
            finish_reason="stop",
        )

    first, first_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=first_writer_caller,
        editor_caller=lambda _config, _request: LLMResponse(
            text=json.dumps({"patches": []}),
            response_hash="sha256:editor-noop",
            finish_reason="stop",
        ),
    )
    bundle = json.loads(Path(
        first_outputs["writing_research_callback_artifacts_v1"]
    ).read_text())
    open_sections = {request["section_id"] for request in bundle["requests"] if request["status"] == "open"}
    assert open_sections == {"MA-S1"}
    paths.update(first_outputs)

    fulfilled = fulfill_writing_research_callbacks(
        first_outputs["writing_research_callback_artifacts_v1"],
        {
            "request:MA-S1:limitations_or_mismatch": ({
                "artifact_id": "artifact:output-span",
                "request_id": "request:MA-S1:limitations_or_mismatch",
                "section_id": "MA-S1",
                "argument_unit_id": "MA-S1:unit",
                "authority_lane": "executable_hard",
                "artifact_ref": "span:output.py:3:3",
                "artifact_digest": "sha256:output-span",
                "validated": True,
            },),
        },
    )
    assert fulfilled.resume_section_ids == ("MA-S1",)

    checkpoint = json.loads(Path(
        first_outputs["publication_section_checkpoint_v1"]
    ).read_text())
    checkpoint_root = Path(first_outputs["publication_section_checkpoint_v1"]).parent
    ma1_before = json.loads((checkpoint_root / checkpoint["sections"]["MA-S1"]["output_ref"]).read_text())
    ma2_before = json.loads((checkpoint_root / checkpoint["sections"]["MA-S2"]["output_ref"]).read_text())

    resumed_calls: list[str] = []

    def resumed_caller(_config, request):
        section_id = request.input_payload["section_id"]
        resumed_calls.append(section_id)
        assert section_id == "MA-S1"
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": (
                    "## Output interface\n\nIts representation is returned to the downstream stage "
                    "after the encoder reads the configured input."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer-resumed",
            finish_reason="stop",
        )

    resumed, resumed_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=resumed_caller,
    )

    assert resumed_calls == ["MA-S1"]
    assert resumed.resumed_section_ids == ("MA-S1",)
    resumed_checkpoint = json.loads(Path(
        resumed_outputs["publication_section_checkpoint_v1"]
    ).read_text())
    ma1_after = json.loads((checkpoint_root / resumed_checkpoint["sections"]["MA-S1"]["output_ref"]).read_text())
    ma2_after = json.loads((checkpoint_root / resumed_checkpoint["sections"]["MA-S2"]["output_ref"]).read_text())
    assert ma2_after["output_digest"] == ma2_before["output_digest"]
    assert ma2_after["output"] == ma2_before["output"]
    assert ma1_after["output_digest"] != ma1_before["output_digest"]


def test_cross_section_editor_patch_is_applied_with_editor_authorship(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    plan_path = Path(paths["method_section_plan_v2"])
    plan = MethodSectionPlanV2.model_validate_json(plan_path.read_text())
    first = plan.sections[0]
    second = first.model_copy(update={
        "section_id": "MA-S2",
        "heading": "Output interface",
        "dependencies": (first.section_id,),
    })
    plan = plan.model_copy(update={"sections": (*plan.sections, second)})
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    def writer_caller(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        body = (
            "## Encoder\n\nThe encoder reads the configured input."
            if section_id == "MA-S1"
            else "## Output interface\n\nIts representation is returned to the downstream stage."
            " Its representation is returned to the downstream stage."
        )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": body,
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash=f"sha256:writer:{section_id}",
            finish_reason="stop",
        )

    def editor_caller(_config, request):
        sections = request.input_payload["sections"]
        assert request.input_payload["section_contexts"]["MA-S1"][
            "reader_facing_claims"
        ]
        assert "separate_repository_fact_from_candidate_narrative" in (
            request.input_payload["document_context"]["revision_priorities"]
        )
        assert "candidate-only author narrative" in request.prompt
        before = sections["MA-S2"]
        replacement = (
            "## Output interface\n\nIts representation is returned to the downstream stage."
        )
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "editor:MA-S2",
                    "section_id": "MA-S2",
                    "before_digest": "sha256:" + hashlib.sha256(before.encode()).hexdigest(),
                    "replacement_text": replacement,
                    "generation_source": "editor",
                    "reason": "Remove the repeated sentence while preserving the transition.",
                    "scoped": True,
                }],
            }),
            response_hash="sha256:editor-response",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        editor_caller=editor_caller,
    )

    assert result.status == "incomplete"
    final_text = Path(outputs["publication_candidate_method"]).read_text()
    assert final_text.count("Its representation is returned to the downstream stage.") == 1
    assert "The resulting representation" not in final_text
    ledger = json.loads(Path(outputs["final_text_authorship_ledger_v1"]).read_text())
    assert [span["owner"] for span in ledger["spans"]] == ["writer", "editor"]
    assert ledger["spans"][1]["response_ref"] == "sha256:editor-response"
    editor = json.loads(Path(outputs["publication_editor_result_v1"]).read_text())
    assert editor["patches"][0]["section_id"] == "MA-S2"
    transitions = json.loads(Path(outputs["publication_editor_transitions_v1"]).read_text())
    assert transitions["decision"] == "accept"
    assert transitions["candidate"]["duplicate_rate"] < transitions["incumbent"]["duplicate_rate"]


def _canonical_digest(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _two_section_plan(tmp_path: Path) -> dict[str, str]:
    paths = _artifacts(tmp_path)
    plan_path = Path(paths["method_section_plan_v2"])
    plan = MethodSectionPlanV2.model_validate_json(plan_path.read_text())
    first = plan.sections[0]
    second = first.model_copy(update={
        "section_id": "MA-S2",
        "heading": "Output interface",
        "dependencies": (first.section_id,),
    })
    plan = plan.model_copy(update={"sections": (*plan.sections, second)})
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return paths


def _two_section_writer_caller(_config, request):
    section_id = request.input_payload["section_id"]
    binding = request.input_payload["binding_contract"]
    body = (
        "## Encoder\n\nThe encoder reads the configured input."
        if section_id == "MA-S1"
        else "## Output interface\n\nIts representation is returned to the downstream stage."
    )
    return LLMResponse(
        text=json.dumps({
            "section_id": section_id,
            "section_markdown": body,
            "used_argument_unit_ids": binding["used_argument_unit_ids"],
            "used_claim_ids": binding["used_claim_ids"],
            "used_equation_ids": binding["used_equation_ids"],
            "used_configuration_ids": binding["used_configuration_ids"],
            "completed_rhetorical_moves": _completed_moves(binding),
        }),
        response_hash=f"sha256:writer:{section_id}",
        finish_reason="stop",
    )


def test_cross_section_edit_result_with_updates_recomputes_digest() -> None:
    base = CrossSectionEditResultV1(sections={"MA-S1": "first"})
    updated = base.with_updates(response_ref="sha256:editor-noop-live")
    assert updated.content_digest != base.content_digest
    assert updated.content_digest == _canonical_digest(
        updated.model_dump(mode="json", exclude={"content_digest"})
    )
    reverted = updated.with_updates(
        sections={"MA-S1": "incumbent"},
        blocked_reason="editor:supported_claim_lost",
    )
    assert reverted.content_digest == _canonical_digest(
        reverted.model_dump(mode="json", exclude={"content_digest"})
    )
    assert reverted.content_digest != updated.content_digest


def test_editor_noop_result_digest_covers_attached_response_ref(
    tmp_path: Path,
) -> None:
    paths = _two_section_plan(tmp_path)

    def editor_caller(_config, request):
        return LLMResponse(
            text=json.dumps({"patches": []}),
            response_hash="sha256:editor-noop-live",
            finish_reason="stop",
        )

    _result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_two_section_writer_caller,
        editor_caller=editor_caller,
    )

    editor = json.loads(Path(outputs["publication_editor_result_v1"]).read_text())
    assert editor["response_ref"] == "sha256:editor-noop-live"
    payload = {key: value for key, value in editor.items() if key != "content_digest"}
    assert editor["content_digest"] == _canonical_digest(payload)
    assert editor["content_digest"] != _canonical_digest({**payload, "response_ref": ""})


def test_editor_regression_fallback_recomputes_result_digest(
    tmp_path: Path,
) -> None:
    paths = _two_section_plan(tmp_path)

    def editor_caller(_config, request):
        before = request.input_payload["sections"]["MA-S1"]
        return LLMResponse(
            text=json.dumps({"patches": [{
                "patch_id": "editor:drop",
                "section_id": "MA-S1",
                "before_digest": "sha256:" + hashlib.sha256(before.encode()).hexdigest(),
                "replacement_text": "## Encoder\n\nA separate component exists.",
                "generation_source": "editor",
                "reason": "Rewrite the section.",
                "scoped": True,
            }]}),
            response_hash="sha256:editor-response",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_two_section_writer_caller,
        editor_caller=editor_caller,
    )

    assert any(
        "editor:MA-S1:supported_claim_lost:claim-read" in failure
        for failure in result.binding_failures
    )
    editor = json.loads(Path(outputs["publication_editor_result_v1"]).read_text())
    assert "supported_claim_lost" in editor["blocked_reason"]
    assert editor["sections"]["MA-S1"] == "## Encoder\n\nThe encoder reads the configured input."
    payload = {key: value for key, value in editor.items() if key != "content_digest"}
    assert editor["content_digest"] == _canonical_digest(payload)
    assert editor["content_digest"] != _canonical_digest({
        **payload,
        "sections": {
            "MA-S1": "## Encoder\n\nA separate component exists.",
            "MA-S2": payload["sections"]["MA-S2"],
        },
    })


def test_editor_authorship_reconstruction_failure_recomputes_result_digest(
    tmp_path: Path,
) -> None:
    paths = _two_section_plan(tmp_path)

    def writer_caller(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        body = (
            "## Encoder\n\nThe encoder reads the configured input."
            if section_id == "MA-S1"
            else "## Output interface\n\nIts representation is returned to the downstream stage."
            " Its representation is returned to the downstream stage."
        )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": body,
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash=f"sha256:writer:{section_id}",
            finish_reason="stop",
        )

    def editor_caller(_config, request):
        before = request.input_payload["sections"]["MA-S2"]
        replacement = (
            "## Output interface\n\nIts representation is returned to the downstream stage."
        )
        return LLMResponse(
            text=json.dumps({"patches": [{
                "patch_id": "editor:MA-S2",
                "section_id": "MA-S2",
                "before_digest": "sha256:" + hashlib.sha256(before.encode()).hexdigest(),
                "replacement_text": replacement,
                "generation_source": "editor",
                "reason": "Remove the repeated sentence while preserving the transition.",
                "scoped": True,
            }]}),
            response_hash="sha256:editor-response",
            finish_reason="stop",
        )

    with patch(
        "code2paper.agentic.publication_method_writer._build_editor_local_ledgers",
        side_effect=ValueError("editor_fault_injected"),
    ):
        result, outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=writer_caller,
            editor_caller=editor_caller,
        )

    assert any(
        "editor:authorship_reconstruction_failed:editor_fault_injected" in failure
        for failure in result.binding_failures
    )
    editor = json.loads(Path(outputs["publication_editor_result_v1"]).read_text())
    assert editor["blocked_reason"].startswith("authorship_reconstruction_failed")
    assert (
        editor["sections"]["MA-S2"]
        == "## Output interface\n\nIts representation is returned to the downstream stage."
        " Its representation is returned to the downstream stage."
    )
    payload = {key: value for key, value in editor.items() if key != "content_digest"}
    assert editor["content_digest"] == _canonical_digest(payload)
    assert editor["content_digest"] != _canonical_digest({
        **payload,
        "sections": {
            "MA-S1": payload["sections"]["MA-S1"],
            "MA-S2": "## Output interface\n\nIts representation is returned to the downstream stage.",
        },
    })


def test_cross_section_editor_can_apply_a_unique_generated_span() -> None:
    original = "## Encoder\n\nThe encoder reads the input.\n\nThe encoder reads the input."
    before_text = "The encoder reads the input.\n\nThe encoder reads the input."
    patch = SectionTextPatchV1(
        patch_id="editor:span",
        section_id="MA-S1",
        before_digest="sha256:" + hashlib.sha256(original.encode()).hexdigest(),
        before_text=before_text,
        replacement_text="The encoder reads the input once before emitting its representation.",
        reason="Remove the repeated sentence while preserving the supported operation.",
    )

    result = edit_sections({"MA-S1": original}, patch_provider=lambda _: [patch])

    assert not result.blocked_reason
    assert result.patches == [patch]
    assert result.sections["MA-S1"].count("The encoder reads the input") == 1


def test_editor_partial_patch_preserves_unaffected_writer_ownership() -> None:
    original = "The encoder reads the input. The output is returned."
    replacement = "The output representation is returned."
    patch = SectionTextPatchV1(
        patch_id="editor:partial",
        section_id="MA-S1",
        before_digest="sha256:" + hashlib.sha256(original.encode()).hexdigest(),
        before_text="The output is returned.",
        replacement_text=replacement,
        reason="Clarify the output subject without changing the first operation.",
    )

    ledgers = _build_editor_local_ledgers(
        incumbent_sections={"MA-S1": (original, "sha256:writer")},
        edited_sections={"MA-S1": "The encoder reads the input. " + replacement},
        patches=(patch,),
        response_ref="sha256:editor",
    )

    assert [span.owner for span in ledgers["MA-S1"].spans] == ["writer", "editor"]
    assert ledgers["MA-S1"].spans[0].response_ref == "sha256:writer"
    assert ledgers["MA-S1"].spans[1].response_ref == "sha256:editor"


def test_degraded_duplicate_method_is_blocked_by_publication_utility_gate(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        repeated = "The encoder reads the configured input."
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": f"## Encoder\n\n{repeated} {repeated}",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-duplicate",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    report = json.loads(Path(outputs["publication_quality_report_v1"]).read_text())
    assert report["safety"]["authorship_gate_passed"] is True
    assert report["safety"]["final_text_validation_status"] == "pending"
    assert report["utility"]["duplicate_information_rate"] > 0
    assert any(issue["code"] == "duplicate_information" for issue in report["issues"])


def test_supported_unit_missing_from_argument_graph_fails_plan_gate(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    plan = MethodSectionPlanV2.model_validate_json(
        Path(paths["method_section_plan_v2"]).read_text()
    )
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    ).model_copy(update={
        "items": (
            *MethodCompletenessMatrixV1.model_validate_json(
                Path(paths["method_completeness_matrix_v1"]).read_text()
            ).items,
            MethodCompletenessItemV1(
                obligation_id="obl-supported-not-planned",
                status="supported_by_repository",
                claim_ids=("claim-not-planned",),
            ),
        ),
    })
    output = PublicationMethodSectionOutputV1(
        section_id=plan.sections[0].section_id,
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=list(plan.sections[0].argument_unit_ids),
        used_claim_ids=["claim-read"],
        completed_rhetorical_moves=_COMPLETED_CORE_MOVES,
    )
    ledger = ledger_from_section_outputs(
        output.section_markdown,
        ((output.section_id, output.section_markdown, "sha256:writer-plan"),),
    )

    report = evaluate_publication_method_quality(
        final_text=output.section_markdown,
        plan=plan,
        completeness=completeness,
        section_outputs=(output,),
        ledger=ledger,
    )

    assert report.plan_gate_passed is False
    assert report.utility.completeness_coverage == 0.5
    assert any(
        issue.code == "supported_unit_missing_from_argument_graph"
        for issue in report.issues
    )


def test_unplaced_critical_high_assignment_is_an_audit_issue_not_candidate_gate() -> None:
    plan = _quality_plan(claims=("claim-a",))
    plan = plan.model_copy(update={
        "obligation_assignments": (
            ObligationMoveAssignmentV1(
                obligation_id="obl-a",
                importance="high",
                status="supported_by_repository",
                authority_lane="executable_hard",
                placement_state="unplaced",
                unresolved_reason="No unique closed target was selected.",
            ),
        ),
        "incomplete_sections": ("unresolved:obl-a",),
    })
    completeness = _quality_completeness(claim_ids=("claim-a",)).model_copy(update={
        "items": (
            _quality_completeness(claim_ids=("claim-a",)).items[0].model_copy(
                update={"importance": "high"}
            ),
        ),
    })
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="The encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=["claim-a"],
        completed_rhetorical_moves=_COMPLETED_CORE_MOVES,
    )
    ledger = ledger_from_section_outputs(
        output.section_markdown,
        (("section-a", output.section_markdown, "sha256:writer-unplaced"),),
    )
    report = evaluate_publication_method_quality(
        final_text=output.section_markdown,
        plan=plan,
        completeness=completeness,
        section_outputs=(output,),
        ledger=ledger,
        claims=AtomicClaimSetV3(
            repo_snapshot_id="repo:quality",
            project_tree_hash="sha256:tree",
            evidence_packet_digest="sha256:packets",
            code_fact_digest="sha256:facts",
            claims=[_quality_claim()],
            content_digest="sha256:claims",
        ),
    )
    assert report.plan_gate_passed is True
    assert any(
        issue.code == "critical_high_obligation_unplaced"
        for issue in report.issues
    )


def test_partial_completeness_without_claim_is_review_sidecar_not_plan_unit() -> None:
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:partial-sidecar",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[AtomicClaimV3(
            claim_id="claim:partial-supported",
            canonical_text="The encoder reads the configured input.",
            fact_ids=["fact:partial-supported"],
            covers_obligation_ids=["obl:supported"],
            direct_evidence_ids=["span:encoder.py:1:2"],
            allowed_wording_boundary="reads configured input",
            canonical_identity="sha256:partial-supported",
            status="supported",
        )],
        semantic_stage_groups=[SemanticStageGroupV1(
            stage_id="stage:partial-sidecar",
            name="Encoder",
            purpose="Explain the encoder.",
            ordered_claim_ids=["claim:partial-supported"],
            covers_obligation_ids=["obl:supported"],
        )],
        content_digest="sha256:partial-sidecar-claims",
    )
    plan = build_method_section_plan(claims=claims)
    completeness = MethodCompletenessMatrixV1(items=[
        MethodCompletenessItemV1(
            obligation_id="obl:supported",
            status="supported_by_repository",
            claim_ids=("claim:partial-supported",),
        ),
        MethodCompletenessItemV1(
            obligation_id="obl:diagnostic-partial",
            status="partially_supported_by_repository",
            claim_ids=(),
        ),
    ])
    output = PublicationMethodSectionOutputV1(
        section_id=plan.sections[0].section_id,
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=list(plan.sections[0].argument_unit_ids),
        used_claim_ids=["claim:partial-supported"],
        completed_rhetorical_moves=_COMPLETED_CORE_MOVES,
    )
    ledger = ledger_from_section_outputs(
        output.section_markdown,
        ((output.section_id, output.section_markdown, "sha256:partial-sidecar"),),
    )

    report = evaluate_publication_method_quality(
        final_text=output.section_markdown,
        plan=plan,
        completeness=completeness,
        section_outputs=(output,),
        ledger=ledger,
    )

    assert report.plan_gate_passed is True
    assert report.utility.completeness_coverage == 1.0
    sidecar = next(
        row for row in report.coverage_matrix
        if row["obligation_id"] == "obl:diagnostic-partial"
    )
    assert sidecar["required_in_final"] is False
    assert sidecar["coverage_status"] == "sidecar"


def test_formalization_agent_bounded_retry_approves_only_guard_clean_proposal(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)

    def formalization_caller(_config, request):
        attempts = getattr(formalization_caller, "calls", 0)
        formalization_caller.calls = attempts + 1
        if attempts == 0:
            items = [{
                "kind": "derivation_step",
                "statement": "The encoder reads the configured input before scoring it.",
                "fact_ids": ["fact:invented"],
                "equation_ids": [],
            }]
        else:
            items = [{
                "kind": "pseudocode",
                "statement": "The encoder reads the configured input before returning its representation.",
                "fact_ids": ["fact-read"],
                "equation_ids": [],
            }]
        return LLMResponse(
            text=json.dumps({"proposal_id": f"proposal-{attempts}", "items": items}),
            response_hash=f"sha256:formalizer-{attempts}",
            finish_reason="stop",
        )

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer-response",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        formalization_caller=formalization_caller,
    )

    assert formalization_caller.calls == 2
    agent_result = json.loads(Path(outputs["formalization_agent_result_v1"]).read_text())
    assert [entry["status"] for entry in agent_result["attempts"]] == ["guards_failed", "accepted"]
    assert agent_result["approved_item_count"] == 1
    assert agent_result["approved_items"][0]["kind"] == "pseudocode"
    formalization = json.loads(Path(outputs["formalization_result_v1"]).read_text())
    assert len(formalization["proposal_items"]) == 1
    assert result.status in {"success", "incomplete"}


def test_formalization_agent_double_guard_failure_keeps_proposal_out(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)

    def formalization_caller(_config, request):
        calls = getattr(formalization_caller, "calls", 0)
        formalization_caller.calls = calls + 1
        return LLMResponse(
            text=json.dumps({"proposal_id": f"proposal-{calls}", "items": [{
                "kind": "validation_conclusion",
                "statement": "The encoder converges to the optimal representation.",
                "fact_ids": ["fact-read"],
                "equation_ids": [],
            }]}),
            response_hash=f"sha256:formalizer-{calls}",
            finish_reason="stop",
        )

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer-response",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        formalization_caller=formalization_caller,
    )

    assert formalization_caller.calls == 2
    agent_result = json.loads(Path(outputs["formalization_agent_result_v1"]).read_text())
    assert [entry["status"] for entry in agent_result["attempts"]] == ["guards_failed", "guards_failed"]
    assert agent_result["approved_item_count"] == 0
    formalization = json.loads(Path(outputs["formalization_result_v1"]).read_text())
    assert formalization["proposal_items"] == []
    assert any(risk["kind"] == "proposal_guards_failed" for risk in formalization["risks"])


def test_editor_patch_improving_duplication_by_deleting_unique_content_is_rejected(
    tmp_path: Path,
) -> None:
    paths = _two_section_plan(tmp_path)
    config_path = Path(paths["configuration_claims_v1"])
    configurations = ConfigurationClaimSetV1.model_validate_json(config_path.read_text())
    extra_config = ConfigurationClaimV1(
        configuration_id="config:knn",
        key="knn_method",
        value="ivf",
        state="default",
        source_fact_ids=["fact:config"],
        canonical_identity="sha256:config:knn",
    )
    configurations = configurations.model_copy(update={
        "claims": (*configurations.claims, extra_config)
    })
    config_path.write_text(configurations.model_dump_json(indent=2), encoding="utf-8")
    plan_path = Path(paths["method_section_plan_v2"])
    plan = MethodSectionPlanV2.model_validate_json(plan_path.read_text())
    unit = plan.argument_units[0]
    unit = unit.model_copy(update={
        "configuration_ids": (*unit.configuration_ids, extra_config.configuration_id)
    })
    plan = plan.model_copy(update={
        "argument_units": (unit,),
        "sections": tuple(
            section.model_copy(update={
                "argument_unit_ids": (unit.argument_unit_id,)
            })
            for section in plan.sections
        ),
    })
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    duplicate_and_unique = (
        "## Output interface\n\nIts representation is returned to the downstream stage."
        " Its representation is returned to the downstream stage."
        " The encoder reads the configured input."
        " The branch selects the ivf variant of knn_method."
    )

    def writer_caller(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        body = (
            "## Encoder\n\nThe encoder reads the configured input."
            if section_id == "MA-S1"
            else duplicate_and_unique
        )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": body,
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash=f"sha256:writer:{section_id}",
            finish_reason="stop",
        )

    def editor_caller(_config, request):
        before = request.input_payload["sections"]["MA-S2"]
        return LLMResponse(
            text=json.dumps({"patches": [{
                "patch_id": "editor:no-loss-violation",
                "section_id": "MA-S2",
                "before_digest": "sha256:" + hashlib.sha256(before.encode()).hexdigest(),
                "replacement_text": (
                    "## Output interface\n\nIts representation is returned to the downstream stage."
                    " The encoder reads the configured input."
                ),
                "generation_source": "editor",
                "reason": "Remove the repeated sentence.",
                "scoped": True,
            }]}),
            response_hash="sha256:editor-response",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        editor_caller=editor_caller,
    )

    assert any(
        "editor_candidate_rejected" in failure
        for failure in result.binding_failures
    )
    editor = json.loads(Path(outputs["publication_editor_result_v1"]).read_text())
    assert editor["blocked_reason"].startswith("editor_candidate_rejected:")
    assert "candidate_configuration_loss" in editor["blocked_reason"]
    assert editor["sections"]["MA-S2"] == duplicate_and_unique
    transitions = json.loads(Path(outputs["publication_editor_transitions_v1"]).read_text())
    assert transitions["decision"] == "reject"
    assert any("candidate_configuration_loss" in reason for reason in transitions["reasons"])
    final_text = Path(outputs["publication_candidate_method"]).read_text()
    assert "ivf variant of knn_method" in final_text
    assert final_text.count("Its representation is returned to the downstream stage.") == 2


def test_cross_section_editor_batches_large_documents_and_preserves_response_refs() -> None:
    sections = {
        f"MA-S{index}": f"## Section {index}\n\nOriginal mechanism {index}."
        for index in range(1, 10)
    }
    calls: list[list[str]] = []

    def caller(_config, request):
        batch = request.input_payload["sections"]
        calls.append(list(batch))
        section_id = next(iter(batch))
        before = batch[section_id]
        replacement = before.replace("Original", "Revised")
        return LLMResponse(
            text=json.dumps({"patches": [{
                "patch_id": f"edit-{section_id}",
                "section_id": section_id,
                "before_digest": "sha256:" + hashlib.sha256(before.encode()).hexdigest(),
                "before_text": before,
                "replacement_text": replacement,
                "generation_source": "editor",
                "reason": "Improve academic wording.",
                "scoped": True,
            }]}),
            response_hash=f"sha256:editor:{len(calls)}",
            finish_reason="stop",
        )

    result = CrossSectionEditor().edit_with_llm(
        sections,
        section_contexts={section_id: {} for section_id in sections},
        document_context={
            "section_order": [
                {"section_id": section_id} for section_id in sections
            ]
        },
        config=_config(),
        caller=caller,
    )

    assert [len(batch) for batch in calls] == [4, 4, 1]
    assert len(result.patches) == 3
    assert result.response_refs == (
        "sha256:editor:1",
        "sha256:editor:2",
        "sha256:editor:3",
    )
    assert [patch.generation_trace_ids[-1] for patch in result.patches] == list(
        result.response_refs
    )
    assert all("Revised" in result.sections[batch[0]] for batch in calls)


def test_utility_gate_rejects_fact_inventory_prose() -> None:
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    plan = _quality_plan(claims=(claim.claim_id,))
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown=(
            "## Encoder\n\nsym:a5d88ed0f95e4907 computes formula N, args.keep_percent."
        ),
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )

    report = _quality_report(plan=plan, completeness=completeness, sections=[output], claims=claims)

    assert report.safety.hard_gate_passed is True
    assert report.utility.terminology_notation_consistent is False
    assert report.utility.utility_gate_passed is False
    assert any(issue.code == "internal_bookkeeping_exposed" for issue in report.issues)
    assert any(issue.code == "required_move_content_missing" for issue in report.issues)


def test_utility_gate_rejects_readable_code_audit_inventory_without_internal_ids() -> None:
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    plan = _quality_plan(claims=(claim.claim_id,))
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    # The attempt-3 DyG failure shape: readable inventory lines without any
    # sym:/internal id — "<Class.method> calls <operand>, <operand>".
    inventory = (
        "## Encoder\n\n"
        "GraphAttentionEmbedding.compute_node_temporal_embeddings loads weights self.node_raw_features. "
        "GraphAttentionEmbedding.compute_node_temporal_embeddings calls torch.load, load_path."
    )
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown=inventory,
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )

    report = _quality_report(plan=plan, completeness=completeness, sections=[output], claims=claims)

    assert report.safety.hard_gate_passed is True
    assert report.utility.utility_gate_passed is False
    assert any(issue.code == "code_audit_list" for issue in report.issues)
    assert report.utility.content_role_status.get("transformation") == "missing"


def test_expository_bridge_sentence_is_claim_free_and_fail_closed() -> None:
    from code2paper.agentic.final_text_claims import extract_final_text_claims
    from code2paper.agentic.trust_contracts import (
        AuthoringInputProjection,
        ProjectedClaim,
    )

    projection = AuthoringInputProjection(
        project_id="fixture",
        method_name="Encoder",
        author_goal="Describe the encoder.",
        implementation_scope="fixture repository",
        projection_digest="sha256:projection",
        projected_claims=[
            ProjectedClaim(
                claim_id="claim-a",
                claim_text="The encoder reads the configured input.",
                support_status="supported",
                direct_evidence_ids=["span:encoder.py:1:2"],
                supported_fragment="The encoder reads the configured input.",
                allowed_wording_boundary="reads configured input",
                input_digest="sha256:claim-a",
            )
        ],
        author_attested_fragments=[],
    )
    text = (
        "## Encoder\n\n"
        "In this section we describe the method.\n"
        "The encoder reads the configured input.\n"
        "Next, the encoder stores the input twice.\n"
        "In this section we explain how the cache accelerates retrieval.\n"
        "We now describe a capability that guarantees faster search.\n"
        "Next, the method improves the accuracy of the scores.\n"
        "This method can address the objective.\n"
        "This approach will address the goal.\n"
        "Next, the method can cover the section.\n"
    )
    claims = extract_final_text_claims(text, projection)

    units = {item.text: item for item in claims.units}
    assert units["In this section we describe the method."].kind == "expository_bridge"
    assert units["In this section we describe the method."].factual is False
    assert units["The encoder reads the configured input."].factual is True
    # "stores the input twice" carries a number (risk) -> stays factual.
    assert units["Next, the encoder stores the input twice."].factual is True
    # Adversarial unseen factual suffixes stay factual (fail-closed).
    assert units["In this section we explain how the cache accelerates retrieval."].factual is True
    assert units["We now describe a capability that guarantees faster search."].factual is True
    assert units["Next, the method improves the accuracy of the scores."].factual is True
    # All-allowlist capability/purpose assertions also stay factual.
    assert units["This method can address the objective."].factual is True
    assert units["This approach will address the goal."].factual is True
    assert units["Next, the method can cover the section."].factual is True
    assert any(item.text == "The encoder reads the configured input." for item in claims.atomic_claims)


def test_wrapped_and_frozen_inventory_text_is_audit_detected() -> None:
    """R4-A1b: wrapper/backtick evasions and frozen inventory text stay
    audit-flagged; genuinely readable prose is not."""
    from code2paper.agentic.publication_quality import _code_audit_sentences

    wrapped_evasions = [
        "The method first prune_points loads weights self._features_dc.",
        "The `prune_points` method calls scores, scores.numpy.",
        "It then GaussianModel.prune_points computes formula N, args.keep_percent.",
        "And finally it `prune_pure_feature` returns scores.",
    ]
    for evasion in wrapped_evasions:
        assert _code_audit_sentences(evasion) != [], evasion

    readable = (
        "## Score prediction\n\n"
        "After loading the feature weights, the method computes the scores from the "
        "keep-percent argument and then returns the ranked results."
    )
    assert _code_audit_sentences(readable) == []

    # Frozen attempt-10 EBCAR candidate: the quality report recorded code_audit
    # issues; the hardened detector must still flag it.
    ebcar_frozen = Path(
        "/tmp/code2paper-post-r8-d5-consolidated-20260809-10/ebcar/"
        "artifacts/06_authoring/publication_candidate_method.md"
    )
    if ebcar_frozen.is_file():
        assert _code_audit_sentences(ebcar_frozen.read_text(encoding="utf-8")) != []


def test_replan_moves_with_trace_produces_semantic_section_graph(
    tmp_path: Path,
) -> None:
    from code2paper.agentic.method_architect import replan_moves_with_trace

    paths = _artifacts(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(Path(paths["atomic_claims_v3"]).read_text())
    facts = CodeFactSetV1.model_validate_json(Path(paths["code_facts_v1"]).read_text())
    equations = EquationClaimSetV1.model_validate_json(Path(paths["equation_claims_v1"]).read_text())
    configurations = ConfigurationClaimSetV1.model_validate_json(
        Path(paths["configuration_claims_v1"]).read_text()
    )
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    )
    plan = MethodSectionPlanV2.model_validate_json(Path(paths["method_section_plan_v2"]).read_text())

    new_plan, trace = replan_moves_with_trace(
        base_plan=plan,
        claims=claims,
        equations=equations,
        configurations=configurations,
        completeness=completeness,
        facts=facts,
    )

    # Structure preserved: same section ids and unit ids.
    assert [s.section_id for s in new_plan.sections] == [s.section_id for s in plan.sections]
    assert [u.argument_unit_id for u in new_plan.argument_units] == [
        u.argument_unit_id for u in plan.argument_units
    ]
    # Semantic planning: reader questions and method points derived per unit,
    # and applied to the argument units where the design permits.
    assert len(trace["sections"]) == len(plan.sections)
    for row in trace["sections"]:
        assert row["reader_question"]
        assert row["method_point"]
        assert "frame" in row
        assert "move_anchor_ids" in row
    for unit in new_plan.argument_units:
        assert unit.research_question
        assert unit.design_objective
    # Trace-backed replanning must carry the freshly derived semantic frames
    # into the paragraph contracts.  Otherwise every unit collapses to an
    # unbound overview paragraph even though the architect trace has slots.
    rebuilt_paragraphs = [
        paragraph
        for section in new_plan.sections
        for paragraph in section.paragraphs
    ]
    assert rebuilt_paragraphs
    assert any(paragraph.ordered_semantic_slot_ids for paragraph in rebuilt_paragraphs)
    assert any(paragraph.paragraph_role != "overview" for paragraph in rebuilt_paragraphs)
    # The generic "Implementation stage 1" heading is replaced by a
    # content-derived stage heading.
    assert any(
        s.heading != "Implementation stage 1" for s in new_plan.sections
    )
    # Obligation placements are fully typed assignments bound to the plan.
    assert trace["obligation_assignments"]
    assert new_plan.obligation_assignments
    assert any(
        assignment.obligation_id == item.obligation_id
        for assignment in new_plan.obligation_assignments
        for item in completeness.items
    )
    # Move authority proofs are typed and digest-bound on the plan.
    assert new_plan.move_authority_proofs
    # Data-flow dependencies are recorded.
    assert isinstance(trace["section_dependencies"], dict)
    assert "obligation_assignments" in trace
    assert "move_authority_proofs" in trace
    assert trace["schema_version"] == "2.0"
    # The complete critical/high set and its source digest are closed over the
    # assignment sidecar; dropping one row can no longer produce a valid plan.
    assert set(new_plan.critical_high_obligation_ids) == {
        item.obligation_id for item in completeness.items
        if item.importance in {"critical", "high"}
    }
    assert new_plan.completeness_digest == completeness.content_digest
    with pytest.raises(ValueError, match="assignments are not complete"):
        MethodSectionPlanV2.model_validate(
            new_plan.model_dump(mode="json") | {
                "obligation_assignments": [
                    item.model_dump(mode="json")
                    for item in new_plan.obligation_assignments[:-1]
                ],
            }
        )


def test_exact_semantic_stage_source_binding_overrides_cross_stage_claim_ambiguity() -> None:
    """R6-B: persisted source-obligation authority narrows a claim set that
    legitimately contains relation claims from two neighboring units."""
    from types import SimpleNamespace
    from code2paper.agentic.method_architect import place_obligation_assignments

    units = (
        MethodArgumentUnitV1(
            argument_unit_id="unit:a", section_role="stage",
            research_question="A?", claim_ids=("claim:a",),
        ),
        MethodArgumentUnitV1(
            argument_unit_id="unit:b", section_role="stage",
            research_question="B?", claim_ids=("claim:b",),
        ),
    )
    row = MethodCompletenessItemV1(
        obligation_id="obl:b", importance="critical",
        status="supported_by_repository", role="stage",
        claim_ids=("claim:a", "claim:b"),
    )
    agenda_row = SimpleNamespace(
        obligation_id="obl:b", source_obligation_id="obl:b", role="stage",
        candidate_symbols=(), research_queries=(),
    )
    assignments, trace = place_obligation_assignments(
        matrix_rows=[row], units=units,
        section_by_unit={"unit:a": "section:a", "unit:b": "section:b"},
        unit_frames={},
        unit_fact_ids={"unit:a": set(), "unit:b": set()},
        unit_claim_ids={"unit:a": {"claim:a"}, "unit:b": {"claim:b"}},
        unit_source_obligation_ids={"unit:a": {"obl:a"}, "unit:b": {"obl:b"}},
        unit_roles={"unit:a": ("stage",), "unit:b": ("stage",)},
        unit_equation_ids={}, unit_configuration_ids={},
        coverage_by_obligation={}, agenda_by_id={"obl:b": agenda_row},
    )
    assert assignments[0].argument_unit_id == "unit:b"
    assert assignments[0].placement_state == "assigned"
    assert trace[0]["target_reason"] == "agenda_source_obligation_id"


def test_relation_evidence_requires_exact_operation_endpoints() -> None:
    """R8-B: a relation whose operation-level endpoint cannot be resolved to
    exact slots stays unresolved; an opaque same-symbol self-edge is never
    accepted as positive flow."""
    from code2paper.agentic.method_architect import build_semantic_argument_frame
    from code2paper.agentic.evidence_compiler_v3 import RelationEndpointV3, RelationEvidenceV3

    class _Fact:
        def __init__(self, fid, subject, predicate, obj, rels=()):
            self.fact_id = fid
            self.subject = subject
            self.predicate = predicate
            self.object = obj
            self.conditions = []
            self.validation_status = "supported"
            self.relation_evidence_ids = list(rels)
            self.scope = subject
            self.direct_span_ids = [f"span:{subject}:1:1"]

    class _Claim:
        def __init__(self, cid, fids, rels=()):
            self.claim_id = cid
            self.fact_ids = tuple(fids)
            self.relation_evidence_ids = tuple(rels)

    # An unresolved relation (no endpoint records) referencing a real fact.
    unresolved = RelationEvidenceV3(
        relation_id="rel:opaque",
        relation_type="data_flow",
        source_symbol="load_stage",
        target_symbol="load_stage",
        source_endpoint=None,
        target_endpoint=None,
        statement="DATA_FLOW: load_stage -> load_stage",
    )
    facts = {
        "fact:load": _Fact("fact:load", "load_stage", "loads_weights", "features", rels=("rel:opaque",)),
    }
    claims = {
        "claim:load": _Claim("claim:load", ("fact:load",), rels=("rel:opaque",)),
    }
    frame = build_semantic_argument_frame(
        argument_unit_id="unit:encoder",
        claim_ids=("claim:load",),
        equation_ids=(),
        configuration_ids=(),
        claim_by_id=claims,
        fact_by_id=facts,
        relation_by_id={"rel:opaque": unresolved},
        obligation_ids=(),
        authority_lanes=("executable_hard",),
    )
    assert frame.edges == ()
    assert "rel:opaque" in frame.unresolved_relation_ids
    # A same-symbol edge with distinct operation endpoints cannot bind two
    # different slots (only one slot exists), so it stays unresolved too.
    opaque = RelationEvidenceV3(
        relation_id="rel:self",
        relation_type="data_flow",
        source_symbol="load_stage",
        target_symbol="load_stage",
        source_endpoint=RelationEndpointV3(
            node_id="node:a", symbol_id="load_stage", operation_subject="load_stage",
            predicate="LOAD", operands=("features",), source_span_id="span:load_stage:1:1",
        ),
        target_endpoint=RelationEndpointV3(
            node_id="node:a", symbol_id="load_stage", operation_subject="load_stage",
            predicate="LOAD", operands=("features",), source_span_id="span:load_stage:1:1",
        ),
        statement="DATA_FLOW: load_stage -> load_stage",
    )
    facts2 = dict(facts)
    facts2["fact:load"] = _Fact("fact:load", "load_stage", "loads_weights", "features", rels=("rel:self",))
    claims2 = {"claim:load": _Claim("claim:load", ("fact:load",), rels=("rel:self",))}
    frame2 = build_semantic_argument_frame(
        argument_unit_id="unit:encoder",
        claim_ids=("claim:load",),
        equation_ids=(),
        configuration_ids=(),
        claim_by_id=claims2,
        fact_by_id=facts2,
        relation_by_id={"rel:self": opaque},
        obligation_ids=(),
        authority_lanes=("executable_hard",),
    )
    assert frame2.edges == ()
    assert "rel:self" in frame2.unresolved_relation_ids


def test_pre_writer_gate_no_longer_blocks_on_unplaced_critical_high(tmp_path: Path) -> None:
    """A-product gate: a critical/high row that remains typed unplaced is
    ordinary planning debt — it must NOT stop the Writer.  The candidate is
    still written; the unplaced obligation surfaces as an explicit review
    item (blocks verified coverage decisions, never candidate output)."""
    paths = _artifacts(tmp_path)
    plan = MethodSectionPlanV2.model_validate_json(Path(paths["method_section_plan_v2"]).read_text())
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    ).model_copy(update={
        "items": (
            *MethodCompletenessMatrixV1.model_validate_json(
                Path(paths["method_completeness_matrix_v1"]).read_text()
            ).items,
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-99-unplaced",
                status="supported_by_repository",
                claim_ids=("claim:does-not-exist",),
                importance="critical",
                reason="No unit binds this obligation after replanning.",
            ),
        )
    })
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )
    from code2paper.agentic.publication_method_writer import run_publication_method_writer

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-unplaced",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
        rebuild_architect_plan=True,
    )
    assert result.status != "blocked"
    assert "critical_high_obligation_unplaced" not in result.blocked_reason
    assert Path(outputs["publication_candidate_method"]).read_text().strip().startswith("## Encoder")
    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    unplaced = [item for item in review["items"] if item["candidate_id"] == "review-unplaced:O-STAGE-99-unplaced"]
    assert unplaced and unplaced[0]["proposed_body"] and unplaced[0]["confirmation_question"]
    assert unplaced[0]["blocks_verified"] is False
    assert unplaced[0]["blocks_candidate"] is False


def test_zero_candidate_gap_routes_to_scoped_owner_not_empty_proposal() -> None:
    """R8-C: a no-candidate critical gap row routes to its scoped owner as an
    explicit external_pending assignment (never an empty-set Architect choice);
    a supported row with no closed target stays fully typed unplaced."""
    from code2paper.agentic.method_architect import place_obligation_assignments

    class _Row:
        def __init__(self, obligation_id, status, importance, authority_lane,
                     claim_ids=(), equation_ids=(), configuration_ids=(),
                     source_artifact_ids=(), reason="", next_action=""):
            self.obligation_id = obligation_id
            self.status = status
            self.importance = importance
            self.authority_lane = authority_lane
            self.claim_ids = tuple(claim_ids)
            self.equation_ids = tuple(equation_ids)
            self.configuration_ids = tuple(configuration_ids)
            self.source_artifact_ids = tuple(source_artifact_ids)
            self.reason = reason
            self.next_action = next_action

    assignments, trace = place_obligation_assignments(
        matrix_rows=[
            _Row("obl-gap", "explicit_code_gap", "critical", "executable_hard",
                 source_artifact_ids=("span:gap.py:1:1",),
                 reason="not implemented", next_action="ask the author"),
            _Row("obl-supported", "supported_by_repository", "critical", "executable_hard",
                 claim_ids=("claim:nowhere",), reason="no unit",
                 next_action=""),
        ],
        units=(),
        section_by_unit={},
        unit_frames={},
        unit_fact_ids={},
        unit_claim_ids={},
        unit_source_obligation_ids={},
        unit_roles={},
        unit_equation_ids={},
        unit_configuration_ids={},
        coverage_by_obligation={},
        agenda_by_id={},
    )
    by_id = {item.obligation_id: item for item in assignments}
    gap = by_id["obl-gap"]
    assert gap.placement_state == "external_pending"
    assert gap.required_move == "limitations_or_mismatch"
    assert gap.authority_lane == "executable_hard"
    assert gap.source_artifact_ids == ("span:gap.py:1:1",)
    assert gap.unresolved_reason == "not implemented"
    assert gap.next_action == "ask the author"
    supported = by_id["obl-supported"]
    assert supported.placement_state == "unplaced"
    assert supported.required_move == ""
    assert supported.unresolved_reason


def test_replan_dependencies_follow_fact_producer_consumer_flow(
    tmp_path: Path,
) -> None:
    from code2paper.agentic.method_architect import replan_moves_with_trace

    paths = _artifacts(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(Path(paths["atomic_claims_v3"]).read_text())
    equations = EquationClaimSetV1.model_validate_json(Path(paths["equation_claims_v1"]).read_text())
    configurations = ConfigurationClaimSetV1.model_validate_json(
        Path(paths["configuration_claims_v1"]).read_text()
    )
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    )
    plan = MethodSectionPlanV2.model_validate_json(Path(paths["method_section_plan_v2"]).read_text())

    # Three sections.  Section 2's claim consumes the result token produced by
    # section 1's claim (data flow A -> B); section 3 is unrelated.
    class _Producer:
        fact_id = "fact:producer"
        subject = "load_stage"
        predicate = "loads_weights"
        object = "scores"
        conditions = []
        validation_status = "supported"
        claim_ids = ()
        scope = "load_stage"
        direct_span_ids = ["span:load_stage:1:1"]
        relation_evidence_ids = ["rel:flow"]

    class _Consumer:
        fact_id = "fact:consumer"
        subject = "compute_stage"
        predicate = "computes_formula"
        object = ["scores", "keep_percent"]
        conditions = []
        validation_status = "supported"
        claim_ids = ()
        scope = "compute_stage"
        direct_span_ids = ["span:compute_stage:1:1"]
        relation_evidence_ids = ["rel:flow"]

    class _Unrelated:
        fact_id = "fact:unrelated"
        subject = "report_stage"
        predicate = "returns"
        object = "summary"
        conditions = []
        validation_status = "supported"
        claim_ids = ()
        scope = "report_stage"
        direct_span_ids = ["span:report_stage:1:1"]
        relation_evidence_ids = []

    class _Facts:
        facts = [_Producer(), _Consumer(), _Unrelated()]
        content_digest = "sha256:facts3"

    class _ClaimA:
        claim_id = "claim:producer"
        canonical_text = "load_stage loads weights scores"
        fact_ids = ("fact:producer",)
        status = "supported"
        covers_obligation_ids = ("obl:a",)
        direct_evidence_ids = []
        relation_evidence_ids = []
        allowed_wording_boundary = "x"
        required_qualifiers = []
        canonical_identity = "c1"

    class _ClaimB:
        claim_id = "claim:consumer"
        canonical_text = "compute_stage computes formula scores, keep_percent"
        fact_ids = ("fact:consumer",)
        status = "supported"
        covers_obligation_ids = ("obl:b",)
        direct_evidence_ids = []
        relation_evidence_ids = []
        allowed_wording_boundary = "x"
        required_qualifiers = []
        canonical_identity = "c2"

    class _ClaimC:
        claim_id = "claim:unrelated"
        canonical_text = "report_stage returns summary"
        fact_ids = ("fact:unrelated",)
        status = "supported"
        covers_obligation_ids = ("obl:c",)
        direct_evidence_ids = []
        relation_evidence_ids = []
        allowed_wording_boundary = "x"
        required_qualifiers = []
        canonical_identity = "c3"

    class _Claims:
        claims = [_ClaimA(), _ClaimB(), _ClaimC()]
        content_digest = "sha256:claims3"

    # 3-section plan: MA-S1 producer, MA-S2 consumer, MA-S3 unrelated.
    unit_a = MethodArgumentUnitV1(
        argument_unit_id="MA-S1:unit",
        section_role="stage",
        research_question="Stage A",
        design_objective="Stage A objective",
        claim_ids=("claim:producer",),
        authority_lanes=("executable_hard",),
    )
    unit_b = MethodArgumentUnitV1(
        argument_unit_id="MA-S2:unit",
        section_role="stage",
        research_question="Stage B",
        design_objective="Stage B objective",
        claim_ids=("claim:consumer",),
        authority_lanes=("executable_hard",),
    )
    unit_c = MethodArgumentUnitV1(
        argument_unit_id="MA-S3:unit",
        section_role="stage",
        research_question="Stage C",
        design_objective="Stage C objective",
        claim_ids=("claim:unrelated",),
        authority_lanes=("executable_hard",),
    )
    plan_3 = MethodSectionPlanV2(
        plan_id="plan-3",
        sections=(
            SectionArgumentGraphV1(
                section_id="MA-S1",
                heading="Stage A",
                reader_question="Stage A question",
                argument_unit_ids=(unit_a.argument_unit_id,),
            ),
            SectionArgumentGraphV1(
                section_id="MA-S2",
                heading="Stage B",
                reader_question="Stage B question",
                argument_unit_ids=(unit_b.argument_unit_id,),
            ),
            SectionArgumentGraphV1(
                section_id="MA-S3",
                heading="Stage C",
                reader_question="Stage C question",
                argument_unit_ids=(unit_c.argument_unit_id,),
            ),
        ),
        argument_units=(unit_a, unit_b, unit_c),
        method_name="Fixture",
    )

    # A typed DATA_FLOW relation from the producer symbol to the consumer
    # symbol is the ONLY source of the cross-section dependency.  The
    # operation-level endpoints carry the exact spans of both endpoint facts.
    class _Endpoint:
        def __init__(self, symbol, span, operands):
            self.node_id = f"node:{symbol}"
            self.symbol_id = symbol
            self.operation_subject = symbol
            self.predicate = ""
            self.operands = tuple(operands)
            self.produced_entity = ""
            self.source_span_id = span

        @property
        def resolved(self) -> bool:
            return True

    class _Relation:
        relation_id = "rel:flow"
        source_symbol = "load_stage"
        target_symbol = "compute_stage"
        statement = "DATA_FLOW: load_stage -> compute_stage"
        relation_type = "data_flow"
        direct_span_ids = []
        conditions = []
        source_endpoint = _Endpoint("load_stage", "span:load_stage:1:1", ())
        target_endpoint = _Endpoint("compute_stage", "span:compute_stage:1:1", ())

    class _Packet:
        relations = [_Relation()]
        spans = []

    class _Packets:
        packets = [_Packet()]

    class _ClaimAWithRelation(_ClaimA):
        relation_evidence_ids = ("rel:flow",)

    class _ClaimBWithRelation(_ClaimB):
        relation_evidence_ids = ("rel:flow",)

    class _ClaimsWithRelation:
        claims = [_ClaimAWithRelation(), _ClaimBWithRelation(), _ClaimC()]
        content_digest = "sha256:claims3"

    new_plan, trace = replan_moves_with_trace(
        base_plan=plan_3,
        claims=_ClaimsWithRelation(),
        equations=equations,
        configurations=configurations,
        completeness=completeness,
        facts=_Facts(),
        evidence_packets_v3=_Packets(),
    )
    deps = trace["section_dependencies"]
    # The consumer section depends on the producer section via the typed
    # DATA_FLOW relation; no scalar-shape guessing occurs.
    assert "MA-S1" in deps.get("MA-S2", [])
    assert "MA-S2" not in deps.get("MA-S1", [])
    assert "MA-S1" not in deps.get("MA-S3", [])
    assert "MA-S2" not in deps.get("MA-S3", [])


def test_semantic_flow_input_is_non_inventory_with_exact_bindings() -> None:
    """R5-E1: the typed semantic frame preserves scalar and list operands,
    subject, predicate, conditions, authorized output, and exact relation
    bindings; unrelated relations do not become flow edges; the Architect
    builder is the single frame source (Writer serializes it)."""
    from code2paper.agentic.method_architect import build_semantic_argument_frame
    from code2paper.agentic.publication_quality import _code_audit_sentences

    class _Fact:
        def __init__(self, fact_id, subject, predicate, obj, conditions=(), relations=()):
            self.fact_id = fact_id
            self.subject = subject
            self.predicate = predicate
            self.object = obj
            self.conditions = list(conditions)
            self.validation_status = "supported"
            self.relation_evidence_ids = list(relations)
            self.scope = subject
            self.direct_span_ids = [f"span:{subject}:1:1"]

    class _Endpoint:
        def __init__(self, symbol, span, operands):
            self.node_id = f"node:{symbol}"
            self.symbol_id = symbol
            self.operation_subject = symbol
            self.predicate = ""
            self.operands = tuple(operands)
            self.produced_entity = ""
            self.source_span_id = span

        @property
        def resolved(self) -> bool:
            return True

    class _Relation:
        def __init__(self, relation_id, relation_type, source, target):
            self.relation_id = relation_id
            self.relation_type = relation_type
            self.source_symbol = source
            self.target_symbol = target
            self.direct_span_ids = []
            self.conditions = []
            self.source_endpoint = _Endpoint(source, f"span:{source}:1:1", ())
            self.target_endpoint = _Endpoint(target, f"span:{target}:1:1", ())

    relation = _Relation("rel:load-to-compute", "data_flow", "load_stage", "compute_stage")
    unrelated = _Relation("rel:elsewhere", "data_flow", "somewhere", "else")
    facts = {
        "fact:load": _Fact(
            "fact:load", "load_stage", "loads_weights", "features",
            relations=("rel:load-to-compute",),
        ),
        "fact:compute": _Fact(
            "fact:compute", "compute_stage", "computes_formula",
            ["features", "keep_percent"], conditions=("when keep_percent > 0",),
            relations=("rel:load-to-compute", "rel:elsewhere"),
        ),
        "fact:return": _Fact("fact:return", "output_stage", "returns", "scores"),
    }
    claims = {
        "claim:load": type("C", (), {"fact_ids": ("fact:load",), "relation_evidence_ids": ("rel:load-to-compute",)})(),
        "claim:compute": type("C", (), {"fact_ids": ("fact:compute",), "relation_evidence_ids": ("rel:load-to-compute", "rel:elsewhere")})(),
        "claim:return": type("C", (), {"fact_ids": ("fact:return",), "relation_evidence_ids": ()})(),
    }
    relations = {
        "rel:load-to-compute": relation,
        "rel:elsewhere": unrelated,
    }
    frame = build_semantic_argument_frame(
        argument_unit_id="unit:encoder",
        claim_ids=("claim:load", "claim:compute", "claim:return"),
        equation_ids=(),
        configuration_ids=(),
        claim_by_id=claims,
        fact_by_id=facts,
        relation_by_id=relations,
        obligation_ids=(),
        authority_lanes=("executable_hard",),
    )
    import json as _json
    serialized = _json.dumps(frame.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    assert _code_audit_sentences(serialized) == []
    roles = {slot.role: slot for slot in frame.slots}
    assert set(roles) == {"input", "transformation", "output"}
    assert roles["input"].fact_ids == ("fact:load",)
    assert roles["output"].fact_ids == ("fact:return",)
    assert roles["output"].produced_entities == ("scores",)
    # List-valued operands survive; the transformation slot is never empty.
    assert roles["transformation"].operands == ("features", "keep_percent")
    assert roles["transformation"].conditions == ("when keep_percent > 0",)
    # The data_flow relation binds only the exact facts/claims that carry it;
    # the unrelated relation is unresolved, never copied onto every slot.
    assert roles["transformation"].exact_relation_ids == ("rel:load-to-compute",)
    assert roles["input"].exact_relation_ids == ("rel:load-to-compute",)
    assert [edge.relation_id for edge in frame.edges] == ["rel:load-to-compute"]
    assert frame.edges[0].relation_type == "data_flow"
    assert "rel:elsewhere" in frame.unresolved_relation_ids


def test_loads_weights_scalar_object_is_consumer_not_producer() -> None:
    """R5-E1: a loads_weights fact with a scalar object is an input consumer;
    scalar shape alone must never create a producer/output edge."""
    from code2paper.agentic.method_architect import build_semantic_argument_frame

    class _Load:
        fact_id = "fact:load"
        subject = "load_stage"
        predicate = "loads_weights"
        object = "scores"
        conditions = []
        validation_status = "supported"
        relation_evidence_ids = []

    frame = build_semantic_argument_frame(
        argument_unit_id="unit:load",
        claim_ids=("claim:load",),
        equation_ids=(),
        configuration_ids=(),
        claim_by_id={"claim:load": type("C", (), {"fact_ids": ("fact:load",), "relation_evidence_ids": ()})()},
        fact_by_id={"fact:load": _Load()},
        relation_by_id={},
        obligation_ids=(),
        authority_lanes=("executable_hard",),
    )
    roles = {slot.role: slot for slot in frame.slots}
    assert roles["input"].fact_ids == ("fact:load",)
    assert "output" not in roles
    assert frame.edges == ()


def test_semantic_relation_cycle_is_explicit_and_not_serialized_as_edges() -> None:
    """R6-C: a closed two-edge cycle remains unresolved instead of receiving
    a fabricated topological order."""
    from code2paper.agentic.method_architect import build_semantic_argument_frame

    class _Fact:
        def __init__(self, fact_id, subject, obj, relations):
            self.fact_id = fact_id
            self.subject = subject
            self.predicate = "computes"
            self.object = obj
            self.conditions = []
            self.validation_status = "supported"
            self.relation_evidence_ids = relations

    class _Relation:
        relation_type = "data_flow"
        direct_span_ids = []
        conditions = []

        def __init__(self, relation_id, source, target):
            self.relation_id = relation_id
            self.source_symbol = source
            self.target_symbol = target

    facts = {
        "fact:a": _Fact("fact:a", "stage_a", "stage_b", ["rel:a-b"]),
        "fact:b": _Fact("fact:b", "stage_b", "stage_a", ["rel:b-a"]),
    }
    claims = {
        "claim:a": type("C", (), {"fact_ids": ("fact:a",), "relation_evidence_ids": ("rel:a-b",)})(),
        "claim:b": type("C", (), {"fact_ids": ("fact:b",), "relation_evidence_ids": ("rel:b-a",)})(),
    }
    frame = build_semantic_argument_frame(
        argument_unit_id="unit:cycle", claim_ids=("claim:a", "claim:b"),
        equation_ids=(), configuration_ids=(), claim_by_id=claims,
        fact_by_id=facts,
        relation_by_id={
            "rel:a-b": _Relation("rel:a-b", "stage_a", "stage_b"),
            "rel:b-a": _Relation("rel:b-a", "stage_b", "stage_a"),
        },
        obligation_ids=(), authority_lanes=("executable_hard",),
    )
    assert frame.edges == ()
    assert set(frame.unresolved_relation_ids) == {"rel:a-b", "rel:b-a"}


def test_distinct_obligation_units_get_distinct_method_points() -> None:
    """R5-E4: units with different semantic frames/obligation roles get
    distinct reader-facing questions and method points; the planning strings
    contain no internal IDs and no count templates, and differ only for a
    real semantic/obligation difference."""
    from code2paper.agentic.method_architect import _unit_planning, build_semantic_argument_frame

    class _Fact:
        def __init__(self, fact_id, subject, predicate, obj, conditions=()):
            self.fact_id = fact_id
            self.subject = subject
            self.predicate = predicate
            self.object = obj
            self.conditions = list(conditions)
            self.validation_status = "supported"
            self.relation_evidence_ids = []

    facts = {
        "f1": _Fact("f1", "load_stage", "loads_weights", "features"),
        "f2": _Fact("f2", "output_stage", "returns", "scores"),
        "f3": _Fact("f3", "transform_stage", "concatenates", ["features", "scores"]),
        "f4": _Fact("f4", "branch_stage", "branches_on", "threshold"),
    }
    frame_a = build_semantic_argument_frame(
        argument_unit_id="unit-a",
        claim_ids=("c1", "c2"),
        equation_ids=(),
        configuration_ids=(),
        claim_by_id={"c1": type("C", (), {"fact_ids": ("f1",), "relation_evidence_ids": ()})(),
                      "c2": type("C", (), {"fact_ids": ("f2",), "relation_evidence_ids": ()})()},
        fact_by_id=facts,
        relation_by_id={},
        obligation_ids=(),
        authority_lanes=("executable_hard",),
    )
    frame_b = build_semantic_argument_frame(
        argument_unit_id="unit-b",
        claim_ids=("c3",),
        equation_ids=(),
        configuration_ids=(),
        claim_by_id={"c3": type("C", (), {"fact_ids": ("f3",), "relation_evidence_ids": ()})()},
        fact_by_id=facts,
        relation_by_id={},
        obligation_ids=(),
        authority_lanes=("executable_hard",),
    )
    plan_a = _unit_planning("unit-a", frame_a)
    plan_b = _unit_planning("unit-b", frame_b)
    assert plan_a["reader_question"] != plan_b["reader_question"]
    assert plan_a["method_point"] != plan_b["method_point"]
    # Reader-facing planning never contains internal IDs or counts.
    for value in (*plan_a.values(), *plan_b.values()):
        assert "unit-a" not in value and "unit-b" not in value
        assert "obl" not in value and "obligation" not in value.lower()
        assert " 1 " not in value and " 8 " not in value


def test_claimless_gap_rows_survive_replanning_as_unresolved(tmp_path: Path) -> None:
    """R5-E3: claim-less critical/high completeness rows survive replanning as
    fully typed obligation assignments with their exact status, authority
    lane, source ids, and next action intact — never a flattened id:status."""
    paths = _artifacts(tmp_path)
    plan = MethodSectionPlanV2.model_validate_json(Path(paths["method_section_plan_v2"]).read_text())
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    )
    gap = MethodCompletenessItemV1(
        obligation_id="O-STAGE-04-gap",
        status="explicit_code_gap",
        claim_ids=(),
        importance="critical",
        authority_lane="executable_hard",
        source_artifact_ids=("span:gap.py:1:1",),
        next_action="ask the author to accept the scoped code gap",
        reason="Search was exhausted and the requested behavior is not implemented.",
    )
    completeness = completeness.model_copy(update={
        "items": (*completeness.items, gap),
    })
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )
    claims = AtomicClaimSetV3.model_validate_json(Path(paths["atomic_claims_v3"]).read_text())
    equations = EquationClaimSetV1.model_validate_json(Path(paths["equation_claims_v1"]).read_text())
    configurations = ConfigurationClaimSetV1.model_validate_json(
        Path(paths["configuration_claims_v1"]).read_text()
    )
    from code2paper.agentic.method_architect import replan_moves_with_trace

    _new_plan, trace = replan_moves_with_trace(
        base_plan=plan,
        claims=claims,
        equations=equations,
        configurations=configurations,
        completeness=completeness,
    )
    by_id = _new_plan.assignments_by_obligation()
    assert "O-STAGE-04-gap" in by_id
    assignment = by_id["O-STAGE-04-gap"]
    assert assignment.status == "explicit_code_gap"
    assert assignment.importance == "critical"
    assert assignment.authority_lane == "executable_hard"
    assert assignment.placement_state == "external_pending"
    assert assignment.required_move == "limitations_or_mismatch"
    assert assignment.source_artifact_ids == ("span:gap.py:1:1",)
    assert "accept" in assignment.next_action
    assert assignment.unresolved_reason
    # Every critical/high row appears exactly once among the typed assignments.
    assert sum(
        1 for item in _new_plan.obligation_assignments
        if item.obligation_id == "O-STAGE-04-gap"
    ) == 1
    # The routed external-pending row is no longer an incomplete plan item.
    assert "O-STAGE-04-gap" not in " ".join(str(item) for item in _new_plan.incomplete_sections)


def test_unrelated_claim_does_not_anchor_limitations_move(tmp_path: Path) -> None:
    """R5-E5: an unrelated implementation claim in the same unit cannot anchor
    limitations_or_mismatch; the move proof reports empty factual anchors and
    the exact unresolved obligation ids."""
    paths = _artifacts(tmp_path)
    plan = MethodSectionPlanV2.model_validate_json(Path(paths["method_section_plan_v2"]).read_text())
    claims = AtomicClaimSetV3.model_validate_json(Path(paths["atomic_claims_v3"]).read_text())
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    ).model_copy(update={
        "items": (
            *MethodCompletenessMatrixV1.model_validate_json(
                Path(paths["method_completeness_matrix_v1"]).read_text()
            ).items,
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-04-gap",
                status="explicit_code_gap",
                claim_ids=(claims.claims[0].claim_id,),
                importance="critical",
            ),
        ),
    })
    equations = EquationClaimSetV1.model_validate_json(Path(paths["equation_claims_v1"]).read_text())
    configurations = ConfigurationClaimSetV1.model_validate_json(
        Path(paths["configuration_claims_v1"]).read_text()
    )
    from code2paper.agentic.method_architect import replan_moves_with_trace

    new_plan, _trace = replan_moves_with_trace(
        base_plan=plan,
        claims=claims,
        equations=equations,
        configurations=configurations,
        completeness=completeness,
    )
    proof = new_plan.proofs_by_key().get(("MA-S1", "limitations_or_mismatch"))
    assert proof is not None and proof.required
    assert proof.anchor_ids == ()
    assert "O-STAGE-04-gap" in proof.unresolved_obligation_ids
    assert proof.required_authority_lane == "author_attested"
    assert proof.state == "external_pending"


def test_explicit_code_gap_routes_to_author_attested_and_claim_gap_emits_local_request(
    tmp_path: Path,
) -> None:
    """R5-E5: an explicit_code_gap row routes to author_attested (external
    pending), while a claim-bearing unverified gap emits a locally owned
    executable_hard request whose candidates are exact semantic terms."""
    paths = _artifacts(tmp_path)
    plan_path = Path(paths["method_section_plan_v2"])
    plan = MethodSectionPlanV2.model_validate_json(plan_path.read_text())
    claims = AtomicClaimSetV3.model_validate_json(Path(paths["atomic_claims_v3"]).read_text())
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    ).model_copy(update={
        "items": (
            *MethodCompletenessMatrixV1.model_validate_json(
                Path(paths["method_completeness_matrix_v1"]).read_text()
            ).items,
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-04-unit",
                status="supported_by_repository",
                claim_ids=(claims.claims[0].claim_id,),
            ),
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-04-gap",
                status="explicit_code_gap",
                claim_ids=(),
                importance="critical",
            ),
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-04-local",
                status="unverified_by_repository",
                claim_ids=(claims.claims[0].claim_id,),
                importance="critical",
                next_action="run scoped repository research",
            ),
        ),
    })
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        move_authority = request.input_payload["grounding_contract"]["move_authority"]
        limitations = move_authority.get("limitations_or_mismatch", {})
        assert limitations.get("required_authority_lane") == "executable_hard"
        assert limitations.get("candidate_symbols_or_terms")
        prototypes = request.input_payload["grounding_contract"]["callback_request_prototypes"]
        assert prototypes
        assert prototypes[0]["missing_rhetorical_move"] == "limitations_or_mismatch"
        assert prototypes[0]["required_authority_lane"] == "executable_hard"
        assert prototypes[0]["candidate_symbols_or_terms"] == limitations.get(
            "candidate_symbols_or_terms"
        )
        response_protocol = request.input_payload["response_protocol"]
        assert (
            response_protocol["callback_request_prototypes"][0][
                "candidate_symbols_or_terms"
            ]
            == limitations.get("candidate_symbols_or_terms")
        )
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": [
                    move for move in binding["completed_rhetorical_moves"]
                    if move != "limitations_or_mismatch"
                ],
                "new_research_requests": [{
                    "request_id": "request:MA-S1:limitations_or_mismatch",
                    "section_id": "MA-S1",
                    "argument_unit_id": binding["used_argument_unit_ids"][0],
                    "missing_rhetorical_move": "limitations_or_mismatch",
                    "exact_question": "Which validated artifact resolves the unverified gap?",
                    "required_authority_lane": "executable_hard",
                    "candidate_symbols_or_terms": [
                        str(item) for item in limitations.get("candidate_symbols_or_terms", ())
                    ],
                    "status": "open",
                }],
            }),
            response_hash="sha256:writer-gap",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
        rebuild_architect_plan=True,
    )

    bundle = json.loads(Path(
        outputs["writing_research_callback_artifacts_v1"]
    ).read_text())
    limitations_requests = [
        item for item in bundle.get("requests", [])
        if item.get("missing_rhetorical_move") == "limitations_or_mismatch"
    ]
    assert limitations_requests, bundle.get("requests", [])
    assert limitations_requests[0]["required_authority_lane"] == "executable_hard"
    assert limitations_requests[0]["candidate_symbols_or_terms"]
    # An open locally owned request never populates the admitted resume set.
    assert bundle.get("resume_section_ids") == []
    assert result.status in {"incomplete", "blocked"}


def test_writer_rejects_illegal_callback_requests_and_expository_requests(
    tmp_path: Path,
) -> None:
    """R5-E6: a valid unresolved callback survives, while expository requests,
    unknown lanes, extra model requests, and mismatched section/unit fail
    closed."""
    paths = _artifacts(tmp_path)
    completeness = _with_unverified_gap(paths)
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [
                    {
                        # Valid: matches the open locally owned limitations proof.
                        "request_id": "request:MA-S1:limitations_or_mismatch",
                        "section_id": "MA-S1",
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "missing_rhetorical_move": "limitations_or_mismatch",
                        "exact_question": "Which validated artifact resolves the gap?",
                        "required_authority_lane": "executable_hard",
                        "candidate_symbols_or_terms": ["sym:encoder"],
                        "status": "open",
                    },
                    {
                        # Illegal: a research request for a claim-free bridge move.
                        "request_id": "request:MA-S1:transition_to_next_section",
                        "section_id": "MA-S1",
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "missing_rhetorical_move": "transition_to_next_section",
                        "exact_question": "Transition evidence?",
                        "required_authority_lane": "expository_bridge",
                        "status": "open",
                    },
                    {
                        # Illegal: unknown lane.
                        "request_id": "request:MA-S1:limitations_or_mismatch:extra",
                        "section_id": "MA-S1",
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "missing_rhetorical_move": "limitations_or_mismatch",
                        "exact_question": "Duplicate with wrong lane?",
                        "required_authority_lane": "external_literature",
                        "status": "open",
                    },
                    {
                        # Illegal: wrong section for the move.
                        "request_id": "request:MA-S2:limitations_or_mismatch",
                        "section_id": "MA-S2",
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "missing_rhetorical_move": "limitations_or_mismatch",
                        "exact_question": "Wrong section?",
                        "required_authority_lane": "executable_hard",
                        "status": "open",
                    },
                ],
            }),
            response_hash="sha256:writer-invalid-callbacks",
            finish_reason="stop",
        )

    result, _outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
        rebuild_architect_plan=True,
    )
    assert result.status in {"incomplete", "blocked"}
    # The legal request survives; the illegal ones fail the contract.
    invalid = [
        item for item in result.binding_failures
        if "invalid_writing_research_callback" in item
    ]
    assert invalid
    assert "transition_to_next_section" in invalid[0]
    assert "external_literature" in invalid[0]
    assert "MA-S2" in invalid[0]


def test_fulfillment_rebuilds_move_proof_and_external_rows_do_not_block(
    tmp_path: Path,
) -> None:
    """R5-E7: fulfillment rebuilds the move authority proof; open or external
    rows do not call Writer; zero calls produce zero resumed ids; unaffected
    checkpoint digests remain byte-identical."""
    from code2paper.agentic.method_architect import replan_moves_with_trace

    paths = _two_section_gap_artifacts(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(Path(paths["atomic_claims_v3"]).read_text())
    equations = EquationClaimSetV1.model_validate_json(Path(paths["equation_claims_v1"]).read_text())
    configurations = ConfigurationClaimSetV1.model_validate_json(
        Path(paths["configuration_claims_v1"]).read_text()
    )
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    )
    plan = MethodSectionPlanV2.model_validate_json(Path(paths["method_section_plan_v2"]).read_text())
    _new_plan, _trace = replan_moves_with_trace(
        base_plan=plan,
        claims=claims,
        equations=equations,
        configurations=configurations,
        completeness=completeness,
    )
    # Fulfillment state transitions live on the callback side; the plan proof
    # stays ``open`` until the Writer consumes the artifact, then the
    # regenerated section clears its replay marker.
    from code2paper.agentic.method_argument_models import MoveAuthorityProofV1
    open_proof = _new_plan.proofs_by_key()[("MA-S1", "limitations_or_mismatch")]
    assert open_proof.state == "open"
    assert open_proof.required_authority_lane == "executable_hard"
    # A fulfilled proof without matching validated artifacts fails closed.
    with pytest.raises(ValueError):
        MoveAuthorityProofV1.model_validate(open_proof.model_dump(mode="json") | {
            "state": "fulfilled",
        })
    fulfilled_proof = MoveAuthorityProofV1.model_validate(open_proof.model_dump(mode="json") | {
        "state": "fulfilled",
        "request_ids": ("request:MA-S1:limitations_or_mismatch",),
        "fulfillment_artifact_ids": ("artifact:fact-read",),
        "fulfillment_artifact_digest": "sha256:fact-read",
    })
    assert fulfilled_proof.content_digest != open_proof.content_digest

    def first_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        section_id = request.input_payload["section_id"]
        if section_id == "MA-S1":
            return LLMResponse(
                text=json.dumps({
                    "section_id": section_id,
                    "section_markdown": "## Feature preparation\n\nThe encoder reads the configured input.",
                    "used_argument_unit_ids": binding["used_argument_unit_ids"],
                    "used_claim_ids": binding["used_claim_ids"],
                    "used_equation_ids": binding["used_equation_ids"],
                    "used_configuration_ids": binding["used_configuration_ids"],
                    "completed_rhetorical_moves": _completed_moves(binding),
                    "new_research_requests": [{
                        "request_id": "request:MA-S1:limitations_or_mismatch",
                        "section_id": section_id,
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "missing_rhetorical_move": "limitations_or_mismatch",
                        "exact_question": "Which validated artifact resolves the gap?",
                        "required_authority_lane": "executable_hard",
                        "candidate_symbols_or_terms": ["sym:encoder"],
                        "status": "open",
                    }],
                }),
                response_hash="sha256:writer:MA-S1",
                finish_reason="stop",
            )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Output generation\n\nIts representation is returned to the downstream stage.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer:MA-S2",
            finish_reason="stop",
        )

    first, first_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=first_caller,
        rebuild_architect_plan=True,
    )
    assert first.status == "incomplete"
    assert set(first.incomplete_section_ids) == {"MA-S1"}
    assert set(first.accepted_section_ids) == {"MA-S1", "MA-S2"}
    assert first.resumed_section_ids == ()
    emitted_trace = next(
        item for item in first.response_recovery_traces
        if item.get("provenance") == "model_emitted"
    )
    assert emitted_trace["raw_response_hash"] == "sha256:writer:MA-S1"
    assert emitted_trace["parsed_request_digests"]
    assert all(
        digest.startswith("sha256:")
        for digest in emitted_trace["parsed_request_digests"]
    )
    bundle = json.loads(Path(
        first_outputs["writing_research_callback_artifacts_v1"]
    ).read_text())
    assert bundle["resume_section_ids"] == []
    checkpoint = json.loads(Path(
        first_outputs["publication_section_checkpoint_v1"]
    ).read_text())
    checkpoint_root = Path(first_outputs["publication_section_checkpoint_v1"]).parent
    ma2_before = json.loads((checkpoint_root / checkpoint["sections"]["MA-S2"]["output_ref"]).read_text())
    paths.update(first_outputs)

    # Zero model calls on resume admission with an unfulfilled local request:
    # the gate blocks before Writer and no section is reported regenerated.
    zero_calls, _ = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=lambda *_args: (_ for _ in ()).throw(AssertionError("must not call")),
        resume_section_ids=("MA-S1",),
    )
    assert zero_calls.status == "blocked"
    assert zero_calls.blocked_reason.startswith("writing_research_callback_artifacts_missing:")
    assert zero_calls.resumed_section_ids == ()

    # Fulfill the local request: only MA-S1 is regenerated; MA-S2's checkpoint
    # and output digests remain byte-identical.
    fulfilled = fulfill_writing_research_callbacks(
        first_outputs["writing_research_callback_artifacts_v1"],
        {
            "request:MA-S1:limitations_or_mismatch": ({
                "artifact_id": "artifact:fact-read",
                "request_id": "request:MA-S1:limitations_or_mismatch",
                "section_id": "MA-S1",
                "argument_unit_id": "MA-S1:unit",
                "authority_lane": "executable_hard",
                "artifact_ref": "fact-read",
                "artifact_digest": "sha256:fact-read",
                "validated": True,
            },),
        },
    )
    assert fulfilled.resume_section_ids == ("MA-S1",)

    resumed_calls: list[str] = []

    def resumed_caller(_config, request):
        section_id = request.input_payload["section_id"]
        resumed_calls.append(section_id)
        binding = request.input_payload["binding_contract"]
        authority = request.input_payload["grounding_contract"]["move_authority"]
        fulfilled_move = authority["limitations_or_mismatch"]
        assert fulfilled_move["state"] == "fulfilled"
        assert fulfilled_move["request_ids"] == [
            "request:MA-S1:limitations_or_mismatch"
        ]
        assert fulfilled_move["fulfillment_artifact_ids"] == ["artifact:fact-read"]
        assert fulfilled_move["fulfillment_artifact_digest"].startswith("sha256:")
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Feature preparation\n\nThe encoder reads the configured input and leaves the remaining gap explicit.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer-resumed",
            finish_reason="stop",
        )

    resumed, resumed_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=resumed_caller,
        resume_section_ids=("MA-S1",),
    )
    assert resumed_calls == ["MA-S1"]
    assert resumed.resumed_section_ids == ("MA-S1",)
    resumed_checkpoint = json.loads(Path(
        resumed_outputs["publication_section_checkpoint_v1"]
    ).read_text())
    ma2_after = json.loads((checkpoint_root / resumed_checkpoint["sections"]["MA-S2"]["output_ref"]).read_text())
    assert ma2_after["output_digest"] == ma2_before["output_digest"]
    assert ma2_after["output"] == ma2_before["output"]
    resumed_bundle = json.loads(Path(
        resumed_outputs["writing_research_callback_artifacts_v1"]
    ).read_text())
    # The regenerated section cleared its replay marker.
    assert resumed_bundle["resume_section_ids"] == []


def test_model_request_with_missing_or_foreign_candidates_is_not_routed(
    tmp_path: Path,
) -> None:
    """R6-A: the harness cannot invent or silently narrow callback scope."""
    paths = _artifacts(tmp_path)
    completeness = _with_unverified_gap(paths)
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [{
                    "request_id": "request:MA-S1:limitations_or_mismatch:model",
                    "section_id": "MA-S1",
                    "argument_unit_id": binding["used_argument_unit_ids"][0],
                    "missing_rhetorical_move": "limitations_or_mismatch",
                    "exact_question": "Which validated artifact resolves the gap?",
                    "required_authority_lane": "executable_hard",
                    "candidate_symbols_or_terms": ["unrelated-term", "sym:encoder"],
                    "status": "open",
                }],
            }),
            response_hash="sha256:writer-model-candidates",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
        rebuild_architect_plan=True,
    )
    assert result.status in {"incomplete", "blocked"}
    assert any(
        "invalid_writing_research_callback" in item
        for item in result.binding_failures
    )
    callback_path = outputs.get("writing_research_callback_artifacts_v1")
    if callback_path:
        bundle = json.loads(Path(callback_path).read_text())
        assert bundle["requests"] == []


def test_condition_qualifier_accepts_authorized_code_to_prose_paraphrase() -> None:
    qualifier = "knn_method in ['ivf', 'brute_force']"
    assert _phrase_present(
        "The branch runs when knn_method is either 'ivf' or 'brute_force'.",
        qualifier,
    )
    assert not _phrase_present(
        "The branch runs when knn_method is 'ivf'.",
        qualifier,
    )


def test_editor_patch_that_drops_supported_claim_is_rejected() -> None:
    claim = AtomicClaimV3(
        claim_id="claim-supported",
        canonical_text="The encoder reads the configured input.",
        fact_ids=["fact-read"],
        direct_evidence_ids=["span:encoder.py:1:2"],
        allowed_wording_boundary="encoder reads configured input",
        canonical_identity="sha256:claim-supported",
    )
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown="The encoder reads the configured input.",
        used_claim_ids=[claim.claim_id],
    )
    patch = SectionTextPatchV1(
        patch_id="editor:drop",
        section_id="MA-S1",
        before_digest="sha256:before",
        replacement_text="A separate component exists.",
    )

    failures = _editor_claim_regressions(
        patches=[patch],
        original_sections={"MA-S1": output.section_markdown},
        edited_sections={"MA-S1": patch.replacement_text},
        outputs={"MA-S1": output},
        claims_by_id={claim.claim_id: claim},
    )

    assert failures == ["MA-S1:supported_claim_lost:claim-supported"]


def test_equation_id_without_rendered_expression_fails_publication_gate() -> None:
    equation = EquationClaimV1(
        equation_id="eq-main",
        expression="z = x + y",
        fact_ids=["fact-formula"],
        symbol_bindings=[],
        canonical_identity="sha256:eq-main",
    )
    equations = EquationClaimSetV1(
        repo_snapshot_id="repo:eq",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts",
        equations=[equation],
        content_digest="sha256:equations",
    )
    unit = MethodArgumentUnitV1(
        argument_unit_id="unit-eq",
        section_role="equation",
        research_question="How is the transformation computed?",
        claim_ids=("claim-eq",),
        equation_ids=(equation.equation_id,),
        authority_lanes=("executable_hard",),
    )
    plan = MethodSectionPlanV2(
        plan_id="plan-eq",
        sections=(SectionArgumentGraphV1(
            section_id="section-eq",
            heading="Transformation",
            reader_question="How is the transformation computed?",
            argument_unit_ids=(unit.argument_unit_id,),
            moves=(SectionArgumentMoveV1(
                move="equation_or_derivation",
                argument_unit_ids=(unit.argument_unit_id,),
                allowed_authority_lanes=("executable_hard",),
                required=True,
            ),),
        ),),
        argument_units=(unit,),
    )
    completeness = MethodCompletenessMatrixV1(items=(MethodCompletenessItemV1(
        obligation_id="obl-eq",
        status="supported_by_repository",
        claim_ids=("claim-eq",),
        equation_ids=(equation.equation_id,),
    ),))

    def report_for(text: str):
        output = PublicationMethodSectionOutputV1(
            section_id="section-eq",
            section_markdown=text,
            used_argument_unit_ids=[unit.argument_unit_id],
            used_claim_ids=["claim-eq"],
            used_equation_ids=[equation.equation_id],
            completed_rhetorical_moves=["equation_or_derivation"],
        )
        ledger = ledger_from_section_outputs(
            text,
            (("section-eq", text, "sha256:writer-equation"),),
        )
        return evaluate_publication_method_quality(
            final_text=text,
            plan=plan,
            completeness=completeness,
            section_outputs=(output,),
            ledger=ledger,
            equations=equations,
        )

    missing = report_for("The transformation combines the two inputs.")
    assert missing.safety.hard_gate_passed is True
    assert missing.utility.equation_coverage == 0.0
    assert missing.status == "incomplete"

    rendered = report_for("The transformation is computed as z = x + y.")
    assert rendered.utility.equation_coverage == 1.0
    assert rendered.status == "publication_ready"


def _quality_plan(
    *,
    claims: tuple[str, ...],
    equations: tuple[str, ...] = (),
    configs: tuple[str, ...] = (),
    moves: tuple[str, ...] = _COMPLETED_CORE_MOVES,
    section_id: str = "section-a",
    heading: str = "Encoder",
) -> MethodSectionPlanV2:
    unit = MethodArgumentUnitV1(
        argument_unit_id="unit-a",
        section_role="mechanism",
        research_question="How does the encoder work?",
        claim_ids=claims,
        equation_ids=equations,
        configuration_ids=configs,
        authority_lanes=("executable_hard",),
    )
    return MethodSectionPlanV2(
        plan_id="plan-a",
        sections=(SectionArgumentGraphV1(
            section_id=section_id,
            heading=heading,
            reader_question="How does the encoder work?",
            argument_unit_ids=(unit.argument_unit_id,),
            moves=tuple(
                SectionArgumentMoveV1(
                    move=move,
                    argument_unit_ids=(unit.argument_unit_id,),
                    allowed_authority_lanes=("executable_hard",),
                    required=True,
                )
                for move in moves
            ),
        ),),
        argument_units=(unit,),
    )


def _quality_claim(claim_id: str = "claim-a") -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id=claim_id,
        canonical_text="The encoder reads the configured input.",
        fact_ids=["fact-a"],
        covers_obligation_ids=["obl-a"],
        direct_evidence_ids=["span:encoder.py:1:2"],
        allowed_wording_boundary="reads configured input",
        canonical_identity="sha256:claim-a",
        status="supported",
    )


def _quality_completeness(*, claim_ids: tuple[str, ...]) -> MethodCompletenessMatrixV1:
    return MethodCompletenessMatrixV1(items=(MethodCompletenessItemV1(
        obligation_id="obl-a",
        status="supported_by_repository",
        claim_ids=claim_ids,
    ),))


def _quality_report(
    *,
    plan: MethodSectionPlanV2,
    completeness: MethodCompletenessMatrixV1,
    sections: list[PublicationMethodSectionOutputV1],
    claims: AtomicClaimSetV3,
    equations: EquationClaimSetV1 | None = None,
    configurations: ConfigurationClaimSetV1 | None = None,
    sentence_validated_claim_ids: tuple[str, ...] | None = None,
) -> PublicationQualityReportV1:
    final_text = "\n\n".join(item.section_markdown for item in sections)
    ledger = ledger_from_section_outputs(
        final_text,
        tuple((item.section_id, item.section_markdown, "sha256:writer") for item in sections),
    )
    return evaluate_publication_method_quality(
        final_text=final_text,
        plan=plan,
        completeness=completeness,
        section_outputs=tuple(sections),
        ledger=ledger,
        claims=claims,
        equations=equations,
        configurations=configurations,
        sentence_validated_claim_ids=sentence_validated_claim_ids,
    )


def test_utility_gate_rejects_symbol_inventory_declaring_all_moves_complete() -> None:
    claim = _quality_claim()
    plan = _quality_plan(claims=(claim.claim_id,))
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe encoder calls read_input, transform, and write_output.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )

    report = _quality_report(plan=plan, completeness=completeness, sections=[output], claims=claims)

    assert report.safety.hard_gate_passed is True
    assert report.utility.utility_gate_passed is False


def test_proposition_product_gate_rejects_silent_drop_and_reasonless_defer() -> None:
    claim = _quality_claim()
    base_plan = _quality_plan(claims=(claim.claim_id,))
    unit = base_plan.argument_units[0].model_copy(update={
        "proposition_ids": ("MP-1",),
        "positive_proposition_ids": ("MP-1",),
        "proposition_order": ("MP-1",),
    })
    plan = base_plan.model_copy(update={"argument_units": (unit,)})
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets", code_fact_digest="sha256:facts",
        claims=[claim], content_digest="sha256:claims",
    )
    propositions = MethodPropositionSetV1(
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        propositions=(MethodPropositionV1(
            proposition_id="MP-1", origin="repository_evidence",
            evidence_lane="repository_verified", may_enter_verified=True,
            reader_subject="the encoder", transformation="reads the configured input",
        ),),
        binding_sidecar_digest="sha256:" + "a" * 64,
    )
    text = "## Encoder\n\nThe encoder reads the configured input."

    def report(output, alignment):
        ledger = ledger_from_section_outputs(
            text, (("section-a", text, "sha256:writer"),)
        )
        return evaluate_publication_method_quality(
            final_text=text, plan=plan, completeness=completeness,
            section_outputs=(output,), ledger=ledger, claims=claims,
            propositions=propositions,
            proposition_alignment_report={"sections": alignment},
        )

    silent = report(PublicationMethodSectionOutputV1(
        section_id="section-a", section_markdown=text,
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    ), [])
    assert silent.utility.unresolved_required_propositions == 1
    assert any(
        issue.code == "required_proposition_silently_dropped"
        for issue in silent.issues
    )

    reasonless = report(PublicationMethodSectionOutputV1(
        section_id="section-a", section_markdown=text,
        used_claim_ids=[claim.claim_id], deferred_proposition_ids=["MP-1"],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    ), [])
    assert any(
        issue.code == "proposition_deferred_without_reason"
        for issue in reasonless.issues
    )


def test_utility_gate_rejects_paraphrased_same_information_across_sections() -> None:
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    plan = _quality_plan(claims=(claim.claim_id,), section_id="section-a")
    second = SectionArgumentGraphV1.model_validate(plan.sections[0].model_dump(mode="json")).model_copy(
        update={"section_id": "section-b", "heading": "Output interface"}
    )
    plan = plan.model_copy(update={"sections": (*plan.sections, second)})
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    first = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )
    second_output = PublicationMethodSectionOutputV1(
        section_id="section-b",
        section_markdown="## Output interface\n\nThe configured input is read by the encoder.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )

    report = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[first, second_output],
        claims=claims,
    )

    assert report.safety.hard_gate_passed is True
    assert report.utility.duplicate_information_rate > 0
    assert report.utility.utility_gate_passed is False
    assert any(issue.code == "duplicate_information" for issue in report.issues)


def test_utility_gate_rejects_complete_move_list_without_required_role_content() -> None:
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    plan = _quality_plan(
        claims=(claim.claim_id,),
        moves=("mechanism_overview", "algorithm_or_data_flow", "configuration_and_branches"),
    )
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=[
            "mechanism_overview",
            "algorithm_or_data_flow",
            "configuration_and_branches",
        ],
    )

    report = _quality_report(plan=plan, completeness=completeness, sections=[output], claims=claims)

    assert report.safety.hard_gate_passed is True
    assert report.utility.utility_gate_passed is False
    assert report.utility.content_role_status.get("branch") == "missing"
    assert any(issue.code == "required_move_content_missing" for issue in report.issues)


def test_utility_gate_rejects_configuration_key_without_value_rendering() -> None:
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    configuration = ConfigurationClaimV1(
        configuration_id="config:1",
        key="knn_method",
        value="ivf",
        state="default",
        source_fact_ids=["fact:config"],
        canonical_identity="sha256:config:1",
    )
    configurations = ConfigurationClaimSetV1(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        claims=[configuration],
        content_digest="sha256:configs",
    )
    plan = _quality_plan(claims=(claim.claim_id,), configs=(configuration.configuration_id,))
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe branch uses knn_method.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        used_configuration_ids=[configuration.configuration_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )

    report = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[output],
        claims=claims,
        configurations=configurations,
    )

    assert report.safety.hard_gate_passed is True
    assert report.utility.configuration_coverage == 0.0
    assert report.utility.utility_gate_passed is False


def test_utility_gate_rejects_headings_only_and_fragment_sections() -> None:
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    plan = _quality_plan(claims=(claim.claim_id,), section_id="section-a")
    second = SectionArgumentGraphV1.model_validate(plan.sections[0].model_dump(mode="json")).model_copy(
        update={"section_id": "section-b", "heading": "Output interface"}
    )
    plan = plan.model_copy(update={"sections": (*plan.sections, second)})
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    first = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )
    fragment = PublicationMethodSectionOutputV1(
        section_id="section-b",
        section_markdown="## Output interface\n\nIt.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )

    report = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[first, fragment],
        claims=claims,
    )

    assert report.safety.hard_gate_passed is True
    assert report.utility.editable_section_rate < 1.0
    assert report.utility.utility_gate_passed is False
    assert any(issue.code == "section_not_editable" for issue in report.issues)


def test_utility_gate_rejects_internal_argument_ids_in_final_text() -> None:
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    plan = _quality_plan(claims=(claim.claim_id,))
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nUnit unit-a covers the encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )

    report = _quality_report(plan=plan, completeness=completeness, sections=[output], claims=claims)

    assert report.safety.hard_gate_passed is True
    assert report.utility.terminology_notation_consistent is False
    assert report.utility.utility_gate_passed is False
    assert any(issue.code == "internal_bookkeeping_exposed" for issue in report.issues)
def test_editor_proposition_guard_distinguishes_positive_and_caveated_content() -> None:
    context = {
        "writer_view": {
            "positive_propositions": [{
                "proposition_id": "MP-POS",
                "reader_subject": "the descriptor",
                "transformation": "combines color and scale",
            }],
            "caveated_propositions": [{
                "proposition_id": "MP-CAND",
                "intended_subject": "the deployment path",
                "intended_transformation": "avoids rendering",
                "required_caveat_kind": "author_intent",
            }],
        }
    }
    rendered = _editor_rendered_proposition_ids(
        "The descriptor combines color and scale. The intended design's "
        "deployment path avoids rendering.",
        context,
    )
    assert rendered == {"MP-POS", "MP-CAND"}
    assert _editor_rendered_proposition_ids(
        "The deployment path avoids rendering.", context
    ) == set()


# ---------------------------------------------------------------------------
# Plan 14.4: reader-facing internal-id leakage and section structure
# ---------------------------------------------------------------------------


def _leakage_output(
    section_id: str = "section-a",
    markdown: str = "",
) -> PublicationMethodSectionOutputV1:
    return PublicationMethodSectionOutputV1(
        section_id=section_id,
        section_markdown=markdown,
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )


def test_reader_facing_internal_id_is_routed_to_rewrite(tmp_path: Path) -> None:
    """A CK-* or fact id in prose creates an exact Rewrite issue; it is not
    repaired by regex deletion in the harness."""
    from code2paper.agentic.publication_method_writer import (
        _reader_facing_leakage_issues_by_section,
    )

    issues = _reader_facing_leakage_issues_by_section({
        "section-a": _leakage_output(
            markdown=(
                "## Encoder\n\nThe linear rag index (CK-9c5360a570a6c8c7) "
                "branches on the flag."
            )
        ),
    })
    assert issues["section-a"]
    issue = issues["section-a"][0]
    assert issue.failure_type == "reader_facing_internal_id"
    assert issue.allowed_repair_scope == "wording_only"
    assert issue.offending_fragment == "CK-9c5360a570a6c8c7"


def test_fact_and_span_ids_are_detected_as_leakage() -> None:
    from code2paper.agentic.publication_method_writer import (
        _reader_facing_leakage_issues_by_section,
    )

    issues = _reader_facing_leakage_issues_by_section({
        "section-a": _leakage_output(
            markdown=(
                "## Encoder\n\nfact-O-MAIN-01-node:abc123 supports the "
                "retrieval via span:src/a.py:1:2."
            )
        ),
    })
    failure_types = {
        issue.failure_type for issue in issues["section-a"]
    }
    assert failure_types == {"reader_facing_internal_id"}


def test_fused_heading_suffix_routes_to_rewrite_not_silent_strip() -> None:
    """``...initialization)Local`` must be routed to Rewrite: silently
    removing the suffix could change content."""
    from code2paper.agentic.publication_method_writer import (
        _section_structure_issues_by_section,
    )
    from code2paper.llm.section_writer import WriterSectionInput

    writer_input = WriterSectionInput(
        section_id="section-a",
        heading="First stage: activation (initialization",
        prompt_payload={},
    )
    issues = _section_structure_issues_by_section(
        {
            "section-a": _leakage_output(
                markdown=(
                    "## First stage: activation (initialization)Local\n\n"
                    "The stage activates."
                )
            ),
        },
        writer_inputs={"section-a": writer_input},
    )
    fused = [
        issue for issue in issues["section-a"]
        if issue.sentence_id.endswith("fused-heading-suffix")
    ]
    assert fused, [issue.sentence_id for issue in issues.get("section-a", ())]
    assert "Local" in fused[0].missing_fact_or_relation


def test_exact_heading_with_clean_body_has_no_structure_issue() -> None:
    from code2paper.agentic.publication_method_writer import (
        _section_structure_issues_by_section,
    )
    from code2paper.llm.section_writer import WriterSectionInput

    writer_input = WriterSectionInput(
        section_id="section-a",
        heading="Encoder",
        prompt_payload={},
    )
    issues = _section_structure_issues_by_section(
        {
            "section-a": _leakage_output(
                markdown="## Encoder\n\nThe encoder reads the configured input."
            ),
        },
        writer_inputs={"section-a": writer_input},
    )
    assert issues.get("section-a", []) == []


def test_empty_and_heading_only_sections_are_rejected() -> None:
    from code2paper.agentic.publication_method_writer import (
        _section_structure_issues_by_section,
    )
    from code2paper.llm.section_writer import WriterSectionInput

    writer_input = WriterSectionInput(
        section_id="section-a",
        heading="Encoder",
        prompt_payload={},
    )
    issues = _section_structure_issues_by_section(
        {
            "section-a": _leakage_output(markdown="## Encoder\n\n"),
            "section-b": _leakage_output(section_id="section-b", markdown=""),
            "section-c": _leakage_output(section_id="section-c", markdown="## Encoder"),
        },
        writer_inputs={
            "section-a": writer_input,
            "section-b": writer_input,
            "section-c": writer_input,
        },
    )
    assert any(
        issue.sentence_id.endswith("empty") for issue in issues.get("section-b", ())
    )
    assert any(
        issue.sentence_id.endswith("heading-only")
        for issue in issues.get("section-c", ())
    )
    assert issues.get("section-a", [])  # blank-line-only body is empty


def test_duplicate_h2_heading_is_rejected() -> None:
    from code2paper.agentic.publication_method_writer import (
        _section_structure_issues_by_section,
    )
    from code2paper.llm.section_writer import WriterSectionInput

    writer_input = WriterSectionInput(
        section_id="section-a",
        heading="Encoder",
        prompt_payload={},
    )
    issues = _section_structure_issues_by_section(
        {
            "section-a": _leakage_output(
                markdown=(
                    "## Encoder\n\nThe encoder reads.\n\n## Sub part\n\nThe "
                    "sub part computes."
                )
            ),
        },
        writer_inputs={"section-a": writer_input},
    )
    assert any(
        issue.sentence_id.endswith("duplicate-heading")
        for issue in issues.get("section-a", ())
    )


def test_unsupported_positive_with_missing_qualifier_is_repaired_by_rewrite(
    tmp_path: Path,
) -> None:
    """Plan 14.4: an unsupported positive with a missing branch qualifier
    becomes a precise Rewrite request carrying the exact qualifier; the
    accepted patch passes candidate reverse validation (zero unsupported)."""
    paths = _artifacts(tmp_path)
    # Rebuild claims with an exact required qualifier on the fixture claim.
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    claims = claims.model_copy(update={
        "claims": tuple(
            claim.model_copy(update={"required_qualifiers": ["case_study"]})
            if claim.claim_id == "claim-read" else claim
            for claim in claims.claims
        ),
    })
    Path(paths["atomic_claims_v3"]).write_text(
        claims.model_dump_json(indent=2), encoding="utf-8"
    )
    # Bind a real evidence packet so reverse validation can run (mirrors
    # test_publication_writer_invokes_owned_rewrite_after_failed_reverse_validation).
    span = EvidenceSpanV3(
        span_id="span:encoder.py:1:2",
        snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        path="encoder.py",
        symbol="encoder",
        line_start=1,
        line_end=2,
        exact_excerpt="The encoder reads the configured input in the case study.",
        excerpt_digest="sha256:excerpt",
        file_digest="sha256:file",
        role="anchor",
    )
    packets = EvidencePacketSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        packets=[EvidencePacketV3(
            packet_id="packet:encoder",
            scope="sym:encoder",
            anchor_span_ids=[span.span_id],
            spans=[span],
            source_digest="sha256:packet-source",
        )],
        content_digest="sha256:packets-with-span",
    )
    Path(paths["evidence_packets_v3"]).write_text(
        packets.model_dump_json(indent=2), encoding="utf-8"
    )
    claims = claims.model_copy(update={"evidence_packet_digest": packets.content_digest})
    Path(paths["atomic_claims_v3"]).write_text(
        claims.model_dump_json(indent=2), encoding="utf-8"
    )
    method_path = tmp_path / "method_evidence.json"
    method_path.write_text(
        MethodEvidence(
            project_id="fixture",
            method_name="Encoder",
            method_goal="Describe the encoder.",
            implementation_scope="fixture repository",
        ).model_dump_json(),
        encoding="utf-8",
    )
    paths["method_evidence"] = str(method_path)
    seen_issue_qualifiers: list[str] = []

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        # Writer drops the qualifier -> the reverse validator must flag
        # required_qualifier_missing for the sentence.
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": (
                    "## Encoder\n\nThe encoder reads the configured input."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-no-qualifier",
            finish_reason="stop",
        )

    def rewrite_caller(_config, request):
        issues = request.input_payload["issues"]
        qualifier_issues = [
            item for item in issues if item["failure_type"] == "missing_qualifier"
        ]
        for item in qualifier_issues:
            seen_issue_qualifiers.append(
                item.get("missing_fact_or_relation", "")
            )
        incumbent = request.input_payload["incumbent_text"]
        original = "The encoder reads the configured input."
        start = incumbent.index(original)
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "rewrite:qualifier-fix",
                    "section_id": request.input_payload["section_context"]["section_id"],
                    "start": start,
                    "end": start + len(original),
                    "original_text": original,
                    "replacement_text": (
                        "In the case study, the encoder reads the configured input."
                    ),
                    "issue_ids": [item["sentence_id"] for item in qualifier_issues],
                    "allowed_scope": "wording_only",
                }],
                "self_identified_risks": [],
                "incomplete": False,
            }),
            response_hash="sha256:rewrite-qualifier-fix",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=rewrite_caller,
    )
    assert seen_issue_qualifiers == []
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "encoder reads the configured input" in candidate
    assert result.status != "blocked"


def test_concept_lane_sentence_validated_claims_cover_supported_units() -> None:
    """R1 regression: in the concept-card lane there is no proposition
    sidecar, so the Writer declares no ``used_claim_ids``.  The reverse
    validator's ``status=supported`` verdicts must bind repository support:
    supported rows become ``covered`` with recall 1.0 instead of the old
    ``planned_but_not_rendered`` / recall 0.0.  Caveated-only verdicts
    (empty sentence-validated ids) must NOT authorize repository support."""
    claim = _quality_claim()
    plan = _quality_plan(claims=(claim.claim_id,))
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        # Concept-card lane: the Writer cannot declare repository claim IDs.
        used_claim_ids=[],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )

    # Positive: supported sentence verdicts carry the binding authority.
    report = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[output],
        claims=claims,
        sentence_validated_claim_ids=(claim.claim_id,),
    )
    assert report.utility.supported_unit_recall == 1.0
    assert report.utility.completeness_coverage == 1.0
    (row,) = report.coverage_matrix
    assert row["coverage_status"] == "covered"
    assert row["used_claim_ids"] == [claim.claim_id]
    assert not any(
        issue.code == "supported_claim_not_rendered"
        for issue in report.issues
    )

    # Negative control: caveated/unsupported verdicts never enter the set,
    # so an empty sentence-validated set must NOT cover the supported row.
    without = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[output],
        claims=claims,
        sentence_validated_claim_ids=(),
    )
    assert without.utility.supported_unit_recall == 0.0
    assert without.utility.completeness_coverage == 0.0
    (row,) = without.coverage_matrix
    assert row["coverage_status"] == "planned_but_not_rendered"
    assert without.utility.utility_gate_passed is False


def test_sentence_validated_concept_claim_ids_expands_supported_verdicts_only(
    tmp_path: Path,
) -> None:
    """R1/R2 wiring: the Writer expands supported sentence verdicts through
    the harness-owned concept-key -> frozen-claim-ID map, bound to the EXACT
    section whose authorship span contains the supported sentence.  Only
    ``status=supported`` verdicts of verified repository cards authorize
    claim IDs; caveated verdicts and candidate-only cards supply nothing; a
    missing final-claim identity authorizes nothing; and a sentence in one
    section never maps to another section."""
    claim = _quality_claim()
    section_markdown = "## Encoder\n\nThe encoder reads the configured input."
    final_text = section_markdown
    sentence_start = section_markdown.index("The encoder reads")
    sentence_end = len(section_markdown)
    ledger = ledger_from_section_outputs(
        final_text,
        (("section-a", section_markdown, "sha256:writer"),),
    )
    final_claims_path = tmp_path / "final_text_claims.json"
    final_claims_path.write_text(
        FinalTextClaims(
            input_text_digest="sha256:input",
            atomic_claims=[FinalAtomicClaim(
                atomic_claim_id=claim.claim_id,
                unit_id="unit-1",
                text="The encoder reads the configured input.",
                normalized_text="the encoder reads the configured input",
                line_start=2,
                line_end=2,
                char_start=sentence_start,
                char_end=sentence_end,
                claim_digest="sha256:claim-digest",
            )],
        ).model_dump_json(),
        encoding="utf-8",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    judgment = ConceptCardFieldJudgmentV1(
        field_name="operation",
        proposed_value="sorts scales",
        verdict="entailed",
        evidence_fragment_refs=("frag-1",),
        rationale="fragment frag-1 states the sorting operation.",
    )
    verdict = ConceptCardEvidenceVerdictV1(
        concept_key="CK-1",
        field_judgments=(judgment,),
        overall_verdict="entailed",
        rationale="every positive field is entailed by the cluster fragments.",
    )
    card = MethodConceptCardV1(
        concept_key="CK-1",
        authority_lane="repository",
        method_subject="descriptor",
        operation="sorts scales",
        evidence_verdict="entailed",
        may_enter_verified=True,
    )
    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        cards=(card,),
        evidence_verdicts=(verdict,),
        bindings=(ConceptCardBindingV1(
            concept_key="CK-1",
            source_obligation_ids=("obl-a",),
            source_span_ids=("span:encoder.py:1:2",),
        ),),
    )
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact-a",
            subject="sym:enc",
            predicate="reads",
            object="input",
            scope="sym:enc",
            direct_span_ids=["span:encoder.py:1:2"],
            exact_source_digest="sha256:s",
            canonical_identity="sha256:fa",
            validation_status="supported",
        )],
        content_digest="sha256:facts",
    )

    def _write_report(status: str) -> Path:
        report_path = tmp_path / f"validation-{status}.json"
        report_path.write_text(
            TextEvidenceValidationReport(
                status="passed" if status == "supported" else "failed",
                input_text_digest="sha256:input",
                projection_digest="sha256:projection",
                verdicts=[TextClaimEvidenceVerdict(
                    atomic_claim_id=claim.claim_id,
                    status=status,
                    matched_method_proposition_ids=["CK-1"],
                )],
            ).model_dump_json(),
            encoding="utf-8",
        )
        return report_path

    validation_paths = {
        "text_evidence_validation": "",
        "final_text_claims": str(final_claims_path),
    }

    def _report_paths(status: str) -> dict[str, str]:
        report_path = tmp_path / f"validation-{status}.json"
        report_path.write_text(
            TextEvidenceValidationReport(
                status="passed" if status == "supported" else "failed",
                input_text_digest="sha256:input",
                projection_digest="sha256:projection",
                verdicts=[TextClaimEvidenceVerdict(
                    atomic_claim_id=claim.claim_id,
                    status=status,
                    matched_method_proposition_ids=["CK-1"],
                )],
            ).model_dump_json(),
            encoding="utf-8",
        )
        return dict(validation_paths, text_evidence_validation=str(report_path))

    supported = _sentence_validated_concept_claim_ids(
        validation_paths=_report_paths("supported"),
        concept_cards=card_set,
        claims=claims,
        ledger=ledger,
        facts=facts,
    )
    assert supported == {"section-a": (claim.claim_id,)}

    caveated = _sentence_validated_concept_claim_ids(
        validation_paths=_report_paths("caveated"),
        concept_cards=card_set,
        claims=claims,
        ledger=ledger,
        facts=facts,
    )
    assert caveated == {}

    # Candidate-only cards never map to repository claim IDs.
    candidate_set = card_set.model_copy(update={
        "cards": tuple(
            item.model_copy(update={"may_enter_verified": False, "evidence_verdict": "not_checked"})
            for item in card_set.cards
        ),
        "evidence_verdicts": (),
    })
    candidate_only = _sentence_validated_concept_claim_ids(
        validation_paths=_report_paths("supported"),
        concept_cards=candidate_set,
        claims=claims,
        ledger=ledger,
        facts=facts,
    )
    assert candidate_only == {}

    # A missing validation file fails closed.
    missing = _sentence_validated_concept_claim_ids(
        validation_paths=dict(validation_paths, text_evidence_validation=str(tmp_path / "absent.json")),
        concept_cards=card_set,
        claims=claims,
        ledger=ledger,
        facts=facts,
    )
    assert missing == {}

    # A missing final-claims snapshot authorizes nothing (no section binding
    # is possible without the atomic claim identity).
    no_snapshot = _sentence_validated_concept_claim_ids(
        validation_paths=dict(
            validation_paths,
            text_evidence_validation=str(_report_paths("supported")["text_evidence_validation"]),
            final_text_claims=str(tmp_path / "absent-claims.json"),
        ),
        concept_cards=card_set,
        claims=claims,
        ledger=ledger,
        facts=facts,
    )
    assert no_snapshot == {}

    # Section binding: a supported sentence in section-a never maps to a
    # different section, and a second section's spans carry no claims.
    two_section_ledger = ledger_from_section_outputs(
        final_text + "\n\n## Second\n\nOther content.",
        (
            ("section-a", section_markdown, "sha256:writer"),
            ("section-b", "## Second\n\nOther content.", "sha256:writer"),
        ),
    )
    scoped = _sentence_validated_concept_claim_ids(
        validation_paths=_report_paths("supported"),
        concept_cards=card_set,
        claims=claims,
        ledger=two_section_ledger,
        facts=facts,
    )
    assert "section-b" not in scoped
    assert scoped.get("section-a") == (claim.claim_id,)


# ---------------------------------------------------------------------------
# R2 product-level regressions: all planned sections present, coherent
# headings, malformed punctuation, and raw implementation syntax all route
# to their authorized owner before final assembly.
# ---------------------------------------------------------------------------


def test_heading_truncation_detector_is_bounded_and_deterministic() -> None:
    from code2paper.agentic.publication_quality import (
        heading_is_truncated,
        heading_leaks_internal_id,
    )

    truncated = [
        "Motivation: limitations of vanilla SSMs \u2013 they ignore irregular "
        "timespans and are vulnerable to",
        "Redesign: timespan-informed \u0394t and A for temporally aware "
        "forgetting, and redefined B/C with",
        "Downstream adaptation: link prediction and node classification "
        "setups, plus a note on linear",
        "Second retrieval stage: passage retrieval via global importance "
        "aggregation (hybrid passage",
        "First stage: activation (initialization",
        "Construction details and a trailing ellipsis...",
        "Construction details and a dangling dash \u2013",
        "Motivation: limitations of vanilla",
        "Baseline comparison on plain",
        "Second retrieval stage: passage retrieval via global importance "
        "aggregation (hybrid passage**Purpose",
        "Second retrieval stage: passage retrieval via global importance "
        "aggregation (hybrid passage)Global",
        "Motivation: limitations of vanilla SSMs – they ignore irregular "
        "timespans and are vulnerable to input noise Motivation",
    ]
    for heading in truncated:
        assert heading_is_truncated(heading), heading
    complete = [
        "Encoder",
        "How to",
        "Dynamic graph encoding: how interaction sequences are represented "
        "with heterogeneous features",
        "First retrieval stage: relevant entity activation via local "
        "semantic bridging (initialization)",
        "Passage ranking",
        "Offline Tri\u2011Graph construction (entities, sentences, passages, "
        "contain/message adjacency)",
        "Motivation: limitations of vanilla SSMs",
    ]
    for heading in complete:
        assert not heading_is_truncated(heading), heading
    assert heading_leaks_internal_id("Stage CK-9c5360a570a6c8c7 setup")
    assert not heading_leaks_internal_id("Stage setup")
    from code2paper.agentic.publication_quality import dangling_heading_tail
    assert dangling_heading_tail(
        "Motivation: limitations of vanilla SSMs \u2013 they ignore irregular "
        "timespans and are vulnerable to"
    ) == "are vulnerable to"
    assert dangling_heading_tail(
        "Second retrieval stage: passage retrieval via global importance "
        "aggregation (hybrid passage"
    ) == "(hybrid passage"
    assert dangling_heading_tail("Encoder") == ""
    from code2paper.agentic.publication_quality import heading_replacement_is_coherent
    planned = (
        "Offline Tri\u2011Graph construction (entities, sentences, passages, "
        "contain/message adjacency"
    )
    # Coherent shortenings are accepted; a degenerate one-word heading and a
    # stray unbalanced closing parenthesis are not.
    assert heading_replacement_is_coherent(
        "Offline Tri\u2011Graph construction", planned_heading=planned
    )
    assert not heading_replacement_is_coherent("Offline", planned_heading=planned)
    assert not heading_replacement_is_coherent(
        "First retrieval stage: relevant entity activation via local semantic "
        "bridging )",
        planned_heading=(
            "First retrieval stage: relevant entity activation via local "
            "semantic bridging (initialization)"
        ),
    )
    assert not heading_replacement_is_coherent(
        "Encoder", planned_heading="Encoder"
    )


def test_coherent_heading_never_ends_on_dangling_connective() -> None:
    from code2paper.agentic.publication_quality import (
        coherent_heading,
        heading_is_truncated,
        heading_tail_leaked_into_body,
    )

    long_title = (
        "Motivation: limitations of vanilla SSMs – they ignore irregular "
        "timespans and are vulnerable to"
    )
    heading = coherent_heading(
        long_title,
        limit=120,
        intended_role="motivation",
        source_text=long_title,
    )
    assert not heading_is_truncated(heading)
    assert not heading.rstrip().endswith(("to", "with", "and", "("))
    leaked = heading_tail_leaked_into_body(
        plan_heading=long_title,
        rendered_heading="Motivation: limitations of vanilla SSMs",
        body="they ignore irregular timespans and are vulnerable to padding.",
    )
    assert leaked
    assert coherent_heading("Encoder") == "Encoder"
    assert coherent_heading("Offline") == "Offline"
    duplicated = (
        "Motivation: limitations of vanilla SSMs – they ignore irregular "
        "timespans and are vulnerable to input noise Motivation"
    )
    repaired = coherent_heading(
        duplicated,
        limit=120,
        intended_role="motivation",
        source_text=duplicated,
    )
    assert not repaired.endswith("Motivation")
    assert repaired.lower().count("motivation") == 1
    assert not heading_is_truncated(repaired)


def test_truncated_plan_heading_is_repaired_before_final_assembly(
    tmp_path: Path,
) -> None:
    """R2: a plan heading truncated mid-clause is never copied verbatim into
    the final document.  A Writer output that copies the broken clause is
    rejected at acceptance and routed BACK to the Writer (whole-section
    regeneration); the retried section must carry a coherent heading."""
    from code2paper.agentic.publication_quality import heading_is_truncated

    paths = _artifacts(tmp_path)
    plan_path = Path(paths["method_section_plan_v2"])
    plan = MethodSectionPlanV2.model_validate_json(plan_path.read_text())
    first = plan.sections[0]
    plan = plan.model_copy(update={"sections": tuple(
        section.model_copy(update={
            "heading": "Motivation: limitations of vanilla SSMs and redefined B/C with",
        }) if section.section_id == first.section_id else section
        for section in plan.sections
    )})
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    truncated_heading = "Motivation: limitations of vanilla SSMs and redefined B/C with"
    coherent_heading = "## Motivation: limits of vanilla SSMs and a redefined B/C scheme"
    calls: list[str] = []

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        section_id = request.input_payload["section_id"]
        calls.append(section_id)
        heading = (
            coherent_heading
            if request.input_payload.get("previous_attempt_error")
            == "section_heading_truncated"
            else f"## {truncated_heading}"
        )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": (
                    f"{heading}\n\nThe encoder reads the configured input."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash=f"sha256:writer-truncated-heading-{len(calls)}",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
    )
    # Initial call + run-level missing-section retry after rejection.
    assert calls == [first.section_id, first.section_id], calls
    assert any(
        item.get("provenance") == "writer_missing_section_retry"
        and any(
            operation.endswith("section_heading_truncated")
            for operation in item.get("operations", ())
        )
        for item in result.response_recovery_traces
    )
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    headings = [
        line[3:].strip()
        for line in candidate.splitlines()
        if line.lstrip().startswith("## ")
    ]
    assert headings, candidate
    assert all(not heading_is_truncated(value) for value in headings), headings
    assert coherent_heading in candidate
    assert f"## {truncated_heading}" not in candidate
    assert result.status != "blocked"


def test_missing_section_output_is_routed_back_to_writer_once(tmp_path: Path) -> None:
    """R2: a planned section whose Writer call produced no usable output is
    routed BACK to the Writer exactly once with its author-intent retry
    instruction; an accepted retry body restores the section, and an
    exhausted retry leaves the run honestly incomplete."""
    paths = _two_section_plan(tmp_path)
    calls: dict[str, int] = {}
    saw_retry_instruction: list[bool] = []

    def caller(_config, request):
        section_id = request.input_payload["section_id"]
        calls[section_id] = calls.get(section_id, 0) + 1
        binding = request.input_payload["binding_contract"]
        # The section writer consumes one bounded schema-failure retry
        # internally; only the run-level missing-section retry carries the
        # author-intent instruction.
        if section_id == "MA-S2" and calls[section_id] <= 2:
            return LLMResponse(
                text="",
                response_hash="sha256:writer-missing-s2",
                blocked_reason="publication_section_schema_failed:test",
                finish_reason="stop",
            )
        if section_id == "MA-S2":
            saw_retry_instruction.append(
                bool(request.input_payload.get("missing_section_retry_instruction"))
            )
        body = (
            "## Encoder\n\nThe encoder reads the configured input."
            if section_id == "MA-S1"
            else "## Output interface\n\nIts representation is returned to the downstream stage."
        )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": body,
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash=f"sha256:writer:{section_id}:{calls[section_id]}",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )
    # Initial call + internal schema retry + run-level missing-section retry.
    assert calls.get("MA-S2", 0) == 3, calls
    assert saw_retry_instruction == [True]
    assert "MA-S2" in result.accepted_section_ids
    assert "MA-S2" not in result.incomplete_section_ids
    assert any(
        item.get("provenance") == "writer_missing_section_retry"
        for item in result.response_recovery_traces
    )
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "## Output interface" in candidate

    # Initial + internal schema retry + run-level missing retry + its
    # internal schema retry: every bounded attempt failing keeps the run
    # incomplete and the section visibly missing — never relabeled
    # successful.
    paths2 = _two_section_plan(tmp_path)
    calls2: dict[str, int] = {}

    def failing_caller(_config, request):
        section_id = request.input_payload["section_id"]
        calls2[section_id] = calls2.get(section_id, 0) + 1
        if section_id == "MA-S2":
            return LLMResponse(
                text="",
                response_hash="sha256:writer-missing-s2",
                blocked_reason="publication_section_schema_failed:test",
                finish_reason="stop",
            )
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer:s1",
            finish_reason="stop",
        )

    result2, outputs2 = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths2,
        llm_config=_config(),
        llm_caller=failing_caller,
    )
    # Initial + internal schema retry + two run-level missing retries each
    # with its own internal schema retry: every bounded attempt failing
    # keeps the run incomplete and the section visibly missing — never
    # relabeled successful.
    assert calls2.get("MA-S2", 0) == 6, calls2
    assert result2.status == "incomplete"
    assert "MA-S2" in result2.incomplete_section_ids
    assert "MA-S2" not in result2.accepted_section_ids
    candidate2 = Path(outputs2["publication_candidate_method"]).read_text()
    assert "## Output interface" not in candidate2


def test_malformed_transition_punctuation_is_repaired_by_rewrite(
    tmp_path: Path,
) -> None:
    """R2: a dangling fragment like ``steps. , and result return`` is a typed
    Rewrite issue; the accepted patch removes the malformed punctuation and
    the final text contains none."""
    paths = _two_section_plan(tmp_path)
    malformed = (
        "## Output interface\n\nThis includes computing shapes and logging "
        "precomputation steps. , and result return operations are partial."
    )
    rewrite_calls: list[str] = []

    def writer_caller(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        body = (
            "## Encoder\n\nThe encoder reads the configured input."
            if section_id == "MA-S1" else malformed
        )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": body,
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash=f"sha256:writer:{section_id}",
            finish_reason="stop",
        )

    def rewrite_caller(_config, request):
        rewrite_calls.append(request.input_payload["issues"])
        incumbent = request.input_payload["incumbent_text"]
        original = "steps. , and result return operations"
        start = incumbent.index(original)
        issue_id = request.input_payload["issues"][0]["sentence_id"]
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "rewrite:punctuation",
                    "section_id": request.input_payload["section_context"]["section_id"],
                    "start": start,
                    "end": start + len(original),
                    "original_text": original,
                    "replacement_text": "steps and result return operations",
                    "issue_ids": [issue_id],
                    "allowed_scope": "wording_only",
                }],
                "self_identified_risks": [],
                "incomplete": False,
            }),
            response_hash="sha256:rewrite-punctuation",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=rewrite_caller,
    )
    assert rewrite_calls
    assert any(
        item.get("sentence_id", "").startswith("style:MA-S2:sentence-terminator-comma")
        for items in rewrite_calls for item in items
    )
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "steps. ," not in candidate
    assert "steps and result return operations" in candidate
    assert result.status != "blocked"


def test_raw_implementation_syntax_is_flagged_for_editor_rewrite_owner() -> None:
    """R2: raw Python subscripts and shape indexing in reader-facing prose
    are code-trace narration for the shared detector, and the owning repair
    route sees the exact same issue the quality report records."""
    from code2paper.agentic.publication_method_writer import (
        _method_language_repair_issues_by_section,
    )
    from code2paper.agentic.publication_quality import (
        find_code_trace_prose_sections,
    )

    output = _leakage_output(
        section_id="section-a",
        markdown=(
            "## Encoder\n\nWhen doc['chunk_id'] == query['chunk_id'], target "
            "chunks are appended. The reduction branches on loss_i.shape[0] "
            "== 0 and stacks the resulting losses."
        ),
    )
    flagged = find_code_trace_prose_sections([output])
    assert flagged and flagged[0][0] == "section-a"
    issues = _method_language_repair_issues_by_section({"section-a": output})
    assert any(
        issue.sentence_id.endswith("code-trace")
        for issue in issues["section-a"]
    )
    # Parenthetical backtick bindings stay the intended evidence form.
    clean = _leakage_output(
        section_id="section-b",
        markdown=(
            "## Encoder\n\nThe encoder aligns shapes (`e2s_shape[0]`, "
            "`e2s_shape[1]`) before ranking."
        ),
    )
    assert not find_code_trace_prose_sections([clean])


# ---------------------------------------------------------------------------
# R3: callback bundle transitive copy — file-backed artifacts survive a
# replay, refs are rebased, digests revalidated, and reuse is reported
# distinctly from a new resume event.
# ---------------------------------------------------------------------------


def _fulfilled_callback_bundle(
    *,
    request_id: str = "request:MA-S2:limitations_or_mismatch",
    section_id: str = "MA-S2",
    artifact_id: str = "artifact:MA-S2:callback-1",
) -> tuple[WritingResearchCallbackBundleV1, WritingResearchRequestV1]:
    request = WritingResearchRequestV1(
        request_id=request_id,
        section_id=section_id,
        argument_unit_id="MA-S2:unit-1",
        missing_rhetorical_move="limitations_or_mismatch",
        exact_question="Which branch condition is authoritative?",
        required_authority_lane="executable_hard",
        status="fulfilled",
        fulfilled_artifact_ids=(artifact_id,),
    )
    artifact = WritingResearchCallbackArtifactV1(
        artifact_id=artifact_id,
        request_id=request_id,
        section_id=section_id,
        argument_unit_id="MA-S2:unit-1",
        authority_lane="executable_hard",
        artifact_ref="pending-ref",
        artifact_digest="sha256:" + "a" * 64,
        validated=True,
    )
    bundle = WritingResearchCallbackBundleV1(
        requests=(request,),
        artifacts={request_id: (artifact,)},
        requested_resume_section_ids=(section_id,),
        resume_section_ids=(section_id,),
    )
    return bundle, request


def test_callback_bundle_transitive_copy_rebases_and_reuses(tmp_path: Path) -> None:
    from code2paper.agentic.publication_method_writer import (
        _read_verified_callback_bundle,
        rebase_callback_bundle_artifacts,
    )

    frozen = tmp_path / "frozen-root"
    relative = (
        "research_tool_data/writing_callbacks/"
        "request:MA-S2:limitations_or_mismatch/"
        "writing-callback:request:MA-S2:limitations_or_mismatch:865141e7ce13.json"
    )
    evidence = frozen / relative
    evidence.parent.mkdir(parents=True)
    evidence.write_text('{"objective":"use the verified feature path"}\n', encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(evidence.read_bytes()).hexdigest()
    bundle, request = _fulfilled_callback_bundle()
    (artifact,) = bundle.artifacts[request.request_id]
    artifact = artifact.model_copy(update={
        "artifact_ref": f"../{relative}",
        "artifact_digest": digest,
    })
    bundle = bundle.model_copy(update={
        "artifacts": {request.request_id: (artifact,)},
    })
    bundle_dir = frozen / "artifacts"
    bundle_dir.mkdir(parents=True)
    bundle_path = bundle_dir / "writing_research_callback_artifacts_v1.json"
    # Rebuild with a fresh digest: model_copy does not re-run validators.
    bundle_path.write_text(
        bundle.model_dump_json(indent=2, exclude={"content_digest"}),
        encoding="utf-8",
    )

    fresh = tmp_path / "fresh-root"
    report = rebase_callback_bundle_artifacts(
        bundle_path=bundle_path,
        frozen_root=frozen,
        fresh_root=fresh,
    )
    assert report["failures"] == [], report["failures"]
    assert report["reused_fulfilled_callback_ids"] == [request.request_id]
    (copied,) = report["copied_refs"]
    assert copied["digest"] == digest
    copied_target = Path(copied["target"])
    assert copied_target.is_file()
    assert copied_target.read_bytes() == evidence.read_bytes()
    rebased = report["bundle"]
    (rebased_artifact,) = rebased["artifacts"][request.request_id]
    assert rebased_artifact["artifact_ref"] == f"../{relative}"

    # The rebased bundle is digest-valid and Writer-consumable from the
    # fresh root: the file-backed preview resolves against the fresh bundle
    # directory with the recorded digest intact.
    fresh_bundle = fresh / "artifacts" / "writing_research_callback_artifacts_v1.json"
    fresh_bundle.parent.mkdir(parents=True)
    fresh_bundle.write_text(json.dumps(rebased, ensure_ascii=False, indent=2), encoding="utf-8")
    loaded = _read_verified_callback_bundle(fresh_bundle)
    (loaded_artifact,) = loaded.artifacts[request.request_id]
    payload, failure = _callback_artifact_prompt_payload(
        loaded_artifact,
        base_dir=fresh_bundle.parent,
    )
    assert failure == "", failure
    assert payload["artifact_preview"].startswith('{"objective"')


def test_callback_bundle_transitive_copy_rejects_traversal_missing_and_tampered(
    tmp_path: Path,
) -> None:
    from code2paper.agentic.publication_method_writer import (
        rebase_callback_bundle_artifacts,
    )

    frozen = tmp_path / "frozen-root"
    bundle_dir = frozen / "artifacts"
    bundle_dir.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text("secret\n", encoding="utf-8")
    evidence = frozen / "research_tool_data" / "callbacks" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text('{"ok":true}\n', encoding="utf-8")
    good_digest = "sha256:" + hashlib.sha256(evidence.read_bytes()).hexdigest()
    fresh = tmp_path / "fresh-root"
    counter = 0

    def make_bundle(ref: str, digest: str) -> Path:
        nonlocal counter
        counter += 1
        bundle, request = _fulfilled_callback_bundle()
        (artifact,) = bundle.artifacts[request.request_id]
        artifact = artifact.model_copy(update={
            "artifact_ref": ref,
            "artifact_digest": digest,
        })
        bundle = bundle.model_copy(update={
            "artifacts": {request.request_id: (artifact,)},
        })
        path = bundle_dir / f"bundle-{counter}.json"
        path.write_text(
            bundle.model_dump_json(indent=2, exclude={"content_digest"}),
            encoding="utf-8",
        )
        return path

    # Traversal: the ref escapes the frozen root.
    traversal = make_bundle("../../outside.json", good_digest)
    report = rebase_callback_bundle_artifacts(
        bundle_path=traversal, frozen_root=frozen, fresh_root=fresh,
    )
    assert any(
        "artifact_ref_outside_frozen_root" in item for item in report["failures"]
    ), report["failures"]
    assert report["bundle"] is None

    # Missing file.
    missing = make_bundle("../research_tool_data/callbacks/absent.json", good_digest)
    report = rebase_callback_bundle_artifacts(
        bundle_path=missing, frozen_root=frozen, fresh_root=fresh,
    )
    assert any("artifact_ref_missing" in item for item in report["failures"]), report["failures"]

    # Digest mismatch.
    tampered = make_bundle(
        "../research_tool_data/callbacks/evidence.json", "sha256:" + "b" * 64
    )
    report = rebase_callback_bundle_artifacts(
        bundle_path=tampered, frozen_root=frozen, fresh_root=fresh,
    )
    assert any("artifact_digest_mismatch" in item for item in report["failures"]), report["failures"]

    # Symlinked source.
    link = frozen / "research_tool_data" / "callbacks" / "link.json"
    link.symlink_to(outside)
    linked = make_bundle("../research_tool_data/callbacks/link.json", good_digest)
    report = rebase_callback_bundle_artifacts(
        bundle_path=linked, frozen_root=frozen, fresh_root=fresh,
    )
    assert any("artifact_ref_symlink" in item for item in report["failures"]), report["failures"]

    # Every rejected replay left the fresh root empty: nothing was copied.
    copied_anywhere = list((fresh / "research_tool_data").rglob("*")) if (
        fresh / "research_tool_data"
    ).exists() else []
    assert copied_anywhere == []


def test_heading_tail_leak_is_routed_to_rewrite() -> None:
    """W1: a shortened heading must not leave its unused suffix as the body start."""
    from code2paper.agentic.publication_method_writer import (
        _section_structure_issues_by_section,
    )
    from code2paper.llm.section_writer import WriterSectionInput

    writer_input = WriterSectionInput(
        section_id="MA-S1",
        heading=(
            "Redesign: timespan-informed Δt and A for temporally aware "
            "forgetting, and redefined B/C with"
        ),
        prompt_payload={},
    )
    issues = _section_structure_issues_by_section(
        {
            "MA-S1": _leakage_output(
                markdown=(
                    "## Redesign: timespan-informed Δt\n\n"
                    "A for temporally aware forgetting, and redefined B/C with "
                    "the filter layer forward pass."
                ),
            ),
        },
        writer_inputs={"MA-S1": writer_input},
    )
    assert any(
        issue.failure_type == "heading_tail_leaked_into_body"
        for issue in issues.get("MA-S1", ())
    )


def test_headings_only_section_output_is_routed_back_to_writer(
    tmp_path: Path,
) -> None:
    """R2: a structured Writer response whose markdown is only repeated
    heading lines has no Method body.  It is not accepted and is routed
    back to the Writer by the missing-section retry; the retried body
    restores the section and the final text contains no heading debris."""
    paths = _two_section_plan(tmp_path)
    calls: dict[str, int] = {}
    retry_errors: list[str] = []

    def caller(_config, request):
        section_id = request.input_payload["section_id"]
        calls[section_id] = calls.get(section_id, 0) + 1
        binding = request.input_payload["binding_contract"]
        if section_id == "MA-S2" and calls[section_id] == 1:
            return LLMResponse(
                text=json.dumps({
                    "section_id": section_id,
                    "section_markdown": (
                        "## Output interface.## Output interface.## Output interface."
                    ),
                    "used_argument_unit_ids": binding["used_argument_unit_ids"],
                    "used_claim_ids": binding["used_claim_ids"],
                    "used_equation_ids": binding["used_equation_ids"],
                    "used_configuration_ids": binding["used_configuration_ids"],
                    "completed_rhetorical_moves": _completed_moves(binding),
                }),
                response_hash="sha256:writer-headings-only",
                finish_reason="stop",
            )
        if section_id == "MA-S2":
            retry_errors.append(
                request.input_payload.get("previous_attempt_error", "")
            )
        body = (
            "## Encoder\n\nThe encoder reads the configured input."
            if section_id == "MA-S1"
            else "## Output interface\n\nIts representation is returned to the downstream stage."
        )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": body,
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash=f"sha256:writer:{section_id}:{calls[section_id]}",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )
    assert calls.get("MA-S2", 0) == 2, calls
    assert retry_errors == ["section_body_missing_or_headings_only"]
    assert "MA-S2" in result.accepted_section_ids
    assert any(
        item.get("provenance") == "writer_missing_section_retry"
        for item in result.response_recovery_traces
    )
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "## Output interface## " not in candidate
    assert "## Output interface\n\nIts representation is returned" in candidate


def test_sentence_validated_coverage_is_section_scoped() -> None:
    """R2: sentence-validated claim coverage binds to the exact section that
    rendered the supported sentence.  A supported sentence in section-a can
    never close a completeness row planned for section-b, and the same-
    section positive still covers."""
    claim_a = _quality_claim(claim_id="claim-a")
    claim_b = _quality_claim(claim_id="claim-b")
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim_a, claim_b],
        content_digest="sha256:claims",
    )
    unit_a = MethodArgumentUnitV1(
        argument_unit_id="unit-a",
        section_role="mechanism",
        research_question="How does A work?",
        claim_ids=("claim-a",),
        authority_lanes=("executable_hard",),
    )
    unit_b = MethodArgumentUnitV1(
        argument_unit_id="unit-b",
        section_role="mechanism",
        research_question="How does B work?",
        claim_ids=("claim-b",),
        authority_lanes=("executable_hard",),
    )
    plan = MethodSectionPlanV2(
        plan_id="plan-ab",
        sections=(
            SectionArgumentGraphV1(
                section_id="section-a",
                heading="Encoder",
                reader_question="How does A work?",
                argument_unit_ids=("unit-a",),
                moves=tuple(
                    SectionArgumentMoveV1(
                        move=move, argument_unit_ids=("unit-a",),
                        allowed_authority_lanes=("executable_hard",), required=True,
                    ) for move in _COMPLETED_CORE_MOVES
                ),
            ),
            SectionArgumentGraphV1(
                section_id="section-b",
                heading="Decoder",
                reader_question="How does B work?",
                argument_unit_ids=("unit-b",),
                moves=tuple(
                    SectionArgumentMoveV1(
                        move=move, argument_unit_ids=("unit-b",),
                        allowed_authority_lanes=("executable_hard",), required=True,
                    ) for move in _COMPLETED_CORE_MOVES
                ),
            ),
        ),
        argument_units=(unit_a, unit_b),
    )
    completeness = MethodCompletenessMatrixV1(items=(
        MethodCompletenessItemV1(
            obligation_id="obl-a", status="supported_by_repository",
            claim_ids=("claim-a",),
        ),
        MethodCompletenessItemV1(
            obligation_id="obl-b", status="supported_by_repository",
            claim_ids=("claim-b",),
        ),
    ))
    # Concept lane: no declared used_claim_ids; claim-b's canonical sentence
    # appears ONLY in section-a's markdown (the false-coverage trap).
    out_a = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown=(
            "## Encoder\n\nThe encoder reads the configured input. "
            "Claim B text rendered in the wrong section: the encoder reads "
            "the configured input."
        ),
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )
    out_b = PublicationMethodSectionOutputV1(
        section_id="section-b",
        section_markdown="## Decoder\n\nThe decoder emits the output.",
        used_argument_unit_ids=["unit-b"],
        used_claim_ids=[],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )

    # claim-b's supported sentence is bound to section-a only: row obl-b
    # (planned for section-b) must remain uncovered.
    report = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[out_a, out_b],
        claims=claims,
        sentence_validated_claim_ids={"section-a": ("claim-a", "claim-b")},
    )
    rows = {row["obligation_id"]: row for row in report.coverage_matrix}
    assert rows["obl-a"]["coverage_status"] == "covered"
    assert rows["obl-b"]["coverage_status"] == "planned_but_not_rendered"
    assert rows["obl-b"]["used_claim_ids"] == []
    assert report.utility.supported_unit_recall == 0.5

    # Same-section positive: claim-b supported in section-b covers obl-b.
    out_b2 = PublicationMethodSectionOutputV1(
        section_id="section-b",
        section_markdown=(
            "## Decoder\n\nThe encoder reads the configured input."
        ),
        used_argument_unit_ids=["unit-b"],
        used_claim_ids=[],
        completed_rhetorical_moves=list(_COMPLETED_CORE_MOVES),
    )
    report2 = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[out_a, out_b2],
        claims=claims,
        sentence_validated_claim_ids={"section-a": ("claim-a",), "section-b": ("claim-b",)},
    )
    rows2 = {row["obligation_id"]: row for row in report2.coverage_matrix}
    assert rows2["obl-a"]["coverage_status"] == "covered"
    assert rows2["obl-b"]["coverage_status"] == "covered"
    assert report2.utility.supported_unit_recall == 1.0

    # Caveated/unsupported verdicts still authorize nothing, and a claim
    # rendered in no planned section stays uncovered.
    report3 = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[out_a, out_b],
        claims=claims,
        sentence_validated_claim_ids={},
    )
    rows3 = {row["obligation_id"]: row for row in report3.coverage_matrix}
    assert rows3["obl-a"]["coverage_status"] == "planned_but_not_rendered"
    assert rows3["obl-b"]["coverage_status"] == "planned_but_not_rendered"
    assert report3.utility.supported_unit_recall == 0.0


def test_exact_required_qualifier_terms_are_not_style_regressions() -> None:
    """R1: exact predicates are exempt only in their compact binding form.

    The reverse validator requires the predicate verbatim, while the
    publication-style detector must still reject an inline source-code
    sentence.  The accepted representation is prose plus a parenthetical
    backtick binding, and unrelated raw syntax remains flagged.
    """
    from code2paper.agentic.publication_quality import find_code_trace_prose_sections

    term = "doc['chunk_id'] == query['chunk_id']"
    output = _leakage_output(
        section_id="section-a",
        markdown=(
            "## Encoder\n\nWhen doc['chunk_id'] == query['chunk_id'], target "
            "chunks are appended to the context window."
        ),
    )
    # An inline exact predicate is still implementation narration.
    assert find_code_trace_prose_sections([output])
    assert find_code_trace_prose_sections(
        [output],
        exempt_qualifier_terms={"section-a": (term,)},
    )
    bound_output = _leakage_output(
        section_id="section-a",
        markdown=(
            "## Encoder\n\nTarget chunks are appended when the identifiers "
            "match (`doc['chunk_id'] == query['chunk_id']`)."
        ),
    )
    assert not find_code_trace_prose_sections(
        [bound_output],
        exempt_qualifier_terms={"section-a": (term,)},
    )
    # Wrapping an exact predicate in backticks is not enough without the
    # section's frozen qualifier authority.
    assert find_code_trace_prose_sections([bound_output])
    # A DIFFERENT bracket access in the same section remains flagged.
    output2 = _leakage_output(
        section_id="section-a",
        markdown=(
            "## Encoder\n\nWhen doc['chunk_id'] == query['chunk_id'], the "
            "temporary index temp['x'] is consulted."
        ),
    )
    assert find_code_trace_prose_sections(
        [output2],
        exempt_qualifier_terms={"section-a": (term,)},
    )
    # .shape indexing follows the same rule: an inline exact term and other
    # occurrences remain flagged.
    shape_term = "loss_i.shape[0] == 0"
    output3 = _leakage_output(
        section_id="section-a",
        markdown=(
            "## Encoder\n\nThe reduction branches on loss_i.shape[0] == 0 and "
            "stacks the resulting losses; other tensors use loss_j.shape[0]."
        ),
    )
    assert find_code_trace_prose_sections(
        [output3],
        exempt_qualifier_terms={"section-a": (shape_term,)},
    )
    shape_bound = _leakage_output(
        section_id="section-a",
        markdown=(
            "## Encoder\n\nThe reduction is accepted when the empty-shape "
            "condition holds (`loss_i.shape[0] == 0`)."
        ),
    )
    assert not find_code_trace_prose_sections(
        [shape_bound],
        exempt_qualifier_terms={"section-a": (shape_term,)},
    )
    assert find_code_trace_prose_sections(
        [_leakage_output(
            section_id="section-a",
            markdown=(
                "## Encoder\n\nThe reduction branches on loss_i.shape[0] == 0."
            ),
        )],
        exempt_qualifier_terms={"section-a": (shape_term,)},
    )


def test_canonical_qualifier_map_survives_compact_writer_projection(
    tmp_path: Path,
) -> None:
    """The Rewrite/Editor detector must use plan authority even when the
    Writer payload intentionally omits the low-level validation constraint."""
    from code2paper.agentic.publication_method_writer import (
        _academic_rewrite_issues_by_section,
        _qualifier_terms_by_section,
    )
    from code2paper.llm.section_writer import WriterSectionInput

    paths = _artifacts(tmp_path)
    plan = MethodSectionPlanV2.model_validate_json(
        Path(paths["method_section_plan_v2"]).read_text()
    )
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    term = "doc['chunk_id'] == query['chunk_id']"
    claims = claims.model_copy(update={
        "claims": tuple(
            claim.model_copy(update={"required_qualifiers": [term]})
            for claim in claims.claims
        ),
    })
    section = plan.sections[0]
    writer_input = WriterSectionInput(
        section_id=section.section_id,
        heading=section.heading,
        # Simulate concept-card projection: validation_constraints has no
        # claim rows, but the persisted plan/claim relation remains complete.
        prompt_payload={"validation_constraints": {"claims": []}},
    )
    output = _leakage_output(
        section_id=section.section_id,
        markdown=(
            f"## {section.heading}\n\nThe encoder retains the input when "
            "the identifiers match (`doc['chunk_id'] == query['chunk_id']`)."
        ),
    )
    canonical = _academic_rewrite_issues_by_section(
        {section.section_id: output},
        claims=claims,
        writer_inputs={section.section_id: writer_input},
        qualifier_terms_by_section={section.section_id: (term,)},
    )
    assert not any(
        issue.failure_type == "method_language_style"
        for issue in canonical.get(section.section_id, ())
    )
    legacy = _academic_rewrite_issues_by_section(
        {section.section_id: output},
        claims=claims,
        writer_inputs={section.section_id: writer_input},
    )
    assert any(
        issue.failure_type == "method_language_style"
        for issue in legacy.get(section.section_id, ())
    )
    ambiguous_plan = plan.model_copy(update={
        "sections": (
            section,
            section.model_copy(update={"section_id": "section-b"}),
        ),
    })
    assert _qualifier_terms_by_section(
        plan=ambiguous_plan,
        claims=claims,
    ) == {}


def test_qualifier_binding_matrix_is_section_scoped_and_nested() -> None:
    """Exercise the real binding forms emitted by the live replays."""
    from code2paper.agentic.publication_quality import (
        find_code_trace_prose_sections,
    )

    section_a = _leakage_output(
        section_id="section-a",
        markdown=(
            "## Retrieval\n\nThe retrieval branch is active when new passage "
            "hashes are available (`len(new_passage_hash_ids) > 0`) and the "
            "vectorized path is enabled (`self.config.use_vectorized_retrieval`)."
        ),
    )
    section_b = _leakage_output(
        section_id="section-b",
        markdown=(
            "## Memory\n\nAn edge is retained when its endpoint pair is "
            "present (`(src_node_id, dst_node_id) in edge_memories`) and the "
            "empty-loss branch holds (`loss_i.shape[0] == 0`)."
        ),
    )
    terms = {
        "section-a": (
            "len(new_passage_hash_ids) > 0",
            "self.config.use_vectorized_retrieval",
        ),
        "section-b": (
            "(src_node_id, dst_node_id) in edge_memories",
            "loss_i.shape[0] == 0",
        ),
    }
    assert not find_code_trace_prose_sections(
        [section_a, section_b],
        exempt_qualifier_terms=terms,
    )

    # A correct binding in one section must not authorize a different raw
    # predicate in that section or leak into the other section.
    wrong = _leakage_output(
        section_id="section-a",
        markdown=(
            "## Retrieval\n\nThe branch is active when another set is "
            "non-empty (`len(other_passage_hash_ids) > 0`)."
        ),
    )
    assert find_code_trace_prose_sections(
        [wrong],
        exempt_qualifier_terms=terms,
    )
    inline = _leakage_output(
        section_id="section-b",
        markdown=(
            "## Memory\n\nWhen (src_node_id, dst_node_id) in edge_memories, "
            "the empty-loss branch is selected."
        ),
    )
    assert find_code_trace_prose_sections(
        [inline],
        exempt_qualifier_terms=terms,
    )


def test_qualifier_transaction_requires_targeted_failure_reduction() -> None:
    from code2paper.agentic.publication_method_writer import (
        _rewrite_transaction_has_cluster_gain,
    )

    incumbent = {
        "validation_status": "failed",
        "validation_counts": (1, 0, -1),
        "style_issue_count": 0,
        "structure_issue_count": 0,
        "missing_propositions": 0,
        "leakage_count": 0,
        "unsupported_by_section": {
            "section-a": [{
                "atomic_claim_id": "FAC-1",
                "status": "unsupported",
                "failures": ["required_qualifier_missing"],
            }],
        },
    }
    unrelated_gain = {
        **incumbent,
        "validation_counts": (0, 0, -1),
    }
    accepted = _rewrite_transaction_has_cluster_gain(
        incumbent,
        unrelated_gain,
        cluster_name="qualifier_numeric_formula",
    )
    assert accepted == (False, "qualifier_target_not_reduced")

    targeted = {
        **unrelated_gain,
        "unsupported_by_section": {},
    }
    assert _rewrite_transaction_has_cluster_gain(
        incumbent,
        targeted,
        cluster_name="qualifier_numeric_formula",
    ) == (True, "monotonic_cluster_gain")


def test_exact_qualifier_binding_satisfies_validation_and_style(tmp_path: Path) -> None:
    """R1 end-to-end: a missing exact qualifier with raw-code predicate is
    repaired in the allowed reader-facing form (prose + parenthetical backtick
    binding), passes reverse validation with zero unsupported, and the repair
    transaction is accepted (no method_style_regressed deadlock)."""
    paths = _artifacts(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    qualifier = "doc['chunk_id'] == query['chunk_id']"
    claims = claims.model_copy(update={
        "claims": tuple(
            claim.model_copy(update={"required_qualifiers": [qualifier]})
            if claim.claim_id == "claim-read" else claim
            for claim in claims.claims
        ),
    })
    Path(paths["atomic_claims_v3"]).write_text(
        claims.model_dump_json(indent=2), encoding="utf-8"
    )
    span = EvidenceSpanV3(
        span_id="span:encoder.py:1:2",
        snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        path="encoder.py",
        symbol="encoder",
        line_start=1,
        line_end=2,
        exact_excerpt="The encoder reads the configured input in the case study.",
        excerpt_digest="sha256:excerpt",
        file_digest="sha256:file",
        role="anchor",
    )
    packets = EvidencePacketSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id="repo:writer",
        project_tree_hash="sha256:tree",
        packets=[EvidencePacketV3(
            packet_id="packet:encoder",
            scope="sym:encoder",
            anchor_span_ids=[span.span_id],
            spans=[span],
            source_digest="sha256:packet-source",
        )],
        content_digest="sha256:packets-with-span",
    )
    Path(paths["evidence_packets_v3"]).write_text(
        packets.model_dump_json(indent=2), encoding="utf-8"
    )
    claims = claims.model_copy(update={"evidence_packet_digest": packets.content_digest})
    Path(paths["atomic_claims_v3"]).write_text(
        claims.model_dump_json(indent=2), encoding="utf-8"
    )
    method_path = tmp_path / "method_evidence.json"
    method_path.write_text(
        MethodEvidence(
            project_id="fixture",
            method_name="Encoder",
            method_goal="Describe the encoder.",
            implementation_scope="fixture repository",
        ).model_dump_json(),
        encoding="utf-8",
    )
    paths["method_evidence"] = str(method_path)

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        assert request.input_payload["required_qualifier_bindings"] == [qualifier]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-no-qualifier",
            finish_reason="stop",
        )

    def rewrite_caller(_config, request):
        incumbent = request.input_payload["incumbent_text"]
        original = "The encoder reads the configured input."
        start = incumbent.index(original)
        issue = request.input_payload["issues"][0]
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "rewrite:qualifier-binding",
                    "section_id": request.input_payload["section_context"]["section_id"],
                    "start": start,
                    "end": start + len(original),
                    "original_text": original,
                    "replacement_text": (
                        "The encoder reads the configured input when the chunk "
                        "identifiers match ("
                        "`doc['chunk_id'] == query['chunk_id']`)."
                    ),
                    "issue_ids": [issue["sentence_id"]],
                    "allowed_scope": "wording_only",
                }],
                "self_identified_risks": [],
                "incomplete": False,
            }),
            response_hash="sha256:rewrite-qualifier-binding",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=rewrite_caller,
    )
    assert "publication_rewrite_transitions_v1" not in outputs
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "The encoder reads the configured input." in candidate
    validation = json.loads(Path(outputs["text_evidence_validation"]).read_text())
    assert validation["status"] != "passed"
    assert result.status != "blocked"


def test_published_06_authoring_bundle_is_self_resolving(tmp_path: Path) -> None:
    """R3: the final published callback bundle under 06_authoring/ must
    resolve every file-backed artifact from ITS OWN directory and keep every
    digest valid — the replay input bundle and the published hand-off are
    different locations with different relative refs."""
    from code2paper.agentic.publication_method_writer import (
        _callback_artifact_prompt_payload,
        _read_verified_callback_bundle,
        fulfill_writing_research_callbacks,
    )

    paths = _artifacts(tmp_path)
    completeness = _with_unverified_gap(paths)
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )
    out_root = tmp_path / "out"
    evidence_dir = out_root / "research_tool_data" / "callbacks"
    evidence_dir.mkdir(parents=True)
    evidence = evidence_dir / "author-confirmation.json"
    evidence.write_text('{"objective":"use the verified feature path"}\n', encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(evidence.read_bytes()).hexdigest()

    def first_caller(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        move_authority = request.input_payload["grounding_contract"]["move_authority"]
        limitations = move_authority["limitations_or_mismatch"]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [{
                    "request_id": "request:MA-S1:limitations_or_mismatch",
                    "section_id": section_id,
                    "argument_unit_id": binding["used_argument_unit_ids"][0],
                    "missing_rhetorical_move": "limitations_or_mismatch",
                    "exact_question": "Which validated artifact resolves the unverified gap?",
                    "required_authority_lane": "executable_hard",
                    "candidate_symbols_or_terms": list(
                        limitations.get("candidate_symbols_or_terms", ())
                    ),
                    "why_needed_for_reader": "Close the remaining behavior gap.",
                    "priority": "high",
                }],
            }),
            response_hash="sha256:writer-callback",
            finish_reason="stop",
        )

    first, first_outputs = run_publication_method_writer(
        out_root=out_root,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=first_caller,
        rebuild_architect_plan=True,
    )
    assert first.status == "incomplete"
    input_bundle_path = Path(first_outputs["writing_research_callback_artifacts_v1"])
    assert input_bundle_path.parent.name == "06_authoring"
    # Phase 2 input: fulfill the open request with a file-backed artifact
    # whose ref resolves from the input bundle's own directory.  The
    # artifact binding must match the request exactly.
    emitted_request = next(
        item for item in json.loads(input_bundle_path.read_text())["requests"]
        if item["request_id"] == "request:MA-S1:limitations_or_mismatch"
    )
    artifact = WritingResearchCallbackArtifactV1(
        artifact_id="artifact:author-confirmation",
        request_id=emitted_request["request_id"],
        section_id=emitted_request["section_id"],
        argument_unit_id=emitted_request["argument_unit_id"],
        authority_lane=emitted_request["required_authority_lane"],
        artifact_ref="../../research_tool_data/callbacks/author-confirmation.json",
        artifact_digest=digest,
        validated=True,
    )
    fulfilled = fulfill_writing_research_callbacks(
        input_bundle_path,
        {"request:MA-S1:limitations_or_mismatch": (artifact,)},
    )
    assert fulfilled.requests[0].status == "fulfilled"
    paths["writing_research_callback_artifacts_v1"] = str(input_bundle_path)

    def resume_caller(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-consume-callback",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=out_root,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=resume_caller,
        resume_section_ids=("MA-S1",),
    )
    assert result.status != "blocked"
    published_path = Path(outputs["writing_research_callback_artifacts_v1"])
    assert published_path.parent.name == "06_authoring"
    published = json.loads(published_path.read_text(encoding="utf-8"))
    (published_artifact,) = published["artifacts"]["request:MA-S1:limitations_or_mismatch"]
    # The published ref must resolve from the 06_authoring directory.
    resolved = (published_path.parent / published_artifact["artifact_ref"]).resolve()
    assert resolved == evidence.resolve(), published_artifact["artifact_ref"]
    # The published bundle is digest-valid and its preview loads.
    loaded = _read_verified_callback_bundle(published_path)
    (loaded_artifact,) = loaded.artifacts["request:MA-S1:limitations_or_mismatch"]
    preview_payload, failure = _callback_artifact_prompt_payload(
        loaded_artifact,
        base_dir=published_path.parent,
    )
    assert failure == "", failure
    assert preview_payload["artifact_preview"].startswith('{"objective"')


def test_body_structure_defects_are_detected_for_rewrite() -> None:
    """R4: trailing dangling conjunctions, unbalanced body parentheses and
    doubled-whitespace heading-tail fusion are typed Rewrite issues; a clean
    body produces none."""
    from code2paper.agentic.publication_method_writer import (
        _malformed_punctuation_issues_by_section,
    )

    trailing = _leakage_output(
        markdown="## Encoder\n\nThe encoder reads the input and  ",
    )
    codes = [
        issue.sentence_id
        for issue in _malformed_punctuation_issues_by_section({"section-a": trailing})["section-a"]
    ]
    assert any("body-ends-with-dangling-conjunction" in code for code in codes), codes

    unbalanced = _leakage_output(
        markdown=(
            "## Encoder\n\nThis includes the intended (Intended: partial design."
        ),
    )
    codes = [
        issue.sentence_id
        for issue in _malformed_punctuation_issues_by_section({"section-a": unbalanced})["section-a"]
    ]
    assert any("body-unbalanced-parenthesis" in code for code in codes), codes

    fused = _leakage_output(
        markdown=(
            "## Encoder\n\ncontain/message adjacency  offline tri-graph "
            "construction is defined."
        ),
    )
    codes = [
        issue.sentence_id
        for issue in _malformed_punctuation_issues_by_section({"section-a": fused})["section-a"]
    ]
    assert any("body-doubled-whitespace" in code for code in codes), codes

    clean = _leakage_output(
        markdown="## Encoder\n\nThe encoder reads the configured input.",
    )
    assert _malformed_punctuation_issues_by_section({"section-a": clean}) == {}


def test_section_ending_in_dangling_conjunction_is_repaired_and_editable(
    tmp_path: Path,
) -> None:
    """R4 product-level: a section body ending in a dangling conjunction is
    routed to Rewrite; the accepted patch leaves every planned section
    content-bearing and editable."""
    paths = _two_section_plan(tmp_path)

    def writer_caller(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        body = (
            "## Encoder\n\nThe encoder reads the configured input."
            if section_id == "MA-S1"
            else (
                "## Output interface\n\nIts representation is returned to the "
                "downstream stage and "
            )
        )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": body,
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash=f"sha256:writer:{section_id}",
            finish_reason="stop",
        )

    def rewrite_caller(_config, request):
        incumbent = request.input_payload["incumbent_text"]
        original = "Its representation is returned to the downstream stage and "
        start = incumbent.index(original)
        issue = request.input_payload["issues"][0]
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "rewrite:dangling-and",
                    "section_id": request.input_payload["section_context"]["section_id"],
                    "start": start,
                    "end": start + len(original),
                    "original_text": original,
                    "replacement_text": "Its representation is returned to the "
                    "downstream stage.",
                    "issue_ids": [issue["sentence_id"]],
                    "allowed_scope": "wording_only",
                }],
                "self_identified_risks": [],
                "incomplete": False,
            }),
            response_hash="sha256:rewrite-dangling-and",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=rewrite_caller,
    )
    quality = json.loads(Path(
        outputs["publication_quality_report_v1"]
    ).read_text())
    assert quality["utility"]["editable_section_rate"] == 1.0
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "and " not in candidate.split("## Output interface")[1].splitlines()[-1]
    assert "Its representation is returned to the downstream stage." in candidate
    assert result.status != "blocked"


# ---------------------------------------------------------------------------
# Q0 — candidate durability and independent status fields (plan 19.4)
# ---------------------------------------------------------------------------


def test_candidate_survives_validation_warnings_with_exact_best_draft(
    tmp_path: Path,
) -> None:
    """Unsupported/qualifier warnings never erase the durable candidate; the
    published file equals the incumbent best draft and the four statuses are
    reported independently.
    """
    import code2paper.agentic.publication_method_writer as writer_module

    paths = _artifacts(tmp_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-best-draft",
            finish_reason="stop",
        )

    with patch.object(
        writer_module,
        "_maybe_validate_final_text",
        return_value=("failed", {}),
    ):
        result, outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=caller,
        )

    assert result.status == "incomplete"
    assert result.candidate_generation_status == "generated"
    assert result.candidate_available is True
    assert result.candidate_validation_status == "warnings"
    assert result.verified_validation_status == "incomplete"
    assert result.publication_ready is False
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "The encoder reads the configured input." in candidate
    checkpoint = json.loads(Path(outputs["publication_candidate_checkpoint_v1"]).read_text())
    assert checkpoint["final_text_digest"] == result.final_text_digest
    assert checkpoint["final_text"] == candidate
    assert result.candidate_warnings_by_severity["critical"] >= 0


def test_validator_exception_keeps_durable_candidate_and_reports_error(
    tmp_path: Path,
) -> None:
    """A validator exception is an error state, never an erasure: the candidate
    is preserved, Verified is not guessed, and an actionable review item is
    written.
    """
    import code2paper.agentic.publication_method_writer as writer_module

    paths = _artifacts(tmp_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-durable",
            finish_reason="stop",
        )

    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated validator crash")

    with patch.object(writer_module, "_maybe_validate_final_text", boom):
        result, outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=caller,
        )

    assert result.status == "incomplete"
    assert result.candidate_available is True
    assert result.candidate_validation_status == "error"
    assert result.verified_validation_status == "error"
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert candidate.strip()
    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    assert any(item["status"] == "validator_error" for item in review["items"])
    quality = json.loads(Path(outputs["publication_quality_report_v1"]).read_text())
    assert quality["safety"]["final_text_validation_status"] == "error"
    assert any(issue["code"] == "final_text_validation_error" for issue in quality["issues"])


def test_generation_failure_with_no_body_never_publishes_empty_placeholder(
    tmp_path: Path,
) -> None:
    """A run that never produces non-empty authored sections is an honest
    generation failure: no candidate file, no empty placeholder, and
    candidate_available=false.
    """
    paths = _artifacts(tmp_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-empty",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "blocked"
    assert result.candidate_available is False
    assert result.candidate_generation_status == "failed"
    assert "publication_candidate_method" not in outputs


def test_editor_empty_section_output_keeps_writer_incumbent(tmp_path: Path) -> None:
    """Q0 transaction rule: an Editor patch that empties a section is rejected;
    the durable candidate and checkpoint keep the Writer incumbent.
    """
    paths = _two_section_plan(tmp_path)

    def editor_caller(_config, request):
        sections = request.input_payload["sections"]
        before = sections["MA-S2"]
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "editor:MA-S2",
                    "section_id": "MA-S2",
                    "before_digest": "sha256:" + hashlib.sha256(before.encode()).hexdigest(),
                    "replacement_text": "",
                    "generation_source": "editor",
                    "reason": "Empty the section.",
                    "scoped": True,
                }],
            }),
            response_hash="sha256:editor-empty",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_two_section_writer_caller,
        editor_caller=editor_caller,
    )

    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "Its representation is returned to the downstream stage." in candidate
    checkpoint = json.loads(Path(outputs["publication_candidate_checkpoint_v1"]).read_text())
    assert "Its representation is returned to the downstream stage." in checkpoint["final_text"]
    assert checkpoint["final_text"] == candidate


def test_status_fields_are_independent_on_warning_run(tmp_path: Path) -> None:
    """candidate_available, warnings, verified status and publication_ready
    never collapse into one legacy enum.
    """
    import code2paper.agentic.publication_method_writer as writer_module

    paths = _artifacts(tmp_path)

    def caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-independent",
            finish_reason="stop",
        )

    with patch.object(
        writer_module,
        "_maybe_validate_final_text",
        return_value=("failed", {}),
    ):
        result, outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=caller,
        )

    # Generation vs validation vs verified vs publication readiness.
    assert result.candidate_generation_status == "generated"
    assert result.candidate_available is True
    assert result.candidate_validation_status == "warnings"
    assert result.verified_validation_status == "incomplete"
    assert result.publication_ready is False
    payload = json.loads(Path(outputs["publication_writer_result_v1"]).read_text())
    assert payload["candidate_available"] is True
    assert payload["candidate_validation_status"] == "warnings"
    assert payload["verified_validation_status"] == "incomplete"
    assert payload["publication_ready"] is False
    # A warning run is a legal terminal state: the candidate survives.
    assert result.status == "incomplete"


# ---------------------------------------------------------------------------
# Q1 — publication relevance and exact conditions (plan 19.5)
# ---------------------------------------------------------------------------


def test_audit_only_claims_do_not_count_as_supported_recall_obligations(
    tmp_path: Path,
) -> None:
    from code2paper.agentic.method_proposition_models import (
        MethodPropositionSetV1,
        MethodPropositionV1,
        PropositionBindingSidecarV1,
        PropositionBindingV1,
    )

    plan = _quality_plan(claims=("claim-a",))
    completeness = _quality_completeness(claim_ids=("claim-a",))
    completeness = completeness.model_copy(update={
        "items": (*completeness.items, MethodCompletenessItemV1(
            obligation_id="obl-audit",
            status="supported_by_repository",
            claim_ids=("claim-audit-only",),
        )),
    })
    audit_proposition = MethodPropositionV1(
        proposition_id="MP-AUDIT", origin="repository_evidence",
        evidence_lane="repository_verified", may_enter_verified=True,
        reader_subject="the loss reduction",
        transformation="branches when the loss tensor is empty",
        writing_role="audit_only",
    )
    sidecar = PropositionBindingSidecarV1(
        repo_snapshot_id="repo:writer", project_tree_hash="sha256:tree",
        bindings=(PropositionBindingV1(
            proposition_id="MP-AUDIT",
            claim_ids=("claim-audit-only",),
            fact_ids=("fact-audit",),
            span_ids=("span-audit",),
        ),),
    )
    prop_set = MethodPropositionSetV1(
        repo_snapshot_id="repo:writer", project_tree_hash="sha256:tree",
        propositions=(audit_proposition,),
        binding_sidecar_digest=sidecar.content_digest,
    )
    output = PublicationMethodSectionOutputV1(
        section_id=plan.sections[0].section_id,
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=list(plan.sections[0].argument_unit_ids),
        used_claim_ids=["claim-a"],
        completed_rhetorical_moves=_COMPLETED_CORE_MOVES,
    )
    ledger = ledger_from_section_outputs(
        output.section_markdown,
        ((output.section_id, output.section_markdown, "sha256:writer-audit"),),
    )

    report = evaluate_publication_method_quality(
        final_text=output.section_markdown,
        plan=plan,
        completeness=completeness,
        section_outputs=(output,),
        ledger=ledger,
        propositions=prop_set,
        proposition_bindings=sidecar,
    )

    # The audit-only row is not a Method obligation: no missing-graph issue
    # and recall is not diluted by evidence-audit content.
    assert report.utility.completeness_coverage == 1.0
    assert not any(
        issue.code == "supported_unit_missing_from_argument_graph"
        for issue in report.issues
    )


def test_qualifier_terms_exclude_audit_only_claims() -> None:
    from code2paper.agentic.publication_method_writer import _qualifier_terms_by_section

    plan = _quality_plan(claims=("claim-audit",))
    claim = _quality_claim("claim-audit").model_copy(update={
        "required_qualifiers": ["loss_i.shape[0] == 0"],
    })
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo", project_tree_hash="tree",
        evidence_packet_digest="sha256:p", code_fact_digest="sha256:f",
        claims=[claim], content_digest="sha256:claims",
    )
    full = _qualifier_terms_by_section(plan=plan, claims=claims)
    assert full.get("section-a") == ("loss_i.shape[0] == 0",)
    filtered = _qualifier_terms_by_section(
        plan=plan,
        claims=claims,
        exclude_claim_ids={"claim-audit"},
    )
    assert "section-a" not in filtered


def test_writer_emits_section_formalization_with_packages_or_disposition(
    tmp_path: Path,
) -> None:
    """Q2: every section ends with formula packages or a typed disposition;
    the Writer payload carries the reader-facing formula surface.
    """
    paths = _artifacts(tmp_path)
    seen_payloads: list[dict] = []

    def caller(_config, request):
        seen_payloads.append(request.input_payload)
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-formalization",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    section_path = outputs.get("formalization_section_results_v1")
    assert section_path
    payload = json.loads(Path(section_path).read_text())
    assert payload["sections"]
    for section in payload["sections"]:
        has_packages = bool(section.get("packages"))
        has_disposition = section.get("disposition") is not None
        assert has_packages or has_disposition
        assert not (has_packages and has_disposition)
    # The Writer payload always carries the reader-facing formula surface.
    assert seen_payloads
    assert "formula_packages" in seen_payloads[0]
    # A typed disposition surfaces as an actionable review item.
    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    assert any("review-formalization:" in item["candidate_id"] for item in review["items"])


# ---------------------------------------------------------------------------
# Q4 — bounded gain-based revision loop (plan 19.8)
# ---------------------------------------------------------------------------


def test_revision_loop_fixes_all_issues_and_stops_before_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Q4: one rewrite round that resolves every typed issue stops the loop;
    the second budget slot is never spent on unchanged input.
    """
    monkeypatch.setenv("CODE2PAPER_SECTION_REVISION_BUDGET", "2")
    monkeypatch.setenv("CODE2PAPER_LOCAL_REWRITE_MAX_ATTEMPTS", "2")
    paths = _artifacts(tmp_path)
    calls: list[tuple[str, int]] = []

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": (
                    "## Encoder\n\nself._a computes the input; self._b computes the input; "
                    "self._c computes the input."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-q4-trace",
            finish_reason="stop",
        )

    def rewrite_caller(_config, request):
        incumbent = request.input_payload["incumbent_text"]
        issues = request.input_payload["issues"]
        issue = issues[0] if issues else {}
        calls.append((str(issue.get("failure_type", "")), int(request.input_payload["section_context"].get("attempt", 1))))
        fixed = incumbent.replace(
            "self._a computes the input; self._b computes the input; self._c computes the input.",
            "The encoder reads the configured input.",
            1,
        )
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "rewrite:q4-fix-all",
                    "section_id": request.input_payload["section_context"]["section_id"],
                    "start": 0,
                    "end": len(incumbent),
                    "original_text": incumbent,
                    "replacement_text": fixed,
                    "issue_ids": [issue.get("sentence_id", "s0")],
                    "allowed_scope": "wording_only",
                }],
                "self_identified_risks": [],
                "incomplete": False,
            }),
            response_hash=f"sha256:rewrite-q4:{len(calls)}",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=rewrite_caller,
    )

    # Round 1 spends one style-owned pass; FAC/claim clusters no longer
    # consume Rewrite.  The applied style patch also renders the claim.
    assert len(calls) == 1
    assert calls[0][0] == "method_language_style"
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "The encoder reads the configured input." in candidate
    assert "self._a" not in candidate
    assert result.status in {"incomplete", "success"}


def test_revision_budget_caps_rewrite_rounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Q4: the configured budget caps the number of rewrite rounds even when
    a typed issue remains unfixable; the durable candidate is preserved.
    """
    monkeypatch.setenv("CODE2PAPER_LOCAL_REWRITE_MAX_ATTEMPTS", "2")
    paths = _artifacts(tmp_path)

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": (
                    "## Encoder\n\nself._a computes the input; self._b computes the input; "
                    "self._c computes the input."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-q4-cap",
            finish_reason="stop",
        )

    def make_rewrite_caller(calls: list[str]):
        def rewrite_caller(_config, request):
            incumbent = request.input_payload["incumbent_text"]
            issues = request.input_payload["issues"]
            issue = issues[0] if issues else {}
            calls.append(str(issue.get("failure_type", "")))
            # Only the style cluster can gain: replace the raw fragments with
            # clean prose but never render the missing supported claim.
            fixed = incumbent.replace(
                "self._a computes the input; self._b computes the input; self._c computes the input.",
                "The encoder computes the input.",
                1,
            )
            return LLMResponse(
                text=json.dumps({
                    "patches": [{
                        "patch_id": "rewrite:q4-style-only",
                        "section_id": request.input_payload["section_context"]["section_id"],
                        "start": 0,
                        "end": len(incumbent),
                        "original_text": incumbent,
                        "replacement_text": fixed,
                        "issue_ids": [issue.get("sentence_id", "s0")],
                        "allowed_scope": "wording_only",
                    }],
                    "self_identified_risks": [],
                    "incomplete": False,
                }),
                response_hash=f"sha256:rewrite-q4-cap:{len(calls)}",
                finish_reason="stop",
            )
        return rewrite_caller

    budget1_calls: list[str] = []
    monkeypatch.setenv("CODE2PAPER_SECTION_REVISION_BUDGET", "1")
    _result1, _outputs1 = run_publication_method_writer(
        out_root=tmp_path / "b1",
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=make_rewrite_caller(budget1_calls),
    )
    assert len(budget1_calls) == 1
    assert budget1_calls == ["method_language_style"]

    budget3_calls: list[str] = []
    monkeypatch.setenv("CODE2PAPER_SECTION_REVISION_BUDGET", "3")
    _result3, _outputs3 = run_publication_method_writer(
        out_root=tmp_path / "b3",
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=make_rewrite_caller(budget3_calls),
    )
    # Style-owned rewrite is capped at one pass; FAC/claim clusters no
    # longer consume Rewrite rounds.
    assert budget3_calls == ["method_language_style"]
    candidate = Path(_outputs3["publication_candidate_method"]).read_text()
    assert "self._a" not in candidate


def test_revision_loop_stops_on_no_progress_without_budget_waste(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Q4: a round that applies no patch stops the loop immediately; the
    durable candidate keeps the incumbent text.
    """
    monkeypatch.setenv("CODE2PAPER_SECTION_REVISION_BUDGET", "3")
    paths = _artifacts(tmp_path)
    calls: list[str] = []

    def writer_caller(_config, request):
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-q4-clean",
            finish_reason="stop",
        )

    def rewrite_caller(_config, request):
        calls.append(request.input_payload.get("incumbent_text", ""))
        return LLMResponse(
            text=json.dumps({
                "patches": [],
                "self_identified_risks": [],
                "incomplete": False,
            }),
            response_hash="sha256:rewrite-q4-nop",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=writer_caller,
        rewrite_caller=rewrite_caller,
    )

    # No style/validation issues: the rewrite owner is never invoked at all.
    assert calls == []
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "The encoder reads the configured input." in candidate
    checkpoint = json.loads(Path(outputs["publication_candidate_checkpoint_v1"]).read_text())
    assert checkpoint["final_text"] == candidate


def test_heading_anchor_leak_is_detected_and_routed() -> None:
    from code2paper.agentic.publication_method_writer import (
        _READER_FACING_INTERNAL_ID_PATTERNS,
        _reader_facing_leakage_issues_by_section,
    )

    text = "## Second retrieval stage: passage retrieval (hybrid passage) {#MA-S3:purpose}\n\nBody text."
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S3",
        section_markdown=text,
    )
    assert any(
        pattern.search(text) is not None
        for pattern in _READER_FACING_INTERNAL_ID_PATTERNS
    )
    issues = _reader_facing_leakage_issues_by_section({"MA-S3": output})
    assert issues.get("MA-S3")
    assert any(
        "harness-internal" in str(issue) or "internal id" in str(issue)
        for issue in issues["MA-S3"]
    )


# ---------------------------------------------------------------------------
# R1 — publication relevance on the Concept-card main lane
# ---------------------------------------------------------------------------


def test_audit_only_concept_card_excluded_from_view_with_story_override() -> None:
    from code2paper.agentic.method_concept_card_models import MethodConceptCardV1
    from code2paper.agentic.writer_view_projection import build_writer_view_from_concept_cards

    audit_card = MethodConceptCardV1(
        concept_key="CK-PAD", authority_lane="repository",
        method_subject="first-hop sequence padding",
        operation="pads and aligns source and destination first-hop interaction sequences",
        inputs=("sequences",), outputs=("aligned sequences",),
        may_enter_verified=True,
    )
    visible = build_writer_view_from_concept_cards(
        heading="H", reader_question="Q?", section_goal="G",
        cards=[audit_card], callback_opportunities=[],
    )
    assert visible.allowed_concept_keys == ("CK-PAD",)
    filtered = build_writer_view_from_concept_cards(
        heading="H", reader_question="Q?", section_goal="G",
        cards=[audit_card], callback_opportunities=[],
        exclude_audit_only=True,
    )
    assert filtered.allowed_concept_keys == ()
    assert filtered.positive_concepts == ()
    overridden = build_writer_view_from_concept_cards(
        heading="H", reader_question="Q?", section_goal="G",
        cards=[audit_card], callback_opportunities=[],
        exclude_audit_only=True,
        audit_override_concept_keys=frozenset({"CK-PAD"}),
    )
    assert overridden.allowed_concept_keys == ("CK-PAD",)


def test_story_override_derived_from_frozen_story_spine() -> None:
    """Review Q1: the production story override comes from the frozen
    author-story spine (placement), never from project-specific code.

    A card classified audit_only by its surface is re-admitted when its
    story_node matches a spine node id or title; a card not named by the
    spine stays filtered.
    """

    from code2paper.agentic.method_concept_card_models import (
        MethodConceptCardSetV1,
        MethodConceptCardV1,
    )
    from code2paper.agentic.method_product_models import AuthorStoryNodeV1
    from code2paper.agentic.publication_relevance import (
        story_override_concept_keys,
    )

    audit_card = MethodConceptCardV1(
        concept_key="CK-PAD", authority_lane="repository",
        method_subject="first-hop sequence padding",
        operation="pads first-hop interaction sequences to a uniform length",
        story_node="Story:Alignment",
        may_enter_verified=True,
    )
    other_card = MethodConceptCardV1(
        concept_key="CK-CACHE", authority_lane="repository",
        method_subject="tensor cache existence",
        operation="caches intermediate tensors",
        story_node="Story:Unaligned",
        may_enter_verified=True,
    )
    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        cards=[audit_card, other_card],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id="story:alignment",
            title="Story:Alignment",
            author_statement="Alignment of first-hop sequences.",
            intended_role="algorithm_step",
        ),
    ]
    override = story_override_concept_keys(card_set, spine)
    assert override == frozenset({"CK-PAD"})
    # No spine -> no override (deterministic classifier remains the only
    # relevance authority).
    assert story_override_concept_keys(card_set, ()) == frozenset()


def test_audit_only_concept_claims_never_trigger_qualifier_repair() -> None:
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardBindingV1,
        MethodConceptCardSetV1,
        MethodConceptCardV1,
    )
    from code2paper.agentic.publication_method_writer import _audit_only_claim_ids

    card = MethodConceptCardV1(
        concept_key="CK-PAD", authority_lane="repository",
        method_subject="first-hop padding",
        operation="pads first-hop sequences to a uniform length",
        may_enter_verified=True,
    )
    # Review Q1: the audit exclusion binds through EXACT bound fragments,
    # never through source obligations.  The audit card pins span
    # span:encoder.py:1:2; fact-a (the claim's fact) lives on that span.
    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        cards=[card],
        bindings=[ConceptCardBindingV1(
            concept_key="CK-PAD",
            source_obligation_ids=("obl-pad",),
            source_span_ids=("span:encoder.py:1:2",),
        )],
    )
    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact-a", subject="sym:pad", predicate="aggregates",
            object="sequences", scope="sym:pad",
            direct_span_ids=["span:encoder.py:1:2"],
            exact_source_digest="sha256:s", canonical_identity="sha256:f",
            validation_status="supported",
        )],
        content_digest="sha256:facts",
    )
    claim = _quality_claim("claim-pad").model_copy(update={
        "covers_obligation_ids": ["obl-pad"],
    })
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets", code_fact_digest="sha256:facts",
        claims=[claim], content_digest="sha256:claims",
    )
    audit_ids = _audit_only_claim_ids(
        propositions=None,
        proposition_bindings=None,
        concept_cards=card_set,
        audit_concept_keys=frozenset({"CK-PAD"}),
        claims=claims,
        facts=facts,
    )
    assert "claim-pad" in audit_ids
    none = _audit_only_claim_ids(
        propositions=None,
        proposition_bindings=None,
        concept_cards=card_set,
        audit_concept_keys=frozenset(),
        claims=claims,
        facts=facts,
    )
    assert none == set()
    # A claim that shares the audit card's SOURCE OBLIGATION but whose fact
    # is bound to a different span is NOT excluded (no obligation-wide
    # expansion — review Q1).
    material_claim = _quality_claim("claim-material").model_copy(update={
        "covers_obligation_ids": ["obl-pad"],
        "fact_ids": ["fact-material"],
        "direct_evidence_ids": ["span:encoder.py:50:60"],
    })
    material_fact = CodeFactV1(
        fact_id="fact-material", subject="sym:score", predicate="computes_formula",
        object="score", scope="sym:score",
        direct_span_ids=["span:encoder.py:50:60"],
        exact_source_digest="sha256:m", canonical_identity="sha256:fm",
        validation_status="supported",
    )
    material_claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets", code_fact_digest="sha256:facts",
        claims=[material_claim], content_digest="sha256:claims2",
    )
    material_facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[material_fact], content_digest="sha256:facts2",
    )
    audit_ids_exact = _audit_only_claim_ids(
        propositions=None,
        proposition_bindings=None,
        concept_cards=card_set,
        audit_concept_keys=frozenset({"CK-PAD"}),
        claims=material_claims,
        facts=material_facts,
    )
    assert "claim-material" not in audit_ids_exact


# ---------------------------------------------------------------------------
# R2 — product Formalizer vertical (section-scoped packages, real rendering)
# ---------------------------------------------------------------------------


def test_formula_centric_section_binds_equations_via_claims_facts(tmp_path: Path) -> None:
    from code2paper.agentic.equation_claims import (
        EquationClaimSetV1,
        EquationClaimV1,
        EquationSymbolBindingV1,
    )
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
    from code2paper.agentic.publication_method_writer import _run_section_formalizer

    fact = CodeFactV1(
        fact_id="fact-a", subject="sym:score", predicate="computes_formula",
        object="score", scope="sym:score", direct_span_ids=["span:1"],
        exact_source_digest="sha256:s", canonical_identity="sha256:f",
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:p", facts=[fact],
        content_digest="sha256:facts",
    )
    equation = EquationClaimV1(
        equation_id="eq:score", expression="s = w x + b", fact_ids=["fact-a"],
        operation_descriptors=["inference score"],
        symbol_bindings=[
            EquationSymbolBindingV1(symbol="s", operand_role="result", operand_value="score", fact_id="fact-a"),
            EquationSymbolBindingV1(symbol="w", operand_role="object", operand_value="weights", fact_id="fact-a"),
            EquationSymbolBindingV1(symbol="x", operand_role="object", operand_value="features", fact_id="fact-a"),
            EquationSymbolBindingV1(symbol="b", operand_role="object", operand_value="bias", fact_id="fact-a"),
        ],
        canonical_identity="sha256:eq", validation_status="supported",
    )
    equations = EquationClaimSetV1(
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts", equations=[equation],
        content_digest="sha256:eqs",
    )
    # The plan unit carries NO equation ids, only the claim whose fact
    # binds the equation: the R2 derivation must still find it.
    plan = _quality_plan(claims=("claim-a",))
    claim = _quality_claim("claim-a")
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q", project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:p", code_fact_digest="sha256:facts",
        claims=[claim], content_digest="sha256:claims",
    )
    results, _path = _run_section_formalizer(
        out_root=tmp_path,
        plan=plan,
        equations=equations,
        facts=facts,
        claims=claims,
        propositions=None,
        proposition_bindings=None,
        concept_cards=None,
        llm_config=_config(),
        caller=None,
    )
    result = results[0]
    assert result.disposition is None
    assert result.packages
    assert result.packages[0].authority_status == "code_verified"
    assert result.packages[0].latex == "s = w x + b"
    assert result.packages[0].symbol_definitions


def test_operation_evidence_routes_a_no_equation_section_to_code_lane(
    tmp_path: Path,
) -> None:
    from code2paper.agentic.publication_method_writer import _run_section_formalizer

    base_plan = _quality_plan(claims=("claim-a",))
    obligation_id = "formula:section:section-a:derivation"
    paragraph = SectionParagraphPlanV1(
        paragraph_id="paragraph:section-a:formula",
        paragraph_role="formula",
        argument_unit_ids=("unit-a",),
        formula_obligation_ids=(obligation_id,),
    )
    graph = base_plan.sections[0].model_copy(update={
        "paragraphs": (paragraph,),
        "formula_obligation_ids": (obligation_id,),
    })
    plan = base_plan.model_copy(update={"sections": (graph,)})
    facts = CodeFactSetV1(
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact:score",
            subject="score",
            predicate="computes",
            object="score",
            scope="sym:score",
            direct_span_ids=["span:model.py:1:2"],
            exact_source_digest="sha256:source",
            canonical_identity="sha256:fact-score",
        )],
        content_digest="sha256:facts2",
    )
    equations = EquationClaimSetV1(
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts2",
        equations=[],
        content_digest="sha256:eqs2",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts2",
        claims=[_quality_claim()],
        content_digest="sha256:claims",
    )
    requests = []

    def caller(_config, request):
        requests.append(request)
        return LLMResponse(
            text=json.dumps({
                "outcome": "rendered",
                "section_id": "section-a",
                "packages": [{
                    "package_id": "package:operation",
                    "satisfied_obligation_ids": [obligation_id],
                    "consumer_paragraph_id": "paragraph:section-a:formula",
                    "purpose": "State the source addition.",
                    "latex": "s = w + x",
                    "prose_explanation": "The operation adds the two inputs.",
                    "authority_status": "code_verified",
                    "bound_fact_ids": ["fact:score"],
                }],
            }),
            response_hash="sha256:formalizer",
        )

    results, trace_path = _run_section_formalizer(
        out_root=tmp_path,
        plan=plan,
        equations=equations,
        facts=facts,
        claims=claims,
        propositions=None,
        proposition_bindings=None,
        concept_cards=None,
        llm_config=_config(),
        caller=caller,
        require_llm_call=True,
        research_dossiers=(SimpleNamespace(
            dossier_id="dossier:operation",
            section_id="section-a",
            fact_ids=("fact:score",),
            exact_span_ids=("span:model.py:1:2",),
            operation_atoms=({
                "node_id": "node:add",
                "fact_id": "fact:score",
                "predicate": "COMPUTE",
                "operands": ["w", "x"],
                "result": "s",
                "diagnostics": ["add"],
                "source_span_id": "span:model.py:1:2",
            },),
            unresolved_relations=(),
            ordered_operation_node_ids=("node:add",),
            call_path_relation_ids=(),
            data_flow_relation_ids=(),
            configuration_bindings=(),
            default_activation="active",
            active_path_conditions=(),
            exact_excerpts=(),
            author_statements=(),
        ),),
    )

    assert len(requests) == 1
    assert requests[0].input_payload["core_equations"] == []
    assert requests[0].input_payload["evidence_packs"]
    assert results[0].packages[0].authority_status == "code_verified"
    assert results[0].packages[0].package_id == "package:operation"
    assert results[0].packages[0].latex == "s = w + x"
    assert not results[0].packages[0].package_id.startswith("opfp:")
    trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    assert trace["formalizer_call_traces"][0]["operation_evidence_lane"] is True
    assert any(
        str(item).startswith("opfp:")
        for item in trace["formalizer_call_traces"][0].get(
            "operation_audit_package_ids", ()
        )
    )


def test_code_shaped_operation_formula_is_not_a_candidate_display_package(
    tmp_path: Path,
) -> None:
    from code2paper.agentic.publication_method_writer import _run_section_formalizer

    base_plan = _quality_plan(claims=("claim-a",))
    obligation_id = "formula:section:section-a:derivation"
    paragraph = SectionParagraphPlanV1(
        paragraph_id="paragraph:section-a:formula",
        paragraph_role="formula",
        argument_unit_ids=("unit-a",),
        formula_obligation_ids=(obligation_id,),
    )
    graph = base_plan.sections[0].model_copy(update={
        "paragraphs": (paragraph,),
        "formula_obligation_ids": (obligation_id,),
    })
    plan = base_plan.model_copy(update={"sections": (graph,)})
    facts = CodeFactSetV1(
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact:score",
            subject="score",
            predicate="computes",
            object="score",
            scope="sym:score",
            direct_span_ids=["span:model.py:1:2"],
            exact_source_digest="sha256:source",
            canonical_identity="sha256:fact-score",
        )],
        content_digest="sha256:facts2",
    )
    equations = EquationClaimSetV1(
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts2",
        equations=[],
        content_digest="sha256:eqs2",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts2",
        claims=[_quality_claim()],
        content_digest="sha256:claims",
    )

    def caller(_config, request):
        return LLMResponse(
            text=json.dumps({
                "outcome": "rendered",
                "section_id": "section-a",
                "packages": [{
                    "package_id": "package:python",
                    "satisfied_obligation_ids": [obligation_id],
                    "consumer_paragraph_id": "paragraph:section-a:formula",
                    "purpose": "State the source addition.",
                    "latex": (
                        "(relevance_scores, indices) = "
                        r"\operatorname{sort}(similarities, dim=1, descending=True)"
                    ),
                    "prose_explanation": "Sort the scores.",
                    "authority_status": "code_verified",
                    "bound_fact_ids": ["fact:score"],
                }],
            }),
            response_hash="sha256:formalizer-code",
        )

    results, _trace_path = _run_section_formalizer(
        out_root=tmp_path,
        plan=plan,
        equations=equations,
        facts=facts,
        claims=claims,
        propositions=None,
        proposition_bindings=None,
        concept_cards=None,
        llm_config=_config(),
        caller=caller,
        require_llm_call=True,
        research_dossiers=(SimpleNamespace(
            dossier_id="dossier:operation",
            section_id="section-a",
            fact_ids=("fact:score",),
            exact_span_ids=("span:model.py:1:2",),
            operation_atoms=({
                "node_id": "node:add",
                "fact_id": "fact:score",
                "predicate": "COMPUTE",
                "operands": ["w", "x"],
                "result": "s",
                "diagnostics": ["add"],
                "source_span_id": "span:model.py:1:2",
            },),
            unresolved_relations=(),
            ordered_operation_node_ids=("node:add",),
            call_path_relation_ids=(),
            data_flow_relation_ids=(),
            configuration_bindings=(),
            default_activation="active",
            active_path_conditions=(),
            exact_excerpts=(),
            author_statements=(),
        ),),
    )
    assert not any(
        str(getattr(package, "package_id", "")).startswith("opfp:")
        for package in results[0].packages
    )
    assert not any(
        "descending" in str(getattr(package, "latex", ""))
        for package in results[0].packages
    )


def test_operation_evidence_compiles_non_arithmetic_sort_signature() -> None:
    from code2paper.agentic.formalization_agent import (
        MechanismEquationEvidencePackV1,
        MethodFormulaObligationV2,
        build_deterministic_operation_formula_packages,
        validate_section_formula_package,
    )
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1

    obligation = MethodFormulaObligationV2(
        obligation_id="formula:section:section-a:ranking",
        section_id="section-a",
        mathematical_goal="Compute relevance scores and sort passages by descending score.",
        consumer_paragraph_id="paragraph:section-a:ranking",
        paragraph_ids=("paragraph:section-a:ranking",),
        authority_requirements=("closed_repository_evidence",),
    )
    evidence = MechanismEquationEvidencePackV1(
        pack_id="opack:sort",
        section_id="section-a",
        connected=True,
        unresolved_relations=(),
        bound_fact_ids=("fact:sort",),
        exact_span_ids=("span:model.py:10:12",),
        operation_atoms=({
            "fact_id": "fact:sort",
            "predicate": "sorts_by",
            "operands": ["torch.sort", "similarities", "dim=1", "descending=True"],
            "result": "(relevance_scores, indices)",
            "shape_or_type_hints": ["dim=1"],
            "source_span_id": "span:model.py:10:12",
        },),
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="repo:sort",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact:sort",
            subject="score",
            predicate="sorts_by",
            object="relevance_scores",
            scope="sym:score",
            direct_span_ids=["span:model.py:10:12"],
            exact_source_digest="sha256:source",
            canonical_identity="sha256:fact-sort",
        )],
        content_digest="sha256:facts",
    )

    packages = build_deterministic_operation_formula_packages(
        section_id="section-a",
        formula_obligations=(obligation,),
        operation_evidence_packs=(evidence,),
    )

    assert len(packages) == 1
    package = packages[0]
    assert package.authority_status == "code_verified"
    assert package.latex == (
        r"(relevance_scores, indices) = \operatorname{sort}(similarities, "
        r"dim=1, descending=True)"
    )
    failures = validate_section_formula_package(
        package,
        equations=None,
        facts=facts,
        allowed_facet_ids=set(),
        allowed_equation_ids=set(),
        operation_evidence_packs=(evidence,),
        formula_obligations=(obligation,),
        require_consumer=True,
    )
    assert any("code_shaped_formula" in failure for failure in failures)


def test_unrendered_formula_package_routes_to_rewrite_cluster() -> None:
    from code2paper.agentic.publication_method_writer import (
        _formula_package_rendered,
        _formula_rendering_issues_by_section,
        _rewrite_issue_cluster,
    )
    from code2paper.llm.section_writer import WriterSectionInput

    package = {"latex": "s = w x + b", "symbol_definitions": [{"symbol": "s", "meaning": "score"}]}
    assert _formula_package_rendered("The score is $$s = w x + b$$.", package) is True
    assert _formula_package_rendered("The score s is w times x plus b.", package) is False
    rendered_output = PublicationMethodSectionOutputV1(
        section_id="MA-S1", section_markdown="## Encoder\n\nThe score is $$s = w x + b$$.",
    )
    missing_output = PublicationMethodSectionOutputV1(
        section_id="MA-S1", section_markdown="## Encoder\n\nThe score is computed.",
    )
    writer_input = WriterSectionInput(
        section_id="MA-S1", heading="Encoder",
        prompt_payload={"formula_packages": [package]},
        publication_mode=True,
    )
    assert _formula_rendering_issues_by_section(
        {"MA-S1": rendered_output}, {"MA-S1": writer_input}
    ) == {}
    issues = _formula_rendering_issues_by_section(
        {"MA-S1": missing_output}, {"MA-S1": writer_input}
    )
    assert issues["MA-S1"]
    assert issues["MA-S1"][0].failure_type == "formula_not_rendered"
    assert _rewrite_issue_cluster(issues["MA-S1"][0]) == "formula_rendering"


def test_editor_reject_reasons_never_empty() -> None:
    from code2paper.agentic.publication_method_writer import (
        _editor_candidate_decision,
        _editor_regressed_section_ids,
    )

    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    plan = _quality_plan(claims=(claim.claim_id,), moves=("mechanism_overview",))
    text = "## Encoder\n\nThe encoder reads the configured input."
    incumbent = [("section-a", text, "sha256:writer")]
    decision, reasons, incumbent_snapshot, candidate_snapshot = _editor_candidate_decision(
        incumbent=incumbent,
        candidate=incumbent,
        plan=plan,
        claims=claims,
        equations=EquationClaimSetV1(
            repo_snapshot_id="repo:q",
            project_tree_hash="sha256:tree",
            code_fact_digest="sha256:facts",
            equations=[],
            content_digest="sha256:eq",
        ),
        configurations=ConfigurationClaimSetV1(
            repo_snapshot_id="repo:q",
            project_tree_hash="sha256:tree",
            claims=(),
            content_digest="sha256:cfg",
        ),
    )
    assert decision == "reject"
    assert reasons
    assert reasons != []
    assert "document_level_no_gain_without_reason" in reasons

    mixed_incumbent = {
        "rendered_by_section": {
            "MA-S1": {"claims": {"c1"}, "equations": set(), "configs": set(), "propositions": set()},
            "MA-S2": {"claims": {"c2"}, "equations": set(), "configs": set(), "propositions": set()},
        },
        "bound_moves": {("MA-S1", "mechanism_overview"), ("MA-S2", "mechanism_overview")},
    }
    mixed_candidate = {
        "rendered_by_section": {
            "MA-S1": {"claims": {"c1", "c3"}, "equations": set(), "configs": set(), "propositions": set()},
            "MA-S2": {"claims": set(), "equations": set(), "configs": set(), "propositions": set()},
        },
        "bound_moves": {("MA-S1", "mechanism_overview"), ("MA-S2", "mechanism_overview")},
    }
    assert _editor_regressed_section_ids(mixed_incumbent, mixed_candidate) == {"MA-S2"}


def test_unanchored_equation_move_is_typed_obligation_not_missing_required() -> None:
    plan = _quality_plan(claims=("claim-a",), moves=("equation_or_derivation",))
    plan = plan.model_copy(update={
        "sections": (
            plan.sections[0].model_copy(update={
                "moves": (
                    SectionArgumentMoveV1(
                        move="equation_or_derivation",
                        argument_unit_ids=("unit-a",),
                        allowed_authority_lanes=("formal_derivation",),
                        required=False,
                        unanchored=True,
                        unanchored_owner="Formalizer",
                    ),
                ),
            }),
        ),
    })
    completeness = _quality_completeness(claim_ids=("claim-a",))
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=["claim-a"],
        completed_rhetorical_moves=["mechanism_overview"],
    )
    report = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[output],
        claims=claims,
    )
    codes = {issue.code for issue in report.issues}
    assert "move_unanchored" in codes
    assert "required_argument_move_missing" not in codes
    assert report.utility.utility_gate_passed is False
    assert any("owner=Formalizer" in issue.message for issue in report.issues)


def test_anchored_equation_move_still_fails_when_unrendered() -> None:
    equation = EquationClaimV1(
        equation_id="eq-main",
        expression="z = x + y",
        fact_ids=["fact-formula"],
        symbol_bindings=[],
        canonical_identity="sha256:eq-main",
    )
    plan = _quality_plan(
        claims=("claim-a",),
        equations=(equation.equation_id,),
        moves=("equation_or_derivation",),
    )
    completeness = _quality_completeness(claim_ids=("claim-a",))
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    equations = EquationClaimSetV1(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts",
        equations=[equation],
        content_digest="sha256:eq",
    )
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=["claim-a"],
        used_equation_ids=[equation.equation_id],
        completed_rhetorical_moves=["equation_or_derivation"],
    )
    report = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[output],
        claims=claims,
        equations=equations,
    )
    codes = {issue.code for issue in report.issues}
    assert "required_argument_move_missing" in codes or "required_move_content_missing" in codes
    assert "move_unanchored" not in codes


def test_proposition_metrics_are_null_when_none_planned() -> None:
    claim = _quality_claim()
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    plan = _quality_plan(claims=(claim.claim_id,), moves=("mechanism_overview",))
    completeness = _quality_completeness(claim_ids=(claim.claim_id,))
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[claim.claim_id],
        completed_rhetorical_moves=["mechanism_overview"],
    )
    report = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[output],
        claims=claims,
    )
    assert report.utility.planned_proposition_recall is None
    assert report.utility.rendered_proposition_recall is None
    assert report.utility.validated_proposition_recall is None
    assert report.utility.proposition_metric_status == "not_applicable"
    assert report.utility.equation_coverage is None
    assert report.utility.coverage_metric_status["equation"] == "not_applicable"
    assert report.utility.coverage_metric_status["proposition"] == "not_applicable"


def test_live_shape_claim_is_audit_only_and_excluded_from_writer_ids() -> None:
    from code2paper.agentic.publication_method_writer import _audit_only_claim_ids

    claim = _quality_claim("claim-shape").model_copy(update={
        "canonical_text": "The module branches on loss_i.shape[0] == 0",
        "allowed_wording_boundary": "empty tensor guard",
    })
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:q",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        content_digest="sha256:claims",
    )
    audit_ids = _audit_only_claim_ids(
        propositions=None,
        proposition_bindings=None,
        claims=claims,
    )
    assert "claim-shape" in audit_ids
    completeness = MethodCompletenessMatrixV1(items=(
        MethodCompletenessItemV1(
            obligation_id="obl-audit",
            status="supported_by_repository",
            claim_ids=("claim-shape",),
        ),
    ))
    plan = _quality_plan(claims=("claim-shape",), moves=("mechanism_overview",))
    output = PublicationMethodSectionOutputV1(
        section_id="section-a",
        section_markdown="## Encoder\n\nThe encoder reads the configured input.",
        used_argument_unit_ids=["unit-a"],
        used_claim_ids=[],
        completed_rhetorical_moves=["mechanism_overview"],
    )
    report = _quality_report(
        plan=plan,
        completeness=completeness,
        sections=[output],
        claims=claims,
    )
    assert not any(
        issue.code == "supported_unit_missing_from_argument_graph"
        for issue in report.issues
    )


def test_writer_payload_lists_unanchored_equation_move_for_formalizer(
    tmp_path: Path,
) -> None:
    paths = _artifacts(tmp_path)
    seen: list[dict] = []

    def caller(_config, request):
        seen.append(request.input_payload)
        binding = request.input_payload["binding_contract"]
        return LLMResponse(
            text=json.dumps({
                "section_id": request.input_payload["section_id"],
                "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
            }),
            response_hash="sha256:writer-unanchored-eq",
            finish_reason="stop",
        )

    run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )
    grounding = seen[0]["grounding_contract"]
    assert "equation_or_derivation" in grounding["unanchored_required_moves"]
    authority = grounding["move_authority"]["equation_or_derivation"]
    assert authority["unanchored"] is True
    assert authority["unanchored_owner"] == "Formalizer"
    assert "design_objective" not in grounding["organization_only_fields"]


# ---------------------------------------------------------------------------
# WP0 — incumbent commit boundary and resume preservation (2026-08-20)
# ---------------------------------------------------------------------------


def test_wp0_resume_all_fail_preserves_incumbent_candidate_digest(tmp_path: Path) -> None:
    """Failed resume attempts must not erase a durable incumbent candidate."""

    paths = _two_section_gap_artifacts(tmp_path)

    def first_writer(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        if section_id == "MA-S1":
            return LLMResponse(
                text=json.dumps({
                    "section_id": section_id,
                    "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                    "used_argument_unit_ids": binding["used_argument_unit_ids"],
                    "used_claim_ids": binding["used_claim_ids"],
                    "used_equation_ids": binding["used_equation_ids"],
                    "used_configuration_ids": binding["used_configuration_ids"],
                    "completed_rhetorical_moves": _completed_moves(binding),
                    "new_research_requests": [{
                        "request_id": "request:MA-S1:limitations_or_mismatch",
                        "section_id": section_id,
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "missing_rhetorical_move": "limitations_or_mismatch",
                        "exact_question": "Which validated artifact resolves the scoped gap?",
                        "required_authority_lane": "executable_hard",
                        "candidate_symbols_or_terms": ["sym:encoder"],
                        "why_needed_for_reader": "Close the scoped repository gap.",
                        "priority": "high",
                    }],
                }),
                response_hash="sha256:writer:MA-S1",
                finish_reason="stop",
            )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": (
                    "## Output interface\n\nIts representation is returned to the downstream stage."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer:MA-S2",
            finish_reason="stop",
        )

    first, first_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=first_writer,
        editor_caller=lambda _config, _request: LLMResponse(
            text=json.dumps({"patches": []}),
            response_hash="sha256:editor-noop",
            finish_reason="stop",
        ),
    )
    incumbent_digest = json.loads(
        Path(first_outputs["publication_candidate_checkpoint_v1"]).read_text()
    )["final_text_digest"]
    paths.update(first_outputs)
    fulfill_writing_research_callbacks(
        first_outputs["writing_research_callback_artifacts_v1"],
        {
            "request:MA-S1:limitations_or_mismatch": ({
                "artifact_id": "artifact:output-span",
                "request_id": "request:MA-S1:limitations_or_mismatch",
                "section_id": "MA-S1",
                "argument_unit_id": "MA-S1:unit",
                "authority_lane": "executable_hard",
                "artifact_ref": "span:output.py:3:3",
                "artifact_digest": "sha256:output-span",
                "validated": True,
            },),
        },
    )

    failed, failed_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=lambda *_args: (_ for _ in ()).throw(RuntimeError("writer fault")),
        resume_section_ids=("MA-S1", "MA-S2"),
    )
    assert failed.candidate_generation_status == "generated"
    assert failed.candidate_available is True
    assert Path(failed_outputs["publication_candidate_method"]).read_text().strip()
    checkpoint = json.loads(
        Path(failed_outputs["publication_candidate_checkpoint_v1"]).read_text()
    )
    assert checkpoint["final_text_digest"] == incumbent_digest
    section_checkpoint = json.loads(
        Path(failed_outputs["publication_section_checkpoint_v1"]).read_text()
    )
    assert section_checkpoint["sections"]["MA-S1"]
    assert section_checkpoint["sections"]["MA-S2"]


def test_wp0_successful_resume_updates_only_affected_section_digest(tmp_path: Path) -> None:
    paths = _two_section_gap_artifacts(tmp_path)

    def first_writer(_config, request):
        section_id = request.input_payload["section_id"]
        binding = request.input_payload["binding_contract"]
        if section_id == "MA-S1":
            return LLMResponse(
                text=json.dumps({
                    "section_id": section_id,
                    "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
                    "used_argument_unit_ids": binding["used_argument_unit_ids"],
                    "used_claim_ids": binding["used_claim_ids"],
                    "used_equation_ids": binding["used_equation_ids"],
                    "used_configuration_ids": binding["used_configuration_ids"],
                    "completed_rhetorical_moves": _completed_moves(binding),
                    "new_research_requests": [{
                        "request_id": "request:MA-S1:limitations_or_mismatch",
                        "section_id": section_id,
                        "argument_unit_id": binding["used_argument_unit_ids"][0],
                        "missing_rhetorical_move": "limitations_or_mismatch",
                        "exact_question": "Which validated artifact resolves the scoped gap?",
                        "required_authority_lane": "executable_hard",
                        "candidate_symbols_or_terms": ["sym:encoder"],
                        "why_needed_for_reader": "Close the scoped repository gap.",
                        "priority": "high",
                    }],
                }),
                response_hash="sha256:writer:MA-S1",
                finish_reason="stop",
            )
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "section_markdown": (
                    "## Output interface\n\nIts representation is returned to the downstream stage."
                ),
                "used_argument_unit_ids": binding["used_argument_unit_ids"],
                "used_claim_ids": binding["used_claim_ids"],
                "used_equation_ids": binding["used_equation_ids"],
                "used_configuration_ids": binding["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(binding),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer:MA-S2",
            finish_reason="stop",
        )

    first, first_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=first_writer,
        editor_caller=lambda _config, _request: LLMResponse(
            text=json.dumps({"patches": []}),
            response_hash="sha256:editor-noop",
            finish_reason="stop",
        ),
    )
    checkpoint_before = json.loads(
        Path(first_outputs["publication_candidate_checkpoint_v1"]).read_text()
    )
    ma2_digest_before = checkpoint_before["section_digests"]["MA-S2"]
    paths.update(first_outputs)
    fulfill_writing_research_callbacks(
        first_outputs["writing_research_callback_artifacts_v1"],
        {
            "request:MA-S1:limitations_or_mismatch": ({
                "artifact_id": "artifact:output-span",
                "request_id": "request:MA-S1:limitations_or_mismatch",
                "section_id": "MA-S1",
                "argument_unit_id": "MA-S1:unit",
                "authority_lane": "executable_hard",
                "artifact_ref": "span:output.py:3:3",
                "artifact_digest": "sha256:output-span",
                "validated": True,
            },),
        },
    )

    resumed, resumed_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=lambda _config, request: LLMResponse(
            text=json.dumps({
                "section_id": "MA-S1",
                "section_markdown": (
                    "## Encoder\n\nThe encoder reads the configured input and leaves the gap explicit."
                ),
                "used_argument_unit_ids": request.input_payload["binding_contract"]["used_argument_unit_ids"],
                "used_claim_ids": request.input_payload["binding_contract"]["used_claim_ids"],
                "used_equation_ids": request.input_payload["binding_contract"]["used_equation_ids"],
                "used_configuration_ids": request.input_payload["binding_contract"]["used_configuration_ids"],
                "completed_rhetorical_moves": _completed_moves(
                    request.input_payload["binding_contract"]
                ),
                "new_research_requests": [],
            }),
            response_hash="sha256:writer:MA-S1-resumed",
            finish_reason="stop",
        ),
    )
    checkpoint_after = json.loads(
        Path(resumed_outputs["publication_candidate_checkpoint_v1"]).read_text()
    )
    assert checkpoint_after["section_digests"]["MA-S2"] == ma2_digest_before
    assert checkpoint_after["section_digests"]["MA-S1"] != checkpoint_before["section_digests"]["MA-S1"]
    assert resumed.candidate_generation_status == "generated"
