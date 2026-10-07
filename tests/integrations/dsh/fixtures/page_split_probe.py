"""K04-G4 探针：段落按页预算分裂时的**义务多重集守恒**（部分 witness 覆盖的最小计划）。

只调用生产入口 ``fit_narrative_plan_to_page_budget``：构造一个合法的、witness 只覆盖部分
义务的最小计划，让它在页预算下真的分裂成多个分片，然后比较**输入行**与**所有分片**的
完整义务/公式包/明细多重集。

K04 起不守恒必须具名阻断（``paragraph_split_obligation_contract_not_conserved``）；
旧实现只比较 target 多重集，于是"ob1 有 formula target、ob3 没有"这一形态会静默丢掉 ob3。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from code2paper.agentic.formalization_agent import MechanismFormulaObligationV1
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextSetV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
)
from code2paper.agentic.method_architect import (
    NarrativeParagraphPlanV3,
    NarrativePlanV3,
    NarrativeSectionPlanV3,
    NarrativeUnitV1,
)
from code2paper.agentic.unified_context_compiler import (
    build_unified_context_archive_v2,
    fit_narrative_plan_to_page_budget,
)

SECTION_ID = "MA-G4"
MECHANISM_ID = "mech_g4"
PARAGRAPH_ID = f"{SECTION_ID}_p1"
DETAIL_IDS: tuple[str, ...] = ("d:g4:1", "d:g4:2", "d:g4:3")
OBLIGATION_IDS: tuple[str, ...] = ("ob:g4:1", "ob:g4:3")
#: 让"一个明细放得下、三个放不下"的页预算（实测：单明细闭包 1055 tokens，三明细超 1300）。
SPLIT_PAGE_BUDGET_TOKENS = 1300


def _archive():
    operations = []
    details = []
    for index, detail_id in enumerate(DETAIL_IDS):
        operation = EvidenceOperationV1(
            operation_id=f"op:{detail_id}",
            predicate="compute_step",
            operands=(f"input_{index}",),
            result=f"output_{index}",
            source_span_id="",
            active_path_status="active_default",
        )
        operations.append(operation)
        details.append(MechanismDetailV1(
            detail_id=detail_id,
            primary_mechanism_id=MECHANISM_ID,
            order_index=index,
            role="transformation",
            importance="core",
            claim_kind="implementation",
            evidence_authority="repository_verified",
            publication_policy="clean_candidate",
            semantic_atom=f"step {index} of the mechanism",
            predicate="compute_step",
            operands=(f"input_{index}",),
            result=f"output_{index}",
            active_path_status="active_default",
            source_operation_ids=(operation.operation_id,),
            witness_atoms=(DetailWitnessAtomV1(
                atom_id=f"atom:{detail_id}",
                atom_kind="operation",
                semantic_anchor=f"step {index}",
                source_operation_ids=(operation.operation_id,),
            ),),
        ))
    closure = MechanismEvidenceClosureV1(
        closure_id=f"closure:{MECHANISM_ID}",
        mechanism_id=MECHANISM_ID,
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
    context_set = MechanismContextSetV1(
        repo_snapshot_id="repo:g4-probe",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:alignment",
        research_digest="sha256:research",
        contexts=(MechanismContextV1(
            mechanism_id=MECHANISM_ID,
            mechanism_name="G4 mechanism",
            scientific_role="core_model",
            reader_question="How does it work?",
            purpose="Explain the mechanism.",
            importance="core",
            evidence_closure=closure,
            ordered_detail_ids=DETAIL_IDS,
            details=tuple(details),
        ),),
    )
    return build_unified_context_archive_v2(
        context_set, source_manifest_digest="sha256:manifest"
    )


def _obligations() -> tuple[MechanismFormulaObligationV1, ...]:
    return (
        MechanismFormulaObligationV1(
            obligation_id=OBLIGATION_IDS[0],
            mechanism_id=MECHANISM_ID,
            source_detail_ids=(DETAIL_IDS[0],),
            mathematical_goal="Formalize detail 1.",
        ),
        MechanismFormulaObligationV1(
            obligation_id=OBLIGATION_IDS[1],
            mechanism_id=MECHANISM_ID,
            source_detail_ids=(DETAIL_IDS[2],),
            mathematical_goal="Formalize detail 3.",
        ),
    )


def _plan(
    obligations: Sequence[Any],
    targets: Sequence[Mapping[str, Any]],
    *,
    package_ids: Sequence[str] = (),
    order: str = "",
) -> NarrativePlanV3:
    """K04-G4 分裂计划的输入。

    ``package_ids`` / ``order`` 是 K04-GAP-2 的加法扩展：只有显式传入时才改变计划，
    G4 的默认输入逐字不变。``order`` 取 ``"obligation"`` / ``"package"`` 时**只反转
    该家族的 ID 顺序**，ID 集、材料与依赖都不变。
    """

    obligation_ids = tuple(str(item.obligation_id) for item in obligations)
    package_id_list = tuple(str(item) for item in package_ids)
    if order == "obligation":
        obligation_ids = tuple(reversed(obligation_ids))
    elif order == "package":
        package_id_list = tuple(reversed(package_id_list))
    elif order:
        raise ValueError(f"unknown formula order family: {order}")
    paragraph = NarrativeParagraphPlanV3(
        paragraph_id=PARAGRAPH_ID,
        section_id=SECTION_ID,
        role="core_transformations",
        mechanism_id=MECHANISM_ID,
        required_detail_ids=DETAIL_IDS,
        formula_obligation_ids=obligation_ids,
        formula_package_ids=package_id_list,
        witness_contract={
            "schema_version": "1.0",
            "paragraph_id": PARAGRAPH_ID,
            "rhetorical_goal": "core_transformations",
            "targets": [dict(target) for target in targets],
        },
    )
    return NarrativePlanV3(
        plan_id="plan:g4-probe",
        sections=(NarrativeSectionPlanV3(
            section_id=SECTION_ID,
            heading="G4",
            mechanism_ids=(MECHANISM_ID,),
            paragraphs=(paragraph,),
        ),),
        narrative_units=(NarrativeUnitV1(
            unit_id="unit_g4",
            section_id=SECTION_ID,
            mechanism_context_ids=(MECHANISM_ID,),
            rhetorical_role="core_model",
            reader_question="How does it work?",
            paragraph_ids=(PARAGRAPH_ID,),
            required_detail_ids=DETAIL_IDS,
            optional_detail_ids=(),
            formula_obligation_ids=tuple(
                str(item.obligation_id) for item in obligations
            ),
            suggested_depth="standard",
        ),),
        context_set_digest="sha256:context-set",
    )


@dataclass(frozen=True)
class SplitOutcome:
    """一次真实分裂的输入/输出多重集与具名失败。"""

    fragment_ids: tuple[str, ...]
    input_obligations: dict[str, int]
    fragment_obligations: dict[str, int]
    input_details: dict[str, int]
    fragment_details: dict[str, int]
    failures: tuple[str, ...]


def split_paragraph(
    *,
    targets: Sequence[Mapping[str, Any]] = (),
    max_page_input_tokens: int = SPLIT_PAGE_BUDGET_TOKENS,
) -> SplitOutcome:
    """用给定 witness targets 真跑一次页预算分裂，返回守恒比较所需的事实。"""

    archive = _archive()
    obligations = _obligations()
    plan = _plan(obligations, targets)
    revised, failures, _diagnostics = fit_narrative_plan_to_page_budget(
        plan,
        archive=archive,
        max_page_input_tokens=max_page_input_tokens,
        formula_obligations=obligations,
    )
    rows = [row for section in revised.sections for row in section.paragraphs]
    return SplitOutcome(
        fragment_ids=tuple(str(row.paragraph_id) for row in rows),
        input_obligations=dict(Counter(obligations_ids(plan))),
        fragment_obligations=dict(Counter(
            str(obligation_id)
            for row in rows
            for obligation_id in row.formula_obligation_ids
        )),
        input_details=dict(Counter(
            str(detail_id)
            for row in plan.sections[0].paragraphs
            for detail_id in (
                *row.required_detail_ids,
                *row.optional_detail_ids,
            )
        )),
        fragment_details=dict(Counter(
            str(detail_id)
            for row in rows
            for detail_id in (
                *row.required_detail_ids,
                *row.optional_detail_ids,
            )
        )),
        failures=tuple(str(item) for item in failures),
    )


def obligations_ids(plan: NarrativePlanV3) -> tuple[str, ...]:
    """输入计划声明的义务（逐行展开，保持多重集语义）。"""

    return tuple(
        str(obligation_id)
        for section in plan.sections
        for row in section.paragraphs
        for obligation_id in row.formula_obligation_ids
    )
