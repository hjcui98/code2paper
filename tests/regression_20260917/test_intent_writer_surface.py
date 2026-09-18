"""WP2：作者意图真正到达 Writer 表面（方案 §6、§12）。

事故事实：15 个槽位在 Writer 请求里只有相同的 section 级 reader_goal、空证据、
`role=step_sequence`，没有各自的作者语义。这里验证修复后的编译与投影行为，
并把"改作者说明必须改指纹"钉死。
"""

from __future__ import annotations

from types import SimpleNamespace

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
