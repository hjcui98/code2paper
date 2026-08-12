"""Contracts shared by project-agnostic structure profiles."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.repo_snapshot import RepoSnapshot


class ProfileMatch(BaseModel):
    """Auditable structural-fingerprint match result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    matched: bool
    required_fingerprints: list[str] = Field(default_factory=list)
    optional_fingerprints: list[str] = Field(default_factory=list)
    matched_fingerprints: list[str] = Field(default_factory=list)
    missing_required_fingerprints: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


@runtime_checkable
class EvidenceDiscoveryProfile(Protocol):
    """A non-authoritative structural discovery profile.

    Profiles may select search direction.  They intentionally expose no
    public ``compile`` method, so facts and claims can only be authorized by
    the generic research data plane after snapshot-bound reads.  Archived
    implementations may retain a private ``_compile_legacy`` hook for the
    explicit migration-diagnostics route only.
    """

    profile_id: str

    def match(self, repo_snapshot: RepoSnapshot) -> ProfileMatch: ...


# Compatibility name for callers that only depend on structural matching.
# The protocol no longer grants compilation authority.
EvidenceCompilerProfile = EvidenceDiscoveryProfile
