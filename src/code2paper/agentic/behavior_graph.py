"""R2.1 core contracts for the generic CodeBehaviorGraph.

Implements the V1 behavior graph schema from design section 6:

- ``BehaviorNodeV1``  - a single static operation (READ / WRITE / CALL / ...);
- ``BehaviorRelationV1`` - a typed edge between two nodes or symbols
  (CONTAINS / NEXT_CONTROL / CALLS / DATA_DEPENDS_ON / ...);
- ``CodeBehaviorGraphV1`` - the container with content-addressed digest;
- ``SymbolRefV1`` / ``SymbolIndexV2`` / ``ReferenceSetV1`` - the adapter
  interface types;
- ``LanguageBehaviorAdapter`` - the Protocol every language adapter
  implements.

The contracts are deliberately Python-agnostic: the only Python-specific
field is ``source_span_id`` (which uses the ``span:<path>:<start>:<end>``
format established by the research tools), and even that is a string.
The Python AST adapter lives in ``python_behavior_adapter.py`` and is the
first concrete implementation; future languages plug in by implementing
the Protocol.

Design invariants enforced here:

- every node carries a ``source_span_id`` and ``source_authority`` so a
  downstream fact compiler can refuse to anchor a positive claim on a
  hint-only node;
- every relation carries both ``source_span_id`` and (optionally)
  ``target_span_id`` so cross-function relations stay auditable;
- ``unresolved_relations`` is a first-class channel: dynamic calls,
  reflection and monkey-patching MUST be recorded here, never guessed;
- ``content_digest`` covers nodes + relations + unresolved, so a
  checkpoint resume can detect graph drift.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from code2paper.agentic.source_authority import SourceAuthorityV1


BEHAVIOR_GRAPH_SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Enumerations (Literal types so Pydantic rejects unknown values)
# ---------------------------------------------------------------------------


BehaviorPredicate = str
BEHAVIOR_PREDICATES: tuple[str, ...] = (
    "READ",
    "WRITE",
    "CALL",
    "CONSTRUCT",
    "LOAD",
    "RETURN",
    "TRANSFORM",
    "CONCAT",
    "STACK",
    "NORMALIZE",
    "REDUCE",
    "AGGREGATE",
    "COMPUTE",
    "COMPARE",
    "BRANCH",
    "LOOP",
    "SELECT",
    "TOPK",
    "SORT",
    "MASK",
    "FILTER",
    "RESHAPE",
    "PROJECT",
    "ATTEND",
    "SAMPLE",
    "PROPAGATE",
    "SERIALIZE",
)
_PREDICATE_SET = frozenset(BEHAVIOR_PREDICATES)


BehaviorRelationKind = str
BEHAVIOR_RELATION_KINDS: tuple[str, ...] = (
    "CONTAINS",
    "NEXT_CONTROL",
    "TRUE_BRANCH",
    "FALSE_BRANCH",
    "CALLS",
    "RETURNS_TO",
    "DATA_DEPENDS_ON",
    "CONTROL_DEPENDS_ON",
    "CONFIGURED_BY",
    "READS_FROM",
    "WRITES_TO",
    "ALIAS_OF",
    "OVERRIDES",
    "IMPLEMENTS",
)
_RELATION_KIND_SET = frozenset(BEHAVIOR_RELATION_KINDS)


# ---------------------------------------------------------------------------
# Symbol reference (adapter interface type)
# ---------------------------------------------------------------------------


class SymbolRefV1(BaseModel):
    """A reference to a single indexed symbol.

    Adapters receive a ``SymbolRefV1`` and return behavior nodes / relations
    scoped to that symbol.  The ``symbol_id`` is stable across runs for the
    same (path, qualified_name, span) triple.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol_id: str
    path: str
    qualified_name: str
    kind: str  # "module" | "class" | "function" | "method"
    start_line: int = 1
    end_line: int = 1
    parent_symbol_id: str = ""
    docstring: str = ""
    text_hash: str = ""


class SymbolIndexV2(BaseModel):
    """V3-era symbol index produced by a language adapter.

    Replaces the legacy ``SymbolIndexReport`` for the V3 research plane.
    The index is content-addressed so a checkpoint resume can detect
    index drift.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.0"
    repo_snapshot_id: str
    project_tree_hash: str
    language: str = "python"
    indexed_files: int = 0
    indexed_symbols: int = 0
    symbols: list[SymbolRefV1] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    content_digest: str = ""

    def find(self, symbol_id: str) -> SymbolRefV1 | None:
        for sym in self.symbols:
            if sym.symbol_id == symbol_id:
                return sym
        return None


class ReferenceSiteV1(BaseModel):
    """A single reference site (import or usage) for a symbol."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    line: int = 1
    kind: str  # "import" | "usage" | "attribute" | "subscript"
    span_id: str
    source_authority: SourceAuthorityV1 = "executable_hard"
    snippet: str = ""


class ReferenceSetV1(BaseModel):
    """All reference sites for a single symbol across the snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol_id: str
    qualified_name: str
    sites: tuple[ReferenceSiteV1, ...] = ()
    unresolved: tuple[str, ...] = ()  # reasons a reference could not be resolved


# ---------------------------------------------------------------------------
# Behavior nodes and relations
# ---------------------------------------------------------------------------


class BehaviorNodeV1(BaseModel):
    """A single static operation extracted from source.

    ``node_id`` is stable: it is derived from ``symbol_id``,
    ``source_span_id``, ``predicate`` and a per-span sequence number so the
    same source always produces the same node id.  This lets an incremental
    graph builder deduplicate nodes across calls.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    symbol_id: str
    operation_id: str
    predicate: BehaviorPredicate
    operands: tuple[str, ...] = ()
    result: str = ""
    guard: str = ""
    iteration_context: str = ""
    shape_or_type_hints: tuple[str, ...] = ()
    source_span_id: str
    source_authority: SourceAuthorityV1 = "executable_hard"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    diagnostics: tuple[str, ...] = ()

    @field_validator("predicate")
    @classmethod
    def _validate_predicate(cls, value: str) -> str:
        if value not in _PREDICATE_SET:
            raise ValueError(f"unknown behavior predicate: {value!r}")
        return value

    @classmethod
    def make_node_id(
        cls,
        *,
        symbol_id: str,
        source_span_id: str,
        predicate: str,
        seq: int,
    ) -> str:
        raw = f"{symbol_id}|{source_span_id}|{predicate}|{seq}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"node:{digest}"


class UnresolvedRelationV1(BaseModel):
    """A relation that could not be statically resolved.

    Dynamic calls, reflection and monkey-patching MUST be recorded here
    rather than guessed.  A fact compiler treats any relation that appears
    only in ``unresolved_relations`` as ``unsupported``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation_id: str
    kind: BehaviorRelationKind
    source_node_id: str
    source_symbol_id: str
    source_span_id: str
    reason: str  # "dynamic_call" | "reflection" | "monkey_patch" | "external_module" | ...
    target_hint: str = ""  # best-effort textual hint, never used as a fact anchor

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        if value not in _RELATION_KIND_SET:
            raise ValueError(f"unknown behavior relation kind: {value!r}")
        return value


class BehaviorRelationV1(BaseModel):
    """A typed edge between two behavior nodes or two symbols.

    For intra-symbol relations, ``source_node_id`` and ``target_node_id``
    are both set.  For inter-symbol relations (CALLS, RETURNS_TO,
    DATA_DEPENDS_ON across function boundaries), ``target_symbol_id`` is
    also set so the supervisor can route a follow-up ``read_symbol`` call.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation_id: str
    kind: BehaviorRelationKind
    source_node_id: str
    target_node_id: str = ""
    source_symbol_id: str
    target_symbol_id: str = ""
    source_span_id: str
    target_span_id: str = ""
    argument_binding: dict[str, str] = Field(default_factory=dict)
    guard: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("kind")
    @classmethod
    def _validate_kind(cls, value: str) -> str:
        if value not in _RELATION_KIND_SET:
            raise ValueError(f"unknown behavior relation kind: {value!r}")
        return value

    @classmethod
    def make_relation_id(
        cls,
        *,
        kind: str,
        source_node_id: str,
        target_node_id: str = "",
        seq: int = 0,
    ) -> str:
        raw = f"{kind}|{source_node_id}|{target_node_id}|{seq}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"rel:{digest}"


# ---------------------------------------------------------------------------
# Graph container
# ---------------------------------------------------------------------------


class CodeBehaviorGraphV1(BaseModel):
    """The generic behavior graph container.

    The graph is content-addressed: ``content_digest`` covers every node,
    relation and unresolved relation in canonical order.  A checkpoint
    resume that observes a different digest MUST treat the persisted graph
    as stale and trigger a rebuild.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = BEHAVIOR_GRAPH_SCHEMA_VERSION
    repo_snapshot_id: str
    project_tree_hash: str
    language: str = "python"
    nodes: list[BehaviorNodeV1] = Field(default_factory=list)
    relations: list[BehaviorRelationV1] = Field(default_factory=list)
    unresolved_relations: list[UnresolvedRelationV1] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    content_digest: str = ""

    def with_digest(self) -> "CodeBehaviorGraphV1":
        """Return a copy with a freshly computed ``content_digest``."""

        return self.model_copy(update={"content_digest": self._compute_digest()})

    def _compute_digest(self) -> str:
        payload = {
            "schema_version": self.schema_version,
            "repo_snapshot_id": self.repo_snapshot_id,
            "project_tree_hash": self.project_tree_hash,
            "language": self.language,
            "nodes": [n.model_dump(mode="json") for n in self.nodes],
            "relations": [r.model_dump(mode="json") for r in self.relations],
            "unresolved": [u.model_dump(mode="json") for u in self.unresolved_relations],
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def nodes_for_symbol(self, symbol_id: str) -> list[BehaviorNodeV1]:
        return [n for n in self.nodes if n.symbol_id == symbol_id]

    def relations_for_symbol(self, symbol_id: str) -> list[BehaviorRelationV1]:
        return [
            r
            for r in self.relations
            if r.source_symbol_id == symbol_id or r.target_symbol_id == symbol_id
        ]

    def predicates(self) -> set[str]:
        return {n.predicate for n in self.nodes}

    def relation_kinds(self) -> set[str]:
        return {r.kind for r in self.relations}

    def merge(self, other: "CodeBehaviorGraphV1") -> "CodeBehaviorGraphV1":
        """Merge another graph into this one, deduplicating by id.

        Used by the incremental ``build_behavior_subgraph`` tool to combine
        per-symbol subgraphs without producing duplicate nodes/relations.
        """

        if self.repo_snapshot_id != other.repo_snapshot_id:
            raise ValueError(
                f"cannot merge behavior graphs from different snapshots: "
                f"{self.repo_snapshot_id!r} vs {other.repo_snapshot_id!r}"
            )
        if self.project_tree_hash != other.project_tree_hash:
            raise ValueError(
                "cannot merge behavior graphs with different project_tree_hash"
            )
        seen_nodes: set[str] = {n.node_id for n in self.nodes}
        seen_rels: set[str] = {r.relation_id for r in self.relations}
        seen_unres: set[str] = {u.relation_id for u in self.unresolved_relations}
        nodes = list(self.nodes)
        relations = list(self.relations)
        unresolved = list(self.unresolved_relations)
        for node in other.nodes:
            if node.node_id not in seen_nodes:
                seen_nodes.add(node.node_id)
                nodes.append(node)
        for rel in other.relations:
            if rel.relation_id not in seen_rels:
                seen_rels.add(rel.relation_id)
                relations.append(rel)
        for unres in other.unresolved_relations:
            if unres.relation_id not in seen_unres:
                seen_unres.add(unres.relation_id)
                unresolved.append(unres)
        merged = CodeBehaviorGraphV1(
            schema_version=self.schema_version,
            repo_snapshot_id=self.repo_snapshot_id,
            project_tree_hash=self.project_tree_hash,
            language=self.language,
            nodes=nodes,
            relations=relations,
            unresolved_relations=unresolved,
            warnings=list(dict.fromkeys([*self.warnings, *other.warnings])),
        )
        return merged.with_digest()


# ---------------------------------------------------------------------------
# Language adapter Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LanguageBehaviorAdapter(Protocol):
    """The contract every language adapter implements.

    The adapter is stateless: every method takes the snapshot / symbol it
    needs and returns a value type.  This keeps adapters testable in
    isolation and lets the supervisor cache results by symbol id.
    """

    language: str

    def index_symbols(self, repo_snapshot_id: str, project_tree_hash: str, files: list[str]) -> SymbolIndexV2:
        ...

    def extract_operations(self, symbol: SymbolRefV1, source_text: str) -> list[BehaviorNodeV1]:
        ...

    def extract_relations(self, symbol: SymbolRefV1, source_text: str, nodes: list[BehaviorNodeV1]) -> list[BehaviorRelationV1]:
        ...

    def resolve_references(self, symbol: SymbolRefV1, index: SymbolIndexV2, files: dict[str, str]) -> ReferenceSetV1:
        ...


# ---------------------------------------------------------------------------
# Validation helpers (used by the adapter and tests)
# ---------------------------------------------------------------------------


def assert_valid_predicate(predicate: str) -> None:
    if predicate not in _PREDICATE_SET:
        raise ValueError(f"unknown behavior predicate: {predicate!r}")


def assert_valid_relation_kind(kind: str) -> None:
    if kind not in _RELATION_KIND_SET:
        raise ValueError(f"unknown behavior relation kind: {kind!r}")


def make_span_id(path: str, start_line: int, end_line: int) -> str:
    """Stable span id matching the research_tools convention."""

    return f"span:{path}:{start_line}:{end_line}"


def make_symbol_id(path: str, qualified_name: str, start_line: int) -> str:
    """Stable symbol id derived from (path, qualified_name, start_line)."""

    raw = f"{path}|{qualified_name}|{start_line}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"sym:{digest}"


__all__ = [
    "BEHAVIOR_GRAPH_SCHEMA_VERSION",
    "BEHAVIOR_PREDICATES",
    "BEHAVIOR_RELATION_KINDS",
    "BehaviorNodeV1",
    "BehaviorRelationV1",
    "BehaviorPredicate",
    "BehaviorRelationKind",
    "CodeBehaviorGraphV1",
    "LanguageBehaviorAdapter",
    "ReferenceSetV1",
    "ReferenceSiteV1",
    "SymbolIndexV2",
    "SymbolRefV1",
    "UnresolvedRelationV1",
    "assert_valid_predicate",
    "assert_valid_relation_kind",
    "make_span_id",
    "make_symbol_id",
]
