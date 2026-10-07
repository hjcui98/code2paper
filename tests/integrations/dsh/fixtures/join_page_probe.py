"""B01-D1 探针：多段落 join 页在不同 PYTHONHASHSEED 下的真实页身份。

以子进程运行（``PYTHONHASHSEED`` 只在解释器启动时生效）：

    python -m tests.integrations.dsh.fixtures.join_page_probe [lexicographic]

输出三行：``mode``、``paragraph_ids``（Narrative 顺序）与 ``page_id`` + 技术字节摘要。
它只调用生产入口，不重写分页、不固定 seed、不按字典序重排。

K04 起默认使用**非字典序**段落 ID（叙述顺序 ``p2`` 在 ``p10`` 之前），因此"顺序正确"
与"恰好等于字典序"不再可能混淆。
"""

from __future__ import annotations

from code2paper.agentic.unified_context_compiler import (
    build_consumer_workset_manifest_v2,
    build_run_invocation_budget_envelope_v1,
    build_unified_context_archive_v2,
    extend_writer_worksets_from_narrative_plan,
)
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

SECTION_ID = "MA-P1"


def _archive():
    contexts = []
    obligations = {}
    for index, mechanism_id in enumerate(("mech_first", "mech_second")):
        operation = EvidenceOperationV1(
            operation_id=f"op:{mechanism_id}",
            predicate="compute_step",
            operands=(f"input_{mechanism_id}",),
            result=f"output_{mechanism_id}",
            source_span_id="",
            active_path_status="active_default",
        )
        detail = MechanismDetailV1(
            detail_id=f"d:{mechanism_id}",
            primary_mechanism_id=mechanism_id,
            order_index=index,
            role="transformation",
            importance="core",
            claim_kind="implementation",
            evidence_authority="repository_verified",
            publication_policy="clean_candidate",
            semantic_atom=f"step for {mechanism_id}",
            predicate="compute_step",
            operands=(f"input_{mechanism_id}",),
            result=f"output_{mechanism_id}",
            active_path_status="active_default",
            source_operation_ids=(operation.operation_id,),
            witness_atoms=(DetailWitnessAtomV1(
                atom_id=f"atom:{mechanism_id}",
                atom_kind="operation",
                semantic_anchor=f"step for {mechanism_id}",
                source_operation_ids=(operation.operation_id,),
            ),),
        )
        closure = MechanismEvidenceClosureV1(
            closure_id=f"closure:{mechanism_id}",
            mechanism_id=mechanism_id,
            operation_nodes=(operation,),
            operation_dispositions=(SourceOperationDispositionV1(
                operation_id=operation.operation_id,
                disposition="absorbed_by_detail",
                detail_ids=(detail.detail_id,),
            ),),
            source_operation_terminal_coverage=1.0,
        )
        contexts.append(MechanismContextV1(
            mechanism_id=mechanism_id,
            mechanism_name=f"Mechanism {mechanism_id}",
            scientific_role="core_model",
            reader_question=f"How does {mechanism_id} work?",
            purpose="Explain the mechanism.",
            importance="core",
            evidence_closure=closure,
            ordered_detail_ids=(detail.detail_id,),
            details=(detail,),
        ))
        obligations[mechanism_id] = (MechanismFormulaObligationV1(
            obligation_id=f"ob:{mechanism_id}",
            mechanism_id=mechanism_id,
            source_detail_ids=(detail.detail_id,),
            mathematical_goal=f"Formalize {mechanism_id}.",
        ),)
    context_set = MechanismContextSetV1(
        repo_snapshot_id="repo:hash-seed-probe",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:alignment",
        research_digest="sha256:research",
        contexts=tuple(contexts),
    )
    return build_unified_context_archive_v2(
        context_set, source_manifest_digest="sha256:manifest"
    ), obligations


#: 叙述顺序的段落后缀。默认刻意**非字典序**：Narrative 顺序是 p2 然后 p10，而字典序会
#: 得到 p10 在前。K04 的稳定性回归据此区分"保序"与"恰好排对了"。
_NARRATIVE_SUFFIXES: tuple[str, ...] = ("p2", "p10")
#: B01 原探针使用的字典序后缀（保留作历史对照）。
_LEXICOGRAPHIC_SUFFIXES: tuple[str, ...] = ("p1", "p2")


def _plan(
    archive,
    suffixes: tuple[str, ...] = _NARRATIVE_SUFFIXES,
    family: str = "",
) -> NarrativePlanV3:
    paragraphs = tuple(
        NarrativeParagraphPlanV3(
            paragraph_id=f"{SECTION_ID}_{suffixes[index]}",
            section_id=SECTION_ID,
            role="core_transformations",
            mechanism_id=str(atom.payload["mechanism_id"]),
            required_detail_ids=tuple(
                str(detail["detail_id"]) for detail in (atom.payload.get("details") or ())
            ),
            witness_contract={
                "schema_version": "1.0",
                "paragraph_id": f"{SECTION_ID}_{suffixes[index]}",
                "rhetorical_goal": "core_transformations",
                "targets": [],
            },
        )
        for index, atom in enumerate(archive.mechanism_atoms)
    )
    unit_paragraph_ids = tuple(row.paragraph_id for row in paragraphs)
    unit_required_detail_ids = tuple(
        detail_id for row in paragraphs for detail_id in row.required_detail_ids
    )
    unit_mechanism_ids = tuple(
        str(atom.payload["mechanism_id"]) for atom in archive.mechanism_atoms
    )
    # K04-G5：**单变量**顺序对照。只有 narrative 家族改段落序列本身；其余家族只反转
    # 纯集合型 ID 列表，用来核查它们不会重排实际请求里的 Narrative 段落序列。
    if family == "narrative":
        paragraphs = tuple(reversed(paragraphs))
        unit_paragraph_ids = tuple(reversed(unit_paragraph_ids))
    elif family == "unit_details":
        unit_required_detail_ids = tuple(reversed(unit_required_detail_ids))
    elif family == "unit_mechanisms":
        unit_mechanism_ids = tuple(reversed(unit_mechanism_ids))
    elif family:
        raise ValueError(f"unknown order family: {family}")
    return NarrativePlanV3(
        plan_id="plan:hash-seed-probe",
        sections=(NarrativeSectionPlanV3(
            section_id=SECTION_ID,
            heading="Two mechanisms",
            mechanism_ids=unit_mechanism_ids,
            paragraphs=paragraphs,
        ),),
        narrative_units=(NarrativeUnitV1(
            unit_id="unit_probe",
            section_id=SECTION_ID,
            mechanism_context_ids=unit_mechanism_ids,
            rhetorical_role="core_model",
            reader_question="How do both mechanisms work?",
            paragraph_ids=unit_paragraph_ids,
            required_detail_ids=unit_required_detail_ids,
            optional_detail_ids=(),
            formula_obligation_ids=(),
            suggested_depth="standard",
        ),),
        context_set_digest=archive.content_digest,
    )


#: G5 单变量顺序对照的家族（见 ``_plan``）。
ORDER_FAMILIES: tuple[str, ...] = ("narrative", "unit_details", "unit_mechanisms")


def probe_page(lexicographic: bool = False, family: str = ""):
    """构建真实多段落 join 页并返回该页对象（调用生产编译入口，不改写生产逻辑）。"""

    archive, obligations = _archive()
    envelope = build_run_invocation_budget_envelope_v1(
        profile_budget=_budget_profile(),
        model_capabilities={"context_tokens": 131072},
        run_digest="sha256:probe-run",
        profile_digest="sha256:probe-profile",
        model_identity_digest="sha256:probe-model",
    )
    base = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    manifest = extend_writer_worksets_from_narrative_plan(
        base,
        _plan(
            archive,
            _LEXICOGRAPHIC_SUFFIXES if lexicographic else _NARRATIVE_SUFFIXES,
            family=family,
        ),
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
    )
    join_pages = [
        page for page in manifest.pages
        if str(page.page_kind) == "join" and len(page.technical_payload.get("paragraph_ids") or ()) > 1
    ]
    assert join_pages, "探针必须产出真实的多段落 join 页"
    return join_pages[0]


def probe(lexicographic: bool = False, family: str = "") -> str:
    """返回多段落 join 页的真实 page_id（最后一行输出）。"""

    page = probe_page(lexicographic=lexicographic, family=family)
    label = "lexicographic" if lexicographic else "narrative"
    if family:
        label += f":{family}"
    print("mode=" + label)
    print("paragraph_ids=" + ",".join(str(item) for item in page.technical_payload["paragraph_ids"]))
    print("technical_bytes_digest=" + str(page.technical_bytes_digest))
    return str(page.page_id)


def _budget_profile() -> dict[str, int]:
    profile: dict[str, int] = {
        "max_page_input_tokens": 20000,
        "max_total_input_tokens": 400000,
        "max_formalizer_calls": 8,
        "max_writer_calls": 8,
        "max_realizer_calls": 8,
        "max_binder_calls": 0,
        "max_obligations_per_page": 8,
        "max_formula_repair_calls": 0,
        "safety_margin_tokens": 1024,
        "prompt_token_reserve": 2048,
        "thinking_token_reserve": 0,
    }
    for role in ("formalizer", "writer", "realizer", "binder"):
        profile[f"output_token_reserve_{role}"] = 4096 if role != "binder" else 2048
        profile[f"max_request_input_tokens_{role}"] = 60000
        profile[f"scaffolding_token_reserve_{role}"] = 4096 if role in {
            "writer",
            "realizer",
        } else 0
        profile[f"retry_reserve_input_tokens_{role}"] = 0
    return profile


if __name__ == "__main__":  # pragma: no cover - 子进程入口
    import sys

    _args = sys.argv[1:]
    print(
        probe(
            lexicographic="lexicographic" in _args,
            family=next(
                (
                    item.split("=", 1)[1]
                    for item in _args
                    if item.startswith("family=")
                ),
                "",
            ),
        )
    )
