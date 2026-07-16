from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

from code2paper.agentic.contracts import AgenticRunState, StageStatus
from code2paper.agentic.final_text_claims import text_digest
from code2paper.agentic.legacy_late_stage_tools import _authoritative_final_text_gate, run_validation
from code2paper.core.output_names import method_output
from code2paper.core.schemas import (
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    EvidenceItem,
    EvidenceStrength,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    RawEvidencePack,
    SourceType,
    SupportStatus,
)


class AgenticValidationTests(unittest.TestCase):
    def test_authoritative_final_text_gate_passes_only_for_digest_bound_direct_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            text = "# Method\n\nThe encoder uses features.\n"
            digest = text_digest(text)
            text_path = root / "method_clean.md"
            text_path.write_text(text, encoding="utf-8")
            snapshot = {"repo_snapshot_id": "repo:1", "project_tree_hash": "sha256:tree",
                        "evidence_snapshot_id": "evidence:1", "evidence_snapshot_digest": "sha256:evidence"}
            artifacts = {
                "repo_snapshot": _json(root / "repo.json", {"snapshot_id": "repo:1"}),
                "evidence_snapshot_v2": _json(root / "evidence-v2.json", {"spans": [{"evidence_id": "E1", "status": "valid"}]}),
                "authoring_projection": _json(root / "projection.json", {"projection_digest": "sha256:projection", **snapshot}),
                "final_text_claims": _json(root / "claims.json", {"input_text_digest": digest,
                    "deterministic_completeness_passed": True, "atomic_claims": [{"atomic_claim_id": "FAC1"}]}),
                "text_evidence_validation": _json(root / "validation.json", {"status": "passed", "input_text_digest": digest,
                    "projection_digest": "sha256:projection", "verdicts": [{"atomic_claim_id": "FAC1", "status": "supported"}], **snapshot}),
                "final_text_trace": _json(root / "trace.json", {"hard_gate_passed": True, "input_text_digest": digest,
                    "projection_digest": "sha256:projection", "entries": [{"atomic_claim_id": "FAC1", "direct_evidence_ids": ["E1"]}], **snapshot}),
                "final_text_candidate": str(text_path),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            passed, failures = _authoritative_final_text_gate(state, text_path)
            text_path.write_text(text + "Tampered.\n", encoding="utf-8")
            tampered, tampered_failures = _authoritative_final_text_gate(state, text_path)

        self.assertTrue(passed, failures)
        self.assertFalse(tampered)
        self.assertIn("final_text_digest_mismatch", tampered_failures)

    def test_validation_uses_grounded_draft_when_clean_text_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            method_output(state.method_root, "evidence").parent.mkdir(parents=True, exist_ok=True)
            method_output(state.method_root, "evidence_raw").write_text(_raw_pack().model_dump_json(), encoding="utf-8")
            method_output(state.method_root, "evidence").write_text(_method_evidence().model_dump_json(), encoding="utf-8")
            method_output(state.method_root, "claims").write_text(_claim_map().model_dump_json(), encoding="utf-8")
            method_output(state.method_root, "text_md").write_text(
                "# Method\n\n<!-- c2p: stage=S1; evidence=E1; confidence=medium -->\nGrounded paragraph.\n",
                encoding="utf-8",
            )
            method_output(state.method_root, "text_clean_md").write_text("# Method\n\nGrounded paragraph.\n", encoding="utf-8")

            with patch("code2paper.agentic.legacy_late_stage_tools.validate_method_fidelity") as validator:
                validator.return_value = _FidelityReport(passed=True)
                result = run_validation(state)
                draft_markdown = validator.call_args.kwargs["draft_markdown"]

        self.assertEqual(result.status, StageStatus.SUCCESS)
        self.assertIn("<!-- c2p:", draft_markdown)

    def test_failed_validation_manifest_blocks_even_when_fidelity_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            method_output(state.method_root, "evidence").parent.mkdir(parents=True, exist_ok=True)
            method_output(state.method_root, "evidence_raw").write_text(_raw_pack().model_dump_json(), encoding="utf-8")
            method_output(state.method_root, "evidence").write_text(_method_evidence().model_dump_json(), encoding="utf-8")
            method_output(state.method_root, "claims").write_text(_claim_map().model_dump_json(), encoding="utf-8")
            method_output(state.method_root, "text_md").write_text("# Method\n\nGrounded paragraph.\n", encoding="utf-8")

            with (
                patch("code2paper.agentic.legacy_late_stage_tools.validate_method_fidelity") as validator,
                patch("code2paper.agentic.legacy_late_stage_tools.write_phase6_validation_manifest") as writer,
            ):
                validator.return_value = _FidelityReport(passed=True)
                writer.return_value = {"status": "failed", "failed_reports": ["qa_claims"]}
                result = run_validation(state)

        self.assertEqual(result.status, StageStatus.BLOCKED)
        self.assertEqual(result.blocked_reason, "validation_manifest_failed")
        self.assertFalse(result.metrics["validation_passed"])


class _FidelityReport(BaseModel):
    passed: bool


def _json(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _raw_pack() -> RawEvidencePack:
    return RawEvidencePack(
        project_id="demo",
        project_root="/repo",
        evidence_items=[
            EvidenceItem(
                evidence_id="E1",
                source_type=SourceType.SOURCE,
                path="train.py",
                line_start=1,
                line_end=4,
                evidence_strength=EvidenceStrength.HARD,
                confidence=0.9,
                content_summary="training_loop",
            )
        ],
    )


def _method_evidence() -> MethodEvidence:
    return MethodEvidence(
        project_id="demo",
        method_name="Demo",
        method_goal="Explain the implementation.",
        implementation_scope="current codebase",
        stages=[
            MethodStageEvidence(
                stage_id="S1",
                name="Training",
                purpose="Run training.",
                mechanisms=[
                    Mechanism(
                        mechanism_id="MECH1",
                        description="Training uses the implementation entrypoint.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E1"],
                    )
                ],
            )
        ],
    )


def _claim_map() -> ClaimEvidenceMap:
    return ClaimEvidenceMap(
        claims=[
            ClaimEvidenceItem(
                claim_id="C1",
                claim_text="Training uses the implementation entrypoint.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
            )
        ]
    )


if __name__ == "__main__":
    unittest.main()
