"""Structure-matched Evidence Compiler profiles.

Profiles may improve structural recall and semantic grouping, but their
outputs still pass the common V3 validators before authoring.
"""

from code2paper.agentic.evidence_profiles.base import (
    EvidenceCompilerProfile,
    ProfileMatch,
)
from code2paper.agentic.evidence_profiles.registry import EvidenceProfileRegistry

__all__ = ["EvidenceCompilerProfile", "EvidenceProfileRegistry", "ProfileMatch"]
