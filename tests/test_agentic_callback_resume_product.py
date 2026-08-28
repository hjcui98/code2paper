"""Writer callback/resume product loop (F contract).

- repository/config/formalization callbacks execute local tools and produce
  digest-pinned artifacts; a fulfilled callback resumes only the affected
  section (unaffected sections and their checkpoints stay unchanged);
- author callbacks produce a review queue item with an editable proposed
  body and an exact question — candidate continues, verified excludes;
- literature/empirical callbacks produce explicit external queue artifacts,
  never a silent ``None``.
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
    GENERIC_RESEARCH_PRODUCER_VERSION,
)
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2, IntentObligationV2
from code2paper.agentic.method_argument_models import (
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
    WritingResearchRequestV1,
)
from code2paper.agentic.obligation_fact_alignment import ObligationAlignmentV1, ObligationCoverageReportV2
from code2paper.agentic.publication_method_writer import (
    fulfill_writing_research_callbacks,
    run_publication_method_writer,
)
from code2paper.agentic.v3_runtime import write_d25_method_research_artifacts, write_v3_evidence_artifacts
from code2paper.agentic.writer_research_router import (
    build_external_research_queue_items,
    execute_open_requests_for_routes,
)
from code2paper.llm.client import LLMResponse
from code2paper.schemas import LLMConfig, LLMProvider


def _base_paths(tmp_path: Path) -> dict[str, str]:
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
        repo_snapshot_id="repo:router",
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


def _add_completeness_row(
    paths: dict[str, str],
    row: MethodCompletenessItemV1,
) -> dict[str, str]:
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        Path(paths["method_completeness_matrix_v1"]).read_text()
    ).model_copy(update={
        "items": (
            *MethodCompletenessMatrixV1.model_validate_json(
                Path(paths["method_completeness_matrix_v1"]).read_text()
            ).items,
            row,
        ),
    })
    Path(paths["method_completeness_matrix_v1"]).write_text(
        completeness.model_dump_json(indent=2), encoding="utf-8"
    )
    return paths


def _config() -> LLMConfig:
    return LLMConfig(
        provider=LLMProvider.NONE,
        model="fixture-writer",
        max_output_tokens=8192,
        cache=False,
    )


def _callback_request(
    request,
    *,
    moves_to_request: tuple[str, ...],
) -> LLMResponse:
    """Writer response completing anchored moves and requesting unanchored ones."""
    binding = request.input_payload["binding_contract"]
    grounding = request.input_payload["grounding_contract"]
    move_authority = grounding.get("move_authority") or {}
    completed = [
        move for move in binding.get("completed_rhetorical_moves", [])
        if move not in moves_to_request
    ]
    callbacks = [
        {
            "request_id": f"request:{request.input_payload['section_id']}:{move}",
            "section_id": request.input_payload["section_id"],
            "argument_unit_id": binding["used_argument_unit_ids"][0],
            "missing_rhetorical_move": move,
            "exact_question": f"Which validated artifact supports {move}?",
            "required_authority_lane": move_authority[move]["allowed_authority_lanes"][0],
            "candidate_symbols_or_terms": move_authority[move]["candidate_symbols_or_terms"],
            "status": "open",
        }
        for move in moves_to_request
    ]
    return LLMResponse(
        text=json.dumps({
            "section_id": request.input_payload["section_id"],
            "section_markdown": "## Encoder\n\nThe encoder reads the configured input.",
            "used_argument_unit_ids": binding["used_argument_unit_ids"],
            "used_claim_ids": binding["used_claim_ids"],
            "used_equation_ids": binding["used_equation_ids"],
            "used_configuration_ids": binding["used_configuration_ids"],
            "completed_rhetorical_moves": completed,
            "new_research_requests": callbacks,
            "self_identified_risks": [],
        }),
        response_hash="sha256:writer-request",
        finish_reason="stop",
    )


def test_author_callback_produces_review_item_and_queue_artifact(
    tmp_path: Path,
) -> None:
    """An author-lane request must never be a silent ``None``: it becomes a
    review item (proposed body + exact question) and a queued external item;
    candidate continues and verified excludes nothing unsupported."""
    paths = _base_paths(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    _add_completeness_row(paths, MethodCompletenessItemV1(
        obligation_id="O-AUTHOR-CONFIRM",
        status="author_confirmation_required",
        claim_ids=(claims.claims[0].claim_id,),
        importance="critical",
        reason="The author must confirm the intended objective.",
    ))

    def caller(_config, request):
        grounding = request.input_payload.get("grounding_contract") or {}
        unanchored = tuple(grounding.get("unanchored_required_moves") or ())
        return _callback_request(
            request,
            moves_to_request=unanchored[:1] or ("limitations_or_mismatch",),
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    assert result.accepted_section_ids == ("MA-S1",)
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert candidate.strip().startswith("## Encoder")

    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    request_items = [
        item for item in review["items"]
        if item["candidate_id"].startswith("review-request:")
    ]
    assert request_items
    for item in request_items:
        assert item["proposed_body"].strip()
        assert item["confirmation_question"].strip()
        assert item["blocks_verified"] is True
        assert item["blocks_candidate"] is False
        assert item["lane"] == "author_intent_unverified"

    queue = json.loads(Path(outputs["external_research_queue_v1"]).read_text())
    assert queue["items"]
    for item in queue["items"]:
        assert item["status"] == "queued"
        assert item["lane"] == "author_attested"
        assert item["exact_question"].strip()
        assert item["proposed_body"].strip()

    routes = json.loads(Path(outputs["writing_research_routes_v1"]).read_text())
    assert routes["routes"]
    assert all(
        route["owner"] == "author_confirmation_queue"
        for route in routes["routes"]
    )
    assert "MA-S1" in review["incomplete_sections"]


def test_literature_callback_produces_external_queue_artifact(tmp_path: Path) -> None:
    """A literature-pending completeness row becomes an explicit external
    queue item (not a silent ``None``) and stays out of the verified lane."""
    paths = _base_paths(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    _add_completeness_row(paths, MethodCompletenessItemV1(
        obligation_id="O-EXT-LIT",
        status="external_evidence_required",
        claim_ids=(claims.claims[0].claim_id,),
        importance="critical",
        reason="The comparison baseline needs a citation.",
    ))

    def caller(_config, request):
        grounding = request.input_payload.get("grounding_contract") or {}
        unanchored = tuple(grounding.get("unanchored_required_moves") or ())
        return _callback_request(
            request,
            moves_to_request=unanchored[:1] or ("limitations_or_mismatch",),
        )

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )

    assert result.status == "incomplete"
    candidate = Path(outputs["publication_candidate_method"]).read_text()
    assert candidate.strip().startswith("## Encoder")
    queue = json.loads(Path(outputs["external_research_queue_v1"]).read_text())
    literature_items = [item for item in queue["items"] if item["lane"] == "external_literature"]
    assert literature_items
    item = literature_items[0]
    assert item["status"] == "queued"
    assert item["exact_question"].strip()
    assert item["proposed_body"].strip()
    assert item["section_id"] == "MA-S1"
    review = json.loads(Path(outputs["author_review_candidates"]).read_text())
    assert any(
        item["candidate_id"] == "review:O-EXT-LIT"
        and item["proposed_body"].strip()
        and item["confirmation_question"].strip()
        for item in review["items"]
    )


def test_repository_callback_route_executes_locally_and_resumes_affected_section_only(
    tmp_path: Path,
) -> None:
    """F3/F4: a repository-lane callback is executed by the local route
    machinery, fulfilled, and the resume regenerates only the affected
    section — the unaffected section's checkpoint stays byte-identical."""
    paths = _base_paths(tmp_path)
    claims = AtomicClaimSetV3.model_validate_json(
        Path(paths["atomic_claims_v3"]).read_text()
    )
    _add_completeness_row(paths, MethodCompletenessItemV1(
        obligation_id="O-MAIN-LOCAL",
        status="unverified_by_repository",
        claim_ids=(claims.claims[0].claim_id,),
        importance="critical",
        reason="No supported code fact covers the remaining behavior.",
    ))

    def caller(_config, request):
        grounding = request.input_payload.get("grounding_contract") or {}
        unanchored = tuple(grounding.get("unanchored_required_moves") or ())
        return _callback_request(
            request,
            moves_to_request=unanchored[:1] or ("limitations_or_mismatch",),
        )

    first, first_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=caller,
    )
    assert first.status == "incomplete"
    bundle_path = Path(first_outputs["writing_research_callback_artifacts_v1"])
    bundle = json.loads(bundle_path.read_text())
    open_requests = [
        item for item in bundle["requests"]
        if item["status"] == "open"
        and item["required_authority_lane"] == "executable_hard"
    ]
    assert open_requests

    # F1: the local route executor fulfills repository-lane requests through
    # the supplied repository provider (existing research tools surface).
    requests = [
        WritingResearchRequestV1.model_validate(item)
        for item in open_requests
    ]
    artifacts = execute_open_requests_for_routes(
        requests,
        repository_provider=lambda request: {
            "artifact_id": "artifact:gap-resolved",
            "authority_lane": "executable_hard",
            "artifact_ref": "span:encoder.py:5:6",
            "artifact_digest": "sha256:gap-resolved-span",
        },
    )
    assert set(artifacts) == {item.request_id for item in requests}
    fulfilled = fulfill_writing_research_callbacks(bundle_path, artifacts)
    assert fulfilled.resume_section_ids == ("MA-S1",)

    # The unaffected section checkpoint is immutable between runs.
    checkpoint_before = json.loads(
        Path(first_outputs["publication_section_checkpoint_v1"]).read_text()
    )
    checkpoint_root = Path(first_outputs["publication_section_checkpoint_v1"]).parent

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
                    "## Encoder\n\nThe encoder reads the configured input."
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

    paths.update(first_outputs)
    resumed, resumed_outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=resumed_caller,
    )
    assert resumed.status == "incomplete"
    assert resumed.resumed_section_ids == ("MA-S1",)
    assert resumed_calls == ["MA-S1"]
    # Resume artifacts consumed: the callback bundle clears the replay marker.
    resumed_bundle = json.loads(
        Path(resumed_outputs["writing_research_callback_artifacts_v1"]).read_text()
    )
    assert resumed_bundle["resume_section_ids"] == []
    # The unaffected checkpoint store is byte-identical (no section was
    # regenerated outside MA-S1).
    checkpoint_after = json.loads(
        Path(resumed_outputs["publication_section_checkpoint_v1"]).read_text()
    )
    for section_id, row in checkpoint_before["sections"].items():
        if section_id == "MA-S1":
            continue
        assert checkpoint_after["sections"][section_id] == row
        store_ref = Path(row["output_ref"])
        store_path = checkpoint_root / store_ref
        assert store_path.is_file()


def _completed_moves(binding: dict) -> list[str]:
    return list(binding.get("anchored_required_rhetorical_moves") or ())


def test_external_queue_builder_never_drops_requests() -> None:
    """F2 unit: author/empirical/literature requests always produce queue
    items with a non-empty proposed body; local-lane requests do not."""
    requests = [
        WritingResearchRequestV1(
            request_id="request:author",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="design_objective",
            exact_question="Which author-confirmed objective applies?",
            required_authority_lane="author_attested",
        ),
        WritingResearchRequestV1(
            request_id="request:empirical",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="inference_and_output",
            exact_question="Which experimental artifact reports the metric?",
            required_authority_lane="empirical_artifact",
        ),
        WritingResearchRequestV1(
            request_id="request:literature",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="limitations_or_mismatch",
            exact_question="Which citation supports the baseline claim?",
            required_authority_lane="external_literature",
        ),
        WritingResearchRequestV1(
            request_id="request:local",
            section_id="MA-S1",
            argument_unit_id="MA-S1:unit",
            missing_rhetorical_move="algorithm_or_data_flow",
            exact_question="Which span resolves the flow?",
            required_authority_lane="executable_hard",
        ),
    ]
    items = build_external_research_queue_items(requests)
    assert len(items) == 3
    lanes = {item.lane for item in items}
    assert lanes == {"author_attested", "empirical_artifact", "external_literature"}
    for item in items:
        assert item.proposed_body.strip()
        assert item.exact_question.strip()
        assert item.status == "queued"
