from __future__ import annotations

import json

import pytest

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    EvidencePacketSetV3,
    EvidencePacketV3,
    EvidenceSpanV3,
)
from code2paper.agentic.method_argument_models import MethodCompletenessItemV1, MethodCompletenessMatrixV1
from code2paper.agentic.method_product_models import AuthorStoryNodeV1
from code2paper.agentic.method_proposition_compiler import (
    _merge_proposition_repair,
    _validate_proposal,
    compile_method_propositions,
)
from code2paper.agentic.method_proposition_models import (
    MethodPropositionProposalBatchV1,
    MethodPropositionProposalV1,
    PropositionCandidateClusterV1,
    PropositionBindingSidecarV1,
)
from code2paper.agentic.method_proposition_provider import build_method_proposition_architect
from code2paper.agentic.method_proposition_provider import _bind_source_fragments
from code2paper.agentic.method_proposition_provider import _dedupe_proposals
from code2paper.agentic.method_proposition_evidence_provider import (
    build_method_proposition_evidence_judge,
)
from code2paper.llm.client import LLMResponse
from code2paper.schemas import LLMConfig, LLMProvider


def _inputs():
    span = EvidenceSpanV3(
        span_id="S1", snapshot_id="snap", project_tree_hash="tree", path="model.py",
        symbol="Model.features", line_start=1, line_end=2, exact_excerpt="x = stack([color, scale])",
        excerpt_digest="sha256:e", file_digest="sha256:f", role="anchor",
    )
    packets = EvidencePacketSetV3(
        repo_snapshot_id="snap", project_tree_hash="tree",
        packets=[EvidencePacketV3(
            packet_id="EP1", obligation_tags=["O-FEATURE"], scope="Model.features",
            anchor_span_ids=["S1"], spans=[span], source_digest="sha256:p",
        )], content_digest="sha256:packets",
    )
    fact = CodeFactV1(
        fact_id="F1", subject="Model.features", predicate="stacks",
        object=["color", "scale"], scope="Model.features", direct_span_ids=["S1"],
        exact_source_digest="sha256:e", canonical_identity="sha256:fact",
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree", evidence_packet_digest="sha256:packets",
        facts=[fact], content_digest="sha256:facts",
    )
    claim = AtomicClaimV3(
        claim_id="C1", canonical_text="Model.features stacks color and scale into a descriptor.",
        fact_ids=["F1"], covers_obligation_ids=["O-FEATURE"], direct_evidence_ids=["S1"],
        allowed_wording_boundary="only the descriptor composition", canonical_identity="sha256:claim",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="snap", project_tree_hash="tree", evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts", claims=[claim], content_digest="sha256:claims",
    )
    completeness = MethodCompletenessMatrixV1(items=(
        MethodCompletenessItemV1(
            obligation_id="O-FEATURE", role="feature extraction",
            statement="Construct a per-primitive descriptor from color and scale.",
            status="supported_by_repository", matched_fact_ids=("F1",), matched_span_ids=("S1",),
        ),
        MethodCompletenessItemV1(
            obligation_id="O-INFERENCE", role="deployment",
            statement="At deployment, the intended path avoids rendering.",
            status="author_confirmation_required", reason="repository evidence is not yet available",
        ),
    ))
    spine = (
        AuthorStoryNodeV1(
            story_node_id="ST-F", title="Feature extraction", author_statement="Build the descriptor.",
            linked_obligation_ids=("O-FEATURE",), evidence_lane="repository_verified",
        ),
        AuthorStoryNodeV1(
            story_node_id="ST-D", title="Deployment", author_statement="Avoid rendering.",
            linked_obligation_ids=("O-INFERENCE",), evidence_lane="author_intent_unverified",
        ),
    )
    return claims, facts, packets, completeness, spine


def _architect(cluster):
    if cluster.origin == "repository_evidence":
        return MethodPropositionProposalV1(
            cluster_id=cluster.cluster_id, used_claim_ids=cluster.claim_ids,
            used_fact_ids=cluster.fact_ids, used_relation_ids=cluster.relation_ids,
            reader_subject="the per-primitive descriptor", transformation="combines complementary attributes",
            inputs=("color", "scale"), outputs=("descriptor",),
            paper_terms=("per-primitive descriptor",), implementation_binding_terms=cluster.subjects,
            source_statement_fragments=(cluster.source_statements[0],),
        )
    return MethodPropositionProposalV1(
        cluster_id=cluster.cluster_id,
        reader_subject="the deployment path", transformation="is intended to avoid rendering",
        paper_terms=("rendering-free inference",),
        source_statement_fragments=(cluster.source_statements[0],),
    )


def test_compile_propositions_separates_repository_and_author_authority():
    claims, facts, packets, completeness, spine = _inputs()
    result, sidecar, clusters = compile_method_propositions(
        claims=claims, facts=facts, packets=packets, completeness=completeness,
        story_spine=spine, proposal_architect=_architect,
    )
    assert len(clusters) == 2
    assert len(result.propositions) == 2
    verified = next(item for item in result.propositions if item.origin == "repository_evidence")
    candidate = next(item for item in result.propositions if item.origin == "author_intent")
    assert verified.may_enter_verified is True
    assert verified.requires_caveat is False
    assert verified.section_hints == ("ST-F",)
    evidence_cluster = next(
        item for item in clusters if item.origin == "repository_evidence"
    )
    assert evidence_cluster.author_term_hints == (
        "Feature extraction",
        "Build the descriptor.",
    )
    assert candidate.may_enter_verified is False
    assert candidate.requires_caveat is True
    assert candidate.section_hints == ("ST-D",)
    assert len(sidecar.bindings) == 2
    assert result.binding_sidecar_digest == sidecar.content_digest


def test_missing_architect_yields_typed_gaps_not_harness_prose():
    claims, facts, packets, completeness, spine = _inputs()
    result, sidecar, clusters = compile_method_propositions(
        claims=claims, facts=facts, packets=packets, completeness=completeness,
        story_spine=spine, proposal_architect=None,
    )
    assert not result.propositions
    assert len(result.gaps) == len(clusters)
    assert {item.reason for item in result.gaps} == {"proposal_missing"}
    assert not sidecar.bindings


def test_architect_cannot_promote_unknown_evidence_ids_without_source_fragments():
    claims, facts, packets, completeness, spine = _inputs()

    def bad_architect(cluster):
        return MethodPropositionProposalV1(
            cluster_id=cluster.cluster_id, used_claim_ids=("C-UNKNOWN",),
            used_fact_ids=cluster.fact_ids, reader_subject="method", transformation="operates",
            conditions=cluster.required_qualifiers,
        )

    result, sidecar, _clusters = compile_method_propositions(
        claims=claims, facts=facts, packets=packets, completeness=completeness,
        story_spine=spine, proposal_architect=bad_architect,
    )
    assert not result.propositions
    assert "source_fragment_not_closed" in {item.reason for item in result.gaps}
    assert all(
        "C-UNKNOWN" not in binding.claim_ids
        for binding in sidecar.bindings
    )


def test_low_level_support_does_not_swallow_unresolved_author_intent_for_same_obligation():
    claims, facts, packets, completeness, spine = _inputs()
    row = completeness.items[0].model_copy(update={
        "status": "partially_supported_by_repository",
        "reason": "the full 15-dimensional composition remains unverified",
    })
    completeness = completeness.model_copy(update={"items": (row, *completeness.items[1:])})
    result, _sidecar, clusters = compile_method_propositions(
        claims=claims, facts=facts, packets=packets, completeness=completeness,
        story_spine=spine, proposal_architect=_architect,
    )
    same_obligation = [
        cluster for cluster in clusters if "O-FEATURE" in cluster.obligation_ids
    ]
    assert {cluster.origin for cluster in same_obligation} == {
        "repository_evidence", "author_intent",
    }
    propositions = [
        item for item in result.propositions if "O-FEATURE" in item.source_obligation_ids
    ]
    assert any(item.may_enter_verified for item in propositions)
    assert any(item.requires_caveat and not item.may_enter_verified for item in propositions)


def test_duplicate_author_cards_are_removed_but_distinct_concepts_remain():
    cluster = PropositionCandidateClusterV1(
        cluster_id="PC-AUTHOR",
        origin="author_intent",
        obligation_ids=("O-AUTHOR",),
        source_statements=("Construct a 15-dimensional descriptor and normalize it.",),
        evidence_lane="repository_partial",
    )
    first = MethodPropositionProposalV1(
        cluster_id=cluster.cluster_id,
        reader_subject="15-dimensional descriptor",
        transformation="is constructed",
        source_statement_fragments=cluster.source_statements,
    )
    normalization = first.model_copy(update={"transformation": "is normalized"})
    assert _dedupe_proposals(cluster, (first, first, normalization)) == (
        first, normalization,
    )


def test_owner_repair_preserves_valid_concepts_and_adds_missing_card():
    first = MethodPropositionProposalV1(
        cluster_id="PC-REPAIR",
        reader_subject="anisotropy",
        transformation="is computed from directional samples",
        source_statement_fragments=("compute anisotropy",),
    )
    missing = MethodPropositionProposalV1(
        cluster_id="PC-REPAIR",
        reader_subject="descriptor",
        transformation="is percentile normalized",
        source_statement_fragments=("normalize descriptor",),
    )
    assert _merge_proposition_repair(
        preserved=(first,), repaired=(first, missing),
    ) == (first, missing)


def test_repository_card_rejects_purpose_meta_language_and_missing_io_fields():
    cluster = PropositionCandidateClusterV1(
        cluster_id="PC-CONCEPT",
        origin="repository_evidence",
        claim_ids=("C1",),
        fact_ids=("F1",),
        span_ids=("S1",),
        source_statements=(
            "Model.features concatenates color and scale, result=descriptor",
        ),
        evidence_lane="repository_verified",
    )
    verbose = MethodPropositionProposalV1(
        cluster_id=cluster.cluster_id,
        used_claim_ids=("C1",),
        used_fact_ids=("F1",),
        reader_subject="the descriptor",
        transformation=(
            "concatenates color and scale for downstream pruning decisions. "
            "The binding harness maps the operation."
        ),
        source_statement_fragments=cluster.source_statements,
    )
    assert _validate_proposal(cluster, verbose) == "concept_not_atomic"
    concise_without_fields = verbose.model_copy(update={
        "transformation": "concatenates the attribute components",
    })
    assert _validate_proposal(cluster, concise_without_fields) == "concept_fields_missing"
    concise = concise_without_fields.model_copy(update={
        "inputs": ("color", "scale"),
        "outputs": ("descriptor",),
    })
    assert _validate_proposal(cluster, concise) == ""


def test_repository_partial_proposition_never_enters_verified_even_with_qualifier():
    claims, facts, packets, completeness, spine = _inputs()
    partial_claim = claims.claims[0].model_copy(update={
        "status": "partial",
        "required_qualifiers": ["when color is available"],
    })
    claims = claims.model_copy(update={"claims": [partial_claim]})
    completeness = completeness.model_copy(update={
        "items": (
            completeness.items[0].model_copy(update={
                "status": "partially_supported_by_repository",
            }),
            completeness.items[1],
        ),
    })

    def architect(cluster):
        proposal = _architect(cluster)
        if cluster.origin == "repository_evidence":
            return proposal.model_copy(update={
                "conditions": ("when color is available",),
            })
        return proposal

    result, _sidecar, _clusters = compile_method_propositions(
        claims=claims,
        facts=facts,
        packets=packets,
        completeness=completeness,
        story_spine=spine,
        proposal_architect=architect,
    )

    repository = next(
        item for item in result.propositions if item.origin == "repository_evidence"
    )
    assert repository.evidence_lane == "repository_partial"
    assert repository.requires_caveat is True
    assert repository.may_enter_verified is False


def test_disconnected_claims_under_one_obligation_form_separate_clusters():
    claims, facts, packets, completeness, spine = _inputs()
    facts = facts.model_copy(update={"facts": [
        *facts.facts,
        facts.facts[0].model_copy(update={
            "fact_id": "F2", "subject": "Other.loss", "predicate": "computes",
            "object": "entropy", "direct_span_ids": ["S2"],
        }),
    ]})
    packet = packets.packets[0]
    packets = packets.model_copy(update={"packets": [packet.model_copy(update={
        "anchor_span_ids": ["S1", "S2"],
        "spans": [
            *packet.spans,
            packet.spans[0].model_copy(update={
                "span_id": "S2", "symbol": "Other.loss", "exact_excerpt": "loss = entropy(x)",
            }),
        ],
    })]})
    claims = claims.model_copy(update={"claims": [
        *claims.claims,
        claims.claims[0].model_copy(update={
            "claim_id": "C2", "canonical_text": "Other.loss computes entropy.",
            "fact_ids": ["F2"], "direct_evidence_ids": ["S2"],
        }),
    ]})
    from code2paper.agentic.method_proposition_compiler import build_proposition_candidate_clusters
    clusters = build_proposition_candidate_clusters(
        claims=claims, facts=facts, packets=packets,
        completeness=completeness, story_spine=spine,
    )
    evidence_clusters = [item for item in clusters if item.origin == "repository_evidence"]
    assert {item.claim_ids for item in evidence_clusters} == {("C1",), ("C2",)}


def test_broad_author_intent_cluster_can_decompose_into_atomic_propositions():
    claims, facts, packets, completeness, spine = _inputs()
    broad = completeness.items[1].model_copy(update={
        "statement": (
            "At deployment, the intended 3-layer predictor applies a sigmoid and avoids "
            "rendering; during training, it combines 2 losses."
        ),
    })
    completeness = completeness.model_copy(update={
        "items": (completeness.items[0], broad),
    })

    def decomposing_architect(cluster):
        if cluster.origin == "repository_evidence":
            return _architect(cluster)
        return MethodPropositionProposalBatchV1(
            cluster_id=cluster.cluster_id,
            proposals=(
                MethodPropositionProposalV1(
                    cluster_id=cluster.cluster_id,
                    reader_subject="the 3-layer deployment predictor",
                    transformation="is intended to map scores through a sigmoid",
                    outputs=("importance scores",),
                    source_statement_fragments=("the intended 3-layer predictor applies a sigmoid",),
                ),
                MethodPropositionProposalV1(
                    cluster_id=cluster.cluster_id,
                    reader_subject="the deployment path",
                    transformation="is intended to avoid rendering",
                    source_statement_fragments=("avoids rendering",),
                ),
                MethodPropositionProposalV1(
                    cluster_id=cluster.cluster_id,
                    reader_subject="the training objective",
                    transformation="is intended to combine two losses",
                    inputs=("two losses",),
                    source_statement_fragments=("it combines 2 losses",),
                ),
            ),
        )

    result, sidecar, _clusters = compile_method_propositions(
        claims=claims,
        facts=facts,
        packets=packets,
        completeness=completeness,
        story_spine=spine,
        proposal_architect=decomposing_architect,
    )

    candidate = [
        item for item in result.propositions if item.origin == "author_intent"
    ]
    assert len(candidate) == 3
    assert len({item.proposition_id for item in candidate}) == 3
    assert all(item.requires_caveat and not item.may_enter_verified for item in candidate)
    by_subject = {item.reader_subject: item for item in candidate}
    assert by_subject["the 3-layer deployment predictor"].immutable_numeric_tokens == ("3",)
    assert by_subject["the deployment path"].immutable_numeric_tokens == ()
    assert by_subject["the training objective"].immutable_numeric_tokens == ("2",)
    assert len(sidecar.bindings) == 4


def test_repository_decomposition_binds_only_selected_claim_spans_and_qualifiers():
    claims, facts, packets, completeness, spine = _inputs()
    second_span = packets.packets[0].spans[0].model_copy(update={
        "span_id": "S2", "symbol": "Model.normalize",
        "exact_excerpt": "normalized = normalize(descriptor)",
        "excerpt_digest": "sha256:e2", "file_digest": "sha256:f2",
    })
    packets = packets.model_copy(update={
        "packets": [packets.packets[0].model_copy(update={
            "spans": [*packets.packets[0].spans, second_span],
            "anchor_span_ids": [*packets.packets[0].anchor_span_ids, "S2"],
        })],
    })
    second_fact = facts.facts[0].model_copy(update={
        "fact_id": "F2", "subject": "Model.normalize", "predicate": "normalizes",
        "object": "descriptor", "direct_span_ids": ["S2"],
        "canonical_identity": "sha256:fact2",
    })
    facts = facts.model_copy(update={"facts": [*facts.facts, second_fact]})
    second_claim = claims.claims[0].model_copy(update={
        "claim_id": "C2", "canonical_text": "Model.normalize normalizes the descriptor.",
        "fact_ids": ["F2"], "direct_evidence_ids": ["S2"],
        "required_qualifiers": ["only during evaluation"],
        "canonical_identity": "sha256:claim2",
    })
    claims = claims.model_copy(update={"claims": [*claims.claims, second_claim]})

    def split_architect(cluster):
        if cluster.origin == "author_intent":
            return _architect(cluster)
        return MethodPropositionProposalBatchV1(
            cluster_id=cluster.cluster_id,
            proposals=tuple(
                MethodPropositionProposalV1(
                    cluster_id=cluster.cluster_id,
                    used_claim_ids=(claim_id,), used_fact_ids=(fact_id,),
                    reader_subject="the descriptor",
                    transformation=("combines attributes" if claim_id == "C1" else "is normalized"),
                    inputs=(("color", "scale") if claim_id == "C1" else ()),
                    conditions=(("only during evaluation",) if claim_id == "C2" else ()),
                    source_statement_fragments=(statement,),
                )
                for claim_id, fact_id, statement in zip(
                    cluster.claim_ids, cluster.fact_ids, cluster.source_statements, strict=True
                )
            ),
        )

    result, sidecar, _clusters = compile_method_propositions(
        claims=claims, facts=facts, packets=packets, completeness=completeness,
        story_spine=spine, proposal_architect=split_architect,
    )
    repository = [item for item in result.propositions if item.origin == "repository_evidence"]
    bindings = {item.proposition_id: item for item in sidecar.bindings}
    assert len(repository) == 2
    first = next(item for item in repository if item.transformation == "combines attributes")
    second = next(item for item in repository if item.transformation == "is normalized")
    assert bindings[first.proposition_id].span_ids == ("S1",)
    assert first.required_qualifiers == ()
    assert bindings[second.proposition_id].span_ids == ("S2",)
    assert second.required_qualifiers == ("only during evaluation",)


def test_architect_source_fragment_must_be_exactly_from_author_statement():
    claims, facts, packets, completeness, spine = _inputs()

    def inventing_architect(cluster):
        if cluster.origin == "repository_evidence":
            return _architect(cluster)
        return MethodPropositionProposalV1(
            cluster_id=cluster.cluster_id,
            reader_subject="the deployment path",
            transformation="avoids rendering",
            source_statement_fragments=("invented 10x speedup",),
        )

    result, _sidecar, _clusters = compile_method_propositions(
        claims=claims,
        facts=facts,
        packets=packets,
        completeness=completeness,
        story_spine=spine,
        proposal_architect=inventing_architect,
    )

    assert {item.reason for item in result.gaps} == {"source_fragment_not_closed"}


def test_architect_cannot_add_unsupported_benefit_or_condition():
    claims, facts, packets, completeness, spine = _inputs()

    def expanding_architect(cluster):
        proposal = _architect(cluster)
        if cluster.origin == "repository_evidence":
            return proposal.model_copy(update={
                "transformation": "improves accuracy",
            })
        return proposal.model_copy(update={
            "conditions": ("when a hidden deployment flag is enabled",),
        })

    result, _sidecar, _clusters = compile_method_propositions(
        claims=claims,
        facts=facts,
        packets=packets,
        completeness=completeness,
        story_spine=spine,
        proposal_architect=expanding_architect,
    )

    reasons = {item.reason for item in result.gaps}
    assert {"authority_expansion", "condition_not_closed"} <= reasons
    assert "concept_coverage_missing" in reasons


def test_live_architect_contract_requests_and_parses_atomic_proposal_batch():
    claims, facts, packets, completeness, spine = _inputs()
    from code2paper.agentic.method_proposition_compiler import build_proposition_candidate_clusters

    cluster = next(
        item for item in build_proposition_candidate_clusters(
            claims=claims,
            facts=facts,
            packets=packets,
            completeness=completeness,
            story_spine=spine,
        )
        if item.origin == "author_intent"
    )
    calls = []

    def caller(config, request):
        calls.append((config, request))
        return LLMResponse(
            text=json.dumps({
                "cluster_id": cluster.cluster_id,
                "proposals": [
                    {
                        "cluster_id": cluster.cluster_id,
                        "reader_subject": "the deployment path",
                        "transformation": "is intended to avoid rendering",
                        "source_statement_fragments": [cluster.source_statements[0]],
                    },
                    {
                        "cluster_id": cluster.cluster_id,
                        "reader_subject": "the deployment output",
                        "transformation": "is intended to remain rendering-free",
                        "source_statement_fragments": [cluster.source_statements[0]],
                    },
                ],
            }),
            response_hash="sha256:proposal-batch",
            finish_reason="stop",
        )

    architect = build_method_proposition_architect(
        LLMConfig(
            provider=LLMProvider.OPENAI,
            model="fixture",
            cache=False,
        ),
        llm_caller=caller,
    )
    batch = architect(cluster)

    assert len(batch.proposals) == 2
    assert calls[0][1].schema_name == "MethodPropositionProposalBatchV1"
    public_schema = json.dumps(calls[0][1].response_json_schema)
    assert "used_claim_ids" not in public_schema
    assert "used_fact_ids" not in public_schema
    assert "used_relation_ids" not in public_schema
    assert "cluster_id" not in public_schema
    assert calls[0][0].temperature == 0.0
    assert "at most six non-overlapping cards" in calls[0][1].prompt


def test_repository_architect_gets_code_derived_reader_terms_not_author_prose():
    claims, facts, packets, completeness, spine = _inputs()
    from code2paper.agentic.method_proposition_compiler import build_proposition_candidate_clusters

    fact = facts.facts[0].model_copy(update={
        "subject": "Model.get_input_f15",
        "object": ["f_p_avg_dists_z_score_local", "f_p_volumn_z_score_global"],
    })
    facts = facts.model_copy(update={"facts": [fact]})
    cluster = next(
        item for item in build_proposition_candidate_clusters(
            claims=claims,
            facts=facts,
            packets=packets,
            completeness=completeness,
            story_spine=spine,
        )
        if item.origin == "repository_evidence"
    )
    calls = []

    def caller(_config, request):
        calls.append(request)
        return LLMResponse(
            text=json.dumps({
                "cluster_id": cluster.cluster_id,
                "proposals": [{
                    "cluster_id": cluster.cluster_id,
                    "reader_subject": "the descriptor",
                    "transformation": "combines attributes",
                    "source_statement_fragments": [cluster.source_statements[0]],
                }],
            }),
            response_hash="sha256:terms",
            finish_reason="stop",
        )

    build_method_proposition_architect(
        LLMConfig(provider=LLMProvider.OPENAI, model="fixture", cache=False),
        llm_caller=caller,
    )(cluster)

    payload = calls[0].input_payload
    assert "author_term_hints" not in payload
    rendered = {item["reader_term_hint"] for item in payload["code_term_hints"]}
    assert any("15-dimensional feature" in item for item in rendered)
    assert any("average distances z-score local" in item for item in rendered)
    assert any("volume z-score global" in item for item in rendered)
    assert set(payload) == {
        "origin", "evidence_lane", "source_statements",
        "source_semantics", "code_term_hints",
    }
    serialized = json.dumps(payload)
    for forbidden in (
        "cluster_id", "obligation_ids", "claim_ids", "fact_ids", "span_ids",
        "section_hints", "content_digest", "claim_required_qualifiers",
    ):
        assert forbidden not in serialized


def test_repository_fragment_binding_adds_only_needed_sibling_statement():
    cluster = PropositionCandidateClusterV1(
        cluster_id="PC-COVER",
        origin="repository_evidence",
        obligation_ids=("O1",),
        claim_ids=("C1", "C2", "C3"),
        fact_ids=("F1", "F2", "F3"),
        fact_connectivity_edges=(("F1", "F2"), ("F2", "F3")),
        span_ids=("S1", "S2", "S3"),
        source_statements=(
            "features concatenates local and global descriptor components",
            "features calls percentile normalize on the descriptor",
            "features returns an unrelated cache record",
        ),
        subjects=("features",),
        predicates=("concatenates", "calls", "returns"),
        operands=("descriptor", "percentile normalize", "cache"),
        evidence_lane="repository_verified",
    )
    proposal = MethodPropositionProposalV1(
        cluster_id=cluster.cluster_id,
        reader_subject="the descriptor",
        transformation="concatenates local and global components and applies percentile normalize",
        source_statement_fragments=(cluster.source_statements[0],),
    )

    bound = _bind_source_fragments(cluster, proposal)

    assert bound.source_statement_fragments == cluster.source_statements[:2]


def test_repository_fragment_binding_removes_irrelevant_model_overbinding():
    cluster = PropositionCandidateClusterV1(
        cluster_id="PC-MIN",
        origin="repository_evidence",
        claim_ids=("C1", "C2", "C3"),
        fact_ids=("F1", "F2", "F3"),
        fact_connectivity_edges=(("F1", "F2"), ("F2", "F3")),
        span_ids=("S1", "S2", "S3"),
        source_statements=(
            "features concatenates color and scale",
            "features normalizes the descriptor",
            "features returns a cache record",
        ),
        subjects=("features",),
        predicates=("concatenates", "normalizes", "returns"),
        operands=("color", "scale", "descriptor", "cache"),
        evidence_lane="repository_verified",
    )
    proposal = MethodPropositionProposalV1(
        cluster_id=cluster.cluster_id,
        reader_subject="the feature descriptor",
        transformation="concatenates color and scale",
        inputs=("color", "scale"),
        source_statement_fragments=cluster.source_statements,
    )

    bound = _bind_source_fragments(cluster, proposal)

    assert bound.source_statement_fragments == (cluster.source_statements[0],)


def test_repository_composition_card_requires_reader_facing_inputs():
    cluster = PropositionCandidateClusterV1(
        cluster_id="PC-INPUTS",
        origin="repository_evidence",
        claim_ids=("C1",),
        fact_ids=("F1",),
        span_ids=("S1",),
        source_statements=("features concatenates color and scale",),
        subjects=("features",),
        predicates=("concatenates",),
        operands=("color", "scale"),
        evidence_lane="repository_verified",
    )
    proposal = MethodPropositionProposalV1(
        cluster_id=cluster.cluster_id,
        used_claim_ids=("C1",),
        used_fact_ids=("F1",),
        reader_subject="the feature descriptor",
        transformation="concatenates the components",
        source_statement_fragments=cluster.source_statements,
    )

    assert _validate_proposal(cluster, proposal) == "concept_fields_missing"


def test_architect_length_failure_requests_compact_owner_retry():
    claims, facts, packets, completeness, spine = _inputs()
    from code2paper.agentic.method_proposition_compiler import build_proposition_candidate_clusters

    cluster = next(
        item for item in build_proposition_candidate_clusters(
            claims=claims,
            facts=facts,
            packets=packets,
            completeness=completeness,
            story_spine=spine,
        )
        if item.origin == "repository_evidence"
    )
    calls = []

    def caller(_config, request):
        calls.append(request)
        if len(calls) == 1:
            return LLMResponse(
                text="not-json",
                response_hash="sha256:truncated",
                finish_reason="length",
            )
        return LLMResponse(
            text=json.dumps({
                "cluster_id": cluster.cluster_id,
                "proposals": [{
                    "cluster_id": cluster.cluster_id,
                    "reader_subject": "the descriptor",
                    "transformation": "combines attributes",
                    "source_statement_fragments": [cluster.source_statements[0]],
                }],
            }),
            response_hash="sha256:repaired",
            finish_reason="stop",
        )

    architect = build_method_proposition_architect(
        LLMConfig(provider=LLMProvider.OPENAI, model="fixture", cache=False),
        llm_caller=caller,
    )
    with pytest.raises(ValueError, match="finish_reason=length") as failed:
        architect(cluster)
    repaired = architect(cluster, str(failed.value))

    assert len(repaired.proposals) == 1
    instruction = calls[1].input_payload["repair"]["instruction"]
    assert "no more than six non-overlapping cards" in instruction
    assert "no explanations outside the JSON object" in instruction
    assert "extend that one card's source fragments" in instruction


def test_architect_replaces_public_correlation_placeholder_with_closed_id():
    claims, facts, packets, completeness, spine = _inputs()
    from code2paper.agentic.method_proposition_compiler import build_proposition_candidate_clusters

    cluster = next(
        item for item in build_proposition_candidate_clusters(
            claims=claims,
            facts=facts,
            packets=packets,
            completeness=completeness,
            story_spine=spine,
        )
        if item.origin == "repository_evidence"
    )
    calls = []

    def caller(_config, request):
        calls.append(request)
        return LLMResponse(
            text=json.dumps({
                "cluster_id": "current",
                "proposals": [{
                    "cluster_id": "current",
                    "reader_subject": "the descriptor",
                    "transformation": "combines attributes",
                    "source_statement_fragments": [],
                }],
            }),
            response_hash="sha256:placeholder",
            finish_reason="stop",
        )

    batch = build_method_proposition_architect(
        LLMConfig(provider=LLMProvider.OPENAI, model="fixture", cache=False),
        llm_caller=caller,
    )(cluster)

    assert "cluster_id" not in calls[0].input_payload
    assert batch.cluster_id == cluster.cluster_id
    assert batch.proposals[0].cluster_id == cluster.cluster_id


def test_compiler_binds_source_fragments_without_id_repair_roundtrip():
    claims, facts, packets, completeness, spine = _inputs()
    feedback: list[str] = []

    def repairing_architect(cluster, validation_error=""):
        feedback.append(validation_error)
        proposal = _architect(cluster)
        return proposal.model_copy(update={
            "used_claim_ids": ("C-OUTSIDE",),
        })

    result, _sidecar, clusters = compile_method_propositions(
        claims=claims,
        facts=facts,
        packets=packets,
        completeness=completeness,
        story_spine=spine,
        proposal_architect=repairing_architect,
    )

    assert len(result.propositions) == len(clusters)
    assert not result.gaps
    assert feedback[0] == ""
    assert all(error == "" for error in feedback)
    assert len(feedback) == len(clusters)


def test_evidence_judge_transport_failure_preserves_caveated_candidate():
    claims, facts, packets, completeness, spine = _inputs()

    def unavailable_judge(_payload):
        raise TimeoutError("stream inactivity")

    result, sidecar, _clusters = compile_method_propositions(
        claims=claims,
        facts=facts,
        packets=packets,
        completeness=completeness,
        story_spine=spine,
        proposal_architect=_architect,
        evidence_judge=unavailable_judge,
        require_evidence_judge=True,
    )

    repository = next(
        item for item in result.propositions if item.origin == "repository_evidence"
    )
    assert repository.evidence_verdict == "not_checked"
    assert repository.may_enter_verified is False
    assert repository.requires_caveat is True
    assert any(item.reason == "evidence_judge_failed" for item in result.gaps)
    assert repository.proposition_id in {item.proposition_id for item in sidecar.bindings}


def test_live_evidence_judge_uses_short_non_retrying_transport_window():
    observed = []

    def caller(config, _request):
        observed.append(config)
        raise TimeoutError("stream inactivity")

    judge = build_method_proposition_evidence_judge(
        LLMConfig(
            provider=LLMProvider.OPENAI,
            model="fixture",
            request_timeout_seconds=1800,
            retry_max_attempts=5,
        ),
        llm_caller=caller,
    )

    with pytest.raises(TimeoutError):
        judge({"proposition_id": "MP-timeout"})

    assert observed[0].request_timeout_seconds == 90
    assert observed[0].retry_max_attempts == 1


def test_live_evidence_judge_batches_cluster_without_exposing_opaque_ids():
    calls = []

    def caller(_config, request):
        calls.append(request)
        rows = request.input_payload["propositions"]
        assert len(rows) == 2
        assert all("proposition_id" not in row for row in rows)
        assert "claim_id" not in json.dumps(rows)
        assert "fact_id" not in json.dumps(rows)
        return LLMResponse(
            text=json.dumps({
                "judgments": [
                    {
                        "judgment_index": index,
                        "status": "entailed",
                        "supported_fields": [
                            "reader_subject", "transformation", "inputs"
                        ],
                        "unsupported_fields": [],
                        "rationale": "The exact row evidence supports the fields.",
                    }
                    for index in (1, 2)
                ]
            }),
            response_hash="sha256:judge-batch",
            finish_reason="stop",
        )

    judge = build_method_proposition_evidence_judge(
        LLMConfig(provider=LLMProvider.OPENAI, model="fixture"),
        llm_caller=caller,
    )
    payloads = [
        {
            "proposition_id": f"MP-{index}",
            "proposed_semantics": {
                "reader_subject": "descriptor",
                "transformation": "combines attributes",
                "inputs": ["color"],
            },
            "required_semantic_fields": [
                "reader_subject", "transformation", "inputs"
            ],
            "selected_atomic_claims": [{"canonical_text": "combines color"}],
            "selected_code_facts": [{
                "subject": "features", "predicate": "concatenates",
                "object": ["color"], "conditions": [],
            }],
            "selected_relations": [],
            "exact_code_excerpts": [{
                "path": "model.py", "symbol": "features",
                "line_start": 1, "line_end": 1,
                "exact_excerpt": "features = cat([color])",
            }],
        }
        for index in (1, 2)
    ]

    verdicts = judge.judge_batch(payloads)

    assert len(calls) == 1
    assert [item.proposition_id for item in verdicts] == ["MP-1", "MP-2"]
    assert all(item.status == "entailed" for item in verdicts)


def test_proposition_cannot_skip_the_connecting_fact_in_evidence_graph():
    cluster = PropositionCandidateClusterV1(
        cluster_id="PC-CONNECTIVITY",
        origin="repository_evidence",
        claim_ids=("C1",),
        fact_ids=("F1", "F2", "F3"),
        fact_connectivity_edges=(("F1", "F2"), ("F2", "F3")),
        span_ids=("S1",),
        source_statements=("A connected three-step transformation.",),
        evidence_lane="repository_verified",
    )
    disconnected = MethodPropositionProposalV1(
        cluster_id=cluster.cluster_id,
        used_claim_ids=("C1",),
        used_fact_ids=("F1", "F3"),
        reader_subject="the transformation",
        transformation="connects its endpoints",
        source_statement_fragments=("A connected three-step transformation.",),
    )
    connected = disconnected.model_copy(update={
        "used_fact_ids": ("F1", "F2", "F3"),
    })

    assert _validate_proposal(cluster, disconnected) == "evidence_not_connected"
    assert _validate_proposal(cluster, connected) == ""


def test_proposition_sidecar_and_set_reject_digest_pinned_mutation():
    claims, facts, packets, completeness, spine = _inputs()
    result, sidecar, _clusters = compile_method_propositions(
        claims=claims,
        facts=facts,
        packets=packets,
        completeness=completeness,
        story_spine=spine,
        proposal_architect=_architect,
    )
    sidecar_payload = sidecar.model_dump(mode="json")
    sidecar_payload["repo_snapshot_id"] = "tampered-snapshot"
    with pytest.raises(ValueError, match="sidecar digest mismatch"):
        PropositionBindingSidecarV1.model_validate(sidecar_payload)

    set_payload = result.model_dump(mode="json")
    set_payload["project_tree_hash"] = "tampered-tree"
    with pytest.raises(ValueError, match="proposition set digest mismatch"):
        type(result).model_validate(set_payload)


# ---------------------------------------------------------------------------
# Q1 — publication-relevance writing roles (plan 19.5.4)
# ---------------------------------------------------------------------------


def test_writing_roles_classify_defensive_vs_material_content() -> None:
    from code2paper.agentic.publication_relevance import classify_fact_writing_role

    defensive = CodeFactV1(
        fact_id="FA", subject="s", predicate="branches_on",
        object=["loss_i.shape[0]", "==", "0"], conditions=("loss_i.shape[0] == 0",),
        scope="s", direct_span_ids=["S1"],
        exact_source_digest="sha256:x", canonical_identity="sha256:fa",
    )
    material = CodeFactV1(
        fact_id="FB", subject="s", predicate="branches_on",
        object=["training mode"], conditions=("mode_is_train",),
        scope="s", direct_span_ids=["S1"],
        exact_source_digest="sha256:x", canonical_identity="sha256:fb",
    )
    central = CodeFactV1(
        fact_id="FC", subject="s", predicate="computes_formula", object=["score"],
        scope="s", direct_span_ids=["S1"],
        exact_source_digest="sha256:x", canonical_identity="sha256:fc",
    )
    loop = CodeFactV1(
        fact_id="FD", subject="s", predicate="loops", object=["i", "range", "len(items)"],
        scope="s", direct_span_ids=["S1"],
        exact_source_digest="sha256:x", canonical_identity="sha256:fd",
    )
    assert classify_fact_writing_role(defensive) == "audit_only"
    assert classify_fact_writing_role(material) == "method_conditional"
    assert classify_fact_writing_role(central) == "method_positive"
    assert classify_fact_writing_role(loop) == "audit_only"


def test_classify_claim_writing_role_on_defensive_shape_claim() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.publication_relevance import classify_claim_writing_role

    defensive = SimpleNamespace(
        claim_id="claim-shape",
        canonical_text="The module branches on loss_i.shape[0] == 0",
        claim_text="The module branches on loss_i.shape[0] == 0",
        fact_ids=(),
        required_qualifiers=(),
    )
    mechanism = SimpleNamespace(
        claim_id="claim-attn",
        canonical_text="Hybrid attention applies a causal mask during encoding",
        claim_text="Hybrid attention applies a causal mask during encoding",
        fact_ids=(),
        required_qualifiers=(),
    )
    assert classify_claim_writing_role(defensive) == "audit_only"
    assert classify_claim_writing_role(mechanism) == "method_positive"


def test_audit_only_propositions_never_enter_writer_view() -> None:
    from code2paper.agentic.method_proposition_models import MethodPropositionV1
    from code2paper.agentic.writer_view_projection import build_writer_view

    positive = MethodPropositionV1(
        proposition_id="MP-P", origin="repository_evidence",
        evidence_lane="repository_verified", may_enter_verified=True,
        reader_subject="the encoder", transformation="reads the configured input",
        writing_role="method_positive",
    )
    audit = MethodPropositionV1(
        proposition_id="MP-A", origin="repository_evidence",
        evidence_lane="repository_verified", may_enter_verified=True,
        reader_subject="the loss reduction",
        transformation="branches when the loss tensor is empty",
        writing_role="audit_only",
    )
    view = build_writer_view(
        heading="Encoder", reader_question="How does it read?",
        section_goal="Explain the encoder.",
        propositions=[positive, audit], callback_opportunities=[],
    )
    assert view.allowed_proposition_ids == ("MP-P",)
    assert view.required_proposition_ids == ("MP-P",)
    assert all(item.proposition_id != "MP-A" for item in view.positive_propositions)
    assert all(item.proposition_id != "MP-A" for item in view.caveated_propositions)
    assert all(item.proposition_id != "MP-A" for item in view.immutable_constraints)


def test_compiler_role_wiring_marks_audit_only_facts() -> None:
    from code2paper.agentic.method_proposition_models import MethodPropositionProposalV1

    span = EvidenceSpanV3(
        span_id="S1", snapshot_id="snap", project_tree_hash="tree", path="model.py",
        symbol="Model.loss", line_start=1, line_end=2,
        exact_excerpt="if loss_i.shape[0] == 0: reduce(loss_i)",
        excerpt_digest="sha256:e", file_digest="sha256:f", role="anchor",
    )
    packets = EvidencePacketSetV3(
        repo_snapshot_id="snap", project_tree_hash="tree",
        packets=[EvidencePacketV3(
            packet_id="EP1", obligation_tags=["O-LOSS"], scope="Model.loss",
            anchor_span_ids=["S1"], spans=[span], source_digest="sha256:p",
        )], content_digest="sha256:packets",
    )
    audit_fact = CodeFactV1(
        fact_id="F2", subject="Model.loss", predicate="branches_on",
        object=["loss_i.shape[0]", "==", "0"], conditions=("loss_i.shape[0] == 0",),
        scope="Model.loss", direct_span_ids=["S1"], exact_source_digest="sha256:e",
        canonical_identity="sha256:fact2",
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        evidence_packet_digest="sha256:packets", facts=[audit_fact],
        content_digest="sha256:facts2",
    )
    claim = AtomicClaimV3(
        claim_id="C2", canonical_text="The loss reduction branches when the loss tensor is empty.",
        fact_ids=["F2"], covers_obligation_ids=["O-LOSS"], direct_evidence_ids=["S1"],
        allowed_wording_boundary="branches when loss is empty", canonical_identity="sha256:claim2",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="snap", project_tree_hash="tree",
        evidence_packet_digest="sha256:packets", code_fact_digest="sha256:facts2",
        claims=[claim], content_digest="sha256:claims2",
    )
    completeness = MethodCompletenessMatrixV1(items=(
        MethodCompletenessItemV1(
            obligation_id="O-LOSS", role="loss reduction",
            statement="Reduce loss when the tensor is empty.",
            status="supported_by_repository", matched_fact_ids=("F2",), matched_span_ids=("S1",),
        ),
    ))
    spine = (
        AuthorStoryNodeV1(
            story_node_id="ST-L", title="Loss reduction",
            author_statement="Reduce loss defensively.",
            linked_obligation_ids=("O-LOSS",), evidence_lane="repository_verified",
        ),
    )

    def architect(cluster):
        return MethodPropositionProposalV1(
            cluster_id=cluster.cluster_id, used_claim_ids=cluster.claim_ids,
            used_fact_ids=cluster.fact_ids, used_relation_ids=cluster.relation_ids,
            reader_subject="the loss reduction",
            transformation="branches when the loss tensor is empty",
            inputs=("loss_i",), outputs=("reduction",),
            paper_terms=("empty-loss branch",), implementation_binding_terms=cluster.subjects,
            source_statement_fragments=(cluster.source_statements[0],),
        )

    result, _sidecar, _clusters = compile_method_propositions(
        claims=claims, facts=facts, packets=packets, completeness=completeness,
        story_spine=spine, proposal_architect=architect,
    )
    assert result.propositions[0].writing_role == "audit_only"
