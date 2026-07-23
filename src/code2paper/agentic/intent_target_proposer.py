"""Gemma proposal + deterministic normalization for typed intent targets.

The author-facing YAML is semantic input, not executable evidence.  This
module lets the intent model propose a richer ``TypedBehaviorTargetV1`` for
each positive obligation while keeping the authorization boundary entirely
deterministic:

* the model may only choose registered behavior predicates/relation kinds;
* obligation ids must exactly match the supplied graph;
* target ids are recomputed from normalized content;
* list sizes and string sizes are bounded;
* malformed/partial output leaves the deterministic intent graph unchanged.

No repository source is sent to this model and no proposal can mark an
obligation supported.  The research/fact alignment layers remain responsible
for proving every proposed operation against executable-hard evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from code2paper.agentic.behavior_graph import (
    BEHAVIOR_PREDICATES,
    BEHAVIOR_RELATION_KINDS,
)
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    IntentObligationV2,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.providers import has_provider_api_key
from code2paper.llm.response_schemas import try_parse_structured_response
from code2paper.llm.role_config import INTENT_COMPILER, apply_role_config
from code2paper.schemas import LLMConfig, LLMProvider


_MAX_TARGETS_PER_OBLIGATION = 4
_MAX_ITEMS_PER_FIELD = 8
_MAX_TEXT_LENGTH = 160
# When the number of eligible obligations is small, a single LLM request
# carries the full proposal set.  Above this threshold the combined
# response risks truncation (e.g. RAP has 10 eligible obligations and
# the Gemma 4096-token output cap cut the JSON mid-array, causing
# ``finish_reason=length`` and ``proposed_obligation_count=0``).  Per-
# obligation sharding keeps each request well under the output cap while
# still using the full proposal prompt for every obligation.
_SHARD_OBLIGATION_THRESHOLD = 4
# The deterministic intent graph may emit a target whose desired_predicates
# collectively span a large fraction of the behavior vocabulary (EBCAR/DyG
# reach 11, LinearRAG reaches 10).  The LLM proposal schema MUST be able to
# represent any legal deterministic target byte-for-byte, otherwise the
# deterministic fallback path inside ``_deterministic_proposal`` raises a
# Pydantic ``ValidationError`` that escapes the enrichment entry point and
# crashes the CLI before the LLM is ever consulted.  Predicate/relation
# bounds therefore track the registered vocabularies; free-form item bounds
# are generous but still bounded so a runaway LLM cannot balloon a single
# request.
_MAX_DESIRED_PREDICATES = len(BEHAVIOR_PREDICATES)
_MAX_REQUIRED_RELATIONS = len(BEHAVIOR_RELATION_KINDS)
_MAX_FREEFORM_ITEMS = 32
# One full proposal can cover several unrelated obligations.  A short repair
# is scoped to exactly one failed item, so six attempts bound the cumulative
# repair budget to 6144 tokens while allowing a six-obligation author summary
# to recover independent omissions without ever enlarging a single request.
_MAX_REPAIR_ATTEMPTS = 6
_REPAIR_MAX_OUTPUT_TOKENS = 1024
_POSITIVE_PRIORITIES = frozenset({"must_cover", "should_cover"})
_PREDICATES = frozenset(BEHAVIOR_PREDICATES)
_RELATIONS = frozenset(BEHAVIOR_RELATION_KINDS)


class IntentTargetProposalV1(BaseModel):
    """One model-proposed semantic behavior target."""

    model_config = ConfigDict(extra="forbid")

    role: str = ""
    desired_predicates: list[str] = Field(
        default_factory=list, max_length=_MAX_DESIRED_PREDICATES
    )
    required_relations: list[str] = Field(
        default_factory=list, max_length=_MAX_REQUIRED_RELATIONS
    )
    inputs: list[str] = Field(default_factory=list, max_length=_MAX_FREEFORM_ITEMS)
    transformations: list[str] = Field(
        default_factory=list, max_length=_MAX_FREEFORM_ITEMS
    )
    decisions: list[str] = Field(default_factory=list, max_length=_MAX_FREEFORM_ITEMS)
    outputs: list[str] = Field(default_factory=list, max_length=_MAX_FREEFORM_ITEMS)
    conditions: list[str] = Field(default_factory=list, max_length=_MAX_FREEFORM_ITEMS)
    search_terms: list[str] = Field(
        default_factory=list, max_length=_MAX_FREEFORM_ITEMS
    )
    aliases: list[str] = Field(default_factory=list, max_length=_MAX_FREEFORM_ITEMS)
    organization_preference: str = ""
    risk_level: str = "medium"

    @field_validator("desired_predicates")
    @classmethod
    def _known_predicates(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().upper() for value in values if value.strip()]
        unknown = sorted(set(normalized) - _PREDICATES)
        if unknown:
            raise ValueError(f"unknown behavior predicates: {unknown}")
        return normalized

    @field_validator("required_relations")
    @classmethod
    def _known_relations(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().upper() for value in values if value.strip()]
        unknown = sorted(set(normalized) - _RELATIONS)
        if unknown:
            raise ValueError(f"unknown behavior relations: {unknown}")
        return normalized


class ObligationTargetProposalV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_id: str
    targets: list[IntentTargetProposalV1] = Field(
        default_factory=list,
        max_length=_MAX_TARGETS_PER_OBLIGATION,
    )


class IntentTargetProposalSetV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligations: list[ObligationTargetProposalV1]


class IntentTargetProposalReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempted: bool = False
    accepted: bool = False
    failure: str = ""
    proposed_obligation_count: int = 0
    enriched_obligation_count: int = 0
    original_graph_digest: str = ""
    enriched_graph_digest: str = ""
    fallback_obligation_ids: tuple[str, ...] = ()
    response_metadata: dict[str, Any] = Field(default_factory=dict)


def enrich_intent_graph_with_llm(
    graph: IntentObligationGraphV2,
    llm_config: LLMConfig,
) -> tuple[IntentObligationGraphV2, IntentTargetProposalReportV1]:
    """Propose rich targets and deterministically rebuild the intent graph."""

    eligible = [
        obligation
        for obligation in graph.obligations
        if obligation.priority in _POSITIVE_PRIORITIES
    ]
    base_report = {
        "original_graph_digest": graph.content_digest,
        "enriched_graph_digest": graph.content_digest,
    }
    if not eligible:
        return graph, IntentTargetProposalReportV1(**base_report)
    if (
        llm_config.provider == LLMProvider.NONE
        or not has_provider_api_key(llm_config)
    ):
        return graph, IntentTargetProposalReportV1(**base_report)

    effective_config = apply_role_config(llm_config, INTENT_COMPILER).model_copy(
        update={"cache": False}
    )
    # Per-obligation sharding when the eligible set is large enough that a
    # single response would risk the model's output-token cap (RAP with 10
    # obligations truncated at 4096 tokens).  Each shard uses the full
    # proposal prompt so the model sees the same instructions; only the
    # input payload is split.
    if len(eligible) > _SHARD_OBLIGATION_THRESHOLD:
        try:
            return _enrich_with_sharded_proposals(
                graph, eligible, effective_config
            )
        except ValidationError as exc:
            return graph, IntentTargetProposalReportV1(
                attempted=True,
                failure=f"validation_error:{type(exc).__name__}",
                original_graph_digest=graph.content_digest,
                enriched_graph_digest=graph.content_digest,
                response_metadata={"validation_error": str(exc)},
            )
    request = _build_proposal_request(eligible)
    try:
        return _enrich_intent_graph_with_llm_impl(
            graph, eligible, effective_config, request
        )
    except ValidationError as exc:
        # Defensive backstop: the schema limits already cover every legal
        # deterministic target, but any future schema/model mismatch must
        # still fail closed with a disclosed report instead of crashing the
        # CLI (R8 P0: EBCAR/DyG/LinearRAG crashed here with
        # ``desired_predicates`` ``max_length=8`` violations).
        return graph, IntentTargetProposalReportV1(
            attempted=True,
            failure=f"validation_error:{type(exc).__name__}",
            original_graph_digest=graph.content_digest,
            enriched_graph_digest=graph.content_digest,
            response_metadata={"validation_error": str(exc)},
        )


def _enrich_with_sharded_proposals(
    graph: IntentObligationGraphV2,
    eligible: list[IntentObligationV2],
    effective_config: LLMConfig,
) -> tuple[IntentObligationGraphV2, IntentTargetProposalReportV1]:
    """Per-obligation sharded proposal for large eligible sets.

    When the eligible set exceeds ``_SHARD_OBLIGATION_THRESHOLD`` a
    single combined LLM response risks truncation at the model's
    output-token cap (RAP: 10 obligations, 4096-token cap,
    ``finish_reason=length``).  This path issues one single-obligation
    request per eligible obligation using the full proposal prompt,
    then merges the successful proposals into one
    ``IntentTargetProposalSetV1``.  Obligations whose shard failed
    (LLM error, truncation, parse error) fall back to the deterministic
    proposal so the intent graph is never left without a valid target.

    The merged proposal is applied through the same ``_apply_proposal``
    validator as the single-request path, so predicate/relation
    coverage and obligation-id set checks remain enforced.
    """

    base_report = {
        "original_graph_digest": graph.content_digest,
        "enriched_graph_digest": graph.content_digest,
    }
    merged_obligations: list[ObligationTargetProposalV1] = []
    shard_metadata: list[dict[str, Any]] = []
    fallback_ids: list[str] = []
    proposed_count = 0

    for obligation in eligible:
        shard_request = _build_proposal_request([obligation])
        shard_meta: dict[str, Any] = {
            "obligation_id": obligation.obligation_id,
            "shard": True,
        }
        try:
            response = LLMClient(effective_config).complete(shard_request)
        except Exception as exc:  # noqa: BLE001 - per-shard fail-closed
            shard_meta["failure"] = f"llm_error:{type(exc).__name__}"
            shard_metadata.append(shard_meta)
            fallback_ids.append(obligation.obligation_id)
            merged_obligations.append(_deterministic_proposal(obligation))
            continue

        shard_meta.update(_response_metadata(response, effective_config))
        if response.blocked_reason:
            shard_meta["failure"] = "llm_blocked"
            shard_metadata.append(shard_meta)
            fallback_ids.append(obligation.obligation_id)
            merged_obligations.append(_deterministic_proposal(obligation))
            continue

        parsed, error = try_parse_structured_response(
            response.text,
            IntentTargetProposalSetV1,
        )
        if parsed is None or len(parsed.obligations) != 1:
            shard_meta["failure"] = "proposal_parse_failed"
            if error:
                shard_meta["parse_error"] = error
            shard_metadata.append(shard_meta)
            fallback_ids.append(obligation.obligation_id)
            merged_obligations.append(_deterministic_proposal(obligation))
            continue

        shard = parsed.obligations[0]
        if shard.obligation_id != obligation.obligation_id:
            shard_meta["failure"] = "obligation_id_mismatch"
            shard_metadata.append(shard_meta)
            fallback_ids.append(obligation.obligation_id)
            merged_obligations.append(_deterministic_proposal(obligation))
            continue

        merged_obligations.append(shard)
        proposed_count += 1
        shard_metadata.append(shard_meta)

    merged_proposal = IntentTargetProposalSetV1(obligations=merged_obligations)
    metadata: dict[str, Any] = {
        "sharded": True,
        "shard_count": len(eligible),
        "shards": shard_metadata,
    }
    enriched, report = _apply_proposal(
        graph, eligible, merged_proposal, metadata=metadata
    )

    if fallback_ids and report.accepted:
        # Restore deterministic targets byte-for-byte for fallback
        # obligations so the enriched graph is stable across prompt/model
        # changes (same rationale as the repair path).
        enriched = _restore_deterministic_targets(
            graph, enriched, frozenset(fallback_ids)
        )
        report = report.model_copy(update={
            "enriched_obligation_count": max(
                0, report.enriched_obligation_count - len(fallback_ids)
            ),
            "enriched_graph_digest": enriched.content_digest,
            "fallback_obligation_ids": tuple(sorted(set(fallback_ids))),
            "response_metadata": {
                **report.response_metadata,
                "deterministic_fallbacks": [
                    {"obligation_id": obl_id, "reason": "shard_fallback"}
                    for obl_id in sorted(set(fallback_ids))
                ],
            },
        })

    if not report.accepted:
        # When _apply_proposal rejects the merged set because a shard
        # returned valid JSON but with empty predicates/relations (or
        # dropped deterministic requirements), progressively replace the
        # failed obligation(s) with their deterministic proposals and
        # re-apply.  This mirrors the repair loop in the single-request
        # path so the sharded path also converges to an accepted graph.
        current_merged = merged_proposal
        normalization_fallback_ids: list[str] = []
        while _is_repairable_normalization_failure(report.failure):
            failed_id = _repairable_obligation_id(report.failure, eligible)
            if not failed_id or failed_id in normalization_fallback_ids:
                break
            normalization_fallback_ids.append(failed_id)
            failed_obligation = next(
                item for item in eligible if item.obligation_id == failed_id
            )
            current_merged = _replace_obligation_proposal(
                current_merged,
                _deterministic_proposal(failed_obligation),
            )
            enriched, report = _apply_proposal(
                graph, eligible, current_merged, metadata=metadata
            )
            if report.accepted:
                break

        if report.accepted:
            all_fallback_ids = sorted(
                set(fallback_ids) | set(normalization_fallback_ids)
            )
            enriched = _restore_deterministic_targets(
                graph, enriched, frozenset(all_fallback_ids)
            )
            report = report.model_copy(update={
                "enriched_obligation_count": max(
                    0, report.enriched_obligation_count - len(all_fallback_ids)
                ),
                "enriched_graph_digest": enriched.content_digest,
                "fallback_obligation_ids": tuple(all_fallback_ids),
                "response_metadata": {
                    **report.response_metadata,
                    "deterministic_fallbacks": [
                        {"obligation_id": obl_id, "reason": "shard_normalization_fallback"}
                        for obl_id in normalization_fallback_ids
                    ] + [
                        {"obligation_id": obl_id, "reason": "shard_fallback"}
                        for obl_id in sorted(set(fallback_ids) - set(normalization_fallback_ids))
                    ],
                },
            })

    if not report.accepted:
        # Final fallback: return the original graph with the failure report
        return graph, report.model_copy(update={
            "response_metadata": {
                **report.response_metadata,
                "sharded": True,
                "shard_count": len(eligible),
            },
        })

    return enriched, report


def _enrich_intent_graph_with_llm_impl(
    graph: IntentObligationGraphV2,
    eligible: list[IntentObligationV2],
    effective_config: LLMConfig,
    request: LLMRequest,
) -> tuple[IntentObligationGraphV2, IntentTargetProposalReportV1]:
    """Implementation of :func:`enrich_intent_graph_with_llm`.

    Wrapped by the public entry point so any ``ValidationError`` raised by
    proposal normalization or deterministic fallback construction is
    converted to a disclosed failure report rather than crashing the CLI.
    """
    base_report = {
        "original_graph_digest": graph.content_digest,
        "enriched_graph_digest": graph.content_digest,
    }
    try:
        response = LLMClient(effective_config).complete(request)
    except Exception as exc:  # noqa: BLE001 - intent proposal must fail closed
        return graph, IntentTargetProposalReportV1(
            attempted=True,
            failure=f"llm_error:{type(exc).__name__}",
            **base_report,
        )
    metadata = {
        "response_mode": response.response_mode,
        "finish_reason": response.finish_reason,
        "token_usage": response.token_usage or {},
        "blocked_reason": response.blocked_reason,
        "max_output_tokens": effective_config.max_output_tokens,
        "temperature": effective_config.temperature,
        "role": effective_config.role,
    }
    if response.blocked_reason:
        return graph, IntentTargetProposalReportV1(
            attempted=True,
            failure="llm_blocked",
            response_metadata=metadata,
            **base_report,
        )
    parsed, error = try_parse_structured_response(
        response.text,
        IntentTargetProposalSetV1,
    )
    if parsed is None:
        metadata["parse_error"] = error or ""
        return graph, IntentTargetProposalReportV1(
            attempted=True,
            failure="proposal_parse_failed",
            response_metadata=metadata,
            **base_report,
        )
    enriched, report = _apply_proposal(graph, eligible, parsed, metadata=metadata)
    if report.accepted or not _is_repairable_normalization_failure(report.failure):
        return enriched, report

    # A long multi-obligation schema response can omit one core target even
    # when the rest is valid.  Repair only the failed obligation(s), with a
    # short output cap, then re-run the same whole-set atomic validator.  This
    # improves recall without accepting an incomplete or partially normalized
    # intent graph.
    current = parsed
    attempts: list[dict[str, Any]] = []
    fallback_reasons: dict[str, str] = {}
    repaired_ids: set[str] = set()
    # A second identical repair of one obligation is neither useful nor a
    # valid reason to spend the shared model budget.  The design's model
    # robustness contract requires deterministic fallback on a failed LLM
    # proposal, so each rejected obligation gets at most one short repair and
    # then explicitly reverts to its deterministic executable target.
    while len(attempts) < _MAX_REPAIR_ATTEMPTS:
        failed_id = _repairable_obligation_id(report.failure, eligible)
        if not failed_id:
            break
        failed_obligation = next(
            item for item in eligible if item.obligation_id == failed_id
        )
        if failed_id in repaired_ids:
            current = _replace_obligation_proposal(
                current,
                _deterministic_proposal(failed_obligation),
            )
            fallback_reasons[failed_id] = report.failure
            enriched, report = _apply_proposal(
                graph, eligible, current, metadata=metadata
            )
            if report.accepted:
                break
            continue

        repaired_ids.add(failed_id)
        attempt_index = len(attempts)
        repair_config = effective_config.model_copy(update={
            "max_output_tokens": min(
                effective_config.max_output_tokens,
                _REPAIR_MAX_OUTPUT_TOKENS,
            ),
        })
        repair_request = _build_proposal_request(
            [failed_obligation], repair=True
        )
        try:
            repair_response = LLMClient(repair_config).complete(repair_request)
        except Exception as exc:  # noqa: BLE001 - repair also fails closed
            attempts.append({
                "attempt": attempt_index + 1,
                "obligation_id": failed_id,
                "failure": f"llm_error:{type(exc).__name__}",
            })
            current = _replace_obligation_proposal(
                current,
                _deterministic_proposal(failed_obligation),
            )
            fallback_reasons[failed_id] = attempts[-1]["failure"]
            enriched, report = _apply_proposal(
                graph, eligible, current, metadata=metadata
            )
            if report.accepted:
                break
            continue
        repair_metadata = _response_metadata(repair_response, repair_config)
        repair_metadata["attempt"] = attempt_index + 1
        repair_metadata["obligation_id"] = failed_id
        attempts.append(repair_metadata)
        if repair_response.blocked_reason:
            current = _replace_obligation_proposal(
                current,
                _deterministic_proposal(failed_obligation),
            )
            fallback_reasons[failed_id] = "llm_blocked"
            enriched, report = _apply_proposal(
                graph, eligible, current, metadata=metadata
            )
            if report.accepted:
                break
            continue
        repaired, repair_error = try_parse_structured_response(
            repair_response.text,
            IntentTargetProposalSetV1,
        )
        if (
            repaired is None
            or len(repaired.obligations) != 1
            or repaired.obligations[0].obligation_id != failed_id
        ):
            if repair_error:
                repair_metadata["parse_error"] = repair_error
            current = _replace_obligation_proposal(
                current,
                _deterministic_proposal(failed_obligation),
            )
            fallback_reasons[failed_id] = "repair_parse_failed"
            enriched, report = _apply_proposal(
                graph, eligible, current, metadata=metadata
            )
            if report.accepted:
                break
            continue
        current = _replace_obligation_proposal(current, repaired.obligations[0])
        enriched, report = _apply_proposal(
            graph, eligible, current, metadata=metadata
        )
        if report.accepted:
            break

    combined_metadata = dict(report.response_metadata)
    combined_metadata["repair_attempts"] = attempts
    if fallback_reasons:
        # Validation above intentionally reuses the normal proposal path.
        # Restore the original objects afterwards so fallback is byte-for-byte
        # stable across prompt/model/library normalization changes (including
        # target ids and role spelling), rather than merely predicate-equivalent.
        enriched = _restore_deterministic_targets(
            graph,
            enriched,
            frozenset(fallback_reasons),
        )
        combined_metadata["deterministic_fallbacks"] = [
            {
                "obligation_id": obligation_id,
                "reason": fallback_reasons[obligation_id],
            }
            for obligation_id in sorted(fallback_reasons)
        ]
    report = report.model_copy(update={
        "enriched_obligation_count": (
            max(0, report.enriched_obligation_count - len(fallback_reasons))
            if report.accepted else report.enriched_obligation_count
        ),
        "enriched_graph_digest": (
            enriched.content_digest if report.accepted else report.enriched_graph_digest
        ),
        "fallback_obligation_ids": tuple(sorted(fallback_reasons)),
        "response_metadata": combined_metadata,
    })
    return enriched, report


def _build_proposal_request(
    obligations: list[IntentObligationV2],
    *,
    repair: bool = False,
) -> LLMRequest:
    """Build a full or one-obligation strict-schema intent request."""

    return LLMRequest(
        prompt_template_id=(
            "agentic_intent_target_repair_v1"
            if repair else "agentic_intent_target_proposal_v1"
        ),
        prompt=_REPAIR_PROMPT if repair else _SYSTEM_PROMPT,
        input_payload={
            "obligations": [
                {
                    "obligation_id": item.obligation_id,
                    "kind": item.kind,
                    "priority": item.priority,
                    "author_text": item.author_text,
                    "mandatory_predicates": sorted({
                        predicate
                        for target in item.typed_behavior_targets
                        for predicate in target.desired_predicates
                    }),
                    "mandatory_relations": sorted({
                        relation
                        for target in item.typed_behavior_targets
                        for relation in target.required_relations
                    }),
                    "deterministic_targets": [
                        target.model_dump(mode="json")
                        for target in item.typed_behavior_targets
                    ],
                }
                for item in obligations
            ],
            "allowed_predicates": list(BEHAVIOR_PREDICATES),
            "allowed_relations": list(BEHAVIOR_RELATION_KINDS),
        },
        schema_name=IntentTargetProposalSetV1.__name__,
        response_json_schema=IntentTargetProposalSetV1.model_json_schema(),
    )


def _response_metadata(response: Any, config: LLMConfig) -> dict[str, Any]:
    return {
        "response_mode": response.response_mode,
        "finish_reason": response.finish_reason,
        "token_usage": response.token_usage or {},
        "blocked_reason": response.blocked_reason,
        "max_output_tokens": config.max_output_tokens,
        "temperature": config.temperature,
        "role": config.role,
    }


def _replace_obligation_proposal(
    proposal: IntentTargetProposalSetV1,
    replacement: ObligationTargetProposalV1,
) -> IntentTargetProposalSetV1:
    return IntentTargetProposalSetV1(obligations=[
        replacement if item.obligation_id == replacement.obligation_id else item
        for item in proposal.obligations
    ])


def _deterministic_proposal(
    obligation: IntentObligationV2,
) -> ObligationTargetProposalV1:
    """Represent the pre-LLM target exactly for an explicit fallback.

    The fallback is deliberately a replacement, not a merge with a malformed
    LLM target: semantic additions without executable predicate/relation
    coverage would otherwise let a failed proposal alter research scope.
    """

    return ObligationTargetProposalV1(
        obligation_id=obligation.obligation_id,
        targets=[
            IntentTargetProposalV1(
                role=target.role,
                desired_predicates=list(target.desired_predicates),
                required_relations=list(target.required_relations),
                inputs=list(target.inputs),
                transformations=list(target.transformations),
                decisions=list(target.decisions),
                outputs=list(target.outputs),
                conditions=list(target.conditions),
                search_terms=list(target.search_terms),
                aliases=list(target.aliases),
                organization_preference=target.organization_preference,
                risk_level=target.risk_level,
            )
            for target in obligation.typed_behavior_targets
        ],
    )


def _restore_deterministic_targets(
    original_graph: IntentObligationGraphV2,
    enriched_graph: IntentObligationGraphV2,
    fallback_ids: frozenset[str],
) -> IntentObligationGraphV2:
    """Restore exact pre-LLM targets for disclosed fallback obligations."""

    originals = {
        item.obligation_id: item.typed_behavior_targets
        for item in original_graph.obligations
        if item.obligation_id in fallback_ids
    }
    obligations = [
        item.model_copy(update={"typed_behavior_targets": originals[item.obligation_id]})
        if item.obligation_id in originals else item
        for item in enriched_graph.obligations
    ]
    return IntentObligationGraphV2(
        schema_version=enriched_graph.schema_version,
        mode=enriched_graph.mode,
        project_goal=enriched_graph.project_goal,
        method_goal=enriched_graph.method_goal,
        implementation_scope=enriched_graph.implementation_scope,
        obligations=obligations,
        relations=list(enriched_graph.relations),
    )


def _is_repairable_normalization_failure(failure: str) -> bool:
    return failure.startswith((
        "normalization_failed:empty_executable_target:",
        "normalization_failed:dropped_deterministic_requirement:",
    ))


def _repairable_obligation_id(
    failure: str,
    eligible: list[IntentObligationV2],
) -> str:
    for item in eligible:
        marker = f":{item.obligation_id}"
        if marker in failure:
            return item.obligation_id
    return ""


def _apply_proposal(
    graph: IntentObligationGraphV2,
    eligible: list[IntentObligationV2],
    proposal: IntentTargetProposalSetV1,
    *,
    metadata: dict[str, Any] | None = None,
) -> tuple[IntentObligationGraphV2, IntentTargetProposalReportV1]:
    expected_ids = {item.obligation_id for item in eligible}
    proposed_ids = [item.obligation_id for item in proposal.obligations]
    if len(proposed_ids) != len(set(proposed_ids)):
        return graph, _rejected_report(
            graph, proposal, "duplicate_obligation_id", metadata
        )
    if set(proposed_ids) != expected_ids:
        return graph, _rejected_report(
            graph, proposal, "obligation_id_set_mismatch", metadata
        )

    targets_by_id: dict[str, tuple[TypedBehaviorTargetV1, ...]] = {}
    eligible_by_id = {item.obligation_id: item for item in eligible}
    try:
        for item in proposal.obligations:
            normalized_targets = tuple(
                _normalize_target(item.obligation_id, target, index)
                for index, target in enumerate(item.targets)
                if target.desired_predicates or target.required_relations
            )
            original = eligible_by_id[item.obligation_id]
            original_predicates = {
                predicate
                for target in original.typed_behavior_targets
                for predicate in target.desired_predicates
            }
            original_relations = {
                relation
                for target in original.typed_behavior_targets
                for relation in target.required_relations
            }
            proposed_predicates = {
                predicate
                for target in normalized_targets
                for predicate in target.desired_predicates
            }
            proposed_relations = {
                relation
                for target in normalized_targets
                for relation in target.required_relations
            }
            if (original_predicates or original_relations) and not normalized_targets:
                raise ValueError(
                    f"empty_executable_target:{item.obligation_id}"
                )
            missing_predicates = sorted(original_predicates - proposed_predicates)
            missing_relations = sorted(original_relations - proposed_relations)
            if missing_predicates or missing_relations:
                detail = ",".join([
                    *(f"predicate={value}" for value in missing_predicates),
                    *(f"relation={value}" for value in missing_relations),
                ])
                raise ValueError(
                    f"dropped_deterministic_requirement:{item.obligation_id}:{detail}"
                )
            targets_by_id[item.obligation_id] = normalized_targets
    except ValueError as exc:
        return graph, _rejected_report(
            graph, proposal, f"normalization_failed:{exc}", metadata
        )

    enriched_count = 0
    obligations: list[IntentObligationV2] = []
    for obligation in graph.obligations:
        if obligation.obligation_id not in targets_by_id:
            obligations.append(obligation)
            continue
        enriched_count += 1
        obligations.append(obligation.model_copy(update={
            "typed_behavior_targets": targets_by_id[obligation.obligation_id]
        }))
    enriched = IntentObligationGraphV2(
        schema_version=graph.schema_version,
        mode=graph.mode,
        project_goal=graph.project_goal,
        method_goal=graph.method_goal,
        implementation_scope=graph.implementation_scope,
        obligations=obligations,
        relations=list(graph.relations),
    )
    return enriched, IntentTargetProposalReportV1(
        attempted=True,
        accepted=True,
        proposed_obligation_count=len(proposal.obligations),
        enriched_obligation_count=enriched_count,
        original_graph_digest=graph.content_digest,
        enriched_graph_digest=enriched.content_digest,
        response_metadata=metadata or {},
    )


def _normalize_target(
    obligation_id: str,
    proposal: IntentTargetProposalV1,
    index: int,
) -> TypedBehaviorTargetV1:
    payload = {
        "role": _normalize_role(proposal.role),
        "desired_predicates": tuple(_dedupe(proposal.desired_predicates)),
        "required_relations": tuple(_dedupe(proposal.required_relations)),
        "inputs": tuple(_normalize_values(proposal.inputs)),
        "transformations": tuple(_normalize_values(proposal.transformations)),
        "decisions": tuple(_normalize_values(proposal.decisions)),
        "outputs": tuple(_normalize_values(proposal.outputs)),
        "conditions": tuple(_normalize_values(proposal.conditions)),
        "search_terms": tuple(_normalize_values(proposal.search_terms)),
        "aliases": tuple(_normalize_values(proposal.aliases)),
        "organization_preference": _normalize_text(
            proposal.organization_preference
        ),
        "risk_level": proposal.risk_level if proposal.risk_level in {
            "low", "medium", "high"
        } else "medium",
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(
        f"{obligation_id}|{index}|{canonical}".encode("utf-8")
    ).hexdigest()[:12]
    return TypedBehaviorTargetV1(
        target_id=f"target-llm-{digest}",
        **payload,
    )


def _normalize_role(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized[:80]


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())[:_MAX_TEXT_LENGTH]


def _normalize_values(values: list[str]) -> list[str]:
    return _dedupe(
        _normalize_text(value)
        for value in values[:_MAX_ITEMS_PER_FIELD]
        if _normalize_text(value)
    )


def _dedupe(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        if value and value not in output:
            output.append(value)
    return output


def _rejected_report(
    graph: IntentObligationGraphV2,
    proposal: IntentTargetProposalSetV1,
    failure: str,
    metadata: dict[str, Any] | None,
) -> IntentTargetProposalReportV1:
    return IntentTargetProposalReportV1(
        attempted=True,
        failure=failure,
        proposed_obligation_count=len(proposal.obligations),
        original_graph_digest=graph.content_digest,
        enriched_graph_digest=graph.content_digest,
        response_metadata=metadata or {},
    )


_SYSTEM_PROMPT = """You are the typed Intent Agent for a code-grounded research writer.
Return only JSON matching the supplied schema.
For every supplied obligation id, decompose the author's requested behavior into one or more minimal typed targets.
Use only the supplied predicate and relation vocabularies.
When mandatory_predicates or mandatory_relations is non-empty, your targets MUST
collectively include every listed token and MUST NOT be empty.
Separate semantically distinct actors or paths (for example draft generation versus target generation) into distinct roles.
Populate concise inputs, transformations, decisions, outputs, conditions, search terms, and aliases when the author text states them.
Do not invent repository paths, symbols, implementation facts, equations, effects, novelty, or performance.
An empty target list means the prose is organizational/rationale-only and has no positive executable target.
The proposal guides research only; executable source evidence decides support.
"""


_REPAIR_PROMPT = """You are repairing one rejected typed Intent Agent obligation.
Return only JSON matching the supplied schema, containing exactly the supplied
obligation id.  It previously omitted a mandatory executable target or dropped
a mandatory predicate/relation.  Return one or more non-empty targets whose
combined desired_predicates and required_relations include every mandatory
token.  Preserve concise role, input, transformation, decision, output, and
condition distinctions explicitly stated by the author text.  Do not invent
repository paths, symbols, implementation facts, equations, effects, novelty,
or performance.  Executable source evidence still decides support.
"""


__all__ = [
    "IntentTargetProposalReportV1",
    "IntentTargetProposalSetV1",
    "IntentTargetProposalV1",
    "ObligationTargetProposalV1",
    "enrich_intent_graph_with_llm",
]
