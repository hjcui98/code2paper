from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.core.output_names import method_output
from code2paper.pipeline.stages.validation import write_phase6_validation_manifest


class Phase6ValidationManifestTests(unittest.TestCase):
    def test_manifest_passes_when_only_readiness_and_missing_latex_engine_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            _write_report(method_root, "method_plan_quality", {"passed": True, "issues": []})
            _write_report(method_root, "semantic_issues", {"passed": True, "issues": []})
            _write_report(method_root, "self_check", {"issues": [{"issue_id": "PR1"}]})
            _write_report(method_root, "self_check_clean", {"issues": [{"issue_id": "PR1"}]})
            _write_report(method_root, "qa_claims", {"passed": True, "issues": []})
            _write_report(method_root, "qa_numbers", {"passed": True, "issues": []})
            _write_report(method_root, "qa_equations", {"passed": True, "issues": []})
            _write_report(method_root, "qa_terms", {"passed": True, "issues": [{"severity": "medium"}]})
            _write_report(
                method_root,
                "qa_latex",
                {
                    "passed": False,
                    "status": "unavailable",
                    "issues": [{"category": "engine_unavailable"}],
                },
            )
            _write_report(method_root, "fidelity", {"passed": True, "issues": []})

            manifest = write_phase6_validation_manifest(method_root=method_root, fidelity_passed=True)

        self.assertEqual(manifest["status"], "passed")
        self.assertEqual(manifest["failed_reports"], [])
        self.assertEqual(
            set(manifest["advisory_failed_reports"]),
            {"self_check", "self_check_clean", "qa_latex"},
        )

    def test_manifest_fails_when_latex_compile_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            _write_report(method_root, "fidelity", {"passed": True, "issues": []})
            _write_report(
                method_root,
                "qa_latex",
                {
                    "passed": False,
                    "status": "failed",
                    "issues": [{"category": "compile_failed"}],
                },
            )

            manifest = write_phase6_validation_manifest(method_root=method_root, fidelity_passed=True)

        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["failed_reports"], ["qa_latex"])


def _write_report(method_root: Path, key: str, payload: dict[str, object]) -> None:
    path = method_output(method_root, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
