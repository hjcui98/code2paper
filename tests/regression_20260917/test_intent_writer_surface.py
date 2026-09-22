"""WP2：作者意图真正到达 Writer 表面（方案 §6、§12）。

事故事实：15 个槽位在 Writer 请求里只有相同的 section 级 reader_goal、空证据、
`role=step_sequence`，没有各自的作者语义。这里验证修复后的编译与投影行为，
并把"改作者说明必须改指纹"钉死。
"""

from __future__ import annotations

from types import SimpleNamespace

from code2paper.agentic.intent_spine_models import AuthorIntentSurfaceV1
from code2paper.agentic.intent_narrative_compiler import (
    _slot_binding_decision,
    build_intent_narrative_plan_v4,
    compile_author_intent_surfaces,
    compile_intent_content_digest,
    project_intent_plan_to_narrative_v3,
)
from code2paper.llm.section_writer import _compact_writer_narrative_plan_for_llm


def _story(
    story_id: str,
    statement: str,
    *,
    role: str = "algorithm_step",
    priority: str = "must_cover",
    kind: str = "stage",
    claims: tuple[str, ...] = (),
    obligations: tuple[str, ...] = (),
) -> SimpleNamespace:
    notes = [f"kind={kind}"] + ([f"priority={priority}"] if priority else [])
    return SimpleNamespace(
        story_node_id=story_id,
        title=statement,
        author_statement=statement,
        intended_role=role,
        notes=tuple(notes),
        linked_claim_ids=claims,
        linked_obligation_ids=obligations,
        source_refs=(),
        reader_question=f"How does this setup realize {statement}?",
    )


def _prior_plan(section_rows: list[dict[str, object]]) -> SimpleNamespace:
    return SimpleNamespace(
        sections=[
            SimpleNamespace(
                section_id=row["section_id"],
                heading=row["heading"],
                argument_unit_ids=tuple(row.get("argument_unit_ids") or ()),
                reader_question=row["heading"],
            )
            for row in section_rows
        ],
        argument_units=[],
    )


def _incident_shaped_inputs() -> tuple[tuple[SimpleNamespace, ...], SimpleNamespace]:
    """复刻事故形状：15 个无材料 must-cover 槽 + 1 个有证据的 grounded 槽。"""

    stories = [
        _story(
            "story:grounded",
            "The encoder adds document identity to passage embeddings.",
            claims=("claim:doc",),
        ),
        *[
            _story(f"story:empty-{index}", f"Architecture detail number {index}.")
            for index in range(1, 16)
        ],
    ]
    contexts = SimpleNamespace(
        contexts=(
            SimpleNamespace(
                mechanism_id="mech_sym:encoder",
                mechanism_name="Encoder",
                story_node_ids=(),
                details=(
                    SimpleNamespace(
                        detail_id="detail:encoder:1",
                        primary_mechanism_id="mech_sym:encoder",
                        importance="core",
                        publication_policy="clean_candidate",
                        active_path_status="active_default",
                        source_claim_ids=("claim:doc",),
                    ),
                ),
                evidence_closure=SimpleNamespace(
                    fact_ids=(),
                    claim_ids=("claim:doc",),
                    equation_ids=(),
                    exact_span_ids=(),
                    seed_obligation_ids=(),
                ),
            ),
        )
    )
    return tuple(stories), contexts


def test_empty_slots_do_not_become_grounded_paragraphs() -> None:
    stories, contexts = _incident_shaped_inputs()
    prior = _prior_plan([
        {"section_id": "MA-S1", "heading": "Motivation", "argument_unit_ids": ()},
        {"section_id": "MA-S2", "heading": "Architecture", "argument_unit_ids": ()},
    ])
    plan, _bindings, trace = build_intent_narrative_plan_v4(
        story_spine=stories, prior_plan=prior, contexts=contexts
    )

    counts = trace["unit_kind_counts"]
    assert counts["grounded_content"] == 1, trace["units"]
    # 15 个同形空槽被合并为一个受限作者描述单元，而不是 15 个"必须补正文"的段落。
    assert counts["unresolved"] + counts["author_specification"] + counts["expository_bridge"] <= 2

    paragraphs = [p for section in plan.sections for p in section.paragraphs]
    grounded = [p for p in paragraphs if p.paragraph_kind == "grounded_content"]
    assert len(grounded) == 1
    assert grounded[0].required_detail_ids == ("detail:encoder:1",)
    assert grounded[0].authority_surface == "repository_statement"
    for paragraph in paragraphs:
        if paragraph.paragraph_kind == "grounded_content":
            continue
        # 非 grounded 段落绝不能声称仓库实现事实，也不能带必需 detail。
        assert paragraph.authority_surface != "repository_statement"
        assert paragraph.required_detail_ids == ()
        assert paragraph.disposition


def test_every_story_has_an_auditable_disposition() -> None:
    stories, contexts = _incident_shaped_inputs()
    prior = _prior_plan([
        {"section_id": "MA-S1", "heading": "Motivation", "argument_unit_ids": ()},
        {"section_id": "MA-S2", "heading": "Architecture", "argument_unit_ids": ()},
    ])
    _plan, _bindings, trace = build_intent_narrative_plan_v4(
        story_spine=stories, prior_plan=prior, contexts=contexts
    )

    covered = {
        story_id
        for unit in trace["units"]
        for story_id in unit["source_story_ids"]
    }
    assert covered == {story.story_node_id for story in stories}
    for unit in trace["units"]:
        assert unit["disposition"], unit
        assert unit["paragraph_kind"] in {
            "grounded_content",
            "author_specification",
            "expository_bridge",
            "structural_only",
            "unresolved",
        }


def test_request_surface_carries_local_author_content() -> None:
    stories, contexts = _incident_shaped_inputs()
    prior = _prior_plan([
        {"section_id": "MA-S1", "heading": "Motivation", "argument_unit_ids": ()},
        {"section_id": "MA-S2", "heading": "Architecture", "argument_unit_ids": ()},
    ])
    plan, _bindings, _trace = build_intent_narrative_plan_v4(
        story_spine=stories, prior_plan=prior, contexts=contexts
    )
    projected = project_intent_plan_to_narrative_v3(plan)

    section = next(item for item in projected.sections if item.section_id == "MA-S2")
    page_plan = {
        "section_id": section.section_id,
        "paragraphs": [
            paragraph.model_dump(mode="json") for paragraph in section.paragraphs
        ],
    }
    compact = _compact_writer_narrative_plan_for_llm(page_plan)

    assert compact["paragraphs"], "Writer 表面不得为空"
    for row in compact["paragraphs"]:
        assert row["paragraph_kind"]
        assert row["disposition"]
        assert row["implementation_status"]
        surfaces = row.get("author_intent_surfaces") or []
        assert surfaces, row
        for surface in surfaces:
            # 实际作者说明与权限必须到达模型，而不是只有 ID。
            assert surface["author_statement"].strip()
            assert surface["authority_surface"]
            assert surface["implementation_status"]
            assert surface["local_reader_goal"].strip()


def test_intent_digest_tracks_statement_with_stable_ids() -> None:
    first = (_story("story:a", "The encoder averages the training loss."),)
    second = (_story("story:a", "The encoder sums the training loss per batch."),)

    surfaces_first = compile_author_intent_surfaces(first)
    surfaces_second = compile_author_intent_surfaces(second)
    assert set(surfaces_first) == set(surfaces_second) == {"story:a"}
    assert (
        surfaces_first["story:a"].content_digest
        != surfaces_second["story:a"].content_digest
    )
    assert compile_intent_content_digest(first) != compile_intent_content_digest(second)

    prior = _prior_plan([{"section_id": "MA-S1", "heading": "Motivation", "argument_unit_ids": ()}])
    plan_first, _, _ = build_intent_narrative_plan_v4(story_spine=first, prior_plan=prior)
    plan_second, _, _ = build_intent_narrative_plan_v4(story_spine=second, prior_plan=prior)
    assert plan_first.source_intent_digest_version == "intent-content-v2"
    assert plan_first.source_intent_digest != plan_second.source_intent_digest
    assert plan_first.content_digest != plan_second.content_digest
    # 段落身份不变，但页内语义指纹必须改变。
    assert (
        plan_first.sections[0].paragraphs[0].paragraph_id
        == plan_second.sections[0].paragraphs[0].paragraph_id
    )
    assert (
        plan_first.sections[0].paragraphs[0].surface_digest
        != plan_second.sections[0].paragraphs[0].surface_digest
    )


def test_zero_overlap_is_organizational_fallback_only() -> None:
    slots = [
        {"slot_id": "MA-S1:slot1", "story_handles": {"claim:a"}},
        {"slot_id": "MA-S1:slot2", "story_handles": {"claim:b"}},
    ]
    decision = _slot_binding_decision(slots, {"claim:unrelated"})
    assert decision.slot_id == "MA-S1:slot1"
    assert decision.status == "organizational_fallback"
    assert decision.overlap_ids == ()
    assert decision.needs_research is True

    grounded = _slot_binding_decision(slots, {"claim:b"})
    assert grounded.slot_id == "MA-S1:slot2"
    assert grounded.status == "grounded"
    assert grounded.overlap_ids == ("claim:b",)
    assert grounded.needs_research is False


def test_must_cover_unresolved_story_stays_unresolved_not_repository_claim() -> None:
    stories = (
        _story("story:no-owner", "Document identity is added to passages.", kind="stage"),
    )
    contexts = SimpleNamespace(contexts=())
    prior = _prior_plan([{"section_id": "MA-S1", "heading": "Motivation", "argument_unit_ids": ()}])
    plan, _bindings, trace = build_intent_narrative_plan_v4(
        story_spine=stories, prior_plan=prior, contexts=contexts
    )
    paragraph = plan.sections[0].paragraphs[0]
    assert paragraph.paragraph_kind == "unresolved"
    assert paragraph.authority_surface != "repository_statement"
    assert paragraph.implementation_status == "unresolved"
    assert paragraph.unresolved_ids
    assert "story:no-owner" in trace["unresolved_story_ids"]


# --------------------------------------------------------------------------- #
# §D.2：owner 选择必须经过 binding decision；叙事适配与代码支持分两条轴
# --------------------------------------------------------------------------- #


def _zero_overlap_inputs(*, publication_policy: str) -> tuple[tuple[SimpleNamespace, ...], SimpleNamespace]:
    story = _story("story:author-only", "The encoder adds document identity.")
    contexts = SimpleNamespace(contexts=(
        SimpleNamespace(
            mechanism_id="mech_sym:encoder",
            mechanism_name="Encoder",
            story_node_ids=(),
            details=(
                SimpleNamespace(
                    detail_id="detail:orphan",
                    primary_mechanism_id="mech_sym:encoder",
                    importance="core",
                    publication_policy=publication_policy,
                    active_path_status="active_default",
                    evidence_authority="repository_verified",
                    source_claim_ids=("claim:elsewhere",),
                ),
            ),
            evidence_closure=SimpleNamespace(
                fact_ids=(), claim_ids=("claim:elsewhere",), equation_ids=(),
                exact_span_ids=(), seed_obligation_ids=(),
            ),
        ),
    ))
    return (story,), contexts


def test_zero_overlap_required_detail_becomes_a_typed_gap_but_keeps_coverage() -> None:
    stories, contexts = _zero_overlap_inputs(publication_policy="clean_candidate")
    prior = _prior_plan([{"section_id": "MA-S1", "heading": "Architecture", "argument_unit_ids": ()}])
    plan, _bindings, trace = build_intent_narrative_plan_v4(
        story_spine=stories, prior_plan=prior, contexts=contexts
    )

    gaps = [
        entry for entry in trace["typed_binding_gaps"] if entry["id"] == "detail:orphan"
    ]
    assert gaps, "零 overlap 的 required detail 必须留下 typed gap/replan 记录"
    assert gaps[0]["kind"] == "required_detail"
    assert gaps[0]["reason"] == "no_story_overlap"
    assert gaps[0]["requested_action"] == "bounded_planner_or_research"

    decisions = [
        entry
        for entry in trace["binding_decisions"]
        if entry["subject_id"] == "detail:orphan"
    ]
    assert decisions and decisions[0]["narrative_binding"] == "organizational_fallback"
    # 两条轴分开：叙事适配不确定，不代表代码支持缺失（也不把它升级成作者主张）。
    assert decisions[0]["evidence_authority"] == "repository_verified"

    # coverage 不丢：detail 仍在某个段落里，但不被写成"仓库已验证实现"。
    carried = [
        paragraph
        for section in plan.sections
        for paragraph in section.paragraphs
        if paragraph.required_detail_ids
    ]
    assert [paragraph.required_detail_ids for paragraph in carried] == [
        ("detail:orphan",)
    ]
    assert carried[0].authority_surface != "repository_statement", (
        "组织落位不得把段落升级为仓库实现主张"
    )
    assert "detail:orphan" in trace["required_detail_binding_fallback_ids"]


def test_zero_overlap_optional_detail_is_kept_in_context_not_forced() -> None:
    stories, contexts = _zero_overlap_inputs(publication_policy="annotated_only")
    prior = _prior_plan([{"section_id": "MA-S1", "heading": "Architecture", "argument_unit_ids": ()}])
    _plan, _bindings, trace = build_intent_narrative_plan_v4(
        story_spine=stories, prior_plan=prior, contexts=contexts
    )

    assert trace["typed_binding_gaps"] == [], "optional 材料不是 required gap"
    assert trace["optional_detail_binding_fallback_ids"] == ["detail:orphan"]
    assert trace["detail_binding_fallback_ids"] == ["detail:orphan"]


def test_production_path_calls_the_binding_decision(monkeypatch) -> None:
    """真实接线：plan 编译必须真的进入 _slot_binding_decision（不是只 import）。"""

    from code2paper.agentic import intent_narrative_compiler as compiler

    calls: list[tuple[str, ...]] = []
    real = compiler._slot_binding_decision

    def _spy(slots, handles):
        calls.append(tuple(sorted(handles)))
        return real(slots, handles)

    monkeypatch.setattr(compiler, "_slot_binding_decision", _spy)
    stories, contexts = _incident_shaped_inputs()
    prior = _prior_plan([{"section_id": "MA-S1", "heading": "Architecture", "argument_unit_ids": ("AU-1",)}])
    build_intent_narrative_plan_v4(story_spine=stories, prior_plan=prior, contexts=contexts)

    assert calls, "生产路径必须调用绑定决策"
    assert any("claim:doc" in call for call in calls)


# --------------------------------------------------------------------------- #
# §D.3：局部指纹与 sealed 模型更新
# --------------------------------------------------------------------------- #


def test_reader_question_changes_the_intent_digest() -> None:
    """reader_question 被消费成段落 reader_goal，只改它也必须改指纹。"""

    base = [_story("story:a", "The encoder adds document identity.")]
    changed = [
        SimpleNamespace(
            **{
                **base[0].__dict__,
                "reader_question": "Which tensor carries the identity signal?",
            }
        )
    ]
    assert compile_intent_content_digest(base) != compile_intent_content_digest(changed)


def test_surface_status_update_rebuilds_the_sealed_digest() -> None:
    from code2paper.agentic.intent_narrative_compiler import _surface_with_status

    surface = compile_author_intent_surfaces(
        [_story("story:a", "The encoder adds document identity.")]
    )["story:a"]
    assert surface.implementation_status == "unresolved"

    # model_copy 绕过 validator：digest 停在旧内容上（这正是审计 §D.3 的反例）。
    stale = surface.model_copy(update={"implementation_status": "supported"})
    assert stale.content_digest == surface.content_digest
    assert stale.implementation_status == "supported"

    # 重建并验证：digest 与"同字段重新构造"的 surface 完全一致。
    rebuilt = _surface_with_status(surface, "supported")
    fresh = AuthorIntentSurfaceV1.model_validate(
        {**surface.model_dump(mode="json", exclude={"content_digest"}),
         "implementation_status": "supported"}
    )
    assert rebuilt.content_digest == fresh.content_digest
    assert rebuilt.content_digest != surface.content_digest


def test_unit_surfaces_are_rebuilt_with_the_slot_status() -> None:
    """生产路径：unit 的 surface 必须重建验证，而不是带旧 digest 的 model_copy。"""

    from code2paper.agentic.intent_narrative_compiler import (
        compile_author_intent_surfaces,
        compile_authoring_units,
    )

    story = _story("story:grounded", "The encoder adds document identity.", claims=("claim:doc",))
    base = compile_author_intent_surfaces([story])["story:grounded"]
    assert base.implementation_status == "unresolved"

    slot = {
        "slot_id": "MA-S1:slot1",
        "story_id": "story:grounded",
        "mechanism_id": "mech_sym:encoder",
        "required_details": [
            SimpleNamespace(
                detail_id="detail:encoder:1",
                publication_policy="clean_candidate",
                active_path_status="active_default",
            )
        ],
        "optional_details": [],
        "argument_unit_ids": [],
        "intent_atom_ids": [],
        "formula_obligation_ids": [],
        "formula_package_ids": [],
    }
    units = compile_authoring_units(
        [slot],
        section_id="MA-S1",
        story_by_id={"story:grounded": story},
        binding_by_story={"story:grounded": SimpleNamespace(binding_status="exact")},
        surfaces_by_story={"story:grounded": base},
    )

    assert len(units) == 1
    surface = units[0].surfaces[0]
    assert surface.implementation_status == "supported"
    fresh = AuthorIntentSurfaceV1.model_validate(
        {
            **base.model_dump(mode="json", exclude={"content_digest"}),
            "implementation_status": "supported",
        }
    )
    assert surface.content_digest == fresh.content_digest, (
        "unit 的 surface 必须按新 status 重新验证；带旧 digest 的 model_copy 会在这里失败"
    )
    assert surface.content_digest != base.content_digest


def test_paragraph_surface_digest_follows_the_rebuilt_surface() -> None:
    """端到端：status 更新后段落 surface_digest 不得停留在旧摘要。"""

    stories = (
        _story("story:grounded", "The encoder adds document identity.", claims=("claim:doc",)),
    )
    contexts = SimpleNamespace(contexts=(
        SimpleNamespace(
            mechanism_id="mech_sym:encoder",
            mechanism_name="Encoder",
            story_node_ids=(),
            details=(
                SimpleNamespace(
                    detail_id="detail:encoder:1",
                    primary_mechanism_id="mech_sym:encoder",
                    importance="core",
                    publication_policy="clean_candidate",
                    active_path_status="active_default",
                    source_claim_ids=("claim:doc",),
                ),
            ),
            evidence_closure=SimpleNamespace(
                fact_ids=(), claim_ids=("claim:doc",), equation_ids=(),
                exact_span_ids=(), seed_obligation_ids=(),
            ),
        ),
    ))
    prior = _prior_plan([{"section_id": "MA-S1", "heading": "Architecture", "argument_unit_ids": ()}])
    plan, _bindings, _trace = build_intent_narrative_plan_v4(
        story_spine=stories, prior_plan=prior, contexts=contexts
    )

    paragraph = next(
        item for section in plan.sections for item in section.paragraphs
        if item.author_intent_surfaces
    )
    surface = paragraph.author_intent_surfaces[0]
    assert surface.content_digest == AuthorIntentSurfaceV1.model_validate(
        surface.model_dump(mode="json")
    ).content_digest, "surface 必须是可重建验证的 sealed 对象"
    assert paragraph.surface_digest == _surface_digest_of(paragraph)


def _surface_digest_of(paragraph) -> str:
    from code2paper.agentic.intent_spine_models import _digest

    return _digest([item.content_digest for item in paragraph.author_intent_surfaces])
