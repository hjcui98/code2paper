from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.method_product_models import (
    MethodEvidenceLane,
    MethodOutputPolicyV1,
    MethodReviewCandidateV1,
    build_default_method_output_policy,
    method_lane_from_reference_status,
)
from code2paper.agentic.semantic_evidence import concepts_semantically_related
from code2paper.agentic.trust_contracts import AuthoringInputProjection


ObligationKind = Literal[
    "method_mainline",
    "stage",
    "component",
    "organization",
    "rationale_check",
    "high_risk_claim",
    "mismatch_check",
]
ObligationPriority = Literal["must_cover", "should_cover", "preference", "verify_only"]
CoverageStatus = Literal[
    "candidate_covered",
    "partially_covered",
    "organization_available",
    "not_implemented_in_repo",
    "unresolved",
]


class IntentObligation(BaseModel):
    """One author-requested method question that code evidence must resolve.

    The author text is a retrieval and coverage input only.  It is deliberately
    not a writable claim and carries no support verdict.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    kind: ObligationKind
    priority: ObligationPriority
    source_field: str
    source_index: int = 0
    author_text: str
    retrieval_queries: list[str] = Field(default_factory=list)
    candidate_paths: list[str] = Field(default_factory=list)
    status: Literal["unresolved"] = "unresolved"


class IntentObligationRelation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_obligation_id: str
    target_obligation_id: str
    relation: Literal["precedes", "supports", "checks"]


class IntentObligationGraphV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: str = "intent-obligation-graph-v1"
    project_goal: str = ""
    method_goal: str = ""
    implementation_scope: str = ""
    obligations: list[IntentObligation] = Field(default_factory=list)
    relations: list[IntentObligationRelation] = Field(default_factory=list)
    content_digest: str = ""


class ObligationCoverageItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    kind: ObligationKind
    priority: ObligationPriority
    status: CoverageStatus
    projected_claim_ids: list[str] = Field(default_factory=list)
    matched_stage_ids: list[str] = Field(default_factory=list)
    lexical_coverage: float = 0.0
    rationale: str = ""


class AuthoringObligationCoverageReport(BaseModel):
    """Quality signal for the decision graph, never a scientific support gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: str = "authoring-obligation-coverage-v1"
    obligation_graph_digest: str
    projection_digest: str
    items: list[ObligationCoverageItem] = Field(default_factory=list)
    must_cover_count: int = 0
    candidate_covered_must_cover_count: int = 0
    unresolved_must_cover_ids: list[str] = Field(default_factory=list)
    projected_claim_count: int = 0
    unique_projected_claim_count: int = 0
    duplicate_projected_claim_ids: list[str] = Field(default_factory=list)
    average_direct_evidence_fan_in: float = 0.0
    max_direct_evidence_fan_in: int = 0
    recommended_next: Literal["authoring", "targeted_evidence_repair", "claim_expansion"] = "authoring"
    recommended_actions: list[str] = Field(default_factory=list)
    content_digest: str = ""


def compile_intent_obligation_graph(summary: AuthorIntentSummary | None) -> IntentObligationGraphV1:
    if summary is None:
        payload = {
            "project_goal": "",
            "method_goal": "",
            "implementation_scope": "",
            "obligations": [],
            "relations": [],
        }
        return IntentObligationGraphV1(**payload, content_digest=_digest(payload))

    obligations: list[IntentObligation] = []
    seen: set[tuple[str, str]] = set()

    def add(
        *,
        kind: ObligationKind,
        priority: ObligationPriority,
        source_field: str,
        source_index: int,
        text: str,
        paths: list[str] | None = None,
    ) -> None:
        clean = _clean(text)
        signature = (kind, _normalize(clean))
        if not clean or signature in seen:
            return
        seen.add(signature)
        obligation_id = _obligation_id(kind, source_index, clean)
        candidate_paths = _dedupe([*(paths or []), *summary.priority_files])[:24]
        obligations.append(
            IntentObligation(
                obligation_id=obligation_id,
                kind=kind,
                priority=priority,
                source_field=source_field,
                source_index=source_index,
                author_text=clean,
                retrieval_queries=_retrieval_queries(clean),
                candidate_paths=candidate_paths,
            )
        )

    add(
        kind="method_mainline",
        priority="must_cover",
        source_field="method_mainline",
        source_index=0,
        text=summary.method_mainline or summary.method_goal,
    )
    for index, text in enumerate(summary.pipeline_steps):
        add(kind="stage", priority="must_cover", source_field="pipeline_steps", source_index=index, text=text)
    for index, text in enumerate(summary.module_roles):
        add(
            kind="component",
            priority="should_cover",
            source_field="module_roles",
            source_index=index,
            text=text,
            paths=_paths_from_module_role(text),
        )
    for index, text in enumerate(summary.key_building_blocks):
        add(
            kind="component",
            priority="should_cover",
            source_field="key_building_blocks",
            source_index=index,
            text=text,
        )
    for index, text in enumerate(summary.story_order):
        add(kind="organization", priority="preference", source_field="story_order", source_index=index, text=text)
    for index, text in enumerate(summary.design_intents):
        add(kind="rationale_check", priority="verify_only", source_field="design_intents", source_index=index, text=text)
    for index, text in enumerate(summary.innovation_claims):
        add(kind="high_risk_claim", priority="verify_only", source_field="innovation_claims", source_index=index, text=text)
    for index, text in enumerate(summary.potential_mismatches):
        add(kind="mismatch_check", priority="verify_only", source_field="potential_mismatches", source_index=index, text=text)

    stage_ids = [item.obligation_id for item in obligations if item.kind == "stage"]
    organization_ids = [item.obligation_id for item in obligations if item.kind == "organization"]
    relations = [
        IntentObligationRelation(
            source_obligation_id=source,
            target_obligation_id=target,
            relation="precedes",
        )
        for sequence in (stage_ids, organization_ids)
        for source, target in zip(sequence, sequence[1:])
    ]
    mainline = next((item.obligation_id for item in obligations if item.kind == "method_mainline"), "")
    if mainline:
        relations.extend(
            IntentObligationRelation(
                source_obligation_id=stage_id,
                target_obligation_id=mainline,
                relation="supports",
            )
            for stage_id in stage_ids
        )

    payload = {
        "project_goal": summary.project_goal,
        "method_goal": summary.method_goal,
        "implementation_scope": summary.implementation_scope,
        "obligations": [item.model_dump(mode="json") for item in obligations],
        "relations": [item.model_dump(mode="json") for item in relations],
    }
    return IntentObligationGraphV1(**payload, content_digest=_digest(payload))


def build_authoring_obligation_coverage(
    graph: IntentObligationGraphV1,
    projection: AuthoringInputProjection,
) -> AuthoringObligationCoverageReport:
    claims = list(projection.projected_claims)
    stage_packets = list(projection.stage_packets)
    explicit_gaps = [
        item for item in projection.forbidden_claims
        if str(item.reason).startswith("explicit_code_gap:")
    ]
    v3_projection = any(item.source.startswith("atomic_claim_v3:") for item in claims)
    items: list[ObligationCoverageItem] = []
    for obligation in graph.obligations:
        if obligation.kind == "organization":
            matched_stages, score = _match_stages(obligation.author_text, stage_packets)
            status: CoverageStatus = "organization_available" if matched_stages else "unresolved"
            items.append(
                ObligationCoverageItem(
                    obligation_id=obligation.obligation_id,
                    kind=obligation.kind,
                    priority=obligation.priority,
                    status=status,
                    matched_stage_ids=matched_stages,
                    lexical_coverage=score,
                    rationale=(
                        "Author organization preference has a compatible evidence-backed stage."
                        if matched_stages
                        else "No evidence-backed stage currently represents this organization preference."
                    ),
                )
            )
            continue

        matches: list[tuple[str, float]] = []
        for claim in claims:
            score = _semantic_coverage(obligation.author_text, claim.supported_fragment)
            if score > 0.0:
                matches.append((claim.claim_id, score))
        best = max((score for _claim_id, score in matches), default=0.0)
        claim_ids = [claim_id for claim_id, _score in sorted(matches, key=lambda item: (-item[1], item[0]))]
        if v3_projection:
            v3_status, v3_claim_ids, v3_rationale = _resolve_v3_obligation(
                obligation.author_text,
                claims,
                explicit_gaps,
            )
            if v3_status:
                items.append(ObligationCoverageItem(
                    obligation_id=obligation.obligation_id,
                    kind=obligation.kind,
                    priority=obligation.priority,
                    status=v3_status,
                    projected_claim_ids=v3_claim_ids,
                    lexical_coverage=round(best, 4),
                    rationale=v3_rationale,
                ))
                continue
        gap_matches = [
            item for item in explicit_gaps
            if _semantic_coverage(
                obligation.author_text,
                str(item.reason).removeprefix("explicit_code_gap:") + " "
                + str(item.repair_metadata.get("rationale") or ""),
            ) > 0.0
        ]
        if best >= 0.55:
            status = "candidate_covered"
            rationale = "A projection-authorized code claim covers the central terms of this author obligation."
        elif matches:
            status = "partially_covered"
            rationale = "An authorized claim is related, but it does not cover enough of the author obligation."
        elif gap_matches:
            status = "not_implemented_in_repo"
            rationale = "The obligation terminates as an explicit code gap in the provided executable scope."
        else:
            status = "unresolved"
            rationale = "No projection-authorized claim currently covers this obligation."
        items.append(
            ObligationCoverageItem(
                obligation_id=obligation.obligation_id,
                kind=obligation.kind,
                priority=obligation.priority,
                status=status,
                projected_claim_ids=claim_ids,
                lexical_coverage=round(best, 4),
                rationale=rationale,
            )
        )

    must_cover = [item for item in items if item.priority == "must_cover"]
    unresolved_must = [
        item.obligation_id
        for item in must_cover
        if item.status not in {
            "candidate_covered", "partially_covered", "organization_available", "not_implemented_in_repo"
        }
    ]
    signatures: dict[str, list[str]] = {}
    for claim in claims:
        signatures.setdefault(_normalize(claim.supported_fragment), []).append(claim.claim_id)
    duplicate_ids = [claim_id for ids in signatures.values() if len(ids) > 1 for claim_id in ids[1:]]
    fan_in = [len(claim.direct_evidence_ids) for claim in claims]
    unique_count = len([signature for signature in signatures if signature])
    actions: list[str] = []
    if unresolved_must:
        recommended_next = "targeted_evidence_repair"
        actions.append("resolve_uncovered_must_cover_obligations_before_counting_the_method_as_usable")
    elif unique_count <= 1 and graph.obligations:
        recommended_next = "claim_expansion"
        actions.append("decompose_author_obligations_and_compile_additional_code_supported_claims")
    else:
        recommended_next = "authoring"
        actions.append("plan_narrative_from_authorized_claims_and_obligation_order")
    if duplicate_ids:
        actions.append("deduplicate_canonical_claims_before_writing")
    if any(value > 3 for value in fan_in):
        actions.append("replace_large_evidence_unions_with_minimal_obligation_packets")

    payload = {
        "obligation_graph_digest": graph.content_digest,
        "projection_digest": projection.projection_digest,
        "items": [item.model_dump(mode="json") for item in items],
        "must_cover_count": len(must_cover),
        "candidate_covered_must_cover_count": len(must_cover) - len(unresolved_must),
        "unresolved_must_cover_ids": unresolved_must,
        "projected_claim_count": len(claims),
        "unique_projected_claim_count": unique_count,
        "duplicate_projected_claim_ids": duplicate_ids,
        "average_direct_evidence_fan_in": round(sum(fan_in) / len(fan_in), 4) if fan_in else 0.0,
        "max_direct_evidence_fan_in": max(fan_in, default=0),
        "recommended_next": recommended_next,
        "recommended_actions": actions,
    }
    return AuthoringObligationCoverageReport(**payload, content_digest=_digest(payload))


def write_intent_obligation_graph(path: str | Path, graph: IntentObligationGraphV1) -> Path:
    return _write_model(path, graph)


def write_authoring_obligation_coverage(
    path: str | Path,
    report: AuthoringObligationCoverageReport,
) -> Path:
    return _write_model(path, report)


def build_review_candidates_from_coverage(
    graph: IntentObligationGraphV1,
    coverage: AuthoringObligationCoverageReport,
    *,
    policy: MethodOutputPolicyV1 | None = None,
) -> tuple[MethodReviewCandidateV1, ...]:
    """Turn uncovered author obligations into actionable author review items.

    Every obligation that the research/projection loop could not cover with
    verified repository support becomes a review candidate with non-empty
    editable ``proposed_body`` and an exact confirmation question.  These
    items block verified inclusion but never candidate generation, so an
    author point that lacks code evidence survives into the review loop
    instead of disappearing.
    """

    policy = policy or build_default_method_output_policy()
    if coverage is None:
        return ()
    obligations_by_id = {item.obligation_id: item for item in graph.obligations}
    candidates: list[MethodReviewCandidateV1] = []
    for item in coverage.items:
        if item.status in {"candidate_covered", "organization_available"}:
            continue
        obligation = obligations_by_id.get(item.obligation_id)
        statement = (
            str(getattr(obligation, "author_text", "") or "").strip()
            or str(item.rationale or "").strip()
        )
        if not statement:
            statement = f"Author-intended method point {item.obligation_id}."
        lane: MethodEvidenceLane
        if item.status == "partially_covered":
            lane = "repository_partial"
        elif item.status == "not_implemented_in_repo":
            lane = "author_intent_unverified"
        else:
            lane = "author_intent_unverified"
        if lane not in policy.review_required_lanes and lane not in policy.verified_positive_lanes:
            lane = "author_intent_unverified"
        proposed_body = (
            "The method is intended to address the following point, which "
            "currently awaits repository or author confirmation: "
            + statement.rstrip(".") + "."
        )
        candidates.append(MethodReviewCandidateV1(
            candidate_id=f"review:{item.obligation_id}",
            source_obligation_id=item.obligation_id,
            lane=lane,
            status=str(item.status),
            proposed_body=proposed_body,
            confirmation_question=(
                f"Should the Method confirm that {statement.rstrip('.').lower()}?"
            ),
            needed_evidence=tuple(_dedupe([*item.projected_claim_ids, item.rationale])),
            suggested_action="confirm_author_intent_or_provide_evidence",
            blocks_verified=True,
            blocks_candidate=False,
            trace_refs=(item.obligation_id,),
        ))
    return tuple(candidates)


def _match_stages(text: str, packets: list[dict]) -> tuple[list[str], float]:
    matches: list[tuple[str, float]] = []
    for packet in packets:
        packet_text = " ".join(str(packet.get(key) or "") for key in ("name", "purpose", "stage_claim"))
        score = _semantic_coverage(text, packet_text)
        if score > 0.0:
            matches.append((str(packet.get("stage_id") or ""), score))
    return [stage_id for stage_id, _score in matches if stage_id], max((score for _stage, score in matches), default=0.0)


def _resolve_v3_obligation(
    author_text: str,
    claims: list,
    gaps: list,
) -> tuple[CoverageStatus | None, list[str], str]:
    """Resolve author language against typed behavior targets (R5.3 generic).

    Replaces the V1 RAP-hardcoded version with a project-agnostic path
    that uses the V2 concept registry (``intent_compiler_v2``) to derive
    typed behavior predicates from author text and from each claim's
    ``supported_fragment``.  Coverage requires:

    - a predicate intersection between the obligation's concepts and the
      claim's concepts (so the claim actually addresses the behavior the
      author asked about);
    - scope compatibility: a training-scoped obligation concept can only
      be covered by a training-scoped claim concept; an inference-scoped
      obligation concept accepts inference or unconditional claims.  This
      is the R5.3 training/inference separation rule.

    When no claim matches but an explicit gap artifact is present, the
    obligation terminates as ``not_implemented_in_repo``.  When the
    obligation text carries no behavior concept at all, the function
    returns ``None`` so the V1 semantic-coverage fallback path handles
    it (this preserves backward compatibility for free-form author notes
    that do not mention any executable behavior).
    """

    from code2paper.agentic.intent_compiler_v2 import _match_concepts

    obl_concepts = list(_match_concepts(author_text))
    if not obl_concepts:
        return None, [], ""

    # R5.3 conservative scope rule: if any concept is training-scoped, only
    # use training-scoped concepts for coverage.  This prevents inference
    # claims from covering a training obligation via any-scoped concepts
    # that happen to share predicates (e.g. "predictor" in "Three training
    # losses learn the importance predictor" must not let inference claims
    # cover the training obligation).  The obligation as a whole is treated
    # as training-scoped because the author's intent is training.
    has_training_scope = any(c.scope == "training" for c in obl_concepts)
    if has_training_scope:
        effective_concepts = [c for c in obl_concepts if c.scope == "training"]
    else:
        effective_concepts = obl_concepts

    matched_claim_ids: list[str] = []
    for claim in claims:
        claim_fragment = getattr(claim, "supported_fragment", "") or getattr(claim, "claim_text", "")
        claim_concepts = list(_match_concepts(claim_fragment))
        if not claim_concepts:
            continue
        if _claim_covers_obligation(effective_concepts, claim_concepts):
            matched_claim_ids.append(claim.claim_id)

    has_gap = bool(gaps)
    if matched_claim_ids and has_gap:
        return (
            "partially_covered",
            list(dict.fromkeys(matched_claim_ids)),
            "Executable parts are covered by validated V3 claims; non-executable extensions terminate as explicit code gaps.",
        )
    if matched_claim_ids:
        return (
            "partially_covered",
            list(dict.fromkeys(matched_claim_ids)),
            "Typed V3 claims cover the executable behavior; broader motivation or deployment wording remains outside the code-backed boundary.",
        )
    if has_gap and has_training_scope:
        return (
            "not_implemented_in_repo",
            [],
            "The requested training behavior terminates as an explicit code gap in the executable scope.",
        )
    if has_gap:
        return (
            "not_implemented_in_repo",
            [],
            "The requested behavior terminates as an explicit code gap in the executable scope.",
        )
    return None, [], ""


def _claim_covers_obligation(obl_concepts: list, claim_concepts: list) -> bool:
    """Return True if any claim concept covers any obligation concept.

    Coverage requires predicate intersection AND scope compatibility.
    """

    for obl_concept in obl_concepts:
        for claim_concept in claim_concepts:
            if not (set(obl_concept.predicates) & set(claim_concept.predicates)):
                continue
            if _concept_scopes_compatible(obl_concept.scope, claim_concept.scope):
                return True
    return False


def _concept_scopes_compatible(obl_scope: str, claim_scope: str) -> bool:
    """Check if a claim concept scope can cover an obligation concept scope.

    Mirrors ``_scope_compatible`` in ``obligation_fact_alignment.py`` but
    operates on individual concept scopes.  Rules:

    - ``any`` obligation may be covered by any claim scope;
    - ``training`` obligation may only be covered by ``training`` claims;
    - ``inference`` obligation may be covered by ``inference`` or ``any``
      claims (an unconditional claim is assumed to run on the inference
      path unless explicitly training-gated).
    """

    if obl_scope == "any":
        return True
    if obl_scope == "training":
        return claim_scope == "training"
    if obl_scope == "inference":
        return claim_scope in {"inference", "any"}
    return False


def _semantic_coverage(author_text: str, supported_text: str) -> float:
    if not _specific_obligation_anchors_supported(author_text, supported_text):
        return 0.0
    author_tokens = _semantic_tokens(author_text)
    supported_tokens = _semantic_tokens(supported_text)
    if not author_tokens or not supported_tokens:
        return 0.0
    overlap = author_tokens & supported_tokens
    lexical = len(overlap) / max(1, len(author_tokens))
    if lexical >= 0.18 and len(overlap) >= 2:
        return lexical
    if concepts_semantically_related(author_text, supported_text):
        return max(lexical, 0.2)
    return 0.0


_OBLIGATION_ANCHORS: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...] = (
    (
        re.compile(r"\b(?:train|learn|optimi[sz])(?:s|ed|ing)?\b", re.IGNORECASE),
        re.compile(r"\b(?:train|learn|optimizer|backward|training_step|fit\s*\()", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(?:loss|losses|objective|objectives)\b", re.IGNORECASE),
        re.compile(r"\b(?:loss|losses|objective|objectives)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(?:render[- ]free|without rendering)\b", re.IGNORECASE),
        re.compile(r"\b(?:render[- ]free|without rendering|does not call .*render)\b", re.IGNORECASE),
    ),
)


def _specific_obligation_anchors_supported(author_text: str, supported_text: str) -> bool:
    """Do not let generic shared nouns satisfy a high-specificity obligation."""

    return all(
        not author_pattern.search(author_text) or bool(claim_pattern.search(supported_text))
        for author_pattern, claim_pattern in _OBLIGATION_ANCHORS
    )


def _retrieval_queries(text: str) -> list[str]:
    tokens = sorted(_semantic_tokens(text))
    compact = " ".join(tokens[:14])
    return _dedupe([text, compact])


def _paths_from_module_role(text: str) -> list[str]:
    prefix = text.split(":", 1)[0].strip()
    path = prefix.split("::", 1)[0].strip()
    return [path] if "/" in path or Path(path).suffix else []


def _obligation_id(kind: str, index: int, text: str) -> str:
    suffix = hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()[:8]
    return f"O-{kind.upper().replace('_', '-')}-{index + 1:02d}-{suffix}"


def _semantic_tokens(text: str) -> set[str]:
    stop = {
        "the", "a", "an", "of", "to", "and", "or", "is", "are", "we", "our",
        "this", "that", "with", "for", "from", "into", "by", "as", "method",
        "stage", "module", "system", "using", "use",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", str(text or "").lower())
        if len(token) > 1 and token not in stop
    }


def _clean(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize(value: str) -> str:
    return _clean(value).lower().rstrip(".")


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _clean(value)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _write_model(path: str | Path, model: BaseModel) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
