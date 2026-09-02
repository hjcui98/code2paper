"""Autonomous Writer-callback fulfillment and section-resume loop.

The Writer emits ``WritingResearchRequestV1`` entries when a required move
lacks evidence.  The router already knows which lane owns each request; this
module adds the *production loop* that the product runner was missing:

- reads the persisted callback bundle after the first Writer run;
- executes open local-owned routes (repository / configuration /
  formalization) with a bounded, progress-driven research loop;
- writes digest-pinned, file-backed callback artifacts the resumed Writer
  can actually read (``artifact_preview``);
- fulfills the bundle and resumes only the affected sections;
- repeats until no local progress remains or the budget is exhausted;
- external author/literature/empirical requests stay in their explicit
  queues and never block local resume.  A replay without a research-stage
  checkpoint may use an explicitly persisted ``ResearchContinuationSeedV1``;
  that seed records frozen authority, not nonexistent Research history.

Nothing here fabricates completion: a request that finds no frozen repository
evidence stays pending, and the candidate prose remains caveated/reviewable.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_compiler_v3 import (
    CodeFactSetV1,
    load_code_facts_v1,
)
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    MethodSectionPlanV2,
    WritingResearchCallbackArtifactV1,
    WritingResearchCallbackBundleV1,
    WritingResearchRequestV1,
)
from code2paper.agentic.research_models import (
    ResearchAgendaItemV1,
    ResearchContinuationSeedV1,
    ResearchToolCallV1,
    TypedBehaviorTargetV1,
)
from code2paper.agentic.research_tools import ResearchToolContext, execute_research_tool
from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph
from code2paper.agentic.generic_fact_compiler import FactCompilerInputV1, compile_facts_from_behavior_graph
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.response_schemas import json_schema_for, try_parse_structured_response
from pydantic import BaseModel as _PydanticBaseModel, Field as _PydanticField
from typing import Literal as _Literal
from code2paper.agentic.writer_research_router import (
    execute_open_requests_for_routes,
)
from code2paper.agentic.publication_method_writer import (
    _writer_transaction_status_from_assessments,
    effective_writer_transaction_status,
    fulfill_writing_research_callbacks,
    run_publication_method_writer,
)


#: Lanes the local harness may fulfill.  Requests on any other lane are
#: external queues (author/literature/empirical) and stay pending here.
_LOCAL_OWNED_LANES: frozenset[str] = frozenset({
    "executable_hard",
    "configuration_resolved",
    "formal_derivation",
})


def _formula_not_applicable_section_ids(
    *,
    plan: MethodSectionPlanV2 | None,
    formalization_sections: tuple[Any, ...] | list[Any] | None,
) -> frozenset[str]:
    """Sections whose Architect/Formalizer already closed formula work.

    A Writer ``formal_derivation`` callback against these sections cannot be
    locally fulfilled; treating an empty package as ``no_progress`` stalls the
    whole loop while external requests stay pending (LinearRAG 234218 MA-S1).
    """

    ids: set[str] = set()
    if plan is not None:
        for section in getattr(plan, "sections", ()) or ():
            if not bool(getattr(section, "formula_not_applicable", False)):
                continue
            section_id = str(getattr(section, "section_id", "") or "").strip()
            if section_id:
                ids.add(section_id)
    for item in formalization_sections or ():
        section_id = str(getattr(item, "section_id", "") or "").strip()
        disp = getattr(item, "disposition", None)
        if isinstance(item, dict):
            section_id = str(item.get("section_id") or "").strip() or section_id
            disp = item.get("disposition")
        if isinstance(disp, dict):
            status = str(disp.get("disposition") or "")
        else:
            status = str(getattr(disp, "disposition", "") or "")
        if section_id and status == "not_applicable":
            ids.add(section_id)
    return frozenset(ids)


_SEED_STOPWORDS: frozenset[str] = frozenset({
    "the", "for", "and", "are", "was", "with", "what", "which", "find",
    "this", "that", "from", "into", "have", "has", "does", "is", "of",
    "it", "its", "on", "in", "to", "a", "an", "be", "by", "or", "how",
})


class WritingCallbackFulfillmentBudgetV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_callback_rounds: int = 3
    max_tool_turns_per_request: int = 8
    max_requests_per_round: int = 8
    max_artifacts_per_request: int = 3


class WritingCallbackFulfillmentResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rounds_attempted: int = 0
    local_requests_seen: int = 0
    local_requests_fulfilled: int = 0
    external_requests_seen: int = 0
    resumed_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    stopped_reason: str = ""
    trace_path: str = ""


# Paths returned by ``persist_product_artifacts`` when a Research callback
# creates a new authoring revision.  Writer/callback output paths intentionally
# do not belong to this set: the fresh callback bundle and the incumbent
# checkpoint are owned by the resume transaction and must remain selected.
_AUTHORING_REVISION_PATH_KEYS: frozenset[str] = frozenset({
    "behavior_graph_v1",
    "intent_obligation_graph_v2",
    "research_agenda_v1",
    "user_claims_input_v1",
    "research_trace",
    "typed_gaps",
    "implementation_scope_v1",
    "candidate_acquisition_ledger_v1",
    "obligation_coverage_v2",
    "reference_method_agenda_v1",
    "method_completeness_matrix_v1",
    "completeness_matrix",
    "story_spine",
    "authoring_projection_v1",
    "method_evidence",
    "claim_evidence_map",
    "equation_claims_v1",
    "configuration_claims_v1",
    "evidence_packets_v3",
    "evidence_packets",
    "code_facts_v1",
    "code_facts",
    "atomic_claims_v3",
    "atomic_claims",
    "technical_claims_v1",
    "method_propositions_v1",
    "method_proposition_bindings_v1",
    "method_proposition_clusters_v1",
    "method_concept_cards_v1",
    "method_argument_facet_alignment_trace_v1",
    "publication_field_candidates_v1",
    "typed_field_deferred_v1",
    "plan_product_readiness_v1",
    "review_candidates",
    "agent_trace",
    "run_summary",
    # These are produced by the resumed Writer from the new authority.  If a
    # caller supplies them in a recompile mapping, they should also supersede
    # an older snapshot; the callback bundle itself is deliberately absent.
    "research_mechanism_dossiers_v1",
    "derivation_records_v1",
})


def _merge_resumed_writer_paths(
    *,
    writer_paths: dict[str, str],
    authoring_paths: dict[str, str],
) -> dict[str, str]:
    """Merge a resumed Writer view with the newest authoring revision.

    A callback recompile can return the same logical artifact keys as the
    initial Writer call.  Recompiled facts, claims, and dossiers are the
    current evidence authority.  The MethodUnit plan, briefs, facets,
    alignments, and Candidate policies stay frozen from the incumbent Writer
    view so a Research rebuild cannot remint paragraph identity.
    """

    merged = dict(writer_paths)
    for key, value in authoring_paths.items():
        if key not in _AUTHORING_REVISION_PATH_KEYS:
            continue
        if str(value or "").strip():
            merged[str(key)] = str(value)
    return merged


def build_research_continuation_seed(
    *,
    runtime: Any,
    artifact_paths: dict[str, str],
    out_root: str | Path,
) -> tuple[ResearchContinuationSeedV1, str]:
    """Build and persist an honest seed when no research checkpoint exists.

    The seed records only the frozen authority that is actually available.
    In particular, it never copies a decision trace or serializes itself as a
    ``research_stage_checkpoint``.  A continuation provider can use the
    frozen packets/facts/claims as a baseline and start a new scoped research
    phase from this provenance.
    """

    root = Path(out_root).expanduser().resolve()
    authority_keys = (
        "intent_obligation_graph_v2",
        "research_agenda_v1",
        "evidence_packets_v3",
        "code_facts_v1",
        "atomic_claims_v3",
        "equation_claims_v1",
        "configuration_claims_v1",
        "method_argument_briefs_v1",
        "method_argument_facets_v1",
        "facet_evidence_alignments_v1",
        "candidate_facet_policies_v1",
    )
    source_digests: dict[str, str] = {}
    source_paths: dict[str, str] = {}
    for key in authority_keys:
        value = str(artifact_paths.get(key) or "").strip()
        if not value:
            continue
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            continue
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        source_digests[key] = digest
        source_paths[key] = str(path)

    def _source_digest(key: str) -> str:
        return source_digests.get(key, "")

    evidence_payload = json.dumps(
        source_digests,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    seed = ResearchContinuationSeedV1(
        run_id=str(getattr(runtime, "run_id", "") or ""),
        repo_snapshot_id=str(
            getattr(getattr(runtime, "repo_snapshot", None), "snapshot_id", "")
            or ""
        ),
        project_tree_hash=str(
            getattr(getattr(runtime, "repo_snapshot", None), "project_tree_hash", "")
            or ""
        ),
        source_digests=source_digests,
        source_paths=source_paths,
        intent_digest=_source_digest("intent_obligation_graph_v2"),
        agenda_digest=_source_digest("research_agenda_v1"),
        evidence_digest="sha256:" + hashlib.sha256(evidence_payload).hexdigest(),
    )
    path = root / "artifacts" / "research_product" / (
        "research_continuation_seed_v1.json"
    )
    _atomic_write_text(path, seed.model_dump_json(indent=2) + "\n")
    return seed, str(path)


def _load_bundle(path: str | Path) -> WritingResearchCallbackBundleV1 | None:
    candidate = Path(path)
    if not str(path).strip() or not candidate.is_file():
        return None
    try:
        return WritingResearchCallbackBundleV1.model_validate_json(
            candidate.read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None


def fulfill_and_resume_writing_callbacks(
    *,
    runtime: Any,
    out_root: Path,
    artifact_paths: dict[str, str],
    writer_paths: dict[str, str],
    llm_config: Any,
    budget: WritingCallbackFulfillmentBudgetV1 | None = None,
    llm_caller: Callable[..., Any] | None = None,
    research_stage_checkpoint: str | Path | None = None,
    research_continuation_seed: ResearchContinuationSeedV1 | None = None,
    method_name: str = "",
) -> tuple[dict[str, str], str, str, WritingCallbackFulfillmentResultV1]:
    """Run the bounded callback fulfillment/resume loop after a Writer run.

    Returns ``(writer_paths, writer_status, writer_blocked_reason, result)``.
    The loop stops when no open local-owned requests remain, a round produces
    no new validated artifacts, the Writer succeeds with no new local-owned
    open request, or the round budget is exhausted.

    Review P0 (Q4): when the run's research stage checkpoint is available,
    local repository requests are fulfilled through the ORIGINAL Research
    LangGraph: the same research thread/checkpoint is restored, the request
    becomes a new scoped obligation with an additive tool budget, and the
    compiled observation -> behavior graph -> evidence packet -> fact ->
    claim/gap -> Concept judgment -> placement/WriterView chain is persisted.
    Fulfillment is decided by an owning validator report, never by the
    provider itself.  Without a checkpoint, the legacy bounded provider
    remains as the explicitly backward-compatible path (old tests).
    """

    budget = budget or WritingCallbackFulfillmentBudgetV1()
    import os
    try:
        env_rounds = int(os.environ.get("CODE2PAPER_MAX_CALLBACK_ROUNDS", str(budget.max_callback_rounds)))
    except ValueError:
        env_rounds = budget.max_callback_rounds
    if env_rounds <= 0 or budget.max_callback_rounds <= 0:
        return (
            writer_paths,
            "complete",
            "",
            WritingCallbackFulfillmentResultV1(stopped_reason="callback_gated_off"),
        )
    bundle_path = str(
        writer_paths.get("writing_research_callback_artifacts_v1")
        or artifact_paths.get("writing_research_callback_artifacts_v1")
        or ""
    )
    bundle = _load_bundle(bundle_path)
    if bundle is None:
        return (
            writer_paths,
            "incomplete",
            "",
            WritingCallbackFulfillmentResultV1(stopped_reason="no_callback_bundle"),
        )

    live_paths = {**artifact_paths, **writer_paths}
    facts = _load_facts(live_paths)
    equations = _load_equations(live_paths)
    plan = _load_plan(live_paths)
    configurations = _load_configurations(live_paths)
    formalization = _load_formalization(live_paths)
    formalization_sections = _load_formalization_sections(live_paths)
    callback_root = Path(bundle_path).expanduser().resolve().parent
    # R4: a live LLM gives the research supervisor; otherwise the
    # deterministic scripted sequence remains the fallback.
    supervisor_caller = llm_caller
    supervisor_config = llm_config
    if supervisor_caller is None and llm_config is not None:
        provider_value = getattr(llm_config, "provider", None)
        provider_value = getattr(provider_value, "value", provider_value)
        if str(provider_value or "").strip().lower() not in {"", "none"}:
            supervisor_caller = _default_llm_caller

    checkpoint_value = str(research_stage_checkpoint or "").strip()
    argument_briefs = _load_argument_briefs(artifact_paths)
    continuation_provider: _ResearchGraphContinuationProvider | None = None
    continuation_error = ""
    if checkpoint_value and Path(checkpoint_value).is_file():
        try:
            continuation_provider = _ResearchGraphContinuationProvider(
                runtime=runtime,
                research_stage_checkpoint=checkpoint_value,
                research_continuation_seed=None,
                facts=facts,
                plan=plan,
                concept_cards=_load_concept_cards(artifact_paths),
                argument_briefs=argument_briefs,
                callback_root=callback_root,
                budget=budget,
                artifact_paths=artifact_paths,
                llm_config=llm_config,
                method_name=method_name,
            )
        except Exception as exc:  # noqa: BLE001 — checkpoint faults degrade to the legacy provider
            continuation_error = f"{type(exc).__name__}:{str(exc)[:200]}"
            continuation_provider = None
    elif research_continuation_seed is not None:
        try:
            continuation_provider = _ResearchGraphContinuationProvider(
                runtime=runtime,
                research_stage_checkpoint=None,
                research_continuation_seed=research_continuation_seed,
                facts=facts,
                plan=plan,
                concept_cards=_load_concept_cards(artifact_paths),
                argument_briefs=argument_briefs,
                callback_root=callback_root,
                budget=budget,
                artifact_paths=artifact_paths,
                llm_config=llm_config,
                method_name=method_name,
            )
        except Exception as exc:  # noqa: BLE001 — seed faults degrade to the
            # explicitly backward-compatible provider, while retaining the
            # typed reason in the fulfillment trace.
            continuation_error = f"{type(exc).__name__}:{str(exc)[:200]}"
            continuation_provider = None
    provider = (
        continuation_provider
        if continuation_provider is not None
        else _BudgetedRepositoryCallbackProvider(
            runtime=runtime,
            facts=facts,
            plan=plan,
            callback_root=callback_root,
            budget=budget,
            argument_briefs=argument_briefs,
            supervisor_caller=supervisor_caller,
            supervisor_config=supervisor_config,
        )
    )

    result = WritingCallbackFulfillmentResultV1()
    trace_rows: list[dict[str, Any]] = []
    local_seen: set[str] = set()
    local_fulfilled: set[str] = set()
    external_seen: set[str] = set()
    resumed: set[str] = set()
    initial_writer_payload: dict[str, Any] = {}
    initial_writer_path = str(
        writer_paths.get("publication_writer_result_v1") or ""
    ).strip()
    if initial_writer_path and Path(initial_writer_path).is_file():
        try:
            loaded = json.loads(Path(initial_writer_path).read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                initial_writer_payload = loaded
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            initial_writer_payload = {}
    initial_assessment_path = str(
        writer_paths.get("publication_paragraph_transaction_assessments_v1") or ""
    ).strip()
    writer_status = _writer_transaction_status_from_assessments(
        initial_assessment_path,
        writer_aggregate=initial_writer_payload.get("writer_aggregate"),
        publication_status=str(initial_writer_payload.get("status") or ""),
    )
    if writer_status == "not_run":
        writer_status = str(initial_writer_payload.get("status") or "incomplete")
    writer_blocked_reason = ""
    continuation_rounds: list[dict[str, Any]] = []
    consecutive_no_gain = 0
    seen_semantic_digests: set[str] = set()

    for round_index in range(1, budget.max_callback_rounds + 1):
        result = result.model_copy(update={"rounds_attempted": round_index})
        open_requests = [
            item for item in bundle.requests if item.status in {"open", "partial"}
        ]
        if not open_requests:
            result = result.model_copy(update={"stopped_reason": "no_open_requests"})
            break
        local_requests = [
            item for item in open_requests
            if item.required_authority_lane in _LOCAL_OWNED_LANES
        ]
        external_requests = [
            item for item in open_requests
            if item.required_authority_lane not in _LOCAL_OWNED_LANES
        ]
        local_seen.update(item.request_id for item in local_requests)
        external_seen.update(item.request_id for item in external_requests)
        selected = local_requests[: budget.max_requests_per_round]
        if not selected:
            result = result.model_copy(update={"stopped_reason": "no_open_local_requests"})
            break

        live_paths = {**artifact_paths, **writer_paths}
        configurations = _load_configurations(live_paths) or configurations
        formalization = _load_formalization(live_paths) or formalization
        formalization_sections = _load_formalization_sections(live_paths) or formalization_sections
        equations = _load_equations(live_paths) or equations
        facts = _load_facts(live_paths) or facts
        na_sections = _formula_not_applicable_section_ids(
            plan=plan,
            formalization_sections=formalization_sections,
        )
        selected = [
            item for item in selected
            if not (
                item.required_authority_lane == "formal_derivation"
                and str(item.section_id) in na_sections
            )
        ]
        if not selected:
            result = result.model_copy(update={"stopped_reason": "no_open_local_requests"})
            break
        artifacts = execute_open_requests_for_routes(
            selected,
            configuration_claims=configurations,
            formalization=formalization,
            formalization_sections=formalization_sections,
            equations=equations,
            facts=facts,
            repository_provider=provider,
        )
        if not artifacts:
            result = result.model_copy(update={"stopped_reason": "no_progress"})
            break
        if sum(len(items) for items in artifacts.values()) == 0:
            result = result.model_copy(update={"stopped_reason": "no_progress"})
            break

        # A continuation provider records semantic gain while executing the
        # scoped research request.  Check that delta *before* recompiling the
        # whole authoring revision or invoking Writer: a repeated/empty
        # observation must not pay the expensive downstream cost again.
        continuation_rows: list[dict[str, Any]] = []
        if continuation_provider is not None:
            continuation_rows = continuation_provider.round_digests()
            continuation_rounds.append({
                "round": round_index,
                "request_ids": sorted(artifacts),
                "continuations": continuation_rows,
            })
            semantic_delta = False
            gain_total = 0
            from code2paper.agentic.callback_semantic_contract import (
                authoring_semantic_delta_changed,
            )
            for row in continuation_rows:
                gain = row.get("request_gain") or {}
                fps = int(gain.get("new_fingerprint_count") or 0)
                slots = list(gain.get("satisfied_slots") or ())
                digest = str(row.get("semantic_digest") or "")
                gain_total += fps + len(slots)
                if authoring_semantic_delta_changed(
                    previous_digests=seen_semantic_digests,
                    semantic_digest=digest,
                    new_fingerprint_count=fps,
                    satisfied_slots=slots,
                ):
                    semantic_delta = True
                    if digest:
                        seen_semantic_digests.add(digest)
            if gain_total == 0 or not semantic_delta:
                consecutive_no_gain += 1
            else:
                consecutive_no_gain = 0
            if consecutive_no_gain >= 1 and not semantic_delta:
                trace_rows.append({
                    "round": round_index,
                    "fulfilled_request_ids": [],
                    "resume_section_ids": [],
                    "stopped_reason": "no_information_gain",
                    "research_traces": _research_traces_for_selected(provider, selected),
                })
                result = result.model_copy(update={"stopped_reason": "no_information_gain"})
                break

        # A Research-Graph continuation changes the evidence authority.  Rebuild
        # every downstream authoring artifact before fulfilling the callback, so
        # the resumed Writer never consumes a stale brief/plan/formula view.
        revision_paths: dict[str, str] = {}
        if continuation_provider is not None:
            try:
                continuation_provider._last_round_request_ids = tuple(
                    item.request_id for item in selected
                )
                revision_paths = continuation_provider.recompile_authoring_revision(
                    out_root=out_root,
                    artifact_paths={**artifact_paths, **writer_paths},
                )
            except Exception as exc:  # noqa: BLE001 — do not fulfill against stale authority
                trace_rows.append({
                    "round": round_index,
                    "fulfilled_request_ids": [],
                    "resume_section_ids": [],
                    "recompile_error": f"{type(exc).__name__}:{str(exc)[:200]}",
                })
                result = result.model_copy(update={
                    "stopped_reason": f"revision_recompile_failed:{type(exc).__name__}",
                })
                break
            artifact_paths.update(revision_paths)

        try:
            slot_progress = _slot_progress_from_artifacts(artifacts, callback_root)
            slot_progress = _infer_missing_slot_progress(
                selected, artifacts, slot_progress, callback_root,
            )
            bundle = fulfill_writing_research_callbacks(
                bundle_path, artifacts, slot_progress=slot_progress or None,
            )
        except (OSError, TypeError, ValueError) as exc:
            detail = str(exc).splitlines()[0].strip()[:200]
            result = result.model_copy(update={
                "stopped_reason": (
                    f"fulfillment_failed:{type(exc).__name__}:{detail}"
                    if detail else f"fulfillment_failed:{type(exc).__name__}"
                ),
            })
            break
        local_fulfilled.update(
            request_id for request_id in artifacts
        )
        resumed.update(bundle.resume_section_ids)
        trace_rows.append({
            "round": round_index,
            "fulfilled_request_ids": sorted(artifacts),
            "resume_section_ids": list(bundle.resume_section_ids),
            "research_traces": _research_traces_for_selected(provider, selected),
        })

        # ``artifact_paths`` contains the authoring revision just rebuilt by
        # the Research continuation.  It must win over the initial Writer
        # snapshot: both mappings contain the same logical keys, and letting
        # ``writer_paths`` overwrite them makes the resumed Writer consume a
        # stale plan/fact/dossier while the freshly persisted artifacts claim
        # the opposite state.  Writer output paths remain available through
        # the left-hand mapping and are only replaced when the revision
        # actually produced a newer path.
        merged_paths = _merge_resumed_writer_paths(
            writer_paths=writer_paths,
            authoring_paths=artifact_paths,
        )
        resume_artifacts = {
            request_id: tuple(items)
            for request_id, items in (bundle.artifacts or {}).items()
        } or artifacts
        writer_result, next_paths = run_publication_method_writer(
            out_root=out_root,
            artifact_paths=merged_paths,
            llm_config=llm_config,
            llm_caller=llm_caller,
            resume_section_ids=bundle.resume_section_ids,
            research_callback_artifacts=resume_artifacts,
        )
        writer_status = effective_writer_transaction_status(writer_result)
        writer_blocked_reason = getattr(writer_result, "blocked_reason", "")
        # A blocked resume writes only publication_writer_result_v1.  Keep
        # the 06_authoring bundle/formalization paths so the next round does
        # not fall back to a stale frozen copy.
        writer_paths = {**writer_paths, **next_paths}
        bundle = _load_bundle(
            writer_paths.get("writing_research_callback_artifacts_v1", "")
            or bundle_path
        ) or bundle
        if writer_status in {"success", "incomplete"}:
            remaining_local = [
                item for item in bundle.requests
                if item.status in {"open", "partial"}
                and item.required_authority_lane in _LOCAL_OWNED_LANES
            ]
            if not remaining_local:
                result = result.model_copy(update={
                    "stopped_reason": "writer_success" if writer_status == "success" else "review_ready_with_warnings",
                })
                break

    else:
        result = result.model_copy(update={"stopped_reason": "budget_exhausted"})

    trace_path = ""
    if trace_rows or continuation_error:
        trace_path = str(
            Path(out_root) / "artifacts" / "research_tool_data"
            / "writing_callback_fulfillment_trace_v1.json"
        )
        trace_payload = {"schema_version": "1.0", "rounds": trace_rows}
        if continuation_rounds:
            trace_payload["research_graph_continuations"] = continuation_rounds
        if continuation_error:
            trace_payload["research_graph_continuation_error"] = continuation_error
        _atomic_write_text(
            trace_path,
            json.dumps(trace_payload, ensure_ascii=False, indent=2) + "\n",
        )
    result = result.model_copy(update={
        "local_requests_seen": len(local_seen),
        "local_requests_fulfilled": len(local_fulfilled),
        "external_requests_seen": len(external_seen),
        "resumed_section_ids": tuple(sorted(resumed)),
        "stopped_reason": result.stopped_reason or "completed",
        "trace_path": trace_path,
    })
    if trace_path:
        writer_paths = {
            **writer_paths,
            "research_continuation_trace_v1": trace_path,
        }
    return writer_paths, writer_status, writer_blocked_reason, result


def _research_traces_for_selected(
    provider: Any,
    selected: list[WritingResearchRequestV1],
) -> dict[str, list[Any]]:
    """Per-request traces; never copy the last request onto every selected id."""

    stored = getattr(provider, "research_traces_by_request", None)
    if isinstance(stored, dict):
        return {
            str(item.request_id): list(stored.get(item.request_id) or ())
            for item in selected
            if stored.get(item.request_id)
        }
    last = list(getattr(provider, "last_research_trace", None) or ())
    if last and len(selected) == 1:
        return {str(selected[0].request_id): last}
    return {}


def _load_facts(artifact_paths: dict[str, str]) -> CodeFactSetV1 | None:
    value = artifact_paths.get("code_facts_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        return load_code_facts_v1(value)
    except (OSError, TypeError, ValueError):
        return None


def _load_evidence_packets(artifact_paths: dict[str, str]) -> Any | None:
    value = artifact_paths.get("evidence_packets_v3", "")
    if not value or not Path(value).is_file():
        return None
    try:
        from code2paper.agentic.evidence_compiler_v3 import load_evidence_packets_v3

        return load_evidence_packets_v3(value)
    except (OSError, TypeError, ValueError):
        return None


def _load_claims(artifact_paths: dict[str, str]) -> Any | None:
    value = artifact_paths.get("atomic_claims_v3", "")
    if not value or not Path(value).is_file():
        return None
    try:
        from code2paper.agentic.evidence_compiler_v3 import load_atomic_claims_v3

        return load_atomic_claims_v3(value)
    except (OSError, TypeError, ValueError):
        return None


def _load_claims_input(artifact_paths: dict[str, str]) -> Any | None:
    value = artifact_paths.get("user_claims_input_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        from code2paper.agentic.autonomous_method_agent import UserClaimsInputV1

        return UserClaimsInputV1.model_validate_json(
            Path(value).read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None


def _load_plan(artifact_paths: dict[str, str]) -> MethodSectionPlanV2 | None:
    value = artifact_paths.get("method_section_plan_v2", "")
    if not value or not Path(value).is_file():
        return None
    try:
        return MethodSectionPlanV2.model_validate_json(Path(value).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None


def _load_argument_briefs(artifact_paths: dict[str, str]) -> Any | None:
    value = artifact_paths.get("method_argument_briefs_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        from code2paper.agentic.method_argument_brief_models import MethodArgumentBriefSetV1

        return MethodArgumentBriefSetV1.model_validate_json(
            Path(value).read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None


def _load_concept_cards(artifact_paths: dict[str, str]) -> Any | None:
    value = artifact_paths.get("method_concept_cards_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        from code2paper.agentic.method_concept_card_models import MethodConceptCardSetV1

        return MethodConceptCardSetV1.model_validate_json(
            Path(value).read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None


def _load_configurations(artifact_paths: dict[str, str]) -> ConfigurationClaimSetV1 | None:
    value = artifact_paths.get("configuration_claims_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        return ConfigurationClaimSetV1.model_validate_json(Path(value).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None


def _load_formalization(artifact_paths: dict[str, str]) -> Any | None:
    value = artifact_paths.get("formalization_result_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        from code2paper.agentic.formalization_agent import FormalizationResultV1

        return FormalizationResultV1.model_validate_json(
            Path(value).read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None


def _load_formalization_sections(artifact_paths: dict[str, str]) -> tuple[Any, ...] | None:
    value = artifact_paths.get("formalization_section_results_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        from code2paper.agentic.formalization_agent import load_formalization_section_results

        return load_formalization_section_results(value)
    except (OSError, TypeError, ValueError):
        return None


def _load_equations(artifact_paths: dict[str, str]) -> Any | None:
    value = artifact_paths.get("equation_claims_v1", "")
    if not value or not Path(value).is_file():
        return None
    try:
        from code2paper.agentic.equation_claims import EquationClaimSetV1

        return EquationClaimSetV1.model_validate_json(
            Path(value).read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None


def _default_llm_caller(config: Any, request: LLMRequest) -> LLMResponse:
    """Default live LLM caller used by the callback research supervisor."""

    return LLMClient(config).complete(request)


def _atomic_write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(target)


class _BudgetedRepositoryCallbackProvider:
    """Local repository research for one callback request, under budget.

    Seeds the search from the request's exact question, candidate symbols and
    known facts; executes bounded tool turns through the frozen research tool
    context; de-duplicates by ``(tool_name, arguments, path_scope)``; and
    produces a file-backed, digest-pinned artifact only when frozen facts
    match the observed spans.  No matching evidence leaves the request
    pending.
    """

    def __init__(
        self,
        *,
        runtime: Any,
        facts: CodeFactSetV1 | None,
        plan: MethodSectionPlanV2 | None,
        callback_root: Path,
        budget: WritingCallbackFulfillmentBudgetV1,
        argument_briefs: Any | None = None,
        supervisor_caller: Callable[..., Any] | None = None,
        supervisor_config: Any | None = None,
    ) -> None:
        self.runtime = runtime
        self.facts = facts
        self.plan = plan
        self.callback_root = callback_root
        self.budget = budget
        self.argument_briefs = argument_briefs
        self.supervisor_caller = supervisor_caller
        self.supervisor_config = supervisor_config
        self._ctx: ResearchToolContext | None = None
        self._seen_calls: set[tuple[str, str, tuple[str, ...]]] = set()
        self._new_facts: list[Any] = []
        self.last_research_trace: list[dict[str, Any]] = []
        self.research_traces_by_request: dict[str, list[dict[str, Any]]] = {}
        self._known_symbol_cache: set[str] | None = None

    def _known_symbol_names(self) -> set[str]:
        if self._known_symbol_cache is not None:
            return self._known_symbol_cache
        names: set[str] = set()
        for fact in (self.facts.facts if self.facts is not None else ()):
            values: list[Any] = [fact.subject, fact.object, *fact.semantic_context]
            for raw in values:
                items = raw if isinstance(raw, list) else [raw]
                for value in items:
                    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", str(value or "")):
                        names.add(token.casefold())
        self._known_symbol_cache = names
        return names

    def _ref_known_in_fact_store(self, ref: str) -> bool:
        _path, symbol = _parse_symbol_reference(ref, self._tool_context())
        if not symbol:
            return False
        return symbol.casefold() in self._known_symbol_names()
        self._known_symbol_cache: set[str] | None = None

    def _known_symbol_names(self) -> set[str]:
        if self._known_symbol_cache is not None:
            return self._known_symbol_cache
        names: set[str] = set()
        for fact in (self.facts.facts if self.facts is not None else ()):
            values: list[Any] = [fact.subject, fact.object, *fact.semantic_context]
            for raw in values:
                items = raw if isinstance(raw, list) else [raw]
                for value in items:
                    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", str(value or "")):
                        names.add(token.casefold())
        self._known_symbol_cache = names
        return names

    def _ref_known_in_fact_store(self, ref: str) -> bool:
        _path, symbol = _parse_symbol_reference(ref, self._tool_context())
        if not symbol:
            return False
        return symbol.casefold() in self._known_symbol_names()

    def _tool_context(self) -> ResearchToolContext:
        if self._ctx is None:
            self._ctx = self.runtime.tool_context()
        return self._ctx

    def __call__(self, request: WritingResearchRequestV1) -> dict[str, Any] | None:
        self._seen_calls.clear()
        self._new_facts = []
        self.last_research_trace = []
        try:
            return self._run_request(request)
        finally:
            self.research_traces_by_request[request.request_id] = list(
                self.last_research_trace
            )

    def _run_request(self, request: WritingResearchRequestV1) -> dict[str, Any] | None:
        if self.facts is None:
            return None
        terms = self._seed_terms(request)
        obligation_id = self._obligation_id_for(request)
        repo_snapshot_id = self.runtime.repo_snapshot.snapshot_id
        # Stage 5: refs the concept card already binds are the known baseline.
        # They are never re-verified as new evidence, so the researcher cannot
        # "fulfill" a request by re-deriving the same span overlap.  The
        # baseline still guides tool navigation (read around known refs), but
        # fact matching uses only refs/spans observed in this run.
        baseline_refs = {
            str(ref) for ref in (request.evidence_refs_used or ()) if str(ref).strip()
        }
        baseline_spans_tuple, baseline_reasons = resolve_request_baseline_spans(
            request,
            concept_bindings=None,
            argument_briefs=self.argument_briefs,
            require_resolvable=True,
        )
        if "baseline_binding_missing" in baseline_reasons:
            self.last_research_trace.append({
                "stop_reason": "baseline_binding_missing",
                "reasons": baseline_reasons,
            })
            return None
        baseline_spans = set(baseline_spans_tuple)
        observed_refs: set[str] = set(baseline_refs)
        new_observed_refs: set[str] = set()
        observed_spans: set[str] = set(baseline_spans)
        new_observed_spans: set[str] = set()
        consecutive_no_new = 0
        stop_reason = "budget_exhausted"
        for turn in range(self.budget.max_tool_turns_per_request):
            # R4: the research supervisor chooses the next action from the
            # request gap and the latest observed tool result; the scripted
            # sequence remains the deterministic fallback when no live LLM
            # supervisor is available.
            tool_call = self._supervisor_tool_call(
                request=request,
                terms=terms,
                observed_spans=observed_spans,
                observed_refs=observed_refs,
                obligation_id=obligation_id,
                repo_snapshot_id=repo_snapshot_id,
                turn=turn,
            )
            if tool_call is None:
                stop_reason = "no_further_tool_selected"
                break
            observation = execute_research_tool(self._tool_context(), tool_call)
            if observation.status == "invalid_request":
                stop_reason = "invalid_tool_request"
                break
            new_spans = set(observation.exact_span_ids) - observed_spans
            new_refs = set(observation.result_refs) - observed_refs
            observed_spans.update(new_spans)
            observed_refs.update(new_refs)
            new_observed_refs.update(new_refs)
            new_observed_spans.update(new_spans)
            # R4: genuinely new evidence is compiled through the normal
            # pipeline (behavior subgraph -> fixed fact compiler), not only
            # matched against already-compiled frozen facts.
            self._compile_new_facts(
                request=request,
                obligation_id=obligation_id,
                observed_refs=observed_refs,
                observed_spans=observed_spans,
                baseline_spans=baseline_spans,
            )
            if not new_spans and not new_refs:
                if turn >= len(terms):
                    consecutive_no_new += 1
            else:
                consecutive_no_new = 0
            matched = self._matched_facts(
                new_observed_spans,
                new_observed_refs,
                baseline_spans=baseline_spans,
            )
            self.last_research_trace.append({
                "turn": turn + 1,
                "tool": tool_call.tool_name,
                "reason": str(observation.status or ""),
                "new_spans": sorted(new_spans)[:8],
                "new_refs": sorted(new_refs)[:8],
                "new_facts": len(self._new_facts),
                "matched": bool(matched),
            })
            if matched:
                stop_reason = "evidence_matched"
                self.last_research_trace.append({"stop_reason": stop_reason})
                return self._write_artifact(
                    request, matched, observed_spans, observed_refs, obligation_id
                )
            if consecutive_no_new >= 2:
                stop_reason = "no_information_gain"
                break
        self.last_research_trace.append({"stop_reason": stop_reason})
        return None

    _SUPERVISOR_TOOLS = frozenset({
        "search_symbols", "list_repository_tree", "search_code",
        "read_symbol", "read_code_span", "find_references",
        "trace_call_path", "trace_data_flow", "inspect_control_flow",
        "inspect_configuration", "build_behavior_subgraph",
        "query_behavior_graph",
    })

    def _supervisor_tool_call(
        self,
        *,
        request: WritingResearchRequestV1,
        terms: list[str],
        observed_spans: set[str],
        observed_refs: set[str],
        obligation_id: str,
        repo_snapshot_id: str,
        turn: int,
    ) -> ResearchToolCallV1 | None:
        """R4: adaptive tool choice driven by the research supervisor.

        The supervisor receives the request gap, the candidate terms, the
        observed spans/refs so far and the last tool result, and returns one
        bounded tool call.  The choice is validated against the allow-list,
        its arguments are closed (strings/ints only, snapshot paths), and it
        is deduplicated by signature.  Falls back to the deterministic
        sequence when no live supervisor is configured.
        """

        if self.supervisor_caller is not None and self.supervisor_config is not None:
            choice = self._supervisor_llm_choice(
                request=request,
                terms=terms,
                observed_spans=observed_spans,
                observed_refs=observed_refs,
                obligation_id=obligation_id,
                turn=turn,
            )
            if choice is not None:
                tool_call = self._validated_supervisor_call(
                    choice=choice,
                    obligation_id=obligation_id,
                    repo_snapshot_id=repo_snapshot_id,
                )
                if tool_call is not None:
                    return tool_call
        return self._next_tool_call(
            terms=terms,
            observed_spans=observed_spans,
            observed_refs=observed_refs,
            obligation_id=obligation_id,
            repo_snapshot_id=repo_snapshot_id,
            turn=turn,
        )

    def _supervisor_llm_choice(
        self,
        *,
        request: WritingResearchRequestV1,
        terms: list[str],
        observed_spans: set[str],
        observed_refs: set[str],
        obligation_id: str,
        turn: int,
    ) -> dict[str, Any] | None:
        """One structured supervisor decision for the next research action."""

        class _SupervisorToolChoice(_PydanticBaseModel):
            model_config = ConfigDict(extra="forbid", frozen=True)

            tool_name: str
            arguments: dict[str, Any]
            reason: str = ""

        prompt = (
            "You are the research supervisor for a writing callback. Return only JSON matching the tool-choice schema. "
            "The Writer needs this gap closed: "
            + str(request.exact_question or request.missing_rhetorical_move or "")
            + " Candidate terms: " + ", ".join(terms[:8])
            + " Obligation: " + str(obligation_id)
            + " Turn budget remaining: " + str(max(0, self.budget.max_tool_turns_per_request - turn))
            + " Observed spans: " + ", ".join(sorted(observed_spans)[:6])
            + " Observed refs: " + ", ".join(sorted(observed_refs)[:6])
            + " Choose the ONE next repository tool from: "
            + ", ".join(sorted(self._SUPERVISOR_TOOLS))
            + ". Arguments must be exact strings/ints only: a snapshot-relative file path, symbol name, query, or span window. Never guess ids. If no further tool can help, return tool_name "" with empty arguments.",
        )
        request_payload = LLMRequest(
            prompt_template_id="agentic_writing_callback_supervisor_v1",
            prompt=prompt,
            schema_name="agentic_writing_callback_supervisor_v1",
            response_json_schema=json_schema_for(_SupervisorToolChoice),
            input_payload={
                "request_id": request.request_id,
                "exact_question": str(request.exact_question or ""),
                "candidate_terms": list(terms)[:8],
                "observed_spans": sorted(observed_spans)[:6],
                "observed_refs": sorted(observed_refs)[:6],
                "budget_remaining": max(0, self.budget.max_tool_turns_per_request - turn),
            },
        )
        try:
            response = self.supervisor_caller(self.supervisor_config, request_payload)
            if response.blocked_reason or not (response.text or "").strip():
                return None
            parsed, _error = try_parse_structured_response(
                response.text, _SupervisorToolChoice
            )
            if parsed is None:
                return None
            return parsed.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 — supervisor faults degrade to the scripted fallback
            self.last_research_trace.append(
                {"turn": turn + 1, "tool": "supervisor_fault", "reason": f"{type(exc).__name__}:{str(exc)[:120]}"}
            )
            return None

    def _validated_supervisor_call(
        self,
        *,
        choice: dict[str, Any],
        obligation_id: str,
        repo_snapshot_id: str,
    ) -> ResearchToolCallV1 | None:
        """Validate and dedupe one supervisor-chosen tool call."""

        ctx = self._tool_context()
        tool_name = str(choice.get("tool_name") or "").strip()
        if not tool_name:
            return None
        if tool_name not in self._SUPERVISOR_TOOLS:
            return None
        raw_arguments = choice.get("arguments") or {}
        if not isinstance(raw_arguments, dict):
            return None
        arguments: dict[str, Any] = {}
        for key, value in raw_arguments.items():
            if isinstance(value, str):
                arguments[str(key)] = value.strip()[:400]
            elif isinstance(value, int) and isinstance(value, bool) is False:
                arguments[str(key)] = value
            elif isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
                arguments[str(key)] = [str(item).strip()[:200] for item in value][:8]
        path = str(arguments.get("path") or "")
        if path:
            known = {item.path for item in ctx.repo_snapshot.included_files if item.kind == "file"}
            if path not in known:
                return None
        signature = (
            tool_name,
            json.dumps(arguments, sort_keys=True),
            tuple(arguments.get("path_scope", ()) or ()),
        )
        if signature in self._seen_calls:
            return None
        self._seen_calls.add(signature)
        return ResearchToolCallV1(
            tool_call_id=f"callback-supervisor-{tool_name}-{len(self._seen_calls)}",
            tool_name=tool_name,
            obligation_id=obligation_id,
            goal=f"Callback research for writer request on obligation {obligation_id}",
            repo_snapshot_id=repo_snapshot_id,
            arguments=arguments,
        )

    def _compile_new_facts(
        self,
        *,
        request: WritingResearchRequestV1,
        obligation_id: str,
        observed_refs: set[str],
        observed_spans: set[str],
        baseline_spans: set[str],
    ) -> None:
        """Compile genuinely new evidence through the normal pipeline.

        R4: for the symbols observed in this run, build a behavior subgraph
        and compile facts with the exact-condition compiler (post-Q1).  Only
        facts whose spans were observed here (outside the baseline) count as
        new evidence; re-reading baseline regions never re-derives a fact.
        """

        if self._new_facts or not observed_refs:
            return
        observed_refs = {
            ref for ref in observed_refs if not self._ref_known_in_fact_store(ref)
        }
        if not observed_refs:
            return
        ctx = self._tool_context()
        files = {
            item.path: ""
            for item in ctx.repo_snapshot.included_files
            if item.kind == "file"
        }
        adapter = ctx.language_adapter()
        index = adapter.index_symbols(
            repo_snapshot_id=self.runtime.repo_snapshot.snapshot_id,
            project_tree_hash=self.runtime.repo_snapshot.project_tree_hash,
            files=files,
        )
        symbol_ids: list[str] = []
        for ref in observed_refs:
            path, symbol = _parse_symbol_reference(ref, ctx)
            for item in (getattr(index, "symbols", ()) or ()):
                if (
                    str(getattr(item, "path", "")) == path
                    and str(getattr(item, "name", "")) == symbol
                    and str(getattr(item, "symbol_id", "") or "").strip()
                ):
                    symbol_ids.append(str(item.symbol_id))
                    break
        if not symbol_ids:
            return
        graph_result = build_behavior_subgraph(
            adapter=adapter,
            repo_snapshot_id=self.runtime.repo_snapshot.snapshot_id,
            project_tree_hash=self.runtime.repo_snapshot.project_tree_hash,
            files=files,
            symbol_index=index,
            symbol_ids=symbol_ids,
            depth=1,
            node_budget=4000,
        )
        if not graph_result.graph.nodes:
            return
        fact_set = compile_facts_from_behavior_graph(
            graph_result.graph,
            FactCompilerInputV1(
                obligation_id=obligation_id,
                behavior_node_ids=[node.node_id for node in graph_result.graph.nodes],
                behavior_relation_ids=[
                    relation.relation_id for relation in graph_result.graph.relations
                ],
                source_authority="executable_hard",
            ),
            repo_snapshot_id=self.runtime.repo_snapshot.snapshot_id,
            project_tree_hash=self.runtime.repo_snapshot.project_tree_hash,
            evidence_packet_digest=graph_result.graph.content_digest,
        )
        existing_ids = {fact.fact_id for fact in self.facts.facts}
        for fact in fact_set.facts:
            if fact.fact_id in existing_ids:
                continue
            spans = set(getattr(fact, "direct_span_ids", ()) or ())
            if any(
                _span_ids_overlap(span_id, observed_spans)
                and not _span_covered_by_any(span_id, baseline_spans)
                for span_id in spans
            ):
                self._new_facts.append(fact)

    def _seed_terms(self, request: WritingResearchRequestV1) -> list[str]:
        # Symbol/term candidates come first and are the authoritative seed;
        # question tokens are only auxiliary search seeds and stay capped so
        # they never starve the read phases of the tool budget.
        terms: list[str] = []
        seen_lower: set[str] = set()

        def add(term: str) -> None:
            clean = str(term or "").strip().strip("`'\"()[]")
            if not clean or len(clean) < 2:
                return
            lowered = clean.lower()
            if lowered in _SEED_STOPWORDS or lowered in seen_lower:
                return
            seen_lower.add(lowered)
            terms.append(clean)

        for value in (
            *request.candidate_symbols_or_terms,
            *request.current_known_facts,
            *request.missing_parts,
        ):
            for part in re.split(r"[\s,;:]+", str(value or "")):
                add(part)
        question = str(request.exact_question or "")
        for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_.]{2,}", question):
            add(match.group(0))
        return terms[:10]

    def _obligation_id_for(self, request: WritingResearchRequestV1) -> str:
        if self.plan is not None:
            for unit in self.plan.argument_units:
                if unit.argument_unit_id == request.argument_unit_id:
                    if unit.source_obligation_ids:
                        return unit.source_obligation_ids[0]
                    break
        return f"callback:{request.request_id}"

    def _next_tool_call(
        self,
        *,
        terms: list[str],
        observed_spans: set[str],
        observed_refs: set[str],
        obligation_id: str,
        repo_snapshot_id: str,
        turn: int,
    ) -> ResearchToolCallV1 | None:
        ctx = self._tool_context()

        def make_call(
            tool_name: str,
            arguments: dict[str, Any],
            *,
            path_scope: tuple[str, ...] = (),
        ) -> ResearchToolCallV1 | None:
            signature = (
                tool_name,
                json.dumps(arguments, sort_keys=True),
                path_scope,
            )
            if signature in self._seen_calls:
                return None
            self._seen_calls.add(signature)
            return ResearchToolCallV1(
                tool_call_id=f"callback-tool-{tool_name}-{len(self._seen_calls)}",
                tool_name=tool_name,
                obligation_id=obligation_id,
                goal=f"Callback research for writer request on obligation {obligation_id}",
                repo_snapshot_id=repo_snapshot_id,
                path_scope=path_scope,
                arguments=arguments,
            )

        # Phase A: search symbols.  Capped so question-derived seeds can never
        # starve the read phases below.
        search_count = min(len(terms), 4)
        if turn < search_count:
            return make_call("search_symbols", {"query": terms[turn], "kind_filter": ()})

        # Phase B: read the source files whose names match the seeded terms
        # (a term like ``train`` must reach ``train.py`` even when the symbol
        # index only matched config refs).
        file_read_start = search_count
        file_read_count = min(4, len(terms))
        if file_read_start <= turn < file_read_start + file_read_count:
            term = terms[turn - file_read_start]
            files = [
                item.path
                for item in ctx.repo_snapshot.included_files
                if item.kind == "file"
                and item.path.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs"))
                and _path_matches_term(item.path, term)
            ]
            for path in files[:3]:
                call = make_call(
                    "read_code_span",
                    {"path": path, "start_line": 1, "end_line": 0},
                    path_scope=(path,),
                )
                if call is not None:
                    return call

        # Phase C: ref-driven reads — the search refs carry exact
        # ``path:line`` anchors, so read those windows directly (the fastest
        # path to real spans), then read_symbol for symbol refs.
        refs = sorted(observed_refs)
        ref_start = file_read_start + file_read_count
        ref_index = turn - ref_start
        if refs and ref_index < len(refs) * 2:
            reference = refs[ref_index % len(refs)]
            path, line = _parse_path_line_reference(reference)
            if path and line and ref_index < len(refs):
                call = make_call(
                    "read_code_span",
                    {
                        "path": path,
                        "start_line": max(1, line - 3),
                        "end_line": line + 3,
                    },
                    path_scope=(path,),
                )
                if call is not None:
                    return call
            symbol_path, symbol = _parse_symbol_reference(reference, ctx)
            if symbol_path and symbol and symbol.casefold() not in self._known_symbol_names():
                call = make_call(
                    "read_symbol",
                    {"path": symbol_path, "symbol": symbol},
                )
                if call is not None:
                    return call
        if refs and ref_index >= len(refs) * 2 and ref_index < len(refs) * 3:
            _path, symbol = _parse_symbol_reference(refs[ref_index % len(refs)], ctx)
            if symbol:
                return make_call("find_references", {"symbol": symbol, "import_only": False})
        return None

    def _matched_facts(
        self,
        observed_spans: set[str],
        observed_refs: set[str],
        baseline_spans: set[str] | None = None,
    ) -> list[Any]:
        baseline_spans = baseline_spans or set()

        def is_new_span(span_id: str) -> bool:
            """A span is new evidence only when it is not confined to a
            baseline (already-bound) region.  Re-reading the same file window
            around a known ref must never re-derive the same fact."""
            if not _span_covered_by_any(span_id, baseline_spans):
                return True
            return False

        matched: list[Any] = []
        # R4: newly compiled evidence (from the fixed exact-condition
        # compiler) joins the frozen facts for matching; it is never
        # confused with baseline-bound re-reads.
        for fact in (*self.facts.facts, *self._new_facts):
            fact_spans = tuple(
                str(item) for item in (getattr(fact, "direct_span_ids", ()) or ())
            )
            if any(
                is_new_span(span_id)
                and _span_ids_overlap(span_id, observed_spans)
                for span_id in fact_spans
            ):
                matched.append(fact)
                continue
            if any(
                str(ref) in observed_refs
                for ref in (
                    f"fact:{fact.fact_id}",
                    f"span:{fact.fact_id}",
                )
            ):
                matched.append(fact)
        return matched[: self.budget.max_artifacts_per_request]

    def _write_artifact(
        self,
        request: WritingResearchRequestV1,
        matched_facts: list[Any],
        observed_spans: set[str],
        observed_refs: set[str],
        obligation_id: str,
    ) -> dict[str, Any]:
        fact_refs = tuple(fact.fact_id for fact in matched_facts)
        span_ids = tuple(dict.fromkeys(
            span_id for fact in matched_facts for span_id in fact.direct_span_ids
        ))
        relation_ids = tuple(dict.fromkeys(
            relation_id for fact in matched_facts for relation_id in fact.relation_evidence_ids
        ))
        summary = _fact_summary_for_writer(matched_facts)
        payload = {
            "schema_version": "1.0",
            "request_id": request.request_id,
            "section_id": request.section_id,
            "argument_unit_id": request.argument_unit_id,
            "authority_lane": "executable_hard",
            "summary_for_writer": summary,
            "matched_fact_ids": list(fact_refs),
            "matched_span_ids": list(span_ids),
            "matched_relation_ids": list(relation_ids),
            "tool_observation_refs": sorted(observed_refs)[:12],
            "research_trace": list(self.last_research_trace),
            "new_compiled_fact_ids": [fact.fact_id for fact in self._new_facts],
            "remaining_limits": [
                f"The repository evidence covers only the matched facts; the "
                "remaining parts of this request stay unresolved for review.",
            ],
            "source_snapshot_id": self.runtime.repo_snapshot.snapshot_id,
            "project_tree_hash": self.runtime.repo_snapshot.project_tree_hash,
            "obligation_id": obligation_id,
        }
        artifact_id = "writing-callback:" + request.request_id + ":" + _short_digest(payload)
        artifact_dir = (
            self.callback_root.parent
            / "research_tool_data" / "writing_callbacks" / request.request_id
        )
        artifact_path = artifact_dir / f"{artifact_id}.json"
        _atomic_write_text(artifact_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        digest = "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        reference = os_path_relative(artifact_path, self.callback_root)
        return {
            "artifact_id": artifact_id,
            "request_id": request.request_id,
            "section_id": request.section_id,
            "argument_unit_id": request.argument_unit_id,
            "authority_lane": "executable_hard",
            "artifact_ref": reference,
            "artifact_digest": digest,
            "validated": True,
        }


class _ResearchGraphContinuationProvider:
    """Research-Graph continuation for one callback request (review P0-Q4).

    This is the repaired mainline path: instead of a separate provider that
    self-authors ``validated=true``, the callback request becomes a NEW
    SCOPED OBLIGATION on the persisted child research state and the ORIGINAL
    Research LangGraph is restored and invoked with an additive tool budget:

        restored thread/checkpoint (same run id + snapshot + intent)
          -> new scoped obligation from the request
          -> existing research subgraph with additive budget
          -> new observations / behavior graph
          -> evidence packet -> fact -> claim/gap
          -> Concept judgment (exact span binding)
          -> placement (affected sections/units)
          -> owning-validator fulfillment report
          -> WriterView summary + affected-section resume

    The legacy ``_BudgetedRepositoryCallbackProvider`` remains only for old
    compatibility callers.  Product replay without a checkpoint supplies a
    ``ResearchContinuationSeedV1`` and still uses this graph provider.
    """

    def __init__(
        self,
        *,
        runtime: Any,
        research_stage_checkpoint: str | Path | None = None,
        research_continuation_seed: ResearchContinuationSeedV1 | None = None,
        facts: CodeFactSetV1 | None,
        plan: MethodSectionPlanV2 | None,
        callback_root: Path,
        budget: WritingCallbackFulfillmentBudgetV1,
        concept_cards: Any | None = None,
        argument_briefs: Any | None = None,
        artifact_paths: dict[str, str] | None = None,
        llm_config: Any | None = None,
        method_name: str = "",
    ) -> None:
        self.runtime = runtime
        self.research_stage_checkpoint = (
            str(research_stage_checkpoint)
            if research_stage_checkpoint is not None
            else ""
        )
        self.research_continuation_seed = research_continuation_seed
        self.facts = facts
        self.plan = plan
        self.callback_root = callback_root
        self.budget = budget
        self.concept_cards = concept_cards
        self.argument_briefs = argument_briefs
        self.artifact_paths = artifact_paths or {}
        self.llm_config = llm_config
        self.method_name = method_name
        self.claims_input: Any | None = None
        self.last_research_trace: list[dict[str, Any]] = []
        self.research_traces_by_request: dict[str, list[dict[str, Any]]] = {}
        self._loop: Any | None = None
        self._restored = False
        self._round_digests: list[dict[str, Any]] = []
        if not self.research_stage_checkpoint and self.research_continuation_seed is None:
            raise ValueError("research continuation requires checkpoint or seed")
        # Eager restore: an unauthenticatable checkpoint (foreign run id,
        # snapshot or intent) must fail here so the fulfillment loop can
        # degrade to the legacy provider instead of failing mid-round.
        self._restore_loop()

    def round_digests(self) -> list[dict[str, Any]]:
        """Digests of the continuation runs of the current round (trace)."""

        rows = list(self._round_digests)
        self._round_digests = []
        return rows

    def recompile_authoring_revision(
        self,
        *,
        out_root: str | Path,
        artifact_paths: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Rebuild all authoring authority after a graph continuation.

        Callback artifacts are not a parallel authoring pipeline.  Once the
        Research graph has produced a new observation, the ordinary evidence,
        coverage, equation, completeness, brief, facet-policy and section-plan
        compilers are run again.  The returned paths are consumed by the
        resumed Writer on the same iteration.
        """

        result = getattr(self, "last_result", None)
        if result is None:
            raise ValueError("research continuation result missing for recompile")
        from code2paper.agentic.autonomous_method_agent import (
            build_product_planning,
            build_typed_gaps,
            merge_product_evidence,
            persist_product_artifacts,
        )

        packet_set, fact_set, claim_set = merge_product_evidence(
            result,
            self.runtime,
        )
        if packet_set is None or fact_set is None or claim_set is None:
            raise ValueError("research continuation produced incomplete evidence sets")
        claims_input = self.claims_input
        if claims_input is None:
            from code2paper.agentic.autonomous_method_agent import UserClaimsInputV1

            claims_input = UserClaimsInputV1()
        existing_paths = artifact_paths or self.artifact_paths
        prior_plan = _load_plan(existing_paths)
        planning = build_product_planning(
            runtime=self.runtime,
            packet_set=packet_set,
            fact_set=fact_set,
            claim_set=claim_set,
            claims_input=claims_input,
            method_name=(
                self.method_name
                or str(getattr(self.runtime.intent_graph, "method_goal", "") or "Method")
            ),
            llm_config=self.llm_config,
            concept_cards=self.concept_cards,
            # Recompile the brief/facet lane from the new evidence.  Passing
            # the old brief set here would silently preserve stale licensing.
            argument_briefs=None,
            compile_argument_briefs=True,
            prior_plan=prior_plan,
            implementation_scope=getattr(
                getattr(result, "loop_state", None),
                "implementation_scope",
                None,
            ),
            behavior_graph=getattr(
                getattr(result, "loop_state", None),
                "behavior_graph",
                None,
            ),
        )
        old_briefs = self.argument_briefs
        new_briefs = planning.get("argument_briefs")
        authority_diff: list[dict[str, Any]] = []
        old_by_clause: dict[tuple[str, str], Any] = {}
        new_by_clause: dict[tuple[str, str], Any] = {}
        for brief in getattr(old_briefs, "briefs", ()) or ():
            for clause in getattr(brief, "clauses", ()) or ():
                old_by_clause[(str(brief.brief_id), str(clause.clause_id))] = clause
        for brief in getattr(new_briefs, "briefs", ()) or ():
            for clause in getattr(brief, "clauses", ()) or ():
                new_by_clause[(str(brief.brief_id), str(clause.clause_id))] = clause
        for key in sorted(set(old_by_clause).union(new_by_clause)):
            before = old_by_clause.get(key)
            after = new_by_clause.get(key)
            before_payload = {
                "license": (
                    str(getattr(before, "license", "") or "")
                    if before is not None else ""
                ),
                "bound_claim_ids": (
                    list(getattr(before, "bound_claim_ids", ()) or ())
                    if before is not None else []
                ),
                "bound_equation_ids": (
                    list(getattr(before, "bound_equation_ids", ()) or ())
                    if before is not None else []
                ),
                "bound_span_ids": (
                    list(getattr(before, "bound_span_ids", ()) or ())
                    if before is not None else []
                ),
            }
            after_payload = {
                "license": (
                    str(getattr(after, "license", "") or "")
                    if after is not None else ""
                ),
                "bound_claim_ids": (
                    list(getattr(after, "bound_claim_ids", ()) or ())
                    if after is not None else []
                ),
                "bound_equation_ids": (
                    list(getattr(after, "bound_equation_ids", ()) or ())
                    if after is not None else []
                ),
                "bound_span_ids": (
                    list(getattr(after, "bound_span_ids", ()) or ())
                    if after is not None else []
                ),
            }
            if before_payload != after_payload:
                authority_diff.append({
                    "kind": "brief_clause",
                    "brief_id": key[0],
                    "clause_id": key[1],
                    "before": before_payload,
                    "after": after_payload,
                    "direction": (
                        "downgrade"
                        if (
                            before_payload["license"] == "positively_licensed"
                            and after_payload["license"] != "positively_licensed"
                        )
                        else "upgrade"
                        if (
                            before_payload["license"] == ""
                            and after_payload["license"]
                            == "positively_licensed"
                        )
                        else "changed"
                    ),
                })
        old_policy_by_facet: dict[str, dict[str, Any]] = {}
        old_policy_path = str(
            existing_paths.get("candidate_facet_policies_v1") or ""
        ).strip()
        if old_policy_path and Path(old_policy_path).is_file():
            try:
                old_policy_payload = json.loads(
                    Path(old_policy_path).read_text(encoding="utf-8")
                )
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                old_policy_payload = {}
            old_policy_by_facet = {
                str(item.get("facet_id") or ""): item
                for item in old_policy_payload.get("policies") or ()
                if isinstance(item, dict) and str(item.get("facet_id") or "").strip()
            }
        new_policy_by_facet = {
            str(getattr(item, "facet_id", "") or ""): item
            for item in planning.get("facet_policies") or ()
            if str(getattr(item, "facet_id", "") or "").strip()
        }
        for facet_id in sorted(
            set(old_policy_by_facet).union(new_policy_by_facet)
        ):
            before = old_policy_by_facet.get(facet_id, {})
            after_model = new_policy_by_facet.get(facet_id)
            after = (
                after_model.model_dump(mode="json")
                if after_model is not None
                else {}
            )
            before_view = {
                key: before.get(key)
                for key in (
                    "alignment_status",
                    "prose_mode",
                    "candidate_allowed",
                    "verified_directly_allowed",
                    "bound_claim_ids",
                    "bound_span_ids",
                    "bound_equation_ids",
                )
            }
            after_view = {
                key: after.get(key)
                for key in before_view
            }
            if before_view != after_view:
                authority_diff.append({
                    "kind": "facet_policy",
                    "facet_id": facet_id,
                    "before": before_view,
                    "after": after_view,
                    "direction": (
                        "downgrade"
                        if (
                            before_view.get("alignment_status") == "entailed"
                            and after_view.get("alignment_status") != "entailed"
                        )
                        else "changed"
                    ),
                })
        summary: dict[str, Any] = {}
        summary_path = str(existing_paths.get("run_summary") or "").strip()
        if summary_path and Path(summary_path).is_file():
            try:
                loaded = json.loads(Path(summary_path).read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    summary = loaded
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                summary = {}
        summary["authoring_revision"] = {
            "origin": (
                self.research_continuation_seed.origin
                if self.research_continuation_seed is not None
                else "continued_from_research_stage_checkpoint"
            ),
            "new_evidence": {
                "packets": len(packet_set.packets),
                "facts": len(fact_set.facts),
                "claims": len(claim_set.claims),
            },
            "affected_request_ids": sorted(
                str(getattr(item, "request_id", item))
                for item in getattr(self, "_last_round_request_ids", ())
                if str(getattr(item, "request_id", item)).strip()
            ),
            "authority_diff_count": len(authority_diff),
            "authority_diff": authority_diff,
        }
        agent_trace: list[dict[str, Any]] = []
        trace_path = str(existing_paths.get("agent_trace") or "").strip()
        if trace_path and Path(trace_path).is_file():
            try:
                loaded_trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
                if isinstance(loaded_trace, list):
                    agent_trace = loaded_trace
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                agent_trace = []
        agent_trace.append({
            "phase": "authoring_revision_compile",
            "status": "ok",
            "detail": summary["authoring_revision"],
        })
        paths = persist_product_artifacts(
            out_root=out_root,
            runtime=self.runtime,
            claims_input=claims_input,
            loop_result=result,
            packet_set=packet_set,
            fact_set=fact_set,
            claim_set=claim_set,
            typed_gaps=build_typed_gaps(
                self.runtime,
                result,
                claim_set=claim_set,
            ),
            planning=planning,
            agent_trace=agent_trace,
            summary=summary,
        )
        authority_diff_path = (
            Path(out_root).expanduser().resolve()
            / "artifacts"
            / "authoring_authority_diff_v1.json"
        )
        authority_diff_payload = {
            "schema_version": "1.0",
            "origin": summary["authoring_revision"]["origin"],
            "changes": authority_diff,
        }
        authority_diff_payload["content_digest"] = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    authority_diff_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        )
        _atomic_write_text(
            authority_diff_path,
            json.dumps(
                authority_diff_payload,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        paths["authoring_authority_diff_v1"] = str(authority_diff_path)
        self.artifact_paths.update(paths)
        self.facts = fact_set
        self.argument_briefs = new_briefs
        self.plan = planning.get("plan")
        return paths

    # -- checkpoint restore -------------------------------------------------

    def _restore_loop(self) -> Any:
        """Restore the SAME research thread/checkpoint once per loop.

        ``load_research_stage_checkpoint`` authenticates the persisted child
        research state (run id, snapshot, tree hash, intent graph) and
        rebuilds the loop state with the original decision history and
        compiled evidence.  The continuation phase resets the *additive*
        turn counter (the checkpoint's own turn budget is closed) while
        keeping the decision history for trace continuity.
        """

        if self._restored:
            return self._loop
        self._restored = True
        if self.research_continuation_seed is not None:
            from code2paper.agentic.autonomous_method_agent import UserClaimsInputV1
            from code2paper.agentic.research_graph import (
                CompiledEvidence,
                initial_loop_state,
            )

            seed = self.research_continuation_seed
            if seed.run_id != self.runtime.run_id:
                raise ValueError("research_continuation_seed_run_id_mismatch")
            snapshot = self.runtime.repo_snapshot
            if (
                seed.repo_snapshot_id != snapshot.snapshot_id
                or seed.project_tree_hash != snapshot.project_tree_hash
            ):
                raise ValueError("research_continuation_seed_snapshot_mismatch")
            loop = initial_loop_state(self.runtime)
            packet_set = _load_evidence_packets(self.artifact_paths)
            fact_set = _load_facts(self.artifact_paths)
            claim_set = _load_claims(self.artifact_paths)
            if packet_set is not None and fact_set is not None and claim_set is not None:
                loop.compiled_evidence["frozen-authority"] = CompiledEvidence(
                    obligation_id="frozen-authority",
                    packet_set=packet_set,
                    fact_set=fact_set,
                    claim_set=claim_set,
                )
            self.claims_input = _load_claims_input(self.artifact_paths) or UserClaimsInputV1()
            self._loop = loop
            return loop
        from code2paper.agentic.autonomous_method_agent import (
            load_research_stage_checkpoint,
        )

        loop_result, _packets, _facts, _claims, _claims_input = (
            load_research_stage_checkpoint(
                path=self.research_stage_checkpoint,
                runtime=self.runtime,
            )
        )
        self.claims_input = _claims_input
        loop = loop_result.loop_state
        # The persisted thread terminated; the callback phase is a NEW
        # additive phase on the same thread with its own tool budget.
        loop.terminated = False
        loop.termination_reason = ""
        loop.turn_index = 0
        self._loop = loop
        return loop

    def _append_obligation(self, request: WritingResearchRequestV1) -> str:
        """Convert the request into a new scoped obligation (review P0)."""

        obligation_id = f"callback:{request.request_id}"
        if any(
            item.obligation_id == obligation_id
            for item in self.runtime.agenda.items
        ):
            return obligation_id
        from code2paper.agentic.research_nodes import seed_per_obligation_budgets

        terms = [
            str(term).strip()
            for term in (
                *request.candidate_symbols_or_terms,
                *request.missing_parts,
            )
            if str(term).strip()
        ]
        self.runtime.agenda.items.append(ResearchAgendaItemV1(
            obligation_id=obligation_id,
            priority="should_cover",
            author_text=str(request.exact_question or request.missing_rhetorical_move or ""),
            typed_behavior_targets=[
                TypedBehaviorTargetV1(
                    target_id=f"target:{request.request_id}",
                    search_terms=tuple(dict.fromkeys(terms)),
                    transformations=tuple(
                        str(value).strip()
                        for value in (request.current_known_facts or ())
                        if str(value).strip()
                    ),
                    outputs=(request.missing_rhetorical_move,),
                )
            ],
            missing_information=list(request.missing_parts or ()),
        ))
        self._loop.per_obligation_budgets.update(
            seed_per_obligation_budgets(
                self.runtime.agenda,
                self.runtime.budget_policy,
            )
        )
        return obligation_id

    def _seed_baseline_spans(self) -> tuple[str, ...]:
        """Return exact spans already covered by reconstructed authority.

        A reconstructed seed has no persisted request-to-span binding for
        every historical Writer request.  Treating that absence as a hard
        ``baseline_binding_missing`` return would prevent the promised
        repository continuation.  The frozen facts and packet spans are an
        honest, conservative baseline: a continuation must produce evidence
        outside the frozen authority rather than re-licensing it.
        """

        spans: set[str] = set()
        fact_set = self.facts or _load_facts(self.artifact_paths)
        for fact in getattr(fact_set, "facts", ()) or ():
            spans.update(
                str(span_id).strip()
                for span_id in (
                    *(getattr(fact, "direct_span_ids", ()) or ()),
                    *(getattr(fact, "relation_span_ids", ()) or ()),
                )
                if str(span_id).strip()
            )
        packet_set = _load_evidence_packets(self.artifact_paths)
        for packet in getattr(packet_set, "packets", ()) or ():
            spans.update(
                str(getattr(span, "span_id", "") or "").strip()
                for span in (getattr(packet, "spans", ()) or ())
                if str(getattr(span, "span_id", "") or "").strip()
            )
        return tuple(sorted(spans))

    # -- research graph invocation -----------------------------------------

    def __call__(self, request: WritingResearchRequestV1) -> dict[str, Any] | None:
        """Fulfill one request by continuing the original Research LangGraph."""

        self.last_research_trace = []
        loop = self._restore_loop()
        # Each request gets its own additive turn budget on the same thread.
        # Do not inherit terminated/turn_index from the previous request, and
        # do not drop earlier round_digests (the loop drains them once).
        loop.terminated = False
        loop.termination_reason = ""
        loop.turn_index = 0
        obligation_id = self._append_obligation(request)
        try:
            return self._continue_graph(request, loop, obligation_id)
        finally:
            self.research_traces_by_request[request.request_id] = list(
                self.last_research_trace
            )

    def _continue_graph(
        self,
        request: WritingResearchRequestV1,
        loop: Any,
        obligation_id: str,
    ) -> dict[str, Any] | None:
        from code2paper.agentic.research_graph import (
            build_research_subgraph,
            snapshot_loop_state,
        )
        from code2paper.agentic.state_v3 import empty_agent_state_v3

        baseline_spans_tuple, baseline_reasons = resolve_request_baseline_spans(
            request,
            concept_bindings={
                item.concept_key: item
                for item in (getattr(self.concept_cards, "bindings", ()) or ())
            } if self.concept_cards is not None else {},
            argument_briefs=self.argument_briefs,
            require_resolvable=True,
        )
        if "baseline_binding_missing" in baseline_reasons:
            if self.research_continuation_seed is None:
                self.last_research_trace.append({
                    "stop_reason": "baseline_binding_missing",
                    "reasons": baseline_reasons,
                })
                return None
            seed_spans = self._seed_baseline_spans()
            baseline_spans_tuple = tuple(
                sorted(set(baseline_spans_tuple).union(seed_spans))
            )
            baseline_reasons = [
                reason
                for reason in baseline_reasons
                if reason != "baseline_binding_missing"
            ]
            self.last_research_trace.append({
                "continuation_seed_baseline": {
                    "origin": self.research_continuation_seed.origin,
                    "past_decision_trace_available": (
                        self.research_continuation_seed.past_decision_trace_available
                    ),
                    "frozen_span_count": len(seed_spans),
                    "baseline_binding_recovered": bool(seed_spans),
                },
            })
        baseline_spans = set(baseline_spans_tuple)

        state = empty_agent_state_v3(
            run_id=self.runtime.run_id,
            repo_snapshot_id=self.runtime.repo_snapshot.snapshot_id,
            project_tree_hash=self.runtime.repo_snapshot.project_tree_hash,
        ).to_state_dict()
        state["active_obligation_id"] = obligation_id
        state["loop_state_snapshot"] = snapshot_loop_state(loop)

        subgraph = build_research_subgraph(
            self.runtime,
            max_turns=max(1, self.budget.max_tool_turns_per_request),
        )
        subgraph.invoke(state, config=None)
        result = subgraph.last_result
        if result is None:
            return None
        self.last_result = result
        if getattr(result, "loop_state", None) is not None:
            self._loop = result.loop_state
        self._build_trace(request, obligation_id, result)

        compiled = result.loop_state.compiled_evidence.get(obligation_id)
        if compiled is None:
            return None
        report = self._owning_validator_report(
            request=request,
            obligation_id=obligation_id,
            compiled=compiled,
            baseline_spans=baseline_spans,
        )
        if not report["validated"]:
            return None

        artifact = self._write_artifact(
            request=request,
            obligation_id=obligation_id,
            compiled=compiled,
            report=report,
            result=result,
            baseline_spans=baseline_spans,
        )
        self._round_digests.append({
            "request_id": request.request_id,
            "obligation_id": obligation_id,
            "validated": report["validated"],
            "partial": bool(report.get("partial")),
            "chain": artifact["chain_record_ref"],
            "semantic_digest": report.get("semantic_digest") or "",
            "request_gain": {
                "new_fact_count": len(report.get("fact_ids") or ()),
                "new_claim_count": len(report.get("claim_ids") or ()),
                "new_span_count": len(report.get("span_ids") or ()),
                "new_fingerprint_count": len(report.get("new_canonical_fingerprints") or ()),
                "satisfied_slots": list(report.get("satisfied_slots") or ()),
                "remaining_slots": list(report.get("remaining_slots") or ()),
            },
            "concept_judgment_absent": bool(report.get("concept_judgment_absent")),
        })
        return artifact["artifact"]

    # -- owning validator ---------------------------------------------------

    def _owning_validator_report(
        self,
        *,
        request: WritingResearchRequestV1,
        obligation_id: str,
        compiled: Any,
        baseline_spans: set[str],
    ) -> dict[str, Any]:
        """Owning-validator fulfillment report (review P0: never self-authors).

        ``validated`` is a pure function of the checks below: the evidence
        came through the research graph's compile gates, at least one fact is
        genuinely new evidence beyond the request's pre-bound refs, the
        compiled claims are supported/partial and bound to the obligation,
        and the artifact will be digest-pinned.  Any missing piece keeps the
        request pending with the typed reasons.
        """

        reasons: list[str] = []
        packet_set = getattr(compiled, "packet_set", None)
        fact_set = getattr(compiled, "fact_set", None)
        claim_set = getattr(compiled, "claim_set", None)
        facts = tuple(getattr(fact_set, "facts", ()) or ()) if fact_set is not None else ()
        claims = tuple(getattr(claim_set, "claims", ()) or ()) if claim_set is not None else ()
        packets = tuple(getattr(packet_set, "packets", ()) or ()) if packet_set is not None else ()

        if not facts:
            reasons.append("no_facts_compiled")
        if not packets:
            reasons.append("no_packets_compiled")
        new_facts = [
            fact for fact in facts
            if any(
                not _span_covered_by_any(span_id, baseline_spans)
                for span_id in (
                    *(getattr(fact, "direct_span_ids", ()) or ()),
                    *(getattr(fact, "relation_span_ids", ()) or ()),
                )
                if str(span_id).strip()
            )
        ]
        if not new_facts:
            reasons.append("no_new_evidence_beyond_used_refs")
        unsupported = [
            fact.fact_id for fact in facts
            if str(getattr(fact, "validation_status", "") or "") != "supported"
        ]
        if unsupported:
            reasons.append("unsupported_facts:" + ",".join(sorted(unsupported)[:6]))
        bound_claims = [
            claim for claim in claims
            if obligation_id in (
                str(item) for item in (getattr(claim, "covers_obligation_ids", ()) or ())
            )
        ]
        if not bound_claims:
            reasons.append("no_claims_bound_to_obligation")
        non_supported_claims = [
            claim.claim_id for claim in bound_claims
            if str(getattr(claim, "status", "") or "") not in {"supported", "partial"}
        ]
        if non_supported_claims:
            reasons.append("claims_not_supported:" + ",".join(sorted(non_supported_claims)[:6]))
        new_claim_ids = [str(claim.claim_id) for claim in bound_claims]
        span_ids = sorted(dict.fromkeys(
            str(span_id)
            for fact in new_facts
            for span_id in (
                *(getattr(fact, "direct_span_ids", ()) or ()),
                *(getattr(fact, "relation_span_ids", ()) or ()),
            )
            if str(span_id).strip()
        ))
        concept_judgment = self._concept_judgment({"span_ids": span_ids})
        uses_brief_callback = bool(
            self.argument_briefs is not None and request.target_brief_ids
        )
        if uses_brief_callback:
            concept_judgment = {}
            brief_failures = _validate_brief_slot_target(
                request,
                argument_briefs=self.argument_briefs,
            )
            if brief_failures:
                reasons.extend(brief_failures)
        else:
            concept_failures = _validate_concept_judgment_target(request, concept_judgment)
            if concept_failures:
                reasons.extend(concept_failures)
            elif self.concept_cards is not None and not request.concept_key.strip() and not concept_judgment:
                reasons.append("concept_judgment_absent")
        from code2paper.agentic.callback_semantic_contract import (
            callback_semantic_digest,
            canonical_fact_fingerprint,
            evaluate_mandatory_slot_coverage,
        )
        baseline_fingerprints = set(
            str(item) for item in (request.baseline_fact_fingerprints or ())
            if str(item).strip()
        )
        new_fingerprints = {
            canonical_fact_fingerprint(fact)
            for fact in new_facts
        }
        if baseline_fingerprints and not (new_fingerprints - baseline_fingerprints):
            reasons.append("no_canonical_information_gain")
        satisfied_slots, remaining_slots = evaluate_mandatory_slot_coverage(
            request,
            new_fact_ids=[str(fact.fact_id) for fact in new_facts],
            new_fingerprints=sorted(new_fingerprints),
            baseline_fingerprints=sorted(baseline_fingerprints),
            concept_judgment=concept_judgment,
            lane_fulfilled=(
                str(request.required_authority_lane or "") == "formal_derivation"
                and not reasons
            ),
        )
        if remaining_slots and not satisfied_slots:
            reasons.append(
                "remaining_mandatory_slots:" + ",".join(remaining_slots)
            )
        validated = not reasons
        partial = bool(validated and remaining_slots and satisfied_slots)
        semantic_digest = callback_semantic_digest(
            new_fingerprints=sorted(new_fingerprints - baseline_fingerprints),
            satisfied_slots=satisfied_slots,
            remaining_slots=remaining_slots,
            concept_keys=tuple(concept_judgment.keys()),
        )
        return {
            "validated": validated,
            "partial": partial,
            "reasons": reasons,
            "fact_ids": [str(fact.fact_id) for fact in new_facts],
            "claim_ids": new_claim_ids,
            "packet_ids": [str(packet.packet_id) for packet in packets],
            "span_ids": span_ids,
            "satisfied_slots": list(satisfied_slots),
            "remaining_slots": list(remaining_slots),
            "baseline_canonical_fingerprints": sorted(baseline_fingerprints),
            "new_canonical_fingerprints": sorted(new_fingerprints - baseline_fingerprints),
            "semantic_digest": semantic_digest,
            "validator": "research_graph_compile_gates_and_closure_checks",
        }

    # -- chain projection ---------------------------------------------------

    def _concept_judgment(self, report: dict[str, Any]) -> dict[str, list[str]]:
        """Affected Concept cards via EXACT span binding (review Q1)."""

        if self.concept_cards is None or not report.get("span_ids"):
            return {}
        new_spans = set(report["span_ids"])
        affected: dict[str, list[str]] = {}
        for binding in (getattr(self.concept_cards, "bindings", ()) or ()):
            key = str(getattr(binding, "concept_key", "") or "")
            if not key:
                continue
            bound = [
                str(span) for span in (getattr(binding, "source_span_ids", ()) or ())
                if str(span).strip()
                and any(
                    _span_ids_overlap(str(span), {span_id})
                    for span_id in new_spans
                )
            ]
            if bound:
                affected[key] = sorted(dict.fromkeys(bound))
        return affected

    def _placement(self, report: dict[str, Any], request: WritingResearchRequestV1) -> dict[str, Any]:
        """Affected sections/units from the request and the new claims."""

        section_ids: dict[str, list[str]] = {}
        if self.plan is not None:
            unit_by_id = {
                str(unit.argument_unit_id): unit
                for unit in self.plan.argument_units
            }
            for graph in self.plan.sections:
                units = [
                    unit_by_id[str(unit_id)]
                    for unit_id in graph.argument_unit_ids
                    if str(unit_id) in unit_by_id
                ]
                unit_ids = [str(unit.argument_unit_id) for unit in units]
                if request.argument_unit_id in unit_ids:
                    section_ids.setdefault(str(graph.section_id), []).extend(unit_ids)
                claim_ids = {
                    str(claim_id)
                    for unit in units
                    for claim_id in unit.claim_ids
                }
                if set(report.get("claim_ids") or ()) & claim_ids:
                    section_ids.setdefault(str(graph.section_id), []).extend(unit_ids)
        if not section_ids and request.section_id:
            section_ids[request.section_id] = [request.argument_unit_id]
        return {
            "affected_sections": sorted(section_ids),
            "sections": section_ids,
        }

    # -- persistence --------------------------------------------------------

    def _write_artifact(
        self,
        *,
        request: WritingResearchRequestV1,
        obligation_id: str,
        compiled: Any,
        report: dict[str, Any],
        result: Any,
        baseline_spans: set[str],
    ) -> dict[str, Any]:
        """Persist the full chain: observations -> behavior graph -> packet ->
        fact -> claim/gap -> Concept judgment -> placement -> WriterView."""

        packet_set = getattr(compiled, "packet_set", None)
        fact_set = getattr(compiled, "fact_set", None)
        claim_set = getattr(compiled, "claim_set", None)
        facts = tuple(getattr(fact_set, "facts", ()) or ()) if fact_set is not None else ()
        claims = tuple(getattr(claim_set, "claims", ()) or ()) if claim_set is not None else ()
        fact_by_id = {str(fact.fact_id): fact for fact in facts}
        new_fact_ids = set(report.get("fact_ids") or ())
        matched_facts = [fact_by_id[fact_id] for fact_id in new_fact_ids if fact_id in fact_by_id]
        summary = _fact_summary_for_writer(matched_facts)
        relation_ids = tuple(dict.fromkeys(
            relation_id
            for fact in matched_facts
            for relation_id in fact.relation_evidence_ids
        ))
        concept_judgment = self._concept_judgment(report)
        placement = self._placement(report, request)
        checkpoint_digest = ""
        try:
            checkpoint_digest = "sha256:" + hashlib.sha256(
                Path(self.research_stage_checkpoint).read_bytes()
            ).hexdigest()
        except OSError:
            pass
        observations = [
            _observation_digest(observation)
            for observation in result.loop_state.recent_observations
            if str(getattr(observation, "obligation_id", "") or "") == obligation_id
            or not any(
                str(getattr(item, "obligation_id", "") or "") == obligation_id
                for item in result.loop_state.recent_observations
            )
        ]
        fact_ids = list(report.get("fact_ids", []))
        if observations:
            fact_source = "this_observation"
        elif fact_ids:
            fact_source = "existing_behavior_graph"
        else:
            fact_source = "none"
        concept_judgment_absent = bool(
            self.concept_cards is not None
            and not (
                self.argument_briefs is not None and request.target_brief_ids
            )
            and not concept_judgment
        )
        if concept_judgment_absent:
            report = {**report, "validated": False, "concept_judgment_absent": True}
        chain_payload = {
            "schema_version": "1.0",
            "request_id": request.request_id,
            "obligation_id": obligation_id,
            "research_thread": {
                "run_id": self.runtime.run_id,
                "checkpoint_path": self.research_stage_checkpoint or None,
                "checkpoint_digest": checkpoint_digest,
                "continuation_origin": (
                    self.research_continuation_seed.origin
                    if self.research_continuation_seed is not None
                    else "continued_from_research_stage_checkpoint"
                ),
                "past_decision_trace_available": (
                    self.research_continuation_seed.past_decision_trace_available
                    if self.research_continuation_seed is not None
                    else True
                ),
                "continuation_seed_digest": (
                    self.research_continuation_seed.content_digest
                    if self.research_continuation_seed is not None
                    else ""
                ),
                "repo_snapshot_id": self.runtime.repo_snapshot.snapshot_id,
                "project_tree_hash": self.runtime.repo_snapshot.project_tree_hash,
            },
            "termination": {
                "turns_executed": getattr(result, "turns_executed", 0),
                "termination_reason": getattr(result, "termination_reason", ""),
                "final_status": str(
                    (getattr(result, "final_state", {}) or {}).get("status", "")
                ),
            },
            "observations": observations,
            "fact_source": fact_source,
            "request_gain": {
                "new_fact_count": len(fact_ids),
                "new_span_count": len(report.get("span_ids") or ()),
                "new_claim_count": len(report.get("claim_ids") or ()),
                "baseline_span_count": len(baseline_spans),
            },
            "behavior_graph": {
                "content_digest": getattr(
                    getattr(result.loop_state, "behavior_graph", None),
                    "content_digest",
                    "",
                ),
            },
            "evidence_packets": report.get("packet_ids", []),
            "facts": report.get("fact_ids", []),
            "claims": [
                {
                    "claim_id": claim.claim_id,
                    "status": claim.status,
                    "fact_ids": list(getattr(claim, "fact_ids", ()) or ()),
                }
                for claim in claims
                if str(claim.claim_id) in set(report.get("claim_ids") or ())
            ],
            "concept_judgment": concept_judgment,
            "concept_judgment_absent": concept_judgment_absent,
            "placement": placement,
            "recompile_chain": {
                "concept": sorted(concept_judgment),
                "placement": placement,
                "formula_obligation_ids": list(
                    request.target_formula_obligation_ids or ()
                ),
                "semantic_digest": report.get("semantic_digest") or "",
            },
            "validator_report": report,
            "decision_trace": [
                {
                    "turn_index": decision.turn_index,
                    "action": decision.action,
                    "obligation_id": decision.obligation_id,
                    "produced_by": decision.produced_by,
                    "tool_calls": [
                        {
                            "tool_name": call.tool_name,
                            "arguments": call.arguments,
                        }
                        for call in decision.selected_tool_calls
                    ],
                }
                for decision in result.decision_trace
                if decision.obligation_id == obligation_id
            ],
        }
        chain_dir = (
            self.callback_root.parent
            / "research_tool_data" / "writing_callbacks" / request.request_id
        )
        chain_dir.mkdir(parents=True, exist_ok=True)
        chain_path = chain_dir / f"research_continuation_{_short_digest(chain_payload)}.json"
        _atomic_write_text(chain_path, json.dumps(chain_payload, ensure_ascii=False, indent=2) + "\n")

        payload = {
            "schema_version": "1.0",
            "request_id": request.request_id,
            "section_id": request.section_id,
            "argument_unit_id": request.argument_unit_id,
            "authority_lane": "executable_hard",
            "obligation_id": obligation_id,
            "summary_for_writer": summary,
            "matched_fact_ids": list(report.get("fact_ids", [])),
            "matched_span_ids": list(report.get("span_ids", [])),
            "matched_relation_ids": list(relation_ids),
            "matched_claim_ids": list(report.get("claim_ids", [])),
            "concept_judgment": concept_judgment,
            "placement": placement,
            "validator_report": report,
            "mandatory_slots": list(request.mandatory_missing_slots or ()),
            "satisfied_slots": list(report.get("satisfied_slots") or ()),
            "remaining_slots": list(report.get("remaining_slots") or ()),
            "baseline_canonical_fingerprints": list(
                report.get("baseline_canonical_fingerprints") or ()
            ),
            "new_canonical_fingerprints": list(
                report.get("new_canonical_fingerprints") or ()
            ),
            "semantic_digest": report.get("semantic_digest") or "",
            "recompile_chain": {
                "concept": sorted(concept_judgment),
                "placement": placement,
                "formula_obligation_ids": list(
                    request.target_formula_obligation_ids or ()
                ),
                "semantic_digest": report.get("semantic_digest") or "",
            },
            "chain_record_ref": os_path_relative(chain_path, self.callback_root),
            "research_trace": list(self.last_research_trace),
            "remaining_limits": [
                "The repository evidence covers only the matched facts; the "
                "remaining parts of this request stay unresolved for review.",
            ],
            "source_snapshot_id": self.runtime.repo_snapshot.snapshot_id,
            "project_tree_hash": self.runtime.repo_snapshot.project_tree_hash,
            "continuation_origin": (
                self.research_continuation_seed.origin
                if self.research_continuation_seed is not None
                else "continued_from_research_stage_checkpoint"
            ),
        }
        artifact_id = "writing-callback:" + request.request_id + ":" + _short_digest(payload)
        artifact_dir = (
            self.callback_root.parent
            / "research_tool_data" / "writing_callbacks" / request.request_id
        )
        artifact_path = artifact_dir / f"{artifact_id}.json"
        _atomic_write_text(artifact_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        digest = "sha256:" + hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        reference = os_path_relative(artifact_path, self.callback_root)
        artifact = {
            "artifact_id": artifact_id,
            "request_id": request.request_id,
            "section_id": request.section_id,
            "argument_unit_id": request.argument_unit_id,
            "authority_lane": "executable_hard",
            "artifact_ref": reference,
            "artifact_digest": digest,
            "validated": bool(report["validated"]),
        }
        return {"artifact": artifact, "chain_record_ref": os_path_relative(chain_path, self.callback_root)}

    # -- trace --------------------------------------------------------------

    def _build_trace(
        self,
        request: WritingResearchRequestV1,
        obligation_id: str,
        result: Any,
    ) -> None:
        """Reader trace of the continuation run (compatible with the loop)."""

        rows: list[dict[str, Any]] = []
        for decision in result.decision_trace:
            if decision.obligation_id != obligation_id:
                continue
            rows.append({
                "turn": decision.turn_index,
                "tool": (
                    decision.selected_tool_calls[0].tool_name
                    if decision.selected_tool_calls else decision.action
                ),
                "reason": str(getattr(decision, "rationale", "") or ""),
                "produced_by": decision.produced_by,
                "new_facts": 0,
                "matched": False,
            })
        rows.append({
            "stop_reason": getattr(result, "termination_reason", ""),
            "terminated": bool(getattr(result, "terminated", False)),
            "turns_executed": getattr(result, "turns_executed", 0),
        })
        self.last_research_trace = rows


def _observation_digest(observation: Any) -> dict[str, Any]:
    return {
        "observation_id": str(getattr(observation, "observation_id", "") or ""),
        "tool_name": str(getattr(observation, "tool_name", "") or ""),
        "status": str(getattr(observation, "status", "") or ""),
        "result_refs": list(getattr(observation, "result_refs", ()) or ())[:8],
        "exact_span_ids": list(getattr(observation, "exact_span_ids", ()) or ())[:8],
    }


def _fact_summary_for_writer(facts: list[Any]) -> str:
    sentences: list[str] = []
    for fact in facts:
        subject = str(getattr(fact, "subject", "") or "").replace("_", " ").strip()
        predicate = str(getattr(fact, "predicate", "") or "").replace("_", " ").strip()
        obj = getattr(fact, "object", None)
        if isinstance(obj, list):
            obj = ", ".join(str(item) for item in obj[:3])
        sentences.append(
            f"Repository evidence shows that {subject} {predicate} {obj or '(an operand)'}."
        )
    return " ".join(sentences) or "Repository evidence matched the requested scope."


def _span_ids_overlap(span_id: str, observed_spans: set[str]) -> bool:
    """True when ``span_id`` overlaps any observed span on the same file.

    Reads return whole-file or wide ranges while facts pin exact operation
    ranges; exact-id equality would miss every genuine hit.  Parse
    ``span:<path>:<start>:<end>`` and compare numeric ranges per path.
    """

    def parsed(value: str) -> tuple[str, int, int] | None:
        parts = str(value or "").split(":")
        if len(parts) != 4 or parts[0] != "span":
            return None
        try:
            return parts[1], int(parts[2]), int(parts[3])
        except ValueError:
            return None

    target = parsed(span_id)
    if target is None:
        return span_id in observed_spans
    path, start, end = target
    for observed in observed_spans:
        other = parsed(observed)
        if other is None:
            continue
        if other[0] != path:
            continue
        if other[1] <= end and start <= other[2]:
            return True
    return False


def _brief_by_id(argument_briefs: Any | None) -> dict[str, Any]:
    if argument_briefs is None:
        return {}
    briefs = getattr(argument_briefs, "briefs", None)
    if briefs is None:
        return {}
    return {
        str(getattr(item, "brief_id", "") or ""): item
        for item in briefs
        if str(getattr(item, "brief_id", "") or "").strip()
    }


def _baseline_spans_for_brief(brief: Any) -> set[str]:
    spans: set[str] = set()
    for span in getattr(brief, "span_ids", ()) or ():
        cleaned = _span_id_from_ref(str(span)) or str(span).strip()
        if cleaned:
            spans.add(cleaned)
    for clause in getattr(brief, "clauses", ()) or ():
        for span in getattr(clause, "bound_span_ids", ()) or ():
            cleaned = _span_id_from_ref(str(span)) or str(span).strip()
            if cleaned:
                spans.add(cleaned)
    return spans


def _validate_brief_slot_target(
    request: WritingResearchRequestV1,
    *,
    argument_briefs: Any | None,
) -> list[str]:
    """Reject fulfillment when target brief ids are absent from the brief set."""

    brief_by_id = _brief_by_id(argument_briefs)
    targets = [
        str(item).strip()
        for item in (request.target_brief_ids or ())
        if str(item).strip()
    ]
    if not targets:
        return ["target_brief_ids_absent"]
    unknown = [brief_id for brief_id in targets if brief_id not in brief_by_id]
    if unknown:
        return ["unknown_target_brief_ids:" + ",".join(sorted(unknown)[:6])]
    if request.target_clause_ids:
        allowed_clause_ids = {
            str(clause.clause_id)
            for brief_id in targets
            for clause in (getattr(brief_by_id[brief_id], "clauses", ()) or ())
        }
        off_target = [
            clause_id
            for clause_id in request.target_clause_ids
            if str(clause_id) not in allowed_clause_ids
        ]
        if off_target:
            return [
                "off_target_clause_ids:" + ",".join(sorted(off_target)[:6])
            ]
    return []


def resolve_request_baseline_spans(
    request: WritingResearchRequestV1,
    *,
    concept_bindings: dict[str, Any] | None = None,
    argument_briefs: Any | None = None,
    require_resolvable: bool = True,
) -> tuple[tuple[str, ...], list[str]]:
    """Resolve digest-bound baseline spans for one callback request.

    ``frag-*`` fragment refs are never interpreted as an empty baseline.
    Concept-bearing requests with only unresolvable refs fail closed as
    ``baseline_binding_missing``.
    """

    reasons: list[str] = []
    spans: set[str] = {
        str(item).strip()
        for item in (request.baseline_span_ids or ())
        if str(item).strip()
    }
    concept_bindings = concept_bindings or {}
    brief_by_id = _brief_by_id(argument_briefs)
    target = str(request.concept_key or "").strip()
    if target and target in concept_bindings:
        binding = concept_bindings[target]
        for span in (getattr(binding, "source_span_ids", ()) or ()):
            cleaned = str(span).strip()
            if cleaned:
                spans.add(cleaned)
    for brief_id in request.target_brief_ids:
        brief = brief_by_id.get(str(brief_id).strip())
        if brief is not None:
            spans.update(_baseline_spans_for_brief(brief))
    unresolved_frag_refs: list[str] = []
    for ref in (request.evidence_refs_used or ()):
        raw = str(ref).strip()
        if not raw:
            continue
        span_id = _span_id_from_ref(raw)
        if span_id:
            spans.add(span_id)
        elif raw.startswith("frag-"):
            unresolved_frag_refs.append(raw)
    if unresolved_frag_refs:
        reasons.append(
            "unresolved_frag_refs:" + ",".join(sorted(unresolved_frag_refs)[:6])
        )
    if require_resolvable and target and (
        unresolved_frag_refs or (request.evidence_refs_used and not spans)
    ):
        reasons.append("baseline_binding_missing")
    elif require_resolvable and request.target_brief_ids and not spans and (
        unresolved_frag_refs or request.evidence_refs_used
    ):
        reasons.append("baseline_binding_missing")
    return tuple(sorted(spans)), reasons


def enrich_writing_research_request_baseline(
    request: WritingResearchRequestV1,
    *,
    concept_bindings: dict[str, Any] | None = None,
    argument_briefs: Any | None = None,
) -> WritingResearchRequestV1:
    """Persist exact baseline span IDs on a Writer-emitted request."""

    spans, _reasons = resolve_request_baseline_spans(
        request,
        concept_bindings=concept_bindings,
        argument_briefs=argument_briefs,
        require_resolvable=False,
    )
    return request.model_copy(update={"baseline_span_ids": spans})


def _validate_concept_judgment_target(
    request: WritingResearchRequestV1,
    concept_judgment: dict[str, list[str]],
) -> list[str]:
    """Reject fulfillment when judgment hits a non-target concept."""

    target = str(request.concept_key or "").strip()
    if not target:
        return []
    if concept_judgment.get(target):
        return []
    if concept_judgment:
        return [
            "off_target_concept_judgment:"
            + ",".join(sorted(concept_judgment.keys())[:6])
        ]
    return ["target_concept_judgment_absent"]


def _span_id_from_ref(ref: str) -> str:
    """Normalize a ``span:``-shaped evidence ref into its canonical span id.

    Concept-card binding refs may arrive as ``span:<path>:<start>:<end>``
    (canonical) or ``span:<path>:<line>`` (abbreviated).  The canonical form
    passes through unchanged; abbreviated forms expand ``<line>`` to a
    single-line span so baseline spans compare correctly against observed
    spans.  Non-span refs return ``""``.
    """

    raw = str(ref or "").strip()
    if not raw.startswith("span:"):
        return ""
    parts = raw[len("span:"):].split(":")
    if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
        return f"span:{parts[0]}:{parts[1]}:{parts[2]}"
    if len(parts) == 2 and parts[1].isdigit():
        return f"span:{parts[0]}:{parts[1]}:{parts[1]}"
    return raw


def _span_covered_by_any(span_id: str, baseline_spans: set[str]) -> bool:
    """True when ``span_id`` lies entirely inside one baseline span region.

    A span that is fully contained in an already-bound region carries no new
    evidence; only spans reaching outside the baseline can fulfill a request.
    """

    def parsed(value: str) -> tuple[str, int, int] | None:
        parts = str(value or "").split(":")
        if len(parts) != 4 or parts[0] != "span":
            return None
        try:
            return parts[1], int(parts[2]), int(parts[3])
        except ValueError:
            return None

    target = parsed(span_id)
    if target is None:
        return span_id in baseline_spans
    path, start, end = target
    for baseline in baseline_spans:
        other = parsed(baseline)
        if other is None or other[0] != path:
            continue
        if other[1] <= start and end <= other[2]:
            return True
    return False


def _slot_progress_from_artifacts(
    artifacts: dict[str, tuple[Any, ...]],
    callback_root: Path,
) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Read satisfied/remaining slots from persisted callback artifact files."""

    progress: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    for request_id, items in artifacts.items():
        for item in items:
            payload = _load_callback_artifact_payload(item, callback_root)
            if not payload:
                continue
            report = payload.get("validator_report") or payload
            satisfied = tuple(
                str(slot) for slot in (
                    payload.get("satisfied_slots")
                    or report.get("satisfied_slots")
                    or ()
                )
                if str(slot).strip()
            )
            remaining = tuple(
                str(slot) for slot in (
                    payload.get("remaining_slots")
                    or report.get("remaining_slots")
                    or ()
                )
                if str(slot).strip()
            )
            if satisfied or remaining:
                progress[str(request_id)] = (satisfied, remaining)
                break
    return progress


def _infer_missing_slot_progress(
    requests: list[Any] | tuple[Any, ...],
    artifacts: dict[str, tuple[Any, ...]],
    progress: dict[str, tuple[tuple[str, ...], tuple[str, ...]]],
    callback_root: Path,
) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Infer slot coverage for artifacts that have no persisted validator report."""

    from code2paper.agentic.callback_semantic_contract import (
        evaluate_mandatory_slot_coverage,
    )

    merged = dict(progress)
    for request in requests:
        request_id = str(getattr(request, "request_id", "") or "")
        if not request_id or request_id in merged:
            continue
        items = artifacts.get(request_id) or ()
        if not items:
            continue
        lane_fulfilled = any(
            str(getattr(item, "authority_lane", "") or "") == "formal_derivation"
            and bool(getattr(item, "validated", False))
            for item in items
        )
        new_fact_ids: list[str] = []
        for item in items:
            payload = _load_callback_artifact_payload(item, callback_root)
            new_fact_ids.extend(
                str(fact_id)
                for fact_id in (payload.get("matched_fact_ids") or ())
                if str(fact_id).strip()
            )
        satisfied, remaining = evaluate_mandatory_slot_coverage(
            request,
            new_fact_ids=new_fact_ids,
            concept_judgment={},
            lane_fulfilled=lane_fulfilled,
        )
        if satisfied or remaining:
            merged[request_id] = (satisfied, remaining)
    return merged


def _load_callback_artifact_payload(item: Any, callback_root: Path) -> dict[str, Any]:
    ref = str(getattr(item, "artifact_ref", "") or "")
    if isinstance(item, dict):
        ref = str(item.get("artifact_ref") or ref)
    if not ref:
        return {}
    path = Path(ref)
    if not path.is_file():
        path = (Path(callback_root) / ref).resolve()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _path_matches_term(path: str, term: str) -> bool:
    normalized = str(term or "").strip().strip("`'\"()[]")
    if not normalized:
        return False
    stem = Path(path).name
    return (
        normalized in path
        or normalized.lower() in stem.lower()
        or normalized.split(".")[0].lower() in stem.lower()
    )


def _parse_path_line_reference(reference: str) -> tuple[str, int]:
    """Parse ``symbol:<path>:<symbol>:<line>`` refs into (path, line)."""

    raw = str(reference or "").strip()
    if not raw.startswith("symbol:"):
        return "", 0
    parts = raw[len("symbol:"):].split(":")
    if len(parts) >= 3 and parts[-1].isdigit():
        return ":".join(parts[:-2]), int(parts[-1])
    return "", 0


def _parse_symbol_reference(
    reference: str,
    ctx: ResearchToolContext,
) -> tuple[str, str]:
    raw = str(reference or "").strip()
    if raw.startswith("symbol:"):
        raw = raw[len("symbol:"):]
    if raw.startswith("span:"):
        return "", ""
    if "::" in raw:
        path, _, symbol = raw.partition("::")
        return path, symbol.split(".")[0]
    if raw.startswith("module:"):
        return "", ""
    path, _, symbol = raw.rpartition(".")
    if path and symbol and not symbol.startswith("_"):
        return path, symbol
    return "", raw


def os_path_relative(path: Path, base: Path) -> str:
    return os.path.relpath(str(path.resolve()), str(base.resolve()))


def _short_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


__all__ = [
    "ResearchContinuationSeedV1",
    "WritingCallbackFulfillmentBudgetV1",
    "WritingCallbackFulfillmentResultV1",
    "build_research_continuation_seed",
    "enrich_writing_research_request_baseline",
    "fulfill_and_resume_writing_callbacks",
    "resolve_request_baseline_spans",
]
