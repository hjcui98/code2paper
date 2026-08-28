"""Generic target-implementation ownership and acquisition helpers.

These helpers deliberately operate on the repository's typed symbol and
behavior records.  They do not know benchmark names or paper answers.  The
scope is a safety projection used for ranking and audit; it never creates an
evidence fact by itself.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from code2paper.agentic.behavior_graph import make_symbol_id
from code2paper.agentic.research_models import (
    CandidateAcquisitionLedgerV1,
    CandidateAcquisitionRecordV1,
    ImplementationOwnershipRoleV1,
    ImplementationScopeV1,
)
from code2paper.agentic.typed_refs import split_span_ref, split_symbol_ref


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}")
_EVALUATION_RE = re.compile(
    r"(?:^|[/_.-])(eval(?:uate|uation)?|benchmark|metric|metrics|ablation|test|tests)(?:$|[/_.-])",
    re.I,
)
_COMPARAND_RE = re.compile(
    r"(?:baseline|compar(?:e|ison)|competitor|ablati(?:on|ve)|reference)",
    re.I,
)
_CONFIG_RE = re.compile(
    r"(?:config|configuration|settings?|options?|args?|flags?|params?|hyperparam)",
    re.I,
)

_OWNERSHIP_GRAPH_RELATIONS = frozenset(
    {"CALLS", "RETURNS_TO", "CONTAINS", "IMPLEMENTS", "OVERRIDES"}
)


def _tokens(value: Any) -> set[str]:
    return {item.casefold() for item in _TOKEN_RE.findall(str(value or ""))}


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


def _canonical_symbol_id(value: Any, symbols_by_id: Mapping[str, Any]) -> str:
    """Resolve a symbol id or a typed location ref to the indexed id."""

    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw in symbols_by_id:
        return raw
    parsed = split_symbol_ref(raw)
    if parsed is not None:
        path, name, line = parsed
        for symbol_id, symbol in symbols_by_id.items():
            if (
                str(_attr(symbol, "path", "") or "") == path
                and int(_attr(symbol, "start_line", 0) or 0) == line
                and str(_attr(symbol, "qualified_name", "") or "")
                in {name, name.split(".")[-1]}
            ):
                return symbol_id
        # The adapter and typed-ref builder share this stable id scheme.
        candidate = make_symbol_id(path, name, line)
        if candidate in symbols_by_id:
            return candidate
    # Accept a compact path/name or path-only seed when it uniquely resolves.
    for symbol_id, symbol in symbols_by_id.items():
        path = str(_attr(symbol, "path", "") or "")
        name = str(_attr(symbol, "qualified_name", "") or "")
        if raw in {path, f"{path}:{name}", f"{path}:{name.split('.')[-1]}"}:
            return symbol_id
    return raw


def _candidate_location(value: str) -> tuple[str, str, int] | None:
    parsed = split_symbol_ref(value)
    if parsed is not None:
        return parsed
    return None


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
    intent_tokens = set().union(*(_tokens(item) for item in author_items)) if author_items else set()

    graph_nodes = {
        str(_attr(node, "node_id", "") or ""): node
        for node in (getattr(behavior_graph, "nodes", ()) or ())
        if str(_attr(node, "node_id", "") or "")
    }
    graph_relations = tuple(getattr(behavior_graph, "relations", ()) or ()) if behavior_graph is not None else ()

    # When the caller has no explicit entrypoint symbol, infer only a small,
    # deterministic set of likely method roots.  This is a scope hint, not
    # evidence: ambiguous symbols remain unknown and cannot authorize claims.
    # Prefer roots exposed by the typed call/containment topology; lexical
    # overlap is only a tie-breaker and never turns a baseline/evaluator into a
    # target merely because it shares an API name.
    if not entry_ids and by_id and graph_relations:
        outgoing: dict[str, set[str]] = {}
        incoming: set[str] = set()
        for relation in graph_relations:
            if str(_attr(relation, "kind", "") or "") not in _OWNERSHIP_GRAPH_RELATIONS:
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
            text = _symbol_text(symbol)
            name = str(_attr(symbol, "qualified_name", "") or "").casefold()
            overlap = len(_tokens(text) & intent_tokens)
            lifecycle_bonus = 2 if any(
                token in name.split(".")[-1]
                for token in ("forward", "encode", "infer", "train", "fit", "run", "main")
            ) else 0
            root_scores.append((overlap * 3 + lifecycle_bonus + len(outgoing[symbol_id]), symbol_id))
        root_scores.sort(key=lambda item: (-item[0], item[1]))
        if root_scores and (intent_tokens or len(root_scores) == 1):
            best_score = root_scores[0][0]
            entry_ids = tuple(
                symbol_id for score, symbol_id in root_scores if score == best_score
            )[:3]

    if not entry_ids and by_id and intent_tokens:
        scored: list[tuple[int, str]] = []
        for symbol_id, symbol in by_id.items():
            path = str(_attr(symbol, "path", "") or "")
            text = _symbol_text(symbol)
            if _EVALUATION_RE.search(path) or _COMPARAND_RE.search(path) or _CONFIG_RE.search(path):
                continue
            kind = str(_attr(symbol, "kind", "") or "").casefold()
            if kind not in {"function", "method", "class", "module"}:
                continue
            overlap = len(_tokens(text) & intent_tokens)
            name = str(_attr(symbol, "qualified_name", "") or "").casefold()
            lifecycle_bonus = 2 if any(
                token in name.split(".")[-1]
                for token in ("forward", "encode", "infer", "train", "fit", "run", "main")
            ) else 0
            if overlap or lifecycle_bonus:
                scored.append((overlap * 3 + lifecycle_bonus, symbol_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        if scored and scored[0][0] >= 2:
            best_score = scored[0][0]
            entry_ids = tuple(symbol_id for score, symbol_id in scored if score == best_score)[:3]

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
        if _EVALUATION_RE.search(path) or _EVALUATION_RE.search(text):
            roles[symbol_id] = {"evaluation"}
            continue
        if _COMPARAND_RE.search(path) or _COMPARAND_RE.search(text):
            # A reachable symbol is still a target dependency when the graph
            # proves it is called by the target.  Otherwise it is audit-only.
            if symbol_id not in reachable:
                roles[symbol_id] = {"comparand"}
            continue
        if _CONFIG_RE.search(path) or _CONFIG_RE.search(text):
            if symbol_id not in reachable and symbol_id not in entry_ids:
                roles[symbol_id] = {"configuration"}
                continue
        if not roles[symbol_id]:
            overlap = len(_tokens(text) & intent_tokens)
            if overlap >= 2:
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
    scope: ImplementationScopeV1,
    candidate: str,
    *,
    behavior_graph: Any | None = None,
) -> ImplementationOwnershipRoleV1:
    """Resolve a heterogeneous candidate reference before role lookup."""

    raw = str(candidate or "").strip()
    direct = scope.role_for(raw)
    if direct != "unknown" or behavior_graph is None:
        return direct
    for node in getattr(behavior_graph, "nodes", ()) or ():
        if _node_matches_candidate(node, raw):
            role = scope.role_for(str(_attr(node, "symbol_id", "") or ""))
            if role != "unknown":
                return role
    return direct


def _candidate_context(candidate: str, behavior_graph: Any | None) -> set[str]:
    """Return semantic context for a candidate without reading source text."""

    values: list[set[str]] = [_tokens(candidate)]
    if behavior_graph is not None:
        location = _candidate_location(candidate)
        for node in getattr(behavior_graph, "nodes", ()) or ():
            same = False
            if location is not None:
                path, name, line = location
                span = str(_attr(node, "source_span_id", "") or "")
                same = str(_attr(node, "symbol_id", "") or "") == candidate
                if not same and span.count(":") >= 3:
                    parsed_span = split_span_ref(span)
                    same = bool(
                        parsed_span
                        and parsed_span[0] == path
                        and parsed_span[1] <= line <= parsed_span[2]
                    )
            else:
                same = str(_attr(node, "symbol_id", "") or "") == candidate
            if same:
                values.append(_tokens(" ".join(
                    str(_attr(node, attr, "") or "")
                    for attr in ("predicate", "operands", "result", "guard", "shape_or_type_hints")
                )))
    return set().union(*values)


def _node_matches_candidate(node: Any, candidate: str) -> bool:
    """Match a behavior node to a stable id or typed location candidate."""

    raw = str(candidate or "").strip()
    if not raw:
        return False
    if str(_attr(node, "node_id", "") or "") in {
        raw,
        raw.removeprefix("behavior:"),
    }:
        return True
    symbol_id = str(_attr(node, "symbol_id", "") or "")
    if raw.removeprefix("symbol:") == symbol_id:
        return True
    location = _candidate_location(raw)
    if location is None:
        return False
    path, _name, line = location
    parsed_span = split_span_ref(str(_attr(node, "source_span_id", "") or ""))
    return bool(parsed_span and parsed_span[0] == path and parsed_span[1] <= line <= parsed_span[2])


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
        matched = bool(candidate_spans.intersection(spans))
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
        if not candidate_spans or candidate_spans.intersection(spans):
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
                context = _candidate_context(canonical, behavior_graph)
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
                        if _node_matches_candidate(node, canonical)
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
                if location is not None:
                    path, name, line = location
                    located = any(
                        (parsed := split_span_ref(span)) is not None
                        and parsed[0] == path
                        and parsed[1] <= line <= parsed[2]
                        for span in spans
                    )
                if exact or located:
                    matched_obs.append(observation)
            read_obs = [item for item in matched_obs if item.tool_name in {"read_symbol", "read_code_span"} and item.status == "success"]
            symbol_matches = [
                node for node in nodes
                if str(_attr(node, "symbol_id", "") or "") == candidate_id.removeprefix("symbol:")
                or _node_matches_candidate(node, candidate_id)
            ]
            compiled = compiled_by_obligation.get(obligation_id)
            candidate_spans = {
                str(_attr(node, "source_span_id", "") or "") for node in symbol_matches
            }
            packet_ids, packet_span_ids = _candidate_packet_refs(
                compiled, candidate_spans=candidate_spans, location=location
            )
            fact_ids, fact_set_ids = _candidate_fact_refs(
                compiled, candidate_spans=packet_span_ids or candidate_spans
            )
            claim_ids = _candidate_claim_refs(compiled, fact_set_ids)
            role = scope_role_for_candidate(scope, candidate_id, behavior_graph=behavior_graph)
            terminal_status = "discovered"
            rejection_reason = ""
            if role in {"comparand", "evaluation"}:
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
