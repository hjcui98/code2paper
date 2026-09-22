"""PR C.6 / F01：发送前用最终实际请求复核冻结 page contract（审计 §C.6）。

冻结 oracle = 事故归档里 MA-S3 页的第一次 provider-request（16 段契约、7 个 allowed
detail、输出上限 8192）。反例全部在这份真实请求上构造：adapter 追加段落、重排段落、
缩小 detail scope、抬高输出上限，以及"repair 却没有冻结契约"。
"""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.page_contract_recheck import (
    ACTUAL_PAGE_CONTRACT_MISMATCH,
    capture_page_contract_snapshot,
    compare_actual_request_to_page_contract,
)

from . import incident_archive

INCIDENT_INVOCATION = incident_archive.INCIDENT_INVOCATION


def _snapshot():
    return capture_page_contract_snapshot(incident_archive.archive_root(), INCIDENT_INVOCATION)


def _payload() -> dict:
    snapshot = _snapshot()
    assert snapshot is not None
    request = json.loads(Path(snapshot.source_path).read_text(encoding="utf-8"))
    return json.loads(json.dumps(request["input_payload"]))


def _compare(payload: dict, **overrides):
    snapshot = _snapshot()
    kwargs = {
        "invocation_id": INCIDENT_INVOCATION,
        "payload": payload,
        "max_output_tokens": snapshot.max_output_tokens,
        "is_repair": False,
    }
    kwargs.update(overrides)
    return compare_actual_request_to_page_contract(snapshot, **kwargs)


def test_frozen_contract_matches_the_incident_page_facts() -> None:
    snapshot = _snapshot()
    assert snapshot is not None
    assert len(snapshot.paragraph_ids) == 16
    assert set(snapshot.paragraph_ids) == set(incident_archive.INCIDENT_PAGE_PARAGRAPH_IDS)
    assert len(snapshot.scope["allowed_detail_ids"]) == 7
    assert snapshot.max_output_tokens == 8192
    assert snapshot.source_path.startswith(str(incident_archive.archive_root()))


def test_frozen_request_order_is_lexical_not_narrative() -> None:
    """**已复现、待 PR C 修**：冻结请求里的段落顺序是字典序，不是计划的叙述顺序。

    审计 §C.1 要求 packing unit 携带"explicit narrative order"，§4 的 I5 要求实际请求的
    段落顺序与冻结 page contract 一致。事故归档里两者不同：请求先给 ``P10..P17`` 再给
    ``P1__f1, P3..P9``。本测试固定该事实，修好后应改为断言顺序等于叙述顺序。
    """

    snapshot = _snapshot()
    assert snapshot is not None
    assert list(snapshot.paragraph_ids) == sorted(snapshot.paragraph_ids), "当前是字典序"
    assert list(snapshot.paragraph_ids) != list(
        incident_archive.INCIDENT_PAGE_PARAGRAPH_IDS
    ), "与计划的叙述顺序不同（待修）"
    assert snapshot.paragraph_ids[0] == "MA-S3:P10"


def test_unchanged_request_passes_the_recheck() -> None:
    assert _compare(_payload()) == ()


def test_adapter_appending_paragraphs_is_rejected() -> None:
    """审计点名的反例：adapter 后来又追加 15 段，必须在发送前拒绝。"""

    payload = _payload()
    payload["narrative_plan"]["page_paragraph_ids"] = list(
        payload["narrative_plan"]["page_paragraph_ids"]
    ) + [f"MA-S3:EXTRA{n}" for n in range(15)]

    failures = _compare(payload, is_repair=True)
    assert failures == (
        f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:paragraph_ids:expected=16:actual=31",
    )


def test_reordering_paragraphs_is_rejected() -> None:
    payload = _payload()
    ids = list(payload["narrative_plan"]["page_paragraph_ids"])
    payload["narrative_plan"]["page_paragraph_ids"] = ids[1:] + ids[:1]

    failures = _compare(payload)
    assert failures and "paragraph_ids" in failures[0]


def test_shrinking_the_detail_scope_is_rejected() -> None:
    payload = _payload()
    payload["binding_contract"]["allowed_detail_ids"] = []

    failures = _compare(payload)
    assert failures == (f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:scope:allowed_detail_ids",)


def test_raising_the_output_cap_is_rejected() -> None:
    snapshot = _snapshot()
    failures = _compare(_payload(), max_output_tokens=snapshot.max_output_tokens + 1)
    assert failures == (
        f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:output_cap:"
        f"{snapshot.max_output_tokens + 1}>{snapshot.max_output_tokens}",
    )


def test_repair_without_a_frozen_contract_is_rejected() -> None:
    """repair 不比对 envelope：失去冻结契约就没有任何东西能证明它没被改页。"""

    failures = compare_actual_request_to_page_contract(
        None,
        invocation_id=INCIDENT_INVOCATION,
        payload=_payload(),
        is_repair=True,
    )
    assert failures == (f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:frozen_page_contract_missing",)
    # primary 由 envelope digest 兜底，因此没有持久化契约时不额外阻断。
    assert (
        compare_actual_request_to_page_contract(
            None, invocation_id=INCIDENT_INVOCATION, payload=_payload(), is_repair=False
        )
        == ()
    )


def test_snapshot_is_read_only_and_deterministic() -> None:
    root = incident_archive.archive_root()
    before = {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }
    first = _snapshot()
    second = _snapshot()
    after = {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert first == second


# --------------------------------------------------------------------------- #
# §C.1/§C.2：无 atom 的叙事段落也必须按同一候选页契约分页
# --------------------------------------------------------------------------- #


def test_narrative_only_section_is_paged_by_the_candidate_contract() -> None:
    """审计最小反例 A：7 个无 atom 作者段落 + 上限 6 → 不能仍是一张 header 页。"""

    from code2paper.agentic.method_architect import (
        NarrativeParagraphPlanV3,
        NarrativePlanV3,
        NarrativeSectionPlanV3,
        NarrativeUnitV1,
    )
    from code2paper.agentic.unified_context_compiler import (
        _max_semantic_paragraphs_per_page,
        build_consumer_workset_manifest_v2,
        extend_writer_worksets_from_narrative_plan,
    )
    from tests.test_agentic_unified_context_compiler import (
        _budget_envelope,
        _two_mechanism_fixture,
    )

    archive, obligations = _two_mechanism_fixture()
    envelope = _budget_envelope()

    paragraph_ids = tuple(f"MA-S9_p{index}" for index in range(1, 8))
    paragraphs = tuple(
        NarrativeParagraphPlanV3(
            paragraph_id=paragraph_id,
            section_id="MA-S9",
            role="motivation",
            mechanism_id="",
            required_detail_ids=(),
            witness_contract={
                "schema_version": "1.0",
                "paragraph_id": paragraph_id,
                "rhetorical_goal": "motivation",
                "targets": [],
            },
        )
        for paragraph_id in paragraph_ids
    )
    plan = NarrativePlanV3(
        plan_id="plan:narrative-only",
        sections=(
            NarrativeSectionPlanV3(
                section_id="MA-S9",
                heading="Motivation",
                mechanism_ids=(),
                paragraphs=paragraphs,
            ),
        ),
        narrative_units=(
            NarrativeUnitV1(
                unit_id="unit_motivation",
                section_id="MA-S9",
                mechanism_context_ids=(),
                rhetorical_role="motivation",
                reader_question="Why does this matter?",
                paragraph_ids=paragraph_ids,
                required_detail_ids=(),
                optional_detail_ids=(),
                formula_obligation_ids=(),
                suggested_depth="standard",
            ),
        ),
        context_set_digest=archive.content_digest,
    )

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

    pages = [page for page in writer_manifest.pages if "MA-S9" in str(page.mechanism_id)]
    assert pages, "该 section 必须产生页"
    limit = _max_semantic_paragraphs_per_page()
    assert limit > 0 and limit < len(paragraph_ids), "夹具必须超过候选页段数上限"
    assert len(pages) >= 2, "无 atom 的叙事段落也必须分页，而不是一张 header 页"

    landed: list[str] = []
    for page in pages:
        ids = list(page.technical_payload.get("paragraph_ids") or ())
        assert len(set(ids)) <= limit, f"单页段落数不得超过候选上限：{len(ids)} > {limit}"
        landed.extend(str(item) for item in ids)
    assert set(landed) == set(paragraph_ids), "分页不得丢段落"
    assert len(landed) == len(paragraph_ids), "分页不得重复段落"


def test_page_payload_preserves_the_narrative_paragraph_order() -> None:
    """§C.1 / I5：页内段落顺序是**叙述顺序**，不是字典序（事故里两者不同）。"""

    from code2paper.agentic.method_architect import (
        NarrativeParagraphPlanV3,
        NarrativePlanV3,
        NarrativeSectionPlanV3,
        NarrativeUnitV1,
    )
    from code2paper.agentic.unified_context_compiler import (
        build_consumer_workset_manifest_v2,
        extend_writer_worksets_from_narrative_plan,
    )
    from tests.test_agentic_unified_context_compiler import (
        _budget_envelope,
        _two_mechanism_fixture,
    )

    archive, obligations = _two_mechanism_fixture()
    envelope = _budget_envelope()

    # 故意构造"字典序 != 叙述顺序"的 id（事故里是 P10..P17 排在 P1__f1/P3..P9 之前）。
    paragraph_ids = ("MA-S9_p1__f1", "MA-S9_p3", "MA-S9_p10")
    assert list(paragraph_ids) != sorted(paragraph_ids), "夹具必须让两种顺序不同"

    paragraphs = tuple(
        NarrativeParagraphPlanV3(
            paragraph_id=paragraph_id,
            section_id="MA-S9",
            role="motivation",
            mechanism_id="",
            required_detail_ids=(),
            witness_contract={
                "schema_version": "1.0",
                "paragraph_id": paragraph_id,
                "rhetorical_goal": "motivation",
                "targets": [],
            },
        )
        for paragraph_id in paragraph_ids
    )
    plan = NarrativePlanV3(
        plan_id="plan:order",
        sections=(
            NarrativeSectionPlanV3(
                section_id="MA-S9",
                heading="Motivation",
                mechanism_ids=(),
                paragraphs=paragraphs,
            ),
        ),
        narrative_units=(
            NarrativeUnitV1(
                unit_id="unit_motivation",
                section_id="MA-S9",
                mechanism_context_ids=(),
                rhetorical_role="motivation",
                reader_question="Why does this matter?",
                paragraph_ids=paragraph_ids,
                required_detail_ids=(),
                optional_detail_ids=(),
                formula_obligation_ids=(),
                suggested_depth="standard",
            ),
        ),
        context_set_digest=archive.content_digest,
    )

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
    pages = [page for page in writer_manifest.pages if "MA-S9" in str(page.mechanism_id)]
    assert pages
    landed = [
        str(item)
        for page in pages
        for item in (page.technical_payload.get("paragraph_ids") or ())
    ]
    assert landed == list(paragraph_ids), "页内顺序必须是叙述顺序而不是字典序"


# --------------------------------------------------------------------------- #
# §C.2：段数上限的策略标注（0=关闭只能是显式实验配置）
# --------------------------------------------------------------------------- #


def test_paragraph_limit_policy_is_explicit_and_identity_bound() -> None:
    from code2paper.agentic.authoring_run_config import capture_effective_config_digest
    from code2paper.agentic.unified_context_compiler import (
        semantic_paragraph_limit_policy,
    )

    default = semantic_paragraph_limit_policy({})
    assert default["value"] > 0
    assert default["source"] == "default"
    assert default["disabled"] is False

    disabled = semantic_paragraph_limit_policy(
        {"CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE": "0"}
    )
    assert disabled["disabled"] is True
    assert disabled["experiment_acknowledged"] is False

    acknowledged = semantic_paragraph_limit_policy(
        {
            "CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE": "0",
            "CODE2PAPER_UNIFIED_PARAGRAPH_LIMIT_EXPERIMENT": "1",
        }
    )
    assert acknowledged["experiment_acknowledged"] is True

    invalid = semantic_paragraph_limit_policy(
        {"CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE": "not-a-number"}
    )
    assert invalid["valid"] is False, "非法值不得静默当作正常配置"

    # 策略进有效配置身份：环境变量不能在不改变身份的情况下改契约。
    base = capture_effective_config_digest(narrative_plan_mode="v3", environment={})
    changed = capture_effective_config_digest(
        narrative_plan_mode="v3",
        environment={"CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE": "0"},
    )
    assert base["digest"] != changed["digest"]
    assert base["payload"]["semantic_paragraph_limit"]["value"] > 0


def test_admission_blocks_an_unacknowledged_disabled_paragraph_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json as _json
    import subprocess as _subprocess

    from code2paper.agentic.live_admission_preflight import preflight_live_admission
    from code2paper.llm.client import LLMConfig, LLMProvider

    target = tmp_path / "target"
    (target / "src").mkdir(parents=True)
    (target / "src" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    for args in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "-m", "i"]):
        _subprocess.run(["git", *args], cwd=target, check=True, capture_output=True)
    intent = tmp_path / "intent.yaml"
    intent.write_text("title: demo\n", encoding="utf-8")

    monkeypatch.setenv("CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE", "0")
    monkeypatch.delenv("CODE2PAPER_UNIFIED_PARAGRAPH_LIMIT_EXPERIMENT", raising=False)
    blocked = preflight_live_admission(
        tmp_path / "run",
        repo_path=target,
        author_intent_path=intent,
        llm_config=LLMConfig(provider=LLMProvider.OPENAI, model="m"),
        run_open_mode="new",
    )
    assert blocked.ready is False
    assert "semantic_paragraph_limit_policy_unacknowledged" in blocked.blockers
    gate = next(
        g for g in blocked.gates if g.name == "semantic_paragraph_limit_policy"
    )
    assert gate.passed is False

    # 显式声明实验后不再是阻断项（仍记录在 policy 里）。
    monkeypatch.setenv("CODE2PAPER_UNIFIED_PARAGRAPH_LIMIT_EXPERIMENT", "1")
    acknowledged = preflight_live_admission(
        tmp_path / "run2",
        repo_path=target,
        author_intent_path=intent,
        llm_config=LLMConfig(provider=LLMProvider.OPENAI, model="m"),
        run_open_mode="new",
    )
    assert "semantic_paragraph_limit_policy_unacknowledged" not in acknowledged.blockers
    assert acknowledged.policy["semantic_paragraph_limit"]["experiment_acknowledged"] is True
    _json.dumps(acknowledged.model_dump(mode="json"))
