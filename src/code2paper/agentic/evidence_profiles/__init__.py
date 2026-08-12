"""Structure-matched, non-authoritative discovery profiles.

Profiles may improve search direction and organization.  They do not grant
fact or claim authority; the generic research data plane owns compilation.
"""

from code2paper.agentic.evidence_profiles.base import (
    EvidenceDiscoveryProfile,
    EvidenceCompilerProfile,
    ProfileMatch,
)
from code2paper.agentic.evidence_profiles.registry import (
    DiscoveryProfileView,
    EvidenceProfileRegistry,
)

__all__ = [
    "EvidenceCompilerProfile",
    "EvidenceDiscoveryProfile",
    "EvidenceProfileRegistry",
    "DiscoveryProfileView",
    "ProfileMatch",
]
