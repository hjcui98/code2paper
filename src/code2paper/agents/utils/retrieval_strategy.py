from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from code2paper.agents.utils.code_scan import read_file_lines


METHOD_MODULE_SUFFIXES = ("Agent", "Processor", "Model", "Module")


def derive_orchestrator_symbol_targets(
    file_index: List[Dict[str, Any]],
    priority_paths: List[str],
) -> List[Dict[str, Any]]:
    indexed_by_suffix = _indexed_python_files(file_index)
    targets: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str]] = set()

    for orchestrator in _orchestrator_files(file_index, priority_paths):
        path = str(orchestrator.get("path") or "").strip()
        lines = read_file_lines(path)
        if not lines:
            continue
        try:
            tree = ast.parse("\n".join(lines))
        except SyntaxError:
            continue

        used_call_names = _called_symbol_names(tree)
        for module_name, symbol_name in _imported_method_symbols(tree):
            if symbol_name not in used_call_names:
                continue
            target_path = _path_for_module(module_name, indexed_by_suffix)
            if not target_path:
                continue
            key = (target_path, symbol_name)
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                {
                    "path": target_path,
                    "symbol": symbol_name,
                    "role": "method_agent",
                    "source": "orchestrator_import",
                    "reason": f"{Path(path).name} imports and instantiates {symbol_name}",
                }
            )

    return targets[:80]


def _indexed_python_files(file_index: List[Dict[str, Any]]) -> Dict[str, str]:
    indexed: Dict[str, str] = {}
    for file_info in file_index:
        if not isinstance(file_info, dict):
            continue
        path = str(file_info.get("path") or "").strip()
        language = str(file_info.get("language") or "").lower()
        if not path or language != "python":
            continue
        normalized = path.replace("\\", "/").strip("/")
        indexed[normalized] = path
    return indexed


def _orchestrator_files(file_index: List[Dict[str, Any]], priority_paths: List[str]) -> List[Dict[str, Any]]:
    priority_matches: List[Dict[str, Any]] = []
    entrypoint_matches: List[Dict[str, Any]] = []
    for file_info in file_index:
        if not isinstance(file_info, dict):
            continue
        path = str(file_info.get("path") or "").strip()
        language = str(file_info.get("language") or "").lower()
        if not path or language != "python":
            continue
        if any(_path_matches_hint(path, hint) for hint in priority_paths):
            priority_matches.append(file_info)
            continue
        if Path(path).name.lower() in {"main.py", "run.py", "train.py", "pipeline.py"}:
            entrypoint_matches.append(file_info)
    return _dedupe_files(priority_matches + entrypoint_matches)


def _imported_method_symbols(tree: ast.AST) -> List[Tuple[str, str]]:
    imported: List[Tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        for alias in node.names:
            symbol = alias.name
            if _looks_like_method_module(symbol):
                imported.append((node.module, alias.asname or symbol))
    return imported


def _called_symbol_names(tree: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _path_for_module(module_name: str, indexed_by_suffix: Dict[str, str]) -> str:
    suffix = module_name.replace(".", "/").strip("/") + ".py"
    for normalized_path, original_path in indexed_by_suffix.items():
        if normalized_path.endswith("/" + suffix) or normalized_path == suffix:
            return original_path
    return ""


def _looks_like_method_module(symbol: str) -> bool:
    return symbol[:1].isupper() and symbol.endswith(METHOD_MODULE_SUFFIXES)


def _path_matches_hint(path: str, hint: str) -> bool:
    normalized_path = path.replace("\\", "/").strip("/")
    normalized_hint = str(hint or "").replace("\\", "/").strip("/")
    return bool(normalized_hint) and (
        normalized_path == normalized_hint
        or normalized_path.endswith("/" + normalized_hint)
        or normalized_hint.endswith("/" + normalized_path)
    )


def _dedupe_files(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for file_info in files:
        path = str(file_info.get("path") or "") if isinstance(file_info, dict) else ""
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(file_info)
    return out
