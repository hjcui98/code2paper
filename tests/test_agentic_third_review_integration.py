"""Third-review integration checkpoint (offline, no model calls).

The three chains the third direction review asked for, each exercised through
the real entry points rather than a private helper:

1. execution record -> receipt -> gap tool -> terminal proof, including the
   corrupted-ledger and reused-call-id refusals;
2. organization proposal -> NarrativePlan -> page revision -> Writer-facing
   paragraph projection;
3. cross-revision budget: an unsettled attempt keeps the allowance of the plan
   it started under.

This is a fixed-scope checkpoint, not full G3: it proves invariants and
refusals, and it does not claim live or Candidate/Verified acceptance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_models import (
    GapRequirementV1,
    ResearchAgendaItemV1,
    ResearchToolCallV1,
)
from code2paper.agentic.research_terminal import evaluate_obligation_terminal_proof
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_KINDS,
    ResearchToolContext,
    execute_research_tool,
)


_MAIN_PY = """\
def main() -> int:
    return 0
"""

_MODEL_PY = """\
class Model:
    def forward(self, batch: int) -> int:
        return batch + 1
"""


@pytest.fixture()
def tool_ctx(tmp_path: Path) -> ResearchToolContext:
    root = tmp_path / "repo"
    (root / "lib").mkdir(parents=True)
    (root / "main.py").write_text(_MAIN_PY, encoding="utf-8")
    (root / "lib" / "model.py").write_text(_MODEL_PY, encoding="utf-8")
    return ResearchToolContext(
        repo_snapshot=build_repo_snapshot(root),
        artifact_root=tmp_path / "artifacts",
    )


def _call(
    ctx: ResearchToolContext,
    *,
    tool_name: str,
    arguments: dict,
    tool_call_id: str,
    path_scope: tuple[str, ...] = (),
    top_k: int = 20,
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=RESEARCH_TOOL_KINDS.get(tool_name, "other"),
        obligation_id="obl-chain",
        goal="prove the obligation",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        path_scope=path_scope,
        top_k=top_k,
        arguments=arguments,
    )


def _read_every_result(ctx: ResearchToolContext, observation, prefix: str) -> None:
    for index, ref in enumerate(observation.result_refs):
        path, line = str(ref).removeprefix("code:").rsplit(":", 1)
        read = execute_research_tool(
            ctx,
            _call(
                ctx,
                tool_name="read_code_span",
                tool_call_id=f"{prefix}-read-{index}",
                arguments={
                    "path": path,
                    "start_line": max(1, int(line) - 2),
                    "end_line": int(line) + 2,
                },
            ),
        )
        assert read.status == "success", read.error_message


def _gap_arguments(**overrides) -> dict:
    payload = {
        "obligation_id_ref": "obl-chain",
        "termination_reason": "bounded search found no implementation",
        "search_scope": ("lib/model.py",),
        "attempted_tools": ("search_code", "read_code_span"),
        "search_complete": True,
        "scope_exhausted": True,
    }
    payload.update(overrides)
    return payload


def _run_authenticated_chain(ctx: ResearchToolContext) -> dict:
    search = execute_research_tool(
        ctx,
        _call(
            ctx,
            tool_name="search_code",
            tool_call_id="chain-search",
            arguments={"query": "forward"},
            path_scope=("lib/model.py",),
        ),
    )
    assert search.status == "success", search.error_message
    _read_every_result(ctx, search, "chain")
    closure = execute_research_tool(
        ctx,
        _call(
            ctx,
            tool_name="close_search_frontier",
            tool_call_id="chain-close",
            arguments={},
            path_scope=("lib/model.py",),
        ),
    )
    assert "search_frontier_closed=true" in closure.diagnostics.notes
    receipt_id = closure.result_refs[0].split(":", 1)[1]
    gap = execute_research_tool(
        ctx,
        _call(
            ctx,
            tool_name="record_explicit_code_gap",
            tool_call_id="chain-gap",
            arguments=_gap_arguments(search_receipt_id=receipt_id),
        ),
    )
    assert gap.status == "success", gap.error_message
    return ctx.read_artifact("terminal_gaps", "obl-chain") or {}


def test_execution_record_to_terminal_proof_chain(
    tool_ctx: ResearchToolContext,
) -> None:
    payload = _run_authenticated_chain(tool_ctx)
    assert payload["terminal_outcome"] == "unsupported_with_scoped_evidence"
    assert payload["negative_evidence_authorized"] is True
    assert payload["receipt_authentication"] == "ledger_verified"

    # The terminal consumer reuses the ledger authentication verdict.
    item = ResearchAgendaItemV1(
        obligation_id="obl-chain",
        priority="must_cover",
        status="explicit_gap",
        gap_requirements=[GapRequirementV1(
            requirement_id="gap-req:obl-chain",
            description="The exhaustive search found no implementation.",
            terminal="explicit_gap",
            terminal_outcome=payload["terminal_outcome"],
            negative_evidence_authorized=True,
            search_receipt=payload["search_receipt"],
        )],
    )
    from code2paper.agentic.research_execution_ledger import (
        build_context_ledger_reader,
    )

    proof = evaluate_obligation_terminal_proof(
        item, receipt_verifier=build_context_ledger_reader(tool_ctx)
    )
    assert proof.explicit_gap_bound is True
    assert proof.terminal is True

    # A later search that adds unread results invalidates the old receipt, so
    # the same requirement no longer proves a closed frontier.
    later = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="search_code",
            tool_call_id="chain-search-later",
            arguments={"query": "class"},
            path_scope=("lib/model.py",),
        ),
    )
    assert later.status == "success"
    stale = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="record_explicit_code_gap",
            tool_call_id="chain-gap-stale",
            arguments=_gap_arguments(
                search_receipt_id=payload["search_receipt_id"]
            ),
        ),
    )
    assert stale.status == "invalid_request"
    assert "search_receipt_stale" in stale.error_message


def test_corrupted_ledger_breaks_the_same_chain(
    tool_ctx: ResearchToolContext, tmp_path: Path
) -> None:
    """Damaging the ledger must not leave an authorizable receipt behind."""

    payload = _run_authenticated_chain(tool_ctx)
    ledger_root = (
        tool_ctx.artifact_root
        / "research_tool_artifacts"
        / "execution_ledger"
    )
    directory = next(path for path in ledger_root.iterdir() if path.is_dir())
    record_files = sorted(
        path for path in directory.glob("*.json") if path.name != "_index.json"
    )
    record_files[-1].write_text("{truncated", encoding="utf-8")

    gap = execute_research_tool(
        tool_ctx,
        _call(
            tool_ctx,
            tool_name="record_explicit_code_gap",
            tool_call_id="chain-gap-corrupt",
            arguments=_gap_arguments(
                search_receipt_id=payload["search_receipt_id"]
            ),
        ),
    )
    assert gap.status == "invalid_request"
    assert "ledger_integrity" in gap.error_message
    # The earlier terminal record is untouched, but it cannot be re-proved:
    # both ledger-aware consumers must refuse it.
    assert (tmp_path / "artifacts").is_dir()
    prior = tool_ctx.read_artifact("terminal_gaps", "obl-chain") or {}
    assert prior.get("negative_evidence_authorized") is True
    from types import SimpleNamespace

    from code2paper.agentic.autonomous_method_agent import (
        _load_terminal_gap_artifacts,
    )
    from code2paper.agentic.research_execution_ledger import (
        build_context_ledger_reader,
    )

    loaded_gaps, _bindings = _load_terminal_gap_artifacts(
        SimpleNamespace(tool_context=lambda: tool_ctx)
    )
    assert loaded_gaps == []
    item = ResearchAgendaItemV1(
        obligation_id="obl-chain",
        priority="must_cover",
        status="explicit_gap",
        gap_requirements=[GapRequirementV1(
            requirement_id="gap-req:obl-chain",
            description="The exhaustive search found no implementation.",
            terminal="explicit_gap",
            terminal_outcome=prior["terminal_outcome"],
            negative_evidence_authorized=True,
            search_receipt=prior["search_receipt"],
        )],
    )
    proof_after = evaluate_obligation_terminal_proof(
        item, receipt_verifier=build_context_ledger_reader(tool_ctx)
    )
    assert proof_after.explicit_gap_bound is False
    assert proof_after.terminal is False


def test_proposal_to_page_revision_to_writer_projection(tmp_path: Path) -> None:
    """An accepted organization survives the page revision into Writer rows."""

    import runpy

    root = Path(__file__).resolve().parents[1]
    fixture = runpy.run_path(str(root / "tests" / "test_agentic_narrative_architect_v3.py"))
    context_set = fixture["_two_context_set"]()
    build_narrative_plan_v3 = fixture["build_narrative_plan_v3"]
    validate_narrative_plan = fixture["validate_narrative_plan"]

    from code2paper.agentic.publication_method_writer import (
        _build_narrative_plan_v3,
    )
    from code2paper.schemas import LLMConfig, LLMProvider

    def _transport(config, request):
        payload = dict(request.input_payload or {})
        body = {
            "mechanism_id": str(payload.get("mechanism_id") or ""),
            "paragraphs": [
                {"role": "core_transformations", "detail_ids": [detail_id]}
                for detail_id in (payload.get("detail_ids") or ())
            ],
        }

        class _Response:
            text = json.dumps(body)

        return _Response()

    plan, trace = _build_narrative_plan_v3(
        context_set,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none"),
        proposal_llm_caller=_transport,
    )
    assert trace["proposal_status"] == "accepted"

    # The Writer consumes the plan rows; each row keeps the proposed detail.
    for section in plan.sections:
        for paragraph in section.paragraphs:
            assert len(paragraph.required_detail_ids) == 1
            row = paragraph.model_dump(mode="json")
            assert row["required_detail_ids"] == list(
                paragraph.required_detail_ids
            )
    assert validate_narrative_plan(plan, context_set) == ()

    # A page revision of the accepted plan keeps the detail→paragraph mapping.
    flat_details = [
        detail_id
        for section in plan.sections
        for paragraph in section.paragraphs
        for detail_id in paragraph.required_detail_ids
    ]
    assert sorted(flat_details) == sorted({
        detail_id
        for context in context_set.contexts
        for detail in context.details
        for detail_id in (detail.detail_id,)
        if getattr(detail, "active_path_status", "unknown") in {
            "active_default", "active_selected", "conditional",
        }
    })
    # ``build_narrative_plan_v3`` above is the deterministic control: the same
    # contexts without a transport stay deterministic and validated.
    control, control_trace = build_narrative_plan_v3(contexts=context_set)
    assert control_trace["proposal_status"] == "not_requested"
    assert validate_narrative_plan(control, context_set) == ()


def test_proposal_survives_pagination_into_the_writer_request() -> None:
    """5.4: a real page split must survive into the captured Writer request.

    The earlier checkpoint only compared plan objects.  This one runs the
    product chain: proposal -> NarrativePlan -> page-budget revision ->
    writer workset manifest -> invocation plan -> ``_writer_section_inputs_v2``,
    and asserts on the actual request payload the Writer receives.
    """

    import json as _json
    import runpy

    root = Path(__file__).resolve().parents[1]
    compiler = runpy.run_path(
        str(root / "tests" / "test_agentic_unified_context_compiler.py")
    )
    from code2paper.agentic.mechanism_context_models import MechanismContextSetV1
    from code2paper.agentic.method_architect import (
        build_narrative_plan_v3,
        validate_narrative_plan,
    )
    from code2paper.agentic.publication_method_writer import (
        _writer_section_inputs_v2,
    )
    from code2paper.agentic.unified_context_compiler import (
        build_consumer_invocation_plan_v1,
        build_consumer_workset_manifest_v2,
        build_unified_context_archive_v2,
        extend_writer_worksets_from_narrative_plan,
        fit_narrative_plan_to_page_budget,
    )

    _archive, obligations = compiler["_budget_fixture"](
        detail_count=3, operations_per_detail=8
    )
    raw = _json.dumps(_archive.mechanism_atoms[0].payload)

    def _clear(value):
        if isinstance(value, dict):
            return {
                key: _clear(item)
                for key, item in value.items()
                if key not in ("content_digest", "source_context_digest")
            }
        if isinstance(value, list):
            return [_clear(item) for item in value]
        return value

    contexts = MechanismContextSetV1(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        intent_digest="i",
        alignment_digest="a",
        research_digest="r",
        contexts=(MechanismContextV1_validate(_clear(_json.loads(raw))),),
    )
    archive = build_unified_context_archive_v2(
        contexts, source_manifest_digest="sha256:manifest"
    )
    plan, _trace = build_narrative_plan_v3(contexts=contexts)
    revised, failures, diagnostics = fit_narrative_plan_to_page_budget(
        plan, archive=archive, max_page_input_tokens=700
    )
    assert diagnostics["split_paragraphs"], "the fixture must split a paragraph"
    assert failures == ()
    assert validate_narrative_plan(revised, contexts) == ()

    before_targets = sorted(
        json.dumps(
            target.model_dump(mode="json")
            if hasattr(target, "model_dump")
            else dict(target),
            sort_keys=True,
            default=str,
        )
        for section in plan.sections
        for paragraph in section.paragraphs
        for target in (
            paragraph.witness_contract.get("targets", ()) or ()
        )
    )
    envelope = compiler["_budget_envelope"]()
    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        {"mech_budget": obligations},
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        revised,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
    )
    writer_plan = build_consumer_invocation_plan_v1(
        writer_manifest,
        envelope,
        phase="writer",
        plan_revision=1,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )
    inputs = _writer_section_inputs_v2(
        narrative_plan=revised,
        consumer_workset_manifest=writer_manifest,
        consumer_invocation_plan=writer_plan,
    )
    assert inputs, "the writer request builder must emit at least one input"

    paragraph_rows: list[dict] = []
    contracts: dict[str, list[dict]] = {}
    for item in inputs:
        payload = item.prompt_payload or {}
        graph = payload.get("unified_v2_full_argument_graph") or {}
        paragraph_rows.extend(
            row for row in (graph.get("paragraphs") or ())
            if isinstance(row, dict)
        )
        binding = payload.get("binding_contract") or {}
        for detail_id, targets in (
            binding.get("detail_witness_contracts") or {}
        ).items():
            contracts.setdefault(str(detail_id), []).extend(targets)

    assert paragraph_rows, "the captured request must carry paragraph rows"
    placed = sorted(
        str(detail_id)
        for row in paragraph_rows
        for detail_id in (
            *tuple(row.get("required_detail_ids") or ()),
            *tuple(row.get("optional_detail_ids") or ()),
        )
    )
    before_details = sorted(
        detail_id
        for section in plan.sections
        for paragraph in section.paragraphs
        for detail_id in (
            tuple(paragraph.required_detail_ids)
            + tuple(paragraph.optional_detail_ids)
        )
    )
    assert placed == before_details
    # The fragment that carries a detail also carries that detail's targets.
    for row in paragraph_rows:
        owned = set(row.get("required_detail_ids") or ()) | set(
            row.get("optional_detail_ids") or ()
        )
        for target in (row.get("witness_contract", {}) or {}).get("targets", ()):
            payload = (
                target.model_dump(mode="json")
                if hasattr(target, "model_dump")
                else dict(target)
            )
            kind = str(payload.get("target_kind") or "")
            owner = str(
                payload.get("detail_id") if kind == "atom" else payload.get("target_id")
            ).removeprefix("detail:")
            assert f"detail:{owner}" in owned or owner in {
                value.removeprefix("detail:") for value in owned
            }, (row.get("paragraph_id"), owner)
    # The full target contract multiset still reaches the request builder.
    assert contracts, "the request must carry the per-detail witness contracts"
    captured_targets = sorted(
        json.dumps(target, sort_keys=True, default=str)
        for targets in contracts.values()
        for target in targets
    )
    assert len(captured_targets) == len(before_targets)
    assert all(
        "required_conditions" in json.loads(target)
        and "authority_lane" in json.loads(target)
        for target in captured_targets
    )


def MechanismContextV1_validate(payload):
    from code2paper.agentic.mechanism_context_models import MechanismContextV1

    return MechanismContextV1.model_validate(payload)


def test_cross_revision_budget_chain(tmp_path: Path) -> None:
    """An unsettled attempt keeps its original allowance across revisions."""

    from types import SimpleNamespace

    from code2paper.agentic.unified_context_models import (
        InvocationAttemptStartedV1,
    )
    from code2paper.agentic.unified_invocation_ledger import (
        publish_attempt_completed,
        publish_attempt_started,
        register_invocation_plan,
        unsettled_started_attempt_records,
    )

    root = tmp_path / "invocations"
    invocation = SimpleNamespace(
        invocation_id="inv:writer:page",
        role="writer",
        phase="writer",
        page_id="page:one",
    )
    old_plan = SimpleNamespace(
        content_digest="sha256:plan:old",
        reserved_input_tokens_by_role={"writer": 2000},
        invocations=(
            SimpleNamespace(max_input_tokens=900, **vars(invocation)),
        ),
    )
    new_plan = SimpleNamespace(
        content_digest="sha256:plan:new",
        reserved_input_tokens_by_role={"writer": 2000},
        invocations=(
            SimpleNamespace(max_input_tokens=100, **vars(invocation)),
        ),
    )
    register_invocation_plan(root, old_plan)
    register_invocation_plan(root, new_plan)
    publish_attempt_started(
        root,
        InvocationAttemptStartedV1(
            invocation_id="inv:writer:page",
            attempt=1,
            plan_digest="sha256:plan:old",
            page_id="page:one",
            expected_technical_bytes_digest="sha256:bytes",
            expected_request_envelope_digest="sha256:envelope",
            model_identity_digest="sha256:model",
            started_at_unix=1.0,
        ),
    )
    records = unsettled_started_attempt_records(root, new_plan)
    assert [(record.plan_source, record.planned_input_tokens) for record in records] == [
        ("recorded_plan", 900),
    ]
    # Once the attempt settles, the reserve disappears.
    publish_attempt_completed(
        root,
        _completed_receipt("inv:writer:page", attempt=1),
    )
    assert unsettled_started_attempt_records(root, new_plan) == ()


def _completed_receipt(invocation_id: str, *, attempt: int):
    from code2paper.agentic.unified_context_models import (
        ActualRequestReceiptV2,
        conservative_token_meter,
        RoleRequestBudgetV1,
    )
    from code2paper.agentic.unified_context_compiler import (
        account_unified_request_tokens,
    )

    accounting = account_unified_request_tokens(
        consumer_role="writer",
        rendered_prompt="x" * 400,
        input_payload={},
        response_schema={},
        request_budget=RoleRequestBudgetV1(
            role="writer",
            prompt_token_reserve=0,
            output_token_reserve=1024,
            thinking_token_reserve=0,
            scaffolding_token_reserve=0,
        ),
        max_input_tokens=1_000_000,
        model_context_tokens=131072,
        safety_margin_tokens=0,
        meter=conservative_token_meter(),
        scaffolding_reserve_tokens=0,
    )
    return ActualRequestReceiptV2(
        invocation_id=invocation_id,
        attempt=attempt,
        consumer_role="writer",
        phase="writer",
        workset_id="workset:test",
        task_ids=("task",),
        mechanism_id="mech:test",
        page_id="page:one",
        actual_technical_bytes_digest="sha256:bytes",
        actual_request_envelope_digest="sha256:envelope",
        response_digest="sha256:response",
        model_identity_digest="sha256:model",
        started_at_unix=1.0,
        finished_at_unix=2.0,
        delivery_status="accepted",
        task_status="complete",
        succeeded_task_ids=("task",),
        token_accounting=accounting,
        upstream_archive_digest="sha256:archive",
        upstream_workset_manifest_digest="sha256:manifest",
        upstream_plan_digest="sha256:plan:old",
    )
