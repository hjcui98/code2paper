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


def _unified_budget_env() -> None:
    """Explicit small V2 live-budget values for deterministic tests."""

    os.environ.update({
        "CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS": "20000",
        "CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS": "400000",
        "CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS": "32",
        "CODE2PAPER_UNIFIED_MAX_WRITER_CALLS": "64",
        "CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS": "64",
        "CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE": "8",
        "CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS": "4",
        "CODE2PAPER_MODEL_CONTEXT_TOKENS": "131072",
    })


def _clear_unified_budget_env() -> None:
    for key in (
        "CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS",
        "CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS",
        "CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS",
        "CODE2PAPER_UNIFIED_MAX_WRITER_CALLS",
        "CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS",
        "CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE",
        "CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS",
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
    snapshot = RepoSnapshot(
        snapshot_id="repo:writer",
        project_root=str(tmp_path),
        project_tree_hash="sha256:tree",
        included_files=[SnapshotFile(
            path="encoder.py",
            size=source_path.stat().st_size,
            content_digest="sha256:source",
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
        content_digest="sha256:source",
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
    p_plan = (
        request.input_payload.get("paragraph_plan")
        or payload.get("paragraph_plan")
        or ()
    )

    paragraphs_out = []
    if p_plan and isinstance(p_plan, (list, tuple)):
        for item in p_plan:
            pid = (
                item.get("paragraph_id")
                if isinstance(item, dict)
                else getattr(item, "paragraph_id", "")
            )
            if pid:
                paragraphs_out.append({
                    "paragraph_id": str(pid),
                    "paragraph_markdown": "The encoder reads the configured input reliably.",
                })
    if not paragraphs_out:
        paragraphs_out.append({
            "paragraph_id": f"{section_id}_p1",
            "paragraph_markdown": "The encoder reads the configured input reliably.",
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
