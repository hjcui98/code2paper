"""审计 §C.04：一个公式依赖多个 detail 时，分页必须保持完整依赖闭包或明确阻断。

要求（文档 §C.4 验收 / §13 矩阵 C04）：

* required occurrence 集合守恒；
* 公式的 consumer/source 闭包在分页后仍完整（多 detail 公式不得被拆到两页）；
* 单个不可分单元仍超预算时返回说明真实限制维度的 typed failure，不截尾。

本文件用真实编译器（`build_unified_context_archive_v2` →
`build_consumer_workset_manifest_v2`）驱动，不构造平行分页逻辑。
"""

from __future__ import annotations

import pytest

from code2paper.agentic.formalization_agent import (
    MechanismFormulaObligationV1,
)
from code2paper.agentic.unified_context_compiler import (
    UnifiedCompilerError,
    build_consumer_workset_manifest_v2,
    build_unified_context_archive_v2,
)
from code2paper.agentic.unified_context_models import (
    UNIFIED_ATOMIC_PAGE_OVER_BUDGET,
)
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextSetV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
)


def _multi_detail_formula_fixture():
    """一个机制、两个 detail、一个依赖**两个** detail 的公式义务。"""

    mechanism_id = "mech_multi"
    details: list[MechanismDetailV1] = []
    operations: list[EvidenceOperationV1] = []
    for index, detail_id in enumerate(("d:one", "d:two"), start=1):
        operation = EvidenceOperationV1(
            operation_id=f"op:{detail_id}",
            predicate="compute_step",
            operands=(f"input_{index}",),
            result=f"output_{index}",
            source_span_id="",
            active_path_status="active_default",
        )
        operations.append(operation)
        details.append(
            MechanismDetailV1(
                detail_id=detail_id,
                primary_mechanism_id=mechanism_id,
                order_index=index - 1,
                role="transformation",
                importance="core",
                claim_kind="implementation",
                evidence_authority="repository_verified",
                publication_policy="clean_candidate",
                semantic_atom=f"step {index} of {mechanism_id}",
                predicate="compute_step",
                operands=(f"input_{index}",),
                result=f"output_{index}",
                active_path_status="active_default",
                source_operation_ids=(operation.operation_id,),
                witness_atoms=(
                    DetailWitnessAtomV1(
                        atom_id=f"atom:{detail_id}",
                        atom_kind="operation",
                        semantic_anchor=f"step {index} of {mechanism_id}",
                        source_operation_ids=(operation.operation_id,),
                    ),
                ),
            )
        )
    closure = MechanismEvidenceClosureV1(
        closure_id=f"closure:{mechanism_id}",
        mechanism_id=mechanism_id,
        operation_nodes=tuple(operations),
        operation_dispositions=tuple(
            SourceOperationDispositionV1(
                operation_id=operation.operation_id,
                disposition="absorbed_by_detail",
                detail_ids=(detail.detail_id,),
            )
            for operation, detail in zip(operations, details)
        ),
        source_operation_terminal_coverage=1.0,
    )
    context = MechanismContextV1(
        mechanism_id=mechanism_id,
        mechanism_name="Multi detail mechanism",
        scientific_role="core_model",
        reader_question="How do the two steps compose?",
        purpose="Explain the mechanism.",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=tuple(detail.detail_id for detail in details),
        details=tuple(details),
    )
    context_set = MechanismContextSetV1(
        repo_snapshot_id="repo:multi",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:alignment",
        research_digest="sha256:research",
        contexts=(context,),
    )
    archive = build_unified_context_archive_v2(
        context_set, source_manifest_digest="sha256:manifest"
    )
    obligations = {
        mechanism_id: (
            MechanismFormulaObligationV1(
                obligation_id="ob:multi",
                mechanism_id=mechanism_id,
                source_detail_ids=("d:one", "d:two"),
                primary_detail_id="d:one",
                mathematical_goal="Formalize the two-step composition.",
            ),
        )
    }
    return archive, obligations


def _detail_atom(detail_id: str) -> str:
    from code2paper.agentic.unified_context_compiler import _detail_atom_id

    return _detail_atom_id(detail_id)


def test_multi_detail_formula_keeps_its_closure_on_one_page() -> None:
    """多 detail 公式必须原子地落在一页，并携带其全部 source detail。"""

    archive, obligations = _multi_detail_formula_fixture()
    manifest = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=200_000,
        max_obligations_per_page=4,
    )

    pages_with_obligation = [
        page
        for page in manifest.pages
        if "ob:multi"
        in set((page.technical_payload or {}).get("obligation_ids") or ())
    ]
    assert len(pages_with_obligation) == 1, (
        "多 detail 公式不得被拆到多页："
        f"{[page.page_id for page in pages_with_obligation]}"
    )
    page = pages_with_obligation[0]
    page_atoms = set(page.atom_ids)
    for detail_id in ("d:one", "d:two"):
        assert _detail_atom(detail_id) in page_atoms, (
            f"{detail_id} 的依赖必须在公式所在页：{sorted(page_atoms)}"
        )

    # 义务守恒：分页后所有义务仍然各出现一次。
    routed = [
        obligation_id
        for item in manifest.pages
        for obligation_id in (item.technical_payload or {}).get("obligation_ids") or ()
    ]
    assert sorted(routed) == ["ob:multi"], routed


def test_multi_detail_formula_closure_survives_a_tight_page_budget() -> None:
    """预算紧到必须单独成页时，闭包仍完整（不是被拆开，而是独占一页）。"""

    archive, obligations = _multi_detail_formula_fixture()
    loose = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=200_000,
        max_obligations_per_page=4,
    )
    technical_pages = [
        page
        for page in loose.pages
        if (page.technical_payload or {}).get("obligation_ids")
    ]
    assert len(technical_pages) == 1
    tight_budget = technical_pages[0].token_estimate
    tight = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=tight_budget,
        max_obligations_per_page=1,
    )
    tight_technical = [
        page
        for page in tight.pages
        if (page.technical_payload or {}).get("obligation_ids")
    ]
    assert len(tight_technical) == 1
    page = tight_technical[0]
    assert set((page.technical_payload or {}).get("obligation_ids") or ()) == {
        "ob:multi"
    }
    page_atoms = set(page.atom_ids)
    for detail_id in ("d:one", "d:two"):
        assert _detail_atom(detail_id) in page_atoms, sorted(page_atoms)

    # 闭包守恒：archive 里的 detail atom 一个不少（用 detail 前缀的 atom id 核对）。
    archived = {atom.atom_id for atom in archive.all_atoms()}
    assert {_detail_atom("d:one"), _detail_atom("d:two")}.issubset(archived), archived


def test_indivisible_over_budget_formula_is_blocked_not_truncated() -> None:
    """不可分依赖超预算 → typed failure 指出真实限制维度，且不截尾。"""

    archive, obligations = _multi_detail_formula_fixture()
    baseline = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=200_000,
        max_obligations_per_page=4,
    )
    technical_pages = [
        page
        for page in baseline.pages
        if (page.technical_payload or {}).get("obligation_ids")
    ]
    assert len(technical_pages) == 1
    needed = technical_pages[0].token_estimate

    with pytest.raises(UnifiedCompilerError) as excinfo:
        build_consumer_workset_manifest_v2(
            archive,
            obligations,
            max_page_input_tokens=max(1, needed - 1),
            max_obligations_per_page=4,
        )
    error = excinfo.value
    assert error.failure_code == UNIFIED_ATOMIC_PAGE_OVER_BUDGET, error.failure_code
    assert "ob:multi" in error.message, error.message
    # 报出真实维度：预算值与贡献 atom，而不是"段数超限"的假不等式。
    assert f">{max(1, needed - 1)}" in error.message, error.message
    assert "contribution:" in error.message, error.message

    # 不截尾：失败后 archive 的 detail atom 与义务集合原样保留。
    archived = {atom.atom_id for atom in archive.all_atoms()}
    assert {_detail_atom("d:one"), _detail_atom("d:two")}.issubset(archived), archived
    assert [
        item.obligation_id
        for values in obligations.values()
        for item in values
    ] == ["ob:multi"]
