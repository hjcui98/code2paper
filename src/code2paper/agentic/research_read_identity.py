"""Canonical content-read identity shared by policy merge and the supervisor.

Two identities are deliberately separate:

* the *byte* identity (``content_read_signature``) is the normalized
  ``(tool, path, symbol | span)`` key.  Within one repo snapshot the returned
  bytes are identical regardless of which obligation prompted the read, so
  this identity is the cache key for reusing already-read source;
* the *analysis* identity (``obligation_read_signature``) adds the obligation
  id.  A second read of the same span for a *different* obligation is allowed
  (the bytes are reused, and the graph/claim compilation for that obligation
  still has to happen), while the same obligation re-reading the same span
  remains a no-gain duplicate.

Rules (fail-closed):

- ``read_symbol``: normalized repository-relative path plus exact symbol.
  A same-named symbol in another path is a different read.
- ``read_code_span``: normalized path plus ``start_line``/``end_line``.  A
  prior span read suppresses the candidate read only when its interval
  *covers* the candidate's source line; a different or merely adjacent
  interval in the same file must not count.
- A candidate without a recoverable exact symbol/span identity is never
  considered already-read from path equality alone.
"""

from __future__ import annotations

from typing import Any, Mapping


def content_read_signature(
    tool_name: str, arguments: Mapping[str, Any]
) -> str:
    """Return the normalized byte identity of a content-read call, or ``""``.

    ``arguments`` may come from a ``ResearchToolCallV1`` or an
    ``ExecutedToolCallSummaryV1`` (both expose ``tool_name`` +
    ``arguments``); only the identity-bearing fields are read.
    """

    if tool_name == "read_symbol":
        path = str(arguments.get("path", "") or "")
        symbol = str(arguments.get("symbol", "") or "")
        if path and symbol:
            return f"read_symbol:{path}::{symbol}"
        return ""
    if tool_name == "read_code_span":
        path = str(arguments.get("path", "") or "")
        start_line = int(arguments.get("start_line", 1) or 1)
        end_line = int(arguments.get("end_line", 0) or 0)
        if path:
            return f"read_code_span:{path}:{start_line}:{end_line}"
        return ""
    return ""


def obligation_read_signature(
    obligation_id: str, tool_name: str, arguments: Mapping[str, Any]
) -> str:
    """Return the obligation-scoped analysis identity of a content read.

    The no-gain rule applies per obligation: the same obligation may not
    re-read the same span, while another obligation may reuse the cached
    bytes for its own analysis.
    """

    identity = content_read_signature(tool_name, arguments)
    scoped = str(obligation_id or "").strip()
    if not identity or not scoped:
        return ""
    return f"{scoped}|{identity}"


def content_read_covers_line(
    tool_name: str,
    arguments: Mapping[str, Any],
    *,
    path: str,
    symbol: str = "",
    line: int | None = None,
) -> bool:
    """Return whether an executed read covers the exact candidate read.

    ``read_symbol`` covers only an exact (path, symbol) match.  A prior
    ``read_code_span`` covers only when its interval contains the
    candidate's source line; without a recoverable line it never covers.
    """

    if tool_name == "read_symbol":
        return (
            str(arguments.get("path", "") or "") == path
            and str(arguments.get("symbol", "") or "") == symbol
        )
    if tool_name == "read_code_span":
        if str(arguments.get("path", "") or "") != path:
            return False
        if line is None:
            return False
        start_line = int(arguments.get("start_line", 1) or 1)
        end_line = int(arguments.get("end_line", 0) or 0)
        return start_line <= line <= end_line
    return False


def span_covers_line(span_id: str, line: int) -> bool:
    """Return whether a ``span:<path>:<start>:<end>`` id contains ``line``."""

    if not span_id.startswith("span:"):
        return False
    body = span_id[len("span:"):]
    # The path may itself contain ``:``, so anchor from the right.
    parts = body.rsplit(":", 2)
    if len(parts) < 3:
        return False
    _path, start_str, end_str = parts
    try:
        start = int(start_str)
        end = int(end_str)
    except ValueError:
        return False
    return start <= line <= end
