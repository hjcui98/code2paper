"""Module role alignment facade."""

from __future__ import annotations

from code2paper.analysis.alignment import _align_module_roles
from code2paper.core.schemas import AlignedModuleRole, EvidenceItem


def align_module_roles(evidence: list[EvidenceItem]) -> list[AlignedModuleRole]:
    return _align_module_roles(evidence)

