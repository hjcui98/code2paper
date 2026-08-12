"""CLI surface tests for ``code2paper method-agent run`` (Agent 3, package H).

Covers argument validation, the no-live-llm deterministic path, required
output files, and the reader-facing summary.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from code2paper.cli.agentic_run import method_agent_main

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


class TestMethodAgentArgValidation:
    def test_missing_repo_returns_error_code(self, tmp_path: Path) -> None:
        code = method_agent_main([
            "run",
            "--repo", str(tmp_path / "nope"),
            "--out", str(tmp_path / "out"),
            "--no-live-llm",
        ])
        assert code == 2

    def test_missing_claims_file_returns_error_code(self, tmp_path: Path) -> None:
        code = method_agent_main([
            "run",
            "--repo", str(FIXTURE_REPO),
            "--claims", str(tmp_path / "nope.json"),
            "--out", str(tmp_path / "out"),
            "--no-live-llm",
        ])
        assert code == 2

    def test_missing_author_intent_returns_error_code(self, tmp_path: Path) -> None:
        code = method_agent_main([
            "run",
            "--repo", str(FIXTURE_REPO),
            "--author-intent", str(tmp_path / "nope.yaml"),
            "--out", str(tmp_path / "out"),
            "--no-live-llm",
        ])
        assert code == 2

    def test_missing_llm_profile_returns_error_code(self, tmp_path: Path) -> None:
        code = method_agent_main([
            "run",
            "--repo", str(FIXTURE_REPO),
            "--out", str(tmp_path / "out"),
            "--no-live-llm",
            "--llm-profile", str(tmp_path / "nope.env"),
        ])
        assert code == 2

    def test_llm_profile_env_restored_on_validation_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CODE2PAPER_LLM_PROVIDER", "original-provider")
        profile = tmp_path / "profile.env"
        profile.write_text("CODE2PAPER_LLM_PROVIDER=openai\n", encoding="utf-8")

        code = method_agent_main([
            "run",
            "--repo", str(tmp_path / "missing-repo"),
            "--out", str(tmp_path / "out"),
            "--llm-profile", str(profile),
        ])

        assert code == 2
        assert os.environ["CODE2PAPER_LLM_PROVIDER"] == "original-provider"

    def test_unknown_command_is_rejected(self) -> None:
        with pytest.raises(SystemExit):
            method_agent_main(["watch"])


class TestMethodAgentRun:
    def test_full_product_run_writes_required_outputs(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out_root = tmp_path / "out"
        code = method_agent_main([
            "run",
            "--repo", str(FIXTURE_REPO),
            "--author-intent", str(FIXTURE_INTENT),
            "--out", str(out_root),
            "--no-live-llm",
            "--max-research-turns", "15",
            "--run-id", "cli-run-1",
        ])
        assert code == 0
        required = [
            "evidence_packets.json",
            "code_facts.json",
            "atomic_claims.json",
            "completeness_matrix.json",
            "research_trace.json",
            "typed_gaps.json",
            "agent_trace.json",
            "run_summary.json",
        ]
        product_dir = out_root / "artifacts" / "research_product"
        for name in required:
            assert (product_dir / name).is_file(), f"missing {name}"
        writer_keys = [
            "evidence_packets_v3.json",
            "code_facts_v1.json",
            "atomic_claims_v3.json",
            "method_completeness_matrix_v1.json",
            "method_section_plan_v2.json",
            "equation_claims_v1.json",
            "configuration_claims_v1.json",
        ]
        for name in writer_keys:
            assert (out_root / "artifacts" / name).is_file(), f"missing {name}"

        summary = json.loads(
            (product_dir / "run_summary.json").read_text(encoding="utf-8")
        )
        assert summary["run_id"] == "cli-run-1"
        assert summary["writer"]["status"] == "skipped_no_live_llm"
        assert summary["writer"]["blocked_reason"] == "no_live_llm"
        assert summary["evidence"]["synthetic_support_used"] is False

        captured = capsys.readouterr()
        assert "candidate written: no" in captured.out
        assert "verified written: no" in captured.out
        assert "verified facts:" in captured.out
        assert "gaps:" in captured.out

    def test_exit_artifact_written(self, tmp_path: Path) -> None:
        out_root = tmp_path / "out"
        code = method_agent_main([
            "run",
            "--repo", str(FIXTURE_REPO),
            "--out", str(out_root),
            "--no-live-llm",
            "--max-research-turns", "10",
        ])
        assert code == 0
        assert (out_root / "method_agent_result.json").is_file()
        payload = json.loads(
            (out_root / "method_agent_result.json").read_text(encoding="utf-8")
        )
        assert payload["schema_version"] == "1.0"
        assert payload["run_id"]

    def test_claims_file_drives_gap_and_review(
        self,
        tmp_path: Path,
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
        out_root = tmp_path / "out"
        code = method_agent_main([
            "run",
            "--repo", str(FIXTURE_REPO),
            "--claims", str(claims_path),
            "--out", str(out_root),
            "--no-live-llm",
            "--max-research-turns", "12",
        ])
        assert code == 0
        product_dir = out_root / "artifacts" / "research_product"
        gaps = json.loads((product_dir / "typed_gaps.json").read_text(encoding="utf-8"))
        assert gaps, "the unverifiable claim must leave a typed gap"
        assert all(gap["status"] in {"explicit_gap", "unresolved"} for gap in gaps)
        review = json.loads(
            (product_dir / "review_candidates.json").read_text(encoding="utf-8")
        )
        assert review

    def test_bad_claims_json_returns_error_code(self, tmp_path: Path) -> None:
        claims_path = tmp_path / "claims.json"
        claims_path.write_text("{not json", encoding="utf-8")
        code = method_agent_main([
            "run",
            "--repo", str(FIXTURE_REPO),
            "--claims", str(claims_path),
            "--out", str(tmp_path / "out"),
            "--no-live-llm",
        ])
        assert code == 2
