"""Product runner tests for the autonomous Method Agent (Agent 3, package B).

Covers the direct repo + author intent + claims -> research loop ->
evidence/facts/claims -> completeness -> plan readiness path without the
R8 legacy bridge, synthetic gaps, or the D5 matrix runner.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.autonomous_method_agent import (
    MethodAgentRunResultV1,
    UserClaimInputV1,
    UserClaimsInputV1,
    _candidate_validation_state,
    _verified_validation_state,
    append_claims_to_intent_graph,
    build_product_research_runtime,
    build_typed_gaps,
    load_user_claims,
    run_autonomous_method_agent,
)
from code2paper.agentic.intent_compiler_v2 import (
    compile_intent_obligation_graph_v2,
)
from code2paper.schemas import LLMConfig, LLMProvider

FIXTURE_REPO = Path(__file__).resolve().parent / "fixtures" / "research_loop_project"
FIXTURE_INTENT = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "research_loop_project_author_markers.yaml"
)


@pytest.fixture(autouse=True)
def _isolate_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODE2PAPER_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODE2PAPER_LLM_PROVIDER", raising=False)


@pytest.fixture()
def llm_none() -> LLMConfig:
    return LLMConfig(
        provider=LLMProvider.NONE,
        model="",
        temperature=0.0,
        max_output_tokens=512,
        request_timeout_seconds=5,
        retry_max_attempts=1,
        cache=False,
    )


class TestUserClaimsInput:
    def test_load_user_claims_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "claims.json"
        path.write_text(json.dumps({
            "claims": [
                {"claim_id": "c1", "text": "Aggregates values.", "priority": "must_cover"},
            ],
        }), encoding="utf-8")
        loaded = load_user_claims(path)
        assert loaded.claims[0].claim_id == "c1"
        assert loaded.claims[0].lane == "author_intent_unverified"

    def test_load_user_claims_none(self) -> None:
        assert load_user_claims(None) == UserClaimsInputV1()

    def test_load_user_claims_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_user_claims(tmp_path / "nope.json")

    def test_load_user_claims_invalid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError):
            load_user_claims(path)

    def test_duplicate_claim_ids_rejected(self) -> None:
        with pytest.raises(ValueError):
            UserClaimsInputV1(claims=[
                UserClaimInputV1(claim_id="c1", text="first"),
                UserClaimInputV1(claim_id="c1", text="second"),
            ])

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValueError):
            UserClaimInputV1(claim_id="c1", text="  ")


class TestAppendClaimsToIntentGraph:
    def test_claims_become_obligations(self) -> None:
        graph = compile_intent_obligation_graph_v2(None)
        assert not graph.obligations
        claims = UserClaimsInputV1(claims=[
            UserClaimInputV1(
                claim_id="c1",
                text="The training computation aggregates values and computes a scaled score.",
                priority="must_cover",
            ),
        ])
        merged = append_claims_to_intent_graph(
            graph,
            claims,
            project_root=str(FIXTURE_REPO),
        )
        assert len(merged.obligations) == 1
        obligation = merged.obligations[0]
        assert obligation.obligation_id.startswith("claim-")
        assert obligation.kind == "method_mainline"
        assert obligation.priority == "must_cover"
        assert obligation.source_field == "user_claims"

    def test_digest_recomputed_after_merge(self) -> None:
        graph = compile_intent_obligation_graph_v2(None)
        claims = UserClaimsInputV1(claims=[
            UserClaimInputV1(claim_id="c1", text="Aggregates input values."),
        ])
        merged = append_claims_to_intent_graph(
            graph,
            claims,
            project_root=str(FIXTURE_REPO),
        )
        assert merged.content_digest
        assert merged.content_digest != graph.content_digest

    def test_merge_is_idempotent_on_same_ids(self) -> None:
        graph = compile_intent_obligation_graph_v2(None)
        claims = UserClaimsInputV1(claims=[
            UserClaimInputV1(claim_id="c1", text="Aggregates input values."),
        ])
        once = append_claims_to_intent_graph(graph, claims, project_root=".")
        twice = append_claims_to_intent_graph(once, claims, project_root=".")
        assert len(twice.obligations) == len(once.obligations) == 1


class TestBuildProductResearchRuntime:
    def test_missing_repo_rejected(self, llm_none: LLMConfig) -> None:
        with pytest.raises(FileNotFoundError):
            build_product_research_runtime(
                repo_path="/definitely/not/a/repo",
                author_intent_path=None,
                claims=None,
                run_id="r1",
                llm_config=llm_none,
            )

    def test_runtime_seeds_agenda_from_intent_and_claims(
        self,
        llm_none: LLMConfig,
    ) -> None:
        claims = UserClaimsInputV1(claims=[
            UserClaimInputV1(claim_id="c1", text="Aggregates input values."),
        ])
        runtime = build_product_research_runtime(
            repo_path=FIXTURE_REPO,
            author_intent_path=FIXTURE_INTENT,
            claims=claims,
            run_id="r2",
            llm_config=llm_none,
        )
        obligation_ids = [item.obligation_id for item in runtime.agenda.items]
        assert any(claim_id.startswith("claim-") for claim_id in obligation_ids)
        assert any(item.priority == "must_cover" for item in runtime.agenda.items)


class TestTypedGaps:
    def test_unverifiable_claim_produces_explicit_gap(self, llm_none: LLMConfig) -> None:
        from code2paper.agentic.autonomous_method_agent import (
            run_product_research_phase,
        )

        claims = UserClaimsInputV1(claims=[
            UserClaimInputV1(
                claim_id="c-q",
                text="The method applies a top-k attention mask over the feature map.",
            ),
        ])
        runtime = build_product_research_runtime(
            repo_path=FIXTURE_REPO,
            author_intent_path=None,
            claims=claims,
            run_id="r-gap",
            llm_config=llm_none,
        )
        loop = run_product_research_phase(runtime, max_turns=12)
        gaps = build_typed_gaps(runtime, loop, claim_set=None)
        matching = [gap for gap in gaps if gap.obligation_id.startswith("claim-")]
        assert matching, "unverifiable claim must produce a typed gap"
        assert matching[0].status == "explicit_gap"
        assert matching[0].stopping_reason
        assert matching[0].attempted_tools

    def test_gap_reason_is_not_synthetic(self, llm_none: LLMConfig) -> None:
        claims = UserClaimsInputV1(claims=[
            UserClaimInputV1(
                claim_id="c-q",
                text="The method applies a top-k attention mask over the feature map.",
            ),
        ])
        runtime = build_product_research_runtime(
            repo_path=FIXTURE_REPO,
            author_intent_path=None,
            claims=claims,
            run_id="r-gap2",
            llm_config=llm_none,
        )
        from code2paper.agentic.autonomous_method_agent import (
            run_product_research_phase,
        )

        loop = run_product_research_phase(runtime, max_turns=12)
        gaps = build_typed_gaps(runtime, loop, claim_set=None)
        for gap in gaps:
            assert "synthetic" not in gap.gap_id
            assert gap.reason


class TestRunAutonomousMethodAgent:
    def test_full_product_run_writes_research_artifacts(
        self,
        tmp_path: Path,
        llm_none: LLMConfig,
    ) -> None:
        out_root = tmp_path / "out"
        result = run_autonomous_method_agent(
            repo_path=FIXTURE_REPO,
            author_intent_path=FIXTURE_INTENT,
            out_root=out_root,
            llm_config=llm_none,
            max_research_turns=15,
        )
        assert isinstance(result, MethodAgentRunResultV1)
        expected = {
            "evidence_packets",
            "code_facts",
            "atomic_claims",
            "completeness_matrix",
            "authoring_projection_v1",
            "method_evidence",
            "claim_evidence_map",
            "research_trace",
            "typed_gaps",
            "agent_trace",
            "run_summary",
        }
        for key in expected:
            assert key in result.artifact_paths, f"missing artifact {key}"
            assert Path(result.artifact_paths[key]).is_file(), f"missing file {key}"
        assert result.writer_status == "skipped_no_live_llm"
        assert result.writer_blocked_reason == "no_live_llm"
        summary = result.summary
        assert summary["evidence"]["synthetic_support_used"] is False
        assert summary["verified_validation"]["status"] == "not_run"
        projection = json.loads(
            Path(result.artifact_paths["authoring_projection_v1"]).read_text(
                encoding="utf-8"
            )
        )
        method_evidence = json.loads(
            Path(result.artifact_paths["method_evidence"]).read_text(encoding="utf-8")
        )
        claim_map = json.loads(
            Path(result.artifact_paths["claim_evidence_map"]).read_text(
                encoding="utf-8"
            )
        )
        story_spine = json.loads(
            Path(result.artifact_paths["story_spine"]).read_text(encoding="utf-8")
        )
        assert projection["projected_claims"]
        assert projection["author_story_spine"]
        assert story_spine == projection["author_story_spine"]
        assert method_evidence["stage_packets"]
        assert method_evidence["claim_contracts"]
        assert claim_map["claims"]

    def test_typed_gap_claim_produces_review_candidates(
        self,
        tmp_path: Path,
        llm_none: LLMConfig,
    ) -> None:
        claims_path = tmp_path / "claims.json"
        claims_path.write_text(json.dumps({
            "claims": [
                {
                    "claim_id": "c-q",
                    "text": "The method applies a top-k attention mask over the feature map.",
                },
            ],
        }), encoding="utf-8")
        out_root = tmp_path / "out2"
        result = run_autonomous_method_agent(
            repo_path=FIXTURE_REPO,
            author_intent_path=None,
            claims_path=claims_path,
            out_root=out_root,
            llm_config=llm_none,
            max_research_turns=12,
        )
        gaps = json.loads(
            Path(result.artifact_paths["typed_gaps"]).read_text(encoding="utf-8")
        )
        assert any(gap["status"] == "explicit_gap" for gap in gaps)
        review = json.loads(
            Path(result.artifact_paths["review_candidates"]).read_text(encoding="utf-8")
        )
        assert review, "an unverified claim must produce review candidates"
        for item in review:
            assert item["proposed_body"].strip()
            assert item["confirmation_question"].strip()
            assert item["blocks_verified"] is True
            assert item["blocks_candidate"] is False

    def test_completeness_matrix_reflects_real_gap(
        self,
        tmp_path: Path,
        llm_none: LLMConfig,
    ) -> None:
        claims_path = tmp_path / "claims.json"
        claims_path.write_text(json.dumps({
            "claims": [
                {
                    "claim_id": "c-q",
                    "text": "The method applies a top-k attention mask over the feature map.",
                },
            ],
        }), encoding="utf-8")
        out_root = tmp_path / "out3"
        result = run_autonomous_method_agent(
            repo_path=FIXTURE_REPO,
            author_intent_path=None,
            claims_path=claims_path,
            out_root=out_root,
            llm_config=llm_none,
            max_research_turns=12,
        )
        matrix = json.loads(
            Path(result.artifact_paths["completeness_matrix"]).read_text(encoding="utf-8")
        )
        claim_rows = [
            item for item in matrix["items"]
            if str(item["obligation_id"]).startswith("claim-")
        ]
        assert claim_rows
        assert any(
            item["status"] == "explicit_code_gap" for item in claim_rows
        )

    def test_missing_claims_file_fails_typed(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            run_autonomous_method_agent(
                repo_path=FIXTURE_REPO,
                claims_path=tmp_path / "nope.json",
                out_root=tmp_path / "out4",
            )

    def test_max_research_turns_must_be_positive(
        self,
        tmp_path: Path,
        llm_none: LLMConfig,
    ) -> None:
        with pytest.raises(ValueError):
            run_autonomous_method_agent(
                repo_path=FIXTURE_REPO,
                out_root=tmp_path / "out5",
                llm_config=llm_none,
                max_research_turns=0,
            )

    def test_result_digest_is_stable(self, tmp_path: Path, llm_none: LLMConfig) -> None:
        out_root = tmp_path / "out6"
        result = run_autonomous_method_agent(
            repo_path=FIXTURE_REPO,
            author_intent_path=FIXTURE_INTENT,
            out_root=out_root,
            llm_config=llm_none,
            max_research_turns=15,
            run_id="stable-run",
        )
        assert result.content_digest
        assert result.run_id == "stable-run"

    def test_candidate_validation_state_reads_final_validation_artifact(
        self,
        tmp_path: Path,
    ) -> None:
        validation_dir = tmp_path / "artifacts" / "07_validation"
        validation_dir.mkdir(parents=True)
        (validation_dir / "agentic_text_evidence_validation.json").write_text(
            json.dumps({
                "status": "passed",
                "unsupported_claims": 0,
                "unverified_claims": 0,
                "checked_factual_claims": 4,
                "supported_claims": 4,
            }),
            encoding="utf-8",
        )

        state = _candidate_validation_state(tmp_path)

        assert state["status"] == "passed"
        assert state["unsupported_positive_claims"] == 0
        assert state["checked_factual_claims"] == 4
        assert state["supported_claims"] == 4

    def test_verified_validation_state_reads_sentence_split_report(
        self,
        tmp_path: Path,
    ) -> None:
        authoring_dir = tmp_path / "artifacts" / "06_authoring"
        authoring_dir.mkdir(parents=True)
        (authoring_dir / "repository_verified_method.md").write_text(
            "## Method\n\nA supported sentence.\n", encoding="utf-8"
        )
        (authoring_dir / "method_draft_bundle_v1.json").write_text(
            json.dumps({
                "validation_split_report": {
                    "split_mode": "sentence_reverse_validation",
                    "verified_positive_unit_count": 1,
                    "excluded_units": [{"unit_id": "FTU2"}],
                }
            }),
            encoding="utf-8",
        )

        state = _verified_validation_state(tmp_path)

        assert state == {
            "status": "passed",
            "unsupported_positive_claims": 0,
            "checked_positive_units": 1,
            "excluded_candidate_units": 1,
            "split_mode": "sentence_reverse_validation",
        }
