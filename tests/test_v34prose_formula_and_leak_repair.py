"""P0–P3 Candidate display-math, academic formula visibility, and leak repairs."""

from __future__ import annotations

from types import SimpleNamespace

from code2paper.agentic.formalization_agent import SectionFormulaPackageV1
from code2paper.agentic.method_proposition_provider import candidate_qualifier_phrase
from code2paper.agentic.publication_method_writer import (
    _normalize_writer_representation_noise,
    _restore_inline_formula_display_math,
    _rewrite_transaction_has_cluster_gain,
    _writer_visible_formula_packages,
)
from code2paper.agentic.publication_quality import _phrase_present
from code2paper.authoring.writer_skill import PublicationMethodWriterSkillV1
from code2paper.llm.section_writer import _is_implementation_trace_text
from code2paper.llm.section_writer import (
    normalize_publication_heading,
    project_operation_to_reader_surface,
)


def test_normalize_preserves_display_math_delimiters() -> None:
    text = (
        "The loss is\n"
        "$$\n"
        r"loss_i = -pos_sim + \operatorname{logsumexp}(all_sims, dim=0)"
        "\n$$\n"
        "and then reduced."
    )
    normalized = _normalize_writer_representation_noise(text)
    assert "$$" in normalized
    assert "loss_i = -pos_sim" in normalized


def test_normalize_still_strips_empty_inline_math() -> None:
    assert "$ $" not in _normalize_writer_representation_noise("keep $ $ this")


def test_restore_wraps_unique_inline_latex_as_display_math() -> None:
    latex = r"loss_i = -pos_sim + \operatorname{logsumexp}(all_sims, dim=0)"
    restored = _restore_inline_formula_display_math(
        f"The per-example loss is {latex}.",
        ({
            "package_id": "opfp:MA-S4:1",
            "latex": latex,
            "markdown_block": f"$$\n{latex}\n$$",
        },),
    )
    assert f"$$\n{latex}\n$$" in restored


def test_writer_visible_packages_include_author_intent_academic() -> None:
    academic = SectionFormulaPackageV1(
        package_id="pkg-MA-S1-01",
        section_id="MA-S1",
        purpose="Pad and stack interaction sequences.",
        latex=r"\mathbf{S}_{src} = \text{Pad}(\mathbf{N}_{src})",
        prose_explanation="Source sequences are padded.",
        symbol_definitions=(("S_src", "padded source sequence"),),
        authority_status="author_intent",
        bound_fact_ids=(),
        bound_equation_ids=(),
    )
    visible = _writer_visible_formula_packages(
        SimpleNamespace(packages=(academic,))
    )
    assert len(visible) == 1
    assert visible[0]["package_id"] == "pkg-MA-S1-01"
    assert visible[0]["placeholder"] == "[[FORMULA:pkg-MA-S1-01]]"


def test_writer_visible_packages_still_exclude_mismatch() -> None:
    mismatch = SectionFormulaPackageV1(
        package_id="fp:bad",
        section_id="MA-S1",
        purpose="Unverified expression.",
        latex="L = invented",
        prose_explanation="Not bound to code.",
        symbol_definitions=(),
        authority_status="paper_code_mismatch",
        bound_fact_ids=(),
        bound_equation_ids=(),
    )
    visible = _writer_visible_formula_packages(
        SimpleNamespace(packages=(mismatch,))
    )
    assert visible == ()


def test_candidate_qualifier_phrase_drops_self_cfg() -> None:
    phrase = candidate_qualifier_phrase("self.cfg.add_positional_encoding")
    assert "self." not in phrase
    assert "positional encoding" in phrase
    assert _phrase_present(
        "Similarity is computed when positional encoding is enabled.",
        "self.cfg.add_positional_encoding",
    )


def test_implementation_trace_filters_case_study_and_ner_skip() -> None:
    assert _is_implementation_trace_text("i == 0 and case_study")
    assert _is_implementation_trace_text("ent.label_ == 'ORDINAL' or ent.label_ == 'CARDINAL'")
    assert _is_implementation_trace_text("logger.info", "precompute sparse")
    assert not _is_implementation_trace_text(
        "personalized PageRank over the passage-entity subgraph"
    )


def test_method_language_style_gain_accepts_restored_display_math() -> None:
    incumbent = {
        "validation_status": "failed",
        "validation_counts": (1, 0, -3),
        "style_issue_count": 2,
        "missing_propositions": 0,
        "leakage_count": 0,
        "formula_missing_count": 1,
    }
    candidate = dict(incumbent, formula_missing_count=0)
    ok, reason = _rewrite_transaction_has_cluster_gain(
        incumbent, candidate, cluster_name="method_language_style",
    )
    assert ok is True
    assert reason == "monotonic_cluster_gain"


def test_writer_skill_1_15_forbids_code_equations_and_self_cfg_bindings() -> None:
    skill = PublicationMethodWriterSkillV1()
    assert skill.version == "1.15"
    joined = " ".join(skill.style_rules) + "\n" + skill.system_prompt()
    assert "[[FORMULA:<package_id>]]" in joined
    assert "positions * div_term" not in joined
    assert "parenthetical backtick binding" not in joined
    assert "not yet fixed" in joined
    assert "case-study debug branches" in joined


def test_formula_package_canonicalizes_markdown_block_to_display_math_only() -> None:
    from code2paper.agentic.formalization_agent import canonical_formula_markdown_block

    latex = r"\dot{h}(t) = A h(t) + B(t) x(t)"
    package = SectionFormulaPackageV1(
        package_id="pkg-memo",
        section_id="MA-S5",
        purpose="Define the continuous state update.",
        latex=latex,
        markdown_block=(
            "### SSM Core\n\n"
            f"$$\n{latex}\n$$\n\n"
            "**Symbol Definitions:**\n* $h(t)$: hidden state."
        ),
        prose_explanation="The hidden state follows a continuous linear system.",
        symbol_definitions=(("h(t)", "hidden state"),),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
    )
    assert package.markdown_block == canonical_formula_markdown_block(latex)
    assert "###" not in package.markdown_block
    assert "Symbol Definitions" not in package.markdown_block


def test_membership_and_type_label_rows_are_implementation_traces() -> None:
    assert _is_implementation_trace_text(
        "(src_node_id, dst_node_id) in edge_memories"
    )
    assert _is_implementation_trace_text("ent.label_ == 'ORDINAL'")
    assert not _is_implementation_trace_text(
        "personalized PageRank over the passage-entity subgraph"
    )


def test_reader_operation_projection_drops_plumbing_and_keeps_science() -> None:
    projected = project_operation_to_reader_surface({
        "predicate": "updates",
        "description": "propagates query relevance through the entity graph",
        "subject": "edge_memories",
        "operands": ["src_node_id", "dst_node_id", "attention mask"],
        "result": "entity activation",
    })
    assert projected is not None
    assert projected["operation"] == "propagates query relevance through the entity graph"
    assert "edge_memories" not in str(projected)
    assert "src_node_id" not in str(projected)
    assert "attention mask" in str(projected)


def test_publication_heading_normalization_strips_only_structural_colon() -> None:
    assert normalize_publication_heading("## Training objective:") == "Training objective"
    assert normalize_publication_heading("A: B") == "A: B"


def test_assembled_heading_keeps_coherent_writer_repair_of_truncated_plan() -> None:
    from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1
    from code2paper.llm.section_writer import (
        WriterSectionInput,
        _assembled_section_heading,
    )

    section = WriterSectionInput(
        section_id="MA-S4",
        heading="Training objective with a dangling connective and",
        prompt_payload={},
    )
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S4",
        heading_text="Training objective with a contrastive InfoNCE loss",
        section_markdown="The encoder is trained with InfoNCE.",
    )
    assert _assembled_section_heading(section, output) == (
        "Training objective with a contrastive InfoNCE loss"
    )
    intact = WriterSectionInput(
        section_id="MA-S1",
        heading="Offline graph construction",
        prompt_payload={},
    )
    assert _assembled_section_heading(intact, output) == "Offline graph construction"


def test_canonical_formula_suppresses_duplicate_code_shaped_equation() -> None:
    from code2paper.agentic.publication_method_writer import _suppress_duplicate_and_code_shaped_display_formulas

    academic_latex = r"\mathcal{L}_i = -\log \frac{\exp(s_i^+ / \tau)}{\sum_j \exp(s_{ij} / \tau)}"
    academic_block = f"$$\n{academic_latex}\n$$"
    code_block = "$$\nloss_i = -pos_sim + \\operatorname{logsumexp}(all_sims, dim=0)\n$$"
    text = (
        "## Training objective\n\n"
        f"The contrastive loss is given by\n\n{academic_block}\n\n"
        f"where the score is computed as\n\n{code_block}\n\n"
        "and optimized via gradient descent."
    )
    cleaned = _suppress_duplicate_and_code_shaped_display_formulas(
        text,
        formula_packages=({
            "package_id": "pkg-1",
            "latex": academic_latex,
            "markdown_block": academic_block,
        },),
    )
    assert academic_block in cleaned
    assert code_block not in cleaned


def test_duplicate_identical_display_math_is_deduplicated() -> None:
    from code2paper.agentic.publication_method_writer import _suppress_duplicate_and_code_shaped_display_formulas

    latex = r"y = Wx + b"
    block = f"$$\n{latex}\n$$"
    text = f"First:\n\n{block}\n\nSecond:\n\n{block}\n"
    cleaned = _suppress_duplicate_and_code_shaped_display_formulas(text)
    assert cleaned.count(block) == 1


def test_scientific_symbol_survives_operation_projection() -> None:
    projected = project_operation_to_reader_surface({
        "predicate": "computes",
        "description": "computes state transition",
        "subject": r"\mathbf{h}_t",
        "operands": [r"\mathbf{W}", r"\mathbf{x}_t", r"\mathbf{b}"],
        "result": r"\mathbf{h}_{t+1}",
    })
    assert projected is not None
    assert projected["subject"] == r"\mathbf{h}_t"
    assert projected["operands"] == [r"\mathbf{W}", r"\mathbf{x}_t", r"\mathbf{b}"]
    assert projected["result"] == r"\mathbf{h}_{t+1}"
