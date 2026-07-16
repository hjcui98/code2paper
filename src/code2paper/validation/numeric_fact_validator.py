"""Numeric fact validation for Phase 4 drafts."""

from __future__ import annotations

from code2paper.core.schemas import CodeAlignmentIR, ConfigValueReport, MethodEvidence
from code2paper.validation.config_value_validator import validate_config_values


def validate_numeric_facts(
    *,
    method_evidence: MethodEvidence,
    draft_markdown: str,
    alignment: CodeAlignmentIR | None = None,
) -> ConfigValueReport:
    """Validate numeric/config facts against architecture parameters and config flow.

    When an alignment IR is available, this is equivalent to the config value
    validator over architecture parameters plus config resolutions. Without an
    alignment IR, the function still checks architecture parameters from Method
    Evidence by using an empty compatibility alignment.
    """

    effective_alignment = alignment or CodeAlignmentIR(project_id=method_evidence.project_id)
    return validate_config_values(
        alignment=effective_alignment,
        method_evidence=method_evidence,
        draft_markdown=draft_markdown,
    )
