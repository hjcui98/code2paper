"""B01 夹具生成器：用**真实**编译器与请求 builder 建立合法正例。

本模块不实现第二套分页器、parser、assessor 或 Binder。它只做三件事：

1. 用生产入口构造真实证据归档，并让真实候选页编译器
   （``build_consumer_workset_manifest_v2`` /
   ``extend_writer_worksets_from_narrative_plan``）分页；
2. 用生产入口 ``_writer_section_inputs_v2`` 与真实请求 builder
   ``build_publication_writer_request`` 生成该页真正会发出的请求；
3. 用一个**离线确定性 provider**（不联网、不调用真实模型）按请求内容回答，
   再把回答交给真实 parser/assessor/Binder，记录它们真实的行为。

因此夹具里的页、请求、响应、判定都不是手写的：手写的只有 provider 的答复策略，
而答复内容完全从实际请求的页合同中派生。

确定性：本模块产出的每个 writer 页恰好包含一个语义段落，因此真实编译器内部
``set`` 迭代顺序不会影响结果。多段落页的该缺陷由
``test_legacy_characterization.py`` 单独记录（B01-D1）。
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

# 说明：本模块只读真实生产代码；下面的导入全部指向生产 owner，不是测试替身。
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextSetV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
    canonical_json_bytes,
)
from code2paper.agentic.formalization_agent import MechanismFormulaObligationV1
from code2paper.agentic.method_architect import (
    NarrativeParagraphPlanV3,
    NarrativePlanV3,
    NarrativeSectionPlanV3,
    NarrativeUnitV1,
)
from code2paper.agentic.page_contract_recheck import (
    author_surface_digest,
    binding_contract_digest,
    page_contract_snapshot_from_payload,
)
from code2paper.agentic.publication_method_writer import _writer_section_inputs_v2
from code2paper.agentic.publication_transaction_contract import (
    assess_paragraph_transaction,
    bind_paragraph_witnesses,
    closed_binding_target_keys,
    required_targets_from_plan_row,
    validate_paragraph_binding_response,
)
from code2paper.agentic.unified_context_compiler import (
    build_consumer_invocation_plan_v1,
    build_consumer_workset_manifest_v2,
    build_run_invocation_budget_envelope_v1,
    build_unified_context_archive_v2,
    consumer_response_json_schema,
    extend_writer_worksets_from_narrative_plan,
)
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.llm.response_schemas import (
    PublicationMethodSectionOutputV1,
    try_parse_structured_response_with_trace,
)
from code2paper.llm.section_writer import (
    WriterSectionInput,
    assess_publication_content_acceptance,
    assess_publication_writer_response,
    build_publication_writer_request,
)

__all__ = [
    "FIXTURE_SCHEMA_VERSION",
    "LEGAL_SECTION_ID",
    "AUTHOR_NO_ATOM_SECTION_ID",
    "SCHEMA_NAME",
    "build_all",
    "build_author_no_atom_fixture",
    "build_invalid_counterexamples",
    "build_legal_page_fixture",
    "write_golden",
]

FIXTURE_SCHEMA_VERSION = "b01-legacy-characterization/1"

#: 合法正例：一个真实机制细节页（作者段落带 atom 义务）。
LEGAL_SECTION_ID = "MA-L1"
#: 合法正例：作者段落没有任何 atom / detail 义务（"作者无 atom 页"）。
AUTHOR_NO_ATOM_SECTION_ID = "MA-N1"
SCHEMA_NAME = "publication_method_section_v1"
PLAN_ID = "plan:b01-legacy"

#: 夹具用的合成源码摘录。它们是**夹具数据**，不是生产逻辑里的项目答案；
#: 生产代码永远看不到这些字面量。
_SOURCE_EXCERPT = "def rescale(values, factor):\n    return values * factor\n"
_DETAIL_ANCHOR = "step for mech_rescale"
_NO_ATOM_READER_GOAL = "Why does the paper need this motivation paragraph?"


def _budget_profile() -> dict[str, int]:
    """与测试环境一致的显式预算（不依赖环境变量默认值）。"""

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


def _budget_envelope():
    return build_run_invocation_budget_envelope_v1(
        profile_budget=_budget_profile(),
        model_capabilities={"context_tokens": 131072},
        run_digest="sha256:b01-run",
        profile_digest="sha256:b01-profile",
        model_identity_digest="sha256:b01-model",
    )


def _evidence_archive():
    """建立冻结的 V1 证据集与 Formalizer 义务（真实 archive 编译器）。"""

    operation = EvidenceOperationV1(
        operation_id="op:rescale",
        predicate="rescale",
        operands=("values", "factor"),
        result="rescaled_values",
        source_span_id="",
        active_path_status="active_default",
    )
    detail = MechanismDetailV1(
        detail_id="d:rescale",
        primary_mechanism_id="mech_rescale",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="implementation",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom=_DETAIL_ANCHOR,
        predicate="rescale",
        operands=("values", "factor"),
        result="rescaled_values",
        active_path_status="active_default",
        source_operation_ids=(operation.operation_id,),
        witness_atoms=(DetailWitnessAtomV1(
            atom_id="atom:rescale",
            atom_kind="operation",
            semantic_anchor=_DETAIL_ANCHOR,
            source_operation_ids=(operation.operation_id,),
            exact_excerpts=("return values * factor",),
        ),),
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:mech_rescale",
        mechanism_id="mech_rescale",
        operation_nodes=(operation,),
        operation_dispositions=(SourceOperationDispositionV1(
            operation_id=operation.operation_id,
            disposition="absorbed_by_detail",
            detail_ids=(detail.detail_id,),
        ),),
        source_operation_terminal_coverage=1.0,
    )
    context = MechanismContextV1(
        mechanism_id="mech_rescale",
        mechanism_name="Rescale mechanism",
        scientific_role="core_model",
        reader_question="How does the rescale mechanism work?",
        purpose="Explain the rescaling step.",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=(detail.detail_id,),
        details=(detail,),
    )
    context_set = MechanismContextSetV1(
        repo_snapshot_id="repo:b01",
        project_tree_hash="sha256:b01-tree",
        intent_digest="sha256:b01-intent",
        alignment_digest="sha256:b01-alignment",
        research_digest="sha256:b01-research",
        contexts=(context,),
    )
    archive = build_unified_context_archive_v2(
        context_set, source_manifest_digest="sha256:b01-manifest"
    )
    obligations = {
        "mech_rescale": (MechanismFormulaObligationV1(
            obligation_id="ob:rescale",
            mechanism_id="mech_rescale",
            source_detail_ids=(detail.detail_id,),
            mathematical_goal="Formalize the rescaling step.",
        ),),
    }
    return archive, obligations


def _narrative_plan(archive) -> NarrativePlanV3:
    """冻结的 Narrative：一个机制段 + 一个作者无 atom 段。"""

    mechanism_paragraph = NarrativeParagraphPlanV3(
        paragraph_id=f"{LEGAL_SECTION_ID}_p1",
        section_id=LEGAL_SECTION_ID,
        role="core_transformations",
        mechanism_id="mech_rescale",
        required_detail_ids=("d:rescale",),
        witness_contract={
            "schema_version": "1.0",
            "paragraph_id": f"{LEGAL_SECTION_ID}_p1",
            "rhetorical_goal": "core_transformations",
            "targets": [],
        },
    )
    author_paragraph = NarrativeParagraphPlanV3(
        paragraph_id=f"{AUTHOR_NO_ATOM_SECTION_ID}_p1",
        section_id=AUTHOR_NO_ATOM_SECTION_ID,
        role="motivation",
        mechanism_id="",
        required_detail_ids=(),
        witness_contract={
            "schema_version": "1.0",
            "paragraph_id": f"{AUTHOR_NO_ATOM_SECTION_ID}_p1",
            "rhetorical_goal": "motivation",
            "targets": [],
        },
    )
    return NarrativePlanV3(
        plan_id=PLAN_ID,
        sections=(
            NarrativeSectionPlanV3(
                section_id=LEGAL_SECTION_ID,
                heading="Rescaling",
                mechanism_ids=("mech_rescale",),
                paragraphs=(mechanism_paragraph,),
            ),
            NarrativeSectionPlanV3(
                section_id=AUTHOR_NO_ATOM_SECTION_ID,
                heading="Motivation",
                mechanism_ids=(),
                paragraphs=(author_paragraph,),
            ),
        ),
        narrative_units=(
            NarrativeUnitV1(
                unit_id="unit_rescale",
                section_id=LEGAL_SECTION_ID,
                mechanism_context_ids=("mech_rescale",),
                rhetorical_role="core_model",
                reader_question="How does the rescale mechanism work?",
                paragraph_ids=(mechanism_paragraph.paragraph_id,),
                required_detail_ids=("d:rescale",),
                optional_detail_ids=(),
                formula_obligation_ids=(),
                suggested_depth="standard",
            ),
            NarrativeUnitV1(
                unit_id="unit_motivation",
                section_id=AUTHOR_NO_ATOM_SECTION_ID,
                mechanism_context_ids=(),
                rhetorical_role="motivation",
                reader_question=_NO_ATOM_READER_GOAL,
                paragraph_ids=(author_paragraph.paragraph_id,),
                required_detail_ids=(),
                optional_detail_ids=(),
                formula_obligation_ids=(),
                suggested_depth="brief",
            ),
        ),
        context_set_digest=archive.content_digest,
    )


def _writer_material(archive, obligations, plan, envelope):
    """真实候选页编译 + 真实 writer invocation plan。"""

    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        plan,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
    )
    invocation_plan = build_consumer_invocation_plan_v1(
        writer_manifest,
        envelope,
        phase="writer",
        plan_revision=1,
        profile_digest=envelope.profile_digest,
        model_identity_digest=envelope.model_identity_digest,
        model_context_tokens=131072,
    )
    writer_inputs = _writer_section_inputs_v2(
        narrative_plan=plan,
        formula_packages=(),
        formula_obligations=tuple(
            obligation for rows in obligations.values() for obligation in rows
        ),
        consumer_workset_manifest=writer_manifest,
        consumer_invocation_plan=invocation_plan,
    )
    return writer_manifest, invocation_plan, writer_inputs


# --------------------------------------------------------------------------- #
# 离线确定性 provider：只按实际请求内容作答，不联网、不使用真实模型
# --------------------------------------------------------------------------- #


def _page_paragraph_rows(section: WriterSectionInput) -> list[Mapping[str, Any]]:
    plan = section.prompt_payload.get("narrative_plan") or {}
    rows = plan.get("paragraphs") if isinstance(plan, Mapping) else None
    return [row for row in (rows or ()) if isinstance(row, Mapping)]


def _page_atoms(section: WriterSectionInput) -> list[Mapping[str, Any]]:
    atoms: list[Mapping[str, Any]] = []
    for payload in section.prompt_payload.get("shared_contexts") or ():
        if not isinstance(payload, Mapping):
            continue
        for atom in payload.get("atoms") or ():
            if isinstance(atom, Mapping):
                atoms.append(atom)
    return atoms


def _detail_atom(section: WriterSectionInput, detail_id: str) -> Mapping[str, Any]:
    """在**本页真实材料**里定位该 detail 的原子。"""

    bare = str(detail_id).removeprefix("detail:")
    for atom in _page_atoms(section):
        atom_id = str(atom.get("_atom_id") or "")
        candidates = {atom_id, atom_id.removeprefix("detail:")}
        if atom.get("detail_id"):
            candidates.add(str(atom["detail_id"]).removeprefix("detail:"))
        if bare in {value.removeprefix("detail:") for value in candidates}:
            return atom
    raise AssertionError(f"page材料里找不到 detail：{detail_id}")


def _detail_anchor_text(section: WriterSectionInput, detail_id: str) -> str:
    """作者声明 witness 用的语义锚（可读 exact excerpt 的来源之一）。"""

    atom = _detail_atom(section, detail_id)
    for witness in atom.get("witness_atoms") or ():
        if not isinstance(witness, Mapping):
            continue
        anchor = str(witness.get("semantic_anchor") or "").strip()
        if anchor:
            return anchor
    anchor = str(atom.get("semantic_atom") or "").strip()
    if not anchor:
        raise AssertionError(f"detail 没有可用语义锚：{detail_id}")
    return anchor


def _detail_excerpt_text(section: WriterSectionInput, detail_id: str) -> str:
    """Binder 绑定原子时要求逐字出现在正文里的源码摘录。"""

    atom = _detail_atom(section, detail_id)
    excerpts = [
        str(item) for item in (atom.get("exact_excerpts") or ()) if str(item).strip()
    ]
    for witness in atom.get("witness_atoms") or ():
        if not isinstance(witness, Mapping):
            continue
        excerpts.extend(
            str(item)
            for item in (witness.get("exact_excerpts") or ())
            if str(item).strip()
        )
    if not excerpts:
        raise AssertionError(f"detail 没有可读 exact excerpt：{detail_id}")
    return excerpts[0]


def offline_provider_response(
    section: WriterSectionInput,
    request: LLMRequest,
) -> LLMResponse:
    """确定性离线 provider：按页合同生成合法作者答复。

    它只做一件事——把请求里已经冻结的义务翻译成一条含 exact excerpt 的正文，
    并对每个 closed detail target 声明一次 witness。它不认识任何项目答案，
    也不读取页以外的材料。
    """

    rows = _page_paragraph_rows(section)
    if not rows:
        raise AssertionError("writer 请求里没有页段落合同")

    paragraphs: list[dict[str, Any]] = []
    for row in rows:
        paragraph_id = str(row.get("paragraph_id") or "")
        required = required_targets_from_plan_row(row)
        detail_ids = tuple(dict.fromkeys(
            str(value).removeprefix("detail:") for value in (required.get("detail") or ())
            if str(value).strip()
        ))
        witnesses: list[dict[str, str]] = []
        clauses: list[str] = []
        for detail_id in detail_ids:
            anchor = _detail_anchor_text(section, detail_id)
            excerpt = _detail_excerpt_text(section, detail_id)
            witnesses.append({
                "witness_kind": "detail",
                "target_id": detail_id,
                "exact_text": anchor,
            })
            clauses.append(
                f"the frozen anchor {anchor} is realized by {excerpt}"
            )
        if clauses:
            body = (
                "This paragraph states that " + "; ".join(clauses)
                + ", and keeps every claim on the material it was given."
            )
        else:
            body = (
                "This motivation paragraph only explains why the reader should care; "
                "it makes no implementation claim and cites no mechanism atom."
            )
        paragraphs.append({
            "paragraph_id": paragraph_id,
            "paragraph_markdown": body,
            "rendered_detail_ids": [str(item) for item in detail_ids],
            "deferred_detail_ids": [],
            "used_formula_package_ids": [],
            "witnesses": witnesses,
        })

    binding = section.prompt_payload.get("binding_contract") or {}
    payload = {
        "section_id": section.section_id,
        "heading_text": section.heading,
        "section_markdown": "\n\n".join(
            item["paragraph_markdown"] for item in paragraphs
        ),
        "paragraphs": paragraphs,
        "completed_rhetorical_moves": list(
            binding.get("required_rhetorical_moves") or ()
        ),
    }
    return LLMResponse(
        text=json.dumps(payload, ensure_ascii=False),
        metadata=payload,
        response_hash="sha256:b01-offline-provider",
        finish_reason="stop",
        token_usage={"prompt_tokens": 0, "completion_tokens": 0},
    )


# --------------------------------------------------------------------------- #
# 单个页夹具
# --------------------------------------------------------------------------- #


def _sentence_spans(text: str) -> list[str]:
    """按真实生产分句器切句（``final_text_claims._sentence_spans`` 同一实现）。"""

    from code2paper.agentic.final_text_claims import _sentence_spans as _spans

    return [sentence for sentence, _start, _end in _spans(text) if sentence.strip()]


def _claim_map(
    paragraph: Mapping[str, Any],
    transactions: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """逐句 claim 映射：每句 → 它真正承载的 closed target key。"""

    transaction = transactions[str(paragraph["paragraph_id"])]
    witnesses = [
        item for item in (transaction.get("witnesses") or ())
        if isinstance(item, Mapping)
    ]
    mapped: list[dict[str, Any]] = []
    for sentence in _sentence_spans(str(paragraph.get("paragraph_markdown") or "")):
        targets = [
            f"{item.get('witness_kind')}:{item.get('target_id')}"
            for item in witnesses
            if str(item.get("exact_text") or "") and str(item["exact_text"]) in sentence
        ]
        mapped.append({
            "sentence": sentence,
            "target_keys": targets,
            "declared_detail_ids": [
                str(item) for item in (paragraph.get("rendered_detail_ids") or ())
            ],
            "claim_kind": "author_prose" if targets else "author_statement",
        })
    return mapped


def _page_fixture(
    *,
    section: WriterSectionInput,
    request: LLMRequest,
    response_schema: dict[str, Any],
    invocation: Any,
    page: Any,
    scenario: str,
    provider_response: LLMResponse | None = None,
) -> dict[str, Any]:
    """把一个真实 writer 页的完整链路结果压成可读夹具。"""

    provider_response = provider_response or offline_provider_response(section, request)
    parsed, trace, error = try_parse_structured_response_with_trace(
        provider_response.text, PublicationMethodSectionOutputV1
    )
    assert error == "" and parsed is not None, f"离线 provider 的答复未能通过真实 parser：{error}"

    parsed_response = LLMResponse(
        text=provider_response.text,
        metadata=parsed,
        response_hash=provider_response.response_hash,
        finish_reason=provider_response.finish_reason,
        token_usage=payload_token_usage(provider_response),
    )
    metrics = assess_publication_writer_response(section, parsed_response)
    accepted, acceptance_metrics = assess_publication_content_acceptance(
        section, parsed_response
    )

    rows = {str(row.get("paragraph_id")): row for row in _page_paragraph_rows(section)}
    formula_packages = tuple(section.prompt_payload.get("formula_packages") or ())
    formula_routes = {
        str(obligation_id): {"package_ids": [package["package_id"]], "latex": package["markdown_block"]}
        for package in formula_packages
        for obligation_id in package.get("satisfied_obligation_ids", ())
    }
    paragraphs = []
    transactions: dict[str, dict[str, Any]] = {}
    for item in parsed.paragraphs:
        plan_row = rows[str(item.paragraph_id)]
        transaction = item.model_dump(mode="json")
        transactions[str(item.paragraph_id)] = transaction
        bound = bind_paragraph_witnesses(transaction, plan_row=plan_row, formula_packages=formula_packages)
        writer_stage = assess_paragraph_transaction(
            transaction, plan_row=plan_row, validation_stage="writer_content", formula_routes=formula_routes
        )
        binder_stage = assess_paragraph_transaction(
            bound, plan_row=plan_row, validation_stage="final_bound", formula_routes=formula_routes
        )
        binder_response = validate_paragraph_binding_response(
            {"paragraph_id": item.paragraph_id, "witnesses": [], "unbound_target_ids": []},
            transaction,
            plan_row=plan_row,
        )
        paragraphs.append({
            "plan_row": copy.deepcopy(dict(plan_row)),
            "response": {
                "paragraph_id": str(item.paragraph_id),
                "paragraph_markdown": str(item.paragraph_markdown),
                "rendered_detail_ids": list(item.rendered_detail_ids),
                "witnesses": [dict(w) for w in transaction.get("witnesses") or ()],
            },
            "closed_target_keys": sorted(
                f"{kind}:{target}"
                for kind, target in closed_binding_target_keys(plan_row=plan_row)
            ),
            "required_targets": {
                kind: list(values)
                for kind, values in required_targets_from_plan_row(plan_row).items()
            },
            "exact_excerpts": [
                {
                    "target_kind": "detail",
                    "target_id": str(detail_id),
                    "role": "writer_declaration_anchor",
                    "exact_text": _detail_anchor_text(section, str(detail_id)),
                    "source": "page.shared_contexts atoms[].witness_atoms[].semantic_anchor",
                }
                for detail_id in (required_targets_from_plan_row(plan_row).get("detail") or ())
            ] + [
                {
                    "target_kind": "atom",
                    "target_id": str(detail_id),
                    "role": "binder_exact_excerpt",
                    "exact_text": _detail_excerpt_text(section, str(detail_id)),
                    "source": "page.shared_contexts atoms[].exact_excerpts[0]",
                }
                for detail_id in (required_targets_from_plan_row(plan_row).get("detail") or ())
            ],
            "sentence_claim_map": _claim_map(transaction, transactions),
            "observed": {
                "writer_content": {
                    "valid": bool(writer_stage.valid),
                    "status": str(writer_stage.status),
                    "failure_codes": [str(f.code) for f in writer_stage.failures],
                    "missing_by_kind": {
                        kind: list(values)
                        for kind, values in writer_stage.missing_by_kind.items()
                    },
                },
                "final_bound": {
                    "valid": bool(binder_stage.valid),
                    "status": str(binder_stage.status),
                    "failure_codes": [str(f.code) for f in binder_stage.failures],
                    "witnessed_by_kind": {
                        kind: list(values)
                        for kind, values in binder_stage.witnessed_by_kind.items()
                    },
                    "derived_rendered_detail_ids": list(bound.get("rendered_detail_ids") or ()),
                    "binder_attached_witnesses": [
                        dict(item) for item in (bound.get("witnesses") or ())
                        if isinstance(item, Mapping)
                    ],
                },
                "binder_response_validation": {
                    "valid_witnesses": [dict(row) for row in binder_response[0]],
                    "errors": list(binder_response[1]),
                    "unbound": list(binder_response[2]),
                },
            },
        })

    page_bytes = canonical_json_bytes(dict(page.technical_payload))
    payload = dict(request.input_payload)
    return {
        "scenario": scenario,
        "section_id": section.section_id,
        "heading": section.heading,
        "prompt_template_id": request.prompt_template_id,
        "page": {
            "page_id": str(page.page_id),
            "page_kind": str(getattr(page, "page_kind", "")),
            "mechanism_id": str(page.mechanism_id),
            "atom_ids": list(page.atom_ids),
            "technical_bytes_digest": str(page.technical_bytes_digest),
            "technical_bytes_sha256": _sha256(page_bytes),
            "content_digest": str(page.content_digest),
            "token_estimate": int(page.token_estimate),
            "technical_payload": dict(page.technical_payload),
        },
        "invocation": {
            "invocation_id": str(invocation.invocation_id),
            "page_id": str(invocation.page_id),
            "workset_id": str(invocation.workset_id),
            "role": str(invocation.role),
            "task_ids": list(invocation.task_ids),
            "max_output_tokens": int(invocation.max_output_tokens),
            "is_repair": bool(invocation.is_repair),
        },
        "request": {
            "prompt_template_id": request.prompt_template_id,
            "prompt_sha256": _sha256(str(request.prompt).encode("utf-8")),
            "input_payload": payload,
            "response_schema_sha256": _sha256(
                canonical_json_bytes(response_schema)
            ),
            "response_schema_paragraph_id_enum": list(
                response_schema["$defs"]["PublicationMethodParagraphOutputV1"]
                ["properties"]["paragraph_id"].get("enum") or ()
            ),
            "page_contract_snapshot": page_contract_snapshot_from_payload(
                invocation_id=str(invocation.invocation_id),
                payload=payload,
                request_digest=str(getattr(request, "request_digest", "") or ""),
            ).model_dump(mode="json"),
            "author_surface_digest": author_surface_digest(payload),
            "binding_contract_digest": binding_contract_digest(payload),
        },
        "page_contract_frozen": {
            "author_surface": _author_surface(payload),
            "scope": _scope(payload),
            # 真实 unified 页请求**不携带** config，冻结上限来自调用计划的每页预算；
            # 生产代码在比较前把它注入 snapshot（publication_method_writer §C.6）。
            "declared_in_payload": int(
                ((payload.get("config") or {}) if isinstance(payload.get("config"), Mapping) else {})
                .get("max_output_tokens") or 0
            ),
            "effective_max_output_tokens": int(invocation.max_output_tokens),
            # 同上：payload 不声明技术字节摘要时，生产代码从真实页对象注入冻结值。
            "declared_technical_bytes_digest": str(
                payload.get("technical_bytes_digest") or payload.get("page_bytes_digest") or ""
            ),
            "effective_technical_bytes_digest": str(page.technical_bytes_digest),
        },
        "paragraphs": paragraphs,
        "offline_response": {
            "raw_text": provider_response.text,
            "parsed_ok": True,
            "parse_trace_operations": list(getattr(trace, "operations", ()) or ()),
            "paragraph_ids": [str(item.paragraph_id) for item in parsed.paragraphs],
        },
        "observed_local_gate": {
            "content_accepted": bool(accepted),
            "metrics": {
                key: _jsonable(value) for key, value in acceptance_metrics.items()
            },
            "writer_transaction_valid": bool(
                all(item["observed"]["writer_content"]["valid"] for item in paragraphs)
            ),
            "binder_transaction_valid": bool(
                all(item["observed"]["final_bound"]["valid"] for item in paragraphs)
            ),
        },
        "verified": {
            # AT-B01：合法正例只证明其**声明的局部门**。旧路径的全局 Verified
            # 由 ``legacy_pipeline_characterization`` 记录为 not_run/False，
            # 不能被当成"新桥已正确验证"的证据。
            "global_verified_status": "not_run",
            "global_verified_complete": False,
            "local_gate": "writer_content+final_bound page transaction",
        },
    }


def _author_surface(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    plan = payload.get("narrative_plan") or {}
    rows = plan.get("paragraphs") if isinstance(plan, Mapping) else None
    surface: list[dict[str, str]] = []
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        contract = row.get("witness_contract")
        surface.append({
            "paragraph_id": str(row.get("paragraph_id") or ""),
            "reader_goal": str(row.get("reader_goal") or ""),
            "role": str(row.get("role") or ""),
            "rhetorical_goal": str(
                (contract or {}).get("rhetorical_goal")
                if isinstance(contract, Mapping) else ""
            ),
        })
    return surface


def _scope(payload: Mapping[str, Any]) -> dict[str, list[str]]:
    binding = payload.get("binding_contract")
    if not isinstance(binding, Mapping):
        return {}
    return {
        str(key): sorted(str(item) for item in value)
        for key, value in binding.items()
        if isinstance(value, (list, tuple))
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


def payload_token_usage(response: LLMResponse) -> dict[str, int]:
    usage = getattr(response, "token_usage", None) or {}
    return {str(key): int(value) for key, value in usage.items()}


def _sha256(payload: bytes) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------- #
# 场景
# --------------------------------------------------------------------------- #


def _build_scenarios() -> dict[str, Any]:
    archive, obligations = _evidence_archive()
    envelope = _budget_envelope()
    plan = _narrative_plan(archive)
    writer_manifest, invocation_plan, writer_inputs = _writer_material(
        archive, obligations, plan, envelope
    )
    page_index = {str(page.page_id): page for page in writer_manifest.pages}
    invocations = {
        str(getattr(item, "page_id", "")): item
        for item in invocation_plan.invocations
        if str(getattr(item, "role", "")) == "writer"
        and not bool(getattr(item, "is_repair", False))
    }

    fixtures: dict[str, Any] = {}
    for section in writer_inputs:
        payload = section.prompt_payload
        page_id = str(payload.get("unified_v2_page_id") or "")
        invocation = invocations.get(page_id)
        page = page_index.get(page_id)
        assert invocation is not None, f"缺少 writer invocation：{page_id}"
        assert page is not None, f"缺少页对象：{page_id}"
        request = build_publication_writer_request(
            section,
            system_prompt=section.system_prompt,
            schema_name=SCHEMA_NAME,
            response_json_schema=consumer_response_json_schema(
                "writer", section_id=section.section_id
            ),
        )
        schema = copy.deepcopy(request.response_json_schema)
        fixture = _page_fixture(
            section=section,
            request=request,
            response_schema=schema,
            invocation=invocation,
            page=page,
            scenario=(
                "legal_page_with_atoms"
                if section.section_id == LEGAL_SECTION_ID
                else "author_no_atom_page"
            ),
        )
        fixture["formed_from"] = {
            "archive_digest": str(getattr(archive, "content_digest", "")),
            "writer_manifest_digest": str(writer_manifest.content_digest),
            "invocation_plan_digest": str(invocation_plan.content_digest),
            "narrative_plan_id": str(plan.plan_id),
            "formalizer_obligation_ids": sorted(
                str(item.obligation_id)
                for rows in obligations.values()
                for item in rows
            ),
        }
        fixtures[section.section_id] = fixture
    return fixtures


def build_legal_page_fixture() -> dict[str, Any]:
    return _build_scenarios()[LEGAL_SECTION_ID]


def build_author_no_atom_fixture() -> dict[str, Any]:
    return _build_scenarios()[AUTHOR_NO_ATOM_SECTION_ID]


def build_completed_formalizer_fixture(
    *, response_mutation: str = "", evidence_root: str | Path | None = None,
) -> dict[str, Any]:
    from .completed_formalizer_fixture import build_fixture

    return build_fixture(response_mutation=response_mutation, evidence_root=evidence_root)


# --------------------------------------------------------------------------- #
# 具名非法反例
# --------------------------------------------------------------------------- #

#: 每个反例只对冻结正例做一处改动，并固定它**具名**的拒绝结果。
INVALID_CASES: tuple[dict[str, Any], ...] = (
    # --- 发送前页合同（真实 compare_actual_request_to_page_contract） ---------
    {
        "name": "narrative_paragraph_appended",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "/narrative_plan/page_paragraph_ids",
        "operation": "append",
        "value": ["MA-L1_p2"],
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:paragraph_ids",
    },
    {
        # 单段落页无法表达"重排"；真实的等价反例是同一段落被换成另一个 id，
        # 它改变作者 surface 而不是段落计数。
        "name": "author_surface_paragraph_id_renamed",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "/narrative_plan/paragraphs/0/paragraph_id",
        "operation": "set",
        "value": "MA-L1_p9",
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:author_surface",
    },
    {
        "name": "detail_scope_shrunk",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "/binding_contract/required_detail_ids",
        "operation": "set",
        "value": [],
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:scope:required_detail_ids",
    },
    {
        "name": "empty_formula_whitelist_expanded",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "/binding_contract/allowed_formula_package_ids",
        "operation": "set",
        "value": ["pkg:not_authorized"],
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:scope:allowed_formula_package_ids",
    },
    {
        "name": "output_cap_raised",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "",
        "operation": "cap_delta",
        "value": 1,
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:output_cap",
    },
    {
        "name": "output_cap_lowered",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "",
        "operation": "cap_delta",
        "value": -1,
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:output_cap",
    },
    {
        "name": "author_reader_goal_rewritten",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "/narrative_plan/paragraphs/0/reader_goal",
        "operation": "set",
        "value": "Rewrite the author goal to something the author never asked for.",
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:author_surface",
    },
    {
        "name": "author_rhetorical_goal_rewritten",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "/narrative_plan/paragraphs/0/witness_contract/rhetorical_goal",
        "operation": "set",
        "value": "overview",
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:author_surface",
    },
    {
        # 实际请求自己声明了与冻结值不同的技术字节摘要。
        "name": "technical_bytes_rewritten",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "/technical_bytes_digest",
        "operation": "set",
        "value": "sha256:" + "0" * 64,
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:technical_bytes",
    },
    {
        "name": "repair_without_frozen_contract",
        "surface": "page_contract",
        "base": "legal_page_with_atoms",
        "pointer": "",
        "operation": "drop_frozen_contract",
        "value": None,
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:frozen_page_contract_missing",
    },
    {
        "name": "author_no_atom_page_atom_obligation_injected",
        "surface": "page_contract",
        "base": "author_no_atom_page",
        "pointer": "/binding_contract/required_detail_ids",
        "operation": "set",
        "value": ["d:rescale"],
        "expected_kind": "page_contract",
        "expected": "actual_page_contract_mismatch:scope:required_detail_ids",
    },
    # --- 真实 parser / 归一化 -------------------------------------------------
    {
        "name": "writer_invented_paragraph_id",
        "surface": "response_parser",
        "base": "legal_page_with_atoms",
        "pointer": "/paragraphs/0/paragraph_id",
        "operation": "set",
        "value": "MA-L1_invented",
        "expected_kind": "response_parser",
        "expected": "unknown_paragraph_transaction:MA-L1_invented",
    },
    {
        "name": "writer_unknown_field",
        "surface": "response_parser",
        "base": "legal_page_with_atoms",
        "pointer": "/paragraphs/0/bogus_field",
        "operation": "set",
        "value": "not-permitted",
        "expected_kind": "response_parser",
        "expected": "schema_validation_failed:ValidationError",
    },
    {
        "name": "writer_missing_paragraph_transaction",
        "surface": "response_parser",
        "base": "legal_page_with_atoms",
        "pointer": "/paragraphs",
        "operation": "set",
        "value": [],
        "expected_kind": "response_parser",
        "expected": "paragraph_transaction_missing",
    },
    {
        "name": "writer_heading_only_body",
        "surface": "response_parser",
        "base": "legal_page_with_atoms",
        "pointer": "/paragraphs/0/paragraph_markdown",
        "operation": "set",
        "value": "## Rescaling",
        "expected_kind": "response_parser",
        "expected": "paragraph_body_not_substantive:MA-L1_p1",
    },
    # --- Writer 内容阶段事务判定（writer_content） ---------------------------
    {
        "name": "writer_detail_witness_removed",
        "surface": "paragraph_assessor",
        "base": "legal_page_with_atoms",
        "pointer": "/paragraphs/0/witnesses",
        "operation": "set",
        "value": [],
        "expected_kind": "paragraph_assessor",
        "expected": "detail_witness_missing",
    },
    {
        "name": "writer_witness_not_verbatim",
        "surface": "paragraph_assessor",
        "base": "legal_page_with_atoms",
        "pointer": "/paragraphs/0/witnesses/0/exact_text",
        "operation": "set",
        "value": "an anchor sentence that never appears in the frozen paragraph",
        "expected_kind": "paragraph_assessor",
        "expected": "exact_span_not_in_body",
    },
    # --- Binder 阶段事务判定（final_bound） ---------------------------------
    {
        # 原子摘录仍在正文里，但 detail 自己的 exact witness 缺失：
        # 确定性 Binder 不会用 atom 摘录替代 detail 义务。
        "name": "binder_detail_obligation_unsatisfied_by_atom_excerpt",
        "surface": "binder",
        "base": "legal_page_with_atoms",
        "pointer": "/paragraphs/0/witnesses",
        "operation": "set",
        "value": [],
        "expected_kind": "binder",
        "expected": "detail_witness_missing",
    },
    {
        "name": "binder_frozen_prose_loses_the_declared_witness",
        "surface": "binder",
        "base": "legal_page_with_atoms",
        "pointer": "/paragraphs/0/paragraph_markdown",
        "operation": "set",
        "value": "This paragraph keeps every claim on the material it was given.",
        "expected_kind": "binder",
        "expected": "exact_span_not_in_body",
    },
    # --- 页模型自身的闭合约束 -------------------------------------------------
    {
        "name": "technical_page_without_atoms",
        "surface": "page_model",
        "base": "legal_page_with_atoms",
        "pointer": "",
        "operation": "page_kind_without_atoms",
        "value": "technical",
        "expected_kind": "page_model",
        "expected": "must carry atom IDs",
    },
    {
        "name": "page_projection_proof_mismatch",
        "surface": "page_model",
        "base": "legal_page_with_atoms",
        "pointer": "",
        "operation": "projection_proof_mismatch",
        "value": None,
        "expected_kind": "page_model",
        "expected": "projection proof is not exact",
    },
)


def build_provenance(golden_digests: Mapping[str, str]) -> dict[str, Any]:
    """夹具来源清单：谁生成的、由哪些生产 owner 生成、已知缺陷是什么。"""

    return {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "task": "B01",
        "generated_by": "tests/integrations/dsh/fixtures/legacy_fixture_builder.py",
        "real_owners": [
            "code2paper.agentic.formalization_agent.execute_formalizer_invocation_plan",
            "code2paper.agentic.formalization_agent.validate_mechanism_formula_package",
            "code2paper.agentic.formalization_agent.adapt_mechanism_formula_package_to_legacy",
            "code2paper.llm.response_schemas.UnifiedFormalizerResponseV2",
            "code2paper.agentic.publication_transaction_contract.splice_formula_placeholders",
            "code2paper.agentic.unified_context_compiler.build_unified_context_archive_v2",
            "code2paper.agentic.unified_context_compiler.build_consumer_workset_manifest_v2",
            "code2paper.agentic.unified_context_compiler."
            "extend_writer_worksets_from_narrative_plan",
            "code2paper.agentic.unified_context_compiler.build_consumer_invocation_plan_v1",
            "code2paper.agentic.unified_context_compiler.consumer_response_json_schema",
            "code2paper.agentic.publication_method_writer._writer_section_inputs_v2",
            "code2paper.llm.section_writer.build_publication_writer_request",
            "code2paper.llm.section_writer.assess_publication_writer_response",
            "code2paper.llm.section_writer.assess_publication_content_acceptance",
            "code2paper.agentic.publication_transaction_contract."
            "assess_paragraph_transaction",
            "code2paper.agentic.publication_transaction_contract.bind_paragraph_witnesses",
            "code2paper.agentic.publication_transaction_contract."
            "validate_paragraph_binding_response",
            "code2paper.agentic.page_contract_recheck."
            "compare_actual_request_to_page_contract",
            "code2paper.llm.response_schemas.try_parse_structured_response_with_trace",
            "code2paper.agentic.final_text_claims._sentence_spans",
            "code2paper.agentic.publication_method_writer.run_publication_method_writer",
        ],
        "fixture_owned_inputs": [
            "synthetic MechanismContextSetV1 (mech_rescale / d:rescale)",
            "synthetic NarrativePlanV3 (MA-L1 机制段 + MA-N1 作者无 atom 段)",
            "offline deterministic provider (tests/integrations/dsh/fixtures, no network)",
        ],
        "not_from_this_fixture": [
            "real provider HTTP/SSE bytes",
            "Verified / candidate acceptance",
            "任何真实项目答案：夹具材料是合成的 rescale 机制，不是仓库数据集",
        ],
        "determinism": {
            "requirement": "每个 writer 页恰好一个语义段落",
            "why": (
                "B01 夹具的页都是单段落，因此不经过多段落累加路径；多段落页的"
                "Narrative 保序由 K04 修复并在 test_legacy_characterization 的跨 seed "
                "回归中验证（原缺陷见 known_defects 的 B01-D1）"
            ),
        },
        "legacy_verified": {
            "source": "run_publication_method_writer(authoring_context_mode='unified') 实测",
            "verified_validation_status": "not_run",
            "verified_complete": False,
            "publication_ready": False,
            "note": (
                "AT-B01：旧夹具的全局 Verified 为空，只能证明页级局部门，"
                "不能当作新桥已正确验证的证据"
            ),
        },
        "known_defects": [
            {
                "id": "B01-D1",
                "summary": (
                    "extend_writer_worksets_from_narrative_plan 生成的多段落页，"
                    "其 technical_payload['paragraph_ids'] 顺序来自 set 迭代，"
                    "同一输入在不同 PYTHONHASHSEED 下得到不同 page_id / 摘要"
                ),
                "owner_file": "src/code2paper/agentic/unified_context_compiler.py",
                "summary_original": (
                    "extend_writer_worksets_from_narrative_plan 生成的多段落页，"
                    "其 technical_payload['paragraph_ids'] 顺序来自 set 迭代，"
                    "同一输入在不同 PYTHONHASHSEED 下得到不同 page_id / 摘要"
                ),
                "status": "fixed_by_K04",
                "fixed_by": "K04",
                "fix": (
                    "unified_context_compiler 的分页累加器由 set 改为保序去重列表"
                    "（_ordered_unique_strings），flush 与合并全程保持 Narrative 顺序"
                ),
                "evidence": (
                    "tests/integrations/dsh/test_legacy_characterization.py::"
                    "test_join_page_identity_and_narrative_order_are_stable_across_hash_seeds"
                ),
                "evidence_original": (
                    "tests/integrations/dsh/test_legacy_characterization.py::"
                    "test_join_page_identity_is_not_stable_across_hash_seeds"
                    "（B01 特征记录，已由上面的稳定性回归取代；原日志保留）"
                ),
                "deadline": "closed before Gate-K by K04; narrative order preserved across hash seeds",
                "identity_scope": "material/page/task contract identity, not runtime composition digest",
            },
        ],
        "characterized_gaps": [
            {
                "id": "B01-G1",
                "summary": (
                    "compare_actual_request_to_page_contract 曾只在**实际 payload 自己声明**"
                    "技术字节摘要时才比较它；unified V2 writer 页请求的 input_payload 不声明"
                    "该字段，因此缺少外层逐字比较时，改技术材料不会被这一步发现"
                ),
                "status": "fixed_by_K04",
                "fixed_by": "K04",
                "fix": (
                    "公共复核改为接收调用方从**实际材料字节重算**的摘要"
                    "（actual_technical_bytes_digest）；声明字段不再替代重算，"
                    "有冻结摘要而重算值缺失时 fail-closed（technical_bytes_unknown）"
                ),
                "evidence": (
                    "tests/integrations/dsh/test_legacy_characterization.py::"
                    "test_missing_measured_technical_digest_is_refused_by_the_helper"
                ),
                "evidence_original": (
                    "tests/integrations/dsh/test_legacy_characterization.py::"
                    "test_absent_actual_technical_digest_is_not_detected_by_the_helper"
                    "（B01 特征记录，已由上面的 K04 回归取代；原日志保留）"
                ),
                "owner": "K04",
                "real_send_point_evidence": (
                    "tests/regression_20260922/test_authoring_contract_closure.py::"
                    "test_technical_bytes_digest_mismatch_is_refused_before_the_provider"
                ),
            },
            {
                "id": "B01-G2",
                "summary": (
                    "该单一detail样例的witness_contract.targets为空且required_atom_count=0；"
                    "只证明当前detail-only target集合，不证明非空atom义务已经闭合。"
                    "C02须补非空atom合同正反例，并保留合法header页无atom语义"
                ),
                "owner": "C02",
                "evidence": (
                    "tests/integrations/dsh/test_legacy_characterization.py::"
                    "test_atom_obligation_is_carried_by_the_detail_not_a_separate_target"
                ),
                "status": "characterized_by_B01_not_fixed_here",
            },
        ],
        "golden_digests": dict(golden_digests),
        "golden_historical_digests": _golden_historical_digests(golden_digests),
    }


#: K04-G6：四个 golden 的**独立旧摘要出处**。每个条目绑定出处文件本身的 sha256，
#: 因此出处文件被改写时该登记立即失效（不能靠重新生成夹具把历史改写成"一直如此"）。
#: 没有独立出处的 golden 必须如实登记 ``not_proven``，不得倒造历史 hash。
_HISTORICAL_DIGEST_SOURCES: dict[str, dict[str, Any]] = {
    "legal_page_with_atoms": {
        "source": "tests/integrations/dsh/fixtures/B01_formalizer_repair_evidence.md",
        "source_kind": "b01_handoff_record",
        "source_sha256": (
            "sha256:6efdcac9729f37954779c8e437687fa38e8fdb12055d92363c86a8fb99b6901d"
        ),
        "status": "attested",
        "note": "B01 形式化修复交接记录里逐字登记的旧摘要；与夹具字节相互独立。",
    },
    "author_no_atom_page": {
        "source": "tests/integrations/dsh/fixtures/B01_formalizer_repair_evidence.md",
        "source_kind": "b01_handoff_record",
        "source_sha256": (
            "sha256:6efdcac9729f37954779c8e437687fa38e8fdb12055d92363c86a8fb99b6901d"
        ),
        "status": "attested",
        "note": "同上：同一份 B01 交接记录里的独立登记。",
    },
    "invalid_counterexamples": {
        "source": "tests/integrations/dsh/fixtures/B01_formalizer_repair_evidence.md",
        "source_kind": "b01_handoff_record",
        "source_sha256": (
            "sha256:6efdcac9729f37954779c8e437687fa38e8fdb12055d92363c86a8fb99b6901d"
        ),
        "status": "attested",
        "note": "同上：同一份 B01 交接记录里的独立登记。",
    },
    "completed_formalizer_page": {
        "source": "",
        "source_kind": "",
        "source_sha256": "",
        "status": "not_proven",
        "note": (
            "未证明：该 golden 的摘要只在当前 provenance.json 中出现过，工作树与 git 历史"
            "都没有更早的独立出处。按 K04-G6 如实标未证明，不倒造历史 hash；"
            "若后续找到出处，登记新出处并重验。"
        ),
    },
}


def _golden_historical_digests(
    golden_digests: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for name in sorted(golden_digests):
        row = dict(_HISTORICAL_DIGEST_SOURCES.get(name) or {})
        row.setdefault("source", "")
        row.setdefault("source_kind", "")
        row.setdefault("source_sha256", "")
        row["status"] = str(row.get("status") or "not_proven")
        row["digest"] = str(golden_digests[name])
        registry[name] = row
    return registry


def _resolve_pointer(payload: Any, pointer: str) -> tuple[Any, str]:
    if not pointer:
        return None, ""
    parts = [item.replace("~1", "/").replace("~0", "~") for item in pointer.split("/")[1:]]
    node = payload
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node, parts[-1]


def _apply_mutation(base: dict[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    """对冻结正例做**一处**改动；返回改动后的响应或请求 payload。"""

    mutated = copy.deepcopy(base)
    operation = str(case["operation"])
    pointer = str(case["pointer"])
    if operation == "drop_frozen_contract":
        mutated["__frozen_contract__"] = None
        return mutated
    if operation == "cap_delta":
        mutated["__max_output_tokens_delta__"] = int(case["value"])
        return mutated
    parent, last = _resolve_pointer(mutated, pointer)
    value = copy.deepcopy(case["value"])
    if operation == "append":
        parent[last] = list(parent[last]) + list(value)
    elif operation == "set":
        if isinstance(parent, list):
            parent[int(last)] = value
        else:
            parent[last] = value
    else:  # pragma: no cover - 生成器自身的防线
        raise AssertionError(f"未知的 mutation operation：{operation}")
    return mutated


def build_invalid_counterexamples() -> dict[str, Any]:
    """把具名反例固化为一处改动的**规格**（改动本身由测试施加在冻结正例上）。

    这里刻意不保存改动后的 payload：反例必须是"冻结正例 + 一处改动"，
    两处各存一份就可能各自漂移。
    """

    return {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "cases": [
            {
                "name": str(case["name"]),
                "surface": str(case["surface"]),
                "base": str(case["base"]),
                "mutation": {
                    "operation": str(case["operation"]),
                    "pointer": str(case["pointer"]),
                    "value": _jsonable(case["value"]),
                },
                "expected_kind": str(case["expected_kind"]),
                "expected": str(case["expected"]),
            }
            for case in INVALID_CASES
        ],
    }


def response_payload(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """从夹具重建离线 provider 的响应 payload（逐段可读）。"""

    paragraphs: list[dict[str, Any]] = []
    for row in fixture["paragraphs"]:
        response = row["response"]
        paragraphs.append({
            "paragraph_id": response["paragraph_id"],
            "paragraph_markdown": response["paragraph_markdown"],
            "rendered_detail_ids": list(response["rendered_detail_ids"]),
            "witnesses": [dict(item) for item in response["witnesses"]],
        })
    return {
        "section_id": fixture["section_id"],
        "heading_text": fixture["heading"],
        "section_markdown": "\n\n".join(
            item["paragraph_markdown"] for item in paragraphs
        ),
        "paragraphs": paragraphs,
    }


def frozen_subject(fixture: Mapping[str, Any], surface: str) -> dict[str, Any]:
    """反例作用的对象：页合同面改请求 payload，其余面改响应 payload。"""

    if surface == "page_contract":
        return copy.deepcopy(fixture["request"]["input_payload"])
    return response_payload(fixture)


def apply_mutation(base: Mapping[str, Any], mutation: Mapping[str, Any]) -> dict[str, Any]:
    """对冻结正例做**一处**改动；``mutation`` 是反例记录里的 ``mutation`` 字段。"""

    mutated = copy.deepcopy(dict(base))
    operation = str(mutation["operation"])
    pointer = str(mutation["pointer"])
    if operation == "drop_frozen_contract":
        mutated["__frozen_contract__"] = None
        return mutated
    if operation == "cap_delta":
        mutated["__max_output_tokens_delta__"] = int(mutation["value"])
        return mutated
    parent, last = _resolve_pointer(mutated, pointer)
    value = copy.deepcopy(mutation["value"])
    if operation == "append":
        parent[last] = list(parent[last]) + list(value)
    elif operation == "set":
        if isinstance(parent, list):
            parent[int(last)] = value
        else:
            parent[last] = value
    else:  # pragma: no cover - 生成器自身的防线
        raise AssertionError(f"未知的 mutation operation：{operation}")
    return mutated


def build_all() -> dict[str, Any]:
    scenarios = _build_scenarios()
    legal = scenarios[LEGAL_SECTION_ID]
    author = scenarios[AUTHOR_NO_ATOM_SECTION_ID]
    return {
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "legal_page_with_atoms": legal,
        "author_no_atom_page": author,
        "invalid_counterexamples": build_invalid_counterexamples(),
        "completed_formalizer_page": build_completed_formalizer_fixture(),
    }


def golden_bytes(payload: Any) -> bytes:
    """夹具文件的唯一序列化形式（排序键、缩进 2、尾随换行）。"""

    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_golden(root: str | Path) -> dict[str, Path]:
    """把夹具写到 ``root``（默认 ``fixtures/golden``）并返回路径。"""

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    payload = build_all()
    written: dict[str, Path] = {}
    digests: dict[str, str] = {}
    for key, value in payload.items():
        if key == "schema_version":
            continue
        data = golden_bytes(value)
        digests[key] = _sha256(data)
        (root / f"{key}.json").write_bytes(data)
        written[key] = root / f"{key}.json"
    provenance_bytes = golden_bytes(build_provenance(digests))
    (root / "provenance.json").write_bytes(provenance_bytes)
    written["provenance"] = root / "provenance.json"
    return written


if __name__ == "__main__":  # pragma: no cover - 手工再生成入口
    target = Path(__file__).with_name("golden")
    for name, path in write_golden(target).items():
        print(f"{name}: {path}")
