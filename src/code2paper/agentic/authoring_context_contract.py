"""Run-level contract for the Method authoring context lane.

The authoring mode is a run input, not an ambient implementation detail.  This
module keeps the small amount of mode resolution and run telemetry shared by
the product runner, replay command, Writer, and callback resume path.
"""

from __future__ import annotations

import os
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.tool_runtime import atomic_write_bytes
from code2paper.agentic.digest import digest_json
from code2paper.core.output_names import method_output

AuthoringContextMode = Literal["legacy", "shadow_unified", "unified"]
AuthoringModeSource = Literal[
    "argument",
    "profile",
    "environment",
    "default",
    "resume",
]

VALID_AUTHORING_CONTEXT_MODES: tuple[str, ...] = (
    "legacy",
    "shadow_unified",
    "unified",
)


def resolve_authoring_context_mode(
    explicit: str | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    source_hint: str | None = None,
) -> tuple[AuthoringContextMode, AuthoringModeSource]:
    """Resolve one mode with explicit input taking precedence over ambient env."""

    env = environment if environment is not None else os.environ
    explicit_value = str(explicit or "").strip().casefold()
    env_value = str(env.get("CODE2PAPER_AUTHORING_CONTEXT_MODE", "") or "").strip().casefold()
    value = explicit_value or env_value or "legacy"
    if value not in VALID_AUTHORING_CONTEXT_MODES:
        raise ValueError(
            "authoring_context_mode must be one of "
            + ", ".join(VALID_AUTHORING_CONTEXT_MODES)
        )
    if explicit_value:
        hint = str(source_hint or "").strip().casefold()
        source = "resume" if hint == "resume" else "argument"
    elif env_value:
        hint = str(source_hint or "").strip().casefold()
        source = "profile" if hint == "profile" else "environment"
    else:
        source = "default"
    return value, source  # type: ignore[return-value]


def expected_authoring_artifact_keys(mode: str) -> tuple[str, ...]:
    """Return the artifact contract for the selected lane.

    Unified deliberately does not require the legacy MethodSectionPlan before
    the unified reconstruction has run.  The research evidence inputs remain
    mandatory; a missing derived plan is reported as typed research evidence
    missing by the Writer rather than as a legacy preflight failure.
    """

    if mode == "unified":
        return (
            "atomic_claims_v3",
            "code_facts_v1",
            "equation_claims_v1",
            "configuration_claims_v1",
            "method_completeness_matrix_v1",
            "mechanism_context_set_v1",
            "mechanism_evidence_closures_v1",
            "mechanism_context_completeness_v1",
            "narrative_plan_v3",
            "mechanism_shared_payload_trace_v1",
            "mechanism_context_page_manifest_v1",
            "mechanism_formula_obligations_v1",
            "mechanism_formula_packages_v2",
        )
    if mode == "shadow_unified":
        return (
            "atomic_claims_v3",
            "code_facts_v1",
            "equation_claims_v1",
            "configuration_claims_v1",
            "method_completeness_matrix_v1",
            "method_section_plan_v2",
            "mechanism_context_set_v1",
            "mechanism_evidence_closures_v1",
            "mechanism_context_completeness_v1",
            "narrative_plan_v3",
            "mechanism_context_page_manifest_v1",
            "mechanism_formula_obligations_v1",
            "mechanism_formula_packages_v2",
        )
    return (
        "atomic_claims_v3",
        "code_facts_v1",
        "equation_claims_v1",
        "configuration_claims_v1",
        "method_completeness_matrix_v1",
        "method_section_plan_v2",
    )


class AuthoringRunContractV1(BaseModel):
    """Immutable run-level mode and artifact contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    run_id: str = ""
    requested_mode: AuthoringContextMode
    effective_mode: AuthoringContextMode
    mode_source: AuthoringModeSource
    code_commit_sha: str = "unknown"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    expected_artifact_keys: tuple[str, ...] = Field(default_factory=tuple)
    actual_artifact_keys: tuple[str, ...] = Field(default_factory=tuple)
    missing_artifact_keys: tuple[str, ...] = Field(default_factory=tuple)
    contract_satisfied: bool = True
    initial_mode_digest: str = ""
    resume_mode_digest: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "AuthoringRunContractV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = digest_json(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError("authoring run contract content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


def validate_authoring_run_contract(
    contract: AuthoringRunContractV1,
    *,
    allow_blocked: bool = False,
) -> tuple[bool, tuple[str, ...]]:
    """Validate that all expected artifacts are present in actual artifacts.

    Returns (is_satisfied, missing_keys).
    """
    missing = tuple(
        key for key in contract.expected_artifact_keys
        if key not in contract.actual_artifact_keys
    )
    return len(missing) == 0, missing


def code_commit_sha() -> str:
    """Return an explicitly supplied commit identity without inventing one."""

    return str(os.environ.get("CODE2PAPER_CODE_COMMIT_SHA", "") or "").strip() or "unknown"


def build_authoring_run_contract(
    *,
    requested_mode: str,
    effective_mode: str,
    mode_source: str,
    artifact_paths: Mapping[str, str] | None = None,
    output_paths: Mapping[str, str] | None = None,
    run_id: str = "",
    repo_snapshot_id: str = "",
    project_tree_hash: str = "",
    initial_mode_digest: str = "",
    resume_mode_digest: str = "",
    code_sha: str | None = None,
) -> AuthoringRunContractV1:
    """Build a contract from paths that actually exist on disk."""

    paths = {**(artifact_paths or {}), **(output_paths or {})}
    actual = tuple(sorted(
        str(key)
        for key, value in paths.items()
        if str(key).strip() and str(value).strip() and Path(str(value)).is_file()
    ))
    expected = expected_authoring_artifact_keys(str(effective_mode))
    missing = tuple(sorted(key for key in expected if key not in actual))
    contract_satisfied = len(missing) == 0
    return AuthoringRunContractV1(
        run_id=str(run_id or ""),
        requested_mode=str(requested_mode),  # type: ignore[arg-type]
        effective_mode=str(effective_mode),  # type: ignore[arg-type]
        mode_source=str(mode_source),  # type: ignore[arg-type]
        code_commit_sha=code_sha or code_commit_sha(),
        repo_snapshot_id=str(repo_snapshot_id or ""),
        project_tree_hash=str(project_tree_hash or ""),
        expected_artifact_keys=expected,
        actual_artifact_keys=actual,
        missing_artifact_keys=missing,
        contract_satisfied=contract_satisfied,
        initial_mode_digest=str(initial_mode_digest or ""),
        resume_mode_digest=str(resume_mode_digest or ""),
    )


def write_authoring_run_contract(
    out_root: str | Path,
    contract: AuthoringRunContractV1,
) -> str:
    path = method_output(Path(out_root), "authoring_run_contract_v1")
    atomic_write_bytes(
        path,
        (contract.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )
    return str(path)


__all__ = [
    "AuthoringContextMode",
    "AuthoringModeSource",
    "VALID_AUTHORING_CONTEXT_MODES",
    "AuthoringRunContractV1",
    "resolve_authoring_context_mode",
    "expected_authoring_artifact_keys",
    "validate_authoring_run_contract",
    "build_authoring_run_contract",
    "write_authoring_run_contract",
]
