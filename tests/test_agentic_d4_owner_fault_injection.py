from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.generic_claim_compiler import ClaimProposalV1, authorize_claim
from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1
from code2paper.agentic.graph_text_trust_nodes import packet_binding_repair_node
from code2paper.agentic.intent_compiler_v2 import compile_intent_obligation_graph_v2
from code2paper.agentic.intent_target_proposer import enrich_intent_graph_with_llm
from code2paper.agentic.rewrite_agent import LocalRewriteAgent
from code2paper.agentic.research_models import TextRepairIssueV1
from code2paper.llm.section_writer import (
    WriterSectionInput,
    write_publication_method_by_sections,
)
from code2paper.schemas import LLMConfig, LLMProvider
from code2paper.llm.client import LLMResponse


def test_intent_owner_fault_preserves_deterministic_obligations() -> None:
    graph = compile_intent_obligation_graph_v2(AuthorIntentSummary(
        method_goal="Read input and return output.",
        method_mainline="Read input and return output.",
        implementation_scope="repository",
    ))
    config = LLMConfig(provider=LLMProvider.OPENAI, model="fault-injection", cache=False)
    with (
        patch(
            "code2paper.agentic.intent_target_proposer.has_provider_api_key",
            return_value=True,
        ),
        patch(
            "code2paper.agentic.intent_target_proposer.LLMClient.complete",
            side_effect=RuntimeError("injected intent owner failure"),
        ),
    ):
        enriched, report = enrich_intent_graph_with_llm(graph, config)

    assert enriched.content_digest == graph.content_digest
    assert report.accepted is False
    assert report.failure == "llm_error:RuntimeError"


def test_packet_owner_fault_preserves_incumbent_and_emits_typed_transition(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "method.md"
    text_path.write_text("Incumbent supported text.\n", encoding="utf-8")
    request_path = tmp_path / "requests.json"
    request_path.write_text(json.dumps({
        "requests": [{
            "claim_id": "FAC1",
            "source_claim_ids": ["C1"],
            "failure_type": "wrong_span_role",
            "requested_scope": "packet_relation",
        }],
    }), encoding="utf-8")
    state = AgenticRunState(
        project_root=tmp_path,
        out_root=tmp_path / "out",
        artifacts={
            "text_clean_md": str(text_path),
            "packet_repair_requests_v1": str(request_path),
        },
        loop_counters={"local_text_repair": 1},
    )

    def exploding_owner(*_args, **_kwargs):
        raise RuntimeError("injected packet owner failure")

    result = AgenticRunState.model_validate(packet_binding_repair_node(
        state.model_dump(mode="json"), repair_owner=exploding_owner
    ))

    assert result.next_node == "blocked"
    assert result.blocked_reason == "packet_repair_owner_error:RuntimeError"
    assert text_path.read_text(encoding="utf-8") == "Incumbent supported text.\n"
    transition = json.loads(Path(result.artifacts["repair_transition_v1"]).read_text())
    assert transition["strategy"] == "packet_relation"
    assert transition["owner"] == "repository_tools"
    assert transition["status"] == "blocked"


def test_claim_owner_fault_cannot_authorize_unknown_fact() -> None:
    facts = CodeFactSetV1(
        repo_snapshot_id="repo:fault",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[],
        content_digest="sha256:facts",
    )
    proposal = ClaimProposalV1(
        claim_id="claim-injected",
        canonical_text="The system always returns an invented result.",
        proposed_fact_ids=["fact-does-not-exist"],
    )

    claim, report = authorize_claim(proposal, facts)

    assert claim is None
    assert "unknown_fact:fact-does-not-exist" in report.failures


def test_writer_owner_fault_emits_no_deterministic_prose() -> None:
    section = WriterSectionInput(
        section_id="section-1",
        heading="Mechanism",
        prompt_payload={},
        publication_mode=True,
        argument_graph={"argument_unit_ids": ["unit-1"]},
    )

    def exploding_writer(*_args, **_kwargs):
        raise RuntimeError("injected writer owner failure")

    result = write_publication_method_by_sections(
        LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        [section],
        llm_caller=exploding_writer,
    )

    assert result.outputs == []
    assert result.aggregate.concatenated_markdown == ""
    assert result.aggregate.incomplete_sections == ["section-1"]
    assert result.aggregate.sections[0].blocked_reason == "section_writer_llm_error:RuntimeError"


def test_local_rewrite_owner_rejects_repository_scopes_before_call() -> None:
    called = False

    def caller(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("repository repair scope must not reach lexical rewrite")

    result = LocalRewriteAgent(
        config=LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        caller=caller,
    ).rewrite(
        "The incumbent sentence.",
        issues=[TextRepairIssueV1(
            sentence_id="S1",
            atomic_claim_id="FAC1",
            failure_type="wrong_span_role",
            allowed_repair_scope="packet_relation",
        )],
    )

    assert result.status == "blocked"
    assert result.blocked_reason == "rewrite_scope_not_owned_by_local_rewrite"
    assert called is False


def test_local_rewrite_owner_rejects_patch_scope_wider_than_issue() -> None:
    issue = TextRepairIssueV1(
        sentence_id="S1",
        atomic_claim_id="FAC1",
        failure_type="missing_qualifier",
        allowed_repair_scope="wording_only",
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "too-wide",
                    "start": 0,
                    "end": 3,
                    "original_text": "The",
                    "replacement_text": "",
                    "issue_ids": ["FAC1"],
                    "allowed_scope": "drop_or_gap",
                }],
            }),
            response_hash="sha256:rewrite-scope-failure",
            finish_reason="stop",
        )

    result = LocalRewriteAgent(
        config=LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        caller=caller,
    ).rewrite("The incumbent sentence.", issues=[issue])

    assert result.status == "rejected"
    assert result.blocked_reason == "rewrite_patch_scope_failed"
    assert result.candidate_text == "The incumbent sentence."


def test_local_rewrite_owner_accepts_explicit_drop_or_gap_patch() -> None:
    issue = TextRepairIssueV1(
        sentence_id="S1",
        atomic_claim_id="FAC1",
        failure_type="no_semantically_matching_projected_claim",
        allowed_repair_scope="drop_or_gap",
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "drop-fac1",
                    "start": 0,
                    "end": len("The incumbent sentence."),
                    "original_text": "The incumbent sentence.",
                    "replacement_text": "",
                    "issue_ids": ["FAC1"],
                    "allowed_scope": "drop_or_gap",
                }],
            }),
            response_hash="sha256:rewrite-drop",
            finish_reason="stop",
        )

    result = LocalRewriteAgent(
        config=LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        caller=caller,
    ).rewrite("The incumbent sentence.", issues=[issue])

    assert result.status == "applied"
    assert result.candidate_text == ""


def test_local_rewrite_repairs_unique_exact_span_coordinates_only() -> None:
    incumbent = "The first sentence. The second sentence."
    issue = TextRepairIssueV1(
        sentence_id="S1",
        atomic_claim_id="FAC1",
        failure_type="missing_qualifier",
        allowed_repair_scope="wording_only",
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "coordinate-only-repair",
                    "start": 0,
                    "end": 5,
                    "original_text": incumbent,
                    "replacement_text": "The first sentence; then the second sentence.",
                    "issue_ids": ["FAC1"],
                    "allowed_scope": "wording_only",
                }],
            }),
            response_hash="sha256:rewrite-coordinate-repair",
            finish_reason="stop",
        )

    result = LocalRewriteAgent(
        config=LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        caller=caller,
    ).rewrite(incumbent, issues=[issue])

    assert result.status == "applied"
    assert result.candidate_text == "The first sentence; then the second sentence."
    assert result.output is not None
    assert result.output.patches[0].end == len(incumbent)
    assert "repair_unique_exact_span_coordinates" in (
        result.response_recovery_trace["operations"]
    )


def test_local_rewrite_restores_unchanged_heading_for_full_section_patch() -> None:
    incumbent = "## Encoder mechanism\n\n`Encoder.forward` loads the input tensor."
    issue = TextRepairIssueV1(
        sentence_id="style:encoder",
        failure_type="method_language_style",
        allowed_repair_scope="wording_only",
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "academic-section",
                    "start": 0,
                    "end": len(incumbent),
                    "original_text": incumbent,
                    "replacement_text": "The encoder maps the input into a latent representation.",
                    "issue_ids": ["style:encoder"],
                    "allowed_scope": "wording_only",
                }],
            }),
            response_hash="sha256:rewrite-heading-repair",
            finish_reason="stop",
        )

    result = LocalRewriteAgent(
        config=LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        caller=caller,
    ).rewrite(
        incumbent,
        issues=[issue],
        section_context={"writer_heading": "Encoder mechanism"},
    )

    assert result.status == "applied"
    assert result.candidate_text.startswith("## Encoder mechanism\n\nThe encoder maps")
    assert "restore_unchanged_section_heading" in (
        result.response_recovery_trace["operations"]
    )


def test_local_rewrite_owner_accepts_most_permissive_scope_among_issues() -> None:
    """When a sentence carries several issues, the repair contract permits
    the most permissive scope among them (``derive_repair_issues`` /
    ``most_permissive_scope``).

    Regression: the scope gate compared against the *least* permissive
    issue, so a live MA-S5 sentence with
    ``no_semantically_matching_projected_claim`` (claim_decomposition) and
    ``direct_evidence_missing`` (drop_or_gap) could not be dropped even
    though drop_or_gap was authorized, and the run stayed blocked."""
    issues = [
        TextRepairIssueV1(
            sentence_id="S1",
            atomic_claim_id="FAC1",
            failure_type="no_semantically_matching_projected_claim",
            allowed_repair_scope="claim_decomposition",
        ),
        TextRepairIssueV1(
            sentence_id="S1",
            atomic_claim_id="FAC1",
            failure_type="unsupported_rationale",
            allowed_repair_scope="drop_or_gap",
        ),
    ]

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "drop-fac1",
                    "start": 0,
                    "end": len("The incumbent sentence."),
                    "original_text": "The incumbent sentence.",
                    "replacement_text": "",
                    "issue_ids": ["FAC1"],
                    "allowed_scope": "drop_or_gap",
                }],
            }),
            response_hash="sha256:rewrite-drop",
            finish_reason="stop",
        )

    result = LocalRewriteAgent(
        config=LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        caller=caller,
    ).rewrite("The incumbent sentence.", issues=issues)

    assert result.status == "applied"
    assert result.candidate_text == ""


def test_local_rewrite_rejects_deleting_an_authorized_method_section() -> None:
    incumbent = "## Intended mechanism\n\nThe repository does not yet establish this mechanism."
    issue = TextRepairIssueV1(
        sentence_id="S1",
        atomic_claim_id="FAC1",
        failure_type="unsupported_rationale",
        allowed_repair_scope="drop_or_gap",
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "erase-section",
                    "start": 0,
                    "end": len(incumbent),
                    "original_text": incumbent,
                    "replacement_text": "## Intended mechanism\n\nand",
                    "issue_ids": ["FAC1"],
                    "allowed_scope": "drop_or_gap",
                }],
            }),
            response_hash="sha256:rewrite-unreadable",
            finish_reason="stop",
        )

    result = LocalRewriteAgent(
        config=LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        caller=caller,
    ).rewrite(
        incumbent,
        issues=[issue],
        section_context={
            "writer_authority_context": {
                "section_candidate_points": [{"point_id": "candidate:1"}],
            }
        },
    )

    assert result.status == "rejected"
    assert result.blocked_reason == "rewrite_candidate_not_readable"
    assert "candidate_body_is_connective_debris" in result.patch_failures


def test_local_rewrite_rejects_patch_referencing_out_of_cluster_issue_id() -> None:
    """The patch contract accepts only issue_ids from the assigned cluster.

    Regression: the section context exposed every section failure (including
    structure:* ids from another cluster), the model referenced them in its
    patch, and the whole repair was rejected as unknown_issue even though the
    span was exact."""
    issue = TextRepairIssueV1(
        sentence_id="S1",
        atomic_claim_id="FAC1",
        failure_type="missing_qualifier",
        allowed_repair_scope="wording_only",
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps({
                "patches": [{
                    "patch_id": "tainted",
                    "start": 0,
                    "end": len("The incumbent sentence."),
                    "original_text": "The incumbent sentence.",
                    "replacement_text": "The incumbent sentence, under case_study.",
                    "issue_ids": ["FAC1", "structure:MA-S2:fused-heading-suffix"],
                    "allowed_scope": "wording_only",
                }],
            }),
            response_hash="sha256:rewrite-out-of-cluster",
            finish_reason="stop",
        )

    result = LocalRewriteAgent(
        config=LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        caller=caller,
    ).rewrite("The incumbent sentence.", issues=[issue])

    assert result.status == "rejected"
    assert result.blocked_reason == "rewrite_patch_contract_failed"
    assert result.patch_failures == ("patch:tainted:unknown_issue",)
    assert result.candidate_text == "The incumbent sentence."


def test_local_rewrite_applies_multiple_disjoint_exact_patches() -> None:
    """Multiple disjoint exact spans are applied in one Rewrite call.

    Regression: patches were capped at one, forcing a single full-section
    span that the model could not reproduce byte-exactly, so multi-claim
    paragraphs churned on incumbent_span_mismatch until the attempt budget
    was exhausted."""
    incumbent = "First sentence stands. Second sentence stands. Third sentence stands."
    issue = TextRepairIssueV1(
        sentence_id="S2",
        atomic_claim_id="FAC2",
        failure_type="missing_qualifier",
        allowed_repair_scope="wording_only",
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps({
                "patches": [
                    {
                        "patch_id": "p2",
                        "start": incumbent.index("Second sentence stands."),
                        "end": incumbent.index("Second sentence stands.") + len("Second sentence stands."),
                        "original_text": "Second sentence stands.",
                        "replacement_text": "Second sentence runs, under case_study.",
                        "issue_ids": ["FAC2"],
                        "allowed_scope": "wording_only",
                    },
                    {
                        "patch_id": "p3",
                        "start": incumbent.index("Third sentence stands."),
                        "end": incumbent.index("Third sentence stands.") + len("Third sentence stands."),
                        "original_text": "Third sentence stands.",
                        "replacement_text": "Third sentence proceeds.",
                        "issue_ids": ["FAC2"],
                        "allowed_scope": "wording_only",
                    },
                ],
            }),
            response_hash="sha256:rewrite-multi-patch",
            finish_reason="stop",
        )

    result = LocalRewriteAgent(
        config=LLMConfig(provider=LLMProvider.NONE, model="fault-injection", cache=False),
        caller=caller,
    ).rewrite(incumbent, issues=[issue])

    assert result.status == "applied"
    assert result.candidate_text == (
        "First sentence stands. Second sentence runs, under case_study. "
        "Third sentence proceeds."
    )
    assert len(result.output.patches) == 2
