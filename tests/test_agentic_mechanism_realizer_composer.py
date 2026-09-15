import json
from types import SimpleNamespace

import pytest

from code2paper.agentic.formalization_agent import MechanismFormulaPackageV2
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    MechanismEvidenceClosureV1,
    MechanismContextV1,
    MechanismDetailV1,
)
from code2paper.agentic.mechanism_context_projection import build_mechanism_context_slices
from code2paper.agentic.mechanism_realizer_composer import (
    MechanismDraftV1,
    MechanismRealizer,
    SectionComposer,
    SectionCompositionV1,
    _unique_representation_substring,
    _unique_conditional_line_excerpt,
    sanitize_representation_only,
)
from code2paper.agentic.method_architect import NarrativeSectionPlanV3
from code2paper.agentic.unified_context_compiler import (
    build_consumer_request_payload,
    render_consumer_page_prompt,
)
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.schemas import LLMConfig


def test_sanitize_representation_only() -> None:
    text_with_control_char = "Method\x00 description\x1f with formula."
    cleaned, diff_class = sanitize_representation_only(text_with_control_char)
    assert "\x00" not in cleaned
    assert "\x1f" not in cleaned
    assert diff_class == "control_chars_removed"

    clean_text = "Clean method prose."
    cleaned2, diff_class2 = sanitize_representation_only(clean_text)
    assert cleaned2 == clean_text
    assert diff_class2 == "none"


def test_representation_substring_accepts_typographic_quote_variants() -> None:
    """A witness may use display quotes; the returned bytes stay body-owned."""

    body = 'print(“all_sims”, all_sims)'
    source_excerpt = 'print("all_sims", all_sims)'

    assert _unique_representation_substring(body, source_excerpt) == body


@pytest.mark.parametrize(
    ("excerpt", "detail_conditions", "atom_conditions", "expected"),
    [
        ("if cfg.enabled:\n    work()", ["cfg.enabled"], ["cfg.enabled"], "if cfg.enabled:"),
        ("if cfg.enabled and ready:\n    work()", ["cfg.enabled"], ["ready"], "if cfg.enabled and ready:"),
        ("if cfg.enabled:\n    work()", ["outer"], ["cfg.enabled"], ""),
        ("if cfg.enabled_extra:\n    work()", ["cfg.enabled"], [], ""),
        ("if not cfg.enabled:\n    work()", ["cfg.enabled"], [], ""),
        ("if cfg.enabled or ready:\n    work()", ["cfg.enabled"], [], ""),
        ("if cfg.enabled and ready:\n    work()", ["cfg.enabled"], [], ""),
        ("if 'cfg.enabled':\n    work()", ["cfg.enabled"], [], ""),
        ("# if cfg.enabled:\nwork()", ["cfg.enabled"], [], ""),
        ("flag = cfg.enabled\nwork()", ["cfg.enabled"], [], ""),
        ("if cfg.enabled:\n    one()\nif cfg.enabled:\n    two()", ["cfg.enabled"], [], ""),
        ("if (cfg.enabled\n    and ready):\n    work()", ["cfg.enabled", "ready"], [], ""),
    ],
)
def test_conditional_witness_narrowing_preserves_all_conditions(
    excerpt: str, detail_conditions: list[str], atom_conditions: list[str], expected: str,
) -> None:
    assert _unique_conditional_line_excerpt(
        {"role": "branch", "conditions": detail_conditions},
        [{"atom_kind": "condition", "required_conditions": atom_conditions,
          "exact_excerpts": [excerpt]}],
    ) == expected


def test_conditional_operation_cannot_use_only_its_guard_as_source_witness() -> None:
    assert _unique_conditional_line_excerpt(
        {"role": "transformation", "polarity": "conditional", "conditions": ["cfg.enabled"]},
        [{"atom_kind": "condition", "required_conditions": ["cfg.enabled"],
          "exact_excerpts": ["if cfg.enabled:\n    transform()"]}],
    ) == ""


def test_realizer_repair_contract_preserves_incumbent_draft() -> None:
    page = SimpleNamespace(
        mechanism_id="mech:repair",
        page_id="page:repair",
        technical_bytes_digest="sha256:page-repair",
        technical_payload={
            "detail_ids": ["mech:repair:1"],
            "atoms": [{
                "_atom_id": "detail:mech:repair:1",
                "_atom_kind": "detail",
                "detail_id": "detail:mech:repair:1",
                "witness_atoms": [{
                    "atom_id": "atom:mech:repair:1",
                    "exact_excerpts": ["source operation"],
                }],
            }],
            "formula_package_ids": [],
        },
    )
    incumbent = "The incumbent method sentence."
    feedback = [{
        "failure_code": "realizer_witness_text_missing",
        "witness_kind": "detail",
        "target_id": "detail:mech:repair:1",
        "source_exact_excerpts": ["source operation"],
        "previous_draft_markdown": incumbent,
    }]

    payload = build_consumer_request_payload(
        page=page,
        role="realizer",
        task_ids=("mech:repair",),
        repair_feedback=feedback,
    )
    repair = payload["response_contract"]["bounded_content_repair"]
    assert repair["incumbent_draft_markdown"] == incumbent
    assert repair["items"][0]["required_literal_insertions"] == [{
        "target_id": "detail:mech:repair:1",
        "exact_text": "source operation",
    }]
    prompt = render_consumer_page_prompt(
        page=page,
        role="realizer",
        task_ids=("mech:repair",),
        repair_feedback=feedback,
    )
    assert incumbent in prompt
    assert "incumbent_rule" in prompt


def test_realizer_reports_all_missing_witnesses_in_one_repair() -> None:
    details = tuple(
        MechanismDetailV1(
            detail_id=f"mech_missing:{index}",
            primary_mechanism_id="mech_missing",
            order_index=index,
            role="transformation",
            importance="core",
            claim_kind="implementation",
            evidence_authority="repository_verified",
            publication_policy="clean_candidate",
            semantic_atom=f"operation {index}",
            source_span_ids=(f"span:missing:{index}",),
            witness_atoms=(
                DetailWitnessAtomV1(
                    atom_id=f"atom:detail:mech_missing:{index}",
                    atom_kind="operation",
                    semantic_anchor=f"operation {index}",
                    source_anchor_ids=(f"span:missing:{index}",),
                ),
            ),
        )
        for index in (1, 2)
    )
    context = MechanismContextV1(
        mechanism_id="mech_missing",
        mechanism_name="Missing witness test",
        scientific_role="mechanism_spine",
        reader_question="What happens?",
        purpose="Test witness recovery.",
        importance="core",
        evidence_closure=MechanismEvidenceClosureV1(
            closure_id="closure:mech_missing",
            mechanism_id="mech_missing",
            operation_nodes=(),
            operation_dispositions=(),
            source_operation_terminal_coverage=0.0,
            exact_span_ids=("span:missing:1", "span:missing:2"),
        ),
        ordered_detail_ids=tuple(detail.detail_id for detail in details),
        details=details,
    )
    page = SimpleNamespace(
        mechanism_id="mech_missing",
        page_id="page:missing",
        technical_bytes_digest="sha256:page-missing",
        technical_payload={
            "detail_ids": [detail.detail_id for detail in details],
            "atoms": [
                {
                    "_atom_id": f"detail:{detail.detail_id}",
                    "_atom_kind": "detail",
                    "detail_id": f"detail:{detail.detail_id}",
                    "witness_atoms": [{
                        "atom_id": f"atom:{detail.detail_id}",
                        "exact_excerpts": [f"source operation {index}"],
                    }],
                }
                for index, detail in enumerate(details, start=1)
            ],
            "formula_package_ids": [],
        },
    )

    def caller(_config: LLMConfig, _request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=json.dumps({
                "draft_markdown": "The method is described.",
                "rendered_detail_ids": [
                    f"detail:{detail.detail_id}" for detail in details
                ],
                "used_formula_package_ids": [],
                "witnesses": [
                    {
                        "witness_kind": "detail",
                        "target_id": f"detail:{detail.detail_id}",
                        "exact_text": f"missing witness {index}",
                    }
                    for index, detail in enumerate(details, start=1)
                ],
            }),
            response_hash="sha256:missing-witnesses",
            finish_reason="stop",
        )

    draft = MechanismRealizer(
        llm_config=LLMConfig(model="test-realizer")
    ).realize_draft(
        context=context,
        consumer_page=page,
        required_detail_ids=tuple(
            f"detail:{detail.detail_id}" for detail in details
        ),
        caller=caller,
    )

    assert draft.status == "blocked"
    assert draft.blocked_reason == "realizer_witness_text_missing"
    assert {item["target_id"] for item in draft.repair_feedback} == {
        f"detail:{detail.detail_id}" for detail in details
    }
    assert all(
        item["previous_draft_markdown"] == "The method is described."
        for item in draft.repair_feedback
    )


def test_mechanism_realizer_and_composer_two_step() -> None:
    detail1 = MechanismDetailV1(
        detail_id="d:1",
        primary_mechanism_id="mech_densify",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="specification",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="densify points based on gradient",
        witness_atoms=(
            DetailWitnessAtomV1(atom_id="atom:1", atom_kind="operation", semantic_anchor="densify"),
        ),
    )
    detail2 = MechanismDetailV1(
        detail_id="d:2",
        primary_mechanism_id="mech_densify",
        order_index=1,
        role="condition",
        importance="core",
        claim_kind="specification",
        evidence_authority="repository_partial",
        publication_policy="clean_candidate",
        semantic_atom="prune points exceeding threshold",
        witness_atoms=(),
    )
    from code2paper.agentic.mechanism_context_models import MechanismEvidenceClosureV1

    closure = MechanismEvidenceClosureV1(
        closure_id="closure:densify",
        mechanism_id="mech_densify",
        operation_nodes=(),
        operation_dispositions=(),
        source_operation_terminal_coverage=0.0,
        exact_span_ids=(),
    )
    ctx = MechanismContextV1(
        mechanism_id="mech_densify",
        mechanism_name="Gaussian Densification and Pruning",
        scientific_role="transformation",
        reader_question="How are Gaussians densified?",
        purpose="Scene optimization",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=("d:1", "d:2"),
        details=(detail1, detail2),
    )

    pkg = MechanismFormulaPackageV2(
        package_id="pkg:vcd",
        mechanism_id="mech_densify",
        source_detail_ids=("d:1",),
        satisfied_obligation_ids=("obl:1",),
        latex=r"\Delta p = \frac{\nabla L}{\tau}",
        prose_explanation="Offset proportional to gradient divided by threshold.",
    )

    # A missing caller is fail-closed: the harness cannot manufacture the
    # paragraph or its witnesses.
    blocked = MechanismRealizer().realize_draft(
        context=ctx,
        page_index=0,
        page_slice=build_mechanism_context_slices(ctx)[0],
        formula_packages=(pkg,),
    )
    assert blocked.status == "blocked"
    assert blocked.draft_markdown == ""
    assert blocked.realized_detail_ids == ()
    assert blocked.witnesses == ()

    # Step 1: Mechanism Realizer through the actual caller boundary.
    calls: list[LLMRequest] = []

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        calls.append(request)
        markdown = (
            "Densify points based on gradient and prune points exceeding threshold. "
            r"The update is \Delta p = \frac{\nabla L}{\tau}."
        )
        return LLMResponse(
            text=__import__("json").dumps({
                "draft_markdown": markdown,
                "rendered_detail_ids": ["d:1", "d:2"],
                "used_formula_package_ids": ["pkg:vcd"],
                "witnesses": [
                    {"witness_kind": "detail", "target_id": "d:1", "exact_text": "Densify points based on gradient"},
                    {"witness_kind": "detail", "target_id": "d:2", "exact_text": "prune points exceeding threshold"},
                    {"witness_kind": "formula", "target_id": "pkg:vcd", "exact_text": r"\Delta p = \frac{\nabla L}{\tau}"},
                ],
            }),
            response_hash="sha256:test",
            finish_reason="stop",
        )

    page = build_mechanism_context_slices(ctx)[0]
    realizer = MechanismRealizer(llm_config=LLMConfig(model="test-realizer"))
    draft = realizer.realize_draft(
        context=ctx,
        page_index=0,
        page_slice=page,
        formula_packages=(pkg,),
        caller=caller,
    )

    assert isinstance(draft, MechanismDraftV1)
    assert draft.mechanism_id == "mech_densify"
    assert "d:1" in draft.realized_detail_ids
    assert "d:2" in draft.realized_detail_ids
    assert "pkg:vcd" in draft.formula_package_ids
    # Authority rules
    assert draft.status == "accepted"
    assert draft.witnesses
    assert calls
    assert calls[0].input_payload["shared_page_bytes"] == page.serialized_payload.decode("utf-8")
    # Formula package is verbatim included without formula rewrite
    assert r"\Delta p = \frac{\nabla L}{\tau}" in draft.draft_markdown

    # Step 2: Section Composer
    sec_plan = NarrativeSectionPlanV3(
        section_id="sec_method",
        heading="Methodology",
        mechanism_ids=("mech_densify",),
    )
    composer = SectionComposer()
    section = composer.compose_section(
        section_plan=sec_plan,
        drafts=(draft,),
    )

    assert isinstance(section, SectionCompositionV1)
    assert section.section_id == "sec_method"
    assert section.heading == "Methodology"
    assert "## Methodology" in section.section_markdown
    assert draft.draft_id in section.used_mechanism_draft_ids
    assert len(section.paragraphs) == 1
    assert section.paragraphs[0]["mechanism_id"] == "mech_densify"


@pytest.mark.parametrize(
    "response_wrapper",
    ("plain", "complete_json_fence", "truncated_json_fence"),
)
def test_v2_realizer_normalizes_detail_ids_and_exposes_closed_witness_contract(
    response_wrapper: str,
) -> None:
    """V2 pages use one prefixed detail identity at the response boundary."""

    detail = MechanismDetailV1(
        detail_id="mech_partial:1",
        primary_mechanism_id="mech_partial",
        order_index=0,
        role="branch",
        importance="core",
        claim_kind="implementation",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="branch: selects a path",
        source_span_ids=("span:test:1",),
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:mech_partial:1",
                atom_kind="operation",
                semantic_anchor="selects a path",
                source_anchor_ids=("span:test:1",),
            ),
        ),
    )
    context = MechanismContextV1(
        mechanism_id="mech_partial",
        mechanism_name="Partial branch",
        scientific_role="mechanism_spine",
        reader_question="How does the branch work?",
        purpose="Select a path.",
        importance="core",
        evidence_closure=MechanismEvidenceClosureV1(
            closure_id="closure:mech_partial",
            mechanism_id="mech_partial",
            operation_nodes=(),
            operation_dispositions=(),
            source_operation_terminal_coverage=0.0,
            exact_span_ids=("span:test:1",),
        ),
        ordered_detail_ids=(detail.detail_id,),
        details=(detail,),
    )
    page = SimpleNamespace(
        mechanism_id="mech_partial",
        page_id="page:partial",
        technical_bytes_digest="sha256:page",
        technical_payload={
            "detail_ids": ["mech_partial:1"],
            "atoms": [{
                "_atom_id": "detail:mech_partial:1",
                "_atom_kind": "detail",
                "detail_id": "detail:mech_partial:1",
                "evidence_authority": "repository_verified",
                "witness_atoms": [{
                    "atom_id": "atom:mech_partial:1",
                    "exact_excerpts": ["The branch selects a path."],
                }],
            }],
        },
    )

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        contract = request.input_payload["response_contract"]
        # The complete technical page remains in the user payload; the system
        # prompt must contain only the compact role contract so the same page
        # is not counted twice against the run-wide input budget.
        assert "sole technical authority" in request.prompt
        assert len(request.prompt) < 1000
        assert contract["required_detail_ids"] == ["detail:mech_partial:1"]
        assert contract["allowed_atom_target_ids"] == ["atom:mech_partial:1"]
        response_text = json.dumps({
                "draft_markdown": "The branch selects a path.",
                # The provider-facing page historically exposes this without
                # the ``detail:`` prefix; the harness canonicalizes it.
                "rendered_detail_ids": ["mech_partial:1"],
                "used_formula_package_ids": [],
                "witnesses": [{
                    "witness_kind": "detail",
                    "target_id": "mech_partial:1",
                    # Representation-only recovery may replace a malformed
                    # witness string with the frozen source excerpt when that
                    # excerpt is already an unchanged substring of the draft.
                    "exact_text": "The branch selects a path with drift.",
                }],
            })
        if response_wrapper == "complete_json_fence":
            response_text = f"```json\n{response_text}\n```"
        elif response_wrapper == "truncated_json_fence":
            # A partial fence is not a safe representation-only recovery
            # case: the harness must not guess the missing JSON suffix.
            response_text = f"```json\n{response_text}"
        return LLMResponse(
            text=response_text,
            response_hash="sha256:v2-realizer",
            finish_reason="stop",
        )

    draft = MechanismRealizer(llm_config=LLMConfig(model="test-realizer")).realize_draft(
        context=context,
        page_index=0,
        consumer_page=page,
        required_detail_ids=("detail:mech_partial:1",),
        caller=caller,
    )

    if response_wrapper == "truncated_json_fence":
        assert draft.status == "blocked"
        assert draft.blocked_reason == "realizer_response_not_json"
        assert draft.repair_feedback[0]["failure_code"] == (
            "realizer_response_not_json"
        )
    else:
        assert draft.status == "accepted"
        assert draft.realized_detail_ids == ("detail:mech_partial:1",)
        assert draft.witnesses[0].target_id == "detail:mech_partial:1"
        assert draft.witnesses[0].exact_text == "The branch selects a path."
        assert draft.representation_diff_class == "witness_exact_text_repaired"


def test_v2_realizer_repairs_only_escaped_whitespace_witness_representation() -> None:
    """A uniquely matching escaped-newline witness may be rebound to body text."""

    detail = MechanismDetailV1(
        detail_id="mech_code:1",
        primary_mechanism_id="mech_code",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="implementation",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="concatenates query and passages",
        source_span_ids=("span:test:code",),
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:mech_code:1",
                atom_kind="operation",
                semantic_anchor="concatenates",
                source_anchor_ids=("span:test:code",),
            ),
        ),
    )
    context = MechanismContextV1(
        mechanism_id="mech_code",
        mechanism_name="Code mechanism",
        scientific_role="mechanism_spine",
        reader_question="How is the input combined?",
        purpose="Combine inputs.",
        importance="core",
        evidence_closure=MechanismEvidenceClosureV1(
            closure_id="closure:mech_code",
            mechanism_id="mech_code",
            operation_nodes=(),
            operation_dispositions=(),
            source_operation_terminal_coverage=0.0,
            exact_span_ids=("span:test:code",),
        ),
        ordered_detail_ids=(detail.detail_id,),
        details=(detail,),
    )
    page = SimpleNamespace(
        mechanism_id="mech_code",
        page_id="page:code",
        technical_bytes_digest="sha256:page-code",
        technical_payload={
            "detail_ids": ["mech_code:1"],
            "atoms": [{
                "_atom_id": "detail:mech_code:1",
                "_atom_kind": "detail",
                "detail_id": "detail:mech_code:1",
                "evidence_authority": "repository_verified",
                "witness_atoms": [{
                    "atom_id": "atom:mech_code:1",
                    "exact_excerpts": [
                        "torch.cat(\n    (query, passages), dim=1)"
                    ],
                }],
            }],
        },
    )

    def caller(_config: LLMConfig, _request: LLMRequest) -> LLMResponse:
        markdown = r"The operation is `torch.cat(\n    (query, passages), dim=1)`."
        return LLMResponse(
            text=json.dumps({
                "draft_markdown": markdown,
                "rendered_detail_ids": ["mech_code:1"],
                "used_formula_package_ids": [],
                "witnesses": [{
                    "witness_kind": "detail",
                    "target_id": "mech_code:1",
                    "exact_text": "torch.cat( (query, passages), dim=1)",
                }],
            }),
            response_hash="sha256:escaped-whitespace",
            finish_reason="stop",
        )

    draft = MechanismRealizer(llm_config=LLMConfig(model="test-realizer")).realize_draft(
        context=context,
        page_index=0,
        consumer_page=page,
        required_detail_ids=("detail:mech_code:1",),
        caller=caller,
    )

    assert draft.status == "accepted"
    assert draft.witnesses[0].exact_text == r"torch.cat(\n    (query, passages), dim=1)"
    assert draft.representation_diff_class == "witness_exact_text_whitespace_repaired"


def test_v2_realizer_binds_formula_witness_to_package_source_detail() -> None:
    """A formula witness cannot use its package ID as the source text."""

    detail = MechanismDetailV1(
        detail_id="mech_formula:1",
        primary_mechanism_id="mech_formula",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="implementation",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="extracts passage count",
        source_span_ids=("span:formula",),
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:mech_formula:1",
                atom_kind="operation",
                semantic_anchor="extracts passage count",
            ),
        ),
    )
    context = MechanismContextV1(
        mechanism_id="mech_formula",
        mechanism_name="Formula mechanism",
        scientific_role="mechanism_spine",
        reader_question="How is the passage count computed?",
        purpose="Extract a tensor dimension.",
        importance="core",
        evidence_closure=MechanismEvidenceClosureV1(
            closure_id="closure:mech_formula",
            mechanism_id="mech_formula",
            operation_nodes=(),
            operation_dispositions=(),
            source_operation_terminal_coverage=0.0,
            exact_span_ids=("span:formula",),
        ),
        ordered_detail_ids=(detail.detail_id,),
        details=(detail,),
    )
    package = MechanismFormulaPackageV2(
        package_id="pkg:formula:passage-count",
        mechanism_id="mech_formula",
        source_detail_ids=(detail.detail_id,),
        satisfied_obligation_ids=("ob:formula:passage-count",),
        latex="num_passages = passages.shape[1]",
        prose_explanation="The second passage dimension is assigned to num_passages.",
    )
    page = SimpleNamespace(
        mechanism_id="mech_formula",
        page_id="page:formula",
        technical_bytes_digest="sha256:page-formula",
        technical_payload={
            "detail_ids": [detail.detail_id],
            "formula_package_ids": [package.package_id],
            "formula_package_source_detail_ids": {
                package.package_id: [f"detail:{detail.detail_id}"],
            },
            "atoms": [{
                "_atom_id": f"detail:{detail.detail_id}",
                "_atom_kind": "detail",
                "detail_id": f"detail:{detail.detail_id}",
                "evidence_authority": "repository_verified",
                "witness_atoms": [{
                    "atom_id": "atom:mech_formula:1",
                    "exact_excerpts": ["num_passages = passages.shape[1]"],
                }],
            }],
        },
    )

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        contract = request.input_payload["response_contract"]
        assert contract["required_formula_witness_bindings"] == [{
            "package_id": package.package_id,
            "source_detail_ids": [f"detail:{detail.detail_id}"],
            "literal_source_excerpts": ["num_passages = passages.shape[1]"],
        }]
        return LLMResponse(
            text=json.dumps({
                "draft_markdown": (
                    "The code computes `num_passages = passages.shape[1]`."
                ),
                "rendered_detail_ids": [detail.detail_id],
                "used_formula_package_ids": [package.package_id],
                "witnesses": [
                    {
                        "witness_kind": "detail",
                        "target_id": detail.detail_id,
                        "exact_text": "The code computes `num_passages = passages.shape[1]`.",
                    },
                    {
                        "witness_kind": "formula",
                        "target_id": package.package_id,
                        # Simulate the live provider's representation mistake:
                        # the package ID is not source text and must be rebound
                        # only through the frozen package source-detail closure.
                        "exact_text": package.package_id,
                    },
                ],
            }),
            response_hash="sha256:formula-binding",
            finish_reason="stop",
        )

    draft = MechanismRealizer(
        llm_config=LLMConfig(model="test-realizer")
    ).realize_draft(
        context=context,
        page_index=0,
        consumer_page=page,
        formula_packages=(package,),
        required_detail_ids=(f"detail:{detail.detail_id}",),
        caller=caller,
    )

    assert draft.status == "accepted"
    assert draft.witnesses[-1].witness_kind == "formula"
    assert draft.witnesses[-1].exact_text == "num_passages = passages.shape[1]"
    assert draft.representation_diff_class == "witness_exact_text_repaired"


def test_v2_realizer_repair_uses_atomic_guard_and_revalidates_incumbent_witnesses() -> None:
    """A repair inserts one guard line and retains only unchanged prior bindings."""

    operation_detail = MechanismDetailV1(
        detail_id="mech_repair:1",
        primary_mechanism_id="mech_repair",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="implementation",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="applies the first operation",
        source_span_ids=("span:repair:1",),
        source_kind="first_party_executable",
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:mech_repair:1",
                atom_kind="operation",
                semantic_anchor="first_operation",
                source_anchor_ids=("span:repair:1",),
                exact_excerpts=("first_operation()",),
            ),
        ),
    )
    branch_excerpt = (
        "if cfg.enabled:\n"
        "    transformed = first_operation()\n"
        "    return transformed"
    )
    branch_detail = MechanismDetailV1(
        detail_id="mech_repair:2",
        primary_mechanism_id="mech_repair",
        order_index=1,
        role="branch",
        importance="supporting",
        claim_kind="implementation",
        evidence_authority="unresolved",
        publication_policy="annotated_only",
        semantic_atom="branch: branches on cfg.enabled",
        conditions=("cfg.enabled",),
        polarity="conditional",
        source_span_ids=("span:repair:2",),
        source_kind="first_party_executable",
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:mech_repair:2:condition",
                atom_kind="condition",
                semantic_anchor="cfg.enabled",
                source_anchor_ids=("span:repair:2",),
                exact_excerpts=(branch_excerpt,),
                required_conditions=("cfg.enabled",),
                required_polarity="conditional",
            ),
        ),
    )
    context = MechanismContextV1(
        mechanism_id="mech_repair",
        mechanism_name="Bounded repair",
        scientific_role="mechanism_spine",
        reader_question="How is the operation selected?",
        purpose="Exercise the Realizer repair transaction.",
        importance="core",
        evidence_closure=MechanismEvidenceClosureV1(
            closure_id="closure:mech_repair",
            mechanism_id="mech_repair",
            operation_nodes=(),
            operation_dispositions=(),
            source_operation_terminal_coverage=0.0,
            exact_span_ids=("span:repair:1", "span:repair:2"),
        ),
        ordered_detail_ids=(operation_detail.detail_id, branch_detail.detail_id),
        details=(operation_detail, branch_detail),
    )
    page = SimpleNamespace(
        mechanism_id="mech_repair",
        page_id="page:repair-state",
        technical_bytes_digest="sha256:repair-state",
        technical_payload={
            "detail_ids": [operation_detail.detail_id, branch_detail.detail_id],
            "formula_package_ids": [],
            "atoms": [
                {
                    "_atom_id": f"detail:{operation_detail.detail_id}",
                    "_atom_kind": "detail",
                    "detail_id": f"detail:{operation_detail.detail_id}",
                    "role": "transformation",
                    "polarity": "positive",
                    "witness_atoms": [{
                        "atom_id": "atom:mech_repair:1",
                        "atom_kind": "operation",
                        "semantic_anchor": "first_operation",
                        "exact_excerpts": ["first_operation()"],
                    }],
                },
                {
                    "_atom_id": f"detail:{branch_detail.detail_id}",
                    "_atom_kind": "detail",
                    "detail_id": f"detail:{branch_detail.detail_id}",
                    "role": "branch",
                    "polarity": "conditional",
                    "conditions": ["cfg.enabled"],
                    "evidence_authority": "unresolved",
                    "witness_atoms": [{
                        "atom_id": "atom:mech_repair:2:condition",
                        "atom_kind": "condition",
                        "semantic_anchor": "cfg.enabled",
                        "required_conditions": ["cfg.enabled"],
                        "exact_excerpts": [branch_excerpt],
                    }],
                },
            ],
        },
    )
    primary_markdown = (
        "The implementation invokes `first_operation()`. The conditional path "
        "depends on `cfg.enabled`, whose active value remains unresolved."
    )

    def primary_caller(_config: LLMConfig, _request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=json.dumps({
                "draft_markdown": primary_markdown,
                "rendered_detail_ids": [
                    operation_detail.detail_id,
                    branch_detail.detail_id,
                ],
                "used_formula_package_ids": [],
                "witnesses": [
                    {
                        "witness_kind": "detail",
                        "target_id": operation_detail.detail_id,
                        "exact_text": f"detail:{operation_detail.detail_id}",
                    },
                    {
                        "witness_kind": "detail",
                        "target_id": branch_detail.detail_id,
                        "exact_text": f"detail:{branch_detail.detail_id}",
                    },
                ],
            }),
            response_hash="sha256:repair-primary",
            finish_reason="stop",
        )

    realizer = MechanismRealizer(llm_config=LLMConfig(model="test-realizer"))
    primary = realizer.realize_draft(
        context=context,
        consumer_page=page,
        required_detail_ids=(
            f"detail:{operation_detail.detail_id}",
            f"detail:{branch_detail.detail_id}",
        ),
        caller=primary_caller,
    )

    assert primary.status == "blocked"
    assert primary.blocked_reason == "realizer_witness_text_missing"
    assert primary.repair_feedback[0]["source_exact_excerpts"] == [
        "if cfg.enabled:"
    ]
    assert primary.repair_feedback[0]["validated_incumbent_witnesses"] == [{
        "witness_kind": "detail",
        "target_id": f"detail:{operation_detail.detail_id}",
        "exact_text": "first_operation()",
    }]

    repair_markdown = primary_markdown + "\n```python\nif cfg.enabled:\n```"

    def repair_caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        repair_contract = request.input_payload["response_contract"][
            "bounded_content_repair"
        ]
        assert repair_contract["items"][0]["required_literal_insertions"] == [{
            "target_id": f"detail:{branch_detail.detail_id}",
            "exact_text": "if cfg.enabled:",
        }]
        assert repair_contract["items"][0]["validated_incumbent_witnesses"]
        return LLMResponse(
            text=json.dumps({
                "draft_markdown": repair_markdown,
                "rendered_detail_ids": [
                    operation_detail.detail_id,
                    branch_detail.detail_id,
                ],
                "used_formula_package_ids": [],
                # The repair owns only the failed target. The prior binding is
                # deliberately omitted and must be revalidated against both
                # drafts before it is carried forward.
                "witnesses": [{
                    "witness_kind": "detail",
                    "target_id": branch_detail.detail_id,
                    "exact_text": "if cfg.enabled:",
                }],
            }),
            response_hash="sha256:repair-complete",
            finish_reason="stop",
        )

    repaired = realizer.realize_draft(
        context=context,
        consumer_page=page,
        required_detail_ids=(
            f"detail:{operation_detail.detail_id}",
            f"detail:{branch_detail.detail_id}",
        ),
        repair_feedback=primary.repair_feedback,
        caller=repair_caller,
    )

    assert repaired.status == "accepted"
    assert {witness.target_id for witness in repaired.witnesses} == {
        f"detail:{operation_detail.detail_id}",
        f"detail:{branch_detail.detail_id}",
    }
    assert repaired.representation_diff_class == "incumbent_witnesses_revalidated"

    def destructive_repair_caller(
        _config: LLMConfig,
        _request: LLMRequest,
    ) -> LLMResponse:
        return LLMResponse(
            text=json.dumps({
                "draft_markdown": (
                    "The prior operation sentence was removed.\n"
                    "```python\nif cfg.enabled:\n```"
                ),
                "rendered_detail_ids": [
                    operation_detail.detail_id,
                    branch_detail.detail_id,
                ],
                "used_formula_package_ids": [],
                "witnesses": [{
                    "witness_kind": "detail",
                    "target_id": branch_detail.detail_id,
                    "exact_text": "if cfg.enabled:",
                }],
            }),
            response_hash="sha256:repair-removes-incumbent",
            finish_reason="stop",
        )

    rejected = realizer.realize_draft(
        context=context,
        consumer_page=page,
        required_detail_ids=(
            f"detail:{operation_detail.detail_id}",
            f"detail:{branch_detail.detail_id}",
        ),
        repair_feedback=primary.repair_feedback,
        caller=destructive_repair_caller,
    )
    assert rejected.status == "blocked"
    assert rejected.blocked_reason == "realizer_required_witness_missing"
    assert rejected.repair_feedback[0]["target_id"] == (
        f"detail:{operation_detail.detail_id}"
    )
