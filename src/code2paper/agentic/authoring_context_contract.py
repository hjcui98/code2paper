"""Run-level contract for the Method authoring context lane.

The authoring mode is a run input, not an ambient implementation detail.  This
module keeps the small amount of mode resolution and run telemetry shared by
the product runner, replay command, Writer, and callback resume path.
"""

from __future__ import annotations

import os
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

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


class RunIdentityV1(BaseModel):
    """Immutable scalar identity for one research/authoring run.

    Paths are artifact references and are intentionally kept out of this
    record.  The identity instead binds the run to the repository state,
    launcher/profile, model, and the Research source sidecars that authorize
    downstream consumers.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    run_id: str
    code_commit_sha: str = "unknown"
    dirty_manifest_digest: str
    launcher_digest: str
    profile_digest: str
    model_identity: str = "unknown"
    model_identity_digest: str
    repo_snapshot_id: str
    project_tree_hash: str
    symbol_index_digest: str = ""
    source_manifest_digest: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "RunIdentityV1":
        for field_name in (
            "run_id",
            "dirty_manifest_digest",
            "launcher_digest",
            "profile_digest",
            "model_identity_digest",
            "repo_snapshot_id",
            "project_tree_hash",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"run identity requires {field_name}")
        expected = digest_json(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("run identity content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


def _git_identity_value(repo_root: str | Path, *args: str) -> str:
    root = Path(repo_root).expanduser().resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def dirty_manifest_digest(repo_root: str | Path) -> str:
    """Digest the Git dirty-path manifest without including file contents."""

    status = _git_identity_value(
        repo_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    return digest_json({
        "repo_root": str(Path(repo_root).expanduser().resolve()),
        "status": tuple(line for line in status.splitlines() if line),
    })


def build_run_identity(
    *,
    run_id: str,
    repo_root: str | Path,
    repo_snapshot_id: str,
    project_tree_hash: str,
    symbol_index_digest: str = "",
    source_manifest_digest: str = "",
    model_identity: str = "unknown",
    model_identity_payload: Any | None = None,
    launcher_payload: Any | None = None,
    profile_payload: Any | None = None,
    code_sha: str | None = None,
    dirty_digest: str | None = None,
) -> RunIdentityV1:
    """Build a complete scalar identity from explicit frozen inputs."""

    root = Path(repo_root).expanduser().resolve()
    commit = str(code_sha or "").strip() or _git_identity_value(root, "rev-parse", "HEAD") or "unknown"
    model_name = str(model_identity or "unknown").strip() or "unknown"
    return RunIdentityV1(
        run_id=str(run_id or "").strip(),
        code_commit_sha=commit,
        dirty_manifest_digest=(
            str(dirty_digest or "").strip() or dirty_manifest_digest(root)
        ),
        launcher_digest=digest_json(
            launcher_payload if launcher_payload is not None else {"entrypoint": "unknown"}
        ),
        profile_digest=digest_json(
            profile_payload if profile_payload is not None else {"profile": "unknown"}
        ),
        model_identity=model_name,
        model_identity_digest=digest_json(
            model_identity_payload
            if model_identity_payload is not None
            else {"model": model_name}
        ),
        repo_snapshot_id=str(repo_snapshot_id or "").strip(),
        project_tree_hash=str(project_tree_hash or "").strip(),
        symbol_index_digest=str(symbol_index_digest or "").strip(),
        source_manifest_digest=str(source_manifest_digest or "").strip(),
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


def expected_authoring_artifact_keys(
    mode: str,
    *,
    candidate_lane: bool = False,
) -> tuple[str, ...]:
    """Return the artifact contract for the selected lane.

    Unified deliberately does not require the legacy MethodSectionPlan before
    the unified reconstruction has run.  The research evidence inputs remain
    mandatory; a missing derived plan is reported as typed research evidence
    missing by the Writer rather than as a legacy preflight failure.
    """

    if mode == "unified":
        keys = (
            "repo_snapshot_v2",
            "symbol_index_v2",
            "repository_source_manifest_v1",
            "implementation_scope_v1",
            "repository_authoring_artifacts_v1",
            "atomic_claims_v3",
            "code_facts_v1",
            "equation_claims_v1",
            "configuration_claims_v1",
            "method_completeness_matrix_v1",
            "intent_obligation_graph_v2",
            "research_agenda_v1",
            "mechanism_context_set_v1",
            "mechanism_evidence_closures_v1",
            "mechanism_context_completeness_v1",
            "narrative_plan_v3",
            "mechanism_shared_payload_trace_v1",
            "mechanism_context_page_manifest_v1",
            "mechanism_formula_obligations_v1",
            "unified_context_archive_v2",
            "consumer_workset_manifest_v2",
            "consumer_workset_manifest_v2.writer.2",
            "run_invocation_budget_envelope_v1",
            "consumer_invocation_plan_v1.1",
            "unified_live_admission_v1.formalizer.1",
            "formalizer_plan_execution_v2",
            "consumer_invocation_plan_v1.2",
            "unified_live_admission_v1.writer.2",
            "mechanism_formula_packages_v2",
            "writer_section_receipts_v2",
            "writer_aggregate_receipt_v2",
            "realizer_plan_execution_v2",
            "realizer_receipts_v2",
            "binder_receipts_v2",
            "run_terminal_event",
        )
        if candidate_lane:
            keys = (*keys, "candidate_handoff_v1", "candidate_retry_ledger_v1")
        return keys
    if mode == "shadow_unified":
        keys = (
            "repo_snapshot_v2",
            "symbol_index_v2",
            "repository_source_manifest_v1",
            "implementation_scope_v1",
            "repository_authoring_artifacts_v1",
            "atomic_claims_v3",
            "code_facts_v1",
            "equation_claims_v1",
            "configuration_claims_v1",
            "method_completeness_matrix_v1",
            "method_section_plan_v2",
            "intent_obligation_graph_v2",
            "research_agenda_v1",
            "mechanism_context_set_v1",
            "mechanism_evidence_closures_v1",
            "mechanism_context_completeness_v1",
            "narrative_plan_v3",
            "mechanism_context_page_manifest_v1",
            "mechanism_formula_obligations_v1",
            "unified_context_archive_v2",
            "consumer_workset_manifest_v2",
            "consumer_workset_manifest_v2.writer.2",
            "run_invocation_budget_envelope_v1",
            "consumer_invocation_plan_v1.1",
            "unified_live_admission_v1.formalizer.1",
            "formalizer_plan_execution_v2",
            "consumer_invocation_plan_v1.2",
            "unified_live_admission_v1.writer.2",
            "mechanism_formula_packages_v2",
            "run_terminal_event",
        )
        if candidate_lane:
            keys = (*keys, "candidate_handoff_v1", "candidate_retry_ledger_v1")
        return keys
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
    not_applicable_artifact_keys: tuple[str, ...] = Field(default_factory=tuple)
    contract_stage: str = "writer"
    run_identity_digest: str = ""
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
    run_identity: RunIdentityV1 | None = None,
    not_applicable_artifact_keys: tuple[str, ...] = (),
    contract_stage: str = "writer",
    candidate_lane: bool = False,
) -> AuthoringRunContractV1:
    """Build a contract from paths that actually exist on disk."""

    paths = {**(artifact_paths or {}), **(output_paths or {})}
    actual = tuple(sorted(
        str(key)
        for key, value in paths.items()
        if str(key).strip() and str(value).strip() and Path(str(value)).is_file()
    ))
    expected = expected_authoring_artifact_keys(
        str(effective_mode),
        candidate_lane=bool(candidate_lane),
    )
    not_applicable = tuple(sorted(
        key for key in not_applicable_artifact_keys if key in expected
    ))
    missing = tuple(sorted(
        key for key in expected
        if key not in actual and key not in set(not_applicable)
    ))
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
        not_applicable_artifact_keys=not_applicable,
        contract_stage=str(contract_stage or "writer"),
        run_identity_digest=(
            str(run_identity.content_digest) if run_identity is not None else ""
        ),
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


def write_run_identity(
    out_root: str | Path,
    identity: RunIdentityV1,
) -> str:
    """Persist the scalar identity in the research-product namespace."""

    path = method_output(Path(out_root), "run_identity_v1")
    atomic_write_bytes(
        path,
        (identity.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )
    return str(path)


__all__ = [
    "AuthoringContextMode",
    "AuthoringModeSource",
    "VALID_AUTHORING_CONTEXT_MODES",
    "AuthoringRunContractV1",
    "RunIdentityV1",
    "build_run_identity",
    "dirty_manifest_digest",
    "resolve_authoring_context_mode",
    "expected_authoring_artifact_keys",
    "validate_authoring_run_contract",
    "build_authoring_run_contract",
    "write_authoring_run_contract",
    "write_run_identity",
]
