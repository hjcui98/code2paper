"""Typed reference builders and parsers for the V3 evidence chain.

Phase 3 unifies all tool-produced references into a single typed
namespace so the observation pipeline, behavior graph updater,
evidence critic and authoring projection can consume them
uniformly.  Each reference is a string of the form
``<type>:<body>`` where ``<type>`` is one of:

- ``symbol``  — a symbol in the repo snapshot (``symbol:<path>:<name>:<line>``)
- ``span``    — a source code span (``span:<path>:<start>:<end>``)
- ``behavior``— a behavior graph node (``behavior:<node_id>``)
- ``packet``  — an evidence packet (``packet:<status>:<id>``)
- ``fact``    — a code fact (``fact:<status>:<id>``)
- ``claim``   — an atomic claim (``claim:<status>:<id>``)
- ``ref``     — a generic find-references hit (``ref:<path>:<line>``)
- ``entrypoint`` — a discovered entrypoint (``entrypoint:<path>``)

The builders validate their inputs and produce canonical strings.
The parser splits a reference into ``(type, body)`` and provides
convenience accessors for each type.

This module does NOT change the wire format of existing references —
it only provides a single source of truth for building and parsing
them so downstream consumers (observation_ingest_node,
behavior_graph_updater_node, evidence_critic_node) can handle every
reference type uniformly.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Reference type prefixes
# ---------------------------------------------------------------------------

SYMBOL_REF = "symbol"
SPAN_REF = "span"
BEHAVIOR_REF = "behavior"
PACKET_REF = "packet"
FACT_REF = "fact"
CLAIM_REF = "claim"
GENERIC_REF = "ref"
ENTRYPOINT_REF = "entrypoint"

ALL_REF_TYPES: frozenset[str] = frozenset({
    SYMBOL_REF,
    SPAN_REF,
    BEHAVIOR_REF,
    PACKET_REF,
    FACT_REF,
    CLAIM_REF,
    GENERIC_REF,
    ENTRYPOINT_REF,
})


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_symbol_ref(path: str, symbol: str, start_line: int) -> str:
    """Build a ``symbol:<path>:<name>:<line>`` reference."""

    if not path:
        raise ValueError("symbol ref requires a non-empty path")
    if not symbol:
        raise ValueError("symbol ref requires a non-empty symbol name")
    if start_line < 1:
        raise ValueError("symbol ref requires start_line >= 1")
    return f"{SYMBOL_REF}:{path}:{symbol}:{start_line}"


def build_span_ref(path: str, start_line: int, end_line: int) -> str:
    """Build a ``span:<path>:<start>:<end>`` reference."""

    if not path:
        raise ValueError("span ref requires a non-empty path")
    if start_line < 1:
        raise ValueError("span ref requires start_line >= 1")
    if end_line < start_line:
        raise ValueError("span ref requires end_line >= start_line")
    return f"{SPAN_REF}:{path}:{start_line}:{end_line}"


def build_behavior_ref(node_id: str) -> str:
    """Build a ``behavior:<node_id>`` reference."""

    if not node_id:
        raise ValueError("behavior ref requires a non-empty node_id")
    return f"{BEHAVIOR_REF}:{node_id}"


def build_packet_ref(status: str, packet_id: str) -> str:
    """Build a ``packet:<status>:<id>`` reference."""

    if not status:
        raise ValueError("packet ref requires a non-empty status")
    if not packet_id:
        raise ValueError("packet ref requires a non-empty packet_id")
    return f"{PACKET_REF}:{status}:{packet_id}"


def build_fact_ref(status: str, fact_id: str) -> str:
    """Build a ``fact:<status>:<id>`` reference."""

    if not status:
        raise ValueError("fact ref requires a non-empty status")
    if not fact_id:
        raise ValueError("fact ref requires a non-empty fact_id")
    return f"{FACT_REF}:{status}:{fact_id}"


def build_claim_ref(status: str, claim_id: str) -> str:
    """Build a ``claim:<status>:<id>`` reference."""

    if not status:
        raise ValueError("claim ref requires a non-empty status")
    if not claim_id:
        raise ValueError("claim ref requires a non-empty claim_id")
    return f"{CLAIM_REF}:{status}:{claim_id}"


def build_generic_ref(path: str, line_no: int) -> str:
    """Build a ``ref:<path>:<line>`` reference (find_references hits)."""

    if not path:
        raise ValueError("generic ref requires a non-empty path")
    if line_no < 1:
        raise ValueError("generic ref requires line_no >= 1")
    return f"{GENERIC_REF}:{path}:{line_no}"


def build_entrypoint_ref(path: str) -> str:
    """Build a ``entrypoint:<path>`` reference (find_entrypoints hits)."""

    if not path:
        raise ValueError("entrypoint ref requires a non-empty path")
    return f"{ENTRYPOINT_REF}:{path}"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse_typed_ref(ref: str) -> tuple[str, str]:
    """Split a typed reference into ``(type, body)``.

    Returns ``("", "")`` for an empty or unparseable reference.  The
    type is the substring before the first ``:``; the body is
    everything after.  When the reference has no ``:``, the type is
    the whole string and the body is empty.
    """

    if not ref:
        return "", ""
    idx = ref.find(":")
    if idx < 0:
        return ref, ""
    return ref[:idx], ref[idx + 1:]


def ref_type(ref: str) -> str:
    """Return the type prefix of a typed reference (empty if unparseable)."""

    return parse_typed_ref(ref)[0]


def ref_body(ref: str) -> str:
    """Return the body of a typed reference (empty if unparseable)."""

    return parse_typed_ref(ref)[1]


# ---------------------------------------------------------------------------
# Type checks
# ---------------------------------------------------------------------------


def is_symbol_ref(ref: str) -> bool:
    return ref_type(ref) == SYMBOL_REF


def is_span_ref(ref: str) -> bool:
    return ref_type(ref) == SPAN_REF


def is_behavior_ref(ref: str) -> bool:
    return ref_type(ref) == BEHAVIOR_REF


def is_packet_ref(ref: str) -> bool:
    return ref_type(ref) == PACKET_REF


def is_fact_ref(ref: str) -> bool:
    return ref_type(ref) == FACT_REF


def is_claim_ref(ref: str) -> bool:
    return ref_type(ref) == CLAIM_REF


def is_generic_ref(ref: str) -> bool:
    return ref_type(ref) == GENERIC_REF


def is_entrypoint_ref(ref: str) -> bool:
    return ref_type(ref) == ENTRYPOINT_REF


# ---------------------------------------------------------------------------
# Symbol ref field extraction
# ---------------------------------------------------------------------------


def split_symbol_ref(ref: str) -> tuple[str, str, int] | None:
    """Split a ``symbol:<path>:<name>:<line>`` reference into fields.

    Returns ``(path, name, start_line)`` or ``None`` when the reference
    is not a valid symbol ref.  The path may contain ``:`` (Windows
    drive letters or namespace separators), so the split is anchored
    from the right: the last two ``:``-delimited segments are the name
    and line, everything before is the path.
    """

    if not is_symbol_ref(ref):
        return None
    body = ref_body(ref)
    parts = body.rsplit(":", 2)
    if len(parts) < 3:
        return None
    path, name, line_str = parts
    try:
        line = int(line_str)
    except ValueError:
        return None
    if not path or not name or line < 1:
        return None
    return path, name, line


def split_span_ref(ref: str) -> tuple[str, int, int] | None:
    """Split a ``span:<path>:<start>:<end>`` reference into fields.

    Returns ``(path, start_line, end_line)`` or ``None`` when the
    reference is not a valid span ref.
    """

    if not is_span_ref(ref):
        return None
    body = ref_body(ref)
    parts = body.rsplit(":", 2)
    if len(parts) < 3:
        return None
    path, start_str, end_str = parts
    try:
        start = int(start_str)
        end = int(end_str)
    except ValueError:
        return None
    if not path or start < 1 or end < start:
        return None
    return path, start, end


def split_generic_ref(ref: str) -> tuple[str, int] | None:
    """Split a ``ref:<path>:<line>`` reference into fields.

    Returns ``(path, line_no)`` or ``None`` when the reference is not
    a valid generic ref.
    """

    if not is_generic_ref(ref):
        return None
    body = ref_body(ref)
    parts = body.rsplit(":", 1)
    if len(parts) < 2:
        return None
    path, line_str = parts
    try:
        line = int(line_str)
    except ValueError:
        return None
    if not path or line < 1:
        return None
    return path, line


def split_entrypoint_ref(ref: str) -> str | None:
    """Split a ``entrypoint:<path>`` reference into fields.

    Returns ``path`` or ``None`` when the reference is not a valid
    entrypoint ref.
    """

    if not is_entrypoint_ref(ref):
        return None
    body = ref_body(ref)
    if not body:
        return None
    return body


# ---------------------------------------------------------------------------
# Convenience: extract all refs of a given type from an observation
# ---------------------------------------------------------------------------


def refs_of_type(refs: list[str], ref_type_str: str) -> list[str]:
    """Filter ``refs`` to those matching the given type prefix."""

    return [r for r in refs if ref_type(r) == ref_type_str]


def symbol_refs(refs: list[str]) -> list[str]:
    return refs_of_type(refs, SYMBOL_REF)


def span_refs(refs: list[str]) -> list[str]:
    return refs_of_type(refs, SPAN_REF)


def behavior_refs(refs: list[str]) -> list[str]:
    return refs_of_type(refs, BEHAVIOR_REF)


def packet_refs(refs: list[str]) -> list[str]:
    return refs_of_type(refs, PACKET_REF)


def fact_refs(refs: list[str]) -> list[str]:
    return refs_of_type(refs, FACT_REF)


def claim_refs(refs: list[str]) -> list[str]:
    return refs_of_type(refs, CLAIM_REF)


def generic_refs(refs: list[str]) -> list[str]:
    return refs_of_type(refs, GENERIC_REF)


def entrypoint_refs(refs: list[str]) -> list[str]:
    return refs_of_type(refs, ENTRYPOINT_REF)


__all__ = [
    # Type prefixes
    "SYMBOL_REF",
    "SPAN_REF",
    "BEHAVIOR_REF",
    "PACKET_REF",
    "FACT_REF",
    "CLAIM_REF",
    "GENERIC_REF",
    "ENTRYPOINT_REF",
    "ALL_REF_TYPES",
    # Builders
    "build_symbol_ref",
    "build_span_ref",
    "build_behavior_ref",
    "build_packet_ref",
    "build_fact_ref",
    "build_claim_ref",
    "build_generic_ref",
    "build_entrypoint_ref",
    # Parser
    "parse_typed_ref",
    "ref_type",
    "ref_body",
    # Type checks
    "is_symbol_ref",
    "is_span_ref",
    "is_behavior_ref",
    "is_packet_ref",
    "is_fact_ref",
    "is_claim_ref",
    "is_generic_ref",
    "is_entrypoint_ref",
    # Field extraction
    "split_symbol_ref",
    "split_span_ref",
    "split_generic_ref",
    "split_entrypoint_ref",
    # Filtering
    "refs_of_type",
    "symbol_refs",
    "span_refs",
    "behavior_refs",
    "packet_refs",
    "fact_refs",
    "claim_refs",
    "generic_refs",
    "entrypoint_refs",
]
