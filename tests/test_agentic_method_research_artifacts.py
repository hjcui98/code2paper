"""D2.5 vertical tests for reference coverage through Method planning."""

from __future__ import annotations

import json

from code2paper.agentic.equation_claims import (
    bind_equations_to_claims,
    compile_equation_claims,
    derive_equation_proposals_from_facts,
)
from code2paper.agentic.configuration_claims import compile_configuration_claims
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    GENERIC_RESEARCH_PRODUCER_VERSION,
)
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    IntentObligationV2,
)
from code2paper.agentic.method_argument_models import (
    REFERENCE_METHOD_STATUSES,
    MethodCompletenessMatrixV1,
    ReferenceMethodAgendaV1,
    ReferenceMethodObligationV1,
    build_completeness_matrix,
    build_reference_method_agenda,
)
from code2paper.agentic.obligation_fact_alignment import (
    ObligationAlignmentV1,
    ObligationCoverageReportV2,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1
from code2paper.agentic.v3_runtime import write_d25_method_research_artifacts


SNAPSHOT = "repo:d25"
TREE = "sha256:d25-tree"
PACKETS = "sha256:d25-packets"


def _fact(
    fact_id: str,
    *,
    subject: str,
    predicate: str,
    object_value: str | list[str],
    semantic_context: list[str],
    conditions: list[str] | None = None,
    validation_status: str = "supported",
    validation_failures: list[str] | None = None,
) -> CodeFactV1:
    return CodeFactV1(
        fact_id=fact_id,
        subject=subject,
        predicate=predicate,
        object=object_value,
        conditions=conditions or [],
        scope="sym:method",
        direct_span_ids=["span:method.py:10:10"],
        relation_span_ids=["span:entry.py:20:20"],
        relation_evidence_ids=["relation:entrypoint"],
        relation_kinds=["CONFIGURED_BY"] if predicate == "configured_by" else [],
        semantic_context=semantic_context,
        exact_source_digest=f"sha256:exact:{fact_id}",
        canonical_identity=f"sha256:identity:{fact_id}",
        validation_status=validation_status,
        validation_failures=validation_failures or [],
    )


def _intent_graph() -> IntentObligationGraphV2:
    return IntentObligationGraphV2(
        project_goal="explain method",
        method_goal="explain the configured computation",
        implementation_scope="repository",
        obligations=[
            IntentObligationV2(
                obligation_id="obl-main",
                kind="method_mainline",
                priority="must_cover",
                source_field="method_mainline",
                author_text="Explain the configured computation.",
                typed_behavior_targets=(
                    TypedBehaviorTargetV1(
                        target_id="target-main",
                        desired_predicates=("COMPUTE",),
                        search_terms=("configured computation",),
                    ),
                ),
                retrieval_queries=("configured computation",),
            )
        ],
    )


def test_d25_writes_reference_configuration_equation_and_plan_chain(
    tmp_path,
) -> None:
    compute = _fact(
        "fact-compute",
        subject="sym:method",
        predicate="computes_formula",
        object_value=["left_operand", "right_operand"],
        semantic_context=["COMPUTE", "add"],
    )
    configuration = _fact(
        "fact-config",
        subject="dropout",
        predicate="configured_by",
        object_value="0.1",
        semantic_context=["config_access", "dropout"],
    )
    facts = CodeFactSetV1(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id=SNAPSHOT,
        project_tree_hash=TREE,
        evidence_packet_digest=PACKETS,
        facts=[compute, configuration],
        content_digest="sha256:d25-facts",
    )
    claim = AtomicClaimV3(
        claim_id="claim-main",
        canonical_text="The dropout-configured stage computes its output.",
        fact_ids=[compute.fact_id, configuration.fact_id],
        covers_obligation_ids=["obl-main"],
        direct_evidence_ids=["span:method.py:10:10"],
        relation_evidence_ids=["relation:entrypoint"],
        allowed_wording_boundary="exact configured computation only",
        canonical_identity="sha256:claim-main",
        status="supported",
    )
    claims = AtomicClaimSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id=SNAPSHOT,
        project_tree_hash=TREE,
        evidence_packet_digest=PACKETS,
        code_fact_digest=facts.content_digest,
        claims=[claim],
        content_digest="sha256:d25-claims",
    )
    equations, reports = compile_equation_claims(
        derive_equation_proposals_from_facts(facts),
        facts,
        repo_snapshot_id=SNAPSHOT,
        project_tree_hash=TREE,
    )
    equations = bind_equations_to_claims(equations, claims)
    assert reports and all(report.authorized for report in reports)
    coverage = ObligationCoverageReportV2(
        intent_graph_digest=_intent_graph().content_digest,
        fact_set_digest=facts.content_digest,
        claim_set_digest=claims.content_digest,
        items=[
            ObligationAlignmentV1(
                obligation_id="obl-main",
                obligation_kind="method_mainline",
                obligation_priority="must_cover",
                matched_claim_ids=(claim.claim_id,),
                coverage_status="supported",
                rationale="typed facts and claim resolve the obligation",
            )
        ],
        must_cover_count=1,
        terminal_must_cover_count=1,
        supported_must_cover_count=1,
    )

    paths = write_d25_method_research_artifacts(
        tmp_path,
        intent_graph=_intent_graph(),
        coverage_report=coverage,
        fact_set=facts,
        claim_set=claims,
        equation_set=equations,
        method_name="Configured computation",
    )

    assert set(paths) == {
        "reference_method_agenda_v1",
        "method_completeness_matrix_v1",
        "configuration_claims_v1",
        "method_section_plan_v2",
    }
    matrix = json.loads(
        open(paths["method_completeness_matrix_v1"], encoding="utf-8").read()
    )
    assert matrix["items"][0]["status"] == "supported_by_repository"
    assert matrix["items"][0]["equation_ids"]
    assert matrix["items"][0]["configuration_ids"]
    plan = json.loads(open(paths["method_section_plan_v2"], encoding="utf-8").read())
    assert plan["argument_units"][0]["equation_ids"]
    assert plan["argument_units"][0]["configuration_ids"]
    assert plan["argument_units"][0]["information_weight"] > 1


def test_completeness_matrix_preserves_all_nine_terminal_states() -> None:
    obligations = tuple(
        ReferenceMethodObligationV1(
            obligation_id=f"obl-{index}",
            role="method_unit",
            statement=f"Reference unit {index}",
            status=status,
        )
        for index, status in enumerate(REFERENCE_METHOD_STATUSES)
    )
    agenda = ReferenceMethodAgendaV1(obligations=obligations)
    supported_obligation = obligations[0]
    claims = AtomicClaimSetV3(
        repo_snapshot_id=SNAPSHOT,
        project_tree_hash=TREE,
        evidence_packet_digest=PACKETS,
        code_fact_digest="sha256:nine-states-facts",
        claims=[
            AtomicClaimV3(
                claim_id="claim-nine-states",
                canonical_text="A repository-backed unit is supported.",
                fact_ids=["fact-nine-states"],
                covers_obligation_ids=[supported_obligation.obligation_id],
                direct_evidence_ids=["span:method.py:1:1"],
                allowed_wording_boundary="repository-backed unit only",
                canonical_identity="sha256:nine-states-claim",
                status="supported",
            )
        ],
        content_digest="sha256:nine-states-claims",
    )

    matrix: MethodCompletenessMatrixV1 = build_completeness_matrix(
        agenda,
        claim_set=claims,
    )

    assert {item.status for item in matrix.items} == set(REFERENCE_METHOD_STATUSES)
    assert all(item.terminal for item in matrix.items)
    assert all(
        item.next_action
        for item in matrix.items
        if item.status not in {"supported_by_repository", "partially_supported_by_repository"}
    )


def test_paper_or_high_risk_text_cannot_authorize_implementation() -> None:
    graph = IntentObligationGraphV2(
        obligations=[
            IntentObligationV2(
                obligation_id="obl-paper-claim",
                kind="high_risk_claim",
                priority="verify_only",
                source_field="innovation_claims",
                author_text="The paper reports a performance advantage.",
            )
        ]
    )

    agenda = build_reference_method_agenda(graph)
    matrix = build_completeness_matrix(agenda)

    assert agenda.obligations[0].authority_lane == "external_literature"
    assert matrix.items[0].status == "external_evidence_required"
    assert matrix.items[0].status != "supported_by_repository"


def test_configuration_compiler_keeps_actual_default_conditional_and_unreachable_separate() -> None:
    facts = CodeFactSetV1(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id=SNAPSHOT,
        project_tree_hash=TREE,
        evidence_packet_digest=PACKETS,
        facts=[
            _fact(
                "fact-actual",
                subject="dropout",
                predicate="configured_by",
                object_value="0.2",
                semantic_context=["config_access", "entrypoint_override"],
            ),
            _fact(
                "fact-default",
                subject="dropout",
                predicate="reads",
                object_value="0.1",
                semantic_context=["config_access", "definition_default"],
            ),
            _fact(
                "fact-conditional",
                subject="dropout",
                predicate="reads",
                object_value="0.3",
                semantic_context=["config_access", "branch_value"],
                conditions=["training"],
            ),
            _fact(
                "fact-unreachable",
                subject="dropout",
                predicate="reads",
                object_value="0.4",
                semantic_context=["config_access", "dead_branch"],
                validation_status="rejected",
                validation_failures=["unreachable_from_entrypoint"],
            ),
        ],
        content_digest="sha256:configuration-branches",
    )

    compiled = compile_configuration_claims(facts)
    by_state = {claim.state: claim for claim in compiled.claims}

    assert set(by_state) == {"actual", "default", "conditional", "unreachable"}
    assert by_state["actual"].value == "0.2"
    assert by_state["default"].value == "0.1"
    assert by_state["conditional"].conditions == ("training",)
    assert by_state["unreachable"].active is False
    assert "unreachable_from_entrypoint" in by_state["unreachable"].unresolved_reason


def test_paper_code_mismatch_remains_a_distinct_review_state() -> None:
    obligation = ReferenceMethodObligationV1(
        obligation_id="obl-mismatch",
        role="method_unit",
        statement="Check the paper and executable branch.",
    )
    coverage = ObligationCoverageReportV2(
        intent_graph_digest="sha256:mismatch-intent",
        items=[
            ObligationAlignmentV1(
                obligation_id=obligation.obligation_id,
                obligation_kind="mismatch_check",
                obligation_priority="verify_only",
                coverage_status="blocked",
                rationale="paper-code mismatch: the two sources select different branches",
            )
        ]
    )

    matrix = build_completeness_matrix(
        ReferenceMethodAgendaV1(obligations=(obligation,)),
        coverage,
    )

    assert matrix.items[0].status == "paper_code_mismatch"
    assert matrix.items[0].status not in {
        "supported_by_repository",
        "explicit_code_gap",
    }


def test_configuration_access_uses_exact_key_and_unresolved_state() -> None:
    """R8-A: a bare config access compiles to a typed unresolved record whose
    key is the exact access expression (args.input_dim), never the consumer
    function, and whose value is None (the access is not a resolved value)."""
    facts = CodeFactSetV1(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id=SNAPSHOT,
        project_tree_hash=TREE,
        evidence_packet_digest=PACKETS,
        facts=[
            _fact(
                "fact-configured",
                subject="prune_pure_feature",
                predicate="configured_by",
                object_value=["args.input_dim"],
                semantic_context=["LOAD", "args.input_dim", "config_access", "attr_read"],
            ),
        ],
        content_digest="sha256:config-access",
    )

    compiled = compile_configuration_claims(facts)
    assert len(compiled.claims) == 1
    claim = compiled.claims[0]
    assert claim.key == "args.input_dim"
    assert claim.key != "prune_pure_feature"
    assert claim.state == "unresolved"
    assert claim.value is None
    assert claim.active is True
    assert "config_access_unresolved" in claim.unresolved_reason


def test_configuration_access_without_resolution_marker_is_not_actual() -> None:
    """R8-A: a configured_by relation with a direct span is an access, not an
    actual value; only an explicit entrypoint/override marker resolves it."""
    facts = CodeFactSetV1(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id=SNAPSHOT,
        project_tree_hash=TREE,
        evidence_packet_digest=PACKETS,
        facts=[
            _fact(
                "fact-configured",
                subject="prune_pure_feature",
                predicate="configured_by",
                object_value=["args.keep_percent"],
                semantic_context=["LOAD", "args.keep_percent", "config_access", "attr_read"],
            ),
            _fact(
                "fact-override",
                subject="dropout",
                predicate="configured_by",
                object_value="0.2",
                semantic_context=["config_access", "entrypoint_override"],
            ),
        ],
        content_digest="sha256:config-access",
    )

    compiled = compile_configuration_claims(facts)
    by_key = {claim.key: claim for claim in compiled.claims}
    assert by_key["args.keep_percent"].state == "unresolved"
    assert by_key["args.keep_percent"].value is None
    assert by_key["dropout"].state == "actual"
    assert by_key["dropout"].value == "0.2"


def test_configuration_scoping_requires_exact_relation_binding() -> None:
    """R8-A: configurations bind to units only through exact relation evidence
    (override_chain vs claim relation ids), never token/function-name overlap.
    Two units mentioning the same consumer function do not both receive the
    same global configuration set."""
    from code2paper.agentic.method_architect import _configuration_binds_unit

    class _Config:
        def __init__(self, key, override_chain=(), source_fact_ids=()):
            self.key = key
            self.override_chain = tuple(override_chain)
            self.source_fact_ids = tuple(source_fact_ids)

    class _Claim:
        def __init__(self, relation_evidence_ids=(), fact_ids=()):
            self.relation_evidence_ids = tuple(relation_evidence_ids)
            self.fact_ids = tuple(fact_ids)

    input_dim = _Config("args.input_dim", override_chain=("rel:input-dim",))
    keep_percent = _Config("args.keep_percent", override_chain=("rel:keep-percent",))
    units = {
        "model_setup": [
            _Claim(relation_evidence_ids=("rel:input-dim",)),
            _Claim(relation_evidence_ids=("rel:load-model",)),
        ],
        "ranking": [
            _Claim(relation_evidence_ids=("rel:keep-percent",)),
            _Claim(relation_evidence_ids=("rel:sort-scores",)),
        ],
    }
    assert _configuration_binds_unit(input_dim, units["model_setup"]) is True
    assert _configuration_binds_unit(input_dim, units["ranking"]) is False
    assert _configuration_binds_unit(keep_percent, units["model_setup"]) is False
    assert _configuration_binds_unit(keep_percent, units["ranking"]) is True


def test_configuration_unresolved_access_is_renderable_without_value() -> None:
    """R8-A.4: an unresolved configuration access (key only, value None) is
    still renderable content, but declaring an unrendered configuration ID is a
    binding failure, not a pass."""
    from code2paper.agentic.publication_quality import _configuration_rendered

    class _Config:
        key = "args.keep_percent"
        value = None

    assert _configuration_rendered(
        "The prune threshold is selected from args.keep_percent.",
        _Config,
    ) is True
    assert _configuration_rendered(
        "The model prunes by score percentile.",
        _Config,
    ) is False
