from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from code2paper.cli.agentic_benchmark import main as agentic_benchmark_main


def _external_benchmark_datasets_available() -> bool:
    """Check whether the external benchmark datasets exist on disk."""
    dataset_root = Path("datasets")
    required = [
        dataset_root / "FastGS/FastGS - Training 3D Gaussian Splatting in 100 Seconds",
        dataset_root / "Spatial-SSRL/Spatial-SSRL - Enhancing Spatial Understanding via Self-Supervised Reinforcement Learning",
        dataset_root / "MOS/MOS - Mitigating Optical-SAR Modality Gap for Cross-Modal Ship Re-Identification",
    ]
    return all(d.is_dir() for d in required)


class AgenticBenchmarkCliTests(unittest.TestCase):
    @unittest.skipIf(not _external_benchmark_datasets_available(), "external benchmark datasets not available")
    def test_cli_builds_p4_v2_report_and_fail_closed_cutover(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            observations = root / "observations.json"
            observations.write_text(json.dumps([{
                "case_id": "toy_train",
                "variant": "agentic_deterministic",
                "repeat_index": 1,
                "run_status": "blocked",
                "blocked_reason": "gold_scope_smoke",
                "claims": [],
                "figure_elements": [],
                "detected_mutation_ids": ["TM1", "TM2", "TM3"],
                "stale_trials": 1,
                "stale_detected": 1,
                "false_block_human_reviewed": True
            }]), encoding="utf-8")
            output = root / "benchmark_v2.json"
            cutover = root / "cutover.json"
            code = agentic_benchmark_main([
                "--gold", str(Path("tests/fixtures/benchmark_v2/gold_adversarial_v1.json").resolve()),
                "--observations", str(observations),
                "--workspace-root", str(Path.cwd()),
                "--out", str(output),
                "--cutover-out", str(cutover),
            ])
            report_payload = json.loads(output.read_text(encoding="utf-8"))
            cutover_payload = json.loads(cutover.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(report_payload["schema_version"], "2.0")
        self.assertEqual(report_payload["case_count"], 4)
        self.assertEqual(cutover_payload["status"], "hold")
        self.assertEqual(cutover_payload["default_mode"], "legacy")
        self.assertEqual(cutover_payload["validated_benchmark_evidence"]["source"], "none")
        self.assertIn(
            "digest_pinned_benchmark_observations_not_validated",
            cutover_payload["failures"],
        )

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
