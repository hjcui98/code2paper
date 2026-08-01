"""Generic configuration-claim compilation from executable evidence.

Configuration is not a synonym for a literal default found in a source file.
This module only emits a positive configuration claim when the value can be
traced to an executable access or a configured entrypoint.  Surface defaults
without an active path are retained as ``default``/``unreachable`` metadata,
never as an ``actual`` claim.
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


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def compile_configuration_claims(
    fact_set: CodeFactSetV1,
    *,
    repo_snapshot_id: str | None = None,
    project_tree_hash: str | None = None,
) -> ConfigurationClaimSetV1:
    """Compile configuration claims from generic fact artifacts.

    ``configured_by`` relation facts are treated as actual only when they
    have a direct relation span.  Configuration-access facts are conditional
    when guards are present and default otherwise.  Rejected facts are kept
    as unreachable records so a writer can explain why a requested detail is
    unavailable without turning it into positive prose.
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
        ) and fact.predicate in {"reads", "selects", "configured_by", "computes", "transforms", "returns", "projects"}
        if not is_config_relation and not is_config_access:
            continue
        value = fact.object
        if is_config_relation:
            state = "actual" if fact.validation_status == "supported" and fact.direct_span_ids else "unreachable"
            entrypoint_spans = tuple(fact.direct_span_ids) if state == "actual" else ()
            definition_spans = tuple(fact.relation_span_ids)
        elif fact.validation_status != "supported":
            state = "unreachable"
            entrypoint_spans = ()
            definition_spans = tuple(fact.direct_span_ids)
        elif fact.conditions:
            state = "conditional"
            entrypoint_spans = tuple(fact.direct_span_ids)
            definition_spans = tuple(fact.direct_span_ids)
        else:
            state = "default"
            entrypoint_spans = tuple(fact.direct_span_ids)
            definition_spans = tuple(fact.direct_span_ids)
        claims.append(ConfigurationClaimV1(
            configuration_id="config:" + _digest(fact.canonical_identity)[:20],
            key=fact.subject or "configuration",
            value=value if isinstance(value, (str, int, float, bool)) or value is None else json.dumps(value, ensure_ascii=False, sort_keys=True),
            state=state,
            definition_span_ids=definition_spans,
            entrypoint_span_ids=entrypoint_spans,
            override_chain=tuple(fact.relation_evidence_ids),
            conditions=tuple(fact.conditions),
            source_authority="executable_hard",
            active=state != "unreachable",
            unresolved_reason=("fact_rejected:" + ";".join(fact.validation_failures)) if state == "unreachable" else "",
        ))
    # Content-addressed de-duplication keeps the writer budget stable when a
    # relation and its corresponding access are observed more than once.
    unique: dict[str, ConfigurationClaimV1] = {}
    for claim in claims:
        unique.setdefault(claim.canonical_identity, claim)
    return ConfigurationClaimSetV1(
        repo_snapshot_id=repo_snapshot_id or fact_set.repo_snapshot_id,
        project_tree_hash=project_tree_hash or fact_set.project_tree_hash,
        claims=tuple(unique.values()),
    )


__all__ = ["compile_configuration_claims"]
