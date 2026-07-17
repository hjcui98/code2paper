from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.invariant_audit import (
    build_invariant_audit,
    check_final_package_traceability,
    load_invariant_audit,
    write_invariant_audit,
)
from code2paper.export.run_manifest import hash_file


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _final_text_gate_artifacts(root: Path, text_path: str, *, claim_id: str = "C1", evidence_id: str = "E1") -> dict[str, str]:
    text = Path(text_path).read_text(encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    projection_digest = "sha256:projection"
    return {
        "final_text_candidate": text_path,
        "authoring_projection": _write_json(root / "authoring_projection.json", {"projection_digest": projection_digest}),
        "final_text_claims": _write_json(
            root / "final_text_claims.json",
            {"input_text_digest": digest, "atomic_claims": [{"atomic_claim_id": "FAC1"}]},
        ),
        "text_evidence_validation": _write_json(
            root / "text_evidence_validation.json",
            {
                "status": "passed",
                "input_text_digest": digest,
                "projection_digest": projection_digest,
                "verdicts": [{"atomic_claim_id": "FAC1", "status": "supported"}],
            },
        ),
        "final_text_trace": _write_json(
            root / "final_text_trace.json",
            {
                "hard_gate_passed": True,
                "input_text_digest": digest,
                "projection_digest": projection_digest,
                "entries": [
                    {
                        "atomic_claim_id": "FAC1",
                        "projection_claim_ids": [claim_id],
                        "direct_evidence_ids": [evidence_id],
                    }
                ],
            },
        ),
    }


def _authoring_context(*, excluded: list[str] | None = None, allowed: list[str] | None = None) -> dict:
    allowed_claims = [
        {
            "claim_id": claim_id,
            "claim_text": "Supported claim.",
            "support_status": "supported",
            "evidence_ids": ["E1"],
            "writing_boundary": "safe_to_write",
        }
        for claim_id in (allowed or ["C1"])
    ]
    excluded_claims = [
        {
            "claim_id": claim_id,
            "claim_text": "Unsupported claim.",
            "support_status": "unsupported",
            "evidence_ids": [],
            "writing_boundary": "do_not_write_as_method_claim",
        }
        for claim_id in (excluded or [])
    ]
    return {
        "hard_gate_passed": True,
        "allowed_claims": allowed_claims,
        "caveated_claims": [],
        "excluded_claims": excluded_claims,
    }


def _authoring_plan(*, claim_ids: list[str] | None = None, evidence_ids: list[str] | None = None) -> dict:
    return {
        "hard_gate_passed": True,
        "sections": [
            {
                "section_id": "AP-S1",
                "heading": "Supported claim",
                "claim_ids": claim_ids or ["C1"],
                "evidence_ids": evidence_ids or ["E1"],
                "caveat_required": False,
            }
        ],
        "excluded_claim_ids": [],
    }


def _authoring_plan_trace(plan: dict | None = None) -> dict:
    return {
        "mode": "agentic-decision-trace",
        "node": "authoring_planner",
        "provider_status": "deterministic_fallback",
        "prompt": {
            "node": "authoring_planner",
            "objective": "test",
            "hard_rules": [],
            "inputs": {},
            "fallback_decision": {},
        },
        "provider_payload": {},
        "parsed_proposal": {},
        "final_decision": plan or _authoring_plan(),
        "safety_notes": [],
    }


def _figure_plan(
    *,
    claim_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    edge_evidence_ids: list[str] | None = None,
) -> dict:
    return {
        "hard_gate_passed": True,
        "nodes": [{"node_id": "N1", "stage_id": "S1", "claim_ids": claim_ids or ["C1"], "evidence_ids": evidence_ids or ["E1"]}],
        "edges": [{"edge_id": "FE1", "source_node_id": "N1", "target_node_id": "N1", "evidence_ids": edge_evidence_ids or ["E1"]}],
    }


def _figure_plan_trace(plan: dict) -> dict:
    return {
        "mode": "agentic-decision-trace",
        "node": "figure_planner",
        "provider_status": "deterministic_fallback",
        "prompt": {
            "node": "figure_planner",
            "objective": "test",
            "hard_rules": [],
            "inputs": {},
            "fallback_decision": {},
        },
        "provider_payload": {},
        "parsed_proposal": {},
        "final_decision": plan,
        "safety_notes": [],
    }


def _evidence_sufficiency_report() -> dict:
    return {
        "mode": "evidence-sufficiency-report",
        "checked_claims": 1,
        "supported_claims": 1,
        "partial_claims": 0,
        "unsupported_claims": 0,
        "claims_with_missing_evidence": 0,
        "support_rate": 1.0,
        "safe_claim_ids": ["C1"],
        "caveated_claim_ids": [],
        "unsupported_claim_ids": [],
        "missing_evidence_claim_ids": [],
        "frozen_evidence_ids": ["E1"],
        "evidence_backed_mechanisms": 1,
        "mechanisms_without_evidence": 0,
        "hard_gate_passed": True,
        "recommended_actions": ["evidence_sufficient_for_grounding_and_authoring"],
    }


def _evidence_sufficiency_trace() -> dict:
    return {
        "mode": "agentic-decision-trace",
        "node": "evidence_sufficiency",
        "provider_status": "deterministic_fallback",
        "prompt": {
            "node": "evidence_sufficiency",
            "objective": "test",
            "hard_rules": [],
            "inputs": {},
            "fallback_decision": {},
        },
        "provider_payload": {},
        "parsed_proposal": {},
        "final_decision": {"decision": "proceed_to_grounding", "recommended_next": "grounding"},
        "safety_notes": [],
    }


class AgenticInvariantAuditTests(unittest.TestCase):
    def test_audit_passes_when_unsupported_claims_are_excluded_before_authoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            figure_plan = _figure_plan(claim_ids=[], evidence_ids=["E1"])
            artifacts = {
                "evidence": _write_json(
                    root / "evidence.json",
                    {
                        "project_id": "demo",
                        "stages": [
                            {
                                "stage_id": "S1",
                                "mechanisms": [{"mechanism_id": "M1", "evidence_ids": ["E1"]}],
                            }
                        ],
                    },
                ),
                "claims": _write_json(
                    root / "claims.json",
                    {
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]},
                            {"claim_id": "C2", "support_status": "unsupported", "evidence_ids": []},
                        ]
                    },
                ),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {
                        "hard_gate_passed": False,
                        "claims_with_missing_evidence": 0,
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported"},
                            {"claim_id": "C2", "support_status": "unsupported"},
                        ],
                    },
                ),
                "evidence_sufficiency_report": _write_json(root / "evidence_sufficiency_report.json", _evidence_sufficiency_report()),
                "evidence_sufficiency_decision_trace": _write_json(root / "evidence_sufficiency_trace.json", _evidence_sufficiency_trace()),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": ["C2"]}),
                "authoring_context": _write_json(root / "authoring_context.json", _authoring_context(excluded=["C2"])),
                "authoring_plan": _write_json(root / "authoring_plan.json", _authoring_plan()),
                "authoring_plan_decision_trace": _write_json(root / "authoring_plan_decision_trace.json", _authoring_plan_trace()),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
                "figure_plan": _write_json(root / "method_overview.intent.json", figure_plan),
                "figure_plan_decision_trace": _write_json(
                    root / "method_overview.intent.decision_trace.json",
                    _figure_plan_trace(figure_plan),
                ),
            }
            artifacts.update(_final_text_gate_artifacts(root, artifacts["text_md"]))
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        self.assertTrue(audit.passed)
        self.assertEqual(audit.blocking_failures, 0)
        self.assertIn("all_agentic_evidence_invariants_satisfied", audit.recommended_actions)

    def test_audit_blocks_method_text_without_evidence_sufficiency_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "authoring_context": _write_json(root / "authoring_context.json", _authoring_context()),
                "authoring_plan": _write_json(root / "authoring_plan.json", _authoring_plan()),
                "authoring_plan_decision_trace": _write_json(root / "authoring_plan_decision_trace.json", _authoring_plan_trace()),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        sufficiency_check = next(check for check in audit.checks if check.name == "evidence_sufficiency_gate")
        self.assertFalse(sufficiency_check.passed)
        self.assertIn("sufficiency review artifacts are missing", sufficiency_check.message)
        self.assertIn("run_evidence_sufficiency_review_before_authoring", audit.recommended_actions)

    def test_audit_blocks_method_text_without_authoring_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"project_id": "demo"}),
                "claims": _write_json(root / "claims.json", {"claims": []}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": []},
                ),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        self.assertFalse(audit.passed)
        self.assertTrue(any(check.name == "authoring_constraints_gate" and not check.passed for check in audit.checks))
        self.assertIn("rebuild_authoring_constraints_from_claim_verification", audit.recommended_actions)

    def test_audit_blocks_method_text_without_authoring_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        context_check = next(check for check in audit.checks if check.name == "authoring_context_gate")
        self.assertFalse(context_check.passed)
        self.assertIn("authoring_context.json is missing", context_check.message)
        self.assertIn("rebuild_authoring_context_from_verified_claim_constraints", audit.recommended_actions)

    def test_audit_blocks_authoring_context_that_marks_excluded_claim_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(
                    root / "claims.json",
                    {
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]},
                            {"claim_id": "C2", "support_status": "unsupported", "evidence_ids": []},
                        ]
                    },
                ),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {
                        "claims_with_missing_evidence": 0,
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported"},
                            {"claim_id": "C2", "support_status": "unsupported"},
                        ],
                    },
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": ["C2"]}),
                "authoring_context": _write_json(root / "authoring_context.json", _authoring_context(allowed=["C1", "C2"])),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        context_check = next(check for check in audit.checks if check.name == "authoring_context_gate")
        self.assertFalse(context_check.passed)
        self.assertIn("excluded or unsupported claims marked writable: C2", context_check.message)

    def test_audit_blocks_authoring_plan_that_uses_excluded_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            authoring_plan = _authoring_plan(claim_ids=["C2"])
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(
                    root / "claims.json",
                    {
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]},
                            {"claim_id": "C2", "support_status": "unsupported", "evidence_ids": []},
                        ]
                    },
                ),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {
                        "claims_with_missing_evidence": 0,
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported"},
                            {"claim_id": "C2", "support_status": "unsupported"},
                        ],
                    },
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": ["C2"]}),
                "authoring_context": _write_json(root / "authoring_context.json", _authoring_context(excluded=["C2"])),
                "authoring_plan": _write_json(root / "authoring_plan.json", authoring_plan),
                "authoring_plan_decision_trace": _write_json(
                    root / "authoring_plan_decision_trace.json",
                    _authoring_plan_trace(authoring_plan),
                ),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        plan_check = next(check for check in audit.checks if check.name == "authoring_plan_gate")
        self.assertFalse(plan_check.passed)
        self.assertIn("excluded or unsupported claims", plan_check.message)
        self.assertIn("rebuild_authoring_plan_from_evidence_bound_authoring_context", audit.recommended_actions)

    def test_audit_blocks_stale_authoring_plan_decision_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            authoring_plan = _authoring_plan()
            stale_plan = _authoring_plan(evidence_ids=["E404"])
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "evidence_sufficiency_report": _write_json(root / "evidence_sufficiency_report.json", _evidence_sufficiency_report()),
                "evidence_sufficiency_decision_trace": _write_json(root / "evidence_sufficiency_trace.json", _evidence_sufficiency_trace()),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "authoring_context": _write_json(root / "authoring_context.json", _authoring_context()),
                "authoring_plan": _write_json(root / "authoring_plan.json", authoring_plan),
                "authoring_plan_decision_trace": _write_json(
                    root / "authoring_plan_decision_trace.json",
                    _authoring_plan_trace(stale_plan),
                ),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        plan_check = next(check for check in audit.checks if check.name == "authoring_plan_gate")
        self.assertFalse(plan_check.passed)
        self.assertIn("authoring_plan decision trace final_decision does not match", plan_check.message)

    def test_audit_blocks_method_text_without_text_claims_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        self.assertFalse(audit.passed)
        self.assertTrue(any(check.name == "text_claim_traceability" and not check.passed for check in audit.checks))
        self.assertIn("rebuild_text_claims_from_frozen_evidence_before_validation", audit.recommended_actions)

    def test_audit_blocks_text_claims_with_unknown_evidence_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E404"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        trace_check = next(check for check in audit.checks if check.name == "text_claim_traceability")
        self.assertFalse(trace_check.passed)
        self.assertIn("unknown evidence ids: E404", trace_check.message)

    def test_audit_blocks_text_claims_outside_authoring_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "evidence": _write_json(
                    root / "evidence.json",
                    {"stages": [{"mechanisms": [{"evidence_ids": ["E1", "E2"]}]}]},
                ),
                "claims": _write_json(
                    root / "claims.json",
                    {
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]},
                            {"claim_id": "C2", "support_status": "supported", "evidence_ids": ["E2"]},
                        ]
                    },
                ),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {
                        "claims_with_missing_evidence": 0,
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported"},
                            {"claim_id": "C2", "support_status": "supported"},
                        ],
                    },
                ),
                "evidence_sufficiency_report": _write_json(root / "evidence_sufficiency_report.json", _evidence_sufficiency_report()),
                "evidence_sufficiency_decision_trace": _write_json(root / "evidence_sufficiency_trace.json", _evidence_sufficiency_trace()),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "authoring_context": _write_json(root / "authoring_context.json", _authoring_context(allowed=["C1", "C2"])),
                "authoring_plan": _write_json(root / "authoring_plan.json", _authoring_plan(claim_ids=["C1"], evidence_ids=["E1"])),
                "authoring_plan_decision_trace": _write_json(
                    root / "authoring_plan_decision_trace.json",
                    _authoring_plan_trace(_authoring_plan(claim_ids=["C1"], evidence_ids=["E1"])),
                ),
                "text_md": _write_json(root / "method.md", {"text": "method"}),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C2"], "evidence_span_ids": ["E2"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        trace_check = next(check for check in audit.checks if check.name == "text_claim_traceability")
        self.assertFalse(trace_check.passed)
        self.assertIn("text claim ids outside authoring plan: C2", trace_check.message)
        self.assertIn("text evidence ids outside authoring plan: E2", trace_check.message)

    def test_audit_blocks_figure_plan_with_unknown_evidence_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            figure_plan = _figure_plan(evidence_ids=["E404"])
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "figure_plan": _write_json(root / "method_overview.intent.json", figure_plan),
                "figure_plan_decision_trace": _write_json(
                    root / "method_overview.intent.decision_trace.json",
                    _figure_plan_trace(figure_plan),
                ),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        figure_check = next(check for check in audit.checks if check.name == "figure_evidence_plan")
        self.assertFalse(figure_check.passed)
        self.assertIn("unknown figure evidence ids: E404", figure_check.message)
        self.assertIn("rebuild_figure_plan_from_verified_method_evidence", audit.recommended_actions)

    def test_audit_blocks_figure_plan_using_unsupported_claim_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            figure_plan = _figure_plan(claim_ids=["C2"], evidence_ids=["E1"])
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(
                    root / "claims.json",
                    {
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]},
                            {"claim_id": "C2", "support_status": "unsupported", "evidence_ids": []},
                        ]
                    },
                ),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {
                        "claims_with_missing_evidence": 0,
                        "claims": [
                            {"claim_id": "C1", "support_status": "supported"},
                            {"claim_id": "C2", "support_status": "unsupported"},
                        ],
                    },
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": ["C2"]}),
                "figure_plan": _write_json(root / "method_overview.intent.json", figure_plan),
                "figure_plan_decision_trace": _write_json(
                    root / "method_overview.intent.decision_trace.json",
                    _figure_plan_trace(figure_plan),
                ),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        figure_check = next(check for check in audit.checks if check.name == "figure_evidence_plan")
        self.assertFalse(figure_check.passed)
        self.assertIn("excluded or unsupported claim ids used in figure: C2", figure_check.message)

    def test_audit_blocks_stale_figure_plan_decision_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            figure_plan = _figure_plan(evidence_ids=["E1"])
            stale_plan = _figure_plan(evidence_ids=["E404"])
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "figure_plan": _write_json(root / "method_overview.intent.json", figure_plan),
                "figure_plan_decision_trace": _write_json(
                    root / "method_overview.intent.decision_trace.json",
                    _figure_plan_trace(stale_plan),
                ),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        figure_check = next(check for check in audit.checks if check.name == "figure_evidence_plan")
        self.assertFalse(figure_check.passed)
        self.assertIn("figure_plan decision trace final_decision does not match", figure_check.message)

    def test_audit_passes_final_package_when_final_tex_embeds_audited_source_tex(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_tex = root / "method_clean.tex"
            final_tex = root / "final_method.tex"
            source_body = "\\subsection{Overview}\nEvidence-backed text."
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "evidence_sufficiency_report": _write_json(root / "evidence_sufficiency_report.json", _evidence_sufficiency_report()),
                "evidence_sufficiency_decision_trace": _write_json(root / "evidence_sufficiency_trace.json", _evidence_sufficiency_trace()),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "authoring_context": _write_json(root / "authoring_context.json", _authoring_context()),
                "authoring_plan": _write_json(root / "authoring_plan.json", _authoring_plan()),
                "authoring_plan_decision_trace": _write_json(root / "authoring_plan_decision_trace.json", _authoring_plan_trace()),
                "text_clean_tex": _write_text(source_tex, source_body),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
                "final_tex": _write_text(final_tex, "\\begin{document}\n" + source_body + "\n\\end{document}\n"),
                "finalize_manifest": _write_json(root / "finalize_manifest.json", {"inputs": {"text_tex": str(source_tex)}}),
            }
            artifacts.update(_final_text_gate_artifacts(root, artifacts["text_clean_tex"]))
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        final_check = next(check for check in audit.checks if check.name == "final_package_traceability")
        self.assertTrue(final_check.passed)
        self.assertTrue(audit.passed)

    def test_audit_blocks_final_package_when_final_tex_does_not_embed_source_tex(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_tex = root / "method_clean.tex"
            final_tex = root / "final_method.tex"
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "text_clean_tex": _write_text(source_tex, "\\subsection{Overview}\nEvidence-backed text."),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
                "final_tex": _write_text(final_tex, "\\begin{document}\nUntracked rewritten method.\n\\end{document}\n"),
                "finalize_manifest": _write_json(root / "finalize_manifest.json", {"inputs": {"text_tex": str(source_tex)}}),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        final_check = next(check for check in audit.checks if check.name == "final_package_traceability")
        self.assertFalse(final_check.passed)
        self.assertIn("does not contain", final_check.message)
        self.assertIn("rebuild_final_package_from_validated_authoring_tex", audit.recommended_actions)

    def test_audit_blocks_final_package_from_unregistered_source_tex(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            registered_source = root / "method_clean.tex"
            unregistered_source = root / "other.tex"
            final_tex = root / "final_method.tex"
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                "text_clean_tex": _write_text(registered_source, "\\subsection{Overview}\nEvidence-backed text."),
                "text_claims": _write_json(
                    root / "text_claims.json",
                    {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                ),
                "validation_manifest": _write_json(root / "validation_manifest.json", {"status": "success"}),
                "final_tex": _write_text(final_tex, "\\begin{document}\nOther text.\n\\end{document}\n"),
                "finalize_manifest": _write_json(
                    root / "finalize_manifest.json",
                    {"inputs": {"text_tex": _write_text(unregistered_source, "Other text.")}},
                ),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        final_check = next(check for check in audit.checks if check.name == "final_package_traceability")
        self.assertFalse(final_check.passed)
        self.assertIn("not a registered audited authoring artifact", final_check.message)

    def test_formal_package_lineage_detects_post_package_figure_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_body = "\\subsection{Overview}\nEvidence-backed text."
            artifacts = {
                "text_clean_tex": _write_text(root / "method_clean.tex", source_body),
                "final_tex": _write_text(root / "final_method.tex", "\\begin{document}\n" + source_body + "\n\\end{document}\n"),
            }
            for key in (
                "intent_spec", "repo_snapshot", "evidence_snapshot_v2", "final_text_candidate",
                "final_text_claims", "text_evidence_validation", "final_text_trace",
                "validation_manifest", "traceability_ledger", "figure_scene",
                "figure_relation_validation", "pre_render_audit", "method_overview_svg",
                "rendering_manifest", "post_render_audit", "final_pdf_report",
                "root_method_md", "root_method_tex", "final_pdf",
            ):
                artifacts[key] = _write_text(root / key, f"artifact:{key}\n")

            lineage_key_map = {
                "source_text_tex": "text_clean_tex",
                **{
                    key: key
                    for key in (
                        "intent_spec", "repo_snapshot", "evidence_snapshot_v2", "final_text_candidate",
                        "final_text_claims", "text_evidence_validation", "final_text_trace",
                        "validation_manifest", "traceability_ledger", "figure_scene",
                        "figure_relation_validation", "pre_render_audit", "method_overview_svg",
                        "rendering_manifest", "post_render_audit",
                    )
                },
            }
            manifest = {
                "schema_version": "2.0",
                "lineage_complete": True,
                "inputs": {"text_tex": artifacts["text_clean_tex"]},
                "lineage": {
                    manifest_key: _artifact_record(Path(artifacts[state_key]))
                    for manifest_key, state_key in lineage_key_map.items()
                },
                "outputs": {
                    manifest_key: _artifact_record(Path(artifacts[state_key]))
                    for manifest_key, state_key in {
                        "final_tex": "final_tex", "final_pdf": "final_pdf",
                        "final_pdf_report": "final_pdf_report", "method_md": "root_method_md",
                        "method_tex": "root_method_tex",
                    }.items()
                },
            }
            artifacts["finalize_manifest"] = _write_json(root / "finalize_manifest.json", manifest)
            artifacts["package_manifest"] = _write_json(root / "package_manifest.json", manifest)
            state = AgenticRunState(project_root=root, out_root=root, artifacts=artifacts)

            self.assertTrue(check_final_package_traceability(state).passed)
            Path(artifacts["method_overview_svg"]).write_text("tampered\n", encoding="utf-8")
            check = check_final_package_traceability(state)

        self.assertFalse(check.passed)
        self.assertIn("lineage.method_overview_svg hash does not match", check.message)

    def test_audit_round_trips_to_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(project_root=Path("."), out_root=root)
            audit = build_invariant_audit(state)
            path = root / "agentic_invariant_audit.json"
            write_invariant_audit(path, audit)
            loaded = load_invariant_audit(path)

        self.assertEqual(loaded.blocking_failures, audit.blocking_failures)


def _artifact_record(path: Path) -> dict[str, str]:
    return {"path": str(path), "hash": hash_file(path)}


if __name__ == "__main__":
    unittest.main()
