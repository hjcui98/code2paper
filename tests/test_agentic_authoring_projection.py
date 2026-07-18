from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from code2paper.agentic.authoring_projection import (
    build_authoring_projection,
    projected_writer_inputs,
    projection_writer_payload,
    restrict_projection_for_authoring_revision,
)
from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.authoring.writing.method_writer import build_method_draft_markdown
from code2paper.core.schemas import (
    AuthorMode,
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    ClaimContract,
    ConflictStatus,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    SupportStatus,
    LLMConfig,
    EvidenceItem,
    RawEvidencePack,
    SourceType,
)
from code2paper.llm.client import LLMResponse
from code2paper.pipeline.stages.authoring import write_phase5_artifacts
from tests.tempdir_support import workspace_tempdir


def _evidence() -> MethodEvidence:
    return MethodEvidence(
        project_id="projection-test",
        method_name="Projection Method",
        method_goal="Claim unsupported 99% acceleration while describing the encoder.",
        implementation_scope="test",
        stages=[
            MethodStageEvidence(
                stage_id="S1",
                name="Encode",
                purpose="Unsupported 99% acceleration.",
                mechanisms=[
                    Mechanism(
                        mechanism_id="MECH1",
                        description="The encoder reads configured features.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E1"],
                    )
                ],
            )
        ],
        stage_packets=[
            {
                "stage_id": "S1",
                "name": "Encode",
                "purpose": "Unsupported 99% acceleration.",
                "claim_ids": ["C1", "C2"],
                "evidence_span_ids": ["E1", "E404"],
                "stage_claim": "Unsupported 99% acceleration.",
            }
        ],
        innovation_candidates=[{"claim": "Unsupported 99% acceleration."}],
    )


def _claims() -> ClaimEvidenceMap:
    return ClaimEvidenceMap(
        claims=[
            ClaimEvidenceItem(
                claim_id="C1",
                claim_text="The encoder reads configured features.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
            ),
            ClaimEvidenceItem(
                claim_id="C2",
                claim_text="The method provides unsupported 99% acceleration.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E404"],
            ),
            ClaimEvidenceItem(
                claim_id="C3",
                claim_text="The encoder exposes only the configured feature path.",
                support_status=SupportStatus.PARTIAL,
                evidence_ids=["E1"],
                caveats=["Only the configured path is implemented."],
            ),
        ]
    )


def test_projection_recursively_removes_forbidden_positive_wording() -> None:
    evidence = _evidence()
    claims = _claims()
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )

    positive_payload = json.dumps(projection_writer_payload(projection), ensure_ascii=False)
    assert "unsupported 99% acceleration" not in positive_payload.lower()
    assert [claim.claim_id for claim in projection.projected_claims] == ["C1", "C3"]
    assert [claim.claim_id for claim in projection.forbidden_claims] == ["C2"]
    assert projection.forbidden_claims[0].model_dump().get("claim_text") is None
    assert len(projection.stage_packets) == 1
    assert projection.stage_packets[0]["stage_id"] == "S1"
    assert set(projection.stage_packets[0]["claim_ids"]) == {"C1", "C3"}
    assert projection.stage_packets[0]["evidence_span_ids"] == ["E1"]
    assert "guarantees impossible speedups" not in str(projection.stage_packets[0]).lower()


def test_partial_projection_keeps_supported_fragment_and_qualifier() -> None:
    evidence = _evidence()
    claims = _claims()
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )
    partial = next(claim for claim in projection.projected_claims if claim.claim_id == "C3")

    assert partial.support_status == "partial"
    assert partial.required_qualifiers == ["Only the configured path is implemented."]
    writer_evidence, writer_claims = projected_writer_inputs(projection, template=evidence)
    assert [stage.stage_id for stage in writer_evidence.stages] == ["S1"]
    assert writer_evidence.stages[0].purpose == projection.stage_packets[0]["purpose"]
    assert writer_evidence.innovation_candidates == []
    assert [claim.claim_id for claim in writer_claims.claims] == ["C1", "C3"]


def test_partial_projection_without_explicit_qualifier_is_forbidden() -> None:
    evidence = _evidence()
    evidence.stage_packets[0]["claim_ids"] = ["C1", "C4"]
    claims = ClaimEvidenceMap(claims=[
        ClaimEvidenceItem(
            claim_id="C1", claim_text="The encoder reads configured features.",
            support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
        ),
        ClaimEvidenceItem(
            claim_id="C4",
            claim_text="The encoder guarantees faster inference.",
            support_status=SupportStatus.PARTIAL, evidence_ids=["E1"],
            source="author_claim:file",
        ),
    ])

    projection = build_authoring_projection(
        method_evidence=evidence, claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )

    assert [claim.claim_id for claim in projection.projected_claims] == ["C1"]
    forbidden = next(item for item in projection.forbidden_claims if item.claim_id == "C4")
    assert forbidden.reason == "partial_claim_missing_explicit_qualifier"


def test_revision_writer_view_excludes_rejected_projection_claims() -> None:
    evidence = _evidence()
    claims = _claims()
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )

    restricted = restrict_projection_for_authoring_revision(projection, {"C1"})

    assert [claim.claim_id for claim in restricted.projected_claims] == ["C3"]
    assert restricted.projection_digest != projection.projection_digest
    assert all("C1" not in packet["claim_ids"] for packet in restricted.stage_packets)


def test_projection_writer_deduplicates_claims_and_omits_stage_contract_metadata() -> None:
    evidence = _evidence()
    evidence.writing_constraints.append(
        "The projection is the writer's only positive method-fact input."
    )
    evidence.stage_packets[0]["claim_ids"] = ["C1", "C2", "C3", "C4"]
    claims = ClaimEvidenceMap(
        claims=[
            ClaimEvidenceItem(
                claim_id="C1",
                claim_text="The encoder reads configured features.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
                source="method_mechanism",
            ),
            ClaimEvidenceItem(
                claim_id="C2",
                claim_text="The method contains a paper-facing stage named Encode.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
                source="claim_contract:C1",
            ),
            ClaimEvidenceItem(
                claim_id="C3",
                claim_text="The encoder reads configured features.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
                source="claim_contract:C2",
                caveats=["Only the configured path is implemented."],
            ),
            ClaimEvidenceItem(
                claim_id="C4",
                claim_text="Unsupported duplicate.",
                support_status=SupportStatus.UNSUPPORTED,
                evidence_ids=[],
                source="author_claim:none",
            ),
        ]
    )

    draft = build_method_draft_markdown(evidence, claims)

    assert draft.count("The encoder reads configured features") == 1
    assert "Only the configured path is implemented." in draft
    assert "paper-facing stage named" not in draft
    assert "Unsupported duplicate" not in draft


def test_projection_omits_stage_name_scaffold_from_positive_writer_facts() -> None:
    evidence = _evidence()
    evidence.stage_packets[0]["claim_ids"] = ["C1", "C2"]
    claims = ClaimEvidenceMap(claims=[
        ClaimEvidenceItem(
            claim_id="C1", claim_text="The encoder reads configured features.",
            support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
            source="method_mechanism",
        ),
        ClaimEvidenceItem(
            claim_id="C2", claim_text="The method contains a paper-facing stage named Encode.",
            support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
            source="claim_contract:C1",
        ),
    ])

    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )

    assert [claim.claim_id for claim in projection.projected_claims] == ["C1"]
    assert "structural_claim:C2" in projection.dropped_positive_fields
    assert "paper-facing stage named" not in json.dumps(
        projection_writer_payload(projection), ensure_ascii=False
    )


def test_projection_scopes_operator_subclaim_by_stage_semantics_and_evidence() -> None:
    evidence = MethodEvidence(
        project_id="cmoe", method_name="C-MoE", method_goal="Route experts.",
        implementation_scope="test",
        stages=[MethodStageEvidence(
            stage_id="S1", name="C-MoE grouped dynamic filtering", purpose="Route experts.",
            mechanisms=[Mechanism(
                mechanism_id="MECH1", description="Route experts.",
                support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
            )],
        )],
        stage_packets=[{
            "stage_id": "S1", "name": "C-MoE grouped dynamic filtering",
            "purpose": "Route experts.", "claim_ids": ["C1"],
            "evidence_span_ids": ["E1"],
        }],
    )
    claims = ClaimEvidenceMap(claims=[
        ClaimEvidenceItem(
            claim_id="C1", claim_text="Route experts.",
            support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
        ),
        ClaimEvidenceItem(
            claim_id="C2",
            claim_text="Pack expert kernels into a single group convolution.",
            support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
            source="submechanism:SUBMECH1",
        ),
    ])

    projection = build_authoring_projection(
        method_evidence=evidence, claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )

    assert [claim.claim_id for claim in projection.projected_claims] == ["C1", "C2"]
    assert projection.stage_packets[0]["claim_ids"] == ["C1", "C2"]


def test_projection_retains_verified_explicit_claim_contract_outside_broad_stage_heading() -> None:
    evidence = MethodEvidence(
        project_id="intent-contract", method_name="Intent Contract",
        method_goal="Describe explicit evidence-backed intent.", implementation_scope="test",
        stages=[MethodStageEvidence(
            stage_id="S1", name="Architecture", purpose="Encode inputs.",
            mechanisms=[Mechanism(
                mechanism_id="MECH1", description="Encode inputs.",
                support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
            )],
        )],
        stage_packets=[{
            "stage_id": "S1", "name": "Architecture", "purpose": "Encode inputs.",
            "claim_ids": ["C1"], "evidence_span_ids": ["E1"],
        }],
        claim_contracts=[ClaimContract(
            claim_id="C2",
            claim_intent="Add sinusoidal passage-position encoding.",
            support_status=ConflictStatus.SUPPORTED,
            evidence_span_ids=["E1"],
            allowed_wording_boundary="Add sinusoidal passage-position encoding.",
        )],
    )
    claims = ClaimEvidenceMap(claims=[
        ClaimEvidenceItem(
            claim_id="C1", claim_text="Encode inputs.",
            support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
        ),
        ClaimEvidenceItem(
            claim_id="C2", claim_text="Add sinusoidal passage-position encoding.",
            support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
            source="claim_contract:C2",
        ),
        ClaimEvidenceItem(
            claim_id="C3", claim_text="Run an unrelated generic helper.",
            support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
            source="submechanism:SUBMECH9",
        ),
    ])

    projection = build_authoring_projection(
        method_evidence=evidence, claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )

    assert [claim.claim_id for claim in projection.projected_claims] == ["C1", "C2"]
    forbidden = next(item for item in projection.forbidden_claims if item.claim_id == "C3")
    assert forbidden.reason == "outside_author_scoped_method_stages"


def test_projection_rejects_mlp_importance_claim_when_code_only_builds_prune_features() -> None:
    evidence = MethodEvidence(
        project_id="rap-boundary", method_name="RAP Boundary",
        method_goal="Describe code-supported pruning features.", implementation_scope="test",
        stages=[MethodStageEvidence(
            stage_id="S1", name="Pruning", purpose="Build pruning features.",
            mechanisms=[Mechanism(
                mechanism_id="MECH1", description="Build pruning features.",
                support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
            )],
        )],
        stage_packets=[{
            "stage_id": "S1", "name": "Pruning", "purpose": "Build pruning features.",
            "claim_ids": ["C1"], "evidence_span_ids": ["E1"],
        }],
    )
    claims = ClaimEvidenceMap(claims=[ClaimEvidenceItem(
        claim_id="C1",
        claim_text="Use an MLP to predict importance scores from pruning features.",
        support_status=SupportStatus.SUPPORTED,
        evidence_ids=["E1"],
        source="claim_contract:C1",
    )])
    raw = RawEvidencePack(
        project_id="rap-boundary", project_root="/repo", author_mode=AuthorMode.ENHANCED,
        evidence_items=[EvidenceItem(
            evidence_id="E1", source_type=SourceType.SOURCE,
            path="gaussian_model.py", line_start=1, line_end=3,
            content_summary=(
                "def get_prune_input(self): input_features = torch.cat(features); "
                "self.prune_features = percentile_cutoff_normalize(input_features)"
            ),
            confidence=0.9,
        )],
    )

    projection = build_authoring_projection(
        method_evidence=evidence, claim_map=claims,
        verification=build_claim_verification_report(evidence, claims), raw_evidence=raw,
    )

    assert projection.projected_claims == []
    assert projection.forbidden_claims[0].reason == "direct_evidence_semantically_unrelated"


def test_projection_recognizes_normalized_mixed_domain_score_code() -> None:
    evidence = MethodEvidence(
        project_id="mixed-domain", method_name="Mixed-domain pruning",
        method_goal="Aggregate normalized domain scores.", implementation_scope="test",
        stages=[MethodStageEvidence(
            stage_id="S1", name="Mixed domain", purpose="Average normalized scores.",
            mechanisms=[Mechanism(
                mechanism_id="MECH1", description="Average normalized scores.",
                support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"],
            )],
        )],
        stage_packets=[{
            "stage_id": "S1", "name": "Mixed domain", "purpose": "Average normalized scores.",
            "claim_ids": ["C1"], "evidence_span_ids": ["E1"],
        }],
    )
    claims = ClaimEvidenceMap(claims=[ClaimEvidenceItem(
        claim_id="C1",
        claim_text="For multiple domains, average normalized domain-specific scores before final selection.",
        support_status=SupportStatus.SUPPORTED, evidence_ids=["E1"], source="method_mechanism",
    )])
    raw = RawEvidencePack(
        project_id="mixed-domain", project_root="/repo", author_mode=AuthorMode.ENHANCED,
        evidence_items=[EvidenceItem(
            evidence_id="E1", source_type=SourceType.SOURCE,
            path="pruning/expert_selection_mix_domain.py", line_start=1, line_end=4,
            content_summary=(
                "score = score / torch.sum(score, dim=-1, keepdim=True); "
                "tmp = tmp + score; topk_experts = torch.topk(tmp, dim=-1)"
            ), confidence=0.9,
        )],
    )

    projection = build_authoring_projection(
        method_evidence=evidence, claim_map=claims,
        verification=build_claim_verification_report(evidence, claims), raw_evidence=raw,
    )

    assert [claim.claim_id for claim in projection.projected_claims] == ["C1"]


def test_projection_model_writer_uses_only_projected_positive_facts() -> None:
    evidence = _evidence()
    claims = _claims()
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )
    writer_evidence, writer_claims = projected_writer_inputs(
        projection, template=evidence
    )
    response_markdown = (
        "# Method\n\n## Encoding\n"
        "The encoder reads configured features and exposes only the configured "
        "feature path; only the configured path is implemented.\n"
    )
    with workspace_tempdir() as tmpdir, patch(
        "code2paper.llm.client.LLMClient.complete", autospec=True
    ) as complete:
        complete.return_value = LLMResponse(
            text=json.dumps({"markdown": response_markdown}),
            response_hash="sha256:projection-writer",
        )
        markdown, _tex, paths = write_phase5_artifacts(
            method_root=Path(tmpdir),
            method_evidence=writer_evidence,
            claim_map=writer_claims,
            llm_config=LLMConfig(provider="openai", model="test-model"),
            equations_tex="FORBIDDEN_RAW_EQUATION",
            symbols_tex="FORBIDDEN_RAW_SYMBOL",
        )
        manifest = json.loads(paths["phase5_manifest"].read_text(encoding="utf-8"))
        request = complete.call_args.args[1]
        serialized_payload = json.dumps(request.input_payload, ensure_ascii=False)
        assert markdown is not None
        assert complete.call_count == 1
        assert request.prompt_template_id == "agentic_projection_method_authoring_v1"
        assert manifest["mode"] == "projection-constrained-llm-writer"
        assert "stage=S1" in markdown
        assert "mechanisms=MECH1" in markdown
        assert "evidence=E1" in markdown
        assert "E404" not in markdown
        assert "unsupported 99% acceleration" not in serialized_payload.lower()
        assert "FORBIDDEN_RAW_EQUATION" not in serialized_payload
        assert "FORBIDDEN_RAW_SYMBOL" not in serialized_payload


def test_projection_model_writer_removes_unmatched_positive_prose() -> None:
    evidence = _evidence()
    claims = _claims()
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )
    writer_evidence, writer_claims = projected_writer_inputs(projection, template=evidence)
    with workspace_tempdir() as tmpdir, patch(
        "code2paper.llm.client.LLMClient.complete", autospec=True
    ) as complete:
        complete.return_value = LLMResponse(
            text=json.dumps(
                {"markdown": "# Method\n\n## Results\nThe system guarantees higher accuracy.\n"}
            ),
            response_hash="sha256:projection-writer-unmatched",
        )
        markdown, _tex, _paths = write_phase5_artifacts(
            method_root=Path(tmpdir),
            method_evidence=writer_evidence,
            claim_map=writer_claims,
            llm_config=LLMConfig(provider="openai", model="test-model"),
        )

    assert markdown is not None
    assert "guarantees higher accuracy" not in markdown
    assert "## Results" not in markdown


def test_projection_model_writer_drops_repeated_verifier_rejected_sentence() -> None:
    evidence = _evidence()
    claims = _claims()
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )
    writer_evidence, writer_claims = projected_writer_inputs(projection, template=evidence)
    rejected = "The encoder reads configured features to resolve all training settings."
    feedback = json.dumps(
        {
            "authoring_revision_feedback": [
                {
                    "keep_supported_fragment": "",
                    "remove_or_rewrite_text": rejected,
                }
            ]
        },
        indent=2,
    )
    with workspace_tempdir() as tmpdir, patch(
        "code2paper.llm.client.LLMClient.complete", autospec=True
    ) as complete:
        complete.return_value = LLMResponse(
            text=json.dumps(
                {
                    "markdown": (
                        "# Method\n\n## Encoding\n"
                        "The encoder reads configured features. " + rejected + "\n"
                    )
                }
            ),
            response_hash="sha256:projection-writer-revision",
        )
        markdown, _tex, _paths = write_phase5_artifacts(
            method_root=Path(tmpdir),
            method_evidence=writer_evidence,
            claim_map=writer_claims,
            llm_config=LLMConfig(provider="openai", model="test-model"),
            grounding_context_markdown=feedback,
        )

    assert markdown is not None
    assert "The encoder reads configured features." in markdown
    assert "resolve all training settings" not in markdown
