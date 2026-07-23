from __future__ import annotations

import json
from unittest.mock import patch

from pydantic import ValidationError

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    IntentObligationV2,
    compile_intent_obligation_graph_v2,
)
from code2paper.agentic.intent_target_proposer import (
    IntentTargetProposalSetV1,
    IntentTargetProposalV1,
    ObligationTargetProposalV1,
    _apply_proposal,
    _MAX_DESIRED_PREDICATES,
    enrich_intent_graph_with_llm,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1
from code2paper.llm.client import LLMResponse
from code2paper.schemas import LLMConfig, LLMProvider


def _graph():
    return compile_intent_obligation_graph_v2(AuthorIntentSummary(
        project_goal="Speculative reasoning",
        method_goal="Generate candidate steps and verify them.",
        implementation_scope="current repository",
        method_mainline="Generate candidate steps and verify them.",
        pipeline_steps=[
            "Draft generation: generate candidate reasoning steps.",
            "Target generation: generate reference reasoning steps.",
        ],
    ))


def _proposal(graph):
    obligations = []
    for obligation in graph.obligations:
        if obligation.priority not in {"must_cover", "should_cover"}:
            continue
        role = "draft_generation" if "Draft" in obligation.author_text else (
            "target_generation" if "Target" in obligation.author_text else "verification"
        )
        deterministic_predicates = sorted({
            predicate
            for target in obligation.typed_behavior_targets
            for predicate in target.desired_predicates
        })
        deterministic_relations = sorted({
            relation
            for target in obligation.typed_behavior_targets
            for relation in target.required_relations
        })
        obligations.append(ObligationTargetProposalV1(
            obligation_id=obligation.obligation_id,
            targets=[IntentTargetProposalV1(
                role=role,
                desired_predicates=deterministic_predicates,
                required_relations=deterministic_relations,
                inputs=["draft prefix" if role == "draft_generation" else "target prefix"],
                transformations=["generate reasoning step"],
                outputs=["candidate step" if role == "draft_generation" else "reference step"],
                search_terms=[role],
            )],
        ))
    return IntentTargetProposalSetV1(obligations=obligations)


def test_proposal_normalization_preserves_distinct_draft_and_target_roles() -> None:
    graph = _graph()
    enriched, report = _apply_proposal(graph, [
        item for item in graph.obligations
        if item.priority in {"must_cover", "should_cover"}
    ], _proposal(graph))

    assert report.accepted is True
    targets = {
        item.author_text: item.typed_behavior_targets[0]
        for item in enriched.obligations
        if item.kind == "stage"
    }
    draft = next(target for text, target in targets.items() if "Draft" in text)
    target = next(target for text, target in targets.items() if "Target" in text)
    assert draft.role == "draft_generation"
    assert target.role == "target_generation"
    assert draft.inputs != target.inputs
    assert draft.outputs != target.outputs
    assert draft.target_id != target.target_id
    assert enriched.content_digest != graph.content_digest


def test_proposal_with_incomplete_obligation_ids_is_rejected_atomically() -> None:
    graph = _graph()
    proposal = _proposal(graph)
    proposal.obligations.pop()
    enriched, report = _apply_proposal(graph, [
        item for item in graph.obligations
        if item.priority in {"must_cover", "should_cover"}
    ], proposal)

    assert enriched is graph
    assert report.accepted is False
    assert report.failure == "obligation_id_set_mismatch"


def test_proposal_cannot_erase_nonempty_deterministic_target() -> None:
    graph = _graph()
    proposal = _proposal(graph)
    proposal.obligations[0] = ObligationTargetProposalV1(
        obligation_id=proposal.obligations[0].obligation_id,
        targets=[],
    )

    enriched, report = _apply_proposal(graph, [
        item for item in graph.obligations
        if item.priority in {"must_cover", "should_cover"}
    ], proposal)

    assert enriched is graph
    assert report.accepted is False
    assert report.failure.startswith("normalization_failed:empty_executable_target:")


def test_proposal_cannot_drop_deterministic_predicate_requirement() -> None:
    graph = _graph()
    proposal = _proposal(graph)
    item = proposal.obligations[0]
    existing = item.targets[0]
    # Keep a syntactically non-empty target while replacing its required
    # behavior token, so this exercises the preservation check rather than
    # the earlier empty-target check.
    dropped = existing.model_copy(update={"desired_predicates": ["READ"]})
    proposal.obligations[0] = item.model_copy(update={"targets": [dropped]})

    enriched, report = _apply_proposal(graph, [
        item for item in graph.obligations
        if item.priority in {"must_cover", "should_cover"}
    ], proposal)

    assert enriched is graph
    assert report.accepted is False
    assert report.failure.startswith(
        "normalization_failed:dropped_deterministic_requirement:"
    )


def test_unknown_behavior_predicate_is_schema_rejected() -> None:
    try:
        IntentTargetProposalV1(desired_predicates=["HALLUCINATE"])
    except ValueError as exc:
        assert "unknown behavior predicates" in str(exc)
    else:
        raise AssertionError("unknown predicate must be rejected")


def test_provider_none_retains_deterministic_graph_without_attempt() -> None:
    graph = _graph()
    enriched, report = enrich_intent_graph_with_llm(
        graph,
        LLMConfig(provider=LLMProvider.NONE),
    )
    assert enriched is graph
    assert report.attempted is False
    assert report.accepted is False


def test_live_path_parses_structured_proposal_and_records_role_config() -> None:
    graph = _graph()
    payload = json.dumps(_proposal(graph).model_dump(mode="json"))
    response = LLMResponse(
        text=payload,
        response_hash="sha256:intent",
        response_mode="json_schema",
        finish_reason="stop",
        token_usage={"output_tokens": 500},
    )
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gemma4-31b-nvfp4",
        cache=False,
    )
    with (
        patch(
            "code2paper.agentic.intent_target_proposer.has_provider_api_key",
            return_value=True,
        ),
        patch(
            "code2paper.agentic.intent_target_proposer.LLMClient.complete",
            return_value=response,
        ) as complete,
    ):
        enriched, report = enrich_intent_graph_with_llm(graph, config)

    assert complete.call_count == 1
    assert report.accepted is True
    assert report.response_metadata["role"] == "intent_compiler"
    assert report.response_metadata["max_output_tokens"] == 4096
    assert enriched.content_digest == report.enriched_graph_digest


def test_live_path_repairs_only_the_rejected_obligation_with_short_budget() -> None:
    """One empty item gets a bounded retry; whole-graph validation stays atomic."""

    graph = _graph()
    full = _proposal(graph)
    broken = full.model_copy(deep=True)
    broken.obligations[0] = broken.obligations[0].model_copy(update={"targets": []})
    repair = IntentTargetProposalSetV1(obligations=[full.obligations[0]])
    responses = [
        LLMResponse(
            text=json.dumps(broken.model_dump(mode="json")),
            response_hash="sha256:broken",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 400},
        ),
        LLMResponse(
            text=json.dumps(repair.model_dump(mode="json")),
            response_hash="sha256:repair",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 100},
        ),
    ]
    config = LLMConfig(provider=LLMProvider.OPENAI, model="local", cache=False)
    with (
        patch(
            "code2paper.agentic.intent_target_proposer.has_provider_api_key",
            return_value=True,
        ),
        patch(
            "code2paper.agentic.intent_target_proposer.LLMClient.complete",
            side_effect=responses,
        ) as complete,
    ):
        enriched, report = enrich_intent_graph_with_llm(graph, config)

    assert complete.call_count == 2
    assert report.accepted is True
    assert enriched.content_digest != graph.content_digest
    attempts = report.response_metadata["repair_attempts"]
    assert attempts[0]["obligation_id"] == full.obligations[0].obligation_id
    assert attempts[0]["max_output_tokens"] == 1024


def test_live_path_discloses_deterministic_fallback_after_one_bad_repair() -> None:
    """Repeated non-executable repairs must not consume the shared budget."""

    graph = _graph()
    full = _proposal(graph)
    broken = full.model_copy(deep=True)
    broken.obligations[0] = broken.obligations[0].model_copy(update={"targets": []})
    broken_repair = IntentTargetProposalSetV1(obligations=[
        broken.obligations[0],
    ])
    responses = [
        LLMResponse(
            text=json.dumps(broken.model_dump(mode="json")),
            response_hash="sha256:broken",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 400},
        ),
        LLMResponse(
            text=json.dumps(broken_repair.model_dump(mode="json")),
            response_hash="sha256:bad-repair",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 100},
        ),
    ]
    config = LLMConfig(provider=LLMProvider.OPENAI, model="local", cache=False)
    with (
        patch(
            "code2paper.agentic.intent_target_proposer.has_provider_api_key",
            return_value=True,
        ),
        patch(
            "code2paper.agentic.intent_target_proposer.LLMClient.complete",
            side_effect=responses,
        ) as complete,
    ):
        enriched, report = enrich_intent_graph_with_llm(graph, config)

    failed_id = full.obligations[0].obligation_id
    assert complete.call_count == 2
    assert report.accepted is True
    assert report.fallback_obligation_ids == (failed_id,)
    assert report.response_metadata["deterministic_fallbacks"] == [{
        "obligation_id": failed_id,
        "reason": f"normalization_failed:empty_executable_target:{failed_id}",
    }]
    enriched_obligation = next(
        item for item in enriched.obligations if item.obligation_id == failed_id
    )
    original_obligation = next(
        item for item in graph.obligations if item.obligation_id == failed_id
    )
    assert enriched_obligation.typed_behavior_targets == original_obligation.typed_behavior_targets


# ---------------------------------------------------------------------------
# R8 P0 regression: deterministic target with 11 predicates must not crash
# the CLI.  EBCAR/DyG/LinearRAG all exited with code 2 because the LLM
# proposal schema capped ``desired_predicates`` at 8 while the deterministic
# intent graph legally emits 10-11.  ``_deterministic_proposal`` then
# raised an uncaught ``ValidationError`` inside the repair loop.
# ---------------------------------------------------------------------------


_ELEVEN_PREDICATES = (
    "ATTEND",
    "COMPUTE",
    "COMPARE",
    "CONCAT",
    "TRANSFORM",
    "STACK",
    "NORMALIZE",
    "REDUCE",
    "AGGREGATE",
    "TOPK",
    "FILTER",
)


def _eleven_predicate_graph() -> IntentObligationGraphV2:
    target = TypedBehaviorTargetV1(
        target_id="t-det-eleven",
        desired_predicates=_ELEVEN_PREDICATES,
    )
    obligation = IntentObligationV2(
        obligation_id="ob-eleven",
        kind="stage",
        priority="must_cover",
        source_field="pipeline_steps",
        author_text="multi-predicate stage",
        typed_behavior_targets=(target,),
    )
    return IntentObligationGraphV2(obligations=[obligation])


def test_intent_target_proposal_schema_accepts_eleven_predicates() -> None:
    """The LLM proposal schema must represent any legal deterministic target.

    A deterministic target can legally carry up to
    ``len(BEHAVIOR_PREDICATES)`` predicates.  The proposal schema must not
    impose a tighter bound, otherwise ``_deterministic_proposal`` crashes
    while building the fallback.
    """

    assert _MAX_DESIRED_PREDICATES >= 11
    proposal = IntentTargetProposalV1(desired_predicates=list(_ELEVEN_PREDICATES))
    assert proposal.desired_predicates == list(_ELEVEN_PREDICATES)


def test_enrichment_does_not_crash_when_deterministic_target_has_eleven_predicates() -> None:
    """R8 P0: deterministic fallback must succeed for 11-predicate targets.

    Reproduces the EBCAR/DyG/LinearRAG crash path:
    1. LLM proposal drops a mandatory predicate -> repair loop starts.
    2. Repair also fails -> ``_deterministic_proposal`` is invoked.
    3. Previously this raised ``ValidationError`` (max_length=8) and the
       CLI exited with code 2 before any Method work began.
    Now the schema accepts the full vocabulary and the fallback restores
    the original 11-predicate target byte-for-byte.
    """

    graph = _eleven_predicate_graph()
    obligation = graph.obligations[0]

    # LLM proposal: valid schema but drops FILTER -> triggers repair.
    broken_proposal = IntentTargetProposalSetV1(obligations=[
        ObligationTargetProposalV1(
            obligation_id=obligation.obligation_id,
            targets=[IntentTargetProposalV1(
                role="stage",
                desired_predicates=list(_ELEVEN_PREDICATES[:-1]),
            )],
        ),
    ])
    # Repair: empty targets -> triggers deterministic fallback.
    broken_repair = IntentTargetProposalSetV1(obligations=[
        ObligationTargetProposalV1(
            obligation_id=obligation.obligation_id,
            targets=[],
        ),
    ])
    responses = [
        LLMResponse(
            text=json.dumps(broken_proposal.model_dump(mode="json")),
            response_hash="sha256:broken",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 400},
        ),
        LLMResponse(
            text=json.dumps(broken_repair.model_dump(mode="json")),
            response_hash="sha256:repair",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 100},
        ),
    ]
    config = LLMConfig(provider=LLMProvider.OPENAI, model="local", cache=False)
    with (
        patch(
            "code2paper.agentic.intent_target_proposer.has_provider_api_key",
            return_value=True,
        ),
        patch(
            "code2paper.agentic.intent_target_proposer.LLMClient.complete",
            side_effect=responses,
        ) as complete,
    ):
        enriched, report = enrich_intent_graph_with_llm(graph, config)

    assert complete.call_count == 2
    assert report.accepted is True
    assert report.fallback_obligation_ids == (obligation.obligation_id,)
    fallbacks = report.response_metadata["deterministic_fallbacks"]
    assert fallbacks == [{
        "obligation_id": obligation.obligation_id,
        "reason": f"normalization_failed:empty_executable_target:{obligation.obligation_id}",
    }]
    enriched_obligation = enriched.obligations[0]
    assert (
        enriched_obligation.typed_behavior_targets
        == obligation.typed_behavior_targets
    )


def test_enrichment_fails_closed_on_unexpected_validation_error() -> None:
    """Defensive backstop: any ``ValidationError`` escaping the impl must
    return the original graph with a disclosed failure report rather than
    crashing the CLI.  Guards future schema/model mismatches.
    """

    graph = _eleven_predicate_graph()
    config = LLMConfig(provider=LLMProvider.OPENAI, model="local", cache=False)

    def _raise_validation_error(*args, **kwargs):
        # Construct a genuine ValidationError via a Pydantic model.
        try:
            IntentTargetProposalV1.model_validate(
                {"desired_predicates": [123, 456]}
            )
        except ValidationError as exc:
            raise exc

    with (
        patch(
            "code2paper.agentic.intent_target_proposer.has_provider_api_key",
            return_value=True,
        ),
        patch(
            "code2paper.agentic.intent_target_proposer._enrich_intent_graph_with_llm_impl",
            side_effect=_raise_validation_error,
        ),
    ):
        enriched, report = enrich_intent_graph_with_llm(graph, config)

    assert enriched is graph
    assert report.attempted is True
    assert report.accepted is False
    assert report.failure.startswith("validation_error:")
    assert report.original_graph_digest == graph.content_digest
    assert report.enriched_graph_digest == graph.content_digest
    assert "validation_error" in report.response_metadata


# ---------------------------------------------------------------------------
# RAP regression: when the eligible set exceeds the sharding threshold the
# proposer must issue one LLM call per obligation instead of a single
# combined request that truncates at the model's output-token cap.
# RAP had 10 eligible obligations and the 4096-token cap cut the JSON
# mid-array (finish_reason=length, proposed_obligation_count=0).
# ---------------------------------------------------------------------------


def _large_eligible_graph(n_obligations: int = 6) -> IntentObligationGraphV2:
    """Build a graph with ``n_obligations`` must_cover stage obligations."""

    obligations: list[IntentObligationV2] = []
    for index in range(n_obligations):
        target = TypedBehaviorTargetV1(
            target_id=f"t-det-{index}",
            desired_predicates=("COMPUTE",),
        )
        obligations.append(IntentObligationV2(
            obligation_id=f"ob-stage-{index}",
            kind="stage",
            priority="must_cover",
            source_field="pipeline_steps",
            author_text=f"stage {index}: compute a value",
            typed_behavior_targets=(target,),
        ))
    return IntentObligationGraphV2(obligations=obligations)


def test_sharded_proposal_issues_one_call_per_obligation_above_threshold() -> None:
    """When the eligible set exceeds ``_SHARD_OBLIGATION_THRESHOLD`` the
    proposer must shard by obligation so each LLM response stays well
    under the output-token cap.  This is the RAP 4096-truncation fix."""

    from code2paper.agentic.intent_target_proposer import _SHARD_OBLIGATION_THRESHOLD

    n = _SHARD_OBLIGATION_THRESHOLD + 2
    assert n > _SHARD_OBLIGATION_THRESHOLD
    graph = _large_eligible_graph(n)

    # Build one valid single-obligation response per eligible obligation.
    responses: list[LLMResponse] = []
    for obligation in graph.obligations:
        if obligation.priority != "must_cover":
            continue
        single = IntentTargetProposalSetV1(obligations=[
            ObligationTargetProposalV1(
                obligation_id=obligation.obligation_id,
                targets=[IntentTargetProposalV1(
                    role="stage",
                    desired_predicates=["COMPUTE"],
                    inputs=[f"input for {obligation.obligation_id}"],
                )],
            ),
        ])
        responses.append(LLMResponse(
            text=json.dumps(single.model_dump(mode="json")),
            response_hash=f"sha256:{obligation.obligation_id}",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 80},
        ))

    config = LLMConfig(provider=LLMProvider.OPENAI, model="local", cache=False)
    with (
        patch(
            "code2paper.agentic.intent_target_proposer.has_provider_api_key",
            return_value=True,
        ),
        patch(
            "code2paper.agentic.intent_target_proposer.LLMClient.complete",
            side_effect=responses,
        ) as complete,
    ):
        enriched, report = enrich_intent_graph_with_llm(graph, config)

    # One call per eligible obligation (no combined request, no repair).
    assert complete.call_count == n
    assert report.accepted is True
    assert report.response_metadata.get("sharded") is True
    assert report.response_metadata.get("shard_count") == n
    assert enriched.content_digest != graph.content_digest


def test_sharded_proposal_falls_back_to_deterministic_on_parse_failure() -> None:
    """A shard whose LLM response truncates/parse-fails must fall back to
    the deterministic proposal for that obligation instead of failing the
    whole intent graph."""

    from code2paper.agentic.intent_target_proposer import _SHARD_OBLIGATION_THRESHOLD

    n = _SHARD_OBLIGATION_THRESHOLD + 1
    graph = _large_eligible_graph(n)
    eligible = [
        item for item in graph.obligations if item.priority == "must_cover"
    ]
    assert len(eligible) == n

    # First shard: truncated JSON (parse failure).  Remaining shards: valid.
    responses: list[LLMResponse] = [
        LLMResponse(
            text='{"obligations": [{"obligation_id": "ob-stage-0", "targets": [',
            response_hash="sha256:truncated",
            response_mode="json_schema",
            finish_reason="length",
            token_usage={"output_tokens": 4096},
        ),
    ]
    for obligation in eligible[1:]:
        single = IntentTargetProposalSetV1(obligations=[
            ObligationTargetProposalV1(
                obligation_id=obligation.obligation_id,
                targets=[IntentTargetProposalV1(
                    role="stage",
                    desired_predicates=["COMPUTE"],
                )],
            ),
        ])
        responses.append(LLMResponse(
            text=json.dumps(single.model_dump(mode="json")),
            response_hash=f"sha256:{obligation.obligation_id}",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 80},
        ))

    config = LLMConfig(provider=LLMProvider.OPENAI, model="local", cache=False)
    with (
        patch(
            "code2paper.agentic.intent_target_proposer.has_provider_api_key",
            return_value=True,
        ),
        patch(
            "code2paper.agentic.intent_target_proposer.LLMClient.complete",
            side_effect=responses,
        ) as complete,
    ):
        enriched, report = enrich_intent_graph_with_llm(graph, config)

    assert complete.call_count == n
    assert report.accepted is True
    assert report.response_metadata.get("sharded") is True
    # The truncated shard must be disclosed as a deterministic fallback.
    assert "ob-stage-0" in report.fallback_obligation_ids
    fallbacks = report.response_metadata.get("deterministic_fallbacks", [])
    fallback_ids = {item["obligation_id"] for item in fallbacks}
    assert "ob-stage-0" in fallback_ids
    # The fallback obligation's targets must match the original graph.
    enriched_ob = next(
        item for item in enriched.obligations if item.obligation_id == "ob-stage-0"
    )
    original_ob = next(
        item for item in graph.obligations if item.obligation_id == "ob-stage-0"
    )
    assert (
        enriched_ob.typed_behavior_targets
        == original_ob.typed_behavior_targets
    )


def test_sharded_proposal_falls_back_on_empty_executable_target() -> None:
    """A shard that returns valid JSON but with empty predicates/relations
    must trigger a deterministic fallback for that obligation instead of
    rejecting the whole merged proposal."""

    from code2paper.agentic.intent_target_proposer import _SHARD_OBLIGATION_THRESHOLD

    n = _SHARD_OBLIGATION_THRESHOLD + 1
    graph = _large_eligible_graph(n)
    eligible = [
        item for item in graph.obligations if item.priority == "must_cover"
    ]
    assert len(eligible) == n

    # First shard: valid JSON but empty predicates AND empty relations
    # (the LLM omitted the mandatory fields).  Remaining shards: valid.
    responses: list[LLMResponse] = [
        LLMResponse(
            text=json.dumps(IntentTargetProposalSetV1(obligations=[
                ObligationTargetProposalV1(
                    obligation_id="ob-stage-0",
                    targets=[IntentTargetProposalV1(
                        role="stage",
                        desired_predicates=[],
                        required_relations=[],
                    )],
                ),
            ]).model_dump(mode="json")),
            response_hash="sha256:empty-pred",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 80},
        ),
    ]
    for obligation in eligible[1:]:
        single = IntentTargetProposalSetV1(obligations=[
            ObligationTargetProposalV1(
                obligation_id=obligation.obligation_id,
                targets=[IntentTargetProposalV1(
                    role="stage",
                    desired_predicates=["COMPUTE"],
                )],
            ),
        ])
        responses.append(LLMResponse(
            text=json.dumps(single.model_dump(mode="json")),
            response_hash=f"sha256:{obligation.obligation_id}",
            response_mode="json_schema",
            finish_reason="stop",
            token_usage={"output_tokens": 80},
        ))

    config = LLMConfig(provider=LLMProvider.OPENAI, model="local", cache=False)
    with (
        patch(
            "code2paper.agentic.intent_target_proposer.has_provider_api_key",
            return_value=True,
        ),
        patch(
            "code2paper.agentic.intent_target_proposer.LLMClient.complete",
            side_effect=responses,
        ),
    ):
        enriched, report = enrich_intent_graph_with_llm(graph, config)

    assert report.accepted is True
    assert report.response_metadata.get("sharded") is True
    # The empty-predicate shard must be disclosed as a deterministic fallback.
    assert "ob-stage-0" in report.fallback_obligation_ids
    # The fallback obligation's targets must match the original graph.
    enriched_ob = next(
        item for item in enriched.obligations if item.obligation_id == "ob-stage-0"
    )
    original_ob = next(
        item for item in graph.obligations if item.obligation_id == "ob-stage-0"
    )
    assert (
        enriched_ob.typed_behavior_targets
        == original_ob.typed_behavior_targets
    )
