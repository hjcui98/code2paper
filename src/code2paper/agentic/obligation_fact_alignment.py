"""R5.2 / R5.3 obligation-to-fact alignment.

Implements design section 8.4 (Agent 何时主动补充信息) and the R5.3
execution plan.  The V1 coverage resolver in ``intent_obligations.py``
used English token overlap and project-specific claim ids to decide
whether an obligation was covered.  This module replaces that with a
deterministic, project-agnostic alignment layer that matches
``TypedBehaviorTargetV1.desired_predicates`` against ``CodeFactV1.predicate``.

Hard rules enforced here (R5.3):

- a training-scoped target (``conditions == ("training",)``) can only be
  covered by facts whose code guards indicate training; inference facts
  never cover a training obligation;
- an inference-scoped target can only be covered by facts whose guards
  indicate inference or carry no training guard;
- a target with no scope condition may be covered by any fact;
- ``verify_only`` obligations (rationale / innovation / mismatch) may
  terminate as ``explicit_gap`` but never as ``supported`` even if a
  matching fact exists, because their typed targets describe behavior
  the author *expects* but the code may legitimately not contain;
- explicit gaps recorded against an obligation count as terminal
  ``not_implemented_in_repo`` regardless of fact alignment.

R5.4 hard constraint: this module's source MUST NOT contain project-specific
literals (``F-RAP-*``, ``C-RAP-*``, ``EBCAR``, ``DyG-Mamba``, ``LinearRAG``).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    ExplicitCodeGapV1,
)
from code2paper.agentic.behavior_graph import BehaviorRelationV1
from code2paper.agentic.generic_fact_compiler import BEHAVIOR_PREDICATE_TO_FACT
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    IntentObligationV2,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1


# ---------------------------------------------------------------------------
# Predicate mapping (uppercase behavior predicate <-> lowercase fact predicate)
# ---------------------------------------------------------------------------


#: Reverse of ``BEHAVIOR_PREDICATE_TO_FACT``: lowercase fact predicate ->
#: uppercase behavior predicate.  Used to align ``CodeFactV1.predicate``
#: against ``TypedBehaviorTargetV1.desired_predicates``.
FACT_PREDICATE_TO_BEHAVIOR: dict[str, str] = {
    fact_pred: behavior_pred
    for behavior_pred, fact_pred in BEHAVIOR_PREDICATE_TO_FACT.items()
}

#: Extra fact predicates that are relation-derived (``configured_by``) or
#: chain-derived (``calls_in_order``).  These map to their closest
#: behavior predicate so relation-level facts still align with targets
#: that ask for ``CONFIGURED_BY`` / ``CALL``.
EXTRA_FACT_PREDICATE_ALIASES: dict[str, str] = {
    "calls_in_order": "CALL",
    "configured_by": "CONFIGURED_BY",
    # Profile-specific predicates used by structure-triggered evidence
    # profiles.  These are not emitted by the generic fact compiler but
    # are the canonical predicates for hand-authored evidence profiles.
    "computes": "COMPUTE",
    "implements": "CONSTRUCT",
    "collects": "AGGREGATE",
    "dispatches": "CALL",
    "optimizes": "COMPUTE",
}

#: Combined lookup: lowercase fact predicate -> uppercase behavior predicate.
#: Every ``CodeFactV1.predicate`` value MUST resolve through this table; an
#: unknown predicate yields no alignment so the obligation stays unresolved
#: rather than being silently covered.
FACT_PREDICATE_TO_BEHAVIOR_FULL: dict[str, str] = {
    **FACT_PREDICATE_TO_BEHAVIOR,
    **EXTRA_FACT_PREDICATE_ALIASES,
}


#: Predicate aliases: when a target desires the key predicate, facts
#: mapping to any of the listed equivalent predicates also satisfy it.
#: This bridges the gap between the intent-graph predicate vocabulary
#: (which includes abstract predicates like AGGREGATE / CONSTRUCT) and
#: the ``PythonBehaviorAdapter`` output (which emits concrete predicates
#: like CONCAT / STACK / CALL).  Without these aliases, obligations
#: desiring AGGREGATE or CONSTRUCT can never be resolved because the
#: adapter never emits those predicates directly.
BEHAVIOR_PREDICATE_ALIASES: dict[str, frozenset[str]] = {
    # AGGREGATE = collect/combine multiple items into a group; in Python
    # code this is implemented via concatenation, stacking, or reduction.
    "AGGREGATE": frozenset({"CONCAT", "STACK", "REDUCE"}),
    # CONSTRUCT = create a new object/instance; in Python code this is a
    # constructor call (tagged as CALL by the adapter) or a load.
    "CONSTRUCT": frozenset({"CALL", "LOAD"}),
}


def _expand_desired_with_aliases(desired: set[str]) -> set[str]:
    """Expand a desired-predicate set with alias-equivalent predicates."""
    expanded = set(desired)
    for pred in desired:
        expanded.update(BEHAVIOR_PREDICATE_ALIASES.get(pred, frozenset()))
    return expanded


def _alias_satisfied(desired_pred: str, matched: set[str]) -> bool:
    """Check whether ``desired_pred`` is satisfied directly or via alias."""
    if desired_pred in matched:
        return True
    aliases = BEHAVIOR_PREDICATE_ALIASES.get(desired_pred)
    if aliases is None:
        return False
    return bool(aliases & matched)


# ---------------------------------------------------------------------------
# Scope detection from fact conditions / code guards
# ---------------------------------------------------------------------------


#: Code-guard substrings that indicate a training-mode branch.
_TRAINING_GUARD_TOKENS: tuple[str, ...] = (
    "self.training", "training=true", "training == true", "training_mode",
    "model.train()", ".train()", "backward", "optimizer.step",
    "loss.backward", "training_step", "in_training", "mode == 'train'",
    'mode == "train"', "phase == 'train'", 'phase == "train"',
)

#: Code-guard substrings that indicate an inference / eval branch.
_INFERENCE_GUARD_TOKENS: tuple[str, ...] = (
    "self.training=false", "training == false", "no_grad", "torch.no_grad",
    "model.eval()", ".eval()", "inference", "mode == 'eval'",
    'mode == "eval"', "phase == 'eval'", 'phase == "eval"',
    "not self.training",
)


def _fact_scope(conditions: list[str]) -> str:
    """Classify a fact's conditions as ``training`` / ``inference`` / ``any``.

    The classifier is conservative: if a fact's guards mention both
    training and inference tokens, it is treated as ``any`` (ambiguous)
    so the alignment layer refuses to use it for either strict scope.
    """

    text = " ".join(str(c or "").lower() for c in conditions)
    if not text:
        return "any"
    has_training = any(token in text for token in _TRAINING_GUARD_TOKENS)
    has_inference = any(token in text for token in _INFERENCE_GUARD_TOKENS)
    if has_training and has_inference:
        return "any"
    if has_training:
        return "training"
    if has_inference:
        return "inference"
    return "any"


def _target_scope(target: TypedBehaviorTargetV1) -> str:
    """Extract the scope recorded in a target's conditions."""

    for cond in target.conditions:
        if cond in {"training", "inference"}:
            return cond
    return "any"


def _scope_compatible(target_scope: str, fact_scope: str) -> bool:
    """Return True when a fact of ``fact_scope`` may cover a target of ``target_scope``.

    Rules:

    - ``any`` target may be covered by any fact;
    - ``training`` target may only be covered by ``training`` facts;
    - ``inference`` target may be covered by ``inference`` or ``any`` facts
      (an unconditional fact is assumed to run on the inference path
      unless it is explicitly training-gated);
    - a ``training`` fact can never cover an ``inference`` target and
      vice-versa.
    """

    if target_scope == "any":
        return True
    if target_scope == "training":
        return fact_scope == "training"
    if target_scope == "inference":
        return fact_scope in {"inference", "any"}
    return False


# ---------------------------------------------------------------------------
# Alignment result models
# ---------------------------------------------------------------------------


class TargetAlignmentV1(BaseModel):
    """Alignment result for a single typed behavior target."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str
    target_scope: str = "any"
    desired_predicates: tuple[str, ...] = Field(default_factory=tuple)
    matched_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    matched_predicates: tuple[str, ...] = Field(default_factory=tuple)
    unmatched_predicates: tuple[str, ...] = Field(default_factory=tuple)
    required_relations: tuple[str, ...] = Field(default_factory=tuple)
    matched_relations: tuple[str, ...] = Field(default_factory=tuple)
    unmatched_relations: tuple[str, ...] = Field(default_factory=tuple)
    required_semantic_fields: tuple[str, ...] = Field(default_factory=tuple)
    matched_semantic_fields: tuple[str, ...] = Field(default_factory=tuple)
    unmatched_semantic_fields: tuple[str, ...] = Field(default_factory=tuple)
    scope_blocked_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    status: str = "unresolved"  # resolved | partial | unresolved | scope_blocked

    @property
    def is_resolved(self) -> bool:
        return self.status == "resolved"


class ObligationAlignmentV1(BaseModel):
    """Alignment result for a single obligation (across all its targets)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    obligation_kind: str
    obligation_priority: str
    target_alignments: tuple[TargetAlignmentV1, ...] = Field(default_factory=tuple)
    matched_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    matched_gap_ids: tuple[str, ...] = Field(default_factory=tuple)
    coverage_status: str = "unresolved"
    rationale: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.coverage_status in {
            "supported", "partial", "explicit_gap", "blocked",
        }


class ObligationCoverageReportV2(BaseModel):
    """Aggregate coverage report produced from a V2 intent graph + fact set.

    Replaces the V1 ``AuthoringObligationCoverageReport`` for the V3
    research plane.  Coverage is computed purely from typed behavior
    targets and authorized facts / claims / gaps: no English token
    overlap, no project-specific claim ids.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.0"
    mode: str = "obligation-coverage-v2"
    intent_graph_digest: str
    fact_set_digest: str = ""
    claim_set_digest: str = ""
    items: list[ObligationAlignmentV1] = Field(default_factory=list)
    must_cover_count: int = 0
    terminal_must_cover_count: int = 0
    supported_must_cover_count: int = 0
    unresolved_must_cover_ids: list[str] = Field(default_factory=list)
    explicit_gap_count: int = 0
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "ObligationCoverageReportV2":
        payload = {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "intent_graph_digest": self.intent_graph_digest,
            "fact_set_digest": self.fact_set_digest,
            "claim_set_digest": self.claim_set_digest,
            "items": [item.model_dump(mode="json") for item in self.items],
        }
        digest = _digest_payload(payload)
        object.__setattr__(self, "content_digest", digest)
        return self


# ---------------------------------------------------------------------------
# Core alignment: target -> facts
# ---------------------------------------------------------------------------


def align_target_to_facts(
    target: TypedBehaviorTargetV1,
    facts: list[CodeFactV1],
    *,
    only_supported: bool = True,
    behavior_relations: list[BehaviorRelationV1] | None = None,
    semantic_context: tuple[str, ...] = (),
) -> TargetAlignmentV1:
    """Align a single typed target against a fact list.

    Parameters
    ----------
    target
        The typed behavior target whose ``desired_predicates`` drive the
        match.
    facts
        The candidate facts.  Only facts whose ``predicate`` maps back to
        a behavior predicate in ``target.desired_predicates`` are
        considered.
    only_supported
        When True (default), only facts with ``validation_status ==
        "supported"`` may cover the target.  Rejected facts are ignored
        so an unsupported predicate never silently covers an obligation.
    """

    target_scope = _target_scope(target)
    desired = set(target.desired_predicates)
    desired_expanded = _expand_desired_with_aliases(desired)
    matched_fact_ids: list[str] = []
    matched_predicates: set[str] = set()
    scope_blocked_fact_ids: list[str] = []

    for fact in facts:
        if only_supported and fact.validation_status != "supported":
            continue
        behavior_pred = FACT_PREDICATE_TO_BEHAVIOR_FULL.get(fact.predicate)
        if behavior_pred is None or behavior_pred not in desired_expanded:
            continue
        fact_scope = _fact_scope(list(fact.conditions))
        if not _scope_compatible(target_scope, fact_scope):
            # The fact matches the predicate but its execution scope is
            # incompatible with the target's scope.  Record it as
            # scope-blocked so the caller can explain why a seemingly
            # matching fact did not cover the obligation.
            scope_blocked_fact_ids.append(fact.fact_id)
            continue
        matched_fact_ids.append(fact.fact_id)
        matched_predicates.add(behavior_pred)

    # Compute unmatched against the ORIGINAL desired set, considering
    # aliases: AGGREGATE is satisfied if CONCAT/STACK/REDUCE was matched,
    # CONSTRUCT is satisfied if CALL/LOAD was matched.
    unmatched_set = {
        pred
        for pred in desired
        if not _alias_satisfied(pred, matched_predicates)
    }
    unmatched = sorted(unmatched_set)
    required_relations = set(target.required_relations)
    available_relations = {
        relation.kind
        for relation in (behavior_relations or [])
        if relation.relation_id in {
            relation_id
            for fact in facts
            if fact.fact_id in matched_fact_ids
            for relation_id in fact.relation_evidence_ids
        }
    }
    # A final coverage replay has facts, not the live behavior graph.  The
    # generic compiler persists verified relation kinds on each fact so a
    # relation requirement cannot disappear at checkpoint/resume time.
    available_relations.update(
        relation_kind
        for fact in facts
        if fact.fact_id in matched_fact_ids
        for relation_kind in fact.relation_kinds
    )
    # Relation-derived facts retain the CONFIGURED_BY kind even when the
    # live behavior graph is unavailable to a downstream coverage report.
    if any(
        fact.fact_id in matched_fact_ids and fact.predicate == "configured_by"
        for fact in facts
    ):
        available_relations.add("CONFIGURED_BY")
    unmatched_relations = sorted(required_relations - available_relations)

    semantic_requirements = _target_semantic_requirements(target)
    fact_terms: set[str] = set()
    for fact in facts:
        if fact.fact_id not in matched_fact_ids:
            continue
        fact_terms.update(_semantic_terms(fact.object))
        fact_terms.update(_semantic_terms(fact.conditions))
        fact_terms.update(_semantic_terms(fact.subject))
        fact_terms.update(_semantic_terms(fact.scope))
        fact_terms.update(_semantic_terms(fact.semantic_context))
    fact_terms.update(_semantic_terms(semantic_context))
    matched_semantic_fields = sorted(
        field
        for field, required_terms in semantic_requirements.items()
        if required_terms <= fact_terms
    )
    unmatched_semantic_fields = sorted(
        set(semantic_requirements) - set(matched_semantic_fields)
    )
    matched_sorted = sorted(matched_predicates)
    if (
        matched_predicates
        and not unmatched
        and not unmatched_relations
        and not unmatched_semantic_fields
    ):
        status = "resolved"
    elif matched_predicates or available_relations:
        status = "partial"
    elif scope_blocked_fact_ids:
        status = "scope_blocked"
    else:
        status = "unresolved"

    return TargetAlignmentV1(
        target_id=target.target_id,
        target_scope=target_scope,
        desired_predicates=tuple(sorted(desired)),
        matched_fact_ids=tuple(matched_fact_ids),
        matched_predicates=tuple(matched_sorted),
        unmatched_predicates=tuple(unmatched),
        required_relations=tuple(sorted(required_relations)),
        matched_relations=tuple(sorted(required_relations & available_relations)),
        unmatched_relations=tuple(unmatched_relations),
        required_semantic_fields=tuple(sorted(semantic_requirements)),
        matched_semantic_fields=tuple(matched_semantic_fields),
        unmatched_semantic_fields=tuple(unmatched_semantic_fields),
        scope_blocked_fact_ids=tuple(scope_blocked_fact_ids),
        status=status,
    )


_GENERIC_ROLES = frozenset({
    "any", "control", "feature", "filter", "generation", "inference",
    "io", "predictor", "ranking", "task_head", "temporal", "training",
    "verification",
})
_SEMANTIC_STOP_WORDS = frozenset({
    "and", "before", "from", "into", "model", "result", "step", "the",
    "then", "this", "using", "with",
})
_SEMANTIC_FIELDS = (
    "inputs", "transformations", "decisions", "outputs",
)


def _target_semantic_requirements(
    target: TypedBehaviorTargetV1,
) -> dict[str, set[str]]:
    requirements: dict[str, set[str]] = {}
    role = target.role.strip().lower()
    if role and role not in _GENERIC_ROLES:
        role_terms = _semantic_terms(role)
        if role_terms:
            requirements["role"] = role_terms
    for field in _SEMANTIC_FIELDS:
        terms = _semantic_terms(getattr(target, field))
        if terms:
            requirements[field] = terms
    # Non-scope conditions (e.g. synchronous mode or rejection branch) are
    # semantic requirements; training/inference are handled by scope rules.
    condition_values = tuple(
        value for value in target.conditions
        if value not in {"training", "inference", "any"}
    )
    condition_terms = _semantic_terms(condition_values)
    if condition_terms:
        requirements["conditions"] = condition_terms
    return requirements


def _semantic_terms(value: Any) -> set[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value))
    raw = re.findall(r"[A-Za-z][A-Za-z0-9]+", text.replace("_", " ").lower())
    return {
        normalized
        for token in raw
        if len(token) >= 3 and token not in _SEMANTIC_STOP_WORDS
        if (normalized := _normalize_semantic_token(token))
    }


def _normalize_semantic_token(token: str) -> str:
    aliases = {
        "generation": "generate", "generated": "generate", "generates": "generate",
        "verification": "verify", "verifier": "verify", "verified": "verify",
        "candidate": "draft", "reference": "target",
    }
    if token in aliases:
        return aliases[token]
    if token.endswith("ing") and len(token) > 6:
        return token[:-3]
    if token.endswith("ed") and len(token) > 5:
        return token[:-2]
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


# ---------------------------------------------------------------------------
# Core alignment: obligation -> facts + claims + gaps
# ---------------------------------------------------------------------------


def align_obligation(
    obligation: IntentObligationV2,
    *,
    facts: list[CodeFactV1],
    claims: list[AtomicClaimV3] | None = None,
    gaps: list[ExplicitCodeGapV1] | None = None,
    gap_obligation_bindings: dict[str, list[str]] | None = None,
) -> ObligationAlignmentV1:
    """Align a single obligation against facts, claims and explicit gaps.

    Coverage resolution rules (R5.3):

    - ``verify_only`` obligations (rationale / innovation / mismatch)
      terminate as ``explicit_gap`` when a gap is recorded against them,
      otherwise ``unresolved``.  They NEVER become ``supported`` even if
      a matching fact exists, because their typed targets describe
      author expectations the code may legitimately not satisfy.
    - ``must_cover`` / ``should_cover`` obligations are ``supported``
      when every typed target is resolved, ``partial`` when at least one
      target is resolved or partial, and ``unresolved`` otherwise.
    - An explicit gap recorded against any obligation forces a terminal
      ``explicit_gap`` status (the search was exhausted).

    Gap binding
    ------------

    ``ExplicitCodeGapV1`` has no ``covered_obligation_ids`` field by design
    (the R4 contract is schema-stable).  Callers bind gaps to obligations
    in one of two ways:

    1. ``gap_obligation_bindings``: a ``{gap_id: [obligation_id, ...]}``
       mapping.  When provided, only explicit bindings are used and no
       English text matching is performed.  This is the deterministic
       path used by the V3 research loop.
    2. When ``gap_obligation_bindings`` is ``None``, the helper falls back
       to predicate-based matching: a gap covers an obligation when the
       predicates derived from the gap's ``topic`` text (via the V2
       concept registry) intersect the obligation's
       ``typed_behavior_targets.desired_predicates`` AND the gap's scope
       is compatible.  This path is still multilingual and paraphrase-
       invariant because it reuses the same concept registry as the
       intent compiler.
    """

    claims = claims or []
    gaps = gaps or []
    gap_obligation_bindings = gap_obligation_bindings or {}

    target_alignments: list[TargetAlignmentV1] = []
    for target in obligation.typed_behavior_targets:
        target_alignments.append(align_target_to_facts(target, facts))

    # Claims that cover this obligation (claims carry covers_obligation_ids).
    matched_claim_ids = [
        claim.claim_id
        for claim in claims
        if obligation.obligation_id in claim.covers_obligation_ids
    ]

    # Gaps recorded against this obligation.  An explicit gap is terminal
    # regardless of fact alignment: it means the research loop searched
    # exhaustively and the behavior is absent from the executable scope.
    matched_gap_ids: list[str] = []
    for gap in gaps:
        bound_obligation_ids = gap_obligation_bindings.get(gap.gap_id)
        if bound_obligation_ids is not None:
            if obligation.obligation_id in bound_obligation_ids:
                matched_gap_ids.append(gap.gap_id)
            continue
        # Profile/compiler gaps sourced from semantic hints are global caveat
        # candidates, not proof that every predicate-compatible obligation is
        # absent.  They require an explicit binding from the research loop.
        # Only author-obligation gaps may use the conservative typed fallback.
        if gap.source_kind != "author_obligation":
            continue
        # Fallback: predicate-based matching using the V2 concept registry.
        if _gap_matches_obligation(gap, obligation):
            matched_gap_ids.append(gap.gap_id)

    coverage_status, rationale = _resolve_coverage(
        obligation=obligation,
        target_alignments=target_alignments,
        matched_claim_ids=matched_claim_ids,
        matched_gap_ids=matched_gap_ids,
    )

    return ObligationAlignmentV1(
        obligation_id=obligation.obligation_id,
        obligation_kind=obligation.kind,
        obligation_priority=obligation.priority,
        target_alignments=tuple(target_alignments),
        matched_claim_ids=tuple(matched_claim_ids),
        matched_gap_ids=tuple(matched_gap_ids),
        coverage_status=coverage_status,
        rationale=rationale,
    )


def _gap_matches_obligation(
    gap: ExplicitCodeGapV1,
    obligation: IntentObligationV2,
) -> bool:
    """Fallback gap matcher: derive predicates from gap text and intersect.

    This path is only used when the caller does not supply explicit
    ``gap_obligation_bindings``.  It reuses the V2 concept registry so the
    match is multilingual and paraphrase-invariant.  A gap matches when:

    - the gap's derived predicates intersect the obligation's desired
      predicates; AND
    - the gap's scope (training / inference / any) is compatible with the
      obligation's target scope.
    """

    # Lazy import to avoid a circular dependency at module load time.
    from code2paper.agentic.intent_compiler_v2 import _match_concepts

    text = f"{gap.topic} {gap.rationale}"
    gap_concepts = list(_match_concepts(text))
    if not gap_concepts:
        # No behavior concept in the gap text: refuse to bind it to any
        # obligation.  The caller must use explicit bindings for free-form
        # gap topics that do not mention any behavior concept.
        return False
    gap_predicates: set[str] = set()
    gap_scopes: set[str] = set()
    for concept in gap_concepts:
        gap_predicates.update(concept.predicates)
        gap_scopes.add(concept.scope)
    if len(gap_scopes) == 1:
        gap_scope = next(iter(gap_scopes))
    else:
        gap_scope = "any"

    obligation_predicates: set[str] = set()
    obligation_scopes: set[str] = set()
    for target in obligation.typed_behavior_targets:
        obligation_predicates.update(target.desired_predicates)
        obligation_scopes.add(_target_scope(target))
    if not obligation_predicates:
        return False
    if not (gap_predicates & obligation_predicates):
        return False
    if gap_scope == "any":
        return True
    if obligation_scopes == {gap_scope}:
        return True
    return False


def _resolve_coverage(
    *,
    obligation: IntentObligationV2,
    target_alignments: list[TargetAlignmentV1],
    matched_claim_ids: list[str],
    matched_gap_ids: list[str],
) -> tuple[str, str]:
    """Apply the R5.3 coverage resolution rules."""

    # 1) Explicit gap is always terminal.
    if matched_gap_ids:
        return (
            "explicit_gap",
            "Search was exhausted and the requested behavior is absent "
            "from the executable scope; the obligation terminates as an "
            "explicit code gap.",
        )

    # 2) verify_only obligations never become supported.
    if obligation.priority == "verify_only":
        if not obligation.typed_behavior_targets:
            return (
                "unresolved",
                "Verify-only obligation has no typed behavior targets; "
                "it remains a diagnostic item and never enters the Method正文.",
            )
        any_partial = any(t.status in {"resolved", "partial"} for t in target_alignments)
        if any_partial:
            return (
                "partial",
                "Verify-only obligation has related executable facts but "
                "remains diagnostic; it does not become a positive Method claim.",
            )
        return (
            "unresolved",
            "Verify-only obligation has no executable evidence; it remains "
            "diagnostic and may terminate as an explicit gap after search.",
        )

    # 3) must_cover / should_cover / preference obligations.
    if not target_alignments:
        return (
            "unresolved",
            "Obligation has no typed behavior targets to align against facts.",
        )
    all_resolved = all(t.status == "resolved" for t in target_alignments)
    any_resolved_or_partial = any(
        t.status in {"resolved", "partial"} for t in target_alignments
    )
    if all_resolved:
        return (
            "supported",
            "Every typed behavior target is covered by supported code facts.",
        )
    if any_resolved_or_partial:
        return (
            "partial",
            "At least one typed behavior target is partially or fully covered; "
            "remaining targets need additional evidence or an explicit gap.",
        )
    scope_blocked = any(t.status == "scope_blocked" for t in target_alignments)
    if scope_blocked:
        return (
            "unresolved",
            "Matching facts exist but their execution scope is incompatible "
            "(e.g. training facts cannot cover an inference obligation).",
        )
    return (
        "unresolved",
        "No supported code fact covers any typed behavior target.",
    )


# ---------------------------------------------------------------------------
# Aggregate coverage report
# ---------------------------------------------------------------------------


def build_obligation_coverage_v2(
    graph: IntentObligationGraphV2,
    *,
    fact_set: CodeFactSetV1 | None = None,
    claim_set: AtomicClaimSetV3 | None = None,
    explicit_gaps: list[ExplicitCodeGapV1] | None = None,
    gap_obligation_bindings: dict[str, list[str]] | None = None,
) -> ObligationCoverageReportV2:
    """Build the V2 coverage report from a typed intent graph + facts.

    This is the generic replacement for ``build_authoring_obligation_coverage``
    in ``intent_obligations.py``.  It uses no English token overlap and no
    project-specific claim ids: coverage is decided entirely by typed
    behavior target alignment.

    ``gap_obligation_bindings`` (``{gap_id: [obligation_id, ...]}``) is the
    deterministic binding path.  When it is ``None`` the alignment layer
    falls back to predicate-based matching against the gap's ``topic`` text
    via the V2 concept registry.
    """

    facts = list(fact_set.facts) if fact_set is not None else []
    claims = list(claim_set.claims) if claim_set is not None else []
    gaps = list(explicit_gaps or [])
    bindings = dict(gap_obligation_bindings or {})

    items: list[ObligationAlignmentV1] = []
    for obligation in graph.obligations:
        items.append(align_obligation(
            obligation,
            facts=facts,
            claims=claims,
            gaps=gaps,
            gap_obligation_bindings=bindings,
        ))

    must_cover_items = [item for item in items if item.obligation_priority == "must_cover"]
    terminal_must = [
        item for item in must_cover_items
        if item.coverage_status in {"supported", "partial", "explicit_gap", "blocked"}
    ]
    supported_must = [
        item for item in must_cover_items if item.coverage_status == "supported"
    ]
    unresolved_must = [
        item.obligation_id
        for item in must_cover_items
        if item.coverage_status not in {"supported", "partial", "explicit_gap", "blocked"}
    ]
    gap_count = sum(1 for item in items if item.coverage_status == "explicit_gap")

    return ObligationCoverageReportV2(
        intent_graph_digest=graph.content_digest,
        fact_set_digest=fact_set.content_digest if fact_set is not None else "",
        claim_set_digest=claim_set.content_digest if claim_set is not None else "",
        items=items,
        must_cover_count=len(must_cover_items),
        terminal_must_cover_count=len(terminal_must),
        supported_must_cover_count=len(supported_must),
        unresolved_must_cover_ids=unresolved_must,
        explicit_gap_count=gap_count,
    )


def bind_claims_to_obligations(
    graph: IntentObligationGraphV2,
    *,
    fact_set: CodeFactSetV1,
    claim_set: AtomicClaimSetV3,
) -> AtomicClaimSetV3:
    """Bind authorized claims to typed obligations through their fact IDs.

    Profile compilers intentionally know only executable structure, not author
    wording. This bridge therefore derives ``covers_obligation_ids`` from the
    same typed target-to-fact alignment used by the coverage gate. A claim is
    bound only when at least one of its supporting facts occurs in an
    obligation's resolved/partial target alignment.  The remaining claim facts
    stay independently authorized by the fact/claim compiler; this allows a
    claim to include closely coupled implementation detail (for example a load
    paired with construction) that the author target did not enumerate.
    """

    fact_ids_by_obligation: dict[str, set[str]] = {}
    for obligation in graph.obligations:
        matched: set[str] = set()
        for target in obligation.typed_behavior_targets:
            alignment = align_target_to_facts(target, fact_set.facts)
            matched.update(alignment.matched_fact_ids)
        fact_ids_by_obligation[obligation.obligation_id] = matched

    rebound: list[AtomicClaimV3] = []
    for claim in claim_set.claims:
        claim_facts = set(claim.fact_ids)
        derived = [
            obligation.obligation_id
            for obligation in graph.obligations
            if claim_facts.intersection(
                fact_ids_by_obligation.get(obligation.obligation_id, set())
            )
        ]
        covers = list(dict.fromkeys([*claim.covers_obligation_ids, *derived]))
        rebound.append(claim.model_copy(update={"covers_obligation_ids": covers}))

    payload = {
        "claims": [claim.model_dump(mode="json") for claim in rebound],
        "explicit_code_gaps": [
            gap.model_dump(mode="json") for gap in claim_set.explicit_code_gaps
        ],
        "semantic_stage_groups": [
            group.model_dump(mode="json")
            for group in claim_set.semantic_stage_groups
        ],
    }
    return claim_set.model_copy(
        update={
            "claims": rebound,
            "content_digest": _digest_payload(payload),
        }
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _digest_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "EXTRA_FACT_PREDICATE_ALIASES",
    "FACT_PREDICATE_TO_BEHAVIOR",
    "FACT_PREDICATE_TO_BEHAVIOR_FULL",
    "ObligationAlignmentV1",
    "ObligationCoverageReportV2",
    "TargetAlignmentV1",
    "align_obligation",
    "align_target_to_facts",
    "bind_claims_to_obligations",
    "build_obligation_coverage_v2",
]
