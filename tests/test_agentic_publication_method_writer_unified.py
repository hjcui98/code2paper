"""Integration tests for unified and shadow_unified modes in publication_method_writer."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from code2paper.agentic.mechanism_context_models import (
    MechanismContextSetV1,
    MechanismContextSliceV1,
)
from code2paper.agentic.mechanism_context_pages import (
    build_shared_payload_delivery_receipt,
    build_shared_payload_manifest,
)
from code2paper.agentic.mechanism_context_projection import (
    build_mechanism_context_slices,
    build_mechanism_context_view,
    serialize_shared_mechanism_payload,
)
from code2paper.agentic.method_architect import NarrativePlanV3
from code2paper.agentic.method_content_trace import (
    MechanismInformationFunnelV1,
    MethodContentTraceV2,
)
from code2paper.agentic.publication_method_writer import (
    AuthoringContextMode,
    _assert_shared_payload_delivery,
    _assert_unified_v2_realizer_delivery,
    _realizer_detail_scope,
    _run_mechanism_formalizer,
    run_publication_method_writer,
)
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.llm.section_writer import WriterSectionInput
from code2paper.agentic.mechanism_context_models import (
    compute_consumer_request_digest,
    compute_shared_payload_digest,
)
from code2paper.schemas import LLMConfig
from tests.test_agentic_publication_method_writer import _artifacts, _config
from tests.test_agentic_mechanism_formalizer import _make_context


@pytest.mark.parametrize("reverse_order", [False, True])
@pytest.mark.parametrize("as_objects", [False, True])
def test_realizer_delivery_reports_latest_failure(reverse_order: bool, as_objects: bool) -> None:
    invocation = SimpleNamespace(invocation_id="inv:realizer:test", role="realizer", is_repair=False)
    receipts = [
        {"invocation_id": invocation.invocation_id, "attempt": 1,
         "delivery_status": "accepted", "task_status": "failed",
         "task_failures": [{"code": "realizer_witness_text_missing"}]},
        {"invocation_id": invocation.invocation_id, "attempt": 2,
         "delivery_status": "accepted", "task_status": "failed",
         "task_failures": [{"code": "realizer_required_witness_missing"}]},
    ]
    if reverse_order:
        receipts.reverse()
    values = [SimpleNamespace(**row) for row in receipts] if as_objects else receipts
    with pytest.raises(ValueError, match="realizer_required_witness_missing$"):
        _assert_unified_v2_realizer_delivery(
            workset_manifest=SimpleNamespace(_page_index=lambda: {}),
            invocation_plan=SimpleNamespace(invocations=[invocation]),
            receipts=values,
        )
    assert {row["task_failures"][0]["code"] for row in receipts} == {
        "realizer_witness_text_missing", "realizer_required_witness_missing",
    }


def _unified_budget_env() -> None:
    """Explicit small V2 live-budget values for deterministic tests."""

    os.environ.update({
        "CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS": "20000",
        "CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS": "400000",
        "CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS": "32",
        "CODE2PAPER_UNIFIED_MAX_WRITER_CALLS": "64",
        "CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS": "64",
        "CODE2PAPER_UNIFIED_MAX_BINDER_CALLS": "0",
        "CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE": "8",
        "CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS": "4",
        # R6: the per-request contract is declared, never defaulted in code.
        "CODE2PAPER_UNIFIED_SAFETY_MARGIN_TOKENS": "1024",
        "CODE2PAPER_UNIFIED_PROMPT_TOKEN_RESERVE": "2048",
        "CODE2PAPER_UNIFIED_THINKING_TOKEN_RESERVE": "0",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_FORMALIZER": "4096",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_WRITER": "8192",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_REALIZER": "8192",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_BINDER": "2048",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_FORMALIZER": "60000",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_WRITER": "60000",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_REALIZER": "60000",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_BINDER": "20000",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_FORMALIZER": "0",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_WRITER": "4096",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_REALIZER": "4096",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_BINDER": "0",
        "CODE2PAPER_MODEL_CONTEXT_TOKENS": "131072",
    })


def _clear_unified_budget_env() -> None:
    for key in (
        "CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS",
        "CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS",
        "CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS",
        "CODE2PAPER_UNIFIED_MAX_WRITER_CALLS",
        "CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS",
        "CODE2PAPER_UNIFIED_MAX_BINDER_CALLS",
        "CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE",
        "CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS",
        "CODE2PAPER_UNIFIED_SAFETY_MARGIN_TOKENS",
        "CODE2PAPER_UNIFIED_PROMPT_TOKEN_RESERVE",
        "CODE2PAPER_UNIFIED_THINKING_TOKEN_RESERVE",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_FORMALIZER",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_WRITER",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_REALIZER",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_BINDER",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_FORMALIZER",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_WRITER",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_REALIZER",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_BINDER",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_FORMALIZER",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_WRITER",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_REALIZER",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_BINDER",
        "CODE2PAPER_UNIFIED_RETRY_RESERVE_INPUT_TOKENS_WRITER",
        "CODE2PAPER_MODEL_CONTEXT_TOKENS",
    ):
        os.environ.pop(key, None)


def _with_source_manifest(paths: dict[str, str], tmp_path: Path) -> dict[str, str]:
    """Write the complete repository-authority closure required by V2."""

    from code2paper.agentic.behavior_graph import SymbolIndexV2, SymbolRefV1
    from code2paper.agentic.repo_snapshot import RepoSnapshot, SnapshotFile
    from code2paper.agentic.research_models import ImplementationScopeV1
    from code2paper.agentic.repository_authoring_artifacts import (
        repository_authoring_identity_payload,
    )
    from code2paper.agentic.source_inventory import (
        RepositorySourceEntryV1,
        RepositorySourceManifestV1,
    )

    # The fixture evidence uses a stable synthetic source digest.  The source
    # file is still materialized because the compiler's resolver reads the
    # frozen snapshot root when it builds operation excerpts.
    source_path = tmp_path / "encoder.py"
    source_path.write_text(
        "class Encoder:\n    def read(self, configured_input):\n        return configured_input\n",
        encoding="utf-8",
    )
    # R2: the declared source digest must match the bytes the resolver will
    # actually read; a placeholder digest is now refused as drift instead of
    # being silently served from the working tree.
    source_bytes = source_path.read_bytes()
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    snapshot = RepoSnapshot(
        snapshot_id="repo:writer",
        project_root=str(tmp_path),
        project_tree_hash="sha256:tree",
        included_files=[SnapshotFile(
            path="encoder.py",
            size=len(source_bytes),
            content_digest=source_digest,
        )],
    )
    symbol = SymbolRefV1(
        symbol_id="sym:encoder",
        path="encoder.py",
        qualified_name="Encoder",
        kind="class",
        start_line=1,
        end_line=3,
    )
    symbol_index = SymbolIndexV2(
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        indexed_files=1,
        indexed_symbols=1,
        symbols=[symbol],
        content_digest="sha256:fixture-symbol-index",
    )
    scope = ImplementationScopeV1(
        target_entry_symbol_ids=(symbol.symbol_id,),
        target_core_symbol_ids=(symbol.symbol_id,),
        ownership_evidence_refs=(symbol_index.content_digest,),
        confidence=1.0,
    )
    entry = RepositorySourceEntryV1(
        path="encoder.py",
        source_kind="first_party_executable",
        ownership_role="target_core",
        executable_authority=True,
        content_digest=source_digest,
        symbol_ids=(symbol.symbol_id,),
        classification_reason="fixture:first_party_executable",
    )
    manifest = RepositorySourceManifestV1(
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        entries=(entry,),
        target_core_paths=(entry.path,),
    )

    authoring_root = tmp_path / "artifacts" / "06_authoring"
    authoring_root.mkdir(parents=True, exist_ok=True)
    artifact_models = {
        "repo_snapshot_v2": snapshot,
        "repo_snapshot": snapshot,
        "symbol_index_v2": symbol_index,
        "symbol_index": symbol_index,
        "implementation_scope_v1": scope,
        "repository_source_manifest_v1": manifest,
    }
    for key, model in artifact_models.items():
        path = authoring_root / f"{key}.json"
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        paths[key] = str(path)
    identity_path = authoring_root / "repository_authoring_artifacts_v1.json"
    identity_path.write_text(
        json.dumps(
            repository_authoring_identity_payload(
                snapshot=snapshot,
                symbol_index=symbol_index,
                implementation_scope=scope,
                source_manifest=manifest,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    paths["repository_authoring_artifacts_v1"] = str(identity_path)
    return paths


def _unified_artifacts(tmp_path: Path) -> dict[str, str]:
    """Base artifacts plus the V2 source/budget preconditions."""

    _unified_budget_env()
    paths = _artifacts(tmp_path)
    paths = _with_source_manifest(paths, tmp_path)
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
    from code2paper.agentic.repo_snapshot import RepoSnapshot
    from code2paper.agentic.v3_runtime import build_research_agenda_from_intent_graph

    graph = IntentObligationGraphV2(
        method_goal="Explain the encoder.",
        obligations=[{
            "obligation_id": "obl-main",
            "kind": "method_mainline",
            "priority": "must_cover",
            "source_field": "method_mainline",
            "author_text": "Explain the encoder.",
        }],
    )
    graph_path = tmp_path / "artifacts" / "intent_obligation_graph_v2.json"
    graph_path.write_text(graph.model_dump_json(indent=2) + "\n")
    snapshot = RepoSnapshot.model_validate_json(
        Path(paths["repo_snapshot_v2"]).read_text()
    )
    agenda = build_research_agenda_from_intent_graph(
        graph,
        run_id="run:writer-fixture",
        repo_snapshot=snapshot,
    )
    # The unified writer fixture represents a completed research hand-off;
    # pending is reserved for the research supervisor and must fail the live
    # admission gate.
    for item in agenda.items:
        item.status = "supported"
        item.supported_claim_ids = ["claim-read"]
    agenda.refresh_content_digest()
    agenda_path = tmp_path / "artifacts" / "research_agenda_v1.json"
    agenda_path.write_text(agenda.model_dump_json(indent=2) + "\n")
    paths["intent_obligation_graph_v2"] = str(graph_path)
    paths["research_agenda_v1"] = str(agenda_path)
    return paths


def _mock_writer_caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
    """Mock section writer caller returning structured publication output."""
    if "binder" in getattr(request, "prompt_template_id", ""):
        binder_out = {
            "paragraph_id": request.input_payload.get("paragraph_id", ""),
            "witnesses": [],
            "unbound_target_ids": [],
        }
        return LLMResponse(
            text=json.dumps(binder_out),
            metadata=binder_out,
            response_hash="sha256:mock-binder-response",
            finish_reason="stop",
            token_usage={"completion_tokens": 50},
        )

    if (
        str(getattr(request, "prompt_template_id", "")) == "unified_realizer_page_v2"
        or (
            isinstance(getattr(request, "input_payload", None), dict)
            and str(request.input_payload.get("consumer_role", "")) == "realizer"
        )
    ):
        technical_payload = request.input_payload.get("technical_payload") or {}
        detail_ids: list[str] = []

        def add_detail(value: Any) -> None:
            text = str(value or "").strip()
            if not text:
                return
            canonical = "detail:" + text.removeprefix("detail:")
            if canonical not in detail_ids:
                detail_ids.append(canonical)

        for value in technical_payload.get("detail_ids", ()) or ():
            add_detail(value)
        for atom in technical_payload.get("atoms", ()) or ():
            if not isinstance(atom, dict):
                continue
            atom_id = str(atom.get("_atom_id") or "").strip()
            if str(atom.get("_atom_kind") or "") == "detail" or atom_id.startswith("detail:"):
                add_detail(atom.get("detail_id") or atom_id)

        markdown = "Realizer covers " + ", ".join(detail_ids)
        return LLMResponse(
            text=json.dumps({
                "draft_markdown": markdown,
                "rendered_detail_ids": detail_ids,
                "used_formula_package_ids": [],
                "witnesses": [
                    {
                        "witness_kind": "detail",
                        "target_id": detail_id,
                        "exact_text": detail_id,
                    }
                    for detail_id in detail_ids
                ],
            }),
            response_hash="sha256:mock-realizer-response",
            finish_reason="stop",
            token_usage={"completion_tokens": 50, "prompt_tokens": 300},
        )

    payload = request.prompt if isinstance(request.prompt, dict) else {}
    if isinstance(request.prompt, str):
        try:
            payload = json.loads(request.prompt)
        except Exception:
            payload = {}

    section_id = str(
        request.input_payload.get("section_id")
        or payload.get("section_id")
        or "sec_method_1"
    )
    heading = str(
        request.input_payload.get("heading")
        or payload.get("heading")
        or "Method"
    )
    narrative_plan = (
        request.input_payload.get("narrative_plan")
        or payload.get("narrative_plan")
        or {}
    )
    p_plan = (
        request.input_payload.get("paragraph_plan")
        or (
            narrative_plan.get("paragraphs", ())
            if isinstance(narrative_plan, dict)
            else ()
        )
        or payload.get("paragraph_plan")
        or ()
    )

    paragraphs_out = []
    if p_plan and isinstance(p_plan, (list, tuple)):
        for item in p_plan:
            row = item if isinstance(item, dict) else {}
            pid = row.get("paragraph_id") or getattr(item, "paragraph_id", "")
            if pid:
                contract = row.get("witness_contract") or {}
                targets = (
                    contract.get("targets", ())
                    if isinstance(contract, dict)
                    else ()
                )
                witness_rows = []
                rendered_detail_ids = []
                prose_fragments = [
                    "The encoder reads configured input and returns read value.",
                    "The operation path reads operation.",
                    "The operand uses configured input.",
                    "The output is read value.",
                ]
                for target in targets:
                    if not isinstance(target, dict):
                        continue
                    kind = str(target.get("target_kind") or "")
                    target_id = str(target.get("target_id") or "")
                    if not kind or not target_id:
                        continue
                    if kind == "detail":
                        exact_text = (
                            "encoder reads configured input and returns read value"
                        )
                        rendered_detail_ids.append(target_id)
                    elif kind == "atom" and ":operation:" in target_id:
                        exact_text = "operation path reads operation"
                    elif kind == "atom" and ":operand:" in target_id:
                        exact_text = "operand uses configured input"
                    elif kind == "atom" and ":output:" in target_id:
                        exact_text = "output is read value"
                    else:
                        continue
                    witness_rows.append({
                        "witness_kind": kind,
                        "target_id": target_id,
                        "exact_text": exact_text,
                    })
                paragraphs_out.append({
                    "paragraph_id": str(pid),
                    "paragraph_markdown": " ".join(prose_fragments),
                    "rendered_detail_ids": rendered_detail_ids,
                    "witnesses": witness_rows,
                })
    if not paragraphs_out:
        paragraphs_out.append({
            "paragraph_id": f"{section_id}_p1",
            "paragraph_markdown": "The encoder reads configured input and returns read value.",
        })

    body_prose = "\n\n".join(p["paragraph_markdown"] for p in paragraphs_out)
    prose = f"## {heading}\n\n{body_prose}"
    binding = request.input_payload.get("binding_contract") or {}
    completed_moves = list(binding.get("completed_rhetorical_moves", ["overview"]))
    if not completed_moves:
        completed_moves = ["overview"]

    structured = {
        "section_id": section_id,
        "heading_text": heading,
        "section_markdown": prose,
        "paragraphs": paragraphs_out,
        "used_argument_unit_ids": binding.get("used_argument_unit_ids", []),
        "used_claim_ids": binding.get("used_claim_ids", []),
        "used_equation_ids": binding.get("used_equation_ids", []),
        "used_configuration_ids": binding.get("used_configuration_ids", []),
        "completed_rhetorical_moves": completed_moves,
    }

    return LLMResponse(
        text=json.dumps(structured),
        metadata=structured,
        response_hash="sha256:mock-writer-response",
        finish_reason="stop",
        token_usage={"completion_tokens": 150, "prompt_tokens": 300},
    )


def test_run_publication_method_writer_unified_mode(tmp_path: Path) -> None:
    paths = _unified_artifacts(tmp_path)

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_mock_writer_caller,
        authoring_context_mode="unified",
    )

    assert result.status in ("success", "incomplete")
    assert result.status != "blocked"

    # Check that unified artifacts exist in outputs
    assert "mechanism_context_set_v1" in outputs
    assert "narrative_plan_v3" in outputs
    assert "method_content_trace_v2" in outputs
    assert "mechanism_information_funnel_v1" in outputs
    trace_payload = json.loads(
        Path(outputs["mechanism_shared_payload_trace_v1"]).read_text(encoding="utf-8")
    )
    assert trace_payload
    assert all(
        any(
            bool(receipt.get("accepted"))
            for receipt in (consumer.get("formalizer_page_delivery_receipts") or ())
        )
        for row in trace_payload
        for consumer in (row.get("writer_consumers") or ())
        if row.get("page_manifest_digest")
    )
    assert all(
        any(
            bool(receipt.get("accepted"))
            for receipt in (consumer.get("writer_page_delivery_receipts") or ())
        )
        for row in trace_payload
        for consumer in (row.get("writer_consumers") or ())
        if row.get("page_manifest_digest")
    )

    # Validate MechanismContextSetV1
    context_set = MechanismContextSetV1.model_validate_json(
        Path(outputs["mechanism_context_set_v1"]).read_text(encoding="utf-8")
    )
    assert len(context_set.contexts) >= 1
    assert context_set.contexts[0].mechanism_id == "mech_sym:encoder"

    # Validate NarrativePlanV3
    plan_v3 = NarrativePlanV3.model_validate_json(
        Path(outputs["narrative_plan_v3"]).read_text(encoding="utf-8")
    )
    assert len(plan_v3.sections) >= 1
    assert len(plan_v3.narrative_units) >= 1

    # Validate MethodContentTraceV2
    trace_v2 = MethodContentTraceV2.model_validate_json(
        Path(outputs["method_content_trace_v2"]).read_text(encoding="utf-8")
    )
    assert len(trace_v2.rows) >= 1
    assert trace_v2.funnel is not None

    # Validate MechanismInformationFunnelV1
    funnel = MechanismInformationFunnelV1.model_validate_json(
        Path(outputs["mechanism_information_funnel_v1"]).read_text(encoding="utf-8")
    )
    assert funnel.total_context_details >= 1
    assert funnel.architect_planned_details >= 1
    assert "context_to_plan" in funnel.funnel_survival_rates


def test_unified_writer_reuses_completed_page_receipts_on_resume(
    tmp_path: Path,
) -> None:
    """A second orchestration pass does not resend completed Writer pages."""

    paths = _unified_artifacts(tmp_path)
    try:
        first, _outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=_mock_writer_caller,
            authoring_context_mode="unified",
        )
        assert first.status != "blocked"

        writer_calls: list[LLMRequest] = []

        def counting_caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
            if request.prompt_template_id == "unified_writer_page_v2":
                writer_calls.append(request)
            return _mock_writer_caller(config, request)

        second, _resumed_outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=counting_caller,
            authoring_context_mode="unified",
        )
        assert second.status != "blocked"
        assert writer_calls == []
    finally:
        _clear_unified_budget_env()


@pytest.mark.parametrize("invalid_mode", ["empty", "heading_only"])
def test_writer_content_repair_uses_declared_retry_reserve_and_commits_only_after_acceptance(
    tmp_path: Path,
    invalid_mode: str,
) -> None:
    """Empty/title-only primaries need content repair before reuse."""

    paths = _unified_artifacts(tmp_path)
    os.environ["CODE2PAPER_UNIFIED_RETRY_RESERVE_INPUT_TOKENS_WRITER"] = "20000"
    writer_requests: list[LLMRequest] = []

    def caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
        if request.prompt_template_id == "unified_writer_page_v2":
            writer_requests.append(request)
            if len(writer_requests) == 1:
                if invalid_mode == "empty":
                    return LLMResponse(
                        text="",
                        response_hash="sha256:mock-writer-empty-content",
                        blocked_reason=(
                            "provider_stream_finished_before_complete_json"
                        ),
                        finish_reason="stop",
                        token_usage={"completion_tokens": 0, "prompt_tokens": 300},
                    )
                narrative_plan = request.input_payload.get("narrative_plan") or {}
                paragraphs = [
                    {
                        "paragraph_id": str(row.get("paragraph_id") or ""),
                        "paragraph_markdown": (
                            "## Method"
                            if invalid_mode == "heading_only"
                            else "The encoder reads configured input reliably."
                        ),
                    }
                    for row in (
                        narrative_plan.get("paragraphs", ())
                        if isinstance(narrative_plan, dict)
                        else ()
                    )
                    if isinstance(row, dict) and row.get("paragraph_id")
                ]
                section_id = str(request.input_payload.get("section_id") or "")
                body = "\n\n".join(
                    str(row["paragraph_markdown"]) for row in paragraphs
                )
                return LLMResponse(
                    text=json.dumps({
                        "section_id": section_id,
                        "heading_text": "Method",
                        "section_markdown": (
                            "## Method"
                            if invalid_mode == "heading_only"
                            else f"## Method\n\n{body}"
                        ),
                        "paragraphs": paragraphs,
                    }),
                    response_hash="sha256:mock-writer-invalid-content",
                    finish_reason="stop",
                    token_usage={"completion_tokens": 80, "prompt_tokens": 300},
                )
        return _mock_writer_caller(config, request)

    try:
        result, _outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="unified",
        )
        # Exercise the production resume path with the same plan and identity.
        resumed, _resumed_outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="unified",
        )
    finally:
        _clear_unified_budget_env()

    assert result.status in ("success", "incomplete")
    assert result.status != "blocked"
    assert resumed.status != "blocked"
    assert len(writer_requests) == 2
    acceptance_files = sorted(
        (tmp_path / "artifacts" / "06_authoring" / "invocations").rglob(
            "*.content-acceptance.json"
        )
    )
    acceptance_rows = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in acceptance_files
    ]
    assert any(row["content_acceptance_status"] == "rejected" for row in acceptance_rows)
    assert any(
        row["content_acceptance_status"] == "accepted"
        and row["resume_eligible"] is True
        and row["repair_committed"] is True
        for row in acceptance_rows
    )


def test_rejected_nonempty_writer_repair_is_not_resume_eligible(
    tmp_path: Path,
) -> None:
    """A title-only repair remains an attempt, not a reusable page."""

    paths = _unified_artifacts(tmp_path)
    os.environ["CODE2PAPER_UNIFIED_RETRY_RESERVE_INPUT_TOKENS_WRITER"] = "20000"
    writer_requests: list[LLMRequest] = []
    response_hash = "sha256:writer-identical-response-hash"

    def title_only_response(request: LLMRequest) -> LLMResponse:
        narrative_plan = request.input_payload.get("narrative_plan") or {}
        paragraphs = [
            {
                "paragraph_id": str(row.get("paragraph_id") or ""),
                "paragraph_markdown": "## Method",
            }
            for row in (
                narrative_plan.get("paragraphs", ())
                if isinstance(narrative_plan, dict)
                else ()
            )
            if isinstance(row, dict) and row.get("paragraph_id")
        ]
        section_id = str(request.input_payload.get("section_id") or "")
        return LLMResponse(
            text=json.dumps({
                "section_id": section_id,
                "heading_text": "Method",
                "section_markdown": "## Method",
                "paragraphs": paragraphs,
            }),
            response_hash=response_hash,
            finish_reason="stop",
            token_usage={"completion_tokens": 20, "prompt_tokens": 300},
        )

    def caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
        if request.prompt_template_id == "unified_writer_page_v2":
            writer_requests.append(request)
            if len(writer_requests) == 1:
                return LLMResponse(
                    text="",
                    response_hash=response_hash,
                    blocked_reason=(
                        "provider_stream_finished_before_complete_json"
                    ),
                    finish_reason="length",
                    token_usage={"completion_tokens": 0, "prompt_tokens": 300},
                )
            if len(writer_requests) == 2:
                return title_only_response(request)
            return _mock_writer_caller(config, request).model_copy(
                update={"response_hash": response_hash}
            )
        return _mock_writer_caller(config, request)

    try:
        first, _outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="unified",
        )
        # A page whose primary and bounded repair both fail content gates may
        # block the aggregate structural gate; that is still a valid failure
        # outcome for this regression.  The key property is that the next
        # orchestration pass must execute the page again.
        assert first.status in {"blocked", "incomplete"}

        acceptance_files = sorted(
            (tmp_path / "artifacts" / "06_authoring" / "invocations").rglob(
                "*.content-acceptance.json"
            )
        )
        acceptance_rows = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in acceptance_files
        ]
        assert len(acceptance_rows) == 2
        assert all(row["content_acceptance_status"] == "rejected" for row in acceptance_rows)
        assert all(row["resume_eligible"] is False for row in acceptance_rows)
        assert all(row["repair_committed"] is False for row in acceptance_rows)
        assert any(
            row["attempt"] == 2
            and "paragraph_body_not_substantive" in row["failures"]
            for row in acceptance_rows
        )

        from code2paper.agentic.unified_context_models import ConsumerInvocationPlanV1
        from code2paper.agentic.unified_invocation_ledger import build_resume_plan

        authoring_root = tmp_path / "artifacts" / "06_authoring"
        plan = ConsumerInvocationPlanV1.model_validate_json(
            (authoring_root / "consumer_invocation_plan_v1.2.json").read_text(
                encoding="utf-8"
            )
        )
        resume = build_resume_plan(
            tmp_path / "artifacts" / "06_authoring" / "invocations",
            plan,
            archive_digest=plan.archive_digest,
            workset_manifest_digest=plan.workset_manifest_digest,
            model_identity_digest=plan.model_identity_digest,
        )
        invocation_id = plan.invocations[0].invocation_id
        assert resume.decisions[invocation_id].decision == "execute"
        # The rejected primary/repair pair must not make the page reusable.
        assert len(writer_requests) == 2
    finally:
        _clear_unified_budget_env()


def test_realizer_receipt_cannot_satisfy_section_writer_receipt() -> None:
    context = _make_context()
    view = build_mechanism_context_view(context)
    slices = build_mechanism_context_slices(view)
    payload_bytes = serialize_shared_mechanism_payload(slices)
    shared_digest = compute_shared_payload_digest(slices)
    manifest = build_shared_payload_manifest(slices)
    page = manifest.pages[0]
    mechanism_id = context.mechanism_id
    section_id = "MA-S1"
    source_context_digest = context.source_context_digest or context.content_digest
    writer_request_digest = compute_consumer_request_digest(
        shared_digest,
        {
            "role": "writer",
            "section_id": section_id,
            "mechanism_id": mechanism_id,
        },
    )
    writer_input = WriterSectionInput(
        section_id=section_id,
        heading="Mechanism",
        prompt_payload={
            "section_id": section_id,
            "narrative_plan": {"mechanism_ids": [mechanism_id]},
            "shared_contexts": [page.serialized_bytes.decode("utf-8")],
            "shared_context_metadata": [{
                "mechanism_id": mechanism_id,
                "page_index": 0,
                "page_manifest_digest": manifest.content_digest,
                "page_digest": page.content_digest,
                "page_bytes_digest": page.technical_bytes_digest,
                "shared_payload_bytes_digest": "sha256:" + hashlib.sha256(payload_bytes).hexdigest(),
                "shared_payload_digest": shared_digest,
                "source_context_digest": source_context_digest,
                "view_digest": view.view_digest,
                "slice_digests": [item.slice_digest for item in slices],
                "core_detail_ids": [
                    value for item in slices for value in item.core_detail_ids
                ],
                "consumer_request_digest": writer_request_digest,
            }],
        },
    )
    formalizer_receipt = build_shared_payload_delivery_receipt(
        manifest,
        consumer_role="formalizer",
        delivered_page_bytes=[page.serialized_bytes],
        actual_payload_bytes=payload_bytes,
    ).model_dump(mode="json")
    formalizer_trace = {
        "mechanism_id": mechanism_id,
        "shared_payload": payload_bytes.decode("utf-8"),
        "shared_payload_bytes_digest": "sha256:" + hashlib.sha256(payload_bytes).hexdigest(),
        "shared_payload_digest": shared_digest,
        "source_context_digest": source_context_digest,
        "view_digest": view.view_digest,
        "slice_digests": [item.slice_digest for item in slices],
        "consumer_request_digest": compute_consumer_request_digest(
            shared_digest,
            {
                "role": "formalizer",
                "mechanism_id": mechanism_id,
                "obligation_ids": [],
            },
        ),
        "page_manifest_digest": manifest.content_digest,
        "page_digests": list(manifest.page_digests),
        "page_bytes_digests": list(manifest.page_bytes_digests),
        "formalizer_page_delivery_receipts": [formalizer_receipt],
    }
    section_receipt = build_shared_payload_delivery_receipt(
        manifest,
        consumer_role="writer",
        delivered_page_bytes=[page.serialized_bytes],
        actual_payload_bytes=payload_bytes,
    ).model_dump(mode="json")
    section_receipt["section_id"] = section_id
    realizer_receipt = dict(section_receipt)
    realizer_receipt["section_id"] = f"realizer:{mechanism_id}"

    common = {
        "contexts": SimpleNamespace(contexts=(context,)),
        "shared_payload_slices": {mechanism_id: slices},
        "formalizer_traces": [formalizer_trace],
        "writer_inputs": [writer_input],
        "page_manifests": {mechanism_id: manifest},
        "require_actual_receipts": True,
    }
    _assert_shared_payload_delivery(
        **common,
        writer_delivery_receipts=[section_receipt],
    )
    with pytest.raises(ValueError, match="writer_actual_page_receipt_missing"):
        _assert_shared_payload_delivery(
            **common,
            writer_delivery_receipts=[realizer_receipt],
        )


def test_realizer_detail_scope_canonicalizes_page_and_context_markers() -> None:
    """A V2 page must not lose all required details at the Realizer boundary."""

    page = SimpleNamespace(technical_payload={
        "atoms": [
            {"_atom_id": "detail:mech:1", "_atom_kind": "detail"},
            {"_atom_id": "detail:mech:2", "_atom_kind": "detail"},
        ],
    })
    context = SimpleNamespace(details=(
        SimpleNamespace(detail_id="detail:mech:1"),
        SimpleNamespace(detail_id="mech:2"),
    ))

    scoped, pool = _realizer_detail_scope(
        page=page,
        source_contexts=(context,),
        section_detail_ids=("mech:1", "detail:mech:2"),
    )

    assert scoped == {"detail:mech:1", "detail:mech:2"}
    assert set(pool) == scoped


def test_realizer_response_schema_freezes_the_nested_witness_contract() -> None:
    """Native JSON-schema mode must emit the current witness model, not legacy evidence blobs."""

    from code2paper.agentic.unified_context_compiler import (
        consumer_response_json_schema,
    )

    schema = consumer_response_json_schema("realizer")
    witness_schema = schema["properties"]["witnesses"]["items"]

    assert witness_schema["type"] == "object"
    assert witness_schema["required"] == [
        "witness_kind",
        "target_id",
        "exact_text",
    ]
    assert witness_schema["additionalProperties"] is False
    assert witness_schema["properties"]["witness_kind"]["enum"] == [
        "detail",
        "atom",
        "facet",
        "field",
        "slot",
        "edge",
        "formula",
        "claim",
        "equation",
    ]


def test_writer_response_schema_requires_nonempty_paragraph_transactions() -> None:
    """Unified Writer pages must not admit section-markdown-only responses."""

    from code2paper.agentic.unified_context_compiler import (
        consumer_response_json_schema,
    )

    schema = consumer_response_json_schema("writer")

    assert "section_id" in schema["required"]
    assert "paragraphs" in schema["required"]
    assert schema["properties"]["paragraphs"]["minItems"] == 1

    scoped = consumer_response_json_schema(
        "writer",
        section_id="MA-S1",
    )
    assert scoped["properties"]["section_id"]["const"] == "MA-S1"
    assert "const" not in schema["properties"]["section_id"]


def test_formalizer_response_schema_closes_all_required_fields() -> None:
    """Formalizer requests must expose one typed, closed six-field row."""

    from code2paper.agentic.unified_context_compiler import (
        consumer_response_json_schema,
    )

    schema = consumer_response_json_schema("formalizer")
    assert schema["type"] == "object"
    assert schema["required"] == ["results"]
    assert schema["additionalProperties"] is False

    row_ref = schema["properties"]["results"]["items"]["$ref"]
    row_name = row_ref.rsplit("/", 1)[-1]
    row_schema = schema["$defs"][row_name]
    assert set(row_schema["required"]) == {
        "obligation_id",
        "latex",
        "prose_explanation",
        "symbol_definitions",
        "material_conditions",
        "assumptions",
    }
    assert row_schema["additionalProperties"] is False
    symbol_schema = row_schema["properties"]["symbol_definitions"]
    assert symbol_schema["items"]["type"] == "array"
    assert symbol_schema["items"]["minItems"] == 2
    assert symbol_schema["items"]["maxItems"] == 2
    assert symbol_schema["items"]["items"]["type"] == "string"
    assert symbol_schema["items"]["items"]["minLength"] == 1
    assert row_schema["properties"]["material_conditions"]["items"]["minLength"] == 1
    assert row_schema["properties"]["assumptions"]["items"]["minLength"] == 1


def test_formalizer_without_formula_obligations_does_not_probe_pages() -> None:
    context = _make_context()
    view = build_mechanism_context_view(context)
    first = build_mechanism_context_slices(view)[0]
    second = MechanismContextSliceV1(
        mechanism_id=first.mechanism_id,
        slice_index=1,
        detail_ids=first.detail_ids,
        exact_evidence_ids=first.exact_evidence_ids,
        view_digest=first.view_digest,
        technical_payload=first.technical_payload,
        core_detail_ids=first.core_detail_ids,
        shared_payload_digest=first.shared_payload_digest,
    )
    slices = (first, second)
    manifest = build_shared_payload_manifest(slices)
    requests: list[LLMRequest] = []

    def caller(_config, request: LLMRequest):
        requests.append(request)
        return None

    _, traces = _run_mechanism_formalizer(
        SimpleNamespace(contexts=(context,)),
        {context.mechanism_id: slices},
        {context.mechanism_id: ()},
        llm_config=object(),
        caller=caller,
        page_manifests={context.mechanism_id: manifest},
    )

    assert requests == []
    assert traces[0]["formalizer_page_delivery_receipts"][0]["accepted"] is False
    assert traces[0]["formalizer_page_delivery_receipts"][0]["rejection_code"] == (
        "formalizer_request_not_observed"
    )
def test_run_publication_method_writer_shadow_unified_mode(tmp_path: Path) -> None:
    paths = _unified_artifacts(tmp_path)

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_mock_writer_caller,
        authoring_context_mode="shadow_unified",
    )

    assert result.status in ("success", "incomplete")
    assert result.status != "blocked"

    # Shadow mode produces both unified diagnostics and legacy outputs
    assert "mechanism_context_set_v1" in outputs
    assert "narrative_plan_v3" in outputs
    assert "method_content_trace_v2" in outputs
    assert "mechanism_information_funnel_v1" in outputs
    assert "publication_candidate_method" in outputs


def test_run_publication_method_writer_env_var_unified_cutover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODE2PAPER_AUTHORING_CONTEXT_MODE", "unified")
    paths = _unified_artifacts(tmp_path)

    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_mock_writer_caller,
    )

    assert result.status in ("success", "incomplete")
    assert "mechanism_context_set_v1" in outputs
    assert "narrative_plan_v3" in outputs
    assert "method_content_trace_v2" in outputs
    assert "mechanism_information_funnel_v1" in outputs


def test_validate_authoring_run_contract_satisfied(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_context_contract import (
        AuthoringRunContractV1,
        build_authoring_run_contract,
        validate_authoring_run_contract,
    )

    paths = _unified_artifacts(tmp_path)
    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_mock_writer_caller,
        authoring_context_mode="unified",
    )
    assert result.status in ("success", "incomplete")
    assert "authoring_run_contract_v1" in outputs
    contract_data = Path(outputs["authoring_run_contract_v1"]).read_text(encoding="utf-8")
    contract = AuthoringRunContractV1.model_validate_json(contract_data)
    assert contract.contract_satisfied is True
    assert len(contract.missing_artifact_keys) == 0
    is_valid, missing = validate_authoring_run_contract(contract)
    assert is_valid is True
    assert missing == ()


def test_run_publication_method_writer_expected_artifact_gate_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When an expected artifact is missing, unified authoring fails-closed."""
    from unittest.mock import patch
    from code2paper.agentic.authoring_context_contract import build_authoring_run_contract

    paths = _unified_artifacts(tmp_path)
    # Simulate an output file being deleted or missing from outputs before contract check
    orig_build = build_authoring_run_contract

    def mock_build_contract(*args: Any, **kwargs: Any) -> Any:
        output_paths = dict(kwargs.get("output_paths") or {})
        # Remove an expected unified artifact
        output_paths.pop("mechanism_formula_packages_v2", None)
        kwargs["output_paths"] = output_paths
        return orig_build(*args, **kwargs)

    with patch("code2paper.agentic.publication_method_writer.build_authoring_run_contract", side_effect=mock_build_contract):
        result, outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=_mock_writer_caller,
            authoring_context_mode="unified",
        )

    assert result.status == "blocked"
    assert "expected_authoring_artifacts_missing" in result.blocked_reason
    assert "mechanism_formula_packages_v2" in result.blocked_reason


def test_writer_request_plan_and_send_share_exact_wire_measurement(
    tmp_path: Path,
) -> None:
    """R6/F4: planning and sending use the same serialized request contract.

    The complete Writer wire request is now measured before the plan is
    admitted.  A zero *additional* scaffolding reserve is therefore valid: it
    must not create a plan/send mismatch or cause a second hidden rejection.
    """

    _unified_budget_env()
    deliveries: list[object] = []

    def _counting_caller(config, request):
        if str(getattr(request, "prompt_template_id", "")) == "unified_writer_page_v2":
            deliveries.append(request)
        return _mock_writer_caller(config, request)

    try:
        paths = _unified_artifacts(tmp_path)
        # All scaffolding is already present in the exact request material;
        # zero here means no extra reserve is added to that measurement.
        os.environ["CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_WRITER"] = "0"
        result, _outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=_counting_caller,
            authoring_context_mode="unified",
        )
    finally:
        _clear_unified_budget_env()

    assert result.status in ("blocked", "incomplete")
    assert len(deliveries) == 1
    receipts = sorted(
        (tmp_path / "artifacts" / "06_authoring" / "invocations").rglob(
            "*.completed.json"
        )
    )
    writer_receipts = [
        json.loads(path.read_text(encoding="utf-8")) for path in receipts
    ]
    writer_receipts = [
        row for row in writer_receipts if row.get("consumer_role") == "writer"
    ]
    assert writer_receipts
    accepted = [row for row in writer_receipts if row.get("delivery_status") == "accepted"]
    assert accepted, writer_receipts
    assert accepted[0]["sent_to_caller"] is True
    accounting = accepted[0]["token_accounting"]
    assert accounting["fits"] is True
    assert accounting["scaffolding_reserve_tokens"] == 0
    assert accounting["input_tokens"] > 0


def test_writer_request_over_declared_cap_fails_before_planning(
    tmp_path: Path,
) -> None:
    """R6/F4: a cap below the planned bound blocks the phase before any send."""

    _unified_budget_env()
    deliveries: list[object] = []

    def _counting_caller(config, request):
        if str(getattr(request, "prompt_template_id", "")) == "unified_writer_page_v2":
            deliveries.append(request)
        return _mock_writer_caller(config, request)

    try:
        paths = _unified_artifacts(tmp_path)
        os.environ["CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_WRITER"] = "2000"
        result, _outputs = run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=paths,
            llm_config=_config(),
            llm_caller=_counting_caller,
            authoring_context_mode="unified",
        )
    finally:
        _clear_unified_budget_env()

    assert result.status in ("blocked", "incomplete")
    assert result.status != "success"
    assert deliveries == []


def test_split_narrative_plan_revision_has_a_registered_output_name(
    tmp_path: Path,
) -> None:
    """A real page-budget split must not fail on an unregistered artifact key."""

    from code2paper.core.output_names import method_output

    path = method_output(tmp_path, "narrative_plan_v3.revision.2")
    assert path == (
        tmp_path
        / "artifacts"
        / "06_authoring"
        / "narrative_plan_v3.revision.2.json"
    )
