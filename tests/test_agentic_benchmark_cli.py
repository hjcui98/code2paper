from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from code2paper.cli.agentic_benchmark import main as agentic_benchmark_main


class AgenticBenchmarkCliTests(unittest.TestCase):
    def test_cli_writes_benchmark_report_from_variant_specs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            eval_path = _write_eval(root / "eval.json")
            output = root / "benchmark.json"

            code = agentic_benchmark_main(
                [
                    "--run",
                    f"agentic=toy={eval_path}",
                    "--out",
                    str(output),
                ]
            )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(payload["mode"], "agentic-benchmark-report")
        self.assertEqual(payload["runs"][0]["variant"], "agentic")
        self.assertEqual(payload["runs"][0]["label"], "toy")

    def test_cli_returns_user_error_for_missing_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            missing = root / "missing_eval.json"
            output = root / "benchmark.json"
            stderr = io.StringIO()

            with contextlib.redirect_stderr(stderr):
                code = agentic_benchmark_main(["--run", str(missing), "--out", str(output)])

        self.assertEqual(code, 2)
        self.assertIn("report_not_found", stderr.getvalue())
        self.assertIn(str(missing), stderr.getvalue())
        self.assertFalse(output.exists())


def _write_eval(path: Path) -> str:
    payload = {
        "mode": "agentic-run-evaluation-report",
        "scope": "single_run",
        "status": "success",
        "blocked_reason": "",
        "evidence_coverage_score": 1.0,
        "unsupported_claim_rate": 0.0,
        "partial_claim_rate": 0.0,
        "retrieval_loops": 0,
        "revision_loops": 0,
        "validation_passed": True,
        "invariant_audit_passed": True,
        "readiness_passed": True,
        "traceability_passed": True,
        "metrics": [],
        "recommended_actions": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    unittest.main()
