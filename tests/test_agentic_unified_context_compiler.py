from __future__ import annotations

import pytest

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
from code2paper.agentic.unified_context_compiler import (
    build_consumer_workset_manifest_v2,
    build_unified_context_archive_v2,
)
def test_qualified_equation_id_is_not_double_prefixed_in_formula_page() -> None:
    """A frozen ``equation:*`` ID must resolve to the same archive atom."""

    operation = EvidenceOperationV1(
        operation_id="op:loss",
        predicate="compute_loss",
        operands=("x",),
        result="loss",
        source_span_id="",
        active_path_status="active_default",
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:loss",
        mechanism_id="mech_loss",
        operation_nodes=(operation,),
        equation_ids=("equation:fact-loss",),
        operation_dispositions=(SourceOperationDispositionV1(
            operation_id=operation.operation_id,
            disposition="absorbed_by_detail",
            detail_ids=("d:loss",),
        ),),
        source_operation_terminal_coverage=1.0,
    )
    detail = MechanismDetailV1(
        detail_id="d:loss",
        primary_mechanism_id="mech_loss",
        order_index=0,
        role="training_objective",
        importance="core",
        claim_kind="formalization",
        evidence_authority="unresolved",
        publication_policy="review_only",
        semantic_atom="compute loss",
        predicate="compute_loss",
        operands=("x",),
        result="loss",
        active_path_status="active_default",
        source_operation_ids=(operation.operation_id,),
        source_equation_ids=("equation:fact-loss",),
        formalizable=True,
    )
    context = MechanismContextV1(
        mechanism_id="mech_loss",
        mechanism_name="Loss",
        scientific_role="training_objective",
        reader_question="What is optimized?",
        purpose="Compute the objective.",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=(detail.detail_id,),
        details=(detail,),
        source_manifest_digest="sha256:manifest",
    )
    context_set = MechanismContextSetV1(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:alignment",
        research_digest="sha256:research",
        contexts=(context,),
    )
    equations = ({
        "equation_id": "equation:fact-loss",
        "expression": "L = f(x)",
        "fact_ids": [],
        "symbol_bindings": [],
        "canonical_identity": "sha256:equation",
    },)
    archive = build_unified_context_archive_v2(
        context_set,
        source_manifest_digest="sha256:manifest",
        equations=equations,
    )
    obligation = MechanismFormulaObligationV1(
        obligation_id="ob:loss",
        mechanism_id=context.mechanism_id,
        source_detail_ids=(detail.detail_id,),
        source_equation_ids=("equation:fact-loss",),
        mathematical_goal="Formalize the loss.",
    )

    assert tuple(atom.atom_id for atom in archive.equation_atoms) == (
        "equation:fact-loss",
    )
    manifest = build_consumer_workset_manifest_v2(
        archive,
        {context.mechanism_id: (obligation,)},
        max_page_input_tokens=20_000,
        max_obligations_per_page=8,
    )
    assert "equation:fact-loss" in manifest.worksets[0].required_atom_ids
    assert all(
        not atom_id.startswith("equation:equation:")
        for atom_id in manifest.worksets[0].required_atom_ids
    )


def test_archive_stores_shared_operation_once_with_canonical_owner() -> None:
    """Two mechanisms sharing one dependency operation must not conflict."""

    from code2paper.agentic.mechanism_context_compiler import (
        annotate_mechanism_paper_details,
        compile_mechanism_evidence_closures,
    )
    from code2paper.agentic.unified_context_compiler import (
        build_unified_context_archive_v2,
    )

    facts = [
        {
            "fact_id": "fact:shared",
            "subject": "shared",
            "predicate": "load",
            "operands": ["path"],
            "result": "loaded",
            "direct_span_ids": ["span:a.py:1:2"],
            "scope": "a.py",
        },
        {
            "fact_id": "fact:a",
            "subject": "loaded",
            "predicate": "encode",
            "operands": ["loaded"],
            "result": "encoded",
            "direct_span_ids": ["span:a.py:3:4"],
            "scope": "a.py",
        },
        {
            "fact_id": "fact:b",
            "subject": "loaded",
            "predicate": "decode",
            "operands": ["loaded"],
            "result": "decoded",
            "direct_span_ids": ["span:a.py:5:6"],
            "scope": "a.py",
        },
    ]
    facets = [
        {"facet_id": "facet:a", "mechanism_id": "mech_a", "author_statement": "Encode."},
        {"facet_id": "facet:b", "mechanism_id": "mech_b", "author_statement": "Decode."},
    ]
    alignments = [
        {
            "facet_id": "facet:a",
            "bound_fact_ids": ["fact:shared", "fact:a"],
            "bound_span_ids": ["span:a.py:1:2", "span:a.py:3:4"],
        },
        {
            "facet_id": "facet:b",
            "bound_fact_ids": ["fact:shared", "fact:b"],
            "bound_span_ids": ["span:a.py:1:2", "span:a.py:5:6"],
        },
    ]
    from code2paper.agentic.source_inventory import (
        RepositorySourceEntryV1,
        RepositorySourceManifestV1,
    )

    entry = RepositorySourceEntryV1(
        path="a.py",
        source_kind="first_party_executable",
        ownership_role="target_core",
        executable_authority=True,
        content_digest="sha256:a-entry",
        classification_reason="fixture:first_party_executable",
    )
    source_manifest = RepositorySourceManifestV1(
        repo_snapshot_id="repo:fixture",
        # The context set has no repository provider in this fixture, so its
        # declared tree hash is the neutral placeholder.
        project_tree_hash="tree:unknown",
        entries=(entry,),
        target_core_paths=(entry.path,),
    )

    closures = compile_mechanism_evidence_closures(
        facets=facets,
        facet_alignments=alignments,
        facts=facts,
        source_manifest=source_manifest,
    )
    assert len(closures) == 2
    context_set = annotate_mechanism_paper_details(closures)

    archive = build_unified_context_archive_v2(
        context_set,
        source_manifest_digest=source_manifest.content_digest,
        source_manifest=source_manifest,
        repo_snapshot_digest="sha256:snapshot",
    )

    shared_atoms = [
        atom for atom in archive.operation_atoms
        if atom.atom_id == "operation:fact-operation:fact:shared"
    ]
    assert len(shared_atoms) == 1
    assert shared_atoms[0].primary_mechanism_id == "mech_a"
    # Both mechanisms keep their own closure projection in the archive.
    assert len(archive.mechanism_atoms) == 2


def test_dual_view_guard_alignment_reaches_archive_detail_atom() -> None:
    """R1: the recovered conditional path evidence must reach the consumer.

    Compiles the full facts+graph fixture through the real loader, then builds
    the V2 archive (the payload Formalizer pages consume) and asserts the
    aligned ``conditional`` status, its condition, and the typed activation
    basis survive into the detail atom.
    """

    from code2paper.agentic.mechanism_context_compiler import (
        compile_mechanism_contexts,
        validate_mechanism_context_completeness,
        validate_mechanism_context_structural_gates,
    )
    from code2paper.agentic.source_inventory import (
        RepositorySourceEntryV1,
        RepositorySourceManifestV1,
    )
    from code2paper.agentic.unified_context_compiler import (
        build_unified_context_archive_v2,
    )

    span = "span:src/model.py:146:149"
    branch_span = "span:src/model.py:145:174"
    facts = {"facts": [{
        "fact_id": "fact:dual:zero-mask",
        "subject": "Model.forward",
        "predicate": "calls",
        "operands": ["torch.zeros", "shape", "device=self.device"],
        "result": "dedicated_attention_mask",
        "conditions": ["self.cfg.use_dedicated_attention"],
        "scope": "sym:model_forward",
        "direct_span_ids": [span],
        "validation_status": "supported",
        "validation_failures": [],
    }]}
    facets = [{
        "facet_id": "facet:dual",
        "mechanism_id": "mech_model_forward",
        "author_statement": "Dedicated attention mask under configuration.",
    }]
    alignments = [{
        "facet_id": "facet:dual",
        "bound_fact_ids": ["fact:dual:zero-mask"],
        "bound_span_ids": [span],
    }]
    graph = {
        "repo_snapshot_id": "repo:fixture",
        "project_tree_hash": "sha256:tree",
        "nodes": [
            {
                "node_id": "node:branch-mask",
                "symbol_id": "sym:model_forward",
                "predicate": "BRANCH",
                "operands": ["self.cfg.use_dedicated_attention"],
                "result": "",
                "guard": "self.cfg.use_dedicated_attention",
                "source_span_id": branch_span,
            },
            {
                "node_id": "node:call-zeros",
                "symbol_id": "sym:model_forward",
                "predicate": "CALL",
                "operands": ["torch.zeros", "shape", "device=self.device"],
                "result": "dedicated_attention_mask",
                "guard": "",
                "source_span_id": span,
            },
        ],
        "relations": [{
            "relation_id": "rel:true-branch-mask",
            "kind": "TRUE_BRANCH",
            "source_node_id": "node:branch-mask",
            "target_node_id": "node:call-zeros",
            "source_span_id": branch_span,
            "target_span_id": span,
            "guard": "self.cfg.use_dedicated_attention",
        }],
    }
    entry = RepositorySourceEntryV1(
        path="src/model.py",
        source_kind="first_party_executable",
        ownership_role="target_core",
        executable_authority=True,
        content_digest="sha256:model-entry",
        classification_reason="fixture:first_party_executable",
    )
    source_manifest = RepositorySourceManifestV1(
        repo_snapshot_id="repo:fixture",
        project_tree_hash="sha256:tree",
        entries=(entry,),
        target_core_paths=(entry.path,),
    )

    context_set = compile_mechanism_contexts(
        facets=facets,
        facet_alignments=alignments,
        facts=facts,
        behavior_graph=graph,
        implementation_scope={
            "schema_version": "1.0",
            "target_entry_symbol_ids": ["sym:model_forward"],
            "target_core_symbol_ids": ["sym:model_forward"],
        },
        source_manifest=source_manifest,
    )
    context = context_set.contexts[0]
    assert validate_mechanism_context_completeness(
        context, source_manifest=source_manifest
    ) == ()
    assert validate_mechanism_context_structural_gates(context_set)[
        "unknown_core_active_path_count"
    ] == 0

    archive = build_unified_context_archive_v2(
        context_set,
        source_manifest_digest=source_manifest.content_digest,
        source_manifest=source_manifest,
        repo_snapshot_digest="sha256:snapshot",
    )

    detail_atoms = [
        atom for atom in archive.detail_atoms
        if span in tuple(atom.payload.get("source_span_ids", ()))
    ]
    assert detail_atoms, "the dual-view detail must be archived"
    payload = detail_atoms[0].payload
    assert payload["active_path_status"] == "conditional"
    assert payload["conditions"] == ["self.cfg.use_dedicated_attention"]
    assert "rel:true-branch-mask" in payload["activation_basis_ids"]


# ---------------------------------------------------------------------------
# R6: page budget metering and oversize atomic-unit reporting
# ---------------------------------------------------------------------------


def _budget_fixture(*, detail_count: int = 1, operations_per_detail: int = 8):
    """Two adjacent details whose single pages fit only under a loose cap."""

    from code2paper.agentic.mechanism_context_models import MechanismEdgeV1

    operations = tuple(
        EvidenceOperationV1(
            operation_id=f"op:{detail_index}:{operation_index}",
            predicate="compute_projection_component",
            operands=(
                f"operand_alpha_{detail_index}_{operation_index}",
                f"operand_beta_{detail_index}_{operation_index}",
            ),
            result=f"result_value_{detail_index}_{operation_index}",
            source_span_id="",
            active_path_status="active_default",
        )
        for detail_index in range(detail_count)
        for operation_index in range(operations_per_detail)
    )
    details = tuple(
        MechanismDetailV1(
            detail_id=f"d:{detail_index}",
            primary_mechanism_id="mech_budget",
            order_index=detail_index,
            role="transformation",
            importance="core",
            claim_kind="implementation",
            evidence_authority="repository_verified",
            publication_policy="clean_candidate",
            semantic_atom=(
                "linear projection with a deliberately verbose semantic "
                f"description for detail {detail_index}"
            ),
            predicate="compute_projection_component",
            operands=(f"operand_alpha_{detail_index}_0",),
            result=f"result_value_{detail_index}_0",
            active_path_status="active_default",
            source_operation_ids=tuple(
                operation.operation_id
                for operation in operations
                if operation.operation_id.startswith(f"op:{detail_index}:")
            ),
            witness_atoms=(DetailWitnessAtomV1(
                atom_id=f"atom:{detail_index}",
                atom_kind="operation",
                semantic_anchor="linear projection",
                source_operation_ids=tuple(
                    operation.operation_id
                    for operation in operations
                    if operation.operation_id.startswith(f"op:{detail_index}:")
                ),
            ),),
        )
        for detail_index in range(detail_count)
    )
    edges = tuple(
        MechanismEdgeV1(
            edge_id=f"edge:{index}",
            mechanism_id="mech_budget",
            source_detail_id=details[index].detail_id,
            target_detail_id=details[index + 1].detail_id,
            relation="feeds",
        )
        for index in range(len(details) - 1)
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:budget",
        mechanism_id="mech_budget",
        operation_nodes=operations,
        operation_dispositions=tuple(
            SourceOperationDispositionV1(
                operation_id=operation.operation_id,
                disposition="absorbed_by_detail",
                detail_ids=(f"d:{operation.operation_id.split(':')[1]}",),
            )
            for operation in operations
        ),
        source_operation_terminal_coverage=1.0,
    )
    context = MechanismContextV1(
        mechanism_id="mech_budget",
        mechanism_name="Budget",
        scientific_role="transformation",
        reader_question="How is the projection computed?",
        purpose="Compute the projection.",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=tuple(detail.detail_id for detail in details),
        details=details,
        edges=edges,
        source_manifest_digest="sha256:manifest",
    )
    context_set = MechanismContextSetV1(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:alignment",
        research_digest="sha256:research",
        contexts=(context,),
    )
    archive = build_unified_context_archive_v2(
        context_set, source_manifest_digest="sha256:manifest"
    )
    obligations = tuple(
        MechanismFormulaObligationV1(
            obligation_id=f"ob:{index}",
            mechanism_id="mech_budget",
            source_detail_ids=(detail.detail_id,),
            mathematical_goal=f"Formalize detail {index}.",
        )
        for index, detail in enumerate(details)
    )
    return archive, obligations


def test_packed_pages_meter_the_whole_page_not_the_atom_sum() -> None:
    """R6: the packer budget is the real page cost, so merging cannot overshoot."""

    from code2paper.agentic.unified_context_compiler import (
        UnifiedCompilerError,
        conservative_token_estimate,
    )

    archive, obligations = _budget_fixture(detail_count=3)

    # Two details cost 2556 tokens as a bare atom sum but 3045 tokens as the
    # real page.  A cap between the two must therefore split, not merge.
    cap = 3000
    manifest = build_consumer_workset_manifest_v2(
        archive,
        {"mech_budget": obligations},
        max_page_input_tokens=cap,
        max_obligations_per_page=8,
    )
    technical = [page for page in manifest.pages if page.page_kind == "technical"]
    assert len(technical) == len(obligations)
    assert all(page.token_estimate <= cap for page in technical)
    assert [page.token_estimate for page in technical] == [1563, 1563, 1563]
    # No evidence is dropped while rebuilding legal pages.
    packed = {atom_id for page in manifest.pages for atom_id in page.atom_ids}
    assert packed == set(manifest.worksets[0].required_atom_ids)
    technical_atoms = {
        atom_id for page in technical for atom_id in page.atom_ids
    }
    assert {
        atom_id for atom_id in manifest.worksets[0].required_atom_ids
        if atom_id.startswith(("detail:", "operation:"))
    } <= technical_atoms

    # The same graph under one cap that no single page can satisfy fails
    # closed with the offending obligation and its largest atoms.
    with pytest.raises(UnifiedCompilerError) as excinfo:
        build_consumer_workset_manifest_v2(
            archive,
            {"mech_budget": (obligations[0],)},
            max_page_input_tokens=200,
            max_obligations_per_page=8,
        )
    message = str(excinfo.value)
    assert "unified_atomic_page_over_budget:obligation:ob:0:" in message
    assert "unified_atomic_page_over_budget:contribution:detail:d:0:" in message
    assert "unified_atomic_page_over_budget:contribution:operation:op:0:0:" in message


def test_atom_sum_estimate_is_below_the_page_estimate() -> None:
    """R6: the fixture really distinguishes atom sums from page payloads."""

    from code2paper.agentic.unified_context_compiler import (
        _minimal_mechanism_header,
        conservative_token_estimate,
    )

    archive, _obligations = _budget_fixture(detail_count=3)
    atom_index = archive._atom_index()

    def _page_payload(atom_ids: tuple[str, ...]) -> dict:
        return {
            "archive_digest": archive.content_digest,
            "mechanism_header": _minimal_mechanism_header(
                archive.mechanism_atoms[0].payload
            ),
            "obligation_ids": [],
            "atoms": [
                dict(atom_index[atom_id].payload)
                | {"_atom_id": atom_id, "_atom_kind": atom_index[atom_id].atom_kind}
                for atom_id in atom_ids
            ],
            "projection_proof": {atom_id: atom_id for atom_id in atom_ids},
        }

    first = tuple(sorted(
        atom_id for atom_id in atom_index
        if atom_id.startswith(("detail:d:0", "operation:op:0"))
    ))
    second = tuple(sorted(
        atom_id for atom_id in atom_index
        if atom_id.startswith(("detail:d:1", "operation:op:1"))
    ))
    pair = first + second
    pair_atom_sum = sum(
        conservative_token_estimate(atom_index[atom_id].payload)
        for atom_id in pair
    )
    pair_page_tokens = conservative_token_estimate(_page_payload(pair))
    single_page_tokens = conservative_token_estimate(_page_payload(first))

    assert pair_atom_sum < 3000 < pair_page_tokens
    assert single_page_tokens <= 3000
    assert pair_atom_sum < pair_page_tokens


def _budget_profile(**overrides: int) -> dict[str, int]:
    profile = {
        "max_page_input_tokens": 3000,
        "max_total_input_tokens": 400000,
        "max_formalizer_calls": 8,
        "max_writer_calls": 8,
        "max_realizer_calls": 8,
        "max_binder_calls": 0,
        "max_obligations_per_page": 8,
        "max_formula_repair_calls": 2,
        "safety_margin_tokens": 1024,
        "prompt_token_reserve": 2048,
        "thinking_token_reserve": 0,
    }
    for role in ("formalizer", "writer", "realizer", "binder"):
        profile[f"output_token_reserve_{role}"] = 4096 if role != "binder" else 2048
        profile[f"max_request_input_tokens_{role}"] = 60000
        # R6/F4: the declared allowance that makes the planned per-invocation
        # input an upper bound for the role's actual request.
        profile[f"scaffolding_token_reserve_{role}"] = 4096 if role in {
            "writer", "realizer",
        } else 0
        profile[f"retry_reserve_input_tokens_{role}"] = 0
    profile.update(overrides)
    return profile


def _budget_envelope(**overrides: int):
    from code2paper.agentic.unified_context_compiler import (
        build_run_invocation_budget_envelope_v1,
    )

    profile = _budget_profile(**overrides)
    return build_run_invocation_budget_envelope_v1(
        profile_budget=profile,
        model_capabilities={"context_tokens": 131072},
        run_digest="sha256:run",
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
    )


def test_budget_envelope_requires_every_declared_field() -> None:
    """R6: no silent reserve, per-request cap or binder default."""

    from code2paper.agentic.unified_context_compiler import (
        UnifiedCompilerError,
        build_run_invocation_budget_envelope_v1,
    )

    for missing in (
        "max_binder_calls",
        "safety_margin_tokens",
        "prompt_token_reserve",
        "thinking_token_reserve",
        "output_token_reserve_writer",
        "max_request_input_tokens_formalizer",
        "scaffolding_token_reserve_writer",
    ):
        profile = _budget_profile()
        profile.pop(missing)
        with pytest.raises(UnifiedCompilerError) as excinfo:
            build_run_invocation_budget_envelope_v1(
                profile_budget=profile,
                model_capabilities={"context_tokens": 131072},
                run_digest="sha256:run",
                profile_digest="sha256:profile",
                model_identity_digest="sha256:model",
            )
        assert excinfo.value.failure_code == "unified_invocation_budget_missing"

    envelope = _budget_envelope()
    assert envelope.token_meter.method == "conservative_utf8_bytes_div_4"
    assert envelope.token_meter.unit == "tokens"
    assert envelope.model_context_tokens == 131072
    for role in ("formalizer", "writer", "realizer", "binder"):
        assert envelope.request_budget_by_role[role].role == role
        assert envelope.max_request_input_tokens_by_role[role] == 60000


def test_realizer_binding_disables_unbounded_reasoning_only_for_realizer() -> None:
    """The V2 Realizer serializer cannot spend its answer ceiling on thinking."""

    from types import SimpleNamespace

    from code2paper.agentic.unified_context_compiler import (
        bound_consumer_llm_config,
    )
    from code2paper.schemas import LLMConfig

    base = LLMConfig(
        model="test-model",
        max_output_tokens=12000,
        reasoning_effort="high",
        thinking_token_budget=512,
    )
    realizer = bound_consumer_llm_config(
        base,
        SimpleNamespace(role="realizer", max_output_tokens=4096),
    )
    formalizer = bound_consumer_llm_config(
        base,
        SimpleNamespace(role="formalizer", max_output_tokens=4096),
    )

    assert realizer.max_output_tokens == 4096
    assert realizer.reasoning_effort == "none"
    assert realizer.thinking_token_budget is None
    assert formalizer.max_output_tokens == 4096
    assert formalizer.reasoning_effort == "high"
    assert formalizer.thinking_token_budget == 512


def test_plan_rejects_request_over_declared_cap() -> None:
    """R6: the declared per-request cap bounds the plan, not just the send."""

    from code2paper.agentic.unified_context_compiler import (
        UnifiedCompilerError,
        build_consumer_invocation_plan_v1,
    )

    archive, obligations = _budget_fixture(detail_count=1)
    tight = _budget_envelope(max_request_input_tokens_formalizer=64)
    with pytest.raises(UnifiedCompilerError) as excinfo:
        build_consumer_invocation_plan_v1(
            _manifest_for_envelope(archive, obligations, tight),
            tight,
            phase="formalizer",
            plan_revision=1,
            profile_digest="sha256:profile",
            model_identity_digest="sha256:model",
            model_context_tokens=131072,
        )
    assert excinfo.value.failure_code == "unified_invocation_budget_exceeded"


def test_plan_measures_the_same_parts_the_send_boundary_measures() -> None:
    """R6: plan-time and send-time accounting use one meter and one cap."""

    from code2paper.agentic.unified_context_compiler import (
        account_unified_request_tokens,
        build_consumer_invocation_plan_v1,
        build_consumer_request_payload,
        consumer_response_json_schema,
        render_consumer_page_prompt,
    )

    archive, obligations = _budget_fixture(detail_count=1)
    envelope = _budget_envelope()
    manifest = _manifest_for_envelope(archive, obligations, envelope)
    plan = build_consumer_invocation_plan_v1(
        manifest,
        envelope,
        phase="formalizer",
        plan_revision=1,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )
    main = [item for item in plan.invocations if not item.is_repair]
    assert main, "the plan must contain a main formalizer invocation"
    page = manifest.page_by_id(main[0].page_id)
    budget = envelope.request_budget_by_role["formalizer"]
    send_side = account_unified_request_tokens(
        consumer_role="formalizer",
        rendered_prompt=render_consumer_page_prompt(
            page=page,
            role="formalizer",
            task_ids=main[0].task_ids,
            is_repair=False,
        ),
        input_payload=build_consumer_request_payload(
            page=page,
            role="formalizer",
            task_ids=main[0].task_ids,
            is_repair=False,
        ),
        response_schema=consumer_response_json_schema("formalizer"),
        request_budget=budget,
        max_input_tokens=envelope.max_request_input_tokens_by_role["formalizer"],
        model_context_tokens=envelope.model_context_tokens,
        safety_margin_tokens=envelope.safety_margin_tokens,
        meter=envelope.token_meter,
    )
    assert send_side.fits is True
    assert send_side.input_tokens == main[0].max_input_tokens


    assert main[0].max_output_tokens == budget.output_token_reserve

    # One measurement rule: the same parts measured with a real tokenizer
    # meter are not silently re-interpreted as conservative byte estimates.
    from code2paper.agentic.unified_context_models import model_tokenizer_meter

    class _Tokenizer:
        identity = "fixture-tokenizer"

        def encode(self, text: str) -> list[str]:
            return str(text).split()

    tokenizer_meter = model_tokenizer_meter("fixture-tokenizer")
    measured = account_unified_request_tokens(
        consumer_role="formalizer",
        rendered_prompt="alpha beta gamma",
        input_payload={"a": 1},
        response_schema={},
        request_budget=budget,
        max_input_tokens=envelope.max_request_input_tokens_by_role["formalizer"],
        model_context_tokens=envelope.model_context_tokens,
        safety_margin_tokens=envelope.safety_margin_tokens,
        meter=tokenizer_meter,
        tokenizer=_Tokenizer(),
    )
    assert measured.meter.method == "model_tokenizer"
    assert measured.meter.tokenizer_identity == "fixture-tokenizer"
    assert measured.system_prompt_tokens == 0
    assert measured.wrapper_reserve_tokens == budget.prompt_token_reserve


def test_realizer_request_contract_carries_page_local_formula_package_ids() -> None:
    """Formula bindings stay page-local at both plan and send boundaries."""

    from types import SimpleNamespace

    from code2paper.agentic.unified_context_compiler import (
        build_consumer_request_payload,
        render_consumer_page_prompt,
    )

    page = SimpleNamespace(
        mechanism_id="mech_formula",
        page_id="page:formula",
        technical_bytes_digest="sha256:page-formula",
        technical_payload={
            "section_id": "MA-S1",
            "formula_obligation_ids": ["ob:formula:1"],
            "formula_package_ids": ["pkg:formula:2", "pkg:formula:1"],
            "detail_ids": [],
            "atoms": [],
        },
    )

    payload = build_consumer_request_payload(
        page=page,
        role="realizer",
        task_ids=("MA-S1",),
        section_id="MA-S1",
    )
    contract = payload["response_contract"]
    assert contract["required_formula_package_ids"] == [
        "pkg:formula:1",
        "pkg:formula:2",
    ]
    assert "witness_kind=formula" in contract["required_formula_witness_rule"]
    prompt = render_consumer_page_prompt(
        page=page,
        role="realizer",
        task_ids=("MA-S1",),
        section_id="MA-S1",
    )
    assert "every required formula package ID" in prompt
    assert "formula witness" in prompt


def test_chat_template_meter_counts_the_actual_wire_sequence_and_requires_identity() -> None:
    """The model-owned meter must measure the client wire shape, not a dict proxy."""

    from code2paper.agentic.unified_context_compiler import (
        UnifiedCompilerError,
        account_unified_request_tokens,
    )
    from code2paper.agentic.unified_context_models import (
        model_chat_template_tokenizer_meter,
    )

    class _WireTokenizer:
        identity = "fixture-chat-template-v1"

        def encode(self, text: str) -> list[int]:
            return list(range(max(1, len(str(text).split()))))

        def encode_wire_request(self, **kwargs: object) -> list[int]:
            assert kwargs["response_mode"] == "native_json_schema"
            assert kwargs["enable_thinking"] is None
            return list(range(17))

    budget = _budget_envelope().request_budget_by_role["formalizer"]
    meter = model_chat_template_tokenizer_meter("fixture-chat-template-v1")
    accounting = account_unified_request_tokens(
        consumer_role="formalizer",
        rendered_prompt="system prompt",
        input_payload={"same": "wire"},
        response_schema={"type": "object"},
        request_budget=budget,
        max_input_tokens=64,
        model_context_tokens=131072,
        safety_margin_tokens=0,
        meter=meter,
        tokenizer=_WireTokenizer(),
    )
    assert accounting.rendered_prompt_tokens == 17
    assert accounting.input_payload_tokens > 0
    assert accounting.input_tokens == (
        17 + accounting.response_schema_tokens + budget.prompt_token_reserve
    )

    class _MissingIdentity(_WireTokenizer):
        identity = ""

    with pytest.raises(UnifiedCompilerError) as excinfo:
        account_unified_request_tokens(
            consumer_role="formalizer",
            rendered_prompt="system prompt",
            input_payload={"same": "wire"},
            response_schema={"type": "object"},
            request_budget=budget,
            max_input_tokens=64,
            model_context_tokens=131072,
            safety_margin_tokens=0,
            meter=meter,
            tokenizer=_MissingIdentity(),
        )
    assert excinfo.value.failure_code == "unified_invocation_budget_missing"


def test_declared_retry_reserve_is_added_once_to_the_run_lineage() -> None:
    """R6: bounded retries get explicit headroom without changing planned calls."""

    from code2paper.agentic.unified_context_compiler import (
        build_consumer_invocation_plan_v1,
        extend_writer_worksets_from_narrative_plan,
    )

    archive, obligations = _two_mechanism_fixture()
    envelope = _budget_envelope(retry_reserve_input_tokens_writer=1234)
    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    narrative_plan = _two_mechanism_section_plan(archive, envelope)
    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        narrative_plan,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
    )
    plan = build_consumer_invocation_plan_v1(
        writer_manifest,
        envelope,
        phase="writer",
        plan_revision=1,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )
    assert plan.reserved_input_tokens_by_role["writer"] == (
        plan.planned_input_tokens_by_role["writer"] + 1234
    )
    assert plan.planned_input_tokens_by_role["writer"] < (
        plan.reserved_input_tokens_by_role["writer"]
    )


def test_accounting_overflow_is_declared_by_cap_or_context() -> None:
    """R6: over-budget measurement is explicit and reproducible."""

    from code2paper.agentic.unified_context_compiler import (
        account_unified_request_tokens,
    )

    envelope = _budget_envelope()
    budget = envelope.request_budget_by_role["formalizer"]
    small = account_unified_request_tokens(
        consumer_role="formalizer",
        rendered_prompt="x" * 400,
        input_payload={},
        response_schema={},
        request_budget=budget,
        max_input_tokens=64,
        model_context_tokens=envelope.model_context_tokens,
        safety_margin_tokens=envelope.safety_margin_tokens,
        meter=envelope.token_meter,
    )
    assert small.fits is False
    assert small.overflow_tokens == small.input_tokens - 64

    wide = account_unified_request_tokens(
        consumer_role="formalizer",
        rendered_prompt="x" * 400,
        input_payload={},
        response_schema={},
        request_budget=budget,
        max_input_tokens=envelope.max_request_input_tokens_by_role["formalizer"],
        model_context_tokens=budget.output_token_reserve + 1,
        safety_margin_tokens=envelope.safety_margin_tokens,
        meter=envelope.token_meter,
    )
    assert wide.fits is False
    assert wide.overflow_tokens == (
        wide.input_tokens
        + budget.output_token_reserve
        + budget.thinking_token_reserve
        + envelope.safety_margin_tokens
        - (budget.output_token_reserve + 1)
    )


def _manifest_for_envelope(archive, obligations, envelope):
    """Build a manifest whose page cap matches the envelope contract."""

    return build_consumer_workset_manifest_v2(
        archive,
        {"mech_budget": obligations},
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )


def _two_mechanism_fixture():
    """Two independent mechanisms with one detail each, no source spans."""

    from code2paper.agentic.formalization_agent import MechanismFormulaObligationV1

    contexts = []
    obligations = {}
    for mechanism_id, detail_id in (
        ("mech_alpha", "d:alpha"),
        ("mech_beta", "d:beta"),
    ):
        operation = EvidenceOperationV1(
            operation_id=f"op:{mechanism_id}",
            predicate="compute_step",
            operands=(f"input_{mechanism_id}",),
            result=f"output_{mechanism_id}",
            source_span_id="",
            active_path_status="active_default",
        )
        detail = MechanismDetailV1(
            detail_id=detail_id,
            primary_mechanism_id=mechanism_id,
            order_index=0,
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
        repo_snapshot_id="repo:two",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:alignment",
        research_digest="sha256:research",
        contexts=tuple(contexts),
    )
    archive = build_unified_context_archive_v2(
        context_set, source_manifest_digest="sha256:manifest"
    )
    return archive, obligations


def _two_mechanism_section_plan(archive, envelope):
    """Build one section that owns paragraphs of two mechanisms."""

    from code2paper.agentic.method_architect import (
        NarrativeParagraphPlanV3,
        NarrativePlanV3,
        NarrativeSectionPlanV3,
        NarrativeUnitV1,
    )

    mechanism_ids = [atom.payload["mechanism_id"] for atom in archive.mechanism_atoms]
    assert len(mechanism_ids) == 2
    details_by_mechanism = {
        str(atom.payload["mechanism_id"]): [
            str(detail["detail_id"])
            for detail in (atom.payload.get("details", ()) or ())
        ]
        for atom in archive.mechanism_atoms
    }
    paragraphs = []
    for index, mechanism_id in enumerate(mechanism_ids):
        detail_ids = tuple(details_by_mechanism[mechanism_id])
        paragraph_id = f"MA-S1_p{index + 1}"
        paragraphs.append(NarrativeParagraphPlanV3(
            paragraph_id=paragraph_id,
            section_id="MA-S1",
            role="core_transformations",
            mechanism_id=mechanism_id,
            required_detail_ids=detail_ids,
            witness_contract={
                "schema_version": "1.0",
                "paragraph_id": paragraph_id,
                "rhetorical_goal": "core_transformations",
                "targets": [],
            },
        ))
    plan = NarrativePlanV3(
        plan_id="plan:two-mechanism",
        sections=(NarrativeSectionPlanV3(
            section_id="MA-S1",
            heading="Two mechanisms",
            mechanism_ids=tuple(mechanism_ids),
            paragraphs=tuple(paragraphs),
        ),),
        narrative_units=(NarrativeUnitV1(
            unit_id="unit_1",
            section_id="MA-S1",
            mechanism_context_ids=tuple(mechanism_ids),
            rhetorical_role="core_model",
            reader_question="How do both mechanisms work?",
            paragraph_ids=tuple(p.paragraph_id for p in paragraphs),
            required_detail_ids=tuple(
                detail_id
                for paragraph in paragraphs
                for detail_id in paragraph.required_detail_ids
            ),
            optional_detail_ids=(),
            formula_obligation_ids=(),
            suggested_depth="standard",
        ),),
        context_set_digest=archive.content_digest,
    )
    del envelope
    return plan


def test_multi_mechanism_section_plans_a_legal_join_page() -> None:
    """R7/F3: a multi-mechanism Writer join page is not a repair page."""

    from code2paper.agentic.unified_context_compiler import (
        build_consumer_invocation_plan_v1,
        extend_writer_worksets_from_narrative_plan,
    )

    archive, obligations = _two_mechanism_fixture()
    envelope = _budget_envelope()
    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    plan = _two_mechanism_section_plan(archive, envelope)
    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        plan,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
    )
    section_pages = [
        page for page in writer_manifest.pages
        if page.technical_payload.get("section_id") == "MA-S1"
    ]
    assert section_pages
    join_pages = [page for page in section_pages if page.page_kind == "join"]
    assert join_pages, "a two-mechanism section must compile a join page"
    assert all(
        "repair_obligation_id" not in page.technical_payload
        for page in join_pages
    )
    assert all(
        page.technical_payload.get("join_dependency_proof")
        for page in join_pages
    )

    writer_plan = build_consumer_invocation_plan_v1(
        writer_manifest,
        envelope,
        phase="writer",
        plan_revision=1,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )
    join_invocations = [
        invocation for invocation in writer_plan.invocations
        if invocation.page_id in {page.page_id for page in join_pages}
    ]
    assert join_invocations
    assert all(invocation.role == "writer" for invocation in join_invocations)
    assert all(not invocation.is_repair for invocation in join_invocations)


def test_writer_page_projection_preserves_paragraph_formula_package_scope() -> None:
    """A projected page carries the package IDs of its owning paragraph only."""

    from code2paper.agentic.unified_context_compiler import (
        extend_writer_worksets_from_narrative_plan,
    )

    archive, _obligations = _two_mechanism_fixture()
    envelope = _budget_envelope()
    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        {"mech_alpha": (), "mech_beta": ()},
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    plan = _two_mechanism_section_plan(archive, envelope)
    section = plan.sections[0]
    first = section.paragraphs[0].model_copy(update={
        "formula_package_ids": ("pkg:paragraph-local",),
    })
    plan = plan.model_copy(update={
        "sections": (section.model_copy(update={
            "paragraphs": (first, *section.paragraphs[1:]),
        }),),
    })

    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        plan,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
        formula_packages=(
            {
                "package_id": "pkg:paragraph-local",
                "source_detail_ids": (first.required_detail_ids[0],),
            },
        ),
    )
    local_pages = [
        page for page in writer_manifest.pages
        if "MA-S1_p1" in page.technical_payload.get("paragraph_ids", ())
    ]
    assert local_pages
    assert any(
        page.technical_payload.get("formula_package_ids")
        == ["pkg:paragraph-local"]
        for page in local_pages
    )
    assert any(
        page.technical_payload.get("formula_package_source_detail_ids")
        == {"pkg:paragraph-local": [first.required_detail_ids[0]]}
        for page in local_pages
    )


def test_writer_page_inputs_materialize_formula_consumer_route() -> None:
    """The frozen page request carries each package's narrative owner."""

    from code2paper.agentic.publication_method_writer import (
        _writer_section_inputs_v2,
    )
    from code2paper.agentic.unified_context_compiler import (
        build_consumer_invocation_plan_v1,
        extend_writer_worksets_from_narrative_plan,
    )

    archive, _obligations = _two_mechanism_fixture()
    envelope = _budget_envelope()
    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        {"mech_alpha": (), "mech_beta": ()},
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    plan = _two_mechanism_section_plan(archive, envelope)
    section = plan.sections[0]
    owner = section.paragraphs[0]
    package = {
        "package_id": "pkg:paragraph-route",
        "mechanism_id": owner.mechanism_id,
        "source_detail_ids": (owner.required_detail_ids[0],),
        "satisfied_obligation_ids": (),
    }
    plan = plan.model_copy(update={
        "sections": (section.model_copy(update={
            "paragraphs": (owner.model_copy(update={
                "formula_package_ids": (package["package_id"],),
            }), *section.paragraphs[1:]),
        }),),
    })
    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        plan,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
        formula_packages=(package,),
    )
    writer_plan = build_consumer_invocation_plan_v1(
        writer_manifest,
        envelope,
        phase="writer",
        plan_revision=1,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )

    inputs = _writer_section_inputs_v2(
        narrative_plan=plan,
        formula_packages=(package,),
        consumer_workset_manifest=writer_manifest,
        consumer_invocation_plan=writer_plan,
    )
    routed = [
        item
        for page_input in inputs
        for item in (page_input.prompt_payload.get("formula_packages") or ())
        if item.get("package_id") == package["package_id"]
    ]
    assert len(routed) == 1
    assert routed[0]["consumer_paragraph_id"] == owner.paragraph_id
    assert routed[0]["package_id"] in (
        inputs[0].prompt_payload["binding_contract"]["allowed_formula_package_ids"]
        if inputs else ()
    ) or any(
        routed[0]["package_id"] in (
            item.prompt_payload["binding_contract"]["allowed_formula_package_ids"]
        )
        for item in inputs
    )


def test_retry_headroom_is_carried_into_each_phase_lineage() -> None:
    """Writer/Realizer retries stay reserved while later primaries remain protected."""

    from code2paper.agentic.unified_context_compiler import (
        build_consumer_invocation_plan_v1,
        extend_writer_worksets_from_narrative_plan,
    )

    archive, obligations = _two_mechanism_fixture()
    envelope = _budget_envelope(
        retry_reserve_input_tokens_writer=400,
        retry_reserve_input_tokens_realizer=100,
    )
    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    narrative_plan = _two_mechanism_section_plan(archive, envelope)
    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        narrative_plan,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
    )
    formalizer_plan = build_consumer_invocation_plan_v1(
        base_manifest,
        envelope,
        phase="formalizer",
        plan_revision=1,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )
    writer_plan = build_consumer_invocation_plan_v1(
        writer_manifest,
        envelope,
        phase="writer",
        parent_plan=formalizer_plan,
        plan_revision=2,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )
    realizer_plan = build_consumer_invocation_plan_v1(
        writer_manifest,
        envelope,
        phase="realizer",
        parent_plan=writer_plan,
        plan_revision=3,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )

    assert writer_plan.reserved_input_tokens_by_role["writer"] == (
        writer_plan.planned_input_tokens_by_role["writer"] + 400
    )
    assert realizer_plan.reserved_input_tokens_by_role["realizer"] == (
        realizer_plan.planned_input_tokens_by_role["realizer"] + 100
    )
    assert sum(realizer_plan.reserved_input_tokens_by_role.values()) <= (
        envelope.max_total_input_tokens
    )


def test_child_plan_inherits_only_activated_parent_invocation_slots() -> None:
    """Untriggered Formalizer repairs do not consume downstream reservation."""

    from code2paper.agentic.unified_context_compiler import (
        build_consumer_invocation_plan_v1,
        extend_writer_worksets_from_narrative_plan,
    )

    archive, obligations = _two_mechanism_fixture()
    envelope = _budget_envelope()
    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    narrative_plan = _two_mechanism_section_plan(archive, envelope)
    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        narrative_plan,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
    )
    formalizer_plan = build_consumer_invocation_plan_v1(
        base_manifest,
        envelope,
        phase="formalizer",
        plan_revision=1,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )
    active_ids = tuple(
        invocation.invocation_id
        for invocation in formalizer_plan.invocations
        if not invocation.is_repair
    )
    writer_plan = build_consumer_invocation_plan_v1(
        writer_manifest,
        envelope,
        phase="writer",
        parent_plan=formalizer_plan,
        parent_active_invocation_ids=active_ids,
        plan_revision=2,
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        model_context_tokens=131072,
    )

    expected_formalizer_tokens = sum(
        invocation.max_input_tokens
        for invocation in formalizer_plan.invocations
        if not invocation.is_repair
    )
    assert writer_plan.reserved_calls_by_role["formalizer"] == len(active_ids)
    assert writer_plan.reserved_input_tokens_by_role["formalizer"] == (
        expected_formalizer_tokens
    )
    assert writer_plan.reserved_input_tokens_by_role["formalizer"] < (
        formalizer_plan.reserved_input_tokens_by_role["formalizer"]
    )


def test_forged_join_identity_fails_closed() -> None:
    """R7/F3: a join page must prove exactly one consumer identity."""

    from code2paper.agentic.unified_context_compiler import (
        UnifiedCompilerError,
        build_consumer_invocation_plan_v1,
    )

    archive, obligations = _two_mechanism_fixture()
    envelope = _budget_envelope()
    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    plan = _two_mechanism_section_plan(archive, envelope)
    from code2paper.agentic.unified_context_compiler import (
        extend_writer_worksets_from_narrative_plan,
    )

    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        plan,
        max_page_input_tokens=envelope.max_page_input_tokens,
        archive=archive,
    )
    join_page = next(
        page for page in writer_manifest.pages
        if page.page_kind == "join"
        and page.technical_payload.get("section_id") == "MA-S1"
    )

    # A section join page that claims a formula repair identity is refused.
    forged_repair = join_page.model_copy(update={
        "technical_payload": dict(join_page.technical_payload)
        | {"repair_obligation_id": "ob:forged"},
    })
    forged_manifest = writer_manifest.model_copy(update={
        "pages": tuple(
            forged_repair if page.page_id == join_page.page_id else page
            for page in writer_manifest.pages
        ),
    })
    with pytest.raises(UnifiedCompilerError) as excinfo:
        build_consumer_invocation_plan_v1(
            forged_manifest,
            envelope,
            phase="writer",
            plan_revision=1,
            profile_digest="sha256:profile",
            model_identity_digest="sha256:model",
            model_context_tokens=131072,
        )
    assert excinfo.value.failure_code == "unified_page_projection_incomplete"

    # A join page with neither identity is refused as well.
    proof = dict(join_page.technical_payload.get("join_dependency_proof") or {})
    forged_orphan = join_page.model_copy(update={
        "technical_payload": {
            key: value
            for key, value in join_page.technical_payload.items()
            if key != "join_dependency_proof"
        },
    })
    orphan_manifest = writer_manifest.model_copy(update={
        "pages": tuple(
            forged_orphan if page.page_id == join_page.page_id else page
            for page in writer_manifest.pages
        ),
    })
    with pytest.raises(UnifiedCompilerError) as excinfo2:
        build_consumer_invocation_plan_v1(
            orphan_manifest,
            envelope,
            phase="writer",
            plan_revision=1,
            profile_digest="sha256:profile",
            model_identity_digest="sha256:model",
            model_context_tokens=131072,
        )
    assert excinfo2.value.failure_code == "unified_page_projection_incomplete"
    assert proof, "the original join page carries a dependency proof"


def test_run_reservation_is_debited_by_retries_and_resume() -> None:
    """R6/F4: retries and resumed attempts consume the same reservation."""

    from code2paper.agentic.unified_context_compiler import (
        remaining_run_input_tokens,
        spend_input_tokens_by_role,
    )
    from code2paper.agentic.unified_context_models import (
        ActualRequestReceiptV2,
        conservative_token_meter,
    )

    meter = conservative_token_meter()

    def _receipt(
        *,
        role: str,
        plan_digest: str,
        input_tokens: int,
        attempt: int,
    ) -> ActualRequestReceiptV2:
        from code2paper.agentic.unified_context_compiler import (
            account_unified_request_tokens,
        )
        from code2paper.agentic.unified_context_models import RoleRequestBudgetV1

        accounting = account_unified_request_tokens(
            consumer_role=role,
            rendered_prompt="x" * ((input_tokens - 1) * 4),
            input_payload={},
            response_schema={},
            request_budget=RoleRequestBudgetV1(
                role=role,
                prompt_token_reserve=0,
                output_token_reserve=1024,
                thinking_token_reserve=0,
                scaffolding_token_reserve=0,
            ),
            max_input_tokens=1_000_000,
            model_context_tokens=131072,
            safety_margin_tokens=0,
            meter=meter,
            scaffolding_reserve_tokens=0,
        )
        assert accounting.input_tokens >= input_tokens
        return ActualRequestReceiptV2(
            invocation_id=f"inv:{attempt}",
            attempt=attempt,
            consumer_role=role,
            phase=role,
            workset_id="workset:test",
            task_ids=("task",),
            mechanism_id="mech:test",
            page_id=f"page:{attempt}",
            actual_technical_bytes_digest="sha256:bytes",
            actual_request_envelope_digest="sha256:envelope",
            response_digest="sha256:response",
            model_identity_digest="sha256:model",
            started_at_unix=1.0,
            finished_at_unix=2.0,
            delivery_status="accepted",
            task_status="complete",
            succeeded_task_ids=("task",),
            token_accounting=accounting,
            upstream_archive_digest="sha256:archive",
            upstream_workset_manifest_digest="sha256:manifest",
            upstream_plan_digest=plan_digest,
        )

    reservations = {"writer": 30_000}
    first = _receipt(role="writer", plan_digest="sha256:plan:a", input_tokens=12_000, attempt=1)
    retry = _receipt(role="writer", plan_digest="sha256:plan:a", input_tokens=11_000, attempt=2)
    other_plan = _receipt(role="writer", plan_digest="sha256:plan:b", input_tokens=9_000, attempt=1)

    spent = spend_input_tokens_by_role(
        (first, retry, other_plan), plan_digests=("sha256:plan:a",)
    )
    expected = (
        first.token_accounting.input_tokens
        + retry.token_accounting.input_tokens
    )
    assert spent == {"writer": expected}
    assert "sha256:plan:b" not in str(first.upstream_plan_digest)
    assert remaining_run_input_tokens(
        reserved_input_tokens_by_role=reservations,
        spent_input_tokens_by_role=spent,
        role="writer",
    ) == reservations["writer"] - expected
    # The retry consumed the same reservation the first attempt did.
    assert remaining_run_input_tokens(
        reserved_input_tokens_by_role=reservations,
        spent_input_tokens_by_role=spend_input_tokens_by_role(
            (first,), plan_digests=("sha256:plan:a",)
        ),
        role="writer",
    ) > remaining_run_input_tokens(
        reserved_input_tokens_by_role=reservations,
        spent_input_tokens_by_role=spent,
        role="writer",
    )

    # A resumed run recomputes the same spend from durable receipts instead of
    # starting from a fresh allowance.
    resumed_spent = spend_input_tokens_by_role(
        (first, retry, other_plan), plan_digests=("sha256:plan:a",)
    )
    assert resumed_spent == spent
    assert remaining_run_input_tokens(
        reserved_input_tokens_by_role=reservations,
        spent_input_tokens_by_role=resumed_spent,
        role="writer",
    ) == reservations["writer"] - expected


def test_run_budget_future_primary_reservation_excludes_repairs(tmp_path) -> None:
    """A persisted phase plan protects future primary calls, not repair slots."""

    from types import SimpleNamespace

    from code2paper.agentic.unified_invocation_ledger import (
        read_run_budget_state,
        register_invocation_plan,
    )

    root = tmp_path / "invocations"
    plan = SimpleNamespace(
        content_digest="sha256:plan:future-primary",
        plan_revision=1,
        reserved_input_tokens_by_role={"writer": 600},
        invocations=(
            SimpleNamespace(
                invocation_id="inv:writer:primary",
                max_input_tokens=100,
                role="writer",
                phase="writer",
                is_repair=False,
            ),
            SimpleNamespace(
                invocation_id="inv:writer:repair",
                max_input_tokens=500,
                role="writer",
                phase="writer",
                is_repair=True,
            ),
        ),
    )

    register_invocation_plan(root, plan)
    state = read_run_budget_state(root)

    assert state["future_primary_reservations"] == {
        "inv:writer:primary": {"role": "writer", "input_tokens": 100},
    }
    assert state["future_primary_input_tokens_by_role"] == {"writer": 100}


def test_run_budget_repair_cannot_consume_future_primary_headroom(tmp_path) -> None:
    """The 70 + 20 + 20 cross-phase counterexample is rejected pre-send."""

    from types import SimpleNamespace

    from code2paper.agentic.unified_context_compiler import (
        account_unified_request_tokens,
    )
    from code2paper.agentic.unified_context_models import (
        ActualRequestReceiptV2,
        RoleRequestBudgetV1,
        conservative_token_meter,
    )
    from code2paper.agentic.unified_invocation_ledger import (
        check_run_budget_before_send,
        publish_attempt_completed,
        register_invocation_plan,
    )

    root = tmp_path / "invocations"
    accounting = account_unified_request_tokens(
        consumer_role="writer",
        rendered_prompt="x" * 280,
        input_payload={},
        response_schema={},
        request_budget=RoleRequestBudgetV1(
            role="writer",
            prompt_token_reserve=0,
            output_token_reserve=1024,
            thinking_token_reserve=0,
            scaffolding_token_reserve=0,
        ),
        max_input_tokens=1_000_000,
        model_context_tokens=131072,
        safety_margin_tokens=0,
        meter=conservative_token_meter(),
        scaffolding_reserve_tokens=0,
    )
    spent = ActualRequestReceiptV2(
        invocation_id="inv:writer:spent",
        attempt=1,
        consumer_role="writer",
        phase="writer",
        workset_id="workset:test",
        task_ids=("task:spent",),
        mechanism_id="mech:test",
        page_id="page:spent",
        actual_technical_bytes_digest="sha256:bytes",
        actual_request_envelope_digest="sha256:envelope",
        response_digest="sha256:response",
        model_identity_digest="sha256:model",
        started_at_unix=1.0,
        finished_at_unix=2.0,
        delivery_status="accepted",
        task_status="complete",
        succeeded_task_ids=("task:spent",),
        token_accounting=accounting,
        upstream_archive_digest="sha256:archive",
        upstream_workset_manifest_digest="sha256:manifest",
        upstream_plan_digest="sha256:plan:spent",
    )
    publish_attempt_completed(root, spent)

    future_plan = SimpleNamespace(
        content_digest="sha256:plan:future-primary-guard",
        plan_revision=1,
        reserved_input_tokens_by_role={"writer": 40},
        invocations=(
            SimpleNamespace(
                invocation_id="inv:writer:future-primary",
                max_input_tokens=20,
                role="writer",
                phase="writer",
                is_repair=False,
            ),
            SimpleNamespace(
                invocation_id="inv:writer:future-repair",
                max_input_tokens=20,
                role="writer",
                phase="writer",
                is_repair=True,
            ),
        ),
    )
    register_invocation_plan(root, future_plan)
    envelope = SimpleNamespace(
        max_calls_by_role={"writer": 10},
        max_total_input_tokens=accounting.input_tokens + 39,
        max_input_tokens_by_role={"writer": 1_000_000},
        retry_reserve_input_tokens_by_role={"writer": 20},
    )

    failures = check_run_budget_before_send(
        root,
        envelope,
        role="writer",
        request_input_tokens=20,
        current_reserved_input_tokens=0,
        current_attempt_recorded=False,
        invocation_id="inv:writer:future-repair",
        is_content_repair=True,
    )

    assert any(
        code.startswith("unified_invocation_budget_exceeded:total_input_tokens:")
        for code in failures
    )


def test_run_budget_repair_reserve_is_hard_pre_send_boundary(tmp_path) -> None:
    """A repair above its declared reserve is refused before transport."""

    from code2paper.agentic.unified_invocation_ledger import (
        check_run_budget_before_send,
    )

    envelope = type("Envelope", (), {
        "max_calls_by_role": {"writer": 10},
        "max_total_input_tokens": 1_000,
        "max_input_tokens_by_role": {"writer": 1_000},
        "retry_reserve_input_tokens_by_role": {"writer": 20},
    })()
    failures = check_run_budget_before_send(
        tmp_path / "invocations",
        envelope,
        role="writer",
        request_input_tokens=21,
        current_reserved_input_tokens=0,
        current_attempt_recorded=False,
        invocation_id="inv:writer:repair",
        is_content_repair=True,
    )

    assert any(
        code.endswith("retry_reserve:writer:21>20")
        for code in failures
    )


def test_run_budget_marks_missing_provider_usage_without_zeroing_spend(tmp_path) -> None:
    """Missing provider usage remains a partial, conservatively charged run."""

    from code2paper.agentic.unified_context_compiler import (
        account_unified_request_tokens,
    )
    from code2paper.agentic.unified_context_models import (
        ActualRequestReceiptV2,
        RoleRequestBudgetV1,
        conservative_token_meter,
    )
    from code2paper.agentic.unified_invocation_ledger import (
        publish_attempt_completed,
        read_run_budget_state,
    )

    accounting = account_unified_request_tokens(
        consumer_role="writer",
        rendered_prompt="x" * 400,
        input_payload={"page": "frozen"},
        response_schema={},
        request_budget=RoleRequestBudgetV1(
            role="writer",
            prompt_token_reserve=0,
            output_token_reserve=1024,
            thinking_token_reserve=0,
            scaffolding_token_reserve=0,
        ),
        max_input_tokens=1_000_000,
        model_context_tokens=131072,
        safety_margin_tokens=0,
        meter=conservative_token_meter(),
    )
    receipt = ActualRequestReceiptV2(
        invocation_id="inv:writer:missing-usage",
        attempt=1,
        consumer_role="writer",
        phase="writer",
        workset_id="workset:test",
        task_ids=("task:one",),
        mechanism_id="mech:test",
        page_id="page:test",
        actual_technical_bytes_digest="sha256:bytes",
        actual_request_envelope_digest="sha256:envelope",
        response_digest="sha256:response",
        model_identity_digest="sha256:model",
        started_at_unix=1.0,
        finished_at_unix=2.0,
        delivery_status="accepted",
        task_status="complete",
        succeeded_task_ids=("task:one",),
        token_accounting=accounting,
        upstream_archive_digest="sha256:archive",
        upstream_workset_manifest_digest="sha256:manifest",
        upstream_plan_digest="sha256:plan",
        provider_usage=None,
    )
    root = tmp_path / "invocations"
    publish_attempt_completed(root, receipt)

    state = read_run_budget_state(root)

    assert state["provider_usage_status"] == "partial"
    assert state["provider_usage_missing_call_count"] == 1
    assert state["provider_usage_missing_input_tokens"] == accounting.input_tokens
    assert state["spent_input_tokens_by_role"] == {"writer": accounting.input_tokens}


def test_pre_send_rejection_is_audited_but_not_charged_as_spend() -> None:
    """A measured page rejected before transport must not debit the run."""

    from code2paper.agentic.unified_context_compiler import spend_input_tokens_by_role
    from types import SimpleNamespace

    accounting = SimpleNamespace(input_tokens=12_000)
    rejected = SimpleNamespace(
        consumer_role="writer",
        token_accounting=accounting,
        sent_to_caller=False,
    )
    provider_failure = SimpleNamespace(
        consumer_role="writer",
        token_accounting=accounting,
        sent_to_caller=True,
    )

    assert spend_input_tokens_by_role((rejected,)) == {}
    assert spend_input_tokens_by_role((provider_failure,)) == {
        "writer": 12_000,
    }


def test_paragraph_page_split_conserves_the_full_witness_contract() -> None:
    """R7 correction: a legal page split must not empty the witness contract.

    The second review's repro: formal ``detail:`` ids plus detail/atom targets
    went through the real plan builder and page revision, and every fragment
    came back with `targets: []` while the page budget, the detail count and
    the schema validator all still passed.  The split now re-parents targets by
    ``target_kind`` with canonical ids and fails closed when the contract
    multiset changes.
    """

    import json

    from code2paper.agentic.method_architect import (
        build_narrative_plan_v3,
        validate_narrative_plan,
    )
    from code2paper.agentic.unified_context_compiler import (
        fit_narrative_plan_to_page_budget,
    )

    fixture = _budget_fixture(detail_count=3, operations_per_detail=8)
    archive, _obligations = fixture
    raw = json.dumps(archive.mechanism_atoms[0].payload)
    for index in range(3):
        raw = raw.replace(f'"d:{index}"', f'"detail:fixture:{index}"')

    def _clear_derived_digests(value):
        if isinstance(value, dict):
            return {
                key: _clear_derived_digests(item)
                for key, item in value.items()
                if key not in ("content_digest", "source_context_digest")
            }
        if isinstance(value, list):
            return [_clear_derived_digests(item) for item in value]
        return value

    contexts = MechanismContextSetV1(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        intent_digest="i",
        alignment_digest="a",
        research_digest="r",
        contexts=(
            MechanismContextV1.model_validate(_clear_derived_digests(json.loads(raw))),
        ),
    )
    archive = build_unified_context_archive_v2(
        contexts, source_manifest_digest="sha256:manifest"
    )
    plan, _trace = build_narrative_plan_v3(contexts=contexts)
    revised, failures, diagnostics = fit_narrative_plan_to_page_budget(
        plan, archive=archive, max_page_input_tokens=700
    )

    assert diagnostics["split_paragraphs"], "the fixture must trigger a split"
    assert failures == ()
    assert validate_narrative_plan(revised, contexts) == ()

    def _targets(paragraph) -> list[str]:
        payloads = [
            target.model_dump(mode="json")
            if hasattr(target, "model_dump")
            else dict(target)
            for target in (paragraph.witness_contract.get("targets", ()) or ())
        ]
        return sorted(json.dumps(item, sort_keys=True) for item in payloads)

    before = {
        paragraph.paragraph_id: (
            tuple(paragraph.required_detail_ids),
            _targets(paragraph),
        )
        for section in plan.sections
        for paragraph in section.paragraphs
    }
    after_fragments: dict[str, list[Any]] = {}
    for section in revised.sections:
        for paragraph in section.paragraphs:
            for original_id in before:
                if paragraph.paragraph_id.startswith(f"{original_id}__f"):
                    after_fragments.setdefault(original_id, []).append(paragraph)
    for original_id, (required, targets) in before.items():
        fragments = after_fragments.get(original_id, [])
        assert fragments, original_id
        assert sorted(
            detail
            for fragment in fragments
            for detail in fragment.required_detail_ids
        ) == sorted(required)
        assert sorted(
            target
            for fragment in fragments
            for target in _targets(fragment)
        ) == targets, original_id
        kinds = set()
        owned_details = {
            str(value).removeprefix("detail:")
            for fragment in fragments
            for value in (
                *tuple(fragment.required_detail_ids),
                *tuple(fragment.optional_detail_ids),
            )
        }
        for fragment in fragments:
            for target in (fragment.witness_contract.get("targets", ()) or ()):
                payload = (
                    target.model_dump(mode="json")
                    if hasattr(target, "model_dump")
                    else dict(target)
                )
                kind = str(payload.get("target_kind") or "")
                kinds.add(kind)
                # The target must belong to the fragment that carries it, which
                # is what the Writer request projection groups on.
                owner = str(
                    payload.get("detail_id")
                    if kind == "atom"
                    else payload.get("target_id")
                ).removeprefix("detail:")
                assert owner in owned_details, (fragment.paragraph_id, owner)
        assert kinds == {"detail", "atom"}


def test_request_measurement_rebuilds_pages_and_conserves_formula_dependencies() -> None:
    """An exact request overflow revises legal pages before Writer admission.

    The conservative archive estimate is deliberately made permissive here;
    only the request estimator rejects a multi-detail page.  This exercises
    the production recovery seam rather than the low-level Writer caller: the
    revised plan, page identities, formula ownership, and witness targets must
    all be rebuilt together.
    """

    import json

    from code2paper.agentic.formalization_agent import (
        MechanismFormulaObligationV1,
    )
    from code2paper.agentic.method_architect import (
        NarrativePlanV3,
        build_narrative_plan_v3,
        validate_narrative_plan,
    )
    from code2paper.agentic.unified_context_compiler import (
        extend_writer_worksets_from_narrative_plan,
        fit_narrative_plan_to_page_budget,
    )

    archive, raw_obligations = _budget_fixture(
        detail_count=3,
        operations_per_detail=8,
    )
    context = MechanismContextV1.model_validate(
        archive.mechanism_atoms[0].payload
    )
    context_set = MechanismContextSetV1(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:alignment",
        research_digest="sha256:research",
        contexts=(context,),
    )
    obligations = tuple(
        MechanismFormulaObligationV1.model_validate(
            obligation.model_dump(mode="json", exclude={"content_digest"})
            | {"primary_detail_id": obligation.source_detail_ids[0]}
        )
        for obligation in raw_obligations
    )
    narrative_plan, _trace = build_narrative_plan_v3(contexts=context_set)
    plan_payload = narrative_plan.model_dump(mode="json")
    formula_ids = [obligation.obligation_id for obligation in obligations]
    for section in plan_payload["sections"]:
        for paragraph in section["paragraphs"]:
            paragraph["formula_obligation_ids"] = formula_ids
            paragraph.pop("content_digest", None)
        section.pop("content_digest", None)
    for unit in plan_payload["narrative_units"]:
        unit["formula_obligation_ids"] = formula_ids
        unit.pop("content_digest", None)
    plan_payload.pop("content_digest", None)
    narrative_plan = NarrativePlanV3.model_validate(plan_payload)

    def _request_tokens(page, _section_id, _rows) -> int:
        # The full page fits the conservative archive cap, but a request that
        # carries more than one detail exceeds the actual provider cap.
        return (
            1_000
            if len(page.technical_payload.get("detail_ids", ())) > 1
            else 100
        )

    revised, failures, diagnostics = fit_narrative_plan_to_page_budget(
        narrative_plan,
        archive=archive,
        max_page_input_tokens=100_000,
        formula_obligations=obligations,
        request_token_estimator=_request_tokens,
        max_request_input_tokens=500,
    )
    assert failures == ()
    assert diagnostics["split_paragraphs"]
    assert validate_narrative_plan(revised, context_set) == ()

    revised_paragraphs = [
        paragraph
        for section in revised.sections
        for paragraph in section.paragraphs
    ]
    assert [
        tuple(paragraph.required_detail_ids)
        for paragraph in revised_paragraphs
    ] == [("d:0",), ("d:1",), ("d:2",)]
    def _target_json(target: Any) -> str:
        payload = (
            target.model_dump(mode="json")
            if hasattr(target, "model_dump")
            else dict(target)
        )
        return json.dumps(payload, sort_keys=True)

    before_targets = sorted(
        _target_json(target)
        for section in narrative_plan.sections
        for paragraph in section.paragraphs
        for target in paragraph.witness_contract.get("targets", ())
    )
    after_targets = sorted(
        _target_json(target)
        for paragraph in revised_paragraphs
        for target in paragraph.witness_contract.get("targets", ())
    )
    assert after_targets == before_targets

    base_manifest = build_consumer_workset_manifest_v2(
        archive,
        {"mech_budget": obligations},
        max_page_input_tokens=100_000,
        max_obligations_per_page=8,
    )
    writer_manifest = extend_writer_worksets_from_narrative_plan(
        base_manifest,
        revised,
        max_page_input_tokens=100_000,
        archive=archive,
        formula_obligations=obligations,
        request_token_estimator=_request_tokens,
        max_request_input_tokens=500,
    )
    writer_pages = [
        page
        for page in writer_manifest.pages
        if page.technical_payload.get("section_id")
    ]
    assert len(writer_pages) == 3
    assert all(
        _request_tokens(page, "sec_method_1", ()) <= 500
        for page in writer_pages
    )
    assert {
        detail_id
        for page in writer_pages
        for detail_id in page.technical_payload.get("detail_ids", ())
    } == {"d:0", "d:1", "d:2"}
    assert {
        obligation_id
        for page in writer_pages
        for obligation_id in page.technical_payload.get(
            "formula_obligation_ids", ()
        )
    } == set(formula_ids)
    section_workset = next(
        workset
        for workset in writer_manifest.worksets
        if workset.task_kind == "section"
    )
    assert set(section_workset.required_page_ids) == {
        page.page_id for page in writer_pages
    }
    assert set(section_workset.required_atom_ids) <= {
        atom_id for page in writer_pages for atom_id in page.atom_ids
    }


def test_run_wide_debit_covers_previous_revisions(tmp_path: Path) -> None:
    """R6 correction: an earlier revision's spend stays inside the bound.

    The second review's repro: an old plan consumed 900 against a cumulative
    reservation of 2000, but the caller filtered receipts by the *current* plan
    digest, so the bound reported the full 2000 again.
    """

    from code2paper.agentic.unified_context_compiler import (
        account_unified_request_tokens,
        remaining_run_input_tokens,
        spend_input_tokens_by_role,
    )
    from code2paper.agentic.unified_context_models import (
        ActualRequestReceiptV2,
        RoleRequestBudgetV1,
        conservative_token_meter,
    )
    from code2paper.agentic.unified_invocation_ledger import (
        publish_attempt_completed,
        read_all_completed_receipts,
    )

    meter = conservative_token_meter()

    def _receipt(*, plan_digest: str, invocation_id: str, tokens: int):
        accounting = account_unified_request_tokens(
            consumer_role="writer",
            rendered_prompt="x" * (tokens * 4),
            input_payload={},
            response_schema={},
            request_budget=RoleRequestBudgetV1(
                role="writer",
                prompt_token_reserve=0,
                output_token_reserve=1024,
                thinking_token_reserve=0,
                scaffolding_token_reserve=0,
            ),
            max_input_tokens=1_000_000,
            model_context_tokens=131072,
            safety_margin_tokens=0,
            meter=meter,
            scaffolding_reserve_tokens=0,
        )
        return ActualRequestReceiptV2(
            invocation_id=invocation_id,
            attempt=1,
            consumer_role="writer",
            phase="writer",
            workset_id="workset:test",
            task_ids=("task",),
            mechanism_id="mech:test",
            page_id=f"page:{invocation_id}",
            actual_technical_bytes_digest="sha256:bytes",
            actual_request_envelope_digest="sha256:envelope",
            response_digest="sha256:response",
            model_identity_digest="sha256:model",
            started_at_unix=1.0,
            finished_at_unix=2.0,
            delivery_status="accepted",
            task_status="complete",
            succeeded_task_ids=("task",),
            token_accounting=accounting,
            upstream_archive_digest="sha256:archive",
            upstream_workset_manifest_digest="sha256:manifest",
            upstream_plan_digest=plan_digest,
        )

    root = tmp_path / "invocations"
    old = _receipt(
        plan_digest="sha256:plan:old", invocation_id="inv:writer:old", tokens=900
    )
    new = _receipt(
        plan_digest="sha256:plan:new", invocation_id="inv:writer:new", tokens=300
    )
    publish_attempt_completed(root, old)
    publish_attempt_completed(root, new)

    # The product callers no longer filter by plan digest: the run reservation
    # is debited by the whole revision lineage.
    spent = spend_input_tokens_by_role(
        read_all_completed_receipts(root, strict=True)
    )
    expected = (
        old.token_accounting.input_tokens + new.token_accounting.input_tokens
    )
    assert spent == {"writer": expected}
    assert remaining_run_input_tokens(
        reserved_input_tokens_by_role={"writer": 2000},
        spent_input_tokens_by_role=spent,
        role="writer",
    ) == 2000 - expected


def test_unsettled_orphan_attempt_reads_its_original_plan(tmp_path: Path) -> None:
    """R6 correction: an orphaned started attempt keeps its own reserve."""

    from types import SimpleNamespace

    from code2paper.agentic.unified_context_models import (
        InvocationAttemptStartedV1,
    )
    from code2paper.agentic.unified_invocation_ledger import (
        publish_attempt_started,
        register_invocation_plan,
        unsettled_started_attempt_records,
        unsettled_started_attempts,
    )

    root = tmp_path / "invocations"
    old_plan = SimpleNamespace(
        content_digest="sha256:plan:old",
        reserved_input_tokens_by_role={"writer": 2000},
        invocations=(SimpleNamespace(
            invocation_id="inv:writer:old-page",
            max_input_tokens=900,
            role="writer",
            phase="writer",
            page_id="page:old",
        ),),
    )
    register_invocation_plan(root, old_plan)
    publish_attempt_started(
        root,
        InvocationAttemptStartedV1(
            invocation_id="inv:writer:old-page",
            attempt=1,
            plan_digest="sha256:plan:old",
            page_id="page:old",
            expected_technical_bytes_digest="sha256:bytes",
            expected_request_envelope_digest="sha256:envelope",
            model_identity_digest="sha256:model",
            started_at_unix=1.0,
        ),
    )
    new_plan = SimpleNamespace(
        content_digest="sha256:plan:new",
        reserved_input_tokens_by_role={"writer": 2000},
        invocations=(SimpleNamespace(
            invocation_id="inv:writer:new-page",
            max_input_tokens=1000,
            role="writer",
            phase="writer",
            page_id="page:new",
        ),),
    )
    records = unsettled_started_attempt_records(root, new_plan)
    assert len(records) == 1
    assert records[0].plan_source == "recorded_plan"
    assert records[0].planned_input_tokens == 900
    assert unsettled_started_attempts(root, new_plan) == (
        (records[0].invocation_id, 1, 900),
    )

    # Without the durable plan record the attempt is honestly unmetered, so a
    # caller can block instead of reserving zero.
    (root / "plans").rename(root / "plans-hidden")
    unknown = unsettled_started_attempt_records(root, new_plan)
    assert len(unknown) == 1
    assert unknown[0].plan_source == "unknown"


def test_same_invocation_across_revisions_keeps_its_own_allowance(
    tmp_path: Path,
) -> None:
    """R6 correction (third review): an old attempt keeps its original reserve.

    The same invocation id can survive a revision with a smaller allowance.  A
    probe with 900 planned under the old plan and 100 under the new one must
    reserve 900 while the old attempt is unsettled.
    """

    from types import SimpleNamespace

    from code2paper.agentic.unified_context_models import (
        InvocationAttemptStartedV1,
    )
    from code2paper.agentic.unified_invocation_ledger import (
        invocation_dir,
        publish_attempt_started,
        register_invocation_plan,
        unsettled_started_attempt_records,
    )

    root = tmp_path / "invocations"
    invocation = SimpleNamespace(
        invocation_id="inv:writer:page",
        role="writer",
        phase="writer",
        page_id="page:one",
    )
    old_plan = SimpleNamespace(
        content_digest="sha256:plan:old",
        reserved_input_tokens_by_role={"writer": 2000},
        invocations=(SimpleNamespace(max_input_tokens=900, **vars(invocation)),),
    )
    new_plan = SimpleNamespace(
        content_digest="sha256:plan:new",
        reserved_input_tokens_by_role={"writer": 2000},
        invocations=(SimpleNamespace(max_input_tokens=100, **vars(invocation)),),
    )
    register_invocation_plan(root, old_plan)
    register_invocation_plan(root, new_plan)
    publish_attempt_started(
        root,
        InvocationAttemptStartedV1(
            invocation_id="inv:writer:page",
            attempt=1,
            plan_digest="sha256:plan:old",
            page_id="page:one",
            expected_technical_bytes_digest="sha256:bytes",
            expected_request_envelope_digest="sha256:envelope",
            model_identity_digest="sha256:model",
            started_at_unix=1.0,
        ),
    )
    records = unsettled_started_attempt_records(root, new_plan)
    assert len(records) == 1
    assert records[0].plan_source == "recorded_plan"
    assert records[0].planned_input_tokens == 900

    # An attempt that really started under the current plan uses its allowance.
    import shutil

    directory = invocation_dir(root, "inv:writer:page")
    for path in directory.glob("*.started.json"):
        path.unlink()
    publish_attempt_started(
        root,
        InvocationAttemptStartedV1(
            invocation_id="inv:writer:page",
            attempt=2,
            plan_digest="sha256:plan:new",
            page_id="page:one",
            expected_technical_bytes_digest="sha256:bytes",
            expected_request_envelope_digest="sha256:envelope",
            model_identity_digest="sha256:model",
            started_at_unix=1.0,
        ),
    )
    current = unsettled_started_attempt_records(root, new_plan)
    assert [record.plan_source for record in current] == ["current_plan"]
    assert current[0].planned_input_tokens == 100
    # A marker whose plan record is gone cannot be metered: it is reported as
    # unknown so the caller blocks instead of reserving zero.
    shutil.rmtree(root / "plans")
    for path in directory.glob("*.started.json"):
        path.unlink()
    publish_attempt_started(
        root,
        InvocationAttemptStartedV1(
            invocation_id="inv:writer:page",
            attempt=3,
            plan_digest="sha256:plan:missing",
            page_id="page:one",
            expected_technical_bytes_digest="sha256:bytes",
            expected_request_envelope_digest="sha256:envelope",
            model_identity_digest="sha256:model",
            started_at_unix=1.0,
        ),
    )
    unknown = unsettled_started_attempt_records(root, new_plan)
    assert [record.plan_source for record in unknown] == ["unknown"]
