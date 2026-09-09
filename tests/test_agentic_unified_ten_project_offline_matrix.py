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
