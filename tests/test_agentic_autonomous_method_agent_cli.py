"""End-to-end CLI tests for ``code2paper method-agent run`` via the unified CLI.

Verifies the exact product command shape from plan section 7 / package H and
that a single command produces the candidate/verified/review + research
artifact surface on a small fixture without the D5 matrix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.cli.main import main as cli_main

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


class TestMethodAgentCommand:
    def test_command_shape_runs_product_path(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out_root = tmp_path / "out"
        code = cli_main([
            "method-agent",
            "run",
            "--repo", str(FIXTURE_REPO),
            "--author-intent", str(FIXTURE_INTENT),
            "--out", str(out_root),
            "--no-live-llm",
            "--max-research-turns", "15",
        ])
        assert code == 0
        captured = capsys.readouterr()
        assert "candidate written: no" in captured.out
        assert "verified written: no" in captured.out
        assert "plan readiness:" in captured.out
        assert "summary=" in captured.out
        product_dir = out_root / "artifacts" / "research_product"
        assert (product_dir / "run_summary.json").is_file()
        summary = json.loads(
            (product_dir / "run_summary.json").read_text(encoding="utf-8")
        )
        assert summary["research"]["status"] in {"trusted", "incomplete"}
        assert summary["plan"]["plan_built"] is True
        assert summary["evidence"]["synthetic_support_used"] is False

    def test_claims_input_reaches_research(
        self,
        tmp_path: Path,
    ) -> None:
        claims_path = tmp_path / "claims.json"
        claims_path.write_text(json.dumps({
            "claims": [
                {
                    "claim_id": "c-ok",
                    "text": "The training computation aggregates values and computes a scaled score.",
                    "priority": "must_cover",
                },
            ],
        }), encoding="utf-8")
        out_root = tmp_path / "out"
        code = cli_main([
            "method-agent",
            "run",
            "--repo", str(FIXTURE_REPO),
            "--claims", str(claims_path),
            "--out", str(out_root),
            "--no-live-llm",
            "--max-research-turns", "15",
        ])
        assert code == 0
        agenda = json.loads(
            (out_root / "artifacts" / "research_agenda_v1.json").read_text(encoding="utf-8")
        )
        claim_items = [
            item for item in agenda["items"] if str(item["obligation_id"]).startswith("claim-")
        ]
        assert claim_items, "user claim must seed a research obligation"

    def test_missing_repo_reported(self, tmp_path: Path) -> None:
        code = cli_main([
            "method-agent",
            "run",
            "--repo", str(tmp_path / "nope"),
            "--out", str(tmp_path / "out"),
        ])
        assert code == 2

    def test_llm_profile_cannot_execute_shell(
        self,
        tmp_path: Path,
    ) -> None:
        profile = tmp_path / "profile.env"
        profile.write_text(
            "export CODE2PAPER_LLM_PROVIDER=openai\n"
            'export OPENAI_API_KEY="${OPENAI_API_KEY:-nope}"\n'
            "export CODE2PAPER_LLM_MODEL=local-model\n",
            encoding="utf-8",
        )
        out_root = tmp_path / "out"
        code = cli_main([
            "method-agent",
            "run",
            "--repo", str(FIXTURE_REPO),
            "--out", str(out_root),
            "--no-live-llm",
            "--llm-profile", str(profile),
            "--max-research-turns", "10",
        ])
        assert code == 0
        summary = json.loads(
            (out_root / "artifacts" / "research_product" / "run_summary.json").read_text(
                encoding="utf-8"
            )
        )
        assert summary["live_llm"] is False
