"""Shadow/opt-in/canary/rollback routing without changing evidence gates."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


ExecutionMode = Literal["default_ready", "shadow", "opt_in", "canary", "rollback"]


class ExecutionProfileV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    mode: ExecutionMode = "shadow"
    language: str = "python"
    provider: str = ""
    model: str = ""
    evidence_policy_digest: str
    fallback_profile_id: str = ""
    canary_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_profile(self) -> "ExecutionProfileV1":
        if not self.profile_id.strip() or not self.evidence_policy_digest.strip():
            raise ValueError("execution profile identity and evidence policy are required")
        if self.mode == "canary" and not 0.0 < self.canary_fraction < 1.0:
            raise ValueError("canary mode requires a fraction between zero and one")
        if self.mode == "rollback" and not self.fallback_profile_id.strip():
            raise ValueError("rollback mode requires a fallback profile")
        if self.fallback_profile_id.strip() == self.profile_id.strip():
            raise ValueError("execution profile cannot roll back to itself")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        computed = "sha256:" + hashlib.sha256(encoded).hexdigest()
        if self.content_digest.strip() and self.content_digest != computed:
            raise ValueError("execution profile content digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        return self


class ExecutionRouteV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    mode: ExecutionMode
    execute: bool
    shadow: bool = False
    rollback_to: str = ""
    evidence_policy_digest: str


def route_execution_profile(
    profile: ExecutionProfileV1,
    *,
    opt_in: bool = False,
    canary_key: str = "",
    rollback: bool = False,
    default_authorized: bool = False,
) -> ExecutionRouteV1:
    """Resolve deployment routing while preserving one policy digest."""

    if rollback or profile.mode == "rollback":
        if not profile.fallback_profile_id.strip():
            raise ValueError("rollback route requires a fallback profile")
        return ExecutionRouteV1(
            profile_id=profile.profile_id,
            mode="rollback",
            execute=False,
            rollback_to=profile.fallback_profile_id,
            evidence_policy_digest=profile.evidence_policy_digest,
        )
    if profile.mode == "shadow":
        return ExecutionRouteV1(
            profile_id=profile.profile_id,
            mode="shadow",
            execute=False,
            shadow=True,
            evidence_policy_digest=profile.evidence_policy_digest,
        )
    if profile.mode == "opt_in" and not opt_in:
        return ExecutionRouteV1(
            profile_id=profile.profile_id,
            mode="opt_in",
            execute=False,
            evidence_policy_digest=profile.evidence_policy_digest,
        )
    if profile.mode == "canary":
        digest = hashlib.sha256(canary_key.encode("utf-8")).hexdigest()
        bucket = int(digest[:12], 16) / float(16**12)
        execute = bucket < profile.canary_fraction
        return ExecutionRouteV1(
            profile_id=profile.profile_id,
            mode="canary",
            execute=execute,
            shadow=not execute,
            evidence_policy_digest=profile.evidence_policy_digest,
        )
    if profile.mode == "default_ready" and not default_authorized:
        # A profile cannot self-authorize the implicit default.  The caller
        # must provide the independently validated cutover decision.
        return ExecutionRouteV1(
            profile_id=profile.profile_id,
            mode="default_ready",
            execute=False,
            evidence_policy_digest=profile.evidence_policy_digest,
        )
    return ExecutionRouteV1(
        profile_id=profile.profile_id,
        mode=profile.mode,
        execute=True,
        evidence_policy_digest=profile.evidence_policy_digest,
    )


def assert_evidence_policy_unchanged(
    route: ExecutionRouteV1,
    expected_digest: str,
) -> None:
    if route.evidence_policy_digest != expected_digest:
        raise ValueError("execution profile cannot change the evidence/authorization policy")


def load_execution_profile(source: str | Path | Mapping[str, Any]) -> ExecutionProfileV1:
    """Load a profile from a JSON file or an already decoded mapping.

    The loader is deliberately small and side-effect free.  A profile is
    configuration, not evidence: loading it never changes a validator or
    authorization policy.  Callers that accept an environment variable can
    pass its resolved path here and still get the same typed contract used by
    the runtime.
    """

    if isinstance(source, Mapping):
        return ExecutionProfileV1.model_validate(dict(source))
    path = Path(source).expanduser().resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("execution profile JSON must be an object")
    return ExecutionProfileV1.model_validate(payload)


def execution_profile_from_env(
    env: Mapping[str, str] | None = None,
) -> ExecutionProfileV1 | None:
    """Resolve ``CODE2PAPER_EXECUTION_PROFILE`` when explicitly configured."""

    values = env if env is not None else os.environ
    raw = str(values.get("CODE2PAPER_EXECUTION_PROFILE", "") or "").strip()
    if not raw:
        return None
    return load_execution_profile(raw)


__all__ = [
    "ExecutionMode",
    "ExecutionProfileV1",
    "ExecutionRouteV1",
    "assert_evidence_policy_unchanged",
    "execution_profile_from_env",
    "load_execution_profile",
    "route_execution_profile",
]
