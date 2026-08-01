"""Conservative JavaScript/TypeScript behavior adapter.

This is intentionally syntax-light.  It recognizes stable function/class
boundaries and a small set of executable operations, while leaving dynamic
resolution unresolved.  It is a second adapter for registry/rollout tests;
it does not grant language-specific authority to the generic compiler.
"""

from __future__ import annotations

import re
from typing import Any

from code2paper.agentic.behavior_graph import (
    BehaviorNodeV1,
    BehaviorRelationV1,
    ReferenceSetV1,
    SymbolIndexV2,
    SymbolRefV1,
    UnresolvedRelationV1,
    make_span_id,
    make_symbol_id,
)
from code2paper.agentic.source_authority import classify_source_authority


_SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*|"
    r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\s*|"
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^\n]*\)\s*=>",
    flags=re.MULTILINE,
)


class JavaScriptBehaviorAdapter:
    language = "javascript"

    def index_symbols(
        self,
        *,
        repo_snapshot_id: str,
        project_tree_hash: str,
        files: dict[str, str],
    ) -> SymbolIndexV2:
        symbols: list[SymbolRefV1] = []
        for path, source in sorted(files.items()):
            if not path.endswith((".js", ".jsx", ".ts", ".tsx")):
                continue
            lines = source.splitlines()
            for match in _SYMBOL_RE.finditer(source):
                name = next((value for value in match.groups() if value), "")
                if not name:
                    continue
                line = source.count("\n", 0, match.start()) + 1
                end_line = _balanced_end_line(lines, line - 1)
                kind = "class" if match.group(2) else "function"
                symbols.append(SymbolRefV1(
                    symbol_id=make_symbol_id(path, name, line),
                    path=path,
                    qualified_name=name,
                    kind=kind,
                    start_line=line,
                    end_line=end_line,
                    text_hash=_text_hash("\n".join(lines[line - 1:end_line])),
                ))
        symbols.sort(key=lambda item: (item.path, item.start_line, item.qualified_name))
        return SymbolIndexV2(
            repo_snapshot_id=repo_snapshot_id,
            project_tree_hash=project_tree_hash,
            language=self.language,
            indexed_files=sum(1 for path in files if path.endswith((".js", ".jsx", ".ts", ".tsx"))),
            indexed_symbols=len(symbols),
            symbols=symbols,
        )

    def extract_operations(
        self,
        symbol: SymbolRefV1,
        source_text: str,
        child_method_symbols: dict[int, SymbolRefV1] | None = None,
    ) -> list[BehaviorNodeV1]:
        lines = source_text.splitlines()
        body = lines[max(0, symbol.start_line - 1): min(len(lines), symbol.end_line)]
        nodes: list[BehaviorNodeV1] = []
        sequence = 0
        for offset, line in enumerate(body, start=symbol.start_line):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            operation = _operation_for_line(stripped)
            if operation is None:
                continue
            predicate, operands = operation
            sequence += 1
            span = make_span_id(symbol.path, offset, offset)
            nodes.append(BehaviorNodeV1(
                node_id=BehaviorNodeV1.make_node_id(
                    symbol_id=symbol.symbol_id,
                    source_span_id=span,
                    predicate=predicate,
                    seq=sequence,
                ),
                symbol_id=symbol.symbol_id,
                operation_id=f"{predicate.lower()}:{sequence}",
                predicate=predicate,
                operands=tuple(operands),
                result=_assignment_target(stripped),
                guard=stripped if predicate == "BRANCH" else "",
                source_span_id=span,
                source_authority=classify_source_authority(symbol.path),
                diagnostics=("syntax_light_adapter",),
            ))
        return nodes

    def extract_relations(
        self,
        symbol: SymbolRefV1,
        source_text: str,
        nodes: list[BehaviorNodeV1],
    ) -> list[BehaviorRelationV1]:
        relations: list[BehaviorRelationV1] = []
        for index, (left, right) in enumerate(zip(nodes, nodes[1:]), start=1):
            relations.append(BehaviorRelationV1(
                relation_id=BehaviorRelationV1.make_relation_id(
                    kind="NEXT_CONTROL", source_node_id=left.node_id, target_node_id=right.node_id, seq=index
                ),
                kind="NEXT_CONTROL",
                source_node_id=left.node_id,
                target_node_id=right.node_id,
                source_symbol_id=symbol.symbol_id,
                target_symbol_id=symbol.symbol_id,
                source_span_id=left.source_span_id,
                target_span_id=right.source_span_id,
            ))
        return relations

    def resolve_references(
        self,
        symbol: SymbolRefV1,
        index: SymbolIndexV2,
        files: dict[str, str],
    ) -> ReferenceSetV1:
        return ReferenceSetV1(symbol_id=symbol.symbol_id, qualified_name=symbol.qualified_name)


def _operation_for_line(line: str) -> tuple[str, list[str]] | None:
    lower = line.lower()
    if re.search(r"\b(if|else|switch|case)\b", lower):
        return "BRANCH", [line]
    if re.search(r"\b(for|while)\b", lower):
        return "LOOP", [line]
    if "return" in lower:
        return "RETURN", [line]
    for token, predicate in (
        (".map(", "TRANSFORM"), (".filter(", "FILTER"), (".reduce(", "REDUCE"),
        (".sort(", "SORT"), (".slice(", "SELECT"), (".reshape(", "RESHAPE"),
        (".softmax(", "NORMALIZE"), (".concat(", "CONCAT"), (".join(", "CONCAT"),
    ):
        if token in lower:
            return predicate, [line]
    if re.search(r"\b[A-Za-z_$][\w$]*\s*\([^)]*\)", line):
        return "CALL", [line]
    if re.search(r"(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=", line):
        return "WRITE", [line]
    if re.search(r"\b[A-Za-z_$][\w$]*\b", line):
        return "READ", [line]
    return None


def _assignment_target(line: str) -> str:
    match = re.search(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=", line)
    return match.group(1) if match else ""


def _balanced_end_line(lines: list[str], start_index: int) -> int:
    depth = 0
    started = False
    for index in range(start_index, len(lines)):
        depth += lines[index].count("{") - lines[index].count("}")
        started = started or "{" in lines[index]
        if started and depth <= 0:
            return index + 1
    return min(len(lines), start_index + 1)


def _text_hash(text: str) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = ["JavaScriptBehaviorAdapter"]
