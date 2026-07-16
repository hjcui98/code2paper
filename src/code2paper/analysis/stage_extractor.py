"""Execution/method stage extraction facade."""

from __future__ import annotations

from code2paper.analysis.alignment import _extract_execution_stages, _extract_method_stages, _map_stages
from code2paper.core.schemas import EvidenceItem, ExecutionStage, MethodStageAlignment, StageMapping


def extract_execution_stages(evidence: list[EvidenceItem]) -> list[ExecutionStage]:
    return _extract_execution_stages(evidence)


def extract_method_stages(evidence: list[EvidenceItem]) -> list[MethodStageAlignment]:
    return _extract_method_stages(evidence)


def map_execution_to_method_stages(
    execution_stages: list[ExecutionStage],
    method_stages: list[MethodStageAlignment],
) -> list[StageMapping]:
    return _map_stages(execution_stages, method_stages)

