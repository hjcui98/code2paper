"""Shared formula content gate for Section and Mechanism validators."""

from __future__ import annotations

import re
from typing import Any


_FORMULA_CODE_TRACE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("operation_opcode", re.compile(
        r"\b(?:LOAD|WRITE|RESHAPE|CALL|READ|COMPARE|RETURN|CONSTRUCT|SELECT|"
        r"FILTER|SORT|REDUCE|CONCAT|NORMALIZE)\s*\(",
    )),
    ("python_qualified_name", re.compile(
        r"\b(?:self|torch|numpy|np|tensorflow|tf|nn)\s*\.",
        flags=re.IGNORECASE,
    )),
    ("python_shape_index", re.compile(
        r"\b(?:shape|size|len)\s*\[",
        flags=re.IGNORECASE,
    )),
    ("python_function_name", re.compile(
        r"\b[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]*\s*\(",
    )),
    ("python_keyword_arg", re.compile(
        r"\b(?:dim|descending|keepdim|axis|dtype|device)\s*=",
        flags=re.IGNORECASE,
    )),
    ("python_tuple_assignment", re.compile(
        r"\([^()\n]{1,80}\)\s*=",
    )),
    ("raw_snake_case_identifier", re.compile(
        r"\b[a-z]+(?:_[a-z0-9]+){2,}\b",
    )),
    ("default_none", re.compile(r"\bNone\b")),
    ("list_initialization", re.compile(r"\[\s*\]|\blist\s*\(")),
)


def formula_surface_text(package: Any) -> str:
    if isinstance(package, str):
        return package
    parts = (
        getattr(package, "latex", "") or "",
        getattr(package, "markdown_block", "") or "",
        getattr(package, "prose_explanation", "") or "",
    )
    if not any(str(item).strip() for item in parts) and isinstance(package, dict):
        parts = (
            package.get("latex", "") or "",
            package.get("markdown_block", "") or "",
            package.get("prose_explanation", "") or "",
        )
    return " ".join(str(item) for item in parts)


def formula_code_trace_failures(package: Any) -> list[str]:
    """Detect implementation syntax that should not be a paper formula."""

    surface = formula_surface_text(package)
    return [
        f"code_shaped_formula:{name}"
        for name, pattern in _FORMULA_CODE_TRACE_PATTERNS
        if pattern.search(surface)
    ]


def formula_symbol_definition_failures(package: Any) -> list[str]:
    definitions = (
        getattr(package, "symbol_definitions", ()) or ()
        if not isinstance(package, dict)
        else package.get("symbol_definitions", ()) or ()
    )
    failures: list[str] = []
    latex = str(
        getattr(package, "latex", "")
        if not isinstance(package, dict)
        else package.get("latex", "")
        or ""
    )
    visible: list[str] = []
    for item in definitions:
        if isinstance(item, (tuple, list)) and item:
            symbol = str(item[0] or "").strip()
        else:
            symbol = str(getattr(item, "symbol", "") or "").strip()
        if symbol:
            visible.append(symbol)
    if latex.strip() and not visible:
        failures.append("formula_symbol_definitions_missing")
    return failures


def shared_formula_content_failures(package: Any) -> list[str]:
    """Union of representation-independent content bans."""

    return [
        *formula_code_trace_failures(package),
        *formula_symbol_definition_failures(package),
    ]
