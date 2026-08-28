from __future__ import annotations

from code2paper.agentic.publication_method_writer import (
    _infer_used_claim_ids,
    _looks_like_caveat_shell,
    _section_body_truncated,
    _section_output_acceptable,
    _section_revision_budget,
    _strip_provenance_tokens,
    _writer_retry_failure_code,
)
from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1


def test_incomplete_last_clause_is_truncated() -> None:
    assert _section_body_truncated("Entities are extracted in")
    assert _section_body_truncated("Scores are passed to a")
    assert _section_body_truncated("动态剪枝从而防止")
    assert _section_body_truncated("The graph is $G_{tri")
    assert not _section_body_truncated("Entities are extracted in the index.")
    assert not _section_body_truncated("动态剪枝排除低于阈值的实体。")


def test_empty_repository_spec_is_a_caveat_shell() -> None:
    text = (
        "## First retrieval\n\n"
        "The operational specification is not provided in the repository."
    )
    assert _looks_like_caveat_shell(text)
    framework = (
        "## Embedding-based ranking formulation and overall framework.\n\n"
        "This section outlines the embedding-based ranking formulation and overall "
        "framework. No repository-supported method operations, formulas, or "
        "caveated propositions are currently authorized for this section. The "
        "available author-intent brief supplies only the organizational label "
        "without accompanying technical content."
    )
    assert _looks_like_caveat_shell(framework)


def test_retry_code_for_truncated_body() -> None:
    output = PublicationMethodSectionOutputV1(
        section_markdown="## Heading\n\nEntities are extracted in",
        heading_text="Heading",
    )
    assert _writer_retry_failure_code(output, expected_heading="Heading") == "section_body_truncated"
    assert not _section_output_acceptable(
        output.section_markdown,
        expected_heading="Heading",
    )


def test_strip_brief_story_tokens() -> None:
    text = "See `brief:story:O-ORGANIZATION-04` and O-STAGE-02 next."
    cleaned = _strip_provenance_tokens(text)
    assert "brief:story:" not in cleaned
    assert "O-STAGE-02" not in cleaned


def test_infer_used_claim_ids_from_overlap() -> None:
    class _Claims:
        claims = [
            type("C", (), {
                "claim_id": "c-activate",
                "canonical_text": "frontier expansion multiplies parent score by similarity",
            })(),
            type("C", (), {
                "claim_id": "c-other",
                "canonical_text": "damping factor initializes personalized pagerank",
            })(),
        ]

    used = _infer_used_claim_ids(
        "Frontier expansion multiplies the parent score by contextual similarity.",
        _Claims(),
        allowed_claim_ids={"c-activate", "c-other"},
    )
    assert "c-activate" in used
    assert "c-other" not in used


def test_infer_used_claim_ids_does_not_bleed_when_section_has_no_claims() -> None:
    class _Claims:
        claims = [
            type("C", (), {
                "claim_id": "c-ppr",
                "canonical_text": "personalized pagerank ranks passages on the entity graph",
            })(),
        ]

    used = _infer_used_claim_ids(
        "Personalized PageRank ranks passages on the entity graph.",
        _Claims(),
        allowed_claim_ids=set(),
    )
    assert used == []


def test_compact_authoring_packet_keeps_long_organization_seed() -> None:
    from code2paper.llm.section_writer import _compact_authoring_packet_for_llm

    seed = (
        "Interaction sequences use four heterogeneous signals: node identity, "
        "edge type, absolute temporal gap, and co-occurrence frequency. "
    ) * 12
    packet = _compact_authoring_packet_for_llm({
        "organization_seed": seed,
        "facets": [{
            "facet_id": "facet-1",
            "required": True,
            "semantic_fields": {
                "inputs": ["node", "edge", "time", "co-occurrence"],
                "transformation": "concat aligned encoding",
            },
        }],
    })
    assert "co-occurrence frequency" in packet["organization_seed"]
    assert len(packet["organization_seed"]) > 500
    assert "node" in packet["facets"][0]["gist"]


def test_compact_writer_view_keeps_long_brief_line() -> None:
    from code2paper.llm.section_writer import _compact_writer_view_for_llm

    line = (
        "The seed entity is the corpus entity with maximum cosine similarity "
        "to the query entity, and each selected sentence contributes a parent "
        "score multiplied by sentence-query similarity before pruning. "
    ) * 4
    compact = _compact_writer_view_for_llm({
        "purpose": {"heading": "Retrieval"},
        "positive_briefs": [{"brief_id": "b1", "licensed_wording": line}],
    })
    kept = compact["brief_one_liners"][0]["line"]
    assert len(kept) > 200
    assert kept == line[:800]


def test_paste_missing_formula_block_and_repair_text_command() -> None:
    from code2paper.agentic.publication_method_writer import (
        _paste_missing_formula_blocks,
        _prose_has_repeated_phrase_spam,
        _repair_writer_text_commands,
        _section_output_acceptable,
    )

    damaged = "A = ext{diag}(a_1)"
    assert "\\text{" in _repair_writer_text_commands(damaged)
    damaged_begin = "A = " + "\b" + "egin{aligned}"
    assert "\\begin{" in _repair_writer_text_commands(damaged_begin)
    pasted = _paste_missing_formula_blocks(
        "## Redesign\n\nThe update is intended.",
        [{"latex": r"h_{t+\Delta t} = e^{A\Delta t}h_t", "markdown_block": r"$$h_{t+\Delta t} = e^{A\Delta t}h_t$$"}],
    )
    assert r"$$h_{t+\Delta t} = e^{A\Delta t}h_t$$" in pasted
    skipped = _paste_missing_formula_blocks(
        "## Architecture\n\nFusion is pending.",
        [{"latex": "x + y", "markdown_block": "$$\nx + y\n$$"}],
    )
    assert "x + y" not in skipped

    heading = "Dynamic graph encoding: how interaction sequences are aligned"
    writer_body = (
        f"## {heading}\n\n"
        "The encoding uses four channels.\n\n"
        "### Dynamic Graph Encoding: Heterogeneous Feature Representation and Alignment\n\n"
        "This section details how raw interaction sequences are transformed into a "
        "unified, aligned feature representation. The core mechanism involves extracting "
        "the first-hop interaction sequence for a node and encoding it using four "
        "distinct heterogeneous signals: node identity, edge attributes, absolute "
        "temporal information, and co-occurrence frequency.\n\n"
        r"\mathbf{h}_i = \text{Concat}\left( \mathbf{W}_n \mathbf{x}_i^{(n)}, "
        r"\mathbf{W}_e \mathbf{x}_i^{(e)}, \mathbf{W}_t \mathbf{x}_i^{(t)}, "
        r"\mathbf{W}_c \mathbf{x}_i^{(c)} \right)"
        "\n"
    )
    package = {
        "latex": (
            r"\mathbf{h}_i = \text{Concat}\left( \mathbf{W}_n \mathbf{x}_i^{(n)}, "
            r"\mathbf{W}_e \mathbf{x}_i^{(e)}, \mathbf{W}_t \mathbf{x}_i^{(t)}, "
            r"\mathbf{W}_c \mathbf{x}_i^{(c)} \right)"
        ),
        "markdown_block": (
            "### Dynamic Graph Encoding: Heterogeneous Feature Representation and Alignment\n\n"
            "This section details how raw interaction sequences are transformed into a "
            "unified, aligned feature representation. The core mechanism involves extracting "
            "the first-hop interaction sequence for a node and encoding it using four "
            "distinct heterogeneous signals: node identity, edge attributes, absolute "
            "temporal information, and co-occurrence frequency.\n\n"
            "$$\n"
            r"\mathbf{h}_i = \text{Concat}\left( \mathbf{W}_n \mathbf{x}_i^{(n)}, "
            r"\mathbf{W}_e \mathbf{x}_i^{(e)}, \mathbf{W}_t \mathbf{x}_i^{(t)}, "
            r"\mathbf{W}_c \mathbf{x}_i^{(c)} \right)"
            "\n$$\n"
        ),
    }
    naive = writer_body.rstrip() + "\n\n" + package["markdown_block"] + "\n"
    repaired = _paste_missing_formula_blocks(writer_body, [package])
    assert repaired.count("### Dynamic Graph Encoding") == 1
    assert naive.count("### Dynamic Graph Encoding") == 2
    assert not _prose_has_repeated_phrase_spam(repaired)
    assert _section_output_acceptable(repaired, expected_heading=heading)

    math_only = _paste_missing_formula_blocks(
        "## Encoding\n\nThe encoder aligns heterogeneous channels before the state update.",
        [{
            "latex": r"h = Wx",
            "markdown_block": (
                "### Encoding formula\n\nThe encoder aligns channels.\n\n"
                "$$\nh = Wx\n$$\n"
            ),
        }],
    )
    assert "### Encoding formula" not in math_only
    assert "$$" in math_only
    assert "h = Wx" in math_only


def test_revision_budget_honors_zero(monkeypatch) -> None:
    monkeypatch.setenv("CODE2PAPER_SECTION_REVISION_BUDGET", "0")
    assert _section_revision_budget() == 0


def test_routing_conflict_rebinds_empty_first_retrieval_not_sibling() -> None:
    from code2paper.agentic.writer_view_projection import (
        rebound_stage_claims_for_routing_conflict,
    )

    l2 = type("C", (), {
        "claim_id": "l2-activate",
        "canonical_text": "Frontier expansion excludes scores below the threshold.",
        "claim_kind": "technical_semantic",
        "inference_level": "E2",
        "covers_obligation_ids": ["O-STAGE-02"],
        "parent_claim_ids": ["c-l0"],
    })()
    rebound, conflict = rebound_stage_claims_for_routing_conflict(
        heading="First retrieval: local activation via semantic bridging",
        bound_claim_ids=set(),
        claims_by_id={"l2-activate": l2},
        heading_to_claim_ids={
            "Motivation: revisit graph retrieval shortcomings": {"l2-activate"},
            "First retrieval: local activation via semantic bridging": set(),
            "Second retrieval: global rank aggregation": set(),
        },
    )
    assert conflict is True
    assert rebound[0].claim_id == "l2-activate"

    stolen, steal_conflict = rebound_stage_claims_for_routing_conflict(
        heading="First retrieval: local activation via semantic bridging",
        bound_claim_ids=set(),
        claims_by_id={"l2-activate": l2},
        heading_to_claim_ids={
            "First retrieval: local activation via semantic bridging": set(),
            "Offline construction of corpus units and adjacency": {"l2-activate"},
        },
    )
    assert steal_conflict is True
    assert stolen[0].claim_id == "l2-activate"

    ppr = type("C", (), {
        "claim_id": "l2-ppr",
        "canonical_text": "Personalized PageRank aggregates global passage rank.",
        "claim_kind": "technical_semantic",
        "inference_level": "E2",
        "covers_obligation_ids": ["O-STAGE-03"],
        "parent_claim_ids": ["c-ppr"],
    })()
    blocked, blocked_conflict = rebound_stage_claims_for_routing_conflict(
        heading="First retrieval: local activation via semantic bridging",
        bound_claim_ids=set(),
        claims_by_id={"l2-ppr": ppr},
        heading_to_claim_ids={
            "First retrieval: local activation via semantic bridging": set(),
            "Offline construction of corpus units and adjacency": {"l2-ppr"},
        },
    )
    assert blocked_conflict is False
    assert blocked == ()
