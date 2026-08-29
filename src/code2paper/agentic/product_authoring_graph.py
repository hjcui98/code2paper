"""Product-authoring state machine and dependency invalidation.

The Research graph owns repository discovery.  This overlay owns the
writing-time product loop: authoring artifacts are compiled, sections are
written and validated, and an issue is returned to its owning repair lane.
It deliberately does not alter the R8 text-trust graph or its
``local_text_repair`` route.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.publication_issue_owner_router import (
    IssueOwnerV1,
    PublicationIssueOwnerRouteV1,
    route_publication_issues,
)
from code2paper.agentic.research_models import TextRepairIssueV1
from code2paper.core.output_names import method_output


PRODUCT_AUTHORING_SCHEMA_VERSION = "1.0"
PRODUCT_AUTHORING_GRAPH_CONTRACT = "product-authoring-v1"
PRODUCT_AUTHORING_START_NODE = "product_authoring_start"

PRODUCT_AUTHORING_NODE_NAMES: tuple[str, ...] = (
    "research_frozen",
    "brief_compile",
    "facet_decompose",
    "facet_evidence_align",
    "writing_gap_router",
    "writing_research_continue",
    "mechanism_planner",
    "architect",
    "section_formalizer",
    "section_writer",
    "reverse_validate",
    "issue_owner_router",
    "editor",
    "rewrite_method_language",
    "split_candidate_verified",
    "author_review_items",
)

PRODUCT_AUTHORING_DIRECT_EDGES: tuple[tuple[str, str], ...] = (
    ("research_frozen", "brief_compile"),
    ("brief_compile", "facet_decompose"),
    ("facet_decompose", "facet_evidence_align"),
    ("facet_evidence_align", "writing_gap_router"),
    ("writing_research_continue", "brief_compile"),
    ("mechanism_planner", "architect"),
    ("architect", "section_formalizer"),
    ("section_formalizer", "section_writer"),
    ("section_writer", "reverse_validate"),
    ("reverse_validate", "issue_owner_router"),
    ("split_candidate_verified", "author_review_items"),
)

PRODUCT_AUTHORING_CONDITIONAL_ROUTES: dict[str, tuple[str, ...]] = {
    "writing_gap_router": (
        "writing_research_continue",
        "mechanism_planner",
        "author_review_items",
    ),
    "issue_owner_router": (
        "writing_research_continue",
        "section_formalizer",
        "section_writer",
        "editor",
        "rewrite_method_language",
        "author_review_items",
    ),
    "editor": (
        "reverse_validate",
        "rewrite_method_language",
    ),
    "rewrite_method_language": (
        "reverse_validate",
        "split_candidate_verified",
    ),
}

_DEFAULT_NEXT_NODE: dict[str, str] = {
    "research_frozen": "brief_compile",
    "brief_compile": "facet_decompose",
    "facet_decompose": "facet_evidence_align",
    "facet_evidence_align": "writing_gap_router",
    "writing_research_continue": "brief_compile",
    "mechanism_planner": "architect",
    "architect": "section_formalizer",
    "section_formalizer": "section_writer",
    "section_writer": "reverse_validate",
    "reverse_validate": "issue_owner_router",
    "editor": "rewrite_method_language",
    "rewrite_method_language": "split_candidate_verified",
    "split_candidate_verified": "author_review_items",
    "author_review_items": "END",
}

_OWNER_NODE: dict[IssueOwnerV1, str] = {
    "research_continuation": "writing_research_continue",
    "formalizer": "section_formalizer",
    "writer": "section_writer",
    "editor": "editor",
    "rewrite": "rewrite_method_language",
    "review": "author_review_items",
}

_DEPENDENCY_ORDER: tuple[str, ...] = (
    "binding",
    "coverage",
    "equations",
    "completeness",
    "brief",
    "facet_policy",
    "formula",
    "placement",
    "section",
    "surface",
    "reverse_validation",
)
_DEPENDENCY_DOWNSTREAM: dict[str, tuple[str, ...]] = {
    "evidence": _DEPENDENCY_ORDER,
    "binding": _DEPENDENCY_ORDER[0:],
    "coverage": _DEPENDENCY_ORDER[1:],
    "equations": _DEPENDENCY_ORDER[2:],
    "completeness": _DEPENDENCY_ORDER[3:],
    "brief": _DEPENDENCY_ORDER[4:],
    "facet_policy": _DEPENDENCY_ORDER[5:],
    "formula": _DEPENDENCY_ORDER[6:],
    "placement": _DEPENDENCY_ORDER[7:],
    "section": _DEPENDENCY_ORDER[8:],
    "surface": _DEPENDENCY_ORDER[9:],
    "reverse_validation": _DEPENDENCY_ORDER[10:],
    "style": ("surface", "reverse_validation"),
    "style_rewrite": ("surface", "reverse_validation"),
}

_ARTIFACT_SURFACE: dict[str, str] = {
    "evidence_packets_v3": "evidence",
    "code_facts_v1": "evidence",
    "atomic_claims_v3": "evidence",
    "equation_claims_v1": "equations",
    "configuration_claims_v1": "completeness",
    "method_completeness_matrix_v1": "completeness",
    "method_argument_briefs_v1": "brief",
    "method_argument_facets_v1": "facet_policy",
    "facet_evidence_alignments_v1": "facet_policy",
    "candidate_facet_policies_v1": "facet_policy",
    "research_mechanism_dossiers_v1": "coverage",
    "derivation_records_v1": "formula",
    "formalization_section_results_v1": "formula",
    "method_section_plan_v2": "placement",
    "publication_candidate_method": "surface",
    "publication_candidate_annotated": "surface",
    "publication_candidate_annotations_v1": "surface",
    "candidate_authority_validation_v1": "surface",
    "repository_verified_method": "surface",
    "method_content_trace_v1": "surface",
    "publication_rewrite_results_v1": "style_rewrite",
    "text_evidence_validation": "reverse_validation",
}

# Authority id fields that become stale when a downstream surface is
# invalidated by an upstream change.  A surface listed in the *direct*
# change set has just been recompiled, so its current ids stay.
_SURFACE_ID_FIELDS: dict[str, tuple[str, ...]] = {
    "brief": ("brief_ids",),
    "facet_policy": ("facet_ids", "policy_ids"),
    "formula": ("formula_obligation_ids",),
    "placement": ("section_ids",),
    "section": ("section_ids",),
}


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class ProductAuthoringBudgetV1(BaseModel):
    """Independent budgets for research continuation and text revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_research_continuations_per_section: int = Field(default=2, ge=0)
    max_research_continuations_total: int = Field(default=6, ge=0)
    max_section_revision_rounds: int = Field(default=3, ge=1, le=5)
    max_steps: int = Field(default=64, ge=1)


class ProductAuthoringIssueV1(BaseModel):
    """An open issue with one deterministic primary owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_id: str = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    owner: IssueOwnerV1
    section_id: str = ""
    source: str = ""
    reason: str = ""
    status: str = "open"

    @model_validator(mode="after")
    def _valid_status(self) -> "ProductAuthoringIssueV1":
        if self.status not in {"open", "resolved", "deferred"}:
            raise ValueError(f"unknown product authoring issue status: {self.status}")
        return self


class ProductAuthoringAttemptReceiptV1(BaseModel):
    """Auditable input/output identity for one product node attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(min_length=1)
    node: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    attempt: int = Field(default=1, ge=1)
    issue_ids: tuple[str, ...] = Field(default_factory=tuple)
    affected_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    input_digest: str = ""
    output_digest: str = ""
    status: str = "applied"
    information_gain: bool = False
    semantic_delta: dict[str, Any] = Field(default_factory=dict)
    stop_reason: str = ""


class ProductAuthoringGraphState(TypedDict, total=False):
    """LangGraph transport shape; the Pydantic model is the authority."""

    authoring_state: dict[str, Any]


class ProductAuthoringStateV1(BaseModel):
    """Checkpointable state for the Method Agent product authoring loop."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PRODUCT_AUTHORING_SCHEMA_VERSION
    graph_contract_version: str = PRODUCT_AUTHORING_GRAPH_CONTRACT
    run_id: str = ""
    revision_id: str = "revision:0"
    frozen_revision_digest: str = ""
    revision_digest: str = ""
    frozen_digests: dict[str, str] = Field(default_factory=dict)
    revision_digests: dict[str, str] = Field(default_factory=dict)
    brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    policy_ids: tuple[str, ...] = Field(default_factory=tuple)
    formula_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    section_ids: tuple[str, ...] = Field(default_factory=tuple)
    open_issues: tuple[ProductAuthoringIssueV1, ...] = Field(default_factory=tuple)
    open_issue_ids: tuple[str, ...] = Field(default_factory=tuple)
    owner_routes: tuple[PublicationIssueOwnerRouteV1, ...] = Field(
        default_factory=tuple
    )
    invalidated_surfaces: tuple[str, ...] = Field(default_factory=tuple)
    affected_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    budgets: ProductAuthoringBudgetV1 = Field(
        default_factory=ProductAuthoringBudgetV1
    )
    attempt_receipts: tuple[ProductAuthoringAttemptReceiptV1, ...] = Field(
        default_factory=tuple
    )
    next_node: str = "research_frozen"
    terminal_status: str = "running"
    stop_reason: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed_and_digest(self) -> "ProductAuthoringStateV1":
        issue_ids = tuple(
            issue.issue_id for issue in self.open_issues if issue.status == "open"
        )
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("open issue ids must be unique")
        if self.open_issues and self.open_issue_ids and tuple(self.open_issue_ids) != issue_ids:
            raise ValueError("open_issue_ids must match open issue records")
        object.__setattr__(
            self,
            "open_issue_ids",
            issue_ids if self.open_issues else _unique(self.open_issue_ids),
        )
        if self.next_node not in set(PRODUCT_AUTHORING_NODE_NAMES) | {"END"}:
            raise ValueError(f"unknown product authoring node: {self.next_node}")
        if self.terminal_status not in {
            "running",
            "completed",
            "review_ready_with_warnings",
            "incomplete",
            "blocked",
        }:
            raise ValueError(f"unknown terminal status: {self.terminal_status}")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


def _unique(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        str(value).strip() for value in values if str(value).strip()
    ))


def _as_issue(
    issue: ProductAuthoringIssueV1 | TextRepairIssueV1 | Mapping[str, Any],
    *,
    section_id: str = "",
) -> ProductAuthoringIssueV1:
    if isinstance(issue, ProductAuthoringIssueV1):
        return issue
    if isinstance(issue, TextRepairIssueV1):
        route = route_publication_issues((issue,), section_id=section_id)[0]
        return ProductAuthoringIssueV1(
            issue_id=route.issue_id,
            issue_type=route.failure_type or "publication_issue",
            owner=route.owner,
            section_id=route.section_id,
            source="text_evidence_validation",
            reason=route.reason,
        )
    raw = dict(issue)
    if not raw.get("owner"):
        route = route_publication_issues((raw,), section_id=section_id)[0]
        raw["owner"] = route.owner
        raw.setdefault("reason", route.reason)
        raw.setdefault("issue_id", route.issue_id)
    raw.setdefault("issue_type", raw.get("failure_type") or "publication_issue")
    raw.setdefault("section_id", section_id)
    return ProductAuthoringIssueV1.model_validate(raw)


def build_product_authoring_state(
    *,
    run_id: str = "",
    frozen_digests: Mapping[str, str] | None = None,
    revision_digests: Mapping[str, str] | None = None,
    brief_ids: Iterable[str] = (),
    facet_ids: Iterable[str] = (),
    policy_ids: Iterable[str] = (),
    formula_obligation_ids: Iterable[str] = (),
    section_ids: Iterable[str] = (),
    open_issues: Iterable[
        ProductAuthoringIssueV1 | TextRepairIssueV1 | Mapping[str, Any]
    ] = (),
    affected_section_ids: Iterable[str] = (),
    budgets: ProductAuthoringBudgetV1 | None = None,
    next_node: str = "research_frozen",
    terminal_status: str = "running",
    stop_reason: str = "",
) -> ProductAuthoringStateV1:
    """Create a state from frozen/revision authority without inventing facts."""

    frozen = {
        str(key): str(value)
        for key, value in (frozen_digests or {}).items()
        if str(key).strip() and str(value).strip()
    }
    revision = {
        str(key): str(value)
        for key, value in (revision_digests or {}).items()
        if str(key).strip() and str(value).strip()
    }
    issues = tuple(_as_issue(item) for item in open_issues)
    frozen_digest = _digest(frozen) if frozen else ""
    revision_digest = _digest(revision) if revision else frozen_digest
    return ProductAuthoringStateV1(
        run_id=str(run_id or ""),
        frozen_revision_digest=frozen_digest,
        revision_digest=revision_digest,
        frozen_digests=frozen,
        revision_digests=revision,
        brief_ids=_unique(brief_ids),
        facet_ids=_unique(facet_ids),
        policy_ids=_unique(policy_ids),
        formula_obligation_ids=_unique(formula_obligation_ids),
        section_ids=_unique(section_ids),
        open_issues=issues,
        affected_section_ids=_unique(affected_section_ids),
        budgets=budgets or ProductAuthoringBudgetV1(),
        next_node=next_node,
        terminal_status=terminal_status,
        stop_reason=stop_reason,
    )


def _state_update(
    state: ProductAuthoringStateV1,
    **updates: Any,
) -> ProductAuthoringStateV1:
    payload = state.model_dump(mode="python")
    payload.update(updates)
    payload.pop("content_digest", None)
    return ProductAuthoringStateV1.model_validate(payload)


def invalidated_surfaces_for_changes(
    changed_surfaces: str | Iterable[str],
) -> tuple[str, ...]:
    """Return downstream authoring surfaces in dependency order.

    Evidence changes invalidate every downstream authority.  A pure style
    rewrite invalidates only the final surface and reverse validation.
    """

    changes = (
        (changed_surfaces,)
        if isinstance(changed_surfaces, str)
        else tuple(changed_surfaces)
    )
    invalidated: set[str] = set()
    for change in changes:
        invalidated.update(_DEPENDENCY_DOWNSTREAM.get(str(change).strip(), ()))
    return tuple(surface for surface in _DEPENDENCY_ORDER if surface in invalidated)


def apply_dependency_invalidation(
    state: ProductAuthoringStateV1,
    *,
    changed_surfaces: str | Iterable[str],
    affected_section_ids: Iterable[str] = (),
    revision_digests: Mapping[str, str] | None = None,
) -> ProductAuthoringStateV1:
    """Apply dependency invalidation without deleting the incumbent text.

    Downstream formula/section/brief/facet ids are dropped when those
    surfaces were not themselves recompiled in this revision, so a changed
    evidence digest cannot keep authorizing the previous products.
    """

    direct_changes = _unique(
        (changed_surfaces,)
        if isinstance(changed_surfaces, str)
        else tuple(changed_surfaces)
    )
    invalidated = invalidated_surfaces_for_changes(direct_changes)
    merged_revision = {
        **state.revision_digests,
        **{
            str(key): str(value)
            for key, value in (revision_digests or {}).items()
            if str(key).strip() and str(value).strip()
        },
    }
    requested_sections = _unique(affected_section_ids)
    already_invalidated = set(state.invalidated_surfaces)
    already_affected = set(state.affected_section_ids)
    stale_id_updates = _stale_authority_id_updates(
        direct_changes=direct_changes,
        invalidated=invalidated,
        state=state,
    )
    if (
        merged_revision == state.revision_digests
        and set(invalidated).issubset(already_invalidated)
        and set(requested_sections).issubset(already_affected)
        and not stale_id_updates
    ):
        return state
    try:
        revision_number = int(str(state.revision_id).rsplit(":", 1)[-1])
    except (TypeError, ValueError):
        revision_number = 0
    return _state_update(
        state,
        revision_id=f"revision:{revision_number + 1}",
        revision_digests=merged_revision,
        revision_digest=_digest(merged_revision) if merged_revision else state.revision_digest,
        invalidated_surfaces=_unique(
            (*state.invalidated_surfaces, *invalidated)
        ),
        affected_section_ids=_unique(
            (*state.affected_section_ids, *requested_sections)
        ),
        **stale_id_updates,
    )


def _stale_authority_id_updates(
    *,
    direct_changes: Iterable[str],
    invalidated: Iterable[str],
    state: ProductAuthoringStateV1,
) -> dict[str, tuple[str, ...]]:
    """Drop downstream authority ids that were not just recompiled."""

    direct = set(direct_changes)
    updates: dict[str, tuple[str, ...]] = {}
    for surface in invalidated:
        if surface in direct:
            continue
        for field in _SURFACE_ID_FIELDS.get(str(surface), ()):
            current = getattr(state, field, ())
            if current:
                updates[field] = ()
    return updates


def close_product_authoring_issues(
    state: ProductAuthoringStateV1,
    *,
    issue_ids: Iterable[str],
    status: str = "resolved",
) -> ProductAuthoringStateV1:
    """Resolve/defer exact issue records while preserving their identities."""

    selected = set(_unique(issue_ids))
    issues = tuple(
        issue.model_copy(update={"status": status})
        if issue.issue_id in selected else issue
        for issue in state.open_issues
    )
    return _state_update(state, open_issues=issues)


def route_product_authoring_issues(
    state: ProductAuthoringStateV1,
) -> ProductAuthoringStateV1:
    """Route the first open issue to exactly one owning product node."""

    open_issues = tuple(
        issue for issue in state.open_issues if issue.status == "open"
    )
    if not open_issues:
        return _state_update(
            state,
            owner_routes=(),
            next_node="editor",
        )
    attempt = len(state.attempt_receipts) + 1
    routes: tuple[PublicationIssueOwnerRouteV1, ...] = tuple(
        PublicationIssueOwnerRouteV1(
            issue_id=issue.issue_id,
            section_id=issue.section_id,
            owner=issue.owner,
            failure_type=issue.issue_type,
            reason=issue.reason or "owner selected by product issue contract",
            attempt=attempt,
        )
        if isinstance(issue, ProductAuthoringIssueV1)
        else route_publication_issues((issue,), attempt=attempt)[0]
        for issue in open_issues
    )
    first_owner = routes[0].owner
    return _state_update(
        state,
        owner_routes=routes,
        next_node=_OWNER_NODE[first_owner],
    )


def record_product_authoring_attempt(
    state: ProductAuthoringStateV1,
    *,
    node: str,
    owner: str,
    attempt: int,
    status: str = "applied",
    issue_ids: Iterable[str] = (),
    affected_section_ids: Iterable[str] = (),
    input_digest: str = "",
    output_digest: str = "",
    information_gain: bool = False,
    semantic_delta: Mapping[str, Any] | None = None,
    stop_reason: str = "",
    next_node: str | None = None,
) -> ProductAuthoringStateV1:
    """Append one auditable attempt receipt and advance the state."""

    input_value = input_digest or state.content_digest
    output_value = output_digest or _digest({
        "input_digest": input_value,
        "node": node,
        "attempt": attempt,
        "status": status,
        "next_node": next_node or state.next_node,
    })
    delta = dict(semantic_delta or {})
    if semantic_delta is not None:
        information_gain = any(
            isinstance(value, (int, float)) and value > 0
            for value in delta.values()
        )
    receipt = ProductAuthoringAttemptReceiptV1(
        receipt_id=f"{node}:{attempt}:{output_value[-12:]}",
        node=node,
        owner=owner,
        attempt=max(1, int(attempt)),
        issue_ids=_unique(issue_ids),
        affected_section_ids=_unique(affected_section_ids),
        input_digest=input_value,
        output_digest=output_value,
        status=status,
        information_gain=bool(information_gain),
        semantic_delta=delta,
        stop_reason=stop_reason,
    )
    return _state_update(
        state,
        attempt_receipts=(*state.attempt_receipts, receipt),
        affected_section_ids=_unique(
            (*state.affected_section_ids, *affected_section_ids)
        ),
        next_node=next_node or state.next_node,
        stop_reason=stop_reason or state.stop_reason,
    )


def _default_product_node(
    node: str,
    state: ProductAuthoringStateV1,
) -> ProductAuthoringStateV1:
    if node == "writing_gap_router":
        if not state.open_issue_ids:
            return _state_update(state, next_node="mechanism_planner")
        return route_product_authoring_issues(state)
    if node == "issue_owner_router":
        return route_product_authoring_issues(state)
    if node == "editor":
        return _state_update(
            state,
            next_node=(
                "reverse_validate"
                if any(route.owner == "editor" for route in state.owner_routes)
                else "rewrite_method_language"
            ),
        )
    if node == "rewrite_method_language":
        return _state_update(
            state,
            next_node=(
                "reverse_validate"
                if any(route.owner == "rewrite" for route in state.owner_routes)
                else "split_candidate_verified"
            ),
        )
    if node == "author_review_items":
        return _state_update(
            state,
            next_node="END",
            terminal_status=(
                "review_ready_with_warnings"
                if state.open_issue_ids else "completed"
            ),
            stop_reason=(
                "open_issues_remain"
                if state.open_issue_ids else "authoring_complete"
            ),
        )
    return _state_update(state, next_node=_DEFAULT_NEXT_NODE.get(node, "END"))


NodeHandler = Callable[
    [ProductAuthoringStateV1],
    ProductAuthoringStateV1 | Mapping[str, Any],
]


def _coerce_handler_result(
    result: ProductAuthoringStateV1 | Mapping[str, Any],
) -> ProductAuthoringStateV1:
    if isinstance(result, ProductAuthoringStateV1):
        return result
    raw = dict(result)
    if "authoring_state" in raw and isinstance(raw["authoring_state"], Mapping):
        raw = dict(raw["authoring_state"])
    return ProductAuthoringStateV1.model_validate(raw)


def run_product_authoring_graph(
    initial_state: ProductAuthoringStateV1,
    *,
    node_handlers: Mapping[str, NodeHandler] | None = None,
    max_steps: int | None = None,
) -> ProductAuthoringStateV1:
    """Run the overlay with injectable owning-node implementations.

    The default handlers only advance the explicit state machine.  Production
    callers can inject the already-maintained Brief/Facet/Formalizer/Writer
    functions; no second business rule is hidden in this runner.
    """

    state = initial_state
    handlers = node_handlers or {}
    limit = max_steps or state.budgets.max_steps
    for _step in range(max(1, int(limit))):
        node = state.next_node
        if node == "END":
            return state
        if node not in PRODUCT_AUTHORING_NODE_NAMES:
            return _state_update(
                state,
                next_node="END",
                terminal_status="blocked",
                stop_reason=f"unknown_node:{node}",
            )
        before = state.content_digest
        try:
            result = handlers.get(node, lambda value: _default_product_node(node, value))(
                state
            )
            state = _coerce_handler_result(result)
        except Exception as exc:  # noqa: BLE001 - state machine records owner faults
            state = _state_update(
                state,
                next_node="END",
                terminal_status="blocked",
                stop_reason=f"{node}_failed:{type(exc).__name__}",
            )
            state = record_product_authoring_attempt(
                state,
                node=node,
                owner="system",
                attempt=sum(
                    receipt.node == node for receipt in state.attempt_receipts
                ) + 1,
                status="blocked",
                input_digest=before,
                information_gain=False,
                stop_reason=state.stop_reason,
            )
            return state
        state = record_product_authoring_attempt(
            state,
            node=node,
            owner=node,
            attempt=sum(
                receipt.node == node for receipt in state.attempt_receipts
            ) + 1,
            status="applied",
            input_digest=before,
            output_digest=state.content_digest,
            information_gain=state.content_digest != before,
        )
        if state.terminal_status != "running":
            return state
    return _state_update(
        state,
        next_node="END",
        terminal_status="review_ready_with_warnings",
        stop_reason="product_authoring_step_budget_exhausted",
    )


def _graph_state(raw: Mapping[str, Any]) -> ProductAuthoringStateV1:
    return ProductAuthoringStateV1.model_validate(
        raw.get("authoring_state") or raw
    )


def _graph_route(raw: Mapping[str, Any], node: str) -> str:
    state = _graph_state(raw)
    candidate = state.next_node
    allowed = PRODUCT_AUTHORING_CONDITIONAL_ROUTES.get(
        node,
        (_DEFAULT_NEXT_NODE.get(node, "END"),),
    )
    return candidate if candidate in allowed else allowed[0]


class _FallbackProductAuthoringGraph:
    """Small ``invoke``-compatible fallback when LangGraph is optional."""

    def __init__(
        self,
        handlers: Mapping[str, NodeHandler] | None,
        max_steps: int | None,
    ) -> None:
        self.handlers = handlers or {}
        self.max_steps = max_steps

    def invoke(
        self,
        input_state: Mapping[str, Any] | ProductAuthoringStateV1,
        config: Any | None = None,
    ) -> dict[str, Any]:
        del config
        state = (
            input_state
            if isinstance(input_state, ProductAuthoringStateV1)
            else _graph_state(input_state)
        )
        result = run_product_authoring_graph(
            state,
            node_handlers=self.handlers,
            max_steps=self.max_steps,
        )
        return {"authoring_state": result.model_dump(mode="json")}


def build_product_authoring_graph(
    *,
    node_handlers: Mapping[str, NodeHandler] | None = None,
    checkpointer: Any | None = None,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    max_steps: int | None = None,
) -> Any:
    """Build the product overlay as a LangGraph when the extra is installed."""

    try:
        from langgraph.graph import END, StateGraph
    except ImportError:  # pragma: no cover - optional dependency path
        return _FallbackProductAuthoringGraph(node_handlers, max_steps)

    graph = StateGraph(ProductAuthoringGraphState)

    def start_node(raw: dict[str, Any]) -> dict[str, Any]:
        # The overlay is resumable at any product node; the start node only
        # selects the checkpoint's next node and never changes authority.
        state = _graph_state(raw)
        return {"authoring_state": state.model_dump(mode="json")}

    def make_node(node: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
        def invoke(raw: dict[str, Any]) -> dict[str, Any]:
            state = _graph_state(raw)
            before = state.content_digest
            handler = (node_handlers or {}).get(node)
            result = (
                handler(state)
                if handler is not None
                else _default_product_node(node, state)
            )
            next_state = _coerce_handler_result(result)
            next_state = record_product_authoring_attempt(
                next_state,
                node=node,
                owner=node,
                attempt=sum(
                    receipt.node == node
                    for receipt in next_state.attempt_receipts
                ) + 1,
                input_digest=before,
                output_digest=next_state.content_digest,
                information_gain=next_state.content_digest != before,
            )
            return {
                "authoring_state": next_state.model_dump(
                    mode="json"
                )
            }

        return invoke

    graph.add_node(PRODUCT_AUTHORING_START_NODE, start_node)
    for node in PRODUCT_AUTHORING_NODE_NAMES:
        graph.add_node(node, make_node(node))
    graph.set_entry_point(PRODUCT_AUTHORING_START_NODE)
    graph.add_conditional_edges(
        PRODUCT_AUTHORING_START_NODE,
        lambda raw: _graph_state(raw).next_node,
        {
            node: node
            for node in PRODUCT_AUTHORING_NODE_NAMES
        } | {"END": END},
    )
    for source, target in PRODUCT_AUTHORING_DIRECT_EDGES:
        graph.add_edge(source, target)
    graph.add_conditional_edges(
        "writing_gap_router",
        lambda raw: _graph_route(raw, "writing_gap_router"),
        {
            target: target
            for target in PRODUCT_AUTHORING_CONDITIONAL_ROUTES["writing_gap_router"]
        },
    )
    graph.add_conditional_edges(
        "issue_owner_router",
        lambda raw: _graph_route(raw, "issue_owner_router"),
        {
            target: target
            for target in PRODUCT_AUTHORING_CONDITIONAL_ROUTES["issue_owner_router"]
        },
    )
    for node in ("editor", "rewrite_method_language"):
        graph.add_conditional_edges(
            node,
            lambda raw, source=node: _graph_route(raw, source),
            {
                target: target
                for target in PRODUCT_AUTHORING_CONDITIONAL_ROUTES[node]
            },
        )
    graph.add_edge("author_review_items", END)
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
        interrupt_after=interrupt_after,
    )


def persist_product_authoring_state(
    path: str | Path,
    state: ProductAuthoringStateV1,
) -> str:
    """Persist a product checkpoint without overwriting other artifacts."""

    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        state.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return str(output)


def load_product_authoring_state(path: str | Path) -> ProductAuthoringStateV1:
    """Load and validate one product-authoring checkpoint."""

    return ProductAuthoringStateV1.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def _artifact_ids(path: Path, keys: tuple[str, ...]) -> tuple[str, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return ()
    rows: Any = payload
    if isinstance(payload, Mapping):
        for container in (
            "briefs",
            "facets",
            "policies",
            "sections",
            "obligations",
            "claims",
            "equations",
            "items",
        ):
            if isinstance(payload.get(container), list):
                rows = payload[container]
                break
    if not isinstance(rows, list):
        return ()
    values: list[Any] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for key in keys:
            if row.get(key):
                values.append(row[key])
                break
    return _unique(values)


def build_product_authoring_state_from_artifacts(
    *,
    artifact_paths: Mapping[str, str],
    run_id: str = "",
    open_issues: Iterable[
        ProductAuthoringIssueV1 | TextRepairIssueV1 | Mapping[str, Any]
    ] = (),
    affected_section_ids: Iterable[str] = (),
    next_node: str = "research_frozen",
    terminal_status: str = "running",
    stop_reason: str = "",
    budgets: ProductAuthoringBudgetV1 | None = None,
) -> ProductAuthoringStateV1:
    """Build the shared state boundary from persisted authoring artifacts."""

    digests: dict[str, str] = {}
    for name, raw_path in artifact_paths.items():
        if str(name) == "product_authoring_state_v1":
            # A checkpoint authenticates the state; it is not an input to its
            # own revision digest.
            continue
        path_value = str(raw_path or "").strip()
        if not path_value:
            continue
        path = Path(path_value).expanduser()
        if path.is_file():
            digests[str(name)] = (
                "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            )

    def ids(name: str, keys: tuple[str, ...]) -> tuple[str, ...]:
        raw_path = str(artifact_paths.get(name, "") or "").strip()
        return _artifact_ids(Path(raw_path), keys) if raw_path else ()

    return build_product_authoring_state(
        run_id=run_id,
        frozen_digests=digests,
        revision_digests=digests,
        brief_ids=ids("method_argument_briefs_v1", ("brief_id",)),
        facet_ids=ids("method_argument_facets_v1", ("facet_id",)),
        policy_ids=ids("candidate_facet_policies_v1", ("policy_id", "facet_id")),
        formula_obligation_ids=ids(
            "formalization_section_results_v1",
            ("obligation_id", "formula_obligation_id"),
        ) or ids("equation_claims_v1", ("equation_id",)),
        section_ids=ids("method_section_plan_v2", ("section_id",)),
        open_issues=open_issues,
        affected_section_ids=affected_section_ids,
        budgets=budgets,
        next_node=next_node,
        terminal_status=terminal_status,
        stop_reason=stop_reason,
    )


def _semantic_delta_for_artifact(artifact_name: str, path_value: str) -> dict[str, int]:
    """Extract semantic (not byte-size) progress counters from one artifact."""

    path = Path(str(path_value or ""))
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        payload = None
    if artifact_name == "method_argument_facets_v1" and isinstance(payload, Mapping):
        facets = payload.get("facets") or ()
        return {"facet_bindings": len(facets)}
    if artifact_name == "facet_evidence_alignments_v1" and isinstance(payload, Mapping):
        alignments = payload.get("alignments") or ()
        return {
            "field_bindings": sum(
                len(item.get("field_bindings") or ())
                for item in alignments
                if isinstance(item, Mapping)
            ),
            "resolved_mismatches": sum(
                str(item.get("status") or "") in {"entailed", "partial"}
                for item in alignments
                if isinstance(item, Mapping)
            ),
        }
    if artifact_name == "method_section_plan_v2" and isinstance(payload, Mapping):
        sections = payload.get("sections") or ()
        return {
            "paragraph_bindings": sum(
                len(item.get("paragraphs") or ())
                for item in sections
                if isinstance(item, Mapping)
            ),
            "required_facets_placed": sum(
                len(paragraph.get("required_facet_ids") or ())
                for item in sections if isinstance(item, Mapping)
                for paragraph in (item.get("paragraphs") or ())
                if isinstance(paragraph, Mapping)
            ),
            "semantic_edges": sum(
                len(paragraph.get("required_edge_ids") or ())
                for item in sections if isinstance(item, Mapping)
                for paragraph in (item.get("paragraphs") or ())
                if isinstance(paragraph, Mapping)
            ),
        }
    if artifact_name == "formalization_section_results_v1" and isinstance(payload, Mapping):
        sections = payload.get("sections") or ()
        return {
            "formula_packages": sum(
                len(item.get("packages") or ())
                for item in sections if isinstance(item, Mapping)
            ),
            "consumed_formula_packages": sum(
                len(item.get("accepted_formula_package_ids") or ())
                for item in sections if isinstance(item, Mapping)
            ),
        }
    if artifact_name == "research_mechanism_dossiers_v1" and isinstance(payload, Mapping):
        dossiers = payload.get("items") or payload.get("dossiers") or ()
        return {
            "mechanism_dossiers": len(dossiers),
            "connected_operation_nodes": sum(
                len(item.get("ordered_operation_node_ids") or ())
                for item in dossiers
                if isinstance(item, Mapping)
            ),
            "unresolved_relations": sum(
                len(item.get("unresolved_relations") or ())
                for item in dossiers
                if isinstance(item, Mapping)
            ),
        }
    if artifact_name == "derivation_records_v1" and isinstance(payload, Mapping):
        records = payload.get("items") or payload.get("records") or ()
        return {
            "derivation_records": len(records),
            "candidate_allowed_records": sum(
                bool(item.get("candidate_allowed"))
                for item in records
                if isinstance(item, Mapping)
            ),
            "verified_eligible_records": sum(
                bool(item.get("verified_eligible"))
                for item in records
                if isinstance(item, Mapping)
            ),
        }
    if artifact_name == "candidate_authority_validation_v1" and isinstance(payload, Mapping):
        validation = payload.get("validation") or payload
        if not isinstance(validation, Mapping):
            return {}
        return {
            "candidate_authority_violations": len(validation.get("violations") or ()),
            "candidate_authority_warnings": len(validation.get("warnings") or ()),
        }
    if artifact_name == "method_content_trace_v1" and isinstance(payload, Mapping):
        summary = payload.get("summary") or {}
        return {
            "validated_witnesses": int(summary.get("rendered_paragraphs") or 0),
            "rendered_slots": int(summary.get("rendered_slots") or 0),
            "consumed_formula_packages": int(summary.get("consumed_formula_packages") or 0),
            "resolved_mismatches": int(summary.get("discovered_bound") or 0),
        }
    if artifact_name == "text_evidence_validation" and isinstance(payload, Mapping):
        return {
            "validated_claims": int(
                payload.get("validated_claim_count")
                or len(payload.get("validated_claim_ids") or ())
            ),
            "resolved_mismatches": int(payload.get("error_count") == 0),
        }
    return {}


def persist_product_authoring_state_from_writer(
    *,
    out_root: str | Path,
    artifact_paths: Mapping[str, str],
    run_id: str = "",
    open_issues: Iterable[
        ProductAuthoringIssueV1 | TextRepairIssueV1 | Mapping[str, Any]
    ] | None = None,
    affected_section_ids: Iterable[str] = (),
    terminal_status: str = "running",
    stop_reason: str = "",
) -> tuple[ProductAuthoringStateV1, str]:
    """Persist the shared overlay boundary after a Writer transaction.

    This adapter is intentionally thin: it records durable artifacts and
    node receipts, while the existing Writer/Formalizer/Editor implementations
    remain the owners of their content operations.
    """

    output = method_output(
        Path(out_root).expanduser().resolve(),
        "product_authoring_state_v1",
    )
    previous = None
    if output.is_file():
        try:
            previous = load_product_authoring_state(output)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            previous = None
    issue_records = (
        open_issues
        if open_issues is not None
        else previous.open_issues
        if previous is not None
        else ()
    )
    state = build_product_authoring_state_from_artifacts(
        artifact_paths=artifact_paths,
        run_id=run_id,
        open_issues=issue_records,
        affected_section_ids=affected_section_ids,
        next_node="END",
        terminal_status=terminal_status,
        stop_reason=stop_reason,
    )
    previous_revision_digests = dict(previous.revision_digests) if previous is not None else {}
    if previous is not None:
        state = _state_update(
            state,
            frozen_digests=previous.frozen_digests,
            frozen_revision_digest=(
                previous.frozen_revision_digest
                or state.frozen_revision_digest
            ),
            attempt_receipts=previous.attempt_receipts,
            invalidated_surfaces=previous.invalidated_surfaces,
            affected_section_ids=_unique(
                (*previous.affected_section_ids, *state.affected_section_ids)
            )
        )
        changed_artifacts = tuple(
            name for name in sorted(
                set(previous.revision_digests)
                | set(state.revision_digests)
            )
            if previous.revision_digests.get(name)
            != state.revision_digests.get(name)
        )
        changed_surfaces = _unique(
            _ARTIFACT_SURFACE.get(name, "")
            for name in changed_artifacts
        )
        if changed_surfaces:
            state = apply_dependency_invalidation(
                state,
                changed_surfaces=changed_surfaces,
                affected_section_ids=affected_section_ids,
            )

    node_artifacts = (
        ("research_frozen", "research", "research_stage_checkpoint_v1"),
        ("writing_research_continue", "research_continuation", "research_continuation_seed_v1"),
        ("writing_research_continue", "research_continuation", "research_continuation_trace_v1"),
        ("brief_compile", "brief_compiler", "method_argument_briefs_v1"),
        ("facet_decompose", "facet_decomposer", "method_argument_facets_v1"),
        ("facet_evidence_align", "facet_evidence_aligner", "facet_evidence_alignments_v1"),
        ("mechanism_planner", "research_compiler", "research_mechanism_dossiers_v1"),
        ("section_formalizer", "research_compiler", "derivation_records_v1"),
        ("mechanism_planner", "planner", "method_section_plan_v2"),
        ("architect", "architect", "method_section_plan_v2"),
        ("section_formalizer", "formalizer", "formalization_section_results_v1"),
        ("section_writer", "writer", "publication_candidate_method"),
        ("section_writer", "writer", "method_content_trace_v1"),
        ("reverse_validate", "candidate_authority", "candidate_authority_validation_v1"),
        ("section_writer", "writer", "publication_candidate_annotations_v1"),
        ("section_writer", "writer", "publication_candidate_annotated"),
        ("reverse_validate", "validator", "text_evidence_validation"),
        ("editor", "editor", "publication_editor_result_v1"),
        ("rewrite_method_language", "rewrite", "publication_rewrite_results_v1"),
        ("split_candidate_verified", "verified_splitter", "repository_verified_method"),
    )
    for node, owner, artifact_name in node_artifacts:
        if (
            artifact_name == "research_continuation_seed_v1"
            and artifact_paths.get("research_continuation_trace_v1")
        ):
            continue
        if not artifact_paths.get(artifact_name):
            continue
        semantic_delta = _semantic_delta_for_artifact(
            artifact_name,
            str(artifact_paths.get(artifact_name) or ""),
        )
        state = record_product_authoring_attempt(
            state,
            node=node,
            owner=owner,
            attempt=sum(
                receipt.node == node for receipt in state.attempt_receipts
            ) + 1,
            affected_section_ids=affected_section_ids,
            input_digest=state.revision_digest,
            output_digest=state.revision_digests.get(artifact_name, ""),
            information_gain=(
                any(value > 0 for value in semantic_delta.values())
                if semantic_delta
                else (
                    previous is None
                    or previous_revision_digests.get(artifact_name)
                    != state.revision_digests.get(artifact_name)
                )
            ),
            semantic_delta=semantic_delta if semantic_delta else None,
            next_node="END",
            stop_reason=(
                stop_reason
                or (
                    "no_semantic_delta"
                    if previous is not None
                    and not any(value > 0 for value in semantic_delta.values())
                    else ""
                )
            ),
        )
    if state.open_issue_ids:
        state = route_product_authoring_issues(state)
    if artifact_paths.get("writing_research_callback_artifacts_v1"):
        state = record_product_authoring_attempt(
            state,
            node="writing_gap_router",
            owner="writing_gap_router",
            attempt=sum(
                receipt.node == "writing_gap_router"
                for receipt in state.attempt_receipts
            ) + 1,
            issue_ids=state.open_issue_ids,
            affected_section_ids=affected_section_ids,
            information_gain=False,
            next_node="END",
            stop_reason=(
                "writing_callbacks_pending"
                if state.open_issue_ids else "writing_gap_checked"
            ),
        )
    if state.open_issue_ids:
        state = record_product_authoring_attempt(
            state,
            node="issue_owner_router",
            owner="issue_owner_router",
            attempt=sum(
                receipt.node == "issue_owner_router"
                for receipt in state.attempt_receipts
            ) + 1,
            issue_ids=state.open_issue_ids,
            affected_section_ids=affected_section_ids,
            information_gain=False,
            next_node="END",
            stop_reason="open_issues_remain",
        )
    # Finish through the same compiled graph used by callers that need a
    # resumable LangGraph boundary.  Existing content stages remain adapters;
    # this final node only commits the already computed review disposition.
    state = _state_update(
        state,
        next_node="author_review_items",
        terminal_status=terminal_status,
        stop_reason=stop_reason,
    )

    def finalize_review(value: ProductAuthoringStateV1) -> ProductAuthoringStateV1:
        return _state_update(
            value,
            next_node="END",
            terminal_status=terminal_status,
            stop_reason=stop_reason,
        )

    graph = build_product_authoring_graph(
        node_handlers={"author_review_items": finalize_review},
        max_steps=1,
    )
    graph_result = graph.invoke(
        {"authoring_state": state.model_dump(mode="json")}
    )
    state = _coerce_handler_result(graph_result)
    persist_product_authoring_state(output, state)
    return state, str(output)


__all__ = [
    "PRODUCT_AUTHORING_SCHEMA_VERSION",
    "PRODUCT_AUTHORING_CONDITIONAL_ROUTES",
    "PRODUCT_AUTHORING_DIRECT_EDGES",
    "PRODUCT_AUTHORING_GRAPH_CONTRACT",
    "PRODUCT_AUTHORING_NODE_NAMES",
    "PRODUCT_AUTHORING_START_NODE",
    "ProductAuthoringAttemptReceiptV1",
    "ProductAuthoringBudgetV1",
    "ProductAuthoringGraphState",
    "ProductAuthoringIssueV1",
    "ProductAuthoringStateV1",
    "apply_dependency_invalidation",
    "build_product_authoring_graph",
    "build_product_authoring_state",
    "build_product_authoring_state_from_artifacts",
    "close_product_authoring_issues",
    "invalidated_surfaces_for_changes",
    "load_product_authoring_state",
    "persist_product_authoring_state",
    "persist_product_authoring_state_from_writer",
    "record_product_authoring_attempt",
    "route_product_authoring_issues",
    "run_product_authoring_graph",
]
