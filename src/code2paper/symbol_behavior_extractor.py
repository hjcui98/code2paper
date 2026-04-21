"""Generic code-behavior extraction for MethodEvidence enrichment.

The extractor is deliberately rule based and conservative. It does not decide
academic novelty; it only turns recurring implementation patterns into
evidence-backed method mechanisms that writers can use later.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .behavior_registry import BehaviorDetectionContext, default_behavior_registry
from .schemas import (
    ArchitectureParameter,
    CodeAlignmentIR,
    ConfidenceLevel,
    EquationCandidate,
    MethodBehaviorPattern,
    ModuleCategory,
    RawEvidencePack,
    SubMechanism,
    TensorRole,
)


@dataclass
class SymbolMechanismExtraction:
    behavior_patterns: list[MethodBehaviorPattern] = field(default_factory=list)
    equation_candidates: list[EquationCandidate] = field(default_factory=list)
    architecture_parameters: list[ArchitectureParameter] = field(default_factory=list)
    tensor_roles: list[TensorRole] = field(default_factory=list)
    submechanisms: list[SubMechanism] = field(default_factory=list)


def extract_symbol_mechanisms(raw_pack: RawEvidencePack, alignment: CodeAlignmentIR) -> SymbolMechanismExtraction:
    """Extract code-backed behavior patterns from method-core symbols."""

    project_root = Path(raw_pack.project_root)
    evidence_by_id = {item.evidence_id: item for item in raw_pack.evidence_items}
    behavior_patterns: list[MethodBehaviorPattern] = []
    equation_candidates: list[EquationCandidate] = []
    architecture_parameters: list[ArchitectureParameter] = []
    tensor_roles: list[TensorRole] = []
    submechanisms: list[SubMechanism] = []

    counters = {"BEH": 1, "EQ": 1, "PARAM": 1, "TENSOR": 1, "SUBMECH": 1}
    for role in alignment.module_roles:
        if role.category != ModuleCategory.METHOD_CORE or not role.symbol or not role.evidence_ids:
            continue
        source_path = project_root / role.path
        if not source_path.exists():
            continue
        try:
            text = source_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
        except SyntaxError:
            continue
        node = _find_symbol_node(tree, role.symbol)
        if node is None:
            continue
        evidence_ids = [evidence_id for evidence_id in role.evidence_ids if evidence_id in evidence_by_id]
        source_segment = ast.get_source_segment(text, node) or ""
        symbol_patterns, symbol_equations = _detect_behavior_patterns(
            path=role.path,
            symbol=role.symbol,
            source_segment=source_segment,
            evidence_ids=evidence_ids,
            counters=counters,
        )
        behavior_patterns.extend(symbol_patterns)
        equation_candidates.extend(symbol_equations)

        architecture_parameters.extend(
            _extract_architecture_parameters(
                path=role.path,
                symbol=role.symbol,
                node=node,
                evidence_ids=evidence_ids,
                counters=counters,
            )
        )
        tensor_roles.extend(
            _extract_tensor_roles(
                path=role.path,
                symbol=role.symbol,
                node=node,
                evidence_ids=evidence_ids,
                counters=counters,
            )
        )
        if symbol_patterns or symbol_equations:
            submechanisms.append(
                SubMechanism(
                    submechanism_id=_next_id("SUBMECH", counters),
                    description=_submechanism_description(role.symbol, symbol_patterns),
                    behavior_ids=[pattern.behavior_id for pattern in symbol_patterns],
                    equation_ids=[equation.equation_id for equation in symbol_equations],
                    parameter_ids=[],
                    tensor_ids=[],
                    evidence_ids=evidence_ids,
                    confidence=_combined_confidence([pattern.confidence for pattern in symbol_patterns]),
                )
            )

    submechanisms = _attach_parameter_and_tensor_ids(submechanisms, architecture_parameters, tensor_roles)
    return SymbolMechanismExtraction(
        behavior_patterns=_dedupe_by_id(behavior_patterns, "behavior_id"),
        equation_candidates=_dedupe_by_id(equation_candidates, "equation_id"),
        architecture_parameters=_dedupe_parameters(architecture_parameters),
        tensor_roles=_dedupe_tensor_roles(tensor_roles),
        submechanisms=submechanisms,
    )


def _find_symbol_node(tree: ast.Module, symbol: str) -> ast.ClassDef | ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == symbol:
            return node
    return None


def _detect_behavior_patterns(
    *,
    path: str,
    symbol: str,
    source_segment: str,
    evidence_ids: list[str],
    counters: dict[str, int],
) -> tuple[list[MethodBehaviorPattern], list[EquationCandidate]]:
    patterns: list[MethodBehaviorPattern] = []
    equations: list[EquationCandidate] = []
    context = BehaviorDetectionContext(
        path=path,
        symbol=symbol,
        source_segment=source_segment,
        evidence_ids=evidence_ids,
        language="python",
    )
    detection = default_behavior_registry().detect(context)
    for behavior in detection.behaviors:
        patterns.append(
            MethodBehaviorPattern(
                behavior_id=_next_id("BEH", counters),
                behavior_type=behavior.behavior_type,
                detected_pattern=behavior.detected_pattern,
                description=behavior.description,
                operations=behavior.operations,
                path=path,
                symbol=symbol,
                evidence_ids=evidence_ids,
                confidence=behavior.confidence,
            )
        )
    for equation in detection.equations:
        equations.append(
            EquationCandidate(
                equation_id=_next_id("EQ", counters),
                name=equation.name,
                latex=equation.latex,
                evidence_ids=evidence_ids,
                confidence=equation.confidence,
                caveats=equation.caveats,
            )
        )
    return patterns, equations


def _extract_architecture_parameters(
    *,
    path: str,
    symbol: str,
    node: ast.ClassDef | ast.FunctionDef,
    evidence_ids: list[str],
    counters: dict[str, int],
) -> list[ArchitectureParameter]:
    init_node = _find_init(node) if isinstance(node, ast.ClassDef) else node
    if init_node is None:
        return []
    args = init_node.args.args
    defaults = init_node.args.defaults
    if not defaults:
        return []
    default_start = len(args) - len(defaults)
    parameters: list[ArchitectureParameter] = []
    for arg, default_node in zip(args[default_start:], defaults):
        if arg.arg == "self":
            continue
        value = _literal(default_node)
        if value is None:
            continue
        if not isinstance(value, (int, float, str, bool)):
            continue
        parameters.append(
            ArchitectureParameter(
                parameter_id=_next_id("PARAM", counters),
                name=arg.arg,
                value=value,
                source="constructor_default",
                path=path,
                symbol=symbol,
                evidence_ids=evidence_ids,
                confidence=ConfidenceLevel.HIGH,
            )
        )
    return parameters


def _extract_tensor_roles(
    *,
    path: str,
    symbol: str,
    node: ast.ClassDef | ast.FunctionDef,
    evidence_ids: list[str],
    counters: dict[str, int],
) -> list[TensorRole]:
    forward_node = _find_method(node, "forward") if isinstance(node, ast.ClassDef) else node
    if forward_node is None:
        return []
    role_by_name = {
        "q": "query representation",
        "query": "query representation",
        "k": "key representation",
        "key": "key representation",
        "v": "value representation",
        "value": "value representation",
        "mask": "attention or validity mask",
        "src_seq": "source token sequence",
        "trg_seq": "target token sequence",
        "src_mask": "source padding mask",
        "trg_mask": "target autoregressive/padding mask",
        "enc_output": "encoder output representation",
        "dec_output": "decoder output representation",
        "x": "layer input representation",
    }
    roles: list[TensorRole] = []
    for arg in forward_node.args.args:
        if arg.arg == "self" or arg.arg not in role_by_name:
            continue
        roles.append(
            TensorRole(
                tensor_id=_next_id("TENSOR", counters),
                name=arg.arg,
                role=role_by_name[arg.arg],
                path=path,
                symbol=symbol,
                evidence_ids=evidence_ids,
                confidence=ConfidenceLevel.MEDIUM,
            )
        )
    return roles


def _find_init(node: ast.ClassDef) -> ast.FunctionDef | None:
    return _find_method(node, "__init__")


def _find_method(node: ast.ClassDef, name: str) -> ast.FunctionDef | None:
    for child in node.body:
        if isinstance(child, ast.FunctionDef) and child.name == name:
            return child
    return None


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _submechanism_description(symbol: str, patterns: list[MethodBehaviorPattern]) -> str:
    if not patterns:
        return f"{symbol} implements a code-backed method submechanism."
    generic_behaviors = _dedupe([pattern.behavior_type.replace("_", " ") for pattern in patterns])
    detected_patterns = _dedupe([pattern.detected_pattern.replace("_", " ") for pattern in patterns if pattern.detected_pattern])
    description = f"{symbol} exposes generic code behaviors: " + ", ".join(generic_behaviors) + "."
    if detected_patterns:
        description += " Detected implementation patterns include " + ", ".join(detected_patterns) + "."
    return description


def _attach_parameter_and_tensor_ids(
    submechanisms: list[SubMechanism],
    parameters: list[ArchitectureParameter],
    tensor_roles: list[TensorRole],
) -> list[SubMechanism]:
    params_by_evidence = _ids_by_evidence(parameters, "parameter_id")
    tensors_by_evidence = _ids_by_evidence(tensor_roles, "tensor_id")
    for submechanism in submechanisms:
        parameter_ids: list[str] = []
        tensor_ids: list[str] = []
        for evidence_id in submechanism.evidence_ids:
            parameter_ids.extend(params_by_evidence.get(evidence_id, []))
            tensor_ids.extend(tensors_by_evidence.get(evidence_id, []))
        submechanism.parameter_ids = _dedupe(parameter_ids)
        submechanism.tensor_ids = _dedupe(tensor_ids)
    return submechanisms


def _ids_by_evidence(items: list[Any], id_field: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in items:
        item_id = getattr(item, id_field)
        for evidence_id in item.evidence_ids:
            result.setdefault(evidence_id, []).append(item_id)
    return result


def _combined_confidence(confidences: list[ConfidenceLevel]) -> ConfidenceLevel:
    if not confidences:
        return ConfidenceLevel.MEDIUM
    if any(confidence == ConfidenceLevel.HIGH for confidence in confidences):
        return ConfidenceLevel.HIGH
    if any(confidence == ConfidenceLevel.MEDIUM for confidence in confidences):
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def _next_id(prefix: str, counters: dict[str, int]) -> str:
    value = counters[prefix]
    counters[prefix] += 1
    return f"{prefix}{value}"


def _tokens(text: str) -> list[str]:
    return text.replace(".", " ").replace("(", " ").replace(")", " ").replace("=", " ").split()


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_by_id(items: list[Any], field: str) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for item in items:
        value = getattr(item, field)
        if value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


def _dedupe_parameters(parameters: list[ArchitectureParameter]) -> list[ArchitectureParameter]:
    seen: set[tuple[str, str, str, object]] = set()
    result: list[ArchitectureParameter] = []
    for parameter in parameters:
        key = (parameter.path, parameter.symbol, parameter.name, parameter.value)
        if key in seen:
            continue
        seen.add(key)
        result.append(parameter)
    return result


def _dedupe_tensor_roles(tensor_roles: list[TensorRole]) -> list[TensorRole]:
    seen: set[tuple[str, str, str]] = set()
    result: list[TensorRole] = []
    for tensor_role in tensor_roles:
        key = (tensor_role.path, tensor_role.symbol, tensor_role.name)
        if key in seen:
            continue
        seen.add(key)
        result.append(tensor_role)
    return result
