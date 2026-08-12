"""Candidate/verified output split (A/G contract).

The product contract: ``publication_candidate_method.md`` may carry caveated
author-intent and review material; ``repository_verified_method.md`` contains
only repository-supported positive implementation facts; and every excluded
point appears in ``author_review_candidates.json`` with a non-empty
``proposed_body`` and an exact confirmation question.  Ordinary missing
evidence never blanks the candidate — it blocks verified inclusion only.
"""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.equation_claims import compile_equation_claims
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    EvidencePacketSetV3,
    EvidencePacketV3,
    EvidenceSpanV3,
    GENERIC_RESEARCH_PRODUCER_VERSION,
)
from code2paper.agentic.final_text_claims import (
    FinalTextClaims,
    classify_final_text_unit_lanes,
    extract_final_text_claims,
)
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2, IntentObligationV2
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
)
from code2paper.agentic.obligation_fact_alignment import ObligationAlignmentV1, ObligationCoverageReportV2
from code2paper.agentic.publication_method_writer import run_publication_method_writer
from code2paper.agentic.text_evidence_validator import build_repository_verified_text
from code2paper.agentic.trust_contracts import (
    AuthoringInputProjection,
    FinalAtomicClaim,
    FinalTextUnit,
    ProjectedClaim,
    TextClaimEvidenceVerdict,
    TextEvidenceValidationReport,
)
from code2paper.agentic.v3_runtime import write_d25_method_research_artifacts, write_v3_evidence_artifacts
from code2paper.llm.client import LLMResponse
from code2paper.schemas import LLMConfig, LLMProvider, MethodEvidence


def _artifact_paths(tmp_path: Path) -> dict[str, str]:
    """One supported claim fixture plus frozen artifacts and method evidence.

    The evidence packet carries the exact span the reverse validator needs,
    so the supported sentence passes and the author-intent sentence fails.
    """

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
    span = EvidenceSpanV3(
        span_id="span:encoder.py:1:2",
        snapshot_id="repo:split",
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
        repo_snapshot_id="repo:split",
        project_tree_hash="sha256:tree",
        packets=[EvidencePacketV3(
            packet_id="packet:encoder",
            scope="sym:encoder",
            anchor_span_ids=[span.span_id],
            spans=[span],
            source_digest="sha256:packet-source",
        )],
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
    # An author-intent point that the repository does not verify: it must
    # survive into the candidate/review surface and never into verified.
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    ).model_copy(update={
        "items": (
            *MethodCompletenessMatrixV1.model_validate_json(
                Path(paths["method_completeness_matrix_v1"]).read_text()
            ).items,
            MethodCompletenessItemV1(
                obligation_id="O-AUTHOR-INTENT",
                status="unverified_by_repository",
                claim_ids=(),
                importance="critical",
                statement=(
                    "The method is intended to generalize to unseen query "
                    "distributions."
                ),
                next_action="confirm author intent or provide evidence",
                reason="No repository evidence covers this author-intended property.",
            ),
        ),
    })
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
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
    return paths


def _config() -> LLMConfig:
    return LLMConfig(
        provider=LLMProvider.NONE,
        model="fixture-writer",
        max_output_tokens=8192,
        cache=False,
    )


def _writer_response(request, *, markdown: str) -> LLMResponse:
    binding = request.input_payload["binding_contract"]
    return LLMResponse(
        text=json.dumps({
            "section_id": request.input_payload["section_id"],
            "section_markdown": markdown,
            "used_argument_unit_ids": binding["used_argument_unit_ids"],
            "used_claim_ids": binding["used_claim_ids"],
            "used_equation_ids": binding["used_equation_ids"],
            "used_configuration_ids": binding["used_configuration_ids"],
            "completed_rhetorical_moves": binding.get(
                "anchored_required_rhetorical_moves"
            ) or binding.get("completed_rhetorical_moves", []),
            "new_research_requests": [],
            "self_identified_risks": [],
        }),
        response_hash="sha256:split-writer",
        finish_reason="stop",
    )


def test_supported_claim_plus_unverified_author_claim_splits_outputs(
    tmp_path: Path,
) -> None:
    paths = _artifact_paths(tmp_path)

    def caller(_config, request):
        return _writer_response(
            request,
            markdown=(
                "## Encoder\n\n"
                "The encoder reads the configured input. The method is intended "
                "to generalize to unseen query distributions."
            ),
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    verified = Path(outputs["repository_verified_method"]).read_text()
    # Candidate covers both the supported point and the author-intent point.
    assert "reads the configured input" in candidate
    assert "generalize to unseen query distributions" in candidate
    # Verified contains only the supported sentence (plus the heading).
    assert "reads the configured input" in verified
    assert "generalize to unseen query distributions" not in verified
    assert verified.strip().startswith("## Encoder")
    # The two documents are distinct.
    assert candidate != verified

    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    items = review["items"]
    assert items
    for item in items:
        assert item["proposed_body"].strip()
        assert item["confirmation_question"].strip()
        assert item["blocks_verified"] is True
        assert item["blocks_candidate"] is False
    # The sentence-level review item carries the Writer's own span as the
    # editable proposed body.
    sentence_items = [
        item for item in items if item["candidate_id"].startswith("review-sentence:")
    ]
    assert sentence_items
    assert any(
        "generalize to unseen query distributions" in item["proposed_body"]
        for item in sentence_items
    )
    # The plan-level item from the completeness matrix also carries body text.
    matrix_items = [
        item for item in items if item["candidate_id"].startswith("review:O-AUTHOR-INTENT")
    ]
    assert matrix_items
    assert any(
        "generalize" in item["proposed_body"] for item in matrix_items
    )
    # The shared bundle contract records the effective readiness.
    bundle = json.loads(Path(outputs["method_draft_bundle_v1"]).read_text())
    assert bundle["plan_readiness"] == "candidate_ready_with_review"
    assert bundle["candidate_markdown"] == candidate
    assert bundle["verified_markdown"] == verified


def test_mismatch_warning_stays_in_candidate_and_never_in_verified(
    tmp_path: Path,
) -> None:
    paths = _artifact_paths(tmp_path)
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    ).model_copy(update={
        "items": (
            *MethodCompletenessMatrixV1.model_validate_json(
                Path(paths["method_completeness_matrix_v1"]).read_text()
            ).items,
            MethodCompletenessItemV1(
                obligation_id="O-MISMATCH",
                status="paper_code_mismatch",
                claim_ids=(),
                importance="high",
                statement=(
                    "The paper describes online re-scoring, while the "
                    "repository implements offline re-scoring."
                ),
                reason="Paper and code disagree on the scoring mode.",
            ),
        ),
    })
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )

    def caller(_config, request):
        return _writer_response(
            request,
            markdown=(
                "## Encoder\n\nThe encoder reads the configured input. "
                "A mismatch is noted: the paper describes online re-scoring, "
                "while the repository implements offline re-scoring."
            ),
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    verified = Path(outputs["repository_verified_method"]).read_text()
    assert "offline re-scoring" in candidate
    assert "offline re-scoring" not in verified
    assert "reads the configured input" in verified
    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    mismatch_items = [
        item for item in review["items"]
        if item["candidate_id"] == "review:O-MISMATCH"
    ]
    assert mismatch_items
    assert mismatch_items[0]["proposed_body"].strip()
    assert mismatch_items[0]["lane"] == "repository_mismatch"


def test_expository_bridge_scaffolding_survives_into_verified(tmp_path: Path) -> None:
    """Claim-free organizational scaffolding is safe for the verified document;
    the unsupported sentence is still excluded."""

    paths = _artifact_paths(tmp_path)

    def caller(_config, request):
        return _writer_response(
            request,
            markdown=(
                "## Encoder\n\nIn this section we describe the encoder. "
                "The encoder reads the configured input. "
                "We now turn to the output stage."
            ),
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    verified = Path(outputs["repository_verified_method"]).read_text()
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert "reads the configured input" in verified
    assert "we describe the encoder" not in verified
    assert "we describe the encoder" in candidate


def test_unsupported_uncaveated_sentence_is_review_linked_and_excluded(
    tmp_path: Path,
) -> None:
    paths = _artifact_paths(tmp_path)

    def caller(_config, request):
        return _writer_response(
            request,
            markdown=(
                "## Encoder\n\nThe encoder reads the configured input. "
                "The cache stores the embeddings in a tensor buffer."
            ),
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    verified = Path(outputs["repository_verified_method"]).read_text()
    assert "stores the embeddings" in candidate
    assert "stores the embeddings" not in verified
    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    assert any(
        item["candidate_id"].startswith("review-sentence:")
        and "stores the embeddings" in item["proposed_body"]
        and item["confirmation_question"]
        for item in review["items"]
    )


def _digest(value: str) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _projection(claim_ids: tuple[str, ...] = ("claim:1",)) -> AuthoringInputProjection:
    claims = [
        ProjectedClaim(
            claim_id=claim_id,
            claim_text="The encoder reads the configured input.",
            support_status="supported",
            direct_evidence_ids=["span:encoder.py:1:2"],
            supported_fragment="The encoder reads the configured input.",
            allowed_wording_boundary="encoder reads configured input only",
            input_digest=_digest(claim_id),
        )
        for claim_id in claim_ids
    ]
    payload = {
        "project_id": "fixture",
        "method_name": "Encoder",
        "author_goal": "Describe the encoder.",
        "implementation_scope": "fixture repository",
        "projected_claims": [item.model_dump(mode="json") for item in claims],
    }
    payload["projection_digest"] = _digest("projection")
    return AuthoringInputProjection(**payload)


def _unit(
    unit_id: str,
    text: str,
    kind: str = "sentence",
    factual: bool = True,
    start: int = 0,
    end: int | None = None,
) -> FinalTextUnit:
    end = len(text) if end is None else end
    return FinalTextUnit(
        unit_id=unit_id,
        kind=kind,
        text=text,
        line_start=1,
        line_end=1,
        char_start=start,
        char_end=end,
        factual=factual,
        span_digest=_digest(text),
    )


def test_candidate_narrative_requires_typed_point_and_visible_author_framing() -> None:
    projection = _projection().model_copy(update={
        "author_intent_unverified_points": [{
            "point_id": "author_point:score",
            "statement": "Map Gaussian features to importance scores for pruning.",
            "source_obligation_id": "obl-score",
            "lane": "author_intent_unverified",
        }],
    })
    caveated = extract_final_text_claims(
        "We aim to map Gaussian features to importance scores for pruning.",
        projection,
    )
    assert caveated.atomic_claims[0].candidate_narrative_ids == [
        "author_point:score"
    ]
    assert classify_final_text_unit_lanes(caveated, projection)["FTU1"] == (
        "author_intent_caveated"
    )

    positive = extract_final_text_claims(
        "The model maps Gaussian features to importance scores for pruning.",
        projection,
    )
    assert positive.atomic_claims[0].candidate_narrative_ids == []
    assert classify_final_text_unit_lanes(positive, projection)["FTU1"] == (
        "unsafe_unsupported_positive"
    )


def test_build_repository_verified_text_keeps_supported_and_bridge_only() -> None:
    text = (
        "## Encoder\n\n"
        "The encoder reads the configured input. "
        "The method is intended to generalize to unseen query distributions."
    )
    units = [
        _unit("U1", "## Encoder", kind="heading", factual=False, start=0, end=12),
        _unit("U2", "The encoder reads the configured input.", start=14, end=50),
        _unit(
            "U3",
            "The method is intended to generalize to unseen query distributions.",
            start=51,
            end=len(text),
        ),
    ]
    claims = FinalTextClaims(
        input_text_digest=_digest(text),
        units=units,
        atomic_claims=[
            FinalAtomicClaim(
                atomic_claim_id="FAC1",
                unit_id="U2",
                text="The encoder reads the configured input.",
                normalized_text="encoder reads configured input",
                line_start=1,
                line_end=1,
                char_start=14,
                char_end=50,
                candidate_projection_claim_ids=["claim:1"],
                claim_digest=_digest("fac1"),
            ),
            FinalAtomicClaim(
                atomic_claim_id="FAC2",
                unit_id="U3",
                text="The method is intended to generalize to unseen query distributions.",
                normalized_text="method intended generalize unseen query distributions",
                line_start=1,
                line_end=1,
                char_start=51,
                char_end=len(text),
                claim_digest=_digest("fac2"),
            ),
        ],
    )
    report = TextEvidenceValidationReport(
        status="failed",
        input_text_digest=_digest(text),
        projection_digest=_digest("projection"),
        verdicts=[
            TextClaimEvidenceVerdict(
                atomic_claim_id="FAC1",
                status="supported",
                matched_projection_claim_ids=["claim:1"],
                direct_evidence_ids=["span:encoder.py:1:2"],
            ),
            TextClaimEvidenceVerdict(
                atomic_claim_id="FAC2",
                status="unsupported",
                deterministic_failures=["no_semantically_matching_projected_claim"],
                repair_action="revise_authoring_wording",
            ),
        ],
    )
    verified, split = build_repository_verified_text(
        final_text=text,
        final_claims=claims,
        validation_report=report,
        projection=_projection(),
    )
    assert "reads the configured input" in verified
    assert "generalize" not in verified
    assert verified.startswith("## Encoder")
    assert len(split["excluded_units"]) == 1
    assert split["excluded_units"][0]["unit_id"] == "U3"
    assert split["unsupported_positive_units"] == 1


def test_build_repository_verified_text_partial_needs_projection_claim_match() -> None:
    """A caveated verdict enters verified only when it is a qualifier-guarded
    partial (its matched ids are projection claim ids); an author-attested
    caveat never does."""
    text = "The encoder reads the configured input. The goal is to prove the encoder works."
    units = [
        _unit("U1", "The encoder reads the configured input.", start=0, end=44),
        _unit("U2", "The goal is to prove the encoder works.", start=45, end=len(text)),
    ]
    claims = FinalTextClaims(
        input_text_digest=_digest(text),
        units=units,
        atomic_claims=[
            FinalAtomicClaim(
                atomic_claim_id="FAC1",
                unit_id="U1",
                text="The encoder reads the configured input.",
                normalized_text="encoder reads configured input",
                line_start=1,
                line_end=1,
                char_start=0,
                char_end=44,
                candidate_projection_claim_ids=["claim:1"],
                claim_digest=_digest("fac1"),
            ),
            FinalAtomicClaim(
                atomic_claim_id="FAC2",
                unit_id="U2",
                text="The goal is to prove the encoder works.",
                normalized_text="goal prove encoder works",
                line_start=1,
                line_end=1,
                char_start=45,
                char_end=len(text),
                candidate_author_attested_ids=["author:1"],
                claim_digest=_digest("fac2"),
            ),
        ],
    )
    report = TextEvidenceValidationReport(
        status="failed",
        input_text_digest=_digest(text),
        projection_digest=_digest("projection"),
        verdicts=[
            TextClaimEvidenceVerdict(
                atomic_claim_id="FAC1",
                status="supported",
                matched_projection_claim_ids=["claim:1"],
                direct_evidence_ids=["span:encoder.py:1:2"],
            ),
            TextClaimEvidenceVerdict(
                atomic_claim_id="FAC2",
                status="caveated",
                matched_projection_claim_ids=["author:1"],
                rationale="Author-attested fragment matched; not repository evidence.",
            ),
        ],
    )
    verified, _split = build_repository_verified_text(
        final_text=text,
        final_claims=claims,
        validation_report=report,
        projection=_projection(),
    )
    assert "prove the encoder works" not in verified


def test_classify_final_text_unit_lanes_partitions_candidate_and_verified() -> None:
    text = "The encoder reads the configured input. The cache stores embeddings."
    units = [
        _unit("U1", "The encoder reads the configured input.", start=0, end=44),
        _unit("U2", "The cache stores embeddings.", start=45, end=len(text)),
    ]
    claims = FinalTextClaims(
        input_text_digest=_digest(text),
        units=units,
        atomic_claims=[
            FinalAtomicClaim(
                atomic_claim_id="FAC1",
                unit_id="U1",
                text="The encoder reads the configured input.",
                normalized_text="encoder reads configured input",
                line_start=1,
                line_end=1,
                char_start=0,
                char_end=44,
                candidate_projection_claim_ids=["claim:1"],
                claim_digest=_digest("fac1"),
            ),
            FinalAtomicClaim(
                atomic_claim_id="FAC2",
                unit_id="U2",
                text="The cache stores embeddings.",
                normalized_text="cache stores embeddings",
                line_start=1,
                line_end=1,
                char_start=45,
                char_end=len(text),
                claim_digest=_digest("fac2"),
            ),
        ],
    )
    lanes = classify_final_text_unit_lanes(claims, _projection())
    assert lanes["U1"] == "repository_positive"
    assert lanes["U2"] == "unsafe_unsupported_positive"
    # Headings are structural scaffolding, safe for both documents.
    heading_claims = claims.model_copy(update={
        "units": [_unit("H1", "## Encoder", kind="heading", factual=False), *units],
    })
    lanes = classify_final_text_unit_lanes(heading_claims, _projection())
    assert lanes["H1"] == "expository_bridge"


def test_writer_unresolved_points_become_review_items(tmp_path: Path) -> None:
    """E1: a Writer that flags an unresolved prose point (without a callback)
    never drops it silently — the point becomes a review item carrying the
    Writer's own wording as the proposed body."""
    paths = _artifact_paths(tmp_path)

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
                "completed_rhetorical_moves": binding.get(
                    "anchored_required_rhetorical_moves"
                ) or binding.get("completed_rhetorical_moves", []),
                "new_research_requests": [],
                "unresolved_points": [
                    "The interaction with the external tokenizer is not described.",
                ],
            }),
            response_hash="sha256:unresolved-writer",
            finish_reason="stop",
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    unresolved = [
        item for item in review["items"]
        if item["candidate_id"].startswith("review-unresolved:")
    ]
    assert unresolved
    assert unresolved[0]["proposed_body"] == (
        "The interaction with the external tokenizer is not described."
    )
    assert unresolved[0]["confirmation_question"].strip()
    assert unresolved[0]["blocks_verified"] is True
    assert unresolved[0]["blocks_candidate"] is False
