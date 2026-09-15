"""Offline matrix harness: rebuild-only inputs, fail-closed stages.

The offline gate must reproduce the production chain with zero model calls:
rebuild the source closure, recompile the current mechanism context, recompile
formula obligations, rebuild the narrative plan, then build archive/worksets/
invocation plans and admission.  These tests pin the harness rules that keep it
from silently validating stale artifacts.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from code2paper.agentic import formalization_agent


def _load_matrix_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_unified_ten_project_offline_matrix.py"
    spec = importlib.util.spec_from_file_location(
        "run_unified_ten_project_offline_matrix", script
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MATRIX = _load_matrix_module()


def test_context_rebuild_inputs_exclude_legacy_context_set(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "mechanism_context_set_v1.json").write_text(
        json.dumps({"contexts": []}), encoding="utf-8"
    )

    inputs, diagnostics = MATRIX._context_rebuild_inputs(tmp_path)

    # The legacy context set is exactly what the current compiler must
    # replace; it can never be a rebuild input.
    assert "context_set" not in inputs
    assert any(
        item.startswith("unified_context_rebuild_input_missing:")
        for item in diagnostics
    )


def test_project_without_repo_fails_source_rehydration(tmp_path: Path) -> None:
    row = MATRIX.project_unified_offline(
        "project",
        tmp_path,
        repo_path=None,
        profile_path=None,
        model_context_override=131072,
        max_attempts=2,
    )

    assert row["status"] == "fail"
    assert "unified_source_rehydration_missing" in row["failure_codes"]
    assert row["source"]["status"] == "fail"


def test_deterministic_formula_packages_disable_operation_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, object]] = []

    def fake_builder(**kwargs: object) -> tuple[str, ...]:
        captured.append(kwargs)
        return ("package",)

    monkeypatch.setattr(
        formalization_agent,
        "build_deterministic_mechanism_formula_packages",
        fake_builder,
    )

    class _Context:
        mechanism_id = "mech_sym:encoder"

    class _Contexts:
        contexts = (_Context(),)

    packages = MATRIX._deterministic_formula_packages(
        contexts=_Contexts(),
        formula_obligations={"mech_sym:encoder": ("obl:1",)},
        research={"equations": ("equation:1",)},
    )

    assert packages == ("package",)
    assert len(captured) == 1
    assert captured[0]["obligations"] == ("obl:1",)
    assert captured[0]["equations"] == ("equation:1",)
    # Offline must never invent an equation from an operation shape.
    assert captured[0]["allow_deterministic_operation_fallback"] is False


# ---------------------------------------------------------------------------
# R2.5 strict/Candidate research-gate parity
# ---------------------------------------------------------------------------

def _partial_agenda():
    from code2paper.agentic.intent_compiler_v2 import (
        IntentObligationGraphV2,
        IntentObligationV2,
    )
    from code2paper.agentic.research_models import (
        ResearchAgendaItemV1,
        ResearchAgendaV1,
    )

    item = ResearchAgendaItemV1(
        obligation_id="core-partial",
        priority="must_cover",
        status="partial",
        supported_claim_ids=["claim-1"],
        missing_information=["call_relation:callee output"],
        attempted_actions=["READ_CANDIDATE"],
    )
    graph = IntentObligationGraphV2(obligations=[IntentObligationV2(
        obligation_id="core-partial",
        kind="organization",
        priority="must_cover",
        source_field="organization",
        author_text="Describe the core mechanism.",
    )])
    agenda = ResearchAgendaV1(
        run_id="run-matrix",
        repo_snapshot_id="repo:snapshot",
        project_tree_hash="sha256:tree",
        items=[item],
        intent_graph_digest=graph.content_digest,
    )

    class _Contexts:
        repo_snapshot_id = "repo:snapshot"
        project_tree_hash = "sha256:tree"

    return graph, agenda, _Contexts()


def test_matrix_research_gate_is_the_product_strict_gate() -> None:
    from code2paper.agentic.publication_method_writer import (
        _unified_research_gate_failures,
    )

    graph, agenda, contexts = _partial_agenda()
    inputs = {
        "intent_graph": graph,
        "research_agenda": agenda,
        "context_set": contexts,
    }

    matrix_failures = MATRIX._research_gate_failures(inputs)
    product_failures = _unified_research_gate_failures(
        intent_graph=graph,
        research_agenda=agenda,
        contexts=contexts,
    )

    assert matrix_failures == product_failures
    assert "unified_core_intent_partial_without_terminal_gap:core-partial" in matrix_failures


def test_matrix_reports_strict_and_candidate_lanes_separately(tmp_path: Path) -> None:
    graph, agenda, contexts = _partial_agenda()
    inputs = {
        "intent_graph": graph,
        "research_agenda": agenda,
        "context_set": contexts,
    }

    strict, candidate, diagnostics = MATRIX._research_mode_failures(
        inputs,
        artifact_paths={},
    )

    # Without a handoff the Candidate lane is exactly the strict lane; a
    # partial is never silently promoted.
    assert candidate == strict
    assert diagnostics["candidate_gate_pass"] is False
    assert diagnostics["candidate_handoff_status"] == "missing"
    assert diagnostics["gate_mode"] == "strict"
    assert diagnostics["strict_failure_codes"] == list(strict)
    assert diagnostics["candidate_failure_codes"] == list(strict)

    # A handoff that fails authentication is reported as rejected and still
    # cannot relax the strict failures.
    bad_handoff = tmp_path / "candidate_handoff_v1.json"
    bad_handoff.write_text("{not json", encoding="utf-8")
    strict_bad, candidate_bad, diagnostics_bad = MATRIX._research_mode_failures(
        inputs,
        artifact_paths={"candidate_handoff_v1": str(bad_handoff)},
    )

    assert candidate_bad == strict_bad == strict
    assert diagnostics_bad["candidate_handoff_status"] == "rejected"
    assert diagnostics_bad["candidate_handoff_revalidation_failures"] == [
        "candidate_handoff_invalid",
    ]
    assert diagnostics_bad["candidate_gate_pass"] is False


def test_matrix_research_gate_reports_missing_context_like_the_product() -> None:
    from code2paper.agentic.publication_method_writer import (
        _unified_research_gate_failures,
    )

    graph, agenda, _contexts = _partial_agenda()
    inputs = {"intent_graph": graph, "research_agenda": agenda}

    assert MATRIX._research_gate_failures(inputs) == _unified_research_gate_failures(
        intent_graph=graph,
        research_agenda=agenda,
        contexts=None,
    )
    assert "unified_research_context_set_missing" in MATRIX._research_gate_failures(inputs)
