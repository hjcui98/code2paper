"""Terminology table helpers for method authoring."""

from __future__ import annotations

from code2paper.phase4_authoring import _terminology_scaffold
from code2paper.schemas import MethodEvidence, TerminologyTable


def build_terminology_table(method_evidence: MethodEvidence) -> TerminologyTable:
    return _terminology_scaffold(method_evidence)
