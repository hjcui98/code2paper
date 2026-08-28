from __future__ import annotations

from code2paper.agentic.publication_issue_owner_router import (
    route_publication_issue,
    route_publication_issues,
)
from code2paper.agentic.publication_quality import find_code_trace_prose_sections
from code2paper.agentic.research_models import TextRepairIssueV1
from code2paper.agentic.rewrite_agent import LocalRewriteAgent
from code2paper.llm.client import LLMResponse
from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1
from code2paper.schemas import LLMConfig, LLMProvider


def test_publication_issue_owner_router_assigns_one_primary_owner() -> None:
    issues = [
        TextRepairIssueV1(
            sentence_id="s-evidence",
            failure_type="unsupported_rationale",
            allowed_repair_scope="drop_or_gap",
        ),
        TextRepairIssueV1(
            sentence_id="s-formula",
            failure_type="formula_not_rendered",
            allowed_repair_scope="formula_rendering",
        ),
        TextRepairIssueV1(
            sentence_id="s-content",
            failure_type="supported_claim_not_rendered",
            allowed_repair_scope="claim_decomposition",
        ),
        TextRepairIssueV1(
            sentence_id="s-style",
            failure_type="method_language_style",
            allowed_repair_scope="wording_only",
        ),
    ]

    routes = route_publication_issues(issues, attempt=2)

    assert [route.owner for route in routes] == [
        "research_continuation",
        "formalizer",
        "writer",
        "rewrite",
    ]
    assert all(route.attempt == 2 for route in routes)


def test_rewrite_owner_rejects_evidence_issue_when_strictly_routed() -> None:
    issue = TextRepairIssueV1(
        sentence_id="s1",
        failure_type="unsupported_rationale",
        allowed_repair_scope="drop_or_gap",
    )
    route = route_publication_issue(issue, input_digest="sha256:in")

    assert route.owner == "research_continuation"
    assert route.input_digest == "sha256:in"
    assert route.output_digest == ""


def test_code_trace_detector_catches_escaped_snake_case_command() -> None:
    output = PublicationMethodSectionOutputV1(
        section_id="S1",
        section_markdown=(
            "## Mechanism\n\n"
            "compute\\_src\\_dst applies the transformation before aggregation."
        ),
    )

    flagged = find_code_trace_prose_sections([output])

    assert flagged == (("S1", output.section_markdown),)


def test_rewrite_prompt_does_not_contain_deleted_drop_example() -> None:
    # Keep this regression test representation-only: the prompt source must
    # not revive the project-specific empty-replacement example.
    prompts: list[str] = []

    def caller(_config: LLMConfig, request) -> LLMResponse:
        prompts.append(request.prompt)
        return LLMResponse(
            text='{"patches":[],"self_identified_risks":[],"incomplete":false}',
            response_hash="sha256:router-prompt",
            finish_reason="stop",
        )

    LocalRewriteAgent(
        config=LLMConfig(
            provider=LLMProvider.NONE,
            model="router-test",
            cache=False,
        ),
        caller=caller,
    ).rewrite(
        "## Mechanism\n\nThe mechanism is described here.",
        issues=[
            TextRepairIssueV1(
                sentence_id="s1",
                failure_type="method_language_style",
                allowed_repair_scope="wording_only",
            )
        ],
    )

    assert prompts
    assert "drop-FAC1" not in prompts[0]
