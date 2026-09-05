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


_ACTIVE_STATUSES = frozenset({"active_default", "active_selected", "conditional"})
_INACTIVE_STATUSES = frozenset({"inactive_default", "unreachable"})
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
        return sha256_digest(_text(value))


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
    default_branch: str = "unknown",
    reachable: bool | None = None,
    operation_id: str = "",
    source_span_id: str = "",
    explicit_status: str = "",
) -> ActivePathStatus:
    """Resolve active-path status from explicit evidence only.

    Precedence is explicit author override, resolved configuration, graph
    reachability/default, then guard.  Names such as ``debug`` or
    ``vectorized`` have no authority and are intentionally ignored.
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
        if len(matches) == 1:
            return matches[0]
    return node_id or symbol_id


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


def _build_adapter_graph(
    *,
    symbol_index: Any,
    source_provider: Any,
    entry_symbol_ids: Sequence[str],
) -> Any | None:
    """Build a bounded graph when the caller supplied a real source snapshot."""

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
) -> dict[str, dict[str, Any]]:
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

    def explicit_symbol_ids(value: Any) -> tuple[str, ...]:
        result: list[str] = []
        for name in explicit_symbol_fields:
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
        mechanism_id = _canonical_mechanism_id(explicit_mid or story_id)
        if not mechanism_id:
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
        row["entry_symbol_ids"].update(explicit_symbol_ids(node))
        row["candidate_symbol_ids"].update(_ids(_get(node, "candidate_symbols_or_terms", ())))
        add_semantic_field(row, _get(node, "semantic_fields", {}))

    brief_to_mechanism: dict[str, str] = {}
    for brief in brief_values:
        brief_id = _text(_get(brief, "brief_id"))
        story_id = _text(_get(brief, "story_node_id"))
        explicit_mid = _text(_get(brief, "mechanism_id") or _get(brief, "mechanism_key"))
        mechanism_id = _canonical_mechanism_id(
            explicit_mid or story_to_mechanism.get(story_id, "") or story_id or brief_id
        )
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
        row["entry_symbol_ids"].update(explicit_symbol_ids(brief))
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
        mechanism_id = _canonical_mechanism_id(
            explicit_mid
            or brief_to_mechanism.get(brief_id, "")
            or story_to_mechanism.get(story_id, "")
            or story_id or brief_id or fid
        )
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
        row["entry_symbol_ids"].update(explicit_symbol_ids(facet))
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
        row = add_mid(
            explicit_mid or facet_to_mechanism.get(fid, "") or fid
        )
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

    if not seeds and (fact_by_id or claim_by_id or equation_by_id):
        row = seeds["mech_core"]
        row["bound_fact_ids"].update(fact_by_id.keys())
        row["bound_claim_ids"].update(claim_by_id.keys())
        row["bound_equation_ids"].update(equation_by_id.keys())
    return seeds


def _merge_mechanism_seed_rows(
    seeds: Mapping[str, dict[str, Any]],
    *,
    facts: Any | None = None,
    graph: Any | None = None,
) -> dict[str, dict[str, Any]]:
    """Merge only independently evidenced mechanism seed fragments.

    Story nodes and briefs are organization priors, not mechanism identity.
    The legacy fallback of making one mechanism per story node fragments a
    single implementation chain; the opposite fallback of merging all
    author text contaminates unrelated mechanisms.  A merge is therefore
    admitted only by exact evidence-handle overlap, an exact producer/result
    to consumer/operand link, or a direct typed behavior-graph edge.  Two
    distinct explicit mechanism keys are never merged.
    """

    if len(seeds) < 2:
        return {str(key): dict(value) for key, value in seeds.items()}

    keys = tuple(sorted(str(key) for key in seeds))
    parent = {key: key for key in keys}
    explicit_by_root = {
        key: set(seeds[key].get("explicit_mechanism_ids", ()))
        for key in keys
    }

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

    def evidence_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
        for name in (
            "bound_fact_ids",
            "bound_claim_ids",
            "bound_equation_ids",
            "bound_span_ids",
            "bound_relation_ids",
        ):
            if set(left.get(name, ())) & set(right.get(name, ())):
                return True
        return False

    fact_by_id = {
        _text(_get(item, "fact_id")): item
        for item in _items(facts, "facts")
        if _text(_get(item, "fact_id"))
    }

    def fact_flow_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
        def flow(row: dict[str, Any]) -> tuple[set[str], set[str]]:
            produced: set[str] = set()
            consumed: set[str] = set()
            for fact_id in row.get("bound_fact_ids", ()):
                fact = fact_by_id.get(str(fact_id))
                if fact is None:
                    continue
                _predicate, operands, result, _conditions = _fact_operation_parts(fact)
                consumed.update(
                    value.casefold() for value in operands if value.strip()
                )
                if result.strip():
                    produced.add(result.casefold())
                subject = _text(_get(fact, "subject"))
                if subject:
                    consumed.add(subject.casefold())
            return produced, consumed

        left_produced, left_consumed = flow(left)
        right_produced, right_consumed = flow(right)
        return bool(
            left_produced.intersection(right_consumed)
            or right_produced.intersection(left_consumed)
        )

    graph_nodes, graph_relations, _unresolved = _graph_parts(graph)

    def graph_anchors(row: dict[str, Any]) -> set[str]:
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

    def direct_graph_link(left: dict[str, Any], right: dict[str, Any]) -> bool:
        left_nodes = graph_anchors(left)
        right_nodes = graph_anchors(right)
        if not left_nodes or not right_nodes:
            return False
        for relation in graph_relations.values():
            source = _relation_endpoint(relation, "source", graph_nodes)
            target = _relation_endpoint(relation, "target", graph_nodes)
            if (
                source in left_nodes and target in right_nodes
                or source in right_nodes and target in left_nodes
            ):
                return True
        return False

    for index, left_key in enumerate(keys):
        for right_key in keys[index + 1:]:
            left = seeds[left_key]
            right = seeds[right_key]
            left_explicit = explicit_by_root[find(left_key)]
            right_explicit = explicit_by_root[find(right_key)]
            if left_explicit and right_explicit and left_explicit != right_explicit:
                continue
            if not (
                evidence_overlap(left, right)
                or fact_flow_overlap(left, right)
                or direct_graph_link(left, right)
            ):
                continue
            left_root, right_root = find(left_key), find(right_key)
            if left_root == right_root:
                continue
            merged_explicit = explicit_by_root[left_root] | explicit_by_root[right_root]
            if len(merged_explicit) > 1:
                continue
            parent[right_root] = left_root
            explicit_by_root[left_root] = merged_explicit

    groups: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        groups[find(key)].append(key)
    merged_rows: dict[str, dict[str, Any]] = {}
    for group_keys in groups.values():
        explicit = sorted(
            set().union(*(set(seeds[key].get("explicit_mechanism_ids", ())) for key in group_keys))
        )
        winner = explicit[0] if explicit else group_keys[0]
        merged: dict[str, Any] = {}
        for key in group_keys:
            row = seeds[key]
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
        merged_rows[winner] = merged
    return merged_rows


def _reachable_graph_nodes(
    *,
    nodes: Mapping[str, Any],
    relations: Mapping[str, Any],
    entry_symbols: Sequence[str],
    selected_seed_ids: Sequence[str],
    max_nodes: int = 256,
) -> tuple[set[str], set[str]]:
    """Return the bounded typed component containing exact seed nodes."""

    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for rid, relation in relations.items():
        kind = _text(_get(relation, "kind")).upper()
        if kind not in _GRAPH_RELATIONS:
            continue
        source = _relation_endpoint(relation, "source", nodes)
        target = _relation_endpoint(relation, "target", nodes)
        if source in nodes and target in nodes and source != target:
            adjacency[source].append((target, rid))
            adjacency[target].append((source, rid))
    seeds = set(selected_seed_ids)
    if not seeds:
        seeds.update(
            node_id for node_id, node in nodes.items()
            if _text(_get(node, "symbol_id")) in set(entry_symbols)
        )
    if not seeds:
        return set(), set()
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
    return selected, selected_relations


def _graph_node_operation(
    node: Any,
    *,
    active_status: ActivePathStatus,
    exact_excerpt: str = "",
    relation_ids: Iterable[str] = (),
    operation_id: str = "",
) -> EvidenceOperationV1:
    return EvidenceOperationV1(
        # Behavior adapters may reuse a local operation label for every
        # symbol.  The node id is the stable graph identity and prevents a
        # callee from overwriting its caller during closure assembly.
        operation_id=operation_id or _text(_get(node, "node_id")) or _text(_get(node, "operation_id")),
        symbol_id=_text(_get(node, "symbol_id")),
        predicate=_text(_get(node, "predicate")) or "unknown_operation",
        operands=_ids(_get(node, "operands", ())),
        result=_text(_get(node, "result")),
        guard=_text(_get(node, "guard")),
        source_span_id=_text(_get(node, "source_span_id")),
        relation_ids=tuple(dict.fromkeys(
            (*_ids(_get(node, "relation_ids", ())), *_ids(relation_ids)
        ))),
        active_path_status=active_status,
        activation_basis_ids=_ids(_get(node, "activation_basis_ids", ())),
        shape_or_type_hints=_ids(_get(node, "shape_or_type_hints", ())),
        source_fact_ids=_ids(_get(node, "source_fact_ids", ())),
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
    seeds = _collect_seed_data(
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

    # Reconcile organization fragments only after the exact graph (including
    # an adapter-built graph) is available.  This prevents one story node per
    # mechanism fragmentation while keeping unrelated explicit mechanisms
    # isolated.
    seeds = _merge_mechanism_seed_rows(seeds, facts=facts, graph=graph)
    graph_nodes, graph_relations, unresolved_relations = _graph_parts(graph)
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
            return "unknown", True, role
        return "unknown", None, role
    graph_node_to_operation: dict[str, str] = {}

    closures: list[MechanismEvidenceClosureV1] = []
    for mechanism_id, seed in sorted(seeds.items()):
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
        selected_seed_nodes = {
            node_id for node_id, node in graph_nodes.items()
            if _text(_get(node, "source_span_id")) in exact_span_set
            or _text(_get(node, "symbol_id")) in candidate_symbols
        }
        selected_graph_nodes, selected_graph_relations = _reachable_graph_nodes(
            nodes=graph_nodes,
            relations=graph_relations,
            entry_symbols=tuple(candidate_symbols),
            selected_seed_ids=tuple(selected_seed_nodes),
        )
        if selected_graph_nodes:
            exact_span_set.update(
                _text(_get(graph_nodes[node_id], "source_span_id"))
                for node_id in selected_graph_nodes
                if _text(_get(graph_nodes[node_id], "source_span_id"))
            )

        # Reachability is calculated from explicit graph edges, not names.
        entry_node_ids = {
            node_id for node_id, node in graph_nodes.items()
            if _text(_get(node, "symbol_id")) in set(seed["entry_symbol_ids"])
        }
        reachable_nodes: set[str] = set(entry_node_ids)
        if entry_node_ids:
            queue: deque[str] = deque(entry_node_ids)
            while queue:
                current = queue.popleft()
                for rid, relation in graph_relations.items():
                    if _text(_get(relation, "kind")).upper() not in _GRAPH_RELATIONS:
                        continue
                    source = _relation_endpoint(relation, "source", graph_nodes)
                    target = _relation_endpoint(relation, "target", graph_nodes)
                    if source == current and target in graph_nodes and target not in reachable_nodes:
                        reachable_nodes.add(target)
                        queue.append(target)

        operations: list[EvidenceOperationV1] = []
        seen_operations: set[str] = set()
        for atom in fact_atoms:
            operation_id = _text(atom.get("operation_id")) or f"fact-operation:{atom.get('fact_id')}"
            span_id = _text(atom.get("source_span_id") or next(iter(_ids(atom.get("span_ids", ()))), ""))
            raw_symbol_name = _text(atom.get("scope") or atom.get("subject"))
            symbol_name = exact_symbol_id(raw_symbol_name) or raw_symbol_name
            explicit_status = _text(atom.get("active_path_status"))
            default_branch, reachable_flag, scope_kind = path_resolution_inputs(
                symbol_name, raw_symbol_name, set(seed["entry_symbol_ids"])
            )
            if scope_kind in {"comparand", "evaluation"} and not explicit_status:
                explicit_status = "inactive_default"
            status = resolve_active_path_status(
                symbol_name=symbol_name,
                operation_id=operation_id,
                source_span_id=span_id,
                guard=_text(atom.get("guard")),
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
                guard=_text(atom.get("guard")),
                source_span_id=span_id,
                relation_ids=_ids(atom.get("relation_evidence_ids", ())),
                active_path_status=status,
                activation_basis_ids=_ids(atom.get("activation_basis_ids", ())),
                shape_or_type_hints=_ids(atom.get("shape_or_type_hints", ())),
                source_fact_ids=(_text(atom.get("fact_id")),) if _text(atom.get("fact_id")) else (),
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
            status = resolve_active_path_status(
                symbol_name=symbol_name,
                operation_id=operation_id,
                source_span_id=span_id,
                guard=_text(_get(node, "guard")),
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
                        status = resolve_active_path_status(
                            symbol_name=symbol_name,
                            operation_id=callee_operation_id,
                            source_span_id=_text(_get(callee_node, "source_span_id")),
                            guard=_text(_get(callee_node, "guard")),
                            config_bindings=config_values,
                            author_config_overrides=author_config_overrides,
                            default_branch=default_branch,
                            reachable=reachable_flag,
                            explicit_status=explicit_status,
                        )
                        operations.append(_graph_node_operation(
                            callee_node,
                            active_status=status,
                            exact_excerpt=resolver.read_span_id(_text(_get(callee_node, "source_span_id"))),
                            relation_ids=(relation_id,) if relation_id else (),
                            operation_id=callee_operation_id,
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
    relation_to_ops: dict[str, list[str]] = defaultdict(list)
    for op in operations:
        for relation_id in op.relation_ids:
            relation_to_ops[relation_id].append(op.operation_id)
    for operation_ids in relation_to_ops.values():
        unique = list(dict.fromkeys(operation_ids))
        for operation_id in unique[1:]:
            uf.union(unique[0], operation_id)

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
        left_facts = set(left.source_fact_ids)
        for right in operations[index + 1:]:
            right_operands, right_results = values(right)
            right_facts = set(right.source_fact_ids)
            same_span = bool(
                left.source_span_id
                and right.source_span_id
                and left.source_span_id == right.source_span_id
            )
            producer_consumer = bool(
                left_results.intersection(right_operands)
                or right_results.intersection(left_operands)
            )
            shared_fact = bool(left_facts.intersection(right_facts))
            shared_guard = bool(
                left.guard and right.guard and left.guard.strip() == right.guard.strip()
            )
            if same_span or producer_consumer or shared_fact or shared_guard:
                uf.union(left.operation_id, right.operation_id)
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
    if role in {"branch", "condition", "configuration", "limitation"}:
        return "supporting"
    # No ordinal cutoff: all proven active core transformations are retained.
    return "core" if statuses.issubset(_ACTIVE_STATUSES) else "supporting"


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


def _operation_status(operations: Sequence[EvidenceOperationV1]) -> ActivePathStatus:
    statuses = {operation.active_path_status for operation in operations}
    if len(statuses) == 1:
        return next(iter(statuses))  # type: ignore[return-value]
    if statuses.intersection(_INACTIVE_STATUSES) and statuses.intersection(_ACTIVE_STATUSES):
        return "conditional"
    return "unknown"


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

        detail_specs: list[tuple[str, tuple[EvidenceOperationV1, ...], DetailRole, DetailImportance, ActivePathStatus]] = []
        for index, cluster in enumerate(owned_clusters):
            role = _detail_role(cluster, index, len(owned_clusters))
            importance = _detail_importance(cluster, role=role)
            status = _operation_status(cluster)
            detail_specs.append((
                f"detail:{mechanism_id}:{index + 1}",
                cluster,
                role,
                importance,
                status,
            ))

        details: list[MechanismDetailV1] = []
        for index, (detail_id, cluster, role, importance, status) in enumerate(detail_specs):
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
            active_for_clean = (
                status in _ACTIVE_STATUSES
                and importance == "core"
                and all(operation.active_path_status in _ACTIVE_STATUSES for operation in cluster)
            )
            evidence_authority: EvidenceAuthority = (
                "repository_verified"
                if source_operation_ids and status in _ACTIVE_STATUSES
                else "repository_partial"
                if source_operation_ids and status != "unknown"
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
            conditions = tuple(dict.fromkeys(
                operation.guard for operation in cluster if operation.guard
            ))
            semantic_parts = [
                ", ".join(predicates) or "unresolved operation",
                f"inputs {', '.join(operands)}" if operands else "",
                f"outputs {', '.join(results)}" if results else "",
            ]
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
                semantic_atom="; ".join(part for part in semantic_parts if part),
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
                activation_basis_ids=tuple(dict.fromkeys(
                    basis for operation in cluster for basis in operation.activation_basis_ids
                )),
                source_operation_ids=source_operation_ids,
                source_fact_ids=source_fact_ids,
                source_claim_ids=source_claim_ids,
                source_span_ids=source_spans,
                source_equation_ids=source_equation_ids,
                exact_excerpts=tuple(dict.fromkeys(
                    operation.exact_excerpt for operation in cluster if operation.exact_excerpt
                )),
                source_facet_ids=intent["facet_ids"],
                source_brief_ids=intent["brief_ids"],
                source_obligation_ids=intent["obligation_ids"],
                author_statements=intent["author_statements"],
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
                importance="core",
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
        detail_ids = tuple(detail.detail_id for detail in details)
        input_ids = tuple(detail.detail_id for detail in details if detail.role in {"input", "representation"})
        output_ids = tuple(detail.detail_id for detail in details if detail.role == "output")
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
            input_detail_ids=input_ids or detail_ids[:1],
            ordered_detail_ids=detail_ids,
            output_detail_ids=output_ids or detail_ids[-1:],
            details=tuple(details),
            edges=tuple(edges),
            shared_detail_refs=(),
            unresolved_items=frozen_closure.unresolved_items,
            context_readiness=readiness,  # type: ignore[arg-type]
            readiness_failures=frozen_closure.unresolved_items,
            budget_exhausted=frozen_closure.budget_exhausted,
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
        unresolved_seed_ids=tuple(
            context.mechanism_id for context in final_contexts
            if context.context_readiness in {"partial", "blocked"}
        ),
        compiler_diagnostics=tuple({
            "mechanism_id": context.mechanism_id,
            "unresolved_items": list(context.unresolved_items),
        } for context in final_contexts if context.unresolved_items),
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


__all__ = [
    "DefinitionResolver",
    "resolve_active_path_status",
    "compile_mechanism_evidence_closures",
    "annotate_mechanism_paper_details",
    "compile_mechanism_contexts",
]
