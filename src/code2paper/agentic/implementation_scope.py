"""Generic target-implementation ownership and acquisition helpers.

These helpers deliberately operate on the repository's typed symbol and
behavior records.  They do not know benchmark names or paper answers.  The
scope is a safety projection used for ranking and audit; it never creates an
evidence fact by itself.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from code2paper.agentic.behavior_graph import make_symbol_id
from code2paper.agentic.research_models import (
    CandidateAcquisitionLedgerV1,
    CandidateAcquisitionRecordV1,
    ImplementationOwnershipRoleV1,
    ImplementationScopeV1,
)
from code2paper.agentic.source_inventory import classify_source_kind
from code2paper.agentic.typed_refs import split_span_ref, split_symbol_ref


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_EVALUATION_RE = re.compile(
    r"(?:^|[/_.-])(eval(?:uate|uation)?|benchmark|metric|metrics|ablation|test|tests)(?:$|[/_.-])",
    re.I,
)
_COMPARAND_RE = re.compile(
    r"(?:^|[/_.-])(baseline|compar(?:e|ison|and)s?|competitor|reference)(?:$|[/_.-])",
    re.I,
)
_CONFIG_RE = re.compile(
    r"(?:config|configuration|settings?|options?|args?|flags?|params?|hyperparam)",
    re.I,
)

_SCOPE_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "into", "is", "it", "its", "model", "of", "on", "or", "that",
    "the", "this", "to", "using", "via", "we", "with",
})
_ENTRY_LIFECYCLE_TERMS = (
    "forward", "encode", "decode", "infer", "predict", "generate", "train",
    "fit", "run", "main", "rerank", "retrieve", "search", "execute",
)
_ENTRY_HELPER_PREFIXES = (
    "get_", "set_", "load_", "save_", "make_", "build_", "create_",
    "parse_", "format_", "validate_", "_",
)

_OWNERSHIP_GRAPH_RELATIONS = frozenset(
    {"CALLS", "RETURNS_TO", "CONTAINS", "IMPLEMENTS", "OVERRIDES"}
)


def _tokens(value: Any) -> set[str]:
    """Tokenize prose and identifiers without relying on project names.

    Symbol indexes preserve Python's CamelCase spelling.  Treating
    ``EBCarRerankerHybridAttention`` as one opaque token made the generic
    owner selector prefer whichever equally-scored ``forward`` happened to
    sort first.  Splitting identifier boundaries keeps the signal semantic
    (``reranker``, ``hybrid``, ``attention``) while retaining the original
    token for callers that use a compact name.
    """

    result: set[str] = set()
    for item in _TOKEN_RE.findall(str(value or "")):
        lowered = item.casefold()
        result.add(lowered)
        for piece in _CAMEL_BOUNDARY_RE.sub(" ", item).replace("_", " ").split():
            if len(piece) >= 3:
                result.add(piece.casefold())
    return result


def _attr(value: Any, name: str, default: Any = "") -> Any:
    """Read a typed model attribute or its checkpointed mapping form."""

    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _symbol_id(symbol: Any) -> str:
    return str(_attr(symbol, "symbol_id", "") or "").strip()


def _symbol_text(symbol: Any) -> str:
    return " ".join(
        str(_attr(symbol, name, "") or "")
        for name in ("qualified_name", "path", "kind", "docstring")
    )


def _symbol_parent_key(symbol: Any, symbols_by_id: Mapping[str, Any]) -> str:
    """Return a stable class/module grouping key for a symbol.

    Real indexes carry ``parent_symbol_id``.  Small replay fixtures sometimes
    omit the parent record, so the qualified-name prefix is a safe structural
    fallback; it is never used as source evidence.
    """

    parent_id = str(_attr(symbol, "parent_symbol_id", "") or "").strip()
    if parent_id and parent_id in symbols_by_id:
        return parent_id
    qualified_name = str(_attr(symbol, "qualified_name", "") or "")
    if "." in qualified_name:
        return qualified_name.rsplit(".", 1)[0]
    return str(_attr(symbol, "path", "") or "")


def _symbol_parent_context(symbol: Any, symbols_by_id: Mapping[str, Any]) -> str:
    """Return the indexed parent context used for entry disambiguation."""

    parent_id = str(_attr(symbol, "parent_symbol_id", "") or "").strip()
    parent = symbols_by_id.get(parent_id)
    if parent is not None:
        return _symbol_text(parent)
    qualified_name = str(_attr(symbol, "qualified_name", "") or "")
    if "." in qualified_name:
        return qualified_name.rsplit(".", 1)[0]
    return str(_attr(symbol, "path", "") or "")


def _is_public_lifecycle_symbol(symbol: Any) -> bool:
    """Whether a symbol is a public lifecycle boundary, not a helper."""

    kind = str(_attr(symbol, "kind", "") or "").casefold()
    if kind not in {"function", "method"}:
        return False
    leaf = str(_attr(symbol, "qualified_name", "") or "").rsplit(".", 1)[-1].casefold()
    if leaf.startswith(_ENTRY_HELPER_PREFIXES):
        return False
    return leaf in _ENTRY_LIFECYCLE_TERMS


def _canonical_symbol_id(value: Any, symbols_by_id: Mapping[str, Any]) -> str:
    """Resolve a symbol id or a typed location ref to the indexed id."""

    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw in symbols_by_id:
        return raw
    parsed = _location_ref_parts(raw)
    if parsed is not None:
        binding = resolve_candidate_binding(
            raw,
            symbols=tuple(symbols_by_id.values()),
            mode="scope",
        )
        if not binding.ambiguous and len(binding.canonical_symbol_ids) == 1:
            return binding.canonical_symbol_ids[0]
        # The adapter and typed-ref builder share this stable id scheme.  It
        # is accepted only when it is actually present in the index; a leaf
        # ref that cannot be uniquely resolved remains unresolved.
        path, name, line = parsed
        candidate = make_symbol_id(path, name, line)
        if candidate in symbols_by_id:
            return candidate
        return raw
    # Accept a compact path/name or path-only seed when it uniquely resolves.
    for symbol_id, symbol in symbols_by_id.items():
        path = str(_attr(symbol, "path", "") or "")
        name = str(_attr(symbol, "qualified_name", "") or "")
        if raw in {path, f"{path}:{name}", f"{path}:{name.split('.')[-1]}"}:
            return symbol_id
    return raw


def _candidate_location(value: str) -> tuple[str, str, int] | None:
    parsed = _location_ref_parts(value)
    if parsed is not None:
        return parsed
    return None


@dataclass(frozen=True)
class CandidateBindingV1:
    """Deterministic binding of one candidate/ref to repository identities.

    A candidate is not evidence.  This value only records how a typed
    location, stable symbol id, behavior id, or exact source span binds to
    the frozen repository index.  ``ambiguous`` and ``rejection_code`` are
    deliberately preserved so callers cannot silently fall back to a broad
    path match after identity resolution failed.
    """

    raw_ref: str
    canonical_symbol_ids: tuple[str, ...] = ()
    symbol_ranges: tuple[tuple[str, int, int], ...] = ()
    behavior_node_ids: tuple[str, ...] = ()
    exact_spans: tuple[tuple[str, int, int], ...] = ()
    index_available: bool = False
    ambiguous: bool = False
    rejection_code: str = ""

    @property
    def resolved(self) -> bool:
        return bool(
            self.canonical_symbol_ids
            or self.behavior_node_ids
            or self.exact_spans
        ) and not self.ambiguous and not self.rejection_code


def _normalized_source_path(value: Any) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    return raw


def _span_interval(value: Any) -> tuple[str, int, int] | None:
    parsed = split_span_ref(str(value or ""))
    if parsed is None:
        return None
    path, start, end = parsed
    path = _normalized_source_path(path)
    return (path, int(start), int(end)) if path else None


def source_intervals_overlap(
    left: tuple[str, int, int] | None,
    right: tuple[str, int, int] | None,
) -> bool:
    """Return whether two repository-relative source intervals overlap."""

    if left is None or right is None:
        return False
    return (
        _normalized_source_path(left[0]) == _normalized_source_path(right[0])
        and int(left[1]) <= int(right[2])
        and int(right[1]) <= int(left[2])
    )


def _symbol_location_matches(
    symbol: Any,
    *,
    path: str,
    name: str,
    line: int,
) -> tuple[int, tuple[str, int, int]] | None:
    symbol_path = _normalized_source_path(_attr(symbol, "path", ""))
    if symbol_path != path:
        return None
    qualified_name = str(_attr(symbol, "qualified_name", "") or "").strip()
    if not qualified_name:
        return None
    leaf = name.rsplit(".", 1)[-1]
    if qualified_name == name:
        name_score = 4
    elif qualified_name.rsplit(".", 1)[-1] == name:
        name_score = 3
    elif qualified_name.rsplit(".", 1)[-1] == leaf or qualified_name.endswith(
        f".{leaf}"
    ):
        name_score = 2
    else:
        return None
    start = int(_attr(symbol, "start_line", 0) or 0)
    end = int(_attr(symbol, "end_line", 0) or 0)
    if start < 1 or end < start or not (start <= line <= end):
        return None
    line_score = 2 if start == line else 1
    return name_score + line_score, (symbol_path, start, end)


def _location_ref_parts(value: Any) -> tuple[str, str, int] | None:
    """Parse a symbol-location ref from either the symbol or behavior lane.

    ``behavior:<node_id>`` is a graph identity.  A few acquisition tools also
    emit ``behavior:<path>:<qualified-name>:<declaration-line>`` as a location
    hint, however, and that hint must go through the same index resolution as
    ``symbol:...`` rather than falling back to a path-wide match.
    """

    raw = str(value or "").strip()
    parsed = split_symbol_ref(raw)
    if parsed is not None:
        return parsed
    if not raw.startswith("behavior:"):
        return None
    body = raw.removeprefix("behavior:")
    parts = body.rsplit(":", 2)
    if len(parts) != 3:
        return None
    path, name, line_text = parts
    try:
        line = int(line_text)
    except (TypeError, ValueError):
        return None
    if not path or not name or line < 1:
        return None
    return path, name, line


def resolve_candidate_binding(
    candidate: Any,
    *,
    symbols: Iterable[Any] = (),
    behavior_nodes: Iterable[Any] = (),
    exact_span_ids: Iterable[str] = (),
    mode: str = "compile",
) -> CandidateBindingV1:
    """Resolve one candidate through the repository identity hierarchy.

    Resolution order is stable-id/node-id, indexed qualified symbol, then
    exact source span.  Leaf-name resolution is accepted only when it has a
    unique best indexed match.  A typed symbol candidate without an index is
    an identity failure for compilation; it is never widened to the whole
    file.  Source intervals use overlap, which covers a wide read span and
    statement-level behavior spans without admitting a sibling symbol.
    """

    raw = str(candidate or "").strip()
    symbol_items = tuple(symbols)
    node_items = tuple(behavior_nodes)
    intervals: list[tuple[str, int, int]] = []
    for value in exact_span_ids:
        interval = _span_interval(value)
        if interval is not None and interval not in intervals:
            intervals.append(interval)
    candidate_interval = _span_interval(raw)
    if candidate_interval is not None and candidate_interval not in intervals:
        intervals.append(candidate_interval)

    direct_nodes: list[str] = []
    raw_node_id = raw.removeprefix("behavior:")
    for node in node_items:
        node_id = str(_attr(node, "node_id", "") or "").strip()
        if node_id and node_id in {raw, raw_node_id} and node_id not in direct_nodes:
            direct_nodes.append(node_id)

    canonical: list[str] = []
    ranges: list[tuple[str, int, int]] = []
    ambiguous = False
    rejection_code = ""
    parsed_symbol = _location_ref_parts(raw)
    if parsed_symbol is not None:
        path, name, line = parsed_symbol
        path = _normalized_source_path(path)
        if not symbol_items:
            # Preserve an exact legacy stable-id match for direct callers.
            # The compile gate still reports a missing index when this id is
            # not present on any behavior node; a qualified leaf cannot be
            # widened from this fallback.
            canonical.append(make_symbol_id(path, name, line))
            if mode in {"compile", "acquisition", "promotion"}:
                rejection_code = "symbol_index_not_available_to_compile"
        else:
            matches: list[tuple[int, str, tuple[str, int, int]]] = []
            for symbol in symbol_items:
                match = _symbol_location_matches(
                    symbol,
                    path=path,
                    name=name,
                    line=line,
                )
                symbol_id = str(_attr(symbol, "symbol_id", "") or "").strip()
                if match is not None and symbol_id:
                    score, symbol_range = match
                    matches.append((score, symbol_id, symbol_range))
            if matches:
                best_score = max(item[0] for item in matches)
                best = [item for item in matches if item[0] == best_score]
                if len(best) != 1:
                    ambiguous = True
                    rejection_code = "candidate_identity_ambiguous"
                else:
                    _score, symbol_id, symbol_range = best[0]
                    canonical.append(symbol_id)
                    ranges.append(symbol_range)
            else:
                rejection_code = "candidate_identity_resolution_failed"
    elif raw.startswith("symbol:"):
        stable_id = raw.removeprefix("symbol:")
        indexed = [
            symbol
            for symbol in symbol_items
            if str(_attr(symbol, "symbol_id", "") or "").strip() == stable_id
        ]
        if len(indexed) == 1:
            canonical.append(stable_id)
            start = int(_attr(indexed[0], "start_line", 0) or 0)
            end = int(_attr(indexed[0], "end_line", 0) or 0)
            path = _normalized_source_path(_attr(indexed[0], "path", ""))
            if path and start > 0 and end >= start:
                ranges.append((path, start, end))
        elif len(indexed) > 1:
            ambiguous = True
            rejection_code = "candidate_identity_ambiguous"
        elif stable_id.startswith("sym:"):
            # A stable id can still bind directly to a graph node in a
            # compatibility fixture.  It carries no qualified-name proof,
            # so do not manufacture a range when the index is absent.
            canonical.append(stable_id)
    elif raw and not raw.startswith(("span:", "behavior:")):
        # Accept an unwrapped stable symbol id or symbol name only through
        # the frozen index.  Exact stable/qualified-name matches outrank
        # leaf-name matches; a tie at the best score is an identity
        # ambiguity rather than permission to choose by sort order.
        indexed_matches: list[tuple[int, str, Any]] = []
        for symbol in symbol_items:
            symbol_id = str(_attr(symbol, "symbol_id", "") or "").strip()
            qualified_name = str(_attr(symbol, "qualified_name", "") or "").strip()
            if not symbol_id or not qualified_name:
                continue
            if raw == symbol_id:
                score = 4
            elif raw == qualified_name:
                score = 3
            elif raw == qualified_name.rsplit(".", 1)[-1]:
                score = 2
            else:
                continue
            indexed_matches.append((score, symbol_id, symbol))
        if indexed_matches:
            best_score = max(item[0] for item in indexed_matches)
            best = [item for item in indexed_matches if item[0] == best_score]
            if len(best) != 1:
                ambiguous = True
                rejection_code = "candidate_identity_ambiguous"
            else:
                _score, symbol_id, symbol = best[0]
                canonical.append(symbol_id)
                start = int(_attr(symbol, "start_line", 0) or 0)
                end = int(_attr(symbol, "end_line", 0) or 0)
                path = _normalized_source_path(_attr(symbol, "path", ""))
                if path and start > 0 and end >= start:
                    ranges.append((path, start, end))

    # Exact span candidates are valid identity anchors even when there is no
    # symbol index.  They do not authorize claims by themselves.
    node_matches: list[str] = list(direct_nodes)
    canonical_set = set(canonical)
    range_items = tuple(ranges)
    for node in node_items:
        node_id = str(_attr(node, "node_id", "") or "").strip()
        if not node_id:
            continue
        node_symbol_id = str(_attr(node, "symbol_id", "") or "").strip()
        node_interval = _span_interval(_attr(node, "source_span_id", ""))
        # A raw stable symbol id may be used by older checkpoint fixtures.
        # This is an exact graph identity match, not a path/name or span
        # fallback, so it does not widen the candidate to sibling nodes.
        matched = node_symbol_id in canonical_set or (
            bool(raw) and node_symbol_id == raw
        )
        # A typed location that failed index resolution is not allowed to
        # regain authority through its declaration line or a broad file/span
        # overlap.  The sole compatibility exception is an exact stable graph
        # symbol id carried in ``canonical_symbol_ids`` without an index.
        allow_interval_match = not rejection_code
        if not matched and allow_interval_match and node_interval is not None:
            # An indexed symbol range is authoritative.  Do not fall back to
            # an observation's wider read span, which may include a sibling
            # method in the same file.
            if range_items:
                matched = any(
                    source_intervals_overlap(node_interval, item)
                    for item in range_items
                )
            else:
                matched = any(source_intervals_overlap(node_interval, item) for item in intervals)
        if matched and node_id not in node_matches:
            node_matches.append(node_id)

    return CandidateBindingV1(
        raw_ref=raw,
        canonical_symbol_ids=tuple(dict.fromkeys(canonical)),
        symbol_ranges=tuple(dict.fromkeys(ranges)),
        behavior_node_ids=tuple(dict.fromkeys(node_matches)),
        exact_spans=tuple(dict.fromkeys(intervals)),
        index_available=bool(symbol_items),
        ambiguous=ambiguous,
        rejection_code=rejection_code,
    )


def infer_implementation_scope(
    symbols: Iterable[Any] = (),
    *,
    author_texts: Iterable[str] = (),
    entry_symbol_ids: Iterable[str] = (),
    behavior_graph: Any | None = None,
    evidence_refs: Iterable[str] = (),
) -> ImplementationScopeV1:
    """Infer a conservative ownership partition from repository structure.

    Entry symbols are target roots.  Symbols reachable from those roots via
    typed behavior edges are dependencies.  Remaining symbols are ranked by
    author-intent token overlap; names that clearly describe comparison or
    evaluation stay in those audit-only roles.  Ambiguous symbols remain
    ``unknown`` rather than being promoted to target code.
    """

    symbol_items = tuple(symbols)
    by_id = {_symbol_id(item): item for item in symbol_items if _symbol_id(item)}
    # ``author_texts`` may be a generator; normalize once for deterministic
    # use.  The previous implementation consumed generators while building
    # the token set, silently dropping the intent signal on the second pass.
    author_items = tuple(str(item or "") for item in author_texts)
    entry_ids = tuple(
        dict.fromkeys(
            resolved
            for resolved in (_canonical_symbol_id(item, by_id) for item in entry_symbol_ids)
            if resolved in by_id
        )
    )
    def scope_tokens(value: Any) -> set[str]:
        return _tokens(value) - _SCOPE_STOPWORDS

    intent_tokens = (
        set().union(*(scope_tokens(item) for item in author_items))
        if author_items
        else set()
    )

    def entry_score(symbol: Any, *, topology_bonus: int = 0) -> int:
        """Score a structural entry candidate with parent context first."""

        overlap = len(scope_tokens(_symbol_text(symbol)) & intent_tokens)
        parent_overlap = len(
            scope_tokens(_symbol_parent_context(symbol, by_id)) & intent_tokens
        )
        leaf_name = str(_attr(symbol, "qualified_name", "") or "").split(".")[-1].casefold()
        lifecycle_bonus = 8 if _is_public_lifecycle_symbol(symbol) else 0
        helper_penalty = 9 if leaf_name.startswith(_ENTRY_HELPER_PREFIXES) else 0
        # Parent context is deliberately weighted more heavily than a method
        # name.  ``forward`` exists in many nested model classes; a class
        # whose name identifies the target component is the useful boundary.
        return overlap * 2 + parent_overlap * 5 + lifecycle_bonus + topology_bonus - helper_penalty

    graph_nodes = {
        str(_attr(node, "node_id", "") or ""): node
        for node in (getattr(behavior_graph, "nodes", ()) or ())
        if str(_attr(node, "node_id", "") or "")
    }
    graph_relations = tuple(getattr(behavior_graph, "relations", ()) or ()) if behavior_graph is not None else ()

    # When the caller has no explicit entrypoint symbol, prefer public
    # lifecycle methods grouped under the semantically matching class/module.
    # A helper such as ``get_passage_positional_encoding`` is never eligible
    # for this lexical lane, even when its docstring shares every target term.
    # If two distinct parent groups remain tied, keep the entry unresolved
    # instead of selecting by symbol-id sort order.
    entry_inference_status: str = (
        "explicit" if entry_ids else "unresolved_missing"
    )
    entry_inference_ambiguous = False
    if not entry_ids and by_id:
        lifecycle_symbols = [
            (symbol_id, symbol)
            for symbol_id, symbol in by_id.items()
            if _is_public_lifecycle_symbol(symbol)
        ]
        if lifecycle_symbols:
            grouped: dict[str, list[tuple[str, Any]]] = {}
            for symbol_id, symbol in lifecycle_symbols:
                grouped.setdefault(
                    _symbol_parent_key(symbol, by_id),
                    [],
                ).append((symbol_id, symbol))
            group_scores: list[tuple[int, str]] = []
            for parent_key, values in grouped.items():
                parent_context = (
                    _symbol_text(by_id[parent_key])
                    if parent_key in by_id
                    else parent_key
                )
                parent_overlap = len(scope_tokens(parent_context) & intent_tokens)
                member_overlap = max(
                    (len(scope_tokens(_symbol_text(symbol)) & intent_tokens) for _sid, symbol in values),
                    default=0,
                )
                topology_bonus = sum(
                    1 for _sid, symbol in values
                    if str(_attr(symbol, "kind", "") or "").casefold() == "method"
                )
                group_scores.append((parent_overlap * 5 + member_overlap * 2 + topology_bonus, parent_key))
            group_scores.sort(key=lambda item: (-item[0], item[1]))
            best_score = group_scores[0][0]
            best_groups = [key for score, key in group_scores if score == best_score]
            # With no intent signal, one lifecycle group is still a safe
            # boundary.  Several groups are genuinely ambiguous.
            if best_score > 0 and len(best_groups) == 1:
                entry_ids = tuple(
                    symbol_id
                    for symbol_id, _symbol in sorted(grouped[best_groups[0]], key=lambda item: item[0])
                )
                entry_inference_status = "lifecycle"
            elif best_score == 0 and len(group_scores) == 1:
                entry_ids = tuple(
                    symbol_id
                    for symbol_id, _symbol in sorted(grouped[best_groups[0]], key=lambda item: item[0])
                )
                entry_inference_status = "lifecycle"
            elif len(best_groups) > 1:
                entry_inference_ambiguous = True
                entry_inference_status = "unresolved_ambiguous"

    # Typed call-graph roots are a fallback after lifecycle detection.  They
    # are considered only when the lifecycle lane produced no choice.  The
    # graph direction is meaningful here; containment/alias edges are not
    # treated as executable ownership edges.
    if not entry_ids and not entry_inference_ambiguous and by_id and graph_relations:
        outgoing: dict[str, set[str]] = {}
        incoming: set[str] = set()
        for relation in graph_relations:
            if str(_attr(relation, "kind", "") or "") not in {"CALLS", "RETURNS_TO"}:
                continue
            source_node = graph_nodes.get(str(_attr(relation, "source_node_id", "") or ""))
            source_symbol = str(_attr(relation, "source_symbol_id", "") or "") or str(
                _attr(source_node, "symbol_id", "") or ""
            )
            target_node = graph_nodes.get(str(_attr(relation, "target_node_id", "") or ""))
            target_symbol = str(_attr(relation, "target_symbol_id", "") or "") or str(
                _attr(target_node, "symbol_id", "") or ""
            )
            if source_symbol in by_id and target_symbol in by_id and source_symbol != target_symbol:
                outgoing.setdefault(source_symbol, set()).add(target_symbol)
                incoming.add(target_symbol)
        roots = [symbol_id for symbol_id in outgoing if symbol_id not in incoming]
        root_scores: list[tuple[int, str]] = []
        for symbol_id in roots:
            symbol = by_id[symbol_id]
            path = str(_attr(symbol, "path", "") or "")
            if _EVALUATION_RE.search(path) or _COMPARAND_RE.search(path) or _CONFIG_RE.search(path):
                continue
            root_scores.append((
                entry_score(symbol, topology_bonus=len(outgoing[symbol_id])),
                symbol_id,
            ))
        root_scores.sort(key=lambda item: (-item[0], item[1]))
        if root_scores and (intent_tokens or len(root_scores) == 1):
            best_score = root_scores[0][0]
            tied = [symbol_id for score, symbol_id in root_scores if score == best_score]
            if len(tied) == 1:
                entry_ids = tuple(tied)
                entry_inference_status = "call_graph_root"
            else:
                entry_inference_ambiguous = True
                entry_inference_status = "unresolved_ambiguous"

    # Last-resort lexical selection is kept for fixtures that have no
    # lifecycle boundary (for example a single class-level symbol).  It is
    # disabled after an ambiguity so an unresolved owner cannot be guessed by
    # the old ``sorted()[:3]`` behaviour.
    if not entry_ids and not entry_inference_ambiguous and by_id and intent_tokens:
        scored: list[tuple[int, str]] = []
        for symbol_id, symbol in by_id.items():
            path = str(_attr(symbol, "path", "") or "")
            if _EVALUATION_RE.search(path) or _COMPARAND_RE.search(path) or _CONFIG_RE.search(path):
                continue
            kind = str(_attr(symbol, "kind", "") or "").casefold()
            if kind not in {"function", "method", "class", "module"}:
                continue
            leaf_name = str(_attr(symbol, "qualified_name", "") or "").split(".")[-1].casefold()
            if leaf_name.startswith(_ENTRY_HELPER_PREFIXES):
                # Helper names are never promoted solely by lexical overlap.
                continue
            score = entry_score(symbol)
            if score > 0:
                scored.append((score, symbol_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        if scored and scored[0][0] >= 2:
            best_score = scored[0][0]
            tied = [symbol_id for score, symbol_id in scored if score == best_score]
            if len(tied) == 1:
                entry_ids = tuple(tied)
                entry_inference_status = "lexical"
            else:
                entry_inference_ambiguous = True
                entry_inference_status = "unresolved_ambiguous"

    reachable: set[str] = set(entry_ids)
    graph = behavior_graph
    if graph is not None:
        changed = True
        while changed:
            changed = False
            for relation in graph_relations:
                if str(_attr(relation, "kind", "") or "") not in _OWNERSHIP_GRAPH_RELATIONS:
                    continue
                source_node = str(_attr(relation, "source_node_id", "") or "")
                target_node = str(_attr(relation, "target_node_id", "") or "")
                source_symbol = str(_attr(relation, "source_symbol_id", "") or "") or str(
                    _attr(graph_nodes.get(source_node), "symbol_id", "") or ""
                )
                target_symbol = str(_attr(relation, "target_symbol_id", "") or "") or str(
                    _attr(graph_nodes.get(target_node), "symbol_id", "") or ""
                )
                if source_symbol in reachable and target_symbol and target_symbol not in reachable:
                    reachable.add(target_symbol)
                    changed = True

    roles: dict[str, set[ImplementationOwnershipRoleV1]] = {item: set() for item in by_id}
    for symbol_id in entry_ids:
        if symbol_id in by_id:
            roles[symbol_id].add("target_core")
    for symbol_id in reachable - set(entry_ids):
        if symbol_id in by_id:
            roles[symbol_id].add("target_dependency")

    for symbol_id, symbol in by_id.items():
        text = _symbol_text(symbol)
        path = str(_attr(symbol, "path", "") or "")
        kind = classify_source_kind(path)
        if kind in {"vendor", "generated", "dataset_or_checkpoint", "paper_or_draft", "submodule"}:
            roles[symbol_id] = {"unknown"}
            continue
        qname = str(_attr(symbol, "qualified_name", "") or "")
        overlap = len(scope_tokens(text) & intent_tokens)
        # Helper names (``get_``/``set_``/``load_``/``save_``/... and private
        # methods) never become target core from lexical overlap alone.  They
        # may still be target dependencies when the typed graph proves the
        # entry calls them; otherwise they stay audit-only ``unknown``.
        leaf_name = qname.rsplit(".", 1)[-1].casefold()
        is_helper = leaf_name.startswith(_ENTRY_HELPER_PREFIXES)
        if overlap >= 2 and not is_helper and not _COMPARAND_RE.search(path):
            roles[symbol_id] = {"target_core"}
            continue
        if _EVALUATION_RE.search(path) or _EVALUATION_RE.search(qname):
            roles[symbol_id] = {"evaluation"}
            continue
        if _COMPARAND_RE.search(path) or _COMPARAND_RE.search(qname):
            # A reachable symbol is still a target dependency when the graph
            # proves it is called by the target.  Otherwise it is audit-only.
            if symbol_id not in reachable:
                roles[symbol_id] = {"comparand"}
            continue
        if _CONFIG_RE.search(path) or _CONFIG_RE.search(qname):
            if symbol_id not in reachable and symbol_id not in entry_ids:
                roles[symbol_id] = {"configuration"}
                continue
        if not roles[symbol_id]:
            if overlap >= 2 and not is_helper:
                roles[symbol_id] = {"target_core"}
            elif overlap == 1:
                roles[symbol_id] = {"unknown"}
            else:
                roles[symbol_id] = {"unknown"}

    # Keep explicit entry roots authoritative even if a generic filename
    # heuristic resembles an evaluation/baseline path.
    for symbol_id in entry_ids:
        if symbol_id in by_id:
            roles[symbol_id] = {"target_core"}
    groups: dict[str, list[str]] = {
        "target_core": [], "target_dependency": [], "comparand": [],
        "evaluation": [], "configuration": [], "unknown": [],
    }
    for symbol_id in sorted(by_id):
        role = sorted(roles[symbol_id] or {"unknown"})[0]
        groups[role].append(symbol_id)
    confidence = 0.0
    if groups["target_core"]:
        confidence = min(1.0, 0.55 + 0.1 * min(4, len(groups["target_core"])))
        if groups["target_dependency"]:
            confidence = min(1.0, confidence + 0.15)
    return ImplementationScopeV1(
        target_entry_symbol_ids=entry_ids,
        target_core_symbol_ids=tuple(groups["target_core"]),
        target_dependency_symbol_ids=tuple(groups["target_dependency"]),
        comparand_symbol_ids=tuple(groups["comparand"]),
        evaluation_symbol_ids=tuple(groups["evaluation"]),
        configuration_symbol_ids=tuple(groups["configuration"]),
        unknown_symbol_ids=tuple(groups["unknown"]),
        ownership_evidence_refs=tuple(dict.fromkeys(str(item).strip() for item in evidence_refs if str(item).strip())),
        entry_inference_status=entry_inference_status,
        confidence=confidence,
    )


def ownership_rank(role: str) -> int:
    """Stable ranking used before semantic relevance scoring."""

    return {
        "target_core": 500,
        "target_dependency": 350,
        "unknown": 100,
        "comparand": 0,
        "evaluation": 0,
        "configuration": 150,
    }.get(str(role), 0)


def scope_role_for_candidate(
    scope: ImplementationScopeV1 | None,
    candidate: str,
    *,
    behavior_graph: Any | None = None,
    symbols: Iterable[Any] = (),
    source_manifest: Any | None = None,
) -> ImplementationOwnershipRoleV1:
    """Resolve a heterogeneous candidate reference before role lookup."""

    if scope is None:
        return "unknown"
    raw = str(candidate or "").strip()
    direct = scope.role_for(raw)
    if direct != "unknown":
        return direct

    if symbols:
        symbols_by_id = {str(_attr(s, "symbol_id", "") or ""): s for s in symbols}
        canon = _canonical_symbol_id(raw, symbols_by_id)
        if canon and canon != raw:
            role = scope.role_for(canon)
            if role != "unknown":
                return role

    if behavior_graph is not None:
        for node in getattr(behavior_graph, "nodes", ()) or ():
            if _node_matches_candidate(node, raw, symbols=symbols):
                role = scope.role_for(str(_attr(node, "symbol_id", "") or ""))
                if role != "unknown":
                    return role

    location = _candidate_location(raw)
    if location is not None:
        path = location[0]
        if source_manifest is not None:
            entry = getattr(source_manifest, "entry_for", lambda p: None)(path)
            if entry is not None and getattr(entry, "ownership_role", "unknown") != "unknown":
                return entry.ownership_role
        kind = classify_source_kind(path)
        if kind in {"vendor", "submodule", "generated", "dataset_or_checkpoint"}:
            return "unknown"
        if _EVALUATION_RE.search(path):
            return "evaluation"
        if _COMPARAND_RE.search(path):
            return "comparand"
        if _CONFIG_RE.search(path):
            return "configuration"
        if kind == "first_party_executable":
            return "target_core"

    return direct


def _candidate_context(
    candidate: str,
    behavior_graph: Any | None,
    *,
    symbols: Iterable[Any] = (),
) -> set[str]:
    """Return semantic context for a candidate without reading source text."""

    values: list[set[str]] = [_tokens(candidate)]
    if behavior_graph is not None:
        for node in getattr(behavior_graph, "nodes", ()) or ():
            same = _node_matches_candidate(node, candidate, symbols=symbols)
            if same:
                values.append(_tokens(" ".join(
                    str(_attr(node, attr, "") or "")
                    for attr in ("predicate", "operands", "result", "guard", "shape_or_type_hints")
                )))
    return set().union(*values)


def _symbol_line_range(
    candidate: str,
    symbols: Iterable[Any],
) -> tuple[str, int, int] | None:
    """Resolve a ``symbol:<path>:<name>:<line>`` candidate to its full span.

    Search results carry the *declaration* line of a symbol, while behavior
    nodes are statement-level single-line spans after that declaration.  A
    containment test (node span must contain the declaration line) can never
    match, which silently left every candidate unbound from the behavior
    graph.  Resolving the candidate to ``[start_line, end_line]`` lets a node
    match when it lies inside the declared symbol body.
    """

    binding = resolve_candidate_binding(
        candidate,
        symbols=tuple(symbols),
        mode="range",
    )
    if binding.ambiguous or len(binding.symbol_ranges) != 1:
        return None
    return binding.symbol_ranges[0]


def _node_matches_candidate(
    node: Any,
    candidate: str,
    *,
    symbols: Iterable[Any] = (),
) -> bool:
    """Match a behavior node to a stable id or typed location candidate."""

    binding = resolve_candidate_binding(
        candidate,
        symbols=tuple(symbols),
        behavior_nodes=(node,),
        mode="match",
    )
    return str(_attr(node, "node_id", "") or "") in binding.behavior_node_ids


def _candidate_packet_refs(
    compiled: Any | None,
    *,
    candidate_spans: set[str],
    location: tuple[str, str, int] | None,
) -> tuple[tuple[str, ...], set[str]]:
    """Return packets whose exact spans belong to one candidate."""

    if compiled is None or getattr(compiled, "packet_set", None) is None:
        return (), set()
    packet_ids: list[str] = []
    packet_spans: set[str] = set()
    for packet in getattr(compiled.packet_set, "packets", ()) or ():
        spans = tuple(
            str(value)
            for value in (
                *(getattr(packet, "anchor_span_ids", ()) or ()),
                *(getattr(packet, "relation_span_ids", ()) or ()),
                *(getattr(packet, "semantic_span_ids", ()) or ()),
            )
        )
        matched = bool(candidate_spans.intersection(spans)) or any(
            source_intervals_overlap(left, right)
            for left in (
                _span_interval(value) for value in candidate_spans
            )
            for right in (_span_interval(value) for value in spans)
        )
        if not matched and location is not None:
            path, name, line = location
            for span in getattr(packet, "spans", ()) or ():
                if (
                    str(getattr(span, "path", "") or "") == path
                    and str(getattr(span, "symbol", "") or "").split(".")[-1]
                    in {name, name.split(".")[-1]}
                    and int(getattr(span, "line_start", 0) or 0)
                    <= line
                    <= int(getattr(span, "line_end", 0) or 0)
                ):
                    matched = True
                    break
        if matched:
            packet_id = str(getattr(packet, "packet_id", "") or "")
            if packet_id:
                packet_ids.append(packet_id)
                packet_spans.update(spans)
    return tuple(dict.fromkeys(packet_ids)), packet_spans


def _candidate_fact_refs(
    compiled: Any | None,
    *,
    candidate_spans: set[str],
) -> tuple[tuple[str, ...], set[str]]:
    if compiled is None or getattr(compiled, "fact_set", None) is None:
        return (), set()
    fact_ids: list[str] = []
    selected_fact_ids: set[str] = set()
    for fact in getattr(compiled.fact_set, "facts", ()) or ():
        spans = set(
            str(value)
            for value in (
                *(getattr(fact, "direct_span_ids", ()) or ()),
                *(getattr(fact, "relation_span_ids", ()) or ()),
            )
        )
        matched = bool(candidate_spans.intersection(spans)) or any(
            source_intervals_overlap(left, right)
            for left in (_span_interval(value) for value in candidate_spans)
            for right in (_span_interval(value) for value in spans)
        )
        if not candidate_spans or matched:
            fact_id = str(getattr(fact, "fact_id", "") or "")
            if fact_id:
                fact_ids.append(fact_id)
                selected_fact_ids.add(fact_id)
    return tuple(dict.fromkeys(fact_ids)), selected_fact_ids


def _candidate_claim_refs(
    compiled: Any | None,
    fact_ids: set[str],
) -> tuple[str, ...]:
    if compiled is None or getattr(compiled, "claim_set", None) is None:
        return ()
    claims: list[str] = []
    for claim in getattr(compiled.claim_set, "claims", ()) or ():
        claim_facts = set(str(value) for value in getattr(claim, "fact_ids", ()) or ())
        if fact_ids.intersection(claim_facts):
            claim_id = str(getattr(claim, "claim_id", "") or "")
            if claim_id:
                claims.append(claim_id)
    return tuple(dict.fromkeys(claims))


def seed_child_candidates_from_parents(
    agenda_items: Iterable[Any],
    *,
    behavior_graph: Any | None = None,
    scope: ImplementationScopeV1 | None = None,
    symbols: Iterable[Any] = (),
    max_candidates: int = 8,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Seed empty child obligations from semantically related parent candidates.

    Candidate sharing is intentionally conservative.  A child receives a
    parent candidate only when its author/typed-target terms overlap the
    candidate context, or when the behavior graph contains a relation between
    the candidate's node and a node already attached to the child.  Ownership
    is checked before semantic overlap so a baseline cannot seed a target
    obligation merely because it uses the same API name.
    """

    items = tuple(agenda_items)
    changed: list[tuple[str, tuple[str, ...]]] = []
    node_by_symbol: dict[str, set[str]] = {}
    if behavior_graph is not None:
        for node in getattr(behavior_graph, "nodes", ()) or ():
            node_by_symbol.setdefault(str(_attr(node, "symbol_id", "") or ""), set()).add(
                str(_attr(node, "node_id", "") or "")
            )
    for child in items:
        if getattr(child, "status", "pending") in {"supported", "explicit_gap", "blocked"}:
            continue
        if getattr(child, "candidate_symbol_ids", None):
            continue
        child_text = " ".join([
            str(getattr(child, "author_text", "") or ""),
            " ".join(
                str(value or "")
                for target in getattr(child, "typed_behavior_targets", ()) or ()
                for value in (
                    getattr(target, "role", ""),
                    *(getattr(target, "search_terms", ()) or ()),
                    *(getattr(target, "inputs", ()) or ()),
                    *(getattr(target, "transformations", ()) or ()),
                    *(getattr(target, "outputs", ()) or ()),
                )
            ),
        ])
        child_terms = _tokens(child_text)
        candidates: list[tuple[int, str]] = []
        for parent in items:
            if parent is child:
                continue
            for candidate in getattr(parent, "candidate_symbol_ids", ()) or ():
                canonical = str(candidate).strip()
                role = (
                    scope_role_for_candidate(scope, canonical, behavior_graph=behavior_graph)
                    if scope
                    else "unknown"
                )
                if role in {"comparand", "evaluation", "configuration"}:
                    continue
                context = _candidate_context(
                    canonical, behavior_graph, symbols=symbols
                )
                parent_terms = _tokens(getattr(parent, "author_text", ""))
                overlap = len(child_terms & (context | parent_terms))
                if overlap <= 0:
                    continue
                if behavior_graph is not None:
                    # A lexical match is insufficient for mainline/child
                    # propagation.  Require a typed graph relation from the
                    # parent candidate's node to a child-attached node (or a
                    # typed target hint that resolves to the child's terms).
                    parent_nodes = {
                        str(_attr(node, "node_id", "") or "")
                        for node in getattr(behavior_graph, "nodes", ()) or ()
                        if _node_matches_candidate(
                            node, canonical, symbols=symbols
                        )
                    }
                    child_nodes = {
                        str(value).strip()
                        for value in (getattr(child, "candidate_behavior_node_ids", ()) or ())
                        if str(value).strip()
                    }
                    connected = False
                    for relation in getattr(behavior_graph, "relations", ()) or ():
                        if str(_attr(relation, "kind", "") or "") not in _OWNERSHIP_GRAPH_RELATIONS:
                            continue
                        endpoints = {
                            str(_attr(relation, "source_node_id", "") or ""),
                            str(_attr(relation, "target_node_id", "") or ""),
                        }
                        if parent_nodes.intersection(endpoints) and child_nodes.intersection(endpoints):
                            connected = True
                            break
                        target_hint = " ".join(
                            str(_attr(relation, name, "") or "")
                            for name in ("target_hint", "target_symbol_id")
                        )
                        if parent_nodes.intersection(endpoints) and _tokens(target_hint) & child_terms:
                            connected = True
                            break
                    if not connected:
                        continue
                candidates.append((overlap * 100 + ownership_rank(role), canonical))
        candidates.sort(key=lambda item: (-item[0], item[1]))
        selected = tuple(dict.fromkeys(item[1] for item in candidates))[:max_candidates]
        if selected:
            child.candidate_symbol_ids.extend(selected)
            changed.append((str(getattr(child, "obligation_id", "") or ""), selected))
    return tuple(changed)


def build_candidate_acquisition_ledger(
    *,
    scope: ImplementationScopeV1,
    agenda_items: Iterable[Any] = (),
    observations: Iterable[Any] = (),
    behavior_graph: Any | None = None,
    compiled_by_obligation: Mapping[str, Any] | None = None,
    symbols: Iterable[Any] = (),
    source_manifest: Any | None = None,
    repo_snapshot_id: str = "",
    project_tree_hash: str = "",
) -> CandidateAcquisitionLedgerV1:
    """Materialize a deterministic acquisition ledger from loop artifacts."""

    compiled_by_obligation = compiled_by_obligation or {}
    observation_items = tuple(observations)
    # ``observations`` is intentionally cumulative.  Do not index only by
    # the current obligation: a candidate discovered while a parent or
    # mainline question was active may later be propagated to a child, and a
    # supervisor obligation switch must not erase its read provenance.
    nodes = tuple(getattr(behavior_graph, "nodes", ()) or ()) if behavior_graph is not None else ()
    symbol_items = tuple(symbols)
    records: list[CandidateAcquisitionRecordV1] = []
    for agenda in agenda_items:
        obligation_id = str(getattr(agenda, "obligation_id", "") or "")
        for rank, candidate in enumerate(getattr(agenda, "candidate_symbol_ids", ()) or (), start=1):
            candidate_id = str(candidate).strip()
            if not candidate_id:
                continue
            # Search/read refs may have either a location ref or the stable
            # symbol id.  Match exact refs first, then location/span evidence.
            location = _candidate_location(candidate_id)
            matched_obs: list[Any] = []
            for observation in observation_items:
                refs = tuple(str(ref) for ref in getattr(observation, "result_refs", ()) or ())
                notebook = getattr(observation, "notebook", None)
                refs += tuple(
                    str(ref)
                    for ref in getattr(notebook, "discovered_symbols", ()) or ()
                )
                spans = tuple(str(ref) for ref in getattr(observation, "exact_span_ids", ()) or ())
                exact = any(
                    ref == candidate_id
                    or ref.removeprefix("symbol:") == candidate_id.removeprefix("symbol:")
                    for ref in refs
                )
                located = False
                if location is not None and spans:
                    path, name, line = location
                    candidate_interval = (path, line, line)
                    located = any(
                        source_intervals_overlap(candidate_interval, parsed)
                        for parsed in (_span_interval(span) for span in spans)
                    )
                if exact or located:
                    matched_obs.append(observation)
            read_obs = [item for item in matched_obs if item.tool_name in {"read_symbol", "read_code_span"} and item.status == "success"]
            binding = resolve_candidate_binding(
                candidate_id,
                symbols=symbol_items,
                behavior_nodes=nodes,
                mode="acquisition",
            )
            compatibility_identity = (
                binding.rejection_code == "symbol_index_not_available_to_compile"
                and bool(binding.behavior_node_ids)
                and any(
                    str(_attr(node, "symbol_id", "") or "")
                    in set(binding.canonical_symbol_ids)
                    for node in nodes
                    if str(_attr(node, "node_id", "") or "")
                    in set(binding.behavior_node_ids)
                )
            )
            identity_rejection = (
                "candidate_identity_ambiguous"
                if binding.ambiguous
                else (
                    binding.rejection_code
                    if binding.rejection_code and not compatibility_identity
                    else ""
                )
            )
            # Do not let a declaration-line/location fallback produce packet,
            # fact, or claim ownership after identity resolution failed.  The
            # typed rejection remains visible on the acquisition record and
            # keeps the Research obligation open for the repository-index
            # owner.
            symbol_matches = [] if identity_rejection else [
                node for node in nodes
                if str(_attr(node, "symbol_id", "") or "") == candidate_id.removeprefix("symbol:")
                or _node_matches_candidate(node, candidate_id, symbols=symbol_items)
            ]
            compiled = compiled_by_obligation.get(obligation_id)
            candidate_spans = {
                str(_attr(node, "source_span_id", "") or "") for node in symbol_matches
            }
            if identity_rejection:
                packet_ids, packet_span_ids = (), set()
                fact_ids, fact_set_ids = (), set()
                claim_ids = ()
            else:
                packet_ids, packet_span_ids = _candidate_packet_refs(
                    compiled, candidate_spans=candidate_spans, location=location
                )
                fact_ids, fact_set_ids = _candidate_fact_refs(
                    compiled, candidate_spans=packet_span_ids or candidate_spans
                )
                claim_ids = _candidate_claim_refs(compiled, fact_set_ids)
            role = scope_role_for_candidate(
                scope,
                candidate_id,
                behavior_graph=behavior_graph,
                symbols=symbols,
                source_manifest=source_manifest,
            )
            terminal_status = "discovered"
            rejection_reason = ""
            if identity_rejection:
                # Keep the acquisition status non-terminal: this is a typed
                # data-plane/binding failure, not evidence that the candidate
                # is absent from the repository.
                rejection_reason = identity_rejection
            elif role in {"comparand", "evaluation"}:
                terminal_status = "explicitly_rejected"
                rejection_reason = "ownership_role_not_target_method"
            elif packet_ids and fact_ids and claim_ids and read_obs and symbol_matches:
                terminal_status = "acquired_and_compiled"
            elif packet_ids:
                terminal_status = "packet_built"
            elif read_obs and symbol_matches:
                terminal_status = "read"
            elif symbol_matches:
                terminal_status = "behavior_built"
            if identity_rejection:
                resolution_status = None
                rejection_code = identity_rejection
            elif role in {"comparand", "evaluation", "configuration"}:
                resolution_status = "out_of_scope"
                rejection_code = "ownership_role_not_target_method"
            elif terminal_status == "acquired_and_compiled":
                resolution_status = "implemented_exact"
                rejection_code = ""
            elif terminal_status in {"packet_built", "read", "behavior_built"}:
                resolution_status = "implemented_partial"
                rejection_code = "evidence_chain_incomplete"
            else:
                resolution_status = "not_found_after_bounded_search"
                rejection_code = "bounded_search_not_closed"
            records.append(CandidateAcquisitionRecordV1(
                obligation_id=obligation_id,
                candidate_symbol_id=candidate_id,
                ownership_role=role,
                discovered_rank=rank,
                search_observation_refs=tuple(dict.fromkeys(
                    f"{getattr(item, 'observation_id', '')}" for item in matched_obs
                    if getattr(item, "tool_name", "") in {"search_symbols", "search_code", "find_entrypoints"}
                )),
                read_status="success" if read_obs else "not_attempted",
                read_observation_refs=tuple(dict.fromkeys(str(getattr(item, "observation_id", "") or "") for item in read_obs)),
                behavior_graph_status="built" if symbol_matches else "not_attempted",
                behavior_node_ids=tuple(dict.fromkeys(str(getattr(item, "node_id", "") or "") for item in symbol_matches if str(getattr(item, "node_id", "") or ""))),
                packet_status="compiled" if packet_ids else "not_attempted",
                packet_ids=packet_ids,
                fact_ids=fact_ids,
                claim_ids=claim_ids if role in {"target_core", "target_dependency", "unknown"} else (),
                terminal_status=terminal_status,
                rejection_reason=rejection_reason,
                resolution_status=resolution_status,
                rejection_code=rejection_code,
            ))
    # Once a target-owned candidate has traversed the full chain, remaining
    # alternatives for the same obligation are closed explicitly as
    # superseded.  This preserves discovery provenance while preventing a
    # terminal obligation from hiding an unread sibling candidate.  The
    # stronger candidate decision is deterministic (first acquired record in
    # discovery order) and never applies to comparand/evaluation records.
    by_obligation: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        by_obligation.setdefault(record.obligation_id, []).append(index)
    for obligation_id, indexes in by_obligation.items():
        acquired = any(
            records[index].terminal_status == "acquired_and_compiled"
            and records[index].ownership_role in {"target_core", "target_dependency", "unknown"}
            for index in indexes
        )
        if not acquired:
            continue
        for index in indexes:
            record = records[index]
            if record.terminal or record.ownership_role in {"comparand", "evaluation"}:
                continue
            records[index] = record.model_copy(update={
                "terminal_status": "superseded",
                "rejection_reason": "alternative_candidate_not_selected_after_acquisition",
                "resolution_status": "inactive_alternative",
                "rejection_code": "alternative_candidate_not_selected_after_acquisition",
            })
    return CandidateAcquisitionLedgerV1(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        records=tuple(records),
    )


__all__ = [
    "build_candidate_acquisition_ledger",
    "infer_implementation_scope",
    "ownership_rank",
    "scope_role_for_candidate",
    "seed_child_candidates_from_parents",
]
