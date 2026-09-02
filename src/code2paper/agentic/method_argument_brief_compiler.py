"""Deterministic compiler for Method argument briefs (WP-A).

Replaces the live default of per-cluster concept cards with one brief per
story node (or orphan obligation).  No LLM calls; mechanism drafts stay empty
until WP-C attaches a planner.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol

from code2paper.agentic.equation_claims import EquationClaimSetV1, EquationClaimV1
from code2paper.agentic.evidence_compiler_v3 import AtomicClaimSetV3, AtomicClaimV3
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2, IntentObligationV2
from code2paper.agentic.method_argument_brief_models import (
    ArgumentBriefGapV1,
    AuthorClauseLicenseV1,
    MechanismDraftV1,
    MethodArgumentBriefSetV1,
    MethodArgumentBriefV1,
)
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    MethodCompletenessMatrixV1,
    ReferenceMethodStatusV1,
)
from code2paper.agentic.method_product_models import AuthorStoryNodeV1

_VERIFIED_COMPLETENESS: frozenset[ReferenceMethodStatusV1] = frozenset({
    "supported_by_repository",
})


def _completeness_requires_caveat(
    statuses: Iterable[ReferenceMethodStatusV1],
) -> bool:
    return any(status not in _VERIFIED_COMPLETENESS for status in statuses)
from code2paper.agentic.obligation_fact_alignment import (
    ObligationCoverageReportV2,
    TargetAlignmentV1,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1


_CLAUSE_SPLIT_RE = re.compile(r"(?<=[.?;。；])\s+")
_IDENTIFIER_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
)
_LICENSE_STOP_WORDS = frozenset({
    "input", "model", "method", "output", "data",
})
_IDENTIFIER_NOISE = frozenset({"self", "torch", "dim", "dtype", "result"})


class MechanismDraftPlanner(Protocol):
    """WP-C planner hook; unused in WP-A."""

    def __call__(
        self,
        briefs: tuple[MethodArgumentBriefV1, ...],
    ) -> tuple[MechanismDraftV1, ...]:
        ...


@dataclass(frozen=True)
class _LicenseKeyBinding:
    key: str
    claim_id: str = ""
    equation_id: str = ""
    target_id: str = ""
    span_ids: tuple[str, ...] = ()
    tier: str = "supported"


@dataclass
class _ObligationCompileContext:
    obligation_id: str
    author_statement: str
    completeness_status: ReferenceMethodStatusV1
    claims: tuple[AtomicClaimV3, ...]
    equations: tuple[EquationClaimV1, ...]
    configuration_ids: tuple[str, ...]
    span_ids: tuple[str, ...]
    target_alignments: tuple[TargetAlignmentV1, ...]
    extra_stop_words: frozenset[str] = frozenset()
    key_bindings: dict[str, tuple[_LicenseKeyBinding, ...]] = field(default_factory=dict)
    unresolved_target_ids: tuple[str, ...] = ()


def _stable_id(prefix: str, *parts: str) -> str:
    material = "|".join(str(part) for part in parts if str(part))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _normalize_match_surface(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def extract_license_keys(
    text: str,
    *,
    extra_stop_words: frozenset[str] = frozenset(),
) -> set[str]:
    """Extract closed-set identifier license keys from evidence-side text."""

    keys: set[str] = set()
    stop = _LICENSE_STOP_WORDS | extra_stop_words | _IDENTIFIER_NOISE
    for match in _IDENTIFIER_RE.finditer(text):
        token = match.group(0)
        for part in token.split("."):
            normalized = part.casefold()
            if len(normalized) >= 4 and normalized not in stop:
                keys.add(normalized)
    return keys


def split_author_clauses(
    author_text: str,
    obligation_id: str,
) -> tuple[AuthorClauseLicenseV1, ...]:
    """Split author text into stable clause shells without licensing."""

    text = author_text.strip()
    if not text:
        return ()
    segments = [segment.strip() for segment in _CLAUSE_SPLIT_RE.split(text) if segment.strip()]
    if not segments:
        segments = [text]
    return tuple(
        AuthorClauseLicenseV1(
            clause_id=f"clause:{obligation_id}:{index}",
            text=segment,
            license="unlicensed",
            license_reason="split only",
        )
        for index, segment in enumerate(segments)
    )


def _claim_tier(claim: AtomicClaimV3) -> str | None:
    if claim.status == "supported":
        return "supported"
    if claim.status == "partial":
        return "partial"
    return None


def _target_tier(target: TargetAlignmentV1) -> str | None:
    if target.status == "resolved":
        return "supported"
    if target.status == "partial":
        return "partial"
    return None


def _extra_stop_words_from_targets(
    targets: Iterable[TypedBehaviorTargetV1],
) -> frozenset[str]:
    return frozenset(
        term.casefold()
        for target in targets
        for term in target.search_terms
        if len(term.strip()) < 4
    )


def _register_key_binding(
    registry: dict[str, list[_LicenseKeyBinding]],
    key: str,
    binding: _LicenseKeyBinding,
) -> None:
    existing = registry.setdefault(key, [])
    if binding not in existing:
        existing.append(binding)


def _target_license_text(target: TargetAlignmentV1) -> str:
    return " ".join(
        (
            *target.desired_predicates,
            *target.matched_predicates,
            *target.matched_semantic_fields,
            *target.required_semantic_fields,
        )
    )


def _build_key_registry(context: _ObligationCompileContext) -> None:
    registry: dict[str, list[_LicenseKeyBinding]] = {}
    for claim in context.claims:
        tier = _claim_tier(claim)
        if tier is None:
            continue
        span_ids = tuple(dict.fromkeys(claim.direct_evidence_ids))
        for key in extract_license_keys(
            claim.canonical_text,
            extra_stop_words=context.extra_stop_words,
        ):
            _register_key_binding(
                registry,
                key,
                _LicenseKeyBinding(
                    key=key,
                    claim_id=claim.claim_id,
                    span_ids=span_ids,
                    tier=tier,
                ),
            )
    for equation in context.equations:
        tier = "supported" if equation.validation_status == "supported" else "partial"
        for key in extract_license_keys(
            equation.expression,
            extra_stop_words=context.extra_stop_words,
        ):
            _register_key_binding(
                registry,
                key,
                _LicenseKeyBinding(
                    key=key,
                    equation_id=equation.equation_id,
                    tier=tier,
                ),
            )
    for target in context.target_alignments:
        tier = _target_tier(target)
        if tier is None:
            continue
        for key in extract_license_keys(
            _target_license_text(target),
            extra_stop_words=context.extra_stop_words,
        ):
            _register_key_binding(
                registry,
                key,
                _LicenseKeyBinding(
                    key=key,
                    target_id=target.target_id,
                    span_ids=target.matched_fact_ids,
                    tier=tier,
                ),
            )
    context.key_bindings = {
        key: tuple(bindings) for key, bindings in registry.items()
    }


def _obligation_shared_license_keys(
    context: _ObligationCompileContext,
) -> set[str]:
    key_sets = [
        extract_license_keys(
            claim.canonical_text,
            extra_stop_words=context.extra_stop_words,
        )
        for claim in context.claims
    ]
    if len(key_sets) <= 1:
        return set()
    shared = set(key_sets[0])
    for keys in key_sets[1:]:
        shared &= keys
    return shared


def _binding_matches_clause(
    binding: _LicenseKeyBinding,
    hit_keys: tuple[str, ...],
    context: _ObligationCompileContext,
) -> bool:
    hit = set(hit_keys)
    if binding.claim_id:
        claim = next(
            (item for item in context.claims if item.claim_id == binding.claim_id),
            None,
        )
        if claim is None:
            return False
        claim_keys = extract_license_keys(
            claim.canonical_text,
            extra_stop_words=context.extra_stop_words,
        )
        matched = claim_keys & hit
        if not matched:
            return False
        shared = _obligation_shared_license_keys(context)
        if matched - shared:
            return True
        return matched == claim_keys
    if binding.equation_id:
        equation = next(
            (item for item in context.equations if item.equation_id == binding.equation_id),
            None,
        )
        if equation is None:
            return False
        equation_keys = extract_license_keys(
            equation.expression,
            extra_stop_words=context.extra_stop_words,
        )
        return bool(equation_keys & hit)
    return bool(binding.target_id)


def _keys_hit_in_clause(
    clause_text: str,
    registry: dict[str, tuple[_LicenseKeyBinding, ...]],
) -> tuple[str, ...]:
    surface = _normalize_match_surface(clause_text)
    if not surface:
        return ()
    return tuple(
        key
        for key in registry
        if key and key in surface
    )


def _resolved_target_fact_ids(
    target_alignments: Iterable[TargetAlignmentV1],
) -> set[str]:
    return {
        fact_id
        for target in target_alignments
        if target.status == "resolved"
        for fact_id in target.matched_fact_ids
    }


def _license_clause(
    clause_text: str,
    context: _ObligationCompileContext,
    clause_index: int,
) -> AuthorClauseLicenseV1:
    clause_id = f"clause:{context.obligation_id}:{clause_index}"
    hit_keys = _keys_hit_in_clause(clause_text, context.key_bindings)
    if not hit_keys:
        return AuthorClauseLicenseV1(
            clause_id=clause_id,
            text=clause_text,
            license="unlicensed",
            license_reason="no closed-set license key hit",
        )

    supported_bindings: list[_LicenseKeyBinding] = []
    partial_bindings: list[_LicenseKeyBinding] = []
    seen_bindings: set[tuple[str, str, str]] = set()
    for key in hit_keys:
        for binding in context.key_bindings.get(key, ()):
            binding_key = (binding.claim_id, binding.equation_id, binding.target_id)
            if binding_key in seen_bindings:
                continue
            if not _binding_matches_clause(binding, hit_keys, context):
                continue
            seen_bindings.add(binding_key)
            if binding.tier == "supported":
                supported_bindings.append(binding)
            elif binding.tier == "partial":
                partial_bindings.append(binding)

    resolved_facts = _resolved_target_fact_ids(context.target_alignments)

    def _supported_binding(binding: _LicenseKeyBinding) -> bool:
        if binding.claim_id:
            claim = next(
                (item for item in context.claims if item.claim_id == binding.claim_id),
                None,
            )
            if claim is None or claim.status != "supported":
                return False
            if any(fact_id in resolved_facts for fact_id in claim.fact_ids):
                return True
            return claim.status == "supported"
        if binding.target_id and binding.tier == "supported":
            return bool(binding.span_ids)
        if binding.equation_id and binding.tier == "supported":
            return True
        return False

    positive_bindings = [
        binding
        for binding in supported_bindings
        if (binding.claim_id or binding.equation_id) and _supported_binding(binding)
    ]
    if positive_bindings:
        claim_ids = tuple(dict.fromkeys(
            binding.claim_id for binding in positive_bindings if binding.claim_id
        ))
        equation_ids = tuple(dict.fromkeys(
            binding.equation_id for binding in positive_bindings if binding.equation_id
        ))
        span_ids = tuple(dict.fromkeys(
            span_id
            for binding in positive_bindings
            for span_id in binding.span_ids
        ))
        target_ids = tuple(dict.fromkeys(
            binding.target_id for binding in positive_bindings if binding.target_id
        ))
        return AuthorClauseLicenseV1(
            clause_id=clause_id,
            text=clause_text,
            license="positively_licensed",
            bound_claim_ids=claim_ids,
            bound_equation_ids=equation_ids,
            bound_span_ids=span_ids,
            bound_target_ids=target_ids,
            license_reason="closed-set supported claim key",
        )

    partial_bindings = [
        binding
        for binding in (*supported_bindings, *partial_bindings)
        if binding.tier == "partial" or (
            binding.claim_id
            and any(
                item.claim_id == binding.claim_id and item.status == "partial"
                for item in context.claims
            )
        )
    ]
    if partial_bindings:
        claim_ids = tuple(dict.fromkeys(
            binding.claim_id for binding in partial_bindings if binding.claim_id
        ))
        equation_ids = tuple(dict.fromkeys(
            binding.equation_id for binding in partial_bindings if binding.equation_id
        ))
        target_ids = tuple(dict.fromkeys(
            binding.target_id for binding in partial_bindings if binding.target_id
        ))
        missing_targets = tuple(
            target.target_id
            for target in context.target_alignments
            if target.status != "resolved"
        )
        return AuthorClauseLicenseV1(
            clause_id=clause_id,
            text=clause_text,
            license="partially_licensed",
            bound_claim_ids=claim_ids,
            bound_equation_ids=equation_ids,
            bound_target_ids=target_ids,
            missing_target_ids=missing_targets,
            license_reason="partial claim or target alignment only",
        )

    return AuthorClauseLicenseV1(
        clause_id=clause_id,
        text=clause_text,
        license="unlicensed",
        license_reason="license keys hit but no supported or partial binding",
    )


def _compile_clauses_for_obligation(
    context: _ObligationCompileContext,
) -> tuple[AuthorClauseLicenseV1, ...]:
    _build_key_registry(context)
    shells = split_author_clauses(context.author_statement, context.obligation_id)
    return tuple(
        _license_clause(shell.text, context, index)
        for index, shell in enumerate(shells)
    )


def _resolve_author_statement(
    obligation_id: str,
    *,
    story_spine: Iterable[AuthorStoryNodeV1],
    completeness_by_id: dict[str, str],
    completeness_statement_by_id: dict[str, str],
    intent_by_id: dict[str, IntentObligationV2],
) -> str:
    for node in story_spine:
        if obligation_id in node.linked_obligation_ids and node.author_statement.strip():
            return node.author_statement.strip()
    if completeness_statement_by_id.get(obligation_id, "").strip():
        return completeness_statement_by_id[obligation_id].strip()
    intent = intent_by_id.get(obligation_id)
    if intent and intent.author_text.strip():
        return intent.author_text.strip()
    return completeness_statement_by_id.get(obligation_id, "").strip()


def _collect_obligation_context(
    obligation_id: str,
    *,
    claims: AtomicClaimSetV3,
    completeness: MethodCompletenessMatrixV1,
    coverage: ObligationCoverageReportV2 | None,
    intent_graph: IntentObligationGraphV2,
    equations: EquationClaimSetV1 | None,
    configurations: ConfigurationClaimSetV1 | None,
    story_spine: Iterable[AuthorStoryNodeV1],
    claim_ids_by_obligation: Mapping[str, tuple[str, ...]] | None = None,
) -> _ObligationCompileContext:
    completeness_by_id = {
        item.obligation_id: item.status for item in completeness.items
    }
    completeness_statement_by_id = {
        item.obligation_id: item.statement for item in completeness.items
    }
    intent_by_id = {item.obligation_id: item for item in intent_graph.obligations}
    coverage_by_id = {
        item.obligation_id: item
        for item in (coverage.items if coverage else [])
    }
    if claim_ids_by_obligation is None:
        obligation_claims = tuple(
            claim for claim in claims.claims
            if obligation_id in claim.covers_obligation_ids
        )
    else:
        claim_by_id = {claim.claim_id: claim for claim in claims.claims}
        obligation_claims = tuple(
            claim_by_id[claim_id]
            for claim_id in claim_ids_by_obligation.get(obligation_id, ())
            if claim_id in claim_by_id
        )
    claim_ids = {claim.claim_id for claim in obligation_claims}
    equation_items = tuple(
        equation
        for equation in (equations.equations if equations else [])
        if equation.prose_claim_id in claim_ids
        or any(
            fact_id in claim.fact_ids
            for claim in obligation_claims
            for fact_id in equation.fact_ids
        )
    )
    obligation_fact_ids = tuple(
        dict.fromkeys(
            fact_id
            for claim in obligation_claims
            for fact_id in claim.fact_ids
        )
    )
    configuration_ids = tuple(
        config.configuration_id
        for config in (configurations.claims if configurations else [])
        if any(fact_id in config.source_fact_ids for fact_id in obligation_fact_ids)
    )
    span_ids = tuple(dict.fromkeys(
        span_id
        for claim in obligation_claims
        for span_id in claim.direct_evidence_ids
    ))
    target_alignments = (
        coverage_by_id[obligation_id].target_alignments
        if obligation_id in coverage_by_id
        else ()
    )
    intent_obligation = intent_by_id.get(obligation_id)
    return _ObligationCompileContext(
        obligation_id=obligation_id,
        author_statement=_resolve_author_statement(
            obligation_id,
            story_spine=story_spine,
            completeness_by_id=completeness_by_id,
            completeness_statement_by_id=completeness_statement_by_id,
            intent_by_id=intent_by_id,
        ),
        completeness_status=completeness_by_id.get(obligation_id, "unverified_by_repository"),  # type: ignore[arg-type]
        claims=obligation_claims,
        equations=equation_items,
        configuration_ids=configuration_ids,
        span_ids=span_ids,
        target_alignments=target_alignments,
        extra_stop_words=_extra_stop_words_from_targets(
            intent_obligation.typed_behavior_targets if intent_obligation else ()
        ),
        unresolved_target_ids=tuple(
            target.target_id
            for target in target_alignments
            if target.status != "resolved"
        ),
    )


def _mechanism_draft_for_brief(
    brief_id: str,
    *,
    requires_caveat: bool,
) -> MechanismDraftV1:
    if requires_caveat:
        return MechanismDraftV1(
            draft_id=_stable_id("draft", brief_id),
            brief_id=brief_id,
            status="empty",
        )
    return MechanismDraftV1(
        draft_id=_stable_id("draft", brief_id),
        brief_id=brief_id,
        status="not_required",
    )


def _may_enter_verified(
    clauses: Iterable[AuthorClauseLicenseV1],
    completeness_statuses: Iterable[ReferenceMethodStatusV1],
) -> bool:
    if _completeness_requires_caveat(completeness_statuses):
        return False
    positive = [clause for clause in clauses if clause.license == "positively_licensed"]
    if not positive:
        return False
    if any(clause.license in {"partially_licensed", "unlicensed"} for clause in clauses):
        return False
    claim_ids = {
        claim_id
        for clause in positive
        for claim_id in clause.bound_claim_ids
    }
    equation_ids = {
        equation_id
        for clause in positive
        for equation_id in clause.bound_equation_ids
    }
    # An independently validated equation is a sufficient deterministic
    # authority atom.  Do not require a prose claim id merely because the
    # clause happens to be equation-only; the equation-only path remains
    # closed by AuthorClauseLicenseV1's bound equation ids.
    return bool(claim_ids or equation_ids)


_GLOBAL_RANK_MARKERS = (
    "pagerank",
    "ppr",
    "run_ppr",
    "passage_score",
    "hybrid rank",
    "global rank",
)
_LOCAL_ACTIVATION_MARKERS = (
    "first retrieval",
    "semantic bridging",
    "local activation",
    "entity activation",
)


def _claim_is_global_rank(text: str) -> bool:
    folded = str(text or "").casefold()
    return any(marker in folded for marker in _GLOBAL_RANK_MARKERS)


def _node_is_local_activation(node: AuthorStoryNodeV1) -> bool:
    folded = f"{node.title} {node.author_statement} {node.intended_role}".casefold()
    return any(marker in folded for marker in _LOCAL_ACTIVATION_MARKERS)


def _claim_fits_story_node(
    claim: AtomicClaimV3,
    node: AuthorStoryNodeV1,
    sibling_nodes: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1],
) -> bool:
    """Drop claims whose tokens match a sibling stage more than this node."""

    if _node_is_local_activation(node) and _claim_is_global_rank(claim.canonical_text):
        return False
    from code2paper.agentic.obligation_fact_alignment import _stage_fold_tokens

    claim_tokens = _stage_fold_tokens(claim.canonical_text)
    own = _stage_fold_tokens(f"{node.title} {node.author_statement}")
    union_own = claim_tokens | own
    own_score = (len(claim_tokens & own) / len(union_own)) if union_own else 0.0
    for sibling in sibling_nodes:
        if sibling.story_node_id == node.story_node_id:
            continue
        sib = _stage_fold_tokens(f"{sibling.title} {sibling.author_statement}")
        union_sib = claim_tokens | sib
        sib_score = (len(claim_tokens & sib) / len(union_sib)) if union_sib else 0.0
        if sib_score >= 0.25 and sib_score > own_score + 0.05:
            return False
    return True


def _claim_id_mentions_obligation(claim_id: str, obligation_id: str) -> bool:
    """Return whether a claim id carries an explicit obligation identity.

    ``covers_obligation_ids`` is an evidence-coverage relation and may be
    intentionally broad (especially for callback facts).  A claim id that
    embeds the obligation, on the other hand, is a deterministic ownership
    hint emitted by the claim compiler.  Keep this helper deliberately
    lexical and exact: it must not infer ownership from claim prose.
    """

    claim_value = str(claim_id or "").strip()
    obligation_value = str(obligation_id or "").strip()
    if not claim_value or not obligation_value:
        return False
    return obligation_value in claim_value


def _claim_ids_by_obligation_from_stage_groups(
    claims: AtomicClaimSetV3,
) -> dict[str, tuple[str, ...]]:
    """Project semantic-stage claim membership onto obligation ids.

    Stage groups are the planning authority for paragraph organization.  A
    claim's multi-obligation evidence coverage must not make it a member of
    every obligation it happens to support.  For each group, all ordered
    claims belong to the group's primary ``O-STAGE-*`` obligation; secondary
    obligations receive only claims whose stable id explicitly names that
    obligation (or claims with a singleton coverage edge).  This preserves
    legitimate shared evidence while preventing callback/technical facts
    from leaking into sibling briefs.

    The projection is used only when semantic groups exist.  Older callers
    without that closed organization surface retain the historical direct
    coverage behavior in ``_collect_obligation_context``.
    """

    claim_by_id = {claim.claim_id: claim for claim in claims.claims}
    result: dict[str, list[str]] = {}
    for group in (getattr(claims, "semantic_stage_groups", ()) or ()):
        declared = tuple(dict.fromkeys(
            str(value).strip()
            for value in (getattr(group, "covers_obligation_ids", ()) or ())
            if str(value).strip()
        ))
        ordered_claim_ids = tuple(dict.fromkeys(
            str(value).strip()
            for value in (getattr(group, "ordered_claim_ids", ()) or ())
            if str(value).strip() and str(value).strip() in claim_by_id
        ))
        if not declared or not ordered_claim_ids:
            continue
        primary = next(
            (
                obligation_id for obligation_id in declared
                if "O-STAGE-" in obligation_id.upper()
            ),
            declared[0],
        )
        for claim_id in ordered_claim_ids:
            result.setdefault(primary, []).append(claim_id)
        for obligation_id in declared:
            if obligation_id == primary:
                continue
            for claim_id in ordered_claim_ids:
                claim = claim_by_id[claim_id]
                covered = tuple(
                    str(value).strip()
                    for value in (claim.covers_obligation_ids or ())
                    if str(value).strip()
                )
                if (
                    _claim_id_mentions_obligation(claim_id, obligation_id)
                    or len(covered) == 1
                ):
                    result.setdefault(obligation_id, []).append(claim_id)

    # Claims produced directly for an obligation may not be listed in the
    # current semantic group (for example a late technical fact appended
    # after the stage compiler ran).  Their explicit id edge is still a safe
    # local ownership signal.  A broad callback claim has neither this edge
    # nor singleton coverage, so it remains confined to the stage group that
    # explicitly ordered it.
    for claim in claims.claims:
        covered = tuple(
            str(value).strip()
            for value in (claim.covers_obligation_ids or ())
            if str(value).strip()
        )
        for obligation_id in covered:
            if _claim_id_mentions_obligation(claim.claim_id, obligation_id) or len(covered) == 1:
                result.setdefault(obligation_id, []).append(claim.claim_id)

    return {
        obligation_id: tuple(dict.fromkeys(values))
        for obligation_id, values in result.items()
    }


def _compile_brief_for_node(
    node: AuthorStoryNodeV1,
    *,
    contexts: dict[str, _ObligationCompileContext],
    sibling_nodes: tuple[AuthorStoryNodeV1, ...] | list[AuthorStoryNodeV1] = (),
) -> MethodArgumentBriefV1:
    brief_id = f"brief:{node.story_node_id}"
    all_clauses: list[AuthorClauseLicenseV1] = []
    claim_ids: list[str] = []
    equation_ids: list[str] = []
    configuration_ids: list[str] = []
    span_ids: list[str] = []
    statuses: list[ReferenceMethodStatusV1] = []
    statements: list[str] = []
    for obligation_id in node.linked_obligation_ids:
        context = contexts[obligation_id]
        statements.append(context.author_statement)
        statuses.append(context.completeness_status)
        all_clauses.extend(_compile_clauses_for_obligation(context))
        claim_ids.extend(
            claim.claim_id
            for claim in context.claims
            if _claim_fits_story_node(claim, node, sibling_nodes)
        )
        equation_ids.extend(equation.equation_id for equation in context.equations)
        configuration_ids.extend(context.configuration_ids)
        span_ids.extend(context.span_ids)

    author_statement = " ".join(statement.strip() for statement in statements if statement.strip())
    if not author_statement:
        author_statement = node.author_statement.strip()
    requires_caveat = (
        any(
            clause.license in {"partially_licensed", "unlicensed"}
            for clause in all_clauses
        )
        or _completeness_requires_caveat(statuses)
    )
    licensed_wording = " ".join(
        clause.text for clause in all_clauses if clause.license == "positively_licensed"
    ).strip()
    return MethodArgumentBriefV1(
        brief_id=brief_id,
        story_node_id=node.story_node_id,
        intended_role=node.intended_role,
        obligation_ids=node.linked_obligation_ids,
        author_statement=author_statement,
        completeness_statuses=tuple(statuses),
        clauses=tuple(all_clauses),
        licensed_wording=licensed_wording,
        claim_ids=tuple(dict.fromkeys(claim_ids)),
        equation_ids=tuple(dict.fromkeys(equation_ids)),
        configuration_ids=tuple(dict.fromkeys(configuration_ids)),
        span_ids=tuple(dict.fromkeys(span_ids)),
        mechanism_draft=_mechanism_draft_for_brief(
            brief_id,
            requires_caveat=requires_caveat,
        ),
        may_enter_verified=_may_enter_verified(all_clauses, statuses),
        requires_caveat=requires_caveat,
    )


def compile_method_argument_briefs(
    *,
    claims: AtomicClaimSetV3,
    completeness: MethodCompletenessMatrixV1,
    coverage: ObligationCoverageReportV2 | None,
    intent_graph: IntentObligationGraphV2,
    story_spine: Iterable[AuthorStoryNodeV1],
    equations: EquationClaimSetV1 | None = None,
    configurations: ConfigurationClaimSetV1 | None = None,
    planner: MechanismDraftPlanner | None = None,
    require_planner_for_unlicensed: bool = False,
) -> MethodArgumentBriefSetV1:
    """Compile deterministic argument briefs without concept-card LLM calls."""

    spine = tuple(story_spine)
    claim_ids_by_obligation = (
        _claim_ids_by_obligation_from_stage_groups(claims)
        if getattr(claims, "semantic_stage_groups", ())
        else None
    )
    obligation_ids = tuple(dict.fromkeys(
        obligation_id
        for item in completeness.items
        for obligation_id in (item.obligation_id,)
    ))
    contexts = {
        obligation_id: _collect_obligation_context(
            obligation_id,
            claims=claims,
            completeness=completeness,
            coverage=coverage,
            intent_graph=intent_graph,
            equations=equations,
            configurations=configurations,
            story_spine=spine,
            claim_ids_by_obligation=claim_ids_by_obligation,
        )
        for obligation_id in obligation_ids
    }

    briefs: list[MethodArgumentBriefV1] = []
    covered_obligations: set[str] = set()
    for node in spine:
        if not node.linked_obligation_ids:
            continue
        briefs.append(_compile_brief_for_node(
            node,
            contexts=contexts,
            sibling_nodes=spine,
        ))
        covered_obligations.update(node.linked_obligation_ids)

    for obligation_id in obligation_ids:
        if obligation_id in covered_obligations:
            continue
        context = contexts[obligation_id]
        clauses = _compile_clauses_for_obligation(context)
        brief_id = f"brief:{obligation_id}"
        requires_caveat = (
            any(
                clause.license in {"partially_licensed", "unlicensed"}
                for clause in clauses
            )
            or _completeness_requires_caveat((context.completeness_status,))
        )
        briefs.append(
            MethodArgumentBriefV1(
                brief_id=brief_id,
                story_node_id=f"orphan:{obligation_id}",
                intended_role="algorithm_step",
                obligation_ids=(obligation_id,),
                author_statement=context.author_statement,
                completeness_statuses=(context.completeness_status,),
                clauses=clauses,
                licensed_wording=" ".join(
                    clause.text
                    for clause in clauses
                    if clause.license == "positively_licensed"
                ).strip(),
                claim_ids=tuple(claim.claim_id for claim in context.claims),
                equation_ids=tuple(equation.equation_id for equation in context.equations),
                configuration_ids=context.configuration_ids,
                span_ids=context.span_ids,
                mechanism_draft=_mechanism_draft_for_brief(
                    brief_id,
                    requires_caveat=requires_caveat,
                ),
                may_enter_verified=_may_enter_verified(
                    clauses,
                    (context.completeness_status,),
                ),
                requires_caveat=requires_caveat,
            )
        )

    gaps: list[ArgumentBriefGapV1] = []
    planner_targets = tuple(
        brief for brief in briefs
        if brief.requires_caveat and brief.mechanism_draft.status == "empty"
    )
    if require_planner_for_unlicensed and planner is None and planner_targets:
        for brief in planner_targets:
            gaps.append(
                ArgumentBriefGapV1(
                    gap_kind="planner_required",
                    brief_id=brief.brief_id,
                    message=(
                        "Unlicensed or partial clauses require a mechanism planner "
                        "draft before live authoring rebuild can continue."
                    ),
                )
            )

    planner_used = False
    planner_traces: tuple[dict[str, Any], ...] = ()
    if planner is not None and planner_targets:
        planner_used = True
        produced = {
            draft.brief_id: draft
            for draft in planner(planner_targets)
        }
        planner_gaps = getattr(planner, "gaps", None) or ()
        gaps.extend(planner_gaps)
        planner_traces = tuple(getattr(planner, "call_traces", None) or ())
        failed_brief_ids = {
            gap.brief_id
            for gap in planner_gaps
            if gap.gap_kind == "planner_failed" and gap.brief_id
        }
        updated: list[MethodArgumentBriefV1] = []
        for brief in briefs:
            draft = produced.get(brief.brief_id)
            if draft is not None:
                updated.append(brief.model_copy(update={"mechanism_draft": draft}))
            elif brief.brief_id in failed_brief_ids:
                updated.append(brief)
            else:
                updated.append(brief)
        briefs = updated

    return MethodArgumentBriefSetV1(
        repo_snapshot_id=claims.repo_snapshot_id,
        project_tree_hash=claims.project_tree_hash,
        claims_digest=claims.content_digest,
        completeness_digest=completeness.content_digest,
        coverage_digest=coverage.content_digest if coverage else "",
        intent_digest=intent_graph.content_digest,
        briefs=tuple(briefs),
        planner_used=planner_used,
        gaps=tuple(gaps),
        planner_call_traces=planner_traces,
    )
