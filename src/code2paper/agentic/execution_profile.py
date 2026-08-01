"""Shadow/opt-in/canary/rollback routing without changing evidence gates."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

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
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
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
) -> ExecutionRouteV1:
    """Resolve deployment routing while preserving one policy digest."""

    if rollback or profile.mode == "rollback":
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


__all__ = [
    "ExecutionMode",
    "ExecutionProfileV1",
    "ExecutionRouteV1",
    "assert_evidence_policy_unchanged",
    "route_execution_profile",
]
