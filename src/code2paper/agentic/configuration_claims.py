"""Generic configuration-claim compilation from executable evidence.

Configuration is not a synonym for a literal default found in a source file.
This module only emits a positive configuration claim when the value can be
traced to an executable access or a configured entrypoint.  Surface defaults
without an active path are retained as ``default``/``unreachable`` metadata,
never as an ``actual`` claim.

Key semantics (round-8 repair):
- ``key`` is the exact configuration access/key (for example ``args.input_dim``
  or ``args.keep_percent``), never the consumer function that reads it.
- A ``default`` claim requires an actual definition/default span (a
  ``definition_default`` resolution marker or a ``parameter_default`` read).
- An ``actual`` claim requires a traced entrypoint/override value
  (``entrypoint_override`` marker).
- A bare configuration access whose value cannot be resolved from the
  repository is retained as a typed ``unresolved`` record with ``value=None``;
  the access expression is never serialized as the resolved value.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    ConfigurationClaimV1,
)

#: Resolution markers that establish a real resolved value in
#: ``semantic_context``.  Absence of every marker means the fact is a bare
#: config access whose value is unknown to the repository.
_DEFINITION_DEFAULT = "definition_default"
_ENTRYPOINT_OVERRIDE = "entrypoint_override"
_BRANCH_VALUE = "branch_value"
_DEAD_BRANCH = "dead_branch"
_RESOLUTION_MARKERS = frozenset({
    _DEFINITION_DEFAULT,
    _ENTRYPOINT_OVERRIDE,
    _BRANCH_VALUE,
    _DEAD_BRANCH,
})

#: Predicates that can carry a config access or a resolved config value.
_CONFIG_PREDICATES = frozenset({
    "reads", "loads_weights", "selects", "configured_by", "computes",
    "transforms", "returns", "projects",
})

_ACCESS_RE = re.compile(r"(?:^|[^A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)")


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _access_terms(object_value: str | list[str]) -> tuple[str, ...]:
    """Return the exact access expressions carried by a fact's object.

    A list object in the frozen D2.5 pipeline is the access expression itself
    (for example ``["args.input_dim"]``); a dotted access string is also
    recognized.  Scalar literals are treated as resolved values, not access
    terms.
    """

    if isinstance(object_value, list):
        return tuple(
            str(item).strip()
            for item in object_value
            if str(item).strip() and not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", str(item).strip())
        )
    text = str(object_value).strip()
    if not text or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text):
        return ()
    return (text,)


def compile_configuration_claims(
    fact_set: CodeFactSetV1,
    *,
    repo_snapshot_id: str | None = None,
    project_tree_hash: str | None = None,
) -> ConfigurationClaimSetV1:
    """Compile configuration claims from generic fact artifacts.

    Resolution is marker-primary: a fact carries a *resolved value* only when
    its semantic context has a resolution marker (``entrypoint_override``,
    ``definition_default``, ``branch_value``) or a definition-time default read
    (``parameter_default`` diagnostic).  A bare ``configured_by`` relation or
    ``config_access`` observation without any resolution evidence is a typed
    ``unresolved`` access: its key is the exact access expression (for example
    ``args.input_dim``), its value is ``None``, and the plan may route it to
    configuration research instead of forcing the Writer to render an unknown
    value.  Rejected facts are kept as ``unreachable`` records.
    """

    claims: list[ConfigurationClaimV1] = []
    for fact in fact_set.facts:
        is_config_relation = fact.predicate == "configured_by"
        source_terms = " ".join(
            [
                str(fact.subject),
                str(fact.object),
                *[str(item) for item in fact.semantic_context],
            ]
        ).lower()
        is_config_access = (
            any("config_access" in str(item).lower() for item in fact.semantic_context)
            or bool(re.search(r"\b(config|configuration|settings?|parameters?|options?|args?)\b", source_terms))
        ) and fact.predicate in _CONFIG_PREDICATES
        if not is_config_relation and not is_config_access:
            continue
        markers = set(str(item) for item in fact.semantic_context)
        resolution_markers = markers & _RESOLUTION_MARKERS
        has_parameter_default = any(
            "parameter_default" in str(item).lower() for item in fact.semantic_context
        )
        if fact.validation_status != "supported":
            # Rejected facts are never positive; the rejected reason is kept.
            state = "unreachable"
            key = fact.subject or "configuration"
            value: str | int | float | bool | None = (
                fact.object if isinstance(fact.object, (str, int, float, bool)) or fact.object is None
                else json.dumps(fact.object, ensure_ascii=False, sort_keys=True)
            )
            definition_spans = tuple(fact.direct_span_ids)
            entrypoint_spans: tuple[str, ...] = ()
            unresolved_reason = "fact_rejected:" + ";".join(fact.validation_failures)
        elif resolution_markers or has_parameter_default:
            # Resolved value backed by explicit resolution evidence.  The key
            # is the config name carried by the subject; the object is the
            # value.
            if _ENTRYPOINT_OVERRIDE in resolution_markers:
                state = "actual"
                definition_spans: tuple[str, ...] = ()
                entrypoint_spans = tuple(fact.direct_span_ids)
            elif _DEFINITION_DEFAULT in resolution_markers or has_parameter_default:
                state = "default"
                definition_spans = tuple(fact.direct_span_ids)
                entrypoint_spans = ()
            elif _BRANCH_VALUE in resolution_markers or fact.conditions:
                state = "conditional"
                definition_spans = tuple(fact.direct_span_ids)
                entrypoint_spans = ()
            else:
                state = "default"
                definition_spans = tuple(fact.direct_span_ids)
                entrypoint_spans = ()
            key = fact.subject or "configuration"
            value = (
                fact.object if isinstance(fact.object, (str, int, float, bool)) or fact.object is None
                else json.dumps(fact.object, ensure_ascii=False, sort_keys=True)
            )
            unresolved_reason = ""
        else:
            # Bare config access: the key is the exact access expression and
            # the value is not resolvable from this repository snapshot.
            access_terms = _access_terms(fact.object)
            state = "unresolved"
            key = access_terms[0] if len(access_terms) == 1 else (
                " ".join(access_terms) if access_terms else (fact.subject or "configuration")
            )
            value = None
            definition_spans = ()
            entrypoint_spans = ()
            unresolved_reason = (
                "config_access_unresolved:no_definition_or_entrypoint_value_evidence"
            )
        claims.append(ConfigurationClaimV1(
            configuration_id="config:" + _digest(f"{key}|{state}|{fact.canonical_identity}")[:20],
            key=key,
            value=value,
            state=state,
            definition_span_ids=definition_spans,
            entrypoint_span_ids=entrypoint_spans,
            override_chain=tuple(fact.relation_evidence_ids),
            conditions=tuple(fact.conditions),
            source_authority="executable_hard",
            source_fact_ids=(fact.fact_id,),
            active=state != "unreachable",
            unresolved_reason=unresolved_reason,
        ))
    # Content-addressed de-duplication keeps the writer budget stable when a
    # relation and its corresponding access are observed more than once.  A
    # resolved claim dedups on its exact identity; an unresolved access dedups
    # on (key, state, value, conditions) so repeated access observations for
    # the same key merge into one typed record.
    unique: dict[str, ConfigurationClaimV1] = {}
    for claim in claims:
        if claim.state == "unresolved":
            identity = _digest({
                "kind": "unresolved_access",
                "key": claim.key,
                "state": claim.state,
                "conditions": tuple(claim.conditions),
            })
        else:
            identity = claim.canonical_identity
        unique.setdefault(identity, claim)
    return ConfigurationClaimSetV1(
        repo_snapshot_id=repo_snapshot_id or fact_set.repo_snapshot_id,
        project_tree_hash=project_tree_hash or fact_set.project_tree_hash,
        claims=tuple(unique.values()),
    )


__all__ = ["compile_configuration_claims"]
