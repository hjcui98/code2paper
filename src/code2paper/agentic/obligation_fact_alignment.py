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
    SemanticStageGroupV1,
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
    # CONSTRUCT is an intent-level operation, not just an object constructor.
    # A learned representation or descriptor is commonly constructed by
    # concatenating/stacking/computing tensors.  Restricting this alias to
    # CALL/LOAD made a helper that merely enumerated attribute names outrank
    # the executable tensor assembly that the author actually wanted to
    # describe.
    "CONSTRUCT": frozenset({"CALL", "LOAD", "CONCAT", "STACK", "COMPUTE", "PROJECT"}),
    # The intent vocabulary uses READ/TRANSFORM as semantic umbrellas while
    # the AST adapter records the concrete operation performed.
    "READ": frozenset({"LOAD"}),
    "TRANSFORM": frozenset({"COMPUTE", "CONCAT", "NORMALIZE", "PROJECT", "RESHAPE"}),
    # A learned projection is a concrete implementation of an abstract
    # score/representation computation.
    "COMPUTE": frozenset({"PROJECT"}),
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
    - ``training`` target may be covered by ``training`` or ``any`` facts
      (an unconditional fact is assumed to run in both training and
      inference unless explicitly gated);
    - ``inference`` target may be covered by ``inference`` or ``any`` facts;
    - a ``training`` fact can never cover an ``inference`` target and
      vice-versa.
    """

    if target_scope == "any":
        return True
    if target_scope == "training":
        return fact_scope in {"training", "any"}
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
    predicate_groups: tuple[tuple[str, ...], ...] = Field(default_factory=tuple)
    matched_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    matched_predicates: tuple[str, ...] = Field(default_factory=tuple)
    unmatched_predicates: tuple[str, ...] = Field(default_factory=tuple)
    required_relations: tuple[str, ...] = Field(default_factory=tuple)
    matched_relations: tuple[str, ...] = Field(default_factory=tuple)
    unmatched_relations: tuple[str, ...] = Field(default_factory=tuple)
    required_semantic_fields: tuple[str, ...] = Field(default_factory=tuple)
    matched_semantic_fields: tuple[str, ...] = Field(default_factory=tuple)
    unmatched_semantic_fields: tuple[str, ...] = Field(default_factory=tuple)
    matched_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    unmatched_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
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
    required_relations = set(target.required_relations)
    matched_fact_ids: list[str] = []
    matched_predicates: set[str] = set()
    scope_blocked_fact_ids: list[str] = []

    for fact in facts:
        if only_supported and fact.validation_status != "supported":
            continue
        behavior_pred = FACT_PREDICATE_TO_BEHAVIOR_FULL.get(fact.predicate)
        relation_witness = bool(
            required_relations
            and (
                behavior_pred in required_relations
                or required_relations.intersection(fact.relation_kinds)
            )
        )
        if behavior_pred is None or (
            behavior_pred not in desired_expanded and not relation_witness
        ):
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
    if target.predicate_groups:
        unmatched_set = {
            group[0]
            for group in target.predicate_groups
            if group and not any(
                _alias_satisfied(predicate, matched_predicates)
                for predicate in group
            )
        }
    else:
        unmatched_set = {
            pred
            for pred in desired
            if not _alias_satisfied(pred, matched_predicates)
        }
    unmatched = sorted(unmatched_set)
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
    semantic_witnesses: list[set[str]] = []
    for fact in facts:
        if fact.fact_id not in matched_fact_ids:
            continue
        witness_terms: set[str] = set()
        witness_terms.update(_semantic_terms(fact.object))
        witness_terms.update(_semantic_terms(fact.conditions))
        witness_terms.update(_semantic_terms(fact.subject))
        witness_terms.update(_semantic_terms(fact.scope))
        witness_terms.update(_semantic_terms(fact.semantic_context))
        semantic_witnesses.append(witness_terms)
    # Candidate-time source descriptors may supplement persisted facts, but
    # each descriptor must independently contain the complete semantic field.
    # Unioning unrelated nodes lets ``dim=1`` from one operation and literal
    # ``15`` from another falsely authorize "dimension 15".
    semantic_witnesses.extend(
        _semantic_terms(value) for value in semantic_context if value
    )
    matched_semantic_fields = sorted(
        field
        for field, required_terms in semantic_requirements.items()
        if any(required_terms <= witness for witness in semantic_witnesses)
    )
    unmatched_semantic_fields = sorted(
        set(semantic_requirements) - set(matched_semantic_fields)
    )
    matched_slot_ids: list[str] = []
    unmatched_slot_ids: list[str] = []
    for slot in getattr(target, "semantic_slots", ()) or ():
        slot_id = str(getattr(slot, "slot_id", "") or "").strip()
        if not slot_id or not bool(getattr(slot, "required", True)):
            continue
        slot_terms = set(
            term
            for value in (getattr(slot, "terms", ()) or ())
            for term in _semantic_terms(value)
        )
        slot_kind = str(getattr(slot, "slot_kind", "") or "")
        slot_matched = (
            any(
                slot_terms <= witness
                for witness in semantic_witnesses
            )
            if slot_terms
            else slot_kind in matched_semantic_fields
        )
        if slot_kind == "relation":
            slot_matched = slot_matched and not unmatched_relations
        if slot_matched:
            matched_slot_ids.append(slot_id)
        else:
            unmatched_slot_ids.append(slot_id)
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
        predicate_groups=target.predicate_groups,
        matched_fact_ids=tuple(matched_fact_ids),
        matched_predicates=tuple(matched_sorted),
        unmatched_predicates=tuple(unmatched),
        required_relations=tuple(sorted(required_relations)),
        matched_relations=tuple(sorted(required_relations & available_relations)),
        unmatched_relations=tuple(unmatched_relations),
        required_semantic_fields=tuple(sorted(semantic_requirements)),
        matched_semantic_fields=tuple(matched_semantic_fields),
        unmatched_semantic_fields=tuple(unmatched_semantic_fields),
        matched_slot_ids=tuple(matched_slot_ids),
        unmatched_slot_ids=tuple(unmatched_slot_ids),
        scope_blocked_fact_ids=tuple(scope_blocked_fact_ids),
        status=status,
    )


_GENERIC_ROLES = frozenset({
    "any", "attention", "composition", "config", "control", "feature",
    "filter", "generation", "graph_builder", "inference", "io", "predictor", "propagation",
    "ranking", "task_head", "temporal", "training", "verification",
})
_SEMANTIC_STOP_WORDS = frozenset({
    "and", "before", "from", "into", "model", "result", "step", "the",
    "then", "this", "using", "with",
})
_SEMANTIC_FIELDS = (
    "inputs", "transformations", "decisions", "outputs",
)


def _decompose_role_into_generic_parts(role: str) -> tuple[str, ...] | None:
    """Decompose a role string into generic role parts by longest match.

    Role hints emitted by the intent compiler may join multiple generic
    roles with underscores (e.g. ``feature_attention_task_head``), while
    ``_GENERIC_ROLES`` stores multi-word entries with underscores (e.g.
    ``task_head``).  Splitting only on ``+`` leaves the joined string
    intact, so the whole token is never found in ``_GENERIC_ROLES`` and a
    non-generic role requirement is added even though every constituent
    is generic.  That spurious ``role`` requirement then fails to match
    against fact witnesses (which carry code identifiers, not role
    labels), downgrading the alignment to ``partial`` and ultimately
    terminating the obligation as an explicit gap.

    This helper tries ``+`` first (the canonical separator) and then
    falls back to a longest-match scan against ``_GENERIC_ROLES`` so that
    ``feature_attention_task_head`` decomposes into
    ``("feature", "attention", "task_head")`` while a genuinely
    descriptive role such as ``query_activation_engine`` returns ``None``.
    """

    if not role:
        return ()
    parts = tuple(part for part in role.split("+") if part)
    if parts and all(part in _GENERIC_ROLES for part in parts):
        return parts
    sorted_roles = sorted(_GENERIC_ROLES, key=len, reverse=True)
    remaining = role
    decomposed: list[str] = []
    while remaining:
        remaining = remaining.lstrip("_")
        if not remaining:
            break
        matched = next(
            (entry for entry in sorted_roles if remaining.startswith(entry)),
            None,
        )
        if matched is None:
            return None
        decomposed.append(matched)
        remaining = remaining[len(matched):]
    return tuple(decomposed) if decomposed else None


def _target_semantic_requirements(
    target: TypedBehaviorTargetV1,
) -> dict[str, set[str]]:
    requirements: dict[str, set[str]] = {}
    role = target.role.strip().lower()
    is_generic_role = _decompose_role_into_generic_parts(role) is not None
    if role and not is_generic_role:
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
    original = str(value).replace("top-k", "topk").replace("top_k", "topk")
    compact_identifiers = {
        token.lower()
        for token in re.findall(
            r"\b[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+\b", original
        )
        if len(token) >= 3
    }
    text = original
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    raw = re.findall(r"[A-Za-z][A-Za-z0-9]+|\d+", text.replace("_", " ").lower())
    terms = compact_identifiers | {
        normalized
        for token in raw
        if (len(token) >= 3 or token.isdigit()) and token not in _SEMANTIC_STOP_WORDS
        if (normalized := _normalize_semantic_token(token))
    }
    # Executable identifiers frequently encode a feature width as ``f15`` or
    # ``dim128``. Unlike retrieval ranking, semantic replay only sees these
    # after an exact source span has been read and compiled. Preserve the
    # explicit numeric width so a fact from ``get_*_f15`` can witness the
    # author's "15-dimensional" constraint without a project dictionary.
    for match in re.finditer(r"(?:^|[_\W])(?:f|d|dim)(\d+)(?:$|[_\W])", original, re.IGNORECASE):
        terms.update({"dimension", match.group(1)})
    return terms


def _normalize_semantic_token(token: str) -> str:
    aliases = {
        "generation": "generate", "generated": "generate", "generates": "generate",
        "infer": "generate", "inference": "generate",
        "propagate": "propagate", "propagates": "propagate",
        "propagating": "propagate", "propagation": "propagate",
        "filter": "filter", "filtering": "filter", "prune": "filter",
        "pruned": "filter", "prunes": "filter", "pruning": "filter",
        "threshold": "filter",
        "score": "predict", "scores": "predict", "scoring": "predict",
        "predict": "predict", "predicts": "predict", "prediction": "predict",
        "predictor": "predict",
        "infonce": "contrastive_objective", "contrastive": "contrastive_objective",
        "logsumexp": "contrastive_objective",
        "verification": "verify", "verifier": "verify", "verified": "verify",
        "candidate": "draft", "reference": "target",
        "dim": "dimension", "dims": "dimension", "dimensional": "dimension",
        "mamba": "state_space", "ssm": "state_space",
        "ppr": "pagerank", "pagerank": "pagerank",
        "topk": "topk",
        "cat": "concat", "concat": "concat",
        "concatenate": "concat", "concatenates": "concat",
        "concatenated": "concat", "concatenating": "concat",
        "concatenation": "concat",
        "normalize": "normalize", "normalizes": "normalize",
        "normalized": "normalize", "normalizing": "normalize",
        "normalization": "normalize",
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
        if obligation.priority in {"must_cover", "should_cover"} and not matched_claim_ids:
            return (
                "partial",
                "Every typed target has a matching fact, but no authorized atomic "
                "claim is bound to this authoring obligation.",
            )
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
    obligation_by_id = {
        obligation.obligation_id: obligation for obligation in graph.obligations
    }
    for obligation in graph.obligations:
        matched: set[str] = set()
        for target in obligation.typed_behavior_targets:
            alignment = align_target_to_facts(target, fact_set.facts)
            matched.update(alignment.matched_fact_ids)
        fact_ids_by_obligation[obligation.obligation_id] = matched

    rebound: list[AtomicClaimV3] = []
    explicit_claim_ids_by_obligation: dict[str, set[str]] = {
        obligation.obligation_id: {
            claim.claim_id
            for claim in claim_set.claims
            if obligation.obligation_id in claim.covers_obligation_ids
        }
        for obligation in graph.obligations
    }
    for claim in claim_set.claims:
        claim_facts = set(claim.fact_ids)
        derived = [
            obligation.obligation_id
            for obligation in graph.obligations
            if claim_facts.intersection(
                fact_ids_by_obligation.get(obligation.obligation_id, set())
            )
        ]
        # Claims compiled inside the research loop already carry the exact
        # obligation that owned the evidence packet.  Treat that producer
        # binding as authoritative and do not broaden it merely because a
        # common predicate (CALL/LOAD/COMPUTE) also appears in unrelated
        # obligations.  The derived bridge exists only for legacy/profile
        # claims that predate explicit obligation ownership.
        explicit = [
            obligation_id
            for obligation_id in claim.covers_obligation_ids
            if obligation_id in fact_ids_by_obligation
        ]
        # The method-mainline obligation is an umbrella over the authored
        # pipeline.  When it was repaired only after aggregate evidence was
        # merged, it has no producer-owned claims of its own; inherit only
        # claims whose exact supporting facts align to its typed targets.
        # Other stage/component obligations retain strict producer ownership
        # so common CALL/COMPUTE facts cannot silently broaden authorship.
        inherited_mainlines = [
            obligation_id
            for obligation_id in derived
            if obligation_by_id[obligation_id].kind == "method_mainline"
            and not explicit_claim_ids_by_obligation[obligation_id]
            and any(
                obligation_by_id.get(owner_id) is not None
                and obligation_by_id[owner_id].priority in {"must_cover", "should_cover"}
                for owner_id in claim.covers_obligation_ids
            )
        ]
        covers = list(dict.fromkeys([*(explicit or derived), *inherited_mainlines]))
        rebound.append(claim.model_copy(update={"covers_obligation_ids": covers}))

    intent_stage_groups = _intent_stage_groups(
        graph=graph,
        facts=fact_set.facts,
        claims=rebound,
    )
    stage_groups = intent_stage_groups or claim_set.semantic_stage_groups
    payload = {
        "claims": [claim.model_dump(mode="json") for claim in rebound],
        "explicit_code_gaps": [
            gap.model_dump(mode="json") for gap in claim_set.explicit_code_gaps
        ],
        "semantic_stage_groups": [
            group.model_dump(mode="json")
            for group in stage_groups
        ],
    }
    return claim_set.model_copy(
        update={
            "claims": rebound,
            "semantic_stage_groups": stage_groups,
            "content_digest": _digest_payload(payload),
        }
    )


def _intent_stage_groups(
    *,
    graph: IntentObligationGraphV2,
    facts: list[CodeFactV1],
    claims: list[AtomicClaimV3],
) -> list[SemanticStageGroupV1]:
    """Organize positive executable claims by author-authored pipeline stage."""

    stages = sorted(
        (item for item in graph.obligations if item.kind == "stage"),
        key=lambda item: (item.source_index, item.obligation_id),
    )
    if not stages:
        return []
    obligation_by_id = {item.obligation_id: item for item in graph.obligations}
    fact_by_id = {fact.fact_id: fact for fact in facts}
    claim_by_id = {claim.claim_id: claim for claim in claims}
    positive_claim_ids = {
        claim.claim_id
        for claim in claims
        if any(
            obligation_by_id.get(obligation_id) is not None
            and obligation_by_id[obligation_id].priority in {"must_cover", "should_cover"}
            for obligation_id in claim.covers_obligation_ids
        )
    }
    assigned: set[str] = set()
    # Pre-compute the set of all stage obligation IDs so the expansion
    # logic can avoid absorbing claims that explicitly belong to a later
    # stage.  Without this guard, a claim covering O-STAGE-03 whose fact
    # subject overlaps with O-STAGE-01's anchor subjects would be pulled
    # into SG-INTENT-01, leaving O-STAGE-03 empty and dropping a section
    # from the method plan.
    stage_obligation_ids = {stage.obligation_id for stage in stages}
    groups: list[SemanticStageGroupV1] = []
    for stage in stages:
        explicit_ids = [
            claim.claim_id
            for claim in claims
            if claim.claim_id in positive_claim_ids
            and stage.obligation_id in claim.covers_obligation_ids
            and claim.claim_id not in assigned
        ]
        anchor_subjects = {
            fact_by_id[fact_id].subject
            for claim_id in explicit_ids
            for fact_id in claim_by_id[claim_id].fact_ids
            if fact_id in fact_by_id
        }
        explicit_spans = {
            str(span_id)
            for claim_id in explicit_ids
            for span_id in claim_by_id[claim_id].direct_evidence_ids
            if str(span_id)
        }
        typed_predicates = {
            str(predicate)
            for target in getattr(stage, "typed_behavior_targets", ()) or ()
            for predicate in getattr(target, "desired_predicates", ()) or ()
            if str(predicate)
        }
        expanded_ids = [
            claim.claim_id
            for claim in claims
            if claim.claim_id in positive_claim_ids
            and claim.claim_id not in assigned
            and claim.claim_id not in explicit_ids
            # Do not expand a claim that explicitly covers another stage
            # obligation into the current stage.  Such a claim has its
            # own authored home and will form (or join) its own group when
            # that stage is processed.  Only truly unstageed claims —
            # those whose covers_obligation_ids contain no stage at all —
            # are eligible for subject-based expansion.
            and not any(
                oid in stage_obligation_ids and oid != stage.obligation_id
                for oid in claim.covers_obligation_ids
            )
            and _claim_joins_stage_by_span(
                claim=claim,
                explicit_span_ids=explicit_spans,
                explicit_subjects=anchor_subjects,
                fact_by_id=fact_by_id,
                stage_text=stage.author_text,
                typed_predicates=typed_predicates,
            )
        ]
        ordered_ids = list(dict.fromkeys([*explicit_ids, *expanded_ids]))
        if not ordered_ids:
            continue
        assigned.update(ordered_ids)
        heading = stage.author_text.split(":", 1)[0].strip()
        if not heading or len(heading) > 120:
            heading = f"Method stage {stage.source_index + 1}"
        groups.append(SemanticStageGroupV1(
            stage_id=f"SG-INTENT-{stage.source_index + 1:02d}-{stage.obligation_id.rsplit('-', 1)[-1]}",
            name=heading,
            purpose=stage.author_text,
            ordered_claim_ids=ordered_ids,
            covers_obligation_ids=[stage.obligation_id],
            relation_evidence_ids=list(dict.fromkeys(
                relation_id
                for claim_id in ordered_ids
                for relation_id in claim_by_id[claim_id].relation_evidence_ids
            )),
            organization_priority=stage.source_index + 1,
        ))

    remaining = [
        claim_id for claim_id in positive_claim_ids
        if claim_id not in assigned
    ]
    if remaining:
        remaining.sort()
        _fold_unassigned_claims_into_nearest_stage(
            remaining=remaining,
            groups=groups,
            stages=stages,
            claim_by_id=claim_by_id,
            obligation_by_id=obligation_by_id,
        )
    return groups


_STAGE_FOLD_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "and", "as", "by", "for", "from", "in", "into", "of",
    "on", "or", "the", "to", "via", "with", "method", "framework",
    "module", "mechanism", "system", "approach", "design", "process",
})
_LOCAL_STAGE_RE = re.compile(
    r"\b(activat|bridg|frontier|threshold|prune|exclude|first retriev)\b",
    re.I,
)
_GLOBAL_STAGE_RE = re.compile(
    r"\b(pagerank|ppr|hybrid|damping|global rank|passage retriev)\b",
    re.I,
)


def _stage_family(text: str) -> str:
    value = str(text or "")
    if _GLOBAL_STAGE_RE.search(value):
        return "global"
    if _LOCAL_STAGE_RE.search(value):
        return "local"
    return "other"


def _claim_joins_stage_by_span(
    *,
    claim: AtomicClaimV3,
    explicit_span_ids: set[str],
    explicit_subjects: set[str],
    fact_by_id: dict[str, CodeFactV1],
    stage_text: str,
    typed_predicates: set[str],
) -> bool:
    """A leftover fact may join a STAGE only via span/symbol identity."""

    claim_family = _stage_family(claim.canonical_text)
    stage_family = _stage_family(stage_text)
    if (
        stage_family in {"local", "global"}
        and claim_family in {"local", "global"}
        and claim_family != stage_family
    ):
        return False
    claim_spans = {str(item) for item in claim.direct_evidence_ids if str(item)}
    if explicit_span_ids and claim_spans & explicit_span_ids:
        return True
    claim_subjects = {
        fact_by_id[fact_id].subject
        for fact_id in claim.fact_ids
        if fact_id in fact_by_id
    }
    if typed_predicates:
        claim_predicates = {
            fact_by_id[fact_id].predicate
            for fact_id in claim.fact_ids
            if fact_id in fact_by_id
        }
        if not (claim_predicates & typed_predicates):
            return False
        return bool(explicit_subjects & claim_subjects) or bool(
            explicit_span_ids and claim_spans & explicit_span_ids
        )
    return bool(explicit_subjects & claim_subjects) and (
        stage_family == "other" or claim_family in {stage_family, "other"}
    )


def _stage_fold_tokens(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", str(value).lower())
        if len(token) > 2 and token not in _STAGE_FOLD_STOPWORDS
    }


def _fold_unassigned_claims_into_nearest_stage(
    *,
    remaining: list[str],
    groups: list[SemanticStageGroupV1],
    stages: list[Any],
    claim_by_id: dict[str, AtomicClaimV3],
    obligation_by_id: dict[str, Any],
) -> None:
    """Place leftover executable claims in the nearest author stage.

    Representation/routing only: claims stay exactly as compiled.  This
    avoids a standalone verified-dump heading that displaces the author's
    pipeline story.
    """

    if not remaining or not stages:
        return
    if not groups:
        assigned_by_stage: dict[str, list[str]] = {
            stage.obligation_id: [] for stage in stages
        }
        for claim_id in remaining:
            stage = _nearest_pipeline_stage(
                claim=claim_by_id[claim_id],
                stages=stages,
                obligation_by_id=obligation_by_id,
            )
            assigned_by_stage[stage.obligation_id].append(claim_id)
        for stage in stages:
            ordered_ids = assigned_by_stage[stage.obligation_id]
            if not ordered_ids:
                continue
            heading = stage.author_text.split(":", 1)[0].strip()
            if not heading or len(heading) > 120:
                heading = f"Method stage {stage.source_index + 1}"
            groups.append(SemanticStageGroupV1(
                stage_id=f"SG-INTENT-{stage.source_index + 1:02d}-{stage.obligation_id.rsplit('-', 1)[-1]}",
                name=heading,
                purpose=stage.author_text,
                ordered_claim_ids=ordered_ids,
                covers_obligation_ids=[stage.obligation_id],
                relation_evidence_ids=list(dict.fromkeys(
                    relation_id
                    for claim_id in ordered_ids
                    for relation_id in claim_by_id[claim_id].relation_evidence_ids
                )),
                organization_priority=stage.source_index + 1,
            ))
        return

    for claim_id in remaining:
        claim = claim_by_id[claim_id]
        claim_tokens = _stage_fold_tokens(claim.canonical_text)
        scores: list[float] = []
        for group in groups:
            group_text = f"{group.name} {group.purpose}"
            group_tokens = _stage_fold_tokens(group_text)
            if re.search(r"\b(motivation|overview|related.?work)\b", group_text, re.I):
                scores.append(-1.0)
                continue
            union = claim_tokens | group_tokens
            score = (len(claim_tokens & group_tokens) / len(union)) if union else 0.0
            claim_family = _stage_family(claim.canonical_text)
            group_family = _stage_family(group_text)
            if (
                claim_family in {"local", "global"}
                and group_family in {"local", "global"}
                and claim_family != group_family
            ):
                score = -1.0
            elif claim_family != "other" and claim_family == group_family:
                score += 0.5
            scores.append(score)
        best = max(scores) if scores else 0.0
        if scores and best >= 0.25:
            target = groups[scores.index(best)]
        else:
            target = _nearest_existing_stage_group(
                claim=claim,
                groups=groups,
                stages=stages,
                obligation_by_id=obligation_by_id,
            )
        target.ordered_claim_ids.append(claim_id)
        target.covers_obligation_ids = list(dict.fromkeys([
            *target.covers_obligation_ids,
            *(
                obligation_id
                for obligation_id in claim.covers_obligation_ids
                if obligation_by_id.get(obligation_id) is not None
                and obligation_by_id[obligation_id].priority in {"must_cover", "should_cover"}
            ),
        ]))
        target.relation_evidence_ids = list(dict.fromkeys([
            *target.relation_evidence_ids,
            *claim.relation_evidence_ids,
        ]))


def _nearest_pipeline_stage(
    *,
    claim: AtomicClaimV3,
    stages: list[Any],
    obligation_by_id: dict[str, Any],
) -> Any:
    claim_tokens = _stage_fold_tokens(claim.canonical_text)
    claim_family = _stage_family(claim.canonical_text)
    scored: list[tuple[float, Any]] = []
    for stage in stages:
        stage_family = _stage_family(stage.author_text)
        if (
            claim_family in {"local", "global"}
            and stage_family in {"local", "global"}
            and claim_family != stage_family
        ):
            scored.append((-1.0, stage))
            continue
        union = claim_tokens | _stage_fold_tokens(stage.author_text)
        score = (
            len(claim_tokens & _stage_fold_tokens(stage.author_text)) / len(union)
            if union else 0.0
        )
        if claim_family != "other" and claim_family == stage_family:
            score += 0.5
        scored.append((score, stage))
    best_score, best_stage = max(scored, key=lambda item: item[0])
    if best_score > 0:
        return best_stage
    compatible = [stage for score, stage in scored if score >= 0.0]
    if compatible:
        return compatible[-1]
    return stages[0]


def _ensure_stage_group(
    *,
    stage: Any,
    groups: list[SemanticStageGroupV1],
) -> SemanticStageGroupV1:
    for group in groups:
        if stage.obligation_id in group.covers_obligation_ids:
            return group
    heading = stage.author_text.split(":", 1)[0].strip()
    if not heading or len(heading) > 120:
        heading = f"Method stage {stage.source_index + 1}"
    group = SemanticStageGroupV1(
        stage_id=f"SG-INTENT-{stage.source_index + 1:02d}-{stage.obligation_id.rsplit('-', 1)[-1]}",
        name=heading,
        purpose=stage.author_text,
        ordered_claim_ids=[],
        covers_obligation_ids=[stage.obligation_id],
        organization_priority=stage.source_index + 1,
    )
    groups.append(group)
    return group


def _nearest_existing_stage_group(
    *,
    claim: AtomicClaimV3,
    groups: list[SemanticStageGroupV1],
    stages: list[Any],
    obligation_by_id: dict[str, Any],
) -> SemanticStageGroupV1:
    stage = _nearest_pipeline_stage(
        claim=claim,
        stages=stages,
        obligation_by_id=obligation_by_id,
    )
    return _ensure_stage_group(stage=stage, groups=groups)


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
