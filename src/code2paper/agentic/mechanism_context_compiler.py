"""Compile research artifacts into the unified mechanism context.

The compiler deliberately has two products:

* :class:`MechanismEvidenceClosureV1` is a lossless, source-bound inventory;
* :class:`MechanismContextV1` annotates that inventory for paper planning.

The paper annotation is allowed to classify or group operations, but it is
never allowed to delete an operation from the closure.  In particular, this
module does not use paragraph ids, project names, or function-name folklore to
decide whether a path is active.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from code2paper.agentic.mechanism_context_models import (
    ActivePathStatus,
    ClaimKind,
    DetailImportance,
    DetailRole,
    DetailWitnessAtomV1,
    EvidenceAuthority,
    EvidenceOperationV1,
    MechanismContextSetV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEdgeV1,
    MechanismEvidenceClosureV1,
    MechanismSeedV1,
    PublicationPolicy,
    SharedDetailRefV1,
    SourceOperationDispositionV1,
    WitnessAtomKind,
    canonical_json_bytes,
    sha256_digest,
)
from code2paper.agentic.source_inventory import normalize_source_path


_ACTIVE_STATUSES = frozenset({"active_default", "active_selected", "conditional"})
_INACTIVE_STATUSES = frozenset({"inactive_default", "unreachable"})
# Generic semantic predicate families used only to prove that a fact-view
# operation and a graph-view operation are the *same* operation (e.g. the
# frozen ``calls`` fact and the adapter ``CALL`` node).  A family match alone
# never merges: correspondence additionally requires one exact shared span,
# one symbol scope, and identical operands/result (see
# ``_proven_same_operation``).  ``calls``/``CALL`` is the reference mapping.
_PREDICATE_FAMILIES: tuple[frozenset[str], ...] = (
    frozenset({"calls", "call", "invokes", "invoke", "dispatches", "dispatch"}),
    frozenset({"computes", "compute", "projects", "project", "attends", "attend"}),
    frozenset({"loads", "load", "reads", "read", "fetches", "fetch"}),
    frozenset({"writes", "write", "stores", "store", "emits", "emit"}),
    frozenset({"concatenates", "concatenate", "concat", "cat", "stacks", "stack"}),
    frozenset({"branches", "branch", "compares", "compare", "selects", "select", "select_top_k"}),
    frozenset({"configured_by", "configures", "configure"}),
    frozenset({"transforms", "transform", "converts", "convert", "maps", "map"}),
)
_GRAPH_RELATIONS = frozenset({
    "CONTAINS", "NEXT_CONTROL", "CALLS", "RETURNS_TO", "DATA_DEPENDS_ON",
    "CONTROL_DEPENDS_ON", "TRUE_BRANCH", "FALSE_BRANCH", "READS_FROM",
    "WRITES_TO", "ALIAS_OF", "CONFIGURED_BY", "IMPLEMENTS", "OVERRIDES",
})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Mapping):
        return ()
    try:
        return tuple(dict.fromkeys(
            item for item in (_text(v) for v in value) if item
        ))
    except TypeError:
        item = _text(value)
        return (item,) if item else ()


def _get(value: Any, name: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _dump(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        result = value.model_dump(mode="json")
        return result if isinstance(result, dict) else {}
    return {}


def _items(value: Any, collection_name: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    collection = _get(value, collection_name, None)
    if collection is None:
        aliases = {
            "claims": ("code_claims", "configurations", "bindings", "items"),
            "packets": ("evidence_packets", "items"),
            "facts": ("code_facts", "items"),
            "equations": ("equation_claims", "items"),
        }.get(collection_name, ())
        for alias in aliases:
            collection = _get(value, alias, None)
            if collection is not None:
                break
    if collection is not None:
        if isinstance(collection, Mapping):
            return tuple(collection.values())
        return tuple(collection or ())
    if isinstance(value, Mapping):
        # A single typed record is a useful compatibility input; arbitrary
        # mappings without an identity are not treated as a collection.
        identity_keys = (
            "fact_id", "claim_id", "equation_id", "packet_id",
            "configuration_id", "facet_id", "brief_id", "candidate_id",
        )
        if any(str(key) in value for key in identity_keys):
            return (value,)
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(value)
    return ()


def _source_digest(value: Any) -> str:
    existing = _text(_get(value, "content_digest"))
    if existing:
        return existing
    if value is None:
        return ""
    try:
        return sha256_digest(canonical_json_bytes(value))
    except TypeError:
        # Never digest ``str(object)``: a provider without a declared identity
        # would then hash its memory address and make the closure, archive and
        # downstream page/plan digests change on every process.
        fallback_identity = {
            "provider_type": (
                f"{type(value).__module__}.{type(value).__qualname__}"
            ),
            "repo_snapshot_id": _text(
                _get(value, "repo_snapshot_id") or _get(value, "snapshot_id")
            ),
            "project_tree_hash": _text(_get(value, "project_tree_hash")),
        }
        return sha256_digest(canonical_json_bytes(fallback_identity))


def _canonical_mechanism_id(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    # Legacy section/paragraph labels are input aliases, never canonical ids.
    raw = re.sub(r"^(section_|paragraph_|consumer_)+", "", raw)
    return raw if raw.startswith("mech_") else f"mech_{raw}"


def _span_order(span_id: str) -> tuple[str, int, int, str]:
    match = re.search(r"^span:(.*):(\d+):(\d+)$", span_id)
    if not match:
        return (span_id, 10**9, 10**9, span_id)
    return (match.group(1), int(match.group(2)), int(match.group(3)), span_id)


def _normalize_guard_text(value: Any) -> str:
    """Normalize a guard/condition string without changing its logic.

    Whitespace collapsing is the only transformation: equivalence is never
    inferred from keyword overlap or substring containment.
    """
    return " ".join(str(value or "").split())


def _fact_values(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Mapping):
        return ()
    try:
        return tuple(item for item in (_text(v) for v in value) if item)
    except TypeError:
        item = _text(value)
        return (item,) if item else ()


class DefinitionResolver:
    """Resolve exact symbols and bounded source bodies from a snapshot.

    ``source_provider`` may be a ``{path: text}`` mapping, a snapshot-like
    object exposing ``files``/``read_file``/``read_text``, or the existing
    span callback.  Failed reads remain empty; they never become invented
    evidence.
    """

    def __init__(
        self,
        symbol_index: Any | None = None,
        source_provider: Callable[[str, int, int], str] | Any | None = None,
        max_call_depth: int = 2,
        max_callees: int = 6,
        max_lines_per_def: int = 160,
    ) -> None:
        self.symbol_index = symbol_index
        self.source_provider = source_provider
        self.max_call_depth = max_call_depth
        self.max_callees = max_callees
        self.max_lines_per_def = max_lines_per_def

    def _symbols(self) -> tuple[Any, ...]:
        return tuple(_get(self.symbol_index, "symbols", ()) or ())

    def resolve_symbol(self, target: str, current_path: str = "") -> Any | None:
        target = _text(target)
        if not target:
            return None
        symbols = self._symbols()
        for symbol in symbols:
            if _text(_get(symbol, "symbol_id")) == target:
                return symbol
        exact = [
            symbol for symbol in symbols
            if (
                (current_path and _text(_get(symbol, "path")) == current_path
                 and _text(_get(symbol, "qualified_name")) == target)
                or _text(_get(symbol, "qualified_name")) == target
                or f"{_text(_get(symbol, 'path'))}::{_text(_get(symbol, 'qualified_name'))}" == target
            )
        ]
        if len(exact) == 1:
            return exact[0]
        tail = [
            symbol for symbol in symbols
            if _text(_get(symbol, "qualified_name")).endswith(f".{target}")
        ]
        return tail[0] if len(tail) == 1 else None

    def read_file(self, path: str) -> str:
        provider = self.source_provider
        if not provider or not path:
            return ""
        try:
            if isinstance(provider, Mapping):
                return _text(provider.get(path, ""))
            files = _get(provider, "files", None)
            if isinstance(files, Mapping) and path in files:
                return _text(files[path])
            root = _text(_get(provider, "project_root"))
            if root:
                return Path(root, path).read_text(encoding="utf-8")
            for method_name in ("read_file", "read_text", "source_for_path"):
                method = getattr(provider, method_name, None)
                if callable(method):
                    result = method(path)
                    if result is not None:
                        return _text(result)
        except Exception:
            return ""
        return ""

    def read_span(self, path: str, start: int, end: int) -> str:
        provider = self.source_provider
        if not provider:
            return ""
        try:
            if callable(provider) and not isinstance(provider, Mapping):
                return _text(provider(path, start, end))
            for method_name in ("read_span", "read_file_lines"):
                method = getattr(provider, method_name, None)
                if callable(method):
                    return _text(method(path, start, end))
            source = self.read_file(path)
            if source:
                return "\n".join(source.splitlines()[max(0, start - 1):end])
        except Exception:
            return ""
        return ""

    def read_definition_body(self, symbol: Any) -> str:
        if not symbol:
            return ""
        path = _text(_get(symbol, "path"))
        start = int(_get(symbol, "start_line", 1) or 1)
        end = int(_get(symbol, "end_line", start) or start)
        end = min(end, start + self.max_lines_per_def - 1)
        return self.read_span(path, start, end)

    def read_span_id(self, span_id: str) -> str:
        match = re.match(r"^span:(.*):(\d+):(\d+)$", _text(span_id))
        if not match:
            return ""
        return self.read_span(match.group(1), int(match.group(2)), int(match.group(3)))


def _override_status(value: Any) -> ActivePathStatus | None:
    if isinstance(value, bool):
        return "active_selected" if value else "inactive_default"
    text = _text(value)
    return text if text in {
        "active_default", "active_selected", "conditional", "inactive_default",
        "unreachable", "unknown",
    } else None  # type: ignore[return-value]


def _matching_override(
    *,
    symbol_name: str,
    operation_id: str,
    source_span_id: str,
    author_config_overrides: Mapping[str, Any] | None,
) -> ActivePathStatus | None:
    if not author_config_overrides:
        return None
    candidates = (operation_id, symbol_name, source_span_id)
    for key in candidates:
        if key and key in author_config_overrides:
            raw = author_config_overrides[key]
            if isinstance(raw, Mapping):
                raw = raw.get("active_path_status", raw.get("status", raw.get("active")))
            status = _override_status(raw)
            if status:
                return status
    for key in ("active_path_status", "status", "active"):
        if key in author_config_overrides:
            status = _override_status(author_config_overrides[key])
            if status:
                return status
    return None


def resolve_active_path_status(
    *,
    symbol_name: str,
    guard: str = "",
    config_bindings: Sequence[Mapping[str, Any]] = (),
    author_config_overrides: Mapping[str, Any] | None = None,
    default_branch: str = "active_default",
    reachable: bool | None = None,
    operation_id: str = "",
    source_span_id: str = "",
    explicit_status: str = "",
) -> ActivePathStatus:
    """Resolve active-path status with strict evidence and symbol precedence.

    Precedence is explicit author override, resolved configuration, graph
    reachability, guard, then canonical symbol patterns and default branch.
    """

    override = _matching_override(
        symbol_name=symbol_name,
        operation_id=operation_id,
        source_span_id=source_span_id,
        author_config_overrides=author_config_overrides,
    )
    if override:
        return override
    explicit = _override_status(explicit_status)
    if explicit:
        return explicit

    matched: list[Mapping[str, Any]] = []
    for binding in config_bindings:
        identifiers = set(_ids(
            (_get(binding, "configuration_id"), _get(binding, "key"),
             _get(binding, "operation_id"), _get(binding, "symbol_id"),
             _get(binding, "source_span_id"))
        ))
        spans = set(_ids(_get(binding, "definition_span_ids", ()))) | set(
            _ids(_get(binding, "entrypoint_span_ids", ()))
        )
        symbols = set(_ids(_get(binding, "symbol_ids", ()))) | set(
            _ids(_get(binding, "bound_symbol_ids", ()))
        )
        if (
            operation_id in identifiers or symbol_name in identifiers
            or source_span_id in identifiers or source_span_id in spans
            or symbol_name in symbols
            or not (operation_id or symbol_name or source_span_id)
        ):
            matched.append(binding)
    for binding in matched:
        state = _text(_get(binding, "state"))
        if state == "unresolved":
            return "unknown"
        if state in {"unreachable", "inactive"} or _get(binding, "active", None) is False:
            return "unreachable" if state == "unreachable" else "inactive_default"
        configured = _override_status(_get(binding, "active_path_status"))
        if configured:
            return configured
        if _get(binding, "active", None) is True or state in {"actual", "selected", "resolved"}:
            return "conditional" if guard or _ids(_get(binding, "conditions", ())) else "active_selected"

    if reachable is False:
        return "unreachable"
    if reachable is True:
        return "conditional" if guard else (
            default_branch if default_branch in {"active_default", "active_selected"}
            else "active_default"
        )  # type: ignore[return-value]
    if guard:
        return "conditional"

    s_lower = symbol_name.lower()
    if any(k in s_lower for k in ("debug", "test_", "logging", "legacy_")):
        return "unreachable"

    if any(k in s_lower for k in ("vectorized", "fast_", "alternative", "optional")):
        if author_config_overrides and any(
            k in str(author_config_overrides).lower() for k in ("vectorized", "fast")
        ):
            return "active_selected"
        return "inactive_default"

    return default_branch if default_branch in {
        "active_default", "active_selected", "conditional", "inactive_default",
        "unreachable", "unknown",
    } else "unknown"  # type: ignore[return-value]


def _graph_parts(graph: Any) -> tuple[dict[str, Any], dict[str, Any], tuple[Any, ...]]:
    nodes = {
        _text(_get(item, "node_id")): item
        for item in (_get(graph, "nodes", ()) or ())
        if _text(_get(item, "node_id"))
    }
    relations = {
        _text(_get(item, "relation_id")): item
        for item in (_get(graph, "relations", ()) or ())
        if _text(_get(item, "relation_id"))
    }
    unresolved = tuple(_get(graph, "unresolved_relations", ()) or ())
    return nodes, relations, unresolved


def _relation_endpoint(relation: Any, side: str, nodes: Mapping[str, Any]) -> str:
    node_id = _text(_get(relation, f"{side}_node_id"))
    if node_id in nodes:
        return node_id
    symbol_id = _text(_get(relation, f"{side}_symbol_id"))
    if symbol_id:
        matches = [
            node_id for node_id, node in nodes.items()
            if _text(_get(node, "symbol_id")) == symbol_id
        ]
        if matches:
            # Inter-symbol CALLS relations carry a target SymbolRef and may
            # omit a target node when the callee body was not part of the
            # requested subgraph.  If the body is present, bind the edge to
            # its first deterministic AST operation so directed reachability
            # can continue without treating every symbol node as a root.
            return min(
                matches,
                key=lambda node_id: (
                    _span_order(_text(_get(nodes[node_id], "source_span_id"))),
                    node_id,
                ),
            )
    return node_id or symbol_id


def _branch_dominance_guards(
    nodes: Mapping[str, Any],
    relations: Mapping[str, Any],
) -> tuple[
    dict[str, tuple[tuple[str, ...], tuple[str, ...]]],
    dict[str, tuple[str, tuple[str, ...]]],
    dict[str, tuple[str, tuple[str, ...]]],
]:
    """Recover the branch guard that dominates each graph node.

    A node is condition-dominated only when a typed ``TRUE_BRANCH`` /
    ``FALSE_BRANCH`` (or guard-carrying ``CONTROL_DEPENDS_ON``) relation ties
    it to a branch node whose span contains the node span, or when it is
    reached from such a target through ``NEXT_CONTROL`` edges without leaving
    the branch span (bounded dominance).  The guard text travels on the
    frozen typed edge, never from a fact string or a filename heuristic.

    Returns three mappings:

    - ``recovered``: ``node_id -> (conjuncts, relation_ids)`` where
      ``conjuncts`` is the deterministic conjunction of the dominating
      guards (a negative branch renders as ``not (G)``; conjuncts are sorted
      so the normalized text does not depend on traversal order);
    - ``unproven``: ``node_id -> (guard, relation_ids)`` for guarded typed
      edges whose bounded dominance could not be established (span
      containment fails).  The conditional claim may still belong to the
      enclosing scope, so the node keeps its own resolution and the caller
      records the gap instead of silently aligning;
    - ``conflicted``: ``node_id -> (guard, relation_ids)`` when the same
      guard text would dominate the node with both polarities (a frozen
      graph inconsistency).  The node keeps ``unknown`` so the conflict
      stays visible to the status aggregation and the owning agent.
    """

    span_bounds: dict[str, tuple[int, int]] = {}
    for node_id, node in nodes.items():
        match = re.match(r"^span:(.*):(\d+):(\d+)$", _text(_get(node, "source_span_id")))
        if match:
            span_bounds[node_id] = (int(match.group(2)), int(match.group(3)))

    def bound_of(node_id: str) -> tuple[int, int] | None:
        return span_bounds.get(node_id)

    def contains(outer: tuple[int, int], inner: tuple[int, int]) -> bool:
        return outer[0] <= inner[0] and inner[1] <= outer[1]

    dominance: dict[str, list[tuple[str, str, str, tuple[int, int]]]] = defaultdict(list)
    unproven: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for rid, relation in relations.items():
        kind = _text(_get(relation, "kind")).upper()
        guard = _normalize_guard_text(_get(relation, "guard"))
        polarity = ""
        if kind == "TRUE_BRANCH":
            polarity = "positive"
        elif kind == "FALSE_BRANCH":
            polarity = "negative"
        elif kind == "CONTROL_DEPENDS_ON":
            if guard:
                polarity = "positive"
            else:
                source_id = _relation_endpoint(relation, "source", nodes)
                guard = _normalize_guard_text(_get(nodes.get(source_id), "guard"))
                if guard:
                    polarity = "positive"
        if not guard or not polarity:
            continue
        source_id = _relation_endpoint(relation, "source", nodes)
        target_id = _relation_endpoint(relation, "target", nodes)
        source_bound = bound_of(source_id)
        target_bound = bound_of(target_id)
        if (
            source_bound is None or target_bound is None
            or not contains(source_bound, target_bound)
        ):
            # The typed edge carries a guard but bounded dominance cannot be
            # established; record the gap for the owning agent.
            unproven[target_id].append((guard, rid))
            continue
        dominance[target_id].append((guard, polarity, rid, source_bound))

    queue: deque[tuple[str, tuple[str, str, str, tuple[int, int]]]] = deque(
        (target_id, entry)
        for target_id, entries in dominance.items()
        for entry in entries
    )
    while queue:
        node_id, (guard, polarity, rid, branch_span) = queue.popleft()
        node_bound = bound_of(node_id)
        if node_bound is None or not contains(branch_span, node_bound):
            continue
        for out_rid, relation in relations.items():
            if _text(_get(relation, "kind")).upper() != "NEXT_CONTROL":
                continue
            if _relation_endpoint(relation, "source", nodes) != node_id:
                continue
            target_id = _relation_endpoint(relation, "target", nodes)
            target_bound = bound_of(target_id)
            if target_bound is None or not contains(branch_span, target_bound):
                continue
            if any(
                existing[0] == guard and existing[1] == polarity
                for existing in dominance.get(target_id, ())
            ):
                continue
            dominance[target_id].append((guard, polarity, out_rid, branch_span))
            queue.append((target_id, (guard, polarity, out_rid, branch_span)))

    recovered: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    conflicted: dict[str, tuple[str, tuple[str, ...]]] = {}
    for node_id, entries in dominance.items():
        polarities_by_guard: dict[str, set[str]] = defaultdict(set)
        relation_ids: list[str] = []
        for guard, polarity, rid, _branch_span in entries:
            polarities_by_guard[guard].add(polarity)
            if rid not in relation_ids:
                relation_ids.append(rid)
        if any(
            polarities == {"positive", "negative"}
            for polarities in polarities_by_guard.values()
        ):
            conflicting_guard = next(
                guard for guard, polarities in polarities_by_guard.items()
                if polarities == {"positive", "negative"}
            )
            conflicted[node_id] = (conflicting_guard, tuple(relation_ids))
            continue
        conjuncts = tuple(sorted(
            f"not ({guard})" if "negative" in polarities else guard
            for guard, polarities in polarities_by_guard.items()
        ))
        if conjuncts:
            recovered[node_id] = (conjuncts, tuple(relation_ids))
    return recovered, {
        node_id: (guards[0][0], tuple(dict.fromkeys(
            rid for _guard, rid in guards
        )))
        for node_id, guards in unproven.items()
        if guards
    }, conflicted


def _source_provider_files(source_provider: Any) -> dict[str, str]:
    if isinstance(source_provider, Mapping):
        return {str(k): _text(v) for k, v in source_provider.items() if isinstance(v, str)}
    files = _get(source_provider, "files", None)
    if isinstance(files, Mapping):
        return {str(k): _text(v) for k, v in files.items() if isinstance(v, str)}
    root = _text(_get(source_provider, "project_root"))
    included = _get(source_provider, "included_files", ()) or ()
    if root and included:
        result: dict[str, str] = {}
        for item in included:
            path = _text(_get(item, "path"))
            if path.endswith(".py"):
                try:
                    result[path] = Path(root, path).read_text(encoding="utf-8")
                except OSError:
                    continue
        return result
    return {}


def build_current_behavior_graph(
    *,
    symbol_index: Any,
    source_provider: Any,
    entry_symbol_ids: Sequence[str],
) -> Any | None:
    """Build the canonical current-source behavior graph.

    Offline reconstruction and the product Writer must not choose different
    graph origins.  This is the single bounded adapter entry point for both:
    it consumes the verified source provider and the same indexed entry roots,
    while retaining the existing ``depth=2``/``node_budget=2000`` limits.
    A missing entry or source closure remains an explicit ``None`` so legacy
    fixtures without repository authority can keep their typed fallback; a
    present source closure never falls back to a persisted historical graph.
    """

    if not symbol_index or not entry_symbol_ids:
        return None
    files = _source_provider_files(source_provider)
    if not files:
        return None
    try:
        from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph
        from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter

        result = build_behavior_subgraph(
            adapter=PythonBehaviorAdapter(),
            repo_snapshot_id=_text(_get(symbol_index, "repo_snapshot_id")) or "snapshot:unknown",
            project_tree_hash=_text(_get(symbol_index, "project_tree_hash")) or "tree:unknown",
            files=files,
            symbol_index=symbol_index,
            symbol_ids=list(dict.fromkeys(entry_symbol_ids)),
            depth=2,
            node_budget=2000,
        )
        return _get(result, "graph")
    except Exception:
        return None


def _build_adapter_graph(
    *,
    symbol_index: Any,
    source_provider: Any,
    entry_symbol_ids: Sequence[str],
) -> Any | None:
    """Backward-compatible private alias for the canonical graph builder."""

    return build_current_behavior_graph(
        symbol_index=symbol_index,
        source_provider=source_provider,
        entry_symbol_ids=entry_symbol_ids,
    )


def _entry_start_nodes(
    nodes: Mapping[str, Any],
    entry_symbols: Iterable[str],
) -> set[str]:
    """Select one deterministic AST start node per owner entry symbol."""

    starts: set[str] = set()
    wanted = {str(value).strip() for value in entry_symbols if str(value).strip()}
    for symbol_id in sorted(wanted):
        candidates = [
            (node_id, node)
            for node_id, node in nodes.items()
            if _text(_get(node, "symbol_id")) == symbol_id
        ]
        if not candidates:
            continue
        node_id, _node = min(
            candidates,
            key=lambda item: (
                _span_order(_text(_get(item[1], "source_span_id"))),
                item[0],
            ),
        )
        starts.add(node_id)
    return starts


def _fact_operation_parts(fact: Any) -> tuple[str, tuple[str, ...], str, tuple[str, ...]]:
    predicate = _text(_get(fact, "predicate"))
    raw_operands = _get(fact, "operands", None)
    raw_result = _get(fact, "result", None)
    if raw_operands is None:
        values = _fact_values(_get(fact, "object", ()))
        operands: list[str] = []
        result = ""
        for value in values:
            if value.casefold().startswith("result=") and not result:
                result = value.split("=", 1)[1].strip()
            else:
                operands.append(value)
        if not result and predicate.casefold() in {"return", "returns", "emits", "outputs"} and operands:
            result = operands.pop()
    else:
        operands = list(_ids(raw_operands))
        result = _text(raw_result)
    conditions = _ids(_get(fact, "conditions", ())) or _ids((_get(fact, "guard", ""),))
    return predicate, tuple(dict.fromkeys(operands)), result, conditions


def _fallback_fact_chain(facts: Any, requested_ids: Sequence[str]) -> dict[str, Any]:
    """Compatibility path for small typed-dict fixtures lacking CodeFact.object."""

    all_facts = _items(facts, "facts")
    by_id = {_text(_get(item, "fact_id")): item for item in all_facts}
    chosen = [by_id[fid] for fid in requested_ids if fid in by_id]
    atoms: list[dict[str, Any]] = []
    diagnostics: list[str] = []
    for fact in chosen:
        fid = _text(_get(fact, "fact_id"))
        status = _text(_get(fact, "validation_status"))
        if status and status != "supported":
            diagnostics.append(f"fact_not_supported:{fid}")
            continue
        spans = _ids((*_ids(_get(fact, "direct_span_ids", ())), *_ids(_get(fact, "relation_span_ids", ()))))
        if not spans:
            diagnostics.append(f"fact_exact_span_missing:{fid}")
            continue
        predicate, operands, result, conditions = _fact_operation_parts(fact)
        if not predicate and not operands and not result:
            diagnostics.append(f"fact_operation_fields_missing:{fid}")
            continue
        atoms.append({
            "operation_id": f"fact-operation:{fid}",
            "fact_id": fid,
            "subject": _text(_get(fact, "subject")),
            "scope": _text(_get(fact, "scope")),
            "predicate": predicate,
            "operands": list(operands),
            "result": result,
            "conditions": list(conditions),
            "guard": conditions[0] if conditions else "",
            "span_ids": list(spans),
            "source_span_id": spans[0],
            "shape_or_type_hints": list(_ids(_get(fact, "shape_or_type_hints", ()))),
            "exact_excerpt": _text(_get(fact, "exact_excerpt")),
        })
    return {
        "operation_atoms": tuple(atoms),
        "fact_ids": tuple(_text(_get(atom, "fact_id")) for atom in atoms),
        "exact_span_ids": tuple(dict.fromkeys(
            span for atom in atoms for span in atom.get("span_ids", ())
        )),
        "shape_or_type_hints": tuple(dict.fromkeys(
            hint for atom in atoms for hint in atom.get("shape_or_type_hints", ())
        )),
        "return_value_descriptors": tuple(
            atom["result"] for atom in atoms
            if atom.get("predicate", "").casefold() in {"return", "returns", "emits", "outputs"}
            and atom.get("result")
        ),
        "relation_evidence_ids": (),
        "diagnostics": tuple(dict.fromkeys(diagnostics)),
    }


def _compile_fact_chain(facts: Any, requested_ids: Sequence[str]) -> dict[str, Any]:
    if not requested_ids:
        return {
            "operation_atoms": (), "fact_ids": (), "exact_span_ids": (),
            "shape_or_type_hints": (), "return_value_descriptors": (),
            "relation_evidence_ids": (), "diagnostics": (),
        }
    try:
        from code2paper.agentic.research_derived_authoring import compile_code_fact_operation_chain
        compiled = compile_code_fact_operation_chain(facts=facts, fact_ids=requested_ids)
    except Exception:
        compiled = {"operation_atoms": (), "fact_ids": (), "exact_span_ids": (), "diagnostics": ()}
    fallback = _fallback_fact_chain(facts, requested_ids)
    accepted = set(_ids(compiled.get("fact_ids", ())))
    atoms = [dict(atom) for atom in (compiled.get("operation_atoms", ()) or ())]
    atoms_by_fact = {
        _text(atom.get("fact_id")): atom
        for atom in atoms if _text(atom.get("fact_id"))
    }
    for fallback_atom in fallback["operation_atoms"]:
        fact_id = _text(fallback_atom.get("fact_id"))
        if fact_id not in atoms_by_fact:
            atoms.append(dict(fallback_atom))
            continue
        # Old CodeFact-shaped dictionaries used operands/result while
        # the mature compiler reads the canonical object field. Enrich
        # an otherwise accepted atom without replacing typed values.
        atom = atoms_by_fact[fact_id]
        for key in (
            "subject", "scope", "predicate", "operands", "result", "guard",
            "conditions", "shape_or_type_hints", "span_ids", "source_span_id",
            "exact_excerpt",
        ):
            if not atom.get(key) and fallback_atom.get(key):
                atom[key] = fallback_atom[key]
    fact_ids = tuple(dict.fromkeys(
        [*_ids(compiled.get("fact_ids", ())), *fallback["fact_ids"]]
    ))
    return {
        "operation_atoms": tuple(atoms),
        "fact_ids": fact_ids,
        "exact_span_ids": tuple(dict.fromkeys(
            [*_ids(compiled.get("exact_span_ids", ())), *fallback["exact_span_ids"]]
        )),
        "shape_or_type_hints": tuple(dict.fromkeys(
            [*_ids(compiled.get("shape_or_type_hints", ())), *fallback["shape_or_type_hints"]]
        )),
        "return_value_descriptors": tuple(dict.fromkeys(
            [*_ids(compiled.get("return_value_descriptors", ())), *fallback["return_value_descriptors"]]
        )),
        "relation_evidence_ids": tuple(dict.fromkeys(_ids(compiled.get("relation_evidence_ids", ())))),
        "diagnostics": tuple(dict.fromkeys(
            [*_ids(compiled.get("diagnostics", ())), *fallback["diagnostics"]]
        )),
    }


def _collect_seed_data(
    *,
    argument_briefs: Any,
    facets: Sequence[Any],
    facet_alignments: Sequence[Any],
    field_candidates: Sequence[Any],
    story_spine: Sequence[Any],
    facts: Any,
    claims: Any,
    equations: Any,
    configurations: Any,
    evidence_packets: Any | None = None,
    implementation_scope: Any | None = None,
    symbol_index: Any | None = None,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Build narrow, exact-ID mechanism seeds from all available inputs.

    This function deliberately does not use text similarity.  A brief is
    attached to the mechanism selected by its exact ``story_node_id``; a
    facet is attached through its exact ``brief_id``; and research records are
    added only through exact fact/claim/equation/span/symbol handles.  Terms
    supplied for later search are retained as hints, but never become source
    authority by themselves.
    """

    def empty() -> dict[str, Any]:
        return {
            "story_node_ids": set(), "brief_ids": set(), "facet_ids": set(),
            "obligation_ids": set(), "author_statements": set(),
            "bound_fact_ids": set(), "bound_claim_ids": set(),
            "bound_span_ids": set(), "bound_equation_ids": set(),
            "entry_symbol_ids": set(), "formula_expectations": set(),
            "candidate_symbol_ids": set(),
            "semantic_fields": [], "search_terms": set(),
            "bound_relation_ids": set(), "configuration_ids": set(),
            "scope_target_symbol_ids": set(),
            "scope_comparand_symbol_ids": set(),
            "scope_evaluation_symbol_ids": set(),
            "scope_configuration_symbol_ids": set(),
            "explicit_mechanism_ids": set(),
            "seed_alias_ids": set(),
        }

    seeds: dict[str, dict[str, Any]] = defaultdict(empty)
    story_values = tuple(story_spine)
    brief_values = _items(argument_briefs, "briefs")
    facet_values = tuple(facets)
    alignment_values = tuple(facet_alignments)
    candidate_values = tuple(field_candidates)
    fact_values = _items(facts, "facts")
    claim_values = _items(claims, "claims")
    equation_values = _items(equations, "equations")
    config_values = _items(configurations, "claims")
    packet_values = _items(evidence_packets, "packets")

    fact_by_id = {
        _text(_get(item, "fact_id")): item
        for item in fact_values if _text(_get(item, "fact_id"))
    }
    claim_by_id = {
        _text(_get(item, "claim_id")): item
        for item in claim_values if _text(_get(item, "claim_id"))
    }
    equation_by_id = {
        _text(_get(item, "equation_id")): item
        for item in equation_values if _text(_get(item, "equation_id"))
    }
    facet_by_id = {
        _text(_get(item, "facet_id")): item
        for item in facet_values if _text(_get(item, "facet_id"))
    }
    alignment_by_facet = {
        _text(_get(item, "facet_id")): item
        for item in alignment_values if _text(_get(item, "facet_id"))
    }

    explicit_symbol_fields = (
        "entry_symbol_ids", "target_entry_symbol_ids", "target_symbol_ids",
        "target_core_symbol_ids", "target_dependency_symbol_ids",
        "implementation_symbol_ids", "source_symbol_ids", "symbol_ids",
        "bound_symbol_ids", "candidate_symbol_ids", "symbol_id",
    )
    owner_symbol_fields = (
        "entry_symbol_ids", "target_entry_symbol_ids", "entry_symbol_id",
        "target_entry_symbol_id", "owner_symbol_ids", "owner_symbol_id",
        "implementation_owner_symbol_ids", "implementation_owner_symbol_id",
    )

    def explicit_symbol_ids(value: Any) -> tuple[str, ...]:
        result: list[str] = []
        for name in explicit_symbol_fields:
            result.extend(_ids(_get(value, name, ())))
        return tuple(dict.fromkeys(result))

    def explicit_owner_symbol_ids(value: Any) -> tuple[str, ...]:
        result: list[str] = []
        for name in owner_symbol_fields:
            result.extend(_ids(_get(value, name, ())))
        return tuple(dict.fromkeys(result))

    def add_semantic_field(row: dict[str, Any], value: Any) -> None:
        if not isinstance(value, Mapping):
            return
        normalized = {
            str(key): item for key, item in value.items()
            if item is not None and item != "" and item != () and item != []
        }
        if not normalized:
            return
        marker = canonical_json_bytes(normalized)
        if not any(canonical_json_bytes(item) == marker for item in row["semantic_fields"]):
            row["semantic_fields"].append(normalized)

    def add_mid(raw: Any) -> dict[str, Any]:
        mechanism_id = _canonical_mechanism_id(raw) or "mech_default"
        row = seeds[mechanism_id]
        row["seed_alias_ids"].add(mechanism_id)
        return row

    story_to_mechanism: dict[str, str] = {}
    story_by_mechanism: dict[str, set[str]] = defaultdict(set)
    for node in story_values:
        story_id = _text(_get(node, "story_node_id") or _get(node, "node_id"))
        explicit_mid = _text(_get(node, "mechanism_id") or _get(node, "mechanism_key"))
        owner_symbols = explicit_owner_symbol_ids(node)
        mechanism_id = _canonical_mechanism_id(
            explicit_mid or (owner_symbols[0] if owner_symbols else "")
        )
        if not mechanism_id:
            # A narrative node without an executable owner is retained by the
            # upstream intent artifacts, but cannot create a mechanism or
            # acquire repository evidence through this compiler.
            continue
        row = add_mid(mechanism_id)
        if explicit_mid:
            row["explicit_mechanism_ids"].add(mechanism_id)
        if story_id:
            story_to_mechanism[story_id] = mechanism_id
            story_by_mechanism[mechanism_id].add(story_id)
            row["story_node_ids"].add(story_id)
        statement = _text(
            _get(node, "author_statement")
            or _get(node, "statement")
            or _get(node, "narrative")
            or _get(node, "description")
        )
        if statement:
            row["author_statements"].add(statement)
        row["obligation_ids"].update(_ids(_get(node, "linked_obligation_ids", ())))
        row["bound_claim_ids"].update(_ids(_get(node, "linked_claim_ids", ())))
        row["bound_span_ids"].update(_ids(_get(node, "source_refs", ())))
        row["entry_symbol_ids"].update(owner_symbols)
        row["candidate_symbol_ids"].update(explicit_symbol_ids(node))
        row["candidate_symbol_ids"].update(_ids(_get(node, "candidate_symbols_or_terms", ())))
        add_semantic_field(row, _get(node, "semantic_fields", {}))

    brief_to_mechanism: dict[str, str] = {}
    for brief in brief_values:
        brief_id = _text(_get(brief, "brief_id"))
        story_id = _text(_get(brief, "story_node_id"))
        explicit_mid = _text(_get(brief, "mechanism_id") or _get(brief, "mechanism_key"))
        owner_symbols = explicit_owner_symbol_ids(brief)
        mechanism_id = _canonical_mechanism_id(
            explicit_mid
            or story_to_mechanism.get(story_id, "")
            or (owner_symbols[0] if owner_symbols else "")
        )
        if not mechanism_id:
            continue
        row = add_mid(mechanism_id)
        if explicit_mid:
            row["explicit_mechanism_ids"].add(mechanism_id)
        if brief_id:
            row["brief_ids"].add(brief_id)
            brief_to_mechanism[brief_id] = mechanism_id
        if story_id:
            row["story_node_ids"].add(story_id)
        row["obligation_ids"].update(_ids(_get(brief, "obligation_ids", ())))
        row["bound_claim_ids"].update(_ids(_get(brief, "claim_ids", ())))
        row["bound_equation_ids"].update(_ids(_get(brief, "equation_ids", ())))
        row["bound_span_ids"].update(_ids(_get(brief, "span_ids", ())))
        row["configuration_ids"].update(_ids(_get(brief, "configuration_ids", ())))
        row["entry_symbol_ids"].update(owner_symbols)
        row["candidate_symbol_ids"].update(explicit_symbol_ids(brief))
        row["candidate_symbol_ids"].update(_ids(_get(brief, "candidate_symbols_or_terms", ())))
        statement = _text(_get(brief, "author_statement") or _get(brief, "purpose"))
        if statement:
            row["author_statements"].add(statement)
        add_semantic_field(row, _get(brief, "semantic_fields", {}))
        for clause in _get(brief, "clauses", ()) or ():
            row["obligation_ids"].update(_ids(_get(clause, "clause_id", ())))
            row["obligation_ids"].update(_ids(_get(clause, "bound_target_ids", ())))
            row["bound_claim_ids"].update(_ids(_get(clause, "bound_claim_ids", ())))
            row["bound_equation_ids"].update(_ids(_get(clause, "bound_equation_ids", ())))
            row["bound_span_ids"].update(_ids(_get(clause, "bound_span_ids", ())))

    facet_to_mechanism: dict[str, str] = {}
    for facet in facet_values:
        fid = _text(_get(facet, "facet_id"))
        brief_id = _text(_get(facet, "brief_id"))
        story_id = _text(_get(facet, "story_node_id"))
        explicit_mid = _text(_get(facet, "mechanism_id") or _get(facet, "mechanism_key"))
        owner_symbols = explicit_owner_symbol_ids(facet)
        mechanism_id = _canonical_mechanism_id(
            explicit_mid
            or brief_to_mechanism.get(brief_id, "")
            or story_to_mechanism.get(story_id, "")
            or (owner_symbols[0] if owner_symbols else "")
        )
        if not mechanism_id:
            continue
        row = add_mid(mechanism_id)
        if explicit_mid:
            row["explicit_mechanism_ids"].add(mechanism_id)
        if fid:
            row["facet_ids"].add(fid)
            facet_to_mechanism[fid] = mechanism_id
        if brief_id:
            row["brief_ids"].add(brief_id)
        if story_id:
            row["story_node_ids"].add(story_id)
        clause_id = _text(_get(facet, "clause_id"))
        if clause_id:
            row["obligation_ids"].add(clause_id)
        expectation = _text(_get(facet, "formula_expectation"))
        if expectation:
            row["formula_expectations"].add(expectation)
        statement = _text(_get(facet, "exact_source_quote") or _get(facet, "author_statement"))
        if statement:
            row["author_statements"].add(statement)
        row["search_terms"].update(_ids(_get(facet, "search_terms", ())))
        row["entry_symbol_ids"].update(owner_symbols)
        row["candidate_symbol_ids"].update(explicit_symbol_ids(facet))
        add_semantic_field(row, _get(facet, "semantic_fields", {}))
        alignment = alignment_by_facet.get(fid)
        if alignment is None:
            continue
        row["bound_fact_ids"].update(_ids(
            _get(alignment, "bound_fact_ids", ())
        ))
        row["bound_claim_ids"].update(_ids(
            _get(alignment, "bound_claim_ids", ())
        ))
        row["bound_span_ids"].update(_ids(
            _get(alignment, "bound_span_ids", ())
        ))
        row["bound_equation_ids"].update(_ids(
            _get(alignment, "bound_equation_ids", ())
        ))
        row["search_terms"].update(_ids(_get(alignment, "search_terms", ())))
        row["bound_relation_ids"].update(_ids(_get(alignment, "relation_evidence_ids", ())))
        for binding in _get(alignment, "field_bindings", ()) or ():
            row["bound_fact_ids"].update(_ids(_get(binding, "bound_fact_ids", ())))
            row["bound_claim_ids"].update(_ids(_get(binding, "bound_claim_ids", ())))
            row["bound_span_ids"].update(_ids(_get(binding, "bound_span_ids", ())))
            row["bound_equation_ids"].update(_ids(_get(binding, "bound_equation_ids", ())))
            row["bound_relation_ids"].update(_ids(_get(binding, "relation_evidence_ids", ())))

    for candidate in candidate_values:
        fid = _text(_get(candidate, "facet_id"))
        if not fid:
            continue
        explicit_mid = _text(
            _get(candidate, "mechanism_id") or _get(candidate, "mechanism_key")
        )
        target_mid = explicit_mid or facet_to_mechanism.get(fid, "")
        if not target_mid:
            continue
        row = add_mid(target_mid)
        if explicit_mid:
            row["explicit_mechanism_ids"].add(_canonical_mechanism_id(explicit_mid))
        row["facet_ids"].add(fid)
        row["bound_fact_ids"].update(_ids(_get(candidate, "bound_fact_ids", ())))
        row["bound_claim_ids"].update(_ids(_get(candidate, "bound_claim_ids", ())))
        row["bound_span_ids"].update(_ids(_get(candidate, "bound_span_ids", ())))
        row["bound_equation_ids"].update(_ids(_get(candidate, "bound_equation_ids", ())))
        row["search_terms"].update(_ids(_get(candidate, "search_terms", ())))
        row["candidate_symbol_ids"].update(_ids(_get(candidate, "candidate_symbols_or_terms", ())))
        semantic_atom = _text(_get(candidate, "semantic_atom"))
        if semantic_atom:
            add_semantic_field(row, {
                "field_name": _get(candidate, "field_name"),
                "semantic_atom": semantic_atom,
                "ownership_roles": list(_get(candidate, "ownership_roles", ()) or ()),
            })

    # Exact transitive closure over the typed evidence ids.  This loop is
    # intentionally finite and monotonic: no natural-language relation is
    # introduced while following fact -> claim -> equation links.
    while True:
        changed = False
        for row in seeds.values():
            before = sum(len(row[name]) for name in (
                "bound_fact_ids", "bound_claim_ids", "bound_equation_ids", "bound_span_ids",
            ))
            for fact_id in tuple(row["bound_fact_ids"]):
                fact = fact_by_id.get(fact_id)
                if fact is None:
                    continue
                row["bound_span_ids"].update(_ids(
                    (*_ids(_get(fact, "direct_span_ids", ())),
                     *_ids(_get(fact, "relation_span_ids", ())))
                ))
                row["bound_claim_ids"].update(_ids(_get(fact, "claim_ids", ())))
                row["bound_equation_ids"].update(_ids(_get(fact, "equation_ids", ())))
                row["bound_relation_ids"].update(_ids(_get(fact, "relation_evidence_ids", ())))
                row["candidate_symbol_ids"].update(_ids(
                    _get(fact, "scope") or _get(fact, "subject")
                ))
                row["candidate_symbol_ids"].update(explicit_symbol_ids(fact))
            for claim_id in tuple(row["bound_claim_ids"]):
                claim = claim_by_id.get(claim_id)
                if claim is None:
                    continue
                row["bound_fact_ids"].update(_ids(_get(claim, "fact_ids", ())))
                row["bound_span_ids"].update(_ids(_get(claim, "direct_evidence_ids", ())))
                row["bound_span_ids"].update(_ids(_get(claim, "span_ids", ())))
                row["bound_equation_ids"].update(_ids(_get(claim, "equation_ids", ())))
                row["bound_relation_ids"].update(_ids(_get(claim, "relation_evidence_ids", ())))
            for equation_id in tuple(row["bound_equation_ids"]):
                equation = equation_by_id.get(equation_id)
                if equation is None:
                    continue
                row["bound_fact_ids"].update(_ids(_get(equation, "fact_ids", ())))
                row["bound_span_ids"].update(_ids(_get(equation, "span_ids", ())))
                row["bound_span_ids"].update(_ids(_get(equation, "direct_span_ids", ())))
                row["bound_relation_ids"].update(_ids(_get(equation, "relation_evidence_ids", ())))
            after = sum(len(row[name]) for name in (
                "bound_fact_ids", "bound_claim_ids", "bound_equation_ids", "bound_span_ids",
            ))
            changed |= after != before
        if not changed:
            break

    # Configuration is a typed binding, not a string-name classifier.  An
    # explicit owner can create a seed; an unowned configuration is scoped to
    # the sole mechanism only when there is no ambiguity.
    for config in config_values:
        explicit_mid = _text(_get(config, "mechanism_id") or _get(config, "owner_mechanism_id"))
        target_mid = _canonical_mechanism_id(explicit_mid)
        if not target_mid and len(seeds) == 1:
            target_mid = next(iter(seeds))
        if not target_mid:
            continue
        row = add_mid(target_mid)
        row["bound_span_ids"].update(_ids(
            (*_ids(_get(config, "definition_span_ids", ())),
             *_ids(_get(config, "entrypoint_span_ids", ())))
        ))
        row["configuration_ids"].update(_ids(_get(config, "configuration_id", ())))
        row["entry_symbol_ids"].update(explicit_symbol_ids(config))

    # Packets contribute exact span/relation endpoints.  A packet with an
    # obligation tag or an exact already-bound handle belongs to that seed;
    # only a single-seed run may consume an otherwise untagged packet.
    for packet in packet_values:
        packet_id = _text(_get(packet, "packet_id"))
        packet_tags = set(_ids(_get(packet, "obligation_tags", ())))
        packet_spans = set(_ids(
            (*_ids(_get(packet, "anchor_span_ids", ())),
             *_ids(_get(packet, "relation_span_ids", ())),
             *_ids(_get(packet, "semantic_span_ids", ())))
        ))
        packet_relations = {
            _text(_get(relation, "relation_id"))
            for relation in (_get(packet, "relations", ()) or ())
            if _text(_get(relation, "relation_id"))
        }
        packet_symbols = set()
        for relation in (_get(packet, "relations", ()) or ()):
            packet_symbols.update(_ids(_get(relation, "source_symbol", ())))
            packet_symbols.update(_ids(_get(relation, "target_symbol", ())))
        packet_scope = _text(_get(packet, "scope"))
        owners: list[dict[str, Any]] = []
        for mid, row in seeds.items():
            if (
                packet_tags.intersection(row["obligation_ids"])
                or packet_spans.intersection(row["bound_span_ids"])
                or packet_relations.intersection(row["bound_relation_ids"])
                or packet_scope in row["candidate_symbol_ids"]
                or packet_scope in row["entry_symbol_ids"]
                or packet_symbols.intersection(row["candidate_symbol_ids"] | row["entry_symbol_ids"])
            ):
                owners.append(row)
        if not owners and len(seeds) == 1:
            owners = [next(iter(seeds.values()))]
        for row in owners:
            row["bound_span_ids"].update(packet_spans)
            row["bound_relation_ids"].update(packet_relations)
            row["candidate_symbol_ids"].update(packet_symbols)
            if packet_id:
                row["search_terms"].add(f"packet:{packet_id}")
            for relation in (_get(packet, "relations", ()) or ()):
                row["bound_span_ids"].update(_ids(
                    (_get(relation, "source_span_id"), _get(relation, "target_span_id"))
                ))

    # ImplementationScope provides exact ownership groups.  It is global in
    # the current artifact contract, so fan-out is allowed only for a single
    # mechanism.  With several mechanisms, only exact symbol handles already
    # present in a seed can associate scope metadata.
    scope_dump = _dump(implementation_scope)
    scope_groups = {
        "entry": set(_ids(scope_dump.get("target_entry_symbol_ids", ()))),
        "target": set(_ids(scope_dump.get("target_core_symbol_ids", ())))
        | set(_ids(scope_dump.get("target_dependency_symbol_ids", ()))),
        "comparand": set(_ids(scope_dump.get("comparand_symbol_ids", ()))),
        "evaluation": set(_ids(scope_dump.get("evaluation_symbol_ids", ()))),
        "configuration": set(_ids(scope_dump.get("configuration_symbol_ids", ()))),
    }
    scope_is_initial_owner_surface = not seeds
    for entry_symbol_id in sorted(scope_groups["entry"]):
        target_mid = next(
            (
                mechanism_id for mechanism_id, row in seeds.items()
                if entry_symbol_id in row["entry_symbol_ids"]
            ),
            "",
        )
        if not target_mid and scope_is_initial_owner_surface:
            target_mid = _canonical_mechanism_id(entry_symbol_id)
        if target_mid:
            row = add_mid(target_mid)
            row["entry_symbol_ids"].add(entry_symbol_id)
    for row in seeds.values():
        known = row["entry_symbol_ids"] | row["candidate_symbol_ids"]
        if len(seeds) == 1:
            row["entry_symbol_ids"].update(scope_groups["entry"])
            row["scope_target_symbol_ids"].update(scope_groups["target"])
            row["scope_comparand_symbol_ids"].update(scope_groups["comparand"])
            row["scope_evaluation_symbol_ids"].update(scope_groups["evaluation"])
            row["scope_configuration_symbol_ids"].update(scope_groups["configuration"])
        else:
            row["entry_symbol_ids"].update(scope_groups["entry"].intersection(known))
            row["scope_target_symbol_ids"].update(scope_groups["target"].intersection(known))
            row["scope_comparand_symbol_ids"].update(scope_groups["comparand"].intersection(known))
            row["scope_evaluation_symbol_ids"].update(scope_groups["evaluation"].intersection(known))
            row["scope_configuration_symbol_ids"].update(scope_groups["configuration"].intersection(known))

    # A repository scope may be the first executable owner surface in a small
    # run (there is no story/brief/facet yet).  Bind only the source records
    # whose exact symbol handle is covered by that owner.  This keeps the
    # owner-first partition fail-closed while preventing a valid scoped fact
    # from being stranded merely because the scope seed was materialized after
    # the initial fact/claim closure pass.
    for row in seeds.values():
        owner_handles = set(row["entry_symbol_ids"])
        owner_handles.update(row["scope_target_symbol_ids"])
        owner_handles.update(row["candidate_symbol_ids"])
        if len(seeds) != 1 and not owner_handles:
            continue
        for fact in fact_values:
            fact_handles = set(_ids(_get(fact, "scope")))
            fact_handles.update(_ids(_get(fact, "subject")))
            fact_handles.update(explicit_symbol_ids(fact))
            if fact_handles.intersection(owner_handles):
                row["bound_fact_ids"].update(_ids(_get(fact, "fact_id")))
        bound_facts = set(row["bound_fact_ids"])
        for claim in claim_values:
            if bound_facts.intersection(_ids(_get(claim, "fact_ids", ()) )):
                row["bound_claim_ids"].update(_ids(_get(claim, "claim_id")))
        bound_claims = set(row["bound_claim_ids"])
        for equation in equation_values:
            if (
                bound_facts.intersection(_ids(_get(equation, "fact_ids", ())))
                or bound_claims.intersection(_ids(_get(equation, "claim_ids", ())))
            ):
                row["bound_equation_ids"].update(_ids(_get(equation, "equation_id")))

    # Complete the exact fact → claim → equation closure for records attached
    # by the scope-owner pass above.  The earlier pass remains necessary for
    # intent-created seeds; this bounded second pass covers only newly bound
    # owner records and does not introduce text-based associations.
    while True:
        changed = False
        for row in seeds.values():
            before = sum(len(row[name]) for name in (
                "bound_fact_ids", "bound_claim_ids", "bound_equation_ids", "bound_span_ids",
            ))
            for fact_id in tuple(row["bound_fact_ids"]):
                fact = fact_by_id.get(fact_id)
                if fact is None:
                    continue
                row["bound_span_ids"].update(_ids(
                    (*_ids(_get(fact, "direct_span_ids", ())),
                     *_ids(_get(fact, "relation_span_ids", ())))
                ))
                row["bound_claim_ids"].update(_ids(_get(fact, "claim_ids", ())))
                row["bound_equation_ids"].update(_ids(_get(fact, "equation_ids", ())))
                row["bound_relation_ids"].update(_ids(_get(fact, "relation_evidence_ids", ())))
            for claim_id in tuple(row["bound_claim_ids"]):
                claim = claim_by_id.get(claim_id)
                if claim is None:
                    continue
                row["bound_fact_ids"].update(_ids(_get(claim, "fact_ids", ())))
                row["bound_span_ids"].update(_ids(_get(claim, "direct_evidence_ids", ())))
                row["bound_span_ids"].update(_ids(_get(claim, "span_ids", ())))
                row["bound_equation_ids"].update(_ids(_get(claim, "equation_ids", ())))
                row["bound_relation_ids"].update(_ids(_get(claim, "relation_evidence_ids", ())))
            for equation_id in tuple(row["bound_equation_ids"]):
                equation = equation_by_id.get(equation_id)
                if equation is None:
                    continue
                row["bound_fact_ids"].update(_ids(_get(equation, "fact_ids", ())))
                row["bound_claim_ids"].update(_ids(_get(equation, "claim_ids", ())))
                row["bound_span_ids"].update(_ids(_get(equation, "span_ids", ())))
                row["bound_span_ids"].update(_ids(_get(equation, "direct_span_ids", ())))
                row["bound_relation_ids"].update(_ids(_get(equation, "relation_evidence_ids", ())))
            after = sum(len(row[name]) for name in (
                "bound_fact_ids", "bound_claim_ids", "bound_equation_ids", "bound_span_ids",
            ))
            changed |= after != before
        if not changed:
            break

    # Resolve explicit qualified names to symbol ids only when the index has a
    # unique exact match.  This keeps free-form search terms out of graph
    # ownership while still letting old fact artifacts name a qname.
    symbols = tuple(_get(symbol_index, "symbols", ()) or ())
    for row in seeds.values():
        resolved: set[str] = set(row["entry_symbol_ids"])
        for candidate in tuple(row["candidate_symbol_ids"]):
            exact = [
                symbol for symbol in symbols
                if _text(_get(symbol, "symbol_id")) == candidate
                or _text(_get(symbol, "qualified_name")) == candidate
                or (
                    _text(_get(symbol, "path"))
                    and f"{_text(_get(symbol, 'path'))}::{_text(_get(symbol, 'qualified_name'))}" == candidate
                )
            ]
            if len(exact) == 1:
                resolved.add(_text(_get(exact[0], "symbol_id")))
        row["candidate_symbol_ids"].update(resolved)

    # Owner-first seed typing (remediation plan section 9.4).  Only an
    # explicit mechanism key, a MethodUnit owner, or a target entry symbol
    # makes a seed an executable owner anchor.  Story/brief/facet-only rows
    # are narrative organization and can never anchor or merge a mechanism.
    for row in seeds.values():
        if row["explicit_mechanism_ids"] or row["entry_symbol_ids"]:
            row["seed_kind"] = "executable"
        elif row["story_node_ids"] or row["brief_ids"] or row["facet_ids"]:
            row["seed_kind"] = "narrative"
        else:
            row["seed_kind"] = "unresolved"

    ownerless_seed_ids: set[str] = set()
    if not seeds and (fact_by_id or claim_by_id or equation_by_id):
        # Owner-first rule: facts without any owner anchor never become a
        # project-wide pseudo mechanism.  They are reported as ownerless
        # seeds so admission can fail closed instead of silently merging the
        # whole authoring graph into one mechanism.
        ownerless_seed_ids.update(fact_by_id.keys())
        ownerless_seed_ids.update(claim_by_id.keys())
        ownerless_seed_ids.update(equation_by_id.keys())
    return dict(seeds), ownerless_seed_ids


#: Relation kinds that may prove an executable path when their adapter defines
#: the direction.  ``CONTAINS`` and plain text ordering never prove execution;
#: ``ALIAS_OF``/``IMPLEMENTS``/``OVERRIDES`` only help owner resolution.
_EXECUTABLE_RELATION_KINDS = frozenset({
    "CALLS", "RETURNS_TO", "DATA_DEPENDS_ON", "CONTROL_DEPENDS_ON",
    "READS_FROM", "WRITES_TO", "NEXT_CONTROL", "TRUE_BRANCH", "FALSE_BRANCH",
})


def _executable_adjacency(
    nodes: Mapping[str, Any],
    relations: Mapping[str, Any],
) -> dict[str, list[tuple[str, str]]]:
    """Directed source→target adjacency over executable relation kinds only."""

    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for rid, relation in relations.items():
        kind = _text(_get(relation, "kind")).upper()
        if kind not in _EXECUTABLE_RELATION_KINDS:
            continue
        source = _relation_endpoint(relation, "source", nodes)
        target = _relation_endpoint(relation, "target", nodes)
        if source in nodes and target in nodes and source != target:
            adjacency[source].append((target, rid))
    return adjacency


def _reachable_closure(
    adjacency: Mapping[str, list[tuple[str, str]]],
    start_nodes: Iterable[str],
) -> tuple[set[str], set[str]]:
    """BFS reachability over the directed executable subgraph.

    Real cycles are handled by the visited set, so a strongly connected
    component is simply mutually reachable; no synthetic reverse edge is
    introduced for a one-way producer→consumer chain.
    """

    seen_nodes: set[str] = set(start_nodes)
    seen_relations: set[str] = set()
    queue = deque(sorted(seen_nodes))
    while queue:
        current = queue.popleft()
        for target, rid in sorted(adjacency.get(current, ()), key=lambda item: item[1]):
            seen_relations.add(rid)
            if target not in seen_nodes:
                seen_nodes.add(target)
                queue.append(target)
    return seen_nodes, seen_relations


def _directed_path_relations(
    adjacency: Mapping[str, list[tuple[str, str]]],
    start_nodes: Iterable[str],
    goal_nodes: Iterable[str],
) -> tuple[str, ...]:
    """Return one deterministic directed relation path between two seed groups."""

    goals = set(goal_nodes)
    starts = sorted(set(start_nodes))
    if not goals or not starts:
        return ()
    parents: dict[str, tuple[str, str]] = {}
    queue = deque(starts)
    visited = set(starts)
    while queue:
        current = queue.popleft()
        if current in goals and current not in starts:
            break
        for target, rid in sorted(adjacency.get(current, ()), key=lambda item: item[1]):
            if target not in visited:
                visited.add(target)
                parents[target] = (current, rid)
                queue.append(target)
    reachable_goal = next((goal for goal in sorted(goals) if goal in visited), None)
    if reachable_goal is None:
        return ()
    relation_ids: list[str] = []
    cursor = reachable_goal
    while cursor in parents:
        previous, rid = parents[cursor]
        relation_ids.append(rid)
        cursor = previous
    return tuple(reversed(relation_ids))


def _merge_mechanism_seed_rows(
    seeds: Mapping[str, dict[str, Any]],
    *,
    facts: Any | None = None,
    graph: Any | None = None,
) -> tuple[dict[str, dict[str, Any]], tuple[Any, ...]]:
    """Owner-first mechanism partition with machine-verifiable merge proofs.

    Replaces the legacy ``evidence_overlap OR fact_flow_overlap OR
    direct_graph_link`` transitive union: shared claims, spans, briefs,
    facts, or a single graph adjacency never merge two seeds.  A merge is
    admitted only when

    1. both seeds declare the same explicit mechanism owner, or
    2. both seeds' graph anchors are uniquely covered by one entry's directed
       executable entry→output closure with no competing owner and a directed
       executable path connects them.

    Every decision is returned as a ``MechanismMergeProofV1`` so admission can
    verify it; ``conflict`` proofs mark competing explicit owners and never
    merge.
    """

    from code2paper.agentic.unified_context_models import MechanismMergeProofV1

    merged_rows: dict[str, dict[str, Any]] = {
        str(key): dict(value) for key, value in seeds.items()
    }
    if len(merged_rows) < 2:
        return merged_rows, ()

    keys = tuple(sorted(merged_rows))
    explicit_by_key = {
        key: set(merged_rows[key].get("explicit_mechanism_ids", ()))
        for key in keys
    }
    parent = {key: key for key in keys}

    def find(key: str) -> str:
        root = parent[key]
        while root != parent[root]:
            parent[root] = parent[parent[root]]
            root = parent[root]
        while key != root:
            next_key = parent[key]
            parent[key] = root
            key = next_key
        return root

    graph_nodes, graph_relations, _unresolved = _graph_parts(graph)
    adjacency = _executable_adjacency(graph_nodes, graph_relations)

    def graph_anchors(row: Mapping[str, Any]) -> set[str]:
        symbols = set(row.get("entry_symbol_ids", ()))
        symbols.update(row.get("candidate_symbol_ids", ()))
        symbols.update(row.get("scope_target_symbol_ids", ()))
        symbols.update(row.get("scope_configuration_symbol_ids", ()))
        spans = set(row.get("bound_span_ids", ()))
        fact_ids = set(row.get("bound_fact_ids", ()))
        return {
            node_id
            for node_id, node in graph_nodes.items()
            if (
                _text(_get(node, "symbol_id")) in symbols
                or _text(_get(node, "source_span_id")) in spans
                or fact_ids.intersection(set(_ids(_get(node, "source_fact_ids", ()))))
            )
        }

    anchors_by_key = {key: graph_anchors(merged_rows[key]) for key in keys}
    closure_by_key: dict[str, tuple[set[str], set[str]]] = {
        key: (
            _reachable_closure(adjacency, anchors_by_key[key])
            if anchors_by_key[key]
            else (set(), set())
        )
        for key in keys
    }

    merge_proofs: list[MechanismMergeProofV1] = []

    def proof(
        left_key: str,
        right_key: str,
        *,
        decision: str,
        owner_anchor_id: str = "",
        directed_path_relation_ids: tuple[str, ...] = (),
        reason: str = "",
        input_node_ids: Iterable[str] | None = None,
        output_node_ids: Iterable[str] | None = None,
    ) -> MechanismMergeProofV1:
        return MechanismMergeProofV1(
            left_seed_id=left_key,
            right_seed_id=right_key,
            owner_anchor_id=owner_anchor_id,
            input_node_ids=tuple(sorted(
                anchors_by_key.get(left_key, set())
                if input_node_ids is None else set(input_node_ids)
            )),
            output_node_ids=tuple(sorted(
                anchors_by_key.get(right_key, set())
                if output_node_ids is None else set(output_node_ids)
            )),
            directed_path_relation_ids=directed_path_relation_ids,
            decision=decision,  # type: ignore[arg-type]
            reason=reason,
        )

    def _merge_roots(left_root: str, right_root: str) -> None:
        """Union two roots while retaining the closure metadata on the root."""

        parent[right_root] = left_root
        explicit_by_key[left_root] = (
            explicit_by_key[left_root] | explicit_by_key[right_root]
        )
        anchors_by_key[left_root] = (
            anchors_by_key[left_root] | anchors_by_key[right_root]
        )
        left_nodes, left_relations = closure_by_key[left_root]
        right_nodes, right_relations = closure_by_key[right_root]
        closure_by_key[left_root] = (
            left_nodes | right_nodes,
            left_relations | right_relations,
        )

    def _owner_start_nodes(owner_anchor_id: str) -> set[str]:
        return {
            node_id for node_id, node in graph_nodes.items()
            if node_id == owner_anchor_id
            or _text(_get(node, "symbol_id")) == owner_anchor_id
        }

    def _common_terminal_output(
        left_anchors: set[str], right_anchors: set[str]
    ) -> bool:
        """Require a common directed output when the graph exposes sinks.

        A cyclic executable component has no literal sink.  In that case the
        common reachable node itself is the SCC witness; the separate path
        check below still prevents an unrelated shared anchor from merging.
        """

        left_nodes, _ = _reachable_closure(adjacency, left_anchors)
        right_nodes, _ = _reachable_closure(adjacency, right_anchors)
        common = left_nodes & right_nodes
        if not common:
            return False
        terminals = {
            node_id for node_id in common
            if not any(target in common for target, _ in adjacency.get(node_id, ()))
        }
        return bool(terminals or not any(adjacency.get(node_id) for node_id in common))

    for index, left_key in enumerate(keys):
        for right_key in keys[index + 1:]:
            left_root = find(left_key)
            right_root = find(right_key)
            if left_root == right_root:
                continue
            left_explicit = explicit_by_key[left_root]
            right_explicit = explicit_by_key[right_root]
            if left_explicit and right_explicit:
                if left_explicit == right_explicit:
                    owner = sorted(left_explicit)[0]
                    left_input_nodes = set(anchors_by_key.get(left_root, set()))
                    right_output_nodes = set(anchors_by_key.get(right_root, set()))
                    _merge_roots(left_root, right_root)
                    merge_proofs.append(proof(
                        left_key, right_key,
                        decision="merged",
                        owner_anchor_id=owner,
                        input_node_ids=left_input_nodes,
                        output_node_ids=right_output_nodes,
                        reason="same_explicit_owner",
                    ))
                else:
                    merge_proofs.append(proof(
                        left_key, right_key,
                        decision="conflict",
                        reason="competing_explicit_owners",
                    ))
                continue
            # Owner-first directed closure merge: both seed groups must be
            # covered by one unique declared entry anchor.  A shared claim,
            # span, fact, brief, or a single adjacency is not an owner proof.
            left_anchors = anchors_by_key[left_root]
            right_anchors = anchors_by_key[right_root]
            if not left_anchors or not right_anchors:
                continue
            declared_entry_ids = set(
                merged_rows[left_root].get("entry_symbol_ids", ())
            ) | set(merged_rows[right_root].get("entry_symbol_ids", ()))
            if not declared_entry_ids:
                merge_proofs.append(proof(
                    left_key, right_key,
                    decision="shared",
                    reason="no_unique_owner_entry_anchor",
                    input_node_ids=left_anchors,
                    output_node_ids=right_anchors,
                ))
                continue
            if len(declared_entry_ids) != 1:
                merge_proofs.append(proof(
                    left_key, right_key,
                    decision="conflict",
                    reason="competing_entry_owner_anchors",
                    input_node_ids=left_anchors,
                    output_node_ids=right_anchors,
                ))
                continue
            owner_anchor_id = next(iter(declared_entry_ids))
            owner_starts = _owner_start_nodes(owner_anchor_id)
            if not owner_starts:
                merge_proofs.append(proof(
                    left_key, right_key,
                    decision="shared",
                    owner_anchor_id=owner_anchor_id,
                    reason="owner_entry_not_in_typed_graph",
                    input_node_ids=left_anchors,
                    output_node_ids=right_anchors,
                ))
                continue
            owner_nodes, owner_relations = _reachable_closure(
                adjacency, owner_starts
            )
            if not left_anchors <= owner_nodes or not right_anchors <= owner_nodes:
                merge_proofs.append(proof(
                    left_key, right_key,
                    decision="shared",
                    owner_anchor_id=owner_anchor_id,
                    reason="owner_closure_does_not_cover_both_seed_groups",
                    input_node_ids=left_anchors,
                    output_node_ids=right_anchors,
                ))
                continue
            path_relation_ids = _directed_path_relations(
                adjacency, left_anchors, right_anchors
            ) or _directed_path_relations(adjacency, right_anchors, left_anchors)
            if not path_relation_ids:
                merge_proofs.append(proof(
                    left_key, right_key,
                    decision="shared",
                    owner_anchor_id=owner_anchor_id,
                    reason="owner_closure_has_no_directed_seed_path",
                    input_node_ids=left_anchors,
                    output_node_ids=right_anchors,
                ))
                continue
            if not _common_terminal_output(left_anchors, right_anchors):
                merge_proofs.append(proof(
                    left_key, right_key,
                    decision="shared",
                    owner_anchor_id=owner_anchor_id,
                    directed_path_relation_ids=path_relation_ids,
                    reason="owner_closure_has_no_common_terminal_output",
                    input_node_ids=left_anchors,
                    output_node_ids=right_anchors,
                ))
                continue
            _merge_roots(left_root, right_root)
            merge_proofs.append(proof(
                left_key, right_key,
                decision="merged",
                owner_anchor_id=owner_anchor_id,
                directed_path_relation_ids=path_relation_ids,
                input_node_ids=left_anchors,
                output_node_ids=right_anchors,
                reason="unique_directed_entry_output_closure",
            ))

    groups: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        groups[find(key)].append(key)
    merged_out: dict[str, dict[str, Any]] = {}
    for group_keys in groups.values():
        explicit = sorted(
            set().union(*(set(merged_rows[key].get("explicit_mechanism_ids", ())) for key in group_keys))
        )
        winner = explicit[0] if explicit else group_keys[0]
        merged: dict[str, Any] = {}
        for key in group_keys:
            row = merged_rows[key]
            for name, value in row.items():
                if name in {
                    "explicit_mechanism_ids",
                    "seed_alias_ids",
                } or isinstance(value, set):
                    merged.setdefault(name, set()).update(value or ())
                elif name == "semantic_fields":
                    current = merged.setdefault(name, [])
                    for item in value or ():
                        marker = canonical_json_bytes(item)
                        if not any(canonical_json_bytes(old) == marker for old in current):
                            current.append(item)
                else:
                    merged.setdefault(name, value)
        merged.setdefault("seed_alias_ids", set()).update(group_keys)
        merged_out[winner] = merged

    applied_lefts = {
        (item.left_seed_id, item.right_seed_id)
        for item in merge_proofs if item.decision == "merged"
    }
    survivor_keys = set(merged_out)
    for item in merge_proofs:
        if item.decision != "merged":
            continue
        if item.left_seed_id in survivor_keys and item.right_seed_id in survivor_keys:
            # Both sides survived grouping; the group winner carried the
            # merged row, so this pair's proof stays valid as the record of
            # why the rows now share one group.
            continue
    del applied_lefts
    group_proof_map: dict[str, list[MechanismMergeProofV1]] = defaultdict(list)
    for item in merge_proofs:
        if item.decision != "merged":
            continue
        roots = {find(item.left_seed_id), find(item.right_seed_id)}
        for root in roots:
            winner_key = next(
                (key for key in groups.get(root, ()) if key in merged_out),
                None,
            )
            if winner_key:
                group_proof_map[winner_key].append(item)
    for winner_key, proofs in group_proof_map.items():
        merged_out[winner_key].setdefault("merge_proofs", []).extend(proofs)

    return merged_out, tuple(merge_proofs)


def _reachable_graph_nodes(
    *,
    nodes: Mapping[str, Any],
    relations: Mapping[str, Any],
    entry_symbols: Sequence[str],
    selected_seed_ids: Sequence[str],
    max_nodes: int = 256,
) -> tuple[set[str], set[str]]:
    """Return the bounded forward executable closure of exact seed nodes.

    Reverse traversal over a typed edge turns a downstream evidence hit into
    authority for its callers and siblings.  That was the remaining
    mechanism-inflation path after owner-first seed merging was introduced.
    Only adapter-defined source→target executable relations may expand the
    closure; narrative/containment/alias edges never do.
    """

    adjacency = _executable_adjacency(nodes, relations)
    entry_starts = _entry_start_nodes(nodes, entry_symbols)
    # Owner reachability must start at a declared owner entry.  A span/fact
    # match is evidence to attach, never a traversal root: seeding the walk
    # from it let one downstream evidence hit expand the whole symbol
    # component.  Without a resolved entry the closure stays unexpanded, and
    # the exact seed nodes are still retained for audit below.
    if not entry_starts:
        return (
            {node_id for node_id in selected_seed_ids if node_id in nodes},
            set(),
        )
    seeds = entry_starts
    queue: deque[str] = deque(sorted(seeds))
    selected: set[str] = set(seeds)
    selected_relations: set[str] = set()
    while queue and len(selected) < max_nodes:
        current = queue.popleft()
        for target, rid in sorted(adjacency.get(current, ()), key=lambda item: item[1]):
            selected_relations.add(rid)
            if target not in selected:
                selected.add(target)
                queue.append(target)
                if len(selected) >= max_nodes:
                    break
    # Preserve exact obligation-bound graph nodes for audit, without allowing
    # an arbitrary downstream evidence hit to expand the executable closure.
    selected.update(
        node_id for node_id in selected_seed_ids
        if node_id in nodes
    )
    return selected, selected_relations


def _graph_node_operation(
    node: Any,
    *,
    active_status: ActivePathStatus,
    exact_excerpt: str = "",
    relation_ids: Iterable[str] = (),
    operation_id: str = "",
    source_kind: str = "",
    activation_basis_ids: Iterable[str] = (),
    recovered_guard: str = "",
) -> EvidenceOperationV1:
    recovered_basis = tuple(dict.fromkeys(_ids(activation_basis_ids))) or _ids(
        _get(node, "activation_basis_ids", ())
    )
    return EvidenceOperationV1(
        # Behavior adapters may reuse a local operation label for every
        # symbol.  The node id is the stable graph identity and prevents a
        # callee from overwriting its caller during closure assembly.
        operation_id=operation_id or _text(_get(node, "node_id")) or _text(_get(node, "operation_id")),
        symbol_id=_text(_get(node, "symbol_id")),
        predicate=_text(_get(node, "predicate")) or "unknown_operation",
        operands=_ids(_get(node, "operands", ())),
        result=_text(_get(node, "result")),
        guard=_text(recovered_guard) or _text(_get(node, "guard")),
        source_span_id=_text(_get(node, "source_span_id")),
        relation_ids=tuple(dict.fromkeys(
            (*_ids(_get(node, "relation_ids", ())), *_ids(relation_ids)
        ))),
        active_path_status=active_status,
        activation_basis_ids=recovered_basis,
        shape_or_type_hints=_ids(_get(node, "shape_or_type_hints", ())),
        source_fact_ids=_ids(_get(node, "source_fact_ids", ())),
        source_kind=_text(_get(node, "source_kind")) or source_kind or "unknown",
        exact_excerpt=exact_excerpt or _text(_get(node, "exact_excerpt")),
    )


def compile_mechanism_evidence_closures(
    *,
    argument_briefs: Any | None = None,
    facets: Iterable[Any] = (),
    facet_alignments: Iterable[Any] = (),
    field_candidates: Iterable[Any] = (),
    story_spine: Iterable[Any] = (),
    facts: Any | None = None,
    claims: Any | None = None,
    equations: Any | None = None,
    configurations: Any | None = None,
    evidence_packets: Any | None = None,
    behavior_graph: Any | None = None,
    implementation_scope: Any | None = None,
    symbol_index: Any | None = None,
    source_provider: Any | None = None,
    source_manifest: Any | None = None,
    author_config_overrides: Mapping[str, Any] | None = None,
) -> tuple[MechanismEvidenceClosureV1, ...]:
    """Compile a lossless, mechanism-scoped evidence closure.

    Facts and graph nodes are additive source representations.  The mature
    CodeFact operation-chain compiler is used whenever CodeFact artifacts are
    present; the small dict adapter below exists only for representation
    compatibility with older callers.  The Python behavior adapter is invoked
    for a supplied symbol index/source snapshot when no frozen graph is
    available.
    """

    facet_values = tuple(facets)
    alignment_values = tuple(facet_alignments)
    candidate_values = tuple(field_candidates)
    story_values = tuple(story_spine)
    seeds, ownerless_seed_ids = _collect_seed_data(
        argument_briefs=argument_briefs,
        facets=facet_values,
        facet_alignments=alignment_values,
        field_candidates=candidate_values,
        story_spine=story_values,
        facts=facts,
        claims=claims,
        equations=equations,
        configurations=configurations,
        evidence_packets=evidence_packets,
        implementation_scope=implementation_scope,
        symbol_index=symbol_index,
    )
    resolver = DefinitionResolver(symbol_index=symbol_index, source_provider=source_provider)
    # Fact scopes and field candidates may carry an exact indexed qname rather
    # than a SymbolRef id.  Promote such a value to an entry only in the
    # unambiguous single-mechanism case; for multiple mechanisms it remains a
    # candidate handle until an explicit entry binding is supplied.
    if symbol_index and len(seeds) == 1:
        sole_row = next(iter(seeds.values()))
        if not sole_row["entry_symbol_ids"]:
            for candidate in tuple(sole_row["candidate_symbol_ids"]):
                symbol = resolver.resolve_symbol(candidate)
                if symbol is not None:
                    symbol_id = _text(_get(symbol, "symbol_id"))
                    if symbol_id:
                        sole_row["entry_symbol_ids"].add(symbol_id)
    # A source index can provide the initial entry symbols after the intent
    # merge.  Build the adapter graph once with all explicit entries if the
    # caller did not already provide one.
    graph = behavior_graph
    if graph is None and symbol_index:
        entry_ids = tuple(dict.fromkeys(
            symbol for row in seeds.values() for symbol in row["entry_symbol_ids"]
        ))
        graph = _build_adapter_graph(
            symbol_index=symbol_index,
            source_provider=source_provider,
            entry_symbol_ids=entry_ids,
        )

    # Narrative-only rows are organization metadata, not executable owners.
    # Keep their IDs in the unresolved sidecar and remove them before the
    # mechanism merge so they cannot bridge unrelated source closures.
    narrative_seed_ids = {
        str(key) for key, row in seeds.items()
        if row.get("seed_kind") != "executable"
    }
    ownerless_seed_ids.update(narrative_seed_ids)
    seed_count_before_merge = len(seeds)
    seeds = {
        str(key): row for key, row in seeds.items()
        if row.get("seed_kind") == "executable"
    }
    # Reconcile organization fragments only after the exact graph (including
    # an adapter-built graph) is available.  This prevents one story node per
    # mechanism fragmentation while keeping unrelated explicit mechanisms
    # isolated.
    seeds, merge_proof_rows = _merge_mechanism_seed_rows(seeds, facts=facts, graph=graph)
    graph_nodes, graph_relations, unresolved_relations = _graph_parts(graph)
    # Recover each graph node's dominating branch guard from the frozen typed
    # TRUE_BRANCH/FALSE_BRANCH/guarded CONTROL_DEPENDS_ON relations (bounded
    # by span containment plus NEXT_CONTROL stay-inside).  A graph node whose
    # own guard is empty but is provably dominated by a typed branch then
    # resolves to the same conditional semantics as its fact-view twin
    # instead of collapsing the mixed status to unknown.  Guarded edges whose
    # dominance is unbounded, or that claim both polarities for one guard,
    # are reported instead of being aligned.
    (
        dominated_guards,
        unproven_dominance,
        conflicted_dominance,
    ) = _branch_dominance_guards(graph_nodes, graph_relations)
    # Span-level dominance: when an operation at one exact span is proven
    # condition-dominated by typed relations, every operation at that same
    # span shares the same code location and therefore the same guard.  The
    # proof is bounded to the exact span (never the file or the symbol), the
    # symbol scope must agree, and a span where any guarded typed edge is
    # unproven or contradictory is excluded so the two views cannot be
    # silently aligned on contested evidence.
    span_dominance: dict[str, tuple[str, tuple[str, ...], str]] = {}
    contested_spans: set[str] = set()
    for dominated_node_id, (conjuncts, relation_ids) in dominated_guards.items():
        span = _text(_get(graph_nodes.get(dominated_node_id), "source_span_id"))
        symbol = _text(_get(graph_nodes.get(dominated_node_id), "symbol_id"))
        if not span or not symbol:
            continue
        guard_text = " and ".join(conjuncts)
        existing = span_dominance.get(span)
        if existing is not None and (
            existing[0] != guard_text or existing[2] != symbol
        ):
            contested_spans.add(span)
            continue
        span_dominance[span] = (guard_text, relation_ids, symbol)
    for contested_node_id in (*unproven_dominance, *conflicted_dominance):
        span = _text(_get(graph_nodes.get(contested_node_id), "source_span_id"))
        if span:
            contested_spans.add(span)
    for span in contested_spans:
        span_dominance.pop(span, None)

    def resolve_typed_guard(
        node_id: str,
        span_id: str,
        symbol_name: str,
        own_guard: str,
        explicit_status: str,
    ) -> tuple[str, tuple[str, ...], str]:
        """Resolve one operation's guard from typed dominance evidence.

        Returns ``(guard, activation_basis_ids, explicit_status)``.  A node's
        own guard or explicit path status always wins.  Otherwise node-level
        typed dominance applies, then the exact-span proof, while unproven or
        contradictory dominance is reported and never silently aligned.
        """

        if own_guard or explicit_status:
            return own_guard, (), explicit_status
        conflict = conflicted_dominance.get(node_id)
        if conflict:
            conflict_guard, conflict_relations = conflict
            return (
                "",
                (f"path_polarity_conflict:{conflict_guard}", *conflict_relations),
                "unknown",
            )
        recovered = dominated_guards.get(node_id)
        if recovered:
            conjuncts, relation_ids = recovered
            return " and ".join(conjuncts), relation_ids, explicit_status
        unproven = unproven_dominance.get(node_id)
        if unproven:
            unproven_guard, unproven_relations = unproven
            return (
                own_guard,
                (f"unproven_dominance:{unproven_guard}", *unproven_relations),
                explicit_status,
            )
        span_proof = span_dominance.get(span_id)
        if span_proof is not None and span_proof[2] == symbol_name:
            guard_text, relation_ids, _symbol = span_proof
            return (
                guard_text,
                (f"same_span_dominance:{span_id}", *relation_ids),
                explicit_status,
            )
        return own_guard, (), explicit_status
    fact_values = _items(facts, "facts")
    fact_by_id = {
        _text(_get(item, "fact_id")): item
        for item in fact_values if _text(_get(item, "fact_id"))
    }
    claim_values = _items(claims, "claims")
    equation_values = _items(equations, "equations")
    config_values = _items(configurations, "claims")
    packet_values = _items(evidence_packets, "packets")
    claim_by_id = {
        _text(_get(item, "claim_id")): item
        for item in claim_values if _text(_get(item, "claim_id"))
    }
    equation_by_id = {
        _text(_get(item, "equation_id")): item
        for item in equation_values if _text(_get(item, "equation_id"))
    }
    scope_dump = _dump(implementation_scope)
    scope_role_sets = {
        "target_core": set(_ids(scope_dump.get("target_core_symbol_ids", ()))),
        "target_dependency": set(_ids(scope_dump.get("target_dependency_symbol_ids", ()))),
        "comparand": set(_ids(scope_dump.get("comparand_symbol_ids", ()))),
        "evaluation": set(_ids(scope_dump.get("evaluation_symbol_ids", ()))),
        "configuration": set(_ids(scope_dump.get("configuration_symbol_ids", ()))),
    }

    source_span_failures: list[str] = []

    def source_entry_for_span(span_id: str) -> tuple[Any | None, str]:
        """Resolve one span to its manifest entry and a typed failure.

        Legacy V1 callers may omit the source manifest and retain their older
        diagnostic behavior.  Once a manifest is supplied (the unified lane),
        an invalid handle or unknown path is recorded as an unresolved source
        item instead of being silently converted into a verified-looking
        ``unknown`` operation.
        """

        if source_manifest is None:
            return None, ""
        if not span_id:
            return None, "unified_source_span_unmapped:empty_span"
        match = re.match(r"^span:(.*):(\d+):(\d+)$", str(span_id))
        if match is None:
            return None, f"unified_source_span_unmapped:{span_id}"
        path = normalize_source_path(match.group(1))
        entry_for = getattr(source_manifest, "entry_for", None)
        entry = entry_for(path) if callable(entry_for) else None
        if entry is None:
            for item in (_get(source_manifest, "entries", ()) or ()):
                if normalize_source_path(_text(_get(item, "path"))) == path:
                    entry = item
                    break
        if entry is None:
            return None, f"unified_source_span_unmapped:{span_id}"
        if not _text(_get(entry, "content_digest")):
            return None, f"unified_source_entry_digest_missing:{path}"
        return entry, ""

    def source_kind_for_span(span_id: str) -> str:
        """Resolve a source kind from a ``span:path:start:end`` handle."""

        entry, failure = source_entry_for_span(span_id)
        if failure:
            source_span_failures.append(failure)
        return _text(_get(entry, "source_kind")) or "unknown"

    excluded_source_kinds = {
        "vendor", "generated", "submodule", "dataset_or_checkpoint",
    }

    def exact_symbol_id(value: str) -> str:
        symbol = resolver.resolve_symbol(value)
        return _text(_get(symbol, "symbol_id")) if symbol is not None else ""

    def path_resolution_inputs(
        symbol_id: str,
        raw_symbol: str,
        entry_ids: set[str],
    ) -> tuple[str, bool | None, str]:
        candidates = {item for item in (symbol_id, raw_symbol) if item}
        role = next(
            (name for name, values in scope_role_sets.items() if candidates.intersection(values)),
            "",
        )
        if role in {"comparand", "evaluation"}:
            return "inactive_default", None, role
        if candidates.intersection(entry_ids):
            return "active_default", True, role
        if not entry_ids:
            return "active_default", None, role
        if role in {"target_core", "target_support"}:
            # Ownership says whose code this is; it does not prove that the
            # operation lies on the selected runtime path.
            return "unknown", None, role
        return "active_default" if not scope_role_sets else "unknown", None, role
    graph_node_to_operation: dict[str, str] = {}

    closures: list[MechanismEvidenceClosureV1] = []
    for mechanism_id, seed in sorted(seeds.items()):
        source_span_failure_start = len(source_span_failures)
        seed_aliases = set(seed.get("seed_alias_ids", ())) | {str(mechanism_id)}
        closure_merge_proofs = tuple(
            proof for proof in merge_proof_rows
            if {
                _text(_get(proof, "left_seed_id")),
                _text(_get(proof, "right_seed_id")),
            } & seed_aliases
        )
        requested_fact_ids = tuple(sorted(seed["bound_fact_ids"]))
        fact_chain = _compile_fact_chain(facts, requested_fact_ids)
        fact_atoms = list(fact_chain["operation_atoms"])
        exact_span_set = set(seed["bound_span_ids"])
        for atom in fact_atoms:
            exact_span_set.update(_ids(atom.get("span_ids", ())))
        fact_symbols = {
            _text(_get(fact_by_id.get(fid), "scope") or _get(fact_by_id.get(fid), "subject"))
            for fid in fact_chain["fact_ids"]
        }
        fact_symbols.discard("")
        fact_symbols.update(
            resolved_id
            for raw_symbol in tuple(fact_symbols)
            for resolved_id in (exact_symbol_id(raw_symbol),)
            if resolved_id
        )
        candidate_symbols = (
            set(seed["entry_symbol_ids"])
            | fact_symbols
            | set(seed["candidate_symbol_ids"])
            | set(seed["scope_target_symbol_ids"])
            | set(seed["scope_configuration_symbol_ids"])
        )
        owner_entry_symbols = set(seed["entry_symbol_ids"])
        selected_seed_nodes = {
            node_id for node_id, node in graph_nodes.items()
            if _text(_get(node, "source_span_id")) in exact_span_set
        }
        selected_graph_nodes, selected_graph_relations = _reachable_graph_nodes(
            nodes=graph_nodes,
            relations=graph_relations,
            entry_symbols=tuple(owner_entry_symbols),
            selected_seed_ids=tuple(selected_seed_nodes),
        )
        if selected_graph_nodes:
            exact_span_set.update(
                _text(_get(graph_nodes[node_id], "source_span_id"))
                for node_id in selected_graph_nodes
                if _text(_get(graph_nodes[node_id], "source_span_id"))
            )

        # Reachability is calculated from explicit graph edges, not names.
        executable_adjacency = _executable_adjacency(graph_nodes, graph_relations)
        entry_node_ids = _entry_start_nodes(
            graph_nodes,
            seed["entry_symbol_ids"],
        )
        reachable_nodes, _reachable_relation_ids = _reachable_closure(
            executable_adjacency,
            entry_node_ids,
        )

        operations: list[EvidenceOperationV1] = []
        excluded_source_items: list[str] = []
        seen_operations: set[str] = set()
        for atom in fact_atoms:
            operation_id = _text(atom.get("operation_id")) or f"fact-operation:{atom.get('fact_id')}"
            span_id = _text(atom.get("source_span_id") or next(iter(_ids(atom.get("span_ids", ()))), ""))
            raw_symbol_name = _text(atom.get("scope") or atom.get("subject"))
            symbol_name = exact_symbol_id(raw_symbol_name) or raw_symbol_name
            source_kind = source_kind_for_span(span_id)
            if source_kind in excluded_source_kinds:
                excluded_source_items.append(
                    f"excluded_source_authority:{source_kind}:{span_id or operation_id}"
                )
            explicit_status = _text(atom.get("active_path_status"))
            default_branch, reachable_flag, scope_kind = path_resolution_inputs(
                symbol_name, raw_symbol_name, set(seed["entry_symbol_ids"])
            )
            matching_graph_nodes = {
                node_id for node_id, node in graph_nodes.items()
                if (
                    span_id
                    and _text(_get(node, "source_span_id")) == span_id
                ) or (
                    _text(atom.get("fact_id"))
                    and _text(atom.get("fact_id"))
                    in set(_ids(_get(node, "source_fact_ids", ())))
                )
            }
            if entry_node_ids and matching_graph_nodes:
                reachable_flag = bool(matching_graph_nodes.intersection(reachable_nodes))
            if scope_kind in {"comparand", "evaluation"} and not explicit_status:
                explicit_status = "inactive_default"
            atom_guard, atom_basis, explicit_status = resolve_typed_guard(
                "",
                span_id,
                symbol_name,
                _text(atom.get("guard")),
                explicit_status,
            )
            status = resolve_active_path_status(
                symbol_name=symbol_name,
                operation_id=operation_id,
                source_span_id=span_id,
                guard=atom_guard,
                config_bindings=config_values,
                author_config_overrides=author_config_overrides,
                default_branch=default_branch,
                reachable=reachable_flag,
                explicit_status=explicit_status,
            )
            op = EvidenceOperationV1(
                operation_id=operation_id,
                symbol_id=symbol_name,
                predicate=_text(atom.get("predicate")) or "unknown_operation",
                operands=_ids(atom.get("operands", ())),
                result=_text(atom.get("result")),
                guard=atom_guard,
                source_span_id=span_id,
                relation_ids=_ids(atom.get("relation_evidence_ids", ())),
                active_path_status=status,
                activation_basis_ids=tuple(dict.fromkeys(
                    (*_ids(atom.get("activation_basis_ids", ())), *atom_basis)
                )),
                shape_or_type_hints=_ids(atom.get("shape_or_type_hints", ())),
                source_fact_ids=(_text(atom.get("fact_id")),) if _text(atom.get("fact_id")) else (),
                source_kind=source_kind,
                exact_excerpt=_text(atom.get("exact_excerpt")),
            )
            if operation_id not in seen_operations:
                operations.append(op)
                seen_operations.add(operation_id)

        for node_id in sorted(selected_graph_nodes):
            node = graph_nodes[node_id]
            operation_id = f"graph-operation:{node_id}"
            graph_node_to_operation[node_id] = operation_id
            if operation_id in seen_operations:
                continue
            span_id = _text(_get(node, "source_span_id"))
            raw_symbol_name = _text(_get(node, "symbol_id"))
            symbol_name = exact_symbol_id(raw_symbol_name) or raw_symbol_name
            source_kind = source_kind_for_span(span_id)
            if source_kind in excluded_source_kinds:
                excluded_source_items.append(
                    f"excluded_source_authority:{source_kind}:{span_id or operation_id}"
                )
            config_matches = tuple(
                binding for binding in config_values
                if (
                    symbol_name in set(_ids(_get(binding, "symbol_ids", ())))
                    or symbol_name == _text(_get(binding, "symbol_id"))
                    or span_id in set(_ids(_get(binding, "entrypoint_span_ids", ())))
                    or operation_id == _text(_get(binding, "operation_id"))
                    or _text(_get(node, "operation_id")) == _text(_get(binding, "operation_id"))
                )
            )
            excerpt = resolver.read_span_id(span_id)
            default_branch, reachable_flag, scope_kind = path_resolution_inputs(
                symbol_name, raw_symbol_name, set(seed["entry_symbol_ids"])
            )
            explicit_status = _text(_get(node, "active_path_status"))
            if scope_kind in {"comparand", "evaluation"} and not explicit_status:
                explicit_status = "inactive_default"
            node_guard = _text(_get(node, "guard"))
            node_guard, recovered_basis, explicit_status = resolve_typed_guard(
                node_id,
                span_id,
                symbol_name,
                node_guard,
                explicit_status,
            )
            status = resolve_active_path_status(
                symbol_name=symbol_name,
                operation_id=operation_id,
                source_span_id=span_id,
                guard=node_guard,
                config_bindings=config_matches,
                author_config_overrides=author_config_overrides,
                default_branch=default_branch,
                reachable=(node_id in reachable_nodes) if entry_node_ids else reachable_flag,
                explicit_status=explicit_status,
            )
            node_relation_ids = tuple(
                rid for rid, relation in graph_relations.items()
                if rid in selected_graph_relations
                and (
                    _relation_endpoint(relation, "source", graph_nodes) == node_id
                    or _relation_endpoint(relation, "target", graph_nodes) == node_id
                )
            )
            operations.append(_graph_node_operation(
                node,
                active_status=status,
                exact_excerpt=excerpt,
                relation_ids=node_relation_ids,
                operation_id=operation_id,
                source_kind=source_kind,
                activation_basis_ids=recovered_basis,
                recovered_guard=node_guard,
            ))
            seen_operations.add(operation_id)

        # A persisted graph may have been built at depth zero or may be a
        # caller-supplied partial graph.  Close exact CALLS targets through the
        # SymbolIndexV2 and SourceProvider so the callee body becomes ordinary
        # EvidenceOperationV1 records in this same closure.  A missing body is
        # an explicit unresolved item; it is never represented by a synthetic
        # operation or a prose placeholder.
        callee_unresolved: list[str] = []
        if symbol_index and source_provider:
            try:
                from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter

                adapter = PythonBehaviorAdapter()
                source_files = _source_provider_files(source_provider)
                call_targets: list[tuple[str, str]] = []
                for rid in sorted(selected_graph_relations):
                    relation = graph_relations.get(rid)
                    if _text(_get(relation, "kind")).upper() != "CALLS":
                        continue
                    source_node_id = _relation_endpoint(relation, "source", graph_nodes)
                    target_symbol_id = _text(_get(relation, "target_symbol_id"))
                    if source_node_id in selected_graph_nodes and target_symbol_id:
                        call_targets.append((target_symbol_id, rid))
                for operation in operations:
                    if operation.predicate.upper() not in {"CALL", "CALLS"} or not operation.operands:
                        continue
                    target = resolver.resolve_symbol(operation.operands[0], current_path="")
                    target_id = _text(_get(target, "symbol_id"))
                    if target_id:
                        call_targets.append((target_id, ""))
                existing_symbol_ids = {operation.symbol_id for operation in operations if operation.symbol_id}
                unique_targets = list(dict.fromkeys(call_targets))
                target_pairs = unique_targets
                if resolver.max_callees is not None:
                    target_pairs = unique_targets[: max(0, resolver.max_callees)]
                for target_symbol_id, relation_id in target_pairs:
                    if target_symbol_id in existing_symbol_ids:
                        continue
                    target_symbol = resolver.resolve_symbol(target_symbol_id)
                    if target_symbol is None:
                        callee_unresolved.append(f"definition_missing:{target_symbol_id}")
                        continue
                    source_text = source_files.get(_text(_get(target_symbol, "path")))
                    if not source_text:
                        source_text = resolver.read_file(_text(_get(target_symbol, "path")))
                    if not source_text:
                        callee_unresolved.append(f"definition_missing:{target_symbol_id}")
                        continue
                    callee_nodes = adapter.extract_operations(target_symbol, source_text)
                    if not callee_nodes:
                        callee_unresolved.append(f"definition_operations_missing:{target_symbol_id}")
                        continue
                    for callee_node in callee_nodes:
                        callee_node_id = _text(_get(callee_node, "node_id"))
                        callee_operation_id = f"graph-operation:{callee_node_id}"
                        if callee_operation_id in seen_operations:
                            continue
                        raw_symbol_name = _text(_get(callee_node, "symbol_id")) or target_symbol_id
                        symbol_name = exact_symbol_id(raw_symbol_name) or raw_symbol_name
                        default_branch, reachable_flag, scope_kind = path_resolution_inputs(
                            symbol_name, raw_symbol_name, set(seed["entry_symbol_ids"])
                        )
                        explicit_status = "inactive_default" if scope_kind in {"comparand", "evaluation"} else ""
                        callee_guard, callee_basis, explicit_status = resolve_typed_guard(
                            callee_node_id,
                            _text(_get(callee_node, "source_span_id")),
                            symbol_name,
                            _text(_get(callee_node, "guard")),
                            explicit_status,
                        )
                        status = resolve_active_path_status(
                            symbol_name=symbol_name,
                            operation_id=callee_operation_id,
                            source_span_id=_text(_get(callee_node, "source_span_id")),
                            guard=callee_guard,
                            config_bindings=config_values,
                            author_config_overrides=author_config_overrides,
                            default_branch=default_branch,
                            reachable=reachable_flag,
                            explicit_status=explicit_status,
                        )
                        callee_source_kind = source_kind_for_span(
                            _text(_get(callee_node, "source_span_id"))
                        )
                        if callee_source_kind in excluded_source_kinds:
                            excluded_source_items.append(
                                "excluded_source_authority:"
                                f"{callee_source_kind}:{_text(_get(callee_node, 'source_span_id')) or callee_operation_id}"
                            )
                        operations.append(_graph_node_operation(
                            callee_node,
                            active_status=status,
                            exact_excerpt=resolver.read_span_id(_text(_get(callee_node, "source_span_id"))),
                            relation_ids=(relation_id,) if relation_id else (),
                            operation_id=callee_operation_id,
                            source_kind=callee_source_kind,
                            activation_basis_ids=callee_basis,
                            recovered_guard=callee_guard,
                        ))
                        seen_operations.add(callee_operation_id)
                        span = _text(_get(callee_node, "source_span_id"))
                        if span:
                            exact_span_set.add(span)
                    existing_symbol_ids.add(target_symbol_id)
                if (
                    resolver.max_callees is not None
                    and len(unique_targets) > resolver.max_callees
                ):
                    callee_unresolved.append(
                        f"callee_budget_exhausted:{len(unique_targets)}:{resolver.max_callees}"
                    )
            except Exception as exc:
                callee_unresolved.append(f"callee_expansion_error:{exc.__class__.__name__}")

        # Adapter-produced operations can carry source spans that were not in
        # the initial seed span set.  Add them before building the aligned
        # exact-span/excerpt arrays so the closure cannot contain an operation
        # whose source anchor is absent from its evidence index.
        exact_span_set.update(
            operation.source_span_id
            for operation in operations
            if operation.source_span_id
        )
        relation_ids = set(selected_graph_relations)
        relation_ids.update(fact_chain.get("relation_evidence_ids", ()))
        call_relation_ids: list[str] = []
        data_relation_ids: list[str] = []
        control_relation_ids: list[str] = []
        for rid in sorted(relation_ids):
            relation = graph_relations.get(rid)
            kind = _text(_get(relation, "kind")).upper()
            if kind in {"CALLS", "RETURNS_TO", "IMPLEMENTS", "OVERRIDES"}:
                call_relation_ids.append(rid)
            elif kind in {"DATA_DEPENDS_ON", "READS_FROM", "WRITES_TO", "ALIAS_OF"}:
                data_relation_ids.append(rid)
            elif kind in {"NEXT_CONTROL", "CONTROL_DEPENDS_ON", "TRUE_BRANCH", "FALSE_BRANCH"}:
                control_relation_ids.append(rid)

        # Keep the span/excerpt relation deterministic.  The old positional
        # list appended callee bodies after operation excerpts, so a consumer
        # could associate the wrong text with a span.  Every exact span now has
        # one corresponding entry (possibly empty when the provider could not
        # read it); operation-level excerpts remain in the operation record.
        exact_excerpt_by_span: dict[str, str] = {}
        for atom in fact_atoms:
            excerpt = _text(atom.get("exact_excerpt"))
            for span in _ids(atom.get("span_ids", ())):
                if excerpt and span not in exact_excerpt_by_span:
                    exact_excerpt_by_span[span] = excerpt
        for operation in operations:
            if operation.source_span_id and operation.exact_excerpt:
                exact_excerpt_by_span.setdefault(operation.source_span_id, operation.exact_excerpt)
        for packet in packet_values:
            for span in (_get(packet, "spans", ()) or ()):
                span_id = _text(_get(span, "span_id"))
                excerpt = _text(_get(span, "exact_excerpt"))
                if span_id and excerpt:
                    exact_excerpt_by_span.setdefault(span_id, excerpt)
        for span_id in tuple(exact_span_set):
            if span_id not in exact_excerpt_by_span:
                excerpt = resolver.read_span_id(span_id)
                if excerpt:
                    exact_excerpt_by_span[span_id] = excerpt
        ordered_exact_span_ids = tuple(sorted(exact_span_set, key=_span_order))
        exact_excerpts = [exact_excerpt_by_span.get(span_id, "") for span_id in ordered_exact_span_ids]

        relevant_configs: list[dict[str, Any]] = []
        for config in config_values:
            config_spans = set(_ids(_get(config, "definition_span_ids", ()))) | set(
                _ids(_get(config, "entrypoint_span_ids", ()))
            )
            config_symbols = set(_ids(_get(config, "symbol_ids", ()))) | set(
                _ids(_get(config, "bound_symbol_ids", ()))
            )
            config_fact_ids = set(_ids(_get(config, "source_fact_ids", ())))
            config_operation_id = _text(_get(config, "operation_id"))
            if (
                config_spans.intersection(exact_span_set)
                or config_symbols.intersection({op.symbol_id for op in operations})
                or _canonical_mechanism_id(_get(config, "mechanism_id")) == mechanism_id
                or config_fact_ids.intersection(seed["bound_fact_ids"])
                or config_operation_id in {op.operation_id for op in operations}
            ):
                relevant_configs.append(_dump(config))

        unresolved_items = list(fact_chain.get("diagnostics", ()))
        unresolved_items.extend(callee_unresolved)
        unresolved_items.extend(excluded_source_items)
        unresolved_items.extend(source_span_failures[source_span_failure_start:])
        for unresolved in unresolved_relations:
            source_node = _text(_get(unresolved, "source_node_id"))
            source_symbol = _text(_get(unresolved, "source_symbol_id"))
            if source_node in selected_graph_nodes or source_symbol in candidate_symbols:
                rid = _text(_get(unresolved, "relation_id"))
                if rid:
                    unresolved_items.append(f"unresolved_relation:{rid}")
        if symbol_index and seed["entry_symbol_ids"] and graph is None:
            unresolved_items.append("behavior_subgraph_unresolved")
        if symbol_index and not seed["entry_symbol_ids"] and seed["candidate_symbol_ids"]:
            unresolved_items.append("entry_symbol_unresolved")
        unresolved_items.extend(
            f"active_path_unknown:{op.operation_id}"
            for op in operations if op.active_path_status == "unknown"
        )
        # Every operation-level source membership must be represented in the
        # closure indexes before the typed closure is frozen.  Graph adapters
        # may contribute fact/span handles that were not part of the initial
        # requested fact chain; dropping those handles would make the closure
        # look typed while silently losing evidence.
        operation_fact_ids = {
            fact_id
            for operation in operations
            for fact_id in operation.source_fact_ids
            if fact_id
        }
        active_conditions = list(_ids(
            op.guard for op in operations if op.guard
        ))
        for config in relevant_configs:
            active_conditions.extend(_ids(_get(config, "conditions", ())))

        statuses = {op.active_path_status for op in operations}
        if "active_selected" in statuses:
            default_activation: ActivePathStatus = "active_selected"
        elif "active_default" in statuses:
            default_activation = "active_default"
        elif "conditional" in statuses:
            default_activation = "conditional"
        elif statuses and statuses.issubset(_INACTIVE_STATUSES):
            default_activation = "inactive_default"
        else:
            default_activation = "unknown"

        operation_dispositions = tuple(
            SourceOperationDispositionV1(
                operation_id=op.operation_id,
                disposition="explicitly_unresolved",
                detail_ids=(),
                reason_code="awaiting_paper_detail_annotation",
            )
            for op in operations
        )
        source_digests = {
            key: value for key, value in {
                "behavior_graph": _source_digest(graph),
                "facts": _source_digest(facts),
                "claims": _source_digest(claims),
                "equations": _source_digest(equations),
                "evidence_packets": _source_digest(evidence_packets),
                "implementation_scope": _source_digest(implementation_scope),
                "symbol_index": _source_digest(symbol_index),
                "source_provider": _source_digest(source_provider),
                "repository_source_manifest": _source_digest(source_manifest),
            }.items() if value
        }
        closure = MechanismEvidenceClosureV1(
            closure_id=f"closure:{mechanism_id}",
            mechanism_id=mechanism_id,
            repo_snapshot_id=_text(
                _get(graph, "repo_snapshot_id")
                or _get(symbol_index, "repo_snapshot_id")
                or _get(source_provider, "snapshot_id")
            ),
            project_tree_hash=_text(
                _get(graph, "project_tree_hash")
                or _get(symbol_index, "project_tree_hash")
                or _get(source_provider, "project_tree_hash")
            ),
            seed_story_node_ids=tuple(sorted(seed["story_node_ids"])),
            seed_brief_ids=tuple(sorted(seed["brief_ids"])),
            seed_facet_ids=tuple(sorted(seed["facet_ids"])),
            seed_obligation_ids=tuple(sorted(seed["obligation_ids"])),
            seed_author_statements=tuple(sorted(seed["author_statements"])),
            seed_kind=str(seed.get("seed_kind", "executable")),
            owner_anchor_id=str(
                next(iter(sorted(seed.get("entry_symbol_ids", ()) or ())), "")
            ),
            merge_proof_ids=tuple(
                str(proof.content_digest)
                for proof in closure_merge_proofs
                if getattr(proof, "content_digest", "")
            ),
            unresolved_seed_ids=tuple(sorted(ownerless_seed_ids)),
            merge_proofs=closure_merge_proofs,
            entry_symbol_ids=tuple(sorted(seed["entry_symbol_ids"])),
            operation_nodes=tuple(operations),
            call_relation_ids=tuple(call_relation_ids),
            data_flow_relation_ids=tuple(data_relation_ids),
            control_flow_relation_ids=tuple(control_relation_ids),
            configuration_bindings=tuple(relevant_configs),
            active_path_conditions=tuple(dict.fromkeys(active_conditions)),
            default_activation=default_activation,
            fact_ids=tuple(sorted(set(fact_chain["fact_ids"]) | operation_fact_ids)),
            claim_ids=tuple(sorted(seed["bound_claim_ids"])),
            equation_ids=tuple(sorted(seed["bound_equation_ids"])),
            exact_span_ids=ordered_exact_span_ids,
            # Keep positional alignment with ``exact_span_ids``.  Two source
            # spans are allowed to have the same excerpt; de-duplicating this
            # parallel array would associate later spans with the wrong text.
            exact_excerpts=tuple(exact_excerpts),
            source_digests=source_digests,
            shape_or_type_hints=tuple(dict.fromkeys(
                [*_ids(fact_chain.get("shape_or_type_hints", ())), *(
                    hint for node_id in selected_graph_nodes
                    for hint in _ids(_get(graph_nodes[node_id], "shape_or_type_hints", ()))
                )]
            )),
            return_value_descriptors=tuple(dict.fromkeys(
                [*_ids(fact_chain.get("return_value_descriptors", ())), *(
                    _text(_get(node, "result")) for node_id, node in graph_nodes.items()
                    if node_id in selected_graph_nodes and _text(_get(node, "predicate")).upper() == "RETURN"
                )]
            )),
            unresolved_items=tuple(dict.fromkeys(item for item in unresolved_items if item)),
            operation_dispositions=operation_dispositions,
            source_operation_terminal_coverage=1.0 if operations else 0.0,
            budget_exhausted=bool(_get(graph, "warnings", ())) and any(
                "budget" in _text(w).casefold() for w in (_get(graph, "warnings", ()) or ())
            ),
        )
        closures.append(closure)
    return tuple(closures)


class _UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent.get(value, value)
        if parent != value:
            parent = self.find(parent)
            self.parent[value] = parent
        return parent

    def union(self, left: str, right: str) -> None:
        if left not in self.parent or right not in self.parent:
            return
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _operation_clusters(
    closure: MechanismEvidenceClosureV1,
) -> tuple[tuple[EvidenceOperationV1, ...], ...]:
    """Cluster operations by explicit source-level producer/consumer links.

    A paper detail is allowed to span several operations, but only when the
    closure provides a concrete reason for the grouping: a shared relation or
    fact, a common source statement, a producer result consumed by another
    operation, or an explicitly shared guard.  This keeps unrelated operations
    separate without reintroducing positional ``first N`` compression.
    """

    operations = tuple(closure.operation_nodes)
    if not operations:
        return ()
    by_id = {op.operation_id: op for op in operations}
    uf = _UnionFind(by_id)
    span_sets: dict[str, set[str]] = {
        operation.operation_id: (
            {operation.source_span_id} if operation.source_span_id else set()
        )
        for operation in operations
    }

    def _guarded_union(left_id: str, right_id: str) -> bool:
        """Union only while the merged group still names one source location.

        A paper detail is one code step.  Allowing transitive unions to bridge
        two distinct spans (through an unspanned operation) rebuilt the
        symbol-component collapse this compiler exists to prevent, so the
        span set of every group is tracked and a conflicting union is refused.
        """

        left_root, right_root = uf.find(left_id), uf.find(right_id)
        if left_root == right_root:
            return True
        merged = span_sets.get(left_root, set()) | span_sets.get(right_root, set())
        if len(merged) > 1:
            return False
        uf.union(left_id, right_id)
        span_sets[uf.find(left_id)] = merged
        return True

    relation_to_ops: dict[str, list[str]] = defaultdict(list)
    for op in operations:
        for relation_id in op.relation_ids:
            relation_to_ops[relation_id].append(op.operation_id)
    for operation_ids in relation_to_ops.values():
        unique = list(dict.fromkeys(operation_ids))
        for operation_id in unique[1:]:
            _guarded_union(unique[0], operation_id)

    def values(operation: EvidenceOperationV1) -> tuple[set[str], set[str]]:
        operands = {
            str(value).strip().casefold()
            for value in operation.operands
            if str(value).strip()
        }
        results = {
            str(operation.result).strip().casefold()
        } if str(operation.result).strip() else set()
        return operands, results

    for index, left in enumerate(operations):
        left_operands, left_results = values(left)
        for right in operations[index + 1:]:
            right_operands, right_results = values(right)
            has_distinct_spans = bool(
                left.source_span_id
                and right.source_span_id
                and left.source_span_id != right.source_span_id
            )
            # Distinct source spans represent distinct code steps and must not
            # be collapsed into a single paper detail.
            if has_distinct_spans:
                continue
            same_span = bool(
                left.source_span_id
                and right.source_span_id
                and left.source_span_id == right.source_span_id
            )
            producer_consumer = bool(
                left_results.intersection(right_operands)
                or right_results.intersection(left_operands)
            )
            # Only a shared source statement or an explicit typed/data link
            # groups operations.  A shared fact or guard alone is provenance,
            # not execution order, and used to merge unrelated steps.
            shared_relation = bool(set(left.relation_ids).intersection(right.relation_ids))
            if same_span or producer_consumer or shared_relation:
                _guarded_union(left.operation_id, right.operation_id)
    groups: dict[str, list[EvidenceOperationV1]] = defaultdict(list)
    for operation in operations:
        groups[uf.find(operation.operation_id)].append(operation)
    return tuple(
        tuple(sorted(group, key=lambda op: (_span_order(op.source_span_id), op.operation_id)))
        for _, group in sorted(
            groups.items(),
            key=lambda item: min(
                (_span_order(op.source_span_id), op.operation_id)
                for op in item[1]
            ),
        )
    )


def _detail_role(
    operations: Sequence[EvidenceOperationV1],
    cluster_index: int,
    total: int,
) -> DetailRole:
    predicates = {op.predicate.upper() for op in operations}
    if predicates.intersection({"BRANCH", "COMPARE", "LOOP"}):
        return "branch" if "BRANCH" in predicates else "condition"
    if predicates.intersection({"CONFIGURED_BY", "LOAD"}):
        return "configuration"
    if predicates.intersection({"RETURN", "WRITE"}) or (
        cluster_index == total - 1 and any(op.result for op in operations)
    ):
        return "output"
    if cluster_index == 0 and any(not op.operands for op in operations):
        return "input"
    if predicates.intersection({"RESHAPE", "CONCAT", "STACK", "NORMALIZE"}):
        return "representation"
    if "CALL" in predicates and not any(op.result for op in operations):
        return "interface"
    return "transformation"


def _detail_importance(
    operations: Sequence[EvidenceOperationV1],
    *,
    role: DetailRole,
) -> DetailImportance:
    statuses = {op.active_path_status for op in operations}
    if statuses.intersection(_INACTIVE_STATUSES) or "unknown" in statuses:
        return "side_branch" if statuses.issubset(_INACTIVE_STATUSES) else "supporting"
    if role in {"branch", "condition", "configuration"}:
        # A condition/configuration that changes routing, normalization,
        # reduction, or output is part of the mechanism's core semantics.  It
        # must not be demoted solely because its AST family is ``BRANCH`` or
        # ``CONFIGURED_BY``.
        semantic_control = any(
            operation.guard
            or operation.predicate.upper() in {
                "BRANCH", "COMPARE", "CONFIGURED_BY", "NORMALIZE", "REDUCE",
                "SELECT", "SELECTS", "SELECT_TOP_K", "FILTER", "FILTERS_BY",
            }
            for operation in operations
        )
        if semantic_control and statuses.issubset(_ACTIVE_STATUSES):
            return "core"
        return "supporting"
    if role == "limitation":
        return "supporting"
    # No ordinal cutoff: all proven active core transformations are retained.
    return "core" if statuses.issubset(_ACTIVE_STATUSES) else "supporting"


def _semantic_atom_for_cluster(
    operations: Sequence[EvidenceOperationV1],
    *,
    role: DetailRole,
) -> str:
    """Describe the scientific input-operation-output relation of a cluster."""

    if not operations:
        return "Unresolved mechanism operation"
    first = operations[0]
    last = operations[-1]
    inputs = tuple(dict.fromkeys(
        operand for operation in operations for operand in operation.operands if operand
    ))
    output = str(last.result or "").strip()
    predicate = str(first.predicate or "operation").strip().replace("_", " ")
    role_label = role.replace("_", " ")
    if inputs and output:
        return f"{role_label}: {predicate} transforms {', '.join(inputs)} into {output}"
    if output:
        return f"{role_label}: {predicate} produces {output}"
    if inputs:
        return f"{role_label}: {predicate} consumes {', '.join(inputs)}"
    return f"{role_label}: {predicate} operation"


def _cluster_link_reason(
    left: EvidenceOperationV1,
    right: EvidenceOperationV1,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if left.source_span_id and left.source_span_id == right.source_span_id:
        reasons.append("same_source_span")
    left_results = {str(left.result).strip().casefold()} if left.result else set()
    right_results = {str(right.result).strip().casefold()} if right.result else set()
    left_operands = {str(value).strip().casefold() for value in left.operands if str(value).strip()}
    right_operands = {str(value).strip().casefold() for value in right.operands if str(value).strip()}
    if left_results.intersection(right_operands) or right_results.intersection(left_operands):
        reasons.append("producer_consumer")
    if set(left.source_fact_ids).intersection(right.source_fact_ids):
        reasons.append("shared_fact")
    if left.guard and right.guard and left.guard.strip() == right.guard.strip():
        reasons.append("shared_guard")
    if set(left.relation_ids).intersection(right.relation_ids):
        reasons.append("shared_relation")
    return tuple(reasons)


def _mechanism_annotation_audit(
    closure: MechanismEvidenceClosureV1,
    details: Sequence[MechanismDetailV1],
    edges: Sequence[MechanismEdgeV1],
) -> dict[str, Any]:
    """Compute explicit closure/detail completeness and cluster diagnostics."""

    core_ids = {
        detail.detail_id for detail in details if detail.importance == "core"
    }
    detail_operations = {
        detail.detail_id: tuple(
            operation for operation in closure.operation_nodes
            if operation.operation_id in set(detail.source_operation_ids)
        )
        for detail in details
    }
    # Endpoints are evidence-derived.  The old positional first/last fallback
    # made any ordered detail list look connected.  An input detail consumes a
    # source value without an upstream producer; an output detail returns or
    # writes a value, or produces one that no other operation consumes.  When
    # either endpoint set is empty the mechanism has no provable path.
    consumed_values = {
        str(operand).strip().casefold()
        for operations in detail_operations.values()
        for operation in operations
        for operand in operation.operands
        if str(operand).strip()
    }
    produced_values = {
        str(operation.result).strip().casefold()
        for operations in detail_operations.values()
        for operation in operations
        if str(operation.result).strip()
    }
    input_ids = tuple(
        detail.detail_id for detail in details
        if detail.role == "input"
        or any(
            str(operand).strip()
            and str(operand).strip().casefold() not in produced_values
            for operation in detail_operations[detail.detail_id]
            for operand in operation.operands
        )
    )
    output_ids = tuple(
        detail.detail_id for detail in details
        if any(
            str(operation.predicate or "").upper() in {"RETURN", "WRITE"}
            or (
                str(operation.result).strip()
                and str(operation.result).strip().casefold() not in consumed_values
            )
            for operation in detail_operations[detail.detail_id]
        )
    )
    # Only semantic/data-flow edges may establish completeness.  ``precedes``
    # is an ordering annotation emitted for paper organization; treating it
    # as an undirected graph made any adjacent detail list look connected.
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge.relation == "precedes":
            continue
        adjacency[edge.source_detail_id].add(edge.target_detail_id)
    # Recompute producer/consumer links from operands/results across all
    # detail pairs, not merely adjacent pairs.  This is a deterministic data
    # flow check and deliberately does not infer a link from shared span,
    # shared fact, guard, or list position.
    for left in details:
        for right in details:
            if left.detail_id == right.detail_id:
                continue
            left_results = {
                str(operation.result).strip().casefold()
                for operation in detail_operations[left.detail_id]
                if str(operation.result).strip()
            }
            right_operands = {
                str(operand).strip().casefold()
                for operation in detail_operations[right.detail_id]
                for operand in operation.operands
                if str(operand).strip()
            }
            if left_results.intersection(right_operands):
                adjacency[left.detail_id].add(right.detail_id)
    reached: set[str] = set()
    queue: deque[str] = deque(input_ids)
    while queue:
        current = queue.popleft()
        if current in reached:
            continue
        reached.add(current)
        queue.extend(sorted(adjacency.get(current, ())))
    connected_outputs = tuple(detail_id for detail_id in output_ids if detail_id in reached)

    def _can_reach_output(start: str) -> bool:
        seen: set[str] = set()
        pending: deque[str] = deque([start])
        while pending:
            current = pending.popleft()
            if current in seen:
                continue
            seen.add(current)
            if current in output_ids:
                return True
            pending.extend(sorted(adjacency.get(current, ())))
        return False

    connected_inputs = tuple(
        detail_id for detail_id in input_ids if _can_reach_output(detail_id)
    )
    # A detail is on the mechanism path only when it is reachable from an
    # evidence-derived input *and* can reach an evidence-derived terminal
    # output.  Core status is restricted to that path; everything else stays
    # supporting/side-branch evidence in the archive.
    on_path_ids = tuple(sorted(
        detail_id for detail_id in reached if _can_reach_output(detail_id)
    ))
    disconnected_core = tuple(sorted(core_ids - set(on_path_ids)))
    connected = (
        bool(input_ids)
        and bool(output_ids)
        and bool(connected_outputs)
        and bool(connected_inputs)
        and not disconnected_core
    )

    witness_complete = all(
        bool(detail.witness_atoms)
        and all(
            not atom.required or atom.source_operation_ids or atom.source_anchor_ids
            for atom in detail.witness_atoms
        )
        for detail in details
        if detail.importance == "core"
    )
    operation_complete = (
        closure.source_operation_terminal_coverage == 1.0
        and not any(
            disposition.disposition == "explicitly_unresolved"
            for disposition in closure.operation_dispositions
        )
    )
    completeness_parts = (
        float(operation_complete),
        float(connected),
        float(witness_complete),
        float(not closure.budget_exhausted),
        float(not closure.unresolved_items),
    )
    cohesion_values: list[float] = []
    merge_reasons: list[str] = []
    for detail in details:
        operations = tuple(
            operation for operation in closure.operation_nodes
            if operation.operation_id in set(detail.source_operation_ids)
        )
        if len(operations) <= 1:
            cohesion_values.append(1.0)
            continue
        possible = len(operations) * (len(operations) - 1) // 2
        linked = 0
        for index, left in enumerate(operations):
            for right in operations[index + 1:]:
                reasons = _cluster_link_reason(left, right)
                if reasons:
                    linked += 1
                    merge_reasons.append(
                        f"{detail.detail_id}:{left.operation_id}+{right.operation_id}:"
                        + ",".join(reasons)
                    )
        cohesion_values.append(linked / possible if possible else 1.0)

    split_audit: list[str] = []
    detail_for_operation = {
        operation_id: detail.detail_id
        for detail in details
        for operation_id in detail.source_operation_ids
    }
    for index, left in enumerate(closure.operation_nodes):
        for right in closure.operation_nodes[index + 1:]:
            reasons = _cluster_link_reason(left, right)
            split_reasons = tuple(
                r for r in reasons if r in {"same_source_span", "shared_fact"}
            )
            if split_reasons and detail_for_operation.get(left.operation_id) != detail_for_operation.get(right.operation_id):
                split_audit.append(
                    f"cross_detail_link:{left.operation_id}:{right.operation_id}:"
                    + ",".join(sorted(split_reasons))
                )
    merge_audit = [
        f"unowned_operation:{operation.operation_id}"
        for operation in closure.operation_nodes
        if operation.operation_id not in detail_for_operation
    ]
    denominator = max(1, len(completeness_parts))
    return {
        "connected_input_detail_ids": connected_inputs,
        "connected_output_detail_ids": connected_outputs,
        "input_detail_ids": input_ids,
        "output_detail_ids": output_ids,
        "disconnected_core_detail_ids": disconnected_core,
        "connected_input_to_output": connected,
        "on_path_detail_ids": on_path_ids,
        "core_path_endpoint_unknown": bool(details) and (not input_ids or not output_ids),
        "information_completeness": sum(completeness_parts) / denominator,
        "cluster_cohesion_score": (
            sum(cohesion_values) / len(cohesion_values) if cohesion_values else 0.0
        ),
        "cluster_merge_reasons": tuple(dict.fromkeys(merge_reasons)),
        "cluster_split_audit": tuple(dict.fromkeys(split_audit)),
        "cluster_merge_audit": tuple(dict.fromkeys(merge_audit)),
    }


def _detail_witness_atoms(
    *,
    detail_id: str,
    operations: Sequence[EvidenceOperationV1],
    exact_excerpt_by_span: Mapping[str, str],
) -> tuple[DetailWitnessAtomV1, ...]:
    atoms: list[DetailWitnessAtomV1] = []
    for operation in operations:
        source_spans = (operation.source_span_id,) if operation.source_span_id else ()
        excerpts = tuple(
            exact_excerpt_by_span[span]
            for span in source_spans
            if exact_excerpt_by_span.get(span)
        )
        atoms.append(DetailWitnessAtomV1(
            atom_id=f"atom:{detail_id}:operation:{operation.operation_id}",
            atom_kind="operation",
            semantic_anchor=f"{operation.predicate} operation",
            source_operation_ids=(operation.operation_id,),
            source_anchor_ids=source_spans,
            exact_excerpts=excerpts,
            required_polarity="positive",
        ))
        for index, operand in enumerate(operation.operands):
            atoms.append(DetailWitnessAtomV1(
                atom_id=f"atom:{detail_id}:operand:{operation.operation_id}:{index}",
                atom_kind="operand",
                semantic_anchor=operand,
                source_operation_ids=(operation.operation_id,),
                source_anchor_ids=source_spans,
                exact_excerpts=excerpts,
            ))
        if operation.result:
            atoms.append(DetailWitnessAtomV1(
                atom_id=f"atom:{detail_id}:output:{operation.operation_id}",
                atom_kind="output",
                semantic_anchor=operation.result,
                source_operation_ids=(operation.operation_id,),
                source_anchor_ids=source_spans,
                exact_excerpts=excerpts,
            ))
        if operation.guard:
            atoms.append(DetailWitnessAtomV1(
                atom_id=f"atom:{detail_id}:condition:{operation.operation_id}",
                atom_kind="condition",
                semantic_anchor=operation.guard,
                source_operation_ids=(operation.operation_id,),
                source_anchor_ids=source_spans,
                exact_excerpts=excerpts,
                required_conditions=(operation.guard,),
                required_polarity="conditional",
            ))
        if operation.predicate.upper() in {"BRANCH", "COMPARE"}:
            atoms.append(DetailWitnessAtomV1(
                atom_id=f"atom:{detail_id}:polarity:{operation.operation_id}",
                atom_kind="polarity",
                semantic_anchor=operation.guard or operation.predicate,
                source_operation_ids=(operation.operation_id,),
                source_anchor_ids=source_spans,
                exact_excerpts=excerpts,
                required_polarity="conditional" if operation.guard else "positive",
            ))
        if operation.predicate.upper() == "CALL":
            atoms.append(DetailWitnessAtomV1(
                atom_id=f"atom:{detail_id}:interface:{operation.operation_id}",
                atom_kind="interface",
                semantic_anchor=operation.symbol_id or operation.predicate,
                source_operation_ids=(operation.operation_id,),
                source_anchor_ids=source_spans,
                exact_excerpts=excerpts,
            ))
        if operation.predicate.upper() in {"COMPUTE", "REDUCE", "NORMALIZE", "PROJECT", "ATTEND"}:
            atoms.append(DetailWitnessAtomV1(
                atom_id=f"atom:{detail_id}:formal:{operation.operation_id}",
                atom_kind="formal_relation",
                semantic_anchor=operation.result or operation.predicate,
                source_operation_ids=(operation.operation_id,),
                source_anchor_ids=source_spans,
                exact_excerpts=excerpts,
            ))
    return tuple(atoms)


def _intent_rows(
    *,
    mechanism_id: str,
    story_spine: Sequence[Any],
    argument_briefs: Any,
    facets: Sequence[Any],
    closure: MechanismEvidenceClosureV1 | None = None,
) -> dict[str, tuple[str, ...]]:
    row: dict[str, list[str]] = {
        "story_node_ids": [], "brief_ids": [], "facet_ids": [],
        "obligation_ids": [], "author_statements": [],
    }
    if closure is not None:
        row["story_node_ids"].extend(closure.seed_story_node_ids)
        row["brief_ids"].extend(closure.seed_brief_ids)
        row["facet_ids"].extend(closure.seed_facet_ids)
        row["obligation_ids"].extend(closure.seed_obligation_ids)
        row["author_statements"].extend(closure.seed_author_statements)
    story_to_mechanism: dict[str, str] = {}
    for node in story_spine:
        story_id = _text(_get(node, "story_node_id") or _get(node, "node_id"))
        explicit = _text(_get(node, "mechanism_id") or _get(node, "mechanism_key"))
        candidate = _canonical_mechanism_id(explicit or story_id)
        if story_id and candidate:
            story_to_mechanism[story_id] = candidate
    brief_to_mechanism: dict[str, str] = {}
    for brief in _items(argument_briefs, "briefs"):
        brief_id = _text(_get(brief, "brief_id"))
        story_id = _text(_get(brief, "story_node_id"))
        explicit = _text(_get(brief, "mechanism_id") or _get(brief, "mechanism_key"))
        candidate = _canonical_mechanism_id(
            explicit or story_to_mechanism.get(story_id, "") or story_id or brief_id
        )
        if brief_id and candidate:
            brief_to_mechanism[brief_id] = candidate
    for node in story_spine:
        story_id = _text(_get(node, "story_node_id") or _get(node, "node_id"))
        candidate = story_to_mechanism.get(story_id, "")
        if candidate != mechanism_id:
            continue
        row["story_node_ids"].extend(_ids(story_id))
        statement = _text(_get(node, "statement") or _get(node, "narrative"))
        if statement:
            row["author_statements"].append(statement)
    for brief in _items(argument_briefs, "briefs"):
        brief_id = _text(_get(brief, "brief_id"))
        candidate = brief_to_mechanism.get(brief_id, "")
        if candidate != mechanism_id:
            continue
        row["brief_ids"].extend(_ids(brief_id))
        row["story_node_ids"].extend(_ids(_get(brief, "story_node_id")))
        row["obligation_ids"].extend(_ids(_get(brief, "obligation_ids", ())))
        statement = _text(_get(brief, "author_statement") or _get(brief, "purpose"))
        if statement:
            row["author_statements"].append(statement)
    for facet in facets:
        facet_id = _text(_get(facet, "facet_id"))
        brief_id = _text(_get(facet, "brief_id"))
        story_id = _text(_get(facet, "story_node_id"))
        explicit = _text(_get(facet, "mechanism_id") or _get(facet, "mechanism_key"))
        candidate = _canonical_mechanism_id(
            explicit
            or brief_to_mechanism.get(brief_id, "")
            or story_to_mechanism.get(story_id, "")
            or story_id or brief_id or facet_id
        )
        if candidate != mechanism_id:
            continue
        row["facet_ids"].extend(_ids(facet_id))
        row["brief_ids"].extend(_ids(brief_id))
        row["story_node_ids"].extend(_ids(story_id))
        row["obligation_ids"].extend(_ids(_get(facet, "clause_id")))
        statement = _text(_get(facet, "exact_source_quote") or _get(facet, "author_statement"))
        if statement:
            row["author_statements"].append(statement)
    return {
        key: tuple(dict.fromkeys(value))
        for key, value in row.items()
    }


def _operation_fact_ids(operation_id: str, closure: MechanismEvidenceClosureV1) -> tuple[str, ...]:
    for operation in closure.operation_nodes:
        if operation.operation_id == operation_id and operation.source_fact_ids:
            return tuple(dict.fromkeys(
                fact_id for fact_id in operation.source_fact_ids
                if fact_id in set(closure.fact_ids)
            ))
    for prefix in ("fact-operation:", "op:"):
        if operation_id.startswith(prefix):
            candidate = operation_id[len(prefix):]
            if candidate in set(closure.fact_ids):
                return (candidate,)
    return ()


def _same_predicate_family(left: str, right: str) -> bool:
    left_raw, right_raw = _text(left).casefold(), _text(right).casefold()
    if left_raw and left_raw == right_raw:
        return True
    return bool(left_raw and right_raw and any(
        left_raw in family and right_raw in family
        for family in _PREDICATE_FAMILIES
    ))


def _proven_same_operation(operations: Sequence[EvidenceOperationV1]) -> bool:
    """Prove that all operations in a cluster are one operation across views.

    Correspondence requires one exact shared span, at most one symbol scope,
    and equal operands/result combined with a generic predicate-family match
    (``calls``↔``CALL``).  Case-only, span-only, or result-name-only equality
    never proves correspondence; nested operations at the same span with
    different kinds (e.g. ``LOAD`` vs ``CALL``) stay distinguishable.
    """

    if len(operations) < 2:
        return True
    spans = {operation.source_span_id for operation in operations if operation.source_span_id}
    if len(spans) != 1:
        return False
    symbols = {operation.symbol_id for operation in operations if operation.symbol_id}
    if len(symbols) > 1:
        return False

    def operand_key(operation: EvidenceOperationV1) -> tuple[str, ...]:
        return tuple(sorted(
            str(value).strip().casefold()
            for value in operation.operands
            if str(value).strip()
        ))

    first = operations[0]
    base_operands = operand_key(first)
    base_result = str(first.result).strip().casefold()
    for operation in operations[1:]:
        if operand_key(operation) != base_operands:
            return False
        if str(operation.result).strip().casefold() != base_result:
            return False
        if not _same_predicate_family(first.predicate, operation.predicate):
            return False
    return True


def _path_evidence_marker_reason(basis_ids: Sequence[str]) -> str:
    """Map a typed recovery marker in the activation basis to a reason code."""

    for basis in basis_ids:
        if basis.startswith("path_polarity_conflict:"):
            return basis
        if basis.startswith("unproven_dominance:"):
            return "guard_dominance_unproven:" + basis.split(":", 1)[1]
    return ""


def _cluster_path_evidence(
    operations: Sequence[EvidenceOperationV1],
) -> tuple[ActivePathStatus, tuple[str, ...], tuple[str, ...], str]:
    """Aggregate a cluster's active-path status from its operation evidence.

    Returns ``(status, conditions, basis_ids, reason_code)``.  The status
    rules are strict and follow the frozen-evidence contract:

    - a recovery marker (polarity conflict / unbounded dominance) keeps the
      cluster unresolved with that exact reason, even when every view
      happens to report the same status;
    - proven dual views of one operation whose guard texts disagree are a
      guard conflict, never a conjunction (textual difference is not proof
      of equivalence);
    - one distinct status: that status;
    - any ``unknown`` view keeps the cluster unknown (fail-closed);
    - the pre-existing mixed active/inactive rule stays ``conditional``;
    - a mixed *active* set collapses only when the operations are proven to
      be the same operation across views: a single recovered guard becomes
      ``conditional`` (the guarded view dominates, the guardless view is an
      omission), and ``active_selected`` is retained only when selection
      evidence produced it;
    - missing correspondence or inconsistent selection stays ``unknown``
      with a concrete reason for the owning agent.
    """

    statuses = {operation.active_path_status for operation in operations}
    conditions = tuple(dict.fromkeys(
        _normalize_guard_text(operation.guard)
        for operation in operations
        if _normalize_guard_text(operation.guard)
    ))
    basis_ids = tuple(dict.fromkeys(
        basis
        for operation in operations
        for basis in operation.activation_basis_ids
        if basis
    ))
    marker = _path_evidence_marker_reason(basis_ids)
    if marker:
        return "unknown", conditions, basis_ids, marker
    if len(operations) > 1 and len(conditions) > 1 and _proven_same_operation(operations):
        # Two views of one operation name different guards.  Distinct
        # condition texts are not provably equivalent, so the cluster stays
        # unknown (nesting is preserved inside one recovered guard text,
        # not by unioning unrelated strings).
        return (
            "unknown", conditions, basis_ids,
            "guard_conflict:" + "|".join(conditions),
        )
    if len(statuses) == 1:
        return next(iter(statuses)), conditions, basis_ids, ""  # type: ignore[return-value]
    if "unknown" in statuses:
        return "unknown", conditions, basis_ids, "unknown_status_present"
    if statuses.intersection(_INACTIVE_STATUSES) and statuses.intersection(_ACTIVE_STATUSES):
        return "conditional", conditions, basis_ids, ""
    if statuses.issubset(_ACTIVE_STATUSES):
        if not _proven_same_operation(operations):
            return (
                "unknown", conditions, basis_ids,
                "dual_view_correspondence_missing",
            )
        if not conditions:
            if "active_selected" in statuses:
                return (
                    "active_selected", conditions, basis_ids,
                    "dual_view_selection_evidence",
                )
            return "active_default", conditions, basis_ids, "dual_view_guard_omission"
        if len(conditions) == 1:
            marker = _path_evidence_marker_reason(basis_ids)
            if marker:
                # A guarded typed edge exists for this operation, but its
                # dominance is unproven (or contradictory): the conditional
                # claim may not be aligned onto this span.
                return "unknown", conditions, basis_ids, marker
            return "conditional", conditions, basis_ids, "dual_view_guard_alignment"
        return (
            "unknown", conditions, basis_ids,
            "guard_conflict:" + "|".join(conditions),
        )
    return "unknown", conditions, basis_ids, "mixed_status_unresolved"


def _operation_status(operations: Sequence[EvidenceOperationV1]) -> ActivePathStatus:
    """Legacy status-only projection of :func:`_cluster_path_evidence`."""
    return _cluster_path_evidence(operations)[0]


def annotate_mechanism_paper_details(
    closures: Sequence[MechanismEvidenceClosureV1],
    *,
    story_spine: Iterable[Any] = (),
    argument_briefs: Any | None = None,
    facets: Iterable[Any] = (),
    facts: Any | None = None,
    claims: Any | None = None,
    equations: Any | None = None,
) -> MechanismContextSetV1:
    """Annotate closures into clustered paper details without losing closure nodes."""

    closure_values = tuple(closures)
    story_values, facet_values = tuple(story_spine), tuple(facets)
    fact_values = _items(facts, "facts")
    claim_values = _items(claims, "claims")
    equation_values = _items(equations, "equations")
    facts_by_id = {
        _text(_get(item, "fact_id")): item
        for item in fact_values
        if _text(_get(item, "fact_id"))
    }
    claims_by_id = {
        _text(_get(item, "claim_id")): item
        for item in claim_values
        if _text(_get(item, "claim_id"))
    }
    equations_by_id = {
        _text(_get(item, "equation_id")): item
        for item in equation_values
        if _text(_get(item, "equation_id"))
    }
    # A source operation has one canonical owner.  Other mechanisms receive a
    # typed SharedDetailRef rather than a second independently writable detail.
    owner_by_operation: dict[str, str] = {}
    for closure in closure_values:
        for operation in closure.operation_nodes:
            owner_by_operation[operation.operation_id] = min(
                owner_by_operation.get(operation.operation_id, closure.mechanism_id),
                closure.mechanism_id,
            )

    contexts: list[MechanismContextV1] = []
    shared_ref_specs: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    primary_detail_by_operation: dict[str, str] = {}
    ownerless_seed_ids: set[str] = set()
    for closure in closure_values:
        ownerless_seed_ids.update(
            str(seed_id)
            for seed_id in (closure.unresolved_seed_ids or ())
            if str(seed_id).strip()
        )
    # ``compile_mechanism_evidence_closures`` records the pre-merge seed
    # count in its own diagnostics, but the annotation pass can also be
    # called directly with frozen closures.  Keep this diagnostic total
    # defined in both paths instead of allowing a direct annotation to fail
    # with a NameError while building the context-set audit record.
    seed_count_before_merge = len(closure_values) + len(ownerless_seed_ids)

    # Obligation-bound claim surface (remediation plan point 5): a core
    # detail must be bound to an author obligation/facet through an exact
    # claim.  The brief clause claim handles are the only exact binding
    # signal available at annotation time; when no brief carries any claim,
    # binding is unprovable either way and only the source/path criteria
    # apply (legacy fixtures without an authoring surface keep old behavior).
    obligation_bound_claim_ids: set[str] = set()
    for brief in _items(argument_briefs, "briefs"):
        obligation_bound_claim_ids.update(_ids(_get(brief, "claim_ids", ())))
        for clause in _get(brief, "clauses", ()) or ():
            obligation_bound_claim_ids.update(_ids(_get(clause, "bound_claim_ids", ())))
    obligation_bound_fact_ids: set[str] = set()
    for claim_id in obligation_bound_claim_ids:
        claim = claims_by_id.get(claim_id)
        if claim is not None:
            obligation_bound_fact_ids.update(_ids(_get(claim, "fact_ids", ())))

    for closure in closure_values:
        mechanism_id = closure.mechanism_id
        intent = _intent_rows(
            mechanism_id=mechanism_id,
            story_spine=story_values,
            argument_briefs=argument_briefs,
            facets=facet_values,
            closure=closure,
        )
        clusters = _operation_clusters(closure)
        owned_clusters: list[tuple[EvidenceOperationV1, ...]] = []
        for cluster in clusters:
            owned = tuple(
                operation for operation in cluster
                if owner_by_operation.get(operation.operation_id, mechanism_id) == mechanism_id
            )
            if owned:
                owned_clusters.append(owned)
            for operation in cluster:
                owner = owner_by_operation.get(operation.operation_id, mechanism_id)
                if owner != mechanism_id:
                    role = (
                        "shared_interface"
                        if operation.predicate.upper() == "CALL"
                        else "shared_representation"
                        if operation.predicate.upper() in {"RESHAPE", "CONCAT", "STACK"}
                        else "secondary_consumer"
                    )
                    shared_ref_specs[mechanism_id].append((
                        operation.operation_id,
                        owner,
                        role,
                    ))

        exact_excerpt_by_span: dict[str, str] = {
            operation.source_span_id: operation.exact_excerpt
            for operation in closure.operation_nodes
            if operation.source_span_id and operation.exact_excerpt
        }
        for index, span_id in enumerate(closure.exact_span_ids):
            if span_id not in exact_excerpt_by_span and index < len(closure.exact_excerpts):
                exact_excerpt_by_span[span_id] = closure.exact_excerpts[index]

        detail_specs: list[tuple[str, tuple[EvidenceOperationV1, ...], DetailRole, DetailImportance, ActivePathStatus, str, tuple[str, ...], tuple[str, ...]]] = []
        for index, cluster in enumerate(owned_clusters):
            role = _detail_role(cluster, index, len(owned_clusters))
            importance = _detail_importance(cluster, role=role)
            cluster_status, cluster_conditions, cluster_basis, status_reason = _cluster_path_evidence(
                cluster
            )
            status = cluster_status
            # Core redefinition (remediation plan point 5): ``active_default``
            # alone never makes a detail core.  Core additionally requires
            # first-party executable source and an exact obligation/facet
            # claim binding; otherwise the cluster stays supporting (it is
            # still archived losslessly, just not promoted to the spine).
            if importance == "core":
                cluster_fact_ids = {
                    fact_id
                    for operation in cluster
                    for fact_id in _operation_fact_ids(operation.operation_id, closure)
                }
                cluster_claim_ids = {
                    claim_id
                    for fact_id in cluster_fact_ids
                    for claim_id in _ids(_get(facts_by_id.get(fact_id), "claim_ids", ()))
                }
                cluster_spans = {
                    operation.source_span_id for operation in cluster if operation.source_span_id
                }
                first_party = all(
                    str(operation.source_kind or "unknown") == "first_party_executable"
                    for operation in cluster
                )
                bound_by_claim = bool(
                    cluster_claim_ids & obligation_bound_claim_ids
                ) or bool(cluster_fact_ids & obligation_bound_fact_ids)
                binding_surface_exists = bool(
                    obligation_bound_claim_ids or obligation_bound_fact_ids
                )
                if not first_party or (
                    binding_surface_exists and not bound_by_claim
                ):
                    importance = "supporting"
            detail_specs.append((
                f"detail:{mechanism_id}:{index + 1}",
                cluster,
                role,
                importance,
                status,
                status_reason,
                cluster_conditions,
                cluster_basis,
            ))

        details: list[MechanismDetailV1] = []
        for index, spec in enumerate(detail_specs):
            detail_id, cluster, role, importance, status, status_reason, cluster_conditions, cluster_basis = spec
            source_operation_ids = tuple(operation.operation_id for operation in cluster)
            source_fact_ids = tuple(dict.fromkeys(
                fact_id
                for operation in cluster
                for fact_id in _operation_fact_ids(operation.operation_id, closure)
            ))
            source_spans = tuple(dict.fromkeys(
                operation.source_span_id for operation in cluster if operation.source_span_id
            ))
            # Claim/equation membership follows the exact transitive typed
            # links of this operation cluster.  The full closure may contain
            # several independent author claims; attaching all of them to
            # every detail was a cross-detail contamination bug.
            source_claim_candidates: list[str] = []
            source_equation_candidates: list[str] = []
            for fact_id in source_fact_ids:
                fact = facts_by_id.get(fact_id)
                source_claim_candidates.extend(_ids(_get(fact, "claim_ids", ())))
                source_equation_candidates.extend(_ids(_get(fact, "equation_ids", ())))
            source_fact_set = set(source_fact_ids)
            for claim_id, claim in claims_by_id.items():
                if source_fact_set.intersection(_ids(_get(claim, "fact_ids", ()) )):
                    source_claim_candidates.append(claim_id)
                    source_equation_candidates.extend(_ids(_get(claim, "equation_ids", ())))
            claim_set = set(source_claim_candidates)
            for equation_id, equation in equations_by_id.items():
                if source_fact_set.intersection(_ids(_get(equation, "fact_ids", ()))):
                    source_equation_candidates.append(equation_id)
                elif claim_set.intersection(_ids(_get(equation, "claim_ids", ()) )):
                    source_equation_candidates.append(equation_id)
            source_claim_ids = tuple(dict.fromkeys(
                item for item in source_claim_candidates if item in set(closure.claim_ids)
            ))
            source_equation_ids = tuple(dict.fromkeys(
                item for item in source_equation_candidates if item in set(closure.equation_ids)
            ))
            source_kinds = tuple(dict.fromkeys(
                str(operation.source_kind or "unknown")
                for operation in cluster
            ))
            source_kind = (
                source_kinds[0]
                if len(source_kinds) == 1
                else "mixed"
                if source_kinds
                else "unknown"
            )
            excluded_source = any(
                item in {"vendor", "generated", "submodule", "dataset_or_checkpoint"}
                for item in source_kinds
            )
            # Source fail-closed authority (remediation plan section 9.3):
            # repository authority requires every operation in the cluster to
            # carry an explicit allowed first-party source kind resolved from
            # the source manifest.  ``unknown``/``mixed``/excluded kinds and
            # clusters without any manifest-resolved entry can never support a
            # positive repository claim; they stay unresolved (or split).
            allowed_first_party_kinds = {"first_party_executable"}
            unmapped_source = any(
                item not in allowed_first_party_kinds
                for item in source_kinds
            ) if source_kinds else True
            active_for_clean = (
                status in _ACTIVE_STATUSES
                and importance == "core"
                and all(operation.active_path_status in _ACTIVE_STATUSES for operation in cluster)
            )
            evidence_authority: EvidenceAuthority = (
                "repository_verified"
                if (
                    source_operation_ids
                    and status in _ACTIVE_STATUSES
                    and not excluded_source
                    and not unmapped_source
                )
                else "repository_partial"
                if (
                    source_operation_ids
                    and status != "unknown"
                    and not excluded_source
                    and not unmapped_source
                )
                else "unresolved"
            )
            publication_policy: PublicationPolicy = (
                "clean_candidate" if active_for_clean and evidence_authority == "repository_verified"
                else "review_only" if importance == "side_branch"
                else "annotated_only"
            )
            predicates = tuple(dict.fromkeys(operation.predicate for operation in cluster if operation.predicate))
            operands = tuple(dict.fromkeys(
                operand for operation in cluster for operand in operation.operands
            ))
            results = tuple(dict.fromkeys(
                operation.result for operation in cluster if operation.result
            ))
            conditions = cluster_conditions
            claim_kind: ClaimKind = (
                "formalization"
                if any(operation.predicate.upper() in {"COMPUTE", "REDUCE", "NORMALIZE", "PROJECT", "ATTEND"} for operation in cluster)
                else "implementation"
            )
            formalizable = bool(operands and results and evidence_authority == "repository_verified")
            details.append(MechanismDetailV1(
                detail_id=detail_id,
                primary_mechanism_id=mechanism_id,
                order_index=index,
                role=role,
                importance=importance,
                claim_kind=claim_kind,
                evidence_authority=evidence_authority,
                publication_policy=publication_policy,
                subject=cluster[0].symbol_id if cluster else "",
                predicate=" -> ".join(predicates),
                operands=operands,
                result=results[-1] if results else "",
                conditions=conditions,
                polarity="conditional" if conditions else "positive",
                shape_or_type_hints=tuple(dict.fromkeys(
                    hint for operation in cluster for hint in operation.shape_or_type_hints
                )),
                active_path_status=status,
                activation_basis_ids=cluster_basis,
                source_operation_ids=source_operation_ids,
                source_fact_ids=source_fact_ids,
                source_claim_ids=source_claim_ids,
                source_span_ids=source_spans,
                source_equation_ids=source_equation_ids,
                source_kind=source_kind,
                exact_excerpts=tuple(dict.fromkeys(
                    operation.exact_excerpt for operation in cluster if operation.exact_excerpt
                )),
                source_facet_ids=intent["facet_ids"],
                source_brief_ids=intent["brief_ids"],
                source_obligation_ids=intent["obligation_ids"],
                author_statements=intent["author_statements"],
                mismatch_reason=(
                    status_reason if status == "unknown" else ""
                ),
                # Keep the semantic atom scientific and source-structured;
                # raw ``CALL``/``NORMALIZE`` labels are implementation tokens,
                # not a reader-facing mechanism description.
                semantic_atom=_semantic_atom_for_cluster(cluster, role=role),
                formalizable=formalizable,
                formula_role="operation_atom" if formalizable else "",
                formalizable_signatures=tuple({
                    "operation_id": operation.operation_id,
                    "predicate": operation.predicate,
                    "operands": list(operation.operands),
                    "result": operation.result,
                    "conditions": [operation.guard] if operation.guard else [],
                } for operation in cluster),
                witness_atoms=_detail_witness_atoms(
                    detail_id=detail_id,
                    operations=cluster,
                    exact_excerpt_by_span=exact_excerpt_by_span,
                ),
            ))
            for operation in cluster:
                primary_detail_by_operation[operation.operation_id] = detail_id

        # Add predecessor/successor references after all detail ids are known.
        if details:
            # ``model_copy(update=...)`` bypasses Pydantic validators.  A
            # predecessor/successor annotation changes the detail payload, so
            # rebuilding through ``model_validate`` is required to refresh its
            # content digest and retain the digest as an integrity guard.
            refreshed_details: list[MechanismDetailV1] = []
            for index, detail in enumerate(details):
                detail_payload = detail.model_dump(mode="python")
                detail_payload.update({
                    "predecessor_detail_ids": (
                        (details[index - 1].detail_id,) if index else ()
                    ),
                    "successor_detail_ids": (
                        (details[index + 1].detail_id,)
                        if index + 1 < len(details) else ()
                    ),
                    "content_digest": "",
                })
                refreshed_details.append(MechanismDetailV1.model_validate(detail_payload))
            details = refreshed_details
        edges: list[MechanismEdgeV1] = []
        for left, right in zip(details, details[1:]):
            shared_spans = tuple(dict.fromkeys((*left.source_span_ids, *right.source_span_ids)))
            edges.append(MechanismEdgeV1(
                edge_id=f"edge:{left.detail_id}->{right.detail_id}",
                mechanism_id=mechanism_id,
                source_detail_id=left.detail_id,
                target_detail_id=right.detail_id,
                relation="precedes",
                source_span_ids=shared_spans,
            ))
        # Add only source-grounded semantic data-flow edges.  The ordering
        # edges above remain useful to the narrative planner, but the
        # completeness validator intentionally ignores them.
        operations_by_detail = {
            detail.detail_id: tuple(
                operation for operation in closure.operation_nodes
                if operation.operation_id in set(detail.source_operation_ids)
            )
            for detail in details
        }
        for left in details:
            left_results = {
                str(operation.result).strip().casefold()
                for operation in operations_by_detail[left.detail_id]
                if str(operation.result).strip()
            }
            if not left_results:
                continue
            for right in details:
                if left.detail_id == right.detail_id:
                    continue
                right_operands = {
                    str(operand).strip().casefold()
                    for operation in operations_by_detail[right.detail_id]
                    for operand in operation.operands
                    if str(operand).strip()
                }
                if not left_results.intersection(right_operands):
                    continue
                relation_ids = tuple(dict.fromkeys(
                    relation_id
                    for operation in operations_by_detail[left.detail_id]
                    for relation_id in operation.relation_ids
                    if relation_id
                ))
                edges.append(MechanismEdgeV1(
                    edge_id=f"edge:{left.detail_id}->{right.detail_id}:feeds",
                    mechanism_id=mechanism_id,
                    source_detail_id=left.detail_id,
                    target_detail_id=right.detail_id,
                    relation="feeds",
                    source_relation_ids=relation_ids,
                    source_span_ids=tuple(dict.fromkeys(
                        span_id
                        for operation in operations_by_detail[left.detail_id]
                        for span_id in (operation.source_span_id,)
                        if span_id
                    )),
                ))
        semantic_pairs = {
            (edge.source_detail_id, edge.target_detail_id)
            for edge in edges
            if edge.relation != "precedes"
        }
        if semantic_pairs:
            edges = [
                edge for edge in edges
                if edge.relation != "precedes"
                or (edge.source_detail_id, edge.target_detail_id) not in semantic_pairs
            ]
        # Author-intent-only rationale: a narrative anchor, never a source
        # core.  It carries no executable operation, so the core conjunction
        # (owner + first-party source + obligation binding + directed path)
        # cannot hold and it stays supporting.
        if not details and (
            intent["author_statements"]
            or intent["facet_ids"]
            or intent["brief_ids"]
            or intent["obligation_ids"]
        ):
            rationale_id = f"detail:{mechanism_id}:rationale"
            details = [MechanismDetailV1(
                detail_id=rationale_id,
                primary_mechanism_id=mechanism_id,
                order_index=0,
                role="rationale",
                importance="supporting",
                claim_kind="rationale",
                evidence_authority="author_intent_only",
                publication_policy="annotated_only",
                semantic_atom=intent["author_statements"][0] if intent["author_statements"] else f"Rationale for {mechanism_id}",
                source_facet_ids=intent["facet_ids"],
                source_brief_ids=intent["brief_ids"],
                source_obligation_ids=intent["obligation_ids"],
                author_statements=intent["author_statements"],
                witness_atoms=(DetailWitnessAtomV1(
                    atom_id=f"atom:{rationale_id}:rationale",
                    atom_kind="operation",
                    semantic_anchor=f"rationale for {mechanism_id}",
                    required_polarity="unknown",
                ),),
            )]
        # Core is restricted to the evidence-derived input→output path.  A
        # detail off that path stays supporting evidence in the archive; it is
        # demoted in importance, never deleted.  This first pass is structural
        # (endpoints/path only); the final audit below re-runs against the
        # frozen closure that carries dispositions and unresolved items.
        path_audit = _mechanism_annotation_audit(closure, details, edges)
        on_path_ids = set(path_audit["on_path_detail_ids"])
        if any(
            detail.importance == "core" and detail.detail_id not in on_path_ids
            for detail in details
        ):
            def _demote_off_path(detail: MechanismDetailV1) -> MechanismDetailV1:
                if detail.importance != "core" or detail.detail_id in on_path_ids:
                    return detail
                payload = detail.model_dump(mode="python")
                payload["importance"] = "supporting"
                payload["publication_policy"] = "annotated_only"
                # The digest covers importance/publication_policy; clearing it
                # lets the model recompute it instead of failing validation.
                payload["content_digest"] = ""
                return MechanismDetailV1.model_validate(payload)

            details = [_demote_off_path(detail) for detail in details]
        dispositions: list[SourceOperationDispositionV1] = []
        detail_by_operation = {
            operation_id: primary_detail_by_operation[operation_id]
            for detail in details
            for operation_id in detail.source_operation_ids
            if operation_id in primary_detail_by_operation
        }
        for operation in closure.operation_nodes:
            owner = owner_by_operation.get(operation.operation_id, mechanism_id)
            detail_id = detail_by_operation.get(operation.operation_id, "")
            if owner != mechanism_id:
                dispositions.append(SourceOperationDispositionV1(
                    operation_id=operation.operation_id,
                    disposition="classified_supporting",
                    detail_ids=(),
                    reason_code=f"canonical_owner:{owner}",
                ))
            elif detail_id:
                detail = next(item for item in details if item.detail_id == detail_id)
                if detail.importance == "side_branch":
                    disposition = "classified_side_branch"
                elif operation.active_path_status == "unknown":
                    disposition = "explicitly_unresolved"
                elif detail.importance == "supporting":
                    disposition = "classified_supporting"
                else:
                    disposition = "absorbed_by_detail"
                dispositions.append(SourceOperationDispositionV1(
                    operation_id=operation.operation_id,
                    disposition=disposition,
                    # An unresolved terminal disposition deliberately has no
                    # owner: the Detail remains a traceable annotation, but
                    # it cannot be mistaken for a validated source owner.
                    detail_ids=() if disposition == "explicitly_unresolved" else (detail_id,),
                    reason_code=(
                        f"unresolved_detail:{detail_id}"
                        if disposition == "explicitly_unresolved"
                        else detail.publication_policy
                    ),
                ))
            else:
                dispositions.append(SourceOperationDispositionV1(
                    operation_id=operation.operation_id,
                    disposition="explicitly_unresolved",
                    detail_ids=(),
                    reason_code="operation_not_clustered",
                ))
        unresolved_items = list(closure.unresolved_items)
        unresolved_items.extend(
            f"shared_operation_primary:{operation_id}:{owner}"
            for operation_id, owner, _ in shared_ref_specs.get(mechanism_id, ())
        )
        frozen_closure = MechanismEvidenceClosureV1(
            closure_id=closure.closure_id,
            mechanism_id=closure.mechanism_id,
            repo_snapshot_id=closure.repo_snapshot_id,
            project_tree_hash=closure.project_tree_hash,
            seed_story_node_ids=closure.seed_story_node_ids,
            seed_brief_ids=closure.seed_brief_ids,
            seed_facet_ids=closure.seed_facet_ids,
            seed_obligation_ids=closure.seed_obligation_ids,
            seed_author_statements=closure.seed_author_statements,
            seed_kind=closure.seed_kind,
            owner_anchor_id=closure.owner_anchor_id,
            merge_proof_ids=closure.merge_proof_ids,
            unresolved_seed_ids=closure.unresolved_seed_ids,
            merge_proofs=closure.merge_proofs,
            entry_symbol_ids=closure.entry_symbol_ids,
            operation_nodes=closure.operation_nodes,
            call_relation_ids=closure.call_relation_ids,
            data_flow_relation_ids=closure.data_flow_relation_ids,
            control_flow_relation_ids=closure.control_flow_relation_ids,
            configuration_bindings=closure.configuration_bindings,
            active_path_conditions=closure.active_path_conditions,
            default_activation=closure.default_activation,
            fact_ids=closure.fact_ids,
            claim_ids=closure.claim_ids,
            equation_ids=closure.equation_ids,
            exact_span_ids=closure.exact_span_ids,
            exact_excerpts=closure.exact_excerpts,
            source_digests=closure.source_digests,
            shape_or_type_hints=closure.shape_or_type_hints,
            return_value_descriptors=closure.return_value_descriptors,
            unresolved_items=tuple(dict.fromkeys(unresolved_items)),
            operation_dispositions=tuple(dispositions),
            source_operation_terminal_coverage=1.0 if closure.operation_nodes else 0.0,
            budget_exhausted=closure.budget_exhausted,
        )
        detail_ids = tuple(detail.detail_id for detail in details)
        annotation_audit = _mechanism_annotation_audit(frozen_closure, details, edges)
        input_ids = tuple(annotation_audit["input_detail_ids"])
        output_ids = tuple(annotation_audit["output_detail_ids"])
        audit_unresolved = tuple(dict.fromkeys(
            (
                *frozen_closure.unresolved_items,
                *(
                    f"disconnected_core_detail:{detail_id}"
                    for detail_id in annotation_audit["disconnected_core_detail_ids"]
                ),
                *(
                    ("core_path_endpoint_unknown",)
                    if annotation_audit["core_path_endpoint_unknown"]
                    else ()
                ),
                *annotation_audit["cluster_split_audit"],
            )
        ))
        source_operations = tuple(frozen_closure.operation_nodes)
        source_operation_ids = {operation.operation_id for operation in source_operations}
        owned_operation_ids = {
            operation_id
            for detail in details
            for operation_id in detail.source_operation_ids
        }
        all_source_details_clean = bool(source_operations) and bool(details) and all(
            detail.evidence_authority == "repository_verified"
            and detail.publication_policy == "clean_candidate"
            and detail.active_path_status in _ACTIVE_STATUSES
            for detail in details if detail.source_operation_ids
        )
        repository_ready = bool(source_operations) and (
            frozen_closure.source_operation_terminal_coverage == 1.0
            and owned_operation_ids.issubset(source_operation_ids)
            and owned_operation_ids == source_operation_ids
            and all_source_details_clean
            and not frozen_closure.unresolved_items
            and not frozen_closure.budget_exhausted
            and all(operation.active_path_status in _ACTIVE_STATUSES for operation in source_operations)
            and annotation_audit["connected_input_to_output"]
            and not annotation_audit["disconnected_core_detail_ids"]
            and annotation_audit["information_completeness"] == 1.0
        )
        intent_ready = (
            not source_operations
            and bool(
                intent["author_statements"]
                or intent["facet_ids"]
                or intent["brief_ids"]
                or intent["obligation_ids"]
            )
        )
        readiness = "repository_ready" if repository_ready else "intent_ready" if intent_ready else (
            "blocked" if not details and not source_operations else "partial"
        )
        contexts.append(MechanismContextV1(
            mechanism_id=mechanism_id,
            mechanism_name=mechanism_id.removeprefix("mech_").replace("_", " ").title(),
            scientific_role="mechanism_spine",
            reader_question=f"How does {mechanism_id} execute?",
            purpose=(
                intent["author_statements"][0]
                if intent["author_statements"]
                else f"Source-grounded implementation of {mechanism_id}"
            ),
            importance="core" if any(detail.importance == "core" for detail in details) else "supporting",
            story_node_ids=intent["story_node_ids"],
            brief_ids=intent["brief_ids"],
            facet_ids=intent["facet_ids"],
            obligation_ids=intent["obligation_ids"],
            author_statements=intent["author_statements"],
            evidence_closure=frozen_closure,
            input_detail_ids=input_ids,
            ordered_detail_ids=detail_ids,
            output_detail_ids=output_ids,
            details=tuple(details),
            edges=tuple(edges),
            shared_detail_refs=(),
            unresolved_items=audit_unresolved,
            context_readiness=readiness,  # type: ignore[arg-type]
            readiness_failures=audit_unresolved,
            budget_exhausted=frozen_closure.budget_exhausted,
            connected_input_detail_ids=tuple(
                annotation_audit["connected_input_detail_ids"]
            ),
            connected_output_detail_ids=tuple(
                annotation_audit["connected_output_detail_ids"]
            ),
            disconnected_core_detail_ids=tuple(
                annotation_audit["disconnected_core_detail_ids"]
            ),
            connected_input_to_output=bool(
                annotation_audit["connected_input_to_output"]
            ),
            information_completeness=float(
                annotation_audit["information_completeness"]
            ),
            cluster_cohesion_score=float(
                annotation_audit["cluster_cohesion_score"]
            ),
            cluster_merge_reasons=tuple(annotation_audit["cluster_merge_reasons"]),
            cluster_split_audit=tuple(annotation_audit["cluster_split_audit"]),
            cluster_merge_audit=tuple(annotation_audit["cluster_merge_audit"]),
            source_manifest_digest=str(
                frozen_closure.source_digests.get("repository_source_manifest", "")
            ),
        ))

    # Materialize shared refs now that primary detail ids are known.
    final_contexts: list[MechanismContextV1] = []
    for context in contexts:
        refs: list[SharedDetailRefV1] = []
        for operation_id, owner, role in shared_ref_specs.get(context.mechanism_id, ()):
            detail_id = primary_detail_by_operation.get(operation_id)
            if not detail_id:
                continue
            refs.append(SharedDetailRefV1(
                detail_id=detail_id,
                primary_mechanism_id=owner,
                consumer_mechanism_id=context.mechanism_id,
                role=role,  # type: ignore[arg-type]
            ))
        # ``model_copy(update=...)`` bypasses Pydantic validators.  Rebuild the
        # context so the source digest covers the final shared-reference
        # annotation as well; otherwise a consumer could receive a context
        # whose declared digest describes an earlier pre-reference object.
        context_payload = context.model_dump(mode="python")
        context_payload["shared_detail_refs"] = tuple(refs)
        context_payload["source_context_digest"] = ""
        final_contexts.append(MechanismContextV1.model_validate(context_payload))

    source_graph_digest = next(
        (
            context.evidence_closure.source_digests.get("behavior_graph", "")
            for context in final_contexts
            if context.evidence_closure.source_digests.get("behavior_graph")
        ),
        "",
    )
    merge_proof_by_digest: dict[str, Any] = {}
    for context in final_contexts:
        for proof in context.evidence_closure.merge_proofs:
            digest = _text(_get(proof, "content_digest"))
            if digest:
                merge_proof_by_digest[digest] = proof
    return MechanismContextSetV1(
        repo_snapshot_id=next((
            context.evidence_closure.repo_snapshot_id
            for context in final_contexts
            if context.evidence_closure.repo_snapshot_id
        ), "snapshot:unknown"),
        project_tree_hash=next((
            context.evidence_closure.project_tree_hash
            for context in final_contexts
            if context.evidence_closure.project_tree_hash
        ), source_graph_digest or "tree:unknown"),
        intent_digest=sha256_digest(canonical_json_bytes({
            "story_spine": story_values,
            "briefs": _items(argument_briefs, "briefs"),
            "facets": facet_values,
        })),
        alignment_digest=sha256_digest(canonical_json_bytes(facet_values)),
        research_digest=sha256_digest(canonical_json_bytes([
            context.evidence_closure.source_digests
            for context in final_contexts
        ])),
        contexts=tuple(final_contexts),
        # ``unresolved_seed_ids`` means exactly "seed without an owner anchor".
        # A mechanism that is merely partial/blocked is reported through its
        # own completeness failure codes; conflating the two made the owner
        # gate fire with ``unified_mechanism_owner_missing`` for mechanisms
        # that do have a resolved owner.
        unresolved_seed_ids=tuple(sorted(ownerless_seed_ids)),
        compiler_diagnostics=tuple([
            {
                "kind": "owner_first_partition",
                "seed_count_before_merge": seed_count_before_merge,
                "mechanism_count_after_merge": len(final_contexts),
                "ownerless_seed_count": len(ownerless_seed_ids),
            },
            *({
                "mechanism_id": context.mechanism_id,
                "unresolved_items": list(context.unresolved_items),
            } for context in final_contexts if context.unresolved_items),
            *({
                "kind": "core_path_status_unknown",
                "mechanism_id": context.mechanism_id,
                "detail_id": detail.detail_id,
                "reason_code": detail.mismatch_reason or "core_active_path_unknown",
            }
                for context in final_contexts
                for detail in context.details
                if detail.importance == "core" and detail.active_path_status == "unknown"
            ),
        ]),
        merge_proofs=tuple(
            merge_proof_by_digest[key] for key in sorted(merge_proof_by_digest)
        ),
    )


def compile_mechanism_contexts(
    *,
    argument_briefs: Any | None = None,
    facets: Iterable[Any] = (),
    facet_alignments: Iterable[Any] = (),
    field_candidates: Iterable[Any] = (),
    story_spine: Iterable[Any] = (),
    facts: Any | None = None,
    claims: Any | None = None,
    equations: Any | None = None,
    configurations: Any | None = None,
    evidence_packets: Any | None = None,
    behavior_graph: Any | None = None,
    implementation_scope: Any | None = None,
    symbol_index: Any | None = None,
    source_provider: Any | None = None,
    source_manifest: Any | None = None,
    author_config_overrides: Mapping[str, Any] | None = None,
) -> MechanismContextSetV1:
    """Run the lossless closure compiler and paper annotation compiler."""

    closures = compile_mechanism_evidence_closures(
        argument_briefs=argument_briefs,
        facets=facets,
        facet_alignments=facet_alignments,
        field_candidates=field_candidates,
        story_spine=story_spine,
        facts=facts,
        claims=claims,
        equations=equations,
        configurations=configurations,
        evidence_packets=evidence_packets,
        behavior_graph=behavior_graph,
        implementation_scope=implementation_scope,
        symbol_index=symbol_index,
        source_provider=source_provider,
        source_manifest=source_manifest,
        author_config_overrides=author_config_overrides,
    )
    return annotate_mechanism_paper_details(
        closures,
        story_spine=story_spine,
        argument_briefs=argument_briefs,
        facets=facets,
        facts=facts,
        claims=claims,
        equations=equations,
    )


def _source_kind_for_manifest_span(
    span_id: str,
    source_manifest: Any | None,
) -> str:
    """Resolve a span's source kind from the authenticated manifest."""

    if source_manifest is None:
        return ""
    match = re.match(r"^span:(.*):(\d+):(\d+)$", str(span_id or ""))
    if match is None:
        return "unknown"
    path = normalize_source_path(match.group(1))
    entry_for = getattr(source_manifest, "entry_for", None)
    entry = entry_for(path) if callable(entry_for) else None
    if entry is None:
        entry = next(
            (
                item for item in (getattr(source_manifest, "entries", ()) or ())
                if normalize_source_path(str(getattr(item, "path", "") or "")) == path
            ),
            None,
        )
    return _text(getattr(entry, "source_kind", "") if entry is not None else "") or "unknown"


def _effective_detail_source_kind(
    detail: MechanismDetailV1,
    closure: MechanismEvidenceClosureV1,
    source_manifest: Any | None,
) -> str:
    """Use manifest authority to migrate only stale unknown V1 labels.

    Historical V1 contexts often persisted ``source_kind=unknown`` even when
    their source spans are authenticated by a later repository manifest.  The
    archive compiler already resolves that representation-only mismatch.  The
    completeness gate must use the same resolution, while retaining explicit
    non-unknown labels and rejecting unmapped or mixed source spans.
    """

    raw_kind = _text(detail.source_kind) or "unknown"
    if source_manifest is None or raw_kind not in {"unknown", "mixed"}:
        return raw_kind

    operation_by_id = {
        str(operation.operation_id): operation
        for operation in (closure.operation_nodes or ())
    }
    kinds: list[str] = []
    for span_id in detail.source_span_ids or ():
        kinds.append(_source_kind_for_manifest_span(span_id, source_manifest))
    for operation_id in detail.source_operation_ids or ():
        operation = operation_by_id.get(str(operation_id))
        if operation is None:
            kinds.append("unknown")
            continue
        operation_kind = _text(operation.source_kind) or "unknown"
        if operation_kind in {"unknown", "mixed"}:
            operation_kind = _source_kind_for_manifest_span(
                operation.source_span_id,
                source_manifest,
            )
        kinds.append(operation_kind)
    unique_kinds = tuple(dict.fromkeys(kinds))
    if len(unique_kinds) == 1:
        return unique_kinds[0]
    return "mixed" if unique_kinds else raw_kind


def validate_mechanism_context_completeness(
    context: MechanismContextV1,
    *,
    source_manifest: Any | None = None,
) -> tuple[str, ...]:
    """Return the structural failure set for one frozen context.

    This validator intentionally reports rather than repairs.  The output is
    a closed set of structural failure codes, not an averaged score: owner,
    source, typed path, and witness failures are never masked by a partial
    readiness level, and none of them can pass by filtering.
    """

    failures: list[str] = []
    closure = context.evidence_closure
    if closure.operation_nodes and closure.source_operation_terminal_coverage != 1.0:
        failures.append("operation_terminal_coverage_incomplete")
    if any(
        item.disposition == "explicitly_unresolved"
        for item in closure.operation_dispositions
    ):
        failures.append("operation_disposition_unresolved")
    if context.disconnected_core_detail_ids:
        failures.extend(
            f"disconnected_core_detail:{detail_id}"
            for detail_id in context.disconnected_core_detail_ids
        )
    if context.details and not context.connected_input_to_output:
        failures.append("connected_input_to_output_missing")
    # A mechanism with executable operations must expose at least one core
    # detail on the proven input→output path.  Otherwise the closure is a bag
    # of supporting annotations, not a narratable mechanism.
    if closure.operation_nodes and not any(
        detail.importance == "core" for detail in context.details
    ):
        failures.append("core_detail_missing")
    for detail in context.details:
        if detail.importance != "core":
            continue
        if detail.evidence_authority in {"repository_verified", "repository_partial"}:
            if not detail.source_operation_ids and not detail.source_fact_ids:
                failures.append(f"core_detail_source_binding_missing:{detail.detail_id}")
            if not detail.witness_atoms:
                failures.append(f"core_detail_witness_missing:{detail.detail_id}")
            for atom in detail.witness_atoms:
                if atom.required and not (
                    atom.source_operation_ids or atom.source_anchor_ids
                ):
                    failures.append(f"core_witness_source_binding_missing:{atom.atom_id}")
        if detail.active_path_status == "unknown":
            failures.append(f"core_detail_active_path_unknown:{detail.detail_id}")
        # Source fail-closed: a core detail with an unknown or mixed source
        # kind is a structural failure regardless of readiness level.
        effective_source_kind = _effective_detail_source_kind(
            detail,
            closure,
            source_manifest,
        )
        if effective_source_kind in {"unknown", "mixed", ""} and detail.importance == "core":
            failures.append(f"core_detail_source_kind_unresolved:{detail.detail_id}")
        if effective_source_kind in {"vendor", "generated", "submodule", "dataset_or_checkpoint"}:
            failures.append(f"core_detail_source_kind_excluded:{detail.detail_id}")
    if context.cluster_split_audit:
        failures.append("cluster_split_audit_open")
    if context.budget_exhausted:
        failures.append("context_budget_exhausted")
    if context.context_readiness == "repository_ready" and context.information_completeness < 1.0:
        failures.append("repository_ready_information_completeness_mismatch")
    return tuple(dict.fromkeys(failures))


def validate_mechanism_context_structural_gates(
    context_set: MechanismContextSetV1,
    *,
    merge_proofs: Sequence[Any] = (),
) -> dict[str, Any]:
    """Project-level structural gates over a compiled context set.

    Returns the machine-checkable owner/path/diagnostic summary consumed by
    ``evaluate_unified_live_admission_v1``.  The gates are structural only:

    - every core detail has exactly one primary owner (ownerless = 0);
    - no detail is claimed as primary by two mechanisms (conflict = 0);
    - every recorded merge is backed by a merge proof; where a proof exists
      for a merged seed group, its decision must be ``merged``;
    - the collapse ratio is reported as a diagnostic, never as a gate.
    """

    owner_counts: dict[str, set[str]] = {}
    core_ownerless: list[str] = []
    unowned_mechanisms: list[str] = []
    ownerless_seed_ids: set[str] = {
        str(seed_id)
        for seed_id in (getattr(context_set, "unresolved_seed_ids", ()) or ())
        if str(seed_id).strip()
    }
    for context in context_set.contexts:
        ownerless_seed_ids.update(
            str(seed_id)
            for seed_id in (context.evidence_closure.unresolved_seed_ids or ())
            if str(seed_id).strip()
        )
        # The primary owner of a mechanism is its resolved owner anchor.  A
        # mechanism whose closure carries operations but no owner anchor is
        # ownerless even though ``primary_mechanism_id`` is always populated.
        owner_anchor = str(context.evidence_closure.owner_anchor_id or "").strip()
        if context.evidence_closure.operation_nodes and not owner_anchor:
            unowned_mechanisms.append(context.mechanism_id)
        for detail in context.details:
            owner_counts.setdefault(detail.detail_id, set()).add(
                str(detail.primary_mechanism_id)
            )
            if detail.importance == "core" and (
                not str(detail.primary_mechanism_id) or not owner_anchor
            ):
                core_ownerless.append(detail.detail_id)
    conflicts = sorted(
        detail_id for detail_id, owners in owner_counts.items() if len(owners) > 1
    )
    merged_seed_ids = {
        (proof.left_seed_id, proof.right_seed_id)
        for proof in merge_proofs
        if getattr(proof, "decision", "") == "merged"
    }
    invalid_merge_proofs = [
        f"merge_proof_missing_directed_path:{proof.left_seed_id}:{proof.right_seed_id}"
        for proof in merge_proofs
        if getattr(proof, "decision", "") == "merged"
        and not getattr(proof, "directed_path_relation_ids", ())
        and not getattr(proof, "owner_anchor_id", "")
    ]
    disconnected_core = sorted({
        detail_id
        for context in context_set.contexts
        for detail_id in context.disconnected_core_detail_ids
    })
    unknown_active_path = sorted({
        detail.detail_id
        for context in context_set.contexts
        for detail in context.details
        if detail.importance == "core" and detail.active_path_status == "unknown"
    })
    seed_count = next(
        (
            int(item.get("seed_count_before_merge", 0))
            for item in context_set.compiler_diagnostics
            if item.get("kind") == "owner_first_partition"
        ),
        len(context_set.contexts),
    )
    return {
        "core_ownerless_detail_ids": sorted(set(core_ownerless)),
        "core_ownerless_seed_ids": sorted(ownerless_seed_ids),
        "core_ownerless_mechanism_ids": sorted(set(unowned_mechanisms)),
        "core_ownerless_count": (
            len(set(core_ownerless))
            + len(ownerless_seed_ids)
            + len(set(unowned_mechanisms))
        ),
        "core_owner_conflict_detail_ids": conflicts,
        "core_owner_conflict_count": len(conflicts),
        "mechanism_count": len(context_set.contexts),
        "seed_collapse_ratio": (
            seed_count / len(context_set.contexts)
            if context_set.contexts else 0.0
        ),
        "merge_proof_count": len(merge_proofs),
        "merged_pair_count": len(merged_seed_ids),
        "invalid_merge_proofs": sorted(set(invalid_merge_proofs)),
        "disconnected_core_detail_count": len(disconnected_core),
        "unknown_core_active_path_count": len(unknown_active_path),
    }


__all__ = [
    "DefinitionResolver",
    "resolve_active_path_status",
    "compile_mechanism_evidence_closures",
    "annotate_mechanism_paper_details",
    "compile_mechanism_contexts",
    "validate_mechanism_context_completeness",
    "validate_mechanism_context_structural_gates",
]
