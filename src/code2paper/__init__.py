"""Code-to-paper agent package."""

from .schemas import (
    AuthorMarkers,
    CodeAlignmentIR,
    MethodEvidence,
    RawEvidencePack,
)
from .ingestion import ingest_project
from .alignment import align_code, align_from_files
from .claim_grounder import build_claim_evidence_map, build_claim_evidence_map_from_files
from .method_evidence import build_method_evidence, build_method_evidence_from_files

__all__ = [
    "align_code",
    "align_from_files",
    "AuthorMarkers",
    "CodeAlignmentIR",
    "MethodEvidence",
    "RawEvidencePack",
    "build_claim_evidence_map",
    "build_claim_evidence_map_from_files",
    "build_method_evidence",
    "build_method_evidence_from_files",
    "ingest_project",
]
