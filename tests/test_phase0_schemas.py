from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml
from pydantic import ValidationError

from code2paper.schemas import (
    AuthorMarkers,
    CodeAlignmentIR,
    Code2PaperRunManifest,
    CommentIndex,
    ConflictStatus,
    ContextMap,
    MethodEvidence,
    RawEvidencePack,
    RawContextIndex,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Phase0SchemaTests(unittest.TestCase):
    def test_author_markers_example_is_valid(self) -> None:
        payload = load_yaml(EXAMPLES / "author_markers.example.yaml")
        markers = AuthorMarkers.model_validate(payload)
        self.assertEqual(markers.project_goal, "Train and evaluate a Transformer model for machine translation.")
        self.assertEqual(markers.module_roles[0].importance, "core")

    def test_author_markers_invalid_example_is_rejected(self) -> None:
        payload = load_yaml(EXAMPLES / "author_markers.invalid.yaml")
        with self.assertRaises(ValidationError):
            AuthorMarkers.model_validate(payload)

    def test_raw_evidence_pack_schema_fixes_source_types_and_confidence(self) -> None:
        payload = load_json(EXAMPLES / "raw_evidence_pack.example.json")
        pack = RawEvidencePack.model_validate(payload)
        self.assertEqual(pack.readme_policy, "exclude")
        self.assertEqual(pack.evidence_items[0].source_type, "bash")
        self.assertGreaterEqual(pack.evidence_items[0].confidence, 0.0)
        self.assertLessEqual(pack.evidence_items[0].confidence, 1.0)
        self.assertEqual(pack.evidence_items[0].line_start, 1)

    def test_raw_evidence_pack_rejects_bad_confidence_and_missing_path(self) -> None:
        payload = load_json(EXAMPLES / "raw_evidence_pack.example.json")
        payload["evidence_items"][0]["confidence"] = 1.5
        payload["evidence_items"][0]["path"] = ""
        with self.assertRaises(ValidationError):
            RawEvidencePack.model_validate(payload)

    def test_code_alignment_ir_separates_execution_and_method_stages(self) -> None:
        payload = load_json(EXAMPLES / "code_alignment_ir.example.json")
        ir = CodeAlignmentIR.model_validate(payload)
        self.assertEqual(ir.execution_stages[0].stage_id, "X1")
        self.assertEqual(ir.method_stages[0].stage_id, "M1")
        self.assertEqual(ir.stage_mappings[0].execution_stage_id, "X1")
        self.assertEqual(ir.stage_mappings[0].method_stage_id, "M1")

    def test_code_alignment_ir_rejects_unknown_stage_mapping(self) -> None:
        payload = load_json(EXAMPLES / "code_alignment_ir.example.json")
        payload["stage_mappings"][0]["method_stage_id"] = "M404"
        with self.assertRaises(ValidationError):
            CodeAlignmentIR.model_validate(payload)

    def test_method_evidence_schema_tracks_stages_modules_mechanisms(self) -> None:
        payload = load_json(EXAMPLES / "method_evidence.example.json")
        evidence = MethodEvidence.model_validate(payload)
        stage = evidence.stages[0]
        self.assertEqual(stage.stage_id, "S1")
        self.assertEqual(stage.modules[0].category, "method-core")
        self.assertEqual(stage.mechanisms[0].support_status, "supported")
        self.assertEqual(stage.mechanisms[0].evidence_ids, ["E1", "E2"])

    def test_method_evidence_rejects_bad_mechanism_id(self) -> None:
        payload = load_json(EXAMPLES / "method_evidence.example.json")
        payload["stages"][0]["mechanisms"][0]["mechanism_id"] = "BAD1"
        with self.assertRaises(ValidationError):
            MethodEvidence.model_validate(payload)

    def test_attention_transformer_examples_are_valid(self) -> None:
        author_markers = AuthorMarkers.model_validate(load_yaml(EXAMPLES / "attention_author_markers.yaml"))
        raw_pack = RawEvidencePack.model_validate(load_json(EXAMPLES / "attention_raw_evidence_pack.json"))
        alignment = CodeAlignmentIR.model_validate(load_json(EXAMPLES / "attention_code_alignment_ir.json"))
        method_evidence = MethodEvidence.model_validate(load_json(EXAMPLES / "attention_method_evidence.json"))

        self.assertEqual(author_markers.priority_files[0], "train_multi30k_de_en.sh")
        self.assertEqual(raw_pack.project_id, "attention_transformer_pytorch")
        self.assertEqual(raw_pack.evidence_items[0].path, "train_multi30k_de_en.sh")
        self.assertEqual(alignment.execution_stages[0].stage_id, "X1")
        self.assertEqual(alignment.method_stages[0].stage_id, "M1")
        self.assertEqual(method_evidence.stages[0].name, "Input preparation")
        self.assertEqual(method_evidence.stages[-1].mechanisms[-1].evidence_ids, ["E1", "E9"])

    def test_crosscutting_comment_context_and_manifest_schemas(self) -> None:
        comments = CommentIndex.model_validate(
            {
                "comments": [
                    {
                        "comment_id": "CMT-001",
                        "evidence_id": "E-comment-001",
                        "path": "src/model.py",
                        "line_start": 10,
                        "line_end": 11,
                        "comment_type": "method_explanation",
                        "tags": ["@method"],
                        "summary": "Explains the method stage.",
                        "navigation_weight": "high",
                        "trust_score": 0.8,
                        "freshness_or_staleness_signal": {"status": "fresh", "reasons": []},
                    }
                ]
            }
        )
        self.assertEqual(comments.comments[0].freshness_or_staleness_signal.status, "fresh")
        self.assertEqual(ConflictStatus.PARTIALLY_SUPPORTED, "partially_supported")

        raw_context = RawContextIndex.model_validate({"project_id": "toy", "entrypoint_candidates": ["train.py"]})
        context_map = ContextMap.model_validate({"likely_entrypoints": ["train.py"]})
        self.assertEqual(raw_context.entrypoint_candidates, context_map.likely_entrypoints)

        manifest = Code2PaperRunManifest.model_validate(
            {
                "run_id": "RUN-1234",
                "created_at": "2026-04-17T00:00:00+00:00",
                "project_root": "/tmp/project",
                "project_hash": "sha256:abc",
                "phase_outputs": {
                    "method_draft_tex": {"path": "paper/method/method_draft.tex", "hash": "sha256:def"}
                },
                "final_draft_hash": "sha256:def",
            }
        )
        self.assertEqual(manifest.phase_outputs["method_draft_tex"].hash, "sha256:def")


if __name__ == "__main__":
    unittest.main()
