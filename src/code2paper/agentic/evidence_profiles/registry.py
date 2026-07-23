"""Deterministic registry and selection for Evidence Compiler profiles."""

from __future__ import annotations

from dataclasses import dataclass, field

from code2paper.agentic.evidence_profiles.base import (
    EvidenceCompilerProfile,
    ProfileMatch,
)
from code2paper.agentic.repo_snapshot import RepoSnapshot


@dataclass
class EvidenceProfileRegistry:
    profiles: list[EvidenceCompilerProfile] = field(default_factory=list)

    def register(self, profile: EvidenceCompilerProfile) -> None:
        if any(item.profile_id == profile.profile_id for item in self.profiles):
            raise ValueError(f"duplicate evidence profile id: {profile.profile_id}")
        self.profiles.append(profile)

    def select(
        self, repo_snapshot: RepoSnapshot
    ) -> tuple[EvidenceCompilerProfile | None, list[ProfileMatch]]:
        matches = [profile.match(repo_snapshot) for profile in self.profiles]
        selected = next(
            (
                profile
                for profile, match in zip(self.profiles, matches, strict=True)
                if match.matched
            ),
            None,
        )
        return selected, matches


def default_evidence_profile_registry() -> EvidenceProfileRegistry:
    from code2paper.agentic.evidence_profiles.dynamic_graph_mamba import (
        DynamicGraphMambaProfile,
    )
    from code2paper.agentic.evidence_profiles.ebcar_reranker import (
        EbcarRerankerProfile,
    )
    from code2paper.agentic.evidence_profiles.linear_graph_retrieval import (
        LinearGraphRetrievalProfile,
    )
    from code2paper.agentic.evidence_profiles.rap_pruning import RapPruningProfile

    return EvidenceProfileRegistry(
        profiles=[
            RapPruningProfile(),
            EbcarRerankerProfile(),
            DynamicGraphMambaProfile(),
            LinearGraphRetrievalProfile(),
        ]
    )


__all__ = ["EvidenceProfileRegistry", "default_evidence_profile_registry"]
