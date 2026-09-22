"""PR D / §D.4：Writer 可见字段的 golden contract 与材料 lineage。

审计要求：完整局部 statement、reader goal、authority、implementation status、支持
detail、unresolved disposition 必须**按权限**到达模型；技术事实继续来自 canonical
page，不在页内叙述合同里复制一份可能不一致的"精简事实"；并且要能回答"材料是未检索
到，还是在投影/合并中丢了"。
"""

from __future__ import annotations

from code2paper.agentic.intent_spine_models import AuthorIntentSurfaceV1
from code2paper.llm.section_writer import (
    _compact_writer_author_intent_surfaces_for_llm,
    _compact_writer_narrative_plan_for_llm,
    writer_paragraph_material_lineage,
)

GOLDEN_PARAGRAPH_FIELDS = {
    "paragraph_id",
    "section_id",
    "role",
    "paragraph_kind",
    "author_intent_surfaces",
    "surface_digest",
    "implementation_status",
    "unresolved_ids",
    "source_story_ids",
    "disposition",
    "mechanism_id",
    "required_detail_ids",
    "optional_detail_ids",
    "formula_obligation_ids",
    "formula_package_ids",
    "authority_surface",
    "required_author_surface_ids",
    "required_repository_proposition_ids",
    "suggested_depth",
    "reader_goal",
    "transition_from",
    "transition_to",
    "content_digest",
}

GOLDEN_SURFACE_FIELDS = {
    "surface_id",
    "story_node_id",
    "author_statement",
    "intended_role",
    "local_reader_goal",
    "authority_surface",
    "implementation_status",
    "supporting_detail_ids",
    "unresolved_points",
    "source_content_digest",
    "content_digest",
}


def _surface() -> AuthorIntentSurfaceV1:
    return AuthorIntentSurfaceV1(
        surface_id="surface:story:a",
        story_node_id="story:a",
        author_statement="The encoder adds document identity to passage embeddings.",
        intended_role="mechanism",
        local_reader_goal="How does the encoder carry document identity?",
        authority_surface="author_specification",
        implementation_status="unresolved",
        supporting_detail_ids=("detail:encoder:1",),
        unresolved_points=("obligation:identity",),
    )


def _page_local_plan_row() -> dict:
    surface = _surface()
    return {
        "paragraph_id": "MA-S1:P1",
        "section_id": "MA-S1",
        "role": "mechanism",
        "paragraph_kind": "grounded_content",
        "author_intent_surfaces": [surface],
        "surface_digest": surface.content_digest,
        "implementation_status": "supported",
        "unresolved_ids": ["obligation:identity"],
        "source_story_ids": ["story:a"],
        "disposition": "rendered_as_implementation_prose",
        "mechanism_id": "mech_sym:encoder",
        "required_detail_ids": ["detail:encoder:1"],
        "optional_detail_ids": ["detail:encoder:2"],
        "formula_obligation_ids": ["ob:one"],
        "formula_package_ids": ["pkg:one"],
        "authority_surface": "repository_statement",
        "required_author_surface_ids": ["surface:story:a"],
        "required_repository_proposition_ids": ["prop:one"],
        "suggested_depth": "standard",
        "reader_goal": "How does the encoder carry document identity?",
        "transition_from": "",
        "transition_to": "MA-S1:P2",
        "content_digest": "sha256:paragraph",
        # 技术事实属于 canonical page；这里出现也不得被复制到叙述合同。
        "atoms": [{"atom_id": "atom:encoder", "exact_excerpt": "def encode(...)"}],
        "shared_contexts": [{"context_id": "ctx:1", "exact_excerpt": "secret"}],
    }


def _page_local_plan() -> dict:
    return {
        "section_id": "MA-S1",
        "heading": "Encoder",
        "mechanism_ids": ["mech_sym:encoder"],
        "page_id": "page:abc",
        "page_paragraph_ids": ["MA-S1:P1"],
        "content_digest": "sha256:plan",
        "paragraphs": [_page_local_plan_row()],
        "shared_contexts": [{"context_id": "ctx:1", "exact_excerpt": "secret"}],
    }


def test_writer_paragraph_view_matches_the_golden_field_contract() -> None:
    compact = _compact_writer_narrative_plan_for_llm(_page_local_plan())
    assert set(compact) == {
        "section_id",
        "heading",
        "mechanism_ids",
        "page_id",
        "page_paragraph_ids",
        "content_digest",
        "paragraphs",
    }
    assert len(compact["paragraphs"]) == 1
    row = compact["paragraphs"][0]
    assert set(row) == GOLDEN_PARAGRAPH_FIELDS

    # 作者语义必须完整到达（不是只给 ID），并且权限/状态与来源同时可见。
    surface = row["author_intent_surfaces"][0]
    assert set(surface) == GOLDEN_SURFACE_FIELDS
    assert surface["author_statement"] == _surface().author_statement
    assert surface["local_reader_goal"] == _surface().local_reader_goal
    assert surface["authority_surface"] == "author_specification"
    assert surface["implementation_status"] == "unresolved"
    assert surface["supporting_detail_ids"] == ["detail:encoder:1"]
    assert surface["unresolved_points"] == ["obligation:identity"]
    assert row["authority_surface"] == "repository_statement"
    assert row["implementation_status"] == "supported"
    assert row["disposition"] == "rendered_as_implementation_prose"


def test_technical_material_is_not_copied_into_the_narrative_contract() -> None:
    """技术事实只来自 canonical page：叙述合同里不得再复制一份 excerpt。"""

    compact = _compact_writer_narrative_plan_for_llm(_page_local_plan())
    serialized = str(compact)
    assert "def encode(" not in serialized
    assert "exact_excerpt" not in serialized
    assert "ctx:1" not in serialized
    assert compact["paragraphs"][0]["required_detail_ids"] == ["detail:encoder:1"]


def test_material_lineage_distinguishes_missing_from_projected() -> None:
    plan = _page_local_plan()
    payload = {
        "detail_ids": ["detail:encoder:1"],
        "atoms": [{"_atom_id": "atom:encoder", "detail_id": "detail:encoder:2"}],
    }
    lineage = writer_paragraph_material_lineage(plan, payload)

    assert len(lineage) == 1
    row = lineage[0]
    assert row["paragraph_id"] == "MA-S1:P1"
    assert row["required_detail_ids"] == ["detail:encoder:1"]
    assert row["materialized_detail_ids"] == ["detail:encoder:1"]
    assert row["missing_detail_ids"] == []
    assert row["required_author_surface_ids"] == ["surface:story:a"]
    assert row["missing_author_surface_ids"] == []


def test_material_lineage_reports_details_lost_in_projection() -> None:
    plan = _page_local_plan()
    plan["paragraphs"][0]["required_author_surface_ids"] = [
        "surface:story:a",
        "surface:story:missing",
    ]
    lineage = writer_paragraph_material_lineage(plan, {"detail_ids": [], "atoms": []})

    assert lineage[0]["missing_detail_ids"] == ["detail:encoder:1"]
    assert lineage[0]["materialized_detail_ids"] == []
    assert lineage[0]["missing_author_surface_ids"] == ["surface:story:missing"]


def test_author_surface_compaction_keeps_content_and_authority() -> None:
    rows = _compact_writer_author_intent_surfaces_for_llm(_surface())
    assert len(rows) == 1
    assert set(rows[0]) == GOLDEN_SURFACE_FIELDS
