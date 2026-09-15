"""Repository-verified definition values for configuration accesses.

A branch such as ``if self.cfg.use_dedicated_attention:`` cannot be resolved
from the access site alone: the value lives in the repository's own
configuration file (for example ``conf/config.yaml``).  Without a definition
fact the access claim stays ``unresolved``, every operation on the branch keeps
``active_path_status="unknown"``, and the frozen mechanism-completeness gate
reports ``operation_disposition_unresolved`` -- so no Candidate can be written
even though the value is sitting in an authenticated source file.

This module closes that gap deterministically.  It reads the *frozen snapshot*
(never the working tree), matches an access expression's leaf key against the
repository's structured configuration files, and emits one ``configured_by``
definition fact carrying the parsed scalar value, the declaration span and the
``definition_default`` resolution marker the configuration-claim compiler
already understands.  Ambiguity is never guessed: several disagreeing
declarations, a non-scalar value, a missing/unreadable file or a digest drift
all produce no fact, leaving the access unresolved and visible.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from code2paper.agentic.generic_fact_compiler import (
    CodeFactSetV1,
    CodeFactV1,
    _digest,
    _fact_id,
    _relation_fact_prefix,
)
from code2paper.agentic.retrieval import config_key_entries, match_config_key
from code2paper.agentic.source_inventory import classify_source_kind


#: Access expressions such as ``self.cfg.use_dedicated_attention``.  The leaf
#: key is what a configuration file declares.
_CONFIG_ACCESS_EXPRESSION_RE = re.compile(
    r"\b(?:self\.)?(?:cfg|config|conf|args|options|params|parameters|settings|flags)"
    r"\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
)
_CONFIG_ACCESS_PREDICATES = frozenset({
    "configured_by", "configures", "configure", "loads_weights",
})
_RESOLUTION_MARKERS = frozenset({
    "definition_default", "entrypoint_override", "branch_value", "dead_branch",
})
#: Structured configuration suffixes this module can read a value from.
_CONFIG_SUFFIXES = (".yaml", ".yml", ".toml", ".json")


def _as_text(value: Any) -> str:
    return str(value or "")


def _flatten_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(_as_text(item) for item in value)
    return (_as_text(value),)


def _access_expressions(fact: Any) -> tuple[tuple[str, str], ...]:
    """Return ``(expression, leaf_key)`` pairs one fact exposes."""

    found: list[tuple[str, str]] = []
    for term in (
        _as_text(getattr(fact, "subject", "")),
        *_flatten_values(getattr(fact, "object", ())),
        *_flatten_values(getattr(fact, "semantic_context", ())),
    ):
        for match in _CONFIG_ACCESS_EXPRESSION_RE.finditer(term):
            leaf = match.group(1).rsplit(".", 1)[-1]
            if leaf:
                found.append((match.group(0), leaf))
    return tuple(dict.fromkeys(found))


def _resolved_expressions(fact_set: CodeFactSetV1) -> set[str]:
    """Access expressions some fact already resolves."""

    resolved: set[str] = set()
    for fact in fact_set.facts:
        markers = set(_flatten_values(getattr(fact, "semantic_context", ())))
        if not markers & _RESOLUTION_MARKERS:
            continue
        resolved.update(
            expression for expression, _leaf in _access_expressions(fact)
        )
    return resolved


def _pending_access_leaves(
    fact_set: CodeFactSetV1,
) -> dict[str, tuple[str, ...]]:
    """Map each unresolved leaf key to the access expressions that read it."""

    already = _resolved_expressions(fact_set)
    pending: dict[str, list[str]] = {}
    for fact in fact_set.facts:
        predicate = _as_text(getattr(fact, "predicate", ""))
        markers = set(_flatten_values(getattr(fact, "semantic_context", ())))
        is_access = (
            "config_access" in markers
            or predicate in _CONFIG_ACCESS_PREDICATES
        )
        if not is_access or str(getattr(fact, "validation_status", "")) != "supported":
            continue
        for expression, leaf in _access_expressions(fact):
            if expression in already:
                continue
            pending.setdefault(leaf, [])
            if expression not in pending[leaf]:
                pending[leaf].append(expression)
    return {leaf: tuple(items) for leaf, items in pending.items()}


def _lookup_value(payload: Any, keypath: str) -> Any:
    """Walk a dotted keypath through a parsed configuration payload."""

    current = payload
    for part in str(keypath or "").split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
            continue
        match = re.fullmatch(r"([^\[\]]+)\[(\d+)\]", part)
        if match and isinstance(current, Mapping):
            base = current.get(match.group(1))
            if isinstance(base, list):
                index = int(match.group(2))
                if index < len(base):
                    current = base[index]
                    continue
        return _MISSING
    return current


_MISSING = object()


def _scalar(value: Any) -> bool:
    return isinstance(value, (bool, int, float, str)) and value is not None


def _render_scalar(value: Any) -> str:
    """Render a definition value into the fact object's string contract.

    ``CodeFactV1.object`` is ``str | list[str]``; the configuration-claim
    compiler restores the typed value for facts marked ``config_definition``,
    so the rendering here stays exact and lossless for bool/int/float/text.
    """

    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _candidate_config_paths(repo_snapshot: Any) -> tuple[str, ...]:
    paths = []
    for item in (getattr(repo_snapshot, "included_files", None) or ()):
        path = _as_text(getattr(item, "path", ""))
        if not path or _as_text(getattr(item, "kind", "file")) != "file":
            continue
        if not path.lower().endswith(_CONFIG_SUFFIXES):
            continue
        # Only the configuration partition may define a value; dataset,
        # vendor, generated and checkpoint files never do.
        if classify_source_kind(path) != "configuration":
            continue
        paths.append(path)
    return tuple(sorted(dict.fromkeys(paths)))


def _read_snapshot_text(repo_snapshot: Any, path: str) -> str | None:
    """Read one snapshot file, refusing digest drift and unreadable bytes."""

    record = next(
        (
            item
            for item in (getattr(repo_snapshot, "included_files", None) or ())
            if _as_text(getattr(item, "path", "")) == path
        ),
        None,
    )
    if record is None:
        return None
    root = Path(_as_text(getattr(repo_snapshot, "project_root", "")) or "").resolve()
    if not str(root):
        return None
    candidate = root / path
    if not candidate.is_file():
        return None
    try:
        text = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    expected = _as_text(getattr(record, "content_digest", ""))
    if expected:
        import hashlib

        actual = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        if actual != expected:
            return None
    return text


def _definition_for_leaf(
    leaf: str,
    *,
    repo_snapshot: Any,
) -> tuple[str, int, str, Any] | None:
    """Return ``(path, line, keypath, value)`` for an unambiguous definition."""

    from code2paper.agentic.retrieval import parse_config_payload

    matches: list[tuple[str, int, str, Any]] = []
    for path in _candidate_config_paths(repo_snapshot):
        text = _read_snapshot_text(repo_snapshot, path)
        if text is None:
            continue
        entries = config_key_entries(text=text, rel_path=path)
        if not entries:
            continue
        found, ambiguous = match_config_key(entries, leaf)
        if ambiguous or not found:
            continue
        try:
            payload = parse_config_payload(text=text, rel_path=path, warnings=[])
        except Exception:  # noqa: BLE001 - an unparseable file is not evidence
            continue
        for keypath, line, _preview in found:
            value = _lookup_value(payload, keypath)
            if value is _MISSING or not _scalar(value):
                continue
            matches.append((path, int(line), keypath, value))

    if not matches:
        return None
    distinct = {repr(value) for _path, _line, _key, value in matches}
    if len(distinct) > 1:
        # Disagreeing declarations are ambiguous, never averaged or guessed.
        return None
    return min(matches, key=lambda item: (item[0], item[1]))


def append_configuration_definition_facts(
    fact_set: CodeFactSetV1,
    *,
    repo_snapshot: Any,
    allowed_definition_span_ids: Iterable[str] | None = None,
) -> CodeFactSetV1:
    """Return ``fact_set`` plus one definition fact per resolvable access.

    The added fact keeps the *access expression* as its subject so the
    configuration-claim compiler produces a claim whose key is exactly the
    expression the branch condition uses.  When
    ``allowed_definition_span_ids`` is supplied, a definition is emitted only
    if its exact declaration span is already carried by the owning evidence
    packet.  This keeps packet and fact provenance closed while retaining the
    unrestricted helper for callers that are constructing the packet itself.
    """

    if repo_snapshot is None or not fact_set.facts:
        return fact_set
    pending = _pending_access_leaves(fact_set)
    if not pending:
        return fact_set
    allowed_spans = (
        {
            str(value).strip()
            for value in allowed_definition_span_ids
            if str(value).strip()
        }
        if allowed_definition_span_ids is not None
        else None
    )

    added: list[CodeFactV1] = []
    seen: set[tuple[str, str, int]] = set()
    for leaf in sorted(pending):
        definition = _definition_for_leaf(leaf, repo_snapshot=repo_snapshot)
        if definition is None:
            continue
        path, line, keypath, value = definition
        span_id = f"span:{path}:{line}:{line}"
        if allowed_spans is not None and span_id not in allowed_spans:
            continue
        for expression in pending[leaf]:
            identity_key = (expression, path, line)
            if identity_key in seen:
                continue
            seen.add(identity_key)
            obligation_prefix = _relation_fact_prefix("configuration")
            identity = _digest({
                "snapshot": _as_text(getattr(repo_snapshot, "snapshot_id", "")),
                "subject": expression,
                "predicate": "configured_by",
                "object": value,
                "keypath": keypath,
                "path": path,
                "line": line,
            })
            added.append(CodeFactV1(
                fact_id=_fact_id(obligation_prefix, identity),
                subject=expression,
                predicate="configured_by",
                object=_render_scalar(value),
                conditions=[],
                scope="",
                direct_span_ids=[span_id],
                relation_span_ids=[],
                relation_evidence_ids=[],
                relation_kinds=[],
                semantic_context=[
                    expression,
                    "config_access",
                    "definition_default",
                    "config_definition",
                    f"config_path:{path}",
                    f"config_keypath:{keypath}",
                ],
                exact_source_digest=_digest([span_id, repr(value)]),
                canonical_identity=identity,
                validation_status="supported",
                validation_failures=[],
            ))

    if not added:
        return fact_set
    # Rebuild the fact set and recompute its content digest exactly like the
    # fact compiler does; ``model_copy`` would leave a stale digest behind.
    facts = (*fact_set.facts, *added)
    return CodeFactSetV1(
        producer_version=fact_set.producer_version,
        repo_snapshot_id=fact_set.repo_snapshot_id,
        project_tree_hash=fact_set.project_tree_hash,
        evidence_packet_digest=fact_set.evidence_packet_digest,
        facts=list(facts),
        content_digest=_digest([
            item.model_dump(mode="json") for item in facts
        ]),
    )


__all__ = ["append_configuration_definition_facts"]
