"""Contracts shared by project-agnostic structure profiles."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

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
class EvidenceCompilerProfile(Protocol):
    """A structure-triggered compiler profile with no project-name trigger."""

    profile_id: str

    def match(self, repo_snapshot: RepoSnapshot) -> ProfileMatch: ...

    def compile(self, repo_snapshot: RepoSnapshot) -> Any | None: ...

