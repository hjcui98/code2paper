"""PR D / §D.1：authoring unit 合并必须无损、相邻、可冲突拒绝。

审计反例：``compile_authoring_units`` 的 merge 只拼接 story/slot/surface/argument/
intent/unresolved，**静默丢弃**了被合并单元的 optional detail、formula obligation 与
formula package；同时合并键只看 (kind, role, authority)，于是同 section 内相隔多个
槽位的同质单元会被跨段并回前面的单元，局部权限/status 也可能被抹平。
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from code2paper.agentic.intent_narrative_compiler import (
    _merge_units,
    compile_authoring_units,
)


def _detail(detail_id: str, *, digest: str = "") -> SimpleNamespace:
    payload = {
        "detail_id": detail_id,
        "primary_mechanism_id": "mech_alpha",
        "semantic_atom": f"step {detail_id}",
    }
    if digest:
        payload["content_digest"] = digest
    return SimpleNamespace(**payload)


def _slot(
    index: int,
    *,
    story_id: str,
    optional: tuple[SimpleNamespace, ...] = (),
    required: tuple[SimpleNamespace, ...] = (),
    obligations: tuple[str, ...] = (),
    packages: tuple[str, ...] = (),
    mechanism_id: str = "mech_alpha",
) -> dict:
    return {
        "slot_id": f"MA-S1:slot{index}",
        "section_id": "MA-S1",
        "story_id": story_id,
        "mechanism_id": mechanism_id,
        "required_details": list(required),
        "optional_details": list(optional),
        "formula_obligation_ids": list(obligations),
        "formula_package_ids": list(packages),
        "argument_unit_ids": [],
        "intent_atom_ids": [],
    }


def _story(
    story_id: str,
    *,
    role: str = "step_sequence",
    statement: str = "Why it matters",
    reader_question: str = "Why does this matter?",
    notes: tuple[str, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        story_node_id=story_id,
        title=statement,
        author_statement=statement,
        intended_role=role,
        reader_question=reader_question,
        notes=notes,
    )


def _compile(slots: list[dict], stories: tuple[SimpleNamespace, ...]):
    story_by_id = {story.story_node_id: story for story in stories}
    return compile_authoring_units(
        slots,
        section_id="MA-S1",
        story_by_id=story_by_id,
        binding_by_story={},
        surfaces_by_story={},
    )


def test_merge_keeps_optional_details_and_obligations() -> None:
    """最小反例：第二个可合并槽位携带的 optional/obligation 不得消失。

    （带 formula package 的槽位会被分类为 grounded_content 因而不参与合并；
    package 的无损合并由下面的 helper 级测试覆盖。）
    """

    stories = (_story("story:a"), _story("story:b"))
    slots = [
        _slot(1, story_id="story:a", optional=(_detail("d:first"),)),
        _slot(
            2,
            story_id="story:b",
            optional=(_detail("d:optional"),),
            obligations=("ob:one",),
        ),
    ]
    units = _compile(slots, stories)

    assert len(units) == 1, "相邻同质槽位应当合并"
    merged = units[0]
    assert [detail.detail_id for detail in merged.optional_details] == [
        "d:first",
        "d:optional",
    ]
    assert merged.formula_obligation_ids == ("ob:one",)
    assert merged.slot_ids == ("MA-S1:slot1", "MA-S1:slot2")

    trace = merged.as_trace()
    assert trace["optional_detail_ids"] == ["d:first", "d:optional"]
    assert trace["formula_obligation_ids"] == ["ob:one"]


def test_merge_is_refused_across_a_mechanism_ownership_boundary() -> None:
    """无归属槽位不得吸收/被吸收进有机制归属的槽位（机制所有权是边界）。"""

    stories = (_story("story:a"), _story("story:b"))
    slots = [
        _slot(1, story_id="story:a", mechanism_id=""),
        _slot(2, story_id="story:b", mechanism_id="mech_alpha"),
    ]
    units = _compile(slots, stories)

    assert len(units) == 2
    assert [unit.mechanism_ids for unit in units] == [(), ("mech_alpha",)]


def test_merge_does_not_reorder_units_across_an_intervening_slot() -> None:
    """A, B, A 形状：第三个单元不得跨过 B 并回第一个（相邻性）。"""

    stories = (
        _story("story:a", statement="First author statement"),
        # 无作者说明、无锚点 → structural_only，与两侧的 author_specification 不同键。
        _story("story:b", statement=""),
        _story("story:c", statement="Third author statement"),
    )
    slots = [
        _slot(1, story_id="story:a"),
        _slot(2, story_id="story:b"),
        _slot(3, story_id="story:c"),
    ]
    units = _compile(slots, stories)

    assert [unit.paragraph_kind for unit in units] == [
        "author_specification",
        "structural_only",
        "author_specification",
    ]
    assert [unit.slot_ids for unit in units] == [
        ("MA-S1:slot1",),
        ("MA-S1:slot2",),
        ("MA-S1:slot3",),
    ]


def test_merge_refuses_different_implementation_status() -> None:
    """同一 merge key、不同 implementation status：不合并（权限不得被抹平）。"""

    stories = (_story("story:a"), _story("story:b"))
    slots = [
        # optional detail 存在 → author_specification / partial
        _slot(1, story_id="story:a", optional=(_detail("d:optional"),)),
        # 无 optional、无可解释实现归属 → author_specification / unresolved
        _slot(2, story_id="story:b"),
    ]
    units = _compile(slots, stories)

    assert len(units) == 2, "status 不同必须保持两个单元"
    assert {unit.implementation_status for unit in units} == {"partial", "unresolved"}
    assert units[0].optional_details[0].detail_id == "d:optional"


def test_same_detail_id_with_different_content_is_a_conflict() -> None:
    """同 ID 不同内容：不得挑一个留下，必须保持单元分离。"""

    stories = (_story("story:a"), _story("story:b"))
    slots = [
        _slot(1, story_id="story:a", optional=(_detail("d:shared", digest="sha256:a"),)),
        _slot(2, story_id="story:b", optional=(_detail("d:shared", digest="sha256:b"),)),
    ]
    units = _compile(slots, stories)

    assert len(units) == 2
    assert {
        unit.optional_details[0].content_digest for unit in units
    } == {"sha256:a", "sha256:b"}


def test_same_detail_id_with_the_same_content_merges_once() -> None:
    stories = (_story("story:a"), _story("story:b"))
    shared = _detail("d:shared", digest="sha256:a")
    slots = [
        _slot(1, story_id="story:a", optional=(shared,)),
        _slot(2, story_id="story:b", optional=(_detail("d:shared", digest="sha256:a"),)),
    ]
    units = _compile(slots, stories)

    assert len(units) == 1
    assert [detail.detail_id for detail in units[0].optional_details] == ["d:shared"]


def test_required_promotion_is_not_a_silent_drop() -> None:
    """同一个 detail 一侧 required、一侧 optional：按 required 保留，不重复不丢弃。"""

    stories = (_story("story:a"), _story("story:b"))
    current = _compile([_slot(1, story_id="story:a")], stories)[0]
    incoming = _compile([_slot(1, story_id="story:b")], stories)[0]
    required_unit = _merge_units(
        current,
        type(incoming)(
            **{
                **incoming.__dict__,
                "required_details": (_detail("d:both", digest="sha256:x"),),
                "optional_details": (),
            }
        ),
    )
    merged = _merge_units(
        required_unit,
        type(incoming)(
            **{
                **incoming.__dict__,
                "required_details": (),
                "optional_details": (_detail("d:both", digest="sha256:x"),),
            }
        ),
    )

    assert [detail.detail_id for detail in merged.required_details] == ["d:both"]
    assert merged.optional_details == ()


def test_units_are_not_merged_when_the_reader_goal_differs() -> None:
    stories = (
        _story("story:a", reader_question="Why it matters"),
        _story("story:b", reader_question="How it works"),
    )
    slots = [
        _slot(1, story_id="story:a"),
        _slot(2, story_id="story:b"),
    ]
    units = _compile(slots, stories)

    assert len(units) == 2
    assert {unit.local_reader_goal for unit in units} == {
        "Why it matters",
        "How it works",
    }


def test_same_surface_id_with_different_content_blocks_the_merge() -> None:
    from code2paper.agentic.intent_narrative_compiler import _unit_merge_conflicts
    from code2paper.agentic.intent_spine_models import AuthorIntentSurfaceV1

    first = AuthorIntentSurfaceV1(
        surface_id="surface:shared",
        story_node_id="story:a",
        author_statement="First statement",
    )
    second = AuthorIntentSurfaceV1(
        surface_id="surface:shared",
        story_node_id="story:b",
        author_statement="Second statement",
    )
    assert first.content_digest != second.content_digest, "夹具必须让同 ID 内容不同"

    stories = (_story("story:a"), _story("story:b"))
    left = _compile([_slot(1, story_id="story:a")], stories)[0]
    right = _compile([_slot(1, story_id="story:b")], stories)[0]
    conflicts = _unit_merge_conflicts(
        replace(left, surfaces=(first,)), replace(right, surfaces=(second,))
    )

    assert "surface_conflict:surface:shared" in conflicts
    # 同 ID 同内容则不是冲突：可以合并。
    assert (
        _unit_merge_conflicts(
            replace(left, surfaces=(first,)), replace(right, surfaces=(first,))
        )
        == ()
    )


@pytest.mark.parametrize("field", ["required_details", "optional_details"])
def test_merge_helper_never_drops_detail_lists(field: str) -> None:
    stories = (_story("story:a"), _story("story:b"))
    current = _compile([_slot(1, story_id="story:a")], stories)[0]
    incoming = _compile([_slot(1, story_id="story:b")], stories)[0]
    detail = _detail("d:kept", digest="sha256:kept")
    merged = _merge_units(
        current,
        type(incoming)(**{**incoming.__dict__, field: (detail,)}),
    )
    assert [item.detail_id for item in getattr(merged, field)] == ["d:kept"]


def test_merge_helper_keeps_formula_obligations_and_packages() -> None:
    stories = (_story("story:a"), _story("story:b"))
    current = _compile([_slot(1, story_id="story:a")], stories)[0]
    incoming = _compile([_slot(1, story_id="story:b")], stories)[0]
    merged = _merge_units(
        type(current)(
            **{
                **current.__dict__,
                "formula_obligation_ids": ("ob:first",),
                "formula_package_ids": ("pkg:first",),
            }
        ),
        type(incoming)(
            **{
                **incoming.__dict__,
                "formula_obligation_ids": ("ob:second", "ob:first"),
                "formula_package_ids": ("pkg:second",),
            }
        ),
    )

    assert merged.formula_obligation_ids == ("ob:first", "ob:second")
    assert merged.formula_package_ids == ("pkg:first", "pkg:second")


def test_homogeneous_empty_slots_record_the_goals_they_unified() -> None:
    """同形空槽（unresolved）可以折叠成一段，但其它 reader goal 必须进 trace。"""

    notes = ("kind=stage", "priority=must_cover")
    stories = (
        _story("story:a", reader_question="How does setup A work?", notes=notes),
        _story("story:b", reader_question="How does setup B work?", notes=notes),
    )
    units = _compile(
        [_slot(1, story_id="story:a"), _slot(2, story_id="story:b")], stories
    )

    assert len(units) == 1, "无实现材料的同形槽位仍应折叠"
    merged = units[0]
    assert merged.paragraph_kind == "unresolved"
    assert merged.local_reader_goal == "How does setup A work?"
    assert merged.merged_local_reader_goals == ("How does setup B work?",)
    assert merged.as_trace()["merged_local_reader_goals"] == ["How does setup B work?"]

    # 有实现材料/作者主张的单元即使同键也不因 goal 不同而合并。
    prose_stories = (
        _story("story:c", reader_question="Why it matters"),
        _story("story:d", reader_question="How it works"),
    )
    prose_units = _compile(
        [_slot(1, story_id="story:c"), _slot(2, story_id="story:d")], prose_stories
    )
    assert len(prose_units) == 2
    assert all(not unit.merged_local_reader_goals for unit in prose_units)
