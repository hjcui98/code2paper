"""Typed four-layer projection exposed to the Method Writer.

Stage 4 (pause-diagnosis plan): the projection gains an optional concept
layer built from Stage 2/3 Method Concept Cards, so the Writer can plan
reader-facing prose from verified/caveated *concepts* instead of raw
low-level propositions.  The existing proposition layer remains for
compatibility; a section uses either propositions or concept cards, never
both at once.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.method_argument_facet_aligner import (
    build_mechanism_authoring_packet,
)
from code2paper.agentic.method_concept_card_models import MethodConceptCardV1
from code2paper.agentic.method_argument_brief_models import (
    CandidateFacetPolicyV1,
    FacetEvidenceAlignmentV1,
    AuthorMechanismFacetV1,
    MechanismAuthoringPacketV1,
    MethodArgumentBriefV1,
    PublicationFieldCandidateV1,
    TypedFieldDeferredV1,
)
from code2paper.agentic.method_proposition_models import MethodPropositionV1


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()


_RHETORICAL_HEADING_RE = re.compile(
    r"\b(motivation|overview|related.?work|background|introduction|overall framework)\b",
    re.I,
)


def heading_is_rhetorical_frame(heading: str) -> bool:
    return bool(_RHETORICAL_HEADING_RE.search(str(heading or "")))


def _view_tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", str(text or ""))
    }


_STAGE_HEADING_RE = re.compile(
    r"\b(?:retriev(?:e|al|ed|ing)?|activat(?:e|ion|ed|ing)?|bridg(?:e|ing)?|frontier|offline|aggregat(?:e|ion|ed|ing)?|rank)\b",
    re.I,
)
_LOCAL_FAMILY_RE = re.compile(
    r"\b(?:first|activat(?:e|ion|ed|ing)?|bridg(?:e|ing)?|frontier|threshold|prune|exclude)\b",
    re.I,
)
_GLOBAL_FAMILY_RE = re.compile(
    r"\b(?:second|pagerank|ppr|passage|damping|global|aggregat(?:e|ion|ed|ing)?|rank)\b",
    re.I,
)
_OFFLINE_FAMILY_RE = re.compile(
    r"\b(offline|construct|index|corpus|adjacenc)\b",
    re.I,
)
_TRAINING_FAMILY_RE = re.compile(
    r"\b(?:train(?:ing|s|ed)?|loss(?:es)?|optimiz(?:e|ation|er)?)\b",
    re.I,
)
_ARCHITECTURE_FAMILY_RE = re.compile(
    r"\b(?:architectur\w*|encod(?:e|ing|er|ed)?|embed(?:ding)?s?|attention|augment(?:ation|ed)?|transformer|sinusoid(?:al)?|hybrid|retriev(?:e|al|ed|ing)?)\b",
    re.I,
)


def _heading_family(text: str) -> str:
    if heading_is_rhetorical_frame(text):
        return "frame"
    if _TRAINING_FAMILY_RE.search(text):
        return "training"
    if _LOCAL_FAMILY_RE.search(text):
        return "local"
    if _GLOBAL_FAMILY_RE.search(text):
        return "global"
    if _OFFLINE_FAMILY_RE.search(text):
        return "offline"
    if _ARCHITECTURE_FAMILY_RE.search(text):
        return "architecture"
    return "other"


def rebound_stage_claims_for_routing_conflict(
    *,
    heading: str,
    bound_claim_ids: set[str],
    claims_by_id: Mapping[str, Any],
    heading_to_claim_ids: Mapping[str, Any] | None = None,
) -> tuple[tuple[Any, ...], bool]:
    """Rebind STAGE facts onto an empty mechanism H2 without sibling steal.

    ``ROUTING_CONFLICT`` fires when this heading has no L2 but the global
    store already holds matching STAGE claims.  Claims bound to another
    non-rhetorical heading stay put.
    """

    if heading_is_rhetorical_frame(heading):
        return (), False
    heading_tokens = _view_tokens(heading)
    if not heading_tokens:
        return (), False
    for claim_id in bound_claim_ids:
        claim = claims_by_id.get(claim_id)
        if claim is None:
            continue
        kind = str(getattr(claim, "claim_kind", "") or "")
        level = str(getattr(claim, "inference_level", "E0") or "E0")
        if kind == "technical_semantic" or level in {"E2", "E3"}:
            return (), False
    mechanism_bound: set[str] = set()
    mechanism_headings = [
        str(other)
        for other in (heading_to_claim_ids or {})
        if not heading_is_rhetorical_frame(str(other))
    ]
    target_family = _heading_family(heading)
    for other_heading, ids in (heading_to_claim_ids or {}).items():
        if str(other_heading) == heading or heading_is_rhetorical_frame(str(other_heading)):
            continue
        other_family = _heading_family(str(other_heading))
        if target_family == "local" and other_family == "offline":
            for claim_id in ids or ():
                claim = claims_by_id.get(str(claim_id))
                if claim is None:
                    mechanism_bound.add(str(claim_id))
                    continue
                covers = " ".join(
                    str(item) for item in getattr(claim, "covers_obligation_ids", ()) or ()
                )
                claim_family = _heading_family(
                    f"{getattr(claim, 'canonical_text', '')} {covers}"
                )
                if claim_family == "local" or "STAGE" in covers.upper():
                    continue
                mechanism_bound.add(str(claim_id))
            continue
        mechanism_bound.update(str(item) for item in (ids or ()))
    rebound: list[Any] = []
    for claim in claims_by_id.values():
        claim_id = str(getattr(claim, "claim_id", "") or "")
        if not claim_id or claim_id in bound_claim_ids or claim_id in mechanism_bound:
            continue
        covers = " ".join(
            str(item) for item in getattr(claim, "covers_obligation_ids", ()) or ()
        )
        kind = str(getattr(claim, "claim_kind", "") or "")
        if "STAGE" not in covers.upper() and kind != "technical_semantic":
            continue
        claim_text = str(getattr(claim, "canonical_text", "") or "")
        claim_tokens = _view_tokens(claim_text)
        if not claim_tokens:
            continue
        claim_family = _heading_family(claim_text)

        def _score(candidate_heading: str) -> float:
            tokens = _view_tokens(candidate_heading)
            overlap = (
                len(claim_tokens & tokens) / max(1, len(claim_tokens | tokens))
                if tokens else 0.0
            )
            family = _heading_family(candidate_heading)
            bonus = 0.5 if family != "other" and family == claim_family else 0.0
            if family != "other" and _STAGE_HEADING_RE.search(candidate_heading):
                bonus += 0.05
            return overlap + bonus

        own = _score(heading)
        best_other = max((_score(other) for other in mechanism_headings if other != heading), default=0.0)
        if own > best_other:
            rebound.append(claim)
    return tuple(rebound), bool(rebound)


class _ViewModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WriterSectionPurposeV1(_ViewModel):
    heading: str
    reader_question: str
    section_goal: str = ""
    preceding_context: str = ""
    following_context: str = ""


class WriterPositivePropositionV1(_ViewModel):
    proposition_id: str
    reader_subject: str
    transformation: str
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    paper_terms: tuple[str, ...] = Field(default_factory=tuple)
    optional_implementation_bindings: tuple[str, ...] = Field(default_factory=tuple)


class WriterCaveatedPropositionV1(_ViewModel):
    proposition_id: str
    lane: str
    intended_subject: str
    intended_transformation: str
    known_parts: tuple[str, ...] = Field(default_factory=tuple)
    missing_parts: tuple[str, ...] = Field(default_factory=tuple)
    required_caveat_kind: Literal[
        "author_intent", "partial", "mismatch", "pending_external", "pending_formalization"
    ]
    review_question: str = ""


class WriterImmutableConstraintV1(_ViewModel):
    proposition_id: str
    required_qualifiers: tuple[str, ...] = Field(default_factory=tuple)
    required_numeric_tokens: tuple[str, ...] = Field(default_factory=tuple)
    formula_renderings: tuple[str, ...] = Field(default_factory=tuple)
    configuration_values: tuple[str, ...] = Field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Stage 4 concept layer (from Method Concept Cards)
# ---------------------------------------------------------------------------


class WriterSupportingFactV1(_ViewModel):
    """A low-level supporting fact nested under a primary concept (WP5)."""

    concept_key: str
    method_subject: str
    operation: str = ""
    role: str = "supporting"


class WriterPositiveConceptV1(_ViewModel):
    """A repository-supported concept the Writer may state positively."""

    concept_key: str
    method_subject: str
    operation: str
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    numeric_constraints: tuple[str, ...] = Field(default_factory=tuple)
    formula_constraints: tuple[str, ...] = Field(default_factory=tuple)
    known_parts: tuple[str, ...] = Field(default_factory=tuple)
    story_node: str = ""
    realizes_story_node: bool = False
    supporting_facts: tuple[WriterSupportingFactV1, ...] = Field(default_factory=tuple)


class WriterCaveatedConceptV1(_ViewModel):
    """An author-intent / partial concept the Writer must caveat explicitly."""

    concept_key: str
    lane: str
    method_subject: str
    operation: str
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    known_parts: tuple[str, ...] = Field(default_factory=tuple)
    missing_parts: tuple[str, ...] = Field(default_factory=tuple)
    candidate_caveat: str = ""
    required_caveat_kind: Literal[
        "author_intent", "partial", "mismatch", "pending_external", "pending_formalization"
    ]
    review_question: str = ""


class WriterConceptConstraintV1(_ViewModel):
    """Immutable numbers/formulas/qualifiers bound to one concept."""

    concept_key: str
    required_qualifiers: tuple[str, ...] = Field(default_factory=tuple)
    numeric_constraints: tuple[str, ...] = Field(default_factory=tuple)
    formula_constraints: tuple[str, ...] = Field(default_factory=tuple)


class WriterLicensedNarrativeV1(_ViewModel):
    """Positively licensed author wording plus closed evidence ids."""

    brief_id: str
    licensed_wording: str
    bound_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_equation_ids: tuple[str, ...] = Field(default_factory=tuple)


class WriterUnlicensedIntentV1(_ViewModel):
    """Unlicensed or partial author clause retained as intent."""

    brief_id: str
    clause_id: str
    text: str
    required_caveat_kind: Literal[
        "author_intent", "partial", "mismatch", "pending_external", "pending_formalization"
    ]
    missing_target_ids: tuple[str, ...] = Field(default_factory=tuple)


class WriterMechanismDraftV1(_ViewModel):
    """Planner mechanism draft constraint; not final prose authority."""

    brief_id: str
    text: str = ""
    cited_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    cited_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    caveat: str = ""
    status: str = "empty"


class WriterBriefConstraintV1(_ViewModel):
    brief_id: str
    formula_constraints: tuple[str, ...] = Field(default_factory=tuple)
    cited_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    cited_equation_ids: tuple[str, ...] = Field(default_factory=tuple)


class WriterEvidenceClaimTextV1(_ViewModel):
    """Read-only repository claim text for brief-mode factual alignment."""

    brief_id: str
    claim_id: str
    canonical_text: str


class WriterViewV1(_ViewModel):
    purpose: WriterSectionPurposeV1
    positive_propositions: tuple[WriterPositivePropositionV1, ...] = Field(default_factory=tuple)
    caveated_propositions: tuple[WriterCaveatedPropositionV1, ...] = Field(default_factory=tuple)
    immutable_constraints: tuple[WriterImmutableConstraintV1, ...] = Field(default_factory=tuple)
    positive_concepts: tuple[WriterPositiveConceptV1, ...] = Field(default_factory=tuple)
    caveated_concepts: tuple[WriterCaveatedConceptV1, ...] = Field(default_factory=tuple)
    concept_constraints: tuple[WriterConceptConstraintV1, ...] = Field(default_factory=tuple)
    allowed_proposition_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_proposition_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_concept_keys: tuple[str, ...] = Field(default_factory=tuple)
    required_concept_keys: tuple[str, ...] = Field(default_factory=tuple)
    positive_briefs: tuple[WriterLicensedNarrativeV1, ...] = Field(default_factory=tuple)
    caveated_briefs: tuple[WriterUnlicensedIntentV1, ...] = Field(default_factory=tuple)
    brief_constraints: tuple[WriterBriefConstraintV1, ...] = Field(default_factory=tuple)
    mechanism_drafts: tuple[WriterMechanismDraftV1, ...] = Field(default_factory=tuple)
    evidence_claim_texts: tuple[WriterEvidenceClaimTextV1, ...] = Field(default_factory=tuple)
    technical_propositions: tuple[WriterPositivePropositionV1, ...] = Field(default_factory=tuple)
    allowed_brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    callback_opportunities: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    mechanism_authoring_packet: MechanismAuthoringPacketV1 | None = None
    publication_field_candidates: tuple[PublicationFieldCandidateV1, ...] = Field(default_factory=tuple)
    typed_field_deferred: tuple[TypedFieldDeferredV1, ...] = Field(default_factory=tuple)
    view_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "WriterViewV1":
        available = {
            item.proposition_id for item in self.positive_propositions
        } | {item.proposition_id for item in self.caveated_propositions}
        if set(self.allowed_proposition_ids) != available:
            raise ValueError("writer view allowed proposition set is not closed")
        if not set(self.required_proposition_ids).issubset(available):
            raise ValueError("writer view requires unknown propositions")
        if {item.proposition_id for item in self.immutable_constraints} - available:
            raise ValueError("writer constraints reference unknown propositions")
        concept_available = {
            item.concept_key for item in self.positive_concepts
        } | {item.concept_key for item in self.caveated_concepts}
        if set(self.allowed_concept_keys) != concept_available:
            raise ValueError("writer view allowed concept set is not closed")
        if not set(self.required_concept_keys).issubset(concept_available):
            raise ValueError("writer view requires unknown concepts")
        if {item.concept_key for item in self.concept_constraints} - concept_available:
            raise ValueError("writer concept constraints reference unknown concepts")
        brief_available = {
            item.brief_id for item in self.positive_briefs
        } | {item.brief_id for item in self.caveated_briefs}
        if set(self.allowed_brief_ids) != brief_available:
            raise ValueError("writer view allowed brief set is not closed")
        if not set(self.required_brief_ids).issubset(brief_available):
            raise ValueError("writer view requires unknown briefs")
        if {item.brief_id for item in self.brief_constraints} - brief_available:
            raise ValueError("writer brief constraints reference unknown briefs")
        if {item.brief_id for item in self.mechanism_drafts} - brief_available:
            raise ValueError("writer mechanism drafts reference unknown briefs")
        if self.mechanism_authoring_packet is not None:
            packet_briefs = set(self.mechanism_authoring_packet.brief_ids)
            if packet_briefs - brief_available:
                raise ValueError(
                    "writer authoring packet references unknown briefs"
                )
            packet_facet_briefs = {
                item.brief_id
                for item in self.mechanism_authoring_packet.facets
                if item.brief_id
            }
            if packet_facet_briefs - brief_available:
                raise ValueError(
                    "writer authoring packet facet references unknown briefs"
                )
            packet_candidate_ids = {
                item.candidate_id
                for item in self.mechanism_authoring_packet.publication_field_candidates
            }
            view_candidate_ids = {item.candidate_id for item in self.publication_field_candidates}
            if view_candidate_ids and packet_candidate_ids != view_candidate_ids:
                raise ValueError("writer field candidate view is not closed over packet")
        active_layers = sum(
            1 for layer in (available, concept_available, brief_available) if layer
        )
        if active_layers > 1:
            raise ValueError(
                "a writer view must use either propositions, concepts, or briefs, not several"
            )
        if concept_available and available:
            raise ValueError(
                "a writer view must use either propositions or concepts, not both"
            )
        computed = _digest(self.model_dump(mode="json", exclude={"view_digest"}))
        if self.view_digest and self.view_digest != computed:
            # The packet is an additive WP-L field.  Accept a digest created
            # by an older WriterView artifact when the new field was absent;
            # any mismatch in the current payload remains fail-closed.
            legacy_payload = self.model_dump(
                mode="json",
                exclude={
                    "view_digest",
                    "mechanism_authoring_packet",
                    "technical_propositions",
                },
            )
            if self.view_digest != _digest(legacy_payload):
                raise ValueError("writer view digest mismatch")
        object.__setattr__(self, "view_digest", computed)
        return self

    @property
    def authoring_packet(self) -> MechanismAuthoringPacketV1 | None:
        """Compatibility alias for the Writer's mechanism packet."""

        return self.mechanism_authoring_packet


def build_writer_view(
    *,
    heading: str,
    reader_question: str,
    section_goal: str,
    propositions: list[MethodPropositionV1],
    callback_opportunities: list[dict[str, Any]],
    configuration_values_by_proposition: dict[str, tuple[str, ...]] | None = None,
) -> WriterViewV1:
    configuration_values_by_proposition = configuration_values_by_proposition or {}
    # Q1 (plan 19.5.4): audit_only propositions stay in evidence but never
    # enter Writer sentence plans (positive, caveated, constraints, allowed
    # and required surfaces alike).  The author story selects content
    # upstream; this projection only keeps audit mechanics out of prose.
    visible = [
        item for item in propositions if item.writing_role != "audit_only"
    ]
    positive = tuple(
        WriterPositivePropositionV1(
            proposition_id=item.proposition_id,
            reader_subject=item.reader_subject,
            transformation=item.transformation,
            inputs=item.inputs,
            outputs=item.outputs,
            conditions=item.conditions,
            paper_terms=item.paper_terms,
            optional_implementation_bindings=item.implementation_binding_terms,
        )
        for item in visible if not item.requires_caveat
    )
    caveated = tuple(
        WriterCaveatedPropositionV1(
            proposition_id=item.proposition_id,
            lane=item.evidence_lane,
            intended_subject=item.reader_subject,
            intended_transformation=item.transformation,
            known_parts=tuple(dict.fromkeys((*item.inputs, *item.outputs, *item.conditions))),
            missing_parts=item.missing_or_uncertain_parts,
            required_caveat_kind=(
                "partial" if item.evidence_lane == "repository_partial"
                else "mismatch" if item.evidence_lane == "repository_mismatch"
                else "pending_external" if item.evidence_lane in {"literature_pending", "empirical_pending"}
                else "pending_formalization" if item.evidence_lane == "formalization_pending"
                else "author_intent"
            ),
            review_question=(
                "Which evidence or author confirmation should resolve this intended method point?"
            ),
        )
        for item in visible if item.requires_caveat
    )
    constraints = tuple(
        WriterImmutableConstraintV1(
            proposition_id=item.proposition_id,
            required_qualifiers=item.required_qualifiers,
            required_numeric_tokens=item.immutable_numeric_tokens,
            formula_renderings=item.immutable_formula_tokens,
            configuration_values=configuration_values_by_proposition.get(item.proposition_id, ()),
        )
        for item in visible
        if item.required_qualifiers or item.immutable_numeric_tokens or item.immutable_formula_tokens
        or configuration_values_by_proposition.get(item.proposition_id)
    )
    ids = tuple(item.proposition_id for item in visible)
    return WriterViewV1(
        purpose=WriterSectionPurposeV1(
            heading=heading, reader_question=reader_question, section_goal=section_goal,
        ),
        positive_propositions=positive,
        caveated_propositions=caveated,
        immutable_constraints=constraints,
        allowed_proposition_ids=ids,
        required_proposition_ids=ids,
        callback_opportunities=tuple(callback_opportunities),
    )


def build_writer_view_from_concept_cards(
    *,
    heading: str,
    reader_question: str,
    section_goal: str,
    cards: list[MethodConceptCardV1],
    callback_opportunities: list[dict[str, Any]],
    exclude_audit_only: bool = False,
    audit_override_concept_keys: frozenset[str] | None = None,
    story_nodes: list[Any] | tuple[Any, ...] = (),
    primary_concept_keys: tuple[str, ...] = (),
    supporting_concept_keys: tuple[str, ...] = (),
    audit_only_concept_keys: tuple[str, ...] = (),
) -> WriterViewV1:
    """Build a four-layer WriterView from Stage 2/3 Method Concept Cards.

    Positive concepts are repository cards eligible for the verified lane;
    caveated concepts are author-intent/partial cards.  Numbers, formulas
    and qualifiers travel as immutable concept constraints.  The Writer
    plans prose from concepts; the harness maps concept keys back to
    evidence fragments after writing.

    R1 (plan 19.5.4 on the concept lane): when ``exclude_audit_only`` is set,
    cards classified ``audit_only`` stay in evidence and validation sidecars
    but never enter the Writer sentence plan, coverage obligations, qualifier
    repair, or Formalizer inputs.  ``audit_override_concept_keys`` is the
    explicit author-story override: a card named there is scientifically
    material and is never filtered.
    """

    if exclude_audit_only:
        from code2paper.agentic.publication_relevance import classify_concept_card_writing_role

        override = set(audit_override_concept_keys or ())
        cards = [
            card for card in cards
            if card.concept_key in override
            or classify_concept_card_writing_role(
                card,
                story_selected=card.concept_key in override
                or bool(card.realized_story_node_ids),
            )
            != "audit_only"
        ]

    audit_keys = set(audit_only_concept_keys)
    if audit_keys:
        cards = [card for card in cards if card.concept_key not in audit_keys]

    def _concept_sort_key(card: MethodConceptCardV1) -> tuple[int, int, str]:
        if primary_concept_keys and card.concept_key in primary_concept_keys:
            return (0, primary_concept_keys.index(card.concept_key), card.concept_key)
        if supporting_concept_keys and card.concept_key in supporting_concept_keys:
            return (1, supporting_concept_keys.index(card.concept_key), card.concept_key)
        if card.realized_story_node_ids:
            return (0, len(primary_concept_keys), card.concept_key)
        return (2, 0, card.concept_key)

    supporting_set = set(supporting_concept_keys)
    primary_set = set(primary_concept_keys)
    primary_cards = [
        card for card in cards if card.concept_key in primary_set
    ]

    def _card_story_ids(card: MethodConceptCardV1) -> set[str]:
        ids = {
            str(item).strip()
            for item in (card.realized_story_node_ids or ())
            if str(item).strip()
        }
        story = str(card.story_node or "").strip()
        if story:
            ids.add(story)
        return ids

    def _supporting_facts_for(primary_card: MethodConceptCardV1) -> tuple[WriterSupportingFactV1, ...]:
        primary_stories = _card_story_ids(primary_card)
        is_first = bool(primary_cards) and primary_card.concept_key == primary_cards[0].concept_key
        nested: list[WriterSupportingFactV1] = []
        for item in cards:
            if item.concept_key not in supporting_set:
                continue
            support_stories = _card_story_ids(item)
            if primary_stories and support_stories:
                if not (primary_stories & support_stories):
                    continue
            elif not is_first:
                continue
            nested.append(WriterSupportingFactV1(
                concept_key=item.concept_key,
                method_subject=item.method_subject,
                operation=item.operation,
            ))
        return tuple(nested)

    def _as_positive(item: MethodConceptCardV1) -> WriterPositiveConceptV1:
        nested = (
            _supporting_facts_for(item)
            if item.concept_key in primary_set
            else ()
        )
        return WriterPositiveConceptV1(
            concept_key=item.concept_key,
            method_subject=item.method_subject,
            operation=item.operation,
            inputs=item.inputs,
            outputs=item.outputs,
            conditions=item.conditions,
            numeric_constraints=item.numeric_constraints,
            formula_constraints=item.formula_constraints,
            known_parts=item.known_parts,
            story_node=item.story_node,
            realizes_story_node=bool(item.realized_story_node_ids),
            supporting_facts=nested,
        )

    positive = tuple(
        _as_positive(item)
        for item in sorted(
            (
                card for card in cards
                if card.may_enter_verified and card.concept_key not in supporting_set
            ),
            key=_concept_sort_key,
        )
    )
    caveated = tuple(
        WriterCaveatedConceptV1(
            concept_key=item.concept_key,
            lane=item.authority_lane,
            method_subject=item.method_subject,
            operation=item.operation,
            inputs=item.inputs,
            outputs=item.outputs,
            known_parts=item.known_parts,
            missing_parts=item.missing_parts,
            candidate_caveat=item.candidate_caveat,
            required_caveat_kind=(
                "partial"
                if item.authority_lane == "repository" and not item.may_enter_verified
                else "author_intent" if item.authority_lane == "author_intent"
                else "pending_external"
                if item.authority_lane in {"external"}
                else "pending_formalization"
                if item.authority_lane == "formalization"
                else "mismatch"
            ),
            review_question=(
                "Which evidence or author confirmation should resolve this intended method point?"
            ),
        )
        for item in cards if not item.may_enter_verified
    )
    story_caveated = tuple(
        WriterCaveatedConceptV1(
            concept_key=f"story:{getattr(node, 'story_node_id', '')}",
            lane="author_intent_unverified",
            method_subject=str(getattr(node, "title", "") or heading).strip() or heading,
            operation=str(getattr(node, "author_statement", "") or "").strip() or section_goal,
            known_parts=(),
            missing_parts=("repository implementation not verified",),
            candidate_caveat=(
                "author-intended; repository implementation not verified"
            ),
            required_caveat_kind="author_intent",
            review_question=(
                "Which repository evidence would confirm this author-intended mechanism?"
            ),
        )
        for node in story_nodes
        if str(getattr(node, "author_statement", "") or "").strip()
        and str(getattr(node, "story_node_id", "") or "").strip()
    )
    caveated = tuple({item.concept_key: item for item in (*story_caveated, *caveated)}.values())
    constraints = tuple(
        WriterConceptConstraintV1(
            concept_key=item.concept_key,
            numeric_constraints=item.numeric_constraints,
            formula_constraints=item.formula_constraints,
        )
        for item in cards
        if item.numeric_constraints or item.formula_constraints
    )
    keys = tuple(dict.fromkeys((
        *(item.concept_key for item in positive),
        *(item.concept_key for item in caveated),
    )))
    if primary_concept_keys:
        required_keys = tuple(
            key for key in primary_concept_keys if key in keys
        )
    else:
        required_keys = tuple(
            key for key in keys
            if not any(
                item.concept_key == key and not item.realizes_story_node
                for item in positive
            )
        )
    return WriterViewV1(
        purpose=WriterSectionPurposeV1(
            heading=heading, reader_question=reader_question, section_goal=section_goal,
        ),
        positive_concepts=positive,
        caveated_concepts=caveated,
        concept_constraints=constraints,
        allowed_concept_keys=keys,
        required_concept_keys=required_keys,
        callback_opportunities=tuple(callback_opportunities),
    )


def build_writer_view_from_argument_briefs(
    *,
    heading: str,
    reader_question: str,
    section_goal: str,
    briefs: list[MethodArgumentBriefV1],
    callback_opportunities: list[dict[str, Any]],
    primary_brief_ids: tuple[str, ...] = (),
    supporting_brief_ids: tuple[str, ...] = (),
    claims_by_id: dict[str, Any] | None = None,
    facts_by_id: Mapping[str, Any] | None = None,
    heading_to_claim_ids: Mapping[str, Any] | None = None,
    mechanism_authoring_packet: MechanismAuthoringPacketV1 | None = None,
    authoring_packet: MechanismAuthoringPacketV1 | None = None,
    facets: tuple[AuthorMechanismFacetV1, ...] | list[AuthorMechanismFacetV1] = (),
    facet_alignments: tuple[FacetEvidenceAlignmentV1, ...]
    | list[FacetEvidenceAlignmentV1] = (),
    facet_policies: tuple[CandidateFacetPolicyV1, ...]
    | list[CandidateFacetPolicyV1] = (),
    formula_packages: tuple[dict[str, Any], ...]
    | list[dict[str, Any]] = (),
    publication_field_candidates: tuple[PublicationFieldCandidateV1, ...]
    | list[PublicationFieldCandidateV1] = (),
    typed_field_deferred: tuple[TypedFieldDeferredV1, ...]
    | list[TypedFieldDeferredV1] = (),
    required_facet_ids: tuple[str, ...] = (),
    organization_seed: str = "",
) -> WriterViewV1:
    """Build a WriterView from deterministic argument briefs."""

    claims_by_id = claims_by_id or {}
    facts_by_id = facts_by_id or {}
    packet = mechanism_authoring_packet or authoring_packet
    if packet is None and facets:
        packet = build_mechanism_authoring_packet(
            briefs=briefs,
            facets=facets,
            policies=facet_policies,
            alignments=facet_alignments,
            publication_field_candidates=publication_field_candidates,
            typed_field_deferred=typed_field_deferred,
            formula_packages=formula_packages,
            required_facet_ids=required_facet_ids,
            organization_seed=organization_seed,
        )
    brief_by_id = {brief.brief_id: brief for brief in briefs}
    positive: list[WriterLicensedNarrativeV1] = []
    caveated: list[WriterUnlicensedIntentV1] = []
    constraints: list[WriterBriefConstraintV1] = []
    drafts: list[WriterMechanismDraftV1] = []
    evidence_claim_texts: list[WriterEvidenceClaimTextV1] = []

    for brief in briefs:
        for claim_id in brief.claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is None:
                continue
            canonical_text = str(getattr(claim, "canonical_text", "") or "").strip()
            if not canonical_text:
                continue
            evidence_claim_texts.append(WriterEvidenceClaimTextV1(
                brief_id=brief.brief_id,
                claim_id=claim_id,
                canonical_text=canonical_text,
            ))
        if brief.licensed_wording.strip():
            positive.append(WriterLicensedNarrativeV1(
                brief_id=brief.brief_id,
                licensed_wording=brief.licensed_wording.strip(),
                bound_claim_ids=tuple(
                    claim_id
                    for clause in brief.clauses
                    if clause.license == "positively_licensed"
                    for claim_id in clause.bound_claim_ids
                ),
                bound_equation_ids=tuple(
                    equation_id
                    for clause in brief.clauses
                    if clause.license == "positively_licensed"
                    for equation_id in clause.bound_equation_ids
                ),
            ))
        for clause in brief.clauses:
            if clause.license == "unlicensed":
                caveated.append(WriterUnlicensedIntentV1(
                    brief_id=brief.brief_id,
                    clause_id=clause.clause_id,
                    text=clause.text,
                    required_caveat_kind="author_intent",
                    missing_target_ids=clause.missing_target_ids,
                ))
            elif clause.license == "partially_licensed":
                caveated.append(WriterUnlicensedIntentV1(
                    brief_id=brief.brief_id,
                    clause_id=clause.clause_id,
                    text=clause.text,
                    required_caveat_kind="partial",
                    missing_target_ids=clause.missing_target_ids,
                ))
        draft = brief.mechanism_draft
        if draft.text.strip() or draft.status not in {"empty", "not_required"}:
            drafts.append(WriterMechanismDraftV1(
                brief_id=brief.brief_id,
                text=draft.text,
                cited_claim_ids=draft.cited_claim_ids,
                cited_equation_ids=draft.cited_equation_ids,
                caveat=draft.caveat,
                status=draft.status,
            ))
            constraints.append(WriterBriefConstraintV1(
                brief_id=brief.brief_id,
                # Planner output is an organization seed, never an immutable
                # formula/evidence token constraint.  Requiring its exact
                # wording here would turn a planning sketch into a substring
                # gate and would prevent the Writer from rewriting it into
                # reader-facing Method prose.
                formula_constraints=(),
                cited_claim_ids=draft.cited_claim_ids,
                cited_equation_ids=draft.cited_equation_ids,
            ))

    brief_ids = tuple(dict.fromkeys(item.brief_id for item in (*positive, *caveated)))
    if primary_brief_ids:
        required_brief_ids = tuple(
            brief_id for brief_id in primary_brief_ids if brief_id in brief_ids
        )
    else:
        required_brief_ids = brief_ids

    bound_claim_ids = {
        claim_id
        for brief in briefs
        for claim_id in brief.claim_ids
    }
    technical: list[WriterPositivePropositionV1] = []
    seen_technical: set[str] = set()
    for claim in claims_by_id.values():
        kind = str(getattr(claim, "claim_kind", "") or "")
        level = str(getattr(claim, "inference_level", "E0") or "E0")
        if kind != "technical_semantic" and level != "E2":
            continue
        claim_id = str(getattr(claim, "claim_id", "") or "")
        if claim_id not in bound_claim_ids:
            continue
        text = str(getattr(claim, "canonical_text", "") or "").strip()
        if not text or claim_id in seen_technical:
            continue
        seen_technical.add(claim_id)
        fact_subjects = tuple(
            str(getattr(facts_by_id.get(fact_id), "subject", "") or "").strip()
            for fact_id in (getattr(claim, "fact_ids", ()) or ())
            if str(getattr(facts_by_id.get(fact_id), "subject", "") or "").strip()
        )
        technical.append(WriterPositivePropositionV1(
            proposition_id=claim_id,
            reader_subject=fact_subjects[0] if fact_subjects else "the method operation",
            transformation=text,
            optional_implementation_bindings=tuple(
                str(item) for item in getattr(claim, "parent_claim_ids", ()) or ()
            ),
        ))
        evidence_claim_texts.insert(0, WriterEvidenceClaimTextV1(
            brief_id=next((brief.brief_id for brief in briefs), ""),
            claim_id=claim_id,
            canonical_text=text,
        ))

    if not technical:
        rebound, conflict = rebound_stage_claims_for_routing_conflict(
            heading=heading,
            bound_claim_ids=bound_claim_ids,
            claims_by_id=claims_by_id,
            heading_to_claim_ids=heading_to_claim_ids,
        )
        if conflict:
            for claim in rebound:
                claim_id = str(getattr(claim, "claim_id", "") or "")
                text = str(getattr(claim, "canonical_text", "") or "").strip()
                if not claim_id or not text or claim_id in seen_technical:
                    continue
                seen_technical.add(claim_id)
                fact_subjects = tuple(
                    str(getattr(facts_by_id.get(fact_id), "subject", "") or "").strip()
                    for fact_id in (getattr(claim, "fact_ids", ()) or ())
                    if str(getattr(facts_by_id.get(fact_id), "subject", "") or "").strip()
                )
                technical.append(WriterPositivePropositionV1(
                    proposition_id=claim_id,
                    reader_subject=fact_subjects[0] if fact_subjects else "the method operation",
                    transformation=text,
                    optional_implementation_bindings=tuple(
                        str(item) for item in getattr(claim, "parent_claim_ids", ()) or ()
                    ),
                ))
                evidence_claim_texts.insert(0, WriterEvidenceClaimTextV1(
                    brief_id=next((brief.brief_id for brief in briefs), ""),
                    claim_id=claim_id,
                    canonical_text=text,
                ))

    return WriterViewV1(
        purpose=WriterSectionPurposeV1(
            heading=heading,
            reader_question=reader_question,
            section_goal=section_goal,
        ),
        positive_briefs=tuple(positive),
        caveated_briefs=tuple(caveated),
        brief_constraints=tuple(constraints),
        mechanism_drafts=tuple(drafts),
        evidence_claim_texts=tuple(evidence_claim_texts),
        technical_propositions=tuple(technical),
        allowed_brief_ids=brief_ids,
        required_brief_ids=required_brief_ids,
        callback_opportunities=tuple(callback_opportunities),
        mechanism_authoring_packet=packet,
        publication_field_candidates=tuple(
            packet.publication_field_candidates if packet is not None
            else publication_field_candidates
        ),
        typed_field_deferred=tuple(
            packet.typed_field_deferred if packet is not None
            else typed_field_deferred
        ),
    )
