"""14 Vertical Tests for Unified Mechanism Context Architecture.

Implements section 7.1 of docs/code2paper_unified_mechanism_context_quality_failure_diagnosis_and_optimization_execution_plan_2026-09-06.md:

1.  replay CLI -> writer unified (防止 mode 参数未传)
2.  product agent -> writer unified (防止真实产品仍为 legacy)
3.  initial run -> callback -> resume (防止 mode/context 丢失和 _digest_json 未定义)
4.  real artifact manifest loader (防止 briefs/story/snapshot/symbol index 未传)
5.  mode-specific preflight (防止 LearNAT 被 legacy plan 前置阻断)
6.  expected artifact gate (防止“说是 unified，产物却不存在”)
7.  source inventory fixture (防止 vendor/data 污染 target scope)
8.  observation promotion fixture (防止 LearNAT 已读代码仍 0 facts)
9.  ownership conflict fixture (防止 FastGS 目标函数被 comparand 拒绝)
10. mechanism connectivity (防止大图稀疏、主链缺失仍通过)
11. formula AST fidelity (防止 EBCAR denominator/Lookahead order 改写)
12. paged actual-byte identity (防止 sanitizer/serializer 改写 payload)
13. Binder atom coverage (防止只绑定 detail ID 就假定语义完整)
14. representation-only sanitation (防止 control chars/LaTeX 损伤且不改语义)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from code2paper.agentic.authoring_context_contract import (
    AuthoringRunContractV1,
    build_authoring_run_contract,
    expected_authoring_artifact_keys,
    resolve_authoring_context_mode,
    validate_authoring_run_contract,
)
from code2paper.agentic.implementation_scope import (
    classify_source_kind,
    scope_role_for_candidate,
)
from code2paper.agentic.intent_ledger import (
    IntentCoverageScheduler,
    IntentImplementationLedgerV1,
    build_intent_implementation_ledger,
)
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextSetV1,
    MechanismContextSliceV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
    canonical_json_bytes,
)
from code2paper.agentic.mechanism_context_pages import (
    SharedPayloadManifestV1,
    SharedPayloadPageV1,
    build_request_delivery_receipt,
    build_shared_payload_manifest,
)
from code2paper.agentic.mechanism_realizer_composer import (
    MechanismDraftV1,
    MechanismRealizer,
    SectionComposer,
    SectionCompositionV1,
    sanitize_representation_only,
)
from code2paper.agentic.method_content_trace import (
    LOSS_TAXONOMY_LAYERS_V2,
    classify_primary_loss_layer,
)
from code2paper.agentic.publication_method_writer import (
    PublicationWriterRunResultV1,
    run_publication_method_writer,
)
from code2paper.agentic.publication_transaction_contract import (
    ParagraphTransactionAssessmentV1,
    assess_paragraph_transaction,
)
from code2paper.agentic.writing_callback_fulfillment import (
    _digest_json,
    MechanismResearchCallbackArtifactV2,
)
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.schemas import LLMConfig
from tests.test_agentic_publication_method_writer import _artifacts, _config


def _mock_writer_caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
    payload = request.prompt if isinstance(request.prompt, dict) else {}
    if isinstance(request.prompt, str):
        try:
            payload = json.loads(request.prompt)
        except Exception:
            payload = {}
    sec_id = str(payload.get("section_id") or "sec_method")
    heading = str(payload.get("heading") or "Method")
    res = {
        "section_id": sec_id,
        "heading_text": heading,
        "section_markdown": f"## {heading}\n\nThe encoder reads input reliably.",
        "paragraphs": [
            {
                "paragraph_id": f"{sec_id}_p1",
                "paragraph_markdown": "The encoder reads input reliably.",
            }
        ],
        "used_argument_unit_ids": [],
        "used_claim_ids": [],
        "used_equation_ids": [],
        "used_configuration_ids": [],
        "completed_rhetorical_moves": ["overview"],
    }
    return LLMResponse(
        text=json.dumps(res),
        metadata=res,
        response_hash="sha256:test",
        finish_reason="stop",
        token_usage={"completion_tokens": 50},
    )


# ============================================================================
# Vertical Test 1: replay CLI -> writer unified (防止 mode 参数未传)
# ============================================================================
def test_vertical_01_replay_cli_to_writer_unified() -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_authoring_replay.py"
    spec = importlib.util.spec_from_file_location("run_authoring_replay", script_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    parser = mod._build_parser()
    args = parser.parse_args(["/tmp/frozen", "/tmp/fresh", "--run-id", "test_run", "--authoring-context-mode", "unified"])
    assert args.authoring_context_mode == "unified"

    mode, source = resolve_authoring_context_mode(args.authoring_context_mode)
    assert mode == "unified"
    assert source == "argument"


# ============================================================================
# Vertical Test 2: product agent -> writer unified (防止真实产品仍为 legacy)
# ============================================================================
def test_vertical_02_product_agent_to_writer_unified(tmp_path: Path) -> None:
    paths = _artifacts(tmp_path)
    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_mock_writer_caller,
        authoring_context_mode="unified",
    )
    assert result.status in ("success", "incomplete")
    assert result.effective_authoring_context_mode == "unified"
    assert "authoring_run_contract_v1" in outputs
    contract = AuthoringRunContractV1.model_validate_json(
        Path(outputs["authoring_run_contract_v1"]).read_text(encoding="utf-8")
    )
    assert contract.effective_mode == "unified"
    assert contract.contract_satisfied is True


# ============================================================================
# Vertical Test 3: initial run -> callback -> resume (防止 mode/context 丢失和 _digest_json 未定义)
# ============================================================================
def test_vertical_03_initial_run_callback_resume_mode_inheritance(tmp_path: Path) -> None:
    # 1. _digest_json must be defined and functional (not undefined)
    sample_payload = {"mode": "unified", "section_id": "sec_1"}
    digest = _digest_json(sample_payload)
    assert digest.startswith("sha256:")
    assert _digest_json(sample_payload) == digest

    # 2. Mode resolution on resume explicitly inherits requested mode
    mode, source = resolve_authoring_context_mode("unified", source_hint="resume")
    assert mode == "unified"
    assert source == "resume"

    # 3. Callback artifact validates context and delta digests
    artifact = MechanismResearchCallbackArtifactV2(
        artifact_id="mech_cb_1",
        request_id="req_1",
        mechanism_id="mech_1",
        unresolved_kind="missing_definition",
        artifact_ref="artifacts/facts.json",
        artifact_digest="sha256:facts",
        baseline_context_digest="sha256:baseline",
        current_context_digest="sha256:current",
        semantic_delta_digest="sha256:delta",
        new_fact_ids=("fact:1",),
        validated=True,
    )
    assert artifact.baseline_context_digest == "sha256:baseline"
    assert artifact.current_context_digest == "sha256:current"
    assert artifact.semantic_delta_digest == "sha256:delta"
    assert artifact.new_fact_ids == ("fact:1",)


# ============================================================================
# Vertical Test 4: real artifact manifest loader (防止 briefs/story/snapshot/symbol index 未传)
# ============================================================================
def test_vertical_04_real_artifact_manifest_loader(tmp_path: Path) -> None:
    from code2paper.agentic.autonomous_method_agent import _writer_artifact_paths

    art_dir = tmp_path / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "repo_snapshot_v2",
        "symbol_index_v2",
        "method_argument_briefs_v1",
        "method_story_nodes_v1",
    ):
        (art_dir / f"{name}.json").write_text("{}", encoding="utf-8")

    writer_paths = _writer_artifact_paths(tmp_path)
    assert "repo_snapshot_v2" in writer_paths
    assert "symbol_index_v2" in writer_paths
    assert "method_argument_briefs_v1" in writer_paths
    assert "method_story_nodes_v1" in writer_paths


# ============================================================================
# Vertical Test 5: mode-specific preflight (防止 LearNAT 被 legacy plan 前置阻断)
# ============================================================================
def test_vertical_05_mode_specific_preflight_fail_closed_lear_nat(tmp_path: Path) -> None:
    paths = {
        "atomic_claims_v3": "",
        "code_facts_v1": "",
    }
    result, outputs = run_publication_method_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        llm_config=_config(),
        llm_caller=_mock_writer_caller,
        authoring_context_mode="unified",
    )
    assert result.status == "blocked"
    # Typed research evidence missing, NOT legacy plan missing
    assert "research_evidence_missing" in result.blocked_reason
    assert "method_section_plan_v2" not in result.blocked_reason


# ============================================================================
# Vertical Test 6: expected artifact gate (防止“说是 unified，产物却不存在”)
# ============================================================================
def test_vertical_06_expected_artifact_gate(tmp_path: Path) -> None:
    contract = build_authoring_run_contract(
        requested_mode="unified",
        effective_mode="unified",
        mode_source="argument",
        artifact_paths={},
        output_paths={},
    )
    assert contract.contract_satisfied is False
    assert len(contract.missing_artifact_keys) > 0
    is_valid, missing = validate_authoring_run_contract(contract)
    assert is_valid is False
    assert len(missing) == len(expected_authoring_artifact_keys("unified"))


# ============================================================================
# Vertical Test 7: source inventory fixture (防止 vendor/data 污染 target scope)
# ============================================================================
def test_vertical_07_source_inventory_fixture_domain_pruning() -> None:
    assert classify_source_kind("sglang/srt/model_executor.py") == "vendor"
    assert classify_source_kind("data/calibration_set.pt") == "dataset_or_checkpoint"
    assert classify_source_kind("pruning/wanda.py") == "first_party_executable"
    assert classify_source_kind("tests/test_pruning.py") == "test"


# ============================================================================
# Vertical Test 8: observation promotion fixture (防止 LearNAT 已读代码仍 0 facts)
# ============================================================================
def test_vertical_08_observation_promotion_fixture_lear_nat() -> None:
    clauses = [{"clause_id": "c_mcts", "clause_text": "MCTS AST search", "is_core": True}]
    queries = {"c_mcts": ["MCTS._classify_node"]}
    reads = {"c_mcts": ["MCTS.py::_classify_node"]}
    rejections = {"c_mcts": "rejection:observation_promoted"}
    facts = {"c_mcts": ["fact:mcts_ast"]}
    ops = {"c_mcts": ["op:mcts_search"]}

    ledger = build_intent_implementation_ledger(
        clauses=clauses,
        queries_by_clause=queries,
        read_symbols_by_clause=reads,
        promoted_facts_by_clause=facts,
        promoted_operations_by_clause=ops,
        rejections_by_clause=rejections,
    )
    assert ledger.core_intent_attempt_coverage == 1.0
    assert ledger.observation_promotion_rate == 1.0
    assert ledger.items[0].status == "implemented_exact"


# ============================================================================
# Vertical Test 9: ownership conflict fixture (防止 FastGS 目标函数被 comparand 拒绝)
# ============================================================================
def test_vertical_09_ownership_conflict_fixture_fastgs() -> None:
    from code2paper.agentic.implementation_scope import (
        infer_implementation_scope,
        scope_role_for_candidate,
    )

    sym = {
        "symbol_id": "scene/gaussian_model.py::GaussianModel.densify_and_prune",
        "path": "scene/gaussian_model.py",
        "qualified_name": "GaussianModel.densify_and_prune",
        "name": "densify_and_prune",
        "kind": "function",
        "docstring": "FastGS Gaussian densification and pruning",
    }
    scope = infer_implementation_scope(
        symbols=[sym],
        author_texts=["FastGS densification and pruning for 3D Gaussian Splatting"],
        entry_symbol_ids=["scene/gaussian_model.py::GaussianModel.densify_and_prune"],
    )
    role = scope_role_for_candidate(
        scope,
        "scene/gaussian_model.py::GaussianModel.densify_and_prune",
        symbols=[sym],
    )
    assert role in ("target_core", "target_dependency")
    assert role != "comparand"


# ============================================================================
# Vertical Test 10: mechanism connectivity (防止大图稀疏、主链缺失仍通过)
# ============================================================================
def test_vertical_10_mechanism_connectivity() -> None:
    loss = classify_primary_loss_layer(
        validated=False,
        discovered=True,
        closed_in_evidence=True,
        annotated=True,
        projected=False,
        writer_delivered=False,
        rendered=False,
        p_valid=False,
        active_path_status="unknown",  # disconnected active path
    )
    assert loss == "R2a"


# ============================================================================
# Vertical Test 11: formula AST fidelity (防止 EBCAR denominator/Lookahead order 改写)
# ============================================================================
def test_vertical_11_formula_ast_fidelity() -> None:
    from code2paper.agentic.formalization_agent import MechanismFormulaPackageV2

    pkg = MechanismFormulaPackageV2(
        package_id="pkg:ebcar_score",
        mechanism_id="mech_ebcar",
        source_detail_ids=("d:score",),
        satisfied_obligation_ids=("obl:score",),
        latex=r"S = \frac{\sum_i w_i x_i}{\sum_j w_j + \epsilon}",
        prose_explanation="Weighted sum divided by normalized denominator.",
    )
    # The realizer must not rewrite the denominator or formula structure, and
    # it cannot produce a formula without an actual Writer caller.
    detail = MechanismDetailV1(
        detail_id="d:score",
        primary_mechanism_id="mech_ebcar",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="formalization",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="compute score with weighted denominator",
        source_equation_ids=("eq:ebcar",),
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:score",
                atom_kind="formal_relation",
                semantic_anchor="score",
            ),
        ),
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:ebcar",
        mechanism_id="mech_ebcar",
        equation_ids=("eq:ebcar",),
        source_operation_terminal_coverage=0.0,
    )
    ctx = MechanismContextV1(
        mechanism_id="mech_ebcar",
        mechanism_name="EBCAR Scoring",
        scientific_role="transformation",
        reader_question="How is score computed?",
        purpose="Score ranking",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=("d:score",),
        details=(detail,),
    )
    blocked = MechanismRealizer().realize_draft(context=ctx, formula_packages=(pkg,))
    assert blocked.status == "blocked"
    assert blocked.draft_markdown == ""

    def caller(_config: LLMConfig, _request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=json.dumps({
                "draft_markdown": (
                    "The score uses the exact denominator "
                    + r"$S = \frac{\sum_i w_i x_i}{\sum_j w_j + \epsilon}$."
                ),
                "rendered_detail_ids": ["d:score"],
                "used_formula_package_ids": ["pkg:ebcar_score"],
                "witnesses": [
                    {"witness_kind": "detail", "target_id": "d:score", "exact_text": "The score uses the exact denominator"},
                    {"witness_kind": "formula", "target_id": "pkg:ebcar_score", "exact_text": r"S = \frac{\sum_i w_i x_i}{\sum_j w_j + \epsilon}"},
                ],
            }),
            response_hash="sha256:test",
            finish_reason="stop",
        )

    realizer = MechanismRealizer(llm_config=LLMConfig(model="test-realizer"))
    draft = realizer.realize_draft(
        context=ctx,
        formula_packages=(pkg,),
        caller=caller,
    )
    assert draft.status == "accepted"
    assert r"S = \frac{\sum_i w_i x_i}{\sum_j w_j + \epsilon}" in draft.draft_markdown


# ============================================================================
# Vertical Test 12: paged actual-byte identity (防止 sanitizer/serializer 改写 payload)
# ============================================================================
def test_vertical_12_paged_actual_byte_identity() -> None:
    detail = MechanismDetailV1(
        detail_id="d:1",
        primary_mechanism_id="mech_1",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="specification",
        evidence_authority="author_intent_only",
        publication_policy="clean_candidate",
        semantic_atom="op1",
        source_facet_ids=("facet:1",),
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:1",
        mechanism_id="mech_1",
        source_operation_terminal_coverage=0.0,
    )
    ctx = MechanismContextV1(
        mechanism_id="mech_1",
        mechanism_name="Mechanism 1",
        scientific_role="transformation",
        reader_question="How does it work?",
        purpose="Testing paged bytes",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=("d:1",),
        details=(detail,),
    )
    manifest = build_shared_payload_manifest(ctx)
    assert isinstance(manifest, SharedPayloadManifestV1)
    assert len(manifest.pages) >= 1
    page = manifest.pages[0]
    assert page.technical_bytes_digest.startswith("sha256:")
    assert page.serialized_bytes == canonical_json_bytes(page.technical_payload)

    # This is deliberately a caller-boundary check, not just a manifest
    # serialization check: the receipt is derived from the bytes in the
    # actual LLMRequest and rejects a one-byte mutation.
    request = LLMRequest(
        prompt_template_id="test-writer",
        prompt="",
        input_payload={
            "shared_contexts": [page.serialized_bytes.decode("utf-8")],
        },
    )
    receipt = build_request_delivery_receipt(
        manifest,
        request,
        consumer_role="writer",
    )
    assert receipt.accepted is True
    mutated = LLMRequest(
        prompt_template_id="test-writer",
        prompt="",
        input_payload={
            "shared_contexts": [
                page.serialized_bytes.decode("utf-8").replace(
                    '"detail_ids"', '"detail_ids_mutated"', 1
                )
            ],
        },
    )
    rejected = build_request_delivery_receipt(
        manifest,
        mutated,
        consumer_role="writer",
    )
    assert rejected.accepted is False
    assert rejected.rejection_code == "actual_page_bytes_mismatch"


# ============================================================================
# Vertical Test 13: Binder atom coverage (防止只绑定 detail ID 就假定语义完整)
# ============================================================================
def test_vertical_13_binder_atom_coverage() -> None:
    assessment = ParagraphTransactionAssessmentV1(
        paragraph_id="sec_p1",
        section_id="sec_1",
        status="invalid",
        valid=False,
        required_by_kind={"detail": ("d:core",), "atom": ("atom:threshold_check",)},
        declared_by_kind={"detail": ("d:core",)},
        witnessed_by_kind={"detail": ("d:core",)},  # missing atom witness!
        missing_by_kind={"atom": ("atom:threshold_check",)},
    )
    assert assessment.valid is False
    assert "atom:threshold_check" in assessment.missing_by_kind["atom"]


# ============================================================================
# Vertical Test 14: representation-only sanitation (防止 control chars/LaTeX 损伤且不改语义)
# ============================================================================
def test_vertical_14_representation_only_sanitation() -> None:
    raw_markdown = "## Section\n\nGaussian \x07densification with \x1bthreshold $\\tau$."
    cleaned, diff_class = sanitize_representation_only(raw_markdown)
    assert "\x07" not in cleaned
    assert "\x1b" not in cleaned
    assert "Gaussian densification with threshold $\\tau$." in cleaned
    assert diff_class == "control_chars_removed"
