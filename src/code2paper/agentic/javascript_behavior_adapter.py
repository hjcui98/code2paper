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
    ReferenceSiteV1,
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
            call_target, call_diagnostic = _call_info(stripped)
            for predicate, operands in _operations_for_line(stripped):
                sequence += 1
                span = make_span_id(symbol.path, offset, offset)
                diagnostics = ["syntax_light_adapter"]
                if call_target and predicate in _CALL_DERIVED_PREDICATES:
                    diagnostics.append(call_diagnostic or f"name:{call_target}")
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
                    diagnostics=tuple(diagnostics),
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
        """Find conservative import/usage sites across JS/TS files.

        This adapter is intentionally syntax-light, so it does not pretend to
        resolve aliases or scope exactly.  It records a site only when the
        target's short name is present on a non-comment line and marks import,
        attribute, or ordinary usage based on stable lexical patterns.  The
        definition line is removed to avoid turning the declaration into a
        self-reference.
        """

        target_name = symbol.qualified_name.split(".")[-1]
        target_re = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(target_name)}(?![A-Za-z0-9_$])")
        sites: list[ReferenceSiteV1] = []
        for path, text in sorted(files.items()):
            if not path.endswith((".js", ".jsx", ".ts", ".tsx")):
                continue
            for line_number, raw_line in enumerate(text.splitlines(), start=1):
                line = raw_line.strip()
                if not line or line.startswith(("//", "/*", "*", "*/")):
                    continue
                if path == symbol.path and line_number == symbol.start_line:
                    continue
                if not target_re.search(raw_line):
                    continue
                if _is_symbol_definition_line(line, target_name):
                    continue
                kind = "usage"
                if _is_import_reference(line, target_name):
                    kind = "import"
                elif re.search(rf"\.\s*{re.escape(target_name)}\b", raw_line):
                    kind = "attribute"
                sites.append(
                    ReferenceSiteV1(
                        path=path,
                        line=line_number,
                        kind=kind,
                        span_id=make_span_id(path, line_number, line_number),
                        source_authority=classify_source_authority(path),
                        snippet=line[:240],
                    )
                )
        seen: set[tuple[str, int, str]] = set()
        unique_sites: list[ReferenceSiteV1] = []
        for site in sites:
            key = (site.path, site.line, site.kind)
            if key not in seen:
                seen.add(key)
                unique_sites.append(site)
        unresolved = () if unique_sites else ("no_static_references_found",)
        return ReferenceSetV1(
            symbol_id=symbol.symbol_id,
            qualified_name=symbol.qualified_name,
            sites=tuple(unique_sites),
            unresolved=unresolved,
        )


def _operations_for_line(line: str) -> list[tuple[str, list[str]]]:
    lower = line.lower()
    operations: list[tuple[str, list[str]]] = []
    call_target, _ = _call_info(line)
    call_operand = call_target or line
    if re.search(r"\b(if|else|switch|case)\b", lower):
        operations.append(("BRANCH", [line]))
    if re.search(r"\b(for|while)\b", lower):
        operations.append(("LOOP", [line]))
    for token, predicate in (
        (".map(", "TRANSFORM"), (".filter(", "FILTER"), (".reduce(", "REDUCE"),
        (".sort(", "SORT"), (".slice(", "SELECT"), (".reshape(", "RESHAPE"),
        (".softmax(", "NORMALIZE"), (".concat(", "CONCAT"), (".join(", "CONCAT"),
    ):
        if token in lower:
            operations.append((predicate, [call_operand]))
    # Keep a generic CALL node for repository helpers and dynamic expressions.
    # Specialized operations above remain the semantic fact anchor, but they
    # are marked call-derived in ``extract_operations`` so the graph builder
    # can still emit CALLS / unresolved relations for them.
    has_specialized_call = any(predicate in _SPECIALIZED_CALL_PREDICATES for predicate, _ in operations)
    if call_target and not has_specialized_call:
        operations.append(("CALL", [call_operand]))
    if "return" in lower:
        operations.append(("RETURN", [call_operand if call_target else line]))
    if not operations and call_target and re.search(r"\b[A-Za-z_$][\w$]*\s*\([^)]*\)", line):
        operations.append(("CALL", [call_operand]))
    if re.search(r"(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=", line):
        operations.append(("WRITE", [line]))
    if not operations and re.search(r"\b[A-Za-z_$][\w$]*\b", line):
        operations.append(("READ", [line]))
    deduplicated: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for predicate, operands in operations:
        if predicate in seen:
            continue
        seen.add(predicate)
        deduplicated.append((predicate, operands))
    return deduplicated


_CALL_DERIVED_PREDICATES = frozenset({
    "CALL", "TRANSFORM", "FILTER", "REDUCE", "SORT", "SELECT", "RESHAPE",
    "NORMALIZE", "CONCAT",
})
_SPECIALIZED_CALL_PREDICATES = frozenset(_CALL_DERIVED_PREDICATES - {"CALL"})
_CALL_KEYWORDS = frozenset({"if", "for", "while", "switch", "catch", "with"})
_DYNAMIC_CALL_RE = re.compile(r"(?:\)\s*|\]\s*)\(\s*|\?\.\s*\(")
_CALL_TARGET_RE = re.compile(
    r"(?<![A-Za-z0-9_$])"
    r"([A-Za-z_$][\w$]*(?:\s*\.\s*[A-Za-z_$][\w$]*)*)"
    r"\s*\("
)


def _call_info(line: str) -> tuple[str | None, str | None]:
    """Return ``(target_hint, diagnostic)`` for the first lexical call.

    A returned callable (``factory()(value)``) or optional callable is not
    statically attributable to a symbol.  It is therefore represented by the
    full line and ``unknown_func`` so the generic graph builder records an
    unresolved dynamic relation instead of guessing.
    """

    if _is_symbol_definition_line(line):
        return None, None
    if _DYNAMIC_CALL_RE.search(line):
        return line, "unknown_func"
    for match in _CALL_TARGET_RE.finditer(line):
        target = re.sub(r"\s+", "", match.group(1))
        if target.split(".")[-1] in _CALL_KEYWORDS:
            continue
        return target, f"name:{target}"
    return None, None


def _is_symbol_definition_line(line: str, target_name: str = "") -> bool:
    definition = re.match(
        r"^(?:(?:export|default|async)\s+)*(?:function|class)\s+([A-Za-z_$][\w$]*)\b",
        line,
    )
    if definition is not None:
        return not target_name or definition.group(1) == target_name
    if re.match(r"^(?:export\s+)?(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=.*=>", line):
        return not target_name or bool(re.search(rf"\b{re.escape(target_name)}\b", line))
    return False


def _is_import_reference(line: str, target_name: str) -> bool:
    if re.match(r"^import\b", line):
        return True
    return bool(
        re.search(r"\brequire\s*\(", line)
        and re.search(rf"\b{re.escape(target_name)}\b", line)
    )


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
