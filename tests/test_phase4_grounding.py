from __future__ import annotations

import json
import unittest
from pathlib import Path

from code2paper.pipeline.stages.grounding import write_phase4_artifacts
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence
from tests.tempdir_support import workspace_tempdir


ROOT = Path(__file__).resolve().parents[1]
ATTENTION_FIXTURES = ROOT / "tests" / "fixtures" / "attention_story_first"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Phase35GroundingTests(unittest.TestCase):
    def test_phase4_writes_grounding_bundle(self) -> None:
        method_evidence = MethodEvidence.model_validate(load_json(ATTENTION_FIXTURES / "attention_method_evidence.generated.json"))
        claim_map = ClaimEvidenceMap.model_validate(load_json(ATTENTION_FIXTURES / "attention_claim_evidence_map.generated.json"))

        with workspace_tempdir() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            paths = write_phase4_artifacts(
                method_root=method_root,
                method_evidence=method_evidence,
                claim_map=claim_map,
            )

            manifest = json.loads(paths["phase4_manifest"].read_text(encoding="utf-8"))
            equations_tex = paths["equations_tex"].read_text(encoding="utf-8")
            symbols_tex = paths["symbols_tex"].read_text(encoding="utf-8")
            grounding = paths["grounding_context"].read_text(encoding="utf-8")
            grounding_exists = paths["grounding_context"].exists()
            equations_exists = paths["equations_tex"].exists()
            symbols_exists = paths["symbols_tex"].exists()

        self.assertEqual(manifest["mode"], "equation-and-symbol-grounding")
        self.assertTrue(grounding_exists)
        self.assertTrue(equations_exists)
        self.assertTrue(symbols_exists)
        self.assertIn("## Evidence-backed Stages", grounding)
        self.assertIn("\\begin{equation}", equations_tex)
        self.assertIn("\\paragraph{", symbols_tex)

    def test_phase4_does_not_emit_generic_fallback_equations(self) -> None:
        payload = load_json(ATTENTION_FIXTURES / "attention_method_evidence.generated.json")
        payload["equation_candidates"] = []
        method_evidence = MethodEvidence.model_validate(payload)
        claim_map = ClaimEvidenceMap.model_validate(load_json(ATTENTION_FIXTURES / "attention_claim_evidence_map.generated.json"))

        with workspace_tempdir() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            paths = write_phase4_artifacts(
                method_root=method_root,
                method_evidence=method_evidence,
                claim_map=claim_map,
            )
            equations_tex = paths["equations_tex"].read_text(encoding="utf-8")
            candidates = json.loads(paths["equation_candidates"].read_text(encoding="utf-8"))
            grounding = paths["grounding_context"].read_text(encoding="utf-8")

        self.assertEqual(candidates["equations"], [])
        self.assertNotIn("\\begin{equation}", equations_tex)
        self.assertNotIn("z_{0}", equations_tex)
        self.assertNotIn("\\operatorname{Group}", equations_tex)
        self.assertIn("Do not invent display equations", grounding)

if __name__ == "__main__":
    unittest.main()
