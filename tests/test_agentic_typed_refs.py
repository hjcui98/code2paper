"""Unit tests for code2paper.agentic.typed_refs (Phase 3.2).

The typed_refs module is the single source of truth for building and
parsing the typed references that flow through the V3 evidence chain.
These tests exercise every builder, the parser, every type-check, every
splitter and the filtering helpers so downstream nodes
(observation_ingest, behavior_graph_updater, evidence_critic) can rely
on the contract.
"""

from __future__ import annotations

import pytest

from code2paper.agentic.typed_refs import (
    ALL_REF_TYPES,
    BEHAVIOR_REF,
    CLAIM_REF,
    ENTRYPOINT_REF,
    FACT_REF,
    GENERIC_REF,
    PACKET_REF,
    SPAN_REF,
    SYMBOL_REF,
    __all__ as exported_names,
    behavior_refs,
    build_behavior_ref,
    build_claim_ref,
    build_entrypoint_ref,
    build_fact_ref,
    build_generic_ref,
    build_packet_ref,
    build_span_ref,
    build_symbol_ref,
    claim_refs,
    entrypoint_refs,
    fact_refs,
    generic_refs,
    is_behavior_ref,
    is_claim_ref,
    is_entrypoint_ref,
    is_fact_ref,
    is_generic_ref,
    is_packet_ref,
    is_span_ref,
    is_symbol_ref,
    packet_refs,
    parse_typed_ref,
    ref_body,
    ref_type,
    refs_of_type,
    split_entrypoint_ref,
    split_generic_ref,
    split_span_ref,
    split_symbol_ref,
    span_refs,
    symbol_refs,
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


class TestSymbolRefBuilder:
    def test_builds_canonical_ref(self):
        ref = build_symbol_ref("src/foo.py", "Bar", 10)
        assert ref == "symbol:src/foo.py:Bar:10"

    def test_path_may_contain_colon(self):
        # Paths with colons (e.g. namespace separators) are preserved.
        ref = build_symbol_ref("pkg:sub/foo.py", "Bar", 1)
        assert ref == "symbol:pkg:sub/foo.py:Bar:1"

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError, match="path"):
            build_symbol_ref("", "Bar", 1)

    def test_rejects_empty_symbol(self):
        with pytest.raises(ValueError, match="symbol"):
            build_symbol_ref("foo.py", "", 1)

    def test_rejects_zero_line(self):
        with pytest.raises(ValueError, match="start_line"):
            build_symbol_ref("foo.py", "Bar", 0)

    def test_rejects_negative_line(self):
        with pytest.raises(ValueError, match="start_line"):
            build_symbol_ref("foo.py", "Bar", -3)


class TestSpanRefBuilder:
    def test_builds_canonical_ref(self):
        ref = build_span_ref("src/foo.py", 10, 20)
        assert ref == "span:src/foo.py:10:20"

    def test_single_line_span(self):
        ref = build_span_ref("foo.py", 5, 5)
        assert ref == "span:foo.py:5:5"

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError, match="path"):
            build_span_ref("", 1, 2)

    def test_rejects_start_below_one(self):
        with pytest.raises(ValueError, match="start_line"):
            build_span_ref("foo.py", 0, 2)

    def test_rejects_end_below_start(self):
        with pytest.raises(ValueError, match="end_line"):
            build_span_ref("foo.py", 10, 5)


class TestBehaviorRefBuilder:
    def test_builds_canonical_ref(self):
        ref = build_behavior_ref("node-abc-123")
        assert ref == "behavior:node-abc-123"

    def test_rejects_empty_node_id(self):
        with pytest.raises(ValueError, match="node_id"):
            build_behavior_ref("")


class TestPacketRefBuilder:
    def test_builds_canonical_ref(self):
        ref = build_packet_ref("proposed", "pkt-1")
        assert ref == "packet:proposed:pkt-1"

    def test_rejects_empty_status(self):
        with pytest.raises(ValueError, match="status"):
            build_packet_ref("", "pkt-1")

    def test_rejects_empty_id(self):
        with pytest.raises(ValueError, match="packet_id"):
            build_packet_ref("proposed", "")


class TestFactRefBuilder:
    def test_builds_canonical_ref(self):
        ref = build_fact_ref("compiled", "fact-9")
        assert ref == "fact:compiled:fact-9"

    def test_rejects_empty_status(self):
        with pytest.raises(ValueError, match="status"):
            build_fact_ref("", "fact-9")

    def test_rejects_empty_id(self):
        with pytest.raises(ValueError, match="fact_id"):
            build_fact_ref("compiled", "")


class TestClaimRefBuilder:
    def test_builds_canonical_ref(self):
        ref = build_claim_ref("authorized", "claim-3")
        assert ref == "claim:authorized:claim-3"

    def test_rejects_empty_status(self):
        with pytest.raises(ValueError, match="status"):
            build_claim_ref("", "claim-3")

    def test_rejects_empty_id(self):
        with pytest.raises(ValueError, match="claim_id"):
            build_claim_ref("authorized", "")


class TestGenericRefBuilder:
    def test_builds_canonical_ref(self):
        ref = build_generic_ref("src/foo.py", 42)
        assert ref == "ref:src/foo.py:42"

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError, match="path"):
            build_generic_ref("", 1)

    def test_rejects_zero_line(self):
        with pytest.raises(ValueError, match="line_no"):
            build_generic_ref("foo.py", 0)


class TestEntrypointRefBuilder:
    def test_builds_canonical_ref(self):
        ref = build_entrypoint_ref("src/main.py")
        assert ref == "entrypoint:src/main.py"

    def test_path_may_contain_colon(self):
        ref = build_entrypoint_ref("pkg:sub/main.py")
        assert ref == "entrypoint:pkg:sub/main.py"

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError, match="path"):
            build_entrypoint_ref("")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestParser:
    def test_parse_returns_type_and_body(self):
        assert parse_typed_ref("symbol:foo.py:Bar:1") == ("symbol", "foo.py:Bar:1")

    def test_parse_handles_body_with_colons(self):
        assert parse_typed_ref("entrypoint:pkg:sub/main.py") == (
            "entrypoint",
            "pkg:sub/main.py",
        )

    def test_parse_empty_returns_empty_tuple(self):
        assert parse_typed_ref("") == ("", "")

    def test_parse_no_colon_returns_whole_as_type(self):
        assert parse_typed_ref("plain") == ("plain", "")

    def test_ref_type_returns_first_segment(self):
        assert ref_type("symbol:foo.py:Bar:1") == "symbol"
        assert ref_type("behavior:node-1") == "behavior"
        assert ref_type("entrypoint:main.py") == "entrypoint"

    def test_ref_body_returns_rest(self):
        assert ref_body("symbol:foo.py:Bar:1") == "foo.py:Bar:1"
        assert ref_body("behavior:node-1") == "node-1"

    def test_ref_type_empty_for_empty_input(self):
        assert ref_type("") == ""

    def test_ref_body_empty_for_empty_input(self):
        assert ref_body("") == ""


# ---------------------------------------------------------------------------
# Type checks
# ---------------------------------------------------------------------------


class TestTypeChecks:
    def test_is_symbol_ref(self):
        assert is_symbol_ref("symbol:foo.py:Bar:1")
        assert not is_symbol_ref("behavior:node-1")
        assert not is_symbol_ref("")

    def test_is_span_ref(self):
        assert is_span_ref("span:foo.py:1:5")
        assert not is_span_ref("symbol:foo.py:Bar:1")

    def test_is_behavior_ref(self):
        assert is_behavior_ref("behavior:node-1")
        assert not is_behavior_ref("symbol:foo.py:Bar:1")

    def test_is_packet_ref(self):
        assert is_packet_ref("packet:proposed:pkt-1")
        assert not is_packet_ref("fact:compiled:f-1")

    def test_is_fact_ref(self):
        assert is_fact_ref("fact:compiled:f-1")
        assert not is_fact_ref("packet:proposed:pkt-1")

    def test_is_claim_ref(self):
        assert is_claim_ref("claim:authorized:c-1")
        assert not is_claim_ref("fact:compiled:f-1")

    def test_is_generic_ref(self):
        assert is_generic_ref("ref:foo.py:10")
        assert not is_generic_ref("symbol:foo.py:Bar:1")

    def test_is_entrypoint_ref(self):
        assert is_entrypoint_ref("entrypoint:main.py")
        assert not is_entrypoint_ref("ref:main.py:10")


# ---------------------------------------------------------------------------
# Field extraction (splitters)
# ---------------------------------------------------------------------------


class TestSplitters:
    def test_split_symbol_ref(self):
        assert split_symbol_ref("symbol:src/foo.py:Bar:10") == ("src/foo.py", "Bar", 10)

    def test_split_symbol_ref_with_colon_in_path(self):
        # Path may contain colons; the splitter anchors from the right.
        assert split_symbol_ref("symbol:pkg:sub/foo.py:Bar:1") == (
            "pkg:sub/foo.py",
            "Bar",
            1,
        )

    def test_split_symbol_ref_returns_none_for_non_symbol(self):
        assert split_symbol_ref("behavior:node-1") is None
        assert split_symbol_ref("") is None

    def test_split_symbol_ref_returns_none_for_missing_line(self):
        assert split_symbol_ref("symbol:foo.py:Bar") is None

    def test_split_symbol_ref_returns_none_for_non_numeric_line(self):
        assert split_symbol_ref("symbol:foo.py:Bar:abc") is None

    def test_split_span_ref(self):
        assert split_span_ref("span:src/foo.py:10:20") == ("src/foo.py", 10, 20)

    def test_split_span_ref_with_colon_in_path(self):
        assert split_span_ref("span:pkg:sub/foo.py:1:5") == ("pkg:sub/foo.py", 1, 5)

    def test_split_span_ref_returns_none_for_non_span(self):
        assert split_span_ref("symbol:foo.py:Bar:1") is None
        assert split_span_ref("") is None

    def test_split_span_ref_returns_none_for_invalid_lines(self):
        assert split_span_ref("span:foo.py:abc:5") is None
        assert split_span_ref("span:foo.py:5:abc") is None

    def test_split_generic_ref(self):
        assert split_generic_ref("ref:src/foo.py:42") == ("src/foo.py", 42)

    def test_split_generic_ref_with_colon_in_path(self):
        assert split_generic_ref("ref:pkg:sub/foo.py:1") == ("pkg:sub/foo.py", 1)

    def test_split_generic_ref_returns_none_for_non_generic(self):
        assert split_generic_ref("symbol:foo.py:Bar:1") is None
        assert split_generic_ref("") is None

    def test_split_generic_ref_returns_none_for_invalid_line(self):
        assert split_generic_ref("ref:foo.py:abc") is None

    def test_split_entrypoint_ref(self):
        assert split_entrypoint_ref("entrypoint:src/main.py") == "src/main.py"

    def test_split_entrypoint_ref_with_colon_in_path(self):
        assert split_entrypoint_ref("entrypoint:pkg:sub/main.py") == "pkg:sub/main.py"

    def test_split_entrypoint_ref_returns_none_for_non_entrypoint(self):
        assert split_entrypoint_ref("ref:main.py:10") is None
        assert split_entrypoint_ref("") is None

    def test_split_entrypoint_ref_returns_none_for_empty_body(self):
        assert split_entrypoint_ref("entrypoint:") is None


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------


class TestFiltering:
    def test_refs_of_type_filters_by_prefix(self):
        refs = [
            "symbol:foo.py:Bar:1",
            "behavior:node-1",
            "symbol:baz.py:Qux:2",
            "ref:foo.py:10",
        ]
        assert refs_of_type(refs, "symbol") == [
            "symbol:foo.py:Bar:1",
            "symbol:baz.py:Qux:2",
        ]

    def test_symbol_refs(self):
        refs = ["symbol:foo.py:Bar:1", "behavior:node-1"]
        assert symbol_refs(refs) == ["symbol:foo.py:Bar:1"]

    def test_span_refs(self):
        refs = ["span:foo.py:1:5", "symbol:foo.py:Bar:1"]
        assert span_refs(refs) == ["span:foo.py:1:5"]

    def test_behavior_refs(self):
        refs = ["behavior:node-1", "symbol:foo.py:Bar:1", "behavior:node-2"]
        assert behavior_refs(refs) == ["behavior:node-1", "behavior:node-2"]

    def test_packet_refs(self):
        refs = ["packet:proposed:p1", "fact:compiled:f1", "packet:validated:p2"]
        assert packet_refs(refs) == ["packet:proposed:p1", "packet:validated:p2"]

    def test_fact_refs(self):
        refs = ["fact:compiled:f1", "packet:proposed:p1", "fact:validated:f2"]
        assert fact_refs(refs) == ["fact:compiled:f1", "fact:validated:f2"]

    def test_claim_refs(self):
        refs = ["claim:authorized:c1", "fact:compiled:f1", "claim:decomposed:c2"]
        assert claim_refs(refs) == ["claim:authorized:c1", "claim:decomposed:c2"]

    def test_generic_refs(self):
        refs = ["ref:foo.py:10", "symbol:foo.py:Bar:1", "ref:baz.py:20"]
        assert generic_refs(refs) == ["ref:foo.py:10", "ref:baz.py:20"]

    def test_entrypoint_refs(self):
        refs = ["entrypoint:main.py", "ref:foo.py:10", "entrypoint:cli.py"]
        assert entrypoint_refs(refs) == ["entrypoint:main.py", "entrypoint:cli.py"]

    def test_filtering_empty_list(self):
        assert symbol_refs([]) == []
        assert behavior_refs([]) == []


# ---------------------------------------------------------------------------
# Registry / module surface
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_all_ref_types_contains_every_type(self):
        assert ALL_REF_TYPES == frozenset({
            SYMBOL_REF,
            SPAN_REF,
            BEHAVIOR_REF,
            PACKET_REF,
            FACT_REF,
            CLAIM_REF,
            GENERIC_REF,
            ENTRYPOINT_REF,
        })

    def test_all_ref_types_is_frozen(self):
        with pytest.raises(AttributeError):
            ALL_REF_TYPES.add("foo")  # type: ignore[attr-defined]

    def test_module_exports_all_helpers(self):
        # Every public helper should be in __all__ so downstream consumers
        # can do ``from code2paper.agentic.typed_refs import *`` safely.
        for name in (
            "build_symbol_ref",
            "build_span_ref",
            "build_behavior_ref",
            "build_packet_ref",
            "build_fact_ref",
            "build_claim_ref",
            "build_generic_ref",
            "build_entrypoint_ref",
            "parse_typed_ref",
            "ref_type",
            "ref_body",
            "is_symbol_ref",
            "is_span_ref",
            "is_behavior_ref",
            "is_packet_ref",
            "is_fact_ref",
            "is_claim_ref",
            "is_generic_ref",
            "is_entrypoint_ref",
            "split_symbol_ref",
            "split_span_ref",
            "split_generic_ref",
            "split_entrypoint_ref",
            "refs_of_type",
            "symbol_refs",
            "span_refs",
            "behavior_refs",
            "packet_refs",
            "fact_refs",
            "claim_refs",
            "generic_refs",
            "entrypoint_refs",
        ):
            assert name in exported_names, f"missing {name!r} in __all__"


# ---------------------------------------------------------------------------
# Round-trip: build -> parse -> split
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_symbol_ref_round_trip(self):
        ref = build_symbol_ref("src/foo.py", "Bar", 10)
        assert is_symbol_ref(ref)
        assert split_symbol_ref(ref) == ("src/foo.py", "Bar", 10)

    def test_span_ref_round_trip(self):
        ref = build_span_ref("src/foo.py", 10, 20)
        assert is_span_ref(ref)
        assert split_span_ref(ref) == ("src/foo.py", 10, 20)

    def test_behavior_ref_round_trip(self):
        ref = build_behavior_ref("node-abc")
        assert is_behavior_ref(ref)
        assert ref_body(ref) == "node-abc"

    def test_packet_ref_round_trip(self):
        ref = build_packet_ref("proposed", "pkt-1")
        assert is_packet_ref(ref)
        assert ref_body(ref) == "proposed:pkt-1"

    def test_fact_ref_round_trip(self):
        ref = build_fact_ref("compiled", "fact-9")
        assert is_fact_ref(ref)
        assert ref_body(ref) == "compiled:fact-9"

    def test_claim_ref_round_trip(self):
        ref = build_claim_ref("authorized", "claim-3")
        assert is_claim_ref(ref)
        assert ref_body(ref) == "authorized:claim-3"

    def test_generic_ref_round_trip(self):
        ref = build_generic_ref("src/foo.py", 42)
        assert is_generic_ref(ref)
        assert split_generic_ref(ref) == ("src/foo.py", 42)

    def test_entrypoint_ref_round_trip(self):
        ref = build_entrypoint_ref("src/main.py")
        assert is_entrypoint_ref(ref)
        assert split_entrypoint_ref(ref) == "src/main.py"
