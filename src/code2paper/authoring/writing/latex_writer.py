"""LaTeX writing adapter."""

from __future__ import annotations

from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence
from code2paper.authoring.writing.method_writer import build_method_draft_tex


def write_method_latex(
    *,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap | None = None,
) -> str:
    return build_method_draft_tex(method_evidence, claim_map)
