"""Deterministic registry and selection for Evidence Compiler profiles."""

from __future__ import annotations

from dataclasses import dataclass, field

from code2paper.agentic.evidence_profiles.base import (
    EvidenceDiscoveryProfile,
    ProfileMatch,
)
from code2paper.agentic.repo_snapshot import RepoSnapshot


@dataclass(frozen=True)
class DiscoveryProfileView:
    """Production-safe view of a structure profile.

    The repository still carries archived profile implementations so old
    fixtures can be inspected, but the object exposed by the normal registry
    selection route intentionally has no ``compile`` attribute.  This keeps a
    fingerprint match a discovery hint rather than an authority-bearing
    packet/fact/claim compiler.  The explicit diagnostics-only route uses
    :meth:`EvidenceProfileRegistry.select_legacy` when migration fixtures need
    to be examined.
    """

    _profile: EvidenceDiscoveryProfile

    @property
    def profile_id(self) -> str:
        return self._profile.profile_id

    def match(self, repo_snapshot: RepoSnapshot) -> ProfileMatch:
        return self._profile.match(repo_snapshot)


@dataclass
class EvidenceProfileRegistry:
    # The public registry contains only discovery views.  Archived raw
    # implementations live in a private list used solely by the explicit
    # diagnostics selector below.
    profiles: list[DiscoveryProfileView] = field(default_factory=list)
    _legacy_profiles: list[EvidenceDiscoveryProfile] = field(
        default_factory=list, repr=False
    )

    def register(self, profile: EvidenceDiscoveryProfile) -> None:
        if any(item.profile_id == profile.profile_id for item in self.profiles):
            raise ValueError(f"duplicate evidence profile id: {profile.profile_id}")
        self.profiles.append(DiscoveryProfileView(profile))
        self._legacy_profiles.append(profile)

    def select(
        self, repo_snapshot: RepoSnapshot
    ) -> tuple[DiscoveryProfileView | None, list[ProfileMatch]]:
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

    def select_legacy(
        self, repo_snapshot: RepoSnapshot
    ) -> tuple[EvidenceDiscoveryProfile | None, list[ProfileMatch]]:
        """Select the archived implementation for diagnostics-only callers.

        Keeping this route explicit prevents an ordinary ``select`` call from
        accidentally acquiring profile compilation authority.
        """

        matches = [profile.match(repo_snapshot) for profile in self.profiles]
        selected = next(
            (
                profile
                for profile, match in zip(self._legacy_profiles, matches, strict=True)
                if match.matched
            ),
            None,
        )
        return selected, matches


def default_evidence_profile_registry() -> EvidenceProfileRegistry:
    from code2paper.agentic.evidence_profiles.bootstrapping_multiview import (
        BootstrappingMultiViewProfile,
    )
    from code2paper.agentic.evidence_profiles.dynamic_graph_mamba import (
        DynamicGraphMambaProfile,
    )
    from code2paper.agentic.evidence_profiles.ebcar_reranker import (
        EbcarRerankerProfile,
    )
    from code2paper.agentic.evidence_profiles.linear_graph_retrieval import (
        LinearGraphRetrievalProfile,
    )
    from code2paper.agentic.evidence_profiles.lookahead_reasoning import (
        LookaheadReasoningProfile,
    )
    from code2paper.agentic.evidence_profiles.rap_pruning import RapPruningProfile

    registry = EvidenceProfileRegistry()
    for profile in (
        RapPruningProfile(),
        EbcarRerankerProfile(),
        DynamicGraphMambaProfile(),
        LinearGraphRetrievalProfile(),
        LookaheadReasoningProfile(),
        BootstrappingMultiViewProfile(),
    ):
        registry.register(profile)
    return registry


__all__ = [
    "DiscoveryProfileView",
    "EvidenceProfileRegistry",
    "default_evidence_profile_registry",
]
