"""Canonical content-read identity contract (plan section 13.3).

Both policy merge and the deterministic supervisor share
``research_read_identity`` so a "read already executed" decision can never
depend on two slightly different private rules.
"""

from __future__ import annotations

from code2paper.agentic.research_read_identity import (
    content_read_covers_line,
    content_read_signature,
    span_covers_line,
)


class TestContentReadSignature:
    def test_read_symbol_identity_is_path_and_symbol(self) -> None:
        assert (
            content_read_signature(
                "read_symbol", {"path": "src/a.py", "symbol": "train", "top_k": 1}
            )
            == "read_symbol:src/a.py::train"
        )

    def test_same_symbol_other_path_differs(self) -> None:
        a = content_read_signature(
            "read_symbol", {"path": "src/a.py", "symbol": "train"}
        )
        b = content_read_signature(
            "read_symbol", {"path": "src/b.py", "symbol": "train"}
        )
        assert a != b

    def test_read_code_span_identity_includes_interval(self) -> None:
        assert (
            content_read_signature(
                "read_code_span", {"path": "src/a.py", "start_line": 10, "end_line": 20}
            )
            == "read_code_span:src/a.py:10:20"
        )

    def test_non_content_tool_has_no_identity(self) -> None:
        assert content_read_signature("search_symbols", {"query": "train"}) == ""


class TestContentReadCoversLine:
    def test_read_symbol_exact_path_and_symbol(self) -> None:
        assert content_read_covers_line(
            "read_symbol",
            {"path": "a.py", "symbol": "train"},
            path="a.py",
            symbol="train",
        )
        assert not content_read_covers_line(
            "read_symbol",
            {"path": "b.py", "symbol": "train"},
            path="a.py",
            symbol="train",
        )
        assert not content_read_covers_line(
            "read_symbol",
            {"path": "a.py", "symbol": "other"},
            path="a.py",
            symbol="train",
        )

    def test_span_covers_only_when_interval_contains_line(self) -> None:
        args = {"path": "a.py", "start_line": 10, "end_line": 20}
        assert content_read_covers_line(
            "read_code_span", args, path="a.py", line=15
        )
        assert content_read_covers_line(
            "read_code_span", args, path="a.py", line=10
        )
        assert content_read_covers_line(
            "read_code_span", args, path="a.py", line=20
        )
        # Adjacent / different interval in the same file must not cover.
        assert not content_read_covers_line(
            "read_code_span", args, path="a.py", line=21
        )
        assert not content_read_covers_line(
            "read_code_span", args, path="a.py", line=9
        )
        # Different file never covers.
        assert not content_read_covers_line(
            "read_code_span", args, path="b.py", line=15
        )

    def test_span_without_recoverable_line_never_covers(self) -> None:
        args = {"path": "a.py", "start_line": 1, "end_line": 100}
        assert not content_read_covers_line(
            "read_code_span", args, path="a.py", line=None
        )


class TestSpanCoversLine:
    def test_covers_inside_interval(self) -> None:
        assert span_covers_line("span:src/a.py:10:20", 15)
        assert span_covers_line("span:src/a.py:10:20", 10)
        assert span_covers_line("span:src/a.py:10:20", 20)

    def test_does_not_cover_outside_interval(self) -> None:
        assert not span_covers_line("span:src/a.py:10:20", 9)
        assert not span_covers_line("span:src/a.py:10:20", 21)

    def test_malformed_span_never_covers(self) -> None:
        assert not span_covers_line("", 15)
        assert not span_covers_line("span:", 15)
        assert not span_covers_line("span:src/a.py:x:y", 15)
        assert not span_covers_line("not-a-span", 15)
